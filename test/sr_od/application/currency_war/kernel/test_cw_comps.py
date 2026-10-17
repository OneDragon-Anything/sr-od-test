"""gift_hit_tier 送卡档位机器回归锁(镜像 src = kernel/cw_comps.py 的该
被测函数;此前零直测,本锁 = 估值域「现值不变」防线)。

测试面依据 = T-28 设计稿(迭代 2026-09-23-invest-effects-calc)§2.5 +
§4.3:条件腿建模批对估值域零动作——持续伤害契约(即时集非空,走规则①
即时优先)的档位由 COMP_LIBRARY 数据派生,不得随条件腿引擎落地漂移。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_comps import gift_hit_tier
from sr_od.application.currency_war.kernel.cw_investments import ENV_GIFTS


def test_dot_contract_gift_tier_unchanged() -> None:
    """持续伤害契约估值档位现值锁(T-28 设计稿 §2.5 估值域零动作):
    即时集 {椒丘, 卡芙卡} 非空 → 规则①即时优先取成员最优档;卡芙卡在
    DOT 队等套为 core(COMP_LIBRARY 分档数据派生,档位语义单一源 =
    gift_hit_tier docstring),整卡档 = 'core'。条件腿建模(猜测写+证实)
    不触碰估值域,本值漂移 = 回归信号。"""
    assert gift_hit_tier(ENV_GIFTS['持续伤害契约']) == 'core'
