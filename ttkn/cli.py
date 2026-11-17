"""Dòng lệnh: python -m ttkn <lệnh>"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from . import alerts, db, excel_io, portal
from .config import load_config


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ttkn", description="Theo dõi, đôn đốc, xử lý sau thanh tra")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("canh-bao", help="In cảnh báo quá hạn/sắp đến hạn")
    e = sub.add_parser("xuat-excel", help="Xuất biểu theo dõi ra .xlsx")
    e.add_argument("--ra", default="data/bieu_theo_doi.xlsx")
    i = sub.add_parser("nhap-excel", help="Nạp biểu .xlsx (định dạng do công cụ xuất)")
    i.add_argument("file")
    d = sub.add_parser("nhap-don-vi", help="Nạp danh mục đơn vị")
    d.add_argument("file")
    sub.add_parser("cong-dang-nhap", help="Mở trình duyệt để đăng nhập Cổng chính quyền điện tử")
    sub.add_parser("cong-kiem-tra", help="Lưu ảnh chụp/HTML hộp thư để chỉnh selector")
    q = sub.add_parser("cong-quet", help="Quét hộp thư đến, tải văn bản liên quan kết luận")
    q.add_argument("--ngay", type=int, default=7)
    q.add_argument("--hien-thi", action="store_true", help="Hiện cửa sổ trình duyệt")
    q.add_argument("--xu-ly", action="store_true", help="Phân loại + đánh giá bằng AI sau khi tải")
    a = ap.parse_args(argv)

    cfg = load_config()
    conn = db.connect(cfg["duong_dan"]["db"])
    if a.cmd == "canh-bao":
        for g in alerts.canh_bao_don_doc(conn, bao_truoc=cfg["dondoc"]["bao_truoc_ngay"]):
            print(f"[{g['muc']:<12}] KL {g['ma_kl']:<9} {g['don_vi']} – {len(g['kn'])} KN tồn, "
                  f"hạn {g['han']}, quá hạn {g['qua_han_ngay'] or 0} ngày, đã đôn đốc {g['lan_don_doc']} lần")
        for r in alerts.den_han_bao_cao(conn, cfg=cfg):
            print(f"[BÁO CÁO UBND] KL {r['ma_kl']} hạn {r['han_bao_cao']} (còn {r['con_ngay']} ngày) – "
                  f"{r['xong']}/{r['tong_kn']} KN xong")
    elif a.cmd == "xuat-excel":
        print(excel_io.export_workbook(conn, a.ra))
    elif a.cmd == "nhap-excel":
        print(excel_io.import_workbook(conn, a.file))
    elif a.cmd == "nhap-don-vi":
        print(excel_io.import_don_vi(conn, a.file), "đơn vị")
    elif a.cmd == "cong-dang-nhap":
        pc = portal.load_portal()
        print("Đăng nhập thành công, đã lưu phiên." if portal.login(pc) else "Hết thời gian chờ đăng nhập.")
    elif a.cmd == "cong-kiem-tra":
        print(*portal.inspect(portal.load_portal()), sep="\n")
    elif a.cmd == "cong-quet":
        pc = portal.load_portal()
        r = portal.fetch_inbox(conn, pc, cfg["duong_dan"]["data"], cfg["loc_van_ban"]["tu_khoa"],
                               a.ngay, headless=not a.hien_thi)
        if r["can_dang_nhap"]:
            print("Phiên hết hạn – chạy `python -m ttkn cong-dang-nhap` trước.")
            return 1
        print({k: v for k, v in r.items() if k != "moi"}, f"mới={len(r['moi'])}")
        if a.xu_ly and r["moi"]:
            from . import inbox
            from .llm import ClaudeLLM
            llm = ClaudeLLM(cfg["llm"]["model"], cfg["llm"]["max_tokens"])
            for vid in r["moi"]:
                print(vid, inbox.process(conn, llm, vid, cfg))
            print("Đã đưa vào hàng chờ duyệt – mở giao diện (streamlit run ttkn/app.py) để duyệt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
