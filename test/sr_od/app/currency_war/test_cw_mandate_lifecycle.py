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
test_cw_prep_projection.py 两代表并入(2026-09-09 套件重建批 A,#7);
备战环席满让路门(球体延迟门)全套自 test_cw_t297_sphere_defer_gate.py
并入(2026-09-12 归并批;旧球谓词锁的语义后继,决策记录 = ADR-0642)。
其余历史锁已退役(git 可复活)。
设计出处:ADR-0596(T-159 方案 v2.1 收编)/ ADR-0599 / T-161 F2。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    Comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge as _bsb,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    PrepObservation,
    RunDeploy,
    SellBench,
    StartBattle,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    CwWorkFrame,
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    MandateState,
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from test.sr_od.app.currency_war._cw_helpers import cw4_feed

_PHASE = (1, 3)


def _sess(target=None) -> StrategySession:
    """target 非 None 时置 target_comp(备战球门簇共用;归并批统一)。"""
    s = StrategySession()
    state_of(s).cw4_counters = {}
    if target is not None:
        state_of(s).target_comp = target
    return s


def _state(plane: int = 1, round_num: int = 3, gold: int = 2,
           ) -> CwWorkFrame:
    return CwWorkFrame(plane=plane, round_num=round_num, gold=gold, hp=100)


def _bc(name: str, slot: int, star: int = 1) -> BenchChar:
    """bench 件构造:注册表内名带阵营(部署谓词消费面),未登记名作
    燃料/填充(谓词经注册表缺读异常走保守放行,与生产同判据)。"""
    ch = CHARACTERS.get(name)
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions or ['?'])[0] if ch else '?')


def _set_s2(sess: StrategySession, state: CwWorkFrame,
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
            _set_s2(sess, _bsb(_state()))
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

        from sr_od.application.currency_war.kernel.cw_vocab import ShopCard
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
        from test.sr_od.app.currency_war._cw_helpers import cw4_bs
        decide_shop_action(cw4_bs(st, sess), sess,
                           _NS(ev_arm='skeleton_only'))
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
        _set_s2(sess, _bsb(state), in_shop=())
        out = mandate.wanted_closure_emit(sess, _bsb(state), self._bench_full(),
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


def _director(sess) -> CwScreenPrep:
    """投影纯计算 + 容器写口经 ``_session()`` 取 session 单例 → 桩注入
    (object.__new__ 免 SrContext,余 self 状态不触)。"""
    d = object.__new__(CwScreenPrep)
    d._session = lambda: sess
    return d


def test_sellbench_projection_adds_sell_refund_gold() -> None:
    """卖出后投影金 = 原金 + sell_refund(star, bench_char_cost)——与
    simulate 卖出分支同式(单一源公式);金账写点 = session 容器 gold 域
    (容器化段 2:黑板帧 state 复制腿退役,写口 apply_prep_action_logic
    单一源),消费面读容器即读到涨后金。"""
    d = _director(_sess())
    bc = BenchChar(slot=3, char_id='希儿', star=1)
    # 容器 bench 喂入 = pad 形(合成按列表位映射物理槽;希儿须落槽 3)。
    cw4_feed(d._session(), CwWorkFrame(
        gold=10, bench=[BenchChar(slot=1, char_id='甲', star=1), None, bc]))
    obs = PrepObservation(
        bench_chars=[BenchChar(slot=1, char_id='甲', star=1), bc],
        free_bench_slots=2)
    out = d._project_prep_obs(SellBench(slot=3), obs)
    assert out is not None
    assert [b.slot for b in out.bench_chars if b is not None] == [1]
    assert out.free_bench_slots == 3
    expect = 10 + sell_refund(bc.star, bench_char_cost(bc))
    assert board_state_of(d._session()).gold.value == expect


def test_sellbench_projection_state_none_skips_gold() -> None:
    """容器 gold 未读(None)⇒ 金账跳过不造值,黑板槽位摘除照常
    (保守侧 = 低估回金,下一 heavy 重读对账;写口输入域 None 语义 =
    域级独立跳写)。"""
    sess = _sess()          # 未喂帧:容器 gold 未观察(None)
    d = _director(sess)
    obs = PrepObservation(
        bench_chars=[BenchChar(slot=2, char_id='乙', star=1)],
        free_bench_slots=2)
    out = d._project_prep_obs(SellBench(slot=2), obs)
    assert out is not None
    assert board_state_of(sess).gold.value is None
    assert out.bench_chars == []

# ===== 备战环席满让路门(球体延迟门;自 test_cw_t297_sphere_defer_gate.py 并入,ADR-0642)=====

#: 守卫阈值引用值(无进展守卫,ADR-0554;cw_loop.PREP_NO_PROGRESS_ROUNDS
#: = 3,不 import 重模块,锁只锚「K 与门行为 ≤ 2 < 3」关系)。
_GUARD_ROUNDS = 3


def _plain_bc(name: str, slot: int, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


class _Pt:
    """球元素坐标载体(read_reward_spheres [(color, Point, r)] 对位)。"""

    def __init__(self, x: int = 100, y: int = 100) -> None:
        self.x, self.y = x, y


def _spheres(n: int) -> list:
    """事故同构球面(blue×6+gray×2 缩放版;色在本门默认态不参与判定)。"""
    colors = ('blue', 'gray')
    return [(colors[i % 2], _Pt(300 + 60 * i, 990), 3) for i in range(n)]


def _prep_state(gold: int = 99, round_num: int = 3,
           bench: list | None = None, deployed: list | None = None) -> CwWorkFrame:
    """决策黑板(CwWorkFrame.bench/deployed 必须同形接线:T-32 空板止损
    守卫对 state.deployed 现读,漏接线 = 腾席卖出腿结构性哑火,假红)。"""
    gs = CwWorkFrame(gold=gold, level=3, round_num=round_num, hp=60)
    gs.plane = 1
    gs.bench = list(bench or [])
    gs.deployed = list(deployed or [])
    return gs


def _obs(bench: list, deployed: list,
         spheres: list, free: int) -> PrepObservation:
    """黑板观察帧(纯视觉/占用域;局内事实经 cw4_feed 喂 session 容器,
    obs.state 视图槽已随 prep 链容器化段 2 退役)。"""
    return PrepObservation(
        bench_chars=bench, deployed_chars=deployed,
        spheres=list(spheres), boxes=[], tomes=[],
        free_bench_slots=free, deploy_vacancy=0)


def _emit(sess: StrategySession, obs: PrepObservation) -> list:
    return entry.emit(obs, SimpleNamespace(), sess, None,
                      registry=MandateV1Strategy().registry)


def _run_len_click_spheres(batches: list[list]) -> int:
    """连续 ClickSpheres 决策批的最大连击长度(§3.4 弱判据观测量)。"""
    best = run = 0
    for batch in batches:
        if any(isinstance(e.action, ClickSpheres) for e in batch):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


# ===== 场景语料 =====

def _stuck_pair(gold: int = 0, round_num: int = 3, spheres_n: int = 8):
    """格2 稳态搁浅语境:席满 9×3★(无 1★ 燃料 → 下游无腾席卖出腿)
    + 板满编(state.max_units()@lv3 = 3,金 0 无必花)→ 让路帧下游
    稳态无动作 = ⑥ StartBattle。返回 (sess, obs 构造器)。"""
    sess = _sess()
    bench = [_plain_bc(f'高价{i}', slot=i, star=3) for i in range(1, 10)]
    deployed = [_plain_bc(f'板件{i}', slot=i, star=2) for i in range(1, 4)]

    def _mk(**overrides) -> PrepObservation:
        st = _prep_state(gold=overrides.get('gold', gold),
                    round_num=overrides.get('round_num', round_num),
                    bench=bench, deployed=deployed)
        cw4_feed(sess, st)   # 局内事实进 session 容器(决策面容器读口)
        return _obs(bench, deployed,
                    _spheres(overrides.get('spheres_n', spheres_n)), free=0)

    return sess, _mk


def _fuel_pair():
    """格1 免卖腾席语境:席满 9×1★ 燃料 + 锁线缺员(目标线成员全不在
    手)→ 让路帧下游 M2→M4 环发常规链腾席卖出腿。"""
    comps = [c for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    sess = _sess(target=comps[0])
    bench = [_plain_bc(f'燃料件{i}', slot=i, star=1) for i in range(1, 10)]
    deployed = [_plain_bc('板上件锚', slot=1, star=2)]

    def _mk(**overrides) -> PrepObservation:
        st = _prep_state(gold=overrides.get('gold', 99),
                    round_num=overrides.get('round_num', 3),
                    bench=bench, deployed=deployed)
        cw4_feed(sess, st)
        return _obs(bench, deployed,
                    _spheres(overrides.get('spheres_n', 8)), free=0)

    return sess, _mk


# ===== 1. 席满让路行为锁(§5.3 主锁)=====

class TestBenchFullYieldGate:

    def test_first_frame_single_probe_then_yield(self):
        """搁浅情节首环 = 单探针(同 prep_spheres 发射形态);次环起让路
        fall-through,决策批零 ClickSpheres(格2 稳态 → ⑥ StartBattle)。"""
        sess, mk = _stuck_pair()
        out1 = _emit(sess, mk())
        assert len(out1) == 1
        assert isinstance(out1[0].action, ClickSpheres)
        assert out1[0].reason == 'prep_spheres'
        out2 = _emit(sess, mk())
        assert not any(isinstance(e.action, ClickSpheres) for e in out2)
        assert [type(e.action) for e in out2] == [StartBattle], \
            '格2 稳态让路批应为 ⑥ StartBattle(空批合法交回)'
        ct = state_of(sess).cw4_counters
        assert ct['sphere_defer_streak'] == 2
        assert ct['sphere_defer_yield'] == 1
        # 死码块现状不可达:sphere_blocked_bench_full 恒零写
        assert 'sphere_blocked_bench_full' not in ct

    def test_yield_persists_and_streak_climbs(self):
        """签名不变 → 不再探针,让路持续,streak 逐帧爬升(每让路帧
        yield 计数 +1,零静默)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())          # 探针
        batches = [_emit(sess, mk()) for _ in range(3)]
        for batch in batches:
            assert not any(isinstance(e.action, ClickSpheres)
                           for e in batch)
        ct = state_of(sess).cw4_counters
        assert ct['sphere_defer_streak'] == 4
        assert ct['sphere_defer_yield'] == 3

    def test_weak_guarantee_run_length_le_k(self):
        """§3.4 弱判据:席满形态连续 ClickSpheres 决策批序列 ≤ K=1
        < 守卫阈值 3——球分支垄断性活锁消除(不主张恒指纹全局有界:
        让路后 OpenShop/RunDeploy 恒指纹残余由守卫按设计停机)。"""
        sess, mk = _stuck_pair()
        batches = [_emit(sess, mk()) for _ in range(6)]
        run = _run_len_click_spheres(batches)
        assert run == entry.SPHERE_DEFER_PROBE_K
        assert run < _GUARD_ROUNDS


# ===== 2. 席自由行为等价锁(B5;§5.2 锚 3)=====

class TestBenchFreeEquivalence:

    def test_free_bench_clicks_unchanged_multi_frame(self):
        """free>0:逐帧恒 ClickSpheres 同形态(max_k=权界/球数,reason
        prep_spheres,mandate=True),动作序列与状态迁移与改前一致;
        streak 恒 0、零让路计数(单帧偶发失败由既有逐帧重试自愈)。"""
        sess = _sess()
        st = _prep_state()
        cw4_feed(sess, st)
        obs = _obs([], [], _spheres(8), free=2)
        for _ in range(3):
            out = _emit(sess, obs)
            assert len(out) == 1
            assert isinstance(out[0].action, ClickSpheres)
            assert out[0].action.max_k == min(3, 8)
            assert out[0].reason == 'prep_spheres'
            assert out[0].mandate is True
        ct = state_of(sess).cw4_counters
        assert ct['sphere_defer_streak'] == 0
        assert 'sphere_defer_yield' not in ct

    def test_seat_freed_resets_and_recovers_clicking(self):
        """成效重置·席自由化腿:搁浅情节中席自由化(free>0)→ streak
        归零;再搁浅 = 新情节从探针重新起算(门语义:自愈形态恢复点击
        不让路,#16 自然回补真实成立)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())                      # 探针 streak=1
        _emit(sess, mk())                      # 让路 streak=2
        bench8 = [_plain_bc(f'高价{i}', slot=i, star=3) for i in range(1, 9)]
        deployed3 = [_plain_bc(f'板件{i}', slot=i, star=2) for i in range(1, 4)]
        st = _prep_state(bench=bench8, deployed=deployed3)
        cw4_feed(sess, st)
        out_free = _emit(sess, _obs(bench8, deployed3, _spheres(8),
                                    free=1))
        assert isinstance(out_free[0].action, ClickSpheres)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 0
        out_again = _emit(sess, mk())          # 再搁浅:新情节首环
        assert isinstance(out_again[0].action, ClickSpheres)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 1


# ===== 3. 批构成锁(下游真实产出面;禁锁死「零 SellBench」)=====

class TestYieldBatchComposition:

    def test_yield_batch_carries_regular_chain_sell_leg(self):
        """格1:席满 ∧ 免卖腾席语境(锁线缺员 + 1★ 燃料在场)→ 让路帧
        批 = 常规链自然产出,含 M4 腾席卖出腿(mandate.py M2→M4 环,
        m4_fuel_sell)——常规链恢复求值即让路的设计收益面;本锁明文
        断言卖出腿**在场**,禁反向锁死「零 SellBench」(r2-P1)。"""
        sess, mk = _fuel_pair()
        out1 = _emit(sess, mk())
        assert isinstance(out1[0].action, ClickSpheres)   # 探针前置
        out2 = _emit(sess, mk())
        assert not any(isinstance(e.action, ClickSpheres) for e in out2)
        m4_legs = [e for e in out2
                   if isinstance(e.action, SellBench)
                   and e.reason == 'm4_fuel_sell']
        assert m4_legs, f'让路批缺常规链 M4 腾席卖出腿:\
{[type(e.action).__name__ for e in out2]}'

    def test_yield_batch_quiescent_face_is_start_battle(self):
        """格2:席满 ∧ 稳态无动作 → 让路批 = ⑥ StartBattle(空批合法
        交回,cw_screen_prep 消费契约;弃球 ≤ 弃局)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        out2 = _emit(sess, mk())
        assert [type(e.action) for e in out2] == [StartBattle]


# ===== 4. 成效载体三元组重置两腿(§7.3 实施批终定)=====

class TestProgressSigReset:

    def test_sphere_count_change_resets_episode(self):
        """重置腿·球计数:搁浅情节中球计数变化(一次成功点开,B8 方向)
        → 签名变 → streak 重开 → 次环再探针(连续收球不被打断,宁多
        收球在门语义层保住)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        _emit(sess, mk())                          # streak=2 让路中
        out = _emit(sess, mk(spheres_n=7))         # 一球被点开
        assert isinstance(out[0].action, ClickSpheres)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 1

    def test_round_advance_resets_episode(self):
        """重置腿·轮次:轮次推进(经战斗一轮 = 新备战语境)→ 签名变 →
        streak 重开再探针。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        _emit(sess, mk())
        out = _emit(sess, mk(round_num=4))
        assert isinstance(out[0].action, ClickSpheres)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 1

    def test_unchanged_face_does_not_reset(self):
        """不重置腿:三分量全不变(纯点击失败,机制性拒绝)→ streak
        持续爬升,不再探针(门不被噪声误开)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        _emit(sess, mk())
        _emit(sess, mk())
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 3
        out = _emit(sess, mk())
        assert not any(isinstance(e.action, ClickSpheres) for e in out)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 4

    def test_sig_carrier_is_int(self):
        """载体面:签名存 cw4_counters 为 int(sim 轮差分逐值 int() 算术,
        sim/engine_p1.py;禁 tuple/str 破坏数值账本面)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        sig = state_of(sess).cw4_counters['sphere_defer_progress_sig']
        assert isinstance(sig, int)


# ===== 5. K 预注册锁(§3.3;改值须回审)=====

class TestProbeKPreregistration:

    def test_k_is_preregistered_one(self):
        assert entry.SPHERE_DEFER_PROBE_K == 1, \
            'K 预注册值被改:须回方案审(§3.3 夹逼依据与守卫竞速约束)'

    @pytest.mark.parametrize('k', [1, 2])
    def test_k_within_guard_race_safe_side(self, k, monkeypatch):
        """竞速安全侧:K∈{1,2}(守卫常量 3 夹逼可行域)→ 连击 ≤ 2
        < 3,让路环先于守卫触发环到来。"""
        monkeypatch.setattr(entry, 'SPHERE_DEFER_PROBE_K', k)
        sess, mk = _stuck_pair()
        batches = [_emit(sess, mk()) for _ in range(6)]
        assert _run_len_click_spheres(batches) == k
        assert k < _GUARD_ROUNDS

    def test_k_three_would_meet_guard_counterfactual(self):
        """反事实(K=3,可行性域外):连击 = 3 == 守卫阈值——让路环恰逢
        守卫触发环,上界论证的「K≤2」边界在纯函数级显影(非注册值,
        仅锚边界存在性)。"""
        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(entry, 'SPHERE_DEFER_PROBE_K', 3)
            sess, mk = _stuck_pair()
            batches = [_emit(sess, mk()) for _ in range(6)]
            assert _run_len_click_spheres(batches) == _GUARD_ROUNDS
        finally:
            monkeypatch.undo()


# ===== 6. 死码保留结构锁(ADR-0596 §4.9③ 结构保活;§7.1 终态)=====

class TestDeadArmKeepAlive:

    def _source(self) -> str:
        return Path(entry.__file__).read_text(encoding='utf-8')

    def test_old_predicate_second_leg_and_fuel_arm_kept(self):
        """旧谓词第二腿(_sf_occupied 判定)+ 腾席臂(fuel 候选→
        m4_fuel_sell 发射→blocked 计数)保留原位,且不可达标注在案
        (读者陷阱显影);结构删除必须先走退役申报(ADR-0642 后果)。"""
        src = self._source()
        assert 'SPHERE_OCCUPYING_COLORS' in src
        assert '_sf_occupied' in src
        assert "'m4_fuel_sell'" in src
        assert 'sphere_blocked_bench_full' in src
        assert '当前不可达' in src and '结构' in src and '保活' in src

    def test_old_unconditional_two_leg_or_retired(self):
        """门重写真实落位:旧无条件两腿 OR(`free>0 or not occupied`
        恒提前 return = 活锁主根)不得回归。"""
        src = self._source()
        assert '_sf_free > 0 or not _sf_occupied' not in src
        assert 'SPHERE_DEFER_PROBE_K' in src
        assert 'sphere_defer_yield' in src

    def test_bench_capacity_invariant_untouched(self):
        """席满语境基准:本文件语料 bench 构形 = BENCH_CAPACITY 满席
        (9),与生产席满形态同构(防语料漂移使门锁失真)。"""
        assert BENCH_CAPACITY == 9
