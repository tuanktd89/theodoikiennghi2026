#!/usr/bin/env python3
"""Truy vấn sổ 'Input - Theo dõi KLTT' (.xlsx) bằng code để không phải nạp cả sổ vào ngữ cảnh.

Lệnh:
  canh-bao <so.xlsx> [--ngay YYYY-MM-DD] [--sap-han 15]
  kien-nghi <so.xlsx> [--kl 38.2026] [--don-vi "tên"] [--ton] [--json]
  thong-ke <so.xlsx> --kl 38.2026
  don-vi <so.xlsx> "tên trong KL"
  ra-soat <so.xlsx>
Cột theo quy ước trong references/quy-trinh-goc.md. Dòng dữ liệu nhận diện bằng mã KL dạng 38.2026 ở cột B.
"""
import argparse, json, re, sys, unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
import openpyxl
from openpyxl.utils import column_index_from_string as ci

KL_RE = re.compile(r"^\d+\.\d{4}$")
S_BT, S_KN, S_DM = "Bieu tong hop", "Kien nghi", "Danh muc don vi"


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip()


def load(path):
    return openpyxl.load_workbook(path, data_only=True, read_only=False)


def cell(row, col):
    i = ci(col) - 1
    return row[i].value if i < len(row) else None


def to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(v or ""))
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def rows(wb, sheet):
    if sheet not in wb.sheetnames:
        sys.exit(f"Không thấy sheet '{sheet}'. Các sheet: {wb.sheetnames}")
    for r in wb[sheet].iter_rows():
        if KL_RE.match(str(cell(r, "B") or "").strip()):
            yield r


def bieu_tong_hop(wb):
    out = {}
    for r in rows(wb, S_BT):
        ma = str(cell(r, "B")).strip()
        out[ma] = dict(
            ma=ma, so=cell(r, "C"), ngay=to_date(cell(r, "D")), theo_doi=cell(r, "G"),
            trich_yeu=cell(r, "J"), vb_ubnd=cell(r, "AU"), ngay_vb=to_date(cell(r, "AV")),
            han_ubnd=to_date(cell(r, "AX")), han_kl=to_date(cell(r, "AZ")),
            han_bc=to_date(cell(r, "BA")), don_doc=cell(r, "BB"),
            tong=num(cell(r, "CN")), xong=num(cell(r, "CO")), chua_xong=num(cell(r, "CP")),
            dang=num(cell(r, "CQ")), chua_th=num(cell(r, "CR")),
            ket_thuc=cell(r, "EE"),
        )
        d = out[ma]
        d["han"] = d["han_ubnd"] or d["han_kl"]
    return out


LOAI = {"K": "Kinh tế", "L": "QLNN", "M": "Trách nhiệm", "N": "Chính sách", "O": "Chuyển CQĐT"}


def kien_nghi(wb):
    out = []
    for r in rows(wb, S_KN):
        loai = next((v for c, v in LOAI.items() if cell(r, c) not in (None, "", 0)), "?")
        xong = cell(r, "Y") not in (None, "", 0) or str(cell(r, "Q") or "").lower() == "x"
        dang = cell(r, "Z") not in (None, "", 0)
        out.append(dict(
            ma=str(cell(r, "B")).strip(), noi_dung=cell(r, "E"), don_vi_kl=cell(r, "F"),
            don_vi=cell(r, "G"), loai=loai, xong=xong, dang=dang,
            da_lam=cell(r, "R"), dang_lam=cell(r, "V"), ly_do=cell(r, "AJ"),
            dong=r[0].row,
        ))
    return out


def lookup_kn(args, wb):
    kns = kien_nghi(wb)
    if args.kl:
        kns = [k for k in kns if k["ma"] == args.kl]
    if args.don_vi:
        q = norm(args.don_vi)
        kns = [k for k in kns if q in norm(k["don_vi"])]
    if args.ton:
        kns = [k for k in kns if not k["xong"]]
    return kns


def cmd_canh_bao(a):
    wb = load(a.so)
    today = date.fromisoformat(a.ngay) if a.ngay else date.today()
    bt = bieu_tong_hop(wb)
    kns = kien_nghi(wb)
    ton = defaultdict(list)
    for k in kns:
        if not k["xong"]:
            ton[k["ma"]].append(k)
    qua, sap, bc = [], [], []
    for ma, d in bt.items():
        if d["ket_thuc"] and str(d["ket_thuc"]).strip():
            if str(d["ket_thuc"]).strip().lower() != "x":
                continue  # đã có ngày kết thúc theo dõi
        con = len(ton.get(ma, [])) or d["chua_xong"]
        if not con or not d["han"]:
            continue
        delta = (d["han"] - today).days
        if delta < 0:
            qua.append((delta, ma, d, con))
        elif delta <= a.sap_han:
            sap.append((delta, ma, d, con))
        if d["han_bc"] and d["han_bc"] < today and con:
            bc.append((ma, d, con))
    qua.sort()
    sap.sort()
    print(f"# Cảnh báo ngày {today:%d/%m/%Y}")
    print(f"\n## Quá hạn còn kiến nghị chưa xong: {len(qua)} KL")
    for delta, ma, d, con in qua:
        print(f"- KL {ma} ({d['so']}) quá {-delta} ngày (hạn {d['han']:%d/%m/%Y}), còn {con} kiến nghị chưa xong; phụ trách: {d['theo_doi'] or '-'}; đôn đốc gần nhất: {d['don_doc'] or 'chưa có'}")
    print(f"\n## Sắp đến hạn trong {a.sap_han} ngày: {len(sap)} KL")
    for delta, ma, d, con in sap:
        print(f"- KL {ma}: còn {delta} ngày (hạn {d['han']:%d/%m/%Y}), còn {con} kiến nghị")
    print(f"\n## Quá hạn báo cáo UBND (cột BA) mà vẫn còn kiến nghị: {len(bc)} KL")
    for ma, d, con in bc:
        print(f"- KL {ma}: hạn báo cáo {d['han_bc']:%d/%m/%Y}")
    cham = Counter()
    for delta, ma, d, con in qua:
        for k in ton.get(ma, []):
            cham[k["don_vi"] or k["don_vi_kl"]] += 1
    print("\n## Đơn vị còn nhiều kiến nghị tồn ở KL quá hạn (top 10)")
    for dv, n in cham.most_common(10):
        print(f"- {dv}: {n}")
    thieu = [m for m, d in bt.items() if not d["han"]]
    if thieu:
        print(f"\n(Lưu ý: {len(thieu)} KL chưa có hạn ở AX/AZ: {', '.join(thieu[:15])}{'…' if len(thieu) > 15 else ''})")


def cmd_kien_nghi(a):
    kns = lookup_kn(a, load(a.so))
    if a.json:
        print(json.dumps(kns, ensure_ascii=False, indent=1))
        return
    print(f"{len(kns)} kiến nghị")
    for k in kns:
        tt = "xong" if k["xong"] else ("đang" if k["dang"] else "chưa")
        print(f"- [{k['ma']} d{k['dong']}] {k['don_vi']} | {k['loai']} | {tt}\n  {str(k['noi_dung'] or '').strip()}")


def cmd_thong_ke(a):
    wb = load(a.so)
    bt = bieu_tong_hop(wb).get(a.kl)
    kns = [k for k in kien_nghi(wb) if k["ma"] == a.kl]
    tong = len(kns)
    xong = sum(k["xong"] for k in kns)
    dang = sum(1 for k in kns if not k["xong"] and k["dang"])
    print(f"KL {a.kl}: {tong} dòng kiến nghị; xong {xong}; đang {dang}; chưa {tong - xong - dang}")
    print("Theo loại:", dict(Counter(k["loai"] for k in kns)))
    dv = defaultdict(lambda: [0, 0, 0])
    for k in kns:
        i = 0 if k["xong"] else (1 if k["dang"] else 2)
        dv[k["don_vi"]][i] += 1
    for name, (x, d, c) in sorted(dv.items(), key=lambda t: str(t[0])):
        print(f"- {name}: tổng {x + d + c} (xong {x}, đang {d}, chưa {c})")
    if bt:
        ok = (bt["tong"], bt["xong"]) == (tong, xong)
        print(f"Đối chiếu Bieu tong hop: CN={bt['tong']} CO={bt['xong']} CP={bt['chua_xong']} CQ={bt['dang']} CR={bt['chua_th']} -> {'KHỚP' if ok else 'LỆCH, cần kiểm tra'}")
    else:
        print("Không thấy KL này ở Bieu tong hop.")


def cmd_don_vi(a):
    wb = load(a.so)
    q = norm(a.ten)
    hits = []
    for r in wb[S_DM].iter_rows():
        chuan, alias, loai = cell(r, "B"), cell(r, "C"), cell(r, "D")
        if not chuan or chuan == "TenChuan":
            continue
        names = [chuan] + [x.strip() for x in re.split(r"[;\n|]", str(alias or "")) if x.strip()]
        if any(norm(n) == q for n in names):
            hits.append((0, chuan, loai))
        elif any(q in norm(n) or norm(n) in q for n in names if len(norm(n)) > 6):
            hits.append((1, chuan, loai))
    if not hits:
        print("KHÔNG có trong danh mục: hỏi người dùng, không tự thêm.")
    for rank, chuan, loai in sorted(hits)[:5]:
        print(("CHÍNH XÁC" if rank == 0 else "gần đúng") + f": {chuan} ({loai})")


def cmd_ra_soat(a):
    wb = load(a.so)
    bt = bieu_tong_hop(wb)
    kns = kien_nghi(wb)
    chuan = {norm(cell(r, "B")) for r in wb[S_DM].iter_rows() if cell(r, "B")}
    loi = []
    by_kl = defaultdict(list)
    for k in kns:
        by_kl[k["ma"]].append(k)
        if k["don_vi"] and norm(k["don_vi"]) not in chuan:
            loi.append(f"Dòng {k['dong']} (KL {k['ma']}): đơn vị '{k['don_vi']}' không có trong Danh muc don vi")
    for ma, lst in by_kl.items():
        seen = {}
        for k in lst:
            key = (norm(k["noi_dung"]), norm(k["don_vi"]))
            if key[0] and key in seen:
                loi.append(f"KL {ma}: dòng {seen[key]} và {k['dong']} trùng nội dung và đơn vị")
            seen[key] = k["dong"]
        d = bt.get(ma)
        if d and d["tong"] and d["tong"] != len(lst):
            loi.append(f"KL {ma}: {len(lst)} dòng kiến nghị nhưng CN={d['tong']}")
    for ma in bt:
        if ma not in by_kl:
            loi.append(f"KL {ma}: có ở Bieu tong hop nhưng chưa có dòng nào ở Kien nghi")
    print(f"Rà soát xong: {len(loi)} vấn đề (chỉ báo, không sửa sổ)")
    for x in loi[:200]:
        print("-", x)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("canh-bao"); c.add_argument("so"); c.add_argument("--ngay"); c.add_argument("--sap-han", type=int, default=15); c.set_defaults(f=cmd_canh_bao)
    c = sp.add_parser("kien-nghi"); c.add_argument("so"); c.add_argument("--kl"); c.add_argument("--don-vi"); c.add_argument("--ton", action="store_true"); c.add_argument("--json", action="store_true"); c.set_defaults(f=cmd_kien_nghi)
    c = sp.add_parser("thong-ke"); c.add_argument("so"); c.add_argument("--kl", required=True); c.set_defaults(f=cmd_thong_ke)
    c = sp.add_parser("don-vi"); c.add_argument("so"); c.add_argument("ten"); c.set_defaults(f=cmd_don_vi)
    c = sp.add_parser("ra-soat"); c.add_argument("so"); c.set_defaults(f=cmd_ra_soat)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
