# -*- coding: utf-8 -*-
"""test_cw_r337_r332_behavior 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations


# (2026-09-03 瘦身批:_make_op 复刻夹具与两条 streak 自抄测删除——
#  _make_op._director_fail 复刻 r332 逻辑断言自己,删生产代码仍绿(纪律 10);
#  streak 接线的唯一保底 = 下方 test_source_has_real_wiring,记债待升级行为锁。)



def test_source_has_real_wiring() -> None:
    """真实接线存在(弱锁保底:streak 挂长命 loop 实例)。"""
    import inspect

    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop.CwLoop)
    assert 'CwScreenPrep(self.ctx).execute()' in src
    assert '_director_fail_streak' in src
