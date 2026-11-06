"""策略卡等级装备发放检查腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_level_equip_grants 直写本体)。

测试面依据 = 迭代设计 designs/T-141-zuanshi-shangren.md §4 锁 2/3/4/5/6
+ 快照存续(实现批修正:达标态构造 = 直构 level=8 + xp 贴阈〔XP_TO_NEXT_
LEVEL 单一源,8 级直构可得〕经 apply_node_xp 真经验通道跨 9,禁容器直置
达标态绕过经验通道——T-102 锁 2「禁经间接路径假绿」的等级版):
- 跨级发放主链(锁 2):经 apply_node_xp 跨 9 → equips 追加财富宝钻恰
  一次 + 落一次性标志位 + 返回装备名,两写 evidence/sig/source 形态;
- 一次性封账(锁 3):一次性标志位后再查(等级持续 ≥9)零追加零重一次性标志位;
- 未持卡/表外卡零写(锁 4):持卡交集空整腿无候选;
- 宁缺勿造(锁 5):level/equips 现值 None → 零写零一次性标志位,值到位重查自愈;
- 状态检查型语义(锁 6):拿卡时已 level ≥9 → 下一次检查即发放(禁实现
  批顺手改严格跨越型而无锁);
- 快照存续:发放落一次性标志位 → 快照恢复往返 → 恢复局不重发。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    _LEVEL_EQUIP_PRODUCER,
    check_strategy_level_equip_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    restore_state_snapshot,
    seed_opening_state,
)
from sr_od.application.currency_war.sim.cw_sim_backend import apply_node_xp

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '钻石商人'
_EQUIP = '财富宝钻'
_OUT_OF_TABLE = '躺平'   # 已登记策略卡,非本表成员(表外卡禁自动猜装)

_LATCH_EV = f'strategy_level_grant:{_CARD}'


def _seeded_gs() -> GameState:
    """开局种子底座(level=3/xp 现值已登记);达标发放 = 确定事件,置一次性标志位锁
    确定面写通道。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    seed_opening_state(gs)
    return gs


def _hold(gs: GameState, card: str | None = _CARD) -> None:
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card', sig=_LSIG)


def _force_level(gs: GameState, level: int, cur: int, need: int) -> None:
    """直构等级/经验贴阈态(经验通道跨级的起点,非达标态直置)。"""
    gs.observe(gs.level, level, sig=_SIG_OBS)
    gs.observe(gs.xp, (cur, need), sig=_SIG_OBS)


def _cross_via_node_xp(gs: GameState) -> None:
    """经 apply_node_xp 真经验通道跨 9(8→9 门槛 72,battle 节点 +2;
    跨级拍 = 等级真值生产点,生产链路同源)。"""
    assert apply_node_xp(gs, node_type='battle') == 2
    assert int(gs.level.value) >= 9, '前置:未跨 9'


def test_cross_level_grant_main_chain() -> None:
    """跨级发放主链(锁 2):持卡 + 直构 8 级贴阈 → apply_node_xp 跨 9 →
    检查 → equips 追加财富宝钻恰一次 + 落一次性标志位;发放 = 确定事件 logic 写
    (source=logic),evidence = strategy_level_grant:<卡名>(gain_
    equipment #equip 后缀链)/一次性标志位同基串;返回值 = 装备名(调用方据此决定
    宝钻回调)。"""
    gs = _seeded_gs()
    _hold(gs)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    _force_level(gs, 8, 71, 72)
    _cross_via_node_xp(gs)
    granted = check_strategy_level_equip_grants(gs, _LSIG)
    assert granted == _EQUIP, f'跨级未发放: {granted!r}'
    assert gs.equips.value == [_EQUIP], f'发放形态漂移: {gs.equips.value!r}'
    assert gs.equips.source == 'logic', '确定事件应走确定面写'
    assert gs.equips.evidence == f'{_LATCH_EV}#equip'
    assert gs.strategy_conditional_done.value == (_CARD,), '未落一次性标志位'
    assert gs.strategy_conditional_done.source == 'logic', '一次性标志位 = 登记事实直写'
    assert gs.strategy_conditional_done.evidence == _LATCH_EV


def test_latch_blocks_regrant_while_level_holds() -> None:
    """一次性封账(锁 3):发放后等级持续 ≥9 再查 → 零追加零重一次性标志位(一次性标志位 =
    「首次」语义,等级单调不减下达标态持续为真靠一次性标志位封账)。"""
    gs = _seeded_gs()
    _hold(gs)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    _force_level(gs, 8, 71, 72)
    _cross_via_node_xp(gs)
    assert check_strategy_level_equip_grants(gs, _LSIG) == _EQUIP
    for _ in range(2):
        assert check_strategy_level_equip_grants(gs, _LSIG) is None, '一次性标志位后重发'
    assert gs.equips.value == [_EQUIP], '一次性标志位后追加发放'
    assert gs.strategy_conditional_done.value == (_CARD,), '一次性标志位值漂移'


def test_no_card_and_out_of_table_card_zero_write() -> None:
    """未持卡/表外卡零写(锁 4):等级 ≥9 但未持卡 → 零写零一次性标志位;持已登记
    非本表卡(躺平)→ 同零写零一次性标志位(持卡 ∩ 登记表为空整腿无候选,表外卡
    禁从效果原文自动猜装)。"""
    gs = _seeded_gs()
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    _force_level(gs, 9, 0, 84)
    assert check_strategy_level_equip_grants(gs, _LSIG) is None, '未持卡误发放'
    assert gs.equips.value == [] and gs.strategy_conditional_done.value \
        in (None, ()), '未持卡误写'
    _hold(gs, _OUT_OF_TABLE)
    assert check_strategy_level_equip_grants(gs, _LSIG) is None, '表外卡误发放'
    assert gs.equips.value == [] and gs.strategy_conditional_done.value \
        in (None, ()), '表外卡误写'


def test_prefers_silence_on_unobserved_then_self_heals() -> None:
    """宁缺勿造 + 自愈(锁 5):冷建无种子(level/equips 恒 None)→ None
    零写零一次性标志位;equips 先到仍 None(level 缺,禁半发放);level 达标到位 →
    补发自愈(一次性标志位只在发放同窗登记,拒落不落一次性标志位语义)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    _hold(gs)
    assert gs.level.value is None and gs.equips.value is None, '前置:冷建'
    assert check_strategy_level_equip_grants(gs, _LSIG) is None, '全缺误发放'
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    assert check_strategy_level_equip_grants(gs, _LSIG) is None, 'level 缺误发放'
    gs.observe(gs.level, 9, sig=_SIG_OBS)
    assert check_strategy_level_equip_grants(gs, _LSIG) == _EQUIP, '值到位未自愈'
    assert gs.strategy_conditional_done.value == (_CARD,), '自愈补发后未落一次性标志位'


def test_state_semantics_hold_at_level_grants() -> None:
    """状态检查型语义(锁 6):先置 level=9 再持卡(拿卡时已达标)→
    下一次检查即发放——等级 = 容器现值非事件流,拿卡时点无从回溯历史
    跨越,禁实现批顺手改成严格跨越型而无锁(金支同判先例)。"""
    gs = _seeded_gs()
    _force_level(gs, 9, 0, 84)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    _hold(gs)
    assert check_strategy_level_equip_grants(gs, _LSIG) == _EQUIP, \
        '拿卡已达标未发放(状态检查型语义破坏)'
    assert gs.strategy_conditional_done.value == (_CARD,), '未落一次性标志位'


def test_snapshot_roundtrip_latch_honored() -> None:
    """快照存续:达标发放落一次性标志位 → full_state_snapshot → restore 往返 →
    恢复局再查返回 None(中断恢复不重发;五件套 roundtrip 本体 =
    kernel/cw_game_state 锁文件已登记,本锁锁本腿语义层)。"""
    gs = _seeded_gs()
    _hold(gs)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    _force_level(gs, 8, 71, 72)
    _cross_via_node_xp(gs)
    assert check_strategy_level_equip_grants(gs, _LSIG) == _EQUIP
    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, gs.full_state_snapshot())
    restored.prep_anchored = True
    _hold(restored)
    assert restored.equips.value == [_EQUIP] \
        and int(restored.level.value) >= 9, '前置:恢复局现值未随快照存续'
    assert check_strategy_level_equip_grants(restored, _LSIG) is None, \
        '恢复局重发'
    assert restored.equips.value == [_EQUIP], '恢复局库存形态漂移'


def test_producer_signature() -> None:
    """写端署名(家族纪律):producer = 专名 strategy_level_equip_grant
    (新写端新名,不沿用链缺省伪装连续;跨模块断言面 = sim 接线锁)。"""
    assert _LEVEL_EQUIP_PRODUCER == 'strategy_level_equip_grant'
