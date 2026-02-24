#!/usr/bin/env python3
"""
自動上傳 MP3 到 Spotify for Creators 的腳本
使用 xdotool 輸入文字，避免 ProseMirror 問題
"""

import subprocess
import time
import json
import os
import sys

# 上傳清單（按日期排序，最舊先上傳）
UPLOAD_LIST = [
    # 第 1 集已上傳
    # {'ep_id': '1079208', 'title': '17至19世紀英國賣妻合法化 - 09/02/2026', 'date': '09/02/2026'},
    {'ep_id': '1079495', 'title': '香港公共屋邨生活誌 - 10/02/2026', 'date': '10/02/2026'},
    {'ep_id': '1079704', 'title': '千秋功罪秦始皇 - 11/02/2026', 'date': '11/02/2026'},
    {'ep_id': '1079957', 'title': '食在廣州 - 12/02/2026', 'date': '12/02/2026'},
    {'ep_id': '1080168', 'title': '反情人節 - 13/02/2026', 'date': '13/02/2026'},
    {'ep_id': '1080674', 'title': '蘇聯援助西班牙共和國 - 16/02/2026', 'date': '16/02/2026'},
    {'ep_id': '1080947', 'title': '新春本地行大運 - 17/02/2026', 'date': '17/02/2026'},
    {'ep_id': '1081081', 'title': '馬到功成 - 18/02/2026', 'date': '18/02/2026'},
    {'ep_id': '1081224', 'title': '還有人拜年嗎 - 19/02/2026', 'date': '19/02/2026'},
    {'ep_id': '1081342', 'title': '探討「大展鴻圖」這四個字 - 20/02/2026', 'date': '20/02/2026'},
]

MP3_DIR = '/home/ubuntu/rthk_podcast/mp3'
SHOW_ID = '6DVYbYCCvSBreKzyStsnFp'

def xdotool_type(text):
    """用 xdotool 輸入文字"""
    subprocess.run(['xdotool', 'type', '--clearmodifiers', '--delay', '30', text], 
                   env={**os.environ, 'DISPLAY': ':0'})

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

if __name__ == '__main__':
    log("上傳腳本啟動")
    log(f"共 {len(UPLOAD_LIST)} 集需要上傳")
    
    for i, ep in enumerate(UPLOAD_LIST):
        mp3_file = f"{MP3_DIR}/{ep['ep_id']}_0.mp3"
        if not os.path.exists(mp3_file):
            log(f"跳過 {ep['title']} - MP3 文件不存在")
            continue
        
        log(f"[{i+1}/{len(UPLOAD_LIST)}] 準備上傳: {ep['title']}")
        log(f"  MP3 文件: {mp3_file}")
        log(f"  等待手動操作...")
        
        # 輸出需要上傳的資訊
        print(f"\n=== 請上傳以下集數 ===")
        print(f"文件: {mp3_file}")
        print(f"標題: {ep['title']}")
        print(f"描述: RTHK Radio 1《講東講西》節目 - {ep['date']}播出。擴闊知識領域，網羅文化通識！")
        print(f"========================\n")
        
        input("按 Enter 繼續下一集...")
