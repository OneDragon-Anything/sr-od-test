"""节点循环族 8 屏两 node 形态锁(迭代 2026-09-18-screen-op-flat-report)。

锁的语义(测试纪律:只锁新形态的核心约定,先例 = test_cw_obs_arch_event_
screens.py 盛会之星段;report 函数级契约由 test_cw_screen_report_ports 锁
承重,本文件不重复):

- **观察上报接线锁**(表驱动;命运卜者双域拆独立锁):观察 node 读链桩化 →
  驱动 observe →
  report 经屏文件落容器(容器终值);盛会之星接线由 obs_arch_event_screens
  同文件锁承重(懒读保真,不在本表);
- **入口门语义锁**(带门四屏):门 miss = round_fail 交回外循环重判,
  文案沿用现役,且不进读链(obs 不装载);
- **chosen 写时机锁**(祈愿试炼代表):确认已发 → 标识不在 = 选卡落地
  → 此刻才写 chosen_wish + success 交回;标识在 = 未落地 → 不写、重走
  (chosen_* 动作事实边界留守重入裁决点);
- **决策动作 node 锁**(银狼策划,无门单发型):决策从容器零参读
  (决策调用形态不变)→ 组装 equip(腿型载荷 classify_planner_leg)→
  点卡链派发 → 派发即 round_success 终结(零重入裁决轮;即时上报迭代
  2026-09-21-pick-planner-equip-immediate-report。原装备三选一代表锁
  随该屏误判退役删除)。

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

from sr_od.application.currency_war.kernel.cw_events import PartnerOption, PlannerOption
from sr_od.application.currency_war.kernel.cw_game_state import (
    ExpertInvitePayload,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

_FRAME = object()   # 稳定帧哨兵(读链桩只验传递不断言内容)

_CW_SCREEN_PKG = 'sr_od.application.currency_war.operations.cw_screen'


class _StubOcr:
    """ocr_service 桩(get_ocr_result_map/list 程序化回值)。"""

    def __init__(self, map_result: dict | None = None,
                 list_result: list | None = None) -> None:
        self._map = map_result or {}
        self._list = list_result or []

    def get_ocr_result_map(self, image, rect=None, color_range=None,
                           crop_first=False):
        return self._map

    def get_ocr_result_list(self, image, crop_first=False):
        return self._list


def _mrl(x: float, y: float) -> SimpleNamespace:
    """OCR 结果行桩(max.center.x/y 消费面)。"""
    return SimpleNamespace(max=SimpleNamespace(center=SimpleNamespace(x=x, y=y)))


def _make_match(session: StrategySession, **strategy) -> SimpleNamespace:
    """局内 match 桩(session 挂容器;策略入口按屏注入零参决策桩)。"""
    match = SimpleNamespace(session=session, strategy=SimpleNamespace(**strategy))
    match.gs = game_state_of(session)
    return match


def _setup_bookcard(op, monkeypatch) -> None:
    """星徽秘典读链桩(全屏 OCR「X星徽」→ 阵营名 + x 中心)。"""
    monkeypatch.setattr(
        op.ctx, 'ocr_service',
        _StubOcr(list_result=[SimpleNamespace(data='列车同行星徽', x=700,
                                              y=100, w=120, h=30)]),
        raising=False)


def _setup_expert(op, monkeypatch) -> None:
    """专家邀请函读链桩(卡羁绊解析模块符号 + 羁绊面板读口)。"""
    from sr_od.application.currency_war.obs import cw_observation
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_expert_invite as mod,
    )
    monkeypatch.setattr(mod, '_resolve_card_bonds',
                        lambda ctx, screen, a: '仙舟' if a == '卡-1' else None)
    monkeypatch.setattr(cw_observation, 'read_board',
                        lambda ctx, screen: {'仙舟': 3})


# ==================== 观察上报接线锁(表驱动)====================

# 屏键 → (模块名, 类名, 装配钩子(op, monkeypatch), 期望容器字段, 期望终值)
_OBS_ROWS = {
    'partner':
        ('cw_screen_partner', 'CwScreenPartner',
         lambda op, mp: (mp.setattr(op, '_read_candidates',
                                    lambda s: [('护盾', 800, 360),
                                               ('能量', 1100, 360)]),
                         mp.setattr(op, '_identify_portraits',
                                    lambda s, c: ['charA', 'charB'])),
         'partner_opts', [PartnerOption(idx=0, char_id='charA'),
                          PartnerOption(idx=1, char_id='charB')]),
    'planner':
        ('cw_screen_yinlang', 'CwScreenYinLang',
         lambda op, mp: mp.setattr(op.ctx, 'ocr_service', _StubOcr(
             # 桩文本位置 = 建档两卡 rect 中心(观察过滤 = 中心点落入
             # area rect,坐标单一真相源回 yml;银狼升星记账批 §2.4)。
             map_result={'左卡文': _mrl(795, 317), '右卡文': _mrl(1305, 317)}),
             raising=False),
         'planner_opts', [PlannerOption(idx=0, text='左卡文'),
                          PlannerOption(idx=1, text='右卡文')]),
    'wish_trial':
        ('cw_screen_wish_trial', 'CwScreenWishTrial',
         lambda op, mp: mp.setattr(op.ctx, 'ocr_service', _StubOcr(
             list_result=[SimpleNamespace(data='objective甲', x=600, y=300,
                                          w=100, h=30)]), raising=False),
         'wish_trial_opts', ['objective甲', '', '']),
    'bookcard':
        ('cw_screen_bookcard', 'CwScreenBookcard',
         _setup_bookcard, 'star_tome_opts', ['列车同行']),
    'expert_invite':
        ('cw_screen_expert_invite', 'CwScreenExpertInvite',
         _setup_expert, 'expert_invite',
         ExpertInvitePayload(card_bonds=['仙舟', None, None, None],
                             board={'仙舟': 3})),
}


@pytest.mark.parametrize('screen_key', [
    'partner', 'planner', 'wish_trial', 'bookcard', 'expert_invite'])
def test_observe_reports_container_per_screen(test_context, monkeypatch,
                                              screen_key: str) -> None:
    """观察上报接线锁(表驱动五屏;命运卜者双域锁拆独立 = 下一锁):
    观察 node 读链桩化 → observe success → report 经屏文件落容器
    (容器终值逐位 = 现役写点转录值)+ obs 挂实例属性。红 = 接线断流 /
    容器终值漂移 / obs 未装载。"""
    import importlib

    mod_name, cls_name, setup, field, expected = _OBS_ROWS[screen_key]
    mod = importlib.import_module(f'{_CW_SCREEN_PKG}.{mod_name}')
    op = getattr(mod, cls_name)(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    if cls_name in ('CwScreenPartner', 'CwScreenWishTrial', 'CwScreenBookcard',
                    'CwScreenExpertInvite'):
        # 带门屏:门桩放行(门 miss 语义由下一锁承重)
        monkeypatch.setattr(op, 'round_by_find_area',
                            lambda s, sc, a, **k: _Area(True), raising=False)
    setup(op, monkeypatch)

    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        _make_match(session), raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'{screen_key}: 观察 success:{rs!r}'
    gs = game_state_of(session)
    assert getattr(gs, field).value == expected, (
        f'{screen_key}: report 落容器(容器终值):'
        f'{getattr(gs, field).value!r}')
    assert op._obs is not None, f'{screen_key}: obs 挂实例属性'


def test_fortune_observe_reports_dual_domain(test_context, monkeypatch) -> None:
    """命运卜者观察上报锁(双域,坐标随报条款):表驱动 5 元组不容双域
    拆独立锁——观察 node 读链桩化(OCR + area_center 读桩回定值,恒稳
    断言不读真实建档)→ observe success → report 双写 fortune_opts /
    fortune_opts_xy(同门同序等长)+ obs 挂实例属性。红 = 接线断流 /
    坐标域未随观察上报 / 双域终值漂移。"""
    from one_dragon.base.geometry.point import Point
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_fortune as mod,
    )

    op = mod.CwScreenFortune(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op.ctx, 'ocr_service', _StubOcr(
        map_result={'甲文': _mrl(510, 350), '乙文': _mrl(900, 350)}),
        raising=False)
    # area 读桩回定值(恒稳;不读真实建档,桩序 = 卡-强化1/2/3)。
    monkeypatch.setattr(
        mod, 'area_center',
        lambda ctx, name, screen_name: Point(
            {'卡-强化1': 511, '卡-强化2': 901, '卡-强化3': 1291}[name], 481))
    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        _make_match(session), raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'fortune: 观察 success:{rs!r}'
    gs = game_state_of(session)
    assert gs.fortune_opts.value == ['甲文', '乙文', ''], (
        f'fortune: report 落名字域:{gs.fortune_opts.value!r}')
    assert gs.fortune_opts_xy.value == [(511, 481), (901, 481), (1291, 481)], (
        f'fortune: report 落坐标域(同门双写):{gs.fortune_opts_xy.value!r}')
    assert op._obs is not None, 'fortune: obs 挂实例属性'


def test_wish_observe_reports_dual_domain(test_context, monkeypatch) -> None:
    """祈愿试炼观察上报锁(双域,选择坐标观察上报条款):观察 node 读链
    桩化(OCR 桩 + 门桩放行,恒稳断言不读真实建档)→ observe success →
    report 双写 wish_trial_opts / wish_trial_opts_xy(同门同序等长;坐标
    = CARD_XS 桶锚 + CARD_Y 观察期一次解出,值锚 660/340 槽常量)+
    obs 挂实例属性。红 = 接线断流 / 坐标域未随观察上报 / 双域终值漂移。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wish_trial as mod,
    )

    op = mod.CwScreenWishTrial(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(True), raising=False)
    monkeypatch.setattr(op.ctx, 'ocr_service', _StubOcr(
        list_result=[SimpleNamespace(data='objective甲', x=600, y=300,
                                     w=100, h=30)]), raising=False)
    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        _make_match(session), raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'wish: 观察 success:{rs!r}'
    gs = game_state_of(session)
    assert gs.wish_trial_opts.value == ['objective甲', '', ''], (
        f'wish: report 落名字域:{gs.wish_trial_opts.value!r}')
    assert gs.wish_trial_opts_xy.value == [
        (660, 340), (960, 340), (1260, 340)], (
        f'wish: report 落坐标域(同门双写):{gs.wish_trial_opts_xy.value!r}')
    assert len(gs.wish_trial_opts_xy.value) == len(gs.wish_trial_opts.value), (
        '坐标域与名字域同序等长')
    assert op._obs is not None, 'wish: obs 挂实例属性'
    assert op._obs.option_points == gs.wish_trial_opts_xy.value, (
        'obs 坐标与容器同源')


# ==================== 入口门语义锁(带门四屏)====================

_GATE_ROWS = [
    # (屏键, 门 miss 现役文案)
    ('partner', '非选择伙伴屏'),
    ('wish_trial', '非祈愿试炼屏'),
    ('bookcard', '非星徽秘典画面'),
    ('expert_invite', '选卡入口:邀请函弹窗未现'),
]


@pytest.mark.parametrize('screen_key, expect_status', _GATE_ROWS)
def test_entry_gate_miss_fails_round(test_context, monkeypatch, screen_key,
                                     expect_status: str) -> None:
    """入口门语义锁:门 miss = round_fail 早退(文案沿用现役,交回外循环
    重判),且不进读链(obs 不装载)。红 = 门失效 / 文案漂移 / miss 后
    仍读屏装 obs。"""
    import importlib

    mod_name, cls_name = _OBS_ROWS[screen_key][0], _OBS_ROWS[screen_key][1]
    mod = importlib.import_module(f'{_CW_SCREEN_PKG}.{mod_name}')
    op = getattr(mod, cls_name)(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(False), raising=False)
    _read_calls: list[int] = []
    if screen_key == 'partner':
        monkeypatch.setattr(op, '_read_candidates',
                            lambda s: _read_calls.append(1) or [])
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and expect_status in (rs.status or ''), (
        f'{screen_key}: 门 miss 文案沿用现役:{rs!r}')
    assert op._obs is None, f'{screen_key}: 门早退不装载 obs'
    if screen_key == 'partner':
        assert _read_calls == [], '门早退不进读链'


# ==================== chosen 写时机锁(祈愿试炼代表)====================

def test_wish_chosen_written_at_reentry_adjudication_only(
        test_context, monkeypatch) -> None:
    """chosen 写时机锁(动作事实边界:chosen_* 值在「确认已落地」重入
    观察后才可信,写端留守重入裁决点):
    - 确认已发 + 标识仍在(= 未落地)→ 不写,清标志重走(决策 + 点卡 +
      确认机械交回);
    - 确认已发 + 标识不在(= 选卡落地)→ 此刻才写 chosen_wish + success
      交回。
    红 = 落地前写(幻影 chosen)/ 落地后断流 / 未落地分支丢失。"""
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    from sr_od.application.currency_war.kernel.cw_screen_report.wish_trial import (
        CwScreenWishTrialObs,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickWishTrialParam,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wish_trial as mod,
    )

    session = StrategySession()
    pick_stub = CwActionPickWishTrialParam(idx=0, reason='stub')
    monkeypatch.setattr(
        test_context, 'cw_match',
        _make_match(session, decide_wish_trial=lambda: pick_stub),
        raising=False)
    op = mod.CwScreenWishTrial(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    op._obs = CwScreenWishTrialObs(on_screen=True,
                                   options=['累计刷新10次', ''],
                                   screen=_FRAME)   # obs 注入(观察 node 产物形态)
    # pick-op-unify:选卡+确认机械链迁入 CwActionPickWishTrialOp;本锁桩
    # 派发捕获(param/env)断言决策半产物,机械链行为锁 =
    # test_cw_unified_action_4 祈愿 op 锁。
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
    # ① 未落地:标识仍在 → 不写 chosen,重走(决策 + 派发选卡确认链)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(True), raising=False)
    op._confirm_pending = (['累计刷新10次', ''], 0)
    rs = _run_node(test_context, op, op.act)
    assert game_state_of(session).chosen_wish.value is None, (
        '标识仍在(未落地)→ chosen 不写')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'未落地重走:round_wait 机械交回:{rs!r}')
    assert len(dispatches) == 1, f'未落地重走:选卡确认链恰一次派发:{dispatches!r}'
    assert dispatches[0].param.idx == 0, '零参决策 idx=0'
    assert dispatches[0].param is pick_stub, (
        '派发 param = 策略产实例(直发零重建,reason 归因不丢)')
    assert (dispatches[0].env.target is None
            and dispatches[0].env.idx is None), (
        'env 仅携 op(定位点 = 观察上报坐标,动作 op 自容器 '
        'wish_trial_opts_xy 取,零 env 坐标喂)')
    assert op._confirm_pending == (['累计刷新10次', ''], 0), (
        '重走后待裁决快照重置(本轮选择)')
    # ② 落地:标识不在 → 此刻才写 chosen + success 交回
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(False), raising=False)
    rs2 = _run_node(test_context, op, op.act)
    assert rs2.is_success and '祈愿试炼选卡已确认' in (rs2.status or ''), (
        f'落地 → success 交回:{rs2!r}')
    assert game_state_of(session).chosen_wish.value == '累计刷新10次', (
        'chosen_wish = 重入裁决点留守写端(落地后值才可信)')


# ==================== 祈愿试炼决策出口锁(守卫①②③ + 直发)====================

def _setup_wish_act(test_context, monkeypatch, session, decide):
    """wish act 锁公共装配(fortune 锁同构):match 桩挂零参决策桩
    (decide=None = cw_match None 局外态)+ obs 注入 + 注册表派发捕获。"""
    from sr_od.application.currency_war.kernel.cw_screen_report.wish_trial import (
        CwScreenWishTrialObs,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wish_trial as mod,
    )

    monkeypatch.setattr(
        test_context, 'cw_match',
        None if decide is None else _make_match(session, decide_wish_trial=decide),
        raising=False)
    op = mod.CwScreenWishTrial(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    op._obs = CwScreenWishTrialObs(on_screen=True,
                                   options=['甲objective', '乙objective', ''],
                                   option_points=[(660, 340), (960, 340),
                                                  (1260, 340)],
                                   screen=_FRAME)   # obs 注入(观察 node 产物形态)
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
    return op, dispatches


def test_wish_act_no_match_ends_success_without_decision_or_click(
        test_context, monkeypatch):
    """守卫①(局外臂,op-layer.md §1.1「画面 op 不支持局外单独调用」):
    cw_match=None → act round_success(消息含「零决策零点击终结交回」)、
    零派发零点击、_confirm_pending 保持未置位;局外臂先于任何决策消费
    (遭遇屏先例同款)。红 = 局外兜底决策路径回潮(盲发首卡)。"""
    session = StrategySession()
    op, dispatches = _setup_wish_act(test_context, monkeypatch, session, None)
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '零决策零点击终结交回' in (rs.status or ''), (
        f'守卫①:局外零决策零点击 round_success 终结交回:{rs!r}')
    assert dispatches == [], '守卫①:零派发'
    assert op._confirm_pending is None, '守卫①:确认未置位(零点击)'


def test_wish_act_guard_invalid_decision_fails_without_dispatch(
        test_context, monkeypatch):
    """守卫②(返回契约):decide_wish_trial 返 None/词表外(SimpleNamespace)
    两子态合一锁 → act 具名 round_fail(消息含「决策无有效输出」,留证
    原值)、零派发零点击、_confirm_pending 保持未置位。红 = 守卫缺失盲发
    / 钳位回潮 / 策略异常被吞。"""
    for stub in (None, SimpleNamespace(idx=0, reason='stub')):
        session = StrategySession()
        op, dispatches = _setup_wish_act(
            test_context, monkeypatch, session, lambda s=stub: s)
        rs = _run_node(test_context, op, op.act)
        assert not rs.is_success and '决策无有效输出' in (rs.status or ''), (
            f'守卫②({stub!r}):具名 round_fail 零盲发:{rs!r}')
        assert dispatches == [], f'守卫②({stub!r}):零派发'
        assert op._confirm_pending is None, (
            f'守卫②({stub!r}):确认未置位(零点击)')


def test_wish_act_guard_idx_out_of_range_asserts(
        test_context, monkeypatch):
    """守卫③(值域):真词表类 idx=3(槽常量现值 3,越界)→
    AssertionError 传播(守卫断言响亮暴露,禁钳位)、零派发零点击。
    红 = 钳位回潮。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickWishTrialParam,
    )

    session = StrategySession()
    op, dispatches = _setup_wish_act(
        test_context, monkeypatch, session,
        lambda: CwActionPickWishTrialParam(idx=3))
    with pytest.raises(AssertionError, match='越界'):
        _run_node(test_context, op, op.act)
    assert dispatches == [], '守卫③:零派发'
    assert op._confirm_pending is None, '守卫③:确认未置位(零点击)'


def test_wish_act_dispatches_strategy_param_env_op_only(
        test_context, monkeypatch):
    """正路形态:真词表类 idx=1 → 恰一次派发且派发 param 即策略产实例
    (直发零重建,reason 归因不丢)、env 仅携 op(零 target 零 idx——
    坐标随报条款,点击坐标 = 动作 op 自容器 wish_trial_opts_xy 读)、
    rs = round_wait、_confirm_pending 置位快照 = 本轮选择。红 = 派发
    实例重建 / env 坐标喂回潮。"""
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickWishTrialParam,
    )

    session = StrategySession()
    pick = CwActionPickWishTrialParam(idx=1, reason='stub')
    op, dispatches = _setup_wish_act(
        test_context, monkeypatch, session, lambda: pick)
    rs = _run_node(test_context, op, op.act)
    assert len(dispatches) == 1, f'恰一次派发:{dispatches!r}'
    assert dispatches[0].param is pick, '派发 param = 策略产实例(直发零重建)'
    assert dispatches[0].env.target is None and dispatches[0].env.idx is None, (
        'env 仅携 op(零 target 零 idx,停喂)')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'round_wait 推进循环(确认未落地轮重走):{rs!r}')
    assert op._confirm_pending == (['甲objective', '乙objective', ''], 1), (
        '确认已发待重入裁决置位(快照 = 本轮选择)')


# ==================== 决策动作 node 锁(银狼策划代表)====================

def test_planner_act_decides_leg_and_dispatch_terminal(
        test_context, monkeypatch) -> None:
    """决策动作 node 锁(银狼策划,即时上报迭代 2026-09-21-pick-planner-
    equip-immediate-report design §2.1):零参决策 → 腿型判定单源
    ``classify_planner_leg`` → env 携腿型载荷 → 选卡确认链派发即
    ``round_success`` 终结(零重入裁决轮、零证据闩存证——效果腿在动作 op
    确认点击后即时上报)。
    红 = 腿型载荷断流 / 派发后回退 wait(重入裁决回潮)/ 存证闩回潮。"""
    from sr_od.application.currency_war.kernel.cw_screen_report.planner import (
        CwScreenPlannerObs,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_yinlang as ymod,
    )

    session = StrategySession()
    _decide_calls: list[int] = []
    match = _make_match(
        session,
        decide_planner=lambda: (_decide_calls.append(1)
                                or SimpleNamespace(idx=1, reason='stub')))
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = ymod.CwScreenYinLang(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    # 决策半腿型判定输入 = 选中的右卡卡文(破解芯片 = 装备域锚命中)。
    op._obs = CwScreenPlannerObs(
        on_screen=True,
        options=[PlannerOption(idx=0, text='随便什么左卡'),
                 PlannerOption(idx=1, text='破解芯片 前台强度 30%')],
        screen=_FRAME)
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
    rs = _run_node(test_context, op, op.act)
    assert _decide_calls == [1], f'零参决策恰一次:{_decide_calls!r}'
    assert len(dispatches) == 1 and dispatches[0].param.idx == 1, (
        f'选卡确认链恰一次派发,param 携真实 idx:{dispatches!r}')
    assert dispatches[0].env.leg_type == 'equip', (
        'env 携腿型载荷(classify_planner_leg 单源)')
    assert dispatches[0].env.norm_item == '破解芯片', '归一件名随 env 透传'
    assert dispatches[0].env.target is not None, '点卡定位点经 env 传入'
    assert rs.is_success, f'派发即 round_success 终结(零重入裁决轮):{rs!r}'


# ==================== 命运卜者决策出口锁(守卫⓪①② + 直发)====================

def _setup_fortune_act(test_context, monkeypatch, session, decide):
    """fortune act 锁公共装配(祈愿锁先例同构):match 桩挂零参决策桩
    (decide=None = cw_match None 局外态)+ obs 注入 + 注册表派发捕获。"""
    from sr_od.application.currency_war.kernel.cw_screen_report.fortune import (
        CwScreenFortuneObs,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_fortune as mod,
    )

    monkeypatch.setattr(
        test_context, 'cw_match',
        None if decide is None else _make_match(session, decide_fortune=decide),
        raising=False)
    op = mod.CwScreenFortune(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    op._obs = CwScreenFortuneObs(on_screen=True,
                                 options=['甲文', '乙文', '丙文'],
                                 option_points=[(511, 481), (901, 481),
                                                (1291, 481)],
                                 screen=_FRAME)   # obs 注入(观察 node 产物形态)
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
    return op, dispatches


def test_fortune_act_guard_invalid_decision_fails_without_dispatch(
        test_context, monkeypatch) -> None:
    """补锁①(返回契约):decide_fortune 返 None/词表外(SimpleNamespace)
    两子态合一锁 → act 具名 round_fail(消息含「决策无有效输出」,留证
    原值)、零派发零点击、_confirm_pending 保持未置位。红 = 守卫缺失盲发
    / 钳位回潮 / 策略异常被吞。"""
    for stub in (None, SimpleNamespace(idx=0, reason='stub')):
        session = StrategySession()
        op, dispatches = _setup_fortune_act(
            test_context, monkeypatch, session, lambda s=stub: s)
        rs = _run_node(test_context, op, op.act)
        assert not rs.is_success and '决策无有效输出' in (rs.status or ''), (
            f'守卫①({stub!r}):具名 round_fail 零盲发:{rs!r}')
        assert dispatches == [], f'守卫①({stub!r}):零派发'
        assert op._confirm_pending is False, (
            f'守卫①({stub!r}):确认未置位(零点击)')


def test_fortune_act_guard_idx_out_of_range_asserts(
        test_context, monkeypatch) -> None:
    """补锁②(值域):真词表类 idx=3(槽数 = 3 越界)→ AssertionError
    传播(守卫断言响亮暴露,禁钳位)、零派发零点击。红 = 钳位回潮。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickFortuneParam,
    )

    session = StrategySession()
    op, dispatches = _setup_fortune_act(
        test_context, monkeypatch, session,
        lambda: CwActionPickFortuneParam(idx=3))
    with pytest.raises(AssertionError, match='越界'):
        _run_node(test_context, op, op.act)
    assert dispatches == [], '守卫②:零派发'
    assert op._confirm_pending is False, '守卫②:确认未置位(零点击)'


def test_fortune_act_dispatches_strategy_param_env_op_only(
        test_context, monkeypatch) -> None:
    """补锁③(正路形态):真词表类 idx=1 → 恰一次派发且派发 param 即
    策略产实例(直发零重建,reason 归因不丢)、env 仅携 op(零 target
    零 idx——坐标随报条款,点击坐标 = 动作 op 自容器读)、rs = round_wait、
    _confirm_pending 置位。红 = 派发实例重建 / env 坐标喂回潮。"""
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickFortuneParam,
    )

    session = StrategySession()
    pick = CwActionPickFortuneParam(idx=1, reason='stub')
    op, dispatches = _setup_fortune_act(
        test_context, monkeypatch, session, lambda: pick)
    rs = _run_node(test_context, op, op.act)
    assert len(dispatches) == 1, f'恰一次派发:{dispatches!r}'
    assert dispatches[0].param is pick, '派发 param = 策略产实例(直发零重建)'
    assert dispatches[0].env.target is None and dispatches[0].env.idx is None, (
        'env 仅携 op(零 target 零 idx,停喂)')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'round_wait 推进循环(确认未落地轮重走):{rs!r}')
    assert op._confirm_pending is True, '确认已发待重入裁决置位'


def test_fortune_act_no_match_ends_success_without_decision_or_click(
        test_context, monkeypatch) -> None:
    """补锁④(局外臂,op-layer.md §1.1 :37):cw_match=None → act
    round_success(消息含「零决策零点击终结交回」)、零派发零点击、
    _confirm_pending 保持未置位;局外臂先于任何决策消费(kernel 直调
    兜底派发退役)。红 = 局外兜底决策路径回潮。"""
    session = StrategySession()
    op, dispatches = _setup_fortune_act(test_context, monkeypatch, session,
                                        None)
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '零决策零点击终结交回' in (rs.status or ''), (
        f'守卫⓪:局外零决策零点击 round_success 终结交回:{rs!r}')
    assert dispatches == [], '守卫⓪:零派发'
    assert op._confirm_pending is False, '守卫⓪:确认未置位(零点击)'
