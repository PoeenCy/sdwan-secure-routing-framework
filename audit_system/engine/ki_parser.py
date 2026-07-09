import re
from pathlib import Path
from typing import Dict, Tuple, Optional


class KIFileParser:
    def __init__(self):
        # Map: component_name -> (formula_string, ki_reference, section)
        self.formulas: Dict[str, Tuple[str, str, str]] = {}

    def parse_directory(self, directory_path: Path) -> None:
        if not directory_path.exists():
            raise FileNotFoundError(f"Directory {directory_path} not found")
        for file_path in directory_path.glob("KI_*.md"):
            self.parse_file(file_path)

    def parse_file(self, file_path: Path) -> None:
        content = file_path.read_text(encoding="utf-8")
        ki_name = file_path.stem

        current_section = "General"
        # Look for headers containing §
        section_pattern = re.compile(r"§([\d\.]+)")

        lines = content.split("\n")

        for line in lines:
            line_stripped = line.strip()

            # Check for section header
            if line_stripped.startswith("#"):
                sec_match = section_pattern.search(line_stripped)
                if sec_match:
                    current_section = f"§{sec_match.group(1)}"

            # Basic formula extraction heuristics
            # 1. Trust Score
            if (
                "T(v)" in line_stripped
                and "=" in line_stripped
                and ("w_I" in line_stripped or "w_B" in line_stripped)
            ):
                self._add_formula(
                    "Trust Score", line_stripped, ki_name, current_section
                )

            # 2. Action Masking
            if (
                "M_t" in line_stripped
                and "=" in line_stripped
                and ("M^zone" in line_stripped or "trust" in line_stripped)
            ):
                self._add_formula(
                    "Action Masking", line_stripped, ki_name, current_section
                )

            # 3. Dynamic Threshold
            if (
                (
                    "θ(t)" in line_stripped
                    or "\\theta(t)" in line_stripped
                    or "theta(t)" in line_stripped
                )
                and "=" in line_stripped
                and (
                    "mu" in line_stripped
                    or "μ" in line_stripped
                    or "\\mu" in line_stripped
                )
            ):
                self._add_formula(
                    "Dynamic Threshold", line_stripped, ki_name, current_section
                )

            # 4. Reward Function
            if (
                "R_t" in line_stripped
                and "=" in line_stripped
                and (
                    "Throughput" in line_stripped
                    or "Delay" in line_stripped
                    or "Penalty" in line_stripped
                )
            ):
                self._add_formula(
                    "Reward Function", line_stripped, ki_name, current_section
                )

    def _add_formula(
        self, component: str, formula: str, ki_name: str, section: str
    ) -> None:
        # Clean up markdown formatting like backticks or math delimiters
        clean_formula = re.sub(r"^\$+|\$+$|^`+|`+$", "", formula).strip()
        self.formulas[component] = (clean_formula, ki_name, section)

    def get_formula(self, component: str) -> Optional[Tuple[str, str, str]]:
        return self.formulas.get(component)
