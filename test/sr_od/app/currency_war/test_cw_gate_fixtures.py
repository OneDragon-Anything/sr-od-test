# -*- coding: utf-8 -*-
"""gate 原语 fixture 回放测试(r323;用户指路:用建档图做 fixture)。

今天(2026-08-23)gate 在实机暴露的两个 bug,本文件用既有
fixture 截图离线回放锁死——以后 gate 语义改动跑这里即知:
1. 局35:奖励面板帧(1-1 reward 节点)——关态 gate 应放行
   (圆数门误杀的形态;现 absence 锚修法下仍应放行);
2. 指纹阈值:同一 fixture 连续喂两帧=必稳定(字节恒等被
   截屏噪声否决后,阈值比较在同源图上必过);
3. 开态帧(shop_open)——关态 profile 应拒绝(absence 锚)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.obs.cw_observation_gate import (
    PROFILE_CLOSED,
    PROFILE_OPEN,
    wait_stable_frame,
)


class _FixtureOp:
    """把 fixture 截图喂给 gate 的桩 op(r324 后 gate 走
    screen_utils.get_match_screen_name——真 ctx 建档判定,
    fixture 场景恰好完美匹配,无需 mock 锚)。"""

    def __init__(self, ctx, frame):
        self.ctx = ctx
        self._frame = frame
        self.park_calls = 0

    def park_cursor(self, **kw):
        self.park_calls += 1

    def screenshot(self):
        return self._frame


def _gate(op, profile, **kw):
    """跑 gate(短超时,离线单帧喂两次靠 stable 窗推进)。"""
    class _Clk:
        def __init__(self):
            self.t = 0.0

        def __call__(self):
            self.t += 0.5   # 每 poll 推进 0.5s(>profile 稳定窗 0.6s 两轮过)
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
    """同源图连续指纹必稳(阈值比较,截屏噪声容差;r324 基元
    在 cv2_utils)。"""
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        pytest.skip('fixture 缺')
    from one_dragon.base.geometry.rectangle import Rect
    from one_dragon.utils import cv2_utils
    frame = test_context.load_screen('货币战争-备战', '补给节点')
    r = (Rect(1408, 23, 1498, 103), Rect(60, 895, 320, 975))
    a = cv2_utils.fingerprint_in_rects(frame, r)
    b = cv2_utils.fingerprint_in_rects(frame, r)   # 同一图再读=完全一致
    assert cv2_utils.fingerprint_same(a, b), '同源图指纹必须一致(阈值语义)'


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


def test_gate_closed_passes_on_r1_stop_frame(test_context) -> None:
    """r344 实机回归锁(局37 停机现场帧):gate 超时预算按全图
    OCR poll 成本(~5s/轮)调 12s 后,真机 r1 备战帧上关态 gate
    必须放行(屏判定 crop_first=False 全图 OCR,局37 diag
    screen:0 实证 4 个 id_mark 区全中,缺的只是预算)。防
    预算/口径回退让 ping-pong 停机复发。
    fixture=局37 bail_pingpong 停机保全帧(hp=80/r1/gold=3)。"""
    if not test_context.has_screen('货币战争-备战', 'r1_idle_stop'):
        pytest.skip('fixture 缺:货币战争-备战/r1_idle_stop.webp')
    frame = test_context.load_screen('货币战争-备战', 'r1_idle_stop')
    op = _FixtureOp(test_context, frame)
    out = _gate(op, PROFILE_CLOSED, timeout_s=8)
    assert out is not None, '局37 停机现场帧关态 gate 必须放行(r344 锁)'
