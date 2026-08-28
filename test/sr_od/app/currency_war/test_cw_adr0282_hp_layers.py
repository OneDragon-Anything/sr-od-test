"""ADR-0282(hp 三层:对账/决策/记录)+ ADR-0283(sim bench 超容守卫)锁测试。

hp 三层(用户设计 2026-08-23,run165501 hp=100 毒化案根治):
① shop 开态帧读不到 → 不写遥测兜底 100(hp_readable=False,hp=沿用值);
② 决策沿用 session.last_hp_real(真值,比假 100 安全);
③ 同域跳变(HP 只降不升,大幅上行)→ obs_conflict 留证;
④ 开局全无真值 → 兜底 100;
⑤ sim BuyCard 前置容量守卫:bench 满(≥BENCH_CAPACITY)买跳过 + 计数披露。
"""
from __future__ import annotations


def _mk_session():
    from sr_od.application.currency_war.cw_strategy import StrategySession
    return StrategySession()


# ===== 件1/件2:对账层保旧 + 决策沿用真值 =====

def test_hp_unreadable_keeps_last_real() -> None:
    """①② 读不到(shop 开态血量区空)→ 沿用 last_hp_real,不是兜底 100。"""
    from sr_od.application.currency_war.cw_reconcile import reconcile_hp
    s = _mk_session()
    s.last_hp_real = 40
    hp, readable = reconcile_hp(s, None)
    assert (hp, readable) == (40, False)   # 沿用真值 + readable=False 披露
    assert s.last_hp_real == 40             # 保旧不写(读失败非漂移)


def test_hp_truth_frame_updates_session() -> None:
    """真值帧(关态可读)写回 last_hp_real(=「session 更新只在关态真值帧」)。"""
    from sr_od.application.currency_war.cw_reconcile import reconcile_hp
    s = _mk_session()
    s.last_hp_real = 50
    hp, readable = reconcile_hp(s, 35)      # 正常下行(掉血)
    assert (hp, readable) == (35, True)
    assert s.last_hp_real == 35


def test_hp_jump_up_leaves_evidence(monkeypatch) -> None:
    """③ 新读非 None 且大幅上行(HP 只降不升)→ obs_conflict 留证(仍采新)。"""
    from sr_od.application.currency_war import cw_reconcile
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


def test_hp_no_truth_fallback_100() -> None:
    """④ 开局全无真值(last_hp_real=None)读不到 → 兜底 100(健康先验)。"""
    from sr_od.application.currency_war.cw_reconcile import reconcile_hp
    s = _mk_session()
    assert s.last_hp_real is None
    hp, readable = reconcile_hp(s, None)
    assert (hp, readable) == (100, False)


def test_hp_offline_no_session_passthrough() -> None:
    """无 session(离线/测试):真值透传;读不到走开局兜底(不炸)。"""
    from sr_od.application.currency_war.cw_reconcile import reconcile_hp
    assert reconcile_hp(None, 70) == (70, True)
    assert reconcile_hp(None, None) == (100, False)


# ===== 件3:记录层接线(写入端走 read_hp_opt + reconcile_hp) =====

def test_read_game_state_hp_wired_through_reconcile() -> None:
    """read_game_state 的 hp 走 reconcile_hp(ADR-0282 接线;源级锁)。"""
    import inspect

    from sr_od.application.currency_war import cw_observation as obs
    src = inspect.getsource(obs.read_game_state)
    assert 'reconcile_hp' in src
    assert 'read_hp_opt' in src


# ===== 件4:hp_trusted 可信位语义(ADR-0428)=====
# 语义锁:沿用真值帧=trusted True;100 兜底帧=trusted False。写入端唯一
# =read_game_state,按「现读非 None ∨ 对账前已有真值」派生——源级锁
# 钉住派生式与写入点,防第二写入端把两语义再混回一位。

def test_hp_trusted_source_level_derivation() -> None:
    """写入端源级锁:read_game_state 里按「真读过守卫 ∨ 同节点沿用」派生
    hp_trusted(ADR-0428 语义 + ADR-0430 帧龄门收紧的唯一接线处)。"""
    import inspect

    from sr_od.application.currency_war import cw_observation as obs
    src = inspect.getsource(obs.read_game_state)
    assert 'hp_trusted' in src
    # 帧龄门:真读且过守卫,或同节点内沿用(last_hp_real_node==当前节点号)
    assert "state.hp_trusted = (state.hp_readable and _hp_opt is not None) \\\n        or _same_node_stale" in src
    assert "getattr(_sess_hp, 'last_hp_real_node', None) == _node_t" in src
    # 派生原料必须是「对账前的 last_hp_real 是否存在」,不是 readable 位
    assert "_had_real = getattr(_sess_hp, 'last_hp_real', None) is not None" in src
    # ADR-0430:reconcile_hp 接收 node_t(下行守卫帧间事实窗锚)
    assert "node_t=_node_t" in src


def test_hp_trusted_default_false() -> None:
    """GameState 默认 False(未知帧按不可信,保守);直接构造的帧不带
    trusted=True——消费方守卫须显式依赖写入端赋值,不吃默认幸运值。"""
    from sr_od.application.currency_war.cw_state import GameState
    assert GameState().hp_trusted is False


def test_telemetry_records_gold_readable() -> None:
    """gold「不可信」日志升级为字段:DecisionTrace 带 gold_readable 并写入。"""
    import inspect

    from sr_od.application.currency_war import cw_telemetry as tel
    assert 'gold_readable' in inspect.getsource(tel.DecisionTrace)
