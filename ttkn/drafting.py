"""Soạn thảo văn bản Word: công văn đôn đốc, báo cáo kết quả thực hiện kết luận (số liệu đếm từ dữ liệu)."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

from . import alerts, db
from .util import num2, parse_date, safe_name, vn_date

FONT = "Times New Roman"
LOAI_NHOM = [("QLNN", "Kiến nghị về quản lý nhà nước"), ("Trách nhiệm", "Kiến nghị xử lý trách nhiệm"),
             ("Kinh tế", "Kiến nghị xử lý về kinh tế"), ("Chính sách", "Kiến nghị về cơ chế, chính sách"),
             ("Chuyển CQĐT", "Kiến nghị chuyển cơ quan điều tra")]


# ---------------------------------------------------------------- tiện ích Word
def _new_doc(size: int = 14) -> Document:
    d = Document()
    s = d.sections[0]
    s.page_height, s.page_width = Mm(297), Mm(210)
    s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Mm(30), Mm(20), Mm(20), Mm(20)
    st = d.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(size)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    st.paragraph_format.space_after = Pt(0)
    return d


def _p(d, text="", bold=False, italic=False, align=None, size=None, indent=True, space_after=6, line=1.15,
       keep=False):
    p = d.add_paragraph()
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "right":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if indent:
            p.paragraph_format.first_line_indent = Mm(12.5)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line
    p.paragraph_format.keep_with_next = keep
    if text:
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
    return p


def _quoc_hieu(d, cfg, so_hieu: str, ngay_text: str, trich_yeu_vb: str | None, loai_vb="CV"):
    co = cfg["co_quan"]
    t = d.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    L, R = t.rows[0].cells
    L.width, R.width = Mm(75), Mm(95)

    def cell(c, lines):
        c.paragraphs[0].text = ""
        first = True
        for txt, b, sz in lines:
            p = c.paragraphs[0] if first else c.add_paragraph()
            first = False
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(txt)
            r.bold, r.font.size = b, Pt(sz)

    cell(L, [(co["cap_tren"], False, 13), (co["ten"], True, 13), ("_______", False, 12),
             (f"Số:        /{so_hieu}", False, 13)])
    cell(R, [("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", True, 13), ("Độc lập - Tự do - Hạnh phúc", True, 14),
             ("____________________", False, 12), (f"{co['dia_danh']}, {ngay_text}", False, 14)])
    R.paragraphs[-1].runs[0].italic = True
    if trich_yeu_vb:
        _p(d, "", space_after=0)
        _p(d, f"V/v {trich_yeu_vb}", align="left", indent=False, size=13, space_after=6)


def _noi_nhan(d, cfg, nhan: list[str], chuc_vu: str | None = None):
    _p(d, "", space_after=0)
    t = d.add_table(rows=1, cols=2)
    L, R = t.rows[0].cells
    L.paragraphs[0].text = ""
    r = L.paragraphs[0].add_run("Nơi nhận:")
    r.bold, r.italic, r.font.size = True, True, Pt(12)
    for n in nhan:
        L.add_paragraph().add_run(f"- {n};").font.size = Pt(11)
    R.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = R.paragraphs[0].add_run(chuc_vu or cfg["co_quan"]["chuc_vu_ky"])
    rr.bold = True
    for _ in range(4):
        R.add_paragraph()
    R.add_paragraph().alignment = WD_ALIGN_PARAGRAPH.CENTER


def _footnotes_as_list(d, items: list[str]):
    for i, s in enumerate(items, 1):
        _p(d, f"({i}) {s}", size=12, indent=False, space_after=2)


# ------------------------------------------------------------- công văn đôn đốc
def _qua_han_text(g: dict, today: date) -> str:
    h = g.get("han")
    if h is None:
        return "Hiện nay chưa xác định được thời hạn hoàn thành."
    if (g.get("qua_han_ngay") or 0) > 0:
        return f"Đến ngày {vn_date(today)}, đã quá hạn {g['qua_han_ngay']} ngày (hạn hoàn thành: {vn_date(h)})."
    return f"Thời hạn hoàn thành là ngày {vn_date(h)} (còn {(h - today).days} ngày)."


def soan_don_doc(conn, cfg: dict, kl_id: int, don_vi: str, out_dir: str | Path,
                 today: date | None = None, so_ngay: int | None = None) -> Path:
    """Công văn đôn đốc gửi 1 đơn vị về 1 kết luận: chỉ liệt kê kiến nghị còn tồn của đơn vị đó."""
    today = today or date.today()
    co = cfg["co_quan"]
    kl = db.one(conn, "SELECT * FROM ket_luan WHERE id=?", (kl_id,))
    cd = alerts.latest_chi_dao(conn, kl_id)
    kns = db.rows(conn, "SELECT * FROM kien_nghi WHERE kl_id=? AND don_vi=? AND tinh_trang<>'xong' ORDER BY stt",
                  (kl_id, don_vi))
    if not kns:
        raise ValueError(f"{don_vi} không còn kiến nghị tồn ở KL {kl['ma_kl']}.")
    so_ngay = so_ngay or cfg["dondoc"]["so_ngay_yeu_cau"]
    han_tl = today + timedelta(days=so_ngay)
    han_goc = max((h for h in (alerts.han_kn(k, kl, cd) for k in kns) if h), default=None)
    lan = db.one(conn, "SELECT COUNT(*) c FROM van_ban_don_doc WHERE kl_id=? AND don_vi=?", (kl_id, don_vi))["c"]

    d = _new_doc()
    _quoc_hieu(d, cfg, f"{co['ky_hieu']}-GSTĐ", f"ngày     tháng     năm {today.year}",
               f"đôn đốc thực hiện kiến nghị tại Kết luận số {kl['so_ky_hieu']}"
               + (f" (lần {lan + 1})" if lan else ""))
    _p(d, "")
    _p(d, f"Kính gửi: {don_vi}", bold=True, align="center", indent=False)
    _p(d, "")

    mo = f"Thực hiện Kết luận thanh tra số {kl['so_ky_hieu']}"
    if kl.get("ngay_ban_hanh"):
        mo += f" ngày {vn_date(kl['ngay_ban_hanh'])}"
    mo += f" về {kl['trich_yeu']}"
    if cd and cd.get("so_vb"):
        mo += (f"; Văn bản số {cd['so_vb']}" + (f" ngày {vn_date(cd['ngay_vb'])}" if cd.get("ngay_vb") else "")
               + f" của {co['ten_ubnd']} chỉ đạo thực hiện kết luận thanh tra")
        if cd.get("han_hoan_thanh"):
            mo += f" (hạn hoàn thành trước ngày {vn_date(cd['han_hoan_thanh'])})"
    mo += "."
    _p(d, mo)
    if lan:
        _p(d, f"{co['ten_thanh_tra']} đã có {lan} văn bản đôn đốc, tuy nhiên đến nay đơn vị chưa hoàn thành đầy đủ các kiến nghị.")
    _p(d, f"Qua theo dõi, {_qua_han_text({'han': han_goc, 'qua_han_ngay': (today - han_goc).days if han_goc else None}, today)} "
          f"Đến nay {co['ten_thanh_tra']} chưa nhận được báo cáo đầy đủ kèm tài liệu kiểm chứng về việc thực hiện "
          f"{num2(len(kns))} kiến nghị sau của {don_vi}:")
    for k in kns:
        _p(d, f"{k['stt']}. “{k['noi_dung'].strip()}”", indent=False, space_after=2)
        if k["da_lam"]:
            _p(d, f"- Đã thực hiện: {k['da_lam']}", italic=True, indent=False, space_after=2)
        if k["chua_lam"]:
            _p(d, f"- Còn thiếu/chưa thực hiện: {k['chua_lam']}", italic=True, indent=False, space_after=2)
        elif not k["da_lam"]:
            _p(d, "- Chưa có báo cáo kết quả thực hiện.", italic=True, indent=False, space_after=2)
    _p(d, "")
    _p(d, f"Để bảo đảm tiến độ và có cơ sở báo cáo {co['ten_ubnd']}, {co['ten_thanh_tra']} đề nghị {don_vi}:")
    _p(d, "1. Khẩn trương tổ chức thực hiện dứt điểm các kiến nghị nêu trên theo đúng nội dung kết luận thanh tra.")
    _p(d, f"2. Báo cáo bằng văn bản kết quả thực hiện (kèm tài liệu kiểm chứng như quyết định, biên bản, chứng từ nộp tiền...) "
          f"gửi {co['ten_thanh_tra']} qua Cổng chính quyền điện tử trước ngày {vn_date(han_tl)}.")
    _p(d, f"{co['ten_thanh_tra']} đề nghị {don_vi} quan tâm, phối hợp thực hiện./.")
    _noi_nhan(d, cfg, [don_vi, co["ten_ubnd"] + " (để báo cáo)", "Lưu: VT, hồ sơ"])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"DonDoc_KL{kl['ma_kl']}_{safe_name(don_vi, 50)}_{today:%Y%m%d}.docx"
    d.save(f)
    return f


def ghi_nhan_don_doc(conn, kl_id: int, don_vi: str, so_vb: str, ngay_vb, han_tra_loi=None, file: str = "") -> int:
    """Người dùng xác nhận đã ban hành công văn đôn đốc (để tính 'lần đôn đốc' và cảnh báo)."""
    from .util import iso
    i = db.insert(conn, "van_ban_don_doc", {"kl_id": kl_id, "don_vi": don_vi, "so_vb": so_vb,
                                            "ngay_vb": iso(ngay_vb), "han_tra_loi": iso(han_tra_loi), "file": file})
    db.log(conn, "Ghi nhận công văn đôn đốc", f"KL {kl_id} - {don_vi} - {so_vb}")
    return i


# --------------------------------------------------------------- báo cáo UBND
def so_lieu_kl(conn, kl_id: int) -> dict:
    """Số liệu đếm trực tiếp từ dữ liệu; dùng cho báo cáo và đối chiếu."""
    kns = db.rows(conn, "SELECT * FROM kien_nghi WHERE kl_id=? ORDER BY stt", (kl_id,))
    s = {"tong": len(kns), "xong": sum(k["tinh_trang"] == "xong" for k in kns),
         "dang": sum(k["tinh_trang"] == "dang" for k in kns),
         "chua": sum(k["tinh_trang"] == "chua" for k in kns), "theo_loai": {}, "theo_don_vi": {}}
    for k in kns:
        L = s["theo_loai"].setdefault(k["loai"], {"tong": 0, "xong": 0})
        L["tong"] += 1
        L["xong"] += k["tinh_trang"] == "xong"
        D = s["theo_don_vi"].setdefault(k["don_vi"], {"tong": 0, "xong": 0, "dang": 0, "chua": 0})
        D["tong"] += 1
        D[k["tinh_trang"]] += 1
    s["kns"] = kns
    return s


def kiem_tra_so_lieu(s: dict) -> list[str]:
    err = []
    if s["tong"] != s["xong"] + s["dang"] + s["chua"]:
        err.append("Tổng kiến nghị khác tổng các tình trạng.")
    if s["tong"] != sum(v["tong"] for v in s["theo_loai"].values()):
        err.append("Tổng kiến nghị khác tổng theo loại.")
    if s["tong"] != sum(v["tong"] for v in s["theo_don_vi"].values()):
        err.append("Tổng kiến nghị khác tổng theo đơn vị.")
    return err


def _ket_qua_text(k: dict) -> str:
    parts = []
    if k["da_lam"]:
        parts.append(k["da_lam"].strip())
    if k["tinh_trang"] != "xong" and k["chua_lam"]:
        parts.append(f"Nội dung chưa thực hiện: {k['chua_lam'].strip()}")
    if k["ket_qua_kiem_diem"]:
        parts.append(f"Kết quả kiểm điểm: {k['ket_qua_kiem_diem'].strip()}")
    if k["so_tien_da_nop_trieu"]:
        parts.append(f"Số tiền đã nộp: {k['so_tien_da_nop_trieu']:,.0f} triệu đồng.")
    return " ".join(parts) or f"Đến thời điểm báo cáo, {k['don_vi']} chưa có văn bản báo cáo kết quả thực hiện."


def soan_bao_cao_kl(conn, cfg: dict, kl_id: int, out_dir: str | Path, today: date | None = None) -> tuple[Path, dict]:
    """Báo cáo UBND kết quả thực hiện 1 kết luận (cấu trúc I–IV theo mẫu). Trả (file, số liệu)."""
    today = today or date.today()
    co = cfg["co_quan"]
    kl = db.one(conn, "SELECT * FROM ket_luan WHERE id=?", (kl_id,))
    cd = alerts.latest_chi_dao(conn, kl_id)
    dds = db.rows(conn, "SELECT * FROM van_ban_don_doc WHERE kl_id=? ORDER BY COALESCE(ngay_vb,''), id", (kl_id,))
    s = so_lieu_kl(conn, kl_id)
    err = kiem_tra_so_lieu(s)
    if err:
        raise ValueError("; ".join(err))

    d = _new_doc()
    _quoc_hieu(d, cfg, f"BC-{co['ky_hieu']}", f"ngày     tháng     năm {today.year}", None)
    _p(d, "")
    _p(d, "BÁO CÁO", bold=True, align="center", indent=False, space_after=0, size=14)
    _p(d, f"Kết quả thực hiện Kết luận số {kl['so_ky_hieu']} ngày {vn_date(kl['ngay_ban_hanh'])} "
          f"của Chánh Thanh tra về {kl['trich_yeu']}", bold=True, align="center", indent=False, space_after=6)
    _p(d, f"Kính gửi: {co['noi_nhan_bao_cao']}", bold=True, align="center", indent=False)
    mo = "Thực hiện "
    mo += (f"Văn bản số {cd['so_vb']} ngày {vn_date(cd['ngay_vb'])} của {co['ten_ubnd']}"
           f"{' về ' + cd['trich_yeu'] if cd.get('trich_yeu') else ''}"
           if cd and cd.get("so_vb") else f"Kết luận số {kl['so_ky_hieu']}")
    mo += (f". Trên cơ sở báo cáo kết quả thực hiện của các sở, ngành, địa phương, đơn vị có liên quan, "
           f"{co['ten_thanh_tra']} báo cáo kết quả thực hiện như sau:")
    _p(d, mo)

    _p(d, "I. KHÁI QUÁT CHUNG", bold=True, indent=False, keep=True)
    khai = [f"Quyết định thanh tra: {kl['qd_thanh_tra'] or '(chưa nhập)'}.",
            f"Kết luận thanh tra số {kl['so_ky_hieu']} ngày {vn_date(kl['ngay_ban_hanh'])} về {kl['trich_yeu']}."]
    if cd and cd.get("so_vb"):
        t = f"Văn bản chỉ đạo của {co['ten_ubnd']}: số {cd['so_vb']} ngày {vn_date(cd['ngay_vb'])}"
        if cd.get("han_hoan_thanh"):
            t += f"; yêu cầu hoàn thành trước ngày {vn_date(cd['han_hoan_thanh'])}"
        khai.append(t + ".")
    for x in khai:
        _p(d, x)
    if dds:
        _p(d, "Các văn bản đôn đốc:")
        _footnotes_as_list(d, [f"Văn bản số {x['so_vb']} ngày {vn_date(x['ngay_vb'])} gửi {x['don_vi']}" for x in dds])

    _p(d, "II. KẾT QUẢ THỰC HIỆN", bold=True, indent=False, keep=True)
    loai_txt = [f"{num2(v['tong'])} {n.lower()}" for (lo, n) in LOAI_NHOM if (v := s["theo_loai"].get(lo))]
    if "Kinh tế" not in s["theo_loai"]:
        loai_txt.append("không có kiến nghị xử lý về kinh tế")
    _p(d, f"Tổng số nội dung kiến nghị tại Kết luận là {num2(s['tong'])} kiến nghị ({'; '.join(loai_txt)}); "
          f"trong đó đã thực hiện xong {num2(s['xong'])} kiến nghị, {num2(s['dang'])} kiến nghị đang thực hiện"
          f"{', ' + num2(s['chua']) + ' kiến nghị chưa thực hiện' if s['chua'] else ''}.")
    for dv, v in s["theo_don_vi"].items():
        _p(d, f"- {dv}: có trách nhiệm thực hiện {num2(v['tong'])} kiến nghị, đã thực hiện xong {num2(v['xong'])}, "
              f"đang thực hiện {num2(v['dang'])}{', chưa thực hiện ' + num2(v['chua']) if v['chua'] else ''}.",
           indent=False)

    gi = 0
    for lo, ten in LOAI_NHOM:
        if lo not in s["theo_loai"]:
            continue
        gi += 1
        _p(d, f"{gi}. {ten}", bold=True, indent=False, keep=True)
        sub = [k for k in s["kns"] if k["loai"] == lo]
        for j, (lbl, cond) in enumerate([("đã thực hiện xong", lambda k: k["tinh_trang"] == "xong"),
                                         ("đang thực hiện / chưa thực hiện", lambda k: k["tinh_trang"] != "xong")], 1):
            items = [k for k in sub if cond(k)]
            if not items:
                continue
            _p(d, f"{gi}.{j}. Kiến nghị {lbl} ({num2(len(items))})", italic=True, bold=True, indent=False, keep=True)
            for dv in dict.fromkeys(k["don_vi"] for k in items):
                mine = [k for k in items if k["don_vi"] == dv]
                _p(d, f"- Trách nhiệm của {dv} ({num2(len(mine))} kiến nghị)", bold=True, indent=False, keep=True)
                for k in mine:
                    _p(d, f"({k['stt']}) Kiến nghị {num2(k['stt'])}: “{k['noi_dung'].strip()}”", indent=False, space_after=2)
                    _p(d, f"*Kết quả thực hiện: {_ket_qua_text(k)}", italic=True, indent=False)

    _p(d, "III. KHÓ KHĂN, VƯỚNG MẮC", bold=True, indent=False, keep=True)
    vuong = [k for k in s["kns"] if k["ly_do_chua_dut_diem"]]
    if vuong:
        for k in vuong:
            _p(d, f"- {k['don_vi']} (Kiến nghị {num2(k['stt'])}): {k['ly_do_chua_dut_diem']}", indent=False)
    else:
        _p(d, "Chưa ghi nhận khó khăn, vướng mắc do các đơn vị nêu.")

    _p(d, "IV. ĐỀ XUẤT, KIẾN NGHỊ", bold=True, indent=False, keep=True)
    _p(d, "[Bản nháp – đề nghị thanh tra viên xem xét, quyết định]", italic=True, indent=False)
    con = [dv for dv, v in s["theo_don_vi"].items() if v["dang"] or v["chua"]]
    if con:
        _p(d, f"1. Đề nghị {co['ten_ubnd']} tiếp tục chỉ đạo các đơn vị sau hoàn thành các kiến nghị còn lại "
              f"và báo cáo {co['ten_thanh_tra']} trước ngày ...: " + "; ".join(con) + ".")
        _p(d, f"2. {co['ten_thanh_tra']} tiếp tục theo dõi, đôn đốc các đơn vị thực hiện, báo cáo {co['ten_ubnd']} kết quả.")
    else:
        _p(d, f"Các kiến nghị đã được thực hiện xong; {co['ten_thanh_tra']} đề nghị {co['ten_ubnd']} cho kết thúc theo dõi.")
    _noi_nhan(d, cfg, [co["noi_nhan_bao_cao"] + " (để báo cáo)", "Lưu: VT, hồ sơ"])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"BaoCao_KL{kl['ma_kl']}_{today:%Y%m%d}.docx"
    d.save(f)
    return f, {k: v for k, v in s.items() if k != "kns"}
