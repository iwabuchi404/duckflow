# サルベージ・メカノイド ゲームエンジン ドキュメント

## 目次

1. [はじめに](#はじめに)
2. [アーキテクチャ概要](#アーキテクチャ概要)
3. [コアエンジンシステム](#コアエンジンシステム)
4. [エンティティコンポーネントシステム](#エンティティコンポーネントシステム)
5. [レンダリングシステム](#レンダリングシステム)
6. [ワールドシステム](#ワールドシステム)
7. [イベントシステム](#イベントシステム)
8. [ゲームクラス](#ゲームクラス)
9. [Vue との統合](#vueとの統合)
10. [実装例](#実装例)
11. [拡張方法](#拡張方法)

## はじめに

このドキュメントは、「サルベージ・メカノイド」ゲームのリファクタリング後のエンジンアーキテクチャについて説明します。このエンジンは、コンポーネントベースの設計に基づき、高い拡張性と保守性を提供します。

エンジンの主な特徴:

- シングルトンパターンを使用したエンジンコア
- コンポーネントベースのエンティティシステム
- イベント駆動型の疎結合アーキテクチャ
- PIXIJS を使用したレンダリングシステム
- タイルベースのワールド管理システム
- Vue.js との容易な統合

## アーキテクチャ概要

エンジンは以下の主要システムから構成されています:

1. **コアエンジン**: `Engine` クラスはシングルトンとして実装され、他のすべてのシステムを管理します。
2. **エンティティシステム**: `EntitySystem`、`Entity`、および各種 `Component` クラスからなるコンポーネントベースのシステム。
3. **レンダリングシステム**: PIXIJS をラップした `RendererSystem` および関連クラス。
4. **ワールドシステム**: ゲーム世界の物理的側面を管理する `WorldSystem` および関連クラス。
5. **イベントシステム**: システム間の通信を可能にする `EventSystem`。

各システムは `System` インターフェースを実装し、エンジンに登録されます。エンジンはゲームループを管理し、各システムの更新を呼び出します。

## コアエンジンシステム

### Engine クラス

`Engine` クラスはエンジンの中心的な役割を果たし、他のすべてのシステムを管理します。

```typescript
// 使用例
const engine = Engine.instance;
engine.registerSystem('renderer', new RendererSystem());
engine.registerSystem('entity', new EntitySystem());
await engine.initialize();
engine.start();
```

主要メソッド:

- `registerSystem(name: string, system: System)`: システムを登録
- `getSystem<T>(name: string)`: 名前でシステムを取得
- `initialize()`: すべてのシステムを初期化
- `start()`: ゲームループを開始
- `stop()`: ゲームループを停止

### System インターフェース

すべてのシステムが実装する必要のあるインターフェース:

```typescript
interface System {
  initialize(engine: Engine): Promise<void>;
  update(deltaTime: number): void;
}
```

## エンティティコンポーネントシステム

### EntitySystem クラス

`EntitySystem` はすべてのゲームエンティティを管理します。

```typescript
// 使用例
const entitySystem = engine.getSystem<EntitySystem>('entity');
const player = new Entity('player', 'character');
entitySystem.registerEntity(player);
```

主要メソッド:

- `registerEntity(entity: Entity)`: エンティティを登録
- `getEntity(id: string)`: ID でエンティティを取得
- `getEntitiesByType(type: string)`: タイプでエンティティを検索
- `getEntitiesByTag(tag: string)`: タグでエンティティを検索
- `removeEntity(id: string)`: エンティティを削除

### Entity クラス

`Entity` はコンポーネントの集合として機能し、ゲーム内のオブジェクトを表現します。

```typescript
// 使用例
const character = new Entity('player1', 'character');
character.addComponent(new TransformComponent(10, 20));
character.addComponent(new SpriteComponent('character.png'));
character.addTag('player');
```

主要メソッド:

- `addComponent(component: Component)`: コンポーネントを追加
- `getComponent<T>(type: string)`: コンポーネントを取得
- `addTag(tag: string)`: タグを追加
- `hasTag(tag: string)`: タグの有無を確認

### Component インターフェース

すべてのコンポーネントが実装するインターフェース:

```typescript
interface Component {
  type: string;
  entity: Entity | null;
  initialize(): void;
  update(deltaTime: number): void;
}
```

### 主要コンポーネント

#### TransformComponent

エンティティの位置、回転、スケールを管理します。

```typescript
// 使用例
const transform = new TransformComponent(10, 20, 0);
entity.addComponent(transform);
transform.setPosition(15, 25, 0);
```

#### SpriteComponent

エンティティの視覚的表現を管理します。

```typescript
// 使用例
const sprite = new SpriteComponent('character.png', 'characters');
entity.addComponent(sprite);
sprite.visible = false; // 非表示にする
```

#### HealthComponent

エンティティの体力とダメージ処理を管理します。

```typescript
// 使用例
const health = new HealthComponent(100, 100);
entity.addComponent(health);
health.takeDamage(20);
```

#### MovementComponent

エンティティの移動と方向を管理します。

```typescript
// 使用例
const movement = new MovementComponent(4);
entity.addComponent(movement);
movement.moveInDirection('up');
```

## レンダリングシステム

### RendererSystem クラス

PIXIJS をラップし、ゲームのビジュアル表現を管理します。

```typescript
// 使用例
const rendererSystem = new RendererSystem();
rendererSystem.setCanvas(document.getElementById('game-canvas'));
engine.registerSystem('renderer', rendererSystem);
```

主要メソッド:

- `setCanvas(canvas: HTMLCanvasElement)`: レンダリング先のキャンバスを設定
- `renderEntity(data: { sprite, layer, position })`: エンティティをレンダリング
- `resize(width: number, height: number)`: レンダラのサイズを変更

### Camera クラス

ゲームワールドのビューを制御します。

```typescript
// 使用例
const rendererSystem = engine.getSystem<RendererSystem>('renderer');
const camera = rendererSystem.getCamera();
camera.setTargetPosition(100, 100);
```

主要メソッド:

- `move(dx: number, dy: number)`: カメラを移動
- `setTargetPosition(x: number, y: number)`: カメラの目標位置を設定
- `setZoom(zoom: number)`: ズームレベルを設定

### CoordinateSystem クラス

座標変換を処理します。

```typescript
// 使用例
const rendererSystem = engine.getSystem<RendererSystem>('renderer');
const coordSystem = rendererSystem.getCoordinateSystem();
const screenPos = coordSystem.isometricToScreen(10, 10, 0);
```

主要メソッド:

- `isometricToScreen(x: number, y: number, z: number)`: アイソメトリック座標をスクリーン座標に変換
- `screenToIsometric(screenX: number, screenY: number)`: スクリーン座標をアイソメトリック座標に変換

## ワールドシステム

### WorldSystem クラス

ゲーム世界の地形やナビゲーションを管理します。

```typescript
// 使用例
const worldSystem = engine.getSystem<WorldSystem>('world');
const isWalkable = worldSystem.isWalkable(10, 10, 0);
const path = worldSystem.findPath(startPos, goalPos);
```

主要メソッド:

- `isWalkable(x: number, y: number, z: number)`: 指定位置が通行可能か確認
- `getTile(x: number, y: number, z: number)`: 指定位置のタイルを取得
- `findPath(start: Vector3, goal: Vector3)`: 2 点間の経路を探索
- `changeFloor(floorNumber: number)`: フロアを変更

### TileMap クラス

タイルベースのマップデータを管理します。

```typescript
// 使用例
const tileMap = new TileMap(50, 50);
tileMap.importMapData(mapData);
const tile = tileMap.getTile(10, 10, 0);
```

主要メソッド:

- `setTile(tile: Tile)`: タイルを設定
- `getTile(x: number, y: number, z: number)`: タイルを取得
- `isWalkable(x: number, y: number, z: number)`: 通行可能か確認
- `importMapData(data: number[][])`: マップデータをインポート

### MapGenerator クラス

ランダムなマップを生成します。

```typescript
// 使用例
const mapGenerator = new MapGenerator(50, 50, 4, 8);
const mapData = mapGenerator.generateMap();
```

主要メソッド:

- `generateMap()`: ランダムマップを生成
- `getRooms()`: 生成された部屋の情報を取得

## イベントシステム

### EventSystem クラス

オブザーバーパターンを実装し、システム間の疎結合通信を可能にします。

```typescript
// 使用例
const eventSystem = engine.getSystem<EventSystem>('event');
eventSystem.on('player_move', (data) => console.log('Player moved:', data));
eventSystem.emit('player_move', { position: { x: 10, y: 20 } });
```

主要メソッド:

- `on(eventName: string, callback: Function)`: イベントリスナーを登録
- `off(eventName: string, callback: Function)`: イベントリスナーを削除
- `emit(eventName: string, data?: any)`: イベントを発行

## ゲームクラス

### Game クラス

エンジンと各システムを統合し、ゲーム固有のロジックを実装します。

```typescript
// 使用例
const game = new Game();
await game.initialize(document.getElementById('game-canvas'));
```

主要メソッド:

- `initialize(canvas: HTMLCanvasElement)`: ゲームを初期化
- `movePlayer(direction: Direction)`: プレイヤーを移動
- `playerAttack()`: プレイヤーの攻撃を処理
- `setOnGameOver(callback: Function)`: ゲームオーバー時のコールバックを設定

### Player クラス

プレイヤーキャラクターを管理します。

```typescript
// 使用例
const player = game.player;
player.move('up');
player.attack();
```

主要メソッド:

- `move(direction: Direction)`: 指定方向に移動
- `attack()`: 攻撃を実行
- `consumeEnergy(amount: number)`: エネルギーを消費
- `getStatus()`: ステータス情報を取得

## Vue との統合

このエンジンは Vue.js と容易に統合できます。

```vue
<template>
  <div class="game-screen">
    <canvas ref="gameCanvas"></canvas>
    <!-- UIコントロール -->
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { Game } from '@/game/Game';

const gameCanvas = ref(null);
const game = new Game();

onMounted(async () => {
  if (gameCanvas.value) {
    await game.initialize(gameCanvas.value);

    // ゲームイベントとUIを連携
    game.setOnGameOver((score) => {
      // ゲームオーバー処理
    });
  }
});

// UIハンドラー
const movePlayer = (direction) => {
  game.movePlayer(direction);
};

const attack = () => {
  game.playerAttack();
};
</script>
```

## 実装例

### 敵キャラクターの作成

```typescript
// EnemyFactory.ts
class EnemyFactory {
  static async createSlime(id: string, position: Vector3): Promise<Entity> {
    const enemy = new Entity(id, 'enemy');
    enemy.addTag('enemy');

    // 必須コンポーネント
    enemy.addComponent(new TransformComponent(position.x, position.y, position.z));
    enemy.addComponent(new SpriteComponent('slime.png', 'characters'));
    enemy.addComponent(new HealthComponent(50));

    // AI行動
    enemy.addComponent(new AIComponent('random', 5));

    return enemy;
  }
}

// 使用例
const enemyPosition = worldSystem.getRandomWalkableTile();
const enemy = await EnemyFactory.createSlime('enemy1', enemyPosition);
entitySystem.registerEntity(enemy);
```

### アイテム収集システム

```typescript
// CollectibleComponent.ts
class CollectibleComponent implements Component {
  type = 'collectible';
  entity: Entity | null = null;

  constructor(public itemType: string, public value: number) {}

  initialize(): void {
    // イベントリスナー登録
    const eventSystem = Engine.instance.getSystem<EventSystem>('event');
    if (eventSystem && this.entity) {
      eventSystem.on('entity_collision', (data) => {
        if (data.entityId === this.entity?.id && data.collidedWith.hasTag('player')) {
          this.collect(data.collidedWith);
        }
      });
    }
  }

  collect(collector: Entity): void {
    // アイテム収集ロジック
    const eventSystem = Engine.instance.getSystem<EventSystem>('event');
    if (eventSystem) {
      eventSystem.emit('item_collected', {
        collectorId: collector.id,
        itemType: this.itemType,
        value: this.value,
      });
    }

    // エンティティシステムからアイテムを削除
    const entitySystem = Engine.instance.getSystem<EntitySystem>('entity');
    if (entitySystem && this.entity) {
      entitySystem.removeEntity(this.entity.id);
    }
  }

  update(deltaTime: number): void {
    // アニメーションなど
  }
}

// 使用例
const energyTank = new Entity('energyTank1', 'item');
energyTank.addComponent(new TransformComponent(15, 20, 0));
energyTank.addComponent(new SpriteComponent('energyTank.png', 'objects'));
energyTank.addComponent(new CollectibleComponent('energy', 50));
entitySystem.registerEntity(energyTank);
```

## 拡張方法

このエンジンは高い拡張性を持ち、様々な方法で機能を拡張できます。

### 新しいコンポーネントの追加

新しい機能を持つコンポーネントを作成することで、エンティティに新しい能力を追加できます。

```typescript
class EnergyComponent implements Component {
  type = 'energy';
  entity: Entity | null = null;

  private _currentEnergy: number;
  private _maxEnergy: number;

  constructor(maxEnergy: number, currentEnergy: number = maxEnergy) {
    this._maxEnergy = Math.max(1, maxEnergy);
    this._currentEnergy = Math.min(Math.max(0, currentEnergy), this._maxEnergy);
  }

  initialize(): void {
    // 初期化処理
  }

  update(deltaTime: number): void {
    // 自動回復などの処理
  }

  consume(amount: number): boolean {
    if (amount <= 0) return true;
    if (this._currentEnergy < amount) return false;

    this._currentEnergy -= amount;
    this.emitEnergyChangedEvent();
    return true;
  }

  restore(amount: number): number {
    if (amount <= 0) return 0;

    const oldEnergy = this._currentEnergy;
    this._currentEnergy = Math.min(this._currentEnergy + amount, this._maxEnergy);

    const restored = this._currentEnergy - oldEnergy;
    if (restored > 0) {
      this.emitEnergyChangedEvent();
    }

    return restored;
  }

  private emitEnergyChangedEvent(): void {
    if (!this.entity) return;

    const eventSystem = Engine.instance.getSystem<EventSystem>('event');
    if (eventSystem) {
      eventSystem.emit('energy_changed', {
        entityId: this.entity.id,
        currentEnergy: this._currentEnergy,
        maxEnergy: this._maxEnergy,
        percentage: (this._currentEnergy / this._maxEnergy) * 100,
      });
    }
  }
}
```

### 新しいシステムの追加

エンジンに新しいシステムを追加することで、ゲーム全体に関わる機能を実装できます。

```typescript
class PhysicsSystem implements System {
  private entities: Map<string, Entity> = new Map();

  async initialize(engine: Engine): Promise<void> {
    const entitySystem = engine.getSystem<EntitySystem>('entity');
    const eventSystem = engine.getSystem<EventSystem>('event');

    // エンティティの作成イベントを監視
    if (eventSystem && entitySystem) {
      eventSystem.on('entity_created', (data) => {
        const entity = entitySystem.getEntity(data.entityId);
        if (entity && entity.hasComponent('rigidbody')) {
          this.entities.set(entity.id, entity);
        }
      });

      eventSystem.on('entity_destroyed', (data) => {
        this.entities.delete(data.entityId);
      });
    }
  }

  update(deltaTime: number): void {
    // 物理シミュレーション
    for (const entity of this.entities.values()) {
      this.updateEntityPhysics(entity, deltaTime);
    }

    // 衝突検出
    this.detectCollisions();
  }

  private updateEntityPhysics(entity: Entity, deltaTime: number): void {
    // 物理更新ロジック
  }

  private detectCollisions(): void {
    // 衝突検出ロジック
  }
}

// 使用例
const physicsSystem = new PhysicsSystem();
engine.registerSystem('physics', physicsSystem);
```

このドキュメントは、エンジンの基本的な使用方法と拡張方法を説明しています。実際のゲーム開発においては、これらのコンポーネントとシステムを組み合わせ、必要に応じて拡張していくことで、様々なゲーム機能を実現できます。
