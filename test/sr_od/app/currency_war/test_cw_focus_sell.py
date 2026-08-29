"""集中卖散测试(r28 散板治法)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_plan import _sell_offline_for_focus  # noqa: E402
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, SellBench  # noqa: E402
from sr_od.application.currency_war.kernel.cw_comps import get_comp  # noqa: E402


def test_sells_offline_bench_dead_stock() -> None:
    """target=列车同行定后:bench off-line 散牌(不属 target/priority/flex)卖出。
    r32 判据修正:场上满员(deployed≥max)时 bench 才是死库存。"""
    target = get_comp('列车同行')
    state = GameState(
        deployed=[BenchChar(slot=i, faction='列车同行') for i in range(6)],   # 满员 6/6
        bench=[BenchChar(slot=0, char_id='卡芙卡', faction='星核猎手'),
               BenchChar(slot=1, char_id='三月七', faction='列车同行'),
               BenchChar(slot=2, char_id='镜流', faction='仙舟')])
    actions: list = []
    _sell_offline_for_focus(state, actions, [], target)
    sells = [a for a in actions if isinstance(a, SellBench)]
    assert len(sells) >= 1, 'off-line 散牌(星核猎手/仙舟)应卖 ≥1'


def test_keeps_target_and_flex() -> None:
    """target 阵营卡与 flex 阵营(过渡件)不卖。"""
    target = get_comp('列车同行')
    flex0 = (target.flex_factions or ['护盾'])[0]
    state = GameState(
        bench=[BenchChar(slot=0, char_id='三月七', faction='列车同行'),
               BenchChar(slot=1, char_id='某护盾', faction=flex0)])
    actions: list = []
    _sell_offline_for_focus(state, actions, [], target)
    assert not any(isinstance(a, SellBench) for a in actions), 'target/flex 卡不卖'


def test_none_target_noop() -> None:
    """target=None(早期)不卖(无集中方向)。"""
    state = GameState(bench=[BenchChar(slot=0, char_id='卡芙卡', faction='星核猎手')])
    actions: list = []
    _sell_offline_for_focus(state, actions, [], None)
    assert not actions
