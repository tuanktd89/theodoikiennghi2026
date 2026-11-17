from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from pathlib import Path


def parse_date(v) -> date | None:
    """Nhận 'YYYY-MM-DD', 'dd/mm/yyyy', date, datetime → date (hoặc None)."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def iso(v) -> str | None:
    d = parse_date(v)
    return d.isoformat() if d else None


def vn_date(v) -> str:
    d = parse_date(v)
    return d.strftime("%d/%m/%Y") if d else ""


def add_working_days(start: date, n: int) -> date:
    """Cộng n ngày làm việc (bỏ thứ 7, chủ nhật; chưa trừ ngày lễ)."""
    d = start
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def so_kl(so_ky_hieu: str) -> str | None:
    """'38/KL-TTr ngày 10/6/2026' → '38'."""
    m = re.search(r"(\d+)\s*/\s*KL", so_ky_hieu or "", re.I)
    return m.group(1) if m else None


def ma_kl(so_ky_hieu: str, ngay) -> str | None:
    n = so_kl(so_ky_hieu)
    d = parse_date(ngay)
    return f"{n}.{d.year}" if n and d else None


def num2(n: int) -> str:
    """Số 2 chữ số: 1 → '01'."""
    return f"{int(n):02d}"


def safe_name(s: str, limit: int = 80) -> str:
    s = re.sub(r"[\\/:*?\"<>|\n\r\t]+", "_", s).strip()
    return s[:limit] or "file"
