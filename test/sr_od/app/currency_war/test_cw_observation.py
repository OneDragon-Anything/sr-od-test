"""货币战争 OCR 观测层测试。

纯逻辑(parse_settlement_hp;P1.5 结算屏 hp_after 解析)+ 集成(read_affixes 简报词缀,
需 fixture + ctx.ocr_service)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.cw_observation import parse_settlement_hp, read_affixes
from test.conftest import SrTestContext

# 2026-08-05 实跑结算屏 OCR(战斗后「挑战结束」屏):小队生命值=71(战前 84,本战损 13)。
_SETTLEMENT_OCR = [
    '19', '挑战结束', '战斗', '216', '小队生命值71i', '获得金币总览', '数据统计', '基础奖励',
    '5', '试用', '98.3万', '利息C', '试用', '连胜×0', '67.4万', '62.4万', '继续挑战',
]
# 投资策略屏 OCR(含陷阱文本「每损失20点小队生命值获得5」——「生命值」后非紧邻数字,不该误取)。
_INVEST_STRATEGY_OCR = [
    '攻略', '返回备战界面', '请选择投资策略', '正能量', '保险', '幸运喷雾',
    '每损失20点小队生命值获得5', '同于能量上限20%的能量。', '确认',
]


def test_parses_hp_from_settlement() -> None:
    """结算屏「小队生命值71i」→ 71(尾部噪声 'i' 容忍)。"""
    assert parse_settlement_hp(_SETTLEMENT_OCR) == 71


def test_clean_hp_no_noise() -> None:
    """无噪声「小队生命值84」→ 84。"""
    assert parse_settlement_hp(['挑战结束', '小队生命值84', '继续挑战']) == 84


def test_rejects_non_adjacent_digits() -> None:
    """投资策略描述「每损失20点小队生命值获得5」→ 「生命值」后非紧邻数字 → None(不误取 20/5)。"""
    assert parse_settlement_hp(_INVEST_STRATEGY_OCR) is None


def test_no_lifespan_text_returns_none() -> None:
    """无「生命值」文本 → None。"""
    assert parse_settlement_hp(['挑战结束', '数据统计', '继续挑战']) is None


def test_out_of_bounds_rejected() -> None:
    """越界(> HP_MAX)→ 丢弃(防 OCR 垃圾级联)。HP_MIN=0,故 0 允许(见下条)。"""
    assert parse_settlement_hp(['小队生命值999']) is None   # > HP_MAX(200)


def test_zero_hp_allowed_at_min() -> None:
    """HP=0(阵亡)边界允许(HP_MIN=0)。"""
    assert parse_settlement_hp(['小队生命值0']) == 0


def test_read_affixes_briefing(test_context: SrTestContext) -> None:
    """简报词缀行 → 4 个词缀(A8 最高 4)。

    fixture ``screens/货币战争-简报/default.webp``:随从强化/开局不利/变宝为废/丢失幸运。
    read_affixes OCR 区域-词缀行 → 4 词缀 OCR 原名(下游 AFFIX_MECHANIC_MAP 映射机制 tag)。
    """
    if not test_context.has_screen('货币战争-简报', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-简报/default.webp')
    screen = test_context.load_screen('货币战争-简报', 'default')
    affixes = read_affixes(test_context, screen)
    assert len(affixes) == 4, f'期望 4 词缀(A8 最高),实际 {affixes}'
    # OCR 原名透传(下游匹配在 AFFIX_MECHANIC_MAP);校验读到预期词缀(容 OCR 小差异,查关键词)
    joined = '/'.join(affixes)
    assert any(k in joined for k in ('强化', '不利', '废', '幸运', '熄火', '行动')), (
        f'未读到预期词缀,实际 {affixes}'
    )


def test_read_invest_env_options(test_context: SrTestContext) -> None:
    """投资环境 3 卡名读取(HandleInvestEnv._read_options by NAME_CY 行过滤)。

    fixture ``screens/货币战争-投资环境/default.webp``。NAME_CY [360,410] 容卡名 y 随立绘变
    (修前 [378,408] 漏 y<378 的卡名,实机 3 卡名 y 375-378)。
    """
    if not test_context.has_screen('货币战争-投资环境', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-投资环境/default.webp')
    from sr_od.application.currency_war.operations.handlers.handle_invest_env import (
        HandleInvestEnv,
    )
    screen = test_context.load_screen('货币战争-投资环境', 'default')
    op = HandleInvestEnv(test_context)
    opts = op._read_options(screen)
    assert len(opts) == 3, f'期望 3 卡名,实际 {opts}'
