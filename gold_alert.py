"""
金价实时监控（双源版）- 修复涨跌幅字符串比较错误
version: 2.3
"""

import requests
import tkinter as tk
import threading
import time
import json

# 默认配置
ZSH_URL = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"
MS_URL = "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice"
DEFAULT_REFRESH_INTERVAL = 1  # 秒
DEBUG = False  # 调试开关，设为 True 可打印原始响应


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

        self.setup_gui()
        self.fetch_thread = threading.Thread(
            target=self.fetch_loop, daemon=True)
        self.fetch_thread.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_gui(self):
        self.root.title("金价实时监控 - 浙商 & 民生")
        self.root.attributes('-topmost', True)

        # 浙商板块
        tk.Label(self.root, text="【浙商金价】", font=(
            "Arial", 12, "bold")).pack(pady=(10, 0))
        self.zsh_price_label = tk.Label(
            self.root, text="等待数据...", font=("Arial", 14))
        self.zsh_price_label.pack(pady=2)
        self.zsh_change_label = tk.Label(
            self.root, text="", font=("Arial", 12))
        self.zsh_change_label.pack(pady=2)

        # 民生板块
        tk.Label(self.root, text="【民生金价】", font=(
            "Arial", 12, "bold")).pack(pady=(10, 0))
        self.ms_price_label = tk.Label(
            self.root, text="等待数据...", font=("Arial", 14))
        self.ms_price_label.pack(pady=2)
        self.ms_change_label = tk.Label(self.root, text="", font=("Arial", 12))
        self.ms_change_label.pack(pady=2)

        # 状态栏和按钮
        self.status_label = tk.Label(
            self.root, text="状态: 运行中", font=("Arial", 10), fg="green")
        self.status_label.pack(pady=10)

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)

        self.stop_button = tk.Button(
            button_frame, text="停止刷新", command=self.stop_monitor)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.resume_button = tk.Button(
            button_frame, text="继续刷新", command=self.resume_monitor, state=tk.NORMAL)
        self.resume_button.pack(side=tk.LEFT, padx=5)

    def fetch_single(self, url, source_name):
        """获取单个 API 数据，返回 (price, change, error_msg)"""
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

            # 两个 API 结构相同，统一解析
            result = data.get('resultData', {})
            datas = result.get('datas', {})
            price_str = datas.get('price')
            change_str = datas.get('upAndDownAmt')

            if price_str is None or change_str is None:
                raise ValueError(f"{source_name} API 返回数据缺失必要字段")

            # 转换为浮点数以便比较和显示
            price = float(price_str)
            change = float(change_str)
            return price, change, None

        except requests.exceptions.Timeout:
            return None, None, "请求超时"
        except requests.exceptions.ConnectionError:
            return None, None, "网络连接失败"
        except requests.exceptions.HTTPError as e:
            return None, None, f"HTTP {e.response.status_code}"
        except requests.exceptions.RequestException as e:
            return None, None, f"请求异常: {str(e)}"
        except ValueError as e:
            return None, None, f"数据解析失败: {str(e)}"
        except Exception as e:
            return None, None, f"未知错误: {str(e)}"

    def fetch_loop(self):
        while True:
            if not self.is_active:
                time.sleep(self.interval)
                continue

            # 获取浙商数据
            price_z, change_z, err_z = self.fetch_single(
                self.zsh_url, "zheshang")
            with self.lock:
                self.zsh_data = {"price": price_z,
                                 "change": change_z, "error": err_z}

            # 获取民生数据
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

        # 更新浙商
        if zsh["error"]:
            self.zsh_price_label.config(text="获取失败")
            self.zsh_change_label.config(text="")
        elif zsh["price"] is not None:
            # 显示价格（保留两位小数）
            self.zsh_price_label.config(text=f"{zsh['price']:.2f} 元/克")
            # 显示涨跌额，正数带加号
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

        # 更新民生
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

        # 更新状态栏
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

    def on_closing(self):
        self.is_active = False
        self.root.destroy()


def main():
    root = tk.Tk()
    monitor = GoldPriceMonitor(
        root, ZSH_URL, MS_URL, interval=DEFAULT_REFRESH_INTERVAL)
    root.mainloop()


if __name__ == "__main__":
    main()
