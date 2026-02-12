# OpenClaw 客製化工作流（GitHub + Zeabur）

這份文件把「部署 repo」和「runtime repo」分開，避免雲端手改造成設定漂移。

## 1. Repo 分工（固定）

- 部署 repo（本專案）：
  - `/Users/goodjob/Desktop/openclaw-deploy/Openclaw-deploy/deploy.py`
  - `/Users/goodjob/Desktop/openclaw-deploy/Openclaw-deploy/openclaw-template.yaml`
  - 用途：建立服務、更新 image、設定 env/start command。
- runtime repo（新建，建議 fork `openclaw/openclaw`）：
  - 用途：OpenClaw 程式碼客製（含 multi-agent）。
  - Zeabur 的「GitHub 儲存庫綁定」應該綁這個 repo。

## 2. 第一次初始化 runtime repo

在部署 repo 根目錄執行（會建立 `runtime/openclaw-runtime`）：

```bash
chmod +x scripts/bootstrap_runtime_repo.sh
scripts/bootstrap_runtime_repo.sh \
  --fork-url https://github.com/<your-org>/<your-runtime-repo>.git
```

腳本會自動完成：

- clone 你的 runtime fork（remote `origin`）
- 設定官方 repo 為 `upstream`（`https://github.com/openclaw/openclaw.git`）
- 抓取 `origin/upstream` 最新內容
- 建立/切換本地 `main` 並追蹤 `origin/main`

## 3. 日常開發（客製功能，例如 multi-agent）

```bash
cd runtime/openclaw-runtime
git checkout -b feat/multi-agent
# 修改程式碼
git add .
git commit -m "feat: add multi-agent runtime structure"
git push -u origin feat/multi-agent
```

完成 review 後合併到 `main`，讓 Zeabur 從 `main` 自動部署。

## 4. 同步官方 openclaw 更新

在 runtime repo 且 working tree 乾淨時執行：

```bash
chmod +x ../scripts/sync_upstream_openclaw.sh
../scripts/sync_upstream_openclaw.sh
```

腳本會：

- 更新本地 `main` 到 `origin/main`（只允許 fast-forward）
- 建立 `sync/upstream-YYYYMMDD` 分支
- 把 `upstream/main` 合併進 sync 分支

接著：

```bash
git push -u origin sync/upstream-YYYYMMDD
```

然後在 GitHub 開 PR：`sync/upstream-YYYYMMDD -> main`。

## 5. Zeabur 綁定建議

- 服務來源：選「GitHub 儲存庫」
- Repo：選 runtime repo（不是部署 repo）
- Branch：`main`（正式環境）
- Auto Deploy：開啟

這樣流程就會是：

1. runtime repo 合併到 `main`
2. Zeabur 自動部署
3. 若要調整部署參數（env/start command/image），回部署 repo 調整並執行部署腳本

## 6. 你的三個需求對應到哪裡改

1. 更新 `openclaw/openclaw`
   - 在 runtime repo 跑 `sync_upstream_openclaw.sh`
2. 調整設定
   - 部署層設定：改部署 repo（`deploy.py`、template、env）
   - 程式層設定：改 runtime repo
3. 建立 multi-agent 架構
   - 主要在 runtime repo 開發（`feat/*` 分支）

## 7. 禁止事項（避免踩坑）

- 不要直接在 Zeabur 容器裡手改檔案當正式流程
- 不要把 runtime 客製直接塞回部署 repo 主線
- 不要讓 Zeabur 正式服務追蹤 feature 分支
