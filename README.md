# richi-console

目前仅支持 Windows 10/11 64 位系统

仅在 Python 3.10 上进行测试

## Windows 运行

1. *clone* 项目文件，安装依赖 
   
   `python install -r requirements.txt`

2. 双击 *run.bat*

3. 在浏览器访问 [mitm.it](http://mitm.it) 并按提示安装证书，之后即可在浏览器正常游戏

4. 为确保系统代理正确重置，退出请直接关闭 ***alacritty*** 窗口

## 使用 http 前置代理

- 如果你有使用代理软件，并且希望通过代理进行游戏
  
  可以修改 *bin\settings.json* 中 *UPSTREAM_PROXY* 项，留空为不使用代理
  
  *e.g.* `"UPSTREAM_PROXY": "http://localhost:2080"`

- 如果依赖下载速度不佳，可修改镜像源为[国内镜像源地址](https://mirrors.cernet.edu.cn/about)
  
  *e.g.* `pip config set global.index-url https://mirror.nju.edu.cn/pypi/web/simple`

## 特别感谢

- [Avenshy/mahjong-helper-majsoul-mitmproxy](https://github.com/Avenshy/mahjong-helper-majsoul-mitmproxy)

- [EndlessCheng/mahjong-helper](https://github.com/EndlessCheng/mahjong-helper)

- [alacritty/alacritty](https://github.com/alacritty/alacritty)