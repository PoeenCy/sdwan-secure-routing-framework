from src.models.graph_c import GraphC
from src.microseg.bridge_cg import CGBridge
from .reward import RewardCalculator

class HeuristicAgent:
    def __init__(self, reward_calculator: RewardCalculator = None):
        self.reward_calculator = reward_calculator if reward_calculator is not None else RewardCalculator()

    def select_path(self, s: str, d: str, P_f: list, C: GraphC, bridge: CGBridge) -> tuple:
        """
        Selects the best path p* in P_f that maximizes R_t(p).
        Returns a tuple of (best_path, best_reward).
        """
        if not P_f:
            return None, -1e9

        best_path = None
        best_reward = -1e9

        for path in P_f:
            reward = self.reward_calculator.calculate_path_reward(path, C, bridge)
            if reward > best_reward:
                best_reward = reward
                best_path = path

        return best_path, best_reward
