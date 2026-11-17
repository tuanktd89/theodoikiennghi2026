"""SQLite: lưu kết luận, kiến nghị, văn bản chỉ đạo, văn bản đến, đề xuất chờ duyệt."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

LOAI_KN = ["Kinh tế", "QLNN", "Trách nhiệm", "Chính sách", "Chuyển CQĐT"]
TINH_TRANG = {"chua": "Chưa thực hiện", "dang": "Đang thực hiện", "xong": "Đã hoàn thành"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS don_vi(
  id INTEGER PRIMARY KEY, ten_chuan TEXT UNIQUE NOT NULL,
  alias TEXT DEFAULT '', loai TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS ket_luan(
  id INTEGER PRIMARY KEY, ma_kl TEXT UNIQUE NOT NULL, so_ky_hieu TEXT, ngay_ban_hanh TEXT,
  trich_yeu TEXT, qd_thanh_tra TEXT, don_vi_duoc_thanh_tra TEXT, nguoi_theo_doi TEXT DEFAULT '',
  han_thuc_hien TEXT, han_text TEXT DEFAULT '', file_goc TEXT DEFAULT '',
  dang_theo_doi INTEGER DEFAULT 1, ngay_ket_thuc TEXT, da_bao_cao_ubnd TEXT,
  ghi_chu TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS van_ban_chi_dao(
  id INTEGER PRIMARY KEY, kl_id INTEGER NOT NULL REFERENCES ket_luan(id),
  so_vb TEXT, ngay_vb TEXT, trich_yeu TEXT, noi_dung TEXT DEFAULT '',
  han_hoan_thanh TEXT, han_bao_cao TEXT, file TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS kien_nghi(
  id INTEGER PRIMARY KEY, kl_id INTEGER NOT NULL REFERENCES ket_luan(id),
  stt INTEGER, noi_dung TEXT NOT NULL, don_vi TEXT NOT NULL, loai TEXT DEFAULT 'QLNN',
  han TEXT, so_tien_trieu REAL, dat_m2 REAL, trang_kl TEXT DEFAULT '',
  tinh_trang TEXT DEFAULT 'chua', da_lam TEXT DEFAULT '', chua_lam TEXT DEFAULT '',
  can_cu TEXT DEFAULT '', so_tien_da_nop_trieu REAL, ket_qua_kiem_diem TEXT DEFAULT '',
  ly_do_chua_dut_diem TEXT DEFAULT '', ngay_cap_nhat TEXT, created_at TEXT);
CREATE INDEX IF NOT EXISTS ix_kn_kl ON kien_nghi(kl_id);
CREATE TABLE IF NOT EXISTS van_ban_den(
  id INTEGER PRIMARY KEY, sha TEXT UNIQUE, ten TEXT, duong_dan TEXT, dinh_kem TEXT DEFAULT '[]',
  ngay_den TEXT, so_ky_hieu TEXT DEFAULT '', don_vi_gui TEXT DEFAULT '', trich_yeu TEXT DEFAULT '',
  nguon TEXT DEFAULT 'thu_cong', phan_loai TEXT DEFAULT '', ma_kl TEXT DEFAULT '',
  trang_thai TEXT DEFAULT 'moi', ghi_chu TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS de_xuat(
  id INTEGER PRIMARY KEY, loai TEXT NOT NULL, vb_id INTEGER, ma_kl TEXT DEFAULT '',
  payload TEXT NOT NULL, trang_thai TEXT DEFAULT 'cho_duyet', created_at TEXT, duyet_at TEXT);
CREATE TABLE IF NOT EXISTS van_ban_don_doc(
  id INTEGER PRIMARY KEY, kl_id INTEGER, don_vi TEXT, so_vb TEXT, ngay_vb TEXT,
  han_tra_loi TEXT, file TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS nhat_ky(
  id INTEGER PRIMARY KEY, thoi_gian TEXT, hanh_dong TEXT, chi_tiet TEXT);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: str | Path) -> sqlite3.Connection:
    p = Path(path)
    if str(path) != ":memory:":
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)  # Streamlit chạy nhiều luồng
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def insert(conn, table: str, row: dict) -> int:
    row = {k: v for k, v in row.items() if v is not None or k in ("han",)}
    if "created_at" in _cols(conn, table) and "created_at" not in row:
        row["created_at"] = now()
    cols = ",".join(row)
    q = ",".join("?" * len(row))
    cur = conn.execute(f"INSERT INTO {table}({cols}) VALUES({q})", list(row.values()))
    conn.commit()
    return cur.lastrowid


def update(conn, table: str, id_: int, row: dict) -> None:
    if not row:
        return
    sets = ",".join(f"{k}=?" for k in row)
    conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*row.values(), id_])
    conn.commit()


def rows(conn, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn, sql: str, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def _cols(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def log(conn, action: str, detail: str = "") -> None:
    conn.execute("INSERT INTO nhat_ky(thoi_gian,hanh_dong,chi_tiet) VALUES(?,?,?)",
                 (now(), action, detail))
    conn.commit()


# ---- đề xuất chờ duyệt -------------------------------------------------
def stage(conn, loai: str, payload: dict, vb_id: int | None = None, ma_kl: str = "") -> int:
    return insert(conn, "de_xuat", {"loai": loai, "vb_id": vb_id, "ma_kl": ma_kl,
                                    "payload": json.dumps(payload, ensure_ascii=False)})


def pending(conn, loai: str | None = None) -> list[dict]:
    q = "SELECT * FROM de_xuat WHERE trang_thai='cho_duyet'"
    p: tuple = ()
    if loai:
        q += " AND loai=?"
        p = (loai,)
    out = rows(conn, q + " ORDER BY id", p)
    for r in out:
        r["payload"] = json.loads(r["payload"])
    return out


def mark(conn, de_xuat_id: int, trang_thai: str) -> None:
    update(conn, "de_xuat", de_xuat_id, {"trang_thai": trang_thai, "duyet_at": now()})


# ---- danh mục đơn vị ---------------------------------------------------
def normalize_unit(conn, name: str) -> tuple[str, bool]:
    """Quy tên đơn vị về tên chuẩn. Trả (tên, có_trong_danh_mục)."""
    n = (name or "").strip()
    if not n:
        return n, False
    r = one(conn, "SELECT ten_chuan FROM don_vi WHERE lower(ten_chuan)=lower(?)", (n,))
    if r:
        return r["ten_chuan"], True
    for d in rows(conn, "SELECT ten_chuan, alias FROM don_vi WHERE alias<>''"):
        if n.lower() in [a.strip().lower() for a in d["alias"].split(";") if a.strip()]:
            return d["ten_chuan"], True
    return n, False
