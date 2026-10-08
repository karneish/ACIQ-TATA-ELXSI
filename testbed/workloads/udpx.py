"""Shared UDP echo engine for the call and game generators.

Why this exists: iperf3 is a TCP bulk tool. It cannot represent a voice call or
a game. TATA's brief needs latency measured *on the call's own traffic*, so the
call carries its own sequence numbers and its own timing, and the sink echoes
the sequence number back. RTT, jitter and loss are then measured from the call's
own packets rather than inferred from ICMP.

Payload layout:  b'ACIQ' | seq (4 bytes, big endian) | sent_monotonic_ns (8)
Only the sequence number is echoed, so the reply is tiny.

No payload of any real application is read. This is synthetic traffic we
generate ourselves, which is also what gives M1 free ground-truth labels.
"""

from __future__ import annotations

import socket
import struct
import threading
import time

MAGIC = b"ACIQ"
HDR = struct.Struct("!4sIQ")  # magic, seq, send-time ns
PREAMBLE = MAGIC + struct.pack("!I", 0) + b"\x00" * 8
#: recvfrom() returns at once when a reply is already queued, so a short value
#: costs nothing under load. A long one blocks the send loop when idle.
DRAIN_TIMEOUT_S = 0.0005


def parse(data: bytes) -> tuple[int, int] | None:
    """Return (seq, sent_ns) from a payload, or None if it isn't ours."""
    if len(data) < HDR.size or not data.startswith(MAGIC):
        return None
    _, seq, ns = HDR.unpack(data[: HDR.size])
    return seq, ns


def build(seq: int, sent_ns: int, pad: int = 0) -> bytes:
    return HDR.pack(MAGIC, seq, sent_ns) + b"\x00" * pad


def jain_fairness(values: list[float]) -> float:
    """Jain's fairness index: (sum x)^2 / (n * sum x^2). 1.0 = perfectly fair."""
    n = len(values)
    if n == 0:
        return 0.0
    s = sum(values)
    sq = sum(v * v for v in values)
    if sq == 0:
        return 0.0
    return (s * s) / (n * sq)


class EchoSink:
    """Listens on a UDP port and echoes the sequence number back to the sender."""

    def __init__(self, port: int, host: str = "0.0.0.0", family: int = socket.AF_INET):
        self.family = family
        self.sock = socket.socket(family, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self._stop = threading.Event()
        self.packets = 0
        self.bytes = 0
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        self.sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            parsed = parse(data)
            if parsed is None:
                continue
            seq, _ = parsed
            try:
                self.sock.sendto(HDR.pack(MAGIC, seq, 0), addr)
            except OSError:
                pass
            self.packets += 1
            self.bytes += len(data)

    def start(self) -> "EchoSink":
        self.thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self.thread.join(timeout=1.0)
        try:
            self.sock.close()
        except OSError:
            pass


class UdpProbe:
    """A timed UDP flow that measures its own RTT, jitter and loss.

    Cadence is in milliseconds, because a call sends a packet roughly every
    20 ms and that cadence is what makes it latency-sensitive rather than
    merely small.
    """

    def __init__(
        self,
        dst: str,
        port: int,
        pps: float = 50.0,
        payload_bytes: int = 256,
        family: int = socket.AF_INET,
        label: str = "probe",
    ):
        self.dst = dst
        self.port = port
        self.interval = 1.0 / pps
        self.payload_bytes = max(0, payload_bytes - HDR.size)
        self.family = family
        self.label = label

        self.sock = socket.socket(family, socket.SOCK_DGRAM)
        self.addr = (dst, port, 0, 0) if family == socket.AF_INET6 else (dst, port)

        self.sent = 0
        self.received = 0
        self.elapsed_s = 0.0
        self.rtts_ms: list[float] = []
        self.loss_events: list[tuple[int, int]] = []  # (seq, gap_size)
        self._waiting: dict[int, float] = {}

    # --- stats ---------------------------------------------------------------
    @property
    def loss_ratio(self) -> float:
        return 0.0 if self.sent == 0 else 1.0 - (self.received / self.sent)

    def jitter_ms(self) -> float:
        """Mean absolute consecutive-difference of RTT samples (RFC 3550 style).

        Positive means the path is getting less steady, which is what a call
        actually cares about.
        """
        if len(self.rtts_ms) < 2:
            return 0.0
        d = [abs(self.rtts_ms[i] - self.rtts_ms[i - 1]) for i in range(1, len(self.rtts_ms))]
        return sum(d) / len(d)

    def percentiles(self, ps: tuple[float, ...] = (50, 95, 99)) -> dict[str, float]:
        if not self.rtts_ms:
            return {f"p{int(p)}": 0.0 for p in ps}
        xs = sorted(self.rtts_ms)
        out = {}
        for p in ps:
            idx = min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1))))
            out[f"p{int(p)}"] = xs[idx]
        return out

    def report(self) -> dict:
        pct = self.percentiles()
        elapsed = max(self.elapsed_s, 1e-9)
        return {
            "label": self.label,
            "sent": self.sent,
            "received": self.received,
            "loss_ratio": round(self.loss_ratio, 5),
            "jitter_ms": round(self.jitter_ms(), 4),
            **{k: round(v, 3) for k, v in pct.items()},
            # achieved rate, measured. Must match the requested pps closely or
            # the generator is not behaving like the traffic it claims to be.
            "pps_requested": round(1.0 / self.interval, 2),
            "pps_achieved": round(self.sent / elapsed, 2),
            "elapsed_s": round(elapsed, 3),
            "loss_events": self.loss_events[:10],
        }

    # --- run -----------------------------------------------------------------
    def run(self, duration_s: float, dscp: int | None = None) -> dict:
        """Send at the configured cadence for `duration_s`, collecting replies.

        The send loop must not let packet transmission delay the cadence: a busy
        sink or a scheduled loop that falls behind silently under-sends and
        reports a throughput far below the configured rate. Catch up against a
        fixed start time so the achieved pps matches what was asked for.
        """
        if dscp is not None:
            self._mark(dscp)
        # A short timeout is load-bearing: recvfrom() returns immediately when a
        # reply is already queued, so a small timeout costs nothing when traffic
        # is flowing. A long timeout makes each drain() block for that whole
        # duration whenever nothing is waiting, which silently throttles the
        # send cadence to 1/timeout packets per second.
        self.sock.settimeout(DRAIN_TIMEOUT_S)
        start = time.monotonic()
        end = start + duration_s
        next_send = start
        seq = 0
        while True:
            now = time.monotonic()
            if now >= end:
                break
            if now >= next_send:
                t_ns = time.monotonic_ns()
                try:
                    self.sock.sendto(build(seq, t_ns, self.payload_bytes), self.addr)
                    self._waiting[seq] = t_ns
                    self.sent += 1
                except OSError:
                    pass
                seq += 1
                next_send += self.interval
                # Drain after each send so the socket buffer never backs up and
                # makes the next sendto() slow.
                self._drain()
            else:
                time.sleep(max(0.0, next_send - now))
        self._drain()
        self._compute_loss()
        self.elapsed_s = time.monotonic() - start
        return self.report()

    def _drain(self) -> None:
        """Collect any replies that arrived since the last check."""
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
            except socket.timeout:
                return
            except OSError:
                return
            parsed = parse(data)
            if parsed is None:
                continue
            seq, _sent = parsed
            t_ns = self._waiting.pop(seq, None)
            if t_ns is None:
                continue
            self.received += 1
            self.rtts_ms.append((time.monotonic_ns() - t_ns) / 1e6)

    def _compute_loss(self) -> None:
        """Any sequence number never acked is a loss event."""
        missing = sorted(set(range(self.sent)) - set(range(self.received)))
        run = 0
        for s in missing:
            run += 1
        if missing:
            self.loss_events = [(missing[0], run)]

    def _mark(self, dscp: int) -> None:
        """Set the DSCP on outgoing packets so tc filters can match them."""
        try:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, dscp << 2)
        except OSError:
            pass  # not fatal: the probe still measures RTT, just not class placement

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass
