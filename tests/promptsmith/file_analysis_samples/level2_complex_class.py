# レベル2テスト: 複雑なクラス構造
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import logging

class DataProcessor(ABC):
    """データ処理の基底クラス"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(self.__class__.__name__)
        self._processed_count = 0
    
    @abstractmethod
    def process(self, data: Dict) -> Dict:
        """データを処理する抽象メソッド"""
        pass
    
    def validate_data(self, data: Dict) -> bool:
        """データの妥当性を検証"""
        required_keys = ['id', 'content', 'timestamp']
        return all(key in data for key in required_keys)
    
    @property
    def processed_count(self) -> int:
        """処理済みアイテム数を取得"""
        return self._processed_count

class TextProcessor(DataProcessor):
    """テキストデータ専用プロセッサー"""
    
    def __init__(self, name: str, max_length: int = 1000):
        super().__init__(name)
        self.max_length = max_length
        self.stop_words = ['the', 'a', 'an', 'and', 'or', 'but']
    
    def process(self, data: Dict) -> Dict:
        """テキストデータを処理"""
        if not self.validate_data(data):
            raise ValueError("Invalid data format")
        
        content = data['content']
        
        # テキストのクリーニング
        cleaned_content = self._clean_text(content)
        
        # 単語数カウント
        word_count = len(cleaned_content.split())
        
        self._processed_count += 1
        self.logger.info(f"Processed text with {word_count} words")
        
        return {
            'id': data['id'],
            'processed_content': cleaned_content,
            'word_count': word_count,
            'timestamp': data['timestamp'],
            'processor': self.name
        }
    
    def _clean_text(self, text: str) -> str:
        """テキストをクリーニング（プライベートメソッド）"""
        # 基本的なクリーニング
        cleaned = text.lower().strip()
        
        # ストップワードの除去
        words = cleaned.split()
        filtered_words = [word for word in words if word not in self.stop_words]
        
        return ' '.join(filtered_words)

class BatchProcessor:
    """複数のプロセッサーを管理するバッチ処理クラス"""
    
    def __init__(self):
        self.processors: List[DataProcessor] = []
        self.results: List[Dict] = []
    
    def add_processor(self, processor: DataProcessor):
        """プロセッサーを追加"""
        self.processors.append(processor)
        logging.info(f"Added processor: {processor.name}")
    
    def process_batch(self, data_list: List[Dict]) -> List[Dict]:
        """バッチでデータを処理"""
        results = []
        
        for data in data_list:
            for processor in self.processors:
                try:
                    result = processor.process(data)
                    results.append(result)
                except Exception as e:
                    logging.error(f"Processing failed: {e}")
                    continue
        
        self.results.extend(results)
        return results
    
    def get_statistics(self) -> Dict:
        """処理統計を取得"""
        total_processed = sum(p.processed_count for p in self.processors)
        
        return {
            'total_processors': len(self.processors),
            'total_processed': total_processed,
            'total_results': len(self.results),
            'processors': [{'name': p.name, 'count': p.processed_count} 
                          for p in self.processors]
        }