from __future__ import annotations

import argparse
import hashlib
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

import yaml


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified(path: Path, expected: str) -> bool:
    return path.is_file() and sha256(path) == expected


def download_verified(
    url: str,
    destination: Path,
    expected: str,
    force: bool,
) -> None:
    if destination.is_file() and not force:
        actual = sha256(destination)
        if actual != expected:
            raise SystemExit(
                f"Existing artifact checksum mismatch for {destination}: "
                f"expected {expected}, got {actual}"
            )
        print(f"Artifact already verified: {destination}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f"{destination.stem}-",
        suffix=destination.suffix,
        dir=destination.parent,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        urllib.request.urlretrieve(url, temporary_path)
        actual = sha256(temporary_path)
        if actual != expected:
            raise SystemExit(
                f"Downloaded artifact checksum mismatch for {url}: "
                f"expected {expected}, got {actual}"
            )
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Artifact downloaded and verified: {destination}")


def extract_verified_member(
    archive: Path,
    member_name: str,
    destination: Path,
    expected: str,
    force: bool,
) -> None:
    if destination.is_file() and not force:
        actual = sha256(destination)
        if actual != expected:
            raise SystemExit(
                f"Existing extracted member checksum mismatch: "
                f"expected {expected}, got {actual}"
            )
        print(f"Archive member already verified: {destination}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:gz") as bundle:
        try:
            member = bundle.getmember(member_name)
        except KeyError as exc:
            raise SystemExit(
                f"Pinned member is missing from archive: {member_name}"
            ) from exc
        if not member.isfile() or member.name != member_name:
            raise SystemExit(f"Unsafe or invalid archive member: {member_name}")
        source = bundle.extractfile(member)
        if source is None:
            raise SystemExit(f"Could not read archive member: {member_name}")
        with tempfile.NamedTemporaryFile(
            prefix=f"{destination.stem}-",
            suffix=destination.suffix,
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            shutil.copyfileobj(source, temporary)
    try:
        actual = sha256(temporary_path)
        if actual != expected:
            raise SystemExit(
                f"Extracted member checksum mismatch: expected {expected}, "
                f"got {actual}"
            )
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Archive member extracted and verified: {destination}")


def repo_path(repo_root: Path, value: str) -> Path:
    result = (repo_root / value).resolve()
    result.relative_to(repo_root.resolve())
    return result


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("version") != 2:
        raise SystemExit("underlay.yaml must have version: 2")
    return config


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch pinned SNDlib Abilene topology, provenance and traffic matrix."
        )
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_config(repo_root / "emulation/config/underlay.yaml")
    topology = config["topology"]
    matrix = config["traffic_matrix"]
    readme = matrix["provenance_readme"]

    topology_path = repo_path(repo_root, topology["path"])
    download_verified(
        topology["source_url"],
        topology_path,
        topology["sha256"],
        args.force,
    )
    readme_path = repo_path(repo_root, readme["path"])
    download_verified(
        readme["source_url"],
        readme_path,
        readme["sha256"],
        args.force,
    )

    archive_path = topology_path.parent / "abilene-traffic-matrices.tgz"
    download_verified(
        matrix["archive_url"],
        archive_path,
        matrix["archive_sha256"],
        args.force,
    )
    matrix_path = repo_path(repo_root, matrix["path"])
    extract_verified_member(
        archive_path,
        matrix["archive_member"],
        matrix_path,
        matrix["sha256"],
        args.force,
    )

    print("SNDlib underlay dataset bundle is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
