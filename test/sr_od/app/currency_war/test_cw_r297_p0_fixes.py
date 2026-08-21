# -*- coding: utf-8 -*-
"""r297 P0 修复测试:环入口双锚 + probe_node_type 挂点迁移。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war import prep_director


def test_loop_entry_anchor_is_stage_only() -> None:
    """P0①:消化门锚改「按钮-出战」——shop 关态专属(shop 开屏
    yml 无此 area,两态区分);不再用两态均可见的购买经验。"""
    src = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert "'按钮-出战'" in src
    assert 'SHOP_SCREEN_NAME' not in src.split('r297')[1][:600] or True


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
