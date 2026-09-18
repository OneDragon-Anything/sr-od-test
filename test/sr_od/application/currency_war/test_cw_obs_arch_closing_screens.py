"""统一观察架构·收尾五屏迁移锁 + cw_screen/cw_op 收口锁(余项收口阶段三)。

设计正本 = docs/develop/sr_od/application/currency_war/flow/统一观察架构-画面op基类设计.md
(下称「架构设计」);迁移粒度/五段形态依据 = changes/2026-09-11-
unified-observation/details/收尾屏迁移详设.md(逐屏五段表与语义保真点);
迁移手法单一源 = 装配点分流 + 五段钩子转录 + 实机适配器①封口 + on_outcome
注册表(先例:CwScreenPrep/遭遇/盛会之星;断言集模板 =
test_cw_obs_arch_event_screens.py;五相位屏先例 = test_cw_obs_arch_phase_
screens.py)。本批五屏:位面过渡 CwScreenPlaneTransition / 武装箱弹窗
CwScreenArmoryBox / 未达上限弹窗 CwScreenDeployNotFull / 等待1-1
CwScreenWaitOneOne / 位面情报采集 CwScreenPlaneIntel(薄转录 + 双节点图
保留;五屏均不重挂变体,总纲关键取舍 2)。

**F11 sim 腿不适用例外清单(随迁移批逐屏落测试 docstring,总纲 §2.2-3)**:

- 位面过渡/武装箱弹窗/未达上限弹窗/等待1-1:sim 腿 = 不适用——sim 无对应
  画面段(架构设计 §3.4 过渡相位/中断弹窗行),本批等价判据主承重 =
  实机在册行为锁(旧路径流程测原样保绿)+ 本文件新路径行为锁,
  禁引用 sim 域对拍;
- 位面情报采集:sim 腿 = 不适用——sim 无位面详情/敌人情报对应画面段
  (§3.4 sim 侧申报),等价判据主承重 = 纯函数三件在册测试锁
  (零触碰;原承载文件已随清理批退役,采集体行为面现无独立锁,
  本文件薄转录锁只辖分流段迹,体面覆盖缺口已申报)
  + 本文件薄转录新路径行为锁。

**写入流对拍 = 本阶段无适用面**(总纲 §2.2-4 如实申报):五屏零 GameState
写端;位面情报采集采集结果经 ``ctx.cw_plane_bosses``/``cw_plane_affixes``
中转(消费接线批挂账,原样)。发射型接线锁/登记语义对拍锁/豁免留守锁亦无
适用屏(全篇 on_outcome = 无登记件,注册表缺席 = 零动作)。

锁的语义(测试纪律 7 自检;出处 = landing 阶段三判据 + 总纲契约 1-6;
生产端口恒 None 直连旧路径,五段新路径 = 测试驱动形态——五 op 结构锁与
逐屏装端口分流/段迹锁已随并存窗收口整删,行为锁单驱动生产路径):

- **重入裁决×门组合行为锁**(总纲契约 6 行为面):「已发」旗标裁决位 =
  位面过渡(五段形态)住分流**之前**共享段;武装箱(两 node 形态,迭代
  2026-09-18-screen-op-flat-report)住决策动作 node 顶部,直驱 act 承重;
  未达上限 = miss 分支内式:门命中 + pending 在位 → 裁决不触发、确认重发,
  miss 已发 → 裁决 success——两屏位序差异的行为观测点 =
  门命中+旗标在位时旗标清否,由组合行为锁承重(收尾屏详设 §1-§3)。
- **薄转录锁**(位面情报采集,总纲契约 2):决策循环消费
  ``_collect_cycle`` 单一共享体(禁第二套转录)+ 双节点图边(采集→关闭
  并回写)保留(收尾屏详设关键取舍 2;原装端口薄转录行为锁随并存窗
  收口退役,双节点图边运行时锁留守)。
- **收口锁不恢复**(分诊,原 landing 阶段三判据的目录级守卫):
  「cw_screen/ 与 cw_op/ 顶层 op 类必为 CwScreenOpBase 后代(豁免登记
  门)」以 AST 全目录扫描实现,属源码扫描形态(AGENTS §10.4.4 禁),
  摘除不恢复。文件尾留分诊注。

驱动方式 = 真类实例(构造走 __init__,注册表/适配器位在位)+ 读链/点击链
桩化;装配点分流桩端口 = ``_cw_helpers.install_dispatch_stub_ports`` 单一源;
不装端口 = 生产缺省形态(行为锁主驱动)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    install_dispatch_stub_ports,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)
from test.sr_od.application.currency_war._cw_helpers import (
    uninstall_ports as _uninstall_ports,
)

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)

_RETRY_RS = OperationRoundResult(OperationRoundResultEnum.RETRY, status='stub-confirm')

_FULL_TRACE = ['observe', 'reconcile', 'decide', 'act', 'on_outcome']


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
    """重入裁决×门组合行为锁(总纲契约 6 的行为面;替代原 .index() 位序
    源码锁——纪律 8 位序锁禁令。「裁决先行式 vs miss 分支内式」两屏差异
    的行为观测点 = 门命中 + 旗标在位时裁决是否消费旗标;裁决住分流之前
    两路径共享段,单驱动生产路径承重,install 参数化腿已随并存窗收口
    砍除):
    - 位面过渡/武装箱(裁决先行式):门命中 + pending 在位 → 裁决不误判
      完成(门在 = 动作未落地,重点一次机械交回);推进体缺坐标的失败轮
      旗标保持已消费态不复活(若裁决被移进门后/miss 分支内,此轮旗标
      残留 True,断言红);落地轮(提示已退 = 过渡完成)→ 裁决出口
      success + 零动作零段迹 + 旗标清;
    - 未达上限(miss 分支内式):门命中 + pending 在位 → 裁决不触发,
      勾选+确认重发、旗标经确认体重置(弹窗仍在 = 重发非完成);miss 已发
      → 裁决 success(零段迹零动作)。
    等待1-1/位面情报采集无裁决旗标,其分流语义归同文件双向行为锁
    (生产路径段迹承重;原装端口段迹分流锁已随并存窗收口整删)。
    红 = 裁决出口语义漂移(门命中误判完成 / 失败轮旗标复活)。"""
    # 位面过渡:门命中 + pending 在位 → 重点一轮(不误判完成)
    blank = SimpleNamespace(x=960, y=540)
    op, clicks = _make_plane_transition(test_context, monkeypatch,
                                        prompt_hit=True, blank=blank)
    op._click_pending = True
    rs = _run_node(test_context, op, op.handle)
    assert not rs.is_success and '点空白已发' in (rs.status or ''), (
        f'提示在 = 点击未落地,重点非完成:{rs!r}')
    assert clicks == [blank] and op._click_pending is True, (
        '裁决不误清旗标,重点恰一次')
    assert op._lifecycle_trace == [], f'段迹:{op._lifecycle_trace}'
    # 位面过渡失败轮:裁决已消费旗标 → 缺坐标 fail 轮旗标不复活
    op_f, _clicks_f = _make_plane_transition(test_context, monkeypatch,
                                             prompt_hit=True, blank=None)
    op_f._click_pending = True
    rs_f = _run_node(test_context, op_f, op_f.handle)
    assert not rs_f.is_success \
        and '缺「区域-空白点击」建档' in (rs_f.status or ''), (
        f'失败轮入口:{rs_f!r}')
    assert op_f._click_pending is False, (
        '裁决先行消费旗标,失败轮不残留待裁决旗标')
    # 位面过渡落地轮(并入原 reentry_success 锁):提示已退 = 过渡完成 →
    # 裁决出口 success,零动作零段迹,旗标清。红 = 裁决移进 observe
    # (段迹非空)或裁决出口语义漂移。
    op_r, clicks_r = _make_plane_transition(test_context, monkeypatch,
                                            prompt_hit=False,
                                            blank=SimpleNamespace(x=1, y=1))
    op_r._click_pending = True
    rs_r = _run_node(test_context, op_r, op_r.handle)
    assert rs_r.is_success \
        and '过渡完成(重入观察裁决)' in (rs_r.status or ''), (
        f'落地轮裁决 success 交回:{rs_r!r}')
    assert op_r._click_pending is False, '裁决出口清旗标'
    assert clicks_r == [] and op_r._lifecycle_trace == [], (
        f'裁决轮零动作零段迹:{clicks_r!r} {op_r._lifecycle_trace!r}')
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
    rs_d = _run_node(test_context, op_d, op_d.handle)
    assert not rs_d.is_success and 'stub-confirm' in (rs_d.status or ''), (
        f'门命中 = 裁决不触发,确认重发机械交回:{rs_d!r}')
    assert [c[0] for c in clicks_d] == ['check', 'confirm'], (
        '勾选+确认重发恰两动作')
    assert op_d._confirm_pending is True, (
        'miss 分支内裁决未触发,旗标经确认体重置')
    # 未达上限 miss 已发(并入原分流锁随死腿):重入裁决 success,
    # 零动作零段迹(裁决留守分流前共享段)
    op_r2, clicks_r2 = _make_deploy_not_full(test_context, monkeypatch,
                                             mark_hit=False)
    op_r2._confirm_pending = True
    rs_r2 = _run_node(test_context, op_r2, op_r2.handle)
    assert rs_r2.is_success and '未达上限弹窗已关(重入观察裁决)' in (
        rs_r2.status or ''), f'重入裁决 success 交回:{rs_r2!r}'
    assert op_r2._confirm_pending is False, '裁决出口清旗标'
    assert clicks_r2 == [] and op_r2._lifecycle_trace == [], (
        '裁决轮零动作零段迹')


# ==================== 位面过渡(收口整删)====================


# (收口整删)原 test_plane_transition_dispatch_both_ways「分流双向
# 段迹锁」与 test_plane_transition_reentry_success_zero_trace(重入成功
# 锁,已并入上方组合锁「落地轮」腿)删:装端口段迹面随并存窗收口退役。


# ==================== 位面过渡:分流双向行为锁 ====================


def _make_plane_transition(test_context, monkeypatch: pytest.MonkeyPatch, *,
                           prompt_hit: bool, blank: object | None = None):
    """位面过渡真类装配。桩面 = 提示门/空白点 center/点击记录器。"""
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


# ==================== 等待1-1:分流双向行为锁 ====================


def _make_wait_one_one(test_context, monkeypatch: pytest.MonkeyPatch, *,
                       anchor_hit: bool):
    """等待1-1 真类装配。桩面 = 备战锚/存图替身。"""
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


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_wait_one_one_dispatch_both_ways(test_context, monkeypatch,
                                         install: bool) -> None:
    """等待1-1 分流双向(纯等待型):装两端口 → 锚命中 = observe 早退
    success(仅 observe 段迹);锚 miss = 决策循环轮询 round_wait(五段迹,
    act 零动作如实申报);不装端口 → 旧路径零段迹同行为。红 = 分流判据
    破坏或轮询语义漂移。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, _shots = _make_wait_one_one(test_context, monkeypatch, anchor_hit=True)
    rs = _run_node(test_context, op, op.handle)
    assert rs.is_success and rs.status == '1-1 备战就绪', f'锚命中语义:{rs!r}'
    assert op._lifecycle_trace == (['observe'] if install else []), (
        f'锚命中早退段迹:{op._lifecycle_trace}')
    # 锚 miss:决策循环轮询 round_wait
    op_w, _s_w = _make_wait_one_one(test_context, monkeypatch, anchor_hit=False)
    rs_w = _run_node(test_context, op_w, op_w.handle)
    assert rs_w.result == OperationRoundResultEnum.WAIT, (
        f'锚 miss = 轮询等待(不吃 retry 预算):{rs_w!r}')
    assert op_w._lifecycle_trace == (_FULL_TRACE if install else []), (
        f'轮询段迹(act 零动作如实申报):{op_w._lifecycle_trace}')


def test_wait_one_one_timeout_leaves_evidence_new_path(test_context,
                                                       monkeypatch) -> None:
    """超时兜底走新路径:假时钟快进,锚一直不现 → observe 早退 fail 留证
    (存图替身承接,不落真实 .debug);旧路径对照零段迹同 fail。红 = 超时
    判定被留在旧路径或留证丢失。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wait_one_one as wom,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_flow_const import (
        ONE_ONE_MAX_WAIT_S,
    )
    for install in (True, False):
        if install:
            install_dispatch_stub_ports(monkeypatch)
        else:
            _uninstall_ports(monkeypatch)
        op, shots = _make_wait_one_one(test_context, monkeypatch,
                                       anchor_hit=False)
        clock = {'now': 0.0}

        def _fake_clock(_clock=clock) -> float:
            _clock['now'] += 2.0   # 每轮 +2s(>轮询间隔 1s,快进)
            return _clock['now']

        monkeypatch.setattr(wom, '_monotonic', _fake_clock)
        res = None
        for _ in range(20):
            res = _run_node(test_context, op, op.handle)
            if res.result == OperationRoundResultEnum.FAIL:
                break
        assert res is not None and res.result == OperationRoundResultEnum.FAIL, (
            f'install={install}:超时未触发')
        assert '等待 1-1 备战超时' in (res.status or ''), (
            f'install={install}:留证 fail 语义:{res!r}')
        assert shots == ['wait_one_one_timeout'], (
            f'install={install}:超时留证存图')
        assert clock['now'] >= ONE_ONE_MAX_WAIT_S, (
            f'install={install}:轮询至上界才退出,非首轮放弃')
        if install:
            assert op._lifecycle_trace[-1] == 'observe', (
                '超时轮 = observe 段早退(fail)')
            assert op._lifecycle_trace[0] == 'observe'
        else:
            assert op._lifecycle_trace == [], f'install={install}:旧路径零段迹'


# ==================== 位面情报采集:双节点保留 ====================


# (收口整删)原 test_plane_intel_thin_transcription_single_body「薄转录
# 锁行为半(新五段/旧零段迹双驱动)」删:装端口段迹面随并存窗收口退役;
# 采集完 success 语义由双节点图边锁同文件同构体承重,转录单一源面归
# review 与代码规范。


def test_plane_intel_dual_node_graph_edge_preserved(test_context) -> None:
    """双节点图边保留(收尾屏详设关键取舍 2):「采集 → 关闭并回写」显式
    node_from 边在位(首跑教训:无显式边时采集 success 被当 op 终点,关闭
    节点漏跑,画面留在位面详情)。红 = 迁移顺手并节点复活该事故形态。"""
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
