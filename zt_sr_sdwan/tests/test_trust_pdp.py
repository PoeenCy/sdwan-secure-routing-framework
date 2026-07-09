import os
from src.trust.pdp import PDP
from src.trust import compute_trust_score
from src.models.graph_c import GraphC

def test_pdp_calculations():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    pdp = PDP(config_dir)

    # Test theta_path
    assert pdp.get_theta_path("HR", "FIN") == 0.90
    assert pdp.get_theta_path("DMZ", "HR") == 0.60

    assert compute_trust_score(1.0, 1.0, 1.0) == 1.0
    assert compute_trust_score(0.0, 0.0, 0.0) == 0.0
    assert abs(compute_trust_score(0.75, 0.9, 0.8) - 0.81) < 0.001

    # Weighted trust calculation with deterministic component overrides.
    pdp.behavior.set_score('11', 0.85)
    pdp.identity.set_score('11', 1.0)
    pdp.context.set_patch_factor('11', 1.0)
    # HR zone max CVSS = 8.8, so C = 0.12. T = 0.4*1 + 0.3*0.85 + 0.3*0.12
    assert abs(pdp.get_trust_score('11', 'HR') - 0.691) < 1e-5


def test_new_trust_components():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    pdp = PDP(config_dir)
    
    # 1. Identity posture scenario test.
    pdp.identity.set_scenario('14', 'partially_compliant')
    assert pdp.identity.get_score('14', strict=False) == 0.75
    assert pdp.identity.get_score('14', strict=True) == 0.0
    pdp.identity.set_scenario('15', 'compromised')
    assert pdp.identity.get_score('15', strict=False) == 0.25
    
    # 2. Behavior scenarios and anomaly override test.
    pdp.behavior.set_scenario('16', 'lateral_movement')
    lateral_score = pdp.behavior.get_score('16')
    assert 0.0 <= lateral_score <= 0.5
    pdp.behavior.set_anomaly_metrics('14', 1.5, 1.0, 0.5)
    assert pdp.behavior.get_score('14') == 0.0

    # 3. AVOD Context test & Adaptive Theta
    C = GraphC()
    C.add_node('9', zone='HR')
    C.add_node('7', zone='FIN')
    C.add_edge('9', '7', bandwidth_mbps=100.0, delay_ms=10.0)
    C.set_node_zones({'HR': ['9'], 'FIN': ['7']})
    
    pdp.use_avod_context = True
    pdp.use_adaptive_theta = True
    pdp.k_factor = 1.0
    
    # Node '9' (HR) has 1 active out-edge, so AVOD('HR') = 1.0
    # Node '7' (FIN) has 0 active out-edge, so AVOD('FIN') = 0.0
    # Max AVOD is 1.0
    # C('9') = 1 - (1.0 / 1.0) = 0.0
    # C('7') = 1 - (0.0 / 1.0) = 1.0
    # Verify context score of '9' is 0.0 and '7' is 1.0
    assert pdp.context.get_score('9', 'HR', C, use_avod_context=True) == 0.0
    assert pdp.context.get_score('7', 'FIN', C, use_avod_context=True) == 1.0

    # Let's clear anomaly metrics so we can check trust scores & adaptive theta
    pdp.behavior.anomaly_metrics.clear()
    pdp.identity.conditions.clear()
    pdp.behavior.set_score('7', 0.90)
    pdp.behavior.set_score('9', 0.90)
    
    # Trust scores use weighted sum:
    # T('9') = 0.4*1 + 0.3*0.90 + 0.3*0 = 0.67
    # T('7') = 0.4*1 + 0.3*0.90 + 0.3*1 = 0.97
    t_9 = pdp.get_trust_score('9', 'HR', C)
    t_7 = pdp.get_trust_score('7', 'FIN', C)
    assert abs(t_9 - 0.67) < 1e-5
    assert abs(t_7 - 0.97) < 1e-5

    
    # Adaptive theta = mean([t_9, t_7]) + k * std([t_9, t_7])
    import numpy as np
    expected_theta = np.mean([t_9, t_7]) + 1.0 * np.std([t_9, t_7])
    assert abs(pdp.get_theta_path('HR', 'FIN', C) - expected_theta) < 1e-5
