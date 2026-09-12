"""假游戏骨架行为锁(T-120 sim 重设计 批 0)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/方案.md``,
**易失产物**)§2.2 假游戏状态机设计(状态容器/转移唯一入口 apply/
确定性契约)+ §6.2 批 0 验收「同 seed 逐位可复现」;ADR 落点待 T-120
退役批分配,后续批回填编号。

锁的语义(测试纪律 7「锁的存在性」自检):
- **单一源守卫** = 假游戏日程必经 kernel 真码(sample_node_sequence 同源
  派生,禁 fixture 自造第二张日程表)、动作转移必经 ``cw_state.simulate``
  (方案 §2.2「假游戏不内联任何动作转移」;spy 证明接线面已随 CUT6 瘦身
  批砍除——买入/卖出/合成的单一源现算期望值断言仍 red-proof 转移实现,
  判据与保留核清单 = reports/_cluster_CUT6.md)。
- **行为锁** = 动作/结算的可观测效果;期望值从单一源推导式现算
  (registry 常量/真码 helper,测试纪律 9),零手抄常数。
"""
from __future__ import annotations

import pytest
from fixtures.cw_fake_game import fake_match as fake_match_mod
from fixtures.cw_fake_game.fake_match import (
    PHASE_PREP,
    FakeMatch,
)
from fixtures.cw_fake_game.fake_ports import FakeActionSink, FakeCwObserver

import sr_od.application.currency_war.kernel.cw_vocab as cw_state
from sr_od.application.currency_war.cw_game_ports import (
    action_sink,
    install_game_ports,
    observation_source,
    uninstall_game_ports,
)
from sr_od.application.currency_war.kernel.cw_coarse_battle import WIN_CAP
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BuyCard,
    CwWorkFrame,
    RefreshShop,
    SellBench,
    ShopCard,
    card_cost,
)

_CTX = object()   # 假环境 ctx 不被端口消费(端口只透传),以裸对象表意

#: coarse 胜态显式命中种子(探针记录见 test_coarse_win_returns_win_cap
#: docstring:扫描窗 [1000,1120) 唯一命中,命中率 1/120)。
_COARSE_WIN_SEED: int = 1009


@pytest.fixture(autouse=True)
def _ports_isolated():
    """装过端口的用例 teardown 强制卸载(模块槽进程全局,同 ports 锁)。"""
    yield
    uninstall_game_ports()


def _deal_shop(m: FakeMatch, level: int = 3) -> list[ShopCard]:
    """用状态机自己的抽店流发一帧店(测试只编排,不造真值)。"""
    cards = m.shop_pool.draw_shop(level)
    m.state.shop = list(cards)
    return cards


class TestDeterminism:
    """日程单一源守卫(无剧本时日程 = kernel 真码同源派生)。"""

    @staticmethod
    def _drive(seed: int) -> list:
        """同一剧本驱动一局,收集全轨迹(编排固定,random 全部来自
        match 自身流)。"""
        m = FakeMatch(seed=seed)
        trace: list = []
        m.push_overlay('invest', ['甲', '乙', '丙'])
        for _step in range(3):
            trace.append((m.phase, m.state.node_type, m.state.round_num))
            m.advance_node()
        m.state.gold = 50
        cards = _deal_shop(m)
        if cards:
            res = m.apply(BuyCard(card=cards[0]))
            trace.append(('buy', res.applied, m.state.gold,
                          [c.name for c in m.state.shop]))
        trace.append(m.settle_battle('battle'))
        trace.append(m.settle_battle('reward'))
        trace.append([(f.kind, list(f.payload)) for f in m.overlay_stack])
        trace.append(m.env_fingerprint())
        trace.append([e.method for e in m.observation_log])
        return trace

    def test_sampled_schedule_matches_kernel_single_source(self) -> None:
        """无剧本时日程 = sample_node_sequence 真码(同派生种子下逐位
        同源;禁 fixture 自造第二张日程表)。"""
        import random
        m = FakeMatch(seed=42)
        # 抽取日程流种子:重放主种子派生序(schedule 是第一股)
        master = random.Random(42)
        sched_seed = master.getrandbits(64)
        assert m.node_sequence == fake_match_mod.sample_node_sequence(
            random.Random(sched_seed))

class TestActionTransitionSingleSource:
    """动作转移单一源守卫 + 行为锁(方案 §2.2 商店动作结算行)。"""

    def test_apply_routes_through_cw_state_simulate(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """接线守卫:apply 必经 cw_state.simulate(spy 记调用并转发真
        函数——把 fake_match 的直调改内联 = 本锁红)。"""
        m = FakeMatch(seed=3)
        calls: list[tuple[CwWorkFrame, object]] = []
        real = cw_state.simulate

        def spy(state: CwWorkFrame, action: object) -> CwWorkFrame:
            calls.append((state, action))
            return real(state, action)   # type: ignore[arg-type]

        monkeypatch.setattr(cw_state, 'simulate', spy)
        cards = _deal_shop(m)
        m.state.gold = 30
        before = m.state
        res = m.apply(BuyCard(card=cards[0]))
        assert res.applied
        assert len(calls) == 1
        assert isinstance(calls[0][1], BuyCard)
        # 投影基底 = 转移前状态对象(spy 收到的就是它;apply 后
        # m.state 已指向投影产生的新对象)
        assert calls[0][0] is before
        assert calls[0][0] is not m.state

    def test_buy_card_transition_and_pool_take(self) -> None:
        """买入:金 -cost(单一源 card_cost 现算)、牌落 bench、店槽下架、
        牌池 take(规则外效应一次落定)。"""
        m = FakeMatch(seed=5)
        cards = _deal_shop(m)
        card = cards[0]
        copies_before = m.shop_pool.copies[card.name]
        m.state.gold = 50
        res = m.apply(BuyCard(card=card))
        assert res.applied
        assert res.observed is not None and res.observed is not m.state
        assert m.state.gold == 50 - card_cost(card)
        assert all(c.x != card.x for c in m.state.shop)
        placed = [b for b in cw_state.iter_occupied(m.state.bench)
                  if b.char_id == card.name]
        assert len(placed) == 1
        assert m.shop_pool.copies[card.name] == copies_before - 1

    def test_buy_rejected_full_bench_consumes_nothing(self) -> None:
        """满栏非合成拒买:simulate 恒返回原态 → applied=False、金不动、
        牌池零消费(ExecResult.applied 的规则性拒绝语义)。"""
        m = FakeMatch(seed=6)
        bench_names = set()
        for name in m.shop_pool.copies:
            if len(bench_names) >= BENCH_CAPACITY:
                break
            bench_names.add(name)
        m.state.bench = [
            cw_state.BenchChar(slot=i + 1, char_id=n, faction='?')
            for i, n in enumerate(sorted(bench_names))
        ]
        cards = _deal_shop(m)
        card = next(c for c in cards if c.name not in bench_names)
        copies_before = m.shop_pool.copies[card.name]
        m.state.gold = 40
        res = m.apply(BuyCard(card=card))
        assert res.applied is False
        assert m.state.gold == 40
        assert len(m.state.shop) == len(cards)
        assert m.shop_pool.copies[card.name] == copies_before

    def test_sell_bench_refund_and_pool_return(self) -> None:
        """卖出:income = 实收回金(1★ = cost,ADR-0111 单一源现算)、
        金入账一致、副本回池(真机制)。"""
        m = FakeMatch(seed=7)
        cards = _deal_shop(m)
        m.state.gold = 30
        buy = m.apply(BuyCard(card=cards[0]))
        assert buy.applied
        name = cards[0].name
        copies_after_buy = m.shop_pool.copies[name]
        idx = next(i for i, b in enumerate(m.state.bench)
                   if b is not None and b.char_id == name)
        gold_before_sell = m.state.gold
        res = m.apply(SellBench(bench_idx=idx))
        assert res.applied
        assert res.income == card_cost(cards[0])
        assert m.state.gold == gold_before_sell + res.income
        assert m.shop_pool.copies[name] == copies_after_buy + 1

    def test_sell_stale_expect_rejected_no_pool_corruption(self) -> None:
        """规则性拒绝锁(落地审 B1 红证对照):陈旧 expect 的卖出 =
        simulate「原状态 + rejected 日志条目」→ applied=False、income=None、
        金不动、**牌池零变化**、角色未离席(修前 applied=True + ret 腐蚀
        池 26→27;破坏本修法即红)。"""
        m = FakeMatch(seed=7)
        cards = _deal_shop(m)
        m.state.gold = 30
        buy = m.apply(BuyCard(card=cards[0]))
        assert buy.applied
        name = cards[0].name
        copies_before_sell = m.shop_pool.copies[name]
        idx = next(i for i, b in enumerate(m.state.bench)
                   if b is not None and b.char_id == name)
        gold_before = m.state.gold
        res = m.apply(SellBench(bench_idx=idx, expect=f'not-{name}'))
        assert res.applied is False
        assert res.income is None
        assert m.state.gold == gold_before
        assert m.shop_pool.copies[name] == copies_before_sell
        sold = m.state.bench[idx]
        assert sold is not None and sold.char_id == name   # 未离席
        # 拒绝条目入档(v2 动作契约冻结 invariant,假游戏侧同守)
        assert any(e.get('result') == 'rejected'
                   for e in m.state.action_log)

    def test_merge_buy_pool_takes_once_per_delisted_card(self) -> None:
        """合成买池账锁(落地审 B2 红证对照):满栏 9/9 + 席上同名 1★ +
        店内 2 张同名 → k=2(merge_buy_k 单一源),simulate 下架 2 张/
        扣 2×cost → 假游戏池恰 take 2 次(27→25 真值形态;修前只 take 1
        次 = 池 27→26 系统性虚高)。期望值全部单一源现算。"""
        m = FakeMatch(seed=7)
        probe = m.shop_pool.draw_shop(3)
        card = probe[0]
        name, cost, faction = card.name, card.cost, card.faction
        others = [n for n in m.shop_pool.copies
                  if n != name and m.shop_pool.copies[n] > 0][:8]
        assert len(others) == 8, '测试前提:池内异名不少于 8'
        # 席上 8 异名 + 1 同名(1★)= 满栏 9/9,own=1
        m.state.bench = [
            cw_state.BenchChar(slot=i + 1, char_id=n, faction='?')
            for i, n in enumerate(others)
        ] + [cw_state.BenchChar(slot=9, char_id=name, faction='?', star=1)]
        # 店内 2 张同名(x=0/1)+ 3 张异名(x=2-4)
        m.state.shop = [
            ShopCard(x=0, name=name, cost=cost, faction=faction),
            ShopCard(x=1, name=name, cost=cost, faction=faction),
        ] + [ShopCard(x=2 + i, name=n, cost=cost, faction='?')
             for i, n in enumerate(others[:3])]
        copies_before = m.shop_pool.copies[name]
        m.state.gold = 50
        res = m.apply(BuyCard(card=m.state.shop[0]))
        assert res.applied
        # simulate 侧:2 张下架 + 2×cost 扣金(全量对账)
        assert len(m.state.shop) == 3
        assert m.state.gold == 50 - 2 * cost
        # 合成兑现:同名 1★ 三份 → 恰一尊 2★,1★ 清零
        merged = [b for b in cw_state.iter_occupied(m.state.bench)
                  if b.char_id == name]
        assert len(merged) == 1 and merged[0].star == 2
        # 假游戏规则外效应:池按 k=2 精确扣减(真值 27→25 形态)
        assert m.shop_pool.copies[name] == copies_before - 2

    def test_refresh_shop_deducts_and_redeals_via_rule_layer(self) -> None:
        """刷新:金 -cost(simulate 契约:只扣金不模拟牌)+ 重抽 = 假游戏
        规则层 _Pool.draw_shop(五槽、牌名全部在池词表内)。"""
        m = FakeMatch(seed=9)
        _deal_shop(m)
        m.state.gold = 20
        m.state.level = 4
        res = m.apply(RefreshShop(cost=2))
        assert res.applied
        assert m.state.gold == 18
        assert len(m.state.shop) == 5
        assert all(c.name in m.shop_pool.copies for c in m.state.shop)
        assert res.verification.get('dealt') == 5


class TestBattleSettlement:
    """战斗结算直调锁(coarse 主路径 + Δ池直调;方案 §2.2/F7 主从口径)。"""

    def test_coarse_win_returns_win_cap(self) -> None:
        """coarse 主路径的胜态交付 = WIN_CAP 封顶值(单一源现算;证明
        battle 节点走 sample_battle_delta 而非 Δ池经验分布)。

        种子固化(测试纪律 12:显式命中种子,非现扫窗):探针记录 =
        扫描窗 [1000,1120) 逐 seed 构 FakeMatch 后首战 battle,唯一命中
        1009(命中率 1/120;命中形态 = rung0 战斗流首抽入胜分支)。
        引擎位移 RNG 消费致失准时,处理 = 重跑探针更新本值并刷新本
        记录,不是机械跟绿。"""
        m = FakeMatch(seed=_COARSE_WIN_SEED)
        assert m.settle_battle('battle').delta == WIN_CAP

class TestFakePorts:
    """两端口假实现行为锁(真值直出 + 快照断别名 + 留痕)。"""

    def test_observer_truthful_snapshot_and_fidelity_bits(self) -> None:
        """观察 = 真值快照(拷贝断别名)+ 保真位恒真(方案 §2.3 契约
        一则:「完美观测」环境参数,判读按 §4-6 申报)。"""
        m = FakeMatch(seed=17)
        m.state.gold = 33
        m.state.hp = 71
        obs = FakeCwObserver(m)
        bundle = obs.observe_prep(_CTX, 'prep_clean')
        st = bundle.state
        assert (st.gold, st.hp) == (33, 71)
        assert st is not m.state
        st.gold = 0   # 快照改动不得污染状态机真值
        assert m.state.gold == 33
        assert st.hp_readable and st.hp_trusted
        assert st.gold_readable and st.board_readable and st.level_readable
        assert bundle.prep is not None and bundle.prep.state is st
        assert bundle.prep.state_gold_trusted is True

    def test_installed_ports_drive_match_end_to_end(self) -> None:
        """经模块槽装配后,观察/执行全链路可用(批 1 harness 的最小形)。"""
        m = FakeMatch(seed=22)
        install_game_ports(FakeCwObserver(m), FakeActionSink(m))
        src = observation_source()
        assert src is not None
        assert src.screen_identity(_CTX) == m.phase == PHASE_PREP
        sink = action_sink()
        assert sink is not None
        cards = _deal_shop(m)
        m.state.gold = 30
        res = sink.execute_action(_CTX, BuyCard(card=cards[0]))
        assert res.applied
        uninstall_game_ports()
        assert observation_source() is None and action_sink() is None


