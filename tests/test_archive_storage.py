"""
Tests for companion/modules/archive.py

ArchiveStorage persists pruned messages in JSONL and provides keyword search.
"""

import json
from datetime import date, datetime
from pathlib import Path

from companion.modules.archive import ArchiveStorage


class TestArchiveStorageInit:
    def test_creates_directory_on_init(self, tmp_path: Path) -> None:
        archive_dir = tmp_path / "archives"
        ArchiveStorage(base_dir=str(archive_dir))
        assert archive_dir.exists()

    def test_existing_directory_is_fine(self, tmp_path: Path) -> None:
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()
        ArchiveStorage(base_dir=str(archive_dir))
        assert archive_dir.exists()


class TestArchiveMessages:
    def test_archive_single_message(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        messages = [{"role": "user", "content": "hello world"}]
        storage.archive_messages(messages)

        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1

        with open(files[0], encoding="utf-8") as f:
            records = [json.loads(line) for line in f]
        assert len(records) == 1
        assert records[0]["role"] == "user"
        assert records[0]["content"] == "hello world"

    def test_archive_multiple_messages(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        messages = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "msg2"},
        ]
        storage.archive_messages(messages)

        files = list(tmp_path.glob("*.jsonl"))
        with open(files[0], encoding="utf-8") as f:
            records = [json.loads(line) for line in f]
        assert len(records) == 2

    def test_archive_empty_list_is_noop(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        storage.archive_messages([])
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 0

    def test_archive_adds_timestamp_if_missing(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        storage.archive_messages([{"role": "user", "content": "no ts"}])

        files = list(tmp_path.glob("*.jsonl"))
        with open(files[0], encoding="utf-8") as f:
            record = json.loads(f.readline())
        assert "timestamp" in record and record["timestamp"] is not None

    def test_archive_preserves_existing_timestamp(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        ts = "2025-01-15T10:30:00"
        storage.archive_messages([{"role": "user", "content": "hi", "timestamp": ts}])

        files = list(tmp_path.glob("*.jsonl"))
        with open(files[0], encoding="utf-8") as f:
            record = json.loads(f.readline())
        assert record["timestamp"] == ts

    def test_archive_appends_to_same_day_file(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        storage.archive_messages([{"role": "user", "content": "first"}])
        storage.archive_messages([{"role": "user", "content": "second"}])

        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1

        with open(files[0], encoding="utf-8") as f:
            records = [json.loads(line) for line in f]
        assert len(records) == 2

    def test_archive_handles_unicode_content(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        storage.archive_messages([{"role": "user", "content": "日本語テスト 🦆"}])

        files = list(tmp_path.glob("*.jsonl"))
        with open(files[0], encoding="utf-8") as f:
            record = json.loads(f.readline())
        assert "日本語テスト" in record["content"]


class TestSearch:
    def _setup_archive(self, tmp_path: Path) -> ArchiveStorage:
        """Create an archive with known data for search tests."""
        storage = ArchiveStorage(base_dir=str(tmp_path))

        today_str = datetime.now().strftime("%Y-%m-%d")
        file_path = tmp_path / f"{today_str}.jsonl"

        records = [
            {
                "timestamp": "2026-06-21T10:00:00",
                "role": "user",
                "content": "fix the login bug",
            },
            {
                "timestamp": "2026-06-21T10:01:00",
                "role": "assistant",
                "content": "I found the login issue",
            },
            {
                "timestamp": "2026-06-21T10:02:00",
                "role": "user",
                "content": "deploy to production",
            },
        ]
        with open(file_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        return storage

    def test_search_single_keyword(self, tmp_path: Path) -> None:
        storage = self._setup_archive(tmp_path)
        results = storage.search("login")
        assert len(results) == 2

    def test_search_and_keyword(self, tmp_path: Path) -> None:
        storage = self._setup_archive(tmp_path)
        results = storage.search("login bug")
        assert len(results) == 1
        assert "bug" in results[0]["content"]

    def test_search_case_insensitive(self, tmp_path: Path) -> None:
        storage = self._setup_archive(tmp_path)
        results = storage.search("LOGIN")
        assert len(results) == 2

    def test_search_no_results(self, tmp_path: Path) -> None:
        storage = self._setup_archive(tmp_path)
        results = storage.search("nonexistent_keyword_xyz")
        assert len(results) == 0

    def test_search_respects_limit(self, tmp_path: Path) -> None:
        storage = self._setup_archive(tmp_path)
        results = storage.search("login", limit=1)
        assert len(results) == 1

    def test_search_empty_directory(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        results = storage.search("anything")
        assert results == []

    def test_search_with_date_range(self, tmp_path: Path) -> None:
        storage = self._setup_archive(tmp_path)
        today = date.today()
        results = storage.search("login", date_range=(today, today))
        assert len(results) >= 1

    def test_search_with_out_of_range_date(self, tmp_path: Path) -> None:
        storage = self._setup_archive(tmp_path)
        old_date = date(2020, 1, 1)
        results = storage.search("login", date_range=(old_date, old_date))
        assert len(results) == 0

    def test_search_ignores_non_jsonl_files(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        (tmp_path / "readme.txt").write_text("not a jsonl file")
        results = storage.search("anything")
        assert results == []

    def test_search_skips_malformed_lines(self, tmp_path: Path) -> None:
        storage = ArchiveStorage(base_dir=str(tmp_path))
        today_str = datetime.now().strftime("%Y-%m-%d")
        file_path = tmp_path / f"{today_str}.jsonl"
        with open(file_path, "w") as f:
            f.write("not valid json\n")
            f.write(json.dumps({"content": "valid record", "role": "user"}) + "\n")
        results = storage.search("valid")
        assert len(results) == 1
