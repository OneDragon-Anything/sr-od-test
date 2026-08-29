"""r410 单位守恒与板面聚合锁(bench 表示语义演进后的现行版)。

历史:批⑦ F1(ADR-0219 第四次命中)曾修「旧代理 deployed=bench
切片不弹出、bench 恒含已上阵件」(席位/容量/卖出类门读假数据);
该「上阵即 pop」表示已被 **ADR-0316 槽位模型**取代——bench 定长
9 槽、空槽 None、上阵/卖出只置槽位不伸缩列表,本锁随之按现行
表示续锁(断言本体在槽位模型下逐位成立):

- 单位守恒:每轮 len(bench)+len(deployed) == 开局基线 + 累计买 −
  累计卖 − 2×累计合并(ADR-0276 起 3合1 merge 接入,每次合并
  净减 2 单位;ADR-0336 起 tx 整档替换轮重置守恒基线);
- deployed 跨轮累积单调不减(生产跟踪态;tx 整档替换合法缩减除外);
- board = deployed 羁绊聚合(生产 DeployMove 口径,ADR-0312 W50)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim import (
    START_BENCH_COUNT,
    _board_counts_of,
    simulate_p1,
)
from sr_od.application.currency_war.cw_state import BenchChar


def test_units_conservation_across_bench_deployed() -> None:
    """单位守恒(bench+deployed+2×merges;ADR-0316 槽位模型下
    bench 只含未上阵占用槽):

    (ADR-0336 适配:decision_v2 的 CompTransaction 整档替换事务
    内部含 fill(shop 源买新件)/ sell(卖件),账本不落 tx 明细
    (只记 reason/result)——tx 轮重置守恒基线(该轮单位数作新
    起点),非 tx 段内 v1 同式守恒照验;tx 披露缺口登记 ADR-0336。)"""
    for seed in (0, 1, 2, 3, 42):
        r = simulate_p1(seed, pool='fallback')
        base_units = START_BENCH_COUNT
        buys = sells = merges = 0
        for row in r.ledger:
            has_tx = any(a['__type__'] == 'CompTransaction'
                         and a.get('result') == 'applied'
                         for a in row['actions'])
            n_bench = len(row['state']['bench'])
            n_dep = len(row['state']['deployed'])
            if has_tx:
                # tx 单位变化不入账本:重置基线(ADR-0336 登记)
                base_units = n_bench + n_dep
                buys = sells = merges = 0
                continue
            for a in row['actions']:
                if a['__type__'] == 'BuyCard':
                    buys += 1
                elif a['__type__'] == 'SellBench':
                    sells += 1
            merges += (row['sim'].get('merges') or 0)
            expect = base_units + buys - sells - 2 * merges
            assert n_bench + n_dep == expect, (
                f'seed{seed} r{row["round_num"]}: bench{n_bench}'
                f'+deployed{n_dep} != {expect}'
                f'(单位守恒破坏:bench 表示 / 双重计数 / 合并计数漂移)')


def test_deployed_accumulates_monotonic() -> None:
    """deployed 跨轮累积(生产跟踪态),轮间单调不减。

    (ADR-0336 适配:decision_v2 的 CompTransaction 整档替换会
    合法缩减 deployed(换人下场)——tx 轮跳过;非 tx 轮单调照验。)"""
    for seed in (0, 5, 11):
        r = simulate_p1(seed, pool='fallback')
        prev = 0
        for row in r.ledger:
            n = len(row['state']['deployed'])
            has_tx = any(a['__type__'] == 'CompTransaction'
                         and a.get('result') == 'applied'
                         for a in row['actions'])
            if has_tx:
                continue   # tx 整档替换合法缩减排面(ADR-0336)
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
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
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
