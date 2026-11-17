---
name: "theo-doi-xu-ly-sau-thanh-tra"
description: "Trợ lý theo dõi, đôn đốc, xử lý sau thanh tra (Thanh tra thành phố Quảng Ninh): nhập kết luận thanh tra (KLTT) mới vào sổ 'Input - Theo dõi KLTT'; soạn văn bản đôn đốc theo chỉ đạo của UBND; quét Cổng chính quyền điện tử để lọc văn bản đến liên quan KL và đánh giá báo cáo của đơn vị; cảnh báo KL/kiến nghị quá hạn; soạn báo cáo kết quả thực hiện KL gửi UBND; tổng hợp kỳ; rà lỗi dữ liệu. Dùng skill này mỗi khi người dùng nhắc tới kết luận thanh tra, kiến nghị, đơn vị chưa thực hiện, quá hạn, đôn đốc, văn bản chỉ đạo của UBND, báo cáo kết quả thực hiện KL, sổ theo dõi KLTT, hoặc 'kiểm tra cổng/văn bản đến' – kể cả khi không nói rõ tên skill."
---

# Theo dõi, đôn đốc, xử lý sau thanh tra

Trả lời bằng tiếng Việt. Người dùng là thanh tra viên theo dõi khoảng 100+ KL, 1.500+ kiến nghị, 100 đơn vị. Mục tiêu: **máy làm phần đếm/lọc/điền, người duyệt phần đánh giá và ký**. Vì vậy:

- **Tiết kiệm token**: không nạp cả sổ vào ngữ cảnh. Dùng `scripts/so.py` (chạy bằng code) để lấy đúng lát cắt cần (một KL, một đơn vị, danh sách quá hạn), chỉ đọc nội dung chi tiết của những mục thực sự phải đánh giá.
- **Không ghi gì vào sổ/cổng khi chưa được duyệt**. Luôn trình "bản nháp thay đổi" (bảng ngắn: ô nào, giá trị cũ → mới, căn cứ) rồi chờ người dùng đồng ý. Mặc định xuất file .xlsx "dán vào"; chỉ ghi thẳng vào Google Sheets khi người dùng nói rõ.
- **Số liệu phải đếm bằng code**, đối chiếu CN/CO/CP/CQ/CR ở Bieu tong hop, lệch thì báo.
- **Nội dung đánh giá là đề xuất**: kết luận "đã đảm bảo/chưa đảm bảo" luôn kèm căn cứ (đoạn nào trong báo cáo/tài liệu kiểm chứng) để người dùng kiểm tra nhanh.

Cấu trúc sổ, quy ước đếm kiến nghị, cột nào là gì: đọc `references/quy-trinh-goc.md` (chỉ khi cần). Thao tác trên Cổng chính quyền điện tử: `references/cong-chinh-quyen.md`. Mẫu văn bản: `references/mau-van-ban.md`.

## Chọn quy trình theo yêu cầu

| Người dùng nói | Quy trình |
|---|---|
| Đưa file KL mới (PDF/ảnh) | A. Nhập KL |
| Đưa văn bản chỉ đạo của UBND | B. Soạn văn bản đôn đốc triển khai |
| "Kiểm tra cổng", "có báo cáo mới chưa" | C. Quét cổng + đánh giá báo cáo |
| "Cảnh báo", "quá hạn", "đầu ngày" | D. Cảnh báo quá hạn |
| "Báo cáo UBND kết quả KL số…" | E. Báo cáo kết quả thực hiện |
| Tổng hợp kỳ / rà lỗi | F. Tổng hợp & rà soát |

Bắt đầu mỗi phiên làm việc bằng quy trình D (30 giây, một lệnh) rồi mới sang việc người dùng yêu cầu: người dùng sẽ thấy ngay việc gấp.

## A. Nhập KL mới vào sổ
1. Đọc KL: `pdftotext` chỉ để định vị trang "KIẾN NGHỊ", "TỔ CHỨC THỰC HIỆN"; bản scan thì render các trang đó (`pdftoppm -r 80 -png`) và đọc bằng hình ảnh, cộng trang 1 (số, ngày, trích yếu, căn cứ QĐ thanh tra).
2. Tách kiến nghị theo quy ước đếm trong `quy-trinh-goc.md` (1 mục × 1 đơn vị = 1 dòng; chép nguyên văn).
3. Chuẩn hóa tên đơn vị theo sheet Danh muc don vi: `python scripts/so.py don-vi <so.xlsx> "<tên trong KL>"`. Tên không có trong danh mục → hỏi người dùng, không tự thêm.
4. Xuất 3 sheet .xlsx "dán vào" (Kien nghi, Bieu tong hop, Xu ly trach nhiem) đúng thứ tự cột. Tự kiểm: số dòng theo loại khớp tổng; ghi số trang KL cho từng kiến nghị.
5. Trình người dùng: bảng KL (mã, số ký hiệu, ngày, số kiến nghị theo loại, hạn, đơn vị) → chờ duyệt → mới giao file/ghi sổ.

## B. Soạn văn bản đôn đốc theo chỉ đạo của UBND
Đầu vào: văn bản chỉ đạo của UBND (số, ngày, trích yếu, hạn hoàn thành) + mã KL.
1. Lấy từ sổ danh sách đơn vị và kiến nghị còn tồn của KL: `python scripts/so.py kien-nghi <so.xlsx> --kl 38.2026 --ton`.
2. Soạn công văn của Thanh tra thành phố gửi các đơn vị (hoặc từng đơn vị nếu khác nội dung), theo `references/mau-van-ban.md`: căn cứ chỉ đạo của UBND → đề nghị thực hiện đúng hạn → liệt kê kiến nghị của đơn vị (nguyên văn) → yêu cầu báo cáo kết quả kèm tài liệu kiểm chứng gửi qua Cổng chính quyền điện tử trước ngày …
3. Xuất .docx bằng `python scripts/soan_cong_van.py` (đọc JSON, tạo file theo thể thức hành chính). Không tự điền người ký, số văn bản.
4. Sau khi người dùng phát hành, đề xuất cập nhật BB–BE (văn bản đôn đốc) trong Bieu tong hop.

## C. Quét Cổng chính quyền điện tử, đánh giá báo cáo
Chi tiết thao tác trong `references/cong-chinh-quyen.md`. Nguyên tắc:
- **Người dùng tự đăng nhập** (kể cả OTP/chữ ký số) trong trình duyệt; Claude làm việc trên phiên đã đăng nhập. Không lưu, không yêu cầu, không nhập mật khẩu hay mã OTP. Nếu phiên hết hạn, dừng và nhờ người dùng đăng nhập lại.
- Bước 1, chỉ lấy **danh sách** văn bản đến từ lần quét trước (số ký hiệu, ngày, nơi gửi, trích yếu) – không mở từng văn bản. Lưu vào file CSV.
- Bước 2, lọc bằng code: `python scripts/loc_van_ban.py ds_van_ban.csv <so.xlsx>` → ba nhóm: **Liên quan chắc chắn** (nêu số KL/văn bản chỉ đạo, hoặc đơn vị đang có kiến nghị tồn + từ khóa), **Cần xem** (mơ hồ), **Bỏ qua**. Chỉ mở và tải văn bản ở hai nhóm đầu. Tiết kiệm phần lớn token vì 90% văn bản đến không liên quan.
- Bước 3, với mỗi báo cáo liên quan: gom kiến nghị tồn của đơn vị đó (`so.py kien-nghi --don-vi`), đọc báo cáo và tài liệu kiểm chứng, đối chiếu **từng kiến nghị**:
  - **Đảm bảo**: có căn cứ chứng minh đúng nội dung kiến nghị (ví dụ nộp đủ tiền: có chứng từ nộp NSNN đúng số; kiểm điểm: có biên bản/quyết định xử lý).
  - **Một phần**: ghi rõ đã làm gì, còn thiếu gì (số tiền còn lại, thiếu tài liệu, chưa có quyết định…).
  - **Chưa đảm bảo / chỉ nêu chung chung**: ghi lý do, đề xuất đôn đốc.
  Báo cáo không rõ ràng hoặc tài liệu không đọc được: nói rõ, không suy đoán.
- Bước 4, trình bảng duyệt gọn (mỗi dòng: mã KL – kiến nghị số – đơn vị – đánh giá – căn cứ – ô sẽ nhập) và chờ người dùng sửa/đồng ý. Sau duyệt mới xuất dữ liệu cập nhật cho các cột kết quả (Q–T, V–X, Y–AB trong Kien nghi; xử lý kinh tế/trách nhiệm nếu có) và soạn công văn đôn đốc cho phần chưa đảm bảo (quy trình B). Việc bấm "kết thúc" trên cổng do người dùng thực hiện, hoặc chỉ làm khi họ yêu cầu rõ từng lần.

## D. Cảnh báo quá hạn
`python scripts/so.py canh-bao <so.xlsx> [--ngay 2026-11-17] [--sap-han 15]` in ra bảng gọn gồm: KL quá hạn còn kiến nghị chưa xong; KL sắp đến hạn trong N ngày; KL đã quá hạn báo cáo UBND (cột BA) chưa lập báo cáo; đơn vị chậm nhiều KL nhất. Hạn lấy AX (hạn theo chỉ đạo UBND), nếu trống lấy AZ.
Sau bảng, chủ động đề xuất: "Soạn đôn đốc cho N đơn vị?" và "Soạn báo cáo UBND cho KL …?". Chỉ soạn khi người dùng đồng ý, nhưng luôn chủ động nhắc.

## E. Báo cáo UBND về kết quả thực hiện KL
Khi đến hạn báo cáo (AX/AZ/BA), hoặc người dùng yêu cầu: lấy số liệu bằng `so.py thong-ke --kl <mã>` (đếm theo loại, đơn vị, đã xong/đang/chưa; đối chiếu CN/CO/CP/CQ/CR), rồi soạn .docx theo mẫu ở Quy trình 2 trong `quy-trinh-goc.md` (tên cơ quan nhận/ban hành đổi theo "Thanh tra thành phố" – "Ủy ban nhân dân thành phố"; mẫu gốc BC 242 viết cấp tỉnh, dùng làm khung cấu trúc, không chép tên cơ quan). Phần đề xuất, kiến nghị là bản nháp. Số liệu lệch sổ → báo ngay, không tự sửa.

## F. Tổng hợp kỳ và rà soát
Quy trình 3 và mục "Rà soát chất lượng" của `quy-trinh-goc.md`; tự động hóa bằng `so.py ra-soat <so.xlsx>` (kiến nghị trùng, tên đơn vị ngoài danh mục, Q/Y không khớp, số dòng lệch CN/CX/DC). Chỉ báo, không tự sửa sổ.

## Bảo mật
KL có tên cá nhân bị kiểm điểm. Không đưa thông tin cá nhân hay nội dung KL vào tìm kiếm web/dịch vụ ngoài. Không lưu mật khẩu, OTP, token đăng nhập trong skill, file cấu hình hay repo.
