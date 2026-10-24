# majsoul-hook-mitm

[English](README.md) | [日本語](README.ja.md) | **简体中文**

使用 Python 和 mitmproxy local mode 捕获雀魂 WebSocket 流量，解析请求、响应、通知及嵌套对局行动。Tkinter 检查器展示收到、修改、接管和注入的内容。默认只读，可选启用本地装扮覆盖。

## 快速开始

安装 [uv](https://docs.astral.sh/uv/)，在仓库根目录运行：

```powershell
uv sync --locked
uv run --locked majsoul-hook gui
```

uv 管理 Python 3.12 和 `.venv`，无需手动激活。GUI 需要正常的标准库 Tkinter 支持。Windows 独立 GUI 入口是 `uv run --locked majsoul-hook-gui`。

1. 首次点击 **Update resources**，生成协议及装扮资源。
2. 输入游戏进程名或 PID，默认 `Jantama_MahjongSoul`。
3. 只读时不勾选 **Local cosmetics**，需要本地装扮修改时才勾选。
4. 点击 **Start capture**，再重新连接或重启游戏，使新连接进入捕获。结束时点击 **Stop capture**。

Windows 上 mitmproxy 的重定向组件可能请求提权，不需要 Proxinject 或手动 SOCKS/HTTP 代理。其他系统取决于 [mitmproxy local capture 的支持范围](https://docs.mitmproxy.org/stable/concepts/modes/#local-capture)。

## 检查消息

固定复选框支持多选：**Pass**（透传）、**Modified**（修改）、**Intercepted**（接管）、**Injected**（注入）、**Error**（错误）。默认全部选中；全部取消只隐藏列表，不删除历史。搜索和动作筛选不随顶部设置滚动。

选中消息查看 **Overview**（概览）、**Before**（处理前）、**Actual content**（实际内容）、**Wire bytes**（完整帧的 Base64）。接管的原请求和本地响应、通知分别显示。错误行保留原消息实际转发或阻止的状态。**Copy details** 复制选中记录。

历史保留最近 2,000 条、序列化后约 64 MiB 的记录，单条超大消息仍完整保留。界面处理不及时会丢弃并统计较旧的待显示事件，转发继续运行。GUI 不自动保存详情；完整载荷和复制内容可能包含账号信息或令牌。

Windows HiDPI 支持字体、行高、列宽和间距缩放，将完整窗口限制在显示器工作区内。小屏幕下顶部设置可滚动，键盘焦点自动进入可见区域。真实不同缩放显示器之间的拖动仍待验证。

## 资源

**Check version** 比较本地与远端索引的 SHA-256，显示生成时间和配置数量。索引变化不表示每个协议或配置表都发生变化。**Update resources** 验证后原子替换包含装扮数据的快照。资源任务与捕获互斥。

```powershell
uv run --locked majsoul-hook resources
uv run --locked majsoul-hook resources --cosmetics
uv run --locked majsoul-hook resources --offline --cosmetics
```

默认来源为 `https://game.maj-soul.com/assetbundles/DXT/`，可用 `--base-url` 指定其他可信 HTTPS 来源。输出为 `data/protocol.json`，按来源隔离的缓存位于 `.cache/bundles/`。离线重建需要对应来源的 bundle。

资源管线参考 `majsoul-mirage`：通过 `bundle_info_so.majset` 定位 Unity bundle，解码 Lua 协议与配置，生成动态 protobuf 描述和可选装扮表。使用 Python 实现，没有 JS/TS、Node.js 或 protoc 依赖。构建时执行可信客户端 Lua，该环境不是恶意资源沙箱。捕获期间不执行 Lua，也不下载资源。

## CLI 捕获

```powershell
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul
uv run --locked majsoul-hook capture --process 1234 --output captures/session.jsonl
uv run --locked majsoul-hook capture --process chrome --host maj-soul.com --verbose
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul --cosmetics
```

`--process` 选择一个进程名或 PID，浏览器可能使用独立网络进程。可重复指定 `--host` 按域名后缀筛选解析与输出，但它**不会缩小拦截范围**。原生客户端可能直接用 IP 连接。

明文 `ws://` 不需要 CA。拦截验证证书的 `wss://`，通常需要客户端信任 mitmproxy CA；程序不会自动安装证书或修改信任。日志记录 scheme、端口及两侧 TLS 状态。参见[证书说明](https://docs.mitmproxy.org/stable/concepts/certificates/)。

捕获使用独立配置和明确的 addon 集合，忽略用户 YAML 与外部脚本，排除通用修改、重放和重定向 addon。保持上游 TLS 验证。`--confdir` 仅修改证书目录，默认是 `~/.mitmproxy/`。

控制台默认只输出摘要。`--verbose` 与 `--output` 包含完整的原始解码载荷。CLI JSONL 动作为 `pass`、`modified`、`local`、`error_blocked`、`error_passthrough`，GUI 则区分接管原请求与注入消息。未知类型保留 Base64；未关联请求的响应标记为 `orphan_response`。字段名、bytes 和 64 位整数遵循 protobuf JSON 约定。

## 本地装扮

使用 `--cosmetics` 或 GUI 准备资源，开启装扮模式并重新连接后，通过游戏原有界面操作：

- 本地角色、皮肤、称号和表情列表，羁绊、结局展示，以及保留已有数量的装扮物品补全。
- 角色、皮肤、称号、加载图选择，排序、隐藏，以及含名称和启用状态的十组装扮方案。
- 房间、对局认证、账号信息、牌谱中的本人装扮覆盖，以及其他玩家的羁绊展示。
- 对局与重连保持一致的随机候选池，以及根据认证座位回显的本地表情。

设置按账号保存在 `data/cosmetics-state.json`，不含登录令牌，CLI 可用 `--state` 修改路径。同一状态文件只供一个捕获进程使用。修改不授予服务器所有权，也不会改变其他玩家看到的装扮。

已识别的本地请求失败时仍保持阻止，尽可能返回错误响应；普通流量失败则原样透传。编辑保留未修改的未知 protobuf 字段。仅向客户端注入消息，不合成服务器请求，不自动操作游戏。

## 开发与验证

```powershell
uv run --locked pytest
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
```

参见英文的[架构](docs/architecture.md)、[开发说明](docs/development.md)、[验证状态](docs/validation.md)、[路线图](docs/roadmap.md)和[协作约定](AGENTS.md)。代码、GUI 和内部文档使用英语。

合成测试覆盖本机 socket 转发、修改和注入、资源、状态和 GUI。Windows 原生客户端大厅解析已验证；完整对局、重连、WSS、实际装扮界面、不同 DPI 显示器之间的切换仍需配合实测。

缓存、生成资源、账号状态、抓包记录、临时文件、证书和私钥被忽略。归档原项目 `majsoul-hook-mitm/` 和参考项目 `majsoul-mirage/` 保持原样，不纳入追踪。

## 许可证与参考来源

[GPL-3.0-or-later](LICENSE)。协议封装与行动 XOR 参考归档原项目；Unity 定位、Lua 提取和装扮业务参考 `majsoul-mirage`，在本项目重新组织为 Python 实现。
