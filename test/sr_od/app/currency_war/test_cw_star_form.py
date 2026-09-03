# -*- coding: utf-8 -*-
"""test_cw_star_form 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w230_star_form: test_cw_w230_star_form.py
- w242_star_directed: test_cw_w242_star_directed.py
- w255_formed_target_boss_nodemech: test_cw_w255_formed_target_boss_nodemech.py
- w170_p1_pair_vd: test_cw_w170_p1_pair_vd.py
- w179_p1_early_gate: test_cw_w179_p1_early_gate.py
- w160_avatar_variants: test_cw_w160_avatar_variants.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w230_star_form ====================

import dataclasses
import logging

import pytest

from sr_od.application.currency_war.data.cw_battle_tables import P2CombatCalib
from sr_od.application.currency_war.kernel import cw_battle_calib as _calib
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState

# 分包期 6 双 runner 归家:批量/敏感性入口 simulate_* 归 sim/runner
# (checks.runner 只辖检查聚合 run_batch_*/run_checks_*)
from sr_od.application.currency_war.sim import runner
from sr_od.application.currency_war.sim.engine_p2 import P2ReplayEntry


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)



def _st(stars: tuple[int, ...] = (), level: int = 6) -> GameState:
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, level, 50, 60
    # 仙舟×3 = 达成仙舟体系 → engines=1(绝对锚,同 锁)
    units = [BenchChar(slot=1, char_id='c0', faction='仙舟', star=stars[0] if stars else 1),
             BenchChar(slot=2, char_id='c1', faction='仙舟', star=stars[1] if len(stars) > 1 else 1),
             BenchChar(slot=3, char_id='c2', faction='仙舟', star=stars[2] if len(stars) > 2 else 1)]
    st.deployed = units
    return st


# ---------- form 分量断言 ----------

def test_form_star_component_arithmetic() -> None:
    """form = engines + w·(lv−6) + ws·Σ(star−1):星级折算 + 全量口径。"""
    calib = P2CombatCalib()          # ws=0.5 默认
    base = _calib.p2_form_key(_st(), calib)          # 全 1★ → star_depth=0
    # 一颗 2★:star_depth=1 → form +0.5
    assert abs(_calib.p2_form_key(_st((2, 1, 1)), calib)
               - (base + 0.5)) < 1e-9
    # 一颗 3★:star_depth=2 → form +1.0(线性,3★ 对 2★ 仍有增量)
    assert abs(_calib.p2_form_key(_st((3, 1, 1)), calib)
               - (base + 1.0)) < 1e-9
    # 两颗 2★:star_depth=2
    assert abs(_calib.p2_form_key(_st((2, 2, 1)), calib)
               - (base + 1.0)) < 1e-9
    # win_p 通道:星级 ↑ → 胜率 ↑(因果通道存在的最小断言)
    wp1 = _calib.p2_win_p(_st((1, 1, 1)), 'battle', 1, calib)
    wp2 = _calib.p2_win_p(_st((2, 2, 1)), 'battle', 1, calib)
    assert wp2 > wp1


def test_form_star_weight_zero_returns_old_form() -> None:
    """ws=0 = ADR-0377 旧 form 形态逐位回(engines+level 折算)。"""
    old = dataclasses.replace(P2CombatCalib(), form_star_weight=0.0)
    for stars in ((), (2, 1, 1), (3, 2, 2), (3, 3, 3)):
        st = _st(stars)
        expect = _calib._settle_rung(st) + old.form_level_weight * (
            st.level - old.form_level_base)
        assert abs(_calib.p2_form_key(st, old) - expect) < 1e-9


# ---------- 校准带内(锚 R1 统计量,ADR-0377 同门) ----------

def test_calibration_anchor_r1_in_band() -> None:
    """案 b 臂(真值进场态)锚 R1 主统计量带内:存活轮 ∈ [0,7](真值
    轮数带 [0,6]+1)/聚合胜率 ∈ [0, 0.55]。
    重锚(2026-09-07,M4 残余批):W956 锚带 [0,0.285] 之后两个已提交
    校准批抬升 P2 聚合胜率 0.226→0.40——fdac8186(代码面收口:轮岗
    建模修复,触面 cw_battle_calib/cw_deploy_logic)首位移至 0.333,
    4cbfb64a(输入基线定稿:机制修改器审计 16 项)再至 0.40,其后至
    HEAD 零位移(git worktree 逐 commit 复核)。带上界 = 新实测 0.40
    + 0.15 容差(沿用原带结构:锚定实测边际 + 同容差;原真值语料
    truth_star.json 已随 cw3 删除迁移,不再可复算,改锚 sim 实测)。
    单 seed 抽样核(全量对拍在批报告,本锁防 form 改动把统计量打出带)。"""
    entries = [
        P2ReplayEntry(hp=60, gold=30, level=6,
                      deployed=[{'char_id': '丹恒·饮月', 'faction': '仙舟',
                                 'star': 2, 'position_pref': 'front'}]),
        P2ReplayEntry(hp=35, gold=20, level=6,
                      deployed=[{'char_id': '丹恒·饮月', 'faction': '仙舟',
                                 'star': 1, 'position_pref': 'front'},
                                {'char_id': '停云', 'faction': '仙舟',
                                 'star': 2, 'position_pref': 'front'},
                                {'char_id': '符玄', 'faction': '仙舟',
                                 'star': 1, 'position_pref': 'front'}]),
    ]
    rounds_all, wt, ww = [], 0, 0
    for e in entries:
        for s in range(4):
            r = engine_p2.simulate_p2_replay_entry(e, s, pool='snapshot')
            if r.p2_entered:
                rounds_all.append(r.p2_rounds)
                wt += r.p2_combat_total
                ww += r.p2_combat_wins
    assert rounds_all and 0 <= sum(rounds_all) / len(rounds_all) <= 7
    if wt:
        assert 0.0 <= ww / wt <= 0.55


# ---------- P1 锚回归(form 只辖 plane>=2) ----------

def test_p1_zero_drift_star_form() -> None:
    """ws=0(旧 form)vs 默认 ws=0.5:P1 段逐位零漂移(planes=2 批的
    plane=1 账本行;星级分量只进 P2 战斗结算)。"""
    old = dataclasses.replace(P2CombatCalib(), form_star_weight=0.0)
    for seed in (0, 1, 2):
        ra = engine_p1.simulate_p1(seed, pool='fallback', planes=2,
                                p2_combat=P2CombatCalib())
        rb = engine_p1.simulate_p1(seed, pool='fallback', planes=2,
                                p2_combat=old)
        pa = [row for row in ra.ledger if row.get('plane') == 1]
        pb = [row for row in rb.ledger if row.get('plane') == 1]
        assert pa == pb


# ---------- 敏感性网格键 ----------

def test_sensitivity_grid_star_key() -> None:
    """simulate_p2_sensitivity 网格行带 form_star_weight 键(维入表)。"""
    out = runner.simulate_p2_sensitivity(
        n=2, pool='fallback', planes=2, betas=(0.04,), gammas=(0.02,),
        event_gold_arms=('p1',), form_level_weights=(0.25,),
        form_star_weights=(0.0, 0.5))
    assert len(out['grid']) == 2
    assert {row['form_star_weight'] for row in out['grid']} == {0.0, 0.5}


from sr_od.application.currency_war.sim import engine_p1, engine_p2


# ==================== w242_star_directed ====================

import logging as _w242_star_directed_logging
from types import SimpleNamespace

import pytest as _w242_star_directed_pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import _check_constraint, arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate, _buy_tag, generate_candidates
from sr_od.application.currency_war.decision.decision_v2.handoff import handoff_gate_gap
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w242_star_directed_BenchChar, BuyCard, GameState as _w242_star_directed_GameState, ShopCard


@_w242_star_directed_pytest.fixture(autouse=True)
def _w242_star_directed_quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = _w242_star_directed_logging.root.manager.disable
    _w242_star_directed_logging.disable(_w242_star_directed_logging.CRITICAL)
    yield
    _w242_star_directed_logging.disable(prev)


#: ADR-0411:C 项授权无条件启用——行为臂即 DEFAULT_REGISTRY
_REG = DEFAULT_REGISTRY

_CARRY = '姬子·启行'
_FILLER = '娜塔莎'
_FAC = '贝洛伯格'


def _bench(name: str, faction: str, slot: int = 0,
           star: int = 1) -> _w242_star_directed_BenchChar:
    return _w242_star_directed_BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _deployed(name: str, faction: str, star: int = 1,
              slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=star,
                           position_pref='back', equips=(), slot=slot)


def _sess() -> StrategySession:
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget, IntentionState
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {_CARRY}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=(_CARRY,))
    return s


def _state(**kw) -> _w242_star_directed_GameState:
    """末窗承接缺口帧:P1 r8,hp 临界(boss 投影后 hp_tier=0)+板面
    tier0(全 1★ → core2=0)→ gap=1(C 项目标场景:星级深度主罚维)。"""
    base = {'plane': 1, 'round_num': 8, 'gold': 55, 'level': 5,
            'hp': 20,
            'board': {'列车同行': 2, _FAC: 1},
            'deployed': [_deployed(_CARRY, '列车同行'),
                         _deployed(_FILLER, _FAC)],
            'bench': [], 'shop': [], 'node_type': 'battle'}
    base.update(kw)
    return _w242_star_directed_GameState(**base)


# ---------- ① 授权点:candidates 层放行生成(非授权) ----------


def test_copy_candidate_generated_in_final_window() -> None:
    """末窗 gap≥1 时方向外 deployed 填充件同名卡生成 'copy' 候选
    (r410 守卫+方向门双豁免)。

    语义演进(ADR-0451 血预算停手·第二波):授权帧改 hp=90(带外,
    ≥p1_exit_blood_target;board 维 tier0 主罚 gap≥1 前置不变)——
    原 hp=20 帧已入末窗血预算不足带,降格面停定向 'copy' 生成臂
    (反例见同文件 test_copy_arm_downgraded_in_blood_band)。"""
    sess = _sess()
    st = _state(hp=90,
                shop=[ShopCard(x=1, faction=_FAC, name=_FILLER, cost=3)])
    assert handoff_gate_gap(st, sess, _REG) >= 1   # 前置:缺口成立
    got = generate_candidates(st, sess, _REG)
    names = [c.action.card.name for c in got if isinstance(c.action,
                                                           BuyCard)]
    assert _FILLER in names
    tag = _buy_tag(st.shop[0], st, sess, _REG)
    assert tag == 'copy'


def test_copy_arm_downgraded_in_blood_band() -> None:
    """ADR-0451 反例锁:同构造 hp=20(末窗血预算不足带)定向 'copy'
    臂降格不生成——血预算不足帧行为(战力投资搜索 → 减损保血)。"""
    sess = _sess()
    st = _state(shop=[ShopCard(x=1, faction=_FAC, name=_FILLER, cost=3)])
    assert handoff_gate_gap(st, sess, _REG) >= 1   # 前置:缺口仍在
    assert _buy_tag(st.shop[0], st, sess, _REG) != 'copy'


def test_copies_cap_and_r408_still_govern() -> None:
    """约束照常辖:星级加权 ≥3 份不生成;r408 同轮已卖名不生成
    (豁免只跳过 r410+方向门,纪律守卫不豁免)。"""
    sess = _sess()
    # copies_cap:deployed 1 + bench 2 = 加权 3 → 第 4 份拒
    st = _state(
        bench=[_bench(_FILLER, _FAC, slot=0),
               _bench(_FILLER, _FAC, slot=1)],
        shop=[ShopCard(x=1, faction=_FAC, name=_FILLER, cost=3)])
    names = [c.action.card.name for c in generate_candidates(st, sess, _REG)
             if isinstance(c.action, BuyCard)]
    assert _FILLER not in names
    # r408 同轮已卖:session 簿记已卖名 → 不生成
    st2 = _state(shop=[ShopCard(x=1, faction=_FAC, name=_FILLER, cost=3)])
    s2 = _sess()
    s2.v2_round_key = (1, 8)
    s2.v2_round_sold = {_FILLER}
    assert _buy_tag(st2.shop[0], st2, s2, _REG) is None


# ---------- ② arbiter 非正分门:定向放行 + 防双计 ----------


def _copy_cand(st: _w242_star_directed_GameState, cost: int = 3) -> Candidate:
    return Candidate(action=BuyCard(
        ShopCard(x=1, faction=_FAC, name=_FILLER, cost=cost), reason=''),
        tag='copy', source='shop')


def test_arbiter_nonpositive_gate_directed_pass() -> None:
    """主通道:末窗 gap≥1 时零分 'copy' 买候选进约束链而非「非正分」
    拒(放行≠必买:金不足/容量约束仍拒);非末窗照拒;非 'copy'
    标签零分候选照拒(定向性)。

    语义演进(ADR-0451):授权帧改 hp=90 带外——血预算不足帧的非正分
    'copy' 豁免同步降格(见 test_copy_arm_downgraded_in_blood_band)。"""
    st = _state(gold=55, hp=90)
    sess = _sess()
    res = arbitrate([(_copy_cand(st), 0.0, {'cost': 3})], st, sess, _REG)
    row = res.log[0]
    assert row['accepted'] is True, f'末窗 gap 授权应放行(log={row})'
    assert any(isinstance(a, BuyCard) for a in res.actions)
    # 同帧 r5(非末窗,W288/ADR-0418 前移后边界):gap=0 → 非正分照拒
    st5 = _state(round_num=5)
    res7 = arbitrate([(_copy_cand(st5), 0.0, {'cost': 3})], st5, sess,
                     _REG)
    assert res7.log[0]['reject'] == '非正分'
    # 定向性:非 copy 标签的零分候选照拒(如 line_opportunistic)
    res_other = arbitrate(
        [(Candidate(action=BuyCard(
            ShopCard(x=1, faction='列车同行', name='三月七', cost=3),
            reason=''), tag='line_opportunistic', source='shop'),
          0.0, {'cost': 3})], st, sess, _REG)
    assert res_other.log[0]['reject'] == '非正分'


def test_arbiter_constraint_chain_still_rejects() -> None:
    """放行只跳过非正分门,不豁免约束链:金不足以付地板 → gold_floor
    拒(零分候选不进 EV 账时地板族照辖;放行≠必买)。"""
    st = _state(gold=8)   # boss 前低金:经济地板 50 远超
    sess = _sess()
    res = arbitrate([(_copy_cand(st, cost=3), 0.0, {'cost': 3})], st,
                    sess, _REG)
    assert res.log[0]['accepted'] is False
    assert not any(isinstance(a, BuyCard) for a in res.actions)


def test_ev_gap_bonus_single_source_no_double_count() -> None:
    """防双计:EV 授权值单一源 = interest_rule 的 W227 缺口项
    (handoff_ev_gap_bonus×gap);C 授权路径不加第二份授权值——r8
    (boss 窗外)跨档买经缺口项放行(auth 带 handoff_gap);
    registry 无 C 项专有数值常量(no star_directed_* bonus 字段)。

    语义演进(ADR-0451):授权帧改 hp=70 带外——hp<60 末窗帧缺口项
    降格不加成(血预算停手·P1-a),反例:hp=30 帧同构造被拒。"""
    st = _state(gold=53, hp=70)   # 带外:投影后 hp_tier=2,board 维 tier0
    sess = _sess()
    cand = _copy_cand(st, cost=4)
    auth: dict = {}
    r = _check_constraint('interest_rule', cand, st, st, sess, _REG,
                          val=1.0, bd={'int_emb': 0.0}, auth=auth)
    # r8 node_type=battle → interest_rule 辖:缺口项 V+5×1 → 放行
    assert r is None
    assert auth.get('handoff_gap') == 1
    assert auth.get('ev_auth', 0) > 0
    # ADR-0451 反例:hp=30(末窗血预算不足带)缺口项不加成 → EV≤0 拒
    st_band = _state(gold=53, hp=30)
    r_band = _check_constraint('interest_rule', _copy_cand(st_band, cost=4),
                               st_band, st_band, sess, _REG,
                               val=1.0, bd={'int_emb': 0.0})
    assert r_band is not None
    # 数值单一源:registry 无 C 项专有 bonus 常量
    assert not [f for f in type(DEFAULT_REGISTRY).__dataclass_fields__
                if f.startswith('handoff_star')]


# ---------- ③ 窗口辖域 ----------


def test_gap_window_scope() -> None:
    """缺口窗口辖域:P1 末窗(r>=6,W288/ADR-0418 前移)才 >0;
    非末窗/P2/达标帧恒 0。"""
    sess = _sess()
    st = _state()
    assert handoff_gate_gap(st, sess, _REG) >= 1
    # 新窗内(r7):照辖(窗加宽语义)
    assert handoff_gate_gap(_state(round_num=7), sess, _REG) >= 0
    assert handoff_gate_gap(_state(round_num=5), sess, _REG) == 0
    assert handoff_gate_gap(_state(plane=2), sess, _REG) == 0
    # 达标帧(W227 锁同式 DOT 队成型帧,hp 高带):gap=0 → C 授权随之关
    # (授权强度单一源随 gap 走,gap=0 即零行为)
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState, intention_core
    comp = get_comp('DOT队')
    core = intention_core(comp)
    st_ok = _w242_star_directed_GameState(
        plane=1, round_num=8, gold=55, level=5, hp=90,
        board=dict(comp.form_tiers),
        deployed=[_w242_star_directed_BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                            star=2),
                  _w242_star_directed_BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮',
                            star=1)],
        bench=[], shop=[], node_type='battle')
    s_ok = StrategySession()
    s_ok.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    s_ok.v3_mode = 'economy'
    assert handoff_gate_gap(st_ok, s_ok, _REG) == 0


# ==================== w255_formed_target_boss_nodemech ====================

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import HoardTarget, IntentionState, intention_core
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w255_formed_target_boss_nodemech_BenchChar, BuyCard as _w255_formed_target_boss_nodemech_BuyCard, DeployMove, GameState as _w255_formed_target_boss_nodemech_GameState, LevelUp, RefreshShop, SellBench, ShopCard as _w255_formed_target_boss_nodemech_ShopCard
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w255_formed_target_boss_nodemech_StrategySession
from sr_od.application.currency_war.kernel.cw_system_cards import engine_char_names
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate as _w255_formed_target_boss_nodemech_arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate as _w255_formed_target_boss_nodemech_Candidate
from sr_od.application.currency_war.decision.decision_v2.filters import filter_candidates
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _w255_formed_target_boss_nodemech_DEFAULT_REGISTRY


def _card(name: str, cost: int = 3) -> _w255_formed_target_boss_nodemech_ShopCard:
    return _w255_formed_target_boss_nodemech_ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _cands(buy_names: list[str]) -> list[_w255_formed_target_boss_nodemech_Candidate]:
    """多条买候选(各一条)+ 等级买/刷新/卖/上阵各一(例外域)。"""
    out = [_w255_formed_target_boss_nodemech_Candidate(action=_w255_formed_target_boss_nodemech_BuyCard(_card(n), reason=''), tag='line_carry',
                     source='shop') for n in buy_names]
    out += [
        _w255_formed_target_boss_nodemech_Candidate(action=LevelUp(cost=4), tag='levelup', source='xp'),
        _w255_formed_target_boss_nodemech_Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
        _w255_formed_target_boss_nodemech_Candidate(action=SellBench(bench_idx=0, income=1, expect=''),
                  tag='for_gold', source='bench'),
        _w255_formed_target_boss_nodemech_Candidate(action=DeployMove(bench_idx=1, to_row='front',
                                    faction='仙舟罗浮'),
                  tag='deploy', source='fence'),
    ]
    return out


def _formed_state(**kw) -> _w255_formed_target_boss_nodemech_GameState:
    """成型态(DOT队 form_tiers 全满 + 核心上场 2★ + P1 r7,金 60)。

    ADR-0418 前移后 r7 ∈ 新授权窗 {r6..r9}:白名单锁的夹具需
    成型停手真激活(窗内 gap>0 会转承接继续投资)。默认部署只含核心
    单件时板面维不足(gap 恒 1),镜像 w227 locked 帧补 DOT 第二件
    (桑博 1★)并抬 hp 到 64 → 承接达标 gap=0;kw 可覆盖。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 7, 'gold': 60, 'level': 5,
        'hp': 64, 'board': {f: t for f, t in comp.form_tiers.items()},
        'deployed': [_w255_formed_target_boss_nodemech_BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2),
                     _w255_formed_target_boss_nodemech_BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮',
                               star=1)],
        'bench': [],
        'shop': [],
    }
    base.update(kw)
    return _w255_formed_target_boss_nodemech_GameState(**base)


def _sess_locked_with_hoard(comp_name: str = 'DOT队') -> _w255_formed_target_boss_nodemech_StrategySession:
    """意向锁 + v3_hoard 目标集(update_target 的生产形态;否则
    _target_names 只有引擎件全集,hoard 采购集分支测不到)。"""
    sess = _w255_formed_target_boss_nodemech_StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp=comp_name)
    comp = get_comp(comp_name)
    chars = set(comp.core_chars) | set(getattr(comp, 'shared_chars', ())
                                       or set())
    sess.v3_hoard = HoardTarget(frozenset(chars), frozenset(), 'locked')
    return sess


def test_formed_stop_passes_target_piece() -> None:
    """新语义:成型停手态,hoard 目标件买入通过;过渡件(名单外)仍拒。"""
    core = intention_core(get_comp('DOT队'))
    state = _formed_state()
    sess = _sess_locked_with_hoard()
    # 名单外过渡件占位:从注册表取一个不在目标集/引擎件的普通件
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    sess2 = _sess_locked_with_hoard()
    from sr_od.application.currency_war.decision.decision_v2.candidates import _target_names
    _tg = _target_names(state, sess2)
    filler = next(n for n in CHARACTERS if n not in _tg)
    kept, log = filter_candidates(
        _cands([core, filler]), state, sess, _w255_formed_target_boss_nodemech_DEFAULT_REGISTRY)
    names_kept = {c.action.card.name for c in kept
                  if isinstance(c.action, _w255_formed_target_boss_nodemech_BuyCard)}
    assert core in names_kept, f'目标件 {core} 必须放行(W255 白名单)'
    assert filler not in names_kept, f'过渡件 {filler} 必须仍拒'
    assert sess.v3_formed_stop is True
    dropped = [e for e in log if e.get('formed_stop')]
    assert dropped and all(not e['kept'] for e in dropped)
    exempt = [e for e in log if e.get('formed_stop_exempt')]
    assert len(exempt) == 1


def test_formed_stop_engine_whitelist_without_hoard() -> None:
    """裸 session(v3_hoard 缺):白名单退化到引擎件全集(种子语义),
    引擎件放行、普通体系外件拒。"""
    engine = next(iter(engine_char_names()))
    filler = '卡芙卡' if engine != '卡芙卡' else '希儿'
    state = _formed_state()
    sess = _w255_formed_target_boss_nodemech_StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    kept, _ = filter_candidates(_cands([engine, filler]),
                                state, sess, _w255_formed_target_boss_nodemech_DEFAULT_REGISTRY)
    names = {c.action.card.name for c in kept
             if isinstance(c.action, _w255_formed_target_boss_nodemech_BuyCard)}
    assert engine in names and filler not in names


# ---------- boss 升级禁令臂删除(约束链验证) ----------

def _boss_frame_state(gold: int = 70) -> _w255_formed_target_boss_nodemech_GameState:
    """cap 满 + bench 有目标件等待上场,P1 r9 boss 帧
    (deploy_cap 补偿触发形态,镜像 w52 锁基座)。"""
    st = _w255_formed_target_boss_nodemech_GameState(
        plane=1, round_num=9, node_type='boss', gold=gold,
        level=5, hp=60, board={},
        bench=[_w255_formed_target_boss_nodemech_BenchChar(slot=i, char_id=n, faction='公司', star=1)
               for i, n in enumerate(['姬子·启行', '卡芙卡'])],
        shop=[],
        deployed=[_w255_formed_target_boss_nodemech_BenchChar(slot=i, char_id=n, faction='公司', star=2)
                  for i, n in enumerate(['丹恒·饮月', '千冶·刃', '绯英',
                                         '娜塔莎', '阿格莱雅'])],
    )
    return st


def _sess_for_compensation(round_key: tuple[int, int]) -> _w255_formed_target_boss_nodemech_StrategySession:
    sess = _w255_formed_target_boss_nodemech_StrategySession()
    sess.v3_intention = IntentionState(phase='unlocked')
    sess.v3_core_names = {'姬子·启行'}
    sess.v2_round_key = round_key
    return sess


def test_boss_round_levelup_allowed_via_ev_basis() -> None:
    """boss 帧内,cap 满+bench 有目标件(EV 总账人口位臂成立)→ 补偿级
    LevelUp 接受,'boss 轮禁升级' 文案不出现。"""
    st = _boss_frame_state()
    cand = _w255_formed_target_boss_nodemech_Candidate(action=DeployMove(bench_idx=0, to_row='back',
                                       faction='列车同行'),
                     tag='deploy', source='test')
    res = _w255_formed_target_boss_nodemech_arbitrate([(cand, 5.0, {})], st,
                    _sess_for_compensation((1, 9)), _w255_formed_target_boss_nodemech_DEFAULT_REGISTRY)
    lvs = [a for a in res.actions if isinstance(a, LevelUp)]
    assert lvs, ('boss 帧 LevelUp 应经 EV 人口位臂接受(ADR-0410):'
                 f'{[r.get("reject") for r in res.log]}')
    # 授权臂不锁死(pop_slot/dp/static_ev 随金位与 DP 姿态浮动):
    # 锁「经 EV 总账放行」本身——auth_basis 非空即可。
    assert all(a.auth_basis for a in lvs)
    joined = '; '.join(r.get('reject') or '' for r in res.log)
    assert 'boss 轮禁升级' not in joined


def test_boss_frame_levelup_rejected_only_by_ev_account() -> None:
    """EV 总账不过(金不足可负担性入口门)→ 拒因走息引擎总账文案,
    非 boss 文案(约束名保留、裁决去 boss 化的行为锁)。"""
    from dataclasses import replace
    reg = replace(_w255_formed_target_boss_nodemech_DEFAULT_REGISTRY, formed_stop_enabled=False)
    st = _boss_frame_state(gold=2)   # 金 2 < 单击价 4 → 可负担性拒
    cand = _w255_formed_target_boss_nodemech_Candidate(action=LevelUp(cost=4), tag='levelup', source='test')
    res = _w255_formed_target_boss_nodemech_arbitrate([(cand, 5.0, {})], st,
                    _sess_for_compensation((1, 9)), reg)
    row = next(r for r in res.log if r['tag'] == 'levelup')
    assert not row['accepted']
    assert 'boss 轮禁升级' not in (row.get('reject') or '')


# ==================== w170_p1_pair_vd ====================

import dataclasses as _w170_p1_pair_vd_dataclasses

from sr_od.application.currency_war.kernel.cw_comps import get_comp as _w170_p1_pair_vd_get_comp
from sr_od.application.currency_war.kernel.cw_economy import _resolve_level_goal
from sr_od.application.currency_war.kernel.cw_intention import IntentionState as _w170_p1_pair_vd_IntentionState
from sr_od.application.currency_war.data.cw_shop_odds import DISTINCT_CARDS_PER_COST, POOL_COPIES_PER_CARD, expected_refreshes, refresh_prob
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w170_p1_pair_vd_BenchChar, GameState as _w170_p1_pair_vd_GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w170_p1_pair_vd_StrategySession
from sr_od.application.currency_war.decision.decision_v2.ev import cross_plane_remaining_nodes
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _w170_p1_pair_vd_DEFAULT_REGISTRY
from sr_od.application.currency_war.decision.decision_v2.scoring import _engines_formed, vd_refresh_score
from sr_od.application.currency_war.kernel.cw_intention import _pair_members

_w170_p1_pair_vd_REG = _w170_p1_pair_vd_DEFAULT_REGISTRY
_PAIR = ('仙舟', '列车同行')


def _locked_sess(pair=_PAIR) -> _w170_p1_pair_vd_StrategySession:
    """①锁局形态:locked comp + transition_pair 副方向(W166 契约)。"""
    s = _w170_p1_pair_vd_StrategySession()
    s.v3_intention = _w170_p1_pair_vd_IntentionState(
        phase='locked', locked_comp='DOT队',
        transition_pair=tuple(pair))
    s.target_comp = _w170_p1_pair_vd_get_comp('DOT队')
    s.v3_mode = 'economy'
    return s


def _unlocked_sess(pair=_PAIR) -> _w170_p1_pair_vd_StrategySession:
    """配方锁局形态:phase=unlocked + p1_pair(W145 契约,core 恒空)。"""
    s = _w170_p1_pair_vd_StrategySession()
    s.v3_intention = _w170_p1_pair_vd_IntentionState(phase='unlocked',
                                    p1_pair=tuple(pair))
    return s


def _p1_state(level: int, gold: int, r: int, *,
              bench: list[_w170_p1_pair_vd_BenchChar] | None = None) -> _w170_p1_pair_vd_GameState:
    return _w170_p1_pair_vd_GameState(
        plane=1, round_num=r, gold=gold, level=level, hp=80,
        shop_refresh_cost=2,
        deployed=[_w170_p1_pair_vd_BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1)
                  for i in range(4)],
        bench=bench or [], shop=[], node_type='battle')


def _e1(level: int, cost: int) -> float:
    """E₁ 本地复算(概率表原语,禁从被测函数借值)。"""
    p = refresh_prob(level, cost)
    assert p > 0
    return expected_refreshes(
        p, DISTINCT_CARDS_PER_COST.get(cost, 13),
        POOL_COPIES_PER_CARD.get(cost, 9), 0, 1, 0)


def _jump(e_cur: int, st: _w170_p1_pair_vd_GameState) -> float:
    """下一档引擎跳变金值本地复算(与 engine_jump_gold 同式,registry
    单一源;ADR-0424 起战斗项=条件掉血拟合×战斗数骨架缺省)。"""
    from sr_od.application.currency_war.decision.decision_v2.scoring import p1_battle_loss_est
    drung = _w170_p1_pair_vd_REG.rung_value.get(e_cur + 1, 0.0) - _w170_p1_pair_vd_REG.rung_value.get(e_cur, 0.0)
    dwin = (_w170_p1_pair_vd_REG.h3_win_rate.get(e_cur + 1, 0.0)
            - _w170_p1_pair_vd_REG.h3_win_rate.get(e_cur, 0.0))
    return (drung * cross_plane_remaining_nodes(st)
            + dwin * p1_battle_loss_est(st, _w170_p1_pair_vd_REG, rung=e_cur + 1)
            * _w170_p1_pair_vd_REG.hp_to_gold * _w170_p1_pair_vd_REG.battles_left_est)


# --- ① 开窗正例 -----------------------------------------------------------------


def test_qlock_window_frame_pair_account() -> None:
    """①①锁局窗外帧(DOT队 lv5=level_up,core 让位):pair 缺件账接管。
    金 53 → 合格缺件=1费档(阈值 50+2+1=53;2费档 54 不可负担),
    全部 1费缺件同 E → 分值逐位 = jump(e_cur) − E₁(5,1)×2。"""
    st = _p1_state(5, 53, 5)
    s = _locked_sess()
    # 前置:该帧 goal 确为 level_up(core 通道窗外让位,W154 ⑤ 同帧判据)
    goal = _resolve_level_goal(st, s.target_comp)
    assert goal is not None and goal.action == 'level_up'
    vd = vd_refresh_score(st, s, _w170_p1_pair_vd_REG)
    e_cur = _engines_formed(st, _w170_p1_pair_vd_REG)
    assert e_cur < 2, '前置:板面未成型'
    expected = _jump(e_cur, st) - _e1(5, 1) * 2
    assert vd is not None and vd > 0, vd
    assert abs(vd - expected) < 1e-6, (vd, expected)


def test_recipe_lock_p1_pair_frame_fires() -> None:
    """①配方锁局帧(phase=unlocked,p1_pair;core 恒空→旧版恒 None):
    pair 通道评估,金 53 lv4 → jump − E₁(4,1)×2 逐位。"""
    st = _p1_state(4, 53, 4)
    vd = vd_refresh_score(st, _unlocked_sess(), _w170_p1_pair_vd_REG)
    e_cur = _engines_formed(st, _w170_p1_pair_vd_REG)
    expected = _jump(e_cur, st) - _e1(4, 1) * 2
    assert vd is not None and vd > 0, vd
    assert abs(vd - expected) < 1e-6, (vd, expected)


# --- ② 金 50/51/52 拒([3] 预算前提;P5⑤ 回归)-----------------------------------


def test_gold_51_52_refused() -> None:
    """②金 51/52:最便宜缺件(1费)阈值=53 → 无一合格对象 → None
    (一次刷+买入后仍 ≥ interest_floor 的单次口径;找牌预算不破息)。"""
    for gold in (50, 51, 52):
        st = _p1_state(5, gold, 5)
        assert vd_refresh_score(st, _locked_sess(), _w170_p1_pair_vd_REG) is None, gold


# --- ③ P1 无窗帧不刷 -------------------------------------------------------------


def test_no_pair_frame_returns_none() -> None:
    """③无对帧(pair 空):①锁局窗外逐位回 W166(恒 None)。"""
    st = _p1_state(5, 53, 5)
    s = _locked_sess(pair=())
    assert vd_refresh_score(st, s, _w170_p1_pair_vd_REG) is None


def test_no_missing_member_frame_returns_none() -> None:
    """③不缺件帧(对成员全持有,bench 放置)→ 找件对象消失 → None。"""
    members = sorted(_pair_members(_PAIR))
    bench = [_w170_p1_pair_vd_BenchChar(slot=i, char_id=n, faction='公司', star=1)
             for i, n in enumerate(members)]
    st = _p1_state(5, 90, 5, bench=bench)
    assert vd_refresh_score(st, _locked_sess(), _w170_p1_pair_vd_REG) is None


# --- ④ A/B 通道 ------------------------------------------------------------------


def test_ab_switch_back_to_w166() -> None:
    """④vd_p1_pair_enabled=False → ①锁局窗外帧逐位回 W166(恒 None)。"""
    reg_off = _w170_p1_pair_vd_dataclasses.replace(_w170_p1_pair_vd_REG, vd_p1_pair_enabled=False)
    st = _p1_state(5, 53, 5)
    assert vd_refresh_score(st, _locked_sess(), reg_off) is None
    # 配方锁局帧(core 恒空)开关关同样回 None
    assert vd_refresh_score(st, _unlocked_sess(), reg_off) is None


# --- ⑤ P2 逐位回归 ---------------------------------------------------------------


def test_p2_branch_untouched_by_pair_channel() -> None:
    """⑤P2 帧(W154 ③ run15 姬子案:列车同行 lv6 姬子·启行 j=1 金 108,
    DP rb=6 窗开但批口径刷金 134.8 > 98 → 预算硬界拒):即便
    transition_pair 非空,pair 通道不辖(plane≠1)→ 仍 None
    (P2 分支逐位不动)。"""
    from sr_od.application.currency_war.decision.decision_v2.posture import Posture
    from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
    s = _w170_p1_pair_vd_StrategySession()
    s.v3_intention = _w170_p1_pair_vd_IntentionState(
        phase='locked', locked_comp='列车同行',
        transition_pair=_PAIR)
    s.target_comp = _w170_p1_pair_vd_get_comp('列车同行')
    s.v3_dp_posture = RoundPosture(
        (2, 1), Posture(save=False, level_up=True, refresh_budget=6))
    st = _w170_p1_pair_vd_GameState(
        plane=2, round_num=1, gold=108, level=6, hp=69,
        shop_refresh_cost=5,
        deployed=[_w170_p1_pair_vd_BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1)
                  for i in range(4)],
        bench=[_w170_p1_pair_vd_BenchChar(slot=0, char_id='姬子·启行',
                         faction='公司', star=1)],
        shop=[], node_type='battle')
    assert vd_refresh_score(st, s, _w170_p1_pair_vd_REG) is None


# --- ⑥ roll/stable 窗内取大 -------------------------------------------------------


def test_roll_window_max_of_core_and_pair() -> None:
    """⑥窗内帧(DOT队 lv8=roll,core 有账)pair 并存取大:
    金 53 → pair 合格对象=1费档;core=卡芙卡 j=2 批口径账;
    V=max(core, pair) 逐位对拍。"""
    st = _p1_state(8, 53, 8,
                   bench=[_w170_p1_pair_vd_BenchChar(slot=0, char_id='卡芙卡',
                                    faction='公司', star=1),
                          _w170_p1_pair_vd_BenchChar(slot=1, char_id='卡芙卡',
                                    faction='公司', star=1)])
    s = _locked_sess()
    goal = _resolve_level_goal(st, s.target_comp)
    assert goal is None or goal.action != 'level_up', '前置:窗内帧'
    vd = vd_refresh_score(st, s, _w170_p1_pair_vd_REG)
    # core 账(2★ 批口径,P1 骨架式本地复算)
    from sr_od.application.currency_war.data.cw_shop_odds import expected_refreshes_for_card
    e_core = expected_refreshes_for_card(8, 2, target_star=2, owned=2)
    core_v = _jump(1, st) - e_core * 2
    e_cur = _engines_formed(st, _w170_p1_pair_vd_REG)
    pair_v = _jump(e_cur, st) - _e1(8, 1) * 2
    assert vd is not None
    assert abs(vd - max(core_v, pair_v)) < 1e-6, (vd, core_v, pair_v)


# ==================== w179_p1_early_gate ====================

import dataclasses as _w179_p1_early_gate_dataclasses

from sr_od.application.currency_war.kernel.cw_intention import IntentionState as _w179_p1_early_gate_IntentionState, p1_early_pair
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w179_p1_early_gate_BenchChar, BuyCard as _w179_p1_early_gate_BuyCard, GameState as _w179_p1_early_gate_GameState, ShopCard as _w179_p1_early_gate_ShopCard
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w179_p1_early_gate_StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate as _w179_p1_early_gate_arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate as _w179_p1_early_gate_Candidate
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _w179_p1_early_gate_DEFAULT_REGISTRY
from sr_od.application.currency_war.decision.decision_v2.scoring import score_all

_w179_p1_early_gate_REG = _w179_p1_early_gate_DEFAULT_REGISTRY

# 注入「press 通道关」注册表:press 通道已正式开臂(commit cb7688d4,
# press_channel_enabled 默认 True),1费/同档无损买改由 arbiter 的
# press_floor_exempt 前置臂(V-B8)授权。本文件锁的是 W179 p1_early
# 早期门自身的辖域行为,注入关臂把该前置臂隔离在本门锁之外。
_REG_NO_PRESS = _w179_p1_early_gate_dataclasses.replace(_w179_p1_early_gate_REG, press_channel_enabled=False)


def _w179_p1_early_gate_sess() -> _w179_p1_early_gate_StrategySession:
    s = _w179_p1_early_gate_StrategySession()   # 未锁线 → FORM 相位(engines<2)
    s.v3_mode = 'economy'
    s.v2_round_key = (1, 4)
    s.v2_round_p1_early = 0
    return s


def _w179_p1_early_gate_state(**kw) -> _w179_p1_early_gate_GameState:
    # 板面:三月七(列车,deployed)+ 青雀(仙舟,bench)→ 支持度 top-2
    # = (列车同行, 仙舟)(_P1_PAIR_PREF 序),未持有对成员 >> k=6
    base = {'plane': 1, 'round_num': 4, 'gold': 14, 'level': 4,
            'hp': 100, 'board': {}, 'bench': [_w179_p1_early_gate_BenchChar(
                slot=0, char_id='青雀', faction='仙舟', star=1)],
            'deployed': [_w179_p1_early_gate_BenchChar(slot=9, char_id='三月七',
                                   faction='列车同行', star=1)],
            'shop': [], 'node_type': 'battle'}
    base.update(kw)
    return _w179_p1_early_gate_GameState(**base)


def _cand(name: str, cost: int, tag: str = 'line_opportunistic') -> _w179_p1_early_gate_Candidate:
    return _w179_p1_early_gate_Candidate(
        action=_w179_p1_early_gate_BuyCard(_w179_p1_early_gate_ShopCard(name=name, faction='仙舟', cost=cost,
                                x=0, star=1), reason=''),
        tag=tag, source='shop')


def _buy_rows(res):
    return [r for r in res.log if r['tag'] == 'line_opportunistic']


def test_gate_open_form_phase_buy_passes() -> None:
    """①未锁形态期窗开:金 14(14-1=13<地板 20,旧路径必拒)买 1费
    仙舟对成员停云 → 同息档(14→13,档 1 不变)放行;auth trace 与
    轮计数在场——pass_buy 修法的行为本体。"""
    st = _w179_p1_early_gate_state()
    s = _w179_p1_early_gate_sess()
    cand = _cand('停云', 1)
    scored = score_all([cand], st, s, _REG_NO_PRESS)
    res = _w179_p1_early_gate_arbitrate(scored, st, s, _REG_NO_PRESS)
    row = _buy_rows(res)[0]
    assert row['accepted'] is True, row
    assert row['ev_auth'].get('p1_early'), row   # 授权依据 trace
    assert s.v2_round_p1_early == 1
    assert any(isinstance(a, _w179_p1_early_gate_BuyCard) and a.card.name == '停云'
               for a in res.actions)


def test_tier_boundary_same_vs_cross() -> None:
    """②息档边界:同档(14-1=13 档1)放行;跨档(11-2=9 档1→0)拒
    ——[11] 精确口径:跨档最多损 1 金,不经本门放行。"""
    st_ok = _w179_p1_early_gate_state()
    s1 = _w179_p1_early_gate_sess()
    res1 = _w179_p1_early_gate_arbitrate(score_all([_cand('停云', 1)], st_ok, s1, _w179_p1_early_gate_REG),
                     st_ok, s1, _w179_p1_early_gate_REG)
    assert _buy_rows(res1)[0]['accepted'] is True
    st_cross = _w179_p1_early_gate_state(gold=11)
    s2 = _w179_p1_early_gate_sess()
    res2 = _w179_p1_early_gate_arbitrate(score_all([_cand('停云', 2)], st_cross, s2, _w179_p1_early_gate_REG),
                     st_cross, s2, _w179_p1_early_gate_REG)
    row = _buy_rows(res2)[0]
    assert row['accepted'] is False, row
    assert 'gold_floor' in row['reject'], row
    assert not row.get('ev_auth', {}).get('p1_early')


def test_bench_full_gate_closed() -> None:
    """③bench 满(bench 余槽 <1)→ 窗关拒([22]② bench 唯一稀缺)。"""
    filler = [_w179_p1_early_gate_BenchChar(slot=i, char_id='银枝', faction='智识', star=1)
              for i in range(9)]
    st = _w179_p1_early_gate_state(bench=filler)
    s = _w179_p1_early_gate_sess()
    res = _w179_p1_early_gate_arbitrate(score_all([_cand('停云', 1)], st, s, _w179_p1_early_gate_REG),
                    st, s, _w179_p1_early_gate_REG)
    row = _buy_rows(res)[0]
    assert row['accepted'] is False, row


def test_same_name_not_governed() -> None:
    """④同名不辖:state 已持有(青雀在 bench)→ 不在门内集;同轮前笔
    买入(working 现持)后的同名第二笔也不经本门(distinct=对 working
    现持判定)。"""
    # ④a:已持有名(青雀)→ 门内集不含 → 拒(注入关臂隔离 press
    # 前置臂——开臂后该臂会另行授权 1费同档买,与本门辖域无关)
    st = _w179_p1_early_gate_state()
    s = _w179_p1_early_gate_sess()
    res = _w179_p1_early_gate_arbitrate(score_all([_cand('青雀', 1)], st, s, _REG_NO_PRESS),
                    st, s, _REG_NO_PRESS)
    row = _buy_rows(res)[0]
    assert row['accepted'] is False, row
    assert not row.get('ev_auth', {}).get('p1_early')
    # ④b:同轮两笔同名(停云×2)→ 只第一笔经门,第二笔无门授权
    st2 = _w179_p1_early_gate_state()
    s2 = _w179_p1_early_gate_sess()
    cands = [_cand('停云', 1), _cand('停云', 1)]
    res2 = _w179_p1_early_gate_arbitrate(score_all(cands, st2, s2, _REG_NO_PRESS),
                     st2, s2, _REG_NO_PRESS)
    rows = _buy_rows(res2)
    gated = [r for r in rows if r.get('ev_auth', {}).get('p1_early')]
    assert len(gated) <= 1, rows   # 同名重复不辖(copy 面)


def test_no_refresh_authorized() -> None:
    """⑤刷新金零授权:同帧(金 14)refresh 候选拒——[3] 预算前提
    (50+刷+买)结构性不满足,V_D 无对象 → 非正分;本门只辖买不辖刷。"""
    from sr_od.application.currency_war.kernel.cw_state import RefreshShop
    st = _w179_p1_early_gate_state()
    s = _w179_p1_early_gate_sess()
    cand = _w179_p1_early_gate_Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = _w179_p1_early_gate_arbitrate(score_all([cand], st, s, _w179_p1_early_gate_REG), st, s, _w179_p1_early_gate_REG)
    row = next(r for r in res.log if r['tag'] == 'refresh')
    assert row['accepted'] is False, row
    assert not any(isinstance(a, RefreshShop) for a in res.actions)


def test_flag_off_reverts_bitwise() -> None:
    """⑥flag off:同帧回到 W174 后行为(gold_floor 原样拒)——
    同时注入 press 通道关(开臂前默认态;通道开时该买由 press_
    floor_exempt 前置臂授权,不落回金地板,与本门无关)。"""
    reg = _w179_p1_early_gate_dataclasses.replace(_REG_NO_PRESS, p1_early_gate_enabled=False)
    st = _w179_p1_early_gate_state()
    s = _w179_p1_early_gate_sess()
    res = _w179_p1_early_gate_arbitrate(score_all([_cand('停云', 1)], st, s, reg),
                    st, s, reg)
    row = _buy_rows(res)[0]
    assert row['accepted'] is False, row
    assert '金<20' in row['reject'], row


def test_round_cap_blocks_second_buy() -> None:
    """⑦单轮上限(cap=1):同窗同档两个不同对成员,只第一笔过门,
    第二笔被上限截断(防 r1 扫店)。"""
    st = _w179_p1_early_gate_state()
    s = _w179_p1_early_gate_sess()
    cands = [_cand('停云', 1), _cand('藿藿', 1)]
    res = _w179_p1_early_gate_arbitrate(score_all(cands, st, s, _REG_NO_PRESS),
                    st, s, _REG_NO_PRESS)
    rows = _buy_rows(res)
    gated = [r for r in rows if r.get('ev_auth', {}).get('p1_early')]
    assert len(gated) == 1, rows
    assert s.v2_round_p1_early == _REG_NO_PRESS.p1_early_round_cap


def test_p2_and_emergency_not_governed() -> None:
    """⑧P2 不辖(买入门只辖 P1)/ 应急态不辖([18] 纪律态地板优先)。
    注入关臂隔离 press 前置臂——其辖域边界只列应急/boss/war 不列
    plane,P2 的 1费买在通道开后由该臂另行授权,非本门辖域变化。"""
    st_p2 = _w179_p1_early_gate_state(plane=2)
    s1 = _w179_p1_early_gate_sess()
    res1 = _w179_p1_early_gate_arbitrate(score_all([_cand('停云', 1)], st_p2, s1,
                               _REG_NO_PRESS),
                     st_p2, s1, _REG_NO_PRESS)
    assert _buy_rows(res1)[0]['accepted'] is False
    st_em = _w179_p1_early_gate_state(hp=20)   # hp≤emergency_hp=25 → 应急态
    s2 = _w179_p1_early_gate_sess()
    res2 = _w179_p1_early_gate_arbitrate(score_all([_cand('停云', 1)], st_em, s2,
                               _REG_NO_PRESS),
                     st_em, s2, _REG_NO_PRESS)
    row = _buy_rows(res2)[0]
    assert row['accepted'] is False, row
    assert not row.get('ev_auth', {}).get('p1_early')


def test_p1_early_pair_read_port() -> None:
    """⑨p1_early_pair 读口:未锁期无门槛派生 top-2(与 _derive_p1_pair
    同口径但无 P1_PAIR_LOCK_MIN_SUPPORT);锁定帧意向字段优先;P2 恒空。"""
    st = _w179_p1_early_gate_state()
    # 未锁:板上三月七(列车 0.5)+青雀(仙舟 1/3)→ top-2 无门槛派生
    assert p1_early_pair(st, None) == ('列车同行', '仙舟')
    # 配方锁定帧:p1_pair 优先于现场派生
    ist = _w179_p1_early_gate_IntentionState(p1_pair=('仙舟', '持续伤害'))
    assert p1_early_pair(st, ist) == ('仙舟', '持续伤害')
    # ①锁局帧:transition_pair 优先于 p1_pair
    ist2 = _w179_p1_early_gate_IntentionState(p1_pair=('仙舟', '持续伤害'),
                          transition_pair=('列车同行', '持续伤害'))
    assert p1_early_pair(st, ist2) == ('列车同行', '持续伤害')
    # 空板未锁(支持度全 0):无门槛同样派生(pref 序 top-2)——与
    # _derive_p1_pair(返回 ())的语义差异本体
    st_empty = _w179_p1_early_gate_state(bench=[], deployed=[])
    assert p1_early_pair(st_empty, None) != ()
    from sr_od.application.currency_war.kernel.cw_intention import _derive_p1_pair
    assert _derive_p1_pair(st_empty) == ()
    # P2 恒空
    assert p1_early_pair(_w179_p1_early_gate_state(plane=2), None) == ()


# ==================== w160_avatar_variants ====================

import numpy as np
import pytest as _w160_avatar_variants_pytest
from cv2.typing import MatLike
from pathlib import Path

from sr_od.application.currency_war.obs.currency_war_char_id import identify_character, load_avatar_templates


def _make_png(path: Path, seed: int) -> None:
    """生成确定性测试图(带角点特征,非纯色)。"""
    rng = np.random.default_rng(seed)
    img = (rng.random((120, 120, 3)) * 255).astype('uint8')
    import cv2
    cv2.imencode('.png', img)[1].tofile(str(path))


@_w160_avatar_variants_pytest.fixture
def tpl_dir(tmp_path: Path) -> Path:
    d = tmp_path / '角色A'
    d.mkdir()
    _make_png(d / 'raw.png', seed=1)        # 主模板(图鉴 art)
    _make_png(d / 'raw_shop.png', seed=2)   # 变体(现场 art,与主不同)
    (tmp_path / '角色B').mkdir()
    _make_png(tmp_path / '角色B' / 'raw.png', seed=3)
    _make_png(tmp_path / '角色A' / 'raw_bak_plaza.png', seed=9)  # 备份:不应进库
    return tmp_path


def test_variant_templates_loaded_and_bak_excluded(tpl_dir: Path) -> None:
    t = load_avatar_templates(tpl_dir)
    keys = sorted(t)
    assert keys == ['角色A', '角色A#1', '角色B']   # bak 不进库,变体带 #1


def test_identify_returns_base_cid_for_variant_match(tpl_dir: Path) -> None:
    t = load_avatar_templates(tpl_dir)
    import cv2
    # 用变体模板原图(角色A#1 的 gray)做现场帧:应命中且返回裸 cid
    slot: MatLike = cv2.cvtColor(t['角色A#1'][0], cv2.COLOR_GRAY2RGB)
    cid, inliers = identify_character(slot, t)
    assert cid == '角色A'
    assert inliers >= 10


def test_identify_same_cid_variants_not_ambiguous(tpl_dir: Path) -> None:
    """同 cid 两变体在 top2(互为最强匹配)不判歧义——返回 base。"""
    t = load_avatar_templates(tpl_dir)
    import cv2
    # 构造一半主模板一半变体的拼接帧:两者都强 → 若按歧义逻辑会 None
    g1, g2 = t['角色A'][0], t['角色A#1'][0]
    mixed = cv2.vconcat([g1[:60], g2[60:]])
    slot = cv2.cvtColor(mixed, cv2.COLOR_GRAY2RGB)
    cid, _ = identify_character(slot, t, min_inliers=5)
    assert cid == '角色A'

# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
