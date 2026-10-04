#!/usr/bin/env bash
# ============================================================
# 🔄 CẬP NHẬT APP SAU KHI BẠN SỬA CODE VÀ PUSH LÊN GITHUB
#
# CÁCH DÙNG (chạy trên máy ảo Oracle):
#     cd ~/app-luyen-doc
#     bash oracle/cap-nhat.sh
# ============================================================
set -e

APP_DIR="$HOME/app-luyen-doc"
TEN_APP="app-luyen-doc"
PORT=8000

cd "$APP_DIR"

echo "▸ 1/3  Tải code mới nhất từ GitHub..."
git pull

echo "▸ 2/3  Build lại (nhanh hơn lần đầu vì đã có cache)..."
sudo docker build -t "$TEN_APP" .

echo "▸ 3/3  Khởi động lại app..."
sudo docker rm -f "$TEN_APP" >/dev/null 2>&1 || true
sudo docker run -d \
    --name "$TEN_APP" \
    --restart unless-stopped \
    -p "$PORT:8000" \
    --env-file "$APP_DIR/.env" \
    "$TEN_APP"

sudo docker image prune -f >/dev/null 2>&1 || true

IP=$(curl -s --max-time 5 ifconfig.me || echo "IP-CUA-BAN")
echo
echo "✅ Đã cập nhật xong! Xem lại tại: http://$IP:$PORT"
