"""形态达标三方向行为锁(设计单一源=
``.debug/temp/currency_war/w415_form_design/DESIGN.md``;决策 why=
ADR-0432/0433/0434)。

锁行为(每条=一个确定输入下的确定行为):
- 方向一 配方围栏:围栏帧内散件买候选全删(删因 recipe_fence_scatter)、
  配方件与非买候选照旧;空配方店放行(存在性围栏非全禁散件);
- 方向二 成型后不拆:成型停手帧卖出/下场使 form_ok 翻假的件被拒,
  不破 form_ok 的件照旧可卖(例外保留);
- 方向三 息线以下支出门:息线下破档升级/刷新默认拒,三例外(E1 人口位/
  E2 店内配方名集件 1 次/轮/E3 零息损同档)放行;
- 零漂移锚:三开关默认关时行为逐位回本批前(谓词恒 False/裁决不变);
- 正交声明:配方围辖域与 C1 时窗正交、与成型停手以 form_ok 真假互斥。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2 import (
    arbiter as arbiter_mod,
)
from sr_od.application.currency_war.decision_v2.arbiter import (
    _below_floor_refresh_e2,
    _check_constraint,
)
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.discipline import (
    form_break_sell_blocked,
    sell_priority_key,
)
from sr_od.application.currency_war.decision_v2.ev import levelup_ev_basis
from sr_od.application.currency_war.decision_v2.filters import (
    filter_candidates,
    formed_stop_active,
    recipe_fence_active,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

#: 名集件(桑博=DOT 体系成员,进 scoring._cand_system_bonds 名集);
#: 散件用注册表外名(名集恒空集)。
RECIPE_NAME = '桑博'
SCATTER_NAME = '围栏测试散件'


def _reg(**kw):
    return replace(DEFAULT_REGISTRY, **kw)


def _card(name: str, cost: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _sess_locked(comp_name: str = 'DOT队') -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked',
                                       locked_comp=comp_name)
    return sess


def _unformed_state(**kw) -> GameState:
    """未成型帧:DOT队 锁线,核心 2★ 躺 bench(form_ok 为假),P1 r4。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 4, 'gold': 45, 'level': 5,
        'hp': 60, 'board': {'仙舟罗浮': 1},
        'deployed': [BenchChar(slot=0, char_id=RECIPE_NAME,
                               faction='仙舟罗浮', star=1)],
        'bench': [BenchChar(slot=1, char_id=core, faction='仙舟罗浮',
                            star=2)],
        'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _formed_state(**kw) -> GameState:
    """成型停手帧(镜像 test_cw_w107 的 gap=0 构造,加厚冗余):核心
    卡芙卡 2★ 上场 + 四名持续伤害件 + 刃(星核猎手 2 档成立),
    hp 64 投影承接达标(form_ok 真 ∧ gap=0);持续伤害冗余 1 份=ADR-0373
    「冗余件照旧」缝隙的夹具化。"""
    comp = get_comp('DOT队')
    base = {
        'plane': 1, 'round_num': 7, 'gold': 41, 'level': 5,
        'hp': 64,
        'board': dict(comp.form_tiers),
        'deployed': [BenchChar(slot=0, char_id='卡芙卡',
                               faction='星核猎手', star=2),
                     BenchChar(slot=1, char_id=RECIPE_NAME,
                               faction='贝洛伯格', star=1),
                     BenchChar(slot=2, char_id='黑天鹅',
                               faction='盛会之星', star=1),
                     BenchChar(slot=3, char_id='椒丘', faction='狼狩',
                               star=1),
                     BenchChar(slot=4, char_id='刃', faction='星核猎手',
                               star=1),
                     BenchChar(slot=5, char_id='海瑟音', faction='昼之半神',
                               star=1)],
        'bench': [],
        'shop': [],
    }
    base.update(kw)
    return GameState(**base)


# ===== 方向一:配方围栏 =====


def _buy_cands() -> list[Candidate]:
    return [
        Candidate(action=BuyCard(_card(RECIPE_NAME), reason=''),
                  tag='line_carry', source='shop'),
        Candidate(action=BuyCard(_card(SCATTER_NAME), reason=''),
                  tag='line_carry', source='shop'),
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
    ]


def test_recipe_fence_drops_scatter_keeps_recipe() -> None:
    """围栏帧:同轮存在配方件买候选 → 散件买候选全删(删因
    recipe_fence_scatter),配方件与非买候选照旧(相对序不归围栏)。"""
    reg = _reg(recipe_fence_enabled=True)
    state = _unformed_state()
    sess = _sess_locked()
    assert recipe_fence_active(state, sess, reg) is True
    kept, log_entries = filter_candidates(_buy_cands(), state, sess, reg)
    kept_names = [c.action.card.name for c in kept
                  if isinstance(c.action, BuyCard)]
    assert RECIPE_NAME in kept_names
    assert SCATTER_NAME not in kept_names, '围栏帧散件买必须被删'
    dropped = [e for e in log_entries
               if e.get('recipe_fence') == 'recipe_fence_scatter']
    assert dropped and all(not e['kept'] for e in dropped)
    assert any(isinstance(c.action, RefreshShop) for c in kept), \
        '非买候选不辖'


def test_recipe_fence_empty_recipe_shop_passes_scatter() -> None:
    """空配方店放行:同轮无配方件候选 → 散件照旧走原链(存在性围栏,
    非全禁散件;[31] 空窗期语义)。"""
    reg = _reg(recipe_fence_enabled=True)
    state = _unformed_state(shop=[_card(SCATTER_NAME)])
    sess = _sess_locked()
    cands = [Candidate(action=BuyCard(_card(SCATTER_NAME), reason=''),
                       tag='line_carry', source='shop')]
    kept, _ = filter_candidates(cands, state, sess, reg)
    assert [c.action.card.name for c in kept] == [SCATTER_NAME]


def test_recipe_fence_default_off_zero_drift() -> None:
    """零漂移锚:开关默认关 → 散件照旧、链日志无 recipe_fence 字段。"""
    assert DEFAULT_REGISTRY.recipe_fence_enabled is False
    state = _unformed_state()
    sess = _sess_locked()
    assert recipe_fence_active(state, sess, DEFAULT_REGISTRY) is False
    kept, log_entries = filter_candidates(_buy_cands(), state, sess,
                                          DEFAULT_REGISTRY)
    names = [c.action.card.name for c in kept
             if isinstance(c.action, BuyCard)]
    assert set(names) == {RECIPE_NAME, SCATTER_NAME}
    assert all('recipe_fence' not in e for e in log_entries)


def test_recipe_fence_orthogonal_to_c1_and_formed_stop() -> None:
    """正交声明锁:①围辖域与 C1 开关独立(互不为前提);②与成型停手
    以 form_ok 真假互斥(未成型帧停手恒假,围栏可活;成型帧反之)。"""
    state = _unformed_state()
    sess = _sess_locked()
    reg_c1_on = _reg(recipe_fence_enabled=True,
                     c1_directed_spend_enabled=True)
    assert recipe_fence_active(state, sess, reg_c1_on) \
        == recipe_fence_active(state, sess, _reg(recipe_fence_enabled=True))
    assert formed_stop_active(state, sess, _reg(recipe_fence_enabled=True)) \
        is False, '未成型帧成型停手必须为假(互斥前提)'
    formed = _formed_state()
    sess2 = _sess_locked()
    assert formed_stop_active(formed, sess2, DEFAULT_REGISTRY) is True
    assert recipe_fence_active(formed, sess2,
                               _reg(recipe_fence_enabled=True)) is False, \
        '成型帧围栏必须自动退出'


# ===== 方向二:成型后不拆 =====


def test_form_break_blocks_core_removal_keeps_redundant() -> None:
    """成型停手帧:移除使 form_ok 翻假的件(核心卡芙卡:移除后星核猎手
    跌档)→ 拒;不破 form_ok 的件(持续伤害冗余份)→ 照旧可卖。"""
    reg = _reg(form_break_sell_blocked_enabled=True)
    state = _formed_state()
    sess = _sess_locked()
    assert formed_stop_active(state, sess, reg) is True, '夹具前提:停手帧'
    core_bc = state.deployed[0]
    assert form_break_sell_blocked(core_bc, state, sess, reg) is True, \
        '核心上场件被移除 → form_ok 翻假 → 必须拒'
    other_bc = state.deployed[1]
    assert form_break_sell_blocked(other_bc, state, sess, reg) is False, \
        '卖了不破 form_ok 的件照旧可卖(例外保留)'


def test_form_break_default_off_and_inactive_frames() -> None:
    """零漂移与辖域:开关默认关恒 False;承接口未达(降 hp 使 gap>0)
    → formed_stop 为假 → 守卫自动不辖。"""
    state = _formed_state()
    sess = _sess_locked()
    core_bc = state.deployed[0]
    assert DEFAULT_REGISTRY.form_break_sell_blocked_enabled is False
    assert form_break_sell_blocked(core_bc, state, sess,
                                   DEFAULT_REGISTRY) is False
    low_hp = _formed_state(hp=20)
    assert formed_stop_active(low_hp, sess, _reg(
        form_break_sell_blocked_enabled=True)) is False, \
        '夹具前提:低血帧承接口未达,停手为假'
    assert form_break_sell_blocked(core_bc, low_hp, sess, _reg(
        form_break_sell_blocked_enabled=True)) is False


def test_form_break_in_sell_priority_key() -> None:
    """统一卖件弱序挂点:成型停手帧内不破 form_ok 的 bench 件
    sell_priority_key 照常返回键(通道不堵;守卫判据单一源=谓词)。"""
    reg = _reg(form_break_sell_blocked_enabled=True)
    state = _formed_state(bench=[BenchChar(slot=2, char_id='花火',
                                           faction='盛会之星', star=1)])
    sess = _sess_locked()
    assert formed_stop_active(state, sess, reg) is True
    key = sell_priority_key(state.bench[0], state, sess, None, reg)
    assert key is not None, '不破 form_ok 的 bench 件照旧可卖'


# ===== 方向三:息线以下支出门 =====


def test_below_floor_levelup_gate_blocks_static_ev() -> None:
    """升级前置门:gate 开 ∧ 息线下破档 → ③ 静态 EV 账不可达(gate 关
    时同帧高 val 走 static_ev 放行=对照)。"""
    state = _unformed_state(gold=41)
    sess = _sess_locked()
    reg = _reg(below_floor_spend_gate_enabled=True)
    # gate 关:同帧 val 足够高 → static_ev 放行(现状行为)
    assert DEFAULT_REGISTRY.below_floor_spend_gate_enabled is False
    assert levelup_ev_basis(state, sess, DEFAULT_REGISTRY,
                            working_gold=41, cost=4, targets=set(),
                            val=100.0) == 'static_ev'
    # gate 开:花后 37 破档 → 拒(E3 不满足)
    assert levelup_ev_basis(state, sess, reg, working_gold=41, cost=4,
                            targets=set(), val=100.0) == ''


def test_below_floor_levelup_e3_same_tier_passes() -> None:
    """E3:息线下同档(⌊gold/10⌋ 不变)→ 零息损,照旧可达静态账。"""
    reg = _reg(below_floor_spend_gate_enabled=True)
    state = _unformed_state(gold=45)
    sess = _sess_locked()
    assert levelup_ev_basis(state, sess, reg, working_gold=45, cost=2,
                            targets=set(), val=100.0) == 'static_ev'


def test_below_floor_levelup_e1_pop_slot_whitelist() -> None:
    """E1 [33] 人口位既有臂收编:cap 满 ∧ bench 有目标件,gate 开仍放行
    pop_slot(例外是白名单不是加分,臂①语义零改动)。"""
    reg = _reg(below_floor_spend_gate_enabled=True)
    state = _unformed_state(gold=41)
    sess = _sess_locked()
    cap = state.max_units()
    state.deployed = [
        BenchChar(slot=i, char_id=f'填充{i}', faction='仙舟罗浮', star=1)
        for i in range(cap)]
    state.bench = [BenchChar(slot=0, char_id=RECIPE_NAME,
                             faction='仙舟罗浮', star=2)]
    assert levelup_ev_basis(state, sess, reg, working_gold=41, cost=4,
                            targets={RECIPE_NAME}, val=0.0) == 'pop_slot'


def _refresh_cand() -> Candidate:
    return Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')


def _no_posture(monkeypatch) -> None:
    """夹具隔离:DP 姿态置空(隔离 gold_floor 的 dp_spend 授权臂,
    单变量验证息线以下分支本身)。"""
    monkeypatch.setattr(arbiter_mod, 'round_posture',
                        lambda *a, **k: None)


def test_below_floor_refresh_gate_e2_and_default_reject(monkeypatch) -> None:
    """刷新收窄(gate 开):息线下破档刷新默认拒(删因
    below_floor_spend);店内有配方围栏名集件 → E2 放行;轮内第 2 次
    E2 不再放行(上限 1 次/轮)。"""
    _no_posture(monkeypatch)
    reg = _reg(below_floor_spend_gate_enabled=True)
    state = _formed_state(gold=41)   # HOARD 帧(form_ok 真 ∧ 金<50)
    sess = _sess_locked()
    # E2 放行:店内有名集件
    state.shop = [_card(RECIPE_NAME)]
    assert _check_constraint('gold_floor', _refresh_cand(), state, state,
                             sess, reg, auth={}) is None
    # E2 轮内已耗:转默认拒
    sess.v3_bf_refresh_key = (state.plane, state.round_num)
    sess.v3_bf_refresh_round = 1
    reason = _check_constraint('gold_floor', _refresh_cand(), state, state,
                               sess, reg, auth={})
    assert reason is not None and 'below_floor_spend' in reason.describe
    # 店内无名集件:默认拒
    sess2 = _sess_locked()
    state.shop = [_card(SCATTER_NAME)]
    reason2 = _check_constraint('gold_floor', _refresh_cand(), state,
                                state, sess2, reg, auth={})
    assert reason2 is not None and 'below_floor_spend' in reason2.describe


def test_below_floor_refresh_e3_same_tier_passes(monkeypatch) -> None:
    """E3:息线下同档刷新(零息损)→ 放行,与既有 [11] 同档臂同式。"""
    _no_posture(monkeypatch)
    reg = _reg(below_floor_spend_gate_enabled=True)
    state = _formed_state(gold=45)
    sess = _sess_locked()
    state.shop = [_card(SCATTER_NAME)]
    assert _check_constraint('gold_floor', _refresh_cand(), state, state,
                             sess, reg, auth={}) is None


def test_below_floor_refresh_default_off_zero_drift(monkeypatch) -> None:
    """零漂移锚:gate 关 → 息线下破档刷新回 HOARD 攒息拒(原文案)。"""
    _no_posture(monkeypatch)
    state = _formed_state(gold=41)
    sess = _sess_locked()
    state.shop = [_card(RECIPE_NAME)]
    reason = _check_constraint('gold_floor', _refresh_cand(), state,
                               state, sess, DEFAULT_REGISTRY, auth={})
    assert reason is not None and 'HOARD 攒息' in reason.describe


def test_below_floor_e2_helper_round_key_reset() -> None:
    """E2 轮内计数键式:轮键不匹配(跨轮)→ 计数归零重新放行。"""
    reg = _reg(below_floor_spend_gate_enabled=True)
    state = _formed_state(gold=41, shop=[_card(RECIPE_NAME)])
    sess = _sess_locked()
    sess.v3_bf_refresh_key = (state.plane, state.round_num)
    sess.v3_bf_refresh_round = 1
    assert _below_floor_refresh_e2(state, state, sess, reg) is False
    sess.v3_bf_refresh_key = (state.plane, state.round_num - 1)
    assert _below_floor_refresh_e2(state, state, sess, reg) is True
