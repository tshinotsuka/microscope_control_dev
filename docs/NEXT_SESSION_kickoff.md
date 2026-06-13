# NEXT SESSION kickoff — 取得側（次回＝実機あり）

```
last_updated:   2026-06-12
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
reflects:       handoff_summary_20260612.md（解析側ログ・本 kickoff はその前向き要約）
scope:          次セッション（実機あり）の頭出し。状態の正本＝status.md / roadmap。
                本 doc は「次に何を・どの順で」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

方式A **galvo go ＋ ALS go（single + multi-line/3-line・4-line config 取得実績）**。**本番前ハードウェアゲート①（sustained 取得／1-min scan stop）＝closed**（原因は有限 `framesPerSlice`＝fault でなく programmed 完走・`Inf` 化で数分連続を確認・4-line `run-02_00001` の post-hoc QC 全 PASS）。**②（deterministic fixed-frame injection）＝機構特定・検証残**: host timer を排し **WG 'Trig Legato130'(D3.2) を frame clock で hardware-trigger**（`D0.0`→`D2.2`）。実機で **widget で WG を Start(arm)→grab すると AI7 に clean 単発**（`run-06_00005`/`00007`・ただし continuous で長 HIGH）。残るは finite 単発の正 config で**クリーンに取り直し**、複数 run で「狙った cycle に毎回当たる」決定論を確認すること。resonant 据え置き。

## 1. 次セッションでやること（実機・優先順）

### 最優先＝本番前ゲート② を閉じる（fixed-frame injection）

> ①（1-min stop）は closed。やり直さない（§3）。
> **方針: 既存の continuous run（`run-06_00005`/`00007`）は「WG は arm すれば D3.2/AI7 に出力する」という存在証明のみに留める。決定論の検証は、finite 単発の正 config で取り直したクリーンデータで行う**（continuous の長 HIGH／永続 on のまま解析しない）。

**クリーン取り直し（正 config で新規取得 → 決定論検証）**
1. WG 'Trig Legato130' を **finite ＋ Start Trigger=`/vDAQ0/D2.2`(rising) ＋ 短パルス（Duty/Period ≈ 0.2 s）＋ `Start=N×cycle`**（狙う cycle N の遅延）に設定。配線 `D0.0`→`D2.2` を確認。設定を全部決める → Apply → **widget で Start(arm)** → GRAB の順。「must write buffer」が出たら **Waveform Function を選び直して buffer 再生成** → Start。
2. **同一設定で 3 run 以上、クリーンに取得**（continuous ではなく finite 単発）。
3. 各 grab で `diag_ttl.py`（AI7 単発・1 edge）→ `als_inject_align.py`（着弾 cycle）。
4. **決定論**: 全 run で `inject map: cycle #N` が **同じ cycle N に一致** → **ゲート② PASS**（trigger が WG をゲートしている＝frame clock 同期・one-shot・cycle 指定を同時に確認できる。free-run なら cycle がばらつくので、これで切り分けも兼ねる）。
5. **自動化（PASS 後）**: `syncArmStart` を「acqModeStart で WG を arm/start」する版へ（widget 手動 Start を不要に）。**widget Start の programmatic 等価**を実機で確定（WG resource の start/arm メソッド・Resource Config の Apply では task 起動しない点に注意）。**per-frame host UF は不可**。

### 並行（実機 / オフライン混在）

7. **behavior 記録・解析**: behavior ch を Data Recorder（同 vDAQ clock・同 HDF5）へ拡張 → `datarecorder_loader` 取り込み → 解析起こし。`trigger_sync` の `signals.behavior` と整合。
8. **FastZ 導入**: fast focus を vDAQ clock 同期で ALS / imaging に統合（多深度）。`sync_architecture.md` に FastZ 波形のクロック整合を追記。
9. **データ解析の一本化**: 散在ツールを raw→sync→per-line→QC の単一パイプラインへ。loader は取得 repo single source・ivwib 一方向 import を維持。契約＝`trigger_sync.schema.json`。
10. **injection / behavior GUI**（9 の先）: `syncControlPanel.m` 起点に operator UX 集約（WG arm/disarm・cycle N 指定・パルス幅・preflight 表示）。

### 据え置き / 最適化（急がない）

11. **4-line 取得**: 機構は line 数非依存・4-line config で取得実績あり（`run-02_00001`）。GUI Add バグ再現時のみ programmatic builder（用意済）。
12. **より速い ALS（pause→line 以外）**: ①transit 最短順（端点 greedy chain）②pause を整定最小まで詰める ③連続 waypoint serpentine（線間 pause を消し beam-on のまま折り返す＝dead transit 削減・連結区間は解析で破棄）。まず run で pause/line 時間比を測り overhead 定量化。
13. **trigger_sync finalize（galvo+ALS 2 mode）**: als_datafile gap・`$id`・`signals.behavior`・`als_datafile_timing` ブロック。
14. **resonant**: hardware 復帰まで据え置き。/ **NAS**: Phase 1.5 安全コピー（取得 PC の NAS アクセスは設定済・新 raw を `projects/2026_microscope_control_dev/` へ）。

## 2. 実機前チェック（preflight）

- ALS: Optimize 不可 → **Reset Waveform → Calibrate + Test**。als_ref / sweep 確認の回は **Monitor Scanner Feedback ON**。
- **取得長**: 連続取得は `framesPerSlice`（ALS=cycle 数）を **`Inf`**（or 必要 cycle 数）に。`framesPerSlice × numSlices × numVolumes` が総 grab frame。raster 切替時は再設定。
- Data Recorder: Sample Rate **5000 Hz**／Auto Start ON／Use Trigger OFF／Duration Inf。`AI7→Legato130_TTL`・`AI6→frame_clock`（ALS でも cycle clock＝branch A）。**`logFramesPerFile=Inf`**（per-scanner）。
- **injector（fixed-frame・検証中）**: 配線 `D3.2`(WG)→T→`AI7`＋Legato＋`D2.1`／`D0.0`(frame clock)→T→`AI6`＋**`D2.2`(WG Start Trigger)**。WG Start Trigger=`/vDAQ0/D2.2`(rising)・**finite**・`Start=N×cycle`・短 Duty。**grab 前に WG を widget で Start(arm)**（自動 arm が済むまで手動）。WG widget の SceneTree 警告は無視（Show Widget OFF で静音）。
- UF: `acqModeStart→syncArmStart` / `acqAbort・acqDone→syncDisarm` / **`frameAcquired` 空**。
- 取得直後: `diag_ttl.py`（AI7 単発・1 edge）→ `als_inject_align.py`（clock [OK]・着弾 cycle）→ `sweep_quality.py`（per-cycle pp PASS）。
- ツール実行 env: `mcd-quicklook`（取得 PC・`...\GitHub\microscope_control_dev\src\python`）。

## 3. オフライン / 実機で既に閉じた（次回やり直さない）

- **本番前ゲート①（1-min scan stop）closed（2026-06-12）**: 有限 `framesPerSlice` が原因＝fault でない。`Inf` 化で数分連続取得を確認（4-line `run-02_00001`・QC 全 PASS）。
- **WG が frame clock trigger で出力すること自体は確認済（2026-06-12）**: widget Start→grab で AI7 に clean 単発（`run-06_00005`/`00007`）。**ただし continuous（長 HIGH・永続 on）＝存在証明のみ**。決定論（cycle 一致）と finite 単発は**次回クリーン取り直しで確認**する。
- **ALS bench go/no-go ①②③**: single-line（06-08）＋ multi-line/3-line（06-09 run-01_00005）＋ 4-line config（06-12 run-02_00001）。
- **掃引品質 PASS**: `sweep_quality.py`（3-line run-01_00005／4-line run-02_00001）。
- **P2 multi-line exact**: `compare_als_ref.py`＝Track-W B loader closed。

## 4. 未決 / 繰越

- **ゲート②の決定論**: finite 単発の正 config で**クリーンに取り直した複数 run**で `als_inject_align` の着弾 cycle 一致を見て確定（既存 continuous 00005/00007 は存在証明のみで決定論には使わない＝trigger/free-run 切り分けも新規データで兼ねる）。
- **finite「must write buffer」の確実な回避手順**（Waveform Function 再選択での buffer 再生成）。
- **`syncArmStart` v2**: widget Start の programmatic 等価（WG resource の start/arm API）を実機で確定 → acqModeStart で arm。
- **per-line orientation/flip**: クリーン multi-line 取得済 → 線軸射影で下流 kymograph 前処理。
- **trigger_sync finalize**・**resonant**・**NAS**（上記 13/14）。
- **commit 候補（今セッション分）**: in-place の `status.md` / 本 kickoff / 新 `handoff_summary_20260612.md`／`vdaq_io_map.yaml`（D0.0→D2.2）／roadmap 反映（06-09＋06-12 畳み込み）。`syncArmStart.m` の v2（arm 版）は実機 API 確定後。

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- 解析側ログ: `in_vivo_water_imaging_brain/docs/handoff/handoff_summary_20260612.md`
- 取得側 status: `docs/status.md`
- 同期設計: `docs/sync_architecture.md`（要追記＝WG frame-clock trigger・D0.0→D2.2・arm 規約。本 handoff §5 に追記文案）
- 配線: `docs/vdaq_io_map.yaml`（D0.0→D2.2 追加済）
- ALS bench 手順: `docs/method_a_als_bench_runsheet_*.md`（親 SOP `sops/method_a_e2e_gonogo_sop.md`）
- 契約 schema: `schemas/trigger_sync.schema.json`
- ツール: `src/python/{datarecorder_loader,als_loader,compare_als_ref,make_trigger_sync,als_inject_align,diag_ttl,sweep_quality}.py`
