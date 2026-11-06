"""概率事件(id 300401)pending 登记条目锁(cw_investments 分目录镜像;
机制修改器 pending 登记,零代码载体[MechanismMutation 申报面];先例 =
同目录 test_strategy_baocang_entry.py 爆仓形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-297 对应稿
§4 锁面(REVIEW-T297 无需用户决定 7/7;卡面官方原文:「刷新时有45%概率获得一次
免费刷新。」——付费域口径待实采 pending 如实标注;写状态副本面 = §6.3
随机分支观察收尾):

- 条目锁:category ECONOMY / payload 同实例单一源对拍 STRATEGY_ECONOMY
  键 / trigger ON_REFRESH / duties 仅 respond=True / pending True;
- 现金 fail-closed 锁:查询键 refresh_free_chance 已登记(ECONOMY 注册
  行值不变)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)

_CARD = '概率事件'


def test_gailv_entry_registered() -> None:
    """条目锁:pending 登记形(payload 同实例单一源;duties 仅 respond;
    pending True)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '300401', 'id 对拍'
    assert spec.category.value == 'economy', 'category = ECONOMY'
    assert spec.payload is STRATEGY_ECONOMY[_CARD], 'payload 同实例单一源'
    assert spec.duties is not None and spec.duties.respond, 'respond=True'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict), \
        'track/predict False'
    assert spec.pending is True, 'pending True(口径待实采)'


def test_gailv_economy_registry_unchanged() -> None:
    """ECONOMY 注册行值不变锁(refresh_free_chance=0.45)。"""
    assert STRATEGY_ECONOMY[_CARD].refresh_free_chance == 0.45, '值不变'
    assert INVESTMENT_STRATEGIES[_CARD].effect == \
        '刷新时有45%概率获得一次免费刷新。', '卡面单一源'
