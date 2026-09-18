from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_repository_hygiene.py"


def run_hygiene(root: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_hygiene_accepts_clean_synthetic_tree(tmp_path):
    (tmp_path / "README.md").write_text("synthetic fixture\n")
    result = run_hygiene(tmp_path)
    assert result.returncode == 0


def test_hygiene_rejects_materials_studio_assets(tmp_path):
    for name in ("private.car", "private.mdf", "private.xsd", "pcff.off", "pcff.frc"):
        path = tmp_path / name
        path.write_text("private\n")
        result = run_hygiene(tmp_path)
        assert result.returncode == 1
        path.unlink()


def test_hygiene_rejects_native_parameter_exports(tmp_path):
    (tmp_path / "pcff_native_bendbend.csv").write_text("record_id,K0\n1,1.0\n")
    result = run_hygiene(tmp_path)
    assert result.returncode == 1
    assert "native parameter export" in result.stdout


def test_hygiene_rejects_personal_absolute_paths(tmp_path):
    (tmp_path / "notes.md").write_text("/Users/alice/private/project/file.txt\n")
    result = run_hygiene(tmp_path)
    assert result.returncode == 1
    assert "personal absolute path" in result.stdout
