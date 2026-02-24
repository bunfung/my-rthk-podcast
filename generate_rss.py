#!/usr/bin/env python3
"""
生成 RTHK 講東講西 Podcast RSS feed
使用 Internet Archive 的 MP3 URL
"""
import os
import json
from datetime import datetime
from email.utils import formatdate
import xml.etree.ElementTree as ET
from xml.dom import minidom

PODCAST_TITLE = "RTHK 講東講西"
PODCAST_DESCRIPTION = "香港電台第一台《講東講西》節目，探討歷史、文化、社會等各類議題。"
PODCAST_LINK = "https://www.rthk.hk/radio/radio1/programme/Free_as_the_wind"
PODCAST_LANGUAGE = "zh-hk"
PODCAST_AUTHOR = "RTHK Radio 1"
PODCAST_IMAGE = "https://bunfung.github.io/my-rthk-podcast/logo.jpg"
BASE_DIR = '/home/ubuntu/rthk_podcast'

def parse_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return formatdate(dt.timestamp(), usegmt=True)
    except:
        return formatdate(usegmt=True)

def generate_rss():
    with open(f'{BASE_DIR}/episodes.json', 'r', encoding='utf-8') as f:
        episodes = json.load(f)
    
    ia_mapping = {}
    ia_mapping_path = f'{BASE_DIR}/ia_mapping.json'
    if os.path.exists(ia_mapping_path):
        with open(ia_mapping_path, 'r', encoding='utf-8') as f:
            ia_mapping = json.load(f)
    
    published_episodes = []
    for ep in episodes:
        ep_id = str(ep.get('id', ''))
        if ep_id in ia_mapping and ia_mapping[ep_id].get('http_code') == 200:
            ep['ia_url'] = ia_mapping[ep_id]['url']
            ep['ia_size'] = ia_mapping[ep_id].get('size', 0)
            published_episodes.append(ep)
    
    def sort_key(ep):
        try:
            return datetime.strptime(ep.get('date', '01/01/2000'), "%d/%m/%Y")
        except:
            return datetime.min
    
    published_episodes.sort(key=sort_key, reverse=True)
    print(f"生成 RSS feed，共 {len(published_episodes)} 集")
    
    rss = ET.Element('rss')
    rss.set('version', '2.0')
    rss.set('xmlns:itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
    rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
    
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = PODCAST_TITLE
    ET.SubElement(channel, 'link').text = PODCAST_LINK
    ET.SubElement(channel, 'description').text = PODCAST_DESCRIPTION
    ET.SubElement(channel, 'language').text = PODCAST_LANGUAGE
    ET.SubElement(channel, 'lastBuildDate').text = formatdate(usegmt=True)
    ET.SubElement(channel, 'itunes:author').text = PODCAST_AUTHOR
    ET.SubElement(channel, 'itunes:summary').text = PODCAST_DESCRIPTION
    ET.SubElement(channel, 'itunes:explicit').text = 'no'
    
    itunes_owner = ET.SubElement(channel, 'itunes:owner')
    ET.SubElement(itunes_owner, 'itunes:name').text = PODCAST_AUTHOR
    ET.SubElement(itunes_owner, 'itunes:email').text = 'bunfung.any@gmail.com'
    
    itunes_image = ET.SubElement(channel, 'itunes:image')
    itunes_image.set('href', PODCAST_IMAGE)
    
    image = ET.SubElement(channel, 'image')
    ET.SubElement(image, 'url').text = PODCAST_IMAGE
    ET.SubElement(image, 'title').text = PODCAST_TITLE
    ET.SubElement(image, 'link').text = PODCAST_LINK
    
    itunes_category = ET.SubElement(channel, 'itunes:category')
    itunes_category.set('text', 'Society &amp; Culture')
    
    for ep in published_episodes:
        ep_id = str(ep.get('id', ''))
        title = ep.get('title', f'Episode {ep_id}')
        date = ep.get('date', '')
        ia_url = ep.get('ia_url', '')
        ia_size = ep.get('ia_size', 0)
        
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = f"{title} - {date}"
        ET.SubElement(item, 'description').text = f"RTHK Radio 1 講東講西 - {title} ({date})"
        ET.SubElement(item, 'pubDate').text = parse_date(date)
        ET.SubElement(item, 'guid').text = f"rthk-jiang-dong-jiang-xi-{ep_id}"
        ET.SubElement(item, 'link').text = ia_url
        
        enclosure = ET.SubElement(item, 'enclosure')
        enclosure.set('url', ia_url)
        enclosure.set('type', 'audio/mpeg')
        enclosure.set('length', str(ia_size))
        
        ET.SubElement(item, 'itunes:title').text = f"{title} - {date}"
        ET.SubElement(item, 'itunes:summary').text = f"RTHK Radio 1 講東講西 - {title} ({date})"
        ET.SubElement(item, 'itunes:explicit').text = 'no'
        ET.SubElement(item, 'itunes:author').text = PODCAST_AUTHOR
    
    xml_str = ET.tostring(rss, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='  ', encoding='UTF-8').decode('utf-8')
    lines = pretty_xml.split('\n')
    if lines[0].startswith('<?xml'):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    pretty_xml = '\n'.join(lines)
    
    output_path = f'{BASE_DIR}/feed.xml'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(pretty_xml)
    
    print(f"✅ RSS feed 已生成：{output_path}")
    return output_path

if __name__ == '__main__':
    generate_rss()
