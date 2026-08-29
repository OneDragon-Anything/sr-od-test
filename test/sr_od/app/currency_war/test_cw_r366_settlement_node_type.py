# -*- coding: utf-8 -*-
"""r366 结算屏节点类型真值测试(ADR-0239)。

局48(2026-08-22)七轮结算屏实拍 OCR token 序列(日志逐帧提取),
锁 parse_settlement_node_type 的判读。背景:node_type 生产链
(EnsureShopClosed probe→current/左移/槽序表)在当前备战流
(RunBuyPhase)下零触发,outcomes 恒「普通战斗」——结算屏头部
类型词是唯一在记录时点可得的权威源。
"""
from __future__ import annotations

from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_node_type,
)

# 局48 实拍(逐 token 原样,含 OCR 噪声)
R1_REWARD = ['挑战成功', '奖励', 'Lv.3', '214', '小队生命值82i',
             '获得金币总览', '数据统计', '基础奖励', '6.5万', '连胜×0',
             '掉落晶矿', '继续挑战']
R3_BATTLE = ['挑战成功', '1-3X点', '战斗', '火热连胜×1', 'Lv.4', '0/20',
             '小队生命值86i', '获得金币总览', '数据统计', '基础奖励']
R7_ENCOUNTER = ['挑战结束', '遭遇', '火热连胜×0', '10/20',
                '小队生命值80i', '获得金币总览', '8', '数据统计']
BOSS_HDR = ['35', '挑战结束', '1-6', '战斗', '4/20', '小队命值45i',
            '获得金币总览', '数据统计', '基础奖励', '5']   # 局47 放弃局帧


def test_reward_node() -> None:
    assert parse_settlement_node_type(R1_REWARD) == '奖励'


def test_battle_node_with_noisy_round_token() -> None:
    """'1-3X点'(OCR 噪声)后仍取到「战斗」。"""
    assert parse_settlement_node_type(R3_BATTLE) == '普通战斗'


def test_encounter_after_end_header() -> None:
    assert parse_settlement_node_type(R7_ENCOUNTER) == '遭遇'


def test_boss_header_layout() -> None:
    assert parse_settlement_node_type(BOSS_HDR) == '普通战斗'


def test_base_reward_no_false_hit() -> None:
    """「基础奖励」≠「奖励」(精确 token 匹配,r260 旧顾虑根除)。"""
    texts = ['挑战成功', '基础奖励', '5', '利息']   # 头部无裸「奖励」
    assert parse_settlement_node_type(texts) is None


def test_no_header_returns_none() -> None:
    assert parse_settlement_node_type(['备战阶段', '1-6', '战斗']) is None


# r361b(review A 守卫)形态锁;r366b 追加粘着/emoji/复合词三测
def test_glued_header_token() -> None:
    """OCR 把头部与类型词粘成一个 token('挑战成功战斗')也能解。"""
    texts = ['挑战成功战斗', '火热连胜×1', '小队生命值86']
    assert parse_settlement_node_type(texts) == '普通战斗'


def test_emoji_prefixed_boss() -> None:
    """'👩首领'(emoji 前缀,局48 r9 实拍)后缀匹配 → boss。"""
    texts = ['挑战成功', '👩首领', '火热连胜×1', '小队生命值84']
    assert parse_settlement_node_type(texts) == 'boss'


def test_compound_word_not_matched() -> None:
    """'基础奖励'是长复合词,后缀长度门拒——不误中。"""
    texts = ['挑战成功', '基础奖励', '5', '利息']
    assert parse_settlement_node_type(texts) is None
