"""
金价实时监控（系统托盘版）
version: 2.5
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
    def __init__(self, root, zsh_url=ZSH_URL, ms_url=MS_URL, interval=DEFAULT_REFRESH_INTERVAL):
        self.root = root
        self.zsh_url = zsh_url
        self.ms_url = ms_url
        self.interval = interval
        self.is_active = True
        self.lock = threading.Lock()

        self.zsh_data = {"price": None, "change": None, "error": None}
        self.ms_data = {"price": None, "change": None, "error": None}

        self.tray_icon = None
        self.root.withdraw()  # 启动时隐藏主窗口

        self.setup_gui()
        self.setup_tray()
        self.fetch_thread = threading.Thread(
            target=self.fetch_loop, daemon=True)
        self.fetch_thread.start()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

    def setup_gui(self):
        self.root.title("金价实时监控 - 浙商 & 民生")
        self.root.geometry("800x400")
        self.root.attributes('-topmost', True)

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧：浙商
        left_frame = tk.Frame(main_frame, relief=tk.GROOVE, bd=2)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH,
                        expand=True, padx=5, pady=5)
        tk.Label(left_frame, text="【浙商金价】", font=(
            "Arial", 14, "bold")).pack(pady=10)
        self.zsh_price_label = tk.Label(
            left_frame, text="等待数据...", font=("Arial", 20))
        self.zsh_price_label.pack(pady=10)
        self.zsh_change_label = tk.Label(
            left_frame, text="", font=("Arial", 14))
        self.zsh_change_label.pack(pady=10)

        # 右侧：民生
        right_frame = tk.Frame(main_frame, relief=tk.GROOVE, bd=2)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH,
                         expand=True, padx=5, pady=5)
        tk.Label(right_frame, text="【民生金价】", font=(
            "Arial", 14, "bold")).pack(pady=10)
        self.ms_price_label = tk.Label(
            right_frame, text="等待数据...", font=("Arial", 20))
        self.ms_price_label.pack(pady=10)
        self.ms_change_label = tk.Label(
            right_frame, text="", font=("Arial", 14))
        self.ms_change_label.pack(pady=10)

        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        self.status_label = tk.Label(
            bottom_frame, text="状态: 运行中", font=("Arial", 10), fg="green")
        self.status_label.pack(side=tk.LEFT, padx=10)

        button_frame = tk.Frame(bottom_frame)
        button_frame.pack(side=tk.RIGHT, padx=10)

        self.stop_button = tk.Button(
            button_frame, text="停止刷新", command=self.stop_monitor)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.resume_button = tk.Button(
            button_frame, text="继续刷新", command=self.resume_monitor, state=tk.NORMAL)
        self.resume_button.pack(side=tk.LEFT, padx=5)

    def create_tray_icon(self):
        """生成托盘图标和右键菜单"""
        size = 64
        image = Image.new('RGB', (size, size), color=(255, 215, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle([size//4, size//4, size*3//4,
                       size*3//4], fill=(255, 140, 0))
        draw.ellipse([size//3, size//3, size*2//3,
                     size*2//3], fill=(255, 215, 0))

        # 修复：enabled 回调需要接受一个参数（菜单项本身）
        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self.show_window, default=True),
            pystray.MenuItem("停止刷新", self.tray_stop_monitor,
                             enabled=lambda item: self.is_active),
            pystray.MenuItem("继续刷新", self.tray_resume_monitor,
                             enabled=lambda item: not self.is_active),
            pystray.MenuItem("退出", self.quit_app)
        )
        return pystray.Icon("gold_monitor", image, "金价监控", menu)

    def setup_tray(self):
        """启动托盘图标"""
        if not PYSTRAY_AVAILABLE:
            print("系统托盘不可用，使用传统窗口模式。")
            self.root.deiconify()
            return

        self.tray_icon = self.create_tray_icon()
        # pystray 需要在后台线程运行，但注意 Windows 下可能要求主线程？run_detached 是安全的。
        threading.Thread(target=self.tray_icon.run_detached,
                         daemon=True).start()
        self.root.after(100, self.update_tray_tooltip)

    def update_tray_tooltip(self):
        """更新托盘悬浮提示"""
        if not self.tray_icon:
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

        tooltip = "\n".join(lines)
        self.tray_icon.title = tooltip
        self.root.after(1000, self.update_tray_tooltip)

    def show_window(self):
        self.root.deiconify()
        self.root.lift()

    def hide_window(self):
        self.root.withdraw()

    def tray_stop_monitor(self, item=None):
        """停止刷新（托盘菜单回调）"""
        self.stop_monitor()

    def tray_resume_monitor(self, item=None):
        """继续刷新（托盘菜单回调）"""
        self.resume_monitor()

    def quit_app(self, item=None):
        """退出程序"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    # ----- 数据获取与更新 -----
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
            price_z, change_z, err_z = self.fetch_single(
                self.zsh_url, "zheshang")
            with self.lock:
                self.zsh_data = {"price": price_z,
                                 "change": change_z, "error": err_z}
            price_m, change_m, err_m = self.fetch_single(
                self.ms_url, "minsheng")
            with self.lock:
                self.ms_data = {"price": price_m,
                                "change": change_m, "error": err_m}
            self.root.after(0, self.update_gui)
            time.sleep(self.interval)

    def update_gui(self):
        with self.lock:
            zsh = self.zsh_data
            ms = self.ms_data

        # 浙商
        if zsh["error"]:
            self.zsh_price_label.config(text="获取失败")
            self.zsh_change_label.config(text="")
        elif zsh["price"] is not None:
            self.zsh_price_label.config(text=f"{zsh['price']:.2f} 元/克")
            change_val = zsh["change"]
            if isinstance(change_val, (int, float)):
                sign = "+" if change_val >= 0 else ""
                self.zsh_change_label.config(
                    text=f"涨跌额: {sign}{change_val:.2f} 元/克")
            else:
                self.zsh_change_label.config(text=f"涨跌额: {change_val}")
        else:
            self.zsh_price_label.config(text="等待数据...")
            self.zsh_change_label.config(text="")

        # 民生
        if ms["error"]:
            self.ms_price_label.config(text="获取失败")
            self.ms_change_label.config(text="")
        elif ms["price"] is not None:
            self.ms_price_label.config(text=f"{ms['price']:.2f} 元/克")
            change_val = ms["change"]
            if isinstance(change_val, (int, float)):
                sign = "+" if change_val >= 0 else ""
                self.ms_change_label.config(
                    text=f"涨跌额: {sign}{change_val:.2f} 元/克")
            else:
                self.ms_change_label.config(text=f"涨跌额: {change_val}")
        else:
            self.ms_price_label.config(text="等待数据...")
            self.ms_change_label.config(text="")

        # 状态栏
        if self.is_active:
            if zsh["error"] or ms["error"]:
                err_msgs = []
                if zsh["error"]:
                    err_msgs.append(f"浙商: {zsh['error']}")
                if ms["error"]:
                    err_msgs.append(f"民生: {ms['error']}")
                self.status_label.config(
                    text=f"状态: 运行中（部分错误） - {'; '.join(err_msgs)}", fg="orange")
            else:
                self.status_label.config(text="状态: 运行中", fg="green")
        else:
            self.status_label.config(text="状态: 已暂停", fg="orange")

    def stop_monitor(self):
        self.is_active = False
        self.stop_button.config(state=tk.DISABLED)
        self.resume_button.config(state=tk.NORMAL)
        self.root.after(0, self.update_gui)

    def resume_monitor(self):
        self.is_active = True
        self.stop_button.config(state=tk.NORMAL)
        self.resume_button.config(state=tk.DISABLED)
        self.root.after(0, self.update_gui)


def main():
    root = tk.Tk()
    app = GoldPriceMonitor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
