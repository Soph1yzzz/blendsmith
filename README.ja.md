<p align="center">
  <img src="docs/assets/blendsmith-readme-hero.png" alt="BlendSmith — AI支援Blender制作のためのプロダクションループハーネス" width="100%">
</p>

<h1 align="center">BlendSmith</h1>

<p align="center"><strong>AI支援Blender制作を、制作・検証・修正・承認まで一つのループで管理するハーネス。</strong></p>
<p align="center">方法を選ぶ。実物を見る。必要なところだけ直す。最後は人間が決める。</p>

<p align="center">
  <a href="https://github.com/Soph1yzzz/blendsmith/releases/latest"><img src="https://img.shields.io/github/v/release/Soph1yzzz/blendsmith?style=flat-square&label=release" alt="Latest release"></a>
  <a href="https://github.com/Soph1yzzz/blendsmith/actions/workflows/ci.yml"><img src="https://github.com/Soph1yzzz/blendsmith/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Blender-5.2%20LTS-F5792A?logo=blender&logoColor=white" alt="Blender 5.2 LTS">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache--2.0-4C8BF5.svg" alt="Apache-2.0"></a>
</p>

<p align="center">
  <strong><a href="README.md">English</a></strong> ·
  <strong><a href="#codexで使う">クイックスタート</a></strong> ·
  <strong><a href="#このワークフローでどこまで作れるか">制作例</a></strong> ·
  <strong><a href="#制作を一周させる">制作ループ</a></strong> ·
  <strong><a href="#専用機能を先にスクラッチは最後に">方法選択</a></strong> ·
  <strong><a href="docs/ROADMAP.md">ロードマップ</a></strong>
</p>

BlendSmithは、Blenderを扱うAIエージェント向けの**モデル非依存ループハーネス**です。

モデルやBlender、MCP、`bpy`、GUI操作そのものを置き換えるものではありません。制作の前後にある、方法選択、候補管理、画像での確認、修正、チェックポイント、人間の承認、保存と公開までをCore側の状態として管理します。

GPT-6 Astraの登場で、モデル単体でもかなり印象的な3Dアセットを作れるようになりました。ただ、**作れることと、毎回適切なBlender機能を選び、結果を確認し、失敗から安全に戻り、レビュー済みの成果物を人間へ渡せることは別の問題**です。BlendSmithは、その周辺を受け持ちます。

## このワークフローでどこまで作れるか

BlendSmithの元になったローカルハーネスは、GPT-5.6 Sol Highの時点で実際のBlender制作に使っていました。

<p align="center">
  <img src="assets/examples/gothic-interior.png" alt="AI支援で制作したゴシック建築内装" width="100%">
</p>

<table>
  <tr>
    <td width="50%" align="center"><img src="assets/examples/ruby-ring.png" alt="ルビーリング" width="100%"></td>
    <td width="50%" align="center"><img src="assets/examples/emerald-ring.png" alt="エメラルドリング" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>宝飾・高密度な装飾</b></td>
    <td align="center"><b>宝石・ハードサーフェス</b></td>
  </tr>
</table>

出力品質は、使うモデル、参考画像、Blender側で利用できる機能、何回見直すかによって変わります。BlendSmithが担当するのは作品そのものではなく、**作品を作って確認し、必要なら直す流れ**です。

### 現行世代でも役割は残った

GPT-6 Astraを使った軽い内部テストでは、モデル自身が候補を作り、前の版を見直して修正するところまで進められました。その状態でも、BlendSmithによる方法探索、候補ファイルのSHA固定、6方向の証跡、Blender GUIでの最終確認、`OWNER_REVIEW`での停止は有用でした。

<p align="center">
  <img src="docs/assets/blendsmith-astra-dogfood.png" alt="GPT-6 AstraでのBlendSmith内部テスト" width="100%">
</p>

## 制作を一周させる

AIで3Dを作るとき、生成だけを独立した作業にすると「とりあえず作った」「見た感じ良さそう」で終わりやすくなります。BlendSmithでは、制作、確認、修正、再選択、承認を同じループに入れます。

<p align="center">
  <img src="docs/assets/blendsmith-control-loop.png" alt="BlendSmithの制作コントロールループ" width="100%">
</p>

レビュー後の進み方も分けています。

- **局所修正** — 方法は合っている。問題になっている箇所だけ直して、もう一度確認する。
- **方法の再選択** — そもそもの作り方が悪い。同じ方法を継ぎ足し続けず、Method Selectionへ戻る。
- **AI側の合格** — 自動検証は通った。ここから先は人間の判断待ち。

最後は意図的にここで止まります。

```text
AI_ACCEPTED != HUMAN_ACCEPTED
```

エージェントは「進めたい」と提案できます。状態遷移が正しいかはBlendSmith Coreが判断し、レビュー済みのそのファイルを最終的に受け取るかどうかはOwnerが決めます。

## BlendSmithが止めたい失敗

| よくある状態 | BlendSmithでの扱い |
| --- | --- |
| Blenderに専用機能があるのに、モデルが思い出さず自作を始める | **Method Selection Gate**で制作前に専用手段を確認する |
| ファイルができた時点で完成扱いする | **Evidence-backed review**で実際の画像を開いて確認する |
| 作り方を間違えたまま細かい手直しを続ける | **Method reconsideration**で方法選択まで戻る |
| AIが「良さそう」と言ったので完成にする | AI合格と人間承認を分離する |
| レビュー後にファイルが変わる | SHA-256でレビュー済みの正確なバイト列を固定する |
| GUIや外部機能が壊れた | `BROKEN` / `UNKNOWN`を勝手に`UNAVAILABLE`扱いしない |
| 長い作業の途中でセッションが切れる | Checkpoint / resumeで検証済み状態から再開する |
| 中間ファイルが増え続ける | TTLと検証付きGCで対象だけ整理する |

全部のループが成功で終わるとは限りません。直せるなら修正へ戻り、方法が悪ければ再選択し、自動で解けない状態ならOwnerへ返します。止まり方まで状態として残すのがBlendSmithの役目です。

## 専用機能を先に、スクラッチは最後に

Blenderに`Mirror`や`Array`、Geometry Nodes、アセットライブラリ、拡張機能があると知っているだけでは足りません。実際の制作で、その場に合うものを選ぶ必要があります。

<p align="center">
  <img src="docs/assets/blendsmith-method-selection.png" alt="BlendSmithのspecialized-first方法選択" width="100%">
</p>

BlendSmithは制作前に作業単位（work unit）へ分け、単位ごとに利用可能な方法を調べます。標準設定では次を確認します。

- Blender標準機能
- Geometry Nodes / Node Tool
- アセットライブラリ
- インストール済み拡張機能
- プロジェクト内カタログ
- 設定済みAdapter

既知の候補を無視したまま「見つからなかったこと」にして通すことはありません。必要な探索元や有力な専用方法が`BROKEN` / `UNKNOWN`のままなら、汎用的な作り方へのフォールバックも止めます。

内蔵ヒントの例です。

```text
symmetry        -> Mirror
repetition      -> Array / Geometry Nodes
surface scatter -> Geometry Nodes
thickness       -> Solidify
lathe / revolve -> Screw
edge rounding   -> Bevel
hair            -> Geometry Nodes / Node Tool
tree generation -> extension / Node Tool / asset-library discovery
```

手作業のメッシュ構築を禁止しているわけではありません。専用機能で素直に解けるなら先にそれを使い、必要なときだけスクラッチへ落とします。

## Codexで使う

### 1. BlendSmithを入れる

```bash
git clone https://github.com/Soph1yzzz/blendsmith.git
cd blendsmith
python -m pip install .
```

Python **3.11以上**が必要です。Blenderは**5.2 LTS**を主要ターゲットにしています。

### 2. Codex Skillを入れる

```bash
blendsmith skill-install
blendsmith doctor
```

`blendsmith doctor`は、インストール済みSkillと現在のCLI/Coreが一致しているかを確認します。Skillを新規インストール・更新したあとはCodexを再起動してください。

### 3. Codexに頼む

```text
BlendSmithを使って、この参考画像からBlenderで作って。
```

これで十分です。

Skillは薄い操作層として作ってあります。状態遷移をプロンプト側に丸ごと複製せず、`doctor`、`status`、CLI help、JSON Schemaを現在のCoreから読みます。正本は常にCLI/Coreです。

## 呼び出した後に何が起きるか

典型的な流れは次の通りです。

```text
preflight
  -> method plan
  -> method selection
  -> Blender production
  -> candidate pin
  -> multi-view evidence
  -> visual review
       -> local repair -> production
       -> method reconsideration -> method selection
  -> live GUI review when available
  -> AI_ACCEPTED
  -> OWNER_REVIEW
```

`OWNER_REVIEW`に入ると自動進行は止まります。

人間の承認は、レビューしたcandidateのSHA-256に対して行います。無言だった、AIが合格と言った、前の版を一度承認した、といった事情から新しいcandidateを自動承認することはありません。

## 中断しても、会話の記憶だけに頼らない

長いBlender作業では、途中でセッションが切れたり、別のエージェントへ引き継いだりします。BlendSmithのcheckpointは、検証済みMethod Plan / Method Selection、selection round、candidate closure、ハッシュの結び付きを保存します。

resume時にはそれらをもう一度検証します。前の会話で「たしかここまで終わっていたはず」という記憶を、そのまま権限として扱いません。

## CLI/Coreを直接使う

BlendSmithはCodex専用ではありません。Codex SkillはAdapterの一つで、状態遷移の決定権はCLI/Core側にあります。

```bash
blendsmith --version
blendsmith doctor
blendsmith init <project>
blendsmith preflight --project <project>
blendsmith start --project <project>
blendsmith status --project <project>
```

契約SchemaもCLIから確認できます。

```bash
blendsmith schema method_plan
blendsmith schema method_selection
blendsmith schema visual_review
```

主なライフサイクルコマンド:

```bash
blendsmith method-hints --project <project> --intent symmetry
blendsmith method-plan --project <project> --input method_plan.json
blendsmith method-select --project <project> --input method_selection.json
blendsmith candidate-add --project <project> --candidate <scene.blend>
blendsmith evidence-begin --project <project>
blendsmith evidence-submit --project <project> --view front=<front.png>
blendsmith visual-review --project <project> --input visual_review.json
blendsmith gui-review --project <project> --input live_gui_review.json
blendsmith ai-accept --project <project>
blendsmith owner-accept --project <project> --sha256 <candidate_sha256>
blendsmith checkpoint --project <project>
blendsmith resume --project <project>
blendsmith publish --project <project>
blendsmith gc --project <project>
```

CLIが状態遷移を検証するので、エージェントがルールを覚えていること自体を安全性の前提にしていません。

## Core側で保証すること

- **状態遷移の決定権はCoreに置く。** エージェントは操作を提案し、Coreが現在の状態から許可できるかを判定する。
- **Specialized first, scratch last.** 要件を満たす専用手段があるなら、汎用構築より先に評価する。
- **Method PlanからcandidateまでSHAでつなぐ。** candidateはMethod SelectionのSHAを持ち、そのSelectionはMethod PlanのSHAへ結び付く。
- **検証済みreceiptは後から差し替えられない。** 正規の状態遷移を通さず編集するとintegrity errorになる。
- **Evidenceはレビューの実入力。** ファイルが存在するだけでは視覚確認済みにならない。
- **局所修正と方法再選択を分ける。** 方法が悪いときに、細かいパッチだけで押し切らない。
- **GUI確認にも具体的な証跡を求める。** path、dirty state、viewport interaction、observed viewsを記録する。
- **人間承認は明示的かつSHA-bound。** Ownerだけが、レビュー済みcandidateの正確なSHAを承認できる。
- **retryは有限。** retry-safeな操作も初回＋最大3回まで。安全性や整合性に関わる曖昧さはOwnerへ返す。
- **checkpointでも検証済みの状態を保つ。** Method receiptとcandidate closureを固定し、resume時に再検証する。
- **GC対象を限定する。** 管理領域内で期限切れかつ検証済みの対象だけを整理する。
- **契約はモデル非依存。** モデル固有の思考フォーマットではなく、状態と証拠を検証する。

## プロジェクト構成

```text
<project>/
├─ blendsmith.project.json
├─ .blendsmith/
│  ├─ install/
│  ├─ capabilities/
│  ├─ runs/
│  └─ history/
└─ publication/
   └─ current/
```

`.blendsmith/`には実行状態や証跡を置きます。通常はソース管理へ入れません。`publication/current/`にはBlendSmithが検証した現在のローカル公開物を置きます。

## ドキュメント

- [仕様](docs/SPECIFICATION.md)
- [Method Selection Gate](docs/METHOD_SELECTION.md)
- [セキュリティモデル](docs/SECURITY.md)
- [契約Schema](docs/CONTRACTS.md)
- [ロードマップ](docs/ROADMAP.md)
- [変更履歴](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## 開発

```bash
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m pytest -q
```

CIはWindows / Ubuntu、Python 3.11 / 3.12で実行しています。

## 現在の状態

**v0.0.1**が最初の公開版です。モデル非依存のCore/CLIを中心に、Production Loop、Method Selection Gate、画像証跡とVisual Review、局所修正、方法の再選択、Live GUI Review、Owner承認、checkpoint/resume、retention/GC、検証付きローカル公開、Codex Skillまでを含みます。

次の**v0.0.2 — Production Structure**では、作業単位の分解、依存関係を持つProduction Graph、Construction Sequence、Structural Integrity、Owner Actionからの安全な復帰、エージェント向けの状態確認機能を進める予定です。詳しくは[ロードマップ](docs/ROADMAP.md)を参照してください。

## ライセンス

Apache License 2.0です。詳細は[LICENSE](LICENSE)を参照してください。
