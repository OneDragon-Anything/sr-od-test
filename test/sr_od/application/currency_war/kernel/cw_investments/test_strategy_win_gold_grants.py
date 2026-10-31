"""策略卡胜利结算条件金登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_WIN_GOLD_GRANTS + 构建校验 + 触发域披露键)。

测试面依据 = 迭代设计 designs/T-130-zhaocai-gou.md §4 锁 1/锁 7 +
REVIEW-T130(免裁 8/8;值域校验按 2026-10-28 治理口径不设——手抄常量
纯笔误类,游戏版本变更不可能独立触发;孤儿键哨留——版本改名/移除可
独立触发;直构形态先例 = 同目录 test_strategy_encounter_battle_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(招财狗 id 103501:「每有一个佩佩
  就会为你提供1金币」→ 每佩佩 1 金;佩佩召唤腿「获得一个佩佩」归
  cw_gain_effects 具名角色发放名单,不入本表);
- 计数单位与登记面对拍:本表语义的计数目标单位 = 招财狗登记行
  chars_immediate(卡授予「佩佩」、结算数「佩佩」,同名单一源);
- 构建校验 1 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    _WIN_GOLD_COUNT_UNIT,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_GRANTS,
    STRATEGY_WIN_GOLD_GRANTS,
    STRATEGY_WIN_GOLD_SCOPE_ASSUMPTION,
    _validate_strategy_win_gold_grants,
)

_CARD = '招财狗'


def test_registry_row_single_source() -> None:
    """登记单一源(设计 §4 锁 1):招财狗行 = 卡面数值直读(每佩佩 1 金);
    键 ∈ 策略注册表(孤儿哨现值通过 = import 过闸即证,显式对拍防静默
    漂移);注册面 = 族现役首例(同族后续条件金卡各自独立批,禁顺手代
    登记)。"""
    assert set(STRATEGY_WIN_GOLD_GRANTS) == {_CARD}, \
        '注册面 = win 结算腿族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_WIN_GOLD_GRANTS[_CARD] == 1, \
        f'行值漂移(卡面明写每佩佩 1 金): {STRATEGY_WIN_GOLD_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_count_unit_matches_grant_registration() -> None:
    """计数单位与登记面单一源对拍:触发函数数「佩佩」= 招财狗登记行
    授予的单位(卡面「获得一个佩佩…每有一个佩佩」同句同单位,两表面
    独立字面量的漂移唯此锁可暴露)。"""
    assert _WIN_GOLD_COUNT_UNIT == '佩佩'
    assert STRATEGY_GRANTS[_CARD].chars_immediate == (_WIN_GOLD_COUNT_UNIT,), \
        'win 金计数单位 ≠ 登记行授予单位(两表面漂移)'


def test_scope_disclosure_key_registered() -> None:
    """披露键常量在册且值非空(设计 §4 锁 7 的 kernel 面;触发域 = desc
    未写明面的建模假设申报,消费 = sim disclosures setdefault,随局形态
    由 sim 链锁承载)。"""
    assert isinstance(STRATEGY_WIN_GOLD_SCOPE_ASSUMPTION, str)
    assert STRATEGY_WIN_GOLD_SCOPE_ASSUMPTION, '披露键值非空'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。值域按 2026-10-28 治理口径不设,
    无对应锁(校验函数本体亦不存在,防哨复增由评审把关)。"""
    monkeypatch.setitem(STRATEGY_WIN_GOLD_GRANTS, '不存在的卡', 1)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_win_gold_grants()
