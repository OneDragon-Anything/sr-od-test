"""大裁员注册面测试(cw_investments 分目录镜像;卖全场族/板面重写族
出售支,先例 = 同目录 test_strategy_gudinglicai_registry.py)。

测试面依据 = 迭代设计 designs/T-186-dacaiyuan.md §2.1/§2.3/§4(锁 1/
锁 2)+ 六裁决点默认案(经族级授权收口)。卡面官方原文
(cw_invest_data.py:134 逐字):「出售场上和备战席的所有角色，获得双倍
价格的金币。获得6次免费刷新。」

- EffectSpec 条目锁(锁 1):id/trigger/duration/category 五元组 +
  载体双载(board_rewrite=素出售语义 / free_refresh_burst=6)+
  duties.predict 单置(一次性 burst 无计数器面,不设 track);
- 注册值锁(锁 2):STRATEGY_ECONOMY burst == 6(官方卡文;注册值
  原为 5 = 已裁漂移且无运行时消费点,订正随批)且 == 条目载荷值
  (双源同值正验);负验 = monkeypatch 注入 burst≠6 注册行实例 →
  双源同值条件失配(frozen 载体禁字面 mutation,注入 + 直读房法;
  治理后形无 import 校验闸,双源对账归本锁——2026-10-28 治理裁定
  「防登记笔误类 import 校验禁新增」);
- 交付通道锁:两条效果条目全在获得链只登记不写状态的实现分支,③段效果体表零新增(键集断言
  零联动);
- 待建模登记锁(裁决点 4):卡级 PENDING 行存续 + 描述非空 + 现金分
  fail-closed(退款腿无字段载体非估值常量,×2 修饰施径缺口待实采,
  估值塌 0 = 治理账零行为)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    BOARD_REWRITE_SELL_ALL,
    BOARD_REWRITE_SELL_ALL_DEAL,
    DurationKind,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    STRATEGY_ECONOMY_PENDING_MODELING,
    strategy_economy_value,
)

_CARD = '大裁员'


def test_dacaiyuan_effect_spec_entry() -> None:
    """锁 1(条目锁):五元组 + 载体双载 + duties.predict 单置;构建
    校验复跑不炸(孤儿键/id 双匹配漂移哨在役)。"""
    cw_investments._validate_strategy_effects()
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '202101'
    assert spec.trigger is TriggerKind.INSTANT
    assert spec.duration is DurationKind.ONCE
    assert spec.category is EffectKind.BATTLEFIELD
    assert spec.payload.board_rewrite == BOARD_REWRITE_SELL_ALL, \
        '素出售语义(卡文无发牌句,发牌判据细分后不入 sim 发牌集)'
    assert spec.payload.free_refresh_burst == 6, '官方卡文「获得6次免费刷新」'
    assert spec.duties.predict is True, \
        'predict=清场+6 刷改变商店决策上下文,买牌/读牌对账须预知'
    assert spec.duties.track is False, '一次性 burst 无剩余期,counter 不建'
    assert spec.pending is False


def test_dacaiyuan_registry_burst_dual_source() -> None:
    """锁 2 正验(注册值锁):注册行 burst == 6(官方卡文,原注册值 5 =
    已裁漂移,订正随批)且 == 条目载荷值(双源同值,注册行为估值面对账源)。"""
    reg = STRATEGY_ECONOMY[_CARD].free_refresh_burst
    payload = STRATEGY_EFFECTS[_CARD].payload.free_refresh_burst
    assert reg == 6, '官方卡文 6(base 层 plaza:202101)'
    assert reg == payload, '双源同值(注册行 ↔ 载体条目)'
    assert STRATEGY_ECONOMY[_CARD].sell_price_mult == 2.0, '×2 卖价修饰在册'


def test_dacaiyuan_registry_burst_drift_breaks_lock(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 2 负验:注入 burst≠6 注册行实例 → 双源同值条件失配(证明本锁
    直读注册行实例、对漂移敏感;治理后形双源对账唯一防线即本锁)。"""
    monkeypatch.setitem(STRATEGY_ECONOMY, _CARD,
                        EconomyEffect(free_refresh_burst=5, sell_price_mult=2.0))
    reg = STRATEGY_ECONOMY[_CARD].free_refresh_burst
    payload = STRATEGY_EFFECTS[_CARD].payload.free_refresh_burst
    assert not (reg == 6 and reg == payload), \
        '漂移注入后锁 2 条件必失配(负验:锁对注册行实例敏感)'
    assert payload == 6, '载荷值不受注入扰动(单一条目不可变)'


def test_dacaiyuan_delivery_channel_registration_leg() -> None:
    """交付通道锁:两条效果条目全在获得链只登记不写状态的实现分支(STRATEGY_EFFECTS 条目),③段
    效果体表零新增(A 案单条目双载,键集闭集断言零联动)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD in STRATEGY_EFFECTS
    assert _CARD not in PICK_INVEST_EFFECTS, '登记腿交付,③段零新增'


def test_dacaiyuan_pending_modeling_and_cash_failclosed() -> None:
    """待建模登记锁(裁决点 4 默认案):卡级 PENDING 行存续 + 描述非空
    (治理账可见性,零运行时闸);现金分 fail-closed——退款腿无字段载体
    (依赖场上构成,非估值常量),burst/sell_price_mult 均待建模分类塌 0。"""
    assert _CARD in STRATEGY_ECONOMY_PENDING_MODELING, '卡级 PENDING 行在册'
    assert STRATEGY_ECONOMY_PENDING_MODELING[_CARD], '描述非空'
    assert BOARD_REWRITE_SELL_ALL_DEAL != BOARD_REWRITE_SELL_ALL
    gs = game_state_of(SimpleNamespace())
    assert strategy_economy_value(_CARD, gs) == (0.0, False), \
        '现金分 fail-closed(无计分通道字段)'
