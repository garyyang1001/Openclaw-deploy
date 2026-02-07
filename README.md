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

### 啟動指令

啟動前需透過 config 檔指定 AI 模型（無法用 env var 設定）：

```bash
sh -c "mkdir -p /root/.openclaw && \
  echo '{\"agents\":{\"defaults\":{\"model\":{\"primary\":\"kimi-coding/k2p5\"}}},\"channels\":{\"telegram\":{\"dmPolicy\":\"open\",\"allowFrom\":[\"*\"]}}}' \
  > /root/.openclaw/openclaw.json && \
  node dist/index.js gateway --allow-unconfigured --bind lan"
```

- `--bind lan`：綁定 0.0.0.0（必要，否則 Zeabur ingress 無法路由）
- `--allow-unconfigured`：跳過 onboard 設定流程
- Port 由 `OPENCLAW_GATEWAY_PORT` 控制（非 `--port` 參數）
- Model 由 config 檔 `openclaw.json` 控制（`deploy.py` 會自動處理）

### AI Provider 對照表

| Provider | `--ai-provider` 參數 | Env Var | Model |
|----------|----------------------|---------|-------|
| **Kimi Coding 國際版** | `kimi-coding` | `KIMI_API_KEY` | `kimi-coding/k2p5` |
| Moonshot 中國版 | `moonshot` | `MOONSHOT_API_KEY` | `moonshot/kimi-k2.5` |
| Anthropic Claude | `anthropic` | `ANTHROPIC_API_KEY` | `anthropic/claude-sonnet-4-5` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `openai/gpt-4o` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `google/gemini-2.5-pro` |

## 常見問題

詳見 [03-deployment-guide.md](docs/03-deployment-guide.md) 的踩坑記錄。

## 授權

MIT License
