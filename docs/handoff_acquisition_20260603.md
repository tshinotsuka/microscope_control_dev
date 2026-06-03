# Handoff — 取得側（hardware / 制御）2026-06-03

```
last_updated:   2026-06-03
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md
                （§6 によりここが「優先順位の単一の正」。本 doc はそこへリンクする側）
supersedes:     （なし・取得側 handoff の初版）
related:        ALS の取得→解析 bootstrap は `HANDOFF.md`（ALS 専用）が引き続き正本
```

取得側 project（vDAQ / ScanImage / FastZ / ALS / behavior / injector / resonant）の状態と次手。
**実体（コードレビュー・装置）は本 doc に閉じ、roadmap には決定事項だけを反映する**
（結合は緩く保つ＝roadmap §6 / loose coupling）。新チャットに貼れば取得側の文脈を引き継げる。

> 起動時の注意: 古い handoff を current 扱いしないこと。`supersedes` と日付を確認し、
> より新しい取得側 handoff があればそちらを正とする。

---

## 0. このセッションの結論（次の一手）

次の一手は FastZ / resonant の**機能追加ではない**。
**取得物を凍結済み契約に載せ、同期の正本を確定し、不可逆な in vivo 取得の gate を閉じる**
＝ roadmap **Phase 2 ＋ gate 条件 2**「取得が契約どおりの解析可能データを吐くと確認済み」。

判断軸は roadmap §1 の **可逆性 × コスト**：安くやり直せる手を先に、本実験 in vivo 取得（最も不可逆）は
gate を満たしてから。FastZ / resonant は roadmap が「将来 capability・本実験 frame/SRS の blocker ではない
→ さらに後ろで可」と明示しているので、後ろに置く。

---

## 1. 取得側 status スナップショット

| 項目 | 状態 | メモ |
|---|---|---|
| vDAQ + ScanImage 稼働 | ☑ | |
| ALS 取得 | ☑ | loader 検証は解析側 Track-W B（☐）で実施 |
| 行動記録コード `BehaviorAcquisition.m` | ◐ | 動作するが **off-contract・同期正本未確定**（§2-1, §2-2, §3） |
| インジェクター同期 | ◐ | 物理はあるが**コード/schema 未捕捉**（§2-2） |
| FastZ 導入 | ◐ | 契約への載せ方が未（Tier 2 / §2-7） |
| resonant 準備 | ☐ | `scanner_type` は metadata 駆動で準備済・フル統合は将来（Tier 2 / §2-8） |

---

## 2. 次セッション頭出し（取得側实体・Tier 順）

### Tier 0 — in vivo（不可逆取得）の前に必ず閉じる

1. **同期の正本を確定し検証する（最重要）**
   - `frame_clock` TTL（`Dev1/ai4`・行動データと同一サンプリング）を **authoritative** にする。
   - `frame_log/sample_index` は `totalWritten` ベース＝**最大 `chunkDuration`（既定 500 ms）の量子化誤差**＋
     イベントコールバックのジッタ。→ **cross-check に降格**。
   - テスト 1 本で「TTL 立ち上がり ↔ frame_log」が**数サンプル以内で一致**することを確認。

2. **behavior / injector を契約に載せる**
   - 保存先を ScanImage GRAB と**同 stem・`raw/` 配下**へ（現状は独立 `sessionName` ＋ `C:\data`＝
     roadmap §3「behavior/injector は同 stem」違反）。
   - **行動データ用 sidecar** を ALS sidecar 流儀で吐く（`channels[].name` 役割・`sample_rate`・
     **クロックドメイン註**・SI stem リンク）。`make_sidecar.py` / schema の流儀を横展開。
   - **injector を記録チャネル / TTL に追加**＋ **`trigger_sync` schema を取得側で確定**
     （roadmap 必要実データの「暫定」を解消）。**Track-M（MTT/CTH）は注入 t0 が無いと成立しない**。

3. **SI が契約どおりの metadata を自動保存しているか検証**（logFileStem SOP、ALS 3 ファイル＋`scnnr`、
   「acq / scan_mode はファイル名でなく metadata」ルールの実機確認）＝ **gate 条件 2**。

### Tier 1 — 並行可・低リスク・de-risk

4. **ALS loader を test データで検証**（offset pre/post を MATLAB `readLineScanDataFiles` と 1 acquisition 突合、
   `bidirectional=true` の方向交互を cycle 平均前に確認）。＝解析側 **Track-W B** と同一作業。
5. **ストリーミング保存のクラッシュ耐性**（`onCleanup` 駆動 finalize ＋ frame_log の**定期 flush**）。
   現状は強制終了で `trimH5` / `writeFrameLog` が走らない（README も try-catch を要求＝既知の脆さ）。長期無人運用の前提。
6. **DAQ API の方針決定**：`daq.createSession('ni')` 系は**レガシー Session interface**
   （MathWorks は R2020a 以降 `daq("ni")` の DataAcquisition interface を推奨）。据え置き or 移行を**明示**する。

### Tier 2 — 将来 capability（上記の後 / 初回 in vivo の後）

7. **FastZ** は機能追加より先に**契約への載せ方**を（ALS scanfields に `zs` 既出。volume framing を metadata で捕捉）。
8. **resonant** はフル統合（`scanner_type` が既に metadata 駆動なのは正しい・契約フックは済）。

---

## 3. 重要な不整合（Tier 0–1 の裏づけ・实体）

**README ↔ code の食い違い**（ラボ標準にする前に解消すべき）:

- README は「**方式 A：MATLAB オールインワン・フレームと同一クロック**」を選定したと書く。
- しかし実装は `Dev1/ai0..ai5` を `daq.createSession('ni')` で開く＝**別 NI ボード（方式 B）**。**vDAQ Aux ではない**。
- 故に「フレームと同一クロック」は**この実装では成り立たない**（別ボードは別クロック・`frame_clock` TTL コピーが橋渡し）。
  設計自体は堅牢だが、**doc と code が「何が起きているか」で食い違ったまま**ラボ標準にすると、将来の解析が
  クロックドメインで必ず混乱する。→ Tier 0-1 で `frame_clock` TTL を正本化＋ **README を実装（方式 B）に合わせて修正**。

**フレーム番号**: `onFrameAcquired` の `fn = hScan2D.frameAcqFcnDecimationFactor * frameCount` は decimation 次第で
ずれ得る／ALS・FastZ volume では "frame" の意味が変わる。**実機検証要**（断定保留）。

---

## 4. → 解析チャットへ持っていく提案（roadmap 反映用・**もんでから更新**）

> このセクションだけを解析チャットに貼り、roadmap（解析 repo）に**もんでから**反映する。
> 实体（§2 / §3）は本 doc に残す（結合を緩く保つため）。

- **§2 現状スナップショット**に**取得側 status table を 1 枚追加**（上記 §1 を移植。解析側から取得進捗が一目で見えるように）。
- **§3 契約**に追加（契約＝ラボ標準）:
  - 「`frame_clock` TTL を**同期の正本**にする」
  - 「behavior / injector は**同 stem ＋ sidecar** で `raw/`」
- **§4 Phase 2** を上記 **Tier 0** の checkbox 項目で具体化。
- **§5 gate** に「**同期正本の検証**（TTL 立ち上がり ↔ frame_log が数サンプル以内一致）」を追加。
- **§7 未決**の「`trigger_sync` schema **暫定**」を「**取得側で確定**」へ更新。
- **改訂履歴**に 1 行。

---

## 5. 関連ドキュメント

- **roadmap（優先順位の正）**: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- **ALS bootstrap**: `HANDOFF.md`（ALS 取得→解析・専用）
- **作図標準**: `handoff_figstyle_tshino_20260603.md`（全図 `figstyle_tshino` 経由）
- **統合 handoff（解析側・前セッション）**: `handoff_summary_20260603_integrated.md`
