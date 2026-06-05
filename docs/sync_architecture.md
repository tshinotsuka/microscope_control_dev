# Sync Architecture — 取得側（microscope_control_dev）

```
更新方法:   この 1 ファイルを in-place 更新（dated にしない）。取得系の時刻同期設計の正本＝これ。
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
scope:      同期の設計原則・vDAQ の役割分担・モダリティ別の生成/記録方針・段階計画・オフライン整列。
            個別手順は status.md §3/§3.5・各 SOP に委ねる（実体は status、本 doc は設計の正＝loose coupling）。
related:    status.md / overview.md / vdaq_io_map.yaml / strategy_roadmap.md §3・§5 / trigger_sync.schema.json
```

---

## 0. 原則（1 段落）

**vDAQ＝クロックマスター兼同期ハブ。** 全モダリティを vDAQ の単一クロックドメインに載せ、イベントとデータは
vDAQ が **生成（trigger 出力）** するか **記録（TTL/AI 取り込み）** する。他装置（瞳孔カメラ・EEG/ephys・opto・
トレッドミル・Bpod/Bonsai/pyControl）は **TTL 同期の衛星**で、各自のクロックで動いてよいが、**vDAQ に戻した TTL エッジ**で
オフライン整列する。**タイミング決定的な処理は per-frame ソフトに置かない**（§4・overflow 教訓）。設計系譜は
IBL/Cortexlab（central sync が全 TTL を記録・`bpod2fpga` で offline align）、Moser（撮像が衛星カメラを scan ごとに pre-sync）、
MouseLand（Facemap/DLC は後段解析）。

---

## 1. vDAQ の二役と記録機構

- **生成（generator）**：vDAQ が TTL を出して衛星/装置を駆動する。
  - 例：injector trigger（Waveform Generator → DO）、Frame/Line/Volume clock out（カメラ等を scan で駆動）。
- **記録（recorder）**：vDAQ が入ってくる信号を時刻つきで取り込む。**イベントも連続も Data Recorder に集約**（同一 vDAQ クロック・HDF5・imaging と同 stem `raw/`）。
  - **イベント（注入 t0・刺激マーカ等）→ TTL を Data Recorder の 1 チャネルに記録**：5V TTL を空き AI（injector は `AI7`）に入れて録る（DI 可なら DI）。エッジ＝イベント時刻。**scan モード非依存（galvo / ALS / resonant いずれも同じ）**。
  - **連続信号（behavior・エンコーダ等）→ Data Recorder**（低速 AI）。
  - **Auxiliary Trigger（TIFF へ timestamp）は任意の冗長クロスチェックに格下げ**：ドキュメント上 **resonant モード限定**で timestamp は TIFF ヘッダに書かれる仕様のため、galvo/ALS では真値に使わない（→ §2）。

> 使い分け：**単発イベント＝Aux Trigger（TIFF・resonant 任意）／連続波形・t0・frame_clock＝Data Recorder（HDF5）。** どちらも同一 vDAQ クロック。

---

## 2. 同期の正本（契約・roadmap §3）

- **注入 t0 の正本 = Data Recorder に録った injector TTL のエッジ**（同一 vDAQ クロック・**全 scan モード共通** galvo/ALS/resonant・`AI7`='Legato130_TTL'）。
  - 注入の「**タイミング**」は任意（実験者が frame N / `delaySec` で指定）。「**t0**」はその**実際に立ったエッジの記録値＝解析の時間ゼロ**（kinetics は注入からの経過時間の関数）。
  - 物理到達遅延（チューブ dead volume・ポンプ立上り）は**別途キャリブする定数オフセット**（t0 はあくまでトリガ瞬間。schema では `physical_delay_offset_s`・下流加算・t0 に折り込まない）。
- **recorder-start ≠ frame-0（重要・2026-06-05 galvo 実測）**：Data Recorder の Auto-Start は **frame 1 より前**から録り出すため、recorder 起点と imaging 起点に**非ゼロのオフセット**がある（galvo で head pad **1.975 s**・tail 0.035 s）。
  - → **注入の imaging 対応は `frame_clock` にアンカーする**（galvo/resonant）。**ALS は frame_clock が無い**ので **common acq-start ＋ ALS data-file timing**でアンカー。
  - **recorder-start や common acq-start を真値（frame-0）として使わない**（近似・上記オフセットがある）。
  - **frame rate は frame_clock のフレーム間隔の中央値**から算出する（`n_frames / total_duration` は head/tail 余白で希釈されるため不可）。
- **Aux Trigger（TIFF timestamp）は t0 に使わない／resonant 時の任意クロスチェックのみ**：根拠＝Aux Trigger の timestamp は**現状 resonant 限定で TIFF ヘッダに書かれる**仕様。galvo は要検証・ALS は TIFF を吐かない → t0 は Data Recorder に一本化（モード分岐を作らない）。
- **連続 behavior = Data Recorder HDF5**（同 stem・`raw/`）。Data-Recorder 開始（Auto Start）＋ frame_clock で対応づけ。
- **`frame_clock`/marker は t0「正本」ではなく imaging 対応づけの手段（＝アンカー）**。`frame_log/sample_index` は cross-check。
- **`trigger_sync` schema は draft 済（2026-06-05 galvo・worked example つき）**。実体＝解析 repo の **`trigger_sync.schema.json`**（draft 2020-12・`als_sidecar.schema.json` の兄弟・条件分岐で scan_mode↔anchor 強制）。**3 mode 並走＋behavior ch 確定後に finalize**。反映断片＝`trigger_sync_doc_notes.md`。

---

## 3. モダリティ別マップ（生成/記録・物理線・状態）

| モダリティ | vDAQ の役割 | 物理線 / 機構 | 状態 |
|---|---|---|---|
| **injector（Legato 130）** | 生成→記録 | `D3.2`(WG TTL) → T 分岐 → ①`AI7`(confirmed) = **Data Recorder で TTL 記録（t0 正本・全モード）** ／②`D2.1`(Aux) は resonant 時の任意クロスチェック ／③Legato 本体 | 生成（writeLineToVal）確認済・**t0 を Data Recorder(AI7) で記録・確認 済（galvo 2026-06-05）／ALS・resonant 残** |
| **frame clock（整列アンカー）** | 生成→記録 | Frame clock out → `D0.0` → `AI6` ループバック = **Data Recorder 'frame_clock' 記録** | **galvo 整列クロスチェック・確認済（2026-06-05・200 frame=設定/16.72 Hz）／resonant 残・ALS は frame 無で非適用** |
| **behavior（velocity/lick/reward）** | 記録 | 低速 AI（AI4,5,8+）→ Data Recorder → HDF5 | 方式A・Data Recorder run-config 済・4ch demo 済（実 behavior 配線待ち） |
| imaging line/volume clock | 生成 | Line/Volume clock out → 物理線（衛星トリガ用） | 未使用（Phase 2 で活用） |
| 瞳孔カメラ | 生成（vDAQ がトリガ） | frame/scan clock out → camera trigger in（Moser 流 pre-sync） | Phase 2 |
| EEG / ephys | 記録 | TTL marker → Aux Trigger（イベント）/ Data Recorder DI | Phase 3 |
| opto stim | 生成 and/or 記録 | TTL 出力＋自己 aux 記録（刺激 t を TIFF に） | Phase 3 |
| トレッドミル | 記録 | エンコーダ → AI/counter → Data Recorder | Phase 1/3 |
| Bpod/Bonsai/pyControl（FSM・閉ループ） | 記録（外部 FSM の TTL を vDAQ に戻す） | task events TTL → DI/Aux（IBL `bpod2fpga` 流 offline align） | Phase 4 |

> 物理線の正本は `config/wiring/vdaq_io_map.yaml`（injector `D3.2`/`AI7`・frame_clock `D0.0`/`AI6` は 2026-06-05 confirmed）。

---

## 4. 設計ルール（lessons）

1. **per-frame ソフトを同期経路に置かない**：`frameAcquired` の MATLAB User Function は高フレームレートで
   `Frame queue overflow` を誘発（実測 17/33Hz で UF 有り→overflow）。**イベントは acqModeStart 1 回 or ハードトリガ**で撃つ（§3.5）。
   2026-06-05 galvo 16.7 Hz で acqModeStart 単発（frameAcquired 空）→ overflow 無しを確認。33 Hz overflow は display/保存側と判断（A/B 未）。
2. **イベント＝Aux Trigger（TIFF・resonant 任意）、t0/連続/frame_clock＝Data Recorder（HDF5）**。混ぜない。
3. **1 クロックドメイン**：全ストリームを vDAQ クロックに載せ、別クロック機器は**記録した TTL エッジ**で vDAQ に写像。
4. **loose coupling**：本 doc が同期設計の正本。`status.md` は名前参照（実装状態は status、設計は本 doc）。
5. **取得レート**：frame は現 PC で ~33–50Hz 上限。Track-M の `dt≤MTT/8` は frame 高速化 or **line-scan** で確保（status §2 #3b）。
6. **recorder-start≠frame-0**：Auto-Start は frame 1 前から録る（head pad 非ゼロ）。整列は frame_clock にアンカーし、recorder-start を frame-0 と仮定しない（§2・2026-06-05）。

---

## 4.5 デバイス選定と早期判断（vDAQ-native / Arduino / 別PC・Bpod）

モダリティを増やすたびに、**それを動かすデバイス階層を“参入時に”決める**（後から気づくと配線・取得設計のやり直しになるため早期判断）。安い方から：

| 階層 | 何で | 適する用途 | クロック扱い |
|---|---|---|---|
| **T1: vDAQ-native** | Aux Trigger / Data Recorder / clock out ＋ acqModeStart UF | 単発イベント生成、連続 AI 記録、衛星トリガ。**まずここで足りるか**を見る | 同一 vDAQ クロック（追加整列不要） |
| **T2: Arduino（手元・すぐ使える）** | Arduino/Teensy で TTL 生成・パルス列・カウント・debounce・level-shift | vDAQ-native で足りないが**決定論的 FSM までは要らない**簡単な生成/IO | **自前クロック → 生成 TTL を vDAQ(aux/DI) に戻して記録**（IBL の「カメラ→FPGA」と同型） |
| **T3: Bpod / pyControl（＋別PC）** | 専用リアルタイム FSM、Bonsai/SpikeGLX 等を別PCで | **sub-ms 決定論・閉ループ課題**、または**重い独立キャプチャ**（高 fps 動画・ephys） | 別クロック → task events TTL を vDAQ に戻し offline 整列 |

**Arduino の方針（決定）**：手元にありすぐ使えるので、T1 で足りない簡単な生成/IO は **Arduino を衛星として使う**。ただし
(a) Arduino は Bpod のような**ハードリアルタイム保証はない**（USB-serial 遅延・loop ジッタ）。複雑な閉ループ FSM は T3。
(b) **Arduino が出す TTL は必ず vDAQ に戻して記録**する（Arduino の `millis()` を同期正本にしない＝§0 の単一クロック原則）。

**“早めに判断”するトリガ（モダリティ参入時にこの 2 つを問う）**
1. **別PC が要る？** → その衛星が**重い独立キャプチャ**（高 fps 動画・ephys 等）で、取得PC の CPU/ディスク/USB 帯域と競合するなら別PC（IBL もカメラ/ephys は別マシン）。現 PC の frame 上限 ~33–50Hz の知見とも整合（status §2 #3b）。
2. **Bpod/pyControl が要る？** → タスクが **sub-ms 決定論・閉ループ contingency** を要するなら専用 FSM。**受動・頭部固定・緩いタイミング（現スコープ）なら不要**＝ T1/T2 で足りる。注入のような緩いイベントは T1（acqModeStart＋Data Recorder 記録）で十分。

> 判断の置き場所：本 §4.5（設計の正）。各モダリティの採用階層は §3 マップの「状態」欄に追記していく。

---

## 5. 段階計画

- **Phase 0 — control＋GUI レイヤ（基盤・完了寄り）**：トリガを arm/設定する operator 前面を最小構成で。
  = User Function 骨子（`syncArmStart/syncDisarm.m` の汎用 arm/disarm）＋ Waveform Generator 配線（D3.2/D2.1/AI7・D0.0/AI6 確定）＋ **GUI ワイヤフレーム**（`syncControlPanel.m`）。
- **Phase 1 — 記録の確立（galvo go・いまここ）**：injector（生成→AI7 記録）＋ frame_clock（D0.0→AI6）＋ behavior（Data Recorder）。同期正本・sidecar・オフライン整列を 1 本のテスト録りで確立 → 方式A go/no-go。**galvo 段 go（2026-06-05）／ALS・resonant 残**。
- **Phase 2 — vDAQ が衛星をトリガ**：瞳孔カメラを frame/scan で駆動（Moser 流 pre-sync）。clock out を物理線へ。
- **Phase 3 — 外部イベントを記録**：EEG/ephys・opto・トレッドミルの TTL/AI を vDAQ に集約（Aux/Data Recorder）。
- **Phase 4 — 閉ループ / FSM**：Bpod/Bonsai/pyControl を別 FSM として走らせ、task events の TTL を vDAQ に戻す
  （IBL `bpod2fpga` 流に offline 整列）。**デバイス階層は §4.5**：簡単な生成/IO は Arduino（T2）、sub-ms 決定論・閉ループや重い独立キャプチャは Bpod/pyControl＋別PC（T3）。**参入時に §4.5 の 2 問で早期判断**。

---

## 6. オフライン整列の手順（recipe）

1. 全ストリームは vDAQ クロック共有 → **記録 timestamp で整列**。
2. **注入 t0 = Data Recorder に録った injector TTL のエッジ**。imaging との対応は **`frame_clock` にアンカー**（galvo/resonant・**recorder-start≠frame-0** のため common acq-start は近似）／**ALS は common acq-start＋ALS data-file timing**。behavior（同 HDF5）は同一クロックで揃う。
3. `frame_log` / `sample_index` で cross-check（ずれ検出）。frame rate は frame_clock のフレーム間隔の中央値から。
4. 別クロック衛星（FSM/カメラ自走分）は、**vDAQ に戻した TTL エッジ**を介して vDAQ クロックへ写像。
5. 整列結果は解析側 `trigger_sync`（`trigger_sync.schema.json`・3 mode 後 finalize）に載せる。

---

## 7. 関連

- **実装状態・次手**：`status.md` §3（behavior 入力経路）・§3.5（injector）・§2（Tier 順）・§5（解析申し送り）
- **優先順位の正**：`strategy_roadmap.md` §3（契約・同期正本）・§5（gate）
- **契約 schema**：`trigger_sync.schema.json`（解析 repo・`als_sidecar.schema.json` の兄弟）／反映断片 `trigger_sync_doc_notes.md`
- **I/O 割当**：`config/wiring/vdaq_io_map.yaml`
- **ベンチ手順**：`method_a_e2e_gonogo_sop.md`
- **システム概要**：`overview.md`
- **SOP（順次起こす）**：`sops/behavior_datarecorder_sop.md` / `sops/injector_frametrigger_sop.md`

---

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-05 | **galvo e2e go**。injector t0 を Data Recorder(`AI7`) で記録・確認、frame clock を `D0.0`→`AI6` で記録し整列クロスチェックに使用。決定: **recorder-start≠frame-0**（Auto-Start head pad ~2 s 実測 1.975 s）→ 注入は **frame_clock にアンカー**（galvo/resonant）／**frame rate は median 間隔**。`trigger_sync.schema.json` を draft（§2 参照）。§2 同期正本・§3 injector/frame clock 行と物理線（AI7/D0.0/AI6 confirmed）・§4 lesson 6・§5 Phase1・§6 recipe を更新。 |
| 2026-06-04 | **注入 t0 の正本を Data Recorder の TTL エッジに一本化（全 scan モード共通）**。発見：Aux Trigger の timestamp は docs 上 **resonant 限定・TIFF ヘッダ書き込み**で、galvo は要検証・ALS は TIFF を吐かない → TIFF-aux 依存を外し、**イベント（注入・刺激）も Data Recorder に TTL で記録**（空き AI 経由、DI 可なら DI）。§1 記録機構・§2 同期正本・§3 injector 行・§6 recipe を更新。Aux Trigger は resonant 時の任意クロスチェックに格下げ。t0 概念（タイミングは任意・t0 は実エッジの記録＝時間ゼロ・物理到達遅延は別オフセット）を明記。**契約影響**：roadmap §3 の「注入 t0=TIFF Aux」→「Data Recorder TTL」へ。 |
| 2026-06-04 | §4.5「デバイス選定と早期判断」を追加：階層 T1 vDAQ-native / **T2 Arduino** / T3 Bpod・pyControl＋別PC。**早期判断トリガ 2 問**。Phase 4 に §4.5 参照を付記。 |
| 2026-06-04 | 初版。同期設計の正本として新設。原則・vDAQ の二役・同期正本・モダリティ別マップ・設計ルール・Phase 0–4・整列 recipe を収載。injector は §3.5 から実装例として昇格。 |
