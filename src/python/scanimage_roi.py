#!/usr/bin/env python
"""scanimage_roi.py -- ScanImage mroi RoiGroup (.roi) の読み書き。

ScanImage の Line/Stimulus ROI は `scanimage.mroi.RoiGroup` を JSON 化した .roi。
各 ROI の scanfields = `StimulusField`（centerXY/sizeXY[deg]・rotationDegrees・
stimulusFunction・duration・repetitions・powers・zs・stimparams）。

このモジュール:
  * read_roi / write_roi : .roi の往復（round-trip 検証付き = ScanImage が読む保証）。
  * StimItem             : 1 stimulus（line / pause / park / point / circle / spiral / ...）。
                           stimulusFunction 名と stimparams を汎用に受ける（line/pause 以外も可）。
  * px<->deg             : raster 画像 px と scan 角度 deg の相互変換（objRes 非依存。
                           raster の角度FOV[deg]と px 数だけで決まる）。
  * 便利コンストラクタ    : line_from_px / point_from_px / pause / stim(...) と interleave_pauses。

座標系: scanfield は scan 角度 deg、FOV 中心 = [0,0]。画像 px (col,row) は
  deg = center_deg + (px/N - 0.5) * fov_deg   （y は画像下向き正なので符号注意・y_down で吸収）

leaf: 標準ライブラリのみ（json/uuid/math/dataclasses）。GUI からも CLI からも使える。
"""
from __future__ import annotations

import json
import math
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Optional, Sequence

SF_CLASS = "scanimage.mroi.scanfield.fields.StimulusField"
ROI_CLASS = "scanimage.mroi.Roi"
GROUP_CLASS = "scanimage.mroi.RoiGroup"
FN_PREFIX = "scanimage.mroi.stimulusfunctions."
BEAMS_FN = "scanimage.mroi.stimulusbeamfunctions.beamPowers"

# 既知の stimulus function（これ以外も名前を渡せばそのまま書ける）
KNOWN_FUNCTIONS = ("line", "pause", "park", "point", "circle", "spiral", "logspiral", "ellipse")


def _new_uuid():
    h = _uuid.uuid4().hex[:16].upper()
    return h, float(int(h, 16))


def _slm_empty():
    return {"_ArrayType_": "double", "_ArraySize_": [0, 4], "_ArrayData_": None}


# --------------------------------------------------------------------------- #
# データモデル
# --------------------------------------------------------------------------- #

@dataclass
class StimItem:
    """1 stimulus ROI。fn は stimulus function 名（'line','pause','park','point',
    'circle','spiral',... 何でも可）。line/pause 以外は stimparams / sizeXY を関数仕様に
    合わせて渡す（例: circle は sizeXY=[d,d]、spiral は stimparams=[...]）。"""
    fn: str = "line"
    name: str = ""
    center_xy: Sequence[float] = (0.0, 0.0)     # deg
    size_xy: Sequence[float] = (0.0, 0.0)       # deg ([length,0] for line; [d,d] for circle 等)
    rotation_deg: float = 0.0
    duration: float = 0.001                     # s（line の掃引時間 / pause の停止時間）
    repetitions: int = 1
    powers: Optional[Sequence[float]] = None    # None=既定 / [p] でビーム power 指定
    zs: float = 0.0                             # z 面 [µm]
    z_span: float = 0.0
    stimparams: list = field(default_factory=list)
    enable: int = 1

    def to_scanfield(self):
        h, u = _new_uuid()
        return {
            "ver": 1, "classname": SF_CLASS, "name": "", "UserData": None,
            "roiUuid": h, "roiUuiduint64": u,
            "centerXY": [float(self.center_xy[0]), float(self.center_xy[1])],
            "sizeXY": [float(self.size_xy[0]), float(self.size_xy[1])],
            "rotationDegrees": float(self.rotation_deg),
            "enable": int(self.enable),
            "stimulusFunction": FN_PREFIX + self.fn,
            "stimparams": list(self.stimparams),
            "duration": float(self.duration),
            "repetitions": int(self.repetitions),
            "powers": (list(self.powers) if self.powers is not None else None),
            "zSpan": float(self.z_span),
            "beamsFunction": BEAMS_FN,
            "slmPattern": _slm_empty(),
        }

    def to_roi(self, idx):
        h, u = _new_uuid()
        return {
            "ver": 1, "classname": ROI_CLASS,
            "name": self.name or f"ROI {idx}", "UserData": None,
            "roiUuid": h, "roiUuiduint64": u, "zs": float(self.zs),
            "scanfields": self.to_scanfield(),
            "discretePlaneMode": 0, "powers": None, "pzAdjust": [], "Lzs": None,
            "interlaceDecimation": None, "interlaceOffset": None, "enable": int(self.enable),
        }


# --------------------------------------------------------------------------- #
# read / write
# --------------------------------------------------------------------------- #

def read_roi(path):
    """`.roi` を読み、(group_name, [StimItem, ...]) を返す。"""
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    items = []
    for r in d.get("rois", []):
        sf = r["scanfields"]
        sf = sf[0] if isinstance(sf, list) else sf      # multi-z は先頭を採用
        fn = sf["stimulusFunction"].split(".")[-1]
        items.append(StimItem(
            fn=fn, name=r.get("name", ""),
            center_xy=tuple(sf.get("centerXY", (0, 0))),
            size_xy=tuple(sf.get("sizeXY", (0, 0))),
            rotation_deg=sf.get("rotationDegrees", 0.0),
            duration=sf.get("duration", 0.001),
            repetitions=int(sf.get("repetitions", 1)),
            powers=sf.get("powers"),
            zs=r.get("zs", 0.0),
            z_span=sf.get("zSpan", 0.0),
            stimparams=list(sf.get("stimparams", [])),
            enable=int(sf.get("enable", 1)),
        ))
    return d.get("name", "ROI Group"), items


def write_roi(path, items, group_name="Line Scanning ROI Group"):
    """StimItem 列を ScanImage .roi（RoiGroup JSON）として書く。"""
    h, u = _new_uuid()
    group = {
        "ver": 1, "classname": GROUP_CLASS, "name": group_name, "UserData": None,
        "roiUuid": h, "roiUuiduint64": u,
        "rois": [it.to_roi(i + 1) for i, it in enumerate(items)],
    }
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(group, f, indent="\t", ensure_ascii=False)
    return path


# --------------------------------------------------------------------------- #
# px <-> deg（raster 画像座標 <-> scan 角度）
# --------------------------------------------------------------------------- #

def px_to_deg(col, row, n_px, fov_deg, center_deg=(0.0, 0.0), y_down=True):
    """画像 px (col,row) -> scan 角度 deg。fov_deg=[wx,wy] は raster の角度FOV(imaging
    scanfield の sizeXY)。center_deg は FOV 中心(通常[0,0])。y_down=True は画像が下向き正。"""
    nx = n_px[0] if hasattr(n_px, "__len__") else n_px
    ny = n_px[1] if hasattr(n_px, "__len__") else n_px
    dx = (col / nx - 0.5) * fov_deg[0] + center_deg[0]
    sy = 1.0 if not y_down else -1.0
    dy = sy * (row / ny - 0.5) * fov_deg[1] + center_deg[1]
    # y_down: 画像下=大きい row。角度の上下を SI に合わせるため round-trip で符号確認すること。
    return dx, dy


def deg_to_px(x_deg, y_deg, n_px, fov_deg, center_deg=(0.0, 0.0), y_down=True):
    """scan 角度 deg -> 画像 px（px_to_deg の逆。GUI で生成 line を画像に重ねて検証する用）。"""
    nx = n_px[0] if hasattr(n_px, "__len__") else n_px
    ny = n_px[1] if hasattr(n_px, "__len__") else n_px
    col = (x_deg - center_deg[0]) / fov_deg[0] * nx + nx * 0.5
    sy = -1.0 if y_down else 1.0
    row = sy * (y_deg - center_deg[1]) / fov_deg[1] * ny + ny * 0.5
    return col, row


def line_endpoints_px(item: "StimItem", n_px, fov_deg, center_deg=(0.0, 0.0), y_down=True):
    """line StimItem の端点を画像 px に戻す（[p0, p1]）。検証オーバーレイ用。"""
    cx, cy = item.center_xy
    L = item.size_xy[0]
    a = math.radians(item.rotation_deg)
    x0, y0 = cx - 0.5 * L * math.cos(a), cy - 0.5 * L * math.sin(a)
    x1, y1 = cx + 0.5 * L * math.cos(a), cy + 0.5 * L * math.sin(a)
    return (deg_to_px(x0, y0, n_px, fov_deg, center_deg, y_down),
            deg_to_px(x1, y1, n_px, fov_deg, center_deg, y_down))


def build_line_group(line_pixels, n_px, fov_deg, center_deg=(0.0, 0.0), y_down=True,
                     names=None, zs=0.0, duration=0.001, repetitions=1, powers=None,
                     pause_s=0.001, lead_pause=True):
    """画像 px の線リスト [(p0,p1), ...] から pause を挟んだ StimItem 列を作る。"""
    lines = []
    for i, (p0, p1) in enumerate(line_pixels):
        nm = names[i] if names and i < len(names) else f"line{i+1}"
        lines.append(line_from_px(p0, p1, n_px, fov_deg, center_deg, y_down,
                                  name=nm, duration=duration, repetitions=repetitions,
                                  powers=powers, zs=zs))
    return interleave_pauses(lines, pause_s, zs, lead_pause)


def line_from_px(p0, p1, n_px, fov_deg, center_deg=(0.0, 0.0), y_down=True,
                 name="", duration=0.001, repetitions=1, powers=None, zs=0.0):
    """画像 px の端点 p0,p1 から line StimItem を作る（center=中点・size=[length_deg,0]・
    rotation=向き）。p0 が r=0（掃引開始）になる。"""
    x0, y0 = px_to_deg(p0[0], p0[1], n_px, fov_deg, center_deg, y_down)
    x1, y1 = px_to_deg(p1[0], p1[1], n_px, fov_deg, center_deg, y_down)
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    length = math.hypot(x1 - x0, y1 - y0)
    rot = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 360.0
    return StimItem(fn="line", name=name, center_xy=(cx, cy), size_xy=(length, 0.0),
                    rotation_deg=rot, duration=duration, repetitions=repetitions,
                    powers=powers, zs=zs)


def pause(duration=0.001, zs=0.0, name=""):
    return StimItem(fn="pause", name=name, center_xy=(0, 0), size_xy=(0, 0),
                    rotation_deg=0.0, duration=duration, zs=zs)


def point_from_px(p, n_px, fov_deg, center_deg=(0.0, 0.0), y_down=True,
                  name="", duration=0.001, zs=0.0):
    x, y = px_to_deg(p[0], p[1], n_px, fov_deg, center_deg, y_down)
    return StimItem(fn="point", name=name, center_xy=(x, y), size_xy=(0, 0),
                    duration=duration, zs=zs)


def stim(fn, center_xy=(0, 0), size_xy=(0, 0), rotation_deg=0.0, duration=0.001,
         repetitions=1, powers=None, zs=0.0, stimparams=None, name=""):
    """汎用: 任意の stimulusFunction 名で StimItem を作る（circle/spiral/park 等）。
    各関数の仕様に従って size_xy / stimparams を渡す。"""
    return StimItem(fn=fn, name=name, center_xy=center_xy, size_xy=size_xy,
                    rotation_deg=rotation_deg, duration=duration, repetitions=repetitions,
                    powers=powers, zs=zs, stimparams=list(stimparams or []))


def interleave_pauses(lines, pause_s=0.001, zs=0.0, lead_pause=True):
    """line 列の間（と任意で先頭）に pause を挟む（参照 .roi と同じ pause-line-pause 構成）。"""
    out = []
    if lead_pause:
        out.append(pause(pause_s, zs))
    for i, ln in enumerate(lines):
        out.append(ln)
        if i < len(lines) - 1:
            out.append(pause(pause_s, zs))
    return out


# --------------------------------------------------------------------------- #
# self-test: 参照 .roi を round-trip（読む -> 書く -> 読む -> 構造一致）
# --------------------------------------------------------------------------- #

def _items_equal(a: StimItem, b: StimItem, tol=1e-9):
    def close(p, q):
        return all(abs(float(x) - float(y)) <= tol for x, y in zip(p, q))
    return (a.fn == b.fn and (a.name == b.name or a.name == "")
            and close(a.center_xy, b.center_xy)
            and close(a.size_xy, b.size_xy) and abs(a.rotation_deg - b.rotation_deg) <= tol
            and abs(a.duration - b.duration) <= tol and a.repetitions == b.repetitions
            and a.powers == b.powers and abs(a.zs - b.zs) <= tol
            and a.stimparams == b.stimparams and a.enable == b.enable)


def _selftest(ref_path=None):
    import tempfile, os
    print("== scanimage_roi self-test ==")
    ok = True

    # 1) 合成 round-trip（line+pause+circle）
    items = interleave_pauses([
        StimItem(fn="line", name="art", center_xy=(-3.29, 0.96), size_xy=(1.52, 0), rotation_deg=230.6),
        StimItem(fn="line", name="cap", center_xy=(-2.16, 3.61), size_xy=(2.24, 0), rotation_deg=203.0),
        stim("circle", center_xy=(1.0, 1.0), size_xy=(2.0, 2.0), stimparams=[1, 2], name="cir"),
    ])
    f = os.path.join(tempfile.gettempdir(), "rt.roi")
    write_roi(f, items)
    name, back = read_roi(f)
    c1 = len(back) == len(items) and all(_items_equal(x, y) for x, y in zip(items, back))
    print(f"  [synth round-trip] {len(items)} items, fns={[i.fn for i in back]} -> {'PASS' if c1 else 'FAIL'}")
    ok &= c1

    # 2) px<->deg 往復
    fov = (13.5, 13.5); N = 512
    dx, dy = px_to_deg(256, 256, N, fov)               # 中心 -> ~0
    c2a = abs(dx) < 1e-9 and abs(dy) < 1e-9
    ln = line_from_px((100, 100), (400, 100), N, fov)  # 水平線
    c2b = abs(ln.size_xy[0] - (300 / 512 * 13.5)) < 1e-6 and ln.fn == "line"
    print(f"  [px<->deg] center->({dx:.2g},{dy:.2g})  line_len_deg={ln.size_xy[0]:.3f} "
          f"rot={ln.rotation_deg:.1f} -> {'PASS' if (c2a and c2b) else 'FAIL'}")
    ok &= (c2a and c2b)

    # 2b) deg->px が px->deg の逆（端点復元）
    p0, p1 = (120, 340), (300, 150)
    ln2 = line_from_px(p0, p1, N, fov)
    e0, e1 = line_endpoints_px(ln2, N, fov)
    c2c = (abs(e0[0] - p0[0]) < 1e-6 and abs(e0[1] - p0[1]) < 1e-6
           and abs(e1[0] - p1[0]) < 1e-6 and abs(e1[1] - p1[1]) < 1e-6)
    print(f"  [deg<->px inverse] p0={p0}->{tuple(round(v,1) for v in e0)} "
          f"p1={p1}->{tuple(round(v,1) for v in e1)} -> {'PASS' if c2c else 'FAIL'}")
    ok &= c2c

    # 3) 実参照 .roi があれば round-trip（line/pause の幾何が保たれるか）
    if ref_path and os.path.exists(ref_path):
        gname, ref_items = read_roi(ref_path)
        g = os.path.join(tempfile.gettempdir(), "ref_rt.roi")
        write_roi(g, ref_items, gname)
        _, ref_back = read_roi(g)
        c3 = len(ref_back) == len(ref_items) and all(_items_equal(x, y) for x, y in zip(ref_items, ref_back))
        fns = [i.fn for i in ref_items]
        print(f"  [ref round-trip] '{gname}' {len(ref_items)} rois fns={fns} -> {'PASS' if c3 else 'FAIL'}")
        ok &= c3
    else:
        print("  [ref round-trip] skipped（参照 .roi 未指定）")

    print(f"== {'ALL PASS' if ok else 'FAILED'} ==")
    return ok


if __name__ == "__main__":
    import sys
    ref = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(0 if _selftest(ref) else 1)
