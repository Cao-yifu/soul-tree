#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""灵树同步中继（可选）· 只存密文，不读内容
用法:
    python relay.py [端口] [数据目录]
默认端口 8787，数据存在 ./lingtree-data/
端点:
    GET  /health                  → {"ok": true}
    POST /api/create {room,pub}   → 创建房间，返回 6 位配对码
    POST /api/join {room,code,pub}→ 凭配对码加入（限两人），返回对方公钥
    GET  /api/peers?room=..       → 房间内参与者公钥列表（配对用）
    POST /api/push {room,items}   → 按 id 去重入库（items 是密文，服务器看不懂）
    GET  /api/pull?room=..&after=<时间戳> → 返回该房间 t > after 的密文条目
服务器丢了没关系——每个人的本地记忆才是原件，随时可以重建。
"""
import json
import os
import random
import string
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get('PORT') or (sys.argv[1] if len(sys.argv) > 1 else 8787))
DATA_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lingtree-data')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'rooms'), exist_ok=True)
LOCK = threading.Lock()
CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # 去掉易混字符 I O 0 1


def safe(room):
    return ''.join(c for c in room if c.isalnum() or c in '-_.')


def room_file(room):
    return os.path.join(DATA_DIR, safe(room) + '.jsonl')


def meta_file(room):
    return os.path.join(DATA_DIR, 'rooms', safe(room) + '.json')


def read_room(room):
    fp = room_file(room)
    if not os.path.exists(fp):
        return {}
    items = {}
    with open(fp, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                it = json.loads(line)
                items[it['id']] = it
            except Exception:
                continue
    return items


def read_meta(room):
    fp = meta_file(room)
    if not os.path.exists(fp):
        return None
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def write_meta(room, meta):
    with open(meta_file(room), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {'ok': True})

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/health':
            self._send(200, {'ok': True})
            return
        qs = {}
        if '?' in self.path:
            for part in self.path.split('?')[1].split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    qs[k] = v
        if path == '/api/pull':
            room = qs.get('room', '')
            after = int(float(qs.get('after', '0') or 0))
            with LOCK:
                items = read_room(room)
            out = sorted([it for it in items.values() if it.get('t', 0) > after], key=lambda x: x.get('t', 0))[-500:]
            self._send(200, {'items': out})
            return
        if path == '/api/peers':
            room = qs.get('room', '')
            with LOCK:
                meta = read_meta(room)
            self._send(200, {'peers': (meta or {}).get('participants', [])})
            return
        self._send(404, {'error': 'not found'})

    def do_POST(self):
        path = self.path.split('?')[0]
        if path == '/api/create':
            n = int(self.headers.get('Content-Length', 0) or 0)
            try:
                data = json.loads(self.rfile.read(n).decode('utf-8'))
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            room = data.get('room', '')
            pub = data.get('pub', '')
            if not room or not pub:
                self._send(400, {'error': 'room 和 pub 必填'})
                return
            with LOCK:
                if read_meta(room):
                    self._send(409, {'error': '房间已存在，直接输入配对码加入'})
                    return
                code = ''.join(random.choices(CODE_CHARS, k=6))
                pid = ''.join(random.choices(string.hexdigits, k=12))
                meta = {'code': code, 'participants': [{'pid': pid, 'pub': pub, 'ts': int(__import__('time').time())}]}
                write_meta(room, meta)
            self._send(200, {'code': code})
            return
        if path == '/api/join':
            n = int(self.headers.get('Content-Length', 0) or 0)
            try:
                data = json.loads(self.rfile.read(n).decode('utf-8'))
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            room = data.get('room', '')
            code = (data.get('code', '') or '').strip().upper()
            pub = data.get('pub', '')
            if not room or not pub:
                self._send(400, {'error': 'room 和 pub 必填'})
                return
            with LOCK:
                meta = read_meta(room)
                if not meta:
                    self._send(404, {'error': '房间不存在，先让对方创建'})
                    return
                if meta.get('code') != code:
                    self._send(403, {'error': '配对码不对'})
                    return
                if len(meta.get('participants', [])) >= 2:
                    self._send(409, {'error': '房间已有两个人'})
                    return
                pid = ''.join(random.choices(string.hexdigits, k=12))
                meta['participants'].append({'pid': pid, 'pub': pub, 'ts': int(__import__('time').time())})
                write_meta(room, meta)
                peers = [p for p in meta['participants'] if p['pub'] != pub]
            self._send(200, {'ok': True, 'pid': pid, 'peers': peers})
            return
        if path == '/api/push':
            n = int(self.headers.get('Content-Length', 0) or 0)
            try:
                data = json.loads(self.rfile.read(n).decode('utf-8'))
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            room = data.get('room', '')
            items = data.get('items', [])
            with LOCK:
                cur = read_room(room)
                new_count = 0
                for it in items:
                    if it.get('id') and it['id'] not in cur:
                        cur[it['id']] = it
                        new_count += 1
                with open(room_file(room), 'w', encoding='utf-8') as f:
                    for it in sorted(cur.values(), key=lambda x: x.get('t', 0)):
                        f.write(json.dumps(it, ensure_ascii=False) + '\n')
            self._send(200, {'ok': True, 'new': new_count})
            return
        self._send(404, {'error': 'not found'})

    def log_message(self, *args):
        pass  # 安静模式


if __name__ == '__main__':
    print('灵树中继已启动: http://0.0.0.0:%d  (数据目录: %s)' % (PORT, DATA_DIR))
    HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
