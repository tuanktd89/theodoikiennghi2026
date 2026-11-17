from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parent.parent / "ttkn" / "app.py")
PAGES = ["Tổng quan & cảnh báo", "Nhập kết luận mới", "Văn bản chỉ đạo UBND", "Văn bản đến",
         "Soạn đôn đốc", "Báo cáo UBND", "Biểu theo dõi"]


@pytest.mark.parametrize("seed", [False, True])
@pytest.mark.parametrize("page", PAGES)
def test_pages_render(page, seed, tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(f"duong_dan:\n  data: {tmp_path}/d\n  db: {tmp_path}/d/x.sqlite\n")
    monkeypatch.setattr("ttkn.config.ROOT", tmp_path)
    if seed:
        from ttkn import db, extract, inbox
        from test_flow import KL_JSON
        c = db.connect(f"{tmp_path}/d/x.sqlite")
        extract.commit_kl(c, dict(KL_JSON))
        inbox.apply_chi_dao(c, {"ma_kl": "38.2026", "so_vb": "1/UBND", "ngay_vb": "2026-07-01", "han_hoan_thanh": "2026-08-01"})
        db.stage(c, "kl_moi", dict(KL_JSON, so_ky_hieu="39/KL-TTr"))
        c.close()
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, at.exception
