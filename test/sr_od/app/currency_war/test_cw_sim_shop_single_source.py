"""sim 商店动作单一源纪律锁(P0 切源批)。

背景(ADR-0561,sim 商店动作执行切 simulate 单一源;分歧消解逐条申报表
在该 ADR):sim 引擎对商店动作内联重实现,与 live 投影单一源
``kernel/cw_state.simulate`` 双源,产生逐条语义分歧。P0 批把
BuyCard/SellBench 执行切到 ``engine_p1._simulate_state`` 单一源
(引擎只余预检披露 + 池/经济/账本转录),本文件防「再内联」回漂:

- 锁1(结构):真策略局中 BuyCard/SellBench 执行必经 ``_simulate_state``
  (spy 包装计数 > 0)。LevelUp/RefreshShop 是**申报保留**的引擎侧
  sim-only 语义(LEVEL_CAP=9 冻结 + 免费刷额度注入 + 刷后重采样
  需引擎层牌池),不入本锁——见 engine_p1 分支注释的逐条申报。
- 锁2(行为):带装备备战件被卖 → 装备回 owned 池(ADR-0561 申报表 #7
  已申报行为修正;修复前卖出凭空消失)。语义单一源 = simulate 内部
  ``s.equips.extend(sold.equips)``,本锁只钉引擎路由后的端到端效果。
- 锁3(grep):engine_p1 源内禁再现内联实现特征式(金扣/槽移除/
  卖出清理的旧内联式)。
"""
from __future__ import annotations

import inspect

import pytest

from sr_od.application.currency_war.sim import engine_p1
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1


class _SpySim:
    """``_simulate_state`` 包装:按动作类型计数,转发真实现。"""

    def __init__(self, real) -> None:
        self._real = real
        self.calls: dict[str, int] = {}

    def __call__(self, state, action):  # noqa: ANN001
        k = type(action).__name__
        self.calls[k] = self.calls.get(k, 0) + 1
        return self._real(state, action)


def test_shop_actions_route_through_simulate_single_source(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁1:BuyCard/SellBench 执行经 cw_state.simulate 单一源(真策略局)。"""
    spy = _SpySim(engine_p1._simulate_state)
    monkeypatch.setattr(engine_p1, '_simulate_state', spy)
    for seed in (0, 1):
        simulate_p1(seed, pool='fallback')
    assert spy.calls.get('BuyCard', 0) > 0, \
        '买入执行未走 simulate 单一源(内联回漂?)'
    assert spy.calls.get('SellBench', 0) > 0, \
        '卖出执行未走 simulate 单一源(内联回漂?)'


class _SellEquippedStub:
    """首段商店决策:提案卖出 bench 0 号位(桩只服务本锁的可达性;真策略
    局带装卖出在默认批不可达,见对拍记录)。W6 波 4 黑板容器化:引擎不再
    把帧挂 session(shop_state_frame 写点退役),桩改读容器单例判席;
    带装注入随帧槽退役移入 :meth:`test_sell_equipped_bench_char_recycles_equip`
    的执行帧包装点。"""

    def __init__(self) -> None:
        self.done = False

    def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.kernel.cw_game_state import (
            bench_slots_of,
            board_state_of,
        )
        from sr_od.application.currency_war.kernel.cw_vocab import SellBench
        slots = bench_slots_of(board_state_of(sess))
        if self.done or not slots or slots[0] is None:
            return []
        self.done = True
        return [SellBench(bench_idx=0, reason='stub')]


def test_sell_equipped_bench_char_recycles_equip(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁2:卖带装备战件装备回 owned 池(申报行为修正 #7;修复前
    卖出装备凭空消失,C6 守恒破)。判据 = 卖出轮末 unworn_equips ≥ 1。
    带装注入 = ``_simulate_state`` 包装(W6 波 4 黑板帧就地改写随写点
    退役;包装点在卖出执行帧生效前,守恒判定输入与旧同帧等价)。"""
    real = engine_p1._simulate_state

    def _attach_equip_then_simulate(state, action):  # noqa: ANN001
        if (type(action).__name__ == 'SellBench'
                and getattr(action, 'bench_idx', None) == 0):
            _b0 = state.bench[0] if state.bench else None
            if _b0 is not None:
                _b0.equips = list(_b0.equips or []) + ['铁皮护臂']
        return real(state, action)

    monkeypatch.setattr(engine_p1, '_simulate_state',
                        _attach_equip_then_simulate)
    r = simulate_p1(1, pool='fallback', strategy=_SellEquippedStub())
    sold_rounds = [row for row in r.ledger
                   if any(a.get('__type__') == 'SellBench'
                          for a in row.get('actions') or ())]
    assert sold_rounds, '桩卖出未发生(桩失效)'
    unworn = sold_rounds[0]['sim'].get('unworn_equips') or 0
    assert unworn >= 1, \
        '卖带装备份件后装备未回 owned 池(C6 守恒破;单一源断线?)'


def test_no_inline_shop_action_reimpl_in_engine_source() -> None:
    """锁3(grep):engine_p1 源内禁再现商店动作内联实现特征式。"""
    src = inspect.getsource(engine_p1)
    for banned in ('st.gold -= a.card.cost',       # 买入金扣内联式
                   'st.shop.remove(_slot)',        # 店槽移除内联式
                   'bench_clear(st.bench, a.bench_idx)',  # 卖出清理内联式
                   'st.gold -= 4',                 # 升级花费字面硬编码
                   ):
        assert banned not in src, \
            f'engine_p1 再现商店动作内联实现特征式: {banned!r}'
