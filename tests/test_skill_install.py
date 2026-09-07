from __future__ import annotations

import json
from pathlib import Path

import pytest

from blendsmith.cli import _json_file, main
from blendsmith.errors import ContractError
from blendsmith.skill_install import (
    bundled_skill_bytes,
    bundled_skill_sha256,
    bundled_skill_version,
    codex_skill_path,
    install_codex_skill,
    skill_status,
)


def test_bundled_skill_is_thin_codex_adapter() -> None:
    text = bundled_skill_bytes().decode("utf-8")
    assert "name: blendsmith" in text
    assert 'version: "0.0.2"' in text
    assert "BlendSmithを使って" in text
    assert "CLI/Core is the source of truth" in text
    assert "AI_ACCEPTED != HUMAN_ACCEPTED" in text
    assert "blendsmith schema <contract>" in text
    assert "blendsmith doctor" in text
    assert bundled_skill_version() == "0.0.2"


def test_skill_install_create_status_and_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    expected = codex_skill_path()

    before = skill_status()
    assert before["status"] == "NOT_INSTALLED"
    assert Path(before["path"]) == expected

    installed = install_codex_skill()
    assert installed["status"] == "INSTALLED"
    assert installed["restart_required"] is True
    assert expected.is_file()
    assert installed["sha256"] == bundled_skill_sha256()

    current = skill_status()
    assert current["status"] == "CURRENT"
    assert current["installed_sha256"] == current["bundled_sha256"]

    unchanged = install_codex_skill()
    assert unchanged["status"] == "UNCHANGED"
    assert unchanged["restart_required"] is False


def test_skill_install_refuses_bundle_version_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr(
        "blendsmith.skill_install.bundled_skill_bytes",
        lambda: b'---\nname: blendsmith\nmetadata:\n  version: "9.9.9"\n---\n',
    )
    with pytest.raises(ContractError, match="does not match CLI/Core version"):
        install_codex_skill()


def test_skill_install_refuses_modified_target_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    install_codex_skill()
    destination = codex_skill_path()
    destination.write_text("modified locally", encoding="utf-8")

    with pytest.raises(ContractError, match="--force"):
        install_codex_skill()

    forced = install_codex_skill(force=True)
    assert forced["status"] == "INSTALLED_OR_UPDATED"
    assert destination.read_bytes() == bundled_skill_bytes()


def test_skill_install_refuses_symlink_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    destination = codex_skill_path()
    destination.parent.mkdir(parents=True)
    real = tmp_path / "real-skill.md"
    real.write_text("external", encoding="utf-8")
    try:
        destination.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable in this test environment")

    with pytest.raises(ContractError, match="unsafe"):
        install_codex_skill(force=True)


def test_cli_json_input_accepts_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "bom.json"
    path.write_bytes(b'\xef\xbb\xbf{"schema_version": 1}')
    assert _json_file(str(path)) == {"schema_version": 1}


def test_cli_schema_uses_authoritative_contract(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema", "method_plan"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["$id"].endswith("method_plan.schema.json")
    assert "work_units" in payload["properties"]


def test_skill_install_refuses_symlink_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path / "codex-home"
    real_skills = tmp_path / "real-skills"
    real_skills.mkdir()
    codex_home.mkdir()
    try:
        (codex_home / "skills").symlink_to(real_skills, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are unavailable in this test environment")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert skill_status()["status"] == "UNSAFE_TARGET"
    with pytest.raises(ContractError, match="unsafe"):
        install_codex_skill(force=True)


def test_cli_doctor_requires_current_skill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    assert main(["doctor"]) == 2
    missing = json.loads(capsys.readouterr().out)
    assert missing["ready"] is False
    assert missing["skill"]["status"] == "NOT_INSTALLED"

    install_codex_skill()
    assert main(["doctor"]) == 0
    current = json.loads(capsys.readouterr().out)
    assert current["ready"] is True
    assert current["skill"]["status"] == "CURRENT"


def test_cli_skill_install_and_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    assert main(["skill-install"]) == 0
    installed = json.loads(capsys.readouterr().out)
    assert installed["status"] == "INSTALLED"

    assert main(["skill-status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "CURRENT"
