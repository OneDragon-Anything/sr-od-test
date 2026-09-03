"""ADR 编号守卫:docs/develop/currency_war/decisions/ 的 INDEX 与文件一致性。

动机(2026-08-26 两起撞号事故):
- W132/W138 两批同用 0353:两文件并存、INDEX 两行撞号,后手工重编号(commit f30f408a);
- W139 起草 0355 时不知 W140 也要用(最终 W139 让到 0356 才没撞)。

并行 worker 各自「查 INDEX 尾号续编」在并行期天然竞态,而 INDEX 与文件名之间
原本没有任何校验。本守卫从主仓工作树读真文件(不复制数据),断言:
1. INDEX.md 表格行编号列无重复;
2. INDEX 每行链接的文件在 decisions/ 真实存在;
3. INDEX 行编号 == 链接文件名前缀编号;
4. decisions/ 里 NNNN-*.md 无孤儿(都在 INDEX 有行);
5. 文件首行标题编号与文件名前缀一致。
"""
from __future__ import annotations

import re
from pathlib import Path

# 主仓定位:本文件 = <主仓>/sr-od-test/test/sr_od/docs/test_cw_adr_index_guard.py
# parents[4] 即主仓根(sr-od-test 是主仓根下被 gitignore 的独立测试仓)。
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DECISIONS_DIR = _REPO_ROOT / 'docs' / 'develop' / 'currency_war' / 'decisions'
_INDEX_FILE = _DECISIONS_DIR / 'INDEX.md'

# INDEX 表格行形态:`| [NNNN](NNNN-slug.md) | 标题 | ...`
_INDEX_ROW_RE = re.compile(r'^\|\s*\[(dd-\d{3})\]\(([^)]+\.md)\)\s*\|')
_ADR_FILE_RE = re.compile(r'^(dd-\d{3})-.+\.md$')
# ADR 文件首行标题形态(实测多种并存):`# 0333 - ...` / `# ADR 0097 ...` / `# ADR-0114:...`
_TITLE_RE = re.compile(r'^#\s*(?:ADR[-\s:]*)?(DD-\d{3})\b', re.IGNORECASE)

# 历史豁免已清(2026-08-26 主仓勘误后删除):0309/0310 撞号与孤儿已修
# (0310 载体批正名+0309-board 补 INDEX 行,主仓 commit 见 git log),守卫全面接管。


def _collect_violations(index_text: str, decisions_dir: Path) -> list[str]:
    """对一份 INDEX 文本 + decisions 目录跑全部守卫,返回违规描述列表(空=通过)。

    独立成纯函数:真文件测试与变异自测(tmp_path 假场景)共用同一判定逻辑。
    """
    problems: list[str] = []

    seen_nums: dict[str, int] = {}
    linked_files: dict[str, str] = {}  # 文件名 -> 编号
    for line in index_text.splitlines():
        m = _INDEX_ROW_RE.match(line)
        if not m:
            continue
        num, filename = m.group(1), m.group(2)
        seen_nums[num] = seen_nums.get(num, 0) + 1
        linked_files.setdefault(filename, num)

    # 1. 编号唯一
    for num, count in seen_nums.items():
        if count > 1:
            problems.append(f'INDEX 编号 {num} 出现 {count} 行(撞号)')

    for filename, num in linked_files.items():
        path = decisions_dir / filename
        # 2. 链接文件存在
        if not path.is_file():
            problems.append(f'INDEX 链接的文件不存在: {filename}')
            continue
        # 3. 行编号 == 文件名前缀编号
        file_num = filename[:6]
        if num != file_num:
            problems.append(f'INDEX 行编号 {num} 与文件名前缀 {file_num} 不一致: {filename}')
        # 5. 标题自洽
        first_line = path.read_text(encoding='utf-8').splitlines()[0]
        tm = _TITLE_RE.match(first_line)
        if tm is None:
            problems.append(f'首行不是 `# NNNN` 标题形态: {filename} -> {first_line!r}')
        elif tm.group(1).lower() != file_num.lower():
            problems.append(f'标题编号 {tm.group(1)} 与文件名前缀 {file_num} 不一致: {filename}')

    # 4. 无孤儿:目录内 NNNN-*.md 都在 INDEX(排除 INDEX.md 等非 ADR 命名)
    for path in sorted(decisions_dir.iterdir()):
        am = _ADR_FILE_RE.match(path.name)
        if not am or not path.is_file():
            continue
        if path.name not in linked_files:
            problems.append(f'孤儿 ADR 文件(不在 INDEX): {path.name}')

    if not seen_nums:
        problems.append('INDEX 未解析到任何表格行(格式漂移或文件损坏)')

    return problems


def test_adr_index_and_files_consistent() -> None:
    """真文件守卫:当前 INDEX(0350-0356 …)应全过,任何撞号/孤儿/断链都会红。"""
    assert _INDEX_FILE.is_file(), f'INDEX 不存在: {_INDEX_FILE}'
    problems = _collect_violations(_INDEX_FILE.read_text(encoding='utf-8'), _DECISIONS_DIR)
    assert not problems, 'ADR 编号守卫违规:\n' + '\n'.join(problems)


# —— 变异自测:tmp_path 假场景,确认各断言真能红(不碰真文件)——


def _write_adr(d: Path, num: str, title_num: str | None = None) -> None:
    head = f'# {title_num if title_num is not None else num} - 变异自测条目'
    (d / f'{num}-fake-slug.md').write_text(head + '\n\n正文\n', encoding='utf-8')


def test_mutation_duplicate_number_detected(tmp_path: Path) -> None:
    """两行同号(复刻 0353 事故形态)必须被检出。"""
    _write_adr(tmp_path, 'dd-003')
    index = (
        '| 编号 | 标题 | Status | 日期 | 一句话 |\n'
        '|------|------|--------|------|--------|\n'
        '| [dd-003](dd-003-fake-slug.md) | a | accepted | 2026-08-26 | x |\n'
        '| [dd-003](dd-003-fake-slug.md) | b | accepted | 2026-08-26 | x |\n'
    )
    problems = _collect_violations(index, tmp_path)
    assert any('撞号' in p for p in problems), problems


def test_mutation_missing_file_and_prefix_mismatch(tmp_path: Path) -> None:
    """断链 + 行编号/文件名前缀不一致必须被检出。"""
    _write_adr(tmp_path, 'dd-005')
    index = (
        '| 编号 | 标题 |\n'
        '|------|------|\n'
        '| [dd-004](dd-004-not-exist.md) | a |\n'
        '| [dd-006](dd-005-fake-slug.md) | b |\n'
    )
    problems = _collect_violations(index, tmp_path)
    assert any('不存在' in p for p in problems), problems
    assert any('dd-006' in p and 'dd-005' in p and '不一致' in p for p in problems), problems


def test_mutation_orphan_and_title_mismatch(tmp_path: Path) -> None:
    """孤儿文件 + 标题编号错位必须被检出。"""
    _write_adr(tmp_path, 'dd-006', title_num='DD-099')  # 标题编号错位
    _write_adr(tmp_path, 'dd-007')  # 不进 INDEX 的孤儿
    index = (
        '| 编号 | 标题 |\n'
        '|------|------|\n'
        '| [dd-006](dd-006-fake-slug.md) | a |\n'
    )
    problems = _collect_violations(index, tmp_path)
    assert any('孤儿' in p and 'dd-007' in p for p in problems), problems
    assert any('标题编号 DD-099' in p for p in problems), problems
