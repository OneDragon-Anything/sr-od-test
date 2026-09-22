"""动作上报函数族命名规约完备锁(摊平批阶段②;拆分包版)。

规约:词表类 ``CwActionXxxParam`` 恰有同名上报函数
``report_action_<snake>_param``(kernel/cw_action_report 包,每动作
一文件;工具族落 ``tool_use``,其余零写族落 ``zero_writes``;包级
``__getattr__`` 命名规约解析)。
新增动作漏建上报函数/漏建文件 = 本锁红。声明面即命名规约本身,
无分发表——分派只允许出现在实机 op 直调与 sim/回放引擎入口。
"""
import re

import pytest

from sr_od.application.currency_war.kernel import cw_action_report as rpt
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import CW_ACTION_TYPES


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(工具七类上报升格容器写后,冒烟路径对空参/未观察
    容器会产生 tool_* 留证行;前清防他测残留、后清防本测外泄——全局缓冲
    被后续测试整池排水对账,残留行即假红)。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


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
def test_report_function_accepts_param_and_sig(t, _isolate_defect_buffer):
    """逐类冒烟:上报函数以零写/拒绝路径可调用(不要求容器效果,
    只锁「函数在场且签名可走」——语义正确性归各域直锁)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        GameState,
    )

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
    if t.__name__ == 'CwActionPickInvestEnvParam':
        # 按 idx 取名契约(op-layer.md §1.1 观察标准化门):env 上报从容器
        # invest_env_opts 取标准名直传链,容器缺读 = 响亮失败——冒烟播种
        # 容器承载该路径(裸容器直调会被正当拒绝)。播种名 = 环境注册表
        # 真名(含半角冒号,兼覆盖链内归一幂等路径;ENV_GIFTS 仅条件腿,
        # 效果面安静零写)。
        gs.write_logic(gs.invest_env_opts, ['特邀专家:银狼'],
                       produced_by='test', sig=sig)
    outcome = fn(gs, param, sig)
    assert outcome is not None
    assert isinstance(outcome.applied, bool)


def test_report_pick_invest_env_container_miss_loud_failure():
    """env 上报「按 idx 取名」契约拒绝腿(op-layer.md §1.1;即时上报契约:
    选卡链发生时观察必然已完成,容器缺读/idx 越界 = 代码 bug = 响亮失败,
    异常上抛禁吞)。红 = 静默零写 noop 回潮 / 非法索引穿透。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        GameState,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestEnvParam,
    )

    sig = ChannelSig(family='logic_action', actor='cw-report-lock',
                     mode='compute')
    fn = rpt.report_action_pick_invest_env_param
    # ① 容器缺读(None)
    with pytest.raises(ValueError):
        fn(GameState(schema_version=1), CwActionPickInvestEnvParam(idx=0), sig)
    # ② 容器空(读得空 = 同判缺读)
    gs_empty = GameState(schema_version=1)
    gs_empty.write_logic(gs_empty.invest_env_opts, [],
                         produced_by='test', sig=sig)
    with pytest.raises(ValueError):
        fn(gs_empty, CwActionPickInvestEnvParam(idx=0), sig)
    # ③ idx 越界(容器非空但 idx 出界)
    gs_seeded = GameState(schema_version=1)
    gs_seeded.write_logic(gs_seeded.invest_env_opts, ['特邀专家:银狼'],
                          produced_by='test', sig=sig)
    with pytest.raises(ValueError):
        fn(gs_seeded, CwActionPickInvestEnvParam(idx=3), sig)
