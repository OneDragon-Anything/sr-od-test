"""遭遇节点 + 盛会之星 两 node 形态锁(迭代 2026-09-18-screen-op-flat-report)。

两屏均已迁移「观察 node → 决策动作 node」直继承 SrOperation 形态(盛会之星
= 节点循环 overlay 环形;遭遇 = 带分支刷新链的全形态)。锁的语义(测试
纪律:只锁新形态的核心约定;report 函数级契约由 test_cw_screen_report_ports
承重,本文件不重复):

- **入口门语义锁**(遭遇):画面身份门 miss = round_fail 交回外循环重判,
  文案沿用现役,且不进读链(obs 不装载);盛会之星 = 节点完成门(overlay
  消失 = 节点完成 success 交还外层)。
- **观察上报接线锁**(遭遇):观察 node 稳定帧一次读(候选 + 剩余次数)
  → report 经屏文件落容器 ``encounter`` + ``encounter_refresh_left``
  (容器终值)+ obs 与刷新文本锚点挂实例属性。
- **刷新链终结锁**(遭遇,迭代 2026-09-21-event-refresh-unify-supply-pick
  3.3:刷新 = 终结动作,剩余闸 = 观察真值):建议刷新 ∧ 闸放行(容器
  left>0 且锚点在位)→ 文本锚定点圆钮恰一次 + 固定等待 → round_success
  终结交回——无同访问 ``screenshot()`` 重读面、无 report 二次覆盖写、
  无重决策、零选卡派发;闸拒绝(剩余 0/None)→ 零点击,重调一次决策
  落选卡;重调仍建议刷新(刷新锚读缺面)→ round_fail 交回(计入外循环
  重派上限——防线行为,迭代 2026-09-24-encounter-screen-strategy-
  migration §2.5)。
- **派发即终结锁**(遭遇,迭代 2026-09-21-event-refresh-unify-supply-pick
  3.3 扩围):选卡确认链派发后 round_success 终结交回(零重入裁决轮);
  空候选 = 零点击终结交回(禁盲选派发确认——不可逆消耗);闸拒绝
  重调落选卡后同样终结。chosen_encounter 发射即写契约(动作侧 report
  函数级)= test_cw_screen_report_ports 承重,本文件不重复。
- **决策出口守卫锁**(遭遇):决策无有效输出(decide_encounter 返回
  词表外/None)= 具名 round_fail 零盲发(op-layer §1.1 出口③);pick
  idx 越界 = 守卫断言 AssertionError(§1.3 禁钳位)——两守卫均派发前
  零点击零派发,直发策略产实例(流程侧零值域改写)。
- **奖励兑现回调锁**(遭遇,kernel ``claim_encounter_reward``):双证
  判遭遇(node 镜像 token ∧ settlement_ring 尾行 node_type)∧
  progress_delta>0 单判;兑现写 ``encounter_reward_claimed`` 且 chosen
  随即清(单次消费,重触发天然幂等);单腿不合/未达标/删失/无 chosen
  = 不写不清。
- **盛会之星族锁**(节点循环形态):完成门/懒读保真/防重入旗标/chosen
  写端(选择点留守)/局外无早退支(observe 照常读链、act 正常链路失败,
  用户裁决 2026-09-22 全族删门)/观察标准化门
  (双源域命中·转换失败·歧义拒判·LCS 同分取域序首确定性)/决策守卫
  (候选空 fail 零盲发·idx 越界断言)/选择坐标观察上报收敛(候选检测
  重做批:标签带限定 OCR 定卡 1..N + 逐卡立绘 SIFT 交叉验证,xy =
  各卡标签中心 x + 在册卡身线 y 每卡自带,零枚举映射;fixture 全链·
  部分读 xy 自带·SIFT 交叉裁决·reader 失败信号透传 round_fail·
  标准化透传·派发 env idx-only·动作 op 容器取点守卫三臂断言零点击)
  各一锁,语义见各 docstring。

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
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickEncounterParam,
    CwActionPickMegastarParam,
    CwActionRefreshNodeOptionsParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    StrategyState,
)

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)


def _make_session() -> StrategySession:
    return StrategySession()


def _make_encounter(test_context, monkeypatch, *, in_screen: bool,
                    options: list[EncounterOption],
                    pick: object,
                    picks: list | None = None,
                    cnt: tuple | None = (1, (771, 899))):
    """遭遇屏真类装配(两 node 形态):门桩 + 稳定帧读链桩 + 确认链桩。
    ``picks`` = 零参决策桩回值队列(闸拒绝重调用例;耗尽后回落
    ``pick``)。刷新机械半 = 真代码路径(controller 桩在用例内打)。
    返回 (op, match, session)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter as em,
    )

    session = _make_session()
    _default_pick = pick
    _queue = list(picks) if picks is not None else None

    def _decide():
        if _queue:
            return _queue.pop(0)
        return _default_pick

    strategy = SimpleNamespace(decide_encounter=_decide)
    match = SimpleNamespace(strategy=strategy, session=session)
    # 终态契约 §B:match 桩挂载容器(gs 持有引用直用)。
    match.gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = em.CwScreenEncounter(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_screen))
    monkeypatch.setattr(op, 'screenshot', lambda: _FRAME)
    monkeypatch.setattr(em, 'read_encounter_options',
                        lambda ctx, scr: list(options))
    monkeypatch.setattr(em, 'read_encounter_refresh_count',
                        lambda ctx, scr: cnt)
    # 统一动作工厂批4:遭遇确认链体迁 pick op 模块——safe_click 桩随体迁移;
    # 确认 = area 查找点击(确认钮查找全族统一,用户裁定 2026-09-22),
    # 宿主 op 桩承接(桩语义不变:确认链回指定轮次结果);机械等待替身
    # (mock 画面瞬时切换,等待纯属空睡)。
    import sr_od.application.currency_war.operations.cw_op.cw_pick_encounter_action as pick_mod
    monkeypatch.setattr(pick_mod, 'safe_click', lambda o, pt, **k: None)
    monkeypatch.setattr(pick_mod, 'time', SimpleNamespace(sleep=lambda *_: None))
    monkeypatch.setattr(em.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda scr, s, a, **k: op.round_retry('stub-confirm'))
    # (record_event_choice 替身桩已随删除波 1 移除——exogenous 写入端退役,
    #  encounter 模块不再引用 telemetry;(gs_view 桩同批移除——模块本体
    #  随波 5b 双删,桩对象不存在。))
    return op, match, session


def _make_megastar(test_context, monkeypatch, *, in_node: bool,
                   options: list | None = None,
                   pick: object | None = None,
                   stub_action: bool = True):
    """盛会之星真类装配(两 node 形态,迭代 2026-09-18-screen-op-flat-report):
    门桩 + 候选读链桩(观察 node 读屏函数注入点)+ 动作体调用计数。
    旗标宿主 = 策略器 StrategyState(经 session.strategy_state 通道)。
    ``pick`` = 策略桩回值(决策守卫锁用;传真实 ``CwActionPickMegastar
    Param`` = 守卫② 类型收紧后桩须同型);``stub_action=False`` = 不桩
    ``_do_action``(守卫锁直驱真动作体,经 act 消费),此时第 4 元恒
    空表(计数桩未挂)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_megastar as ms,
    )

    session = _make_session()
    match = SimpleNamespace(session=session)
    if pick is not None:
        match.strategy = SimpleNamespace(decide_megastar=lambda: pick)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(in_node))
    monkeypatch.setattr(ms, 'read_megastar_options',
                        lambda ctx, scr: list(options or []))
    calls: list[int] = []
    if stub_action:
        monkeypatch.setattr(op, '_do_action', lambda: calls.append(1))
    return op, match, session, calls


# ==================== 遭遇节点(两 node 全形态)====================


def test_encounter_observe_gate_fails_off_screen(
        test_context, monkeypatch) -> None:
    """入口门语义锁:非遭遇屏 → round_fail 早退交回外循环重判(现役首闸
    同 status),且不进读链(obs 不装载)。红 = 门失效 / 门早退仍读屏。"""
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=False, options=[],
        pick=CwActionPickEncounterParam(idx=0, reason='stub'))
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and '非遭遇节点屏' in (rs.status or ''), (
        f'观察门早退语义不变:{rs!r}')
    assert op._obs is None, '门早退不装载 obs'


def test_encounter_observe_reports_container(
        test_context, monkeypatch) -> None:
    """观察上报接线锁:观察 node 稳定帧一次读(候选 + 剩余次数)→ report
    落容器 ``encounter``(容器终值 = 候选)+ ``encounter_refresh_left``
    (剩余语义摄入;读缺跳写闸在 report 内)+ obs 与刷新文本锚点挂实例
    属性。红 = 接线断流 / 容器终值漂移 / left 未摄入。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, _match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionPickEncounterParam(idx=0, reason='stub'),
        cnt=(2, (771, 899)))
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success:{rs!r}'
    gs = game_state_of(session)
    assert gs.encounter.value is not None \
        and list(gs.encounter.value.options) == opts, (
        f'report 落容器(容器终值):{gs.encounter.value!r}')
    assert gs.encounter_refresh_left.value == 2, (
        'report 摄入剩余次数(容器 left = 观察真值)')
    assert op._obs is not None and op._obs.refresh_left == 2, (
        'obs 挂实例属性(剩余次数随观察一次读)')
    assert op._refresh_point is not None, '刷新文本锚点挂实例属性'


def test_encounter_act_dispatch_terminal(
        test_context, monkeypatch) -> None:
    """派发即终结锁(迭代 …3.3 扩围):零参决策 → 选卡确认链派发 →
    round_success 终结交回(零重入裁决轮、零刷新点击)。红 = round_wait
    循环回潮(重入裁决复活)/ 派发断流 / 刷新臂误触发。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
            EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])]
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionPickEncounterParam(idx=1, reason='stub'))
    _run_node(test_context, op, op.observe)
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '终结交回' in (rs.status or ''), (
        f'派发后 round_success 终结交回:{rs!r}')
    assert len(dispatches) == 1, f'选卡派发恰一次:{dispatches!r}'
    assert clicks == [], '非刷新臂零点击'


def test_encounter_empty_options_zero_click_terminal(
        test_context, monkeypatch) -> None:
    """空候选零点击终结锁(attack3 X2):候选读缺(obs.options 空)→
    零点击零派发 round_success 终结交回重读。红 = 盲选 idx0 派发确认
    回潮(选卡确认不可逆消耗本节点)。"""
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=[],
        pick=CwActionPickEncounterParam(idx=0, reason='stub'))
    _run_node(test_context, op, op.observe)
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '零点击' in (rs.status or ''), (
        f'空候选 = 零点击终结交回重读:{rs!r}')
    assert clicks == [] and dispatches == [], (
        f'空候选禁盲选派发:clicks={clicks!r} dispatches={dispatches!r}')


def test_encounter_decision_invalid_named_fail_zero_blindfire(
        test_context, monkeypatch) -> None:
    """决策无输出守卫锁(规范 = screens/op-layer.md §1.1 出口③「决策无
    有效输出也走此出口——零盲发」):decide_encounter 返回 None / 词表外
    类型 → 具名 round_fail(消息含策略器原值)零点击零派发。红 = 默认
    idx0 盲选左卡派发回潮(决策失败被静默降级为不可逆的选卡消耗)。"""
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    for bad in (None, object()):
        op, _match, _session = _make_encounter(
            test_context, monkeypatch, in_screen=True,
            options=[EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])],
            pick=bad)
        assert _run_node(test_context, op, op.observe).is_success, (
            f'前置:观察 success(候选 1 元,bad={bad!r})')
        rs = _run_node(test_context, op, op.act)
        assert not rs.is_success and '决策无有效输出' in (rs.status or ''), (
            f'词表外/None = 具名 fail 零盲发(bad={bad!r}):{rs!r}')
    assert clicks == [] and dispatches == [], (
        f'守卫零盲发(零点击零派发):{clicks!r} {dispatches!r}')


def test_encounter_out_of_range_idx_asserts_before_click(
        test_context, monkeypatch) -> None:
    """决策值域守卫锁(规范 = screens/op-layer.md §1.3「非法返回 = 策略器
    bug 响亮暴露,禁静默钳位」):策略器返回越界 idx(真实
    ``CwActionPickEncounterParam(idx=5)``、options 1 元)→ AssertionError
    传播(消息含 idx/len/原值留证)、零点击零派发(守卫在派发前——越界
    放行会确认错卡,不可逆)。红 = 静默钳 0 续跑回潮 / 越界放行派发。"""
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=True,
        options=[EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])],
        pick=CwActionPickEncounterParam(idx=5, reason='stub'))
    assert _run_node(test_context, op, op.observe).is_success, (
        '前置:观察 success(obs.options 1 元)')
    with pytest.raises(AssertionError, match='禁钳位'):
        _run_node(test_context, op, op.act)
    assert clicks == [] and dispatches == [], (
        f'断言前零点击零派发:{clicks!r} {dispatches!r}')


def _refresh_fixture(test_context, monkeypatch) -> tuple[list, list]:
    """刷新臂公共桩:controller 点击记录 + 机械等待替身 + 动作派发计数。
    返回 (clicks, dispatches)。"""
    clicks: list = []
    dispatches: list = []
    monkeypatch.setattr(test_context.controller, 'mouse_move',
                        lambda p, **k: None, raising=False)
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda p, **k: clicks.append((p.x, p.y)))
    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as reg_mod
    monkeypatch.setattr(reg_mod, 'action_op_for',
                        lambda act, ctx, env: dispatches.append(act)
                        or SimpleNamespace(execute=lambda: True))
    return clicks, dispatches


def test_encounter_refresh_terminal_click_once_and_success(
        test_context, monkeypatch) -> None:
    """刷新链终结锁(迭代 2026-09-21-event-refresh-unify-supply-pick
    design §2.0A):建议刷新 ∧ 剩余闸放行(容器 left=1 ∧ 锚点在位)→
    文本锚定点圆钮**恰一次** + 固定等待 → round_success 终结交回;同访问
    零 ``screenshot()`` 重读、零 report 二次覆盖写(容器终值 = 刷前候选)、
    零重决策(恰一次决策)、零选卡派发。红 = 重读回潮 / 二次覆盖写回潮 /
    重复点钮 / 终结交回失败。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    op, match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionRefreshNodeOptionsParam(reason='stub'),
        cnt=(1, (771, 899)))
    _ss_calls: list[int] = []
    monkeypatch.setattr(op, 'screenshot',
                        lambda: _ss_calls.append(1) or _FRAME)
    _decide_calls: list[int] = []
    _orig_decide = match.strategy.decide_encounter

    def _counting():
        _decide_calls.append(1)
        return _orig_decide()

    match.strategy.decide_encounter = _counting
    _run_node(test_context, op, op.observe)
    gs = game_state_of(session)
    assert gs.encounter_refresh_left.value == 1, '前置:观察轮摄入容器 left'
    _ss_calls.clear()
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '终结交回' in (rs.status or ''), (
        f'点钮后 round_success 终结交回:{rs!r}')
    assert clicks == [(771 - 100, 899)], (
        f'刷新圆钮文本锚定偏移点击恰一次:{clicks!r}')
    assert _decide_calls == [1], f'零重决策(恰一次决策):{_decide_calls!r}'
    assert _ss_calls == [], '同访问零 screenshot() 重读面'
    assert list(gs.encounter.value.options) == opts, (
        f'零二次覆盖写(容器终值 = 刷前候选):{gs.encounter.value!r}')
    assert gs.encounter_refresh_left.value == 1, 'left 不被访问内改写'
    assert dispatches == [], '终结轮零选卡派发'


def test_encounter_refresh_gate_rejects_zero_and_none(
        test_context, monkeypatch) -> None:
    """刷新闸拒绝锁:建议刷新但剩余 0 / None(未观察)→ 零点击不按刷新
    终结,重调一次决策按原评分选卡(派发即终结交回)。红 = 闸失守重刷 /
    拒绝轮漏选卡。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
            EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])]
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    # ① 剩余 0 → 零点击,重调落选卡派发即终结
    op, _match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionPickEncounterParam(idx=1, reason='rescore'),
        picks=[CwActionRefreshNodeOptionsParam(reason='stub')],
        cnt=(0, (771, 899)))
    _run_node(test_context, op, op.observe)
    assert game_state_of(session).encounter_refresh_left.value == 0, (
        '前置:观察轮摄入 left=0')
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '终结交回' in (rs.status or ''), (
        f'拒绝轮重调落选卡 → 派发即终结交回:{rs!r}')
    assert clicks == [], f'剩余 0 = 刷新钮零点击:{clicks!r}'
    assert len(dispatches) == 1, '选卡派发照发'
    # ② 剩余 None(读缺未摄入)→ 零点击,重调落选卡派发即终结
    op2, _m2, session2 = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionPickEncounterParam(idx=0, reason='rescore'),
        picks=[CwActionRefreshNodeOptionsParam(reason='stub')],
        cnt=None)
    _run_node(test_context, op2, op2.observe)
    assert game_state_of(session2).encounter_refresh_left.value is None, (
        '前置:读缺跳写,容器 left 未写')
    rs2 = _run_node(test_context, op2, op2.act)
    assert rs2.is_success and '终结交回' in (rs2.status or ''), (
        f'None 拒绝轮重调落选卡派发即终结:{rs2!r}')
    assert clicks == [], f'None = 刷新钮零点击:{clicks!r}'
    assert len(dispatches) == 2, 'None 拒绝轮派发照发(桩跨臂累计 ①+②)'


def test_encounter_refresh_gate_mismatch_round_fail_redispatch(
        test_context, monkeypatch) -> None:
    """刷新锚读缺防线锁(迭代 2026-09-24-encounter-screen-strategy-
    migration design §2.5):拒绝后重调仍返回刷新建议(刷新锚点读缺面)
    → round_fail 交回——失败计入外循环重派上限
    (``OP_FAIL_REDISPATCH_LIMIT`` 只计连续 fail,零点击 round_success
    交回不计数且清零计数窗,故改 fail 有界收敛;设计定谳「零点击交回」
    对「锚持续读缺 ∧ 建议刷恒成立」无防护)。红 = 零点击 round_success
    终结交回回潮(无界重进循环面)/ 拒绝-重调环回潮漏处置死循环。"""
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionRefreshNodeOptionsParam(reason='stub-again'),
        picks=[CwActionRefreshNodeOptionsParam(reason='stub')],
        cnt=(0, (771, 899)))
    _run_node(test_context, op, op.observe)
    rs = _run_node(test_context, op, op.act)
    assert not rs.is_success and '刷新锚点读缺' in (rs.status or ''), (
        f'重调仍建议刷新 → round_fail 交回:{rs!r}')
    assert clicks == [], '零点击'
    assert dispatches == [], '零选卡派发'


def test_claim_encounter_reward_branches(
        test_context, monkeypatch) -> None:
    """奖励兑现回调锁(迭代 …3.3 扩围 design §2.4,R1 复攻定谳后形态):
    判遭遇 = 双证(node 镜像 token 'encounter' ∧ settlement_ring 尾行
    node_type='遭遇')——单腿不满足即拒(ring-mismatch 臂 = 镜像遭遇但
    ring 尾行普通战斗的陈旧镜像防线);达标 = progress_delta>0 单判。
    达标双证 → 写 encounter_reward_claimed 且 chosen 随即清(单次消费),
    重触发 = no-chosen 天然幂等;非遭遇/删失/无 chosen = 不写不清。
    红 = 单证兑现回潮(note 腿静默删除旧形态)/ 陈旧镜像误兑现 /
    消费后 chosen 不清(重兑现面)。"""
    from sr_od.application.currency_war.kernel.cw_encounter_selection import (
        claim_encounter_reward,
        record_settlement_row,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        NodeKey,
        Settlement,
    )

    def _set_frame(session, *, kind: str, delta: int | None,
                   ring_node: str, round_num: int = 7) -> None:
        gs = game_state_of(session)
        _obs_sig = ChannelSig(family='obs', actor='test', mode='read')
        gs.observe(gs.node, NodeKey(plane=1, round_num=round_num, kind=kind),
                   sig=_obs_sig)
        gs.observe(gs.settlement,
                   Settlement(hp_after=80, streak_after=1, killed=None,
                              progress_delta=delta, gold=10, level=3,
                              xp=(5, 20)),
                   sig=_obs_sig)
        # 结算行入环(与生产同口 = record_settlement_row 单一写端;
        # outcome 腿只取 killed/progress_fill_ratio,桩最小面)。
        # round_num 逐臂递增 = 模拟不同节点(环按 plane+round 去重合并,
        # 同键会合并进首见行,node_type 以首见为准)。
        record_settlement_row(
            gs, SimpleNamespace(killed=None, progress_fill_ratio=None),
            plane=1, round_num=round_num, node_type=ring_node,
            difficulty_node=None, encounter_tier=None)

    session = StrategySession()
    gs = game_state_of(session)
    _sig = ChannelSig(family='logic_action', actor='test', mode='compute')
    gs.write_logic(gs.chosen_encounter, (3, '随机4费×3'),
                   produced_by='test', sig=_sig)
    # ① 镜像=encounter 但 ring 尾行=普通战斗:双证第二腿不合 → 拒
    #    (attack3 R1 陈旧镜像防线;「单证兑现」缺陷形态回归锁)
    _set_frame(session, kind='encounter', delta=2, ring_node='普通战斗',
               round_num=7)
    assert claim_encounter_reward(gs) == 'ring-mismatch', 'ring 腿不合拒兑现'
    assert gs.encounter_reward_claimed.value is None, 'ring 腿不合零写'
    assert gs.chosen_encounter.value == (3, '随机4费×3'), 'ring 腿不合不清'
    # ② 镜像非遭遇(镜像腿独立防面):拒
    _set_frame(session, kind='battle', delta=2, ring_node='遭遇',
               round_num=8)
    assert claim_encounter_reward(gs) == 'not-encounter', '非遭遇拒兑现'
    assert gs.encounter_reward_claimed.value is None, '非遭遇零写'
    assert gs.chosen_encounter.value == (3, '随机4费×3'), '非遭遇不清 chosen'
    # ③ 双证合未达标(败局负值):不写不清
    _set_frame(session, kind='encounter', delta=-22, ring_node='遭遇',
               round_num=9)
    assert claim_encounter_reward(gs) == 'not-qualified', '败局不兑现'
    assert gs.encounter_reward_claimed.value is None and \
        gs.chosen_encounter.value == (3, '随机4费×3'), '未达标零写零清'
    # ④ 双证合删失(delta None):不写不清(fail-closed)
    _set_frame(session, kind='encounter', delta=None, ring_node='遭遇',
               round_num=10)
    assert claim_encounter_reward(gs) == 'not-qualified', '删失不兑现'
    # ⑤ 达标双证:兑现写 + chosen 随即清(单次消费)
    _set_frame(session, kind='encounter', delta=2, ring_node='遭遇',
               round_num=11)
    assert claim_encounter_reward(gs) == 'claimed', '达标兑现'
    assert gs.encounter_reward_claimed.value == (3, '随机4费×3'), (
        '兑现记录 = 所选 (难度, 奖励)')
    assert gs.chosen_encounter.value is None, '兑现后清 chosen(单次消费)'
    # ⑥ 重触发(驻留轮二调):no-chosen 天然幂等
    assert claim_encounter_reward(gs) == 'no-chosen', '重触发幂等'
    assert gs.encounter_reward_claimed.value == (3, '随机4费×3'), (
        '幂等轮不覆写')
    # ⑦ 遭遇双证达标但无 chosen:不兑现
    _set_frame(session, kind='encounter', delta=2, ring_node='遭遇',
               round_num=12)
    assert claim_encounter_reward(gs) == 'no-chosen', '无 chosen 不兑现'


# ==================== 盛会之星(节点循环形态)====================


def test_megastar_observe_gate_completes_off_overlay(
        test_context, monkeypatch) -> None:
    """盛会之星观察 node 完成门(两 node 形态):门 miss = overlay 消失 /
    进了下一节点 → 节点完成,success 交还外层(完成 settle 承诺不变);
    选中标记复位副作用随 ``_in_node`` 复检保留(跨节点不保持);门早退
    不读候选不动作不写容器。红 = 完成门失效 / 复位丢失 / 早退后仍发动作。"""
    op, _match, session, calls = _make_megastar(
        test_context, monkeypatch, in_node=False, options=['哨兵'])
    session.strategy_state = StrategyState()
    session.strategy_state.megastar_clicked = True   # 预置跨节点残留态
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success and '巨星节点完成' in (rs.status or ''), (
        f'完成语义不变:{rs!r}')
    assert session.strategy_state.megastar_clicked is False, (
        '选中标记复位副作用随 _in_node 复检保留(跨节点不保持;'
        '宿主 = 策略器 StrategyState)')
    assert calls == [], '离屏早退 = 不发动作'
    assert game_state_of(session).megastar_opts.value is None, (
        '门早退不进读链,容器零写')


def test_megastar_observe_reports_and_act_acts(
        test_context, monkeypatch) -> None:
    """盛会之星在屏形态(两 node 形态):观察 node 读候选一次 → report 落
    容器 ``megastar_opts``(容器终值)+ obs 挂实例属性 → 决策动作 node 恰
    一个动作 + round_wait 推进循环(不计节点重试预算)。红 = report 断流 /
    容器终值漂移 / 动作丢失 / 循环推进回退为计预算的 retry。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    op, _match, session, calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花火')])
    session.strategy_state = StrategyState()   # 未选中 → 本访问将选择(读候选)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success and game_state_of(session).megastar_opts.value == [
        MegastarOption(idx=0, char_id='花火')], (
        f'观察上报落容器(容器终值):{game_state_of(session).megastar_opts.value!r}')
    assert op._obs is not None and len(op._obs.options) == 1, (
        'obs 挂实例属性(跨 node 传递)')
    rs2 = _run_node(test_context, op, op.act)
    assert calls == [1], f'决策动作 node 恰一个动作:{calls!r}'
    assert rs2.result == OperationRoundResultEnum.WAIT, (
        f'循环推进 = round_wait(不计节点重试预算):{rs2!r}')


def test_megastar_lazy_read_skipped_on_confirm_visit(
        test_context, monkeypatch) -> None:
    """巨星懒读保真(读时机保真,迁移不增加读屏):已选中(确认访问)→
    观察 node **不读候选**(读链桩零调用)→ report 空候选不写(容器保持
    前值);决策动作 node 照发确认(动作体被消费)。红 = 确认访问重读候选
    (新增读屏)/ 容器被空值覆写。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    op, _match, session, calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花火')])
    session.strategy_state = StrategyState()
    session.strategy_state.megastar_clicked = True   # 已选中 = 确认访问
    _read_calls: list[int] = []
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar as ms
    monkeypatch.setattr(
        ms, 'read_megastar_options',
        lambda ctx, scr: _read_calls.append(1) or [])
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success and _read_calls == [], (
        f'确认访问不重读候选(懒读保真):{_read_calls!r}')
    assert game_state_of(session).megastar_opts.value is None, (
        '空候选不写(闸在 report 内),容器保持前值')
    rs2 = _run_node(test_context, op, op.act)
    assert calls == [1] and not rs2.is_success, '确认访问照发确认动作'


def test_megastar_redispatch_no_reclick_and_gate_reset(
        test_context, monkeypatch) -> None:
    """巨星防重入行为锁(旗标宿主 = 策略器 StrategyState,执行层经 kernel
    ``strategy_state_of`` None-safe 通道读写;picks-op-unify 批起选中半
    迁入 ``CwActionPickMegastarOp``,本锁经派发 env.need_select 断言):
    - 同节点二次派发(re-dispatch 重入,门未 miss)→ 已点标记在位,
      再派发 need_select=False(不重触发选中,防 re-click toggle 反选 →
      确认无候选卡死);
    - 门 miss(离开巨星 overlay)→ 节点完成即复位,标记不跨节点保持
      (巨星一局可多次触发);
    - 状态对象缺席(裸 session,第三方策略面)→ 读退 False、写跳过,
      执行层不冷建策略器状态(禁 impl ``state_of`` 装配语义);
    - chosen_megastar = 选择点留守写端(动作事实边界,不进 report),
      首派发选中时点落容器;
    - 派发 env = idx-only 构造(选择坐标观察上报收敛):零 target 传参,
      候选点击坐标由动作 op 自容器取(op-layer.md §1.1「选择坐标观察
      上报」)。
    红 = 重入再触发选中 / 门 miss 不复位 / 缺席态炸错或冷建 / chosen 断流
    / 派发 env 回潮带 target 坐标。"""
    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as reg_mod
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_megastar as ms,
    )

    session = StrategySession()
    st = StrategyState()
    session.strategy_state = st
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(
            decide_megastar=lambda: CwActionPickMegastarParam(
                idx=0, reason='stub')))
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_match,
    )
    match.gs = _gso_match(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    monkeypatch.setattr(ms, 'read_megastar_options',
                        lambda ctx, scr: [MegastarOption(idx=0, char_id='花火')])

    # 派发桩:捕获每次派发的 need_select(选中半触发标志)与 env.target
    # (idx-only 断言;选中点击的机械行为锁 = test_cw_unified_action_4
    # 巨星 op 锁,本锁只锁画面 op 的防重入与派发形态)。
    dispatches: list[bool] = []
    env_targets: list[object] = []

    class _StubPickOp:
        def __init__(self, env) -> None:
            self.env = env

        def execute(self) -> bool:
            dispatches.append(bool(getattr(self.env, 'need_select', False)))
            env_targets.append(getattr(self.env, 'target', 'MISSING'))
            return True

    monkeypatch.setattr(reg_mod, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(env))
    # 观察注入(观察 node 读屏函数注入点):驱动观察 node 装载 obs
    assert op.observe().is_success, '在屏观察 success'
    # ① 首派发:触发选中(need_select=True)+ 发射即置位 + chosen 留守写端落容器
    op._do_action()
    assert dispatches == [True], f'首派发触发选中半:{dispatches!r}'
    assert env_targets == [None], (
        f'派发 env = idx-only 构造零 target 传参:{env_targets!r}')
    assert st.megastar_clicked is True, '置位落策略器 StrategyState'
    assert match.gs.chosen_megastar.value == '花火', (
        'chosen_megastar = 选择点留守写端(动作事实边界不进 report)')
    # ② 同节点二次派发:标记在位 → 不再触发选中
    op._do_action()
    assert dispatches == [True, False], (
        f'二次派发不重触发选中(防反选卡死):{dispatches!r}')
    # ③ 门 miss(离开巨星 overlay)→ 节点完成即复位
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    assert op._in_node(_FRAME) is False, '门 miss = 节点完成'
    assert st.megastar_clicked is False, '门 miss 复位(标记不跨节点保持)'
    # ④ 状态对象缺席:读退 False、写跳过、不冷建(裸 session 可完整跑动作)
    session2 = StrategySession()   # strategy_state 缺省 None
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session2,
                                        strategy=match.strategy,
                                        gs=_gso_match(session2)),
                        raising=False)
    op2 = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op2, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op2, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    assert op2.observe().is_success, '缺席态观察照常'
    op2._do_action()
    assert dispatches == [True, False, True], (
        '缺席态读退 False → 照常触发选中(无宿主防重入)')
    assert env_targets[-1] is None, '缺席态派发 env 仍 idx-only 零 target'
    assert session2.strategy_state is None, '缺席态写跳过,执行层不冷建'


# ==================== 盛会之星(局外无早退支 + 观察标准化门)====================


def test_megastar_out_of_match_no_early_exit_normal_chain(
        test_context, monkeypatch) -> None:
    """局外无早退支锁(用户裁决 2026-09-22 全族删门,op-layer.md §1.1):
    无 match / match 无 gs 两态 → observe 照常走读链(读链桩被调、obs
    装载,report 空候选零写不炸)、act 无局外早退门——沿正常链路走候选
    空守卫具名 round_fail,零派发。红 = 局外 round_success 早退门回潮
    (observe 零读早退 / act 局外交回)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as reg_mod
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar as ms

    dispatches: list[object] = []
    monkeypatch.setattr(reg_mod, 'action_op_for',
                        lambda act, ctx, env: dispatches.append(act)
                        or SimpleNamespace(execute=lambda: True))

    # ① 无 match
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    op = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    _read_calls: list[int] = []
    monkeypatch.setattr(ms, 'read_megastar_options',
                        lambda ctx, scr: _read_calls.append(1) or [])
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success and _read_calls == [1], (
        f'无 match 局外:观察照常走读链:{rs!r} reads={_read_calls!r}')
    assert op._obs is not None, '局外 obs 照常装载(无早退门)'
    rs2 = _run_node(test_context, op, op.act)
    assert not rs2.is_success, f'act 无局外早退门(候选空守卫 fail):{rs2!r}'
    assert dispatches == [], f'局外零派发:{dispatches!r}'

    # ② match 无 gs
    session = _make_session()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op2 = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op2, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op2, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    _read_calls.clear()
    rs3 = _run_node(test_context, op2, op2.observe)
    assert rs3.is_success and _read_calls == [1], (
        f'match 无 gs 局外:观察照常走读链:{rs3!r}')
    rs4 = _run_node(test_context, op2, op2.act)
    assert not rs4.is_success, f'match 无 gs:act 无局外早退门:{rs4!r}'
    assert dispatches == [], '局外零派发'


def test_megastar_observe_standardizes_options_with_dual_source_domain(
        test_context, monkeypatch) -> None:
    """观察标准化门·命中锁(规范 = screens/op-layer.md §1.1 观察标准化
    门):选中半候选含可转换名 → 容器存规范名(idx 原值保留)。覆盖三判
    与双源域(用户裁定 2026-09-22:匹配域 = 盛会之星阵营成员 ∪ 场上持
    「盛会之星星徽」角色):
    - 静态域精确命中(「花火」= 阵营成员);
    - ①形变归一(全角字母数字转半角)后精确命中 + 动态域入员(「Ａｒｃ
      ｈｅｒ」→ Archer,域源 = 前排星徽持有者);
    - ②域内 LCS 兜底(漏「·」单字缺)过阈值命中 + ③边距放行(域内唯
      一过阈值名)+ 动态域开拓者按排归一(后排欢愉形态)。
    红 = 转换门断流(脏名直报容器)/ 归一失效 / LCS 兜底失效 / 动态域
    漏员 / idx 丢失。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        Unit,
    )
    op, match, session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花火'),
                 MegastarOption(idx=1, char_id='Ａｒｃｈｅｒ'),
                 MegastarOption(idx=2, char_id='开拓者欢愉')])
    gs = match.gs
    _sig = ChannelSig(family='obs', actor='test', mode='read')
    gs.observe(gs.front_row, [Unit(char_id='Archer', star=1,
                                   equips=['盛会之星星徽'], slot=1)],
               sig=_sig)
    gs.observe(gs.back_row, [Unit(char_id='开拓者·欢愉', star=1,
                                  equips=['盛会之星星徽'], slot=1)],
               sig=_sig)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'全候选可转换 → 观察 success:{rs!r}'
    assert game_state_of(session).megastar_opts.value == [
        MegastarOption(idx=0, char_id='花火'),
        MegastarOption(idx=1, char_id='Archer'),
        MegastarOption(idx=2, char_id='开拓者·欢愉')], (
        '容器存规范名(转换门产出;idx 原值保留):'
        f'{game_state_of(session).megastar_opts.value!r}')


def test_megastar_observe_standardize_failure_fails_clean(
        test_context, monkeypatch) -> None:
    """观察标准化门·失败锁(规范 = screens/op-layer.md §1.1 观察标准化
    门):候选含未注册乱串或域外注册名 → 转换失败 = observe round_fail
    整函数早退,零写容器零上报零点击(禁带病上报),消息含候选原值列表。
    转置例 = 「火花」(星间旅人,既非盛会之星阵营、gs 亦无穿徽记录;与
    「花火」互为形近误读——域收窄后域外注册名同样不可达)。红 = 脏名
    进容器 / 转换失败静默续跑 / fail 前发生点击派发。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    op, _match, session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='乱码'),
                 MegastarOption(idx=1, char_id='火花')])
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and '标准化' in (rs.status or ''), (
        f'转换失败 = 观察 round_fail:{rs!r}')
    assert '乱码' in (rs.status or '') and '火花' in (rs.status or ''), (
        f'fail 消息含候选原值列表:{rs.status!r}')
    assert game_state_of(session).megastar_opts.value is None, (
        '零写容器(转换失败不落脏名)')
    assert op._obs is None, '零上报(整函数早退,obs 不装载)'
    assert clicks == [] and dispatches == [], (
        f'零点击零派发:{clicks!r} {dispatches!r}')


def test_megastar_observe_standardize_ambiguity_rejected(
        test_context, monkeypatch) -> None:
    """观察标准化门·歧义拒判锁(规范 = screens/op-layer.md §1.1 观察
    标准化门):≥2 候选命中同一规范名(识别质量不足以区分)或单候选
    域内最高/次高分差小于边距 → round_fail 零写零上报。近分腿 = 桩控
    LCS 分值原语(实机短名域近分形态难自然构造,控分直接锁边距分支)。
    红 = 重复命中放行 / 近分放行(共享词素族跨名借分通道回潮)。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption

    # ① 两候选命中同一规范名(「 花火」形变归一即「花火」)
    op, _match, session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花火'),
                 MegastarOption(idx=1, char_id=' 花火')])
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and '标准化' in (rs.status or ''), (
        f'重复命中 = 拒判:{rs!r}')
    assert game_state_of(session).megastar_opts.value is None, '零写容器'

    # ② 单候选最高/次高分差 < 边距(桩控:域内全员同分 → 分差 0;LCS
    # 分值原语单一源 = cw_obs_core,拒判判法全族统一后桩点随迁)。
    op2, _m2, session2, _c2 = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花钬')])
    import sr_od.application.currency_war.kernel.cw_obs_core as _oc
    monkeypatch.setattr(_oc, 'longest_common_subsequence_length',
                        lambda a, b: len(b))
    rs2 = _run_node(test_context, op2, op2.observe)
    assert not rs2.is_success and '标准化' in (rs2.status or ''), (
        f'近分歧义 = 拒判:{rs2!r}')
    assert game_state_of(session2).megastar_opts.value is None, '零写容器'


# ==================== 盛会之星(决策守卫 + 同分确定性)====================


def test_megastar_empty_options_fail_not_blindfire(
        test_context, monkeypatch) -> None:
    """决策输入守卫锁①b(规范 = screens/op-layer.md §1.1 出口③「空候选
    /决策无有效输出零盲发」):选中半访问 + 策略器在位正常 + 候选空
    (读链桩返 [])→ act 具名 round_fail 交回外循环(不计节点重试预算)、
    零派发零点击(守卫在派发前;确认点击不可逆消耗)。红 = 屏内缺省支
    盲选 idx0 派发回潮。"""
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    op, _match, _session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True, options=[],
        pick=CwActionPickMegastarParam(idx=0, reason='stub'),
        stub_action=False)
    assert _run_node(test_context, op, op.observe).is_success, (
        '前置:空候选 = 合法读(标准化门空集放行),观察 success')
    rs = _run_node(test_context, op, op.act)
    assert not rs.is_success and '零盲发' in (rs.status or ''), (
        f'候选空 = 具名 round_fail 零盲发:{rs!r}')
    assert dispatches == [], f'零派发(守卫在派发前):{dispatches!r}'
    assert clicks == [], f'零点击:{clicks!r}'


def test_megastar_out_of_range_idx_asserts_before_click(
        test_context, monkeypatch) -> None:
    """决策值域守卫锁②(规范 = screens/op-layer.md §1.3「非法返回 =
    策略器 bug 响亮暴露,禁静默钳位」):策略器返回越界 idx(真实
    ``CwActionPickMegastarParam(idx=5)``、options 1 元,守卫② 同型放行)
    → AssertionError 传播(守卫③断言,消息含 idx/len/pick 留证)、零
    点击零派发(守卫均在派发前)。红 = 钳位改写回潮 / 越界放行派发。"""
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    op, _match, _session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花火')],
        pick=CwActionPickMegastarParam(idx=5, reason='stub'),
        stub_action=False)
    assert _run_node(test_context, op, op.observe).is_success, (
        '前置:观察 success(obs.options 1 元)')
    with pytest.raises(AssertionError, match='禁钳位'):
        _run_node(test_context, op, op.act)
    assert clicks == [] and dispatches == [], (
        f'断言前零点击零派发:{clicks!r} {dispatches!r}')


def test_megastar_lcs_tie_resolves_domain_first(
        test_context, monkeypatch) -> None:
    """LCS 同分确定性锁(设计钉面 = 标准化门评分循环「固定序,平分取序
    首」):桩控域内全员 LCS 同分(最高/次高分差 0)+ 边距常量桩 0 放行
    (边距拒判本身由歧义锁承重,本锁只锁平分取向的稳定序确定性)→ 转换
    放行且取域序首规范名(静态域 = 注册表序)。红 = 平分结果随内部容
    器序漂移(同分不可确定 = 识别结果不稳定)。"""
    import sr_od.application.currency_war.kernel.cw_obs_core as _oc
    import sr_od.application.currency_war.obs.cw_megastar_obs as mo
    from sr_od.application.currency_war.data.cw_chars import chars_by_faction
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    op, _match, session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花钬')])
    monkeypatch.setattr(_oc, 'longest_common_subsequence_length',
                        lambda a, b: len(b))
    monkeypatch.setattr(mo._MegastarGate, 'MEGASTAR_LCS_AMBIGUITY_MARGIN',
                        0.0)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'边距桩 0 → 同分放行:{rs!r}'
    domain_first = chars_by_faction('盛会之星', include_flows=False)[0].name
    assert game_state_of(session).megastar_opts.value == [
        MegastarOption(idx=0, char_id=domain_first)], (
        f'平分取域序首(固定序确定性):'
        f'{game_state_of(session).megastar_opts.value!r} 域首={domain_first!r}')


# ==================== 盛会之星(候选检测重做:标签带 OCR 定卡 + SIFT 交叉验证)====================


def _ocr_hit(center_x: float) -> SimpleNamespace:
    """OCR map 单 hit 桩值(text → mrl.max.center.x 读取形,与
    ``get_ocr_result_map`` 返回形同构)。"""
    return SimpleNamespace(max=SimpleNamespace(
        center=SimpleNamespace(x=center_x)))


def _stub_screen() -> object:
    """reader 裁片用的假帧(1080p 零图;identify 桩不消费裁片内容)。"""
    import numpy as np
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


def _read_stub_ctx(ocr_map: dict, *, gs: object | None = None) -> SimpleNamespace:
    """reader 离线装配 stub ctx:标签带 area(screen_info 桩,归档 fixture
    实测 rect)+ OCR map 桩 + cw_match.gs(星徽动态域源;None = 不挂 =
    静态域 only;局外无早退支后,gs 缺席态在生产同样可达 reader 此路径)。"""
    from one_dragon.base.geometry.rectangle import Rect
    band = SimpleNamespace(area_name='候选标签带',
                           pc_rect=Rect(420, 300, 1690, 380))
    ctx = SimpleNamespace(
        screen_loader=SimpleNamespace(
            get_screen=lambda name: (SimpleNamespace(area_list=[band])
                                     if name == '货币战争-盛会之星' else None)),
        ocr_service=SimpleNamespace(
            get_ocr_result_map=lambda image, rect, color_range, crop_first:
                dict(ocr_map)),
    )
    if gs is not None:
        ctx.cw_match = SimpleNamespace(gs=gs)
    return ctx


def test_megastar_read_fixture_full_chain(test_context) -> None:
    """fixture 全链锁(候选检测重做批;归档 fixture = 本屏在册存档
    「未选择.webp」,双候选:左 = 星期日 / 右 = 花火):标签带限定 OCR
    定卡 + 逐卡立绘 SIFT 交叉验证全链真跑(真 OCR + 真 SIFT 立绘库,
    零桩)→ 2 选项 = 标准名,xy = 各卡标签中心 x + 在册卡身线 y,
    序左→右。红 = 标签带 area 失效 / OCR 漏读 / SIFT 裁区漂移 /
    标准化门误拒 / 序或坐标错。"""
    import sr_od.application.currency_war.obs.cw_megastar_obs as mo
    screen = test_context.load_screen('货币战争-盛会之星', '未选择')
    opts = mo.read_megastar_options(test_context, screen)
    assert opts is not None and len(opts) == 2, f'双候选定卡:{opts!r}'
    assert [o.char_id for o in opts] == ['星期日', '花火'], (
        f'标准名左→右:{[o.char_id for o in opts]!r}')
    # 标签中心 fixture OCR 实测:星期日 823+199/2≈922、花火 1060+199/2≈1160;
    # 容差 2px 容 OCR 亚像素漂移;y = 在册卡身线 333。
    assert abs(opts[0].xy[0] - 922) <= 2 and opts[0].xy[1] == 333, (
        f'左卡 xy:{opts[0].xy!r}')
    assert abs(opts[1].xy[0] - 1160) <= 2 and opts[1].xy[1] == 333, (
        f'右卡 xy:{opts[1].xy!r}')
    assert [o.idx for o in opts] == [0, 1], 'idx 按 x 左→右 0..N-1'


def test_megastar_read_partial_hit_uses_own_xy(monkeypatch) -> None:
    """部分读回归锁(单候选右槽 xy 随卡):桩 OCR 只喂右卡 hit(单候选在右槽
    布局)→ 该卡 xy = 右卡标签中心 (1160, 333)。旧「idx 枚举序恒映射
    左右槽」模型此处必错(idx0 → 左槽常量 (822,333) 点到空位——名字
    与点击位错位的实锤缺陷形态),坐标随卡自带后该缺陷类整体灭绝
    (退役常量 ``CANDIDATE_LEFT``/``CANDIDATE_RIGHT`` 已不存在)。
    红 = 枚举序映射回潮 / xy 取兜底常量而非标签中心。"""
    import sr_od.application.currency_war.obs.cw_megastar_obs as mo
    ctx = _read_stub_ctx({'盛会之星一花火女士！': _ocr_hit(1160)})
    opts = mo.read_megastar_options(ctx, _stub_screen(),
                                    identify=lambda _crop: '花火')
    assert opts is not None and len(opts) == 1, f'单 hit 定卡:{opts!r}'
    assert opts[0].idx == 0 and opts[0].char_id == '花火', f'{opts[0]!r}'
    assert opts[0].xy == (1160, 333), (
        f'xy = 该卡标签中心 + 卡身线(非左槽常量):{opts[0].xy!r}')


def test_megastar_read_sift_cross_validate(monkeypatch) -> None:
    """SIFT 交叉裁决锁(候选检测重做批模型②,四臂):
    ① SIFT 命中且与 OCR 转换名一致 → 放行;
    ② 不一致 → 置 ``READ_FAILED`` 哨兵,过标准化门判观察失败(识别质量
      不足以区分);
    ③ SIFT 未命中(None = 库缺新角色形态)→ OCR 转换名承重(不硬依赖);
    ④ OCR 名域外 → 原值留列表过门,标准化门既有判法判观察失败。
    红 = 不一致放行 / 未命中误判失败 / 域外名放行。"""
    import sr_od.application.currency_war.obs.cw_megastar_obs as mo
    ctx = _read_stub_ctx({'盛会之星一花火女士！': _ocr_hit(1160)})

    # ① 命中一致 → 放行(SIFT 名即规范名)
    opts = mo.read_megastar_options(ctx, _stub_screen(),
                                    identify=lambda _crop: '花火')
    assert opts is not None and [o.char_id for o in opts] == ['花火'], (
        f'一致放行:{opts!r}')

    # ② 不一致 → 哨兵过门判失败(OCR 花火 vs SIFT 星期日 = 识别质量不足)
    opts2 = mo.read_megastar_options(ctx, _stub_screen(),
                                     identify=lambda _crop: '星期日')
    assert opts2 is not None \
        and [o.char_id for o in opts2] == [mo.READ_FAILED], (
        f'不一致 = 失败哨兵:{opts2!r}')
    assert mo.standardize_megastar_options(opts2, None) is None, (
        '哨兵过标准化门判失败')

    # ③ 未命中 → OCR 转换名承重
    opts3 = mo.read_megastar_options(ctx, _stub_screen(),
                                     identify=lambda _crop: None)
    assert opts3 is not None and [o.char_id for o in opts3] == ['花火'], (
        f'未命中 OCR 承重:{opts3!r}')

    # ④ OCR 名域外 → 原值过门判失败(标准化门既有判法;「乱码」域外由
    #   既有失败锁 test_megastar_observe_standardize_failure_fails_clean
    #   同源)
    ctx4 = _read_stub_ctx({'盛会之星一乱码先生！': _ocr_hit(600)})
    opts4 = mo.read_megastar_options(ctx4, _stub_screen(),
                                     identify=lambda _crop: '花火')
    assert opts4 is not None and [o.char_id for o in opts4] == ['乱码'], (
        f'域外名原值过门:{opts4!r}')
    assert mo.standardize_megastar_options(opts4, None) is None, (
        '域外名过标准化门判失败')


def test_megastar_read_failure_round_fails_clean(
        test_context, monkeypatch) -> None:
    """reader 失败信号裁决锁:真 read 交叉验证反证失败(真 OCR 定卡 +
    identify 桩注入不一致 → ``READ_FAILED`` 哨兵)经真实 observe node →
    标准化门判失败 → round_fail 零写容器零上报零点击(现役失败机制
    保持、调用方零改;失败信号以列表形态过门,fail 消息构造迭代列表)。
    红 = 哨兵被吞成空读成功 / 容器被写 / fail 前点击派发。"""
    import sr_od.application.currency_war.obs.cw_megastar_obs as mo
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar as ms
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)

    def _mismatch_read(ctx, scr):
        # 真 reader + SIFT 桩恒回「星期日」:左卡(星期日)一致放行,
        # 右卡(花火)不一致 → 置 READ_FAILED 哨兵 → 整函数观察失败。
        return mo.read_megastar_options(ctx, scr,
                                        identify=lambda _crop: '星期日')

    op, match, session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True, options=[])
    monkeypatch.setattr(ms, 'read_megastar_options', _mismatch_read)
    # 真实读链输入:fixture 帧(真标签带 OCR;观察 node 读 last_screenshot)
    monkeypatch.setattr(
        op, 'last_screenshot',
        test_context.load_screen('货币战争-盛会之星', '未选择'),
        raising=False)
    session.strategy_state = StrategyState()   # 未选中 → 本访问将选择(读候选)
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and '标准化' in (rs.status or ''), (
        f'reader 失败信号 → observe round_fail:{rs!r}')
    assert mo.READ_FAILED in (rs.status or ''), (
        f'fail 消息含失败哨兵留证:{rs.status!r}')
    assert game_state_of(session).megastar_opts.value is None, '零写容器'
    assert op._obs is None, '零上报(obs 不装载)'
    assert clicks == [] and dispatches == [], (
        f'fail 前零点击零派发:{clicks!r} {dispatches!r}')


def test_megastar_observe_reports_xy_and_standardize_passthrough(
        test_context, monkeypatch) -> None:
    """观察上报 xy 透传锁(选择坐标观察上报收敛,规范 = screens/op-layer.md
    §1.1「选择坐标观察上报」):read 产每卡自带 xy(标签中心 x + 在册
    卡身线 y,候选检测重做批新坐标模型;xy 生产正确性由候选检测重做批
    各锁承重,本锁不重复),经标准化门转换后 xy 原值透传(转换只动名字,
    名字与坐标同进退),经真实观察链落容器后 xy 仍在(动作 op 取点输入)。
    红 = 标准化剥坐标 / 观察链容器终值丢 xy。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        Unit,
    )
    op, match, session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花火', xy=(1160, 333)),
                 MegastarOption(idx=1, char_id='Ａｒｃｈｅｒ', xy=(1400, 333))])
    gs = match.gs
    _sig = ChannelSig(family='obs', actor='test', mode='read')
    gs.observe(gs.front_row, [Unit(char_id='Archer', star=1,
                                   equips=['盛会之星星徽'], slot=1)],
               sig=_sig)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'标准化门放行:{rs!r}'
    container_opts = game_state_of(session).megastar_opts.value
    assert [o.char_id for o in container_opts] == ['花火', 'Archer'], (
        f'容器存规范名:{container_opts!r}')
    assert [o.xy for o in container_opts] == [(1160, 333), (1400, 333)], (
        f'标准化透传 xy(转换只动名字,坐标同进退落容器):'
        f'{[o.xy for o in container_opts]!r}')


def test_megastar_pick_op_asserts_container_xy_before_click(
        test_context, monkeypatch) -> None:
    """动作 op 容器取点守卫锁(action_ops.md §1 增补 5 + op-layer.md §1.3):
    选中半(need_select=True)点击坐标 = 容器 ``megastar_opts[param.idx].xy``
    ——容器缺席/空、下标越界、元素缺 xy 三臂均 AssertionError 响亮暴露
    且零点击(守卫在选中点击与确认点击之前;禁控制流回退、禁 screen_info
    二次取点)。红 = 静默跳过选中(旧 target None 消极臂回潮)/ 坐标现算
    回退 / 越界钳位 / 守卫前发生点击。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_megastar_action as pm
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickMegastarParam,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_env import (
        OverlayPickExecEnv,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_pick_megastar_action import (
        CwActionPickMegastarOp,
    )

    monkeypatch.setattr(pm, 'time', SimpleNamespace(sleep=lambda *_: None))

    def _run_arm(session, *, idx: int) -> list[tuple[int, int]]:
        """三臂公共装配:match 桂挂 session → 容器供给口可达;controller
        点击记录;env 零机械下标(取点键 = param.idx)+ need_select=True;
        返回点击序。"""
        monkeypatch.setattr(test_context, 'cw_match',
                            SimpleNamespace(session=session), raising=False)
        clicks: list[tuple[int, int]] = []
        monkeypatch.setattr(test_context.controller, 'mouse_move',
                            lambda p, **k: None, raising=False)
        monkeypatch.setattr(test_context.controller, 'click',
                            lambda p, **k: clicks.append((p.x, p.y)),
                            raising=False)
        stub_op = SimpleNamespace(ctx=test_context)
        env = OverlayPickExecEnv(op=stub_op, need_select=True)
        op = CwActionPickMegastarOp(test_context,
                                    CwActionPickMegastarParam(idx=idx),
                                    env=env)
        with pytest.raises(AssertionError):
            op.run()
        return clicks

    # ① 容器缺席/空(megastar_opts 未写)
    session1 = StrategySession()
    clicks1 = _run_arm(session1, idx=0)
    assert clicks1 == [], f'容器缺席臂零点击:{clicks1!r}'
    # ② 下标越界(容器 1 元,param.idx=5)
    session2 = StrategySession()
    _sig = ChannelSig(family='logic_action', actor='test', mode='compute')
    game_state_of(session2).write_logic(
        game_state_of(session2).megastar_opts,
        [MegastarOption(idx=0, char_id='花火', xy=(822, 333))],
        produced_by='test', sig=_sig)
    clicks2 = _run_arm(session2, idx=5)
    assert clicks2 == [], f'越界臂零点击:{clicks2!r}'
    # ③ 元素缺 xy(观察上报未产坐标)
    session3 = StrategySession()
    game_state_of(session3).write_logic(
        game_state_of(session3).megastar_opts,
        [MegastarOption(idx=0, char_id='花火')],
        produced_by='test', sig=_sig)
    clicks3 = _run_arm(session3, idx=0)
    assert clicks3 == [], f'缺 xy 臂零点击:{clicks3!r}'
