import os

# Load from .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

API_BASE = os.getenv("API_BASE", "https://discord.com/api/v9")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))
AUTO_ACCEPT = os.getenv("AUTO_ACCEPT", "True").lower() in ("true", "1", "yes")
LOG_PROGRESS = os.getenv("LOG_PROGRESS", "True").lower() in ("true", "1", "yes")
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
CHANNEL_ID = int(os.getenv("CHANNEL_ID")) if os.getenv("CHANNEL_ID", "").strip().isdigit() else None

# Global statistics & tracking
ACTIVE_USERS = {}  # maps user_id -> task reference or metadata
TOTAL_COMPLETED = 0
TOTAL_FAILED = 0

# Load from user_limits.json if it exists to preserve stats across restarts
if os.path.exists("user_limits.json"):
    try:
        import json
        with open("user_limits.json", "r", encoding="utf-8") as f:
            limits_data = json.load(f)
            TOTAL_COMPLETED = limits_data.get("total_completed", 0)
            TOTAL_FAILED = limits_data.get("total_failed", 0)
    except Exception:
        pass

# Custom Emojis (configurable via .env, fallback to standard unicode)
EMOJI_LOADING = os.getenv("EMOJI_LOADING", "⚙️")
EMOJI_SUCCESS = os.getenv("EMOJI_SUCCESS", "✅")
EMOJI_FAIL = os.getenv("EMOJI_FAIL", "❌")
EMOJI_ROCKET = os.getenv("EMOJI_ROCKET", "🚀")

# Cấu hình SePay & Thanh Toán MB Bank
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY", "")
BANK_ID = "MB"
ACCOUNT_NO = "2211231106"
ACCOUNT_NAME = "TANG XUAN ANH"

SUPPORTED_TASKS = [
    "WATCH_VIDEO",
    "PLAY_ON_DESKTOP",
    "STREAM_ON_DESKTOP",
    "PLAY_ACTIVITY",
    "WATCH_VIDEO_ON_MOBILE",
]
