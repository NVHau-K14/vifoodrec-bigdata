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
