# -*- coding: utf-8 -*-
import ast, os, sys, builtins
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.getcwd()
BUILTINS = set(dir(builtins))
pyfiles = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in ('__pycache__', 'runs', 'reports', 'matlab')]
    absp = os.path.abspath(dirpath)
    if absp.startswith(os.path.join(ROOT, 'ui')):
        dirnames[:] = []
        continue
    for fn in filenames:
        if fn.endswith('.py') and not fn.startswith('py_'):
            pyfiles.append(os.path.join(dirpath, fn))
info = {}
for f in pyfiles:
    with open(f, encoding='utf-8') as fh:
        src = fh.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print('[SYNTAX ERROR]', os.path.relpath(f, ROOT), 'line', e.lineno)
        continue
    defined = {}
    imports = set(); impmap = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined[node.name] = node.lineno
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name): defined[t.id] = node.lineno
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined[node.target.id] = node.lineno
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                nm = a.asname or a.name.split('.')[0]
                imports.add(nm); impmap[nm] = 'import ' + a.name
        elif isinstance(node, ast.ImportFrom):
            prefix = '.' * node.level if node.level else ''
            mod = (prefix + (node.module or '')) or '.'
            for a in node.names:
                nm = a.asname or a.name
                if nm != '*':
                    imports.add(nm); impmap[nm] = 'from ' + mod + ' import ' + a.name
    local = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for a in node.args.args: local.add(a.arg)
            if node.args.vararg: local.add(node.args.vararg.arg)
            if node.args.kwarg: local.add(node.args.kwarg.arg)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            local.add(node.id)
    uses = [(n.id, n.lineno) for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)]
    info[f] = {'defined': defined, 'imports': imports, 'impmap': impmap, 'local': local, 'uses': uses}
from collections import defaultdict
pkg_syms = defaultdict(lambda: defaultdict(list))
for f, inf in info.items():
    d = os.path.dirname(f)
    for name, ln in inf['defined'].items():
        pkg_syms[d][name].append((os.path.basename(f), ln))
print('=' * 72)
print('PART A: same-package symbol used but not imported (NameError risk)')
print('=' * 72)
nfiles = 0
for f, inf in sorted(info.items()):
    rel = os.path.relpath(f, ROOT)
    d = os.path.dirname(f)
    hits = defaultdict(set)
    for name, ln in inf['uses']:
        if name in BUILTINS or name in inf['defined'] or name in inf['imports'] or name in inf['local']:
            continue
        for sym, defs in pkg_syms[d].items():
            if sym == name and any(df != os.path.basename(f) for df, _ in defs):
                for df, dl in defs:
                    if df != os.path.basename(f):
                        hits[name].add((ln, df, dl))
    if hits:
        nfiles += 1
        print('FILE:', rel)
        for name, items in sorted(hits.items()):
            for ln, df, dl in sorted(items):
                print('   line %-5d uses %-22s (defined in %s.py:%d)' % (ln, name, df[:-3], dl))
print('files affected:', nfiles)
print()
print('=' * 72)
print('PART B: per-file import map (dot = same package)')
print('=' * 72)
for f in sorted(info):
    rel = os.path.relpath(f, ROOT)
    own = [v for v in sorted(info[f]['impmap'].values()) if v.startswith('from .')]
    ext = [v for v in sorted(info[f]['impmap'].values()) if not v.startswith('from .')]
    print(rel)
    if own: print('    pkg:', ', '.join(own))
    if ext: print('    ext:', ', '.join(ext))