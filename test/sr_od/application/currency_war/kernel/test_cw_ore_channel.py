"""cw_ore_channel 镜像测试:惊喜盒板件观察写入口(giftbox_sight)。

锁面 = 迭代设计 已退役账本
giftbox-piece-obs.md §4.2(上报语义矩阵)+ §4.3(零纠偏核心裁定锁)。
晶矿侧(report_spheres_observed / check_ore_declared_level)锁面住
test_ore.py(存量机制主题文件),本文件不重复。
"""
from __future__ import annotations

import sr_od.application.currency_war.kernel.cw_game_state as gs_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    seed_opening_state,
)
from sr_od.application.currency_war.kernel.cw_ore_channel import (
    report_giftbox_sight_observed,
)

_SIG = ChannelSig(family='obs', actor='TestGiftboxChannel', mode='read')
_SIG_LOGIC = ChannelSig(family='logic_hook', actor='TestGiftboxChannel',
                        group_id='test:giftbox')   # logic 写通道族校验专用


def _seeded_gs() -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    return gs


def _tap_journal(monkeypatch) -> list[dict]:
    """接状态容器 journal sink(行含 field/sig 键,过滤键用法同
    test_game_state 每局全新创建种子行断言)。"""
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    return rows


def test_report_matrix_whole_tuple_replacement() -> None:
    """矩阵行1/行2:读到数字 → 整条一次替换写。多件全报;部分可读 =
    可读子集整条替换(不可读件上一帧读数随写丢失,设计披露 4/5——
    tuple 无件级身份,件级并集不可实现);写入 = observation 通道,
    evidence 进 Field(快照 prov 面)。"""
    gs = _seeded_gs()

    report_giftbox_sight_observed(gs, (12, 10), sig=_SIG,
                                  evidence='giftbox#p1-r2')
    assert gs.giftbox_sight.value == (12, 10), '多件全报'
    assert gs.giftbox_sight.source == 'observation', '观察通道'
    assert gs.giftbox_sight.evidence == 'giftbox#p1-r2', 'evidence 落 prov 面'

    report_giftbox_sight_observed(gs, (9,), sig=_SIG, evidence='giftbox#p1-r3')
    assert gs.giftbox_sight.value == (9,), \
        '部分可读 = 可读子集整条替换(非件级并集)'


def test_report_matrix_empty_zero_write(monkeypatch) -> None:
    """矩阵行3:全未检出/OCR 全败(空 readings)→ no-op 零写——域原值
    与来源保持,无「空读」形态;本路径零 giftbox_sight journal 行
    (经写入口 no-op 证实,非写后回滚)。"""
    gs = _seeded_gs()
    report_giftbox_sight_observed(gs, (12,), sig=_SIG,
                                  evidence='giftbox#p1-r2')
    rows = _tap_journal(monkeypatch)

    report_giftbox_sight_observed(gs, (), sig=_SIG, evidence='giftbox#p1-r3')

    assert gs.giftbox_sight.value == (12,), '零写:域原值保持(滞留语义)'
    assert gs.giftbox_sight.evidence == 'giftbox#p1-r2', '来源保持(无新写)'
    assert not [r for r in rows if r['field'] == 'giftbox_sight'], \
        '零写路径不产生任何 journal 行'


def test_report_never_touches_pending_item_opens(monkeypatch) -> None:
    """零纠偏核心裁定锁:观察写前后 pending_item_opens 逐位不变、写侧
    零队列 journal 行——观察域任何值(含与队列推算必然不一致的读数)
    不触发队列写端;逻辑态恒由战斗结算/节点推进等模型事件链更新,
    差异留证给离线校准批(运行时零比较零纠偏)。"""
    gs = _seeded_gs()
    queue = (('命运礼物', (1, 3)),)
    gs.write_logic(gs.pending_item_opens, queue, produced_by='t',
                   sig=_SIG_LOGIC)
    rows = _tap_journal(monkeypatch)

    for readings in ((12,), (12, 10), ()):   # 含空读与多件形态
        report_giftbox_sight_observed(gs, readings, sig=_SIG,
                                      evidence='giftbox#p1-r2')

    assert gs.pending_item_opens.value == queue, '队列逐位不变'
    assert not [r for r in rows if r['field'] == 'pending_item_opens'], \
        '队列零 journal 行(零写端)'
    assert gs.giftbox_sight.value == (12, 10), '观察域照常留证'
