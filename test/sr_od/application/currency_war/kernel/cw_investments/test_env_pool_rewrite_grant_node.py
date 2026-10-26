"""ENV_POOL_REWRITE 数量通道 direct 挂点(策略大师)登记与闸面测试
(镜像 src = kernel/cw_investments.py 的 `StrategyPoolRewrite.
extra_strategy_grant_node` 字段与 `_validate_env_pool_rewrite` 增量;按拆
目录规范落位本目录,先例 = 同目录 test_env_bond_tier_grants.py;offer 通道
现役闸锁 = kernel/test_cw_investments.py〔在册超限文件,只读复用不追加〕)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-46-celue-dashi.md(定稿)§4 锁 4(§2.2(b)/(c)/(d) 落地形态):
- 登记:策略大师 direct 挂点 (3,5)(「3-5节点」位-轮单点,T-23 裁决 1
  判例联动);
- 互斥闸语义化:估值语义字段(rewrite_quality/offer_structure)非空条目
  才禁与 ENV_ECONOMY 同键,纯数量事实条目放行;
- 空条目闸:七结构字段全默认 → 炸(挂点被误清 None 即落此闸);
- 双挂点互斥:offer+grant 同条目皆非 None → 炸;
- 挂点结构闸扩展:grant 字段同 offer 字段闸(位面 ∈ PLANE_NODE_TABLES
  且轮次 ≤ 序列长)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ECONOMY,
    ENV_POOL_REWRITE,
    StrategyPoolRewrite,
)


def test_celuedashi_grant_node_registered() -> None:
    """策略大师条目值锁(T-46 设计 §4 锁 4):direct 挂点 = (3, 5)
    (坐标系 = (位面, 轮次) 单点两元各 1 基),offer 字段 None(直发
    非 offer 三选一),纯数量事实条目(零估值字段)与 ENV_ECONOMY 同键
    共存 = 互斥闸语义化豁免的现值形态;现表直调校验零炸。"""
    entry = ENV_POOL_REWRITE['策略大师']
    assert entry.extra_strategy_grant_node == (3, 5), '挂点 = P3r5'
    assert entry.extra_strategy_offer_node is None, '直发非 offer 形态'
    assert entry.rewrite_quality == '' and entry.rewrite_picks == ()
    assert entry.offer_structure == '', '纯事实登记,零估值语义字段'
    cw_investments._validate_env_pool_rewrite()


def test_mutex_gate_semanticized_quality_rewrite_still_banned(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """互斥闸语义化·估值侧仍禁(T-46 设计 §4 锁 4):伪造「品质改写 +
    ENV_ECONOMY 双估值条目」→ 炸(闸防的是估值双通道叠加,估值语义字段
    非空条目不得与 ENV_ECONOMY 同键)。"""
    bad = dict(ENV_POOL_REWRITE)
    bad['策略大师'] = StrategyPoolRewrite(
        rewrite_quality='金', rewrite_picks=(1, 2, 3),
        extra_strategy_grant_node=(3, 5))
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad)
    with pytest.raises(ValueError, match='ENV_ECONOMY 非空'):
        cw_investments._validate_env_pool_rewrite()


def test_mutex_gate_semanticized_offer_structure_still_banned(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """互斥闸语义化·结构侧仍禁(T-46 设计 §2.2(b) 两层表述第二层):
    offer_structure(池结构语义字段,层 E 转正后即第二估值通道,一并禁交
    取保守侧)非空条目与 ENV_ECONOMY 同键 → 炸。"""
    bad = dict(ENV_POOL_REWRITE)
    bad['策略大师'] = StrategyPoolRewrite(
        offer_structure='silver_gold_prism_slots',
        slot_qualities=('银', '金', '棱彩'),
        extra_strategy_grant_node=(3, 5))
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad)
    with pytest.raises(ValueError, match='ENV_ECONOMY 非空'):
        cw_investments._validate_env_pool_rewrite()


def test_mutex_gate_semanticized_fact_only_entry_passes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """互斥闸语义化·纯数量事实条目放行(T-46 设计 §4 锁 4):仅挂点
    字段的条目与 ENV_ECONOMY 成员同键共存 → 不炸(策略大师现役登记形态
    同构,未来新数量通道卡免逐个加白);对照面 = 现役七条全量过闸。"""
    ok = dict(ENV_POOL_REWRITE)
    ok['增发货币'] = StrategyPoolRewrite(
        extra_strategy_grant_node=(2, 6))   # 增发货币 ∈ ENV_ECONOMY
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', ok)
    cw_investments._validate_env_pool_rewrite()


def test_empty_entry_gate_grant_node_cleared_bombs(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """空条目闸(T-46 设计 §4 锁 4):策略大师条目挂点清 None(七结构
    字段全默认 = 无任何语义的登记笔误形状)→ 炸;边界对照 = 仅
    rewrite_settled 单独非默认的条目归 settled 现役闸网(settled 定谳
    形态不抢本闸报错)。"""
    bad = dict(ENV_POOL_REWRITE)
    bad['策略大师'] = StrategyPoolRewrite()
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad)
    with pytest.raises(ValueError, match='空条目'):
        cw_investments._validate_env_pool_rewrite()


def test_dual_node_mutex_offer_and_grant_both_set_bombs(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """双挂点互斥(T-46 设计 §4 锁 4):同条目 offer 与 grant 挂点皆非
    None → 炸(一环境一形态:三选一与直接发互斥)。"""
    bad = dict(ENV_POOL_REWRITE)
    bad['策略大师'] = StrategyPoolRewrite(
        extra_strategy_offer_node=(2, 6), extra_strategy_grant_node=(3, 5))
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad)
    with pytest.raises(ValueError, match='双挂点互斥'):
        cw_investments._validate_env_pool_rewrite()


@pytest.mark.parametrize('bad_node,match', [
    ((3, 9), '轮次超位面节点数'),   # P3 序列长 7,轮次 9 超界
    ((4, 1), '位面不在节点真值表'),  # 现役键 {1,2,3}
])
def test_grant_node_structure_gate(
        monkeypatch: pytest.MonkeyPatch, bad_node: tuple[int, int],
        match: str) -> None:
    """grant 挂点结构闸(T-46 设计 §4 锁 4,同 offer 字段闸):越界轮次
    与不在表位面 → 炸(防 sim 挂点比对静默恒 False)。"""
    bad = dict(ENV_POOL_REWRITE)
    bad['策略大师'] = StrategyPoolRewrite(
        extra_strategy_grant_node=bad_node)
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad)
    with pytest.raises(ValueError, match=match):
        cw_investments._validate_env_pool_rewrite()


def test_grant_node_gate_legal_p3r5_passes_and_env_untouched(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """合法挂点放行 + ENV_ECONOMY 零动(T-46 设计 §2.4 复核结论):
    grant 挂点 (3,5) 合法(offer 字段同构先例同款断言位);估值面登记值
    gold_per_strategy_coef=2 不变。"""
    assert ENV_ECONOMY['策略大师'].gold_per_strategy_coef == 2, \
        '估值面登记值不变(变的是消费口径)'
    ok = dict(ENV_POOL_REWRITE)
    ok['联席决策'] = StrategyPoolRewrite(extra_strategy_grant_node=(3, 5))
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', ok)
    cw_investments._validate_env_pool_rewrite()
