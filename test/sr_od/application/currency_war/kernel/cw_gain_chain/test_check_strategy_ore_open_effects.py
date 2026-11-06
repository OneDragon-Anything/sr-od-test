"""check_strategy_ore_open_effects 晶矿开启触发发放直构锁(镜像 src =
cw_gain_chain.py 同名函数 + _grant_ores_to_world 世界写;test_gain_chain.py
已超行限禁追加,本文件按拆目录规范落新位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-316-huangjing-kuanggong.md(定稿,REVIEW-T316 无需用户决定 7/7)§4 锁 2:
- 条件矩阵:掷中授予/未掷中零写/非持卡零写零流键消耗/灰档链底零发放/
  未知色档零发放/live 英文归一同判;
- 撞键负例锁(轮 1 F1 修订后基准案):spheres 预置 sim 满面板 8 点摘 1 号
  (k=1/g=1 非连续剩余集)→ 断言授予序 = 合成形 max+1、与剩余点零同坐标、
  ore_rewards 零键覆盖、原剩余矿全部仍在 spheres——count/len 基准在此
  形态会把授予点落回剩余区间(80,10 撞 8 号),三条后果路径的回归闸。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_ore_open_effects,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    OreSight,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
)

_SIG = ChannelSig(family='logic_action', actor='CwActionCollectOreParam',
                  group_id='g1')
_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_LSIG = ChannelSig(family='logic_action', actor='test-seed', mode='compute')

_HIT_SEED = 1     # Random(1) 首掷 ≈ 0.134 < 0.5(单掷中)
_HIT2_SEED = 7    # Random(7) 前两掷 0.324/0.151 < 0.5(双连中,批锁用)
_MISS_SEED = 2    # Random(2) 首掷 ≈ 0.956 ≥ 0.5(未掷中)
_CARD = '黄晶矿工'


@pytest.fixture
def rng_provider() -> Iterator[None]:
    """测试后必达复位注入槽(先例 = 同目录条件发放族锁同款纪律)。"""
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def _make_gs(*, held: bool = True,
             points: tuple[tuple[str, int, int, int], ...] = (),
             ore_rewards: dict[str, OreReward] | None = None,
             level: int | None = 3) -> GameState:
    """直构容器(spheres/ore_rewards/level/持卡按参播种;先例 =
    test_strategy_reward_ore 直构形)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if held:
        gs.write_logic(gs.active_strategies, [_CARD],
                       produced_by='test-seed', sig=_LSIG)
    gs.observe(gs.spheres, OreSight(
        count=len(points),
        colors=tuple(dict.fromkeys(p[0] for p in points)),
        points=points), sig=_OBS)
    if ore_rewards is not None:
        gs.write_logic(gs.ore_rewards, ore_rewards,
                       produced_by='test-seed', sig=_LSIG)
    if level is not None:
        gs.observe(gs.level, level, sig=_OBS)
    return gs


def _seed_provider(seed: int) -> None:
    set_action_rng_provider(lambda tool: random.Random(seed))


def _sphere_pts(gs: GameState) -> tuple[tuple[str, int, int, int], ...]:
    return gs.spheres.value.points if gs.spheres.value else ()


def test_hit_grants_tier_down_with_attachment(rng_provider) -> None:
    """掷中授予锁(T-316 设计 §4 锁 2):掷中 seed → spheres +1 映射档点
    ('金' 开 → 低一档 '蓝',合成形基准 0 起专用带 (10,10))+ ore_rewards
    +1 附着 + 返回 1。"""
    _seed_provider(_HIT_SEED)
    gs = _make_gs(points=(('gold', 100, 200, 30),))
    got = check_strategy_ore_open_effects(gs, ('金',), sig=_SIG, level=3)
    assert got == 1, f'返回授予数: {got}'
    pts = _sphere_pts(gs)
    assert ('蓝', 10, 10, 10) in pts, f'授予点在 spheres: {pts}'
    assert len(pts) == 2, f' spheres +1: {pts}'
    assert '10,10' in (gs.ore_rewards.value or {}), '附着键已生成'
    assert len(gs.ore_rewards.value) == 1, 'ore_rewards +1'


def test_miss_zero_write(rng_provider) -> None:
    """未掷中零写锁:未掷中 seed → 返回 0,spheres/ore_rewards 值不变
    (零写;rng 消耗 = 50% 掷点一笔,世界零落)。"""
    _seed_provider(_MISS_SEED)
    gs = _make_gs(points=(('gold', 100, 200, 30),))
    got = check_strategy_ore_open_effects(gs, ('金',), sig=_SIG, level=3)
    assert got == 0, f'未掷中返回 0: {got}'
    assert len(_sphere_pts(gs)) == 1, 'spheres 零写'
    assert gs.ore_rewards.value is None, 'ore_rewards 零写'


def test_not_holding_zero_write_zero_rng_consume(rng_provider) -> None:
    """非持卡零写零流键消耗锁(「无命中不消耗采样流键」,战技点契约族形):
    采样解析零次——若误先取键后判持卡,provider 调用计数红灯。"""
    calls = {'n': 0}

    def counting_provider(tool: str) -> random.Random:
        calls['n'] += 1
        return random.Random(_HIT_SEED)

    set_action_rng_provider(counting_provider)
    gs = _make_gs(held=False, points=(('gold', 100, 200, 30),))
    got = check_strategy_ore_open_effects(gs, ('金',), sig=_SIG, level=3)
    assert got == 0, f'非持卡返回 0: {got}'
    assert calls['n'] == 0, f'流键零消耗: {calls["n"]}'


def test_gray_chain_bottom_and_unknown_tier_zero_grant(rng_provider) -> None:
    """链底与未知色档零发放锁:灰档(链底 None)与未知色档(宁缺勿造)
    均零发放零流键消耗(全点未达掷点条件不取键)。"""
    calls = {'n': 0}

    def counting_provider(tool: str) -> random.Random:
        calls['n'] += 1
        return random.Random(_HIT_SEED)

    set_action_rng_provider(counting_provider)
    for colors in (('灰',), ('gray',), ('紫',)):
        gs = _make_gs(points=(('gold', 100, 200, 30),))
        got = check_strategy_ore_open_effects(gs, colors, sig=_SIG, level=3)
        assert got == 0, f'{colors} 零发放: {got}'
        assert len(_sphere_pts(gs)) == 1, f'{colors} spheres 零写'
    assert calls['n'] == 0, f'流键零消耗: {calls["n"]}'


def test_live_english_tier_normalized(rng_provider) -> None:
    """live 英文归一同判锁:('gold',) 入参归一为 '金' 后同判(授予 '蓝')。"""
    _seed_provider(_HIT_SEED)
    gs = _make_gs(points=(('gold', 100, 200, 30),))
    got = check_strategy_ore_open_effects(gs, ('gold',), sig=_SIG, level=3)
    assert got == 1, f'英文入参同判授予: {got}'
    assert ('蓝', 10, 10, 10) in _sphere_pts(gs), '归一后授予档同判'


def test_batch_load_order_sequential_coords(rng_provider) -> None:
    """多开批载荷序锁:('金','蓝') 双连中 seed → 授予 ('蓝',10,10)+
    ('灰',20,10) 依载荷序续接,返回 2(逐开独立掷,共享流键序内推进)。"""
    _seed_provider(_HIT2_SEED)
    gs = _make_gs()
    got = check_strategy_ore_open_effects(gs, ('金', '蓝'), sig=_SIG, level=3)
    assert got == 2, f'双连中授予数: {got}'
    pts = _sphere_pts(gs)
    assert (('蓝', 10, 10, 10) in pts and ('灰', 20, 10, 10) in pts), \
        f'载荷序续接坐标: {pts}'


def test_collision_negative_non_continuous_remaining(rng_provider) -> None:
    """撞键负例锁(T-316 设计 §4 锁 2,轮 1 F1 修订后基准案的回归闸):
    sim 满面板 8 点摘 1 号 → remaining = {2..8} 非连续集,max+1 基准授予
    序 = 9 号 (90,10)——与剩余点零同坐标、ore_rewards 零键覆盖(剩余矿
    附着原值不动)、原剩余矿全部仍在 spheres。count/len 基准回归形态 =
    授予点 (80,10) 撞 8 号,本锁红灯。"""
    _seed_provider(_HIT_SEED)
    # sim 面板真实构成(锚 = 1 金 + 5 蓝 + 2 灰):摘 1 号(金)后 remaining
    remaining = tuple(('蓝', i * 10, 10, 10) for i in range(2, 7)) + \
        (('灰', 70, 10, 10), ('灰', 80, 10, 10))
    seeded_attach = {f'{i * 10},10': OreReward(kind='gold', gold=i)
                     for i in range(2, 9)}
    gs = _make_gs(points=remaining, ore_rewards=seeded_attach)
    got = check_strategy_ore_open_effects(gs, ('金',), sig=_SIG, level=3)
    assert got == 1, f'掷中授予: {got}'
    pts = _sphere_pts(gs)
    # ① 原剩余矿全部仍在
    for pt in remaining:
        assert pt in pts, f'原剩余矿保持: {pt}'
    # ② 授予序 = 合成形 max+1(9 号 → (90,10)),非 count/len 基准(8 号)
    assert ('蓝', 90, 10, 10) in pts, f'授予点 = max+1 序: {pts}'
    # ③ 与剩余点零同坐标
    assert len({(p[1], p[2]) for p in pts}) == len(pts), '零同坐标'
    # ④ ore_rewards 零键覆盖(剩余矿附着原值不动)+ 授予矿新键已登记
    attach = gs.ore_rewards.value or {}
    for i in range(2, 9):
        assert attach[f'{i * 10},10'] == OreReward(kind='gold', gold=i), \
            f'剩余矿附着不被覆盖: {i}'
    assert '90,10' in attach, '授予矿附着新键'
    assert attach['90,10'] not in \
        [OreReward(kind='gold', gold=i) for i in range(2, 9)], \
        '新键值 = 新掷内容(非沿用被覆盖旧值)'


def test_level_none_grant_without_attachment(rng_provider) -> None:
    """level 缺读兜底锁:授予照常入世界,ore_rewards 零写(该批矿无附着,
    点击走既有缺项兜底路径,禁炸)。"""
    _seed_provider(_HIT_SEED)
    gs = _make_gs(points=(('gold', 100, 200, 30),), level=None)
    got = check_strategy_ore_open_effects(gs, ('金',), sig=_SIG, level=None)
    assert got == 1, f'level 缺读仍授予: {got}'
    assert ('蓝', 10, 10, 10) in _sphere_pts(gs), '矿入世界'
    assert gs.ore_rewards.value is None, '无附着零写'
