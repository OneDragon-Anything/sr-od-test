"""商店免费刷新次数 GameState Field 化回归锁(迭代
 阶段 3.2;设计依据 =
 与
details/shop-visit-loop.md §2.3/§2.9)。

判据 ↔ 测试对照(landing §3.2 完成判据):

- 双态锚定三支(免费态锚次数/付费域锚 0/判不出跳写)
        → test_funnel_anchor_three_states
- observe 覆盖 logic 失配走既有安灯(Field 机制白送)
        → test_anchor_covers_logic_mismatch_fires_andon
- 扣减写端 produced_by/evidence 断言 + 未观察保守按付费
        → test_report_free_leg_deducts_field /
          test_report_unobserved_field_conservative_paid
- 两桥发放写端 produced_by/evidence(None 基 = 0 起算;值语义锁在
  test_cw_game_state 桥面,此处锁写端调用面元数据)
        → test_grant_bridges_field_write_end
- 随机态采样(固定种子确定性 + write_logic_rand 通道语义:observe 覆盖
  差异落 logic_rand_outcome 台账、不进失配安灯三分流)
        → test_report_random_leg_deterministic /
          test_report_random_leg_rand_outcome_not_andon
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import REFRESH_PROB
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_refresh_shop_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    ShopPayload,
    ShopSlot,
    consume_defect_sink,
    game_state_of,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_EFFECTS
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionRefreshShopParam,
)
from sr_od.application.currency_war.obs import cw_observation as obs
from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
    ShopRefreshButton,
)

_LSIG = ChannelSig(family='logic_action', actor='CwShopRefreshFieldTest',
                   mode='compute')
_HSIG = ChannelSig(family='logic_hook', actor='CwShopRefreshFieldTest',
                   mode='compute')
_OSIG = ChannelSig(family='obs', actor='CwShopRefreshFieldTest', mode='read')


class _ExecutedStub:
    """executed 回执桩(仅 refresh_paid 字段面;duck 型,免 import 真类)。"""

    def __init__(self, refresh_paid: int) -> None:
        self.refresh_paid = refresh_paid


def _fresh_gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _spy_write_logic(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """GameState.write_logic 调用面捕获(produced_by 不落 Field,写端
    produced_by/evidence 断言 = 调用面锁):收 (field, value, produced_by,
    evidence) 四元组,调用照常透传。"""
    captured: list[tuple] = []
    real = GameState.write_logic

    def _spy(self: GameState, target, value, **kw):
        captured.append((self._field_name(target), value,
                         kw.get('produced_by'), kw.get('evidence')))
        return real(self, target, value, **kw)

    monkeypatch.setattr(GameState, 'write_logic', _spy)
    return captured


# ============================================================ 观察锚定(漏斗 shop-open 段)


def _feed_ctx(sess: SimpleNamespace) -> SimpleNamespace:
    """read_game_state 观察流测试的最小 ctx(mock ocr_service 空读;
    与 test_cw_game_state 漏斗桩同款先例)。"""
    return SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: []),
    )


def _patch_shop_open_readers(monkeypatch: pytest.MonkeyPatch,
                             btn: ShopRefreshButton) -> None:
    """shop_open 帧读链桩(零像素;刷新钮三态读 = 注入的 ``btn``)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile

    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs, 'read_phase_round',
                        lambda ctx, screen, round_caps=None: (1, 5),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_level_up_cost', lambda ctx, screen: 4,
                        raising=False)
    monkeypatch.setattr(obs, 'board_from_deployed', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({}, False), raising=False)
    monkeypatch.setattr(obs, 'read_shop_cards',
                        lambda ctx, screen, full_ocr=None: [],
                        raising=False)
    monkeypatch.setattr(obs, 'read_refresh_probs', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_shop_refresh_obs'
        '.read_shop_refresh_button',
        lambda ctx, screen, gold=None: btn, raising=False)


def test_funnel_anchor_three_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """双态锚定三支一锁(零新增读屏,复用现役 read_shop_refresh_button
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
        obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
        gs = game_state_of(sess)
        assert gs.free_refresh_left.value == expect and why
        assert gs.free_refresh_left.source == 'observation', why
    # 判不出(free=None)→ 跳写:字段保持未观察
    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_shop_open_readers(
        monkeypatch, ShopRefreshButton(free=None, free_remaining=None,
                                       price=None, affordable=None))
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    assert game_state_of(sess).free_refresh_left.value is None, '判不出跳写'


def test_anchor_covers_logic_mismatch_fires_andon(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """失配对账 = Field 机制白送:动作扣减/发放登记的 logic 值被下一入口
    观察覆盖,失配走既有 observe_vs_logic_mismatch 安灯(缺陷行 + 钩子),
    零手写台账。"""
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )

    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = _fresh_gs()
    gs.write_logic(gs.free_refresh_left, 1,
                   produced_by='CwActionRefreshShopParam',
                   evidence='proj_refresh_free_left', sig=_LSIG)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.free_refresh_left, 2, sig=_OSIG)   # 入口实读 2 次 ≠ 账面 1
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows) == 1 and rows[0]['kind'] == 'observe_vs_logic_mismatch'
    assert fired and fired[0] == rows[0], '既有安灯被调(行同构)'
    assert gs.free_refresh_left.source == 'observation', '观察赢覆盖照常'


# ============================================================ 动作上报扣减(逻辑态)


def test_report_free_leg_deducts_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """免费腿扣减:Field 值 > 0 → 免费帧——Field write_logic 扣减(下限 0)
    + 付费计数不动 + 写端 produced_by/evidence 断言。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _fresh_gs()
    gs.observe(gs.level, 3, sig=_OSIG)
    gs.write_logic(gs.free_refresh_left, 2, produced_by='EffectLedgerBridge',
                   evidence='effect_burst@p1-r2', sig=_HSIG)
    captured.clear()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        executed=_ExecutedStub(refresh_paid=0),
        rng=random.Random('cw-shop-field-test'))
    assert gs.free_refresh_left.value == 1, '免费帧 Field 扣减 2→1'
    assert gs.free_refresh_left.source == 'logic'
    assert captured == [('free_refresh_left', 1, 'CwActionRefreshShopParam',
                         'proj_refresh_free_left')], '写端调用面元数据'
    assert gs.effects.refresh_paid == 0, '免费帧禁进付费计数'
    assert gs.effects.refresh_total == 1, '全量计数含免费'


def test_report_unobserved_field_conservative_paid() -> None:
    """未观察(None)→ 保守按付费:计数进 paid,零 Field 扣减行(次数是
    记账面非决策闸);level 同帧缺读 → 随机态腿跳写(概率表按级索引)→
    容器整拍零写。"""
    gs = _fresh_gs()
    seq0 = gs.write_seq
    report_action_refresh_shop_param(gs, CwActionRefreshShopParam(cost=2),
                                     _LSIG)
    assert gs.free_refresh_left.value is None, '未观察 = 不扣减(零 Field 行)'
    assert gs.effects.refresh_paid == 1, '保守按付费计数'
    assert gs.effects.refresh_total == 1
    assert gs.write_seq == seq0, 'level 缺读随机态腿跳写 → 容器零写'


# ============================================================ 两桥发放(写端元数据)


def test_grant_bridges_field_write_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """两桥发放写端元数据(值语义锁 = test_cw_game_state 桥面):burst 桥
    produced_by 带效果名 + evidence effect_burst@frame;节点桥
    produced_by 带在场条目名 + evidence effect_node@frame;None 基 = 0
    起算(开局无免费次数 = 机制真值,发放即首次落值)。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _fresh_gs()
    from sr_od.application.currency_war.kernel.cw_game_state import (
        apply_effect_burst_grant,
        grant_effect_node_refresh_balance,
    )
    apply_effect_burst_grant(gs, STRATEGY_EFFECTS['固定理财'], frame='p1-r2')
    assert gs.free_refresh_left.value == 2, 'None 基 = 0 起算'
    assert captured[-1] == ('free_refresh_left', 2,
                            'EffectLedgerBridge:固定理财',
                            'effect_burst@p1-r2'), 'burst 桥写端元数据'
    gs2 = _fresh_gs()
    gs2.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                  acquired_key=(1, 5))
    gs2.effects.advance_node((1, 6))
    grant_effect_node_refresh_balance(gs2, frame='p1-r6')
    assert gs2.free_refresh_left.value == 2, 'None 基 = 0 起算'
    assert captured[-1] == ('free_refresh_left', 2,
                            'EffectLedgerBridge:双手狸开键盘！',
                            'effect_node@p1-r6'), '节点桥写端元数据'


# ============================================================ 刷新随机态腿(kernel 采样器)


def _seed_for_random_leg() -> GameState:
    """随机态腿场景种子:等级可读(概率表索引)+ 在屏空店(覆盖面在册)。"""
    gs = _fresh_gs()
    gs.observe(gs.level, 1, sig=_OSIG)
    gs.observe(gs.shop, ShopPayload(cards=[ShopSlot(kind='empty')
                                            for _ in range(5)],
                                    refresh_probs={}), sig=_OSIG)
    return gs


def _slot_signature(payload: ShopPayload) -> list:
    return [(s.kind,
             (s.card.name, s.card.cost, s.card.slot, s.card.star)
             if s.card is not None else None)
            for s in payload.cards]


def test_report_random_leg_deterministic() -> None:
    """随机态腿 = kernel 采样器(sample_shop_deal,与 sim deal_shop 同源):
    固定种子两次独立容器采样逐槽一致(确定性);payload 形态 = 定长 5 槽
    content/1★/注册表名 + 基线概率条;写通道 = write_logic_rand 专用通道
    (source=logic_rand + evidence 注记)。"""
    signatures = []
    for _ in range(2):
        gs = _seed_for_random_leg()
        report_action_refresh_shop_param(
            gs, CwActionRefreshShopParam(cost=2), _LSIG,
            rng=random.Random('cw-shop-deal-fixed-seed'))
        payload = gs.shop.value
        assert payload is not None and len(payload.cards) == 5
        assert payload.refresh_probs == {int(k): float(v)
                                         for k, v in REFRESH_PROB[1].items()
                                         if v > 0}, '基线概率条随载荷'
        for slot in payload.cards:
            if slot.card is not None:
                assert slot.card.name in CHARACTERS
                assert slot.card.star == 1, 'U12:直出 2/3 星概率 0'
        assert gs.shop.source == 'logic_rand', '随机态专用通道'
        assert gs.shop.evidence == 'refresh_random_sample'
        signatures.append(_slot_signature(payload))
    assert signatures[0] == signatures[1], '固定种子 → 采样确定性'


def test_report_random_leg_rand_outcome_not_andon(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """write_logic_rand 通道语义:随机态采样被下一入口观察覆盖,差异 =
    预期内——只落 logic_rand_outcome 台账行,不进失配安灯三分流(无
    observe_vs_logic_mismatch 行、安灯钩子不触发、无 [cw!] 告警面)。"""
    from sr_od.application.currency_war.kernel import cw_game_state as _gs_mod
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )

    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    warns: list[tuple] = []
    monkeypatch.setattr(_gs_mod.log, 'warning',
                        lambda *a, **k: warns.append(a))

    gs = _seed_for_random_leg()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-deal-fixed-seed'))
    assert gs.shop.source == 'logic_rand'
    # 下一入口观察覆盖(换一张不同的真值牌面)
    truth = ShopPayload(
        cards=[ShopSlot(kind='content'), ShopSlot(kind='empty'),
               ShopSlot(kind='empty'), ShopSlot(kind='empty'),
               ShopSlot(kind='empty')], refresh_probs={})
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.shop, truth, sig=_OSIG)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    kinds = [r['kind'] for r in rows]
    assert 'logic_rand_outcome' in kinds, '差异落随机结果台账'
    assert 'observe_vs_logic_mismatch' not in kinds, '不进失配三分流'
    assert fired == [], '安灯不触发(随机落地非 bug)'
    assert not any('观察覆盖 logic 失配' in str(w) for w in warns), \
        '无 [cw!] 告警面'
    assert gs.shop.source == 'observation', '观察赢覆盖照常'
