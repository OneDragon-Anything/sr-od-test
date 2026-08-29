"""W88 d2 批三件锁(ADR-0339;升星投资/coldstart v2 防线/engine_seed 互踩)。

锁定对象:
1. 件1 升星投资:score_state 核心升星项(core_star)——2★ 目标件显影、
   1★ 不显影、unit=0 关闭(A/B 通道);sim 验证见 deep_read/W88_报告.md
   (配对 +18/0,2★ 达成率 0.280→0.400,n=150)。
2. 件2 coldstart v2 防线(AD8 条件④限期):v2 门(discipline.pair_wants
   冷启动分支)单帧锁 + 检查器(check_coldstart_seed_squander)d2 标签
   面变异自检——去门账本必须涌现违规(检查器非安慰剂)。
3. 件3 engine_seed 互踩:种子 2 轮窗绝对不让位给 carry_gate 腾位
   (W51 死锁豁免裁决移除,carry 延后有界);检查器 reason 口径
   语义不变(0 容忍恢复成立)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_sim_checks import (
    check_coldstart_seed_squander,
    check_engine_seed_not_resold,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.discipline import (
    engine_char_names,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision_v2.scoring import score_state

_REG = DEFAULT_REGISTRY
_CARRY = '姬子·启行'          # 引擎件(恒在目标集)
_PAIR_FILLER = '花火'          # 目标件(锁线视窗内)
_NON_DIRECTION = '翡翠'        # 公司件,线外散件(冷启动反例)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess(line: bool = True) -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    if line:
        from sr_od.application.currency_war.kernel.cw_intention import (
            HoardTarget,
            IntentionState,
        )
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '姬子列车'
        s.v3_intention = ist
        s.v3_hoard = HoardTarget(
            frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
            frozenset(), 'locked')
        s.v3_core_names = {'姬子·启行'}
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 6, 'gold': 60, 'level': 5,
            'board': {'仙舟罗浮': 1}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


# --- 件1:核心升星价值项 ------------------------------------------------------


def test_core_star_term_values_2star_target() -> None:
    """2★ 目标件显影 core_star=unit;1★ 不显影;非目标 2★ 不显影([31]
    填充件可回收语义保留)。"""
    sess = _sess()
    st_2star = _state(bench=[_bench(_PAIR_FILLER, star=2)])
    st_1star = _state(bench=[_bench(_PAIR_FILLER, star=1)])
    v2 = score_state(st_2star, _REG, sess)['core_star']
    v1 = score_state(st_1star, _REG, sess)['core_star']
    import pytest
    assert v2 == pytest.approx(_REG.core_star_unit * _REG.bench_form_weight), \
        f'bench 2★ 目标件应按折减权重显影(实际 {v2})'
    assert v1 == 0.0
    # 非目标 2★ 不受保护
    st_off = _state(bench=[_bench('星期日', faction='盛会之星', star=2)])
    assert score_state(st_off, _REG, sess)['core_star'] == 0.0


def test_core_star_deployed_full_weight_and_ab_off() -> None:
    """deployed 2★ 全额;core_star_unit=0 关闭(A/B 基线臂)。"""
    sess = _sess()
    st = _state(
        deployed=[SimpleNamespace(char_id=_CARRY, faction='列车同行',
                                  star=2, position_pref='back',
                                  equips=(), slot=0)])
    assert score_state(st, _REG, sess)['core_star'] == _REG.core_star_unit
    reg_off = DecisionV2Registry(core_star_unit=0.0)
    assert score_state(st, reg_off, sess)['core_star'] == 0.0


# --- 件2:coldstart v2 防线 ---------------------------------------------------


def test_coldstart_door_single_frame() -> None:
    """v2 冷启动门单帧锁:P1 r1 板面空,pair 通道只放行方向件(引擎件/
    同名副本);线外散件不生成买候选(局49 形态,v1 门语义在 v2 的载体)。"""
    sess = _sess(line=False)   # 无方向(冷启动常态)
    _eng = next(iter(engine_char_names()))
    st = _state(round_num=1, board={}, shop=[
        SimpleNamespace(name=_eng, faction='列车同行', cost=3,
                        x=0, star=1),
        SimpleNamespace(name=_NON_DIRECTION, faction='公司', cost=1,
                        x=0, star=1),
    ])
    cands = generate_candidates(st, sess, _REG)
    tags = {c.action.card.name: c.tag for c in cands
            if c.action.__class__.__name__ == 'BuyCard'}
    assert tags.get(_NON_DIRECTION) is None, \
        f'冷启动线外散件 {_NON_DIRECTION} 不应生成买候选(实际 {tags})'
    assert _eng in tags, '引擎件(方向件)冷启动应放行'


def _cw_row(plane: int, rn: int, actions: list[dict]) -> dict:
    return {'plane': plane, 'round_num': rn, 'actions': actions,
            'state': {}}


def _buy(name: str, reason: str, cost: int = 1) -> dict:
    return {'__type__': 'BuyCard', 'reason': reason,
            'card': {'name': name, 'cost': cost}}


def _sell(name: str) -> dict:
    return {'__type__': 'SellBench', 'name': name}


def test_coldstart_checker_catches_d2_pair_violation() -> None:
    """变异自检(检查器非安慰剂):去门账本(p1 r1 d2_pair 买线外散件)
    必须涌现违规——v2 标签面(d2_ 前缀归一化)可被检查器消费。"""
    rows = [_cw_row(1, 1, [_buy(_NON_DIRECTION, 'd2_pair')]),
            _cw_row(1, 2, [_buy(_NON_DIRECTION, 'd2_pair')])]
    v = check_coldstart_seed_squander(rows)
    assert len(v) == 2, \
        f'去门变异必须涌现违规(实际 {v})——检查器对 v2 标签面失明'


def test_coldstart_checker_passes_legal_v2_ledger() -> None:
    """合法 v2 账本不误报:方向件(engine_seed)/copy(3合1 素材)放行。"""
    rows = [_cw_row(1, 1, [_buy('姬子·启行', 'd2_engine_seed', 3),
                           _buy('花火', 'd2_copy')]),
            _cw_row(1, 2, [_buy('三月七', 'd2_line_carry')])]
    assert check_coldstart_seed_squander(rows) == []


# --- 件3:engine_seed 买/卖互踩(窗口绝对不让位)-------------------------------


def test_carry_gate_yields_to_fresh_seed() -> None:
    """seed16 回归锁:bench 满+唯一可卖=新鲜 engine_seed 种子 →
    carry_gate 本轮不腾(旧 W51 死锁豁免=买侧见即买与卖侧腾位互踩,
    r4 买 r6 卖 r7 再买;ADR-0339 件3 裁决移除豁免)。"""
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
    from sr_od.application.currency_war.decision_v2.discipline import (
        carry_gate_actions,
    )

    sess = _sess()
    sess.v2_round_key = (1, 4)
    sess.v2_seed_bought = {'姬子·启行': ((1, 3), 1)}
    bench = ([_bench('姬子·启行', faction='列车同行', slot=0)]
             + [_bench(n, faction='仙舟罗浮', slot=i)
                for i, n in enumerate(['藿藿', '爻光', '三月七', '花火',
                                       '瓦尔特', '藿藿', '爻光', '三月七'],
                                      start=1)])
    st = _state(round_num=4, gold=50,
                shop=[SimpleNamespace(name='姬子·启行', faction='列车同行',
                                      cost=4, x=0, star=1)],
                bench=bench)
    assert carry_gate_actions(st, sess, _REG) == [], \
        '窗口内种子不让位给 carry 腾位(carry 延后 ≤2 轮,死锁有界)'


def test_seed_age_blocked_phantom_cnt_not_exempt() -> None:
    """幻影计数锁:cnt≥2 但真持有 <2 份(登记重复/执行层否决留痕)
    不解除种子保护(seed16 姬子·启行单买 cnt=2 被 r5 卖出的互踩根因);
    真持有 ≥2 份才走素材语境豁免。"""
    from sr_od.application.currency_war.kernel.cw_discipline_rules import (
        seed_age_blocked,
    )
    sess = _sess()
    sess.v2_round_key = (1, 5)
    sess.v2_seed_bought = {'姬子·启行': ((1, 4), 2)}
    st = _state(round_num=5, bench=[_bench('姬子·启行',
                                            faction='列车同行')])
    bc = st.bench[0]
    assert seed_age_blocked(bc, st, sess) is True, \
        '幻影 cnt=2(真持有 1 份)不得解除种子保护'
    st2 = _state(round_num=5,
                 bench=[_bench('姬子·启行', faction='列车同行', slot=0),
                        _bench('姬子·启行', faction='列车同行', slot=1)])
    assert seed_age_blocked(st2.bench[0], st2, sess) is False, \
        '真持有 2 份=3合1 素材语境,豁免(不挡)'


def test_checker_flags_reason_channel_resale() -> None:
    """检查器(reason 口径,语义不变):engine_seed 买入 ≤2 轮内单份回卖
    必报(seed16 姬子·启行 r4 买 r6 卖形态的账本侧锁)。"""
    rows = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3)]),
            _cw_row(1, 6, [_sell('姬子·启行')])]
    v = check_engine_seed_not_resold(rows)
    assert len(v) == 1 and '姬子·启行' in v[0], f'回卖未报(实际 {v})'


def test_checker_bounds_and_merge_exemption() -> None:
    """边界:>2 轮后卖不报([21] 囤件窗口外合法);同轮 ≥2 份=3合1
    素材语境豁免不报。"""
    rows_late = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3)]),
                 _cw_row(1, 8, [_sell('姬子·启行')])]
    assert check_engine_seed_not_resold(rows_late) == []
    rows_merge = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3),
                                 _buy('姬子·启行', 'd2_engine_seed', 3)]),
                  _cw_row(1, 5, [_sell('姬子·启行')])]
    assert check_engine_seed_not_resold(rows_merge) == []
