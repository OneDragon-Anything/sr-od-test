"""统一观察架构·五相位屏迁移锁(余项收口阶段一)。

设计正本 = docs/develop/sr_od/application/currency_war/flow/统一观察架构-画面op基类设计.md
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

锁的语义(测试纪律 7 自检;出处 = landing 阶段一判据;行为锁单驱动
生产路径):

- **重入裁决归属锁**(单一定谳;锁形 = 裁决×门组合行为锁
  ``test_reentry_arbitration_flag_gate_combination``):投资环境/投资策略/
  简报已迁移两 node 形态(迭代 2026-09-18-screen-op-flat-report),
  「已发」旗标裁决住决策动作 node 顶部(直驱 act 承重);BOSS 简报
  (两 node 形态)无裁决旗标,横幅退场裁决 = 外循环重派后的下一次
  入口门;战斗等待无裁决旗标。
  红 = 裁决被转录进观察 node。
- **观察上报接线锁**(两 node 形态屏):观察 node 稳定帧一次读
  → report 经屏文件落容器(容器终值)+ obs 挂实例属性;投资策略入口锚
  复探窗(ADR-0529 有界自愈)语义逐位(复探窗内自愈、超窗 round_retry
  消耗观察 node 预算)。
- **刷新终结交回锁**(投资策略,两 node 形态):建议刷新 → 闸 1 槽计数
  现读 >0 → 点钮恰一次 → 终结交回 round_success(交回外循环重进 = 入口
  重建);刷新计数写端随画面 op 基类退役(记账归动作 op 会话承接),
  闸 2 容器计数读端原样。
- **写入流对拍锁**:``active_env`` 选卡时点写(值/写时点 = 点卡前,
  决策面留守)、``active_strategies`` 重入裁决出口 append(值/时点)、
  简报三字段容器写(词缀幂等辖「读+采」/boss 恒覆写/难度仅 None 写)
  逐位;结算观察半直写(D-94 时序)经战斗等待在册行为锁的轨迹断言承载。
- **判别单一源消费面锁**:`is_boss_briefing_texts` 消费点集合迁移前后不变
  (cw_loop / cw_screen_battle_wait / cw_screen_boss_briefing;防转录顺手
  复制判别逻辑)。

驱动方式 = 真类实例(构造走 __init__)+ 读链/点击链桩化,节点函数直驱
(run_node 外壳);战斗等待 = 生产缺省形态(行为锁
主驱动)。
"""
from __future__ import annotations

import time
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
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    normalize_invest_name,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickInvestParam,
    CwActionRefreshInvestCardsParam,
)

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)

_RETRY_RS = OperationRoundResult(OperationRoundResultEnum.RETRY, status='stub-confirm')


# ==================== 迁移结构锁 + 重入裁决归属锁 ====================


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


# (原 test_phase_ops_inherit_base「五 op 均为 CwScreenOpBase 子类」结构与
#  `_PHASE_OPS` 常量删:继承结构 = 静态形状,类体不迁移行为不变,红时答不
#  出哪个运行行为坏了;结构面归 review 与代码规范。)


def test_reentry_arbitration_flag_gate_combination(test_context,
                                                   monkeypatch) -> None:
    """重入裁决×门组合行为锁(投资环境/投资策略/简报均为两 node 形态
    (迭代 2026-09-18-screen-op-flat-report):「已发」旗标裁决住决策动作
    node 顶部,直驱 act 承重;BOSS 简报/战斗等待无裁决旗标):
    - 投资环境(裁决先行式两态):落地轮(锚已退 = overlay 已关)+
      旗标在位 → 裁决出口 success + 零动作 + 旗标保持已消费态不复活;
      门命中轮(锚仍在 = 未落地)+ 旗标在位 → 裁决不误判完成,确认链
      重发、旗标经确认体重置;
    - 投资策略:门命中(入口锚在)+ 旗标在位 → 裁决不触发,在屏轮零
      append(append 归裁决出口,出口面由
      test_invest_strategy_active_strategies_appended_at_reentry_exit
      承重);
    - 简报(两 node 形态):落地轮(pending 在位 + 标识已退)→ 裁决
      出口 success,读链不发生(裁决住 act 顶部,act 零读链);门命中轮
      (标识仍在)→ 裁决不误判完成,「下一步」重发、旗标经置位体重置。
    红 = 裁决出口语义漂移(门命中误判完成 / 落地轮旗标复活 / 裁决移位)。"""
    # 投资环境·落地轮:pending 在位 + 锚已退 → 裁决出口 success,零动作
    op_land, _m, _s, _d = _make_env(test_context, monkeypatch, in_screen=False)
    op_land._confirm_pending = '彩虹时代'
    rs_land = _run_node(test_context, op_land, op_land.act)
    assert rs_land.is_success and '重入观察裁决' in (rs_land.status or ''), (
        f'落地轮裁决出口 success 交回:{rs_land!r}')
    assert op_land._confirm_pending is None, (
        '裁决先行消费旗标,落地轮不残留待裁决旗标')
    # 投资环境·门命中轮:pending 在位 + 锚仍在 → 不误判完成,确认链重发
    events: list = []
    op_hit, _m2, _s2, _d2 = _make_env(test_context, monkeypatch, in_screen=True,
                                      opts=[('追击概念股', 460)], events=events)
    op_hit._confirm_pending = '追击概念股'
    rs_hit = _run_node(test_context, op_hit, op_hit.act)
    assert rs_hit.result == OperationRoundResultEnum.WAIT, (
        f'锚在 = 确认未落地,裁决不误判完成(round_wait 机械交回):{rs_hit!r}')
    assert any(e[0] == 'card_click' for e in events), (
        f'裁决消费后正常流程重发(选卡点击在案):{events!r}')
    assert op_hit._confirm_pending is None, (
        '旗标经确认体重置(非裁决出口);桩轮无候选 → 选中名 ? → 不置名 '
        '(载荷语义:值 = 选中名,银狼闭环双屏分流):'
        f'{events!r}')
    # 投资策略·门命中轮:pending 在位 + 入口锚在 → 裁决不触发,在屏轮
    # 零 append(append 只归裁决出口)
    book = _FrameBook([object()])
    book.options[id(book.frames[0])] = _opts_of(['赌神·银', '恢复生机',
                                                 '气氛组'])
    picks = [CwActionPickInvestParam(idx=1, reason='stub')]
    op_st, _m3, session_st, clicks_st, _dc, disp_st = _make_strategy(
        test_context, monkeypatch, book, picks)
    op_st._confirm_pending = '白银投资'
    _run_node(test_context, op_st, op_st.observe)
    rs_st = _run_node(test_context, op_st, op_st.act)
    assert rs_st.result == OperationRoundResultEnum.WAIT, (
        f'在屏轮确认链机械交回(round_wait):{rs_st!r}')
    assert len(disp_st) == 1, (
        f'裁决不触发,选卡+确认链重发恰一次派发:{disp_st!r}')
    assert op_st._confirm_pending == '恢复生机', (
        f'旗标经确认体重置:{clicks_st!r}')
    # 终态契约 §B:session.active_strategies 退役——门命中轮零 append 改由
    # 容器侧断言(持卡单一源 = gs.active_strategies)。
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_arch,
    )
    assert (_gso_arch(session_st).active_strategies.value or []) == [], (
        '门命中轮裁决不触发,零 append(出口面归重入锁)')
    # 简报·落地轮:pending 在位 + 标识已退 → 裁决出口 success,读链不发生
    #(裁决住决策动作 node 顶部,act 零读链)
    op_b_land, session_b, calls_b = _make_briefing(
        test_context, monkeypatch, mark_hit=False)
    op_b_land._click_pending = True
    rs_b = _run_node(test_context, op_b_land, op_b_land.act)
    assert rs_b.is_success and '已离开简报' in (rs_b.status or ''), (
        f'落地轮裁决出口 success 交回:{rs_b!r}')
    assert op_b_land._click_pending is False, (
        '裁决先行消费旗标,落地轮不残留')
    assert calls_b['affix_read'] == 0 and calls_b['boss_read'] == 0, (
        f'裁决出口先行,读链不发生(act 零读链):{calls_b!r}')
    # 简报·门命中轮:pending 在位 + 标识仍在 → 「下一步」重发,旗标经
    # 置位体重置
    op_b_hit, _s_b2, _c_b2 = _make_briefing(test_context, monkeypatch,
                                            mark_hit=True, affixes=[('火弱点',
                                                                     None)],
                                            bosses=['碎星王虫'], difficulty=5)
    op_b_hit._click_pending = True
    rs_bh = _run_node(test_context, op_b_hit, op_b_hit.act)
    assert not rs_bh.is_success and '重入观察裁决' in (rs_bh.status or ''), (
        f'标识在 = 点击未落地,重点非完成:{rs_bh!r}')
    assert op_b_hit._click_pending is True, (
        '旗标经「下一步」置位体重置')


# ==================== 投资环境:写入流对拍 ====================


def _make_env(test_context, monkeypatch: pytest.MonkeyPatch, *,
              in_screen: bool, opts: list | None = None, pick_idx: int = 0,
              events: list | None = None):
    """投资环境真类装配(生产构造走 __init__ = 适配器位/注册表在位)。

    桩面 = 画面门/截屏/候选读/策略器/计数读 + 派发动作 op 桩(pick-op-unify
    批起选卡+确认机械链迁入 ``CwActionPickInvestOp``,本文件桩派发捕获
    (param, env) 断言决策半产物与写端时序;机械链行为锁 =
    test_cw_unified_action_4 投资 op 锁)。派发时点快照 ``active_env``
    现值(选卡时点写对拍载体 = 写在点卡链派发前)。
    (台账写点②桩面已随该方法退役删除——链观察落地批:环境改型由返回
    备战后的入口观察链读承接,op 层零自读。)"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_env as iem,
    )

    session = StrategySession()
    strategy = SimpleNamespace(
        decide_invest_env=lambda: CwActionPickInvestParam(idx=pick_idx, reason='stub'))
    match = SimpleNamespace(strategy=strategy, session=session)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = iem.CwScreenInvestEnv(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_screen))
    monkeypatch.setattr(op, 'screenshot', lambda: _FRAME)
    monkeypatch.setattr(op, '_read_options',
                        lambda screen: list(opts or []))
    monkeypatch.setattr(iem, 'read_invest_refresh_counts',
                        lambda ctx, scr, kind: [])

    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            if events is not None:
                events.append(('card_click',
                               (self.env.target.x, self.env.target.y)))
                events.append(('active_env_at_dispatch',
                               game_state_of(session).active_env.value))
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    monkeypatch.setattr(iem.time, 'sleep', lambda *_: None)
    return op, match, session, dispatches


# (原 test_invest_env_dispatch_and_gate「投资环境分流双向 + 段迹形态」删:
#  装两端口走五段新路径的分流/段迹面随并存窗收口整删(生产端口恒 None);
#  其唯一跨路径幸存断言「确认发出置 pending」并入下方选卡时点写锁;
#  离屏门 fail 早退语义由简报/BOSS 简报在册行为锁同形承重。)


def test_invest_env_observe_gate_and_report(test_context,
                                            monkeypatch) -> None:
    """投资环境观察 node 锁(两 node 形态):入口门 miss = round_fail 早退
    (现役文案,obs 不装载);门 hit → 稳定帧候选一次读 → report 落容器
    ``invest_env_opts``(容器终值)+ obs 挂实例属性。红 = 门失效 / 接线
    断流 / 容器终值漂移。"""
    opts = [('追击概念股', 460), ('彩虹时代', 960), ('头彩', 1460)]
    op_off, _m0, _s0, _d0 = _make_env(test_context, monkeypatch, in_screen=False,
                                      opts=opts)
    rs_off = _run_node(test_context, op_off, op_off.observe)
    assert not rs_off.is_success and '非投资环境屏' in (rs_off.status or ''), (
        f'门 miss 文案沿用现役:{rs_off!r}')
    assert op_off._obs is None, '门早退不装载 obs'
    op, _m, session, _disp = _make_env(test_context, monkeypatch, in_screen=True,
                                       opts=opts)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    assert game_state_of(session).invest_env_opts.value == [
        n for n, _x in opts], (
        f'report 落容器(容器终值):'
        f'{game_state_of(session).invest_env_opts.value!r}')
    assert op._obs is not None and op._obs.options == opts, 'obs 挂实例属性'


def test_invest_env_active_env_written_at_pick_time(test_context,
                                                    monkeypatch) -> None:
    """写入流对拍(§9.1-F2 主门 (b)):``active_env`` 选卡时点写——写时点 =
    点卡链派发**前**(派发时点快照已见新值,pick-op-unify 批起点卡链
    迁入动作 op,对拍载体 = 派发时点快照)、值 = 决策选中名(决策面留守,
    ADR-0598 投资两屏各自实证语义);确认发出置 pending(落地归重入裁决)。
    红 = 写时点后移(落派发后)、值漂移或确认链置位断线。"""
    events: list = []
    opts = [('追击概念股', 460), ('彩虹时代', 960), ('头彩', 1460)]
    op, _match, session, dispatches = _make_env(test_context, monkeypatch,
                                                in_screen=True,
                                                opts=opts, pick_idx=1,
                                                events=events)
    _run_node(test_context, op, op.observe)
    rs = _run_node(test_context, op, op.act)
    assert ('active_env_at_dispatch', '彩虹时代') in events, (
        f'active_env 须写在点卡链派发前(选卡时点语义):{events!r}')
    assert game_state_of(session).active_env.value == '彩虹时代', (
        '值 = 决策选中名(produced_by 面 = CwScreenInvestEnv,见豁免留守锁'
        '源形态断言)')
    assert len(dispatches) == 1 and dispatches[0].param.idx == 1, (
        f'选卡+确认链恰一次派发,param 携真实 idx:{dispatches!r}')
    assert op._confirm_pending == '彩虹时代', (
        '确认已发 → pending 置位携选中名(重入裁决承载;银狼闭环双屏分流'
        '载荷 = 落地相效果分派输入)')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'确认链机械交回 round_wait(循环推进):{rs!r}')


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

    桩面 = 入口锚/截屏/候选读/计数读/刷新点击 + 派发动作 op 桩
    (pick-op-unify 批起选卡+确认机械链迁入 ``CwActionPickInvestOp``;
    刷新臂 ``safe_click`` 留守画面 op,经桩记录)。``_ensure_entry_screen``
    方法级桩(复探窗语义归 ADR-0529 既有锁,本文件不辖)。返回
    ``(op, match, session, clicks, decide_calls, dispatches)``。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy as ism,
    )

    session = StrategySession()
    decide_calls: list[list[str]] = []

    def _decide():
        decide_calls.append(['stub'])   # 零参口后候选自容器槽(handler 写槽)
        return picks.pop(0) if picks else CwActionPickInvestParam(
            idx=0, reason='stub-exhausted')

    match = SimpleNamespace(strategy=SimpleNamespace(decide_invest_strategy=_decide),
                            session=session)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
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

    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    monkeypatch.setattr(ism.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(op, '_interruptible_sleep', lambda s: None)
    return op, match, session, clicks, decide_calls, dispatches


_OPT_XS = (460, 960, 1460)
_CNT_Y = 855
_DX = -88   # = CwScreenInvestStrategy._REFRESH_BTN_DX(常量单一源直读)


def _opts_of(names: list[str]) -> list[tuple[str, int, int]]:
    return [(n, _OPT_XS[i], 490) for i, n in enumerate(names)]


# (原 test_invest_strategy_dispatch_new_path 删:在屏轮断言面与
#  test_reentry_arbitration_flag_gate_combination 的 strategy 门命中腿
#  逐项重叠;独有段迹/单决策断言已并入该锁。)


def test_invest_strategy_active_strategies_appended_at_reentry_exit(
        test_context, monkeypatch) -> None:
    """写入流对拍(主门 (b)):``active_strategies`` append 时点 = 重入裁决
    出口(入口锚不在 = overlay 已关 = 选卡落地,决策动作 node 顶部)——
    值 = 待裁决选卡名 + 去重;GameState 写端(list 本体)同点。
    红 = append 时点前移(幻影卡回潮,ADR-0598)。"""
    op = _phase_mod('cw_screen_invest_strategy').CwScreenInvestStrategy(
        test_context)
    session = StrategySession()
    match = SimpleNamespace(strategy=SimpleNamespace(), session=session)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, '_entry_anchor_hit', lambda screen: False)
    op._confirm_pending = '白银投资'
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '已确认(重入观察裁决)' in (rs.status or ''), (
        f'裁决出口 success 交回:{rs!r}')
    assert game_state_of(session).active_strategies.value == ['白银投资'], (
        'append 值 = 待裁决选卡名(终态契约 §B:容器单源)')
    # 去重:同卡二次确认不重复入列
    op._confirm_pending = '白银投资'
    _run_node(test_context, op, op.act)
    assert game_state_of(session).active_strategies.value == ['白银投资'], (
        '去重防重复入列')


# (原 test_strategy_refresh_emission_wired_to_registry 删:注册表取证型
#  断言——登记件缺席时发射行为半必红,取证面零独立判别力,登记形状重构
#  = 误红源;行为半由 test_strategy_refresh_emission_semantics 承重。


def test_strategy_refresh_terminal_handback(test_context, monkeypatch) -> None:
    """逐卡刷新终结交回锁(两 node 形态):建议刷新 → 闸 1 槽计数现读 >0 →
    点钮恰一次(文本锚定)→ 终结交回 = round_success(op 结束,交回外循环
    重进 = 入口重建,重进后重观察重决策;本访问零比对零重决策——刷后不重读
    不比对不重决策)。观察轮 report 落容器 ``invest_strategy_opts`` 接线随锁
    (容器终值)。刷新计数写端随画面 op 基类退役(记账归动作 op 会话承接,
    本 op 不写计数——容器计数断言不设,闸 2 读端由下锁承重)。
    红 = 刷新点击丢失 / 循环内重读重决策回潮 / 终结交回改轮询 / 接线断流。"""
    names = ['赌神·银', '恢复生机', '气氛组']
    book = _FrameBook([object()])
    book.options[id(book.frames[0])] = _opts_of(names)
    book.counts[id(book.frames[0])] = [(1, 477, _CNT_Y), (1, 975, _CNT_Y),
                                       (1, 1474, _CNT_Y)]
    picks = [CwActionRefreshInvestCardsParam(slots=(0,), reason='stub+refresh')]
    op, _match, session, clicks, decide_calls, _disp = _make_strategy(
        test_context, monkeypatch, book, picks)
    rs_obs = _run_node(test_context, op, op.observe)
    assert rs_obs.is_success, f'前置:观察 success:{rs_obs!r}'
    assert game_state_of(session).invest_strategy_opts.value == names, (
        f'观察 report 落容器(容器终值):'
        f'{game_state_of(session).invest_strategy_opts.value!r}')
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success, (
        f'终结交回 = round_success(交回外循环重进重观察):{rs!r}')
    assert len(decide_calls) == 1, (
        f'刷后终结交回,本访问单决策(重决策归重进):{decide_calls!r}')
    refresh_clicks = [c for c in clicks if c.y == _CNT_Y]
    assert [(c.x, c.y) for c in refresh_clicks] == [(477 + _DX, _CNT_Y)], (
        f'刷新点击恰一次(槽 0 文本锚定):{refresh_clicks!r}')


def test_strategy_refresh_gate2_reads_container_count(
        test_context, monkeypatch) -> None:
    """闸 2 读源锁(防重入账 = 容器 ``strategy_refresh_used`` 逐卡计数,
    旧执行侧 visit 级槽集已退役):
    - 容器计数在位(键 = normalize_invest_name 规范卡名,闸 1 计数现读
      仍在)→ 闸 2 拦截:零刷新点击、拦截轮不发射不计数(无双计);
    - 点击面仅剩选卡/确认两击 = 闸后流程照常走到选卡(闸拦 ≠ 流程断)。
    红 = 闸 2 仍读已退役槽集 / 容器计数不拦 / 拦截轮误发射。"""
    names = ['赌神·银', '恢复生机', '气氛组']
    book = _FrameBook([object()])
    book.options[id(book.frames[0])] = _opts_of(names)
    book.counts[id(book.frames[0])] = [(1, 477, _CNT_Y), (1, 975, _CNT_Y),
                                       (1, 1474, _CNT_Y)]
    picks = [CwActionRefreshInvestCardsParam(slots=(0,), reason='stub+refresh')]
    op, _match, session, clicks, _dc, disp = _make_strategy(
        test_context, monkeypatch, book, picks)
    _k = normalize_invest_name(names[0])
    _gs = game_state_of(session)
    _gs.write_logic(_gs.strategy_refresh_used, {_k: 1},
                    produced_by='CwScreenInvestStrategy',
                    sig=ChannelSig(family='logic_action',
                                   actor='CwScreenInvestStrategy',
                                   mode='compute'))
    _run_node(test_context, op, op.observe)
    rs = _run_node(test_context, op, op.act)
    refresh_clicks = [c for c in clicks if c.y == _CNT_Y]
    assert refresh_clicks == [], (
        f'容器计数在位 → 闸 2 拦截,零刷新点击:{clicks!r}')
    assert len(disp) == 1, (
        f'闸拦 ≠ 流程断:选卡+确认链照常一次派发:{disp!r}')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'闸拦轮照常确认链机械交回(round_wait):{rs!r}')
    assert _gs.strategy_refresh_used.value == {_k: 1}, (
        f'拦截轮不发射不计数(写端出辖 + 无双计):{_gs.strategy_refresh_used.value!r}')


def test_invest_strategy_observe_reprobe_and_report(test_context,
                                                    monkeypatch) -> None:
    """投资策略观察 node 锁(两 node 形态):入口锚复探窗(ADR-0529 有界
    自愈)语义逐位——复探窗内自愈、超窗 = round_retry(现役文案,消耗观察
    node 预算的既有 retry 面);在窗 → 候选一次读 → report 落容器
    ``invest_strategy_opts``(容器终值)+ obs 挂实例属性。
    红 = 超窗改 fail(炸 op 触发哨兵)/ 复探窗丢失 / 接线断流。"""
    names = ['赌神·银', '恢复生机', '气氛组']
    # ① 超窗(entry_ok False)→ round_retry 现役文案,obs 不装载
    book_off = _FrameBook([])
    op_off, _m0, _s0, _c0, _d0, _disp0 = _make_strategy(
        test_context, monkeypatch, book_off, [], entry_ok=False)
    rs_off = _run_node(test_context, op_off, op_off.observe)
    assert not rs_off.is_success \
        and '投资策略屏未稳定,复探超窗重试' in (rs_off.status or ''), (
        f'超窗 retry 文案沿用现役:{rs_off!r}')
    assert op_off._obs is None, '超窗不装载 obs'
    # ② 在窗 → report 落容器 + obs 装载
    book = _FrameBook([object()])
    book.options[id(book.frames[0])] = _opts_of(names)
    op, _m, session, _clicks, _dc, _disp = _make_strategy(
        test_context, monkeypatch, book, [])
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    assert game_state_of(session).invest_strategy_opts.value == names, (
        f'report 落容器(容器终值):'
        f'{game_state_of(session).invest_strategy_opts.value!r}')
    assert op._obs is not None and op._obs.options == _opts_of(names), (
        'obs 挂实例属性')


# ==================== 豁免留守锁(§2.2/§6.5-6)====================


# (三审整删)原 test_write_flow_exempt_surfaces_stay_inline「豁免
# 留守锁」(getsource ×6:注册表接线恰一处/钩子体与豁免面字面在场/环境屏
# 零登记件)——源码扫描形态(README 禁止清单,红时是文本变了,答不出哪个
# 运行行为坏了);豁免面纪律归 review 与代码规范。豁免面的行为面
# (chosen 写端不入注册表收编)由 event_screens 同名行为锁辖。


# ==================== 简报:三字段写语义 ====================


def _make_briefing(test_context, monkeypatch: pytest.MonkeyPatch, *,
                   mark_hit: bool = True, bosses: list | None = None,
                   affixes: list | None = None, difficulty: int | None = 5,
                   session: StrategySession | None = None):
    """简报真类装配(两 node 形态)。桩面 = 画面门/「下一步」点击/三读链;
    读链桩按记录器计数(幂等守卫辖「读+采」断言载体)。返回 (op, session, calls)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_briefing as bm,
    )

    session = session or StrategySession()
    match = SimpleNamespace(session=session)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
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
    monkeypatch.setattr(bm, 'clean_boss_names_by_lcs', lambda gs: gs)
    monkeypatch.setattr(bm, 'read_briefing_enemy_difficulty',
                        lambda ctx, scr: (calls.__setitem__(
                            'diff_read', calls['diff_read'] + 1) or difficulty))
    monkeypatch.setattr(bm.CwScreenBriefing, '_collect_affix_effects',
                        lambda self, aff: (calls.__setitem__(
                            'affix_collect', calls['affix_collect'] + 1) or {}))
    return op, session, calls


# (原 test_briefing_dispatch_and_session_writes「简报分流双向」删:装两
#  端口走五段新路径的分流/段迹面随并存窗收口整删;其跨路径幸存断言
#  (「下一步」发出置 pending / 标识 miss 门 fail 早退零读链)分别由
#  test_reentry_arbitration_flag_gate_combination 的简报两腿与三字段锁
#  的幂等守卫腿承重。)


def test_briefing_observe_gate_and_report(test_context, monkeypatch) -> None:
    """简报观察 node 锁(两 node 形态):入口门 miss = round_fail 早退
    (现役文案,obs 不装载零读链);门 hit → 三读数一次读 → report 落
    容器(三字段容器终值)+ obs 挂实例属性;「下一步」点击不在观察轮
    (归决策动作 node,点击桩零命中断言)。
    红 = 门失效 / 接线断流 / 容器终值漂移 / 观察轮误点击。"""
    # ① 门 miss → fail 早退,obs 不装载零读链
    op_off, _s0, calls_off = _make_briefing(test_context, monkeypatch,
                                            mark_hit=False,
                                            affixes=[('火弱点', None)],
                                            bosses=['碎星王虫'])
    rs_off = _run_node(test_context, op_off, op_off.observe)
    assert not rs_off.is_success and '非简报屏' in (rs_off.status or ''), (
        f'门 miss 文案沿用现役:{rs_off!r}')
    assert op_off._obs is None, '门早退不装载 obs'
    assert calls_off['affix_read'] == 0 and calls_off['boss_read'] == 0, (
        f'门早退零读链:{calls_off!r}')
    # ② 门 hit → 三读数一次读 → report 落容器 + obs 挂实例属性
    op, session, calls = _make_briefing(test_context, monkeypatch,
                                        mark_hit=True,
                                        affixes=[('火弱点', None)],
                                        bosses=['碎星王虫'], difficulty=5)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    _gs = game_state_of(session)
    assert _gs.enemy_affixes.value == ['火弱点'], (
        f'词缀经 report 落容器:{_gs.enemy_affixes.value!r}')
    assert _gs.plane_bosses.value == ['碎星王虫'], (
        f'boss 经 report 落容器:{_gs.plane_bosses.value!r}')
    assert _gs.enemy_difficulty.value == 5, (
        f'难度经 report 落容器:{_gs.enemy_difficulty.value!r}')
    assert op._obs is not None and op._obs.enemy_affixes == ['火弱点'], (
        'obs 挂实例属性')
    assert calls['diff_read'] == 1, '难度容器缺省 → 读一次(仅缺省读)'


def test_briefing_session_write_semantics_three_fields(test_context,
                                                       monkeypatch) -> None:
    """写入流对拍:简报三字段三种写语义逐字——①词缀幂等守卫辖「读+采」
    (容器非空 → 跳过读与点采,观察侧读门);②boss 恒覆写(不做已存
    跳过,防跨局残留;读空 → 清 None);③敌人难度仅 None 时写(容器
    已有不读不写)。单驱动观察 node(读侧住观察 node,写闸住 report 屏
    文件,report 函数级闸面由 test_cw_screen_report_ports 承重,本锁辖
    op 侧读门接线)。
    红 = 守卫辖面漂移(如幂等只辖读不辖采)或覆写语义丢失。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig as _cs_t,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_t,
    )

    def _seed(session, field, value):
        _gso_t(session).write_logic(
            getattr(_gso_t(session), field), value,
            produced_by='test',
            sig=_cs_t(family='logic_action', actor='CwLoop',
                      screen='', mode='compute'))

    # ① 词缀幂等守卫辖「读+采」
    session = StrategySession()
    _seed(session, 'enemy_affixes', ['已有词缀'])
    op, session, calls = _make_briefing(test_context, monkeypatch,
                                        mark_hit=True, affixes=['新词缀'],
                                        bosses=['碎星王虫'], session=session)
    _run_node(test_context, op, op.observe)
    assert calls['affix_read'] == 0 and calls['affix_collect'] == 0, (
        f'容器已有词缀 → 跳过读与点采(幂等辖「读+采」):{calls!r}')
    assert _gso_t(session).enemy_affixes.value == ['已有词缀'], '幂等轮不覆写词缀'
    assert _gso_t(session).plane_bosses.value == ['碎星王虫'], 'boss 幂等豁免(恒覆写)照写'
    # ② boss 恒覆写:残留 → 本局真值;读空 → 清 None
    session2 = StrategySession()
    _seed(session2, 'plane_bosses', ['上一局残留'])
    op2, session2, _c2 = _make_briefing(test_context, monkeypatch,
                                        mark_hit=True, bosses=['碎星王虫'],
                                        session=session2)
    _run_node(test_context, op2, op2.observe)
    assert _gso_t(session2).plane_bosses.value == ['碎星王虫'], 'boss 恒覆写防跨局残留'
    op2b, session2b, _c2b = _make_briefing(test_context, monkeypatch,
                                           mark_hit=True, bosses=[],
                                           session=StrategySession())
    _seed(session2b, 'plane_bosses', ['上一局残留'])
    _run_node(test_context, op2b, op2b.observe)
    assert _gso_t(session2b).plane_bosses.value is None, 'boss 读空 → 清 None(防假真值)'
    # ③ 难度仅 None 写(容器已有不读不写)
    session3 = StrategySession()
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig as _cs3,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso3,
    )
    _gso3(session3).write_logic(
        _gso3(session3).enemy_difficulty, 3,
        produced_by='test',
        sig=_cs3(family='logic_action', actor='CwLoop',
                 screen='', mode='compute'))
    op3, session3, calls3 = _make_briefing(test_context, monkeypatch,
                                           mark_hit=True, difficulty=5,
                                           session=session3)
    _run_node(test_context, op3, op3.observe)
    assert calls3['diff_read'] == 0 and _gso3(
        session3).enemy_difficulty.value == 3, (
        '难度已有值 → 不读不写(仅缺省写)')


# ==================== BOSS 简报:误读接管(生产路径)====================


def _make_boss(test_context, monkeypatch: pytest.MonkeyPatch, *,
               area_hit: bool, ocr_texts: list[str] | None = None):
    """BOSS 简报真类装配(两 node 形态)。桩面 = 横幅 area 锚/片段判别 OCR/
    空白区 center/点击记录器。返回 (op, clicks)。"""
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


# (原 test_boss_briefing_dispatch_both_ways「BOSS 简报分流双向」删:装两
#  端口走五段新路径的分流/段迹面随并存窗收口整删;其跨路径幸存断言
#  (横幅在 = 点空白 + success 交回 / 横幅已退 = 零动作早退)由下方误读
#  接管锁与观察门锁同形承重。)


def test_boss_briefing_misread_takeover(test_context, monkeypatch) -> None:
    """误读帧(「强敌米」)两 node 形态仍接管:area 锚 miss + 片段判别命中 →
    观察判横幅在(obs 装载)→ act 点空白路径(P4R3 锚加固语义,判别单一源
    消费同源)。红 = 迁移把片段判别兜底写丢 / 点空白动作断流。"""
    op, clicks = _make_boss(test_context, monkeypatch, area_hit=False,
                            ocr_texts=['强敌米', '点击空白处继续',
                                       '云骑骁卫·彦卿'])
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success and op._obs is not None and op._obs.on_screen is True, (
        f'误读帧观察判横幅在(obs 装载):{rs!r} {op._obs!r}')
    rs2 = _run_node(test_context, op, op.act)
    assert clicks == ['blank'], '误读帧仍走「横幅命中 → 点空白」路径'
    assert rs2.is_success and '点空白已发' in (rs2.status or '')


def test_boss_briefing_observe_gate_and_placeholder_report(
        test_context, monkeypatch) -> None:
    """BOSS 简报观察 node 锁(两 node 形态):横幅已退(area 锚 miss +
    片段判别 miss)→ 早退 success 交回外循环重判(零点击,obs 不装载);
    横幅在 → obs 装载 + 占位 report 接线恰一次(match/gs 在场;本屏现役
    零容器写点,接口为统一形态占位)。
    红 = 门语义反转 / 接线断流。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_boss_briefing as bb,
    )
    # ① 横幅已退 → success 交回,零点击
    op_gone, clicks_gone = _make_boss(test_context, monkeypatch,
                                      area_hit=False, ocr_texts=[])
    rs_gone = _run_node(test_context, op_gone, op_gone.observe)
    assert rs_gone.is_success and '推进完成' in (rs_gone.status or ''), (
        f'横幅已退早退语义:{rs_gone!r}')
    assert clicks_gone == [] and op_gone._obs is None, (
        f'早退轮零动作零 obs:{clicks_gone!r} {op_gone._obs!r}')
    # ② 横幅在 → obs 装载 + 占位 report 恰一次
    op, _clicks = _make_boss(test_context, monkeypatch, area_hit=True,
                             ocr_texts=[])
    _reports: list = []
    monkeypatch.setattr(bb, 'report_screen_boss_briefing_obs',
                        lambda gs, obs: _reports.append(obs))
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=SimpleNamespace(), gs=object()),
                        raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    assert op._obs is not None and op._obs.on_screen is True, 'obs 挂实例属性'
    assert len(_reports) == 1 and _reports[0] is op._obs, (
        f'占位 report 接线恰一次(统一形态调用):{_reports!r}')


# (三审整删)原 test_boss_discrimination_single_source_consumers_
# unchanged「判别单一源消费面锁」(getsource ×3:消费点计数/import 复制面/
# token 表扩散断言;且 import 在飞互斥面 cw_loop)——源码扫描形态(README
# 禁止清单);「判别逻辑禁复制成第二源」防线归 review 与代码规范。


# ==================== 战斗等待:B2-③ 主门(在册行为锁·生产路径)====


def _make_bwait(test_context, monkeypatch: pytest.MonkeyPatch,
                hit_areas: frozenset):
    """战斗等待真类装配(生产构造走 __init__;RunLoop 注入面 =
    SettlementState + config 桩同形)。桩面 = 画面门/OCR 原语/存图/光标/
    点击记录器;``ctx.ocr_service`` 桩恒空行(读图域不出单元)。
    驱动 = 单路径(wait() 节点直驱;装配点分流随基类退役,本屏为
    驻留状态机单 node 形态)。"""
    from sr_od.application.currency_war.currency_war_config import (
        CurrencyWarConfig,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )
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
    monkeypatch.setattr(
        test_context, 'cw_match',
        SimpleNamespace(session=StrategySession()),
        raising=False)
    monkeypatch.setattr(time, 'sleep', lambda *_: None)
    # op 框架首节点「检测游戏窗口」的假环境承接(execute() 驱动专用;
    # cw_harness._stub_window_check 同式:窗口检查直通成功)。
    monkeypatch.setattr(op, 'check_game_window',
                        lambda: op.round_success('窗口桩(假环境无窗口)'))
    return op


# (原 test_battle_wait_execute_terminal_exit_new_path「B2-③ 主门经
#  execute() 走新路径:大厅终局锚 → terminal_lobby 早退」删:装端口驱动
#  的出口门随并存窗收口整删;出口门生产那份由下方完成白名单锁承重。)


def test_battle_wait_normal_exits(test_context, monkeypatch) -> None:
    """正常出口两段并一(单路径驱动,共享体断言不变)。
    [完成白名单出口] B2-③ 出口门:完成白名单锚命中 →
    back_to_loop 交回循环分发(装配点分流随基类退役,wait() 单路径直驱)。
    [结算分支逐位] D-94 读点(结算观察半直写)先于「继续挑战」点击
    (时序红线);C-1 新帧计数。
    (分诊:defer 复位腿摘除——defer_count 载体已在 src 退役
    (全仓零消费点),生产端无复位语义可锁。)"""
    # [完成白名单出口]
    op = _make_bwait(
        test_context, monkeypatch,
        frozenset({('货币战争-备战', '备战标识-购买经验')}))
    rs = op.wait()
    assert rs.is_success and rs.status == 'back_to_loop'
    # [结算分支逐位]
    order: list[str] = []
    op = _make_bwait(
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
    rs = op.wait()
    assert order == ['record', 'click'], (
        f'D-94 读点先于点击(时序红线):{order!r}')
    assert _rec.called
    assert op._st.rounds_done == 1, 'C-1 新结算帧计数'
    assert op._st.settle_stay == 1, '停留计数继续执行到 round_wait'
    assert not rs.is_success and rs.result == OperationRoundResultEnum.WAIT, (
        '驻留轮 round_wait(等待语义)')


def test_battle_wait_fallback_exits(test_context, monkeypatch) -> None:
    """兜底出口两段并一(生产路径驱动)。
    [长按] M39 停留第 3 轮(点击未生效)→ 长按 (960,898)
    press_time=0.5 兜底推进 + 停留计数归零(在册时序行为锁)。
    [未知 bail] 未知帧达 UNKNOWN_BAIL_N(10)→ round_fail 交主循环
    兜底链 + op 截图留证(flag 已退役,零真实 .debug 落盘)。
    生产路径逐轮 = 观察门双 miss → 决策循环分支链 miss → 计数。"""
    # [长按]
    clicks: list = []
    op = _make_bwait(
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
    # [未知 bail]
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )
    op = _make_bwait(test_context, monkeypatch, frozenset())
    shots: list[str | None] = []
    monkeypatch.setattr(op, 'save_screenshot',
                        lambda prefix=None: shots.append(prefix))
    res = None
    for _ in range(bwo.CwScreenBattleWait.UNKNOWN_BAIL_N):
        res = op.wait()
    assert res is not None and res.result == OperationRoundResultEnum.FAIL
    assert shots == ['battle_wait_bail'], 'bail 留证 = op 截图(flag 已退役)'
