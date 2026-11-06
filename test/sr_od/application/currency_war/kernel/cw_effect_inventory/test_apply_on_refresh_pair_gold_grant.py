"""刷新出对条件金腿判定测试(apply_on_refresh_pair_gold_grant 分方法镜像)。

锁 5(判定边界,直构 payload 逐形态):恰 2 同名成立 / 3 同名单笔(不多发)/
双对(2+2)单笔 / 空槽不参与 / 异 star 同名成立(前瞻锁——采样器直出恒 1★
〔同帧重复同名原生允许、直出 2/3 星概率 = 0 的发牌口径〕,该形态锁的是判定
语义完备性〔卡面「相同的角色」= 同名〕非现役行为,直构面覆盖);附负锁:
无对零写 / gold 未读宁缺勿造跳过 / 零命中保守零动作 / 同触发异载体鸭子缺省。

发金 = ``gs.observe``(sim 状态副本数值面 = 观察通道;gold 现值 None → 跳过,
条件逐刷独立下次刷新自动重查)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    apply_on_refresh_pair_gold_grant,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ShopCard,
    ShopPayload,
    ShopSlot,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)


def _payload(entries: list[tuple[str, int] | None]) -> ShopPayload:
    """定长 5 槽 payload 直构((name, star) 或 None = 空槽;不足补空)。"""
    cards: list[ShopSlot] = []
    for i, entry in enumerate(entries):
        if entry is None:
            cards.append(ShopSlot(kind='empty'))
        else:
            name, star = entry
            cards.append(ShopSlot(
                kind='content',
                card=ShopCard(name=name, faction='散', cost=3, star=star,
                              cost_source='roster', slot=i + 1)))
    while len(cards) < 5:
        cards.append(ShopSlot(kind='empty'))
    return ShopPayload(cards=cards, refresh_probs={})


def _seed_gs(*, gold: int | None = 30, spec_name: str | None = '合并同类项'):
    gs = cw4_gs(gold=gold if gold is not None else 30,
                gold_unread=gold is None, node_fill=False,
                shop_screen='off')
    if spec_name is not None:
        gs.effects.register_strategy(STRATEGY_EFFECTS[spec_name], (1, 2))
    return gs


@pytest.mark.parametrize('entries', [
    [('甲', 1), ('甲', 1), ('乙', 1), None, None],        # 恰 2 同名
    [('甲', 1), ('甲', 1), ('甲', 1), ('乙', 1), None],   # 3 同名 → 单笔
    [('甲', 1), ('甲', 1), ('乙', 1), ('乙', 1), None],   # 双对 → 单笔
    [('甲', 1), ('甲', 2), ('乙', 1), None, None],        # 异 star 同名(前瞻)
    [None, ('甲', 1), None, ('甲', 1), None],             # 空槽不参与判定
])
def test_pair_boundary_forms_grant_one_gold_each(entries) -> None:
    """成立形态逐个:恰一笔 +1(单刷至多一笔;3 同名/双对不多发;异 star
    前瞻形态 = 判定语义完备性覆盖;空槽不参与)。单笔性以 write_seq 增量
    = 1 行(恰一次观察笔)钉死。"""
    gs = _seed_gs()
    seq0 = gs.write_seq
    apply_on_refresh_pair_gold_grant(gs, _payload(entries), frame='refresh')
    assert gs.gold.value == 31, f'{entries}: 出对成立 +1'
    assert gs.gold.source == 'observation', '观察通道'
    assert gs.gold.evidence == 'strategy_refresh_pair_gold@refresh', '证据串'
    assert gs.write_seq == seq0 + 1, '单刷至多一笔(恰一次观察笔)'


@pytest.mark.parametrize('entries', [
    [('甲', 1), ('乙', 1), ('丙', 1), ('丁', 1), ('戊', 1)],  # 全异名
    [('甲', 1), ('乙', 1), ('丙', 1), None, None],            # 各 1 张无对
])
def test_no_pair_zero_writes(entries) -> None:
    """无对负锁:零写(gold 值/来源/证据三面保持种子态,write_seq 不动)。"""
    gs = _seed_gs()
    seq0 = gs.write_seq
    apply_on_refresh_pair_gold_grant(gs, _payload(entries))
    assert gs.gold.value == 30 and gs.gold.source == 'observation', \
        f'{entries}: 无对零写'
    assert gs.write_seq == seq0, '零观察行'


def test_gold_unread_skips_defensively() -> None:
    """gold 现值 None(未观察)→ 宁缺勿造跳过(出对在场、条目在场仍零写;
    条件逐刷独立,下次刷新自动重查)。"""
    gs = _seed_gs(gold=None)
    seq0 = gs.write_seq
    apply_on_refresh_pair_gold_grant(
        gs, _payload([('甲', 1), ('甲', 1), None, None, None]),
        frame='refresh')
    assert gs.gold.value is None, '未读保持未读(禁造)'
    assert gs.write_seq == seq0, '零写'


def test_empty_ledger_and_duck_default_zero_grant() -> None:
    """零命中保守零动作(账本空)/ 同触发异载体鸭子缺省 0(市场干预
    ECONOMY 条目无 gold_per_refresh_pair 字段 → 零授予,零金写)。"""
    gs_empty = _seed_gs(spec_name=None)
    seq0 = gs_empty.write_seq
    apply_on_refresh_pair_gold_grant(
        gs_empty, _payload([('甲', 1), ('甲', 1), None, None, None]))
    assert gs_empty.gold.value == 30 and gs_empty.write_seq == seq0, \
        '账本零命中 = 零动作'

    gs_duck = _seed_gs(spec_name='市场干预')
    seq1 = gs_duck.write_seq
    apply_on_refresh_pair_gold_grant(
        gs_duck, _payload([('甲', 1), ('甲', 1), None, None, None]))
    assert gs_duck.gold.value == 30 and gs_duck.write_seq == seq1, \
        '鸭子缺省 0 零授予(未来同触发异载体卡天然隔离)'
