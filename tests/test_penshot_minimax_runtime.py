from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_penshot_minimax_runtime.py"
SPEC = importlib.util.spec_from_file_location("penshot_runtime_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_reads_only_allowlisted_minimax_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MINIMAX_API_KEY='secret-value'\n"
        "MINIMAX_API_BASE=https://api.minimaxi.com/\n"
        "UNRELATED_SECRET=must-not-load\n",
        encoding="utf-8",
    )

    values = MODULE.read_allowed_env(env_file)

    assert values == {
        "MINIMAX_API_KEY": "secret-value",
        "MINIMAX_API_BASE": "https://api.minimaxi.com/",
    }


def test_builds_openai_compatible_v1_base() -> None:
    assert (
        MODULE.minimax_openai_base("https://api.minimaxi.com")
        == "https://api.minimaxi.com/v1"
    )
    assert (
        MODULE.minimax_openai_base("https://api.minimaxi.com/v1/")
        == "https://api.minimaxi.com/v1"
    )


def test_redacts_credentials_and_bounds_error_text() -> None:
    result = MODULE.redact("prefix api-secret suffix" + "x" * 3000, ["api-secret"])

    assert "api-secret" not in result
    assert "***REDACTED***" in result
    assert len(result) == 2000


def test_isolated_work_dir_is_deep_below_output(tmp_path: Path) -> None:
    output = tmp_path / "verification" / "summary.json"

    work_dir = MODULE.isolated_work_dir(output)

    assert work_dir.is_dir()
    assert work_dir.parent.name == "level_1"
    assert not any((parent / ".env").exists() for parent in list(work_dir.parents)[:2])


def test_workflow_mode_requires_explicit_model_call_acknowledgement(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mode",
            "rule-workflow",
            "--env-file",
            str(tmp_path / ".env"),
            "--output",
            str(tmp_path / "summary.json"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert "PenShot ignores enable_llm=False" in result.stderr
    assert not (tmp_path / "summary.json").exists()
