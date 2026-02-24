#!/usr/bin/env python3
"""
批量發布所有 Untitled episodes 腳本
使用 CDP (Chrome DevTools Protocol) 自動化瀏覽器操作
"""

import asyncio
import json
import time
import websockets
import requests
import sys

CDP_URL = 'http://127.0.0.1:9222'
SHOW_ID = '6DVYbYCCvSBreKzyStsnFp'

# 所有需要發布的 episodes（已排除已發布的 4 個和已處理的王陽明和佛學）
EPISODES_TO_PUBLISH = [
    {"spotify_id": "1IyfFH4wHBox2S79t7Zmd2", "title": "納粹軍官拯救一千猶太人", "date": "26/01/2026"},
    {"spotify_id": "1wRS9iONRVDcCdKpdjIciQ", "title": "赤馬紅羊是禍是福？", "date": "21/01/2026"},
    {"spotify_id": "2a13JxeVrtltKsDqbEMGuN", "title": "重慶防空洞菜市場", "date": "19/01/2026"},
    {"spotify_id": "4KYLbh3HYvONQM3cTEAuTf", "title": "巨貪嚴嵩", "date": "31/12/2025"},
    {"spotify_id": "21HYc8ioSawI3e789h9BIn", "title": "農民運動大王彭湃", "date": "29/12/2025"},
    {"spotify_id": "4HuR1wpDlXMlu7HRKCdPML", "title": "大禮議", "date": "24/12/2025"},
    {"spotify_id": "5GlnRzFCQ8YnOSXGSNFxrf", "title": "中國電建調撥75億元在建項目", "date": "22/12/2025"},
    {"spotify_id": "6vVN2wpUjYyTtQz2t3BGhQ", "title": "古今的眼睛與視力", "date": "26/11/2025"},
    {"spotify_id": "44uoAcDGzD1PUXDxu7EDo6", "title": "粵語流行曲的文化流向", "date": "24/11/2025"},
    {"spotify_id": "48Y6lyzpD6QJ9nKNHxwYix", "title": "明憲宗與萬貴妃", "date": "19/11/2025"},
    {"spotify_id": "6GpU0RSkLhemgWVZ2vWkmh", "title": "一孩政策三十六年", "date": "17/11/2025"},
    {"spotify_id": "1zH5UkT8dJkVDQ0gaAzzKd", "title": "朱高熾之亂", "date": "29/10/2025"},
    {"spotify_id": "7I2Yte3IVqHcWDqvsQ8uMc", "title": "香港體育會百年歷史", "date": "28/10/2025"},
    {"spotify_id": "0qhS07O0NjUHWvbri7BbVA", "title": "二戰美軍在巴黎腐敗", "date": "27/10/2025"},
    {"spotify_id": "4MMms6T040X6LQXHNIsGr2", "title": "中史科優化", "date": "22/10/2025"},
    {"spotify_id": "6EhWQJICyiFVIhrhkVjSfu", "title": "陳景潤的故事", "date": "20/10/2025"},
]

def get_ws_url():
    resp = requests.get(f'{CDP_URL}/json')
    tabs = resp.json()
    for tab in tabs:
        if tab.get('type') == 'page':
            return tab['webSocketDebuggerUrl']
    return None

async def send_cdp(ws, method, params=None):
    msg_id = int(time.time() * 1000) % 1000000
    cmd = {'id': msg_id, 'method': method}
    if params:
        cmd['params'] = params
    await ws.send(json.dumps(cmd))
    while True:
        msg = await asyncio.wait_for(ws.recv(), timeout=30)
        data = json.loads(msg)
        if data.get('id') == msg_id:
            return data

async def navigate_to(ws, url):
    """導航到指定 URL"""
    result = await send_cdp(ws, 'Page.navigate', {'url': url})
    # 等待頁面載入
    await asyncio.sleep(3)
    return result

async def wait_for_element(ws, selector, timeout=15):
    """等待元素出現"""
    start = time.time()
    while time.time() - start < timeout:
        result = await send_cdp(ws, 'Runtime.evaluate', {
            'expression': f'document.querySelector("{selector}") !== null',
            'returnByValue': True
        })
        if result.get('result', {}).get('result', {}).get('value'):
            return True
        await asyncio.sleep(0.5)
    return False

async def fill_title(ws, title):
    """填入標題"""
    result = await send_cdp(ws, 'Runtime.evaluate', {
        'expression': '''
        (function() {
            var input = document.querySelector('input#title-input');
            if (!input) return false;
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(input, arguments[0]);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        })()
        '''.replace('arguments[0]', f'"{title}"'),
        'returnByValue': True
    })
    return result.get('result', {}).get('result', {}).get('value', False)

async def fill_description(ws, description):
    """填入描述"""
    # 先確保描述欄有焦點
    await send_cdp(ws, 'Runtime.evaluate', {
        'expression': '''
        (function() {
            var editor = document.querySelector('div[role="textbox"]');
            if (editor) {
                editor.click();
                editor.focus();
                return true;
            }
            return false;
        })()
        ''',
        'returnByValue': True
    })
    await asyncio.sleep(0.3)
    
    # 用 Input.insertText 輸入文字
    result = await send_cdp(ws, 'Input.insertText', {'text': description})
    await asyncio.sleep(0.3)
    
    # 驗證字數
    verify = await send_cdp(ws, 'Runtime.evaluate', {
        'expression': '''
        (function() {
            var allEls = Array.from(document.querySelectorAll("*"));
            var countEl = allEls.find(el => el.children.length === 0 && /^\\d+ \\/ 4000$/.test(el.textContent.trim()));
            return countEl ? countEl.textContent.trim() : "0 / 4000";
        })()
        ''',
        'returnByValue': True
    })
    count = verify.get('result', {}).get('result', {}).get('value', '0 / 4000')
    return count

async def click_next(ws):
    """點擊 Next 按鈕"""
    result = await send_cdp(ws, 'Runtime.evaluate', {
        'expression': '''
        (function() {
            var buttons = Array.from(document.querySelectorAll("button"));
            var nextBtn = buttons.find(b => b.textContent.trim() === "Next");
            if (nextBtn) {
                nextBtn.click();
                return true;
            }
            return false;
        })()
        ''',
        'returnByValue': True
    })
    await asyncio.sleep(2)
    return result.get('result', {}).get('result', {}).get('value', False)

async def select_now_and_publish(ws):
    """選擇 Now 並點擊 Publish"""
    # 選擇 Now
    await send_cdp(ws, 'Runtime.evaluate', {
        'expression': '''
        (function() {
            var nowRadio = document.querySelector('input#publish-date-now');
            if (nowRadio && !nowRadio.checked) {
                nowRadio.click();
            }
            return nowRadio ? nowRadio.checked : false;
        })()
        ''',
        'returnByValue': True
    })
    await asyncio.sleep(0.5)
    
    # 點擊 Publish
    result = await send_cdp(ws, 'Runtime.evaluate', {
        'expression': '''
        (function() {
            var buttons = Array.from(document.querySelectorAll("button"));
            var publishBtn = buttons.find(b => b.textContent.trim() === "Publish");
            if (publishBtn) {
                publishBtn.click();
                return true;
            }
            return false;
        })()
        ''',
        'returnByValue': True
    })
    await asyncio.sleep(3)
    return result.get('result', {}).get('result', {}).get('value', False)

async def check_published(ws):
    """檢查是否已成功發布"""
    result = await send_cdp(ws, 'Runtime.evaluate', {
        'expression': '''
        (function() {
            var allText = document.body.textContent;
            return allText.includes("Episode published") || allText.includes("published!");
        })()
        ''',
        'returnByValue': True
    })
    return result.get('result', {}).get('result', {}).get('value', False)

async def get_current_url(ws):
    """獲取當前 URL"""
    result = await send_cdp(ws, 'Runtime.evaluate', {
        'expression': 'window.location.href',
        'returnByValue': True
    })
    return result.get('result', {}).get('result', {}).get('value', '')

async def publish_episode(ws, episode):
    """發布單個 episode"""
    spotify_id = episode['spotify_id']
    title = episode['title']
    date = episode['date']
    description = f'RTHK Radio 1《講東講西》節目 - {date}播出。擴闊知識領域，網羅文化通識！'
    full_title = f'{title} - {date}'
    
    wizard_url = f'https://creators.spotify.com/pod/show/{SHOW_ID}/episode/{spotify_id}/wizard'
    
    print(f'\n處理: {full_title}')
    print(f'  URL: {wizard_url}')
    
    # 導航到 wizard 頁面
    await navigate_to(ws, wizard_url)
    
    # 等待標題輸入框出現
    found = await wait_for_element(ws, 'input#title-input', timeout=15)
    if not found:
        print(f'  錯誤: 找不到標題輸入框')
        return False
    
    # 填入標題
    title_ok = await fill_title(ws, full_title)
    if not title_ok:
        print(f'  錯誤: 填入標題失敗')
        return False
    print(f'  標題已填入: {full_title}')
    
    # 填入描述
    count = await fill_description(ws, description)
    print(f'  描述已填入: {count}')
    
    if count == '0 / 4000':
        print(f'  警告: 描述可能未填入成功')
    
    # 點擊 Next
    next_ok = await click_next(ws)
    if not next_ok:
        print(f'  錯誤: 點擊 Next 失敗')
        return False
    print(f'  已點擊 Next')
    
    # 等待 Review 頁面
    await asyncio.sleep(2)
    
    # 選擇 Now 並發布
    publish_ok = await select_now_and_publish(ws)
    if not publish_ok:
        print(f'  錯誤: 點擊 Publish 失敗')
        return False
    
    # 等待發布完成
    await asyncio.sleep(3)
    
    # 檢查是否成功
    published = await check_published(ws)
    if published:
        print(f'  ✅ 成功發布!')
        return True
    else:
        # 檢查當前 URL
        url = await get_current_url(ws)
        print(f'  ⚠️  未確認發布成功，當前 URL: {url}')
        # 如果已跳轉到 episodes 頁面，也算成功
        if '/episodes' in url and '/wizard' not in url:
            print(f'  ✅ 已跳轉到 episodes 頁面，視為成功')
            return True
        return False

async def main():
    ws_url = get_ws_url()
    if not ws_url:
        print('錯誤: 無法連接到 Chrome CDP')
        sys.exit(1)
    
    print(f'連接到 Chrome CDP: {ws_url}')
    print(f'需要處理 {len(EPISODES_TO_PUBLISH)} 個 episodes')
    
    results = []
    
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        for i, episode in enumerate(EPISODES_TO_PUBLISH):
            print(f'\n[{i+1}/{len(EPISODES_TO_PUBLISH)}] 處理 episode...')
            
            success = await publish_episode(ws, episode)
            results.append({
                'spotify_id': episode['spotify_id'],
                'title': episode['title'],
                'date': episode['date'],
                'success': success
            })
            
            if success:
                # 等待一下再處理下一個
                await asyncio.sleep(2)
            else:
                print(f'  跳過此 episode，繼續下一個')
                await asyncio.sleep(1)
    
    # 輸出結果
    print('\n\n=== 發布結果 ===')
    success_count = sum(1 for r in results if r['success'])
    fail_count = len(results) - success_count
    
    print(f'成功: {success_count}/{len(results)}')
    print(f'失敗: {fail_count}/{len(results)}')
    
    if fail_count > 0:
        print('\n失敗的 episodes:')
        for r in results:
            if not r['success']:
                print(f'  - {r["title"]} ({r["spotify_id"]})')
    
    # 儲存結果
    with open('/tmp/publish_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print('\n結果已儲存到 /tmp/publish_results.json')

if __name__ == '__main__':
    asyncio.run(main())
