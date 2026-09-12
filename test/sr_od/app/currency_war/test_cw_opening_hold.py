"""r388 开局装备 hold 纯函数锁(ADR-0257 R3 修正;18 号稿落码后迁新址)。

锁行为(构造参数 → 断言 hold 门输出):
- 开局轮(P1 r≤2)row1 帧域活跃(opening_hold 字段)——含 target 真空
  (R3:重启后首局,旧判 `tgt_comp is not None` 让乱穿残留的最高频窗口);
- 非开局轮走 r70 form 门(target 在 + 0<form<COMMIT_FRAC + committed)。

18 号稿落码批(ADR-0526)把判据从执行层(cw_op_equip_all)整编迁移至
kernel/cw_equip_env.resolve_wear_release;21 号稿落码批(ADR-0531)把
opening 扣留收窄为逐件判定(classify_item_hold,§2.3)——旧锁「开局帧
hold 布尔=True」的语义已被取代(帧级布尔只辖 row2 域),按锁的存在性
纪律改写为 row1 域标记断言;逐件收窄行为由 test_cw_opening_tool_
semantics.py 逐件判定锁面(自由件/hold 保留域五条/求值序组)承接。
"""
from sr_od.application.currency_war.kernel.cw_comps import COMMIT_FRAC
from sr_od.application.currency_war.kernel.cw_equip_env import (
    resolve_wear_release,
)

_BATTLE_NODES = frozenset({'战斗', 'boss', '遭遇', '精英'})


def _resolve(comp, form, committed, opening_round: bool):
    """旧 _transition_hold_active(comp, form, dual, opening_round) 等价面:
    battle_gate 开 + 战斗节点 = 非开局支;battle_gate 关 = 开局支。
    21 号稿收窄后返回 row1 域标记(opening_hold 字段,非帧级 hold 布尔)。"""
    if opening_round:
        return resolve_wear_release(
            2, '奖励', True, _BATTLE_NODES,
            comp, form, committed, [], False).opening_hold
    return resolve_wear_release(
        3, '战斗', True, _BATTLE_NODES,
        comp, form, committed, [], False).hold


class TestOpeningHoldR388:
    def test_opening_target_vacuum_row1_active(self):
        """R3 核心:开局轮 target=None row1 域仍活跃(白名单为空的历史
        hold 面,21 号稿收窄后由逐件判定接管)。"""
        assert _resolve(None, 0.0, True, opening_round=True) is True

    def test_opening_with_target_row1_active(self):
        assert _resolve('comp', 0.0, True, opening_round=True) is True

    def test_opening_uncommitted_row1_active(self):
        """r388 覆盖优先于 r70 committed 豁免(开局轮无战斗,穿了零变现);
        旧锁的 dual=True 即 committed=False,等价改写。"""
        assert _resolve('comp', 0.0, False, opening_round=True) is True

    def test_not_opening_target_vacuum_no_hold(self):
        """r3+ 无 target:r70 门需要 target,不 hold(白板该穿)。"""
        assert _resolve(None, 0.0, True, opening_round=False) is False

    def test_not_opening_formed_low_form_holds(self):
        assert _resolve('comp', COMMIT_FRAC / 2, True, opening_round=False) is True

    def test_not_opening_zero_form_no_hold(self):
        """form=0(无投入)不 hold——r70 语义:白板也该穿。"""
        assert _resolve('comp', 0.0, True, opening_round=False) is False

    def test_not_opening_uncommitted_no_hold(self):
        """未定型(双轨)期不 hold(穿给当前 5 人,r70;18 号稿 §2.1
        方向声明:未定型帧扣留不激活)。"""
        assert _resolve('comp', COMMIT_FRAC / 2, False, opening_round=False) is False

    def test_not_opening_committed_no_hold(self):
        """成型(form≥COMMIT_FRAC)不 hold。"""
        assert _resolve('comp', COMMIT_FRAC * 2, True, opening_round=False) is False

    def test_opening_battle_node_releases(self):
        """row3(18 号稿 §2.1):r≤2 战斗类节点释放(opening hold 不辖战斗
        节点,ADR-0461 H3 收窄)。"""
        d = resolve_wear_release(2, '战斗', True, _BATTLE_NODES,
                                 None, 0.0, False, [], False)
        assert d.opening_hold is False and d.hold is False

    def test_zero_drift_without_affix_rows(self):
        """零漂移锚:row4/row5 均不命中时,hold = opening ∨ committed
        (与迁移前 `_transition_hold_active ∧ ¬rust` 逐位一致)。"""
        for comp, form, committed in [(None, 0.0, True), ('c', 0.0, True),
                                      ('c', COMMIT_FRAC / 2, True),
                                      ('c', COMMIT_FRAC / 2, False),
                                      ('c', COMMIT_FRAC * 2, True)]:
            opening = False
            expected = (opening
                        or (comp is not None and 0.0 < form < COMMIT_FRAC
                            and committed))
            assert resolve_wear_release(
                5, '投资', True, _BATTLE_NODES,
                comp, form, committed, [], False).hold is expected
