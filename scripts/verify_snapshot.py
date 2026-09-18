"""Verify the original delivery's files offline, without checking current code."""

import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sys


COMPACT_OUTPUTS = {
    "adjacency.csv", "neighbour_analysis.csv", "prices_run.json",
    "sector_wealth.csv", "selected.csv", "selection_run.json",
}


def safe_path(base, relative):
    """Resolve a manifest path only within its designated directory."""
    if not isinstance(relative, str) or not relative:
        raise ValueError("Manifest file paths must be nonempty relative strings")
    portable = relative.replace("\\", "/")
    candidate = Path(portable)
    if portable.startswith("/") or PureWindowsPath(relative).drive or ".." in candidate.parts:
        raise ValueError(f"Unsafe manifest path: {relative!r}")
    base = base.resolve()
    target = (base / candidate).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"Manifest path escapes its directory: {relative!r}")
    return target


def verify_file(path, metadata, label):
    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid file metadata for {label}")
    size, digest = metadata.get("bytes"), metadata.get("sha256")
    if type(size) is not int or size < 0:
        raise ValueError(f"Invalid byte count for {label}")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise ValueError(f"Invalid SHA-256 for {label}")
    if not path.is_file():
        raise ValueError(f"Missing snapshot file: {label}")
    actual_size = path.stat().st_size
    if actual_size != size:
        raise ValueError(f"Byte count mismatch for {label}: expected {size}, found {actual_size}")
    with path.open("rb") as handle:
        actual_digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if actual_digest != digest.lower():
        raise ValueError(f"SHA-256 mismatch for {label}")


def verify_snapshot(root, include_local=False):
    """Return the number verified; raise on a missing, unsafe or changed file."""
    root = Path(root).resolve()
    output = safe_path(root, "output")
    manifest_path = safe_path(output, "run_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("outputs"), dict):
        raise ValueError("Manifest must contain an outputs object")
    outputs = manifest["outputs"]
    missing = COMPACT_OUTPUTS - outputs.keys()
    if missing:
        raise ValueError(f"Manifest is missing required outputs: {', '.join(sorted(missing))}")
    if include_local and "sectors.geojson" not in outputs:
        raise ValueError("Manifest is missing required local output: sectors.geojson")
    verified = 0
    for name, metadata in outputs.items():
        path = safe_path(output, name)
        if name == "sectors.geojson" and not include_local:
            continue
        verify_file(path, metadata, f"output/{name}")
        verified += 1
    if include_local:
        sources = manifest.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError("Manifest must contain source files for --include-local")
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError("Invalid source metadata")
            name = source.get("path")
            path = safe_path(root, name)
            verify_file(path, source, name)
            verified += 1
    return verified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository directory (defaults to this script's repository)")
    parser.add_argument("--include-local", action="store_true",
                        help="also require and verify local geometry and source downloads")
    args = parser.parse_args(argv)
    try:
        count = verify_snapshot(args.root, args.include_local)
    except (OSError, ValueError) as error:
        print(f"Snapshot verification failed: {error}", file=sys.stderr)
        return 1
    print(f"Snapshot verified: {count} files match their recorded sizes and SHA-256 hashes.")
    if not args.include_local:
        print("Local geometry and source downloads were not checked; use --include-local to verify them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
