"""W971 P3b 段1 接线锁:开局编排接线 + overlay 分发接管 + ctx 信箱退役。

设计单一源 = docs/develop/currency_war/prereg/w971_flow_layer/
01-opening.md(开局序列/接管局/位面切换)、06-overlays.md(完成承诺两口径)。
源码结构锁(inspect.getsource):锁「分发接线与退役清单」,不锁分布数值。
"""

import inspect

from sr_od.application.currency_war.operations import cw_loop
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_briefing as briefing_mod,
)


def _loop_src() -> str:
    return inspect.getsource(cw_loop.CwLoop)


# ==================== 开局编排接线(01-opening §2/§2.1) ====================


# (2026-09-03 攻击性排查:原 test_opening_sequence_dissolved_branches_wired 删除
#  ——五条断言与 test_cw_dispatch_order_matrix.py::test_dissolved_opening_sequence_
#  in_matrix 逐字重复,后者为超集(额外锁开局两屏登记序锁矩阵,防「删壳忘接线」),
#  纪律 7 跨文件择一留超集。)


def test_briefing_plane_invest_inline_branches_retired() -> None:
    """三段退役(01-opening §2):0a0b 位面简报内联、位面过渡点空白内联、
    开局投资环境段不再出现在主循环。"""
    src = _loop_src()
    # 位面简报只在入场出现(用户裁决,01-opening §2.2)→ 简报分发点归
    # OpeningSequence/CwScreenBriefing,loop 不再有简报采集+点「下一步」内联分支。
    assert "'货币战争-简报', '按钮-下一步'" not in src, '位面简报内联分支未退役'
    # 投资环境分支已随拆解退役批接线(0s,见 opening_sequence_dissolved 守卫)。\n    # 位面过渡内联点空白退役 → 交 CwScreenPlaneTransition。
    assert 'CwScreenPlaneTransition(self.ctx)' in src, '位面过渡未接 CwScreenPlaneTransition'
    assert "self.round_by_ocr(screen, '点击空白处继续')" not in src, (
        '位面过渡仍走分支2 内联点空白(应改 CwScreenPlaneTransition 分发)'
    )


# ==================== overlay 分发接管(06-overlays §4) ====================


def test_overlay_ops_replace_handler_direct_calls() -> None:
    """七 overlay op 接入循环分发:loop 不再直调被接管的 handler/内联选卡。"""
    src = _loop_src()
    # 退役批终态:旧 handler 直调名(HandleX(self.ctx))已随改名消失;
    # 委托壳直调历史同步溶解(见 wrapper_family_dissolved 锁)。
    for op_name in ('CwScreenMegastar', 'CwScreenPartner', 'CwScreenPlanner',
                    'CwScreenFortune', 'CwScreenWishTrial', 'CwScreenBookcard'):
        assert f'{op_name}(self.ctx)' in src, f'{op_name} 未接入循环分发'


def test_wrapper_family_dissolved_final_shape() -> None:
    """最终形态锁(NAMING §2/§4 收尾):overlay 委托壳族(CwScreenOverlay 基类/
    HANDLER_FACTORY/OVERLAY_OPS)已溶解;主循环直派各 cw_screen 真身画面 op
    (入口门由 0 系分支承担,轮间等待由 loop round_wait 承担)。"""
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar as megastar_mod
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_bookcard,
        cw_screen_fortune,
        cw_screen_partner,
        cw_screen_planner,
        cw_screen_wish_trial,
    )
    src = _loop_src()
    assert not hasattr(megastar_mod, 'CwScreenOverlay'), '委托基类未溶解'
    assert not hasattr(megastar_mod, 'OVERLAY_OPS'), 'OVERLAY_OPS 注册表未溶解'
    for mod, cls in ((cw_screen_partner, 'CwScreenPartner'),
                     (cw_screen_planner, 'CwScreenPlanner'),
                     (cw_screen_fortune, 'CwScreenFortune'),
                     (cw_screen_wish_trial, 'CwScreenWishTrial'),
                     (cw_screen_bookcard, 'CwScreenBookcard')):
        assert hasattr(mod, cls), f'{cls} 画面 op 缺失(NAMING §2 迁移未完成)'
        assert f'{cls}(self.ctx)' in src, f'{cls} 未接入主循环分发'

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
    assert 'cw_briefing_affixes' not in src, 'cw_loop 仍读写简报词缀 ctx 槽'
    assert 'cw_briefing_bosses' not in src, 'cw_loop 仍读写简报 boss ctx 槽'
    assert 'cw_enemy_difficulty' not in src, 'cw_loop 仍读写敌人难度 ctx 槽'


def test_entry_chain_dispatches_briefing_op() -> None:
    """入口链简报屏调度 = CwScreenBriefing;HandleBriefing 退役文件已删。"""
    import importlib.util

    from sr_od.application.currency_war.operations.cw_entry import (
        cw_entry_start as entry_mod,
    )
    src = inspect.getsource(entry_mod.CwEntryStart)
    assert 'CwScreenBriefing(self.ctx)' in src
    assert 'HandleBriefing(self.ctx)' not in src
    # handlers 包已整体退役(命名迁移终态:operations/cw_screen 承接)——
    # find_spec 对父包不存在的子模块路径抛 ModuleNotFoundError 而非返 None,
    # 故只断言父包(父包不在 = 子模块必不在)。
    assert importlib.util.find_spec(
        'sr_od.application.currency_war.operations.handlers') is None, (
        'handlers 包应已整体退役(命名迁移终态:operations/cw_screen 承接)')
    # CwScreenBriefing 为简报唯一执行面(P3a 委托壳已内联)。
    assert not hasattr(briefing_mod.CwScreenBriefing, 'HANDLER_FACTORY'), (
        'CwScreenBriefing 委托壳应已内联(HANDLER_FACTORY 退役)')
