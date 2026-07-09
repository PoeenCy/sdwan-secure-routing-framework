import ast
from pathlib import Path
from audit_system.models.audit import Discrepancy
from audit_system.models.deployment import PatchReport

class ASTTrustVisitor(ast.NodeVisitor):
    def __init__(self):
        self.target_line = None
        
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'min':
            args = [a.id for a in node.args if isinstance(a, ast.Name)]
            if args == ['i', 'c', 'b']:
                self.target_line = node.lineno
        self.generic_visit(node)

class ASTActionMaskVisitor(ast.NodeVisitor):
    def __init__(self):
        self.target_line = None
        
    def visit_BoolOp(self, node):
        if isinstance(node.op, ast.And):
            names = [a.id for a in node.values if isinstance(a, ast.Name)]
            if all(n in names for n in ['M_zone', 'M_trust', 'M_struct']):
                self.target_line = node.lineno
        self.generic_visit(node)

class CodePatcher:
    def __init__(self, code_dir: Path):
        self.code_dir = code_dir
        
    def patch_formula(self, discrepancy: Discrepancy) -> str:
        filepath = Path(discrepancy.file_path)
        if not filepath.exists():
            return f"Failed: File not found {filepath}"
            
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
            
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return f"Failed: Syntax error in {filepath.name}"
            
        target_line = None
        
        if discrepancy.component == "Trust Score Formula":
            visitor = ASTTrustVisitor()
            visitor.visit(tree)
            target_line = visitor.target_line
        elif discrepancy.component == "Action Masking Conditions":
            visitor = ASTActionMaskVisitor()
            visitor.visit(tree)
            target_line = visitor.target_line
            
        if target_line is not None:
            lines = code.splitlines()
            original_line = lines[target_line - 1]
            if "min(" in original_line.lower():
                # Replace everything after return/assign with new formula
                parts = original_line.split("=")
                if len(parts) > 1:
                    lines[target_line - 1] = parts[0] + "= (0.33*i + 0.33*c + 0.34*b)"
                else:
                    lines[target_line - 1] = "        return (0.33*i + 0.33*c + 0.34*b)"
            elif "and" in original_line.lower() or "&" in original_line:
                parts = original_line.split("=")
                if len(parts) > 1:
                    lines[target_line - 1] = parts[0] + "= (M_zone * M_trust * M_struct)"
                else:
                    lines[target_line - 1] = "        return (M_zone * M_trust * M_struct)"
            else:
                return f"Failed: Could not replace string in {filepath.name}"
                
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return f"AST Patched {discrepancy.component} on line {target_line} in {filepath.name}"
            
        return f"Failed: Could not find AST node for {discrepancy.component} in {filepath.name}"

class DeploymentPipeline:
    def __init__(self, code_dir: Path):
        self.code_dir = code_dir
        self.patcher = CodePatcher(code_dir)
        
    def apply_fixes(self, discrepancies: list[Discrepancy]) -> PatchReport:
        patches = []
        for disc in discrepancies:
            if disc.component in ["Trust Score Formula", "Action Masking Conditions"]:
                res = self.patcher.patch_formula(disc)
                if not res.startswith("Failed"):
                    patches.append(res)
        return PatchReport(patches=patches)
