"""r96:P1 后段极端 drought 不弃线(第18局三连换根因)。"""
from sr_od.application.currency_war import cw_comps
from sr_od.application.currency_war.cw_comps import Comp
from sr_od.application.currency_war.cw_state import GameState, ShopCard
from sr_od.application.currency_war.strategies.default_strategy import DefaultCwStrategy


def _cfg():
    from sr_od.application.currency_war.currency_war_config import CurrencyWarConfig
    return CurrencyWarConfig.__new__(CurrencyWarConfig)


def test_p1_late_drought_keeps_line(capsys):
    """P1 r8 极端 drought(≥8 轮)→ 保持现线不弃(弃=无重建轮次必死)。"""
    strat = DefaultCwStrategy()
    sess = strat.create_session(_cfg())
    xz = Comp(name="景元仙舟", factions=["仙舟"], core_chars=["景元"],
              form_tiers={"仙舟": 3}, strength="A", form_difficulty="easy")
    sess.target_comp = xz
    sess.target_drought = 8
    state = GameState(gold=30, hp=46, level=5, round_num=8, plane=1,
                      board={"仙舟": 2, "治疗": 1},
                      shop=[ShopCard(x=1, faction="减益", name="", cost=1)])
    strat.update_target(state, sess, _cfg())
    assert sess.target_comp is not None, "P1 后段弃线 = 三连换根因(局18),必须保持"
    assert sess.target_drought == 9, "保持时计数自然累积(8+1,继续观测;不弃不重置)"


def test_p1_early_or_p2_drought_still_bails(monkeypatch):
    """P1 前段(有重建轮次)/P2 极端 drought → 仍弃线重选(原语义保留)。"""
    strat = DefaultCwStrategy()
    sess = strat.create_session(_cfg())
    xz = Comp(name="景元仙舟", factions=["仙舟"], core_chars=["景元"],
              form_tiers={"仙舟": 3}, strength="A", form_difficulty="easy")
    monkeypatch.setattr(cw_comps, "select_comp", lambda *a, **k: [xz])
    monkeypatch.setattr(cw_comps, "select_comp_scored", lambda *a, **k: [(0.5, xz)])
    # P1 前段 r4
    sess.target_comp = xz
    sess.target_drought = 8
    state = GameState(gold=30, hp=60, level=4, round_num=4, plane=1,
                      board={"仙舟": 2},
                      shop=[ShopCard(x=1, faction="减益", name="", cost=1)])
    strat.update_target(state, sess, _cfg())
    assert sess.target_drought == 0, "P1 前段极端 drought 仍弃线重选(有轮次重建)"
