"""现金为王(id 250301)卖全场通道桥记账锁(cw_investments 分目录镜像;
kernel/test_effect_inventory.py 桥行为锁同源)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§3 锁面(卡面官方原文 cw_invest_data.py:200 逐字:
「出售场上和备战席的所有角色，之后每场进入战斗时，为我方前台提供护盾，
护盾量等同于该次出售角色所获得总金币数*1000。」):

- 桥记账锁:counters['shield_bank'] = 出售退款合计×1000(系数以测试字面
  量 1000 独立对拍,不引生产常量防同源漂移;键集断言恰 {'shield_bank'},
  固化 track=False 下无 bump_key 噪声键);空场退款零 → 无该键;
- fail-closed 锁:出售域未全读(partial_read)→ 退款零写入 ∧ 护盾零记账。

(v4.7 换季机制桥解耦:现金为王 V4.7 退场,注册行条目锁随卡删除;
记账/fail-closed 两锁测的是 apply_board_rewrite 卖全场通道行为
(spec.id == CASH_KING_SPEC_ID 判别的记账桥 = 活代码),载荷直构同形
EffectSpec 注入不查注册表——示范 = test_effect_inventory 板面重写
解耦同款。注册表条目重采时直构值可删。)
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    BOARD_REWRITE_SELL_ALL,
    CASH_KING_SPEC_ID,
    BattlefieldEffect,
    CounterKey,
    DurationKind,
    DutyFlags,
    EffectKind,
    EffectSpec,
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

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')

#: 现金为王载荷直构(机制桥 fixture 解耦:原取注册表['现金为王'],该卡
#: V4.7 退场;记账桥按 spec.id == CASH_KING_SPEC_ID 判别,id/payload
#: 同形保持,桥行为锁面不变)。
_SELL_ALL_SPEC = EffectSpec(
    id=CASH_KING_SPEC_ID, name='现金为王', trigger=TriggerKind.INSTANT,
    duration=DurationKind.WHILE_HELD, category=EffectKind.BATTLEFIELD,
    payload=BattlefieldEffect(board_rewrite=BOARD_REWRITE_SELL_ALL),
    duties=DutyFlags(predict=True),
)


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
    entry = gs.effects.register_strategy(_SELL_ALL_SPEC,
                                         acquired_key=(1, 1))
    report = apply_board_rewrite(gs, _SELL_ALL_SPEC)
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
    # 臂 2:空场(状态容器全读但无可出售面)→ 退款零 → 护盾零记账(无该键)。
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs2.observe(gs2.deployed, DeployedView(
        front_slots=[None] * 4, back_slots=[None] * 6), sig=_SIG_OBS)
    gs2.observe(gs2.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 9, capacity=9), sig=_SIG_OBS)
    entry2 = gs2.effects.register_strategy(_SELL_ALL_SPEC,
                                           acquired_key=(1, 1))
    report2 = apply_board_rewrite(gs2, _SELL_ALL_SPEC)
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
    entry = gs.effects.register_strategy(_SELL_ALL_SPEC,
                                         acquired_key=(1, 1))
    report = apply_board_rewrite(gs, _SELL_ALL_SPEC)
    assert report is not None
    assert report.partial_read is True, 'bench 未读 → 输入不完整(§6.3)'
    assert report.refund_gold > 0, '已读面退款留证据(partial 证据形态)'
    assert gs.gold.value == 10, '退款零写入(禁把部分退款标成权威值)'
    assert CounterKey.SHIELD_BANK not in entry.counters, \
        '护盾零记账(fail-closed 同闸:partial_read → 禁部分记账)'
    assert entry.counters == {}
