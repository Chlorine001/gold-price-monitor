#!/usr/bin/env python3
"""
金价实时监控（悬浮窗版 + 价格预警）+ 邮件预警
version: 6.1
功能: 
- 密码加密存储
- 支持自定义预警冷却时间
"""

import requests
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time
import json
import sys
import os
import logging
import smtplib
import base64
from email.mime.text import MIMEText
from email.header import Header
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from PIL import Image, ImageDraw

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

# ------------------ 日志配置 ------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("gold_monitor.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GoldMonitor")

# ------------------ 常量 ------------------
ZSH_URL = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"
MS_URL = "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice"
DEFAULT_REFRESH_INTERVAL = 1
ALERT_COOLDOWN_SECONDS = 20
CONFIG_FILE = "gold_config.json"
DEBUG = False

# ------------------ 加密工具 ------------------
# 固定密钥（可自行修改，注意保密性）
_ENCRYPT_KEY = b'gold_monitor_2026_key!@#'


def _simple_encrypt(text: str) -> str:
    """简单异或加密 + Base64编码，返回加密后的字符串"""
    if not text:
        return ""
    data = text.encode('utf-8')
    key = _ENCRYPT_KEY
    encrypted = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
    return base64.b64encode(encrypted).decode('ascii')


def _simple_decrypt(encrypted: str) -> str:
    """解密由_simple_encrypt加密的字符串"""
    if not encrypted:
        return ""
    try:
        data = base64.b64decode(encrypted.encode('ascii'))
        key = _ENCRYPT_KEY
        decrypted = bytes([data[i] ^ key[i % len(key)]
                          for i in range(len(data))])
        return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"解密失败: {e}")
        return ""

# ------------------ 数据类 ------------------


@dataclass
class AlertConfig:
    enabled: bool = True
    upper: Optional[float] = None
    lower: Optional[float] = None
    last_alert_upper: float = 0.0
    last_alert_lower: float = 0.0


@dataclass
class MailConfig:
    enabled: bool = False
    smtp_server: str = "smtp.qq.com"
    smtp_port: int = 587
    sender_email: str = ""
    sender_password: str = ""   # 存储时加密
    receiver_email: str = ""
    subject_prefix: str = "【金价预警】"


@dataclass
class AppConfig:
    refresh_interval: int = DEFAULT_REFRESH_INTERVAL
    alert_cooldown_seconds: int = ALERT_COOLDOWN_SECONDS   # 预警冷却时间
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    alerts: Dict[str, AlertConfig] = None
    mail: MailConfig = None

    def __post_init__(self):
        if self.alerts is None:
            self.alerts = {
                "zheshang": AlertConfig(),
                "minsheng": AlertConfig()
            }
        if self.mail is None:
            self.mail = MailConfig()

# 添加全局函数


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ------------------ 主类 ------------------
class GoldPriceMonitor:
    def __init__(self):
        self.config = self.load_config()
        self.is_active = True
        self.lock = threading.RLock()
        self.zsh_data = {"price": None, "change": None, "error": None}
        self.ms_data = {"price": None, "change": None, "error": None}

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

        self.create_floating_window()
        self.setup_tray()

        self.fetch_thread = threading.Thread(
            target=self.fetch_loop, daemon=True)
        self.fetch_thread.start()

    # ---------- 配置加载与保存（含密码加密） ----------
    def load_config(self) -> AppConfig:
        if not os.path.exists(CONFIG_FILE):
            return AppConfig()
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cfg = AppConfig()
            cfg.refresh_interval = data.get(
                "refresh_interval", DEFAULT_REFRESH_INTERVAL)
            cfg.alert_cooldown_seconds = data.get(
                "alert_cooldown_seconds", ALERT_COOLDOWN_SECONDS)   # 新增
            cfg.window_x = data.get("window_x")          # 可能为 None
            cfg.window_y = data.get("window_y")

            # 加载预警配置
            for bank in ["zheshang", "minsheng"]:
                if bank in data.get("alerts", {}):
                    alert_data = data["alerts"][bank]
                    cfg.alerts[bank] = AlertConfig(
                        enabled=alert_data.get("enabled", True),
                        upper=alert_data.get("upper"),
                        lower=alert_data.get("lower"),
                        last_alert_upper=alert_data.get("last_alert_upper", 0),
                        last_alert_lower=alert_data.get("last_alert_lower", 0)
                    )

            # 加载邮件配置（密码自动解密）
            if "mail" in data:
                mail_data = data["mail"]
                pwd = mail_data.get("sender_password", "")
                # 兼容旧配置: 若以 'ENC:' 开头则解密，否则视为明文
                if pwd.startswith("ENC:"):
                    pwd = _simple_decrypt(pwd[4:])
                cfg.mail = MailConfig(
                    enabled=mail_data.get("enabled", False),
                    smtp_server=mail_data.get("smtp_server", "smtp.qq.com"),
                    smtp_port=mail_data.get("smtp_port", 587),
                    sender_email=mail_data.get("sender_email", ""),
                    sender_password=pwd,
                    receiver_email=mail_data.get("receiver_email", ""),
                    subject_prefix=mail_data.get("subject_prefix", "【金价预警】")
                )
            logger.info("配置加载成功")
            return cfg
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return AppConfig()

    def save_config(self):
        """保存配置到文件"""
        try:
            # 加密密码
            encrypted_pwd = ""
            if self.config.mail.sender_password:
                encrypted_pwd = "ENC:" + \
                    _simple_encrypt(self.config.mail.sender_password)

            data = {
                "refresh_interval": self.config.refresh_interval,
                "alert_cooldown_seconds": self.config.alert_cooldown_seconds,   # 新增
                "window_x": self.config.window_x,          # 新增
                "window_y": self.config.window_y,          # 新增
                "alerts": {
                    bank: {
                        "enabled": cfg.enabled,
                        "upper": cfg.upper,
                        "lower": cfg.lower,
                        "last_alert_upper": cfg.last_alert_upper,
                        "last_alert_lower": cfg.last_alert_lower
                    } for bank, cfg in self.config.alerts.items()
                },
                "mail": {
                    "enabled": self.config.mail.enabled,
                    "smtp_server": self.config.mail.smtp_server,
                    "smtp_port": self.config.mail.smtp_port,
                    "sender_email": self.config.mail.sender_email,
                    "sender_password": encrypted_pwd,
                    "receiver_email": self.config.mail.receiver_email,
                    "subject_prefix": self.config.mail.subject_prefix
                }
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    # ---------- 网络请求（带重试） ----------
    def fetch_single(self, url: str, source_name: str, retries=2) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        for attempt in range(retries + 1):
            try:
                response = requests.get(url, headers=headers, timeout=5)
                response.raise_for_status()
                data = response.json()
                if DEBUG:
                    logger.debug(
                        f"{source_name} 原始响应: {json.dumps(data, indent=2, ensure_ascii=False)}")

                result = data.get('resultData', {})
                datas = result.get('datas', {})
                price_str = datas.get('price')
                change_str = datas.get('upAndDownAmt')
                if price_str is None or change_str is None:
                    raise ValueError(f"{source_name} API 返回数据缺失必要字段")
                return float(price_str), float(change_str), None
            except Exception as e:
                logger.warning(
                    f"{source_name} 获取失败 (尝试 {attempt+1}/{retries+1}): {e}")
                if attempt == retries:
                    return None, None, str(e)
                time.sleep(1)
        return None, None, "未知错误"

    # ---------- 数据获取循环 ----------
    def fetch_loop(self):
        while True:
            if not self.is_active:
                time.sleep(self.config.refresh_interval)
                continue

            price_z, change_z, err_z = self.fetch_single(ZSH_URL, "zheshang")
            with self.lock:
                self.zsh_data = {"price": price_z,
                                 "change": change_z, "error": err_z}
                current_price = price_z
                current_err = err_z
            if current_price is not None and not current_err:
                self.check_and_alert("zheshang", current_price, time.time())

            price_m, change_m, err_m = self.fetch_single(MS_URL, "minsheng")
            with self.lock:
                self.ms_data = {"price": price_m,
                                "change": change_m, "error": err_m}
                current_price = price_m
                current_err = err_m
            if current_price is not None and not current_err:
                self.check_and_alert("minsheng", current_price, time.time())

            self.root.after(0, self.update_gui)
            time.sleep(self.config.refresh_interval)

    # ---------- 预警检查 ----------
    def check_and_alert(self, bank_key: str, price: float, current_time: float):
        cfg = self.config.alerts[bank_key]
        if not cfg.enabled:
            return
        bank_name = "浙商" if bank_key == "zheshang" else "民生"
        cooldown = self.config.alert_cooldown_seconds   # 使用配置的冷却时间

        if cfg.upper is not None and price > cfg.upper:
            if current_time - cfg.last_alert_upper > cooldown:
                cfg.last_alert_upper = current_time
                self.save_config()
                logger.info(bank_name + "当前价格: " +
                            f"{price:.2f}" + " 元/克 高于上限: " + "{:.2f}".format(cfg.upper)+"元/克")
                self.show_alert_dialog(bank_name, price, "高于上限: ", cfg.upper)

        if cfg.lower is not None and price < cfg.lower:
            if current_time - cfg.last_alert_lower > cooldown:
                cfg.last_alert_lower = current_time
                self.save_config()
                logger.info(bank_name + "当前价格: " +
                            f"{price:.2f}" + " 元/克 低于下限；" + "{:.2f}".format(cfg.upper)+"元/克")
                self.show_alert_dialog(bank_name, price, "低于下限: ", cfg.lower)

    def show_alert_dialog(self, bank_name: str, price: float, alert_type: str, threshold: float):
        msg = f"{bank_name}金价: {price:.2f} 元/克\n{alert_type} {threshold:.2f} 元/克"
        self.root.after(0, lambda: messagebox.showwarning("金价预警", msg))
        threading.Thread(target=self.send_mail_alert, args=(
            bank_name, price, alert_type, threshold), daemon=True).start()

    # ---------- 邮件发送 ----------
    def send_mail_alert(self, bank_name: str, price: float, alert_type: str, threshold: float):
        if not self.config.mail.enabled:
            return
        try:
            msg = MIMEText(f"""
                金价预警

                银行: {bank_name}
                当前价格: {price:.2f} 元/克
                触发类型: {alert_type}
                阈值: {threshold:.2f} 元/克
                时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """, "plain", "utf-8")
            msg['Subject'] = Header(
                f"{self.config.mail.subject_prefix}{bank_name}金价{alert_type}", "utf-8")
            msg['From'] = self.config.mail.sender_email
            msg['To'] = self.config.mail.receiver_email

            server = smtplib.SMTP(
                self.config.mail.smtp_server, self.config.mail.smtp_port)
            server.starttls()
            server.login(self.config.mail.sender_email,
                         self.config.mail.sender_password)
            server.sendmail(self.config.mail.sender_email, [
                            self.config.mail.receiver_email], msg.as_string())
            server.quit()
            logger.info(f"邮件预警已发送至 {self.config.mail.receiver_email}")
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")

    # ---------- 悬浮窗 ----------
    def create_floating_window(self):
        self.floating = tk.Toplevel(self.root)
        self.floating.title("金价监控")
        self.floating.overrideredirect(True)
        self.floating.attributes('-topmost', True)
        self.floating.attributes('-alpha', 0.85)

        # 设置初始位置：如果配置中有坐标，则使用，否则默认 (50, 50)
        x = self.config.window_x if self.config.window_x is not None else 50
        y = self.config.window_y if self.config.window_y is not None else 50
        self.floating.geometry(f"260x120+{x}+{y}")

        self.floating.configure(bg='#2c3e50')
        self.floating.wm_attributes('-transparentcolor', '#2c3e50')

        self.frame = tk.Frame(self.floating, bg='#2c3e50')
        self.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.zsh_label = tk.Label(self.frame, text="浙商: 等待数据", font=(
            "微软雅黑", 12), fg='#ecf0f1', bg='#2c3e50')
        self.zsh_label.pack(anchor='w', pady=2)

        self.ms_label = tk.Label(self.frame, text="民生: 等待数据", font=(
            "微软雅黑", 12), fg='#ecf0f1', bg='#2c3e50')
        self.ms_label.pack(anchor='w', pady=2)

        self.change_label = tk.Label(self.frame, text="", font=(
            "微软雅黑", 10), fg='#bdc3c7', bg='#2c3e50')
        self.change_label.pack(anchor='w', pady=2)

        self.status_label = tk.Label(self.frame, text="● 运行中", font=(
            "微软雅黑", 9), fg='#2ecc71', bg='#2c3e50')
        self.status_label.pack(anchor='w', pady=2)

        self.floating.bind('<Any-Button-1>', self.start_move)
        self.floating.bind('<Any-B1-Motion>', self.on_move)
        self.floating.config(cursor='fleur')
        self.floating.bind('<Button-3>', self.show_context_menu)
        self.context_menu = tk.Menu(self.floating, tearoff=0)
        self.context_menu.add_command(label="隐藏窗口", command=self.hide_window)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="停止刷新", command=self.stop_monitor)
        self.context_menu.add_command(
            label="继续刷新", command=self.resume_monitor)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="设置", command=self.show_settings)
        self.context_menu.add_command(label="退出", command=self.quit_app)

    def start_move(self, event):
        self.drag_x = event.x_root - self.floating.winfo_x()
        self.drag_y = event.y_root - self.floating.winfo_y()

    def on_move(self, event):
        x = event.x_root - self.drag_x
        y = event.y_root - self.drag_y
        self.config.window_x = x
        self.config.window_y = y
        self.floating.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def hide_window(self):
        self.floating.withdraw()

    def show_window(self):
        self.floating.deiconify()
        self.floating.lift()

    # ---------- 设置窗口 ----------
    def show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("550x450")
        win.attributes('-topmost', True)
        win.resizable(False, False)
        win.grab_set()

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        zsh_frame = ttk.Frame(nb)
        nb.add(zsh_frame, text="浙商金价")
        self._create_alert_ui(zsh_frame, "zheshang")

        ms_frame = ttk.Frame(nb)
        nb.add(ms_frame, text="民生金价")
        self._create_alert_ui(ms_frame, "minsheng")

        mail_frame = ttk.Frame(nb)
        nb.add(mail_frame, text="邮件通知")
        self._create_mail_ui(mail_frame)

        general_frame = ttk.Frame(nb)
        nb.add(general_frame, text="通用")
        self._create_general_ui(general_frame)

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="保存", command=lambda: self._save_all_settings(
            win)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", command=win.destroy).pack(
            side=tk.LEFT, padx=5)

    def reset_window_position(self):
        self.config.window_x = None
        self.config.window_y = None
        self.save_config()
        # 立即移动窗口到默认位置
        self.floating.geometry("+50+50")

    def _create_alert_ui(self, parent, bank_key):
        cfg = self.config.alerts[bank_key]
        bank_name = "浙商" if bank_key == "zheshang" else "民生"

        enabled_var = tk.BooleanVar(value=cfg.enabled)
        tk.Checkbutton(parent, text=f"启用{bank_name}金价预警", variable=enabled_var).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=5)

        tk.Label(parent, text="上限价格（高于此值预警）:").grid(
            row=1, column=0, sticky='e', padx=5, pady=5)
        upper_entry = tk.Entry(parent, width=15)
        upper_entry.insert(0, str(cfg.upper) if cfg.upper is not None else "")
        upper_entry.grid(row=1, column=1, sticky='w', padx=5)

        tk.Label(parent, text="下限价格（低于此值预警）:").grid(
            row=2, column=0, sticky='e', padx=5, pady=5)
        lower_entry = tk.Entry(parent, width=15)
        lower_entry.insert(0, str(cfg.lower) if cfg.lower is not None else "")
        lower_entry.grid(row=2, column=1, sticky='w', padx=5)

        parent.enabled_var = enabled_var
        parent.upper_entry = upper_entry
        parent.lower_entry = lower_entry

    def _create_mail_ui(self, parent):
        mail_cfg = self.config.mail
        self.mail_enabled_var = tk.BooleanVar(value=mail_cfg.enabled)
        tk.Checkbutton(parent, text="启用邮件预警", variable=self.mail_enabled_var).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=5)

        tk.Label(parent, text="SMTP服务器:").grid(
            row=1, column=0, sticky='e', padx=5, pady=5)
        self.smtp_server_entry = tk.Entry(parent, width=30)
        self.smtp_server_entry.insert(0, mail_cfg.smtp_server)
        self.smtp_server_entry.grid(row=1, column=1, sticky='w', padx=5)

        tk.Label(parent, text="端口:").grid(
            row=2, column=0, sticky='e', padx=5, pady=5)
        self.smtp_port_entry = tk.Entry(parent, width=10)
        self.smtp_port_entry.insert(0, str(mail_cfg.smtp_port))
        self.smtp_port_entry.grid(row=2, column=1, sticky='w', padx=5)

        tk.Label(parent, text="发件邮箱:").grid(
            row=3, column=0, sticky='e', padx=5, pady=5)
        self.sender_email_entry = tk.Entry(parent, width=30)
        self.sender_email_entry.insert(0, mail_cfg.sender_email)
        self.sender_email_entry.grid(row=3, column=1, sticky='w', padx=5)

        tk.Label(parent, text="授权码:").grid(
            row=4, column=0, sticky='e', padx=5, pady=5)
        self.sender_pwd_entry = tk.Entry(parent, width=30, show="*")
        self.sender_pwd_entry.insert(0, mail_cfg.sender_password)
        self.sender_pwd_entry.grid(row=4, column=1, sticky='w', padx=5)

        tk.Label(parent, text="收件邮箱:").grid(
            row=5, column=0, sticky='e', padx=5, pady=5)
        self.receiver_email_entry = tk.Entry(parent, width=30)
        self.receiver_email_entry.insert(0, mail_cfg.receiver_email)
        self.receiver_email_entry.grid(row=5, column=1, sticky='w', padx=5)

        tk.Label(parent, text="邮件主题前缀:").grid(
            row=6, column=0, sticky='e', padx=5, pady=5)
        self.subject_prefix_entry = tk.Entry(parent, width=30)
        self.subject_prefix_entry.insert(0, mail_cfg.subject_prefix)
        self.subject_prefix_entry.grid(row=6, column=1, sticky='w', padx=5)

    def _create_general_ui(self, parent):
        tk.Label(parent, text="刷新间隔 (秒):").grid(
            row=0, column=0, sticky='e', padx=5, pady=5)
        self.refresh_interval_entry = tk.Entry(parent, width=10)
        self.refresh_interval_entry.insert(
            0, str(self.config.refresh_interval))
        self.refresh_interval_entry.grid(row=0, column=1, sticky='w', padx=5)
        tk.Button(parent, text="重置窗口位置", command=self.reset_window_position).grid(
            row=2, column=0, columnspan=2, pady=5)

        # 新增冷却时间输入框
        tk.Label(parent, text="预警冷却时间 (秒):").grid(
            row=1, column=0, sticky='e', padx=5, pady=5)
        self.cooldown_seconds_entry = tk.Entry(parent, width=10)
        self.cooldown_seconds_entry.insert(
            0, str(self.config.alert_cooldown_seconds))
        self.cooldown_seconds_entry.grid(row=1, column=1, sticky='w', padx=5)

    def _save_all_settings(self, win):
        # 保存预警
        for tab_name, bank_key in [("zheshang", "zheshang"), ("minsheng", "minsheng")]:
            frame = None
            for child in win.winfo_children():
                if isinstance(child, ttk.Notebook):
                    for tab_id in range(child.index("end")):
                        tab = child.nametowidget(child.tabs()[tab_id])
                        if child.tab(tab_id, "text") == ("浙商金价" if bank_key == "zheshang" else "民生金价"):
                            frame = tab
                            break
            if frame:
                cfg = self.config.alerts[bank_key]
                cfg.enabled = frame.enabled_var.get()
                upper_str = frame.upper_entry.get().strip()
                cfg.upper = float(upper_str) if upper_str else None
                lower_str = frame.lower_entry.get().strip()
                cfg.lower = float(lower_str) if lower_str else None

        # 保存邮件
        self.config.mail.enabled = self.mail_enabled_var.get()
        self.config.mail.smtp_server = self.smtp_server_entry.get().strip()
        self.config.mail.smtp_port = int(self.smtp_port_entry.get().strip())
        self.config.mail.sender_email = self.sender_email_entry.get().strip()
        self.config.mail.sender_password = self.sender_pwd_entry.get().strip()  # 明文，保存时会加密
        self.config.mail.receiver_email = self.receiver_email_entry.get().strip()
        self.config.mail.subject_prefix = self.subject_prefix_entry.get().strip()

        # 保存刷新间隔
        interval_str = self.refresh_interval_entry.get().strip()
        try:
            self.config.refresh_interval = max(1, int(interval_str))
        except ValueError:
            self.config.refresh_interval = DEFAULT_REFRESH_INTERVAL

        # 保存冷却时间
        cooldown_str = self.cooldown_seconds_entry.get().strip()
        try:
            self.config.alert_cooldown_seconds = max(1, int(cooldown_str))
        except ValueError:
            self.config.alert_cooldown_seconds = ALERT_COOLDOWN_SECONDS

        self.save_config()
        win.destroy()
        logger.info("设置已保存")

    # ---------- 更新 GUI ----------
    def update_gui(self):
        with self.lock:
            zsh = self.zsh_data
            ms = self.ms_data

        if zsh["error"]:
            zsh_text = f"浙商: 错误"
        elif zsh["price"] is not None:
            zsh_text = f"浙商: {zsh['price']:.2f} 元/克"
        else:
            zsh_text = "浙商: 等待数据"

        if ms["error"]:
            ms_text = f"民生: 错误"
        elif ms["price"] is not None:
            ms_text = f"民生: {ms['price']:.2f} 元/克"
        else:
            ms_text = "民生: 等待数据"

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

    # ---------- 控制方法 ----------
    def stop_monitor(self):
        self.is_active = False
        self.root.after(0, self.update_gui)
        logger.info("监控已暂停")

    def resume_monitor(self):
        self.is_active = True
        self.root.after(0, self.update_gui)
        logger.info("监控已恢复")
    # ---------- 系统托盘 ----------

    def setup_tray(self):
        if not PYSTRAY_AVAILABLE:
            logger.warning("pystray 未安装，系统托盘功能不可用")
            return
        self.tray_icon = self.create_tray_icon()
        threading.Thread(target=self.tray_icon.run_detached,
                         daemon=True).start()
        self.root.after(100, self.update_tray_tooltip)

    def create_tray_icon(self):
        icon_path = resource_path("icons\\gold_icon.ico")
        try:
            image = Image.open(icon_path)
            # 统一缩放到 64x64（可选）
            image = image.resize((64, 64), Image.Resampling.LANCZOS)
        except FileNotFoundError:
            # 如果图片加载失败，回退到原来的绘制方式
            logger.warning("icon加载失败")
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
            pystray.MenuItem("设置", self.show_settings),
            pystray.MenuItem("退出", self.quit_app)
        )
        return pystray.Icon("gold_monitor", image, "金价监控", menu)

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

    # ---------- 退出 ----------
    def quit_app(self, item=None):
        self.save_config()
        logger.info("程序退出")
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
