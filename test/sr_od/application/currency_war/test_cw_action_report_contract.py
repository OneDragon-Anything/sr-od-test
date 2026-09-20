"""动作上报函数族命名规约完备锁(摊平批阶段②;拆分包版)。

规约:词表类 ``CwActionXxxParam`` 恰有同名上报函数
``report_action_<snake>_param``(kernel/cw_action_report 包,每动作
一文件;零写族落 zero_writes;包级 ``__getattr__`` 命名规约解析)。
新增动作漏建上报函数/漏建文件 = 本锁红。声明面即命名规约本身,
无分发表——分派只允许出现在实机 op 直调与 sim/回放引擎入口。
"""
import re

import pytest

from sr_od.application.currency_war.kernel import cw_action_report as rpt
from sr_od.application.currency_war.kernel.cw_vocab import CW_ACTION_TYPES


def _snake(cls_name: str) -> str:
    core = cls_name[len('CwAction'):] if cls_name.startswith('CwAction') else cls_name
    if core.endswith('Param'):
        core = core[:-len('Param')]
    return re.sub(r'(?<!^)(?=[A-Z])', '_', core).lower()


def test_every_action_type_has_report_function():
    """每个词表动作类恰有一个 ``report_action_<snake>_param`` 可调用。"""
    missing = []
    for t in CW_ACTION_TYPES:
        fn = f'report_action_{_snake(t.__name__)}_param'
        if not callable(getattr(rpt, fn, None)):
            missing.append(f'{t.__name__} -> {fn}')
    assert not missing, f'漏建上报函数: {missing}'


@pytest.mark.parametrize('t', CW_ACTION_TYPES, ids=lambda t: t.__name__)
def test_report_function_accepts_param_and_sig(t):
    """逐类冒烟:上报函数以零写/拒绝路径可调用(不要求容器效果,
    只锁「函数在场且签名可走」——语义正确性归各域直锁)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        GameState,
        register_sig_actors,
    )

    register_sig_actors('cw-report-lock')
    gs = GameState(schema_version=1)
    sig = ChannelSig(family='logic_action', actor='cw-report-lock',
                     mode='compute')
    fn = getattr(rpt, f'report_action_{_snake(t.__name__)}_param')
    # 构造最小 param:必填字段给哑值(仅为了走函数入口;写路径按域锁覆盖)
    import dataclasses

    from sr_od.application.currency_war.kernel.cw_vocab import ShopCard

    kwargs = {}
    for f in dataclasses.fields(t):
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            kwargs[f.name] = ShopCard(x=0) if f.name == 'card' else (
                0 if f.type == 'int' else '')
    param = t(**kwargs)
    outcome = fn(gs, param, sig)
    assert outcome is not None
    assert isinstance(outcome.applied, bool)
