"""开局血量初值表锁(ADR-0559)。

语义:开局 hp 初值 = f(词缀集) 的查表先验,只填 hp0_survey 实证过的档
(A8/数值难度 108);接在 reconcile_hp 开局分支(读不到 ∧ session 无真值),
readable=False(先验非真读),不写 last_hp_real,真值帧到达即被覆盖。
数据出处 = `.debug/temp/currency_war/hp0_survey/报告.md`(133 局,2026-09-06)。
"""
from __future__ import annotations

_A8 = 'A8'
_D108 = 108


def _mk_session():
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession)
    return StrategySession()


# ===== 表语义:实证档查表 =====

def test_prior_base_and_bad_start_affix() -> None:
    """默认档 82(109 局零方差);「开局不利」恒 −20 → 62(7/7 局)。"""
    from sr_od.application.currency_war.kernel.cw_opening_hp import (
        OPENING_HP_BASE, opening_hp_prior)
    assert OPENING_HP_BASE == 82
    assert opening_hp_prior([], _A8, _D108) == 82
    assert opening_hp_prior(None, _A8, _D108) == 82
    assert opening_hp_prior(['开局不利'], _A8, _D108) == 62
    # 修正词缀与其他随机词缀共存:只看修正词缀,组合不改变值
    assert opening_hp_prior(['开局不利', '随从强化', '首领强化'], _A8, _D108) == 62


def test_prior_time_assassin_is_base() -> None:
    """「时间刺客」初值仍 82:它污染 1-1 读数(r1=44/46,r2 回 84/86),
    不改初值——禁把被污染读数固化成先验。"""
    from sr_od.application.currency_war.kernel.cw_opening_hp import opening_hp_prior
    assert opening_hp_prior(['时间刺客'], _A8, _D108) == 82


def test_prior_unknown_difficulty_stays_none() -> None:
    """非实证难度档(其他职级/数值难度/未读到)→ None,禁外推
    (133 局样本全 A8/108,难度维度无数据=诚实未知)。"""
    from sr_od.application.currency_war.kernel.cw_opening_hp import opening_hp_prior
    assert opening_hp_prior([], '', _D108) is None          # 职级未检测
    assert opening_hp_prior([], 'A7', _D108) is None        # 其他职级
    assert opening_hp_prior([], _A8, None) is None          # 数值难度未读到
    assert opening_hp_prior([], _A8, 107) is None           # 其他数值难度


# ===== 接线语义:reconcile_hp 开局分支 =====

def test_reconcile_opening_uses_prior_not_real_read() -> None:
    """开局无真值帧 → 先验 + readable=False(先验非真读,遥测保真位不混)。"""
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = _mk_session()
    s.briefing_affixes = ['开局不利']
    s.selected_difficulty = _A8
    s.enemy_difficulty = _D108
    assert (hp := reconcile_hp(s, None)) == (62, False)
    assert s.last_hp_real is None   # 先验不进真值锚(防污染下行守卫基线)


def test_reconcile_real_read_overrides_prior() -> None:
    """真值帧优先:到达即写回 last_hp_real 并取代先验;其后读不到走既有
    沿用分支(返回真值),先验永不再现身——禁覆盖真读。"""
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = _mk_session()
    s.briefing_affixes = []
    s.selected_difficulty = _A8
    s.enemy_difficulty = _D108
    assert reconcile_hp(s, None) == (82, False)     # 先验帧
    assert reconcile_hp(s, 80) == (80, True)        # 真值帧采新(先验让位)
    assert s.last_hp_real == 80
    assert reconcile_hp(s, None) == (80, False)     # 沿用真值,非先验


def test_reconcile_no_evidence_scope_stays_none() -> None:
    """无实证档开局仍 None 诚实未知(ADR-0491 口径在本档不变)。"""
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = _mk_session()
    s.selected_difficulty = ''      # 难度未检测 → 查表 miss
    assert reconcile_hp(s, None) == (None, False)
    assert s.last_hp_real is None


def test_reconcile_offline_no_session_passthrough_unchanged() -> None:
    """无 session(离线/测试)透传语义零漂移(先验查表需要 session,离线无源)。"""
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    assert reconcile_hp(None, None) == (None, False)
