<p align="center">
  <img src="docs/assets/blendsmith-readme-hero.png" alt="BlendSmith — AI支援Blender制作のためのプロダクションコントロールループ" width="100%">
</p>

<h1 align="center">BlendSmith</h1>

<p align="center"><strong>AIにBlenderをやらせるなら、まずこれを挟めばいい。</strong></p>
<p align="center">強いモデルはもう作れる。BlendSmithは、作り方を崩させない。</p>

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

AIにBlenderを本気でやらせるなら、プロンプトだけ渡して「あとは賢くやって」で終わらせない。**BlendSmithを噛ませる。**

BlendSmithは、Blenderを扱うAIエージェント向けの**モデル非依存プロダクションコントロールループ**です。モデルやBlender、MCP、`bpy`、GUI操作そのものを置き換えるものではありません。仕事を分解し、専用機能を先に検討し、作業同士の依存関係を持たせ、renderとGUIの両方で確認し、問題が起きたら正しい階層まで戻す。その制作判断をCore側で管理します。

大事なのは、**「問題が見えた場所」と「判断を間違えた場所」は同じとは限らない**ことです。見えている不具合は小さくても、原因が作り方にあるならMethod Selectionへ戻す。構造にあるならProduction Graphまで戻す。要求そのものが違うなら上流の契約を更新する。局所修正を積み続ける前に、戻る場所を決めます。

これは弱いモデルを補うための道具ではありません。強いモデルは、もうかなりの3Dを作れます。**BlendSmithは、その能力を長い制作の中で崩さず使い切るための制御層です。**

> 賢さはモデルに任せる。制作の筋道はBlendSmithに守らせる。出力がおかしいなら「もう一回やって」で済ませず、判断を間違えた階層まで戻す。

## このワークフローでどこまで作れるか

私はBlenderも3Dも初心者です。これは、Blenderに慣れた作者が横から細かく直し続けて出した制作例ではありません。

少なくとも私の実制作では、**GPT-5.6 Solをほぼ素のままBlenderに向かわせたときの結果はかなり弱く、専用機能の選び方や見直し方も安定しませんでした。** そこで、方法選択、証拠確認、修正、再選択、承認までをHarnessとして外に出し、モデルに制作ループを与えました。

すると、同じGPT-5.6 Solでもここまで出せるようになりました。

<table>
  <tr>
    <td align="center"><img src="assets/examples/gothic-interior.png" alt="AI支援で制作したゴシック建築内装" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>ゴシック建築 / 大規模内装</b></td>
  </tr>
</table>

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

だからBlendSmithの出発点は、**「AIに3Dを作らせる」ことではありません。もう作れるモデルを、長い制作の中でどう崩さないか**です。

正しいmethodを選び続けられるか。局所修正では済まない問題に気づけるか。固定renderで見逃した違和感まで拾えるか。間違えたら、どの階層まで戻るべきか。BlendSmithはそこを受け持ちます。

出力品質は、使うモデル、参考画像、Blender側で利用できる機能、何回見直すかによって変わります。ただ、強いモデルとBlenderを操作できる環境があるなら、**その間にBlendSmithを入れて制作ループを任せる**という使い方ができます。

### 現行世代でも同じ方向の効果を確認した

これは定量ベンチマークではなく、作者自身の実制作で得た比較です。ただ、GPT-5.6 Solで見えた差は、より強いGPT-6 Astraでも完全には消えませんでした。

GPT-6 Astraを使った小規模な内部テストでは、モデル自身が候補を作り、前の版を見直して修正するところまで進められました。それでも、BlendSmithを通すことで方法探索、候補ファイルのSHA固定、6方向の証跡、Blender GUIでの探索確認、`OWNER_REVIEW`での停止までが一つの制作ループとして残りました。

**モデルが強くなっても、制作ループを外から持たせる効果は残る。** 少なくとも今回の小規模dogfoodでは、GPT-5.6 Solで得たのと同じ方向の効果を確認できました。

<p align="center">
  <img src="docs/assets/blendsmith-astra-dogfood.png" alt="GPT-6 AstraでのBlendSmith内部テスト" width="100%">
</p>

## 制作を一周させる

v0.0.2では、単純な「確認して、悪ければ直す」から一段進めました。修正に入る前に、**どの階層の判断を直すべきか**を決めます。

```text
要求
  -> 作業を分解
  -> Production Graph
  -> 既知のmethod familyを一通り確認
  -> Method Selection
  -> Blenderで制作
  -> candidateを固定
  -> render evidence
  -> Visual Review
       -> 問題・改善点あり
            -> Change Impact Gate
                 -> LOCAL      -> methodを維持 -> Fix Plan
                 -> METHOD     -> Method Selectionへ戻る
                 -> STRUCTURAL -> Production Graph / Method Planを更新
                 -> CONTRACT   -> 上流の要求・Planを更新
       -> Render側は合格
            -> Exploratory Live GUI Review
                 -> 回す / 寄る / 裏を見る / 厚みを見る
                 -> REVISE -> Change Impact Gateへ戻る
                 -> PASS   -> 最終AI検証
  -> AI_ACCEPTED
  -> OWNER_REVIEW
```

`LOCAL`が続いたときは、途中で**Global Reassessment**を挟めます。Method Plan、Production Graph、Method Selection、現在のcandidate、未解決issue、修正履歴まで見直したうえで、「本当にもう一回だけ局所修正でいいのか」を決め直します。

戻り先は4種類です。

- **LOCAL** — 計画と方法は合っている。選択済みmethodを維持したまま、問題箇所だけ直す。
- **METHOD** — 作り方が悪い。手作業で継ぎ足さずMethod Selectionへ戻す。
- **STRUCTURAL** — 作業同士の依存関係が悪い。Production Graphを更新し、影響する下流作業を古いものとして扱う。
- **CONTRACT** — そもそもの要求や設計判断が違う。実装だけこっそり変えず、上流Planを新しいrevisionとして作り直す。

GUI確認も、最後に一度開いてPASSを付けるだけにはしません。使える環境なら、固定renderでは見えにくい**厚み、接続、裏側、装飾密度、materialの見え方、回したときだけ出る違和感**を探しにいきます。

最後は今まで通り、意図的にここで止まります。

```text
AI_ACCEPTED != HUMAN_ACCEPTED
```

エージェントは次の操作を提案できますが、状態遷移を許可するのはBlendSmith Coreです。レビュー済みのそのcandidateを受け取るかどうかはOwnerが決めます。

## モデル単体でよくない？

| よくある状態 | BlendSmithでの扱い |
| --- | --- |
| Blenderに専用機能があるのに、モデルが思い出さず自作を始める | **method familyの事前確認 + Method Selection Gate**で、既知の専用手段を制作前に明示的に扱う |
| 修正時だけMirrorやArrayをやめて手作業へ逃げる | **Method Continuity Gate**で、LOCAL修正中は選択済みmethodを維持する |
| 見えている不具合は小さいが、原因は上流の設計にある | **Change Impact Gate**でLOCAL / METHOD / STRUCTURAL / CONTRACTを先に決める |
| 小さな修正を重ねているうちに全体が崩れる | **Global Reassessment**で一度制作全体を見直す |
| 固定renderは良いのに、回して見ると妙に薄い・浮いている | **Exploratory Live GUI Review**で裏側、厚み、接続、detail、material responseまで見る |
| 同じ環境なのに毎回method探索をやり直す | **環境に紐づくDiscovery Cache**で、安全に再利用できる事実だけ使い回す |
| ファイルができた時点で完成扱いする | **Evidence-backed review**で実際の画像を開いて確認する |
| AIが「良さそう」と言ったので完成にする | AI合格と人間承認を分離する |
| レビュー後にファイルが変わる | SHA-256でレビュー済みの正確なバイト列を固定する |
| GUIや外部機能が壊れた | `BROKEN` / `UNKNOWN`を勝手に`UNAVAILABLE`扱いせず、復帰時も新しい明示probeを要求する |
| 長い作業の途中でセッションが切れる | Checkpoint / resumeで検証済み状態から再開する |

全部のループが成功で終わるとは限りません。直せるなら修正へ戻り、方法が悪ければ再選択し、自動で解けない状態ならOwnerへ返します。止まり方まで状態として残すのがBlendSmithの役目です。

## 専用機能を先に、スクラッチは最後に

Blenderに`Mirror`や`Array`、Geometry Nodes、アセットライブラリ、拡張機能があると知っているだけでは足りません。実際の制作で、その場に合うものを選ぶ必要があります。

<p align="center">
  <img src="docs/assets/blendsmith-method-selection.png" alt="BlendSmithのspecialized-first方法選択" width="100%">
</p>

BlendSmithは制作前に作業単位（work unit）へ分けます。さらに各work unitで、既知のmethod familyを**APPLICABLE / NOT_APPLICABLE**のどちらかとして一度は明示的に確認します。

たとえば`symmetry`をAPPLICABLEにしたなら、Method Planには`symmetry`のoperationが必要です。「剣を作る」という大きなoperationの中へ左右対称処理まで埋めて、`Mirror`を検討し忘れる形では通りません。

そのうえで利用可能な方法を調べます。標準設定では次を確認します。

- Blender標準機能
- Geometry Nodes / Node Tool
- アセットライブラリ
- インストール済み拡張機能
- プロジェクト内カタログ
- 設定済みAdapter

既知の候補を無視したまま「見つからなかったこと」にして通すことはありません。必要な探索元や有力な専用方法が`BROKEN` / `UNKNOWN`のままなら、汎用的な作り方へのフォールバックも止めます。

探索結果にはcacheも使えます。ただし、cacheはMethod Selectionそのものの権限にはしません。Core側で鮮度を証明できる範囲だけ再利用し、それ以外のsourceはもう一度確認します。

Method Selection v2では適合度も分けています。`SPECIALIZED + FULL`があるなら原則そちらを優先します。一方、専用methodが`PARTIAL_LOCAL_REFINEMENT`までしか満たせず、汎用methodが`FULL`で満たせる場合は、根拠付きwaiverがあれば汎用methodを選べます。スクラッチは最後です。
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
  -> Method Plan / Production Graph
  -> method familyの確認
  -> Method Selection
  -> Blender production
  -> candidate pin
  -> multi-view evidence
  -> Visual Review
       -> Change Impact Gate
            -> LOCAL      -> Method Continuity -> Fix Plan -> production
            -> METHOD     -> Method Selection
            -> STRUCTURAL -> 上流Graph / Planを更新
            -> CONTRACT   -> 上流Contract / Planを更新
       -> render accepted
            -> Exploratory Live GUI Review
                 -> REVISE -> Change Impact Gate
                 -> PASS
  -> final AI validation
  -> AI_ACCEPTED
  -> OWNER_REVIEW
```

LOCAL修正が続いたときは、次の修正へ入る前にGlobal Reassessmentを挟めます。

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
blendsmith next --project <project>
blendsmith method-hints --project <project> --intent symmetry
blendsmith method-cache --project <project> --intent symmetry
blendsmith method-plan --project <project> --input method_plan.json
blendsmith method-select --project <project> --input method_selection.json
blendsmith candidate-add --project <project> --candidate <scene.blend>
blendsmith evidence-begin --project <project>
blendsmith evidence-submit --project <project> --view front=<front.png>
blendsmith visual-review --project <project> --input visual_review.json
blendsmith change-impact --project <project> --input change_impact.json
blendsmith global-reassess --project <project> --input global_reassessment.json
blendsmith gui-review --project <project> --input live_gui_review.json
blendsmith owner-action-recover --project <project>
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
- **作業分解を曖昧にしない。** 各work unitで既知のmethod familyを一度は明示的に確認する。
- **Production Graphを状態として持つ。** work unitにはrationale、stage、依存関係を持たせ、上流変更時は影響する下流を古い状態として扱う。
- **Specialized first, scratch last.** 要件を満たす専用手段を先に評価する。FULLの汎用methodがPARTIALの専用methodを上回るときだけ、根拠付きwaiverを許す。
- **LOCAL修正でもmethodを勝手に変えない。** Method Continuityで、影響するwork unitの選択済みmethodを維持する。
- **直す前に変更の深さを決める。** LOCAL / METHOD / STRUCTURAL / CONTRACTで戻り先を分ける。
- **局所修正を積み上げ続けない。** 必要ならGlobal Reassessmentで制作全体を見直す。
- **Method PlanからcandidateまでSHAでつなぐ。** candidateはMethod SelectionのSHAを持ち、そのSelectionはMethod PlanのSHAへ結び付く。
- **検証済みPlanは上書きしない。** 上流変更は古いSHAを残したまま新revisionとしてsupersedeする。
- **Evidenceはレビューの実入力。** ファイルが存在するだけでは視覚確認済みにならない。
- **GUIは探索レビューとして使う。** PASSにはorbit、zoom、固定render外の視点、具体的な観察、複数の確認項目を求める。明確なquality gainを見つけたままPASSにはできない。
- **Owner Actionからの復帰にも新しい証拠が要る。** 同じrunへ戻すときは、failureより後の明示的なcapability probeを要求する。
- **Discovery Cacheは範囲を限定する。** 鮮度をCoreで証明できないsourceはcache authorityにしない。
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

現在の公開版は**v0.0.2 — Production Structure**です。

元のreview / repair loopに、作業分解、method familyの事前確認、依存関係を持つProduction Graph、Change Impact、Method Continuity、Global Reassessment、探索型GUI Review、安全なsame-run recovery、範囲を限定したDiscovery Cache、Evidence Profile、`next`による状態確認を加えています。

**v0.0.1**は最初の公開版として残しています。

## ライセンス

Apache License 2.0です。詳細は[LICENSE](LICENSE)を参照してください。
