"""统一观察架构·五相位屏迁移锁(账本 T-8,余项收口阶段一)。

设计正本 = docs/develop/sr_od/application/currency_war/design/统一观察架构-画面op基类设计.md
(下称「架构设计」);迁移粒度/五段形态依据 = changes/2026-09-11-
unified-observation/details/五相位屏迁移详设.md(逐屏五段表与语义保真点);
迁移手法单一源 = 装配点分流 + 五段钩子转录 + 实机适配器①封口 + on_outcome
注册表(先例:CwScreenPrep/遭遇/盛会之星,断言集模板 =
test_cw_obs_arch_event_screens.py)。本批五屏:投资环境 CwScreenInvestEnv /
投资策略 CwScreenInvestStrategy / 战斗等待 CwScreenBattleWait / 简报
CwScreenBriefing / BOSS 简报 CwScreenBossBriefing。

**F11 sim 腿不适用例外清单(随迁移批逐屏落测试 docstring,总纲 §2.2-3)**:

- 投资环境/投资策略:sim 腿 = 不适用——有 sim 事实来源(``decide_invest``
  注入段,架构设计 §3.2)但 sim 端口适配器未建(归 sim 接线批),本批
  等价判据主承重 = 实机在册行为锁 + 写入流对拍(实机腿),禁引用 sim 域
  对拍;
- 战斗等待:sim 腿 = 不适用——sim 事实来源为 coarse 结算产出,非画面段
  (§3.2 结算行),等价判据主承重 = 实机在册行为锁(B2-③ 主门:在册
  行为锁经 execute()/wait() 走新路径全绿);
- 简报/BOSS 简报:sim 腿 = 不适用——sim 无对应画面段(过渡相位,§3.2),
  等价判据主承重 = 实机在册行为锁 + 写入流对拍。

锁的语义(测试纪律 7 自检;出处 = landing 阶段一判据 + 总纲契约 1-6):

- **迁移结构锁**:五 op 是 CwScreenOpBase 子类 ∧ start 节点方法顶部装配点
  分流(投资两屏/简报/BOSS 简报 = ``handle``,战斗等待 = ``wait()``;两端口
  完整在场 → ``run_lifecycle``;缺省 None = 生产直连旧路径,§9.1 并存期)。
- **重入裁决归属锁**(总纲契约 6,单一定谳):投资两屏/简报的「已发」旗标
  裁决住分流判据**之前**两路径共享段(裁决出口写端随段共享);战斗等待/
  BOSS 简报无裁决旗标,分流在出口判定之前。先例锚 = cw_screen_encounter.py
  :241-251(裁决)/:252-258(分流)。红 = 裁决被转录进 observe 段/适配器①。
- **新路径行为锁**(§9.1-F2 主门 (a)):四屏装两端口经节点方法走新路径,
  段迹形态 + 单轮动作/确认置位行为(模板同构 = 事件屏锁 :170-184 段迹、
  :247-259 单动作);战斗等待在册行为锁语义(出口分叉/C-1 计数/defer 复位/
  M39 长按/未知帧 bail/D-94 读点先于点击)经新路径逐条重驱动全绿(B2-③)。
- **发射型接线锁**(§6.4-R-E 在册两件②):strategy_refresh_used 写端自
  刷新链内联位收编为 on_outcome 注册表发射型钩子,触发点唯一
  (``_emit_refresh_click`` 两路径共用分派面);「随点击置位不等验效」
  逐字保绿(B5-④)。
- **登记语义对拍锁**(B5-③):写端值/evidence/produced_by(流水行
  sig.actor)与现役内联位逐位一致。
- **写入流对拍锁**(§9.1-F2 主门 (b)):``active_env`` 选卡时点写(值/
  写时点 = 点卡前)、``active_strategies`` 重入裁决出口 append(值/时点)、
  简报三字段 session 写(词缀幂等辖「读+采」/boss 恒覆写/难度仅 None 写)
  逐位;结算观察半直写(D-94 时序)经战斗等待在册行为锁的轨迹断言承载。
- **豁免留守锁**(§2.2/§6.5-6):``active_env``/``active_strategies``/
  效果账本登记不入注册表收编面。
- **判别单一源消费面锁**:`is_boss_briefing_texts` 消费点集合迁移前后不变
  (cw_loop / cw_screen_battle_wait / cw_screen_boss_briefing;防转录顺手
  复制判别逻辑)。

驱动方式 = 真类实例(构造走 __init__,注册表/适配器位在位)+ 读链/点击链
桩化;装配点分流桩端口 = ``_cw_helpers.install_dispatch_stub_ports`` 单一源;
不装端口(生产缺省形态)= 旧路径代表驱动(并存窗旧路径锁专用)。
"""
from __future__ import annotations

import inspect
import time
from types import SimpleNamespace

import pytest

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.kernel import cw_state_journal as journal_mod
from sr_od.application.currency_war.kernel.cw_board_state import board_state_of
from sr_od.application.currency_war.kernel.cw_exec_state import (
    ExecState,
    exec_state_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    normalize_invest_name,
)
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
from sr_od.application.currency_war.operations.cw_screen.cw_screen_op_base import (
    CwScreenOpBase,
)
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
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


# ==================== 迁移结构锁 + 重入裁决归属锁 ====================

_PHASE_OPS = (
    ('cw_screen_invest_env', 'CwScreenInvestEnv'),
    ('cw_screen_invest_strategy', 'CwScreenInvestStrategy'),
    ('cw_screen_battle_wait', 'CwScreenBattleWait'),
    ('cw_screen_briefing', 'CwScreenBriefing'),
    ('cw_screen_boss_briefing', 'CwScreenBossBriefing'),
)


def _phase_mod(name: str):
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait,
        cw_screen_boss_briefing,
        cw_screen_briefing,
        cw_screen_invest_env,
        cw_screen_invest_strategy,
    )
    return {
        'cw_screen_invest_env': cw_screen_invest_env,
        'cw_screen_invest_strategy': cw_screen_invest_strategy,
        'cw_screen_battle_wait': cw_screen_battle_wait,
        'cw_screen_briefing': cw_screen_briefing,
        'cw_screen_boss_briefing': cw_screen_boss_briefing,
    }[name]


def test_phase_ops_inherit_base() -> None:
    """五相位屏迁移(账本 T-8):五 op 均为 CwScreenOpBase 子类。
    红 = 迁移回退或漏迁。"""
    for mod_name, cls_name in _PHASE_OPS:
        mod = _phase_mod(mod_name)
        assert issubclass(getattr(mod, cls_name), CwScreenOpBase), (
            f'{cls_name} 未迁移到 CwScreenOpBase(T-8 五相位屏)')


def test_dispatch_and_reentry_arbitration_source_form() -> None:
    """装配点分流 + 重入裁决归属(总纲契约 6,源形态锁;先例锚 =
    cw_screen_encounter.py :241-251/:252-258「两路径共用(分流前挂,先于
    五段 lifecycle 的 observe 门)」):
    - 投资环境/投资策略/简报:「已发」旗标裁决住 handle 内 ``run_lifecycle``
      分流判据**之前**(裁决出口写端随共享段;禁转录进 observe 段/适配器①);
    - 战斗等待:无裁决旗标,``wait()`` 内分流在出口判定(大厅终局锚)之前;
    - BOSS 简报:无裁决旗标,分流在 handle 首行(横幅判定之前)。
    红 = 裁决被移进五段 observe 形态/适配器,或分流判据缺失。"""
    # 投资两屏/简报:裁决(旗标消费)先于分流(run_lifecycle)
    for mod_name, cls_name, flag in (
            ('cw_screen_invest_env', 'CwScreenInvestEnv', '_confirm_pending'),
            ('cw_screen_invest_strategy', 'CwScreenInvestStrategy', '_confirm_pending'),
            ('cw_screen_briefing', 'CwScreenBriefing', '_click_pending')):
        src = inspect.getsource(getattr(_phase_mod(mod_name), cls_name).handle)
        i_flag = src.index(flag)
        i_disp = src.index('run_lifecycle')
        assert i_flag < i_disp, (
            f'{cls_name}: 重入裁决须住装配点分流之前(总纲契约 6 两路径共享段)')
    # 战斗等待:分流先于出口判定(本屏无裁决旗标;出口判定旧路径原位保留,
    # observe 段另持转录份——遭遇先例同式,门判定纯读零副作用)
    bw_src = inspect.getsource(
        _phase_mod('cw_screen_battle_wait').CwScreenBattleWait.wait)
    i_disp = bw_src.index('run_lifecycle')
    i_exit = bw_src.index('标识-创业指南')
    assert i_disp < i_exit, (
        '战斗等待分流须在 wait() 首行、出口判定之前(详设关键取舍 4)')
    assert '_dispatch_frame' in bw_src, (
        '战斗等待分流后分支链经共享方法承载(两路径共享零转录)')
    bb_src = inspect.getsource(
        _phase_mod('cw_screen_boss_briefing').CwScreenBossBriefing.handle)
    assert bb_src.index('run_lifecycle') < bb_src.index('banner_hit'), (
        'BOSS 简报分流在首行(无裁决旗标,横幅判定归 observe 段)')


# ==================== 投资环境:分流双向 + 写入流对拍 ====================


def _make_env(test_context, monkeypatch: pytest.MonkeyPatch, *,
              in_screen: bool, opts: list | None = None, pick_idx: int = 0,
              events: list | None = None):
    """投资环境真类装配(生产构造走 __init__ = 适配器位/注册表在位)。

    桩面 = 画面门/截屏/候选读/策略器/确认链/计数读/台账写点;``safe_click``
    记录点击并快照点击时点 ``active_env`` 现值(选卡时点写对拍载体)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_env as iem,
    )

    session = StrategySession()
    strategy = SimpleNamespace(
        decide_invest=lambda kind, names, st, sess, cfg: SimpleNamespace(
            option_idx=pick_idx, reason='stub'))
    match = SimpleNamespace(strategy=strategy, session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = iem.CwScreenInvestEnv(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_screen))
    monkeypatch.setattr(op, 'screenshot', lambda: _FRAME)
    monkeypatch.setattr(op, '_read_options',
                        lambda screen: list(opts or []))
    monkeypatch.setattr(op, '_refresh_node_ledger', lambda: None)
    monkeypatch.setattr(iem, 'read_invest_refresh_counts',
                        lambda ctx, scr, kind: [])

    def _click(op_, pt, **k):
        if events is not None:
            events.append(('card_click', (pt.x, pt.y)))
            events.append(('active_env_at_click',
                           board_state_of(session).active_env.value))

    monkeypatch.setattr(iem, 'safe_click', _click)
    monkeypatch.setattr(iem, 'emit_overlay_confirm', lambda op_, **k: _RETRY_RS)
    monkeypatch.setattr(iem.time, 'sleep', lambda *_: None)
    import sr_od.application.currency_war.kernel.cw_bs_view as bs_view_mod
    monkeypatch.setattr(bs_view_mod, 'strategy_input_state',
                        lambda sess: GameState())
    return op, match, session


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_invest_env_dispatch_and_gate(test_context, monkeypatch,
                                      install: bool) -> None:
    """投资环境分流双向 + 段迹形态(§9.1-F2 主门 (a) 本屏行):装两端口 →
    五段新路径(段迹 observe..on_outcome 恰五段;确认发出置 pending,落地
    归重入裁决);离屏 → observe 门 fail 早退(仅 observe 段迹,零动作);
    不装端口 → 旧路径零段迹同行为。红 = 分流判据破坏或段迹漂移。"""
    opts = [('追击概念股', 460), ('彩虹时代', 960), ('头彩', 1460)]
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, _match, _session = _make_env(test_context, monkeypatch,
                                     in_screen=True, opts=opts, pick_idx=1)
    rs = _run_node(test_context, op, op.handle)
    if install:
        assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act',
                                       'on_outcome'], (
            f'装端口须走五段新路径:{op._lifecycle_trace}')
    else:
        assert op._lifecycle_trace == [], f'旧路径不得写段迹:{op._lifecycle_trace}'
    assert op._confirm_pending is True, '确认已发 → pending 置位(重入裁决承载)'
    assert not rs.is_success, '确认链机械交回 round_retry(保形)'
    # 离屏:门 fail 早退(新路径 = observe 段早退仅 observe 段迹;旧路径 =
    # 旧序列早退零段迹,行为同形)
    op_f, _m_f, _s_f = _make_env(test_context, monkeypatch, in_screen=False,
                                 opts=opts)
    rs_f = _run_node(test_context, op_f, op_f.handle)
    assert not rs_f.is_success and '非投资环境屏' in (rs_f.status or ''), (
        f'观察门早退语义不变:{rs_f!r}')
    expected_gate_trace = ['observe'] if install else []
    assert op_f._lifecycle_trace == expected_gate_trace, (
        f'离屏早退段迹:{op_f._lifecycle_trace}')


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_invest_env_active_env_written_at_pick_time(test_context,
                                                    monkeypatch,
                                                    install: bool) -> None:
    """写入流对拍(§9.1-F2 主门 (b)):``active_env`` 选卡时点写——写时点 =
    点卡**前**(点击时点快照已见新值)、值 = 决策选中名、两路径逐位一致
    (写端住共享 ``_decide_and_act``,零转录)。红 = 写时点后移(落选卡后)
    或两路径值漂移。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    events: list = []
    opts = [('追击概念股', 460), ('彩虹时代', 960), ('头彩', 1460)]
    op, _match, session = _make_env(test_context, monkeypatch, in_screen=True,
                                    opts=opts, pick_idx=1, events=events)
    _run_node(test_context, op, op.handle)
    assert ('active_env_at_click', '彩虹时代') in events, (
        f'active_env 须写在点卡前(选卡时点语义):{events!r}')
    assert board_state_of(session).active_env.value == '彩虹时代', (
        '值 = 决策选中名(produced_by 面 = CwScreenInvestEnv,见豁免留守锁'
        '源形态断言)')


# ==================== 投资策略:分流双向 + 发射型接线 + 对拍 ====================


class _FrameBook:
    """帧登记簿:op.screenshot 逐次弹帧(末帧复用);读桩按帧对象分发
    (test_cw_invest_refresh 同款形态)。"""

    def __init__(self, frames: list[object]) -> None:
        self.frames = frames
        self.options: dict[int, list] = {}
        self.counts: dict[int, list] = {}
        self.i = 0

    def next_frame(self) -> object:
        f = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return f


def _make_strategy(test_context, monkeypatch: pytest.MonkeyPatch,
                   book: _FrameBook, picks: list, *,
                   entry_ok: bool = True, anchor_hit: bool = True):
    """投资策略真类装配(生产构造走 __init__ = 注册表在位)。

    桩面 = 入口锚/截屏/候选读/计数读/点击/确认链;``_ensure_entry_screen``
    方法级桩(复探窗语义归 ADR-0529 既有锁,本文件不辖)。返回
    ``(op, match, session, clicks, decide_calls)``。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy as ism,
    )

    session = StrategySession()
    decide_calls: list[list[str]] = []

    def _decide(kind, names, st, sess, cfg):
        decide_calls.append(list(names))
        return picks.pop(0) if picks else SimpleNamespace(
            option_idx=0, reason='stub-exhausted')

    match = SimpleNamespace(strategy=SimpleNamespace(decide_invest=_decide),
                            session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = ism.CwScreenInvestStrategy(test_context)
    monkeypatch.setattr(op, '_ensure_entry_screen', lambda: entry_ok)
    monkeypatch.setattr(op, '_entry_anchor_hit', lambda screen: anchor_hit)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: book.next_frame())
    monkeypatch.setattr(op, '_read_options',
                        lambda screen: book.options.get(id(screen), []))
    clicks: list = []
    monkeypatch.setattr(ism, 'read_invest_refresh_counts',
                        lambda ctx, scr, kind: book.counts.get(id(scr), []))
    monkeypatch.setattr(ism, 'safe_click',
                        lambda op_, pt, **k: clicks.append(pt))

    def _confirm_stub(op_, confirm_point, **k):
        clicks.append(confirm_point)   # 确认点击经桩记录(test_cw_invest_refresh 同形)
        return _RETRY_RS

    monkeypatch.setattr(ism, 'emit_overlay_confirm', _confirm_stub)
    monkeypatch.setattr(ism.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(op, '_interruptible_sleep', lambda s: None)
    import sr_od.application.currency_war.kernel.cw_bs_view as bs_view_mod
    monkeypatch.setattr(bs_view_mod, 'strategy_input_state',
                        lambda sess: GameState())
    return op, match, session, clicks, decide_calls


_OPT_XS = (460, 960, 1460)
_CNT_Y = 855
_DX = -88   # = CwScreenInvestStrategy._REFRESH_BTN_DX(常量单一源直读)


def _opts_of(names: list[str]) -> list[tuple[str, int, int]]:
    return [(n, _OPT_XS[i], 490) for i, n in enumerate(names)]


def test_invest_strategy_dispatch_new_path(test_context, monkeypatch) -> None:
    """投资策略分流双向 + 段迹形态(主门 (a) 本屏行):装两端口 → 五段
    新路径;在屏轮确认发出置 pending 且 **不 append active_strategies**
    (append 归重入裁决出口,ADR-0598);不装端口 → 旧路径零段迹同行为。
    红 = 分流判据破坏/持卡时点漂移。"""
    install_dispatch_stub_ports(monkeypatch)
    book = _FrameBook([object()])
    book.options[id(book.frames[0])] = _opts_of(['赌神·银', '恢复生机', '气氛组'])
    picks = [SimpleNamespace(option_idx=1, refresh=False, refresh_slots=(),
                             reason='stub')]
    op, _match, session, clicks, decide_calls = _make_strategy(
        test_context, monkeypatch, book, picks)
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act',
                                   'on_outcome'], (
        f'装端口须走五段新路径:{op._lifecycle_trace}')
    assert len(clicks) == 2, f'现状路径恰两击(选卡+确认):{clicks!r}'
    assert op._confirm_pending == '恢复生机', '确认已发 → pending 置位'
    assert session.active_strategies == [], (
        '在屏轮不 append 持卡(append 归重入裁决出口,ADR-0598)')
    assert len(decide_calls) == 1, '恰一次决策'
    # 不装端口:旧路径零段迹(生产形态)
    _uninstall_ports(monkeypatch)
    book2 = _FrameBook([object()])
    book2.options[id(book2.frames[0])] = _opts_of(['赌神·银', '恢复生机', '气氛组'])
    picks2 = [SimpleNamespace(option_idx=1, refresh=False, refresh_slots=(),
                              reason='stub')]
    op2, _m2, _s2, clicks2, _dc2 = _make_strategy(test_context, monkeypatch,
                                                  book2, picks2)
    rs2 = _run_node(test_context, op2, op2.handle)
    assert op2._lifecycle_trace == [], f'旧路径不得写段迹:{op2._lifecycle_trace}'
    assert len(clicks2) == 2 and op2._confirm_pending == '恢复生机', (
        '旧路径行为保形(两击 + pending 置位)')
    assert not rs2.is_success and not rs.is_success, '确认链机械交回 round_retry'


def test_invest_strategy_active_strategies_appended_at_reentry_exit(
        test_context, monkeypatch) -> None:
    """写入流对拍(主门 (b)):``active_strategies`` append 时点 = 重入裁决
    出口(入口锚不在 = overlay 已关 = 选卡落地)——总纲契约 6 裁决出口写端
    随共享段,单驱动两路径同承;值 = 待裁决选卡名 + 去重;BoardState 写端
    (list 本体)同点。红 = append 时点前移(幻影卡回潮,ADR-0598)。"""
    for install in (True, False):
        if install:
            install_dispatch_stub_ports(monkeypatch)
        else:
            _uninstall_ports(monkeypatch)
        op = _phase_mod('cw_screen_invest_strategy').CwScreenInvestStrategy(
            test_context)
        session = StrategySession()
        match = SimpleNamespace(strategy=SimpleNamespace(), session=session)
        monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
        monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
        monkeypatch.setattr(op, '_entry_anchor_hit', lambda screen: False)
        op._confirm_pending = '白银投资'
        rs = _run_node(test_context, op, op.handle)
        assert rs.is_success and '已确认(重入观察裁决)' in (rs.status or ''), (
            f'install={install}:裁决出口 success 交回:{rs!r}')
        assert session.active_strategies == ['白银投资'], (
            f'install={install}:append 值 = 待裁决选卡名')
        assert board_state_of(session).active_strategies.value == ['白银投资'], (
            f'install={install}:BoardState 写端同点(list 本体)')
        assert op._lifecycle_trace == [], (
            f'install={install}:裁决在分流前共享段,本轮不经生命周期(零段迹)')
        # 去重:同卡二次确认不重复入列
        op._confirm_pending = '白银投资'
        _run_node(test_context, op, op.handle)
        assert session.active_strategies == ['白银投资'], (
            f'install={install}:去重防重复入列')


def test_strategy_refresh_emission_wired_to_registry(test_context,
                                                     monkeypatch) -> None:
    """发射型接线锁(§6.4-R-E 在册两件②;B5-② 形态):①注册表在 __init__
    按 StrategyRefreshClick 登记发射钩子(name=strategy_refresh_used,已在
    申报面——基类申报面本批零增改;运行时注册表直接取证);②单一发射口
    fire_outcome_hooks 全模块恰一处 + 原口名退役墓碑(两 fire 口合并,
    T-223)。登记件写端住钩子体/发射点同步置位防重入旗标不再源码在场锁
    (纪律 8 肯定性在场禁):两路径真实驱动的行为锁
    (test_strategy_refresh_emission_semantics:值/evidence/防重入旗标/
    sig.actor 逐位对拍)承重同一事实。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy as ism,
    )
    src = inspect.getsource(ism)
    assert src.count('fire_outcome_hooks') == 1, (
        '发射触发点须唯一且经单一发射口(_emit_refresh_click 分派面)')
    assert 'fire_emit_hooks' not in src, (
        '原发射口名须已退役(两 fire 口合并,T-223)')
    op = ism.CwScreenInvestStrategy(test_context)
    specs = op._outcome_hooks.get(
        ism.StrategyRefreshClick(slot=0, name='x').__class__, [])
    assert any(s.name == 'strategy_refresh_used' for s in specs), (
        f'发射登记件须在 __init__ 入注册表:{specs!r}')


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_strategy_refresh_emission_semantics(test_context, monkeypatch,
                                             journal_rows,
                                             install: bool) -> None:
    """B5-④ 发射型断言 + 登记语义对拍锁(B5-③):建议刷新 → 槽计数 >0 →
    发射即置位(+1 带证据),卡面未变帧(原「验效失败」形态)仍 +1;值/
    evidence/produced_by(流水行 sig.actor)逐位 = 现役内联位口径;发射后
    无条件重读 + 经 decide_invest 重决策(恰两次,验效双通道已拆形态)。
    两路径同断言(登记件经共用分派面,位置迁移语义不变)。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        register_sig_actors,
    )
    register_sig_actors('CwScreenInvestStrategy')
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    names = ['赌神·银', '恢复生机', '气氛组']
    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _opts_of(names)
    book.options[id(book.frames[1])] = _opts_of(names)   # 重读 = 原卡面(未变形态)
    book.counts[id(book.frames[0])] = [(1, 477, _CNT_Y), (1, 975, _CNT_Y),
                                       (1, 1474, _CNT_Y)]
    picks = [
        SimpleNamespace(option_idx=0, refresh=True, refresh_slots=(0,),
                        reason='stub+refresh'),
        SimpleNamespace(option_idx=0, reason='re-decide'),
    ]
    op, _match, session, clicks, decide_calls = _make_strategy(
        test_context, monkeypatch, book, picks)
    _run_node(test_context, op, op.handle)
    bs = board_state_of(session)
    _k = normalize_invest_name(names[0])
    assert bs.strategy_refresh_used.value == {_k: 1}, (
        f'卡面未变帧仍 +1(随点击置位不等验效,B5-④):{bs.strategy_refresh_used.value!r}')
    assert bs.strategy_refresh_used.evidence == 'refresh_click@slot0', (
        f'发射证据逐位一致:{bs.strategy_refresh_used.evidence!r}')
    assert exec_state_of(session)._invest_refresh_used_slots == {0}, (
        '防重入旗标(执行侧载体)发射点同步置位')
    assert len(decide_calls) == 2, (
        f'刷后无条件重读 + 重决策(恰两次,验效双通道已拆):{decide_calls!r}')
    rows = [r for r in journal_rows.rows
            if r['field'] == 'strategy_refresh_used']
    assert rows and rows[-1]['sig']['actor'] == 'CwScreenInvestStrategy', (
        f'流水行 sig.actor = 产生者(produced_by 对拍面):{rows!r}')
    refresh_clicks = [c for c in clicks if c.y == _CNT_Y]
    assert [(c.x, c.y) for c in refresh_clicks] == [(477 + _DX, _CNT_Y)], (
        f'刷新点击恰一次(槽 0 文本锚定):{refresh_clicks!r}')


@pytest.fixture()
def journal_rows(tmp_path):
    """装一份指到 tmp 的状态流水(teardown 复位;test_cw_state_telemetry_w1
    同款形态)。"""
    j = journal_mod.install_state_telemetry(
        tmp_path / 'state' / 'journal.jsonl',
        run_id_provider=lambda: 'run_t8')
    yield j
    journal_mod.reset_state_telemetry()


# ==================== 豁免留守锁(§2.2/§6.5-6)====================


def test_write_flow_exempt_surfaces_stay_inline() -> None:
    """豁免留守锁:``active_env``/``active_strategies``/效果账本登记不入
    on_outcome 注册表收编面——①投资策略模块 register_outcome_hook 恰一处
    (__init__ 接线),钩子体无 active_strategies/效果账本登记;
    ``_append_confirmed_strategy`` 原位保留本体追加 + write_logic +
    register_strategy + apply_effect_burst_grant;②投资环境模块零注册表
    接线,active_env 写端住共享 ``_decide_and_act``(produced_by 面逐位)。
    红 = 豁免面被顺手收编。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_env as iem,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy as ism,
    )
    ism_src = inspect.getsource(ism)
    assert ism_src.count('register_outcome_hook') == 1, (
        '投资策略注册表接线恰一处(__init__;豁免面不得另立登记件)')
    hook_src = inspect.getsource(ism.CwScreenInvestStrategy._on_refresh_emitted)
    assert 'active_strategies' not in hook_src, (
        'active_strategies 不入注册表收编面(重入裁决出口豁免留守)')
    assert 'register_strategy' not in hook_src and \
        'apply_effect_burst_grant' not in hook_src, (
        '效果账本登记不入注册表收编面(豁免留守)')
    append_src = inspect.getsource(
        ism.CwScreenInvestStrategy._append_confirmed_strategy)
    for token in ('active_strategies', 'write_logic', 'register_strategy',
                  'apply_effect_burst_grant'):
        assert token in append_src, f'豁免留守面缺 {token}(_append_confirmed_strategy 原位)'
    env_src = inspect.getsource(iem)
    assert 'register_outcome_hook' not in env_src and \
        'fire_outcome_hooks' not in env_src, (
        '投资环境零登记件(环境侧刷新执行不启用,ADR-0600 §2/§4)')
    act_src = inspect.getsource(iem.CwScreenInvestEnv._decide_and_act)
    assert "produced_by='CwScreenInvestEnv'" in act_src, (
        'active_env 写端 produced_by 逐位(选卡时点,选卡 handler 单次逻辑写入豁免)')


# ==================== 简报:分流双向 + 三字段写语义 ====================


def _make_briefing(test_context, monkeypatch: pytest.MonkeyPatch, *,
                   mark_hit: bool = True, bosses: list | None = None,
                   affixes: list | None = None, difficulty: int | None = 5,
                   session: StrategySession | None = None):
    """简报真类装配。桩面 = 画面门/「下一步」点击/三读链;读链桩按记录器
    计数(幂等守卫辖「读+采」断言载体)。返回 (op, session, calls)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_briefing as bm,
    )

    session = session or StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op = bm.CwScreenBriefing(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(mark_hit))
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda *a, **k: _Area(True))
    calls = {'affix_read': 0, 'affix_collect': 0, 'boss_read': 0,
             'diff_read': 0}
    monkeypatch.setattr(bm, 'read_affixes_with_pos',
                        lambda ctx, scr: (calls.__setitem__(
                            'affix_read', calls['affix_read'] + 1)
                            or list(affixes or [])))
    monkeypatch.setattr(bm, 'read_bosses',
                        lambda ctx, scr: (calls.__setitem__(
                            'boss_read', calls['boss_read'] + 1)
                            or list(bosses or [])))
    monkeypatch.setattr(bm, 'clean_boss_names_by_lcs', lambda bs: bs)
    monkeypatch.setattr(bm, 'read_briefing_enemy_difficulty',
                        lambda ctx, scr: (calls.__setitem__(
                            'diff_read', calls['diff_read'] + 1) or difficulty))
    monkeypatch.setattr(bm.CwScreenBriefing, '_collect_affix_effects',
                        lambda self, aff: (calls.__setitem__(
                            'affix_collect', calls['affix_collect'] + 1) or {}))
    return op, session, calls


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_briefing_dispatch_and_session_writes(test_context, monkeypatch,
                                              install: bool) -> None:
    """简报分流双向(主门 (a) 本屏行):装两端口 → 五段新路径(段迹恰五段;
    「下一步」发出置 pending + round_retry 机械交回,落地归重入裁决);标识
    miss → observe 门 fail 早退(仅 observe 段迹,零动作);不装端口 → 旧
    路径零段迹同行为。红 = 分流判据破坏或段迹漂移。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    op, session, calls = _make_briefing(
        test_context, monkeypatch, mark_hit=True,
        affixes=[('火弱点', None)], bosses=['碎星王虫'], difficulty=5)
    rs = _run_node(test_context, op, op.handle)
    if install:
        assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act',
                                       'on_outcome'], (
            f'装端口须走五段新路径:{op._lifecycle_trace}')
    else:
        assert op._lifecycle_trace == [], f'旧路径不得写段迹:{op._lifecycle_trace}'
    assert op._click_pending is True, '「下一步」已发 → pending 置位(重入裁决)'
    assert not rs.is_success and '重入观察裁决' in (rs.status or ''), (
        f'机械交回 round_retry(保形):{rs!r}')
    assert session.briefing_affixes == ['火弱点'], '词缀 session 直写'
    assert session.briefing_bosses == ['碎星王虫'], 'boss session 直写(恒覆写)'
    assert session.enemy_difficulty == 5, '难度 session 直写(仅 None 写)'
    # 标识 miss:门 fail 早退(新路径 = observe 段早退仅 observe 段迹;旧
    # 路径 = 旧序列早退零段迹,行为同形)
    op_f, _s_f, calls_f = _make_briefing(test_context, monkeypatch,
                                         mark_hit=False)
    rs_f = _run_node(test_context, op_f, op_f.handle)
    assert not rs_f.is_success and '非简报屏' in (rs_f.status or ''), (
        f'标识门早退语义不变:{rs_f!r}')
    expected_gate_trace = ['observe'] if install else []
    assert op_f._lifecycle_trace == expected_gate_trace, (
        f'离屏早退段迹:{op_f._lifecycle_trace}')
    assert calls_f['affix_read'] == 0 and calls_f['boss_read'] == 0, (
        '离屏零观察(门失败后不做读链)')


@pytest.mark.parametrize('install', [True, False], ids=['new_path', 'old_path'])
def test_briefing_session_write_semantics_three_fields(test_context,
                                                       monkeypatch,
                                                       install: bool) -> None:
    """写入流对拍(主门 (b)):简报三字段三种写语义逐字——①词缀幂等守卫
    辖「读+采」(session 非空 → 跳过读与点采);②boss 恒覆写(不做已存
    跳过,防跨局残留;读空 → 清 None);③敌人难度仅 None 时写。红 = 守卫
    辖面漂移(如幂等只辖读不辖采)或覆写语义丢失。"""
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    # ① 词缀幂等守卫辖「读+采」
    session = StrategySession()
    session.briefing_affixes = ['已有词缀']
    op, session, calls = _make_briefing(test_context, monkeypatch,
                                        mark_hit=True, affixes=['新词缀'],
                                        bosses=['碎星王虫'], session=session)
    _run_node(test_context, op, op.handle)
    assert calls['affix_read'] == 0 and calls['affix_collect'] == 0, (
        f'session 已有词缀 → 跳过读与点采(幂等辖「读+采」):{calls!r}')
    assert session.briefing_affixes == ['已有词缀'], '幂等轮不覆写词缀'
    assert session.briefing_bosses == ['碎星王虫'], 'boss 幂等豁免(恒覆写)照写'
    # ② boss 恒覆写:残留 → 本局真值;读空 → 清 None
    session2 = StrategySession()
    session2.briefing_bosses = ['上一局残留']
    op2, session2, _c2 = _make_briefing(test_context, monkeypatch,
                                        mark_hit=True, bosses=['碎星王虫'],
                                        session=session2)
    _run_node(test_context, op2, op2.handle)
    assert session2.briefing_bosses == ['碎星王虫'], 'boss 恒覆写防跨局残留'
    op2b, session2b, _c2b = _make_briefing(test_context, monkeypatch,
                                           mark_hit=True, bosses=[],
                                           session=StrategySession())
    session2b.briefing_bosses = ['上一局残留']
    _run_node(test_context, op2b, op2b.handle)
    assert session2b.briefing_bosses is None, 'boss 读空 → 清 None(防假真值)'
    # ③ 难度仅 None 写
    session3 = StrategySession()
    session3.enemy_difficulty = 3
    op3, session3, calls3 = _make_briefing(test_context, monkeypatch,
                                           mark_hit=True, difficulty=5,
                                           session=session3)
    _run_node(test_context, op3, op3.handle)
    assert calls3['diff_read'] == 0 and session3.enemy_difficulty == 3, (
        '难度已有值 → 不读不写(仅缺省写)')


# ==================== BOSS 简报:分流双向 + 判别单一源 ====================


def _make_boss(test_context, monkeypatch: pytest.MonkeyPatch, *,
               area_hit: bool, ocr_texts: list[str] | None = None):
    """BOSS 简报真类装配。桩面 = 横幅 area 锚/片段判别 OCR/空白区 center/
    点击记录器。返回 (op, clicks)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_boss_briefing as bb,
    )
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    op = bb.CwScreenBossBriefing(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(area_hit))
    monkeypatch.setattr(bb, 'read_ocr_texts',
                        lambda ctx, scr: list(ocr_texts or []))
    monkeypatch.setattr(bb, 'area_center',
                        lambda ctx, name, screen=None: SimpleNamespace(
                            x=960, y=540))
    clicks: list[str] = []
    monkeypatch.setattr(
        test_context, 'controller',
        SimpleNamespace(mouse_move=lambda *a, **k: None,
                        click=lambda p, **k: clicks.append('blank')),
        raising=False)
    monkeypatch.setattr(bb.time, 'sleep', lambda *_: None)
    return op, clicks


def test_boss_briefing_dispatch_both_ways(test_context, monkeypatch) -> None:
    """BOSS 简报分流双向(主门 (a) 本屏行):装两端口 → 横幅在 = 五段新
    路径 + 点空白 + success 交回;横幅已退 = observe 早退 success(交回外
    循环重判,零动作,仅 observe 段迹);不装端口 → 旧路径零段迹同行为。
    红 = 分流判据破坏或早退语义漂移。"""
    install_dispatch_stub_ports(monkeypatch)
    op, clicks = _make_boss(test_context, monkeypatch, area_hit=True)
    rs = _run_node(test_context, op, op.handle)
    assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act',
                                   'on_outcome'], (
        f'装端口须走五段新路径:{op._lifecycle_trace}')
    assert clicks == ['blank'], '横幅在 = 点空白恰一次'
    assert rs.is_success and '点空白已发' in (rs.status or ''), (
        f'交回外循环重判语义不变:{rs!r}')
    # 横幅已退:observe 早退 success(零动作)
    op_g, clicks_g = _make_boss(test_context, monkeypatch, area_hit=False,
                                ocr_texts=['点击空白处继续', '备战阶段'])
    rs_g = _run_node(test_context, op_g, op_g.handle)
    assert op_g._lifecycle_trace == ['observe'], (
        f'横幅已退 = 仅 observe 段迹(早退交回):{op_g._lifecycle_trace}')
    assert clicks_g == [], '横幅已退 = 零动作'
    assert rs_g.is_success and '推进完成' in (rs_g.status or ''), (
        f'早退 success 交回外循环重判:{rs_g!r}')
    # 不装端口:旧路径零段迹(生产形态)
    _uninstall_ports(monkeypatch)
    op_o, clicks_o = _make_boss(test_context, monkeypatch, area_hit=True)
    rs_o = _run_node(test_context, op_o, op_o.handle)
    assert op_o._lifecycle_trace == [], f'旧路径不得写段迹:{op_o._lifecycle_trace}'
    assert clicks_o == ['blank'] and rs_o.is_success, '旧路径行为保形'


def test_boss_briefing_misread_takeover_new_path(test_context,
                                                 monkeypatch) -> None:
    """误读帧(「强敌米」)新路径仍接管:area 锚 miss + 片段判别命中 →
    observe 判横幅在 → 点空白路径(P4R3 锚加固语义,判别单一源消费同源)。
    红 = 转录把片段判别兜底写丢。"""
    install_dispatch_stub_ports(monkeypatch)
    op, clicks = _make_boss(test_context, monkeypatch, area_hit=False,
                            ocr_texts=['强敌米', '点击空白处继续',
                                       '云骑骁卫·彦卿'])
    rs = _run_node(test_context, op, op.handle)
    assert clicks == ['blank'], '误读帧仍走「横幅命中 → 点空白」路径'
    assert rs.is_success and '点空白已发' in (rs.status or '')
    assert op._lifecycle_trace[0] == 'observe'


def test_boss_discrimination_single_source_consumers_unchanged() -> None:
    """判别单一源消费面锁:`is_boss_briefing_texts` 消费点集合迁移前后不变
    (cw_loop 0q 排他 / cw_screen_battle_wait 完成白名单 / cw_screen_boss_
    briefing 模块定义);迁移只改宿主类,禁转录顺手复制判别逻辑(battle_wait
    源面无 token 表、无判别函数定义)。红 = 判别面被复制成第二源。"""
    from sr_od.application.currency_war.operations import cw_loop
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bw,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_boss_briefing as bb,
    )
    assert 'is_boss_briefing_texts' in inspect.getsource(cw_loop)
    bw_src = inspect.getsource(bw)
    assert bw_src.count('is_boss_briefing_texts') == 2, (
        'battle_wait 消费面 = import + 调用恰两处(白名单同源,零复制)')
    assert 'BOSS_BRIEFING_TOKENS' not in bw_src, (
        'token 表不得被复制进 battle_wait(判别单一源)')
    assert 'def is_boss_briefing_texts' not in bw_src
    bb_src = inspect.getsource(bb)
    assert 'BOSS_BRIEFING_TOKENS' in bb_src and \
        'def is_boss_briefing_texts' in bb_src, (
        '定义单一源仍在 boss_briefing 模块')


# ==================== 战斗等待:B2-③ 主门(在册行为锁走新路径)====================


def _make_bwait(test_context, monkeypatch: pytest.MonkeyPatch,
                hit_areas: frozenset, *, install: bool = True):
    """战斗等待真类装配(生产构造走 __init__;RunLoop 注入面 =
    SettlementState + config 桩同形)。桩面 = 画面门/OCR 原语/存图/光标/
    点击记录器;``ctx.ocr_service`` 桩恒空行(读图域不出单元)。"""
    from sr_od.application.currency_war.currency_war_config import (
        CurrencyWarConfig,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )
    if install:
        install_dispatch_stub_ports(monkeypatch)
    else:
        _uninstall_ports(monkeypatch)
    st = bwo.SettlementState(run_start_ts=time.monotonic(), is_new_match=True)
    op = bwo.CwScreenBattleWait(
        test_context, st,
        CurrencyWarConfig(test_context.current_instance_idx))
    monkeypatch.setattr(op, 'last_screenshot', None, raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: None)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area((s, a) in hit_areas))
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda *a, **k: _Area(True))
    monkeypatch.setattr(op, 'round_by_ocr', lambda *a, **k: _Area(False))
    monkeypatch.setattr(op, 'save_screenshot', lambda prefix=None: '')
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    monkeypatch.setattr(test_context, 'ocr_service',
                        SimpleNamespace(
                            get_ocr_result_list=lambda **kw: []),
                        raising=False)
    es = ExecState()
    monkeypatch.setattr(
        test_context, 'cw_match',
        SimpleNamespace(exec_state=es, session=StrategySession()),
        raising=False)
    monkeypatch.setattr(time, 'sleep', lambda *_: None)
    # op 框架首节点「检测游戏窗口」的假环境承接(execute() 驱动专用;
    # cw_harness._stub_window_check 同式:窗口检查直通成功)。
    monkeypatch.setattr(op, 'check_game_window',
                        lambda: op.round_success('窗口桩(假环境无窗口)'))
    return op, es


def test_battle_wait_execute_terminal_exit_new_path(test_context,
                                                    monkeypatch) -> None:
    """B2-③ 主门(经 ``execute()`` 走新路径):大厅终局锚命中 → observe 段
    早退 terminal_lobby(交整局退出收口),op 终态 success,段迹仅 observe。
    红 = 分流断线(execute 仍走旧路径)或出口语义漂移。"""
    install_dispatch_stub_ports(monkeypatch)
    op, _es = _make_bwait(
        test_context, monkeypatch,
        frozenset({('货币战争-大厅', '标识-创业指南')}))
    with fast_sleep():
        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)
    assert result.success and result.status == 'terminal_lobby', (
        f'终局出口语义不变(经 execute 走新路径):{result!r}')
    assert op._lifecycle_trace == ['observe'], (
        f'出口判定早退 = 仅 observe 段迹:{op._lifecycle_trace}')


def test_battle_wait_completion_exit_new_path(test_context,
                                              monkeypatch) -> None:
    """B2-③:完成白名单锚命中 → observe 段早退 back_to_loop(交回循环
    分发)。旧路径对照(不装端口)= 同出口零段迹(生产缺省保形)。"""
    op, _es = _make_bwait(
        test_context, monkeypatch,
        frozenset({('货币战争-备战', '备战标识-购买经验')}))
    rs = op.wait()
    assert rs.is_success and rs.status == 'back_to_loop'
    assert op._lifecycle_trace == ['observe']
    _uninstall_ports(monkeypatch)
    op_o, _es_o = _make_bwait(
        test_context, monkeypatch,
        frozenset({('货币战争-备战', '备战标识-购买经验')}), install=False)
    rs_o = op_o.wait()
    assert rs_o.is_success and rs_o.status == 'back_to_loop'
    assert op_o._lifecycle_trace == [], f'旧路径不得写段迹:{op_o._lifecycle_trace}'


def test_battle_wait_settlement_branch_order_and_defer_new_path(
        test_context, monkeypatch) -> None:
    """B2-③:结算分支新路径逐位——D-94 读点(结算观察半直写)先于「继续
    继续」点击(时序红线);C-1 新帧计数;defer 复位宿主 = exec_state;段迹
    五段(单轮 = observe..on_outcome + round_wait 驻留)。"""
    order: list[str] = []
    op, es = _make_bwait(
        test_context, monkeypatch,
        frozenset({('货币战争-结算', '按钮-继续挑战')}))

    def _rec(screen, telemetry_only=False):
        order.append('record')
        _rec.called = True

    _rec.called = False
    monkeypatch.setattr(op, '_record_round_outcome', _rec)
    _orig_click_area = op.round_by_find_and_click_area

    def _click_area(*a, **k):
        order.append('click')
        return _orig_click_area(*a, **k)

    monkeypatch.setattr(op, 'round_by_find_and_click_area', _click_area)
    es.defer_count = 2
    rs = op.wait()
    assert order == ['record', 'click'], (
        f'D-94 读点先于点击(时序红线,新路径同序):{order!r}')
    assert _rec.called
    assert es.defer_count == 0, '结算点 defer 复位(宿主 = cw_match.exec_state)'
    assert op._st.rounds_done == 1, 'C-1 新结算帧计数'
    assert op._st.settle_stay == 1, '停留计数继续执行到 round_wait'
    assert not rs.is_success and rs.result == OperationRoundResultEnum.WAIT, (
        '驻留轮 round_wait(等待语义不随路径变)')
    assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act',
                                   'on_outcome'], (
        f'单轮五段:{op._lifecycle_trace}')


def test_battle_wait_long_press_new_path(test_context, monkeypatch) -> None:
    """B2-③:M39 停留第 3 轮(点击未生效)→ 长按 (960,898) press_time=0.5
    兜底推进 + 停留计数归零(在册时序行为锁走新路径)。"""
    clicks: list = []
    op, _es = _make_bwait(
        test_context, monkeypatch,
        frozenset({('货币战争-结算', '按钮-继续挑战')}))
    monkeypatch.setattr(
        test_context, 'controller',
        SimpleNamespace(click=lambda pt, **kw: clicks.append((pt, kw)),
                        mouse_move=lambda *a, **k: None),
        raising=False)
    op.wait()
    op.wait()
    assert clicks == [], '停留 1-2 轮未达长按线'
    op.wait()
    assert len(clicks) == 1, '第 3 轮恰触发长按兜底'
    (point, kw), = clicks
    assert (point.x, point.y) == (960, 898)
    assert kw == {'press_time': 0.5}
    assert op._st.settle_stay == 0, '长按兜底后停留计数归零'


def test_battle_wait_unknown_bail_new_path(test_context, monkeypatch,
                                           tmp_path) -> None:
    """B2-③:未知帧达 UNKNOWN_BAIL_N(10)→ round_fail 交主循环兜底链 +
    flag 留证(get_project_root 重定向 tmp_path,留证不落真实 .debug)。
    新路径逐轮 = observe 门双 miss → 决策循环分支链 miss → 计数。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )
    monkeypatch.setattr(bwo, 'get_project_root', lambda: tmp_path)
    op, _es = _make_bwait(test_context, monkeypatch, frozenset())
    res = None
    for _ in range(bwo.CwScreenBattleWait.UNKNOWN_BAIL_N):
        res = op.wait()
    assert res is not None and res.result == OperationRoundResultEnum.FAIL
    assert (tmp_path / '.debug' / 'temp' / 'currency_war'
            / 'battle_wait_bail.flag').exists()
