"""
eval_features_check.py - Do chinh xac cua dac trung mon (buoc 03, D05) tren 100 mon kiem tra tay (D19).

Cot kiem_tra cua file mau: "đúng" (ca 7 thuoc tinh dung) hoac danh sach thuoc tinh sai, cach nhau dau phay
(vd "main_method, is_vegetarian"). O trong = chua ket luan (chi co o ban lan 1) -> bo ca dong khoi mau so.
  - Ban cuoi : data/output/features_check_sample.csv        (sau khi chot cach cham is_spicy)
  - Ban lan 1: data/output/features_check_sample_lan1.csv   (truoc khi chot, de so sanh)
is_spicy them cach (b), dinh nghia mo rong, TU DEM tu nguyen_lieu (uoc tinh, chua kiem tung mon):
  cay neu co ot tuoi ("ớt" dung rieng, ớt băm, ớt sừng, ớt hiểm, ớt trái…), ớt khô, ớt bột, sa tế, kim chi;
  khong tinh ớt chuông, tương ớt, tiêu, mù tạt vàng.
  loi (b) = may khac (b): may false ma co ot; may true ma chi co ot chuong (dong 76); may true ma khong co
  nguyen lieu cay nao (dong 89, chi co mu tat vang; nguoi kiem cung cham sai o ban cuoi).

Dau vao : 2 file CSV tren (khong doc HDFS, khong chay Spark)
Dau ra  : data/output/features_check_report.json
Chay tren may:  python scripts/eval_features_check.py
"""
import csv
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "data", "output")
ATTRS = ["main_protein", "main_method", "dish_category", "dish_type_fixed", "is_vegetarian", "is_spicy", "season"]
sys.stdout.reconfigure(encoding="utf-8")


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def wrong_attrs(row):
    v = row["kiem_tra"].strip()
    if not v:
        return None                                   # chua ket luan
    if v == "đúng":
        return set()
    out = {a.strip() for a in v.split(",") if a.strip()}
    bad = out - set(ATTRS)
    if bad:
        raise ValueError(f"food_id {row['food_id']}: thuoc tinh la {bad}")
    return out


def accuracy(rows):
    judged = [(r, wrong_attrs(r)) for r in rows]
    skipped = [r["food_id"] for r, w in judged if w is None]
    judged = [(r, w) for r, w in judged if w is not None]
    n = len(judged)
    per_attr = {a: {"correct": sum(a not in w for _, w in judged), "n": n,
                    "accuracy_pct": round(100 * sum(a not in w for _, w in judged) / n, 1),
                    "wrong_food_ids": [int(r["food_id"]) for r, w in judged if a in w]} for a in ATTRS}
    all7 = sum(not w for _, w in judged)
    six = {f"all_except_{x}": round(100 * sum(not (w - {x}) for _, w in judged) / n, 1) for x in ("season", "is_spicy")}
    return {"n_judged": n, "n_skipped_unresolved": len(skipped), "skipped_food_ids": [int(x) for x in skipped],
            "per_attribute": per_attr,
            "per_dish": {"all_7_correct": all7, "all_7_correct_pct": round(100 * all7 / n, 1),
                         "pct_correct_6_of_7": six,
                         "n_wrong_attrs_hist": {str(k): sum(len(w) == k for _, w in judged) for k in range(0, 4)}},
            "attr_accuracy_mean_pct": round(sum(v["accuracy_pct"] for v in per_attr.values()) / len(ATTRS), 1)}


# --- is_spicy cach (b): dem tu nguyen lieu ---
def ing_tokens(s):
    return [t.strip().lower() for t in s.split(",") if t.strip()]


def is_hot(t):
    """Nguyen lieu cay theo dinh nghia (b)."""
    if t.startswith("ớt chuông") or t.startswith("tương ớt"):
        return False
    if t == "ớt" or t.startswith("ớt "):               # ot tuoi dung rieng, ot bam / sung / hiem / trai / kho / bot
        return True
    return "sa tế" in t or "kim chi" in t


def spicy_b(rows):
    errs, rows_out = [], []
    for i, r in enumerate(rows):
        toks = ing_tokens(r["nguyen_lieu"])
        hot = [t for t in toks if is_hot(t)]
        bell = [t for t in toks if t.startswith("ớt chuông")]
        machine = r["is_spicy"].strip().lower() == "true"
        kind = None
        if not machine and hot:
            kind = "máy false, có ớt / sa tế / kim chi"
        elif machine and not hot and bell:
            kind = "máy true, chỉ có ớt chuông"
        elif machine and not hot:
            kind = "máy true, không có nguyên liệu cay"
        rec = {"csv_line": i + 2, "food_id": int(r["food_id"]), "dish_name": r["dish_name"], "machine": machine,
               "hot_ingredients": hot, "bell_pepper": bell,
               "not_counted": [t for t in toks if t.startswith(("tương ớt", "mù tạt"))], "case": kind}
        rows_out.append(rec)
        if kind:
            errs.append(rec)
    n = len(rows)
    return {"definition": "cay nếu nguyen_lieu có ớt tươi ('ớt' đứng riêng, ớt băm, ớt sừng, ớt hiểm, ớt trái…), "
                          "ớt khô, ớt bột, sa tế, kim chi; không tính ớt chuông, tương ớt, tiêu, mù tạt vàng",
            "error_rule": "máy khác (b): máy false mà có ớt; máy true mà chỉ có ớt chuông; máy true mà không có "
                          "nguyên liệu cay nào (chỉ mù tạt vàng)",
            "estimate_note": "Ước tính tự đếm từ nguyen_lieu, chưa kiểm từng món",
            "n": n, "errors": len(errs), "accuracy_pct": round(100 * (n - len(errs)) / n, 1),
            "positives_b": sum(bool(x["hot_ingredients"]) for x in rows_out),
            "positives_machine": sum(x["machine"] for x in rows_out),
            "errors_by_case": {k: sum(e["case"] == k for e in errs) for k in sorted({e["case"] for e in errs})},
            "error_list": errs}


def main():
    final, lan1 = load("features_check_sample.csv"), load("features_check_sample_lan1.csv")
    assert [r["food_id"] for r in final] == [r["food_id"] for r in lan1], "hai ban khac thu tu mon"
    rep = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "note": "100 món chọn theo hash ở bước 03 (D11); máy = nhãn của luật 03, người kiểm tay ghi thuộc tính sai. "
                   "Không sửa luật 03, không chạy lại pipeline (D19).",
           "attributes": ATTRS,
           "final": accuracy(final), "lan1": accuracy(lan1), "is_spicy_b": spicy_b(final),
           "season_non_default": {"machine_not_khong": sum(r["season"] != "không" for r in final), "n": len(final)}}
    path = os.path.join(OUT, "features_check_report.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    f, l1, b = rep["final"], rep["lan1"], rep["is_spicy_b"]
    print(f"{'thuoc tinh':<16}{'ban cuoi':>10}{'lan 1':>10}")
    for a in ATTRS:
        print(f"{a:<16}{f['per_attribute'][a]['accuracy_pct']:>9}%{l1['per_attribute'][a]['accuracy_pct']:>9}%")
    print(f"{'is_spicy (b)':<16}{b['accuracy_pct']:>9}%   (uoc tinh, {b['errors']} loi)")
    print(f"dung ca 7: {f['per_dish']['all_7_correct_pct']}% (cuoi, n={f['n_judged']}), "
          f"{l1['per_dish']['all_7_correct_pct']}% (lan 1, n={l1['n_judged']}, bo {l1['n_skipped_unresolved']} dong chua ket luan)")
    print("6/7:", f["per_dish"]["pct_correct_6_of_7"], "| lan1:", l1["per_dish"]["pct_correct_6_of_7"])
    print("Loi is_spicy (b) - UOC TINH, chua kiem tung mon:")
    for e in b["error_list"]:
        print(f"  dong {e['csv_line']:>3}  {e['food_id']:>5}  {e['dish_name']:<45} may={str(e['machine']).lower():<5} "
              f"{e['case']}: {', '.join(e['hot_ingredients'] or e['bell_pepper'] or e['not_counted'])}")
    print(f"da ghi {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
