"""CwWorkFrame 正名退役零命中哨兵(sim 推演内核正名收编批新增)。

正名语义:旧名 ``CwWorkFrame`` 随推演内核正式类型 ``CwSimFrame``
(kernel/cw_vocab.py)正名收编退役删除,不留别名/子类/兼容壳——名字死亡
即死,防双名长尾。本哨兵锁定退役完成态。

扫描域 = 主仓 ``src/`` 全部 .py + 本测试仓全部 .py(不含 docs:正本文档
的名称现态由 fields.md §9 承载,哨兵含 docs 会与迭代设计件的历史记述
冲突,故不入域)。配对定位:``Path(__file__).parents[4]`` = 本测试仓根,
``parents[5]`` = 与本测试仓同根的主仓(主工作区与 worktree 两种布局
同构成立)。
"""
from __future__ import annotations

from pathlib import Path

_TEST_REPO_ROOT = Path(__file__).parents[4]
_MAIN_REPO_ROOT = Path(__file__).parents[5]
_RETIRED_NAME = 'CwWorkFrame'


def _scan_py_files(roots: list[Path]) -> list[Path]:
    """收集扫描域全部 .py(跳过 __pycache__/.venv 等派生目录)。"""
    files: list[Path] = []
    for root in roots:
        files.extend(sorted(root.rglob('*.py')))
    return [p for p in files
            if '__pycache__' not in p.parts and '.venv' not in p.parts]


def test_cw_work_frame_zero_hit_in_src_and_test_repo() -> None:
    """退役名全仓零命中(src + 测试仓,.py 文本级扫描,含注释/
    docstring/字符串——与 grep 同口径)。

    本测试文件自身为唯一豁免(哨兵必须写出被扫名字才能判;除此之外
    测试仓任何文件复现该名 = 红)。"""
    files = _scan_py_files([_MAIN_REPO_ROOT / 'src', _TEST_REPO_ROOT])
    assert len(files) > 150, f'扫描文件数异常({len(files)}),根可能错位'
    self_path = Path(__file__).resolve()
    offenders = [str(p) for p in files
                 if p.resolve() != self_path
                 and _RETIRED_NAME in p.read_text(encoding='utf-8',
                                                  errors='replace')]
    assert not offenders, (
        f'退役名 {_RETIRED_NAME} 复潮(正名收编后应零命中,'
        f'禁别名/兼容壳):{offenders[:10]}')


def test_sentinel_mutation_self_check() -> None:
    """变异自检:判据对植入样本必须命中、对新名不误报(防扫描逻辑
    失准仍绿)。"""
    assert _RETIRED_NAME in 'class CwWorkFrame:\n    pass\n'
    assert _RETIRED_NAME not in 'class CwSimFrame:\n    pass\n'
