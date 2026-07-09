POSTURE_SCENARIOS = {
    'fully_compliant': {
        'cert_valid': True,
        'patch_ok': True,
        'edr_running': True,
        'encryption_on': True,
    },
    'partially_compliant': {
        'cert_valid': True,
        'patch_ok': False,
        'edr_running': True,
        'encryption_on': True,
    },
    'compromised': {
        'cert_valid': False,
        'patch_ok': False,
        'edr_running': False,
        'encryption_on': True,
    },
}


POSTURE_KEYS = ['cert_valid', 'patch_ok', 'edr_running', 'encryption_on']


class IdentityProvider:
    def __init__(self):
        self.identity_scores = {}
        # Node conditions: {node_id: [cert_valid, patch_ok, edr_running, encryption_on]}
        # Default conditions: all True (1.0 ratio)
        self.conditions = {}

    def set_conditions(self, node_id: str, cert_valid: bool, patch_ok: bool, edr_running: bool, encryption_on: bool):
        self.conditions[str(node_id)] = [cert_valid, patch_ok, edr_running, encryption_on]

    def set_scenario(self, node_id: str, scenario: str):
        if scenario not in POSTURE_SCENARIOS:
            raise ValueError(f"Unknown posture scenario: {scenario}")
        posture = POSTURE_SCENARIOS[scenario]
        self.conditions[str(node_id)] = [bool(posture[key]) for key in POSTURE_KEYS]

    def get_score(self, node_id: str, strict: bool = False) -> float:
        node_str = str(node_id)
        # Direct override score takes precedence (for tests or manual overrides)
        if node_str in self.identity_scores:
            return self.identity_scores[node_str]
        
        # Posture score calculation: ratio of met conditions (or AND if strict)
        if node_str in self.conditions:
            conds = self.conditions[node_str]
            if strict:
                return 1.0 if all(conds) else 0.0
            return sum(1.0 if c else 0.0 for c in conds) / len(conds)
        
        return 1.0

    def set_score(self, node_id: str, score: float):
        self.identity_scores[str(node_id)] = float(score)
