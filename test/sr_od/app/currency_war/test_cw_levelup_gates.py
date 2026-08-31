# -*- coding: utf-8 -*-
"""test_cw_levelup_gates 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w131_buy_ev_gate: test_cw_w131_buy_ev_gate.py
- w131_levelup_auth_gate: test_cw_w131_levelup_auth_gate.py
- w652_p4_fixes: test_cw_w652_p4_fixes.py
- w373_c3c4_redesign: test_cw_w373_c3c4_redesign.py
- r412_levelup_cost_flat4: test_cw_r412_levelup_cost_flat4.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w131_buy_ev_gate ====================

from sr_od.application.currency_war.kernel.cw_state import BenchChar, BuyCard, GameState, ShopCard
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.ev import cross_plane_remaining_nodes, interest_cost
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.decision.decision_v2.scoring import engine_jump_gold, formation_gold_account, score_candidate

_REG = DEFAULT_REGISTRY


def _sess() -> StrategySession:
    s = StrategySession()   # 未锁线 → FORM 相位
    s.v3_mode = 'economy'
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 52, 'level': 5,
            'hp': 100, 'board': {}, 'bench': [], 'shop': [],
            'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


def _cand(name: str, cost: int, tag: str = 'bond_fallback') -> Candidate:
    return Candidate(
        action=BuyCard(ShopCard(name=name, faction='公司', cost=cost,
                                x=0, star=1), reason=''),
        tag=tag, source='shop')


# --- ① 量纲断言(两口径表值对拍)----------------------------------------------


def test_dimension_assertions() -> None:
    """①engine_jump_gold 与 interest_cost 的量纲/口径断言:
    - jump(e)=Δrung×R + Δwin×掉血×HP金价×剩余战斗(registry 单一源);
    - 买侧 C=档数×min(R, interest_recovery_rounds);默认口径(刷新)
      =档数×R(平面 R 上界,P5⑤ 逐位保留);
    - e≥2 封顶档无跳变。"""
    st = _state()
    r = cross_plane_remaining_nodes(st)
    assert r >= 10, '前置:跨位面 R 量级(P1 中段 ≈20+)'
    from sr_od.application.currency_war.decision.decision_v2.scoring import p1_battle_loss_est
    dwin01 = _REG.h3_win_rate[1] - _REG.h3_win_rate[0]
    dwin12 = _REG.h3_win_rate[2] - _REG.h3_win_rate[1]
    # ADR-0425:战斗项=条件掉血拟合(成型后档)×战斗数(裸 session
    # 无槽序表 → registry 骨架缺省)
    assert abs(engine_jump_gold(0, st, _REG)
               - (_REG.rung_value[1] * r
                  + dwin01 * p1_battle_loss_est(st, _REG, rung=1)
                  * _REG.hp_to_gold * _REG.battles_left_est)) < 1e-6
    assert abs(engine_jump_gold(1, st, _REG)
               - ((_REG.rung_value[2] - _REG.rung_value[1]) * r
                  + dwin12 * p1_battle_loss_est(st, _REG, rung=2)
                  * _REG.hp_to_gold * _REG.battles_left_est)) < 1e-6
    assert engine_jump_gold(2, st, _REG) == 0.0
    # C 两口径:52→48 跨 1 档
    assert interest_cost(52, 4, st) == float(r)          # 默认=平面 R 上界
    assert interest_cost(
        52, 4, st,
        recovery_rounds=_REG.interest_recovery_rounds) \
        == _REG.interest_recovery_rounds    # 买侧折中(min(R,3)=3)
    assert interest_cost(52, 2, st) == 0.0  # 同档([11] 特例前置)


# --- ② 买侧放行帧(进度份额计值,W123 恒拒面的主修复位)-----------------------


def test_engine_progress_buy_passes_gate() -> None:
    """②金 52 买 4 费仙舟进度件(板上青雀 1/3 → 2/3):跨 50 档
    (52→48)EV 账 V=组合跳变份额(Δprogress×jump(0),R 视界)> C
    (回档折中 3)→ 放行,ev_auth trace 在场。W131 前该帧 V≈层3 分
    (~1)vs C=R(20+)恒拒——买侧放行面的修复本体。"""
    st = _state(deployed=[BenchChar(slot=9, char_id='青雀',
                                    faction='仙舟罗浮', star=1)])
    s = _sess()
    cand = _cand('停云', 4)
    val, bd = score_candidate(cand, st, s, _REG)
    # 量纲断言:form_gold = Δprogress × jump(0)(deployed 域权重 1.0)
    from sr_od.application.currency_war.decision.decision_v2.scoring import _engine_frac_remainder
    from sr_od.application.currency_war.kernel.cw_state import simulate
    after = simulate(st, cand.action)
    from sr_od.application.currency_war.decision.decision_v2.scoring import _deploy_pipeline
    _deploy_pipeline(after, s)
    d_rem = (_engine_frac_remainder(after, _REG)
             - _engine_frac_remainder(st, _REG))
    expect = d_rem * engine_jump_gold(0, st, _REG)
    assert d_rem > 0, '前置:进度件推高小数余量'
    assert abs(bd['form_gold'] - round(expect, 3)) < 0.01, bd
    assert bd['form_gold'] > _REG.interest_recovery_rounds, \
        '前置:份额金值 > 买侧 C(否则非本锁辖域帧)'
    # 端到端:跨档买放行 + ev_auth trace
    res = arbitrate([(cand, val, bd)], st, s, _REG)
    row = next(r for r in res.log if r['tag'] == cand.tag)
    assert row['accepted'] is True, row
    assert row['ev_auth']['ev_auth'] > 0, row
    assert any(isinstance(a, BuyCard) for a in res.actions)


# --- ③ 真拒绝帧(无完成度贡献的填充件)----------------------------------------


def test_filler_buy_still_rejected() -> None:
    """③同帧买无完成度贡献的填充件(form_gold=0,V=注入小值 1):
    EV=1−3<0 → 拒(「EV≤0 破息拒」)——标定打开的是**有完成度
    价值的买**,门对纯填充仍关(门语义保留,非门全开)。"""
    st = _state(deployed=[BenchChar(slot=9, char_id='青雀',
                                    faction='仙舟罗浮', star=1)])
    s = _sess()
    cand = _cand('公司杂件', 4)
    from sr_od.application.currency_war.kernel.cw_state import simulate
    after = simulate(st, cand.action)
    assert formation_gold_account(st, after, _REG) == 0.0, \
        '前置:非过渡体系件零组合跳变贡献'
    res = arbitrate([(cand, 1.0, {'int_emb': 0.0})], st, s, _REG)
    row = next(r for r in res.log if r['tag'] == cand.tag)
    assert row['accepted'] is False, row
    assert 'EV≤0 破息拒' in (row['reject'] or ''), row


# --- ④ 组合跳变帧(买入即跨整数引擎档)----------------------------------------


def test_engine_completion_buy_full_jump() -> None:
    """④板上桑博(持续伤害 1/2)买第二件(卡芙卡,合成 4 费跨档):
    apply 后整数引擎 0→1 → form_gold=该级**全额**跳变金(jump(0),
    与 vd_refresh_score 收益侧同式同源)——买件对完成度的贡献按
    组合跳变计,不是单件散分(W126 D 侧同思路的买侧对偶)。"""
    st = _state(deployed=[BenchChar(slot=9, char_id='桑博',
                                    faction='仙舟罗浮', star=1)])
    s = _sess()
    cand = _cand('卡芙卡', 4)
    val, bd = score_candidate(cand, st, s, _REG)
    expect = engine_jump_gold(0, st, _REG)
    assert abs(bd['form_gold'] - round(expect, 3)) < 0.01, bd
    assert bd['form_gold'] > engine_jump_gold(0, st, _REG) * 0.99
    res = arbitrate([(cand, val, bd)], st, s, _REG)
    row = next(r for r in res.log if r['tag'] == cand.tag)
    assert row['accepted'] is True, row
    assert row['ev_auth'] and row['ev_auth']['ev_auth'] > 0, row


# --- ⑤ 跨档触发形状(50-51 金买 2-3 费;W135 交叉验证验收位)-------------


def test_cross_tier_50_51_buy_2_3_cost() -> None:
    """⑤金 50/51 买 2/3 费引擎进度件(跨 1 档;run14「金 51 整轮零买」
    的实机触发形状):新口径 C=1 档×min(R,interest_recovery_rounds)=3
    (vs 旧口径 20-23)→ 份额金值 > 3 → 放行;同帧按旧口径(V=层3 分
    剥离息,无 form_gold;C=平面 R 上界 1×R≈20+)→ 拒——单帧证明门
    真开了(sim 零差因该 seed 集此形状候选仅 3 个,分布观测功效不足,
    见 W131 报告 §3)。"""
    for gold, cost in ((50, 2), (51, 2), (51, 3), (50, 3)):
        st = _state(gold=gold,
                    deployed=[BenchChar(slot=9, char_id='青雀',
                                        faction='仙舟罗浮', star=1)])
        s = _sess()
        cand = _cand('停云', cost)
        val, bd = score_candidate(cand, st, s, _REG)
        assert bd['form_gold'] > _REG.interest_recovery_rounds, (
            gold, cost, bd['form_gold'])
        res = arbitrate([(cand, val, bd)], st, s, _REG)
        row = next(r for r in res.log if r['tag'] == cand.tag)
        assert row['accepted'] is True, (gold, cost, row)
        assert row['ev_auth'] and row['ev_auth']['ev_auth'] > 0, row
        # 对照(旧口径语义):同帧 V=层3 分剥离息分量(减去 form_gold
        # 注入)、C=平面 R 上界(interest_cost 默认口径=1×R≈20+)
        assert interest_cost(gold, cost, st) \
            >= cross_plane_remaining_nodes(st)
        res_old = arbitrate(
            [(cand, round(val - bd['form_gold'], 4),
              {'int_emb': bd['int_emb']})], st, s, _REG)
        row_old = next(r for r in res_old.log if r['tag'] == cand.tag)
        assert row_old['accepted'] is False, (gold, cost, row_old)
        assert ('EV≤0 破息拒' in (row_old['reject'] or '')
                or '非正分' in (row_old['reject'] or '')), row_old


# ==================== w131_levelup_auth_gate ====================

# 检查器判据重定义批(ADR-0353):levelup_interest_engine_gate
# 改读授权依据(旧「金<50 且未曾满息」判据把 [33] 人口位合法 <50 升级
# 全数计违规——§5.3.3 实测 378 违规绝大多数为合法面,后 206)。
#
# 锁面(双向,检查器非安慰剂):
# 1. 合法授权升级(pop_slot/dp)0 违规——重定义的放行面;
# 2. 无依据升级('')/static_ev 估值账放行的 <50 升级涌现违规——去门
#    变异必须被杀(授权依据缺失时检查器不失明);
# 3. 旧判据面保留:lv<5 不报、时点金 ≥50 不报;
# 4. 账本接线:sim 账本 LevelUp 行带 auth 键(观测字段端到端落地),
#    真实批 rows 过检查器 0 违规(合法面;static_ev 残量见 sim 冒测)。
import json
from pathlib import Path

from sr_od.application.currency_war.sim.checks import ledger as chk

from sr_od.application.currency_war.sim.runner import simulate_p1_batch


def _row(round_num: int, gold0: int, level: int, auths: list[str]) -> dict:
    """构造单轮账本行(shop_waves 首波金=时点金;actions=LevelUp 组)。"""
    return {
        'plane': 1,
        'round_num': round_num,
        'gold': max(0, gold0 - 4 * len(auths)),
        'actions': [{'__type__': 'LevelUp', 'cost': 4, 'auth': a}
                    for a in auths],
        'sim': {'shop_waves': [{'gold': gold0}]},
        'state': {'level': level},
    }


def test_authorized_levelup_zero_violation() -> None:
    """合法授权升级 0 违规:pop_slot([33] 人口位)与 dp(DP 花费授权)
    的 lv≥5 时点金<50 升级是重定义后的放行面(旧判据误计违规的主体)。"""
    rows = [
        _row(4, 30, 5, ['pop_slot', 'pop_slot']),   # 多击整组
        _row(6, 12, 6, ['dp']),
        _row(7, 45, 7, ['pop_slot']),
    ]
    assert chk.check_levelup_interest_engine_gate(rows) == []


def test_unauthorized_levelup_emerges_violation() -> None:
    """无授权依据的 <50 升级必须涌现违规(去门变异可杀)。

    - auth=''(default 栈旧调用/未过账路径)→ 违规且消息标「无授权依据」;
    - ADR-0410 起 static_ev 并入合法面(旧断言「static_ev 计违规」
      随语义过期——boss 升级禁令删除后该臂是末窗升级主授权臂,「帧量级 0-1 保守计违规」的校准前提已失效);无授权依据检测面
      (auth 空/缺失)保留,检查器对授权观测缺失不失明。"""
    # prev_level 语义:检查器用上一轮账本 level 判追级段(首轮 prev=3)
    # ——先放一行 lv5 铺底,违规落在第二行。
    _pre = _row(4, 60, 5, [])
    rows_no_basis = [_pre, _row(5, 30, 6, [''])]
    v1 = chk.check_levelup_interest_engine_gate(rows_no_basis)
    assert len(v1) == 1 and '无授权依据' in v1[0], v1

    # 旧 auth 键整体缺失(旧账本形态)等同无依据
    row = _row(5, 30, 6, ['pop_slot'])
    del row['actions'][0]['auth']
    v3 = chk.check_levelup_interest_engine_gate([_pre, row])
    assert len(v3) == 1, 'auth 键缺失必须计违规(授权不可默认成立)'


def test_old_criterion_surface_kept() -> None:
    """旧判据的非违规面保留:lv<5(r263 过渡宽松段)与时点金≥50 不报。"""
    assert chk.check_levelup_interest_engine_gate(
        [_row(3, 20, 4, [''])]) == []          # lv<5(首轮 prev=3)
    assert chk.check_levelup_interest_engine_gate(
        [_row(6, 55, 6, [''])]) == []          # 时点金 ≥50(息平台在场)
    # P1 外位面不辖
    row = _row(5, 30, 6, [''])
    row['plane'] = 2
    assert chk.check_levelup_interest_engine_gate([row]) == []


def test_ledger_auth_key_wired(tmp_path: Path) -> None:
    """账本接线锁:sim 账本 LevelUp 行带 auth 键(观测字段端到端落地),
    真实批 rows 过新判据检查器——授权升级不误报。"""
    rep = simulate_p1_batch(5, pool='fallback', seed_base=0,
                            ledger=tmp_path / 'auth')
    d = Path(rep['ledger_dir'])
    n_lv = 0
    arms: set[str] = set()
    for name in ('decisions.jsonl', 'outcomes.jsonl'):
        f = d / name
        if not f.exists():
            continue
        for ln in f.read_text(encoding='utf-8').splitlines():
            row = json.loads(ln)
            for a in row.get('actions') or []:
                if a.get('__type__') == 'LevelUp':
                    assert 'auth' in a, \
                        f'LevelUp 账本行缺 auth 键(观测字段断链):{a}'
                    assert a['auth'] in ('', 'pop_slot', 'dp',
                                         'static_ev'), a
                    n_lv += 1
                    arms.add(a['auth'])
    assert n_lv > 0, '5 局零 LevelUp:接线锁样本不足(换 seed_base)'
    # 真实批 rows(检查器消费的行流)过新判据:合法授权面(pop_slot/dp/
    # static_ev)不误报。
    rows = [json.loads(ln) for ln in
            (d / 'outcomes.jsonl').read_text(encoding='utf-8').splitlines()]
    v = chk.check_levelup_interest_engine_gate(rows)
    for line in v:
        assert '无授权依据' not in line, \
            f'真实批涌现无授权依据升级(接线断裂或真违规):{line}'




# ==================== w652_p4_fixes ====================

from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim.checks import ledger as _led, segments as _seg
from sr_od.application.currency_war.sim.checks import runner as _rn
from sr_od.application.currency_war.kernel.cw_state import GameState as _w652_p4_fixes_GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w652_p4_fixes_StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import generate_candidates
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _w652_p4_fixes_DEFAULT_REGISTRY

# --- ② 满级升级空转门 --------------------------------------------------------


def _state_at(level: int, **kw) -> _w652_p4_fixes_GameState:
    base = {'plane': 1, 'round_num': 6, 'gold': 80, 'level': level,
            'board': {'仙舟罗浮': 1}, 'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return _w652_p4_fixes_GameState(**base)


def test_sim_registry_aligns_exec_cap() -> None:
    """sim 视图注册表 level_max == 执行层 LEVEL_CAP(单一尺);
    实机真值 DEFAULT_REGISTRY.level_max 保持 10 不漂移。"""
    assert cw_sim.LEVEL_CAP == 9
    reg = cw_sim.sim_decision_registry()
    assert reg.level_max == cw_sim.LEVEL_CAP
    assert _w652_p4_fixes_DEFAULT_REGISTRY.level_max == 10


def test_levelup_candidate_absent_at_sim_cap_frame() -> None:
    """满级帧(sim 语义 lv9)候选零升级:决策层前置拦住,执行层
    拒付层不再被空转触发(穿透锁:接线前该帧有 LevelUp 候选 →
    每帧发起到被拒)。"""
    sess = _w652_p4_fixes_StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    st = _state_at(cw_sim.LEVEL_CAP)
    cands = generate_candidates(st, sess, cw_sim.sim_decision_registry())
    assert not [c for c in cands
                if c.action.__class__.__name__ == 'LevelUp']


def test_levelup_candidate_still_valid_below_live_cap() -> None:
    """防矫枉过正:实机语义下 lv9 是正常付费升级档(live 满级 = 10),
    用 DEFAULT_REGISTRY 时 lv9 帧仍生成 LevelUp 候选——sim 建模分歧
    不得倒灌实机行为。"""
    sess = _w652_p4_fixes_StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    st = _state_at(9)
    cands = generate_candidates(st, sess, _w652_p4_fixes_DEFAULT_REGISTRY)
    assert [c for c in cands if c.action.__class__.__name__ == 'LevelUp']


# --- ① 破息例外记账 ----------------------------------------------------------


def _break_row(round_num: int, g0: int, g1: int, node: str,
               spend: dict, actions: list[dict]) -> dict:
    return {'plane': 1, 'round_num': round_num, 'gold': g1, 'hp': 80,
            'sim': {'node': node, 'delta': 1, 'spend': spend,
                    'shop_waves': [{'event': 'offer', 'gold': g0,
                                    'cards': []}]},
            'actions': actions}


def test_levelup_driven_break_not_flagged() -> None:
    """追级经验通道破息 = 授权通道表征(ev.levelup_ev_basis 单一源),
    不进「无例外」红(穿透锁:收编前该形态红,是基线噪声主体)。"""
    rows = [_break_row(7, 52, 19, 'encounter',
                       {'buys': {}, 'levelup': 32, 'refresh': 0,
                        'sell_income': 0},
                       [{'__type__': 'LevelUp', 'cost': 4, 'auth': ''}])]
    assert _seg.seg_check_break_interest_exception(rows) == []


def test_refresh_driven_break_not_flagged() -> None:
    """刷新找牌通道破息(refresh_ev_budget / M-A 预算授权面)同上。"""
    rows = [_break_row(9, 67, 45, 'boss',
                       {'buys': {}, 'levelup': 0, 'refresh': 6,
                        'sell_income': 0},
                       [{'__type__': 'RefreshShop', 'cost': 2}] * 3)]
    assert _seg.seg_check_break_interest_exception(rows) == []


def test_unexplained_buy_break_still_flagged_with_breakdown() -> None:
    """真无例外破息(单笔非店全想要买件,无升级/刷新/连胜)仍红,
    且事件带花费分解(升级/刷新/买件,归因不看人工)。"""
    rows = [_break_row(5, 60, 40, 'encounter',
                       {'buys': {'engine': 20}, 'levelup': 0,
                        'refresh': 0, 'sell_income': 0},
                       [{'__type__': 'BuyCard',
                         'card': {'name': '某件', 'cost': 20,
                                  'faction': '仙舟罗浮'},
                         'reason': 'engine', 'channel': 'engine'}])]
    ev = _seg.seg_check_break_interest_exception(rows)
    assert len(ev) == 1
    assert ev[0]['spend_breakdown'] == {'levelup': 0, 'refresh': 0,
                                        'buys': {'engine': 20}}


# --- ③ 刷新预算帽双检查 --------------------------------------------------------


def _refresh_rows(counts: list[tuple[int, int]],
                  dir_counts: list[int] | None = None) -> list[dict]:
    """counts = (round_num, 该轮 RefreshShop 数);dir_counts 可选给定。"""
    dir_counts = dir_counts or [0] * len(counts)
    out: list[dict] = []
    for (rn, n), d in zip(counts, dir_counts, strict=True):
        out.append({
            'plane': 1, 'round_num': rn, 'gold': 40, 'hp': 80,
            'sim': {'node': 'encounter', 'dir_refreshes': d,
                    'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                              'sell_income': 0}},
            'actions': [{'__type__': 'RefreshShop', 'cost': 2}] * n,
        })
    return out


def test_refresh_roll_cap_discloses_ordinary_over_cap() -> None:
    """普通车道 7 刷/轮 > REFRESH_ROLL_CAP(6)→ 披露 frames_over_cap
    (变异注入形态:7 连刷此前零检查命中;披露型不作归零锁——逐段
    重决策语义下账本轮级不可判,语义见检查 docstring)。"""
    rep = _led.check_refresh_roll_cap_frame([_refresh_rows([(6, 7)])])
    assert rep['violations'] == 0
    assert rep['frames_over_cap'] == 1
    assert rep['max_ordinary_per_round'] == 7


def test_refresh_roll_cap_deducts_directed_lane() -> None:
    """6 普通刷新 + 2 定向 = 8/轮 不计越帽:定向车道有自身授权面
    (per_round 上限),不得计入普通车道帽。"""
    rep = _led.check_refresh_roll_cap_frame(
        [_refresh_rows([(8, 8)], [2])])
    assert rep['frames_over_cap'] == 0
    assert rep['max_ordinary_per_round'] == 6


def test_directed_refresh_game_cap_lock() -> None:
    """定向车道全局 7 次 > 局帽 6(directed_refresh_game_cap)→ 违规;
    帽内(≤6)恒绿。"""
    assert len(_led.check_directed_refresh_game_cap(
        _refresh_rows([(7, 2), (8, 2), (9, 1), (5, 2)], [2, 2, 1, 2]))) == 1
    assert _led.check_directed_refresh_game_cap(
        _refresh_rows([(8, 2), (9, 2)], [2, 2])) == []


def test_refresh_cap_checks_wired() -> None:
    """两检查项接线到位:硬锁在批检查表(run_checks_on_ledgers 自动
    扫),披露项在批级聚合入口(遗漏接线 = 检查静默失明)。"""
    assert 'directed_refresh_game_cap_lock' in _rn._BATCH_CHECKS
    # 批级披露经 run_batch_level_checks 汇出(以注册名为键)
    rep = _rn.run_batch_level_checks(
        [[{'plane': 1, 'round_num': 1, 'gold': 40, 'hp': 80,
           'sim': {'node': 'encounter', 'dir_refreshes': 0,
                   'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                             'sell_income': 0}},
           'actions': []}]])
    assert 'refresh_roll_cap_frame' in rep
    assert rep['refresh_roll_cap_frame']['violations'] == 0


# --- 语义快照:默认策略构造走 sim 视图(接线单一址生效) -----------------------


def test_default_simulate_strategy_uses_sim_registry() -> None:
    """simulate_p1 默认策略的 registry.level_max == LEVEL_CAP
    (注入自定义 strategy 的调用方不受影响)。"""
    from sr_od.application.currency_war.decision.decision_v2.strategy import DecisionV2Strategy
    strat = DecisionV2Strategy(registry=cw_sim.sim_decision_registry())
    assert strat.registry.level_max == cw_sim.LEVEL_CAP








# ==================== w373_c3c4_redesign ====================

import dataclasses
import math

import pytest

from sr_od.application.currency_war.kernel.cw_line_switch import node_loss_kind, register_gate_block, rounds_alive, should_switch_e, survival_gate
from sr_od.application.currency_war.kernel.cw_state import GameState as _w373_c3c4_redesign_GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w373_c3c4_redesign_StrategySession
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _w373_c3c4_redesign_DEFAULT_REGISTRY

_REG_GATE = dataclasses.replace(_w373_c3c4_redesign_DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)
#: 两态口径夹具(p_rung=0.65,W346 §3.2 rung2 胜占比量级;空板 rung=0;
#: rounds_two_state_enabled=True——两态通道总开关,默认关=零漂移锚)
_REG_TWO_STATE = dataclasses.replace(
    _REG_GATE, rounds_two_state_enabled=True,
    p_win_p2_by_rung={0: 0.65, 1: 0.65, 2: 0.65})

P2_FULL_TABLE = ['battle', 'battle', 'encounter', 'reward',
                 'encounter', 'reward', 'boss']


def _w373_c3c4_redesign_state(**kw) -> _w373_c3c4_redesign_GameState:
    base = {
        'plane': 2, 'round_num': 1, 'gold': 30, 'level': 5,
        'hp': 20, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return _w373_c3c4_redesign_GameState(**base)


def _w373_c3c4_redesign_sess(round_num: int = 1,
          table: list[str] | None = None) -> _w373_c3c4_redesign_StrategySession:
    s = _w373_c3c4_redesign_StrategySession()
    s.plane_node_table = list(table or P2_FULL_TABLE)
    s.plane_node_table_plane = 2
    s.round_num = round_num
    return s


# --- C4-L1:投影手算锁(常数口径数表入注释) ----------------------------------


def test_c4_l1_projection_hand_computed() -> None:
    """满表夹具×常数口径(W443 后幅度源=p2_cond_loss_table 条件败面档
    12.77/13.33/15.50,p 表空),r1 起:
    hp=29:12.77→16.23→12.77→3.46→遭遇 13.33 死 → ra=3;hp=43:
    30.23→17.46→4.13→奖励→遭遇死 → ra=5;hp=60:…→奖励→7.8→奖励→
    boss 15.5 死 → ra=7。"""
    sess = _w373_c3c4_redesign_sess()
    assert rounds_alive(_w373_c3c4_redesign_state(hp=29), sess) == 3
    assert rounds_alive(_w373_c3c4_redesign_state(hp=43), sess) == 5
    assert rounds_alive(_w373_c3c4_redesign_state(hp=60), sess) == 7


# --- C4-L2:奖励零损轮锁 ------------------------------------------------------


def test_c4_l2_reward_front_extends_survival() -> None:
    """同 hp=25、同战斗构成:奖励轮前置的表 ra=3 > 战斗轮前置 ra=2——
    零损日历轮照走(等权除数口径漏算奖励轮的病灶方向锁)。"""
    reward_front = ['reward', 'battle', 'battle', 'encounter',
                    'reward', 'encounter', 'boss']
    battle_front = list(P2_FULL_TABLE)
    ra_r = rounds_alive(_w373_c3c4_redesign_state(hp=25), _w373_c3c4_redesign_sess(table=reward_front))
    ra_b = rounds_alive(_w373_c3c4_redesign_state(hp=25), _w373_c3c4_redesign_sess(table=battle_front))
    assert ra_r == 3 and ra_b == 2 and ra_r > ra_b


# --- C4-L3:未知节点保守锁 ----------------------------------------------------


def test_c4_l3_unknown_node_counts_as_normal_battle() -> None:
    """表含「?」占位 → 按 battle+normal 档计损(hp=20:12.77→7.23→
    奖励→遭遇死 → ra=3;未知多算一场损失=存活估计更短=门更紧,
    保守方向声明)。"""
    table = ['?', 'reward', 'encounter', 'reward', 'encounter',
             'reward', 'boss']
    assert node_loss_kind('?') == 'normal'
    assert rounds_alive(_w373_c3c4_redesign_state(hp=20), _w373_c3c4_redesign_sess(table=table)) == 3


# --- C4-L4:缺档零损锁 --------------------------------------------------------


def test_c4_l4_missing_kind_zero_loss_calendar_still_ticks() -> None:
    """p2_cond_loss_table 缺 kind → 该轮损 0、轮数照计(与旧实现
    「缺读=normal 最大战斗档」方向相反且各自声明):缺 encounter/boss
    档,hp=1 走完 encounter(0 损)与 boss(0 损)→ ra=2=全表长。"""
    reg = dataclasses.replace(_w373_c3c4_redesign_DEFAULT_REGISTRY,
                              p2_cond_loss_table={'normal': 12.77})
    sess = _w373_c3c4_redesign_sess(table=['encounter', 'boss'])
    assert rounds_alive(_w373_c3c4_redesign_state(hp=1), sess, reg) == 2


# --- S8 单一源不变量锁:损血表唯一(消费面=C4 投影) ----------------------------


def test_p2_node_loss_table_single_source() -> None:
    """损血表单一源不变量(C4 逐节点投影 rounds_alive 读
    registry.p2_cond_loss_table 条件败面档;原批 C3 桶位查表消费点已随
    ADR-0426 增补节定谳清理删除;无条件期望表 p2_node_loss_table 是另一
    estimand,消费面=阈值层 _loss_dist,W443 起):注入自定义表后投影
    同步位移——重标定覆写只改一处,「数值源唯一」由本锁固化,不靠人工
    纪律。"""
    assert not hasattr(_w373_c3c4_redesign_DEFAULT_REGISTRY, 'dying_band_next_loss')
    assert not hasattr(_w373_c3c4_redesign_DEFAULT_REGISTRY, 'line_switch_node_loss')
    assert not hasattr(_w373_c3c4_redesign_DEFAULT_REGISTRY, 'dying_band_account_enabled')
    reg = dataclasses.replace(
        _w373_c3c4_redesign_DEFAULT_REGISTRY,
        p2_cond_loss_table={'normal': 5.0, 'encounter': 6.0,
                            'boss': 8.0, 'reward': 0.0})
    sess = _w373_c3c4_redesign_sess(table=P2_FULL_TABLE)
    # C4 逐节点投影跟随同一份表(hp=25:默认条件档 12.77/13.33/15.50 →
    # ra=2;轻损表 5/6/8 → 25−5−5−6+0−6+0−8 死于 boss → ra=7)
    assert rounds_alive(_w373_c3c4_redesign_state(hp=25), _w373_c3c4_redesign_sess()) == 2
    assert rounds_alive(_w373_c3c4_redesign_state(hp=25), sess, reg) == 7


# --- C4-L5:死锁画像双向锁 ----------------------------------------------------


def test_c4_l5_deadlock_frame_both_calibers() -> None:
    """hp=29 + E_cur=inf + E_alt=2 的死锁画像,两行行为各锁:
    常数口径(p 表空,每战全损)→ ra=2 < need → 拦(理由 survival);
    两态口径(p_rung=0.65 注入,板强通道进投影)→ ra=7 ≥ need → 放行
    (「强板换线能活到兑现」由胜率通道可达,REDESIGN §3.6 数表)。"""
    sess = _w373_c3c4_redesign_sess()
    st = _w373_c3c4_redesign_state(hp=29)
    do, _ = should_switch_e(math.inf, 2.0, 2, _w373_c3c4_redesign_DEFAULT_REGISTRY)
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
    sess = _w373_c3c4_redesign_StrategySession()
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
    """开关默认关:registry 缺省下门恒放行——decide 全链与基线逐位
    一致的结构前提(registry hash 锁另辖字段面)。"""
    assert _w373_c3c4_redesign_DEFAULT_REGISTRY.line_switch_survival_gate_enabled is False
    st = _w373_c3c4_redesign_state(hp=20)
    assert survival_gate(st, _w373_c3c4_redesign_sess(), 99.0, _w373_c3c4_redesign_DEFAULT_REGISTRY)[0] is True


# ==================== r412_levelup_cost_flat4 ====================

from sr_od.application.currency_war.kernel.cw_economy import _want_level_up, xp_click_cost
from sr_od.application.currency_war.kernel.cw_state import GameState as _r412_levelup_cost_flat4_GameState


def _st(level: int, gold: int) -> _r412_levelup_cost_flat4_GameState:
    """P1 lv≥5 追级抑制门作用域的构造态(非 boss/hp≥30/gold<50)。"""
    return _r412_levelup_cost_flat4_GameState(level=level, gold=gold, plane=1, round_num=3,
                     node_type='普通战斗', hp=100)


def test_flat4_click_cost_constant() -> None:
    """OCR 通道死(stylized 不可检,ADR-0275)→ xp_click_cost 恒 flat-4 兜底。"""
    assert xp_click_cost(_st(7, 50)) == 4
    assert xp_click_cost(_st(5, 50)) == 4


def test_flat4_gate_boundary_lv7() -> None:
    """lv7 边界:金 13 拦 / 金 14 过(旧 4+level 模型两值全拦,门槛 21)。"""
    assert _want_level_up(_st(7, 13), None) is False, '金 13 < 4+10 → 追级抑制照拦'
    assert _want_level_up(_st(7, 14), None) is True, \
        '金 14 ≥ flat-4 单击+保命地板 → 放行(旧 4+level 模型误拦)'


def test_flat4_gate_boundary_lv5() -> None:
    """lv5 同边界(M31 语义:拦攒金追级,不拦金够的有效点击)。"""
    assert _want_level_up(_st(5, 13), None) is False
    assert _want_level_up(_st(5, 14), None) is True
