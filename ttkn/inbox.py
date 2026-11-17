"""Bước 3/5: văn bản đến → lọc → ghép với kết luận → đánh giá kết quả thực hiện (chờ duyệt)."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import db, prompts
from .docs import blocks_for, quick_text
from .util import iso, ma_kl as make_ma_kl, safe_name, sha256_file, so_kl, parse_date

SUPPORTED = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".txt"}


# ------------------------------------------------------------- đăng ký tệp
def register(conn, main: str | Path, attachments: list[str | Path] = (), **meta) -> int | None:
    """Ghi 1 văn bản đến. Trả id, hoặc None nếu đã có (trùng nội dung)."""
    main = Path(main)
    sha = sha256_file(main)
    if db.one(conn, "SELECT id FROM van_ban_den WHERE sha=?", (sha,)):
        return None
    return db.insert(conn, "van_ban_den", {
        "sha": sha, "ten": meta.get("ten") or main.name, "duong_dan": str(main),
        "dinh_kem": json.dumps([str(a) for a in attachments], ensure_ascii=False),
        "ngay_den": iso(meta.get("ngay_den")), "so_ky_hieu": meta.get("so_ky_hieu", ""),
        "don_vi_gui": meta.get("don_vi_gui", ""), "trich_yeu": meta.get("trich_yeu", ""),
        "nguon": meta.get("nguon", "thu_cong"),
    })


def import_folder(conn, folder: str | Path) -> list[int]:
    """Mỗi thư mục con = 1 văn bản (tệp đầu tiên là văn bản chính, các tệp còn lại là đính kèm);
    tệp nằm trực tiếp trong thư mục gốc = mỗi tệp 1 văn bản."""
    folder = Path(folder)
    ids: list[int] = []
    for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
        files = sorted(f for f in sub.iterdir() if f.suffix.lower() in SUPPORTED)
        if files:
            i = register(conn, files[0], files[1:], ten=sub.name, nguon="thu_muc")
            if i:
                ids.append(i)
    for f in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED):
        i = register(conn, f, nguon="thu_muc")
        if i:
            ids.append(i)
    return ids


def save_upload(data_dir: str | Path, name: str, content: bytes) -> Path:
    d = Path(data_dir) / "vanban_den" / "tai_len"
    d.mkdir(parents=True, exist_ok=True)
    p = d / safe_name(name, 120)
    p.write_bytes(content)
    return p


# --------------------------------------------------------------- lọc sơ bộ
def keyword_hit(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in keywords)


def _kl_catalog(conn) -> str:
    rows = db.rows(conn, "SELECT ma_kl, so_ky_hieu, ngay_ban_hanh, trich_yeu, don_vi_duoc_thanh_tra "
                         "FROM ket_luan ORDER BY ngay_ban_hanh")
    return "\n".join(f"- {r['ma_kl']} | {r['so_ky_hieu']} ngày {r['ngay_ban_hanh']} | "
                     f"{(r['trich_yeu'] or '')[:150]} | {r['don_vi_duoc_thanh_tra'] or ''}" for r in rows)


# ------------------------------------------------------------ phân loại
def classify(conn, llm, vb_id: int, cfg: dict) -> dict:
    vb = db.one(conn, "SELECT * FROM van_ban_den WHERE id=?", (vb_id,))
    blocks, skipped = blocks_for([vb["duong_dan"]], cfg["llm"]["max_pdf_pages"] // 5 or 20)
    head = (f"Metadata từ cổng: số ký hiệu={vb['so_ky_hieu']}; đơn vị gửi={vb['don_vi_gui']}; "
            f"trích yếu={vb['trich_yeu']}; ngày đến={vb['ngay_den']}\n\n"
            f"DANH SÁCH KẾT LUẬN ĐANG THEO DÕI:\n{_kl_catalog(conn)}")
    res = llm.structured(prompts.SYS_CLASSIFY, [{"type": "text", "text": head}, *blocks],
                         prompts.SCHEMA_CLASSIFY)
    valid = {r["ma_kl"] for r in db.rows(conn, "SELECT ma_kl FROM ket_luan")}
    res["ma_kl"] = [m for m in res.get("ma_kl", []) if m in valid]
    # đối chiếu thêm theo số ký hiệu xuất hiện trong trích yếu/văn bản
    text = " ".join([vb["trich_yeu"] or "", res.get("trich_yeu", ""), quick_text(vb["duong_dan"])])
    for m in re.finditer(r"(\d+)\s*/\s*KL\s*-\s*TTr[^.;]{0,40}?(\d{4})?", text, re.I):
        cand = db.rows(conn, "SELECT ma_kl FROM ket_luan WHERE so_ky_hieu LIKE ?", (f"{m.group(1)}/KL%",))
        if len(cand) == 1 and cand[0]["ma_kl"] not in res["ma_kl"]:
            res["ma_kl"].append(cand[0]["ma_kl"])
    db.update(conn, "van_ban_den", vb_id, {
        "phan_loai": res["loai"], "ma_kl": ",".join(res["ma_kl"]),
        "so_ky_hieu": vb["so_ky_hieu"] or res.get("so_ky_hieu", ""),
        "don_vi_gui": vb["don_vi_gui"] or res.get("don_vi_gui", ""),
        "trich_yeu": vb["trich_yeu"] or res.get("trich_yeu", ""),
        "trang_thai": "da_phan_loai" if res["loai"] != "khac" else "bo_qua",
        "ghi_chu": res.get("ly_do", ""),
    })
    return res


# ----------------------------------------------------------- đánh giá báo cáo
def evaluate(conn, llm, vb_id: int, ma_kl: str, cfg: dict) -> dict:
    """Đối chiếu báo cáo của đơn vị với các kiến nghị chưa xong của KL. Trả đề xuất."""
    vb = db.one(conn, "SELECT * FROM van_ban_den WHERE id=?", (vb_id,))
    kl = db.one(conn, "SELECT * FROM ket_luan WHERE ma_kl=?", (ma_kl,))
    if not kl:
        raise ValueError(f"Không có KL {ma_kl}")
    kns = db.rows(conn, "SELECT * FROM kien_nghi WHERE kl_id=? AND tinh_trang<>'xong' ORDER BY stt", (kl["id"],))
    # chỉ các kiến nghị của đơn vị gửi báo cáo (nếu xác định được)
    sender = (vb["don_vi_gui"] or "").lower()
    own = [k for k in kns if k["don_vi"].lower() in sender or sender in k["don_vi"].lower()] if sender else []
    kns_eval = own or kns
    listing = "\n".join(f"[ID {k['id']}] (KN {k['stt']}, {k['loai']}, hạn {k['han'] or kl['han_thuc_hien']}) "
                        f"đơn vị {k['don_vi']}: {k['noi_dung']}" for k in kns_eval)
    paths = [vb["duong_dan"], *json.loads(vb["dinh_kem"] or "[]")]
    blocks, skipped = blocks_for(paths, cfg["llm"]["max_pdf_pages"])
    intro = (f"KẾT LUẬN {kl['so_ky_hieu']} ngày {kl['ngay_ban_hanh']}: {kl['trich_yeu']}\n"
             f"Đơn vị gửi báo cáo: {vb['don_vi_gui']}; số ký hiệu: {vb['so_ky_hieu']}\n\n"
             f"CÁC KIẾN NGHỊ CẦN ĐỐI CHIẾU:\n{listing}\n\n"
             f"Văn bản báo cáo và tài liệu kiểm chứng ở dưới (tệp đầu tiên là báo cáo chính).")
    res = llm.structured(prompts.SYS_EVAL, [{"type": "text", "text": intro}, *blocks], prompts.SCHEMA_EVAL)
    valid = {k["id"] for k in kns_eval}
    res["ket_qua"] = [r for r in res.get("ket_qua", []) if r.get("kien_nghi_id") in valid]
    res["bo_qua_tep"] = skipped
    res["ma_kl"] = ma_kl
    res["vb"] = {"id": vb_id, "ten": vb["ten"], "so_ky_hieu": vb["so_ky_hieu"], "don_vi_gui": vb["don_vi_gui"]}
    by_id = {k["id"]: k for k in kns_eval}
    for r in res["ket_qua"]:   # kèm nội dung để người duyệt dễ đối chiếu
        k = by_id[r["kien_nghi_id"]]
        r["_don_vi"], r["_stt"], r["_noi_dung"] = k["don_vi"], k["stt"], k["noi_dung"]
    # Chưa có kiểm chứng đầy đủ thì không để 'đảm bảo' với độ tin cậy thấp
    for r in res["ket_qua"]:
        if r["danh_gia"] == "dam_bao" and r.get("do_tin_cay") == "thap":
            r["danh_gia"] = "chua_dam_bao"
            r["chua_lam"] = (r.get("chua_lam") or "") + " [Hạ mức do độ tin cậy thấp – cần kiểm tra lại]"
    return res


def stage_evaluation(conn, res: dict, vb_id: int) -> int:
    return db.stage(conn, "ket_qua", res, vb_id=vb_id, ma_kl=res["ma_kl"])


def process(conn, llm, vb_id: int, cfg: dict) -> dict:
    """Chạy trọn quy trình cho 1 văn bản: phân loại → (nếu liên quan) đưa vào hàng chờ duyệt."""
    res = classify(conn, llm, vb_id, cfg)
    out = {"loai": res["loai"], "ma_kl": res["ma_kl"], "de_xuat": []}
    if res["loai"] == "bao_cao_ket_qua":
        for ma in res["ma_kl"]:
            ev = evaluate(conn, llm, vb_id, ma, cfg)
            out["de_xuat"].append(stage_evaluation(conn, ev, vb_id))
    elif res["loai"] == "chi_dao_ubnd":
        for ma in res["ma_kl"]:
            out["de_xuat"].append(db.stage(conn, "chi_dao", {
                "ma_kl": ma, "so_vb": res.get("so_ky_hieu", ""), "ngay_vb": res.get("ngay"),
                "trich_yeu": res.get("trich_yeu", ""), "noi_dung": res.get("noi_dung_chi_dao", ""),
                "han_hoan_thanh": res.get("han_hoan_thanh"), "han_bao_cao": res.get("han_bao_cao"),
                "file": db.one(conn, "SELECT duong_dan FROM van_ban_den WHERE id=?", (vb_id,))["duong_dan"],
            }, vb_id=vb_id, ma_kl=ma))
    return out


# --------------------------------------------------------------- duyệt & ghi
def apply_evaluation(conn, items: list[dict], today=None) -> int:
    """Ghi các dòng đã duyệt (đã chỉnh sửa) vào kiến nghị. Trả số dòng cập nhật."""
    from datetime import date

    day = (today or date.today()).isoformat()
    n = 0
    for it in items:
        kn = db.one(conn, "SELECT * FROM kien_nghi WHERE id=?", (it["kien_nghi_id"],))
        if not kn or it["danh_gia"] == "chua_co_thong_tin":
            continue
        if it["danh_gia"] == "dam_bao":
            upd = {"tinh_trang": "xong", "da_lam": it.get("da_lam", ""), "chua_lam": "",
                   "can_cu": it.get("can_cu", ""), "ly_do_chua_dut_diem": ""}
        else:
            upd = {"tinh_trang": "dang" if (it.get("da_lam") or "").strip() else "chua",
                   "da_lam": it.get("da_lam", ""), "chua_lam": it.get("chua_lam", ""),
                   "can_cu": it.get("can_cu", "")}
        if it.get("so_tien_da_nop_trieu") is not None:
            upd["so_tien_da_nop_trieu"] = it["so_tien_da_nop_trieu"]
        if it.get("ket_qua_kiem_diem"):
            upd["ket_qua_kiem_diem"] = it["ket_qua_kiem_diem"]
        upd["ngay_cap_nhat"] = day
        db.update(conn, "kien_nghi", kn["id"], upd)
        n += 1
    db.log(conn, "Ghi kết quả thực hiện", f"{n} kiến nghị")
    return n


def apply_chi_dao(conn, p: dict) -> int:
    kl = db.one(conn, "SELECT id FROM ket_luan WHERE ma_kl=?", (p["ma_kl"],))
    if not kl:
        raise ValueError(f"Không có KL {p['ma_kl']}")
    vid = db.insert(conn, "van_ban_chi_dao", {
        "kl_id": kl["id"], "so_vb": p.get("so_vb", ""), "ngay_vb": iso(p.get("ngay_vb")),
        "trich_yeu": p.get("trich_yeu", ""), "noi_dung": p.get("noi_dung", ""),
        "han_hoan_thanh": iso(p.get("han_hoan_thanh")), "han_bao_cao": iso(p.get("han_bao_cao")),
        "file": p.get("file", ""),
    })
    db.log(conn, "Ghi văn bản chỉ đạo UBND", f"{p['ma_kl']}: {p.get('so_vb')}")
    return vid


def ket_thuc_theo_doi(conn, kl_id: int, ngay=None) -> None:
    from datetime import date

    db.update(conn, "ket_luan", kl_id, {"dang_theo_doi": 0, "ngay_ket_thuc": iso(ngay) or date.today().isoformat()})
    db.log(conn, "Kết thúc theo dõi", str(kl_id))
