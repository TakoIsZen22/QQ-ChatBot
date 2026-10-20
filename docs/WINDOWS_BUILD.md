# Windows 绿色包构建与依赖来源

普通使用者阅读 GETTING_STARTED.md，不需要执行构建。

1.00.01（仅自有 API）与 1.00.02（API + 可选 Magpie）从主源码一次构建，命令如下；版本区别、迁移与回滚见 EDITIONS.md。每个版本分别产生 Windows 与源码 ZIP 及 SHA256。主源码版本须为 1.00.02，1.00.01 专属源码可单独构建自身。

```powershell
python tools/build-editions.py --sevenzip 'C:\Program Files\7-Zip\7z.exe'
```

## 构建机

Windows x64、Python 3.11/3.13、pip、7-Zip 完整版、系统 .NET Framework C# 编译器，Visual Studio Build Tools 的 C++ x64 工具链与 Windows SDK。新建干净的源码目录，在项目根执行：

```powershell
python tools/build-windows.py --sevenzip 'C:\Program Files\7-Zip\7z.exe'
python tools/package-release.py
```

前者从 package_release 的隐私白名单产生干净源码，再下载固定 CPython embeddable x64、跨版本安装锁定的 Windows cp313 wheels、复制独立 7-Zip 并编译窗口启动器和原创 QQ NativeHost；VS/SDK 由 vswhere 与注册表定位，C++ 使用 /MT，不复制构建机运行数据。不会复制本机 `.venv`、账号、登录态、环境变量或运行数据。

输出 `dist/qq-chatbot-版本-windows-x64.zip` 与 `.sha256`。后者输出独立源码 ZIP。构建中间目录为 `.runtime/builds/qq-chatbot-版本-windows-x64`；重复构建同一版本时先保留并移动旧中间目录和旧 ZIP 到明确的归档目录，不覆盖、也不递归清理工作目录。下载缓存 `.runtime/public-downloads` 可复用。

## 运行机制

`QQ ChatBot.exe` 是 .NET Framework 窗口启动器，只接受预设开关，以绝对路径启动 `_runtime/pythonw.exe -m src.desktop`。CPython `_pth` 固定到内置标准库、vendored site-packages 和本安装根；不依赖系统 PATH 或 Python。GUI、核心、QQ启动、备份恢复复用同一私有运行时；源码运行仍使用原来的独立虚拟环境。

运行时不包含QQ或登录态。向导只可选下载官方独立QQ并校验SHA256，不运行系统安装器、不复用个人QQ。自写宿主与适配层随程序提供，用户显式扫码，本机主人文字收发已通过；其他安装与群消息另行验收；网关仅绑定127.0.0.1:3002。

系统 WebView2、.NET Framework、VC/UCRT 需可用，绿色包不会静默安装系统组件。缺失时向导教程指向微软官方入口。Windows10/11 x64 是目标平台；不同干净机器的冷启动、手机扫码与设备验证仍需独立验收。

## 来源与许可

`config/runtime-downloads.json` 集中记录固定版本、官方下载 URL、SHA256、体积和解压限制。升级组件必须同步修改并重新验证，不能改成不校验的 latest 下载。

- CPython 3.13.16：[Python 官方发布页](https://www.python.org/downloads/release/python-31316/)，包内 `_runtime/LICENSE.txt` 保留 PSF/第三方许可。[官方 embeddable 说明](https://docs.python.org/3.13/using/windows.html#the-embeddable-package)。
- Python 依赖：`requirements.windows.lock.txt` 是合并锁文件，wheel 自带 dist-info/许可证保留。纯 Python 的 proxy_tools 在构建机从固定版本生成 wheel，用户端不运行 pip。
- 7-Zip 26.04：[官方发布](https://github.com/ip7z/7zip/releases/tag/26.04)。包内 `_tools/7zip/License.txt` 保留许可（LGPL、BSD 及 unRAR 限制）；未修改二进制，[对应源码](https://github.com/ip7z/7zip/releases/download/26.04/7z2604-src.7z) 可获得。仅捆绑解压所需7z.exe/7z.dll和许可。

## GitHub Actions

将**干净源码包的内容**放到仓库根，包含 `.github/workflows/windows-release.yml`。在 Actions 允许工作流运行，选择 Windows portable release → Run workflow，下载产物；其中 ZIP 才是给用户的包。

发布 Releases 时主源码标签为 `v1.00.02`（与 src/version.py 一致），一次提供两个版本的四个 ZIP。release published 事件会针对该标签构建，通过测试后用仓库自己的短期 GITHUB_TOKEN 上传发布资产，不需硬编码个人 token。构建失败不会上传半成品。发布说明应指向 EDITIONS.md 与 GETTING_STARTED.md，并清楚区分 Windows 包与源码包。

本工作流已写入源码；是否在你的 GitHub 仓库成功运行，需要实际上传后观察 Actions。此地不声称远端流水线已通过。
- QQ客户端固定版本、URL与SHA256见config/runtime-downloads.json，仅供研发准备，不表示原生桥接已验收。

自写宿主单独构建：`python tools/build-native-host.py`。固定版本与哈希在 config/qq-native-compat.json；更改 QQ 需重新验证导出/ABI和真实收发。官方QQ原生库不受项目MIT重新授权，也不放进发布包。
