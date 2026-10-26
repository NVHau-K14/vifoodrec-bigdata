"""
nb_style.py - Kieu bieu do dung chung cho notebook 05, 06, 09_10 (anh PNG cho bao cao).

Mau lay theo token cua dashboard (skill vifood-dashboard): herb la mau du lieu chinh, nen trang, chu ink / muted.
Nhieu chuoi (toi da 4) dung thu tu SERIES co dinh, da kiem tra tach mau voi nguoi mu mau (validator cua skill dataviz);
moi chuoi luon co chu giai hoac nhan truc tiep, khong chi phan biet bang mau.

  from nb_style import *          # C, SERIES, SEQ, load(), out(), save(), bar_labels()
"""
import json
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "data", "output")
IMG = os.path.join(ROOT, "docs", "images")

C = {"ink": "#17201B", "ink2": "#2B3530", "muted": "#5B6660", "line": "#CDD3CB", "grid": "#EEF1EC",
     "herb": "#1E6B4A", "herb_dark": "#134A33", "herb_mid": "#9CC7B0", "herb_soft": "#E3F0E8",
     "chili": "#C2481B", "slate": "#3F4B45", "neutral": "#8A958F", "blue": "#2a78d6", "amber": "#eda100"}
SERIES = [C["herb"], C["blue"], C["chili"], C["amber"]]          # thu tu co dinh, khong xoay vong
SEQ = LinearSegmentedColormap.from_list("herb", ["#EEF4F0", "#6FAE8D", "#0F4A32"])
DIV = LinearSegmentedColormap.from_list("div", [C["blue"], "#F2F2EF", C["chili"]])   # lift < 1 / = 1 / > 1

mpl.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.titlecolor": C["ink"], "axes.labelcolor": C["muted"],
    "axes.edgecolor": C["line"], "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": C["grid"], "grid.linewidth": 0.8,
    "axes.axisbelow": True, "xtick.color": C["muted"], "ytick.color": C["muted"], "xtick.major.size": 0,
    "ytick.major.size": 0, "legend.frameon": False, "legend.fontsize": 9, "figure.facecolor": "white",
    "axes.facecolor": "white", "savefig.facecolor": "white", "figure.dpi": 110, "lines.linewidth": 2,
    "axes.prop_cycle": mpl.cycler(color=SERIES),
})
NOTE = "Dữ liệu hành vi là mô phỏng (ViFoodRec)."

# Nhan truc kieu Viet Nam (dau phay thap phan); container khong co locale vi_VN nen sua thang ScalarFormatter
_scalar_call = mpl.ticker.ScalarFormatter.__call__
mpl.ticker.ScalarFormatter.__call__ = lambda self, x, pos=None: _scalar_call(self, x, pos).replace(".", ",")


def load(name):
    """Doc data/output/<name> (.json)."""
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def save(fig, name, note=NOTE):
    """Ghi docs/images/nb_<name>.png (150 dpi), kem dong ghi chu nguon o goc duoi."""
    if note:
        fig.text(0.01, 0.005, note, fontsize=8, color=C["muted"], ha="left", va="bottom")
    os.makedirs(IMG, exist_ok=True)
    path = os.path.join(IMG, f"nb_{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.15)
    print("da ghi", os.path.relpath(path, ROOT).replace("\\", "/"))
    return path


def fmt(v, nd=0):
    """So kieu Viet Nam: 1.234,5"""
    s = f"{v:,.{nd}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def bar_labels(ax, bars, nd=0, suffix="", horizontal=False, pad=3):
    """Nhan so o dau cot (chu mau ink, khong dung mau chuoi)."""
    for b in bars:
        v = b.get_width() if horizontal else b.get_height()
        txt = fmt(v, nd) + suffix
        if horizontal:
            ax.annotate(txt, (v, b.get_y() + b.get_height() / 2), xytext=(pad, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=8.5, color=C["ink2"])
        else:
            ax.annotate(txt, (b.get_x() + b.get_width() / 2, v), xytext=(0, pad), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.5, color=C["ink2"])
