"""
金价实时监控（双源版）
version: 2.1
API:
    浙商: https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816
    民生: https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice
"""

import requests
import tkinter as tk
import threading
import time

# 默认配置
ZSH_URL = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"
MS_URL = "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice"
DEFAULT_REFRESH_INTERVAL = 1  # 秒


class GoldPriceMonitor:
    def __init__(self, root, zsh_url=ZSH_URL, ms_url=MS_URL, interval=DEFAULT_REFRESH_INTERVAL):
        self.root = root
        self.zsh_url = zsh_url
        self.ms_url = ms_url
        self.interval = interval
        self.is_active = True          # 是否继续刷新
        self.lock = threading.Lock()   # 保护数据一致性

        # 存储最新数据（用于GUI更新）
        self.zsh_data = {"price": None, "change": None, "error": None}
        self.ms_data = {"price": None, "change": None, "error": None}

        # 创建 GUI 组件
        self.setup_gui()

        # 启动后台数据获取线程
        self.fetch_thread = threading.Thread(
            target=self.fetch_loop, daemon=True)
        self.fetch_thread.start()

        # 窗口关闭时停止循环
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_gui(self):
        """初始化 GUI 布局"""
        self.root.title("金价实时监控 - 浙商 & 民生")
        self.root.attributes('-topmost', True)  # 窗口置顶

        # 浙商板块
        self.zsh_title = tk.Label(
            self.root, text="【浙商金价】", font=("Arial", 12, "bold"))
        self.zsh_title.pack(pady=(10, 0))
        self.zsh_price_label = tk.Label(
            self.root, text="等待数据...", font=("Arial", 14))
        self.zsh_price_label.pack(pady=2)
        self.zsh_change_label = tk.Label(
            self.root, text="", font=("Arial", 12))
        self.zsh_change_label.pack(pady=2)

        # 民生板块
        self.ms_title = tk.Label(
            self.root, text="【民生金价】", font=("Arial", 12, "bold"))
        self.ms_title.pack(pady=(10, 0))
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
        """
        获取单个 API 数据
        返回 (price, change, error_msg)
        """
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            # 不同 API 数据结构可能不同，分别解析
            if source_name == "zheshang":
                # 浙商 API 结构: resultData.datas.price / upAndDownAmt
                result = data.get('resultData', {})
                datas = result.get('datas', {})
                price = datas.get('price')
                change = datas.get('upAndDownAmt')
                if price is None or change is None:
                    raise ValueError("浙商 API 返回数据缺失必要字段")
                return price, change, None
            elif source_name == "minsheng":
                # 民生 API 结构（与原代码一致）: resultData.datas.price / upAndDownAmt
                # 如果结构相同，复用；若有差异可在此扩展
                result = data.get('resultData', {})
                datas = result.get('datas', {})
                price = datas.get('price')
                change = datas.get('upAndDownAmt')
                if price is None or change is None:
                    raise ValueError("民生 API 返回数据缺失必要字段")
                return price, change, None
            else:
                raise ValueError(f"未知数据源: {source_name}")

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
        """后台循环获取数据，通过 after 方法安全更新 GUI"""
        while True:
            # 如果未激活，只睡眠，不获取数据
            if not self.is_active:
                time.sleep(self.interval)
                continue

            # 获取浙商数据
            price_z, change_z, err_z = self.fetch_single(
                self.zsh_url, "zheshang")
            with self.lock:
                if err_z:
                    self.zsh_data = {"price": None,
                                     "change": None, "error": err_z}
                else:
                    self.zsh_data = {"price": price_z,
                                     "change": change_z, "error": None}

            # 获取民生数据
            price_m, change_m, err_m = self.fetch_single(
                self.ms_url, "minsheng")
            with self.lock:
                if err_m:
                    self.ms_data = {"price": None,
                                    "change": None, "error": err_m}
                else:
                    self.ms_data = {"price": price_m,
                                    "change": change_m, "error": None}

            # 使用 after 将 GUI 更新操作调度到主线程
            self.root.after(0, self.update_gui)

            # 等待下一次刷新
            time.sleep(self.interval)

    def update_gui(self):
        """在主线程中更新界面"""
        with self.lock:
            zsh = self.zsh_data
            ms = self.ms_data

        # 更新浙商显示
        if zsh["error"]:
            self.zsh_price_label.config(text="获取失败")
            self.zsh_change_label.config(text="")
            # 可将错误信息显示在状态栏，但状态栏整体展示，暂时不单独显示
        else:
            self.zsh_price_label.config(text=f"{zsh['price']} 元/克")
            sign = "+" if zsh["change"] >= 0 else ""
            self.zsh_change_label.config(
                text=f"涨跌额: {sign}{zsh['change']} 元/克")

        # 更新民生显示
        if ms["error"]:
            self.ms_price_label.config(text="获取失败")
            self.ms_change_label.config(text="")
        else:
            self.ms_price_label.config(text=f"{ms['price']} 元/克")
            sign = "+" if ms["change"] >= 0 else ""
            self.ms_change_label.config(text=f"涨跌额: {sign}{ms['change']} 元/克")

        # 更新状态栏（显示是否激活，以及是否有错误）
        if self.is_active:
            # 检查是否有任何错误
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
        """暂停刷新"""
        self.is_active = False
        self.stop_button.config(state=tk.DISABLED)
        self.resume_button.config(state=tk.NORMAL)
        # 立即更新状态栏
        self.root.after(0, self.update_gui)

    def resume_monitor(self):
        """恢复刷新"""
        self.is_active = True
        self.stop_button.config(state=tk.NORMAL)
        self.resume_button.config(state=tk.DISABLED)
        # 立即更新状态栏
        self.root.after(0, self.update_gui)

    def on_closing(self):
        """窗口关闭时的清理工作"""
        self.is_active = False
        self.root.destroy()


def main():
    root = tk.Tk()
    # 可根据需要修改 URL 和刷新间隔
    monitor = GoldPriceMonitor(
        root, ZSH_URL, MS_URL, interval=DEFAULT_REFRESH_INTERVAL)
    root.mainloop()


if __name__ == "__main__":
    main()
