"""批 4 commit-2 零漂移锁:decision_target 双轨判定换 committed_from 派生。

零漂移依据(W646 攻击面 3 实证):decision_v2 生产路径
``session.transition_framework`` 恒 ''(framework_startup 休眠开关关、
无写端),旧 `state.dual_track_phase` 分支与换源后 `committed_from`
分支在 fw≡'' 下同返回 target_comp。本文件锁四象限语义 + 「不再读
state.dual_track_phase」源级守卫,防回滑。
"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_recipe import decision_target
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession


def _sess() -> StrategySession:
    s = StrategySession()
    s.target_comp = next(c for c in COMP_LIBRARY if c.name == '专家桑博DOT')
    return s


def test_fw_empty_returns_target_regardless_of_dual_flag():
    """零漂移主锁:fw≡''(v2 生产恒态)→ 两分支同返回 target_comp,
    与 state.dual_track_phase 取值无关(dual flag 任意塞值不改变结果)。"""
    sess = _sess()
    for flag in (False, True):
        st = GameState(plane=1, round_num=3, dual_track_phase=flag)
        assert decision_target(sess, st) is sess.target_comp


def test_fw_set_not_committed_returns_recipe():
    """双轨语义保留(挂账层 cw_plan 仍消费):fw 已定 + 未定型 → 配方伪 comp。"""
    sess = _sess()
    sess.transition_framework = '仙舟'
    st = GameState(plane=1, round_num=3)
    assert decision_target(sess, st).name == '过渡·仙舟配方'


def test_fw_set_committed_returns_final_comp():
    """定型(plane≥2 权威派生)→ 终局 comp,即使 fw 字段残留非空。"""
    sess = _sess()
    sess.transition_framework = '仙舟'
    st = GameState(plane=2, round_num=1)
    assert decision_target(sess, st) is sess.target_comp


def test_no_intention_supply_defaults_not_committed():
    """变异锁:拔掉意向供给(无 v3_intention,P1)→ committed_from 落
    保守 False → 配方分支可达(禁缺省 True=恒按定型=配方静默丢失)。"""
    sess = _sess()
    sess.transition_framework = '列车'
    st = GameState(plane=1, round_num=3)
    assert decision_target(sess, st).name == '过渡·列车配方'


def test_decision_target_no_longer_reads_dual_track_phase():
    """源级守卫:decision_target 不再直读 state.dual_track_phase
    (换源后读点归零,回滑即红)。"""
    import re

    import sr_od.application.currency_war.kernel.cw_recipe as m
    src = inspect.getsource(m.decision_target)
    assert not re.search(r"state\s*\.\s*dual_track_phase|"
                         r"getattr\(\s*state\s*,\s*'dual_track_phase'", src)
