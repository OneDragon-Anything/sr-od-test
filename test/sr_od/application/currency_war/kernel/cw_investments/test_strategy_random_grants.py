"""策略卡获得时点随机策略发放注册表测试(镜像 src =
kernel/cw_investments.py 的 STRATEGY_RANDOM_GRANTS + 构建校验 + 披露键
常量)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§2.2/§4.3/§6 + REVIEW
T331 §4.2-R2(granted 卡 overlay 缺口按 40/135 现值申报):
- 登记单一源:行值 = 卡面效果原文直读(远见 id 303601,「获得一个随机
  黄金投资策略」→ 发放品质词「金」;全池唯一直接发放形状——期货/白银
  投资族系「三选一」offer 形状归 STRATEGY_DELAYED_OFFERS,不入本表);
- 构建校验三哨(漂移哨,import 即炸语义经直调校验函数锁定,治理口径 =
  2026-10-28「只能由写表人笔误触发的校验删,能被游戏版本变更独立触发的
  漂移哨留」):孤儿键 / 品质词漂移 / 目标品质池空;
- 远见 ∉ STRATEGY_EFFECTS(裁决点 8:零 trigger/burst/板面载荷,声明性
  条目零消费位,burst 桥只读 free_refresh_burst,T-299/T-302 同判);
- 注册面三字段挂值唯一(future_quality_upgrade/difficulty_inflation_
  exempt 全注册表唯一挂值条目 = 远见——效果条目③改写分支判定名与难度豁免
  守卫的注册面基准)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    FORESIGHT_ENV_REWRITE_PRIORITY,
    FORESIGHT_EXEMPTION_READING,
    FORESIGHT_REWRITE_SCREEN_SHAPE,
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    STRATEGY_RANDOM_GRANT_ASSUMPTION_UNIFORM_V0,
    STRATEGY_RANDOM_GRANTS,
    _validate_strategy_random_grants,
)


def test_yuanjian_registry_row_single_source() -> None:
    """登记单一源:表键集闭族现役单卡(远见),行值 = 卡面「黄金投资
    策略」直读品质词「金」;base 溯源(id 303601/棱彩)对拍;金币效果条目与
    难度豁免效果条目归 STRATEGY_ECONOMY 三字段已登记通道不入本表。"""
    assert set(STRATEGY_RANDOM_GRANTS) == {'远见'}, \
        '注册面 = 族现役单卡(直接发放形状全池唯一)'
    assert STRATEGY_RANDOM_GRANTS['远见'] == '金', \
        f"发放品质词漂移: {STRATEGY_RANDOM_GRANTS['远见']!r}"
    base = INVESTMENT_STRATEGIES['远见']
    assert base.source == 'plaza:303601', f'溯源 id 漂移: {base.source}'
    assert base.rarity == '棱彩', '远见自身品质(棱彩)与发放品质(金)分域'
    eco = STRATEGY_ECONOMY['远见']
    assert eco.instant_gold == 15, '效果条目①即时金已登记估值通道(不入本表)'
    assert eco.future_quality_upgrade == 'prism', '效果条目③改写字段已登记'
    assert eco.difficulty_inflation_exempt is True, '难度豁免字段已登记'


def test_yuanjian_not_in_strategy_effects() -> None:
    """远见 ∉ STRATEGY_EFFECTS(裁决点 8):零 trigger/burst/板面载荷,
    声明性条目零消费位(burst 桥只读 free_refresh_burst,远见条目即使
    已登记也无下游);同判 T-299/T-302 已登记先例。"""
    assert '远见' not in STRATEGY_EFFECTS


def test_quality_rewrite_and_exempt_fields_unique() -> None:
    """注册面两字段挂值唯一(全注册表枚举):future_quality_upgrade 挂
    值条目与 difficulty_inflation_exempt=True 条目均恰 = 远见——效果条目③
    改写分支判定名与难度豁免守卫的注册面单一源基准(第二张挂值卡出现时
    本锁先红,实现批须重推触发载体而非静默泛化)。"""
    rewrite_srcs = [n for n, e in STRATEGY_ECONOMY.items()
                    if e.future_quality_upgrade]
    assert rewrite_srcs == ['远见'], f'品质改写挂值唯一被破坏: {rewrite_srcs}'
    exempt_srcs = [n for n, e in STRATEGY_ECONOMY.items()
                   if e.difficulty_inflation_exempt]
    assert exempt_srcs == ['远见'], f'难度豁免挂值唯一被破坏: {exempt_srcs}'


def test_grant_quality_pool_nonempty_and_membership() -> None:
    """发放品质池成员前提(掷骰效果条目池派生判据):'金' 品质池 = 注册表
    rarity 等值过滤非空,granted 候选 ∈ 该池;池规模漂移由注册表派生
    自动跟随,本锁只锚定「值 = 注册表品质词且池派生非空」语义。"""
    quality = STRATEGY_RANDOM_GRANTS['远见']
    pool = [n for n, s in INVESTMENT_STRATEGIES.items()
            if s.rarity == quality]
    assert pool, '目标品质池空(发放类效果条目结构性无产出)'
    assert len(pool) == 135, f'金池规模漂移(2026-11-04 现值 135): {len(pool)}'


def test_disclosure_keys_family() -> None:
    """披露键四枚已登记(§6 设想,常量宿主 = cw_investments):效果条目②分布
    假设键 + 效果条目③形状键 + 豁免读法键 + env 冲突优先级键——键值互异且
    为蛇形字符串(消费面 = sim 随局披露面 disclosures)。"""
    keys = {
        STRATEGY_RANDOM_GRANT_ASSUMPTION_UNIFORM_V0,
        FORESIGHT_REWRITE_SCREEN_SHAPE,
        FORESIGHT_EXEMPTION_READING,
        FORESIGHT_ENV_REWRITE_PRIORITY,
    }
    assert len(keys) == 4, '披露键互异被破坏'
    assert all(isinstance(k, str) and k for k in keys)


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(cw_investments.STRATEGY_RANDOM_GRANTS,
                        '不存在的卡', '金')
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_random_grants()


def test_validator_quality_word_drift_raises(monkeypatch) -> None:
    """构建校验②(品质词漂移哨):值非注册表品质词 → ValueError(写表
    笔误与品质词表扩员双源;词表外值 = 掷骰恒空池静默失联)。"""
    monkeypatch.setitem(cw_investments.STRATEGY_RANDOM_GRANTS,
                        '远见', '钻石')
    with pytest.raises(ValueError, match='品质词漂移'):
        _validate_strategy_random_grants()


def test_validator_quality_pool_empty_raises(monkeypatch) -> None:
    """构建校验③(品质池空哨):值 = 合法品质词但注册表该品质清零
    (品质分布改版可独立触发)→ 同哨 ValueError(池空 = 发放类效果条目结构性
    无产出,失联同①;镜像 STRATEGY_DELAYED_GRANTS 类别池哨两路径同响
    形态)。"""
    monkeypatch.setitem(cw_investments.STRATEGY_RANDOM_GRANTS,
                        '远见', '银')
    real = cw_investments.INVESTMENT_STRATEGIES

    class _NoSilverDict(dict):
        """银品质清空替身(rarity 读数全非银;其余语义透传)。"""

        def values(self):
            return [s for s in dict.values(self)
                    if getattr(s, 'rarity', '') != '银']

    monkeypatch.setattr(cw_investments, 'INVESTMENT_STRATEGIES',
                        _NoSilverDict(real))
    with pytest.raises(ValueError, match='品质池空'):
        _validate_strategy_random_grants()
