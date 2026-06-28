#!/usr/bin/env python
"""roi_builder_gui.py -- raster 上でクリックして ScanImage .roi を作る GUI（Windows/acquisition PC で実行）。

できること:
  * raster 画像（tif/png）を表示し、クリックで line を置く。
    1クリック目 = r=0（掃引開始）＝解析の r=0。**血管中心を先にクリック**して外へ。
  * line 以外（point / circle / spiral / park ...）も function 選択で置ける（line/pause 以外も可）。
  * 生成した line を deg に変換 -> px に逆投影して画像に重ねる（ズレ=座標系不一致を保存前に発見）。
  * pause を自動で間に挟んで .roi（scanimage.mroi.RoiGroup）を書き出す -> ScanImage でロード。

操作:
  左クリック2回 = 1 line（中心→外）。 function=point/park は1クリック。
  キー:  u=最後を取り消す  s=保存  l/p/c=function 切替(line/point/circle)  q=終了
  （duration/power/z/本数は下の設定で。細かい数値は保存後 ScanImage 側でも調整可）

必要: scanimage_roi.py を同じ場所か import パスに。画像読み込みに tifffile か Pillow。

設定（FOV_DEG は raster の角度FOV[deg]= imaging scanfield の sizeXY。raster meta から。
y_down を保存前のオーバーレイで合わせる：重ねた線が画像上の意図とズレたら Y_DOWN を反転）。
"""
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import scanimage_roi as SR

# ============================== 設定 ==============================
RASTER_PATH = r"C:\path\to\raster.tif"      # 表示する raster（vessel reference）
OUT_ROI     = r"C:\path\to\my_lines.roi"    # 書き出し先
FOV_DEG     = (13.5, 13.5)                   # raster の角度FOV[deg]（imaging scanfield sizeXY）
CENTER_DEG  = (0.0, 0.0)                     # FOV 中心（通常 [0,0]）
Y_DOWN      = True                           # 画像下向き正。オーバーレイがズレたら反転
ZS          = 15.24                          # z 面 [µm]
DURATION    = 0.001                          # line 掃引時間 [s]（取得側の dwell 設計に合わせる）
REPETITIONS = 1
POWER       = None                           # None=既定 / 数値でビーム power
PAUSE_S     = 0.001                          # line 間 pause [s]
RASTER_CHANNEL = 0                           # 多ch tif の表示 ch（0始まり）
# ===============================================================


def load_image(path):
    try:
        import tifffile
        a = tifffile.imread(path)
    except Exception:
        from PIL import Image
        a = np.asarray(Image.open(path))
    a = np.asarray(a)
    if a.ndim == 3:                         # (frame/ch, y, x) or (y,x,ch)
        if a.shape[0] <= 8:
            a = a[min(RASTER_CHANNEL, a.shape[0] - 1)]
        elif a.shape[-1] <= 8:
            a = a[..., min(RASTER_CHANNEL, a.shape[-1] - 1)]
        else:
            a = a.mean(0)
    elif a.ndim == 4:
        a = a[:, min(RASTER_CHANNEL, a.shape[1] - 1)].mean(0)
    return a.astype(float)


class Builder:
    def __init__(self, img):
        self.img = img
        self.ny, self.nx = img.shape
        self.n_px = (self.nx, self.ny)
        self.fn = "line"
        self.pending = []          # クリック途中の点
        self.lines = []            # [(p0,p1)] for line / (p,) for point 等は別管理
        self.items = []            # 確定 StimItem（line/point/...）
        self.artists = []
        self.fig, self.ax = plt.subplots(figsize=(9, 9))
        lo, hi = np.percentile(img, [2, 99])
        self.ax.imshow(img, cmap="gray", vmin=lo, vmax=hi, origin="upper")
        self.ax.set_title(self._title())
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)

    def _title(self):
        return (f"fn={self.fn} | lines/items={len(self.items)} | "
                f"click: line=2pts(center->out) point=1pt | u=undo s=save l/p/c=fn q=quit")

    def _redraw_title(self):
        self.ax.set_title(self._title()); self.fig.canvas.draw_idle()

    def on_key(self, e):
        if e.key == "u":
            self.undo()
        elif e.key == "s":
            self.save()
        elif e.key in ("l", "p", "c"):
            self.fn = {"l": "line", "p": "point", "c": "circle"}[e.key]
            self.pending = []; self._redraw_title()
        elif e.key == "q":
            plt.close(self.fig)

    def on_click(self, e):
        if e.inaxes != self.ax or e.xdata is None:
            return
        self.pending.append((e.xdata, e.ydata))
        need = 2 if self.fn in ("line",) else 1
        if len(self.pending) >= need:
            self.commit(self.pending[:need]); self.pending = []

    def commit(self, pts):
        if self.fn == "line":
            p0, p1 = pts
            it = SR.line_from_px(p0, p1, self.n_px, FOV_DEG, CENTER_DEG, Y_DOWN,
                                 name=f"line{len([i for i in self.items if i.fn=='line'])+1}",
                                 duration=DURATION, repetitions=REPETITIONS, powers=POWER, zs=ZS)
            # 逆投影オーバーレイ（座標系検証）: 生成 deg -> px に戻して描く
            (q0, q1) = SR.line_endpoints_px(it, self.n_px, FOV_DEG, CENTER_DEG, Y_DOWN)
            ln, = self.ax.plot([q0[0], q1[0]], [q0[1], q1[1]], "-", color="cyan", lw=2)
            dot, = self.ax.plot([q0[0]], [q0[1]], "o", color="cyan", ms=8, mec="white")  # r=0
            self.artists.append((ln, dot))
        else:
            p = pts[0]
            x, y = SR.px_to_deg(p[0], p[1], self.n_px, FOV_DEG, CENTER_DEG, Y_DOWN)
            size = (2.0, 2.0) if self.fn == "circle" else (0.0, 0.0)
            it = SR.stim(self.fn, center_xy=(x, y), size_xy=size, duration=DURATION,
                         repetitions=REPETITIONS, powers=POWER, zs=ZS,
                         name=f"{self.fn}{len([i for i in self.items if i.fn==self.fn])+1}")
            dot, = self.ax.plot([p[0]], [p[1]], "s", color="yellow", ms=9, mec="black")
            self.artists.append((dot,))
        self.items.append(it)
        self._redraw_title()

    def undo(self):
        if not self.items:
            return
        self.items.pop()
        for a in self.artists.pop():
            a.remove()
        self._redraw_title()

    def save(self):
        lines = [it for it in self.items if it.fn == "line"]
        others = [it for it in self.items if it.fn != "line"]
        seq = SR.interleave_pauses(lines, PAUSE_S, ZS) if lines else []
        seq += others                       # line 以外は末尾に（順序は ScanImage 側で調整可）
        if not seq:
            print("[save] 置かれた item が無い"); return
        SR.write_roi(OUT_ROI, seq, group_name="GUI Line ROI Group")
        print(f"[save] {len([i for i in seq if i.fn=='line'])} line + "
              f"{len([i for i in seq if i.fn=='pause'])} pause + {len(others)} other -> {OUT_ROI}")
        print("  ScanImage の ROI Group manager でこの .roi をロードして確認。")

    def run(self):
        print("クリックで line を置く（中心→外）。s=保存 u=undo q=終了。")
        print("シアン線が画像の意図とズレる場合は設定の Y_DOWN を反転して置き直す。")
        plt.show()


def main():
    if not os.path.exists(RASTER_PATH):
        print(f"raster が無い: {RASTER_PATH}\n設定 RASTER_PATH を直して。")
        return
    img = load_image(RASTER_PATH)
    print(f"image {img.shape}  FOV_DEG={FOV_DEG}  -> deg/px≈{FOV_DEG[0]/img.shape[1]:.4f}")
    Builder(img).run()


if __name__ == "__main__":
    main()
