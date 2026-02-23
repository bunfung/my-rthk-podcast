#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下載符合主持人條件的集數 MP3
從 host_check_final.json 讀取符合條件的集數，然後從 RTHK API 獲取音頻 URL 並下載
"""
import json
import os
import subprocess
import logging
import time
import requests
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/download_qualified_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

HOST_CHECK_FILE = '/home/ubuntu/rthk_podcast/host_check_final.json'
MP3_DIR = '/home/ubuntu/rthk_podcast/mp3'
CHANNEL = 'radio1'
PROGRAMME = 'Free_as_the_wind'
PROGRAMME_ID = '527'
BASE_URL = 'https://www.rthk.hk'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": f"https://www.rthk.hk/radio/{CHANNEL}/programme/{PROGRAMME}",
}

os.makedirs(MP3_DIR, exist_ok=True)


def get_audio_url(ep_id):
    """從 RTHK getEpisode 頁面抓取音頻 URL"""
    url = f'{BASE_URL}/radio/getEpisode'
    params = {'c': CHANNEL, 'p': PROGRAMME, 'e': ep_id}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        # 搜尋完整 m3u8 URL（不含時間範圍參數的第一個）
        matches = re.findall(r'https://rthkaod2022[^"\'\ ]+master\.m3u8', resp.text)
        if matches:
            # 返回第一個（完整集數，不含 start/end 參數）
            for m in matches:
                if 'start=' not in m:
                    return m
            return matches[0]
    except Exception as e:
        logger.warning(f"getEpisode 失敗: {e}")
    return None


def download_mp3(ep_id, audio_url, title):
    """下載 MP3"""
    mp3_path = os.path.join(MP3_DIR, f"{ep_id}_0.mp3")

    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 100000:
        logger.info(f"  已存在: {mp3_path}")
        return True

    logger.info(f"  下載中: {audio_url[:60]}...")
    tmp_path = mp3_path + '.tmp'

    cmd = [
        'ffmpeg', '-loglevel', 'error',
        '-i', audio_url,
        '-vn',
        '-acodec', 'libmp3lame',
        '-ab', '64k',
        '-ar', '44100',
        '-f', 'mp3',
        '-y', tmp_path
    ]

    try:
        result = subprocess.run(cmd, timeout=600, capture_output=True)
        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 100000:
            os.rename(tmp_path, mp3_path)
            size_mb = os.path.getsize(mp3_path) / 1024 / 1024
            logger.info(f"  ✅ 完成: {size_mb:.1f} MB")
            return True
        else:
            logger.error(f"  ❌ 失敗: returncode={result.returncode}")
            if result.stderr:
                logger.error(f"  stderr: {result.stderr.decode()[:200]}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"  ❌ 超時")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False
    except Exception as e:
        logger.error(f"  ❌ 錯誤: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def main():
    # 讀取符合條件的集數
    with open(HOST_CHECK_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    qualified = [ep for ep in data if ep.get('qualify')]
    logger.info(f"符合條件: {len(qualified)} 集")

    # 找出需要下載的集數
    to_download = []
    for ep in qualified:
        ep_id = str(ep['id'])
        mp3_path = os.path.join(MP3_DIR, f"{ep_id}_0.mp3")
        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) < 100000:
            to_download.append(ep)

    logger.info(f"需要下載: {len(to_download)} 集")

    if not to_download:
        logger.info("所有集數已下載完成")
        return

    success = 0
    failed = 0
    failed_list = []

    for i, ep in enumerate(to_download):
        ep_id = str(ep['id'])
        title = ep['title']
        ep_date = ep['date']
        logger.info(f"\n[{i+1}/{len(to_download)}] {title} ({ep_date})")

        # 獲取音頻 URL
        audio_url = get_audio_url(ep_id)
        if not audio_url:
            logger.error(f"  ❌ 無法獲取音頻 URL")
            failed += 1
            failed_list.append(title)
            continue

        # 下載 MP3
        ok = download_mp3(ep_id, audio_url, title)
        if ok:
            success += 1
        else:
            failed += 1
            failed_list.append(title)

        time.sleep(2)

    logger.info(f"\n下載完成: 成功 {success}，失敗 {failed}")
    if failed_list:
        logger.info(f"失敗集數: {failed_list}")


if __name__ == '__main__':
    main()
