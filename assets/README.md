# QQ ChatBot 应用图标

1.00.01 与 1.00.02 的默认程序图标均使用 2026-10-20 使用者提供的图片（蓝发角色与「穷光蛋」气泡），保留原图完整内容。经 FlyingMouse Format 转换为 PNG 和 Windows 多尺寸 ICO，未重新生成图案。

- `qq-chatbot-fish-chat-v1.png`：设计图稿原始 PNG，1254×1254。
- `qq-chatbot-fish-chat-v1.ico`：Windows 多尺寸 ICO，包含 16/24/32/48/64/128/256。
- `qq-chatbot-fish-chat-v1.prompt.md`：生成图稿时使用的提示词与说明，随素材保留以便复现或改版。

上述 `qq-chatbot-fish-chat-v1.*` 为前一版设计的存档，程序已不再引用。程序现在使用 `xiaojing-user-icon.png` / `.ico`，内容为新提供的图片。ICO 包含 16/24/32/48/64/128/256 尺寸；文件名沿用历史引用，不代表当前昵称。`xiaojing-icon.*` 与 `icon-prompt.txt` 为更早存档，公开源码包不包含。

桌面、开始菜单、Windows 程序登记和窗口使用 ICO，托盘与网页内头像使用 PNG。网页与桌面内头像的副本分别位于 `src/channel/ui/icons`、`src/channel/ui/desktop/assets`。

使用者可在「设置 → 角色形象」上传自己的角色图与程序图标，保存后立即生效，无需替换仓库内素材。

更新图标后需重新创建快捷方式（`tools/create-desktop-shortcut.ps1`）并退出、重新打开桌面界面，聊天与 QQ 服务无需停止。迁移项目后重建快捷方式，不能只复制 lnk 而不复制 assets。
