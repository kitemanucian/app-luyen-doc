#!/usr/bin/env bash
# ============================================================
# 🚀 CÀI APP LÊN MÁY ẢO ORACLE CLOUD (bản miễn phí vĩnh viễn)
#
# CÁCH DÙNG (chạy trên máy ảo, sau khi đã SSH vào):
#     cd ~/app-luyen-doc
#     bash oracle/cai-dat-lan-dau.sh
#
# Script tự làm hết: cài Docker → tải code → hỏi key Gemini
#                    → build → chạy 24/7 → mở cổng 8000
# ============================================================
set -e

REPO_URL="${REPO_URL:-https://github.com/TEN-BAN/app-luyen-doc.git}"  # ← chỉ cần sửa nếu muốn
APP_DIR="$HOME/app-luyen-doc"
TEN_APP="app-luyen-doc"
PORT=8000

echo "▸ 1/6  Cài Docker (nếu chưa có)..."
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable --now docker

echo "▸ 2/6  Cài git (nếu chưa có)..."
if ! command -v git >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq git
fi

echo "▸ 3/6  Tải code từ GitHub..."
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi

echo "▸ 4/6  Nhập key Gemini..."
if [ -f "$APP_DIR/.env" ]; then
    echo "   (Đã có file .env rồi — giữ nguyên, không hỏi lại)"
else
    read -r -p "   Dán GEMINI_API_KEY mới của bạn rồi Enter: " KEY
    printf 'GEMINI_API_KEY=%s\nALLOWED_ORIGINS=*\n' "$KEY" > "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "   Đã lưu vào $APP_DIR/.env (chỉ máy này đọc được)"
fi

echo "▸ 5/6  Build app (lần đầu hơi lâu, khoảng 5-10 phút vì cài Tesseract + spaCy)..."
sudo docker build -t "$TEN_APP" "$APP_DIR"

echo "▸ 6/6  Chạy app 24/7..."
sudo docker rm -f "$TEN_APP" >/dev/null 2>&1 || true
sudo docker run -d \
    --name "$TEN_APP" \
    --restart unless-stopped \
    -p "$PORT:8000" \
    --env-file "$APP_DIR/.env" \
    "$TEN_APP"

# Oracle mặc định CHẶN hết cổng ở tường lửa của máy ảo → phải mở cổng 8000
echo "▸ Mở cổng $PORT trên tường lửa của máy ảo..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$PORT" -j ACCEPT || true
if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save >/dev/null 2>&1 || true
fi

IP=$(curl -s --max-time 5 ifconfig.me || echo "IP-CUA-BAN")
echo
echo "=============================================================="
echo " ✅ XONG!  Mở trình duyệt và vào địa chỉ:"
echo
echo "        http://$IP:$PORT"
echo
echo " Xem log khi cần :  sudo docker logs -f $TEN_APP"
echo " Tắt / bật lại   :  sudo docker stop $TEN_APP  |  sudo docker start $TEN_APP"
echo "=============================================================="
