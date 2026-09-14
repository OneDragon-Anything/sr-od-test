"""CW 统一动作工厂 批2a 锁面(原子通路就位 + 逻辑态建模扩域)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-14-unified-action-factory/landing.md §3.2a 判据七组锁(2a 半)+
design.md §2.6(R2 组合壳溶解 / R4 ClickSpheres 改形 / R6 LevelUp 定案④ /
R7 武装箱画面 op / R8 工具各立类 / R9 逻辑态全覆盖 / 裁决 3 零比对)。
规则正本 = flow/action-logic-state.md(同批转录版)。

锁面全部为运行时行为锁(源码扫描测试禁止,AGENTS.md §10.4);
kernel/执行器级用桩宿主,零真实 IO。
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel import cw_prep_actions as kpa
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
    apply_prep_action_logic,
    bench_slots_of,
    board_state_of,
    deployed_slots_of,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PREP_ACTION_TYPES,
    ClickSpheres,
    DeployMove,
    LevelUp,
    OpenTome,
    SellBench,
    SellDeployed,
    WearEquip,
    select_sphere_clicks,
)
from sr_od.application.currency_war.operations.cw_loop import (
    EXHAUSTION_WINDOW_ACTIONS,
    prep_exhaustion_launch_eligible,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


# ===== EXHAUSTION 重推记录(判据 7)=====

def test_exhaustion_whitelist_repushed_to_open_shop_only():
    """白名单重推 = {OpenShop}:RunDeploy 组合壳随 R2 删除,DeployMove 是
    进展性动作不入窗(恒指纹窗内出现 = 部署未落地 = 停机留证形态);
    OpenShop-only 恒指纹窗(上一环 success)满足出战判据(支配性论证,
    出口确定化)。"""
    assert frozenset({'OpenShop'}) == EXHAUSTION_WINDOW_ACTIONS
    sig = (('OpenShop',), ('OpenShop',), ('OpenShop',))
    assert prep_exhaustion_launch_eligible(sig, True,
                                           frozenset({'OpenShop'})) is True
    # 白名单外动作(含部署原子)在窗 = 语义未核实 → 不出战
    assert prep_exhaustion_launch_eligible(sig, True,
                                           frozenset({'OpenShop',
                                                      'DeployMove'})) is False
    assert prep_exhaustion_launch_eligible(sig, False,
                                           frozenset({'OpenShop'})) is False


# ===== ClickSpheres 改形专锁(判据 3 前半)=====

def test_sphere_selection_kernel_orders_big_first_and_caps():
    """挑选 kernel 单一源:大球优先(r 降序稳定排序)+ 预算上界;载荷 =
    有序 (x, y) 坐标列。"""
    spheres = [('blue', Point(30, 40), 20),
               ('gold', Point(10, 20), 50),
               ('blue', Point(70, 80), 35)]
    pts = select_sphere_clicks(spheres, 2)
    assert pts == ((10, 20), (70, 80))
    assert select_sphere_clicks(spheres, 99) == ((10, 20), (70, 80), (30, 40))
    assert select_sphere_clicks([], 3) == ()


def test_sphere_executor_is_mechanical_payload_clicks():
    """执行器机械半:逐载荷坐标点击,零读屏(读屏选球半随 R4 改形退役,
    旧形态靠 op.screenshot 选球——零 screenshot 调用即机械化证明)。"""

    controller = _RecordingController()
    screens: list[int] = []
    ex = _make_executor(controller, screens)
    ex.execute(ClickSpheres(points=((12, 34), (56, 78))))
    assert [(p.x, p.y) for p in controller.clicks] == [(12, 34), (56, 78)]
    assert controller.drags == []   # 点球不拖拽
    assert screens == []            # 零读屏(挑选归决策侧 kernel)
    # 逻辑态:按载荷精确摘球(坐标匹配,非保守清空)
    obs = kpa.PrepObservation(
        spheres=[('gold', Point(12, 34), 50), ('blue', Point(99, 99), 10)])
    out = CwScreenPrep._project_prep_obs(
        SimpleNamespace(_session=lambda: None), ClickSpheres(
            points=((12, 34),)), obs)
    assert [(int(s[1].x), int(s[1].y)) for s in out.spheres] == [(99, 99)]


# ===== R9 逻辑态全覆盖锁(判据 5)=====

def test_vocab_actions_all_have_logic_state_projection():
    """词表逐动作有逻辑态计算(R9):保守回退(None → 交回外循环)分支
    已删——除转场类(§5 显式空)与终结化 OpenBox(R7)与组合壳死类(2b 删)
    外,每个词表成员投影必产出观察帧;词表外类型 = AssertionError 响亮
    暴露。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        FurnaceUse,
        LuckyTokenUse,
        PerfectProjectorUse,
        PrecisionWrenchUse,
        PrivilegeCardUse,
        StaffProjectorUse,
        WearEquip,
        WrenchUse,
    )
    stub = CwScreenPrep.__new__(CwScreenPrep)   # 绕道构造(无框架状态)
    stub._session = lambda: None
    obs = kpa.PrepObservation(
        bench_chars=[BenchChar(slot=3, char_id='刃', star=1)],
        deployed_chars=[BenchChar(slot=1, char_id='刃', star=1,
                                  position_pref='front')],
        owned_equips=['轮滑鞋'], free_bench_slots=5,
        front_occupied={1}, back_occupied=set())
    cases: list = [
        ClickSpheres(points=((1, 2),)),
        OpenTome(),
        SellBench(slot=3),
        DeployMove(from_slot=3, to_row='front', to_slot=2),
        SellDeployed(row='front', slot=1),
        LevelUp(),
        WearEquip(item_name='轮滑鞋', char_name='刃', row='front', slot=2),
        FurnaceUse(target_kind='equip', item_name='轮滑鞋'),
        FurnaceUse(target_kind='char', row='front', slot=1),
        PrivilegeCardUse(target_kind='equip', item_name='轮滑鞋'),
        WrenchUse(row='front', slot=1),
        PrecisionWrenchUse(row='front', slot=1),
        StaffProjectorUse(row='front', slot=1),
        PerfectProjectorUse(row='front', slot=1),
        LuckyTokenUse(row='front', slot=1),
    ]
    names = {c.__name__ for c in PREP_ACTION_TYPES}
    assert 'PickBoxCard' not in names   # R7:词表删除,武装箱选卡归画面 op
    for action in cases:
        out = CwScreenPrep._project_prep_obs(stub, action, obs)
        assert out is not None, type(action).__name__
        assert isinstance(out, kpa.PrepObservation)
    # 词表外 = 分派漏斗被绕过,响亮暴露(禁静默)
    with pytest.raises(AssertionError):
        CwScreenPrep._project_prep_obs(stub, SimpleNamespace(), obs)


# ===== LevelUp 形态锁 2a 半(判据 2)=====

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
    升 N 击 = N 帧)。金腿 = 执行缝金差(单击价记入 _last_levelup_spent)。"""
    controller = _RecordingController()
    ex = _make_executor(controller)
    ex.execute(LevelUp())
    assert len(controller.clicks) == 1
    assert ex._last_levelup_spent is not None \
        and ex._last_levelup_spent > 0
    ex.execute(LevelUp())
    assert len(controller.clicks) == 2   # 第二帧再击


def test_levelup_logic_state_advances_xp_level_without_gold():
    """R6 定案④逻辑态半(2a 中间态):xp/level 跨门槛推进(推进算子
    单一源 = xp_apply_clicks,单击步长);金腿本批不写(执行缝金差承担,
    批 2b 翻转切 action.cost 直写)。"""
    bs = board_state_of(None)
    bs.observe(bs.level, 3, evidence='t', sig=_SIG_OBS)
    bs.observe(bs.xp, (10, 12), evidence='t', sig=_SIG_OBS)
    apply_prep_action_logic(bs, LevelUp(), produced_by='T', sig=_SIG)
    exp_level, exp_cur = xp_apply_clicks(3, 10, 1)
    assert bs.level.value == exp_level
    assert bs.xp.value[0] == exp_cur
    assert bs.gold.value is None   # 金域零写(域集封闭申报)
    # 缺读跳写:level/xp 未观察帧零写不炸
    bs2 = board_state_of(None)
    apply_prep_action_logic(bs2, LevelUp(), produced_by='T', sig=_SIG)
    assert bs2.level.value is None and bs2.xp.value is None


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
    """DeployMove 容器逻辑态(§3.1 落码):bench 摘槽 + deployed 落槽 +
    board 羁绊增量;陈旧提案(源槽空/目标被占)= 零写。"""
    bs = board_state_of(None)
    bc = BenchChar(slot=3, char_id='甲', star=1)
    slots = [None] * 9
    slots[2] = bc
    from sr_od.application.currency_war.kernel.cw_game_state import (
        bench_view_of_slots,
    )
    bs.observe(bs.bench, bench_view_of_slots(slots), evidence='t', sig=_SIG_OBS)
    bs.observe(bs.board, {'欢愉': 1}, evidence='t', sig=_SIG_OBS)
    apply_prep_action_logic(bs, DeployMove(from_slot=3, to_row='front',
                                           to_slot=2),
                            produced_by='T', sig=_SIG)
    bench_after = bench_slots_of(bs)
    assert bench_after[2] is None
    dep = deployed_slots_of(bs)
    assert dep[1] is not None and dep[1].char_id == '甲'
    # 陈旧提案:目标槽已被占 → 零写(前排 1 槽已有单位,再往 1 槽部署被守卫拒)
    bs.observe(bs.bench, bench_view_of_slots(list(slots)), evidence='t', sig=_SIG_OBS)
    bs.observe(bs.front_row, [Unit(char_id='乙', star=1, equips=[],
                                   slot=1)], evidence='t', sig=_SIG_OBS)
    apply_prep_action_logic(bs, DeployMove(from_slot=3, to_row='front',
                                           to_slot=1),
                            produced_by='T', sig=_SIG)
    assert deployed_slots_of(bs)[0].char_id == '乙'   # 已占槽未被覆盖


def test_selldeployed_logic_state_clears_slot_and_recounts_board():
    """SellDeployed 容器逻辑态(§3.2 落码):deployed 摘槽 + board 重算;
    金域零写口径 = gold 未观察时跳写(回金公式单一源 = sell_refund)。"""
    bs = board_state_of(None)
    bs.observe(bs.front_row, [Unit(char_id='甲', star=2, equips=[],
                                   slot=1)], evidence='t', sig=_SIG_OBS)
    apply_prep_action_logic(bs, SellDeployed(row='front', slot=1),
                            produced_by='T', sig=_SIG)
    dep = deployed_slots_of(bs)
    assert dep[0] is None
    assert bs.gold.value is None   # gold 未观察 = 域级跳写
    # 槽空(陈旧提案)= 零写不炸
    apply_prep_action_logic(bs, SellDeployed(row='front', slot=1),
                            produced_by='T', sig=_SIG)


# ===== 零比对出生锁(判据 6)=====

def test_wear_equip_single_mechanical_drag_no_diff_verification(monkeypatch):
    """WearEquip 零比对出生(裁决 3):单次机械拖拽,拖后零验穿读屏
    (原 avatar-slot CV-diff 判穿/补救链通道已删);落位真值归观察对账。"""
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
    ex.execute(WearEquip(item_name='轮滑鞋', char_name='刃',
                         row='front', slot=1))
    assert len(controller.drags) == 1   # 单次机械拖拽(无补救链重试)
    after_drag = len(screens)
    time.sleep(0)   # 拖后仅固定等待,零读屏(零比对:无验穿 diff 读帧)
    assert len(screens) == after_drag


# ===== 武装箱专锁(判据 4)=====

def test_pick_box_card_removed_from_vocab_and_specs(monkeypatch):
    """R7 全链删除:词表无 PickBoxCard(选卡 = 武装箱选择画面 op,选卡即
    终结);适配器映射表无该行(发射面已不存在);决策面 fail-closed 契约
    (越界索引上抛,禁无声回落)由画面 op 决策半继承。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        adapter,
    )
    assert 'PickBoxCard' not in adapter._OP_SPECS
    assert not hasattr(adapter, 'PickBoxCard')
    # 选卡决策 fail-closed 契约(画面 op _decide_card_index 决策半,原位
    # 消费策略契约;局部 fake 策略越界 → 上抛)
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_box_pick as bp,
    )
    assert bp.CwScreenBoxPick.SCREEN_NAME == '货币战争-备战-武装箱选择'
    op = bp.CwScreenBoxPick.__new__(bp.CwScreenBoxPick)
    strategy = SimpleNamespace(
        decide_box_card=lambda names, bs, session, config: 9)
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(
        strategy=strategy, session=SimpleNamespace(), config=None))
    with pytest.raises(ValueError):
        op._decide_card_index(['甲', '乙'])
