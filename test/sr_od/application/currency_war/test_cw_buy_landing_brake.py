"""买牌落地验证与 miss 刹车锁(T-44;点击≠成了补齐)。

病理(run_20260918_055133 停局链):商店 5 连买投影写了 5 张购买,实读
5 卡全在(0 张成交)→ shop+gold 双失配停局。根因 = BuyCardOp 点击后
无条件落账返回 True(点击可能静默不生效),投影照写失真值。修法形态
对齐 DeployMoveOp 拖后像素验证先例:点击后对该槽位区域做像素差判定,
零变化 = 未生效 → 零落账返回 False(投影写端 apply_action_outcome 的
_ok 门两侧不动);连续 miss 由 run_buy_waves 的 buy_miss_streak 计数
(同槽累加/异槽归 1/落地成功归零),触顶 BUY_MISS_REDISPATCH_LIMIT
→ round_fail 显式停交上层(同 deploy 刹车语义)。

锁四件事:
1. 槽位像素差纯函数:零变化 = 未生效 / 可见变化 = 落地 / 缺证不可判
   保守放行(对齐 deploy._region_changed_px 取向);
2. BuyCardOp 落地门:miss 零落账(账本/tracked/期望态基座两侧不动)+
   返回 False;落地照常落账返回 True;首采无变化经 settle 重采收敛
   (动画时序误报防线,run_20260830_071711 同款);
3. miss 刹车:同槽连续 miss 触顶 → round_fail 交上层 + buy_miss_skip
   台账分键显影;
4. 单次假阳清零:miss 后一次成功购买把计数归零,后续 miss 不假满
   (永不触顶的假阳容忍语义,deploy 同依据)。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect

import sr_od.application.currency_war.operations.cw_op.cw_buy_card_action as buy_action_mod
import sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards as buy_mod
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
    CloseShop,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op.cw_buy_card_action import (
    BUY_LAND_DIFF_THRESHOLD,
    BuyCardOp,
    buy_slot_region_changed,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopExecEnv,
    ShopVisitLedger,
)
from sr_od.application.currency_war.telemetry import defects

_SIG = ChannelSig(family='logic_action', actor='CwScreenBuyCards')

# 帧尺寸 = 5 槽宽(5×96)× 槽高 270;槽 i rect = ((i-1)*96, 0, i*96, 270)。
_FRAME_H, _FRAME_W = 270, 480


def _frame() -> np.ndarray:
    return np.zeros((_FRAME_H, _FRAME_W, 3), dtype=np.uint8)


def _slot_rect(idx: int) -> Rect:
    return Rect((idx - 1) * 96, 0, idx * 96, _FRAME_H)


def _fake_area_rect(ctx, name: str, screen_name: str = '') -> Rect | None:
    try:
        idx = int(str(name).replace('商店牌-', ''))
    except ValueError:
        return None
    return _slot_rect(idx) if 1 <= idx <= 5 else None


# ===== 锁1 槽位像素差纯函数 =====

class TestBuySlotRegionChanged:

    def test_zero_diff_means_miss(self):
        """两帧同区域零差 = 槽位无可见变化 = 判未生效(False)。"""
        pre, post = _frame(), _frame()
        assert buy_slot_region_changed(pre, post, _slot_rect(1)) is False

    def test_visible_diff_means_landed(self):
        """槽位区域出现可见变化(卡片消失/替换)= 判落地(True)。"""
        pre, post = _frame(), _frame()
        post[10:_FRAME_H - 10, 5:90] = 120
        assert buy_slot_region_changed(pre, post, _slot_rect(1)) is True

    def test_missing_evidence_is_unknown_not_failure(self):
        """缺帧/两帧形状不一致/矩形越界 = 不可判(None)→ 调用方按生效
        走既有行为;验证只在两帧齐备时发声,缺证不改变既有语义。"""
        pre, post = _frame(), _frame()
        assert buy_slot_region_changed(None, post, _slot_rect(1)) is None
        assert buy_slot_region_changed(pre, None, _slot_rect(1)) is None
        bad = np.zeros((_FRAME_H + 8, _FRAME_W, 3), dtype=np.uint8)
        assert buy_slot_region_changed(pre, bad, _slot_rect(1)) is None
        assert buy_slot_region_changed(pre, post,
                                       Rect(999, 999, 1200, 1200)) is None

    def test_threshold_aligned_with_deploy_precedent(self):
        """阈值与 DeployMoveOp 落位阈值同量级(同族形态同取向,防某侧
        静默漂移成漏报/误报失衡)。"""
        from sr_od.application.currency_war.operations.cw_op.\
            cw_deploy_move_action import DEPLOY_LAND_DIFF_THRESHOLD
        assert BUY_LAND_DIFF_THRESHOLD == DEPLOY_LAND_DIFF_THRESHOLD


# ===== 锁2 BuyCardOp 落地门 =====

def _buy_op_env(monkeypatch: pytest.MonkeyPatch, frames: list[np.ndarray]):
    """BuyCardOp 离线执行环境(零真实副作用):容器在屏 payload 槽1 =
    花火;frames = op.screenshot 依序弹出(基线 → 点击后首采 → 重采)。
    返回 (op, env, ledger, gs)。"""
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


def test_buy_miss_returns_false_and_books_nothing(monkeypatch):
    """落地门 miss 臂:点击后槽位像素零变化(首采+settle 重采均零差)
    → 返回 False + 零落账(账本/tracked 两侧不动)——投影写端
    apply_action_outcome 的 _ok 门据此跳写,失真值从未写下。"""
    zeros = _frame()
    op, env, ledger, gs, clicks = _buy_op_env(
        monkeypatch, [zeros.copy(), zeros.copy(), zeros.copy()])

    ok = op.execute(env)

    assert ok is False
    assert clicks, '判定必须发生在点击之后(先发射后验证,非前置拦截)'
    assert ledger.total_buy == 0 and ledger.spend_executed == 0
    assert ledger.bought_names == [] and ledger.buy_purchases == []
    assert [b for b in gs.tracked_books.bench if b is not None] == []
    assert env.last_buy_slot_no == 1   # miss 键旁路上报(计数消费面)


def test_buy_landed_returns_true_and_books(monkeypatch):
    """落地门成功臂:槽位像素可见变化(卡片被买走)→ 返回 True + 照常
    落账(账本/tracked/期望态基座全落),行为与旧实现逐位一致。"""
    pre, post = _frame(), _frame()
    post[10:_FRAME_H - 10, 5:90] = 120
    op, env, ledger, gs, _clicks = _buy_op_env(
        monkeypatch, [pre, post])

    ok = op.execute(env)

    assert ok is True
    assert ledger.total_buy == 1 and ledger.spend_executed == 3
    assert ledger.bought_names == ['花火']
    assert len(ledger.buy_purchases) == 1
    assert [(b.char_id, b.star)
            for b in gs.tracked_books.bench if b is not None] == [('花火', 1)]


def test_buy_first_read_anim_then_settle_converges_landed(monkeypatch):
    """settle 重采臂:首采恰逢卡牌飞行动画零差 → 延迟重采一次收敛判
    落地(观测时序防线,先例 run_20260830_071711 买真实执行纯时序误报)。"""
    zeros, changed = _frame(), _frame()
    changed[10:_FRAME_H - 10, 5:90] = 120
    op, env, ledger, gs, _clicks = _buy_op_env(
        monkeypatch, [zeros.copy(), zeros.copy(), changed])

    ok = op.execute(env)

    assert ok is True
    assert ledger.total_buy == 1
    assert [(b.char_id, b.star)
            for b in gs.tracked_books.bench if b is not None] == [('花火', 1)]


# ===== 锁3/锁4 miss 刹车与单次假阳清零(run_buy_waves 决策循环)=====

def _spy_defects(monkeypatch) -> list[tuple]:
    rows: list[tuple] = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append((surface, kind, expected, observed))

    monkeypatch.setattr(defects, 'record_defect', _rec)
    return rows


def _run_waves_miss_host(monkeypatch, tmp_path, counters: dict,
                         exec_results: list[bool]) -> tuple:
    """miss 刹车流锁离线宿主:策略替身按动作队列连发同槽 BuyCard,
    动作执行替身按 exec_results 逐动作返回落地事实(False = 槽位像素
    零变化,miss)。替身缝 = shop_action_op_for(函数内 lazy import,
    每轮取模块属性)。返回 (run_buy_waves 结果元组, session)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_shop_actions \
        as shop_actions_mod
    from sr_od.application.currency_war.obs.cw_observation import (
        GameStateReadReceipt,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        economy_cycle as economy_cycle_mod,
    )
    from sr_od.application.currency_war.telemetry import recorder as rec_mod
    from sr_od.application.currency_war.telemetry import state as tel_state

    # 遥测单例隔离(缺陷台账去重键;行落 tmp_path)。
    monkeypatch.setattr(tel_state, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 't44host')
    monkeypatch.setattr(tel_state, '_defect_seen', {})
    monkeypatch.setattr(tel_state, '_defect_seen_run', '')

    card = ShopCard(x=50, slot=1, name='花火', faction='?', cost=3, star=1)
    actions_q: list = [BuyCard(card=card) for _ in exec_results]
    actions_q.append(CloseShop())

    class _SeqStrategy:
        """替身决策源:逐轮弹动作队列(空 = 关店终结)。"""

        def decide_shop_action(self):
            return actions_q.pop(0) if actions_q else CloseShop()

    match = CurrencyWarMatch(_SeqStrategy(), StrategySession())
    match.session.strategy_state = SimpleNamespace(
        cw4_counters=counters, cw4_segment_serial=0)
    # 容器在屏 payload(同卡;guard 提案牌名对票 + 直写基座)。
    game_state_of(match.session).write_logic(
        game_state_of(match.session).shop,
        ShopPayload(cards=[ShopSlot(kind='content', card=card)]
                    + [ShopSlot(kind='empty') for _ in range(4)],
                    refresh_probs={}),
        produced_by='test', sig=_SIG)

    class _FakeActionOp:
        terminal = False

        def __init__(self, action):
            self.action = action

        def execute(self, env) -> bool:
            ok = exec_results.pop(0)
            if not ok:
                env.last_buy_slot_no = 1
            return ok

    monkeypatch.setattr(shop_actions_mod, 'shop_action_op_for',
                        lambda a: _FakeActionOp(a))
    # 落地直写腿会移除容器店牌(fka 落地),后续 miss 轮的提案牌名对票
    # 由 guard 承担——本锁面是计数非 guard,桩成 no-op 保持面窄。
    import sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops \
        as shop_ops_mod
    monkeypatch.setattr(shop_ops_mod, 'guard_proposal_vs_expected',
                        lambda a, s: None)

    class _Op:
        ctx = SimpleNamespace(current_instance_idx=1)

        def screenshot(self) -> bytes:
            return b''

        def park_cursor(self, after_wait: float = 0.0) -> None:
            pass

        def save_screenshot(self, prefix: str = '') -> str:
            return ''

        def round_fail(self, status: str = None, data=None,
                       wait: float = None):
            return SimpleNamespace(status=status, is_success=False)

    def _entry_receipt(*a, **k) -> GameStateReadReceipt:
        return GameStateReadReceipt(gold=10, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=5, plane=1, round_num=8)

    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points', lambda ctx: [])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)

    result = buy_mod.run_buy_waves(_Op(), match)
    return result, match.session


def test_consecutive_miss_brakes_at_limit(monkeypatch, tmp_path):
    """锁3 miss 刹车:同槽连续 3 次 miss 触顶 → round_fail 显式停交上层
    (同 deploy 刹车语义;消费面按 rr 非 None 收口)+ buy_miss_skip 台账
    分键逐次显影(防静默)。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {}

    (rr, ledger), _session = _run_waves_miss_host(
        monkeypatch, tmp_path, counters, [False, False, False])

    assert rr is not None and not rr.is_success   # 刹车停交上层
    assert ledger is not None   # 访问账本随行(上层判 rr 即收失败)
    assert counters['buy_miss_streak_n'] == 3   # 同槽累加
    assert counters['buy_miss_streak_slot'] == 1
    assert sum(1 for _s, kind, _e, _o in rows if kind == 'buy_miss_skip') == 3


def test_single_false_positive_resets_and_never_brakes(monkeypatch, tmp_path):
    """锁4 单次假阳清零:miss → 落地 → miss ×2 ——成功购买把计数归零,
    后续 miss 从 1 重计不假满(4 次动作终局 rr=None 正常收工;若清零
    失效,第 4 次动作会使 streak 达 4 触顶假停)。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {}

    (rr, ledger), _session = _run_waves_miss_host(
        monkeypatch, tmp_path, counters, [False, True, False, False])

    assert rr is None and ledger is not None   # 正常收工(未触顶)
    assert counters['buy_miss_streak_n'] == 2   # 归零后从 1 重计到 2
    miss_rows = [r for r in rows if r[1] == 'buy_miss_skip']
    assert len(miss_rows) == 3   # 三次 miss 各留证,刹车零触发


def test_brake_status_pure_read_semantics():
    """触顶判定纯读形态:tick 3 次同槽后 status 出文案;reset 后 None
    (文案单一源,对齐 deploy_miss_brake_status 形态)。"""
    session = StrategySession()
    session.strategy_state = SimpleNamespace(cw4_counters={},
                                             cw4_segment_serial=0)
    assert buy_mod.buy_miss_brake_status(session) is None
    for _ in range(buy_mod.BUY_MISS_REDISPATCH_LIMIT - 1):
        buy_mod.buy_miss_streak_tick(session, 1)
    assert buy_mod.buy_miss_brake_status(session) is None   # 差一次不触顶
    buy_mod.buy_miss_streak_tick(session, 2)   # 异槽归 1 重计
    assert buy_mod.buy_miss_brake_status(session) is None
    buy_mod.buy_miss_streak_tick(session, 2)
    buy_mod.buy_miss_streak_tick(session, 2)   # 同槽累加至 3
    assert buy_mod.buy_miss_brake_status(session) is not None
    buy_mod.buy_miss_streak_reset(session)   # 落地成功归零
    assert buy_mod.buy_miss_brake_status(session) is None


def test_miss_counter_carrier_absent_is_noop():
    """载体缺席(第三方策略面)= 无计数面零动作(与
    _note_shop_skip_unobserved 缺席退缺省口径同;帧帽仍兜底防无界)。"""
    session = StrategySession()   # strategy_state 缺省 None
    assert buy_mod.buy_miss_streak_tick(session, 1) == 0
    buy_mod.buy_miss_streak_reset(session)   # 零动作不炸
    assert buy_mod.buy_miss_brake_status(session) is None
