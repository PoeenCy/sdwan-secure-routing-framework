import os
from src.models.graph_c import GraphC
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.routing.action_mask import ActionMask

def test_action_masking():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    pdp = PDP(config_dir)
    pdp.use_adaptive_theta = False
    pdp.use_avod_context = False
    zm = ZoneMatrix(config_dir)
    
    C = GraphC()
    C.add_node('9', zone='HR')
    C.add_node('7', zone='FIN')
    C.add_edge('9', '7', bandwidth_mbps=100.0, delay_ms=10.0)
    C.set_node_zones({'HR': ['9'], 'FIN': ['7']})

    # Override behavior and identity to pass trust check
    pdp.identity.set_score('9', 1.0)
    pdp.context.set_patch_factor('9', 1.0)
    pdp.behavior.set_score('9', 0.95)
    pdp.identity.set_score('7', 1.0)
    pdp.context.set_patch_factor('7', 1.0)
    pdp.behavior.set_score('7', 0.90)
    # HR context = 1 - 8.8/10 = 0.12.
    # Weighted T('9') = 0.4*1 + 0.3*0.95 + 0.3*0.12 = 0.721 < 0.90.
    
    struct_mask = {'9': True, '7': True}
    node_masks = ActionMask.build_node_masks(C, pdp, '9', '7', struct_mask)
    
    # Node '9' fails trust check (0.721 < 0.90)
    assert node_masks['9'] is False
    
    # Lower the threshold so HR passes but FIN still fails.
    pdp.theta_zone['HR'] = 0.70
    pdp.theta_zone['FIN'] = 0.70
    node_masks_2 = ActionMask.build_node_masks(C, pdp, '9', '7', struct_mask)
    # T('9') = 0.721 >= 0.70 -> True
    # FIN context = 1 - 9.8/10 = 0.02, T('7') = 0.676 < 0.70 -> False.
    assert node_masks_2['9'] is True
    assert node_masks_2['7'] is False
