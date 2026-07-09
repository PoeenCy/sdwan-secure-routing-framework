import os
from src.microseg.zone_matrix import ZoneMatrix
from src.models.graph_c import GraphC

def test_zone_matrix_rules():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    zm = ZoneMatrix(config_dir)

    # Test allowed
    assert zm.is_allowed("Core", "Core") is True
    assert zm.is_allowed("Core", "FIN") is True
    assert zm.is_allowed("IT", "FIN") is True
    
    # Test blocked
    assert zm.is_allowed("DMZ", "FIN") is False
    assert zm.is_allowed("HR", "FIN") is False

    # Test business whitelist check
    C = GraphC()
    C.add_node('0', zone='Core')
    C.add_node('5', zone='DMZ')
    C.add_node('7', zone='FIN')
    C.add_node('14', zone='IT')
    
    # Core <-> * is mandatory
    assert zm.is_mandatory_edge(C, '0', '5') is True
    # IT <-> * is mandatory
    assert zm.is_mandatory_edge(C, '14', '7') is True
    # DMZ <-> FIN is NOT mandatory
    assert zm.is_mandatory_edge(C, '5', '7') is False
