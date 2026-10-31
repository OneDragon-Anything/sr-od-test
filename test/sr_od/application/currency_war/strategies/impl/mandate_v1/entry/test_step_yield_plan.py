"""计划游标前置步测试(阶段 3 落地、阶段 5/6 升级为差分执行器驱动:
roster-plane1-union design §2.2 第 4 项执行端 + 用户裁定补录「跨画面
计划变量终版」+ unified-deploy-order §3.5 拖动/重观察交替;镜像 =
mandate_v1/entry.py ``_step_yield_plan``)。

验收锚 = design §3「计划变量测试」行:步骤序列写入(shop 侧承载,
shop/test_acquire_yield)/前置步逐帧消化(卖 V₁..Vₙ → 驱板面至 T)→
序列空清槽 → 开店(第 5 步常规机制发,SF-10)/零重验断言(备战执行零
搜索调用)/执行失败三态(V 不在场/卖失败/卡死)→ 清槽 + X 路径失败
标记 + 按计划语境记键/节点边界槽与标记清零/前置步挡第 1-9 步(含
出战)。阶段 5/6:T = 名→(排,星) 板面(就位粒度名+排+星);驱板
= 统一拖动 + in_place 重观察交替(§3.5 D8-1)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionMoveUnitParam,
    CwActionSellDeployedParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    YieldPlan,
    YieldPlanStep,
    state_of,
)

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-yield-plan-test',
                        mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-yield-plan-test',
                      mode='synthesized')

_GIL, _SBR, _FUX = '吉尔伽美什', 'Saber', '符玄'
_F3 = ('娜塔莎', '姬子·启行', '刻律德菈', '镜流')
_B5 = ('流萤', '昔涟', '布洛妮娅', '云璃', '景元',
       '托帕&账账', 'Archer', '大黑塔')


def _tb(*names, row: str = 'back') -> dict[str, tuple[str, int]]:
    """T 板面构造(名 → (排, 星);排缺省 back,星 1——就位粒度
    名+排+星,阶段 5/6 接口契约②)。"""
    return {n: (row, 1) for n in names}


def _plan_frame(*, bench=(), front=(), back=(), gold=30, level=5,
                board=None, plane=1, round_num=3):
    """双王圣杯锁定帧(计划执行端驱动;board 缺省空 = 配方不完备,
    非受限局态)。"""
    sess = StrategySession()
    st = state_of(sess)
    st.cw4_counters = {}
    st.v3_intention = IntentionState(locked_comp='双王圣杯')
    st.target_comp = get_comp('双王圣杯')
    gs = cw4_gs(sess, plane=plane, round_num=round_num, node='battle',
                gold=gold, level=level, hp=80, deploy_cap=level,
                bench=[cw4_bc(n) for n in bench],
                front_row=[Unit(char_id=n, star=1) for n in front],
                back_row=[Unit(char_id=n, star=1) for n in back],
                board=board)
    gs.observe(gs.node_pos, (plane, round_num), evidence='cw-yield-plan',
               sig=_OBS_SIG)
    gs.strategy_state = st
    return sess, gs, SimpleNamespace(ev_arm='full')


def _plan(steps, *, context='seat', target_board=None, stamp=(1, 3)):
    return YieldPlan(
        steps=[YieldPlanStep(kind=k, name=n) for k, n in steps],
        target_board=target_board, context=context, node_stamp=stamp)


def _remove_from_board(gs, name):
    """卖出落地投影:场上名移除(deployed 槽位置 None)。"""
    view = gs.deployed.value
    front = [None if (u is not None and u.char_id == name) else u
             for u in view.front_slots]
    back = [None if (u is not None and u.char_id == name) else u
            for u in view.back_slots]
    from sr_od.application.currency_war.kernel.cw_game_state import (
        DeployedView,
    )
    gs.write_logic(gs.deployed,
                   DeployedView(front_slots=front, back_slots=back),
                   produced_by='cw-yield-plan-test', sig=_LOGIC_SIG)


def _deploy_to_board(gs, name, row: str = 'back'):
    """上场落地投影:bench 首个同名件 → 指定排首个空槽(缺省后排,
    与 _tb 的排缺省一致)。"""
    view = gs.deployed.value
    front = list(view.front_slots)
    back = list(view.back_slots)
    slots = list(gs.bench.value.slots)
    for i, s in enumerate(slots):
        u = s.unit if s is not None else None
        if u is not None and u.char_id == name:
            slots[i] = BenchSlot(kind='empty')
            break
    target = None
    lst = front if row == 'front' else back
    for j, u in enumerate(lst):
        if u is None:
            lst[j] = Unit(char_id=name, star=1)
            target = (lst, j)
            break
    assert target is not None, '上场投影无空槽'
    from sr_od.application.currency_war.kernel.cw_game_state import (
        DeployedView,
    )
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-yield-plan-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.deployed,
                   DeployedView(front_slots=front, back_slots=back),
                   produced_by='cw-yield-plan-test', sig=_LOGIC_SIG)


class TestYieldPlanCursor:

    def test_digest_sells_deploys_clears_then_reopens_shop(self):
        """逐帧消化主链:卖 V(SellDeployed)→ 驱板(统一拖动上场 →
        in_place 重观察交替,§3.5 D8-1)→ T 就位 → 序列空 → 清槽
        (yield_plan_completed)→ 第 5 步常规机制发开店(SF-10:开店 =
        非序列步骤)。"""
        bench = [_SBR] + list(_B5)
        front = [_GIL, *_F3[:3]]
        back = [_F3[3]]
        sess, gs, cfg = _plan_frame(bench=bench, front=front, back=back)
        st = state_of(gs)
        # 商店写端产物形态(shop/test_acquire_yield 的
        # test_field_victim_writes_plan 同款帧与计划)。
        st.yield_plan = _plan(
            [('sell', '娜塔莎'), ('deploy', '')],
            target_board={
                _GIL: ('front', 1), _F3[1]: ('front', 1),
                _F3[2]: ('front', 1), _F3[3]: ('back', 1),
                _SBR: ('back', 1)})
        # 帧 1:卖场上件 V。
        acts = entry.emit(sess, cfg)
        assert len(acts) == 1 \
            and isinstance(acts[0].action, CwActionSellDeployedParam)
        assert st.yield_plan.steps[0].issued is True
        # 卖出落地 → 帧 2:对账通过,驱板缺位者(Saber)统一拖动上场。
        _remove_from_board(gs, '娜塔莎')
        acts = entry.emit(sess, cfg)
        assert len(acts) == 1 \
            and isinstance(acts[0].action, CwActionMoveUnitParam)
        assert acts[0].action.dst_domain == 'back'
        assert st.yield_plan.pending_reobserve is True, '拖动后应挂交替位'
        # 帧 3:交替重观察(in_place 环内对账)。
        acts = entry.emit(sess, cfg)
        assert type(acts[0].action).__name__ == 'CwActionObsParam'
        assert st.yield_plan.pending_reobserve is False
        # 上场落地 → 帧 4:T 就位(名+排+星)→ 序列空 → 清槽 → 扫描
        # 继续 → 第 5 步开店(shop_handled 未置)。
        _deploy_to_board(gs, _SBR)
        acts = entry.emit(sess, cfg)
        kinds = [type(a.action).__name__ for a in acts]
        assert 'CwActionOpenShopParam' in kinds[:1], \
            f'序列空帧应扫描至开店: {kinds}'
        assert st.yield_plan is None, '序列空未清槽'
        assert st.cw4_counters.get('yield_plan_completed') == 1
        assert st.cw4_counters.get('yield_plan_step') == 2

    def test_execution_zero_search_calls(self, monkeypatch):
        """零重验断言(裁定一:备战执行零搜索——T 已定型,差分与落位
        是执行算术):计划消化帧 select_deployment/assemble_prep_context
        零调用(调用即断言炸)。"""
        bench = [_SBR] + list(_B5)
        sess, gs, cfg = _plan_frame(bench=bench,
                                    front=[_GIL, *_F3[:3]], back=(_F3[3],))
        st = state_of(gs)
        st.yield_plan = _plan(
            [('sell', '娜塔莎'), ('deploy', '')],
            target_board={
                _GIL: ('front', 1), _F3[1]: ('front', 1),
                _F3[2]: ('front', 1), _F3[3]: ('back', 1),
                _SBR: ('back', 1)})

        def _no_search(*_a, **_k):
            raise AssertionError('备战计划执行禁部署搜索(零重验)')

        monkeypatch.setattr(mandate, 'select_deployment', _no_search)
        monkeypatch.setattr(mandate, 'assemble_prep_context', _no_search)
        acts = entry.emit(sess, cfg)
        assert isinstance(acts[0].action, CwActionSellDeployedParam)
        _remove_from_board(gs, '娜塔莎')
        acts = entry.emit(sess, cfg)
        assert isinstance(acts[0].action, CwActionMoveUnitParam)

    def test_fail_v_missing_clears_and_marks_by_context(self):
        """执行失败三态之一(V 不在场):游标指向卖步骤但目标已不在
        场/席(计划时在场,执行时被别处卖掉/合并的形态)→ 清槽 +
        X 路径失败标记 + 按语境记键(席位语境 →
        yield_plan_failed_priority_insufficient)+ 恢复扫描。"""
        bench = list(_B5)
        # 娜塔莎不在场上(计划语境的 V 已消失)。
        sess, gs, cfg = _plan_frame(bench=bench,
                                    front=[_GIL, _F3[1], _F3[2], _F3[3]],
                                    back=())
        st = state_of(gs)
        st.yield_plan = _plan(
            [('sell', '娜塔莎'), ('deploy', '')],
            target_board=_tb(_GIL))
        acts = entry.emit(sess, cfg)
        assert st.yield_plan is None, 'V 不在场未清槽'
        assert st.x_path_failed is True
        assert st.cw4_counters.get(
            'yield_plan_failed_priority_insufficient') == 1
        kinds = [type(a.action).__name__ for a in acts]
        assert 'CwActionSellDeployedParam' not in kinds, \
            '失败帧不得发卖出(恢复扫描)'
        # 失败标记在商店重评时排除场上件路径(消费面断言归 shop 侧
        # test_x_path_failed_excludes_field_victims 承载)。

    def test_fail_sell_unsuccessful_marks(self):
        """执行失败三态之二(卖失败):issued ∧ 目标仍在场 = 卖出执行
        层失败 → 同款清槽 + 标记 + 记键(纯金语境 →
        yield_plan_failed_priority_insufficient_gold)。"""
        sess, gs, cfg = _plan_frame(bench=list(_B5),
                                    front=[_GIL, *_F3[:3]], back=(_F3[3],))
        st = state_of(gs)
        st.yield_plan = _plan([('sell', '娜塔莎')],
                              context='gold', target_board=None)
        # 帧 1 发出卖 → 娜塔莎未实际落地(执行层失败形态)。
        entry.emit(sess, cfg)
        assert st.yield_plan is not None, 'issued 帧槽应保持'
        acts = entry.emit(sess, cfg)
        assert st.yield_plan is None, '卖失败未清槽'
        assert st.x_path_failed is True
        assert st.cw4_counters.get(
            'yield_plan_failed_priority_insufficient_gold') == 1
        assert not [a for a in acts
                    if isinstance(a.action, CwActionSellDeployedParam)]

    def test_fail_stall_two_frames_no_progress(self):
        """执行失败三态之三(级联卡死,本阶段简化版):驱板步骤基线
        观察后连续 2 帧覆盖数不增(缺位者不在 bench = 无动作帧计入
        S7-9)→ 清槽 + 标记 + 记键。「连续 2 次重观察后 diff 无进展」
        = 基线帧 + 2 个无变化帧。"""
        bench = list(_B5)   # bench 无 T 缺位者(镜流不在 bench)
        sess, gs, cfg = _plan_frame(bench=bench,
                                    front=[_GIL, _F3[1], _F3[2]], back=())
        st = state_of(gs)
        st.yield_plan = _plan(
            [('deploy', '')],
            target_board=_tb(_GIL, _F3[1], _F3[2], '镜流', row='front'))
        act1 = entry.emit(sess, cfg)   # 帧 1:基线观察(covered 3)
        assert type(act1[0].action).__name__ == 'CwActionObsParam', \
            f'无动作帧应 in_place 重观察: {act1[0].action!r}'
        assert st.yield_plan is not None
        entry.emit(sess, cfg)          # 帧 2:无变化(第 1 次)
        assert st.yield_plan is not None, '第 1 次无变化帧不得提前出口'
        entry.emit(sess, cfg)          # 帧 3:无变化(第 2 次)→ 卡死出口
        assert st.yield_plan is None, '连续 2 帧无进展未清槽'
        assert st.x_path_failed is True
        assert st.cw4_counters.get(
            'yield_plan_failed_priority_insufficient') == 1

    def test_node_boundary_resets_plan_and_marker(self):
        """节点边界:槽与标记均清零(重置表登记;节点戳 = 双保险)。"""
        sess, gs, cfg = _plan_frame(bench=list(_B5),
                                    front=[_GIL, *_F3[:3]], back=(_F3[3],))
        st = state_of(gs)
        st.yield_plan = _plan([('sell', '娜塔莎')])
        st.x_path_failed = True
        gs.observe(gs.node_pos, (1, 4), evidence='cw-yield-plan-test',
                   sig=_OBS_SIG)
        session_scope.handle_node_boundary(gs)
        assert st.yield_plan is None, '节点边界未清计划槽'
        assert st.x_path_failed is False, '节点边界未清失败标记'

    def test_stamp_mismatch_clears_stale_plan(self):
        """节点戳双保险:跨节点残留(未经边界处理直达)→ 戳不等 =
        失效清槽(同 shop_handled 形态)。"""
        sess, gs, cfg = _plan_frame(bench=list(_B5),
                                    front=[_GIL, *_F3[:3]], back=(_F3[3],))
        st = state_of(gs)
        st.yield_plan = _plan([('sell', '娜塔莎')], stamp=(9, 9))
        entry.emit(sess, cfg)
        assert st.yield_plan is None
        assert st.cw4_counters.get('yield_plan_stamp_mismatch') == 1

    def test_plan_slot_blocks_steps_and_battle(self):
        """槽在期间前置步优先于第 1-9 全部步(含第 9 步出战):无动作
        可发帧(差分空动作:缺位者不在 bench ∧ 多余者无 bench 空槽可下)
        返回 CwActionObsParam(in_place 重观察)而非出战;bridge
        前置动作发出点让位(计划槽非空谓词 → 让位于十段扫描)。"""
        bench = list(_B5) + ['花火']   # 9 件满席:多余者无空槽可下
        sess, gs, cfg = _plan_frame(bench=bench, front=[_GIL],
                                    back=(), gold=60)
        st = state_of(gs)
        # deploy 步骤 + T 含既不在板也不在 bench 的缺位者(符玄),
        # 板上唯一件已就位 → 差分无动作 → in_place 重观察挡扫描。
        st.yield_plan = _plan(
            [('deploy', '')],
            target_board={_GIL: ('front', 1), _FUX: ('front', 1)})
        acts = entry.emit(sess, cfg)
        assert type(acts[0].action).__name__ == 'CwActionObsParam', \
            f'计划期无动作帧禁出战/禁后续步: {acts[0].action!r}'
        # bridge 让位:计划槽非空 → 出战就绪帧也让位于扫描。
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            bridge,
        )
        assert bridge._launch_front_check(gs) is None, \
            '计划槽非空帧前置动作发出点应让位(不出战)'
        assert st.cw4_launch_spend_visited is False, '段旗应复位'
