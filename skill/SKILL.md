---
name: rthk-podcast-automation
description: 自動化抓取 RTHK 《講東講西》節目集數、下載 MP3、上傳到 Internet Archive、生成 RSS feed 並部署到 GitHub Pages，每日自動更新並發送 Telegram 通知。適用於：設定或恢復 RTHK podcast 自動化系統、處理新集數上傳、管理 RSS feed、設定每日排程通知。
---

# RTHK 講東講西 Podcast 自動化系統

## 系統概覽

自動化流程：RTHK 網站 → 篩選主持人 → 下載 MP3 → 上傳 Internet Archive → 更新 ia_mapping.json → 生成 RSS feed → git push → Telegram 通知

**主持人篩選條件：** 蘇奭、邱逸、馬鼎盛、馮天樂（四選一）

## 關鍵設定參數

| 參數 | 值 |
|------|-----|
| RTHK 頻道 | `radio1` / `Free_as_the_wind` |
| 工作目錄 | `/home/ubuntu/rthk_podcast/` |
| MP3 目錄 | `/home/ubuntu/rthk_podcast/mp3/` |
| GitHub Repo | `bunfung/my-rthk-podcast` |
| RSS Feed URL | `https://bunfung.github.io/my-rthk-podcast/feed.xml` |
| IA Account | `bunfung.any@gmail.com` |
| IA Access Key | `kFTwDB2nXEGiWNYZ` |
| IA Secret Key | `gPTTPew6CA8WyEXn` |
| Telegram Bot Token | `8634320454:AAH6IpV7uN6-y_Gzd731Xm3O1-D76UCdnzQ` |
| Telegram Chat ID | `220866475` |
| Cron 時間 | 每日 09:00 HKT |

## 腳本說明

| 腳本 | 用途 |
|------|------|
| `update.py` | 抓取 RTHK 網站最新集數，只處理比 `last_checked_date` 更新的集數，更新 `episodes.json` 和 `last_checked.json` |
| `upload_all_to_ia.py` | 上傳本地 MP3 到 Internet Archive，更新 `ia_mapping.json`（讀取 `episodes.json`） |
| `generate_rss.py` | 從 `ia_mapping.json` 生成 RSS feed XML |
| `daily_update_ia.sh` | 整合所有步驟，完成後發送 Telegram 通知（包含今日新增集數名稱） |

## 核心邏輯：避免重複下載

**重要：** RTHK 集數 ID 係全台共用流水號（唔係《講東講西》專用），唔能用來判斷新舊。

正確邏輯：
1. `last_checked.json` 記錄上次檢查到的最新**日期**（唔係 ID）
2. `update.py` 每次只抓取比 `last_checked_date` 更新的集數
3. 符合主持人條件 → 加入 `episodes.json`
4. 唔符合條件 → 唔加入，但 `last_checked_date` 仍然更新
5. `upload_all_to_ia.py` 只上傳 `episodes.json` 有但 `ia_mapping.json` 冇的集數
6. **sandbox 重置後本地 MP3 會消失，但 `ia_mapping.json` 有記錄就代表已上傳，唔需要重新下載**

## 本地 JSON 記錄

| 檔案 | 格式 | 用途 | 是否在 GitHub |
|------|------|------|--------------|
| `episodes.json` | `[{id, title, date, audio_urls, ...}]` | 符合主持人條件的集數 | ✅ 是 |
| `ia_mapping.json` | `{ep_id: {item_id, url, title, date}}` | 已上傳到 IA 的記錄 | ✅ 是 |
| `last_checked.json` | `{last_checked_date, last_checked_title, ...}` | 上次檢查到的最新日期 | ✅ 是 |
| `.env` | `KEY=VALUE` | 所有 credentials | ❌ 否（.gitignore） |

每次更新後自動 `git push` 到 GitHub，確保記錄持久化。

## 恢復系統（Sandbox 重置後）

```bash
# 1. 從 GitHub 恢復所有腳本和 JSON 記錄
git clone https://github.com/bunfung/my-rthk-podcast.git /home/ubuntu/rthk_podcast

# 2. 建立 MP3 目錄
mkdir -p /home/ubuntu/rthk_podcast/mp3

# 3. 重建 .env（sandbox 重置後會消失）
cat > /home/ubuntu/rthk_podcast/.env << 'EOF'
GITHUB_TOKEN=<your_github_pat_here>
TELEGRAM_BOT_TOKEN=8634320454:AAH6IpV7uN6-y_Gzd731Xm3O1-D76UCdnzQ
TELEGRAM_CHAT_ID=220866475
IA_ACCESS_KEY=kFTwDB2nXEGiWNYZ
IA_SECRET_KEY=gPTTPew6CA8WyEXn
EOF

# 4. 設定 git 認證
cd /home/ubuntu/rthk_podcast
source .env
git remote set-url origin "https://${GITHUB_TOKEN}@github.com/bunfung/my-rthk-podcast.git"
git config user.email "bunfung.any@gmail.com"
git config user.name "bunfung"
git pull origin main

# 5. 安裝依賴
sudo pip3 install requests internetarchive beautifulsoup4 -q

# 6. 設定 IA credentials
mkdir -p ~/.config/internetarchive
cat > ~/.config/internetarchive/ia.ini << 'EOF'
[s3]
access=kFTwDB2nXEGiWNYZ
secret=gPTTPew6CA8WyEXn

[cookies]
logged-in-user=bunfung.any@gmail.com
EOF

# 7. 手動測試執行
cd /home/ubuntu/rthk_podcast && bash daily_update_ia.sh
```

## 每日排程設定

使用 Manus schedule tool 設定：
- **類型：** cron
- **表達式：** `0 0 9 * * *`（每日 09:00 HKT）
- **Prompt 必須包含：** 重建 `.env`、設定 git 認證、安裝依賴、執行 `daily_update_ia.sh`

## Internet Archive 上傳流程

`upload_all_to_ia.py` 使用 IA S3 API：

1. 讀取 `episodes.json` 獲取集數列表
2. 跳過已在 `ia_mapping.json` 中的集數
3. 只上傳本地有 MP3 的集數
4. 用 HTTP PUT 上傳到 `https://s3.us.archive.org/{item_id}/{filename}`
5. item_id 格式：`rthk-jiang-dong-jiang-xi-{ep_id}`
6. metadata 中文字符需用 `uri(quote(value))` 格式
7. 上傳成功後記錄到 `ia_mapping.json`

## RSS Feed 生成

`generate_rss.py` 從 `ia_mapping.json` 生成標準 RSS 2.0 + iTunes podcast feed：
- 音頻 URL：`https://archive.org/download/{item_id}/{ep_id}_0.mp3`
- Logo：`https://bunfung.github.io/my-rthk-podcast/podcast_logo.jpg`（1400x1400 正方形，符合 iTunes 標準）
- 部署到 GitHub Pages：`https://bunfung.github.io/my-rthk-podcast/feed.xml`

## Telegram 通知格式

```
🎙️ RTHK 講東講西 Podcast 每日更新報告
📅 2026-02-26 09:05

📋 新集數：1 集
⬇️ 已下載：1 個 MP3
⬆️ 成功上傳：1 集
☁️ IA 總集數：22 集

📝 今日上傳集數：
  • 新集數標題 (26/02/2026)

✅ 今日更新完成！

🔗 RSS: https://bunfung.github.io/my-rthk-podcast/feed.xml

— Manus 自動通知系統
```

## 常見問題排查

| 問題 | 原因 | 解決方法 |
|------|------|----------|
| 每次都重複下載大量 MP3 | 用本地 MP3 判斷是否需要下載（sandbox 重置後本地是空的） | 改用 `ia_mapping.json` 判斷（已上傳就唔需要下載） |
| IA 上傳 UnicodeEncodeError | HTTP header 不支援中文 | 用 `uri(quote(value))` 格式編碼 metadata |
| IA 上傳 403 | credentials 錯誤 | 確認 `~/.config/internetarchive/ia.ini` 設定正確 |
| git push 失敗（secrets detected） | 腳本中有硬編碼 token | 確保 token 只在 `.env` 中，腳本用 `source .env` 讀取 |
| git push 失敗（需要輸入密碼） | git remote URL 冇包含 token | 執行 `git remote set-url origin "https://${GITHUB_TOKEN}@github.com/..."` |
| git push 失敗（token 過期） | GitHub PAT 過期 | 到 GitHub Settings 重新生成 Personal Access Token，更新 `.env` |
| RSS feed 無法訪問 | GitHub Pages 未啟用 | 到 repo Settings → Pages → 設定 Source 為 main branch |
| Telegram 未收到通知 | Bot Token 或 Chat ID 錯誤 | 用 `getUpdates` API 重新確認 Chat ID |
| .env 消失 | sandbox 重置後 .gitignore 的檔案會消失 | schedule job prompt 每次執行前自動重建 .env |
