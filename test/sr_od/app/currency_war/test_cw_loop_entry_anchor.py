# -*- coding: utf-8 -*-
"""test_cw_loop_entry_anchor 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations


import inspect

from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep


def test_loop_entry_anchor_is_stage_only() -> None:
    """P0①→r347→W971 P3b 拆内环(返工定稿):旧「按钮-出战」双态区分锚
    退役;环入口消化语义 = 外循环每轮重识别 + 单轮 op 清场/开店收起探针
    (gate 时间稳定窗随内环拆除)。锁:旧锚不得回流 + 收起探针在。"""
    src = inspect.getsource(cw_screen_prep.CwScreenPrep.run)
    assert "'按钮-出战'" not in src, \
        '旧 3 探针锚已删(r347),不得回流单轮入口'
    assert '_try_collapse_open_shop()' in src, \
        '单轮入口必须探开商店合法态并收起(读互斥:hp 关态可读)'
    assert 'wait_stable_frame' not in src, \
        'gate 时间稳定窗已随内环拆除(W971 P3b 返工定稿),不得回流'
    assert '_bail(' not in src and 'bail_reason_counts' not in src, (
        '内环 bail/同因计数机制不得回流(拆内环定稿;'
        '原 test_no_fallthrough_blind_observe 墓碑句,2026-09-03 瘦身批并入)')
