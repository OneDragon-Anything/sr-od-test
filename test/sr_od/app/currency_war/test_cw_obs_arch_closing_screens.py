"""统一观察架构·收尾五屏迁移锁 + cw_screen/cw_op 收口锁(账本 T-48,余项收口阶段三)。

设计正本 = docs/develop/sr_od/application/currency_war/design/统一观察架构-画面op基类设计.md
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

**写入流对拍 = 本阶段无适用面**(总纲 §2.2-4 如实申报):五屏零 GameState
写端;位面情报采集采集结果经 ``ctx.cw_plane_bosses``/``cw_plane_affixes``
中转(消费接线批挂账,原样)。发射型接线锁/登记语义对拍锁/豁免留守锁亦无
适用屏(全篇 on_outcome = 无登记件,注册表缺席 = 零动作)。

锁的语义(测试纪律 7 自检;出处 = landing 阶段三判据 + 总纲契约 1-6):

- **五 op 结构锁**:五 op 是 CwScreenOpBase 子类 ∧ 节点预算逐屏逐字
  登记归装饰器不随路径变(登记门,总纲契约 1);装配点分流的存在性/
  先后不再源码锁——装两端口走五段段迹、不装端口零段迹的双向行为锁
  在分流判据被删/后置时必红,承重同一事实(纪律 8:实现形状锁禁)。
- **重入裁决×门组合行为锁**(总纲契约 6 行为面):「已发」旗标裁决
  住分流**之前**两路径共享段(位面过渡/武装箱 = 裁决先行式:门命中 +
  pending 在位 → 不误判完成、失败轮旗标不复活;未达上限 = miss 分支内
  式:门命中 + pending 在位 → 裁决不触发、确认重发)——两屏位序差异的
  行为观测点 = 门命中+旗标在位时旗标清否,由组合行为锁承重(收尾屏
  详设 §1-§3)。
- **新路径行为锁**(§9.1-F2 主门 (a) 本阶段行,逐屏适用性随批登记:五屏全
  适用):装两端口经节点方法走新路径,段迹形态 + 单轮动作/确认置位行为
  (模板同构 = 五相位屏锁);不装端口 → 旧路径零段迹同行为(旧路径不写
  迹纪律)。
- **薄转录锁**(位面情报采集,总纲契约 2):observe 直通(场景门不前移)+
  决策循环消费 ``_collect_cycle`` 单一共享体(新旧路径同一份,禁第二套
  转录)+ 双节点图边(采集→关闭并回写)保留(收尾屏详设关键取舍 2)。
- **收口锁**(landing 阶段三判据;B4 判据第 1 条达成凭据):cw_screen/ 与
  cw_op/ 两目录顶层类凡 op 祖链达 SrOperation 者必为 CwScreenOpBase 后代
  (AST 全目录扫描 + 运行时 issubclass 复核双面;豁免登记门 = 非画面
  动作 op 直继 SrOperation 逐名注缘由,未登记新名即红)。商店系三件
  (CwOpBuyCards/CwOpOpenShop/CwOpCloseShop)已随 T-45 收编挂基类
  (结构/行为锁 = test_cw_obs_arch_shop_ops.py),原「三件直继、挂账归
  后续批」的收窄声明随之失效。

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
from test.sr_od.app.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.app.currency_war._cw_helpers import (
    install_dispatch_stub_ports,
)
from test.sr_od.app.currency_war._cw_helpers import (
    run_node as _run_node,
)
from test.sr_od.app.currency_war._cw_helpers import (
    uninstall_ports as _uninstall_ports,
)

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


def test_closing_ops_node_budget_gate() -> None:
    """五 op 结构锁②(登记门):节点预算归装饰器、逐屏逐字登记
    (总纲契约 1:预算不随路径变)。红时该登记的是「哪屏预算为何改」
    ——登记门形态,照常跟绿;装配点分流的存在性/先后不再源码锁:
    装两端口走五段段迹、不装走旧路径零段迹的双向行为锁(下方各屏)
    在分流判据被删/后置时必红,承重同一事实。"""
    _BUDGETS = {
        'cw_screen_plane_transition': 'node_max_retry_times=8',
        'cw_screen_armory_box': 'node_max_retry_times=8',
        'cw_screen_deploy_not_full': 'node_max_retry_times=10',
        'cw_screen_wait_one_one': "name='等待1-1', is_start_node=True)",
        'cw_screen_plane_intel': 'node_max_retry_times=60',
    }
    for mod_name, cls_name, _node_name in _CLOSING_OPS:
        cls = getattr(_closing_module(mod_name), cls_name)
        assert _BUDGETS[mod_name] in inspect.getsource(cls), (
            f'{cls_name}: 节点预算漂移(预算归装饰器不随路径变,总纲契约 1)')


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_reentry_arbitration_flag_gate_combination(test_context, monkeypatch,
                                                   install: bool) -> None:
    """重入裁决×门组合行为锁(总纲契约 6 的行为面;替代原 .index() 位序
    源码锁——纪律 8 位序锁禁令。「裁决先行式 vs miss 分支内式」两屏差异
    的行为观测点 = 门命中 + 旗标在位时裁决是否消费旗标):
    - 位面过渡/武装箱(裁决先行式):门命中 + pending 在位 → 裁决不误判
      完成(门在 = 动作未落地,重点一次机械交回);推进体缺坐标的失败轮
      旗标保持已消费态不复活(裁决住分流前共享段——若被移进门后/miss
      分支内,此轮旗标残留 True,断言红);
    - 未达上限(miss 分支内式):门命中 + pending 在位 → 裁决不触发,
      勾选+确认重发、旗标经确认体重置(弹窗仍在 = 重发非完成)。
    等待1-1/位面情报采集无裁决旗标,其「分流在首行」语义由双向行为锁段迹
    承重:分流判据被移到锚判定/采集体委托之后时,装端口轮段迹偏离五段/仅
    observe 形态即红(下方各屏行为锁)。
    红 = 裁决出口语义漂移(门命中误判完成 / 失败轮旗标复活)。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    # 位面过渡:门命中 + pending 在位 → 重点一轮(不误判完成)
    blank = SimpleNamespace(x=960, y=540)
    op, clicks = _make_plane_transition(test_context, monkeypatch,
                                        prompt_hit=True, blank=blank)
    op._click_pending = True
    rs = _run_node(test_context, op, op.handle)
    assert not rs.is_success and '点空白已发' in (rs.status or ''), (
        f'install={install}:提示在 = 点击未落地,重点非完成:{rs!r}')
    assert clicks == [blank] and op._click_pending is True, (
        f'install={install}:裁决不误清旗标,重点恰一次')
    assert op._lifecycle_trace == (_FULL_TRACE if install else []), (
        f'install={install}:段迹:{op._lifecycle_trace}')
    # 位面过渡失败轮:裁决已消费旗标 → 缺坐标 fail 轮旗标不复活
    op_f, _clicks_f = _make_plane_transition(test_context, monkeypatch,
                                             prompt_hit=True, blank=None)
    op_f._click_pending = True
    rs_f = _run_node(test_context, op_f, op_f.handle)
    assert not rs_f.is_success \
        and '缺「区域-空白点击」建档' in (rs_f.status or ''), (
        f'install={install}:失败轮入口:{rs_f!r}')
    assert op_f._click_pending is False, (
        f'install={install}:裁决先行消费旗标,失败轮不残留待裁决旗标')
    # 武装箱:门命中 + pending 在位 → 重点一轮(不误判完成)
    close_pt = SimpleNamespace(x=1108, y=760)
    op_a, clicks_a = _make_armory(test_context, monkeypatch,
                                  mark_hit=True, close_pt=close_pt)
    op_a._click_pending = True
    rs_a = _run_node(test_context, op_a, op_a.handle)
    assert not rs_a.is_success and '点 × 已发' in (rs_a.status or ''), (
        f'install={install}:标识在 = 点击未落地,重点非完成:{rs_a!r}')
    assert clicks_a == [close_pt] and op_a._click_pending is True, (
        f'install={install}:裁决不误清旗标,重点恰一次')
    # 未达上限:门命中 + pending 在位 → 裁决不触发,确认链重发
    op_d, clicks_d = _make_deploy_not_full(test_context, monkeypatch,
                                           mark_hit=True)
    op_d._confirm_pending = True
    rs_d = _run_node(test_context, op_d, op_d.handle)
    assert not rs_d.is_success and 'stub-confirm' in (rs_d.status or ''), (
        f'install={install}:门命中 = 裁决不触发,确认重发机械交回:{rs_d!r}')
    assert [c[0] for c in clicks_d] == ['check', 'confirm'], (
        f'install={install}:勾选+确认重发恰两动作')
    assert op_d._confirm_pending is True, (
        f'install={install}:miss 分支内裁决未触发,旗标经确认体重置')


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
    # 边的登记面以运行时节点图为准(下方真图查询);不另做装饰器源码
    # 字面扫描——合法改写登记写法即假红,纪律 8(运行时锁承重同事实)。
    op = pim.CwScreenPlaneIntel(test_context)
    op._init_network()   # 显式建图(框架在 execute 前调;测试内直调取边登记面)
    edges = op._node_edges_map.get('采集', [])
    assert any(e.node_to.cn == '关闭并回写' for e in edges), (
        f'采集→关闭并回写 边未在节点图登记:{op._node_edges_map!r}')


# ==================== 收口锁(cw_screen/ + cw_op/ 目录全量)====================


def _closure_scan_targets() -> list[tuple[str, Path]]:
    """收口锁扫描目录(画面 op 收编辖域):(包前缀, 目录路径)对。"""
    from sr_od.application.currency_war.operations import cw_op, cw_screen
    return [
        ('sr_od.application.currency_war.operations.cw_screen',
         Path(cw_screen.__file__).parent),
        ('sr_od.application.currency_war.operations.cw_op',
         Path(cw_op.__file__).parent),
    ]


#: 动作 op 豁免登记(登记门):直继 SrOperation 的**非画面** op 逐名
#: 注缘由——它们无画面生命周期,不属 CwScreenOpBase 收编辖域。登记
#: 双向:未登记的新直继 op = 红(强制「收编 or 豁免登记」决策);
#: 登记名对应的类消失 = 红(清死登记)。
_CLOSURE_EXEMPT: dict[str, str] = {
    'CwOpTools': '工具箱编排动作 op,非画面 op',
    'CwOpDeploy': '出战编排动作 op,非画面 op',
    'CwOpEquipAll': '装备全穿编排动作 op,非画面 op',
    'CwOpSellOffTarget': '卸下目标编排动作 op,非画面 op',
}


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
    """收口锁(landing 阶段三判据;B4 判据第 1 条达成凭据):cw_screen/
    与 cw_op/ 两目录顶层类,凡 op 祖链达 SrOperation 者必达 CwScreenOpBase
    或入豁免登记(AST 全目录扫描:不靠手点名,遗漏新类自动入锁;运行时
    issubclass 复核补 AST 跨模块基类盲区)。商店系三件已随 T-45 收编挂
    基类(其结构/行为锁 = test_cw_obs_arch_shop_ops.py),原「三件直继
    不在锁面、挂账归后续批」的收窄声明随之失效,锁面扩至 cw_op/。
    红 = 扫描目录内出现直继 SrOperation 且未豁免登记的 op(收口回退),
    或豁免登记名对应的类已消失(死登记)。"""
    class_bases: dict[str, list[str]] = {}
    class_module: dict[str, str] = {}
    for pkg_prefix, root in _closure_scan_targets():
        for f in sorted(root.glob('*.py')):
            tree = ast.parse(f.read_text(encoding='utf-8'))
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    assert node.name not in class_bases, (
                        f'收口目录顶层类名冲突:{node.name}')
                    class_bases[node.name] = _ast_base_names(node)
                    class_module[node.name] = f'{pkg_prefix}.{f.stem}'

    def reaches(cls_name: str, target: str, seen: set[str] | None = None) -> bool:
        """cls_name 的基类闭包(经扫描目录内定义的类上溯)是否含 target;
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

    assert 'CwScreenOpBase' in class_bases, '基类不在扫描目录(锁面前提)'
    for name in class_bases:
        if reaches(name, 'SrOperation'):
            assert reaches(name, 'CwScreenOpBase') or name in _CLOSURE_EXEMPT, (
                f'收口锁失守:{class_module[name]} 顶层类 {name} 直继 '
                f'SrOperation(画面 op 必挂 CwScreenOpBase;确属非画面动作 '
                f'op 则逐名登记 _CLOSURE_EXEMPT 并注缘由)')
    # 死登记清查(登记门双向):豁免名必须仍对应扫描面里的真实顶层类。
    for exempt in _CLOSURE_EXEMPT:
        assert exempt in class_bases, (
            f'收口豁免死登记:{exempt} 不在扫描目录顶层类中(类已删/更名,'
            f'同步清登记项)')
    # 运行时复核(AST 跨模块基类的盲区补面):逐顶层类真 issubclass。
    for name, mod_path in class_module.items():
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, name)
        if isinstance(cls, type) and issubclass(cls, SrOperation):
            assert issubclass(cls, CwScreenOpBase) or name in _CLOSURE_EXEMPT, (
                f'收口锁失守(运行时):{mod_path}.{cls.__name__} 是 '
                f'SrOperation 后代但非 CwScreenOpBase 后代且未豁免登记')
