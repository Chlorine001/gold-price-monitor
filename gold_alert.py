'''
    浙商金价实时监控   
    version: 1.0
    提供金价数值的实时价监控
    2025年5月6日
'''
import requests
import tkinter as tk

# URL
url = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"


def fetch_data():
    try:
        # 发送 GET 请求
        response = requests.get(url)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()

        # 提取 price 和 upAndDownAmt
        price = data['resultData']['datas']['price']
        up_and_down_amt = data['resultData']['datas']['upAndDownAmt']

        # 更新 GUI
        price_label.config(text=f"Price: {price}")
        up_and_down_amt_label.config(text=f"Up and Down: {up_and_down_amt}")

    except requests.exceptions.RequestException as e:
        price_label.config(text="请求出错")
        up_and_down_amt_label.config(text="请求出错")
    except ValueError as e:
        price_label.config(text="解析 JSON 失败")
        up_and_down_amt_label.config(text="解析 JSON 失败")
    except KeyError as e:
        price_label.config(text="数据缺失")
        up_and_down_amt_label.config(text="数据缺失")

    # 每隔 1 秒钟调用一次 fetch_data 函数
    root.after(1000, fetch_data)


# 创建主窗口
root = tk.Tk()
root.title("监控")

# 设置窗口置顶
root.attributes('-topmost', True)

# 创建标签以显示价格和涨跌幅
price_label = tk.Label(root, text="Price: ", font=("Arial", 16))
price_label.pack(pady=10)

up_and_down_amt_label = tk.Label(
    root, text="Up and Down: ", font=("Arial", 16))
up_and_down_amt_label.pack(pady=10)

# 启动数据获取
fetch_data()

# 启动 GUI 主循环
root.mainloop()
