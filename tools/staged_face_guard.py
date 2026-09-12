"""staged_face_guard —— 暂存面手术护栏(staged 非路径行=0 断言的通用化)。

手法先例 = 剥离微批的一次性三层断言脚本(.debug/temp/t25_r2_phase_e.py,
易失产物;本工具为其通用化常驻形态):对「索引层手术」(只动路径改写/
泄漏剥离,禁携内容变更入库)的暂存区做机械验收——

1. **层1 暂存集对账**:`git diff --cached --name-only` 全集 == 预期文件集
   (对称差逐个点名);
2. **层2 路径改写纯度**:声明了 ``--path-rewrite 文件:FROM=TO`` 的文件,
   其 staged diff 的 −/+= 行必须 1:1 配对,且每条 − 行经「FROM→TO」替换后
   与对应 + 行逐字节相等(申报方向 = 暂存变更实际替换方向;剥离/回退
   手术场景 = 新路径→旧路径;非路径内容变更 = 红并点名行);
3. **层3 泄漏符号禁入**:声明了 ``--forbid-symbol 文件:符号`` 的文件,
   其 staged 全文不得含该符号(剥离目标残留 = 红)。

用法(仓库根执行)::

    uv run python sr-od-test/tools/staged_face_guard.py \
        --expect-file docs/game/a.md --expect-file src/x.py \
        --path-rewrite "docs/game/a.md:docs/develop/sr_od=docs/develop" \
        --forbid-symbol "src/x.py:leaked_symbol"

(层2 示例申报方向 = 回退手术:− 行含新路径 ``docs/develop/sr_od/…``,
+ 行含旧路径 ``docs/develop/…``;正向改写场景按实际方向申报 FROM=旧/TO=新。)

全过退出码 0;任何一层破缺打印逐条违例并以退出码 1 退出。输出为人类
可读清单;加 ``--json`` 追加机器可读摘要(结构同层1-3)。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def _git(*args: str) -> str:
    r = subprocess.run(['git'] + list(args), capture_output=True)
    if r.returncode != 0:
        raise SystemExit(
            f'git {" ".join(args)} 失败: {r.stderr.decode("utf-8", "replace")[:300]}')
    return r.stdout.decode('utf-8', 'replace')


def check(expect_files: list[str], rewrites: dict[str, list[tuple[str, str]]],
          forbids: dict[str, list[str]]) -> tuple[list[str], dict]:
    """跑三层断言,返回 (违例清单, 摘要 dict)。"""
    violations: list[str] = []
    staged_raw = [x for x in _git('diff', '--cached', '--name-only').splitlines()
                  if x.strip()]
    staged = {x.replace('"', '') for x in staged_raw}
    expected = set(expect_files)

    # —— 层1:暂存集 == 预期集 ——
    if staged != expected:
        violations.append(
            f'层1 暂存集对账破缺:仅暂存有={sorted(staged - expected)} '
            f'仅预期有={sorted(expected - staged)}')

    # —— 层2:路径改写纯度(−/+ 1:1 配对,−行经替换逐字节等于 +行)——
    rewrite_report: dict[str, int] = {}
    for rel, pairs in rewrites.items():
        d = _git('diff', '--cached', '--', rel)
        minus = [ln[1:] for ln in d.splitlines()
                 if ln.startswith('-') and not ln.startswith('---')]
        plus = [ln[1:] for ln in d.splitlines()
                if ln.startswith('+') and not ln.startswith('+++')]
        if len(minus) != len(plus):
            violations.append(
                f'层2 {rel}: −/+= 行数不等({len(minus)} vs {len(plus)})'
                '——存在净增/净删行,非纯路径改写')
            continue
        for i, (m, p) in enumerate(zip(minus, plus, strict=True)):
            mapped = m
            for frm, to in pairs:
                mapped = mapped.replace(frm, to)
            if mapped != p:
                violations.append(
                    f'层2 {rel}: 第 {i + 1} 对变更行非纯路径替换:'
                    f'- {m[:90]!r} + {p[:90]!r}')
        rewrite_report[rel] = len(minus)

    # —— 层3:泄漏符号禁入(staged 全文)——
    forbid_report: dict[str, list[str]] = {}
    for rel, symbols in forbids.items():
        try:
            content = _git('show', f':{rel}')
        except SystemExit as e:
            violations.append(f'层3 {rel}: staged 内容不可读:{e}')
            continue
        hits = [s for s in symbols if s in content]
        if hits:
            violations.append(
                f'层3 {rel}: 剥离目标符号仍残留 staged 内容:{hits}')
        forbid_report[rel] = hits

    summary = {
        'staged_files': sorted(staged),
        'path_rewrite_lines': rewrite_report,
        'forbidden_symbol_hits': forbid_report,
        'violations': violations,
        'verdict': 'PASS' if not violations else 'FAIL',
    }
    return violations, summary


def main() -> int:
    ap = argparse.ArgumentParser(
        description='暂存面手术护栏(staged 非路径行=0 三层断言)')
    ap.add_argument('--expect-file', action='append', default=[],
                    metavar='REL', help='预期暂存文件(可重复;全集须恰等)')
    ap.add_argument('--path-rewrite', action='append', default=[],
                    metavar='REL:FROM=TO',
                    help='路径改写声明(可重复;FROM→TO = 暂存变更的替换'
                         '方向,剥离/回退场景 = 新路径=FROM 旧路径=TO)')
    ap.add_argument('--forbid-symbol', action='append', default=[],
                    metavar='REL:SYMBOL',
                    help='staged 全文禁入符号(可重复)')
    ap.add_argument('--json', action='store_true', help='追加机器可读 JSON 摘要')
    args = ap.parse_args()

    rewrites: dict[str, list[tuple[str, str]]] = {}
    for spec in args.path_rewrite:
        rel, _, pair = spec.partition(':')
        frm, _, to = pair.partition('=')
        if not rel or not frm or not to:
            raise SystemExit(f'--path-rewrite 格式应为 REL:FROM=TO,得 {spec!r}')
        rewrites.setdefault(rel, []).append((frm, to))
    forbids: dict[str, list[str]] = {}
    for spec in args.forbid_symbol:
        rel, _, sym = spec.partition(':')
        if not rel or not sym:
            raise SystemExit(f'--forbid-symbol 格式应为 REL:SYMBOL,得 {spec!r}')
        forbids.setdefault(rel, []).append(sym)

    violations, summary = check(args.expect_file, rewrites, forbids)
    for v in violations:
        print(f'[staged_face_guard] {v}')
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"staged_face_guard: {summary['verdict']} "
          f"(staged={len(summary['staged_files'])} 文件)")
    return 0 if not violations else 1


if __name__ == '__main__':
    sys.exit(main())
