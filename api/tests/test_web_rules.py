"""Luat cua skill vifood-dashboard (muc 1, 3, 7, 9) kiem tra tu dong tren ma nguon web/."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
NAV = ["Tổng quan", "Hành vi ăn uống", "Món ăn", "Phân khúc người dùng", "Gợi ý món", "Đánh giá mô hình", "Thời gian thực"]


def files(pattern):
    return sorted(WEB.glob(pattern))


def test_no_hex_outside_theme_and_charts():
    # skill muc 9: grep -rn "#[0-9A-Fa-f]{6}" web/js web/*.html (tru theme.css, charts.js)
    bad = []
    for f in files("js/*.js") + files("*.html") + files("css/*.css"):
        if f.name in ("theme.css", "charts.js"):
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if HEX.search(line):
                bad.append(f"{f.name}:{i}")
    assert bad == []


def test_no_cdn():
    # skill muc 1: khong CDN; anh mon lay tu image_link luc chay, khong nam trong ma nguon
    bad = [f.name for f in files("*.html") + files("css/*.css") + files("js/*.js")
           if re.search(r"https?://", f.read_text(encoding="utf-8"))]
    assert bad == []


def test_nav_order():
    js = (WEB / "js" / "layout.js").read_text(encoding="utf-8")
    labels = re.findall(r"label: '([^']+)'", js)
    hrefs = re.findall(r"href: '([^']+)'", js)
    assert labels == NAV
    assert all((WEB / h).exists() for h in hrefs)


def test_pages_shell():
    for f in files("*.html"):
        s = f.read_text(encoding="utf-8")
        assert '<html lang="vi">' in s, f.name
        assert 'id="nav"' in s and 'id="head-pills"' in s and "js/layout.js" in s, f.name
        assert 'name="viewport"' in s, f.name
        assert "lorem" not in s.lower(), f.name


def test_img_have_alt():
    for f in files("*.html") + files("js/*.js"):
        for m in re.finditer(r"<img\b[^>]*>", f.read_text(encoding="utf-8")):
            assert "alt=" in m.group(0), f"{f.name}: {m.group(0)[:60]}"


def enclosing_object(src, pos):
    """Doan {...} nho nhat bao quanh vi tri pos (dem ngoac nhon, du cho JS cua du an)."""
    depth, i = 0, pos
    while i >= 0:
        if src[i] == "}":
            depth += 1
        elif src[i] == "{":
            if depth == 0:
                break
            depth -= 1
        i -= 1
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return src[i:]


def bar_series(src):
    return [enclosing_object(src, m.start()) for m in re.finditer(r"type:\s*'bar'", src)]


def test_no_empty_bar_series():
    # Series cot rong (data: []) chi de lam chu giai van chiem 1 cho trong nhom cot -> cot manh, lech trai.
    # Chu giai viet bang HTML (vd MONTH_LEGEND), hoac series do phai dat barGap: '-100%'.
    bad = []
    for f in files("js/*.js"):
        for obj in bar_series(f.read_text(encoding="utf-8")):
            if re.search(r"data:\s*\[\s*\]", obj) and not re.search(r"barGap:\s*'-100%'", obj):
                bad.append(f"{f.name}: {' '.join(obj.split())[:70]}")
    assert bad == []


def test_empty_bar_rule_catches_legend_series():
    # Kiem tra chinh luat tren: ban monthlyBars cu (3 series rong de lam chu giai) phai bi bat
    old = "series: [{ name: 'Lượt nấu', type: 'bar', data: xs }, { name: 'Train', type: 'bar', data: [], itemStyle: { color: c } }]"
    objs = bar_series(old)
    assert len(objs) == 2 and re.search(r"data:\s*\[\s*\]", objs[1]) and not re.search(r"data:\s*\[\s*\]", objs[0])


def test_charts_use_vifood_theme():
    js = (WEB / "js" / "charts.js").read_text(encoding="utf-8")
    assert "registerTheme('vifood'" in js and "echarts.init(el, 'vifood', { renderer: 'svg' })" in js
    others = [f.name for f in files("js/*.js") if f.name != "charts.js" and "echarts.init" in f.read_text(encoding="utf-8")]
    assert others == []
