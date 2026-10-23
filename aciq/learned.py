"""Optional learned classifier with deterministic comparison.

The shipped classifier is deterministic and rule-based. This adds a tiny,
pure-Python learned model that uses only the same features the rule-based
classifier sees, trains on a deterministic synthetic set, and can be compared
against it without becoming the default path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .flowtrack import FlowFeatures
from .model import Classification, TrafficClass


@dataclass(frozen=True)
class ComparisonRow:
    case: str
    rule_cls: TrafficClass | None
    learned_cls: TrafficClass | None
    agree: bool
    rule_tier: str
    learned_tier: str


class LogisticClassifier:
    def __init__(self, lr: float = 0.1, epochs: int = 200):
        self.lr = lr
        self.epochs = epochs
        self.weights: dict[tuple[TrafficClass, str], float] = {}
        self.bias: dict[TrafficClass, float] = {c: 0.0 for c in TrafficClass}
        self.trained = False

    @staticmethod
    def _features(f: FlowFeatures, capacity_mbps: float) -> dict[str, float]:
        flow = f.flow
        age = max(float(f.age_s), 1e-6)
        packets = max(int(f.packets), 0)
        bytes_total = max(float(f.rx_bytes) + float(f.tx_bytes), 0.0)
        rate_mbps = (bytes_total * 8.0 / 1_000_000.0) / age
        pps = packets / age
        bpp = (bytes_total / packets) if packets else 0.0
        duty = float(f.duty_cycle or 0.0)
        burst = float(f.burstiness or 0.0)
        dscp_ef = 1.0 if f.dscp == 46 else 0.0
        is_udp = 1.0 if flow.proto == "udp" else 0.0
        is_tcp = 1.0 if flow.proto == "tcp" else 0.0
        is_rtp = 1.0 if flow.dport in (5001, 5002, 3478, 7000) else 0.0
        rel = rate_mbps / max(capacity_mbps, 1e-6)
        return {
            "bias": 1.0,
            "dscp_ef": dscp_ef,
            "is_udp": is_udp,
            "is_tcp": is_tcp,
            "is_rtp": is_rtp,
            "pps": min(pps / 1000.0, 10.0),
            "bpp": min(bpp / 1500.0, 10.0),
            "duty": duty,
            "burst": burst,
            "rate_mbps": min(rate_mbps / 1000.0, 10.0),
            "rel": min(rel, 10.0),
            "bulk_like": 1.0 if (rel >= 0.5 and bytes_total >= 10_000_000) else 0.0,
        }

    def fit(self) -> LogisticClassifier:
        data = _synthetic()
        for _ in range(self.epochs):
            for feats, label, w in data:
                v = self._logits(feats)
                exps = {c: 2.718281828459045 ** (v[c] - max(v.values())) for c in v}
                s = sum(exps.values()) or 1.0
                probs = {c: exps[c] / s for c in v}
                for c in TrafficClass:
                    y = 1.0 if c == label else 0.0
                    err = probs[c] - y
                    self.bias[c] -= self.lr * err * w
                    for k, val in feats.items():
                        self.weights[(c, k)] = self.weights.get((c, k), 0.0) - self.lr * err * val * w
        self.trained = True
        return self

    def _logits(self, feats: dict[str, float]) -> dict[TrafficClass, float]:
        v = {c: self.bias.get(c, 0.0) for c in TrafficClass}
        for (c, k), w in self.weights.items():
            v[c] = v.get(c, 0.0) + w * feats.get(k, 0.0)
        return v

    def predict(self, f: FlowFeatures, capacity_mbps: float) -> Classification:
        if not self.trained:
            self.fit()
        feats = self._features(f, capacity_mbps)
        v = self._logits(feats)
        order = sorted(v.items(), key=lambda kv: kv[1], reverse=True)
        top_cls, top_log = order[0]
        second = order[1][1] if len(order) > 1 else top_log - 10.0
        margin = max(0.0, top_log - second)
        conf = min(0.99, 1.0 / (1.0 + 2.718281828459045 ** (-margin)))
        if conf < 0.5:
            return Classification(cls=None, confidence=0.0, tier="abstain",
                                  flow=f.flow, evidence="learned: abstain")
        return Classification(cls=top_cls, confidence=round(conf, 3),
                              tier="learned", flow=f.flow,
                              evidence="learned: logistic")


def _synthetic() -> list[tuple[dict[str, float], TrafficClass, float]]:
    data: list[tuple[dict[str, float], TrafficClass, float]] = []
    for _ in range(80):
        data.append(({"bias": 1.0, "dscp_ef": 1.0, "is_udp": 1.0, "is_rtp": 1.0,
                      "pps": 0.3, "bpp": 0.08, "duty": 0.5, "burst": 0.1,
                      "rel": 0.01, "bulk_like": 0.0}, TrafficClass.INTERACTIVE, 1.0))
    for _ in range(80):
        data.append(({"bias": 1.0, "dscp_ef": 0.0, "is_udp": 0.0, "is_tcp": 1.0,
                      "pps": 0.05, "bpp": 1.8, "duty": 0.8, "burst": 0.15,
                      "rel": 0.2, "bulk_like": 0.0}, TrafficClass.ADAPTIVE, 1.0))
    for _ in range(80):
        data.append(({"bias": 1.0, "dscp_ef": 0.0, "is_udp": 0.0, "is_tcp": 1.0,
                      "pps": 0.002, "bpp": 8.0, "duty": 0.99, "burst": 0.02,
                      "rel": 0.8, "bulk_like": 1.0}, TrafficClass.BULK, 1.0))
    return data


def compare(rule_fn, learned: LogisticClassifier, cases) -> list[ComparisonRow]:
    rows = []
    for name, feats, cap in cases:
        r = rule_fn(feats, cap)
        l = learned.predict(feats, cap)
        rows.append(ComparisonRow(name, r.cls, l.cls,
                                  r.cls == l.cls, r.tier, l.tier))
    return rows
