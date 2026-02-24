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
| `update.py` | 抓取 RTHK 網站最新集數，更新 `episodes.json` |
| `download_qualified.py` | 下載符合主持人條件且未上傳的 MP3 |
| `upload_all_to_ia.py` | 上傳 MP3 到 Internet Archive，更新 `ia_mapping.json` |
| `generate_rss.py` | 從 `ia_mapping.json` 生成 RSS feed XML |
| `daily_update_ia.sh` | 整合所有步驟，完成後發送 Telegram 通知 |
| `telegram_notify.py` | Telegram 通知模組 |

## 恢復系統（Sandbox 重置後）

```bash
# 1. 從 GitHub 恢復所有腳本和 JSON 記錄
git clone https://github.com/bunfung/my-rthk-podcast.git /home/ubuntu/rthk_podcast

# 2. 建立 MP3 目錄
mkdir -p /home/ubuntu/rthk_podcast/mp3

# 3. 設定 git 認證（從 .env 讀取 token）
cd /home/ubuntu/rthk_podcast
source .env
git remote set-url origin https://${GITHUB_TOKEN}@github.com/bunfung/my-rthk-podcast.git
git config --global user.email "bunfung.any@gmail.com"
git config --global user.name "bunfung"

# 4. 安裝依賴
sudo pip3 install requests internetarchive

# 5. 設定 IA credentials
mkdir -p ~/.config/internetarchive
cat > ~/.config/internetarchive/ia.ini << 'EOF'
[s3]
access=kFTwDB2nXEGiWNYZ
secret=gPTTPew6CA8WyEXn

[cookies]
logged-in-user=bunfung.any@gmail.com
EOF

# 6. 手動測試執行
cd /home/ubuntu/rthk_podcast && bash daily_update_ia.sh
```

## 每日排程設定

使用 Manus schedule tool 設定：
- **類型：** cron
- **表達式：** `0 0 9 * * *`（每日 09:00 HKT）
- **執行內容：** 執行 `/home/ubuntu/rthk_podcast/daily_update_ia.sh`

## Internet Archive 上傳流程

`upload_all_to_ia.py` 使用 IA S3 API：

1. 讀取 `spotify_episode_mapping.json` 獲取 rthk_id 列表
2. 跳過已在 `ia_mapping.json` 中的集數
3. 用 HTTP PUT 上傳到 `https://s3.us.archive.org/{item_id}/{filename}`
4. item_id 格式：`rthk-jiang-dong-jiang-xi-{rthk_id}`
5. metadata 中文字符需用 `uri(quote(value))` 格式
6. 上傳成功後記錄到 `ia_mapping.json`

## RSS Feed 生成

`generate_rss.py` 從 `ia_mapping.json` 生成標準 RSS 2.0 + iTunes podcast feed：
- 音頻 URL：`https://archive.org/download/{item_id}/{rthk_id}_0.mp3`
- 部署到 GitHub Pages：`https://bunfung.github.io/my-rthk-podcast/feed.xml`

## 本地 JSON 記錄

| 檔案 | 格式 | 用途 |
|------|------|------|
| `episodes.json` | `[{id, title, date, audio_urls, ...}]` | 所有已知集數（含主持人篩選） |
| `spotify_episode_mapping.json` | `[{rthk_id, title, date, spotify_id}]` | 已上傳到 Spotify 的記錄（含 rthk_id） |
| `ia_mapping.json` | `{rthk_id: {item_id, url, title, date}}` | 已上傳到 IA 的記錄 |

每次更新後自動 `git push` 到 GitHub，確保記錄持久化。

## Telegram 通知格式

```
🎙️ RTHK 講東講西 Podcast 每日更新報告
📅 2026-02-24 09:05

📋 新集數：1 集
⬇️ 已下載：1 個 MP3
⬆️ 成功上傳：1 集
☁️ IA 總集數：22 集

✅ 今日更新完成！

🔗 RSS: https://bunfung.github.io/my-rthk-podcast/feed.xml

— Manus 自動通知系統
```

## 常見問題排查

| 問題 | 原因 | 解決方法 |
|------|------|----------|
| IA 上傳 UnicodeEncodeError | HTTP header 不支援中文 | 用 `uri(quote(value))` 格式編碼 metadata |
| IA 上傳 403 | credentials 錯誤 | 確認 `~/.config/internetarchive/ia.ini` 設定正確 |
| git push 失敗（secrets detected） | 腳本中有硬編碼 token | 確保 token 只在 `.env` 中，腳本用 `source .env` 讀取 |
| git push 失敗（token 過期） | GitHub PAT 過期 | 到 GitHub Settings 重新生成 Personal Access Token，更新 `.env` |
| RSS feed 無法訪問 | GitHub Pages 未啟用 | 到 repo Settings → Pages → 設定 Source 為 main branch |
| Telegram 未收到通知 | Bot Token 或 Chat ID 錯誤 | 用 `getUpdates` API 重新確認 Chat ID |
