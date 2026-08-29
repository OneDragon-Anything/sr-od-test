# -*- coding: utf-8 -*-
"""r388 开局装备 hold 纯函数锁(ADR-0257 R3 修正)。

锁行为(构造参数 → 断言 hold 门输出):
- 开局轮(P1 r≤2)hold 无条件——含 target 真空(R3:重启后首局,
  旧判 `tgt_comp is not None` 让乱穿残留的最高频窗口);
- 非开局轮走 r70 form 门(target 在 + 0<form<COMMIT_FRAC + 非双轨)。
"""
from sr_od.application.currency_war.kernel.cw_comps import COMMIT_FRAC
from sr_od.application.currency_war.operations.prep.equip_all import (
    _transition_hold_active,
)


class TestOpeningHoldR388:
    def test_opening_target_vacuum_holds(self):
        """R3 核心:开局轮 target=None 也 hold(白名单为空=全 hold)。"""
        assert _transition_hold_active(None, 0.0, False, opening_round=True) is True

    def test_opening_with_target_holds(self):
        assert _transition_hold_active('comp', 0.0, False, opening_round=True) is True

    def test_opening_dual_track_still_holds(self):
        """r388 覆盖优先于 r70 双轨豁免(开局轮无战斗,穿了零变现)。"""
        assert _transition_hold_active('comp', 0.0, True, opening_round=True) is True

    def test_not_opening_target_vacuum_no_hold(self):
        """r3+ 无 target:r70 门需要 target,不 hold(白板该穿)。"""
        assert _transition_hold_active(None, 0.0, False, opening_round=False) is False

    def test_not_opening_formed_low_form_holds(self):
        assert _transition_hold_active('comp', COMMIT_FRAC / 2, False, opening_round=False) is True

    def test_not_opening_zero_form_no_hold(self):
        """form=0(无投入)不 hold——r70 语义:白板也该穿。"""
        assert _transition_hold_active('comp', 0.0, False, opening_round=False) is False

    def test_not_opening_dual_track_no_hold(self):
        """双轨期不 hold(穿给当前 5 人,r70)。"""
        assert _transition_hold_active('comp', COMMIT_FRAC / 2, True, opening_round=False) is False

    def test_not_opening_committed_no_hold(self):
        """成型(form≥COMMIT_FRAC)不 hold。"""
        assert _transition_hold_active('comp', COMMIT_FRAC * 2, False, opening_round=False) is False
