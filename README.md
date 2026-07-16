# 🤖 TXA Discord Quest Bot

> **Bot tự động hoàn thành Discord Quests** — Nhận Gift Code, Nitro, Avatar Frame, Profile Decoration mà không cần làm thủ công!

---

## ✨ Tính năng nổi bật

- 🚀 **Tự động 100%** — Làm Quest xem video, chơi game, livestream không cần can thiệp thủ công
- 📊 **Tiến độ thực chiếu** — Cập nhật % tiến trình trực tiếp qua DM Discord (thanh tiến trình emoji)
- 💳 **Hệ thống giới hạn & thanh toán** — Giới hạn theo phiên chạy (session), hỗ trợ QR SePay
- 🔑 **Tiện ích Chrome riêng** — Extension lấy token 1 click, hiện trực tiếp trên Discord (Side Panel)
- 🛡️ **An toàn** — Token không được lưu lại, chỉ dùng trong phiên chạy hiện tại
- 👑 **Bảng Admin** — `/status`, `/set_limit`, `/clear_cache`, `/system_stats`, `/config` đầy đủ

---

## 🚀 Hướng dẫn cho Người Dùng (User)

### Bước 1 — Bật nhận tin nhắn riêng (DM)
Bạn cần bật DM để nhận cập nhật tiến độ từ bot:
1. Vào **Cài đặt người dùng** trên Discord
2. Chọn **Bảo mật & An toàn**
3. Bật **"Cho phép tin nhắn trực tiếp từ thành viên máy chủ"**

### Bước 2 — Lấy Discord Token bằng Tiện ích Chrome
> ⚠️ **Token giống mật khẩu** — Đừng bao giờ chia sẻ cho người khác!

1. Vào kênh Bot và bấm nút **❓ Hướng Dẫn** — Bot sẽ gửi file `TXA_Discord_Token_Retriever.zip`
2. Tải về và cài extension vào Chrome/Edge:
   - Mở `chrome://extensions`
   - Bật **Chế độ Nhà phát triển** (Developer mode) góc trên phải
   - Kéo thả file `.zip` vào trang **hoặc** giải nén → bấm **Load unpacked** → chọn thư mục vừa giải nén
3. Vào [discord.com](https://discord.com) → F5 tải lại trang
4. Bấm icon tiện ích trên thanh trình duyệt → **Side Panel** hiện ra bên phải
5. Token tự động xuất hiện ở dạng ẩn → bấm **📋 Sao Chép Token**

### Bước 3 — Bắt đầu làm Quest
1. Vào kênh Bot do Admin thiết lập
2. Bấm nút **🚀 Bắt Đầu**
3. Dán token vào ô nhập và gửi
4. Bot sẽ nhắn DM tiến độ làm quest cho bạn!

### Bước 4 — Theo dõi & Dừng
- Dùng lệnh `/my_quests` để xem trạng thái và nhận Gift Code khi hoàn thành
- Dùng lệnh `/stop_my_session` để dừng phiên chạy của bạn

---

## 🎯 Các loại Quest được hỗ trợ

| Quest | Mô tả |
|---|---|
| 🎬 Watch Video | Xem video quảng cáo (Mobile/Desktop) |
| 🎮 Play on Desktop | Chơi game/treo game trên Discord Desktop |
| 📡 Stream on Desktop | Livestream trên Discord Desktop |
| 🕹️ Play Activity | Tham gia Activity trong kênh thoại Discord |

---

## 👑 Hướng dẫn cho Admin

### Cài đặt & Chạy Bot

**Yêu cầu:** Python 3.10+, pip

```bash
# Clone repo
git clone https://github.com/TXAVLOG/discord-quest-bot.git
cd discord-quest-bot

# Cài dependencies
pip install -r requirements.txt

# Cấu hình .env (xem phần bên dưới)
# Chạy bot
python bot.py
```

### Cấu hình `.env`

```env
# === DISCORD BOT ===
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_ADMIN_IDS=123456789,987654321

# === THANH TOÁN SEPAY (tuỳ chọn) ===
SEPAY_API_KEY=your_sepay_key
BANK_ID=your_bank_id
ACCOUNT_NO=your_account_number
ACCOUNT_NAME=YOUR_NAME

# === CẤU HÌNH BOT ===
PRICE_PER_QUEST=50000
TRANSACTION_TIMEOUT=300
POLL_INTERVAL=60
HEARTBEAT_INTERVAL=30
AUTO_ACCEPT=true
```

### Các lệnh Admin

| Lệnh | Mô tả |
|---|---|
| `/channel` | Thiết lập kênh hoạt động & tạo bảng điều khiển |
| `/status` | Xem danh sách phiên đang chạy (click tên để DM nhanh) |
| `/system_stats` | Thống kê phần cứng & hiệu suất bot thời gian thực |
| `/config` | Xem toàn bộ cấu hình hệ thống |
| `/set_limit` | Đặt số lượt làm quest cho người dùng |
| `/stop_user` | Dừng phiên của một người dùng cụ thể |
| `/clear_cache` | Xóa `__pycache__` và giải phóng dung lượng |

---

## 🔒 Bảo mật & Điều khoản

- Token người dùng **không được lưu lại** sau khi phiên kết thúc
- Xem thêm: [Chính sách Bảo mật](PRIVACY_POLICY.md) | [Điều khoản Dịch vụ](TERMS_OF_SERVICE.md)

---

<div align="center">
  <sub>Made with ❤️ by TXA • Discord Quest Bot v4.0</sub>
</div>
