"""dict 形买牌确认口免费闸测试(cw_exec_state 分目录镜像;宿主面散在
test_prep_action_ops.py 超行数线,dict 口新锁落本镜像目录)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§2.2-3(裁决点 5
A 案:dict 口同闸一行,免张数源 = 实扣张数与扣金张数同源)+ §3 T-92 免费帧
豁免义务。该口现值零 live 调用方(模拟/离线保留口),锁面 = 行为等价防御性
覆盖:未持卡局与改前逐字节同值(全价扣金 + 置位),持卡局免费帧零金写零置位。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_exec_state import (
    apply_confirm_effect,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)

_ACTION = {'op': 'CwActionBuyCardParam', 'name': '希儿', 'star': 1,
           'k': 1, 'cost': 3}


def _seed_session(with_card_uses: int | None) -> object:
    """session 桩:金 30 + 空备战席;with_card_uses 给定 = 直种持卡态。"""
    session = SimpleNamespace()
    from test.sr_od.application.currency_war._cw_helpers import cw4_gs
    gs = cw4_gs(session, bench=[], gold=30)
    if with_card_uses is not None:
        gs.effects.register_strategy(STRATEGY_EFFECTS['降本增效'],
                                     acquired_key=(1, 2))
        gs.effects.first('202301').remaining_uses = with_card_uses
    return session


def test_confirm_buy_card_free_frame_zero_gold_write() -> None:
    """dict 口免费帧:持条目(uses=6)买 1 张 cost=3 → 金零写 + uses 6→5
    (与买牌上报单点同闸同豁免;全免帧零金写)。"""
    session = _seed_session(with_card_uses=6)
    gs = game_state_of(session)
    effects = apply_confirm_effect(session, dict(_ACTION))
    assert gs.gold.value == 30, '免费帧金零变动'
    assert gs.effects.first('202301').remaining_uses == 5, 'uses 递减'
    assert effects == [], '零金推进(推进清单空)'


def test_confirm_buy_card_without_card_pays_full() -> None:
    """dict 口负写端:未持卡局 → 全价扣金(与改前逐字节同值,零扰动)。"""
    session = _seed_session(with_card_uses=None)
    gs = game_state_of(session)
    effects = apply_confirm_effect(session, dict(_ACTION))
    assert gs.gold.value == 27, '未持卡照常扣金(cost×bought)'
    assert effects and effects[0]['path'] == 'gold', '金推进记录已登记'
    assert effects[0]['value'] == '-3(买牌×1)', \
        '免张数 0 时消息形与改前一致(行为等价面)'


def test_confirm_buy_card_free_frame_skips_spend_flag() -> None:
    """dict 口免费帧豁免:全免帧不置花费事件(置位旗维持种子基值不翻
    True——session 载体开局种子 False;存款回报条件输入保真,与买牌上报
    单点同豁免);未持卡局置位照常。"""
    session = _seed_session(with_card_uses=6)
    gs = game_state_of(session)
    apply_confirm_effect(session, dict(_ACTION))
    assert gs.prev_node_spent.value is not True, '免费帧零置位'
    session2 = _seed_session(with_card_uses=None)
    apply_confirm_effect(session2, dict(_ACTION))
    assert game_state_of(session2).prev_node_spent.value is True, \
        '未持卡全价帧置位照常'
