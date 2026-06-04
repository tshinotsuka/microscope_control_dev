# Sync Architecture — 取得側（microscope_control_dev）

```
更新方法:   この 1 ファイルを in-place 更新（dated にしない）。取得系の時刻同期設計の正本＝これ。
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
scope:      同期の設計原則・vDAQ の役割分担・モダリティ別の生成/記録方針・段階計画・オフライン整列。
            個別手順は status.md §3/§3.5・各 SOP に委ねる（実体は status、本 doc は設計の正＝loose coupling）。
related:    status.md / overview.md / vdaq_io_map.yaml / strategy_roadmap.md §3・§5
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
  - **イベント（注入 t0・刺激マーカ等）→ TTL を Data Recorder の 1 チャネルに記録**：5V TTL を空き AI（例 `AI7`）に入れて録る（DI 可なら DI）。エッジ＝イベント時刻。**scan モード非依存（galvo / ALS / resonant いずれも同じ）**。
  - **連続信号（behavior・エンコーダ等）→ Data Recorder**（低速 AI）。
  - **Auxiliary Trigger（TIFF へ timestamp）は任意の冗長クロスチェックに格下げ**：ドキュメント上 **resonant モード限定**で timestamp は TIFF ヘッダに書かれる仕様のため、galvo/ALS では真値に使わない（→ §2）。

> 使い分け：**単発イベント＝Aux Trigger（TIFF）／連続波形＝Data Recorder（HDF5）。** どちらも同一 vDAQ クロック。

---

## 2. 同期の正本（契約・roadmap §3）

- **注入 t0 の正本 = Data Recorder に録った injector TTL のエッジ**（同一 vDAQ クロック・**全 scan モード共通** galvo/ALS/resonant）。
  - 注入の「**タイミング**」は任意（実験者が frame N / `delaySec` で指定。例 1000 フレーム目）。「**t0**」はその**実際に立ったエッジの記録値＝解析の時間ゼロ**（kinetics は注入からの経過時間の関数）。
  - 物理到達遅延（チューブ dead volume・ポンプ立上り）は**別途キャリブレする定数オフセット**（t0 はあくまでトリガ瞬間）。
- **Aux Trigger（TIFF timestamp）は t0 に使わない／resonant 時の任意クロスチェックのみ**：根拠＝Aux Trigger の timestamp は**現状 resonant 限定で TIFF ヘッダに書かれる**仕様（docs.scanimage.org/Concepts/Triggers/Auxiliary+Trigger.html）。galvo は要検証・ALS は TIFF を吐かない → t0 は Data Recorder に一本化（モード分岐を作らない）。
- **連続 behavior = Data Recorder HDF5**（同 stem・`raw/`）。Data-Recorder 開始 trigger か 1ch frame clock/marker で対応づけ。
- **`frame_clock`/marker は「正本」ではなく対応づけの一手段に格下げ**。`frame_log/sample_index` は cross-check。
- `trigger_sync` schema は **方式A go/no-go 後**に取得側で確定（実 HDF5 レイアウト＋aux timestamp 形式が判明してから）。

---

## 3. モダリティ別マップ（生成/記録・物理線・状態）

| モダリティ | vDAQ の役割 | 物理線 / 機構 | 状態 |
|---|---|---|---|
| **injector（Legato 130）** | 生成→記録 | `D3.2`(WG TTL) → T 分岐 → ①空き AI（例 `AI7`）= **Data Recorder で TTL 記録（t0 正本・全モード）** ／②`D2.1`(Aux) は resonant 時の任意クロスチェック ／③Legato 本体 | 生成（writeLineToVal）確認済・**t0 を Data Recorder で録る検証待ち**（§3.5） |
| **behavior（velocity/lick/reward）** | 記録 | 低速 AI（AI4+）→ Data Recorder → HDF5 | 方式A・Data Recorder 実装待ち |
| imaging frame/line/volume clock | 生成 | Frame/Line/Volume clock out → 物理線（衛星トリガ用） | 未使用（Phase 2 で活用） |
| 瞳孔カメラ | 生成（vDAQ がトリガ） | frame/scan clock out → camera trigger in（Moser 流 pre-sync） | Phase 2 |
| EEG / ephys | 記録 | TTL marker → Aux Trigger（イベント）/ Data Recorder DI | Phase 3 |
| opto stim | 生成 and/or 記録 | TTL 出力＋自己 aux 記録（刺激 t を TIFF に） | Phase 3 |
| トレッドミル | 記録 | エンコーダ → AI/counter → Data Recorder | Phase 1/3 |
| Bpod/Bonsai/pyControl（FSM・閉ループ） | 記録（外部 FSM の TTL を vDAQ に戻す） | task events TTL → DI/Aux（IBL `bpod2fpga` 流 offline align） | Phase 4 |

> 物理線の正本は `config/wiring/vdaq_io_map.yaml`（injector の D3.2/D2.1 は confirmed）。

---

## 4. 設計ルール（lessons）

1. **per-frame ソフトを同期経路に置かない**：`frameAcquired` の MATLAB User Function は高フレームレートで
   `Frame queue overflow` を誘発（実測 17/33Hz で UF 有り→overflow）。**イベントは acqModeStart 1 回 or ハードトリガ**で撃つ（§3.5）。
2. **イベント＝Aux Trigger（TIFF）、連続＝Data Recorder（HDF5）**。混ぜない。
3. **1 クロックドメイン**：全ストリームを vDAQ クロックに載せ、別クロック機器は**記録した TTL エッジ**で vDAQ に写像。
4. **loose coupling**：本 doc が同期設計の正本。`status.md` は名前参照（実装状態は status、設計は本 doc）。
5. **取得レート**：frame は現 PC で ~33–50Hz 上限。Track-M の `dt≤MTT/8` は frame 高速化 or **line-scan** で確保（status §2 #3b）。

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
2. **Bpod/pyControl が要る？** → タスクが **sub-ms 決定論・閉ループ contingency** を要するなら専用 FSM。**受動・頭部固定・緩いタイミング（現スコープ）なら不要**＝ T1/T2 で足りる。注入のような緩いイベントは T1（acqModeStart＋aux 記録）で十分。

> 判断の置き場所：本 §4.5（設計の正）。各モダリティの採用階層は §3 マップの「状態」欄に追記していく。

---

## 5. 段階計画

- **Phase 0 — control＋GUI レイヤ（基盤・次の一手）**：トリガを arm/設定する operator 前面を最小構成で立てる。
  = User Function 骨子（`legatoInjectStart/Stop.m` を汎用 arm/disarm に整理）＋ Waveform Generator 配線（D3.2/D2.1 確定済）＋ **GUI ワイヤフレーム**（モダリティ選択・delay/pulse 設定・arm 状態表示）。実体設計は別途。
- **Phase 1 — 記録の確立（いまここ）**：injector（生成→aux 記録）＋ behavior（Data Recorder）。同期正本・sidecar・オフライン整列を 1 本のテスト録りで確立 → 方式A go/no-go。
- **Phase 2 — vDAQ が衛星をトリガ**：瞳孔カメラを frame/scan で駆動（Moser 流 pre-sync）。clock out を物理線へ。
- **Phase 3 — 外部イベントを記録**：EEG/ephys・opto・トレッドミルの TTL/AI を vDAQ に集約（Aux/Data Recorder）。
- **Phase 4 — 閉ループ / FSM**：Bpod/Bonsai/pyControl を別 FSM として走らせ、task events の TTL を vDAQ に戻す
  （高速閉ループが要る場合。IBL `bpod2fpga` 流に offline 整列）。**デバイス階層は §4.5**：簡単な生成/IO は Arduino（T2）、sub-ms 決定論・閉ループや重い独立キャプチャは Bpod/pyControl＋別PC（T3）。**参入時に §4.5 の 2 問で早期判断**。

---

## 6. オフライン整列の手順（recipe）

1. 全ストリームは vDAQ クロック共有 → **記録 timestamp で整列**。
2. **注入 t0 = Data Recorder に録った injector TTL のエッジ** を基準に、behavior（同 HDF5）・imaging frame / ALS cycle を揃える（共通 acq-start ＋ vDAQ クロック）。
3. `frame_log` / `sample_index` で cross-check（ずれ検出）。
4. 別クロック衛星（FSM/カメラ自走分）は、**vDAQ に戻した TTL エッジ**を介して vDAQ クロックへ写像。
5. 整列結果は解析側 `trigger_sync`（方式A go 後に確定）に載せる。

---

## 7. 関連

- **実装状態・次手**：`status.md` §3（behavior 入力経路）・§3.5（injector フレームトリガ实装）・§2（Tier 順）
- **優先順位の正**：`strategy_roadmap.md` §3（契約・同期正本）・§5（gate）
- **I/O 割当**：`config/wiring/vdaq_io_map.yaml`
- **システム概要**：`overview.md`
- **SOP（順次起こす）**：`sops/behavior_datarecorder_sop.md` / `sops/injector_frametrigger_sop.md`

---

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-04 | **注入 t0 の正本を Data Recorder の TTL エッジに一本化（全 scan モード共通）**。発見：Aux Trigger の timestamp は docs 上 **resonant 限定・TIFF ヘッダ書き込み**で、galvo は要検証・ALS は TIFF を吐かない → TIFF-aux 依存を外し、**イベント（注入・刺激）も Data Recorder に TTL で記録**（空き AI 経由、DI 可なら DI）。§1 記録機構・§2 同期正本・§3 injector 行・§6 recipe を更新。Aux Trigger は resonant 時の任意クロスチェックに格下げ。t0 概念（タイミングは任意・t0 は実エッジの記録＝時間ゼロ・物理到達遅延は別オフセット）を明記。**契約影響**：roadmap §3 の「注入 t0=TIFF Aux」→「Data Recorder TTL」へ（4 ファイル同期・解析側 coordinate）。 |
| 2026-06-04 | §4.5「デバイス選定と早期判断」を追加：階層 T1 vDAQ-native / **T2 Arduino（手元・すぐ使える・生成 TTL は vDAQ に戻して記録・Bpod 級の決定論は無し）** / T3 Bpod・pyControl＋別PC。**早期判断トリガ 2 問**（別PC＝重い独立キャプチャで取得PC と競合か／Bpod＝sub-ms 決定論・閉ループか。受動・緩いタイミングの現スコープは T1/T2 で足りる）。Phase 4 に §4.5 参照を付記。 |
| 2026-06-04 | 初版。同期設計の正本として新設。原則（vDAQ マスター＋衛星 TTL＋オフライン整列）・vDAQ の二役（生成/記録）・同期正本（注入 t0 = TIFF aux timestamp）・モダリティ別マップ・設計ルール（per-frame ソフト禁止等）・Phase 0–4・整列 recipe を収載。injector は §3.5 から実装例として昇格。 |
