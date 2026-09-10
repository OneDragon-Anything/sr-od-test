"""CW 委任(mandate)生命周期测试(#7):备战旗标机 S1/S2 + prep gate
前件 + landed 契约 + 备战投影金账。

覆盖面:
- S1(备战期开店闩)重置代表:RunDeploy 真落地清键 ↔ 零落地(STATUS_NOOP)
  保闩零遥测(F1b/T-167 事故对:「no-op 部署清闩 = 凭空再武装开店意图,
  交替活锁,25 次无信息量重开店」实录);
- S2(商店 wanted 残差旗标)代表:经生产链 decide_shop_action 席满残差点
  置位,四元载体 + 在店快照同源口径(ADR-0599 F2-6);
- prep gate 代表:S2 门 0′ 前件 hold(缺员不在店)——零发射、S2 保留、
  不置放弃态(T-161 F2 缺陷关闭面);
- landed 契约代表:F1b 落地判定 = 执行器具名常量结构化比对(T-167 修法;
  常量解析缺失 fail-closed 按未落地);
- 投影金账(金钱不变量):SellBench 投影 gold += sell_refund(与 simulate
  卖出分支同式)+ state 缺失帧金账跳过不造值(保守侧)。

来源:本文件 = test_cw_prep_flag_machine.py(git mv,保留代表行)+
test_cw_prep_projection.py 两代表并入(2026-09-09 套件重建批 A,#7)。
其余历史锁已退役(git 可复活)。
设计出处:ADR-0596(T-159 方案 v2.1 收编)/ ADR-0599 / T-161 F2。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
    RunDeploy,
    SellBench,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    MandateState,
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)

_PHASE = (1, 3)


def _sess() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    return s


def _state(plane: int = 1, round_num: int = 3, gold: int = 2,
           ) -> GameState:
    return GameState(plane=plane, round_num=round_num, gold=gold, hp=100)


def _bc(name: str, slot: int, star: int = 1) -> BenchChar:
    """bench 件构造:注册表内名带阵营(部署谓词消费面),未登记名作
    燃料/填充(谓词经注册表缺读异常走保守放行,与生产同判据)。"""
    ch = CHARACTERS.get(name)
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions or ['?'])[0] if ch else '?')


def _set_s2(sess: StrategySession, state: GameState,
            missing: tuple[str, ...] = ('目标件',),
            in_shop: tuple[tuple[str, int], ...] | None = None) -> None:
    """经生产唯一写点 mandate.shop_wanted_defer 置 S2(禁直写字段:
    供给半环锁面纪律,README 测试纪律 13)。

    T-161 F2 起写点要求在店快照(「在店缺员 (名, 费用)」子集;T-161
    方案审 F2-1/F2-6,ADR-0599):缺省种「缺员在店且可负担」形态
    (名, 1)——cost 1 ≤ 缺省帧 gold 2,前件放行,既有用例聚焦各自
    原锁面。旧用例不种快照时被门 0′ 前件 hold 拦截属预期锁红(方案审
    §3 波及预估),按锁纪律改 helper 种快照,禁绕过前件保绿;前件拦截
    形态的锁面见 TestWantedPrecondition(显式传 in_shop=()/高费用)。
    """
    mandate.shop_wanted_defer(
        sess, state, list(missing),
        in_shop_snapshot=in_shop if in_shop is not None
        else tuple((m, 1) for m in missing if m))


# ===== 1. S1 重置白名单代表(deploy 落地对;§3.3,审 D1)=====

class TestS1ResetWhitelist:
    """路径 (i) 白名单 tag 落地的一对代表:真落地清 / 零落地(F1b)保。
    本文件仅保留 deploy 落地/零落地代表行(S2 交叉/纯金绝对项等兄弟行
    退役 git 可复活);三路径封闭枚举全貌见 git 历史本类。"""

    def _mk(self, s1: bool = True, s2: bool = True):
        sess = _sess()
        st = state_of(sess)
        if s1:
            st.cw4_shopped_phase = _PHASE
        if s2:
            _set_s2(sess, _state())
        return sess, st

    def cleared(self, st: MandateState) -> bool:
        return getattr(st, 'cw4_shopped_phase', None) is None

    def test_i_deploy_launch_landing_clears(self):
        """(i) 部署类:RunDeploy 落地 → 清键,遥测分键
        s1_reset_by_deploy_launch(route 类由动作类型承载,§5.1 M1 行)。"""
        sess, st = self._mk()
        mandate.mark_s1_route_check(sess, _state(), RunDeploy(),
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=True)
        assert self.cleared(st)
        assert st.cw4_counters.get('s1_reset_by_deploy_launch') == 1

    def test_i_deploy_noop_landing_keeps_latch(self):
        """F1b(T-167):RunDeploy progressed 但零落地(landed=False,执行器
        对 STATUS_NOOP 合法稳态的结构化判定)→ 不清闩、零遥测——no-op
        部署清闩 = 凭空再武装一次开店意图,交替活锁引擎本体(事故实证:
        25 次无信息量重开店)。landed 必传(落地审低②:删缺省防静默
        沿用旧「progressed 即落地」口径)。"""
        sess, st = self._mk()
        mandate.mark_s1_route_check(sess, _state(), RunDeploy(),
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=False)
        assert not self.cleared(st), 'no-op RunDeploy 必须保持开店闩(F1b)'
        assert not [k for k in st.cw4_counters
                    if k.startswith('s1_reset_by')], '零落地形态零清键遥测'


# ===== 2. S2 置位契约代表(经生产链;§5.2 迁移 A)=====

class TestS2Lifecycle:
    """本文件仅保留 S2 登记契约代表(席满残差经 decide_shop_action 写点
    置位);门 0/门 1/腿序/安全阀等生命周期兄弟行退役 git 可复活。"""

    def _comp(self) -> Comp:
        from sr_od.application.currency_war.kernel.cw_comps import (
            COMP_LIBRARY,
        )
        names = [c.name for c in COMP_LIBRARY
                 if getattr(c, 'core_chars', None)]
        return next(c for c in COMP_LIBRARY if c.name == names[0])

    def _members(self, comp: Comp) -> list[str]:
        ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars',
                                                  []) or [])
        return list(dict.fromkeys(ms))

    def test_registration_at_shop_residual(self):
        """置位经生产链:decide_shop_action 席满残差点(m2_retry_exhausted/
        bench_full_buy_abandon 同点,猎点 10)→ S2 = (phase, obligation,
        残差名单, 在店快照) + shop_wanted_deferred 计数。bench 满用 2★
        填充件(非燃料 ⇒ 腾席候选空,诚实停摆形态)。T-161 F2 起 S2 扩
        四元(ADR-0599):快照由写点同帧经 _shop_candidates 同源闭包计算
        (方案审 F2-6),本锁经生产链钉快照内容 = 在店缺员最便宜卡费用。"""
        from types import SimpleNamespace as _NS

        from sr_od.application.currency_war.kernel.cw_state import ShopCard
        comp = self._comp()
        missing = self._members(comp)[0]
        bench = [_bc(f'填充件{i}', slot=i, star=2)
                 for i in range(1, BENCH_CAPACITY + 1)]
        st = _state()
        st.gold = 2
        st.bench = bench
        # 店面播缺员 1★ 卡(cost 2)+ 一张无关卡:快照应只收缺员且取
        # 同名最便宜卡(M2 语义,不滤星)。
        st.shop = [ShopCard(x=1, faction='?', name=missing, cost=2, star=1),
                   ShopCard(x=2, faction='?', name='填充件1', cost=1, star=1)]
        sess = _sess()
        state_of(sess).target_comp = comp
        sess.active_strategies = ['买断制']   # ADR-0598 注入面迁移
        decide_shop_action(st, sess, _NS(ev_arm='skeleton_only'))
        s2 = state_of(sess).cw4_shop_wanted_pending
        assert s2 is not None and s2[0] == (st.plane, st.round_num) \
            and s2[1] == 'obligation' and missing in s2[2], \
            f'席满残差未置 S2:{s2}'
        assert len(s2) == 4, f'S2 载体形态漂移(应为四元):{s2}'
        assert s2[3] == ((missing, 2),), \
            f'在店快照与店面牌面不符(F2-6 同源口径):{s2[3]}'
        assert state_of(sess).cw4_counters.get('shop_wanted_deferred', 0) >= 1


# ===== 3. S2 门 0′ 前件 hold 代表(prep gate;T-161 F2)=====

class TestWantedPrecondition:
    """前件 = ∃m∈still_missing:m 在店快照 ∧ check_affordable(①号本体,
    金臂时点现读;方案审 T-161 §1.2/§1.3)。本文件仅保留 ① hold 形态
    代表(零发射 + S2 保留 + 不置放弃态);②-⑤ 兄弟行退役 git 可复活。"""

    def _bench_full(self, star: int = 1) -> list[BenchChar]:
        return [_bc(f'填充件{i}', slot=i, star=star)
                 for i in range(1, 10)]

    def test_not_in_shop_holds_and_keeps_s2(self):
        """① 不在店(空快照)→ hold:零发射(腾席腿不再为买不成的买入
        付出不可逆代价 = F2 缺陷关闭面)、S2 保留、不置放弃态、
        wanted_precond_hold 计 1。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state, in_shop=())
        out = mandate.wanted_closure_emit(sess, state, self._bench_full(),
                                          [], 0, 3)
        assert out == []
        st = state_of(sess)
        assert st.cw4_shop_wanted_pending is not None, '前件 hold 不得早清 S2'
        assert st.cw4_wanted_abandon_phase is None, 'hold 非放弃态'
        assert st.cw4_counters.get('wanted_precond_hold') == 1
        assert st.cw4_counters.get('wanted_leg_fuel_sell') is None


# ===== 4. F1b 落地判定退役墓碑 + 过渡期供给写死(T-167→T-223;批3a)=====

def test_run_deploy_dispatch_landing_retired_interim_failclosed(monkeypatch):
    """F1b 墓碑 + 过渡期锁(批3a):原「执行器具名常量结构化落地判定
    ``(ok, detail, landed)`` 三元组」随 T-223 端口回执退役——执行器不再
    输出成败与落地(落地判定归观察侧 reconcile,批5 E1 落地供给)。分派
    位改为 ``(机械摘要, 是否发出)``,STATUS 具名常量经 detail 显影透传
    (观察侧对账的供给面,禁丢);S1 清键门 landed 过渡期恒 False = 
    fail-closed(宁「该清不清」不「乱清」——T-167 交替活锁防线语义完整
    存活;红 = 执行器回执形态复活或 STATUS 显影断流)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_deploy as deploy_mod,
    )
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor

    statuses = {'next': deploy_mod.CwOpDeploy.STATUS_NOOP}

    class _StubDeploy:
        STATUS_DEPLOYED = deploy_mod.CwOpDeploy.STATUS_DEPLOYED
        STATUS_NOOP = deploy_mod.CwOpDeploy.STATUS_NOOP

        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            return SimpleNamespace(success=True,
                                   status=statuses['next'])

    monkeypatch.setattr(deploy_mod, 'CwOpDeploy', _StubDeploy)
    ctx = SimpleNamespace(
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        run_context=None, cw_match=None)
    ex = PrepActionExecutor(SimpleNamespace(screenshot=lambda: object()), ctx)
    # no-op 稳态:机械执行已发出,STATUS_NOOP 经 detail 显影透传
    detail, emitted = ex._execute_dispatch(RunDeploy())
    assert emitted is True, '组合 op 已派发 = 发出事实 True(非落地判定)'
    assert '部署' in detail and _StubDeploy.STATUS_NOOP in detail, (
        f'STATUS 显影文本必须透传(观察侧对账供给面,禁丢):{detail!r}')
    # 真部署:同样只透传 STATUS(成败/落地不再由执行器输出)
    statuses['next'] = deploy_mod.CwOpDeploy.STATUS_DEPLOYED
    detail2, emitted2 = ex._execute_dispatch(RunDeploy())
    assert emitted2 is True and deploy_mod.CwOpDeploy.STATUS_DEPLOYED in detail2
    # 端口无回执形态墓碑:execute 机械执行无返回(T-223);分派位不再
    # 产出落地判定位(F1b 结构化比对面退役)
    import inspect as _inspect
    dispatch_src = _inspect.getsource(PrepActionExecutor._execute_dispatch)
    assert 'landed_status_attr' not in dispatch_src, (
        '分派位不得再产出落地判定位(T-223;过渡期 landed=False 写死在 '
        'execute 的 S1 门调用位)')
    assert ', emitted' in dispatch_src or 'emitted' in dispatch_src, (
        '分派位返回形态 = (机械摘要, 是否发出)——发出事实非落地判定')
    # S1 门过渡期供给写死:landed=False(fail-closed,批5 观察侧接管)
    exec_src = _inspect.getsource(PrepActionExecutor.execute)
    assert 'landed=False' in exec_src, (
        'S1 清键门过渡期必须恒传 landed=False(fail-closed;批5 观察侧'
        ' reconcile 落地事实接管后随批改写)')


# ===== 5. 备战投影金账(自 test_cw_prep_projection.py 并入;F2)=====


def _director() -> CwScreenPrep:
    # _project_prep_obs 纯计算不触 self 状态 → 无初始化实例即够
    return object.__new__(CwScreenPrep)


def _proj_obs(state: GameState | None = None) -> PrepObservation:
    return PrepObservation(state=state, free_bench_slots=2)


def test_sellbench_projection_adds_sell_refund_gold() -> None:
    """卖出后投影金 = 原金 + sell_refund(star, bench_char_cost)——与
    simulate 卖出分支同式(单一源公式);下一帧 funding_support 等金位
    判据读 ``obs.state.gold`` 即读到涨后金。"""
    d = _director()
    bc = BenchChar(slot=3, char_id='希儿', star=1)
    obs = _proj_obs(GameState(gold=10))
    obs.bench_chars = [BenchChar(slot=1, char_id='甲', star=1), bc]
    out = d._project_prep_obs(SellBench(slot=3), obs)
    assert out is not None
    assert [b.slot for b in out.bench_chars if b is not None] == [1]
    assert out.free_bench_slots == 3
    expect = 10 + sell_refund(bc.star, bench_char_cost(bc))
    assert out.state is not None and out.state.gold == expect


def test_sellbench_projection_state_none_skips_gold() -> None:
    """state 缺失帧(heavy 未刷新)⇒ 金账跳过不造值,槽位摘除照常
    (保守侧 = 低估回金,下一 heavy 重读对账)。"""
    d = _director()
    obs = _proj_obs(None)
    obs.bench_chars = [BenchChar(slot=2, char_id='乙', star=1)]
    out = d._project_prep_obs(SellBench(slot=2), obs)
    assert out is not None
    assert out.state is None
    assert out.bench_chars == []
