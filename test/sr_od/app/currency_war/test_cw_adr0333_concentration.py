"""ADR-0333 体系集中度锁(d2 意向批;板面散面收敛)。

锁定对象(decision_v2/candidates.py + cw_line_defs.py):
① 候选层配方亲和 `_engine_seed_affinity`([20] 配方加法 + [31] 空窗):
   空窗(板面无过渡体系)→ 放行(第一体系要开);板面已有体系未成型 →
   深化件放行 / 新体系第 1 件拒(散买断);全部成型 → 放行(两两组合);
   希儿系/非三羁绊件不辖(返回 True);
② 买标签接线:engine_seed_wants 命中后叠加亲和过滤,新体系件 tag=None
   (不生成候选 → 0 分被拒);
③ 新 sim 指标纯函数(board_system_tiers/board_max_recipe_tier/
   board_recipe_faction_count/board_total_faction_count);
④ registry 常量锁:concentration_bias 已撤销(评分加分证伪,ADR-0333
   记录 Considered Options)。
决策见 docs/develop/currency_war/decisions/0333-board-concentration.md。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_line_defs import (
    board_max_recipe_tier,
    board_recipe_faction_count,
    board_system_tiers,
    board_total_faction_count,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    _engine_seed_affinity,
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '仙舟', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _bench(name: str, faction: str = '公司',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 7, 'gold': 55, 'level': 6, 'hp': 80,
            'board': {'公司': 6},
            'deployed': [_bench(f'板件{i}', faction='公司', slot=i)
                         for i in range(6)],
            'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return GameState(**base)


# --- ① 候选层配方亲和 _engine_seed_affinity -------------------------------


def test_affinity_empty_window_pass() -> None:
    """空窗(板面无任何过渡体系)→ 新体系引擎件放行(第一体系要开,[31])。"""
    st = _state(board={'公司': 6}, shop=[_card('爻光')])
    assert _engine_seed_affinity(_card('爻光'), st, _REG), '空窗应放行'


def test_affinity_deepen_pass() -> None:
    """板面已有仙舟 1 件(未成型)→ 仙舟件(深化)放行。"""
    st = _state(board={'仙舟': 1, '公司': 5}, shop=[_card('爻光')])
    assert _engine_seed_affinity(_card('爻光'), st, _REG), '深化件应放行'


def test_affinity_new_system_reject() -> None:
    """板面已有仙舟 1 件(未成型)→ 列车件(新体系第 1 件)拒(散买断)。"""
    st = _state(board={'仙舟': 1, '公司': 5},
                shop=[_card('三月七', faction='列车同行')])
    assert not _engine_seed_affinity(
        _card('三月七', faction='列车同行'), st, _REG), '新体系件应拒'


def test_affinity_all_formed_pass() -> None:
    """板面全部成型(仙舟3+列车2=引擎2)→ 新体系件放行(两两组合)。"""
    st = _state(board={'仙舟': 3, '列车同行': 2, '公司': 1},
                shop=[_card('艾丝妲', faction='持续伤害')])
    assert _engine_seed_affinity(
        _card('艾丝妲', faction='持续伤害'), st, _REG), '成型后可开新体系'


def test_affinity_non_recipe_immune() -> None:
    """非三羁绊件(公司/砂金)不辖(返回 True,engine_seed 本就不辖)。"""
    st = _state(board={'仙舟': 1, '公司': 5},
                shop=[_card('砂金', faction='公司', cost=2)])
    assert _engine_seed_affinity(
        _card('砂金', faction='公司', cost=2), st, _REG), '非三羁绊件不辖'


def test_affinity_seele_immune() -> None:
    """希儿系(deployed 二元判定)不辖(返回 True)。"""
    st = _state(board={'仙舟': 1, '公司': 5},
                shop=[_card('希儿', faction='贝洛伯格', cost=3)])
    assert _engine_seed_affinity(
        _card('希儿', faction='贝洛伯格', cost=3), st, _REG), '希儿系不辖'


# --- ② 买标签接线(engine_seed 分支叠加亲和) --------------------------------


def test_buy_tag_affinity_filter() -> None:
    """板面已有仙舟 1 件(未成型)+ shop 新体系引擎件(列车星期日,
    非桥名单):
    亲和过滤后不生成 engine_seed 候选(散买断)。"""
    st = _state(
        deployed=[_bench('爻光', faction='仙舟', slot=0),
                  _bench('板件1', faction='公司', slot=1),
                  _bench('板件2', faction='公司', slot=2),
                  _bench('板件3', faction='公司', slot=3),
                  _bench('板件4', faction='公司', slot=4),
                  _bench('板件5', faction='公司', slot=5)],
        board={'仙舟': 1, '公司': 5},
        shop=[_card('星期日', faction='列车同行', cost=3)],
    )
    cands = [c for c in generate_candidates(st, _sess(), _REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert not any(c.action.card.name == '星期日' for c in cands), \
        '新体系引擎件(未成型窗)不应生成 engine_seed 候选'


def test_buy_tag_affinity_deepen_generated() -> None:
    """板面已有仙舟 1 件(未成型)+ shop 深化件(爻光):
    生成 engine_seed 候选(配方加法)。"""
    st = _state(
        deployed=[_bench('爻光', faction='仙舟', slot=0),
                  _bench('板件1', faction='公司', slot=1),
                  _bench('板件2', faction='公司', slot=2),
                  _bench('板件3', faction='公司', slot=3),
                  _bench('板件4', faction='公司', slot=4),
                  _bench('板件5', faction='公司', slot=5)],
        board={'仙舟': 1, '公司': 5},
        shop=[_card('藿藿')],
    )
    cands = [c for c in generate_candidates(st, _sess(), _REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert any(c.action.card.name == '藿藿' for c in cands), \
        '深化件应生成 engine_seed 候选'


def test_buy_tag_affinity_empty_window_generated() -> None:
    """空窗(板面无过渡体系)+ shop 引擎件(爻光):
    生成 engine_seed 候选(第一体系要开)。"""
    st = _state(
        deployed=[_bench('板件0', faction='公司', slot=0),
                  _bench('板件1', faction='公司', slot=1),
                  _bench('板件2', faction='公司', slot=2),
                  _bench('板件3', faction='公司', slot=3),
                  _bench('板件4', faction='公司', slot=4),
                  _bench('板件5', faction='公司', slot=5)],
        board={'公司': 6},
        shop=[_card('爻光')],
    )
    cands = [c for c in generate_candidates(st, _sess(), _REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert any(c.action.card.name == '爻光' for c in cands), \
        '空窗引擎件应生成候选'


# --- ③ 新 sim 指标纯函数 ----------------------------------------------------


def test_board_concentration_metrics() -> None:
    """集中度指标纯函数:深堆 vs 散面的区分度量。"""
    deep = {'仙舟': 3, '列车同行': 2, '公司': 1, '治疗': 1}
    spread = {'仙舟': 1, '列车同行': 1, '持续伤害': 1,
              '公司': 1, '治疗': 1, '能量': 1, '欢愉': 1}
    assert board_max_recipe_tier(deep) == 3
    assert board_max_recipe_tier(spread) == 1
    assert board_recipe_faction_count(deep) == 2
    assert board_recipe_faction_count(spread) == 3
    assert board_total_faction_count(spread) == 7
    # 空板
    assert board_max_recipe_tier({}) == 0
    assert board_recipe_faction_count({}) == 0
    assert board_system_tiers({'仙舟': 3, '公司': 2}) == {
        '仙舟': 3, '列车同行': 0, '持续伤害': 0}
