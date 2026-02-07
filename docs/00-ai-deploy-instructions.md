# AI 部署指令 — OpenClaw on Zeabur

> 這份文件供 AI agent（Claude Code、Cursor 等）讀取。
> 讀完後你應該能完整執行 OpenClaw 部署流程。

---

## 快速部署（一行指令）

```bash
python deploy.py \
  --zeabur-token "<客戶的 Zeabur Token>" \
  --ai-provider kimi-coding \
  --ai-key "<客戶的 AI API Key>" \
  --telegram-token "<客戶的 Telegram Bot Token>" \
  --telegram-user-id "<客戶的 Telegram User ID>" \
  --subdomain "<客戶想要的子域名>"
```

> **安全預設**：`--dm-policy` 預設為 `allowlist`，只有 `--telegram-user-id` 指定的用戶可以私訊 Bot。**嚴禁使用 `--dm-policy open`**，否則任何人都能使用客戶的 AI 額度。

deploy.py 會自動完成所有 9 個步驟。以下是每個步驟的說明，供你在自動化腳本失敗時手動排除問題。

---

## 前置需求（客戶需提供）

| 項目 | 格式 | 取得方式 |
|------|------|----------|
| Zeabur API Token | `sk-xxxxx` | zeabur.com → Settings → API Token |
| Zeabur 專用伺服器 | 已建立 | zeabur.com → Servers → 新增專用伺服器 |
| AI API Key | 見下方 | 各 AI 平台申請 |
| Telegram Bot Token | `123456789:AABBCC` | Telegram @BotFather → /newbot |
| Telegram User ID | `6005789080`（純數字） | Telegram 搜尋 @userinfobot 或 @raw_data_bot，發送任意訊息即可取得 |

### AI Provider 對照表（重要！）

| 情境 | `--ai-provider` | Env Var | Config Model | API Endpoint |
|------|-----------------|---------|--------------|--------------|
| Kimi Coding 國際版（`sk-kimi-*` key） | `kimi-coding` | `KIMI_API_KEY` | `kimi-coding/k2p5` | api.kimi.com（Anthropic-compatible） |
| Moonshot 中國版（`sk-*` key，無 kimi） | `moonshot` | `MOONSHOT_API_KEY` | `moonshot/kimi-k2.5` | api.moonshot.cn（OpenAI-compatible） |
| Anthropic Claude | `anthropic` | `ANTHROPIC_API_KEY` | `anthropic/claude-sonnet-4-5` | api.anthropic.com |
| OpenAI | `openai` | `OPENAI_API_KEY` | `openai/gpt-4o` | api.openai.com |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `google/gemini-2.5-pro` | generativelanguage.googleapis.com |

**關鍵提醒**：`sk-kimi-*` 開頭的 key 是 Kimi Coding 國際版，必須用 `KIMI_API_KEY`。如果誤設為 `MOONSHOT_API_KEY` 會導致 HTTP 401 Invalid Authentication。

---

## 9 步部署流程

### Step 1: 驗證 Zeabur Token

```graphql
query { user { name username } }
```

### Step 2: 取得專用伺服器

```graphql
query { servers { _id hostname status ip } }
```

記下 `_id`，Region 格式為 `server-<_id>`。

### Step 3: 建立專案

```graphql
mutation { createProject(region: "server-<SERVER_ID>", name: "openclaw") { _id } }
```

### Step 4: 部署 Docker Image

使用 `openclaw-template.yaml` 透過 `deployTemplate` mutation 部署。
Image: `ghcr.io/openclaw/openclaw:2026.2.2`

部署後查詢 serviceID 和 environmentID：
```graphql
query { project(_id: "<PROJECT_ID>") { services { _id name } environments { _id name } } }
```

### Step 5: 設定環境變數

必要：
- `OPENCLAW_GATEWAY_TOKEN` — 至少 32 字元隨機字串
- `OPENCLAW_GATEWAY_PORT` — 必須是 `3000`

AI Key（依 provider 選一個）：
- `KIMI_API_KEY` / `MOONSHOT_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`

通訊平台：
- `TELEGRAM_BOT_TOKEN`

```graphql
mutation {
  createEnvironmentVariable(
    serviceID: "<SVC_ID>",
    environmentID: "<ENV_ID>",
    key: "<KEY>",
    value: "<VALUE>"
  ) { key value }
}
```

### Step 6: 設定啟動指令（含 config 生成）

OpenClaw 的 model 和 DM 策略**無法透過環境變數設定**，必須在啟動前寫入 config 檔。

啟動指令格式：
```bash
sh -c "mkdir -p /root/.openclaw && echo '<CONFIG_JSON>' > /root/.openclaw/openclaw.json && node dist/index.js gateway --allow-unconfigured --bind lan"
```

Config JSON 範例（Kimi Coding + allowlist DM，安全預設）：
```json
{
  "agents": { "defaults": { "model": { "primary": "kimi-coding/k2p5" } } },
  "channels": { "telegram": { "dmPolicy": "allowlist", "allowFrom": ["<TELEGRAM_USER_ID>"] } }
}
```

DM 策略選項：
- `allowlist`（**預設，強烈建議**）— 只有白名單上的 Telegram User ID 可以對話，防止他人盜用 AI 額度
- `pairing` — 新用戶需配對碼，管理員核准
- `open` — ⚠️ **不建議**：任何人都可以直接跟 bot 對話，會消耗客戶的 AI API 額度
- `disabled` — 關閉私訊

GraphQL mutation（注意：`updateServiceCommand` 不需要 environmentID）：
```graphql
mutation($cmd: String!) {
  updateServiceCommand(serviceID: "<SVC_ID>", command: $cmd)
}
```

### Step 7: 重啟服務

```graphql
mutation { restartService(serviceID: "<SVC_ID>", environmentID: "<ENV_ID>") }
```

等待約 30 秒讓服務完全啟動。

### Step 8: 綁定域名

先檢查可用性（`isGenerated: true` 時只傳子域名部分，例如 `myapp`，不是 `myapp.zeabur.app`）：
```graphql
mutation {
  checkDomainAvailable(domain: "<SUBDOMAIN>", isGenerated: true, region: "server-<SID>") {
    isAvailable reason
  }
}
```

綁定：
```graphql
mutation {
  addDomain(serviceID: "<SVC_ID>", environmentID: "<ENV_ID>", isGenerated: true, domain: "<SUBDOMAIN>") {
    domain
  }
}
```

### Step 9: 驗證

- 查詢服務狀態：`query { service(_id: "<SVC_ID>") { name status } }`
- 查詢 logs：`query { runtimeLogs(projectID: "<PID>", serviceID: "<SVC_ID>", environmentID: "<EID>") { message timestamp } }`
- HTTP 測試：`curl https://<SUBDOMAIN>.zeabur.app/`

成功標準：
- `[gateway] agent model: kimi-coding/k2p5`（或你選的 model）
- `[gateway] listening on ws://0.0.0.0:3000`
- `[telegram] [default] starting provider`

---

## 常見踩坑

| 問題 | 原因 | 解法 |
|------|------|------|
| Container crash | 缺 `OPENCLAW_GATEWAY_TOKEN` | 設定 env var，至少 32 字元 |
| 502 Bad Gateway | Port 不匹配 | 設定 `OPENCLAW_GATEWAY_PORT=3000` |
| 502 Bad Gateway | Bind 在 127.0.0.1 | 啟動指令加 `--bind lan` |
| HTTP 401 Invalid Auth | Kimi key 用錯 env var | `sk-kimi-*` → `KIMI_API_KEY` + `kimi-coding/k2p5` |
| Domain UNAVAILABLE | 子域名格式錯 | `isGenerated:true` 只傳子域名部分 |
| REQUIRE_DEDICATED_SERVER | 用了 shared cluster | `createProject` 時指定 `region: "server-<id>"` |

---

## 檔案參考

| 檔案 | 用途 |
|------|------|
| `deploy.py` | 一鍵自動化部署（推薦使用） |
| `zeabur_api.py` | Zeabur GraphQL API client library |
| `openclaw-template.yaml` | Zeabur 部署 YAML 模板 |
| `.env.example` | 環境變數範例檔 |
| `docs/01-security-audit.md` | 資安設定報告 |
| `docs/02-features.md` | OpenClaw 功能說明 |
| `docs/03-deployment-guide.md` | 完整部署 SOP + 踩坑記錄 |
| `docs/04-user-guide.md` | 終端使用者指南（繁體中文） |

---

## Zeabur API 注意事項

- API endpoint: `https://api.zeabur.com/graphql`
- Auth: `Authorization: Bearer <token>`
- `updateServiceCommand` 不接受 `environmentID` 參數
- `runtimeLogs` 不接受 `limit` 參數
- `addDomain` 的 `isGenerated: true` 只傳子域名
- GraphQL variables 建議用 `$variables` 方式傳遞，避免 escaping 問題
