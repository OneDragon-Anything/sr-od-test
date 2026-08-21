# -*- coding: utf-8 -*-
"""gate 原语 fixture 回放测试(r323;用户指路:用建档图做 fixture)。

今天(2026-08-23)gate 在实机暴露的两个 bug,本文件用既有
fixture 截图离线回放锁死——以后 gate 语义改动跑这里即知:
1. 局35:奖励面板帧(1-1 reward 节点)——关态 gate 应放行
   (圆数门误杀的形态;现 absence 锚修法下仍应放行);
2. 指纹阈值:同一 fixture 连续喂两帧=必稳定(字节恒等被
   截屏噪声否决后,阈值比较在同源图上必过);
3. 开态帧(shop_open)——关态 profile 应拒绝(absence 锚)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.cw_observation_gate import (
    PROFILE_CLOSED,
    PROFILE_OPEN,
    _fingerprint,
    _fp_same,
    wait_stable_frame,
)


class _FixtureOp:
    """把 fixture 截图喂给 gate 的桩 op(带 ctx 供锚识别)。"""

    def __init__(self, ctx, frame):
        self.ctx = ctx
        self._frame = frame
        self.park_calls = 0

    def park_cursor(self, **kw):
        self.park_calls += 1

    def screenshot(self):
        return self._frame

    def round_by_ocr(self, frame, kw, **kwargs):
        return _Res(self._has(kw))

    def round_by_find_area(self, frame, scr, area, **kwargs):
        return _Res(self._area_hit(scr, area))

    # —— 识别委托真实框架(test_context 建档齐全)——
    def _has(self, kw: str) -> bool:
        from one_dragon.base.geometry.rectangle import Rect
        texts = [m.data for m in self.ctx.ocr_service.get_ocr_result_list(
            image=self._frame, rect=Rect(0, 0, 1920, 1080))]
        return any(kw in t for t in texts)

    def _area_hit(self, scr: str, area: str) -> bool:
        """真框架找锚(load_screen 的 ctx 已注册 screen_info)。"""
        from sr_od.application.currency_war.cw_obs_core import _area_rect
        from one_dragon.base.geometry.rectangle import Rect
        rect = _area_rect(self.ctx, area, screen_name=scr)
        if rect is None:
            return False
        texts = [m.data for m in self.ctx.ocr_service.get_ocr_result_list(
            image=self._frame, rect=rect)]
        # 锚语义=**找到该锚自己的文字**(非「该区有任何文字」
        # ——fixture 抓到的误判:备战帧上按开商店屏 rect 读到
        # 别的文字,count>0 ≠「收起」可见)。area 名取尾词匹配。
        kw = area.split('-')[-1]
        return any(kw in t for t in texts)


class _Res:
    def __init__(self, ok: bool):
        self.is_success = ok


def _gate(op, profile, **kw):
    """跑 gate(短超时,离线单帧喂两次靠 stable 窗推进)。"""
    class _Clk:
        def __init__(self):
            self.t = 0.0

        def __call__(self):
            self.t += 0.5   # 每 poll 推进 0.5s(>min_stable_s 0.8 两轮过)
            return self.t
    return wait_stable_frame(op, profile=profile, clock=_Clk(), **kw)


def test_gate_closed_passes_on_reward_panel_frame(test_context) -> None:
    """局35 形态:1-1 奖励面板帧(备战+奖励展开)关态 gate 放行。

    fixture「货币战争-备战/补给节点.webp」=备战屏带节点面板
    展开形态(节点行被遮)——圆数门误杀的现场形态。
    """
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        pytest.skip('fixture 缺:货币战争-备战/补给节点.webp')
    frame = test_context.load_screen('货币战争-备战', '补给节点')
    op = _FixtureOp(test_context, frame)
    out = _gate(op, PROFILE_CLOSED, timeout_s=8)
    assert out is not None, '奖励面板帧应放行(局35 误杀形态回归锁)'


def test_gate_fingerprint_same_source_stable(test_context) -> None:
    """同源图连续指纹必稳(阈值比较,截屏噪声容差)。"""
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        pytest.skip('fixture 缺')
    from one_dragon.base.geometry.rectangle import Rect
    frame = test_context.load_screen('货币战争-备战', '补给节点')
    r = (Rect(1408, 23, 1498, 103), Rect(60, 895, 320, 975))
    a = _fingerprint(frame, r)
    b = _fingerprint(frame, r)   # 同一图再读=完全一致
    assert _fp_same(a, b), '同源图指纹必须一致(阈值语义)'


def test_gate_closed_rejects_shop_open_frame(test_context) -> None:
    """开商店帧:关态 profile 拒绝(absence 锚「按钮-收起」可见)。"""
    if not test_context.has_screen('货币战争-备战-开商店', 'shop_open'):
        pytest.skip('fixture 缺:货币战争-备战-开商店/shop_open.webp')
    frame = test_context.load_screen('货币战争-备战-开商店', 'shop_open')
    op = _FixtureOp(test_context, frame)
    out = _gate(op, PROFILE_CLOSED, timeout_s=4)
    assert out is None, '开商店帧关态 gate 必须拒绝(absence 锚)'


def test_gate_open_profile_passes_shop_open(test_context) -> None:
    """开态 profile 在商店开帧放行(锚=按钮-收起 presence)。"""
    if not test_context.has_screen('货币战争-备战-开商店', 'shop_open'):
        pytest.skip('fixture 缺')
    frame = test_context.load_screen('货币战争-备战-开商店', 'shop_open')
    op = _FixtureOp(test_context, frame)
    out = _gate(op, PROFILE_OPEN, timeout_s=8)
    assert out is not None, '商店开帧开态 gate 应放行'
