#!/bin/bash
# RTHK 《講東講西》Podcast 每日自動更新腳本
#
# 流程：
# 1. 讀取 last_checked.json 取得上次檢查日期
# 2. 從 RTHK 抓取比上次更新的集數
# 3. 符合主持人條件 AND 唔在 ia_mapping.json → 下載 MP3
# 4. 上傳到 Internet Archive
# 5. 加入 ia_mapping.json + 更新 last_checked.json
# 6. 生成 RSS feed
# 7. Push 到 GitHub
# 8. 發送 Telegram 通知（包含今日新增集數名稱）

LOG_FILE="/home/ubuntu/rthk_podcast/daily_update.log"
SCRIPT_DIR="/home/ubuntu/rthk_podcast"

# 從 .env 讀取所有 credentials
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') [錯誤] .env 唔存在" >> "$LOG_FILE"
    exit 1
fi

export IA_ACCESS_KEY="${IA_ACCESS_KEY:-kFTwDB2nXEGiWNYZ}"
export IA_SECRET_KEY="${IA_SECRET_KEY:-gPTTPew6CA8WyEXn}"

send_telegram() {
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "parse_mode=HTML" \
        --data-urlencode "text=$1" > /dev/null 2>&1
}

echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 開始每日更新" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$SCRIPT_DIR"
mkdir -p mp3

# 確保 IA config 存在
mkdir -p ~/.config/internetarchive
cat > ~/.config/internetarchive/ia.ini << 'EOF'
[s3]
access=kFTwDB2nXEGiWNYZ
secret=gPTTPew6CA8WyEXn

[cookies]
logged-in-user=bunfung.any@gmail.com
EOF

# 步驟 0: 從 GitHub pull 最新記錄
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟0] 從 GitHub 同步..." >> "$LOG_FILE"
if [ -n "$GITHUB_TOKEN" ]; then
    git remote set-url origin "https://${GITHUB_TOKEN}@github.com/bunfung/my-rthk-podcast.git"
fi
git config user.email "bunfung.any@gmail.com" 2>/dev/null
git config user.name "bunfung" 2>/dev/null
git pull origin main >> "$LOG_FILE" 2>&1 || echo "$(date '+%Y-%m-%d %H:%M:%S') [警告] git pull 失敗" >> "$LOG_FILE"

# 執行主流程 Python 腳本
echo "$(date '+%Y-%m-%d %H:%M:%S') [主流程] 開始執行..." >> "$LOG_FILE"
python3 "$SCRIPT_DIR/run_update.py" >> "$LOG_FILE" 2>&1
PYTHON_EXIT=$?

if [ $PYTHON_EXIT -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [錯誤] 主流程失敗 (exit=$PYTHON_EXIT)" >> "$LOG_FILE"
    send_telegram "🚨 <b>RTHK Podcast 更新失敗</b>
📅 $(date '+%Y-%m-%d %H:%M')
❌ 主流程執行失敗，請查看 log

— Manus 自動通知系統"
    exit 1
fi

# 步驟: 生成 RSS feed
echo "$(date '+%Y-%m-%d %H:%M:%S') [RSS] 生成 RSS feed..." >> "$LOG_FILE"
python3 "$SCRIPT_DIR/generate_rss.py" >> "$LOG_FILE" 2>&1

# 步驟: Push 到 GitHub
echo "$(date '+%Y-%m-%d %H:%M:%S') [Git] Push 到 GitHub..." >> "$LOG_FILE"
git add ia_mapping.json last_checked.json feed.xml >> "$LOG_FILE" 2>&1
git commit -m "Daily update: $(date '+%Y-%m-%d')" >> "$LOG_FILE" 2>&1
git push origin main >> "$LOG_FILE" 2>&1 || echo "$(date '+%Y-%m-%d %H:%M:%S') [警告] git push 失敗" >> "$LOG_FILE"

# 讀取今次更新統計（由 run_update.py 寫入）
STATS_FILE="/tmp/rthk_update_stats.json"
if [ -f "$STATS_FILE" ]; then
    NEW_EPS=$(python3 -c "import json; d=json.load(open('$STATS_FILE')); print(d.get('new_episodes',0))" 2>/dev/null || echo "0")
    DOWNLOADED=$(python3 -c "import json; d=json.load(open('$STATS_FILE')); print(d.get('downloaded',0))" 2>/dev/null || echo "0")
    UPLOADED=$(python3 -c "import json; d=json.load(open('$STATS_FILE')); print(d.get('uploaded',0))" 2>/dev/null || echo "0")
    FAILED=$(python3 -c "import json; d=json.load(open('$STATS_FILE')); print(d.get('failed',0))" 2>/dev/null || echo "0")
    UPLOADED_TITLES=$(python3 -c "import json; d=json.load(open('$STATS_FILE')); print('\n'.join(d.get('uploaded_titles',[])))" 2>/dev/null || echo "")
else
    NEW_EPS=0; DOWNLOADED=0; UPLOADED=0; FAILED=0; UPLOADED_TITLES=""
fi

TOTAL_IA=$(python3 -c "import json; d=json.load(open('ia_mapping.json')); print(len(d))" 2>/dev/null || echo "?")
DATE_STR=$(date '+%Y-%m-%d %H:%M')

# 組合 Telegram 通知
MESSAGE="🎙️ <b>RTHK 講東講西 Podcast 每日更新報告</b>
📅 ${DATE_STR}

📋 新集數：<b>${NEW_EPS}</b> 集
⬇️ 已下載：<b>${DOWNLOADED}</b> 個 MP3
⬆️ 成功上傳：<b>${UPLOADED}</b> 集
☁️ IA 總集數：<b>${TOTAL_IA}</b> 集"

if [ -n "$UPLOADED_TITLES" ]; then
    MESSAGE="${MESSAGE}

📝 <b>今日上傳集數：</b>"
    while IFS= read -r line; do
        [ -n "$line" ] && MESSAGE="${MESSAGE}
  • ${line}"
    done <<< "$UPLOADED_TITLES"
fi

[ $FAILED -gt 0 ] && MESSAGE="${MESSAGE}
❌ 上傳失敗：<b>${FAILED}</b> 集"

if [ $NEW_EPS -eq 0 ] && [ $UPLOADED -eq 0 ]; then
    MESSAGE="${MESSAGE}

💤 今日暫無新集數"
else
    STATUS="✅"
    [ $FAILED -gt 0 ] && STATUS="⚠️"
    MESSAGE="${MESSAGE}

${STATUS} 今日更新完成！"
fi

MESSAGE="${MESSAGE}

🔗 RSS: https://bunfung.github.io/my-rthk-podcast/feed.xml

— Manus 自動通知系統"

send_telegram "$MESSAGE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 每日更新完成，Telegram 通知已發送" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
