#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTHK 《講東講西》集數更新腳本
抓取新集數，並用主持人篩選規則過濾
篩選規則：
  - 有「主持：」欄 → 必須包含蘇奭、邱逸、馬鼎盛、馮天樂其中一位
  - 冇「主持：」欄 → 用「主持人：」欄判斷，必須包含以上其中一位
"""
import requests
import json
import re
import os
import logging
import time
from datetime import datetime, date
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/rthk_podcast/update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CHANNEL = "radio1"
PROGRAMME = "Free_as_the_wind"
BASE_URL = "https://www.rthk.hk"
START_DATE = date(2025, 10, 1)
EPISODES_FILE = "/home/ubuntu/rthk_podcast/episodes.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Referer": f"https://www.rthk.hk/radio/{CHANNEL}/programme/{PROGRAMME}",
}

# 符合條件的主持人名單
ALLOWED_HOSTS = ["蘇奭", "邱逸", "馬鼎盛", "馮天樂"]


def load_existing_episodes():
    """加載現有集數數據"""
    if os.path.exists(EPISODES_FILE):
        with open(EPISODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_episodes(episodes):
    """保存集數數據"""
    with open(EPISODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)
    logger.info(f"已保存 {len(episodes)} 個集數")


def parse_date(date_str):
    """解析日期字符串"""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except:
        return None


def clean_html(text):
    """清除 HTML 標籤"""
    return re.sub(r'<[^>]+>', '', text)


def check_host_qualification(ep_id):
    """
    檢查集數是否符合主持人條件
    規則：
      - 有「主持：」欄 → 必須包含 ALLOWED_HOSTS 其中一位（包括嘉賓欄）
      - 冇「主持：」欄 → 用「主持人：」欄判斷
    返回 (qualify: bool, rule_used: str, matched: list)
    """
    url = f'{BASE_URL}/radio/{CHANNEL}/programme/{PROGRAMME}/episode/{ep_id}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        text = resp.text

        # 從 popEpiTit 抓取目標集數的完整資料
        pop_match = re.search(r'popEpiTit.*?</div>\s*</div>\s*</div>', text, re.DOTALL)

        ep_hosts = []
        ep_guests = []
        programme_host_list = []

        if pop_match:
            pop_section = pop_match.group(0)

            # 從 epidesc 抓「主持：」欄（當集主持人，排除「主持人：」）
            epidesc_match = re.search(r'epidesc.*?</div>', pop_section, re.DOTALL)
            if epidesc_match:
                epidesc = epidesc_match.group(0)
                host_matches = re.findall(r'(?<![人])主持[：:]([^\n<\r]+)', epidesc)
                ep_hosts = list(set([clean_html(h).strip() for h in host_matches if clean_html(h).strip()]))
                guest_matches = re.findall(r'嘉賓[：:]([^\n<\r]+)', epidesc)
                ep_guests = list(set([clean_html(g).strip() for g in guest_matches if clean_html(g).strip()]))

            # 從 popEpiTit 的 <p> 抓「主持人：」欄（節目整體輪值）
            host_list_matches = re.findall(r'主持人[：:]([^\n<\r]+)', pop_section)
            programme_host_list = list(set([clean_html(h).strip() for h in host_list_matches if clean_html(h).strip()]))

        # 篩選邏輯
        if ep_hosts:
            # 有「主持：」欄 → 用主持 + 嘉賓判斷
            check_people = ep_hosts + ep_guests
            rule_used = '主持：'
        else:
            # 冇「主持：」欄 → 用「主持人：」欄判斷
            check_people = programme_host_list
            rule_used = '主持人：（節目整體）'

        matched = [h for h in ALLOWED_HOSTS if any(h in p for p in check_people)]
        qualify = len(matched) > 0

        return qualify, rule_used, matched

    except Exception as e:
        logger.error(f"檢查主持人失敗 (ep_id={ep_id}): {e}")
        return False, 'error', []


def get_available_months():
    """獲取可用月份列表"""
    url = f"{BASE_URL}/radio/{CHANNEL}/programme/{PROGRAMME}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    months = []

    select = soup.find('select', class_='selMonWrap')
    if select:
        for option in select.find_all('option'):
            val = option.get('value', '').strip()
            if val and len(val) == 6:
                months.append(val)

    return sorted(months, reverse=True)


def get_episodes_by_month(ym):
    """獲取指定月份的所有集數"""
    url = f"{BASE_URL}/radio/catchUpByMonth"
    params = {"c": CHANNEL, "p": PROGRAMME, "m": ym}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "1":
        return data.get("content", [])
    return []


def get_episode_audio_urls(episode_id):
    """獲取指定集數的音頻 URL"""
    url = f"{BASE_URL}/radio/getEpisode"
    params = {"c": CHANNEL, "p": PROGRAMME, "e": episode_id}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    audio_urls = re.findall(r'https://rthkaod2022[^"\']+master\.m3u8[^"\']*', resp.text)
    seen = set()
    unique_urls = []
    for u in audio_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    return unique_urls


def update_episodes():
    """更新集數數據，只添加符合主持人條件的新集數"""
    logger.info("開始更新集數...")

    # 加載現有集數
    existing = load_existing_episodes()
    existing_ids = {ep.get("id") for ep in existing}
    logger.info(f"現有集數: {len(existing)} 個")

    # 獲取可用月份
    months = get_available_months()
    logger.info(f"可用月份: {months}")

    new_episodes = []
    skipped_host = []

    for ym in months:
        year = int(ym[:4])
        month = int(ym[4:])

        if (year, month) < (2025, 10):
            break

        logger.info(f"檢查 {ym} 的集數...")
        episodes = get_episodes_by_month(ym)

        for ep in episodes:
            ep_id = ep.get("id")
            ep_date = parse_date(ep.get("date", ""))
            title = ep.get("title", "未知")

            if ep_date and ep_date >= START_DATE and ep_id not in existing_ids:
                logger.info(f"  新集數: {ep.get('date')} - {title} (ID: {ep_id})")

                # 檢查主持人條件
                qualify, rule_used, matched = check_host_qualification(ep_id)
                time.sleep(0.3)  # 避免過於頻繁請求

                if not qualify:
                    logger.info(f"  ❌ 不符合主持人條件 (規則: {rule_used}) - 跳過")
                    skipped_host.append(f"{ep.get('date')} - {title}")
                    existing_ids.add(ep_id)  # 標記為已處理，避免重複檢查
                    continue

                logger.info(f"  ✅ 符合條件 (規則: {rule_used}, 匹配: {matched})")

                # 獲取音頻 URL
                try:
                    audio_urls = get_episode_audio_urls(ep_id)
                    ep["audio_urls"] = audio_urls

                    part_info = []
                    for i, part_text in enumerate(ep.get("part", [])):
                        audio_url = audio_urls[i] if i < len(audio_urls) else ""
                        part_info.append({
                            "label": part_text,
                            "audio_url": audio_url,
                            "part_index": i
                        })
                    ep["part_info"] = part_info
                    ep["host_matched"] = matched
                    ep["host_rule"] = rule_used

                except Exception as e:
                    logger.error(f"  獲取音頻 URL 失敗: {e}")
                    ep["audio_urls"] = []
                    ep["part_info"] = []

                new_episodes.append(ep)
                existing_ids.add(ep_id)

    if skipped_host:
        logger.info(f"因主持人條件跳過 {len(skipped_host)} 集: {skipped_host}")

    if new_episodes:
        logger.info(f"找到 {len(new_episodes)} 個符合條件的新集數")
        updated = new_episodes + existing
        def sort_key(ep):
            d = parse_date(ep.get("date", ""))
            return d if d else date.min
        updated.sort(key=sort_key, reverse=True)
        save_episodes(updated)
        logger.info("更新完成！")
        return len(new_episodes)
    else:
        logger.info("沒有符合條件的新集數")
        return 0


if __name__ == "__main__":
    count = update_episodes()
    print(f"更新完成，新增 {count} 個符合條件的集數")
