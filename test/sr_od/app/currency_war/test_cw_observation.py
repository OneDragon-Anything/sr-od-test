"""货币战争 OCR 观测层测试 —— 纯逻辑(parse_settlement_hp;P1.5 结算屏 hp_after 解析)。

用 2026-08-05 实跑结算屏 OCR 作 fixture(不依赖游戏/截图)。read_round_outcome 涉及 ctx.ocr_service
(需游戏/模型),留集成测;本文件只测纯解析函数。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_observation import parse_settlement_hp
from test import SrTestBase


# 2026-08-05 实跑结算屏 OCR(战斗后「挑战结束」屏):小队生命值=71(战前 84,本战损 13)。
_SETTLEMENT_OCR = [
    '19', '挑战结束', '战斗', '216', '小队生命值71i', '获得金币总览', '数据统计', '基础奖励',
    '5', '试用', '98.3万', '利息C', '试用', '连胜×0', '67.4万', '62.4万', '继续挑战',
]
# 投资策略屏 OCR(含陷阱文本「每损失20点小队生命值获得5」——「生命值」后非紧邻数字,不该误取)。
_INVEST_STRATEGY_OCR = [
    '攻略', '返回备战界面', '请选择投资策略', '正能量', '保险', '幸运喷雾',
    '每损失20点小队生命值获得5', '同于能量上限20%的能量。', '确认',
]


class TestParseSettlementHp(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_parses_hp_from_settlement(self):
        """结算屏「小队生命值71i」→ 71(尾部噪声 'i' 容忍)。"""
        self.assertEqual(parse_settlement_hp(_SETTLEMENT_OCR), 71)

    def test_clean_hp_no_noise(self):
        """无噪声「小队生命值84」→ 84。"""
        self.assertEqual(parse_settlement_hp(['挑战结束', '小队生命值84', '继续挑战']), 84)

    def test_rejects_non_adjacent_digits(self):
        """投资策略描述「每损失20点小队生命值获得5」→ 「生命值」后非紧邻数字 → None(不误取 20/5)。"""
        self.assertIsNone(parse_settlement_hp(_INVEST_STRATEGY_OCR))

    def test_no_lifespan_text_returns_none(self):
        """无「生命值」文本 → None。"""
        self.assertIsNone(parse_settlement_hp(['挑战结束', '数据统计', '继续挑战']))

    def test_out_of_bounds_rejected(self):
        """越界(> HP_MAX)→ 丢弃(防 OCR 垃圾级联)。HP_MIN=0,故 0 允许(见下条)。"""
        self.assertIsNone(parse_settlement_hp(['小队生命值999']))   # > HP_MAX(200)

    def test_zero_hp_allowed_at_min(self):
        """HP=0(阵亡)边界允许(HP_MIN=0)。"""
        self.assertEqual(parse_settlement_hp(['小队生命值0']), 0)
