"""统一观察架构·推进型基类收编锁(账本 T-47,余项收口阶段二)。

设计正本 = docs/develop/sr_od/application/currency_war/design/统一观察架构-画面op基类设计.md
(下称「架构设计」);收编粒度/变体五段依据 = changes/2026-09-11-
unified-observation/details/推进型基类收编详设.md。辖域:CwProgression
ScreenOp 改挂 CwScreenOpBase 作只读/导航变体(B4 选项②,ADR-0584 空决策
合同逐字保留),11 子类零改动随之收敛。

**F11 sim 腿不适用例外清单(推进型 11 屏,总纲 §2.2-3 随批登记)**:
sim 无对应画面段(空决策合同零策略问询、零 BoardState 写端),等价
判据主承重 = ADR-0584 在册行为锁(实机腿,test_cw_progression_ops.py
原样保绿,不装端口经 execute() 走旧路径)+ 本文件变体结构锁与新路径
语义锁;**写入流对拍 = 本阶段无适用面**(ADR-0584 空决策合同零写端,
总纲 §2.2-4 如实申报)。

锁的语义(测试纪律 7 自检;出处 = landing 阶段二判据 + 总纲契约 1-5):

- **变体结构锁**:CwProgressionScreenOp 是 CwScreenOpBase 子类 ∧ 11 子类
  AST 全量为其后代 ∧ 节点预算 = 2 归装饰器不随路径变(登记门,ADR-0584)
  ∧ 变体五段钩子在(observe 早退语义 + decide 空申报 = 本屏无策略消费
  合同声明)。装配点分流的存在性/「先于骨架观察」不再源码锁(纪律 8
  形状锁禁):装端口走变体五段的行为锁承重分流存在性,重入往返锁的
  入口单读计数承重「分流在 handle 顶部」(后置 = 每轮双读即红)。
- **新路径语义锁**(§9.1-F2 主门 (a) 变体行):装两端口经 handle() 走
  变体五段,ADR-0584 轮次语义(误分发 fail / 推进 retry / 重入 success
  清旗标 / act 未落地 fail / 免锚发出即 success)逐条保形 + 段迹形态;
  不装端口 → 旧路径同形零段迹(旧路径不写迹纪律)。
- **on_outcome 无登记件**:基类模块零 register_outcome_hook(注册表缺席
  = 零动作,推进型无 §6.4 收编面)。

驱动方式 = 真类实例(生产构造走 __init__)+ entry_ok/progress_once 实例
级桩;装配点分流桩端口 = ``_cw_helpers.install_dispatch_stub_ports``
单一源;不装端口 = 旧路径代表驱动(并存窗旧路径锁专用)。
"""
from __future__ import annotations

import ast
import importlib
import inspect

import pytest

from sr_od.application.currency_war.operations.cw_screen import (
    _progression_base as pb,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_op_base import (
    CwScreenOpBase,
)
from sr_od.context.sr_context import SrContext
from sr_od.operations.sr_operation import SrOperation
from test.sr_od.app.currency_war._cw_helpers import (
    install_dispatch_stub_ports,
)
from test.sr_od.app.currency_war._cw_helpers import (
    run_node as _run_node,
)
from test.sr_od.app.currency_war._cw_helpers import (
    uninstall_ports as _uninstall_ports,
)

#: 11 子类(详设辖域清单;模块名 → 画面 op 类名)
_SUBCLASS_MODULES = {
    'cw_screen_aha_equip_pick': 'CwScreenAhaEquipPick',
    'cw_screen_consumable_overlay': 'CwScreenConsumableOverlay',
    'cw_screen_emblem_detail_popup': 'CwScreenEmblemDetailPopup',
    'cw_screen_interrupt_dialog': 'CwScreenInterruptDialog',
    'cw_screen_item_detail_popup': 'CwScreenItemDetailPopup',
    'cw_screen_next_button': 'CwScreenNextButton',
    'cw_screen_plane_detail': 'CwScreenPlaneDetail',
    'cw_screen_prep_locked_return': 'CwScreenPrepLockedReturn',
    'cw_screen_refresh_odds_popup': 'CwScreenRefreshOddsPopup',
    'cw_screen_role_detail_overlay': 'CwScreenRoleDetailOverlay',
    'cw_screen_shop_card_detail': 'CwScreenShopCardDetailPopup',
}

_FULL_TRACE = ['observe', 'reconcile', 'decide', 'act', 'on_outcome']


def _prog_module(name: str):
    """按名取 cw_screen 子模块(importlib;11 子类清单遍历用)。"""
    return importlib.import_module(
        f'sr_od.application.currency_war.operations.cw_screen.{name}')


def _make_plane_detail(test_context, monkeypatch: pytest.MonkeyPatch, *,
                       entry_hit: bool, progress_ok: bool = True):
    """位面详情真类装配(entry_ok/progress_once 实例级桩;生产构造走
    __init__ = 注册表/适配器位在位)。``entry`` dict 供重入场景翻转;
    ``entry['reads']`` = 入口读计数(单轮单读行为锁载体)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_detail as pdm,
    )

    op = pdm.CwScreenPlaneDetail(test_context)
    entry = {'hit': entry_hit, 'reads': 0}

    def _entry_ok(screen) -> bool:
        entry['reads'] += 1
        return entry['hit']

    monkeypatch.setattr(op, 'entry_ok', _entry_ok)
    monkeypatch.setattr(op, 'progress_once', lambda: progress_ok)
    return op, entry


class _FreeAnchorOp(pb.CwProgressionScreenOp):
    """免锚即 success 形态最小推进 op(空锚 ∧ 未覆写 entry_ok = 基类
    合同分支的纯形态;现役 11 子类均无此形态,免锚臂由本类承载)。"""

    SCREEN_NAME = ''
    ENTRY_AREA = ''

    def __init__(self, ctx: SrContext):
        pb.CwProgressionScreenOp.__init__(self, ctx, op_name='测试-免锚推进')

    def progress_once(self) -> bool:
        return True


# ==================== 变体结构锁 ====================


def test_progression_variant_inherits_base() -> None:
    """变体结构锁①(landing 阶段二判据 1):CwProgressionScreenOp 改挂
    CwScreenOpBase(SrOperation 仍为祖先,挂链不截断)∧ 11 子类逐名为其
    后代。红 = 迁移回退或子类面漂移。"""
    assert issubclass(pb.CwProgressionScreenOp, CwScreenOpBase), (
        '推进型基类未挂 CwScreenOpBase(变体收编回退)')
    assert issubclass(pb.CwProgressionScreenOp, SrOperation), (
        '挂链截断:CwScreenOpBase 应仍继承 SrOperation')
    for mod_name, cls_name in _SUBCLASS_MODULES.items():
        cls = getattr(_prog_module(mod_name), cls_name)
        assert issubclass(cls, pb.CwProgressionScreenOp), (
            f'{mod_name}.{cls_name} 非推进型基类后代(子类面漂移)')


def test_progression_subclasses_ast_full_coverage() -> None:
    """变体结构锁②(详设 §4「11 子类 AST 全量为其后代」):逐子类模块
    AST 枚举顶层类,全量断言为 CwProgressionScreenOp 后代 ∧ 详设点名类
    在位——不靠手点名遗漏新类。红 = 模块新增非变体顶层类,或点名类
    被移除(子类文件面漂移)。"""
    for mod_name, cls_name in _SUBCLASS_MODULES.items():
        mod = _prog_module(mod_name)
        tree = ast.parse(inspect.getsource(mod))
        top_classes = [n.name for n in tree.body
                       if isinstance(n, ast.ClassDef)]
        assert cls_name in top_classes, (
            f'{mod_name}: 详设点名类 {cls_name} 不在顶层类中(子类面漂移)')
        for name in top_classes:
            cls = getattr(mod, name)
            assert issubclass(cls, pb.CwProgressionScreenOp), (
                f'{mod_name}.{name}: 顶层类非推进型基类后代'
                f'(变体收编面漂移)')


def test_progression_variant_node_budget_gate() -> None:
    """变体结构锁③(登记门):节点预算 = 2 归装饰器不随路径变
    (ADR-0584)。红时该登记的是「推进型预算为何改」。装配点分流的
    存在性/「先于骨架入口观察」不再源码锁(纪律 8 形状锁禁):装端口
    走变体五段的行为锁承重分流存在性;「分流在 handle 顶部」由重入
    往返锁的入口单读计数承重(分流后置 = handle 先读 + observe 再读,
    每轮双读,reads 计数即红)。"""
    src = inspect.getsource(pb.CwProgressionScreenOp.handle)
    assert 'node_max_retry_times=2' in src, '推进节点预算 ≠ 2(ADR-0584)'


def test_progression_variant_hooks_declared() -> None:
    """变体结构锁④(详设 §4「变体五段钩子在」):三钩子均为本类覆写;
    decide 空申报(零策略器问询,ADR-0584)+ on_outcome 无登记件
    (模块零 register_outcome_hook,注册表缺席 = 零动作)。
    observe 早退分支形态/旗标清零写点/段迹标记在位不再源码锁:误分发
    fail、重入 success 清旗标、act 未落地 fail 的双向行为锁(下方)承重
    同一事实(纪律 8:实现形状锁禁);``wait=1`` 轮间等待由框架在返回
    对象之外消费,无行为观测点,随位序锁一并退役。"""
    assert pb.CwProgressionScreenOp.lifecycle_observe \
        is not CwScreenOpBase.lifecycle_observe, 'observe 钩子未覆写'
    assert pb.CwProgressionScreenOp.lifecycle_reconcile \
        is not CwScreenOpBase.lifecycle_reconcile, 'reconcile 空申报未显式'
    assert pb.CwProgressionScreenOp.lifecycle_decision_cycle \
        is not CwScreenOpBase.lifecycle_decision_cycle, '决策循环未覆写'
    dc_src = inspect.getsource(
        pb.CwProgressionScreenOp.lifecycle_decision_cycle)
    assert 'strategy' not in dc_src, (
        'decide 空申报被破坏:决策循环出现策略器问询(ADR-0584 零策略器'
        '问询合同)')
    mod_src = inspect.getsource(pb)
    assert 'register_outcome_hook' not in mod_src, (
        'on_outcome 无登记件被破坏:推进型基类不得登记注册件(§6.4)')


# ==================== 新路径语义锁(变体五段;§9.1-F2 主门 (a) 变体行)====


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_progression_variant_reentry_roundtrip_both_paths(
        test_context, monkeypatch, install: bool) -> None:
    """推进 + 重入裁决往返(ADR-0584 轮次语义主形,两路径同形):入口
    命中 → 推进已发 round_retry(置旗标)→ 重入锚 miss = 已离开本画面
    → round_success 清旗标。装端口走变体五段(首轮恰五段迹,重入轮仅
    observe 段迹——早退后后续段不执行);不装端口走旧路径同形零段迹。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, entry = _make_plane_detail(test_context, monkeypatch, entry_hit=True)

    rs1 = _run_node(test_context, op, op.handle)

    assert not rs1.is_success and '重入观察裁决' in (rs1.status or ''), (
        f'推进已发应机械交回 retry:{rs1!r}')
    assert op._advanced_once is True, '推进已发须置旗标(重入裁决承载)'

    entry['hit'] = False
    rs2 = _run_node(test_context, op, op.handle)

    assert rs2.is_success and '已推进' in (rs2.status or ''), (
        f'重入锚 miss 应 success 交回:{rs2!r}')
    assert op._advanced_once is False, '重入出口须清旗标(ADR-0584)'
    assert entry['reads'] == 2, (
        f'两轮各恰一次入口读(分流在 handle 顶部——后置时每轮 handle 先读'
        f' + observe 再读 = 双读,此处红):{entry["reads"]}')
    expected = (_FULL_TRACE + ['observe']) if install else []
    assert op._lifecycle_trace == expected, (
        f'段迹形态漂移:{op._lifecycle_trace}')


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_progression_variant_misdispatch_fail_both_paths(
        test_context, monkeypatch, install: bool) -> None:
    """首发锚 miss = 误分发 → round_fail 交回外循环重判,两路径同形;
    新路径 = observe 段早退(仅 observe 段迹,零动作零后续段)。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, _entry = _make_plane_detail(test_context, monkeypatch,
                                    entry_hit=False)

    rs = _run_node(test_context, op, op.handle)

    assert not rs.is_success and '入口锚未命中' in (rs.status or ''), (
        f'误分发应 fail 交回:{rs!r}')
    assert op._advanced_once is False, '未推进不得置旗标'
    expected = ['observe'] if install else []
    assert op._lifecycle_trace == expected, (
        f'误分发早退段迹:{op._lifecycle_trace}')


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_progression_variant_act_miss_fail_both_paths(
        test_context, monkeypatch, install: bool) -> None:
    """推进动作未落地(progress_once False)→ round_fail,两路径同形;
    新路径 = 决策循环出口 fail(恰五段迹,旗标不置位)。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, _entry = _make_plane_detail(test_context, monkeypatch,
                                    entry_hit=True, progress_ok=False)

    rs = _run_node(test_context, op, op.handle)

    assert not rs.is_success and '推进动作未落地' in (rs.status or ''), (
        f'act 未落地应 fail:{rs!r}')
    assert op._advanced_once is False, '动作未落地不得置旗标'
    expected = _FULL_TRACE if install else []
    assert op._lifecycle_trace == expected, (
        f'decision cycle 出口段迹:{op._lifecycle_trace}')


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_progression_variant_free_anchor_emit_success(
        test_context, monkeypatch, install: bool) -> None:
    """免锚形态(空锚 ∧ 未覆写 entry_ok = 重入裁决不可达)发出即
    success 交回,两路径同形(ADR-0584 免锚合同臂;现役 11 子类均无此
    形态,由测试本地最小 op 承载)。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op = _FreeAnchorOp(test_context)

    rs = _run_node(test_context, op, op.handle)

    assert rs.is_success and '免锚' in (rs.status or ''), (
        f'免锚发出即 success:{rs!r}')
    assert op._advanced_once is True, '免锚臂亦置旗标(骨架合同)'
    expected = _FULL_TRACE if install else []
    assert op._lifecycle_trace == expected, (
        f'免锚段迹:{op._lifecycle_trace}')
