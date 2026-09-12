"""ADR-0282(hp 三层:对账/决策/记录)+ ADR-0283(sim bench 超容守卫)锁测试。

hp 三层(用户设计 2026-08-23,run165501 hp=100 毒化案根治):
① shop 开态帧读不到 → 不写遥测兜底 100(hp_readable=False,hp=沿用值);
② 决策沿用 session.last_hp_real(真值,比假 100 安全);
③ 同域跳变(HP 只降不升,大幅上行)→ obs_conflict 留证;
④ 开局全无真值 → None 诚实未知(旧「兜底 100」由 ADR-0491 废止,W823 hp None 化);
⑤ sim BuyCard 前置容量守卫:bench 满(≥BENCH_CAPACITY)买跳过 + 计数披露。
"""
from __future__ import annotations


def _mk_session():
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )
    return StrategySession()


# ===== 件1/件2:对账层保旧 + 决策沿用真值 =====

def test_hp_unreadable_keeps_last_real() -> None:
    """①② 读不到(shop 开态血量区空)→ 沿用 last_hp_real,不是兜底 100。"""
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = _mk_session()
    s.last_hp_real = 40
    hp, readable = reconcile_hp(s, None)
    assert (hp, readable) == (40, False)   # 沿用真值 + readable=False 披露
    assert s.last_hp_real == 40             # 保旧不写(读失败非漂移)


def test_hp_truth_frame_updates_session() -> None:
    """真值帧(关态可读)写回 last_hp_real(=「session 更新只在关态真值帧」)。"""
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = _mk_session()
    s.last_hp_real = 50
    hp, readable = reconcile_hp(s, 35)      # 正常下行(掉血)
    assert (hp, readable) == (35, True)
    assert s.last_hp_real == 35


def test_hp_jump_up_leaves_evidence(monkeypatch) -> None:
    """③ 新读非 None 且大幅上行(HP 只降不升)→ obs_conflict 留证(仍采新)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    s.last_hp_real = 20
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict',
                        lambda *a, **k: calls.append((a, k)))
    hp, readable = cw_reconcile.reconcile_hp(s, 90)   # +70 ≥ 阈值 30
    assert (hp, readable) == (90, True)     # 真值帧仍采新
    assert len(calls) == 1 and calls[0][0][0] == 'hp'
    # 小幅下行/常规变化不触发
    s.last_hp_real = 60
    calls.clear()
    cw_reconcile.reconcile_hp(s, 55)
    assert calls == []


def test_hp_no_truth_honest_none() -> None:
    """④ 开局全无真值(last_hp_real=None)读不到 → None(诚实未知)。

    旧锁「兜底 100」已随 ADR-0491 废止(ADR-0282 ④ 被正式取代:
    r1 开局血量随难度/词缀变不恒 100,兜底值是假值;W823 hp None 化)。
    """
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = _mk_session()
    assert s.last_hp_real is None
    hp, readable = reconcile_hp(s, None)
    assert (hp, readable) == (None, False)


def test_hp_offline_no_session_passthrough() -> None:
    """无 session(离线/测试):真值透传;读不到=诚实 None(不炸,不兜底)。"""
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    assert reconcile_hp(None, 70) == (70, True)
    assert reconcile_hp(None, None) == (None, False)


# ===== 件3:记录层接线(写入端走 read_hp_opt + reconcile_hp) =====

def _wired_read_env(monkeypatch, tmp_path, hp_opt):
    """read_game_state 真链最小桩面(reader 全桩,只留 hp 现读可变)。

    手法镜像 test_cw_arbitration._stub_read_game_state(reader 桩按模块属性
    打);删除波 1:冲突证据行归宿 = journal obs_event,本 helper 辖 hp 读链
    (留证行非断言面,无需装账本——obs_conflict 无账本时零产出、不写真实
    .debug/)。返回 (obs 模块, session, ctx)。
    """
    from types import SimpleNamespace

    import sr_od.application.currency_war.kernel.cw_observe as core_obs
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(core_obs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(obs, 'is_prep_like_frame', lambda c, s: True)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda c, s, level=None, expected=None: ({}, True))
    monkeypatch.setattr(obs, 'board_from_tracked', lambda tracked: None)
    monkeypatch.setattr(obs, 'ledger_node_type',
                        lambda session, plane, round_num: None)
    monkeypatch.setattr(obs, 'resolve_paddle_pair',
                        lambda c, s, level: (None, None))
    monkeypatch.setattr(obs, 'read_hp_opt', hp_opt)   # 被测面:直接挂可调用桩
    for _n, _v in {
        'read_gold_settled': 55, 'read_phase_round': (2, 3), 'read_node_type': None,
        'read_xp_progress': (0, 6), 'read_level_raw_opt': 5, 'read_level_up_cost': 4,
        'read_enemy_difficulty': None, 'read_streak': None,
        'read_shop_cards': [], 'read_refresh_probs': None, 'read_bench_full': None,
    }.items():
        monkeypatch.setattr(obs, _n,
                            (lambda _v: lambda *a, _v=_v, **kw: _v)(_v))
    session = SimpleNamespace(
        active_strategies=[], last_level_obs=0, last_hp_real=40,
        last_hp_real_node=None, last_streak=0,
        briefing_bosses=None, briefing_affixes=None, active_env='',
        chosen_megastar=None, chosen_partner=None, enemy_difficulty=None)
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    return obs, session, ctx


def test_read_game_state_hp_wired_through_reconcile(monkeypatch, tmp_path) -> None:
    """read_game_state 的 hp 段经 reconcile_hp 对账(ADR-0282 三层接线)。

    行为锁(替代原 inspect.getsource 在场锁,纪律 8:肯定性在场锁同族=禁):
    ①读不到帧(shop 开态 read_hp_opt→None)→ 沿用 session.last_hp_real=40、
      readable=False、保旧不写——对账层脱落时该帧 state.hp 直落 None,红;
    ②真值帧(现读 35)→ 采新 (35, True) 并写回 session(真值帧锚推进
      node_t=(plane-1)*9+round=12)——写回脱落时 session 滞留旧值,红。
    """
    from sr_od.application.currency_war.obs.cw_observation import PHASE_PREP_CLEAN
    obs, session, ctx = _wired_read_env(monkeypatch, tmp_path,
                                        lambda *a, **kw: None)
    state = obs.read_game_state(ctx, None, phase=PHASE_PREP_CLEAN)
    assert (state.hp, state.hp_readable) == (40, False)   # 沿用真值,非兜底/None
    assert session.last_hp_real == 40                      # 保旧不写
    assert session.last_hp_real_node is None               # 沿用帧不推节点锚

    obs, session, ctx = _wired_read_env(monkeypatch, tmp_path,
                                        lambda *a, **kw: 35)
    state = obs.read_game_state(ctx, None, phase=PHASE_PREP_CLEAN)
    assert (state.hp, state.hp_readable) == (35, True)     # 真值帧采新
    assert (session.last_hp_real, session.last_hp_real_node) == (35, 12)


# ===== 件4:hp_trusted 可信位语义(ADR-0428)=====
# 语义锁:沿用真值帧=trusted True;100 兜底帧=trusted False。写入端唯一
# =read_game_state(实现形状断言已按源码锁瘦身删除;派生逻辑的正确性由
# 行为锁 test_hp_trusted_default_false 及后续行为覆盖守住)。

def test_hp_trusted_default_false() -> None:
    """CwWorkFrame 默认 False(未知帧按不可信,保守);直接构造的帧不带
    trusted=True——消费方守卫须显式依赖写入端赋值,不吃默认幸运值。"""
    from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame
    assert CwWorkFrame().hp_trusted is False


# ===== 件5:075840 hp 真值链形态锁(T-109③ 定谳,ADR-0605) =====

def test_hp_down_cross_node_no_facts_accepts_075840_shape(monkeypatch) -> None:
    """075840 08:35:31 实证帧锁(素材:obs_conflicts 行 + 冲突帧截图
    .debug/temp/currency_war/shots/obs_conflict_hp__32006c4d.png 视觉实证:
    备战帧 HP HUD 真值 = 1)。

    形态:跨节点下行 17→1(p2r1 结算 17 为上一真值,节点锚 10;本帧节点
    13),窗内无任何已观测战斗行(P2R2 结算行未入 performance.history 的
    观察缺口形态)→「战斗事实缺观测」臂:采新 + 留证,读数链采信 1。

    锁的存在性纪律判语:复盘候选「hp 帧读漏补给回血(final_hp=1 陈旧读数,
    实际 17)」被冲突帧视觉证据反证——1 是真值,17 是补给合成行的陈旧
    last_state 快照(ADR-0577 §3.3 同型鬼值,conf 降权守卫落地前的旧码行)。
    本锁钉住读数链对该形态的采信方向,防后续下行守卫修订无意识翻转真值;
    若将来修订「窗内事实查找覆盖面」(改走胜战臂),须先对照本帧重推——
    该帧真值经视觉裁决,不是守卫臂选择的函数。
    """
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    s.last_hp_real = 17
    s.last_hp_real_node = 10
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict',
                        lambda *a, **k: calls.append((a, k)))
    hp, readable = cw_reconcile.reconcile_hp(
        s, 1, source='read_game_state', node_t=13)
    assert (hp, readable) == (1, True)              # 真值帧采新(视觉实证 1 为真)
    assert (s.last_hp_real, s.last_hp_real_node) == (1, 13)
    assert s.hp_suspect is None                      # 采新即出窗,无复现候选
    assert len(calls) == 1 and calls[0][0][0] == 'hp'
    assert '战斗事实缺观测' in calls[0][1]['verdict']   # 观察缺口臂留证(非拒信)
