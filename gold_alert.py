"""
金价实时监控（悬浮窗版 + 价格预警）+ 邮件预警
version: 4.1
功能：
- 邮件预警
"""

import requests
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time
import json
import sys
import os
from PIL import Image, ImageDraw

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("未安装 pystray，系统托盘功能不可用。可运行: pip install pystray pillow")

# API 地址
ZSH_URL = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"
MS_URL = "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice"

# 配置
DEFAULT_REFRESH_INTERVAL = 1   # 刷新间隔（秒）
ALERT_COOLDOWN_SECONDS = 8   # 预警冷却时间（秒），同一类型预警在此时间内不重复
CONFIG_FILE = "gold_alerts.json"
DEBUG = False                   # 调试开关，打印原始响应


class GoldPriceMonitor:
    def __init__(self, interval=DEFAULT_REFRESH_INTERVAL):
        self.interval = interval
        self.is_active = True
        self.lock = threading.Lock()

        self.zsh_data = {"price": None, "change": None, "error": None}
        self.ms_data = {"price": None, "change": None, "error": None}

        # 预警配置
        self.alerts = {
            "zheshang": {
                "enabled": True,
                "upper": None,
                "lower": None,
                "last_alert_upper": 0,
                "last_alert_lower": 0
            },
            "minsheng": {
                "enabled": True,
                "upper": None,
                "lower": None,
                "last_alert_upper": 0,
                "last_alert_lower": 0
            }
        }
        self.load_alerts_config()

        # 邮件配置
        self.mail_config = {
            "enabled": False,            # 是否启用邮件预警
            "smtp_server": "smtp.qq.com",
            "smtp_port": 587,
            "sender_email": "",
            "sender_password": "",       # 授权码
            "receiver_email": "",
            "subject_prefix": "【金价预警】"
        }
        self.load_mail_config()  # 新增方法

        # 创建根窗口（隐藏，用于事件循环）
        self.root = tk.Tk()
        self.root.withdraw()

        # 创建悬浮窗
        self.create_floating_window()

        # 创建系统托盘
        self.setup_tray()

        # 启动数据获取线程
        self.fetch_thread = threading.Thread(
            target=self.fetch_loop, daemon=True)
        self.fetch_thread.start()

        # 关闭窗口时退出程序
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

    # ---------- 设置窗口界面初始化 ----------
    def show_alert_settings(self):
        win = tk.Toplevel(self.root)
        win.title("价格预警设置")
        win.geometry("550x450")
        win.attributes('-topmost', True)
        win.resizable(False, False)
        win.grab_set()

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 浙商选项卡
        zsh_frame = ttk.Frame(nb)
        nb.add(zsh_frame, text="浙商金价")
        self._create_alert_ui(zsh_frame, "zheshang")
        win.zsh_frame = zsh_frame

        # 民生选项卡
        ms_frame = ttk.Frame(nb)
        nb.add(ms_frame, text="民生金价")
        self._create_alert_ui(ms_frame, "minsheng")
        win.ms_frame = ms_frame

        # 邮件设置选项卡
        mail_frame = ttk.Frame(nb)
        nb.add(mail_frame, text="邮件通知")
        self._create_mail_ui(mail_frame)
        win.mail_frame = mail_frame

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="保存", command=lambda: self._save_all_settings(
            win)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", command=win.destroy).pack(
            side=tk.LEFT, padx=5)

    # ---------- 创建预警设置界面 ----------
    def _create_alert_ui(self, parent, bank_key):
        bank_name = "浙商" if bank_key == "zheshang" else "民生"
        self.load_alerts_config()
        cfg = self.alerts[bank_key]

        enabled_var = tk.BooleanVar(value=cfg["enabled"])
        tk.Checkbutton(parent, text=f"启用{bank_name}金价预警", variable=enabled_var).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=5)

        tk.Label(parent, text="上限价格（高于此值预警）:").grid(
            row=1, column=0, sticky='e', padx=5, pady=5)
        upper_entry = tk.Entry(parent, width=15)
        upper_entry.insert(0, str(cfg["upper"])
                           if cfg["upper"] is not None else "")
        upper_entry.grid(row=1, column=1, sticky='w', padx=5)

        tk.Label(parent, text="下限价格（低于此值预警）:").grid(
            row=2, column=0, sticky='e', padx=5, pady=5)
        lower_entry = tk.Entry(parent, width=15)
        lower_entry.insert(0, str(cfg["lower"])
                           if cfg["lower"] is not None else "")
        lower_entry.grid(row=2, column=1, sticky='w', padx=5)

        parent.enabled_var = enabled_var
        parent.upper_entry = upper_entry
        parent.lower_entry = lower_entry

    # ---------- 创建邮件设置界面 ----------
    def _create_mail_ui(self, parent):
        # 启用复选框
        self.mail_enabled_var = tk.BooleanVar(
            value=self.mail_config["enabled"])
        tk.Checkbutton(parent, text="启用邮件预警", variable=self.mail_enabled_var).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=5)

        # 服务器
        tk.Label(parent, text="SMTP服务器:").grid(
            row=1, column=0, sticky='e', padx=5, pady=5)
        self.smtp_server_entry = tk.Entry(parent, width=30)
        self.smtp_server_entry.insert(0, self.mail_config["smtp_server"])
        self.smtp_server_entry.grid(row=1, column=1, sticky='w', padx=5)

        # 端口
        tk.Label(parent, text="端口:").grid(
            row=2, column=0, sticky='e', padx=5, pady=5)
        self.smtp_port_entry = tk.Entry(parent, width=10)
        self.smtp_port_entry.insert(0, str(self.mail_config["smtp_port"]))
        self.smtp_port_entry.grid(row=2, column=1, sticky='w', padx=5)

        # 发件邮箱
        tk.Label(parent, text="发件邮箱:").grid(
            row=3, column=0, sticky='e', padx=5, pady=5)
        self.sender_email_entry = tk.Entry(parent, width=30)
        self.sender_email_entry.insert(0, self.mail_config["sender_email"])
        self.sender_email_entry.grid(row=3, column=1, sticky='w', padx=5)

        # 授权码/密码
        tk.Label(parent, text="授权码:").grid(
            row=4, column=0, sticky='e', padx=5, pady=5)
        self.sender_pwd_entry = tk.Entry(parent, width=30, show="*")
        self.sender_pwd_entry.insert(0, self.mail_config["sender_password"])
        self.sender_pwd_entry.grid(row=4, column=1, sticky='w', padx=5)

        # 收件邮箱
        tk.Label(parent, text="收件邮箱:").grid(
            row=5, column=0, sticky='e', padx=5, pady=5)
        self.receiver_email_entry = tk.Entry(parent, width=30)
        self.receiver_email_entry.insert(0, self.mail_config["receiver_email"])
        self.receiver_email_entry.grid(row=5, column=1, sticky='w', padx=5)

        # 主题前缀（可选）
        tk.Label(parent, text="邮件主题前缀:").grid(
            row=6, column=0, sticky='e', padx=5, pady=5)
        self.subject_prefix_entry = tk.Entry(parent, width=30)
        self.subject_prefix_entry.insert(0, self.mail_config["subject_prefix"])
        self.subject_prefix_entry.grid(row=6, column=1, sticky='w', padx=5)

    # ---------- 保存配置 ----------
    def _save_all_settings(self, win):
        # 保存预警配置
        zsh_frame = win.zsh_frame
        ms_frame = win.ms_frame

        self.alerts["zheshang"]["enabled"] = zsh_frame.enabled_var.get()
        upper_str = zsh_frame.upper_entry.get().strip()
        lower_str = zsh_frame.lower_entry.get().strip()
        self.alerts["zheshang"]["upper"] = float(
            upper_str) if upper_str else None
        self.alerts["zheshang"]["lower"] = float(
            lower_str) if lower_str else None

        self.alerts["minsheng"]["enabled"] = ms_frame.enabled_var.get()
        upper_str = ms_frame.upper_entry.get().strip()
        lower_str = ms_frame.lower_entry.get().strip()
        self.alerts["minsheng"]["upper"] = float(
            upper_str) if upper_str else None
        self.alerts["minsheng"]["lower"] = float(
            lower_str) if lower_str else None

        # 保存邮件配置
        self.mail_config["enabled"] = self.mail_enabled_var.get()
        self.mail_config["smtp_server"] = self.smtp_server_entry.get().strip()
        self.mail_config["smtp_port"] = int(self.smtp_port_entry.get().strip())
        self.mail_config["sender_email"] = self.sender_email_entry.get().strip()
        self.mail_config["sender_password"] = self.sender_pwd_entry.get(
        ).strip()
        self.mail_config["receiver_email"] = self.receiver_email_entry.get(
        ).strip()
        self.mail_config["subject_prefix"] = self.subject_prefix_entry.get(
        ).strip()

        # 保存到文件
        self.save_alerts_config()   # 注意：需要修改此方法同时保存邮件配置
        self.save_mail_config()     # 可合并为一个保存方法
        win.destroy()

    # ---------- 预警检查 ----------
    def check_and_alert(self, bank_key, price, current_time):
        self.load_alerts_config()
        cfg = self.alerts[bank_key]
        if not cfg["enabled"]:
            return
        bank_name = "浙商" if bank_key == "zheshang" else "民生"

        # 上限
        if cfg["upper"] is not None and price > cfg["upper"]:
            if current_time - cfg["last_alert_upper"] > ALERT_COOLDOWN_SECONDS:
                cfg["last_alert_upper"] = current_time
                self.show_alert_dialog(bank_name, price, "高于上限", cfg["upper"])
                self.save_alerts_config()

        # 下限
        if cfg["lower"] is not None and price < cfg["lower"]:
            if current_time - cfg["last_alert_lower"] > ALERT_COOLDOWN_SECONDS:
                cfg["last_alert_lower"] = current_time
                self.show_alert_dialog(bank_name, price, "低于下限", cfg["lower"])
                self.save_alerts_config()

    # ---------- 预警弹窗提醒 ----------
    def show_alert_dialog(self, bank_name, price, alert_type, threshold):
        msg = f"{bank_name} 金价 {price:.2f} 元/克\n{alert_type} {threshold:.2f} 元/克"
        self.root.after(0, lambda: messagebox.showwarning("金价预警", msg))
        # 发送邮件（在子线程中，避免阻塞）
        threading.Thread(target=self.send_mail_alert, args=(bank_name, price, alert_type, threshold), daemon=True).start()

    # ---------- 加载预警配置 ----------
    def load_alerts_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    for bank in ['zheshang', 'minsheng']:
                        if bank in saved:
                            self.alerts[bank].update(saved[bank])
            except Exception as e:
                print(f"加载预警配置失败: {e}")

    # ---------- 保存预警配置 ----------
    def save_alerts_config(self):
        try:
            to_save = {}
            for bank in ['zheshang', 'minsheng']:
                to_save[bank] = {
                    "enabled": self.alerts[bank]["enabled"],
                    "upper": self.alerts[bank]["upper"],
                    "lower": self.alerts[bank]["lower"]
                }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存预警配置失败: {e}")

    # ---------- 加载邮件配置 ----------
    def load_mail_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    if "mail_config" in saved:
                        self.mail_config.update(saved["mail_config"])
            except Exception as e:
                print(f"加载邮件配置失败: {e}")

    # ---------- 保存邮件配置（在保存预警设置时一并保存） ----------
    def save_mail_config(self):
        try:
            # 读取现有文件，更新 mail_config
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            data["mail_config"] = self.mail_config.copy()
            # 注意：不要保存密码明文？如需更安全可加密，此处简化
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存邮件配置失败: {e}")

    # ---------- 发送邮件预警（在子线程中运行） ----------
    def send_mail_alert(self, bank_name, price, alert_type, threshold):
        if not self.mail_config["enabled"]:
            return
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.header import Header

            msg = MIMEText(f"""
                金价预警

                银行：{bank_name}
                当前价格：{price:.2f} 元/克
                触发类型：{alert_type}
                阈值：{threshold:.2f} 元/克
                时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
            """, "plain", "utf-8")
            msg['Subject'] = Header(
                f"{self.mail_config['subject_prefix']}{bank_name}金价{alert_type}", "utf-8")
            msg['From'] = self.mail_config["sender_email"]
            msg['To'] = self.mail_config["receiver_email"]

            server = smtplib.SMTP(
                self.mail_config["smtp_server"], self.mail_config["smtp_port"])
            server.starttls()
            server.login(self.mail_config["sender_email"],
                        self.mail_config["sender_password"])
            server.sendmail(self.mail_config["sender_email"], [
                            self.mail_config["receiver_email"]], msg.as_string())
            server.quit()
            print(f"邮件预警已发送至 {self.mail_config['receiver_email']}")
        except Exception as e:
            print(f"发送邮件失败: {e}")

    # ---------- 悬浮窗（主窗口） ----------
    def create_floating_window(self):
        self.floating = tk.Toplevel(self.root)
        self.floating.title("金价监控")
        self.floating.overrideredirect(True)
        self.floating.attributes('-topmost', True)
        self.floating.attributes('-alpha', 0.85)
        self.floating.geometry("260x120+50+50")
        self.floating.configure(bg='#2c3e50')
        self.floating.wm_attributes('-transparentcolor', '#2c3e50')

        self.frame = tk.Frame(self.floating, bg='#2c3e50')
        self.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.zsh_label = tk.Label(
            self.frame, text="浙商: 等待数据", font=("微软雅黑", 12),
            fg='#ecf0f1', bg='#2c3e50'
        )
        self.zsh_label.pack(anchor='w', pady=2)

        self.ms_label = tk.Label(
            self.frame, text="民生: 等待数据", font=("微软雅黑", 12),
            fg='#ecf0f1', bg='#2c3e50'
        )
        self.ms_label.pack(anchor='w', pady=2)

        self.change_label = tk.Label(
            self.frame, text="", font=("微软雅黑", 10),
            fg='#bdc3c7', bg='#2c3e50'
        )
        self.change_label.pack(anchor='w', pady=2)

        self.status_label = tk.Label(
            self.frame, text="● 运行中", font=("微软雅黑", 9),
            fg='#2ecc71', bg='#2c3e50'
        )
        self.status_label.pack(anchor='w', pady=2)

        # 拖动
        self.floating.bind('<Any-Button-1>', self.start_move)
        self.floating.bind('<Any-B1-Motion>', self.on_move)
        self.floating.config(cursor='fleur')

        # 右键菜单
        self.floating.bind('<Button-3>', self.show_context_menu)
        self.context_menu = tk.Menu(self.floating, tearoff=0)
        self.context_menu.add_command(label="隐藏窗口", command=self.hide_window)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="停止刷新", command=self.stop_monitor)
        self.context_menu.add_command(
            label="继续刷新", command=self.resume_monitor)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="设置", command=self.show_alert_settings)
        self.context_menu.add_command(label="退出", command=self.quit_app)

    def start_move(self, event):
        self.drag_x = event.x_root - self.floating.winfo_x()
        self.drag_y = event.y_root - self.floating.winfo_y()

    def on_move(self, event):
        x = event.x_root - self.drag_x
        y = event.y_root - self.drag_y
        self.floating.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def hide_window(self):
        self.floating.withdraw()

    def show_window(self):
        self.floating.deiconify()
        self.floating.lift()

    # ---------- 系统托盘 ----------
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
            pystray.MenuItem("设置", self.show_alert_settings),
            pystray.MenuItem("退出", self.quit_app)
        )
        return pystray.Icon("gold_monitor", image, "金价监控", menu)

    def setup_tray(self):
        if not PYSTRAY_AVAILABLE:
            return
        self.tray_icon = self.create_tray_icon()
        threading.Thread(target=self.tray_icon.run_detached,
                         daemon=True).start()
        self.root.after(100, self.update_tray_tooltip)

    def update_tray_tooltip(self):
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

        tooltip = "\n".join(lines)
        self.tray_icon.title = tooltip
        self.root.after(1000, self.update_tray_tooltip)

    def tray_stop_monitor(self, item=None):
        self.stop_monitor()

    def tray_resume_monitor(self, item=None):
        self.resume_monitor()

    # ---------- 数据获取与更新 ----------
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

            # 预警检查
            current_time = time.time()
            if price_z is not None and not err_z:
                self.check_and_alert("zheshang", price_z, current_time)
            if price_m is not None and not err_m:
                self.check_and_alert("minsheng", price_m, current_time)

            time.sleep(self.interval)

    def update_gui(self):
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

        # 涨跌幅
        change_text = ""
        if zsh["price"] is not None and not zsh["error"]:
            change_z = zsh["change"]
            sign_z = "+" if change_z >= 0 else ""
            change_text += f"浙商涨跌: {sign_z}{change_z:.2f}  "
        if ms["price"] is not None and not ms["error"]:
            change_m = ms["change"]
            sign_m = "+" if change_m >= 0 else ""
            change_text += f"民生涨跌: {sign_m}{change_m:.2f}"

        self.zsh_label.config(text=zsh_text)
        self.ms_label.config(text=ms_text)
        self.change_label.config(text=change_text)

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
