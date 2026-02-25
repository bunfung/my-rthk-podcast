#!/bin/bash
# 每日自動更新 RTHK 《講東講西》Podcast 腳本（Internet Archive 版本）
# 工作流程：
# 1. 從 GitHub pull 最新記錄
# 2. 更新集數列表（抓取新集數，篩選主持人）
# 3. 下載新 MP3
# 4. 上傳到 Internet Archive
# 5. 更新 ia_mapping.json
# 6. 生成 RSS feed
# 7. Push 到 GitHub
# 8. 發送 Telegram 通知報告

LOG_FILE="/home/ubuntu/rthk_podcast/daily_update.log"
SCRIPT_DIR="/home/ubuntu/rthk_podcast"
TELEGRAM_BOT_TOKEN="8634320454:AAH6IpV7uN6-y_Gzd731Xm3O1-D76UCdnzQ"
TELEGRAM_CHAT_ID="220866475"
# 從 .env 讀取 GitHub token
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi
# GITHUB_TOKEN 應在 .env 中設定為 GITHUB_TOKEN=ghp_...

# IA credentials
export IA_ACCESS_KEY="kFTwDB2nXEGiWNYZ"
export IA_SECRET_KEY="gPTTPew6CA8WyEXn"

# 統計變數
NEW_EPISODES=0
DOWNLOADED=0
UPLOADED=0
FAILED=0

send_telegram() {
    local message="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "parse_mode=HTML" \
        --data-urlencode "text=${message}" > /dev/null 2>&1
}

echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 開始每日更新（IA 版本）" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$SCRIPT_DIR"

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

# 步驟 2: 下載新 MP3（只下載尚未在 ia_mapping 中的集數）
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟2] 下載新 MP3..." >> "$LOG_FILE"
BEFORE_MP3=$(ls "$SCRIPT_DIR/mp3/"*.mp3 2>/dev/null | wc -l)

# 使用 update.py 更新後的 episodes.json 下載新集數
python3 -c "
import json, os, subprocess, time, requests, re

BASE_DIR = '/home/ubuntu/rthk_podcast'
MP3_DIR = f'{BASE_DIR}/mp3'
CHANNEL = 'radio1'
PROGRAMME = 'Free_as_the_wind'
BASE_URL = 'https://www.rthk.hk'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

os.makedirs(MP3_DIR, exist_ok=True)

# 讀取 episodes.json
with open(f'{BASE_DIR}/episodes.json') as f:
    episodes = json.load(f)

# 讀取 ia_mapping
try:
    with open(f'{BASE_DIR}/ia_mapping.json') as f:
        ia_mapping = json.load(f)
except:
    ia_mapping = {}

# 找出需要下載的集數（在 episodes.json 但不在 ia_mapping 且無 MP3）
to_download = []
for ep in episodes:
    ep_id = str(ep.get('id', ''))
    if not ep_id:
        continue
    if ep_id in ia_mapping:
        continue
    mp3_path = f'{MP3_DIR}/{ep_id}_0.mp3'
    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 100000:
        continue
    to_download.append(ep)

print(f'需要下載: {len(to_download)} 集')

for ep in to_download:
    ep_id = str(ep.get('id', ''))
    title = ep.get('title', '?')
    date = ep.get('date', '?')
    
    # 獲取音頻 URL
    audio_urls = ep.get('audio_urls', [])
    audio_url = None
    for url in audio_urls:
        if 'start=' not in url:
            audio_url = url
            break
    if not audio_url and audio_urls:
        audio_url = audio_urls[0]
    
    if not audio_url:
        print(f'無音頻 URL: {title}')
        continue
    
    mp3_path = f'{MP3_DIR}/{ep_id}_0.mp3'
    tmp_path = mp3_path + '.tmp'
    
    print(f'下載: {title} ({date})')
    cmd = ['ffmpeg', '-loglevel', 'error', '-i', audio_url, '-vn', '-acodec', 'libmp3lame', '-ab', '64k', '-ar', '44100', '-f', 'mp3', '-y', tmp_path]
    
    try:
        result = subprocess.run(cmd, timeout=600, capture_output=True)
        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 100000:
            os.rename(tmp_path, mp3_path)
            print(f'  ✅ 完成: {os.path.getsize(mp3_path)/1024/1024:.1f}MB')
        else:
            print(f'  ❌ 失敗: returncode={result.returncode}')
    except Exception as e:
        print(f'  ❌ 錯誤: {e}')
    
    time.sleep(2)
" >> "$LOG_FILE" 2>&1

AFTER_MP3=$(ls "$SCRIPT_DIR/mp3/"*.mp3 2>/dev/null | wc -l)
DOWNLOADED=$((AFTER_MP3 - BEFORE_MP3))
if [ $DOWNLOADED -lt 0 ]; then DOWNLOADED=0; fi

# 步驟 3: 上傳新 MP3 到 Internet Archive
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟3] 上傳到 Internet Archive..." >> "$LOG_FILE"
python3 upload_all_to_ia.py >> "$LOG_FILE" 2>&1
UPLOAD_EXIT=$?

# 讀取上傳統計
if [ -f /tmp/ia_upload_stats.json ]; then
    UPLOADED=$(python3 -c "import json; d=json.load(open('/tmp/ia_upload_stats.json')); print(d.get('success',0))" 2>/dev/null || echo "0")
    FAILED=$(python3 -c "import json; d=json.load(open('/tmp/ia_upload_stats.json')); print(d.get('failed',0))" 2>/dev/null || echo "0")
fi

# 步驟 4: 生成 RSS feed
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟4] 生成 RSS feed..." >> "$LOG_FILE"
python3 generate_rss.py >> "$LOG_FILE" 2>&1

# 步驟 5: Push 到 GitHub
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟5] Push 到 GitHub..." >> "$LOG_FILE"

# 設定包含 token 的 git remote URL（確保無需人手輸入密碼）
if [ -n "$GITHUB_TOKEN" ]; then
    git remote set-url origin "https://${GITHUB_TOKEN}@github.com/bunfung/my-rthk-podcast.git"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟5] 已設定 git remote URL（含 token）" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') [警告] GITHUB_TOKEN 未設定，git push 可能失敗" >> "$LOG_FILE"
fi

git config user.email "bunfung.any@gmail.com" 2>/dev/null
git config user.name "bunfung" 2>/dev/null

git add episodes.json ia_mapping.json feed.xml >> "$LOG_FILE" 2>&1
git commit -m "Daily update: $(date '+%Y-%m-%d')" >> "$LOG_FILE" 2>&1
git push origin main >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [警告] git push 失敗" >> "$LOG_FILE"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') 每日更新完成" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# 步驟 6: 發送 Telegram 通知
DATE_STR=$(date '+%Y-%m-%d %H:%M')
STATUS_ICON="✅"
if [ $FAILED -gt 0 ]; then STATUS_ICON="⚠️"; fi

if [ $NEW_EPISODES -eq 0 ] && [ $UPLOADED -eq 0 ]; then
    SUMMARY="💤 今日暫無新集數"
else
    SUMMARY="${STATUS_ICON} 今日更新完成！"
fi

TOTAL_IA=$(python3 -c "import json; d=json.load(open('ia_mapping.json')); print(len(d))" 2>/dev/null || echo "?")

MESSAGE="🎙️ <b>RTHK 講東講西 Podcast 每日更新報告</b>
📅 ${DATE_STR}

📋 新集數：<b>${NEW_EPISODES}</b> 集
⬇️ 已下載：<b>${DOWNLOADED}</b> 個 MP3
⬆️ 成功上傳：<b>${UPLOADED}</b> 集
☁️ IA 總集數：<b>${TOTAL_IA}</b> 集"

if [ $FAILED -gt 0 ]; then
    MESSAGE="${MESSAGE}
❌ 上傳失敗：<b>${FAILED}</b> 集"
fi

MESSAGE="${MESSAGE}

${SUMMARY}

🔗 RSS: https://bunfung.github.io/my-rthk-podcast/feed.xml

— Manus 自動通知系統"

send_telegram "$MESSAGE"
echo "$(date '+%Y-%m-%d %H:%M:%S') Telegram 通知已發送" >> "$LOG_FILE"
