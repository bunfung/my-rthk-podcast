#!/bin/bash
# 每日自動更新 RTHK 《講東講西》Podcast 腳本
# 1. 更新集數列表
# 2. 下載新 MP3
# 3. 上傳到 Spotify

LOG_FILE="/home/ubuntu/rthk_podcast/daily_update.log"
SCRIPT_DIR="/home/ubuntu/rthk_podcast"

echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 開始每日更新" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$SCRIPT_DIR"

# 步驟 1: 更新集數列表
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟1] 更新集數列表..." >> "$LOG_FILE"
python3 update.py >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [錯誤] 更新集數列表失敗" >> "$LOG_FILE"
    exit 1
fi

# 步驟 2: 下載新 MP3
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟2] 下載新 MP3..." >> "$LOG_FILE"
python3 download_qualified.py >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [警告] 下載 MP3 時出現問題" >> "$LOG_FILE"
fi

# 步驟 3: 上傳到 Spotify
echo "$(date '+%Y-%m-%d %H:%M:%S') [步驟3] 上傳到 Spotify..." >> "$LOG_FILE"
python3 auto_upload.py >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [警告] 上傳到 Spotify 時出現問題" >> "$LOG_FILE"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') 每日更新完成" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
