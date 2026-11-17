"""Xuất/nhập biểu theo dõi chung (.xlsx). Tên cột theo cách gọi của sổ theo dõi hiện hành."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import alerts, db
from .util import iso, parse_date

TT = db.TINH_TRANG
TT_REV = {v: k for k, v in TT.items()}

KL_COLS = [("Mã KL", "ma_kl"), ("Số ký hiệu", "so_ky_hieu"), ("Ngày ban hành", "ngay_ban_hanh"),
           ("Trích yếu", "trich_yeu"), ("Quyết định thanh tra", "qd_thanh_tra"),
           ("Đơn vị được thanh tra", "don_vi_duoc_thanh_tra"), ("Người theo dõi", "nguoi_theo_doi"),
           ("Hạn thực hiện theo KL", "han_thuc_hien"), ("Thời hạn (nguyên văn)", "han_text"),
           ("Đang theo dõi", "dang_theo_doi"), ("Ngày kết thúc theo dõi", "ngay_ket_thuc"),
           ("Đã báo cáo UBND ngày", "da_bao_cao_ubnd"), ("Ghi chú", "ghi_chu")]
KN_COLS = [("Mã KL", None), ("STT", "stt"), ("Nội dung kiến nghị", "noi_dung"), ("Đơn vị", "don_vi"),
           ("Loại", "loai"), ("Hạn", "han"), ("Số tiền kiến nghị (triệu đồng)", "so_tien_trieu"),
           ("Đất (m2)", "dat_m2"), ("Trang KL", "trang_kl"), ("Tình trạng", "tinh_trang"),
           ("Nội dung đã hoàn thành / đang thực hiện", "da_lam"), ("Nội dung chưa thực hiện", "chua_lam"),
           ("Căn cứ / tài liệu kiểm chứng", "can_cu"), ("Số tiền đã nộp (triệu đồng)", "so_tien_da_nop_trieu"),
           ("Kết quả kiểm điểm / xử lý", "ket_qua_kiem_diem"), ("Lý do chưa dứt điểm", "ly_do_chua_dut_diem"),
           ("Ngày cập nhật", "ngay_cap_nhat")]
CD_COLS = [("Mã KL", None), ("Số văn bản", "so_vb"), ("Ngày", "ngay_vb"), ("Trích yếu", "trich_yeu"),
           ("Nội dung chỉ đạo", "noi_dung"), ("Hạn hoàn thành", "han_hoan_thanh"), ("Hạn báo cáo", "han_bao_cao")]
DD_COLS = [("Mã KL", None), ("Đơn vị", "don_vi"), ("Số văn bản", "so_vb"), ("Ngày", "ngay_vb"),
           ("Hạn trả lời", "han_tra_loi")]
HEAD = PatternFill("solid", fgColor="1F3A5F")


def _sheet(wb, title, cols, data, widths=None):
    ws = wb.create_sheet(title)
    ws.append([c[0] for c in cols])
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for r in data:
        ws.append(r)
    for i, (h, _) in enumerate(cols, 1):
        w = (widths or {}).get(h, 16)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    return ws


def export_workbook(conn, path: str | Path, today: date | None = None) -> Path:
    today = today or date.today()
    wb = Workbook()
    wb.remove(wb.active)
    kls = db.rows(conn, "SELECT * FROM ket_luan ORDER BY ngay_ban_hanh, id")
    ma = {k["id"]: k["ma_kl"] for k in kls}
    # Biểu tổng hợp (1 dòng/KL) kèm số liệu đếm từ kiến nghị
    tong = []
    for k in kls:
        c = db.one(conn, "SELECT COUNT(*) n, SUM(tinh_trang='xong') x, SUM(tinh_trang='dang') d, "
                         "SUM(tinh_trang='chua') c FROM kien_nghi WHERE kl_id=?", (k["id"],))
        cd = alerts.latest_chi_dao(conn, k["id"])
        tong.append([k[f] for _, f in KL_COLS] + [
            c["n"], c["x"] or 0, (c["d"] or 0) + (c["c"] or 0), c["d"] or 0, c["c"] or 0,
            cd["so_vb"] if cd else "", cd["ngay_vb"] if cd else "", cd["han_hoan_thanh"] if cd else "",
            str(alerts.han_bao_cao_kl(k, cd) or "")])
    extra = ["Tổng KN", "Đã hoàn thành", "Chưa hoàn thành", "Đang thực hiện", "Chưa thực hiện",
             "VB chỉ đạo UBND (số)", "VB chỉ đạo (ngày)", "Hạn hoàn thành (chỉ đạo)", "Hạn báo cáo UBND"]
    _sheet(wb, "Bieu tong hop", KL_COLS + [(e, None) for e in extra], tong,
           {"Trích yếu": 50, "Quyết định thanh tra": 30})
    kn = []
    for r in db.rows(conn, "SELECT * FROM kien_nghi ORDER BY kl_id, stt"):
        kn.append([ma[r["kl_id"]]] + [TT.get(r[f], r[f]) if f == "tinh_trang" else r[f] for _, f in KN_COLS[1:]])
    _sheet(wb, "Kien nghi", KN_COLS, kn, {"Nội dung kiến nghị": 70, "Đơn vị": 30,
                                          "Nội dung đã hoàn thành / đang thực hiện": 50,
                                          "Nội dung chưa thực hiện": 40, "Căn cứ / tài liệu kiểm chứng": 30})
    cd = [[ma[r["kl_id"]]] + [r[f] for _, f in CD_COLS[1:]]
          for r in db.rows(conn, "SELECT * FROM van_ban_chi_dao ORDER BY kl_id, ngay_vb")]
    _sheet(wb, "Chi dao UBND", CD_COLS, cd, {"Trích yếu": 50, "Nội dung chỉ đạo": 50})
    dd = [[ma.get(r["kl_id"], "")] + [r[f] for _, f in DD_COLS[1:]]
          for r in db.rows(conn, "SELECT * FROM van_ban_don_doc ORDER BY ngay_vb")]
    _sheet(wb, "Don doc", DD_COLS, dd)
    # Xử lý kinh tế (từ kiến nghị loại Kinh tế)
    kt = [[ma[r["kl_id"]], r["don_vi"], r["noi_dung"], r["so_tien_trieu"], r["so_tien_da_nop_trieu"],
           (r["so_tien_trieu"] or 0) - (r["so_tien_da_nop_trieu"] or 0)]
          for r in db.rows(conn, "SELECT * FROM kien_nghi WHERE loai='Kinh tế' ORDER BY kl_id, stt")]
    _sheet(wb, "Xu ly kinh te", [("Mã KL", 0), ("Đơn vị", 0), ("Nội dung", 0), ("Kiến nghị (triệu đồng)", 0),
                                 ("Đã nộp (triệu đồng)", 0), ("Còn phải nộp (triệu đồng)", 0)], kt, {"Nội dung": 60})
    # Cảnh báo
    cb = [[g["ma_kl"], g["don_vi"], {"qua_han": "QUÁ HẠN", "sap_den_han": "Sắp đến hạn",
                                      "khong_co_han": "Chưa có hạn"}[g["muc"]],
           str(g["han"] or ""), g["qua_han_ngay"] if (g["qua_han_ngay"] or 0) > 0 else "", len(g["kn"]),
           g["lan_don_doc"]] for g in alerts.canh_bao_don_doc(conn, today)]
    _sheet(wb, "Canh bao", [("Mã KL", 0), ("Đơn vị", 0), ("Mức", 0), ("Hạn", 0), ("Quá hạn (ngày)", 0),
                            ("Số KN tồn", 0), ("Số lần đã đôn đốc", 0)], cb, {"Đơn vị": 40})
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return Path(path)


# ------------------------------------------------------------------ nhập
def _read(ws, cols):
    hdr = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
    idx = {h: i for i, h in enumerate(hdr)}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(v not in (None, "") for v in row):
            continue
        yield {f: row[idx[h]] for h, f in cols if h in idx and f}, row, idx


def _d(v):
    return iso(v) if v not in (None, "") else None


def import_workbook(conn, path: str | Path) -> dict:
    """Nạp dữ liệu từ file đúng định dạng xuất ra (Bieu tong hop + Kien nghi [+ Chi dao UBND, Don doc]).
    KL đã có (trùng mã) được bỏ qua; kiến nghị của KL đã có cũng bỏ qua – không ghi đè dữ liệu hiện hành."""
    wb = load_workbook(path, data_only=True)
    res = {"kl": 0, "kn": 0, "bo_qua_kl": 0}
    ids: dict[str, int] = {}
    new: set[str] = set()
    for r, _, _ in _read(wb["Bieu tong hop"], KL_COLS):
        if not r.get("ma_kl"):
            continue
        ex = db.one(conn, "SELECT id FROM ket_luan WHERE ma_kl=?", (str(r["ma_kl"]),))
        if ex:
            ids[str(r["ma_kl"])] = ex["id"]
            res["bo_qua_kl"] += 1
            continue
        r = {k: (None if v == "" else v) for k, v in r.items()}
        for f in ("ngay_ban_hanh", "han_thuc_hien", "ngay_ket_thuc", "da_bao_cao_ubnd"):
            r[f] = _d(r.get(f))
        r["dang_theo_doi"] = 0 if str(r.get("dang_theo_doi")).strip() in ("0", "False", "None") else 1
        r["ma_kl"] = str(r["ma_kl"])
        ids[r["ma_kl"]] = db.insert(conn, "ket_luan", r)
        new.add(r["ma_kl"])
        res["kl"] += 1
    if "Kien nghi" in wb.sheetnames:
        for r, row, idx in _read(wb["Kien nghi"], KN_COLS):
            ma = str(row[idx["Mã KL"]]) if "Mã KL" in idx and row[idx["Mã KL"]] else None
            if ma not in new:
                continue
            r = {k: v for k, v in r.items() if v not in (None, "")}
            r["kl_id"] = ids[ma]
            r["han"] = _d(r.get("han"))
            r["ngay_cap_nhat"] = _d(r.get("ngay_cap_nhat"))
            tt = r.get("tinh_trang")
            r["tinh_trang"] = TT_REV.get(tt, tt if tt in TT else "chua")
            if r.get("loai") not in db.LOAI_KN:
                r["loai"] = "QLNN"
            db.insert(conn, "kien_nghi", r)
            res["kn"] += 1
    if "Chi dao UBND" in wb.sheetnames:
        for r, row, idx in _read(wb["Chi dao UBND"], CD_COLS):
            ma = str(row[idx["Mã KL"]]) if "Mã KL" in idx and row[idx["Mã KL"]] else None
            if ma in new:
                r = {k: v for k, v in r.items() if v not in (None, "")}
                for f in ("ngay_vb", "han_hoan_thanh", "han_bao_cao"):
                    r[f] = _d(r.get(f))
                db.insert(conn, "van_ban_chi_dao", {"kl_id": ids[ma], **r})
    db.log(conn, "Nhập Excel", f"{res}")
    return res


def import_don_vi(conn, path: str | Path) -> int:
    """Nhập danh mục đơn vị từ sheet 'Danh muc don vi' (cột TenChuan, Alias, LoaiDonVi)."""
    wb = load_workbook(path, data_only=True)
    ws = wb["Danh muc don vi"] if "Danh muc don vi" in wb.sheetnames else wb.active
    n = 0
    hdr = [str(c.value or "").strip().lower() for c in ws[1]]
    def col(*names):
        for nm in names:
            if nm in hdr:
                return hdr.index(nm)
        return None
    i_t, i_a, i_l = col("tenchuan", "tên chuẩn"), col("alias", "tên khác"), col("loaidonvi", "loại đơn vị")
    if i_t is None:
        raise ValueError("Không tìm thấy cột TenChuan.")
    for row in ws.iter_rows(min_row=2, values_only=True):
        t = (row[i_t] or "").strip() if row[i_t] else ""
        if not t or db.one(conn, "SELECT id FROM don_vi WHERE ten_chuan=?", (t,)):
            continue
        db.insert(conn, "don_vi", {"ten_chuan": t, "alias": (row[i_a] or "") if i_a is not None else "",
                                   "loai": (row[i_l] or "") if i_l is not None else ""})
        n += 1
    return n
