"""假游戏骨架行为锁(T-120 sim 重设计 批 0)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/方案.md``,
**易失产物**)§2.2 假游戏状态机设计(状态容器/转移唯一入口 apply/
确定性契约)+ §6.2 批 0 验收「同 seed 逐位可复现」;ADR 落点待 T-120
退役批分配,后续批回填编号。

锁的语义(测试纪律 7「锁的存在性」自检):
- **确定性锁** = 重放契约的假游戏半边:同 seed → 全轨迹(画面身份/
  节点日程/金/牌池副本/结算回执)逐位相等。真值来源全部是 kernel/sim
  真码直调,fixture 零平行实现——红 = 真码确定性或分流纪律被破坏。
- **单一源守卫** = ``apply`` 的转移必经 ``cw_state.simulate``、reward/
  supply 结算必经 ``live_delta_for``(方案 §2.2「假游戏不内联任何动作
  转移」)。monkeypatch spy 证明接线(删直调即红),属依赖方向守卫
  (测试纪律 8②),非源码形状锁。
- **行为锁** = 动作/结算/浮层的可观测效果;期望值从单一源推导式现算
  (registry 常量/真码 helper,测试纪律 9),零手抄常数。
"""
from __future__ import annotations

import pytest
from fixtures.cw_fake_game import fake_match as fake_match_mod
from fixtures.cw_fake_game.fake_match import (
    DEFAULT_OPENING_HP,
    FAKE_GAME_ENV_VERSION,
    PHASE_PLANE_TRANSITION,
    PHASE_PREP,
    FakeMatch,
)
from fixtures.cw_fake_game.fake_ports import FakeActionSink, FakeCwObserver

import sr_od.application.currency_war.kernel.cw_state as cw_state
from sr_od.application.currency_war.cw_game_ports import (
    action_sink,
    install_game_ports,
    observation_source,
    uninstall_game_ports,
)
from sr_od.application.currency_war.kernel.cw_coarse_battle import WIN_CAP
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    XP_PER_BUY,
    XP_TO_NEXT_LEVEL,
    BuyCard,
    GameState,
    LevelUp,
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
    """确定性锁(方案 §6.2 批 0 验收:同 seed 逐位可复现)。"""

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

    def test_same_seed_bitwise_replay(self) -> None:
        """同 seed 两次全程驱动 → 轨迹逐位相等(重放契约的假游戏半边)。"""
        t1 = self._drive(20260907)
        t2 = self._drive(20260907)
        assert t1 == t2

    def test_scripted_node_sequence_honored_and_exhausts_to_transition(
            self) -> None:
        """剧本注入优先于采样;日程耗尽 → 画面身份切位面过渡(骨架面,
        P2 继承归批 3)。"""
        seq = ['reward', 'battle', 'boss']
        m = FakeMatch(seed=1, node_sequence=seq)
        assert m.node_sequence == seq
        assert (m.state.node_type, m.state.round_num) == ('reward', 1)
        m.advance_node()
        assert (m.state.node_type, m.state.round_num) == ('battle', 2)
        assert m.phase == PHASE_PREP
        m.advance_node()
        assert m.state.node_type == 'boss'
        m.advance_node()
        assert m.phase == PHASE_PLANE_TRANSITION

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

    def test_env_fingerprint_carries_version_and_pool(self) -> None:
        """环境指纹 = 规则层版本 + Δ池指纹(跨版本对照禁裸串比的载体;
        池指纹值 = 主仓快照在案锚 460e6031e2f4ae06(T-119 提交触发 Δ池
        快照再生,前值 a0722904dea13294 为 ADR-0582 时代历史出处))。"""
        m = FakeMatch(seed=7)
        fp = m.env_fingerprint()
        assert fp['env_version'] == FAKE_GAME_ENV_VERSION
        assert fp['delta_pool'] == '460e6031e2f4ae06'


class TestActionTransitionSingleSource:
    """动作转移单一源守卫 + 行为锁(方案 §2.2 商店动作结算行)。"""

    def test_apply_routes_through_cw_state_simulate(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """接线守卫:apply 必经 cw_state.simulate(spy 记调用并转发真
        函数——把 fake_match 的直调改内联 = 本锁红)。"""
        m = FakeMatch(seed=3)
        calls: list[tuple[GameState, object]] = []
        real = cw_state.simulate

        def spy(state: GameState, action: object) -> GameState:
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

    def test_levelup_click_accumulates_xp_and_crosses_threshold(self) -> None:
        """升级 = 一次点击 +XP_PER_BUY(ADR-0129 真实语义);跨门槛自动
        升级,期望值全部从 XP 常量表现算(测试纪律 9)。
        级别取 5(门槛 20):未跨/跨两态可分(level 3 门槛 4 = XP_PER_BUY,
        任何一击都跨,两态不可分)。"""
        need5 = XP_TO_NEXT_LEVEL[5]
        m = FakeMatch(seed=8)
        m.state.level = 5
        m.state.xp_progress = (0, need5)
        m.state.gold = 40
        cost = 6
        res = m.apply(LevelUp(cost=cost))
        assert res.applied
        assert m.state.gold == 40 - cost
        assert m.state.level == 5
        assert m.state.xp_progress == (XP_PER_BUY, need5)
        # 跨门槛:余量 = 门槛 - 已攒 = XP_PER_BUY,一击恰好填满 → 溢出 0
        m2 = FakeMatch(seed=8)
        m2.state.level = 5
        m2.state.xp_progress = (need5 - XP_PER_BUY, need5)
        m2.state.gold = 40
        res2 = m2.apply(LevelUp(cost=cost))
        assert res2.applied
        assert m2.state.level == 6
        assert m2.state.xp_progress == (0, XP_TO_NEXT_LEVEL[6])

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

    def test_battle_settlement_deterministic_and_applies_hp(self) -> None:
        """同 seed 同节点 → 回执逐位相等;hpΔ 落到 state(下钳 0)。"""
        a = FakeMatch(seed=12)
        b = FakeMatch(seed=12)
        sa = a.settle_battle('battle')
        sb = b.settle_battle('battle')
        assert sa == sb
        assert a.state.hp == sa.hp_after
        assert sa.hp_after == max(0, DEFAULT_OPENING_HP + sa.delta)

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

    def test_reward_settlement_routes_delta_pool(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Δ池直调接线守卫:reward 结算走 live_delta_for 且显式带池
        (snapshot 源,零本地产物依赖);断言不锁池数值——池内容由
        快照指纹守卫(env_fingerprint 锁),此处只锁接线与回执形状。"""
        m = FakeMatch(seed=13)
        calls: list[tuple[str, bool]] = []
        real = fake_match_mod.live_delta_for

        def spy(node_type: str, key: int, rng, **kw):
            calls.append((node_type, kw.get('pool_map') is not None))
            return real(node_type, key, rng, **kw)

        monkeypatch.setattr(fake_match_mod, 'live_delta_for', spy)
        out = m.settle_battle('reward')
        assert calls == [('reward', True)]
        assert isinstance(out.delta, int)
        assert out.hp_after == max(0, DEFAULT_OPENING_HP + out.delta)

    def test_supply_settlement_deterministic(self) -> None:
        m1 = FakeMatch(seed=14)
        m2 = FakeMatch(seed=14)
        assert m1.settle_battle('supply') == m2.settle_battle('supply')


class TestOverlayStack:
    """浮层栈行为锁(方案 §2.2 浮层栈行)。"""

    def test_lifo_and_kind_filter(self) -> None:
        m = FakeMatch(seed=15)
        m.push_overlay('invest', ['甲', '乙'])
        m.push_overlay('supply', [{'char': 'x', 'equip': 'y'}])
        # kind 过滤按栈顶优先,越过不匹配的上层帧
        assert m.top_overlay('invest').payload == ['甲', '乙']
        assert m.top_overlay('supply').payload == [{'char': 'x',
                                                    'equip': 'y'}]
        top = m.pop_overlay()
        assert top is not None and top.kind == 'supply'
        assert m.top_overlay('supply') is None
        assert m.top_overlay().kind == 'invest'

    def test_empty_stack_returns_none_and_empty_options(self) -> None:
        m = FakeMatch(seed=16)
        assert m.pop_overlay() is None
        assert m.top_overlay('invest') is None


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

    def test_shop_cards_snapshot_copies(self) -> None:
        m = FakeMatch(seed=18)
        _deal_shop(m)
        obs = FakeCwObserver(m)
        cards = obs.observe_shop_cards(_CTX)
        assert [c.name for c in cards] == [c.name for c in m.state.shop]
        cards[0].cost = 99
        assert m.state.shop[0].cost != 99   # 快照拷贝语义

    def test_overlay_options_from_stack_top(self) -> None:
        m = FakeMatch(seed=19)
        obs = FakeCwObserver(m)
        assert obs.overlay_options(_CTX, 'invest') == []
        m.push_overlay('invest', ['甲', '乙', '丙'])
        assert obs.overlay_options(_CTX, 'invest') == ['甲', '乙', '丙']
        assert obs.overlay_options(_CTX, 'supply') == []

    def test_observation_log_records_calls_monotonic(self) -> None:
        """契约二则:读屏次数语义保留(留痕 = 语义事件计数,seq 单调)。"""
        m = FakeMatch(seed=20)
        obs = FakeCwObserver(m)
        obs.screen_identity(_CTX)
        obs.observe_prep(_CTX, 'prep_clean')
        obs.observe_prep(_CTX, 'prep_clean')
        assert [e.method for e in m.observation_log] == [
            'screen_identity', 'observe_prep', 'observe_prep']
        seqs = [e.seq for e in m.observation_log]
        assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
        assert all(e.clock <= m.clock for e in m.observation_log)

    def test_sink_executes_action_into_match(self) -> None:
        """执行器端口 = 状态机转移直落(applied/金变化经真值回执)。"""
        m = FakeMatch(seed=21)
        cards = _deal_shop(m)
        m.state.gold = 30
        sink = FakeActionSink(m)
        res = sink.execute_action(_CTX, BuyCard(card=cards[0]))
        assert res.applied
        assert m.state.gold == 30 - card_cost(cards[0])

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


class TestPhaseVocabulary:
    """画面身份词表锚(screen_info screen_name 同名,方案 §2.2)。"""

    def test_core_phases_match_screen_info(self) -> None:
        """词表单一源 = screen_info 画面档:名漂移即红(档案改名须同批
        改词表)。PHASE_LOBBY 在列但骨架推进面暂不消费(大厅档归入口链,
        批 3 接入)。"""
        from pathlib import Path
        # fake_match.py 住 sr-od-test/fixtures/cw_fake_game/ → parents[3] = 仓库根
        repo = Path(fake_match_mod.__file__).resolve()
        info_root = (repo.parents[3] / 'assets' / 'game_data' / 'screen_info')
        expect = {
            'currency_war_battle_prep': fake_match_mod.PHASE_PREP,
            'currency_war_battle_prep_shop_open':
                fake_match_mod.PHASE_PREP_SHOP_OPEN,
            'currency_war_battle': fake_match_mod.PHASE_BATTLE,
            'currency_war_battle_settle': fake_match_mod.PHASE_SETTLE,
            'currency_war_plane_transition':
                fake_match_mod.PHASE_PLANE_TRANSITION,
            'currency_war_lobby': fake_match_mod.PHASE_LOBBY,
        }
        for screen_id, phase_name in expect.items():
            yml = (info_root / f'{screen_id}.yml').read_text(encoding='utf-8')
            assert f'screen_name: {phase_name}' in yml, (
                f'{screen_id} 的 screen_name 与词表 {phase_name!r} 漂移')
