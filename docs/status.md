# Status — 取得側（microscope_control_dev）

```
更新方法:   この 1 ファイルを in-place で更新する（日付つきで増やさない）。最新状態は常にこれ。
            鮮度は末尾「改訂履歴」と `git log -1 -- docs/status.md`。
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md
                （§6 によりここが「優先順位の単一の正」。本 doc はそこへリンクする側）
scope:      取得側の状態・次手・取得側 reference。優先順位 roadmap ではない。
```

取得側 project（vDAQ / ScanImage / FastZ / ALS / behavior / injector / resonant）の現状と次手。
**実体（コードレビュー・装置・設計判断）は本 doc に閉じ、roadmap には決定事項だけを反映する**（結合は緩く保つ）。

---

## 0. いまの一手

behavior 入力経路は **方式A（vDAQ Data Recorder + Auxiliary Trigger）に決定**（§3）。
injector フレームトリガは **acqModeStart 方式に確定**（per-frame User Function は廃止＝§3.5）。配線・WG 出力・Aux ループバックはベンチ確認済、`acqModeStart` 版 UF 実装済、**end-to-end テストが次の一手**。
これと同じ **方式A test 録り**で「**実 HDF5 レイアウト＋ TIFF aux-trigger timestamp の形式**」を確定する。これが
**解析側 `trigger_sync` schema と Track-M 実データ取得を gate する Tier 0**（roadmap §4 Phase 2 / §5 gate 2・3）。判断軸は roadmap §1 の **可逆性 × コスト**。

---

## 1. status スナップショット

| 項目 | 状態 | メモ |
|---|---|---|
| vDAQ + ScanImage 稼働 | ☑ | Phase 1 done（`overview.md`） |
| ALS 取得 | ☑ | loader 検証は §2 Tier1 #4（解析側 Track-W B と同一タスク・☐）。**Optimize Waveform はベンダーバグ(MBF 25850)で command 不可 → `.scnnr.dat` 実位置が真値 → 常時記録**（§2 Tier0 #3） |
| **behavior 入力経路** | ◐ | **方式A 決定**（Data Recorder + Aux Trigger・同一クロック）。方式B（`.m`+NI）は fallback。Data Recorder 実装・検証は未（§2-0） |
| **injector 同期（フレームトリガ）** | ◐ | **WG「Trig Legato130」(D3.2) ＋ Aux Trigger(D2.1) 配線・出力確認済**（writeLineToVal で ~5V）。**acqModeStart 方式の UF 実装済**（`legatoInjectStart/Stop.m`・per-frame UF 廃止）。**残: end-to-end テスト**（galvo mode で aux timestamp が TIFF に載るか・overflow 無し）。实体＝§3.5 |
| 同期の正本 | ◐ | 方式A で大幅簡素化。injection t0 = **TIFF Aux-Trigger timestamp**（同一 vDAQ クロック）。連続 behavior は Data Recorder HDF5（同 stem・`raw/`）。`frame_clock`/marker は対応づけの一手段に格下げ（§3） |
| **取得レート上限（Track-M gate ②）** | ◐ | **frame は現 PC で ~33–50 Hz が上限**（64 Hz は UF 無しでも `Frame queue overflow`）。Track-M の `dt ≤ MTT/8` 確保には frame 高速化 or **line-scan** が要（§2 Tier0/1・§3.5） |
| behavior sidecar（schema/generator） | ◐ | schema は有効。generator は **Data Recorder の HDF5 レイアウト＋ TIFF aux timestamp** へ再ターゲット要（§2-2・方式A go 後） |
| FastZ | ◐ | 契約への載せ方が未（Tier 2） |
| resonant | ☐ | `scanner_type` は metadata 駆動・準備済、フル統合は将来（Tier 2） |
| repo 構成 | ☑ | `docs/sops/config/src/schemas/examples` 配置・push 済 |

---

## 2. 次手（Tier 順）

### Tier 0 — in vivo（不可逆取得）の前に閉じる
0. **方式A を実装・検証（決定済・最優先）**
   - `config/wiring/vdaq_io_map.yaml` に vDAQ 低速 AI / DI 割当を確定（velocity/lick 等＝AI、injector＝DI→Aux Trigger）。
     **injector 系は確定済**：`injector_trigger = D3.2`（WG 出力）、`injector_aux = D2.1`（Aux Trigger 1）→ proposed から **confirmed** に更新。
   - ScanImage **Resource Configuration** に **Data Recorder** を追加し、behavior AI 信号を登録（HDF5 出力）。
   - injector TTL を **Auxiliary Trigger** に接続（**済**：D3.2→T 分岐→D2.1）。同時記録 TIFF に timestamp が載るかを §3.5 のテストで確認。
   - テスト 1 本録って **Data Recorder の HDF5 レイアウト**と **TIFF の aux-trigger timestamp** の実物を確認 → 解析側 `trigger_sync` schema の確定材料。
1. **同期の正本を確定し検証**（方式A で簡素化）
   - 同一 vDAQ クロック。**injection は Aux Trigger で frame に揃って TIFF に載る**ので別同期不要。
   - 連続 behavior は Data Recorder を **imaging 開始 trigger で start**、または **frame clock/marker を 1ch 記録**して対応づけ（`frame_clock` は正本でなく対応づけ手段）。
   - テストで frame ↔ behavior ↔ injection 対応が想定どおりかを確認。
2. **behavior / injector を契約に載せる**
   - Data Recorder の HDF5 を ScanImage GRAB と**同 stem・`raw/`** へ。
   - **behavior sidecar** を **Data Recorder の HDF5 レイアウト＋ TIFF aux-trigger timestamp** 向けに再ターゲット
     （schema＝契約は流用、`make_behavior_sidecar.py` の入力側を差し替え）。`trigger_sync` は Aux Trigger timestamp を正本に。
   - **チャネル命名**（generate_metadata / 手入力ヒント）：**Ch0/1/3 = PMT2100、Ch2 = 自作フォトダイオード（SRS 検出系）** → `channels[].name` の Ch2 は `srs`/`od`/`water`/`oh` 系で意味付け（roadmap §7）。
   - **Track-M（MTT/CTH）は注入 t0 必須** → 方式A の aux timestamp で満たす。
3. **SI metadata 自動保存の契約適合確認**（logFileStem SOP〔`sops/`〕、ALS 3 ファイル＋`scnnr`、acq/scan_mode は metadata）＝ gate 条件 2。
   - **`.scnnr.dat`（scnnr feedback）を常時記録**：Optimize Waveform がベンダーバグ(MBF 25850)で command 不可のため、**`.scnnr.dat` の実位置が真値**（ALS の幾何復元の前提）。SOP に明記。

### Tier 0/1 — Track-M 実データの取得側 gate（②）
3b. **高速取得（`dt ≤ MTT/8`・line-scan）の確保（Track-M 実データの前提）**
   - phantom 実測 floor：皮質 MTT~0.8s → **dt ≲ 0.1s**。**1 Hz フレームは Track-M 不適**（dt=0.93s で MTT −94%・回収不能）。
   - 現状の発見：**frame は現 PC で ~33–50 Hz 上限**（64 Hz は overflow）。33 Hz なら dt≈0.03s で MTT≳0.24s は満たすが、
     **安全側は line-scan**（cf. Gutiérrez-Jiménez 2016 ~150 Hz line）。
   - ACTION：① frame の持続可能な最大レートを実測（表示 ch / 保存 ch / pixels-line を削って上限を上げる）、
     ② Track-M 用に **line-scan の取得経路**（ALS 既存資産と接続）を確保。これが満たせない取得は解析側 cell24 guard で `undersampled` flag が立つ（§4.5）。

### Tier 1 — 並行・低リスク
4. **ALS loader を test データで検証（do once・取得側に loader が居る／解析側と二重計上しない）**＝解析側 Track-W B と同一タスク。
   - offset の pre/post を MATLAB `readLineScanDataFiles` と **1 acquisition 突合**。
   - `bidirectional=true` の scan 方向交互を確認してから cycle 平均。
   - feedback 補間：PMT と feedback はレート **×12.5 差**（5000 vs 400 samp/cycle）→ feedback を PMT グリッドに upsample。
   - done は「取得側 ALS SOP（`.scnnr.dat` 必須・bidirectional・waveform 最適化バグ回避）の検証」と「機会的 in vivo ALS の最低 gate」を兼ねる。
5. **クラッシュ耐性**：方式A では Data Recorder 任せ（SI 側）。自作 `.m`（fallback）を使う場合のみ `onCleanup` finalize ＋ frame_log flush が要る。
6. **DAQ API 方針**：方式A では NI session 不使用 → moot。方式B に落ちた場合のみ `daq.createSession('ni')`（レガシー）の据え置き/移行を判断。

### Tier 2 — 将来 capability
7. **FastZ** を契約に（ALS scanfields の `zs`。volume framing を metadata で捕捉）。
8. **resonant** フル統合（`scanner_type` は既に metadata 駆動）。

---

## 3. behavior 入力経路の決定（实体）

**決定: 方式A（vDAQ Data Recorder + Auxiliary Trigger）を採用・試行。方式B は fallback。**

- **方式A**：behavior/aux は vDAQ 低速アナログ入力を ScanImage の **Data Recorder** で HDF5 記録
  （docs.scanimage.org/Basic+Features/Data+Recorder.html・500 Hz–500 kHz、信号名＝HDF5 dataset 名、任意のデジタル trigger 可）。
  injector TTL は **Auxiliary Trigger** に入れて同時記録 TIFF に timestamp
  （docs.scanimage.org/Concepts/Triggers/Auxiliary+Trigger.html。SI は刺激トリガを aux 入力に共有して TIFF に
  timestamp する運用を推奨。debounce 遅延あり・1 frame 登録上限 1000／推奨 ~10、注入 on/off なら余裕）。
- **採用理由**：同一 vDAQ クロック・SI ネイティブ・追加 HW 不要・**注入 t0 が frame に揃って TIFF に直接載る**。
- **fallback（方式B）**：`Dev1` 別 NI ボード ＋ `BehaviorAcquisition.m`（`daq.createSession('ni')`）＋ `frame_clock` TTL bridge。
  方式A が要件を満たさないときのみ。`src/matlab/BehaviorAcquisition.m` は**消さず残す**。
- 旧 README #2 の「方式A 同一クロック」は意図として正しかった（コードが方式B に分岐していただけ）。

### 3.5 injector フレームトリガ实装（确定 2026-06-04・实体）

**結論：vDAQ がトリガを生成し aux で記録、ソフトは per-frame ループから外す（acqModeStart 1 回）。** roadmap の
「vDAQ＝クロックマスター兼同期ハブ／衛星は TTL 同期／オフライン整列」原則に一致。injector はその第一例。

- **ハードウェア**
  - WG **「Trig Legato130」**＝ `dabs.generic.WaveformGenerator`、**Control Port `/vDAQ0/D3.2`**（Digital, 5V TTL）。
  - **D2.1 = Aux Trigger 1**（Resource Config に `/vDAQ0/D2.1 <Trig Legato130>` で登録）。D3.2 出力を **BNC T 分岐**して D2.1（aux）と Legato 本体へ。共通グランドは BNC シールド。
  - 配線・出力ともベンチ確認済（**DC 結合**オシロで ~5V。AC 結合だと静的レベルが見えないので注意）。io_map の D3.2/D2.1 は **confirmed**。
- **パルス駆動**：`hWG.writeLineToVal(1)` / `writeLineToVal(0)`（**数値**。logical は不可）。
  ハンドル取得は `dabs.resources.ResourceStore().filterByName('Trig Legato130')`。
  - `startTask`（finite 波形）は **task は走るがライン出力が出ない**（emit せず）→ **不採用**。パルスは writeLineToVal で出す。
- **発火ロジック（採用）**：**`acqModeStart` User Function（取得開始時に 1 回だけ）** が単発タイマで遅延（`delaySec` または `targetFrame/scanFrameRate`）→ `writeLineToVal(1)`→`pulseSec` 後 `writeLineToVal(0)`。
  `acqAbort`/`acqDone` UF が保留タイマを消してライン強制 low（撃ちっぱなし防止）。
  - **per-frame の `frameAcquired` UF は廃止**：高フレームレートで `Frame queue overflow` を誘発（**実測：17/33 Hz は UF 無しなら完走、UF を入れると overflow**）。MATLAB を per-frame ループに置く設計は高速撮像と非互換。
  - acqModeStart 方式は per-frame 処理ゼロ → **撮像自体が回るレートなら overflow しない**。注入 t0 の精度は host タイマ依存だが、**実エッジは D2.1 aux が FPGA timestamp で記録**するのでオフライン整列は厳密（注入の緩いタイミングに十分）。
- **ファイル**：`legatoInjectStart.m`（acqModeStart）、`legatoInjectStop.m`（acqAbort/acqDone）。
  **deprecated**：`legatoFrameTrigger.m` / `legatoFrameReset.m`（per-frame 方式）。
- **取得レート上限の発見**：**64 Hz は UF 無しでも overflow、~33–50 Hz が現 PC 上限**（表示・保存・ディスク律速＝トリガとは別問題）。Track-M の `dt≤MTT/8` に直結（§2 Tier0/1 #3b）。
- **残テスト**：①≤33 Hz で acqModeStart UF が overflow 無く遅延後に単発発火、② **galvo mode で aux timestamp が TIFF/metadata に載る**こと（resonant 限定でないこと）、③ Legato 実機のトリガモード（edge/Trigger 推奨）と実注入の確認。

- 補足（解消済）：旧 §3 の「`onFrameAcquired` の `fn = frameAcqFcnDecimationFactor * frameCount` は decimation 次第でずれ得る・実機検証要」は、**per-frame UF を使わない方針で moot**（acqModeStart 1 回方式に移行したため frame カウント依存が消えた）。

---

## 4. → 解析チャットへ持っていく提案（roadmap 反映・**もんでから更新**）

> このセクションだけ解析チャットに貼り、roadmap に**もんでから**反映する。实体（§2 / §3 / §3.5）は本 doc に残す。
> roadmap は 2026-06-04 改訂で解析側レビュー（`acq_review_for_roadmap_20260604.md`）を §2/§3/§5/§7 に取り込み済。本回は**取得側ベンチ進捗の同期**が主。

- **§2 取得側 status ミラー**を更新：injector 同期行を「**WG(D3.2)+Aux(D2.1) 配線・出力確認済・acqModeStart UF 実装済・end-to-end test 待ち**」に。取得レート上限（frame ~33–50 Hz・64 Hz overflow）を 1 行追記（Track-M gate ② に効く）。
- **§4 Phase 2 Tier 0**：injector aux 経路は **配線・WG 出力確認済**（残＝aux timestamp が TIFF に載るかの実機検証）。`trigger_sync` schema は方式A go/no-go 後に取得側で確定、で据え置き。
- **§5 gate 3 / §必要実データ（Track-M）**：**② `dt≤MTT/8`** に対し取得側の現実＝「frame は ~33–50 Hz 上限・安全側は line-scan」を註記（line-scan 経路の確保が Track-M 実データの取得側 gate）。
- **§3 / §7 契約注記の確認（変更なし・honor）**：注入 t0 正本 = TIFF Aux-Trigger、behavior = Data Recorder HDF5 同 stem、`frame_clock` 格下げ／file_naming の CSV sidecar 例は go 後に HDF5+aux-embedded へ更新／Ch2 = SRS（自作 PD）の channel naming ヒント。
- **契約 v3 凍結の遵守**：片側変更禁止。変更時は **4 ファイル同期**（`file_naming.md` + `metadata_schema.md` + `generate_metadata.py` + 取得側 handoff）。取得側からは現状 schema 変更提案なし（方式A go 後に `trigger_sync` を追加する見込み）。
- **命名 / NAS 構造**：dev/test の project_id は **`2026_microscope_control_dev`** で確定済（前回反映）。解析側 `nas_structure.md` の index に dev project_id が並ぶことを確認。
- 改訂履歴に 1 行。

---

## 4.5 解析側の現在地（取得側が前提にできる・ミラー）

> 正本は解析側 roadmap §2/§4/§5（最終同期 2026-06-04）。drift したら roadmap に合わせる。

- **Track-M（MTT/CTH・優先度最高）**：transport-function の **digital phantom gate PASS**（2026-06-03）＋ **cell24 under-sampling guard 適用済**（2026-06-04・self-test green）。漏出系 M0/M1/M2・Tofts・OEF_max は現物未実装で**対象外確定**。
  **実データ待ちは 2 条件のみ**：**[① 方式A 検証 → 注入 t0 が TIFF Aux-Trigger に載る] AND [② `dt ≤ MTT/8` の高速取得]**。②を満たさない取得は cell24 guard が実行時に `undersampled` flag を立てる。
- **Track-W（water transport）**：kymograph self-test green（径は真値回収）。**残は ALS loader 検証**（＝§2 Tier1 #4 の共有タスク・loader は取得側に居る）。
- **基盤**：canonical env **`ivwib`**（`pyproject.toml` = 依存の正）、作図 **`figstyle_tshino v0.1.0` を tag 作成・pin 済**。
- 詳細の正は解析側 `docs/handoff/acq_review_for_roadmap_20260604.md` ＋ roadmap §2/§3/§5/§7。

---

## 5. 次セッション（実機込み）の段取り（＝戦略）

**目標: 方式A を実機で end-to-end 実装・検証し、契約どおりの behavior + imaging + injection テスト 1 本を出し、
方式A の go / no-go を決める。** 各ステップに通過ゲート。

1. **配線確定 → `vdaq_io_map.yaml` 確定**：実 breakout の AI / DI を確認して port を埋め commit。
   injector（D3.2/D2.1）は confirmed 反映。〔ゲート: io_map が実配線と一致〕
2. **Data Recorder セットアップ**：Resource Config に Data Recorder を追加、低速 AI 信号を登録、sample rate 設定 →
   単体テスト録り。〔ゲート: HDF5 が出て信号が入る〕
3. **injector フレームトリガ（acqModeStart 方式）の end-to-end テスト**（§3.5）：
   `legatoInjectStart`→acqModeStart、`legatoInjectStop`→acqAbort/acqDone を登録、旧 per-frame UF を外す。
   base に `delaySec`（=注入までの baseline、= targetFrame/frameRate）と `pulseSec` を設定。
   **≤33 Hz で Grab** → overflow 無し＋遅延後に単発パルス＋**TIFF/metadata に aux timestamp**（galvo mode で）。
   〔ゲート: overflow 無し ＆ TIFF に注入 timestamp〕
4. **同期検証**：imaging + Data Recorder + Aux Trigger を 1 本同時録り。start を揃え、
   frame ↔ behavior ↔ injection の対応を確認。〔ゲート: 対応が想定どおり〕
5. **契約適合**：logFileStem で sub/ses/cond/run を入れ、同 stem・`raw/` に出るか、metadata（Ch2=SRS 含む）が契約どおりか、`.scnnr.dat` が出るかを確認。
   〔ゲート: gate 条件 2〕
6. **sidecar 再ターゲット**：実 HDF5 レイアウト＋ TIFF aux timestamp が判明 → `make_behavior_sidecar.py` の
   入力を差し替え、テスト acquisition で sidecar 生成 → `behavior_sidecar.schema.json` で validate。
   〔ゲート: sidecar が schema 通過〕→ これで解析側 `trigger_sync` schema が確定できる。
7. **go / no-go**：sample rate・同期精度・連続記録の安定性で方式A が要件を満たすか判定。
   だめなら方式B（`BehaviorAcquisition.m` + NI）へ切替（fallback は残してある）。

**Track-M レート（並行）**：frame の持続可能最大レートを実測（表示/保存/pixels-line を削る）＋ Track-M 用 line-scan 経路の確保（§2 #3b）。

**判断 / フォールバック**：Data Recorder が frame と揃わない → frame marker を 1ch 録る or 方式B。
sample rate / 連続安定性 不足 → 方式B。injector aux が galvo mode で TIFF に載らない → aux 設定/モードを再検討。

**並行（机でも可）**：ALS loader 検証（§2 Tier1 #4・test データがあれば）／ README #2 の残り
（設計根拠・HDF5 構造・behavior troubleshooting）を**方式A 確定後**に `overview.md` / `troubleshooting.md` へ救出。

**セッション後**：確定手順から `sops/behavior_datarecorder_sop.md` ＋ `sops/injector_frametrigger_sop.md` を起こし、`status.md` を更新
（go なら behavior 入力経路と injector 同期を ☑、§3 は fallback 注記だけ残す）。

---

## 6. 関連ドキュメント

- **roadmap（優先順位の正）**：`in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- **解析側レビュー（本同期の元）**：`in_vivo_water_imaging_brain/docs/handoff/acq_review_for_roadmap_20260604.md`
- **ALS 形式 / loader API の正本**：`src/python/als_loader.py`（旧 `HANDOFF.md` は廃止・救出済）
- **既知の問題（ベンダー波形バグ等）**：`docs/troubleshooting.md`（Optimize Waveform = MBF 25850）
- **システム概要 / 設計**：`docs/overview.md`
- **I/O 割当**：`config/wiring/vdaq_io_map.yaml`（injector: D3.2/D2.1 confirmed）
- **injector トリガ UF**：`legatoInjectStart.m` / `legatoInjectStop.m`（deprecated: `legatoFrameTrigger.m`/`legatoFrameReset.m`）
- **ScanImage 参照**：Data Recorder / Auxiliary Trigger（docs.scanimage.org）
- **作図標準**：`handoff_figstyle_tshino_20260603.md`

---

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-04 | **injector フレームトリガを acqModeStart 方式に確定（§3.5 新設）**。WG「Trig Legato130」(`/vDAQ0/D3.2`, Digital)＋Aux Trigger(`D2.1`) 配線・出力をベンチ確認（writeLineToVal で ~5V／DC 結合で観測）。パルスは `writeLineToVal(1/0)`（数値・logical 不可）、`startTask` は出力せず不採用。**per-frame `frameAcquired` UF は廃止**（高レート overflow・実測 17/33Hz は UF 無しなら完走/UF で overflow）→ `acqModeStart` 1 回方式（`legatoInjectStart/Stop.m`、`legatoFrameTrigger/Reset.m` deprecated）。**取得レート上限の発見**：64Hz は UF 無しでも overflow・~33–50Hz が現 PC 上限（Track-M gate ② `dt≤MTT/8` に直結 → line-scan 検討を §2 #3b 追加）。§3 の frameAcqFcnDecimationFactor 註は moot 化。§1 表・§2 Tier0/§4/§5 を同期。§4.5「解析側の現在地（ミラー）」追加。解析側 gate を取得側 ACTION として明示（Ch2=SRS 命名・`.scnnr.dat` 常時記録・ALS loader = Tier1 #4／二重計上回避・v3 凍結 4 ファイル同期）。 |
| 2026-06-04 | dev/test の project_id を **`2026_microscope_control_dev`** に確定（`<YYYY>_<theme>` 準拠、dev データも NAS に上げる方針）。取得側 SOP（`scanimage_logfilestem_sop.md`）反映済み・併せて `file_naming.md` v3 と同期（`100d2o`→`d2oiv`／`egfp-slice`→`qc`／`run-` 規則・dangling 参照修正）、`overview.md` を status と同期。§4 に解析側への持ち込み項目（nas_structure index 同期）を追加。 |
| 2026-06-03 | §5「次セッション（実機込み）の段取り」を追加（実機での方式A 実装 → 検証 → go/no-go の順序とゲート、フォールバック、並行・セッション後タスク）。 |
| 2026-06-03 | behavior 入力経路を **方式A（vDAQ Data Recorder + Auxiliary Trigger）に決定**（§3）。ScanImage が低速 AI を Data Recorder で HDF5 記録、injector TTL を Aux Trigger で TIFF に timestamp できることを確認（docs.scanimage.org）。§2 を方式A 実装手順に、§1 を反映。`BehaviorAcquisition.m`+NI は方式B fallback として保持。 |
| 2026-06-03 | living 化（dated handoff → `status.md`）。§3 を「方式B 断定」から入力経路 fork へ訂正。behavior sidecar/injector・repo 構成を反映。`supersedes` 機構は廃止。ALS 形式の正本を `als_loader.py`、ベンダーバグを `troubleshooting.md` に委譲。 |
