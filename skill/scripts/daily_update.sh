#!/bin/bash
# 每日自動更新 RTHK 《講東講西》Podcast 腳本
# 1. 從 GitHub pull 最新 JSON 記錄
# 2. 更新集數列表
# 3. 下載新 MP3
# 4. 上傳到 Spotify（上傳後自動刪除 MP3 並 push 到 GitHub）
# 5. 發送 Telegram 通知報告

LOG_FILE="/home/ubuntu/rthk_podcast/daily_update.log"
SCRIPT_DIR="/home/ubuntu/rthk_podcast"
TELEGRAM_BOT_TOKEN="8634320454:AAH6IpV7uN6-y_Gzd731Xm3O1-D76UCdnzQ"
TELEGRAM_CHAT_ID="220866475"

# 統計變數
NEW_EPISODES=0
DOWNLOADED=0
UPLOADED=0
FAILED=0
ERRORS=""

send_telegram() {
    local message="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "parse_mode=HTML" \
        --data-urlencode "text=${message}" > /dev/null 2>&1
}

echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 開始每日更新" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$SCRIPT_DIR"

# 步驟 0: 從 GitHub pull 最新記錄
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟0] 從 GitHub 同步最新記錄..." >> "$LOG_FILE"
git pull origin main >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [警告] git pull 失敗，繼續使用本地記錄" >> "$LOG_FILE"
fi

# 記錄更新前的集數數量
BEFORE_COUNT=$(python3 -c "import json; data=json.load(open('episodes.json')); print(len(data))" 2>/dev/null || echo "0")

# 步驟 1: 更新集數列表
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟1] 更新集數列表..." >> "$LOG_FILE"
python3 update.py >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [錯誤] 更新集數列表失敗" >> "$LOG_FILE"
    send_telegram "🚨 <b>RTHK Podcast 更新失敗</b>
📅 $(date '+%Y-%m-%d %H:%M')

❌ 步驟1：更新集數列表失敗

— Manus 自動通知系統"
    exit 1
fi

# 計算新增集數
AFTER_COUNT=$(python3 -c "import json; data=json.load(open('episodes.json')); print(len(data))" 2>/dev/null || echo "0")
NEW_EPISODES=$((AFTER_COUNT - BEFORE_COUNT))
if [ $NEW_EPISODES -lt 0 ]; then NEW_EPISODES=0; fi

# 步驟 2: 下載新 MP3
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟2] 下載新 MP3..." >> "$LOG_FILE"
BEFORE_MP3=$(ls "$SCRIPT_DIR/mp3/"*.mp3 2>/dev/null | wc -l)
python3 download_qualified.py >> "$LOG_FILE" 2>&1
AFTER_MP3=$(ls "$SCRIPT_DIR/mp3/"*.mp3 2>/dev/null | wc -l)
DOWNLOADED=$((AFTER_MP3 - BEFORE_MP3))
if [ $DOWNLOADED -lt 0 ]; then DOWNLOADED=0; fi

# 步驟 3: 上傳到 Spotify（腳本內部會統計上傳結果並寫入 /tmp/upload_stats.json）
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟3] 上傳到 Spotify..." >> "$LOG_FILE"
python3 auto_upload.py >> "$LOG_FILE" 2>&1
UPLOAD_EXIT=$?

# 讀取上傳統計（如果有）
if [ -f /tmp/upload_stats.json ]; then
    UPLOADED=$(python3 -c "import json; d=json.load(open('/tmp/upload_stats.json')); print(d.get('success',0))" 2>/dev/null || echo "0")
    FAILED=$(python3 -c "import json; d=json.load(open('/tmp/upload_stats.json')); print(d.get('failed',0))" 2>/dev/null || echo "0")
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') 每日更新完成" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# 步驟 4: 發送 Telegram 通知
DATE_STR=$(date '+%Y-%m-%d %H:%M')
STATUS_ICON="✅"
if [ $FAILED -gt 0 ]; then STATUS_ICON="⚠️"; fi

if [ $NEW_EPISODES -eq 0 ] && [ $UPLOADED -eq 0 ]; then
    SUMMARY="💤 今日暫無新集數"
else
    SUMMARY="${STATUS_ICON} 今日更新完成！"
fi

MESSAGE="🎙️ <b>RTHK 講東講西 Podcast 每日更新報告</b>
📅 ${DATE_STR}

📋 新集數：<b>${NEW_EPISODES}</b> 集
⬇️ 已下載：<b>${DOWNLOADED}</b> 個 MP3
⬆️ 成功上傳：<b>${UPLOADED}</b> 集"

if [ $FAILED -gt 0 ]; then
    MESSAGE="${MESSAGE}
❌ 上傳失敗：<b>${FAILED}</b> 集"
fi

MESSAGE="${MESSAGE}

${SUMMARY}

— Manus 自動通知系統"

send_telegram "$MESSAGE"
echo "$(date '+%Y-%m-%d %H:%M:%S') Telegram 通知已發送" >> "$LOG_FILE"
