import os
import sys

# Đặt cờ xác thực khởi động chính quy từ txa.py
os.environ["TXA_LAUNCHED"] = "1"

from bot import run_bot

if __name__ == "__main__":
    run_bot()
