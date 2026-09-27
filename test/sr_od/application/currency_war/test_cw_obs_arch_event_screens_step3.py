"""统一观察架构·补给节点行为锁(两 node 形态,)。

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
- **supply 刷新闸锁**(剩余语义观察真值,迭代
   3.2):剩余 1 → 建议刷新 →
  点钮恰一次 + 终结交回;剩余 0/None → 零点击不按刷新终结,重调一次
  决策按原评分选卡。原「已用计数发射即记」写端锁随计数闸退役(考古走 git)。

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


def _make_supply(test_context, monkeypatch, *, pick, opts,
                 anchor=None):
    """补给真类装配(两 node 形态):门桩 + 选项读链桩 + 锚读桩 +
    机械派发半桩;观察 node 装载 obs(report 落容器)+ 动作体载体。
    ``pick`` = decide_supply 返回值或可调用(闸拒绝重调用例传序列);
    ``anchor`` = ``_read_refresh_anchor`` 桩返回值(默认 None=读缺)。
    返回 (op, match, session, stub, envs)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_action_registry,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    session = StrategySession()
    _decide = pick if callable(pick) else (lambda: pick)
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(decide_supply=_decide))
    match.gs = game_state_of(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    monkeypatch.setattr(sn, 'read_supply_options', lambda ctx, screen: list(opts))
    monkeypatch.setattr(op, '_read_refresh_anchor', lambda screen: anchor)
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
    envs: list = []
    monkeypatch.setattr(cw_action_registry, 'action_op_for',
                        lambda act, ctx, env: (envs.append(env), stub)[1])
    return op, match, session, stub, envs


def test_supply_chosen_written_on_confirm_pick(test_context, monkeypatch) -> None:
    """补给 chosen_supply 确认即写行为锁(选定中转暂存宿主已随执行层状态
    类目退役,写端 = 选定确认时点;口径分叉申报见文件头):
    - 真选(有选项 + 决策选列):确认分支单次逻辑写入 (角色,装备,有钻石)
      三元组,source=logic,机械派发半照发(记录面不拦截动作);
      选定快照携 ``refresh_left`` 键 = 容器剩余次数现值(可 None);
    - 刷新轮不写 = 真选守卫(闸拒绝零点击路径语义)。
    OCR 读链/配置/机械派发半桩化,只锁记录面。"""
    from one_dragon.base.geometry.point import Point

    # ① 真选:确认即写(锚读 1 → 容器 left=1 → 快照 refresh_left=1)
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=True)
    op, _match, session, stub, envs = _make_supply(
        test_context, monkeypatch,
        pick=CwActionPickSupplyParam(idx=0, reason='test'),
        opts=[(opt, SimpleNamespace(x=900, y=550))],
        anchor=(1, Point(1315, 983)))
    _run_node(test_context, op, op.observe)   # 观察 node 装载 obs(report 落容器)
    op._do_action()
    gs = game_state_of(session)
    assert gs.chosen_supply.value == ('希儿', '星币收集器', True), (
        f'确认即写:容器持选定三元组,实得 {gs.chosen_supply.value!r}')
    assert gs.chosen_supply.source == 'logic', '单次逻辑写入(source=logic)'
    assert stub.executed == 1, '机械派发半照发(记录面不拦截动作链)'
    assert gs.supply.value is not None, '前置:观察轮 report 落容器 supply'
    assert gs.supply_refresh_left.value == 1, '观察轮锚读摄入容器 left'
    assert envs and envs[0].picked is not None \
        and envs[0].picked['refresh_left'] == 1, (
            f"选定快照携 refresh_left=容器现值:"
            f"{envs[0].picked!r}")
    # ② 刷新轮不写(真选守卫;闸拒绝零点击语义)
    op2, _m2, s2, _stub2, _ = _make_supply(
        test_context, monkeypatch,
        pick=CwActionRefreshSupplyParam(reason='test'),
        opts=[(opt, SimpleNamespace(x=900, y=550))])
    _run_node(test_context, op2, op2.observe)
    op2._do_action()
    assert game_state_of(s2).chosen_supply.value is None, \
        '刷新轮不写 = 真选守卫'


def test_supply_refresh_gate_left_semantics(test_context, monkeypatch) -> None:
    """supply 刷新闸行为锁(剩余语义观察真值,迭代
     design §2.0A/§2.1):
    - 剩余 1 → 建议刷新 → 点钮恰一次 + 终结交回(_do_action 返回 True);
    - 剩余 0 / None → 零点击不按刷新终结,重调一次决策后落选卡
      (机械派发半照发,刷新钮零点击)。
    注(补给画面策略迁移批语义过期注记):判据侧次数闸已内嵌策略层
    decide(``strategies/impl/mandate_v1/supply.py``,仅剩余 ≥1 才可能返
    刷新建议),生产中「建议刷 ∧ 对照闸拒绝」仅剩刷新锚点缺失一种触发面
    ——重调同输入同输出仍建议刷 → 零点击终结交回;「按原评分选卡」为旧
    kernel 评分叙述,决策本体现 = 策略层三级字典序。本锁以 stub 驱动,
    保留 op 面对照闸的行为断言(闸拒绝零点击、重调链有界)。
    OCR 读链/机械派发/固定等待桩化,只锁闸面与点击面。"""
    from one_dragon.base.geometry.point import Point
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=True)
    opts = [(opt, SimpleNamespace(x=900, y=550))]
    clicks: list = []
    monkeypatch.setattr(test_context.controller, 'mouse_move',
                        lambda p, **k: None, raising=False)
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda p, **k: clicks.append((p.x, p.y)))
    monkeypatch.setattr(sn.time, 'sleep', lambda s: None)   # 固定等待 2s 桩

    # ① 剩余 1:点钮恰一次 + 终结交回
    op, _m, _s, stub, _ = _make_supply(
        test_context, monkeypatch,
        pick=CwActionRefreshSupplyParam(reason='test'), opts=opts,
        anchor=(1, Point(1315, 983)))
    _run_node(test_context, op, op.observe)
    assert op._do_action() is True, '放行:动作已发,终结交回'
    assert clicks == [(1315 - 100, 983)], \
        f'刷新圆钮文本锚定偏移点击恰一次:{clicks!r}'
    assert stub.executed == 0, '放行轮零选卡派发'
    # ② 剩余 0:零点击不终结,重调按原评分选卡
    picks = iter([CwActionRefreshSupplyParam(reason='test'),
                  CwActionPickSupplyParam(idx=0, reason='rescore')])
    op2, _m2, _s2, stub2, _ = _make_supply(
        test_context, monkeypatch, pick=lambda: next(picks), opts=opts,
        anchor=(0, Point(1315, 983)))
    _run_node(test_context, op2, op2.observe)
    assert op2._do_action() is True, '拒绝轮经重选落选卡派发(终结交回)'
    n_clicks = len(clicks)
    assert n_clicks == 1, f'剩余 0 = 刷新钮零点击:{clicks!r}'
    assert stub2.executed == 1, '重调一次决策按原评分选卡(派发照发)'
    # ③ None(未观察/读缺):零点击不终结,重调按原评分选卡
    picks3 = iter([CwActionRefreshSupplyParam(reason='test'),
                   CwActionPickSupplyParam(idx=0, reason='rescore')])
    op3, _m3, _s3, stub3, _ = _make_supply(
        test_context, monkeypatch, pick=lambda: next(picks3), opts=opts,
        anchor=None)
    _run_node(test_context, op3, op3.observe)
    assert op3._do_action() is True
    assert len(clicks) == 1, f'None = 刷新钮零点击(容器未写):{clicks!r}'
    assert stub3.executed == 1, 'None 拒绝轮重调按原评分选卡'


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
