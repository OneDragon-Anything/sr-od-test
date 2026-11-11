"""策略卡空仓+ 登记面测试(cw_investments 分目录镜像;姊妹锁先例 =
同目录 test_strategy_empty_equip_xp_grants.py)。

测试面依据 = 设计稿(原件已退役)T-190 对应稿 §4
(已退役评审稿 无需用户决定 6/6;卡面官方原文:「获得1件随机的简易装备和10经验值。
进入新节点时，如果物品栏和备战席没有任何装备(消耗品除外)，则获得2经验值。」):

- 三条效果条目登记单一源:窗效果条目行值 = 卡面直读 2(与姊妹空仓同谓词复用,机制件
  零新);即时效果条目 xp_instant=10(字段分派通道自动覆盖,现金分随 XP_GOLD_RATE
  激活);装备效果条目 1 件简易 = 随机装备族泛化表行(工厂生成式自动跟随);
- 估值零登记维持(随机装备不可具名,姊妹同判)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_EMPTY_EQUIP_XP_GRANTS,
    EconomyEffect,
)

_CARD = '空仓+'


def test_kongcang_plus_window_row() -> None:
    """窗效果条目行值直测:空仓表 +1 行 = 卡面直读 2(与姊妹空仓同谓词复用,
    机制件零新——谓词按表逐卡遍历,姊妹行锁零改自动覆盖本卡)。"""
    assert STRATEGY_EMPTY_EQUIP_XP_GRANTS[_CARD] == 2, \
        f'窗效果条目行值漂移: {STRATEGY_EMPTY_EQUIP_XP_GRANTS[_CARD]!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:202402', \
        '注册行 id 对拍(202402,改名/换 id 漂移哨现值通过)'


def test_kongcang_plus_instant_xp_row() -> None:
    """即时效果条目行值直测:xp_instant=10(卡面「获得10经验值」直读;字段分派
    通道零新代码,现金分随 XP_GOLD_RATE 自动激活——固定理财族先例同构)。"""
    assert STRATEGY_ECONOMY[_CARD] == EconomyEffect(xp_instant=10), \
        f'即时效果条目行值漂移: {STRATEGY_ECONOMY[_CARD]!r}'


def test_kongcang_plus_random_equip_row() -> None:
    """装备效果条目行值直测:泛化表 ('简易', 1)(卡面「获得1件随机的简易装备」
    直读;生成式注册自动跟随,无具名 gift 零估值面)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_RANDOM_EQUIP_GRANTS,
    )
    assert _STRATEGY_RANDOM_EQUIP_GRANTS[_CARD] == ('简易', 1), \
        f'装备效果条目行值漂移: {_STRATEGY_RANDOM_EQUIP_GRANTS[_CARD]!r}'
    assert _CARD in PICK_INVEST_EFFECTS, '生成式注册自动入选卡效果表'
