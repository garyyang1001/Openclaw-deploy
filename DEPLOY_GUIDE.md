# EasyClaw OpenClaw 部署指南

> 適用版本: OpenClaw **v2026.2.9+** / Zeabur Dedicated Server
> 最後更新: 2026-02-10

---

## 目錄

1. [快速開始](#1-快速開始)
2. [新建部署流程](#2-新建部署流程)
3. [更新（覆蓋）部署流程](#3-更新覆蓋部署流程)
4. [.env 設定參考](#4-env-設定參考)
5. [Start Command 結構](#5-start-command-結構)
6. [Config 檔案格式](#6-config-檔案格式)
7. [Zeabur API 參考](#7-zeabur-api-參考)
8. [踩坑紀錄與解法](#8-踩坑紀錄與解法)
9. [故障排除](#9-故障排除)

---

## 1. 快速開始

```bash
# 安裝依賴
pip install requests

# 複製設定檔
cp .env.example .env
# 編輯 .env 填入你的 token

# 首次部署（新建）
python deploy.py --env-file .env

# 之後更新（自動偵測已有 ID）
python deploy.py --env-file .env

# 強制新建（忽略已有 ID）
python deploy.py --env-file .env --force-new
```

---

## 1.1 客戶資料清單（部署前必收）

**必填**
1. Zeabur API Token（格式 `sk-xxx`）
2. 專用伺服器已建立（Zeabur Dedicated Server）
3. AI Provider API Key（擇一）
4. Telegram Bot Token（@BotFather 取得）
5. Telegram User ID（數字 ID，用於 allowlist）

**可選**
1. 子網域（`SUBDOMAIN`，不填會自動產生）
2. Brave Search API Key（需要搜尋功能才填）
3. Webhook 設定（只在要 webhook 時才需要）：`TELEGRAM_WEBHOOK_URL` / `TELEGRAM_WEBHOOK_SECRET` / `TELEGRAM_WEBHOOK_PATH`

> 建議：請客戶把以上資料填入 `.env`，你只要執行 `python deploy.py --env-file .env`

---

## 2. 新建部署流程

```
Step 1: 驗證 Zeabur Token
Step 2: 找到 Dedicated Server
Step 3: 建立 Project
Step 4: 用 YAML Template 部署 OpenClaw image
Step 5: 設定環境變數 (createEnvironmentVariable)
Step 6: 綁定 Domain
Step 7: （選用）設定 Telegram Webhook 相關 env vars
Step 8: 設定 Start Command（base64 config + 寫入 auth-profiles + 啟用 Telegram）
Step 9: Restart Service
Step 10: 設定 Telegram Webhook 或清除（預設 long polling）
Step 11: 驗證部署
      → 自動將 PROJECT_ID / SERVICE_ID / ENVIRONMENT_ID / DOMAIN 寫回 .env
```

完成後 `.env` 尾部會自動追加：
```
# Deployment IDs (auto-generated, do not delete)
PROJECT_ID=xxxx
SERVICE_ID=xxxx
ENVIRONMENT_ID=xxxx
DOMAIN=oc-xxxxx.zeabur.app
```

---

## 3. 更新（覆蓋）部署流程

**判斷條件**: `.env` 內有 `PROJECT_ID` + `SERVICE_ID` + `ENVIRONMENT_ID` 且未帶 `--force-new`

```
Step 1: 驗證 Token
Step 2: 驗證現有部署 (service query 確認 ID 有效)
Step 3: 更新環境變數
Step 4: 設定 Start Command（base64 config + 寫入 auth-profiles + 啟用 Telegram）
Step 5: 更新 Image Tag (觸發重新拉取)
Step 6: Restart
Step 7: 設定 Telegram Webhook 或清除（預設 long polling）
Step 8: 驗證
```

---

## 4. .env 設定參考

```bash
# === 必填 ===
ZEABUR_TOKEN=sk-xxxxxxxxxxxxxxxxxxxxx        # Zeabur API Token
GATEWAY_TOKEN=random-32-char-string-here     # OpenClaw Gateway 認證 (>=32 字元)
TELEGRAM_BOT_TOKEN=123456789:AABBCCDD        # 從 @BotFather 取得

# === AI Provider (擇一) ===
KIMI_API_KEY=sk-kimi-xxxx                    # Kimi Coding 國際版 (推薦)
# MOONSHOT_API_KEY=sk-xxxx                   # Moonshot 中國版
# ANTHROPIC_API_KEY=sk-ant-xxxx              # Claude
# OPENAI_API_KEY=sk-xxxx                     # OpenAI

# === 安全設定 ===
TELEGRAM_USER_ID=1234567890                  # 你的 Telegram 數字 ID
                                             # 取得方式: 搜尋 @userinfobot

# === 可選 ===
SUBDOMAIN=my-bot                             # 自定子域名 (不填會自動產生)
BRAVE_API_KEY=                               # Brave Search API Key
TELEGRAM_WEBHOOK_URL=                        # 有需要才填（Webhook 模式）
TELEGRAM_WEBHOOK_SECRET=                     # 有需要才填
TELEGRAM_WEBHOOK_PATH=                       # 預設 /telegram-webhook
# 不填 = 預設 long polling（不需要公開網址）

# === 部署 ID (首次部署後自動產生，勿手動修改) ===
# PROJECT_ID=
# SERVICE_ID=
# ENVIRONMENT_ID=
# DOMAIN=
```

---

## 5. Start Command 結構

這是 deploy.py 產生的 Start Command 結構。**每一段都有特定原因，不可省略。**

```bash
sh -c "\
  export OPENCLAW_HOME=/home/node && \
  export OPENCLAW_CONFIG_PATH=/home/node/.openclaw/openclaw.json && \
  export OPENCLAW_STATE_DIR=/home/node/.openclaw && \
  export OPENCLAW_GATEWAY_TOKEN=random32 && \
  mkdir -p /home/node/.openclaw && \
  echo <base64_config> | base64 -d > /home/node/.openclaw/openclaw.json && \
  mkdir -p /home/node/.openclaw/credentials/telegram && \
  echo <base64_bot_token> | base64 -d > /home/node/.openclaw/credentials/telegram/botToken && \
  mkdir -p /home/node/.openclaw/agents/main/agent && \
  echo <base64_auth_profiles> | base64 -d > /home/node/.openclaw/agents/main/agent/auth-profiles.json && \
  node dist/index.js plugins enable telegram && \
  node dist/index.js channels add --channel telegram --token \"$(cat /home/node/.openclaw/credentials/telegram/botToken)\" && \
  node dist/index.js gateway --bind lan --port 3000"
```

### 各段說明

| 段落 | 原因 |
|------|------|
| `export OPENCLAW_*` | Zeabur env var 注入不可靠，OpenClaw 相關設定直接在 shell 層 export |
| `export OPENCLAW_HOME=/home/node` | 容器以 root 運行，OpenClaw 預設讀 `/root/.openclaw/`；volume 掛在 `/home/node/.openclaw/`，需要用 OPENCLAW_HOME 指向 `/home/node`（**不是** `/home/node/.openclaw`，OpenClaw 會自己加 `/.openclaw/`） |
| `mkdir -p ...` | 確保目錄存在 |
| `echo base64 \| base64 -d > ...json` | 用 base64 寫入 config 檔（不能用 `updateServiceConfig` API，會跟 volume mount 衝突變成 read-only） |
| `echo base64 ... botToken` | 寫入 Telegram Bot Token 檔案 |
| `echo base64 ... auth-profiles` | 寫入 AI Provider 的 `auth-profiles.json` |
| `plugins enable telegram` | 啟用 Telegram plugin |
| `channels add ...` | 註冊 Telegram channel（長輪詢模式） |
| `gateway --bind lan --port 3000` | 啟動 gateway |

---

## 6. Config 檔案格式

寫入 `/home/node/.openclaw/openclaw.json` 的 config：

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "kimi-coding/k2p5"
      }
    }
  },
  "channels": {
    "telegram": {
      "dmPolicy": "allowlist",
      "allowFrom": ["7933301912"],
      "groupPolicy": "disabled",
      "configWrites": false
    }
  }
}
```

### 重要：不要包含的 key

| 不要用 | 原因 |
|--------|------|
| `plugins.telegram` | v2026.2.9 已移除，會造成 **crash**: `Unrecognized key: "telegram"` |
| `plugins.telegram.enabled` | 同上，Telegram 啟用改由 CLI `plugins enable telegram` |

### Model 對照表

| `--ai-provider` | config model ID | env var |
|------------------|----------------|---------|
| `kimi-coding` | `kimi-coding/k2p5` | `KIMI_API_KEY` |
| `moonshot` | `moonshot/kimi-k2.5` | `MOONSHOT_API_KEY` |
| `anthropic` / `claude` | `anthropic/claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| `openai` | `openai/gpt-4o` | `OPENAI_API_KEY` |
| `gemini` | `google/gemini-2.5-pro` | `GEMINI_API_KEY` |

### DM Policy 選項

| 值 | 行為 |
|----|------|
| `allowlist` (預設) | 只有 `allowFrom` 列表中的 user ID 可私訊 bot |
| `open` | 所有人都可以私訊 |
| `pairing` | 需要配對碼 |
| `disabled` | 關閉私訊 |

---

## 7. Zeabur API 參考

所有 mutation/query 已實測驗證通過。

### 環境變數

```graphql
# 建立
mutation {
  createEnvironmentVariable(
    serviceID: "xxx", environmentID: "xxx",
    key: "KEY", value: "value"
  ) { key }
}

# 更新 — key 不加引號！
mutation {
  updateEnvironmentVariable(
    serviceID: "xxx", environmentID: "xxx",
    data: { KEY: "value" }         # ✅ KEY 不加引號
  )
}

# ❌ 錯誤寫法 (GRAPHQL_PARSE_FAILED):
# data: { "KEY": "value" }
```

### Service 操作

```graphql
# 更新 Start Command (注意：沒有 environmentID 參數)
mutation {
  updateServiceCommand(serviceID: "xxx", command: "...")
}

# 更新 Image Tag (會觸發重新部署)
mutation {
  updateServiceImage(serviceID: "xxx", environmentID: "xxx", tag: "2026.2.9")
}

# 重啟
mutation {
  restartService(serviceID: "xxx", environmentID: "xxx")
}
```

### Config 操作（謹慎使用）

```graphql
# 寫入 config 檔 — 注意：會跟 volume mount 衝突！
mutation {
  updateServiceConfig(
    serviceID: "xxx", environmentID: "xxx",
    path: "/path/to/file", content: "..."
  )
}

# 刪除 config 檔 (解除 read-only)
mutation {
  deleteServiceConfig(
    serviceID: "xxx", environmentID: "xxx",
    path: "/path/to/file"
  )
}
```

### 查詢

```graphql
# Service 狀態
query { service(_id: "xxx") { name status } }

# 專案列表 (含 service + domain)
query {
  projects {
    edges {
      node {
        _id name
        services { _id name status domains { domain } }
        environments { _id name }
      }
    }
  }
}

# Runtime Logs
query {
  runtimeLogs(
    projectID: "xxx", serviceID: "xxx", environmentID: "xxx"
  ) { message timestamp }
}
```

---

## 8. 踩坑紀錄與解法

### 8.1 Zeabur env var 注入不可靠

**現象**: `createEnvironmentVariable` / `updateEnvironmentVariable` API 回傳成功，但容器內看不到該環境變數。

**解法**: OpenClaw 相關設定（`OPENCLAW_*`）會在 start command 直接 export；AI/Telegram 金鑰改寫入檔案（`auth-profiles.json`、`botToken`）。

### 8.2 `updateServiceConfig` 跟 volume mount 衝突

**現象**: 呼叫 `updateServiceConfig` 寫檔到 `/home/node/.openclaw/openclaw.json` 後，整個 `/home/node/.openclaw/` 目錄變成 read-only，shell 無法寫入。

**原因**: Zeabur 用 Kubernetes ConfigMap 實作 `updateServiceConfig`，會覆蓋同路徑的 volume mount。

**解法**:
- 不要用 `updateServiceConfig` 寫到 volume mount 的路徑
- 改用 start command 中的 base64 方式寫入
- 如果已經呼叫過，用 `deleteServiceConfig` 撤銷

### 8.3 OPENCLAW_HOME 設定錯誤導致路徑雙重嵌套

**現象**: Canvas 路徑變成 `/home/node/.openclaw/.openclaw/canvas`（雙重 `.openclaw`）。

**原因**: `OPENCLAW_HOME=/home/node/.openclaw` 錯誤，因為 OpenClaw 會自動附加 `/.openclaw/`。

**正確**: `OPENCLAW_HOME=/home/node` → OpenClaw 使用 `/home/node/.openclaw/`

### 8.4 `plugins.telegram` 在 v2026.2.9 crash

**現象**: 啟動後立即 crash: `Config invalid — plugins: Unrecognized key: "telegram"`

**原因**: v2026.2.9 移除了 `plugins.telegram` config key。

**解法**: config 中不放 `plugins` 欄位，改用 CLI：`plugins enable telegram` + `channels add --channel telegram --token ...`。

### 8.5 `updateServiceImage` 觸發立即重新部署

**現象**: 呼叫 `updateServiceImage` 後，新 pod 馬上建立，可能在其他設定完成前就啟動。

**建議**: 先設好 start command 和 env vars，最後才呼叫 `updateServiceImage`，再手動 `restartService`。

---

## 9. 故障排除

### Telegram 沒回應

1. 檢查 logs 有沒有 `"Telegram configured, not enabled yet."`
   - 有 → start command 中缺少 `plugins enable telegram`
2. 檢查 logs 有沒有 `"No API key found for provider"`
   - 有 → `auth-profiles.json` 未寫入（確認 start command 會寫入 `/home/node/.openclaw/agents/main/agent/auth-profiles.json`）
3. 檢查 logs 有沒有 `"Unrecognized key: telegram"`
   - 有 → config 檔包含 `plugins.telegram`，移除後重啟

### Service CRASHED

1. 查 logs 最後幾行找 crash 原因
2. 常見：
   - `Gateway auth is set to token, but no token is configured` → env var OPENCLAW_GATEWAY_TOKEN 沒注入
   - `Config invalid` → config 檔有不認識的 key
   - `Read-only file system` → `updateServiceConfig` 把 volume 弄成 read-only，需要 `deleteServiceConfig`

### 查看 Logs

```bash
python3 -c "
import requests, json
TOKEN='sk-your-token'
API='https://api.zeabur.com/graphql'
h={'Authorization':f'Bearer {TOKEN}','Content-Type':'application/json'}
r=requests.post(API,headers=h,json={'query':'query{runtimeLogs(projectID:\"PROJECT_ID\",serviceID:\"SERVICE_ID\",environmentID:\"ENV_ID\"){message timestamp}}'})
for l in r.json()['data']['runtimeLogs'][:20]:
    print(f\"{l['timestamp'][:19]} | {l['message'][:150]}\")
"
```

### 手動重啟

```bash
python3 -c "
import requests
TOKEN='sk-your-token'
API='https://api.zeabur.com/graphql'
h={'Authorization':f'Bearer {TOKEN}','Content-Type':'application/json'}
requests.post(API,headers=h,json={'query':'mutation{restartService(serviceID:\"SERVICE_ID\",environmentID:\"ENV_ID\")}'})
print('Restarted')
"
```

---

## deploy.py 檔案結構

```
deploy.py
├── gql()                      # GraphQL API 呼叫
├── verify_token()             # 驗證 Zeabur token
├── find_existing_deployment() # 驗證已有部署的 ID 有效
├── get_server()               # 找到 dedicated server
├── create_project()           # 建立 project
├── deploy_template()          # 用 YAML 部署 OpenClaw image
├── set_env_var()              # 設定單一 env var (create 或 update)
├── configure_service()        # 設定所有 env vars
├── build_config()             # 產生 openclaw.json config dict
├── set_start_command()        # 產生完整 start command (base64 config + auth-profiles + Telegram plugin)
├── update_service_image()     # 更新 Docker image tag
├── restart_service()          # 重啟 + 等待
├── add_domain()               # 綁定 subdomain
├── verify_deployment()        # 驗證部署狀態
├── save_deployment_ids()      # 寫回 .env
└── main()                     # 主流程 (新建 / 更新 分支)
```
