#!/bin/bash
# LT758x 驱动框架依赖安装 (Orange Pi 5 Pro / Ubuntu 22.04)
set -e
cd "$(dirname "$0")"

echo "[1/3] 安装 Python 依赖 (spidev / smbus2 / pillow)..."
python3 -m pip install -r requirements.txt

echo "[2/3] 配置 SPI/I2C 设备权限(免 sudo)..."
sudo tee /etc/udev/rules.d/99-spi-i2c.rules > /dev/null <<'EOF'
SUBSYSTEM=="spidev", MODE="0666"
KERNEL=="i2c-[0-9]*", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "[3/3] 完成。运行演示: python3 main.py"
