"""Diff-friendly JSON: one top-level section per block, one entity per line."""
import json
import os


def _dump(v):
    return json.dumps(v, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def _key(k):
    return (0, int(k), '') if isinstance(k, int) or (isinstance(k, str) and k.lstrip('-').isdigit()) else (1, 0, str(k))


def write_sections(path, sections):
    """sections: {name: dict or list or scalar}. Dict/list sections are written one entry per line."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = ['{']
    names = list(sections)
    for si, name in enumerate(names):
        val = sections[name]
        tail = ',' if si < len(names) - 1 else ''
        if isinstance(val, dict) and val:
            out.append('%s:{' % _dump(name))
            keys = sorted(val, key=_key)
            for i, k in enumerate(keys):
                out.append('%s:%s%s' % (_dump(str(k)), _dump(val[k]), ',' if i < len(keys) - 1 else ''))
            out.append('}' + tail)
        elif isinstance(val, list) and val:
            out.append('%s:[' % _dump(name))
            for i, x in enumerate(val):
                out.append('%s%s' % (_dump(x), ',' if i < len(val) - 1 else ''))
            out.append(']' + tail)
        else:
            out.append('%s:%s%s' % (_dump(name), _dump(val), tail))
    out.append('}')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out) + '\n')


def read(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def int_keys(d):
    """JSON object keys are strings; turn numeric ones back into ints."""
    return {(int(k) if k.lstrip('-').isdigit() else k): v for k, v in d.items()}
