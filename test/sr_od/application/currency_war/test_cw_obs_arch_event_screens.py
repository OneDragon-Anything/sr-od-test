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
  按原评分选卡;重调仍建议刷新(闸数据不一致)→ 零点击终结交回。
- **重入裁决时机锁**(遭遇):确认已发 → 锚在 = 未落地 → 不写 chosen、
  清标志重走;锚不在 = 落地 → 此刻才写 chosen_encounter + success 交回。
- **盛会之星族锁**(节点循环形态):完成门/懒读保真/防重入旗标/chosen
  写端(选择点留守)各一锁,语义见各 docstring。

驱动方式 = 真类实例(构造走 __init__)+ 读链/门/机械点击链桩化,节点
函数直驱(run_node 外壳)。
"""
from __future__ import annotations

from types import SimpleNamespace

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
    # 统一动作工厂批4:遭遇确认链体迁 pick op 模块——safe_click/emit_overlay_
    # confirm 桩随体迁移(替身跟随被迁体;桩语义不变:机械点击空操作、确认
    # 链回指定轮次结果);机械等待替身(mock 画面瞬时切换,等待纯属空睡)。
    import sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action as pick_mod
    monkeypatch.setattr(pick_mod, 'safe_click', lambda o, pt, **k: None)
    monkeypatch.setattr(pick_mod, 'time', SimpleNamespace(sleep=lambda *_: None))
    monkeypatch.setattr(em.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(pick_mod, 'emit_overlay_confirm',
                        lambda o, **k: op.round_retry('stub-confirm'))
    # (record_event_choice 替身桩已随删除波 1 移除——exogenous 写入端退役,
    #  encounter 模块不再引用 telemetry;(gs_view 桩同批移除——模块本体
    #  随波 5b 双删,桩对象不存在。))
    return op, match, session


def _make_megastar(test_context, monkeypatch, *, in_node: bool,
                   options: list | None = None):
    """盛会之星真类装配(两 node 形态,迭代 2026-09-18-screen-op-flat-report):
    门桩 + 候选读链桩(观察 node 读屏函数注入点)+ 动作体调用计数。
    旗标宿主 = 策略器 StrategyState(经 session.strategy_state 通道)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_megastar as ms,
    )

    session = _make_session()
    match = SimpleNamespace(session=session)
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


def test_encounter_act_round_wait_and_reentry_chosen(
        test_context, monkeypatch) -> None:
    """决策动作 node 锁 + chosen 写时机锁:零参决策 → 点卡 + 确认机械交回
    → round_wait 推进循环(不计节点重试预算);chosen_encounter = 重入
    裁决点留守写端——确认未落地(锚在)不写、清标志重走;落地(锚不在)
    此刻才写 + success 交回。红 = 循环推进回退为计预算 retry / 落地前写
    (幻影 chosen)/ 落地后断流。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
            EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])]
    op, _match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionPickEncounterParam(idx=1, reason='stub'))
    _run_node(test_context, op, op.observe)
    # ① 决策动作轮:确认机械交回 → round_wait;pending 置位;chosen 不写
    rs = _run_node(test_context, op, op.act)
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'循环推进 = round_wait(不计节点重试预算):{rs!r}')
    assert op._confirm_pending == (opts, 1), (
        f'确认已发 → (options, idx) 快照置位:{op._confirm_pending!r}')
    assert game_state_of(session).chosen_encounter.value is None, (
        '确认未落地轮不写 chosen(时点 = 重入裁决)')
    # ② 未落地重走(锚在):清标志 → 重选重确认 → 仍不写
    rs2 = _run_node(test_context, op, op.act)
    assert rs2.result == OperationRoundResultEnum.WAIT, f'未落地重走机械交回:{rs2!r}'
    assert game_state_of(session).chosen_encounter.value is None, (
        '锚在(未落地)重走仍不写 chosen')
    # ③ 落地(锚不在):此刻才写 chosen + success 交回
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    rs3 = _run_node(test_context, op, op.act)
    assert rs3.is_success and '重入观察裁决' in (rs3.status or ''), (
        f'落地 → success 交回:{rs3!r}')
    assert game_state_of(session).chosen_encounter.value == (3, '随机4费×3'), (
        'chosen_encounter = 重入裁决点留守写端(落地后值才可信)')
    assert op._confirm_pending is None, '裁决消费待裁决快照'


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
    assert op._confirm_pending is None, '终结轮不进入确认链'


def test_encounter_refresh_gate_rejects_zero_and_none(
        test_context, monkeypatch) -> None:
    """刷新闸拒绝锁:建议刷新但剩余 0 / None(未观察)→ 零点击不按刷新
    终结,重调一次决策按原评分选卡(确认链照发 round_wait 推进)。
    红 = 闸失守重刷 / 拒绝轮漏选卡。"""
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
            EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])]
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    # ① 剩余 0 → 零点击,重调落选卡
    op, _match, session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionPickEncounterParam(idx=1, reason='rescore'),
        picks=[CwActionRefreshNodeOptionsParam(reason='stub')],
        cnt=(0, (771, 899)))
    _run_node(test_context, op, op.observe)
    assert game_state_of(session).encounter_refresh_left.value == 0, (
        '前置:观察轮摄入 left=0')
    rs = _run_node(test_context, op, op.act)
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'拒绝轮重调落选卡 → 确认链 round_wait 推进:{rs!r}')
    assert clicks == [], f'剩余 0 = 刷新钮零点击:{clicks!r}'
    assert op._confirm_pending == (opts, 1), (
        f'重调一次决策按原评分选卡:{op._confirm_pending!r}')
    assert len(dispatches) == 1, '选卡派发照发'
    # ② 剩余 None(读缺未摄入)→ 零点击,重调落选卡
    op2, _m2, session2 = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionPickEncounterParam(idx=0, reason='rescore'),
        picks=[CwActionRefreshNodeOptionsParam(reason='stub')],
        cnt=None)
    _run_node(test_context, op2, op2.observe)
    assert game_state_of(session2).encounter_refresh_left.value is None, (
        '前置:读缺跳写,容器 left 未写')
    rs2 = _run_node(test_context, op2, op2.act)
    assert rs2.result == OperationRoundResultEnum.WAIT, (
        f'None 拒绝轮重调落选卡:{rs2!r}')
    assert clicks == [], f'None = 刷新钮零点击:{clicks!r}'
    assert op2._confirm_pending == (opts, 0), 'None 拒绝轮按原评分选卡'


def test_encounter_refresh_gate_mismatch_zero_click_terminal(
        test_context, monkeypatch) -> None:
    """闸数据不一致防御锁:拒绝后重调仍返回刷新建议(策略未消费剩余闸)
    → 不再循环,零点击终结交回(外循环重进 = 入口重建重试观察)。
    红 = 拒绝-重调环回潮(防循环面)或漏处置死循环。"""
    clicks, dispatches = _refresh_fixture(test_context, monkeypatch)
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])]
    op, _match, _session = _make_encounter(
        test_context, monkeypatch, in_screen=True, options=opts,
        pick=CwActionRefreshNodeOptionsParam(reason='stub-again'),
        picks=[CwActionRefreshNodeOptionsParam(reason='stub')],
        cnt=(0, (771, 899)))
    _run_node(test_context, op, op.observe)
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '终结交回' in (rs.status or ''), (
        f'重调仍建议刷新 → 零点击终结交回:{rs!r}')
    assert clicks == [], '零点击'
    assert dispatches == [], '零选卡派发'
    assert op._confirm_pending is None, '不进入确认链'


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
      首派发选中时点落容器。
    红 = 重入再触发选中 / 门 miss 不复位 / 缺席态炸错或冷建 / chosen 断流。"""
    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as reg_mod
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_megastar as ms,
    )

    session = StrategySession()
    st = StrategyState()
    session.strategy_state = st
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(
            decide_megastar=lambda: SimpleNamespace(
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
                        lambda ctx, scr: [SimpleNamespace(char_id='花火')])
    monkeypatch.setattr(ms, 'area_center',
                        lambda ctx, name, screen=None: SimpleNamespace(
                            x=822, y=333))

    # 派发桩:捕获每次派发的 need_select(选中半触发标志;选中点击的
    # 机械行为锁 = test_cw_unified_action_4 巨星 op 锁,本锁只锁画面 op
    # 的防重入语义)。
    dispatches: list[bool] = []

    class _StubPickOp:
        def __init__(self, env) -> None:
            self.env = env

        def execute(self) -> bool:
            dispatches.append(bool(getattr(self.env, 'need_select', False)))
            return True

    monkeypatch.setattr(reg_mod, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(env))
    # 观察注入(观察 node 读屏函数注入点):驱动观察 node 装载 obs
    assert op.observe().is_success, '在屏观察 success'
    # ① 首派发:触发选中(need_select=True)+ 发射即置位 + chosen 留守写端落容器
    op._do_action()
    assert dispatches == [True], f'首派发触发选中半:{dispatches!r}'
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
    assert session2.strategy_state is None, '缺席态写跳过,执行层不冷建'
