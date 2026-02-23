#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram 通知模組
每日 podcast 更新完成後發送摘要報告
"""
import requests
import json
import time

TELEGRAM_BOT_TOKEN = '8634320454:AAH6IpV7uN6-y_Gzd731Xm3O1-D76UCdnzQ'
TELEGRAM_CHAT_ID = '220866475'
TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'


def send_telegram(message):
    """發送 Telegram 訊息"""
    try:
        resp = requests.post(TELEGRAM_API, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }, timeout=10)
        return resp.json().get('ok', False)
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")
        return False


def send_daily_report(new_episodes, downloaded, uploaded, failed, errors=None):
    """發送每日更新報告"""
    date_str = time.strftime('%Y-%m-%d')
    time_str = time.strftime('%H:%M')

    status_icon = '✅' if failed == 0 else '⚠️'

    lines = [
        f'🎙️ <b>RTHK 講東講西 Podcast 每日更新報告</b>',
        f'📅 {date_str} {time_str}',
        '',
        f'📋 新集數：<b>{new_episodes}</b> 集',
        f'⬇️ 已下載：<b>{downloaded}</b> 個 MP3',
        f'⬆️ 成功上傳：<b>{uploaded}</b> 集',
    ]

    if failed > 0:
        lines.append(f'❌ 上傳失敗：<b>{failed}</b> 集')

    if errors:
        lines.append('')
        lines.append('⚠️ <b>錯誤記錄：</b>')
        for err in errors[:3]:  # 最多顯示 3 個錯誤
            lines.append(f'  • {err}')

    if uploaded == 0 and new_episodes == 0:
        lines.append('')
        lines.append('💤 今日暫無新集數')
    elif uploaded > 0:
        lines.append('')
        lines.append(f'{status_icon} 今日更新完成！')

    lines.append('')
    lines.append('— Manus 自動通知系統')

    message = '\n'.join(lines)
    return send_telegram(message)


def send_error_alert(error_msg):
    """發送錯誤警報"""
    date_str = time.strftime('%Y-%m-%d %H:%M')
    message = (
        f'🚨 <b>RTHK Podcast 更新出現錯誤</b>\n'
        f'📅 {date_str}\n\n'
        f'❌ 錯誤詳情：\n{error_msg}\n\n'
        f'— Manus 自動通知系統'
    )
    return send_telegram(message)


if __name__ == '__main__':
    # 測試發送
    send_daily_report(
        new_episodes=2,
        downloaded=2,
        uploaded=2,
        failed=0
    )
    print("測試訊息已發送")
