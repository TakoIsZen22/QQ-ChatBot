# 素材与第三方组件

MIT 许可适用于本项目原创代码与文档，不改变第三方组件或素材各自的许可。

- `qq-chatbot-fish-chat-v1.png/.ico` 为本项目设计的聊天小鱼图标，使用内置 imagegen 生成图稿并封装 Windows 多尺寸 ICO；设计提示词随素材保存。
- 程序运行时引用的 `xiaojing-user-icon.png/.ico` 与上述自产小鱼图标内容相同，文件名是历史沿用，不代表素材来源。
- `xiaojing-icon.*` 与 `assets/icon-prompt.txt` 是早期图标的存档，程序不再引用，公开源码包不包含这些未使用的文件。
- Python 依赖按各自许可分发；requirements 锁文件记录版本，安装时从相应软件源取得。
- NapCat、QQ 客户端、Magpie、Whisper 模型权重不随本项目源码包分发，由使用者自行准备。项目不包含它们的登录态或访问凭据。

Windows绿色包另外包含CPython、锁定的Python依赖和未修改的7-Zip解压组件，各自许可证保留在_runtime与_tools中，来源/源码链接见docs/WINDOWS_BUILD.md。QQ和NapCat由使用者在向导中从官方来源下载，不包含在本项目分发ZIP中。
