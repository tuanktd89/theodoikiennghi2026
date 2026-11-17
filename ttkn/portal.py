"""Tự động hóa Cổng chính quyền điện tử bằng Playwright.

Nguyên tắc an toàn:
- KHÔNG lưu mật khẩu trong tệp. Phiên đăng nhập giữ trong thư mục profile của trình duyệt.
- Bước xác thực (OTP, CAPTCHA, chữ ký số) do người dùng làm tay trong cửa sổ trình duyệt.
- Chỉ ĐỌC và TẢI VỀ văn bản đến; công cụ không gửi/ký/ban hành văn bản nào trên cổng.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import yaml

from . import db, inbox
from .util import safe_name


def load_portal(path: str | Path = "portal.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Chưa có {p}. Sao chép portal.example.yaml thành portal.yaml và chỉnh selector.")
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    pd = Path(cfg.get("profile_dir", "data/browser_profile"))
    cfg["profile_dir"] = str(pd if pd.is_absolute() else Path.cwd() / pd)
    return cfg


def _launch(pw, cfg, headless: bool):
    kw = {"headless": headless, "accept_downloads": True, "viewport": {"width": 1366, "height": 900}}
    if cfg.get("browser_path"):
        kw["executable_path"] = cfg["browser_path"]
    return pw.chromium.launch_persistent_context(cfg["profile_dir"], **kw)


def is_logged_in(page, cfg) -> bool:
    sel = cfg.get("logged_in_selector")
    return bool(sel) and page.locator(sel).count() > 0


def login(cfg: dict, wait_seconds: int = 600) -> bool:
    """Mở cửa sổ trình duyệt; người dùng đăng nhập (có thể nhập OTP/CAPTCHA). Phiên được lưu lại."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx = _launch(pw, cfg, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(cfg["login_url"])
        user, pwd = os.environ.get("PORTAL_USER"), os.environ.get("PORTAL_PASS")
        f = cfg.get("login_form") or {}
        if user and pwd and f.get("user") and page.locator(f["user"]).count():
            page.fill(f["user"], user)
            page.fill(f["password"], pwd)
            if f.get("submit"):
                page.click(f["submit"])
        ok = False
        for _ in range(wait_seconds):
            if is_logged_in(page, cfg):
                ok = True
                break
            page.wait_for_timeout(1000)
        ctx.close()
        return ok


def inspect(cfg: dict, out_dir: str | Path = "data/portal_inspect") -> list[Path]:
    """Lưu ảnh chụp + HTML của trang đăng nhập/hộp thư để chỉnh selector."""
    from playwright.sync_api import sync_playwright

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    with sync_playwright() as pw:
        ctx = _launch(pw, cfg, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(cfg["inbox_url"])
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(out / "inbox.png"), full_page=True)
        (out / "inbox.html").write_text(page.content(), encoding="utf-8")
        files = [out / "inbox.png", out / "inbox.html"]
        ctx.close()
    return files


def _download(ctx, page, link, dest_dir: Path) -> Path | None:
    name = (link.inner_text() or "").strip()
    href = link.get_attribute("href")
    try:
        if href and not href.startswith(("javascript", "#")):
            url = urljoin(page.url, href)
            r = ctx.request.get(url)
            if r.ok and "text/html" not in (r.headers.get("content-type") or ""):
                disp = r.headers.get("content-disposition") or ""
                m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disp)
                fn = safe_name(m.group(1) if m else (name or Path(url).name or "tep"), 120)
                if not Path(fn).suffix:
                    fn += ".pdf"
                p = dest_dir / fn
                p.write_bytes(r.body())
                return p
        with page.expect_download(timeout=30000) as dl:
            link.click()
        d = dl.value
        p = dest_dir / safe_name(d.suggested_filename, 120)
        d.save_as(str(p))
        return p
    except Exception:
        return None


def fetch_inbox(conn, cfg: dict, data_dir: str | Path, keywords: list[str], since_days: int = 7,
                headless: bool = True, all_docs: bool = False) -> dict:
    """Duyệt hộp thư đến, tải văn bản (và tệp đính kèm) có từ khóa liên quan, ghi vào CSDL.

    Văn bản không khớp từ khóa được bỏ qua (không tải) trừ khi all_docs=True."""
    from playwright.sync_api import sync_playwright

    ib = cfg["inbox"]
    since = date.today() - timedelta(days=since_days)
    res = {"duyet": 0, "tai": 0, "moi": [], "bo_qua": 0, "can_dang_nhap": False}
    with sync_playwright() as pw:
        ctx = _launch(pw, cfg, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(cfg["inbox_url"])
        page.wait_for_load_state("networkidle")
        if cfg.get("logged_in_selector") and not is_logged_in(page, cfg):
            res["can_dang_nhap"] = True
            ctx.close()
            return res
        for _ in range(int(ib.get("max_pages", 1))):
            rows = page.locator(ib["row"])
            items = []
            for i in range(rows.count()):
                r = rows.nth(i)
                meta = {}
                for k, sel in ib["fields"].items():
                    loc = r.locator(sel)
                    meta[k] = (loc.first.inner_text().strip() if loc.count() else "")
                try:
                    d = datetime.strptime(meta.get("ngay_den", "")[:10], ib.get("date_format", "%d/%m/%Y")).date()
                except ValueError:
                    d = None
                href = None
                if ib.get("open_link") and r.locator(ib["open_link"]).count():
                    href = urljoin(page.url, r.locator(ib["open_link"]).first.get_attribute("href") or "")
                items.append((meta, d, href, i))
            stop = False
            for meta, d, href, i in items:
                res["duyet"] += 1
                if d and d < since:
                    stop = True
                    continue
                text = " ".join([meta.get("trich_yeu", ""), meta.get("so_ky_hieu", "")])
                if not all_docs and not inbox.keyword_hit(text, keywords):
                    res["bo_qua"] += 1
                    continue
                dest = Path(data_dir) / "vanban_den" / (d.isoformat() if d else "khong_ngay") / \
                    safe_name(f"{meta.get('so_ky_hieu', '')}_{meta.get('don_vi_gui', '')}", 80)
                if inbox_known(conn, meta, d):
                    continue
                dest.mkdir(parents=True, exist_ok=True)
                tab = page
                if href:
                    tab = ctx.new_page()
                    tab.goto(href)
                    tab.wait_for_load_state("networkidle")
                files = []
                links = tab.locator(ib["attachments"])
                for j in range(links.count()):
                    f = _download(ctx, tab, links.nth(j), dest)
                    if f:
                        files.append(f)
                if href:
                    tab.close()
                if files:
                    res["tai"] += 1
                    vid = inbox.register(conn, files[0], files[1:], so_ky_hieu=meta.get("so_ky_hieu", ""),
                                         don_vi_gui=meta.get("don_vi_gui", ""), trich_yeu=meta.get("trich_yeu", ""),
                                         ngay_den=d, nguon="cong_chinh_quyen")
                    if vid:
                        res["moi"].append(vid)
            if stop or not ib.get("next_page") or not page.locator(ib["next_page"]).count():
                break
            page.locator(ib["next_page"]).first.click()
            page.wait_for_load_state("networkidle")
        ctx.close()
    db.log(conn, "Quét cổng", f"duyệt {res['duyet']}, tải {res['tai']}, mới {len(res['moi'])}")
    return res


def inbox_known(conn, meta: dict, d) -> bool:
    return bool(db.one(conn, "SELECT id FROM van_ban_den WHERE nguon='cong_chinh_quyen' AND so_ky_hieu=? "
                             "AND don_vi_gui=? AND COALESCE(ngay_den,'')=?",
                       (meta.get("so_ky_hieu", ""), meta.get("don_vi_gui", ""), d.isoformat() if d else "")))
