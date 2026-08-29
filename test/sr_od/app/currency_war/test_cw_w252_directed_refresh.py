"""W252/ADR-0409:M-A 定向 D 牌授权窗单帧锁。

**语义演进(ADR-0411 flag 家族清理)**:M-A 授权窗自 W257 起无条件
启用——历史 handoff_refresh_directed(及 gate 正交 flag)布尔删除,
原「默认关零漂移/仅 M-A 开(gate 关)=0 正交」锁面随 flag 退场
(docstring 记过期原因);历史三臂 AB 数字见 ADR-0409/0411。

锁面:
- 授权窗:预算>0 只在「gate gap>0(P1 末窗)∧ 追名 peak≥2(锁定
  采购目标名集内某名 star 加权副本 ∈[2,3),距 3合1 只差最后一张)」
  两条件同时成立;任一缺 → 0;
- 有界性:每轮 ≤per_round、每局 ≤game_cap;消耗计数不重置局级;
- 防双计(互斥边界):预算只辖 refresh 维——非正分刷新经预算放行时
  买候选授权路径(interest_rule 缺口项/copy 放行)零改动;正分刷新
  走既有 V_D 路径不耗预算;gold_floor 金地板照辖。
n 取断言成立最小值。

W263/ADR-0412 追名判据扩展节(⑤):未锁线(unlocked/weak/fallback)
模式追名名集并入当前活跃过渡组合成员;锁线帧不并入(双向锁)。
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.handoff import (
    directed_refresh_budget,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

logging.disable(logging.CRITICAL)

#: ADR-0411:M-A 授权窗无条件启用——行为臂即 DEFAULT_REGISTRY
_REG = DEFAULT_REGISTRY

_CARRY = '姬子·启行'
_FILLER = '娜塔莎'
_FAC = '贝洛伯格'


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
    """末窗承接缺口帧 + 追名 peak≥2 帧:deployed 含 1× 核心(星级加权 1)
    + bench 1× 核心副本(星级加权 1)→ 合计 2(∈[2,3));hp/board 维
    缺口成立(boss 投影口径,同 W242 帧族)。"""
    base = {'plane': 1, 'round_num': 8, 'gold': 55, 'level': 5,
            'hp': 20,
            'board': {'列车同行': 2, _FAC: 1},
            'deployed': [_deployed(_CARRY, '列车同行'),
                         _deployed(_FILLER, _FAC)],
            'bench': [_bench(_CARRY, '列车同行', slot=0)],
            'shop': [], 'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


# ---------- ① 授权窗条件 ----------


def test_budget_requires_gap_and_peak() -> None:
    """两条件缺一即 0:gap>0+peak≥2 才授权;持满 3 份(copies_cap 面)
    /peak<2/非末窗(gap=0)/达标帧均不授权。"""
    sess = _sess()
    st = _state()
    assert directed_refresh_budget(st, sess, _REG) \
        == DEFAULT_REGISTRY.directed_refresh_per_round
    # 非末窗(r5,W288/ADR-0418 前移后边界):gap=0 → 不授权
    assert directed_refresh_budget(_state(round_num=5), sess, _REG) == 0
    # 新窗内(r7,W288 前移后):照常授权(窗加宽语义)
    assert directed_refresh_budget(_state(round_num=7), sess, _REG) \
        == DEFAULT_REGISTRY.directed_refresh_per_round
    # 追名 peak 出域:已满 3 份(copies_cap 面)→ 不授权
    st_full = _state(bench=[_bench(_CARRY, '列车同行', slot=0),
                            _bench(_CARRY, '列车同行', slot=1)])
    assert directed_refresh_budget(st_full, sess, _REG) == 0
    # 追名 peak <2(只有 deployed 一份):收集线未起步不授权(W249 口径)
    st_one = _state(bench=[])
    assert directed_refresh_budget(st_one, sess, _REG) == 0


# ---------- ② arbiter:有界放行 + 单一来源 ----------


def test_arbiter_nonpositive_refresh_bounded_pass() -> None:
    """主通道:非正分刷新在授权窗开时有界放行(进 actions+计数);
    预算外的第二次放行被轮上限拦回「非正分」。

    语义演进(ADR-0451 血预算停手·第二波):授权帧改 hp=70(带外,
    >p1_exit_blood_target)——原 hp=30 帧已落入末窗血预算不足带,搜索型
    刷新停付取代 M-A 授权(见 test_refresh_stop_overrides_ma);hp 维
    不影响 gap(board 维 tier0 主罚,gap≥1 前置不变)。"""
    sess = _sess()
    st = _state(gold=55, hp=70)   # 带外非应急([18]);board 维 tier0→gap≥1
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st, sess, _REG)
    row = res.log[-1]
    assert row['accepted'] is True, f'预算内应放行(log={row})'
    assert any(isinstance(a, RefreshShop) for a in res.actions)
    assert (getattr(sess, 'v3_dir_refresh_round', 0),
            getattr(sess, 'v3_dir_refresh_used', 0)) == (1, 1)


def test_refresh_stop_overrides_ma() -> None:
    """ADR-0451 接缝锁:末窗血预算不足帧(25<hp<60)血线胜——M-A
    预算虽在,刷新收尾被 blood_budget_refresh_stop 前置拒付,预算
    零消耗(独立谓词 AND,承接/定向授权不豁免停手)。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate as _C,
    )
    sess = _sess()
    st = _state(gold=55, hp=30)
    cand = _C(action=RefreshShop(cost=2), tag='refresh', source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st, sess, _REG)
    assert res.log[-1]['accepted'] is False
    assert '搜索型刷新停拒' in (res.log[-1].get('reject') or '')
    assert not any(isinstance(a, RefreshShop) for a in res.actions)
    assert getattr(sess, 'v3_dir_refresh_used', 0) == 0


def test_nonfinal_window_nonpositive_rejected() -> None:
    """非末窗(r5,W288/ADR-0418 前移后边界,gap=0):非正分刷新照拒
    (窗口外零行为)。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    st = _state(round_num=5, gold=55)
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st,
                    StrategySession(), _REG)
    assert res.log[-1]['reject'] == '非正分'


def test_positive_vd_path_not_billed_to_budget() -> None:
    """防双计单一来源面:正分刷新(V_D 放行)不消耗 M-A 预算计数——
    预算只辖 M-A 授权面,W249 的 0.44 次/局基线不受扰动。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    sess = _sess()
    st = _state(gold=55)
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = arbitrate([(cand, 6.0, {'int_emb': 0.0})], st, sess, _REG)
    assert res.log[-1]['accepted'] is True   # V_D 正分与预算无关
    assert getattr(sess, 'v3_dir_refresh_used', 0) == 0


# ---------- ③ 约束链照辖 ----------


def test_affordability_floor_still_governs_authorized_refresh() -> None:
    """可负担性下限照辖:金 11 刷 2 → 花后 9 < boss_floor(10)拒;
    金 13 → 花后 11 达标放行(收尾的下限兜底,M-A 授权≠无限透支)。
    (ADR-0451:hp 改 70 带外——原 hp=30 帧已入血预算停手辖域,
    授权面语义迁移见 test_refresh_stop_overrides_ma。)"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})],
                    _state(gold=11, hp=70), _sess(), _REG)
    assert res.log[-1]['accepted'] is False
    res3 = arbitrate([(cand, -2.0, {'int_emb': 0.0})],
                     _state(gold=13, hp=70), _sess(), _REG)
    assert res3.log[-1]['accepted'] is True
    assert any(isinstance(a, RefreshShop) for a in res3.actions)


# ---------- ⑤ W263/ADR-0412 追名判据扩展(未锁线并入活跃过渡组合成员) ----------


def _transition_peak_state() -> GameState:
    """未锁线追名帧:唯一 peak≥2 的名 = 三月七(列车同行过渡件,
    star 加权 2∈[2,3)),且**不在**采购目标名集内(fallback 式窄集);
    末窗承接缺口帧族与 `_state` 同式。"""
    return GameState(
        plane=1, round_num=8, gold=55, level=5, hp=20,
        board={'列车同行': 1, _FAC: 1},
        deployed=[_deployed(_FILLER, _FAC)],
        bench=[_bench('三月七', '列车同行', slot=0),
               _bench('三月七', '列车同行', slot=1)],
        shop=[], node_type='battle')


def _sess_mode(mode: str, targets: set[str]) -> StrategySession:
    """指定意向模式的 session(phase=unlocked ∧ locked_comp 空 =
    未锁线;W263 扩展辖面)。"""
    from sr_od.application.currency_war.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'unlocked'
    ist.locked_comp = ''
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(frozenset(targets), frozenset(), mode)
    return s


def test_w263_unlocked_transition_member_authorizes() -> None:
    """扩展主锁:未锁线(unlocked/weak/fallback 模式)下,活跃过渡
    组合成员(p1_early_pair 派生体系对成员——bench 两张三月七支撑
    列车同行系)即使不在采购目标名集内,peak≥2 也授权预算>0
    (ADR-0409 只锚锁线采购集时此类局恒 0,W260 观测面)。"""
    sess = _sess_mode('fallback', {'花火', '瓦尔特'})   # 窄采购集,不含三月七
    st = _transition_peak_state()
    assert directed_refresh_budget(st, sess, _REG) \
        == DEFAULT_REGISTRY.directed_refresh_per_round


def test_w263_locked_frame_not_extended() -> None:
    """锁线不变形锁(双向):phase='locked'∧locked_comp 非空时扩展
    **不生效**——追名仍只锚锁定采购目标名集,目标集外过渡件 peak≥2
    不授权(若无此守卫、无条件并入,本帧会错误拿到 budget>0)。"""
    sess = _sess()
    sess.v3_hoard = type(sess.v3_hoard)(
        frozenset({_CARRY, '花火', '瓦尔特'}), frozenset(), 'locked')
    assert directed_refresh_budget(_transition_peak_state(), sess, _REG) == 0


# ---------- ④ 局级消耗边界 + 数值单一源 ----------



def test_game_cap_exhaustion() -> None:
    """局级上限:game_cap 次后预算归 0。"""
    sess = _sess()
    sess.v3_dir_refresh_used = DEFAULT_REGISTRY.directed_refresh_game_cap
    assert directed_refresh_budget(_state(), sess, _REG) == 0


def test_no_new_bonus_constant_single_source() -> None:
    """数值单一源:registry 无 M-A 分数 bonus 常量(有界次数预算≠分数
    叠加);买侧授权常量族(W227 缺口项)不被本批触碰。"""
    fields = [f for f in type(DEFAULT_REGISTRY).__dataclass_fields__
              if f.startswith('handoff_refresh')
              or f.startswith('directed_refresh')]
    assert set(fields) == {
        'directed_refresh_per_round', 'directed_refresh_game_cap',
        'directed_refresh_high_cost_floor'}   # 第三项=C3 清理批 dying_band_high_cost_floor 改名并入(ADR-0426 增补节),非分数 bonus
