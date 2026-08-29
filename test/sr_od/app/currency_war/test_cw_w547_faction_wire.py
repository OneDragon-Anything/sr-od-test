"""W547 羁绊对账接线锁(prep_director 备战 heavy 稳定帧消费 cw_faction_obs)。

设计出处:``prep_director.PrepDirector._reconcile_faction_display`` docstring +
``cw_faction_obs`` 对账口径(W545:计算侧=主源,显示侧=对账票;截断/失读/
computed_missing 均只计数不判错)。接线零决策:不一致仅落缺陷台账
(kind=faction_display_mismatch),不纠漂不重读。
"""
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.prep_director as pd
from sr_od.application.currency_war.obs.cw_faction_obs import (
    parse_panel_tokens,
    read_displayed_factions,
)
from sr_od.application.currency_war.prep_director import PrepDirector
from test.conftest import SrTestContext


# ===== 接线源码锁(形态先例=inspect.getsource 静态锁) =====
def test_faction_wire_source_locks() -> None:
    """接线三锁:方法用 cw_faction_obs 三件套且 best-effort;主环在 XP 对账
    同帧之后消费;禁改面(cw_faction_obs)只 import 不含本地重定义。"""
    src = inspect.getsource(PrepDirector._reconcile_faction_display)
    assert 'board_from_tracked(' in src
    assert 'read_displayed_factions(' in src
    assert 'compare_factions(' in src
    assert 'report_faction_reconcile(' in src
    # 零决策:方法不 return 环结果、不做任何游戏交互(无 screenshot/click)
    assert 'round_' not in src.replace('round_num', '')
    assert 'screenshot(' not in src
    # best-effort:异常吞掉不阻塞环(与 _reconcile_xp_expect 同款)
    assert 'except Exception' in src
    loop_src = inspect.getsource(PrepDirector._run_loop)
    xp_at = loop_src.index('self._reconcile_xp_expect(obs)')
    fac_at = loop_src.index('self._reconcile_faction_display(obs)')
    assert fac_at > xp_at, '羁绊对账须与 XP 对账同一 heavy 定型帧、紧随其后'
    mod_src = Path(pd.__file__).read_text(encoding='utf-8')
    assert 'from sr_od.application.currency_war.obs.cw_faction_obs import' in mod_src


# ===== 行为锁(假 reader/假账本,零 OCR/零游戏) =====
def _make_director(monkeypatch: pytest.MonkeyPatch, computed, reading) -> PrepDirector:
    """构造无初始化的 Director:session 挂假 tracked,ctx/cw_match 走 _session
    真路径;board_from_tracked / read_displayed_factions 注入假实现。"""
    d = object.__new__(PrepDirector)
    session = SimpleNamespace(tracked_deployed=[])
    d.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    d.last_screenshot = object()   # 消费帧=last_screenshot(heavy 定型帧,零新增截屏)
    monkeypatch.setattr(pd, 'board_from_tracked', lambda tracked: computed)
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: reading)
    return d


def _tok(text: str, x1: int, y1: int) -> tuple[str, int, int, int, int]:
    return (text, x1, y1, x1 + 28 * max(len(text), 1), y1 + 28)


def _capture_defects(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    # 分包期 4:obs 落账走 kernel.cw_telemetry_exit 出口钩子位,桩点随迁
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    calls: list[dict] = []
    monkeypatch.setattr(cw_telemetry_exit, '_record_defect',
                        lambda *a, **k: calls.append({'args': a, 'kwargs': k}))
    return calls


def test_wire_mismatch_records_defect(monkeypatch: pytest.MonkeyPatch) -> None:
    """不一致 → 逐 mismatch 落台账(kind=faction_display_mismatch),带
    plane/round 与不评口径计数 refs;一致行/截断嫌疑不落。"""
    calls = _capture_defects(monkeypatch)
    reading = parse_panel_tokens(
        [_tok('仙舟', 106, 140), _tok('能量', 106, 240)],
        [_tok('3', 83, 175), _tok('4', 83, 275)])
    d = _make_director(monkeypatch, {'仙舟': 3, '能量': 5}, reading)
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=2, round_num=5)
    d._reconcile_faction_display(obs)
    assert len(calls) == 1
    kw = calls[0]['kwargs']
    assert kw['surface'] == 'board' and kw['kind'] == 'faction_display_mismatch'
    assert kw['expected'] == '5' and kw['observed'] == '4'   # computed(主源) vs 显示
    assert kw['plane'] == 2 and kw['round_num'] == 5
    assert kw['reader_source'] == 'faction_display_reconcile'
    ref_fields = {r['field'] for r in kw['refs']}
    assert {'ocr_skipped', 'unmatched', 'truncated',
            'truncation_suspects', 'computed_missing'} <= ref_fields


def test_wire_match_no_defect(monkeypatch: pytest.MonkeyPatch) -> None:
    """一致 → 零台账(纯对账票,一致不打扰)。"""
    calls = _capture_defects(monkeypatch)
    reading = parse_panel_tokens(
        [_tok('仙舟', 106, 140)], [_tok('3', 83, 175)])
    d = _make_director(monkeypatch, {'仙舟': 3}, reading)
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=1, round_num=2)
    d._reconcile_faction_display(obs)
    assert calls == []


def test_wire_computed_none_or_no_frame_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """computed 不可算(tracked 含未知身份 → None)或无消费帧 → 不评,
    且不触面板 OCR(宁缺勿造)。"""
    calls = _capture_defects(monkeypatch)
    ocr_calls: list = []
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: ocr_calls.append(1))
    d = _make_director(monkeypatch, None, None)
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=1, round_num=1)
    d._reconcile_faction_display(obs)
    d.last_screenshot = None
    d._reconcile_faction_display(obs)
    assert ocr_calls == [] and calls == []


def test_wire_best_effort_on_reader_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """识别异常 → 静默跳过,不阻塞环(best-effort 契约)。"""
    _capture_defects(monkeypatch)
    d = _make_director(monkeypatch, {'仙舟': 3}, None)
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: (_ for _ in ()).throw(RuntimeError('ocr down')))
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=1, round_num=1)
    d._reconcile_faction_display(obs)   # 不抛即过
    d = _make_director(monkeypatch, {'仙舟': 3}, None)
    d._session = lambda: None           # 无 session → 直接跳过
    d._reconcile_faction_display(obs)


# ===== 端到端一例(真 fixture 帧 + 真 OCR;模型不可用 → skip) =====
def _make_real_ocr_ctx(test_context: SrTestContext,
                       monkeypatch: pytest.MonkeyPatch) -> None:
    """真 OCR service 注入(与 W545 同款;模型不可用 → skip)。"""
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    try:
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            pytest.skip('OCR 模型不可用')
    except Exception:
        pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))


_FIX = (Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战'
        / 'shop_closed.webp')
#: 该帧 VLM 亲读真值(W545 对拍表):computed 与显示一致 → 零台账
_TRUTH = {'巡海游侠': 1, '能量': 2, '仙舟': 1, '击破': 1, '昼之半神': 1, '治疗': 1}


def test_wire_end_to_end_fixture(test_context: SrTestContext,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """端到端:真帧识别 → compare → report 转发,一致零台账、污染一条。"""
    from one_dragon.utils import cv2_utils
    if not _FIX.exists():
        pytest.skip(f'fixture 缺:{_FIX.name}')
    _make_real_ocr_ctx(test_context, monkeypatch)
    calls = _capture_defects(monkeypatch)
    img = cv2_utils.read_image(str(_FIX))
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: read_displayed_factions(test_context, img))
    d = _make_director(monkeypatch, dict(_TRUTH), None)
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: read_displayed_factions(test_context, img))
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=1, round_num=1)
    d._reconcile_faction_display(obs)
    assert calls == []                       # 真值一致 → 零台账
    computed_bad = dict(_TRUTH)
    computed_bad['能量'] = 5                  # 污染一个计数
    d = _make_director(monkeypatch, computed_bad, None)
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: read_displayed_factions(test_context, img))
    d._reconcile_faction_display(obs)
    assert len(calls) == 1
    kw = calls[0]['kwargs']
    assert kw['kind'] == 'faction_display_mismatch'
    assert kw['expected'] == '5' and kw['observed'] == '2'
    assert kw['note'] == 'faction=能量'
