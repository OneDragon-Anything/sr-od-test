"""r410/ADR-0271 锁:sim 上阵即 pop(生产 bench 语义对齐)。

批⑦ F1(ADR-0219 第四次命中):旧代理 deployed=bench 切片不弹出,
bench 恒含已上阵件(94.6% 轮 bench≥9 虚高、极大 25),席位/容量/
卖出类门全读假数据。修正后锁三条:
- 单位守恒:每轮 len(bench)+len(deployed) == 开局4 + 累计买 −
  累计卖 − 2×累计合并(ADR-0276 起 3合1 merge 接入,每次合并
  净减 2 单位;旧代理双重计数,此守恒必破);
- deployed 跨轮累积单调不减(生产跟踪态;旧代理每轮从零重算);
- board = deployed 主阵营聚合(生产 DeployMove 口径)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim import (
    START_BENCH_COUNT,
    _board_counts_of,
    simulate_p1,
)
from sr_od.application.currency_war.cw_state import BenchChar


def test_units_conservation_bench_excludes_deployed() -> None:
    """上阵即 pop + 3合1 合并:bench+deployed+2×merges 守恒。"""
    for seed in (0, 1, 2, 3, 42):
        r = simulate_p1(seed, pool='fallback')
        buys = sells = merges = 0
        for row in r.ledger:
            for a in row['actions']:
                if a['__type__'] == 'BuyCard':
                    buys += 1
                elif a['__type__'] == 'SellBench':
                    sells += 1
            merges += (row['sim'].get('merges') or 0)
            n_bench = len(row['state']['bench'])
            n_dep = len(row['state']['deployed'])
            expect = START_BENCH_COUNT + buys - sells - 2 * merges
            assert n_bench + n_dep == expect, (
                f'seed{seed} r{row["round_num"]}: bench{n_bench}'
                f'+deployed{n_dep} != {expect}'
                f'(上阵未 pop / 双重计数 / 合并计数漂移)')


def test_deployed_accumulates_monotonic() -> None:
    """deployed 跨轮累积(生产跟踪态),轮间单调不减。"""
    for seed in (0, 5, 11):
        r = simulate_p1(seed, pool='fallback')
        prev = 0
        for row in r.ledger:
            n = len(row['state']['deployed'])
            assert n >= prev, (
                f'seed{seed} r{row["round_num"]}: deployed {n}<{prev}'
                '(累积态不应缩减——无下场机制)')
            prev = n


def test_board_is_deployed_faction_counts() -> None:
    """state.board = deployed 羁绊全集聚合(ADR-0312 W50 口径;
    per-unit 单一源 unit_bond_tags——本锁锁「sim 维护 board ← 聚合」
    的接线,per-unit 值由 test_cw_w50_board_caliber 直锁)。"""
    from sr_od.application.currency_war.cw_bond_equips import unit_bond_tags
    r = simulate_p1(7, pool='fallback')
    for row in r.ledger:
        expect: dict[str, int] = {}
        for d in row['state']['deployed']:
            tags = unit_bond_tags(_ns(d))
            if tags:
                for t in tags:
                    expect[t] = expect.get(t, 0) + 1
                continue
            f = d.get('faction') or ''
            if f and f != '?':
                expect[f] = expect.get(f, 0) + 1
        assert row['state']['board'] == expect


def _ns(d: dict):
    from types import SimpleNamespace
    return SimpleNamespace(
        char_id=d.get('char_id') or '',
        position_pref=d.get('position_pref') or 'back',
        faction=d.get('faction') or '',
        equips=d.get('equips') or [])


def test_board_counts_of_fullset_caliber() -> None:
    """_board_counts_of:羁绊全集(factions+flows+independent+星徽装备
    贡献;ADR-0312 W50);未识别回退 faction 单标签(空/'?' 不计)。"""
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    dep = [
        BenchChar(slot=1, char_id='希儿', faction='量子同频'),
        BenchChar(slot=2, char_id='银狼', faction='量子同频'),
        BenchChar(slot=3, char_id='', faction='?'),
        BenchChar(slot=4, char_id='银狼LV.999', faction='星核猎手',
                  equips=['欢愉卡带']),
    ]
    expect: dict[str, int] = {}
    for d in dep[:2] :
        ch = CHARACTERS[d.char_id]
        for t in (*ch.factions, *ch.flows, ch.independent):
            if t:
                expect[t] = expect.get(t, 0) + 1
    # 银狼LV.999 = 星核猎手 + 欢愉(flow) + 头号玩家(独立)+ 卡带欢愉 +1
    expect['星核猎手'] = expect.get('星核猎手', 0) + 1
    expect['欢愉'] = expect.get('欢愉', 0) + 2
    expect['头号玩家'] = expect.get('头号玩家', 0) + 1
    assert _board_counts_of(dep) == expect
    assert _board_counts_of([]) == {}
