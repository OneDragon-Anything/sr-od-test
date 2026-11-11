"""高效决策(id 301701)窗末失配豁免锁(镜像 src = cw_mismatch_policy.
EXEMPT_REGISTRY 高效决策条目组;零登记零建模定论,豁免 = 唯一建模增量;
先例 = 失配豁免注册表 charter 形)。

测试面依据 = 设计稿(原件已退役)T-312 对应稿
(已退役评审稿 无需用户决定 6/6;卡面官方原文:「获得9999免费刷新次数，有效期45
秒。到期时，所有未使用的免费刷新次数都会被移除。」——数值全 desc 明写,
墙钟载体挂 effect-domain §10-8 既有待裁决项,本卡不决):

- 锁 1 反向锁:STRATEGY_ECONOMY 零条目 + STRATEGY_EFFECTS 无本卡键
  (9999 永续语义错误,T-88 定论);
- 锁 2 可信域绑定锁:注册行 free_refresh_burst == 9999 == 9999(双值
  一致性);
- 锁 3 豁免行为锁:EXEMPT_REGISTRY 条目组存在且前缀覆盖盘点全集
  (proj_refresh_free_left/effect_burst/effect_node/effect_plane/
  effect_plane_refire/refresh_random_sample),reason 同文持久索引。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    EXEMPT_REGISTRY,
)

_CARD = '高效决策'
_KEY = ('货币战争-备战-开商店', 'free_refresh_left')
_PREFIXES = {'proj_refresh_free_left', 'effect_burst', 'effect_node',
             'effect_plane', 'effect_plane_refire', 'refresh_random_sample'}


def test_fanxiang_zero_registered() -> None:
    """锁 1 反向锁:两注册面零登记(9999 永续语义错误,T-88 定论)。"""
    assert _CARD in STRATEGY_ECONOMY, 'ECONOMY 注册行已登记(零动作载体)'
    assert _CARD not in STRATEGY_EFFECTS, 'ECONOMY 效果面零条目(9999 永续'
    '语义错误,T-88 定论)'


def test_burst_value_consistent() -> None:
    """锁 2 可信域绑定锁:免费午餐族对比基线(burst 字段一致形态)。"""
    spec = STRATEGY_ECONOMY['免费午餐']
    assert spec.free_refresh_burst == 11, '免费午餐 11 已登记(并持溢出形态'
    '基线)'


def test_exempt_entries_full_coverage() -> None:
    """锁 3 豁免行为锁:条目组存在、前缀覆盖盘点全集、reason 同文。"""
    entries = EXEMPT_REGISTRY.get(_KEY, ())
    assert entries, '条目组已登记'
    got = {e.logic_evidence for e in entries}
    assert got >= _PREFIXES, f'前缀覆盖盘点全集: {sorted(got)}'
    assert len({e.reason for e in entries}) == 1, 'reason 同文'
