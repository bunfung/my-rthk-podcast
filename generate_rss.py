#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從 ia_mapping.json 生成 RSS feed XML
供 Downcast 等 Podcast 客戶端訂閱
"""
import json
import os
import re
from datetime import datetime

BASE_DIR = '/home/ubuntu/rthk_podcast'
IA_MAPPING_FILE = f'{BASE_DIR}/ia_mapping.json'
FEED_FILE = f'{BASE_DIR}/feed.xml'

# Podcast 基本資訊
PODCAST_TITLE = "RTHK 講東講西"
PODCAST_DESCRIPTION = "香港電台第一台《講東講西》節目精選集數，主持人：蘇奭、邱逸、馬鼎盛、馮天樂"
PODCAST_LINK = "https://www.rthk.hk/radio/radio1/programme/Free_as_the_wind"
PODCAST_IMAGE = "https://bunfung.github.io/my-rthk-podcast/podcast_logo.jpg"
PODCAST_AUTHOR = "RTHK Radio 1"
PODCAST_EMAIL = "bunfung.any@gmail.com"
PODCAST_LANGUAGE = "zh-hk"
FEED_URL = "https://bunfung.github.io/my-rthk-podcast/feed.xml"


def parse_date_to_rfc2822(date_str):
    """將 DD/MM/YYYY 格式轉換為 RFC 2822 格式"""
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        # RFC 2822 格式
        return dt.strftime("%a, %d %b %Y 22:30:00 +0800")
    except:
        return datetime.now().strftime("%a, %d %b %Y 22:30:00 +0800")


def escape_xml(text):
    """轉義 XML 特殊字符"""
    if not text:
        return ""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    return text


def generate_rss():
    """生成 RSS feed"""
    # 讀取 ia_mapping
    if not os.path.exists(IA_MAPPING_FILE):
        print(f"錯誤：找不到 {IA_MAPPING_FILE}")
        return False
    
    with open(IA_MAPPING_FILE, 'r', encoding='utf-8') as f:
        ia_mapping = json.load(f)
    
    print(f"讀取到 {len(ia_mapping)} 集")
    
    # 按日期排序（最新在前）
    episodes = []
    for ep_id, info in ia_mapping.items():
        episodes.append({
            'id': ep_id,
            'title': info.get('title', f'Episode {ep_id}'),
            'date': info.get('date', ''),
            'url': info.get('url', ''),
            'size': info.get('size', 0),
            'item_id': info.get('item_id', f'rthk-jiang-dong-jiang-xi-{ep_id}'),
        })
    
    # 按日期排序（最新在前）
    def sort_key(ep):
        try:
            return datetime.strptime(ep['date'], "%d/%m/%Y")
        except:
            return datetime.min
    
    episodes.sort(key=sort_key, reverse=True)
    
    # 生成 RSS XML
    now_rfc2822 = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
    
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        f'    <title>{escape_xml(PODCAST_TITLE)}</title>',
        f'    <description>{escape_xml(PODCAST_DESCRIPTION)}</description>',
        f'    <link>{PODCAST_LINK}</link>',
        f'    <language>{PODCAST_LANGUAGE}</language>',
        f'    <lastBuildDate>{now_rfc2822}</lastBuildDate>',
        f'    <atom:link href="{FEED_URL}" rel="self" type="application/rss+xml"/>',
        f'    <itunes:author>{escape_xml(PODCAST_AUTHOR)}</itunes:author>',
        f'    <itunes:summary>{escape_xml(PODCAST_DESCRIPTION)}</itunes:summary>',
        f'    <itunes:owner>',
        f'      <itunes:name>{escape_xml(PODCAST_AUTHOR)}</itunes:name>',
        f'      <itunes:email>{PODCAST_EMAIL}</itunes:email>',
        f'    </itunes:owner>',
        f'    <itunes:image href="{PODCAST_IMAGE}"/>',
        f'    <itunes:category text="Society &amp; Culture"/>',
        f'    <itunes:explicit>false</itunes:explicit>',
    ]
    
    for ep in episodes:
        title = ep['title']
        date = ep['date']
        url = ep['url']
        size = ep['size']
        ep_id = ep['id']
        item_id = ep['item_id']
        
        pub_date = parse_date_to_rfc2822(date)
        ia_page_url = f"https://archive.org/details/{item_id}"
        
        xml_lines.extend([
            '    <item>',
            f'      <title>{escape_xml(title)} ({escape_xml(date)})</title>',
            f'      <description>{escape_xml(f"RTHK 講東講西 - {title}，播出日期：{date}")}</description>',
            f'      <link>{ia_page_url}</link>',
            f'      <guid isPermaLink="false">{item_id}</guid>',
            f'      <pubDate>{pub_date}</pubDate>',
            f'      <enclosure url="{url}" length="{size}" type="audio/mpeg"/>',
            f'      <itunes:title>{escape_xml(title)}</itunes:title>',
            f'      <itunes:author>{escape_xml(PODCAST_AUTHOR)}</itunes:author>',
            f'      <itunes:summary>{escape_xml(f"RTHK 講東講西 - {title}，播出日期：{date}")}</itunes:summary>',
            f'      <itunes:image href="{PODCAST_IMAGE}"/>',
            f'      <itunes:duration>5400</itunes:duration>',
            f'      <itunes:explicit>false</itunes:explicit>',
            '    </item>',
        ])
    
    xml_lines.extend([
        '  </channel>',
        '</rss>',
    ])
    
    xml_content = '\n'.join(xml_lines)
    
    with open(FEED_FILE, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    print(f"✅ RSS feed 已生成: {FEED_FILE}")
    print(f"   共 {len(episodes)} 集")
    return True


if __name__ == '__main__':
    generate_rss()
