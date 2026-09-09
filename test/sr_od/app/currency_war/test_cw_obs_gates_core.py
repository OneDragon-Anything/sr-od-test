"""test_cw_obs_gates_core 主题锁——全套件唯一 fail-closed 口径代表(纯函数解析器)。

覆盖面(编排者裁决收缩,2026-09-09:只保留 1 条纯函数「garbage→None/拒绝」
口径锁;其余 fail-closed/闸/读链锁不搬):
- parse_settlement_hp 本体直调:投资策略陷阱文本「每损失20点小队生命值获得5」
  → 「生命值」后非紧邻数字必须拒信 None(不误取 20/5)。喂 OCR token 列表,
  零图像零 OCR 引擎,毫秒级。

来源指针(2026-09-09 目标形态重建批;来源文件在飞 M,以 git show HEAD 已提交
内容为搬水源,断言零改动;其退役随并行批落地后二轮):
- test_cw_obs_gates.py@HEAD(observation 段)。
其余历史锁已退役(git 可复活):防线①读链锁(obs→session 写入正确性 5 测)
与 board fail-closed 闸仍在该在飞本体,按裁决不搬,随二轮处置。
"""
from __future__ import annotations

from sr_od.application.currency_war.obs.cw_settlement_obs import parse_settlement_hp

# 投资策略屏 OCR(含陷阱文本「每损失20点小队生命值获得5」——「生命值」后非紧邻数字,不该误取)。
_INVEST_STRATEGY_OCR = [
    '攻略', '返回备战界面', '请选择投资策略', '正能量', '保险', '幸运喷雾',
    '每损失20点小队生命值获得5', '同于能量上限20%的能量。', '确认',
]


def test_rejects_non_adjacent_digits() -> None:
    """投资策略描述「每损失20点小队生命值获得5」→ 「生命值」后非紧邻数字 → None(不误取 20/5)。"""
    assert parse_settlement_hp(_INVEST_STRATEGY_OCR) is None
