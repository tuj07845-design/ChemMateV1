# -*- coding: utf-8 -*-
import ast, os, sys, builtins
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.getcwd()
BUILTINS = set(dir(builtins))

# ---------- 1. collect files ----------
pyfiles = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in ('__pycache__', 'runs', 'reports', 'matlab')]
    for fn in filenames:
        if fn.endswith('.py') and not fn.startswith('py_'):
            pyfiles.append(os.path.join(dirpath, fn))

# ---------- 2. per-file parse ----------
# info[path] = {defined:{name:lineno}, imports:set, impmap:{name:desc}, local:set, uses:{(name,lineno)}}
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
    imports = set()
    impmap = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined[node.name] = node.lineno
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defined[t.id] = node.lineno
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined[node.target.id] = node.lineno
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                nm = a.asname or a.name.split('.')[0]
                imports.add(nm); impmap[nm] = 'import ' + a.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or '.'
            for a in node.names:
                nm = a.asname or a.name
                if nm != '*':
                    imports.add(nm); impmap[nm] = 'from ' + ('(dot).' if not node.module else node.module) + ' import ' + a.name
    local = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in ('__init__',):
            for a in node.args.args: local.add(a.arg)
            if node.args.vararg: local.add(node.args.vararg.arg)
            if node.args.kwarg: local.add(node.args.kwarg.arg)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name,)) and isinstance(node.ctx, ast.Store):
            local.add(node.id)
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            uses.append((node.id, node.lineno))
    info[f] = {'defined': defined, 'imports': imports, 'impmap': impmap, 'local': local, 'uses': uses}

# ---------- 3. package symbol tables (same-directory = same package) ----------
from collections import defaultdict
pkg_syms = defaultdict(dict)  # dir -> {name: [(file, lineno)]}
for f, inf in info.items():
    d = os.path.dirname(f)
    for name, ln in inf['defined'].items():
        pkg_syms[d].setdefault(name, []).append((os.path.basename(f), ln))

# ---------- 4. report: cross-file references missing import ----------
print('=' * 70)
print('REPORT: cross-file symbol used but NOT imported (same package)')
print('=' * 70)
problems = []
for f, inf in sorted(info.items()):
    rel = os.path.relpath(f, ROOT)
    d = os.path.dirname(f)
    others = {k: v for k, v in pkg_syms[d].items() if not any(os.path.samefile(x[0] and os.path.join(d, os.path.basename(f)), f) for x in []) }
    used_names = defaultdict(list)
    for name, ln in inf['uses']:
        if name in BUILTINS: continue
        if name in inf['defined']: continue
        if name in inf['imports']: continue
        if name in inf['local']: continue
        # in-package others' symbols?
        for sym, defs in pkg_syms[d].items():
            if sym == name and not any(os.path.basename(df) == os.path.basename(f) and dl == inf['defined'].get(name) for df, dl in defs):
                # exclude own definition
                for df, dl in defs:
                    if df == os.path.basename(f):
                        continue
                    used_names[name].append((ln, df, dl))
    if used_names:
        print()
        print('FILE:', rel)
        for name, hits in sorted(used_names.items()):
            srcs = sorted(set((df, dl) for _, df, dl in hits))
            for ln, df, dl in sorted(set(hits)):
                msg = '  line %-4d uses %-28s defined in %s:%d  ->  add: from .%s import %s' % (ln, name, df, dl, df[:-3], name)
                print(msg)
                problems.append((rel, ln, name, df, dl))
print()
print('=' * 70)
print('TOTAL potential missing imports:', len(problems))
print('=' * 70)

# ---------- 5. list every file's imports for eyeball ----------
print()
print('ALL FILES & THEIR IMPORTS:')
for f in sorted(info):
    rel = os.path.relpath(f, ROOT)
    imp = sorted(info[f]['impmap'].values())
    print(' ', rel, '=>', ', '.join(imp) if imp else '(no imports)')