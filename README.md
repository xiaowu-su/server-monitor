# 服务器监控 - PyQt5 版

5.5英寸屏幕（1920x1080）服务器监控仪表盘，带终端输出功能。

## 功能

- 📊 CPU / 内存 / 磁盘使用率监控
- 🌤️ 实时天气显示（深圳）
- 🌐 网络流量监控
- 💻 终端输出卡片 - 在屏幕上实时显示命令输出
- 🐳 Docker 容器状态

## 截图

> 运行在5.5英寸1920x1080屏幕上的效果

## 安装

```bash
git clone https://github.com/USERNAME/server-monitor.git
cd server-monitor
sudo bash install.sh
```

## 使用

### 启动监控

```bash
DISPLAY=:0 python3 /opt/server-monitor/monitor_pyqt5.py &
```

### 终端输出命令

```bash
# 普通命令（显示在屏幕终端卡片上）
run apt update
run docker ps

# 带ANSI颜色的输出
run-ansi neofetch

# neofetch专用（打开xterm窗口）
run-neofetch
```

## 文件结构

```
server-monitor/
├── README.md
├── install.sh          # 一键安装
├── monitor_pyqt5.py    # 主程序
├── scripts/
│   ├── run             # 普通命令
│   ├── run-ansi        # ANSI彩色输出
│   └── run-neofetch    # neofetch专用
└── images/
    └── bg.jpg          # 背景图
```

## 依赖

- Python 3
- PyQt5
- psutil
- curl
- 文泉驿微米黑字体
- Noto CJK 字体
- Noto Color Emoji 字体
- xterm（可选，用于neofetch）

## 环境变量

监控程序需要设置 `DISPLAY=:0` 才能输出到屏幕。

## License

MIT

## License

MIT License - see [LICENSE](LICENSE) for details.
