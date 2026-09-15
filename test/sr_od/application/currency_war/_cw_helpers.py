"""cw4 策略测试共享构造器(六件套)、prep 单测装配与 obs_arch 运行夹具的单一源。

收纳此前散布在十余个测试文件、各持一份近同构副本的桩构造六件套
(``_comp/_members/_session/_state/_card/_bc/_decide``,DEBTS.md D17)、
备战单轮 op 装配(``_make_round_director``,DEBTS.md D22)与 obs_arch
六文件的运行外壳三件(``run_node``/``uninstall_ports``/``Area``,
夹具收敛——原为 6/4/4 份逐文件复制)。收敛建立在测试仓 README
「跨文件的复制夹具是漂移源头」纪律之上(README 常驻摘要不编号,故不引
条号);本模块文件名以下划线开头,pytest 不收集。

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

    from test.sr_od.application.currency_war._cw_helpers import cw4_bc as _bc
"""
from __future__ import annotations

from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    CwSimFrame,
    ShopCard,
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


def cw4_bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    """备战席件(slot/char_id/star;faction 走 BenchChar 缺省)。"""
    return BenchChar(slot=slot, char_id=name, star=star)


def cw4_card(name: str, cost: int = 3, star: int = 1, x: int = 0) -> ShopCard:
    """在售店卡(x = 牌位桩值;三态合成口按 x 对物理槽(0 基,越界丢卡,
    用户三态裁定 2026-09-13),缺省 0 = 物理槽 1;旧「画面横向坐标 100」
    桩值语义已随容器三态化退役)。"""
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
              xp=None, hp: int = 100) -> CwSimFrame:
    """prep/shop 决策帧(round_num=2 家族缺省;各轴缺省 = 空店/空席)。"""
    st = CwSimFrame(gold=gold, level=level, round_num=2, node_type=node,
                   hp=hp)
    st.shop = shop if shop is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    if deploy_cap is not None:
        st.deploy_cap = deploy_cap
    if xp is not None:
        st.xp_progress = xp
    return st


def cw4_decide(state: CwSimFrame, session, cfg=None, *, registry=None):
    """商店决策驱动(decide_shop_screen)。``registry=None`` = live
    真值表 DEFAULT_REGISTRY(旧 sim 注入视图随 sim 重做删除面退役,
    sim 重做设计稿 §2.4.4:策略器自带注册表,sim 不构造策略视图);
    传 ``DEFAULT_REGISTRY`` 同义(保留参数 = 对拍面显式形态,cap 单一
    源锁参考 ADR-0565);cfg 缺省 = ``DecideCfg()``(ev_arm='full',与
    各文件原 SimpleNamespace/type 桩同语义:cfg 对象只承载 ev_arm 读数)。

    W6 波 4 黑板容器化:喂入通道 = sim 合成口写容器(生产/离线同路;
    原黑板槽直写随槽退役消亡,设计件《商店黑板容器化方案》§2.4-3)。"""
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
    )
    strat = MandateV1Strategy(
        registry=(DEFAULT_REGISTRY if registry is None else registry))
    cw4_feed(session, state)
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


def uninstall_ports(monkeypatch) -> None:
    """装配点分流桩端口卸载复位(生产缺省形态;旧路径代表驱动专用)。

    与 :func:`install_dispatch_stub_ports` 成对的卸载半:``_INSTALLED``
    复位 ``(None, None)`` = 装配点判据不成立,op 直连旧路径原序列。
    直改模块槽绕过 install_game_ports 的单装配守卫 = harness 用法
    (守卫语义由 test_cw_game_ports 自辖)。
    """
    from sr_od.application.currency_war import cw_game_ports as _ports_mod
    monkeypatch.setattr(_ports_mod, '_INSTALLED', (None, None))


def run_node(test_context, op, fn) -> object:
    """节点函数运行外壳(fast_sleep + running_state;返回轮次结果)。

    op 流程测试纪律 5/6 的封装位:``execute()``/节点直调包
    ``fast_sleep()``(mock 画面瞬时切换,框架轮间等待纯属空等)+
    运行态前置/复位(harness helper,禁手写 ``_run_state`` 裸赋值)。
    """
    with fast_sleep():
        enter_running_state(test_context)
        try:
            return fn()
        finally:
            reset_running_state(test_context, op)


class Area:
    """round_by_find_area 桩回执(程序化回 is_success;桩只验判定结果)。"""

    def __init__(self, ok: bool) -> None:
        self.is_success = ok


# (原 make_prep_round_director 删:声明消费方 test_cw_gate_hooks 文件已
#  不存在,全树零消费死代码 ~68 行;备战单轮 op 装配需求出现时按现行
#  纪律随锁重建。)


def cw4_feed(session, frame):
    """帧 → session 容器喂入(W6 波 4 测试迁移单一源;生产同路 = sim
    合成口)。空牌面补在屏空 payload(旧测试语境「在屏 ∧ 牌面空」,
    与合成口「空表=离屏」真值口径的分叉在此显式对齐)。

    节点缺席补写(node_type=None 帧的 plane/round 保真):合成口对
    node_type 未识别帧不写 node(禁 'prep' 占位假值),旧决策链直读
    ``CwSimFrame.plane/round_num`` 标量、位面门照常生效——补写
    ``NodeKey(kind='')``(kind 空串 = 帧未识别的忠实镜像,禁词表值
    冒充真值),保喂入路对未识别帧决策面行为保真。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        NodeKey,
        ShopPayload,
        board_state_of,
        synthesize_from_game_state,
    )
    _bs = board_state_of(session)
    synthesize_from_game_state(_bs, frame)
    _sig = ChannelSig(family='obs', actor='synthesize_from_game_state',
                      mode='synthesized')
    if _bs.node.value is None:
        _bs.observe(_bs.node,
                    NodeKey(plane=int(getattr(frame, 'plane', 1) or 1),
                            round_num=int(getattr(frame, 'round_num', 1)
                                          or 1),
                            kind=''),
                    evidence='kind_inherited', sig=_sig)
    if _bs.shop.value is None:
        _bs.observe(_bs.shop, ShopPayload(
            cards=[],
            refresh_probs={int(k): float(v) for k, v in
                           (getattr(frame, 'refresh_probs', None)
                            or {}).items()}),
            sig=ChannelSig(family='obs', actor='synthesize_from_game_state',
                           mode='synthesized'))
    return _bs


def cw4_bs(frame, session):
    """帧 → 容器并返回容器(cw4_feed 的取值形态;decide_shop_action
    首参直喂迁移用)。"""
    return cw4_feed(session, frame)


class _DuckFrame:
    """鸭子帧属性缺读回落 CwSimFrame 缺省(轻量桩帧兼容——旧链消费只读
    桩提供的字段;装箱经合成口搬运全域,缺属性按同帧 ``CwSimFrame()``
    缺省解释,与「缺读 = 缺省保守值」惯例一致)。"""

    __slots__ = ('_st', '_base')

    def __init__(self, st_: object, base_: object) -> None:
        object.__setattr__(self, '_st', st_)
        object.__setattr__(self, '_base', base_)

    def __getattr__(self, name: str):
        st = object.__getattribute__(self, '_st')
        base = object.__getattribute__(self, '_base')
        try:
            return getattr(st, name)
        except AttributeError:
            return getattr(base, name)


def cw4_box(frame, session=None):
    """帧 → 容器一次性装箱(「桥装箱」配方的退役承接:桥本体删除
    批起,本函数 = 该配方测试侧单一源)。域写入语义与退役的 kernel
    ``board_state_bridge`` 逐位同构,消费方式 = 别名导入(调用点零改动,
    见模块头)。

    - 载体 = 容器读口 ``board_state_of(session)``:session=None(缺省)
      = 一次性空白容器(读口 None 分支契约:不缓存不挂载);传 session
      时装入该 session 单例(适合「装箱面与生产读口面须同容器」的用例,
      注意多次装箱同 session 为累加写,与一次性桥语义有差);
    - 域写入 = 生产同路合成口 ``synthesize_from_game_state`` + 节点缺席
      补写(NodeKey(kind=''),evidence=sim:synthesized)+ D 类域补写
      (level_up_cost/shop_refresh_cost/selected_difficulty,帧值缺席
      不写——喂入口现不写这三域(fields.md D 类行),桥期由桥独有补写
      承载,此处原样承接,读口侧回落 None 缺省的语义与桥期一致);
    - 与 cw4_feed 的两处刻意分叉(沿桥语义,勿「对齐」):①不补在屏空
      payload(桥语义 = 合成口离屏分支原样,cw4_feed 的空牌面补写是旧
      商店语境的对齐面);②节点补写 evidence=sim:synthesized(cw4_feed
      用 kind_inherited)。两分叉各有存量断言辖,收敛归喂入口域覆盖批。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SIM_SYNTHESIZED,
        ChannelSig,
        NodeKey,
        board_state_of,
        synthesize_from_game_state,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwSimFrame as _FrameDefaults,
    )
    bs = board_state_of(session)
    _sig = ChannelSig(family='obs', actor='synthesize_from_game_state',
                      mode='synthesized')
    st_view: object = (_DuckFrame(frame, _FrameDefaults())
                       if not isinstance(frame, _FrameDefaults) else frame)
    synthesize_from_game_state(bs, st_view)
    if bs.node.value is None:
        bs.observe(bs.node,
                   NodeKey(plane=int(getattr(frame, 'plane', 1) or 1),
                           round_num=int(getattr(frame, 'round_num', 1)
                                         or 1),
                           kind=''),
                   evidence=SIM_SYNTHESIZED, sig=_sig)
    if getattr(frame, 'level_up_cost', None) is not None:
        bs.observe(bs.level_up_cost, int(frame.level_up_cost),
                   evidence=SIM_SYNTHESIZED, sig=_sig)
    if getattr(frame, 'shop_refresh_cost', None) is not None:
        bs.observe(bs.shop_refresh_cost, int(frame.shop_refresh_cost),
                   evidence=SIM_SYNTHESIZED, sig=_sig)
    if getattr(frame, 'selected_difficulty', None):
        bs.observe(bs.selected_difficulty, str(frame.selected_difficulty),
                   evidence=SIM_SYNTHESIZED, sig=_sig)
    return bs
