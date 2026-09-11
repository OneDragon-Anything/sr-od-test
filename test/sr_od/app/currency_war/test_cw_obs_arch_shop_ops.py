"""统一观察架构·商店系三件收编锁(账本 T-45,B4 挂账批)。

设计依据 = changes/2026-09-11-unified-observation/design.md §2.1-4
(attack A-4 挂账行:「点名清单内 cw_op/ 商店系三件直继 SrOperation,
挂账归后续批」——本批即该后续批)+ details/推进型基类收编详设.md
(变体形态先例,T-47 已落)。辖域:CwOpBuyCards / CwOpOpenShop /
CwOpCloseShop 三件直挂 CwScreenOpBase,start 节点方法顶部装配点分流,
生产行为零变化(缺省 None = 生产直连旧路径,原序列逐位保留)。

**F11 sim 腿不适用例外清单(随批登记,总纲 §2.2-3)**:sim 无对应画面段
(三件为备战/商店子相位的原子动作单元,非独立画面段;open/close 幂等
原子动作零策略消费、零 BoardState 新写端——回执写端 = kernel 口既有,
两路径同一份),等价判据主承重 = 在册行为锁(test_cw_state_action_
receipts.py 回执三出口/test_cw_op_boundary、test_cw_launch_arbitrage
模块缝替身,全走旧路径函数原样保绿)+ 本文件变体结构锁与新路径语义锁;
**写入流对拍 = 本批无适用面**(零新写端,总纲 §2.2-4 如实申报)。

三件的目标形态(总纲 §2.1-2 规则逐件定谳,申报面 = 各类 docstring):

- CwOpOpenShop/CwOpCloseShop:只读/导航变体(B4 选项②;幂等原子动作
  零策略消费,decide 空申报 = 合同声明)。observe = 幂等入口观察裁决
  (纯读早退,幂等出口构造与旧路径共享单一构造),act 及其后 = 整体
  委托旧路径函数(旧体单一共享零第二转录,重入观察裁决出口原位保留);
  无「已发」旗标(收起锚可见与否即全部裁决,首入/重入同义——异于
  总纲契约 6「已发旗标」定谳辖域,同推进型变体理由)。
- CwOpBuyCards:**旧体委托**变体(直迁全五段的过渡替代):入口观察/
  播种对账/单动作决策循环全住 run_buy_waves 段循环内,不拆段循环
  (拆段 = 「刷新终结交回重进」物理载体与节点预算语义变更,总纲契约 5
  红线);策略消费在委托体内 decide_shop_action,**不申报**空决策合同。

锁的语义(测试纪律 7 自检;出处 = 本批报告对照表 + 总纲契约 1/5):

- **结构锁**:三件是 CwScreenOpBase 子类(SrOperation 祖链不截断)∧
  节点预算保持缺省(归装饰器、不随路径变——登记门)∧ 变体五段钩子
  覆写(open/close observe 早退语义 + reconcile/decide 空申报;buy 空申报
  observe/reconcile + decision_cycle 消费委托体)∧ on_outcome 无登记件
  (三模块零 register_outcome_hook,注册表缺席 = 零动作)。装配点分流的
  存在性/「先于旧路径调用」不再源码锁(纪律 8 形状锁禁):装端口恰一次
  点击(分流后置 = 装端口双击即红)、幂等早退零点击、buy 恰一次委托的
  行为锁承重同一事实。
- **新路径语义锁**:装两端口经节点方法走变体五段,轮次语义与旧路径
  逐条同形(open 三出口/.close 两出口/buy 委托透传)+ 段迹形态
  (全五段/observe 早退仅一段);不装端口 → 旧路径同形零段迹
  (旧路径不写迹纪律)。

驱动方式 = 真类实例(生产构造走 __init__,注册表/适配器位在位)+
round_by_*/screenshot/park_cursor 实例级桩 + run_buy_waves 模块缝替身
(test_cw_op_boundary 同缝位);装配点分流桩端口 =
``_cw_helpers.install_dispatch_stub_ports`` 单一源;不装端口 = 旧路径
代表驱动(并存窗旧路径锁专用)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.operations.cw_screen.cw_screen_op_base import (
    CwScreenOpBase,
)
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

#: 三件清单(模块名 → 类名 → start 节点方法名 → 旧路径被委托体)
_SHOP_OPS = {
    'cw_op_open_shop': ('CwOpOpenShop', 'open', 'open_shop(self)'),
    'cw_op_close_shop': ('CwOpCloseShop', 'close', 'close_shop(self)'),
    'cw_op_buy_cards': ('CwOpBuyCards', 'buy', 'return self._buy_round()'),
}

_FULL_TRACE = ['observe', 'reconcile', 'decide', 'act', 'on_outcome']

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)


def _shop_module(name: str):
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards,
        cw_op_close_shop,
        cw_op_open_shop,
    )
    return {
        'cw_op_open_shop': cw_op_open_shop,
        'cw_op_close_shop': cw_op_close_shop,
        'cw_op_buy_cards': cw_op_buy_cards,
    }[name]


def _make_open_shop(test_context, monkeypatch: pytest.MonkeyPatch, *,
                    shop_open: bool, click_ok: bool = True):
    """开商店真类装配(round_by_*/screenshot/park_cursor 实例级桩;
    生产构造走 __init__ = 注册表/适配器位在位)。``clicks`` = 发出的
    点击记录(观察纯读零动作 / 装端口恰一次点击的行为锁载体)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_open_shop as m,
    )
    op = m.CwOpOpenShop(test_context)
    monkeypatch.setattr(op, 'screenshot', lambda: _FRAME)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: SimpleNamespace(is_success=shop_open))
    clicks: list = []

    def _click(*a, **k):
        if click_ok:
            clicks.append(1)   # 只计发出的点击(find 未命中 = 未发出)
        return SimpleNamespace(is_success=click_ok)

    monkeypatch.setattr(op, 'round_by_find_and_click_area', _click)
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    return op, clicks


def _make_close_shop(test_context, monkeypatch: pytest.MonkeyPatch, *,
                     shop_open: bool):
    """关商店真类装配(桩面同开商店;融合判定点击 is_success = shop_open)。
    ``clicks`` = 发出的点击记录(行为锁载体,同开商店)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_close_shop as m,
    )
    op = m.CwOpCloseShop(test_context)
    monkeypatch.setattr(op, 'screenshot', lambda: _FRAME)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: SimpleNamespace(is_success=shop_open))
    clicks: list = []

    def _click(*a, **k):
        if shop_open:
            clicks.append(1)   # 只计发出的点击(find 未命中 = 未发出)
        return SimpleNamespace(is_success=shop_open)

    monkeypatch.setattr(op, 'round_by_find_and_click_area', _click)
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    return op, clicks


def _make_buy_cards(test_context, monkeypatch: pytest.MonkeyPatch, *,
                    waves_fail: bool = False):
    """买牌真类装配(run_buy_waves 模块缝替身,test_cw_op_boundary 同缝位;
    委托透传 = 计数 + 轮次结果原样,循环内部语义归其在册锁自辖)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards as m,
    )
    op = m.CwOpBuyCards(test_context)
    calls = {'waves': 0}

    def _fake_waves(op_obj, match, hp_value, hp_readable, hp_trusted):
        calls['waves'] += 1
        if waves_fail:
            rr = SimpleNamespace(is_success=False, status='FAIL')
            return rr, None
        outcome = SimpleNamespace(total_buy=1, total_level=0,
                                  total_refresh=0, total_sell=0)
        return None, outcome

    monkeypatch.setattr(m, 'run_buy_waves', _fake_waves)
    return op, calls


# ==================== 结构锁 ====================


def test_shop_ops_inherit_base() -> None:
    """结构锁①(B4 判据第 1 条本批达成面):三件均为 CwScreenOpBase
    后代(SrOperation 祖链不截断)。红 = 收编回退。"""
    for mod_name, (cls_name, _node, _old) in _SHOP_OPS.items():
        cls = getattr(_shop_module(mod_name), cls_name)
        assert issubclass(cls, CwScreenOpBase), (
            f'{mod_name}.{cls_name} 未挂 CwScreenOpBase(B4 挂账收编回退)')
        assert issubclass(cls, SrOperation), (
            f'{mod_name}.{cls_name} 挂链截断:CwScreenOpBase 应仍继承'
            f' SrOperation')


@pytest.mark.parametrize('mod_name', sorted(_SHOP_OPS))
def test_shop_op_node_budget_default_gate(mod_name: str) -> None:
    """结构锁②(登记门):节点预算保持缺省——预算归装饰器、不随收编变
    (总纲契约 1/5 红线)。红时该登记的是「该 op 预算为何改」。
    分流表达式/旧路径保留位的存在性与先后不再源码锁(纪律 8 形状锁禁):
    装端口恰一次点击、不装端口同形零段迹的双向行为锁在分流被删/后置时
    必红(下方语义锁 + clicks 计数承重同一事实)。"""
    mod = _shop_module(mod_name)
    cls_name, node_name, _old_call = _SHOP_OPS[mod_name]
    src = inspect.getsource(getattr(mod, cls_name).__dict__[node_name])
    assert 'node_max_retry_times' not in src, (
        f'{cls_name}.{node_name} 节点预算被显式改动(缺省预算不随收编变,'
        f'契约 5 红线)')


def test_open_close_variant_hooks_declared() -> None:
    """结构锁③(open/close 只读/导航变体):observe 早退语义(幂等出口
    构造共享单一构造)∧ reconcile/decide 空申报显式覆写 ∧ act 整体委托
    旧路径函数(零第二转录)∧ 零策略器问询(B4 选项②空决策合同声明)。
    段迹标记在位/observe 纯读零动作不再源码锁:装端口段迹恰五段/observe
    早退仅一段的行为锁 + 幂等早退 clicks == [] 行为锁承重同一事实
    (纪律 8:实现形状锁禁)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_close_shop as cm,
    )
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_open_shop as om,
    )
    for mod, cls_name, old_fn, exit_helper in (
            (om, 'CwOpOpenShop', 'open_shop', '_open_shop_already_open'),
            (cm, 'CwOpCloseShop', 'close_shop', '_close_shop_already_closed')):
        cls = getattr(mod, cls_name)
        assert cls.lifecycle_observe is not CwScreenOpBase.lifecycle_observe, (
            f'{cls_name} observe 钩子未覆写')
        assert cls.lifecycle_reconcile \
            is not CwScreenOpBase.lifecycle_reconcile, (
            f'{cls_name} reconcile 空申报未显式')
        obs_src = inspect.getsource(cls.lifecycle_observe)
        assert exit_helper in obs_src, (
            f'{cls_name} observe 幂等出口未共享单一构造({exit_helper})')
        dc_src = inspect.getsource(cls.lifecycle_decision_cycle)
        assert f'{old_fn}(self)' in dc_src, (
            f'{cls_name} act 半未整体委托 {old_fn}(旧体单一共享)')
        assert 'strategy' not in dc_src, (
            f'{cls_name} decide 空申报被破坏:决策循环出现策略器问询'
            f'(B4 选项②零策略消费合同)')
    # 幂等出口构造单一性:旧路径臂与变体 observe 共用同一构造函数。
    assert 'return _open_shop_already_open(op)' in inspect.getsource(om), (
        '开商店旧路径首臂未接共享构造(第二份出口构造漂移)')
    assert 'return _close_shop_already_closed(op)' in inspect.getsource(cm), (
        '关商店旧路径 miss 臂未接共享构造(第二份出口构造漂移)')


def test_buy_cards_delegate_variant_declared() -> None:
    """结构锁③(buy 旧体委托变体):observe/reconcile 空申报(不拆段
    循环,总纲契约 5)∧ decision_cycle 消费委托体单一实现 ∧ 委托体被
    旧路径与变体共享(buy 旧路径保留位 = 同一方法)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards as bm,
    )
    cls = bm.CwOpBuyCards
    assert cls.lifecycle_observe is not CwScreenOpBase.lifecycle_observe, (
        'observe 空申报未显式(基类为 NotImplementedError,不覆写即炸)')
    assert cls.lifecycle_reconcile is not CwScreenOpBase.lifecycle_reconcile, (
        'reconcile 空申报未显式')
    dc_src = inspect.getsource(cls.lifecycle_decision_cycle)
    assert '_buy_round' in dc_src, '决策循环未消费委托体单一实现'
    assert 'match.strategy' not in dc_src, (
        '决策循环段不得内联策略问询(策略消费住委托体内,旧体委托申报)')
    buy_src = inspect.getsource(bm.CwOpBuyCards.buy)
    assert buy_src.count('_buy_round') == 1 and 'run_buy_waves' not in buy_src, (
        'buy 旧路径保留位须委托 _buy_round(两路径共享单一实现,禁第二份)')


@pytest.mark.parametrize('mod_name', sorted(_SHOP_OPS))
def test_shop_ops_no_outcome_registry(mod_name: str) -> None:
    """结构锁④(on_outcome 无登记件):三模块零 register_outcome_hook
    (注册表缺席 = 零动作;商店系无 §6.4 收编面,回执写端 = kernel 口
    既有且两路径同一份)。"""
    mod_src = inspect.getsource(_shop_module(mod_name))
    assert 'register_outcome_hook' not in mod_src, (
        f'{mod_name} 出现登记件(§6.4:新登记件先改 EMIT_TRIGGERED_DECLARED'
        f' 申报面再登记,禁静默新增)')


# ==================== 新路径语义锁(§9.1-F2 主门 (a) 本批行)====


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_open_shop_already_open_early_exit(
        test_context, monkeypatch, install: bool) -> None:
    """开商店幂等出口(首臂/observe 早退同形,两路径):店已开 →
    success('商店已开')。新路径 = observe 段早退(仅 observe 段迹,
    零动作);旧路径 = 同出口零段迹。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, clicks = _make_open_shop(test_context, monkeypatch, shop_open=True)

    rs = _run_node(test_context, op, op.open)

    assert rs.is_success and '商店已开' in (rs.status or ''), (
        f'幂等已开应 success 交回:{rs!r}')
    assert clicks == [], '幂等早退零点击(observe 纯读,旧路径亦零执行)'
    expected = ['observe'] if install else []
    assert op._lifecycle_trace == expected, f'段迹漂移:{op._lifecycle_trace}'


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_open_shop_click_issued_reentry_roundtrip(
        test_context, monkeypatch, install: bool) -> None:
    """开商店点击已发 → retry(重入观察裁决),两路径同形:店没开 →
    委托体点击已发 round_retry(wait=1);新路径 = 全五段迹。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, clicks = _make_open_shop(test_context, monkeypatch, shop_open=False,
                                 click_ok=True)

    rs = _run_node(test_context, op, op.open)

    assert not rs.is_success and '重入观察裁决' in (rs.status or ''), (
        f'点击已发应机械交回 retry:{rs!r}')
    assert len(clicks) == 1, (
        f'点击恰一次(分流后置/旧路径先执行 = 装端口双击,此处红):{clicks!r}')
    expected = _FULL_TRACE if install else []
    assert op._lifecycle_trace == expected, f'段迹漂移:{op._lifecycle_trace}'


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_open_shop_not_found_fail(
        test_context, monkeypatch, install: bool) -> None:
    """开商店入口观察失败(动作没发出)→ fail 如实交回,两路径同形。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, clicks = _make_open_shop(test_context, monkeypatch, shop_open=False,
                                 click_ok=False)

    rs = _run_node(test_context, op, op.open)

    assert not rs.is_success and '找不到商店/收起按钮' in (rs.status or ''), (
        f'入口观察失败应 fail 交回:{rs!r}')
    assert clicks == [], '入口观察失败 = 动作没发出,零点击'
    expected = _FULL_TRACE if install else []
    assert op._lifecycle_trace == expected, f'段迹漂移:{op._lifecycle_trace}'


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_close_shop_already_closed_early_exit(
        test_context, monkeypatch, install: bool) -> None:
    """关商店幂等出口(miss 臂/observe 早退同形,两路径):收起不在 =
    店已关 → success('商店已关(收起不在,幂等入口观察)')。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, clicks = _make_close_shop(test_context, monkeypatch, shop_open=False)

    rs = _run_node(test_context, op, op.close)

    assert rs.is_success and '商店已关' in (rs.status or ''), (
        f'幂等已关应 success 交回:{rs!r}')
    assert clicks == [], '幂等早退零点击(observe 纯读,旧路径亦零执行)'
    expected = ['observe'] if install else []
    assert op._lifecycle_trace == expected, f'段迹漂移:{op._lifecycle_trace}'


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_close_shop_click_issued_reentry_roundtrip(
        test_context, monkeypatch, install: bool) -> None:
    """关商店点击已发 → retry(重入观察裁决),两路径同形:店开 →
    委托体点击已发 round_retry(wait=1);新路径 = 全五段迹。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, clicks = _make_close_shop(test_context, monkeypatch, shop_open=True)

    rs = _run_node(test_context, op, op.close)

    assert not rs.is_success and '重入观察裁决' in (rs.status or ''), (
        f'点击已发应机械交回 retry:{rs!r}')
    assert len(clicks) == 1, (
        f'点击恰一次(分流后置/旧路径先执行 = 装端口双击,此处红):{clicks!r}')
    expected = _FULL_TRACE if install else []
    assert op._lifecycle_trace == expected, f'段迹漂移:{op._lifecycle_trace}'


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
@pytest.mark.parametrize('waves_fail', [False, True],
                         ids=['waves_ok', 'waves_fail'])
def test_buy_cards_delegate_passthrough_both_paths(
        test_context, monkeypatch, install: bool, waves_fail: bool) -> None:
    """买牌委托透传(旧体委托变体语义主形,两路径同形):run_buy_waves
    被恰调一次,轮次结果原样透传(rr 非空 = 透传;正常收工 = plan 摘要
    success)。新路径 = 全五段迹;旧路径 = 同形零段迹。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, calls = _make_buy_cards(test_context, monkeypatch,
                                waves_fail=waves_fail)

    rs = _run_node(test_context, op, op.buy)

    assert calls['waves'] == 1, '委托体未被恰调一次(分流/共享断裂)'
    if waves_fail:
        assert not rs.is_success and rs.status == 'FAIL', f'rr 应透传:{rs!r}'
    else:
        assert rs.is_success and 'plan 买1张' in (rs.status or ''), (
            f'正常收工应 plan 摘要 success:{rs!r}')
    expected = _FULL_TRACE if install else []
    assert op._lifecycle_trace == expected, f'段迹漂移:{op._lifecycle_trace}'
