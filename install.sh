#!/bin/bash
# 服务器监控 - 一键安装脚本
# 适配5.5英寸屏幕（1920x1080）

set -e

echo "📦 安装依赖..."
apt install -y python3 python3-pyqt5 python3-psutil curl fonts-wqy-microhei fonts-noto-cjk fonts-noto-color-emoji xterm

echo "📁 安装监控程序..."
mkdir -p /opt/server-monitor/images
cp monitor_pyqt5.py /opt/server-monitor/
cp images/bg.jpg /opt/server-monitor/images/ 2>/dev/null || true

echo "🔧 安装命令行工具..."
cp scripts/run /usr/local/bin/run
cp scripts/run-ansi /usr/local/bin/run-ansi 2>/dev/null || true
cp scripts/run-neofetch /usr/local/bin/run-neofetch 2>/dev/null || true
chmod +x /usr/local/bin/run /usr/local/bin/run-ansi /usr/local/bin/run-neofetch 2>/dev/null

echo "✅ 安装完成！"
echo ""
echo "使用方法："
echo "  启动监控：  DISPLAY=:0 python3 /opt/server-monitor/monitor_pyqt5.py &"
echo "  普通命令：  run <命令>"
echo "  neofetch：  run-neofetch"
