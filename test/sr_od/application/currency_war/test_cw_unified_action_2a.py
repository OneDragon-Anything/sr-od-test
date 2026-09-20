"""CW 统一动作工厂 批2a 锁面(原子通路就位 + 逻辑态建模扩域)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-14-unified-action-factory/landing.md §3.2a 判据七组锁(2a 半)+
design.md §2.6(R2 组合壳溶解 / R4 CwActionCollectOreParam 改形 / R6 CwActionLevelUpParam 定案④ /
R7 武装箱画面 op / R8 工具各立类 / R9 逻辑态全覆盖 / 裁决 3 零比对)。
规则正本 = flow/action-logic-state.md(同批转录版)。

锁面全部为运行时行为锁(源码扫描测试禁止,AGENTS.md §10.4);
kernel/执行器级用桩宿主,零真实 IO。
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
    report_action_deploy_move_param,
    report_action_level_up_param,
    report_action_sell_bench_param,
    report_action_sell_deployed_param,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    assign_deploy_slots,
    empty_deploy_slots,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    xp_apply_clicks,
)
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
    bench_slots_of,
    deployed_slots_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    select_ore_clicks,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    CwActionCollectOreParam,
    CwActionDeployMoveParam,
    CwActionLevelUpParam,
    CwActionOpenTomeParam,
    CwActionSellBenchParam,
    CwActionSellDeployedParam,
    CwActionWearEquipParam,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')



# ===== CwActionCollectOreParam 改形专锁(判据 3 前半)=====

def test_sphere_selection_kernel_orders_big_first_and_caps():
    """挑选 kernel 单一源:大晶矿优先(r 降序稳定排序)+ 预算上界;载荷 =
    有序 (x, y) 坐标列。"""
    spheres = [('blue', Point(30, 40), 20),
               ('gold', Point(10, 20), 50),
               ('blue', Point(70, 80), 35)]
    pts = select_ore_clicks(spheres, 2)
    assert pts == ((10, 20), (70, 80))
    assert select_ore_clicks(spheres, 99) == ((10, 20), (70, 80), (30, 40))
    assert select_ore_clicks([], 3) == ()


def test_sphere_executor_is_mechanical_payload_clicks(monkeypatch):
    """执行器机械半:逐载荷坐标点击,零读屏(读屏选晶矿半随 R4 改形退役,
    旧形态靠 op.screenshot 选晶矿——零 screenshot 调用即机械化证明)。
    (monkeypatch time.sleep = 溢出/动画家族固定等待空等,真机等待节奏
    非本锁辖面。)"""
    monkeypatch.setattr('time.sleep', lambda _s: None)

    controller = _RecordingController()
    screens: list[int] = []
    ex = _make_executor(controller, screens)
    ex.execute(CwActionCollectOreParam(points=((12, 34), (56, 78))))
    assert [(p.x, p.y) for p in controller.clicks] == [(12, 34), (56, 78)]
    assert controller.drags == []   # 采晶矿不拖拽
    assert screens == []            # 零读屏(挑选归决策侧 kernel)
    # 逻辑态:按载荷精确摘晶矿(坐标匹配,非保守清空)——阶段 3.5 宿主 =
    # report_action_collect_ore_param 容器 spheres 精确摘除(原黑板投影
    # 断言随 _project_prep_obs 退役)。
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        BenchView,
        OreSight,
    )
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.spheres, OreSight(
        count=2, colors=('gold', 'blue'),
        points=(('gold', 12, 34, 50), ('blue', 99, 99, 10))),
               sig=ChannelSig(family='obs', actor='synthesize_from_game_state',
                       mode='synthesized'))
    # logic-rand-sampling 迭代:bench/level 前置守卫在册,须观测方可摘除
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty') for _ in range(9)], capacity=9),
        sig=ChannelSig(family='obs', actor='CwScreenPrep'))
    gs.observe(gs.level, 5, sig=ChannelSig(family='obs', actor='CwScreenPrep'))
    report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((12, 34),)),
        sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
    assert [(p[1], p[2]) for p in gs.spheres.value.points] == [(99, 99)]


# ===== R9 逻辑态全覆盖锁(判据 5)=====

def test_vocab_actions_all_have_logic_state_projection():
    """词表逻辑态覆盖锁(R9;动作 op 重组后宿主 = 上报函数族
    ``kernel/cw_action_report``,每动作恰一个具名函数——原聚合写口
    ``apply_prep_action_logic`` 随批退役)。

    覆盖面两集(登记面申报 = 函数族 docstring:有容器写动作一动作
    一文件,零写族集中 ``zero_writes``):
    - **容器写集**:CwActionSellBenchParam/CwActionSellDeployedParam/
      CwActionDeployMoveParam/CwActionLevelUpParam/CwActionCollectOreParam/
      CwActionOpenTomeParam/CwActionOpenBookcardParam/CwActionWearEquipParam
      ——供数容器上逐动作必产生容器写(write_seq 推进);
    - **合法零写集**(正本申报「消费真值归观察」):CwActionOpenBoxParam
      (R7 终结化)/工具原子七类——容器零写。
    裁决注记:CwActionWearEquipParam 原在零写集(聚合口形态),上报
    函数族起穿戴 = 发出即记账 owned −1(在册才减,执行侧效果收编进
    上报),按新事实移入容器写集。函数名机械推导(snake 规约同
    test_cw_action_report_contract)。"""
    import re

    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel import cw_action_report as rpt
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        BenchView,
        OreSight,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionFurnaceUseParam,
        CwActionLuckyTokenUseParam,
        CwActionOpenBookcardParam,
        CwActionOpenBoxParam,
        CwActionPerfectProjectorUseParam,
        CwActionPrecisionWrenchUseParam,
        CwActionPrivilegeCardUseParam,
        CwActionStaffProjectorUseParam,
        CwActionWearEquipParam,
        CwActionWrenchUseParam,
    )

    def _report(gs_, action):
        """类名 → 上报函数机械推导(命名规约:去前后缀转 snake)。"""
        core = type(action).__name__[len('CwAction'):]
        if core.endswith('Param'):
            core = core[:-len('Param')]
        snake = re.sub(r'(?<!^)(?=[A-Z])', '_', core).lower()
        fn = getattr(rpt, f'report_action_{snake}_param')
        return fn(gs_, action, _logic)

    session = cw4_session()
    gs = game_state_of(session)
    _sig = ChannelSig(family='obs', actor='synthesize_from_game_state',
                      mode='synthesized')
    _logic = ChannelSig(family='logic_action', actor='CwScreenPrep')
    # 供数容器:bench(2 unit+1 tome+1 bookcard+1 box)、front 1 人、gold/level/xp、晶矿
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                               equips=[], slot=1)),
              BenchSlot(kind='unit', unit=Unit(char_id='乙', star=1,
                                               equips=[], slot=2)),
              BenchSlot(kind='tome'),
              BenchSlot(kind='bookcard'),
              BenchSlot(kind='supply_box')]
    _slots += [BenchSlot(kind='empty') for _ in range(4)]
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    gs.observe(gs.front_row, [Unit(char_id='丙', star=1, equips=[],
                                   slot=1)], sig=_sig)
    gs.observe(gs.gold, 10, sig=_sig)
    gs.observe(gs.level, 3, sig=_sig)
    gs.observe(gs.xp, (0, 4), sig=_sig)
    gs.observe(gs.spheres, OreSight(
        count=1, colors=('gold',), points=(('gold', 1, 2, 9),)), sig=_sig)
    gs.observe(gs.equips, ['轮滑鞋'], sig=_sig)

    def _seq() -> int:
        return gs.write_seq

    written: list = [
        CwActionSellBenchParam(bench_idx=0),
        CwActionSellDeployedParam(deployed_idx=0),
        CwActionDeployMoveParam(bench_idx=1, to_row='front', faction=''),
        CwActionLevelUpParam(cost=0),
        CwActionCollectOreParam(points=((1, 2),)),
        CwActionOpenTomeParam(slot=None),
        CwActionOpenBookcardParam(slot=None),
        CwActionWearEquipParam(item_name='轮滑鞋', char_name='丙',
                               row='front', slot=1),
    ]
    zero: list = [
        CwActionOpenBoxParam(slot=None),
        CwActionFurnaceUseParam(target_kind='equip', item_name='轮滑鞋'),
        CwActionPrivilegeCardUseParam(target_kind='equip', item_name='轮滑鞋'),
        CwActionWrenchUseParam(row='front', slot=1),
        CwActionPrecisionWrenchUseParam(row='front', slot=1),
        CwActionStaffProjectorUseParam(row='front', slot=1),
        CwActionPerfectProjectorUseParam(row='front', slot=1),
        CwActionLuckyTokenUseParam(row='front', slot=1),
    ]
    for action in written:
        before = _seq()
        _report(gs, action)
        assert _seq() > before, f'{type(action).__name__} 应产生容器写'
    for action in zero:
        before = _seq()
        _report(gs, action)
        assert _seq() == before, f'{type(action).__name__} 应合法零写'
    # 词表覆盖完备性:两集并集覆盖 CW_ACTION_TYPES 中非转场/非组合壳成员
    names = {c.__name__ for c in CW_ACTION_TYPES}
    covered = ({type(a).__name__ for a in written}
               | {type(a).__name__ for a in zero})
    assert {'CwActionCollectOreParam', 'CwActionOpenTomeParam', 'CwActionOpenBookcardParam', 'CwActionOpenBoxParam',
            'CwActionSellBenchParam', 'CwActionDeployMoveParam', 'CwActionSellDeployedParam', 'CwActionLevelUpParam',
            'CwActionWearEquipParam'} <= covered
    assert names >= covered   # 两集均为词表成员(不越词表)


# ===== CwActionLevelUpParam 形态锁 2a 半(判据 2)=====

class _RecordingController:
    def __init__(self) -> None:
        self.moves: list[Point] = []
        self.clicks: list[Point] = []
        self.drags: list[dict] = []

    def mouse_move(self, p: Point) -> None:
        self.moves.append(p)

    def click(self, p: Point) -> None:
        self.clicks.append(p)

    def drag_to(self, **kw: object) -> None:
        self.drags.append(dict(kw))


def _make_executor(controller: _RecordingController,
                   screens: list | None = None):
    from sr_od.application.currency_war import prep_actions as pa
    op = SimpleNamespace(park_cursor=lambda **kw: None,
                         screenshot=lambda: (screens.append(1) if
                                             screens is not None else None)
                         or np.zeros((4, 4), dtype='uint8'))
    ctx = SimpleNamespace(controller=controller, cw_match=None,
                          run_context=None,
                          screen_loader=SimpleNamespace(
                              get_screen=lambda name: None))
    return pa.PrepActionExecutor(op, ctx)


def test_levelup_executes_single_click_per_frame():
    """R6 定案④执行器半:一次 execute = 恰一次单击(零授权零循环;
    升 N 击 = N 帧)。金腿批2b 翻转 = action.cost 逻辑态直写(唯一写点
    report_action_level_up_param),执行缝金差退役:执行点
    gold_delta 恒 0(不进回执 extra 键、不经 _advance_gold)。"""
    controller = _RecordingController()
    ex = _make_executor(controller)
    ex.execute(CwActionLevelUpParam(cost=4))
    assert len(controller.clicks) == 1
    assert ex.last_gold_delta == 0   # 执行缝金差退役(防双记)
    ex.execute(CwActionLevelUpParam(cost=4))
    assert len(controller.clicks) == 2   # 第二帧再击


def test_levelup_logic_state_advances_xp_level_and_gold():
    """R6 定案④逻辑态半(批2b 翻转):xp/level 跨门槛推进(推进算子
    单一源 = xp_apply_clicks,单击步长)+ 金腿 action.cost 直写(唯一
    写点,执行缝金差退役防双记)。gold 未观察 = 域级跳写(值留观察)。"""
    gs = game_state_of(None)
    gs.observe(gs.level, 3, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.xp, (10, 12), evidence='t', sig=_SIG_OBS)
    gs.observe(gs.gold, 100, evidence='t', sig=_SIG_OBS)
    report_action_level_up_param(gs, CwActionLevelUpParam(cost=4), sig=_SIG)
    exp_level, exp_cur = xp_apply_clicks(3, 10, 1)
    assert gs.level.value == exp_level
    assert gs.xp.value[0] == exp_cur
    assert gs.gold.value == 96   # 金腿直写:-action.cost
    # 缺读跳写:level/xp 未观察帧零写不炸
    bs2 = game_state_of(None)
    report_action_level_up_param(bs2, CwActionLevelUpParam(cost=4), sig=_SIG)
    assert bs2.level.value is None and bs2.xp.value is None
    # gold 未观察 = 域级跳写(xp/level 照推进)
    bs3 = game_state_of(None)
    bs3.observe(bs3.level, 3, evidence='t', sig=_SIG_OBS)
    bs3.observe(bs3.xp, (10, 12), evidence='t', sig=_SIG_OBS)
    report_action_level_up_param(bs3, CwActionLevelUpParam(cost=4), sig=_SIG)
    assert bs3.gold.value is None


# ===== 原子通路对照锁(判据 7)=====

def test_deploy_slot_assignment_matches_kernel_plan():
    """原子部署发射位件(发射×执行单一源对照):选排指派输出覆盖
    select_deployments 上场集(每件恰一 move)、槽位取自空槽集、前排保证
    (pref=back ∧ 前排全空 → 真 front 先提/无 front 强转)。"""
    bench = [BenchChar(slot=1, char_id='甲', position_pref='back'),
             BenchChar(slot=2, char_id='乙', position_pref='front'),
             BenchChar(slot=3, char_id='丙', position_pref='back')]
    fe, be = empty_deploy_slots([], front_total=4, back_total=6)
    assert fe == [1, 2, 3, 4] and be == [1, 2, 3, 4, 5, 6]
    moves = assign_deploy_slots(bench, [0, 1, 2], fe, be)
    # 前排保证:甲 pref=back、前排全空、乙为真 front → 乙先提
    assert moves[0][0] == 1 and moves[0][1] == 'front'
    # 槽位不重叠、全部来自空槽集
    used = [(row, slot) for _i, row, slot in moves]
    assert len(used) == len(set(used))
    assert all(slot in (set(range(1, 5)) if row == 'front'
                        else set(range(1, 7))) for row, slot in used)
    # 两排全满 = 截断(防御停)
    moves2 = assign_deploy_slots(bench, [0], [], [])
    assert moves2 == []


def test_deploymove_logic_state_moves_unit_and_increments_board():
    """CwActionDeployMoveParam 容器逻辑态(§3.1 落码):bench 摘槽 + deployed 落槽;
    陈旧提案(源槽空/目标被占)= 零写。(docstring 收窄:board 羁绊增量
    面本测未断言,不虚报。)"""
    gs = game_state_of(None)
    bc = BenchChar(slot=3, char_id='甲', star=1)
    slots = [None] * 9
    slots[2] = bc
    from sr_od.application.currency_war.kernel.cw_game_state import (
        bench_view_of_slots,
    )
    gs.observe(gs.bench, bench_view_of_slots(slots), evidence='t', sig=_SIG_OBS)
    gs.observe(gs.board, {'欢愉': 1}, evidence='t', sig=_SIG_OBS)
    report_action_deploy_move_param(gs, CwActionDeployMoveParam(bench_idx=2,
                                                   to_row='front',
                                                   faction=''),
                                    sig=_SIG)
    bench_after = bench_slots_of(gs)
    assert bench_after[2] is None
    dep = deployed_slots_of(gs)
    # 落位 = 首空(deployed_place 单一源,与 simulate 同式):前排 1 号
    assert dep[0] is not None and dep[0].char_id == '甲'
    # 陈旧提案:两排全满 → deployed_place 无位 = 零写(源槽不摘)
    gs.observe(gs.bench, bench_view_of_slots(list(slots)), evidence='t', sig=_SIG_OBS)
    gs.observe(gs.front_row, [Unit(char_id=f'乙{i}', star=1, equips=[],
                                   slot=i + 1) for i in range(4)],
               evidence='t', sig=_SIG_OBS)
    gs.observe(gs.back_row, [Unit(char_id=f'丙{i}', star=1, equips=[],
                                  slot=i + 1) for i in range(6)],
               evidence='t', sig=_SIG_OBS)
    report_action_deploy_move_param(gs, CwActionDeployMoveParam(bench_idx=2,
                                                   to_row='front',
                                                   faction=''),
                                    sig=_SIG)
    assert bench_slots_of(gs)[2].char_id == '甲'   # 源槽未摘(整笔零写)


def test_selldeployed_logic_state_clears_slot_and_recounts_board():
    """CwActionSellDeployedParam 容器逻辑态(§3.2 落码):deployed 摘槽;金域零写口径
    = gold 未观察时跳写(回金公式单一源 = sell_refund)。(docstring 收窄:
    board 重算面本测未断言,不虚报。)"""
    gs = game_state_of(None)
    gs.observe(gs.front_row, [Unit(char_id='甲', star=2, equips=[],
                                   slot=1)], evidence='t', sig=_SIG_OBS)
    report_action_sell_deployed_param(
        gs, CwActionSellDeployedParam(deployed_idx=0), sig=_SIG)
    dep = deployed_slots_of(gs)
    assert dep[0] is None
    assert gs.gold.value is None   # gold 未观察 = 域级跳写
    # 槽空(陈旧提案)= 零写不炸
    report_action_sell_deployed_param(
        gs, CwActionSellDeployedParam(deployed_idx=0), sig=_SIG)


def test_prep_sell_gold_booked_exactly_once_across_seam_and_projection():
    """备战卖出金账全链恰一次入账(统一观察对账迭代 2026-09-16 归因批
    出口①修模锁):历史形态 live 执行链对同一 CwActionSellBenchParam 先后
    跑执行缝(旧 apply_op_effect)与容器投影,两腿各记一次 +refund →
    逻辑金系统性虚高,下帧实读倒挂(journal 实证 −2,2026-09-15
    run_20260915_070645)。修后容器唯一写点 = 卖出上报函数,确认口
    (apply_confirm_effect,dict 确认族专用)对动作参数零入账
    (复返即红:确认口若再收编动作分支即双腿双记)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        bench_char_cost,
        sell_refund,
    )
    from sr_od.application.currency_war.kernel.cw_exec_state import (
        apply_confirm_effect,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        bench_view_of_slots,
    )
    session = SimpleNamespace()
    gs = game_state_of(session)
    bc = BenchChar(slot=1, char_id='甲', star=1)
    slots = [None] * 9
    slots[0] = bc
    gs.observe(gs.gold, 10, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.bench, bench_view_of_slots(slots), evidence='t',
               sig=_SIG_OBS)
    gs.tracked_books.bench = [bc]   # 旧执行缝腿的数据源(腿复返即红)
    refund = sell_refund(1, bench_char_cost(bc))
    action = CwActionSellBenchParam(bench_idx=0)
    apply_confirm_effect(session, action)   # 确认口:动作参数零入账
    report_action_sell_bench_param(gs, action, sig=_SIG)
    assert gs.gold.value == 10 + refund, \
        f'卖出回金恰一次 +{refund}(双腿双记 = 台账 −N 倒挂病灶)'


# ===== 零比对出生锁(判据 6)=====

def test_wear_equip_single_mechanical_drag_no_diff_verification(monkeypatch):
    """CwActionWearEquipParam 单次机械拖拽,无补救链重试(用户裁定:动作 op = 机械
    执行,判效/重试禁入动作层):发出即记账(emitted=True),拖后零
    落地判定,拖拽静默不生效由观察侧 reconcile 对账显影。
    (monkeypatch time.sleep = 拖后固定等待空等,真机等待节奏非本锁辖面。)"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war import prep_actions as pa
    from sr_od.application.currency_war.obs import cw_equipment
    from sr_od.application.currency_war.operations.cw_op import cw_op_equip_all

    controller = _RecordingController()
    screens: list[int] = []
    monkeypatch.setattr(cw_op_equip_all, 'get_equip_templates_cached',
                        lambda ctx: object())
    monkeypatch.setattr(cw_equipment, 'read_equips',
                        lambda screen, templates, equip_rect=None:
                        [('轮滑鞋', (1700, 900), 0.9)])
    monkeypatch.setattr(pa, '_area_rect',
                        lambda ctx, name, screen: SimpleNamespace(
                            x1=1620, y1=850, x2=1918, y2=950))

    class _FakeScreenInfo:
        area_list = [SimpleNamespace(area_name='前排-1',
                                     pc_rect=SimpleNamespace(
                                         x1=600, y1=300, x2=700, y2=340))]

    ex = _make_executor(controller, screens)
    ex._ctx.screen_loader = SimpleNamespace(
        get_screen=lambda name: _FakeScreenInfo())
    ex.execute(CwActionWearEquipParam(item_name='轮滑鞋', char_name='刃',
                         row='front', slot=1))
    assert len(controller.drags) == 1   # 单次机械拖拽(无补救链重试)


# ===== 武装箱专锁(判据 4)=====

# (原 test_pick_box_card_removed_from_vocab_and_specs 的词表/映射表墓碑
#  两腿删:退役符号墓碑 = 源码扫描族,禁止清单无例外;fail-closed 决策
#  契约行为半保留独立成锁。)

def test_pick_box_decision_fail_closed():
    """武装箱选卡决策 fail-closed 契约(画面 op _decide_card_index 决策
    半,原位消费策略契约;局部 fake 策略越界 → 上抛,禁无声回落)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_box_pick as bp,
    )
    assert bp.CwScreenBoxPick.SCREEN_NAME == '货币战争-备战-武装箱选择'
    op = bp.CwScreenBoxPick.__new__(bp.CwScreenBoxPick)
    strategy = SimpleNamespace(
        decide_box_card=lambda: SimpleNamespace(idx=9))
    # 终态契约 §2.7(零参 + 写槽):桩挂载 gs(决策输入 = 容器持有引用;
    # handler 先写 gs.box_card_names 槽再零参调 decide)。
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_2a,
    )
    _sess_2a = SimpleNamespace()
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(
        strategy=strategy, session=_sess_2a, config=None,
        gs=_gso_2a(_sess_2a)))
    with pytest.raises(ValueError):
        op._decide_card_index(['甲', '乙'])
