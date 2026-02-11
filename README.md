# OpenClaw Deploy — EasyClaw 一鍵部署工具

透過 Zeabur API 在專用伺服器上自動部署 [OpenClaw](https://github.com/openclaw/openclaw) AI 助理。

## 什麼是這個專案？

這是一套完整的 OpenClaw 部署工具，包含：

- **`deploy.py`** — 一鍵部署腳本，自動完成建立專案、部署服務、設定環境變數、綁定域名
- **`openclaw-template.yaml`** — Zeabur 部署模板
- **`docs/`** — 完整的技術文件、資安報告、使用者指南

## 快速開始

### 前置需求

- Python 3.10+（需安裝 `requests`）
- 客戶的 Zeabur API Token（[取得方式](https://zeabur.com/docs/zh-TW/developer/public-api)）
- 客戶的 Zeabur 帳號需有一台專用伺服器
- AI API Key（Kimi K2.5 / Claude / OpenAI）
- 通訊平台 Bot Token（Telegram / Discord / WhatsApp）

### 使用方式

```bash
# 安裝依賴
pip install requests

# 執行部署
python deploy.py \
  --zeabur-token "sk-xxx" \
  --gateway-token "your-random-32char-token-here123" \
  --ai-provider kimi-coding \
  --ai-key "sk-kimi-xxx" \
  --telegram-token "123:ABC" \
  --subdomain "my-assistant"
```

部署完成後會輸出：
- OpenClaw 控制台網址
- Telegram Bot 連結
- Gateway Token（用於管理）

## 專案結構

```
Openclaw-deploy/
├── README.md                    # 本文件
├── deploy.py                    # 一鍵部署腳本
├── openclaw-template.yaml       # Zeabur 部署模板
├── .env.example                 # 環境變數範例
├── .gitignore                   # Git 忽略規則
└── docs/
    ├── 01-security-audit.md     # 資安設定報告
    ├── 02-features.md           # 功能說明文件
    ├── 03-deployment-guide.md   # 完整部署 SOP
    └── 04-user-guide.md         # 使用者指南（繁體中文）
```

## 部署架構

```
[deploy.py] → [Zeabur GraphQL API] → [專用伺服器 (K3s)]
                                          │
                                          ▼
                                    [OpenClaw Pod]
                                    ├── Gateway (port 3000)
                                    ├── Telegram Bot
                                    ├── WebChat UI
                                    └── AI Models (Kimi/Claude/GPT)
```

## 關鍵技術細節

### Zeabur 專用伺服器 Region 格式

```
server-<serverID>
```

例如：`server-697a44ca9bd53ac41b43ce26`

### 必要環境變數

| 變數 | 必要 | 說明 |
|------|------|------|
| `OPENCLAW_GATEWAY_TOKEN` | 是 | Gateway 認證 Token（>=32 字元） |
| `OPENCLAW_GATEWAY_PORT` | 是 | 必須設為 `3000`（Zeabur 預期） |
| `TELEGRAM_BOT_TOKEN` | 否 | Telegram Bot Token |
| `KIMI_API_KEY` | 否 | Kimi Coding 國際版 API Key（`sk-kimi-*`） |
| `MOONSHOT_API_KEY` | 否 | Moonshot Open Platform API Key（中國版） |
| `ANTHROPIC_API_KEY` | 否 | Claude API Key |
| `OPENAI_API_KEY` | 否 | OpenAI API Key |

### 啟動指令（概念示意）

```bash
sh -c "\
  export OPENCLAW_HOME=/home/node && \
  export OPENCLAW_CONFIG_PATH=/home/node/.openclaw/openclaw.json && \
  export OPENCLAW_STATE_DIR=/home/node/.openclaw && \
  export OPENCLAW_GATEWAY_TOKEN=your-token && \
  mkdir -p /home/node/.openclaw/credentials/telegram && \
  mkdir -p /home/node/.openclaw/agents/main/agent && \
  echo <base64_config> | base64 -d > /home/node/.openclaw/openclaw.json && \
  echo <base64_bot_token> | base64 -d > /home/node/.openclaw/credentials/telegram/botToken && \
  echo <base64_auth_profiles> | base64 -d > /home/node/.openclaw/agents/main/agent/auth-profiles.json && \
  node dist/index.js plugins enable telegram && \
  node dist/index.js channels add --channel telegram --token \"$(cat /home/node/.openclaw/credentials/telegram/botToken)\" && \
  node dist/index.js gateway --bind lan --port 3000"
```

- `--bind lan`：綁定 0.0.0.0（Zeabur ingress 必要）
- `--port 3000`：Gateway 入口
- AI/Telegram 金鑰會寫入檔案，不依賴 env 注入
- 預設採用 long polling（Webhook 需自行提供公開 HTTPS）

### AI Provider 對照表

| Provider | `--ai-provider` 參數 | Env Var | Model |
|----------|----------------------|---------|-------|
| **Kimi Coding 國際版** | `kimi-coding` | `KIMI_API_KEY` | `kimi-coding/k2p5` |
| Moonshot 中國版 | `moonshot` | `MOONSHOT_API_KEY` | `moonshot/kimi-k2.5` |
| Anthropic Claude | `anthropic` | `ANTHROPIC_API_KEY` | `anthropic/claude-sonnet-4-5` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `openai/gpt-4o` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `google/gemini-2.5-pro` |

## 常見問題

詳見 `DEPLOY_GUIDE.md` 的踩坑記錄與完整流程。

## 授權

MIT License
