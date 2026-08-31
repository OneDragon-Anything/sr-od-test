"""锁测试:货币战争 P1 节点序列校验器(cw_node_validate,W27)。

双向锁:
- 正常局全过(众数模板行 + 变异槽偏离 + 特殊环境证据豁免 + 对照表真值);
- 构造脏行被捕获(固定槽偏离 / 越界轮 / 缺字段 / P2 接口拒绝);
- 语料实锤回归:重启接管伪行(r1 普通战斗 / r1 遭遇)必须被抓——
  这正是校验器的建器动机(run_20260823_151050/151913 定因,见
  .debug/temp/currency_war/cw_dev/deep_read/W27_报告.md)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""

import pytest

from sr_od.application.currency_war.tools.cw_node_validate import (
    P1_NODE_TEMPLATE,
    validate_p1_node_sequence,
    validate_p2_node_sequence,
)


def _row(rn: int, nt: str, **kw) -> dict:
    d = {'run_id': 'run_test', 'round_num': rn, 'node_type': nt}
    d.update(kw)
    return d


def test_normal_full_run_passes() -> None:
    """正常局(众数模板,缺 r5 已知系统性缺失)全过、零脏行。"""
    rounds_present = [1, 2, 3, 4, 6, 7, 8, 9]   # r5 补给缺行是已知缺陷②,不在场不判
    rows = [_row(r, P1_NODE_TEMPLATE[r - 1]) for r in rounds_present]
    assert validate_p1_node_sequence(rows) == []


def test_variant_slot_deviation_downgraded() -> None:
    """变异槽(slot3/5/6 → r4/r6/r7)偏离标 variant_slot(非 template_mismatch)。"""
    dirty = validate_p1_node_sequence([
        _row(6, '遭遇'),    # r6 众数=普通战斗,slot5=变异位
    ])
    assert len(dirty) == 1
    assert dirty[0]['reason'] == 'variant_slot'
    assert dirty[0]['expected'] == '普通战斗'


def test_fixed_slot_mismatch_flagged() -> None:
    """固定槽偏离(如接管伪行 r1=普通战斗)标 template_mismatch。"""
    dirty = validate_p1_node_sequence([
        _row(1, '普通战斗'), _row(2, '奖励'),
    ])
    assert len(dirty) == 1
    assert dirty[0]['round_num'] == 1
    assert dirty[0]['reason'] == 'template_mismatch'
    assert dirty[0]['expected'] == '奖励'


def test_special_env_evidence_exonerates() -> None:
    """带特殊环境证据字段(invest-env 改节点/实读真值)的偏离不标脏。"""
    assert validate_p1_node_sequence([_row(1, '遭遇', special_env_evidence='人身意外险+补给')]) == []
    assert validate_p1_node_sequence([_row(4, '遭遇', node_source='live_read')]) == []


def test_plane_node_table_is_authority() -> None:
    """传开局帧实读槽序 → 以它为该局期望(变异位概念失效)。"""
    table = ['奖励', '奖励', '普通战斗', '遭遇', '补给', '补给', '遭遇', '奖励', 'boss']
    rows = [_row(4, '遭遇'), _row(6, '补给'), _row(1, '奖励')]
    assert validate_p1_node_sequence(rows, plane_node_table=table) == []
    # 与实读表冲突才算脏(原因不再降级 variant_slot)
    dirty = validate_p1_node_sequence([_row(4, '普通战斗')], plane_node_table=table)
    assert dirty == [{'run_id': 'run_test', 'round_num': 4, 'node_type': '普通战斗',
                      'expected': '遭遇', 'reason': 'template_mismatch'}]


def test_out_of_range_and_missing_field() -> None:
    """越界轮与缺字段行分别标 round_out_of_range / missing_field。"""
    dirty = validate_p1_node_sequence([
        _row(10, '奖励'), _row(0, '奖励'),
        {'run_id': 'run_test'},          # 缺 round_num/node_type
        _row('x', '奖励'),               # round_num 非数
    ])
    reasons = sorted(d['reason'] for d in dirty)
    assert reasons == ['missing_field', 'missing_field',
                       'round_out_of_range', 'round_out_of_range']


def test_takeover_fake_rows_caught_corpus_regression() -> None:
    """语料实锤回归:两异常局的接管伪行(P1r1 战斗/遭遇,真值 r6/r7)被捕获。"""
    rows = [
        _row(1, '普通战斗', run_id='run_20260823_151050'),
        _row(1, '遭遇', run_id='run_20260823_151913'),
    ]
    dirty = validate_p1_node_sequence(rows)
    assert len(dirty) == 2
    assert all(d['reason'] == 'template_mismatch' for d in dirty)
    assert {d['run_id'] for d in dirty} == {
        'run_20260823_151050', 'run_20260823_151913'}


def test_p2_interface_reserved() -> None:
    """P2 校验留接口:模板证据不足,显式 NotImplementedError 防误用。"""
    with pytest.raises(NotImplementedError):
        validate_p2_node_sequence([])
