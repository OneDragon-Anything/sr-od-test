"""CW 动作 op「机械执行 + 发出即记账」语义锁(验证/重试机制拆除批)。

用户裁定(规范级):动作 op = 机械执行,动作层禁设一切判效与重试——
落地判定归观察侧 reconcile 对账;重试/再规划 = 决策循环按新观察自然
重决策;动作未生效 = 动作层修执行可靠性。拖拽/点击静默不生效属执行
环境噪声,由下一入口 heavy 实读对账显影(账实失配 → 安灯停 → 按真
bug 修),不是投影 bug。

本锁钉拆除后的「发出即记账」语义(原 T-22 部署 / T-44 买牌 / T-55
穿戴三件落地像素验证 + miss 刹车随拆除退役):
1. BuyCardOp:点击后零像素验证零读屏,发出即成功态 + 账本/tracked 直写
   (买前裁片已随动作 op 零读屏收口退役,证据职能归下一入口观察);
   槽解析失败(payload 无此牌,card.slot 旧档兜底已删)/槽号越界/点位
   缺失 = 显式 round_fail 未发出事实(禁兜底坐标静默点击);
2. WearEquipOp:单次机械拖拽 + emitted=True(拖后零读屏零判定);
   定位落空 = 未发出通道(emitted=False),非判效语义保留;
3. DeployMoveOp:拖拽发出即 tracked 记上阵(拖后画面零变化也不回滚
   ——零判效的直接证据)。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

import sr_od.application.currency_war.operations.cw_op.cw_buy_card_action as buy_action_mod
from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    ShopPayload,
    ShopSlot,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionDeployMoveParam,
    CwActionWearEquipParam,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op.cw_buy_card_action import (
    CwActionBuyCardOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_deploy_move_action import (
    CwActionDeployMoveOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopExecEnv,
    ShopVisitLedger,
)
from sr_od.application.currency_war.operations.cw_op.cw_wear_equip_action import (
    CwActionWearEquipOp,
)
from sr_od.application.currency_war.prep_actions import PrepExecEnv

_SIG = ChannelSig(family='logic_action', actor='CwScreenShop')


# ============================================================
# 锁1 BuyCardOp:点击发出即记账(零像素验证,恒 True)
# ============================================================


def _buy_op_env(monkeypatch: pytest.MonkeyPatch,
                click_pts: list[Point] | None = None):
    """BuyCardOp 离线执行环境(零真实副作用,零读屏替身):容器在屏
    payload 槽1 = 花火;click_pts 可参(缺省槽1命中)。返回 (op, env,
    ledger, gs, clicks)。"""
    session = StrategySession()
    gs = game_state_of(session)
    card = ShopCard(x=50, slot=1, name='花火', faction='?', cost=3, star=1)
    gs.write_logic(
        gs.shop,
        ShopPayload(cards=[ShopSlot(kind='content', card=card)]
                    + [ShopSlot(kind='empty') for _ in range(4)],
                    refresh_probs={}),
        produced_by='test', sig=_SIG)
    ledger = ShopVisitLedger()
    clicks: list = []

    class _Ctrl:
        def click(self, pt) -> None:
            clicks.append(pt)

    class _Op:
        ctx = SimpleNamespace(controller=_Ctrl())

    env = ShopExecEnv(
        op=_Op(), match=SimpleNamespace(session=session), config=None,
        click_pts=click_pts if click_pts is not None else [Point(50, 50)],
        level_btn=None, refresh_btn=None,
        ledger=ledger, state=gs)
    monkeypatch.setattr(buy_action_mod.time, 'sleep', lambda s: None)
    return CwActionBuyCardOp(env.op.ctx, CwActionBuyCardParam(card=card), env=env), env, ledger, gs, clicks


def test_buy_card_emits_and_books_unconditionally(monkeypatch):
    """机械执行主锁:恒返回 True + 照常落账(账本/tracked 全落)——零判效
    的直接证据;落地真值归下一入口观察对账(静默不生效 → shop+gold 失配
    安灯停,按真 bug 修)。"""
    op, env, ledger, gs, clicks = _buy_op_env(monkeypatch)

    ok = op.run()

    assert ok.is_success, '发出即记账(round 成功态,零判效)'
    assert clicks, '机械点击已发出'
    assert ledger.total_buy == 1 and ledger.spend_executed == 3
    assert ledger.bought_names == ['花火']
    assert len(ledger.buy_purchases) == 1
    assert [(b.unit.char_id, b.unit.star)
            for b in gs.tracked_books.bench if b is not None] == [('花火', 1)]


def test_buy_card_missing_slot_point_fails_loudly(monkeypatch):
    """兜底坐标清除锁:槽号越界(点位缺失同出口)→ 显式 round_fail
    (错误信息带 area 名,与 level_btn/refresh_btn 同款纪律),零点击
    零记账——禁兜底坐标静默点击(坐标单一真相源)。"""
    op, _env, ledger, _gs, clicks = _buy_op_env(monkeypatch, click_pts=[])

    ok = op.run()

    assert ok.is_success is False, '点位缺失 = 显式失败(非兜底点击)'
    assert '商店牌-' in (ok.status or ''), '错误信息带 area 名'
    assert clicks == [], '零点击(禁兜底坐标)'
    assert ledger.total_buy == 0, '零记账(动作未发出)'


# ============================================================
# B 层解析链两档契约锁(buy_cards §2.2-B:解析恰两档,card.slot 旧档
# 兜底已删;失败语义 = 逐形态 round_fail 未发出事实,零记账零点击)
# ============================================================


def _buy_op_env_ex(monkeypatch: pytest.MonkeyPatch, *, slots: list,
                   action_card: ShopCard, click_pts: list[Point]):
    """B 层失败形态宿主:payload 槽阵列/动作牌/点表全可参,其余与
    _buy_op_env 同式(零真实副作用,零读屏)。返回 (op, ledger, clicks)。"""
    session = StrategySession()
    gs = game_state_of(session)
    gs.write_logic(
        gs.shop,
        ShopPayload(cards=list(slots), refresh_probs={}),
        produced_by='test', sig=_SIG)
    ledger = ShopVisitLedger()
    clicks: list = []

    class _Ctrl:
        def click(self, pt) -> None:
            clicks.append(pt)

    class _Op:
        ctx = SimpleNamespace(controller=_Ctrl())

    env = ShopExecEnv(
        op=_Op(), match=SimpleNamespace(session=session), config=None,
        click_pts=click_pts, level_btn=None, refresh_btn=None,
        ledger=ledger, state=gs)
    monkeypatch.setattr(buy_action_mod.time, 'sleep', lambda s: None)
    return (CwActionBuyCardOp(env.op.ctx, CwActionBuyCardParam(card=action_card),
                              env=env), ledger, clicks)


def test_buy_card_unknown_proposal_fails_without_slot_fallback(monkeypatch):
    """B 层·槽解析失败:payload 无此牌(身份同一性 ∧ (name,star) 双未
    命中)→ round_fail 非 round_success,信息含 slot_no=None 与双未命中
    形态——card.slot 旧档兜底已删,提案数据 bug 响亮暴露(静默错槽
    掩盖 bug 禁);零点击零记账。"""
    in_shop = ShopCard(x=60, slot=2, name='景元', faction='?', cost=4, star=2)
    ghost = ShopCard(x=50, slot=0, name='花火', faction='?', cost=3, star=1)
    op, ledger, clicks = _buy_op_env_ex(
        monkeypatch,
        slots=[ShopSlot(kind='content', card=in_shop)]
        + [ShopSlot(kind='empty') for _ in range(4)],
        action_card=ghost, click_pts=[Point(50, 50)] * 5)

    rr = op.run()

    assert rr.is_success is False, 'payload 无此牌 = round_fail(非恒 success)'
    status = rr.status or ''
    assert 'slot_no=None' in status, '信息含 slot_no=None 形态'
    assert '身份未命中' in status, '信息含双未命中形态'
    assert clicks == [] and ledger.total_buy == 0, '零点击零记账(未发出事实)'
    assert ledger.spend_executed == 0 and ledger.bought_names == [], \
        '记账面零增量'


def test_buy_card_slot_out_of_range_fails(monkeypatch):
    """B 层·槽号越界:payload 槽号 7 对 5 点表 → round_fail 越界形态
    (信息含 slot 与点表长,槽号-点表不一致 = 建档/数据漂移上游显影);
    零点击零记账。"""
    deep = ShopCard(x=70, slot=7, name='停云', faction='?', cost=2, star=1)
    op, ledger, clicks = _buy_op_env_ex(
        monkeypatch,
        slots=[ShopSlot(kind='empty') for _ in range(6)]
        + [ShopSlot(kind='content', card=deep)],
        action_card=deep, click_pts=[Point(50, 50)] * 5)

    rr = op.run()

    assert rr.is_success is False, '槽号越界 = round_fail'
    status = rr.status or ''
    assert 'slot=7' in status and 'click_pts=5' in status, \
        '信息含槽号与点表长(槽号-点表不一致形态)'
    assert '槽号-点表不一致' in status
    assert clicks == [] and ledger.total_buy == 0, '零点击零记账(未发出事实)'


# ============================================================
# 锁2 WearEquipOp:单次机械拖拽 + emitted=True(拖后零判定)
# ============================================================

def _wear_env(monkeypatch: pytest.MonkeyPatch) -> tuple:
    """WearEquipOp 离线执行环境(零真实副作用):坐标注入绕 screen_info
    (拖点/源件格心固定),screens = 截图调用计数;返回 (op, env,
    拖拽记录, 截图计数列表)。"""
    drags: list = []
    screens: list[int] = []
    controller = type('_Ctl', (), {
        'mouse_move': lambda self, p: None,
        'drag_to': lambda self, **kw: drags.append(kw),
    })()
    sl = type('_SL', (), {'get_screen': lambda self, n: None})()
    op = type('_Op', (), {
        'screenshot': lambda self: (screens.append(1)
                                    or np.zeros((4, 4), dtype='uint8')),
        'park_cursor': lambda self, **kw: None,
        'ctx': type('_Ctx', (), {
            'controller': controller,
            'cw_match': None,
            'run_context': None,
            'screen_loader': sl,
        })(),
    })()
    ctx = op.ctx
    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor(op, ctx)
    ex._bench_pts = [Point(300, 800)] * 9
    ex._front_pts = [Point(300 + i * 140, 400) for i in range(4)]
    ex._back_pts = [Point(300 + i * 140, 620) for i in range(6)]
    # 坐标边注入(替身缝 = 执行器实例方法;等价于 screen_info 命中形态)。
    ex._equip_slot_drag_point = lambda row, slot: Point(420, 421)
    ex._owned_grid_locate = lambda name: Point(1768, 247)
    env = PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    monkeypatch.setattr('time.sleep', lambda _s: None)
    return CwActionWearEquipOp(ctx, CwActionWearEquipParam(item_name='轮滑鞋', char_name='刃',
                                        row='front', slot=1), env=env), env, drags, screens


def test_wear_equip_single_mechanical_drag_emits(monkeypatch):
    """发出即记账主锁:单次机械拖拽(无补救链重试)+ emitted=True +
    拖后零读屏(零落地判定);定位落空 = 未发出通道(emitted=False,
    非判效语义保留)。"""
    op, env, drags, screens = _wear_env(monkeypatch)

    ok = op.run()

    assert ok.is_success
    assert len(drags) == 1, '单次机械拖拽(无重试链)'
    assert ok.is_success, '发出即记账(round 成功态)'
    assert '已发' in (ok.status or '')
    assert screens == [], '拖后零读屏(落地判定归观察侧对账)'

    # 定位落空 = 未发出通道(计划失效,下帧重派重算;非 miss 判效)
    op2, env2, drags2, _screens = _wear_env(monkeypatch)
    env2.executor._owned_grid_locate = lambda name: None
    _r2 = op2.run()
    assert _r2.is_success is False and drags2 == []


# ============================================================
# 锁3 DeployMoveOp:拖拽发出即 tracked 记上阵(零判效)
# ============================================================

def _deploy_env(session: object | None):
    """DeployMoveOp 离线执行环境(坐标注入;截图序列 scripted)。"""
    from sr_od.application.currency_war import prep_actions as pa
    controller = type('_Ctl', (), {
        'mouse_move': lambda self, p: None,
        'drag_to': lambda self, **kw: None,
    })()
    sl = type('_SL', (), {'get_screen': lambda self, n: None})()
    op = type('_Op', (), {
        'screenshot': staticmethod(lambda: None),
        'park_cursor': staticmethod(lambda **kw: None),
        'ctx': type('_Ctx', (), {
            'controller': controller,
            'cw_match': (None if session is None
                         else type('_M', (), {'session': session})()),
            'run_context': None,
            'screen_loader': sl,
        })(),
    })()
    ctx = op.ctx
    ex = pa.PrepActionExecutor(op, ctx)
    ex._bench_pts = [Point(300, 800)] * 9
    ex._front_pts = [Point(300 + i * 140, 400) for i in range(4)]
    ex._back_pts = [Point(300 + i * 140, 620) for i in range(6)]
    env = PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    return env


def test_deploy_move_tracks_immediately_on_emit(monkeypatch):
    """发出即记账主锁:拖拽发出即 tracked 记上阵 + bench 摘除;拖后
    画面零变化(零差帧形态)也不回滚不申报——落地判定归观察侧 reconcile
    (静默不生效 → 账实失配安灯停,按真 bug 修)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    session = StrategySession()
    gs = game_state_of(session)
    gs.tracked_books.bench = [None, BenchSlot(kind='unit', unit=Unit(
        char_id='甲', star=1))]

    env = _deploy_env(session)
    action = CwActionDeployMoveParam(bench_idx=1, to_row='front', to_slot=1,
                                     faction='')
    ok = CwActionDeployMoveOp(env.op.ctx, action, env=env).run()

    assert ok.is_success, '机械发出即职责完成(round 成功态)'
    assert ok.is_success, '发出即记账'
    assert '发出即记账' in (ok.status or '')
    moved = [d for d in gs.tracked_books.deployed
             if d is not None and d.char_id == '甲']
    assert moved, 'tracked 记上阵(拖后零变化也照记 = 零判效)'
    assert all(b is None or b.kind != 'unit' or b.unit is None
               or b.unit.char_id != '甲'
               for b in (gs.tracked_books.bench or [])), 'bench 侧摘除照旧'
