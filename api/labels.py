"""Ten hien thi cua mo hinh (trang Danh gia, Tong quan)."""

MODEL_LABELS = {
    "hybrid": "Hybrid",
    "hybrid_c2": "Hybrid + content 2 vị trí",
    "als_implicit": "ALS implicit",
    "nau_lai": "Nấu lại",
    "pop_vung_tuoi": "Phổ biến theo vùng-tuổi",
    "pop_gan_day": "Phổ biến 2 tháng cuối",
    "pop_chung": "Phổ biến chung",
    "content": "Content (TF-IDF)",
    "random": "Ngẫu nhiên",
}
# Mo hinh chinh to mau herb, con lai la baseline (mau neutral), skill muc 6
MAIN_MODELS = {"hybrid", "hybrid_c2", "als_implicit"}


def model_label(m):
    return MODEL_LABELS.get(m, m)


def model_kind(m):
    return "chính" if m in MAIN_MODELS else "baseline"


# ---------- Phan khuc (E15): nhan va chien luoc cum sinh theo luat tu features (D15) ----------
# Dac trung cua 06e: (ten hien thi, cum tu khi CAO hon cac cum khac, cum tu khi THAP hon)
FEATURES = {
    "log_events": ("Số sự kiện (log)", "hoạt động nhiều", "hoạt động ít"),
    "log_sessions": ("Số phiên (log)", "nhiều phiên", "ít phiên"),
    "cook_per_view": ("Tỷ lệ nấu / xem", "hay nấu sau khi xem", "xem nhiều, ít nấu"),
    "rate_per_cook": ("Tỷ lệ chấm / nấu", "hay chấm điểm", "ít chấm điểm"),
    "share_chay": ("Tỷ trọng món chay", "nhiều món chay", "ít món chay"),
    "share_haisan": ("Tỷ trọng hải sản", "nhiều hải sản", "ít hải sản"),
    "share_ngot": ("Tỷ trọng món ngọt, đồ uống", "nhiều món ngọt, đồ uống", "ít món ngọt"),
    "share_nhanh": ("Tỷ trọng món nhanh", "chuộng món nhanh", "ít món nhanh"),
    "share_cay": ("Tỷ trọng món cay", "thích cay", "ít ăn cay"),
    "share_canh": ("Tỷ trọng canh/súp", "nhiều canh/súp", "ít canh/súp"),
    "share_lau": ("Tỷ trọng lẩu", "hay nấu lẩu", "ít nấu lẩu"),
    "slot_0": ("Tỷ trọng bữa sáng", "nấu bữa sáng", "ít nấu bữa sáng"),
    "slot_1": ("Tỷ trọng bữa trưa", "nấu bữa trưa", "ít nấu bữa trưa"),
    "slot_2": ("Tỷ trọng bữa tối", "nấu bữa tối", "ít nấu bữa tối"),
    "slot_3": ("Tỷ trọng bữa khuya", "nấu khuya", "ít nấu khuya"),
    "share_weekend": ("Tỷ trọng cuối tuần", "nấu cuối tuần", "nấu ngày thường"),
    "cat_entropy": ("Độ đa dạng nhóm món", "nấu đa dạng", "nấu ít loại món"),
    "avg_rating": ("Điểm chấm trung bình", "chấm điểm cao", "chấm điểm thấp"),
}

# Bang luat chien luoc: (dac trung, huong +1 = cao / -1 = thap, cau de xuat). Moi cum chi giu 1 cau dac trung nhat,
# va trong cung mot k khong cum nao lap cau cua cum khac (describe_clusters). Bang nay chep vao D16 de bao cao trich duoc.
STRATEGY_RULES = [
    ("share_chay", 1, "Ưu tiên bộ sưu tập món chay, thêm món chay mới vào gợi ý"),
    ("share_nhanh", 1, "Gợi ý món nhanh, ít bước cho ngày bận rộn"),
    ("share_haisan", 1, "Đẩy món hải sản và món ăn kèm (luật FP-Growth)"),
    ("share_cay", 1, "Gợi ý món cay, món nhậu vào buổi tối và cuối tuần"),
    ("share_ngot", 1, "Gợi ý chè, bánh, đồ uống cho bữa phụ"),
    ("share_canh", 1, "Gợi ý mâm cơm: món mặn kèm canh (luật FP-Growth)"),
    ("share_lau", 1, "Gợi ý lẩu vào cuối tuần"),
    ("slot_0", 1, "Gửi gợi ý bữa sáng vào đầu ngày"),
    ("slot_3", 1, "Gợi ý món ăn khuya, món nhanh vào buổi tối muộn"),
    ("slot_1", 1, "Gửi gợi ý bữa trưa trước giờ nấu trưa"),
    ("slot_2", 1, "Gửi gợi ý bữa tối vào buổi chiều"),
    ("share_weekend", 1, "Tập trung gợi ý vào cuối tuần"),
    ("log_events", -1, "Kích hoạt lại: gợi ý món phổ biến theo vùng-tuổi"),
    ("log_sessions", -1, "Kích hoạt lại: gợi ý món phổ biến theo vùng-tuổi"),
    ("cook_per_view", -1, "Xem nhiều nấu ít: ưu tiên món dễ làm, ít nguyên liệu"),
    ("log_events", 1, "Người dùng tích cực: giới thiệu món mới trong danh mục trước"),
    ("cat_entropy", 1, "Khẩu vị đa dạng: tăng tỷ trọng món khám phá (content)"),
    ("cat_entropy", -1, "Ít loại món: gợi ý món cùng nhóm, mở rộng dần sang nhóm gần"),
    ("rate_per_cook", 1, "Hay chấm điểm: mời đánh giá để cải thiện gợi ý"),
]
DEFAULT_STRATEGY = "Giữ gợi ý cá nhân hybrid mặc định"
Z_STRONG = 0.5   # do lech (z giua cac cum) toi thieu de mot dac trung duoc coi la noi bat


def cluster_z(clusters):
    """z cua tung dac trung theo cac cum cung k (trung binh va do lech chuan khong trong so)."""
    feats = list(FEATURES)
    stats = {}
    for f in feats:
        xs = [c["features"][f] for c in clusters]
        m = sum(xs) / len(xs)
        sd = (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5
        stats[f] = (m, sd)
    return {c["cluster"]: {f: (c["features"][f] - stats[f][0]) / stats[f][1] if stats[f][1] > 0 else 0.0
                           for f in feats} for c in clusters}, {f: stats[f][0] for f in feats}


def describe_cluster(z):
    """(nhan, 3 dac trung noi bat, cac cau de xuat ung vien [(|z|, cau)]) tu z cua mot cum."""
    order = sorted(z, key=lambda f: -abs(z[f]))
    top = [{"feature": f, "label": FEATURES[f][0], "z": round(z[f], 2),
            "text": FEATURES[f][1] if z[f] > 0 else FEATURES[f][2]} for f in order[:3]]
    lab = " · ".join(t["text"] for t in top[:2])
    cand = []
    for f in order:
        if abs(z[f]) < Z_STRONG:
            break
        d = 1 if z[f] > 0 else -1
        cand += [(abs(z[f]), text) for rf, rd, text in STRATEGY_RULES if rf == f and rd == d]
    return lab[:1].upper() + lab[1:], top, cand


def describe_clusters(zmap):
    """{cum: (nhan, dac trung noi bat, [1 cau de xuat])} cho cac cum cung k.

    Gan tham lam theo |z| giam dan tren toan bo cac cap (cum, cau ung vien): cum nao lech manh nhat o mot dac trung
    thi nhan cau cua dac trung do; moi cau chi gan cho 1 cum. Cum khong con cau nao thi dung DEFAULT_STRATEGY.
    """
    desc = {c: describe_cluster(z) for c, z in zmap.items()}
    pairs = sorted(((az, c, text) for c, (_, _, cand) in desc.items() for az, text in cand), key=lambda x: (-x[0], x[1]))
    chosen, used = {}, set()
    for _, c, text in pairs:
        if c not in chosen and text not in used:
            chosen[c] = text
            used.add(text)
    return {c: (lab, top, [chosen.get(c, DEFAULT_STRATEGY)]) for c, (lab, top, _) in desc.items()}
