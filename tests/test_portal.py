"""Kiểm thử bộ quét cổng với một cổng giả chạy cục bộ."""
import functools
import http.server
import os
import threading
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from ttkn import db, portal  # noqa: E402

CHROME = next(iter(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")), None)
pytestmark = pytest.mark.skipif(CHROME is None and not os.environ.get("TTKN_CHROME"),
                                reason="không có trình duyệt Chromium")

TODAY = date.today().strftime("%d/%m/%Y")
INBOX = f"""<html><head><meta charset="utf-8"></head><body><a class="dang-xuat" href="#">Đăng xuất</a>
<table id="ds-van-ban"><tbody>
<tr><td>1</td><td>12/BC-SXD</td><td>{TODAY}</td><td>Sở Xây dựng</td><td><a href="ct1.html">Báo cáo kết quả thực hiện kết luận thanh tra số 38/KL-TTr</a></td></tr>
<tr><td>2</td><td>77/TB-VP</td><td>{TODAY}</td><td>Văn phòng</td><td><a href="ct2.html">Thông báo lịch họp</a></td></tr>
</tbody></table></body></html>"""
CT1 = '<html><head><meta charset="utf-8"></head><body><a class="tep-dinh-kem" href="bc.pdf">bc.pdf</a><a class="tep-dinh-kem" href="kc.pdf">kc.pdf</a></body></html>'


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "inbox.html").write_text(INBOX, encoding="utf-8")
    (root / "ct1.html").write_text(CT1, encoding="utf-8")
    (root / "bc.pdf").write_bytes(b"%PDF-1.4 bao cao")
    (root / "kc.pdf").write_bytes(b"%PDF-1.4 kiem chung")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_fetch_inbox(site, tmp_path):
    cfg = {"inbox_url": f"{site}/inbox.html", "profile_dir": str(tmp_path / "prof"),
           "browser_path": os.environ.get("TTKN_CHROME") or str(CHROME), "logged_in_selector": "a.dang-xuat",
           "inbox": {"row": "table#ds-van-ban tbody tr",
                     "fields": {"so_ky_hieu": "td:nth-child(2)", "ngay_den": "td:nth-child(3)",
                                "don_vi_gui": "td:nth-child(4)", "trich_yeu": "td:nth-child(5)"},
                     "open_link": "td:nth-child(5) a", "attachments": "a.tep-dinh-kem", "max_pages": 1}}
    conn = db.connect(":memory:")
    kw = ["kết luận thanh tra", "kl-ttr"]
    r = portal.fetch_inbox(conn, cfg, tmp_path / "data", kw, since_days=3)
    assert r["duyet"] == 2 and r["bo_qua"] == 1 and len(r["moi"]) == 1
    vb = db.one(conn, "SELECT * FROM van_ban_den")
    assert vb["don_vi_gui"] == "Sở Xây dựng" and vb["nguon"] == "cong_chinh_quyen"
    assert Path(vb["duong_dan"]).read_bytes().startswith(b"%PDF") and "kc.pdf" in vb["dinh_kem"]
    # quét lại không tạo bản trùng
    r2 = portal.fetch_inbox(conn, cfg, tmp_path / "data", kw, since_days=3)
    assert r2["moi"] == [] and db.one(conn, "SELECT COUNT(*) c FROM van_ban_den")["c"] == 1
    # chưa đăng nhập → báo cần đăng nhập, không tải gì
    cfg["logged_in_selector"] = "a.khong-ton-tai"
    assert portal.fetch_inbox(conn, cfg, tmp_path / "data", kw)["can_dang_nhap"] is True
