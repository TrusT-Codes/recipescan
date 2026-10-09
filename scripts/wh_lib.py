# -*- coding: utf-8 -*-
"""Shared helpers for the Wowhead Classic scraper (Python 3).

Pages are cached under scratch/cache (git-ignored) so a stage can be re-run without hitting Wowhead again.
Wowhead's CDN returns a 919 byte 403 page when requests come too fast, so fetches are paced and retried with backoff.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'scratch', 'cache')
DATA = os.path.join(ROOT, 'data')
BASE = 'https://www.wowhead.com/classic/'
BS = chr(92)
os.makedirs(CACHE, exist_ok=True)
_last = [0.0]


def fetch(path, pace=3.0):
    """GET BASE+path (or a full URL). Returns the page text, cached on disk."""
    url = path if path.startswith('http') else BASE + path
    p = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + '.html')
    if os.path.exists(p):
        return open(p, encoding='utf-8').read()
    for attempt in range(1, 9):
        wait = pace - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        r = subprocess.run(['curl', '-s', '-L', '-A', 'Mozilla/5.0', '--max-time', '60', url], capture_output=True)
        body = r.stdout.decode('utf-8', 'replace')
        if len(body) > 5000:
            open(p, 'w', encoding='utf-8').write(body)
            return body
        print('retry', url, attempt, len(body), file=sys.stderr, flush=True)
        time.sleep(20 * attempt)
    raise Exception('failed ' + url)


def _match_close(h, j, open_ch, close_ch):
    d = 0
    instr = False
    esc = False
    for p in range(j, len(h)):
        c = h[p]
        if instr:
            if esc:
                esc = False
            elif c == BS:
                esc = True
            elif c == '"':
                instr = False
            continue
        if c == '"':
            instr = True
        elif c == open_ch:
            d += 1
        elif c == close_ch:
            d -= 1
            if d == 0:
                return p
    return None


def loads(s):
    # Wowhead leaves a few keys unquoted (quality, popularity, ...)
    s = re.sub(r'([,{])([A-Za-z_]\w*):', r'\1"\2":', s)
    return json.loads(s)


def listview(h, id_):
    """Data array of the page Listview with this id, or None."""
    i = h.find("id: '%s'," % id_)
    if i < 0:
        return None
    m = re.compile(r"data: ?\[").search(h, i)
    if not m:
        return None
    j = m.end() - 1
    return loads(h[j:_match_close(h, j, '[', ']') + 1])


def var_array(h, name):
    i = h.find(name)
    if i < 0:
        return None
    j = h.find('[', i)
    return loads(h[j:_match_close(h, j, '[', ']') + 1])


def read_lines(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return []
    return [l for l in open(p, encoding='utf-8').read().splitlines() if l and not l.startswith('#')]
