"""cw4 策略测试共享构造器(六件套)与 prep 单测装配的单一源。

收纳此前散布在十余个测试文件、各持一份近同构副本的桩构造六件套
(``_comp/_members/_session/_state/_card/_bc/_decide``,DEBTS.md D17)
与备战单轮 op 装配(``_make_round_director``,DEBTS.md D22)。收敛建立在
sr-od-test README 第 14 条「跨文件的复制夹具是漂移源头」之上;本模块
文件名以下划线开头,pytest 不收集。

消费面分层(参照 DEBTS D3/D17 的分叉教训,禁强行合一):

- **StrategySession 桩族**(``cw4_session``):cw4_counters 空表 +
  target_comp 可空 + cw4_line_state 可关(refresh_ledger 的配方对语境
  不建 LineState)+ plane_lengths 可注(vgap/refresh_ledger 的位面史);
- **prep/shop 决策帧族**(``cw4_state``):shop/bench/deployed/node/
  deploy_cap/xp/hp 各轴参数化——六件套各文件的历史分叉(hp/xp/
  deploy_cap)全部落在参数上,round_num=2 为家族共同缺省;
- **血线战斗帧族**(``battle_state`` + ``ns_session``):budget_gate/
  guarantee_floor 的开态可读等级/plane=2 battle/单击 4 金/禁刷新帧,
  与 SimpleNamespace 策略 session 四键桩;
- **备战单轮 op 装配**(``make_prep_round_director``):CwScreenPrep
  最小桩面,同源服务签名写点锁(no_progress_guard)与 token 载体写点
  锁(stall_cache)。

各文件专属形状不入本模块、留在原文件自持:interest_floor 的垫卡 shop
帧、spend_face 的 decide_shop_action 桩族(_shop_session/_st)、
deploy_transition 的 faction 版 BenchChar(参数序与构造都不同)、
encounter 桩族(_LAMBDA_TABLE monkeypatch 模式)、suspect_review/
auth_crossface 的两行授权帧(D53 亲读驳回:真实重复面仅 ~5 行骨架
dict,字段面即消费语义,参数化合一会把单侧夹具语义编码进共享件)。

消费方式 = 别名导入(调用点零改动)::

    from test.sr_od.app.currency_war._cw_helpers import cw4_bc as _bc
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


class DecideCfg:
    """``decide_shop_screen`` 的 config 桩(ev_arm 字段 = R1-1 实验因子)。"""

    def __init__(self, ev_arm: str = 'full') -> None:
        self.ev_arm = ev_arm


def cw4_comp(name: str | None = None):
    """测试 comp:name=None = 注册表首个带 core_chars 的套(六件套家族
    缺省锚);传名 = 具名套(血线族/spend_face 的 ``'列车同行'``)。"""
    if name is None:
        names = [c.name for c in COMP_LIBRARY
                 if getattr(c, 'core_chars', None)]
        return get_comp(names[0])
    return get_comp(name)


def cw4_members(comp) -> list[str]:
    """核心∪弹性成员名(注册表序,去重保序)。"""
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def cw4_km(comp) -> list[str]:
    """线名册(statefn.predicates.line_members 注册表现读,禁手抄名)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
        line_members,
    )
    return list(line_members(comp))


def cw4_bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    """备战席件(slot/char_id/star;faction 走 BenchChar 缺省)。"""
    return BenchChar(slot=slot, char_id=name, star=star)


def cw4_card(name: str, cost: int = 3, star: int = 1, x: int = 100) -> ShopCard:
    """在售店卡(x = 画面横向坐标桩值,家族缺省 100)。"""
    return ShopCard(x=x, name=name, cost=cost, star=star)


def cw4_session(comp=None, *, plane_lengths=None,
                line_state: bool = True) -> StrategySession:
    """StrategySession 桩:cw4_counters 空表 + target_comp;``line_state``
    = 建 proof.LineState()(shop 线决策语境;refresh_ledger 的配方对
    锁帧不建,传 False);``plane_lengths`` = 位面长度史注记。"""
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = comp
    if line_state:
        state_of(s).cw4_line_state = proof.LineState()
    if plane_lengths is not None:
        s.plane_lengths_seen = list(plane_lengths)
    return s


def cw4_state(gold: int = 30, shop=None, bench=None, deployed=None,
              level: int = 3, node=None, deploy_cap: int | None = None,
              xp=None, hp: int = 100) -> GameState:
    """prep/shop 决策帧(round_num=2 家族缺省;各轴缺省 = 空店/空席)。"""
    st = GameState(gold=gold, level=level, round_num=2, node_type=node,
                   hp=hp)
    st.shop = shop if shop is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    if deploy_cap is not None:
        st.deploy_cap = deploy_cap
    if xp is not None:
        st.xp_progress = xp
    return st


def battle_state(gold: int, level: int, *, xp: tuple[int, int] = (0, 6),
                 hp: int = 60, bench: list | None = None,
                 deployed: list | None = None) -> GameState:
    """血线族战斗帧(原 budget_gate/guarantee_floor 同款 ``_state``):
    开态可读等级、plane=2 battle、level_up_cost=4、refresh_probs={5:0}
    禁刷新(升级闸判据的隔离帧,刷新通道不得介入)。"""
    st = GameState(gold=gold, level=level, round_num=2, hp=hp)
    st.level_readable = True
    st.plane = 2
    st.node_type = 'battle'
    st.xp_progress = xp
    st.level_up_cost = 4
    st.shop = []
    st.bench = list(bench) if bench is not None else []
    st.deployed = list(deployed) if deployed is not None else []
    st.refresh_probs = {5: 0}
    return st


def ns_session(target_comp=None) -> SimpleNamespace:
    """SimpleNamespace 策略 session 桩(原 budget_gate/guarantee_floor
    ``_sess`` 同款四键字面;cw4_counters/target_comp 生产读面经
    state_of 载体对该桩同样生效)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    return SimpleNamespace(cw4_counters={}, target_comp=target_comp,
                           v3_intention=IntentionState(),
                           active_strategies=[])


def cw4_decide(state: GameState, session, cfg=None, *, registry=None):
    """商店决策驱动(decide_shop_screen)。``registry=None`` = sim 注入
    视图(shop_line 历史缺省,sim 冻结语义锁的面),传
    ``DEFAULT_REGISTRY`` = live 真值表(等级帽单一源锁的双表对拍面,
    ADR-0565);cfg 缺省 = ``DecideCfg()``(ev_arm='full',与各文件原
    SimpleNamespace/type 桩同语义:cfg 对象只承载 ev_arm 读数)。"""
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )
    strat = MandateV1Strategy(
        registry=(sim_decision_registry() if registry is None
                  else registry))
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, cfg or DecideCfg())


def install_dispatch_stub_ports(monkeypatch) -> None:
    """装配点分流桩端口(观察/动作两半)安装·单一源。

    桩端口仅作 run() 装配点判据的在场标记(统一观察架构 §9.1 并存期);
    方法被消费 = 桩面破缺(测试应桩化 _observe,端口不该被读)。
    monkeypatch 装配,teardown 自动复位 = 卸载语义;setattr 直改模块槽
    绕过 install_game_ports 的单装配守卫 = harness 用法(守卫语义由
    test_cw_game_ports 自辖)。

    消费方 = ``make_prep_round_director``(整体装配)与
    ``test_cw_gate_hooks._make_director``(__new__ 裸装配,只共享本桩)。
    """
    from sr_od.application.currency_war import cw_game_ports as _ports_mod

    class _DispatchOnlyObserver:
        """装配点分流桩(观察半):仅作 run() 分流判据的在场端口;
        方法被消费 = 桩面破缺(锁应桩化 _observe,端口不该被读)。"""

        def screen_identity(self, ctx):
            raise NotImplementedError('分流桩端口被消费(观察半)')

        def observe_prep(self, ctx, phase):
            raise NotImplementedError('分流桩端口被消费(观察半)')

        def observe_shop_cards(self, ctx):
            raise NotImplementedError('分流桩端口被消费(观察半)')

        def overlay_options(self, ctx, kind):
            raise NotImplementedError('分流桩端口被消费(观察半)')

    class _DispatchOnlySink:
        """装配点分流桩(动作半):同上,仅作分流判据。"""

        def execute_action(self, ctx, action, env=None):
            raise NotImplementedError('分流桩端口被消费(动作半)')

    monkeypatch.setattr(_ports_mod, '_INSTALLED',
                        (_DispatchOnlyObserver(), _DispatchOnlySink()))


def make_prep_round_director(test_context, monkeypatch, scripted_actions,
                             overlay=None, *, prewarm_state: bool = False,
                             install_dispatch_ports: bool = True):
    """备战单轮 op 单测装配(CwScreenPrep 最小桩面;DEBTS.md D22 单一源)。

    镜像关系声明(原 no_progress_guard/stall_cache 两处互指声明归此):
    本装配同源服务两个写点锁——no_progress_guard 锁
    ``exec_state_of(session).last_prep_action_sig`` 签名写点、stall_cache
    锁 ``cw4_frame_action_record`` token 载体写点;两写点同一决策出口,
    禁删边留角。``prewarm_state=True`` = 预冷建 MandateState 并挂
    session(token 载体锁的写点消费面需要载体先在;签名写点不需要)。

    桩面 = 决策策略桩(scripted_actions 原样回放)+ 入口浮层清理/
    收店探针/代收/步记录全 no-op + ``_observe`` 恒空观察(overlay 可注
    模拟交回环)+ 开店阶段 read_only 短路。(read_bench_full 桩已随通道
    退役删除——迁移批次二 §3.2.5,墓碑函数无桩面消费。)
    返回 ``(director, match, session)``;运行外壳
    (``fast_sleep`` + enter/reset_running_state)留在各锁自持。

    装配点分流(统一观察架构 §9.1 并存期,试点批):缺省(缺省装配,
    ``install_dispatch_ports=True``)monkeypatch ``cw_game_ports.
    _INSTALLED`` 装入分流桩端口(teardown 自动复位 = 卸载语义)——使
    run() 经装配点判据进入五段生命周期新路径,备战行为锁自此锁
    「op execute() 走新基类」(架构设计 §9.1 主门 a)。``_observe`` 桩
    使桩端口不被消费(端口方法 = 响错误,静默消费即桩面破缺信号)。
    ``install_dispatch_ports=False`` = **不装端口(生产缺省形态)**,
    run() 直连旧路径——并存窗旧路径代表锁专用(架构设计 §9.1 并存期:
    生产在跑旧路径,零行为锁 = 回归网清零;**退役批随删**,旧路径删除
    时本形态的消费锁一并退役)。
    """
    if install_dispatch_ports:
        install_dispatch_stub_ports(monkeypatch)

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    class _StubStrategy:
        def decide_prep_screen(self, session, config):
            return list(scripted_actions)

    d = pd_mod.CwScreenPrep(test_context)
    session = StrategySession()
    if prewarm_state:
        state_of(session)   # 冷建 MandateState 并挂 session(写点消费面)
    match = SimpleNamespace(strategy=_StubStrategy(), session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    monkeypatch.setattr(d, '_clear_entry_overlays', lambda: None)
    monkeypatch.setattr(d, '_try_collapse_open_shop', lambda: False)
    monkeypatch.setattr(d, '_takeover_collect_if_needed', lambda m, s: None)
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)

    class _Obs:
        event_overlay = overlay
        state = None
        bench_chars: list = []
        deployed_chars: list = []
        spheres: list = []
        boxes: list = []
        deploy_vacancy = 0

    monkeypatch.setattr(d, '_observe', lambda heavy=True, screen=None: _Obs())
    monkeypatch.setattr(d, '_open_shop_phase',
                        lambda a, obs: (True, 'read_only 读牌完成'))
    return d, match, session
