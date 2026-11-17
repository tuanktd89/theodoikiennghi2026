
# Theo dõi, đôn đốc, xử lý sau thanh tra

Dùng cho công việc của Phòng Giám sát, thẩm định và xử lý sau thanh tra (Thanh tra Quảng Ninh). Trả lời bằng tiếng Việt.

## Nguồn dữ liệu: sổ "Input - Theo dõi KLTT"

- Google Sheets ID `18gTxbvYbAFGNMEPWWyRhBEN7sjP_qT34QlTvUfTo2fo`. Nếu connector báo không có quyền, dùng bản .xlsx người dùng tải lên.
- Sổ có Apps Script (cảnh báo, sửa định dạng có điều kiện, nhật ký). **Không ghi trực tiếp vào sổ** trừ khi người dùng yêu cầu rõ. Mặc định: xuất file .xlsx "dán vào" có cột đúng thứ tự để người dùng tự dán.
- Đọc .xlsx bằng openpyxl `data_only=True` (cột C, D ở các sheet là công thức mảng, chỉ có giá trị khi đọc data_only).
- Mã KL dạng `38.2026` (cột B). Số ký hiệu dạng `38/KL-TTr ngày 10/6/2026`.

### Các sheet chính
- **Bieu tong hop** (1 dòng/KL). Cột quan trọng: B mã · C số ký hiệu · D ngày ban hành · G người theo dõi · H cảnh báo đôn đốc · J trích yếu · K/L/M QĐ thanh tra · R–S hình thức · T–Y lĩnh vực (x) · AE–AM kiến nghị kinh tế/đất · AP–AT tổng số KN theo loại · AU/AV/AW/AX văn bản chỉ đạo UBND (số, ngày, trích yếu, hạn hoàn thành) · AZ thời hạn thực hiện theo KL · BA hạn báo cáo (KL + 45 ngày làm việc) · BB/BC/BD/BE văn bản đôn đốc cuối · CN tổng KN · CO đã hoàn thành · CP chưa hoàn thành · CQ đang thực hiện · CR chưa thực hiện · CS–DQ chi tiết theo loại · EE "x" = đang theo dõi (hoặc ngày kết thúc theo dõi) · EK–EN báo cáo kết quả theo dõi · EQ–ES kết thúc theo dõi.
- **Kien nghi** (1 dòng/kiến nghị/đơn vị): E nội dung nguyên văn · F tên đơn vị theo KL · G tên đơn vị hiện nay (tên chuẩn) · H/I/J loại đơn vị (Cơ quan nhà nước / Doanh nghiệp / Khác) · K Kinh tế · L QLNN · M Trách nhiệm · N Chính sách · O Chuyển CQĐT · P tồn tại, hạn chế · Q xác nhận hoàn thành (x) · R nội dung đã hoàn thành · S căn cứ · T ngày cập nhật · V nội dung đang thực hiện · W căn cứ · X ngày cập nhật · Y/Z/AA đã xong/đang/chưa (1) · AB phân nhóm kết quả · AC–AI cam kết · AJ/AK lý do chưa dứt điểm · AM–AR lĩnh vực · AS đơn vị đã hoàn thành (kèm ngày).
- **Xu ly kinh te**: G–J số tiền kiến nghị (triệu đồng) · O–AF đã/chưa thực hiện theo từng hình thức.
- **Xu ly trach nhiem**: F nội dung · G đơn vị phải thực hiện · H–O kết quả kiểm điểm, biên bản/quyết định · P–AD hình thức xử lý.
- **Danh muc don vi**: B TenChuan · C alias · D LoaiDonVi. Luôn quy tên đơn vị về TenChuan (ví dụ "UBND phường Cao Xanh" → "Ủy ban nhân dân phường Cao Xanh"; "Thuế tỉnh Quảng Ninh" → cột G là "Thuế thành phố Quảng Ninh"). Tên chưa có trong danh mục: báo cho người dùng, không tự thêm.
- **Theo doi bao cao**: J người đôn đốc · K/L/M báo cáo đơn vị · N tình trạng · P số lần không báo cáo.

## Quy ước đếm kiến nghị (theo sổ hiện hành)
1. Mỗi mục kiến nghị có đánh số hoặc gạch đầu dòng, giao cho 1 đơn vị = **1 dòng**. **Không tách** các ý (1)(2)(3) hay (i1)(i2)(i3) trong cùng mục. Ví dụ: KL 38, mục 5 của Công ty Than Hòn Gai là 1 dòng, gồm cả ý cấp GCN và 02 căn hộ DV1, DV2.
2. Một nội dung giao cho nhiều đơn vị (đặc biệt kiểm điểm trách nhiệm) = **mỗi đơn vị 1 dòng**, cột E chép nguyên văn.
3. Kiến nghị "Sở Nội vụ hướng dẫn kiểm điểm": phần lớn KL 2026 tính là **Trách nhiệm (M)**. KL 18, 33, 35 lại tính QLNN. Theo M, và nhắc người dùng nếu gặp KL tính khác.
4. Cột E chép **nguyên văn** từ KL, không tóm tắt.
5. Lĩnh vực (AM–AR) lấy theo dòng KL ở Bieu tong hop.

## Quy trình 1: Nhập KL mới từ PDF
1. KL thường là bản scan, lớp chữ (pdftotext) bị lỗi font. Dùng pdftotext chỉ để định vị trang có "KIẾN NGHỊ" và "TỔ CHỨC THỰC HIỆN". Sau đó render các trang đó (`pdftoppm -r 80 -png`) và **đọc bằng hình ảnh**. Đọc cả trang 1 để lấy số, ngày, trích yếu, căn cứ (QĐ thanh tra).
2. Tách kiến nghị theo quy ước trên. Lấy thời hạn từ phần Tổ chức thực hiện (ví dụ "trong quý III/2026" → 30/9/2026).
3. Xuất file .xlsx gồm 3 sheet, tiêu đề và thứ tự cột giống hệt sổ:
   - `Kien nghi (dan)`: cột B–O, P (nếu KL nêu rõ), AM–AR.
   - `Bieu tong hop (dan)`: B, C, D, J, K, L, M, R/S, T–Y, AE–AT, AZ.
   - `Xu ly trach nhiem (dan)`: B, C, D, F, G cho mỗi đơn vị phải kiểm điểm.
4. Tự kiểm tra: số dòng theo từng loại khớp với tổng ở sheet Bieu tong hop; mọi tên ở cột G có trong Danh muc don vi. Ghi rõ số trang KL cho từng kiến nghị để người dùng đối chiếu.

## Quy trình 2: Báo cáo kết quả thực hiện một KL
Theo mẫu báo cáo số 242/BC-TTr (báo cáo KL 18, lần 2). Xuất file Word .docx, trình bày theo thể thức văn bản hành chính: Times New Roman 13–14, khổ A4, lề trái 30–35 mm. Bố cục:
- Tiêu đề: "BÁO CÁO Kết quả thực hiện Kết luận số …/KL-TTr ngày … của Chánh Thanh tra tỉnh về …". Kính gửi: Ủy ban nhân dân tỉnh.
- Đoạn mở: "Thực hiện [VB chỉ đạo AU] … Trên cơ sở báo cáo kết quả thực hiện của các sở, ngành, địa phương, đơn vị có liên quan, Thanh tra tỉnh báo cáo kết quả thực hiện như sau:"
- **I. KHÁI QUÁT CHUNG**: QĐ thanh tra, ngày ban hành KL, VB chỉ đạo của UBND tỉnh (nội dung, các mốc hạn), các văn bản đôn đốc (liệt kê ở chú thích chân trang, lấy từ BB/BC).
- **II. KẾT QUẢ THỰC HIỆN**: câu tổng "Tổng số nội dung kiến nghị … là NN kiến nghị (NN kiến nghị về quản lý nhà nước, NN kiến nghị xử lý trách nhiệm, không có kiến nghị xử lý về kinh tế); trong đó đã thực hiện xong NN …, NN kiến nghị đang thực hiện (…)". Tiếp theo là từng đơn vị "- [Đơn vị]: có trách nhiệm thực hiện NN kiến nghị (…), đã thực hiện xong …, đang thực hiện …". Số dùng 2 chữ số (01, 02…). Sau đó đi theo nhóm: 1. Kiến nghị QLNN → 1.1 đã xong / 1.2 đang thực hiện (hạn …), chia theo "- Trách nhiệm của [đơn vị] (NN kiến nghị)"; 2. Kiến nghị xử lý trách nhiệm → 2.1 / 2.2. Mỗi kiến nghị: "(n) Kiến nghị 0n: “[nguyên văn E]” (trách nhiệm của …)" rồi "*Kết quả thực hiện: …" lấy từ R+S hoặc V+W (+AJ). Không có dữ liệu thì ghi "Đến thời điểm báo cáo, [đơn vị] chưa có văn bản báo cáo kết quả thực hiện."
- **III. KHÓ KHĂN, VƯỚNG MẮC**: từ AJ và nội dung đơn vị nêu.
- **IV. ĐỀ XUẤT, KIẾN NGHỊ**: đề xuất theo từng đơn vị còn tồn; mục cuối là Thanh tra tỉnh tiếp tục theo dõi, đôn đốc. Phần đề xuất là bản nháp cho người dùng quyết định.
- Nơi nhận / chữ ký: để khung theo mẫu, không tự điền người ký.
- **Mọi con số đều phải đếm từ dữ liệu, không ước lượng.** Trước khi giao, đếm lại và đối chiếu với CN/CO/CQ/CR ở Bieu tong hop. Báo ngay nếu lệch.

## Quy trình 3: Báo cáo tổng hợp theo kỳ (nhiều KL)
- Phạm vi: các KL có EE = "x" (đang theo dõi), hoặc theo năm/kỳ người dùng nêu.
- Tính toán bằng code (pandas) trên file đã tải, không đếm thủ công. Gồm: tổng KL, tổng KN theo loại và tình trạng; tiền, đất kiến nghị/đã thu/chưa thu (Xu ly kinh te, đơn vị triệu đồng); số tập thể, cá nhân đã xử lý (Xu ly trach nhiem); bảng theo đơn vị (cột G Kien nghi); danh sách KL quá hạn (AX hoặc AZ < ngày báo cáo, CP > 0).
- Xuất báo cáo Word kèm phụ lục .xlsx.

## Quy trình 4: Đôn đốc
- Lọc KL cần đôn đốc theo cột H Bieu tong hop (cảnh báo) và sheet Theo doi bao cao (N, P).
- Soạn công văn đôn đốc riêng cho từng đơn vị, chỉ liệt kê kiến nghị còn tồn của đơn vị đó (nguyên văn E). Lần đầu dùng, xin người dùng một công văn đôn đốc mẫu để theo đúng văn phong.

## Rà soát chất lượng (chạy kèm mọi quy trình, báo cáo ngắn gọn)
- Nội dung kiến nghị trùng nhau trong cùng KL. Ví dụ: BC 242 chép nhầm KN04 của phường Cao Xanh thành nội dung KN02.
- Q = "x" nhưng Y trống, hoặc ngược lại. AB còn ghi "Đang …" trên dòng đã hoàn thành.
- Số dòng thực tế khác CN/CX/DC ở Bieu tong hop.
- Cột G không có trong Danh muc don vi.
- KL có kiểm điểm nhưng thiếu dòng "Sở Nội vụ hướng dẫn" (ví dụ KL 39/2026), hoặc phân loại khác quy ước.
- Lỗi ngày, số trong văn bản, ví dụ "tháng 76".
- Chỉ báo, không tự sửa sổ.

## Bảo mật
KL có thể có tên cá nhân bị kiểm điểm. Không đưa thông tin cá nhân vào tìm kiếm web hoặc dịch vụ bên ngoài.