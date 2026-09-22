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
- **派发即终结锁**(遭遇,迭代 2026-09-21-event-refresh-unify-supply-pick
  3.3 扩围):选卡确认链派发后 round_success 终结交回(零重入裁决轮);
  空候选/局外 = 零点击终结交回(禁盲选派发确认——不可逆消耗);闸拒绝
  重调落选卡后同样终结。chosen_encounter 发射即写契约(动作侧 report
  函数级)= test_cw_screen_report_ports 承重,本文件不重复。
- **奖励兑现回调锁**(遭遇,kernel ``claim_encounter_reward``):双证
  判遭遇(node 镜像 token ∧ settlement_ring 尾行 node_type)∧
  progress_delta>0 单判;兑现写 ``encounter_reward_claimed`` 且 chosen
  随即清(单次消费,重触发天然幂等);单腿不合/未达标/删失/无 chosen
  = 不写不清。
- **盛会之星族锁**(节点循环形态):完成门/懒读保真/防重入旗标/chosen
  写端(选择点留守)/局外交回(无 match/gs 零读屏零派发)/观察标准化门
  (双源域命中·转换失败·歧义拒判·LCS 同分取域序首确定性)/决策守卫
  (候选空 fail 零盲发·idx 越界断言)各一锁,语义见各 docstring。

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
      首派发选中时点落容器。
    红 = 重入再触发选中 / 门 miss 不复位 / 缺席态炸错或冷建 / chosen 断流。"""
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


# ==================== 盛会之星(局外交回 + 观察标准化门)====================


def test_megastar_out_of_match_zero_read_and_return(
        test_context, monkeypatch) -> None:
    """局外交回锁(正本 = screens/op-layer.md §1.1「画面 op 不支持局外
    单独调用」,判式 = match/gs 双缺宽判,对齐投资环境在飞双判):选中半
    访问 + 无 match / match 无 gs → observe 零读屏(读链桩零调用、零
    obs 装载零上报)、act round_success 局外交回(零决策零点击)、零派发。
    红 = 局外仍读屏 / act 盲走决策体 / 交回回潮 fail。"""
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
    assert rs.is_success and _read_calls == [], (
        f'无 match 局外:观察零读屏:{rs!r} reads={_read_calls!r}')
    assert op._obs is None, '局外零 obs 装载零上报'
    rs2 = _run_node(test_context, op, op.act)
    assert rs2.is_success and '局外交回' in (rs2.status or ''), (
        f'act 局外交回(零决策零点击):{rs2!r}')
    assert dispatches == [], f'局外零派发:{dispatches!r}'

    # ② match 无 gs(宽判式第二腿)
    session = _make_session()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op2 = ms.CwScreenMegastar(test_context)
    monkeypatch.setattr(op2, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op2, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    _read_calls.clear()
    rs3 = _run_node(test_context, op2, op2.observe)
    assert rs3.is_success and _read_calls == [], (
        f'match 无 gs 局外:观察零读屏:{rs3!r}')
    rs4 = _run_node(test_context, op2, op2.act)
    assert rs4.is_success and '局外交回' in (rs4.status or ''), (
        f'match 无 gs:act 局外交回:{rs4!r}')
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
    import sr_od.application.currency_war.obs.cw_megastar_obs as mo
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

    # ② 单候选最高/次高分差 < 边距(桩控:域内全员同分 → 分差 0)
    op2, _m2, session2, _c2 = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花钬')])
    monkeypatch.setattr(mo, 'longest_common_subsequence_length',
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
    import sr_od.application.currency_war.obs.cw_megastar_obs as mo
    from sr_od.application.currency_war.data.cw_chars import chars_by_faction
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    op, _match, session, _calls = _make_megastar(
        test_context, monkeypatch, in_node=True,
        options=[MegastarOption(idx=0, char_id='花钬')])
    monkeypatch.setattr(mo, 'longest_common_subsequence_length',
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
