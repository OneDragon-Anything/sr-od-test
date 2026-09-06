"""P65 晋升候选集可达性·12 线枚举快照锁 + 集合包含锁(v2 生产展开语义)。

锁契约(设计稿验收要求,.debug/temp/currency_war/lock_path_p2_channel_design/
DESIGN.md §3 P65 行「落码前 12 线枚举快照锁」):锁**结构事实**(枚举结果表),
不锁状态依赖数值(_core_reachable/G>ε 是逐帧数据面,归 sim 前置计数)。
锁红 ≠ 改动错:COMP_LIBRARY/TRANSITION_TRAITS 漂移时先对照设计出处重推
语义,确认漂移后同批更新快照表与单篇
docs/develop/currency_war/proofs/p65-promote-candidate-set-reachability.md。

v2 修订(复核 B1/B2):晋升侧直调生产 promote_candidates(cw_intention,
G8 观测载体在用,公式已落码——禁字面键第二实现);体系键交集语义 =
_pair_bond_keys 键侧展开(希儿系→量子同频+贝洛伯格);v1 的
「pair=(仙舟,希儿系) 反例洞」在生产展开语义下不存在(希儿量子线承接
展开键),洞断言改为闭合断言。

复算全量网格版(10368 格):tools/cw/proofs/p65_check.py。
"""
import itertools

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import TRANSITION_TRAITS
from sr_od.application.currency_war.kernel.cw_intention import (
    _core_reachable,
    _derive_p1_pair,
    _pair_bond_keys,
    _v2_comps,
    intention_core,
    line_completion_feasibility,
    promote_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY

#: 12 线枚举快照(单篇 §3 逐线表;漂移 = 锁红 → 重推语义后同批更新)。
#: 体系键交集列为**字面三羁绊键域**口径(M2 注:注册表快照口径;生产
#: 晋升判据消费 _pair_bond_keys 展开键,展开载体表见 test_p65_pair_carriers)。
SNAPSHOT_12 = (
    ('列车同行', '姬子列车', ('列车同行',), ()),
    ('命运圣杯红A', '圣杯双C', (), ()),
    ('绯英欢愉', '欢愉族', (), ()),
    ('希儿量子', '希儿量子', (), ()),
    ('黄泉减益', '黄泉减益', (), ()),
    ('双王圣杯', '圣杯双C', (), ()),
    ('大黑塔银河学者', '大黑塔群攻', (), ()),
    ('反甲白厄', '白厄反甲', (), ()),
    ('狼尊欢愉', '欢愉族', (), ()),
    ('万敌单C', '万敌燃血', (), ()),
    ('DOT队', 'DOT卡芙卡', ('持续伤害',), (2,)),
    ('专家桑博DOT', 'DOT卡芙卡', ('持续伤害',), ()),
)

_ENGINE_KEYS = tuple(b for b, _t in TRANSITION_TRAITS)
_PAIR_KEYS = _ENGINE_KEYS + ('希儿系',)


class _StubState:
    """纯函数评估用最小状态桩(字段契约同 p65_check.py,零真实副作用)。"""

    def __init__(self, plane: int, level: int, hp: int, round_num: int) -> None:
        self.plane = plane
        self.level = level
        self.hp = hp
        self.round_num = round_num
        self.bench = []
        self.deployed = []
        self.shop = []
        self.enemy_affixes = ()


class _StubIst:
    def __init__(self, evicted: frozenset[str] = frozenset(),
                 pair: tuple[str, ...] = ()) -> None:
        self.evicted = evicted
        self.p1_pair_frozen_obs = pair


def _handoff(state, ist, visible) -> set[str]:
    """移交候选判据(cw_intention.update_intention P2 移交段生产原式镜像,
    符号锚 = `_p2_handoff` 支 cands 列表推导)。"""
    return {c.name for c in _v2_comps()
            if c.name not in ist.evicted
            and state.plane not in (c.weak_planes or ())
            and _core_reachable(c, state, visible)
            and (state.plane != 2
                 or line_completion_feasibility(state, c, None, DEFAULT_REGISTRY,
                                                visible)
                 > DEFAULT_REGISTRY.revoke_miss_tolerance_eps)}


def _line_tiers(name: str) -> set[str]:
    """线档键(注册表现取;快照表不载档键全集,禁第二份)。"""
    for c in _v2_comps():
        if c.name == name:
            return set(c.form_tiers or {}) | set(c.sub_tiers or {})
    raise KeyError(name)


def test_p65_snapshot_12_lines() -> None:
    """枚举快照锁:12 线 × (family, 字面体系键交集, weak_planes) 结构事实。"""
    v2 = _v2_comps()
    assert len(v2) == 12
    got = []
    for c in v2:
        tiers = set(c.form_tiers or {}) | set(c.sub_tiers or {})
        got.append((c.name, c.family,
                    tuple(sorted(tiers & set(_ENGINE_KEYS))),
                    tuple(c.weak_planes or ())))
    assert tuple(got) == SNAPSHOT_12
    # 字面域读数:交集非空线恰 3 条,弱面注册恰 1 条(单载体边界,设计 §2.2)
    inter_lines = [r for r in SNAPSHOT_12 if r[2]]
    weak_lines = [r for r in SNAPSHOT_12 if r[3]]
    assert {r[0] for r in inter_lines} == {'列车同行', 'DOT队', '专家桑博DOT'}
    assert [r[0] for r in weak_lines] == ['DOT队']


def test_p65_containment_grid() -> None:
    """集合包含锁:生产 promote_candidates ⊆ 移交候选(网格抽样,全量
    10368 格见 p65_check.py)。"""
    n = 0
    for plane, level, hp, pair, evicted in itertools.product(
            (1, 2, 3), (5, 9), (0, 50),
            tuple(itertools.combinations(_PAIR_KEYS, 2)),
            (frozenset(), frozenset({'列车同行', 'DOT队', '专家桑博DOT',
                                     '希儿量子'}))):
        state = _StubState(plane, level, hp, 4)
        visible = {'姬子·启行', '桑博', '卡芙卡', '希儿'}
        ist = _StubIst(evicted, pair)
        extra = ({c.name for c in promote_candidates(state, ist, None,
                                                     DEFAULT_REGISTRY, visible)}
                 - _handoff(state, ist, visible))
        assert not extra, (f'包含破坏: plane={plane} lv={level} hp={hp} '
                           f'pair={pair} ev={sorted(evicted)} 越集={extra}')
        n += 1
    assert n == 3 * 2 * 2 * 6 * 2  # 144 格抽样(抽样锁,全量在复算脚本)


def test_p65_pair_carriers_expanded_bonds() -> None:
    """非空性结构锁(v2 生产展开语义):六 pair 在 _pair_bond_keys 展开下
    全部有非弱面活载体;v1 字面键「仙舟-希儿洞」闭合。"""
    expect = {
        ('列车同行', '持续伤害'): {'列车同行', '专家桑博DOT'},
        ('列车同行', '仙舟'): {'列车同行'},
        ('列车同行', '希儿系'): {'列车同行', '希儿量子', '专家桑博DOT'},
        ('持续伤害', '仙舟'): {'专家桑博DOT'},
        ('持续伤害', '希儿系'): {'希儿量子', '专家桑博DOT'},
        ('仙舟', '希儿系'): {'希儿量子', '专家桑博DOT'},   # v1 洞已闭合
    }
    for pair, carriers in expect.items():
        assert set(_pair_bond_keys(pair)) == (
            (set(pair) - {'希儿系'})
            | ({'量子同频', '贝洛伯格'} if '希儿系' in pair else set())), \
            f'pair={pair} 展开键漂移'
        got = {name for name, _f, _i, weak in SNAPSHOT_12
               if 2 not in weak
               and set(_pair_bond_keys(pair)) & _line_tiers(name)}
        assert got == carriers, f'pair={pair} 展开载体漂移: {got} ≠ {carriers}'
    # 直跑实证:生产 promote_candidates 吃 (仙舟,希儿系) 冻结快照非空
    state = _StubState(3, 7, 100, 4)
    got = promote_candidates(state, _StubIst(frozenset(), ('仙舟', '希儿系')),
                             None, DEFAULT_REGISTRY, {'希儿'})
    assert '希儿量子' in {c.name for c in got}, (
        f'洞闭合直跑实证失败: {[c.name for c in got]}')
    # evicted 反例(仍可能的反例形态):全体系活载体驱逐 → 结构性空
    ev_all = frozenset({'列车同行', 'DOT队', '专家桑博DOT', '希儿量子'})
    for pair in expect:
        got = promote_candidates(state, _StubIst(ev_all, pair),
                                 None, DEFAULT_REGISTRY, {'希儿'})
        assert got == [], (
            f'evicted 反例失效: pair={pair} 残余 {[c.name for c in got]}')


def test_p65_hole_pair_derivable() -> None:
    """(仙舟,希儿系) pair 派生性锁:支持度 1.0 资产确可派生该 pair
    (注册表现查;该 pair 在生产展开语义下非空,派生性只证帧面可达)。"""
    tiers = dict(TRANSITION_TRAITS)
    bench_names = ['希儿']
    for name, ch in CHARACTERS.items():
        if '仙舟' in (set(ch.factions) | set(ch.flows)) \
                and len(bench_names) < tiers['仙舟'] + 1:
            bench_names.append(name)
    assert len(bench_names) == tiers['仙舟'] + 1

    class _Bc:
        def __init__(self, cid: str) -> None:
            self.char_id = cid
            self.faction = ''

    state = _StubState(1, 5, 50, 1)
    state.bench = [_Bc(n) for n in bench_names]
    pair = _derive_p1_pair(state)
    assert set(pair) == {'仙舟', '希儿系'}, f'pair 派生性失效: {pair}'


def test_p65_intention_core_resolves_all_12() -> None:
    """判据域完备性:12 线的意向核心全部可解析(空核心 = 判据域收窄前置)。"""
    for c in _v2_comps():
        assert intention_core(c), f'线 {c.name} 意向核心为空'


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
