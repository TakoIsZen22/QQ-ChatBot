# 本机 QQ 与多版本兼容

2026-10-21，适用于两个 API 发行版本。本轮仅更新源码，既有 GitHub 下载包没有重建。

目标是让用户沿用自己安装的 QQ 程序版本。当前实现自动检测与按版本配置的适配机制，**没有实现任意新旧 QQ 通用**。清单目前只有 9.9.33-52230；该版本此前在原安装验证过文字登录与收发，不能代表本轮新增的本机程序复制流程或另一台电脑已完成真实验收。

## 在程序里使用

1. 退出桌面窗口，再重新打开，进入「程序设置 → 首次使用 / QQ 接入」。仅退出界面不必停止已有 QQ 接入。
2. 点击「检测本机 QQ 兼容性」。目前从 Windows 标准卸载项和常见安装目录查找 QQ；非标准安装位置暂不提供任意路径导入。检测读取程序版本元数据与关键程序文件校验，不启动系统 QQ、不枚举已登录账号。
3. 结果显示版本、安装位置与原因。只有已登记适配、版本元数据一致且关键文件 SHA256 通过的结果提供「复制此版本到独立目录」。目录可诊断不等于版本已兼容，本地登记的旧 build 门槛也不代表腾讯实时的最低登录要求。
4. 要使用检测结果时，先在程序手动停止本安装的 QQ 接入，再点击复制按钮。复制不关闭或修改日常 QQ，不复制账号、数据库、日志或登录态。已有同版本独立目录不会被覆盖，失败的临时目录会清理，现有程序和登录文件保留。
5. 复制完成后手动「扫码接入」，用机器人号重新扫码。先在暂停状态核对接收，自己决定何时开启只回复并测试发送。程序不自动恢复聊天或使用日常 QQ 的登录态。
6. 显示「尚未适配」时，使用「下载并准备 QQ 组件」准备已兼容的独立版本，不要求升级或降级日常 QQ。已有不完整目录会保留并报错，由维护者核对，不能直接覆盖。

这里的复用是复制支持的程序文件给自写宿主，不是控制日常 QQ 窗口。复制清单仅包括四个关键文件、package.json 和运行时根目录 / resources/app 直接依赖的 DLL；不递归复制系统 QQ 的用户目录或其他资源。该精简复制路径尚待在用户安装中验证扫码、文字收发；未来适配若需要更多公开资源，应明确增补程序文件清单，不能改为整目录无差别复制。

## 兼容边界

底层宿主直接使用 QQ 自带的 Node/V8、Chromium libc++ ABI 布局和原生登录/消息服务。版本号、Node ABI、wrapper 接口或登录参数变化，都可能破坏初始化。保留同名导出也不保证 C++ 布局和会话行为相同。

其他底层路线的未知版本放行策略不能作为全部版本已验证的证据。本轮没有引入外部原生二进制，也没有通过伪造版本参数绕过服务端的旧版本拒绝。

## 配置与模块

| 位置 | 用途 |
|---|---|
| config/qq-native-compat.json | v2 清单：profiles 多版本、preferred 默认选择、limits 超时 |
| src/core/native_compat.py | 清单验证、已实现宿主 ABI 映射、文件验证、独立版本选择 |
| src/core/system_qq.py、local_qq.py | 只读本机安装检测、按已适配版本复制程序文件 |
| src/core/native_host.py | 启动前校验，只加载独立目录受支持的运行时 |
| src/qq_native/compatibility.js | 复核实际 Node/V8，从清单取 appid/qua，忽略旧 host-config 参数 |
| src/core/onboarding.py、desktop_api.py | 界面检测 / 复制；服务锁、后台复制、保持暂停 |
| src/channel/ui/desktop/onboarding.js | 检测结果和复制按钮，外来文字使用 textContent |
| config/local.json 的 qq.native_version | 明确选择的版本；空字符串按 preferred、再按清单顺序选择已安装版本 |
| .runtime/qq-client/versions/版本号 | 独立运行时，不启动系统 QQ.exe |

显式选择的版本缺失或校验失败时不会退回其他版本。默认模式下首选版本文件损坏也会报错，不会静默跳过。多个已适配版本可共存，同版本多个目录则报歧义。旧 v1 清单仍可读取；旧 prepare/restore 单目录规则仅用于历史入口恢复。

新增适配需要：官方文件 → 确认 Node/V8 和 C++ 布局 → 适配登录及会话 → 核对真实 appid/qua → 登记四项哈希 → 隔离夹具 → 独立扫码、收发、掉线与账号隔离验收。同 ABI 可增加 profiles；不同 ABI 必须实现新宿主/适配器并更新映射，不能仅添加配置或复制旧登录参数。当前只有 embedded-qqnt-v1，没有第二套已实现宿主。

## 验证与回滚

源码环境从项目根运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
node --test tests/qq-native.test.js tests/desktop-status.test.js tests/qq-compat.test.js
.\.venv-desktop\Scripts\python.exe tools/smoke-onboarding.py
.\.venv\Scripts\python.exe tools/qq-native.py doctor
```

前三项使用隔离数据 / 协议或界面夹具，不发真实 QQ 消息；doctor 只读。精简复制后的实际运行、其他 QQ 版本和其他机器需单独验收，不将夹具或旧安装结果当作新版本收发已通过。

回滚前按 HANDOFF 备份数据并保持暂停，手动停止本安装 QQ，换回修改前完整可信源码（包含 config/settings.json 和兼容清单）。若曾使用复制功能，停服务后用文本编辑器从 config/local.json 的 qq 对象移除新增的 native_version 字段，再换回旧源码；旧代码不认识该字段。不公开或打印本机配置。不清空 data、profile、登录缓存、配额、去重和日志，不自动重发消息或拉起 QQ。未使用复制功能的旧安装没有新增本机配置项，可直接回退完整源码。
