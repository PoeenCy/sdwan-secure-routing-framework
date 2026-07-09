import os
import yaml

def test_load_configs():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    
    # 1. zone_matrix.yaml
    with open(os.path.join(config_dir, "zone_matrix.yaml"), 'r', encoding='utf-8') as f:
        matrix_data = yaml.safe_load(f)
        assert 'matrix' in matrix_data
        assert 'Core' in matrix_data['matrix']
        assert matrix_data['matrix']['Core']['Core'] == 1

    # 2. zone_mapping.yaml
    with open(os.path.join(config_dir, "zone_mapping.yaml"), 'r', encoding='utf-8') as f:
        mapping_data = yaml.safe_load(f)
        assert 'zones' in mapping_data
        assert 'Core' in mapping_data['zones']
        assert '0' in mapping_data['zones']['Core']

    # 3. trust_policy.yaml
    with open(os.path.join(config_dir, "trust_policy.yaml"), 'r', encoding='utf-8') as f:
        trust_data = yaml.safe_load(f)
        assert 'theta_zone' in trust_data
        assert trust_data['theta_zone']['FIN'] == 0.90

    # 4. cve_profiles.yaml
    with open(os.path.join(config_dir, "cve_profiles.yaml"), 'r', encoding='utf-8') as f:
        cve_data = yaml.safe_load(f)
        assert 'nodes' in cve_data
        assert all(str(node_id) in cve_data['nodes'] for node_id in range(19))
        assert cve_data['nodes']['5']['zone'] == 'DMZ'
        assert cve_data['nodes']['5']['cve_list'][0]['access_vector'] == 'NETWORK'

    # 5. qos_catalog.yaml
    with open(os.path.join(config_dir, "qos_catalog.yaml"), 'r', encoding='utf-8') as f:
        qos_data = yaml.safe_load(f)
        assert 'services' in qos_data
        assert qos_data['services']['VoIP']['max_delay'] == 150

    # 6. hyperparams.yaml
    with open(os.path.join(config_dir, "hyperparams.yaml"), 'r', encoding='utf-8') as f:
        hyper_data = yaml.safe_load(f)
        assert hyper_data['reward']['alpha'] == 0.30
        assert hyper_data['reward']['theta_bn'] == 0.30
