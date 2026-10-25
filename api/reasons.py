"""Cau ly do goi y va mau cham theo source (D15 cau 2, skill vifood-dashboard muc 5)."""

DOT = {"als": "herb", "rep": "herb", "content_slot": "chili", "content": "chili", "pop": "neutral", "fill": "neutral"}
ALS = "Người có khẩu vị giống bạn cũng hay nấu món này"


def pop_reason(region, age_group):
    """Cau cua 06f: pop la pho bien theo vung-tuoi."""
    if region and age_group:
        return f"Đang được nhiều người {age_group} tuổi ở miền {region} nấu"
    return "Đang được nhiều người nấu"


def fill_reason(filter_label):
    """Mon bu xep theo stats.cook_rank toan danh muc, khong theo vung hay bua."""
    return f"{filter_label} được nấu nhiều trong danh mục" if filter_label else "Được nấu nhiều trong danh mục"


def content_reason(because_name, cooked):
    name = because_name or "bạn từng chọn"
    return f"Giống món {name} bạn đã nấu" if cooked else f"Giống món {name} bạn đã xem"


def rep_reason(n_cook):
    return f"Bạn đã nấu món này {n_cook} lần" if n_cook else "Bạn đã nấu món này"
