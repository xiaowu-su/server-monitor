#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务器监控 - PyQt5 版本
适配5.5英寸屏幕（1920x1080 横屏）
功能：CPU/内存/磁盘监控、天气、网络流量、Docker容器
"""

import sys
import os
import time
import socket
import json
import subprocess
import threading
from datetime import datetime

# PyQt5 导入
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QFrame, QProgressBar,
    QVBoxLayout, QHBoxLayout, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont


# ============================================================
# 全局样式表 - 所有控件的样式
# ============================================================
STYLE_SHEET = """
* {
    font-family: "WenQuanYi Micro Hei", "Noto Sans CJK SC", sans-serif;
}

/* 主窗口 - 透明背景 */
QWidget#mainWindow {
    background-color: transparent;
}

/* 顶部标题栏 */
QWidget#header {
    background-color: rgba(12, 40, 80, 0.95);
    border-bottom: 1px solid rgba(30, 60, 110, 0.6);
}

/* 卡片样式（未直接使用，卡片用内联样式） */
QFrame.card {
    background-color: rgba(16, 28, 50, 0.95);
    border-radius: 14px;
    border: 1px solid rgba(30, 60, 110, 0.6);
}

/* 进度条基础样式 */
QProgressBar {
    border: none;
    border-radius: 6px;
    background-color: rgba(35, 45, 70, 0.8);
    max-height: 14px;
    min-height: 14px;
    text-align: center;
    color: transparent;
}

/* 进度条填充颜色 - 默认蓝色 */
QProgressBar::chunk {
    border-radius: 6px;
    background-color: #4fc3f7;
}

/* 内存进度条 - 绿色 */
QProgressBar#memBar::chunk {
    background-color: #81c784;
}

/* 磁盘/ 进度条 - 橙色 */
QProgressBar#diskBar::chunk {
    background-color: #ffb74d;
}

/* 磁盘/vol1 进度条 - 红色 */
QProgressBar#disk1Bar::chunk {
    background-color: #e57373;
}
"""


class MonitorWindow(QWidget):
    """
    服务器监控主窗口
    显示系统信息、CPU/内存/磁盘使用率、天气、网络流量、Docker状态
    适配5.5英寸屏幕，分辨率1920x1080
    """

    def __init__(self):
        super().__init__()
        # 设置窗口属性
        self.setObjectName("mainWindow")
        self.setWindowTitle("服务器监控")
        self.setFixedSize(1920, 1080)  # 5.5寸屏固定分辨率

        # 加载背景图片
        self.bg_pixmap = None
        bg_path = "/opt/server-monitor/images/bg.jpg"
        if os.path.exists(bg_path):
            self.bg_pixmap = QPixmap(bg_path)

        # 网络速度计算变量
        self.prev_net = None        # 上一次的网络计数器
        self.prev_time = time.time()  # 上一次的时间戳

        # 终端输出相关
        self.terminal_lines = []     # 终端输出行缓冲
        self.terminal_file = '/tmp/terminal_output.log'  # 使用普通文件
        self._last_terminal_content = ''  # 上次读取的内容

        # 构建界面
        self.init_ui()

        # 系统数据更新定时器（每2秒）
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)

        # 天气更新定时器（每60秒）
        self.weather_timer = QTimer()
        self.weather_timer.timeout.connect(self.update_weather)
        self.weather_timer.start(60000)

        # 终端输出刷新定时器（每500毫秒）
        self.terminal_timer = QTimer()
        self.terminal_timer.timeout.connect(self.refresh_terminal)
        self.terminal_timer.start(1000)  # 每1秒刷新

        # 首次立即更新
        self.update_data()
        self.update_weather()

    def init_ui(self):
        """构建整个界面布局"""

        # ========================================
        # 主垂直布局（填满整个窗口）
        # ========================================
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 无边距
        main_layout.setSpacing(0)                     # 各区域之间无间距

        # ========================================
        # 顶部标题栏
        # ========================================
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(80)  # 标题栏高度80px
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)

        # 左侧：标题
        self.title_lbl = QLabel("服务器监控")
        self.title_lbl.setStyleSheet(
            "color: white; font-size: 32px; font-weight: bold; background: transparent;"
        )
        header_layout.addWidget(self.title_lbl)

        # 弹性空间，把时间推到右边
        header_layout.addStretch()

        # 右侧：日期时间和服务器信息
        self.time_lbl = QLabel()
        self.time_lbl.setStyleSheet(
            "color: white; font-size: 26px; background: transparent;"
        )
        self.time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(self.time_lbl)

        main_layout.addWidget(header)

        # ========================================
        # 内容区（左栏 + 右栏）
        # ========================================
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 10, 16, 0)  # 上方间距10px
        content_layout.setSpacing(14)  # 左右栏间距

        # ----- 左栏：系统使用率卡片 -----
        left_widget = QWidget()
        left_widget.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)  # 卡片之间间距
        left_layout.setAlignment(Qt.AlignTop)  # 顶部对齐

        # 系统信息卡片（只显示文字，无进度条）
        sys_card = self.make_card("系统信息")
        sys_card.setMinimumHeight(160)  # 最小高度
        self.sys_lbl = QLabel()
        self.sys_lbl.setStyleSheet(
            "color: #e8e8e8; font-size: 22px; background: transparent;"
        )
        sys_card.layout().addWidget(self.sys_lbl)
        left_layout.addWidget(sys_card)

        # CPU使用率卡片（带进度条）
        self.cpu_bar = self.make_progress_card("CPU 使用率", "cpuBar")
        self.cpu_bar.setMinimumHeight(160)  # 最小高度
        left_layout.addWidget(self.cpu_bar)

        # 内存使用率卡片（带进度条）
        self.mem_bar = self.make_progress_card("内存使用率", "memBar")
        self.mem_bar.setMinimumHeight(160)  # 最小高度
        left_layout.addWidget(self.mem_bar)

        # 磁盘/ 使用率卡片（带进度条）
        self.disk_bar = self.make_progress_card("磁盘使用率 (/)", "diskBar")
        self.disk_bar.setMinimumHeight(160)  # 最小高度
        left_layout.addWidget(self.disk_bar)

        # 磁盘/vol1 使用率卡片（带进度条）
        self.disk1_bar = self.make_progress_card("磁盘使用率 (/vol1)", "disk1Bar")
        self.disk1_bar.setMinimumHeight(160)  # 最小高度
        left_layout.addWidget(self.disk1_bar)

        # 网络流量卡片（放在左栏）
        net_card = self.make_card("网络流量")
        net_card.setMinimumHeight(160)  # 最小高度
        self.net_lbl = QLabel()
        self.net_lbl.setStyleSheet(
            "color: #e8e8e8; font-size: 22px; background: transparent;"
        )
        net_card.layout().addWidget(self.net_lbl)
        left_layout.addWidget(net_card)

        # 左栏占3/5宽度
        content_layout.addWidget(left_widget, stretch=2)

        # ----- 右栏：天气 -----
        right_widget = QWidget()
        right_widget.setStyleSheet("background: transparent;")
        right_widget.setContentsMargins(0, 0, 0, 0)  # 无边距
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)  # 无间距

        # 天气卡片
        weather_card = self.make_card("天气 - 深圳")
        weather_card.setFixedHeight(488)  # 两个卡片高度
        self.weather_lbl = QLabel()
        self.weather_lbl.setStyleSheet(
            "color: #e8e8e8; font-size: 22px; background: transparent;"
        )
        self.weather_lbl.setWordWrap(True)  # 允许文字换行
        weather_card.layout().addWidget(self.weather_lbl)
        right_layout.addWidget(weather_card)

        # 终端输出卡片（天气下面，延伸到底部，与左栏底部对齐）
        terminal_card = self.make_card("终端输出")
        terminal_card.setFixedHeight(488)  # 左栏3个卡片高度：160×3+4×2
        self.terminal_txt = QTextEdit()
        self.terminal_txt.setReadOnly(True)
        self.terminal_txt.setLineWrapMode(QTextEdit.WidgetWidth)
        self.terminal_txt.setStyleSheet(
            "color: #00ff88; font-size: 28px; background: transparent;"
            "border: none; padding: 0px;"
        )
        font = QFont("WenQuanYi Micro Hei Mono", 28)
        self.terminal_txt.setFont(font)
        terminal_card.layout().addWidget(self.terminal_txt)
        right_layout.addWidget(terminal_card, stretch=1)

        # 弹性空间，天气靠上显示
        right_layout.addStretch(2)

        # 右栏占2/5宽度
        content_layout.addWidget(right_widget, stretch=2)

        # 添加内容区到主布局
        main_layout.addWidget(content_widget, stretch=1)

    def make_card(self, title):
        """
        创建带标题的卡片
        用于：系统信息、天气、网络流量、Docker
        返回：带标题标签的QFrame
        """
        card = QFrame()
        card.setObjectName("cardFrame")
        # 卡片样式：深蓝半透明背景 + 圆角
        card.setStyleSheet("""
            QFrame#cardFrame {
                background-color: rgba(16, 28, 50, 0.85);
                border-radius: 12px;
                border: 1px solid rgba(30, 60, 110, 0.5);
            }
        """)

        # 垂直布局
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 6, 12, 6)  # 卡片内边距
        layout.setSpacing(2)

        # 卡片标题（蓝色加粗）
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #4fc3f7; font-size: 28px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(title_lbl)

        return card

    def make_progress_card(self, title, bar_name):
        """
        创建带进度条的卡片
        用于：CPU、内存、磁盘使用率
        返回：带 _progress 和 _value_lbl 属性的QFrame
        """
        card = QFrame()
        card.setObjectName("cardFrame")
        # 同样的卡片样式
        card.setStyleSheet("""
            QFrame#cardFrame {
                background-color: rgba(16, 28, 50, 0.85);
                border-radius: 12px;
                border: 1px solid rgba(30, 60, 110, 0.5);
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)

        # 顶部行：标题在左，数值在右
        top_row = QHBoxLayout()

        # 卡片标题
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #4fc3f7; font-size: 28px; font-weight: bold; background: transparent;"
        )
        top_row.addWidget(title_lbl)

        # 数值显示（如 "45.2%  (4核)"）
        value_lbl = QLabel("0%")
        value_lbl.setStyleSheet(
            "color: #e8e8e8; font-size: 24px; background: transparent;"
        )
        value_lbl.setAlignment(Qt.AlignRight)  # 右对齐
        value_lbl.setObjectName(f"{bar_name}_value")
        top_row.addWidget(value_lbl)

        layout.addLayout(top_row)

        # 进度条
        progress = QProgressBar()
        progress.setObjectName(bar_name)  # 用于CSS选择颜色
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setFixedHeight(14)  # 进度条高度
        layout.addWidget(progress)

        # 保存引用，供后续更新使用
        card._value_lbl = value_lbl
        card._progress = progress

        return card

    def paintEvent(self, event):
        """
        自定义绘制事件 - 绘制背景图片
        Qt在窗口需要重绘时自动调用
        """
        painter = QPainter(self)
        if self.bg_pixmap:
            # 缩放背景图适应窗口，保持比例
            scaled = self.bg_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,  # 填满整个窗口
                Qt.SmoothTransformation         # 高质量缩放
            )
            # 居中显示（如果背景图比窗口大）
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            # 没有背景图就用纯色
            painter.fillRect(self.rect(), QColor(10, 18, 32))
        painter.end()

    def update_progress(self, card, percent, text):
        """
        更新进度条卡片的数值和文字
        参数：
            card: 卡片组件（来自make_progress_card）
            percent: 使用百分比（0-100）
            text: 显示文字（如 "45.2%  (4核)"）
        """
        card._progress.setValue(int(percent))
        card._value_lbl.setText(text)

    def update_data(self):
        """
        获取并显示所有系统数据
        每2秒由定时器调用
        """
        try:
            import psutil  # 系统监控库

            # --- 服务器信息 ---
            host = os.uname().nodename                    # 主机名
            up = time.time() - psutil.boot_time()         # 运行时间（秒）
            d = int(up // 86400)                          # 天
            h = int((up % 86400) // 3600)                 # 时
            m = int((up % 3600) // 60)                    # 分
            ip = self.get_ip()                            # IP地址

            # 当前日期时间
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            weekday = weekday_names[datetime.now().weekday()]

            # 更新标题栏：时间和服务器信息
            self.time_lbl.setText(
                f"{now}  {weekday}\n{host} | 运行 {d}天{h}时{m}分 | IP: {ip}"
            )

            # --- 系统信息卡片 ---
            cc = psutil.cpu_count()          # CPU核心数
            cf = psutil.cpu_freq()           # CPU频率
            freq = f"{cf.current:.0f}MHz" if cf else ""
            self.sys_lbl.setText(
                f"{self.get_os_info()} | CPU: {cc}核 @ {freq}"
            )

            # --- CPU使用率 ---
            cpu = psutil.cpu_percent(interval=0.1)  # 采样0.1秒
            self.update_progress(
                self.cpu_bar, cpu,
                f"{cpu:.1f}%  ({cc}核)"
            )

            # --- 内存使用率 ---
            mv = psutil.virtual_memory()
            self.update_progress(
                self.mem_bar, mv.percent,
                f"{mv.percent:.1f}%  ({mv.used/1024**3:.1f}G / {mv.total/1024**3:.1f}G)"
            )

            # --- 磁盘/ 使用率 ---
            du = psutil.disk_usage('/')
            self.update_progress(
                self.disk_bar, du.percent,
                f"{du.percent:.1f}%  ({du.used/1024**3:.1f}G / {du.total/1024**3:.1f}G)"
            )

            # --- 磁盘/vol1 使用率（可能不存在）---
            try:
                d1 = psutil.disk_usage('/vol1')
                self.update_progress(
                    self.disk1_bar, d1.percent,
                    f"{d1.percent:.1f}%  ({d1.used/1024**3:.1f}G / {d1.total/1024**3:.1f}G)"
                )
            except:
                self.update_progress(self.disk1_bar, 0, "未挂载")

            # --- 网络速度 ---
            net = psutil.net_io_counters()
            dt = time.time() - self.prev_time
            if self.prev_net and dt > 0:
                # 计算速度：(当前值 - 上次值) / 时间差
                up_speed = (net.bytes_sent - self.prev_net.bytes_sent) / dt
                dn_speed = (net.bytes_recv - self.prev_net.bytes_recv) / dt
                self.net_lbl.setText(
                    f"↑ {self.fmt_speed(up_speed)}  ↓ {self.fmt_speed(dn_speed)}\n"
                    f"总发送: {self.fmt_bytes(net.bytes_sent)}  "
                    f"总接收: {self.fmt_bytes(net.bytes_recv)}"
                )
            self.prev_net = net
            self.prev_time = time.time()

            # --- Docker容器（后台线程获取）---
            threading.Thread(target=self.update_docker_async, daemon=True).start()

        except Exception as e:
            print(f"更新错误: {e}")

    def update_weather(self):
        """
        从wttr.in获取天气数据并显示
        每60秒由天气定时器调用
        """
        try:
            # 获取当前天气：温度、描述、湿度、风速
            r = subprocess.run(
                ['curl', '-s', 'wttr.in/深圳?format=%t|%C|%h|%w'],
                capture_output=True, text=True, timeout=10
            )
            parts = r.stdout.strip().split('|')
            temp = parts[0].replace('+', '') if parts else '--'
            desc_en = parts[1] if len(parts) > 1 else '--'
            desc = self.translate_weather(desc_en)
            hum = parts[2] if len(parts) > 2 else '--'
            wind = parts[3] if len(parts) > 3 else '--'

            # 获取小时预报
            r2 = subprocess.run(
                ['curl', '-s', 'wttr.in/深圳?format=j1'],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(r2.stdout)
            hours = data.get('weather', [{}])[0].get('hourly', [])

            # 格式化今天日期
            today = datetime.now().strftime('%Y年%m月%d日')
            weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            weekday = weekday_names[datetime.now().weekday()]

            # 构建HTML格式的天气文本
            text = (
                f"<span style='color:#4fc3f7; font-size:28px;'>{today} {weekday}</span><br>"
                f"<span style='color:#e8e8e8; font-size:28px;'>☀️ {temp}°C  {desc}</span><br>"
                f"<span style='color:#8892a0; font-size:22px;'>湿度 {hum}  风速 {wind}</span><br><br>"
                f"<span style='color:#4fc3f7; font-size:28px;'>未来预报：</span><br>"
            )

            # 添加6个时段的预报
            for h in hours[:6]:
                hr = int(h.get('time', '0')) // 100        # 小时（0-23）
                ft = h.get('tempC', '--')                   # 温度
                fd_en = h.get('weatherDesc', [{}])[0].get('value', '--').strip()
                fd = self.translate_weather(fd_en)          # 翻译成中文
                text += (
                    f"<span style='color:#b0b0b0; font-size:22px;'>"
                    f"{hr:02d}:00  {ft}°C  {fd}</span><br>"
                )

            self.weather_lbl.setText(text)
        except Exception as e:
            print(f"天气错误: {e}")

    def update_docker_async(self):
        """
        后台线程获取Docker容器状态
        使用QTimer.singleShot在主线程更新UI（线程安全）
        """
        try:
            # 获取容器名称和状态
            ps = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}\t{{.State}}'],
                capture_output=True, text=True, timeout=5
            )
            states = {}
            for line in ps.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        states[parts[0]] = parts[1]

            # 获取容器资源使用（可能较慢）
            try:
                st = subprocess.run(
                    ['docker', 'stats', '--no-stream',
                     '--format', '{{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}'],
                    capture_output=True, text=True, timeout=8
                )
                stats_lines = st.stdout.strip().split('\n')
            except subprocess.TimeoutExpired:
                stats_lines = []  # 超时，只显示状态

            # 格式化输出文本
            text = ''
            for line in stats_lines:
                if not line or line.startswith('NAME'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    # 绿色点=运行中，红色点=已停止
                    dot = '●' if states.get(parts[0]) == 'running' else '○'
                    text += f'{dot} {parts[0]}  CPU {parts[1]}  MEM {parts[2]}\n'

            # 备用方案：如果stats失败但有状态信息
            if not text and states:
                for name, state in states.items():
                    dot = '●' if state == 'running' else '○'
                    text += f'{dot} {name}  {state}\n'

            # 在主线程更新UI（线程安全）
            QTimer.singleShot(0, lambda: self.docker_lbl.setText(text or "没有容器"))
        except Exception:
            QTimer.singleShot(0, lambda: self.docker_lbl.setText("获取失败"))

    def refresh_terminal(self):
        """
        定时刷新终端输出显示（直接读文件，不追踪位置）
        """
        try:
            if not os.path.exists(self.terminal_file):
                return
            with open(self.terminal_file, 'r') as f:
                content = f.read()
            if content != self._last_terminal_content:
                self._last_terminal_content = content
                self.terminal_txt.setText(content)
                scrollbar = self.terminal_txt.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        except Exception:
            pass

    def translate_weather(self, desc):
        """
        英文天气描述翻译成中文
        参数：
            desc: 英文天气描述（如 "Partly cloudy"）
        返回：
            中文翻译（如 "多云"）
        """
        mapping = {
            'Clear': '晴',
            'Sunny': '晴',
            'Partly cloudy': '多云',
            'Cloudy': '阴',
            'Overcast': '阴天',
            'Mist': '薄雾',
            'Light rain': '小雨',
            'Moderate rain': '中雨',
            'Heavy rain': '大雨',
            'Fog': '雾',
            'Rain Shower': '阵雨',
            'Light rain shower': '小阵雨',
            'Moderate rain shower': '中阵雨',
            'Heavy rain shower': '大阵雨',
            'Patchy rain possible': '可能有雨',
            'Patchy rain nearby': '附近有雨',
            'Thundery outbreaks possible': '可能有雷阵雨',
            'Light drizzle': '毛毛雨',
            'Patchy light drizzle': '零星毛毛雨',
            'Patchy light rain': '零星小雨',
            'Light freezing rain': '冻雨',
            'Moderate or heavy freezing rain': '大冻雨',
            'Light sleet': '雨夹雪',
            'Moderate or heavy sleet': '大雨夹雪',
            'Patchy snow possible': '可能有雪',
            'Light snow': '小雪',
            'Moderate snow': '中雪',
            'Heavy snow': '大雪',
            'Blowing snow': '风吹雪',
            'Blizzard': '暴风雪',
            'Freezing fog': '冻雾',
            'Patchy light snow': '零星小雪',
            'Moderate or heavy snow showers': '大阵雪',
            'Light snow showers': '小阵雪',
            'Moderate or heavy showers of snow': '大阵雪',
        }
        for en, zh in mapping.items():
            if en.lower() in desc.lower():
                return zh
        return desc  # 没找到翻译就返回原文

    def get_os_info(self):
        """
        从/etc/os-release读取操作系统名称
        返回：操作系统名称字符串（如 "Debian GNU/Linux 12"）
        """
        try:
            with open('/etc/os-release') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=', 1)[1].strip().strip('"')[:35]
        except:
            pass
        return "Linux"

    def get_ip(self):
        """
        通过连接外部服务器获取本机IP地址
        返回：IP地址字符串
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # 谷歌DNS
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "未知"

    def fmt_speed(self, bps):
        """
        格式化速度：字节/秒 → 可读字符串
        参数：
            bps: 字节/秒
        返回：
            格式化字符串（如 "1.2 MB/s"）
        """
        if bps < 1024:
            return f"{bps:.0f} B/s"
        elif bps < 1024**2:
            return f"{bps/1024:.1f} KB/s"
        else:
            return f"{bps/1024**2:.1f} MB/s"

    def fmt_bytes(self, b):
        """
        格式化字节数 → 可读大小
        参数：
            b: 字节数
        返回：
            格式化字符串（如 "2.1 GB"）
        """
        if b < 1024**2:
            return f"{b/1024:.0f} KB"
        elif b < 1024**3:
            return f"{b/1024**2:.1f} MB"
        else:
            return f"{b/1024**3:.1f} GB"


# ============================================================
# 程序入口
# ============================================================
if __name__ == "__main__":
    # 创建Qt应用
    app = QApplication(sys.argv)

    # 应用全局样式表
    app.setStyleSheet(STYLE_SHEET)

    # 创建并显示监控窗口（全屏）
    monitor = MonitorWindow()
    monitor.showFullScreen()

    # 运行事件循环
    sys.exit(app.exec_())
