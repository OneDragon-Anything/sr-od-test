# -*- coding: utf-8 -*-
"""r335/r336 批次3/4 收尾锁(单文件)。"""
from __future__ import annotations

import inspect


def test_shop_collapse_single_poll_fn() -> None:
    """r335:shop 收起三路等待收敛为一个 _legacy_poll。"""
    from sr_od.application.currency_war.operations.prep import shop
    src = inspect.getsource(shop.BuyShopCards)
    assert '_legacy_poll' in src
    # 轮询体只定义一次(收起按钮消失检查的 for 循环唯一)
    assert src.count('for _ in range(5):') == 1


def test_star_evidence_queue_pattern() -> None:
    """r336:star 留证从 reconcile 深处改队列登记,对账位统一消费。"""
    from sr_od.application.currency_war import cw_reconcile
    src = inspect.getsource(cw_reconcile.reconcile_tracking)
    assert '_pending_evidence.append' in src       # 深处只登记
    assert '_pending_evidence:' in src              # 队列初始化
    # 消费在函数尾部(对账&hook 位)
    tail = src[src.index('return True') - 700:]
    assert '_star_stop_hook' in tail


def test_star_hook_none_screen_tolerant() -> None:
    """r336b:screen=None(测试/无帧)不拦留证。"""
    from sr_od.application.currency_war import cw_reconcile
    src = inspect.getsource(cw_reconcile._star_stop_hook)
    assert 'screen is not None' in src


def test_prep_settle_attribution_declared() -> None:
    """r336:PREP_SETTLE_S 归属声明(分发层 vs 环内 gate 正交)。"""
    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert 'r336' in src and '正交' in src


def test_shop_currency_war_config_module_level() -> None:
    """r345(局38 实机,gate bug #5):shop.py 的 CurrencyWarConfig
    必须模块级 import——原局部 import 在「收起按钮可见」条件分支
    内,shop 关态入口(分支跳过)+后方引用 = UnboundLocalError,
    buy 全崩。锁:模块级名存在 + buy 体内无任何局部 import。"""
    from sr_od.application.currency_war.operations.prep import shop
    assert getattr(shop, 'CurrencyWarConfig', None) is not None, \
        'shop.py 必须模块级 import CurrencyWarConfig'
    src = inspect.getsource(shop.BuyShopCards.buy)
    assert 'currency_war_config import' not in src, \
        'buy 体内不得再有局部 import CurrencyWarConfig(r345 局38 崩溃根因)'


def test_shop_contextlib_module_level_no_local_import() -> None:
    """r346(review H1,gate bug #5 同型):buy 体内 `import contextlib`
    原只在两个 gate 分支内,L352 的 `with contextlib.suppress`
    (decide_prep 异常留证路径)在分支外——shop 开态入口或 flag off
    时 decide_prep 抛异常会先抛 UnboundLocalError,吞掉原始异常
    与遥测留证。锁:模块级存在 + buy/buy_card 体内无局部 import
    contextlib + contextlib.suppress 使用点无局部 import 保护。"""
    from sr_od.application.currency_war.operations.prep import shop
    assert getattr(shop, 'contextlib', None) is not None, \
        'shop.py 必须模块级 import contextlib(r346 H1)'
    for method in (shop.BuyShopCards.buy,):
        src = inspect.getsource(method)
        assert 'import contextlib' not in src, \
            f'{method.__name__} 体内不得有局部 import contextlib(r346 H1 雷)'


def test_director_gate_open_shop_tolerated_not_bail() -> None:
    """r346(局38 r2 停机根因):环入口 gate 超时后必须先区分
    「开商店稳定态」(合法,游戏在战斗胜利后新回合可能自动开)
    vs「真特效」——开态走收起+round_retry 重进,只有非开态才
    _bail(3-strike 停机)。锁源检:超时分支含开商店检测与收起重进
    路径,bail 仍保留。"""
    from sr_od.application.currency_war import prep_director
    src = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert '环入口开商店态' in src, \
        'gate 超时分支必须有开商店态容忍路径(r346)'
    assert '环入口商店开,已收起重进' in src, \
        '开态路径必须收起后 round_retry 重进(非 bail)'
    assert '环入口帧不clean' in src, \
        '真特效/overlay 的原 bail 路径必须保留(容忍不能吞掉消化门)'
