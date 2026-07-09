import ast
from typing import List, Dict, Any, Optional


class CodeInspector(ast.NodeVisitor):
    def __init__(self):
        self.functions = {}
        self.assignments = []
        self.magic_numbers = []
        self.current_file = ""

    def extract_from_file(self, filepath: str) -> None:
        self.current_file = filepath
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        try:
            tree = ast.parse(code, filename=filepath)
            self.visit(tree)
        except SyntaxError:
            pass

    def visit_FunctionDef(self, node):
        self.functions[node.name] = node
        self.generic_visit(node)

    def visit_Assign(self, node):
        self.assignments.append(node)
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)) and node.value not in (0, 1):
            self.magic_numbers.append(node)
        self.generic_visit(node)

    def detect_trust_score_calculation(self) -> Optional[str]:
        for assign in self.assignments:
            if isinstance(assign.value, ast.Call):
                func = assign.value.func
                if isinstance(func, ast.Name) and func.id.lower() == "min":
                    return "MIN(I, B, C)"
            elif isinstance(assign.value, ast.BinOp) and isinstance(
                assign.value.op, ast.Add
            ):
                # Basic weighted sum check
                return "w_I*I + w_B*B + w_C*C"
        return None

    def detect_action_masking(self) -> Optional[str]:
        for assign in self.assignments:
            if isinstance(assign.value, ast.BoolOp) and isinstance(
                assign.value.op, ast.And
            ):
                return "M^zone AND M^trust AND M^struct"
        return None

    def detect_dynamic_threshold(self) -> Optional[str]:
        for assign in self.assignments:
            if isinstance(assign.value, ast.Constant) and isinstance(
                assign.value.value, float
            ):
                targets = [t.id for t in assign.targets if isinstance(t, ast.Name)]
                if any(
                    "theta" in t.lower() or "threshold" in t.lower() for t in targets
                ):
                    return str(assign.value.value)
            elif isinstance(assign.value, ast.BinOp) and isinstance(
                assign.value.op, ast.Add
            ):
                targets = [t.id for t in assign.targets if isinstance(t, ast.Name)]
                if any(
                    "theta" in t.lower() or "threshold" in t.lower() for t in targets
                ):
                    return "mu + k*sigma"
        return None

    def detect_reward_function(self) -> Optional[str]:
        for assign in self.assignments:
            targets = [t.id for t in assign.targets if isinstance(t, ast.Name)]
            if any("reward" in t.lower() or "r_t" in t.lower() for t in targets):
                # Extremely simplified detection
                return "R_t = alpha*Throughput - beta*Delay"
        return None

    def detect_delta_mspl(self) -> Optional[str]:
        for name, node in self.functions.items():
            if "mspl" in name.lower() and "delta" in name.lower():
                return "forward-looking MSPL"
        # Check assignments if no func
        for assign in self.assignments:
            targets = [t.id for t in assign.targets if isinstance(t, ast.Name)]
            if any("delta_mspl" in t.lower() for t in targets):
                if isinstance(assign.value, ast.Constant):
                    return "static value"
        return None

    def detect_basta_metrics(self) -> Optional[List[str]]:
        metrics_found = []
        for name in self.functions.keys():
            if "enice" in name.lower():
                metrics_found.append("ENICE")
            if "gcc" in name.lower():
                metrics_found.append("GCC")
            if "mpl" in name.lower():
                metrics_found.append("MPL")
            if "cd" in name.lower() and len(name) < 10:
                metrics_found.append("CD")
            if "tinr" in name.lower():
                metrics_found.append("TINR")
            if "avod" in name.lower():
                metrics_found.append("AVOD")
            if "cl" in name.lower() and len(name) < 10:
                metrics_found.append("CL")
            if "acc" in name.lower():
                metrics_found.append("ACC")
            # G metrics
            if "nsp" in name.lower():
                metrics_found.append("NSP")
            if "cmpl" in name.lower():
                metrics_found.append("CMPL")
            if "cmc" in name.lower():
                metrics_found.append("CMC")
            if "aod" in name.lower():
                metrics_found.append("AOD")
            if "mod" in name.lower() and "model" not in name.lower():
                metrics_found.append("MOD")
            if "bn" in name.lower() and len(name) < 10:
                metrics_found.append("BN")
            if "ab" in name.lower() and len(name) < 10:
                metrics_found.append("AB")
        return metrics_found if metrics_found else None

    def detect_dqn_architecture(self) -> Optional[str]:
        # Search for DQN class or Double DQN implementation
        for name in self.functions.keys():
            if "target_network" in name.lower():
                return "Double DQN"
        return "Single DQN"

    def detect_control_plane(self) -> Optional[str]:
        # Check if they only have CONNECTED/DISCONNECTED
        connected = False
        isolated = False
        suspect = False
        for assign in self.assignments:
            if isinstance(assign.value, ast.Constant) and isinstance(
                assign.value.value, str
            ):
                val = assign.value.value.upper()
                if val == "CONNECTED":
                    connected = True
                if val == "ISOLATED" or val == "DISCONNECTED":
                    isolated = True
                if val == "SUSPECT":
                    suspect = True

        if connected and suspect and isolated:
            return "{CONNECTED, SUSPECT, ISOLATED}"
        elif connected and isolated:
            return "{CONNECTED, DISCONNECTED}"
        return None

    def detect_oscillation_control(self) -> Optional[str]:
        for name in self.functions.keys():
            if "oscillation" in name.lower() or "violation" in name.lower():
                return "k_consecutive"
        return None
