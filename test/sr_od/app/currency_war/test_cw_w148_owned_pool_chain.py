"""W148 owned 穿戴池搬运链回归锁(ADR-0357,W92 修法 A)。

背景(W92 诊断,2026-08-25):装备「攒着」的持有面完全不可见——
``state.equips``(owned 池)在 3,061 条 decisions 里 0 条非空。根因:
``battle_prep_recognizer``/``EquipAll`` 已读 owned_equips,但没有任何代码
把它搬进 session/决策 state(有读点、无写链)。

本锁钉死搬运链三节,防再断:
- 写端过滤:read_equips 命中 → 穿戴类名单(工具类剔除);
- 读端拷贝:``_pseudo_state`` 把 ``session.last_owned_equips`` 拷入
  ``state.equips``(decisions 遥测携带 → win_model 持有面特征可见);
- session 字段默认态(新局空列表,非 None)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.operations.prep.equip_all import (
    _owned_wearable_names,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)


def test_owned_wearable_names_filters_tools() -> None:
    """写端过滤:工具类(冶金炉)剔除,穿戴类保留;未注册名(识别残留)剔除。"""
    hits = [('冶金炉', (1800, 240), 0.9),      # 工具类 → 剔除
            ('财富宝钻', (1850, 240), 0.9),    # 穿戴类 → 保留
            ('未注册残影', (1900, 240), 0.9)]  # 不在 EQUIPMENTS → 剔除
    assert _owned_wearable_names(hits) == ['财富宝钻']


def test_session_last_owned_equips_defaults_empty() -> None:
    """session 新局默认空列表(非 None——下游 list() 拷贝不崩)。"""
    assert StrategySession().last_owned_equips == []


def test_pseudo_state_copies_owned_pool() -> None:
    """读端拷贝(W92 验收锚点①的锁形态):session 快照 → st.equips 非空。

    EquipAll 读到 owned 穿戴池(写 session.last_owned_equips)后,决策
    state.equips 必须非空——修复前此链断裂(恒空)。
    """
    sess = StrategySession()
    sess.last_owned_equips = ['财富宝钻', '分身墨镜']
    st = DecisionV2Strategy()._pseudo_state(None, sess)
    assert st.equips == ['财富宝钻', '分身墨镜']


def test_pseudo_state_owned_pool_empty_semantics_unchanged() -> None:
    """空快照:st.equips 为空列表(默认语义不变,不造出假持有)。"""
    sess = StrategySession()
    st = DecisionV2Strategy()._pseudo_state(None, sess)
    assert st.equips == []
