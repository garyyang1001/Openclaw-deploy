# EasyClaw OpenClaw 部署 — 資安設定報告

## 1a. 目前資安設定狀態

### 已套用的安全設定

| 項目 | 設定值 | 狀態 |
|------|--------|------|
| Gateway 認證模式 | Token (`OPENCLAW_GATEWAY_TOKEN`) | 已啟用 |
| Gateway Token | `easyclaw-gw-2026` (16字元) | 需加強 |
| 綁定模式 | `--bind lan` (0.0.0.0) | 已設定 |
| HTTPS | 透過 Zeabur 自動 SSL | 已啟用 |
| DM 政策 | `pairing`（預設） | 安全 |
| 群組政策 | `allowlist`（預設） | 安全 |

### 需改善項目

1. **Gateway Token 強度不足**
   - 目前：`easyclaw-gw-2026`（16 字元）
   - 建議：至少 32 字元以上的隨機字串
   - OpenClaw 即將強制要求外部綁定必須使用 >=32 字元 Token（PR #9626）

2. **尚未設定 AI API Key**
   - 需要用戶提供 Kimi K2.5 API Key
   - 未設定時 AI 功能無法使用

3. **尚未串接任何通訊頻道**
   - Telegram、WhatsApp 等均未設定
   - 需要用戶提供各平台 Token

## 1b. 資安標準規範

### OpenClaw 安全架構層級

```
第 1 層：網路存取控制
├── Gateway 綁定模式（loopback/lan/tailnet）
├── HTTPS（Zeabur 自動提供）
└── Firewall（Zeabur 專用伺服器層級）

第 2 層：Gateway 認證
├── Token 模式（Bearer Token）
├── Password 模式（密碼認證）
└── Tailscale 整合（Tailnet 內認證）

第 3 層：頻道存取控制
├── DM 配對制度（pairing）
├── 允許清單（allowlist）
└── 群組提及閘門（mention gating）

第 4 層：工具權限控制
├── 沙箱隔離（sandbox）
├── 工具允許/拒絕清單
└── 檔案系統存取控制

第 5 層：模型安全
├── 提示注入防護
├── 推理內容隱藏
└── 敏感資料遮蔽
```

### 安全基準設定（建議）

```json5
{
  gateway: {
    bind: "lan",
    auth: { mode: "token", token: "<至少32字元隨機字串>" }
  },
  channels: {
    telegram: {
      dmPolicy: "pairing",         // 新聯絡人需配對碼
      groupPolicy: "allowlist"      // 群組限定已授權者
    }
  },
  agents: {
    defaults: {
      sandbox: { mode: "non-main" } // 工具在沙箱中執行
    }
  },
  logging: {
    redactSensitive: "tools"        // 工具輸出自動遮蔽敏感資料
  }
}
```

## 1c. 能做與不能做

### 安全方面能做的事

| 功能 | 說明 |
|------|------|
| 配對制度 | 陌生人必須取得配對碼才能與 Bot 對話 |
| 允許清單 | 指定哪些用戶可以使用 Bot |
| 群組提及閘門 | Bot 在群組中只回應被 @ 的訊息 |
| 沙箱隔離 | AI 執行的程式碼在隔離容器中運行 |
| 工具限制 | 可針對不同代理設定不同的工具權限 |
| 安全稽核 | `openclaw security audit --deep` 自動檢查安全風險 |
| 憑證輪替 | Token/密碼可隨時更換 |
| 日誌遮蔽 | 自動遮蔽 API Key、密碼等敏感資料 |

### 安全方面不能做的事

| 限制 | 說明 |
|------|------|
| 端對端加密 | OpenClaw 不提供 E2E 加密（依賴各通訊平台自身的加密） |
| 訊息審計 | 無內建合規審計功能（需自行查看日誌） |
| 多因素認證 | Gateway 不支援 MFA |
| IP 白名單 | 需在 Zeabur/Firewall 層級設定 |
| 自動威脅偵測 | 無 IDS/IPS 功能 |

### 用戶資料安全

- **資料儲存位置**：所有資料存在 Zeabur 專用伺服器（IP: 43.167.222.48）
- **Session 紀錄**：`~/.openclaw/agents/<agentId>/sessions/*.jsonl`
- **設定檔**：`~/.openclaw/openclaw.json`
- **權限**：檔案權限 600（僅擁有者可讀寫）
- **磁碟加密**：依 Zeabur 伺服器設定

### 客戶端安全保證

如果是幫客戶部署在客戶自己的 Zeabur 帳號：
1. **Token 可撤銷**：客戶隨時可在 Zeabur 後台撤銷 API Token
2. **資料在客戶帳號**：所有資料存在客戶自己的帳號內
3. **我們無法存取**：部署完成後，除非客戶再次提供 Token，否則我們無法存取
4. **獨立隔離**：每個客戶的 OpenClaw 實例完全獨立
