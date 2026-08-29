"""W601 合成预览对账激活锁(compare_merge_preview 接线 + compare 行为锁)。

设计出处:``prep_director.PrepDirector._reconcile_merge_preview`` docstring +
``cw_shop_obs.compare_merge_preview`` docstring(激活依据 = W600 批B 数据
充分性评估:reader 产线 136 组同刻重复读数 0 分歧 / 15 非零事件 8 例与持有
台账精确相符,原「多帧闪烁采样」合格线作废)。接线零决策:mismatch 仅落
缺陷台账(kind=merge_preview_mismatch),不 return/不重读不纠错。

行为锁 fixture 素材 = W600 报告的 15 非零事件语料
(``replay/shop_snapshots.jsonl`` 全量扫出的 (槽位, ✦数) 形状,13 个唯一
形状 / 20 次读数;详见该报告「生产级替代证据」节),数据驱动锁 compare
真值表与 det 语义映射(merge_preview>0)。
"""
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.prep_director as pd
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, ShopCard
from sr_od.application.currency_war.obs.cw_shop_obs import (
    MergePreviewCompareRow,
    compare_merge_preview,
)

from sr_od.application.currency_war.prep_director import PrepDirector, _merge_preview_inputs

# ===== 接线源码锁(形态先例=W564 inspect.getsource 静态锁) =====

#: W600 非零事件语料的 (槽位, ✦数) 形状(13 个唯一形状;fixture 素材单一源)。
_W600_NONZERO_SHAPES: list[list[tuple[int, int]]] = [
    [(2, 2)], [(3, 2), (4, 2)], [(2, 1), (4, 1)], [(4, 2)], [(0, 2)],
    [(0, 2)], [(2, 1)], [(0, 2), (1, 2), (4, 2)], [(4, 2)], [(0, 1)],
    [(1, 2)], [(2, 2), (3, 2)], [(3, 2)],
]


def test_merge_preview_wire_source_locks() -> None:
    """接线锁:_reconcile_merge_preview 用 compare_merge_preview 且 best-effort;
    入参折算走 _merge_preview_inputs 单一源;主环在卡池票同帧紧随其后消费;
    零决策(无游戏交互,不 return 环结果)。"""
    mod_src = Path(pd.__file__).read_text(encoding='utf-8')
    assert "compare_merge_preview" in mod_src
    assert "_SHOP_MERGE_DEFECT_KIND = 'merge_preview_mismatch'" in mod_src
    src = inspect.getsource(PrepDirector._reconcile_merge_preview)
    assert 'compare_merge_preview(' in src
    assert '_merge_preview_inputs(' in src
    assert 'record_defect(' in src
    # 零决策:方法不做任何游戏交互(无 screenshot/click/round 流转)
    assert 'round_' not in src.replace('round_num', '')
    assert 'screenshot(' not in src
    assert 'except Exception' in src   # best-effort,不阻塞环
    loop_src = inspect.getsource(PrepDirector._run_loop)
    shop_at = loop_src.index('self._reconcile_shop_pool(obs)')
    merge_at = loop_src.index('self._reconcile_merge_preview(obs)')
    assert merge_at > shop_at, '合成预览对账须与卡池票同一 heavy 定型帧、紧随其后'


# ===== _merge_preview_inputs(入参折算单一源,纯函数) =====


def _state_with_shop(cards: list[ShopCard],
                     bench: list[BenchChar | None] | None = None,
                     deployed: list[BenchChar] | None = None) -> GameState:
    st = GameState(plane=2, round_num=5, level=7)
    st.shop = cards
    if bench is not None:
        st.bench = bench
    if deployed is not None:
        st.deployed = deployed
    return st


def test_merge_inputs_det_mapping_and_unnamed() -> None:
    """det = merge_preview>0(W600 语义映射);未识别牌两侧不参评只计数。"""
    st = _state_with_shop([
        ShopCard(x=100, name='甲', merge_preview=2),
        ShopCard(x=200, name='', merge_preview=0),
        ShopCard(x=300, name='乙', merge_preview=0),
        ShopCard(x=400, name='丙', merge_preview=1),
    ])
    our, det, unnamed = _merge_preview_inputs(st)
    assert det == {0: True, 2: False, 3: True}
    assert our == {0: False, 2: False, 3: False}
    assert unnamed == 1


def test_merge_inputs_our_from_same_star_holding() -> None:
    """our = 全场域同名同星持有 >0(bench∪deployed;跨星不算——3合1 须同星)。"""
    st = _state_with_shop(
        [ShopCard(x=100, name='甲'), ShopCard(x=200, name='乙')],
        bench=[BenchChar(slot=0, char_id='甲', star=1), None,
               BenchChar(slot=2, char_id='乙', star=2)],
        deployed=[BenchChar(slot=0, char_id='甲', star=1)])
    our, det, unnamed = _merge_preview_inputs(st)
    assert our == {0: True, 1: False}   # 甲:bench1+deployed1;乙:仅 2★ 不同星
    assert det == {0: False, 1: False}
    assert unnamed == 0


def test_merge_inputs_empty_shop() -> None:
    """空 shop → 三空(关店帧调用方自带锚门,双保险)。"""
    assert _merge_preview_inputs(_state_with_shop([])) == ({}, {}, 0)
    assert _merge_preview_inputs(GameState()) == ({}, {}, 0)


# ===== compare_merge_preview 行为锁(fixture=W600 非零事件语料,数据驱动) =====


class TestCompareAgainstW600Fixture:
    """真值面 = W600 非零事件形状逐条过 compare 真值表(激活的规格锁)。"""

    @staticmethod
    def _det_of(shape: list[tuple[int, int]]) -> dict[int, bool]:
        return {slot: cnt > 0 for slot, cnt in shape}

    def test_fixture_det_mapping_all_true(self) -> None:
        """事件语料全部 merge_preview>0 → det 恒 True(非零事件语义)。"""
        for shape in _W600_NONZERO_SHAPES:
            det = self._det_of(shape)
            assert det and all(det.values()), f'shape={shape} 应全映射 True'

    def test_holding_matches_detection_is_match(self) -> None:
        """持有台账与识别相符形态(W600 15 事件中 8 例精确相符的形状):
        our=True 且 det=True → match,suspect 空。"""
        for shape in _W600_NONZERO_SHAPES:
            our = {slot: True for slot, _ in shape}
            r = compare_merge_preview(our, self._det_of(shape))
            assert {row.verdict for row in r.rows} == {'match'}
            assert r.suspect_slots == []

    def test_holding_without_sparkle_is_suspect(self) -> None:
        """我方持有 ≥1 副本而识别无✦ → our_suspect(单向罚则唯一对象;
        也是暗相漏检疑云的票形态,双义不逐票判死)。"""
        r = compare_merge_preview({2: True, 4: True}, {2: True, 4: False})
        by_slot = {row.slot: row.verdict for row in r.rows}
        assert by_slot == {2: 'match', 4: 'our_suspect'}
        assert r.suspect_slots == [4]

    def test_sparkle_without_holding_is_game_extra(self) -> None:
        """识别有✦而我方无账 → game_extra 留证不判罚,不出 suspect。"""
        for shape in _W600_NONZERO_SHAPES:
            our = {slot: False for slot, _ in shape}
            r = compare_merge_preview(our, self._det_of(shape))
            assert {row.verdict for row in r.rows} == {'game_extra'}
            assert r.suspect_slots == []

    def test_detected_none_still_pending(self) -> None:
        """preview_detected=None 登记形态保留(全 pending),激活不删契约。"""
        r = compare_merge_preview({0: True}, None)
        assert [row.verdict for row in r.rows] == ['pending']
        assert r.suspect_slots == []
        assert isinstance(r.rows[0], MergePreviewCompareRow)

    def test_zero_preview_is_legal_false_not_missing(self) -> None:
        """merge_preview=0 映射 False 是合法语义(无✦),不等于识别端缺席
        (缺席 = dict 整体 None)——两者分道。"""
        r = compare_merge_preview({0: False}, {0: False})
        assert r.rows[0].verdict == 'match'
        assert r.rows[0].detected is False


# ===== 行为锁(假台账,零 OCR/零游戏;形态同 W564) =====


def _capture_defects(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    from sr_od.application.currency_war.telemetry import defects as tel
    calls: list[dict] = []
    monkeypatch.setattr(tel, 'record_defect',
                        lambda *a, **k: calls.append({'args': a, 'kwargs': k}))
    return calls


def _director() -> PrepDirector:
    d = object.__new__(PrepDirector)
    d.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=SimpleNamespace()))
    return d


def _obs(st: GameState | None, shop_open: bool = True) -> pd.PrepObservation:
    obs = pd.PrepObservation()
    obs.shop_open = shop_open
    obs.state = st
    return obs


def test_merge_wire_mismatch_records_defect(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """our_suspect → 落台账(surface=shop,kind=merge_preview_mismatch),
    带双义不判死 verdict 与槽位 refs。"""
    calls = _capture_defects(monkeypatch)
    d = _director()
    st = _state_with_shop(
        [ShopCard(x=100, name='甲', merge_preview=0)],
        bench=[BenchChar(slot=0, char_id='甲', star=1)])
    d._reconcile_merge_preview(_obs(st))
    assert len(calls) == 1
    assert calls[0]['args'] == ('shop', 'merge_preview_mismatch')
    kw = calls[0]['kwargs']
    assert kw['plane'] == 2 and kw['round_num'] == 5
    assert kw['reader_source'] == 'merge_preview_reconcile'
    assert kw['gap_large'] is True
    assert 'our_suspect' in kw['observed']
    refs = {r['field']: r['value'] for r in kw['refs']}
    assert refs['our_suspect'] == '0'
    assert refs['game_extra'] == ''
    assert refs['unnamed'] == '0'
    assert '已产线' in refs['reader']


def test_merge_wire_game_extra_also_records(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """game_extra(识别有✦而我方无账)同为开票形态(留证不判罚≠不记账)。"""
    calls = _capture_defects(monkeypatch)
    d = _director()
    st = _state_with_shop([ShopCard(x=100, name='甲', merge_preview=2)])
    d._reconcile_merge_preview(_obs(st))
    assert len(calls) == 1
    refs = {r['field']: r['value'] for r in calls[0]['kwargs']['refs']}
    assert refs['game_extra'] == '0' and refs['our_suspect'] == ''


def test_merge_wire_clean_or_closed_or_no_holding_skips(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """全 match / 关店帧 / 空牌 / 无任何持有(our 空集)→ 零台账(一致不打扰)。"""
    calls = _capture_defects(monkeypatch)
    d = _director()
    match_st = _state_with_shop([ShopCard(x=100, name='甲', merge_preview=0)])
    d._reconcile_merge_preview(_obs(match_st))                    # 全 match
    d._reconcile_merge_preview(_obs(match_st, shop_open=False))   # 关店帧
    d._reconcile_merge_preview(_obs(_state_with_shop([])))        # 空牌
    d._reconcile_merge_preview(_obs(None))                        # 无 state
    unnamed_st = _state_with_shop([ShopCard(x=100, name='', merge_preview=1)])
    d._reconcile_merge_preview(_obs(unnamed_st))                  # 仅未识别牌
    assert calls == []


def test_merge_wire_best_effort_on_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """对账异常 → 静默跳过,不阻塞环(best-effort 契约)。"""
    _capture_defects(monkeypatch)
    d = _director()
    monkeypatch.setattr(pd, 'compare_merge_preview',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('down')))
    st = _state_with_shop(
        [ShopCard(x=100, name='甲', merge_preview=2)],
        bench=[BenchChar(slot=0, char_id='甲', star=1)])
    d._reconcile_merge_preview(_obs(st))   # 不抛即过

