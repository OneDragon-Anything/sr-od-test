"""sim 观测面补齐批五观察件测试(刷新触发源分键/冷启动金轨迹/theta 成因
分桶/b_t 写者(form_score 口径替换)/fenced 拆键)。

纪律 = 先立观察再定谳,纯观测零策略语义改动;锁契约 = 结构/回显,
不锁分布数值(README 第 8 条)。五锁与落点:
1. 刷新触发源(任务①):sim 账本 RefreshShop 动作带 reason 记录字段
   (kernel/cw_state.RefreshShop,先例 = LevelUp.auth_basis「记录不是
   指令」);行内 obs.refresh_trigger 分键与 actions 逐项对账。
2. 冷启动金轨迹(任务②):cw_batch_stats analyze_game 冷启动金轨迹
   = P1 r1-r4 逐轮轮末金(口径 = decisions 行 gold,对照
   20260906-0145-simfind 报告问题 1 的轨迹形态口径)。
3. theta 成因分桶(任务③):proof.switch_param_missing 缺失清单 +
   should_switch 聚合键 theta_unavailable 原样 + 成因键
   theta_unavailable_<槽位>(不同键防混淆,R24-2)。
4. b_t 写者(form_score→B_t 口径替换):flow.write_shop_mirrors 写
   session.v3_b_t(kernel board_target_line_weight 单一源口径),
   空板恒 0、上场线内件逐件计数;phase/form_ok 退役缺省不受影响。
5. fenced 拆键(任务⑤):kernel can_deploy_single 拒因五键词表
   (单一源)可产生 cap/name_dup;发射位拆键透传 + 预注册裁决协议
   注释在场(源码契约锁,exit3_fence_semantics DESIGN §5-3)。
"""
from __future__ import annotations

import importlib.util
import inspect

from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    can_deploy_single,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.sim.engine_p1 import (
    sim_decision_registry,
    simulate_p1,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    provisional,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)


def _load_stats_module():
    """cw_batch_stats(skill 脚本,非包成员)按路径加载(同采购面批)。"""
    from one_dragon.utils.file_utils import get_project_root
    path = (get_project_root() / 'skills' / 'sr-od-currency-war-dev'
            / 'scripts' / 'cw_batch_stats.py')
    spec = importlib.util.spec_from_file_location('cw_batch_stats_b2', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_stats_module()

_SEED_CACHE: dict[int, object] = {}


def _seeded_result(seed: int):
    """同 seed 单局结果同次运行只算一次(昂贵计算共享,README 纪律)。"""
    if seed not in _SEED_CACHE:
        _SEED_CACHE[seed] = simulate_p1(seed, pool='snapshot')
    return _SEED_CACHE[seed]


def _mk_strat() -> MandateV1Strategy:
    return MandateV1Strategy(registry=sim_decision_registry())


# ---------- 锁 1:刷新触发源分键(任务①) ----------

class TestRefreshTriggerSource:
    def test_refresh_action_carries_reason(self):
        """sim 账本 RefreshShop 动作必带触发源 reason(值域契约;
        零刷新局跳过——采样窗口内至少一局有刷新,否则观测面失明)。"""
        seen = 0
        for seed in range(4):
            for row in _seeded_result(seed).ledger:
                for a in row.get('actions') or []:
                    if a.get('__type__') != 'RefreshShop':
                        continue
                    seen += 1
                    assert a.get('reason') in (
                        'r1', 'must_spend_r1_yielded'), a
        assert seen, '采样 4 seed 零刷新动作(观测面失明,需换 seed 窗口)'

    def test_obs_refresh_trigger_matches_actions(self):
        """obs.refresh_trigger 分键 = 本轮 RefreshShop 动作按 reason
        计数(逐轮逐项对账;''/未标 = other 桶)。"""
        for seed in range(2):
            for row in _seeded_result(seed).ledger:
                want: dict[str, int] = {}
                for a in row.get('actions') or []:
                    if a.get('__type__') != 'RefreshShop':
                        continue
                    k = a.get('reason') or 'other'
                    want[k] = want.get(k, 0) + 1
                got = (row.get('obs') or {}).get('refresh_trigger')
                assert got == want, (row.get('round_num'), got, want)


# ---------- 锁 2:冷启动金轨迹统计族(任务②) ----------

class TestColdGoldTrajectory:
    def test_cold_track_identity(self):
        """冷启动金轨迹 = P1 r1-r4 逐轮轮末金(合成行回显锁)。"""
        rows = [{'plane': 1, 'round': rr, 'gold': g, 'hp': None,
                 'hp_delta': None, 'node_type': None, 'form': None,
                 'form_ok': False, 'level': 3, 'deployed': [],
                 'factions': {}, 'acts': [], 'launch': None,
                 'shop_waves': [], 'obs': {}}
                for rr, g in ((1, 10), (2, 24), (3, 47), (4, 41))]
        rows.append({'plane': 1, 'round': 5, 'gold': 3, 'hp': None,
                     'hp_delta': None, 'node_type': None, 'form': None,
                     'form_ok': False, 'level': 3, 'deployed': [],
                     'factions': {}, 'acts': [], 'launch': None,
                     'shop_waves': [], 'obs': {}})
        m = mod.analyze_game(rows)
        assert m['冷启动金轨迹'] == [10, 24, 47, 41]

    def test_report_prints_trajectory_section(self):
        """J 族打印面不炸(零观测局 = 无数据退化,不误报)。"""
        rows = [{'plane': 1, 'round': 1, 'gold': 5, 'hp': None,
                 'hp_delta': None, 'node_type': None, 'form': None,
                 'form_ok': False, 'level': 3, 'deployed': [],
                 'factions': {}, 'acts': [], 'launch': None,
                 'shop_waves': [], 'obs': {}}]
        mod.report({'g0': rows}, 'cold-track-smoke')   # 不抛即过


# ---------- 锁 3:theta_unavailable 成因分桶(任务③) ----------

class TestThetaUnavailableCauseKeys:
    def setup_method(self):
        provisional.reset()

    def teardown_method(self):
        provisional.reset()   # 全局槽位测试隔离(测试纪律)

    def test_missing_list_slots(self):
        """缺失清单逐槽位回显(全缺/单缺两种形态)。"""
        assert proof.switch_param_missing() == ['theta', 'd_min', 'delta']
        provisional.inject('THETA', provisional.CalibValue(1.0))
        assert proof.switch_param_missing() == ['d_min', 'delta']

    def test_should_switch_counts_aggregate_and_causes(self):
        """聚合键 theta_unavailable 原样 + 三成因键各计一次(不同键
        防混淆;判返回值不变 = SwitchOutcome(False,'theta_unavailable'))。"""
        sess = StrategySession()
        sess.cw4_counters = {}   # 计数载体(entry 每局创建;直调需预置)
        out = proof.should_switch(GameState(), sess, None, None)
        assert out.event is False and out.key == 'theta_unavailable'
        ct = sess.cw4_counters
        assert ct.get('theta_unavailable') == 1
        assert ct.get('theta_unavailable_theta') == 1
        assert ct.get('theta_unavailable_d_min') == 1
        assert ct.get('theta_unavailable_delta') == 1


# ---------- 锁 4:b_t 写者(form_score→B_t 口径替换) ----------

class TestBoardTargetLineWriter:
    def test_empty_board_zero_and_stamp(self):
        """空板 = 0(板面真空事实态照写不虚构);轮键戳盖章
        (sim 引擎缺写守卫不重复触发)。"""
        sess = StrategySession()
        st = GameState()
        _mk_strat().write_shop_mirrors(st, sess)
        assert sess.v3_b_t == 0
        assert sess.v3_mirror_key == (1, 1)

    def test_deployed_line_pieces_counted(self):
        """有上场线内件 → 按件计数(青雀=仙舟∈线内集,3 件 = 3;
        退役字段 v3_form_score 不再有写者)。char_id 用注册表真名
        (B_t 按注册表查羁绊,未注册假名不计)。"""
        sess = StrategySession()
        st = GameState()
        _mk_strat().write_shop_mirrors(st, sess)
        base = sess.v3_b_t
        assert base == 0
        st.deployed = [BenchChar(slot=i, char_id='青雀', star=1,
                                 faction='仙舟', position_pref='back')
                       for i in range(3)]
        _mk_strat().write_shop_mirrors(st, sess)
        assert sess.v3_b_t == 3, '三件线内上场件应逐件计 3'

    def test_out_of_line_and_unregistered_not_counted(self):
        """线外件与未注册件不计(件级承重口径:仅线内阵营集命中件计 1)。"""
        sess = StrategySession()
        st = GameState()
        st.deployed = [BenchChar(slot=0, char_id='x_unregistered', star=1,
                                 faction='', position_pref='back')]
        _mk_strat().write_shop_mirrors(st, sess)
        assert sess.v3_b_t == 0

    def test_phase_retired_form_ok_present_read(self):
        """phase 维持无写端退役缺省;form_ok 已接 readiness_form_ok
        板面现读(sim71 批死镜像处置;GameState 空板 → 现读 False,
        与缺省同值但路径不同——写端已接线)。正确性细锁 =
        test_cw_obs_keys_sim71 直调写端面。"""
        sess = StrategySession()
        st = GameState()
        st.deployed = [BenchChar(slot=0, char_id='x', star=1,
                                 faction='仙舟', position_pref='back')]
        _mk_strat().write_shop_mirrors(st, sess)
        assert getattr(sess, 'v3_phase', None) in (None, '', 'FORM')
        assert sess.v3_form_ok is False


# ---------- 锁 6:terminal_release 账本行键接线(增补 C1) ----------

class TestTerminalReleaseLedgerKey:
    def test_row_key_present_and_bool(self):
        """账本行键 terminal_release 恢复写入(C1 接线;曾缺写 →
        检查器恒读缺省 False 命中不可判,sim58 报告问题 3 同源)。"""
        for row in _seeded_result(0).ledger:
            assert isinstance(row.get('terminal_release'), bool), \
                f"行 {row.get('round_num')} 缺 terminal_release 布尔键"

    def test_checker_consumes_row_key(self):
        """seg_p1_blood_budget_refresh 吃行键豁免面(结构锁):位真 =
        带内刷新合法;位假/缺省 = 违规事件。"""
        from sr_od.application.currency_war.sim.checks.segments import (
            seg_check_p1_blood_budget_refresh,
        )

        def _rows(bit: bool) -> list[dict]:
            base = {'plane': 1, 'actions': [], 'sim': {'node': 'battle'}}
            return [dict(base, round_num=6, hp=40),
                    dict(base, round_num=7, hp=40, terminal_release=bit,
                         actions=[{'__type__': 'RefreshShop', 'cost': 2}])]

        assert seg_check_p1_blood_budget_refresh(_rows(True)) == []
        evs = seg_check_p1_blood_budget_refresh(_rows(False))
        assert len(evs) == 1 and evs[0]['terminal_release'] is False


# ---------- 锁 5:fenced 拆键 + 预注册协议(任务⑤) ----------

def _bc(name: str) -> BenchChar:
    return BenchChar(slot=0, char_id=name, star=1, faction='?',
                     position_pref='back')


class TestFencedSplitKeys:
    def test_kernel_reason_vocabulary(self):
        """kernel 拒因词表(单一源,cw_deploy_logic):板满 → 'cap';
        同名已上阵 → 'name_dup'——拆键透传的键值必须出自该闭集。"""
        _ok, why_cap = can_deploy_single(
            _bc('cand'), [],
            deployed_cids={'a'}, deployed_fac={}, board={},
            cap=1, front_total=4, back_total=6)
        assert why_cap == 'cap'
        _ok, why_dup = can_deploy_single(
            _bc('a'), [],
            deployed_cids={'a'}, deployed_fac={}, board={},
            cap=10, front_total=4, back_total=6)
        assert why_dup == 'name_dup'

    def test_emission_split_and_protocol_in_source(self):
        """发射位拆键透传(fenced_<拒因> 动态键 + l2_ 触发源前缀键)
        与预注册裁决协议注释在场(源码契约锁;协议原文 =
        exit3_fence_semantics DESIGN §5-3)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            shop,
        )
        src = inspect.getsource(shop)
        assert "fuel_filler_stall_fenced_'" in src \
            and "'{_ff_why}'" in src, '拆键透传缺失'
        assert "'l2_{_ff_why}'" in src, '触发源对照分列缺失'
        assert '预注册裁决协议' in src and 'DESIGN §5-3' in src, \
            '预注册协议注释缺失'
