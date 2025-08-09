# FileAnalyzer プロジェクト

ファイル内容を分析してコードの品質を評価するツールです。

## 概要

FileAnalyzerは、様々な形式のファイルを読み取り、以下の分析を行います：

- **構文解析**: コードの構造と文法チェック
- **品質評価**: コーディング規約の遵守状況
- **セキュリティチェック**: 潜在的な脆弱性の検出

## インストール

```bash
pip install file-analyzer
```

## 使用方法

### 基本的な使用方法

```python
from file_analyzer import analyze_file

result = analyze_file("example.py")
print(result.summary)
```

### コマンドライン

```bash
file-analyzer scan /path/to/project
```

## サポート対象

- Python (.py)
- JavaScript (.js, .ts)
- JSON (.json)
- YAML (.yaml, .yml)

## ライセンス

MIT License