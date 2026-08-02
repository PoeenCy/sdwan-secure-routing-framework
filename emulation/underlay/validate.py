from __future__ import annotations

import argparse
import json
from pathlib import Path

from emulation.artifacts import artifact_envelope

from .model import build_underlay_plan, load_underlay_config


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and render a deterministic underlay plan."
    )
    parser.add_argument("--profile", choices=("mini", "abilene"), default="mini")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("emulation/config/underlay.yaml"),
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = repo_root_from_module()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = repo_root / config_path
    config = load_underlay_config(repo_root, config_path)
    plan = build_underlay_plan(config, args.profile)
    payload = json.dumps(
        artifact_envelope(
            artifact_class="configuration",
            producer="emulation.underlay.validate",
            method="SNDlib capacity plus Haversine/fiber delay derivation",
            payload=plan.to_dict(),
        ),
        indent=2,
        sort_keys=True,
    )

    if args.output:
        output = args.output
        if not output.is_absolute():
            output = repo_root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
        print(f"Underlay plan written to {output}")
    else:
        print(payload)

    print(
        f"VALID: profile={plan.profile}, routers={len(plan.nodes)}, "
        f"links={len(plan.links)}, ospf_area={plan.ospf_area}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
