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
次は **方式A を実装・検証して取得物を契約に載せ、同期の正本を確定し、不可逆な in vivo 取得の gate を閉じる**
（roadmap **Phase 2 ＋ gate 条件 2**）。判断軸は roadmap §1 の **可逆性 × コスト**。

---

## 1. status スナップショット

| 項目 | 状態 | メモ |
|---|---|---|
| vDAQ + ScanImage 稼働 | ☑ | Phase 1 done（`overview.md`） |
| ALS 取得 | ☑ | loader 検証は解析側 Track-W B（☐） |
| **behavior 入力経路** | ◐ | **方式A 決定**（Data Recorder + Aux Trigger・同一クロック）。方式B（`.m`+NI）は fallback。実装・検証は未（§2-0） |
| 同期の正本 | ◐ | 方式A で大幅簡素化。injection は Aux Trigger で TIFF に直接 timestamp、連続は Data Recorder + 開始 trigger / frame marker（§2-1） |
| injector 同期 | ◐ | TTL on/off → **Aux Trigger**（TIFF へ frame 揃い timestamp）。配線・Resource Config は未 |
| behavior sidecar（schema/generator） | ◐ | schema は有効。generator は **Data Recorder の HDF5 レイアウト＋ TIFF aux timestamp** へ再ターゲット要（§2-2） |
| FastZ | ◐ | 契約への載せ方が未（Tier 2） |
| resonant | ☐ | `scanner_type` は metadata 駆動・準備済、フル統合は将来（Tier 2） |
| repo 構成 | ☑ | `docs/sops/config/src/schemas/examples` 配置・push 済 |

---

## 2. 次手（Tier 順）

### Tier 0 — in vivo（不可逆取得）の前に閉じる
0. **方式A を実装・検証（決定済・最優先）**
   - `config/wiring/vdaq_io_map.yaml` に vDAQ 低速 AI / DI 割当を確定（velocity/lick 等＝AI、injector＝DI→Aux Trigger）。
   - ScanImage **Resource Configuration** に **Data Recorder** を追加し、behavior AI 信号を登録（HDF5 出力）。
   - injector TTL を **Auxiliary Trigger** に接続（同時記録 TIFF に timestamp）。
   - テスト 1 本録って **Data Recorder の HDF5 レイアウト**と **TIFF の aux-trigger timestamp** の実物を確認。
1. **同期の正本を確定し検証**（方式A で簡素化）
   - 同一 vDAQ クロック。**injection は Aux Trigger で frame に揃って TIFF に載る**ので別同期不要。
   - 連続 behavior は Data Recorder を **imaging 開始 trigger で start**、または **frame clock/marker を 1ch 記録**して対応づけ。
   - テストで frame ↔ behavior 対応が想定どおりかを確認。
2. **behavior / injector を契約に載せる**
   - Data Recorder の HDF5 を ScanImage GRAB と**同 stem・`raw/`** へ。
   - **behavior sidecar** を **Data Recorder の HDF5 レイアウト＋ TIFF aux-trigger timestamp** 向けに再ターゲット
     （schema＝契約は流用、`make_behavior_sidecar.py` の入力側を差し替え）。`trigger_sync` は Aux Trigger timestamp を正本に。
   - **Track-M（MTT/CTH）は注入 t0 必須** → これで満たす。
3. **SI metadata 自動保存の契約適合確認**（logFileStem SOP〔`sops/`〕、ALS 3 ファイル＋`scnnr`、acq/scan_mode は metadata）＝ gate 条件 2。

### Tier 1 — 並行・低リスク
4. **ALS loader を test データで検証**（offset pre/post を MATLAB `readLineScanDataFiles` と突合、`bidirectional` 方向交互）。＝解析側 Track-W B と同一。
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
- 補足：`onFrameAcquired` の `fn = frameAcqFcnDecimationFactor * frameCount` は decimation 次第でずれ得る／
  ALS・FastZ volume で "frame" の意味が変わる。**実機検証要**（断定保留）。

---

## 4. → 解析チャットへ持っていく提案（roadmap 反映・**もんでから更新**）

> このセクションだけ解析チャットに貼り、roadmap に**もんでから**反映する。实体（§2 / §3）は本 doc に残す。

- **§2 スナップショット**に取得側 status table を追加（§1 を移植）。
- **§3 契約**に：「behavior / injector は**同 stem ＋ sidecar** で `raw/`」「injection t0 は **TIFF の Aux-Trigger timestamp**（同一 vDAQ クロック）」。
- **§4 Phase 2** を Tier 0 の checkbox 項目で具体化（方式A 実装＋検証を先頭に）。
- **§5 gate** に「同期検証（frame ↔ behavior 対応）」。**§7 未決**の「`trigger_sync` schema 暫定」→「取得側で確定（behavior_sidecar 内蔵・Aux Trigger 由来）」。
- 改訂履歴に 1 行。

---

## 5. 関連ドキュメント

- **roadmap（優先順位の正）**：`in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- **ALS 形式 / loader API の正本**：`src/python/als_loader.py`（旧 `HANDOFF.md` は廃止・救出済）
- **既知の問題（ベンダー波形バグ等）**：`docs/troubleshooting.md`
- **システム概要 / 設計**：`docs/overview.md`
- **I/O 割当**：`config/wiring/vdaq_io_map.yaml`
- **ScanImage 参照**：Data Recorder / Auxiliary Trigger（docs.scanimage.org）
- **作図標準**：`handoff_figstyle_tshino_20260603.md`

---

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-03 | behavior 入力経路を **方式A（vDAQ Data Recorder + Auxiliary Trigger）に決定**（§3）。ScanImage が低速 AI を Data Recorder で HDF5 記録、injector TTL を Aux Trigger で TIFF に timestamp できることを確認（docs.scanimage.org）。§2 を方式A 実装手順に、§1 を反映。`BehaviorAcquisition.m`+NI は方式B fallback として保持。 |
| 2026-06-03 | living 化（dated handoff → `status.md`）。§3 を「方式B 断定」から入力経路 fork へ訂正。behavior sidecar/injector・repo 構成を反映。`supersedes` 機構は廃止。ALS 形式の正本を `als_loader.py`、ベンダーバグを `troubleshooting.md` に委譲。 |
