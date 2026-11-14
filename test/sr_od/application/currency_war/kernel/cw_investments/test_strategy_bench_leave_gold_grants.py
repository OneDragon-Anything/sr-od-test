"""策略卡备战席条件离场金登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_BENCH_LEAVE_GOLD_GRANTS + 构建校验)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§2.2 +
原稿评审锁(§ 号 = 原稿节序)§四④(卡面官方原文:「进入新节点时，备战席的1星【花火】/
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
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_BENCH_LEAVE_GOLD_GRANTS,
    _validate_strategy_bench_leave_gold_grants,
)

_CARD = '愚者恶作剧'
_ROWS = (('花火', 1, 2), ('火花', 1, 4))


def test_registry_current_value_and_validation_passes() -> None:
    """现表 = v4.7 换季退役态空表 + 直调校验器零异常(唯一条目愚者恶作剧
    V4.7 退场随 A 组清理删登记;同族新卡登记时本断言即红灯强制复审,
    沿 STRATEGY_BOND_TIER_GRANTS 测试同形)。"""
    assert STRATEGY_BENCH_LEAVE_GOLD_GRANTS == {}
    _validate_strategy_bench_leave_gold_grants()


def test_row_values_desc_aligned() -> None:
    """行值-卡面结构对拍(值形防线):星级恒 1(desc「1星」明写);角色名
    ∈ CHARACTER_ROSTER。(离场金与注册费用档平行的旧锁随 v4.7 费用重排
    失效——行值对拍由 _ROWS 值锁承担;登记面恢复时随批生效。)"""
    for name, star, _gold in _ROWS:
        assert star == 1, f'{name}: 星级恒 1(desc 明写)'
        assert name in CHARACTER_ROSTER, f'{name}: 角色名已登记'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿键哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_BENCH_LEAVE_GOLD_GRANTS, '不存在的卡',
                        (('花火', 1, 2),))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_bench_leave_gold_grants()


def test_validator_unknown_char_raises(monkeypatch) -> None:
    """构建校验(角色名哨):角色名不在角色注册表(GUARD 词表)→ ValueError
    (游戏角色词表改版即触发的漂移哨;注入键取策略注册表在册名——
    v4.7 现表空,退场卡名作键会先撞孤儿哨)。"""
    monkeypatch.setitem(STRATEGY_BENCH_LEAVE_GOLD_GRANTS, '躺平',
                        (('花火', 1, 2), ('不存在的角色', 1, 4)))
    with pytest.raises(ValueError, match='角色名不在角色注册表'):
        _validate_strategy_bench_leave_gold_grants()
