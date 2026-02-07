# OpenClaw v2026.2.2 功能說明

## 2a. 功能權限範圍

### 能做的事

#### AI 對話
- 與 AI 助理進行自然語言對話
- 支援長上下文（最高 256K token）
- 支援思考模式（reasoning/thinking）
- 支援多模型切換（`/model` 指令）
- 支援多代理路由（不同頻道/用戶可分配不同代理）

#### 通訊平台整合
- 同時連接多個通訊平台
- 支援私訊和群組對話
- 支援媒體（圖片、音訊、影片）傳送與接收
- 支援串流回應（即時顯示 AI 回答）

#### 工具能力
- **瀏覽器控制**：自動瀏覽網頁、截圖、填表
- **檔案操作**：讀寫編輯檔案
- **程式執行**：在沙箱中執行程式碼
- **網路搜尋**：透過 Brave API 搜尋網路
- **URL 擷取**：抓取網頁內容並分析
- **排程任務**：設定定時任務（cron jobs）
- **Webhook**：接收外部系統通知

#### 進階功能
- **Canvas 畫布**：AI 可產生互動式視覺內容
- **語音模式**：語音輸入/輸出（需 ElevenLabs API）
- **技能系統**：安裝/管理 AI 技能包
- **Session 管理**：多對話管理、歷史回顧

### 不能做的事

| 限制 | 說明 |
|------|------|
| 無法主動發起對話 | AI 只能回應訊息，不能主動找人聊天（除了排程任務） |
| 無法處理即時通話 | 不支援語音/視訊通話（只支援語音訊息） |
| 無法存取本地裝置 | 除非安裝 macOS/iOS/Android node |
| 無法突破 AI 限制 | 受 AI 模型自身的安全限制約束 |
| 無法無限制使用 | 受 AI API 配額和費用限制 |
| 無法保證即時回應 | AI 處理需要時間，尤其是複雜任務 |

## 2b. 支援串接的項目

### 通訊平台（20 個）

| 平台 | 類型 | 狀態 |
|------|------|------|
| Telegram | 內建 | 推薦首選 |
| WhatsApp | 內建 | QR 碼配對 |
| Discord | 內建 | Bot API |
| Slack | 內建 | Bolt SDK |
| Google Chat | 內建 | API |
| Signal | 內建 | signal-cli |
| BlueBubbles (iMessage) | 內建 | 推薦用於 iMessage |
| Microsoft Teams | 插件 | Bot Framework |
| LINE | 插件 | Messaging API |
| Matrix | 插件 | Matrix 協議 |
| Feishu/Lark | 插件 | WebSocket |
| Mattermost | 插件 | Bot API |
| Nextcloud Talk | 插件 | 自架 |
| Nostr | 插件 | 去中心化 |
| Twitch | 插件 | IRC |
| Zalo | 插件 | 越南通訊 |
| Zalo Personal | 插件 | QR 登入 |
| WebChat | 內建 | 網頁介面 |
| iMessage (legacy) | 內建 | macOS 限定 |
| Tlon | 插件 | Urbit |

### AI 模型供應商

| 供應商 | 環境變數 | 代表模型 |
|--------|----------|----------|
| Anthropic | `ANTHROPIC_API_KEY` | Claude Opus 4.6, Sonnet 4.5 |
| OpenAI | `OPENAI_API_KEY` | GPT-4o, o3 |
| Moonshot | `MOONSHOT_API_KEY` | Kimi K2.5, K2-thinking |
| Kimi Coding | `KIMI_API_KEY` | kimi-k2-code |
| Google | `GEMINI_API_KEY` | Gemini 2.5 |
| OpenRouter | `OPENROUTER_API_KEY` | 多模型路由 |
| Groq | `GROQ_API_KEY` | 快速推理 |
| MiniMax | `MINIMAX_API_KEY` | 寫作專長 |
| Cerebras | `CEREBRAS_API_KEY` | 快速推理 |

### 外部服務

| 服務 | 環境變數 | 用途 |
|------|----------|------|
| Brave Search | `BRAVE_API_KEY` | 網路搜尋 |
| ElevenLabs | `ELEVENLABS_API_KEY` | 語音合成 |
| Firecrawl | `FIRECRAWL_API_KEY` | 網頁抓取 |

## 2c. 完整功能清單

### Gateway 功能
- WebSocket 控制平面
- 多代理路由
- Session 管理（main/per-channel-peer/per-session）
- 自動重連與容錯
- 健康檢查與自我診斷（`openclaw doctor`）
- 自動更新通知

### 通訊功能
- 多平台同時連接
- 私訊配對制度
- 群組提及閘門
- 訊息串流顯示
- 媒體處理（圖片/音訊/影片）
- 訊息分塊傳送（超長訊息自動分段）

### AI 功能
- 多模型切換（`/model`）
- 模型容錯備援（failover）
- 思考模式（extended thinking）
- 工具呼叫（function calling）
- 記憶搜尋（memory）
- 上下文剪裁（session pruning）

### 自動化功能
- Cron 排程任務
- Webhook 接收器
- Gmail 監控（Pub/Sub）
- 瀏覽器自動化

### 管理功能
- Web 控制台（Control UI）
- WebChat 網頁聊天
- 安全稽核工具
- 日誌管理
- 設定熱更新
