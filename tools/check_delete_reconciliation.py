"""删除测试前的 src 指针对账工序工具(R0 防再犯线)。

背景 = 2026-09-13 清理提交 1cc1958b 整目录删除 261 个 CW 测试文件,未做
src 侧反向对账,一次性打悬 ~60 处「行为由测试钉住」类声明(损失盘点 =
主仓 .debug/progress/2026-09-11-cw-clear-run/reports/T-249-r1.md;恢复批
= T-252)。本工具把「删测试先对账 src 指针」固化为可执行工序。

用法(测试仓根或主仓根均可跑):

    uv run python sr-od-test/tools/check_delete_reconciliation.py <路径或文件名>...

    # 例:删目录前
    uv run python sr-od-test/tools/check_delete_reconciliation.py test/sr_od/app/currency_war

    # 例:单个文件
    uv run python sr-od-test/tools/check_delete_reconciliation.py test/sr_od/application/currency_war/test_cw_game_state.py

输出 = 对账清单(stdout):每个将删文件名(去扩展名)与其中测试函数名,
在 src/sr_od 下被多少「test_ 指针」引用、命中位置逐行列出。**退出码
非零 = 存在悬空风险引用**:删除批必须先消费清单(逐条改写声明或随批
摘除 src 注释)再删,并把清单附进删除 commit 说明。

判据说明:src 侧引用形态 = 注释/docstring 里的文件名或 ``test_xxx`` 函数
名(词边界)。工具只做存在性对账(谁会悬空),不做语义判断(该锁是否
仍该存在归删除批的分诊纪律,sr-od-test/README.md「删除测试的工序」节)。
本工具是工序工具,不是 pytest 测试——源码扫描形态的 pytest 测试被
AGENTS §10.4.4 / README 禁止清单禁止,工序工具不受此约束(不进测试网,
只在删除类操作时人工触发)。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

#: 主仓根(脚本位于 sr-od-test/tools/ 下,parents[2] = 仓根)。
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / 'src' / 'sr_od'
_TEST_ROOT = _REPO_ROOT / 'sr-od-test' / 'test'


def _collect_test_names(target: Path) -> tuple[str, set[str]]:
    """将删目标 → (文件词干, 其中定义的测试函数名集)。

    目录 = 递归收全部 test_*.py;文件 = 自身。函数名按缩进无关的
    ``def test_xxx`` 收集(类内方法同算——src 声明常引函数级名字)。
    目标已不存在(对照删除清单复查场景)时函数集为空,词干仍参与对账。
    """
    stem_names: set[str] = {target.stem}
    func_names: set[str] = set()
    files = ([target] if target.is_file()
             else sorted(target.rglob('test_*.py')))
    def_re = re.compile(r'def (test_\w+)\(')
    for f in files:
        stem_names.add(f.stem)
        try:
            text = f.read_text(encoding='utf-8')
        except OSError as e:   # noqa: PERF203  逐文件容错,缺文件报跳过
            print(f'[warn] 不可读,跳过 {f}: {e}', file=sys.stderr)
            continue
        func_names.update(def_re.findall(text))
    return target.stem, func_names


def _scan_src_pointers(needles: set[str]) -> dict[str, list[str]]:
    """在 src/sr_od 全部 .py 中逐 needle 找词边界命中,返回命中行清单。"""
    if not needles:
        return {}
    pattern = re.compile(
        r'\b(' + '|'.join(re.escape(n) for n in sorted(needles)) + r')\b')
    hits: dict[str, list[str]] = {n: [] for n in needles}
    for py in sorted(_SRC_ROOT.rglob('*.py')):
        try:
            lines = py.read_text(encoding='utf-8').splitlines()
        except OSError:
            continue
        rel = py.relative_to(_REPO_ROOT)
        for lineno, line in enumerate(lines, start=1):
            for m in pattern.finditer(line):
                hits[m.group(1)].append(f'{rel}:{lineno}: {line.strip()[:90]}')
    return hits


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    all_names: set[str] = set()
    per_file: list[tuple[str, set[str]]] = []
    for arg in argv:
        target = Path(arg)
        if not target.exists():
            # 允许只给文件名(如 test_cw_xxx.py)——按测试树搜定位
            candidates = list(_TEST_ROOT.rglob(arg))
            if len(candidates) == 1:
                target = candidates[0]
            elif not candidates:
                print(f'[warn] 目标不存在,跳过: {arg}', file=sys.stderr)
                continue
            else:
                print(f'[warn] 文件名命中多处,请给完整相对路径: '
                      f'{[str(c) for c in candidates]}', file=sys.stderr)
                continue
        stem, funcs = _collect_test_names(target)
        per_file.append((stem, funcs))
        all_names.add(stem)
        all_names.update(funcs)
    if not all_names:
        print('没有可对账的目标。')
        return 2
    hits = _scan_src_pointers(all_names)
    total = 0
    print('=== 删除对账清单(src 指针悬空风险)===')
    for stem, funcs in per_file:
        related = ([f'{stem}: 文件名引用 {len(hits.get(stem, []) )} 处']
                   + [f'  {line}' for line in hits.get(stem, [])])
        print('\n'.join(related) if hits.get(stem) else f'{stem}: 无文件名引用')
        total += len(hits.get(stem, []))
        for fn in sorted(funcs):
            fn_hits = hits.get(fn, [])
            total += len(fn_hits)
            if fn_hits:
                print(f'{fn}: 函数名引用 {len(fn_hits)} 处')
                print('\n'.join(f'  {line}' for line in fn_hits))
    print('=== 汇总 ===')
    print(f'悬空风险引用合计 {total} 处。')
    if total:
        print('处置纪律:先消费清单(逐条改写声明出处/随批摘除 src 注释)'
              '再删,并把本清单附进删除 commit 说明。')
        return 1
    print('无 src 指针悬空风险,可删(仍须遵守测试纪律的分诊要求)。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
