# -*- coding: utf-8 -*-
"""W131/ADR-0352 买侧 EV 门标定单帧锁(EV 门买侧 V/C 量级错档修复)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 量纲断言:engine_jump_gold 与 interest_cost 的两口径表值对拍
  (买侧 C=回档折中 min(R,3);刷新默认口径=平面 R 上界不动);
- ② 买侧放行帧:引擎进度件跨 50 档买入(52→48)按组合跳变份额计值
  → EV>0 放行(ev_auth trace 在场)——W123 实测该面 0/8 恒拒的
  主修复位;
- ③ 真拒绝帧:无完成度贡献的填充件同帧 → EV<0 拒(门语义保留,
  标定≠门全开);
- ④ 组合跳变帧:买入即跨整数引擎档 → form_gold=该级全额跳变金
  (与 V_D 收益侧同式同源,ADR-0349 思路的买侧对偶)。
(金 50/51 拒 D 的 P5⑤ 退化输出=W119 既有锁 test_w120_p5_c_interest_
boundary,刷新口径本批不动,不重复立锁。)
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.ev import (
    cross_plane_remaining_nodes,
    interest_cost,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    engine_jump_gold,
    formation_gold_account,
    score_candidate,
)

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
    dwin01 = _REG.h3_win_rate[1] - _REG.h3_win_rate[0]
    dwin12 = _REG.h3_win_rate[2] - _REG.h3_win_rate[1]
    assert abs(engine_jump_gold(0, st, _REG)
               - (_REG.rung_value[1] * r
                  + dwin01 * _REG.expected_battle_loss
                  * _REG.hp_to_gold * _REG.battles_left_est)) < 1e-6
    assert abs(engine_jump_gold(1, st, _REG)
               - ((_REG.rung_value[2] - _REG.rung_value[1]) * r
                  + dwin12 * _REG.expected_battle_loss
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
    from sr_od.application.currency_war.decision_v2.scoring import (
        _engine_frac_remainder,
    )
    from sr_od.application.currency_war.cw_state import simulate
    after = simulate(st, cand.action)
    from sr_od.application.currency_war.decision_v2.scoring import (
        _deploy_pipeline,
    )
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
    from sr_od.application.currency_war.cw_state import simulate
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
