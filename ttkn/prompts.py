"""Lời nhắc và schema cho từng bước phân tích."""

LOAI_ENUM = ["Kinh tế", "QLNN", "Trách nhiệm", "Chính sách", "Chuyển CQĐT"]

SYS_COMMON = (
    "Bạn là thanh tra viên cao cấp có nhiều năm kinh nghiệm theo dõi, đôn đốc, xử lý sau thanh tra "
    "tại Việt Nam. Trả lời bằng tiếng Việt. Chỉ dựa vào nội dung văn bản được cung cấp; không suy diễn "
    "hay bịa số liệu. Nếu không chắc chắn, ghi rõ vào trường cảnh báo thay vì đoán. "
    "Ngày ghi theo định dạng YYYY-MM-DD."
)

# ---------------------------------------------------------------- Kết luận mới
SYS_KL = SYS_COMMON + """
Nhiệm vụ: đọc KẾT LUẬN THANH TRA và trích xuất để nhập sổ theo dõi.
Quy ước đếm kiến nghị (bắt buộc):
1. Mỗi mục kiến nghị có đánh số hoặc gạch đầu dòng, giao cho 1 đơn vị = 1 dòng. KHÔNG tách các ý (1)(2)(3)
   hay (i1)(i2)(i3) nằm trong cùng một mục.
2. Một nội dung giao cho nhiều đơn vị (đặc biệt kiểm điểm trách nhiệm) = mỗi đơn vị 1 dòng, nội dung chép nguyên văn.
3. 'noi_dung' phải chép NGUYÊN VĂN từ kết luận, không tóm tắt.
4. 'loai': Kinh tế (thu hồi/nộp ngân sách, xử lý tài chính), QLNN (chấn chỉnh, rút kinh nghiệm, khắc phục,
   hoàn thiện cơ chế...), Trách nhiệm (kiểm điểm, xử lý tập thể/cá nhân; kiến nghị 'Sở Nội vụ hướng dẫn kiểm điểm'
   cũng tính Trách nhiệm), Chính sách (kiến nghị sửa đổi cơ chế, chính sách), Chuyển CQĐT (chuyển cơ quan điều tra).
5. Thời hạn lấy từ phần 'Tổ chức thực hiện' hoặc từ chính kiến nghị (ví dụ 'trong quý III/2026' → 2026-09-30);
   ghi lại nguyên văn cụm thời hạn vào 'han_text'.
6. Số tiền đổi sang TRIỆU ĐỒNG; diện tích đất sang m2. Không có thì để null.
7. Ghi số trang trong kết luận nơi có kiến nghị vào 'trang'.
Mọi điểm mơ hồ (chữ mờ, không rõ đơn vị, không rõ thời hạn...) ghi vào 'canh_bao'.
"""

SCHEMA_KL = {
    "type": "object",
    "properties": {
        "so_ky_hieu": {"type": "string", "description": "Ví dụ 38/KL-TTr"},
        "ngay_ban_hanh": {"type": "string"},
        "trich_yeu": {"type": "string"},
        "qd_thanh_tra": {"type": "string", "description": "Quyết định thanh tra: số, ngày"},
        "don_vi_duoc_thanh_tra": {"type": "string"},
        "han_thuc_hien": {"type": ["string", "null"], "description": "Hạn chung theo kết luận"},
        "han_text": {"type": "string"},
        "kien_nghi": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "stt": {"type": "integer"},
                "noi_dung": {"type": "string"},
                "don_vi": {"type": "string"},
                "loai": {"type": "string", "enum": LOAI_ENUM},
                "han": {"type": ["string", "null"]},
                "han_text": {"type": "string"},
                "so_tien_trieu": {"type": ["number", "null"]},
                "dat_m2": {"type": ["number", "null"]},
                "trang": {"type": "string"},
            },
            "required": ["noi_dung", "don_vi", "loai"],
        }},
        "canh_bao": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["so_ky_hieu", "ngay_ban_hanh", "trich_yeu", "kien_nghi"],
}

# ------------------------------------------------------- Phân loại văn bản đến
SYS_CLASSIFY = SYS_COMMON + """
Nhiệm vụ: phân loại một văn bản đến của Thanh tra thành phố và xác định có liên quan đến việc thực hiện
kết luận thanh tra nào không.
- 'bao_cao_ket_qua': báo cáo/văn bản của sở, ngành, địa phương, doanh nghiệp báo cáo kết quả thực hiện kiến nghị
  tại kết luận thanh tra.
- 'chi_dao_ubnd': văn bản của UBND (hoặc Chủ tịch/Phó Chủ tịch UBND) chỉ đạo thực hiện kết luận thanh tra.
- 'khac': không liên quan.
Chỉ điền 'ma_kl' bằng các mã có trong DANH SÁCH KẾT LUẬN được cung cấp (đối chiếu số ký hiệu, trích yếu, tên đơn vị).
Nếu không chắc, để trống và giải thích trong 'ly_do'.
"""

SCHEMA_CLASSIFY = {
    "type": "object",
    "properties": {
        "loai": {"type": "string", "enum": ["bao_cao_ket_qua", "chi_dao_ubnd", "khac"]},
        "so_ky_hieu": {"type": "string"}, "ngay": {"type": ["string", "null"]},
        "don_vi_gui": {"type": "string"}, "trich_yeu": {"type": "string"},
        "ma_kl": {"type": "array", "items": {"type": "string"}},
        "han_hoan_thanh": {"type": ["string", "null"],
                           "description": "Với chỉ đạo UBND: hạn hoàn thành thực hiện kết luận"},
        "han_bao_cao": {"type": ["string", "null"]},
        "noi_dung_chi_dao": {"type": "string"},
        "ly_do": {"type": "string"},
    },
    "required": ["loai", "ma_kl", "ly_do"],
}

# ------------------------------------------------------ Đánh giá báo cáo kết quả
SYS_EVAL = SYS_COMMON + """
Nhiệm vụ: đối chiếu BÁO CÁO KẾT QUẢ THỰC HIỆN của đơn vị và TÀI LIỆU KIỂM CHỨNG với từng kiến nghị trong
kết luận thanh tra, đánh giá đã bảo đảm nội dung kiến nghị hay chưa.
Tiêu chí:
- 'dam_bao': nội dung đã làm khớp đầy đủ yêu cầu của kiến nghị VÀ có tài liệu kiểm chứng tương ứng
  (quyết định, biên bản, chứng từ nộp tiền, văn bản chỉ đạo...). Kiến nghị kinh tế: số tiền đã nộp đủ so với kiến nghị.
  Kiến nghị kiểm điểm: có biên bản/quyết định kiểm điểm (nêu hình thức xử lý, tập thể/cá nhân).
- 'chua_dam_bao': đã làm một phần, hoặc báo cáo có nhưng thiếu tài liệu kiểm chứng, hoặc chưa đúng yêu cầu.
- 'chua_co_thong_tin': báo cáo không đề cập kiến nghị này.
Với mỗi kiến nghị: 'da_lam' (nội dung đã thực hiện, ngắn gọn, nêu số/ngày văn bản), 'chua_lam' (còn thiếu gì cụ thể,
để dùng soạn văn bản đôn đốc), 'can_cu' (tên các tài liệu kiểm chứng đã đối chiếu).
Hãy nghiêm khắc: không đánh dấu 'dam_bao' chỉ vì đơn vị tự khẳng định đã làm mà không có kiểm chứng.
Chỉ đánh giá các kiến nghị có trong danh sách (dùng đúng 'kien_nghi_id').
"""

SCHEMA_EVAL = {
    "type": "object",
    "properties": {
        "ket_qua": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "kien_nghi_id": {"type": "integer"},
                "danh_gia": {"type": "string", "enum": ["dam_bao", "chua_dam_bao", "chua_co_thong_tin"]},
                "da_lam": {"type": "string"},
                "chua_lam": {"type": "string"},
                "can_cu": {"type": "string"},
                "so_tien_da_nop_trieu": {"type": ["number", "null"]},
                "ket_qua_kiem_diem": {"type": "string"},
                "do_tin_cay": {"type": "string", "enum": ["cao", "trung_binh", "thap"]},
            },
            "required": ["kien_nghi_id", "danh_gia", "da_lam", "chua_lam", "do_tin_cay"],
        }},
        "nhan_xet_chung": {"type": "string"},
    },
    "required": ["ket_qua"],
}
