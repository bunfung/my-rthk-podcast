---
name: rthk-podcast-automation
description: 自動化抓取 RTHK 《講東講西》節目集數、下載 MP3、上傳到 Spotify for Creators 並發送 Telegram 每日通知。適用於：設定或恢復 RTHK podcast 自動化系統、處理新集數上傳、管理 Spotify episodes、設定每日排程通知。
---

# RTHK 講東講西 Podcast 自動化系統

## 系統概覽

自動化流程：RTHK 網站 → 篩選主持人 → 下載 MP3 → 上傳 Spotify → 刪除 MP3 → git push → Telegram 通知

**主持人篩選條件：** 蘇奭、邱逸、馬鼎盛、馮天樂（四選一）

## 關鍵設定參數

| 參數 | 值 |
|------|-----|
| Spotify Show ID | `6DVYbYCCvSBreKzyStsnFp` |
| RTHK 頻道 | `radio1` / `Free_as_the_wind` |
| 工作目錄 | `/home/ubuntu/rthk_podcast/` |
| MP3 目錄 | `/home/ubuntu/rthk_podcast/mp3/` |
| GitHub Repo | `bunfung/my-rthk-podcast` |
| GitHub Token | `REMOVED_TOKEN` |
| Telegram Bot Token | `8634320454:AAH6IpV7uN6-y_Gzd731Xm3O1-D76UCdnzQ` |
| Telegram Chat ID | `220866475` |
| RSS Feed URL | `https://anchor.fm/s/10f5e7a94/podcast/rss` |
| Cron 時間 | 每日 08:00 |

## 腳本說明

| 腳本 | 用途 |
|------|------|
| `scripts/update.py` | 抓取 RTHK 網站最新集數，更新 `episodes.json` |
| `scripts/download_qualified.py` | 下載符合主持人條件且未上傳的 MP3 |
| `scripts/auto_upload.py` | 用 CDP 自動上傳 MP3 到 Spotify，上傳後刪除 MP3，完成後 git push |
| `scripts/daily_update.sh` | 整合以上三個步驟，完成後發送 Telegram 通知 |
| `scripts/telegram_notify.py` | Telegram 通知模組 |

## 恢復系統（Sandbox 重置後）

```bash
# 1. 從 GitHub 恢復所有腳本和 JSON 記錄
git clone https://github.com/bunfung/my-rthk-podcast.git /home/ubuntu/rthk_podcast

# 2. 建立 MP3 目錄
mkdir -p /home/ubuntu/rthk_podcast/mp3

# 3. 設定 git 認證
cd /home/ubuntu/rthk_podcast
git remote set-url origin https://REMOVED_TOKEN@github.com/bunfung/my-rthk-podcast.git
git config --global user.email "bunfung.any@gmail.com"
git config --global user.name "bunfung"

# 4. 安裝依賴
sudo pip3 install requests websocket-client websockets

# 5. 啟動 Chrome（CDP 模式）
chromium-browser --headless --remote-debugging-port=9222 --no-sandbox &
sleep 3

# 6. 手動測試執行
cd /home/ubuntu/rthk_podcast && bash daily_update.sh
```

## 每日排程設定

使用 Manus schedule tool 設定：
- **類型：** cron
- **表達式：** `0 0 8 * * *`（每日 08:00）
- **執行內容：** 執行 `/home/ubuntu/rthk_podcast/daily_update.sh`

## Spotify 上傳流程（CDP 自動化）

`auto_upload.py` 使用 Chrome DevTools Protocol (CDP) 控制瀏覽器：

1. 導航到 `https://creators.spotify.com/pod/show/{SHOW_ID}/episode/wizard`
2. 用 `DOM.setFileInputFiles` 設置 MP3 檔案
3. 等待上傳完成後點擊 Next
4. 用 React setter 填入標題（格式：`{集數標題} - {DD/MM/YYYY}`）
5. 用 `Input.insertText` CDP 方法填入描述到 ProseMirror 編輯器
6. 進入 Review 頁面，選擇 Now，點擊 Publish
7. 確認「Episode published!」後刪除本地 MP3

**重要：** 描述欄必須用 `Input.insertText` CDP 方法，普通 JS `innerHTML` 無法觸發 React 狀態更新。

## 本地 JSON 記錄

| 檔案 | 格式 | 用途 |
|------|------|------|
| `episodes.json` | `[{id, title, date, url, ...}]` | 所有已知集數 |
| `spotify_episode_mapping.json` | `{ep_id: {title, date, uploaded_at}}` | 已上傳到 Spotify 的記錄 |

每次上傳後自動 `git push` 到 GitHub，確保記錄持久化。

## Telegram 通知格式

```
🎙️ RTHK 講東講西 Podcast 每日更新報告
📅 2026-02-24 08:05

📋 新集數：1 集
⬇️ 已下載：1 個 MP3
⬆️ 成功上傳：1 集

✅ 今日更新完成！

— Manus 自動通知系統
```

## 常見問題排查

| 問題 | 原因 | 解決方法 |
|------|------|----------|
| Chrome CDP 無法連接 | Chrome 未啟動 | 執行 `chromium-browser --headless --remote-debugging-port=9222 --no-sandbox &` |
| 描述欄 0/4000 | React 未識別輸入 | 確保用 `Input.insertText` CDP 方法，而非 JS innerHTML |
| git push 失敗 | Token 過期 | 到 GitHub Settings 重新生成 Personal Access Token |
| 上傳後 episode 仍是 Untitled | 標題填入失敗 | 檢查 `#title-input` selector 是否仍有效 |
| Telegram 未收到通知 | Bot Token 或 Chat ID 錯誤 | 用 `getUpdates` API 重新確認 Chat ID |
