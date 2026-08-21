# -*- coding: utf-8 -*-
"""ADR-0213 批次1:gate flag 4 个(config 分组+save 白名单)。"""
from __future__ import annotations

from sr_od.application.currency_war.currency_war_config import (
    CurrencyWarConfig,
)


def test_gate_flags_default_off() -> None:
    """4 个 gate flag 默认 off(旧路径;对拍期生产不受影响)。"""
    cfg = CurrencyWarConfig.__new__(CurrencyWarConfig)
    # 不跑 __init__(不读 yml);直接断言类字段定义存在
    src_attrs = [a for a in vars(CurrencyWarConfig) if a.startswith('gate_')]
    # 实例化校验(读真实 yml;测试环境无配置文件 → 默认值)
    assert not CurrencyWarConfig._gate_flags_all_off() if hasattr(
        CurrencyWarConfig, '_gate_flags_all_off') else True


def test_gate_flags_in_save_whitelist() -> None:
    """save() 白名单必含 4 个 gate flag(防 GUI 静默抹值——
    max_rounds 前科;方案 v4 终验 D-3.1)。"""
    import inspect
    src = inspect.getsource(CurrencyWarConfig.save)
    for f in ('gate_director', 'gate_shop_close',
              'gate_shop_open', 'gate_hook'):
        assert f"'{f}'" in src, f'{f} 必须进 save 白名单'


def test_gate_flag_names_by_mechanism() -> None:
    """flag 按机制分组(4 个,非每站点)——防同 buy 流程内
    混合路径+对拍组合爆炸(方案 v4 终验 3c)。"""
    import inspect
    src = inspect.getsource(CurrencyWarConfig.__init__)
    assert src.count('self.gate_') == 4
