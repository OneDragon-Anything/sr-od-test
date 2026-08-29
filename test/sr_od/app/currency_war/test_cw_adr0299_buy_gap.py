"""ADR-0299 买入面差异解剖批锁(engine_seed 生成通道 + 目标集语义)。

锁定对象(decision_v2/candidates.py + registry.py,ADR-0299):
① engine_seed 买候选:过渡体系阵营(仙舟/列车同行/持续伤害)未持有
   件在 P1 生成 engine_seed 候选(v1 ADR-0260 门镜像直通);门:已持有
   不生成 / bench 满不种 / P2 不辖;
② 标签注册:engine_seed 进 buy_tag_priority 与四覆盖态放行标签集;
③ 目标集语义:意向载体(ADR-0336 后唯一形态,v3_hoard 驱动);
   裸 session 走引擎件种子(旧线库/桥池派生垫片已删)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_intention import HoardTarget
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    _target_names,
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _sess(hoard: set[str] | None = None) -> StrategySession:
    s = StrategySession()
    if hoard is not None:
        # 意向载体(生产真实形态;旧 locked_line 垫片已删)
        s.v3_hoard = HoardTarget(frozenset(hoard), frozenset(), 'locked')
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {'仙舟': 2}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _buy_tags(st: GameState, sess: StrategySession) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in generate_candidates(st, sess, _REG):
        a = c.action
        card = getattr(a, 'card', None)
        if card is not None and card.name:
            out[card.name] = c.tag
    return out


# --- ① engine_seed 生成通道 -------------------------------------------------


def test_engine_seed_generated_for_transition_unheld() -> None:
    """P1 未持有的过渡体系件(青雀=仙舟)→ engine_seed 候选
    (v2 买入面缺口主导层的修复:首块砖无需先凑档/锁线)。"""
    sess = _sess(hoard={'三月七'})   # 意向目标不含青雀
    st = _state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') == 'engine_seed'

def test_engine_seed_not_generated_when_held() -> None:
    """已持有同名(engine_seed 语义=未持有的第一块砖)不走
    engine_seed——副本走 copy 通道(ADR-0300 迁移后生成 'copy',
    上限归 copies_cap/层4,v1 同式)。"""
    sess = _sess(hoard={'三月七'})
    st = _state(round_num=1, board={}, bench=[
        BenchChar(slot=0, char_id='青雀', faction='仙舟')], shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_bench_full() -> None:
    """bench 满不种(r408 容量门:满员态「未持有」与卖出态构成
    永动机,ADR-0267 F1)——engine_seed 通道不触发;生成层其他
    通道(copy/pair)不受此门辖,容量由层4 bench_capacity 收口。"""
    sess = _sess(hoard={'三月七'})
    bench = [BenchChar(slot=i, char_id='娜塔莎', faction='护盾')
             for i in range(_REG.bench_capacity)]
    st = _state(round_num=1, board={}, bench=bench, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_plane2() -> None:
    """P2 不辖(过渡期种子是 P1 语义;v1 同式)——engine_seed 不
    触发;冷启动 pair 分支(classify_buy=engine)P2 照放(ADR-0300
    迁移,与 v1 _pair_wants 同判据)。"""
    sess = _sess(hoard={'三月七'})
    st = _state(plane=2, round_num=1, board={}, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_non_transition() -> None:
    """非过渡体系阵营件(阿格莱雅=昼之半神/能量)不生成
    (engine_seed 不是散买通道)。"""
    sess = _sess(hoard={'三月七'})
    st = _state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='阿格莱雅', faction='昼之半神', cost=1)])
    assert '阿格莱雅' not in _buy_tags(st, sess)


def test_engine_seed_target_piece_takes_target_tag() -> None:
    """目标件优先取目标类标签(line_opportunistic),不被 engine_seed
    降级(目标件优先于 engine_seed 通道)。"""
    sess = _sess(hoard={'三月七'})
    st = _state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='三月七', faction='列车同行', cost=1)])
    assert _buy_tags(st, sess).get('三月七') == 'line_opportunistic'


# --- ② 标签注册 --------------------------------------------------------------


def test_engine_seed_registered_everywhere() -> None:
    """engine_seed 进 buy_tag_priority 与各放行标签集
    (层2 过滤不误杀;追赶标签集已随 W126/ADR-0349 退场)。"""
    assert 'engine_seed' in _REG.buy_tag_priority
    for tags in (_REG.economy_tags, _REG.war_tags,
                 _REG.emergency_tags):
        assert 'engine_seed' in tags


# --- ③ 目标集语义(意向载体) ------------------------------------------------


def test_target_names_include_hoard_and_engines() -> None:
    """意向载体目标集 = hoard char_targets + 体系引擎件(ADR-0336
    后唯一形态;旧线库/桥池派生垫片已删)。"""
    sess = _sess(hoard={'飞霄', '三月七'})
    st = _state()
    names = _target_names(st, sess)
    assert {'飞霄', '三月七'} <= names, 'hoard 目标件漏入目标集'
    from sr_od.application.currency_war.cw_system_cards import (
        engine_char_names,
    )
    assert set(engine_char_names()) <= names, '体系引擎件漏入目标集'


def test_target_names_bare_session_engines() -> None:
    """裸 session(无 v3_hoard)= 引擎件全集种子(旧全桥名单派生已删)。"""
    sess = _sess()
    st = _state()
    from sr_od.application.currency_war.cw_system_cards import (
        engine_char_names,
    )
    assert _target_names(st, sess) == set(engine_char_names())


def test_locked_bridge_fixed_buy_candidate_generated() -> None:
    """桥 fixed 件(飞霄)在意向目标态仍生成买候选(目标类标签)。"""
    sess = _sess(hoard={'飞霄', '三月七'})
    st = _state(round_num=2, board={}, shop=[
        ShopCard(x=0, name='飞霄', faction='追击', cost=2)])
    assert _buy_tags(st, sess).get('飞霄') == 'line_opportunistic'
