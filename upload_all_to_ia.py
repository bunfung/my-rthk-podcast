#!/usr/bin/env python3
"""
上傳所有 21 集到 Internet Archive
使用 spotify_episode_mapping.json 的 rthk_id 來識別集數
"""
import os
import json
import time
import requests
from urllib.parse import quote

BASE_DIR = '/home/ubuntu/rthk_podcast'
MP3_DIR = f'{BASE_DIR}/mp3'

IA_ACCESS_KEY = "kFTwDB2nXEGiWNYZ"
IA_SECRET_KEY = "gPTTPew6CA8WyEXn"

def encode_header(value):
    """將 header 值進行 URI encoding 以支援非 ASCII 字符"""
    return f"uri({quote(value, safe='')})"

def upload_to_ia(ep_id, mp3_path, title, date):
    """上傳 MP3 到 Internet Archive"""
    item_id = f"rthk-jiang-dong-jiang-xi-{ep_id}"
    filename = f"{ep_id}_0.mp3"
    file_size = os.path.getsize(mp3_path)
    
    # 轉換日期格式 DD/MM/YYYY -> YYYY-MM-DD
    try:
        day, month, year = date.split('/')
        iso_date = f"{year}-{month}-{day}"
    except:
        iso_date = date
    
    upload_url = f"https://s3.us.archive.org/{item_id}/{filename}"
    
    title_encoded = encode_header(f'RTHK 講東講西 - {title} ({date})')
    desc_encoded = encode_header(f'香港電台第一台《講東講西》節目 - {title}，播出日期：{date}')
    subject_encoded = encode_header('podcast;RTHK;講東講西;香港電台')
    creator_encoded = encode_header('RTHK Radio 1')
    
    headers = {
        'Authorization': f'LOW {IA_ACCESS_KEY}:{IA_SECRET_KEY}',
        'x-archive-meta-mediatype': 'audio',
        'x-archive-meta-collection': 'opensource_audio',
        'x-archive-meta-title': title_encoded,
        'x-archive-meta-creator': creator_encoded,
        'x-archive-meta-subject': subject_encoded,
        'x-archive-meta-description': desc_encoded,
        'x-archive-meta-language': 'zho',
        'x-archive-meta-date': iso_date,
        'x-archive-auto-make-bucket': '1',
        'Content-Type': 'audio/mpeg',
        'Content-Length': str(file_size),
    }
    
    with open(mp3_path, 'rb') as f:
        resp = requests.put(upload_url, data=f, headers=headers, timeout=600)
    
    print(f"  HTTP {resp.status_code}")
    
    if resp.status_code in [200, 201]:
        ia_url = f"https://archive.org/download/{item_id}/{filename}"
        return {
            'item_id': item_id,
            'url': ia_url,
            'size': file_size,
            'title': title,
            'date': date
        }
    else:
        print(f"  錯誤: {resp.text[:300]}")
        return None

def main():
    # 讀取 spotify_episode_mapping.json（包含 rthk_id）
    with open(f'{BASE_DIR}/spotify_episode_mapping.json', 'r', encoding='utf-8') as f:
        spotify_eps = json.load(f)
    
    print(f"Spotify mapping: {len(spotify_eps)} 集")
    
    # 讀取現有 ia_mapping
    ia_mapping_path = f'{BASE_DIR}/ia_mapping.json'
    try:
        with open(ia_mapping_path, 'r', encoding='utf-8') as f:
            ia_mapping = json.load(f)
        print(f"現有 ia_mapping: {len(ia_mapping)} 集")
    except:
        ia_mapping = {}
        print("ia_mapping: 空，重新開始")
    
    # 整理需要上傳的集數
    to_upload = []
    for ep in sorted(spotify_eps, key=lambda x: x.get('date', ''), reverse=False):
        rthk_id = str(ep.get('rthk_id', ''))
        title = ep.get('title', '?')
        date = ep.get('date', '?')
        
        if not rthk_id:
            print(f"  ⚠️  跳過（無 rthk_id）: {title}")
            continue
        
        # 檢查是否已在 ia_mapping
        if rthk_id in ia_mapping:
            print(f"  ✅ 已上傳: {title} ({date})")
            continue
        
        # 找 MP3 檔案
        mp3_path = f"{MP3_DIR}/{rthk_id}_0.mp3"
        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) < 100000:
            print(f"  ❌ 無 MP3: {title} ({date}) - {mp3_path}")
            continue
        
        to_upload.append({
            'id': rthk_id,
            'mp3_path': mp3_path,
            'title': title,
            'date': date
        })
    
    print(f"\n需要上傳: {len(to_upload)} 集")
    print("=" * 60)
    
    success = 0
    failed = 0
    
    for i, ep in enumerate(to_upload):
        mp3_size = os.path.getsize(ep['mp3_path']) / 1024 / 1024
        print(f"\n[{i+1}/{len(to_upload)}] {ep['title']} ({ep['date']}) [{mp3_size:.1f}MB]")
        print(f"  IA ID: rthk-jiang-dong-jiang-xi-{ep['id']}")
        
        result = upload_to_ia(ep['id'], ep['mp3_path'], ep['title'], ep['date'])
        
        if result:
            ia_mapping[ep['id']] = result
            success += 1
            print(f"  ✅ 成功: {result['url']}")
            
            # 立即儲存 mapping
            with open(ia_mapping_path, 'w', encoding='utf-8') as f:
                json.dump(ia_mapping, f, ensure_ascii=False, indent=2)
        else:
            failed += 1
            print(f"  ❌ 失敗")
        
        # 等待避免 rate limit
        if (i + 1) % 5 == 0:
            print("  等待 10 秒...")
            time.sleep(10)
        else:
            time.sleep(3)
    
    print("\n" + "=" * 60)
    print(f"完成！成功: {success} | 失敗: {failed}")
    print(f"ia_mapping.json 共 {len(ia_mapping)} 集")

if __name__ == '__main__':
    main()
