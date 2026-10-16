"""check_env_merge_grants 合并升星触发发放检查测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同文件兄弟触发函数测试 =
kernel/test_env_grants.py,本文件按被测方法拆目录规范落位,先例 =
同目录 test_check_env_boss_grants.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-26-liangzi-tongpin-qiyue.md(定稿)§2.2 + §4.4/§4.5:
- **条件矩阵**:env 未激活(None/空链)/不在册/facts 无触发角色 → 零写
  零效果串;bench 未观察 → 效果串照返、容器零写(链拒落语义,不炸);
  席满 + 溢出位空 → 溢出落位;席满 + 溢出位占 → 零写 +
  DEFECT_OVERFLOW_TAKEN 留证;
- **rng 双端**:注入槽确定性(装 provider 同动作序列两次重放结果一致)/
  回退自掷(未装配仍产出 = live 猜测口径)/ 解析口显式优先
  (action_sampling_rng 解析序,在本工具键解析点钉住)。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    action_sampling_rng,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_env_grants import (
    ENV_MERGE_GRANT_RNG_TOOL,
    check_env_merge_grants,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    DEFECT_OVERFLOW_TAKEN,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    consume_defect_sink,
    set_defect_sink,
)

_ENV = '量子同频契约'
_POOL = ('符玄', '希儿')

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG = ChannelSig(family='logic_action', actor='EnvMergeGrantTest',
                  mode='compute')


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾;
    先例 = kernel/test_gain_chain.py 同名 helper)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> Iterator[_RowSink]:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def seeded_provider() -> Iterator[None]:
    """注确定 rng 提供槽(固定种子,期望名可现算钉名),必达复位。"""
    set_action_rng_provider(lambda tool: random.Random(20261016))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def _make_gs(*, env: str | None = _ENV,
             bench: list[tuple[str, int]] | None = None,
             overflow_card: str | None = None) -> GameState:
    """观察面按参组装(bench None = 保持未写形态;overflow_card 观察种
    = 溢出位已占形态,缺省 = 空溢出位)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if bench is not None:
        slots: list[BenchSlot | None] = [
            BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
            for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if overflow_card is not None:
        gs.observe(gs.overflow_card, overflow_card, sig=_SIG_OBS)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道)
    写行(先例 = 同目录 test_check_env_boss_grants.py 同名 helper)。"""
    calls: list[tuple[str, str | None, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic',
                        _wrap(gs.write_logic, 'logic'))
    return calls


def test_condition_matrix_short_circuits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """条件矩阵前两序短路(T-26 设计 §2.2 条 ①②):env 未激活(None/
    空链形态)/不在册/facts 无触发角色(发放物升星形态)→ 空效果串
    且零写(rng 未解析,不消耗采样流键)。"""
    cases = [
        ('env 未选择(None 形态)',
         _make_gs(env=None, bench=[]), (('花火', 2),)),
        ('env 空链(开局种子形态)',
         _make_gs(env='', bench=[]), (('花火', 2),)),
        ('env 不在册', _make_gs(env='蓝海', bench=[]), (('花火', 2),)),
        ('facts 无触发角色(发放物升星)',
         _make_gs(bench=[]), (('希儿', 2),)),
    ]
    for label, gs, facts in cases:
        calls = _record_writes(gs, monkeypatch)
        assert check_env_merge_grants(gs, facts, sig=_SIG) == (), label
        assert not calls, f'{label} 零写: {calls}'


def test_grant_seeded_via_provider_pinned_name(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """达标发放(T-26 设计 §4.4 正面):激活 + 触发角色 → 注入槽种子
    现算钉名,bench 增 1 个 1★ 发放角色,效果串 ``env_merge_grant:<名>``
    逐条对应;链写 evidence 前缀 = ``env_merge_grant:<env>``
    (#place 后缀为链内约定)。"""
    expected = random.Random(20261016).choice(list(_POOL))
    gs = _make_gs(bench=[])
    calls = _record_writes(gs, monkeypatch)
    effects = check_env_merge_grants(gs, (('花火', 2),), sig=_SIG)
    assert effects == (f'env_merge_grant:{expected}',), \
        f'效果串与发放名逐条对应: {effects}'
    units = [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
             if s is not None and s.kind == 'unit' and s.unit is not None]
    assert units == [(expected, 1)], '落席 1 个,1★ 先验'
    assert len(calls) == 1 and calls[0][0] == 'bench' \
        and calls[0][2] == 'rand', f'链写一行,采样 → rand 通道: {calls}'
    assert calls[0][1] == f'env_merge_grant:{_ENV}#place', \
        'evidence 前缀 = env_merge_grant:<env>'


def test_bench_unobserved_zero_container_write(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """bench 未观察(T-26 设计 §4.4):零写不炸,效果串照返——发放事实
    与落位成败解耦(item_gift 通道同阶口径),容器落位语义归链
    (拒落档零写)。"""
    gs = _make_gs(bench=None)
    assert gs.bench.value is None
    calls = _record_writes(gs, monkeypatch)
    effects = check_env_merge_grants(gs, (('花火', 2),), sig=_SIG)
    assert len(effects) == 1 and effects[0].startswith('env_merge_grant:'), \
        f'效果串照返: {effects}'
    assert not calls, f'链拒落零写: {calls}'


def test_bench_full_overflows_to_overflow_slot(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """席满 + 溢出位空(T-26 设计 §4.4):发放走溢出落位——overflow
    两字段成对写,身份 = 发放名。"""
    expected = random.Random(20261016).choice(list(_POOL))
    gs = _make_gs(bench=[(f'c{i}', 1) for i in range(9)])
    calls = _record_writes(gs, monkeypatch)
    effects = check_env_merge_grants(gs, (('缇宝', 2),), sig=_SIG)
    assert effects == (f'env_merge_grant:{expected}',), '效果串照返'
    fields = [c[0] for c in calls]
    assert fields == ['overflow_warning', 'overflow_card'], \
        f'溢出落位两字段成对写: {calls}'
    assert gs.overflow_card.value == expected, '溢出位身份 = 发放名'


def test_bench_full_overflow_occupied_zero_write(
        monkeypatch: pytest.MonkeyPatch, seeded_provider,
        rows_sink: _RowSink) -> None:
    """席满 + 溢出位占(T-26 设计 §4.4):零写 + DEFECT_OVERFLOW_TAKEN
    留证(游戏行为未实证禁猜,链内既有语义);效果串照返(发放事实
    与落位成败解耦)。"""
    gs = _make_gs(bench=[(f'c{i}', 1) for i in range(9)],
                  overflow_card='简易武装箱')
    calls = _record_writes(gs, monkeypatch)
    effects = check_env_merge_grants(gs, (('花火', 2),), sig=_SIG)
    assert len(effects) == 1 and effects[0].startswith('env_merge_grant:'), \
        '效果串照返'
    assert not calls, f'零写: {calls}'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN], \
        f'留证行: {rows_sink.kinds()}'


def test_rng_fallback_without_provider(seeded_provider) -> None:
    """回退自掷腿的反向对照(T-26 设计 §4.5):未装 provider(= live
    缺省)→ 回退自掷仍产出,名 ∈ 发放池(采样是猜测口径,不因缺装配
    而零发放)。"""
    set_action_rng_provider(None)
    gs = _make_gs(bench=[])
    effects = check_env_merge_grants(gs, (('花火', 2),), sig=_SIG)
    name = effects[0].split(':', 1)[1]
    assert name in _POOL, f'自掷仍发放且 ∈ 池: {effects}'


def test_rng_provider_deterministic_replay(seeded_provider) -> None:
    """注入槽确定性(T-26 设计 §4.5):装 provider 后同 facts 两次重放
    (各自全新 gs)采样结果一致——sim 世界真值 + 动作序列确定性 ⟹
    采样链确定性;同窗两条 facts 逐条发(两次发放)。"""
    facts = (('花火', 2), ('缇宝', 2))
    r = random.Random(20261016)
    expected = (f'env_merge_grant:{r.choice(list(_POOL))}',
                f'env_merge_grant:{r.choice(list(_POOL))}')
    results = []
    for _ in range(2):
        gs = _make_gs(bench=[])
        results.append(check_env_merge_grants(gs, facts, sig=_SIG))
    assert results[0] == expected and results[1] == expected, \
        f'两次重放同序: {results}'


def test_resolver_explicit_rng_beats_provider(seeded_provider) -> None:
    """解析口显式优先(T-26 设计 §4.5 末腿,action_sampling_rng 解析序
    「显式传入 > 注入槽」在本工具键解析点钉住):装 provider 下显式 rng
    在场则原样返回该实例(provider 不触)。"""
    explicit = random.Random(7)
    assert action_sampling_rng(ENV_MERGE_GRANT_RNG_TOOL, explicit) \
        is explicit, '显式传入优先于注入槽'
