"""E15 phan khuc nguoi dung (cum K-means k = 3 / 8 / 11), E16 nguoi dung trong mot cum k = 8.

Chi E15 co persona (persona_kiem_chung = persona pho bien nhat trong cum, tinh o 06e), kem verify_only = true:
dashboard ghi "chi de kiem chung". E16 khong tra truth cua tung user.
"""
from fastapi import APIRouter, HTTPException, Query

from ..cache import cached
from ..db import get_db
from ..labels import FEATURES, cluster_z, describe_cluster
from .overview import reports

router = APIRouter(prefix="/segments", tags=["Phân khúc người dùng"])

GROUPS = ["ấm", "ít", "lạnh"]
K_VALUES = (3, 8, 11)


@cached
def clusters_of(k):
    return list(get_db().clusters.find({"k": k}, {"_id": 0}).sort("cluster", 1))


@router.get("", summary="E15 – các cụm người dùng: quy mô, hồ sơ 18 đặc trưng, nhãn, chiến lược, chất lượng phân cụm")
def segments(k: int = Query(8, description="số cụm: 3, 8 hoặc 11")):
    if k not in K_VALUES:
        raise HTTPException(422, "k phải là 3, 8 hoặc 11")
    cl = clusters_of(k)
    z, means = cluster_z(cl) if cl else ({}, {})
    km = reports().get("model_kmeans_report", {})
    out = []
    for c in cl:
        label, top, strategy = describe_cluster(z[c["cluster"]])
        out.append({"cluster": c["cluster"], "n_users": c["n_users"], "features": c["features"],
                    "z": {f: round(v, 3) for f, v in z[c["cluster"]].items()},
                    "label": label, "top_features": top, "strategy": strategy,
                    "persona_kiem_chung": c.get("persona_kiem_chung"), "persona_share": c.get("persona_share"),
                    "verify_only": True})
    return {"k": k, "dashboard_k": km.get("dashboard_k"), "n_users": sum(c["n_users"] for c in cl),
            "best_by_silhouette": km.get("best_by_silhouette"),
            "quality": km.get("search", []),
            "feature_names": [{"feature": f, "label": v[0]} for f, v in FEATURES.items()],
            "feature_means": means, "clusters": out, "verify_only": True}


@router.get("/8/{cluster}", summary="E16 – người dùng trong một cụm (k = 8): vùng, tuổi, nhóm, user mẫu")
def segment_users(cluster: int, sample: int = Query(8, ge=0, le=12)):
    if cluster not in {c["cluster"] for c in clusters_of(8)}:
        raise HTTPException(404, f"Không có cụm {cluster} (k = 8)")
    count = lambda f: [{"$group": {"_id": f, "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]  # noqa: E731
    # $match tren cluster_k8 dung index cluster_k8_1; user mau: user_id nho nhat co lich su (co dinh)
    res = next(get_db().users.aggregate([
        {"$match": {"cluster_k8": cluster}},
        {"$facet": {
            "total": [{"$count": "n"}],
            "by_region": count("$region"), "by_age": count("$age_group"), "by_group": count("$group"),
            "sample": [{"$sort": {"_id": 1}}, {"$match": {"history.2": {"$exists": True}}}, {"$limit": sample},
                       {"$project": {"region": 1, "age_group": 1, "group": 1, "profile.n_cook": 1,
                                     "profile.pref_slot": 1}}],
        }}]))
    total = res["total"][0]["n"] if res["total"] else 0
    rows = lambda key, order=None: sorted(  # noqa: E731
        [{"value": r["_id"], "n_users": r["n"], "share_pct": round(100 * r["n"] / total, 2) if total else 0}
         for r in res[key]], key=lambda r: order.index(r["value"]) if order and r["value"] in order else 0)
    return {"cluster": cluster, "n_users": total,
            "by_region": rows("by_region", ["Bắc", "Trung", "Nam"]), "by_age": rows("by_age"),
            "by_group": rows("by_group", GROUPS),
            "sample_users": [{"user_id": u["_id"], "region": u.get("region"), "age_group": u.get("age_group"),
                              "group": u.get("group"), "n_cook": (u.get("profile") or {}).get("n_cook"),
                              "pref_slot": (u.get("profile") or {}).get("pref_slot")} for u in res["sample"]]}
