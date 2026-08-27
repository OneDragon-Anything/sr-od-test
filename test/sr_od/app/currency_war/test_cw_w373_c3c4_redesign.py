"""C3/C4 重设计落码批单帧锁(§6.2 锁清单)。

设计=唯一规格:`.debug/temp/currency_war/w373_c3c4_redesign/REDESIGN.md`
§2/§3/§4/§6.2。旧 W354 语义的两处反模式在本批锁死不复发:
- A1-α:濒死帧 LevelUp 被动作类型黑名单无条件滤出(旧语义),而 bench
  蹲着可上件时升级恰是最大 Δp 载体——C3-L1 锁放行;
- A3:rounds_alive 用 ceil(hp/等权均值) 把战斗均摊损失摊到奖励零损轮,
  系统性低估存活——C4-L1/L2 锁投影口径。
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from sr_od.application.currency_war.cw_line_switch import (
    node_loss_kind,
    register_gate_block,
    rounds_alive,
    should_switch_e,
    survival_gate,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.cw_system_cards import engine_char_names
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.filters import (
    filter_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG_DYING = dataclasses.replace(DEFAULT_REGISTRY,
                                 dying_band_account_enabled=True)
_REG_GATE = dataclasses.replace(DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)
#: 两态口径夹具(p_rung=0.65,W346 §3.2 rung2 胜占比量级;空板 rung=0)
_REG_TWO_STATE = dataclasses.replace(
    _REG_GATE, p_win_p2_by_rung={0: 0.65, 1: 0.65, 2: 0.65})

P2_FULL_TABLE = ['battle', 'battle', 'encounter', 'reward',
                 'encounter', 'reward', 'boss']


def _card(name: str, cost: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _unit(slot: int, front: bool) -> BenchChar:
    return BenchChar(slot=slot, char_id=f'件{slot}', faction='仙舟罗浮',
                     star=1, position_pref='front' if front else 'back')


def _state(**kw) -> GameState:
    base = {
        'plane': 2, 'round_num': 1, 'gold': 30, 'level': 5,
        'hp': 20, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _sess(round_num: int = 1,
          table: list[str] | None = None) -> StrategySession:
    s = StrategySession()
    s.plane_node_table = list(table or P2_FULL_TABLE)
    s.plane_node_table_plane = 2
    s.round_num = round_num
    return s


def _cands(target: str, other: str = '散件甲') -> list[Candidate]:
    return [
        Candidate(action=BuyCard(_card(target), reason=''), tag='line_carry',
                  source='shop'),
        Candidate(action=BuyCard(_card(other), reason=''), tag='plugin',
                  source='shop'),
        Candidate(action=LevelUp(cost=4), tag='levelup', source='xp'),
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
        Candidate(action=SellBench(bench_idx=0, income=1, expect=''),
                  tag='for_gold', source='bench'),
        Candidate(action=DeployMove(bench_idx=1, to_row='front',
                                    faction='仙舟罗浮'),
                  tag='deploy', source='fence'),
    ]


def _kept_ids(kept: list[Candidate]) -> set[tuple]:
    out = set()
    for c in kept:
        a = c.action
        name = getattr(getattr(a, 'card', None), 'name', '')
        out.add((c.tag, type(a).__name__, name))
    return out


# --- C3-L1:A1-α 反模式锁(濒死帧 LevelUp 是唯一生存动作) --------------------


def test_c3_l1_levelup_with_deployable_bench_survives() -> None:
    """濒死帧(hp≤下战损)bench 蹲 2 件、空位不足(free=1<2)→ LevelUp
    放行(升完立刻多上 1 件,Δp_board=1);dying_band 日志无 levelup
    删除行——动作类型黑名单反模式(ADR-0302/0303 已修族)不复发。"""
    tgt = sorted(engine_char_names())[0]
    st = _state(level=5, deployed=[_unit(0, True), _unit(1, True),
                                   _unit(2, True), _unit(3, False)],
                bench=[_unit(0, True), _unit(1, False)])
    assert st.max_units() - st.deployed_count() == 1   # 夹具前提:free<bench_n
    kept, flog = filter_candidates(_cands(tgt), st, StrategySession(),
                                   _REG_DYING)
    assert any(isinstance(c.action, LevelUp) for c in kept)
    lv_rows = [e for e in flog if e['tag'] == 'levelup']
    assert lv_rows and all(e['kept'] or e.get('dying_band') != 'levelup'
                           for e in lv_rows)


# --- C3-L2:hoard 买锁 --------------------------------------------------------


def test_c3_l2_hoard_buy_dropped_incl_final_target() -> None:
    """濒死帧无空位(deployed=cap)→ 买候选全删,原因 hoard_buy;
    final 目标件「买而不上」同判([21] 正常囤在濒死帧来不及兑现,
    Δp_board=0,设计内意图显式锁)。"""
    tgt = sorted(engine_char_names())[0]
    st = _state(level=5,
                deployed=[_unit(i, i < 3) for i in range(5)])
    assert st.max_units() - st.deployed_count() == 0   # 夹具前提:无空位
    kept, flog = filter_candidates(_cands(tgt), st, StrategySession(),
                                   _REG_DYING)
    assert not any(isinstance(c.action, BuyCard) for c in kept)
    drops = {e['tag']: e.get('dying_band', '') for e in flog if not e['kept']}
    assert drops.get('line_carry') == 'hoard_buy'
    assert drops.get('plugin') == 'hoard_buy'


# --- C3-L6:买侧合成豁免锁(bench 对子 + 店同名牌 = 即时 2★ 上场) -------------


def test_c3_l6_merge_buy_exempt_from_hoard_drop() -> None:
    """濒死帧无空位(free=0)∧ bench 蹲目标件对子(1★×2)∧ 店有同名牌
    → merge 买候选放行(买第 3 张即合成 2★ 上场,Δp_board>0 的可部署
    性,与 C1 侧判据同款);对照:同帧非合成 hoard 买仍删。"""
    tgt = sorted(engine_char_names())[0]
    st = _state(level=5,
                deployed=[_unit(i, i < 3) for i in range(5)],
                bench=[BenchChar(slot=0, char_id=tgt, faction='仙舟罗浮',
                                 star=1, position_pref='front'),
                       BenchChar(slot=1, char_id=tgt, faction='仙舟罗浮',
                                 star=1, position_pref='front')])
    # 生产形态:merge 标志挂在常规标签买候选上(candidates.py 买侧
    # will_merge_on_buy 标定),synthesize 标签候选不在任何放行标签集,
    # 层1即拦,不涉本判据;独立标签避免与对照买在链日志按 tag 相互覆盖
    merge_buy = Candidate(action=BuyCard(_card(tgt), reason=''),
                          tag='bridge_core', source='shop', merge=True)
    kept, flog = filter_candidates(_cands(tgt) + [merge_buy], st,
                                   StrategySession(), _REG_DYING)
    assert any(isinstance(c.action, BuyCard) and c.merge for c in kept)
    kept_buy_names = [c.action.card.name for c in kept
                      if isinstance(c.action, BuyCard)]
    assert kept_buy_names == [tgt]   # 唯一存活的买=合成买
    drops = {e['tag']: e.get('dying_band', '')
             for e in flog if not e['kept']}
    # 对照:非合成买(无对子可合)同帧仍删
    assert drops.get('line_carry') == 'hoard_buy'
    assert drops.get('plugin') == 'hoard_buy'


# --- C3-L3:可上强件锁(A1-β) ------------------------------------------------


def test_c3_l3_offtarget_playable_buy_survives() -> None:
    """濒死帧有空位∧店有非目标战力件 → 买候选存活——名单不再是放行
    门槛(名单退居评分先验;买谁由 EV 层定价)。"""
    tgt = sorted(engine_char_names())[0]
    st = _state(shop=[_card('散件甲'), _card(tgt)])
    kept, _ = filter_candidates(_cands(tgt), st, StrategySession(),
                                _REG_DYING)
    assert any(isinstance(c.action, BuyCard)
               and c.action.card.name == '散件甲' for c in kept)


# --- C3-L4:盲刷锁 ------------------------------------------------------------


def test_c3_l4_blind_refresh_existence_gate() -> None:
    """危机金(≥40,refresh 解锁)下:店无可买+上件 → refresh 删
    (blind_refresh);店有 → 存活(定向刷新)。"""
    tgt = sorted(engine_char_names())[0]
    sess = StrategySession()
    kept_no, flog = filter_candidates(
        _cands(tgt), _state(gold=45, shop=[_card('无关件乙')]), sess,
        _REG_DYING)
    assert not any(isinstance(c.action, RefreshShop) for c in kept_no)
    assert any(e['tag'] == 'refresh' and
               e.get('dying_band') == 'blind_refresh' for e in flog)
    kept_yes, _ = filter_candidates(
        _cands(tgt), _state(gold=45, shop=[_card(tgt)]), sess, _REG_DYING)
    assert any(isinstance(c.action, RefreshShop) for c in kept_yes)


# --- C3-L5:收窄性质不变量锁 --------------------------------------------------


def test_c3_l5_narrowing_invariant() -> None:
    """纯收窄不变量:濒死带开臂前后,四类动作×(可上/不可上)状态枚举下
    开臂后存活集 ⊆ 开臂前存活集(只删不增,W363 A1 结论固化)。"""
    tgt = sorted(engine_char_names())[0]
    states = []
    for deployed in ([], [_unit(i, i < 3) for i in range(5)]):
        for bench in ([], [_unit(0, True), _unit(1, False)]):
            for shop in ([], [_card(tgt)], [_card('无关件乙')]):
                states.append(_state(deployed=deployed, bench=bench,
                                     shop=shop))
    for st in states:
        before, _ = filter_candidates(_cands(tgt), st, StrategySession(),
                                      DEFAULT_REGISTRY)
        after, _ = filter_candidates(_cands(tgt), st, StrategySession(),
                                     _REG_DYING)
        assert _kept_ids(after) <= _kept_ids(before), \
            f'开臂后存活集必须 ⊆ 开臂前(deployed={len(st.deployed)},'\
            f'bench={len(st.bench)},shop={len(st.shop)})'


# --- C4-L1:投影手算锁(常数口径数表入注释) ----------------------------------


def test_c4_l1_projection_hand_computed() -> None:
    """满表夹具×常数口径(默认表 20.05/16.67/26.71,p 表空),r1 起:
    hp=29:战 8.95→战 −11.1 死 → ra=2;hp=43:22.95→2.9→遭遇 −13.8 死
    → ra=3;hp=60:39.95→19.9→3.2→奖励→遭遇 −13.4 死 → ra=5。"""
    sess = _sess()
    assert rounds_alive(_state(hp=29), sess) == 2
    assert rounds_alive(_state(hp=43), sess) == 3
    assert rounds_alive(_state(hp=60), sess) == 5


# --- C4-L2:奖励零损轮锁 ------------------------------------------------------


def test_c4_l2_reward_front_extends_survival() -> None:
    """同 hp=25、同战斗构成:奖励轮前置的表 ra=3 > 战斗轮前置 ra=2——
    零损日历轮照走(等权除数口径漏算奖励轮的病灶方向锁)。"""
    reward_front = ['reward', 'battle', 'battle', 'encounter',
                    'reward', 'encounter', 'boss']
    battle_front = list(P2_FULL_TABLE)
    ra_r = rounds_alive(_state(hp=25), _sess(table=reward_front))
    ra_b = rounds_alive(_state(hp=25), _sess(table=battle_front))
    assert ra_r == 3 and ra_b == 2 and ra_r > ra_b


# --- C4-L3:未知节点保守锁 ----------------------------------------------------


def test_c4_l3_unknown_node_counts_as_normal_battle() -> None:
    """表含「?」占位 → 按 battle+normal 档计损(hp=20 一场即死 → ra=1,
    未知多算一的一场损失=存活估计更短=门更紧,保守方向声明)。"""
    table = ['?', 'reward', 'encounter', 'reward', 'encounter',
             'reward', 'boss']
    assert node_loss_kind('?') == 'normal'
    assert rounds_alive(_state(hp=20), _sess(table=table)) == 1


# --- C4-L4:缺档零损锁 --------------------------------------------------------


def test_c4_l4_missing_kind_zero_loss_calendar_still_ticks() -> None:
    """line_switch_node_loss 缺 kind → 该轮损 0、轮数照计(与旧实现
    「缺读=normal 最大战斗档」方向相反且各自声明):缺 encounter/boss
    档,hp=1 走完 encounter(0 损)与 boss(0 损)→ ra=2=全表长。"""
    reg = dataclasses.replace(DEFAULT_REGISTRY,
                              line_switch_node_loss={'normal': 20.05})
    sess = _sess(table=['encounter', 'boss'])
    assert rounds_alive(_state(hp=1), sess, reg) == 2


# --- C4-L5:死锁画像双向锁 ----------------------------------------------------


def test_c4_l5_deadlock_frame_both_calibers() -> None:
    """hp=29 + E_cur=inf + E_alt=2 的死锁画像,两行行为各锁:
    常数口径(p 表空,每战全损)→ ra=2 < need → 拦(理由 survival);
    两态口径(p_rung=0.65 注入,板强通道进投影)→ ra=7 ≥ need → 放行
    (「强板换线能活到兑现」由胜率通道可达,REDESIGN §3.6 数表)。"""
    sess = _sess()
    st = _state(hp=29)
    do, _ = should_switch_e(math.inf, 2.0, 2, DEFAULT_REGISTRY)
    assert do, '夹具前提:E_cur=inf 时主判据放行'
    ok, why = survival_gate(st, sess, 2.0, _REG_GATE)
    assert not ok and why.startswith('survival(')
    ok2, why2 = survival_gate(st, sess, 2.0, _REG_TWO_STATE)
    assert ok2 and why2 == 'ok', f'两态口径必须放行(实得 {why2})'
    assert rounds_alive(st, sess, _REG_TWO_STATE) == 7


# --- C4-L6:去重锁 ------------------------------------------------------------


def test_c4_l6_gate_block_log_dedup() -> None:
    """同线对二次拦截不重复发日志:计数累加(1→2→3),换线对重新计数
    (消费侧约定=次数 1 发日志行,>1 只累加)。"""
    sess = StrategySession()
    assert register_gate_block(sess, '甲线', '乙线') == 1
    assert register_gate_block(sess, '甲线', '乙线') == 2
    assert register_gate_block(sess, '甲线', '乙线') == 3
    assert register_gate_block(sess, '甲线', '丙线') == 1


# --- 标-L1:标定双源锁(口径语义固化在夹具语料上) ----------------------------


def _frame_losses(rows: list[dict]) -> dict[str, list[float]]:
    """标定脚本源 A 同口径(相邻战斗类行差分;hp_after=0 死亡行按
    hp_before 全额;hp≤1 不删失;不按置信度过滤;净负记 0 损)。"""
    BK = {'普通战斗': 'normal', '遭遇': 'encounter', 'boss': 'boss'}
    by_run: dict[str, list[dict]] = {}
    for r in rows:
        by_run.setdefault(r['run_id'], []).append(r)
    buckets: dict[str, list[float]] = {}
    for seq in by_run.values():
        seq = sorted(seq, key=lambda r: (r['plane'], r['round_num']))
        pb = [r for r in seq if r['plane'] == 2
              and r.get('node_type') in BK]
        for prev, cur in zip(pb, pb[1:], strict=False):
            a, b = prev.get('hp_after'), cur.get('hp_after')
            if a is None or b is None:
                continue
            loss = float(a) if b <= 0 else max(0.0, float(a) - float(b))
            buckets.setdefault(BK[cur['node_type']], []).append(loss)
    return buckets


def test_std_l1_dual_source_calibration_semantics() -> None:
    """标定口径三要素(死亡行全额入桶修反保守/hp≤1 入桶/置信=0 行入桶):
    夹具语料上帧级桶必须含死亡事件全额 30、hp=1 行前差 19;双源互校
    判据=帧级合并均值必须落在 run 级 CI 内,出界即 raise(红旗)。"""
    rows = [
        # run A:战斗 40 → 奖励 45(回血)→ 战斗 30 → boss 死(hp 0,置信 0)
        {'run_id': 'A', 'plane': 2, 'round_num': 1, 'node_type': '普通战斗',
         'hp_after': 40, 'hp_confidence': 1.0},
        {'run_id': 'A', 'plane': 2, 'round_num': 2, 'node_type': '奖励',
         'hp_after': 45, 'hp_confidence': 1.0},
        {'run_id': 'A', 'plane': 2, 'round_num': 3, 'node_type': '普通战斗',
         'hp_after': 30, 'hp_confidence': 1.0},
        {'run_id': 'A', 'plane': 2, 'round_num': 4, 'node_type': 'boss',
         'hp_after': 0, 'hp_confidence': 0.0},
        # run B:战斗 20 → 战斗 1(hp=1 非死亡,不删失)
        {'run_id': 'B', 'plane': 2, 'round_num': 1, 'node_type': '普通战斗',
         'hp_after': 20, 'hp_confidence': 1.0},
        {'run_id': 'B', 'plane': 2, 'round_num': 2, 'node_type': '普通战斗',
         'hp_after': 1, 'hp_confidence': 1.0},
    ]
    buckets = _frame_losses(rows)
    assert buckets['boss'] == [30.0], '死亡行必须按 hp_before 全额入桶'
    assert buckets['normal'] == [10.0, 19.0], (
        '跨奖励回血的战斗差分=10,hp=1 行前差 19 必须入桶(不删失)')
    # 互校判据:帧级均值 19.67 ∉ run 级 CI [10,11] → raise
    frame_mean = (sum(buckets['normal']) + sum(buckets['boss'])) / 3
    run_ci = (10.0, 11.0)
    with pytest.raises(SystemExit):
        if not (run_ci[0] <= frame_mean <= run_ci[1]):
            raise SystemExit('标定红旗:帧级均值 ∉ run 级 CI')


# --- 兜-L1:零漂移锁 ----------------------------------------------------------


def test_zero_drift_default_off_chain() -> None:
    """双开关默认关:registry 缺省下濒死判据恒 False、门恒放行——
    decide 全链与基线逐位一致的结构前提(registry hash 锁另辖字段面)。"""
    assert DEFAULT_REGISTRY.dying_band_account_enabled is False
    assert DEFAULT_REGISTRY.line_switch_survival_gate_enabled is False
    st = _state(hp=20)
    assert not DEFAULT_REGISTRY.dying_band_account_enabled and \
        survival_gate(st, _sess(), 99.0, DEFAULT_REGISTRY)[0] is True
