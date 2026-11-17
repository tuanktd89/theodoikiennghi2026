"""Cấu hình: đọc config.yaml (nếu có), bổ sung giá trị mặc định."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict = {
    "co_quan": {
        "cap_tren": "ỦY BAN NHÂN DÂN THÀNH PHỐ QUẢNG NINH",
        "ten": "THANH TRA THÀNH PHỐ",
        "ky_hieu": "TTr",
        "dia_danh": "Quảng Ninh",
        "chuc_vu_ky": "CHÁNH THANH TRA",
        "noi_nhan_bao_cao": "Ủy ban nhân dân thành phố",
        "ten_ubnd": "Ủy ban nhân dân thành phố",
        "ten_thanh_tra": "Thanh tra thành phố",
    },
    "llm": {"model": "claude-sonnet-5-5", "max_tokens": 16000, "max_pdf_pages": 100},
    "dondoc": {
        "so_ngay_yeu_cau": 7,          # yêu cầu đơn vị báo cáo trong N ngày kể từ ngày ký
        "bao_truoc_ngay": 7,           # cảnh báo "sắp đến hạn" trước N ngày
        "ngay_lam_viec_bao_cao": 45,   # hạn báo cáo = ngày KL + N ngày làm việc
    },
    "loc_van_ban": {
        # Từ khóa để lọc văn bản đến có liên quan tới việc thực hiện KL
        "tu_khoa": [
            "kết luận thanh tra", "kl-ttr", "thực hiện kết luận", "kiến nghị",
            "xử lý sau thanh tra", "khắc phục", "báo cáo kết quả thực hiện",
        ],
    },
    "duong_dan": {"data": "data", "db": "data/ttkn.sqlite"},
}


def _merge(base: dict, over: dict) -> dict:
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str | Path | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    p = Path(path) if path else ROOT / "config.yaml"
    if p.exists():
        _merge(cfg, yaml.safe_load(p.read_text(encoding="utf-8")) or {})
    data = Path(cfg["duong_dan"]["data"])
    if not data.is_absolute():
        data = ROOT / data
    cfg["duong_dan"]["data"] = str(data)
    db = Path(cfg["duong_dan"]["db"])
    if not db.is_absolute():
        db = ROOT / db
    cfg["duong_dan"]["db"] = str(db)
    return cfg
