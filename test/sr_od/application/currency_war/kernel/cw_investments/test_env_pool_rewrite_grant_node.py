"""ENV_POOL_REWRITE 数量通道 direct 调用点(策略大师)登记与闸面测试
(镜像 src = kernel/cw_investments.py 的 `StrategyPoolRewrite.
extra_strategy_grant_node` 字段与 `_validate_env_pool_rewrite` 增量;按拆
目录规范落位本目录,先例 = 同目录 test_env_bond_tier_grants.py;offer 通道
现役闸锁 = kernel/test_cw_investments.py〔已登记超限文件,只读复用不追加〕)。

测试面依据 = 原稿锁面
原稿锁面§4 锁 4(§2.2(b)/(c)/(d) 落地形态;
2026-10-28 校验治理后只留漂移哨——互斥闸/空条目闸/双调用点互斥随防登记
笔误类删除,本文件相应锁随删):
- 登记:策略大师 direct 调用点 (3,5)(「3-5节点」位-轮单点,T-23 裁决 1
  先例联动);
- 调用点结构闸:grant 字段同 offer 字段闸(位面 ∈ PLANE_NODE_TABLES
  且轮次 ≤ 序列长——节点真值表跨版本变化可独立触发)。
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
    """策略大师条目值锁(T-46 设计 §4 锁 4):direct 调用点 = (3, 5)
    (坐标系 = (位面, 轮次) 单点两元各 1 基),offer 字段 None(直发
    非 offer 三选一),纯数量事实条目(零估值字段)与 ENV_ECONOMY 同键
    共存 = 登记数据性质;现表直调校验零炸。"""
    entry = ENV_POOL_REWRITE['策略大师']
    assert entry.extra_strategy_grant_node == (3, 5), '调用点 = P3r5'
    assert entry.extra_strategy_offer_node is None, '直发非 offer 形态'
    assert entry.rewrite_quality == '' and entry.rewrite_picks == ()
    assert entry.offer_structure == '', '纯事实登记,零估值语义字段'
    cw_investments._validate_env_pool_rewrite()


@pytest.mark.parametrize('bad_node,match', [
    ((3, 9), '轮次超位面节点数'),   # P3 序列长 7,轮次 9 超界
    ((4, 1), '位面不在节点真值表'),  # 现役键 {1,2,3}
])
def test_grant_node_structure_gate(
        monkeypatch: pytest.MonkeyPatch, bad_node: tuple[int, int],
        match: str) -> None:
    """grant 调用点结构闸(T-46 设计 §4 锁 4,同 offer 字段闸;漂移哨):
    越界轮次与不在表位面 → 炸(防 sim 调用点比对静默恒 False)。"""
    bad = dict(ENV_POOL_REWRITE)
    bad['策略大师'] = StrategyPoolRewrite(
        extra_strategy_grant_node=bad_node)
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad)
    with pytest.raises(ValueError, match=match):
        cw_investments._validate_env_pool_rewrite()


def test_grant_node_gate_legal_p3r5_passes_and_env_untouched(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """合法调用点放行 + ENV_ECONOMY 零动(T-46 设计 §2.4 复核结论):
    grant 调用点 (3,5) 合法(offer 字段同构先例同款断言位);估值面登记值
    gold_per_strategy_coef=2 不变。"""
    assert ENV_ECONOMY['策略大师'].gold_per_strategy_coef == 2, \
        '估值面登记值不变(变的是消费口径)'
    ok = dict(ENV_POOL_REWRITE)
    ok['联席决策'] = StrategyPoolRewrite(extra_strategy_grant_node=(3, 5))
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', ok)
    cw_investments._validate_env_pool_rewrite()
