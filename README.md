# StarFate 入群欢迎

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.0.0-blue)](https://astrbot.app)

一个为 AstrBot 设计的入群欢迎插件，支持 Markdown 渲染、多套欢迎语、本地/网络背景图、@ 提醒。

---

## 效果预览

入群后自动发送 @ 消息和欢迎图片。

---

## 特性

- Markdown 自由排版 - 使用 Markdown 语法编写欢迎内容
- 多套欢迎语 - 可创建多套独立欢迎语，通过绑定群号切换
- @ 提醒 - 入群自动 @ 新成员，文字可自定义
- 背景图片 - 支持本地文件（自动转 Base64）和网络 URL，可叠加半透明遮罩
- 三级回退 - 本地优先 → URL 其次 → 纯色背景兜底
- 背景图内含文字 - 如背景图已包含所有内容，可将 Markdown 留空
- 缓存渲染 - 配置未变时复用图片，秒级响应
- 完全可配置 - 颜色、字号、缩放、内边距等全部在 WebUI 配置
- 热重载 - /sfwelcome_reload 刷新配置，无需重启
- 调试模式 - 开启后输出详细日志

---

## 安装

### 方法一：Git 克隆

cd /path/to/AstrBot/data/plugins/
git clone https://github.com/StarFateYHJM/astrbot_plugin_starfate_welcome.git

### 方法二：WebUI 上传

1. 下载插件压缩包
2. 在 AstrBot WebUI 中进入「插件管理」
3. 点击「上传插件」，选择压缩包上传

---

## 命令

| 命令 | 权限 | 说明 |
|------|------|------|
| /sfwelcome_list | 所有人 | 列出所有可用欢迎语和群绑定 |
| /sfwelcome_test [id] | 管理员 | 测试指定欢迎语 |
| /sfwelcome_bind <群号> <id> | 管理员 | 绑定群与欢迎语 |
| /sfwelcome_unbind <群号> | 管理员 | 解绑群 |
| /sfwelcome_reload | 管理员 | 热重载配置 |

---

## Markdown 变量

在欢迎语的 content 字段中，可以使用以下变量，入群时自动替换：

| 变量 | 替换为 |
|------|--------|
| {user_id} | 新成员 QQ 号 |
| {user_name} | 新成员昵称 |
| {group_id} | 群号 |
| {group_name} | 群名称 |
| {at_user} | @新成员 |

---

## 背景图使用

### 本地图片（推荐）

1. 将图片放入 backgrounds 目录：
   - Windows: C:\Users\用户名\.astrbot\data\plugin_data\astrbot_plugin_starfate_welcome\backgrounds\
   - Linux/macOS: ~/.astrbot/data/plugin_data/astrbot_plugin_starfate_welcome/backgrounds/
   - Docker: 宿主机映射目录下的 plugin_data/astrbot_plugin_starfate_welcome/backgrounds/

2. 在 WebUI 的 background_image 中填入文件名（如 my_bg.png）

3. 保存配置，发送 /sfwelcome_reload

### 网络图片

在 background_image 中直接填入图片 URL（如 https://example.com/bg.png）

### 纯色背景

将 background_image 留空，使用 background_color 配置纯色

### 背景图内含文字

如果背景图本身已包含所有文字，将 content 字段留空即可。

---

## 配置示例

### Markdown 内容（content 字段）

# 欢迎 {user_name} 加入本群！

## 群规

- 禁止广告
- 禁止刷屏
- 文明聊天

## 功能菜单

| 功能 | 命令 | 描述 |
|------|------|------|
| 协议签订 | /协议 | 查看并签署用户协议 |
| 签到 | /sign | 每日签到领积分 |

---
发送 /menu 查看所有功能

### 主要样式配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| css_zoom | 2.0 | CSS 缩放倍数（1.0-4.0） |
| background_color | #1A1A2E | 背景色 |
| background_image | (空) | 本地文件名或 URL |
| background_overlay | true | 是否叠加遮罩 |
| overlay_opacity | 0.5 | 遮罩透明度 |
| text_color | #FFFFFF | 正文颜色 |
| base_font_size | 16px | 基础字号 |
| padding_body | 40px 50px | 页面内边距 |
| at_text | " 欢迎入群！" | @ 后显示的文字 |

---

## 常见问题

### 本地图片不显示？

1. 确认文件在正确的 backgrounds 目录中
2. 确认文件名填写正确（含后缀名）
3. 开启 debug_mode，查看日志错误
4. Docker 用户确认文件在容器内可访问

### 图片渲染失败？

- T2I 服务偶发 502 错误，插件会自动重试
- 如图片过大（>10MB），可能导致超时，建议压缩到 2MB 以内
- 可在 AstrBot 配置中将 t2i_strategy 改为 local 使用本地渲染

### {user_name} 显示 QQ 号？

- 部分 QQ 协议端不上报昵称，此时会显示 QQ 号，属于正常现象

---

## 技术说明

| 项目 | 说明 |
|------|------|
| 本地图片处理 | 自动转为 Base64 嵌入 HTML，无需网络请求 |
| 图片尺寸限制 | 最大显示 2000x2000 像素，超出自动等比缩小 |
| 缓存机制 | 配置哈希，未变时直接返回缓存图片 |
| 依赖 | 无额外 Python 依赖，仅使用 AstrBot 内置库 |

---

## 作者

YHJM

---

## 许可证

MIT License - 可自由使用、修改、分发。
