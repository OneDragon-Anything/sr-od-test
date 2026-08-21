"""极端 drought 弃线测试(r20;ADR 见 commit 6ded7411)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_state import GameState  # noqa: E402
from sr_od.application.currency_war.cw_strategy import StrategySession  # noqa: E402
from sr_od.application.currency_war.strategies.default_strategy import DefaultCwStrategy  # noqa: E402


class _Cfg:
    character_priority: list[str] = []
    faction_priority: list[str] = []


def test_extreme_drought_bails_invested(monkeypatch) -> None:
    """drought≥8(供给断绝)时 invested 线弃,且弃后**不选回同线**(r20 排除语义)。
    r99:shop 给真牌面(无列车阵营)——空 shop 语义改「无商店相位」(drought 中性不涨),
    原空 shop 构造的断供场景不再触发。"""
    import sr_od.application.currency_war.cw_comps as comps
    from sr_od.application.currency_war.cw_state import ShopCard
    strat = DefaultCwStrategy()
    session = StrategySession()
    target = next(c for c in comps.COMP_LIBRARY if c.name == '列车同行')
    session.target_comp = target
    session.target_drought = 8
    state = GameState(board={'列车同行': 2},
                      shop=[ShopCard(x=0, faction='击破'), ShopCard(x=1, faction='击破')],
                      bench=[], plane=1, round_num=6)
    strat.update_target(state, session, _Cfg())
    new_t = session.target_comp
    assert new_t is None or new_t.name != '列车同行', (
        'drought=8 弃线后不得立即选回同一条(供给断绝线本局已死)')
    assert '列车同行' in session.drought_excluded


def test_moderate_drought_keeps_invested(monkeypatch) -> None:
    """drought 5-7(invested)仍保线(集中性优先,防破坏性 pivot)。"""
    import sr_od.application.currency_war.cw_comps as comps
    strat = DefaultCwStrategy()
    session = StrategySession()
    target = next(c for c in comps.COMP_LIBRARY if c.name == '列车同行')
    session.target_comp = target
    session.target_drought = 6
    state = GameState(board={'列车同行': 2}, shop=[], bench=[], plane=1, round_num=6)
    strat.update_target(state, session, _Cfg())
    assert session.target_comp is target, 'drought=6 invested → 保线'
