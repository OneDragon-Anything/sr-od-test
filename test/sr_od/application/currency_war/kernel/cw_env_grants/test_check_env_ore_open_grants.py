"""check_env_ore_open_grants 晶矿开启计数触发发放检查测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同模块兄弟触发函数测试住本目录
按被测方法拆分文件,先例 = 同目录 test_check_env_interest_grants.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-29-zhanjidian-qiyue.md(定稿 v2.1)§2.3 + §4:
- **条件矩阵**:env 空链/不在册 → 零写;bench 未观察 → 缓发不标 done
  (宁缺勿造);未达标 → 零写;达标 → bench 增火花(1★)+ 随机分支 1 名;
- **两条分支随机态**:两条分支 gain_character 一律 rand=True(通道定级硬语义,
  用户裁定 2026-10-17:触发前提 = 晶矿开启计数为未验证推演,发放按
  随机态定级走台账纠偏+观察覆盖)→ bench 写通道均随机态;rng 消耗仅
  随机分支一笔,具名分支零消耗(采样解析恰一次);
- **done 封账**:``ore_open#<阈值>`` write_logic 簿记(非随机态面),
  同 evidence 同 sig;
- **阈值序列**:首阈值 20 达标发一次 / 已封账段推进零发 / 30 达标再发 /
  断档续发(done 缺档按计数现值补发)/ 单批跨多阈值 loop 逐阈值发放
  (直构计数器形态);
- **rng 双端**:未装配 provider → 回退自掷仍产出;装 provider 后同动作
  序列两次重放随机分支结果一致;解析口显式传入优先于注入槽;
- **池空守卫**(不可达防御语义钉死):注册表/校验重构若把守卫无声删改,
  本锁红灯——池空 = 零发放零 done,恢复后同计数下批正常发放。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest

from sr_od.application.currency_war.kernel import cw_env_grants
from sr_od.application.currency_war.kernel.cw_action_report import (
    action_sampling_rng,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_env_grants import (
    ORE_OPEN_GRANT_RNG_TOOL,
    ORE_OPEN_THRESHOLD_KEY_PREFIX,
    check_env_ore_open_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_investments import RandomCharSpec
from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool

_ENV = '战技点契约'
_NAMED = '火花'
_FACTION = '战技点'
_FIRST, _STEP = 20, 10

# 生产池镜像(战技点契约开箱窗 = 空解锁态直构):grant_char_pool = 规格域
# ∩ 当时牌库(未解锁专家剔除,用户裁定 2026-10-28)——与 check_env_ore_
# open_grants 采样源同源,种子钉名/成员断言共用本镜像。
_POOL = grant_char_pool(
    GameState(schema_version=GAME_STATE_SCHEMA_VERSION),
    RandomCharSpec(faction=_FACTION, star=1))

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep',
                  group_id='act:CwScreenPrep@1')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SEED = 20261016


@pytest.fixture
def seeded_provider() -> Iterator[None]:
    """注确定 rng 提供槽(固定种子,期望名可现算钉名),必达复位。"""
    set_action_rng_provider(lambda tool: random.Random(_SEED))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def _expected_random_name() -> str:
    """随机分支期望名现算(provider 固定种子 ⟹ 单笔掷名结果确定;
    注册表现算对照,非手抄)。"""
    return random.Random(_SEED).choice(list(_POOL))


def _make_gs(*, env: str | None = _ENV,
             bench: list[tuple[str, int]] | None = None,
             ore_open_total: int = 0,
             done: tuple[tuple[str, str], ...] | None = None) -> GameState:
    """观察面按参组装(bench None = 保持未观察形态;计数/登记域经单口
    /logic 直写播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if bench is not None:
        slots: list[BenchSlot | None] = [
            BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
            for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if ore_open_total:
        gs.effects.record_ore_open(ore_open_total)
    if done is not None:
        gs.write_logic(gs.env_grants_done, tuple(done),
                       produced_by='test-seed', sig=_SIG)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(先例 = 同目录 test_check_env_interest_grants
    .py 同名 helper)。"""
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
    """未发放分支逐序零写(设计 §2.3 条件矩阵 1/2/4):env 空链/不在册/
    计数未达标 → 返回空效果串且容器零写行。"""
    cases = [
        ('env 未激活(None 形态)', _make_gs(env=None, bench=[], ore_open_total=20)),
        ('env 空链形态', _make_gs(env='', bench=[], ore_open_total=20)),
        ('env 不在册', _make_gs(env='蓝海', bench=[], ore_open_total=20)),
        ('计数未达标(19)', _make_gs(bench=[], ore_open_total=_FIRST - 1)),
    ]
    for label, gs in cases:
        calls = _record_writes(gs, monkeypatch)
        assert check_env_ore_open_grants(gs, _SIG) == (), label
        assert not calls, f'{label} 零写: {calls}'


def test_bench_unobserved_defer_without_done(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """bench 未观察(设计 §2.3 条件 3)→ 返回空且不标 done(宁缺勿造:
    done 只在发放同窗登记;计数保留,下个开矿窗自动重查)。"""
    gs = _make_gs(bench=None, ore_open_total=_FIRST)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_ore_open_grants(gs, _SIG) == ()
    assert not calls, f'bench 未观察零写: {calls}'
    assert gs.env_grants_done.value is None, '不标 done'


def test_grant_two_legs_rand_channel_and_done(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """达标发放(设计 §2.3 条件 7):bench 增火花(1★,具名分支)+ 随机分支
    1 名(1★),done 追加 ``ore_open#20``。两条分支 bench 写通道均随机态
    (rand=True 通道定级硬语义)且同 evidence 同 sig 同 produced_by
    相邻;done = write_logic 簿记(非随机态面);随机分支名 ∈ 战技点池
    (注册表现算对照)。"""
    expected = _expected_random_name()
    gs = _make_gs(bench=[], ore_open_total=_FIRST)
    calls = _record_writes(gs, monkeypatch)
    granted = check_env_ore_open_grants(gs, _SIG)
    assert granted == (_NAMED, expected), \
        f'具名分支先、随机分支后: {granted}'
    assert _bench_units(gs) == [(_NAMED, 1), (expected, 1)], '两条分支 1★ 入席'
    assert gs.env_grants_done.value == \
        ((_ENV, f'{ORE_OPEN_THRESHOLD_KEY_PREFIX}{_FIRST}'),), 'done 封账'
    assert [c[0] for c in calls] == ['bench', 'bench', 'env_grants_done'], \
        f'两条分支链写 + done 相邻: {calls}'
    assert calls[0][2] == calls[1][2] == 'rand', \
        '两条分支 bench 写通道均随机态(rand=True 硬语义)'
    assert calls[2][2] == 'logic', 'done 封账 = write_logic 簿记'
    evidence = f'env_grant#{_ENV}#ore_open{_FIRST}'
    assert calls[0][1] == evidence + '#place', '具名分支链写 evidence'
    assert calls[1][1] == evidence + '#place', '随机分支链写 evidence(同基串)'
    assert calls[2][1] == evidence, 'done evidence = 基串'
    assert calls[0][3] == calls[1][3] == calls[2][3] == _SIG, '同 sig'
    assert calls[0][4] == calls[1][4] == calls[2][4] == \
        'env_conditional_grant', '同 produced_by'
    assert expected in _POOL, '随机分支名 ∈ chars_by_faction(战技点)'


def test_named_leg_consumes_no_rng(seeded_provider) -> None:
    """rng 消耗面(设计 §2.3 rng 语义):达标发放全程采样解析恰一次
    (随机分支掷名一笔)——具名分支名字确定零 rng 消耗;若具名分支也走采样,
    解析次数会翻倍红灯。"""
    calls = {'n': 0}

    def counting_provider(tool: str) -> random.Random:
        calls['n'] += 1
        return random.Random(_SEED)

    set_action_rng_provider(counting_provider)
    try:
        gs = _make_gs(bench=[], ore_open_total=_FIRST)
        granted = check_env_ore_open_grants(gs, _SIG)
        assert granted == (_NAMED, _expected_random_name()), \
            f'发放照常: {granted}'
        assert calls['n'] == 1, \
            f'采样解析恰一次(具名分支零消耗): {calls["n"]}'
    finally:
        set_action_rng_provider(None)


# ============================================================ 阈值序列

def test_threshold_sequence_reach_gap_and_multi(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """阈值序列(设计 §2.3 条件 4 + §4 锁 4):20 达标发一次;封账后
    21-29 计数推进零发(无新阈值达标);30 达标再发(ore_open#30);
    done 已含 20 缺 30、计数 31 → 只发 30 档(断档续发);单批跨多阈值
    (直构计数器一笔 39,20/30 达标、40 未达)loop 逐阈值发放。
    局部种子 4(两掷均非火花且互异,池 = 过滤后镜像 _POOL)——随机分支抽中
    火花会与具名分支叠加触发 3合1 连锁(裁决点 2 合法形态,归链域既有锁),
    本锁只验 loop 逐阈值发放形状,种子避开合并形态保持写行数确定。"""
    set_action_rng_provider(lambda tool: random.Random(4))
    try:
        seq_rng = random.Random(4)
        rand_throw1 = seq_rng.choice(list(_POOL))
        rand_throw2 = seq_rng.choice(list(_POOL))
        assert rand_throw1 != _NAMED and rand_throw2 != _NAMED \
            and rand_throw1 != rand_throw2, '种子前提:两掷非火花且互异'
        key = ORE_OPEN_THRESHOLD_KEY_PREFIX
        # 20 达标发一次
        gs = _make_gs(bench=[], ore_open_total=_FIRST)
        granted = check_env_ore_open_grants(gs, _SIG)
        assert granted == (_NAMED, rand_throw1)
        assert gs.env_grants_done.value == ((_ENV, f'{key}{_FIRST}'),)
        # 21-29 推进零发(封账段跳过,无新阈值)
        calls = _record_writes(gs, monkeypatch)
        gs.effects.record_ore_open(9)   # 20 → 29
        assert check_env_ore_open_grants(gs, _SIG) == ()
        assert not calls, f'封账段零写: {calls}'
        # 30 达标再发(跨 check 调用各解析新实例同种子,每窗第一掷同值)
        gs.effects.record_ore_open(1)   # 29 → 30
        granted30 = check_env_ore_open_grants(gs, _SIG)
        assert granted30 == (_NAMED, rand_throw1), '每阈值重复发放'
        assert gs.env_grants_done.value == \
            ((_ENV, f'{key}{_FIRST}'), (_ENV, f'{key}{_FIRST + _STEP}'),)
        # 断档续发:done 含 20 缺 30、计数 31 → 只发 30 档
        gs_gap = _make_gs(bench=[], ore_open_total=31,
                          done=((_ENV, f'{key}{_FIRST}'),))
        calls_gap = _record_writes(gs_gap, monkeypatch)
        assert check_env_ore_open_grants(gs_gap, _SIG) == \
            (_NAMED, rand_throw1), '只补发缺档阈值'
        assert gs_gap.env_grants_done.value == \
            ((_ENV, f'{key}{_FIRST}'), (_ENV, f'{key}{_FIRST + _STEP}'),)
        assert [c[1] for c in calls_gap].count(
            f'env_grant#{_ENV}#ore_open{_FIRST + _STEP}#place') == 2, \
            '两条分支 evidence 均挂 30 档(不发已封账的 20 档)'
        # 单批跨多阈值:两档逐阈值发放(单窗内 roll_rng 解析一次后
        # loop 复用,两档随机分支 = 同一 rng 实例顺序两掷,期望按序现算)
        gs_multi = _make_gs(bench=[], ore_open_total=2 * _FIRST - 1)
        calls_multi = _record_writes(gs_multi, monkeypatch)
        granted_multi = check_env_ore_open_grants(gs_multi, _SIG)
        assert granted_multi == (_NAMED, rand_throw1,
                                 _NAMED, rand_throw2), \
            'loop 逐阈值各发整组'
        assert gs_multi.env_grants_done.value == \
            ((_ENV, f'{key}{_FIRST}'), (_ENV, f'{key}{_FIRST + _STEP}'),)
        assert len(calls_multi) == 6, \
            f'两档 × (两条分支 + done): {len(calls_multi)}'
    finally:
        set_action_rng_provider(None)


# ============================================================ rng 双端

def test_rng_fallback_without_provider() -> None:
    """回退自掷(设计 §2.3 rng 语义):未装配 provider(= live 缺省)
    → 回退自掷仍产出,随机分支名 ∈ 池(采样是猜测口径,不因缺装配而
    零发放)。"""
    set_action_rng_provider(None)
    gs = _make_gs(bench=[], ore_open_total=_FIRST)
    granted = check_env_ore_open_grants(gs, _SIG)
    assert len(granted) == 2 and granted[0] == _NAMED, f'自掷仍发放: {granted}'
    assert granted[1] in _POOL, '自掷名 ∈ 池'


def test_rng_provider_deterministic_replay(seeded_provider) -> None:
    """注入槽确定性(设计 §2.5):装 provider 后同动作序列两次重放
    (各自全新 gs)随机分支结果一致——sim 世界真值 + 动作序列确定性
    ⟹ 采样链确定性。"""
    results = []
    for _ in range(2):
        gs = _make_gs(bench=[], ore_open_total=_FIRST)
        results.append(check_env_ore_open_grants(gs, _SIG))
    expected = (_NAMED, _expected_random_name())
    assert results[0] == expected and results[1] == expected, \
        f'两次重放同序: {results}'


def test_resolver_explicit_rng_beats_provider(seeded_provider) -> None:
    """解析口显式优先(action_sampling_rng 解析序「显式传入 > 注入槽」
    在本工具键解析点钉住):装 provider 下显式 rng 在场则原样返回该
    实例(provider 不触)。"""
    explicit = random.Random(7)
    assert action_sampling_rng(ORE_OPEN_GRANT_RNG_TOOL, explicit) \
        is explicit, '显式传入优先于注入槽'


# ============================================================ 池空守卫

def test_empty_pool_guard_blocks_then_recovers(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """池空守卫(设计 §2.3 条件 6,不可达防御语义钉死):注册表漂移态
    (monkeypatch 直构池空,patch 目标 = 生产端池派生单一源
    ``cw_env_grants.grant_char_pool``——晶矿随机分支池与随机赠卡家族同源
    取池)→ 达标阈值零发放、done 零追加(整体缓发,禁「具名分支已发、
    done 未封」半发放态);恢复后同计数下批正常发放——防未来注册表/校验
    重构把守卫无声删改时无红灯。"""
    monkeypatch.setattr(cw_env_grants, 'grant_char_pool', lambda gs, spec: [])
    gs = _make_gs(bench=[], ore_open_total=_FIRST)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_ore_open_grants(gs, _SIG) == (), '池空整体缓发'
    assert not calls, f'池空零写: {calls}'
    assert gs.env_grants_done.value is None, 'done 零追加'
    monkeypatch.undo()   # 恢复注册表现值:同计数下批正常发放
    calls_ok = _record_writes(gs, monkeypatch)
    granted = check_env_ore_open_grants(gs, _SIG)
    assert granted == (_NAMED, _expected_random_name()), '恢复后照常发放'
    assert gs.env_grants_done.value == \
        ((_ENV, f'{ORE_OPEN_THRESHOLD_KEY_PREFIX}{_FIRST}'),)
    assert calls_ok, '恢复后有写行'
