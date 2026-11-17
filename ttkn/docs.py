"""Đọc văn bản (PDF, DOCX, ảnh) thành nội dung gửi cho mô hình."""
from __future__ import annotations

import base64
import io
from pathlib import Path

MAX_BYTES = 26 * 1024 * 1024   # giới hạn dung lượng SAU khi mã hóa base64 (API cho tối đa 32 MB/yêu cầu)
PDF_NANG = 8 * 1024 * 1024     # PDF nặng hơn mức này (thường là bản scan) sẽ được nén thành ảnh từng trang
MAX_ANH = 100                  # API cho tối đa 100 ảnh/yêu cầu


def b64len(n: int) -> int:
    return (n + 2) // 3 * 4


def pdf_to_jpegs(path, max_pages: int = 100, dpi: int = 110, quality: int = 70) -> list[bytes]:
    """Render từng trang PDF thành ảnh JPEG nhẹ (dùng cho bản scan quá nặng)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    out = []
    for i in range(min(len(pdf), max_pages)):
        img = pdf[i].render(scale=dpi / 72).to_pil().convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=True)
        out.append(buf.getvalue())
    pdf.close()
    return out


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


from pypdf import PdfReader  # noqa: E402


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
                if len(data) <= PDF_NANG and b64len(len(data)) <= budget:
                    budget -= b64len(len(data))
                    blocks.append({"type": "text", "text": f"[Tệp: {p.name}]"})
                    blocks.append({"type": "document", "source": {
                        "type": "base64", "media_type": "application/pdf",
                        "data": base64.standard_b64encode(data).decode()}})
                    continue
                # PDF nặng: nén thành ảnh từng trang, giảm dần chất lượng cho đến khi vừa giới hạn
                n_img = sum(1 for b in blocks if b["type"] == "image")
                room = max(MAX_ANH - n_img, 0)
                done = False
                for dpi, q in ((110, 70), (90, 60), (72, 55)):
                    pages = pdf_to_jpegs(p, min(max_pdf_pages, room), dpi, q)
                    if sum(b64len(len(x)) for x in pages) <= budget:
                        done = True
                        break
                if not pages or not done:
                    skipped.append(f"{p.name} (quá nặng, không nén được – hãy tách bớt trang)")
                    continue
                total = len(PdfReader(str(p)).pages)
                for i, x in enumerate(pages, 1):
                    budget -= b64len(len(x))
                    blocks.append({"type": "text", "text": f"[Tệp: {p.name} – trang {i}]"})
                    blocks.append({"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": base64.standard_b64encode(x).decode()}})
                if total > len(pages):
                    skipped.append(f"{p.name} (chỉ đọc {len(pages)}/{total} trang đầu do giới hạn dung lượng)")
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
