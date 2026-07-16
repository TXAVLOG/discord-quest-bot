# CHÍNH SÁCH BẢO MẬT (PRIVACY POLICY)

*Cập nhật lần cuối: 05 tháng 07 năm 2026*

Nhà phát triển (**TXA**) cam kết bảo vệ tối đa quyền riêng tư và bảo mật thông tin của bạn khi sử dụng **Quest Bot v4.0** (sau đây gọi là "Bot"). Chính sách Bảo mật này giải thích cách chúng tôi xử lý thông tin cá nhân của bạn.

---

## 1. Dữ liệu Thu thập và Xử lý
Chúng tôi chỉ yêu cầu và xử lý loại dữ liệu duy nhất sau:
* **Discord User Token (Mã thông báo tài khoản Discord):** Chuỗi mã hóa dùng để xác thực quyền truy cập của tài khoản bạn với máy chủ Discord.

## 2. Cách thức sử dụng dữ liệu
* Token được sử dụng duy nhất cho mục đích: Gửi các yêu cầu API giả lập (giải pháp xem video, treo game, hoạt động) để hoàn thành các Quest đang diễn ra trên tài khoản của bạn.
* Chúng tôi **không thu thập** bất kỳ thông tin cá nhân nào khác như mật khẩu, email, số điện thoại, tin nhắn chat cá nhân hoặc danh sách bạn bè của bạn.

## 3. Lưu trữ và Bảo mật Dữ liệu
* **Không lưu trữ Cơ sở Dữ liệu (No Database Storage):** Hệ thống được thiết kế tối giản và an toàn tuyệt đối. Chúng tôi **không lưu trữ** token của bạn vào bất kỳ cơ sở dữ liệu (Database), tệp tin (File) hay máy chủ lưu trữ bên ngoài nào.
* **Xử lý trên RAM (Memory-Only Processing):** Token của bạn được nạp trực tiếp vào bộ nhớ RAM tạm thời của tiến trình ứng dụng đang chạy và sẽ tự động bị xóa bỏ (giải phóng hoàn toàn) ngay khi nhiệm vụ hoàn thành hoặc khi tiến trình bị dừng.
* **Mã hóa kết nối:** Mọi yêu cầu truyền tải dữ liệu giữa Bot và Discord API đều được mã hóa thông qua giao thức bảo mật an toàn HTTPS.

## 4. Chia sẻ dữ liệu với bên thứ ba
Chúng tôi **không chia sẻ**, bán hoặc chuyển giao token cũng như thông tin tài khoản của bạn cho bất kỳ cá nhân hoặc tổ chức thứ ba nào dưới bất kỳ hình thức nào.

## 5. Quyền kiểm soát dữ liệu của Người dùng
Bạn có toàn quyền kiểm soát và thu hồi quyền truy cập dữ liệu của mình bất kỳ lúc nào bằng các cách sau:
1. Liên hệ với Quản trị viên quản lý hệ thống Bot để yêu cầu dừng tiến trình và xóa token khỏi bộ nhớ RAM qua lệnh `/stop_user`.
2. **Tự vô hiệu hóa Token:** Truy cập vào tài khoản Discord của bạn và thực hiện thay đổi mật khẩu (Password). Hành động này là cơ chế bảo mật của Discord để tự động đổi/vô hiệu hóa tất cả các User Token cũ của tài khoản đó, khiến Bot không thể tiếp tục truy cập hoặc sử dụng token đó nữa.
