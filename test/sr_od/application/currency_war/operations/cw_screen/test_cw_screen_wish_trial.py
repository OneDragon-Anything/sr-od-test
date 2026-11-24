"""祈愿试炼画面 op 测试(CwScreenWishTrial;守卫登记 =
docs/develop/sr_od/application/currency_war/screens/wish_trial.md §8,族规 =
screens/op-layer.md §1.1 出口③ / §1.3;同构样板 = test_cw_screen_yinlang)。

一、决策出口守卫(``act``)——锁的故障形态:候选数为 0(obs 载体缺席 /
读链产空)时进策略器——策略器对空候选回落 idx=0,放进去 = 盲选派发;修前
形态 = 越界断言(非具名 fail,且策略器已被盲选调用一次)。守卫序 = 选卡
族规:① 候选空 → 具名 round_fail(调策略器前);② 策略返回词表外/None →
具名 round_fail;③ idx 越界 → AssertionError(禁钳位)——三守卫均在
派发前、零点击。边界(防守卫①误伤):OCR 空桶(候选文本为空串)≠ 候选空
——空桶照持仍是合法候选,合法 pick 照常派发。

二、落地复查与 chosen_wish 写端(``act`` 顶部 pending 分支 +
``_record_chosen``)——锁的故障形态:确认已发后重入,标识不在(overlay
已关)= 选卡落地,此刻才写 ``chosen_wish``(写晚 / 漏写 = 选卡事实永不出
账,标志不清 = 重入卡死);标识仍在(确认未落地)= 不得写(写早 = 幻影
登记),清标志重读重选;选中槽文本空不得写空串冒充记录(归档帧中桶即
空串);记录面异常不得上抛(pending 已清后的异常进框架节点重试 = 在已关
的 overlay 上按陈旧 obs 重决策重点击)。

三、观察节点真实帧(``observe``)——锁的故障形态:OCR 分桶读数与槽位
坐标是候选两域的唯一生成路径,读链坏了此前无测试会红;归档帧 2 张卡、
中桶空串,空桶照持才保候选下标 = 画面物理卡位。

演法 = 直调节点方法:观察产物 ``op._obs`` 由测试装配(节点方法不替换——
替换 @operation_node 方法会丢节点元数据);派发接缝 =
``cw_action_registry.action_op_for`` 模块级名字(act 内函数级 import,
monkeypatch 承接并计数);策略器桩记录调用次数(锁「候选空不进策略器」)。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import FixtureController, fast_sleep

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_screen_report.wish_trial import (
    CwScreenWishTrialObs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickWishTrialParam,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_wish_trial import (
    CwScreenWishTrial,
)

_REGISTRY: str = ('sr_od.application.currency_war.operations.cw_op.'
                  'cw_action_registry')
#: 状态容器供给口所在模块(``_record_chosen`` 函数级 import,调用时现取模块名)。
_GS_MODULE: str = 'sr_od.application.currency_war.kernel.cw_game_state'
_OPT_A: str = '累计刷新10次'
_OPT_B: str = '获得20金币'
_OPT_C: str = '进行一场难度3+遭遇节点战斗'
#: 归档帧(测试仓 screens/):祈愿试炼 overlay 在场 / 确认后已关回备战。
_FRAME_OVERLAY: tuple[str, str] = ('货币战争-祈愿试炼', '祈愿试炼')
_FRAME_PREP: tuple[str, str] = ('货币战争-备战', '攻略已应用')
#: 归档帧读数真值(screens/货币战争-祈愿试炼/祈愿试炼.webp:2 张卡,中位无卡
#: = 空桶;卡面文字经视觉模型独立判读核对,非取自被测 OCR)。
_FRAME_TRUTH: list[str] = [
    '金币 累计刷新10次', '', '命运圣杯星徽 进行一场难度3及以上的遭遇节点战斗']


def _attach(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
            options: list[str], pick: object,
            ) -> tuple[CwScreenWishTrial, list[tuple[object, object]],
                       list[int]]:
    """装配 op 与假局(假局 = session + gs + 策略器桩,与生产
    CurrencyWarMatch 同形:gs = game_state_of(session) 同一对象):观察产物
    直挂 ``op._obs``(坐标域与名字域同序等长),策略器回 ``pick`` 并记录
    调用,派发工厂换成计数桩(记录 (param, env),execute 空转)。"""
    op = CwScreenWishTrial(test_context)
    op._obs = CwScreenWishTrialObs(
        on_screen=True, options=list(options),
        option_points=[(660, 340)] * len(options))
    strategy_calls: list[int] = []
    session = SimpleNamespace()
    match = SimpleNamespace(
        session=session, gs=game_state_of(session),
        strategy=SimpleNamespace(
            decide_wish_trial=lambda: (strategy_calls.append(1), pick)[1]))
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    dispatched: list[tuple[object, object]] = []
    stub = SimpleNamespace(execute=lambda: None)
    monkeypatch.setattr(
        f'{_REGISTRY}.action_op_for',
        lambda param, ctx, env: (dispatched.append((param, env)), stub)[1])
    return op, dispatched, strategy_calls


def test_empty_options_named_fail_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """守卫①:候选空 → 具名 round_fail(状态含「候选空」)、零派发、
    策略器零调用(空候选不进策略器——进去 = 盲选派发)。"""
    op, dispatched, strategy_calls = _attach(
        test_context, monkeypatch, [], CwActionPickWishTrialParam(idx=0))

    result = op.act()

    assert result.is_fail, f'候选空应 fail 交外环,实际 {result.status!r}'
    assert '候选空' in (result.status or ''), result.status
    assert strategy_calls == [], f'候选空不应进策略器,实际调用 {len(strategy_calls)} 次'
    assert dispatched == [], f'候选空应零派发,实际 {dispatched}'


@pytest.mark.parametrize('bad', [None, SimpleNamespace(idx=0)])
def test_non_contract_return_named_fail_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        bad: object) -> None:
    """守卫②:decide_wish_trial 返回 None / 词表外类型(非动作类型对象)→
    具名 round_fail 含原值 repr、零派发。"""
    op, dispatched, _ = _attach(
        test_context, monkeypatch, [_OPT_A, _OPT_B], bad)

    result = op.act()

    assert result.is_fail, f'词表外/None 应 fail,实际 {result.status!r}'
    assert '词表外/None' in (result.status or ''), result.status
    assert repr(bad) in (result.status or ''), result.status
    assert dispatched == [], f'词表外/None 应零派发,实际 {dispatched}'


@pytest.mark.parametrize('idx', [3, -1])
def test_idx_out_of_range_asserts_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        idx: int) -> None:
    """守卫③:idx 越界(上界外 / 负值)→ AssertionError(禁钳位)、零派发。"""
    op, dispatched, _ = _attach(
        test_context, monkeypatch, [_OPT_A, _OPT_B, _OPT_C],
        CwActionPickWishTrialParam(idx=idx))

    with pytest.raises(AssertionError, match='越界'):
        op.act()
    assert dispatched == [], f'越界应零派发,实际 {dispatched}'


def test_empty_bucket_text_still_dispatches(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """边界:OCR 空桶(候选文本空串)≠ 候选空——候选 ``['', '获得20金币', '']``
    合法 pick idx=1 → 守卫① 放行、恰派发一次(param = 策略产值原对象)、
    返回 round_wait(非终结出口:本 node 循环推进,落地由下一轮复查判)。"""
    pick = CwActionPickWishTrialParam(idx=1)
    op, dispatched, strategy_calls = _attach(
        test_context, monkeypatch, ['', _OPT_B, ''], pick)

    with fast_sleep():
        result = op.act()

    assert result.result is OperationRoundResultEnum.WAIT, \
        f'合法 pick 派发后应 round_wait 循环推进,实际 {result.result!r}'
    assert strategy_calls == [1], '合法候选应恰调策略器一次'
    assert len(dispatched) == 1, f'应恰派发一次,实际 {dispatched}'
    param, env = dispatched[0]
    assert param is pick, '派发 param 应 = 策略产值原对象(直发零重建)'
    assert env.op is op, '派发 env 应仅携 op(坐标由动作 op 自状态容器取)'


def test_landed_confirm_records_chosen_and_returns_to_loop(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """落地复查·已落地:确认已发 + 标识不在(overlay 已关,备战归档帧)→
    ``chosen_wish`` = 选中卡原文、pending 清空、round_success 返回主循环;
    策略器零调用、零派发(已落地不重选)。"""
    op, dispatched, strategy_calls = _attach(
        test_context, monkeypatch, [_OPT_A, _OPT_B], None)
    op._confirm_pending = ([_OPT_A, _OPT_B], 1)
    op.last_screenshot = test_context.load_screen(*_FRAME_PREP)

    with fast_sleep(op):
        result = op.act()

    assert result.is_success, f'已落地应 success 返回主循环,实际 {result.status!r}'
    assert test_context.cw_match.gs.chosen_wish.value == _OPT_B, \
        '落地后 chosen_wish 应 = 选中卡(objs[1])原文'
    assert op._confirm_pending is None, '裁决后 pending 应清空(防重入卡死)'
    assert strategy_calls == [], f'已落地不应重选,实际策略器调用 {len(strategy_calls)} 次'
    assert dispatched == [], f'已落地不应再派发,实际 {dispatched}'


def test_unlanded_confirm_rerecides_without_recording(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """落地复查·未落地:确认已发 + 标识仍在(overlay 未关,祈愿试炼归档帧)
    → ``chosen_wish`` 不写(防幻影登记)、pending 换新快照、重调策略器并
    再派发一次、返回 round_wait。"""
    pick = CwActionPickWishTrialParam(idx=1)
    op, dispatched, strategy_calls = _attach(
        test_context, monkeypatch, [_OPT_A, _OPT_B], pick)
    op._confirm_pending = ([_OPT_A, _OPT_B], 0)
    op.last_screenshot = test_context.load_screen(*_FRAME_OVERLAY)

    with fast_sleep(op):
        result = op.act()

    assert test_context.cw_match.gs.chosen_wish.value is None, \
        '确认未落地不得写 chosen_wish(幻影登记)'
    assert strategy_calls == [1], '未落地应清标志重走(重调策略器一次)'
    assert len(dispatched) == 1 and dispatched[0][0] is pick, \
        f'应按新决策再派发一次,实际 {dispatched!r}'
    assert op._confirm_pending == ([_OPT_A, _OPT_B], 1), \
        f'pending 应换新快照,实际 {op._confirm_pending!r}'
    assert result.result is OperationRoundResultEnum.WAIT


def test_record_chosen_empty_text_keeps_no_record(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """写入口径:选中槽文本空(归档帧中桶即空串,策略可选到)→ 不写,
    ``chosen_wish`` 保持 None(「无记录」语义,不写空串冒充记录);同局选中文本
    非空的槽照常写入(对照:证明上一步不写是口径而非链路坏)。"""
    op, _dispatched, _calls = _attach(test_context, monkeypatch, ['', _OPT_B], None)
    gs = test_context.cw_match.gs

    op._record_chosen(['', _OPT_B], 0)
    assert gs.chosen_wish.value is None, '选中空桶不得写空串冒充记录'
    op._record_chosen(['', _OPT_B], 1)
    assert gs.chosen_wish.value == _OPT_B


def test_record_chosen_write_failure_does_not_block(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """记录面失败不阻塞:状态容器供给抛错被吞——否则 pending 已清后的异常
    进框架节点重试,会在已关的 overlay 上按陈旧 obs 重决策重点击。"""
    op, _dispatched, _calls = _attach(
        test_context, monkeypatch, [_OPT_A, _OPT_B], None)

    def _boom(_session: object) -> None:
        raise RuntimeError('状态容器供给失效')
    monkeypatch.setattr(f'{_GS_MODULE}.game_state_of', _boom)

    op._record_chosen([_OPT_A, _OPT_B], 1)

    assert test_context.cw_match.gs.chosen_wish.value is None


def test_observe_real_frame_reports_buckets_to_state_container(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """观察节点真实生成路径:归档帧上入口门过,OCR 分桶读数与槽位坐标经
    真实 report 写进状态容器(``match.gs`` 两域)——候选下标 = 画面物理
    卡位序(空桶照持);槽位坐标 = 桶识别标志 x × 卡身 y。"""
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': _FRAME_OVERLAY}])
    op, _dispatched, _calls = _attach(test_context, monkeypatch, [], None)

    with fast_sleep(op):
        op.screenshot()
        result = op.observe()

    assert result.is_success, f'祈愿试炼帧入口门应过,实际 {result.status!r}'
    assert op._obs.options == _FRAME_TRUTH, \
        f'分桶读数应 = 归档帧真值(中桶空),实际 {op._obs.options!r}'
    gs = test_context.cw_match.gs
    assert gs.wish_trial_opts.value == _FRAME_TRUTH
    assert gs.wish_trial_opts_xy.value == [
        (x, CwScreenWishTrial.CARD_Y) for x in CwScreenWishTrial.CARD_XS], \
        f'槽位坐标应 = 桶标志 x × 卡身 y,实际 {gs.wish_trial_opts_xy.value!r}'
