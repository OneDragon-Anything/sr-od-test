"""节点循环族 8 屏两 node 形态锁(迭代 2026-09-18-screen-op-flat-report)。

锁的语义(测试纪律:只锁新形态的核心约定,先例 = test_cw_obs_arch_event_
screens.py 盛会之星段;report 函数级契约由 test_cw_screen_report_ports 锁
承重,本文件不重复):

- **观察上报接线锁**(表驱动七屏):观察 node 读链桩化 → 驱动 observe →
  report 经屏文件落容器(容器终值);盛会之星接线由 obs_arch_event_screens
  同文件锁承重(懒读保真,不在本表);
- **入口门语义锁**(带门四屏):门 miss = round_fail 交回外循环重判,
  文案沿用现役,且不进读链(obs 不装载);
- **chosen 写时机锁**(祈愿试炼代表):确认已发 → 标识不在 = 选卡落地
  → 此刻才写 chosen_wish + success 交回;标识在 = 未落地 → 不写、重走
  (chosen_* 动作事实边界留守重入裁决点);
- **决策动作 node 锁**(装备三选一代表,无门单发型):决策从容器零参读
  (决策调用形态不变)→ 点卡点击序列 → round_wait 推进循环(不计节点
  重试预算)。

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

from sr_od.application.currency_war.kernel.cw_events import PartnerOption
from sr_od.application.currency_war.kernel.cw_events import PlannerOption
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


# ==================== 观察上报接线锁(七屏表驱动)====================

# 屏键 → (模块名, 类名, 装配钩子(op, monkeypatch), 期望容器字段, 期望终值)
_OBS_ROWS = {
    'equip_pick':
        ('cw_screen_equip_pick', 'CwScreenEquipPick',
         lambda op, mp: mp.setattr(op, '_read_cards',
                                   lambda s: ['甲卡', '乙卡', '丙卡']),
         'equip_pick_opts', ['甲卡', '乙卡', '丙卡']),
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
             map_result={'左卡文': _mrl(500, 350), '右卡文': _mrl(1200, 350)}),
             raising=False),
         'planner_opts', [PlannerOption(idx=0, text='左卡文'),
                          PlannerOption(idx=1, text='右卡文')]),
    'fortune':
        ('cw_screen_fortune', 'CwScreenFortune',
         lambda op, mp: mp.setattr(op.ctx, 'ocr_service', _StubOcr(
             map_result={'甲文': _mrl(510, 350), '乙文': _mrl(900, 350)}),
             raising=False),
         'fortune_opts', ['甲文', '乙文', '']),
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
    'equip_pick', 'partner', 'planner', 'fortune', 'wish_trial', 'bookcard',
    'expert_invite'])
def test_observe_reports_container_per_screen(test_context, monkeypatch,
                                              screen_key: str) -> None:
    """观察上报接线锁(表驱动七屏):观察 node 读链桩化 → observe success →
    report 经屏文件落容器(容器终值逐位 = 现役写点转录值)+ obs 挂实例
    属性。红 = 接线断流 / 容器终值漂移 / obs 未装载。"""
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
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wish_trial as mod,
    )

    session = StrategySession()
    monkeypatch.setattr(
        test_context, 'cw_match',
        _make_match(session,
                    decide_wish_trial=lambda: SimpleNamespace(idx=0,
                                                              reason='stub')),
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
    assert (dispatches[0].env.target.x, dispatches[0].env.target.y) == (
        mod.CwScreenWishTrial.FIRST_CARD.x, mod.CwScreenWishTrial.FIRST_CARD.y), (
        f'定位点 = 首卡:{dispatches[0].env.target!r}')
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


# ==================== 决策动作 node 锁(装备三选一代表)====================

def test_equip_act_decides_from_container_and_round_wait(
        test_context, monkeypatch) -> None:
    """决策动作 node 锁(无门单发型代表):决策从容器零参读(决策调用
    形态不变;写槽已由 report 落容器)→ 选卡链派发(pick-op-unify 批:
    点卡即选迁入 ``CwActionPickEquipOp``;机械链行为锁 =
    test_cw_unified_action_4)→ round_wait 推进循环(不计节点重试预算)。
    红 = 决策形态回迁带参 / 定位点漂移 / 循环推进回退为计预算的 retry。"""
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_equip_pick as mod,
    )

    session = StrategySession()
    _decide_calls: list[int] = []
    match = _make_match(
        session,
        decide_equip_pick=lambda: (_decide_calls.append(1)
                                   or SimpleNamespace(idx=1, reason='stub')))
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = mod.CwScreenEquipPick(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, '_read_cards',
                        lambda s: ['甲卡', '乙卡', '丙卡'])
    # 观察 node(report 落容器)+ 决策动作 node(零参决策消费)
    _run_node(test_context, op, op.observe)
    assert game_state_of(session).equip_pick_opts.value == [
        '甲卡', '乙卡', '丙卡'], '前置:观察已落容器'
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
        f'选卡链恰一次派发,param 携真实 idx:{dispatches!r}')
    assert (dispatches[0].env.target.x, dispatches[0].env.target.y) == (
        mod.CwScreenEquipPick.CARD_XS[1], mod.CwScreenEquipPick.CARD_Y), (
        f'定位点(策略 idx=1 → 第二卡):{dispatches[0].env.target!r}')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'循环推进 = round_wait(不计节点重试预算):{rs!r}')
    assert op._pick_pending is True, '点击已发 → 重入裁决标志置位'
