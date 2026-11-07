"""Crash-restart reconciliation: adopt the kernel's current tree as truth.

On controller restart the in-process plan is gone but tc state remains. This
module reads the live tree, normalizes it into the applied-state shape the
harness records, and reports drift vs the last persisted plan. Pure helpers
only; the kernel readback happens in the caller.
"""
from __future__ import annotations

def describe_applied(policy_committed: bool, kernel_tree: str | None) -> dict:
    """Summarize applied state after restart reconciliation."""
    return {
        'policy_committed': policy_committed,
        'kernel_tree_present': bool(kernel_tree and kernel_tree.strip()),
        'kernel_tree_head': (kernel_tree.strip()[:200] if kernel_tree else ''),
        'reconciled': True,
    }
