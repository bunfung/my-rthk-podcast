#!/bin/bash
# 每日自動更新 RTHK 《講東講西》Podcast 腳本（Internet Archive 版本）
#
# 工作流程：
# 1. 從 GitHub pull 最新記錄（episodes.json, ia_mapping.json, last_checked.json）
# 2. 執行 update.py：只抓取比 last_checked_date 更新的集數，符合主持人條件才加入 episodes.json
# 3. 下載新集數 MP3（只下載 episodes.json 有但 ia_mapping.json 冇的集數）
# 4. 上傳新 MP3 到 Internet Archive，更新 ia_mapping.json
# 5. 生成 RSS feed
# 6. Push 所有更新到 GitHub（episodes.json, ia_mapping.json, last_checked.json, feed.xml）
# 7. 發送 Telegram 通知（包含今日新增集數名稱）

LOG_FILE="/home/ubuntu/rthk_podcast/daily_update.log"
SCRIPT_DIR="/home/ubuntu/rthk_podcast"

# 從 .env 讀取所有 credentials
# 注意：.env 在 .gitignore 內，sandbox 重置後會消失
# 如果 .env 唔存在，schedule job 的 prompt 會先自動重建它
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') [錯誤] .env 唔存在，請先建立 .env 檔案" >> "$LOG_FILE"
    exit 1
fi

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}"

# IA credentials
export IA_ACCESS_KEY="${IA_ACCESS_KEY:-kFTwDB2nXEGiWNYZ}"
export IA_SECRET_KEY="${IA_SECRET_KEY:-gPTTPew6CA8WyEXn}"

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

# 確保 mp3 目錄存在
mkdir -p "$SCRIPT_DIR/mp3"

# 步驟 0: 從 GitHub pull 最新記錄
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟0] 從 GitHub 同步最新記錄..." >> "$LOG_FILE"
if [ -n "$GITHUB_TOKEN" ]; then
    git remote set-url origin "https://${GITHUB_TOKEN}@github.com/bunfung/my-rthk-podcast.git"
fi
git config user.email "bunfung.any@gmail.com" 2>/dev/null
git config user.name "bunfung" 2>/dev/null
git pull origin main >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [警告] git pull 失敗，繼續使用本地記錄" >> "$LOG_FILE"
fi

# 記錄更新前的集數 ID 列表（用於之後比對新增了哪些集數）
python3 -c "
import json
try:
    data = json.load(open('episodes.json'))
    ids = set(str(ep.get('id','')) for ep in data)
    with open('/tmp/rthk_before_ids.txt', 'w') as f:
        f.write('\n'.join(sorted(ids)))
except:
    open('/tmp/rthk_before_ids.txt', 'w').close()
" 2>/dev/null

BEFORE_COUNT=$(python3 -c "import json; data=json.load(open('episodes.json')); print(len(data))" 2>/dev/null || echo "0")

# 記錄更新前 ia_mapping 的集數（用於之後比對哪些是新上傳的）
python3 -c "
import json
try:
    d = json.load(open('ia_mapping.json'))
    ids = list(d.keys())
    with open('/tmp/rthk_before_ia_ids.txt', 'w') as f:
        f.write('\n'.join(ids))
except:
    open('/tmp/rthk_before_ia_ids.txt', 'w').close()
" 2>/dev/null

# 步驟 1: 更新集數列表（只抓取比 last_checked_date 更新的集數）
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

# 找出新增集數的名稱和日期，寫入暫存檔
python3 -c "
import json

try:
    before_ids = set(open('/tmp/rthk_before_ids.txt').read().strip().split('\n'))
except:
    before_ids = set()

try:
    data = json.load(open('episodes.json'))
except:
    data = []

new_eps = []
for ep in data:
    ep_id = str(ep.get('id', ''))
    if ep_id and ep_id not in before_ids:
        title = ep.get('title', '?')
        date_str = ep.get('date', '?')
        new_eps.append(f'{title} ({date_str})')

with open('/tmp/rthk_new_episodes.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_eps))

print(f'新增集數: {len(new_eps)} 集')
for ep in new_eps:
    print(f'  {ep}')
" >> "$LOG_FILE" 2>&1

# 步驟 2: 下載新集數 MP3
# 邏輯：只下載 episodes.json 有但 ia_mapping.json 冇的集數
# 唔理本地有冇 MP3（sandbox 重置後本地是空的，但 ia_mapping.json 有記錄就代表已上傳過）
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟2] 下載新集數 MP3..." >> "$LOG_FILE"

python3 -c "
import json, os, subprocess, time

BASE_DIR = '/home/ubuntu/rthk_podcast'
MP3_DIR = f'{BASE_DIR}/mp3'

os.makedirs(MP3_DIR, exist_ok=True)

# 讀取 episodes.json（符合條件的集數）
with open(f'{BASE_DIR}/episodes.json') as f:
    episodes = json.load(f)

# 讀取 ia_mapping（已上傳到 IA 的集數）
try:
    with open(f'{BASE_DIR}/ia_mapping.json') as f:
        ia_mapping = json.load(f)
except:
    ia_mapping = {}

# 只下載：在 episodes.json 但不在 ia_mapping 的集數
# 唔理本地有冇 MP3（因為 sandbox 重置後本地是空的）
to_download = []
for ep in episodes:
    ep_id = str(ep.get('id', ''))
    if not ep_id:
        continue
    # 已上傳到 IA，唔需要下載
    if ep_id in ia_mapping:
        continue
    to_download.append(ep)

print(f'需要下載: {len(to_download)} 集（episodes.json 有但 ia_mapping.json 冇）')

downloaded = 0
for ep in to_download:
    ep_id = str(ep.get('id', ''))
    title = ep.get('title', '?')
    date_str = ep.get('date', '?')

    audio_urls = ep.get('audio_urls', [])
    audio_url = None
    for url in audio_urls:
        if 'start=' not in url:
            audio_url = url
            break
    if not audio_url and audio_urls:
        audio_url = audio_urls[0]

    if not audio_url:
        print(f'  ⚠️  無音頻 URL: {title}')
        continue

    mp3_path = f'{MP3_DIR}/{ep_id}_0.mp3'
    tmp_path = mp3_path + '.tmp'

    print(f'  下載: {title} ({date_str})')
    cmd = ['ffmpeg', '-loglevel', 'error', '-i', audio_url,
           '-vn', '-acodec', 'libmp3lame', '-ab', '64k', '-ar', '44100',
           '-f', 'mp3', '-y', tmp_path]

    try:
        result = subprocess.run(cmd, timeout=600, capture_output=True)
        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 100000:
            os.rename(tmp_path, mp3_path)
            downloaded += 1
            print(f'    ✅ 完成: {os.path.getsize(mp3_path)/1024/1024:.1f}MB')
        else:
            print(f'    ❌ 失敗: returncode={result.returncode}')
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        print(f'    ❌ 錯誤: {e}')

    time.sleep(2)

print(f'下載完成: {downloaded} 個 MP3')
with open('/tmp/rthk_downloaded_count.txt', 'w') as f:
    f.write(str(downloaded))
" >> "$LOG_FILE" 2>&1

DOWNLOADED=$(cat /tmp/rthk_downloaded_count.txt 2>/dev/null || echo "0")

# 步驟 3: 上傳新 MP3 到 Internet Archive
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟3] 上傳到 Internet Archive..." >> "$LOG_FILE"
python3 upload_all_to_ia.py >> "$LOG_FILE" 2>&1

# 讀取上傳統計
if [ -f /tmp/ia_upload_stats.json ]; then
    UPLOADED=$(python3 -c "import json; d=json.load(open('/tmp/ia_upload_stats.json')); print(d.get('success',0))" 2>/dev/null || echo "0")
    FAILED=$(python3 -c "import json; d=json.load(open('/tmp/ia_upload_stats.json')); print(d.get('failed',0))" 2>/dev/null || echo "0")
fi

# 找出今次新上傳的集數名稱
UPLOADED_LIST=$(python3 -c "
import json

try:
    before_ids = set(open('/tmp/rthk_before_ia_ids.txt').read().strip().split('\n'))
except:
    before_ids = set()

try:
    ia_mapping = json.load(open('ia_mapping.json'))
except:
    ia_mapping = {}

new_uploaded = []
for ep_id, info in ia_mapping.items():
    if ep_id not in before_ids:
        title = info.get('title', '?')
        date_str = info.get('date', '?')
        new_uploaded.append(f'{title} ({date_str})')

for ep in new_uploaded:
    print(ep)
" 2>/dev/null)

# 步驟 4: 生成 RSS feed
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟4] 生成 RSS feed..." >> "$LOG_FILE"
python3 generate_rss.py >> "$LOG_FILE" 2>&1

# 步驟 5: Push 到 GitHub
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟5] Push 到 GitHub..." >> "$LOG_FILE"

git add episodes.json ia_mapping.json last_checked.json feed.xml >> "$LOG_FILE" 2>&1
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

TOTAL_IA=$(python3 -c "import json; d=json.load(open('ia_mapping.json')); print(len(d))" 2>/dev/null || echo "?")

MESSAGE="🎙️ <b>RTHK 講東講西 Podcast 每日更新報告</b>
📅 ${DATE_STR}

📋 新集數：<b>${NEW_EPISODES}</b> 集
⬇️ 已下載：<b>${DOWNLOADED}</b> 個 MP3
⬆️ 成功上傳：<b>${UPLOADED}</b> 集
☁️ IA 總集數：<b>${TOTAL_IA}</b> 集"

# 加入上傳集數名稱列表
if [ -n "$UPLOADED_LIST" ]; then
    MESSAGE="${MESSAGE}

📝 <b>今日上傳集數：</b>"
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            MESSAGE="${MESSAGE}
  • ${line}"
        fi
    done <<< "$UPLOADED_LIST"
fi

# 加入失敗數量（如有）
if [ $FAILED -gt 0 ]; then
    MESSAGE="${MESSAGE}

❌ 上傳失敗：<b>${FAILED}</b> 集"
fi

# 加入總結
if [ $NEW_EPISODES -eq 0 ] && [ $UPLOADED -eq 0 ]; then
    MESSAGE="${MESSAGE}

💤 今日暫無新集數"
else
    MESSAGE="${MESSAGE}

${STATUS_ICON} 今日更新完成！"
fi

MESSAGE="${MESSAGE}

🔗 RSS: https://bunfung.github.io/my-rthk-podcast/feed.xml

— Manus 自動通知系統"

send_telegram "$MESSAGE"
echo "$(date '+%Y-%m-%d %H:%M:%S') Telegram 通知已發送" >> "$LOG_FILE"
