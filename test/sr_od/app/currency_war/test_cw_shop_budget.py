"""CW 商店/备战预算闸测试(#9):spend_unified 整买拒付锁 + 预算闸拒付
单代表(上位 = P71-b 溢余段闸 ADR-0560;现役 = P72 全段闸 ADR-0576,
证明 = docs/develop/sr_od/application/currency_war/proofs/p72-full-band-budget-gate.md)。

覆盖面(金钱类按 2026-09-09 编排者裁决收缩:实机结算对账 + sim 段检双层
已覆盖预算闸逐面锁族,单位层只留拒付判据本体):
- spend_unified 直测(D-BUYNOTE 整买拒付纪律三分支:散买拦截/整批放行/
  零剩余 click 守卫;原 test_cw_shop_line::test_d_buynote_embedded 承载,
  must_spend_zone 侧等价锁删后全仓唯一载体,D7 消费);
- budget 拒付单代表(归 fail-closed):T-93 中段真洞拒(s110 r6 同参,
  旧 P71-b 在该帧 vacuous 空过 = 事故本体;全段化后中间段逐帧管账)。
退役面:73002 形/开局畅通/分量单一源贴线/ρ 别名委托/契约锚登记/ALL IN
豁免(T-149)/prep 整批推迟(预算闸 12 锁族按裁决不搬,git 可复活)。

来源:shop_line 之 spend_unified 段 + budget_gate 核(2026-09-09 套件
重建批 A,#9;两来源文件已分别按 #8/#5 重建退役)。其余历史锁已退役
(git 可复活)。
"""
from __future__ import annotations

from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as crit_levelup,
)
from test.sr_od.app.currency_war._cw_helpers import (
    battle_state as _state,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp_single_source,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_km as _km_of,
)

_COMP = '列车同行'


def _km() -> list[str]:
    return _km_of(_comp_single_source(_COMP))


# ==================== spend_unified 拒付判据本体(自 test_cw_shop_line 段并入) ====================


def test_spend_unified_whole_batch_discipline():
    """D-BUYNOTE:P48 整买拒付纪律作为常量判据内嵌(spend_unified 直测;
    must_spend_zone 侧等价锁删后本文件为全仓唯一载体,D7 消费)。
    三分支:散买拦截/整批放行/零剩余 click 守卫(clicks_to_next≤0
    ⇒ False,防 0×cost=0 恒过把「无级可升」当「可整批支付」)。"""
    assert not crit_levelup.spend_unified(2, 4, 4)   # 散买拦截
    assert crit_levelup.spend_unified(2, 8, 4)       # 整批放行
    assert not crit_levelup.spend_unified(0, 8, 4)   # 零剩余 click 守卫


# ==================== budget 拒付单代表(自 test_cw_budget_gate 并入) ====================


def test_levelup_budget_gate_midband_dive_rejected():
    """budget 拒付单代表:T-93 签名 A 真洞同参复刻(s110 r6 形):义务买牌
    把金花到 49 后逐击发射,批余 20 金(5 击×4)——τ(49)=4,floor =
    40+2ρ ≥ 40,花后 29 ⇒ 拒 + 拒因 levelup_budget_gate_blocked。旧
    P71-b 在该帧 vacuous 空过(49 ≤ 50)= 真洞本体;全段化后中间段逐帧
    管账。
    (金钱类收缩:73002 深穿/开局畅通/分量单一源/ρ 别名/契约锚/ALL IN
    豁免/prep 整批推迟各行按裁决不搬,git 可复活。)"""
    st = _state(49, 7, xp=(40, 52))
    ok, why = crit_levelup.levelup_budget_gate(
        st, None, 49, 5, tuple(_km()), [], [], 5, 4)
    assert ok is False
    assert why == 'levelup_budget_gate_blocked'
