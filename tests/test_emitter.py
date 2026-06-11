"""FileEmitter: hardlink, copy mode, existing-destination skip, no .part residue."""

import os

from feed_simulator.core.emitter import FileEmitter


def _seed_file(tmp_path, name="seed.bin", content=b"data"):
    seed = tmp_path / "seed" / name
    seed.parent.mkdir(exist_ok=True)
    seed.write_bytes(content)
    return seed


def test_hardlink_shares_inode(tmp_path):
    seed = _seed_file(tmp_path)
    dst = tmp_path / "out" / "emitted.bin"
    assert FileEmitter("hardlink").emit_file(seed, dst) is True
    assert os.stat(seed).st_ino == os.stat(dst).st_ino


def test_copy_mode_independent_inode(tmp_path):
    seed = _seed_file(tmp_path)
    dst = tmp_path / "out" / "emitted.bin"
    assert FileEmitter("copy").emit_file(seed, dst) is True
    assert dst.read_bytes() == b"data"
    assert os.stat(seed).st_ino != os.stat(dst).st_ino


def test_existing_destination_skipped(tmp_path):
    seed = _seed_file(tmp_path)
    dst = tmp_path / "out" / "emitted.bin"
    emitter = FileEmitter("hardlink")
    assert emitter.emit_file(seed, dst) is True
    assert emitter.emit_file(seed, dst) is False


def test_copy_leaves_no_part_file(tmp_path):
    seed = _seed_file(tmp_path)
    dst = tmp_path / "out" / "emitted.bin"
    FileEmitter("copy").emit_file(seed, dst)
    assert [p.name for p in dst.parent.iterdir()] == ["emitted.bin"]
