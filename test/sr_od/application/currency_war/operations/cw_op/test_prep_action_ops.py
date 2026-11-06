"""CW 备战动作 op 测试面(执行器机械半 + 逻辑态上报 + 发射面装载)。

规则权威版本 = docs/develop/sr_od/application/currency_war/flow/
action-logic-state.md 与 flow/logic-updates/prep-executor-actions.md;
op 形态权威版本 = flow/action_ops.md(动作 op = 机械执行后直调自己的上报
函数,映射单一源 = kernel/cw_action_report 同名上报函数族,op-layer.md
§1.2)。测试面三组(全部运行时行为测试,源码扫描测试禁止,AGENTS.md
§10.4;kernel/执行器级用桩宿主,零真实 IO):

- **执行器机械半**:逐动作点击/拖拽契约(零读屏 / 每帧恰一击 / 单次
  机械拖拽无判效重试 / 出战点击序列与弹窗路径 / 免战牌上报递减);
- **逻辑态上报**:每动作的上报函数容器写契约(覆盖完备 + 逐动作摘件/
  落位/腾席/金账恰一次);
- **发射面装载**:kernel 参数构造(晶矿挑选/落位策略)与发射臂装载
  (cost 现算/auth_basis 分键/通道 reason/桥复检语境/状态容器下标 fail-closed
  解析)。
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
    report_action_level_up_param,
    report_action_move_unit_param,
    report_action_open_bookcard_param,
    report_action_sell_bench_param,
    report_action_sell_deployed_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    xp_apply_clicks,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    Unit,
    bench_free_slots,
    bench_view_slots_of,
    consume_defect_sink,
    deployed_indexed_of_view,
    deployed_view_of_indexed,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    select_ore_clicks,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    CwActionCollectOreParam,
    CwActionLevelUpParam,
    CwActionMoveUnitParam,
    CwActionOpenBookcardParam,
    CwActionOpenBoxParam,
    CwActionOpenTomeParam,
    CwActionSellBenchParam,
    CwActionSellDeployedParam,
    CwActionStartBattleParam,
    CwActionWearEquipParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    deploy_slot_plans,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


# ============================================================ 桩宿主


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


class _NoSleepTime:
    """模块内 ``time`` 替身:机械等待记录不真睡(出战 op 的
    POST_CLICK_WAIT 弹窗渲染窗;真机等待节奏非本测试辖面)。"""

    def __init__(self) -> None:
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.skipped.append(seconds)


class _DerefController(_RecordingController):
    """坐标解引用消费替身:mouse_move 即刻消费点坐标(真控制器
    game2win_pos 坐标换算的消费形态)——None 坐标在消费点自然炸
    (零防御契约「取值直接使用」的自然失败形态,terminal-fail-status)。"""

    def mouse_move(self, p) -> None:
        self.moves.append((p.x, p.y))

    def click(self, p) -> None:
        self.clicks.append((p.x, p.y))


def _make_executor(controller: _RecordingController,
                   screens: list | None = None,
                   cw_match=None,
                   screen_loader=None):
    from sr_od.application.currency_war import prep_actions as pa
    op = SimpleNamespace(park_cursor=lambda **kw: None,
                         screenshot=lambda: (screens.append(1) if
                                             screens is not None else None)
                         or np.zeros((4, 4), dtype='uint8'))
    ctx = SimpleNamespace(controller=controller, cw_match=cw_match,
                          run_context=None,
                          screen_loader=screen_loader or SimpleNamespace(
                              get_screen=lambda name: None))
    ex = pa.PrepActionExecutor(op, ctx)
    # 槽位表种子(screen_loader 桩读不到建档 → 空表):op 内参数守卫按
    # 真执行器形状(备战栏 9 / 前排 4 / 后排 6)判合法域,空表会让一切
    # 合法槽位误炸——种子 = 机械 fixture 数据,非断言面。
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    ex._front_pts = [Point(i * 10, i * 10) for i in range(4)]
    ex._back_pts = [Point(i * 10, i * 10) for i in range(6)]
    return ex


# ============================================================ 执行器机械半:晶矿


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
    非本测试辖面。)"""
    monkeypatch.setattr('time.sleep', lambda _s: None)

    controller = _RecordingController()
    screens: list[int] = []
    ex = _make_executor(controller, screens)
    ex.execute(CwActionCollectOreParam(points=((12, 34), (56, 78))))
    assert [(p.x, p.y) for p in controller.clicks] == [(12, 34), (56, 78)]
    assert controller.drags == []   # 采晶矿不拖拽
    assert screens == []            # 零读屏(挑选归决策侧 kernel)
    # 逻辑态:按载荷精确摘晶矿(坐标匹配,非保守清空)——宿主 =
    # report_action_collect_ore_param 状态容器 spheres 精确摘除。
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_game_state import (
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
    # logic-rand-sampling 迭代:bench/level 前置守卫已登记,须观测方可摘除
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


# ============================================================ 逻辑态上报:覆盖完备


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(工具上报升格容器写后,本测覆盖循环会落 tool_*
    留证行;后清防外泄——全局缓冲被后续测试整池排水对账,残留行即假红)。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


def test_vocab_actions_all_have_logic_state_projection(
        _isolate_defect_buffer):
    """词表逻辑态覆盖测试(R9;动作 op 重组后宿主 = 上报函数族
    ``kernel/cw_action_report``,每动作恰一个具名函数——原聚合写口
    ``apply_prep_action_logic`` 随批退役)。

    覆盖面三集(登记面申报 = 函数族 docstring:有容器写动作一动作
    一文件,零写族集中 ``zero_writes``):
    - **容器写集**:CwActionSellBenchParam/CwActionSellDeployedParam/
      CwActionMoveUnitParam/CwActionLevelUpParam/CwActionCollectOreParam/
      CwActionOpenTomeParam/CwActionOpenBookcardParam/CwActionWearEquipParam
      ——供数状态容器上逐动作必产生容器写(write_seq 推进);
    - **工具容器写集**(tool-gain-report 迭代自零写族升格,机械执行直接
      上报写状态容器):冶金炉/特权赋予卡/拆装扳手/精密拆装扳手/员工投影仪/
      完美投影仪——逐动作面对相同入场态(equips 含该工具 + 目标件/穿戴
      面)必产生容器写;好运令牌除外(见零写集);
    - **合法零写集**:CwActionOpenBoxParam(R7 终结化)/CwActionLuckyTokenUse
      Param(判据面 fail-closed 永不准入,上报零写留证)。
    裁决注记:CwActionWearEquipParam 原在零写集(聚合口形态),上报
    函数族起穿戴 = 发出即记账 owned −1(已登记才减,执行侧效果并入
    上报),按新事实移入容器写集;工具六类原在零写集(零写占位),
    tool-gain-report 迭代升格容器写。函数名机械推导(snake 规约同
    test_action_report)。"""
    import re

    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel import cw_action_report as rpt
    from sr_od.application.currency_war.kernel.cw_game_state import (
        OreSight,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionFurnaceUseParam,
        CwActionLuckyTokenUseParam,
        CwActionOpenBookcardParam,
        CwActionPerfectProjectorUseParam,
        CwActionPrecisionWrenchUseParam,
        CwActionPrivilegeCardUseParam,
        CwActionStaffProjectorUseParam,
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
    # 供数状态容器:bench(2 unit+1 tome+1 bookcard+1 box)、front 1 人、gold/level/xp、晶矿
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
    # 动作会消耗件名(炉替换/特权变换/扳手回区)与穿戴面,覆盖测试按同一
    # 入场态逐个评估写行为;重播种 = 状态容器域 builder 同写入口(observe)。
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
    # 供数状态容器重播种(工具循环的消耗/置换不复原;穿戴分支依赖
    # owned 已登记、卖出分支依赖前排 1 号位有单位)。
    gs.observe(gs.equips, ['轮滑鞋'], sig=_sig)
    gs.observe(gs.deployed, _dvs([Unit(char_id='丙', star=1, equips=[])], []), sig=_sig)

    written: list = [
        CwActionSellBenchParam(bench_idx=0),
        CwActionSellDeployedParam(deployed_idx=0),
        CwActionMoveUnitParam(src_domain='bench', src_slot=1,
                              dst_domain='front', dst_slot=2),
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
    # 穿戴分支单独重播种(布尔契约前置:owned 已登记 + 目标角色已登记——前序
    # 卖出分支已消耗前排;与工具循环同款入场态纪律)。
    gs.observe(gs.equips, ['轮滑鞋'], sig=_sig)
    gs.observe(gs.deployed, _dvs([Unit(char_id='丙', star=1, equips=['轮滑鞋'])], []), sig=_sig)
    before = _seq()
    _report(gs, CwActionWearEquipParam(item_name='轮滑鞋', char_name='丙',
                                       row='front', slot=1))
    assert _seq() > before, 'CwActionWearEquipParam 应产生容器写'
    # 词表覆盖完备性:三集并集(含独立重播种的穿戴分支)覆盖 CW_ACTION_TYPES
    # 中非转场/非组合壳成员
    names = {c.__name__ for c in CW_ACTION_TYPES}
    covered = ({type(a).__name__ for a, _t in tools_written}
               | {type(a).__name__ for a in written}
               | {type(a).__name__ for a in zero}
               | {'CwActionWearEquipParam'})
    assert names >= covered   # 三集均为词表成员(不越词表)


# ============================================================ 执行器机械半 + 逻辑态:升级


def test_levelup_executes_single_click_per_frame(monkeypatch):
    """执行器半:一次 execute = 恰一次单击(零授权零循环;升 N 击 = N 帧)。
    金分支翻转 = action.cost 逻辑态直写(唯一写点
    report_action_level_up_param);执行缝金差链已整体退役——执行器
    不再计算/携带金差,回执 extra 无 gold_delta 键。
    建档纪律(terminal-fail-status 用户裁定:建档缺失零防御):按钮
    area 命中 = 每帧恰一击;缺失 = 取值直接使用,点击消费点自然异常
    (禁兜底坐标)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_prep_level_up_action as lvl_mod

    controller = _RecordingController()
    ex = _make_executor(controller)
    # 命中臂:area_center 命中「备战标识-购买经验」→ 每帧恰一击。
    monkeypatch.setattr(lvl_mod, 'area_center',
                        lambda ctx, name, screen_name='': Point(296, 860))
    ex.execute(CwActionLevelUpParam(cost=4))
    assert len(controller.clicks) == 1
    ex.execute(CwActionLevelUpParam(cost=4))
    assert len(controller.clicks) == 2   # 第二帧再击
    # 缺失臂:area 缺失 → 取值直接使用零检查,点击消费点自然异常
    # (None 坐标解引用即炸;零兜底坐标静默点击)。
    controller_miss = _DerefController()
    ex_miss = _make_executor(controller_miss)
    monkeypatch.setattr(lvl_mod, 'area_center',
                        lambda ctx, name, screen_name='': None)
    with pytest.raises(AttributeError):
        ex_miss.execute(CwActionLevelUpParam(cost=4))
    assert controller_miss.clicks == [], '点击消费点即炸,零点击(禁兜底坐标)'


def test_moveunit_slot_out_of_range_guard_assertion(monkeypatch):
    """MoveUnit 落位载荷越界直驱 = op 内守卫断言 AssertionError
    (terminal-fail-status QD 终裁:参数违法类校验收拢 op 内;旧
    DeployMove op 守卫随戊批并入,等价面 = 统一拖动 op 同款守卫)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war.operations.cw_op.cw_move_unit_action import (
        CwActionMoveUnitOp,
    )

    controller = _RecordingController()
    ex = _make_executor(controller)
    env = SimpleNamespace(executor=ex)
    action = CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                                   dst_domain='back', dst_slot=9)
    with pytest.raises(AssertionError) as ei:
        CwActionMoveUnitOp(SimpleNamespace(), action, env=env).run()
    assert '越界' in str(ei.value), '守卫断言消息语义保留'
    assert controller.drags == [], '零拖拽(参数违法不执行)'


def test_levelup_logic_state_advances_xp_level_and_gold():
    """逻辑态半:xp/level 跨门槛推进(推进算子单一源 = xp_apply_clicks,
    单击步长)+ 金分支 action.cost 直写(唯一写点,执行缝金差退役防双记)。
    gold 未观察 = 域级跳写(值留观察)。"""
    gs = game_state_of(None)
    gs.observe(gs.level, 3, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.xp, (10, 12), evidence='t', sig=_SIG_OBS)
    gs.observe(gs.gold, 100, evidence='t', sig=_SIG_OBS)
    report_action_level_up_param(gs, CwActionLevelUpParam(cost=4), sig=_SIG)
    exp_level, exp_cur = xp_apply_clicks(3, 10, 1)
    assert gs.level.value == exp_level
    assert gs.xp.value[0] == exp_cur
    assert gs.gold.value == 96   # 金分支直写:-action.cost
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


# ============================================================ 逻辑态上报:落位与卖出


def test_deploy_slot_plans_front_guarantee_and_slot_set():
    """落位策略测试(发射面;原 kernel assign/empty 测试迁 mandate_v1
    deploy_plan.deploy_slot_plans,断言语义不变):输出覆盖上场集(每件
    恰一 move)、槽位取自状态容器空槽集、前排保证(pref=back ∧ 前排全空 →
    真 front 先提/无 front 强转)。

    名字表达纪律:排偏好经注册表角色名获得(砂金=front,花火/爻光=
    back〔flex 派生 back〕),禁种子构造注入口。"""
    gs = game_state_of(None)   # 行域未观察 = 前后排全空
    # 状态容器形:落位策略输入 = 状态容器占席条目
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
    """CwActionMoveUnitParam 状态容器逻辑态(统一拖动落位载荷契约):bench 摘槽 +
    deployed 按载荷 (to_row, to_slot) 直落——目标槽有人 = 交换交互
    (被占位角色回源 bench 槽,其余占位不受波及,与换位动作同语义);
    载荷槽空 = 放置;源槽空 / 载荷槽跨排非法 = 陈旧提案零写。(docstring
    收窄:board 羁绊增量面本测未断言,不虚报。)"""
    gs = game_state_of(None)
    bc = BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1))
    slots: list[BenchSlot | None] = [None] * 9
    slots[2] = bc
    gs.observe(gs.bench, cw4_bview(slots), evidence='t', sig=_SIG_OBS)
    # move_unit 上报 fail-closed 面:deployed 未观察(视图 None)= 零写
    # 陈旧提案——与旧 deploy_move 口差异,本测先种子空板视图。
    gs.observe(gs.deployed, _dvs([], []), evidence='t', sig=_SIG_OBS)
    report_action_move_unit_param(gs, CwActionMoveUnitParam(src_domain='bench', src_slot=2,
                                  dst_domain='front', dst_slot=1),
                                 sig=_SIG)
    bench_after = bench_view_slots_of(gs)
    assert bench_after[2] is None or bench_after[2].kind == 'empty'
    dep = deployed_indexed_of_view(gs.deployed.value)
    # 落位 = 载荷直落(前排 1 号)
    assert dep[0] is not None and dep[0].char_id == '甲'
    # 目标槽有人 = 交换:甲拖到前排 1 号(乙0 占位)→ 甲落 1 号、乙0 回源
    # bench 槽 2、其余占位不受波及(与换位契约同语义)
    gs.observe(gs.bench, cw4_bview(list(slots)), evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed,
               _dvs([Unit(char_id=f'乙{i}', star=1, equips=[]) for i in range(4)],
                    [Unit(char_id=f'丙{i}', star=1, equips=[]) for i in range(6)]),
               evidence='t', sig=_SIG_OBS)
    report_action_move_unit_param(gs, CwActionMoveUnitParam(src_domain='bench', src_slot=2,
                                  dst_domain='front', dst_slot=1),
                                 sig=_SIG)
    dep = deployed_indexed_of_view(gs.deployed.value)
    assert dep[0] is not None and dep[0].char_id == '甲', \
        '交换语义:上场者落被占位的目标槽'
    assert dep[1].char_id == '乙1', '其余占位不受交换波及'
    swapped_back = bench_view_slots_of(gs)[2]
    assert swapped_back is not None and swapped_back.kind == 'unit' \
        and swapped_back.unit.char_id == '乙0', \
        '交换语义:被占位角色回发射者源 bench 槽'
    # 载荷槽空 = 放置:前排 1 号被乙占,载荷指 2 号空槽 → 照落 2 号,
    # 占位槽不受放置波及
    gs.observe(gs.bench, cw4_bview(list(slots)), evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id='乙', star=1, equips=[])], []),
               evidence='t', sig=_SIG_OBS)
    report_action_move_unit_param(gs, CwActionMoveUnitParam(src_domain='bench', src_slot=2,
                                  dst_domain='front', dst_slot=2),
                                 sig=_SIG)
    dep = deployed_indexed_of_view(gs.deployed.value)
    assert dep[1] is not None and dep[1].char_id == '甲'   # 载荷槽 = 表 1 位
    assert dep[0].char_id == '乙', '占位槽不受放置波及'
    # 源槽无件(bench_idx 越界空槽)= 陈旧提案,本口零写
    before = gs.write_seq
    report_action_move_unit_param(gs, CwActionMoveUnitParam(src_domain='bench', src_slot=5,
                                  dst_domain='front', dst_slot=2),
                                 sig=_SIG)
    assert gs.write_seq == before
    # 载荷槽跨排非法(前排无 5 号,front 5 号换算落表后段不符)= 零写
    # (源槽不摘,整笔零写)
    gs.observe(gs.bench, cw4_bview(list(slots)), evidence='t', sig=_SIG_OBS)
    report_action_move_unit_param(gs, CwActionMoveUnitParam(src_domain='bench', src_slot=2,
                                  dst_domain='front', dst_slot=5),
                                 sig=_SIG)
    _src2 = bench_view_slots_of(gs)[2]
    assert _src2 is not None and _src2.kind == 'unit' \
        and _src2.unit.char_id == '甲', '载荷槽非法也零写:源槽不摘'


def test_selldeployed_logic_state_clears_slot_and_recounts_board():
    """CwActionSellDeployedParam 状态容器逻辑态:deployed 摘槽;金域零写口径
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
    """备战卖出金账全链恰一次入账(统一观察对账迭代归因批出口①修模测试):
    历史形态 live 执行链对同一 CwActionSellBenchParam 先后跑执行缝
    (旧 apply_op_effect)与状态容器投影,两条分支各记一次 +refund → 逻辑金系统
    性虚高,下帧实读倒挂(journal 实证 −2,run_20260915_070645)。修后
    状态容器唯一写点 = 卖出上报函数,确认口(apply_confirm_effect,dict 确认
    族专用)对动作参数零入账(复返即红:确认口若再纳入动作分支即两条分支
    双记)。"""
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
    # (旧执行缝分支数据源 tracked 第二账已退役;确认口零入账判据由
    #  「动作参数零入账」本身承载,主域 bench 即唯一账。)
    refund = sell_refund(1, bench_char_cost(bc.unit))
    action = CwActionSellBenchParam(bench_idx=0)
    apply_confirm_effect(session, action)   # 确认口:动作参数零入账
    report_action_sell_bench_param(gs, action, sig=_SIG)
    assert gs.gold.value == 10 + refund, \
        f'卖出回金恰一次 +{refund}(两条分支双记 = 台账 −N 倒挂病灶)'


# ============================================================ 执行器机械半:穿戴 / 开卡 / 武装箱


def test_wear_equip_single_mechanical_drag_no_diff_verification(monkeypatch):
    """CwActionWearEquipParam 单次机械拖拽,无补救链重试(用户裁定:动作 op = 机械
    执行,判效/重试禁入动作层):发出即记账(emitted=True),拖后零
    落地判定,拖拽静默不生效由观察侧 reconcile 对账暴露。
    (monkeypatch time.sleep = 拖后固定等待空等,真机等待节奏非本测试辖面。)"""
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


def test_open_bookcard_executor_mechanical(monkeypatch):
    """书册卡机械半(状态容器槽位直点形态,open-actions-mechanical-pure
    design §2.1/§2.5 重推):槽号解析(None = gs 状态容器现算首件槽,双出口
    守卫)→ 备战栏-N 建档坐标单击 → 固定动画等待(等待家族单一源
    _OVERLAY_ANIM_WAIT_S;判效交下一帧观察)。识别读门随直点形态拆除
    ——旧「slot 对位不中/识别空 = 未发出」失败分支不复存在(状态容器陈旧
    「件不在」的治理归观察对账域);gs 装配 = 新守卫 slot=None 现算需要
    (design §2.5 既有用例补装条)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from one_dragon.base.geometry.rectangle import Rect

    monkeypatch.setattr(time, 'sleep', lambda s: None)   # 动画等待桩(零真实等待)

    class _Screen:
        area_list = [SimpleNamespace(
            area_name=f'备战栏-{i}',
            pc_rect=Rect(100 + i * 10, 845, 150 + i * 10, 979))
            for i in range(1, 10)]

    loader = SimpleNamespace(get_screen=lambda name: _Screen())
    session = cw4_session()
    gs = game_state_of(session)
    _sig = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty'), BenchSlot(kind='bookcard')]
        + [BenchSlot(kind='empty')] * 7, capacity=9), sig=_sig)
    cw_match = SimpleNamespace(session=session)

    # None 现算:状态容器首个 bookcard 槽(下标+1 = 槽2)→ 建档坐标单击。
    controller = _RecordingController()
    ex = _make_executor(controller, [], cw_match=cw_match,
                        screen_loader=loader)
    detail, emitted = ex._open_bookcard(CwActionOpenBookcardParam())
    assert emitted and '槽2' in detail, '现算首件槽显示显式槽号'
    assert [(p.x, p.y) for p in controller.clicks] == [(145, 912)], \
        '单击落备战栏建档坐标中心'
    assert len(controller.moves) == 1   # bug#1 缓解口径:先移后点
    assert gs.bench.value.slots[1].kind == 'empty', '开卡腾席落账'
    # 显式 slot:直驱建档坐标(点槽本体中心)。
    controller2 = _RecordingController()
    ex2 = _make_executor(controller2, [], cw_match=cw_match,
                         screen_loader=loader)
    detail2, emitted2 = ex2._open_bookcard(CwActionOpenBookcardParam(slot=5))
    assert emitted2 and '槽5' in detail2
    assert [(p.x, p.y) for p in controller2.clicks] == [(175, 912)]
    # None 现算双出口守卫(design §2.5):gs 缺席 / 状态容器无 bookcard 首槽
    # → 守卫断言响亮暴露零点击(参数面,非识别失败)。
    controller3 = _RecordingController()
    ex3 = _make_executor(controller3, [])   # cw_match=None → gs 缺席
    with pytest.raises(AssertionError):
        ex3._open_bookcard(CwActionOpenBookcardParam())
    assert controller3.clicks == [], '零点击(gs 缺席出口)'
    session4 = cw4_session()
    gs4 = game_state_of(session4)
    gs4.observe(gs4.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 9, capacity=9), sig=_sig)
    controller4 = _RecordingController()
    ex4 = _make_executor(controller4, [],
                         cw_match=SimpleNamespace(session=session4),
                         screen_loader=loader)
    with pytest.raises(AssertionError):
        ex4._open_bookcard(CwActionOpenBookcardParam())
    assert controller4.clicks == [], '零点击(状态容器无首件槽出口)'


def test_open_bookcard_logic_state_frees_slot():
    """开卡即腾席(状态容器版;原黑板 free_bench_slots +1 语义随投影退役):
    书册卡槽(状态容器 kind='bookcard',kind 细分批起不再统一降级 supply_box)
    经 CwActionOpenBookcardParam 腾席 = 槽 kind → empty——bench_free_slots
    派生 +1(状态容器读口单点),其余槽不动。降级口径(slot
    kind='supply_box')= 类型不符拒零写(防跨物误腾)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    session = cw4_session()
    gs = game_state_of(session)
    _sig = ChannelSig(family='obs', actor='cw4_seed',
                      mode='synthesized')
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                               equips=[])),
              BenchSlot(kind='bookcard')]
    _slots += [BenchSlot(kind='empty') for _ in range(7)]
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    before = bench_free_slots(gs)
    assert before == 7
    report_action_open_bookcard_param(
        gs, CwActionOpenBookcardParam(slot=2),
        sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
    assert gs.bench.value.slots[1].kind == 'empty'
    assert bench_free_slots(gs) == before + 1
    # 类型不符拒零写:supply_box 槽不是本动作的腾席对象(开箱 = OpenBox 辖)
    before_seq = gs.write_seq
    report_action_open_bookcard_param(
        gs, CwActionOpenBookcardParam(slot=2),
        sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
    assert gs.write_seq == before_seq   # 槽已 empty,陈旧提案零写


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
    # 终态契约 §2.7(零参 + 写槽):桩挂载 gs(决策输入 = 状态容器持有引用;
    # handler 先写 gs.box_card_names 槽再零参调 decide)。
    _sess = SimpleNamespace()
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(
        strategy=strategy, session=_sess, config=None,
        gs=game_state_of(_sess)))
    with pytest.raises(ValueError):
        op._decide_card_index(['甲', '乙'])


# ============================================================ 发射面装载


def test_levelup_emission_carries_cost_and_auth_basis():
    """发射面装载(CwActionLevelUpParam 粒度定案③口径,持久索引见模块头):cost = kernel
    xp_click_cost 现算(gs.level_up_cost 缺读时函数内回退
    XP_CLICK_COST_FALLBACK 折扣支,发射位零本地回退分支);auth_basis =
    触发键闭集('stay_gate'=带滞后升级 / 'natural'=无未完成目标自然
    升级——升级触发单判据三分派,11 号稿 §2,发射位 = entry
    备战第 4 步);route_tag 沿 Emitted.reason 透传
    (step3_levelup_batch:<tag>;动作对象 route_tag 由桥伴在
    decide_prep_frame 装载,发射位直跑不经桥 → reason 承载)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_box

    from sr_od.application.currency_war.kernel.cw_economy import (
        xp_click_cost,
    )
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        entry,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        session_scope as _ss,
    )

    st = {'gold': 80, 'level': 4, 'hp': 80, 'plane': 2, 'round_num': 2,
          'deploy_cap': 4, 'node': 'battle',
          'bench': [BenchSlot(kind='unit', unit=Unit(
              char_id='注册表外散件A', star=1))],
          'front_row': [Unit(char_id=f'注册表外散件{i}', star=2)
                        for i in range(4)]}
    sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                           v3_intention=IntentionState(),
                           active_strategies=[])
    gs = cw4_box(sess, **st)   # 挂 sess:emit 经 game_state_of(session) 解析同状态容器
    gs.observe(gs.node_pos, (2, 2), sig=ChannelSig(
        family='obs', actor='cw4_seed', mode='synthesized'))
    gs.node_hist_pos = (2, 1)
    _ss.handle_node_boundary(gs)   # plane2_started 置位(node_hist_pos 水位驱动)
    _ss.write_line_lock(gs, '希儿量子')   # 锁定线:未持有缺件 → 希儿 1★ 目标(3 费,带 (7,7))
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of as _state_of,
    )
    _state_of(gs).gold_ledger = 80   # 金位账面锚定(3.6 读数门:桥族种子不自带钉位)
    out = entry.emit(sess, None)
    lv = [e for e in out if isinstance(e.action, CwActionLevelUpParam)]
    assert lv, '构帧须命中带滞后触发(lv4 < 带下界 7)∧ 现金足(花后 ≥ 线)'
    gs_cost_view = cw4_box(gold=80, level=4, hp=30, plane=2,
                           round_num=2, level_up_cost=4)
    a = lv[0].action
    assert a.cost == xp_click_cost(gs_cost_view)   # 现算单一源(含回退支)
    assert a.auth_basis in ('stay_gate', 'natural')
    assert lv[0].reason.startswith('step3_levelup_batch:')
    # 整批击数字段随授权装载(一次买齐;批大小 = 门槛表差值折击数)
    assert a.clicks >= 1


def test_sellbench_emission_carries_channel_reason():
    """CwActionSellBenchParam 发射面通道记录装载:r9 争金归因证据层
    (决策行 form_ok 时序批 sibling 件;登记门单一源 =
    cw_vocab.SELL_BENCH_REASONS)。溢出清位臂(overflow_warning 短路
    return)CwActionSellBenchParam.reason = 通道键 m4_fuel_sell;记录非
    指令,资格单一源(sell_gate 装配 A)零触碰。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    # 状态容器形:MandateFrame 直构面 = 占席条目 + 行域 Unit
    deployed = [Unit(char_id=f'注册表外散件{i}', star=2)
                for i in range(4)]
    frame = mandate.MandateFrame(
        gold=80, level=4,
        bench=[BenchSlot(kind='unit', unit=Unit(
            char_id='注册表外散件A', star=1))],
        deployed=deployed, deploy_cap=4, node_type='battle',
        stop_flag=False, k_members=(), round_num=2, overflow_warning=True)
    gs = game_state_of(None)
    # 燃料资格面读状态容器(空板守卫读 deployed + bench 边际维),双状态容器预写
    gs.write_logic(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=Unit(
            char_id='注册表外散件A', star=1))]
        + [BenchSlot(kind='empty')] * 8, capacity=9),
        produced_by='T', sig=_SIG)
    gs.write_logic(gs.deployed, _dvs([
        Unit(char_id=f'注册表外散件{i}', star=2)
        for i in range(4)], []),
        produced_by='T', sig=_SIG)
    sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                           v3_intention=IntentionState(), active_strategies=[])
    out = mandate.run_mandate(frame, sess, state=gs)
    sb = [e for e in out if isinstance(e.action, CwActionSellBenchParam)]
    assert sb, '构帧须命中溢出清位臂(1★ 线外燃料 + overflow_warning)'
    assert sb[0].action.reason == 'm4_fuel_sell'
    # route_tag 载体 = Emitted.reason(桥伴装载;通道键单一词汇)
    assert sb[0].reason == 'm4_fuel_sell'


def test_bridge_recheck_context_uses_slot_table_indices(monkeypatch):
    """桥复检语境坐标测试(「bridge 复检语境容器下标化」行为半):
    ``decide_prep_frame`` 供给截断复检的 bench 占用集必须 = **定长槽位表
    下标**(动作参数坐标系,bench_idx 同系,cw_vocab 坐标契约节单一源)
    ——前部有洞帧按紧缩序(bench_entries_of)枚举下标供给会错杀后部
    占用槽的合法引用,发射被截空后状态副本不变 → 备战环「本帧无动作」
    无限交回(sim 多种子首局活锁实证,实机同链路同受害)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        bridge,
        entry,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        Emitted,
    )

    class _Cfg:
        ev_arm = 'full'

    session = SimpleNamespace()
    gs = game_state_of(session)
    # 前部两洞 + 槽3/槽5 占席(槽位信息位 = 数组下标+1);占用槽表下标
    # 集 = {2, 4},紧缩序枚举下标集 = {0, 1}——两坐标系此帧分叉。
    gs.write_logic(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 2
        + [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1)),
           BenchSlot(kind='empty'),
           BenchSlot(kind='unit', unit=Unit(char_id='乙', star=1))]
        + [BenchSlot(kind='empty')] * 4, capacity=9),
        produced_by='T', sig=_SIG)
    # 正半:引用占用槽表下标 4(乙)必须通过复检照发——错杀即本测试红。
    sell = CwActionSellBenchParam(bench_idx=4, reason='interest_prep')
    monkeypatch.setattr(entry, 'emit',
                        lambda *a, **k: [Emitted(sell, True, 'interest_prep')])
    assert bridge.decide_prep_frame(session, _Cfg()) == [sell]
    # 负半:真空槽引用(下标 0)照旧 fail-closed 截空——复检防线语义
    # 不因坐标修复放宽。
    ghost = CwActionSellBenchParam(bench_idx=0, reason='interest_prep')
    monkeypatch.setattr(entry, 'emit',
                        lambda *a, **k: [Emitted(ghost, True, 'interest_prep')])
    assert bridge.decide_prep_frame(session, _Cfg()) == []


def test_emission_resolves_container_index_fail_closed():
    """发射面状态容器下标解析(换算归属裁定,持久索引见模块头):bench
    域按紧缩位键(占席序 0 基)与状态容器槽位表枚举
    对位取下标;deployed 域按视图子表条目对位;失配 = None
    (fail-closed 跳过,禁猜位)。"""
    gs = game_state_of(None)
    # 槽位表构造 = 位置映射(槽 i = 列表下标 i)——槽 4(第 1 个占用槽)
    # 的件放列表下标 3。
    gs.write_logic(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 3
        + [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1))]
        + [BenchSlot(kind='empty')] * 5, capacity=9),
        produced_by='T', sig=_SIG)
    gs.write_logic(gs.deployed,
                   DeployedView(front_slots=[None, Unit(char_id='刃', star=1)],
                                back_slots=[]),
                   produced_by='T', sig=_SIG)
    assert mandate._bench_container_idx_by_compact(gs, 0) == 3   # 首占用槽
    assert mandate._bench_container_idx(
        gs, BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1))
    ) == 3
    assert mandate._bench_container_idx_by_compact(gs, 1) is None   # 无第 2 占用
    assert mandate._bench_container_idx_by_compact(gs, -1) is None  # 非法值
    assert mandate._deployed_container_idx(
        gs, Unit(char_id='刃', star=1)) \
        == 1   # front slot2 → 下标1(视图子表下标对位)
    # fail-closed = 视图子表条目失配;不在场 → None。
    assert mandate._deployed_container_idx(
        gs, Unit(char_id='不在场', star=1)) is None
    # 生产桥互逆测试(换算函数族退役,动作坐标系工作副本桥 =
    # deployed_indexed_of_view/deployed_view_of_indexed,保留裁定在案):
    # 视图 → 定长 10 表 → 视图逐位等价(前排原样 + 后排 1-6 位;7-9 扩展
    # 格经 orig 参继承,不截断——工作副本往返不得丢容量)。front 1-4 /
    # back 1-6 值域同步钉死。
    view = DeployedView(
        front_slots=[Unit(char_id='甲', star=1), None,
                     Unit(char_id='乙', star=2), None],
        back_slots=[None, Unit(char_id='丙', star=1), None, None,
                    Unit(char_id='丁', star=3), None,
                    Unit(char_id='扩展七格', star=1)])
    dep = deployed_indexed_of_view(view)
    assert len(dep) == 10
    assert [(u.char_id if u is not None else None) for u in dep] == [
        '甲', None, '乙', None,
        None, '丙', None, None, '丁', None], \
        'front 1-4 直取 + back 1-6 位(7-9 扩展格不入动作坐标系)'
    rebuilt = deployed_view_of_indexed(dep, view)
    assert rebuilt.front_slots == view.front_slots
    assert rebuilt.back_slots == view.back_slots, \
        'orig 参继承原容量(往返等价,7-9 扩展格不丢)'


# ============================================================ 卡片臂 / 箱典籍臂发射


def _emit_with_bench(bench_slots: list[BenchSlot]):
    """观测 bench 后调 entry.emit(臂① 早返回面;session = cw4 每局全新创建)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry
    session = cw4_session()
    gs = game_state_of(session)
    _slots = list(bench_slots)
    _slots += [BenchSlot(kind='empty')] * (9 - len(_slots))
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9),
               sig=ChannelSig(family='obs', actor='CwScreenPrep',
                              mode='read'))
    return entry.emit(session, None)


def test_entry_card_arms_emit_from_bench_kind():
    """用户裁定 2026-09-19(开卡时机归策略器):状态容器 bench 槽位 kind
    'bookcard' → entry ① 卡片臂发射 CwActionOpenBookcardParam(物理槽号
    = 下标 +1);优先序卡先于箱(旧「入口清场先于观察」全局序)。
    (历史注:「trial_card」臂随幻影机制撤销——备战栏发光金卡 = 动画帧
    误判,用户定论 2026-09-19,禁再建模。)"""
    # bookcard 槽 → OpenBookcard(slot=下标+1)
    out = _emit_with_bench([BenchSlot(kind='unit', unit=Unit(
        char_id='甲', star=1, equips=[])),
        BenchSlot(kind='bookcard')])
    assert len(out) == 1 and isinstance(out[0].action, CwActionOpenBookcardParam)
    assert out[0].action.slot == 2
    # 优先序:卡先于箱(旧「入口清场先于观察」全局序)
    out = _emit_with_bench([BenchSlot(kind='bookcard'),
                            BenchSlot(kind='supply_box')])
    assert isinstance(out[0].action, CwActionOpenBookcardParam)


def test_entry_box_tome_arms_read_benchview_kind():
    """回归测试:开箱/开典籍臂与卡片臂同读状态容器 BenchView.slots kind
    (占位件三分类 kind 直读,单一形状无换形路)。本测试钉死 box/tome 臂
    在真 kind 载荷上照常命中。"""
    out = _emit_with_bench([BenchSlot(kind='supply_box')])
    assert len(out) == 1
    assert isinstance(out[0].action, CwActionOpenBoxParam)
    assert out[0].action.slot == 1
    slots = [BenchSlot(kind='empty')] * 9
    slots[3] = BenchSlot(kind='tome')
    out = _emit_with_bench(slots)
    assert len(out) == 1 and isinstance(out[0].action, CwActionOpenTomeParam)
    assert out[0].action.slot == 4


# ============================================================ 出战动作 op(点击序列/免战)

#: 识别命中表的键 = (画面名, area 名)(op 桩 round_by_find_area 的判定面)。
_HIT_BTN = ('货币战争-备战', '按钮-出战')
_HIT_SKIP = ('货币战争-备战', '按钮-跳过')
_HIT_NOTFULL = ('货币战争-未达上限警告', '标识-未达上限警告')
_HIT_NOFRONT = ('货币战争-提示-前台无角色', '标识-无角色提示')

#: area_center 桩返回表:每个交互 area 一个定值点(区分点击对象)。
_AREA_POINTS = {
    _HIT_BTN: Point(100, 200),
    ('货币战争-备战-开商店', '按钮-出战'): Point(100, 200),
    _HIT_SKIP: Point(110, 200),
    ('货币战争-未达上限警告', '勾选-本局不再提示'): Point(300, 400),
    ('货币战争-未达上限警告', '按钮-确认'): Point(301, 401),
    ('货币战争-提示-前台无角色', '按钮-确认'): Point(302, 402),
}


def _sb_patch(monkeypatch) -> None:
    """出战 op 模块桩:area_center 命中表 + 模块内 ``time`` 替身
    (POST_CLICK_WAIT 弹窗渲染窗空等——裸 ``import time`` 直睡,
    fast_sleep() 不传 op 够不着,测试换模块替身;screen_info 坐标解析
    本身不属本测试面,本测试只校验 op 的决策/点击序列)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_start_battle_action as _sba,
    )
    monkeypatch.setattr(
        _sba, 'area_center',
        lambda ctx, name, screen_name=_sba.SCREEN_NAME:
        _AREA_POINTS.get((screen_name, name)))
    monkeypatch.setattr(_sba, 'time', _NoSleepTime())


def _sb_stub_op(hits: set[tuple[str, str]]):
    """op 桩:screenshot 恒同帧对象,round_by_find_area 按命中表演。"""

    def _find(_screen, screen_name: str, area_name: str, **_kw):
        return SimpleNamespace(is_success=(screen_name, area_name) in hits)

    return SimpleNamespace(screenshot=lambda: object(),
                           round_by_find_area=_find,
                           save_screenshot=lambda prefix='': 'stub.png')


def _sb_executor(controller: _RecordingController, stub_op,
                 cw_match=None):
    """执行器桩宿主(出战 op 专用:分派包络分支需真 executor 容纳
    last_launch_ok/last_detail 旁路写点)。"""
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor
    ctx = SimpleNamespace(controller=controller, cw_match=cw_match,
                          run_context=None,
                          screen_loader=SimpleNamespace(
                              get_screen=lambda name: None))
    return PrepActionExecutor(stub_op, ctx)


def _sb_env(ex):
    return SimpleNamespace(op=ex._op, match=None, config=None,
                           executor=ex, detail='', emitted=False,
                           skip_substate=False)


def test_start_battle_click_sequence_and_envelope(monkeypatch):
    """已登记例外(点击序列语义)+ 三条弹窗路径 + 包络分支:

    - 常规帧:出战一次单击 → True(detail = 已点击无弹窗);零验证
      (无轮询/重试面,单击即完成交回);
    - 未达上限帧:勾选+确认两击后完成(勾选幂等,ADR-0136 行为对齐);
    - 前台无角色帧:确认一击后完成;
    - 找不到按钮:两屏查空 → False + 「未执行:找不到按钮」上报 + 零点击
      (交回外循环重判,不炸);
    - 包络分支:经注册表分派写 ``executor.last_launch_ok`` 旁路(点击序列
      已执行语义)与机械摘要 ``last_detail``,执行缝金差恒 0,薄委托
      替身函数的接缝(stub seam)返回序保持原 (ok, detail)。"""
    from test.harness.fixture_controller import fast_sleep

    from sr_od.application.currency_war.operations.cw_op.cw_start_battle_action import (
        CwActionStartBattleOp as _SBO,
    )
    _sb_patch(monkeypatch)

    def _make(ex):
        env = _sb_env(ex)
        return _SBO(SimpleNamespace(), CwActionStartBattleParam(), env=env), env

    ctl = _RecordingController()
    ex = _sb_executor(ctl, _sb_stub_op({_HIT_BTN}))
    op, env = _make(ex)
    # 常规帧:无弹窗(直调路径 status 走 round 结果;last_detail 是 runner
    # 包装写点,包络分支段另验)
    with fast_sleep():
        result = op.run()
    assert result.is_success is True
    assert ctl.clicks == [_AREA_POINTS[_HIT_BTN]]
    assert '出战已点击' in result.status and '无弹窗' in result.status
    # 未达上限帧:勾选 + 确认
    ctl = _RecordingController()
    ex = _sb_executor(ctl, _sb_stub_op({_HIT_BTN, _HIT_NOTFULL}))
    op, env = _make(ex)
    with fast_sleep():
        result = op.run()
    assert result.is_success is True
    assert ctl.clicks == [_AREA_POINTS[_HIT_BTN],
                          _AREA_POINTS[('货币战争-未达上限警告',
                                        '勾选-本局不再提示')],
                          _AREA_POINTS[('货币战争-未达上限警告',
                                        '按钮-确认')]]
    assert '未达上限警告:勾选+确认' in result.status
    assert result.is_success is True and env.skip_substate is False
    # 前台无角色帧:确认
    ctl = _RecordingController()
    ex = _sb_executor(ctl, _sb_stub_op({_HIT_BTN, _HIT_NOFRONT}))
    op, env = _make(ex)
    with fast_sleep():
        result = op.run()
    assert result.is_success is True
    assert ctl.clicks == [_AREA_POINTS[_HIT_BTN],
                          _AREA_POINTS[('货币战争-提示-前台无角色',
                                        '按钮-确认')]]
    assert '前台无角色提示:确认' in result.status
    # 找不到按钮:未执行上报 + 零点击
    ctl = _RecordingController()
    ex = _sb_executor(ctl, _sb_stub_op(set()))
    op, env = _make(ex)
    with fast_sleep():
        result = op.run()
    assert result.is_success is False
    assert result.status == '未执行:找不到按钮'
    assert ctl.clicks == []
    # 包络分支:注册表分派路径的旁路写点(点击序列已执行语义)
    ctl = _RecordingController()
    ex = _sb_executor(ctl, _sb_stub_op({_HIT_BTN}))
    with fast_sleep():
        ex.execute(CwActionStartBattleParam())
    assert ex.last_launch_ok is True
    assert '出战已点击' in ex.last_detail
    # 薄委托替身函数接缝:返回序保持原 (ok, detail)
    assert ex._start_battle()[0] is True


def test_start_battle_skip_substate_reported_not_consumed(monkeypatch):
    """免战子态上报测试(T-286):出战 miss + 「按钮-跳过」命中 → 点跳过
    坐标 + env.skip_substate True;递减本体 = op 自上报(行为测试见免战牌
    递减测试),op 直调层零多余容器写。"""
    from test.harness.fixture_controller import fast_sleep

    from sr_od.application.currency_war.operations.cw_op.cw_start_battle_action import (
        CwActionStartBattleOp as _SBO,
    )
    _sb_patch(monkeypatch)
    ctl = _RecordingController()
    ex = _sb_executor(ctl, _sb_stub_op({_HIT_SKIP}))
    env = _sb_env(ex)
    op = _SBO(SimpleNamespace(), CwActionStartBattleParam(), env=env)
    with fast_sleep():
        result = op.run()
    assert result.is_success is True
    assert env.skip_substate is True
    assert ctl.clicks == [_AREA_POINTS[_HIT_SKIP]]
    assert '出战已点击' in result.status


def test_freeze_card_decrement_via_report_path(monkeypatch):
    """免战牌递减经 op 自上报测试(T-286;接入调用):PrepActionExecutor
    .execute(跳过型 CwActionStartBattleParam)→ op 自上报
    report_action_start_battle_param 在 session effects 递减 remaining_uses
    (上报时递减);常规出战零递减;未登记(登记面缺位)零动作不炸。"""
    from test.harness.fixture_controller import fast_sleep

    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EFFECTS,
    )
    _sb_patch(monkeypatch)
    # 跳过型:登记免战牌 → 经包络执行 → 递减 2→1
    sess = SimpleNamespace()
    gs = game_state_of(sess)
    gs.effects.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_key=None)
    ex = _sb_executor(_RecordingController(), _sb_stub_op({_HIT_SKIP}),
                      cw_match=SimpleNamespace(session=sess))
    with fast_sleep():
        ex.execute(CwActionStartBattleParam())
    assert gs.effects.first(STRATEGY_EFFECTS['免战牌'].id).remaining_uses == 1
    # 常规出战(非跳过):零递减
    sess2 = SimpleNamespace()
    bs2 = game_state_of(sess2)
    bs2.effects.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_key=None)
    ex2 = _sb_executor(_RecordingController(), _sb_stub_op({_HIT_BTN}),
                       cw_match=SimpleNamespace(session=sess2))
    with fast_sleep():
        ex2.execute(CwActionStartBattleParam())
    assert bs2.effects.first(
        STRATEGY_EFFECTS['免战牌'].id).remaining_uses == 2
    # 未登记:零动作不炸(递减调用点与登记面解耦;execute 无返回契约,
    # 不抛 = 链路完整)
    sess3 = SimpleNamespace()
    ex3 = _sb_executor(_RecordingController(), _sb_stub_op({_HIT_SKIP}),
                       cw_match=SimpleNamespace(session=sess3))
    with fast_sleep():
        ex3.execute(CwActionStartBattleParam())
    assert ex3.last_launch_ok is True
