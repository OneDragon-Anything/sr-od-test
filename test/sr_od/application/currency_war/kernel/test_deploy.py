"""部署与换人域锁(机制主题文件;部署决策 → 载荷执行 → 写序契约全链)。

被锁机制(按节;设计出处见各节 docstring):
- **部署围栏与占槽物品防线**:占位件(kind ∈ tome/bookcard/supply_box)
  恒 held、拒因 ``item_slot``,先于一切围栏/cap 判定被剔除(benchchar-
  retirement P4 容器槽位 kind 口);
- **板满门三锁**(事故 match_g_20260918_023823,定谳见
  .debug/temp/incidents/20260918-reconcile/rootcause-reopen.md 案一):
  部署输入改容器现读 + 显式板满门,拒因 ``deploy_cap_full`` 帧级去重;
- **落位策略三级排路由**:comp 站位覆盖 > 注册表派生 > back 兜底;
  后排槽位上限 = back_layout 现值(P2 遗留分歧消除);
- **必需件语义**(判据必要条件支配论证;sim n1000 s91700 两失败局):
  required 成员 cap 竞争首桶序 + 板满换入臂(成型折法单一源 =
  ``form_progress``,OR 组承接);
- **双轨对锁期换入通道**(2026-09-18 sim 实证:配方对锁局板满帧全
  plan_empty):转型域方向锁前提推广 / 完成件让位 / 发射门轴①读法;
- **残余补部署守卫**(P24 结构支配定理,零自由参数):dup 剔除 /
  cap 满停 / 两排皆满停 / cap=None 不设门 + 配方底线门 kernel 直锁;
- **载荷与执行语义**(P2 拖拽语义落码):(to_row, to_slot) 直落
  反「首空」、目标槽有人 = 交换(写侧/执行链/sim 三面同源);
- **动作上报单写写序**(合卷契约):一次语义变更 = 恰一次 deployed 写;
  动态容量布局真值辖载荷校验。
"""
from __future__ import annotations

from types import SimpleNamespace

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
    COMP_LIBRARY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
    recipe_floor_holds,
    required_swap_arm_pending,
    residual_fill_plan,
    select_swap_plan,
    swap_sell_exclusion_reason,
    xianzhou_supply_exists,
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
from sr_od.application.currency_war.kernel.cw_intention import (
    pair_target_comp,
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
    deploy_plan as dp,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    deploy_row_pref,
    deploy_slot_plans,
    select_deployments,
    select_deployments_reasoned,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    _redeploy_emission_allowed,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    _slot_cid as _slot_cid_of,
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


# ============================================================ 部署围栏与占槽物品防线


def _unit_slot(slot: int, char_id: str, star: int = 1) -> BenchSlot:
    """占席单位槽(``slot`` 参数保留签名兼容,位置 = 列表下标)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star))


def test_item_slot_candidate_held_with_item_slot_reason() -> None:
    """占位件候选:不上场、进留置、拒因 item_slot;普通候选不受防线
    误伤(防线只剔占位件候选,不背 item_slot 拒因)。"""
    bench = [_unit_slot(1, '甲'),
             BenchSlot(kind='supply_box', unit=None)]
    reasons: dict[int, str] = {}
    up, rest = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={}, cap=10,
        reasons_out=reasons)
    assert 1 not in up, '占槽物品永不进上场集'
    assert 1 in rest, '占槽物品恒留置(常驻占席)'
    assert reasons.get(1) == 'item_slot', \
        f'拒因 = item_slot,实得 {reasons.get(1)!r}'
    assert 0 in up, '普通候选照常上场'
    assert reasons.get(0) != 'item_slot', '普通候选不背 item_slot 拒因'


# ============================================================ 板满门三锁(容器现读 + 显式门 + 拒因台账)


def _bs_unit(name: str) -> BenchSlot:
    """容器占席条目(P4 载体迁移:MandateFrame 直构面)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=1))


def _full_board_session():
    """容器 3/3 满板(上阵前 3 人)+ 备战席候选;返回 (session, gs)。"""
    session = cw4_session(cw4_comp())
    gs = cw4_gs(session, deploy_cap=3, bench=[cw4_bc('艾丝妲')],
                front_row=[Unit(char_id='丹恒·饮月', star=1),
                           Unit(char_id='卡芙卡', star=1),
                           Unit(char_id='杰帕德', star=1)])
    return session, gs


def _stale_frame(round_num: int = 2):
    """陈旧决策帧:黑板名单仍是 2 人(缺刚上场的第 3 人)——事故帧形态。
    P4 容器形:bench = 占席条目,deployed = 行域 Unit。"""
    return mandate.MandateFrame(
        gold=10, level=3,
        bench=[_bs_unit('艾丝妲')],
        deployed=[Unit(char_id='丹恒·饮月', star=1),
                  Unit(char_id='卡芙卡', star=1)],
        deploy_cap=3, node_type=None, stop_flag=False,
        k_members=(), round_num=round_num)


def test_cap_full_stale_frame_emits_nothing():
    """事故形态锁:容器 3/3 满 + 决策帧黑板 2 人(陈旧)→ 零拖拽发射、放行 False。"""
    session, gs = _full_board_session()
    frame = _stale_frame()
    assert mandate._deployable(frame, session, gs) is False
    out: list = []
    mandate._emit_deploy_moves(out, frame, session, gs, 'm1_test')
    assert out == []


def test_cap_roomy_stale_container_still_deploys():
    """陈旧视图锁:容器 2/3 未满时照常产出部署(换源不改坏正常路径);
    容器名单为部署输入真值——板满判定读容器而非帧。"""
    session = cw4_session(cw4_comp())
    gs = cw4_gs(session, deploy_cap=3, bench=[cw4_bc('艾丝妲')],
                front_row=[Unit(char_id='丹恒·饮月', star=1),
                           Unit(char_id='卡芙卡', star=1)])
    stale = _stale_frame()
    assert mandate._deployable(stale, session, gs) is True
    out: list = []
    mandate._emit_deploy_moves(out, stale, session, gs, 'm1_test')
    assert len(out) == 1


def test_cap_full_counter_frame_dedup():
    """拒因台账锁:板满帧 → cw4_counters['deploy_cap_full'] 计数,同帧
    (plane, round) 去重;跨帧(round 推进)再计。"""
    session, gs = _full_board_session()
    counters = state_of(session).cw4_counters
    assert mandate._deploy_cap_full_gate(session, gs, _stale_frame()) is True
    assert counters.get('deploy_cap_full') == 1
    # 同帧重复判定(同次备战访问内 M1/M5/wanted 臂多次过门)不再计数
    assert mandate._deploy_cap_full_gate(session, gs, _stale_frame()) is True
    assert counters.get('deploy_cap_full') == 1
    # 轮次推进 = 新帧,再计
    assert mandate._deploy_cap_full_gate(session, gs, _stale_frame(round_num=3)) is True
    assert counters.get('deploy_cap_full') == 2


# ============================================================ 落位策略三级排路由 + back_layout 槽上限


def _bs(slot: int, char_id: str) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=1))


def test_comp_position_override_beats_registry_pref() -> None:
    """comp char_positions 覆盖注册表:万敌注册表 flex(派生 back),
    「万敌单C」覆盖为 front → 落位排 = front(逐件路由直接断言 +
    落位计划端到端各一腿)。"""
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
    被落位策略排到前排——旧链路恒按后排,本锁钉住派生真实生效。"""
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
    正确行为,不混入本锁)。"""
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
    前排保证强转(不混入本锁)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_layout, 8, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id=f'前{i}', star=1, equips=[])
                for i in range(1, 5)], []), evidence='t', sig=_SIG_OBS)
    bench = [_bs(i + 1, '花火') for i in range(8)]
    moves = deploy_slot_plans(bench, list(range(8)), None, gs)
    back_slots = [slot for _bi, row, slot in moves if row == 'back']
    assert back_slots == [1, 2, 3, 4, 5, 6, 7, 8], \
        f'扩展局后排空槽达 8 号,实得 {back_slots!r}'


# ============================================================ 必需件语义(首桶序 + 板满换入臂)

# 真实注册表角色(锁语义不锁巧合;registry 真值):
# 桑博 = 贝+持续伤害 / 娜塔莎 = 贝 / 花火 = 量子 / 卡芙卡 = 持续伤害 /
# 缇宝 = 量子 / 希儿 = 贝+量(required carry)/ 黑天鹅 = 持续伤害 /
# 三月七 = 列车同行+护盾(fenced,对视野外)。
_SANGBO = '桑博'
_NATASHA = '娜塔莎'
_HUAHUO = '花火'
_KAFKA = '卡芙卡'
_TIBAO = '缇宝'
_XIER = '希儿'
_HEITIANQUE = '黑天鹅'
_SANYUEQI = '三月七'

# 持续伤害+希儿系 pair 的判据腿(真实 pair 键;fallback 分支产物 =
# form_tiers {持续伤害:2} + or_legs 量2∨贝2 + required 希儿;单一源 =
# pair_target_comp)。
_PAIR = ('持续伤害', '希儿系')


def _bc(name: str, idx: int) -> BenchSlot:
    """bench 件(容器占席条目;slot = 1 基物理槽,idx 供唯一 slot)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=1))


def _pair_comp():
    return pair_target_comp(_PAIR)


def _static_comp():
    """静态套「希儿量子」(P2+ 锁线路径;form_tiers 全被 OR 承接的
    ADR-0621 形态——换入臂折法单一源的本形态验证面)。"""
    return get_comp('希儿量子')


def test_required_carry_seats_first_under_cap_competition() -> None:
    """cap 竞争(空位 1,候选 2)下必需件先于普通 target 成员上板。

    反证面:required_names 缺省空集 = 逐位旧序(bench 序先者上),锁
    「默认路径零漂移」与「新参翻转竞争结果」一对事实。
    """
    bench = [_bc(_SANGBO, 1), _bc(_XIER, 2)]   # 桑博 bench 序在前
    up, _held = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={},
        cap=1, target_factions={'贝洛伯格', '持续伤害'},
        target_cores={_SANGBO, _XIER}, required_names={_XIER})
    assert [dp._slot_cid(bench[i]) for i in up] == [_XIER]

    up_old, _held = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={},
        cap=1, target_factions={'贝洛伯格', '持续伤害'},
        target_cores={_SANGBO, _XIER})
    assert [dp._slot_cid(bench[i]) for i in up_old] == [_SANGBO]


def _ctx(*, board: list[str], bench: list[str], cap: int,
         comp=None, required=frozenset()) -> SwapPlanContext:
    """直构 SwapPlanContext(1★ 单元格;target 键 = pair 真值;
    required 缺省按「bench 有希儿 ∧ 板上无」派生,可显式覆写)。"""
    return SwapPlanContext(
        target_factions=frozenset({'持续伤害', '量子同频', '贝洛伯格'}),
        target_cores=frozenset((*board, *bench)),
        fw_carry=frozenset(),
        locked_factions=frozenset(),
        protect_names=frozenset(),
        membership=frozenset(),
        fresh_buys=frozenset(),
        board={},
        deployed=[Unit(char_id=n, star=1)
                  for i, n in enumerate(board)],
        bench=[_bc(n, i + 1) for i, n in enumerate(bench)],
        cap=cap,
        front_slots=4,
        back_slots=6,
        fenced_on=False,
        fp=0.0,
        locked=False,
        board_full=len(board) >= cap,
        recipe_floor_lock_exempt=False,
        target_comp=comp if comp is not None else _pair_comp(),
        evolution_swap_armed=False,
        transition_domain=False,
        required_names=frozenset(required)
        if required else (
            frozenset({_XIER})
            if _XIER in bench and _XIER not in board else frozenset()),
    )


def test_swap_arm_sellable_only_when_completion_holds() -> None:
    """换入臂资格分野:假想面板(离场+必需件按已换入计)下判据满的可卖;
    破判据的照旧 target_keep。

    板 = 桑博(贝+DOT)+卡芙卡(DOT)+娜塔莎(贝)+花火(量),pair
    判据 = DOT2 ∧ (量2∨贝2) ∧ 希儿在板:花火/娜塔莎离场 → DOT2 ✓ 且
    (量2:花火+希儿 / 贝2)判据满 → 让位可卖(1★ 单元格资格族余守卫全
    过);桑博离场 → DOT1 = AND 破;卡芙卡离场 → DOT1 同破——均
    target_keep。
    """
    ctx = _ctx(board=[_SANGBO, _KAFKA, _NATASHA, _HUAHUO],
               bench=[_XIER], cap=4)
    assert required_swap_arm_pending(ctx)
    assert swap_sell_exclusion_reason(_HUAHUO, ctx) == ''
    assert swap_sell_exclusion_reason(_NATASHA, ctx) == ''
    assert swap_sell_exclusion_reason(_SANGBO, ctx) == 'target_keep'
    assert swap_sell_exclusion_reason(_KAFKA, ctx) == 'target_keep'


def test_swap_arm_holds_via_or_leg_on_static_comp() -> None:
    """静态套「希儿量子」(OR 承接形态):量4+贝2 板卖一量件判据仍满。

    判据 = 希儿在板 ∧ 量2∨贝2(form_tiers 全被 OR 承接,AND 账为空):
    花火离场 → 量3 ≥2 OR 腿仍在 → 可卖。若按裸 AND 量4 计账会误判破腿
    (臂过度关闭)——本锁钉住折法单一源(form_progress)的承接规则。
    """
    comp = _static_comp()
    ctx = _ctx(board=[_HUAHUO, _TIBAO, _NATASHA, _SANGBO],
               bench=[_XIER], cap=4, comp=comp)
    assert required_swap_arm_pending(ctx)
    assert swap_sell_exclusion_reason(_HUAHUO, ctx) == ''


def test_swap_arm_closed_when_carry_already_on_board() -> None:
    """必需件在板 = 臂关(无换入需求),target 保护原样。"""
    ctx = _ctx(board=[_SANGBO, _KAFKA, _NATASHA, _HUAHUO, _XIER],
               bench=[_HUAHUO], cap=5)
    assert not required_swap_arm_pending(ctx)


def test_swap_plan_seats_required_carry_after_sell() -> None:
    """卖后上序正形:卖冗余件后空位落必需件(sell = 扫描序首个可让位件,
    up = 希儿)。

    席位竞争面:bench 序普通 target 成员(缇宝,不在板,无同名去重拦截)
    在前时,必需件仍须先落——旧序会把席位给缇宝 = 卖冗余件白卖形态,
    本锁行使「首桶序 × 卖后上序」的组合语义。victim 序 = 板槽位扫描序
    (域外键),首个资格通过者 = 娜塔莎(桑博/卡芙卡破 DOT 腿被拒)。
    """
    ctx = _ctx(board=[_SANGBO, _KAFKA, _NATASHA, _HUAHUO],
               bench=[_TIBAO, _XIER], cap=4)
    plan = select_swap_plan(ctx, select_up=select_deployments_reasoned)
    assert plan.nonempty
    assert plan.sell_names == [_NATASHA]
    up_names = {dp._slot_cid(ctx.bench[i]) for i in plan.up_bench}
    assert up_names == {_XIER}


def test_swap_arm_never_opens_protect_extension() -> None:
    """保护域扩展集(shared ∪ 替班,protect_names − target_cores)不因
    换入臂解除(P41② + 替班=不卖字段契约):armed 帧照旧 target_keep。

    构造:target_cores 不含该件(保护域扩展 = 板上「万敌」占位形态),
    腿保持与否无关紧要——护栏先于臂判定。
    """
    comp = _pair_comp()
    ctx = _ctx(board=[_SANGBO, _KAFKA, _NATASHA, _HUAHUO],
               bench=[_XIER], cap=4, comp=comp)
    ctx.protect_names = frozenset({'万敌'})
    ctx.deployed = list(ctx.deployed) + [Unit(char_id='万敌', star=1)]
    ctx.cap = 5
    ctx.board_full = True
    assert swap_sell_exclusion_reason('万敌', ctx) == 'target_keep'


def test_swap_arm_premise_single_required_member() -> None:
    """换入臂前提锁(现役单 required 成员):假想面板把 required_names
    全体按「已换入」计(``select_swap_plan`` 检验处),而臂一次只卖一个
    victim、换入一个必需件——该计法仅当 required 成员数 ≤1 时无白卖面
    (≥2 成员且多个不在板时检验通过 ≠ 实际成型,卖一换一仍缺腿)。
    ``required_deployed`` 字段契约允许多成员(``cw_comps.Comp``),
    生产来源全量 = 静态注册表 ``COMP_LIBRARY`` 逐 comp + pair 物化
    ``pair_target_comp``,本锁逐一断言单成员前提;任一来源出现多成员
    形态 → 本锁红 = 提示先重审假想面板计法(改按「换入后仍缺数」折算)
    再上多成员 comp,禁为保绿直接放行。
    """
    multi = [c.name for c in COMP_LIBRARY
             if len(c.required_deployed) > 1]
    assert not multi, \
        f'多 required 成员 comp 已注册,换入臂假想面板计法前提破: {multi}'
    pair = _pair_comp()
    assert pair is not None and len(pair.required_deployed) <= 1, \
        'pair 物化 required 多成员形态激活,同上重审假想面板计法'


# ============================================================ 双轨对锁期换入通道


def _swap_ctx(*, board: list[str], bench: list[str], cap: int,
              fp: float, locked: bool, domain: bool,
              required: frozenset[str] = frozenset()) -> SwapPlanContext:
    """直构 SwapPlanContext(1★ 单元格;pair 真值键面;域快照随 locked
    一致传入——装配点两字段同点同值)。"""
    comp = pair_target_comp(_PAIR)
    return SwapPlanContext(
        target_factions=frozenset(comp.all_factions),
        target_cores=frozenset(comp.core_chars),
        fw_carry=frozenset(),
        locked_factions=frozenset(),
        protect_names=frozenset(),
        membership=frozenset(),
        fresh_buys=frozenset(),
        board={},
        deployed=[Unit(char_id=n, star=1)
                  for i, n in enumerate(board)],
        bench=[BenchSlot(kind='unit',
                         unit=Unit(char_id=n, star=1))
               for i, n in enumerate(bench)],
        cap=cap,
        front_slots=4,
        back_slots=6,
        fenced_on=False,
        fp=fp,
        locked=locked,
        board_full=len(board) >= cap,
        recipe_floor_lock_exempt=False,
        target_comp=comp,
        evolution_swap_armed=False,
        transition_domain=domain,
        required_names=frozenset(required) or frozenset(comp.required_deployed),
    )


def test_pair_locked_domain_releases_fenced_offline_victim() -> None:
    """配方对锁帧转型域开:fenced 离线件经资格族可卖;未对锁帧照旧拒。

    板 = 卡芙卡(DOT1)+希儿+花火(量2)+三月七(围栏件,对视野外):
    判据缺 DOT 腿(fp 0.833 <1)∧ 板满 → 对锁帧三月七经守恒门(列车/
    护盾 0 档不掉)放行;同板未对锁帧 = fenced_arm_closed(前提分野)。
    """
    board = [_KAFKA, _XIER, _HUAHUO, _SANYUEQI]
    ctx_open = _swap_ctx(board=board, bench=[_HEITIANQUE], cap=4,
                         fp=0.833, locked=True, domain=True)
    assert swap_sell_exclusion_reason(_SANYUEQI, ctx_open) == ''
    ctx_closed = _swap_ctx(board=board, bench=[_HEITIANQUE], cap=4,
                           fp=0.833, locked=False, domain=False)
    assert swap_sell_exclusion_reason(_SANYUEQI, ctx_closed) \
        == 'fenced_arm_closed'


def test_completion_member_yields_target_seat() -> None:
    """完成件滞留通道:希儿在板(required 臂关)∧ bench 有入板即成型件,
    多余腿 target 板件让位可卖;破腿件照旧 target_keep;计划真换入完成件。

    板 = 卡芙卡(DOT1)+希儿+花火(量2)+娜塔莎(贝1):判据缺 DOT 腿;
    黑天鹅入板 → DOT2 → fp=1.0(完成件)。花火/娜塔莎离场(量2 或贝2 有
    另一腿承住)+黑天鹅入板 → 判据满 → 让位;卡芙卡离场 → DOT 归零破腿
    → 照旧保。旧语义下必需件臂只辖 required(希儿在板 = 臂关),完成件
    压席无解形态(sim 实证主桶)。victim 序 = 让渡序(贡献并列 1
    → 扫描序,花火在前);卖后板面 = DOT2∧贝2∧希儿在板,成型。
    """
    ctx = _swap_ctx(board=[_KAFKA, _XIER, _HUAHUO, _NATASHA],
                    bench=[_HEITIANQUE], cap=4,
                    fp=0.833, locked=True, domain=True)
    assert required_swap_arm_pending(ctx)   # 完成分支武装(希儿在板)
    assert swap_sell_exclusion_reason(_HUAHUO, ctx) == ''
    assert swap_sell_exclusion_reason(_NATASHA, ctx) == ''
    assert swap_sell_exclusion_reason(_KAFKA, ctx) == 'target_keep'
    plan = select_swap_plan(ctx, select_up=select_deployments_reasoned)
    assert plan.nonempty
    assert plan.sell_names == [_HUAHUO]
    # (P4 容器形:bench 身份经解包口读)
    assert {_slot_cid_of(ctx.bench[i]) for i in plan.up_bench} \
        == {_HEITIANQUE}


def test_completion_channel_gates() -> None:
    """完成通道三闭门:成型帧关 / bench 无完成件关 / 未对锁帧关。

    板面同 test_completion_member_yields_target_seat,仅翻转前提——
    fp≥1.0(已成型,无完成缺口)、bench 无完成件(黑天鹅换万敌)、
    locked=False(未对锁,方向锁前提不在)三者 pending 均 False。
    """
    board = [_KAFKA, _XIER, _HUAHUO, _NATASHA]
    assert not required_swap_arm_pending(_swap_ctx(
        board=board, bench=[_HEITIANQUE], cap=4,
        fp=1.0, locked=True, domain=True))
    assert not required_swap_arm_pending(_swap_ctx(
        board=board, bench=['万敌'], cap=4,
        fp=0.833, locked=True, domain=True))
    assert not required_swap_arm_pending(_swap_ctx(
        board=board, bench=[_HEITIANQUE], cap=4,
        fp=0.833, locked=False, domain=False))


def test_redeploy_gate_pair_period_reads_target_view() -> None:
    """发射门轴①对锁期读法:membership 空集帧压席成员轴退 target 视图。

    bench = 花火(视图内,入板即成型)+万敌(视图外):空 membership 帧
    花火撑起轴①,轴②(入板推进成型度,严格上升)真 → 放行;bench 全
    视图外 → defer。轴①锁线分支(membership 非空)不辖本读法。
    """
    comp = pair_target_comp(_PAIR)
    gate_ctx = SimpleNamespace(
        membership=frozenset(),
        bench=[SimpleNamespace(char_id=_HUAHUO),
               SimpleNamespace(char_id='万敌')],
        target_comp=comp,
        target_factions=frozenset(comp.all_factions),
        target_cores=frozenset(comp.core_chars),
        fw_carry=frozenset(),
    )
    # 板 = DOT1 + 量1 + 希儿在板口径(fp 0.833):花火入板 → 量2 → OR 腿
    # 0.5→1.0 严格上升(轴②)。
    state = SimpleNamespace(board=SimpleNamespace(value={
        '持续伤害': 1, '量子同频': 1, '贝洛伯格': 1}))
    assert _redeploy_emission_allowed(session=None, state=state,
                                      ctx=gate_ctx)
    off_ctx = SimpleNamespace(
        membership=frozenset(),
        bench=[SimpleNamespace(char_id='万敌')],
        target_comp=comp,
        target_factions=frozenset(comp.all_factions),
        target_cores=frozenset(comp.core_chars),
        fw_carry=frozenset(),
    )
    assert not _redeploy_emission_allowed(session=None, state=state,
                                          ctx=off_ctx)


def test_redeploy_gate_membership_unread_fails_closed() -> None:
    """发射门 membership 缺读弃权:None = 缺读,不放行(fail-closed)。

    契约边界 = None 缺读 ≠ 空集缺省,禁坠对锁期回退放宽(出处 =
    ``_redeploy_emission_allowed`` None 分支注)。入面参照
    test_redeploy_gate_pair_period_reads_target_view 的放行构造——若
    None 分支被误删坠回空集缺省读法,本构造经 target 视读法会假放行,
    锁响。
    """
    comp = pair_target_comp(_PAIR)
    unread_ctx = SimpleNamespace(
        membership=None,
        bench=[SimpleNamespace(char_id=_HUAHUO),
               SimpleNamespace(char_id='万敌')],
        target_comp=comp,
        target_factions=frozenset(comp.all_factions),
        target_cores=frozenset(comp.core_chars),
        fw_carry=frozenset(),
    )
    # 板面同放行构造口径:花火入板 → 量2 → 轴②严格上升(None 分支
    # 被删时走空集读法会真放行,保证本锁判别力)。
    state = SimpleNamespace(board=SimpleNamespace(value={
        '持续伤害': 1, '量子同频': 1, '贝洛伯格': 1}))
    assert not _redeploy_emission_allowed(session=None, state=state,
                                          ctx=unread_ctx)


# ============================================================ 残余补部署守卫(P24)


def test_fill_legal_held_on_empty_slot():
    # 合法散牌 + 空槽 → 逐件补上(P24 ΔEV≥0 = 补);slot_idx 取自
    # 对应排空槽列表原值(0 基,row_pts[slot_idx] 取拖点)。
    plan = residual_fill_plan(
        held=[5, 6], front_empty=[1], back_empty=[3, 4],
        bench_pos={5: 'front', 6: 'back'},
        bench_cid={5: '飞霄', 6: '停云'},
        deployed_cids=set(), cap=4, deployed_count=2)
    assert plan == [(5, 'front', 1), (6, 'back', 3)]


def test_fill_dup_name_stays_bench():
    # 同名禁双(5.1.7):dup 是 3合1 素材,游戏拒收同名 → 留 bench 不补。
    plan = residual_fill_plan(
        held=[2], front_empty=[0, 1], back_empty=[0, 1, 2, 3, 4, 5],
        bench_pos={2: 'front'}, bench_cid={2: '藿藿'},
        deployed_cids={'藿藿'}, cap=6, deployed_count=1)
    assert plan == []


def test_fill_stops_at_cap():
    # cap 满不补;半满 → 只补到 cap 截断。
    rows = {'front_empty': [0, 1], 'back_empty': [0, 1, 2, 3, 4, 5]}
    plan = residual_fill_plan(
        held=[3, 4], bench_pos={3: 'back', 4: 'back'},
        bench_cid={3: '停云', 4: '青雀'},
        deployed_cids=set(), cap=3, deployed_count=3, **rows)
    assert plan == []   # 已达 cap → 一件不补
    plan = residual_fill_plan(
        held=[3, 4], bench_pos={3: 'back', 4: 'back'},
        bench_cid={3: '停云', 4: '青雀'},
        deployed_cids=set(), cap=4, deployed_count=3, **rows)
    assert [p[0] for p in plan] == [3]   # 只补 1 件到 cap


def test_fill_cap_none_means_no_gate():
    # cap=None 不设门(拖到游戏拒即真值,同主循环 5.1.8 口径)。
    plan = residual_fill_plan(
        held=[3, 4], front_empty=[], back_empty=[0, 1, 2, 3, 4, 5],
        bench_pos={3: 'back', 4: 'back'},
        bench_cid={3: '停云', 4: '青雀'},
        deployed_cids=set(), cap=None, deployed_count=10)
    assert [p[0] for p in plan] == [3, 4]


def test_fill_row_pref_fallback_and_both_full():
    # 首选排满 fallback 另一排;两排皆满停;position_pref 缺读默认
    # back(后排槽多,安全缺省)。
    plan = residual_fill_plan(
        held=[7], front_empty=[], back_empty=[2],
        bench_pos={7: 'front'}, bench_cid={7: '飞霄'},
        deployed_cids=set(), cap=8, deployed_count=3)
    assert plan == [(7, 'back', 2)]
    plan = residual_fill_plan(
        held=[7], front_empty=[], back_empty=[],
        bench_pos={7: 'front'}, bench_cid={7: '飞霄'},
        deployed_cids=set(), cap=8, deployed_count=3)
    assert plan == []   # 两排皆满
    plan = residual_fill_plan(
        held=[0], front_empty=[0], back_empty=[1],
        bench_pos={}, bench_cid={0: '飞霄'},
        deployed_cids=set(), cap=8, deployed_count=3)
    assert plan == [(0, 'back', 1)]


def test_fill_floor_gate_direct_kernel():
    # 配方底线门(kernel 直锁):kernel 留 bench 的列车件
    # (列车≥2 ∧ 仙舟<3)不得经补部署绕回上板;锁定线豁免语境
    # (∧ 本帧无有效仙舟供给)门让位放行,供给在场时门照拦(供给
    # 保留条款)。holds=True = 该件应被门持有(对 fill 计划即剔除)。
    # 常规语境:门拦
    assert recipe_floor_holds('列车同行', 2, 0, False, False)
    # 锁定线豁免 + 本帧无仙舟供给:门让位 → 放行
    assert not recipe_floor_holds('列车同行', 2, 0, True, False)
    # 豁免武装但 bench 有有效仙舟供给(停云:仙舟羁绊非列车主阵营)
    # → 门照拦
    assert recipe_floor_holds(
        '列车同行', 2, 0, True,
        xianzhou_supply_exists(
            [BenchSlot(kind='unit',
                       unit=Unit(char_id='停云', star=1))], set()))


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
    (陈旧载荷;执行层唯一失败形态 = 拖拽未生效,拒绝面只在载荷静态域)。"""
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
    """执行链同源锁:载荷 (back, 3) → 拖点 = 后排 area 序 3−1;
    主域 deployed 落位 = 载荷槽子表下标(与容器写侧同式;
    tracked 同步腿退役,op 自上报单点写主域)。
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
    """载荷槽越出画面槽位数(back 7 > 6 槽)= 陈旧载荷未发出
    (round_fail),零拖拽零主域写(观察重派)。"""
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
    ok = CwActionDeployMoveOp(env.op.ctx, action, env=env).run()
    assert not ok.is_success and drags == [], '越界载荷未发出'
    assert gs.bench.value.slots[0].kind == 'unit', '主域整笔未写'


def test_sim_applies_occupied_target_as_swap():
    """部署上报(动作腿单一源)对「目标槽有人」按交换建模:上场者落
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
    """对照腿:载荷槽空 = 放置(上报函数与写侧同一转移函数)。"""
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
    test_board_derived_and_reorder 行域族锁定)。"""
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
