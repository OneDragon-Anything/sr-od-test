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


# ============================================================ uid 注入(T-30)


def test_uid_param_injected_into_placed_unit() -> None:
    """uid 尾形参 = 环境发放链注入点(T-30 设计 §2.3 条 7):显式传
    uid → 落位单位携带该实例号;缺省(既有全部调用点)恒 None。"""
    gs = _make_gs([])
    gain_character(gs, '流萤', 1, rand=False, sig=_SIG,
                   evidence='t', producer='T', uid=7)
    assert _bench_units(gs) == [('流萤', 1)]
    placed = [s.unit for s in gs.bench.value.slots
              if s is not None and s.kind == 'unit' and s.unit is not None]
    assert placed[0].uid == 7, 'uid 随落位构造注入'
    gs2 = _make_gs([])
    gain_character(gs2, '卡芙卡', 1, rand=False, sig=_SIG,
                   evidence='t', producer='T')
    placed2 = [s.unit for s in gs2.bench.value.slots
               if s is not None and s.kind == 'unit' and s.unit is not None]
    assert placed2[0].uid is None, '缺省恒 None(即时分支/购入形态)'


# ============================================================ 合成落场不辖(T-30)


def test_merge_consumes_locked_unit_product_free() -> None:
    """锁件合成消耗自由(设计 §4 锁 9,裁决 6 随裁决 2 收尾钉死):被锁
    流萤(uid=1)作素材的 3 合 1 成功——不炸不拦(锁 = 直部署禁令,
    合成消耗不在辖域);产物 2★ uid=1 承继(T-368 合成承继规则改判:
    素材已发号 uid 最小值;本测试 gs 无锁记录 = 豁免不触发,锁域豁免
    形态归 test_merge_inherit_uid.py 专项)——「锁随消耗自愈」经豁免
    路径保留(素材 uid 命中未解锁锁记录时产物置 None,守卫不再匹配)。"""
    slots_units = [Unit(char_id='流萤', star=1),
                   Unit(char_id='流萤', star=1, uid=1),
                   Unit(char_id='流萤', star=1)]
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [BenchSlot(kind='unit', unit=u)
                                     for u in slots_units]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gain_character(gs, '流萤', 1, rand=False, sig=_SIG,
                   evidence='t', producer='T')
    # 落位第四只补齐三连:合成 2★ 产物 + 新落位 1★ 并存(扫描序最左
    # 为载体);被锁 uid=1 张在素材组内被消耗
    assert _bench_units(gs) == [('流萤', 2), ('流萤', 1)]
    placed = [s.unit for s in gs.bench.value.slots
              if s is not None and s.kind == 'unit' and s.unit is not None]
    assert placed[0].uid == 1 and placed[1].uid is None, \
        '产物承继素材已发号 min(uid=1),新落位缺省恒 None'


def test_board_carrier_merge_product_lands_board_uid_free() -> None:
    """场上载体优先通道(设计 §4 锁 9 后半):被锁流萤(uid=1)在场上
    作载体 + bench 1×同名 → 新落位补齐后跨域三连,载体 = 场上那只
    (引擎 B merge_step_once「场上优先」规则)→ 产物直接落 board 且
    uid=1 承继(素材已发号 min,T-368 承继规则;不炸不拦)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        DeployedView,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [BenchSlot(kind='unit', unit=Unit(
        char_id='流萤', star=1))]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.deployed,
               DeployedView(front_slots=[Unit(char_id='流萤', star=1,
                                              uid=1), None, None, None],
                            back_slots=[None] * 6), sig=_SIG_OBS)
    gain_character(gs, '流萤', 1, rand=False, sig=_SIG,
                   evidence='t', producer='T')
    front = [u for u in gs.deployed.value.front_slots if u is not None]
    assert [(u.char_id, u.star) for u in front] == [('流萤', 2)], \
        '场上载体升星,产物落 board'
    assert front[0].uid == 1, 'board 产物承继载体 uid(素材已发号 min)'
    bench_left = [s.unit for s in gs.bench.value.slots
                  if s is not None and s.kind == 'unit' and s.unit is not None]
    assert bench_left == [], 'bench 素材两只(存量+新落位)全数被消耗'
