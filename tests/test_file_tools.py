# tests/test_file_tools.py
"""
file_toolsモジュールのテスト
"""
import pytest
import tempfile
import os
from pathlib import Path
from codecrafter.tools.file_tools import file_tools, FileOperationError


class TestFileTools:
    """FileToolsクラスのテスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        self.test_content = "テスト内容\n日本語テスト\n"
    
    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_write_and_read_file(self):
        """ファイル書き込みと読み込みのテスト"""
        # ファイル書き込み
        result = file_tools.write_file(self.test_file, self.test_content)
        
        assert result["success"] is True
        assert result["size"] == len(self.test_content.encode('utf-8'))
        assert os.path.exists(self.test_file)
        
        # ファイル読み込み
        content = file_tools.read_file(self.test_file)
        assert content == self.test_content
    
    def test_write_file_creates_directory(self):
        """ファイル書き込み時のディレクトリ自動作成テスト"""
        nested_file = os.path.join(self.temp_dir, "subdir", "nested.txt")
        
        result = file_tools.write_file(nested_file, "nested content")
        
        assert result["success"] is True
        assert os.path.exists(nested_file)
        assert os.path.isdir(os.path.dirname(nested_file))
    
    def test_write_file_with_backup(self):
        """既存ファイルのバックアップ作成テスト"""
        # 元ファイルを作成
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("元の内容")
        
        # 新しい内容で上書き
        result = file_tools.write_file(self.test_file, "新しい内容")
        
        assert result["success"] is True
        assert result["backup_created"] is True
        assert "backup_path" in result
        
        # バックアップファイルの確認
        backup_path = result["backup_path"]
        assert os.path.exists(backup_path)
        with open(backup_path, "r", encoding="utf-8") as f:
            assert f.read() == "元の内容"
    
    def test_read_nonexistent_file(self):
        """存在しないファイルの読み込みエラーテスト"""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.txt")
        
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.read_file(nonexistent_file)
        
        assert "ファイルが見つかりません" in str(exc_info.value)
    
    def test_write_to_readonly_location(self):
        """読み取り専用ディレクトリへの書き込みエラーテスト"""
        # Windowsでは適切な権限エラーテストが困難なため、スキップまたは簡易テスト
        readonly_file = os.path.join("/", "readonly_test.txt")
        
        with pytest.raises(FileOperationError):
            file_tools.write_file(readonly_file, "content")
    
    def test_list_files_basic(self):
        """基本的なファイル一覧取得テスト"""
        # テストファイルを作成
        test_files = ["file1.txt", "file2.py", "subdir"]
        for name in test_files[:2]:
            Path(os.path.join(self.temp_dir, name)).touch()
        os.makedirs(os.path.join(self.temp_dir, "subdir"))
        
        files = file_tools.list_files(self.temp_dir)
        
        assert len(files) >= 3  # 作成したファイル + 可能性のある他のファイル
        file_names = [f["name"] for f in files]
        for name in test_files:
            assert name in file_names
    
    def test_list_files_nonexistent_directory(self):
        """存在しないディレクトリの一覧取得エラーテスト"""
        nonexistent_dir = os.path.join(self.temp_dir, "nonexistent")
        
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.list_files(nonexistent_dir)
        
        assert "ディレクトリが見つかりません" in str(exc_info.value)
    
    def test_get_file_info_file(self):
        """ファイル情報取得テスト"""
        # テストファイルを作成
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(self.test_content)
        
        info = file_tools.get_file_info(self.test_file)
        
        assert info["name"] == "test.txt"
        assert info["path"] == self.test_file
        assert info["is_file"] is True
        assert info["is_directory"] is False
        assert info["size"] == len(self.test_content.encode('utf-8'))
        assert info["extension"] == ".txt"
        assert info["parent"] == self.temp_dir
        assert "modified" in info
        assert "created" in info
    
    def test_get_file_info_directory(self):
        """ディレクトリ情報取得テスト"""
        info = file_tools.get_file_info(self.temp_dir)
        
        assert info["is_file"] is False
        assert info["is_directory"] is True
        assert info["extension"] is None
        assert info["size"] == 0  # ディレクトリのサイズは0
    
    def test_get_file_info_nonexistent(self):
        """存在しないファイル/ディレクトリの情報取得エラーテスト"""
        nonexistent = os.path.join(self.temp_dir, "nonexistent")
        
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.get_file_info(nonexistent)
        
        assert "が見つかりません" in str(exc_info.value)
    
    def test_create_directory(self):
        """ディレクトリ作成テスト"""
        new_dir = os.path.join(self.temp_dir, "new_directory")
        
        result = file_tools.create_directory(new_dir)
        
        assert result["created"] is True
        assert "message" in result
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)
    
    def test_create_nested_directory(self):
        """入れ子ディレクトリ作成テスト"""
        nested_dir = os.path.join(self.temp_dir, "level1", "level2", "level3")
        
        result = file_tools.create_directory(nested_dir)
        
        assert result["created"] is True
        assert os.path.exists(nested_dir)
        assert os.path.isdir(nested_dir)
    
    def test_create_existing_directory(self):
        """既存ディレクトリの作成テスト（エラーにならない）"""
        os.makedirs(os.path.join(self.temp_dir, "existing"))
        existing_dir = os.path.join(self.temp_dir, "existing")
        
        result = file_tools.create_directory(existing_dir)
        
        assert result["created"] is False
        assert "すでに存在" in result["message"]
    
    def test_unicode_filename_handling(self):
        """Unicodeファイル名の処理テスト"""
        unicode_file = os.path.join(self.temp_dir, "日本語ファイル名.txt")
        unicode_content = "日本語の内容です。\n"
        
        # 書き込み
        result = file_tools.write_file(unicode_file, unicode_content)
        assert result["success"] is True
        
        # 読み込み
        content = file_tools.read_file(unicode_file)
        assert content == unicode_content
        
        # ファイル情報
        info = file_tools.get_file_info(unicode_file)
        assert info["name"] == "日本語ファイル名.txt"
    
    def test_large_file_handling(self):
        """大きなファイルの処理テスト"""
        # 1MB程度のファイル
        large_content = "テスト行\n" * 100000
        
        result = file_tools.write_file(self.test_file, large_content)
        assert result["success"] is True
        
        content = file_tools.read_file(self.test_file)
        assert content == large_content
    
    def test_file_extension_detection(self):
        """ファイル拡張子検出テスト"""
        test_cases = [
            ("test.txt", ".txt"),
            ("script.py", ".py"),
            ("config.yaml", ".yaml"),
            ("no_extension", None),
            ("multiple.dots.js", ".js"),
            (".hidden", None),  # 隠しファイル
            (".gitignore", None),  # 拡張子のない隠しファイル
        ]
        
        for filename, expected_ext in test_cases:
            file_path = os.path.join(self.temp_dir, filename)
            Path(file_path).touch()
            
            info = file_tools.get_file_info(file_path)
            assert info["extension"] == expected_ext, f"Failed for {filename}"