# 🀄 majsoul-hook-mitm

[English](README.md) | [日本語](README.ja.md) | **简体中文**

雀魂流量检查与本地装扮工具。

<p>
  <a href="https://www.python.org/"><img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/Python-Dark.svg" width="32" height="32" alt="Python"></a>
  <a href="https://docs.astral.sh/uv/"><img src="https://raw.githubusercontent.com/astral-sh/uv/main/docs/assets/logo-letter.svg" width="32" height="32" alt="uv"></a>
  <a href="https://mitmproxy.org/"><img src="https://www.mitmproxy.org/logo-navbar.png" height="32" alt="mitmproxy"></a>
</p>

## ✨ 功能

- 查看 WebSocket 消息，搜索与筛选动作，对比处理前后的内容。
- 通过游戏原有界面，在本地切换角色、皮肤、称号和表情。
- 英／日／中三语 GUI，自动检测系统语言，支持 HiDPI。

## ⚠️ 免责声明

本项目非官方项目。流量拦截与本地装扮修改可能违反游戏规则，并导致账号受限或封禁。请仅在获得授权的情况下使用，妥善保护敏感数据，并在使用前阅读[免责声明](docs/disclaimer.md)。

## 🚀 快速开始

安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，在仓库根目录运行：

```powershell
uv sync --locked
uv run --locked majsoul-hook gui
```

Python 3.14 由 uv 管理。GUI 需要正常的 Tkinter 环境；Windows 捕获时可能请求管理员权限。

## 🎮 使用 GUI

1. 首次点击“更新资源”。
2. 输入游戏进程名或 PID，默认 `Jantama_MahjongSoul`。
3. 点击“开始捕获”，然后重新连接或重启游戏。
4. 选中消息查看详情，结束后点击“停止捕获”。

“本地装扮”默认启用，只读检查时取消勾选。装扮修改仅在本地可见。通过“语言”选项可切换界面语言。

## 📚 文档

[CLI 与使用说明](docs/usage.md) · [打包与 CI](docs/packaging.md) · [开发](docs/development.md) · [国际化](docs/localization.md) · [架构](docs/architecture.md) · [验证状态](docs/validation.md) · [路线图](docs/roadmap.md)

## 📄 许可证与致谢

[GPL-3.0-or-later](LICENSE)。参考 `majsoul-hook-mitm` 与 `majsoul-mirage`。图标：[Skill Icons](https://github.com/tandpfun/skill-icons)、[uv](https://github.com/astral-sh/uv)、[mitmproxy](https://mitmproxy.org/)。
