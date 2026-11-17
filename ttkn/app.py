"""Giao diện Streamlit: streamlit run ttkn/app.py"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ttkn import alerts, db, drafting, excel_io, extract, inbox
from ttkn.config import load_config
from ttkn.util import iso, parse_date, vn_date

st.set_page_config(page_title="Theo dõi sau thanh tra", page_icon="📋", layout="wide")
TT = db.TINH_TRANG
DG = {"dam_bao": "Đảm bảo", "chua_dam_bao": "Chưa đảm bảo", "chua_co_thong_tin": "Chưa có thông tin"}
DG_REV = {v: k for k, v in DG.items()}
MUC = {"qua_han": "🔴 Quá hạn", "sap_den_han": "🟠 Sắp đến hạn", "khong_co_han": "⚪ Chưa có hạn"}


@st.cache_resource
def _ctx():
    cfg = load_config()
    return cfg, db.connect(cfg["duong_dan"]["db"])


cfg, conn = _ctx()
DATA = Path(cfg["duong_dan"]["data"])


def get_llm():
    from ttkn.llm import ClaudeLLM, LLMError
    try:
        return ClaudeLLM(cfg["llm"]["model"], cfg["llm"]["max_tokens"])
    except LLMError as e:
        st.error(str(e))
        st.stop()


def dl(path: Path, label: str | None = None, key: str | None = None):
    st.download_button(label or f"⬇️ Tải {path.name}", path.read_bytes(), file_name=path.name,
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=key or str(path))


def kl_options() -> dict[str, int]:
    return {f"{k['ma_kl']} – {k['so_ky_hieu']} – {(k['trich_yeu'] or '')[:70]}": k["id"]
            for k in db.rows(conn, "SELECT * FROM ket_luan ORDER BY ngay_ban_hanh DESC")}


# =================================================================== trang
def page_tong_quan():
    st.title("📋 Tổng quan & cảnh báo")
    s = alerts.thong_ke(conn)
    c = st.columns(5)
    c[0].metric("KL đang theo dõi", s["kl_dang_theo_doi"])
    c[1].metric("Tổng kiến nghị", s["kn_tong"])
    c[2].metric("Đã hoàn thành", s["kn_xong"])
    c[3].metric("Kiến nghị quá hạn", s["kn_qua_han"])
    c[4].metric("Đơn vị quá hạn", s["don_vi_qua_han"])
    pend = len(db.pending(conn))
    if pend:
        st.warning(f"Có **{pend}** đề xuất đang chờ bạn duyệt (mục *Nhập kết luận* / *Văn bản đến*).")
    st.subheader("🔔 Đến hạn báo cáo UBND")
    br = alerts.den_han_bao_cao(conn, cfg=cfg)
    if br:
        st.dataframe(pd.DataFrame([{"Mã KL": r["ma_kl"], "Số KL": r["so_ky_hieu"], "Hạn báo cáo": vn_date(r["han_bao_cao"]),
                                    "Còn (ngày)": r["con_ngay"], "KN xong/tổng": f"{r['xong']}/{r['tong_kn']}"} for r in br]),
                     hide_index=True, use_container_width=True)
        st.caption("Vào mục *Báo cáo UBND* để soạn báo cáo.")
    else:
        st.success("Chưa có KL nào đến hạn báo cáo.")
    st.subheader("⏰ Đơn vị quá hạn / sắp đến hạn chưa dứt điểm")
    g = alerts.canh_bao_don_doc(conn, bao_truoc=cfg["dondoc"]["bao_truoc_ngay"])
    if g:
        st.dataframe(pd.DataFrame([{"Mức": MUC[x["muc"]], "Mã KL": x["ma_kl"], "Đơn vị": x["don_vi"],
                                    "Hạn": vn_date(x["han"]), "Quá hạn (ngày)": max(x["qua_han_ngay"] or 0, 0),
                                    "KN tồn": len(x["kn"]), "Đã đôn đốc (lần)": x["lan_don_doc"]} for x in g]),
                     hide_index=True, use_container_width=True)
    else:
        st.success("Không có đơn vị nào quá hạn.")


def page_nhap_kl():
    st.title("📥 Nhập kết luận thanh tra mới")
    st.caption("Tải file Kết luận (PDF/Word, kể cả bản scan). AI trích xuất → bạn rà soát/sửa → bấm Duyệt thì mới ghi vào sổ.")
    up = st.file_uploader("File kết luận", type=["pdf", "docx"], accept_multiple_files=True)
    if up and st.button("🔍 Phân tích kết luận", type="primary"):
        llm = get_llm()
        for f in up:
            p = DATA / "ket_luan"
            p.mkdir(parents=True, exist_ok=True)
            path = p / f.name
            path.write_bytes(f.getbuffer())
            with st.spinner(f"Đang đọc {f.name}…"):
                try:
                    extract.stage_kl(conn, extract.extract_kl(llm, path, cfg["llm"]["max_pdf_pages"]))
                except Exception as e:
                    st.error(f"{f.name}: {e}")
        st.rerun()
    for d in db.pending(conn, "kl_moi"):
        p = d["payload"]
        with st.expander(f"#{d['id']} · {p.get('so_ky_hieu')} · {len(p.get('kien_nghi', []))} kiến nghị", expanded=True):
            for w in p.get("canh_bao", []):
                st.warning(w)
            c = st.columns(3)
            p["so_ky_hieu"] = c[0].text_input("Số ký hiệu", p.get("so_ky_hieu", ""), key=f"sk{d['id']}")
            p["ngay_ban_hanh"] = c[1].text_input("Ngày ban hành (YYYY-MM-DD)", p.get("ngay_ban_hanh") or "", key=f"nb{d['id']}")
            p["han_thuc_hien"] = c[2].text_input("Hạn thực hiện chung", p.get("han_thuc_hien") or "", key=f"ht{d['id']}")
            p["trich_yeu"] = st.text_area("Trích yếu", p.get("trich_yeu", ""), key=f"ty{d['id']}")
            p["qd_thanh_tra"] = st.text_input("Quyết định thanh tra", p.get("qd_thanh_tra", ""), key=f"qd{d['id']}")
            ntd = st.text_input("Người theo dõi", key=f"ntd{d['id']}")
            df = pd.DataFrame(p.get("kien_nghi", []))
            for col in ("stt", "noi_dung", "don_vi", "loai", "han", "so_tien_trieu", "dat_m2", "trang"):
                if col not in df:
                    df[col] = None
            ed = st.data_editor(df[["stt", "noi_dung", "don_vi", "loai", "han", "so_tien_trieu", "dat_m2", "trang"]],
                                num_rows="dynamic", use_container_width=True, key=f"kn{d['id']}",
                                column_config={"loai": st.column_config.SelectboxColumn(options=db.LOAI_KN),
                                               "noi_dung": st.column_config.TextColumn(width="large")})
            p["kien_nghi"] = [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in ed.to_dict("records")]
            b = st.columns(3)
            if b[0].button("✅ Duyệt & ghi sổ", key=f"ok{d['id']}", type="primary"):
                try:
                    extract.commit_kl(conn, p, ntd)
                    db.mark(conn, d["id"], "da_duyet")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if b[1].button("🔄 Kiểm tra lại", key=f"re{d['id']}"):
                p["canh_bao"] = extract.validate_kl(conn, p)
                conn.execute("UPDATE de_xuat SET payload=? WHERE id=?", (__import__("json").dumps(p, ensure_ascii=False), d["id"]))
                conn.commit()
                st.rerun()
            if b[2].button("🗑️ Từ chối", key=f"no{d['id']}"):
                db.mark(conn, d["id"], "tu_choi")
                st.rerun()


def page_chi_dao():
    st.title("🏛️ Văn bản chỉ đạo của UBND thành phố")
    st.caption("Nhập tay, hoặc để AI nhận diện từ *Văn bản đến*. Hạn trong văn bản chỉ đạo được ưu tiên khi tính quá hạn.")
    opts = kl_options()
    if not opts:
        st.info("Chưa có kết luận nào.")
        return
    with st.form("cd"):
        kl = st.selectbox("Kết luận", list(opts))
        c = st.columns(3)
        so, ngay, han = c[0].text_input("Số văn bản"), c[1].date_input("Ngày", value=date.today()), c[2].date_input("Hạn hoàn thành", value=None)
        ty, nd = st.text_input("Trích yếu"), st.text_area("Nội dung chỉ đạo")
        hbc = st.date_input("Hạn báo cáo UBND (nếu khác hạn hoàn thành)", value=None)
        if st.form_submit_button("Lưu", type="primary"):
            ma = db.one(conn, "SELECT ma_kl FROM ket_luan WHERE id=?", (opts[kl],))["ma_kl"]
            inbox.apply_chi_dao(conn, {"ma_kl": ma, "so_vb": so, "ngay_vb": ngay, "trich_yeu": ty, "noi_dung": nd,
                                       "han_hoan_thanh": han, "han_bao_cao": hbc})
            st.success("Đã lưu.")
    rows = db.rows(conn, "SELECT l.ma_kl, c.so_vb, c.ngay_vb, c.han_hoan_thanh, c.trich_yeu FROM van_ban_chi_dao c "
                         "JOIN ket_luan l ON l.id=c.kl_id ORDER BY c.ngay_vb DESC")
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _review_ket_qua(d):
    p = d["payload"]
    st.markdown(f"**KL {p['ma_kl']}** · báo cáo: *{p['vb']['ten']}* · gửi bởi **{p['vb']['don_vi_gui'] or '?'}**")
    if p.get("nhan_xet_chung"):
        st.info(p["nhan_xet_chung"])
    if p.get("bo_qua_tep"):
        st.warning("Tệp chưa đọc được: " + "; ".join(p["bo_qua_tep"]))
    df = pd.DataFrame([{"Ghi": r["danh_gia"] != "chua_co_thong_tin", "ID": r["kien_nghi_id"], "KN": r["_stt"],
                        "Đơn vị": r["_don_vi"], "Nội dung kiến nghị": r["_noi_dung"], "Đánh giá": DG[r["danh_gia"]],
                        "Đã làm": r["da_lam"], "Chưa làm": r["chua_lam"], "Căn cứ": r.get("can_cu", ""),
                        "Đã nộp (triệu)": r.get("so_tien_da_nop_trieu"), "Kiểm điểm": r.get("ket_qua_kiem_diem", ""),
                        "Tin cậy": r["do_tin_cay"]} for r in p["ket_qua"]])
    if df.empty:
        st.write("Không có kiến nghị nào được đối chiếu.")
    else:
        ed = st.data_editor(df, hide_index=True, use_container_width=True, key=f"ev{d['id']}",
                            disabled=["ID", "KN", "Đơn vị", "Nội dung kiến nghị", "Tin cậy"],
                            column_config={"Đánh giá": st.column_config.SelectboxColumn(options=list(DG_REV)),
                                           "Nội dung kiến nghị": st.column_config.TextColumn(width="large")})
        c = st.columns(3)
        if c[0].button("✅ Duyệt & ghi vào biểu", key=f"okev{d['id']}", type="primary"):
            items = [{"kien_nghi_id": int(r["ID"]), "danh_gia": DG_REV[r["Đánh giá"]], "da_lam": r["Đã làm"] or "",
                      "chua_lam": r["Chưa làm"] or "", "can_cu": r["Căn cứ"] or "",
                      "so_tien_da_nop_trieu": None if pd.isna(r["Đã nộp (triệu)"]) else float(r["Đã nộp (triệu)"]),
                      "ket_qua_kiem_diem": r["Kiểm điểm"] or ""} for r in ed.to_dict("records") if r["Ghi"]]
            n = inbox.apply_evaluation(conn, items)
            db.update(conn, "van_ban_den", d["vb_id"], {"trang_thai": "da_ghi"})
            db.mark(conn, d["id"], "da_duyet")
            st.success(f"Đã ghi {n} kiến nghị.")
            st.rerun()
        if c[1].button("🗑️ Từ chối", key=f"noev{d['id']}"):
            db.mark(conn, d["id"], "tu_choi")
            st.rerun()


def page_van_ban_den():
    st.title("📬 Văn bản đến – lọc & đánh giá kết quả thực hiện")
    t1, t2, t3 = st.tabs(["1️⃣ Lấy văn bản", "2️⃣ Phân tích bằng AI", "3️⃣ Duyệt đề xuất"])
    with t1:
        st.markdown("**Từ Cổng chính quyền điện tử**")
        c = st.columns(3)
        ngay = c[0].number_input("Quét văn bản đến trong … ngày", 1, 90, 7)
        if c[1].button("🌐 Quét cổng", type="primary"):
            try:
                from ttkn import portal
                with st.spinner("Đang quét cổng…"):
                    r = portal.fetch_inbox(conn, portal.load_portal(), DATA, cfg["loc_van_ban"]["tu_khoa"], int(ngay))
                if r["can_dang_nhap"]:
                    st.error("Phiên đăng nhập đã hết. Chạy lệnh `python -m ttkn cong-dang-nhap` rồi quét lại.")
                else:
                    st.success(f"Duyệt {r['duyet']} văn bản, tải {r['tai']}, mới {len(r['moi'])}, bỏ qua {r['bo_qua']} (không liên quan).")
            except Exception as e:
                st.error(f"Không quét được cổng: {e}")
        st.caption("Lần đầu: `python -m ttkn cong-dang-nhap` (tự đăng nhập, bạn chỉ nhập OTP/CAPTCHA nếu có).")
        st.markdown("**Hoặc tải thủ công** (báo cáo + tài liệu kiểm chứng đã tải từ cổng)")
        files = st.file_uploader("Mỗi lần tải = 1 văn bản; tệp đầu là báo cáo chính, các tệp sau là tài liệu kiểm chứng",
                                 accept_multiple_files=True, type=["pdf", "docx", "png", "jpg", "jpeg"])
        m = st.columns(2)
        dv = m[0].text_input("Đơn vị gửi (nếu biết)")
        ty = m[1].text_input("Trích yếu (nếu biết)")
        if files and st.button("Thêm vào danh sách văn bản đến"):
            ps = [inbox.save_upload(DATA, f.name, f.getvalue()) for f in files]
            i = inbox.register(conn, ps[0], ps[1:], don_vi_gui=dv, trich_yeu=ty, ngay_den=date.today())
            st.success("Đã thêm." if i else "Văn bản này đã có (trùng nội dung).")
        folder = st.text_input("Hoặc nhập thư mục đã tải sẵn (mỗi thư mục con = 1 văn bản)")
        if folder and st.button("Nhập thư mục") and Path(folder).is_dir():
            st.success(f"Đã thêm {len(inbox.import_folder(conn, folder))} văn bản.")
    with t2:
        rows = db.rows(conn, "SELECT * FROM van_ban_den WHERE trang_thai='moi' ORDER BY id DESC")
        st.write(f"**{len(rows)}** văn bản chưa phân tích.")
        if rows:
            st.dataframe(pd.DataFrame(rows)[["id", "ten", "don_vi_gui", "trich_yeu", "ngay_den", "nguon"]], hide_index=True,
                         use_container_width=True)
        if rows and st.button("🤖 Phân loại + đánh giá tất cả", type="primary"):
            llm = get_llm()
            bar = st.progress(0.0)
            for i, r in enumerate(rows):
                try:
                    out = inbox.process(conn, llm, r["id"], cfg)
                    st.write(f"{r['ten']}: **{out['loai']}** {out['ma_kl']}")
                except Exception as e:
                    st.error(f"{r['ten']}: {e}")
                bar.progress((i + 1) / len(rows))
        other = db.rows(conn, "SELECT id, ten, phan_loai, ma_kl, ghi_chu FROM van_ban_den WHERE trang_thai IN ('bo_qua')")
        if other:
            with st.expander(f"Văn bản không liên quan ({len(other)})"):
                st.dataframe(pd.DataFrame(other), hide_index=True)
    with t3:
        ds = db.pending(conn, "ket_qua") + db.pending(conn, "chi_dao")
        if not ds:
            st.success("Không có đề xuất nào chờ duyệt.")
        for d in ds:
            with st.expander(f"#{d['id']} · {d['loai']} · KL {d['ma_kl']}", expanded=True):
                if d["loai"] == "ket_qua":
                    _review_ket_qua(d)
                else:
                    p = d["payload"]
                    st.write(f"Văn bản chỉ đạo UBND số **{p.get('so_vb')}** ngày {p.get('ngay_vb')} – {p.get('trich_yeu')}")
                    p["han_hoan_thanh"] = st.text_input("Hạn hoàn thành (YYYY-MM-DD)", p.get("han_hoan_thanh") or "", key=f"hh{d['id']}")
                    p["han_bao_cao"] = st.text_input("Hạn báo cáo (YYYY-MM-DD)", p.get("han_bao_cao") or "", key=f"hb{d['id']}")
                    if st.button("✅ Duyệt & ghi", key=f"okcd{d['id']}", type="primary"):
                        inbox.apply_chi_dao(conn, p)
                        db.mark(conn, d["id"], "da_duyet")
                        st.rerun()
                    if st.button("🗑️ Từ chối", key=f"nocd{d['id']}"):
                        db.mark(conn, d["id"], "tu_choi")
                        st.rerun()


def page_don_doc():
    st.title("✉️ Soạn văn bản đôn đốc")
    g = alerts.canh_bao_don_doc(conn, bao_truoc=cfg["dondoc"]["bao_truoc_ngay"])
    if not g:
        st.success("Không có đơn vị nào cần đôn đốc.")
        return
    only = st.checkbox("Chỉ đơn vị đã quá hạn", True)
    g = [x for x in g if x["muc"] == "qua_han"] if only else g
    labels = {f"{MUC[x['muc']]} · KL {x['ma_kl']} · {x['don_vi']} · {len(x['kn'])} KN": x for x in g}
    pick = st.multiselect("Chọn đơn vị cần soạn công văn", list(labels), default=list(labels)[:5])
    n = st.number_input("Yêu cầu báo cáo trong (ngày)", 1, 60, cfg["dondoc"]["so_ngay_yeu_cau"])
    if st.button("📝 Soạn công văn", type="primary"):
        st.session_state["dd"] = []
        for k in pick:
            x = labels[k]
            f = drafting.soan_don_doc(conn, cfg, x["kl_id"], x["don_vi"], DATA / "soan_thao", so_ngay=int(n))
            st.session_state["dd"].append((x, f))
    for x, f in st.session_state.get("dd", []):
        c = st.columns([3, 1, 1, 1, 1])
        c[0].write(f"**{x['don_vi']}** (KL {x['ma_kl']})")
        with c[1]:
            dl(f, "⬇️ Tải", key=f"dl{f.name}")
        so = c[2].text_input("Số CV đã ban hành", key=f"so{f.name}")
        ng = c[3].date_input("Ngày", value=date.today(), key=f"ng{f.name}")
        if c[4].button("Ghi nhận đã ban hành", key=f"gn{f.name}") and so:
            drafting.ghi_nhan_don_doc(conn, x["kl_id"], x["don_vi"], so, ng, file=str(f))
            st.success("Đã ghi nhận.")
    st.caption("Công văn là bản nháp theo văn phong chung: hãy rà soát và đối chiếu mẫu của cơ quan trước khi ký.")


def page_bao_cao():
    st.title("📑 Báo cáo UBND kết quả thực hiện kết luận")
    for r in alerts.den_han_bao_cao(conn, cfg=cfg):
        st.warning(f"KL {r['ma_kl']} – hạn báo cáo {vn_date(r['han_bao_cao'])} (còn {r['con_ngay']} ngày), {r['xong']}/{r['tong_kn']} KN xong.")
    opts = kl_options()
    if not opts:
        return
    kl_id = opts[st.selectbox("Chọn kết luận", list(opts))]
    s = drafting.so_lieu_kl(conn, kl_id)
    c = st.columns(4)
    c[0].metric("Tổng KN", s["tong"]); c[1].metric("Đã xong", s["xong"])
    c[2].metric("Đang thực hiện", s["dang"]); c[3].metric("Chưa thực hiện", s["chua"])
    if st.button("📝 Soạn báo cáo", type="primary"):
        try:
            f, _ = drafting.soan_bao_cao_kl(conn, cfg, kl_id, DATA / "soan_thao")
            st.session_state["bc"] = f
        except ValueError as e:
            st.error(f"Số liệu không khớp: {e}")
    if st.session_state.get("bc"):
        dl(st.session_state["bc"], key="dlbc")
    st.divider()
    c = st.columns(2)
    nb = c[0].date_input("Ngày đã báo cáo UBND", value=date.today())
    if c[0].button("Ghi nhận đã báo cáo UBND"):
        db.update(conn, "ket_luan", kl_id, {"da_bao_cao_ubnd": nb.isoformat()}); st.success("Đã ghi.")
    if c[1].button("🏁 Kết thúc theo dõi KL này", disabled=s["xong"] != s["tong"]):
        inbox.ket_thuc_theo_doi(conn, kl_id); st.success("Đã kết thúc theo dõi.")
    if s["xong"] != s["tong"]:
        c[1].caption("Chỉ kết thúc được khi mọi kiến nghị đã hoàn thành.")


def page_bieu():
    st.title("📊 Biểu theo dõi chung")
    opts = {"(Tất cả)": None, **kl_options()}
    sel = opts[st.selectbox("Kết luận", list(opts))]
    q = "SELECT k.*, l.ma_kl FROM kien_nghi k JOIN ket_luan l ON l.id=k.kl_id"
    rows = db.rows(conn, q + (" WHERE kl_id=?" if sel else "") + " ORDER BY l.ngay_ban_hanh, k.stt", (sel,) if sel else ())
    if rows:
        df = pd.DataFrame(rows)
        df["tinh_trang"] = df["tinh_trang"].map(TT)
        show = ["id", "ma_kl", "stt", "don_vi", "loai", "noi_dung", "han", "tinh_trang", "da_lam", "chua_lam", "can_cu",
                "ly_do_chua_dut_diem"]
        ed = st.data_editor(df[show], hide_index=True, use_container_width=True, disabled=["id", "ma_kl", "stt", "don_vi", "loai", "noi_dung"],
                            column_config={"tinh_trang": st.column_config.SelectboxColumn(options=list(TT.values()))})
        if st.button("💾 Lưu chỉnh sửa"):
            rev = {v: k for k, v in TT.items()}
            for r in ed.to_dict("records"):
                db.update(conn, "kien_nghi", int(r["id"]), {"han": iso(r["han"]), "tinh_trang": rev[r["tinh_trang"]], "da_lam": r["da_lam"] or "",
                                                          "chua_lam": r["chua_lam"] or "", "can_cu": r["can_cu"] or "",
                                                          "ly_do_chua_dut_diem": r["ly_do_chua_dut_diem"] or "", "ngay_cap_nhat": date.today().isoformat()})
            st.success("Đã lưu.")
    out = DATA / "bieu_theo_doi.xlsx"
    if st.button("📤 Xuất Excel"):
        excel_io.export_workbook(conn, out)
    if out.exists():
        st.download_button("⬇️ Tải bieu_theo_doi.xlsx", out.read_bytes(), file_name=out.name)
    st.divider()
    st.subheader("Nạp dữ liệu có sẵn")
    x = st.file_uploader("Biểu .xlsx (định dạng do công cụ xuất)", type=["xlsx"], key="imp")
    if x and st.button("Nạp biểu"):
        p = DATA / "nhap" / x.name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(x.getvalue())
        st.json(excel_io.import_workbook(conn, p))
    dvx = st.file_uploader("Danh mục đơn vị .xlsx (cột TenChuan, Alias, LoaiDonVi)", type=["xlsx"], key="dv")
    if dvx and st.button("Nạp danh mục đơn vị"):
        p = DATA / "nhap" / dvx.name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(dvx.getvalue())
        st.success(f"Đã thêm {excel_io.import_don_vi(conn, p)} đơn vị.")
    st.caption(f"Danh mục hiện có {db.one(conn, 'SELECT COUNT(*) c FROM don_vi')['c']} đơn vị.")


PAGES = {"Tổng quan & cảnh báo": page_tong_quan, "Nhập kết luận mới": page_nhap_kl, "Văn bản chỉ đạo UBND": page_chi_dao,
         "Văn bản đến": page_van_ban_den, "Soạn đôn đốc": page_don_doc, "Báo cáo UBND": page_bao_cao, "Biểu theo dõi": page_bieu}
with st.sidebar:
    st.header("Thanh tra – Theo dõi sau thanh tra")
    page = st.radio("Chức năng", list(PAGES), label_visibility="collapsed")
    n = len(db.pending(conn))
    st.caption(f"Đề xuất chờ duyệt: **{n}**")
PAGES[page]()
