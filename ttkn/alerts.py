"""Cảnh báo quá hạn / sắp đến hạn; đến hạn báo cáo UBND."""
from __future__ import annotations

from datetime import date, timedelta

from . import db
from .util import add_working_days, parse_date


def han_kn(kn: dict, kl: dict, cd: dict | None) -> date | None:
    """Hạn thực hiện hiệu lực của kiến nghị: văn bản chỉ đạo UBND > hạn riêng của KN > hạn trong KL."""
    for v in ((cd or {}).get("han_hoan_thanh"), kn.get("han"), kl.get("han_thuc_hien")):
        d = parse_date(v)
        if d:
            return d
    return None


def latest_chi_dao(conn, kl_id: int) -> dict | None:
    return db.one(conn, "SELECT * FROM van_ban_chi_dao WHERE kl_id=? "
                        "ORDER BY COALESCE(ngay_vb,'') DESC, id DESC", (kl_id,))


def han_bao_cao_kl(kl: dict, cd: dict | None, ngay_lam_viec: int = 45) -> date | None:
    """Hạn báo cáo UBND: ghi trong chỉ đạo; nếu không có thì hạn hoàn thành; cuối cùng KL + 45 ngày làm việc."""
    for v in ((cd or {}).get("han_bao_cao"), (cd or {}).get("han_hoan_thanh"), kl.get("han_thuc_hien")):
        d = parse_date(v)
        if d:
            return d
    nb = parse_date(kl.get("ngay_ban_hanh"))
    return add_working_days(nb, ngay_lam_viec) if nb else None


def kn_ton(conn, today: date | None = None) -> list[dict]:
    """Mọi kiến nghị chưa hoàn thành của các KL đang theo dõi, kèm hạn và số ngày quá hạn."""
    today = today or date.today()
    out = []
    kls = db.rows(conn, "SELECT * FROM ket_luan WHERE dang_theo_doi=1")
    for kl in kls:
        cd = latest_chi_dao(conn, kl["id"])
        for kn in db.rows(conn, "SELECT * FROM kien_nghi WHERE kl_id=? AND tinh_trang<>'xong' ORDER BY stt", (kl["id"],)):
            h = han_kn(kn, kl, cd)
            kn = {**kn, "ma_kl": kl["ma_kl"], "so_ky_hieu": kl["so_ky_hieu"], "han_hieu_luc": h,
                  "chi_dao": cd, "kl_trich_yeu": kl["trich_yeu"],
                  "qua_han_ngay": (today - h).days if h else None}
            out.append(kn)
    return out


def canh_bao_don_doc(conn, today: date | None = None, bao_truoc: int = 7) -> list[dict]:
    """Gom theo (KL, đơn vị): quá hạn hoặc sắp đến hạn mà còn kiến nghị tồn."""
    today = today or date.today()
    groups: dict[tuple, dict] = {}
    for kn in kn_ton(conn, today):
        h = kn["han_hieu_luc"]
        if h is None:
            muc = "khong_co_han"
        elif kn["qua_han_ngay"] > 0:
            muc = "qua_han"
        elif (h - today).days <= bao_truoc:
            muc = "sap_den_han"
        else:
            continue
        g = groups.setdefault((kn["ma_kl"], kn["don_vi"]), {
            "ma_kl": kn["ma_kl"], "kl_id": kn["kl_id"], "don_vi": kn["don_vi"], "so_ky_hieu": kn["so_ky_hieu"],
            "kn": [], "muc": muc, "han": h, "qua_han_ngay": kn["qua_han_ngay"], "chi_dao": kn["chi_dao"]})
        g["kn"].append(kn)
        # mức nặng nhất của nhóm
        rank = {"qua_han": 3, "sap_den_han": 2, "khong_co_han": 1}
        if rank[muc] > rank[g["muc"]]:
            g["muc"] = muc
        if kn["qua_han_ngay"] is not None and (g["qua_han_ngay"] is None or kn["qua_han_ngay"] > g["qua_han_ngay"]):
            g["qua_han_ngay"], g["han"] = kn["qua_han_ngay"], h
    # đã đôn đốc gần đây?
    for g in groups.values():
        last = db.one(conn, "SELECT ngay_vb, han_tra_loi, so_vb FROM van_ban_don_doc WHERE kl_id=? AND don_vi=? "
                            "ORDER BY COALESCE(ngay_vb,'') DESC, id DESC", (g["kl_id"], g["don_vi"]))
        g["lan_don_doc"] = db.one(conn, "SELECT COUNT(*) c FROM van_ban_don_doc WHERE kl_id=? AND don_vi=?",
                                  (g["kl_id"], g["don_vi"]))["c"]
        g["don_doc_cuoi"] = last
    order = {"qua_han": 0, "sap_den_han": 1, "khong_co_han": 2}
    return sorted(groups.values(), key=lambda g: (order[g["muc"]], -(g["qua_han_ngay"] or -9999)))


def den_han_bao_cao(conn, today: date | None = None, cfg: dict | None = None) -> list[dict]:
    """KL đang theo dõi, đã/đang đến hạn báo cáo UBND mà chưa báo cáo."""
    today = today or date.today()
    nlv = ((cfg or {}).get("dondoc") or {}).get("ngay_lam_viec_bao_cao", 45)
    bt = ((cfg or {}).get("dondoc") or {}).get("bao_truoc_ngay", 7)
    out = []
    for kl in db.rows(conn, "SELECT * FROM ket_luan WHERE dang_theo_doi=1"):
        h = han_bao_cao_kl(kl, latest_chi_dao(conn, kl["id"]), nlv)
        if h is None or kl.get("da_bao_cao_ubnd"):
            continue
        if h <= today + timedelta(days=bt):
            tong = db.one(conn, "SELECT COUNT(*) c, SUM(tinh_trang='xong') x FROM kien_nghi WHERE kl_id=?", (kl["id"],))
            out.append({"ma_kl": kl["ma_kl"], "kl_id": kl["id"], "so_ky_hieu": kl["so_ky_hieu"],
                        "trich_yeu": kl["trich_yeu"], "han_bao_cao": h, "con_ngay": (h - today).days,
                        "tong_kn": tong["c"], "xong": tong["x"] or 0})
    return sorted(out, key=lambda r: r["han_bao_cao"])


def thong_ke(conn, today: date | None = None) -> dict:
    today = today or date.today()
    r = db.one(conn, "SELECT COUNT(*) kl FROM ket_luan WHERE dang_theo_doi=1")
    k = db.one(conn, "SELECT COUNT(*) tong, SUM(tinh_trang='xong') xong, SUM(tinh_trang='dang') dang, "
                     "SUM(tinh_trang='chua') chua FROM kien_nghi k JOIN ket_luan l ON l.id=k.kl_id WHERE l.dang_theo_doi=1")
    ton = kn_ton(conn, today)
    return {"kl_dang_theo_doi": r["kl"], "kn_tong": k["tong"] or 0, "kn_xong": k["xong"] or 0,
            "kn_dang": k["dang"] or 0, "kn_chua": k["chua"] or 0,
            "kn_qua_han": sum(1 for x in ton if (x["qua_han_ngay"] or 0) > 0),
            "don_vi_qua_han": len({x["don_vi"] for x in ton if (x["qua_han_ngay"] or 0) > 0})}
