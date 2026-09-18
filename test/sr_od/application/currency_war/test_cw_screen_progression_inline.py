"""推进型 11 屏骨架内联形态锁 + 武装箱选卡观察上报接线锁(迭代
2026-09-18-screen-op-flat-report T-6 批)。

背景:11 推进型屏脱离共享骨架(原推进型基类,其骨架语义 = 「入口观察 →
单次推进 → 重入观察裁决交回」),逐屏内联为「观察 node → 决策动作 node」
两段直继承 SrOperation;武装箱选卡屏两 node 化并把卡名写点收编至
``report_screen_box_pick_obs``(kernel 屏文件,report 函数级契约由
test_cw_screen_report_ports 锁承重,本文件不重复)。

锁的语义(测试纪律:只锁新形态的核心约定,先例 = test_cw_screen_two_node_
family.py):

- **入口门 miss 锁**(表驱动,覆盖全部入口形状):门 miss 未发 =
  round_fail 交回外循环重判(文案沿用现役),obs 不装载;
- **观察装载锁**(表驱动全 11 屏):门 hit → obs{on_screen=True, screen}
  挂实例属性(空决策形态无 report,本锁不涉容器);
- **重入裁决×旗标组合锁**(默认 area 锚 + 自有 OCR 两形状代表 + 免锚
  参数化屏):已发 + 门 miss = 已离开本画面 → success 交回 + 旗标清 +
  推进体零调用;已发/未发 + 门在 = 再推进恰一次 → round_wait 循环
  (不烧节点重试预算);推进体未落地 = round_fail + 旗标不置位;
- **免锚出口锁**(参数化屏空锚构造):无「已离开」观察信号 → 发出即
  success(免锚),重入裁决不可达;
- **武装箱观察上报接线锁**:门 hit + 读数非空 → 容器 ``box_card_names``
  终值 = 卡名表(经 report 接线);读数空/门 miss → fail 交回 + 容器与
  obs 均空(report 不调,禁盲值);决策动作 node = 容器外读数决策 →
  点卡点击序列 → 选卡即终结 success。

驱动方式 = 真类实例(构造走 __init__)+ 门/推进体桩化,节点函数直驱
(run_node 外壳)。
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
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

_FRAME = object()   # 稳定帧哨兵(读链桩只验传递不断言内容)

_PKG = 'sr_od.application.currency_war.operations.cw_screen'


def _make_op(module_name: str, cls_name: str, ctx, *args):
    """真类实例构造(构造走 __init__;参数化屏带参透传)。"""
    import importlib

    mod = importlib.import_module(f'{_PKG}.{module_name}')
    return getattr(mod, cls_name)(ctx, *args)


def _stub_controller(ctx, monkeypatch: pytest.MonkeyPatch) -> list:
    """controller 桩:mouse_move no-op + click 记录器。返回点击记录列表。"""
    clicks: list = []
    monkeypatch.setattr(
        ctx, 'controller',
        SimpleNamespace(mouse_move=lambda *a, **k: None,
                        click=lambda p, **k: clicks.append(p)),
        raising=False)
    return clicks


# ==================== 入口门 miss 锁(全部入口形状)====================

#: 屏键 → (模块名, 类名, 构造参数, 门 miss 桩装配(op, monkeypatch))
_GATE_MISS_ROWS = {
    'plane_detail':   # 默认 area 锚形状
        ('cw_screen_plane_detail', 'CwScreenPlaneDetail', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(False),
                                   raising=False)),
    'next_button':    # 自有 OCR 形状
        ('cw_screen_next_button', 'CwScreenNextButton', (),
         lambda op, mp: mp.setattr(op, 'round_by_ocr',
                                   lambda s, t, **k: _Area(False),
                                   raising=False)),
    'consumable_overlay':   # 双 OCR AND(首条件短路即 miss)
        ('cw_screen_consumable_overlay', 'CwScreenConsumableOverlay', (),
         lambda op, mp: mp.setattr(op, 'round_by_ocr',
                                   lambda s, t, **k: _Area(False),
                                   raising=False)),
    'item_detail_popup':    # OCR ∧ 排他锚(OCR 短路即 miss)
        ('cw_screen_item_detail_popup', 'CwScreenItemDetailPopup', (),
         lambda op, mp: mp.setattr(op, 'round_by_ocr',
                                   lambda s, t, **k: _Area(False),
                                   raising=False)),
    'emblem_detail_popup':  # 双锚其一(同桩双锚全 miss)
        ('cw_screen_emblem_detail_popup', 'CwScreenEmblemDetailPopup', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(False),
                                   raising=False)),
    'role_detail_overlay':  # 双锚其一(同桩双锚全 miss)
        ('cw_screen_role_detail_overlay', 'CwScreenRoleDetailOverlay', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(False),
                                   raising=False)),
    'shop_card_detail':     # 双锚 AND(同桩即 miss)
        ('cw_screen_shop_card_detail', 'CwScreenShopCardDetailPopup', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(False),
                                   raising=False)),
}


@pytest.mark.parametrize('screen_key', sorted(_GATE_MISS_ROWS))
def test_entry_gate_miss_fails_back(test_context, monkeypatch,
                                    screen_key: str) -> None:
    """入口门 miss 锁:miss 未发 = round_fail 交回外循环重判(现役文案),
    obs 不装载。红 = 门失效 / 文案漂移 / miss 后仍装载 obs。"""
    mod_name, cls_name, args, miss = _GATE_MISS_ROWS[screen_key]
    op = _make_op(mod_name, cls_name, test_context, *args)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    miss(op, monkeypatch)
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success, f'{screen_key}: 门 miss 应 fail 交回:{rs!r}'
    assert '入口锚未命中(交回外循环重判)' in (rs.status or ''), (
        f'{screen_key}: 误分发 fail 文案沿用现役:{rs!r}')
    assert op._obs is None, f'{screen_key}: 门早退不装载 obs'


# ==================== 观察装载锁(全 11 屏)====================

#: 屏键 → (模块名, 类名, 构造参数, 门 hit 桩装配(op, monkeypatch))
_OBS_ROWS = {
    'plane_detail':
        ('cw_screen_plane_detail', 'CwScreenPlaneDetail', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(True),
                                   raising=False)),
    'next_button':
        ('cw_screen_next_button', 'CwScreenNextButton', (),
         lambda op, mp: mp.setattr(op, 'round_by_ocr',
                                   lambda s, t, **k: _Area(True),
                                   raising=False)),
    'consumable_overlay':
        ('cw_screen_consumable_overlay', 'CwScreenConsumableOverlay', (),
         lambda op, mp: mp.setattr(op, 'round_by_ocr',
                                   lambda s, t, **k: _Area(True),
                                   raising=False)),
    'item_detail_popup':
        ('cw_screen_item_detail_popup', 'CwScreenItemDetailPopup', (),
         lambda op, mp: (mp.setattr(op, 'round_by_ocr',
                                    lambda s, t, **k: _Area(True),
                                    raising=False),
                         mp.setattr(op, 'round_by_find_area',
                                    lambda s, sc, a, **k: _Area(False),
                                    raising=False))),
    'interrupt_dialog':
        ('cw_screen_interrupt_dialog', 'CwScreenInterruptDialog', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(True),
                                   raising=False)),
    'refresh_odds_popup':
        ('cw_screen_refresh_odds_popup', 'CwScreenRefreshOddsPopup', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(True),
                                   raising=False)),
    'emblem_detail_popup':
        ('cw_screen_emblem_detail_popup', 'CwScreenEmblemDetailPopup', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(True),
                                   raising=False)),
    'role_detail_overlay':
        ('cw_screen_role_detail_overlay', 'CwScreenRoleDetailOverlay', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(True),
                                   raising=False)),
    'shop_card_detail':
        ('cw_screen_shop_card_detail', 'CwScreenShopCardDetailPopup', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(True),
                                   raising=False)),
    'prep_locked_return':
        ('cw_screen_prep_locked_return', 'CwScreenPrepLockedReturn',
         ('货币战争-备战-策略锁定', '按钮-返回策略选择'),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(True),
                                   raising=False)),
    'aha_equip_pick':
        ('cw_screen_aha_equip_pick', 'CwScreenAhaEquipPick', (),
         lambda op, mp: mp.setattr(op, 'round_by_find_area',
                                   lambda s, sc, a, **k: _Area(True),
                                   raising=False)),
}


@pytest.mark.parametrize('screen_key', sorted(_OBS_ROWS))
def test_observe_loads_obs_on_hit(test_context, monkeypatch,
                                  screen_key: str) -> None:
    """观察装载锁:门 hit → obs{on_screen=True, screen=帧} 挂实例属性
    (空决策形态无 report,观察 node 不触容器)。红 = obs 断流/字段漂移。"""
    mod_name, cls_name, args, hit = _OBS_ROWS[screen_key]
    op = _make_op(mod_name, cls_name, test_context, *args)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    hit(op, monkeypatch)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'{screen_key}: 门 hit 应 success 进决策:{rs!r}'
    assert op._obs is not None and op._obs.on_screen is True, (
        f'{screen_key}: obs 装载(门判定 + 帧引用)')
    assert op._obs.screen is _FRAME, f'{screen_key}: 稳定帧引用透传'


# ==================== 重入裁决×旗标组合锁 ====================

#: 裁决代表屏:默认 area 锚形状(位面详情)+ 自有 OCR 形状(前进按钮)。
#: advance 桩 = 推进体 ok/miss 程序化回值;clicks = 推进体调用记录。
_ADJUDICATION_ROWS = {
    'plane_detail': (
        'cw_screen_plane_detail', 'CwScreenPlaneDetail',
        lambda op, mp, ok: (
            mp.setattr(op, 'round_by_find_area',
                       lambda s, sc, a, **k: _Area(ok), raising=False),
            mp.setattr(op, 'round_by_find_and_click_area',
                       lambda s, sc, a, **k: _Area(True), raising=False))),
    'next_button': (
        'cw_screen_next_button', 'CwScreenNextButton',
        lambda op, mp, ok: (
            mp.setattr(op, 'round_by_ocr',
                       lambda s, t, **k: _Area(ok), raising=False),
            mp.setattr(op, 'round_by_ocr_and_click',
                       lambda s, t, **k: _Area(True), raising=False))),
}


@pytest.mark.parametrize('screen_key', sorted(_ADJUDICATION_ROWS))
def test_reentry_arbitration_flag_combination(test_context, monkeypatch,
                                              screen_key: str) -> None:
    """重入裁决×旗标组合锁(两入口形状代表):
    - 已发 + 门 miss = 已离开本画面 → success 交回(现役文案)+ 旗标清
      + 推进体零调用(裁决出口 = 入口观察的合法重判,非动作层判效);
    - 已发 + 门在 = 点击未落地 → 再推进恰一次 → round_wait(循环推进
      不烧节点重试预算);
    - 推进体未落地 → round_fail(现役文案)+ 旗标不置位。
    红 = 裁决出口语义漂移 / 旗标误清复活 / 循环推进回退为 retry。"""
    mod_name, cls_name, setup = _ADJUDICATION_ROWS[screen_key]
    # ① 已发 + 门 miss → success + 旗标清 + 推进体零调用
    op = _make_op(mod_name, cls_name, test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    _advance_calls: list[int] = []

    def _advance(op, mp, ok: bool):
        setup(op, mp, ok)
        mp.setattr(op, 'progress_once',
                   lambda: _advance_calls.append(1) or True, raising=False)

    _advance(op, monkeypatch, False)
    op._advanced_once = True
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '已推进(重入观察:已离开本画面)' in (
        rs.status or ''), f'{screen_key}: 重入裁决出口 success:{rs!r}'
    assert op._advanced_once is False, f'{screen_key}: 裁决出口旗标清'
    assert _advance_calls == [], f'{screen_key}: 裁决出口推进体零调用'
    # ② 已发 + 门在 = 未落地 → 再推进恰一次 → round_wait
    op2 = _make_op(mod_name, cls_name, test_context)
    monkeypatch.setattr(op2, 'last_screenshot', _FRAME, raising=False)
    _calls2: list[int] = []
    setup(op2, monkeypatch, True)
    monkeypatch.setattr(op2, 'progress_once',
                        lambda: _calls2.append(1) or True, raising=False)
    op2._advanced_once = True
    rs2 = _run_node(test_context, op2, op2.act)
    assert rs2.result == OperationRoundResultEnum.WAIT, (
        f'{screen_key}: 循环推进 = round_wait(不烧节点重试预算):{rs2!r}')
    assert '推进已发,重入观察裁决' in (rs2.status or ''), (
        f'{screen_key}: 推进已发机械交回文案:{rs2!r}')
    assert _calls2 == [1] and op2._advanced_once is True, (
        f'{screen_key}: 锚在 = 再推进恰一次,旗标保持已发')
    # ③ 推进体未落地 → round_fail + 旗标不置位
    op3 = _make_op(mod_name, cls_name, test_context)
    monkeypatch.setattr(op3, 'last_screenshot', _FRAME, raising=False)
    setup(op3, monkeypatch, True)
    monkeypatch.setattr(op3, 'progress_once', lambda: False, raising=False)
    rs3 = _run_node(test_context, op3, op3.act)
    assert not rs3.is_success and '推进动作未落地' in (rs3.status or ''), (
        f'{screen_key}: 推进未落地 fail 文案:{rs3!r}')
    assert op3._advanced_once is False, f'{screen_key}: 失败轮旗标不置位'


def test_anchor_free_advance_succeeds_immediately(test_context,
                                                  monkeypatch) -> None:
    """免锚出口锁(参数化屏空锚构造 = 免锚形态):无「已离开」观察信号,
    发出即 success(免锚),重入裁决不可达(已发与否同出口)。
    红 = 空锚误走重入裁决 / 免锚出口漂移。"""
    op = _make_op('cw_screen_prep_locked_return', 'CwScreenPrepLockedReturn',
                  test_context, '货币战争-备战-策略锁定', '')
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    assert op.entry_ok(_FRAME) is True, '空锚 = 入口观察恒过(免锚形态)'
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda s, sc, a, **k: _Area(True), raising=False)
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '推进已发(免锚)' in (rs.status or ''), (
        f'免锚发出即 success:{rs!r}')
    # 已发重入(空锚无裁决信号)→ 同免锚出口,不误判完成/失败
    op._advanced_once = True
    rs2 = _run_node(test_context, op, op.act)
    assert rs2.is_success and '推进已发(免锚)' in (rs2.status or ''), (
        f'免锚重入同出口(裁决不可达):{rs2!r}')


def test_area_center_advance_missing_fail(test_context, monkeypatch) -> None:
    """推进体缺坐标形态(area_center 读缺 = 未落地):round_fail 现役文案
    + 旗标不置位(area_center 代表屏 = 阿哈装备选择)。红 = 缺坐标误判
    已推进。"""
    import importlib

    mod = importlib.import_module(f'{_PKG}.cw_screen_aha_equip_pick')
    op = mod.CwScreenAhaEquipPick(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(mod, 'area_center', lambda ctx, a, sc: None,
                        raising=False)
    rs = _run_node(test_context, op, op.act)
    assert not rs.is_success and '推进动作未落地' in (rs.status or ''), (
        f'缺坐标 = 推进未落地:{rs!r}')
    assert op._advanced_once is False, '失败轮旗标不置位'


# ==================== 武装箱选卡观察上报接线锁 ====================

_CARDS = [('甲卡', 500), ('乙卡', 900)]   # x 升序读数桩


def _make_box_pick(test_context, monkeypatch: pytest.MonkeyPatch,
                   *, gate_ok: bool, cards: list):
    """武装箱选卡 op 装配:门/读链桩化 + 局内容器挂载。返回 (op, session)。"""
    import importlib

    mod = importlib.import_module(f'{_PKG}.cw_screen_box_pick')
    session = StrategySession()
    match = SimpleNamespace(session=session, strategy=SimpleNamespace())
    match.gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = mod.CwScreenBoxPick(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(gate_ok), raising=False)
    monkeypatch.setattr(op, '_read_card_names', lambda s: cards,
                        raising=False)
    return op, session


def test_box_pick_observe_reports_card_names(test_context, monkeypatch):
    """观察上报接线锁:门 hit + 读数非空 → 容器 ``box_card_names`` 终值 =
    卡名表(report 接线落容器)+ obs/原始读数挂实例属性(点击定位要
    x 坐标,x 对留守 op 不进容器)。红 = 接线断流 / 容器终值漂移。"""
    op, session = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                 cards=list(_CARDS))
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success 进决策动作 node:{rs!r}'
    gs = game_state_of(session)
    assert gs.box_card_names.value == ['甲卡', '乙卡'], (
        f'report 落容器(容器终值 = 卡名表):{gs.box_card_names.value!r}')
    assert gs.box_card_names.source == 'logic', '容器来源渠道 = logic'
    assert op._obs is not None and op._obs.card_names == ['甲卡', '乙卡'], (
        'obs 装载(字段对齐 T-1 契约)')
    assert op._cards == _CARDS, '原始读数(x 对)挂实例属性供决策动作 node'


@pytest.mark.parametrize('gate_ok, cards, expect_status', [
    (False, list(_CARDS), '非武装箱选择画面(标识-请选择 miss)'),
    (True, [], 'OCR 未读到卡名(变体/动画帧),交回重派'),
])
def test_box_pick_observe_gates_skip_report(test_context, monkeypatch,
                                            gate_ok: bool, cards: list,
                                            expect_status: str) -> None:
    """两道闸锁(现役单 node 首闸/读数闸逐位):锚 miss / 卡名空 →
    fail 交回外循环重派(现役文案),容器与 obs 均空(report 不调,
    禁盲值进容器)。红 = 闸失效 / 盲写容器。"""
    op, session = _make_box_pick(test_context, monkeypatch, gate_ok=gate_ok,
                                 cards=cards)
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and expect_status in (rs.status or ''), (
        f'闸 fail 文案沿用现役:{rs!r}')
    assert game_state_of(session).box_card_names.value is None, (
        '闸早退 report 不调(容器不进盲值)')
    assert op._obs is None and op._cards == [], '闸早退不装载 obs/读数'


def test_box_pick_act_clicks_decided_card(test_context, monkeypatch):
    """决策动作 node 锁:容器外读数决策(零参策略契约)→ 点卡点击序列
    (选中即确认)→ 选卡即终结 success。红 = 决策形态漂移 / 点击坐标
    漂移 / 终结交回语义漂移。"""
    import importlib

    mod = importlib.import_module(f'{_PKG}.cw_screen_box_pick')
    op, _session = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                  cards=list(_CARDS))
    _decide_calls: list[int] = []
    match = test_context.cw_match
    match.strategy = SimpleNamespace(
        decide_box_card=lambda: (_decide_calls.append(1)
                                 or SimpleNamespace(idx=1, reason='stub')))
    _run_node(test_context, op, op.observe)   # 前置:观察装载读数
    clicks = _stub_controller(test_context, monkeypatch)
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None, raising=False)
    rs = _run_node(test_context, op, op.act)
    assert _decide_calls == [1], f'零参决策恰一次:{_decide_calls!r}'
    assert [(p.x, p.y) for p in clicks] == [(900, mod.CwScreenBoxPick.CARD_Y)], (
        f'点卡点击序列(策略 idx=1 → 第二卡 x 中心 + CARD_Y):{clicks!r}')
    assert rs.is_success and '选卡即终结' in (rs.status or ''), (
        f'选卡即终结交回:{rs!r}')
