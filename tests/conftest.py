import pytest

from customstaller.cli import main


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """A freshly initialised project with a LICENSE and a small payload."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "LICENSE").write_text("Example license text\n")
    (tmp_path / "payload").mkdir()
    (tmp_path / "payload" / "app.txt").write_text("hello")
    (tmp_path / "payload" / "bin").mkdir()
    (tmp_path / "payload" / "bin" / "tool.txt").write_text("tool")
    assert main(["init", "--yes", "--name", "Test App", "--theme", "ocean"]) == 0
    return tmp_path
