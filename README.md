# Công cụ theo dõi, đôn đốc, xử lý sau thanh tra

Chạy **trên máy của thanh tra viên**, dữ liệu lưu trong một tệp SQLite (`data/ttkn.sqlite`) và xuất ra Excel khi cần.
Nguyên tắc: **AI chỉ đề xuất – không có gì được ghi vào biểu hoặc ban hành khi bạn chưa bấm Duyệt.**

| Nhu cầu | Chức năng |
|---|---|
| 1. Nhập kết luận mới | *Nhập kết luận mới*: tải PDF/Word (kể cả scan) → AI trích xuất mã KL, số ký hiệu, kiến nghị (nguyên văn), đơn vị, loại, hạn, số tiền → bạn sửa trên bảng → **Duyệt** mới ghi sổ. Tự cảnh báo: trùng mã KL, kiến nghị trùng, đơn vị ngoài danh mục, thiếu hạn. |
| 2. Văn bản đôn đốc theo chỉ đạo UBND | *Văn bản chỉ đạo UBND* (nhập tay hoặc AI nhận từ văn bản đến) → *Soạn đôn đốc*: công văn Word cho **từng đơn vị**, chỉ liệt kê kiến nghị còn tồn (nguyên văn), nêu số/ngày văn bản chỉ đạo, hạn, số ngày quá hạn. |
| 3 & 5. Lọc văn bản đến, đánh giá kết quả | *Văn bản đến*: quét Cổng chính quyền điện tử (hoặc tải tay) → lọc theo từ khóa → AI phân loại, ghép đúng KL → đối chiếu báo cáo + tài liệu kiểm chứng với từng kiến nghị → đề xuất *Đảm bảo / Chưa đảm bảo* kèm "đã làm / chưa làm / căn cứ" → bạn sửa & **Duyệt** mới ghi vào biểu. |
| 4. Cảnh báo quá hạn, tự soạn đôn đốc | *Tổng quan*: danh sách đơn vị quá hạn/sắp đến hạn (hạn theo chỉ đạo UBND > hạn riêng của kiến nghị > hạn trong KL) → *Soạn đôn đốc* hàng loạt. `python -m ttkn canh-bao` để chạy theo lịch. |
| 6. Báo cáo UBND | *Báo cáo UBND*: cảnh báo KL đến hạn báo cáo; sinh báo cáo Word (I. Khái quát – II. Kết quả – III. Vướng mắc – IV. Đề xuất). **Mọi con số đếm từ dữ liệu** và tự kiểm tra tổng khớp. |

## Cài đặt (máy Windows/Mac/Linux, Python 3.10+)
```bash
pip install -r requirements.txt
python -m playwright install chromium     # chỉ cần nếu dùng quét cổng tự động
cp config.example.yaml config.yaml         # chỉnh tên cơ quan
export ANTHROPIC_API_KEY=sk-ant-...        # Windows: setx ANTHROPIC_API_KEY ...
streamlit run ttkn/app.py
```

## Nạp dữ liệu hiện có
- *Biểu theo dõi → Nạp danh mục đơn vị* (cột `TenChuan`, `Alias`, `LoaiDonVi`) để tên đơn vị luôn về tên chuẩn.
- Biểu hiện hành của cơ quan có hàng trăm cột nên **chưa được ánh xạ tự động**: hãy gửi 1 bản mẫu (đã xóa thông tin nhạy cảm) để làm bộ xuất/nhập đúng cột. Hiện công cụ xuất file `bieu_theo_doi.xlsx` (sheet *Bieu tong hop, Kien nghi, Chi dao UBND, Don doc, Xu ly kinh te, Canh bao*) để đối chiếu/dán.

## Cổng chính quyền điện tử
```bash
cp portal.example.yaml portal.yaml            # chỉnh URL + selector theo giao diện cổng của bạn
python -m ttkn cong-kiem-tra                  # lưu ảnh + HTML hộp thư để xác định selector
python -m ttkn cong-dang-nhap                 # mở trình duyệt, đăng nhập (OTP/CAPTCHA nhập tay), lưu phiên
python -m ttkn cong-quet --ngay 7 --xu-ly     # tải văn bản liên quan + đưa vào hàng chờ duyệt
```
- **Không lưu mật khẩu** trong tệp; phiên giữ trong thư mục profile trình duyệt (`data/browser_profile`). Có thể đặt `PORTAL_USER/PORTAL_PASS` để tự điền form.
- Công cụ chỉ **đọc và tải** văn bản đến, không gửi/ký/ban hành gì trên cổng.
- Selector trong `portal.example.yaml` là **ví dụ**; mỗi cổng khác nhau nên cần chỉnh một lần. Bộ quét đã được kiểm thử trên cổng giả cục bộ, chưa thử trên cổng thật.
- Hãy xác nhận với bộ phận CNTT/an toàn thông tin của cơ quan việc dùng tự động hóa trên cổng.

## Bảo mật & dữ liệu
- Nội dung kết luận/báo cáo được gửi tới API Anthropic để phân tích. Kết luận thanh tra có thể thuộc diện hạn chế công khai và chứa tên cá nhân: **cần được lãnh đạo/CNTT cho phép trước khi dùng** (hoặc chỉ dùng cho văn bản đã công khai).
- Không đưa `data/`, `config.yaml`, `portal.yaml`, `.env` lên Git (đã có trong `.gitignore`).

## Giới hạn cần biết
- AI có thể đọc sai bản scan mờ hoặc đánh giá chưa chuẩn → luôn có bước duyệt; đánh giá có độ tin cậy "thấp" tự hạ về *Chưa đảm bảo*.
- Tính ngày làm việc (hạn báo cáo = KL + 45 ngày làm việc) mới bỏ thứ 7, chủ nhật, chưa trừ ngày lễ; hạn ghi trong chỉ đạo UBND luôn được ưu tiên.
- Mẫu công văn/báo cáo là văn phong chung theo thể thức hành chính; cần đối chiếu mẫu của cơ quan (số, ký hiệu, người ký để trống).

## Kiểm thử
```bash
python -m pytest -q tests
```
