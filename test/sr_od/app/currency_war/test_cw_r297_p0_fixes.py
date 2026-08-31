# -*- coding: utf-8 -*-
"""r297 P0 修复测试:环入口双锚 + probe_node_type 挂点迁移。

出处:docs/develop/currency_war/decisions/0216-gate-old-path-removal.md(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war import prep_director


def test_loop_entry_anchor_is_stage_only() -> None:
    """P0①→r347(旧路径删除):原「按钮-出战」双态区分锚随 3 探针
    旧路径删除而退役——环入口消化语义由 gate 时间稳定窗
    (PROFILE_CLOSED 屏判定=备战关态专属)+r346 开商店容忍
    (收起重进)承担。锁:旧锚不得回流 + gate 调用在。"""
    src = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert "'按钮-出战'" not in src, \
        '旧 3 探针锚已删(r347),环入口消化由 gate 承担'
    assert 'wait_stable_frame' in src, \
        '环入口必须走 gate(时间稳定窗消化门)'


def test_no_fallthrough_blind_observe() -> None:
    """P0①:3 次不 clean → bail(交外环重进),不再 fall-through
    盲 observe(实锤路径:16:42:35 deployed 6人读成1人)。"""
    src = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert '环入口帧不clean' in src


def test_probe_node_type_after_shop_closed() -> None:
    """P0③:_probe_node_type 迁至 EnsureShopClosed 后(与 reward
    钩子同挂点);run() 入口不再直调(skip 69% 根因)。"""
    src_loop = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert 'self._probe_node_type()' in src_loop
    src_run = inspect.getsource(prep_director.PrepDirector.run)
    assert 'self._probe_node_type()' not in src_run
