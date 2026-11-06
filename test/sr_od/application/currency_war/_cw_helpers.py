"""cw 策略测试共享构造器六件套与 obs_arch 运行夹具的单一源。

**种子载体(benchchar-retirement P5 起)**:帧→状态容器换形通道不存在——
测试种子经本模块 builder **直写状态容器域**(与观察链同写入口
``GameState.observe``,design §2.5 测试种子纪律):

- **状态容器域种子**(``cw4_gs``/``cw4_box``):gold/level/xp/hp/deploy_cap/
  node/bench/deployed 行/shop 等各轴参数化,直写 session 状态容器或一次性
  空白状态容器;**商店屏态域字段** ``shop_screen`` 承接原合成口
  shop_open/shop_empty_off_screen 三分支语义(字段语义在
  :func:`_seed_write` docstring 声明);
- **名字表达纪律**(design §2.5):测试想要某阵营/前后排偏好 = 挑对应
  注册表角色名;未知阵营 = 注册表外名字(如 'c0'/'杂1');占位件 =
  ``BenchSlot(kind=...)`` 直种。种子不提供绕过注册表派生的覆盖参数
  (无注入口);
- **StrategySession 桩族**(``cw4_session``):cw4_counters 空表 +
  target_comp 可空 + target_comp 可空(锁定线槽直种) + plane_lengths 可注;
- **商店决策驱动**(``cw4_decide``):装配 mandate 策略器并跑
  decide_shop_screen(种子由调用方先经 ``cw4_gs`` 落状态容器);
- **备战席件构造**(``cw4_bc``):BenchSlot 占席条目(状态容器形状);
- **obs_arch 运行外壳**(``run_node``/``Area``)。

各文件专属形状不入本模块、留在原文件自持。

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
from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    SIM_SYNTHESIZED,
    BenchSlot,
    BenchView,
    ChannelSig,
    NodeKey,
    ShopPayload,
    ShopSlot,
    Unit,
    deployed_view_sequential,
    game_state_of,
    shop_card_to_container,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    ShopCard,
)
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
    缺省锚);传名 = 具名套(血线族/spend_face 的 ``'列车同行·反震'``)。"""
    if name is None:
        names = [c.name for c in COMP_LIBRARY
                 if getattr(c, 'core_chars', None)]
        return get_comp(names[0])
    return get_comp(name)


def cw4_members(comp) -> list[str]:
    """核心∪弹性成员名(注册表序,去重保序)。"""
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def cw4_bc(name: str, star: int = 1) -> BenchSlot:
    """备战席占席条目(状态容器形状;位置 = 种子列表下标:Unit 无槽位信息位,槽位 = 表下标派生)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


def cw4_bview(entries: list) -> BenchView:
    """BenchView 直构(状态容器形状种子;条目 = BenchSlot | None,槽位 =
    下标 + 1,不足容量补空槽)。"""
    slots = [e if e is not None else BenchSlot(kind='empty')
             for e in entries]
    while len(slots) < BENCH_CAPACITY_DEFAULT:
        slots.append(BenchSlot(kind='empty'))
    return BenchView(slots=slots, capacity=BENCH_CAPACITY_DEFAULT)


def cw4_card(name: str, cost: int = 3, star: int = 1, x: int = 0) -> ShopCard:
    """在售店卡(x = 牌位桩值;种子按 x 对物理槽(0 基,越界丢卡,
    用户三态裁定 2026-09-13),缺省 0 = 物理槽 1)。"""
    return ShopCard(x=x, name=name, cost=cost, star=star)


def cw4_session(comp=None, *, plane_lengths=None) -> StrategySession:
    """StrategySession 桩:cw4_counters 空表 + target_comp(锁定线槽直种
    ——批 3.7 键面归一后 target_comp 非空即锁定态;``plane_lengths``
    = 位面长度史注记(**簿记位,不入决策**——视界长度真值 = GameState
    场字段 ``node_seq_by_plane``(None 回退默认表),旧 schedule_of 读数
    已随 9 制几何层退役;strategy 域判定不再消费本注记,仅为 node_books
    簿记形状)。原 ``line_state`` 参数已随 proof.LineState 退役删除
    (批 3.7 换线机器退役)。"""
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = comp
    if plane_lengths is not None:
        game_state_of(s).node_books.plane_lengths_seen = list(plane_lengths)   # 终态契约 §A′
    return s


def cw4_decide(session, cfg=None):
    """商店决策驱动(decide_shop_screen)。种子由调用方先经
    :func:`cw4_gs` 落状态容器,本函数只装配策略器与决策(原「收帧再喂」
    两步随帧退役并一步)。注册表恒 = live 真值表 DEFAULT_REGISTRY;
    cfg 缺省 = ``DecideCfg()``(ev_arm='full')。"""
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
    )
    _cfg = cfg or DecideCfg()
    strat = MandateV1Strategy(
        game_state_of(session),
        _cfg,
        registry=DEFAULT_REGISTRY)   # 终态契约:构造注入
    strat.state = state_of(session)   # 状态归一:策略器状态 = 会话播种对象(config 同源)
    return strat.decide_shop_screen(session, _cfg)


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


# ============================================================ 状态容器域种子
# 两条种子配方的语义差异原样保留(存量断言辖),收敛归本批统一载体——
# - ``cw4_gs``(原 cw4_state+cw4_feed 配方):决策帧家族缺省
#   (gold=30/level=3/round_num=2/hp=100);空牌面 = 在屏空 payload;
#   节点缺席补写 evidence='kind_inherited'(帧未识别的忠实镜像);
# - ``cw4_box``(原桥装箱配方):帧缺省(gold=0/level=1/round_num=1/
#   hp 不写);空牌面 = 离屏分支原样;节点缺席补写 evidence=
#   sim:synthesized;D 类域补写(level_up_cost/shop_refresh_cost/
#   selected_difficulty)仅本配方承接(喂入口域覆盖集不含三域,
#   帧值缺席不写——读口侧回落 None 缺省的语义与桥期一致)。


def _seed_slot(entry: BenchSlot | None, idx: int) -> BenchSlot:
    """备战席条目归一:占位件 kind 直种原样;unit 条目按 ``槽位 = 下标+1``
    归一(原合成口「下标权威」口径;Unit 无槽位信息位——位置 = 表下标派生,归一分支为占位件 kind 直通)。"""
    if entry is None:
        return BenchSlot(kind='empty')
    return entry


def _seed_write(gs, *, sig: ChannelSig, ev: str, ev_node_fill: str,
                gold: int, gold_unread: bool, level: int, level_unread: bool,
                xp, streak, hp, deploy_cap, back_max,
                plane: int, round_num: int, node,
                bench, bench_unread: bool, front_row, back_row,
                shop, shop_screen: str, refresh_probs,
                active_strategies, enemy_affixes, plane_bosses,
                active_env, equips, board,
                level_up_cost, shop_refresh_cost,
                selected_difficulty) -> None:
    """状态容器域种子写实现(与观察链同写入口;域覆盖口径 = 原合成口语义):

    - 可读域全记 observation,evidence 恒 ``sim:synthesized``;声明缺席
      的域不写(保持 None/现值,禁种子合成假值);
    - bench 条目按 ``槽位 = 下标 + 1`` 归一补齐到容量 9(``bench_unread``
      = True 时整域跳写——未读域≠真空域,不覆盖状态容器已有真读);
    - deployed 行域 = front_row/back_row 的 Unit 行直写(两行全空不写,
      与原合成口一致);
    - **shop 三态**(原合成口 shop_open/shop_empty_off_screen 分支在
      种子层的承接口径):
      * 牌面非空 → 按 x 对物理槽(0 基,越界丢卡)落 payload;
      * 空 + ``shop_screen='on'`` → 在屏空牌面 = 买空合法真值
        ([empty×5] 照写,None 仅离屏);
      * 空 + ``shop_screen='off'`` → 结构离屏(leave_screen,禁旧
        payload 连旧 evidence 残留);
      * 空 + ``shop_screen='unread'`` → 识别域失读窗:不写保现值
        (2026-09-13 实机事故口径:买空店重进禁被清 None);
    - encounter/supply 两 payload 域种子不建模,恒离屏口径;
    - node:声明 kind 照写;缺席补写 ``kind=''``(帧未识别的忠实镜像,
      禁词表值冒充真值;``ev_node_fill=''`` = 原裸帧合成语义,节点整域
      不写)。
    """
    if node is not None:
        gs.observe(gs.node,
                   NodeKey(plane=int(plane), round_num=int(round_num),
                           kind=str(node)), evidence=ev, sig=sig)
    elif ev_node_fill:
        gs.observe(gs.node,
                   NodeKey(plane=int(plane), round_num=int(round_num),
                           kind=''), evidence=ev_node_fill, sig=sig)
    if not gold_unread:
        gs.observe(gs.gold, int(gold), evidence=ev, sig=sig)
    if not level_unread:
        gs.observe(gs.level, int(level), evidence=ev, sig=sig)
    if xp is not None:
        gs.observe(gs.xp, tuple(xp), evidence=ev, sig=sig)
    if streak is not None:
        gs.observe(gs.streak, int(streak), evidence=ev, sig=sig)
    if hp is not None:
        gs.observe(gs.hp, int(hp), evidence=ev, sig=sig)
    if deploy_cap is not None:
        gs.observe(gs.deploy_cap, int(deploy_cap), evidence=ev, sig=sig)
    if back_max is not None:
        gs.observe(gs.back_layout, int(back_max), evidence=ev, sig=sig)
    if plane_bosses:
        gs.observe(gs.plane_bosses, list(plane_bosses), evidence=ev, sig=sig)
    if enemy_affixes:
        gs.observe(gs.enemy_affixes, list(enemy_affixes), evidence=ev,
                   sig=sig)
    if active_env:
        gs.observe(gs.active_env, str(active_env), evidence=ev, sig=sig)
    if equips:
        gs.observe(gs.equips, list(equips), evidence=ev, sig=sig)
    if front_row or back_row:
        # deployed 域种子 = 紧缩行序顺延落位视图(
        # 状态容器合并:第 k 个单位落槽 k,与原紧凑行域「顺序即占位」口径
        # 等价;后排容量 = back_max)。
        gs.observe(gs.deployed,
                   deployed_view_sequential(front_row, back_row,
                                            back_capacity=back_max),
                   evidence=ev, sig=sig)
    if not bench_unread:
        slots = [_seed_slot(e, i) for i, e in enumerate(bench)]
        while len(slots) < BENCH_CAPACITY_DEFAULT:
            slots.append(BenchSlot(kind='empty'))
        gs.observe(gs.bench,
                   BenchView(slots=slots, capacity=BENCH_CAPACITY_DEFAULT),
                   evidence=ev, sig=sig)
    if board:
        gs.observe(gs.board, dict(board), evidence=ev, sig=sig)
    probs = ({int(k): float(v) for k, v in refresh_probs.items()}
             if refresh_probs else {})
    if shop:
        # 牌转换 = 映射单一源;定长槽映射:卡 x = 物理槽-1,按 x 对槽
        # (缺位 empty)——紧凑列表顺延映射会错位槽几何(三态裁定)。
        slots = [ShopSlot(kind='empty') for _ in range(5)]
        for c in shop:
            _i = int(getattr(c, 'x', 0) or 0)
            if 0 <= _i < 5:
                slots[_i] = ShopSlot(kind='content',
                                     card=shop_card_to_container(c))
        gs.observe(gs.shop, ShopPayload(cards=slots, refresh_probs=probs),
                   evidence=ev, sig=sig)
    elif shop_screen == 'on':
        gs.observe(gs.shop,
                   ShopPayload(cards=[ShopSlot(kind='empty')
                                      for _ in range(5)], refresh_probs=probs),
                   evidence=ev, sig=sig)
    elif shop_screen == 'off':
        gs.leave_screen(gs.shop, sig=sig)
    elif shop_screen != 'unread':
        raise ValueError(f'shop_screen 非法值:{shop_screen!r}'
                         "(合法 = 'on'/'off'/'unread')")
    gs.leave_screen(gs.encounter, sig=sig)
    gs.leave_screen(gs.supply, sig=sig)
    if active_strategies:
        gs.observe(gs.active_strategies, list(active_strategies),
                   evidence=ev, sig=sig)
    if level_up_cost is not None:
        gs.observe(gs.level_up_cost, int(level_up_cost), evidence=ev, sig=sig)
    if shop_refresh_cost is not None:
        gs.observe(gs.shop_refresh_cost, int(shop_refresh_cost),
                   evidence=ev, sig=sig)
    if selected_difficulty:
        gs.observe(gs.selected_difficulty, str(selected_difficulty),
                   evidence=ev, sig=sig)
    gs.mark_frame_obs('full')


_SEED_SIG = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')


def _seed_steady_pins(gs, target, *, plane: int, round_num: int,
                      gold: int, gold_unread: bool) -> None:
    """种子稳态钉位(读数协议/节点边界的种子层承载,3.6 批):
    金位账面锚定(种子帧 = 可信金读)+ 节点边界判重键钉位(种子帧 =
    「本节点边界已处理」稳态;target=None 一次性状态容器形态经 gs 动态
    挂载状态同宿主)。失效态/边界触发类测试显式改写 ``gold_ledger``/
    ``node_boundary_last_pos``。"""
    try:
        st = state_of(gs)   # 宿主 = 状态容器态(session_scope/读数协议函数族同宿主)
    except Exception:   # noqa: BLE001  无状态宿主 = 无钉位面
        return
    if not gold_unread:
        st.gold_ledger = int(gold)
    st.node_boundary_last_pos = (int(plane), int(round_num))


def cw4_gs(target=None, *, gold: int = 30, gold_unread: bool = False,
           level: int = 3, level_unread: bool = False,
           xp=None, streak=None, hp: int | None = 100,
           deploy_cap=None, back_max: int = 6,
           plane: int = 1, round_num: int = 2, node=None,
           bench=(), bench_unread: bool = False,
           front_row=(), back_row=(),
           shop=(), shop_screen: str = 'on', refresh_probs=None,
           active_strategies=(), enemy_affixes=(), plane_bosses=(),
           active_env: str = '', equips=(), board=None,
           node_fill: bool = True) -> object:
    """决策帧家族的状态容器域种子(原 cw4_state+cw4_feed 配方退役承接)。

    target = session(装入其状态容器,多次调用为累加覆盖写)或 None(一次性
    空白状态容器);返回状态容器。家族缺省 = 旧决策帧家族口径:gold=30、
    level=3、round_num=2、hp=100(各轴显式传参覆盖;hp 传 None = 不写,
    状态容器保持诚实缺位)。shop_screen 缺省 'on'(旧 feed 配方:空牌面 =
    在屏空 payload);节点缺席补写 evidence='kind_inherited'。
    ``node_fill=False`` = 原裸帧合成语义(节点整域不写,M1 投影测试等
    直合成配方场景用)。域语义全表见 :func:`_seed_write`。"""
    gs = game_state_of(target)
    _seed_write(
        gs, sig=_SEED_SIG, ev=SIM_SYNTHESIZED,
        ev_node_fill='kind_inherited' if node_fill else '',
        gold=gold, gold_unread=gold_unread, level=level,
        level_unread=level_unread, xp=xp, streak=streak, hp=hp,
        deploy_cap=deploy_cap, back_max=back_max, plane=plane,
        round_num=round_num, node=node, bench=bench,
        bench_unread=bench_unread, front_row=front_row, back_row=back_row,
        shop=shop, shop_screen=shop_screen, refresh_probs=refresh_probs,
        active_strategies=active_strategies, enemy_affixes=enemy_affixes,
        plane_bosses=plane_bosses, active_env=active_env, equips=equips,
        board=board, level_up_cost=None, shop_refresh_cost=None,
        selected_difficulty='')
    _seed_steady_pins(gs, target, plane=plane, round_num=round_num,
                      gold=gold, gold_unread=gold_unread)
    return gs


def cw4_box(target=None, *, gold: int = 0, gold_unread: bool = False,
            level: int = 1, level_unread: bool = False,
            xp=None, streak=None, hp: int | None = None,
            deploy_cap=None, back_max: int = 6,
            plane: int = 1, round_num: int = 1, node=None,
            bench=(), bench_unread: bool = False,
            front_row=(), back_row=(),
            shop=(), shop_screen: str = 'off', refresh_probs=None,
            active_strategies=(), enemy_affixes=(), plane_bosses=(),
            active_env: str = '', equips=(), board=None,
            level_up_cost=None, shop_refresh_cost=None,
            selected_difficulty: str = '') -> object:
    """桥装箱配方的状态容器域种子承接(原 cw4_box;域写入语义与退役的
    kernel ``board_state_bridge`` 逐位同构)。

    与 :func:`cw4_gs` 的三处刻意分叉(沿桥语义,勿「对齐」):
    ①帧缺省(gold=0/level=1/round_num=1/hp 不写);②空牌面 = 离屏分支
    原样(shop_screen 缺省 'off',不补在屏空 payload);③节点缺席补写
    evidence=sim:synthesized,且独有 D 类域补写(level_up_cost/
    shop_refresh_cost/selected_difficulty,声明缺席不写——读口侧回落
    None 缺省的语义与桥期一致)。"""
    gs = game_state_of(target)
    _seed_write(
        gs, sig=_SEED_SIG, ev=SIM_SYNTHESIZED, ev_node_fill=SIM_SYNTHESIZED,
        gold=gold, gold_unread=gold_unread, level=level,
        level_unread=level_unread, xp=xp, streak=streak, hp=hp,
        deploy_cap=deploy_cap, back_max=back_max, plane=plane,
        round_num=round_num, node=node, bench=bench,
        bench_unread=bench_unread, front_row=front_row, back_row=back_row,
        shop=shop, shop_screen=shop_screen, refresh_probs=refresh_probs,
        active_strategies=active_strategies, enemy_affixes=enemy_affixes,
        plane_bosses=plane_bosses, active_env=active_env, equips=equips,
        board=board, level_up_cost=level_up_cost,
        shop_refresh_cost=shop_refresh_cost,
        selected_difficulty=selected_difficulty)
    return gs
