# プロンプトコンパイラ追加メソッド

def _combine_contexts(
    self, 
    rag_results: Optional[List[Dict[str, Any]]] = None,
    file_context: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """コンテキスト情報を結合"""
    context_parts = []
    total_files = 0
    languages = {}
    
    # RAGコンテキストを追加
    if rag_results and len(rag_results) > 0:
        rag_context = self._format_rag_context(rag_results)
        if rag_context != "関連コードなし":
            context_parts.append(f"**RAG検索結果:**\n{rag_context}")
        
        unique_files = set(result.get("file_path", "") for result in rag_results)
        total_files += len(unique_files)
        
        for result in rag_results:
            lang = result.get("language", "unknown")
            languages[lang] = languages.get(lang, 0) + 1
    
    # ファイルコンテキストを追加
    if file_context:
        file_context_str = self._format_file_context(file_context)
        if file_context_str:
            context_parts.append(f"**ファイル情報:**\n{file_context_str}")
        
        if file_context.get('files_list'):
            total_files += len(file_context['files_list'])
    
    return {
        "code_context": "\n\n".join(context_parts) if context_parts else "関連するコードコンテキストは見つかりませんでした",
        "index_status": "利用可能" if (rag_results or file_context) else "未インデックス",
        "total_files": str(total_files),
        "primary_languages": self._format_languages(languages)
    }

def _format_file_context(self, file_context: Dict[str, Any]) -> str:
    """ファイルコンテキストをフォーマット"""
    context_parts = []
    
    # ファイル一覧
    if file_context.get('files_list'):
        files_list = file_context['files_list']
        context_parts.append(f"ファイル一覧 ({len(files_list)}件):")
        for file_info in files_list[:10]:
            name = file_info.get('name', '不明')
            size = file_info.get('size', 0)
            context_parts.append(f"  - {name} ({size} bytes)")
        
        if len(files_list) > 10:
            context_parts.append(f"  ... 他{len(files_list) - 10}件")
    
    # ファイル内容
    if file_context.get('file_contents'):
        file_contents = file_context['file_contents']
        context_parts.append(f"\nファイル内容 ({len(file_contents)}件):")
        for file_path, content in file_contents.items():
            preview = content[:300] + "..." if len(content) > 300 else content
            context_parts.append(f"\n[{file_path}]:\n{preview}")
    
    return "\n".join(context_parts)

def _format_languages(self, languages: Dict[str, int]) -> str:
    """言語統計をフォーマット"""
    if not languages:
        return "不明"
    
    sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
    return ", ".join([f"{lang} ({count})" for lang, count in sorted_langs[:3]])