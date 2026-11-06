"""策略卡条件发放检查效果条目测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_conditional_grants + kernel/cw_game_state.py 的
_tick_strategy_conditional_grants 接入调用)。

测试面依据 = 迭代设计 designs/T-102-guimo-xiaoying.md §4 锁 2/3/4/5/9:
- 构造 = 状态容器直置 + advance_node_effective 驱动(序位前进唯一落账入口,
  尾段自带 tick_effect_boundary;advanced 位闸下同序位重复 tick 检查效果条目
  跳过,达标触发必须真实推进——设计稿「直调 tick_effect_boundary」的
  可达形;禁经 gain_character 构造达标态,会对触发面盲区假绿);
- 持卡 + 池(备战 ∪ 上阵 ∪ 溢出)8 同名单位 → tick → equips 追加完美
  投影仪 + 落一次性标志位;未达阈/未持卡/表外卡零写零一次性标志位;
- 一次性标志位:发放后池回落再置回 ≥8 不二次发放(一次性标志位 = 「首次」语义);
- 单位数口径:7 单位(含 2★ = 1 单位,拷贝当量 8)不触发,置第 8 单位
  才触发(锁计数口径默认案,改判随改);
- 拒落不落一次性标志位:equips 未观察零写零一次性标志位,观察恢复后补发放(自愈)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    advance_node_effective,
    tick_effect_boundary,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '规模效应'
_EQUIP = '完美投影仪'
_NAME = '希儿'


def _slots(bench: list[tuple[str, int]]) -> list[BenchSlot]:
    out = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
           for c, s in bench]
    return out + [BenchSlot(kind='empty')] * (9 - len(out))


def _gs_with_card(*, bench: list[tuple[str, int]],
                  equips: list[str] | None,
                  card: str | None = _CARD) -> GameState:
    """持卡 + 状态容器直置池(equips=None = 未观察,供拒落分支;bench 直置
    即真值写,不走获得链——触发面 = tick 现值检查,获路无关)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True   # 置一次性标志位:达标发放 = 确定事件,锁确定面写通道
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card', sig=_LSIG)
    gs.observe(gs.bench, BenchView(slots=_slots(bench), capacity=9),
               sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def _set_bench(gs: GameState, bench: list[tuple[str, int]]) -> None:
    gs.observe(gs.bench, BenchView(slots=_slots(bench), capacity=9),
               sig=_SIG_OBS)


def _advance(gs: GameState, plane: int, round_num: int) -> None:
    assert advance_node_effective(gs, (plane, round_num), actor='TestDriver',
                                  sig=_LSIG, source='logic'), \
        f'推进被去重守卫挡下: {(plane, round_num)}'


def test_hold_card_pool_met_grants_and_latches() -> None:
    """触发主条(锁 2a):持卡 + 池 8 同名单位 → tick → equips 追加完美
    投影仪(发放) + 落一次性标志位(「首次」封账);发放走确定面(source=logic,
    rand=False 置一次性标志位状态容器),evidence 留证 = strategy_conditional_grant:
    <卡名>(gain_equipment #equip 后缀链,披露键 1)。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 8, equips=[])
    _advance(gs, 1, 1)
    assert gs.equips.value == [_EQUIP], f'未发放: {gs.equips.value!r}'
    assert gs.equips.source == 'logic', '确定事件应走确定面写'
    assert gs.equips.evidence == f'strategy_conditional_grant:{_CARD}#equip'
    assert gs.strategy_conditional_done.value == (_CARD,), \
        f'未落一次性标志位: {gs.strategy_conditional_done.value!r}'
    assert gs.strategy_conditional_done.source == 'logic', '一次性标志位 = 登记事实直写'
    assert gs.strategy_conditional_done.evidence \
        == f'strategy_conditional_grant:{_CARD}'
    # 同序位重复 tick(advanced 位闸):零二次发放
    tick_effect_boundary(gs)
    assert gs.equips.value == [_EQUIP], '同节点重复 tick 二次发放'


def test_below_threshold_zero_grant_zero_latch() -> None:
    """未达阈(锁 2b):持卡 + 池 7 同名 → tick 后零发放零一次性标志位。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 7, equips=[])
    _advance(gs, 1, 1)
    assert gs.equips.value == [], '未达阈误发放'
    assert gs.strategy_conditional_done.value in (None, ()), '未达阈误置一次性标志位'


def test_no_card_pool_met_zero_grant() -> None:
    """未持卡(锁 2c):池 ≥8 同名但未持卡 → 零发放零一次性标志位(持卡为条件
    前置,active_strategies ∩ 注册表为空即整效果条目无候选)。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 8, equips=[], card=None)
    _advance(gs, 1, 1)
    assert gs.equips.value == [], '未持卡误发放'
    assert gs.strategy_conditional_done.value in (None, ()), '未持卡误置一次性标志位'


def test_out_of_registry_card_zero_write() -> None:
    """表外卡零写(锁 9):持注册表外卡(躺平) + 池 ≥8 → 零发放零一次性标志位
    (表外卡一律无条目,禁从效果原文自动猜装的通道纪律)。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 8, equips=[], card='躺平')
    _advance(gs, 1, 1)
    assert gs.equips.value == [], '表外卡误发放'
    assert gs.strategy_conditional_done.value in (None, ()), '表外卡误置一次性标志位'


def test_pool_covers_bench_deployed_overflow() -> None:
    """池口径三域(裁决点 4):6 备战 + 1 上阵 + 1 溢出 = 8 同名单位 →
    触发(「拥有」直读全部持有,溢出/备战也是拥有;与 gain_character
    升星判断同池)。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 6, equips=[])
    gs.observe(gs.deployed, _dvs([Unit(char_id=_NAME, star=1)], []),
               sig=_SIG_OBS)
    gs.observe(gs.overflow_card, _NAME, sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    _advance(gs, 1, 1)
    assert gs.equips.value == [_EQUIP], \
        '池三域计数缺失(备战 ∪ 上阵 ∪ 溢出)'


def test_unit_count_basis_two_star_counts_one() -> None:
    """单位数口径(锁 4/8,计数口径默认案):7 单位(含 2★ = 1 单位,
    拷贝当量 8)→ 不触发——若按拷贝当量口径此帧必误触发(红判据);
    直置第 8 单位(1★)→ 触发。改判拷贝当量口径时本锁随改。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 6 + [(_NAME, 2)], equips=[])
    _advance(gs, 1, 1)
    assert gs.equips.value == [], '拷贝当量口径误触发(2★ 应计 1 单位)'
    _set_bench(gs, [(_NAME, 1)] * 7 + [(_NAME, 2)])
    _advance(gs, 1, 2)
    assert gs.equips.value == [_EQUIP], '单位数 8 未触发'


def test_latch_blocks_regrant_after_pool_dip_and_restore() -> None:
    """一次性标志位(锁 3):发放后池回落(置 4 同名)→ tick 不重发(条件
    亦不满足);再置回 ≥8 → tick 仍不重发(一次性标志位在)——一次性标志位 = 「首次」语义,
    卖出/合成回落不回滚已发放。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 8, equips=[])
    _advance(gs, 1, 1)
    assert gs.equips.value == [_EQUIP]
    _set_bench(gs, [(_NAME, 1)] * 4)
    _advance(gs, 1, 2)
    assert gs.equips.value == [_EQUIP], '回落窗二次发放'
    _set_bench(gs, [(_NAME, 1)] * 8)
    _advance(gs, 1, 3)
    assert gs.equips.value == [_EQUIP], '一次性标志位后重置池二次发放'
    assert gs.strategy_conditional_done.value == (_CARD,), '一次性标志位值漂移'


def test_unobserved_equips_grant_refused_no_latch() -> None:
    """拒落不落一次性标志位(锁 5a):equips 未观察(None)+ 达标 → tick 后零写零一次性标志位
    (fail-closed,拒落域)——发放与封账都不发生,重试窗口保持开启。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 8, equips=None)
    _advance(gs, 1, 1)
    assert gs.equips.value is None, '未观察窗误写'
    assert gs.strategy_conditional_done.value in (None, ()), '拒落误置一次性标志位'


def test_observed_recovery_self_heal_grants() -> None:
    """拒落自愈(锁 5b):拒落窗后状态容器置为观察态 → 再 tick 补发放 + 落一次性标志位
    (池现值维持达标时后续 tick 重试,「观察恢复后补真值」框架惯例)。"""
    gs = _gs_with_card(bench=[(_NAME, 1)] * 8, equips=None)
    _advance(gs, 1, 1)
    assert gs.strategy_conditional_done.value in (None, ()), '前置:拒落误置一次性标志位'
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    _advance(gs, 1, 2)
    assert gs.equips.value == [_EQUIP], '观察恢复后未自愈补发'
    assert gs.strategy_conditional_done.value == (_CARD,), '自愈补发后未落一次性标志位'
