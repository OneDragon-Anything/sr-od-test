"""统一观察架构·相位/收尾屏迁移测试(五相位屏 + 收尾屏,原两文件并入)。

设计正本 = docs/develop/sr_od/application/currency_war/flow/统一观察架构-画面op基类设计.md
(下称「架构设计」);迁移粒度/五段形态依据 = );
迁移手法单一源 = 装配点分流 + 五段钩子转录 + 实机适配器①封口 + on_outcome
注册表(先例:CwScreenPrep/遭遇/盛会之星,断言集模板 =
test_obs_arch_event_screens.py)。辖屏:
投资环境 CwScreenInvestEnv / 投资策略 CwScreenInvestStrategy / 战斗等待
CwScreenBattleWait / 简报 CwScreenBriefing / BOSS 简报 CwScreenBossBriefing
(五相位屏)+ 位面过渡 CwScreenPlaneTransition / 武装箱弹窗
CwScreenArmoryBox / 未达上限弹窗 CwScreenDeployNotFull / 等待1-1
CwScreenWaitOneOne(收尾/过渡相位屏,原 obs_arch_closing_screens 并入)。
位面情报采集 CwScreenPlaneIntel 已重构为 6 node 管线,其行为测试随迁
test_plane_intel_pipeline.py,本文件不辖。

**sim 腿不适用例外清单(随迁移批逐屏落测试 docstring,总纲 §2.2-3)**:

- 投资环境/投资策略:sim 腿 = 不适用——有 sim 事实来源(``decide_invest``
  注入段,架构设计 §3.2)但 sim 端口适配器未建(归 sim 接线批),本批
  等价判据主承重 = 实机在册行为测试 + 写入流对拍(实机腿),禁引用 sim 域
  对拍;
- 战斗等待:sim 腿 = 不适用——sim 事实来源为 coarse 结算产出,非画面段
  (§3.2 结算行),等价判据主承重 = 实机在册行为测试(B2-③ 主门:在册
  行为测试经 execute()/wait() 走新路径全绿);
- 简报/BOSS 简报:sim 腿 = 不适用——sim 无对应画面段(过渡相位,§3.2),
  等价判据主承重 = 实机在册行为测试 + 写入流对拍;
- 位面过渡/武装箱弹窗/未达上限弹窗/等待1-1:sim 腿 = 不适用——sim 无
  对应画面段(架构设计 §3.4 过渡相位/中断弹窗行),等价判据主承重 =
  实机在册行为测试 + 本文件两 node 形态测试,禁引用 sim 域对拍。

测试的语义(测试纪律 7 自检;出处 = landing 阶段一/三判据;行为测试单驱动
生产路径):

- **重入裁决归属测试**(单一定谳;简报腿 = ``test_briefing_reentry_
  adjudication_flag_gate_combination``,收尾屏组合腿 =
  ``test_reentry_arbitration_flag_gate_combination``):「已发」旗标裁决
  住决策动作 node 顶部(直驱 act 承重);投资两屏已改派发即终结交回
  (写时点测试另辖);简报仍为重入裁决形态;BOSS 简报无裁决旗标,横幅
  退场裁决 = 外循环重派后的下一次入口门;战斗等待/等待1-1 无裁决旗标。
  红 = 裁决被转录进观察 node。
- **观察上报接线测试**(两 node 形态屏):观察 node 稳定帧一次读
  → report 经屏文件落容器(容器终值)+ obs 挂实例属性;投资策略入口锚
  复探窗(ADR-0529 有界自愈)语义逐位(复探窗内自愈、超窗 round_retry
  消耗观察 node 预算)。位面过渡 = 实体链写(链容器终值双写);武装箱/
  未达上限/等待1-1 = 占位接线(现役零容器写点,统一形态)。
- **刷新终结交回测试**(投资策略,两 node 形态):建议刷新 → 闸 1 槽计数
  现读 >0 → 点钮恰一次 → 终结交回 round_success(交回外循环重进 = 入口
  重建);刷新计数写端随画面 op 基类退役(记账归动作 op 会话承接),
  闸 2 容器计数读端原样。
- **写入流对拍测试**:``active_env`` 写时点(gain-chain 3.2 反转:点卡/派发
  时点零写,落地相经获得链写;ADR-0598 点卡前写退役)、
  ``active_strategies`` 重入裁决出口 append(值/时点)、
  简报三字段容器写(词缀幂等辖「读+采」/boss 恒覆写/难度仅 None 写)
  逐位;结算观察半直写(D-94 时序)经战斗等待在册行为测试的轨迹断言承载。
- **round_wait 语义测试**(收尾屏):循环推进 = round_wait(不烧节点重试
  预算);等待1-1 = 轮询 round_wait 自环观察 node(全库唯一观察轮询
  变体)+ 固定超时留证兜底。
- **判别单一源消费面测试**已随三审整删退役(见文件尾在册注;源码扫描
  测试禁令不重建),防线归 review 与代码规范。
- **收口测试不恢复**(分诊):「cw_screen/ 顶层 op 类必为基类后代」AST
  全目录扫描形态(AGENTS §10.4.4 禁),摘除不恢复;结构面归 review 与
  代码规范。

驱动方式 = 真类实例(构造走 __init__)+ 读链/点击链桩化,节点函数直驱
(run_node 外壳);战斗等待 = 生产缺省形态(行为测试
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
from sr_od.application.currency_war.kernel.cw_action_report.pick_invest_env import (
    report_action_pick_invest_env_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_invest_strategy import (
    report_action_pick_invest_strategy_param,
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
    CwActionPickInvestEnvParam,
    CwActionPickInvestStrategyParam,
    CwActionRefreshInvestCardsParam,
)

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)

_RETRY_RS = OperationRoundResult(OperationRoundResultEnum.RETRY, status='stub-confirm')


# ==================== 迁移结构测试 + 重入裁决归属测试 ====================


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


def test_briefing_reentry_adjudication_flag_gate_combination(test_context,
                                                             monkeypatch) -> None:
    """简报重入裁决测试(重入裁决现役,归后续批;投资两屏的「派发即终结
    交回 + 派发时点写入」腿由 test_invest_env_active_env_written_at_
    dispatch / test_invest_strategy_written_at_dispatch 承重,不再重复):
    - 简报·落地轮:pending 在位 + 标识已退 → 裁决出口 success,读链不
      发生(裁决住决策动作 node 顶部,act 零读链);
    - 简报·门命中轮:pending 在位 + 标识仍在 → 「下一步」重发,旗标经
      置位体重置。
    红 = 简报裁决出口语义漂移 / 旗标复活。"""
    # 简报·落地轮:pending 在位 + 标识已退 → 裁决出口 success,读链不发生
    #(裁决住决策动作 node 顶部,act 零读链;简报重入裁决现役,归后续批)
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
              events: list | None = None, counts: list | None = None):
    """投资环境真类装配(生产构造走 __init__ = 适配器位/注册表在位)。

    桩面 = 画面门/截屏/候选读/策略器/计数读 + 派发动作 op 桩(pick-op-unify
    批起选卡+确认机械链迁入 ``CwActionPickInvestOp``,本文件桩派发捕获
    (param, env) 断言决策半产物与写端时序;机械链行为测试 =
    test_overlay_ops 投资 pick op 测试)。派发时点快照 ``active_env``
    现值(写时点对拍载体 = 点卡/派发时点应零写,写发生在落地相获得链)。
    ``counts`` = 计数读桩回值(缺省 [] = 读缺,obs.refresh=None → report
    跳写 env_refresh_left;走真计数用例传 [(count, x, y), ...])。
    (台账写点②桩面已随该方法退役删除——链观察落地批:环境改型由返回
    备战后的入口观察链读承接,op 层零自读。)"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_env as iem,
    )

    session = StrategySession()
    strategy = SimpleNamespace(
        decide_invest_env=lambda: CwActionPickInvestEnvParam(idx=pick_idx, reason='stub'))
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
                        lambda ctx, scr, kind: list(counts or []))

    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            if events is not None:
                events.append(('card_click',
                               (self.env.target.x, self.env.target.y)))
            # 模拟真动作 op 即时上报(桩不跑机械链,只承载上报接线;写时点
            # 对拍载体 = 派发时点结果已写入 game state)
            report_action_pick_invest_env_param(
                game_state_of(session), self.param,
                ChannelSig(family='logic_action',
                           actor='CwActionPickInvestOp', mode='compute'),
                session=session)
            if events is not None:
                events.append(('active_env_after_dispatch',
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
#  其唯一跨路径幸存断言「确认发出置 pending」并入下方选卡时点写测试;
#  离屏门 fail 早退语义由简报/BOSS 简报在册行为测试同形承重。)


def test_invest_env_observe_gate_and_report(test_context,
                                            monkeypatch) -> None:
    """投资环境观察 node 测试(两 node 形态):入口门 miss = round_fail 早退
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


def test_invest_env_active_env_written_at_dispatch(test_context,
                                                   monkeypatch) -> None:
    """写入流对拍(即时上报契约,写时点测试):派发确认链时点 = active_env
    已写入(动作 op 点完确认立即上报,gain_invest_env 整链;值 = 决策选中
    名)→ round_success 终结交回。红 = 写时点回退(派发时零写/等重入裁
    决)或 round_wait 循环回潮。"""
    events: list = []
    opts = [('追击概念股', 460), ('彩虹时代', 960), ('头彩', 1460)]
    op, _match, session, dispatches = _make_env(test_context, monkeypatch,
                                                in_screen=True,
                                                opts=opts, pick_idx=1,
                                                events=events)
    _run_node(test_context, op, op.observe)
    rs = _run_node(test_context, op, op.act)
    assert ('active_env_after_dispatch', '彩虹时代') in events, (
        f'派发时点 active_env 已写入(动作 op 即时上报):{events!r}')
    assert game_state_of(session).active_env.value == '彩虹时代', (
        '写值 = 决策选中名(获得链注册)')
    assert len(dispatches) == 1 and dispatches[0].param.idx == 1, (
        f'选卡+确认链恰一次派发,param 携真实 idx:{dispatches!r}')
    assert rs.is_success and '已派发' in (rs.status or ''), (
        f'派发后 round_success 终结交回:{rs!r}')


def test_invest_env_observe_standardization_gate(test_context,
                                                 monkeypatch) -> None:
    """观察标准化门测试(op-layer.md §1.1;观察层在观察时把读数转换成标准
    注册数据,容器值域 = 标准注册名):
    - 可转换名(全角冒号形变走归一精确命中;仅 LCS 可命中的单字误读形变)
      → 容器与 obs 存标准名(含「彩虹吋代」3/4 恰达阈值命中 = 拒判不过严
      回归锚);
    - 候选含转换失败名(乱串,注册表零重叠)→ 观察 round_fail,零写零
      上报(obs 不装载);
    - 两候选命中同一注册名(选项互斥屏重复名 = 必有误读)→ round_fail;
    - LCS 近分歧义(「击口概念股」对击破/追击概念股同分 0.8,注册表内
      歧义不可分辨)→ round_fail(防静默错标准化)。
    红 = 观察门漏转(脏值入容器)/ 转换失败带病上报 / 分差拒判缺失或过严。"""
    # ① 可转换名 → 标准名落容器('彩虹吋代' 仅 LCS 可命中:归一后不在注册
    # 表,LCS 3/4 恰达阈值且次高分明显低 → 命中;全角冒号走归一精确命中)
    opts = [('特邀专家：银狼', 460), ('彩虹吋代', 960), ('头彩', 1460)]
    op, _m, session, _disp = _make_env(test_context, monkeypatch, in_screen=True,
                                       opts=opts)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'可转换候选观察 success:{rs!r}'
    assert game_state_of(session).invest_env_opts.value == [
        '特邀专家:银狼', '彩虹时代', '头彩'], (
        f'容器存标准注册名(值域收敛):'
        f'{game_state_of(session).invest_env_opts.value!r}')
    assert op._obs is not None and op._obs.options == [
        ('特邀专家:银狼', 460), ('彩虹时代', 960), ('头彩', 1460)], (
        'obs 携标准名(x 坐标原样保留)')
    # ② 转换失败名(乱串)→ round_fail 零写零上报
    op_bad, _m2, session2, _d2 = _make_env(
        test_context, monkeypatch, in_screen=True,
        opts=[('骉羴犇', 460), ('头彩', 960)])
    rs_bad = _run_node(test_context, op_bad, op_bad.observe)
    assert not rs_bad.is_success and '标准化失败' in (rs_bad.status or ''), (
        f'转换失败观察早退:{rs_bad!r}')
    assert op_bad._obs is None, '失败路径 obs 不装载(零上报)'
    assert game_state_of(session2).invest_env_opts.value in (None, []), (
        '零写容器')
    # ③ 两候选命中同一注册名 → round_fail
    op_dup, _m3, session3, _d3 = _make_env(
        test_context, monkeypatch, in_screen=True,
        opts=[('彩虹时代', 460), ('彩虹吋代', 960)])
    rs_dup = _run_node(test_context, op_dup, op_dup.observe)
    assert not rs_dup.is_success and '标准化失败' in (rs_dup.status or ''), (
        f'重复命中判失败:{rs_dup!r}')
    assert game_state_of(session3).invest_env_opts.value in (None, []), (
        '重复命中零写容器')
    # ④ LCS 近分歧义(实机探针:「击口概念股」对击破/追击概念股同分
    # 0.8 → 注册表内歧义不可分辨,禁静默错标准化)
    op_amb, _m4, session4, _d4 = _make_env(
        test_context, monkeypatch, in_screen=True,
        opts=[('击口概念股', 460), ('头彩', 960)])
    rs_amb = _run_node(test_context, op_amb, op_amb.observe)
    assert not rs_amb.is_success and '标准化失败' in (rs_amb.status or ''), (
        f'近分歧义拒判:{rs_amb!r}')
    assert game_state_of(session4).invest_env_opts.value in (None, []), (
        '歧义零写容器')


def test_invest_env_refresh_left_observed_write(test_context,
                                                monkeypatch) -> None:
    """env_refresh_left 观察写端双腿测试(观察写端缺口补测):计数读得
    → report 落 ``env_refresh_left``(值 = 桩读数首条);读缺(缺省桩恒
    [])→ 跳写(缺省行为不变)。红 = 观察写端断流。"""
    op_hit, _m1, session1, _d1 = _make_env(
        test_context, monkeypatch, in_screen=True,
        opts=[('追击概念股', 460), ('彩虹时代', 960), ('头彩', 1460)],
        counts=[(2, 772, 983)])
    rs1 = _run_node(test_context, op_hit, op_hit.observe)
    assert rs1.is_success, f'前置:观察 success:{rs1!r}'
    assert game_state_of(session1).env_refresh_left.value == 2, (
        '计数读得 → env_refresh_left 值写入(读数首条)')
    op_miss, _m2, session2, _d2 = _make_env(
        test_context, monkeypatch, in_screen=True,
        opts=[('追击概念股', 460), ('彩虹时代', 960), ('头彩', 1460)])
    rs2 = _run_node(test_context, op_miss, op_miss.observe)
    assert rs2.is_success, f'前置:观察 success:{rs2!r}'
    assert game_state_of(session2).env_refresh_left.value is None, (
        '读缺 → 跳写')


def test_invest_env_empty_opts_fail_not_blindfire(test_context,
                                                  monkeypatch) -> None:
    """空候选 = round_fail 显式失败(零盲发;op-layer.md §1.1 + action_ops.md
    §1 增补 2「没有选到就是代码 bug」;策略屏同形测试
    test_invest_strategy_empty_opts_fail_not_blindfire 同构)。"""
    op = _phase_mod('cw_screen_invest_env').CwScreenInvestEnv(test_context)
    session = StrategySession()
    match = SimpleNamespace(strategy=SimpleNamespace(), session=session)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    from sr_od.application.currency_war.kernel.cw_screen_report.invest_env import (
        CwScreenInvestEnvObs as _ObsT,
    )
    # 装载「锚在但候选读空」的 obs(observe 成功形态;读缺发生在读链半)
    op._obs = _ObsT(hit=True, options=[])
    rs_empty = _run_node(test_context, op, op.act)
    assert not rs_empty.is_success and '读缺' in (rs_empty.status or ''), (
        f'空候选显式失败(零盲发):{rs_empty!r}')
    assert game_state_of(session).active_env.value in (None, ''), (
        '零盲发:无候选不写选择事实')


def test_invest_env_out_of_match_no_early_exit_normal_chain(
        test_context, monkeypatch) -> None:
    """无 match 局外无早退支测试(用户裁决 2026-09-22 全族删门,op-layer.md
    §1.1:画面 op 不支持局外单独调用,不设单跑防御分支):cw_match=None +
    非空候选 obs(区分空候选早退出口)→ act 不设局外早退门,沿正常链路
    因缺上下文自然失败(AttributeError)、零派发零点击。红 = 局外
    round_success 早退门回潮 / 局外 kernel 直调兜底决策回潮。"""
    iem = _phase_mod('cw_screen_invest_env')
    op = iem.CwScreenInvestEnv(test_context)
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    from sr_od.application.currency_war.kernel.cw_screen_report.invest_env import (
        CwScreenInvestEnvObs as _ObsT,
    )
    # 非空候选 obs(区分于空候选早退:本测试辖局外无早退支)
    op._obs = _ObsT(hit=True,
                    options=[('追击概念股', 460), ('彩虹时代', 960),
                             ('头彩', 1460)])
    clicks: list = []
    monkeypatch.setattr(iem, 'safe_click',
                        lambda op_, pt, **k: clicks.append(pt))
    dispatches: list = []

    class _SpyPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _SpyPickOp(act, env))
    with pytest.raises(AttributeError, match='strategy'):
        _run_node(test_context, op, op.act)   # 无 match 正常链路失败
    assert clicks == [], f'零点击:{clicks!r}'
    assert dispatches == [], f'零派发零上报:{dispatches!r}'


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
    方法级桩(复探窗语义归 ADR-0529 既有测试,本文件不辖)。返回
    ``(op, match, session, clicks, decide_calls, dispatches)``。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy as ism,
    )

    session = StrategySession()
    decide_calls: list[list[str]] = []

    def _decide():
        decide_calls.append(['stub'])   # 零参口后候选自容器槽(handler 写槽)
        return picks.pop(0) if picks else CwActionPickInvestStrategyParam(
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
            # 模拟真动作 op 即时上报(点完即写入 game state,即时上报契约;
            # 写时点对拍载体 = 派发时点持卡面已有值)
            report_action_pick_invest_strategy_param(
                game_state_of(session), self.param,
                ChannelSig(family='logic_action',
                           actor='CwActionPickInvestOp', mode='compute'),
                session=session)
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
#  逐项重叠;独有段迹/单决策断言已并入该测试。)


def test_invest_strategy_written_at_dispatch(test_context,
                                             monkeypatch) -> None:
    """写入流对拍(即时上报契约,写时点测试):派发确认链时点 = 持卡面已
    写入(动作 op 点完确认立即上报,gain_invest_strategy 整链:按名字去重
    追加)→ round_success 终结交回。真上报接线经桩内调用
    report_action_pick_invest_strategy_param 承载(与 _make_strategy 桩
    同款);本测试辖「决策 → 派发 → 写入 → 终结」全链。
    红 = 写时点回退(派发时零写)或 round_wait 循环回潮。"""
    names = ['赌神·银', '恢复生机', '气氛组']
    book = _FrameBook([object()])
    book.options[id(book.frames[0])] = _opts_of(names)
    picks = [CwActionPickInvestStrategyParam(idx=1, reason='stub')]
    op, _match, session, _clicks, _dc, disp = _make_strategy(
        test_context, monkeypatch, book, picks)
    _run_node(test_context, op, op.observe)
    rs = _run_node(test_context, op, op.act)
    assert len(disp) == 1 and disp[0].param.idx == 1, (
        f'选卡+确认链恰一次派发:{disp!r}')
    assert game_state_of(session).active_strategies.value == ['恢复生机'], (
        '派发时点经动作 op 即时上报写入(按名字去重追加)')
    assert rs.is_success and '已派发' in (rs.status or ''), (
        f'派发后 round_success 终结交回:{rs!r}')
    # 去重:同卡再上报 → 持卡面单份(数据卫生语义,裁定⑩)
    report_action_pick_invest_strategy_param(
        game_state_of(session),
        CwActionPickInvestStrategyParam(idx=1, norm_name='恢复生机'),
        ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute'),
        session=session)
    assert game_state_of(session).active_strategies.value == ['恢复生机'], (
        '持卡面按名字去重,不重复入列')


def test_invest_strategy_empty_opts_fail_not_blindfire(
        test_context, monkeypatch) -> None:
    """空候选 = round_fail 显式失败(零盲发;裁定「没有选到就是代码
    bug」——原 fallback(no-ocr) 盲点屏中路径废除)。"""
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
    # 装载「锚在但候选读空」的 obs(observe 成功形态;读缺发生在读链半)
    from sr_od.application.currency_war.kernel.cw_screen_report.invest_strategy import (
        CwScreenInvestStrategyObs as _ObsT,
    )
    op._obs = _ObsT(entry_ok=True, options=[])
    rs_empty = _run_node(test_context, op, op.act)
    assert not rs_empty.is_success and '读缺' in (rs_empty.status or ''), (
        f'空候选显式失败(零盲发):{rs_empty!r}')
    assert game_state_of(session).active_strategies.value in (None, []), (
        '零盲发:无候选不写持卡面')


def test_invest_strategy_out_of_match_no_early_exit_normal_chain(
        test_context, monkeypatch) -> None:
    """无 match 局外无早退支测试(用户裁决 2026-09-22 全族删门,op-layer.md
    §1.1:画面 op 不支持局外单独调用,不设单跑防御分支):cw_match=None +
    非空候选 obs(区分空候选早退出口;本测试防局外直调 kernel 决策器的
    兜底分支回潮)→ act 不设局外早退门,沿正常链路
    因缺上下文自然失败(AttributeError)、零派发零点击。红 = 局外
    round_success 早退门回潮 / 局外 kernel 直调兜底决策回潮。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy as ism,
    )
    op = ism.CwScreenInvestStrategy(test_context)
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    from sr_od.application.currency_war.kernel.cw_screen_report.invest_strategy import (
        CwScreenInvestStrategyObs as _ObsT,
    )
    # 非空候选 obs(区分于空候选早退:本测试辖局外无早退支)
    op._obs = _ObsT(entry_ok=True,
                    options=_opts_of(['赌神·银', '恢复生机', '气氛组']))
    clicks: list = []
    monkeypatch.setattr(ism, 'safe_click',
                        lambda op_, pt, **k: clicks.append(pt))
    dispatches: list = []

    class _SpyPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _SpyPickOp(act, env))
    with pytest.raises(AttributeError, match='strategy'):
        _run_node(test_context, op, op.act)   # 无 match 正常链路失败
    assert clicks == [], f'零点击:{clicks!r}'
    assert dispatches == [], f'零派发零上报:{dispatches!r}'


# (原 test_strategy_refresh_emission_wired_to_registry 删:注册表取证型
#  断言——登记件缺席时发射行为半必红,取证面零独立判别力,登记形状重构
#  = 误红源;行为半由 test_strategy_refresh_emission_semantics 承重。


def test_strategy_refresh_terminal_handback(test_context, monkeypatch) -> None:
    """逐卡刷新终结交回测试(两 node 形态):建议刷新 → 闸 1 槽计数现读 >0 →
    点钮恰一次(文本锚定)→ 终结交回 = round_success(op 结束,交回外循环
    重进 = 入口重建,重进后重观察重决策;本访问零比对零重决策——刷后不重读
    不比对不重决策)。观察轮 report 落容器 ``invest_strategy_opts`` 接线归测试
    (容器终值)。刷新计数写端随画面 op 基类退役(记账归动作 op 会话承接,
    本 op 不写计数——容器计数断言不设,闸 2 读端由下一测试承重)。
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


# (原 test_strategy_refresh_gate2_reads_container_count 删:剩余语义下
#  观察写端每访问覆盖容器(与闸 1 obs 同帧同值),「闸 2 独立拦截」形态
#  不复存在——剩余 ≤0 的拦截由闸 1 现值天然承载;观察写端摄入测试 =
#  test_invest_strategy_observe_reprobe_and_report 的 left 终值断言。)


def test_invest_strategy_observe_reprobe_and_report(test_context,
                                                    monkeypatch) -> None:
    """投资策略观察 node 测试(两 node 形态):入口锚复探窗(ADR-0529 有界
    自愈)语义逐位——复探窗内自愈、超窗 = round_retry(现役文案,消耗观察
    node 预算的既有 retry 面);在窗 → 一次读全 → report 落容器
    ``invest_strategy_opts``(容器终值)+ 逐卡刷新剩余 ``strategy_refresh_
    left`` 摄入(观察写端,键 = 规范卡名)+ obs 挂实例属性。
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
    # ② 在窗 → report 落容器 + obs 装载(计数在读 → left 观察写端摄入)
    book = _FrameBook([object()])
    book.options[id(book.frames[0])] = _opts_of(names)
    book.counts[id(book.frames[0])] = [(1, 477, _CNT_Y), (1, 975, _CNT_Y),
                                       (1, 1474, _CNT_Y)]
    op, _m, session, _clicks, _dc, _disp = _make_strategy(
        test_context, monkeypatch, book, [])
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    assert game_state_of(session).invest_strategy_opts.value == names, (
        f'report 落容器(容器终值):'
        f'{game_state_of(session).invest_strategy_opts.value!r}')
    _expect_left = {normalize_invest_name(n): 1 for n in names}
    assert game_state_of(session).strategy_refresh_left.value == _expect_left, (
        f'逐卡剩余观察写端摄入(键 = 规范卡名):'
        f'{game_state_of(session).strategy_refresh_left.value!r}')
    assert op._obs is not None and op._obs.options == _opts_of(names), (
        'obs 挂实例属性')


# ==================== 豁免留守测试(§2.2/§6.5-6)====================


# (三审整删)原 test_write_flow_exempt_surfaces_stay_inline「豁免
# 留守测试」(getsource ×6:注册表接线恰一处/钩子体与豁免面字面在场/环境屏
# 零登记件)——源码扫描形态(README 禁止清单,红时是文本变了,答不出哪个
# 运行行为坏了);豁免面纪律归 review 与代码规范。豁免面的行为面
# (chosen 写端不入注册表收编)由 event_screens 同名行为测试辖。


# ==================== 简报:三字段写语义 ====================


def _make_briefing(test_context, monkeypatch: pytest.MonkeyPatch, *,
                   mark_hit: bool = True, bosses: list | None = None,
                   affixes: list | None = None, difficulty: int | None = 5,
                   session: StrategySession | None = None):
    """简报真类装配(两 node 形态)。桩面 = 画面门/「下一步」点击/三读链;
    读链桩按记录器计数(读写语义断言载体)。返回 (op, session, calls)。"""
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
#  test_reentry_arbitration_flag_gate_combination 的简报两腿与三字段写
#  语义测试承重。)


def test_briefing_observe_gate_and_report(test_context, monkeypatch) -> None:
    """简报观察 node 测试(两 node 形态):入口门 miss = round_fail 早退
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
    assert calls['diff_read'] == 1, '难度每次进屏重读(读一次)'


def test_briefing_session_write_semantics_three_fields(test_context,
                                                       monkeypatch) -> None:
    """写入流对拍:简报三字段统一读写语义逐字——每次进屏都重读,
    读到非空恒覆写(重读自愈首次误读)/ 读空跳过写(读缺=跳过写,
    不擦同局已读真值)。单驱动观察 node(读侧住观察 node,写闸住
    report 屏文件,report 函数级闸面由 test_screen_report_ports
    承重,本测试辖 op 侧读链接线)。
    红 = 读链被已读守卫短路 / 覆写或跳写语义漂移。"""
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

    # ① 词缀:容器已有也重读重采重写(无已读守卫)
    session = StrategySession()
    _seed(session, 'enemy_affixes', ['已有词缀'])
    op, session, calls = _make_briefing(test_context, monkeypatch,
                                        mark_hit=True,
                                        affixes=[('新词缀', None)],
                                        bosses=['碎星王虫'], session=session)
    _run_node(test_context, op, op.observe)
    assert calls['affix_read'] == 1 and calls['affix_collect'] == 1, (
        f'词缀无已读守卫 → 重读重采:{calls!r}')
    assert _gso_t(session).enemy_affixes.value == ['新词缀'], '词缀读到必写'
    assert _gso_t(session).plane_bosses.value == ['碎星王虫'], \
        'boss 读到必写(恒覆写)'
    # ② boss:读到恒覆写(重读自愈)/ 读空跳过写(不擦已读真值)
    session2 = StrategySession()
    _seed(session2, 'plane_bosses', ['首次误读'])
    op2, session2, _c2 = _make_briefing(test_context, monkeypatch,
                                        mark_hit=True, bosses=['碎星王虫'],
                                        session=session2)
    _run_node(test_context, op2, op2.observe)
    assert _gso_t(session2).plane_bosses.value == ['碎星王虫'], \
        'boss 读到恒覆写(重读自愈)'
    op2b, session2b, _c2b = _make_briefing(test_context, monkeypatch,
                                           mark_hit=True, bosses=[],
                                           session=StrategySession())
    _seed(session2b, 'plane_bosses', ['首读真值'])
    _run_node(test_context, op2b, op2b.observe)
    assert _gso_t(session2b).plane_bosses.value == ['首读真值'], \
        'boss 读空跳过写(不擦已读真值)'
    # ③ 难度:容器已有也重读重写(无仅缺省读门)
    session3 = StrategySession()
    _seed(session3, 'enemy_difficulty', 3)
    op3, session3, calls3 = _make_briefing(test_context, monkeypatch,
                                           mark_hit=True, difficulty=5,
                                           session=session3)
    _run_node(test_context, op3, op3.observe)
    assert calls3['diff_read'] == 1, '难度无已读守卫 → 重读'
    assert _gso_t(session3).enemy_difficulty.value == 5, \
        '难度读到必写(恒覆写)'


def test_briefing_boss_standardize_fail_round_fail_zero_write(test_context, monkeypatch) -> None:
    """观察标准化门失败语义测试:boss 读数两段转换失败(任一候选未归一
    到规范名)= 观察失败——observe round_fail 早退、容器零写零上报、
    obs 不装载(op-layer.md §1.1 观察标准化门;禁原名透传带病上报)。
    红 = 失败路径回潮为透传照写照报。"""
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_briefing as bm
    from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
    op, session, _calls = _make_briefing(test_context, monkeypatch,
                                         mark_hit=True, bosses=['未知读数'],
                                         session=StrategySession())
    monkeypatch.setattr(bm, 'clean_boss_names_by_lcs', lambda gs: None)
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success, f'转换失败须 round_fail 早退:{rs!r}'
    assert game_state_of(session).plane_bosses.value is None, '容器零写'
    assert op._obs is None, 'obs 不装载(零上报)'


def test_clean_boss_names_lcs_ambiguity_rejection_and_unique_pass() -> None:
    """boss 两段转换·次高分差拒判测试(op-layer.md §1.1;用户裁定
    2026-09-22 全族统一,纯函数直测):LCS 阶段最高分未明显高于次高分 =
    歧义 = 转换失败返 None,禁直接取最高分——「造梦互动影业」对造梦
    兄弟影业/造梦互动娱乐同分 4/6 ≈ 0.667(共享词素族跨名借分),旧
    形态取注册表序首个 = 静默错配;明确唯一(「银甲武装公私」对银甲
    武装公司 5/6 ≈ 0.833,次高不过阈)照常命中 = 拒判不过严回归锚。
    红 = 歧义取最高分回潮 / 拒判误杀唯一命中。"""
    from sr_od.application.currency_war.obs import cw_briefing_obs as cbo
    assert cbo.clean_boss_names_by_lcs(['造梦互动影业']) is None, (
        '近分歧义 = 转换失败(禁静默取最高分)')
    assert cbo.clean_boss_names_by_lcs(
        ['银甲武装公私']) == ['银甲武装公司'], '②段唯一命中归一规范名'


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
#  接管测试与观察门测试同形承重。)


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


def test_boss_briefing_observe_gate_and_report_wiring(
        test_context, monkeypatch) -> None:
    """BOSS 简报观察 node 测试(两 node 形态):横幅已退(area 锚 miss +
    片段判别 miss)→ 早退 success 交回外循环重判(零点击,obs 不装载);
    横幅在 → obs 装载 + report 接线恰一次(match/gs 在场;boss 类型直定,
    目标 = 现 hist)。
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
    # ② 横幅在 → obs 装载 + report 恰一次
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
        f'report 接线恰一次(统一形态调用):{_reports!r}')


# (三审整删)原 test_boss_discrimination_single_source_consumers_
# unchanged「判别单一源消费面测试」(getsource ×3:消费点计数/import 复制面/
# token 表扩散断言;且 import 在飞互斥面 cw_loop)——源码扫描形态(README
# 禁止清单);「判别逻辑禁复制成第二源」防线归 review 与代码规范。


# ==================== 战斗等待:B2-③ 主门(在册行为测试·生产路径)====


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
#  的出口门随并存窗收口整删;出口门生产那份由下方完成白名单测试承重。)


def test_battle_wait_normal_exits(test_context, monkeypatch) -> None:
    """正常出口两段并一(单路径驱动,共享体断言不变)。
    [完成白名单出口] B2-③ 出口门:完成白名单锚命中 →
    back_to_loop 交回循环分发(装配点分流随基类退役,wait() 单路径直驱)。
    [结算分支逐位] D-94 读点(结算观察半直写)先于「继续挑战」点击
    (时序红线);C-1 新帧计数。
    (分诊:defer 复位腿摘除——defer_count 载体已在 src 退役
    (全仓零消费点),生产端无复位语义可校验。)"""
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

    # ②段已改调结算确认动作 op(landing §3.2):桩化子 op 为点击记录器
    # (M39 长按/证据等待/上报的行为测试迁 test_settle)。
    import importlib

    settle_confirm_mod = importlib.import_module(
        'sr_od.application.currency_war.operations.cw_op.cw_op_settle_confirm')

    class _ConfirmRecorder:
        def __init__(self, ctx):
            pass

        def execute(self):
            order.append('click')
            return SimpleNamespace(success=True, status='转移证据命中桩')

    monkeypatch.setattr(settle_confirm_mod, 'CwOpSettleConfirm',
                        _ConfirmRecorder)
    rs = op.wait()
    assert order == ['record', 'click'], (
        f'D-94 读点先于点击(时序红线):{order!r}')
    assert _rec.called
    assert op._st.rounds_done == 1, 'C-1 新结算帧计数'
    assert not rs.is_success and rs.result == OperationRoundResultEnum.WAIT, (
        '驻留轮 round_wait(等待语义;子 op 成功后回 ③段出口收口)')


def test_battle_wait_fallback_exits(test_context, monkeypatch) -> None:
    """兜底出口(生产路径驱动)。
    [未知 bail] 未知帧达 UNKNOWN_BAIL_N(10)→ round_fail 交主循环
    兜底链 + op 截图留证(flag 已退役,零真实 .debug 落盘)。
    生产路径逐轮 = 观察门双 miss → 决策循环分支链 miss → 计数。
    (原 [长按] M39 测试随结算点击/M39 迁入 CwOpSettleConfirm 改住
    test_settle,
    landing §3.2。)"""
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


# ==================== 收尾/过渡相位屏(原 obs_arch_closing_screens 并入)====


def _stub_controller(test_context, monkeypatch: pytest.MonkeyPatch) -> list:
    """controller 桩:mouse_move no-op + click 记录器。返回点击记录列表。"""
    clicks: list = []
    monkeypatch.setattr(
        test_context, 'controller',
        SimpleNamespace(mouse_move=lambda *a, **k: None,
                        click=lambda p, **k: clicks.append(p)),
        raising=False)
    return clicks


# (继承结构/节点预算门等静态形状测试分诊不恢复,见文件头「收口测试不恢复」。)


def test_reentry_arbitration_flag_gate_combination(test_context,
                                                   monkeypatch) -> None:
    """重入裁决×门组合行为测试(位面过渡/武装箱/未达上限均已迁移两 node
    形态,「已发」旗标裁决住决策动作 node 顶部,直驱 act 承重):
    - 位面过渡:门命中 + pending 在位 → 裁决不误判完成(门在 = 动作未
      落地,重点一次机械交回 round_wait);推进体缺坐标的失败轮旗标保持
      已消费态不复活;落地轮(提示已退 = 过渡完成)→ 裁决出口 success +
      零动作 + 旗标清;
    - 武装箱:门命中 + pending 在位 → 重点一轮(不误判完成);
    - 未达上限:门命中 + pending 在位 → 裁决不触发,勾选+确认重发、
      旗标经确认体重置(弹窗仍在 = 重发非完成);miss 已发 → 裁决
      success(零动作)。
    等待1-1 无裁决旗标(纯等待轮询)。红 = 裁决出口语义漂移(门命中误判
    完成 / 失败轮旗标复活)。"""
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
    # 位面过渡落地轮:提示已退 = 过渡完成 → 裁决出口 success,零动作,
    # 旗标清。红 = 裁决出口语义漂移。
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
    # 武装箱(裁决住决策动作 node 顶部):门命中 + pending 在位
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


def _make_plane_transition(test_context, monkeypatch: pytest.MonkeyPatch, *,
                           prompt_hit: bool, blank: object | None = None):
    """位面过渡真类装配(两 node 形态)。桩面 = 提示门/空白点 center/点击
    记录器;链读链(观察 node)由各测试按需补桩。"""
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
    """位面过渡观察 node 测试(两 node 形态):提示门 miss = round_fail 早退
    (现役文案,obs 不装载、零读链);门 hit → 底部行读数构造链值 → report
    落容器(开局链容器终值:node_path + node_path_baseline 双写,链正本
    §3 基线幂等门的写闸面在 report 屏文件,由 test_screen_report_ports
    承重,本测试辖 op 侧读链→report 接线)→ obs 挂实例属性。
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
    """武装箱两 node 形态测试(轻屏统一形态,
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


def test_deploy_not_full_observe_gate_and_placeholder_report(
        test_context, monkeypatch) -> None:
    """未达上限观察 node 测试(两 node 形态,补齐观察门申报面):
    标识门 miss = round_fail 早退(现役文案,obs 不装载、零 report);
    门 hit + gs 在场 → obs 装载 + 占位 report 接线恰一次;
    cw_match/gs 缺席 → 跳过 report 不炸(obs 仍装载,局外兜底路径)。
    红 = 门失效 / 接线断流 / 缺席路径误炸。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_deploy_not_full as dnm,
    )
    # ① 门 miss → fail 早退,obs 不装载零 report
    op_off, _c0 = _make_deploy_not_full(test_context, monkeypatch,
                                        mark_hit=False)
    _reports_off: list = []
    monkeypatch.setattr(dnm, 'report_screen_deploy_not_full_obs',
                        lambda gs, obs: _reports_off.append(obs))
    rs_off = _run_node(test_context, op_off, op_off.observe)
    assert not rs_off.is_success and '非未达上限弹窗' in (rs_off.status or ''), (
        f'门 miss 文案沿用现役:{rs_off!r}')
    assert op_off._obs is None and _reports_off == [], (
        f'门早退不装载 obs 零 report:{op_off._obs!r}')
    # ② 门 hit + gs 在场 → obs 装载 + 占位 report 恰一次
    _reports: list = []
    monkeypatch.setattr(dnm, 'report_screen_deploy_not_full_obs',
                        lambda gs, obs: _reports.append(obs))
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(gs=object()), raising=False)
    op, _clicks = _make_deploy_not_full(test_context, monkeypatch,
                                        mark_hit=True)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    assert op._obs is not None and op._obs.on_screen is True, 'obs 挂实例属性'
    assert len(_reports) == 1 and _reports[0] is op._obs, (
        f'占位 report 接线恰一次(统一形态调用):{_reports!r}')
    # ③ cw_match 缺席 → 跳过 report(obs 仍装载,局外兜底路径不炸)
    _reports_skip: list = []
    monkeypatch.setattr(dnm, 'report_screen_deploy_not_full_obs',
                        lambda gs, obs: _reports_skip.append(obs))
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    op_s, _c2 = _make_deploy_not_full(test_context, monkeypatch,
                                      mark_hit=True)
    rs_s = _run_node(test_context, op_s, op_s.observe)
    assert rs_s.is_success, f'缺席路径观察 success:{rs_s!r}'
    assert op_s._obs is not None and _reports_skip == [], (
        f'gs 缺席跳过 report,obs 仍装载:{op_s._obs!r}')


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
    """等待1-1 两 node 形态测试(纯等待型,现役 handle 逐位映射):锚命中 →
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


# (位面情报采集两个测试——薄转录装帧观察 node / 双节点图边——随 6 node 管线
#  重构退役,行为测试迁 test_plane_intel_pipeline.py。)
