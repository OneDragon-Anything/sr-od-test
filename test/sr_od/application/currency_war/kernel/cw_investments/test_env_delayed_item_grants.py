"""世界发放域倒计时件登记表测试(镜像 src = kernel/cw_investments.py 的
EnvDelayedItemGrant + ENV_DELAYED_ITEM_GRANTS + _validate_env_delayed_
item_grants;按拆目录规范落位,存量命运礼物段 =
kernel/test_cw_investments.py DELAYED 段〔超限只读复用〕)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/REVIEW-T329.md
§五④ 锁 1 + §四基线漂移裁定(M12 校验面治理铁律:防登记笔误校验不加,
漂移哨保留):
- 键域扩展首例(策略道):偶像经济条目 = 卡面效果原文直读(id 303401,
  cw_invest_data.PLAZA_AUGMENTS 同 id 行;「倒计时10个节点」→ 10、
  「完胜…额外减少1点」→ 加速 True、「一个【火花礼盒】」→ 件名);
- 孤儿键哨键域 = INVESTMENT_ENVS ∪ INVESTMENT_STRATEGIES(世界发放域
  = 环境 ∪ 策略):策略孤儿键炸、环境孤儿键炸(存量段同款半边的策略
  道镜像)、**偶像经济同入 STRATEGY_GRANTS + 本表合法不炸**(两条效果条目分表
  正例锁——角色腿具名送卡/礼盒腿队列登记两表通道互斥,防后继把环境域
  ∩ENV_GIFTS=∅ 防呆盲扩到策略域);
- 现役条目锁 + 非占席词表反向锁(火花礼盒 = 战利品区浮动件,若后继批
  惯性把件名加进 BENCH_ITEM_NAMES 派生词表,反向锁红)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_NAMES,
    CHARACTER_ROSTER,
    ENV_DELAYED_ITEM_GRANTS,
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    STRATEGY_GRANTS,
    _validate_env_delayed_item_grants,
)

_CARD = '偶像经济'


def test_idol_economy_registry_row_single_source() -> None:
    """登记单一源:偶像经济行 = 卡面效果原文直读(火花礼盒/倒计时 10/
    完胜加速 True);base 溯源 id 对拍(303401 ↔ plaza:303401)。"""
    row = ENV_DELAYED_ITEM_GRANTS[_CARD]
    assert row.item == '火花礼盒'
    assert row.open_delay_nodes == 10
    assert row.perfect_win_accel is True
    base = INVESTMENT_STRATEGIES[_CARD]
    assert base.source == 'plaza:303401', \
        f'溯源 id 对拍失同步: {base.source}'


def test_dual_leg_split_tables_legal() -> None:
    """两条效果条目分表正例锁(REVIEW-T329 §五④ 锁 1):偶像经济同入
    STRATEGY_GRANTS(角色腿 = 具名送卡)+ 本表(礼盒腿 = 队列登记)
    → 合法不炸;若后继把环境域 ∩ENV_GIFTS=∅ 防呆盲扩成 ∩STRATEGY_
    GRANTS,本卡 import 即红。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_immediate == ('火花',), '角色腿 = STRATEGY_GRANTS 在册'
    assert _CARD in ENV_DELAYED_ITEM_GRANTS, '礼盒腿 = 本表在册'
    _validate_env_delayed_item_grants()   # 两条效果条目分表 = 校验通过零炸


def test_validator_strategy_orphan_key_raises(monkeypatch) -> None:
    """构建校验①策略道半边(孤儿哨键域扩 ∪ INVESTMENT_STRATEGIES):
    策略孤儿键(不在策略/环境注册表)→ ValueError(import 即炸语义,
    直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.ENV_DELAYED_ITEM_GRANTS, '不存在的卡X',
        cw_investments.EnvDelayedItemGrant(item='火花礼盒',
                                           open_delay_nodes=10,
                                           perfect_win_accel=True))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_env_delayed_item_grants()


def test_validator_env_orphan_key_still_raises(monkeypatch) -> None:
    """构建校验①环境道半边回归(键域扩展不缩环境域):环境孤儿键 →
    ValueError(存量 kernel/test_cw_investments.py 同款锁的策略道批
    回归锚)。"""
    monkeypatch.setitem(
        cw_investments.ENV_DELAYED_ITEM_GRANTS, '不存在环境Y',
        cw_investments.EnvDelayedItemGrant(item='惊喜盒',
                                           open_delay_nodes=12,
                                           perfect_win_accel=True))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_env_delayed_item_grants()


def test_loot_float_item_wordlist_untouched() -> None:
    """非占席词表反向锁(REVIEW-T329 §五④ 锁 1 负半边,存量命运礼物
    段「惊喜盒 ∉ BENCH_ITEM_NAMES」同式的策略道镜像):火花礼盒 =
    战利品区浮动件非占席,禁进占席道具派生词表;道具/角色域天然无交集。
    """
    assert '火花礼盒' not in BENCH_ITEM_NAMES, \
        '倒计时件非占席,禁进占席道具词表(战利品区件锁)'
    assert '火花礼盒' not in CHARACTER_ROSTER, \
        '道具/角色域天然无交集(登记面不变量)'
    assert INVESTMENT_ENVS.get(_CARD) is None, \
        '偶像经济 ∈ 策略非环境(键域扩展的成员域事实锁)'
