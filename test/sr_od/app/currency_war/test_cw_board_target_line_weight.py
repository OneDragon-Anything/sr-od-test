"""B_t(板面目标线承重计数)kernel 计数正确性锁。

单一源 = kernel.cw_deploy_logic.board_target_line_weight(禁第二实现);
锚值经注册表直调复算(cw_chars.CHARACTERS 全羁绊 factions+flows 并计,
线内集 = TRANSITION_TRAITS 三羁绊阵营 ∪ 希儿系放大器阵营)。病灶帧锚
= 二十一局 P2r2(转型臂 DESIGN §5 回放帧:deployed = 爻光/藿藿/忘归人/
符玄/艾丝妲/椒丘 六过渡件)。纯遥测观测面,本锁只锁计数语义。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SEELE_AMP_FACTIONS,
    SYSTEM_CARDS,
    SYSTEM_LINE_FACTIONS,
    TRANSITION_TRAITS,
    board_target_line_weight,
)

# 二十一局 P2r2 病灶帧 deployed 六件(复盘档案帧序;注册表直调复算
# 六件全为线内件 → B_t = 6)
P2R2_DEPLOYED = ['爻光', '藿藿', '忘归人', '符玄', '艾丝妲', '椒丘']


def test_p2r2_anchor_counts_six() -> None:
    """病灶帧锚:六过渡件全为线内承重件,B_t = 6(注册表直调复算一致)。"""
    assert board_target_line_weight(P2R2_DEPLOYED) == 6


def test_anchor_derivable_from_registry() -> None:
    """锚值可由注册表独立复算(判据源直核,防锁值与注册表漂移):
    逐件全羁绊 ∩ 线内集非空,或希儿本人。"""
    n = 0
    for name in P2R2_DEPLOYED:
        ch = CHARACTERS.get(name)
        assert ch is not None, f'锚帧角色 {name} 应在注册表'
        bonds = set(ch.factions or ()) | set(ch.flows or ())
        assert bonds & SYSTEM_LINE_FACTIONS, f'{name} 应为线内件'
        n += 1
    assert n == 6


def test_dual_bond_piece_counts_once() -> None:
    """双籍件只计 1(件级非阵营级):桑博 = 贝洛伯格 + 持续伤害双承重
    身份,仍只计 1 件。"""
    assert board_target_line_weight(['桑博']) == 1


def test_seele_personally_counts_as_single_card() -> None:
    """希儿本人单卡计入(希儿系单卡判据;不看放大器档)。"""
    assert board_target_line_weight(['希儿']) == 1


def test_off_line_and_unregistered_not_counted() -> None:
    """线外注册件与未注册件不计(空名/假名 → 空集不命中)。"""
    assert board_target_line_weight([]) == 0
    assert board_target_line_weight(['', '未注册假名']) == 0


def test_line_faction_set_derivation() -> None:
    """线内阵营集 = TRANSITION_TRAITS 三羁绊阵营 ∪ 希儿系放大器阵营
    (与 engines_count 同辖域的派生关系锁;阈值经 FACTIONS 注册表)。"""
    assert TRANSITION_TRAITS == tuple(
        (card.judge_factions[0], FACTIONS[card.judge_factions[0]].tiers[0])
        for card in SYSTEM_CARDS.values() if card.card_id != 'seele')
    assert SYSTEM_LINE_FACTIONS == (
        frozenset(b for b, _t in TRANSITION_TRAITS) | SEELE_AMP_FACTIONS)
    assert '量子同频' in SYSTEM_LINE_FACTIONS
    assert '贝洛伯格' in SYSTEM_LINE_FACTIONS
