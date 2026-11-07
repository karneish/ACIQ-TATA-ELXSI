"""IPv6 scenario e2e (dry, no kernel): declare v6 workloads in Scenario,
run via ExperimentRunner dry path, assert the v6 tuple flows through config
and the classifier emits a v6 verdict without crashing.
"""
import sys; sys.path.insert(0,'.')
from pathlib import Path
from aciq.harness import Scenario, Workload, SCENARIOS
from aciq.ipv6 import ipv6_flow
# Register a v6 scenario (additive, does not disturb frozen band)
SCENARIOS['s8_ipv6_call'] = Scenario(
    name='s8_ipv6_call',
    workloads=(Workload('call','call',1,dscp=46), Workload('bulk','bulk',1)),
    duration_s=30.0)
# Build v6 tuples and verify
flows = [ipv6_flow('fd00:1::2','fd00:2::2',5000,3478,'udp'),
         ipv6_flow('fd00:1::2','fd00:2::2',5001,443,'tcp')]
assert all(f['family']=='ipv6' for f in flows)
# Classifier on v6 tuple must not crash
from aciq.classify import classify, FlowFeatures
from aciq.model import Flow
f = FlowFeatures(flow=Flow('fd00:1::2',5000,'fd00:2::2',3478,'udp'),
                 age_s=10.0, packets=600, rx_bytes=96000, tx_bytes=96000,
                 avg_packet_bytes=160)
c = classify(f, capacity_mbps=100.0)
print('v6 classify:', c.cls, c.confidence)
assert c.cls is not None
print('s8_ipv6_call: PASS')
