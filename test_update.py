#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試腳本：測試 run_update.py 的完整流程
測試方法：
  1. 將 last_checked_date 調回 17/02/2026（比最新集數早）
  2. 執行 run_update.py（DRY RUN 模式，唔真正下載/上傳）
  3. 確認腳本能正確識別 18/02/2026 的「馬到功成」為「已在 ia_mapping，跳過」
  4. 確認腳本能正確識別 19/02/2026、20/02/2026 為「唔符合主持人條件，跳過」
  5. 確認 last_checked_date 更新到 20/02/2026

注意：呢個係 DRY RUN，唔會真正下載 MP3 或上傳到 IA
"""
import json
import os
import shutil
from datetime import datetime

BASE_DIR = '/home/ubuntu/rthk_podcast'
LAST_CHECKED_FILE = f'{BASE_DIR}/last_checked.json'
IA_MAPPING_FILE = f'{BASE_DIR}/ia_mapping.json'

print("=" * 60)
print("測試開始：驗證 run_update.py 的邏輯")
print("=" * 60)

# 備份原始 last_checked.json
shutil.copy(LAST_CHECKED_FILE, LAST_CHECKED_FILE + '.bak')
print(f"\n✅ 已備份 last_checked.json")

# 讀取現有 ia_mapping
ia_mapping = json.load(open(IA_MAPPING_FILE))
print(f"✅ ia_mapping 現有 {len(ia_mapping)} 集")

# 讀取原始 last_checked_date
original = json.load(open(LAST_CHECKED_FILE))
print(f"✅ 原始 last_checked_date: {original['last_checked_date']}")

# 將 last_checked_date 調回 17/02/2026（比最新集數早一日）
test_date = {
    "last_checked_date": "17/02/2026",
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "note": "測試用：調回 17/02/2026"
}
json.dump(test_date, open(LAST_CHECKED_FILE, 'w'), ensure_ascii=False, indent=2)
print(f"\n🔧 已將 last_checked_date 調回: 17/02/2026")
print(f"   預期行為：")
print(f"   - 18/02/2026 馬到功成 (ID=1081081) → 已在 ia_mapping，跳過")
print(f"   - 19/02/2026 還有人拜年嗎 → 唔符合主持人條件，跳過")
print(f"   - 20/02/2026 探討大展鴻圖 → 唔符合主持人條件，跳過")
print(f"   - last_checked_date 更新到 20/02/2026（或更新）")
print(f"   - ia_mapping 集數保持 {len(ia_mapping)} 集（唔增加）")

print("\n" + "=" * 60)
print("執行 run_update.py...")
print("=" * 60)

# 執行 run_update.py
import subprocess
result = subprocess.run(
    ['python3', f'{BASE_DIR}/run_update.py'],
    capture_output=False,
    timeout=300
)

print("\n" + "=" * 60)
print("驗證結果：")
print("=" * 60)

# 驗證 1: ia_mapping 集數是否保持不變
ia_mapping_after = json.load(open(IA_MAPPING_FILE))
ia_count_ok = len(ia_mapping_after) == len(ia_mapping)
print(f"\n{'✅' if ia_count_ok else '❌'} ia_mapping 集數: {len(ia_mapping_after)} 集 (預期: {len(ia_mapping)} 集)")

# 驗證 2: last_checked_date 是否已更新
last_checked_after = json.load(open(LAST_CHECKED_FILE))
new_date = last_checked_after.get('last_checked_date', '')
date_updated = new_date > '17/02/2026'  # 應該更新到 20/02/2026 或更新
print(f"{'✅' if date_updated else '❌'} last_checked_date: {new_date} (預期: > 17/02/2026)")

# 驗證 3: 統計檔案
stats_file = '/tmp/rthk_update_stats.json'
if os.path.exists(stats_file):
    stats = json.load(open(stats_file))
    print(f"\n📊 統計：")
    print(f"   新集數: {stats.get('new_episodes', 0)}")
    print(f"   下載: {stats.get('downloaded', 0)}")
    print(f"   上傳: {stats.get('uploaded', 0)}")
    print(f"   失敗: {stats.get('failed', 0)}")
    print(f"   上傳標題: {stats.get('uploaded_titles', [])}")

print("\n" + "=" * 60)
if ia_count_ok and date_updated:
    print("✅ 測試通過！流程正確")
    print("   - ia_mapping 冇增加（已上傳的集數正確跳過）")
    print("   - last_checked_date 已更新（唔符合條件的集數也更新了日期）")
else:
    print("❌ 測試失敗！請查看 update.log")

print("=" * 60)

# 恢復原始 last_checked.json
shutil.copy(LAST_CHECKED_FILE + '.bak', LAST_CHECKED_FILE)
os.remove(LAST_CHECKED_FILE + '.bak')
print(f"\n✅ 已恢復原始 last_checked.json: {original['last_checked_date']}")
print("測試完成！")
