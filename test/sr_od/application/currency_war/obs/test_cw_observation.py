"""cw_observation 账实金对账生产者测试(gold 域统一对账)。

锁两件事(design executor-gold-delta-retire §2.3):
1. 生产者接线语义:gap>0 产 ``obs_conflict('gold_delta', old=账面,
   new=实读)``,old/new 方向 = 容器账面在 old(告警门按 |new-old| 算
   gap,方向反了证据行失真);gap=0 / 账面 None / 同帧重入静默零产证;
2. 告警门首次可达:同一调用形态喂真告警门(kernel/cw_observe.obs_conflict),
   gap>GOLD_DELTA_ALARM_GAP → ``[cw!][alarm][gold_delta]`` 告警行;
   gap≤阈值 → 仅证据行不响。

另辖:商店免费刷新次数 Field 的入口观察锚定(漏斗 shop-open 段;
双态锚定三支,主断言对象 = 本镜像 src 的 ``read_game_state``)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_observe import (
    GOLD_DELTA_ALARM_GAP,
)
from sr_od.application.currency_war.obs import cw_observation as obs_mod
from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
    ShopRefreshButton,
)

_SIG = ChannelSig(family='obs', actor='TestGoldReconcile', mode='read')


def _make_gs_with_gold(value: int) -> GameState:
    """直构容器并预置账面金(观察态;对账基线)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, value, sig=_SIG)
    return gs


def test_gold_reconcile_beyond_alarm_gap_alarms(monkeypatch):
    """gap 超阈:生产者产证(old=账面/new=实读)→ 真告警门响
    [cw!][alarm][gold_delta](生产者上线 + 告警门首次可达)。"""
    fired: list[tuple] = []
    monkeypatch.setattr(obs_mod, 'obs_conflict',
                        lambda *a, **k: fired.append((a, k)))
    warns: list[tuple] = []
    from sr_od.application.currency_war.kernel import cw_observe as obs_gate
    monkeypatch.setattr(obs_gate._log, 'warning',
                        lambda *a, **k: warns.append(a))

    gs = _make_gs_with_gold(30)
    obs_mod._reconcile_gold_against_container(gs, 45, 'p1-r1', None)
    assert len(fired) == 1, 'gap=15>10:账实错位必须产证'
    args, kwargs = fired[0]
    assert args[0] == 'gold_delta', 'field 键 = 告警门词表 gold_delta'
    assert args[1] == 30 and args[2] == 45, 'old=账面(30) new=实读(45)'

    obs_gate.obs_conflict(*args, **kwargs)   # 同一调用形态喂真告警门
    assert any('[cw!][alarm][gold_delta]' in str(a[0]) for a in warns), \
        '超阈 → 分级告警行可达'


def test_gold_reconcile_silent_and_dedup(monkeypatch):
    """静默面与去重:gap=0 / 账面 None 零产证;0<gap≤阈值产证据行;
    同帧重入去重;跨帧照产;真告警门对 ≤ 阈值 gap 不响。"""
    fired: list[tuple] = []
    monkeypatch.setattr(obs_mod, 'obs_conflict',
                        lambda *a, **k: fired.append((a, k)))
    # 同帧去重键为模块级全局:跨测试残留防线,先复位
    monkeypatch.setattr(obs_mod, '_last_gold_reconcile_key', None)

    # 账面 None(本局尚无金读数)= 无对账基线,静默
    gs_none = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    obs_mod._reconcile_gold_against_container(gs_none, 30, 'p1-r1', None)
    assert fired == []

    gs = _make_gs_with_gold(30)
    obs_mod._reconcile_gold_against_container(gs, 30, 'p1-r1', None)
    assert fired == [], 'gap=0 账实一致,零差异不是冲突'

    obs_mod._reconcile_gold_against_container(gs, 30 + GOLD_DELTA_ALARM_GAP,
                                              'p1-r2', None)
    assert len(fired) == 1, '0<gap≤阈值:产证据行(分级归告警门)'
    obs_mod._reconcile_gold_against_container(gs, 30 + GOLD_DELTA_ALARM_GAP,
                                              'p1-r2', None)
    assert len(fired) == 1, '同帧重入(recognizer 并发形态)去重不重复产证'
    obs_mod._reconcile_gold_against_container(gs, 30 + GOLD_DELTA_ALARM_GAP,
                                              'p1-r3', None)
    assert len(fired) == 2, '跨帧 = 新事件照常产证'

    # 真告警门:阈值级 gap 只留证据不告警(≤10 维持留存证据)
    warns: list[tuple] = []
    from sr_od.application.currency_war.kernel import cw_observe as obs_gate2
    monkeypatch.setattr(obs_gate2._log, 'warning',
                        lambda *a, **k: warns.append(a))
    obs_gate2.obs_conflict('gold_delta', 30, 30 + GOLD_DELTA_ALARM_GAP, None,
                           verdict='测试')
    assert not any('[cw!][alarm][gold_delta]' in str(a[0]) for a in warns), \
        'gap≤阈值不响(证据行照落)'


# ---- 商店免费刷新次数 Field:入口观察锚定(漏斗 shop-open 段)----


def _feed_ctx(sess: SimpleNamespace) -> SimpleNamespace:
    """read_game_state 观察流测试的最小 ctx(mock ocr_service 空读;
    与 test_game_state 漏斗桩同款先例)。"""
    return SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: []),
    )


def _patch_shop_open_readers(monkeypatch: pytest.MonkeyPatch,
                             btn: ShopRefreshButton) -> None:
    """shop_open 帧读链桩(零像素;刷新钮三态读 = 注入的 ``btn``)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile

    monkeypatch.setattr(obs_mod, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs_mod, 'read_phase_round',
                        lambda ctx, screen, round_caps=None: (1, 5),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
                        (82, False), raising=False)
    monkeypatch.setattr(obs_mod, 'read_level_up_cost', lambda ctx, screen: 4,
                        raising=False)
    monkeypatch.setattr(obs_mod, 'board_from_deployed', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs_mod, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({}, False), raising=False)
    monkeypatch.setattr(obs_mod, 'read_shop_cards',
                        lambda ctx, screen, full_ocr=None: [],
                        raising=False)
    monkeypatch.setattr(obs_mod, 'read_refresh_probs', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_shop_refresh_obs'
        '.read_shop_refresh_button',
        lambda ctx, screen, gold=None: btn, raising=False)


def test_funnel_anchor_three_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """双态锚定三支一测试(零新增读屏,复用现役 read_shop_refresh_button
    产物):免费态锚次数 / 付费域锚 0(耗尽/灰态,游戏规则 ⇒ 免费余量恒
    0)/ 整帧判不出跳写(宁缺勿造)。"""
    cases = [
        (ShopRefreshButton(free=True, free_remaining=2, price=None,
                           affordable=True), 2, '免费态锚次数'),
        (ShopRefreshButton(free=False, free_remaining=None, price=2,
                           affordable=True), 0, '付费域锚 0'),
    ]
    for btn, expect, why in cases:
        sess = SimpleNamespace(last_streak=0, active_strategies=[])
        _patch_shop_open_readers(monkeypatch, btn)
        obs_mod.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
        gs = game_state_of(sess)
        assert gs.free_refresh_left.value == expect and why
        assert gs.free_refresh_left.source == 'observation', why
    # 判不出(free=None)→ 跳写:字段保持未观察
    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_shop_open_readers(
        monkeypatch, ShopRefreshButton(free=None, free_remaining=None,
                                       price=None, affordable=None))
    obs_mod.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    assert game_state_of(sess).free_refresh_left.value is None, '判不出跳写'
