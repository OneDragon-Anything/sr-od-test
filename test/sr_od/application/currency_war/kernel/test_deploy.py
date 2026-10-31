"""部署与换人域测试(机制主题文件;部署决策 → 载荷执行 → 写序契约全链)。

被测机制(按节;设计出处见各节 docstring):
- **部署围栏与占槽物品防线**:占位件(kind ∈ tome/bookcard/supply_box)
  恒 held、拒因 ``item_slot``,先于一切围栏/cap 判定被剔除(benchchar-
  retirement P4 容器槽位 kind 口);
- **板满门三个测试**(事故 match_g_20260918_023823,定谳见
  .debug/temp/incidents/20260918-reconcile/rootcause-reopen.md 案一):
  部署输入改容器现读 + 显式板满门,拒因 ``deploy_cap_full`` 帧级去重;
- **落位策略三级排路由**:comp 站位覆盖 > 注册表派生 > back 兜底;
  后排槽位上限 = back_layout 现值(P2 遗留分歧消除);
- **必需件语义**(判据必要条件支配论证;sim n1000 s91700 两失败局):
  required 成员 cap 竞争首桶序;
- **残余补部署守卫**(P24 结构支配定理,零自由参数):dup 剔除 /
  cap 满停 / 两排皆满停 / cap=None 不设门 + 配方底线门 kernel 直测;
- **载荷与执行语义**(P2 拖拽语义落码):(to_row, to_slot) 直落
  反「首空」、目标槽有人 = 交换(写侧/执行链/sim 三面同源);
- **动作上报单写写序**(合卷契约):一次语义变更 = 恰一次 deployed 写;
  动态容量布局真值辖载荷校验。

(换入臂/双轨对锁期换入通道/发射门三轴测试节已随部署统一批丁丁收编删除:
kernel swap 机器与三轴门退役,场上去留 = 统一部署搜索定型单属——
unified-deploy-order §2.7/§4;残余补部署/配方底线门测试随七桶选人
退役批次处置。)
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_comp,
    cw4_gs,
    cw4_session,
)

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
    report_action_sell_deployed_param,
    report_action_swap_deploy_param,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    bench_view_slots_of,
    deployed_indexed_of_view,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    CwActionSellDeployedParam,
    CwActionSwapDeployParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_deploy_move_action import (
    CwActionDeployMoveOp,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    deploy_row_pref,
    deploy_slot_plans,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='CwScreenPrep')


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    """测试卫生:主域种子经 observe 覆盖开局种子(logic_rand 通道)会产
    预期内 logic_rand_outcome 行入进程级缓冲——前后双清,防跨用例顺序
    依赖红(同 test_tracked_slot_star_guard / test_effect_inventory
    同款排水纪律)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
    )
    consume_defect_sink()
    yield
    consume_defect_sink()


# (围栏与占槽物品防线/板满门/必需件 cap 竞争测试节已随部署统一批丁丁批
#  收编删除:七桶选人族(select_deployments)与 _deployable/_emit_
#  deploy_moves/_deploy_cap_full_gate 随选人退役,拒因闭集
#  (item_slot/deploy_cap_full/deploy_emit_held_*)停产——unified-
#  deploy-order §2/§4;占位件不入目标板 = 搜索段 0 剔除,板满帧部署
#  由差分执行器交换交互承载,覆盖面归 test_deploy_search.py。)
# ============================================================ 落位策略三级排路由 + back_layout 槽上限


def _bs(slot: int, char_id: str) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=1))


def test_comp_position_override_beats_registry_pref() -> None:
    """comp char_positions 覆盖注册表:万敌注册表 flex(派生 back),
    「万敌单C」覆盖为 front → 落位排 = front(逐件路由直接断言 +
    落位计划端到端各一分支)。"""
    comp = get_comp('万敌单C')
    assert comp is not None and comp.char_positions.get('万敌') == 'front', \
        '注册表前置自检:万敌单C 带 char_positions 覆盖'
    assert deploy_row_pref('万敌', None) == 'back', \
        '无 comp 覆盖时:flex 派生 back(③兜底前先走②注册表)'
    assert deploy_row_pref('万敌', comp) == 'front', \
        'comp 覆盖压过注册表派生(①>②)'

    gs = game_state_of(None)   # 行域全空:两排都有空,路由无 fallback 干扰
    bench = [_bs(1, '万敌')]
    moves = deploy_slot_plans(bench, [0], comp, gs)
    assert moves[0][1] == 'front', \
        f'落位计划按覆盖排路由,实得 {moves[0]!r}'


def test_registry_front_char_seats_front_when_front_has_room() -> None:
    """注册表前排角色(开拓者·记忆,position_pref='front')在前排有空时
    被落位策略排到前排——旧链路恒按后排,本测试钉住派生真实生效。"""
    gs = game_state_of(None)
    bench = [_bs(1, '开拓者·记忆'),
             _bs(2, '花火')]   # 花火 = 注册表 back(对照组)
    moves = deploy_slot_plans(bench, [0, 1], None, gs)
    assert moves[0][:2] == (0, 'front'), \
        f'注册表前排角色落前排,实得 {moves[0]!r}'
    assert moves[1][:2] == (1, 'back'), '注册表后排角色照旧落后排'


def test_unregistered_name_falls_back_to_back() -> None:
    """③兜底:注册表未登记名(识别对齐缺失形态)按后排处理(fail 向
    后排 = 与旧缺省同侧,不因识别缺失翻到前排)。前排预置占位避开
    前排保证强转(前排全空 → back 件被强转前排,是另一条策略规则的
    正确行为,不混入本测试)。"""
    assert deploy_row_pref('未注册角色名', None) == 'back'
    gs = game_state_of(None)
    gs.observe(gs.deployed, _dvs([Unit(char_id='砂金', star=1, equips=[])], []),
               evidence='t', sig=_SIG_OBS)
    bench = [_bs(1, '未注册角色名')]
    moves = deploy_slot_plans(bench, [0], None, gs)
    assert moves[0][1] == 'back', '未注册名兜底后排'


def test_back_slots_capped_by_back_layout_baseline() -> None:
    """back_layout 基线 6:8 个后排候选(前排被占满)→ 后排槽号至多 6,
    永不发射 7-9 号槽(执行面 6 槽,越界载荷 = 静默分歧的消除面)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_layout, 6, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id=f'前{i}', star=1, equips=[])
                for i in range(1, 5)], []), evidence='t', sig=_SIG_OBS)
    bench = [_bs(i + 1, '花火') for i in range(8)]
    moves = deploy_slot_plans(bench, list(range(8)), None, gs)
    back_slots = [slot for _bi, row, slot in moves if row == 'back']
    assert back_slots == [1, 2, 3, 4, 5, 6], \
        f'后排空槽按 back_layout 现值派生,实得 {back_slots!r}'


def test_back_layout_extended_value_extends_back_slots() -> None:
    """back_layout 扩展局(宝钻 8):后排空槽随实值到 8 号——执行面/表
    随实值,扩展槽在扩展局可达(上限随实值,非恒 6)。前排占满避开
    前排保证强转(不混入本测试)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_layout, 8, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id=f'前{i}', star=1, equips=[])
                for i in range(1, 5)], []), evidence='t', sig=_SIG_OBS)
    bench = [_bs(i + 1, '花火') for i in range(8)]
    moves = deploy_slot_plans(bench, list(range(8)), None, gs)
    back_slots = [slot for _bi, row, slot in moves if row == 'back']
    assert back_slots == [1, 2, 3, 4, 5, 6, 7, 8], \
        f'扩展局后排空槽达 8 号,实得 {back_slots!r}'


# (残余补部署守卫(P24)与配方底线门/仙舟供给谓词测试节已随部署统一
#  批丁丁批收编删除:七桶选人族与 recipe_floor_holds/xianzhou_supply_
#  exists/residual_fill_plan 随选人退役——unified-deploy-order §2/§4;
#  空槽补位/围栏语义由统一部署搜索 + 差分执行器单测承载
#  (test_deploy_search.py/test_deploy_diff.py)。)
# ============================================================ 载荷与执行语义(P2 拖拽语义落码)


def _seed_main(gs: GameState, *,
               bench_units: list[tuple[str, int]] | None = None,
               dep_units: list[tuple[str, int, str, int]] | None = None
               ) -> None:
    """主域账面种子(tracked 第二账退役,执行链测试种子/断言全在
    主域):bench_units = [(名, 星)] 紧凑落位;dep_units = [(排, 槽号,
    名, 星)] 载荷落位。"""
    from sr_od.application.currency_war.kernel.cw_game_state import BenchView
    if bench_units is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench_units]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if dep_units is not None:
        front: list[Unit | None] = [None] * 4
        back: list[Unit | None] = [None] * 6
        for row, slot_no, name, star in dep_units:
            (front if row == 'front' else back)[slot_no - 1] = \
                Unit(char_id=name, star=star)
        gs.observe(gs.deployed,
                   DeployedView(front_slots=front, back_slots=back),
                   sig=_SIG_OBS)


def _gs(*, bench: list[BenchSlot | None] | None = None,
        front: list[Unit] | None = None,
        back: list[Unit] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        from sr_od.application.currency_war.kernel.cw_game_state import (
            BenchView,
        )
        slots = list(bench) + [BenchSlot(kind='empty')] * (9 - len(bench))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if front is not None or back is not None:
        gs.observe(gs.deployed, _dvs(list(front or []),
                                     list(back or [])), sig=_SIG_OBS)
    return gs


def _unit(cid: str, slot: int, star: int = 1) -> Unit:
    return Unit(char_id=cid, star=star, equips=[])


def test_write_side_lands_at_payload_slot_not_first_empty():
    """反「首空」证据:前排 2 号空、载荷指 3 号 → 落 3 号,2 号保持空
    (首空位现读若在,会落 2 号)。"""
    gs = _gs(bench=[BenchSlot(kind='unit', unit=_unit('甲', 1))],
             front=[_unit('乙', 1)])
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=3,
                                    faction=''),
        sig=_SIG_LOGIC)
    assert out.applied, f'应按载荷直落,实得 {out.reason!r}'
    dep = deployed_indexed_of_view(gs.deployed.value)
    assert dep[2] is not None and dep[2].char_id == '甲', \
        '落位 = 载荷指定槽(表下标 2)'
    assert dep[1] is None, '更低位的空槽(2 号)不被静默填充(禁首空位现读)'
    _s0 = bench_view_slots_of(gs)[0]
    assert _s0 is None or _s0.kind == 'empty', '源槽摘除'


def test_write_side_rejects_invalid_payload_slot_zero_write():
    """载荷槽非法(前排无 5 号 / 后排 7 号越出定长表)= 零写,源槽不摘
    (report 静态域拒绝 = 战斗链边界载体的陈旧化治理;执行层唯一失败
    形态 = 拖拽未生效,拒绝面只在载荷静态域)。"""
    gs = _gs(bench=[BenchSlot(kind='unit', unit=_unit('甲', 1))],
             front=[_unit('乙', 1)])
    for row, slot in (('front', 5), ('back', 7)):
        before = gs.write_seq
        out = report_action_deploy_move_param(
            gs, CwActionDeployMoveParam(bench_idx=0, to_row=row, to_slot=slot,
                                        faction=''),
            sig=_SIG_LOGIC)
        assert not out.applied and out.reason.startswith('to_slot_invalid')
        assert gs.write_seq == before, '载荷槽非法 = 整笔零写'


def _deploy_op_env(session: object, drags: list[dict]):
    """DeployMoveOp 离线执行环境(坐标注入;drag_to kwargs 全录)。"""
    from sr_od.application.currency_war import prep_actions as pa
    controller = type('_Ctl', (), {
        'mouse_move': lambda self, p: None,
        'drag_to': lambda self, **kw: drags.append(kw),
    })()
    sl = type('_SL', (), {'get_screen': lambda self, n: None})()
    op = type('_Op', (), {
        'screenshot': staticmethod(lambda: None),
        'park_cursor': staticmethod(lambda **kw: None),
        'ctx': type('_Ctx', (), {
            'controller': controller,
            'cw_match': (None if session is None
                         else type('_M', (), {'session': session})()),
            'run_context': None,
            'screen_loader': sl,
        })(),
    })()
    ctx = op.ctx
    ex = pa.PrepActionExecutor(op, ctx)
    ex._bench_pts = [Point(300, 800)] * 9
    ex._front_pts = [Point(300 + i * 140, 400) for i in range(4)]
    ex._back_pts = [Point(300 + i * 140, 620) for i in range(6)]
    env = pa.PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    return env


def test_executor_drag_point_and_main_domain_lands_at_payload_slot(
        monkeypatch: pytest.MonkeyPatch):
    """执行链同源测试:载荷 (back, 3) → 拖点 = 后排 area 序 3−1;
    主域 deployed 落位 = 载荷槽子表下标(与容器写侧同式;
    tracked 同步分支退役,op 自上报单点写主域)。
    后排 1 号已有占位乙(更低位占用不影响),载荷槽 3 空 = 放置。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    session = StrategySession()
    gs = game_state_of(session)
    _seed_main(gs, bench_units=[('甲', 1)],
               dep_units=[('back', 1, '乙', 1)])
    drags: list[dict] = []
    env = _deploy_op_env(session, drags)
    action = CwActionDeployMoveParam(bench_idx=0, to_row='back', to_slot=3,
                                     faction='')
    ok = CwActionDeployMoveOp(env.op.ctx, action, env=env).run()
    assert ok.is_success, '载荷槽合法 = 机械发出(占位只看载荷槽,不拒)'
    assert len(drags) == 1 and drags[0]['end'] == env.executor._back_pts[2], \
        '拖点 = 载荷槽 area 序(to_slot−1),与写侧同源'
    _dep_after = gs.deployed.value
    assert _dep_after.back_slots[2] is not None \
        and _dep_after.back_slots[2].char_id == '甲', \
        '主域落载荷槽(位置 = 子表下标,拖点同源)'
    assert _dep_after.back_slots[0].char_id == '乙', \
        '既有占位不受放置波及(禁静默换槽)'
    assert gs.bench.value.slots[0].kind == 'empty', 'bench 侧摘除照旧'


def test_executor_occupied_target_swaps_without_rejection(
        monkeypatch: pytest.MonkeyPatch):
    """拖拽语义:载荷槽有人 = 交换交互——执行层不判断占位、不拒
    (round_success 照常发出);主域镜像(自上报):上场者落载荷槽、
    被占位者回源 bench 槽。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    session = StrategySession()
    gs = game_state_of(session)
    _seed_main(gs, bench_units=[('甲', 1)],
               dep_units=[('front', 2, '乙', 2)])
    drags: list[dict] = []
    env = _deploy_op_env(session, drags)
    action = CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=2,
                                     faction='')
    ok = CwActionDeployMoveOp(env.op.ctx, action, env=env).run()
    assert ok.is_success, '目标槽有人 = 交换交互,不视为异常、不拒'
    assert gs.deployed.value.front_slots[1].char_id == '甲', \
        '上场者落被占位载荷槽'
    _src = gs.bench.value.slots[0]
    assert _src is not None and _src.kind == 'unit' \
        and _src.unit.char_id == '乙', \
        '被占位者回发射者源 bench 槽(交换契约,装备随单位对象)'


def test_executor_rejects_slot_beyond_screen_points_no_drag(
        monkeypatch: pytest.MonkeyPatch):
    """载荷槽越出画面槽位数(back 7 > 6 槽)= 参数违法,op 内守卫断言
    AssertionError(terminal-fail-status QD 终裁;消息语义保留),零拖拽
    零主域写。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    session = StrategySession()
    gs = game_state_of(session)
    _seed_main(gs, bench_units=[('甲', 1)])
    drags: list[dict] = []
    env = _deploy_op_env(session, drags)
    action = CwActionDeployMoveParam(bench_idx=0, to_row='back', to_slot=7,
                                     faction='')
    with pytest.raises(AssertionError) as ei:
        CwActionDeployMoveOp(env.op.ctx, action, env=env).run()
    assert '落位载荷越界' in str(ei.value), '守卫断言消息语义保留'
    assert drags == [], '零拖拽(参数违法不执行)'
    assert gs.bench.value.slots[0].kind == 'unit', '主域整笔未写'


def test_sim_applies_occupied_target_as_swap():
    """部署上报(动作分支单一源)对「目标槽有人」按交换建模:上场者落
    载荷槽、被占位角色回发射者源 bench 槽(经上报函数,零私有占位规则)。"""
    gs = _gs(bench=[BenchSlot(kind='unit', unit=_unit('甲', 1))],
             front=[_unit('乙', 1)])
    report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=1,
                                    faction=''),
        _SIG_LOGIC)
    assert gs.deployed.value.front_slots[0].char_id == '甲', '上场者落载荷槽'
    slot = gs.bench.value.slots[0]
    assert slot.kind == 'unit' and slot.unit.char_id == '乙', \
        '被占位角色回源 bench 槽(交换语义,非占位拒绝)'


def test_sim_applies_empty_target_as_place():
    """对照分支:载荷槽空 = 放置(上报函数与写侧同一转移函数)。"""
    gs = _gs(bench=[BenchSlot(kind='unit', unit=_unit('甲', 1))],
             front=[], back=[])
    report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='back', to_slot=4,
                                    faction=''),
        _SIG_LOGIC)
    assert gs.deployed.value.back_slots[3].char_id == '甲', '空槽 = 放置(载荷槽 4)'


# ============================================================ 动作上报单写写序(合卷契约)


def _u(cid: str, star: int = 1, equips: list[str] | None = None) -> Unit:
    return Unit(char_id=cid, star=star, equips=list(equips or []))


def _gs_with(view: DeployedView, bench: list[BenchSlot] | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = list(bench or []) + [BenchSlot(kind='empty')] * (
        BENCH_CAPACITY_DEFAULT - len(bench or []))
    gs.observe(gs.bench, BenchView(slots=slots,
                                   capacity=BENCH_CAPACITY_DEFAULT),
               sig=_SIG_OBS)
    gs.observe(gs.deployed, view, sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    return gs


_ORIG_WRITES = (GameState.write_logic, GameState.write_logic_rand,
                GameState.observe)


class _WriteRecorder:
    """容器写口记录器(单写写序断言面:写时刻按「target 即该名当前
    Field 实例」解析字段名——Field 帧替换语义下写后实例即换,身份表
    只能在写时刻对位;logic/logic_rand/observe 三写口全记)。"""

    def __init__(self, gs: GameState) -> None:
        self.gs = gs
        self.rows: list[str] = []   # 字段名序列(写序)

    def __enter__(self) -> _WriteRecorder:
        rec = self

        def _wrap(orig):
            def _w(s, target, value, **kw):
                name = next((n for n in dir(s)
                             if getattr(s, n, None) is target), '?')
                rec.rows.append(name)
                return orig(s, target, value, **kw)
            return _w

        GameState.write_logic = _wrap(_ORIG_WRITES[0])
        GameState.write_logic_rand = _wrap(_ORIG_WRITES[1])
        GameState.observe = _wrap(_ORIG_WRITES[2])
        return self

    def __exit__(self, *exc) -> None:
        (GameState.write_logic, GameState.write_logic_rand,
         GameState.observe) = _ORIG_WRITES

    def count(self, field_name: str) -> int:
        """指定字段的写次数。"""
        return sum(1 for n in self.rows if n == field_name)


def test_deploy_move_writes_deployed_exactly_once() -> None:
    """空槽上场 = 单次 deployed 写(合卷契约):写序只含
    bench 摘槽写 + deployed 单写,无姊妹行域中间态。"""
    gs = _gs_with(
        DeployedView(front_slots=[None] * 4, back_slots=[None] * 6),
        bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    with _WriteRecorder(gs) as rec:
        report_action_deploy_move_param(
            gs, CwActionDeployMoveParam(bench_idx=0, to_row='back',
                                        to_slot=3, faction=''),
            _SIG_LOGIC)
    assert rec.count('deployed') == 1, '空槽上场恰一次 deployed 写'
    assert gs.deployed.value.back_slots[2].char_id == '甲'


def test_deploy_move_swap_occupied_target_single_write() -> None:
    """替换(目标槽有人 = 交换)= 仍单次 deployed 写:整视图整值替换,
    被占位者回源 bench 槽(bench 写独立,deployed 无第二写)。"""
    gs = _gs_with(
        DeployedView(front_slots=[_u('乙'), None, None, None],
                     back_slots=[None] * 6),
        bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    with _WriteRecorder(gs) as rec:
        report_action_deploy_move_param(
            gs, CwActionDeployMoveParam(bench_idx=0, to_row='front',
                                        to_slot=1, faction=''),
            _SIG_LOGIC)
    assert rec.count('deployed') == 1
    assert gs.deployed.value.front_slots[0].char_id == '甲'
    assert gs.bench.value.slots[0].unit.char_id == '乙', '被占位者回源'


def test_sell_and_swap_deployed_single_write() -> None:
    """卖场上/换位 = 各恰一次 deployed 写(合卷契约族全查)。"""
    gs = _gs_with(
        DeployedView(front_slots=[_u('乙'), None, None, None],
                     back_slots=[_u('丙'), None, None, None, None, None]),
        bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    with _WriteRecorder(gs) as rec:
        report_action_sell_deployed_param(
            gs, CwActionSellDeployedParam(deployed_idx=0), _SIG_LOGIC)
    assert rec.count('deployed') == 1
    assert gs.deployed.value.front_slots[0] is None

    with _WriteRecorder(gs) as rec2:
        report_action_swap_deploy_param(
            gs, CwActionSwapDeployParam(deployed_idx=4, bench_idx=0), _SIG_LOGIC)
    assert rec2.count('deployed') == 1
    assert gs.deployed.value.back_slots[0].char_id == '甲', '上场者落槽'


def test_row_reposition_observed_write_is_single() -> None:
    """换排/重排观察写 = 单次 deployed 写(director 观察合一写;同子表
    纯重排吸收不产生额外 deployed 写;重排吸收台账行为由
    test_board_derived_and_reorder 行域族校验)。"""
    gs = _gs_with(DeployedView(
        front_slots=[_u('佩佩'), _u('黑塔'), _u('万敌'), None],
        back_slots=[None] * 6))
    # 换排:佩佩 前→后
    with _WriteRecorder(gs) as rec:
        gs.observe(gs.deployed, DeployedView(
            front_slots=[None, _u('黑塔'), _u('万敌'), None],
            back_slots=[_u('佩佩'), None, None, None, None, None]),
            sig=_SIG_OBS)
    assert rec.count('deployed') == 1
    # 同子表纯重排:观察 = 采新覆盖,仍单写。
    with _WriteRecorder(gs) as rec2:
        gs.observe(gs.deployed, DeployedView(
            front_slots=[_u('万敌'), _u('黑塔'), None, None],
            back_slots=[_u('佩佩'), None, None, None, None, None]),
            sig=_SIG_OBS)
    assert rec2.count('deployed') == 1


def test_deploy_move_back_slot8_with_nine_layout_applies_and_extends() -> None:
    """动态容量布局真值辖载荷校验:back_layout=9 局 to_slot=8 applied +
    视图扩容到 8(旧定长表结构性拒绝的表示缺陷消失);同载荷在默认
    6 档仍拒绝(布局真值辖域互不越界)。"""
    # 9 格局:to_slot=8 落位 + 视图随落位扩容
    gs = _gs_with(DeployedView(front_slots=[None] * 4,
                               back_slots=[None] * 6),
                  bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    gs.observe(gs.back_layout, 9, sig=_SIG_OBS)
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='back',
                                    to_slot=8, faction=''),
        _SIG_LOGIC)
    assert out.applied, '9 格局 to_slot=8 在容量内(旧定长表拒绝 = 表示缺陷)'
    assert len(gs.deployed.value.back_slots) == 8, '视图随落位扩容'
    assert gs.deployed.value.back_slots[7].char_id == '甲'
    # 对照:默认 6 档同载荷拒绝(未观察 back_layout = 6 基线)
    gs6 = _gs_with(DeployedView(front_slots=[None] * 4,
                                back_slots=[None] * 6),
                   bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    out6 = report_action_deploy_move_param(
        gs6, CwActionDeployMoveParam(bench_idx=0, to_row='back',
                                     to_slot=8, faction=''),
        _SIG_LOGIC)
    assert not out6.applied, '6 档 to_slot=8 越容量 = 陈旧载荷零写'
