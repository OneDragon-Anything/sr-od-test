"""check_env_interest_grants 利息累计条件发放测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同模块兄弟触发函数测试 =
kernel/test_env_grants.py〔超限只读复用〕与本目录按被测方法拆分文件,
本文件按拆目录规范落位)。

测试面依据 = 迭代 T-27 公司契约利息累计触发设计(v2.3 定稿)§2.3 + §4.3:
- **条件矩阵**(六序短路):env 空链/未登记/已 done(一次性封账)/
  计数不足/bench 未观察(缓发不标 done,宁缺勿造)/达标发放;
- **两写契约**:角色链(gain_character rand=False 确定发放,1★ 先验)
  + done interest_threshold 键同 evidence 同 sig 同 produced_by 相邻;
- **一次性**:发放后同条件重查零写(不重发);
- **快照恢复**:done 随快照往返无损,恢复局重查不重发(计数不入快照,
  恢复局不满足阈 → 重建累计后再触发 = 家族「最佳猜测」边界,此边界
  语义归披露,不在本文件断言)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_env_grants import (
    INTEREST_THRESHOLD_KEY,
    check_env_interest_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    restore_state_snapshot,
)

_ENV = '公司契约'
_CHAR = '托帕&账账'
_THRESHOLD = 40

_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenBattleWait',
                       group_id='battle-wait:env-grant')
_SIG_SIM = ChannelSig(family='logic_action', actor='SimBackend',
                      mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_SEED = ChannelSig(family='logic_action', actor='test-seed',
                       mode='compute')

_EVIDENCE = f'env_grant#{_ENV}#interest{_THRESHOLD}'


def _make_gs(*, env: str | None = _ENV,
             bench: list[tuple[str, int]] | None = None,
             interest_earned: int = 0,
             done: tuple[tuple[str, str], ...] | None = None
             ) -> GameState:
    """观察面按参组装(None = 保持未写形态;计数/登记域经唯一入口函数/logic
    直写播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if bench is not None:
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
        for i, (c, s) in enumerate(bench):
            slots[i] = BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if interest_earned:
        gs.effects.record_interest_earned(interest_earned)
    if done is not None:
        gs.write_logic(gs.env_grants_done, tuple(done),
                       produced_by='test-seed', sig=_SIG_SEED)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(先例 = kernel/test_env_grants.py 同名
    helper,扩 produced_by 列)。"""
    calls: list[tuple[str, str | None, str, ChannelSig, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel, sig,
                          produced_by))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


# ============================================================ 条件矩阵


def test_condition_matrix_short_circuits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """未发放分支逐序零写(T-27 设计 §2.3 条件矩阵 1-4):env 空链/
    未登记/已 done/计数不足 → 返回 None 且容器零写行(计数不足分支
    放在 done 之后断言,与设计短路序一致)。"""
    # ① env 未激活(None/空链)
    gs = _make_gs(env=None, bench=[], interest_earned=_THRESHOLD)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_interest_grants(gs, _SIG_HOOK) is None
    assert not calls, f'env 空链零写: {calls}'
    # ② 未登记(表外环境)
    gs = _make_gs(env='轮岗', bench=[], interest_earned=_THRESHOLD)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_interest_grants(gs, _SIG_HOOK) is None
    assert not calls, f'表外环境零写: {calls}'
    # ③ 已 done(一次性封账)
    gs = _make_gs(bench=[], interest_earned=_THRESHOLD,
                  done=((_ENV, INTEREST_THRESHOLD_KEY),))
    calls = _record_writes(gs, monkeypatch)
    assert check_env_interest_grants(gs, _SIG_HOOK) is None
    assert not calls, f'已 done 零写: {calls}'
    # ④ 计数不足
    gs = _make_gs(bench=[], interest_earned=_THRESHOLD - 1)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_interest_grants(gs, _SIG_HOOK) is None
    assert not calls, f'计数不足零写: {calls}'


def test_bench_unobserved_defer_without_done(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """bench 未观察(直构域防御分支,设计 §2.3 条件 5)→ None 且不标
    done(宁缺勿造:done 只在发放同窗登记;计数保留,下个收入刻自动
    重查)。"""
    gs = _make_gs(env=_ENV, bench=None, interest_earned=_THRESHOLD)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_interest_grants(gs, _SIG_HOOK) is None
    assert not calls, f'bench 未观察零写: {calls}'
    assert gs.env_grants_done.value is None, '不标 done'


def test_grant_two_adjacent_writes_same_contract(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """达标发放(T-27 设计 §2.3 条件 6):bench 增 1 个 1★ 托帕&账账
    + done 追加 ('公司契约','interest_threshold'),两笔写同 evidence
    ``env_grant#公司契约#interest40`` 同 sig 同 produced_by 相邻
    (同窗原子语义面);角色链经 gain_character 确定发放(rand=False
    形态 = 链内写通道由 gs 采样模式决定,世界无随机采样)。"""
    gs = _make_gs(bench=[], interest_earned=_THRESHOLD)
    calls = _record_writes(gs, monkeypatch)
    granted = check_env_interest_grants(gs, _SIG_HOOK)
    assert granted == _CHAR, '返回发放角色名(日志面消费)'
    assert _bench_units(gs) == [(_CHAR, 1)], '1★ 先验入席'
    assert gs.env_grants_done.value == ((_ENV, INTEREST_THRESHOLD_KEY),)
    # 两笔写契约:done evidence = 基串;bench 链写 = 基串 + '#place'
    # (gain-chain.md §2 链内后缀约定,streak/refresh 通道同款);两笔同
    # sig(logic_hook 族),produced_by 同为 _PRODUCER 写者归组
    assert [c[0] for c in calls] == ['bench', 'env_grants_done'], \
        f'两笔相邻写: {calls}'
    assert calls[0][1] == _EVIDENCE + '#place', '链写 evidence(基串+#place)'
    assert calls[1][1] == _EVIDENCE, 'done evidence(基串)'
    assert calls[0][3] == calls[1][3] == _SIG_HOOK, '同 sig'
    assert calls[0][4] == calls[1][4] == 'env_conditional_grant', \
        '同 produced_by(_PRODUCER 写者归组)'


def test_once_only_no_regrant(monkeypatch: pytest.MonkeyPatch) -> None:
    """一次性语义(T-27 设计 §6 披露 5):发放后计数继续增长再查 = done
    短路零写(不重发;「累计获得40利息后获得」读作一次性)。"""
    gs = _make_gs(bench=[], interest_earned=_THRESHOLD)
    check_env_interest_grants(gs, _SIG_HOOK)
    assert _bench_units(gs) == [(_CHAR, 1)]
    calls = _record_writes(gs, monkeypatch)
    gs.effects.record_interest_earned(10)
    assert check_env_interest_grants(gs, _SIG_SIM) is None
    assert not calls, f'再查零写: {calls}'


def test_snapshot_roundtrip_done_persists(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """快照恢复不重发(T-27 设计 §2.5 恢复语义两面性前半):发放完成态
    快照 → 恢复局 done 往返无损,重查零写。"""
    gs = _make_gs(bench=[], interest_earned=_THRESHOLD)
    assert check_env_interest_grants(gs, _SIG_HOOK) == _CHAR
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    assert restored.env_grants_done.value == \
        ((_ENV, INTEREST_THRESHOLD_KEY),), 'done 值往返无损'
    assert restored.effects.interest_earned == 0, \
        '计数不入快照(接管局归零边界,披露 3)'
    calls = _record_writes(restored, monkeypatch)
    restored.effects.record_interest_earned(_THRESHOLD)
    assert check_env_interest_grants(restored, _SIG_HOOK) is None
    assert not calls, f'恢复局 done 已登记零写: {calls}'
