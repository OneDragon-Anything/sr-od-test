"""开源节流条件息顶满 kernel 测试(镜像 src = kernel/cw_economy.py 的
strategy_interest_floor + round_start_income interest_floor 参;宿主文件
test_economy.py 超限冻结,按被测函数拆目录新文件落位)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 1/锁 2 +
已退役评审稿(§ 号 = 原稿节序)§3.3 裁决点默认案(1 顶满/6 层序 max(息, floor)+flat):
- 锁 1 检查函数四态 + 并持:持卡∧未花费 → resolved 帽(聚合取宽,
  开源节流+利息上调 → 10/买断制+开源节流 → 9,对表
  test_cap_override_link.test_multi_hold_takes_widest 并持语义);
  已花费/不可评估(None)/未持卡 → 0 保守零顶满(本金充裕金 None
  同款禁猜口径);
- 锁 2 floor 参:缺省 0 现状零漂移(逐字段相等);floor=9 顶满息分量
  (gold=25 自然 2 → 9);gold=100 自然即 9 no-op;flat 层序 = 两修饰
  层分立(max(息, floor)+flat,并持狸财经狸且未花费 9+2=11 同式);
  败补支随计(四分支统一含息分量单点)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_economy import (
    LostNodeRef,
    round_start_income,
    strategy_interest_floor,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)

_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '开源节流'


def _gs(strategies: tuple[str, ...] = (), prev: bool | None = False
        ) -> GameState:
    """直构状态容器种子(prev=None = 不写保持直构 None 态,前置断言同
    test_game_state 直构状态容器不跑种子先例)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if strategies:
        gs.write_logic(gs.active_strategies, list(strategies),
                       produced_by='test-seed', evidence='t:strat', sig=_LSIG)
    if prev is not None:
        gs.write_logic(gs.prev_node_spent, prev,
                       produced_by='test-seed', evidence='t:prev', sig=_LSIG)
    return gs


# ============================================================ 锁 1 检查函数四态 + 并持

@pytest.mark.parametrize(('strategies', 'prev', 'expected'), [
    ((_CARD,), False, 9),      # 持卡 ∧ 未花费 → resolved 帽
    ((_CARD,), True, 0),       # 已花费不授
    ((_CARD,), None, 0),       # 条件不可评估禁猜
    ((), False, 0),            # 未持卡
])
def test_strategy_interest_floor_four_states(strategies: tuple[str, ...],
                                             prev: bool | None,
                                             expected: int) -> None:
    """检查函数四态(锁 1;None = 保守零顶满,与存款回报桥禁猜口径同款)。"""
    assert strategy_interest_floor(_gs(strategies, prev)) == expected


@pytest.mark.parametrize(('strategies', 'expected'), [
    (('开源节流', '利息上调'), 10),   # 并持取宽(对表 test_cap_override_link ⑤)
    (('买断制', '开源节流'), 9),      # 0 与 None 不同层,并持 0 不折叠
])
def test_strategy_interest_floor_multi_hold_takes_widest(
        strategies: tuple[str, ...], expected: int) -> None:
    """并持取宽(锁 1 并持半边):floor = 聚合 resolved 帽,注册行覆写值
    经 aggregate_economy max 归一,与 session 链并持语义同源。"""
    assert strategy_interest_floor(_gs(strategies, False)) == expected


# ============================================================ 锁 2 floor 参(kernel 收入单一源)

def test_floor_default_zero_is_fieldwise_no_drift() -> None:
    """缺省 0 = 现状零漂移(锁 2 第一条):interest_floor 缺省与显式 0
    逐字段相等(现役调用点无感的机械证明)。"""
    base = round_start_income(1, 2, 'reward', 25, 3)
    explicit = round_start_income(1, 2, 'reward', 25, 3, interest_floor=0)
    assert base == explicit, '缺省 0 与显式 0 逐字段相等(dataclass 判等)'


def test_floor_tops_interest_component_below_cap() -> None:
    """顶满息分量(锁 2):gold=25 自然息 min(2, 9)=2 被顶满到 9,total
    相应 +7;分量单点改动,base/streak 零漂移。"""
    natural = round_start_income(1, 2, 'reward', 25, 2)
    topped = round_start_income(1, 2, 'reward', 25, 2, interest_floor=9)
    assert natural.interest == 2, '前置:自然息 = min(gold//10, 5)'
    assert topped.interest == 9, '息分量顶满至 floor'
    assert topped.total == natural.total + 7, 'total 增量 = 顶满差'
    assert (topped.base, topped.streak, topped.branch) \
        == (natural.base, natural.streak, natural.branch), \
        '其余分量零漂移'


def test_floor_noop_when_natural_interest_meets_floor() -> None:
    """金库满档 no-op(锁 2):gold=100 自然息即 9,floor=9 顶满为恒等
    (max 不放大自然值之上的息)。"""
    row = round_start_income(1, 2, 'reward', 100, 0, interest_floor=9)
    assert row.interest == 9, '自然息即帽,顶满 no-op'


def test_floor_layering_flat_added_after_topup() -> None:
    """flat 层序(锁 2;裁决点 6 默认案):floor 作用于帽界利息分量之内,
    flat(狸财经狸固定息)照加其后 = max(息, floor) + flat —— 并持
    开源节流+狸财经狸且未花费 9+2=11 的算式锁(flat 与帽两修饰层分立,
    interest_flat_per_node 字段「与 interest_cap 无关」同口径)。"""
    row = round_start_income(1, 2, 'reward', 25, 0, interest_flat=2,
                             interest_floor=9)
    assert row.interest == 11, 'max(2, 9) + 2 = 11'
    row_no_flat = round_start_income(1, 2, 'reward', 25, 0, interest_floor=9)
    assert row_no_flat.interest == 9, '无 flat 同局恒等 9(两修饰层分立)'


def test_floor_applies_to_loss_comp_branch() -> None:
    """败补支随计(锁 2):息分量 = 四分支统一单点,败补(base+息、连胜
    取 0)的息同被顶满(economy.md 败轮实发 = 基础+利息口径自然延伸)。"""
    row = round_start_income(
        1, 3, 'battle', 25, 4,
        lost_node=LostNodeRef(plane=1, round_num=2, node_type='battle'),
        interest_floor=9)
    assert row.branch == 'loss_comp', '前置:败补支'
    assert row.interest == 9, '败补支息分量同被顶满'
    assert row.streak == 0, '败补支连胜取 0(现役口径回归基准)'
