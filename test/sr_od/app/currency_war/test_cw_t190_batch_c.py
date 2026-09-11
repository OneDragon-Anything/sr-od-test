"""T-190 批 C 检查项锁面(C-A1..A4;sim/checks/t190_c.py)。

锁面组织(与检查器四项一一对应):
- C-A1 归因分类账:占席桶闭集正控/负控(保护形态 → no_fuel_honest;
  裸燃料 + no_fuel 申报 → honest_stall_dispute 红;裸燃料无申报 →
  chain_act;2★ 非燃料),零未归因锚(覆盖恒等);
- C-A2 T-16 覆盖:计划点定位(同行优先)、覆盖形态闭集、gap 三分
  (plan_active 红 / plan_idle 弱 / board_open 弱)、verdict 两态;
- C-A3 豁免开火:D 轮豁免买入正控、域泄漏红(P1 开火)、hub 哨兵红、
  空面申报两态;
- C-A4 漏斗配平:闭集外幽灵键红、fate 三终态配平、闭集全键在表、
  收缩对账(sold 认账)。

**守卫移除验证(实施纪律:临时去掉被检守卫重跑小批,违规必须涌现;
全量基线 100% 命中 = 伪检查)**,引擎级三发(种子锚定,快照池与在册
批复用同一池语义):
- M-C1:拔 ``mandate.fuel_sell_candidates``(腾席支 victim 生产面,
  恒返空 = 诚实停摆被伪造)→ 真实存在裸燃料占席的 core 拒帧被误报
  no_fuel → C-A1 ``honest_stall_dispute`` 必须涌现(violations > 0);
- M-C3a:拔收窄**辖域纪律**(``shop.swap_transition_narrow_frame``
  恒 True = 域谓词失守)→ 开火落 P1 → C-A3 域泄漏红必须涌现;
- M-C3b(正控,不拔任何守卫):真实小批 D 轮豁免买入 >0 = 解封收益
  可见、C-A3 绿——与 M-C1/M-C3a 的红形成「先红后绿」对子。

数据面近似与红语义边界见 t190_c.py 模块 docstring;P89 定谳一致性
边界(四项不读不判 0.75 线)同源。
"""

from __future__ import annotations

from sr_od.application.currency_war.sim.checks.t190_c import (
    LAUNCH_CAUSE_BY_ARM,
    check_t190_c1_bench_clog_attribution,
    check_t190_c2_new_buy_swap_coverage,
    check_t190_c3_exemption_fire,
    check_t190_c4_funnel_reconcile,
)

# =====================================================================
# 合成账本夹具(生产行形状最小子集;字段同 sim decisions.jsonl)
# =====================================================================

_COMP = '希儿量子'  # 任一在册 comp 名;夹具用 core_chars 做拒因判定


def _row(plane: int = 2, round_num: int = 1, *, bench=None, deployed=None,
         cap: int = 9, actions=None, waves=None, shop_rejects=None,
         counters=None, m1p=None, target_comp: str = _COMP) -> dict:
    st = {'bench': bench or [], 'deployed': deployed or [], 'cap': cap}
    row = {
        'plane': plane, 'round_num': round_num, 'target_comp': target_comp,
        'state': st, 'actions': actions or [],
        'sim': {'shop_waves': waves or []},
        'shop_rejects': shop_rejects or {},
        'obs': {'cw4_counters': counters or {}},
    }
    if m1p is not None:
        row['m1p'] = m1p
    return row


def _piece(name: str, star: int = 1, equips: list | None = None) -> dict:
    return {'char_id': name, 'star': star, 'equips': equips or []}


def _wave(rejects: dict[str, str]) -> dict:
    return {'event': 'offer', 'cards': [], 'rejects': rejects}


def _buy(name: str, reason: str) -> dict:
    return {'__type__': 'BuyCard', 'card': {'name': name}, 'reason': reason}


# =====================================================================
# C-A1 归因分类账
# =====================================================================

class TestC1BenchClogAttribution:

    def _two_reject_rows(self, extra_bench_rows: list[dict] | None = None):
        """两局:局 0 = 三形态行(诚实停摆/链行权/矛盾候选),局 1 = 2★ 非燃料。

        拒因名 = 缇宝(希儿量子 core_chars 在册成员;拒因判定要求
        名 ∈ comp.core_chars)。占席分类:希儿/花火 = 线名单;艾丝妲/
        椒丘 = drop 档不入 ④放行集(TRANSITION_PACK 档 ∈ {carry,
        partial} 才算)→ 1★ 裸燃料形态。
        """
        g0 = [
            _row(round_num=1,
                 bench=[_piece('希儿'), _piece('花火')],
                 waves=[_wave({'缇宝': 'missing_bench_full'})],
                 counters={'core_locked_no_fuel': 1}),
            _row(round_num=2,
                 bench=[_piece('艾丝妲'), _piece('椒丘')],
                 waves=[_wave({'缇宝': 'missing_bench_full'})],
                 counters={}),  # 零 no_fuel 申报 + 裸燃料 = chain_act
            _row(round_num=3,
                 bench=[_piece('艾丝妲')],
                 waves=[_wave({'缇宝': 'missing_bench_full'})],
                 counters={'core_unlocked_no_fuel': 1}),  # 矛盾候选红
        ]
        g1 = [
            _row(round_num=1,
                 bench=[_piece('艾丝妲', star=2)],
                 waves=[_wave({'缇宝': 'missing_bench_full'})],
                 counters={'core_locked_no_fuel': 1}),  # 2★ 非燃料=诚实停摆
        ]
        return [g0, g1]

    def test_shapes_and_zero_unattributed(self):
        rep = check_t190_c1_bench_clog_attribution(
            self._two_reject_rows())
        # 零未归因锚:事件级覆盖恒等
        assert rep['unattributed'] == 0
        assert rep['attributed_events'] == rep['total_events']
        assert rep['total_events'] == 4
        # 三形态逐行命中
        assert rep['shape_rows'].get('no_fuel_honest') == 2
        assert rep['shape_rows'].get('chain_act') == 1
        assert rep['shape_rows'].get('honest_stall_dispute') == 1
        # 矛盾候选红 = 局级
        assert rep['violations'] == 1 and rep['games'] == [0]

    def test_occupancy_buckets_and_star2_not_fuel(self):
        rep = check_t190_c1_bench_clog_attribution(
            self._two_reject_rows())
        occ = rep['occupancy_buckets']
        # 希儿/花火 = roster_line(线名单,优先序高于 ④放行集)
        assert occ.get('roster_line') == 2
        # 艾丝妲/椒丘 = drop 档不入放行集 → 1★ 裸燃料形态
        assert occ.get('sellable_fuel') == 3
        # 2★ 艾丝妲落 star2_plus,不构成 sellable_fuel(局 1 诚实停摆)
        assert occ.get('star2_plus') == 1

    def test_transition_pack_bucket_priority(self):
        # 爻光 ∈ TRANSITION_PACK(partial)且 ∉ 希儿量子线名单 → pack 桶
        g = [_row(round_num=1,
                  bench=[_piece('爻光'), _piece('三月七')],
                  waves=[_wave({'缇宝': 'missing_bench_full'})],
                  counters={'core_locked_no_fuel': 1})]
        rep = check_t190_c1_bench_clog_attribution([g])
        assert rep['occupancy_buckets'].get('transition_pack') == 2
        assert rep['transition_pack_occupancy_frames'] == 1

    def test_non_benchfull_reasons_attributed(self):
        g = [_row(round_num=1,
                  bench=[_piece('希儿')],
                  waves=[_wave({'花火': 'owned',
                                '刻律德菈': 'missing_unaffordable',
                                '符玄': 'missing_no_path'})])]
        rep = check_t190_c1_bench_clog_attribution([g])
        assert rep['total_events'] == 3
        assert rep['unattributed'] == 0
        assert rep['reason_hist_wave'].get('owned') == 1
        assert rep['reason_hist_wave'].get('missing_unaffordable') == 1
        # 异常态披露不判红(violations 只辖矛盾候选)
        assert rep['missing_no_path_events'] == 1
        assert rep['violations'] == 0

    def test_obligation_and_hold_tags_beat_sellable(self):
        g = [_row(round_num=2,
                  bench=[_piece('青雀'), _piece('停云')],
                  actions=[_buy('青雀', 'm2_line_member'),
                           _buy('停云', 'core_single_card_buy')],
                  waves=[_wave({'缇宝': 'missing_bench_full'})],
                  counters={'core_locked_no_fuel': 1})]
        rep = check_t190_c1_bench_clog_attribution([g])
        # 两件都有渠道保护标签 → 零裸燃料 → 诚实停摆,不红
        assert rep['shape_rows'].get('no_fuel_honest') == 1
        assert rep['violations'] == 0


# =====================================================================
# C-A2 T-16 覆盖复查
# =====================================================================

class TestC2NewBuySwapCoverage:

    def test_recorded_and_deployed_covered_same_row_first(self):
        g = [
            _row(round_num=1,
                 bench=[_piece('青雀')],
                 actions=[_buy('青雀', 'm2_line_member')],
                 m1p={'nonempty': False, 'abstain': '',
                      'reasons': {'青雀': 'post_sell_held'}, 'sell': []}),
        ]
        rep = check_t190_c2_new_buy_swap_coverage([g])
        assert rep['buys_tracked'] == 1
        assert rep['shapes'].get('recorded@same_row') == 1
        assert rep['gaps_plan_active'] == 0
        assert 'coverage_closed' in rep['verdict']

    def test_gap_plan_active_is_red_with_verdict_repair(self):
        g = [
            _row(round_num=1,
                 bench=[_piece('青雀'), _piece('艾丝妲')],
                 deployed=[_piece('景元', star=2)],
                 cap=1,
                 actions=[_buy('青雀', 'm2_locked_member')],
                 m1p={'nonempty': True, 'abstain': '',
                      'reasons': {}, 'sell': ['景元']}),
        ]
        rep = check_t190_c2_new_buy_swap_coverage([g])
        # 青雀仍在 bench、不在 reasons、计划非空 → 强信号缺口
        assert rep['shapes'].get('gap_plan_active@same_row') == 1
        assert rep['violations'] == 1
        assert 'repair_face' in rep['verdict']
        assert rep['gap_samples'][0]['name'] == '青雀'

    def test_gap_plan_idle_and_board_open_weak(self):
        idle = [_row(round_num=1,
                     bench=[_piece('青雀')],
                     deployed=[_piece('景元'), _piece('彦卿')],
                     cap=2,
                     actions=[_buy('青雀', 'm2_line_member')],
                     m1p={'nonempty': False, 'abstain': '',
                          'reasons': {}, 'sell': []})]
        rep = check_t190_c2_new_buy_swap_coverage([idle])
        assert rep['shapes'].get('gap_plan_idle@same_row') == 1
        assert rep['violations'] == 0
        open_board = [_row(round_num=1,
                           bench=[_piece('青雀')],
                           deployed=[_piece('景元')],
                           cap=2,
                           actions=[_buy('青雀', 'm2_line_member')],
                           m1p={'nonempty': False, 'abstain': '',
                                'reasons': {}, 'sell': []})]
        rep2 = check_t190_c2_new_buy_swap_coverage([open_board])
        assert rep2['shapes'].get('gap_board_open@same_row') == 1
        assert rep2['violations'] == 0

    def test_no_plan_carrier_and_next_row_fallback(self):
        none_carrier = [_row(round_num=1,
                             bench=[_piece('青雀')],
                             actions=[_buy('青雀', 'm2_line_member')])]
        rep = check_t190_c2_new_buy_swap_coverage([none_carrier])
        assert rep['shapes'].get('no_plan_carrier') == 1
        fallback = [
            _row(round_num=1, bench=[_piece('青雀')],
                 actions=[_buy('青雀', 'm2_line_member')]),
            _row(round_num=2, bench=[_piece('青雀')],
                 m1p={'nonempty': False, 'abstain': '',
                      'reasons': {'青雀': 'post_sell_held'}, 'sell': []}),
        ]
        rep2 = check_t190_c2_new_buy_swap_coverage([fallback])
        assert rep2['shapes'].get('recorded@next_row') == 1


# =====================================================================
# C-A3 豁免集开火性
# =====================================================================

class TestC3ExemptionFire:

    def test_d_round_exempt_buy_positive(self):
        g = [_row(round_num=3,
                  actions=[_buy('青雀', 'm2_line_member'),
                           _buy('停云', 'core_single_card_buy')],
                  counters={'press_narrowed_transition_domain': 2})]
        rep = check_t190_c3_exemption_fire([g])
        assert rep['d_rounds'] == 1
        assert rep['dominance_narrow_fires'] == 2
        assert rep['exempt_buys_in_d_total'] == 2
        assert rep['exemption_zero_fire_in_d_rounds'] is False
        assert rep['violations'] == 0

    def test_domain_leak_p1_is_red(self):
        g = [_row(plane=1, round_num=4,
                  counters={'press_narrowed_transition_domain': 1})]
        rep = check_t190_c3_exemption_fire([g])
        assert rep['domain_leak_planes'] == [1]
        assert rep['violations'] == 1

    def test_hub_sentinel_is_red_and_separate(self):
        g = [_row(round_num=3,
                  counters={'press_narrowed_transition_domain_hub': 1})]
        rep = check_t190_c3_exemption_fire([g])
        assert rep['hub_sentinel_fires'] == 1
        assert rep['violations'] == 1
        assert rep['d_rounds'] == 0  # hub 键独立,禁并桶进 dominance 位

    def test_zero_fire_declared_not_red(self):
        g = [_row(round_num=3,
                  actions=[_buy('大黑塔', 'dominance_buy')],
                  counters={'press_narrowed_transition_domain': 1})]
        rep = check_t190_c3_exemption_fire([g])
        assert rep['exempt_buys_in_d_total'] == 0
        assert rep['exemption_zero_fire_in_d_rounds'] is True
        assert rep['violations'] == 0  # 空面申报非红(验收锚二选一)


# =====================================================================
# C-A4 转化漏斗配平
# =====================================================================

class TestC4FunnelReconcile:

    def test_closed_set_and_fate_balance(self):
        g = [
            # 行状态 = 局末快照(买后未部署件在本行 bench 上)
            _row(plane=2, round_num=1,
                 bench=[_piece('青雀'), _piece('停云'), _piece('艾丝妲')],
                 actions=[_buy('青雀', 'm2_line_member'),
                          _buy('停云', 'm2_locked_member'),
                          _buy('艾丝妲', 'dominance_buy')]),
            _row(plane=2, round_num=2,
                 bench=[_piece('停云')],
                 actions=[{'__type__': 'SellBench', 'name': '艾丝妲'}],
                 deployed=[_piece('青雀'), _piece('景元')]),
        ]
        rep = check_t190_c4_funnel_reconcile([g])
        assert rep['closed_set_unknown_keys'] == {}
        assert rep['fate_bitwise_match'] is True
        assert rep['buys_total'] == rep['fate_accounted'] == 3
        assert rep['violations'] == 0
        funnel = rep['funnel_by_arm']
        # 闭集全键在表(零计键也列)
        assert set(funnel) == set(LAUNCH_CAUSE_BY_ARM)
        assert funnel['m2_line_member']['fates'].get('reached_board') == 1
        assert funnel['dominance_buy']['fates'].get('sold') == 1
        assert funnel['m2_locked_member']['fates'].get('stuck_end') == 1

    def test_ghost_arm_key_is_red(self):
        g = [_row(plane=2, round_num=1,
                  actions=[_buy('青雀', 'ghost_arm_buy')])]
        rep = check_t190_c4_funnel_reconcile([g])
        assert rep['closed_set_unknown_keys'] == {'ghost_arm_buy': 1}
        assert rep['violations'] == 1

    def test_shrink_settles_unnamed_consumption(self):
        # 买入 2 件同名,局终场上只剩 1 件(1 件无名卖出/合成消耗)
        # → 收缩对账把多出的台账副本认 sold,总量仍配平
        g = [
            _row(plane=2, round_num=1,
                 bench=[_piece('青雀'), _piece('青雀')],
                 actions=[_buy('青雀', 'm2_stockpile'),
                          _buy('青雀', 'm2_stockpile')]),
            _row(plane=2, round_num=2, bench=[_piece('青雀')]),
        ]
        rep = check_t190_c4_funnel_reconcile([g])
        assert rep['fate_bitwise_match'] is True
        assert rep['violations'] == 0
        fates = rep['funnel_by_arm']['m2_stockpile']['fates']
        assert fates.get('sold') == 1
        assert fates.get('stuck_end') == 1


# =====================================================================
# 守卫移除验证(引擎级;快照池种子锚,在册批复用种子段)
# =====================================================================

# 种子重锚(2026-09-12,T-313 P92 ④资格维修复落码,凭据=该批交付报告
# §④):修复改变停摆帧族轨迹形态,原种子 (8575, 8555, 8596) 在 M-C1
# 变异下矛盾候选 honest_stall_dispute 不再涌现——种子锚漂移而非检查器
# 失明(邻段探针 13 种子三场景全兼容实证)。现锚三种子逐粒验证:
# c3b 正控 D 轮豁免可开火 ∧ c3a 拔辖域纪律可检出泄漏 ∧ c1 拔腾席支
# victim 生产面可检出矛盾候选。
_SNAP_SEEDS = (8572, 8593, 8594)


def _run_games(patch=None, seeds: tuple = _SNAP_SEEDS):
    """跑小批(快照池)返回账本;``patch`` = 零参闭包,守卫移除变异用
    (在引擎首局跑前施设一次)。"""
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    if patch is not None:
        patch()
    return [simulate_p1(s, pool='snapshot', planes=2).ledger
            for s in seeds]


class TestGuardRemovalEngine:
    """守卫移除三发:两红(M-C1/M-C3a)+ 一绿正控(M-C3b)。"""

    def test_m_c3b_positive_control_exempt_fires_in_d_rounds(self):
        """正控(不拔守卫):真实批 D 轮豁免买入 >0 = 解封收益可见,C-A3 绿。"""
        ledgers = _run_games()
        rep = check_t190_c3_exemption_fire(ledgers)
        assert rep['d_rounds'] > 0, '种子锚漂移:D 轮绝迹,重锚 _SNAP_SEEDS'
        assert rep['exempt_buys_in_d_total'] > 0
        assert rep['violations'] == 0
        assert rep['domain_leak_planes'] == []
        assert rep['hub_sentinel_fires'] == 0

    def test_m_c3a_narrow_scope_guard_removal_leaks_to_p1(self, monkeypatch):
        """M-C3a:拔收窄辖域纪律(域谓词恒 True)→ 开火落 P1 → 红涌现。

        patch 位 = mandate 模块属性(shop.py 经 ``mandate.swap_transition_
        narrow_frame`` 模块属性调用,prep 位同模块直调——单点覆盖两域)。
        """
        import sr_od.application.currency_war.strategies.impl.mandate_v1.mandate as mandate_mod

        def _overbroad(state, session):
            return True

        monkeypatch.setattr(mandate_mod, 'swap_transition_narrow_frame',
                            _overbroad)
        ledgers = _run_games()
        rep = check_t190_c3_exemption_fire(ledgers)
        assert rep['domain_leak_planes'], \
            '守卫移除未涌现:P1 域泄漏零开火(检查器对辖域失守失明)'
        assert rep['violations'] == 1

    def test_m_c1_fuel_source_guard_removal_forges_disputes(self, monkeypatch):
        """M-C1:拔腾席支 victim 生产面(fuel_sell_candidates 恒空)
        → 诚实停摆被伪造 → C-A1 矛盾候选必须涌现。"""
        import sr_od.application.currency_war.strategies.impl.mandate_v1.mandate as mandate_mod

        def _no_fuel(bench, k_members, state=None, *, exclude_names=None,
                     defer_names=None, counters=None, dedup_names=None):
            return []

        monkeypatch.setattr(mandate_mod, 'fuel_sell_candidates', _no_fuel)
        ledgers = _run_games()
        rep = check_t190_c1_bench_clog_attribution(ledgers)
        assert rep['benchfull_rows'] > 0, \
            '种子锚漂移:零 core 拒 bench 满行,重锚 _SNAP_SEEDS'
        assert rep['shape_rows'].get('honest_stall_dispute', 0) > 0, \
            '守卫移除未涌现:victim 生产面被拔而矛盾候选零显影'
        assert rep['violations'] > 0
