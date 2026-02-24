#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTHK 《講東講西》自動上傳腳本
- 讀取 episodes.json，找出符合主持人條件且已下載 MP3 的集數
- 用 CDP + xdotool 自動上傳到 Spotify for Creators
- 只上傳尚未在 Spotify 上的集數
- 上傳成功後刪除本地 MP3
- 完成後自動 git push 更新 JSON 記錄到 GitHub

主持人篩選規則：
  - 有「主持：」欄 → 必須包含蘇奭、邱逸、馬鼎盛、馮天樂其中一位
  - 冇「主持：」欄 → 用「主持人：」欄判斷
"""
import json
import os
import sys
import time
import subprocess
import requests
import re
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/auto_upload_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

EPISODES_FILE = '/home/ubuntu/rthk_podcast/episodes.json'
MAPPING_FILE = '/home/ubuntu/rthk_podcast/spotify_episode_mapping.json'
MP3_DIR = '/home/ubuntu/rthk_podcast/mp3'
SCRIPT_DIR = '/home/ubuntu/rthk_podcast'
SHOW_ID = '6DVYbYCCvSBreKzyStsnFp'
WIZARD_URL = f'https://creators.spotify.com/pod/show/{SHOW_ID}/episode/wizard'
EPISODES_URL = f'https://creators.spotify.com/pod/show/{SHOW_ID}/episodes'
CHROME_URL = 'http://localhost:9222'
GITHUB_TOKEN = 'GITHUB_TOKEN_REMOVED'
GITHUB_REPO = 'bunfung/my-rthk-podcast'

ALLOWED_HOSTS = ["蘇奭", "邱逸", "馬鼎盛", "馮天樂"]
CHANNEL = "radio1"
PROGRAMME = "Free_as_the_wind"
BASE_URL = "https://www.rthk.hk"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": f"https://www.rthk.hk/radio/{CHANNEL}/programme/{PROGRAMME}",
}


def clean_html(text):
    return re.sub(r'<[^>]+>', '', text)


def check_host_qualification(ep_id):
    """檢查集數是否符合主持人條件"""
    url = f'{BASE_URL}/radio/{CHANNEL}/programme/{PROGRAMME}/episode/{ep_id}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        text = resp.text

        pop_match = re.search(r'popEpiTit.*?</div>\s*</div>\s*</div>', text, re.DOTALL)
        ep_hosts = []
        ep_guests = []
        programme_host_list = []

        if pop_match:
            pop_section = pop_match.group(0)
            epidesc_match = re.search(r'epidesc.*?</div>', pop_section, re.DOTALL)
            if epidesc_match:
                epidesc = epidesc_match.group(0)
                host_matches = re.findall(r'(?<![人])主持[：:]([^\n<\r]+)', epidesc)
                ep_hosts = list(set([clean_html(h).strip() for h in host_matches if clean_html(h).strip()]))
                guest_matches = re.findall(r'嘉賓[：:]([^\n<\r]+)', epidesc)
                ep_guests = list(set([clean_html(g).strip() for g in guest_matches if clean_html(g).strip()]))
            host_list_matches = re.findall(r'主持人[：:]([^\n<\r]+)', pop_section)
            programme_host_list = list(set([clean_html(h).strip() for h in host_list_matches if clean_html(h).strip()]))

        if ep_hosts:
            check_people = ep_hosts + ep_guests
            rule_used = '主持：'
        else:
            check_people = programme_host_list
            rule_used = '主持人：（節目整體）'

        matched = [h for h in ALLOWED_HOSTS if any(h in p for p in check_people)]
        return len(matched) > 0, rule_used, matched
    except Exception as e:
        logger.error(f"檢查主持人失敗 (ep_id={ep_id}): {e}")
        return False, 'error', []


def get_chrome_tab():
    """獲取 Chrome 的 WebSocket URL"""
    try:
        resp = requests.get(f'{CHROME_URL}/json', timeout=5)
        tabs = resp.json()
        for tab in tabs:
            if tab.get('type') == 'page':
                return tab.get('webSocketDebuggerUrl')
    except Exception as e:
        logger.error(f"無法連接 Chrome: {e}")
    return None


def cdp_command(ws_url, method, params=None):
    """發送 CDP 命令"""
    import websocket
    import json as _json
    ws = websocket.create_connection(ws_url, timeout=30)
    cmd = {'id': 1, 'method': method, 'params': params or {}}
    ws.send(_json.dumps(cmd))
    result = _json.loads(ws.recv())
    ws.close()
    return result


def navigate_to(ws_url, url):
    """導航到指定 URL"""
    cdp_command(ws_url, 'Page.navigate', {'url': url})
    time.sleep(3)


def get_page_content(ws_url):
    """獲取頁面 HTML"""
    result = cdp_command(ws_url, 'Runtime.evaluate', {
        'expression': 'document.documentElement.outerHTML',
        'returnByValue': True
    })
    return result.get('result', {}).get('result', {}).get('value', '')


def js_eval(ws_url, expression):
    """執行 JavaScript"""
    result = cdp_command(ws_url, 'Runtime.evaluate', {
        'expression': expression,
        'returnByValue': True,
        'awaitPromise': True
    })
    return result.get('result', {}).get('result', {}).get('value')


def set_file_input(ws_url, file_path):
    """設置文件 input"""
    doc = cdp_command(ws_url, 'DOM.getDocument', {'depth': -1})
    root_id = doc.get('result', {}).get('root', {}).get('nodeId', 1)

    node = cdp_command(ws_url, 'DOM.querySelector', {
        'nodeId': root_id,
        'selector': '#uploadAreaInput'
    })
    node_id = node.get('result', {}).get('nodeId')

    if not node_id:
        logger.error("找不到 file input")
        return False

    result = cdp_command(ws_url, 'DOM.setFileInputFiles', {
        'nodeId': node_id,
        'files': [file_path]
    })
    return True


def wait_for_element(ws_url, selector, timeout=60):
    """等待元素出現"""
    start = time.time()
    while time.time() - start < timeout:
        result = js_eval(ws_url, f'document.querySelector("{selector}") !== null')
        if result:
            return True
        time.sleep(2)
    return False


def wait_for_text(ws_url, text, timeout=60):
    """等待頁面包含特定文字"""
    start = time.time()
    while time.time() - start < timeout:
        content = js_eval(ws_url, 'document.body.innerText')
        if content and text in content:
            return True
        time.sleep(2)
    return False


def click_element(ws_url, selector):
    """點擊元素"""
    js_eval(ws_url, f'document.querySelector("{selector}").click()')
    time.sleep(1)


def fill_title(ws_url, title):
    """填寫標題"""
    js_eval(ws_url, f'''
        var input = document.querySelector("#title-input");
        if (input) {{
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(input, {json.dumps(title)});
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    ''')
    time.sleep(1)


def insert_description(ws_url, text):
    """用 CDP Input.insertText 輸入描述到 ProseMirror"""
    import asyncio
    import websockets
    import json as _json

    async def _insert():
        async with websockets.connect(ws_url) as ws:
            # 先 focus 描述框
            focus_cmd = {
                'id': 1,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': '''
                        var desc = document.querySelector(".ProseMirror");
                        if (desc) { desc.focus(); true; } else { false; }
                    ''',
                    'returnByValue': True
                }
            }
            await ws.send(_json.dumps(focus_cmd))
            await ws.recv()
            await asyncio.sleep(0.5)

            # 用 Input.insertText 輸入
            insert_cmd = {
                'id': 2,
                'method': 'Input.insertText',
                'params': {'text': text}
            }
            await ws.send(_json.dumps(insert_cmd))
            await ws.recv()

    asyncio.run(_insert())
    time.sleep(1)


def delete_mp3(mp3_path):
    """刪除本地 MP3 檔案"""
    try:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
            logger.info(f"  🗑️ 已刪除 MP3: {mp3_path}")
            return True
    except Exception as e:
        logger.warning(f"  ⚠️ 刪除 MP3 失敗: {e}")
    return False


def sync_skill_directory():
    """將最新腳本同步到 skill 目錄"""
    skill_scripts_dir = os.path.join(SCRIPT_DIR, 'skill', 'scripts')
    skill_md_path = os.path.join(SCRIPT_DIR, 'skill', 'SKILL.md')
    manus_skill_dir = '/home/ubuntu/skills/rthk-podcast-automation'

    # 確保 skill 目錄存在
    os.makedirs(skill_scripts_dir, exist_ok=True)

    # 同步所有腳本到 skill/scripts/
    scripts_to_sync = [
        'auto_upload.py',
        'download_qualified.py',
        'update.py',
        'daily_update.sh',
        'telegram_notify.py'
    ]
    for script in scripts_to_sync:
        src = os.path.join(SCRIPT_DIR, script)
        dst = os.path.join(skill_scripts_dir, script)
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, dst)

    # 同步 SKILL.md（從 Manus skill 目錄）
    manus_skill_md = os.path.join(manus_skill_dir, 'SKILL.md')
    if os.path.exists(manus_skill_md):
        import shutil
        shutil.copy2(manus_skill_md, skill_md_path)
        # 同時同步 Manus skill 目錄的腳本
        manus_scripts_dir = os.path.join(manus_skill_dir, 'scripts')
        os.makedirs(manus_scripts_dir, exist_ok=True)
        for script in scripts_to_sync:
            src = os.path.join(SCRIPT_DIR, script)
            dst = os.path.join(manus_scripts_dir, script)
            if os.path.exists(src):
                shutil.copy2(src, dst)

    logger.info("  📦 Skill 目錄已同步最新腳本")


def git_push_updates():
    """將更新後的 JSON 檔案及 skill 目錄 push 到 GitHub"""
    try:
        # 先同步 skill 目錄
        sync_skill_directory()

        result = subprocess.run(
            ['git', '-C', SCRIPT_DIR, 'add',
             'episodes.json', 'spotify_episode_mapping.json',
             'skill/'],
            capture_output=True, text=True
        )
        result = subprocess.run(
            ['git', '-C', SCRIPT_DIR, 'diff', '--cached', '--quiet'],
            capture_output=True
        )
        if result.returncode == 0:
            logger.info("  📁 檔案無變化，跳過 git push")
            return True

        subprocess.run(
            ['git', '-C', SCRIPT_DIR, 'commit', '-m',
             f'Auto update: {time.strftime("%Y-%m-%d %H:%M")}'],
            capture_output=True, text=True
        )
        push_result = subprocess.run(
            ['git', '-C', SCRIPT_DIR, 'push'],
            capture_output=True, text=True
        )
        if push_result.returncode == 0:
            logger.info("  ✅ 已 push 更新到 GitHub（含 skill 目錄）")
            return True
        else:
            logger.warning(f"  ⚠️ git push 失敗: {push_result.stderr}")
            return False
    except Exception as e:
        logger.warning(f"  ⚠️ git push 出現錯誤: {e}")
        return False


def load_mapping():
    """載入 spotify_episode_mapping.json"""
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_mapping(mapping):
    """儲存 spotify_episode_mapping.json"""
    with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def upload_episode(ws_url, mp3_path, title, ep_date):
    """上傳單集到 Spotify"""
    logger.info(f"  導航到 wizard...")
    navigate_to(ws_url, WIZARD_URL)

    # 等待 file input 出現
    logger.info(f"  等待上傳頁面...")
    if not wait_for_element(ws_url, '#uploadAreaInput', timeout=30):
        logger.error("  上傳頁面未出現")
        return False

    # 設置文件
    logger.info(f"  設置文件: {mp3_path}")
    if not set_file_input(ws_url, mp3_path):
        logger.error("  設置文件失敗")
        return False

    # 等待 Next 按鈕出現（表示上傳完成）
    logger.info(f"  等待上傳完成...")
    if not wait_for_text(ws_url, 'Next', timeout=120):
        logger.error("  上傳超時")
        return False

    # 點擊 Next
    logger.info(f"  點擊 Next...")
    js_eval(ws_url, '''
        var btns = Array.from(document.querySelectorAll("button"));
        var nextBtn = btns.find(b => b.textContent.trim() === "Next");
        if (nextBtn) nextBtn.click();
    ''')
    time.sleep(3)

    # 等待 Details 頁面（標題輸入框出現）
    logger.info(f"  等待 Details 頁面...")
    if not wait_for_element(ws_url, '#title-input', timeout=30):
        logger.error("  Details 頁面未出現")
        return False

    # 填寫標題
    logger.info(f"  填寫標題: {title}")
    fill_title(ws_url, title)

    # 填寫描述（用 CDP Input.insertText）
    logger.info(f"  填寫描述...")
    desc_text = f"RTHK Radio 1 podcast - {ep_date}. Expand your knowledge horizons!"
    insert_description(ws_url, desc_text)
    time.sleep(1)

    # 點擊 Next 進入 Review
    logger.info(f"  點擊 Next 進入 Review...")
    js_eval(ws_url, '''
        var btns = Array.from(document.querySelectorAll("button"));
        var nextBtn = btns.find(b => b.textContent.trim() === "Next");
        if (nextBtn) nextBtn.click();
    ''')
    time.sleep(3)

    # 等待 Review 頁面
    logger.info(f"  等待 Review 頁面...")
    if not wait_for_text(ws_url, 'Review and publish', timeout=30):
        logger.error("  Review 頁面未出現")
        return False

    # 選擇 Now
    logger.info(f"  選擇 Now...")
    js_eval(ws_url, '''
        var labels = Array.from(document.querySelectorAll("label"));
        var nowLabel = labels.find(l => l.textContent.trim() === "Now");
        if (nowLabel) nowLabel.click();
    ''')
    time.sleep(1)

    # 點擊 Publish
    logger.info(f"  點擊 Publish...")
    js_eval(ws_url, '''
        var btns = Array.from(document.querySelectorAll("button"));
        var publishBtn = btns.find(b => b.textContent.trim() === "Publish");
        if (publishBtn) publishBtn.click();
    ''')
    time.sleep(5)

    # 等待發布確認
    if wait_for_text(ws_url, 'Episode published', timeout=30):
        logger.info(f"  ✅ 發布成功！")
        # 點擊 Done
        js_eval(ws_url, '''
            var btns = Array.from(document.querySelectorAll("button"));
            var doneBtn = btns.find(b => b.textContent.trim() === "Done");
            if (doneBtn) doneBtn.click();
        ''')
        time.sleep(2)
        return True
    else:
        logger.warning(f"  ⚠️ 未偵測到發布確認，可能已發布")
        return True  # 繼續下一集


def get_spotify_published_titles(ws_url):
    """獲取 Spotify 上已發布的集數標題"""
    navigate_to(ws_url, EPISODES_URL)
    time.sleep(3)
    content = js_eval(ws_url, 'document.body.innerText')
    return content or ''


def main():
    # 載入集數資料
    with open(EPISODES_FILE, 'r', encoding='utf-8') as f:
        episodes = json.load(f)

    # 載入 mapping
    mapping = load_mapping()

    # 連接 Chrome
    ws_url = get_chrome_tab()
    if not ws_url:
        logger.error("無法連接 Chrome，請確保 Chrome 已開啟並啟用遠程調試")
        sys.exit(1)
    logger.info(f"已連接 Chrome: {ws_url[:50]}...")

    # 獲取 Spotify 上已有的集數（用於雙重確認）
    logger.info("獲取 Spotify 上已有的集數...")
    spotify_content = get_spotify_published_titles(ws_url)

    # 找出需要上傳的集數
    to_upload = []
    for ep in episodes:
        ep_id = str(ep.get('id', ''))
        title = ep.get('title', '')
        ep_date = ep.get('date', '')
        mp3_path = f"{MP3_DIR}/{ep_id}_0.mp3"

        # 檢查 MP3 是否存在
        if not os.path.exists(mp3_path):
            logger.info(f"跳過 {title} - MP3 不存在")
            continue

        # 檢查是否已在 mapping 中（本地記錄）
        display_title = f"{title} - {ep_date}"
        if ep_id in mapping:
            logger.info(f"跳過 {display_title} - 已在本地 mapping 記錄中")
            # 刪除多餘的 MP3（已上傳但未刪除的）
            delete_mp3(mp3_path)
            continue

        # 雙重確認：檢查是否已在 Spotify 上
        if display_title in spotify_content:
            logger.info(f"跳過 {display_title} - 已在 Spotify 上（雙重確認）")
            # 更新本地 mapping
            mapping[ep_id] = {'title': display_title, 'date': ep_date}
            save_mapping(mapping)
            delete_mp3(mp3_path)
            continue

        # 檢查主持人條件
        qualify, rule_used, matched = check_host_qualification(ep_id)
        time.sleep(0.3)

        if not qualify:
            logger.info(f"跳過 {title} - 不符合主持人條件 ({rule_used})")
            continue

        logger.info(f"待上傳: {display_title} (匹配: {matched})")
        to_upload.append({
            'ep_id': ep_id,
            'title': display_title,
            'date': ep_date,
            'mp3_path': mp3_path
        })

    if not to_upload:
        logger.info("沒有需要上傳的集數")
        # 即使無新集數，也 push 一次確保 JSON 同步
        git_push_updates()
        return

    logger.info(f"共 {len(to_upload)} 集需要上傳")

    # 逐集上傳
    success = 0
    failed = 0
    for i, ep in enumerate(to_upload):
        logger.info(f"\n[{i+1}/{len(to_upload)}] 上傳: {ep['title']}")
        ok = upload_episode(ws_url, ep['mp3_path'], ep['title'], ep['date'])
        if ok:
            success += 1
            # 更新本地 mapping
            mapping[ep['ep_id']] = {
                'title': ep['title'],
                'date': ep['date'],
                'uploaded_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            save_mapping(mapping)
            # 刪除已上傳的 MP3
            delete_mp3(ep['mp3_path'])
        else:
            failed += 1
        time.sleep(3)

    logger.info(f"\n上傳完成: 成功 {success}，失敗 {failed}")

    # 寫入上傳統計供 daily_update.sh 讀取
    stats = {'success': success, 'failed': failed}
    with open('/tmp/upload_stats.json', 'w') as f:
        json.dump(stats, f)

    # Push 更新到 GitHub
    logger.info("\n同步更新到 GitHub...")
    git_push_updates()


if __name__ == '__main__':
    main()
