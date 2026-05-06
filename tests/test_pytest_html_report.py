from pathlib import Path


def test_reports_dir_can_be_created():
    # pytest-html akan membuat file report di reports/. Pastikan foldernya bisa dibuat di CI/container.
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    assert reports_dir.exists()
    assert reports_dir.is_dir()

