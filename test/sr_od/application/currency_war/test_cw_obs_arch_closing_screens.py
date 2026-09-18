"""统一观察架构·收尾五屏迁移锁 + cw_screen/cw_op 收口锁(余项收口阶段三)。

断言集模板 = test_cw_obs_arch_event_screens.py(事件屏两 node 形态先例)。
本批五屏:位面过渡 CwScreenPlaneTransition / 武装箱弹窗 CwScreenArmoryBox /
未达上限弹窗 CwScreenDeployNotFull / 等待1-1 CwScreenWaitOneOne / 位面
情报采集 CwScreenPlaneIntel。位面过渡/武装箱/未达上限/等待1-1已迁移
两 node 形态(迭代 2026-09-18-screen-op-flat-report);位面情报采集 =
薄转录直通(装帧观察 node + 双节点图保留)。

**F11 sim 腿不适用例外清单(随迁移批逐屏落测试 docstring,总纲 §2.2-3)**:

- 位面过渡/武装箱弹窗/未达上限弹窗/等待1-1:sim 腿 = 不适用——sim 无对应
  画面段(架构设计 §3.4 过渡相位/中断弹窗行),等价判据主承重 =
  实机在册行为锁 + 本文件两 node 形态锁,禁引用 sim 域对拍;
- 位面情报采集:sim 腿 = 不适用——sim 无位面详情/敌人情报对应画面段
  (§3.4 sim 侧申报),等价判据主承重 = 纯函数三件在册测试锁
  (零触碰)+ 双节点图边锁。

锁的语义(测试纪律 7 自检;出处 = landing 阶段三判据;行为锁单驱动
生产路径):

- **重入裁决×门组合行为锁**:「已发」旗标裁决位 = 位面过渡(两 node
  形态)住决策动作 node 顶部,直驱 act 承重;武装箱(两 node 形态,
  迭代 2026-09-18-screen-op-flat-report)同位;未达上限(两 node 形态)
  同位——门命中 + 旗标在位 → 裁决不触发、确认重发,miss 已发 → 裁决
  success(原「裁决先行式 vs miss 分支内式」位序差异随两 node 拆分自然
  消解,行为观测点 = 门命中+旗标在位时旗标清否,由组合行为锁承重)。
- **观察上报接线锁**(两 node 形态屏):观察 node 门内 obs 装载 → 占位
  report 接线恰一次(占位 = 现役零容器写点的统一形态;位面过渡 = 实体
  接线,链容器终值锁);门早退轮 obs 不装载。
- **round_wait 语义锁**(两 node 形态屏):循环推进 = round_wait(不烧
  节点重试预算);等待1-1 = 轮询 round_wait 自环观察 node。
- **薄转录锁**(位面情报采集):双节点图边(采集→关闭并回写)保留;
  装帧观察 node 不前移场景门。
- **收口锁不恢复**(分诊,原 landing 阶段三判据的目录级守卫):
  「cw_screen/ 与 cw_op/ 顶层 op 类必为 CwScreenOpBase 后代(豁免登记
  门)」以 AST 全目录扫描实现,属源码扫描形态(AGENTS §10.4.4 禁),
  摘除不恢复。文件尾留分诊注。

驱动方式 = 真类实例(构造走 __init__)+ 读链/门/机械点击链桩化,节点
函数直驱(run_node 外壳)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)

_RETRY_RS = OperationRoundResult(OperationRoundResultEnum.RETRY, status='stub-confirm')


def _stub_controller(test_context, monkeypatch: pytest.MonkeyPatch) -> list:
    """controller 桩:mouse_move no-op + click 记录器。返回点击记录列表。"""
    clicks: list = []
    monkeypatch.setattr(
        test_context, 'controller',
        SimpleNamespace(mouse_move=lambda *a, **k: None,
                        click=lambda p, **k: clicks.append(p)),
        raising=False)
    return clicks


# ==================== 重入裁决归属锁 ====================


# (收口整删)原 test_closing_ops_inherit_base「五 op 均为 CwScreenOpBase
# 子类」(连 _CLOSING_OPS 常量与 _closing_module 装配 helper)删:继承
# 结构 = 静态形状,红时答不出哪个运行行为坏了;结构面归 review 与代码
# 规范。


# (三审整删)原 test_closing_ops_node_budget_gate「五 op 结构锁②」
# (getsource(cls) 断言预算装饰器字面逐屏在场)——源码扫描形态(README
# 禁止清单);「节点预算归装饰器逐屏登记」防线归 review 与代码规范。


def test_reentry_arbitration_flag_gate_combination(test_context,
                                                   monkeypatch) -> None:
    """重入裁决×门组合行为锁(位面过渡/武装箱/未达上限均已迁移两 node
    形态(迭代 2026-09-18-screen-op-flat-report),「已发」旗标裁决住决策
    动作 node 顶部,直驱 act 承重):
    - 位面过渡:门命中 + pending 在位 → 裁决不误判完成(门在 = 动作未
      落地,重点一次机械交回 round_wait);推进体缺坐标的失败轮旗标保持
      已消费态不复活;落地轮(提示已退 = 过渡完成)→ 裁决出口 success +
      零动作 + 旗标清;
    - 未达上限:门命中 + pending 在位 → 裁决不触发,勾选+确认重发、
      旗标经确认体重置(弹窗仍在 = 重发非完成);miss 已发 → 裁决
      success(零动作)。
    等待1-1/位面情报采集无裁决旗标(等待1-1 = 纯等待轮询,位面情报采集
    = 薄转录装帧)。红 = 裁决出口语义漂移(门命中误判完成 / 失败轮旗标
    复活)。"""
    # 位面过渡:门命中 + pending 在位 → 重点一轮(不误判完成)
    blank = SimpleNamespace(x=960, y=540)
    op, clicks = _make_plane_transition(test_context, monkeypatch,
                                        prompt_hit=True, blank=blank)
    op._click_pending = True
    rs = _run_node(test_context, op, op.act)
    assert not rs.is_success and '点空白已发' in (rs.status or ''), (
        f'提示在 = 点击未落地,重点非完成:{rs!r}')
    assert clicks == [blank] and op._click_pending is True, (
        '裁决不误清旗标,重点恰一次')
    # 位面过渡失败轮:裁决已消费旗标 → 缺坐标 fail 轮旗标不复活
    op_f, _clicks_f = _make_plane_transition(test_context, monkeypatch,
                                             prompt_hit=True, blank=None)
    op_f._click_pending = True
    rs_f = _run_node(test_context, op_f, op_f.act)
    assert not rs_f.is_success \
        and '缺「区域-空白点击」建档' in (rs_f.status or ''), (
        f'失败轮入口:{rs_f!r}')
    assert op_f._click_pending is False, (
        '裁决先行消费旗标,失败轮不残留待裁决旗标')
    # 位面过渡落地轮(并入原 reentry_success 锁):提示已退 = 过渡完成 →
    # 裁决出口 success,零动作,旗标清。红 = 裁决出口语义漂移。
    op_r, clicks_r = _make_plane_transition(test_context, monkeypatch,
                                            prompt_hit=False,
                                            blank=SimpleNamespace(x=1, y=1))
    op_r._click_pending = True
    rs_r = _run_node(test_context, op_r, op_r.act)
    assert rs_r.is_success \
        and '过渡完成(重入观察裁决)' in (rs_r.status or ''), (
        f'落地轮裁决 success 交回:{rs_r!r}')
    assert op_r._click_pending is False, '裁决出口清旗标'
    assert clicks_r == [], f'裁决轮零动作:{clicks_r!r}'
    # 武装箱(两 node 形态,裁决住决策动作 node 顶部):门命中 + pending 在位
    # → 重点一轮(不误判完成)
    close_pt = SimpleNamespace(x=1108, y=760)
    op_a, clicks_a = _make_armory(test_context, monkeypatch,
                                  mark_hit=True, close_pt=close_pt)
    op_a._click_pending = True
    rs_a = _run_node(test_context, op_a, op_a.act)
    assert not rs_a.is_success and '点 × 已发' in (rs_a.status or ''), (
        f'标识在 = 点击未落地,重点非完成:{rs_a!r}')
    assert clicks_a == [close_pt] and op_a._click_pending is True, (
        '裁决不误清旗标,重点恰一次')
    # 未达上限:门命中 + pending 在位 → 裁决不触发,确认链重发
    op_d, clicks_d = _make_deploy_not_full(test_context, monkeypatch,
                                           mark_hit=True)
    op_d._confirm_pending = True
    rs_d = _run_node(test_context, op_d, op_d.act)
    assert not rs_d.is_success and rs_d.result == OperationRoundResultEnum.WAIT, (
        f'门命中 = 裁决不触发,确认重发机械交回(round_wait):{rs_d!r}')
    assert [c[0] for c in clicks_d] == ['check', 'confirm'], (
        '勾选+确认重发恰两动作')
    assert op_d._confirm_pending is True, (
        '裁决未触发,旗标经确认体重置')
    # 未达上限 miss 已发:重入裁决 success,零动作
    op_r2, clicks_r2 = _make_deploy_not_full(test_context, monkeypatch,
                                             mark_hit=False)
    op_r2._confirm_pending = True
    rs_r2 = _run_node(test_context, op_r2, op_r2.act)
    assert rs_r2.is_success and '未达上限弹窗已关(重入观察裁决)' in (
        rs_r2.status or ''), f'重入裁决 success 交回:{rs_r2!r}'
    assert op_r2._confirm_pending is False, '裁决出口清旗标'
    assert clicks_r2 == [], '裁决轮零动作'


# ==================== 位面过渡(收口整删)====================


# (收口整删)原 test_plane_transition_dispatch_both_ways「分流双向
# 段迹锁」与 test_plane_transition_reentry_success_zero_trace(重入成功
# 锁,已并入上方组合锁「落地轮」腿)删:装端口段迹面随并存窗收口退役。


# ==================== 位面过渡:观察上报接线锁(实体链写)====================


def _make_plane_transition(test_context, monkeypatch: pytest.MonkeyPatch, *,
                           prompt_hit: bool, blank: object | None = None):
    """位面过渡真类装配(两 node 形态)。桩面 = 提示门/空白点 center/点击
    记录器;链读链(观察 node)由各锁按需补桩。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_transition as ptm,
    )
    op = ptm.CwScreenPlaneTransition(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(prompt_hit))
    monkeypatch.setattr(ptm, 'area_center',
                        lambda ctx, name, screen=None: blank)
    clicks = _stub_controller(test_context, monkeypatch)
    monkeypatch.setattr(ptm.time, 'sleep', lambda *_: None)
    return op, clicks


def test_plane_transition_observe_gate_and_chain_report(
        test_context, monkeypatch) -> None:
    """位面过渡观察 node 锁(两 node 形态):提示门 miss = round_fail 早退
    (现役文案,obs 不装载、零读链);门 hit → 底部行读数构造链值 → report
    落容器(开局链容器终值:node_path + node_path_baseline 双写,链正本
    §3 基线幂等门的写闸面在 report 屏文件,由 test_cw_screen_report_ports
    承重,本锁辖 op 侧读链→report 接线)→ obs 挂实例属性。
    红 = 门失效 / 读链未接 / 容器终值漂移。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_transition as ptm,
    )
    slots = [NodeSlot(idx=0, cx=0, cy=0, state='upcoming', node_type='battle',
                      hu_dist=0.9, boss=None),
             NodeSlot(idx=1, cx=0, cy=0, state='upcoming', node_type=None,
                      hu_dist=None, boss='巳蛇')]
    # ① 门 miss → fail 早退,obs 不装载零读链
    _reads: list = []
    op_off, _c0 = _make_plane_transition(test_context, monkeypatch,
                                         prompt_hit=False, blank=None)
    monkeypatch.setattr(ptm, 'read_node_sequence',
                        lambda ctx, scr: _reads.append(1) or None)
    rs_off = _run_node(test_context, op_off, op_off.observe)
    assert not rs_off.is_success and '位面过渡提示未出现' in (rs_off.status or ''), (
        f'门 miss 文案沿用现役:{rs_off!r}')
    assert op_off._obs is None and _reads == [], (
        f'门早退不装载 obs 零读链:{op_off._obs!r} {_reads!r}')
    # ② 门 hit + 开局容器(镜像/hist 双缺)→ 链构造 + report 双写
    session = StrategySession()
    match = SimpleNamespace(session=session)
    match.gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op, _clicks = _make_plane_transition(test_context, monkeypatch,
                                         prompt_hit=True,
                                         blank=SimpleNamespace(x=1, y=1))
    monkeypatch.setattr(ptm, 'read_node_sequence',
                        lambda ctx, scr: list(slots))
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    gs = game_state_of(session)
    assert gs.node_path.value is not None and gs.node_path.value.plane == 1, (
        f'离场快照经 report 落容器(开局行位面 = P1):{gs.node_path.value!r}')
    assert gs.node_path_baseline.value == gs.node_path.value, (
        '开局基线经 report 同链双写')
    assert gs.node_path.value.seq[0].token == 'battle', '行读数构造进链(观察侧读半部)'
    assert gs.node_path.value.seq[1].token == 'boss' \
        and gs.node_path.value.seq[1].channel == 'sift', (
        f'boss 末槽 SIFT 单元:{gs.node_path.value.seq[1]!r}')
    assert op._obs is not None and op._obs.chain == gs.node_path.value, (
        'obs 挂实例属性(链值载体)')


# ==================== 武装箱弹窗(收口整删)====================


# (收口整删)原 test_armory_box_dispatch_both_ways「武装箱分流双向
# 段迹锁」删:装端口段迹面随并存窗收口退役;其跨路径幸存断言(标识在 =
# 点 × 重点恰一次、缺坐标 fail 零点击)由组合锁武装箱腿与下注说明承重。


def _make_armory(test_context, monkeypatch: pytest.MonkeyPatch, *,
                 mark_hit: bool, close_pt: object | None = None):
    """武装箱弹窗真类装配。桩面 = 标识门/「按钮-关闭」center/点击记录器。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_armory_box as abm,
    )
    op = abm.CwScreenArmoryBox(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(mark_hit))
    monkeypatch.setattr(abm, 'area_center',
                        lambda ctx, name, screen=None: close_pt)
    clicks = _stub_controller(test_context, monkeypatch)
    monkeypatch.setattr(abm.time, 'sleep', lambda *_: None)
    return op, clicks


def test_armory_box_two_node_observe_report_and_round_wait(
        test_context, monkeypatch) -> None:
    """武装箱两 node 形态锁(轻屏统一形态,迭代 2026-09-18-screen-op-flat-
    report):观察 node = 标识门(miss = round_fail 交编排壳,obs 不装载)+
    obs{on_screen} → 占位 report 接线(gs 缺席跳过不炸;本屏现役零容器
    写点,接口为统一形态占位);决策动作 node = 点 × 关闭机械交回
    round_wait(不烧节点重试预算)。红 = 门失效 / 接线断流 / 循环推进
    回退为计预算 retry。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_armory_box as abm,
    )
    # ① 门 miss → fail 早退,obs 不装载
    op_off, _c0 = _make_armory(test_context, monkeypatch, mark_hit=False,
                               close_pt=None)
    rs_off = _run_node(test_context, op_off, op_off.observe)
    assert not rs_off.is_success and '非武装箱弹窗' in (rs_off.status or ''), (
        f'门 miss 文案沿用现役:{rs_off!r}')
    assert op_off._obs is None, '门早退不装载 obs'
    # ② 门 hit → obs 装载(on_screen)+ 占位 report 调用(gs 在场)
    _reports: list = []
    monkeypatch.setattr(abm, 'report_screen_armory_box_obs',
                        lambda gs, obs: _reports.append(obs))
    monkeypatch.setattr(
        test_context, 'cw_match',
        SimpleNamespace(session=SimpleNamespace(), gs=object()), raising=False)
    op, _clicks = _make_armory(test_context, monkeypatch, mark_hit=True,
                               close_pt=SimpleNamespace(x=1108, y=760))
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    assert op._obs is not None and op._obs.on_screen is True, 'obs 挂实例属性'
    assert len(_reports) == 1 and _reports[0] is op._obs, (
        f'占位 report 接线恰一次(统一形态调用):{_reports!r}')
    # ③ 点 × 关闭 → round_wait 机械交回(落地裁决 = 下轮 act 顶部)
    rs2 = _run_node(test_context, op, op.act)
    assert rs2.result == OperationRoundResultEnum.WAIT, (
        f'循环推进 = round_wait(不计节点重试预算):{rs2!r}')
    assert op._click_pending is True, '点 × 已发 → pending 置位(重入裁决承载)'


# ==================== 未达上限弹窗(收口整删)====================


def _make_deploy_not_full(test_context, monkeypatch: pytest.MonkeyPatch, *,
                          mark_hit: bool):
    """未达上限弹窗真类装配。桩面 = 标识门/勾选确认坐标/点击与确认链。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_deploy_not_full as dnm,
    )
    op = dnm.CwScreenDeployNotFull(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(mark_hit))
    monkeypatch.setattr(dnm, 'area_center',
                        lambda ctx, name, screen=None: SimpleNamespace(x=1, y=1))
    clicks: list = []
    monkeypatch.setattr(dnm, 'safe_click',
                        lambda op_, pt, **k: clicks.append(('check', pt)))
    monkeypatch.setattr(dnm, 'emit_overlay_confirm',
                        lambda op_, **k: clicks.append(('confirm', k))
                        or _RETRY_RS)
    monkeypatch.setattr(dnm.time, 'sleep', lambda *_: None)
    return op, clicks


# (收口整删)原 test_deploy_not_full_dispatch_both_ways「未达上限分流
# 双向段迹锁」删:装端口段迹面随并存窗收口退役;门命中确认重发腿与
# miss 已发裁决 success 腿并入上方组合锁。


# ==================== 等待1-1:纯等待两 node 形态锁 ====================


def _make_wait_one_one(test_context, monkeypatch: pytest.MonkeyPatch, *,
                       anchor_hit: bool):
    """等待1-1 真类装配(两 node 形态)。桩面 = 备战锚/存图替身。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wait_one_one as wom,
    )
    op = wom.CwScreenWaitOneOne(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(anchor_hit))
    shots: list[str] = []
    monkeypatch.setattr(op, 'save_screenshot',
                        lambda prefix=None: shots.append(prefix or ''))
    return op, shots


def test_wait_one_one_anchor_hit_and_poll_round_wait(
        test_context, monkeypatch) -> None:
    """等待1-1 两 node 形态锁(纯等待型,现役 handle 逐位映射):锚命中 →
    观察轮 obs 装载 + 占位 report 接线恰一次(现役零容器写点,统一形态
    占位)→ round_success 进决策动作 node → act 零动作 success 交回
    ('1-1 备战就绪' 终态语义同点);锚 miss 且未超时 → 观察轮 round_wait
    轮询(自环,不吃 retry 预算,轮询轮不装载 obs)。
    红 = 轮询改计预算 retry / 终态语义漂移 / 接线断流。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wait_one_one as wom,
    )
    # ① 锚命中:观察轮 obs + 占位 report 恰一次 → act 零动作交回
    op, _shots = _make_wait_one_one(test_context, monkeypatch, anchor_hit=True)
    _reports: list = []
    monkeypatch.setattr(wom, 'report_screen_wait_one_one_obs',
                        lambda gs, obs: _reports.append(obs))
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=SimpleNamespace(), gs=object()),
                        raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'锚命中观察轮 success 进 act:{rs!r}'
    assert op._obs is not None and op._obs.on_screen is True, 'obs 挂实例属性'
    assert len(_reports) == 1 and _reports[0] is op._obs, (
        f'占位 report 接线恰一次(统一形态调用):{_reports!r}')
    rs_act = _run_node(test_context, op, op.act)
    assert rs_act.is_success and rs_act.status == '1-1 备战就绪', (
        f'锚命中终态语义(act 零动作交回):{rs_act!r}')
    # ② 锚 miss 且未超时:观察轮 round_wait 轮询(不吃 retry 预算)
    op_w, _s_w = _make_wait_one_one(test_context, monkeypatch, anchor_hit=False)
    rs_w = _run_node(test_context, op_w, op_w.observe)
    assert rs_w.result == OperationRoundResultEnum.WAIT, (
        f'锚 miss = 轮询等待(不吃 retry 预算):{rs_w!r}')
    assert op_w._obs is None, '轮询轮不装载 obs'


def test_wait_one_one_timeout_leaves_evidence(test_context,
                                              monkeypatch) -> None:
    """超时兜底:假时钟快进,锚一直不现 → 观察轮早退 fail 留证(存图替身
    承接,不落真实 .debug),轮询至上界才退出(非首轮放弃)。
    红 = 超时判定丢失 / 提前放弃 / 留证丢失。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wait_one_one as wom,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_flow_const import (
        ONE_ONE_MAX_WAIT_S,
    )
    op, shots = _make_wait_one_one(test_context, monkeypatch,
                                   anchor_hit=False)
    clock = {'now': 0.0}

    def _fake_clock(_clock=clock) -> float:
        _clock['now'] += 2.0   # 每轮 +2s(>轮询间隔 1s,快进)
        return _clock['now']

    monkeypatch.setattr(wom, '_monotonic', _fake_clock)
    res = None
    for _ in range(20):
        res = _run_node(test_context, op, op.observe)
        if res.result == OperationRoundResultEnum.FAIL:
            break
    assert res is not None and res.result == OperationRoundResultEnum.FAIL, (
        '超时未触发')
    assert '等待 1-1 备战超时' in (res.status or ''), (
        f'留证 fail 语义:{res!r}')
    assert shots == ['wait_one_one_timeout'], '超时留证存图'
    assert clock['now'] >= ONE_ONE_MAX_WAIT_S, (
        '轮询至上界才退出,非首轮放弃')


# ==================== 位面情报采集:薄转录装帧 + 双节点保留 ====================


# (收口整删)原 test_plane_intel_thin_transcription_single_body「薄转录
# 锁行为半(新五段/旧零段迹双驱动)」删:装端口段迹面随并存窗收口退役;
# 采集完 success 语义由双节点图边锁同文件同构体承重,转录单一源面归
# review 与代码规范。


def test_plane_intel_observe_mount_and_placeholder_report(
        test_context, monkeypatch) -> None:
    """装帧观察 node 锁(薄转录直通形态):观察 node 仅装配稳定帧 →
    obs{on_screen} → 占位 report 接线恰一次(match/gs 在场;本屏现役零
    容器写点,接口为统一形态占位)→ round_success 进采集 node;场景门
    [在位面详情/备战/其它]不前移(仍住采集体,采集轮不被观察 node 拦截)。
    红 = 场景门前移 / 接线断流。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel as pim,
    )
    op = pim.CwScreenPlaneIntel(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    _reports: list = []
    monkeypatch.setattr(pim, 'report_screen_plane_intel_obs',
                        lambda gs, obs: _reports.append(obs))
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=SimpleNamespace(), gs=object()),
                        raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'装帧观察 success 进采集 node:{rs!r}'
    assert op._obs is not None and op._obs.on_screen is True, 'obs 挂实例属性'
    assert len(_reports) == 1 and _reports[0] is op._obs, (
        f'占位 report 接线恰一次(统一形态调用):{_reports!r}')


def test_plane_intel_dual_node_graph_edge_preserved(test_context) -> None:
    """双节点图边保留:「采集 → 关闭并回写」显式 node_from 边在位(首跑
    教训:无显式边时采集 success 被当 op 终点,关闭节点漏跑,画面留在
    位面详情);装帧观察 node 前置后边不丢。红 = 迁移顺手并节点复活该
    事故形态。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel as pim,
    )
    # 边的登记面以运行时节点图为准(下方真图查询);不另做装饰器源码
    # 字面扫描——合法改写登记写法即假红,纪律 8(运行时锁承重同事实)。
    op = pim.CwScreenPlaneIntel(test_context)
    op._init_network()   # 显式建图(框架在 execute 前调;测试内直调取边登记面)
    edges = op._node_edges_map.get('采集', [])
    assert any(e.node_to.cn == '关闭并回写' for e in edges), (
        f'采集→关闭并回写 边未在节点图登记:{op._node_edges_map!r}')


# ==================== 收口锁(不恢复)====================
#
# 分诊:原 test_closure_all_cw_screen_ops_inherit_base(AST 全目录
# 扫描 + 继承闭包守卫 + _CLOSURE_EXEMPT 豁免登记门)不恢复——源码扫描
# 形态(AGENTS §10.4.4 包布局/依赖方向守卫禁令):红的时候是静态结构变
# 了,答不出「哪个运行行为坏了」。「画面 op 必挂 CwScreenOpBase 或逐名
# 豁免登记」的收口裁决归 review 与代码规范(运行时点名继承锁亦随并存
# 窗收口整删,同判:结构面无运行行为可断)。
