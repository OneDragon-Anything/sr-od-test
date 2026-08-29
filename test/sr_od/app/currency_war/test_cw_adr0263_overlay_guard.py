# -*- coding: utf-8 -*-
"""ADR-0263 Revision summon/bookcard 钩子 overlay 排除测试(局69 误触实证锁)。

Revision(ADR-0269 合并):`_KNOWN_OVERLAYS` 注册表 + `prep_areas_unobstructed`
退役;summon/bookcard 钩子的 overlay 排除改为 —— ①两段式帧态门
(``is_prep_like_frame``,上层屏在场=非 prep-like=跳过,见 ADR-0269 测试);
②金币说明(C 类无档案 overlay,进不了 UPPER_SCREENS)锚 OCR 判定作补充
第三段(``cw_obs_core.gold_info_overlay_open``)。

测试:
- 函数层:锚命中/锚未命中/锚 area 缺失 三态;
- 钩子层(mock OCR/CV):金币说明锚命中 + slot 占用未识别 → 不触发停机;
  锚未命中 → 正常判定停机;帧非 prep-like(上层屏)→ 门前置拦截不停机。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from one_dragon.base.geometry.rectangle import Rect

# 证据帧(034f8ef3)实测:金币说明面板标题锚 pc_rect (1000,370,1165,435),
# 覆盖带盖备战栏 slot6 (1004,847,1118,978);slot1 (382,845,495,979) 在带外。
_SLOT6 = Rect(1004, 847, 1118, 978)


class _OcrItem:
    """最小 OcrMatchResult 替身(守卫只读 .data)。"""

    def __init__(self, data: str) -> None:
        self.data = data


class _FakeCtx:
    """只喂 cw_obs_core 依赖(_area_rect/_ocr 均被 monkeypatch,不需要真服务)。"""

    run_context = None


@pytest.fixture
def anchor_env(monkeypatch):
    """mock cw_obs_core 的 area/OCR 依赖:锚 area 恒有 rect,OCR 返回锚文本。"""
    from sr_od.application.currency_war.kernel import cw_obs_core

    class _Item:
        data = '金币说明'

    monkeypatch.setattr(cw_obs_core, '_area_rect',
                        lambda ctx, name, screen_name=None: Rect(1000, 370, 1165, 435))
    monkeypatch.setattr(cw_obs_core, '_ocr', lambda ctx, screen, rect: [_Item()])
    return cw_obs_core, monkeypatch


def test_gold_anchor_hit(anchor_env) -> None:
    """金币说明锚 OCR 命中 → overlay 判开(True)。"""
    mod, _ = anchor_env
    ctx = _FakeCtx()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    assert mod.gold_info_overlay_open(ctx, screen) is True


def test_gold_anchor_miss(anchor_env, monkeypatch) -> None:
    """锚 OCR 未命中(overlay 关)→ False。"""
    mod, _ = anchor_env
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: [])
    ctx = _FakeCtx()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    assert mod.gold_info_overlay_open(ctx, screen) is False


def test_gold_anchor_area_missing(anchor_env, monkeypatch) -> None:
    """锚 area 缺失(screen_info 无档)→ best-effort False(不拦)。"""
    mod, _ = anchor_env
    monkeypatch.setattr(mod, '_area_rect',
                        lambda ctx, name, screen_name=None: None)
    ctx = _FakeCtx()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    assert mod.gold_info_overlay_open(ctx, screen) is False


def test_overlay_registry_retired() -> None:
    """ADR-0263 Revision:_KNOWN_OVERLAYS / prep_areas_unobstructed 退役删除,
    全仓(src)无引用残留。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert not hasattr(cw_obs_core, 'prep_areas_unobstructed')
    assert not hasattr(cw_obs_core, '_KNOWN_OVERLAYS')


# ===== 钩子层:summon 钩子三态(mock OCR/CV,验证排除链接线) =====

class _FakeOcrService:
    def __init__(self, texts: list[str]) -> None:
        self._texts = [_OcrItem(t) for t in texts]

    def get_ocr_result_list(self, **kwargs):   # noqa: ANN003 ARG003 兼容签名
        return list(self._texts)


class _FakeRunContext:
    def __init__(self) -> None:
        self.stops: list[str] = []

    def stop_running(self, reason: str = '') -> None:
        self.stops.append(reason)


class _HookCtx(_FakeCtx):
    def __init__(self, ocr_texts: list[str]) -> None:
        self.ocr_service = _FakeOcrService(ocr_texts)
        self.run_context = _FakeRunContext()


@pytest.fixture
def hook_env(monkeypatch, tmp_path):
    """mock 掉 CV/OCR 依赖,只留 summon 钩子判定链(chdir tmp 防真实 .debug 落盘)。"""
    from sr_od.application.currency_war.obs import cw_identity_obs, currency_war_cv
    from sr_od.application.currency_war.kernel import cw_obs_core, cw_observe
    monkeypatch.chdir(tmp_path)
    # 生产约定:.debug/temp/currency_war/ 已存在(flag/shots 落盘处);tmp 里预建,
    # 否则 flag write_text 抛错被钩子外层 best-effort except 吞掉,测不到停机分支
    (tmp_path / '.debug/temp/currency_war').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cw_identity_obs, 'identify_slots', lambda *a, **k: [])
    monkeypatch.setattr(cw_identity_obs, '_ctx_slots',
                        lambda ctx, prefix, count: [(6, _SLOT6)])
    monkeypatch.setattr(cw_identity_obs, 'find_supply_boxes', lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_tomes', lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards', lambda screen, slots: [])
    # cw_identity_obs 顶部 `from cw_obs_core import _area_rect` 绑定的是直接引用,
    # 面板守卫(按钮-装备推荐)走它 → 两侧都要 patch(角色详情面板 area 缺 → None)
    monkeypatch.setattr(cw_identity_obs, '_area_rect',
                        lambda ctx, name, screen_name=None: None)
    monkeypatch.setattr(cw_obs_core, 'is_prep_like_frame', lambda ctx, screen: True)
    monkeypatch.setattr(currency_war_cv, 'slot_occupied', lambda screen, x, y: True)
    # 锚接线:标识-金币说明 area 有 rect,OCR 由 per-test 控制
    monkeypatch.setattr(cw_obs_core, '_area_rect',
                        lambda ctx, name, screen_name=None:
                        Rect(1000, 370, 1165, 435) if name == '标识-金币说明' else None)
    shots: list[str] = []

    def _fake_shot(screen, prefix):
        shots.append(prefix)
        return f'{prefix}.png'

    monkeypatch.setattr(cw_observe, 'cw_shot_unique', _fake_shot)
    return cw_identity_obs, cw_obs_core, shots, tmp_path, monkeypatch


def test_summon_hook_skips_when_overlay_open(hook_env) -> None:
    """局69 误触态:slot6 占用未识别 + 金币说明锚命中 → 排除,不停机。"""
    mod, core, shots, tmp_path, monkeypatch = hook_env

    class _Item:
        data = '金币说明'

    monkeypatch.setattr(core, '_ocr', lambda ctx, screen, rect: [_Item()])
    ctx = _HookCtx(['连胜', '金币说明', '2-4'])
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    mod.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == []                     # 不停机
    assert shots == []                                     # 不采证
    assert not (tmp_path / '.debug/temp/currency_war/summon_stop_hook.flag').exists()


def test_summon_hook_stops_when_overlay_closed(hook_env) -> None:
    """对照态:锚 OCR 未命中(overlay 关)→ 正常判定停机 + sentinel flag。"""
    mod, core, shots, tmp_path, monkeypatch = hook_env
    monkeypatch.setattr(core, '_ocr', lambda ctx, screen, rect: [])
    ctx = _HookCtx(['备战阶段', '金币 35'])
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    mod.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == ['hook:summon_unknown']
    assert shots == ['summon_unknown']
    assert (tmp_path / '.debug/temp/currency_war/summon_stop_hook.flag').exists()


def test_summon_hook_skips_when_upper_screen(hook_env) -> None:
    """ADR-0269 两段式:帧态门(上层屏在场)在前,非 prep-like 帧不停机
    (即使金币说明锚也未命中)。"""
    mod, core, shots, tmp_path, monkeypatch = hook_env
    monkeypatch.setattr(core, 'is_prep_like_frame', lambda ctx, screen: False)
    monkeypatch.setattr(core, '_ocr', lambda ctx, screen, rect: [])
    ctx = _HookCtx(['选择伙伴'])
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    mod.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == []
    assert shots == []
