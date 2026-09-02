"""W971 P3b 段1 接线锁:开局编排接线 + overlay 分发接管 + ctx 信箱退役。

设计单一源 = docs/develop/currency_war/prereg/w971_flow_layer/
01-opening.md(开局序列/接管局/位面切换)、06-overlays.md(完成承诺两口径)。
源码结构锁(inspect.getsource):锁「分发接线与退役清单」,不锁分布数值。
"""

import inspect

from sr_od.application.currency_war.operations import battle_loop
from sr_od.application.currency_war.operations.cw_flow import (
    briefing_op as briefing_mod,
)
from sr_od.application.currency_war.operations.cw_flow import (
    overlay_ops as overlay_mod,
)


def _loop_src() -> str:
    return inspect.getsource(battle_loop.CurrencyWarRunLoop)


# ==================== 开局编排接线(01-opening §2/§2.1) ====================


def test_opening_sequence_wired_at_loop_entry() -> None:
    """开局编排接线存在:run 首帧在开局序列画面 → OpeningSequence 首帧分流;
    判定集单一源 = 类常量 OPENING_SEQUENCE_FRAMES(离线锁可枚举)。"""
    src = _loop_src()
    assert 'OpeningSequence(self.ctx)' in src, '开局编排未接进主循环开局路径'
    assert 'OPENING_SEQUENCE_FRAMES' in src, '首帧分流判定集单一源缺失'
    frames = battle_loop.CurrencyWarRunLoop.OPENING_SEQUENCE_FRAMES
    by_screen = dict(frames)
    assert by_screen['货币战争-简报'] == '标识-本场对局首领'
    assert by_screen['货币战争-位面过渡'] == '提示-点击空白继续'
    assert by_screen['货币战争-投资环境'] == '标识-投资环境'


def test_briefing_plane_invest_inline_branches_retired() -> None:
    """三段退役(01-opening §2):0a0b 位面简报内联、位面过渡点空白内联、
    开局投资环境段不再出现在主循环。"""
    src = _loop_src()
    # 位面简报只在入场出现(用户裁决,01-opening §2.2)→ 简报分发点归
    # OpeningSequence/BriefingOp,loop 不再有简报采集+点「下一步」内联分支。
    assert "'货币战争-简报', '按钮-下一步'" not in src, '位面简报内联分支未退役'
    # 投资环境仅开场一次(#11)→ loop 不再分发 HandleInvestEnv。
    assert 'HandleInvestEnv' not in src, '开局投资环境段未退役'
    # 位面过渡内联点空白退役 → 交 PlaneTransitionOp。
    assert 'PlaneTransitionOp(self.ctx)' in src, '位面过渡未接 PlaneTransitionOp'
    assert "self.round_by_ocr(screen, '点击空白处继续')" not in src, (
        '位面过渡仍走分支2 内联点空白(应改 PlaneTransitionOp 分发)'
    )


# ==================== overlay 分发接管(06-overlays §4) ====================


def test_overlay_ops_replace_handler_direct_calls() -> None:
    """七 overlay op 接入循环分发:loop 不再直调被接管的 handler/内联选卡。"""
    src = _loop_src()
    for retired in ('HandleSelectPartner(self.ctx)', 'HandlePlannerEvent(self.ctx)',
                    'HandleFortunePicker(self.ctx)', 'HandleWishTrial(self.ctx)',
                    'RunMegastarNode(self.ctx)', '_handle_star_tome_pick('):
        assert retired not in src, f'{retired} 直调点未退役(应交 overlay op)'
    for op_name in ('MegastarOp', 'PartnerOp', 'PlannerEventOp',
                    'FortunePickerOp', 'WishTrialOp', 'BookcardOp'):
        assert f'{op_name}(self.ctx)' in src, f'{op_name} 未接入循环分发'


def test_overlay_ops_delegate_same_handlers_decision_parity() -> None:
    """新旧编排对拍(验证④·分发面):旧分支 handler ↔ 新 op 委托目标逐项全等
    (同局面同 handler 执行,行为等价由委托构造保证)。"""
    from sr_od.application.currency_war.operations.run_nodes.run_megastar_node import (
        RunMegastarNode,
    )
    from sr_od.application.currency_war.operations.handlers.handle_fortune_picker import (
        HandleFortunePicker,
    )
    from sr_od.application.currency_war.operations.handlers.handle_planner_event import (
        HandlePlannerEvent,
    )
    from sr_od.application.currency_war.operations.handlers.handle_select_partner import (
        HandleSelectPartner,
    )
    from sr_od.application.currency_war.operations.handlers.handle_supply_box import (
        HandleSupplyBox,
    )
    from sr_od.application.currency_war.operations.handlers.handle_wish_trial import (
        HandleWishTrial,
    )
    assert overlay_mod.MegastarOp.HANDLER_FACTORY is RunMegastarNode
    assert overlay_mod.PartnerOp.HANDLER_FACTORY is HandleSelectPartner
    assert overlay_mod.PlannerEventOp.HANDLER_FACTORY is HandlePlannerEvent
    assert overlay_mod.FortunePickerOp.HANDLER_FACTORY is HandleFortunePicker
    assert overlay_mod.WishTrialOp.HANDLER_FACTORY is HandleWishTrial
    assert overlay_mod.ArmoryBoxOp.HANDLER_FACTORY is HandleSupplyBox
    assert tuple(overlay_mod.OVERLAY_OPS) == (
        overlay_mod.MegastarOp, overlay_mod.PartnerOp, overlay_mod.ArmoryBoxOp,
        overlay_mod.WishTrialOp, overlay_mod.PlannerEventOp,
        overlay_mod.FortunePickerOp, overlay_mod.BookcardOp)


def test_interference_popup_branches_retained() -> None:
    """干扰弹窗分支保留(06-overlays §4:死循环修复史分支不退役)。"""
    src = _loop_src()
    for anchor in ('标识-刷新概率表',  # 0e2 概率表
                   '标识-祈愿试炼',      # 0e3 道具详情的祈愿让路排除
                   '标识-简易装备',      # 0g 阿哈装备选择
                   '标识-专家邀请函',    # 0k 专家邀请函
                   '标识-未达上限警告',  # 0d
                   '标识-位面详情标题',  # 0a4 位面详情兜底
                   ):
        assert anchor in src, f'干扰/兜底分支锚 {anchor} 消失(静默丢弃退避停机风险)'


# ==================== ctx 信箱退役(01-opening §1 / W971 §2.1) ====================


def test_ctx_mailbox_absorb_retired() -> None:
    """ctx 信箱退役:吸收段只剩职级难度;简报三字段不再经 ctx 中转。"""
    src = _loop_src()
    assert 'self._absorb_ctx_mailbox' not in src, 'ctx 信箱吸收段未退役(P3 批口径)'
    assert '_absorb_selected_difficulty' in src, '职级难度吸收段缺失(3.5.1 接线断流)'
    assert 'cw_briefing_affixes' not in src, 'battle_loop 仍读写简报词缀 ctx 槽'
    assert 'cw_briefing_bosses' not in src, 'battle_loop 仍读写简报 boss ctx 槽'
    assert 'cw_enemy_difficulty' not in src, 'battle_loop 仍读写敌人难度 ctx 槽'


def test_entry_chain_dispatches_briefing_op() -> None:
    """入口链简报屏调度 = BriefingOp;HandleBriefing 退役文件已删。"""
    import importlib.util

    from sr_od.application.currency_war.operations.entry import (
        start_currency_war_match as entry_mod,
    )
    src = inspect.getsource(entry_mod.StartCurrencyWarMatch)
    assert 'BriefingOp(self.ctx)' in src
    assert 'HandleBriefing(self.ctx)' not in src
    assert importlib.util.find_spec(
        'sr_od.application.currency_war.operations.handlers.handle_briefing') is None, (
        'handle_briefing 模块应已删除(退役文件残留)')
    # BriefingOp 为简报唯一执行面(P3a 委托壳已内联)。
    assert not hasattr(briefing_mod.BriefingOp, 'HANDLER_FACTORY'), (
        'BriefingOp 委托壳应已内联(HANDLER_FACTORY 退役)')
