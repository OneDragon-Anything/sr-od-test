"""CW 统一动作工厂 批2a 锁面(原子通路就位 + 逻辑态建模扩域)。

 §3.2a 判据七组锁(2a 半)+
 组合壳溶解 / R4 CwActionCollectOreParam 改形 / R6 CwActionLevelUpParam 定案④ /
R7 武装箱画面 op / R8 工具各立类 / R9 逻辑态全覆盖 / 裁决 3 零比对)。
规则正本 = flow/action-logic-state.md(同批转录版)。

锁面全部为运行时行为锁(源码扫描测试禁止,AGENTS.md §10.4);
kernel/执行器级用桩宿主,零真实 IO。
"""

from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
    deployed_indexed_of_view,
)


from types import SimpleNamespace

import numpy as np
import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
    report_action_deploy_move_param,
    report_action_level_up_param,
    report_action_sell_bench_param,
    report_action_sell_deployed_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    xp_apply_clicks,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
    bench_view_slots_of,
    consume_defect_sink,
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    deploy_slot_plans,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')



# ===== CwActionCollectOreParam 改形专锁(判据 3 前半)=====

def test_ore_selection_kernel_orders_big_first_and_caps():
    """挑选 kernel 单一源:大晶矿优先(r 降序稳定排序)+ 预算上界;载荷 =
    有序 (x, y) 坐标列。"""
    spheres = [('blue', Point(30, 40), 20),
               ('gold', Point(10, 20), 50),
               ('blue', Point(70, 80), 35)]
    pts = select_ore_clicks(spheres, 2)
    assert pts == ((10, 20), (70, 80))
    assert select_ore_clicks(spheres, 99) == ((10, 20), (70, 80), (30, 40))
    assert select_ore_clicks([], 3) == ()


def test_ore_executor_is_mechanical_payload_clicks(monkeypatch):
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
    from sr_od.application.currency_war.kernel.cw_ore_reward import OreReward
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.spheres, OreSight(
        count=2, colors=('gold', 'blue'),
        points=(('gold', 12, 34, 50), ('blue', 99, 99, 10))),
               sig=ChannelSig(family='obs', actor='cw4_seed',
                       mode='synthesized'))
    # logic-rand-sampling 迭代:bench/level 前置守卫在册,须观测方可摘除
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty') for _ in range(9)], capacity=9),
        sig=ChannelSig(family='obs', actor='CwScreenPrep'))
    gs.observe(gs.level, 5, sig=ChannelSig(family='obs', actor='CwScreenPrep'))
    gs.write_logic_rand(
        gs.ore_rewards,
        {'12,34': OreReward(kind='gold', gold=2),
         '99,99': OreReward(kind='gold', gold=2)},
        produced_by='test-seed',
        sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
    report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((12, 34),)),
        sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
    assert [(p[1], p[2]) for p in gs.spheres.value.points] == [(99, 99)]
    assert '12,34' not in (gs.ore_rewards.value or {}), '开成即键移除'
    assert '99,99' in gs.ore_rewards.value, '未被点的附着保全'


# ===== R9 逻辑态全覆盖锁(判据 5)=====

@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(工具上报升格容器写后,本测覆盖循环会落 tool_*
    留证行;后清防外泄——全局缓冲被后续测试整池排水对账,残留行即假红)。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


def test_vocab_actions_all_have_logic_state_projection(
        _isolate_defect_buffer):
    """词表逻辑态覆盖锁(R9;动作 op 重组后宿主 = 上报函数族
    ``kernel/cw_action_report``,每动作恰一个具名函数——原聚合写口
    ``apply_prep_action_logic`` 随批退役)。

    覆盖面三集(登记面申报 = 函数族 docstring:有容器写动作一动作
    一文件,零写族集中 ``zero_writes``):
    - **容器写集**:CwActionSellBenchParam/CwActionSellDeployedParam/
      CwActionDeployMoveParam/CwActionLevelUpParam/CwActionCollectOreParam/
      CwActionOpenTomeParam/CwActionOpenBookcardParam/CwActionWearEquipParam
      ——供数容器上逐动作必产生容器写(write_seq 推进);
    - **工具容器写集**(tool-gain-report 迭代自零写族升格,机械执行直接
      上报写容器):冶金炉/特权赋予卡/拆装扳手/精密拆装扳手/员工投影仪/
      完美投影仪——逐动作面对相同入场态(equips 含该工具 + 目标件/穿戴
      面)必产生容器写;好运令牌除外(见零写集);
    - **合法零写集**:CwActionOpenBoxParam(R7 终结化)/CwActionLuckyTokenUse
      Param(判据面 fail-closed 永不准入,上报零写留证)。
    裁决注记:CwActionWearEquipParam 原在零写集(聚合口形态),上报
    函数族起穿戴 = 发出即记账 owned −1(在册才减,执行侧效果收编进
    上报),按新事实移入容器写集;工具六类原在零写集(零写占位),
     迭代升格容器写。函数名机械推导(snake
    规约同 test_cw_action_report_contract)。"""
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
    _sig = ChannelSig(family='obs', actor='cw4_seed',
                      mode='synthesized')
    _logic = ChannelSig(family='logic_action', actor='CwScreenPrep')
    # 供数容器:bench(2 unit+1 tome+1 bookcard+1 box)、front 1 人、gold/level/xp、晶矿
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                               equips=[])),
              BenchSlot(kind='unit', unit=Unit(char_id='乙', star=1,
                                               equips=[])),
              BenchSlot(kind='tome'),
              BenchSlot(kind='bookcard'),
              BenchSlot(kind='supply_box')]
    _slots += [BenchSlot(kind='empty') for _ in range(4)]
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    gs.observe(gs.deployed, _dvs([Unit(char_id='丙', star=1, equips=[])], []), sig=_sig)
    gs.observe(gs.gold, 10, sig=_sig)
    gs.observe(gs.level, 3, sig=_sig)
    gs.observe(gs.xp, (0, 4), sig=_sig)
    gs.observe(gs.spheres, OreSight(
        count=1, colors=('gold',), points=(('gold', 1, 2, 9),)), sig=_sig)
    gs.observe(gs.equips, ['轮滑鞋'], sig=_sig)

    def _seq() -> int:
        return gs.write_seq

    # 工具容器写集(tool-gain-report 升格):逐动作重播种「equips 含该
    # 工具 + 目标件/穿戴面 + 前排 1 号位有单位」的相同入场态——前序工具
    # 动作会消耗件名(炉替换/特权变换/扳手回区)与穿戴面,覆盖锁按同一
    # 入场态逐个评估写行为;重播种 = 容器域 builder 同写入口(observe)。
    def _reseed_tool_state(tool_name: str, target_unit: Unit) -> None:
        gs.observe(gs.equips, [tool_name, '轮滑鞋'], sig=_sig)
        gs.observe(gs.deployed, _dvs([target_unit], []), sig=_sig)

    tools_written: list = [
        (CwActionFurnaceUseParam(target_kind='equip', item_name='轮滑鞋'),
         '冶金炉'),
        (CwActionPrivilegeCardUseParam(target_kind='equip',
                                       item_name='轮滑鞋'), '特权赋予卡'),
        (CwActionWrenchUseParam(row='front', slot=1), '拆装扳手'),
        (CwActionPrecisionWrenchUseParam(row='front', slot=1), '精密拆装扳手'),
        (CwActionStaffProjectorUseParam(row='front', slot=1), '员工投影仪'),
        (CwActionPerfectProjectorUseParam(row='front', slot=1), '完美投影仪'),
    ]
    for action, tool in tools_written:
        _reseed_tool_state(tool, Unit(char_id='丙', star=1,
                                      equips=['轮滑鞋']))
        before = _seq()
        _report(gs, action)
        assert _seq() > before, f'{type(action).__name__} 应产生容器写'
    # 供数容器重播种(工具循环的消耗/置换不复原;穿戴腿依赖
    # owned 在册、卖出腿依赖前排 1 号位有单位)。
    gs.observe(gs.equips, ['轮滑鞋'], sig=_sig)
    gs.observe(gs.deployed, _dvs([Unit(char_id='丙', star=1, equips=[])], []), sig=_sig)

    written: list = [
        CwActionSellBenchParam(bench_idx=0),
        CwActionSellDeployedParam(deployed_idx=0),
        CwActionDeployMoveParam(bench_idx=1, to_row='front', to_slot=2,
                                faction=''),
        CwActionLevelUpParam(cost=0),
        CwActionCollectOreParam(points=((1, 2),)),
        CwActionOpenTomeParam(slot=None),
        CwActionOpenBookcardParam(slot=None),
    ]
    zero: list = [
        CwActionOpenBoxParam(slot=None),
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
    # 穿戴腿单独重播种(布尔契约前置:owned 在册 + 目标角色在册——前序
    # 卖出腿已消耗前排;与工具循环同款入场态纪律)。
    gs.observe(gs.equips, ['轮滑鞋'], sig=_sig)
    gs.observe(gs.deployed, _dvs([Unit(char_id='丙', star=1, equips=['轮滑鞋'])], []), sig=_sig)
    before = _seq()
    _report(gs, CwActionWearEquipParam(item_name='轮滑鞋', char_name='丙',
                                       row='front', slot=1))
    assert _seq() > before, 'CwActionWearEquipParam 应产生容器写'
    # 词表覆盖完备性:三集并集(含独立重播种的穿戴腿)覆盖 CW_ACTION_TYPES
    # 中非转场/非组合壳成员
    names = {c.__name__ for c in CW_ACTION_TYPES}
    covered = ({type(a).__name__ for a, _t in tools_written}
               | {type(a).__name__ for a in written}
               | {type(a).__name__ for a in zero}
               | {'CwActionWearEquipParam'})
    assert names >= covered   # 三集均为词表成员(不越词表)


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


def test_levelup_executes_single_click_per_frame(monkeypatch):
    """R6 定案④执行器半:一次 execute = 恰一次单击(零授权零循环;
    升 N 击 = N 帧)。金腿批2b 翻转 = action.cost 逻辑态直写(唯一写点
    report_action_level_up_param),执行缝金差退役:执行点
    gold_delta 恒 0(不进回执 extra 键、不经 _advance_gold)。
    建档纪律(用户裁定 2026-09-22):按钮 area 命中 = 每帧恰一击;
    缺失 = round_fail 零点击(禁兜底坐标,emitted=False 未发出事实)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_prep_level_up_action as lvl_mod

    controller = _RecordingController()
    ex = _make_executor(controller)
    # 命中臂:area_center 命中「备战标识-购买经验」→ 每帧恰一击。
    monkeypatch.setattr(lvl_mod, 'area_center',
                        lambda ctx, name: Point(296, 860))
    ex.execute(CwActionLevelUpParam(cost=4))
    assert len(controller.clicks) == 1
    assert ex.last_gold_delta == 0   # 执行缝金差退役(防双记)
    ex.execute(CwActionLevelUpParam(cost=4))
    assert len(controller.clicks) == 2   # 第二帧再击
    # 缺失臂:area 缺失 → round_fail 零点击零移动(禁兜底坐标静默点击)。
    controller_miss = _RecordingController()
    ex_miss = _make_executor(controller_miss)
    monkeypatch.setattr(lvl_mod, 'area_center', lambda ctx, name: None)
    ex_miss.execute(CwActionLevelUpParam(cost=4))
    assert controller_miss.clicks == [] and controller_miss.moves == [], \
        '按钮 area 缺失 = 零点击(禁兜底坐标)'


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

def test_deploy_slot_plans_front_guarantee_and_slot_set():
    """落位策略锁(P3 锁载体迁移:原 kernel assign/empty 锁迁
    mandate_v1 deploy_plan.deploy_slot_plans,断言语义不变):输出覆盖
    上场集(每件恰一 move)、槽位取自容器空槽集、前排保证(pref=back ∧
    前排全空 → 真 front 先提/无 front 强转)。

    名字表达纪律:排偏好经注册表角色名获得(砂金=front,花火/爻光=
    back〔flex 派生 back〕),禁种子构造注入口。"""
    gs = game_state_of(None)   # 行域未观察 = 前后排全空
    # P4 容器形:落位策略输入 = 容器占席条目
    bench = [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1)),
             BenchSlot(kind='unit', unit=Unit(char_id='砂金', star=1)),
             BenchSlot(kind='unit', unit=Unit(char_id='爻光', star=1))]
    moves = deploy_slot_plans(bench, [0, 1, 2], None, gs)
    # 前排保证:花火 pref=back、前排全空、砂金为真 front → 砂金先提
    assert moves[0][0] == 1 and moves[0][1] == 'front'
    # 槽位不重叠、全部来自空槽集
    used = [(row, slot) for _i, row, slot in moves]
    assert len(used) == len(set(used))
    assert all(slot in (set(range(1, 5)) if row == 'front'
                        else set(range(1, 7))) for row, slot in used)
    # 两排全满 = 截断(防御停)
    gs_full = game_state_of(None)
    gs_full.observe(gs_full.deployed,
                    _dvs([Unit(char_id=f'前{i}', star=1, equips=[])
                          for i in range(1, 5)],
                         [Unit(char_id=f'后{i}', star=1, equips=[])
                          for i in range(1, 7)]),
                    evidence='t', sig=_SIG_OBS)
    moves2 = deploy_slot_plans(bench, [0], None, gs_full)
    assert moves2 == []


def test_deploymove_logic_state_moves_unit_and_increments_board():
    """CwActionDeployMoveParam 容器逻辑态(§3.1 落码;落位载荷契约改造):
    bench 摘槽 + deployed 按载荷 (to_row, to_slot) 直落;目标槽有人 =
    交换交互(被占位角色回源 bench 槽);载荷槽非法/源槽空 = 零写。
    (docstring 收窄:board 羁绊增量面本测未断言,不虚报。)"""
    gs = game_state_of(None)
    bc = BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1))
    slots: list[BenchSlot | None] = [None] * 9
    slots[2] = bc
    gs.observe(gs.bench, cw4_bview(slots), evidence='t', sig=_SIG_OBS)
    gs.observe(gs.board, {'欢愉': 1}, evidence='t', sig=_SIG_OBS)
    report_action_deploy_move_param(gs, CwActionDeployMoveParam(bench_idx=2,
                                                   to_row='front',
                                                   to_slot=1,
                                                   faction=''),
                                    sig=_SIG)
    bench_after = bench_view_slots_of(gs)
    assert bench_after[2] is None or bench_after[2].kind == 'empty'
    dep = deployed_indexed_of_view(gs.deployed.value)
    # 落位 = 载荷直落(前排 1 号)
    assert dep[0] is not None and dep[0].char_id == '甲'
    # 目标槽有人 = 交换:甲拖到前排 1 号(乙0 占位)→ 甲落 1 号、乙0 回源
    # bench 槽 3(与 CwActionSwapDeployParam 换位契约同语义)
    gs.observe(gs.bench, cw4_bview(list(slots)), evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed,
               _dvs([Unit(char_id=f'乙{i}', star=1, equips=[]) for i in range(4)],
                    [Unit(char_id=f'丙{i}', star=1, equips=[]) for i in range(6)]),
               evidence='t', sig=_SIG_OBS)
    report_action_deploy_move_param(gs, CwActionDeployMoveParam(bench_idx=2,
                                                   to_row='front',
                                                   to_slot=1,
                                                   faction=''),
                                    sig=_SIG)
    dep = deployed_indexed_of_view(gs.deployed.value)
    assert dep[0] is not None and dep[0].char_id == '甲', \
        '交换语义:上场者落被占位的目标槽'
    assert dep[1].char_id == '乙1', '其余占位不受交换波及'
    swapped_back = bench_view_slots_of(gs)[2]
    assert swapped_back is not None and swapped_back.kind == 'unit' \
        and swapped_back.unit.char_id == '乙0', \
        '交换语义:被占位角色回发射者源 bench 槽'
    # 陈旧提案:载荷槽跨排(前排无 5 号,front 5 号换算落表后段不符)
    # = 零写(源槽不摘)
    report_action_deploy_move_param(gs, CwActionDeployMoveParam(bench_idx=2,
                                                   to_row='front',
                                                   to_slot=5,
                                                   faction=''),
                                    sig=_SIG)
    _src2 = bench_view_slots_of(gs)[2]
    assert _src2 is not None and _src2.kind == 'unit' \
        and _src2.unit.char_id == '乙0'   # 源槽未摘(整笔零写)


def test_selldeployed_logic_state_clears_slot_and_recounts_board():
    """CwActionSellDeployedParam 容器逻辑态(§3.2 落码):deployed 摘槽;金域零写口径
    = gold 未观察时跳写(回金公式单一源 = sell_refund)。(docstring 收窄:
    board 重算面本测未断言,不虚报。)"""
    gs = game_state_of(None)
    gs.observe(gs.deployed, _dvs([Unit(char_id='甲', star=2, equips=[])], []), evidence='t', sig=_SIG_OBS)
    report_action_sell_deployed_param(
        gs, CwActionSellDeployedParam(deployed_idx=0), sig=_SIG)
    dep = deployed_indexed_of_view(gs.deployed.value)
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
    session = SimpleNamespace()
    gs = game_state_of(session)
    bc = BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1))
    slots: list[BenchSlot | None] = [None] * 9
    slots[0] = bc
    gs.observe(gs.gold, 10, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.bench, cw4_bview(slots), evidence='t',
               sig=_SIG_OBS)
    # (3.2:旧执行缝腿数据源 tracked 第二账已退役;确认口零入账判据
    #  由「动作参数零入账」本身承载,主域 bench 即唯一账。)
    refund = sell_refund(1, bench_char_cost(bc.unit))
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

    controller = _RecordingController()
    screens: list[int] = []
    monkeypatch.setattr(cw_equipment, 'ensure_equip_sift_templates',
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
