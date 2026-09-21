"""统一观察架构·补给节点行为锁(两 node 形态,迭代 2026-09-18-screen-op-flat-report)。

补给 CwScreenSupplyNode 已迁移「观察 node → 决策动作 node」直继承
SrOperation 形态(同批原七选卡屏与结构/分流/源面锁已随并存窗收口整删,
见文件尾分诊注)。锁的语义(测试纪律:只锁核心约定;report 函数级契约
由 test_cw_screen_report_ports 承重,本文件不重复):

- **chosen_supply 确认即写锁**(口径分叉申报:supply 直写,chosen_tome
  维持出口验真后写家族口径——差异理由 = supply 的中转暂存宿主已随执行
  层状态类目退役,直写是载体消亡后的唯一形态):
  真选(有选项 + 决策选列)→ 确认分支单次逻辑写入 (角色,装备,有钻石)
  三元组,机械派发半照发(记录面不拦截动作);刷新轮不写 = 真选守卫
  (兜底点卡/刷新路径与真选分支互斥)。
- **supply 刷新写端锁**(:248 内联写留守决策体,发射即记不等验效,含锚
  读缺零点击路径;本点 = 决策体唯一容器写点,无双计面):
  刷新发射 → 容器计数恰 +1(evidence=refresh_click);计数在位(>0 =
  已用)重入 → 不再发射不计数。

驱动方式 = 真类实例(构造走 __init__)+ 读链/锚读/机械派发半桩化,观察
node 装载 obs(选项与点击点载体)后动作体直驱。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickSupplyParam,
    CwActionRefreshSupplyParam,
)

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;共享体桩只验传递不断言内容)


def _make_supply(test_context, monkeypatch, *, pick, opts):
    """补给真类装配(两 node 形态):门桩 + 选项读链桩 + 机械派发半桩;
    观察 node 装载 obs(report 落容器)+ 动作体载体。返回 (op, match, session)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_action_registry,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    session = StrategySession()
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(decide_supply=lambda: pick))
    match.gs = game_state_of(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    monkeypatch.setattr(sn, 'read_supply_options', lambda ctx, screen: list(opts))
    # 节点条锚定桩(读不得 = 跳过;锚定接线锁归
    # test_cw_supply_advance_wiring,本文件不重复)
    monkeypatch.setattr(op, '_read_node_bar', lambda screen: None)

    class _StubPickOp:
        def __init__(self) -> None:
            self.executed = 0

        def execute(self) -> bool:
            self.executed += 1
            return True

    stub = _StubPickOp()
    monkeypatch.setattr(cw_action_registry, 'action_op_for',
                        lambda act, ctx, env: stub)
    return op, match, session, stub


def test_supply_chosen_written_on_confirm_pick(test_context, monkeypatch) -> None:
    """补给 chosen_supply 确认即写行为锁(选定中转暂存宿主已随执行层状态
    类目退役,写端 = 选定确认时点;口径分叉申报见文件头):
    - 真选(有选项 + 决策选列):确认分支单次逻辑写入 (角色,装备,有钻石)
      三元组,source=logic,机械派发半照发(记录面不拦截动作);
    - 刷新轮不写 = 真选守卫(锚读缺零点击在册语义)。
    OCR 读链/配置/机械派发半桩化,只锁记录面。"""
    # ① 真选:确认即写
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=True)
    op, _match, session, stub = _make_supply(
        test_context, monkeypatch,
        pick=CwActionPickSupplyParam(idx=0, reason='test'),
        opts=[(opt, SimpleNamespace(x=900, y=550))])
    _run_node(test_context, op, op.observe)   # 观察 node 装载 obs(report 落容器)
    op._do_action()
    gs = game_state_of(session)
    assert gs.chosen_supply.value == ('希儿', '星币收集器', True), (
        f'确认即写:容器持选定三元组,实得 {gs.chosen_supply.value!r}')
    assert gs.chosen_supply.source == 'logic', '单次逻辑写入(source=logic)'
    assert stub.executed == 1, '机械派发半照发(记录面不拦截动作链)'
    assert gs.supply.value is not None, '前置:观察轮 report 落容器 supply'
    # ② 刷新轮不写(真选守卫;锚读缺零点击在册语义)
    op2, _m2, s2, _stub2 = _make_supply(
        test_context, monkeypatch,
        pick=CwActionRefreshSupplyParam(reason='test'),
        opts=[(opt, SimpleNamespace(x=900, y=550))])
    monkeypatch.setattr(op2, '_read_refresh_anchor', lambda screen: None)
    _run_node(test_context, op2, op2.observe)
    op2._do_action()
    assert game_state_of(s2).chosen_supply.value is None, \
        '刷新轮不写 = 真选守卫'


def test_supply_refresh_emission_counts_container(
        test_context, monkeypatch) -> None:
    """supply 刷新写端锁(内联写留守决策体,live 写端接容器
    ``supply_refresh_used`` 计数——发射即记不等验效,含锚读缺零点击路径):
    - 刷新发射 → 容器计数恰 +1(evidence=refresh_click;无双计面——
      本点 = 决策体唯一容器写点);
    - 计数在位(>0 = 已用)重入 → 不再发射不计数。
    OCR 读链/锚读/机械派发桩化,只锁记录面与闸面。"""
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=True)
    op, _match, session, _stub = _make_supply(
        test_context, monkeypatch,
        pick=CwActionRefreshSupplyParam(reason='test'),
        opts=[(opt, SimpleNamespace(x=900, y=550))])
    monkeypatch.setattr(op, '_read_refresh_anchor', lambda screen: None)
    _run_node(test_context, op, op.observe)   # 观察 node 装载 obs
    # ① 刷新发射(锚读缺零点击路径)→ 容器 +1
    op._do_action()
    gs = game_state_of(session)
    assert gs.supply_refresh_used.value == 1, (
        f'刷新发射即计数恰 +1(发射即记不等验效):'
        f'{gs.supply_refresh_used.value!r}')
    assert gs.supply_refresh_used.evidence == 'refresh_click', (
        f'发射证据逐位一致:{gs.supply_refresh_used.evidence!r}')
    # ② 计数在位重入 → 不再发射不计数
    op._do_action()
    assert gs.supply_refresh_used.value == 1, (
        f'已用重入不发射(容器计数闸):{gs.supply_refresh_used.value!r}')


# ==================== 七选卡屏(收口整删)====================


# (收口整删)原 test_gated_screens_dispatch_both_ways /
# test_gateless_screens_dispatch_both_ways / test_expert_choose_dispatch_
# both_ways(带门/无门/专家邀请函三组选卡屏的装端口五段分流锁,连唯一
# 消费者 _make_op helper)删:装端口驱动的段迹/分流面随并存窗收口退役
# (生产端口恒 None);旧路径在屏单动作语义已由 supply 同族锁同形承重,
# 七屏体为纯转录、无域写入面,无独立行为锁可立——覆盖缺口归总纲收口
# 申报,不再以分流锁占位。

# (三审整删)原 test_expert_open_card_node_stays_legacy「纯导航留旧
# 路径申报面」(getsource 方法体断言无 run_lifecycle/observation_source)——
# 源码扫描形态(README 禁止清单);开卡节点路由面归 review 与代码规范。
# (三审整删)原 test_batch3_no_outcome_registry_wiring「注册表零登记
# 锁」与 test_batch3_sources_free_of_verify_segment「验证段废除·源面锁」
# (八屏 getsource 字面在场/不在场断言)——源码扫描形态;注册表收编纪律
# 归 review 与代码规范,验证段废除语义 = 分流后无残迹可断。
# (原 test_supply_no_outcome_registry_item 删:负向注册表取证断言——
#  「不得私设登记件」红时答不出哪个运行行为坏了,架构申报纪律归 review
#  与代码规范;supply 行为面由同文件 chosen/刷新写端两锁承重。)
