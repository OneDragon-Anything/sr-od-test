# -*- coding: utf-8 -*-
"""test_cw_r336_batch4_locks 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations



import inspect as _r336_batch4_locks_inspect


def test_shop_open_collapse_wait_dd011() -> None:
    """否定性回流锁(DD-011 裁决背书):商店路径「测量驱动稳定门」与
    「旧轮询 _legacy_poll」均已退役,不得无意回流——两者皆有事故/裁决史
    (gate = 测量驱动等待被 DD-011 整体退役;_legacy_poll = 40min 空转死循环)。
    W970 批 A 原子化后商店路径 = 编排壳 buy + 波循环 run_buy_waves +
    开/关店原子核心,四落点同锁。
    注:不设肯定性断言(常量名在场类)——那类锁只是实现的影子,无独立语义。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards as buy_cards,
        cw_op_close_shop as close_shop,
        cw_op_open_shop as open_shop,
    )
    for fn in (cw_screen_prep.CwScreenPrep._open_shop_phase, buy_cards.run_buy_waves,
               open_shop.open_shop, close_shop.close_shop):
        src = _r336_batch4_locks_inspect.getsource(fn)
        assert 'def _legacy_poll' not in src, \
            '旧轮询 _legacy_poll 已删(r347 40min 空转事故),不得回流'
        assert 'wait_stable_frame' not in src, \
            '商店路径 gate 已按 DD-011 全退役(测量驱动等待),不得回流'


def test_shop_currency_war_config_module_level() -> None:
    """r345(局38 实机,gate bug #5):商店路径的 CurrencyWarConfig
    必须模块级 import——原局部 import 在「收起按钮可见」条件分支
    内,shop 关态入口(分支跳过)+后方引用 = UnboundLocalError,
    buy 全崩。W970 批 A 原子化后 config 构造点 = run_buy_waves 顶部
    (无条件,UnboundLocalError 形态结构性消除);锁:buy_cards 模块级
    名存在 + 编排壳/波循环体内无任何局部 import。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
    from sr_od.application.currency_war.operations.cw_op import cw_op_buy_cards as buy_cards
    assert getattr(buy_cards, 'CurrencyWarConfig', None) is not None, \
        'buy_cards.py 必须模块级 import CurrencyWarConfig'
    # visit_open_shop = 0n 转交与显式开店的共用尾段(ADR-0562),同辖
    for method in (cw_screen_prep.CwScreenPrep._open_shop_phase,
                   cw_screen_prep.CwScreenPrep.visit_open_shop,
                   buy_cards.run_buy_waves):
        src = _r336_batch4_locks_inspect.getsource(method)
        assert 'currency_war_config import' not in src, \
            f'{method.__name__} 体内不得有局部 import CurrencyWarConfig(r345 局38 崩溃根因)'


def test_shop_contextlib_module_level_no_local_import() -> None:
    """r346(review H1,gate bug #5 同型):商店路径体内 `import contextlib`
    原只在两个 gate 分支内,分支外的 `with contextlib.suppress`
    (decide_prep 异常留证路径)在分支外——shop 开态入口或 flag off
    时 decide_prep 抛异常会先抛 UnboundLocalError,吞掉原始异常
    与遥测留证。W970 批 A 原子化后路径 = 编排壳 buy + 波循环
    run_buy_waves。锁:两模块模块级存在 + 两体内无局部 import
    contextlib + contextlib.suppress 使用点无局部 import 保护。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
    from sr_od.application.currency_war.operations.cw_op import cw_op_buy_cards as buy_cards
    assert getattr(cw_screen_prep, 'contextlib', None) is not None, \
        'cw_screen_prep.py 必须模块级 import contextlib(r346 H1;编排宿主随壳退役迁移)'
    assert getattr(buy_cards, 'contextlib', None) is not None, \
        'buy_cards.py 必须模块级 import contextlib(r346 H1)'
    # visit_open_shop = 0n 转交与显式开店的共用尾段(ADR-0562),同辖
    for method in (cw_screen_prep.CwScreenPrep._open_shop_phase,
                   cw_screen_prep.CwScreenPrep.visit_open_shop,
                   buy_cards.run_buy_waves):
        src = _r336_batch4_locks_inspect.getsource(method)
        assert 'import contextlib' not in src, \
            f'{method.__name__} 体内不得有局部 import contextlib(r346 H1 雷)'
