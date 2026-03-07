#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修復指定集數：重新從 RTHK 下載並覆蓋上傳到 IA"""
import os, re, json, subprocess, requests, time
from urllib.parse import quote

BASE_DIR = '/home/ubuntu/rthk_podcast'
MP3_DIR = f'{BASE_DIR}/mp3'
IA_MAPPING_FILE = f'{BASE_DIR}/ia_mapping.json'
IA_ACCESS_KEY = os.environ.get('IA_ACCESS_KEY', 'kFTwDB2nXEGiWNYZ')
IA_SECRET_KEY = os.environ.get('IA_SECRET_KEY', 'gPTTPew6CA8WyEXn')
BASE_URL = 'https://www.rthk.hk'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', 'Referer': 'https://www.rthk.hk/'}
FFMPEG = '/usr/bin/ffmpeg'

REPAIR_IDS = ['1056032', '1054594', '1069077', '1072248', '1067879']

def get_audio_url_from_rthk(ep_id):
    """嘗試多種方法取得音頻 URL"""
    # 方法1: 直接抓 episode 頁面
    for prog in ['Free_as_the_wind', 'free_as_the_wind_sunday']:
        url = f'{BASE_URL}/radio/radio1/programme/{prog}/episode/{ep_id}'
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            m = re.search(r'(https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*)', r.text)
            if m:
                return m.group(1)
        except:
            pass
    # 方法2: catchup detail API
    url = f'{BASE_URL}/radio/catchup/detail/{ep_id}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        try:
            d = r.json()
            for key in ['streamUrl', 'stream_url', 'url', 'audioUrl']:
                if d.get(key): return d[key]
            item = d.get('item')
            if item:
                if isinstance(item, list): item = item[0]
                for key in ['streamUrl', 'url']:
                    if item.get(key): return item[key]
        except:
            m = re.search(r'(https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*)', r.text)
            if m: return m.group(1)
    except:
        pass
    return None

def download_mp3(ep_id, audio_url):
    os.makedirs(MP3_DIR, exist_ok=True)
    mp3_path = f'{MP3_DIR}/{ep_id}_0.mp3'
    ts_path = f'{MP3_DIR}/{ep_id}_raw.mp4'
    
    print(f'  ⬇️ yt-dlp: {audio_url[:80]}')
    r = subprocess.run(['yt-dlp', '--no-playlist', '--fixup', 'never', '-o', ts_path, audio_url],
                       timeout=600, capture_output=True)
    if not os.path.exists(ts_path) or os.path.getsize(ts_path) < 1024*1024:
        print(f'  ❌ yt-dlp 失敗')
        print(r.stderr[-500:].decode(errors='ignore'))
        return None
    print(f'  ✅ 下載: {os.path.getsize(ts_path)//1024//1024}MB')
    
    r2 = subprocess.run([FFMPEG, '-y', '-f', 'mpegts', '-i', ts_path,
                         '-acodec', 'libmp3lame', '-b:a', '128k', mp3_path],
                        timeout=600, capture_output=True)
    if os.path.exists(ts_path): os.remove(ts_path)
    if r2.returncode == 0 and os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 100000:
        print(f'  ✅ 轉換: {os.path.getsize(mp3_path)//1024//1024}MB')
        return mp3_path
    print(f'  ❌ ffmpeg 失敗 rc={r2.returncode}')
    print(r2.stderr[-300:].decode(errors='ignore'))
    return None

def upload_to_ia(ep_id, mp3_path, title, ep_date):
    item_id = f'rthk-jiang-dong-jiang-xi-{ep_id}'
    filename = f'{ep_id}_0.mp3'
    file_size = os.path.getsize(mp3_path)
    try:
        day, month, year = ep_date.split('/')
        iso_date = f'{year}-{month}-{day}'
    except:
        iso_date = ep_date
    def enc(v): return f"uri({quote(v, safe='')})"
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
        'x-archive-keep-old-version': '0',
    }
    upload_url = f'https://s3.us.archive.org/{item_id}/{filename}'
    print(f'  ⬆️ 上傳 {item_id}')
    with open(mp3_path, 'rb') as f:
        resp = requests.put(upload_url, data=f, headers=headers, timeout=600)
    if resp.status_code in [200, 201]:
        ia_url = f'https://archive.org/download/{item_id}/{filename}'
        print(f'  ✅ 上傳成功 ({file_size//1024//1024}MB)')
        return {'item_id': item_id, 'url': ia_url, 'size': file_size, 'title': title, 'date': ep_date}
    else:
        print(f'  ❌ 上傳失敗 HTTP {resp.status_code}: {resp.text[:300]}')
        return None

def main():
    with open(IA_MAPPING_FILE) as f:
        ia_mapping = json.load(f)
    
    success = []
    failed = []
    
    for ep_id in REPAIR_IDS:
        info = ia_mapping.get(ep_id, {})
        title = info.get('title', f'EP{ep_id}')
        ep_date = info.get('date', '')
        print(f'\n{"="*50}')
        print(f'修復: {title} ({ep_date}) [ID: {ep_id}]')
        
        audio_url = get_audio_url_from_rthk(ep_id)
        if not audio_url:
            print(f'  ❌ 未能取得音頻 URL，嘗試用 yt-dlp 抓節目頁面')
            audio_url = f'https://www.rthk.hk/radio/radio1/programme/Free_as_the_wind/episode/{ep_id}'
        
        print(f'  🔗 URL: {audio_url[:100]}')
        mp3_path = download_mp3(ep_id, audio_url)
        if not mp3_path:
            failed.append(f'{title} ({ep_date})')
            continue
        
        result = upload_to_ia(ep_id, mp3_path, title, ep_date)
        if os.path.exists(mp3_path): os.remove(mp3_path)
        
        if result:
            ia_mapping[ep_id] = result
            with open(IA_MAPPING_FILE, 'w', encoding='utf-8') as f:
                json.dump(ia_mapping, f, ensure_ascii=False, indent=2)
            success.append(f'{title} ({ep_date})')
        else:
            failed.append(f'{title} ({ep_date})')
        
        time.sleep(3)
    
    print(f'\n{"="*50}')
    print(f'✅ 成功: {len(success)} 集')
    for s in success: print(f'   • {s}')
    if failed:
        print(f'❌ 失敗: {len(failed)} 集')
        for s in failed: print(f'   • {s}')

if __name__ == '__main__':
    main()
