"""推进型 11 屏骨架内联形态测试 + 武装箱选卡观察上报接线测试(迭代
 T-6 批)。

背景:11 推进型屏脱离共享骨架(原推进型基类,其骨架语义 = 「入口观察 →
单次推进 → 重入观察裁决交回」),逐屏内联为「观察 node → 决策动作 node」
两段直继承 SrOperation;武装箱选卡屏两 node 化并把卡名写点收编至
``report_screen_box_pick_obs``(kernel 屏文件,report 函数级契约由
test_screen_report_ports 测试承重,本文件不重复)。

测试的语义(测试纪律:只校验新形态的核心约定,先例 = test_screen_two_node_
family.py):

- **入口门 miss 测试**(表驱动,覆盖全部入口形状):门 miss 未发 =
  round_fail 交回外循环重判(文案沿用现役),obs 不装载;
- **观察装载测试**(表驱动全 11 屏):门 hit → obs{on_screen=True, screen}
  挂实例属性(空决策形态无 report,本测试不涉容器);
- **重入裁决×旗标组合测试**(默认 area 锚 + 自有 OCR 两形状代表 + 免锚
  参数化屏):已发 + 门 miss = 已离开本画面 → success 交回 + 旗标清 +
  推进体零调用;已发/未发 + 门在 = 再推进恰一次 → round_wait 循环
  (不烧节点重试预算);推进体未落地 = round_fail + 旗标不置位;
- **免锚出口测试**(参数化屏空锚构造):无「已离开」观察信号 → 发出即
  success(免锚),重入裁决不可达;
- **武装箱观察上报接线测试**:门 hit + 读数非空 → 观察标准化门 → 容器
  ``box_card_names`` 终值 = 标准名表 + 坐标同门双写
  ``box_card_names_xy``(观察期解点);读数空/门 miss/转换失败 → fail
  交回 + 容器与 obs 均空(report 不调,禁盲值;名字与坐标同进退);
  决策动作 node = 容器外读数决策 → 选卡链派发(env idx-only,target
  停喂)→ 选卡即终结 success;无 match 局外不设早退支(用户裁决
  2026-09-22 全族删门),沿正常链路自然失败;
- **读数闸放宽测试**(:读数闸上限 ``_CARD_NAME_LEN_MAX``
  派生自装备注册表最长名(防手抄常数),9 字特权名经真读数闸存活并
  归一精确命中(旧 8 字手抄上限先于归一化确定性丢弃 9 字名 = 四选一
  缩三选一)。

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
from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENT_ROSTER,
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


# ==================== 入口门 miss 测试(全部入口形状)====================

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
    """入口门 miss 测试:miss 未发 = round_fail 交回外循环重判(现役文案),
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


# ==================== 观察装载测试(全 11 屏)====================

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
    """观察装载测试:门 hit → obs{on_screen=True, screen=帧} 挂实例属性
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


# ==================== 重入裁决×旗标组合测试 ====================

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
    """重入裁决×旗标组合测试(两入口形状代表):
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
    """免锚出口测试(参数化屏空锚构造 = 免锚形态):无「已离开」观察信号,
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


# ==================== 武装箱选卡观察上报接线测试 ====================

#: x 升序读数桩(名字 = 装备注册表在册名——观察标准化门要求读数可
#: 转换为标准注册名,桩名必须真名可命中)。
_CARDS = [('反重力皮靴', 500), ('光能电池', 900)]


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
    """观察上报接线测试:门 hit + 读数非空 → 观察标准化门 → 容器
    ``box_card_names`` 终值 = 标准名表(report 接线落容器)+ 坐标同门
    双写 ``box_card_names_xy``(观察期解点,x + CARD_Y)。红 = 接线断流 /
    容器终值漂移 / 坐标域断供。"""
    import importlib

    mod = importlib.import_module(f'{_PKG}.cw_screen_box_pick')
    op, session = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                 cards=list(_CARDS))
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success 进决策动作 node:{rs!r}'
    gs = game_state_of(session)
    assert gs.box_card_names.value == ['反重力皮靴', '光能电池'], (
        f'report 落容器(容器终值 = 标准名表):{gs.box_card_names.value!r}')
    assert gs.box_card_names.source == 'logic', '容器来源渠道 = logic'
    assert gs.box_card_names_xy.value == [
        (500, mod.CwScreenBoxPick.CARD_Y),
        (900, mod.CwScreenBoxPick.CARD_Y)], (
        f'坐标同门双写(观察期解点):{gs.box_card_names_xy.value!r}')
    assert op._obs is not None and op._obs.card_names == [
        '反重力皮靴', '光能电池'], 'obs 装载(标准名字段)'
    assert op._obs.points == gs.box_card_names_xy.value, 'obs 坐标与容器同源'
    assert op._cards == _CARDS, '标准化读数(x 对)挂实例属性'


@pytest.mark.parametrize('gate_ok, cards, expect_status', [
    (False, list(_CARDS), '非武装箱选择画面(标识-请选择 miss)'),
    (True, [], 'OCR 未读到卡名(变体/动画帧),交回重派'),
])
def test_box_pick_observe_gates_skip_report(test_context, monkeypatch,
                                            gate_ok: bool, cards: list,
                                            expect_status: str) -> None:
    """两道闸测试(现役单 node 首闸/读数闸逐位):锚 miss / 卡名空 →
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


def test_box_pick_observe_standardization_gate_and_duplicates(
        test_context, monkeypatch):
    """观察标准化门测试(op-layer.md §1.1 条款①):任一候选转换不到标准
    注册名 = 观察失败 round_fail 零写零上报交回重读(名字与坐标同进退,
    禁带病上报);形变读数两段转换命中标准名;重复名合法(四卡可能
    同名,同装备多张)逐候选独立归一,不适用互斥拒判。红 = 带病直报 /
    重复名误拒 / 转换失败未同进退零写。"""
    # ① 转换失败:注册表外名字 → fail 早退,名字与坐标域双零写。
    op, session = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                 cards=[('甲卡', 500)])
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and '卡名标准化失败' in (rs.status or ''), (
        f'转换失败 = 观察失败交回重读:{rs!r}')
    gs = game_state_of(session)
    assert gs.box_card_names.value is None and gs.box_card_names_xy.value \
        is None, '转换失败名字坐标同进退零写'
    assert op._obs is None, '转换失败不装载 obs'
    # ② 形变读数:两段转换(归一精确 miss → LCS)命中标准注册名。
    op2, session2 = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                   cards=[('光能电地', 700)])
    rs2 = _run_node(test_context, op2, op2.observe)
    assert rs2.is_success, f'形变读数标准化命中:{rs2!r}'
    assert game_state_of(session2).box_card_names.value == ['光能电池'], (
        f'两段转换落标准名:{game_state_of(session2).box_card_names.value!r}')
    # ③ 重复名合法:同名双卡逐候选独立归一,容器保重复项,坐标等长。
    op3, session3 = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                   cards=[('反重力皮靴', 300),
                                          ('反重力皮靴', 900)])
    rs3 = _run_node(test_context, op3, op3.observe)
    assert rs3.is_success, f'重复名成功上报:{rs3!r}'
    gs3 = game_state_of(session3)
    assert gs3.box_card_names.value == ['反重力皮靴', '反重力皮靴'], (
        f'重复名合法(容器保重复项):{gs3.box_card_names.value!r}')
    assert len(gs3.box_card_names_xy.value) == 2, '坐标域与名字域同序等长'


def test_box_pick_lcs_ambiguity_rejection_and_unique_pass(test_context,
                                                          monkeypatch):
    """观察标准化门第二段·次高分差拒判测试(op-layer.md §1.1;用户裁定
    2026-09-22 全族统一):LCS 阶段最高分未明显高于次高分(差值不足
    ``_EQUIP_LCS_AMBIGUITY_MARGIN``)= 歧义 = 转换失败,禁直接取最高分
    ——「穿剌死棘之枪」对穿刺/穿越死棘之枪同分 5/6 ≈ 0.833(①段归一
    相似救援层多命中拒后落②段),旧形态取注册表序首个 = 静默错配,现判
    round_fail 零写零上报;明确唯一(「击破星甲徽」噪声插入,对击破星徽
    4/4 = 1.0 与次高追击星徽 3/4 = 0.75,差 0.25)②段照常命中 = 拒判
    不过严回归锚。红 = 歧义静默取最高分回潮 / 拒判误杀唯一命中。"""
    # ① 歧义对 → round_fail,名字与坐标同进退零写、obs 不装载
    op, session = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                 cards=[('穿剌死棘之枪', 500)])
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and '卡名标准化失败' in (rs.status or ''), (
        f'近分歧义 = 转换失败交回重读:{rs!r}')
    gs = game_state_of(session)
    assert gs.box_card_names.value is None and gs.box_card_names_xy.value \
        is None, '歧义名字坐标同进退零写'
    assert op._obs is None, '歧义不装载 obs'
    # ② 明确唯一(②段兜底命中,分差足额)→ 通过,容器落标准名
    op2, session2 = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                   cards=[('击破星甲徽', 700)])
    rs2 = _run_node(test_context, op2, op2.observe)
    assert rs2.is_success, f'②段唯一命中放行(拒判不过严):{rs2!r}'
    assert game_state_of(session2).box_card_names.value == ['击破星徽'], (
        f'②段唯一命中落标准名:'
        f'{game_state_of(session2).box_card_names.value!r}')


def test_box_pick_read_gate_admits_registry_longest_priv_name(
        test_context, monkeypatch):
    """读数闸放宽测试(:上限 ``_CARD_NAME_LEN_MAX`` = 注册表
    最长名派生(防手抄常数——手抄值在注册表最长名变化时即红),9 字特权名
    「战场进化手册·特权」经真读数闸存活(旧 8 字手抄上限先于归一化会把它
    确定性静默丢弃 = 四选一缩三选一),并经标准化门归一精确命中落容器;
    下限 2 不动(单字噪声仍滤除)。
    ``_make_box_pick`` 把 ``_read_card_names`` 整个桩掉恰好绕开闸,测闸须
    还原真读数闸直调;``cw_screen_box_pick`` 对 ``_ocr``/``_area_rect`` 是
    模块级绑定,OCR 桩打在本模块命名空间(同 takeover 管线
    ``cw_obs_core._ocr`` patch 惯用法——该屏函数内导入故打 cw_obs_core,
    本屏模块级导入故打本模块,同形不同位)。
    红 = 上限回退手抄 8 / 派生常数漂移 / 9 字名进不了容器。"""
    import importlib
    from types import MethodType

    mod = importlib.import_module(f'{_PKG}.cw_screen_box_pick')
    # 常数一致性测试:派生式对拍注册表最长名。
    assert max(
        len(n) for n in mod._EQUIP_ROSTER_LIST) == mod._CARD_NAME_LEN_MAX, (
        '读数闸上限必须派生自装备注册表最长名,禁手抄常数')
    nine = '战场进化手册·特权'
    assert len(nine) == 9 and nine in EQUIPMENT_ROSTER, (
        '用例前提:9 字特权名在册(旧 8 字闸必丢的形态)')
    op, session = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                 cards=[])
    # 还原真读数闸 + OCR/rect 桩(读数 = 9 字特权名 + 1 字噪声 + 4 字简易名)。
    monkeypatch.setattr(mod, '_area_rect',
                        lambda ctx, name, screen_name=None: 'rect',
                        raising=False)
    _rows = [SimpleNamespace(data=nine, center=SimpleNamespace(x=500)),
             SimpleNamespace(data='长', center=SimpleNamespace(x=100)),
             SimpleNamespace(data='光能电池', center=SimpleNamespace(x=900))]
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: _rows,
                        raising=False)
    monkeypatch.setattr(op, '_read_card_names',
                        MethodType(mod.CwScreenBoxPick._read_card_names, op),
                        raising=False)
    # ① 直调真读数闸:9 字名存活、1 字噪声被下限滤除、x 升序保序。
    cards = op._read_card_names('屏')
    assert cards == [(nine, 500), ('光能电池', 900)], (
        f'9 字特权名经闸存活(1 字噪声滤除):{cards!r}')
    # ② 全链观察:闸存活读数经标准化门归一精确命中(段一注册名全等)落容器。
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'观察 success 进决策:{rs!r}'
    assert game_state_of(session).box_card_names.value == [nine, '光能电池'], (
        f'归一精确命中落容器:'
        f'{game_state_of(session).box_card_names.value!r}')


def test_box_pick_act_clicks_decided_card(test_context, monkeypatch):
    """决策动作 node 测试:容器外读数决策(零参策略契约)→ 选卡链派发
    (点卡选中即确认 + 动画等待迁入 ``CwActionPickBoxCardOp``;机械链
    行为测试 = test_overlay_ops pick op)→ 选卡即终结 success。红 = 决策
    形态漂移 / 坐标现算回潮(env.target 停喂后禁再喂)/ 终结交回语义
    漂移。"""
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
    assert dispatches[0].env.target is None, (
        'env idx-only(target 停喂——坐标单一真相源 = 观察上报容器,'
        '点击坐标由动作 op 自取)')
    assert rs.is_success and '选卡即终结' in (rs.status or ''), (
        f'选卡即终结交回:{rs!r}')
    assert mod.CwScreenBoxPick.CARD_Y == 290, '画面常量在册(避让几何)'


def test_box_pick_act_off_match_fails_via_normal_chain(test_context,
                                                       monkeypatch):
    """局外无早退支测试(用户裁决 2026-09-22 全族删门,op-layer.md §1.1):
    match 缺席(局外)不设 round_success 早退门,act 沿正常链路因缺上下文
    自然失败(AttributeError),零派发零容器写。红 = 局外 round_success
    早退门回潮 / 兜底决策路径回潮(局外调机器决策/发点击/写容器)。"""
    op, session = _make_box_pick(test_context, monkeypatch, gate_ok=True,
                                 cards=list(_CARDS))
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    _run_node(test_context, op, op.observe)   # 局外观察:report 跳过,obs 照常装载
    dispatched: list = []

    class _SpyPickOp:
        def __init__(self, param, env) -> None:
            dispatched.append(self)

        def execute(self) -> bool:
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _SpyPickOp(act, env))
    with pytest.raises(AttributeError, match='strategy'):
        _run_node(test_context, op, op.act)   # 无 match 正常链路失败
    assert dispatched == [], '零派发(局外禁选卡动作)'
    assert game_state_of(session).box_card_names.value is None, '容器零写'
