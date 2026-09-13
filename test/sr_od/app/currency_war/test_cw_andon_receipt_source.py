"""安灯判定源对拍锁(T-186 切片3;换轨对拍窗一期·纯逻辑对拍,无需实机)。

详设 = docs/develop/sr_od/application/currency_war/changes/
2026-09-13-state-slot-convergence/details/sim-state-switch.md §5「安灯
判定链按 classify_spend_unit 真判定链逐态保留」+ 换轨后数据源 = 精简
访问事实暂存(容器+渠道三源)。

对拍双源(同一输入形态,判定必须一致):
- **旧源** = visit_actions 逐动作 ``serialize_action`` + BuyCardsOutcome
  执行事实字段(退役前 ``_exec_fail_hook_check`` 的输入构造,原样内联);
- **新源** = 访问窗 receipts 发射行(note_shop_action_receipt 写点形态:
  发射行附 ``action`` 载荷 + 刷新行附 refresh 留证 extra;硬墙受阻行仅
  plan_truncated extra 无载荷)经 ``unit_exec_facts_from_receipts`` 派生。

场景覆盖:effective(正常生效)/ not_effective(计划花费>0 金差≈0,唯一
停机态)/ plan_truncated(豁免一:硬墙计划未尝试)/ free_refresh_proc
(豁免二:刷新已尝试∧牌面已变∧金差≈0)/ partial_mismatch(金动了但
对不上账,不停)。分类单一源 = telemetry.query.classify_spend_unit
(纯函数零改),两豁免态 = 其判定序①③,本锁防换轨时逐态语义漂移。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    LevelUpShop,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.telemetry.query import classify_spend_unit
from sr_od.application.currency_war.telemetry.schema import serialize_action

# ---------------------------------------------------------------------------
# 双源构造(形态 = 生产写点原样内联;禁另起第二套分类)
# ---------------------------------------------------------------------------

def _old_source(visit_actions: list, executed: dict, gold_open: int | None):
    """旧源输入构造(BuyCardsOutcome 退役前 _exec_fail_hook_check 原样)。"""
    return {
        'plan_actions': [serialize_action(a) for a in visit_actions],
        'executed': dict(executed),
        'gold_open': gold_open,
    }


def _receipt_row(action, applied: bool, reason: str = '',
                 extra: dict | None = None,
                 include_payload: bool = True) -> dict:
    """发射行形态(note_shop_action_receipt → kernel note_action_receipt)。"""
    row: dict = {'op': type(action).__name__, 'applied': applied,
                 'reason': reason, 'screen': '货币战争-商店'}
    if include_payload:
        row['action'] = serialize_action(action)
    if extra:
        row.update(dict(extra))
    return row


def _new_source(receipt_rows: list, gold_open: int | None):
    """新源输入构造(unit_exec_facts_from_receipts 单一派生口)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        unit_exec_facts_from_receipts,
    )
    return unit_exec_facts_from_receipts(receipt_rows, gold_open)


def _classify(source: dict, gold_close: int | None) -> str:
    return classify_spend_unit(
        source['plan_actions'], source['gold_open'], gold_close,
        boundary='closed', executed=source['executed'])['verdict']


# ---------------------------------------------------------------------------
# 场景夹具(动作序列 / 两源构造 / 期望判定)
# ---------------------------------------------------------------------------

def _scn_effective():
    """正常生效:买 3 金卡,金 20→17(计划花费>0 金差=花费,差≈0)。"""
    visit = [BuyCard(card=ShopCard(x=1, name='希儿', faction='仙舟', cost=3))]
    rows = [_receipt_row(visit[0], applied=True)]
    old_exec = {'plan_truncated': False, 'refresh_attempted': False,
                'refresh_board_changed': None}
    return visit, old_exec, rows, 20, 17, 'effective'


def _scn_not_effective():
    """唯一停机态:计划花费>0 金差≈0(点击落空)。"""
    visit = [BuyCard(card=ShopCard(x=1, name='希儿', faction='仙舟', cost=3))]
    rows = [_receipt_row(visit[0], applied=False,
                         reason='执行未落地(BuyCardOp)')]
    old_exec = {'plan_truncated': False, 'refresh_attempted': False,
                'refresh_board_changed': None}
    return visit, old_exec, rows, 20, 20, 'not_effective'


def _scn_plan_truncated():
    """豁免一:刷新硬墙(计划未尝试,不停)——plan_truncated 走 receipts
    extra(现役写点 = 硬墙受阻行,无动作载荷)。"""
    visit = [BuyCard(card=ShopCard(x=1, name='希儿', faction='仙舟', cost=3))]
    hard_wall = RefreshShop(cost=2)
    rows = [
        _receipt_row(visit[0], applied=True),
        _receipt_row(hard_wall, applied=False,
                     reason='skipped:max_cap(刷新硬墙,计划未尝试)',
                     extra={'plan_truncated': True,
                            'refresh_skipped': 'max_cap'},
                     include_payload=False),
    ]
    old_exec = {'plan_truncated': True, 'refresh_attempted': False,
                'refresh_board_changed': None}
    return visit, old_exec, rows, 20, 17, 'plan_truncated'


def _scn_free_refresh_proc():
    """豁免二:免费刷新生效(刷新已尝试∧牌面已变∧金差≈0,不停+采证)。

    形态 = 计划含付费续段(刷+两买)但实际仅免费刷新落地(两买已发射
    未落地,金照不变)——planned_spend>0 ∧ gap>容差 ∧ |actual|≤容差
    才进豁免支(判定序②后半)。
    """
    visit = [RefreshShop(cost=2),
             BuyCard(card=ShopCard(x=2, name='停云', faction='仙舟', cost=4)),
             BuyCard(card=ShopCard(x=3, name='艾丝妲', faction='仙舟', cost=4))]
    rows = [_receipt_row(visit[0], applied=True,
                         extra={'refresh_board_changed': True}),
            _receipt_row(visit[1], applied=False,
                         reason='执行未落地(BuyCardOp)'),
            _receipt_row(visit[2], applied=False,
                         reason='执行未落地(BuyCardOp)')]
    old_exec = {'plan_truncated': False, 'refresh_attempted': True,
                'refresh_board_changed': True}
    return visit, old_exec, rows, 20, 20, 'free_refresh_proc'


def _scn_refresh_attempted_not_effective():
    """判定序②:计划花费>0、金差≈0,刷新已尝试但牌面未变(False)→
    不入豁免,落 not_effective(付费刷新落空 = 真点击落空类)。"""
    visit = [RefreshShop(cost=2),
             BuyCard(card=ShopCard(x=2, name='停云', faction='仙舟', cost=4))]
    rows = [_receipt_row(visit[0], applied=True,
                         extra={'refresh_board_changed': False}),
            _receipt_row(visit[1], applied=False,
                         reason='执行未落地(BuyCardOp)')]
    old_exec = {'plan_truncated': False, 'refresh_attempted': True,
                'refresh_board_changed': False}
    return visit, old_exec, rows, 20, 20, 'not_effective'


def _scn_partial_mismatch():
    """金动了但对不上账(计划外花销混入:计划 5 金,实付 12),不停。"""
    visit = [LevelUpShop(cost=3), BuyCard(
        card=ShopCard(x=2, name='停云', faction='仙舟', cost=2))]
    rows = [_receipt_row(visit[0], applied=True),
            _receipt_row(visit[1], applied=True)]
    old_exec = {'plan_truncated': False, 'refresh_attempted': False,
                'refresh_board_changed': None}
    return visit, old_exec, rows, 20, 8, 'partial_mismatch'


_SCENARIOS = [
    _scn_effective, _scn_not_effective, _scn_plan_truncated,
    _scn_free_refresh_proc, _scn_refresh_attempted_not_effective,
    _scn_partial_mismatch,
]


@pytest.mark.parametrize('scenario', _SCENARIOS, ids=lambda f: f.__name__)
def test_andon_new_source_matches_old_verdict(scenario):
    """换轨对拍:新源(receipts 派生)与旧源(visit_actions 序列化)在
    classify_spend_unit 判定链上逐态一致。"""
    visit_actions, old_exec, rows, gold_open, gold_close, expected = scenario()
    old_src = _old_source(visit_actions, old_exec, gold_open)
    new_src = _new_source(rows, gold_open)
    assert _classify(old_src, gold_close) == expected
    assert _classify(new_src, gold_close) == expected


def test_andon_new_source_payload_equals_old_serialize():
    """动作序列同 schema:新源发射行载荷 ≡ serialize_action 产物(逐键)。"""
    visit = [BuyCard(card=ShopCard(x=1, name='希儿', faction='仙舟', cost=3)),
             LevelUpShop(cost=2)]
    rows = [_receipt_row(a, applied=True) for a in visit]
    new_src = _new_source(rows, 20)
    assert new_src['plan_actions'] == [serialize_action(a) for a in visit]


def test_andon_new_source_blocked_row_not_in_plan():
    """受阻行(硬墙/闸拒,include_payload=False)不入 plan 序列——与旧
    visit_actions 成员资格同界(计划花费口径不吞未发射动作)。"""
    visit = [BuyCard(card=ShopCard(x=1, name='希儿', faction='仙舟', cost=3))]
    hard_wall = RefreshShop(cost=2)
    rows = [
        _receipt_row(visit[0], applied=True),
        _receipt_row(hard_wall, applied=False, reason='blocked:spend_gate:x',
                     extra={'blocked': 'spend_gate'}, include_payload=False),
    ]
    new_src = _new_source(rows, 20)
    assert [a['__type__'] for a in new_src['plan_actions']] == ['BuyCard']
