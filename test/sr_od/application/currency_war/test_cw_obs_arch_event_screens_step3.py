"""统一观察架构·逐屏迁移第二批量锁(试点步骤 3:补给 + 余事件屏按族批量)。

设计正本 = docs/develop/sr_od/application/currency_war/flow/统一观察架构-画面op基类设计.md
(下称「架构设计」);迁移粒度依据 = 开放问题清单 B3 三段走第二段(代表屏
断言集模板已立 → 「补给 + 余事件屏按族批量」)+ §9.2 迁移步骤 4 建议序
(遭遇 → 补给 → 事件屏族);迁移手法单一源 = 试点步骤 2 先例
(装配点分流 + 五段转录 + 实机适配器封口 + on_outcome 注册表;本批八屏按
其「盛会之星型」共享动作体形态落码,lifecycle_observe 消费
``_observation_port()`` 位)。

**本批屏清单(B3 族表 = 架构设计 §6.6 事件选择行十屏 − 步骤 2 已迁两屏)**:
补给 CwScreenSupplyNode / 伙伴 CwScreenPartner / 骇入策划 CwScreenPlanner /
祈愿试炼 CwScreenWishTrial / 命运卜者 CwScreenFortune / 星徽秘典
CwScreenBookcard / 装备三选一 CwScreenEquipPick / 专家邀请函
CwScreenExpertInvite。武装箱弹窗(CwScreenArmoryBox)不在本批:B4 把它点名列
入弹窗/导航类 op(非事件屏族,无选择面)。

**F11/B3 sim 腿例外清单(随迁移批逐屏落测试 docstring)**:

- 伙伴/祈愿试炼/命运卜者/骇入策划/星徽秘典/装备三选一/专家邀请函七屏:
  sim 腿 = 不适用——sim 无对应画面段/决策段(引擎事件即时落定,架构设计
  §3.2 事件浮层族行),等价判据主承重 = 实机在册行为锁 + 写入流对拍
  (实机腿),禁引用 sim 域对拍;
- 补给(CwScreenSupplyNode):sim 腿 = 引擎补给决策段**已在**(engine_p1
  直调 kernel decide_supply,T5 接口收敛挂账)但**本批未接线**(sim 接线批
  后续),本批等价判据仍以实机在册行为锁承重。

锁的语义(测试纪律 7 自检;出处 = 架构设计 §9.1/§6.4-R-E/B5;先例 =
test_cw_obs_arch_event_screens.py 断言集模板;生产端口恒 None 直连旧
路径——迁移结构锁与八屏装配点分流锁已随并存窗收口整删,行为锁单驱动
生产路径):

- **注册表零登记锁**(§6.4 收编面本批零行):八屏源无 register_outcome_
  hook / fire_emit_hooks 接线——§6.4 表登记件全不涉事件选卡屏;supply_
  refresh_used GameState 字段位 = 先申报禁静默(cw_game_state.py 字段行
  自注),执行侧防重入旗标 _supply_refresh_used 留守 _do_action,不入注册
  表。红 = 未经申报面擅立登记件(EMIT_TRIGGERED_DECLARED 同款纪律)。
- **共享动作体锁**:七选卡屏 post-gate 体纯移入 ``_handle_overlay``(两路径
  共用零转录,先例 = 盛会之星 ``_do_action``);supply 暂存生命周期
  (chosen 完成落账/取走清/重入弃陈旧)住 handle 出口/入口共享段。
- **chosen_* 豁免留守锁**(§2.2/§6.5-6):chosen_* 写端仍内联于共享体
  (出口验真通过分支),不入 on_outcome 注册表收编面。
- **验证段废除源面锁**(用户裁定 2026-09-10,同
  test_cw_obs_arch_event_screens.py 同名锁):八屏源无「六段」表述、无
  'verify' 段迹字面。

驱动方式 = 真类实例(构造走 __init__,适配器位在位)+ 画面门/动作体桩化
(``_do_action`` 方法级桩;生产端口缺省 None = 直连旧路径,行为锁单驱动
生产形态)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_game_state import board_state_of
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;共享体桩只验传递不断言内容)


def _make_supply(test_context, monkeypatch, *, in_node: bool):
    """补给屏真类装配(生产构造走 __init__;共享动作体 ``_do_action`` 桩)。

    桩面 = 节点完成门(round_by_find_area → _in_node)+ ``_do_action`` 计数;
    会话 = 真 StrategySession(chosen/暂存面走真实 GameState 语义)。
    返回 (op, match, session, calls)。
    """
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    session = StrategySession()
    match = SimpleNamespace(session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_node))
    calls: list[int] = []
    monkeypatch.setattr(op, '_do_action', lambda scr: calls.append(1))
    return op, match, session, calls


# ==================== 迁移结构锁(§9.1 并存期)====================


# (收口整删)原 test_migration_batch3_ops_inherit_base「八 op 均为
# CwScreenOpBase 子类」(连 _BATCH3_SCREENS 常量)删:继承结构 = 静态形状,
# 红时答不出哪个运行行为坏了;结构面归 review 与代码规范。


def test_supply_chosen_staging_lifecycle(test_context, monkeypatch) -> None:
    """补给 chosen 暂存生命周期(supply 两条幸存锁并一:完成落账+取走清
    +重入弃陈旧;单驱动生产旧路径,暂存生命周期住 handle 出口/入口共享
    段,装端口段迹面随并存窗收口退役):
    - 完成落账:已离开节点画面 = 节点完成早退 → chosen_supply 自选定
      暂存写入 + 暂存取走即清(不跨节点残留),节点完成零动作;
    - 重入弃陈旧:在屏轮开始先 pop 取走暂存再做动作(防跨轮/跨节点
      误写),本轮动作照发。
    (并锁 = 原 test_supply_exit_writes_chosen_on_lifecycle_path /
    test_supply_reentry_discards_stale_pending_both_paths。红 = 幻影
    chosen / 陈旧暂存跨节点误写。)"""
    # ① 完成落账 + 取走清
    op, _match, session, calls = _make_supply(
        test_context, monkeypatch, in_node=False)
    exec_state_of(session)._pending_chosen_supply = ('希儿', '星币收集器',
                                                     True)
    rs = _run_node(test_context, op, op.handle)
    assert rs.is_success and '节点完成' in (rs.status or ''), (
        f'完成语义不变:{rs!r}')
    assert calls == [], '节点完成 = 不再发动作'
    assert op._lifecycle_trace == [], (
        f'生产路径零段迹:{op._lifecycle_trace}')
    bs = board_state_of(session)
    assert bs.chosen_supply.value == ('希儿', '星币收集器', True), (
        f'chosen_supply 自暂存写入:{bs.chosen_supply.value!r}')
    assert exec_state_of(session)._pending_chosen_supply is None, (
        '写后取走暂存(不跨节点残留)')
    # ② 重入弃陈旧
    op2, _m2, session2, calls2 = _make_supply(
        test_context, monkeypatch, in_node=True)
    exec_state_of(session2)._pending_chosen_supply = ('符玄', '旧选定', False)
    rs2 = _run_node(test_context, op2, op2.handle)
    assert exec_state_of(session2)._pending_chosen_supply is None, (
        '重入轮入口弃陈旧暂存')
    assert calls2 == [1] and not rs2.is_success, (
        '弃陈旧后本轮动作照发(在屏 = 一动作 + retry,保形)')


# (原 test_supply_no_outcome_registry_item 删:负向注册表取证断言——
#  「不得私设登记件」红时答不出哪个运行行为坏了,架构申报纪律归 review
#  与代码规范;supply 行为面由同文件 chosen 暂存/重入弃陈旧两锁承重。)


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
