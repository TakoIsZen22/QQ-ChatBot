# 模型 API 接入

0.7.0 起可选择默认 Magpie 或自定义 OpenAI 兼容 API。两种方式共用 `modules/model.py`，记忆、工具白名单、暂停和 QQ 限流保持相同。只会使用已保存并重启生效的地址，不会自动回退到另一个服务。

已经有 Magpie，希望直接接通？请看 [Magpie 五步接入教程（可选）](MAGPIE_SETUP.md)。不使用 Magpie 时继续本页，自有 API 不需要安装或启动 Magpie。两份说明均可在程序的 API 设置页内阅读。

## 在程序中配置

1. 进入「设置 → 模型与 API 接入」。保留 Magpie 时地址固定为 `http://127.0.0.1:3425/v1`，旧安装无需改动。
2. 不使用 Magpie 时选择「自定义 OpenAI 兼容 API」。按服务方文档填写 **Base URL**，通常含 `/v1`；不要填写完整 `/chat/completions` 或 `/models` 路径。其他版本前缀也可以，程序会追加固定协议路径。远程地址使用 HTTPS，本机 `localhost`、`127.0.0.1`、`[::1]` 可用 HTTP。
3. 填写密钥的**环境变量名称**，例如 `HARNESS_API_KEY`。这里不粘贴密钥值。变量有值时使用 `Authorization: Bearer`；无需鉴权的服务可不设置该变量。
4. 点击「检查连接 / 读取模型」。使用当前表单地址读取 `GET <Base URL>/models`，不保存配置，不发送聊天、人设、记忆或图片，不进行计费推理。会显示核心进程是否读到该环境变量，始终不返回值。部分服务不提供清单：可按服务方说明手动填写模型 ID，再用真实聊天验收。
5. 选择或填写主模型和视觉辅助模型；二者共用当前 API 地址及鉴权。点击「保存设置 → 重启聊天」，再手动恢复「只回复」。重启保留暂停，不自动解除。
6. 发一句简单文本，再测试一个有限工具与一张图片；检查日志中 model_usage/she_spoke。模型清单成功仅证明清单可访问，不代表这些能力均可用。

## 用 Windows 界面配置密钥

在 Windows 搜索「编辑账户的环境变量」，在当前用户环境变量中新建名称与表单完全一致的变量，值由你填入服务方提供的密钥，不加 `Bearer ` 前缀。不要截图、复制给维护 Agent 或写进配置、人设及仓库。

保存环境变量后，从托盘选择「退出并停止全部」，再从开始菜单或桌面快捷方式重新打开程序。仅点窗口 X 会收进托盘，仍会保留旧进程环境；仅重启聊天也可能继续继承桌面的旧环境。连接检查可确认新核心是否已读到变量；若仍显示未检测到，注销 Windows 后重新登录再打开。

Magpie 的厂商密钥、反代 token 和订阅登录仍在 Magpie 中配置；如 Magpie 网关自身需要 Bearer 鉴权，使用 `MAGPIE_API_KEY`。OneBot 的 `NAPCAT_TOKEN` 与模型密钥独立。程序不编辑 Windows 环境变量，不把密钥值保存进 JSON、备份或源码。

## 配置字段与协议

以下只含参数和变量名，实际写入本机 `config/local.json`：

```json
{
  "model": {
    "provider": "openai_compatible",
    "base_url": "https://api.example.com/v1",
    "key_env": "HARNESS_API_KEY",
    "main": "",
    "auxiliary": ""
  }
}
```

| 项目 | 要求 |
|---|---|
| provider | `magpie` 或 `openai_compatible` |
| 文本/工具 | `POST /chat/completions`，支持 messages、max_tokens、temperature 和标准 tools/tool_calls；返回 choices[].message |
| 视觉 | 同一协议支持 `image_url`，包括程序提供的 data URL；视觉模型 ID 填 auxiliary |
| 鉴权 | 从 key_env 所指环境变量取 Bearer token；不支持把密钥放 URL 查询参数 |
| 清单 | `GET /models` 返回 data 数组，包含字符串 id；不支持时可手动填 ID |
| 超时/大小 | timeout_seconds 管推理；models_timeout_seconds 默认 10 秒；max_response_bytes 默认 4 MiB |
| 安全 | 不跟随重定向，不关闭 TLS 证书验证，不接受 URL 内账号/密码/查询参数 |

仅提供原生 Messages、GenerateContent 或 Responses 协议的服务，需要先提供上述 Chat Completions 兼容层；本版本未实现这些原生协议适配。API 的模型和参数能力以服务方实际返回为准，不把所有“兼容”服务都标为已实测。

## 运维与故障

- 保存地址、模型或变量名后重启聊天；变更环境变量值还需重启整个程序和核心。
- 401/403：自己检查变量是否生效、密钥权限、账户与服务限制；不要让 Agent 打印环境变量。
- 404/非 JSON：核对 Base URL 是否误填网页地址或完整推理路径；不提供清单的服务可手动填写模型。
- 429：检查额度、服务方限制并等待，不绕过本机 QQ 发送配额。
- 工具/图片失败：确认对应模型与兼容层支持 tools/image_url；文本可用不代表视觉可用。
- 只读 health/supervise/诊断会检查所选 API 主机端口，不要求自定义模式下的 Magpie 在线；TCP 可达不代表 TLS、鉴权或推理已经成功。
- 换回 Magpie：选择 Magpie，核对模型 ID 与环境变量名，保存、重启；不覆盖记忆、人设或角色图片。
- 分享时只用发布工具。自定义地址、模型和变量名留在本机 local.json，密钥值仅在用户环境中。清洁发布包仍默认 Magpie、模型 ID 留空。
