"""Reader for the Lua table literals in addon data files (pfQuest, Atlas-CFM).

Not a Lua interpreter: expressions are reduced to plain values.
- `L["Text"]`, `LS["Text"]` and similar locale lookups become "Text".
- `a .. b` becomes the concatenated text of both sides.
- Other identifiers (`AtlasCFM.Server.TURTLE`) and calls become their source text.
"""
import re

TOKEN = re.compile(r'''
    \s*(?:
        --\[(?P<eq>=*)\[.*?\](?P=eq)\]          # long comment
      | --[^\n]*                                # line comment
      | (?P<str>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')
      | (?P<num>\d+(?:\.\d*)?(?:[eE][-+]?\d+)?|\.\d+)
      | (?P<op>\.\.|==|~=|<=|>=|[{}\[\]=,;()+\-*/%^#<>:])
      | (?P<name>[A-Za-z_][\w.]*)
    )''', re.S | re.X)

ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '"': '"', "'": "'"}


def _unescape(s):
    return re.sub(r'\\(.)', lambda m: ESCAPES.get(m.group(1), m.group(1)), s)


def tokenize(src):
    pos, n = 0, len(src)
    while pos < n:
        m = TOKEN.match(src, pos)
        if not m:
            if not src[pos:].strip():
                break
            raise ValueError('unexpected text at %d: %r' % (pos, src[pos:pos + 60]))
        pos = m.end()
        if m.group('str') is not None:
            yield ('str', _unescape(m.group('str')[1:-1]))
        elif m.group('num') is not None:
            v = m.group('num')
            yield ('num', float(v) if re.search(r'[.eE]', v) else int(v))
        elif m.group('op') is not None:
            yield ('op', m.group('op'))
        elif m.group('name') is not None:
            yield ('name', m.group('name'))
    while True:
        yield ('eof', None)


class Expr(str):
    """Identifier or call kept as source text (e.g. AtlasCFM.Server.TURTLE)."""


class Parser:
    def __init__(self, src):
        self.src = tokenize(src)
        self.buf = []

    def peek(self, o=0):
        while len(self.buf) <= o:
            self.buf.append(next(self.src))
        return self.buf[o]

    def take(self):
        tok = self.peek()
        self.buf.pop(0)
        return tok

    def expect(self, op):
        tok = self.take()
        if tok != ('op', op):
            raise ValueError('expected %r, got %r ' % (op, tok))

    def expr(self):
        left = self.unary()
        while self.peek()[0] == 'op' and self.peek()[1] in ('..', '+', '-', '*', '/', '%', '^', '==', '~=', '<', '>', '<=', '>='):
            op = self.take()[1]
            right = self.unary()
            if op == '..':
                left = '%s%s' % (_text(left), _text(right))
            elif isinstance(left, (int, float)) and isinstance(right, (int, float)) and op in '+-*/':
                left = {'+': left + right, '-': left - right, '*': left * right, '/': left / right if right else 0}[op]
            else:
                left = Expr('%s %s %s' % (left, op, right))
        return left

    def unary(self):
        k, v = self.peek()
        if k == 'op' and v == '-':
            self.take()
            x = self.unary()
            return -x if isinstance(x, (int, float)) else Expr('-%s' % x)
        if k == 'op' and v == '#':
            self.take()
            return Expr('#%s' % self.unary())
        if k == 'name' and v == 'not':
            self.take()
            return Expr('not %s' % self.unary())
        return self.primary()

    def primary(self):
        k, v = self.take()
        if k in ('str', 'num'):
            return v
        if k == 'op' and v == '{':
            return self.table()
        if k == 'op' and v == '(':
            x = self.expr()
            self.expect(')')
            return x
        if k == 'name':
            if v in ('true', 'false', 'nil'):
                return {'true': True, 'false': False, 'nil': None}[v]
            return self.suffix(v)
        raise ValueError('unexpected token %r ' % ((k, v),))

    def suffix(self, name):
        value = Expr(name)
        while True:
            k, v = self.peek()
            if (k, v) == ('op', '['):
                self.take()
                key = self.expr()
                self.expect(']')
                value = key if isinstance(key, str) else Expr('%s[%s]' % (value, key))  # locale lookup -> key text
            elif (k, v) == ('op', '('):
                self.take()
                args = []
                while self.peek() != ('op', ')'):
                    args.append(self.expr())
                    if self.peek() == ('op', ','):
                        self.take()
                self.take()
                value = Expr('%s(%s)' % (value, ', '.join(map(str, args))))
            elif (k, v) == ('op', ':'):
                self.take()
                method = self.take()[1]
                value = self.suffix('%s:%s' % (value, method))
            elif k == 'str':  # f"str" call sugar
                self.take()
                value = Expr('%s(%r)' % (value, v))
            else:
                return value

    def table(self):
        d, n = {}, 1
        while True:
            k, v = self.peek()
            if (k, v) == ('op', '}'):
                self.take()
                return d
            if (k, v) == ('op', '['):
                self.take()
                key = self.expr()
                self.expect(']')
                self.expect('=')
                d[key] = self.expr()
            elif k == 'name' and self.peek(1) == ('op', '=') and '.' not in v:
                self.take()
                self.take()
                d[v] = self.expr()
            else:
                d[n] = self.expr()
                n += 1
            if self.peek() in (('op', ','), ('op', ';')):
                self.take()


def _text(x):
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return '' if x is None else str(x)


def parse_value(src):
    """Parses one expression (usually a table literal) from the start of src."""
    return Parser(src).expr()


def tables_assigned(path, lhs):
    """{lhs text: table} for each unindented `LHS = {` whose LHS matches the regex `lhs`."""
    src = open(path, encoding='utf-8', errors='replace').read()
    out = {}
    for m in re.finditer(r'^(?:local[ \t]+)?(' + lhs + r')[ \t]*=[ \t]*\{', src, re.M):
        out[m.group(1).strip()] = Parser(src[m.end() - 1:]).expr()
    return out


def as_list(t):
    """Array part of a parsed table (keys 1..n) as a Python list; holes become None."""
    if not isinstance(t, dict):
        return []
    n = 0
    while (n + 1) in t:
        n += 1
    return [t[i] for i in range(1, n + 1)]
