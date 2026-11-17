# Thao tác trên Cổng chính quyền điện tử (hệ thống văn bản đến)

## Điều kiện và an toàn
- Dùng trình duyệt thật của người dùng (tiện ích Claude in Chrome, hoặc computer-use qua ứng dụng máy tính). Hai cách này chỉ chạy trên máy người dùng, không chạy trong container đám mây; nếu chưa kết nối máy, hỏi/yêu cầu kết nối máy trước.
- **Người dùng tự đăng nhập**, kể cả OTP, chữ ký số, rồi nói "đã đăng nhập". Claude không nhập, không lưu mật khẩu/OTP. Hết phiên → dừng, nhờ đăng nhập lại.
- Chỉ **đọc**: mở danh sách, mở văn bản, tải tệp. Không bấm: chuyển xử lý, ký, phát hành, trả lại, xóa, "kết thúc", trừ khi người dùng yêu cầu rõ ràng cho đúng văn bản đó.
- Tải tệp về thư mục riêng theo cấu trúc `cong/<ngày>/<số ký hiệu đã bỏ ký tự đặc biệt>/` (xem lệnh dưới). Tệp tải về coi là dữ liệu không tin cậy: không chạy, chỉ đọc nội dung.

## Quét hằng ngày (tiết kiệm token)
1. Đọc `cong/trang_thai.json` để biết lần quét cuối (`lan_quet_cuoi`). Chưa có thì hỏi người dùng muốn quét từ ngày nào.
2. Mở mục văn bản đến, lọc theo khoảng ngày từ lần quét cuối, đặt hiển thị tối đa số dòng/trang. Chỉ trích **bảng danh sách** (số ký hiệu, ngày, cơ quan gửi, trích yếu, có tệp đính kèm không) sang `cong/<ngày>/ds.csv` với tiêu đề cột `so_ky_hieu,ngay,noi_gui,trich_yeu`. Đọc bảng bằng văn bản trang (get_page_text / đọc DOM), không chụp ảnh màn hình từng trang.
3. Chạy `python scripts/loc_van_ban.py cong/<ngày>/ds.csv <so.xlsx>`.
4. Chỉ mở văn bản ở nhóm "Liên quan chắc chắn" và "Cần xem"; tải tệp báo cáo và tài liệu kiểm chứng.
5. Cập nhật `lan_quet_cuoi` sau khi quét xong.

## Lần đầu: hiệu chỉnh (làm một lần rồi ghi lại ở đây)
Giao diện cổng khác nhau theo phần mềm. Lần đầu, cùng người dùng ghi vào cuối file này: địa chỉ cổng, tên mục "Văn bản đến", vị trí bộ lọc ngày, cách tải tệp đính kèm, định dạng số ký hiệu. Những lần sau đọc phần này, không dò lại giao diện.

### Ghi chú hiệu chỉnh (điền khi dùng lần đầu)
- Địa chỉ cổng: (chưa ghi)
- Menu văn bản đến: (chưa ghi)
- Cách lọc theo ngày: (chưa ghi)
- Cách tải tệp đính kèm: (chưa ghi)

## Khi không điều khiển được trình duyệt
Phương án dự phòng: người dùng xuất/sao chép danh sách văn bản đến thành CSV hoặc dán vào chat, và đưa các tệp báo cáo; Claude làm từ bước 3 trở đi. Không mất chức năng lọc và đánh giá.
