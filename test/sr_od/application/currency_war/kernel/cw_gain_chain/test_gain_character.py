"""gain_character 顶层合并升星触发发放测试(镜像 src =
kernel/cw_gain_chain.py 的被测函数 ``gain_character``;同模块存量测试 =
kernel/test_gain_chain.py,本文件按被测方法拆目录规范落位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-26-liangzi-tongpin-qiyue.md(定稿)§2.3 条 3 + §2.2 条 ④ + §4.3:
- **引擎 B 采集顶层发火**:链内每级合并攒一条 ``(角色名, 新星级)``
  事实,顶层 ``gain_character`` 全部写毕后统一交
  ``check_env_merge_grants``——单级三连 = 发火一次一发;
- **级联两级 = 两次发放**(逐级触发判例:每完成一级 3 合 1 各触发
  一次);
- **发放物不在触发集不发**:希儿/符玄自身升星,facts 过滤后零发放,
  递归天然终止(无环,无额外闸)。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_character,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
)

_ENV = '量子同频契约'
_POOL = ('符玄', '希儿')

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG = ChannelSig(family='logic_action', actor='CwGainChainTest',
                  mode='compute')


def _make_gs(bench: list[tuple[str, int]],
             env: str | None = _ENV) -> GameState:
    """直构容器:bench 观察(按参组装)+ active_env 观察种子。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [
        BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
        for c, s in bench]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    return gs


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


@pytest.fixture
def seeded_provider() -> Iterator[None]:
    """注确定 rng 提供槽(固定种子,期望名可现算钉名),必达复位。"""
    set_action_rng_provider(
        lambda tool: random.Random(20261016))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def test_single_level_fires_once(seeded_provider) -> None:
    """单级三连顶层发火一次(T-26 设计 §4.3 前半):预置 2×1★花火,
    gain_character('花火', 1) 补齐三连 → 2★ 产物 + 恰一次发放
    (bench = [花火 2★, 发放角色 1★];发放名 = 注入槽种子现算,∈ 发放池)。"""
    expected = random.Random(20261016).choice(list(_POOL))
    gs = _make_gs([('花火', 1), ('花火', 1)])
    gain_character(gs, '花火', 1, rand=False, sig=_SIG,
                   evidence='t', producer='T')
    assert _bench_units(gs) == [('花火', 2), (expected, 1)], \
        '合并产物 + 发放角色 1★ 并存,发放恰一次'


def test_cascade_two_levels_fires_twice(seeded_provider) -> None:
    """级联两级两次发放(T-26 设计 §4.3,逐级触发判例):预置 2×1★ +
    2×2★ 花火,gain_character('花火', 1) → facts [(花火,2),(花火,3)]
    两条 → 两次发放(同窗逐条发,共享一个解析 rng 依序消耗)。"""
    r = random.Random(20261016)
    expected = [r.choice(list(_POOL)), r.choice(list(_POOL))]
    gs = _make_gs([('花火', 1), ('花火', 1),
                   ('花火', 2), ('花火', 2)])
    gain_character(gs, '花火', 1, rand=False, sig=_SIG,
                   evidence='t', producer='T')
    assert _bench_units(gs) == [('花火', 3),
                                (expected[0], 1), (expected[1], 1)], \
        f'3★ 产物 + 两次发放并存: {_bench_units(gs)}'


def test_grant_target_star_up_does_not_retrigger() -> None:
    """发放物升星不发(T-26 设计 §4.3 末句):希儿不在触发集——预置
    2×1★希儿,gain_character('希儿', 1) 合成 2★ 产物,facts 过滤后
    零发放(无符玄/希儿新增发放,链天然终止无环)。"""
    gs = _make_gs([('希儿', 1), ('希儿', 1)])
    gain_character(gs, '希儿', 1, rand=False, sig=_SIG,
                   evidence='t', producer='T')
    assert _bench_units(gs) == [('希儿', 2)], \
        '仅升星产物,零发放'
