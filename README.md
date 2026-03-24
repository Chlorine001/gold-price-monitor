# 金价实时监控工具 💰

[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2FmacOS%2FLinux-lightgrey.svg)]()

一个基于 Python 的实时金价监控工具，支持悬浮窗显示、价格预警和邮件通知功能。可监控**浙商银行**和**民生银行**的实时黄金价格。

---

## ✨ 功能特性

- 📊 **实时价格监控** - 每 1 秒自动刷新浙商、民生金价
- 🖥️ **悬浮窗显示** - 置顶透明悬浮窗，实时查看价格
- 🔔 **价格预警** - 支持设置上下限价格，触发时弹窗提醒
- 📧 **邮件通知** - 预警触发时自动发送邮件通知
- 🎨 **系统托盘** - 最小化到系统托盘，托盘图标实时显示价格
- 🖱️ **可拖拽窗口** - 悬浮窗支持自由拖拽定位
- 💾 **配置持久化** - 预警设置自动保存到本地文件
- 🌙 **后台运行** - 关闭窗口后仍可在托盘后台运行

---

## 📦 安装依赖

### 环境要求
- Python 3.6 或更高版本
- Windows/macOS/Linux 操作系统

### 安装步骤

```bash
# 1. 克隆或下载本仓库
git clone https://github.com/yourusername/gold-price-monitor.git
cd gold-price-monitor

# 2. 安装必要依赖
pip install requests pillow pystray
```

### 依赖说明

| 包名 | 版本要求 | 用途 |
|------|---------|------|
| `requests` | >=2.25.0 | 获取金价 API 数据 |
| `pillow` | >=8.0.0 | 系统托盘图标生成 |
| `pystray` | >=0.19.0 | 系统托盘功能（可选） |

> 💡 **提示**：如果不安装 `pystray`，程序仍可正常运行，但系统托盘功能将不可用。

---

## 🚀 使用方法

### 快速启动

```bash
python gold_monitor.py
```

### 程序启动后

1. **悬浮窗**会自动显示在桌面左上角，实时展示金价
2. 程序会自动最小化到**系统托盘**（屏幕右下角）
3. 鼠标悬停在托盘图标上可查看实时价格 tooltip

---

## ⚙️ 配置说明

### 价格预警设置

1. **右键点击悬浮窗** → 选择 **"设置"**
2. 在设置窗口中选择 **"浙商金价"** 或 **"民生金价"** 选项卡
3. 勾选 **"启用预警"**
4. 设置预警参数：
   - **上限价格**：当金价高于此值时触发预警
   - **下限价格**：当金价低于此值时触发预警
5. 点击 **"保存"** 按钮保存配置

> ⚠️ **预警冷却机制**：同一类型的预警触发后，会有 **8 秒冷却时间**，避免重复弹窗打扰。

### 邮件通知设置

1. 在设置窗口中选择 **"邮件通知"** 选项卡
2. 勾选 **"启用邮件预警"**
3. 填写 SMTP 配置信息：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| SMTP服务器 | 邮箱服务器地址 | `smtp.qq.com` (QQ邮箱) |
| 端口 | SMTP 端口号 | `587` (TLS) 或 `465` (SSL) |
| 发件邮箱 | 发送预警邮件的邮箱地址 | `your_email@qq.com` |
| 授权码 | 邮箱 SMTP 授权码（非登录密码） | `abcdxyz123` |
| 收件邮箱 | 接收预警邮件的邮箱地址 | `receiver@example.com` |
| 邮件主题前缀 | 邮件标题前缀 | `【金价预警】` |

#### 常见邮箱 SMTP 设置

| 邮箱服务商 | SMTP服务器 | 端口 | 安全协议 |
|-----------|-----------|------|---------|
| QQ邮箱 | smtp.qq.com | 587 | STARTTLS |
| 163邮箱 | smtp.163.com | 25/465 | TLS/SSL |
| Gmail | smtp.gmail.com | 587 | STARTTLS |
| Outlook | smtp.office365.com | 587 | STARTTLS |

> 💡 **QQ邮箱授权码获取**：登录 QQ邮箱 → 设置 → 账户 → 开启 "SMTP服务" → 生成授权码

---

## 📁 配置文件

程序会自动在同目录下生成 `gold_alerts.json` 文件存储所有配置：

```json
{
  "zheshang": {
    "enabled": true,
    "upper": 500.0,
    "lower": 450.0,
    "last_alert_upper": 0,
    "last_alert_lower": 0
  },
  "minsheng": {
    "enabled": true,
    "upper": 500.0,
    "lower": 450.0,
    "last_alert_upper": 0,
    "last_alert_lower": 0
  },
  "mail_config": {
    "enabled": true,
    "smtp_server": "smtp.qq.com",
    "smtp_port": 587,
    "sender_email": "your_email@qq.com",
    "sender_password": "your_auth_code",
    "receiver_email": "receiver@example.com",
    "subject_prefix": "【金价预警】"
  }
}
```

> 🔒 **安全提示**：配置文件中的邮箱授权码为明文存储，请妥善保管配置文件，避免泄露。

---

## 🖥️ 界面操作指南

### 悬浮窗操作

| 操作 | 功能说明 |
|------|---------|
| 左键拖拽 | 移动悬浮窗到任意位置 |
| 右键点击 | 打开功能菜单 |

### 右键菜单功能

```
├─ 隐藏窗口        # 隐藏悬浮窗，程序仍在托盘运行
├─ 停止刷新        # 暂停数据获取（保持当前显示）
├─ 继续刷新        # 恢复数据获取
├─ 设置           # 打开预警和邮件配置窗口
└─ 退出           # 完全退出程序
```

### 系统托盘操作

| 操作 | 功能说明 |
|------|---------|
| 左键单击/双击 | 显示/隐藏悬浮窗 |
| 右键单击 | 打开托盘菜单 |
| 鼠标悬停 | 显示实时价格 tooltip |

### 托盘菜单功能

```
├─ 显示窗口        # 显示悬浮窗（默认双击也可）
├─ 隐藏窗口        # 隐藏悬浮窗
├─ 停止刷新        # 暂停数据获取（仅在运行中可用）
├─ 继续刷新        # 恢复数据获取（仅在暂停时可用）
├─ 设置           # 打开配置窗口
└─ 退出           # 完全退出程序
```

---

## 🔧 高级配置

如需修改程序默认行为，请编辑脚本开头的**配置常量**：

```python
# 数据刷新间隔（秒）
DEFAULT_REFRESH_INTERVAL = 1

# 预警冷却时间（秒），同一类型预警在此时间内不重复触发
ALERT_COOLDOWN_SECONDS = 8

# 配置文件名
CONFIG_FILE = "gold_alerts.json"

# 调试模式开关（True 时打印 API 原始响应）
DEBUG = False
```

### 修改示例

```python
# 改为每 5 秒刷新一次
DEFAULT_REFRESH_INTERVAL = 5

# 改为 30 秒预警冷却
ALERT_COOLDOWN_SECONDS = 30

# 开启调试模式查看 API 响应
DEBUG = True
```

---

## 📊 数据来源

本工具通过以下 API 获取实时金价数据：

| 银行 | API 地址 | 更新频率 |
|------|---------|---------|
| 浙商银行 | `https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816` | 实时 |
| 民生银行 | `https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice` | 实时 |

> 📌 数据来源于京东金融平台，仅供参考，投资请以官方渠道为准。

---

## ⚠️ 注意事项

### 网络要求
- 需要稳定的网络连接以获取实时数据
- 如遇数据获取失败，程序会显示 "错误" 状态，并在后台自动重试

### 防火墙/代理
- 如遇数据获取失败，请检查：
  - 网络连接是否正常
  - 是否开启了代理/VPN（可能需要关闭）
  - 防火墙是否拦截了 Python 的网络请求

### 邮箱安全
- 配置文件中的邮箱授权码为**明文存储**
- 建议：
  - 不要将配置文件上传到公共仓库
  - 使用专门的预警邮箱（非重要邮箱）
  - 定期更换邮箱授权码

### 系统兼容性
- **Windows**：完整支持所有功能（测试通过 Windows 10/11）
- **macOS**：悬浮窗和基本功能可用，托盘图标可能需要适配
- **Linux**：取决于桌面环境，部分功能可能需要额外配置

---

## 🐛 故障排查

### 常见问题与解决方案

| 问题现象 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 悬浮窗不显示 | Python 版本过低 | 升级至 Python 3.6+ |
| 数据始终显示 "等待数据" | 网络连接问题 | 检查网络，尝试关闭代理 |
| 数据获取显示 "错误" | API 地址变更或失效 | 检查 API 是否可访问，或等待修复 |
| 预警不触发 | 未启用预警或价格未达阈值 | 检查预警设置，确认价格已突破阈值 |
| 邮件发送失败 | SMTP 配置错误 | 检查服务器、端口、授权码 |
| 托盘图标不显示 | 未安装 pystray | 运行 `pip install pystray` |
| 程序崩溃退出 | 依赖缺失 | 安装所有依赖：`pip install requests pillow pystray` |

### 调试模式

如需排查问题，可开启调试模式：

1. 编辑脚本，将 `DEBUG = False` 改为 `DEBUG = True`
2. 重新运行程序
3. 查看控制台输出的 API 原始响应数据
4. 根据响应内容判断问题所在

### 获取帮助

如遇到无法解决的问题，请：
1. 开启调试模式并记录控制台输出
2. 检查 `gold_alerts.json` 配置文件格式是否正确
3. 提交 Issue 时附上错误信息和配置文件（脱敏后）

---

## 📝 更新日志

### v4.1 (当前版本)
- ✨ 新增邮件预警功能
- 🎨 优化系统托盘 tooltip 显示
- 🐛 修复配置保存相关问题
- ⚡ 优化预警冷却机制

### v4.0
- ✨ 新增价格预警功能（上下限设置）
- ✨ 新增配置持久化功能
- 🎨 优化悬浮窗 UI 设计

### v3.0
- ✨ 新增系统托盘功能
- ✨ 支持悬浮窗拖拽定位
- 🎨 添加右键菜单

### v2.0
- ✨ 新增民生银行金价监控
- ⚡ 优化数据获取逻辑

### v1.0
- 🎉 初始版本发布
- ✨ 支持浙商银行金价监控
- ✨ 基础悬浮窗显示

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 提交 Issue
- 描述清楚问题现象
- 提供复现步骤
- 附上错误日志（如有）
- 说明操作系统和 Python 版本

### 提交代码
1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m 'Add some AmazingFeature'`
4. 推送分支：`git push origin feature/AmazingFeature`
5. 提交 Pull Request

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源。

```
MIT License

Copyright (c) 2024 Gold Price Monitor Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 致谢

- 金价数据来源：[京东金融](https://jdjygold.com/)
- 图标设计：使用 Pillow 动态生成金色主题图标
- 灵感来源：黄金投资者的实时监控需求

---

## 📧 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 提交 [GitHub Issue](../../issues)
- 发送邮件至：`your_email@example.com`

---

**免责声明**：本工具仅供参考学习使用，不构成任何投资建议。金价数据来源于第三方平台，可能存在延迟或误差，投资请以官方渠道为准。使用本工具产生的任何损失，开发者不承担责任。

---

<div align="center">

💰 **Happy Gold Monitoring!** 💰
[⭐ Star 本仓库](https://github.com/Chlorine001/gold-price-monitor.git) 如果你觉得这个工具对你有帮助！

</div>
