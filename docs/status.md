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
新チャットに貼れば取得側の文脈を引き継げる。

---

## 0. いまの一手

FastZ / resonant の機能追加ではなく、**取得物を契約に載せ、同期の正本を確定し、不可逆な in vivo 取得の
gate を閉じる**（roadmap **Phase 2 ＋ gate 条件 2**）。判断軸は roadmap §1 の **可逆性 × コスト**。

**ただしその前提として、behavior の入力経路（§3 の fork）を先に確定する** — これが同期アーキ全体を決める。

---

## 1. status スナップショット

| 項目 | 状態 | メモ |
|---|---|---|
| vDAQ + ScanImage 稼働 | ☑ | Phase 1 done（`overview.md`） |
| ALS 取得 | ☑ | loader 検証は解析側 Track-W B（☐） |
| **behavior 入力経路** | ⚠ | **未確定 fork**：`overview.md` は vDAQ 低速（方式A・同一クロック）、code は別 NI `Dev1`（方式B）。→ §3 |
| behavior sidecar（schema/generator） | ☑ | `schemas/behavior_sidecar.schema.json` ＋ `src/python/make_behavior_sidecar.py` 配置済 |
| injector 同期 | ◐ | TTL on/off。sidecar 設計済、`.m` への channel 追加は未（§2-2） |
| 同期の正本 | ◐ | `frame_clock` TTL 案。ただし §3 の経路次第（方式A なら TTL bridge 不要） |
| FastZ | ◐ | 契約への載せ方が未（Tier 2） |
| resonant | ☐ | `scanner_type` は metadata 駆動・準備済、フル統合は将来（Tier 2） |
| repo 構成 | ☑ | `docs/sops/config/src/schemas/examples` 配置済 |

---

## 2. 次手（Tier 順）

### Tier 0 — in vivo（不可逆取得）の前に閉じる
0. **behavior 入力経路の確定（最優先・§3）**：vDAQ 低速入力（方式A・同一クロック）か、別 NI ボード
   （方式B・TTL bridge）か。これが 1. の同期設計を決める。`overview.md` と code が食い違っている。
1. **同期の正本を確定し検証**（経路確定後）：
   - 方式A なら imaging と同一クロックで frame 対応が単純化。
   - 方式B なら `frame_clock` TTL（`Dev1/ai4`）を **authoritative** にし、`frame_log/sample_index`
     （`totalWritten` ベース＝最大 `chunkDuration` の量子化誤差）は **cross-check に降格**。
   - テスト 1 本で「TTL 立ち上がり ↔ frame_log」が数サンプル以内一致を確認。
2. **behavior / injector を契約に載せる**：保存を ScanImage GRAB と同 stem・`raw/` へ。behavior sidecar
   （配置済）で channels 役割・クロックドメイン・SI stem リンク・**trigger_sync（injector TTL on/off）**を出力。
   `injector` チャネルを `.m` に追加。**Track-M（MTT/CTH）は注入 t0 必須**。
3. **SI metadata 自動保存の契約適合確認**（logFileStem SOP〔`sops/`〕、ALS 3 ファイル＋`scnnr`、
   acq/scan_mode は metadata）＝ gate 条件 2。

### Tier 1 — 並行・低リスク
4. **ALS loader を test データで検証**（offset pre/post を MATLAB `readLineScanDataFiles` と突合、
   `bidirectional` 方向交互）。＝解析側 Track-W B と同一。
5. **ストリーミング保存のクラッシュ耐性**（`onCleanup` finalize ＋ frame_log 定期 flush）。
6. **DAQ API 方針**：`daq.createSession('ni')` はレガシー Session interface（R2020a 以降は
   DataAcquisition interface 推奨）。※方式A 採用なら `BehaviorAcquisition.m` 自体を見直すので、§3 と一緒に判断。

### Tier 2 — 将来 capability
7. **FastZ** を契約に（ALS scanfields の `zs`。volume framing を metadata で捕捉）。
8. **resonant** フル統合（`scanner_type` は既に metadata 駆動）。

---

## 3. behavior 入力経路の fork（要確定・实体）

- **`overview.md` §2** は behavior を **vDAQ 低速入力（12ch・最大 500 kHz）**に置く前提＝imaging と
  **同一クロック（方式A）**。
- **`BehaviorAcquisition.m`** は `Dev1/ai0..` を `daq.createSession('ni')` で開く＝**別 NI ボード（方式B）**。
  `daq.createSession('ni')` は NI-DAQmx 専用で、vDAQ ではない。
- つまり **設計意図（方式A）と現コード（方式B）が食い違っている**。旧 README #2 の「方式A 同一クロック」は
  意図を、コードは別実装を表していた可能性（＝以前「README が誤り」と断定したのは早計だった）。
- **判断が要る**：
  - **(A) vDAQ 低速入力へ寄せる** — imaging と同一クロック・別 NI 不要・frame 対応が単純。`.m` は ScanImage 側
    取得へ作り直し。
  - **(B) 別 NI を正式採用** — `frame_clock` TTL コピーで同期（現コードの延長）。NI ボードが必要。
  → 決めたら `overview.md` / `README` / `.m` を**一方に揃える**。これが §2 の 0→1 を確定させる。
- 補足：`onFrameAcquired` の `fn = frameAcqFcnDecimationFactor * frameCount` は decimation 次第でずれ得る／
  ALS・FastZ volume で "frame" の意味が変わる。**実機検証要**（断定保留）。

---

## 4. → 解析チャットへ持っていく提案（roadmap 反映・**もんでから更新**）

> このセクションだけ解析チャットに貼り、roadmap に**もんでから**反映する。实体（§2 / §3）は本 doc に残す。

- **§2 スナップショット**に取得側 status table を追加（§1 を移植）。
- **§3 契約**に：「behavior / injector は**同 stem ＋ sidecar** で `raw/`」。同期の正本は **§3 の経路確定後**に
  「frame_clock TTL（方式B）or 同一クロック（方式A）」を確定して追記。
- **§4 Phase 2** を Tier 0 の checkbox 項目で具体化（**経路確定を先頭に**）。
- **§5 gate** に「同期正本の検証」。**§7 未決**の「`trigger_sync` schema 暫定」→「取得側で確定（behavior_sidecar 内蔵）」。
- 改訂履歴に 1 行。

---

## 5. 関連ドキュメント

- **roadmap（優先順位の正）**：`in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- **ALS 形式 / loader API の正本**：`src/python/als_loader.py`（旧 `HANDOFF.md` は廃止・内容救出済）
- **既知の問題（ベンダー波形バグ等）**：`docs/troubleshooting.md`
- **システム概要 / 設計**：`docs/overview.md`
- **作図標準**：`handoff_figstyle_tshino_20260603.md`（全図 `figstyle_tshino` 経由）

---

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-03 | living 化（dated `handoff_acquisition_20260603.md` → `status.md`、in-place 更新方式へ）。**§3 を「README↔code＝方式B」断定から、behavior 入力経路の未確定 fork（方式A vs B）へ訂正**（`overview.md` §2 が vDAQ 低速＝方式A を示すため）。behavior sidecar / injector / repo 構成の進捗を §1 に反映。`supersedes` 機構は living 化で廃止。ALS 形式の正本を `als_loader.py` に、ベンダーバグを `troubleshooting.md` に委譲。 |
