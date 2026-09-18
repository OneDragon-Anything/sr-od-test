"""CW 动作行归一 reason 键序列化锁(serialize_action 接线面)。

出处(持久索引):提取键序单一源 =
src telemetry/schema.py ``ACTION_REASON_SOURCE_KEYS``(reason → route_tag
→ auth_basis → convert_reason);接线位 = ``serialize_action``
(动作序列化唯一单点,decisions 行与执行回执 action 载荷同源同键)。

锁的语义:动作行统一附归一 ``reason`` 键,消费面(复盘骨架/归因下钻)
不必逐动作类各认各的键。归因遥测面缺陷实证 = 2026-09-15 sim 批
CwActionLevelUpParam 6978 行/CwActionSellBenchParam 3729 行零 reason(r9 争金归因少一层直接证据)。
锁三件事:
1. CwActionLevelUpParam(无 reason 字段,禁新增字段)的归因由既有 route_tag 载体
   承载(桥伴自 Emitted.reason 透传 m3_levelup_batch:<tag>),序列化
   后以归一 reason 键显形;
2. CwActionSellBenchParam 自带 reason 字段(登记门键)优先于 route_tag(键序首
   位);auth_basis 兜底次序亦在键序内;
3. 全空动作 reason = ''(诚实缺省,不虚构归因)。
"""

from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionLevelUpParam,
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.telemetry.schema import (
    serialize_action,
)


def test_serialize_action_attaches_normalized_reason():
    """归一 reason 键矩阵(键序 = ACTION_REASON_SOURCE_KEYS 单一源)。"""
    # CwActionLevelUpParam:route_tag 载体显形(桥伴透传 m3_levelup_batch:<tag>)
    lv = CwActionLevelUpParam(cost=4, auth_basis='arm1',
                 route_tag='m3_levelup_batch:arm1')
    d = serialize_action(lv)
    assert d['reason'] == 'm3_levelup_batch:arm1'
    # CwActionSellBenchParam:自带 reason 字段(登记门键)优先
    sb = CwActionSellBenchParam(bench_idx=2, reason='funding_support')
    d2 = serialize_action(sb)
    assert d2['reason'] == 'funding_support'
    # auth_basis 兜底(键序次位;route_tag/reason 皆空时)
    lv2 = CwActionLevelUpParam(cost=4, auth_basis='must_spend')
    d3 = serialize_action(lv2)
    assert d3['reason'] == 'must_spend'
    # 全空 = 诚实缺省 ''
    d4 = serialize_action(CwActionLevelUpParam(cost=4))
    assert d4['reason'] == ''
