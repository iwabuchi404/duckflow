"""
Tests for companion/security/file_protector.py

FileProtector enforces workspace-boundary and extension-based safety rules.
"""

from pathlib import Path

import pytest

from companion.security.file_protector import FileProtector


class TestIsInsideWorkdir:
    """Verify workspace boundary checks."""

    def _make(self, work_dir: str) -> FileProtector:
        return FileProtector(work_dir=work_dir, safe_extensions=[".py", ".txt"])

    def test_file_inside_workdir_returns_true(self, tmp_path: Path) -> None:
        fp = self._make(str(tmp_path))
        assert fp.is_inside_workdir(str(tmp_path / "sub" / "file.py"))

    def test_file_at_workdir_root_returns_true(self, tmp_path: Path) -> None:
        fp = self._make(str(tmp_path))
        assert fp.is_inside_workdir(str(tmp_path / "file.py"))

    def test_file_outside_workdir_returns_false(self, tmp_path: Path) -> None:
        fp = self._make(str(tmp_path / "project"))
        assert not fp.is_inside_workdir("/etc/passwd")

    def test_parent_escape_returns_false(self, tmp_path: Path) -> None:
        fp = self._make(str(tmp_path / "project"))
        assert not fp.is_inside_workdir(str(tmp_path / "project" / ".." / "secret.txt"))

    def test_symlink_resolved(self, tmp_path: Path) -> None:
        """Symlinks are resolved before comparison."""
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link = tmp_path / "link"
        try:
            link.symlink_to(real_dir, target_is_directory=True)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                pytest.skip("Symlink creation requires Windows privileges")
            raise
        fp = self._make(str(real_dir))
        assert fp.is_inside_workdir(str(link / "file.py"))


class TestIsSafeExtension:
    """Verify extension safety checks."""

    def _make(self) -> FileProtector:
        return FileProtector(work_dir="/tmp", safe_extensions=[".py", ".txt", ".md"])

    def test_safe_extension_returns_true(self) -> None:
        fp = self._make()
        assert fp.is_safe_extension("module.py")

    def test_dangerous_exe_returns_false(self) -> None:
        fp = self._make()
        assert not fp.is_safe_extension("virus.exe")

    def test_dangerous_bat_returns_false(self) -> None:
        fp = self._make()
        assert not fp.is_safe_extension("script.bat")

    def test_dangerous_sh_returns_false(self) -> None:
        fp = self._make()
        assert not fp.is_safe_extension("run.sh")

    def test_dangerous_ps1_returns_false(self) -> None:
        fp = self._make()
        assert not fp.is_safe_extension("deploy.ps1")

    def test_unlisted_extension_returns_false(self) -> None:
        fp = self._make()
        assert not fp.is_safe_extension("archive.zip")

    def test_case_insensitive_dangerous_check(self) -> None:
        fp = self._make()
        assert not fp.is_safe_extension("VIRUS.EXE")

    def test_no_extension_returns_false(self) -> None:
        fp = self._make()
        assert not fp.is_safe_extension("Makefile")


class TestCheckOperation:
    """Verify operation-level access control."""

    def _make(self, tmp_path: Path) -> FileProtector:
        return FileProtector(work_dir=str(tmp_path), safe_extensions=[".py", ".txt"])

    def test_read_always_allowed_outside_workdir(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation("read", "/etc/hosts")

    def test_list_always_allowed(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation("list", "/usr/bin")

    def test_write_inside_workdir_safe_ext_allowed(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation("write", str(tmp_path / "hello.py"))

    def test_write_outside_workdir_blocked(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert not fp.check_operation("write", "/etc/passwd")

    def test_write_dangerous_ext_blocked(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert not fp.check_operation("write", str(tmp_path / "evil.exe"))

    def test_delete_inside_workdir_safe_ext_allowed(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation("delete", str(tmp_path / "old.txt"))

    def test_delete_outside_workdir_blocked(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert not fp.check_operation("delete", "/tmp/other/file.py")

    def test_create_inside_workdir_safe_ext_allowed(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation("create", str(tmp_path / "new.py"))

    def test_mkdir_inside_workdir_allowed(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation("mkdir", str(tmp_path / "subdir"))

    def test_mkdir_outside_workdir_blocked(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert not fp.check_operation("mkdir", "/opt/hacked")

    def test_move_inside_workdir_allowed(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation("move", str(tmp_path / "a.py"))

    def test_copy_inside_workdir_allowed(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation("copy", str(tmp_path / "b.txt"))

    def test_unknown_operation_allowed(self, tmp_path: Path) -> None:
        """Unknown operations fall through to the default allow."""
        fp = self._make(tmp_path)
        assert fp.check_operation("foobar", "/anywhere")

    def test_none_operation_allowed(self, tmp_path: Path) -> None:
        fp = self._make(tmp_path)
        assert fp.check_operation(None, "/anywhere")
