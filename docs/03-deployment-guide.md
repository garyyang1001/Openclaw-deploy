# EasyClaw OpenClaw 部署技術文件

## 概要

本文件記錄如何透過 Zeabur API 在專用伺服器上部署 OpenClaw 實例。
適用於為客戶一鍵部署的商業場景。

## 前置需求

| 項目 | 說明 |
|------|------|
| Zeabur API Token | 客戶提供，格式 `sk-xxx` |
| Zeabur 專用伺服器 | 客戶帳號內需有一台專用伺服器 |
| AI API Key | 客戶提供（Kimi K2.5 / Claude / OpenAI） |
| 通訊平台 Token | 客戶提供（Telegram Bot Token 等） |

## 架構

```
[客戶的 Zeabur 帳號]
  └─ [專用伺服器 (Dedicated Server)]
       └─ [K3s 叢集]
            └─ [OpenClaw Pod]
                 ├─ Port 3000 (HTTP)
                 ├─ Volume: /home/node/.openclaw
                 └─ 環境變數: Token, API Keys, Bind
```

## 部署步驟

### Step 1: 驗證 Zeabur Token

```bash
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"query{user{name username}}"}'
```

### Step 2: 取得專用伺服器 ID

```bash
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"query{servers{_id hostname status ip}}"}'
```

記下 `_id` 欄位（例如 `697a44ca9bd53ac41b43ce26`）。
Region 格式為 `server-<serverID>`。

### Step 3: 建立專案（指定專用伺服器 Region）

```bash
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{createProject(region:\"server-<SERVER_ID>\",name:\"openclaw-client\"){_id}}"}'
```

記下回傳的 `projectID`。

### Step 4: 部署 OpenClaw 模板

準備 YAML 模板檔（`openclaw-template.yaml`）：

```yaml
apiVersion: zeabur.com/v1
kind: Template
metadata:
    name: OpenClaw-EasyClaw
spec:
    description: OpenClaw AI Assistant deployed by EasyClaw
    services:
        - name: openclaw
          template: PREBUILT
          spec:
            source:
                image: ghcr.io/openclaw/openclaw:2026.2.2
            ports:
                - id: web
                  port: 3000
                  type: HTTP
            env:
                NODE_ENV:
                    default: production
            volumes:
                - id: openclaw-data
                  dir: /home/node/.openclaw
```

執行部署：

```bash
YAML_CONTENT=$(cat openclaw-template.yaml)
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation{deployTemplate(projectID:\\\"<PROJECT_ID>\\\",rawSpecYaml:\\\"$(echo "$YAML_CONTENT" | sed 's/"/\\\\"/g' | tr '\n' ' ')\\\"){_id}}\"}"
```

記下回傳的 `serviceID` 和 `environmentID`。

### Step 5: 設定環境變數

必要環境變數：

```bash
# 1. Gateway Token（必要 - 至少 32 字元）
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{createEnvironmentVariable(serviceID:\"<SERVICE_ID>\",environmentID:\"<ENV_ID>\",key:\"OPENCLAW_GATEWAY_TOKEN\",value:\"<隨機32字元TOKEN>\"){key}}"}'

# 2. Gateway Port（必要 - 必須是 3000）
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{createEnvironmentVariable(serviceID:\"<SERVICE_ID>\",environmentID:\"<ENV_ID>\",key:\"OPENCLAW_GATEWAY_PORT\",value:\"3000\"){key}}"}'

# 3. AI API Key（依客戶選擇的模型）
# Kimi Coding 國際版 (sk-kimi-* keys, 推薦):
curl -s -X POST ... key:\"KIMI_API_KEY\",value:\"<KEY>\"
# Moonshot Open Platform 中國版 (sk-* keys):
curl -s -X POST ... key:\"MOONSHOT_API_KEY\",value:\"<KEY>\"
# Anthropic:
curl -s -X POST ... key:\"ANTHROPIC_API_KEY\",value:\"<KEY>\"
# OpenAI:
curl -s -X POST ... key:\"OPENAI_API_KEY\",value:\"<KEY>\"

# 4. 通訊平台 Token（依客戶選擇的平台）
# Telegram:
curl -s -X POST ... key:\"TELEGRAM_BOT_TOKEN\",value:\"<TOKEN>\"
```

### Step 6: 設定啟動指令（含 config 生成）

啟動指令需要先產生 `openclaw.json` 設定檔來指定 AI 模型和 Telegram DM 策略，再啟動 gateway。

**Kimi Coding 國際版（推薦）：**

```bash
# 啟動指令會自動生成設定檔
sh -c "mkdir -p /root/.openclaw && echo '{\"agents\":{\"defaults\":{\"model\":{\"primary\":\"kimi-coding/k2p5\"}}},\"channels\":{\"telegram\":{\"dmPolicy\":\"open\",\"allowFrom\":[\"*\"]}}}' > /root/.openclaw/openclaw.json && node dist/index.js gateway --allow-unconfigured --bind lan"
```

**其他 AI Provider 範例：**

| Provider | Model 值 | Env Var |
|----------|----------|---------|
| Kimi Coding 國際版 | `kimi-coding/k2p5` | `KIMI_API_KEY` |
| Moonshot 中國版 | `moonshot/kimi-k2.5` | `MOONSHOT_API_KEY` |
| Anthropic Claude | `anthropic/claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |

使用 `deploy.py` 會自動根據 `--ai-provider` 參數產生正確的啟動指令。

**關鍵參數說明：**
- `--allow-unconfigured`：允許在沒有 onboard 設定的情況下啟動
- `--bind lan`：綁定 0.0.0.0，讓 Zeabur ingress 可以路由流量
- Port 3000 由 `OPENCLAW_GATEWAY_PORT` 環境變數控制（Dockerfile 預設 18789）
- Model 和 DM 策略無法透過 env var 設定，必須透過 config 檔（`/root/.openclaw/openclaw.json`）

### Step 7: 重啟服務

```bash
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{restartService(serviceID:\"<SERVICE_ID>\",environmentID:\"<ENV_ID>\")}"}'
```

### Step 8: 綁定域名

先檢查可用性（`isGenerated: true` 時只傳子域名部分）：

```bash
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{checkDomainAvailable(domain:\"<SUBDOMAIN>\",isGenerated:true,region:\"server-<SERVER_ID>\"){isAvailable reason}}"}'
```

綁定域名：

```bash
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{addDomain(serviceID:\"<SERVICE_ID>\",environmentID:\"<ENV_ID>\",isGenerated:true,domain:\"<SUBDOMAIN>\"){domain}}"}'
```

### Step 9: 驗證部署

```bash
# 檢查服務狀態
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"query{service(_id:\"<SERVICE_ID>\"){name status}}"}'

# 檢查 runtime logs
curl -s -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer <ZEABUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"query{runtimeLogs(projectID:\"<PROJECT_ID>\",serviceID:\"<SERVICE_ID>\",environmentID:\"<ENV_ID>\"){message timestamp}}"}'

# 驗證網頁可訪問
curl -s "https://<SUBDOMAIN>.zeabur.app/" -w "\nHTTP: %{http_code}\n"
```

成功指標：
- 服務狀態：`RUNNING`
- 日誌中出現：`[gateway] listening on ws://0.0.0.0:3000`
- 網頁回傳 HTTP 200 + OpenClaw Control UI

## 踩坑記錄

### 問題 1: Container Crash — 缺少 OPENCLAW_GATEWAY_TOKEN
- **症狀**：`Gateway auth is set to token, but no token is configured`
- **原因**：OpenClaw 預設使用 token 認證模式，未設定則拒絕啟動
- **解法**：設定 `OPENCLAW_GATEWAY_TOKEN` 環境變數

### 問題 2: 502 Bad Gateway — Port 不匹配
- **症狀**：服務 RUNNING 但網頁 502
- **原因**：Zeabur 期望 port 3000，OpenClaw 預設 18789
- **解法**：設定 `OPENCLAW_GATEWAY_PORT=3000` 環境變數
- **技術細節**：`resolveGatewayPort()` 在 `src/config/paths.ts` 中讀取此環境變數

### 問題 3: 502 Bad Gateway — Bind 在 loopback
- **症狀**：日誌顯示 `listening on ws://127.0.0.1:3000` 但網頁 502
- **原因**：Gateway CLI (`src/cli/gateway-cli/run.ts`) 不讀取 `OPENCLAW_GATEWAY_BIND` 環境變數
- **解法**：使用 `updateServiceCommand` 傳入 `--bind lan` CLI 參數
- **注意**：只有 macOS daemon 和 docker-compose 讀取 `OPENCLAW_GATEWAY_BIND` 環境變數

### 問題 4: Domain UNAVAILABLE — 子域名格式錯誤
- **症狀**：`addDomain` 回傳 `DOMAIN_UNAVAILABLE` 或 `UNSUPPORTED_DOMAIN_NAME`
- **原因**：`isGenerated: true` 時只需傳子域名部分（如 `myapp`），不是完整域名（`myapp.zeabur.app`）
- **解法**：先用 `checkDomainAvailable` 驗證，再用正確格式呼叫 `addDomain`

### 問題 5: HTTP 401 Invalid Authentication — Kimi API Key 設定錯誤
- **症狀**：Telegram Bot 回覆 `HTTP 401: Invalid Authentication`
- **原因**：Kimi 有兩個不同平台，API Key 和 endpoint 不同：
  - **Kimi Coding 國際版**：key 格式 `sk-kimi-*`，env var `KIMI_API_KEY`，model `kimi-coding/k2p5`
  - **Moonshot Open Platform 中國版**：key 格式 `sk-*`（無 kimi），env var `MOONSHOT_API_KEY`，model `moonshot/kimi-k2.5`
- **解法**：確認 key 格式，使用對應的 env var 名稱和 model 名稱。`sk-kimi-*` 開頭的 key 必須用 `KIMI_API_KEY` + `kimi-coding/k2p5`

### 問題 6: Zeabur Shared Cluster 拒絕 OpenClaw
- **症狀**：`REQUIRE_DEDICATED_SERVER` 錯誤
- **原因**：OpenClaw Docker image 被 Zeabur 標記為需要專用伺服器
- **解法**：建立專案時使用 `region: "server-<serverID>"` 指定專用伺服器

## Zeabur GraphQL API 速查

| 操作 | Mutation/Query |
|------|---------------|
| 驗證身份 | `query{user{name username}}` |
| 列出伺服器 | `query{servers{_id hostname status ip}}` |
| 建立專案 | `mutation{createProject(region,name){_id}}` |
| 部署模板 | `mutation{deployTemplate(projectID,rawSpecYaml){_id}}` |
| 建立環境變數 | `mutation{createEnvironmentVariable(serviceID,environmentID,key,value){key value}}` |
| 更新啟動指令 | `mutation{updateServiceCommand(serviceID,command)}` |
| 重啟服務 | `mutation{restartService(serviceID,environmentID)}` |
| 檢查域名可用 | `mutation{checkDomainAvailable(domain,isGenerated,region){isAvailable reason}}` |
| 綁定域名 | `mutation{addDomain(serviceID,environmentID,isGenerated,domain){domain}}` |
| 查詢服務狀態 | `query{service(_id){name status}}` |
| 查詢日誌 | `query{runtimeLogs(projectID,serviceID,environmentID){message timestamp}}` |
| 列出專案 | `query{projects{edges{node{_id name services{_id name domains{domain}}}}}}` |

## 程式與文件清單

| 檔案 | 說明 |
|------|------|
| `openclaw-template.yaml` | Zeabur 部署 YAML 模板 |
| `deploy.py` | 一鍵部署自動化腳本 |
| `01-security-audit.md` | 資安設定報告 |
| `02-features.md` | 功能說明文件 |
| `03-deployment-guide.md` | 本文件 |
| `04-user-guide.md` | 使用者指南 |

## 部署實例範例

| 項目 | 值 |
|------|-----|
| Domain | `https://<subdomain>.zeabur.app` |
| Project ID | `<from createProject>` |
| Service ID | `<from deployTemplate>` |
| Environment ID | `<from deployTemplate>` |
| Server ID | `<from servers query>` |
| Image | `ghcr.io/openclaw/openclaw:2026.2.2` |
| Gateway Port | 3000 |
| Gateway Bind | 0.0.0.0 (lan) |
| Start Command | `node dist/index.js gateway --allow-unconfigured --bind lan` |
