#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTHK 《講東講西》Podcast 主更新腳本
流程：
  1. 讀取 last_checked.json 取得上次檢查日期
  2. 從 RTHK 抓取比上次更新的集數
  3. 符合主持人條件 AND 唔在 ia_mapping.json → 下載 MP3
  4. 上傳到 Internet Archive
  5. 加入 ia_mapping.json + 更新 last_checked.json
  6. 輸出統計到 /tmp/rthk_update_stats.json
"""
import os
import re
import json
import time
import logging
import subprocess
import requests
from datetime import datetime, date
from urllib.parse import quote

# ── 設定 ──────────────────────────────────────────────
BASE_DIR = '/home/ubuntu/rthk_podcast'
MP3_DIR = f'{BASE_DIR}/mp3'
IA_MAPPING_FILE = f'{BASE_DIR}/ia_mapping.json'
LAST_CHECKED_FILE = f'{BASE_DIR}/last_checked.json'
STATS_FILE = '/tmp/rthk_update_stats.json'

CHANNEL = 'radio1'
PROGRAMME = 'Free_as_the_wind'
BASE_URL = 'https://www.rthk.hk'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': f'https://www.rthk.hk/radio/{CHANNEL}/programme/{PROGRAMME}',
}

ALLOWED_HOSTS = ['蘇奭', '邱逸', '馬鼎盛', '馮天樂']

IA_ACCESS_KEY = os.environ.get('IA_ACCESS_KEY', 'kFTwDB2nXEGiWNYZ')
IA_SECRET_KEY = os.environ.get('IA_SECRET_KEY', 'gPTTPew6CA8WyEXn')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{BASE_DIR}/update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ── 工具函數 ──────────────────────────────────────────
def parse_date(s):
    try:
        return datetime.strptime(s, '%d/%m/%Y').date()
    except:
        return None


def clean_html(text):
    return re.sub(r'<[^>]+>', '', text).strip()


def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── RTHK 抓取 ─────────────────────────────────────────
def get_available_months():
    from bs4 import BeautifulSoup
    url = f'{BASE_URL}/radio/{CHANNEL}/programme/{PROGRAMME}'
    resp = requests.get(url, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(resp.text, 'html.parser')
    months = []
    select = soup.find('select', class_='selMonWrap')
    if select:
        for opt in select.find_all('option'):
            val = opt.get('value', '').strip()
            if val and len(val) == 6:
                months.append(val)
    return sorted(months, reverse=True)


def get_episodes_by_month(ym):
    url = f'{BASE_URL}/radio/catchUpByMonth'
    params = {'c': CHANNEL, 'p': PROGRAMME, 'm': ym}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    data = resp.json()
    if data.get('status') == '1':
        return data.get('content', [])
    return []


def check_host_qualification(ep_id):
    """
    檢查集數是否符合主持人條件
    返回 (qualify: bool, matched: list)
    """
    url = f'{BASE_URL}/radio/{CHANNEL}/programme/{PROGRAMME}/episode/{ep_id}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        text = resp.text

        ep_hosts = []
        ep_guests = []
        programme_hosts = []

        pop_match = re.search(r'popEpiTit.*?</div>\s*</div>\s*</div>', text, re.DOTALL)
        if pop_match:
            section = pop_match.group(0)
            epidesc_match = re.search(r'epidesc.*?</div>', section, re.DOTALL)
            if epidesc_match:
                epidesc = epidesc_match.group(0)
                ep_hosts = [clean_html(h) for h in re.findall(r'(?<![人])主持[：:]([^\n<\r]+)', epidesc) if clean_html(h)]
                ep_guests = [clean_html(g) for g in re.findall(r'嘉賓[：:]([^\n<\r]+)', epidesc) if clean_html(g)]
            programme_hosts = [clean_html(h) for h in re.findall(r'主持人[：:]([^\n<\r]+)', section) if clean_html(h)]

        check_people = (ep_hosts + ep_guests) if ep_hosts else programme_hosts
        matched = [h for h in ALLOWED_HOSTS if any(h in p for p in check_people)]
        return len(matched) > 0, matched

    except Exception as e:
        logger.error(f'檢查主持人失敗 (ep_id={ep_id}): {e}')
        return False, []


def get_audio_url(ep_id):
    """獲取集數的音頻 URL"""
    url = f'{BASE_URL}/radio/getEpisode'
    params = {'c': CHANNEL, 'p': PROGRAMME, 'e': ep_id}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    urls = re.findall(r'https://rthkaod2022[^"\']+master\.m3u8[^"\']*', resp.text)
    # 優先選冇 start= 的 URL（完整集數）
    for u in urls:
        if 'start=' not in u:
            return u
    return urls[0] if urls else None


# ── 下載 MP3 ──────────────────────────────────────────
def download_mp3(ep_id, audio_url, title):
    """用 ffmpeg 下載 MP3，返回路徑或 None"""
    os.makedirs(MP3_DIR, exist_ok=True)
    mp3_path = f'{MP3_DIR}/{ep_id}_0.mp3'
    tmp_path = mp3_path + '.tmp'

    cmd = ['ffmpeg', '-loglevel', 'error', '-i', audio_url,
           '-vn', '-acodec', 'libmp3lame', '-ab', '64k', '-ar', '44100',
           '-f', 'mp3', '-y', tmp_path]
    try:
        result = subprocess.run(cmd, timeout=600, capture_output=True)
        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 100000:
            os.rename(tmp_path, mp3_path)
            size_mb = os.path.getsize(mp3_path) / 1024 / 1024
            logger.info(f'  ✅ 下載完成: {size_mb:.1f}MB')
            return mp3_path
        else:
            logger.error(f'  ❌ 下載失敗: returncode={result.returncode}')
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return None
    except Exception as e:
        logger.error(f'  ❌ 下載錯誤: {e}')
        return None


# ── 上傳到 IA ─────────────────────────────────────────
def upload_to_ia(ep_id, mp3_path, title, ep_date):
    """上傳 MP3 到 Internet Archive，返回 ia_info dict 或 None"""
    item_id = f'rthk-jiang-dong-jiang-xi-{ep_id}'
    filename = f'{ep_id}_0.mp3'
    file_size = os.path.getsize(mp3_path)

    try:
        day, month, year = ep_date.split('/')
        iso_date = f'{year}-{month}-{day}'
    except:
        iso_date = ep_date

    def enc(v):
        return f"uri({quote(v, safe='')})"

    headers = {
        'Authorization': f'LOW {IA_ACCESS_KEY}:{IA_SECRET_KEY}',
        'x-archive-meta-mediatype': 'audio',
        'x-archive-meta-collection': 'opensource_audio',
        'x-archive-meta-title': enc(f'RTHK 講東講西 - {title} ({ep_date})'),
        'x-archive-meta-creator': enc('RTHK Radio 1'),
        'x-archive-meta-subject': enc('podcast;RTHK;講東講西;香港電台'),
        'x-archive-meta-description': enc(f'香港電台第一台《講東講西》節目 - {title}，播出日期：{ep_date}'),
        'x-archive-meta-language': 'zho',
        'x-archive-meta-date': iso_date,
        'x-archive-auto-make-bucket': '1',
        'Content-Type': 'audio/mpeg',
        'Content-Length': str(file_size),
    }

    upload_url = f'https://s3.us.archive.org/{item_id}/{filename}'
    with open(mp3_path, 'rb') as f:
        resp = requests.put(upload_url, data=f, headers=headers, timeout=600)

    if resp.status_code in [200, 201]:
        ia_url = f'https://archive.org/download/{item_id}/{filename}'
        logger.info(f'  ✅ 上傳成功: {ia_url}')
        return {
            'item_id': item_id,
            'url': ia_url,
            'size': file_size,
            'title': title,
            'date': ep_date
        }
    else:
        logger.error(f'  ❌ 上傳失敗 HTTP {resp.status_code}: {resp.text[:200]}')
        return None


# ── 主流程 ────────────────────────────────────────────
def main():
    # 讀取現有記錄
    ia_mapping = load_json(IA_MAPPING_FILE, {})
    last_checked = load_json(LAST_CHECKED_FILE, {'last_checked_date': '01/10/2025'})
    last_checked_date = parse_date(last_checked.get('last_checked_date', '01/10/2025'))

    logger.info(f'上次檢查日期: {last_checked_date}')
    logger.info(f'ia_mapping 現有: {len(ia_mapping)} 集')

    # 統計
    stats = {'new_episodes': 0, 'downloaded': 0, 'uploaded': 0, 'failed': 0, 'uploaded_titles': []}
    latest_date_seen = last_checked_date

    # 獲取可用月份
    months = get_available_months()
    logger.info(f'可用月份: {months}')

    for ym in months:
        year, month = int(ym[:4]), int(ym[4:])
        ym_date = date(year, month, 1)
        last_ym_date = date(last_checked_date.year, last_checked_date.month, 1)

        # 早於上次檢查月份，停止
        if ym_date < last_ym_date:
            logger.info(f'月份 {ym} 早於上次檢查月份，停止')
            break

        logger.info(f'檢查 {ym}...')
        episodes = get_episodes_by_month(ym)

        for ep in episodes:
            ep_id = str(ep.get('id', ''))
            ep_date_str = ep.get('date', '')
            title = ep.get('title', '未知')
            ep_date = parse_date(ep_date_str)

            if not ep_date or not ep_id:
                continue

            # 只處理比上次更新的集數
            if ep_date <= last_checked_date:
                continue

            # 更新今次見到的最新日期
            if ep_date > latest_date_seen:
                latest_date_seen = ep_date

            logger.info(f'新集數: {ep_date_str} - {title} (ID: {ep_id})')
            stats['new_episodes'] += 1

            # 已在 ia_mapping，跳過
            if ep_id in ia_mapping:
                logger.info(f'  已在 ia_mapping，跳過')
                continue

            # 檢查主持人條件
            qualify, matched = check_host_qualification(ep_id)
            time.sleep(0.5)

            if not qualify:
                logger.info(f'  ❌ 唔符合主持人條件，跳過')
                continue

            logger.info(f'  ✅ 符合條件 (匹配: {matched})')

            # 獲取音頻 URL
            audio_url = get_audio_url(ep_id)
            if not audio_url:
                logger.error(f'  ❌ 無法獲取音頻 URL')
                stats['failed'] += 1
                continue

            # 下載 MP3
            logger.info(f'  下載 MP3...')
            mp3_path = download_mp3(ep_id, audio_url, title)
            if not mp3_path:
                stats['failed'] += 1
                continue
            stats['downloaded'] += 1

            # 上傳到 IA
            logger.info(f'  上傳到 IA...')
            ia_info = upload_to_ia(ep_id, mp3_path, title, ep_date_str)
            if not ia_info:
                stats['failed'] += 1
                continue

            # 加入 ia_mapping 並立即儲存
            ia_mapping[ep_id] = ia_info
            save_json(IA_MAPPING_FILE, ia_mapping)
            stats['uploaded'] += 1
            stats['uploaded_titles'].append(f'{title} ({ep_date_str})')
            logger.info(f'  ✅ 已記錄到 ia_mapping.json')

            # 下載後刪除本地 MP3（節省空間，IA 已有備份）
            try:
                os.remove(mp3_path)
                logger.info(f'  🗑️  已刪除本地 MP3')
            except:
                pass

            time.sleep(2)

    # 更新 last_checked.json
    if latest_date_seen > last_checked_date:
        new_last_checked = {
            'last_checked_date': latest_date_seen.strftime('%d/%m/%Y'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'note': '只記錄日期，唔記錄 ID（ID 係全台共用流水號）'
        }
        save_json(LAST_CHECKED_FILE, new_last_checked)
        logger.info(f'已更新 last_checked_date 至 {latest_date_seen.strftime("%d/%m/%Y")}')
    else:
        logger.info('今次冇見到更新的日期，last_checked.json 保持不變')

    # 輸出統計
    save_json(STATS_FILE, stats)
    logger.info(f'完成！新集數={stats["new_episodes"]}, 下載={stats["downloaded"]}, 上傳={stats["uploaded"]}, 失敗={stats["failed"]}')


if __name__ == '__main__':
    main()
