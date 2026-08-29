"""W606 批③·对拍协议门2:逆真值 fixture(9 恒真位反事实直喂 decide)。

sim 合成器 9 恒真位(W598 攻击4)逐一反事实构造 Snapshot,喂适配器
(真 DecisionV2Strategy 决策核),断言保守臂:不崩 + 显式预期动作。
协议总则:sim 全绿不可替代本门(边界态行为 sim 结构性测不到)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_assembly import DecideAdapter
from sr_od.application.currency_war.decision_v2.adapter import (
    decision_state,
    snapshot_to_obs,
)
from sr_od.application.currency_war.decision_v2.contracts import (
    RewardSphere,
    Snapshot,
    SubstateClassification,
)

_CONFIG = SimpleNamespace(character_priority=[])


def _snap(**kw) -> Snapshot:
    kw.setdefault(
        'classification', SubstateClassification(name='prep_shop', confident=True))
    return Snapshot(**kw)


def _decide(snapshot: Snapshot, session: StrategySession | None = None):
    from sr_od.application.currency_war.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    ad = DecideAdapter(DecisionV2Strategy(), _CONFIG, executor=None)
    return ad.decide(snapshot, session or StrategySession())


def _two_spheres():
    return (RewardSphere(color='blue', x=100, y=200, radius=5),
            RewardSphere(color='gold', x=300, y=400, radius=5))


# ── 1 confident 恒 True → False:不可进 decide(框架门职责;适配器断言)──

def test_fixture1_unconfident_rejected():
    bad = Snapshot(classification=SubstateClassification(
        name='unknown', confident=False))
    with pytest.raises(ValueError):
        _decide(bad)


# ── 2 gold_trusted 恒 True → False:F2 门,金不进决策 state(禁假真值)──

def test_fixture2_gold_untrusted_not_adopted():
    st = decision_state(_snap(gold=47, gold_trusted=False), StrategySession())
    assert st.gold == 0 and st.gold_readable is True


# ── 3 free_bench_slots 恒 int → None:收球臂,零 SellBench(宁多收不误卖)──

def test_fixture3_free_bench_none_clicks_not_sells():
    d = _decide(_snap(spheres=_two_spheres(), free_bench_slots=None,
                      shop_open=False))
    assert len(d.ops) == 1
    assert d.ops[0].op_key == 'click_spheres:2'
    assert 'sell' not in d.ops[0].op_key


# ── 4 board 恒可读 → None:步级无消费,decide 正常出动作(不崩不空转)──

def test_fixture4_board_none_decide_still_emits_op():
    st = decision_state(_snap(board=None), StrategySession())
    assert st.board == {} and st.board_readable is False
    d = _decide(_snap(board=None, box_overlay_open=True))
    assert d.ops[0].op_key == 'pick_box_card'


# ── 5 spheres 恒空 → 非空(假球位):商店开先关店(live 重叠误检防线)──

def test_fixture5_fake_spheres_with_shop_open_closes_shop_first():
    d = _decide(_snap(spheres=_two_spheres(), free_bench_slots=2,
                      shop_open=True))
    assert d.ops[0].op_key == 'ensure_shop_closed'


# ── 6 event_overlay 恒 None → 非 None:透传(引擎环顶 bail;适配器不吞)──

def test_fixture6_event_overlay_passthrough():
    obs = snapshot_to_obs(_snap(event_overlay='盛会之星'), StrategySession())
    assert obs.event_overlay == '盛会之星'


# ── 7 shop_open 恒 True → False(金/牌可读前提消失,F2 同源)──

def test_fixture7_shop_closed_untrusted_gold():
    snap = _snap(shop_open=False, gold=88, gold_trusted=False)
    obs = snapshot_to_obs(snap, StrategySession())
    assert obs.shop_open is False
    assert obs.state_gold_trusted is False
    assert decision_state(snap, StrategySession()).gold == 0


# ── 8 hp 恒真值 → None + hp_readable False:session 锚,禁 0/100 兜底 ──

def test_fixture8_hp_none_session_anchor():
    sess = StrategySession()
    sess.last_hp = 55
    sess.last_hp_t = 4
    st = decision_state(_snap(hp=None, hp_readable=False, plane=1, round_num=5),
                        sess)
    assert st.hp not in (0, 100)
    assert st.hp == 55   # 同节点 gap≤3 沿用链
    assert st.hp_readable is False


# ── 9 box_overlay_open 恒 False → True:规则 1 首位恒 PickBoxCard ──

def test_fixture9_box_overlay_pick_box_card():
    d = _decide(_snap(box_overlay_open=True))
    assert d.ops[0].op_key == 'pick_box_card'
