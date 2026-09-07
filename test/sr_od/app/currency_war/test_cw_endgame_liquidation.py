"""域①终局清算臂与仲裁豁免行锁(T-143 落码批;P81;方案 v2 §4)。

锁出处(持久索引;锁纪律第 7 条):
- docs/develop/currency_war/proofs/math_proofs.md **P81** 行(S2′ 终局清算
  弱占优;域①= 终局帧主定理辖域,持金未来效用 ≡0 ⟹ 当帧可兑现消费
  弱支配持金);
- docs/develop/currency_war/decisions/ADR-0594(T-143 落码批;域①豁免行
  三件套 + 双落点 + 卖出腿对价段);
- 找问题-第三跑 N2 实证(`.debug/temp/currency_war/t120_sim_redesign/
  找问题-第三跑.md` §五/§六:20260958/76「闸开≠臂发」,清算臂辖域判据
  必须独立于 arm1 板满谓词)。

覆盖地图:域①单帧锁(清算动作序)/清算循环终止锁(金尽 + 无合法动作)/
步 0 升级续批锁(N2 病灶复演面)/卖出腿禁卖锁(骨架/本 visit 买入禁卖,
victim = 燃料类)/两落点发射率分键锁(落点一 kernel 分键 vs 落点二策略
分键)/红证(退域①豁免 → 带内冻结复现)。

载体声明:本文件所有域①帧经 ``sess.run_plane_count = 1`` 显式声明
(方案 v2 §4 B1 修法路线 (a);sim 假局载体=1 载体声明,生产缺省 3,
未声明载体的既有行为零漂移由既有锁 test_cw_launch_arbitrage 等价扫描
看守)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_launch_arbitrage
from sr_od.application.currency_war.kernel.cw_economy import (
    in_launch_spend_zone,
    saturation_line,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    CloseShop,
    GameState,
    LevelUpShop,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# 测试用注册表实名(与 test_cw_sell_window_launch 同源代表件):
_FUEL = '青雀'          # 线外 1★ 燃料代表(cost=1;穿过全部物理谓词)
_DEPLOY = '希儿'        # 可上板件代表(静态持有档,作店内买件用)
_FILLER2 = '瓦尔特'     # 2★ 填槽代表(star 过滤 = 非燃料,占满 bench 用)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int = 3, star: int = 1, x: int = 100) -> ShopCard:
    return ShopCard(x=x, name=name, cost=cost, star=star)


def _sess(run_planes: int = 1, **state_fields) -> SimpleNamespace:
    """桩 session(策略器字段经 state_of 载体;run_plane_count = 载体
    声明,B1 修法的「本局位面数」输入)。"""
    s = SimpleNamespace()
    st = state_of(s)
    for k, v in state_fields.items():
        setattr(st, k, v)
    s.run_plane_count = run_planes
    return s


def _end_frame(gold: int, *, level: int = 5, plane: int = 1,
               rn: int = 9, cards: list[ShopCard] | None = None,
               deployed: list[BenchChar] | None = None,
               bench: list[BenchChar] | None = None,
               run_planes: int = 1) -> tuple:
    """域①终局帧:位面末 boss 备战帧 ∧ 末位面(载体声明 run_planes)。

    plane_node_table 供 9 槽(nodes_of_plane 真值链,免回退告警);
    hp 真值帧(血闸/血预算链直通,金本位缺省)。"""
    st = GameState(gold=gold, level=level, round_num=rn, hp=8)
    st.level_readable = True
    st.hp_readable = True
    st.hp_trusted = True
    st.plane = plane
    st.node_type = 'boss'
    st.shop = list(cards or [])
    st.bench = list(bench or [])
    st.deployed = list(deployed or [])
    st.shop_refresh_cost = 2
    sess = _sess(run_planes, cw4_counters={}, target_comp=None,
                 plane_node_table=['boss'] * 9)
    return st, sess


def _boss_state(plane: int = 1, rn: int = 9) -> SimpleNamespace:
    """域①谓词的帧态桩(仲裁语境 state 解析消费面)。"""
    return SimpleNamespace(plane=plane, round_num=rn, node_type='boss')


def _decide(st: GameState, sess) -> object:
    return shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))


def _counters(sess) -> dict:
    return state_of(sess).cw4_counters


class TestZoneExemption:
    """落点一:域①带内解除 + 地板降 0(P81 豁免行;kernel 判定单一源)。"""

    def test_inband_endgame_frame_released(self):
        """带内 fail-closed 解除:域①帧 g ≤ g* 且 g > 0 → zone 开
        (P81 = L1' 域①子域已证);分键 launch_arbitrage_endgame_frames
        随释放同源 +1(落点一发射率分键;两面循环体各恰调一次/帧)。"""
        sess = _sess(1, cw4_cap_override=None)
        sess.last_state = _boss_state()
        sess.plane_node_table = ['boss'] * 9
        counters = state_of(sess).cw4_counters = {}
        g_star = saturation_line(5)
        assert g_star > 10   # 前提:取带内金位做判定
        assert in_launch_spend_zone(g_star - 1, sess) is True
        assert counters.get(cw_launch_arbitrage.KEY_ENDGAME_FRAMES) == 1
        assert in_launch_spend_zone(0, sess) is False   # 金尽不出 zone

    def test_inband_endgame_nonfinal_plane_still_closed(self):
        """域③破防守卫:同形态帧在非末位面(生产 3 位面载体的 P1 r9)
        带内仍 fail-closed——息档纪律禁入(P81 辖域三分);载体声明
        缺省 3 位面是本守卫的承重面,禁由 plane_lengths_seen 长度推断
        位面数(生产 P1 帧该序列长度=1)。"""
        sess = _sess(3, cw4_cap_override=None)   # 生产载体:未声明 → 3
        sess.last_state = _boss_state()
        sess.plane_node_table = ['boss'] * 9
        state_of(sess).cw4_counters = {}
        assert in_launch_spend_zone(saturation_line(5) - 1, sess) is False

    def test_gate_floor_zero_on_endgame_frame(self):
        """地板降 0:域①帧花后 ≥0 即放行(P70 边界 1 的域①豁免行);
        非域①帧逐字走既有 g* 地板(零漂移对照)。"""
        card = BuyCard(card=_card(_FUEL, cost=3), reason='test')
        sess = _sess(1)
        sess.last_state = _boss_state()
        sess.plane_node_table = ['boss'] * 9
        # 域①:金 4 花 3 → 1 ≥ 0 放行(既有 g*=50 地板会拒)
        ok, why = cw_launch_arbitrage.launch_arbitration_gate(card, 4, sess)
        assert ok is True and why == ''
        # 对照:同金位非域①帧(载体 3 位面 → P1 r9 = 域③)拒
        sess3 = _sess(3)
        sess3.last_state = _boss_state()
        sess3.plane_node_table = ['boss'] * 9
        ok3, why3 = cw_launch_arbitrage.launch_arbitration_gate(
            card, 4, sess3)
        assert ok3 is False
        assert why3 == cw_launch_arbitrage.GATE_BLOCKED_REASON

    def test_zero_cost_actions_always_pass(self):
        """零成本动作(卖出/部署族)恒放行——域①豁免不改变该既有语义。"""
        sess = _sess(1)
        sess.last_state = _boss_state()
        sess.plane_node_table = ['boss'] * 9
        ok, _ = cw_launch_arbitrage.launch_arbitration_gate(
            SellBench(bench_idx=0), 0, sess)
        assert ok is True


class TestEndgameLiquidationArm:
    """落点二:决策层清算臂(方案 v2 §4 循环;N2 辖域判据)。"""

    def test_single_frame_liquidation_sequence(self):
        """域①单帧锁(方案 §7 单帧锁形态):域①帧 ∧ 金 >0 ∧ 店内有
        可上场件 → 清算动作序列。板有空位帧首动作 = 补位买入
        (费档降序「最强可上场件」;步 2;level=10 使步 0 满级不辖)。"""
        st, sess = _end_frame(30, level=10,
                              cards=[_card(_FUEL, cost=1),
                                     _card(_DEPLOY, cost=5)])
        act = _decide(st, sess)
        assert isinstance(act, BuyCard)
        assert act.card.name == _DEPLOY   # 费档降序最强可上场件
        assert act.reason == 'endgame_liquidation_fill'
        assert _counters(sess).get('endgame_liquidation_frame') == 1
        assert _counters(sess).get('endgame_liquidation_fill') == 1

    def test_step0_upgrade_continuation_independent_of_arm1(self):
        """步 0 升级续批(N2 锁):20260958 形态——lv5 后 cap 松开
        (板 4/5)arm1 失效,余金 ≥ 升级批成本(20 金 = 5 击 × 4)→
        LevelUpShop 照发,auth_basis = endgame_liquidation:step0。
        同帧非末位面载体(域③)不发射——辖域判据 = 域①帧本身,
        不挂 arm1。"""
        deployed = [_bc(_FILLER2, slot=i + 1) for i in range(4)]
        st, sess = _end_frame(48, level=5, deployed=deployed)
        # 前提自证:cap=5、板 4 → arm1(板满)假;bench 空 → 无候补。
        assert st.max_units() == 5 and len(deployed) == 4
        act = _decide(st, sess)
        assert isinstance(act, LevelUpShop)
        assert act.auth_basis == 'endgame_liquidation:step0'
        assert act.cost == 4   # 单击发射(整批 5 击 = 动作内部步骤)
        assert _counters(sess).get('endgame_liquidation_upgrade') == 1
        # 域③对照:同形态、非末位面载体 → 无清算发射(金留给息档)
        st3, sess3 = _end_frame(48, level=5, deployed=deployed,
                                run_planes=3)
        act3 = _decide(st3, sess3)
        assert not isinstance(act3, LevelUpShop)
        assert _counters(sess3).get('endgame_liquidation_upgrade') is None

    def test_liquidation_loop_terminates_at_dust(self):
        """清算循环终止锁(方案 §4 步 5):空店空目标帧持续寻件刷新,
        金单调递减,金 < 刷价 → 终止动作 CloseShop(金尽)。循环有限
        终止由金单调递减承载(步 0-4 净耗金 ≥0)。"""
        st, sess = _end_frame(7, level=10, cards=[])
        actions: list = []
        for _ in range(16):
            act = _decide(st, sess)
            actions.append(act)
            if isinstance(act, CloseShop):
                break
            if isinstance(act, RefreshShop):
                st.gold -= act.cost
            else:
                break
        assert isinstance(actions[-1], CloseShop)
        assert st.gold < 2    # 金尽口径(金 < 刷价)
        assert sum(1 for a in actions if isinstance(a, RefreshShop)) >= 3
        assert _counters(sess).get('endgame_liquidation_close') == 1

    def test_no_legal_action_closes_without_refresh(self):
        """无合法消费动作终止:金 < 刷价且无目标 → 恰 CloseShop
        (不刷不买)。"""
        st, sess = _end_frame(1, level=10, cards=[])
        act = _decide(st, sess)
        assert isinstance(act, CloseShop)

    def _full_bench_with_fuel(self) -> list[BenchChar]:
        """满 bench 夹具:槽 1 = 1★ 燃料(唯一 fuel 合格件),其余 =
        2★ 填槽(star 过滤非燃料;同名 bench 内副本不阻假想上板)。"""
        slots = [_bc(_FUEL, slot=1)]
        slots += [_bc(_FILLER2, star=2, slot=i + 2)
                  for i in range(BENCH_CAPACITY - 1)]
        return slots

    def test_sell_leg_frees_slot_for_fill_target(self):
        """卖出腿(腾位):bench 满 ∧ 板有空位 ∧ 店有可上板件 →
        卖燃料垫件腾位(SellBench reason = endgame_liquidation_clear,
        枚举闭集登记值);victim = 燃料类单一源首件。"""
        st, sess = _end_frame(30, level=10,
                              cards=[_card(_DEPLOY, cost=5)],
                              bench=self._full_bench_with_fuel())
        act = _decide(st, sess)
        assert isinstance(act, SellBench)
        assert act.reason == 'endgame_liquidation_clear'
        assert act.expect == _FUEL
        assert act.bench_idx == 0
        assert _counters(sess).get('endgame_liquidation_sell') == 1

    def test_sell_leg_never_sells_protected_pieces(self):
        """禁卖锁(方案 §4 B3 边界):bench 满但 1★ 件全为静态持有
        (core/transition 档骨架件)→ 燃料 victim 空,腾位腿不发射
        (诚实空转),禁手搓绕统一装配 A。"""
        bench = [_bc('希儿', slot=1), _bc('丹恒·饮月', slot=2),
                 _bc('三月七', slot=3)]
        bench += [_bc(_FILLER2, star=2, slot=i + 4) for i in range(6)]
        st, sess = _end_frame(30, level=10,
                              cards=[_card(_DEPLOY, cost=5)],
                              bench=bench)
        act = _decide(st, sess)
        assert not isinstance(act, SellBench)   # 保护件全满 = 无合法腾位

    def test_sell_leg_skips_visit_bought_pieces(self):
        """P78-1 同 visit 禁卖(funding 兜底减法①同款消费位减法):
        本 visit 买入件不入燃料 victim 集——清算机制不得自造同 visit
        换手。"""
        st, sess = _end_frame(30, level=10,
                              cards=[_card(_DEPLOY, cost=5)],
                              bench=self._full_bench_with_fuel())
        state_of(sess).cw4_visit_bought_names = [_FUEL]
        act = _decide(st, sess)
        assert not isinstance(act, SellBench)

    def test_merge_buy_target(self):
        """步 3 单帧合成:店内+持有同名同星合计 ≥3 ∧ 合成产物能上板
        (合成销后板面假想)→ 买齐(reason = endgame_liquidation_merge;
        level=10 使步 0 满级不辖)。"""
        bench = [_bc(_FUEL, slot=1), _bc(_FUEL, slot=2)]
        st, sess = _end_frame(30, level=10, cards=[_card(_FUEL, cost=1)],
                              bench=bench)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard)
        assert act.reason == 'endgame_liquidation_merge'
        assert _counters(sess).get('endgame_liquidation_merge_buy') == 1

    def test_red_without_exemption_freezes_inband(self, monkeypatch):
        """红证(退域①豁免 → 冻结复现):谓词退 False 后,①带内帧
        zone 重新关死(in_launch_spend_zone 恒 False)、②清算臂沉默
        (既有栈语义接管,无 endgame_* 分键)——本批病灶面整体回退。"""
        st, sess = _end_frame(48, level=5,
                              deployed=[_bc(_FILLER2, slot=i + 1)
                                        for i in range(4)])
        monkeypatch.setattr(cw_launch_arbitrage,
                            'endgame_liquidation_frame',
                            lambda state, session: False)
        # ① zone 冻结:带内金位(48 < g*)不再出 True
        sess_zone = _sess(1, cw4_cap_override=None)
        sess_zone.last_state = st
        sess_zone.plane_node_table = ['boss'] * 9
        state_of(sess_zone).cw4_counters = {}
        assert in_launch_spend_zone(48, sess_zone) is False
        # ② 决策面冻结:无 endgame_* 计数(帧计数也不落)
        act = _decide(st, sess)
        assert not isinstance(act, (BuyCard, LevelUpShop, RefreshShop,
                                    SellBench))
        got = _counters(sess)
        assert not [k for k in got if k.startswith('endgame_liquidation')]

    def test_non_endgame_frame_zero_drift(self):
        """非域①帧零漂移:既有选择序语义原样(3 位面载体的 P1 r9 boss
        帧 = 域③)——本批不改既有栈行为(断言 = 无任何 endgame_* 分键
        落账,且不发清算族动作)。"""
        st, sess = _end_frame(48, level=5, run_planes=3,
                              deployed=[_bc(_FILLER2, slot=i + 1)
                                        for i in range(4)])
        act = _decide(st, sess)
        got = _counters(sess)
        assert not [k for k in got if k.startswith('endgame_liquidation')]
        assert not isinstance(act, (BuyCard, RefreshShop, SellBench))

    def test_two_landing_keys_counted_separately(self):
        """两落点发射率分键锁(A/B 判据①分键面):落点一 =
        launch_arbitrage_endgame_frames(kernel zone 释放支写入),
        落点二 = endgame_liquidation_frame(清算臂决策位写入)——
        两键并存、互不混计。"""
        sess = _sess(1, cw4_cap_override=None)
        sess.last_state = _boss_state()
        sess.plane_node_table = ['boss'] * 9
        counters = state_of(sess).cw4_counters = {}
        in_launch_spend_zone(saturation_line(5) - 1, sess)
        st, sess2 = _end_frame(30, level=10,
                               cards=[_card(_DEPLOY, cost=5)])
        _decide(st, sess2)
        c2 = _counters(sess2)
        assert counters.get(cw_launch_arbitrage.KEY_ENDGAME_FRAMES) == 1
        assert c2.get('endgame_liquidation_frame') == 1
        assert cw_launch_arbitrage.KEY_ENDGAME_FRAMES \
            not in c2   # 落点一写入不经清算臂载体


class TestDiseaseReplay20260958:
    """病灶复演(三跑 N2;20260958 R9 形态):lv5 后 48 金在域①帧
    被清算循环持续消费直至金尽——「闸开≠臂发」病灶的修复面。"""

    def test_lv5_dead_arm_gold_gets_spent(self):
        deployed = [_bc(_FILLER2, slot=i + 1) for i in range(4)]
        st, sess = _end_frame(48, level=5, deployed=deployed, cards=[])
        kinds: list[str] = []
        act = None
        for _ in range(64):
            act = _decide(st, sess)
            if isinstance(act, CloseShop):
                break
            if isinstance(act, LevelUpShop):
                kinds.append('up')
                st.gold -= act.cost      # 单击 4 金投影推进
                if st.level < 6:
                    st.level += 1        # 批完成后重判(20260958 R9 序)
            elif isinstance(act, RefreshShop):
                kinds.append('refresh')
                st.gold -= act.cost
            else:
                kinds.append(type(act).__name__)
                break
        assert 'up' in kinds          # 续批真的发了(N2 病灶修复面)
        assert isinstance(act, CloseShop)
        assert st.gold < 2            # 48 金清算至金尽
        c = _counters(sess)
        assert c.get('endgame_liquidation_upgrade', 0) >= 1
        assert c.get('endgame_liquidation_close') == 1
