from src.models.graph_c import GraphC
from src.models.graph_g import GraphG


def test_generate_from_c_uses_reachability_and_exploitable_cves():
    C = GraphC()
    C.add_node('A', zone='DMZ')
    C.add_node('B', zone='HR')
    C.add_node('C', zone='HR')
    C.add_node('D', zone='FIN')
    C.add_node('E', zone='Core')
    C.add_edges_from([
        ('A', 'B', {'bandwidth_mbps': 100.0}),
        ('B', 'C', {'bandwidth_mbps': 100.0}),
        ('C', 'D', {'bandwidth_mbps': 100.0}),
        ('D', 'E', {'bandwidth_mbps': 100.0}),
    ])

    cve_profiles = {
        'A': {'cve_list': []},
        'B': {'cve_list': [{
            'cvss_score': 9.8,
            'cvss_vector': 'AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
        }]},
        'C': {'cve_list': [{
            'cvss_score': 7.8,
            'cvss_vector': 'AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
        }]},
        'D': {'cve_list': [{
            'cvss_score': 8.8,
            'cvss_vector': 'AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H',
        }]},
        'E': {'cve_list': [{
            'cvss_score': 10.0,
            'cvss_vector': 'AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H',
        }]},
    }

    G = GraphG().generate_from_c(C, cve_profiles)

    assert 'A' in G.entry_nodes
    assert 'E' in G.entry_nodes
    assert 'D' in G.target_nodes
    assert 'E' in G.target_nodes
    assert G.nodes['E']['is_critical'] is True
    assert ('A', 'B') in G.edges()
    assert ('B', 'C') not in G.edges()
    assert ('C', 'D') not in G.edges()
    assert ('D', 'E') in G.edges()
    assert len(G.entry_nodes) >= 2
    assert len(G.target_nodes) == 2
