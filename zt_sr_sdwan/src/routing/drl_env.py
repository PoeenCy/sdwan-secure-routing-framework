import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    # Fallback to older gym if gymnasium is not available
    try:
        import gym
        from gym import spaces
    except ImportError:
        # Dummy classes to prevent syntax errors if gym is totally missing
        class GymMock:
            class Env: pass
        gym = GymMock()
        class SpacesMock:
            @staticmethod
            def Discrete(x): return None
            @staticmethod
            def Box(low, high, shape, dtype): return None
        spaces = SpacesMock()

import networkx as nx
from src.routing.reward import compute_reward, load_reward_hyperparams

class ZTEnv(gym.Env):
    """
    Zero Trust SD-WAN Routing Environment for Reinforcement Learning.
    State: current_node
    Action: next_node
    """
    def __init__(self, C: nx.DiGraph, pdp, source: str, target: str, E_f: set = None,
                 graph_g: nx.DiGraph = None, hyperparams: dict = None):
        super(ZTEnv, self).__init__()
        self.C = C
        self.G = graph_g
        self.pdp = pdp
        self.source = str(source)
        self.target = str(target)
        self.E_f = E_f
        self.hyperparams = load_reward_hyperparams()
        if hyperparams:
            self.hyperparams.update(hyperparams)
        
        # Map node strings to integers for gym actions
        self.nodes = list(C.nodes())
        self.node_to_idx = {n: i for i, n in enumerate(self.nodes)}
        self.idx_to_node = {i: n for i, n in enumerate(self.nodes)}
        self.n_nodes = len(self.nodes)
        
        self.action_space = spaces.Discrete(self.n_nodes)
        
        # Observation space could be the current node index
        # For a full DQN/PPO, it should ideally be a vector, but discrete is fine for tabular/simple PPO
        self.observation_space = spaces.Discrete(self.n_nodes)
        
        self.current_node = self.source
        self.visited = set()
        self.path = []
        self.max_steps = self.n_nodes
        self.steps = 0

    def reset(self, seed=None, options=None):
        self.current_node = self.source
        self.visited = {self.source}
        self.path = [self.source]
        self.steps = 0
        return self.node_to_idx[self.source], {}

    def _get_valid_actions(self):
        valid = []
        for next_node in self.C.successors(self.current_node):
            edge = (self.current_node, next_node)
            if next_node not in self.visited and (self.E_f is None or edge in self.E_f):
                valid.append(self.node_to_idx[next_node])
        return valid

    def step(self, action):
        if action is None:
            return self.node_to_idx[self.current_node], -10.0, False, True, {}

        next_node = self.idx_to_node[action]
        self.steps += 1
        
        reward = 0.0
        terminated = False
        truncated = False
        info = {}

        # Invalid move: Not an edge, or already visited, or masked out by E_f
        edge = (self.current_node, next_node)
        if not self.C.has_edge(*edge) or next_node in self.visited or (self.E_f is not None and edge not in self.E_f):
            reward = -10.0
            truncated = True  # End episode early for bad moves
            return self.node_to_idx[self.current_node], reward, terminated, truncated, info

        # Valid move
        self.path.append(next_node)
        self.visited.add(next_node)
        
        zone = self.C.nodes[next_node].get('zone', 'Unknown')
        trust = self.pdp.get_trust_score(next_node, zone, self.C)
        info['trust'] = trust
        
        step_reward = compute_reward(
            self.current_node,
            next_node,
            self.C,
            self.G,
            self.path[:-1],
            self.hyperparams,
        )
        
        reward += step_reward

        self.current_node = next_node

        if self.current_node == self.target:
            reward += 100.0  # Big bonus for reaching target
            terminated = True
        elif self.steps >= self.max_steps:
            truncated = True

        return self.node_to_idx[self.current_node], reward, terminated, truncated, info
