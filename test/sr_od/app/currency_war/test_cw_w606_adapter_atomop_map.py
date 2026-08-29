"""W606 批③·PrepAction→AtomOp 映射与绑定回放锁(设计 §4)。

锁面:
1. 14 原子/组合动作 → op_key(参数指纹)/domain 全集(op_key 粒度 =
   动作类型+参数,同族不同参数=不同幂等键);
2. 控制流不产 op:DeferSpheres→Decision(control=Defer)、BailToOuter→Bail;
3. 绑定回放:decide 登记的 op_key → execute 回放同一 PrepAction 给执行器;
4. 查无绑定 = 缺陷路径(progressed=False);
5. 未登记动作显式抛错(禁静默;F3 白名单同纪律)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_assembly import DecideAdapter
from sr_od.application.currency_war.decision.decision_v2.contracts import (
    AtomOp,
    Bail,
    Defer,
    Snapshot,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    BailToOuter,
    ClickSpheres,
    DeferSpheres,
    DeployMove,
    EnsureShopClosed,
    EnsureShopOpen,
    LevelUp,
    OpenBox,
    OpenTome,
    PickBoxCard,
    RunBuyPhase,
    RunDeploy,
    RunEquip,
    SellBench,
    SellDeployed,
    StartBattle,
)

_EXPECTED_KEYS = [
    (PickBoxCard(), 'pick_box_card'),
    (OpenBox(), 'open_box'),
    (OpenTome(), 'open_tome'),
    (LevelUp(), 'level_up'),
    (EnsureShopOpen(), 'ensure_shop_open'),
    (EnsureShopClosed(), 'ensure_shop_closed'),
    (StartBattle(), 'start_battle'),
    (RunBuyPhase(), 'run_buy_phase'),
    (RunDeploy(), 'run_deploy'),
    (RunEquip(), 'run_equip'),
]
_EXPECTED_KEYED = [
    (SellBench(3), 'sell_bench:3'),
    (SellDeployed('front', 2), 'sell_deployed:front:2'),
    (DeployMove(5, 'back', 3), 'deploy:5:back:3'),
    (ClickSpheres(max_k=2), 'click_spheres:2'),
]
_EXPECTED_DOMAINS = {
    'pick_box_card': 'interact', 'open_box': 'interact',
    'open_tome': 'interact', 'click_spheres': 'interact',
    'sell_bench': 'bench', 'sell_deployed': 'bench', 'deploy': 'bench',
    'level_up': 'shop', 'ensure_shop_open': 'shop',
    'ensure_shop_closed': 'shop', 'start_battle': 'battle',
    'run_buy_phase': 'shop', 'run_deploy': 'deploy', 'run_equip': 'equip',
}


def _from_sr():
    from sr_od.application.currency_war.decision.decision_v2.adapter import (
        action_to_atomop,
    )
    return action_to_atomop


def test_full_action_set_maps_to_expected_keys_and_domains():
    action_to_atomop = _from_sr()
    for action, key in _EXPECTED_KEYS:
        op = action_to_atomop(action)
        assert op.op_key == key
        assert op.domain == _EXPECTED_DOMAINS[key]
    for action, key in _EXPECTED_KEYED:
        op = action_to_atomop(action)
        assert op.op_key == key   # 参数指纹入键:SellBench(3)≠SellBench(5)
        assert op.domain == _EXPECTED_DOMAINS[key.split(':')[0]]
    assert action_to_atomop(SellBench(5)).op_key == 'sell_bench:5'


def test_same_family_different_params_distinct_keys():
    action_to_atomop = _from_sr()
    assert (action_to_atomop(SellBench(3)).op_key
            != action_to_atomop(SellBench(5)).op_key)


def test_control_flow_actions_do_not_produce_ops():
    """DeferSpheres/BailToOuter 走 Decision.control(框架信号不经 execute)。"""
    from sr_od.application.currency_war.decision.decision_v2.contracts import (
        SubstateClassification,
    )

    class _Strat:
        def decide_prep_action(self, obs, session, config):
            return DeferSpheres()

    ad = DecideAdapter(_Strat(), config=None, executor=None)
    d = ad.decide(Snapshot(classification=SubstateClassification(
        name='prep_shop', confident=True)), StrategySession())
    assert d.ops == () and isinstance(d.control, Defer)

    class _Strat2(_Strat):
        def decide_prep_action(self, obs, session, config):
            return BailToOuter(reason='事件overlay:x')

    ad2 = DecideAdapter(_Strat2(), config=None, executor=None)
    d2 = ad2.decide(Snapshot(classification=SubstateClassification(
        name='prep_shop', confident=True)), StrategySession())
    assert d2.ops == () and isinstance(d2.control, Bail)
    assert '事件overlay' in d2.control.reason


def test_binding_replay_executes_same_action():
    """decide 登记 op_key → execute 回放同一 PrepAction 给现役执行器。"""
    from sr_od.application.currency_war.decision.decision_v2.contracts import (
        SubstateClassification,
    )

    sent = SellBench(4)

    class _Strat:
        def decide_prep_action(self, obs, session, config):
            return sent

    executed = {}

    class _Exec:
        def execute(self, action):
            executed['action'] = action
            return True, 'ok'

    ad = DecideAdapter(_Strat(), config=None, executor=_Exec())
    d = ad.decide(Snapshot(classification=SubstateClassification(
        name='prep_shop', confident=True)), StrategySession())
    assert len(d.ops) == 1
    progressed, detail = ad.execute(d.ops[0])
    assert progressed is True and detail == 'ok'
    assert executed['action'] == sent   # dataclass 值相等:全参数回放


def test_execute_without_binding_is_defect_path():
    ad = DecideAdapter(None, config=None, executor=None)
    progressed, detail = ad.execute(AtomOp(op_key='nope', domain='shop'))
    assert progressed is False
    assert '无绑定' in detail


def test_unregistered_action_raises_loudly():
    action_to_atomop = _from_sr()

    class _Ghost:
        pass

    with pytest.raises(ValueError):
        action_to_atomop(_Ghost())
