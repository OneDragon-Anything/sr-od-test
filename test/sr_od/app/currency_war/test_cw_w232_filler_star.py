"""W232 产星通道锁(ADR-0402;方案 A filler_star 期权分 + 方案 B 方向门豁免)。

锁定对象(W231 诊断 §③ 定稿,W232 实现批):
1. 评分项 filler_star:已 deployed 填充件(目标集外)第 2 份同名 1★
   计期权分;bench-only 囤件不折;目标集内名让位 merge_progress;
   star≥2 回落;unit=0 关闭。
2. 方案 B 门序:同名副本豁免 pair_wants 方向门(判定在方向门之前,
   冷启动例外 r383b 的全轮域推广);默认关。
3. 默认双关零漂移:filler_star_unit=0 且 pair_copy_direction_exempt=
   False(=DEFAULT_REGISTRY)时,方向外 deployed 填充件同名卡不生成
   任何买候选(r410 守卫 + 方向门现行为,W96 锁的语义延续)。
4. r410 守卫 A 臂豁免:filler_star_unit>0 时已 deployed 名的同名副本
   生成候选(bench-only 囤件名不豁免);copies_cap 照常辖。
5. 评分断言:A+B 开臂时,deployed 填充件第 2 份买入候选正分且
   filler_star 维构成 delta。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    _buy_tag,
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
    score_state,
)

_REG = DEFAULT_REGISTRY
_AB = DecisionV2Registry(filler_star_unit=1.0,
                         pair_copy_direction_exempt=True)
_A_ONLY = DecisionV2Registry(filler_star_unit=1.0)
_CARRY = '姬子·启行'          # 核心件(v3_core_names;line_carry)
_FILLER = '娜塔莎'             # 方向外填充件(贝洛伯格/治疗,∉方向阵营)
_FILLER_FAC = '贝洛伯格'


def _bench(name: str, faction: str, slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _deployed(name: str, faction: str, star: int = 1,
              slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=star,
                           position_pref='back', equips=(), slot=slot)


def _sess() -> StrategySession:
    from sr_od.application.currency_war.cw_intention import (
        HoardTarget,
        IntentionState,
    )
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


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 7, 'gold': 60, 'level': 5,
            'board': {'列车同行': 2, _FILLER_FAC: 1},
            'deployed': [_deployed(_CARRY, '列车同行'),
                         _deployed(_FILLER, _FILLER_FAC)],
            'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return GameState(**base)


# --- 件1:filler_star 项值 ----------------------------------------------------


def test_filler_star_term_values() -> None:
    """deployed 填充件 2 份显影;bench-only 不折;目标集内让位;
    star≥2 回落;默认关。"""
    sess = _sess()
    # deployed 1 + bench 1(2 份,已 deployed 名)→ 全额 1 进度
    st2 = _state(bench=[_bench(_FILLER, _FILLER_FAC, slot=0)])
    assert score_state(st2, _AB, sess)['filler_star'] == \
        pytest.approx(_AB.filler_star_unit)
    # 默认 registry:0(=现行为,A/B 基线臂)
    assert score_state(st2, _REG, sess)['filler_star'] == 0.0
    # unit=0 显式关
    assert score_state(
        st2, DecisionV2Registry(filler_star_unit=0.0), sess
    )['filler_star'] == 0.0
    # bench-only 2 份(无 deployed 名)→ 不折(ADR-0295 域边界)
    st_bench_only = _state(
        deployed=[_deployed(_CARRY, '列车同行')],
        bench=[_bench(_FILLER, _FILLER_FAC, slot=0),
               _bench(_FILLER, _FILLER_FAC, slot=1)])
    assert score_state(st_bench_only, _AB, sess)['filler_star'] == 0.0
    # 目标集内名(花火∈hoard targets)→ 让位 merge_progress,不双计
    st_target = _state(
        deployed=[_deployed('花火', '列车同行')],
        bench=[_bench('花火', '列车同行', slot=0)])
    assert score_state(st_target, _AB, sess)['filler_star'] == 0.0
    assert score_state(st_target, _AB, sess)['merge_progress'] > 0.0
    # 已 2★:进度回落(填充 2★ 不另计价,战力走阵营计数 star 加权)
    st_star2 = _state(
        deployed=[_deployed(_CARRY, '列车同行'),
                  _deployed(_FILLER, _FILLER_FAC, star=2, slot=1)],
        bench=[_bench(_FILLER, _FILLER_FAC, slot=0)])
    assert score_state(st_star2, _AB, sess)['filler_star'] == 0.0


def test_filler_star_per_name_cap_one_progress() -> None:
    """每名只计一次第 2 份进度;多名 deployed 填充件各计各的。"""
    sess = _sess()
    st = _state(
        deployed=[_deployed(_CARRY, '列车同行'),
                  _deployed(_FILLER, _FILLER_FAC, slot=1),
                  _deployed('青雀', '仙舟', slot=2)],
        bench=[_bench(_FILLER, _FILLER_FAC, slot=0),
               _bench('青雀', '仙舟', slot=1)])
    assert score_state(st, _AB, sess)['filler_star'] == \
        pytest.approx(_AB.filler_star_unit * 2)


# --- 件2/3:B 门序 + 默认双关零漂移 -------------------------------------------


def _shop_of(cands: list) -> list[str]:
    return [getattr(getattr(c.action, 'card', None), 'name', '') or ''
            for c in cands]


def test_default_arm_no_candidate_off_direction_deployed_filler() -> None:
    """默认双关(unit=0 + exempt=False):方向外 deployed 填充件同名卡
    不生成任何买候选——r410 守卫 + 方向门现行为(W96 r7 帧锁的语义
    延续;零漂移门的行为面)。"""
    sess = _sess()
    st = _state(shop=[ShopCard(x=1, faction=_FILLER_FAC, name=_FILLER,
                               cost=3)])
    assert _buy_tag(st.shop[0], st, sess, _REG) is None
    cands = generate_candidates(st, sess, _REG)
    assert _FILLER not in _shop_of(cands)


def test_b_exempts_direction_gate_before_pair_wants() -> None:
    """方案 B:同名副本豁免方向门(判定先于 pair_wants)→ 'copy' 标签;
    即使单独开 B(评分仍 0 分维度)候选也生成(是否成交归仲裁)。"""
    sess = _sess()
    st = _state(shop=[ShopCard(x=1, faction=_FILLER_FAC, name=_FILLER,
                               cost=3)])
    b_only = DecisionV2Registry(pair_copy_direction_exempt=True)
    # B 单独:pair_wants 方向门拦(r410 守卫也拦 deployed 名)——
    # 但 B 的豁免在 _buy_tag 层,r410 守卫仍在 → deployed 副本需 A 臂
    # 开才过生成层;b_only 下该帧不生成(B 单独对 deployed 名无效果,
    # 对 bench-only 名有效,见下一用例)
    assert _FILLER not in _shop_of(generate_candidates(st, sess, b_only))
    # A+B 同臂:候选生成且标签 = 'copy'
    cands = generate_candidates(st, sess, _AB)
    got = [c for c in cands if _FILLER in _shop_of([c])]
    assert got, 'A+B 开臂应生成 deployed 填充件副本候选'
    assert got[0].tag == 'copy'


def test_b_alone_unlocks_bench_only_copy() -> None:
    """B 单独:bench-only 同名副本(方向外)候选生成——无 deployed 名
    → r410 守卫不辖,豁免只跳过方向门。"""
    sess = _sess()
    st = _state(
        deployed=[_deployed(_CARRY, '列车同行')],
        bench=[_bench(_FILLER, _FILLER_FAC, slot=0)],
        shop=[ShopCard(x=1, faction=_FILLER_FAC, name=_FILLER, cost=3)])
    b_only = DecisionV2Registry(pair_copy_direction_exempt=True)
    # 默认:方向门拦(owned 阵营门也拦——贝洛伯格∈owned 放行,但
    # 方向门先拦);B 开:豁免
    assert _FILLER not in _shop_of(generate_candidates(st, sess, _REG))
    got = [c for c in generate_candidates(st, sess, b_only)
           if _FILLER in _shop_of([c])]
    assert got and got[0].tag == 'copy'


# --- 件4:r410 守卫 A 臂豁免 --------------------------------------------------


def test_r410_guard_a_arm_exemption_scope() -> None:
    """filler_star_unit>0 时已 deployed 名的同名副本过 r410 守卫;
    bench-only 名不豁免(默认关=W96 守卫现行为)。"""
    sess = _sess()
    # deployed 填充件名:A 臂开(无 B)→ 过守卫;但方向门仍拦
    # (pair_wants False → bond_fallback 条件外)→ 无候选——A 单独
    # 对方向外 deployed 名不足,须配 B
    st = _state(shop=[ShopCard(x=1, faction=_FILLER_FAC, name=_FILLER,
                               cost=3)])
    assert _FILLER not in _shop_of(generate_candidates(st, sess, _A_ONLY))


def test_copies_cap_still_applies() -> None:
    """copies_cap 沿用:同名星级加权 ≥3 份时 A+B 臂也不生成候选。"""
    sess = _sess()
    st = _state(
        bench=[_bench(_FILLER, _FILLER_FAC, slot=0),
               _bench(_FILLER, _FILLER_FAC, slot=1)],
        shop=[ShopCard(x=1, faction=_FILLER_FAC, name=_FILLER, cost=3)])
    # deployed 1 + bench 2 = 星级加权 3 ≥ copies_cap → 第 4 份拒
    assert _FILLER not in _shop_of(generate_candidates(st, sess, _AB))


# --- 件5:评分断言 ------------------------------------------------------------


def test_ab_arm_second_copy_scores_positive() -> None:
    """A+B 开臂:deployed 填充件第 2 份买入候选正分,filler_star 维
    构成 delta(修前:候选不存在;A 臂开=期权显影)。"""
    sess = _sess()
    st = _state(shop=[ShopCard(x=1, faction=_FILLER_FAC, name=_FILLER,
                               cost=3)])
    got = [c for c in generate_candidates(st, sess, _AB)
           if _FILLER in _shop_of([c])]
    val, bd = score_candidate(got[0], st, sess, _AB)
    assert val > 0, f'第 2 份买入应正分(实际 {val})'
    assert bd['after']['filler_star'] > bd['base']['filler_star']
    # 默认臂:同帧无候选(零漂移)
    assert not [c for c in generate_candidates(st, sess, _REG)
                if _FILLER in _shop_of([c])]


def test_registry_defaults_zero_drift_constants() -> None:
    """默认值锁:filler_star_unit=0.0 / pair_copy_direction_exempt=False
    (=现行为零漂移,A/B 通道保留模式)。"""
    assert DEFAULT_REGISTRY.filler_star_unit == 0.0
    assert DEFAULT_REGISTRY.pair_copy_direction_exempt is False
