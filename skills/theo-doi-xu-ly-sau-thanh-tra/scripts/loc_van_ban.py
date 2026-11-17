#!/usr/bin/env python3
"""Lọc danh sách văn bản đến của Cổng chính quyền điện tử: văn bản nào liên quan việc thực hiện KL thanh tra.

Dùng: loc_van_ban.py ds.csv so.xlsx
ds.csv có cột: so_ky_hieu,ngay,noi_gui,trich_yeu
Không dùng LLM: lọc bằng quy tắc để chỉ phải mở số ít văn bản.
Nhóm 1 'chac_chan': nêu số KL/văn bản chỉ đạo UBND đã có trong sổ, hoặc nêu 'kết luận thanh tra' + từ khóa thực hiện.
Nhóm 2 'can_xem': nơi gửi là đơn vị có kiến nghị tồn (theo sổ) + từ khóa báo cáo; hoặc có từ khóa mơ hồ.
Nhóm 3 'bo_qua': còn lại.
"""
import csv, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from so import load, bieu_tong_hop, kien_nghi, norm

KW_STRONG = re.compile(r"ket luan (so )?\d+|kltt|/kl-ttr|kl-ttr|kien nghi (tai|cua) ket luan|ket luan thanh tra")
KW_ACTION = re.compile(r"bao cao ket qua|thuc hien ket luan|thuc hien kien nghi|khac phuc|xu ly sau thanh tra|kiem diem|thu hoi|nop ngan sach|don doc")
KW_WEAK = re.compile(r"thanh tra|kien nghi|sai pham|ket qua thuc hien")


def main(csv_path, so_path):
    wb = load(so_path)
    bt = bieu_tong_hop(wb)
    kns = kien_nghi(wb)
    don_vi_ton = {norm(k["don_vi"]) for k in kns if not k["xong"] and k["don_vi"]}
    so_kl = {}  # '38/kl-ttr' -> ma
    for ma, d in bt.items():
        m = re.match(r"\s*(\d+)\s*/", str(d["so"] or ""))
        if m:
            so_kl[m[1]] = ma
    so_vb = {norm(d["vb_ubnd"]).replace(" ", "") for d in bt.values() if d["vb_ubnd"]}
    out = {"chac_chan": [], "can_xem": [], "bo_qua": []}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ty, noi, so = norm(r.get("trich_yeu")), norm(r.get("noi_gui")), norm(r.get("so_ky_hieu")).replace(" ", "")
            ly = []
            for m in re.finditer(r"ket luan (?:thanh tra )?(?:so )?(\d+)\s*/\s*kl", ty):
                if m[1] in so_kl:
                    ly.append(f"nêu KL số {m[1]} (mã {so_kl[m[1]]})")
            if any(v and v in ty.replace(" ", "") for v in so_vb):
                ly.append("nêu văn bản chỉ đạo của UBND đã có trong sổ")
            strong = bool(KW_STRONG.search(ty))
            act = bool(KW_ACTION.search(ty))
            dv_ton = any(noi and (noi in d or d in noi) for d in don_vi_ton)
            if ly or (strong and act):
                nhom = "chac_chan"
            elif dv_ton and (act or KW_WEAK.search(ty)) or strong or KW_WEAK.search(ty):
                nhom = "can_xem"
                if dv_ton:
                    ly.append("đơn vị gửi đang có kiến nghị tồn")
            else:
                nhom = "bo_qua"
            out[nhom].append((r.get("so_ky_hieu"), r.get("ngay"), r.get("noi_gui"), r.get("trich_yeu"), "; ".join(ly)))
    for nhom, ten in (("chac_chan", "LIÊN QUAN CHẮC CHẮN (mở và tải)"), ("can_xem", "CẦN XEM (mở nếu cần)")):
        print(f"## {ten}: {len(out[nhom])}")
        for so, ng, noi, ty, ly in out[nhom]:
            print(f"- {so} ({ng}) từ {noi}: {ty}" + (f"  [{ly}]" if ly else ""))
    print(f"\n## Bỏ qua: {len(out['bo_qua'])} văn bản (không liệt kê). Dùng --liet-ke-bo-qua để xem." if "--liet-ke-bo-qua" not in sys.argv else "")
    if "--liet-ke-bo-qua" in sys.argv:
        for so, ng, noi, ty, _ in out["bo_qua"]:
            print(f"- {so} ({ng}) {noi}: {ty}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    main(*args)
