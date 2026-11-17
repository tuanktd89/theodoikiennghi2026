"""Kiểm thử toàn quy trình bằng LLM giả: nhập KL → chỉ đạo → báo cáo đơn vị → đôn đốc → báo cáo UBND."""
from datetime import date

import docx
import pytest

from ttkn import alerts, db, drafting, excel_io, extract, inbox
from ttkn.config import load_config
from ttkn.llm import FakeLLM

CFG = load_config("/nonexistent.yaml")

KL_JSON = {
    "so_ky_hieu": "38/KL-TTr", "ngay_ban_hanh": "2026-06-10", "trich_yeu": "việc quản lý, sử dụng đất tại Công ty A",
    "qd_thanh_tra": "Quyết định số 12/QĐ-TTr ngày 01/3/2026", "don_vi_duoc_thanh_tra": "Công ty A",
    "han_thuc_hien": "2026-09-30", "han_text": "trong quý III/2026",
    "kien_nghi": [
        {"stt": 1, "noi_dung": "Nộp ngân sách số tiền 500 triệu đồng.", "don_vi": "UBND phường Cao Xanh",
         "loai": "Kinh tế", "so_tien_trieu": 500, "trang": "12"},
        {"stt": 2, "noi_dung": "Rút kinh nghiệm, chấn chỉnh công tác quản lý đất.", "don_vi": "Công ty A", "loai": "QLNN"},
        {"stt": 3, "noi_dung": "Kiểm điểm tập thể, cá nhân có liên quan.", "don_vi": "Công ty A", "loai": "Trách nhiệm"},
        {"stt": 4, "noi_dung": "Rút kinh nghiệm, chấn chỉnh công tác quản lý đất.", "don_vi": "Công ty A", "loai": "QLNN"},
    ],
}


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.insert(c, "don_vi", {"ten_chuan": "Ủy ban nhân dân phường Cao Xanh", "alias": "UBND phường Cao Xanh"})
    db.insert(c, "don_vi", {"ten_chuan": "Công ty A"})
    return c


@pytest.fixture
def kl(conn, tmp_path):
    f = tmp_path / "kl.docx"
    d = docx.Document()
    d.add_paragraph("KẾT LUẬN THANH TRA số 38/KL-TTr")
    d.save(f)
    data = extract.extract_kl(FakeLLM([dict(KL_JSON)]), f)
    return conn, data


def test_extract_validate_commit(kl):
    conn, data = kl
    w = extract.validate_kl(conn, data)
    assert any("trùng nội dung" in x for x in w)           # KN4 trùng KN2
    assert not any("chưa có trong danh mục" in x for x in w)  # alias được nhận diện
    kl_id = extract.commit_kl(conn, data, "TTV")
    kns = db.rows(conn, "SELECT * FROM kien_nghi WHERE kl_id=? ORDER BY stt", (kl_id,))
    assert len(kns) == 4 and kns[0]["don_vi"] == "Ủy ban nhân dân phường Cao Xanh"
    assert db.one(conn, "SELECT ma_kl FROM ket_luan")["ma_kl"] == "38.2026"
    with pytest.raises(ValueError):
        extract.commit_kl(conn, data)   # chống trùng mã


def _setup_with_chi_dao(conn, data):
    kl_id = extract.commit_kl(conn, data)
    inbox.apply_chi_dao(conn, {"ma_kl": "38.2026", "so_vb": "100/UBND-VP", "ngay_vb": "2026-07-01",
                               "trich_yeu": "thực hiện KL 38", "han_hoan_thanh": "2026-08-31"})
    return kl_id


def test_alerts_use_ubnd_deadline(kl):
    conn, data = kl
    _setup_with_chi_dao(conn, data)
    g = alerts.canh_bao_don_doc(conn, today=date(2026, 9, 10))
    assert {x["don_vi"] for x in g} == {"Ủy ban nhân dân phường Cao Xanh", "Công ty A"}
    assert all(x["muc"] == "qua_han" and x["qua_han_ngay"] == 10 for x in g)   # hạn 31/8 theo chỉ đạo UBND
    assert alerts.canh_bao_don_doc(conn, today=date(2026, 7, 1)) == []
    br = alerts.den_han_bao_cao(conn, today=date(2026, 8, 25), cfg=CFG)
    assert br and br[0]["con_ngay"] == 6


def test_inbox_classify_evaluate_apply(kl, tmp_path):
    conn, data = kl
    kl_id = _setup_with_chi_dao(conn, data)
    rep = tmp_path / "bc.docx"
    d = docx.Document(); d.add_paragraph("Báo cáo kết quả thực hiện KL 38"); d.save(rep)
    vid = inbox.register(conn, rep, [], don_vi_gui="Công ty A", trich_yeu="Báo cáo kết quả thực hiện Kết luận 38/KL-TTr")
    assert inbox.register(conn, rep) is None   # trùng nội dung
    kn_ids = [r["id"] for r in db.rows(conn, "SELECT id FROM kien_nghi WHERE don_vi='Công ty A' ORDER BY stt")]
    llm = FakeLLM([
        {"loai": "bao_cao_ket_qua", "ma_kl": ["38.2026", "99.2026"], "ly_do": "khớp số KL"},
        {"ket_qua": [
            {"kien_nghi_id": kn_ids[0], "danh_gia": "dam_bao", "da_lam": "Đã ban hành VB 5/CV", "chua_lam": "",
             "can_cu": "VB 5/CV", "do_tin_cay": "cao"},
            {"kien_nghi_id": kn_ids[1], "danh_gia": "dam_bao", "da_lam": "Tự khẳng định", "chua_lam": "",
             "do_tin_cay": "thap"},
            {"kien_nghi_id": 9999, "danh_gia": "dam_bao", "da_lam": "x", "chua_lam": "", "do_tin_cay": "cao"},
        ]},
    ])
    out = inbox.process(conn, llm, vid, CFG)
    assert out["ma_kl"] == ["38.2026"]            # mã không có trong sổ bị loại
    # Chưa duyệt thì sổ chưa đổi
    assert db.one(conn, "SELECT COUNT(*) c FROM kien_nghi WHERE tinh_trang<>'chua'")["c"] == 0
    p = db.pending(conn, "ket_qua")[0]["payload"]
    assert len(p["ket_qua"]) == 2                 # id lạ bị loại
    assert p["ket_qua"][1]["danh_gia"] == "chua_dam_bao"   # tin cậy thấp → hạ mức
    assert inbox.apply_evaluation(conn, p["ket_qua"], today=date(2026, 9, 1)) == 2
    st = {r["id"]: r["tinh_trang"] for r in db.rows(conn, "SELECT id, tinh_trang FROM kien_nghi")}
    assert st[kn_ids[0]] == "xong" and st[kn_ids[1]] == "dang"


def test_drafts_and_counts(kl, tmp_path):
    conn, data = kl
    kl_id = _setup_with_chi_dao(conn, data)
    kn = db.rows(conn, "SELECT id FROM kien_nghi ORDER BY stt")
    db.update(conn, "kien_nghi", kn[0]["id"], {"tinh_trang": "xong", "da_lam": "Đã nộp 500 triệu đồng theo UNT 01",
                                              "so_tien_da_nop_trieu": 500})
    f = drafting.soan_don_doc(conn, CFG, kl_id, "Công ty A", tmp_path, today=date(2026, 9, 10))
    text = "\n".join(p.text for p in docx.Document(f).paragraphs)
    assert "Kết luận thanh tra số 38/KL-TTr" in text and "100/UBND-VP" in text
    assert "quá hạn 10 ngày" in text and "Kiểm điểm tập thể" in text
    assert "500 triệu" not in text        # kiến nghị đã xong của đơn vị khác không lọt vào
    with pytest.raises(ValueError):
        drafting.soan_don_doc(conn, CFG, kl_id, "Ủy ban nhân dân phường Cao Xanh", tmp_path)  # đã xong → không đôn đốc
    f2, s = drafting.soan_bao_cao_kl(conn, CFG, kl_id, tmp_path, today=date(2026, 9, 12))
    assert (s["tong"], s["xong"], s["dang"], s["chua"]) == (4, 1, 0, 3)
    t = "\n".join(p.text for p in docx.Document(f2).paragraphs)
    assert "04 kiến nghị" in t and "đã thực hiện xong 01" in t and "Đã nộp 500 triệu đồng theo UNT 01" in t
    assert "chưa có văn bản báo cáo kết quả thực hiện" in t


def test_excel_roundtrip(kl, tmp_path):
    conn, data = kl
    _setup_with_chi_dao(conn, data)
    x = excel_io.export_workbook(conn, tmp_path / "b.xlsx", today=date(2026, 9, 10))
    conn2 = db.connect(":memory:")
    r = excel_io.import_workbook(conn2, x)
    assert r["kl"] == 1 and r["kn"] == 4
    assert db.one(conn2, "SELECT han_hoan_thanh h FROM van_ban_chi_dao")["h"] == "2026-08-31"
    assert excel_io.import_workbook(conn2, x)["kl"] == 0   # không ghi đè/nhân đôi


def test_db_usable_across_threads(tmp_path):
    """Streamlit dùng kết nối cache ở nhiều luồng khác nhau."""
    import threading
    c = db.connect(tmp_path / "t.sqlite")
    err = []
    t = threading.Thread(target=lambda: err.append(db.pending(c)))
    t.start(); t.join()
    assert err == [[]]


def test_pdf_scan_nang_duoc_nen_thanh_anh(tmp_path):
    import os
    from PIL import Image
    from ttkn.docs import MAX_BYTES, blocks_for
    imgs = [Image.frombytes("RGB", (1650, 2340), os.urandom(1650 * 2340 * 3)) for _ in range(6)]
    f = tmp_path / "scan.pdf"
    imgs[0].save(f, "PDF", save_all=True, append_images=imgs[1:], resolution=200)
    assert f.stat().st_size > 8 * 1024 * 1024
    blocks, skipped = blocks_for([f])
    assert not skipped and {b["type"] for b in blocks} == {"text", "image"}
    assert sum(len(b["source"]["data"]) for b in blocks if b["type"] == "image") < MAX_BYTES


def test_claude_llm_khong_ep_tool_choice_va_thu_lai():
    """Mô hình không hỗ trợ tool_choice ép buộc: không được gửi tham số này; thử lại nếu chưa gọi tool."""
    from types import SimpleNamespace as NS
    from ttkn.llm import ClaudeLLM

    sent = []
    replies = [NS(content=[NS(type="text", name=None, model_dump=lambda **k: {"type": "text", "text": "xin chào"})],
                  stop_reason="end_turn"),
               NS(content=[NS(type="tool_use", name="ghi_ket_qua", input={"a": 1})], stop_reason="tool_use")]

    class Stream:
        def __init__(self, r): self.r = r
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get_final_message(self): return self.r

    class Client:
        class messages:
            @staticmethod
            def stream(**kw):
                sent.append(kw)
                return Stream(replies[len(sent) - 1])

    llm = ClaudeLLM.__new__(ClaudeLLM)
    llm.client, llm.model, llm.max_tokens = Client, "m", 100
    assert llm.structured("s", [{"type": "text", "text": "x"}], {"type": "object"}) == {"a": 1}
    assert len(sent) == 2 and all("tool_choice" not in k for k in sent)


def test_nhap_tu_claude_web(conn):
    import json
    from ttkn import prompts
    assert "Quy ước đếm kiến nghị" in prompts.manual_prompt_kl()
    js = json.dumps(KL_JSON, ensure_ascii=False)
    # kèm lời dẫn, hàng rào mã và dấu phẩy thừa
    raw = f"Đây là kết quả:\n```json\n{js[:-1]},}}\n```\nHy vọng hữu ích."
    d = extract.parse_manual_json(raw)
    assert len(d["kien_nghi"]) == 4
    assert extract.parse_manual_json(js.replace('"Kinh tế"', '"abc"'))["kien_nghi"][0]["loai"] == "QLNN"
    with pytest.raises(ValueError, match="cắt dở"):
        extract.parse_manual_json(js[:200])
    with pytest.raises(ValueError):
        extract.parse_manual_json("không có json")
    extract.stage_kl(conn, d)
    assert len(db.pending(conn, "kl_moi")) == 1
