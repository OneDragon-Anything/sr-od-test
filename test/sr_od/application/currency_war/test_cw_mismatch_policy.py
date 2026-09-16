"""cw_mismatch_policy 单元锁:豁免注册表三维度查表 + 安灯钩子槽。

锁面来源 = 迭代 2026-09-16-unified-obs-reconcile design.md §2.2/§2.4
(落地判据见同目录 landing.md §3.1)。注册表经 monkeypatch 换测试专用
dict,不污染模块常量(真注册表恒空,扩面走代码 review)。"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_mismatch_policy as policy
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    EXEMPT_ANY,
    ExemptEntry,
    fire_reconcile_andon,
    lookup_mismatch_exempt,
    set_reconcile_andon_hook,
)

PREP_SCREEN: str = '货币战争-备战'


def _entry(screen: str = PREP_SCREEN, field: str = 'gold',
           logic_evidence: str = 'free_refresh@',
           reason: str = '测试条目') -> ExemptEntry:
    return ExemptEntry(screen=screen, field=field,
                       logic_evidence=logic_evidence, reason=reason)


def _install_registry(monkeypatch: pytest.MonkeyPatch,
                      *entries: ExemptEntry) -> None:
    """换入测试专用注册表(键 = (screen, field),同键条目按申报序并存)。"""
    reg: dict[tuple[str, str], tuple[ExemptEntry, ...]] = {}
    for e in entries:
        reg[(e.screen, e.field)] = reg.get((e.screen, e.field), ()) + (e,)
    monkeypatch.setattr(policy, 'EXEMPT_REGISTRY', reg)


def test_lookup_precise_screen_bucket_prefix_hit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """精确桶命中:screen×字段×写端前缀全维命中返回条目(豁免治理三维度)。"""
    _install_registry(monkeypatch, _entry())
    hit = lookup_mismatch_exempt(PREP_SCREEN, 'gold', 'free_refresh@p1-r4')
    assert hit is not None and hit.screen == PREP_SCREEN \
        and hit.logic_evidence == 'free_refresh@', '前缀命中精确桶条目'
    assert lookup_mismatch_exempt(PREP_SCREEN, 'gold', 'post_buy@p1-r4') is None, \
        '同字段他写端不命中(真点击落空不被免刷豁免吞掉)'
    assert lookup_mismatch_exempt('货币战争-简报', 'gold',
                                  'free_refresh@p1-r4') is None, \
        '他画面不命中精确桶(按画面治理)'


def test_lookup_precise_miss_falls_through_to_wildcard_bucket(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """两桶独立评估:精确桶 evidence 不中不阻断通配桶(互不阻断语义)。"""
    _install_registry(monkeypatch, _entry(), _entry(screen=EXEMPT_ANY,
                                                    logic_evidence='post_buy@'))
    hit = lookup_mismatch_exempt(PREP_SCREEN, 'gold', 'post_buy@p1-r2')
    assert hit is not None and hit.screen == EXEMPT_ANY, \
        '精确桶不中 → 通配桶接住'


def test_lookup_screen_none_only_wildcard_can_hit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """sig.screen=None(不可指名画面的写端)→ 精确键不可能命中,仅通配条目。"""
    _install_registry(monkeypatch, _entry())
    assert lookup_mismatch_exempt(None, 'gold', 'free_refresh@p1-r4') is None, \
        'screen=None 精确桶结构性失效,仅通配可豁免'
    _install_registry(monkeypatch, _entry(screen=EXEMPT_ANY))
    assert lookup_mismatch_exempt(None, 'gold',
                                  'free_refresh@p1-r4') is not None


def test_lookup_multi_entries_same_key_first_full_match(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """同 (screen, field) 多条目并存,桶内逐条比对,首条全维命中即返回。"""
    _install_registry(monkeypatch, _entry(logic_evidence='refresh_a@'),
                      _entry(logic_evidence='refresh_b@'))
    hit = lookup_mismatch_exempt(PREP_SCREEN, 'gold', 'refresh_b@p1-r1')
    assert hit is not None and hit.logic_evidence == 'refresh_b@', \
        '首条不中继续桶内比对,次条命中'
    hit2 = lookup_mismatch_exempt(PREP_SCREEN, 'gold', 'refresh_a@p1-r1')
    assert hit2 is not None and hit2.logic_evidence == 'refresh_a@', \
        '首条命中即返回'


def test_lookup_any_evidence_entry_matches_even_none(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """不限写端条目(EXEMPT_ANY):字段无 logic evidence(None)也可命中。"""
    _install_registry(monkeypatch, _entry(logic_evidence=EXEMPT_ANY))
    assert lookup_mismatch_exempt(PREP_SCREEN, 'gold', None) is not None, \
        'EXEMPT_ANY 对无注记写端命中'
    assert lookup_mismatch_exempt(PREP_SCREEN, 'gold', '任意写端@x') is not None


def test_lookup_none_evidence_never_matches_prefix_entry(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """无注记写端(logic_evidence=None)对前缀条目恒不中(禁把「无注记」
    当任意前缀,防豁免误吞)。"""
    _install_registry(monkeypatch, _entry())
    assert lookup_mismatch_exempt(PREP_SCREEN, 'gold', None) is None


def test_andon_hook_slot_default_off_and_best_effort(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """安灯槽缺省关(零副作用)+ best-effort(钩子异常不外抛)两形态一锁。"""
    fired: list[dict] = []
    row = {'field': 'gold'}

    fire_reconcile_andon(row)   # 缺省 None:零副作用,不抛
    monkeypatch.setattr(policy, '_ANDON_HOOK', fired.append)
    fire_reconcile_andon(row)
    assert fired == [row], '接通后同步收到缺陷行'
    monkeypatch.setattr(
        policy, '_ANDON_HOOK',
        lambda _r: (_ for _ in ()).throw(RuntimeError('钩子炸了')))
    fire_reconcile_andon(row)   # 钩子异常被吞,不阻塞写路径


def test_set_reconcile_andon_hook_roundtrip() -> None:
    """注入槽 setter 接通/复位(roundtrip;模块级槽测试后必须还原)。"""
    fired: list[dict] = []
    set_reconcile_andon_hook(fired.append)
    try:
        fire_reconcile_andon({'k': 1})
        assert fired == [{'k': 1}]
    finally:
        set_reconcile_andon_hook(None)
    fired.clear()
    fire_reconcile_andon({'k': 2})
    assert fired == [], '复位后不再触达'
