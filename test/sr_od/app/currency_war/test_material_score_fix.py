"""r130 合成材料分修复测试(字段名 recipes;局33b 获取侧根因)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.strategy import DecisionV2Strategy


def _sess_baiyu():
    s = StrategySession()
    s.target_comp = next(c for c in COMP_LIBRARY if c.name == '反甲白厄')
    return s


def test_material_score_now_alive():
    """反甲白厄定型:幸运星(以牙还牙甲材料)应拿 +30 材料分——
    旧代码读 .materials 恒空,材料分静默失效(局33b 根因)。"""
    st = DecisionV2Strategy()
    sess = _sess_baiyu()
    gs = GameState()
    # 幸运星 vs 无关件:幸运星应胜
    i = st.decide_box_card(['幸运星', '完全无关的垃圾'], gs, sess, None)
    assert i == 0, '幸运星(key_equip 材料)应因材料分胜出'
    # key_equip 直命中仍最高
    i2 = st.decide_box_card(['幸运星', '以牙还牙甲'], gs, sess, None)
    assert i2 == 1, 'key_equip 直命中(+100)应胜材料(+30)'


def test_material_chain_via_recipes():
    """注册表链:以牙还牙甲.recipes 含 (量产型装甲, 幸运星)。"""
    from sr_od.application.currency_war.cw_equipment_data import EQUIPMENTS
    eq = EQUIPMENTS['以牙还牙甲']
    recipes = getattr(eq, 'recipes', ()) or ()
    flat = {m for r in recipes for m in r}
    assert '幸运星' in flat and '量产型装甲' in flat
