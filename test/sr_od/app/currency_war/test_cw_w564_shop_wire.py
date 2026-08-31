"""W564 商店对账接线锁(prep_director heavy 帧消费 cw_shop_obs)。

设计出处:``prep_director.PrepDirector._reconcile_shop_pool`` docstring +
``cw_shop_obs`` 对账口径(W556:违例只留证不判哪边错;pool_state 无账本
传 None = 只查 tier 门,如实降级)。接线零决策:违例仅落缺陷台账
(kind=shop_pool_violation),不 return/不重读。刷新期望本批落 producer
契约(build_refresh_expect,None 口径单一源)+ 消费判据
(refresh_reconcile_mismatches)纯函数;评估窗在 shop.py 刷新波内(挂账,
见 build_refresh_expect docstring 的架构证据链)。
"""
from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.prep_director as pd
from sr_od.application.currency_war.kernel.cw_state import GameState, ShopCard
from sr_od.application.currency_war.obs.cw_shop_obs import RefreshExpect

from sr_od.application.currency_war.prep_director import PrepDirector, build_refresh_expect, refresh_reconcile_mismatches

# ===== _shop_pool_inputs(参评牌过滤,纯函数)=====


def _state_with_shop(cards: list[ShopCard]) -> GameState:
    st = GameState(plane=2, round_num=5, level=7)
    st.shop = cards
    return st


def test_pool_inputs_filters_unnamed() -> None:
    """未识别牌(name 空)不参评(空名+0费=invalid_cost 假票),只计数。"""
    st = _state_with_shop([
        ShopCard(x=100, name='甲', cost=1),
        ShopCard(x=200, name='', cost=0),
        ShopCard(x=300, name='乙', cost=2),
    ])
    cards, unnamed = pd._shop_pool_inputs(st)
    assert cards == [('甲', 1), ('乙', 2)]
    assert unnamed == 1


def test_pool_inputs_empty_shop() -> None:
    """shop 关态帧 read_shop_cards 返空 → 无参评牌(调用方天然跳过)。"""
    st = _state_with_shop([])
    assert pd._shop_pool_inputs(st) == ([], 0)
    assert pd._shop_pool_inputs(GameState()) == ([], 0)


# ===== build_refresh_expect(producer 契约,None 口径单一源)=====


class TestBuildRefreshExpect:
    def test_cost_none_skips(self) -> None:
        """刷费读不到(None)→ 跳过对账;禁 or-2 合并(不兜 2)。"""
        assert build_refresh_expect(10, None, [], 1, 1) is None

    def test_gold_none_skips(self) -> None:
        """开店金失读(None)→ 同跳(宁缺勿造)。"""
        assert build_refresh_expect(None, 2, [], 1, 1) is None

    def test_true_zero_preserved(self) -> None:
        """真 0(免费刷/减免档)原样保 0:gold_after==gold_before、不判不足。
        与 None 分道——0 是「读到的免费」,None 是「读不到」,绝不混写。"""
        r = build_refresh_expect(10, 0, [('甲', 1)], 1, 1)
        assert r is not None
        expect, plane, round_num = r
        assert expect.refresh_cost == 0
        assert expect.gold_after == 10
        assert expect.insufficient is False
        assert (plane, round_num) == (1, 1)

    def test_normal_and_insufficient(self) -> None:
        """正常扣费与金不足(算术差如实为负,判归调用方)。"""
        r = build_refresh_expect(10, 3, [], 2, 5)
        assert r is not None and r[0].gold_after == 7
        r = build_refresh_expect(1, 2, [], 2, 5)
        assert r is not None and r[0].gold_after == -1 and r[0].insufficient

    def test_cards_old_pooling(self) -> None:
        """旧五张回池账经 cw_shop_obs.refresh_expect 按名合并计数。"""
        r = build_refresh_expect(8, 2, [('甲', 1), ('甲', 1), ('乙', 2)], 1, 1)
        assert r is not None and r[0].pool_returned == {'甲': 2, '乙': 1}


# ===== refresh_reconcile_mismatches(消费判据,纯函数)=====


class TestRefreshReconcileMismatches:
    @staticmethod
    def _expect(gold_before: int = 10, cost: int = 2) -> RefreshExpect:
        return RefreshExpect(gold_before=gold_before, gold_after=gold_before - cost,
                             refresh_cost=cost, insufficient=gold_before < cost)

    def test_all_match(self) -> None:
        assert refresh_reconcile_mismatches(self._expect(), 8, 5) == []

    def test_gold_mismatch(self) -> None:
        m = refresh_reconcile_mismatches(self._expect(), 7, 5)
        assert m == [{'domain': 'gold', 'slot': '-', 'expected': '8', 'observed': '7'}]

    def test_gold_unreadable_not_judged(self) -> None:
        """金失读(None)→ 金腿不评(宁缺勿造,不猜)。"""
        assert refresh_reconcile_mismatches(self._expect(), None, 5) == []

    def test_no_cards_is_violation(self) -> None:
        """刷新后一格有身份牌都没有 → 刷新未生效形态,开票。"""
        m = refresh_reconcile_mismatches(self._expect(10, 0), 10, 0)
        assert m == [{'domain': 'cards', 'slot': '-',
                      'expected': '>=1', 'observed': '0'}]

    def test_partial_slots_not_judged(self) -> None:
        """1-4 张不判错(低等级后槽未解锁常态,槽位解锁规则未建模)。"""
        assert refresh_reconcile_mismatches(self._expect(), 8, 3) == []

    def test_combined_legs(self) -> None:
        m = refresh_reconcile_mismatches(self._expect(), 5, 0)
        assert {x['domain'] for x in m} == {'gold', 'cards'}


# ===== 行为锁(假 reader/假台账,零 OCR/零游戏)=====


def _make_director(monkeypatch: pytest.MonkeyPatch,
                   violations: list) -> PrepDirector:
    """构造无初始化的 Director;check_shop_pool 注入假实现。"""
    d = object.__new__(PrepDirector)
    session = SimpleNamespace()
    d.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    monkeypatch.setattr(pd, 'check_shop_pool', lambda cards, level, pool_state:
                        violations)
    return d


def _capture_defects(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    from sr_od.application.currency_war.telemetry import defects as tel
    calls: list[dict] = []
    monkeypatch.setattr(tel, 'record_defect',
                        lambda *a, **k: calls.append({'args': a, 'kwargs': k}))
    return calls


def _shop_obs(st: GameState | None, shop_open: bool = True) -> pd.PrepObservation:
    obs = pd.PrepObservation()
    obs.shop_open = shop_open
    obs.state = st
    return obs


def test_pool_wire_violation_records_defect(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """违例 → 落台账(surface=shop,kind=shop_pool_violation),带降级披露 refs。"""
    calls = _capture_defects(monkeypatch)
    viol = SimpleNamespace(name='甲', cost=5, kind='tier_locked', detail='p=0')
    d = _make_director(monkeypatch, [viol])
    st = _state_with_shop([ShopCard(x=100, name='甲', cost=5),
                           ShopCard(x=200, name='', cost=0)])
    d._reconcile_shop_pool(_shop_obs(st))
    assert len(calls) == 1
    assert calls[0]['args'] == ('shop', 'shop_pool_violation')
    kw = calls[0]['kwargs']
    assert kw['plane'] == 2 and kw['round_num'] == 5
    assert kw['reader_source'] == 'shop_pool_reconcile'
    assert kw['gap_large'] is True
    assert 'tier_locked' in kw['observed'] and 'p=0' in kw['observed']
    refs = {r['field']: r['value'] for r in kw['refs']}
    assert refs['level'] == '7' and refs['cards'] == '1' and refs['unnamed'] == '1'
    assert 'None' in refs['pool_state']   # 池守恒查降级如实披露


def test_pool_wire_clean_or_closed_or_empty_skips(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """零违例 / 关店帧 / 空牌帧 → 零台账(一致不打扰,宁缺勿造)。"""
    calls = _capture_defects(monkeypatch)
    d = _make_director(monkeypatch, [])
    st = _state_with_shop([ShopCard(x=100, name='甲', cost=1)])
    d._reconcile_shop_pool(_shop_obs(st))            # 零违例
    d._reconcile_shop_pool(_shop_obs(st, shop_open=False))   # 关店帧
    d._reconcile_shop_pool(_shop_obs(_state_with_shop([])))  # 空牌
    d._reconcile_shop_pool(_shop_obs(None))          # 无 state
    assert calls == []


def test_pool_wire_best_effort_on_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """违例票异常 → 静默跳过,不阻塞环(best-effort 契约)。"""
    _capture_defects(monkeypatch)
    d = _make_director(monkeypatch, [])
    monkeypatch.setattr(pd, 'check_shop_pool',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('down')))
    st = _state_with_shop([ShopCard(x=100, name='甲', cost=1)])
    d._reconcile_shop_pool(_shop_obs(st))   # 不抛即过

