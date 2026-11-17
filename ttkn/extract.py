"""Bước 1: nhập kết luận thanh tra mới (PDF/DOCX) → bản nháp chờ duyệt → ghi sổ."""
from __future__ import annotations

from pathlib import Path

from . import db, prompts
from .docs import blocks_for
from .util import iso, ma_kl as make_ma_kl, parse_date


def extract_kl(llm, path: str | Path, max_pdf_pages: int = 100) -> dict:
    blocks, skipped = blocks_for([path], max_pdf_pages)
    if not blocks:
        raise ValueError(f"Không đọc được tệp: {skipped}")
    blocks.append({"type": "text", "text": "Hãy trích xuất kết luận thanh tra trên theo đúng quy ước."})
    data = llm.structured(prompts.SYS_KL, blocks, prompts.SCHEMA_KL)
    data.setdefault("canh_bao", [])
    data["canh_bao"] += [f"Không đọc được: {s}" for s in skipped]
    data["file_goc"] = str(path)
    return data


def parse_manual_json(text: str) -> dict:
    """Đọc kết quả JSON dán từ Claude.ai (chịu được ```json ... ```, lời dẫn thừa, dấu phẩy thừa)."""
    import json
    import re

    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S | re.I)
    if m:
        t = m.group(1).strip()
    a, b = t.find("{"), t.rfind("}")
    if a >= 0 and b <= a:
        raise ValueError("Câu trả lời bị cắt dở (có dấu { mở đầu nhưng không có phần kết). Hãy bảo Claude gửi lại "
                         "đầy đủ hoặc chia kết luận làm đôi.")
    if a < 0:
        raise ValueError("Không thấy khối JSON trong nội dung đã dán. Hãy sao chép toàn bộ câu trả lời của Claude.")
    t = re.sub(r",\s*([}\]])", r"\1", t[a:b + 1])
    try:
        d = json.loads(t)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON bị lỗi ở dòng {e.lineno}, cột {e.colno} ({e.msg}). Có thể câu trả lời bị cắt dở – "
                         "hãy bảo Claude gửi lại phần còn thiếu hoặc chia kết luận làm đôi.") from e
    if not isinstance(d, dict) or not isinstance(d.get("kien_nghi"), list):
        raise ValueError("JSON thiếu mục 'kien_nghi'.")
    for k in d["kien_nghi"]:
        if k.get("loai") not in db.LOAI_KN:
            k["loai"] = "QLNN"
    d.setdefault("canh_bao", [])
    return d


def validate_kl(conn, data: dict) -> list[str]:
    """Kiểm tra bản nháp; trả danh sách cảnh báo cho người duyệt."""
    w: list[str] = list(data.get("canh_bao") or [])
    ma = make_ma_kl(data.get("so_ky_hieu", ""), data.get("ngay_ban_hanh"))
    if not ma:
        w.append("Không xác định được mã KL (cần số ký hiệu dạng NN/KL-TTr và ngày ban hành).")
    elif db.one(conn, "SELECT id FROM ket_luan WHERE ma_kl=?", (ma,)):
        w.append(f"Mã KL {ma} đã có trong sổ – duyệt sẽ bị từ chối để tránh trùng.")
    seen: dict[tuple, int] = {}
    for i, kn in enumerate(data.get("kien_nghi", []), 1):
        key = (kn.get("don_vi", "").strip().lower(), " ".join(kn.get("noi_dung", "").split()).lower())
        if key in seen:
            w.append(f"Kiến nghị {i} trùng nội dung với kiến nghị {seen[key]} (cùng đơn vị).")
        seen[key] = i
        _, ok = db.normalize_unit(conn, kn.get("don_vi", ""))
        if not ok:
            w.append(f"Kiến nghị {i}: đơn vị “{kn.get('don_vi')}” chưa có trong danh mục đơn vị.")
        if not kn.get("han") and not data.get("han_thuc_hien"):
            w.append(f"Kiến nghị {i}: chưa xác định được thời hạn thực hiện.")
        if kn.get("han") and not parse_date(kn["han"]):
            w.append(f"Kiến nghị {i}: thời hạn “{kn['han']}” không đúng định dạng ngày.")
    if not data.get("kien_nghi"):
        w.append("Không có kiến nghị nào được trích xuất.")
    return w


def stage_kl(conn, data: dict) -> int:
    data["canh_bao"] = validate_kl(conn, data)
    ma = make_ma_kl(data.get("so_ky_hieu", ""), data.get("ngay_ban_hanh")) or ""
    return db.stage(conn, "kl_moi", data, ma_kl=ma)


def commit_kl(conn, data: dict, nguoi_theo_doi: str = "") -> int:
    """Ghi bản đã duyệt vào sổ. Trả id kết luận."""
    ma = make_ma_kl(data.get("so_ky_hieu", ""), data.get("ngay_ban_hanh"))
    if not ma:
        raise ValueError("Thiếu mã KL (số ký hiệu / ngày ban hành).")
    if db.one(conn, "SELECT id FROM ket_luan WHERE ma_kl=?", (ma,)):
        raise ValueError(f"Mã KL {ma} đã tồn tại.")
    kl_id = db.insert(conn, "ket_luan", {
        "ma_kl": ma, "so_ky_hieu": data["so_ky_hieu"], "ngay_ban_hanh": iso(data["ngay_ban_hanh"]),
        "trich_yeu": data.get("trich_yeu", ""), "qd_thanh_tra": data.get("qd_thanh_tra", ""),
        "don_vi_duoc_thanh_tra": data.get("don_vi_duoc_thanh_tra", ""),
        "nguoi_theo_doi": nguoi_theo_doi, "han_thuc_hien": iso(data.get("han_thuc_hien")),
        "han_text": data.get("han_text", ""), "file_goc": data.get("file_goc", ""),
    })
    for i, kn in enumerate(data.get("kien_nghi", []), 1):
        don_vi, _ = db.normalize_unit(conn, kn["don_vi"])
        db.insert(conn, "kien_nghi", {
            "kl_id": kl_id, "stt": kn.get("stt") or i, "noi_dung": kn["noi_dung"].strip(),
            "don_vi": don_vi, "loai": kn.get("loai") or "QLNN", "han": iso(kn.get("han")),
            "so_tien_trieu": kn.get("so_tien_trieu"), "dat_m2": kn.get("dat_m2"),
            "trang_kl": kn.get("trang", ""),
        })
    db.log(conn, "Nhập KL", f"{ma}: {len(data.get('kien_nghi', []))} kiến nghị")
    return kl_id
