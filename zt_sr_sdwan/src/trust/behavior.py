import numpy as np


BEHAVIOR_SCENARIOS = {
    'normal': {
        'description': 'Normal behavior within baseline',
        'mean': 0.90,
        'std': 0.05,
    },
    'anomalous_traffic': {
        'description': 'C2 communication pattern, MITRE ATT&CK T1071',
        'mean': 0.40,
        'std': 0.15,
    },
    'lateral_movement': {
        'description': 'Remote Services lateral movement, MITRE ATT&CK T1021',
        'mean': 0.25,
        'std': 0.10,
    },
}


class BehaviorProvider:
    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)
        self.statuses = {}       # node_id -> 'NORMAL' or 'ATTACK'
        self.attack_ticks = {}   # node_id -> tick counter for linear drop
        self.override_scores = {} # node_id -> fixed behavior score
        self.scenarios = {}
        # Anomaly metrics: {node_id: {'x': current_value, 'mu': mean, 'sigma': std}}
        self.anomaly_metrics = {}

    def set_anomaly_metrics(self, node_id: str, x: float, mu: float, sigma: float):
        self.anomaly_metrics[str(node_id)] = {'x': float(x), 'mu': float(mu), 'sigma': float(sigma)}

    def set_status(self, node_id: str, status: str):
        self.statuses[str(node_id)] = status
        if status == 'NORMAL':
            self.set_scenario(node_id, 'normal')
        elif status == 'ATTACK':
            self.set_scenario(node_id, 'anomalous_traffic')
            self.attack_ticks[str(node_id)] = 0

    def set_scenario(self, node_id: str, scenario: str):
        if scenario not in BEHAVIOR_SCENARIOS:
            raise ValueError(f"Unknown behavior scenario: {scenario}")
        self.scenarios[str(node_id)] = scenario

    def set_score(self, node_id: str, score: float):
        self.override_scores[str(node_id)] = float(score)

    def get_score(self, node_id: str, t: int = None) -> float:
        node_str = str(node_id)
        if node_str in self.override_scores:
            return self.override_scores[node_str]

        # Dynamic anomaly score check
        if node_str in self.anomaly_metrics:
            m = self.anomaly_metrics[node_str]
            x, mu, sigma = m['x'], m['mu'], m['sigma']
            if sigma > 0.0:
                anomaly = (x - mu) / sigma
            else:
                anomaly = 0.0
            score = 1.0 - anomaly
            return max(0.0, min(1.0, score))

        scenario_name = self.scenarios.get(node_str, 'normal')
        scenario = BEHAVIOR_SCENARIOS[scenario_name]
        val = float(self.rng.normal(scenario['mean'], scenario['std']))
        return max(0.0, min(1.0, val))
