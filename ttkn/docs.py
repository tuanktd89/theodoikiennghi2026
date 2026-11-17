"""Đọc văn bản (PDF, DOCX, ảnh) thành nội dung gửi cho mô hình."""
from __future__ import annotations

import base64
import io
from pathlib import Path

MAX_BYTES = 28 * 1024 * 1024  # giới hạn an toàn cho 1 yêu cầu


def docx_text(path: str | Path) -> str:
    import docx

    d = docx.Document(str(path))
    out = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for row in t.rows:
            out.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(out)


def pdf_text(path: str | Path, max_pages: int = 5) -> str:
    """Lớp chữ của PDF (có thể rỗng/lỗi font nếu là bản scan)."""
    import pdfplumber

    try:
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages[:max_pages])
    except Exception:
        return ""


def pdf_bytes(path: str | Path, max_pages: int = 100) -> bytes:
    from pypdf import PdfReader, PdfWriter

    r = PdfReader(str(path))
    if len(r.pages) <= max_pages:
        return Path(path).read_bytes()
    w = PdfWriter()
    for p in r.pages[:max_pages]:
        w.add_page(p)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def quick_text(path: str | Path, max_pages: int = 3) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".docx":
        return docx_text(p)[:6000]
    if ext == ".pdf":
        return pdf_text(p, max_pages)[:6000]
    return ""


def blocks_for(paths: list[str | Path], max_pdf_pages: int = 100) -> tuple[list[dict], list[str]]:
    """Tạo các khối nội dung (document/image/text) cho Claude.

    Trả (blocks, bỏ_qua) – bỏ_qua là danh sách tệp không đọc được/quá dung lượng."""
    blocks: list[dict] = []
    skipped: list[str] = []
    budget = MAX_BYTES
    for path in paths:
        p = Path(path)
        ext = p.suffix.lower()
        try:
            if ext == ".pdf":
                data = pdf_bytes(p, max_pdf_pages)
                if len(data) > budget:
                    skipped.append(f"{p.name} (quá dung lượng)")
                    continue
                budget -= len(data)
                blocks.append({"type": "text", "text": f"[Tệp: {p.name}]"})
                blocks.append({"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(data).decode()}})
            elif ext in (".png", ".jpg", ".jpeg"):
                data = p.read_bytes()
                if len(data) > min(budget, 5 * 1024 * 1024):
                    skipped.append(f"{p.name} (quá dung lượng)")
                    continue
                budget -= len(data)
                mt = "image/png" if ext == ".png" else "image/jpeg"
                blocks.append({"type": "text", "text": f"[Tệp: {p.name}]"})
                blocks.append({"type": "image", "source": {
                    "type": "base64", "media_type": mt,
                    "data": base64.standard_b64encode(data).decode()}})
            elif ext == ".docx":
                blocks.append({"type": "text",
                               "text": f"[Tệp: {p.name}]\n{docx_text(p)[:60000]}"})
            elif ext in (".txt", ".md", ".csv"):
                blocks.append({"type": "text",
                               "text": f"[Tệp: {p.name}]\n{p.read_text(errors='ignore')[:60000]}"})
            else:
                skipped.append(f"{p.name} (định dạng {ext or '?'} chưa hỗ trợ – hãy chuyển sang PDF)")
        except Exception as e:  # tệp hỏng
            skipped.append(f"{p.name} (lỗi đọc: {e})")
    return blocks, skipped
