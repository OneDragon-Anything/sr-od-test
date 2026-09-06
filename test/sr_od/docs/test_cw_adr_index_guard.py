"""ADR 编号守卫:docs/develop/currency_war/decisions/ 的 INDEX 与文件一致性。

动机(2026-08-26 两起撞号事故):
- W132/W138 两批同用 0353:两文件并存、INDEX 两行撞号,后手工重编号(commit f30f408a);
- W139 起草 0355 时不知 W140 也要用(最终 W139 让到 0356 才没撞)。

并行 worker 各自「查 INDEX 尾号续编」在并行期天然竞态,而 INDEX 与文件名之间
原本没有任何校验。本守卫从主仓工作树读真文件(不复制数据),断言:
1. INDEX.md 表格行编号列无重复;
2. INDEX 每行链接的文件在 decisions/ 真实存在;
3. INDEX 行编号 == 链接文件名前缀编号;
4. decisions/ 里 dd 系与 0N 系 ADR 文件均无孤儿(都在 INDEX 有行);
5. 文件首行标题编号与文件名前缀一致。

INDEX 表格行首列有两类合法链接形态,守卫同等解析:
- 短式:`| [dd-NNN](dd-NNN-slug.md) | 标题 |`(链接文本=编号,dd 系历史形态);
- 文件名式:`| [dd-NNN-slug.md](…) |` / `| [NNNN-slug.md](…) |` / `| [ADR-NNNN-slug.md](…)`
  (链接文本=完整文件名,dd 系与 0N 系现行主流形态)。
首列是 ADR 形态链接却两类都不匹配的行,单行判格式漂移(防新形态静默漏检)。
"""
from __future__ import annotations

import re
from pathlib import Path

# 主仓定位:本文件 = <主仓>/sr-od-test/test/sr_od/docs/test_cw_adr_index_guard.py
# parents[4] 即主仓根(sr-od-test 是主仓根下被 gitignore 的独立测试仓)。
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DECISIONS_DIR = _REPO_ROOT / 'docs' / 'develop' / 'currency_war' / 'decisions'
_INDEX_FILE = _DECISIONS_DIR / 'INDEX.md'

# INDEX 表格行形态:首列为 markdown 链接 `| [label](href.md) | 标题 |`,
# label 与 href 的合法性由 _parse_index_row 按两类形态细分。
_INDEX_ROW_RE = re.compile(r'^\|\s*\[([^\]]+)\]\(([^)]+\.md)\)\s*\|')
# 短式链接文本=编号本身(全匹配,避免误吃 dd-NNN-slug.md 文件名式)。
_SHORT_LABEL_RE = re.compile(r'dd-\d{3}')
# 文件名前缀编号:dd 系 `dd-NNN`;0N 系 `NNNN` 或 `ADR-NNNN`(ADR-0529 即此形态)。
# `(?=-)` 要求编号后必须跟 `-`,防止把无 slug 的裸编号当地址前缀。
_FILE_NUM_RE = re.compile(r'^(dd-\d{3}|ADR-\d{4}|\d{4})(?=-)')
# 粗判「这个链接文本长得像 ADR 编号」:用于把形态不合法的 ADR 行判红,
# 而不误伤 INDEX 里可能存在的非 ADR 链接行。
_ADR_LABEL_HINT_RE = re.compile(r'dd-\d{3}|\d{4}')
# decisions/ 里 dd 系 ADR 文件名。
_ADR_FILE_RE = re.compile(r'^dd-\d{3}-.+\.md$')
# decisions/ 里 0N 系 ADR 文件名:`NNNN-slug.md` 与 `ADR-NNNN-slug.md`(ADR-0527/0528 即后者)。
_ON_ADR_FILE_RE = re.compile(r'^(?:ADR-)?\d{4}-.+\.md$')
# 文件首行标题形态(实测多种并存):`# 0333 - ...` / `# ADR 0097 ...` / `# ADR-0114:...` /
# `# DD-001 ...`;捕获组取编号(可带 DD- 前缀),比较时取数字尾对齐命名空间。
_TITLE_RE = re.compile(r'^#\s*(?:ADR[-\s:]*)?((?:DD-)?\d{3,4})\b', re.IGNORECASE)
_NUM_TAIL_RE = re.compile(r'(\d{3,4})$')

# 历史豁免已清(2026-08-26 主仓勘误后删除):0309/0310 撞号与孤儿已修
# (0310 载体批正名+0309-board 补 INDEX 行,主仓 commit 见 git log),守卫全面接管。


def _parse_index_row(label: str, href: str) -> tuple[str, str] | None:
    """把 INDEX 行首列链接解析为 (编号, 文件名);两类合法形态都不匹配时返回 None。

    - 短式:label 即编号(`dd-NNN`),文件名取 href;
    - 文件名式:label 是完整文件名,编号取文件名前缀,文件名仍取 href
      (label 与 href 不一致时由「行编号 == 文件名前缀」检查暴露)。
    """
    if _SHORT_LABEL_RE.fullmatch(label):
        return label, href
    m = _FILE_NUM_RE.match(label)
    if m is not None and label.endswith('.md'):
        return m.group(1), href
    return None


def _num_tail(num: str) -> str:
    """取编号的数字尾:dd-001→001 / ADR-0529→0529 / 0033→0033。

    标题捕获组不带命名空间前缀(如 `# ADR-0529` 捕获 0529),与文件名前缀
    (ADR-0529)比较时须剥前缀,只对数字位。
    """
    m = _NUM_TAIL_RE.search(num)
    return m.group(1) if m else num


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
        label, href = m.group(1), m.group(2)
        parsed = _parse_index_row(label, href)
        if parsed is None:
            # 首列像 ADR 编号却两类合法形态都不匹配:单行判格式漂移。
            # 不判红的代价是漏检——该行不进编号/存在/孤儿任何校验。
            if _ADR_LABEL_HINT_RE.search(label):
                problems.append(f'INDEX 行链接形态不合法(既非 [dd-NNN] 短式也非文件名式): {label} -> {href}')
            continue
        num, filename = parsed
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
        # 3. 行编号 == 文件名前缀编号(短式行有实义;文件名式行两值同源,退化为恒真自检)
        if not filename.startswith(f'{num}-'):
            problems.append(f'INDEX 行编号 {num} 与文件名前缀不一致: {filename}')
        # 5. 标题自洽
        lines = path.read_text(encoding='utf-8').splitlines()
        first_line = lines[0] if lines else ''
        tm = _TITLE_RE.match(first_line)
        if tm is None:
            problems.append(f'首行不是 `# NNNN` 标题形态: {filename} -> {first_line!r}')
        elif _num_tail(tm.group(1)) != _num_tail(num):
            problems.append(f'标题编号 {tm.group(1)} 与文件名前缀 {num} 不一致: {filename}')

    # 4. 两系均无孤儿:目录内 dd-NNN-*.md 与 (ADR-)NNNN-*.md 都在 INDEX
    #    (排除 INDEX.md 等非 ADR 命名)。
    for path in sorted(decisions_dir.iterdir()):
        if not (_ADR_FILE_RE.match(path.name) or _ON_ADR_FILE_RE.match(path.name)):
            continue
        if not path.is_file():
            continue
        if path.name not in linked_files:
            problems.append(f'孤儿 ADR 文件(不在 INDEX): {path.name}')

    if not seen_nums:
        problems.append('INDEX 未解析到任何表格行(格式漂移或文件损坏)')

    return problems


def test_adr_index_and_files_consistent() -> None:
    """真文件守卫:当前 INDEX(0N 系/dd 系文件名式行+历史短式)应全过,撞号/孤儿/断链/形态漂移都会红。"""
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


def test_mutation_filename_form_parsed_and_cross_form_dup(tmp_path: Path) -> None:
    """文件名式行必须被解析(格式漂移回归锁);与短式行混排时编号归一判撞号。"""
    _write_adr(tmp_path, 'dd-003')
    index = (
        '| 编号 | 标题 |\n'
        '|------|------|\n'
        '| [dd-003-fake-slug.md](dd-003-fake-slug.md) | a |\n'
    )
    problems = _collect_violations(index, tmp_path)
    assert not problems, problems

    dup = (
        '| 编号 | 标题 |\n'
        '|------|------|\n'
        '| [dd-003-fake-slug.md](dd-003-fake-slug.md) | a |\n'
        '| [dd-003](dd-003-fake-slug.md) | b |\n'
    )
    problems = _collect_violations(dup, tmp_path)
    assert any('撞号' in p for p in problems), problems


def test_mutation_0n_series_filename_rows(tmp_path: Path) -> None:
    """0N 系文件名式行(NNNN-/ADR-NNNN- 前缀)同等解析:干净行全过,断链行红。"""
    (tmp_path / '0571-fake.md').write_text('# 0571 - 变异自测条目\n\n正文\n', encoding='utf-8')
    index = (
        '| 编号 | 标题 |\n'
        '|------|------|\n'
        '| [0571-fake.md](0571-fake.md) | a |\n'
        '| [ADR-0572-missing.md](ADR-0572-missing.md) | b |\n'
    )
    problems = _collect_violations(index, tmp_path)
    assert not any('未解析' in p for p in problems), problems
    assert any('不存在' in p and 'ADR-0572-missing.md' in p for p in problems), problems


def test_mutation_illegal_link_label_flagged(tmp_path: Path) -> None:
    """首列 ADR 形态链接两类合法形态都不匹配 → 单行格式漂移红(防新形态静默漏检)。"""
    _write_adr(tmp_path, 'dd-003')
    index = (
        '| 编号 | 标题 |\n'
        '|------|------|\n'
        '| [dd-003-fake-slug](dd-003-fake-slug.md) | a |\n'
    )
    problems = _collect_violations(index, tmp_path)
    assert any('链接形态不合法' in p for p in problems), problems


def test_mutation_0n_series_orphan(tmp_path: Path) -> None:
    """0N 系孤儿(NNNN-/ADR-NNNN- 前缀文件不进 INDEX)必须被检出。"""
    (tmp_path / '0572-fake.md').write_text('# 0572 - 变异自测条目\n\n正文\n', encoding='utf-8')
    (tmp_path / 'ADR-0573-fake.md').write_text('# ADR-0573 - 变异自测条目\n\n正文\n', encoding='utf-8')
    index = (
        '| 编号 | 标题 |\n'
        '|------|------|\n'
    )
    problems = _collect_violations(index, tmp_path)
    assert any('孤儿' in p and '0572-fake.md' in p for p in problems), problems
    assert any('孤儿' in p and 'ADR-0573-fake.md' in p for p in problems), problems
