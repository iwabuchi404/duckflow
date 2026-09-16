# ①ツール定義一元化・②実行前検証・⑥Tool Calling比較 実装計画

作成日: 2026-09-13
状態: **提案・実装前**。本書は製品仕様の確定やSym-Ops廃止の決定ではない。

## 目的と範囲

「弱いモデルにはSym-Opsのほうが低負荷ではないか」という仮説を維持し、同じ意味のツール操作をnative Tool Callingでも実行できる比較経路を作る。単発の形式成功率ではなく、正しい完遂1件当たりのトークン・時間・費用・介入回数を比較する。

対象は先の改善案の①ツール定義一元化、②パースと実行の間の検証、⑥ネイティブTool Calling比較。③完了制御の全面変更、④反復検知の改訂、⑤編集手段の自動切替、Sym-Ops v4への全面移行、追加LLMによる要約、自動モデル昇格、サブエージェントは本計画に含めない。

調査結果: [Tool Calling対応一覧](../research/tool-calling-support-2026-09-13.md)。主評価4モデルは公開APIで対応掲載。ただし認証付き往復は未検証。最初はOpenRouter/MiniMax-M2.1で接続を実証し、DeepSeek V4.1 Flash、Haiku 4.5、GLM-4.5-Airへ広げる。他の経路は後段の互換性試験対象。

## 現状と前提

- `core_tools.py` が登録とモード公開、`llm_client.py` 内の `_TARGET_PARAM` / `_CONTENT_PARAM` がSym-Ops引数変換、`core_action_invocation.py` が本文回復・必須引数検証を担当しており、契約が分散している。
- `core_action_executor.py` では承認の後にinvoke_toolが引数回復する。回復によって対象が決まる場合、承認前に確定した操作を提示できない。②では正規化を前へ移す。
- `llm_client.chat()` はメインActionListの場合もテキストをSym-Ops解析する。通常のcontent=null＋tool_callsを空応答と扱わない分岐が必要。
- 会話履歴は主にrole/contentのテキスト。nativeで必要な呼び出しIDとtool結果の対応、再起動時の保存復元、pruningによる対応崩れを設計する必要がある。
- 既存のToolResult、ActionList、承認、モード制限、fail-fast、パス保護、Correction Guideを利用する。native専用の実行エンジンは作らない。
- 作業ツリーにユーザーの未コミット修正が多数ある。実装時に再確認し、今回のwrite_file回復案内等を消さない。
- Notion context/specは調査時点で旧5ノード構成の記載。現コードとAGENTS.mdを優先した。Notionへの提案・仕様の連鎖更新はユーザー確認後に行う。

## 構成案

```text
ToolSpec / Registry
  ├─ Sym-Ops説明と引数マッピング
  └─ native tools schema

Sym-Opsテキスト ─ adapter ─┐
                          ├─ ActionList候補 → 正規化 → 共通検証 → 承認 → 実行
API tool_calls ─ adapter ─┘                                    ↓
                    各プロトコルの履歴へ ← 実行イベント・ToolResult
```

### ToolSpecで共有する情報

名前、短い説明、ハンドラー、型付き公開引数、必須/任意/default、target引数、body引数、公開モード、変更対象の解決、承認方針への参照、終端/非終端、本文内の編集形式、契約バージョン。

引数モデルは既存Pydanticを利用し、schemaとローカル検証を同じ定義から生成する案を第一候補とする。ハンドラーの型ヒントと起動時に照合し、二重管理の食い違いをテストで検知する。workspace_root、**kwargs、内部専用ツールをそのまま公開しない。

対象・本文を単純な名前推測で決めない。例: replace_functionはtarget=path/body=body、write_fileはtarget=path/body=content、run_commandはtarget/body=command。edit_fileの本文形式は比較時に両経路とも同じSEARCH/REPLACE文字列にする。

## 実装順序と受入条件

### Phase 0: 基準とプローブを固定

- 既存の未コミット状態を含め、コミット＋差分ハッシュ・シナリオ/fixtureハッシュ・有効設定を記録する。
- 既存の形式失敗（inline <<<、本文欠落、SEARCH不一致、XML漏れ）をオフライン回帰素材にする。
- 能力レジストリは `(provider, model_id, endpoint, serving_provider)` を単位に supported / unsupported / unknown と、根拠・確認日時・往復確認有無を持つ。strict・parallel・reasoningは独立の能力とする。
- 公開情報確認は読取のみ。ライブ能力試験は副作用なしのecho相当ツールで行い、成果と消費を保存する。

受入: native対応掲載と実際の1往復成功を区別して記録できる。APIエラーやモデル未掲載を推論性能の失敗へ混ぜない。

### Phase 1: ①ツール定義の一元化

候補ファイル: 新規 `companion/tool_contracts.py`、`companion/tool_registry.py`、変更 `core_tools.py`、`base/llm_client.py`、`core_action_results.py`。

1. 公開ツールの契約を登録。まずread_file/write_file/edit_file/replace_function/run_commandで実証後、現在の公開ツール全体へ移行する。
2. Sym-Ops説明とtarget/body対応表をRegistryから生成する。
3. 承認やモード判定も同じ契約を参照するが、既存の実行ポリシーを無断で緩めない。replace_function等の承認漏れが見つかった場合は差分として明示する。
4. 旧インターフェースを一時的に委譲ラッパーとして残し、段階移行する。

受入: 公開された例をparse→normalize→validateして、実ハンドラーが受け取る名前・型・本文が一致する。書込本文の改行、引用符、Unicode、空文字を保持する。シグネチャ変更時に説明/検証との不一致がテストで失敗する。

### Phase 2: ②副作用より前の共通検証

候補ファイル: 新規 `companion/action_validation.py`、変更 `core_action_invocation.py`、`core_action_executor.py`、`core_action_pipeline.py`、`prompts/builder.py`。

順序を `decode → normalize → validate → mode/path policy → approve → invoke` に統一する。回復・正規化は承認前に終え、承認後に引数を再解釈しない。実行直前にも必要なパス保護とモードを確認する。

- ツール名、公開範囲、必須値、型、列挙値、長さ上限、パス、編集本文構造を検証する。
- `0` / `False` を欠損にしない。空ファイル作成の `content=""` は「本文未指定」と区別する。
- 外部入力の未知引数を黙って捨てない。互換回復が必要なら適用内容を記録する。本文を意味的に書き換えない。
- 曖昧なinline <<<はファイル名に流さず、形式エラーにする。自動回復は一意で損失のない既存ルールに限定し、nativeのJSON引数へSym-Ops回復をかけない。
- エラーは共通モデル（code/tool/field/expected/received概要/retry hint/executed=false）で保持し、Sym-Opsにもnativeにも同じ意味で返す。
- バッチは静的な構文検証を行い、各呼出し時の動的モードは実行順で確認。1つが無効でも他を実行するかは現行fail-fast契約と揃え、無言スキップはしない。

受入: 不正アクションは副作用ゼロ、承認画面と実行引数が一致。本文欠落とSEARCH不一致で具体的なガイドが返り、次ターンに到達する。既存の拒否・キャンセル・Investigation制限が保たれる。

### Phase 3: ⑥native adapterを実装

候補ファイル: 新規 `companion/base/tool_call_adapter.py`、`companion/protocol_history.py`、`companion/config/model_capabilities.py`。変更 `base/llm_client.py`、`core.py`、`state/agent_state.py`、`core_action_executor.py`、`prompts/builder.py`、`prompts/few_shot.py`、`modules/memory.py`、`modules/session_manager.py`。

- 設定案 `agent.action_protocol: sym_ops | native_tools`。既定はsym_ops。モデル別上書きと評価CLI `--protocol` を追加する案とし、選択はセッション/試行開始時に固定する。
- native対象外/unknownを明示指定したら能力未確認エラーで停止。サイレントにSym-Opsへ戻さない。対応していないモデルは通常設定でSym-Opsを使える。
- OpenAI互換Chat Completionsを最初の対象にする。モデルの生XMLを独自に実行するのではなくAPIのtool_callsを使う。
- nativeでは `tools` と `tool_choice=auto` を送る。全応答JSON強制やstrict=trueは初期比較に入れない。通常文章・推論のチャネルを保持する。
- content=null＋tool_callsは有効応答。不正JSON、未知名、欠損ID、重複ID、途中切断、拒否を区別する。APIが返したtool_callsをSym-Opsへ文字列化して再パースしない。
- API tool_call_idは実行イベントへ保存し、完了・拒否・無効・上限で未実行の各呼出しに対応結果を返す。APIの複数呼出し提案と並列実行を混同せず、初期実装は現行同様に順次実行する。
- assistant tool_callsの後、全tool結果を対応ID付きで返すまで次のassistant生成へ進まない。terminalなduck_call等も結果を閉じてから人間入力待ちへ移る。
- 呼出しと結果を履歴の1グループとして保存・pruningし、片側だけを落とさない。モデル切替/セッション復元時も孤立IDを送信しない。旧セッションはSym-Opsとして読む。
- provider固有のreasoning_details/signature等、継続に必要な情報は対応文書に従い保持する。推論を通常contentへ重複注入しない。
- 通常文章はresponse相当に変換するが、tool_calls併存時の文章を完了と即断しない。初期A/Bでは双方の説明で「実行結果を待ってから完了報告」を揃える。混在時の扱いが異なる実験は別条件として記録する。
- nativeではSym-Ops文法/vitals記法の説明を外す。目的、ツールの意味、モード、承認、ユーザー協業方針は共通にする。例を残す場合は意味・個数を揃えて各方式で表現する。

受入: 副作用なしの往復→ファイル1個作成→編集→テスト→最終報告が動作し、nativeでも同じ承認とパス保護が働く。補助LLMのJSON/Pydantic応答経路を壊さない。

### Phase 4: A/B評価

候補ファイル: `evals/runner.py`、`evals/replay.py`、`evals/analysis.py`、新規 `tests/test_native_tool_calls.py` 等。

比較を3条件に分ける。

| 条件 | 意味 |
|---|---|
| A0 | 現在のSym-Ops基準 |
| A1 | ①②導入後のSym-Ops |
| B | A1と同じ共通層を使うnative Tool Calling |

A0→A1は契約/検証の改善、A1→Bは外部プロトコルの違い。これらを一度に変更してnativeの効果と主張しない。

最初はMiniMax-M2.1で、read_file/write_file/edit_file/replace_function/run_command/duck_callと終了応答を使う小規模課題を各5試行。部分ツール面の結果を全機能E2Eへ混ぜない。その後、公開ツール全体を揃えて主評価4モデルへ展開する。非対応モデルのSym-Ops回帰も別に実施する。

課題: FizzBuzz、multi-file-rename、本文欠落・SEARCH不一致からの回復、期間と行数の回答分岐、質問不要の対照、仕様を明示したno-change、任意のコード生成での複数の正解。応答の創造性をtemperature低下で抑えず、同一モデルでは対応するsampling/推論/出力/ループ/時間予算を固定する。

指標: 成果物の独立採点、必要/不要な質問、回答前の変更、最終報告と実結果の一致、形式エラー・修復回数、反復、実ツール実行数、LLM呼出し数、入力/出力/推論/キャッシュトークン、時間、完遂1件当たり実費。失敗に使った費用も含める。API障害・非対応とモデル失敗を分離し、中央値と最大値を報告する。

記録はLLMClientが組み立てた最終リクエスト地点で行う。messagesだけでなくtools、tool_choice、有効max_tokens、temperature、reasoning、provider routeを保存し、秘密ヘッダーは保存しない。リトライ/空応答を含め各API呼出し前にdeep copyし、応答のcontent/tool_calls/finish_reason/usageと対応付ける。

replayでは保存したpayloadを使う。同一プロトコルでモデルだけ変更する比較は同一入力ハッシュで実施。Sym-Opsとnativeは形式が異なるため「同一のAPI入力」と呼ばず、同一の論理状態・対象ファイル版から各形式へ表現した対応比較にする。

合格基準: すべての安全・契約テストを通過。nativeの成績が良いだけで既定を切替えない。小標本で結論を出さず、差が見えた課題を10回以上へ拡張し、弱いモデルの完遂率・総コスト・多ターン協業を重視してモデル単位に採否を提案する。

## テストと作業単位

PR/作業単位は Phase 0、Phase 1、Phase 2、Phase 3、Phase 4 に分ける。各単位で関連テストと `uv run python -X utf8 -m pytest tests/ -v` を実行する。全関数・クラスに型ヒントとArgs/Returnsを含むDocstringを付ける。

重点テスト:
- 正規・legacy Sym-Opsとnative引数が同じ内部操作になる。
- 改行、引用符、Unicode、空本文、0/False/null、未知引数、パス境界。
- content=null、複数tool_calls、順序、ID対応、拒否・タイムアウト・fail-fast、履歴圧縮・復元。
- 未知モデル、ツール非対応経路、strict非対応、推論モード非対応、402/429は別診断。
- malformed XMLや不完全な呼出しを通常の完了として数えない。最終報告がない場合は「自然完了」にしない。
- 現行evalの正解構造を依頼に明示。質問の期待条件とfixtureは試行時に固定し、現在のyamlから過去の結果を再解釈しない。

今回作成するのは本計画・対応調査・公開APIスナップショット・PROGRESS追記のみ。製品コード、設定、既存の未コミット修正、過去の評価結果は変更しない。
