"""W545 羁绊显示识别 + 对账锁(显示侧=对账票,计算侧=主源,用户裁决)。

设计出处:``cw_faction_obs`` 模块 docstring + 16 帧 fixture 离线对拍
(``.debug/temp/currency_war/w545_faction_reconcile/REPORT.md``,真值=VLM 逐帧
亲读;批报告属易失产物,语义出处以代码 docstring 为准)。

判读口径:徽章数字(白字黑底单数字)= 该羁绊当前单位数;灰梯档位不读
(档位由注册表计算);底部截断条目(名可见徽章被面板裁掉)只计数不判错。
"""
from pathlib import Path

import pytest

from sr_od.application.currency_war.cw_faction_obs import (
    FactionReconcileResult,
    _match_faction,
    compare_factions,
    parse_panel_tokens,
    read_displayed_factions,
    report_faction_reconcile,
)
from test.conftest import SrTestContext

_FIX_DIR = Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战'


# ===== 名称→注册表匹配真值表(精确优先;LCS 兜底防邻项误配) =====
def test_match_faction_truth_table() -> None:
    """精确命中;唯一 LCS 兜底;一字差邻项并列/低比例不猜。"""
    assert _match_faction('仙舟') == '仙舟'
    assert _match_faction('列车同行') == '列车同行'
    assert _match_faction('昼之半神') == '昼之半神'
    assert _match_faction('星辰大海') is None        # 完全不沾边
    # 仅一字差的两邻项:候选文本同时接近昼/夜之半神 → 并列不猜
    assert _match_faction('X之半神') is None
    # 唯一高比例兜底(艺术字缺字形态)
    assert _match_faction('战技') == '战技点'


# ===== 对账纯函数真值表(逐名三态 + 不评口径 + 截断嫌疑) =====
def test_compare_factions_truth_table() -> None:
    """一致/不一致/显示侧不可判三态;OCR 失读跳过;computed 独有为截断嫌疑。"""
    r = compare_factions(
        {'仙舟': 3, '能量': 5, '欢愉': 1, '列车同行': 2},
        [('仙舟', 3), ('能量', 4), ('欢愉', 1)],
        unreadable=['战技点'])
    assert isinstance(r, FactionReconcileResult)
    assert [(row.faction, row.verdict) for row in r.rows] == [
        ('仙舟', 'match'), ('能量', 'mismatch'), ('欢愉', 'match')]
    assert r.ocr_skipped == ['战技点']                  # 失读只计数,不成行
    assert r.truncation_suspects == ['列车同行']        # computed 有显示无 = 截断嫌疑
    assert r.mismatch_count == 1


def test_compare_factions_computed_missing_explicit() -> None:
    """显示有而计算无 = computed_missing 显式态(计算侧是全集主源)。"""
    r = compare_factions({'仙舟': 2}, [('仙舟', 2), ('狼狩', 1)])
    assert r.rows[1].verdict == 'computed_missing'
    assert r.rows[1].computed is None and r.rows[1].displayed == 1


# ===== 解析层真值表(锚点提取 + 徽章配对 + 截断标记,纯构造) =====
def _tok(text: str, x1: int, y1: int) -> tuple[str, int, int, int, int]:
    """构造 token(text, x1, y1, x2, y2),高 28、宽按字数。"""
    return (text, x1, y1, x1 + 28 * max(len(text), 1), y1 + 28)


def test_parse_panel_pairs_badge_by_offset_window() -> None:
    """徽章在名 cy+8~65 窗内配对;灰梯(含/)不成为锚点。"""
    names = [_tok('仙舟', 106, 140), _tok('2/3', 110, 205), _tok('能量', 106, 240)]
    badges = [_tok('1', 83, 175), _tok('2', 83, 275)]
    r = parse_panel_tokens(names, badges)
    assert r.entries == [('仙舟', 1), ('能量', 2)]
    assert not r.unreadable and not r.unmatched and not r.truncated


def test_parse_panel_last_anchor_without_badge_is_truncated() -> None:
    """最后一条无徽章 = 截断(名可对上→unreadable+truncated;对不上→unmatched)。"""
    names = [_tok('仙舟', 106, 140), _tok('盛会之星', 107, 732)]
    badges = [_tok('2', 87, 175)]
    r = parse_panel_tokens(names, badges)
    assert r.entries == [('仙舟', 2)]
    assert r.unreadable == ['盛会之星'] and r.truncated
    # 残名对不上注册表:进 unmatched,仍标 truncated
    r2 = parse_panel_tokens([_tok('仙舟', 106, 140), _tok('残缺名', 107, 732)], badges)
    assert r2.unmatched == ['残缺名'] and r2.truncated


def test_parse_panel_badge_out_of_range_ignored() -> None:
    """徽章数字越界(>12)= OCR 误读,不配对 → 条目失读。"""
    names = [_tok('仙舟', 106, 140)]
    badges = [_tok('99', 83, 175)]
    r = parse_panel_tokens(names, badges)
    assert r.entries == [] and r.unreadable == ['仙舟']


# ===== 真帧终态锁(16 帧对拍代表集;模型不可用 → skip) =====
# 真值 = VLM 逐帧亲读(名+徽章数);truncated 条目名列在截断位不计 entries。
_EXPECTS: dict[str, list[tuple[str, int]]] = {
    'r1_idle_stop.webp': [],                                   # 空面板
    'shop_closed.webp': [('巡海游侠', 1), ('能量', 2), ('仙舟', 1), ('击破', 1),
                         ('昼之半神', 1), ('治疗', 1)],
    '后排8槽-P3局.webp': [('领航员', 1), ('列车同行', 4), ('能量', 4), ('战技点', 2),
                       ('仙舟', 2), ('昼之半神', 1), ('欢愉', 1)],   # 特殊态+底部截断
    '后排8槽-满级局.webp': [('领航员', 1), ('列车同行', 5), ('仙舟', 3), ('能量', 3),
                        ('战技点', 2), ('欢愉', 2), ('盛会之星', 1)],
    '补给节点.webp': [('狼狩', 1), ('夜之半神', 1), ('燃血', 1), ('列车同行', 1),
                     ('减益', 1), ('战技点', 1), ('持续伤害', 1)],
    '后排6槽-P2开局局.webp': [('盛会之星', 3), ('列车同行', 2), ('战技点', 2),
                          ('量子同频', 2), ('护盾', 2), ('仙舟', 1), ('击破', 1)],
    '攻略已应用.webp': [('领航员', 1), ('列车同行', 4), ('战技点', 3), ('盛会之星', 2),
                     ('护盾', 2), ('仙舟', 1), ('能量', 1)],
    'deployed_p1r9.webp': [('领航员', 1), ('能量', 2), ('仙舟', 1), ('群攻', 1),
                           ('贝洛伯格', 1), ('列车同行', 1), ('减益', 1)],
}
_TRUNCATED = {
    '后排8槽-P3局.webp': ['盛会之星'],
    '后排8槽-满级局.webp': ['治疗'],
    '补给节点.webp': ['盛会之星'],
    '后排6槽-P2开局局.webp': ['追击'],
    '攻略已应用.webp': ['昼之半神'],
    'deployed_p1r9.webp': ['银河学者'],
}


def _make_real_ocr_ctx(test_context: SrTestContext,
                       monkeypatch: pytest.MonkeyPatch) -> None:
    """真 OCR service 注入(与 W529 同款;模型不可用 → skip)。"""
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    try:
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            pytest.skip('OCR 模型不可用')
    except Exception:
        pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))


@pytest.mark.parametrize('filename', sorted(_EXPECTS))
def test_read_displayed_factions_real_fixtures(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        filename: str) -> None:
    """16 帧对拍代表集终态锁:名称/徽章数逐条读对,截断如实标记。"""
    from one_dragon.utils import cv2_utils
    if not (_FIX_DIR / filename).exists():
        pytest.skip(f'fixture 缺:{filename}')
    _make_real_ocr_ctx(test_context, monkeypatch)
    img = cv2_utils.read_image(str(_FIX_DIR / filename))
    reading = read_displayed_factions(test_context, img)
    assert reading.entries == _EXPECTS[filename], filename
    assert sorted(reading.unreadable) == sorted(_TRUNCATED.get(filename, [])), filename
    assert reading.truncated == (filename in _TRUNCATED), filename


def test_report_faction_reconcile_forwards_mismatches_only(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """台账转发锁:逐 mismatch 落 record_defect(kind=faction_display_mismatch)。"""
    import sr_od.application.currency_war.cw_telemetry as tel
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(tel, 'record_defect',
                        lambda *a, **k: calls.append((a, k)))
    r = compare_factions({'仙舟': 3, '能量': 5}, [('仙舟', 3), ('能量', 4)])
    n = report_faction_reconcile(r, round_num=3)
    assert n == 1 and len(calls) == 1
    args, kwargs = calls[0]
    assert kwargs['surface'] == 'board'
    assert kwargs['kind'] == 'faction_display_mismatch'
    assert kwargs['expected'] == '5' and kwargs['observed'] == '4'
    assert kwargs['note'] == 'faction=能量' and kwargs['round_num'] == 3
