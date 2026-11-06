"""现金为王(id 250301)注册面+桥记账锁(cw_investments 分目录镜像;卖全场族
素出售第三张 + 护盾记忆量伴生数值,先例 = 同目录 test_strategy_datong_entry.py
条目锁 / kernel/test_effect_inventory.py 桥行为锁——宿主两文件均超行数线,
登记面新锁落本镜像目录新文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-252-xianjin-weiwang.md
§3 锁面(REVIEW-T252 无需用户决定 7/7;卡面官方原文 cw_invest_data.py:200 逐字:
「出售场上和备战席的所有角色，之后每场进入战斗时，为我方前台提供护盾，
护盾量等同于该次出售角色所获得总金币数*1000。」):

- 条目锁:五元组 + 素出售载体 + duties=predict 单置(track=False,裁决点 7)
  + 桥侧常量键×id 对拍(防两处 '250301' 漂移);
- 桥记账锁:counters['shield_bank'] = 出售退款合计×1000(系数以测试字面
  量 1000 独立对拍,不引生产常量防同源漂移;键集断言恰 {'shield_bank'},
  固化 track=False 下无 bump_key 噪声键);空场退款零 → 无该键;
- fail-closed 锁:出售域未全读(partial_read)→ 退款零写入 ∧ 护盾零记账。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    BOARD_REWRITE_SELL_ALL,
    CASH_KING_SHIELD_PER_GOLD,
    CASH_KING_SPEC_ID,
    CounterKey,
    DurationKind,
    EffectKind,
    TriggerKind,
    apply_board_rewrite,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
    _validate_strategy_effects,
)

_CARD = '现金为王'

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')


def _u(cid: str, star: int = 1) -> Unit:
    """单位直构(char_id 不入角色注册表 → 费用查表落中费 3 保守档)。"""
    return Unit(char_id=cid, star=star)


def _read_board(gs: GameState, *, bench_read: bool) -> None:
    """合成已读板面:前台 1 只 1★ / 后台空;bench_read=False 留 bench 从未
    观察(None)构造 partial_read 面。"""
    gs.observe(gs.deployed, DeployedView(
        front_slots=[_u('现金为王测试甲'), None, None, None],
        back_slots=[None] * 6), sig=_SIG_OBS)
    if bench_read:
        gs.observe(gs.bench, BenchView(
            slots=[BenchSlot(kind='unit', unit=_u('现金为王测试乙', star=2))]
            + [BenchSlot(kind='empty')] * 8, capacity=9), sig=_SIG_OBS)


def test_xianjin_weiwang_effect_spec_entry() -> None:
    """锁 1(条目锁):五元组 + 素出售载体 + duties=predict 单置 + 桥侧
    常量键×id 对拍;构建校验复跑不炸(孤儿键/id 双匹配漂移哨在役)。"""
    _validate_strategy_effects()
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '250301', 'id 对拍(checklist :294 三方一致)'
    assert spec.trigger is TriggerKind.INSTANT, '出售+记账选卡时点一次结清'
    assert spec.duration is DurationKind.WHILE_HELD, \
        '护盾在役语义,实例随局存活(裁决点 1)'
    assert spec.category is EffectKind.BATTLEFIELD
    assert spec.payload.board_rewrite == BOARD_REWRITE_SELL_ALL, \
        '素出售语义(卡文无发牌句,不入 sim 发牌判据集)'
    assert spec.duties is not None and spec.duties.predict is True, \
        'predict=出售后板面空,部署/买牌对账须预知'
    assert spec.duties.track is False, \
        'track=False(裁决点 7):记账走桥内直写,免 bump_key 噪声键'
    assert spec.pending is False
    # 桥侧判别键×id 对拍(两处 '250301' 漂移哨,同 HYPEREMIT_SPEC_ID 键×id
    # 测试直锁先例)
    assert spec.id == CASH_KING_SPEC_ID
    assert CASH_KING_SHIELD_PER_GOLD == 1000, \
        '卡文明写换算系数(数值漂移即红)'


def test_xianjin_weiwang_bridge_shield_bank_recorded() -> None:
    """锁 2(桥记账锁):register → apply_board_rewrite → 实例
    counters['shield_bank'] == sell_refund 合计×1000(系数按测试字面 1000
    独立对拍);counters 键集恰 {'shield_bank'}(track=False 无 bump 噪声);
    空场退款零 → 无该键。"""
    # 臂 1:已知构成(前台 1★×1 + 备战 2★×1,费用均落中费 3):
    # 1★ 退 3;2★ = 3×3−1(手续费)= 8;合计 11 → 护盾 11000。
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _read_board(gs, bench_read=True)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    entry = gs.effects.register_strategy(STRATEGY_EFFECTS[_CARD],
                                         acquired_key=(1, 1))
    report = apply_board_rewrite(gs, STRATEGY_EFFECTS[_CARD])
    assert report is not None
    units = ([Unit(char_id='现金为王测试甲', star=1)]
             + [Unit(char_id='现金为王测试乙', star=2)])
    expected_refund = sum(sell_refund(int(u.star), bench_char_cost(u, gs))
                          for u in units)
    assert report.refund_gold == expected_refund == 11, \
        '退款真值(1★=3 + 2★=3×3−1=8);公式漂移即红'
    assert gs.gold.value == 10 + expected_refund, '退款权威入金(记账前提)'
    assert entry.counters == {CounterKey.SHIELD_BANK: expected_refund * 1000}, \
        '护盾记忆量 = 退款×1000(测试字面系数独立对拍)+ 键集恰单键干净'
    assert entry.counters[CounterKey.SHIELD_BANK] == 11000, \
        '×1000 算术硬值对拍(3+8=11 → 11000)'
    # 臂 2:空场(容器全读但无可出售面)→ 退款零 → 护盾零记账(无该键)。
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs2.observe(gs2.deployed, DeployedView(
        front_slots=[None] * 4, back_slots=[None] * 6), sig=_SIG_OBS)
    gs2.observe(gs2.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 9, capacity=9), sig=_SIG_OBS)
    entry2 = gs2.effects.register_strategy(STRATEGY_EFFECTS[_CARD],
                                           acquired_key=(1, 1))
    report2 = apply_board_rewrite(gs2, STRATEGY_EFFECTS[_CARD])
    assert report2 is not None and report2.refund_gold == 0
    assert CounterKey.SHIELD_BANK not in entry2.counters, \
        '空场零记账(fail-closed 同闸:退款零 → 护盾零)'
    assert entry2.counters == {}


def test_xianjin_weiwang_fail_closed_partial_read() -> None:
    """锁 3(fail-closed 锁):bench 从未观察(partial_read=True)→ 退款零
    写入(gold 保持原值)∧ 护盾零记账;已读面退款在报告留存证据
    (BoardRewriteReport.refund_gold × partial_read 形态,存量语义不破)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _read_board(gs, bench_read=False)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    entry = gs.effects.register_strategy(STRATEGY_EFFECTS[_CARD],
                                         acquired_key=(1, 1))
    report = apply_board_rewrite(gs, STRATEGY_EFFECTS[_CARD])
    assert report is not None
    assert report.partial_read is True, 'bench 未读 → 输入不完整(§6.3)'
    assert report.refund_gold > 0, '已读面退款留证据(partial 证据形态)'
    assert gs.gold.value == 10, '退款零写入(禁把部分退款标成权威值)'
    assert CounterKey.SHIELD_BANK not in entry.counters, \
        '护盾零记账(fail-closed 同闸:partial_read → 禁部分记账)'
    assert entry.counters == {}
