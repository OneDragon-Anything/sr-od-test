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

import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    Comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    committed_authority,
    drive_intention,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    PrepObservation,
    RunDeploy,
    SellBench,
    StartBattle,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY as _REG,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_transition import CommitSignals
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    CloseShop,
    CwSimFrame,
    LevelUpShop,
    RefreshShop,
    ShopCard,
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
    assemble,
    hoard_consumer_domain,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.contracts import (
    Snapshot,
    SubstateClassification,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    StrategyState,
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_box,
    cw4_bs,
    cw4_feed,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_box as _bsb,
)

_PHASE = (1, 3)


def _sess(target=None) -> StrategySession:
    """target 非 None 时置 target_comp(备战球门簇共用;归并批统一)。"""
    s = StrategySession()
    state_of(s).cw4_counters = {}
    if target is not None:
        state_of(s).target_comp = target
    return s


def _state(plane: int = 1, round_num: int = 3, gold: int = 2,
           ) -> CwSimFrame:
    return CwSimFrame(plane=plane, round_num=round_num, gold=gold, hp=100)


def _bc(name: str, slot: int, star: int = 1) -> BenchChar:
    """bench 件构造:注册表内名带阵营(部署谓词消费面),未登记名作
    燃料/填充(谓词经注册表缺读异常走保守放行,与生产同判据)。"""
    ch = CHARACTERS.get(name)
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions or ['?'])[0] if ch else '?')


def _set_s2(sess: StrategySession, state: CwSimFrame,
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

    def cleared(self, st: StrategyState) -> bool:
        return getattr(st, 'cw4_shopped_phase', None) is None

    def test_i_deploy_launch_landing_clears(self):
        """(i) 部署类:RunDeploy 落地 → 清键,遥测分键
        s1_reset_by_deploy_launch(route 类由动作类型承载,§5.1 M1 行)。"""
        sess, st = self._mk()
        mandate.mark_s1_route_check(sess, _bsb(_state()), RunDeploy(),
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
        mandate.mark_s1_route_check(sess, _bsb(_state()), RunDeploy(),
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
    cw4_feed(d._session(), CwSimFrame(
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
           bench: list | None = None, deployed: list | None = None) -> CwSimFrame:
    """决策黑板(CwSimFrame.bench/deployed 必须同形接线:T-32 空板止损
    守卫对 state.deployed 现读,漏接线 = 腾席卖出腿结构性哑火,假红)。"""
    gs = CwSimFrame(gold=gold, level=3, round_num=round_num, hp=60)
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


# ==================== 方向层/息线哨兵/committed 对拍(自 migration_direction_layer 归并) ====================
# hoard 可信位(投影失败帧 → 保守域)/息线单一源(全仓属性读点=0)/意向状态机
# 每 game-round 恰一次驱动/ist 跨局零残留/局23 哨兵(2★压库件无退款背书/
# 满金不破息线)/committed 翻真谓词逐帧对拍。行为断言零改动。

_DL_SRC = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
        / 'currency_war')


def _dl_snapshot(plane: int = 1, round_num: int = 2) -> Snapshot:
    return Snapshot(
        classification=SubstateClassification(
            name='prep_shop', evidence=('test',), confident=True),
        plane=plane, round_num=round_num, level=3, gold=40, gold_trusted=True,
        free_bench_slots=3, deploy_vacancy=1, shop_open=False,
    )


def _dl_state(plane: int = 1, round_num: int = 2, gold: int = 40) -> CwSimFrame:
    st = CwSimFrame()
    st.plane = plane
    st.round_num = round_num
    st.gold = gold
    st.level = 3
    return st


# ----------------------------------------------------- D1 hoard 可信位

def test_d1_hoard_readable_normal_frame():
    """正常帧:ist 未锁 → hoard = ⑤兜底域(fallback),可信位为真。

    「空集双义」分离的关键:正常帧 readable 恒 True(含 fallback 非空域
    与真空集),失败帧才 False——消费侧语义不因实现细节抖动。
    """
    sess = StrategySession()
    state_of(sess).v3_intention = IntentionState()
    turn = assemble(_dl_snapshot(), sess)
    assert turn.direction.hoard_readable is True
    assert isinstance(turn.direction.hoard, frozenset)


def test_d1_mutation_probe_projection_failure_conservative_domain(monkeypatch):
    """变异探针(D1 验收判据):hoard_target_set 抛错 → 消费域 = 保守域。

    静默退空集 = 锁线局囤货方向消失一帧、买侧按无方向放行——本锁钉住
    「投影失败」与「真无目标」表示分离(hoard_readable 位)。
    """
    import sr_od.application.currency_war.kernel.cw_intention as cw_intention_mod

    sess = StrategySession()
    state_of(sess).v3_intention = IntentionState()

    def _boom(_dl_state, _ist):
        raise RuntimeError('注入:投影失败')

    monkeypatch.setattr(cw_intention_mod, 'hoard_target_set', _boom)
    turn = assemble(_dl_snapshot(), sess)
    d = turn.direction
    assert d.hoard_readable is False          # 失败帧显式暴露
    full = frozenset({'任意件A', '任意件B'})
    assert hoard_consumer_domain(d, full) == full     # 保守域,非空集放行
    ok = replace(d, hoard_readable=True)
    assert hoard_consumer_domain(ok, full) == ok.hoard  # 正常帧走目标集


# ----------------------------------------------------- D2 缺供给保守侧
# (原 test_d2_missing_supply_falls_conservative 删并:缺供给保守侧现由
#  test_cw_session_separation::test_none_state_criterion_faces_return_
#  defaults 直锁(committed_authority(None, bare) is False)+ 本文件
#  对拍锁帧 1-2 承载。原并入目标 test_cw_w620_migration_b1 本体已随
#  统一迁移批删除,死指针收口重锚。重复构成删并理由(README 纪律 8)。)


# ----------------------------------------------------- W629-R2 镜像雷锁


def test_d3_grep_lock_no_interest_floor_attribute_reads():
    """grep 锁(D3):``registry/reg.interest_floor`` 属性读点全仓 = 0。

    豁免:registry.py 定义处(方法本体/override 字段/注释);调用形态
    ``.interest_floor()`` 不匹配(带括号),裸属性读(无括号)即违规。
    """
    pat = re.compile(r'\b(?:registry|reg)\.interest_floor\b(?!\()')
    offenders = {}
    for path in _DL_SRC.rglob('*.py'):
        hits = len(pat.findall(path.read_text(encoding='utf-8')))
        if hits:
            offenders[path.name] = hits
    assert set(offenders) <= {'registry.py'}, offenders


# ----------------------------------------------------- P7 驱动点契约 + P6 注入

def test_p7_drive_intention_idempotent_per_round():
    """P7:同 (plane, round) 重入驱动 = 幂等(键守卫),跨轮才推进。"""
    sess = StrategySession()
    st = _dl_state(plane=1, round_num=2)
    # W6 波3:drive_intention 切容器签名,CwSimFrame 帧经一次性装箱。
    drive_intention(cw4_box(st), sess)
    assert state_of(sess).v3_intention_key == (1, 2)
    ev1 = state_of(sess).v3_intention.last_event
    drive_intention(cw4_box(st), sess)  # 同轮重入:不重复驱动
    assert state_of(sess).v3_intention_key == (1, 2)
    assert state_of(sess).v3_intention.last_event == ev1
    drive_intention(cw4_box(_dl_state(plane=1, round_num=3)), sess)   # 跨轮:推进
    assert state_of(sess).v3_intention_key == (1, 3)


def test_p6_registry_injection_reaches_state_machine():
    """P6 注入分歧探针:注入臂与缺省臂必须出现受控分歧,无分歧 = 注入链断。

    旋钮 = line_env_lock_min_round(环境判据观察期):调大 = 判据本轮不辖
    → 对抗环境帧缺省臂缓锁、注入臂落锁——两臂 ist 分歧即注入链可达证。
    【夹具演进(经济冻结批)】原 plane=2 unlocked 帧:旧形态缺省臂保持
    unlocked;现 P2 unlocked 帧被强制移交重锁域接管(目标不空窗
    语义,载体 = test_cw_line_feasibility.py P2 移交组),与旋钮无关
    → 不再承载分歧。改用 weak 帧(撤销机器在册态,移交不辖,「直至
    新信号」语义保留)。
    """
    from sr_od.application.currency_war.kernel.cw_intention import update_intention
    st = _dl_state(plane=2, round_num=1)   # P2:comp 锁定通道(P1 配方锁区不锁 comp)
    st.enemy_affixes = ['净化身心']            # 对抗词缀(万敌强环境不命中)
    st.shop = [SimpleNamespace(name='万敌')]   # ③核心卡信号可见
    reg_def = _REG
    reg_inj = replace(_REG, line_env_lock_min_round=99)
    ist_def = update_intention(cw4_box(st),
                               IntentionState(phase='weak', weak_comp='万敌单C'),
                               None, registry=reg_def)
    ist_inj = update_intention(cw4_box(st),
                               IntentionState(phase='weak', weak_comp='万敌单C'),
                               None, registry=reg_inj)
    assert ist_def.locked_comp == ''            # 缺省臂:环境判据缓锁(weak 保持)
    assert ist_inj.locked_comp != ''            # 注入臂:判据不辖 → 落锁


def test_p4_ist_zero_residue_across_matches():
    """P4:跨局 ist 零残留——每局新建 StrategySession,ist/驱动键从零开始。"""
    sess = StrategySession()
    drive_intention(cw4_box(_dl_state()), sess)
    assert state_of(sess).v3_intention is not None and state_of(sess).v3_intention.evicted == set()
    fresh = StrategySession()   # 新局(构造性重置)
    assert state_of(fresh).v3_intention is None      # 策略器字段迁 MandateState
    assert state_of(fresh).v3_intention_key is None


# ----------------------------------------------------- 哨兵锁:局23 型帧
# 复活说明:原 test_sentinel_ju23_frame_releases_on_new_stack 以「并入
# w633」为名删除,并入目标经 2026-09-03 歼击战核查不存在 = 指针失真。
# 旧「release 帧」形态随 DP 姿态核/泄息指令死链退役(w633 同批注记),
# dp_posture='release' 遥测标签写端已死、不可锁;复活语义改锁现行
# mandate_v1 商店线决策面的三件事:息线供给恒等 / 不死守可辨收敛 /
# 金位不破息线。统一帧形状 = 列车同行线成型(全员 2★ 上场,stop_buy
# 成立)+ bench 空 + level 6(4 费档在档窗内)+ P1 局中帧。

_JU23_COMP = next(c for c in COMP_LIBRARY if c.name == '列车同行')
_JU23_STOCK_COST = 4     # 压库件卡费(档窗内;与注册表 cost 解耦)


def _sc(name: str, cost: int = _JU23_STOCK_COST, star: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=star)


def _ju23_frame(gold: int, shop: list[ShopCard] | None = None) -> CwSimFrame:
    """局23 型帧:线成型(全员 2★ 上场)+ 备战空 + P1 局中。"""
    return CwSimFrame(
        plane=1, round_num=4, gold=gold, level=6, hp=80,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=m, faction='仙舟罗浮',
                            star=2)
                  for i, m in enumerate(line_members(_JU23_COMP))],
        bench=[None] * BENCH_CAPACITY,
        shop=shop if shop is not None else [],
        node_type='battle', board={})


def _ju23_session() -> StrategySession:
    sess = StrategySession()
    state_of(sess).target_comp = _JU23_COMP
    return sess


# (test_ju23_supply_identity_gstar_and_s_reserve_boundary 已删 2026-09-08
#  覆盖对账:息线供给恒等两面均由主题文件承载——g*==50 = saturation_line(5)
#  ==50(test_cw_statefn)× cap_resolved_of_session(裸真 session)==DEFAULT
#  (test_cw_session_separation),组合面另经 test_cw_launch_arbitrage 全域
#  等价扫现算;s_reserve==50 金约束边界(49 拒/50 过)= test_cw_realizable_interest_floor::
#  test_m6_p56_reject_counter 同边界对 + test_stockpile_s_reserve_boundary
#  位移面超集。README 纪律 7 跨文件等价择一。)


# (test_ju23_stock_match_buys_and_empty_shop_close_discernible 已删
#  2026-09-08 覆盖对账:店空必花域帧 → LevelUpShop(m3_batch:must_spend)
#  终结面 = test_cw_mandate_v1::test_shop_visit_sets_latch 同构造帧
#  (_visit_state ≡ 本文件 _ju23_frame(100, []),gold/level/deployed 逐字段
#  一致)同断言;shop_visit_idle_gold==1 = test_cw_shop_line::
#  test_d_p2idle_idle_gold_counter,shop_r1_no_chaseable_member==1 =
#  test_cw_must_spend_zone::test_whitelist_empty_shop_cap_top_zero_consume;
#  stockpile_buy 放行面 = test_cw_shop_line::test_stockpile_face_m6_
#  opens_with_frame_window。README 纪律 7 跨文件择一。)


def test_ju23_star2_stock_card_has_no_refund_backing_no_spend():
    """局23 帧 2★ 压库件:无全额可退背书 ⇒ 端到端零支出。

    stockpile_buy 与 dominance 同以 refund_full_star_ok 为背书门:
    2★ 件两条买面都不可发射,溢余滞留(不放行)而非带病买——
    锁「背书门在局23 帧端到端成立」,非单位锁复述。
    """
    cfg = SimpleNamespace(ev_arm='full')
    sess = _ju23_session()
    act = decide_shop_action(cw4_bs(_ju23_frame(
        100, [_sc('花火', star=2)]), sess), sess, cfg)
    assert not isinstance(act, (BuyCard, RefreshShop))
    # 必花域末位 L3(店空/2★ 无背书 ⇒ 全层无对象)
    assert isinstance(act, LevelUpShop)
    assert act.auth_basis == 'm3_batch:must_spend'


# (test_ju23_liquid_refund_shifts_s_reserve_down 已删 2026-09-08 覆盖对账:
#  断言面 = stockpile_buy 金约束边界在 s_reserve=48 的实例,与
#  test_cw_realizable_interest_floor::test_stockpile_s_reserve_boundary(s_reserve=47,差 1 拒/
#  边界过/差 2 过)同谓词等价,常量差异零新语义;docstring 所称「活期退金
#  投影进 s_reserve」的算术不在断言路径(s_reserve 是测试手抄入参,
#  stockpile_buy 不算投影)——与 DEBTS D21 删 test_liquid_refund_excludes_
#  material 同判据(rule 18 docstring≠断言面)。投影值收缩的 decide 级
#  真锁缺口维持 D21 记账。)


def test_ju23_full_surface_gold_never_breaks_interest_line():
    """金位不破息线(端到端复合):0-100 金全决策面逐帧走真函数。

    每个起始金位完整走一次店内访问(动作后真值回写再判,ADR-0517
    §8.1 口径):任一 BuyCard/RefreshShop 花后金 ≥ s_reserve(本帧形状
    = 50);息线下(≤50)整访问零支出(无误清);每访问都以 CloseShop
    收束且有界迭代(无死守环)。
    T-115 适配(ADR-0580):店卡改用真无关件(局23杂件,非④放行集/
    registry 核心)——原探针花火 ∈ TRANSITION_PACK carry,未锁双轨
    P1 帧会被 ④转线放行臂在息线下买入(1★ 全额退 = 可逆资产,裁定
    408② 的有意取舍);「息线下零支出」不变式对④放行件域已被裁定
    取代,④例外语义由 test_cw_locked_buy_membership_split 重推锁
    承载,本锁在真无关件域保持。"""
    cfg = SimpleNamespace(ev_arm='full')
    for gold0 in range(0, 101):
        st = _ju23_frame(gold0, [_sc('局23杂件')])
        sess = _ju23_session()
        for _ in range(15):
            act = decide_shop_action(cw4_bs(st, sess), sess, cfg)
            if isinstance(act, BuyCard):
                cost = act.card.cost if act.card.cost else 3
                if gold0 <= 50:
                    assert st.gold - cost >= 50, (gold0, st.gold, cost)
                st.gold -= cost
                st.shop = [c for c in st.shop if c is not act.card]
            elif isinstance(act, RefreshShop):
                if gold0 <= 50:
                    assert st.gold - act.cost >= 50, (gold0, st.gold)
                st.gold -= act.cost
            elif isinstance(act, LevelUpShop):
                # 必花域 L3(20 号稿):域内升级授权;域外(≤50)零升级
                if gold0 <= 50:
                    raise AssertionError(
                        f'域外帧意外升级 {act!r} @ {gold0} 金')
                st.gold -= act.cost
                st.level += 1
            elif isinstance(act, CloseShop):
                break
            else:
                raise AssertionError(f'局23 帧意外动作 {act!r} @ {gold0} 金')
        else:
            raise AssertionError(f'决策不收敛(死守嫌疑)@ {gold0} 金')
        if gold0 <= 50:
            assert st.gold == gold0, (gold0, st.gold)


# ------------------------------------------- committed 谓词逐帧对拍(P1 附)

# 旧语义复刻的基准常量:生产面 t_of/ready/阈值常量已随旧定型机退役
# (working tree 在飞批删除),此处按退役前版本原值记录,只辖本对拍
# 基准,非生产路径。
_COMMIT_SIGNAL_THRESHOLD: float = 5.0
_COMMIT_MIN_T: int = 7


def _old_t_of(plane: int, round_num: int) -> int:
    """全局节点序号((plane−1)*9 + round,round 1-9 截断;与 horizon 的 t 同构)。"""
    return (min(plane, 3) - 1) * 9 + max(1, min(round_num, 9))


def _old_ready(sig: CommitSignals, t: int = 0) -> bool:
    """退役版 ready 判定:领先线信号分 ≥ 阈值 且 t ≥ 轮门。"""
    if t and t < _COMMIT_MIN_T:
        return False
    lead = sig.leader()
    return lead is not None and lead[1] >= _COMMIT_SIGNAL_THRESHOLD


def _old_committed(state, session: StrategySession) -> bool:
    """旧语义复刻(退役战略层判定式;对拍基准,非生产路径)。

    committed = plane≥2 ∨ (signals.ready ∧ (可切换 ∨ target==领先线));
    ready/t_of 消费退役前复刻(见上常量注)。链退役批重锚:输入 =
    容器单例(plane/round 经节点读口)。
    """
    _nd = state.node.value
    _plane = int(_nd.plane) if _nd is not None else 1
    _round = int(_nd.round_num) if _nd is not None else 1
    if _plane >= 2:
        return True
    sig = getattr(state_of(session), 'commit_signals', None)
    if sig is None:
        return False
    ready = _old_ready(sig, _old_t_of(_plane, _round))
    lead = sig.leader() if ready else None
    return bool(ready and lead is not None)


def _bs_state(plane: int, round_num: int):
    """容器单例构造(链退役批重锚:committed_authority 波5 兼容支退役,
    对拍帧集换容器节点播种;真值语义 = 节点 plane/round)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        GameState,
        NodeKey,
    )
    bs = GameState(schema_version=1)
    bs.observe(bs.node, NodeKey(plane=plane, round_num=round_num,
                                kind='普通战斗'),
               sig=ChannelSig(family='obs', actor='cw_observation',
                              mode='read'))
    return bs


def test_committed_predicate_frame_by_frame_vs_old():
    """committed 翻真谓词 vs 旧 CommitSignals 判定:逐帧对拍锁。

    帧集(判前锁):分歧仅允许出现在「方向层接管区」= 新谓词尚保守
    (ist 未锁)而旧信号已 ready 的窗口;反向分歧(新 True 旧 False)
    仅允许 plane≥2 帧。任何出区分歧 = 谓词漂移,门红。
    """
    frames = []
    # 帧1-2:P1 前段,信号空、ist 未锁 → 双 False
    for rnd in (1, 3):
        frames.append((_bs_state(1, rnd), StrategySession(),
                       'both_false'))
    # 帧3:P1 信号 ready(分超阈+过轮门)但 ist 未锁 → 预期分歧(接管区,
    # 新谓词保守)
    s3 = StrategySession()
    state_of(s3).commit_signals = CommitSignals()
    state_of(s3).commit_signals.scores = {'万敌燃血': 99.0}
    frames.append((_bs_state(1, 8), s3, 'takeover_zone_only_old'))
    # 帧4:ist 已锁 → 双 True
    s4 = StrategySession()
    state_of(s4).v3_intention = IntentionState(phase='locked', locked_comp='万敌燃血')
    state_of(s4).commit_signals = CommitSignals()
    state_of(s4).commit_signals.scores = {'万敌燃血': 99.0}
    frames.append((_bs_state(1, 8), s4, 'both_true'))
    # 帧5:P2 → 双 True(语义边界保留)
    frames.append((_bs_state(2, 1), StrategySession(),
                   'both_true_p2'))
    for st, sess, expect in frames:
        new_v = committed_authority(st, sess)
        old_v = _old_committed(st, sess)
        if expect == 'both_false':
            assert not new_v and not old_v
        elif expect == 'both_true' or expect == 'both_true_p2':
            assert new_v and old_v
        else:   # takeover_zone_only_old:旧翻新未翻 = 接管区唯一合法分歧形
            _nd = st.node.value
            assert old_v and not new_v, (_nd.plane, _nd.round_num, new_v, old_v)
