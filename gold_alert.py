"""
金价实时监控（悬浮窗版）
version: 3.0
"""

import requests
import tkinter as tk
import threading
import time
import json
import sys
from PIL import Image, ImageDraw

# 尝试导入 pystray
try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("未安装 pystray，系统托盘功能不可用。可运行: pip install pystray pillow")

# 默认配置
ZSH_URL = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"
MS_URL = "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice"
DEFAULT_REFRESH_INTERVAL = 1  # 秒
DEBUG = False


class GoldPriceMonitor:
    def __init__(self, interval=DEFAULT_REFRESH_INTERVAL):
        self.interval = interval
        self.is_active = True
        self.lock = threading.Lock()

        self.zsh_data = {"price": None, "change": None, "error": None}
        self.ms_data = {"price": None, "change": None, "error": None}

        # 创建主窗口（作为隐藏的根窗口，用于管理事件循环）
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏根窗口

        # 创建悬浮窗
        self.create_floating_window()

        # 创建托盘图标
        self.setup_tray()

        # 启动数据获取线程
        self.fetch_thread = threading.Thread(
            target=self.fetch_loop, daemon=True)
        self.fetch_thread.start()

        # 窗口关闭时退出
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

    def create_floating_window(self):
        """创建无边框、置顶、半透明的悬浮窗"""
        self.floating = tk.Toplevel(self.root)
        self.floating.title("金价监控")
        self.floating.overrideredirect(True)  # 无边框
        self.floating.attributes('-topmost', True)  # 置顶
        self.floating.attributes('-alpha', 0.85)  # 半透明（0.0-1.0）
        self.floating.geometry("260x120+50+50")  # 初始位置 (50,50)

        # 背景色和字体
        self.floating.configure(bg='#2c3e50')
        self.floating.wm_attributes(
            '-transparentcolor', '#2c3e50')  # 设置透明色（可选）

        # 内容框架（用于放置标签）
        self.frame = tk.Frame(self.floating, bg='#2c3e50')
        self.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 浙商标签
        self.zsh_label = tk.Label(
            self.frame, text="浙商: 等待数据", font=("微软雅黑", 12),
            fg='#ecf0f1', bg='#2c3e50'
        )
        self.zsh_label.pack(anchor='w', pady=2)

        # 民生标签
        self.ms_label = tk.Label(
            self.frame, text="民生: 等待数据", font=("微软雅黑", 12),
            fg='#ecf0f1', bg='#2c3e50'
        )
        self.ms_label.pack(anchor='w', pady=2)

        # 涨跌标签（整合到一行或单独显示）
        self.change_label = tk.Label(
            self.frame, text="", font=("微软雅黑", 10),
            fg='#bdc3c7', bg='#2c3e50'
        )
        self.change_label.pack(anchor='w', pady=2)

        # 状态标签（显示运行/暂停）
        self.status_label = tk.Label(
            self.frame, text="● 运行中", font=("微软雅黑", 9),
            fg='#2ecc71', bg='#2c3e50'
        )
        self.status_label.pack(anchor='w', pady=2)

        # 绑定鼠标事件，支持拖动
        self.floating.bind('<Button-1>', self.start_move)
        self.floating.bind('<B1-Motion>', self.on_move)

        # 右键菜单（在悬浮窗上右键）
        self.floating.bind('<Button-3>', self.show_context_menu)

        # 创建右键菜单
        self.context_menu = tk.Menu(self.floating, tearoff=0)
        self.context_menu.add_command(label="隐藏窗口", command=self.hide_window)
        self.context_menu.add_command(label="停止刷新", command=self.stop_monitor)
        self.context_menu.add_command(
            label="继续刷新", command=self.resume_monitor)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="退出", command=self.quit_app)

    def show_context_menu(self, event):
        """显示右键菜单"""
        self.context_menu.post(event.x_root, event.y_root)

    def start_move(self, event):
        """开始拖动"""
        self.x = event.x
        self.y = event.y

    def on_move(self, event):
        """拖动中"""
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.floating.winfo_x() + deltax
        y = self.floating.winfo_y() + deltay
        self.floating.geometry(f"+{x}+{y}")

    def hide_window(self):
        """隐藏悬浮窗"""
        self.floating.withdraw()

    def show_window(self):
        """显示悬浮窗"""
        self.floating.deiconify()
        self.floating.lift()

    # ----- 托盘相关 -----
    def create_tray_icon(self):
        size = 64
        image = Image.new('RGB', (size, size), color=(255, 215, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle([size//4, size//4, size*3//4,
                       size*3//4], fill=(255, 140, 0))
        draw.ellipse([size//3, size//3, size*2//3,
                     size*2//3], fill=(255, 215, 0))

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self.show_window, default=True),
            pystray.MenuItem("隐藏窗口", self.hide_window),
            pystray.MenuItem("停止刷新", self.tray_stop_monitor,
                             enabled=lambda item: self.is_active),
            pystray.MenuItem("继续刷新", self.tray_resume_monitor,
                             enabled=lambda item: not self.is_active),
            pystray.MenuItem("退出", self.quit_app)
        )
        return pystray.Icon("gold_monitor", image, "金价监控", menu)

    def setup_tray(self):
        if not PYSTRAY_AVAILABLE:
            print("系统托盘不可用，仅使用悬浮窗模式。")
            return
        self.tray_icon = self.create_tray_icon()
        threading.Thread(target=self.tray_icon.run_detached,
                         daemon=True).start()
        self.root.after(100, self.update_tray_tooltip)

    def update_tray_tooltip(self):
        """更新托盘悬浮提示"""
        if not PYSTRAY_AVAILABLE or not hasattr(self, 'tray_icon') or self.tray_icon is None:
            return
        with self.lock:
            zsh = self.zsh_data
            ms = self.ms_data

        lines = []
        if zsh["error"]:
            lines.append(f"浙商: 错误 - {zsh['error']}")
        elif zsh["price"] is not None:
            change = zsh["change"]
            sign = "+" if change >= 0 else ""
            lines.append(f"浙商: {zsh['price']:.2f} 元/克 ({sign}{change:.2f})")
        else:
            lines.append("浙商: 等待数据")

        if ms["error"]:
            lines.append(f"民生: 错误 - {ms['error']}")
        elif ms["price"] is not None:
            change = ms["change"]
            sign = "+" if change >= 0 else ""
            lines.append(f"民生: {ms['price']:.2f} 元/克 ({sign}{change:.2f})")
        else:
            lines.append("民生: 等待数据")

        tooltip = "/n".join(lines)
        self.tray_icon.title = tooltip
        self.root.after(1000, self.update_tray_tooltip)

    def tray_stop_monitor(self, item=None):
        self.stop_monitor()

    def tray_resume_monitor(self, item=None):
        self.resume_monitor()

    # ----- 数据获取 -----
    def fetch_single(self, url, source_name):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            if DEBUG:
                print(f"=== {source_name} 原始响应 ===")
                print(json.dumps(data, indent=2, ensure_ascii=False))

            result = data.get('resultData', {})
            datas = result.get('datas', {})
            price_str = datas.get('price')
            change_str = datas.get('upAndDownAmt')
            if price_str is None or change_str is None:
                raise ValueError(f"{source_name} API 返回数据缺失必要字段")
            return float(price_str), float(change_str), None
        except Exception as e:
            return None, None, str(e)

    def fetch_loop(self):
        while True:
            if not self.is_active:
                time.sleep(self.interval)
                continue
            price_z, change_z, err_z = self.fetch_single(ZSH_URL, "zheshang")
            with self.lock:
                self.zsh_data = {"price": price_z,
                                 "change": change_z, "error": err_z}
            price_m, change_m, err_m = self.fetch_single(MS_URL, "minsheng")
            with self.lock:
                self.ms_data = {"price": price_m,
                                "change": change_m, "error": err_m}
            self.root.after(0, self.update_gui)
            time.sleep(self.interval)

    def update_gui(self):
        """更新悬浮窗显示"""
        with self.lock:
            zsh = self.zsh_data
            ms = self.ms_data

        # 浙商
        if zsh["error"]:
            zsh_text = f"浙商: 错误"
        elif zsh["price"] is not None:
            zsh_text = f"浙商: {zsh['price']:.2f} 元/克"
        else:
            zsh_text = "浙商: 等待数据"

        # 民生
        if ms["error"]:
            ms_text = f"民生: 错误"
        elif ms["price"] is not None:
            ms_text = f"民生: {ms['price']:.2f} 元/克"
        else:
            ms_text = "民生: 等待数据"

        # 涨跌幅信息（合并显示）
        change_text = ""
        if zsh["price"] is not None and not zsh["error"]:
            change_z = zsh["change"]
            sign_z = "+" if change_z >= 0 else ""
            change_text += f"浙商涨跌: {sign_z}{change_z:.2f}  "
        if ms["price"] is not None and not ms["error"]:
            change_m = ms["change"]
            sign_m = "+" if change_m >= 0 else ""
            change_text += f"民生涨跌: {sign_m}{change_m:.2f}"

        # 更新标签
        self.zsh_label.config(text=zsh_text)
        self.ms_label.config(text=ms_text)
        self.change_label.config(text=change_text)

        # 更新状态标签（运行/暂停）
        if self.is_active:
            self.status_label.config(text="● 运行中", fg='#2ecc71')
        else:
            self.status_label.config(text="● 已暂停", fg='#e67e22')

    def stop_monitor(self):
        self.is_active = False
        self.root.after(0, self.update_gui)

    def resume_monitor(self):
        self.is_active = True
        self.root.after(0, self.update_gui)

    def quit_app(self, item=None):
        if PYSTRAY_AVAILABLE and hasattr(self, 'tray_icon') and self.tray_icon is not None:
            self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()
        sys.exit(0)


def main():
    app = GoldPriceMonitor()
    app.root.mainloop()


if __name__ == "__main__":
    main()
