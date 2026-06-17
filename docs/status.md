# status.md 更新パッチ（2026-06-17）— 貼り込み用

```
適用先:   microscope_control_dev/docs/status.md（in-place 更新・dated にしない方針）
内容:     ゲート② = WG 方式 ALS 行き止まり確定＋DoTask ピボット。
          §1 先頭・§2.1②・§3.5・§4・改訂履歴 の 5 か所を差し替え/追記。
note:     本ファイルはパッチ集。status.md へ手で反映したら破棄してよい。
```

---

## ① §1「現在地」先頭に挿入（既存 2026-06-12 ブロックの**上**へ）

```markdown
**2026-06-17 更新（ゲート② = WG 方式 ALS 行き止まり確定・DoTask ピボット）**

- **ゲート②（fixed-frame injection）= WG（ScanImage WaveformGenerator）方式は ALS で行き止まり確定**。`startTask` 自体が毎回 `updateWaveform→computeWaveform→refreshWvfmParams→hSI.hScan2D.scannerset.linePeriod(ss)` で波形を再計算し、`GalvoGalvo.linePeriod`（行 489）が `assert(isa(scanfield,'ImagingField'))` を持つため **ALS の `StimulusField` で必ず落ちる**（フルスタック取得・2026-06-17 17:33）。**pre-compute は無意味**（startTask が作り直す）・**Show Widget OFF も無効**（widget 再描画でなく startTask 内部の再計算が原因）。`[sync] armed` は**偽陽性**だった（SI の ErrorHandler が内部の linePeriod / must-write を握り潰し try/catch に伝播せず「正常終了」に見えた＝task 未起動・AI7 flat）。**SI の制約であり当方ロジックの問題ではない**。
- **白と確認できたもの（実機・2026-06-17）**: frame clock `D0.0→AI6` = **125.0 Hz（8.0 ms/cycle・4-line）** clean train（**cycle rate 確定**）／**D2.2 分岐が生きてる**（D2.2 行きケーブルを空き AI9 で録ると 125 Hz/5V）／**WG 本体＋D3.2→AI7 経路は正常**（トリガ無し Test B で clean 単発 edges@2.5V=1・max 5.09V）／**behavior** `AI4=treadmill_dir`・`AI5=treadmill_speed` が HDF5 signals に入る。詰まりは「WG task を ALS 中に起こす方法が原理的に無い」点に集約。
- **次の一手 = v4：WG をバイパスし自前の `dabs.vidrio.ddi.rdi.DoTask` を D3.2 に立てて D2.2 trigger で撃つ**（§3.5・§2.1②）。WG（'TrigLegato130-2'）を Remove して D3.2 を解放 → `createDoTask→addChannel('D3.2')→cfgSampClkTiming(finite)→cfgDigEdgeStartTrig('/vDAQ0/D2.2','rising')→writeOutputBuffer→start`。linePeriod を踏まないので ALS 中も start できる見込み（= v4 の分水嶺・未確認）。DoTask API 取得済。

```

---

## ② §2.1 の項目 2 を**全文差し替え**

差し替え対象（既存）:
> 2. **決まったフレームでの投与（fixed-frame injection）＝機構特定・検証残（2026-06-12）**。…（WG widget arm 前提の段落）

差し替え後:

```markdown
2. **決まったフレームでの投与（fixed-frame injection）＝WG 方式 ALS 行き止まり確定・DoTask へピボット（2026-06-17）**。現行 `delaySec`（host timer）は head_pad 可変ゆえ毎回同 cycle に当たらず deterministic でない。当初狙った **WG hardware-trigger（`D0.0`→`D2.2`）は、ScanImage の generic WaveformGenerator が ALS scan mode で arm（startTask）できないため不可**（`startTask`→`updateWaveform`→`computeWaveform`→`linePeriod` の再計算が ALS の `StimulusField` で assert 落ち・§3.5/§4）。**WG 方式は却下・再試行しない**。**次手＝v4：WG を Remove して D3.2 を解放し、自前の `dabs.vidrio.ddi.rdi.DoTask` を D3.2 に立てて `D2.2`(rising) で hardware-trigger**（linePeriod 非依存）。手順: ①WG Remove → ②`createDoTask`→`addChannel('D3.2')`→`cfgSampClkTiming(R_Hz,'finite',nSamp)`→`cfgDigEdgeStartTrig('/vDAQ0/D2.2','rising')`→`writeOutputBuffer(pulseVec)`→`start()`（着弾 cycle N = buffer 前方 zero 長 `N×8.0ms×R`・`R` は 1e5〜1e6・短 HIGH ~0.1–0.2 s）→ ③**DoTask が ALS 中に start するか確認（=分水嶺）** → ④ALS ON grab で `diag_ttl`（単発 edges@2.5V=1）→ `als_inject_align`（着弾 cycle）→ ⑤3 run 以上で cycle=N 一致で **gate② PASS** → ⑥`syncArmStart`/`syncDisarm` を v4（acqModeStart で DoTask 構成→start／acqAbort・acqDone で stop/abort）へ。**per-frame host UF は overflow ゆえ不可**（§3.5）。
```

---

## ③ §3.5 injector — 「2026-06-12 fixed-frame 機構」サブ項目の**直後**に追記

```markdown
- **2026-06-17 WG 方式は ALS 行き止まり確定（却下）**: 上の「widget Start(arm)→grab」を自動化すべく `syncArmStart` を acqModeStart で WG を起こす版にしたところ、**WG task の起動自体が ALS で原理的に不可**と判明。フルスタック（17:33）:
  ```
  WaveformGenerator.startTask (379)  -> obj.updateWaveform()
    updateWaveform (272)             -> obj.computeWaveform()
      computeWaveform (310)          -> obj.refreshWvfmParams()
        refreshWvfmParams (357)      -> hSI.hScan2D.scannerset.linePeriod(ss)
          GalvoGalvo.linePeriod (489)-> assert(isa(scanfield,'ImagingField'))  ← ALS=StimulusField で FAIL
  startTask (380)                    -> obj.hTask.start()  → "Must write buffer"（再計算が落ちて buffer 空）
  ```
  - **`startTask` 自体が毎回 `updateWaveform→computeWaveform→linePeriod` で再計算する**ため、pre-compute は無意味・Show Widget OFF も無効（widget 再描画でなく startTask 内部が原因）。`linePeriod` は raster(ImagingField) 前提の hardcode で ALS では必ず assert 落ち＝SI 制約。
  - `[sync] armed` は**偽陽性**（SI の ErrorHandler が startTask 内部の linePeriod / must-write を握り潰し try/catch に非伝播。task は未起動＝AI7 flat）。
- **2026-06-17 採用＝v4：自前 DoTask（WG バイパス）**: スタック下層の task 型 `dabs.vidrio.ddi.rdi.DoTask` を**自分で**立て、scannerset/linePeriod に一切触れずに D3.2 を駆動する。
  - 配線は不変（`D3.2`→T→`AI7`＋Legato／`D0.0`→T→`AI6`＋`D2.2`）。**WG 'TrigLegato130-2' を Remove して D3.2 を解放**（現状 `<Reserved: TrigLegato130-2>` で予約中）。`hDAQ`=vDAQR1（`wg.hDAQ`／ResourceStore 経由）。
  - 構成: `hT = dabs.vidrio.ddi.rdi.DoTask.createDoTask(hDAQ,'injTrig'); hT.addChannel('D3.2'); hT.cfgSampClkTiming(R_Hz,'finite',nSamp); hT.cfgDigEdgeStartTrig('/vDAQ0/D2.2','rising'); hT.writeOutputBuffer(pulseVec); hT.start();`
  - 着弾 cycle N = buffer 前方 zero 長 `N × cycle_period(8.0 ms) × R`。`R` は控えめ（1e5〜1e6）でサイズ現実化。短 HIGH（~0.1–0.2 s）。
  - **分水嶺＝DoTask が ALS 中に start できるか**（linePeriod 非依存ゆえ通る見込み・未確認）。disarm（syncDisarm v4）= `hT.stop()/abort()`＋必要なら `tristateOutputs`／default low。task ハンドルは persistent/appdata 保持。
- **cycle rate 確定（2026-06-17）**: 4-line config で frame clock `D0.0→AI6` = **125.0 Hz＝8.0 ms/cycle**（clean train・max ~5V）。着弾位置計算に使用。
```

また、§3.5 の冒頭付近の `syncArmStart`/`syncDisarm` の版表記を更新（任意）:
```markdown
- UF: `acqModeStart`→`syncArmStart`（**v4＝自前 DoTask 構成→start**・v3 までの WG 方式は却下）／`acqAbort`・`acqDone`→`syncDisarm`（**v4＝DoTask stop/abort**）。**`frameAcquired` 空**。
```

---

## ④ §4「既知の注意」に新規項目を追記（既存「WG arming」項目の**直後**を推奨）

```markdown
- **WG↔ALS 非互換＝WG 方式は却下（2026-06-17・最重要）**: ScanImage の generic WaveformGenerator は **ALS scan mode では arm（startTask）できない**。`startTask` が毎回 `updateWaveform→computeWaveform→refreshWvfmParams→scannerset.linePeriod` で波形を再計算し、`GalvoGalvo.linePeriod`（行 489）の `assert(isa(scanfield,'ImagingField'))` が ALS の `StimulusField` で落ちるため。**pre-compute / Show Widget OFF とも無効**（startTask 内部の再計算が原因）。SI 制約であり当方ロジックの問題ではない。injector は **WG をバイパスして自前 `dabs.vidrio.ddi.rdi.DoTask` を D3.2 に立てる v4 へ移行**（§3.5）。なお §4 旧「WG arming（widget Start が必要）」項目は v4 では DoTask の `start()` がその役割を担う（widget Start 不要）。
```

---

## ⑤ §5「解析側への申し送り」に 1 行（任意）

```markdown
- **behavior ch 確認（2026-06-17）**: HDF5 signals に `AI4=treadmill_dir` / `AI5=treadmill_speed`（`vdaq_io_map.yaml` の旧記載 velocity/lick は誤りにつき要修正）。R2（behavior 記録）は Gate② run に相乗り可。
```

---

## ⑥ 改訂履歴に 1 行追加（表の先頭）

```markdown
| 2026-06-17 | **ゲート②: WG 方式 ALS 行き止まり確定＋DoTask ピボット**（実機）。generic WaveformGenerator は ALS で arm 不可＝`startTask`→`updateWaveform`→`computeWaveform`→`scannerset.linePeriod`→`GalvoGalvo.linePeriod`(489) の `assert(isa(scanfield,'ImagingField'))` が ALS `StimulusField` で落ちる（フルスタック 17:33）。`startTask` 自体が毎回再計算するため pre-compute / Show Widget OFF とも無効。`[sync] armed` は偽陽性（SI ErrorHandler が内部エラーを握り潰し task 未起動・AI7 flat）。**WG 方式却下**。白＝frame clock `D0.0→AI6` 125.0Hz/8.0ms（cycle rate 確定）・D2.2 分岐健全（AI9 で 125Hz/5V）・WG 出力経路正常（Test B 単発 edges=1・max5.09V）・behavior `AI4=treadmill_dir`/`AI5=treadmill_speed`。**次手 v4＝WG Remove で D3.2 解放→自前 `dabs.vidrio.ddi.rdi.DoTask`（createDoTask/addChannel/cfgSampClkTiming finite/cfgDigEdgeStartTrig D2.2 rising/writeOutputBuffer/start）を立て linePeriod 非依存で撃つ**（着弾 cycle=buffer 前方 zero `N×8ms×R`）。検証＝DoTask が ALS 中 start するか→diag_ttl(単発)→als_inject_align(cycle)→3run 一致で PASS→syncArmStart/Disarm を v4 化。schema v0.2.0 finalize（9/9 PASS・$id host 揃え TODO）。**SI 起動中 `clear functions`/`clear all` 厳禁**（MDF/resource unload）。 |
```
