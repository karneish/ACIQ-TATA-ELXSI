"""Force-safe teardown on signals and timeouts (M-controller support).

A killed controller must leave the kernel like it never existed. "Kill -9 the
python process" leaves every `tc` class and `flower` filter it installed
behind: the kernel keeps running what the dead process configured, forever.
So the shutdown path cannot be "whatever the exception machinery decides" --
it has to be an explicit, installed, ordered handler that runs the safe path
FIRST and only then lets the process die the way it would have anyway.

This module is deliberately tiny and has zero aciq imports apart from nothing:
it takes the safe callable as a parameter, so it can be unit-tested offline
and drives teardown from the caller (which knows its own Bridge).

## Semantics

- **idempotent latch**: a second signal cannot re-enter a half-torn-down
  teardown. The first signal runs exactly one safe-path invocation.
- **exceptions in the safe path are reported to stderr but swallowed** for the
  handoff: a raised exception inside a signal handler would abort the process
  BEFORE the cleanup finished, which is exactly the residue we exist to
  prevent.
- **the delivered signal still kills the process properly.** After the safe
  path runs, the handler resets to SIG_DFL and re-raises the same signal --
  the process exits with the code the caller would have seen without us
  (e.g. 143 for SIGTERM). Nothing is masked, nothing is silently turned into
  success.
- **timeout watchdog is optional** (`timeout_s`): a live hang (the dangerous
  case for enforcement) must produce the same safe path, via SIGALRM /
  setitimer, with the same exit semantics it never makes up.

An earlier phase's gap note said "signal/watchdog safe path" was missing from
the enforcement module list; a contract here that mentioned teardown but
relied on the caller remembering to install is how that gap would survive a
refactor. `install()` returns self and callers are expected to keep the
reference: a garbage-collected handler object whose method the C signal
mechanism references is a use-after-free in the making.
"""

from __future__ import annotations

import os
import signal


class Watchdog:
    """Installs signal/timeout handlers running `safe_fn` once, then exits."""

    def __init__(self, safe_fn, *, timeout_s: float | None = None,
                 signaller=signal, re_raise: bool = True):
        # `signaller` exists so offline tests can stand in a recorder for the
        # real C-level signal module; `re_raise=False` keeps the process alive
        # for tests that only assert the safe path ran.
        self.safe_fn = safe_fn
        self.timeout_s = timeout_s
        self._sig = signaller
        self._re_raise = re_raise
        self._fired = False
        self.reason: str | None = None

    @property
    def engaged(self) -> bool:
        return self._fired

    def install(self) -> "Watchdog":
        s = self._sig
        for sig in (signal.SIGTERM, signal.SIGINT):
            s.signal(sig, self._on_signal)
        if self.timeout_s is not None and self.timeout_s > 0:
            s.signal(signal.SIGALRM, self._on_signal)
            s.setitimer(signal.ITIMER_REAL, self.timeout_s)
        return self

    def disarm(self) -> None:
        """Cancel a pending timeout without engaging the safe path."""
        if self.timeout_s is not None and self.timeout_s > 0:
            self._sig.setitimer(signal.ITIMER_REAL, 0.0)

    def _on_signal(self, signum, frame):
        if self._fired:
            return
        self._fired = True
        self.reason = {signal.SIGTERM: "sigterm", signal.SIGINT: "sigint",
                       signal.SIGALRM: "timeout"}.get(signum, f"signal{signum}")
        print(f"[watchdog] {self.reason}: force-safe path engaged", flush=True)
        try:
            self.safe_fn()
        except Exception as e:                      # noqa: BLE001
            # Swallow deliberately: the residue is the thing we must finish.
            print(f"[watchdog] force-safe raised {e!r}; continuing exit",
                  flush=True)
        if not self._re_raise:
            return
        # Exit the way the original signal intended. Resetting to SIG_DFL and
        # re-raising preserves the caller's exit status (128+n) instead of a
        # synthetic sys.exit code that could be mistaken for a normal verify
        # result.
        self._sig.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
