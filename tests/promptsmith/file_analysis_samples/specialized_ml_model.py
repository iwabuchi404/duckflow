# 専門領域テスト: 機械学習モデル（TensorFlow）
import tensorflow as tf
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

class ImageClassifierCNN:
    """
    画像分類用の畳み込みニューラルネットワーク
    分析上の課題: モデル設計の妥当性、ハイパーパラメータ調整、最適化手法
    """
    
    def __init__(self, input_shape=(224, 224, 3), num_classes=10):
        self.input_shape = input_shape
        self.num_classes = num_classes
        self.model = None
        self.history = None
        
    def build_model(self):
        """モデル構築 - アーキテクチャ設計の分析ポイント"""
        
        model = tf.keras.Sequential([
            # 入力層
            tf.keras.layers.Input(shape=self.input_shape),
            
            # 第1畳み込みブロック
            tf.keras.layers.Conv2D(32, (3, 3), activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(0.25),
            
            # 第2畳み込みブロック  
            tf.keras.layers.Conv2D(64, (3, 3), activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(0.25),
            
            # 第3畳み込みブロック
            tf.keras.layers.Conv2D(128, (3, 3), activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(0.25),
            
            # 全結合層
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.5),
            
            # 出力層
            tf.keras.layers.Dense(self.num_classes, activation='softmax')
        ])
        
        # コンパイル設定 - 最適化戦略の分析ポイント
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy', 'top_5_accuracy']
        )
        
        self.model = model
        return model
    
    def prepare_data(self, X, y, test_size=0.2, validation_size=0.1):
        """
        データ前処理 - データ処理方法の分析ポイント
        問題: データ拡張、正規化、クラス不均衡への対応
        """
        
        # データ分割
        X_train, X_temp, y_train, y_temp = train_test_split(
            X, y, test_size=test_size + validation_size, random_state=42
        )
        
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, 
            test_size=test_size/(test_size + validation_size),
            random_state=42
        )
        
        # 正規化 (0-255 -> 0-1)
        X_train = X_train.astype('float32') / 255.0
        X_val = X_val.astype('float32') / 255.0
        X_test = X_test.astype('float32') / 255.0
        
        # ワンホットエンコーディング
        y_train = tf.keras.utils.to_categorical(y_train, self.num_classes)
        y_val = tf.keras.utils.to_categorical(y_val, self.num_classes)
        y_test = tf.keras.utils.to_categorical(y_test, self.num_classes)
        
        return (X_train, X_val, X_test), (y_train, y_val, y_test)
    
    def train(self, X_train, y_train, X_val, y_val, epochs=100, batch_size=32):
        """
        モデル訓練 - 学習戦略の分析ポイント
        課題: 過学習対策、学習率調整、早期停止
        """
        
        if self.model is None:
            self.build_model()
        
        # コールバック設定
        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-7
            ),
            tf.keras.callbacks.ModelCheckpoint(
                'best_model.h5',
                monitor='val_accuracy',
                save_best_only=True,
                save_weights_only=False
            )
        ]
        
        # データ拡張
        datagen = tf.keras.preprocessing.image.ImageDataGenerator(
            rotation_range=20,
            width_shift_range=0.2,
            height_shift_range=0.2,
            horizontal_flip=True,
            zoom_range=0.2,
            shear_range=0.2,
            fill_mode='nearest'
        )
        
        # 学習実行
        self.history = self.model.fit(
            datagen.flow(X_train, y_train, batch_size=batch_size),
            steps_per_epoch=len(X_train) // batch_size,
            epochs=epochs,
            validation_data=(X_val, y_val),
            callbacks=callbacks,
            verbose=1
        )
        
        return self.history
    
    def evaluate_model(self, X_test, y_test):
        """
        モデル評価 - 評価指標の妥当性分析ポイント
        """
        if self.model is None:
            raise ValueError("Model must be trained before evaluation")
        
        # 基本評価
        test_loss, test_accuracy, test_top5 = self.model.evaluate(
            X_test, y_test, verbose=0
        )
        
        # 予測結果
        y_pred = self.model.predict(X_test)
        y_pred_classes = np.argmax(y_pred, axis=1)
        y_true_classes = np.argmax(y_test, axis=1)
        
        # 詳細分析
        from sklearn.metrics import classification_report, confusion_matrix
        
        print("=== Model Evaluation Results ===")
        print(f"Test Loss: {test_loss:.4f}")
        print(f"Test Accuracy: {test_accuracy:.4f}")
        print(f"Top-5 Accuracy: {test_top5:.4f}")
        
        print("\n=== Classification Report ===")
        print(classification_report(y_true_classes, y_pred_classes))
        
        return {
            'test_loss': test_loss,
            'test_accuracy': test_accuracy,
            'test_top5': test_top5,
            'predictions': y_pred,
            'confusion_matrix': confusion_matrix(y_true_classes, y_pred_classes)
        }
    
    def get_model_summary(self):
        """モデル構造の確認"""
        if self.model is None:
            self.build_model()
        
        print("=== Model Architecture ===")
        self.model.summary()
        
        # パラメータ数の分析
        trainable_params = sum([np.prod(layer.get_weights()[0].shape) 
                               for layer in self.model.layers 
                               if layer.get_weights()])
        
        print(f"\nTrainable parameters: {trainable_params:,}")
        return self.model

# 使用例とテストケース
def create_dummy_data():
    """ダミーデータ作成（テスト用）"""
    X = np.random.rand(1000, 224, 224, 3) * 255
    y = np.random.randint(0, 10, 1000)
    return X, y

def main():
    """実行例（分析対象の使用パターン）"""
    
    print("Creating image classifier...")
    classifier = ImageClassifierCNN(input_shape=(224, 224, 3), num_classes=10)
    
    # ダミーデータで実験
    X, y = create_dummy_data()
    
    print("Preparing data...")
    (X_train, X_val, X_test), (y_train, y_val, y_test) = classifier.prepare_data(X, y)
    
    print("Building and training model...")
    history = classifier.train(X_train, y_train, X_val, y_val, epochs=5, batch_size=16)
    
    print("Evaluating model...")
    results = classifier.evaluate_model(X_test, y_test)
    
    # モデル保存
    classifier.model.save('trained_classifier.h5')
    
    return classifier, results

if __name__ == "__main__":
    classifier, results = main()

"""
分析ポイント（AIが評価すべき観点）：

1. アーキテクチャ設計:
   - 畳み込み層の深さと幅の妥当性
   - ActivationとBatchNormalizationの配置
   - Dropoutの適用箇所と比率

2. ハイパーパラメータ:
   - 学習率の初期値と調整戦略
   - バッチサイズの選択根拠
   - エポック数と早期停止の設定

3. データ処理:
   - 正規化手法の適切性
   - データ拡張の種類と範囲
   - 訓練/検証/テスト分割比率

4. 最適化:
   - オプティマイザーの選択
   - 損失関数の妥当性
   - 評価指標の包括性

5. 過学習対策:
   - 正則化手法の効果
   - コールバック設定の適切性
   - 検証戦略の妥当性

6. コード品質:
   - 再利用性とモジュラー設計
   - エラーハンドリング
   - ドキュメンテーション

7. 実用性:
   - スケーラビリティ
   - 推論時パフォーマンス
   - デプロイメント考慮事項
"""