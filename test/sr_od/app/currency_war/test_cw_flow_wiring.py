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
    """位面简报内联退役(01-opening §2):简报只在入场出现(用户裁决 §2.2),
    loop 不再有简报采集+点「下一步」内联分支。"""
    src = _loop_src()
    assert "'货币战争-简报', '按钮-下一步'" not in src, '位面简报内联分支未退役'
    # (2026-09-08 瘦身批:原「CwScreenPlaneTransition 分发在场」与「内联点空白
    #  退役」两断言删除——前者是 test_cw_dispatch_order_matrix.py::
    #  test_boss_briefing_vs_plane_transition_exclusion_wired 的真子集(该锁把
    #  分发行钉在 boss 排他判定之后,缺行即红);后者锁的是历史无 kwarg 字面形态,
    #  生产现态的探测调用本就含 lcs_percent=0.8(同矩阵锁反向断言其在场),
    #  其真实失效模式 boss 帧误分发由该排他锁辖,此墓碑只剩快照锁形态。)


# ==================== overlay 分发接管(06-overlays §4) ====================


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
        assert f'{cls}(self.ctx)' in src, f'{cls} 未接入主循环分发'
    # (2026-09-08 瘦身批:原逐类 `hasattr(mod, cls)` 删除——类存在性在 import 时
    #  已被本文件与 test_cw_flow_ops 的 harness 构造双重验证,改名/删类
    #  在 import 处即红;残留 hasattr 只会以「迁移未完成」的失实语义红。本循环
    #  保留 = loop→op 分发接线的独家守卫(矩阵锁判定调用位在场,不锁分发行)。)

def test_interference_popup_branches_retained() -> None:
    """干扰弹窗分支保留(06-overlays §4:死循环修复史分支不退役)。

    只留矩阵未辖的两锚(概率表/简易装备);其余四锚(祈愿试炼/专家邀请函/
    未达上限警告/位面详情标题)的「判定调用位在场+先于备战双锚」已由
    test_cw_dispatch_order_matrix.py 序锁矩阵同名行以更强形态锁定
    (调用位+序位,分支被删/被挪后置均红),裸串在场是其弱化重复
    (2026-09-08 瘦身批删除)。"""
    src = _loop_src()
    for anchor in ('标识-刷新概率表',  # 0e2 概率表
                   '标识-简易装备',      # 0g 阿哈装备选择
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
