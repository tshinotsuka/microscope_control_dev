# Method-A 実機 runsheet — 本番前ゲート② close（deterministic fixed-frame injection）

```
last_updated:   2026-06-15
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（§5 gate2・優先順位の単一の正）
scope:          実機セッション専用。WG 'Trig Legato130' を frame clock で hardware-trigger し、
                狙った cycle N に毎回着弾する決定論を確認して gate② を閉じるまでの手順。
                状態の正本＝status.md §2.1/§3.5・sync_architecture.md §3.5・vdaq_io_map.yaml。
                本 doc は「実機で何を・どの順で・どこで go/no-go か」だけ。
parent_sop:     sops/method_a_e2e_gonogo_sop.md
related:        NEXT_SESSION_kickoff.md §1, handoff_summary_20260612.md §2A, trigger_sync.schema.json
```

> 既存 continuous run（`run-06_00005`/`00007`）は「arm すれば D3.2/AI7 に出る」の**存在証明のみ**。
> 決定論は本 runsheet の **finite 単発・正 config・複数 run** で取り直したクリーンデータでのみ判定する。
> continuous の長 HIGH／永続 on は解析に使わない。

---

## 0. このセッションの PASS 定義（先に固定）

**gate② PASS = 次を全部同時に満たす：**
- finite 単発の正 config で **同一設定の 3 run 以上**をクリーンに取得した。
- 各 run で `diag_ttl.py` が **AI7 単発・1 edge**（continuous の長 HIGH でない）。
- 各 run で `als_inject_align.py` の **着弾 cycle が、狙った N に全 run 一致**。

> この 3 点一致は、trigger が WG をゲートしている（＝frame clock 同期）・one-shot・cycle 指定、の 3 つを
> 同時に立証する。free-run なら cycle がばらつくので、trigger 有効性 vs free-run の切り分けも兼ねる。
> ①（1-min stop）は **closed・やり直さない**（roadmap §5 gate①）。

---

## 1. preflight（grab 前・配線と config）

### 1.1 配線（`vdaq_io_map.yaml` と一致を目視）
- `D3.2`(WG 'Trig Legato130' 出力) → T 分岐 → ①`AI7`(Data Recorder `Legato130_TTL`＝t0 正本) ／②`D2.1`(Aux・resonant 任意・無害) ／③Legato 本体。
- `D0.0`(frame clock out・vDAQgalvo 所有) → T 分岐 → ①`AI6`(Data Recorder `frame_clock` ループバック) ／②**`D2.2`(WG Start Trigger 入力)**。
- D2.2 は D2=Inputs Only で WG-ownable。D0.0 を WG の trigger に直接予約はできない（registration error）→ 物理 T 分岐が正。

### 1.2 ALS / 波形
- Optimize Waveform は不可（MBF 25850）→ **Reset Waveform → Calibrate + Test**。
- als_ref / sweep を見る回は **Monitor Scanner Feedback ON**。

### 1.3 Data Recorder（run-config）
- Sample Rate **5000 Hz** ／ Auto Start **ON** ／ Use Trigger **OFF** ／ Duration **Inf**。
- `AI7 → Legato130_TTL` ／ `AI6 → frame_clock`（ALS でも cycle clock＝branch A）。
- `hScan2D.logFramesPerFile = Inf`（**per-scanner**・空 `_00002` 抑止）。

### 1.4 取得長（①の運用・再設定漏れ注意）
- 連続取得は `framesPerSlice`（ALS=cycle 数）を **`Inf`** or 必要 cycle 数に。
- 総 grab frame = `framesPerSlice × numSlices × numVolumes`。raster へ切替時は再設定。

### 1.5 User Function
- `acqModeStart → syncArmStart` ／ `acqAbort`・`acqDone → syncDisarm` ／ **`frameAcquired` 空**（overflow 回避の要）。
- ※ 本セッションは syncArmStart 旧版のままで可（WG arm は §2 で手動）。自動 arm 化は §6（PASS 後）。

> **GO/NO-GO ①（preflight）**: 1.1〜1.5 を全て確認 → GO。配線/Recorder ch のどれか不一致なら直してから先へ。

---

## 2. WG 正 config（finite 単発・frame clock trigger・cycle 指定）

> 目的: continuous（永続 on）を捨て、**finite 単発**で `Start = N×cycle` の遅延に短パルスを 1 発置く。
> トリガは D2.2（frame clock の T 分岐）。

設定順（全部決めてから Apply → arm → grab）:
1. WG 'Trig Legato130' を **finite** モードに。
2. **Start Trigger = `/vDAQ0/D2.2`（rising）**。
3. パルス: 短 Duty/Period（≈ 0.2 s 幅）。pulse 幅 = Duty% × Period。
4. **`Start = N × cycle_period`**（cycle 0 からの遅延で着弾 cycle N を指定）。
   - cycle_period = 1 / cycle_rate（例 166.67 Hz → 6.0 ms）。狙う N をここで決める（例 N=500）。
5. Apply。
6. **widget で WG を Start(arm)**（← ここが鍵。Resource Config の Apply だけでは task 未起動＝D3.2 無出力）。
7. GRAB。

> **「must write buffer」が出たら**: config 変更で buffer が空のまま start しようとした状態。
> **Waveform Function を選び直して buffer を再生成** → Start。
> WG widget の `SceneTree ... replaceChild` 警告は GUI 描画ノイズ・出力に無関係（Show Widget OFF で静音）。

> **GO/NO-GO ②（WG 設定）**: finite ✓ ／ Start Trigger=D2.2(rising) ✓ ／ 短パルス ✓ ／ Start=N×cycle ✓ ／ arm 済 ✓ → GO（grab）。
> いずれか未設定なら戻る。**continuous のまま grab しない**（決定論判定に使えないデータになる）。

---

## 3. 取得ループ（同一設定で 3 run 以上）

各 run で §2 の **6→7（widget Start(arm)→GRAB）** を繰り返す。**設定（N・パルス幅・trigger）は固定**。
- run ごとに stem を控える（例 `run-07_00001`, `00002`, `00003`）。
- 3 run で足りなければ追加。途中で config を触ったら §2 から arm し直し。

---

## 4. per-run QC（取得直後・各 run）

実行 env: `mcd-quicklook`（取得 PC・`...\GitHub\microscope_control_dev\src\python`）。

各 run につき順に:
1. `diag_ttl.py` … AI7 単発・**1 edge**（`edges@2.5V = 1`）を確認。
   - **NO-GO**: edges=0（flat）→ §7 A（未 arm / continuous / config 途中）。長 HIGH → continuous のまま（§7 B）。
2. `als_inject_align.py` … branch A clock `[OK]`・**着弾 cycle 番号**を記録。
   - clock が `[OK]`（N/N or 境界 off-by-one）でないなら §7 C。
3.（任意）`sweep_quality.py` … per-cycle pp PASS（park 病が無いこと）。掃引品質に疑義がある回のみ。

> **GO/NO-GO ③（各 run）**: diag_ttl 単発 ✓ ＋ als_inject_align clock [OK] ＋ 着弾 cycle 取得 → この run は採用。
> 1 でも欠ければこの run は破棄して §7 で原因を潰し、設定を直して取り直す。

---

## 5. 決定論判定（gate②）

採用した 3 run 以上の **着弾 cycle を並べる**:
- **全 run で `inject cycle = N`（狙い値）に一致** → **gate② PASS**。
  - = trigger が WG をゲート（frame clock 同期）・one-shot・cycle 指定の 3 点を同時立証。
- ばらつく（run ごとに違う cycle） → trigger が効いていない／free-run の疑い → §7 C へ。

> **GO/NO-GO ④（gate②）**: 一致 → PASS → §6 へ（自動 arm 化）。
> 不一致 → PASS 保留。§7 C を潰してから §2 で取り直す。**この段階では in-vivo 不可逆取得に進まない**。

---

## 6. PASS 後（automation・本セッション内 or 次回）

- `syncArmStart` を **「acqModeStart で WG を arm/start」する v2** へ（widget 手動 Start を不要に）。
  - 確定すべき＝**widget Start の programmatic 等価**（WG resource の start/arm メソッド）。
    Resource Config の Apply では task が起動しない点に注意。
  - **per-frame host UF は不可**（>~17 Hz で frame queue overflow）。arm は acqModeStart 1 回のみ。
- v2 で再度 §3→§5 を 1 巡し、**自動 arm でも cycle 一致**を確認 → 運用へ。

---

## 7. トラブルシュート（NO-GO 分岐）

- **A. AI7 flat（edges=0）**: WG が未 arm、または continuous で未 start、または config 途中。
  → §2-6 の **widget Start(arm)** を実施。失敗 run `run-05_00002`/`run-06_00003` はこれ（機構の否定ではない）。
- **B. AI7 が長 HIGH（永続 on）**: continuous のまま。→ §2-1 で **finite** に直す。
- **C. 着弾 cycle がばらつく / clock が [OK] でない**:
  - Start Trigger source が `/vDAQ0/D2.2`(rising) か、D0.0→D2.2 の物理 T 分岐が生きているか確認。
  - `D2.2` が他で予約されていないか（free_ports で D2.2=WG Start Trigger）。
  - branch A clock（D0.0→AI6）の loopback 健全性を `als_inject_align` で確認。
- **D. 「must write buffer」**: §2 の Waveform Function 再選択で buffer 再生成 → Start。

---

## 8. このセッションで触る/残すドキュメント

- 触る（PASS 後・in-place）: `status.md §2.1`（gate② ◐→☑）、`strategy_roadmap.md §5 gate2`（②を PASS に・ミラー）、新 `handoff_summary_<YYYYMMDD>.md`。
- v2 を入れたら: `syncArmStart.m`（arm 版）、`vdaq_io_map.yaml` の injector_trigger 注記（arm 自動化）。
- 不変: t0 正本（AI7 = Data Recorder TTL edge）・`als_inject_align.py`・`trigger_sync.schema.json`（解析側契約）。
