"""利息上调(id 300801)声明性条目锁(cw_investments 分目录镜像;payload
同实例单一源首例;先例 = 同目录 test_strategy_baocang_entry.py 爆仓形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-301 对应稿
(REVIEW-T301 免裁 4/4;卡面官方原文:「获得25金币。你的最大利息提升至
10金币。」——静态分量 interest_cap_override=10 注册行承载;
instant_gold=25 族级缺口维持):

- 条目锁:category ECONOMY / payload **同实例单一源**(is 断言,首例)/
  id 300801 / duties 三位全 False / pending False;
- 注册行值不变锁:interest_cap_override=10。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)

_CARD = '利息上调'


def test_lixishang_entry_identity_payload() -> None:
    """条目锁:声明性条目(payload 同实例单一源首例;duties 全 False;
    pending False)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '300801', 'id 对拍'
    assert spec.category.value == 'economy', 'category = ECONOMY'
    assert spec.payload is STRATEGY_ECONOMY[_CARD], \
        'payload 同实例单一源(is 断言首例)'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False'
    assert spec.pending is False, 'pending False'


def test_lixishang_registry_unchanged() -> None:
    """注册行值不变锁(interest_cap_override=10)。"""
    assert STRATEGY_ECONOMY[_CARD].interest_cap_override == 10, '值不变'
