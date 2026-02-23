#!/usr/bin/env python3
"""
最終版：抓取 2025-10-01 後所有講東講西集數的主持人資料
使用 popEpiTit div 正確抓取目標集數的主持人資料

規則：
- 有「主持：」欄（在 epidesc 裡）→ 用「主持：」欄（及「嘉賓：」欄）判斷
- 冇「主持：」欄 → 用「主持人：」欄（節目整體，在 popEpiTit 裡）判斷
"""
import requests, json, re, time
from datetime import datetime, date

BASE_URL = 'https://www.rthk.hk'
CHANNEL = 'radio1'
PROGRAMME = 'Free_as_the_wind'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': f'https://www.rthk.hk/radio/{CHANNEL}/programme/{PROGRAMME}',
}

ALLOWED_HOSTS = ['蘇奭', '邱逸', '馬鼎盛', '馮天樂']

def clean_html(s):
    return re.sub(r'<[^>]+>', '', s).strip()

def get_host_info(ep_id, ep_title=''):
    """
    從 RTHK 網頁抓取當集主持人資料
    使用 popEpiTit div 正確抓取目標集數的主持人資料
    """
    url = f'{BASE_URL}/radio/{CHANNEL}/programme/{PROGRAMME}/episode/{ep_id}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        text = resp.text
        
        # 從 popEpiTit 抓取（目標集數的完整資料）
        pop_match = re.search(r'popEpiTit.*?</div>\s*</div>\s*</div>', text, re.DOTALL)
        
        ep_hosts = []
        ep_guests = []
        programme_host_list = []
        
        if pop_match:
            pop_section = pop_match.group(0)
            
            # 從 epidesc 抓「主持：」欄（當集主持人）
            epidesc_match = re.search(r'epidesc.*?</div>', pop_section, re.DOTALL)
            if epidesc_match:
                epidesc = epidesc_match.group(0)
                host_matches = re.findall(r'(?<![人])主持[：:]([^\n<\r]+)', epidesc)
                ep_hosts = list(set([clean_html(h).strip() for h in host_matches if clean_html(h).strip()]))
                guest_matches = re.findall(r'嘉賓[：:]([^\n<\r]+)', epidesc)
                ep_guests = list(set([clean_html(g).strip() for g in guest_matches if clean_html(g).strip()]))
            
            # 從 popEpiTit 的 <p> 抓「主持人：」欄（節目整體）
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
        
        return {
            'programme_host_list': programme_host_list,
            'ep_hosts': ep_hosts,
            'ep_guests': ep_guests,
            'rule_used': rule_used,
            'matched': matched,
            'qualify': qualify
        }
    except Exception as e:
        return {
            'error': str(e),
            'qualify': False,
            'rule_used': 'error',
            'matched': [],
            'ep_hosts': [],
            'ep_guests': [],
            'programme_host_list': []
        }

# 抓取所有集數
all_eps = []
months = ['202510','202511','202512','202601','202602']
for ym in months:
    url = f'{BASE_URL}/radio/catchUpByMonth'
    params = {'c': CHANNEL, 'p': PROGRAMME, 'm': ym}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    data = resp.json()
    if data.get('status') == '1':
        all_eps.extend(data.get('content', []))

# 按日期排序（最舊到最新）
def parse_date(s):
    try:
        return datetime.strptime(s, '%d/%m/%Y').date()
    except:
        return date.min

all_eps.sort(key=lambda e: parse_date(e.get('date', '')))

print(f'共 {len(all_eps)} 集，開始逐集檢查主持人...\n')

results = []
qualified = []
not_qualified = []

for i, ep in enumerate(all_eps):
    ep_id = ep.get('id', '')
    title = ep.get('title', '')
    ep_date = ep.get('date', '')
    
    info = get_host_info(ep_id, title)
    
    qualify = info.get('qualify', False)
    rule = info.get('rule_used', '')
    matched = info.get('matched', [])
    ep_hosts = info.get('ep_hosts', [])
    ep_guests = info.get('ep_guests', [])
    programme_host_list = info.get('programme_host_list', [])
    
    status = '✅' if qualify else '❌'
    
    result = {
        'id': ep_id,
        'title': title,
        'date': ep_date,
        'qualify': qualify,
        'rule_used': rule,
        'matched': matched,
        'ep_hosts': ep_hosts,
        'ep_guests': ep_guests,
        'programme_host_list': programme_host_list
    }
    results.append(result)
    
    if qualify:
        qualified.append(result)
    else:
        not_qualified.append(result)
    
    # 顯示進度
    host_info = ''
    if ep_hosts:
        host_info = f'主持：{", ".join(ep_hosts[:2])}'
        if ep_guests:
            host_info += f' | 嘉賓：{", ".join(ep_guests[:2])}'
    elif programme_host_list:
        host_info = f'主持人（整體）：{programme_host_list[0][:50]}' if programme_host_list else ''
    
    print(f'{status} [{ep_date}] {title}')
    if host_info:
        print(f'   {host_info}')
    if matched:
        print(f'   匹配：{matched}')
    
    time.sleep(0.3)

# 儲存結果
with open('/home/ubuntu/rthk_podcast/host_check_final.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f'\n{"="*60}')
print(f'符合條件：{len(qualified)}/{len(all_eps)} 集')
print(f'不符合條件：{len(not_qualified)}/{len(all_eps)} 集')
print(f'\n✅ 符合條件的集數：')
for r in qualified:
    hosts_info = r.get('ep_hosts', []) or r.get('programme_host_list', [])
    print(f'  [{r["date"]}] {r["title"]} → 匹配：{r["matched"]} | 規則：{r["rule_used"]}')
print(f'\n❌ 不符合條件的集數：')
for r in not_qualified:
    hosts_info = ''
    if r.get('ep_hosts'):
        hosts_info = f'（主持：{r["ep_hosts"]}）'
    print(f'  [{r["date"]}] {r["title"]} {hosts_info}')
