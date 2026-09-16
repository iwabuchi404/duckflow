# Tool Calling 対応調査

調査日: 2026-09-13。対象は `duckflow.yaml` の登録・既定モデル（重複除外）、最近のE2E対象4モデル、比較用M2.5。世界中のLLMの網羅ではない。

## 結論と判定範囲

- E2E対象の GLM-4.5-Air / MiniMax-M2.1 / Claude Haiku 4.5 / DeepSeek V4.1 Flash は、OpenRouterのモデル一覧で `tools` / `tool_choice` 対応掲載を確認。
- **モデル側対応とDuckflow側実装は別**。現行メインループはSym-OpsテキストをActionListへ変換する。APIのtools送信、tool_calls受信、tool_call_id付き結果履歴の一巡は未実装。
- 今回は公式資料・公開APIによる調査。認証付きTool Callingの往復試験は未実施。配信プロバイダー、アカウント権限、推論モードまで含む実動作保証ではない。
- `structured_outputs` の掲載は、全応答JSON化やstrict toolsの対応と同一視しない。Tool Callingは独立の機能。
- 公開情報がないことを「モデル能力として非対応」とは断定しない。未掲載・廃止・未確認を分離する。

## 1. OpenRouter経由

根拠: [公開モデルAPI](https://openrouter.ai/api/v1/models)。取得日時とsupported_parametersの抜粋は [JSONスナップショット](tool-calling-catalog-2026-09-13.json) に保存。

| モデルID | tools / tool_choice | structured_outputs掲載 | 扱い |
|---|---|---|---|
| `z-ai/glm-4.5-air` | 両方あり | なし | 主評価対象。通常Tool Calling候補 |
| `minimax/minimax-m2.1` | 両方あり | なし | 最初のA/B対象 |
| `anthropic/claude-haiku-4.5` | 両方あり | あり | 主評価対象 |
| `deepseek/deepseek-v4.1-flash` | 両方あり | あり | 強い参照モデル |
| `minimax/minimax-m2.5` | 両方あり | あり | 追加候補 |
| `deepseek/deepseek-v4-flash-0731` | 両方あり | あり | 設定上の既定ID。旧版・提供実体の変更は別途確認 |
| `anthropic/claude-sonnet-4.5` | 両方あり | あり | 対応掲載 |
| `google/gemini-2.5-flash` | 両方あり | あり | 対応掲載。yaml内に重複登録あり |
| `google/gemini-2.5-pro` | 両方あり | あり | 対応掲載 |
| `z-ai/glm-4.5-air:free` | ID自体が未掲載 | 判定不可 | 有料IDの対応を流用しない。新規実験から除外 |
| `anthropic/claude-3-5-sonnet-20241022` | ID自体が未掲載 | 判定不可 | 現在の経路が未確認。新規実験から除外 |

公開APIはモデル単位の情報。初回の認証付き試験では実際の配信先を記録し、可能な場合は `provider.require_parameters=true` 等で必要パラメータに対応する経路へ限定する。非対応経路へサイレントに迂回しない。

## 2. その他の設定済み経路

| 経路 / モデルID | 公開資料での判定 | 補足 |
|---|---|---|
| OpenAI / `gpt-4o` | Function calling対応 | [公式](https://developers.openai.com/api/docs/models/gpt-4o)。アカウントでの利用可否は未確認 |
| OpenAI / `gpt-4o-mini` | Function calling対応 | [公式](https://developers.openai.com/api/docs/models/gpt-4o-mini) |
| Groq / `llama-3.3-70b-versatile` | Tool Use対応 | [公式対応表](https://console.groq.com/docs/tool-use/overview)。strict等は別判定 |
| Google / `gemini-1.5-pro-002` | 旧モデル・利用対象外 | Gemini 1.5は現行APIで廃止。歴史的な機能対応と利用可能性を混同しない。[Google公式フォーラム回答](https://discuss.ai.google.dev/t/topic-critical-execution-hallucination-in-gemini-api-shell-tool-integration/135658/3) |
| Cloudflare / `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Function calling: Yes | [モデル資料](https://developers.cloudflare.com/workers-ai/models/llama-3.3-70b-instruct-fp8-fast/) |
| Cloudflare / `@cf/moonshotai/kimi-k2.7-code` | Function calling: Yes | [モデル資料](https://developers.cloudflare.com/workers-ai/models/kimi-k2.7-code/)。有料アクセス要件あり |
| Cloudflare / `@cf/zai-org/glm-5.2` | Function calling: Yes | [モデル資料](https://developers.cloudflare.com/workers-ai/models/glm-5.2/)。推論設定のマッピングあり |
| Cloudflare / `@cf/qwen/qwq-32b` | 未確認・初期native対象外 | [モデル資料](https://developers.cloudflare.com/workers-ai/models/qwq-32b/)の機能欄にFunction callingなし、入力toolsなし。一方、出力型にtool_calls欄があり断定不可。QwQ全体の非対応とはしない |

## 3. 非対応経路の扱い

今回の登録モデルには、「現行公式経路が明示的にTool Calling非対応」と確定できる例は見つからなかった。対応不明のQwQ、廃止・未掲載のIDを、無理に非対応へ分類しない。

参考としてOpenRouter公開一覧には `inference-net/schematron-v2-small` と `tencent/hy-mt2-1.8b` が存在するが、`tools` / `tool_choice` は掲載されていない。現時点のその経路ではnativeを利用対象外とする。前者にはstructured_outputsが掲載されており、JSONスキーマ出力とTool Callingが別機能である例でもある。コーディング比較用にこの2モデルを追加する提案ではない。

ローカル推論では、モデル名だけで決めず「重み版・chat template・推論エンジン・tool parser」の組合せで確認する。未確認・非対応経路はSym-Opsを維持する。

## 4. 実装前の能力確認

1. 公開対応情報を取得し、model ID / provider / endpoint / 調査日時を固定。
2. 副作用のないテストツール1つで、名前・引数・IDの受信を確認。
3. tool_call_id付き結果を返し、次の通常応答まで往復させる。
4. content=nullのtool_calls、複数呼び出し、拒否、推論あり、必要パラメータ未対応を別ケースで確認。
5. 掲載ありでも試験失敗なら、その理由を記録してnative未検証に戻す。能力判定API障害をモデル非対応にしない。

MiniMaxは内部XMLからAPI tool_callsへ変換する構成が公式に説明されている。APIがJSONを返すこととモデルがJSONを直接生成することは同じではない。[公式ガイド](https://huggingface.co/MiniMaxAI/MiniMax-M2.1/blob/main/docs/tool_calling_guide.md)

その他の契約根拠: [OpenRouter Tool Calling](https://openrouter.ai/docs/guides/features/tool-calling)、[DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)。
