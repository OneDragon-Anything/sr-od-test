"""武装箱选卡:锁线材料档与直击优先(armory-box-value 重锚版)。

出处:被测模块本体(flow.CwFlowStrategy.decide_box_card 薄壳 + kernel
cw_equip_value 机器;design = changes/2026-09-12-armory-box-value/design.md
§2.2/§2.3)。历史:r130 修复批原锚 = state_of.target_comp;armory-box-value
锚定两态化后 target_comp 伪 comp 不再被箱打分消费(伪 comp key_equips
恒空,原 ①③ 项在 P1 帧结构性恒死——锚切换行为等价),重锚 = locked_comp。
两断言在新锚下语义保持:幸运星 tier1 胜未知件(tier0)、key 直击 tier3
胜材料(tier1)。
"""
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_vocab import CwSimFrame
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


def _sess_locked_baiyu():
    s = StrategySession()
    state_of(s).v3_intention = IntentionState(locked_comp='反甲白厄')
    return s


def test_material_score_now_alive():
    """锁线反甲白厄:幸运星(key_equip 材料)tier1 胜未知件(tier0);
    key 直击 tier3 胜材料 tier1。原 target_comp 锚已随两态化退役,
    重锚 locked_comp(锁语义重推,见模块 docstring)。"""
    st = MandateV1Strategy()
    sess = _sess_locked_baiyu()
    gs = CwSimFrame()
    # 幸运星 vs 无关件:幸运星应胜
    i = st.decide_box_card(['幸运星', '完全无关的垃圾'], gs, sess, None)
    assert i == 0, '幸运星(key_equip 材料)应因材料档胜出'
    # key_equip 直命中仍最高
    i2 = st.decide_box_card(['幸运星', '以牙还牙甲'], gs, sess, None)
    assert i2 == 1, 'key_equip 直击(tier3)应胜材料(tier1)'


def test_material_chain_via_recipes():
    """注册表链:以牙还牙甲.recipes 含 (量产型装甲, 幸运星)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
    eq = EQUIPMENTS['以牙还牙甲']
    recipes = getattr(eq, 'recipes', ()) or ()
    flat = {m for r in recipes for m in r}
    assert '幸运星' in flat and '量产型装甲' in flat
