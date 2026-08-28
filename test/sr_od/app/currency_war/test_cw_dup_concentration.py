"""同名牌集中度约束行为锁(决策 why=ADR-0437;数据依据=配方供给链
逐帧分析:差一张桶内第三张 offer 被放过 48%、错过 99.5% 非金约束)。

锁行为(每条=一个确定输入下的确定行为):
- 谓词辖域:开关开 ∧ P1 ∧ form_ok 为假才活;成型帧/P2/默认关恒假;
- 动作级:已持 2 张同名 1★ 配方名 + 该名第三张 offer 在 survivors →
  散件买候选全删(删因 dup_concentration_scatter),第三张与非买候选
  照旧;仅持 1 张(未达集中度条件)不辖;
- 零漂移锚:开关默认关时行为逐位回本批前(谓词恒 False/无链日志字段);
- 正交声明锁:与 recipe_fence 开关独立;双开时散件已被围栏删,本条
  空转不重复记账(删因分列互不污染)。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.cw_line_defs import (
    recipe_char_names,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.filters import (
    dup_concentration_active,
    filter_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

#: 夹具配方名 = recipe_char_names() 任取一个 1 费名(名集单一源锁见
#: test_recipe_char_names_single_source);散件用注册表外名。
RECIPE_NAME = '三月七'
SCATTER_NAME = '集中度测试散件'


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
    """未成型帧:DOT队 锁线,核心 2★ 躺 bench(form_ok 为假),P1 r4;
    bench 预置 2 张同名 1★ 配方名(差一张凑 3合1 的集中度条件)。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 4, 'gold': 45, 'level': 5,
        'hp': 60, 'board': {'仙舟罗浮': 1},
        'deployed': [BenchChar(slot=0, char_id=RECIPE_NAME,
                               faction='仙舟罗浮', star=1)],
        'bench': [BenchChar(slot=1, char_id=core, faction='仙舟罗浮',
                            star=2),
                  BenchChar(slot=2, char_id=RECIPE_NAME,
                            faction='仙舟罗浮', star=1)],
        'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _cands(*names: str) -> list[Candidate]:
    out = [Candidate(action=BuyCard(_card(n), reason=''),
                     tag='line_carry', source='shop') for n in names]
    out.append(Candidate(action=RefreshShop(cost=2), tag='refresh',
                         source='shop'))
    return out


def test_recipe_char_names_single_source() -> None:
    """名集单一源锁:配方名集=factions ∩ RECIPE_FACTIONS(16 名,与
    供给链分析口径一致);夹具名在集内、散件名不在。"""
    names = recipe_char_names()
    assert len(names) == 16
    assert RECIPE_NAME in names
    assert SCATTER_NAME not in names
    assert '桑博' not in names, '桑博=DOT flow 命中、factions 不在 \
RECIPE_FACTIONS,不进配方名集(与供给链 16 名口径一致)'


def test_dup_concentration_drops_scatter_on_third_offer() -> None:
    """核心行为:已持 2 张同名 1★ 配方名 + 该名第三张 offer 在
    survivors → 散件买候选全删(删因 dup_concentration_scatter),
    第三张与非买候选照旧。"""
    reg = _reg(dup_concentration_enabled=True)
    state = _unformed_state()
    sess = _sess_locked()
    assert dup_concentration_active(state, sess, reg) is True
    kept, log_entries = filter_candidates(
        _cands(RECIPE_NAME, SCATTER_NAME), state, sess, reg)
    kept_names = [c.action.card.name for c in kept
                  if isinstance(c.action, BuyCard)]
    assert kept_names == [RECIPE_NAME], '散件删、第三张留'
    dropped = [e for e in log_entries
               if e.get('dup_concentration') == 'dup_concentration_scatter']
    assert dropped and all(not e['kept'] for e in dropped)
    assert any(isinstance(c.action, RefreshShop) for c in kept), \
        '非买候选不辖'


def test_dup_concentration_needs_two_copies() -> None:
    """集中度条件:同名仅 1 张(未达差一张)→ 不删散件;散件名持 2 张
    但散件非配方名 → 同样不辖(判据对象=配方名集)。"""
    reg = _reg(dup_concentration_enabled=True)
    sess = _sess_locked()
    one_copy = _unformed_state(
        bench=[BenchChar(slot=2, char_id='卡芙卡',
                         faction='星核猎手', star=1)])
    kept, log_entries = filter_candidates(
        _cands(RECIPE_NAME, SCATTER_NAME), one_copy, sess, reg)
    names = [c.action.card.name for c in kept
             if isinstance(c.action, BuyCard)]
    assert set(names) == {RECIPE_NAME, SCATTER_NAME}
    assert all('dup_concentration' not in e for e in log_entries)
    # 第三张 offer 不在场(店内无该名)→ 触发条件不成立,散件照旧
    no_offer = _unformed_state()
    kept2, log2 = filter_candidates(_cands(SCATTER_NAME), no_offer, sess,
                                    reg)
    assert [c.action.card.name for c in kept2
            if isinstance(c.action, BuyCard)] == [SCATTER_NAME]
    assert all('dup_concentration' not in e for e in log2)


def test_dup_concentration_scope_gates() -> None:
    """辖域门:成型帧(form_ok 真)与 P2 恒假;开关默认关恒假。"""
    sess = _sess_locked()
    assert DEFAULT_REGISTRY.dup_concentration_enabled is False
    assert dup_concentration_active(_unformed_state(), sess,
                                    DEFAULT_REGISTRY) is False
    p2 = _unformed_state(plane=2)
    assert dup_concentration_active(
        p2, sess, _reg(dup_concentration_enabled=True)) is False


def test_dup_concentration_orthogonal_to_fence() -> None:
    """正交声明锁:①开关独立(互不为前提);②双开零冲突——散件已被
    围栏先删,本条空转,无 dup_concentration 字段残留(删因分列)。"""
    sess = _sess_locked()
    state = _unformed_state()
    assert dup_concentration_active(
        state, sess, _reg(dup_concentration_enabled=True)) \
        == dup_concentration_active(
            state, sess, _reg(dup_concentration_enabled=True,
                              recipe_fence_enabled=True)), \
        '开关独立,互不为开臂前提'
    kept, log_entries = filter_candidates(
        _cands(RECIPE_NAME, SCATTER_NAME), state, sess,
        _reg(dup_concentration_enabled=True, recipe_fence_enabled=True))
    names = [c.action.card.name for c in kept
             if isinstance(c.action, BuyCard)]
    assert names == [RECIPE_NAME]
    assert any(e.get('recipe_fence') == 'recipe_fence_scatter'
               for e in log_entries)
    assert all('dup_concentration' not in e for e in log_entries), \
        '双开时集中度后置步空转,不重复记账'


def test_dup_concentration_default_off_zero_drift() -> None:
    """零漂移锚:开关默认关 → 散件照旧、链日志无 dup_concentration
    字段(行为逐位回本批前)。"""
    state = _unformed_state()
    sess = _sess_locked()
    assert dup_concentration_active(state, sess, DEFAULT_REGISTRY) is False
    kept, log_entries = filter_candidates(
        _cands(RECIPE_NAME, SCATTER_NAME), state, sess, DEFAULT_REGISTRY)
    names = [c.action.card.name for c in kept
             if isinstance(c.action, BuyCard)]
    assert set(names) == {RECIPE_NAME, SCATTER_NAME}
    assert all('dup_concentration' not in e for e in log_entries)
