"""统一观察架构·收尾五屏迁移锁 + cw_screen 收口锁(账本 T-48,余项收口阶段三)。

设计正本 = docs/develop/currency_war/design/统一观察架构-画面op基类设计.md
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
  画面段(架构设计 §3.4 过渡相位/中断弹窗行),本批等价判据主承重 = 实机
  在册行为锁(test_cw_flow_ops.py 等在册面原样保绿)+ 本文件新路径行为锁,
  禁引用 sim 域对拍;
- 位面情报采集:sim 腿 = 不适用——sim 无位面详情/敌人情报对应画面段
  (§3.4 sim 侧申报),等价判据主承重 = 纯函数三件在册测试锁
  (test_cw_plane_intel_start_plane.py / test_cw_node_screens.py,零触碰)
  + 本文件薄转录新路径行为锁。

**写入流对拍 = 本阶段无适用面**(总纲 §2.2-4 如实申报):五屏零 BoardState
写端;位面情报采集采集结果经 ``ctx.cw_plane_bosses``/``cw_plane_affixes``
中转(消费接线批挂账,原样)。发射型接线锁/登记语义对拍锁/豁免留守锁亦无
适用屏(全篇 on_outcome = 无登记件,注册表缺席 = 零动作)。

锁的语义(测试纪律 7 自检;出处 = landing 阶段三判据 + 总纲契约 1-6):

- **五 op 结构锁**:五 op 是 CwScreenOpBase 子类 ∧ start 节点方法顶部装配点
  分流(位面过渡/武装箱/未达上限/等待1-1 = ``handle``,位面情报采集 =
  ``collect()`` 节点首行;两端口完整在场 → ``run_lifecycle``;缺省 None =
  生产直连旧路径,§9.1 并存期)∧ 节点预算归装饰器不随路径变(总纲契约 1)。
- **重入裁决归属锁**(总纲契约 6,单一定谳):位面过渡/武装箱/未达上限的
  「已发」旗标裁决住 handle 分流判据**之前**两路径共享段;裁决位序逐字保真
  禁统一——位面过渡/武装箱 = pending 先行、miss fail 后置,未达上限 = miss
  分支内先查 pending 后 fail(收尾屏详设 §1-§3)。红 = 裁决被转录进 observe
  段/适配器①,或位序被顺手统一。
- **新路径行为锁**(§9.1-F2 主门 (a) 本阶段行,逐屏适用性随批登记:五屏全
  适用):装两端口经节点方法走新路径,段迹形态 + 单轮动作/确认置位行为
  (模板同构 = 五相位屏锁);不装端口 → 旧路径零段迹同行为(旧路径不写
  迹纪律)。
- **薄转录锁**(位面情报采集,总纲契约 2):observe 直通(场景门不前移)+
  决策循环消费 ``_collect_cycle`` 单一共享体(新旧路径同一份,禁第二套
  转录)+ 双节点图边(采集→关闭并回写)保留(收尾屏详设关键取舍 2)。
- **收口锁**(landing 阶段三判据;B4 判据第 1 条的 cw_screen/ 目录达成
  凭据):cw_screen 全目录顶层类凡op 祖链达 SrOperation 者必为 CwScreenOpBase
  后代(AST 全目录扫描 + 运行时 issubclass 复核双面)。达成声明收窄定谳
  (design.md §2.1-4):点名清单余 cw_op/ 商店系三件 CwOpBuyCards/
  CwOpOpenShop/CwOpCloseShop 直继 SrOperation,不在本迭代,挂账归后续批。

驱动方式 = 真类实例(构造走 __init__,注册表/适配器位在位)+ 读链/点击链
桩化;装配点分流桩端口 = ``_cw_helpers.install_dispatch_stub_ports`` 单一源;
不装端口(生产缺省形态)= 旧路径代表驱动(并存窗旧路径锁专用)。
"""
from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_op_base import (
    CwScreenOpBase,
)
from sr_od.operations.sr_operation import SrOperation
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.app.currency_war._cw_helpers import install_dispatch_stub_ports

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)

_RETRY_RS = OperationRoundResult(OperationRoundResultEnum.RETRY, status='stub-confirm')

_FULL_TRACE = ['observe', 'reconcile', 'decide', 'act', 'on_outcome']

#: 五屏清单(模块名 → 画面 op 类名;start 节点方法名)
_CLOSING_OPS = (
    ('cw_screen_plane_transition', 'CwScreenPlaneTransition', 'handle'),
    ('cw_screen_armory_box', 'CwScreenArmoryBox', 'handle'),
    ('cw_screen_deploy_not_full', 'CwScreenDeployNotFull', 'handle'),
    ('cw_screen_wait_one_one', 'CwScreenWaitOneOne', 'handle'),
    ('cw_screen_plane_intel', 'CwScreenPlaneIntel', 'collect'),
)

_DISPATCH_EXPR = ('observation_source() is not None'
                  ' and action_sink() is not None')


def _closing_module(name: str):
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_armory_box,
        cw_screen_deploy_not_full,
        cw_screen_plane_intel,
        cw_screen_plane_transition,
        cw_screen_wait_one_one,
    )
    return {
        'cw_screen_plane_transition': cw_screen_plane_transition,
        'cw_screen_armory_box': cw_screen_armory_box,
        'cw_screen_deploy_not_full': cw_screen_deploy_not_full,
        'cw_screen_wait_one_one': cw_screen_wait_one_one,
        'cw_screen_plane_intel': cw_screen_plane_intel,
    }[name]


def _uninstall_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    """卸载复位(生产缺省形态;旧路径代表驱动专用,先例 = T-8 锁)。"""
    from sr_od.application.currency_war import cw_game_ports as _ports_mod
    monkeypatch.setattr(_ports_mod, '_INSTALLED', (None, None))


def _run_node(test_context, op, fn) -> object:
    """节点函数运行外壳(fast_sleep + running_state;返回轮次结果)。"""
    with fast_sleep():
        enter_running_state(test_context)
        try:
            return fn()
        finally:
            reset_running_state(test_context, op)


class _Area:
    """round_by_find_area 桩回执(程序化回 in_screen/in_node)。"""

    def __init__(self, ok: bool) -> None:
        self.is_success = ok


def _stub_controller(test_context, monkeypatch: pytest.MonkeyPatch) -> list:
    """controller 桩:mouse_move no-op + click 记录器。返回点击记录列表。"""
    clicks: list = []
    monkeypatch.setattr(
        test_context, 'controller',
        SimpleNamespace(mouse_move=lambda *a, **k: None,
                        click=lambda p, **k: clicks.append(p)),
        raising=False)
    return clicks


# ==================== 五 op 结构锁 + 重入裁决归属锁 ====================


def test_closing_ops_inherit_base() -> None:
    """五 op 结构锁①(landing 阶段三判据 1):五 op 均为 CwScreenOpBase
    子类。红 = 迁移回退或漏迁。"""
    for mod_name, cls_name, _node in _CLOSING_OPS:
        cls = getattr(_closing_module(mod_name), cls_name)
        assert issubclass(cls, CwScreenOpBase), (
            f'{cls_name} 未迁移到 CwScreenOpBase(T-48 收尾五屏)')


def test_closing_ops_dispatch_source_form() -> None:
    """五 op 结构锁②:装配点分流表达式 + 位置(分流措辞 = 各屏 start 节点
    方法顶部,位面情报采集 = collect() 节点首行)+ 节点预算归装饰器不随
    路径变(总纲契约 1)。红 = 分流判据缺失/后置或预算漂移。"""
    _BUDGETS = {
        'cw_screen_plane_transition': 'node_max_retry_times=8',
        'cw_screen_armory_box': 'node_max_retry_times=8',
        'cw_screen_deploy_not_full': 'node_max_retry_times=10',
        'cw_screen_wait_one_one': "name='等待1-1', is_start_node=True)",
        'cw_screen_plane_intel': 'node_max_retry_times=60',
    }
    for mod_name, cls_name, node_name in _CLOSING_OPS:
        cls = getattr(_closing_module(mod_name), cls_name)
        src = inspect.getsource(getattr(cls, node_name))
        assert _DISPATCH_EXPR in src, f'{cls_name}: 装配点分流判据缺失'
        assert 'run_lifecycle' in src, f'{cls_name}: 分流缺 run_lifecycle'
        assert _BUDGETS[mod_name] in inspect.getsource(cls), (
            f'{cls_name}: 节点预算漂移(预算归装饰器不随路径变,总纲契约 1)')


def test_reentry_arbitration_position_and_order() -> None:
    """重入裁决归属锁(总纲契约 6 + 收尾屏详设 §1-§3 位序红线):
    - 位面过渡/武装箱:「已发」旗标裁决住分流**之前**;裁决序 = pending
      先行、miss fail 后置(pending 判据先于 miss fail 出现);
    - 未达上限:裁决住分流之前;裁决序 = miss 分支内先查 pending 后 fail
      (miss 判据先于 pending 出现——与位面过渡序**刻意不同**,逐字保真
      禁统一);
    - 等待1-1/位面情报采集:无裁决旗标,分流在首行(锚/场景判定之前)。
    红 = 裁决被移进五段 observe 形态/适配器,或位序被顺手统一。"""
    pt_src = inspect.getsource(
        _closing_module('cw_screen_plane_transition').CwScreenPlaneTransition.handle)
    i_flag = pt_src.index('self._click_pending')
    i_disp = pt_src.index('run_lifecycle')
    assert i_flag < i_disp, '位面过渡:重入裁决须住装配点分流之前(总纲契约 6)'
    assert i_flag < pt_src.index('if not _hit'), (
        '位面过渡裁决序 = pending 先行、miss fail 后置(详设 §1,禁与未达上限统一)')

    ab_src = inspect.getsource(
        _closing_module('cw_screen_armory_box').CwScreenArmoryBox.handle)
    assert ab_src.index('self._click_pending') < ab_src.index('run_lifecycle'), (
        '武装箱:重入裁决须住装配点分流之前(总纲契约 6)')
    assert ab_src.index('self._click_pending') < ab_src.index('if not _hit'), (
        '武装箱裁决序 = pending 先行(详设 §2)')

    dn_src = inspect.getsource(
        _closing_module('cw_screen_deploy_not_full').CwScreenDeployNotFull.handle)
    i_disp = dn_src.index('run_lifecycle')
    i_miss = dn_src.index('if not _hit')
    i_flag = dn_src.index('self._confirm_pending')
    assert i_miss < i_flag, (
        '未达上限裁决序 = miss 分支内先查 pending(与位面过渡序刻意不同,'
        '详设 §3 逐字保真禁统一)')
    assert i_flag < i_disp, '未达上限:重入裁决须住装配点分流之前(总纲契约 6)'

    wo_src = inspect.getsource(
        _closing_module('cw_screen_wait_one_one').CwScreenWaitOneOne.handle)
    assert wo_src.index('run_lifecycle') < wo_src.index('self.PREP_ANCHOR'), (
        '等待1-1:无裁决旗标,分流在首行、锚判定之前(详设 §4)')
    assert '_pending' not in wo_src, '等待1-1 无裁决旗标(纯等待型)'

    pi_cls = _closing_module('cw_screen_plane_intel').CwScreenPlaneIntel
    pi_src = inspect.getsource(pi_cls.collect)
    assert pi_src.index('return self.run_lifecycle()') \
        < pi_src.index('return self._collect_cycle()'), (
        '位面情报采集:分流在 collect() 节点首行、采集体委托之前(详设 §5)')


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


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_plane_transition_dispatch_both_ways(test_context, monkeypatch,
                                             install: bool) -> None:
    """位面过渡分流双向(主门 (a) 本屏行):装两端口 → 五段新路径(段迹恰
    五段;点空白发出置 pending + round_retry 机械交回);提示 miss → observe
    门 fail 早退(仅 observe 段迹,零动作);不装端口 → 旧路径零段迹同行为。
    红 = 分流判据破坏或段迹漂移。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    blank = SimpleNamespace(x=960, y=540)
    op, clicks = _make_plane_transition(test_context, monkeypatch,
                                        prompt_hit=True, blank=blank)
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == (_FULL_TRACE if install else []), (
        f'段迹形态漂移:{op._lifecycle_trace}')
    assert clicks == [blank] and op._click_pending is True, (
        '点空白恰一次 + pending 置位(重入裁决承载)')
    assert not rs.is_success and '点空白已发' in (rs.status or ''), (
        f'机械交回 round_retry(保形):{rs!r}')
    # 提示 miss:门 fail 早退(新路径 = observe 段早退仅 observe 段迹;
    # 旧路径 = 旧序列早退零段迹,行为同形)
    op_f, clicks_f = _make_plane_transition(test_context, monkeypatch,
                                            prompt_hit=False, blank=blank)
    rs_f = _run_node(test_context, op_f, op_f.handle)
    assert not rs_f.is_success and '位面过渡提示未出现' in (rs_f.status or ''), (
        f'提示门早退语义不变:{rs_f!r}')
    assert op_f._lifecycle_trace == (['observe'] if install else []), (
        f'离屏早退段迹:{op_f._lifecycle_trace}')
    assert clicks_f == [], '提示 miss 零动作(交编排壳按步分流)'


def test_plane_transition_reentry_success_zero_trace(test_context,
                                                     monkeypatch) -> None:
    """重入裁决(两路径共用,分流前共享段):点空白已发 + 提示不在 = 过渡
    完成 → success 交回,本轮不经生命周期(零段迹)。红 = 裁决移进 observe
    (段迹非空)或裁决出口语义漂移。"""
    for install, trace in ((True, []), (False, [])):
        if install:
            install_dispatch_stub_ports(monkeypatch)
        else:
            _uninstall_ports(monkeypatch)
        op, clicks = _make_plane_transition(test_context, monkeypatch,
                                            prompt_hit=False,
                                            blank=SimpleNamespace(x=1, y=1))
        op._click_pending = True
        rs = _run_node(test_context, op, op.handle)
        assert rs.is_success and '过渡完成(重入观察裁决)' in (rs.status or ''), (
            f'install={install}:重入裁决 success 交回:{rs!r}')
        assert op._click_pending is False, f'install={install}:裁决出口清旗标'
        assert clicks == [], f'install={install}:裁决轮零动作'
        assert op._lifecycle_trace == trace, (
            f'install={install}:裁决在分流前共享段,本轮零段迹')


# ==================== 武装箱弹窗:分流双向行为锁 ====================


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


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_armory_box_dispatch_both_ways(test_context, monkeypatch,
                                       install: bool) -> None:
    """武装箱分流双向:装两端口 → 五段新路径(点 × 关闭 + 置位 + 机械交回);
    标识 miss → observe 门 fail 早退('非武装箱弹窗');关闭钮坐标缺失 →
    fail 缺坐标(共享体分支,新路径同语义);不装端口 → 旧路径零段迹同
    行为。红 = 分流判据破坏或段迹漂移。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    close_pt = SimpleNamespace(x=1108, y=760)
    op, clicks = _make_armory(test_context, monkeypatch,
                              mark_hit=True, close_pt=close_pt)
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == (_FULL_TRACE if install else []), (
        f'段迹形态漂移:{op._lifecycle_trace}')
    assert clicks == [close_pt] and op._click_pending is True, (
        '点 × 恰一次 + pending 置位')
    assert not rs.is_success and '点 × 已发' in (rs.status or ''), (
        f'机械交回 round_retry(保形):{rs!r}')
    # 标识 miss:门 fail 早退
    op_f, clicks_f = _make_armory(test_context, monkeypatch,
                                  mark_hit=False, close_pt=close_pt)
    rs_f = _run_node(test_context, op_f, op_f.handle)
    assert not rs_f.is_success and '非武装箱弹窗' in (rs_f.status or ''), (
        f'标识门早退语义不变:{rs_f!r}')
    assert op_f._lifecycle_trace == (['observe'] if install else []), (
        f'离屏早退段迹:{op_f._lifecycle_trace}')
    assert clicks_f == [], '标识 miss 零动作'
    # 关闭钮坐标缺失(共享体内分支):fail 缺坐标,零点击
    op_n, clicks_n = _make_armory(test_context, monkeypatch,
                                  mark_hit=True, close_pt=None)
    rs_n = _run_node(test_context, op_n, op_n.handle)
    assert not rs_n.is_success and '按钮-关闭' in (rs_n.status or ''), (
        f'缺坐标 fail 语义不变:{rs_n!r}')
    assert clicks_n == [], '缺坐标零点击'
    if install:
        assert op_n._lifecycle_trace == _FULL_TRACE, '缺坐标 fail 出自决策循环'


# ==================== 未达上限弹窗:分流双向行为锁 ====================


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


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_deploy_not_full_dispatch_both_ways(test_context, monkeypatch,
                                            install: bool) -> None:
    """未达上限分流双向:装两端口 → 五段新路径(勾选 + 确认 + 置位 + 机械
    交回);miss 未发 → observe 门 fail('非未达上限弹窗',仅 observe 段迹);
    miss 已发 → 裁决 success(零段迹,两路径共用);不装端口 → 旧路径零段迹
    同行为。红 = 分流判据破坏或确认链语义漂移。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, clicks = _make_deploy_not_full(test_context, monkeypatch, mark_hit=True)
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == (_FULL_TRACE if install else []), (
        f'段迹形态漂移:{op._lifecycle_trace}')
    assert [c[0] for c in clicks] == ['check', 'confirm'], (
        f'勾选 + 确认恰两动作:{clicks!r}')
    assert op._confirm_pending is True, '确认已发 → pending 置位'
    assert not rs.is_success and 'stub-confirm' in (rs.status or ''), (
        'emit_overlay_confirm 机械交回(保形)')
    # miss 未发:门 fail 早退
    op_f, clicks_f = _make_deploy_not_full(test_context, monkeypatch,
                                           mark_hit=False)
    rs_f = _run_node(test_context, op_f, op_f.handle)
    assert not rs_f.is_success and '非未达上限弹窗' in (rs_f.status or ''), (
        f'标识门早退语义不变:{rs_f!r}')
    assert op_f._lifecycle_trace == (['observe'] if install else []), (
        f'离屏早退段迹:{op_f._lifecycle_trace}')
    assert clicks_f == [], 'miss 未发零动作'
    # miss 已发:重入裁决 success(分流前共享段,零段迹两路径同形)
    op_r, clicks_r = _make_deploy_not_full(test_context, monkeypatch,
                                           mark_hit=False)
    op_r._confirm_pending = True
    rs_r = _run_node(test_context, op_r, op_r.handle)
    assert rs_r.is_success and '未达上限弹窗已关(重入观察裁决)' in (rs_r.status or ''), (
        f'重入裁决 success 交回:{rs_r!r}')
    assert op_r._confirm_pending is False, '裁决出口清旗标'
    assert clicks_r == [] and op_r._lifecycle_trace == [], (
        '裁决轮零动作零段迹(裁决留守分流前共享段)')


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


# ==================== 位面情报采集:薄转录 + 双节点保留 ====================


def test_plane_intel_thin_transcription_single_body(test_context,
                                                    monkeypatch) -> None:
    """薄转录锁(总纲契约 2,收尾屏详设 §5):①observe 直通(无门无早退,
    场景门不前移);②决策循环消费 ``_collect_cycle`` 单一共享体(新旧路径
    同一份,禁第二套转录);③新路径成功轮 = 五段迹 + 采集完 success(三位
    面齐桩态);④旧路径同结果零段迹。红 = 体被转录成第二份或直通被拆门。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel as pim,
    )
    obs_src = inspect.getsource(pim.CwScreenPlaneIntel.lifecycle_observe)
    assert 'round_fail' not in obs_src and 'round_retry' not in obs_src, (
        '薄转录 observe 直通:场景门不得前移进观察段(收尾屏详设 §5)')
    dc_src = inspect.getsource(
        pim.CwScreenPlaneIntel.lifecycle_decision_cycle)
    assert '_collect_cycle' in dc_src, '决策循环须消费共享采集体(零转录)'
    collect_src = inspect.getsource(pim.CwScreenPlaneIntel.collect)
    assert collect_src.count('return self._collect_cycle()') == 1, (
        'collect 节点 = 分流 + 委托(体唯一住 _collect_cycle,禁双份)')
    for install in (True, False):
        if install:
            install_dispatch_stub_ports(monkeypatch)
        else:
            _uninstall_ports(monkeypatch)
        op = pim.CwScreenPlaneIntel(test_context)
        op._cur_plane = 3   # 三位面已采桩态(体早退分支:round_success 采集完)
        op._prep_plane = 2   # 会话位面真值桩(免顶栏 OCR 路径)
        monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
        monkeypatch.setattr(op, 'round_by_find_area',
                            lambda scr, s, a, **k: _Area(True))   # 已在位面详情
        rs = _run_node(test_context, op, op.collect)
        assert rs.is_success and '三位面采集完' in (rs.status or ''), (
            f'install={install}:采集完 success:{rs!r}')
        assert op._lifecycle_trace == (_FULL_TRACE if install else []), (
            f'install={install}:段迹:{op._lifecycle_trace}')


def test_plane_intel_dual_node_graph_edge_preserved(test_context) -> None:
    """双节点图边保留(收尾屏详设关键取舍 2):「采集 → 关闭并回写」显式
    node_from 边在位(首跑教训:无显式边时采集 success 被当 op 终点,关闭
    节点漏跑,画面留在位面详情)。红 = 迁移顺手并节点复活该事故形态。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel as pim,
    )
    mod_src = inspect.getsource(pim)
    assert "@node_from(from_name='采集')" in mod_src, (
        '显式 node_from 边声明缺失(关闭节点漏跑事故防线)')
    op = pim.CwScreenPlaneIntel(test_context)
    op._init_network()   # 显式建图(框架在 execute 前调;测试内直调取边登记面)
    edges = op._node_edges_map.get('采集', [])
    assert any(e.node_to.cn == '关闭并回写' for e in edges), (
        f'采集→关闭并回写 边未在节点图登记:{op._node_edges_map!r}')


# ==================== 收口锁(cw_screen/ 目录全量)====================


def _cw_screen_pkg_dir() -> Path:
    from sr_od.application.currency_war.operations import cw_screen as pkg
    return Path(pkg.__file__).parent


def _ast_base_names(cls_node: ast.ClassDef) -> list[str]:
    """类声明的基类名(Name/Attribute 尾名;AST 静态面)。"""
    names: list[str] = []
    for b in cls_node.bases:
        if isinstance(b, ast.Name):
            names.append(b.id)
        elif isinstance(b, ast.Attribute):
            names.append(b.attr)
    return names


def test_closure_all_cw_screen_ops_inherit_base() -> None:
    """收口锁(landing 阶段三判据;B4 判据第 1 条的 cw_screen/ 目录达成
    凭据):cw_screen 全目录顶层类,凡 op 祖链达 SrOperation 者必达
    CwScreenOpBase(AST 全目录扫描:不靠手点名,遗漏新类自动入锁;运行时
    issubclass 复核补 AST 跨模块基类盲区)。达成声明收窄定谳(design.md
    §2.1-4):cw_op/ 商店系三件直继 SrOperation 不在锁面,挂账归后续批。
    红 = 目录内出现直继 SrOperation 的新画面 op(收口回退)。"""
    root = _cw_screen_pkg_dir()
    class_bases: dict[str, list[str]] = {}
    class_module: dict[str, str] = {}
    for f in sorted(root.glob('*.py')):
        tree = ast.parse(f.read_text(encoding='utf-8'))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                assert node.name not in class_bases, (
                    f'cw_screen 顶层类名冲突:{node.name}')
                class_bases[node.name] = _ast_base_names(node)
                class_module[node.name] = f.stem

    def reaches(cls_name: str, target: str, seen: set[str] | None = None) -> bool:
        """cls_name 的基类闭包(经目录内定义的类上溯)是否含 target;
        cls_name 即 target = 边界本体,平凡成立。"""
        if cls_name == target:
            return True
        if seen is None:
            seen = set()
        if cls_name in seen:
            return False
        seen.add(cls_name)
        for base in class_bases.get(cls_name, ()):
            if base == target:
                return True
            if base in class_bases and reaches(base, target, seen):
                return True
        return False

    assert 'CwScreenOpBase' in class_bases, '基类不在 cw_screen 目录(锁面前提)'
    for name in class_bases:
        if reaches(name, 'SrOperation'):
            assert reaches(name, 'CwScreenOpBase'), (
                f'收口锁失守:cw_screen/{class_module[name]}.py 顶层类 {name} '
                f'直继 SrOperation(未迁 CwScreenOpBase)')
    # 运行时复核(AST 跨模块基类的盲区补面):逐顶层类真 issubclass。
    for name, mod_stem in class_module.items():
        mod = importlib.import_module(
            f'sr_od.application.currency_war.operations.cw_screen.{mod_stem}')
        cls = getattr(mod, name)
        if isinstance(cls, type) and issubclass(cls, SrOperation):
            assert issubclass(cls, CwScreenOpBase), (
                f'收口锁失守(运行时):{mod_stem}.{cls.__name__} 是 '
                f'SrOperation 后代但非 CwScreenOpBase 后代')
