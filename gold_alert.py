"""
浙商金价实时监控
version: 2.0
API: https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816
功能：实时获取金价并显示在置顶窗口，可自定义刷新间隔
"""

import requests
import tkinter as tk
from tkinter import messagebox
import threading
import time

# 默认配置
DEFAULT_URL = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"
DEFAULT_REFRESH_INTERVAL = 1  # 秒


class GoldPriceMonitor:
    def __init__(self, root, url=DEFAULT_URL, interval=DEFAULT_REFRESH_INTERVAL):
        self.root = root
        self.url = url
        self.interval = interval
        self.running = True
        self.lock = threading.Lock()  # 保护数据一致性

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
        self.root.title("浙商金价实时监控")
        self.root.attributes('-topmost', True)  # 窗口置顶

        self.price_label = tk.Label(
            self.root, text="等待数据...", font=("Arial", 16))
        self.price_label.pack(pady=10)

        self.change_label = tk.Label(self.root, text="", font=("Arial", 14))
        self.change_label.pack(pady=5)

        self.status_label = tk.Label(
            self.root, text="状态: 运行中", font=("Arial", 10), fg="green")
        self.status_label.pack(pady=5)

        # 可选的停止按钮（便于手动停止）
        self.stop_button = tk.Button(
            self.root, text="停止刷新", command=self.stop_monitor)
        self.stop_button.pack(pady=5)

    def fetch_data(self):
        """发送请求并解析数据"""
        try:
            # 设置超时时间，避免长时间阻塞
            response = requests.get(self.url, timeout=5)
            response.raise_for_status()
            data = response.json()

            # 安全提取数据，避免 KeyError
            result_data = data.get('resultData', {})
            datas = result_data.get('datas', {})
            price = datas.get('price')
            up_and_down_amt = datas.get('upAndDownAmt')

            if price is None or up_and_down_amt is None:
                raise ValueError("API 返回数据缺失必要字段")

            return price, up_and_down_amt

        except requests.exceptions.Timeout:
            return None, "请求超时"
        except requests.exceptions.ConnectionError:
            return None, "网络连接失败"
        except requests.exceptions.HTTPError as e:
            return None, f"HTTP 错误: {e.response.status_code}"
        except requests.exceptions.RequestException as e:
            return None, f"请求异常: {str(e)}"
        except ValueError as e:
            return None, f"数据解析失败: {str(e)}"
        except Exception as e:
            return None, f"未知错误: {str(e)}"

    def fetch_loop(self):
        """后台循环获取数据，通过 after 方法安全更新 GUI"""
        while self.running:
            price, change = self.fetch_data()

            # 使用 after 将 GUI 更新操作调度到主线程
            self.root.after(0, self.update_gui, price, change)

            # 等待下一次刷新
            time.sleep(self.interval)

    def update_gui(self, price, change):
        """在主线程中更新界面"""
        if price is None:
            # 出错时显示错误信息
            self.price_label.config(text="获取失败")
            self.change_label.config(text="")
            self.status_label.config(text=f"状态: 错误 - {change}", fg="red")
        else:
            # 成功获取数据
            self.price_label.config(text=f"浙商金价: {price} 元/克")
            # 涨跌幅可自定义格式，如显示正负号
            sign = "+" if change >= 0 else ""
            self.change_label.config(text=f"涨跌额: {sign}{change} 元/克")
            self.status_label.config(text="状态: 运行中", fg="green")

    def stop_monitor(self):
        """停止后台刷新线程"""
        self.running = False
        self.status_label.config(text="状态: 已停止", fg="orange")
        # 可选：禁用停止按钮
        self.stop_button.config(state=tk.DISABLED)

    def on_closing(self):
        """窗口关闭时的清理工作"""
        self.running = False
        self.root.destroy()


def main():
    # 创建主窗口
    root = tk.Tk()

    # 可选：从命令行参数或配置文件读取 URL 和间隔
    # 此处使用默认值
    monitor = GoldPriceMonitor(
        root, url=DEFAULT_URL, interval=DEFAULT_REFRESH_INTERVAL)

    root.mainloop()


if __name__ == "__main__":
    main()
