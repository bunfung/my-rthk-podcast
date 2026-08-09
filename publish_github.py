#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish generated podcast files to GitHub via Contents API (no git binary required)."""
import base64
import json
import os
import sys
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
except Exception:
    pass

BASE_DIR = Path(os.environ.get('RTHK_PODCAST_DIR', Path(__file__).resolve().parent))
OWNER = os.environ.get('GITHUB_OWNER', 'bunfung')
REPO = os.environ.get('GITHUB_REPO', 'my-rthk-podcast')
BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
TOKEN = os.environ.get('GITHUB_TOKEN')
FILES = ['ia_mapping.json', 'last_checked.json', 'feed.xml', 'run_update.py', 'publish_github.py']


def gh(method, url, **kwargs):
    headers = kwargs.pop('headers', {})
    headers.update({
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'
    r = requests.request(method, url, headers=headers, timeout=60, **kwargs)
    if r.status_code >= 400:
        raise RuntimeError(f'{method} {url} -> {r.status_code}: {r.text[:500]}')
    return r.json() if r.text else {}


def publish_file(name):
    path = BASE_DIR / name
    if not path.exists():
        print(f'skip missing {name}')
        return False
    api = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/{name}'
    sha = None
    try:
        meta = gh('GET', api, params={'ref': BRANCH})
        sha = meta.get('sha')
    except Exception as e:
        print(f'warn: cannot get current sha for {name}: {e}')
    content = base64.b64encode(path.read_bytes()).decode('ascii')
    payload = {
        'message': f'Daily update: {name}',
        'content': content,
        'branch': BRANCH,
    }
    if sha:
        payload['sha'] = sha
    gh('PUT', api, json=payload)
    print(f'published {name}')
    return True


def main():
    if not TOKEN:
        print('GITHUB_TOKEN not set; skip publish')
        return 2
    changed = 0
    for name in FILES:
        changed += bool(publish_file(name))
    print(f'done, published {changed} file(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
