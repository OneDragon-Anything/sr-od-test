# -*- coding: utf-8 -*-
"""r347(旧路径删除):gate flag 4 个已删——观测 gate 无条件化
(ADR-0213 对拍期结束,局38 r1-r3 实机验证过新路径+path=old 恒 0)。

原 3 测(默认 off/save 白名单/按机制分组)随 flag 删除而废;
本文件留「flag 不得回流」负向锁。
"""
from __future__ import annotations

from sr_od.application.currency_war.currency_war_config import (
    CurrencyWarConfig,
)


def test_gate_flags_removed() -> None:
    """r347:gate_* flag 不得回流——对拍已完成,gate 是唯一路径;
    flag 回流 = 死代码复活(双路径维护+组合爆炸)。"""
    src_attrs = [a for a in vars(CurrencyWarConfig) if a.startswith('gate_')]
    assert not src_attrs, f'gate flag 已删不得回流: {src_attrs}'
    import inspect
    init_src = inspect.getsource(CurrencyWarConfig.__init__)
    assert 'self.gate_' not in init_src, '__init__ 不得再读 gate flag'
    save_src = inspect.getsource(CurrencyWarConfig.save)
    assert "'gate_" not in save_src, 'save 白名单不得再写 gate flag 键'
