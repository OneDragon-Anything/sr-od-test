"""策略卡战后触发发放检查腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_battle_grants)。

测试面依据 = 迭代设计 designs/T-105-yizhan-yangzhan.md §4 锁 6(条件矩阵
短路序直构;直构形态先例 = 同目录 test_check_strategy_conditional_grants.py
的容器直置):
- node_kind 非 encounter → 空(节点类型条件短路);
- 未持卡/表外卡 → 空(持卡交集判定);
- 命中 → 席上落带名槽件 + 返回 (卡名, 道具名) 逐对一致 + evidence 形态;
- 可重复(无 done 一次性标志位,对照 T-102 条件通道的「首次」一次性标志位语义——本卡卡文无
  「首次」限定 = 每次遭遇战后都发);
- bench 未观察(None)→ 原语内拒落零写(宁缺勿造,与 env 触发器同契约)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_battle_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '以战养战'
_ITEM = '简易武装箱'


def _empty_slots(n: int = 9) -> list[BenchSlot]:
    return [BenchSlot(kind='empty')] * n


def _gs(*, card: str | None = _CARD,
        bench_slots: list[BenchSlot] | None = None) -> GameState:
    """持卡 + bench 直置(card=None = 未持卡;bench_slots=None = 未观察)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True   # 确定发放 = 锁确定面写通道(先例同款)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card', sig=_LSIG)
    if bench_slots is not None:
        gs.observe(gs.bench, BenchView(slots=bench_slots, capacity=9),
                   sig=_SIG_OBS)
    return gs


def test_non_encounter_kind_short_circuit() -> None:
    """锁 6a:node_kind != 'encounter' → 空(battle/boss 节点零发放,
    节点类型条件在矩阵首位短路,持卡与否零影响)。"""
    for kind in ('battle', 'boss', 'reward', 'supply', ''):
        gs = _gs(bench_slots=_empty_slots())
        assert check_strategy_battle_grants(gs, kind, _LSIG) == (), \
            f'非遭遇 kind={kind!r} 误发放'
        assert all(s.kind == 'empty' for s in gs.bench.value.slots), \
            f'非遭遇 kind={kind!r} 误落席'


def test_no_card_zero_grant() -> None:
    """锁 6b:未持卡 + encounter → 空(active_strategies ∩ 登记表键集
    为空即整腿无候选)。"""
    gs = _gs(card=None, bench_slots=_empty_slots())
    assert check_strategy_battle_grants(gs, 'encounter', _LSIG) == (), \
        '未持卡误发放'
    assert all(s.kind == 'empty' for s in gs.bench.value.slots), '未持卡误落席'


def test_out_of_registry_card_zero_grant() -> None:
    """锁 6c:持表外卡(躺平)+ encounter → 空(表外卡一律无条目,
    禁从效果原文自动猜装的通道纪律)。"""
    gs = _gs(card='躺平', bench_slots=_empty_slots())
    assert check_strategy_battle_grants(gs, 'encounter', _LSIG) == (), \
        '表外卡误发放'
    assert all(s.kind == 'empty' for s in gs.bench.value.slots), '表外卡误落席'


def test_grant_lands_named_slot_and_returns_pairs() -> None:
    """锁 6 主条:持卡 + encounter → 席上落带名槽件(kind=item 同源映射)
    + 返回 (卡名, 道具名) 与登记表值逐对一致;发放 = 确定面(source=
    logic,rand=False)+ evidence 形态 strategy_post_battle#<卡名>#
    (落席 #place 后缀)。"""
    gs = _gs(bench_slots=_empty_slots())
    out = check_strategy_battle_grants(gs, 'encounter', _LSIG)
    assert out == ((_CARD, _ITEM),), f'返回值漂移: {out!r}'
    slots = gs.bench.value.slots
    landed = [s for s in slots if s is not None and s.kind == 'supply_box']
    assert len(landed) == 1, f'落席数漂移: {len(landed)}'
    assert landed[0].item == _ITEM, '钉名槽件漂移'
    assert gs.bench.source == 'logic', '确定发放应走确定面写'
    assert gs.bench.evidence == f'strategy_post_battle#{_CARD}#place'


def test_repeatable_no_done_latch() -> None:
    """锁 6 可重复(对照 T-102「首次」一次性标志位语义的通道差异):同 kind 连调
    两次 → 两箱(无 done 一次性标志位,卡文无「首次」限定 = 每次遭遇战后都发;
    防重归调用方节点键幂等守卫,本函数零二次守卫)。"""
    gs = _gs(bench_slots=_empty_slots())
    assert check_strategy_battle_grants(gs, 'encounter', _LSIG) \
        == ((_CARD, _ITEM),)
    assert check_strategy_battle_grants(gs, 'encounter', _LSIG) \
        == ((_CARD, _ITEM),), '二次调用被误拦(可重复语义破坏)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert len(boxes) == 2, f'重复发放未落席: {len(boxes)}'


def test_unobserved_bench_refused() -> None:
    """锁 6 拒落:bench 未观察(None)→ 原语内拒落零写返回空(宁缺勿造,
    开局种子底座下生产不可达,直构/测试形态防御)。"""
    gs = _gs(bench_slots=None)
    assert check_strategy_battle_grants(gs, 'encounter', _LSIG) == (), \
        '未观察窗误发放'
    assert gs.bench.value is None, '未观察窗误写'
