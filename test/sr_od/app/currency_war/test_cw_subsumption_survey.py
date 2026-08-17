"""cw_subsumption_survey(49 号 J0 子承普查)测试:护栏 + 命中语义。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_subsumption_survey import (  # noqa: E402
    _module_facts,
    overlap_pair,
    survey,
)

_PKG = _REPO / 'src' / 'sr_od' / 'application' / 'currency_war'


def test_survey_ci_guard_no_dup_source() -> None:
    """CI 护栏:全包普查零同值异名关键常量(HP_LOSS 双源已于 ADR-0183 统一后消除)。

    命中 = 新引入双源(同值异名常量对),fail 并报对名 —— 单一源纪律的机器守卫。
    """
    out = survey(_PKG, top_k=50)
    dups = [p for p in out if p['same_value_diff_name']]
    assert not dups, f"发现同值异名常量对(双源): {[(p['pair'], p['same_value_diff_name']) for p in dups]}"


def test_overlap_detects_dup_constant(tmp_path: Path) -> None:
    """命中语义:两模块各持同值异名非平凡常量 → 提名(写临时文件验证工具本身)。"""
    fa = tmp_path / 'cw_aaa_probe.py'
    fb = tmp_path / 'cw_bbb_probe.py'
    fa.write_text('X_TABLE: dict[int, float] = {1: 14.0, 2: 7.0}\n', encoding='utf-8')
    fb.write_text('Y_PRIOR: dict[int, float] = {1: 14.0, 2: 7.0}\n', encoding='utf-8')
    facts_a = _module_facts(fa)
    facts_b = _module_facts(fb)
    ov = overlap_pair(facts_a, facts_b)
    assert ('X_TABLE', 'Y_PRIOR') in ov['same_value_diff_name']
    assert ov['score'] >= 3


def test_overlap_ignores_trivial_and_empty(tmp_path: Path) -> None:
    """短标量巧合与空容器占位不算结构重叠。"""
    fa = tmp_path / 'cw_ccc_probe.py'
    fb = tmp_path / 'cw_ddd_probe.py'
    fa.write_text('A_W = 2.0\nB_TABLE: dict = {}\n', encoding='utf-8')
    fb.write_text('C_BONUS = 2.0\nD_CACHE: dict = {}\n', encoding='utf-8')
    ov = overlap_pair(_module_facts(fa), _module_facts(fb))
    assert ov['same_value_diff_name'] == []
    assert ov['score'] == 0
