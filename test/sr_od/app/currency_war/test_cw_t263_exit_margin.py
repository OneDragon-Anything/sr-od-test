"""T-263 P1 出口生存余量专项 · P90/P91/P92 落码锁。

锁依据(锁的存在性纪律:新锁必引设计出处):
- 命题正本 = math_proofs.md P90/P91/P92/P94 行(T-175 设计批,轮三对抗
  审修订版);命题文档 = .debug/temp/currency_war/T-175-设计批-命题与
  因果链.md §2;设计正本 = attacks/t175_exit_margin/设计方案.md §4;
  实施设计 = 同目录 T-263-实施设计.md;ADR-0635。
- P92 = p40-refresh-ev §② R0-1 席满维(「bench 满到没过渡牌可买 →
  刷=纯烧金」)的在册语义落地,注册口径「在册结构的严格化非新门」。
- P91 多目标排序键**禁设**(轮三中 1 调和注):本文件不含任何按
  E[refreshes] 对目标排序的断言;同轴键只分带内/带外二元(P91(a)
  本体,对非目标压库件)。
- P94 fail-closed:豁免拒绝键显影,grant 键结构性恒 0(无代码路径),
  本文件断言 refuse 计数而非 grant。

与 test_cw_refresh_ledger 的正交性:该锁钉「必花域 yield 发射」语义
(p1r8 档案帧,bench 空 ⇒ dominance 通道可达 ⇒ P92 门放行);本文件
钉「全通道空帧拦刷」与其判据真值表,两锁互补不重叠。

fixture 说明:角色名/费用/名单全部注册表现查(CHARACTERS/pair_target
_comp/line_identity_tier),禁手抄值;两配方对
(('仙舟','持续伤害')/('列车同行','击破'))的成员交集为空域由
成本1角色(停云/万敌)分属两侧承载,注册表变动时本文件随判据语义
同步,不做数值硬编码。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    RefreshShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.refresh import (
    all_channel_buy_exists,
    qualified_member_costs,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    advances_four_system,
    front_window_frame,
    zero_form_frame,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_session as _session,
)

#: P1 众数节点表(单一源词表语义;production 为中文词,模拟为英文词,
#: node_loss_kind 混词表归一——两词形各测一支)
_TABLE_P1_CN: list[str] = [
    '奖励', '奖励', '普通战斗', '普通战斗', '补给',
    '普通战斗', '遭遇', '奖励', 'boss',
]
_TABLE_P1_EN: list[str] = [
    'reward', 'reward', 'battle', 'battle', 'supply',
    'battle', 'encounter', 'reward', 'boss',
]


def _table_session(comp, table: list[str] | None, anchor: int | None = 1):
    """带节点表注记的会话(front_window_frame 查表面)。"""
    s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
    s.plane_node_table = list(table) if table is not None else None
    s.plane_node_table_plane = anchor
    return s


def _front_state(gold: int = 13, node: str = 'reward',
                 round_num: int = 2) -> GameState:
    """前窗帧(round 2 ≤ 首战槽 3;reward 型触发 ②(b) 压库臂)。"""
    st = GameState(gold=gold, level=3, plane=1, round_num=round_num,
                   node_type=node, hp=100)
    st.shop = []
    st.bench = []
    st.deployed = []
    return st


# ===== P90:前窗/零成型谓词真值表 =====

class TestFrontWindowPredicates:

    def test_front_window_rounds_and_vocab(self):
        """前窗 = 首战槽前窗(含首战备战帧):中文表/英文表同判——
        r1-r3 真,r4 假;战斗性判定 = 本地零战斗词集中英并集
        (predicates._FRONT_NONCOMBAT_NODES;非 node_loss_kind 直消费——
        其词集无中文生产词『奖励』会误判战斗,放弃直消费 = 实施设计
        落法偏差,落地审 H3 确认为正确,偏差补记见 ADR-0635)。"""
        comp = _pair_comp_travel()
        for table in (_TABLE_P1_CN, _TABLE_P1_EN):
            s = _table_session(comp, table, 1)
            st = _front_state()
            for rn, want in ((1, True), (2, True), (3, True), (4, False)):
                st.round_num = rn
                assert front_window_frame(st, s) is want, (table, rn)

    def test_front_window_fail_closed_on_table_missing(self):
        """表缺/锚不符/位面外帧 fail-closed False(前窗行为不发生 =
        现行为;调用方以 front_window_table_ready 分键显影)。"""
        comp = _pair_comp_travel()
        st = _front_state()
        s = _table_session(comp, None, None)
        assert front_window_frame(st, s) is False
        s = _table_session(comp, _TABLE_P1_CN, 2)   # 锚=P2(表非本位面)
        assert front_window_frame(st, s) is False
        st2 = _front_state()
        st2.plane = 2
        s = _table_session(comp, _TABLE_P1_CN, 1)
        assert front_window_frame(st2, s) is False

    def test_zero_form_truth_table(self):
        """零成型 = per-体系 board_factions[s] < FACTIONS tiers[0] 全真
        ∧ 希儿系复合未达成(P94 谓词原文;engines_count 合计标量禁用)。
        仙舟成员名注册表现查(cost1 仙舟名单)。"""
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        xz = [n for n, c in CHARACTERS.items()
              if '仙舟' in ({*c.factions} | {*c.flows}) and c.cost == 1]
        two = [_bc(xz[0], star=1, slot=1), _bc(xz[1], star=1, slot=2)]
        assert zero_form_frame(two) is True      # 仙舟 2 < tiers[0]=3
        three = two + [_bc(xz[2], star=1, slot=3)]
        assert zero_form_frame(three) is False   # 仙舟 3 → 1 档
        # 希儿系复合(希儿在场 ∧ 放大器≥2)→ 非零成型
        amps = [n for n, c in CHARACTERS.items()
                if {'量子同频', '贝洛伯格'} & ({*c.factions} | {*c.flows})
                and n != '希儿']
        seele = [_bc('希儿', star=1, slot=1),
                 _bc(amps[0], star=1, slot=2), _bc(amps[1], star=1, slot=3)]
        assert zero_form_frame(seele) is False

    def test_advances_four_system(self):
        """推进件 = 三羁绊键命中 ∨ 希儿系贡献件(单一源判定)。"""
        assert advances_four_system('停云') is True    # 仙舟
        assert advances_four_system('希儿') is True    # 希儿本人
        assert advances_four_system('万敌') is False   # 四体系外


def _pair_comp_travel():
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )
    return pair_target_comp(('列车同行', '击破'))


def _pair_comp_xz_dot():
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )
    return pair_target_comp(('仙舟', '持续伤害'))


# ===== P91:合格集费带单一源 + M6 同轴 =====

class TestQualifiedBand:

    def test_qualified_member_costs_filters(self):
        """费带 = 非 2★ ∧ 该级 refresh_prob>0 成员 cost(lv5:5 费景元
        不可追剔出;2★ 成型先序剔出;升序返回)。卡芙卡 = 2 费
        (注册表现查)。"""
        bench = [_bc('停云', star=2, slot=1)]
        costs = qualified_member_costs(
            ('停云', '景元', '卡芙卡'), bench, [], 5)
        assert costs == [2]   # 停云 2★ 出域;景元 lv5 不可追;卡芙卡 2 费

    def test_r2_reserve_uses_same_source(self):
        """重构零漂移:r2_card_reserve(带内 min)与费带同源
        (test_cw_interest_floor 语义锁的判据面锚)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.refresh import (
            r2_card_reserve,
        )
        bench = [_bc('停云', star=2, slot=1)]
        st = GameState(gold=10, level=5, plane=1, round_num=2, hp=100)
        assert r2_card_reserve(('停云', '景元', '卡芙卡'), bench, [],
                               st) == 2


class TestM6SameAxis:

    def _frame(self, shop_cards: list, formed: bool):
        """M6 同轴帧:gold=51(溢余 1 金)、bench 含 1★ 2 费燃料件
        (liquid_refund=2 ⇒ s_reserve=48,3 费件可过而 dominance 结算线
        拒 2/3 费——M6 为唯一活买入臂)。lv4:可刷档 = 1-3 费
        (REFRESH_PROB[4]),4/5 费成员不可追。formed=False:未成型
        chaseable = 卡芙卡(2 费)⇒ 带 = {2};formed=True:10 名可刷
        成员全 2★ ⇒ 带空(对照臂;席余 = bench_free ≥ 2 保 M6 开火)。"""
        comp = _pair_comp_xz_dot()
        s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
        st = GameState(gold=51, level=4, plane=1, round_num=2,
                       node_type='reward', hp=100)
        members = ['丹恒·饮月', '停云', '卡芙卡', '彦卿', '忘归人', '景元',
                   '桑博', '椒丘', '海瑟音', '爻光', '符玄', '艾丝妲',
                   '藿藿', '青雀', '黑天鹅']
        chaseable = [m for m in members
                     if CHARACTERS[m].cost <= 3]   # lv4 不可追:4/5 费
        unformed = set() if formed else {'卡芙卡'}
        # 燃料件 = 2 费 1★ 线外 unrelated 层级件(退款 2;unrelated 过滤
        # 同时排除 ④ 转线包静态持有集成员——其入 P56 投影排除集,
        # liquid_refund 不计,燃料前置失真)
        from sr_od.application.currency_war.kernel.cw_card_identity import (
            TIER_UNRELATED,
            line_identity_tier,
        )
        fuel = [n for n, c in CHARACTERS.items() if c.cost == 2
                and n not in members
                and not getattr(c, 'bench_effect', '')
                and line_identity_tier(n) == TIER_UNRELATED][0]
        bench = [_bc(fuel, star=1, slot=1)]
        deployed = []
        for m in chaseable:
            if m in unformed:
                continue
            piece = _bc(m, star=2, slot=1)
            if len(deployed) < 4:
                deployed.append(piece)
            else:
                bench.append(piece)
        st.bench = bench
        st.deployed = deployed
        st.shop = list(shop_cards)
        return st, s

    def test_same_axis_card_bought_over_shop_order(self):
        """P91(a) 压库同轴:带 {2} 非空时,带内 2 费件后位仍先于带外
        3 费件被选(稳定排序,带内先于带外);分键 same_axis_hit。"""
        st, s = self._frame([_card('姬子', cost=3, star=1, x=100),
                             _card('砂金', cost=2, star=1, x=200)], False)
        acts = _decide(st, s)
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert buys and buys[0].card.name == '砂金', acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p91_active_band_frame', 0) >= 1
        assert cnt.get('p91_m6_same_axis_hit', 0) >= 1
        assert cnt.get('p91_m6_off_axis_hit', 0) == 0

    def test_off_axis_fallback_keyed(self):
        """带非空而无带内候选帧:M6 照买唯一候选,落 off_axis 对键
        (零静默:两键覆盖全部 M6 买入)。"""
        st, s = self._frame([_card('姬子', cost=3, star=1, x=100)], False)
        acts = _decide(st, s)
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert buys and buys[0].card.name == '姬子', acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p91_m6_off_axis_hit', 0) >= 1
        assert cnt.get('p91_m6_same_axis_hit', 0) == 0

    def test_empty_band_zero_drift(self):
        """带空帧(全员成型)无同轴语义:店面序取首候选,零漂移。"""
        st, s = self._frame([_card('姬子', cost=3, star=1, x=100),
                             _card('砂金', cost=2, star=1, x=200)], True)
        acts = _decide(st, s)
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert buys and buys[0].card.name == '姬子', acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p91_active_band_frame', 0) == 0
        assert cnt.get('p91_m6_same_axis_hit', 0) == 0


# ===== P92:全通道可实现买入集判定尺 =====

class TestAllChannelPredicate:
    """四通道帧级可达真值表(P92 判定尺;『任何店产都不会触发买入』
    语义——可达性按可刷出×可负担×席位三轴,不看当前店面内容)。"""

    def test_dominance_channel(self):
        # 溢余带 + 席空 + 结算线内 ⇒ dominance 可达(1★ 线外件恒在池)
        assert all_channel_buy_exists(
            gold=53, g_star=50, cap_resolved=5, bench_free=8,
            seat_recoverable=False, missing_costs=[], stockpile_costs=[],
            merge_pair_costs=[], level=5, ev_face_open=False,
            window_nonempty=False) is True
        # 席满 ⇒ dominance 死(bench_free=0 且不可腾)
        assert all_channel_buy_exists(
            gold=53, g_star=50, cap_resolved=5, bench_free=0,
            seat_recoverable=False, missing_costs=[], stockpile_costs=[],
            merge_pair_costs=[], level=5, ev_face_open=False,
            window_nonempty=False) is False

    def test_m2_channel_drawability_and_seat(self):
        # 缺员可刷出可负担 + 席 ⇒ 可达
        assert all_channel_buy_exists(
            gold=10, g_star=50, cap_resolved=5, bench_free=1,
            seat_recoverable=False, missing_costs=[1], stockpile_costs=[],
            merge_pair_costs=[], level=5, ev_face_open=False,
            window_nonempty=False) is True
        # 成员该级不可刷出(lv3 无 5 费面)⇒ 通道死——「任何店产」语义
        assert all_channel_buy_exists(
            gold=10, g_star=50, cap_resolved=5, bench_free=1,
            seat_recoverable=False, missing_costs=[5], stockpile_costs=[],
            merge_pair_costs=[], level=3, ev_face_open=False,
            window_nonempty=False) is False
        # 席满但可腾(seat_recoverable=liquid_refund>0 代理)⇒ 可达
        assert all_channel_buy_exists(
            gold=10, g_star=50, cap_resolved=5, bench_free=0,
            seat_recoverable=True, missing_costs=[1], stockpile_costs=[],
            merge_pair_costs=[], level=5, ev_face_open=False,
            window_nonempty=False) is True

    def test_merge_pair_ignores_seats(self):
        """合成完备购满栏不阻断(merge §2.5;第三张可刷出且买得起)。"""
        assert all_channel_buy_exists(
            gold=10, g_star=50, cap_resolved=5, bench_free=0,
            seat_recoverable=False, missing_costs=[], stockpile_costs=[],
            merge_pair_costs=[2], level=5, ev_face_open=False,
            window_nonempty=False) is True

    def test_ev_channel_fail_closed(self):
        """EV 通道如实建模现决策机器:U_X None(fail-closed)⇒ 恒死;
        开放 + 窗口 + 席 ⇒ 可达。(gold 取息线下方使 dominance 通道
        死亡,隔离出 EV 通道单变量。)"""
        base = {'gold': 30, 'g_star': 50, 'cap_resolved': 5, 'bench_free': 1,
                'seat_recoverable': False, 'missing_costs': [],
                'stockpile_costs': [], 'merge_pair_costs': [], 'level': 5}
        assert all_channel_buy_exists(ev_face_open=False,
                                      window_nonempty=True,
                                      **base) is False
        assert all_channel_buy_exists(ev_face_open=True,
                                      window_nonempty=True,
                                      **base) is True

    def test_all_dead_is_false(self):
        assert all_channel_buy_exists(
            gold=20, g_star=50, cap_resolved=5, bench_free=0,
            seat_recoverable=False, missing_costs=[], stockpile_costs=[],
            merge_pair_costs=[], level=5, ev_face_open=False,
            window_nonempty=False) is False


# ===== P92:R1 位集成(拦刷帧 + 放行帧)=====

class TestP92GateIntegration:

    def _blocked_frame(self, gold: int = 100):
        """全通道空帧构造:chaseable 成员(lv5 费 ≤3,共 10 名)中除
        停云(j=1,无配对)外全部 2★ 成型 ⇒ E 非空且账可过;bench 以
        线外 2★ 件填满(2★ 非燃料、非配对、零重叠)⇒ dominance/
        M2/EV/合成完备购全死;reward 型 defer M3,gold=100 过 account/
        r2 门直达 P92 位。"""
        comp = _pair_comp_xz_dot()
        s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
        st = GameState(gold=gold, level=5, plane=1, round_num=2,
                       node_type='reward', hp=100)
        members = ['丹恒·饮月', '停云', '卡芙卡', '彦卿', '忘归人', '景元',
                   '桑博', '椒丘', '海瑟音', '爻光', '符玄', '艾丝妲',
                   '藿藿', '青雀', '黑天鹅']
        formed = [m for m in members
                  if m != '停云' and CHARACTERS[m].cost <= 3]
        assert len(formed) == 9
        fillers = [n for n, c in CHARACTERS.items() if c.cost == 2
                   and n not in members
                   and not getattr(c, 'bench_effect', '')]
        st.deployed = [_bc('停云', star=1, slot=1)]
        st.deployed += [_bc(m, star=2, slot=i + 1)
                        for i, m in enumerate(formed[:4])]
        st.bench = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(formed[4:])]
        st.bench += [_bc(n, star=2, slot=1)
                     for n in fillers[:9 - len(st.bench)]]
        assert len(st.bench) == 9
        st.shop = []
        return st, s

    def test_all_channel_empty_frame_refresh_blocked(self):
        """全通道空帧:刷新被拦(P92 净差 = −(c_eff+L) < 0 严格),
        分键 p92_no_buy_refresh_blocked;必花域内加计域内 liveness 键;
        无 RefreshShop/买牌发射(驱动器以 CloseShop 收尾,不入序列)。"""
        st, s = self._blocked_frame()
        acts = _decide(st, s)
        assert not [a for a in acts if isinstance(a, RefreshShop)], acts
        assert not [a for a in acts if isinstance(a, BuyCard)], acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p92_no_buy_refresh_blocked', 0) >= 1
        assert cnt.get('must_spend_r1_no_buy_blocked', 0) >= 1

    def test_frame_with_seat_recoverable_refresh_passes(self):
        """放行对照:纯函数面 seat_recoverable=True(腾席代理)翻转
        判定尺——通道判定对代理输入敏感(集成面 dominance 可达放行由
        test_cw_refresh_ledger p1r8 档案帧承载,互补不重叠)。"""
        base = {'g_star': 50, 'cap_resolved': 5, 'bench_free': 0,
                'missing_costs': [], 'stockpile_costs': [1],
                'merge_pair_costs': [], 'level': 5, 'ev_face_open': False,
                'window_nonempty': False}
        assert all_channel_buy_exists(gold=100, seat_recoverable=False,
                                      **base) is False
        assert all_channel_buy_exists(gold=100, seat_recoverable=True,
                                      **base) is True


# ===== P90/P94:零成型帧排序层 + 前窗买入分键(②(b) 臂集成)=====

class TestZeroStackSortLayer:

    def _armed_frame(self, session_ready: bool = True):
        """前窗∧零成型帧:r2 奖励帧 gold=13(带内余 3 ≥ 1 费地板),
        店面 [万敌(非推进件), 停云(推进件)] 皆 1 费零重叠 unrelated
        —— ②(b) prio2 燃料类两候选,排序层前移后取停云。"""
        comp = _pair_comp_travel()
        s = _table_session(comp, _TABLE_P1_CN if session_ready else None,
                           1 if session_ready else None)
        st = _front_state(gold=13)
        st.shop = [_card('万敌', cost=1, star=1, x=100),
                   _card('停云', cost=1, star=1, x=200)]
        return st, s

    def test_sort_layer_buys_advancing_piece(self):
        """零成型帧排序层:推进件前移命中(②(b) 燃料类同门序,仅改
        取件序);P94 豁免拒绝分键显影(fail-closed,grant 无路径)。"""
        st, s = self._armed_frame(True)
        acts = _decide(st, s)
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert buys and buys[0].card.name == '停云', acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p90_zerostack_frame_armed', 0) >= 1
        assert cnt.get('p90_zerostack_advancing_buy', 0) >= 1
        assert cnt.get('p94_exemption_refuse', 0) >= 1
        # 四分键零静默:每个 armed 帧恰落「豁免拒绝 ∨ 无可激活件」一支
        assert (cnt.get('p94_exemption_refuse', 0)
                + cnt.get('p94_no_activatable', 0)
                >= cnt.get('p90_zerostack_frame_armed', 0))
        # 前窗买入分键(P90①):1 费档内买入,零跨档
        assert cnt.get('p90_front_window_buy', 0) >= 1
        assert cnt.get('p90_front_buy_cross_tier', 0) == 0
        assert cnt.get('p90_front_buy_over_bound', 0) == 0
        assert cnt.get('p90_front_buy_cost3p', 0) == 0

    def test_table_missing_fail_closed_zero_drift(self):
        """表缺:前窗行为不发生(排序层不武装)⇒ 店面序取首候选;
        p90_front_table_missing 分键显影(零静默)。"""
        st, s = self._armed_frame(False)
        acts = _decide(st, s)
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert buys and buys[0].card.name == '万敌', acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p90_front_table_missing', 0) >= 1
        assert cnt.get('p90_zerostack_frame_armed', 0) == 0
        assert cnt.get('p90_zerostack_advancing_buy', 0) == 0
        assert cnt.get('p94_exemption_refuse', 0) == 0
