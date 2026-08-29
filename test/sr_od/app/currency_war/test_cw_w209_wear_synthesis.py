# -*- coding: utf-8 -*-
"""W209e/ADR-0387:穿着触发自动合成的装备对账等价豁免(run 26 取实锤锁)。

游戏机制(编排者现场取证,run 26):角色**穿着的两件基础件恰为某进阶配方
组件**(自配同件×2 / 交叉两件不同)→ 画面自动合成显示该进阶——我们的
tracking 不建模该行为,旧对账把已知形态误报 EquipsInconsistencyError
(风堇/卡芙卡 各一次实证)。

实锤锚(日志/画面对照):
- 风堇:量产型装甲×2 → 很硬的甲(SELF_RECIPES);
- 卡芙卡:光能电池+生命之花 → 绝对热量(GUANGNENG_CROSS)。
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / 'src'))

from sr_od.application.currency_war.kernel.cw_bench_equips import (
    assert_equips_consistency,
    wear_synthesis_equivalent,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar


def test_run26_self_recipe_equivalent() -> None:
    """实锤①:账面 [量产型装甲×2] ↔ 画面 [很硬的甲](自配)。"""
    assert wear_synthesis_equivalent(['量产型装甲', '量产型装甲'], ['很硬的甲'])


def test_run26_cross_recipe_equivalent() -> None:
    """实锤②:账面 [光能电池,生命之花] ↔ 画面 [绝对热量](交叉)。"""
    assert wear_synthesis_equivalent(['光能电池', '生命之花'], ['绝对热量'])


def test_multistep_closure() -> None:
    """闭包:多次合成链(组件×3 → 进阶+组件 → 再合成)可达即等价。"""
    # 量产型装甲×3 → 很硬的甲 + 装甲×1(不可再合)≠ [很硬的甲];
    # 但 组件A×2 合成后恰与第三件再交叉的场景可达:
    # 光能电池×2 → 永动机(自配),再与任意件共存 = [永动机, X]
    assert wear_synthesis_equivalent(['光能电池', '光能电池', '生命之花'],
                                     ['永动机', '生命之花'])


def test_no_recipe_not_equivalent() -> None:
    """无配方关联的多重集不等价(豁免不得放水)。"""
    assert not wear_synthesis_equivalent(['光能电池'], ['永动机'])  # 单件不够自配
    assert not wear_synthesis_equivalent(['甲', '乙'], ['丙'])      # 未知配方
    assert not wear_synthesis_equivalent([], ['很硬的甲'])
    assert not wear_synthesis_equivalent(['很硬的甲'], ['很硬的甲', '很硬的甲'])
    # 反向(账面进阶 画面组件)不等价——合成不可逆
    assert not wear_synthesis_equivalent(['很硬的甲'], ['量产型装甲', '量产型装甲'])


def test_assert_consistency_exempt_and_real_mismatch() -> None:
    """assert_equips_consistency:等价豁免不 raise;真漂移照 raise。"""
    c = BenchChar(slot=1, char_id='风堇', position_pref='back')
    c.equips = ['量产型装甲', '量产型装甲']
    assert_equips_consistency(c, ['很硬的甲'], 'test')   # 豁免
    c2 = BenchChar(slot=2, char_id='卡芙卡', position_pref='back')
    c2.equips = ['光能电池']
    try:
        assert_equips_consistency(c2, ['永动机'], 'test')
        raise SystemExit('should raise')
    except SystemExit:
        raise
    except Exception:
        pass   # EquipsInconsistencyError 预期
