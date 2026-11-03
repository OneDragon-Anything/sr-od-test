"""策略卡备战席条件离场金登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_BENCH_LEAVE_GOLD_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-292-yuzhe-ezuoju.md(定稿)§2.2 +
REVIEW-T292 §四④(卡面官方原文:「进入新节点时，备战席的1星【花火】/
【火花】会留下2/4金币并去别处找乐子。」;直构形态先例 = 同目录
test_strategy_bench_count_xp_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(愚者恶作剧 id 260701:值 =
  ((角色名, 星级, 离场金), ...),星级恒 1/金与费用档平行全 desc 明写);
- 行值精确断言 + id 对拍 + 金-费用档平行对拍 = 值形/值域防线的合规承载
  (2026-10-28 治理裁定:登记笔误类对账归评审与测试,import 期形查不加
  ——星级恒 1/金币 > 0 两笔误哨按治理删,本文件锁面精确断言接棒);
- 构建校验负控:孤儿键/角色名两漂移哨(游戏词表改版可独立触发)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTER_ROSTER,
    CHARACTERS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BENCH_LEAVE_GOLD_GRANTS,
    _validate_strategy_bench_leave_gold_grants,
)

_CARD = '愚者恶作剧'
_ROWS = (('花火', 1, 2), ('火花', 1, 4))


def test_registry_row_single_source() -> None:
    """登记单一源(锁 1):键集 = 族现役首例;行值 = 卡面直读((花火,1★,2金),
    (火花,1★,4金));键 ∈ 策略注册表且 id 对拍(防改名/换 id 后静默错挂)。"""
    assert set(STRATEGY_BENCH_LEAVE_GOLD_GRANTS) == {_CARD}, \
        '注册面 = 族现役单卡(同族后继卡独立批,禁顺手代登记)'
    assert STRATEGY_BENCH_LEAVE_GOLD_GRANTS[_CARD] == _ROWS, \
        f'行值漂移: {STRATEGY_BENCH_LEAVE_GOLD_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:260701', \
        '注册行 id 对拍(260701,改名/换 id 漂移哨现值通过)'
    assert INVESTMENT_STRATEGIES[_CARD].name == _CARD, '名字键对拍'


def test_row_values_desc_aligned() -> None:
    """行值-卡面结构对拍(值形防线,星级恒 1/金币>0 笔误哨删后的承重锁):
    星级恒 1(desc「1星」明写);角色名 ∈ CHARACTER_ROSTER;离场金与
    注册费用档平行(花火 2 费留 2 金/火花 4 费留 4 金——desc 判读的结构
    依据,费用档漂移即本锁红)。"""
    for name, star, gold in _ROWS:
        assert star == 1, f'{name}: 星级恒 1(desc 明写)'
        assert name in CHARACTER_ROSTER, f'{name}: 角色名在册'
        assert gold == CHARACTERS[name].cost, \
            f'{name}: 离场金({gold})须与费用档({CHARACTERS[name].cost})平行'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿键哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_BENCH_LEAVE_GOLD_GRANTS, '不存在的卡',
                        (('花火', 1, 2),))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_bench_leave_gold_grants()


def test_validator_unknown_char_raises(monkeypatch) -> None:
    """构建校验(角色名哨):角色名不在 CHARACTER_ROSTER → ValueError
    (游戏角色词表改版即触发的漂移哨)。"""
    monkeypatch.setitem(STRATEGY_BENCH_LEAVE_GOLD_GRANTS, _CARD,
                        (('花火', 1, 2), ('不存在的角色', 1, 4)))
    with pytest.raises(ValueError, match='CHARACTER_ROSTER'):
        _validate_strategy_bench_leave_gold_grants()
