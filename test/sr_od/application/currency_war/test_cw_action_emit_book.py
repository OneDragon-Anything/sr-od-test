"""CW 动作 op「机械执行 + 发出即记账」语义锁(验证/重试机制拆除批)。

用户裁定(规范级):动作 op = 机械执行,动作层禁设一切判效与重试——
落地判定归观察侧 reconcile 对账;重试/再规划 = 决策循环按新观察自然
重决策;动作未生效 = 动作层修执行可靠性。拖拽/点击静默不生效属执行
环境噪声,由下一入口 heavy 实读对账显影(账实失配 → 安灯停 → 按真
bug 修),不是投影 bug。

本锁钉拆除后的「发出即记账」语义(原 T-22 部署 / T-44 买牌 / T-55
穿戴三件落地像素验证 + miss 刹车随拆除退役):
1. BuyCardOp:点击后零像素验证,恒返回 True + 账本/tracked 直写;
   买前裁片 = 纯留证零判效(保留面);
2. WearEquipOp:单次机械拖拽 + emitted=True(拖后零读屏零判定);
   定位落空 = 未发出通道(emitted=False),非判效语义保留;
3. DeployMoveOp:拖拽发出即 tracked 记上阵(拖后画面零变化也不回滚
   ——零判效的直接证据)。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect

import sr_od.application.currency_war.operations.cw_op.cw_buy_card_action \
    as buy_action_mod
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopPayload,
    ShopSlot,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    DeployMove,
    ShopCard,
    WearEquip,
)
from sr_od.application.currency_war.operations.cw_op.cw_buy_card_action import (
    BuyCardOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_deploy_move_action \
    import DeployMoveOp
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopExecEnv,
    ShopVisitLedger,
)
from sr_od.application.currency_war.operations.cw_op.cw_wear_equip_action \
    import WearEquipOp
from sr_od.application.currency_war.prep_actions import PrepExecEnv

_SIG = ChannelSig(family='logic_action', actor='CwScreenBuyCards')

# 帧尺寸 = 5 槽宽(5×96)× 槽高 270;槽 i rect = ((i-1)*96, 0, i*96, 270)。
_FRAME_H, _FRAME_W = 270, 480


def _frame() -> np.ndarray:
    return np.zeros((_FRAME_H, _FRAME_W, 3), dtype=np.uint8)


# ============================================================
# 锁1 BuyCardOp:点击发出即记账(零像素验证,恒 True)
# ============================================================

def _fake_area_rect(ctx, name: str, screen_name: str = '') -> Rect | None:
    try:
        idx = int(str(name).replace('商店牌-', ''))
    except ValueError:
        return None
    return (Rect((idx - 1) * 96, 0, idx * 96, _FRAME_H)
            if 1 <= idx <= 5 else None)


def _buy_op_env(monkeypatch: pytest.MonkeyPatch,
                frames: list[np.ndarray]):
    """BuyCardOp 离线执行环境(零真实副作用):容器在屏 payload 槽1 =
    花火;frames = op.screenshot 依序弹出(拆除后仅买前裁片一采)。
    返回 (op, env, ledger, gs, clicks)。"""
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

        def screenshot(self):
            return frames.pop(0) if frames else None

    env = ShopExecEnv(
        op=_Op(), match=SimpleNamespace(session=session), config=None,
        click_pts=[Point(50, 50)], level_btn=None, refresh_btn=None,
        ledger=ledger, state=gs)
    monkeypatch.setattr(buy_action_mod, '_area_rect', _fake_area_rect)
    monkeypatch.setattr(buy_action_mod.time, 'sleep', lambda s: None)
    return BuyCardOp(BuyCard(card=card)), env, ledger, gs, clicks


def test_buy_card_emits_and_books_unconditionally(monkeypatch):
    """机械执行主锁:拖后画面零变化(同帧零差)也恒返回 True + 照常落账
    (账本/tracked 全落)——零判效的直接证据;落地真值归下一入口观察
    对账(静默不生效 → shop+gold 失配安灯停,按真 bug 修)。"""
    frame = _frame()   # 点击前后同帧 = 旧像素验证必判 miss 的形态
    op, env, ledger, gs, clicks = _buy_op_env(monkeypatch, [frame])

    ok = op.execute(env)

    assert ok is True, '发出即记账(返回恒 True,零判效)'
    assert clicks, '机械点击已发出'
    assert ledger.total_buy == 1 and ledger.spend_executed == 3
    assert ledger.bought_names == ['花火']
    assert len(ledger.buy_purchases) == 1
    assert ledger.buy_purchases[0].crop is not None, \
        '买前裁片 = 纯留证零判效(保留面)'
    assert [(b.char_id, b.star)
            for b in gs.tracked_books.bench if b is not None] == [('花火', 1)]


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
    ex._wait_stable_frame = lambda *a, **k: None
    env = PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    monkeypatch.setattr('time.sleep', lambda _s: None)
    return WearEquipOp(WearEquip(item_name='轮滑鞋', char_name='刃',
                                 row='front', slot=1)), env, drags, screens


def test_wear_equip_single_mechanical_drag_emits(monkeypatch):
    """发出即记账主锁:单次机械拖拽(无补救链重试)+ emitted=True +
    拖后零读屏(零落地判定);定位落空 = 未发出通道(emitted=False,
    非判效语义保留)。"""
    op, env, drags, screens = _wear_env(monkeypatch)

    ok = op.execute(env)

    assert ok is True
    assert len(drags) == 1, '单次机械拖拽(无重试链)'
    assert env.emitted is True, '发出即记账'
    assert '已发' in env.detail
    assert screens == [], '拖后零读屏(落地判定归观察侧对账)'

    # 定位落空 = 未发出通道(计划失效,下帧重派重算;非 miss 判效)
    op2, env2, drags2, _screens = _wear_env(monkeypatch)
    env2.executor._owned_grid_locate = lambda name: None
    assert op2.execute(env2) is True
    assert env2.emitted is False and drags2 == []


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
        'round_by_find_area': staticmethod(
            lambda *a, **k: type('_R', (), {'is_success': False})()),
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
    gs.tracked_books.bench = [None, BenchChar(slot=2, char_id='甲', star=1)]

    env = _deploy_env(session)
    action = DeployMove(bench_idx=1, to_row='front', faction='')
    ok = DeployMoveOp(action).execute(env)

    assert ok is True, '机械发出即职责完成(返回契约不变)'
    assert env.emitted is True, '发出即记账'
    assert '发出即记账' in env.detail
    moved = [d for d in gs.tracked_books.deployed
             if d is not None and d.char_id == '甲']
    assert moved, 'tracked 记上阵(拖后零变化也照记 = 零判效)'
    assert all(b is None or b.char_id != '甲'
               for b in (gs.tracked_books.bench or [])), 'bench 侧摘除照旧'
