# -*- coding: utf-8 -*-
"""BoardState 迁移批次三回归锁(策略器状态归位;设计正本 =
docs/develop/sr_od/application/currency_war/
changes/2026-09-11-unified-state/details/BoardState-数据结构设计.md,下称「设计」)。

锁面 = §8.7 批次三六件:§8.6-6 StrategyState 改名归位+泛型携带(§1 归属
判据)/§5.1 effect_inventory 挂点接线(登记/节点 tick/计数 bump/到期
尾款返回面)/§3.2.19 免战牌 EffectSpec 条目+跳过递减/§3.4.1-4 节点屏
刷新计数组写端/§8.7 Snapshot 消费切换(mandate_v1 内部改读)/§5.1 账本
载体归一(session.effect_inventory → BoardState.effects 单例)。
断言全部按设计语义写;批一 110 锁(test_cw_board_state.py)与批二消费锁
(test_cw_board_state_consume.py)持续有效,本文件不重复其断言面。
"""
from __future__ import annotations

import dataclasses
import inspect
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BoardState,
    NodeKey,
    board_state_of,
)


from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    CounterKey,
    ActiveEffectInventory,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    ShopCard as StateShopCard,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CwStrategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    MandateState,
    StrategyState,
    state_of,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_board_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
    register_sig_actors as _register_sig_actors,
)

_register_sig_actors('TestSigWriter')


def _sig() -> "_ChannelSig":
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> "_ChannelSig":
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _hsig() -> "_ChannelSig":
    """渠道③签名(logic_hook 族;relay 中继)。"""
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')


_REPO = Path(__file__).resolve().parents[5]
_PKG = _REPO / 'src' / 'sr_od' / 'application' / 'currency_war'


# ============================================================ §8.6-6/§1
# StrategyState 改名归位 + 下沉策略实现层 + 泛型携带


def test_strategy_state_renamed_alias_is_same_object() -> None:
    """§8.6-6(批次三已落):类名改名归位为目标名 StrategyState;历史名
    MandateState = 同对象别名(isinstance/is X 全兼容,零行为差)。"""
    assert StrategyState is MandateState
    sess = StrategySession()
    assert state_of(sess) is sess.strategy_state
    assert isinstance(state_of(sess), StrategyState)
    assert isinstance(state_of(sess), MandateState), '别名 isinstance 兼容'


def test_framework_layer_does_not_import_concrete_state() -> None:
    """§1 归属判据(硬约束):框架层(kernel 桶 + one_dragon 框架包)不得
    import StrategyState 具体类型——泛型约束的静态锁。策略实现层
    (strategies/)与 app 桶按布局矩阵各自合法,不在本锁辖域。"""
    banned = re.compile(
        r'^\s*(?:from|import)\s+\S*(?:strategies\.impl\.mandate_v1'
        r'|mandate_state)\b', re.M)
    offenders: list[str] = []
    for f in sorted((_PKG / 'kernel').rglob('*.py')):
        if banned.search(f.read_text(encoding='utf-8')):
            offenders.append(str(f.relative_to(_PKG)))
    assert not offenders, f'kernel 桶 import 策略实现层具体状态:{offenders}'
    od_dir = _REPO / 'src' / 'one_dragon'
    cw_ref = re.compile(r'currency_war')
    od_offenders = [str(f.relative_to(_REPO / 'src'))
                    for f in sorted(od_dir.rglob('*.py'))
                    if cw_ref.search(f.read_text(encoding='utf-8',
                                                 errors='ignore'))]
    assert not od_offenders, f'one_dragon 框架包引用 CW 业务面:{od_offenders}'


def test_base_class_carries_state_only_generically() -> None:
    """§8.5/§1:策略器基类仅以泛型参数携带状态——``create_state`` 返回
    注解 = TypeVar(``_TState``) 而非具体类型;基类模块零 StrategyState
    import;具体绑定发生在策略实现层(CwFlowStrategy)。"""
    sig = inspect.signature(CwStrategy.create_state)
    assert '_TState' in str(sig.return_annotation), \
        '基类 create_state 返回注解必须是泛型参数,禁具体状态类型'
    src = inspect.getsource(CwStrategy)
    assert not re.search(r'(?:from|import)\s+\S*mandate_state', src) \
        and not re.search(r'(?:from|import)\s+\S*MandateState\b', src) \
        and not re.search(r'(?:from|import)\s+\S*StrategyState\b', src), \
        '基类零 import 具体状态类型(§1 框架不感知;docstring 提及不算)'

    from sr_od.application.currency_war.strategies.impl.flow import (
        CwFlowStrategy,
    )
    bases = getattr(CwFlowStrategy, '__orig_bases__', ())
    assert any(getattr(b, '__origin__', None) is CwStrategy for b in bases), \
        '泛型绑定必须在策略实现层的类声明上(CwStrategy[StrategyState])'


# ============================================================ §5.1 载体归一
# session.effect_inventory → BoardState.effects 单例


def test_effect_inventory_is_board_state_ledger_read_through() -> None:
    """§5.1/§8.4 载体归一(批次三):账本单一实例 = BoardState.effects;
    ``session.effect_inventory`` 是只读透传属性(历史写点读点零改动兼容),
    字段本体已从 session 移除——双账本漂移面消除。"""
    assert 'effect_inventory' not in {
        f.name for f in dataclasses.fields(StrategySession)}, \
        'session 不得再持有独立账本实例(双账本禁)'
    sess = StrategySession()
    inv = sess.effect_inventory
    assert inv is board_state_of(sess).effects, '透传属性指向 BoardState 正本'
    with pytest.raises(AttributeError):
        sess.effect_inventory = ActiveEffectInventory(), '无 setter:禁直挂实例'


def test_level_up_hook_writes_unified_ledger() -> None:
    """升级标记挂点(prep_actions 既有)经归一后写 BoardState 正本:
    session.effect_inventory.on_level_up() 与 bs.effects 事件计数同源。"""
    sess = StrategySession()
    sess.effect_inventory.on_level_up()
    assert board_state_of(sess).effects.event_count('_event_level_up') == 1, \
        '归一后写点落在单一实例(经属性写透)'


# ============================================================ §5.1 挂点机制
# register 播种 / tick 去重与到期 / consume_use / bump_key


def test_register_seeds_remaining_uses_and_nodes() -> None:
    """§3.2.19/§5.1:登记播种双轨——次数类(duration_uses>0)播
    remaining_uses(免战牌=2),N_NODES 播 remaining_nodes(躺平=3)。"""
    inv = ActiveEffectInventory()
    e_skip = inv.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=5)
    assert e_skip.remaining_uses == 2 and e_skip.remaining_nodes is None
    e_lie = inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    assert e_lie.remaining_nodes == 3 and e_lie.remaining_uses is None


def test_tick_node_dedup_and_acquired_guard_and_expiry() -> None:
    """§5.1 节点 tick:同节点去重(每备战环采样只推进一次)/登记当节点
    不推进(「持续 N 个节点」= 登记节点的后继 N 节点,实采定谳前保守读)/
    归零移除并返回到期条目(尾款触发面)。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    assert inv.tick_node(5) == [], '登记当节点不推进(吞节点即错口径)'
    assert inv.tick_node(5) == [], '同节点去重:幂等'
    assert inv.first('102001').remaining_nodes == 3
    assert inv.tick_node(6) == [] and inv.first('102001').remaining_nodes == 2
    assert inv.tick_node(6) == [], '同节点去重'
    inv.tick_node(7)
    expired = inv.tick_node(8)
    assert [e.spec.id for e in expired] == ['102001'], '归零移除+到期返回'
    assert inv.first('102001') is None
    assert inv.tick_node(8) == [], '空清单 tick 幂等'


def test_tick_node_without_ordinal_is_legacy_unconditional() -> None:
    """无 node_ordinal(旧签名)→ 无条件推进(测试/sim 直调兼容面)。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    inv.tick_node()
    assert inv.first('102001').remaining_nodes == 2


def test_advance_node_reports_advanced_flag() -> None:
    """B1 桥闸门:advance_node 返回 (advanced, expired)——同节点重复推进
    advanced=False(余额累加闸 = 每节点恰一次);tick_node 兼容口语义不变。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    advanced, expired = inv.advance_node(6)
    assert advanced is True and expired == []
    advanced2, _ = inv.advance_node(6)
    assert advanced2 is False, '同节点去重位 = 余额累加闸门'
    inv.advance_node(7)
    advanced3, expired3 = inv.advance_node(8)
    assert advanced3 is True and [e.spec.id for e in expired3] == ['102001'], \
        '三次有效推进(6/7/8)后到期移除'


# ============================================================ B1 账本→字段桥
# §5.1/§3.3.5-6/§3.2.5:burst(登记一次性)/per_node(每节点)/容量投影三形态


def test_burst_grant_adds_free_refresh_balance_once() -> None:
    """桥·burst:登记时点把 payload.free_refresh_burst 一次性累加进余额
    (固定理财即时段=2 活载体);零额度 payload(免战牌)= no-op。「一次性」
    由调用点唯一性承载(登记挂点,接线锁辖),函数本体不加去重。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        apply_effect_burst_grant,
    )
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    apply_effect_burst_grant(bs, STRATEGY_EFFECTS['固定理财'], frame='p1-r2')
    assert bs.free_refresh_balance.value == 2
    assert bs.free_refresh_balance.evidence == 'effect_burst@p1-r2'
    apply_effect_burst_grant(bs, STRATEGY_EFFECTS['免战牌'])
    assert bs.free_refresh_balance.value == 2, '零额度 = no-op'


def test_per_node_grant_adds_once_per_node() -> None:
    """桥·per_node:节点边界一次,把在场条目声明的每节点额度累加
    (双手狸 free_refresh_on_node_enter=2 活载体);同节点重复挂点采样不
    双计(闸 = advance_node advanced 位)。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        grant_effect_node_refresh_balance,
    )
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_t=5)
    adv, _ex = bs.effects.advance_node(6)
    if adv:
        grant_effect_node_refresh_balance(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 2
    # 同节点重复采样(挂点每备战环一次):去重位关闭累加
    adv2, _ex2 = bs.effects.advance_node(6)
    if adv2:
        grant_effect_node_refresh_balance(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 2, '同节点禁双计'
    adv3, _ex3 = bs.effects.advance_node(7)
    if adv3:
        grant_effect_node_refresh_balance(bs, frame='p1-r7')
    assert bs.free_refresh_balance.value == 4, '下一节点再 +2'


def test_capacity_projection_activates_and_recovers() -> None:
    """桥·容量投影(§3.2.5):在册容量声明 payload.capacity_limit=3 → bench
    容量投影 3;条目到期移除 → 回默认 9;bench 未观察(None)= 无容器跳过;
    零声明条目 → 恒默认 9(幂等,当前注册表活载体为零,行为与接线前
    逐位一致)。声明契约 = payload 鸭子属性 capacity_limit(注册表建模批
    候选,§5.2 缺口;测试以鸭子桩承载声明,机制先于数据)。"""
    from types import SimpleNamespace as _NS
    from sr_od.application.currency_war.kernel.cw_board_state import (
        BENCH_CAPACITY_DEFAULT,
        BenchSlot,
        BenchView,
        project_effect_capacity,
    )
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        DutyFlags,
        DurationKind,
        EffectKind,
        EffectSpec,
        TriggerKind,
    )

    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    # bench 未观察:无容器可写,投影跳过
    inv = bs.effects
    inv.register_strategy(EffectSpec(
        id='test_cap', name='容量测试桩', trigger=TriggerKind.CONDITIONAL,
        duration=DurationKind.N_NODES, category=EffectKind.ECONOMY,
        payload=_NS(capacity_limit=3), duties=DutyFlags(track=True),
        duration_nodes=2), acquired_t=5)
    project_effect_capacity(bs)
    assert bs.bench.value is None, 'bench 未观察 = 无容器,不造帧'
    # 观察(默认容量 9)→ 投影 3
    slots = [BenchSlot(kind='unit')] + [BenchSlot(kind='empty')] * 8
    bs.observe(bs.bench, BenchView(slots=slots, capacity=BENCH_CAPACITY_DEFAULT), sig=_sig())
    project_effect_capacity(bs)
    assert bs.bench.value.capacity == 3, '激活期容量 = 声明值'
    assert bs.bench.value.slots[0].kind == 'unit', '槽位表原样保留'
    assert bs.bench.source == 'logic' \
        and bs.bench.evidence == 'capacity_project'
    # 条目到期(N_NODES=2,两次推进)→ 移除后投影回默认 9
    inv.advance_node(6)
    inv.advance_node(7)
    project_effect_capacity(bs)
    assert bs.bench.value.capacity == BENCH_CAPACITY_DEFAULT == 9, \
        '到期自动回 9(§3.2.5)'


def test_consume_use_decrements_removes_and_tolerates_missing() -> None:
    """§3.2.19 跳过递减:落地一次 −1;归零移除;无在册条目返 None 零动作
    (递减挂点与登记挂点解耦,不炸执行链)。"""
    inv = ActiveEffectInventory()
    assert inv.consume_use('151301') is None, '未登记 = None 零动作'
    inv.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=3)
    assert inv.consume_use('151301') == 1
    assert inv.first('151301') is not None, '尚有余量不移除'
    assert inv.consume_use('151301') == 0
    assert inv.first('151301') is None, '用尽 = 效果离场'
    assert inv.consume_use('151301') is None


def test_bump_key_advances_only_tracked_entries() -> None:
    """§5.1 计数 bump:动作侧全量推进只辖 duties.track=True 条目(「谁要
    记账」的声明单一源);消费按 (spec_id, key) 隔离读。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·金'], acquired_t=1)  # track=True
    inv.register_strategy(STRATEGY_EFFECTS['人力重组'], acquired_t=1)     # predict only
    inv.bump_key(CounterKey.REFRESH)
    inv.bump_key(CounterKey.REFRESH)
    assert inv.counter('201201', CounterKey.REFRESH) == 2
    assert inv.counter('102801', CounterKey.REFRESH) == 0, \
        '未声明记账义务的条目不被推进'


def test_skip_battle_spec_entry_matches_base_registry() -> None:
    """§8.7 批次三件 5(建模批件):免战牌 EffectSpec 条目 = id 与 base
    注册表双匹配(构建校验之外显式锁语义),次数种子 2,即时经验 30。"""
    spec = STRATEGY_EFFECTS['免战牌']
    assert spec.id == '151301'
    assert INVESTMENT_STRATEGIES['免战牌'].source == 'plaza:151301'
    assert spec.duration_uses == 2
    assert spec.payload.xp_instant == 30, \
        '+30 经验 = 选牌当场即时经验(§4 投资选择通用通道词表)'


# ============================================================ §3.4.1-4/§8.7
# 节点屏刷新计数组写端 + 挂点接线存在性(inspect 烟雾,README 第 8 条容忍档;
# 行为面已由上方函数级锁覆盖,op 装配面不重建重 harness)


def test_refresh_ledger_write_sites_wired() -> None:
    """件 6 写端接线存在性:遭遇屏(+1 置位,refresh_click)/策略屏
    (逐卡键=normalize_invest_name 规范名)/环境屏无执行链不接线
    (ADR-0600 环境侧未启用,零写端禁按值决策口径继续辖)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter,
        cw_screen_invest_env,
        cw_screen_invest_strategy,
    )
    enc_src = inspect.getsource(cw_screen_encounter)
    assert 'encounter_refresh_used' in enc_src \
        and 'refresh_click' in enc_src, '遭遇屏刷计数写端在位'
    strat_src = inspect.getsource(cw_screen_invest_strategy)
    assert 'strategy_refresh_used' in strat_src \
        and 'normalize_invest_name' in strat_src, \
        '策略屏逐卡刷计数写端在位(键=规范卡名)'
    env_src = inspect.getsource(cw_screen_invest_env)
    assert 'env_refresh_used' not in env_src, \
        '环境屏刷新执行链未启用,无点击即无写端(禁观察镜像混入点击置位口径)'


def test_effect_hooks_wired_at_production_sites() -> None:
    """§5.1 挂点接线存在性:选卡登记(register_strategy)/执行落地门
    bump(REFRESH+BUY)/节点 tick(advance_node)/跳过递减(consume_use)
    四挂点 + B1 桥两采样点(burst 登记后/per_node+容量投影 tick 后)在
    生产调用面在位。"""
    from sr_od.application.currency_war.operations.cw_op import cw_op_buy_cards
    from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy,
    )
    from sr_od.application.currency_war import prep_actions
    strat_src = inspect.getsource(cw_screen_invest_strategy)
    assert 'register_strategy' in strat_src, '选卡登记挂点在位'
    assert 'apply_effect_burst_grant' in strat_src, \
        'B1 burst 桥采样点(登记后)在位'
    buy_src = inspect.getsource(cw_op_buy_cards)
    assert 'bump_key' in buy_src \
        and 'CounterKey.REFRESH' in buy_src \
        and 'CounterKey.BUY' in buy_src, '执行落地门计数 bump 在位'
    loop_src = inspect.getsource(cw_loop_mod)
    assert 'effects.advance_node' in loop_src, '节点 tick 挂点在位'
    assert 'grant_effect_node_refresh_balance' in loop_src, \
        'B1 per_node 桥采样点(tick 后)在位'
    assert 'project_effect_capacity' in loop_src, \
        'B1 容量投影采样点(备战帧观察后重锚)在位'
    prep_src = inspect.getsource(prep_actions)
    assert 'consume_use' in prep_src and '按钮-跳过' in prep_src, \
        '免战牌跳过递减挂点在位'


# ============================================================ 第 15 轮对抗审 C8
# sim 合成口 payload 离屏分支(§2.2 例外:真值缺席 = 结构离屏,禁旧 payload 残留)


def test_synthesis_payload_offscreen_branch() -> None:
    """C8:合成口 shop 真值缺席 = 结构离屏(置 None+left_screen,等价
    leave_screen)——禁旧 shop payload 连旧 evidence 残留(把「不在商店」帧
    误读成「商店仍开着」);encounter/supply 两域 sim 不建模,合成帧恒
    离屏口径;牌面在场帧照常观察落 payload。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        synthesize_from_game_state,
    )

    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    st_shop = GameState()
    st_shop.shop = [StateShopCard(x=1, name='花火', cost=2, star=1,
                                  cost_source='badge')]
    synthesize_from_game_state(bs, st_shop, at_round='p1-r2')
    assert bs.shop.value is not None and bs.shop.value.cards[0].name == '花火'

    # 连续合成帧:真值缺席 → 离屏(旧 payload 不残留)
    st_prep = GameState()
    synthesize_from_game_state(bs, st_prep, at_round='p1-r3')
    assert bs.shop.value is None, '离屏帧 payload 置 None(禁残留)'
    assert bs.shop.source == 'observation' \
        and bs.shop.evidence == 'left_screen', '结构离屏 = left_screen 标记'
    assert bs.encounter.value is None \
        and bs.encounter.evidence == 'left_screen'
    assert bs.supply.value is None and bs.supply.evidence == 'left_screen'


# ============================================================ §8.7 件 3
# Snapshot 消费切换:mandate_v1 内部改读 BoardState 视图


def _bs_with_node(sess) -> None:
    bs = board_state_of(sess)
    bs.observe(bs.node, NodeKey(plane=2, round_num=5, kind='battle'), sig=_sig())


def test_snapshot_assembly_falls_back_to_board_state_view() -> None:
    """件 3:snapshot_from_obs 的 session 回退锚改读 BoardState 视图——
    obs.state 缺席帧,plane/round 取记录值(与旧 last_state 直读在常态帧
    逐位一致;失读帧取 carried 沿用值 = 记录模型申报面)。"""
    from sr_od.application.currency_war.decision_assembly import snapshot_from_obs

    sess = StrategySession()
    _bs_with_node(sess)
    obs = SimpleNamespace(
        state=None, state_gold_trusted=False, bench_chars=[], deployed_chars=[],
        spheres=[], boxes=[], tomes=[], deploy_vacancy=0, free_bench_slots=None,
        front_occupied=set(), back_occupied=set(), front_size=4, back_size=6,
        shop_open=False, box_overlay_open=False, event_overlay=None,
    )
    snap = snapshot_from_obs(obs, sess)
    assert (snap.plane, snap.round_num) == (2, 5), \
        '回退锚 = BoardState 记录值(非 last_state 原帧)'


def test_snapshot_anchor_state_falls_back_to_board_state_view() -> None:
    """件 3:adapter._anchor_state 的 session 锚同切——快照值缺席域取
    BoardState 记录值。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.adapter import (
        _anchor_state,
    )

    sess = StrategySession()
    _bs_with_node(sess)
    snap = SimpleNamespace(
        plane=None, round_num=None, node_type=None, level=None,
        xp_progress=None, level_up_cost=None, selected_difficulty='',
        streak=None, gold_trusted=False, gold=None, hp_readable=False,
    )
    st = _anchor_state(snap, sess)
    assert (st.plane, st.round_num) == (2, 5), '锚回退 = 记录值'
    assert st.node_type == 'battle'
