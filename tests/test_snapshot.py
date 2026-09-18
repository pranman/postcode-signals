import hashlib
import json

import pytest

from scripts import verify_snapshot as snapshot


@pytest.fixture
def delivery(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    outputs = {}
    for name in sorted(snapshot.COMPACT_OUTPUTS | {"sectors.geojson"}):
        content = f"sample {name}\n".encode()
        (output / name).write_bytes(content)
        outputs[name] = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    (tmp_path / "data").mkdir()
    content = b"source data\n"
    (tmp_path / "data" / "source.csv").write_bytes(content)
    manifest = {
        "outputs": outputs,
        "sources": [{"path": "data/source.csv", "bytes": len(content),
                     "sha256": hashlib.sha256(content).hexdigest()}],
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path, manifest


def save_manifest(root, manifest):
    (root / "output" / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_default_requires_compact_files_but_not_local_inputs(delivery):
    root, _ = delivery
    (root / "output" / "sectors.geojson").unlink()
    (root / "data" / "source.csv").unlink()
    assert snapshot.verify_snapshot(root) == 6


def test_include_local_verifies_all_recorded_files(delivery):
    root, _ = delivery
    assert snapshot.verify_snapshot(root, include_local=True) == 8
    (root / "data" / "source.csv").write_bytes(b"SOURCE data\n")
    with pytest.raises(ValueError, match="SHA-256 mismatch for data/source.csv"):
        snapshot.verify_snapshot(root, include_local=True)


@pytest.mark.parametrize("mutation,message", [
    ("longer", "Byte count mismatch"),
    ("same-size", "SHA-256 mismatch"),
    ("missing", "Missing snapshot file"),
    ("manifest-entry", "missing required outputs"),
    ("digest", "SHA-256 mismatch"),
])
def test_corruption_or_absence_fails(delivery, mutation, message):
    root, manifest = delivery
    path = root / "output" / "selected.csv"
    if mutation == "longer":
        path.write_bytes(path.read_bytes() + b"extra")
    elif mutation == "same-size":
        path.write_bytes(path.read_bytes().upper())
    elif mutation == "missing":
        path.unlink()
    elif mutation == "manifest-entry":
        del manifest["outputs"]["selected.csv"]
    else:
        manifest["outputs"]["selected.csv"]["sha256"] = "0" * 64
    save_manifest(root, manifest)
    with pytest.raises(ValueError, match=message):
        snapshot.verify_snapshot(root)


@pytest.mark.parametrize("name", ["../outside.csv", "..\\outside.csv", "/outside.csv", "C:\\outside.csv"])
def test_output_paths_cannot_escape_output_directory(delivery, name):
    root, manifest = delivery
    manifest["outputs"][name] = manifest["outputs"]["selected.csv"]
    save_manifest(root, manifest)
    with pytest.raises(ValueError, match="Unsafe manifest path"):
        snapshot.verify_snapshot(root)


def test_source_paths_cannot_escape_repository(delivery):
    root, manifest = delivery
    manifest["sources"][0]["path"] = "../outside.csv"
    save_manifest(root, manifest)
    with pytest.raises(ValueError, match="Unsafe manifest path"):
        snapshot.verify_snapshot(root, include_local=True)


@pytest.mark.parametrize("name", ["output/sectors.geojson", "data/source.csv"])
def test_include_local_requires_each_local_file(delivery, name):
    root, _ = delivery
    (root / name).unlink()
    with pytest.raises(ValueError, match="Missing snapshot file"):
        snapshot.verify_snapshot(root, include_local=True)


def test_cli_reports_success_and_nonzero_failure(delivery, capsys):
    root, _ = delivery
    assert snapshot.main(["--root", str(root)]) == 0
    assert "Snapshot verified: 6 files" in capsys.readouterr().out
    (root / "output" / "selected.csv").unlink()
    assert snapshot.main(["--root", str(root)]) == 1
    assert "Missing snapshot file: output/selected.csv" in capsys.readouterr().err
