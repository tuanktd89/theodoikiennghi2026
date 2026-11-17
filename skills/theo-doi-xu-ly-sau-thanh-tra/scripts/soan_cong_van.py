#!/usr/bin/env python3
"""Tạo công văn đôn đốc .docx từ JSON. Không điền số văn bản, ngày ký, người ký.

Dùng: soan_cong_van.py in.json out.docx
JSON: {"co_quan":"THANH TRA THÀNH PHỐ ...","ve_viec":"...","kinh_gui":"...",
       "can_cu":["..."],"hien_trang":"...","kien_nghi":[{"stt":"1","nguyen_van":"...","ghi_chu":"..."}],
       "de_nghi":"...","han":"dd/mm/yyyy"}
"""
import json, sys
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt


def para(doc, text="", bold=False, italic=False, align=None, indent=True):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if align is not None:
        p.alignment = align
    elif indent:
        p.paragraph_format.first_line_indent = Mm(10)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(6)
    return p


def main(src, dst):
    d = json.load(open(src, encoding="utf-8"))
    doc = Document()
    s = doc.sections[0]
    s.page_width, s.page_height = Mm(210), Mm(297)
    s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Mm(30), Mm(20), Mm(20), Mm(20)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Times New Roman", Pt(14)
    C = WD_ALIGN_PARAGRAPH.CENTER
    para(doc, d.get("co_quan", "THANH TRA THÀNH PHỐ"), bold=True, align=C)
    para(doc, "Số: …/TTr-…", align=C)
    para(doc, "V/v " + d["ve_viec"], align=C, italic=True)
    para(doc, "Kính gửi: " + d["kinh_gui"], bold=True, align=C)
    for c in d.get("can_cu", []):
        para(doc, c)
    if d.get("hien_trang"):
        para(doc, d["hien_trang"])
    for k in d.get("kien_nghi", []):
        para(doc, f"({k['stt']}) “{k['nguyen_van']}”")
        if k.get("ghi_chu"):
            para(doc, "Đánh giá: " + k["ghi_chu"], italic=True)
    para(doc, d["de_nghi"] + (f" trước ngày {d['han']}." if d.get("han") else ""))
    para(doc, "Nơi nhận: …", italic=True, indent=False)
    para(doc, "[Chức vụ – chữ ký – họ tên: người dùng điền]", italic=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    doc.save(dst)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
