"""统一观察架构·逐屏迁移第二批量锁(试点步骤 3:补给 + 余事件屏按族批量)。

设计正本 = docs/develop/currency_war/design/统一观察架构-画面op基类设计.md
(下称「架构设计」);迁移粒度依据 = 开放问题清单 B3 三段走第二段(代表屏
断言集模板已立 → 「补给 + 余事件屏按族批量」)+ §9.2 迁移步骤 4 建议序
(遭遇 → 补给 → 事件屏族);迁移手法单一源 = 试点步骤 2 先例
(commit 9c2e29a50 + 验收 reviews/T-215-r1.md:装配点分流 + 五段转录 +
实机适配器封口 + on_outcome 注册表;本批八屏按其「盛会之星型」共享动作体
形态落码,T-215-r1 §五.5 统一形态注意项 = lifecycle_observe 消费
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
test_cw_obs_arch_event_screens.py 断言集模板):

- **迁移结构锁**:八 op 是 CwScreenOpBase 子类 ∧ 决策承载节点顶部装配点
  分流(两端口完整在场 → 五段生命周期;缺省 None = 生产直连旧路径,§9.1
  并存期)。红 = 迁移断线(结构退回)或分流判据破坏(生产误走新路径)。
- **注册表零登记锁**(§6.4 收编面本批零行):八屏源无 register_outcome_
  hook / fire_emit_hooks 接线——§6.4 表登记件全不涉事件选卡屏;supply_
  refresh_used BoardState 字段位 = 先申报禁静默(cw_board_state.py 字段行
  自注),执行侧防重入旗标 _supply_refresh_used 留守 _do_action,不入注册
  表。红 = 未经申报面擅立登记件(EMIT_TRIGGERED_DECLARED 同款纪律)。
- **共享动作体锁**:七选卡屏 post-gate 体纯移入 ``_handle_overlay``(两路径
  共用零转录,先例 = 盛会之星 ``_do_action``);旧路径行为锁(出口 chosen
  写端/门 fail 语义)经共享体持续成立。
- **chosen_* 豁免留守锁**(§2.2/§6.5-6):chosen_* 写端仍内联于共享体
  (出口验真通过分支),不入 on_outcome 注册表收编面。
- **验证段废除源面锁**(用户裁定 2026-09-10,同
  test_cw_obs_arch_event_screens.py 同名锁):八屏源无「六段」表述、无
  'verify' 段迹字面。

驱动方式 = 真类实例(构造走 __init__,适配器位在位)+ 画面门/动作体桩化
(``_handle_overlay``/``_do_action`` 方法级桩;装配点分流桩端口 =
``_cw_helpers.install_dispatch_stub_ports`` 单一源)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.kernel.cw_board_state import board_state_of
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
from sr_od.application.currency_war.operations.cw_screen.cw_screen_op_base import (
    CwScreenOpBase,
)
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.app.currency_war._cw_helpers import install_dispatch_stub_ports

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;共享体桩只验传递不断言内容)
_OK_RS = OperationRoundResult(OperationRoundResultEnum.SUCCESS, status='stub')

#: 本批八屏:(模块名, 类名)。单一源 = 迁移面清单(模块 docstring)。
_BATCH3_SCREENS: tuple[tuple[str, str], ...] = (
    ('cw_screen_supply_node', 'CwScreenSupplyNode'),
    ('cw_screen_partner', 'CwScreenPartner'),
    ('cw_screen_planner', 'CwScreenPlanner'),
    ('cw_screen_wish_trial', 'CwScreenWishTrial'),
    ('cw_screen_fortune', 'CwScreenFortune'),
    ('cw_screen_bookcard', 'CwScreenBookcard'),
    ('cw_screen_equip_pick', 'CwScreenEquipPick'),
    ('cw_screen_expert_invite', 'CwScreenExpertInvite'),
)


class _Area:
    """round_by_find_area 桩回执(程序化回 in_screen/in_node)。"""

    def __init__(self, ok: bool) -> None:
        self.is_success = ok


def _make_op(test_context, monkeypatch, module_name: str, cls_name: str, *,
             in_screen: bool):
    """事件屏真类装配(生产构造走 __init__ = 适配器位在位)。

    桩面 = 画面门(round_by_find_area 程序化回 in_screen)+ 共享动作体
    ``_handle_overlay``(计数 + 回成功桩);``last_screenshot``/``screenshot``
    桩喂稳定帧哨兵。返回 (op, calls)。
    """
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_partner, cw_screen_planner, cw_screen_wish_trial,
        cw_screen_fortune, cw_screen_bookcard, cw_screen_equip_pick,
        cw_screen_expert_invite,
    )
    mod = {
        'cw_screen_partner': cw_screen_partner,
        'cw_screen_planner': cw_screen_planner,
        'cw_screen_wish_trial': cw_screen_wish_trial,
        'cw_screen_fortune': cw_screen_fortune,
        'cw_screen_bookcard': cw_screen_bookcard,
        'cw_screen_equip_pick': cw_screen_equip_pick,
        'cw_screen_expert_invite': cw_screen_expert_invite,
    }[module_name]
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    op = getattr(mod, cls_name)(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_screen))
    calls: list[int] = []

    def _stub_body(*_a, **_k) -> OperationRoundResult:
        calls.append(1)
        return _OK_RS

    monkeypatch.setattr(op, '_handle_overlay', _stub_body)
    return op, calls


def _make_supply(test_context, monkeypatch, *, in_node: bool):
    """补给屏真类装配(生产构造走 __init__;共享动作体 ``_do_action`` 桩)。

    桩面 = 节点完成门(round_by_find_area → _in_node)+ ``_do_action`` 计数;
    会话 = 真 StrategySession(chosen/暂存面走真实 BoardState 语义)。
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


def _run_node(test_context, op, fn) -> object:
    """节点函数运行外壳(fast_sleep + running_state;返回轮次结果)。"""
    with fast_sleep():
        enter_running_state(test_context)
        try:
            return fn()
        finally:
            reset_running_state(test_context, op)


# ==================== 迁移结构锁(§9.1 并存期)====================


def test_migration_batch3_ops_inherit_base() -> None:
    """逐屏迁移第二批量(试点步骤 3):补给 + 余事件屏八 op 均为
    CwScreenOpBase 子类(B3 三段走第二段族表)。红 = 迁移回退或漏迁。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node, cw_screen_partner, cw_screen_planner,
        cw_screen_wish_trial, cw_screen_fortune, cw_screen_bookcard,
        cw_screen_equip_pick, cw_screen_expert_invite,
    )
    for mod in (cw_screen_supply_node, cw_screen_partner, cw_screen_planner,
                cw_screen_wish_trial, cw_screen_fortune, cw_screen_bookcard,
                cw_screen_equip_pick, cw_screen_expert_invite):
        cls_name = dict(_BATCH3_SCREENS)[mod.__name__.rsplit('.', 1)[-1]]
        assert issubclass(getattr(mod, cls_name), CwScreenOpBase), (
            f'{cls_name} 未迁移到 CwScreenOpBase(B3 第二段族表)')


def test_supply_dispatch_both_ways(test_context, monkeypatch) -> None:
    """补给屏装配点分流双向:装端口 → 五段(observe 门起步,decide+act
    内聚共享动作体,节点完成判定 = 下一轮 observe 门——无验证段,迹到
    act 为止);不装端口 → 旧路径零段迹(行为保形:在屏 = 一动作 + retry)。"""
    # 装端口 + 在屏:五段新路径
    install_dispatch_stub_ports(monkeypatch)
    op, _match, _session, calls = _make_supply(
        test_context, monkeypatch, in_node=True)
    rs = _run_node(test_context, op, op.handle)
    assert calls == [1], f'每轮恰一个动作:{calls!r}'
    assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act'], (
        f'补给段迹 = observe/reconcile/decide/act(节点完成判定归下一轮 '
        f'observe 门,无验证段):{op._lifecycle_trace}')
    assert getattr(rs, '_retry', False) or not rs.is_success, '在屏 = retry'
    # 不装端口:旧路径零段迹
    from sr_od.application.currency_war import cw_game_ports as _ports_mod
    monkeypatch.setattr(_ports_mod, '_INSTALLED', (None, None))
    op2, _m2, _s2, calls2 = _make_supply(
        test_context, monkeypatch, in_node=True)
    rs2 = _run_node(test_context, op2, op2.handle)
    assert op2._lifecycle_trace == [], f'旧路径不得写段迹:{op2._lifecycle_trace}'
    assert calls2 == [1] and not rs2.is_success, (
        '旧路径在屏 = 一个动作 + retry(保形)')


def test_supply_exit_writes_chosen_on_lifecycle_path(test_context,
                                                     monkeypatch) -> None:
    """新路径出口分支:已离开节点画面 = 节点完成早退(observe 门内落
    chosen 写端)→ chosen_supply 自选定暂存写入 + 暂存取走即清 + 段迹
    仅 observe(后续段不执行)。"""
    install_dispatch_stub_ports(monkeypatch)
    op, _match, session, calls = _make_supply(
        test_context, monkeypatch, in_node=False)
    exec_state_of(session)._pending_chosen_supply = ('希儿', '星币收集器', True)
    rs = _run_node(test_context, op, op.handle)
    assert rs.is_success and '节点完成' in (rs.status or ''), (
        f'完成语义不变:{rs!r}')
    assert calls == [], '节点完成 = 不再发动作'
    assert op._lifecycle_trace == ['observe'], (
        f'出口早退 = 仅 observe 段迹:{op._lifecycle_trace}')
    bs = board_state_of(session)
    assert bs.chosen_supply.value == ('希儿', '星币收集器', True), (
        f'chosen_supply 自暂存写入:{bs.chosen_supply.value!r}')
    assert exec_state_of(session)._pending_chosen_supply is None, (
        '写后取走暂存(不跨节点残留)')


def test_supply_reentry_discards_stale_pending_both_paths(
        test_context, monkeypatch) -> None:
    """重入轮入口弃陈旧暂存(防跨轮/跨节点误写)两路径保形:在屏轮开始
    = 先 pop 取走暂存再做动作。"""
    for install in (True, False):
        if install:
            install_dispatch_stub_ports(monkeypatch)
        else:
            from sr_od.application.currency_war import (
                cw_game_ports as _ports_mod,
            )
            monkeypatch.setattr(_ports_mod, '_INSTALLED', (None, None))
        op, _match, session, _calls = _make_supply(
            test_context, monkeypatch, in_node=True)
        exec_state_of(session)._pending_chosen_supply = ('符玄', '旧选定', False)
        _run_node(test_context, op, op.handle)
        assert exec_state_of(session)._pending_chosen_supply is None, (
            f'install={install}:重入轮入口弃陈旧暂存')


def test_supply_no_outcome_registry_item(test_context, monkeypatch) -> None:
    """补给屏无 on_outcome 落地登记件(§6.4 收编面无补给行):
    supply_refresh_used BoardState 字段位 = 先申报禁静默、无写端
    (cw_board_state.py 字段行自注「收窄待证」);执行侧防重入旗标
    _supply_refresh_used 留守 _do_action。注册表缺席 = 零动作
    (盛会之星同式申报)。"""
    op, _match, _session, _calls = _make_supply(
        test_context, monkeypatch, in_node=True)
    assert not getattr(op, '_outcome_hooks', None), (
        f'补给屏不得私设登记件:{op._outcome_hooks!r}')


# ==================== 七选卡屏:装配点分流 + 共享动作体 ====================


def test_gated_screens_dispatch_both_ways(test_context, monkeypatch) -> None:
    """带门选卡屏(伙伴/祈愿试炼/星徽秘典)分流双向 + 门 fail 语义:
    装端口 → 五段(observe 门起步,共享动作体单触发);不装端口 → 旧路径
    零段迹;离屏 = round_fail 早退(旧 handle 首闸逐位转录,仅 observe
    段迹,动作体零触发)。"""
    _CASES = (
        ('cw_screen_partner', 'CwScreenPartner', '非选择伙伴屏'),
        ('cw_screen_wish_trial', 'CwScreenWishTrial', '非祈愿试炼屏'),
        ('cw_screen_bookcard', 'CwScreenBookcard', '非星徽秘典画面'),
    )
    for module_name, cls_name, fail_status in _CASES:
        # 装端口 + 在屏:五段
        install_dispatch_stub_ports(monkeypatch)
        op, calls = _make_op(test_context, monkeypatch, module_name, cls_name,
                             in_screen=True)
        rs = _run_node(test_context, op, op.handle)
        assert calls == [1], f'{cls_name}:装端口走新路径恰一动作:{calls!r}'
        assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act'], (
            f'{cls_name} 段迹 = 五段到 act:{op._lifecycle_trace}')
        assert rs.is_success, f'{cls_name}:共享体回执直返'
        # 装端口 + 离屏:observe 门 fail 早退
        op_f, calls_f = _make_op(test_context, monkeypatch, module_name,
                                 cls_name, in_screen=False)
        rs_f = _run_node(test_context, op_f, op_f.handle)
        assert not rs_f.is_success and fail_status in (rs_f.status or ''), (
            f'{cls_name} 门 fail 语义不变:{rs_f!r}')
        assert calls_f == [] and op_f._lifecycle_trace == ['observe'], (
            f'{cls_name} 离屏早退 = 零动作、仅 observe 段迹')
        # 不装端口:旧路径零段迹 + 共享体触发
        from sr_od.application.currency_war import cw_game_ports as _ports_mod
        monkeypatch.setattr(_ports_mod, '_INSTALLED', (None, None))
        op_o, calls_o = _make_op(test_context, monkeypatch, module_name,
                                 cls_name, in_screen=True)
        _run_node(test_context, op_o, op_o.handle)
        assert op_o._lifecycle_trace == [], (
            f'{cls_name} 旧路径不得写段迹:{op_o._lifecycle_trace}')
        assert calls_o == [1], f'{cls_name} 旧路径在屏 = 一动作(保形)'


def test_gateless_screens_dispatch_both_ways(test_context, monkeypatch) -> None:
    """无门选卡屏(骇入策划/命运卜者/装备三选一)分流双向:入口判定归
    主循环分发(0 系检测即门,op 内无首闸)→ observe 段 = 轻观察 payload
    (现役帧获取内聚,盛会之星同式);装端口 → 五段;不装端口 → 旧路径
    零段迹。"""
    for module_name, cls_name in (
            ('cw_screen_planner', 'CwScreenPlanner'),
            ('cw_screen_fortune', 'CwScreenFortune'),
            ('cw_screen_equip_pick', 'CwScreenEquipPick')):
        install_dispatch_stub_ports(monkeypatch)
        op, calls = _make_op(test_context, monkeypatch, module_name, cls_name,
                             in_screen=True)
        rs = _run_node(test_context, op, op.handle)
        assert calls == [1], f'{cls_name}:装端口走新路径恰一动作:{calls!r}'
        assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act'], (
            f'{cls_name} 段迹 = 五段到 act:{op._lifecycle_trace}')
        assert rs.is_success
        from sr_od.application.currency_war import cw_game_ports as _ports_mod
        monkeypatch.setattr(_ports_mod, '_INSTALLED', (None, None))
        op_o, calls_o = _make_op(test_context, monkeypatch, module_name,
                                 cls_name, in_screen=True)
        _run_node(test_context, op_o, op_o.handle)
        assert op_o._lifecycle_trace == [], (
            f'{cls_name} 旧路径不得写段迹:{op_o._lifecycle_trace}')
        assert calls_o == [1], f'{cls_name} 旧路径 = 一动作(保形)'


def test_expert_choose_dispatch_both_ways(test_context, monkeypatch) -> None:
    """专家邀请函:装配点分流在**选卡节点**(决策承载段,读板面→选卡→
    点击→验关内联其 handle 语义);开卡节点 = 纯导航(找卡/点卡/过渡帧
    等待,零决策)两路径均留旧路径(本文件源面锁另钉)。装端口 → 五段;
    不装端口 → 旧路径零段迹;弹窗未现 = round_fail 早退语义不变。"""
    # 装端口 + 弹窗在:五段
    install_dispatch_stub_ports(monkeypatch)
    op, calls = _make_op(test_context, monkeypatch, 'cw_screen_expert_invite',
                         'CwScreenExpertInvite', in_screen=True)
    rs = _run_node(test_context, op, op.choose)
    assert calls == [1] and rs.is_success
    assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act'], (
        f'选卡节点段迹 = 五段到 act:{op._lifecycle_trace}')
    # 装端口 + 弹窗未现:observe 门 fail 早退
    op_f, calls_f = _make_op(test_context, monkeypatch, 'cw_screen_expert_invite',
                             'CwScreenExpertInvite', in_screen=False)
    rs_f = _run_node(test_context, op_f, op_f.choose)
    assert not rs_f.is_success and '邀请函弹窗未现' in (rs_f.status or ''), (
        f'选卡入口门 fail 语义不变:{rs_f!r}')
    assert calls_f == [] and op_f._lifecycle_trace == ['observe']
    # 不装端口:旧路径零段迹
    from sr_od.application.currency_war import cw_game_ports as _ports_mod
    monkeypatch.setattr(_ports_mod, '_INSTALLED', (None, None))
    op_o, calls_o = _make_op(test_context, monkeypatch, 'cw_screen_expert_invite',
                             'CwScreenExpertInvite', in_screen=True)
    _run_node(test_context, op_o, op_o.choose)
    assert op_o._lifecycle_trace == [], (
        f'旧路径不得写段迹:{op_o._lifecycle_trace}')
    assert calls_o == [1]


def test_expert_open_card_node_stays_legacy() -> None:
    """开卡节点 = 纯导航留旧路径申报面(两路径同式):源无装配点分流/
    生命周期调用——六段辖选卡节点(决策承载段),开卡找卡/点卡动作无
    决策消费面,不属观察端口辖(架构设计 §2.5 端口辖循环体决策面)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_expert_invite as ei,
    )
    src = inspect.getsource(ei.CwScreenExpertInvite.open_card)
    assert 'run_lifecycle' not in src and 'observation_source' not in src, (
        '开卡节点不得接分流(纯导航节点留旧路径,申报面见本锁)')


# ==================== 注册表零登记 + 源面形态锁 ====================


def test_batch3_no_outcome_registry_wiring() -> None:
    """注册表零登记锁(§6.4 收编面本批零行):八屏源无 register_outcome_
    hook / fire_emit_hooks 接线。§6.4 表登记件(刷新执行事实组/bump_key/
    合成升星 expect/免战牌 consume_use/遭遇·策略屏刷新计数)全不涉事件
    选卡屏;新登记件入册须先申报(EMIT_TRIGGERED_DECLARED 同款纪律),
    红 = 未经申报擅立登记件。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node, cw_screen_partner, cw_screen_planner,
        cw_screen_wish_trial, cw_screen_fortune, cw_screen_bookcard,
        cw_screen_equip_pick, cw_screen_expert_invite,
    )
    for mod in (cw_screen_supply_node, cw_screen_partner, cw_screen_planner,
                cw_screen_wish_trial, cw_screen_fortune, cw_screen_bookcard,
                cw_screen_equip_pick, cw_screen_expert_invite):
        src = inspect.getsource(mod)
        assert 'register_outcome_hook' not in src, (
            f'{mod.__name__} 私设落地登记件(§6.4 收编面本批零行)')
        assert 'fire_emit_hooks' not in src, (
            f'{mod.__name__} 私设发射型触发(在册两件不涉本批屏)')


def test_batch3_sources_free_of_verify_segment() -> None:
    """验证段废除·源面锁(用户裁定 2026-09-10:动作 op 只管机械执行,
    禁止在画面 op 做验证):八屏源无「六段」表述、无 'verify' 段迹字面;
    节点完成判定归 observe 门复检(观察驱动节点循环),落地判定归动作
    适配器回执(§6.2)。红 = 验证段残面回潮。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node, cw_screen_partner, cw_screen_planner,
        cw_screen_wish_trial, cw_screen_fortune, cw_screen_bookcard,
        cw_screen_equip_pick, cw_screen_expert_invite,
    )
    for mod in (cw_screen_supply_node, cw_screen_partner, cw_screen_planner,
                cw_screen_wish_trial, cw_screen_fortune, cw_screen_bookcard,
                cw_screen_equip_pick, cw_screen_expert_invite):
        src = inspect.getsource(mod)
        assert '六段' not in src, (
            f'{mod.__name__} 源面残留「六段」表述(验证段已废除)')
        assert "'verify'" not in src, (
            f'{mod.__name__} 源面残留 verify 段迹字面(验证段已废除)')
