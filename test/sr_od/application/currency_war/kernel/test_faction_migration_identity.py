"""羁绊优先级结构(faction_reqs)迁移恒等测试。

迭代 comp-structure-unification 3.1(details/faction-priority.md §7):
迁移前在旧代码上生成期望快照(fixtures/gen_faction_snapshots.py →
faction_migration_snapshots.json),迁移后本文件重建同构板面逐位断言——
除变化①②(副档投资分/轮廓计数,按新语义单列断言)外全部恒等。

板面构造与生成脚本同源(importlib 加载复用,禁第二份构造逻辑——
构造漂移 = 恒等断言失效):每线 3 代表板面(零羁绊/半成型/成型)+
2 全局混合板面 = 65;快照面 = 成型度/线距离逐档进度/部署 L1/L2/L3
(65×21 全组合)+ 囤货采购集/受克判定/投资通道逐卡加分/阵容轮廓。

测试纪律:贵计算一次跑完(module fixture 现算全部值,断言共用);
JSON 里的 invest_old/all_factions_old 仅供人工对照,不作断言面
(新代码实跑 == invest_new/all_factions_new——副档语义修正的期望;
「当前 21 套数据下新旧相等」是数据现状非结构契约,不锁)。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    Comp,
    form_progress,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_invest_channels import (
    env_line_bonus,
    strategy_line_bonus,
)
from sr_od.application.currency_war.kernel.cw_line_switch import (
    line_distance,
    tier_progress,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_search import (
    _line_form_tier_groups,
    selection_score,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.pick_common import (
    punished_mechs_of,
)

_FIXTURES = Path(__file__).parent / 'fixtures'


def _load_gen_module():
    """加载生成脚本模块(板面构造逻辑单一源,测试与生成共用)。"""
    spec = importlib.util.spec_from_file_location(
        '_gen_faction_snapshots', _FIXTURES / 'gen_faction_snapshots.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def snapshot() -> dict:
    return json.loads(
        (_FIXTURES / 'faction_migration_snapshots.json').read_text(
            encoding='utf-8'))


@pytest.fixture(scope='module')
def fixtures(snapshot: dict) -> dict:
    """65 板面重建(与生成脚本同源构造)+ 全快照面现算(一次跑完)。"""
    gen = _load_gen_module()
    boards = []
    for comp in COMP_LIBRARY:
        for kind in ('zero', 'half', 'formed'):
            members = gen._board_members(kind, comp)
            boards.append(gen._make_fixture(
                f'{comp.name}:{kind}', kind, comp.name, members))
    for i, (a, b) in enumerate(gen._MIXED_PAIRS, start=1):
        boards.append(gen._make_fixture(
            f'mixed{i}', 'mixed', f'{a}+{b}', gen._mixed_members(a, b)))
    assert [fx['id'] for fx in boards] == \
        [b['id'] for b in snapshot['boards']], '板面集与快照漂移'
    return {fx['id']: fx for fx in boards}


def _selection_of(comp, fx: dict) -> dict:
    from sr_od.application.currency_war.strategies.impl.mandate_v1.\
        deploy_search import DeploySearchPanel
    panel = DeploySearchPanel(
        units=tuple(fx['units']),
        k_budget=len(fx['units']),
        front_capacity=4, back_capacity=6,
        locked=True, locked_comp=comp,
        candidate_comps=(), p1_pair=(), plane1=False,
        current_board=dict(fx['current_board']),
    )
    keys = tuple(dict.fromkeys(
        k for g in _line_form_tier_groups(comp) for k in g))
    l1, l2, l3 = selection_score(panel, list(fx['units']), comp, keys)
    return {'l1': l1, 'l2': l2, 'l3': l3}


def test_migration_identity_board_lines(snapshot: dict, fixtures: dict) -> None:
    """恒等主面:65 板面 × 21 线的成型度/线距离逐档进度/部署 L1/L2/L3
    与迁移前快照逐位相等(浮点按快照原值精确比较——计算链未变,
    差异即迁移破坏)。"""
    for board_id, per_line in snapshot['board_line'].items():
        fx = fixtures[board_id]
        for line_name, want in per_line.items():
            comp = get_comp(line_name)
            got_fp = form_progress(comp, fx['gs'])
            assert got_fp == want['fp'], \
                f'{board_id}×{line_name} 成型度漂移: {got_fp} ≠ {want["fp"]}'
            got_prog = {k: list(v) for k, v in
                        tier_progress(comp, fx['gs']).items()}
            assert got_prog == want['prog'], \
                f'{board_id}×{line_name} 逐档进度漂移'
            assert line_distance(comp, fx['gs']) == want['dist'], \
                f'{board_id}×{line_name} 线距离漂移'
            got_sel = _selection_of(comp, fx)
            for key in ('l1', 'l2', 'l3'):
                assert got_sel[key] == want[key], (
                    f'{board_id}×{line_name} 部署{key.upper()}漂移: '
                    f'{got_sel[key]} ≠ {want[key]}')


def test_migration_identity_line_static(snapshot: dict) -> None:
    """恒等静态面:囤货采购集(角色件/装备件)与受克判定输出逐线相等
    (受克判定 = 3.1 中间态行为面,键集恒等 → 输出恒等)。"""
    from sr_od.application.currency_war.kernel import cw_intention
    for comp in COMP_LIBRARY:
        want = snapshot['line_static'][comp.name]
        chars, equips = cw_intention._line_hoard(comp)
        assert sorted(chars) == want['hoard_chars'], \
            f'{comp.name} 囤货角色件漂移'
        assert sorted(equips) == want['hoard_equips'], \
            f'{comp.name} 囤货装备件漂移'
        assert sorted(punished_mechs_of(comp)) == want['punished'], \
            f'{comp.name} 受克判定输出漂移'


def test_invest_bonus_subtier_semantics(snapshot: dict) -> None:
    """变化①(副档语义修正,单列断言):投资通道逐卡加分 = 新语义期望
    (档 0/or 键全档;副档键降档分,INVEST_SOFT 同 flex 规则;flex 不变)。
    当前 21 套数据副档键全部同时在 flex 里 → 数值与旧值相等(快照
    invest_old 留档对照);副档键脱离 flex 的未来数据演化按新语义给分。"""
    for comp in COMP_LIBRARY:
        want = snapshot['line_static'][comp.name]['invest_new']
        for name, expected in want['env'].items():
            assert env_line_bonus(name, comp) == expected, \
                f'{comp.name}×{name} 环境加分漂移(新语义)'
        for name, expected in want['strategy'].items():
            assert strategy_line_bonus(name, comp) == expected, \
                f'{comp.name}×{name} 策略加分漂移(新语义)'


def test_all_factions_subtier_semantics(snapshot: dict) -> None:
    """变化②(副档语义修正,单列断言):阵容轮廓 = 核心 ∪ 副档 ∪ 弹性
    (副档键计入轮廓——旧读法不含副档键的历史遗留修正)。"""
    for comp in COMP_LIBRARY:
        want = set(snapshot['line_static'][comp.name]['all_factions_new'])
        assert comp.all_factions == want, \
            f'{comp.name} 阵容轮廓漂移(新语义)'


def test_faction_reqs_read_ports() -> None:
    """统一读口结构契约:core/bonus 按档切分、factions = 档 0 键派生、
    旧字段(form_tiers/sub_tiers)已删零残留。"""
    assert not hasattr(Comp, 'form_tiers') and not hasattr(Comp, 'sub_tiers'), \
        '旧羁绊字段禁复活(双源)'
    for comp in COMP_LIBRARY:
        assert comp.core_faction_reqs == comp.faction_reqs.get(0, {}), \
            comp.name
        expect_bonus: dict[str, int] = {}
        for p in sorted(comp.faction_reqs):
            if p:
                expect_bonus.update(comp.faction_reqs[p])
        assert comp.bonus_faction_reqs == expect_bonus, comp.name
        assert comp.factions == list(comp.core_faction_reqs.keys()), comp.name


def test_faction_reqs_build_validation() -> None:
    """建库校验(①②④⑤;③实施时点 = 3.3,faction-priority.md §5):
    非法数据构造即炸——未注册羁绊名/同一羁绊跨档/跳档/非正整数。"""
    with pytest.raises(ValueError, match='羁绊名未注册'):
        Comp(name='x', core_chars=[], faction_reqs={0: {'不存在的羁绊': 2}})
    with pytest.raises(ValueError, match='同时出现在档'):
        Comp(name='x', core_chars=[],
             faction_reqs={0: {'仙舟': 3}, 1: {'仙舟': 2}})
    with pytest.raises(ValueError, match='连续 0..max'):
        Comp(name='x', core_chars=[], faction_reqs={0: {'仙舟': 3},
                                                    2: {'护盾': 2}})
    with pytest.raises(ValueError, match='连续 0..max'):
        Comp(name='x', core_chars=[], faction_reqs={1: {'护盾': 2}})
    with pytest.raises(ValueError, match='正整数'):
        Comp(name='x', core_chars=[], faction_reqs={0: {'仙舟': 0}})
    with pytest.raises(ValueError, match='正整数'):
        Comp(name='x', core_chars=[], faction_reqs={0: {'仙舟': (2, 4)}})


def test_library_migration_values() -> None:
    """21 套数据迁移正确性(迁移规则 = 档 0 承载旧主档、档 1 承载旧
    副档,值不变——代表性抽样断言 + 全库档结构健全)。"""
    by_name = {c.name: c for c in COMP_LIBRARY}
    assert by_name['列车同行·反震'].faction_reqs == \
        {0: {'列车同行': 4}, 1: {'护盾': 2}}
    assert by_name['黄泉减益'].faction_reqs == \
        {0: {'减益': 4, '巡海游侠': 4}, 1: {'击破': 2}}
    assert by_name['万敌单C'].faction_reqs == \
        {0: {'夜之半神': 2, '燃血': 4}, 1: {'战技点': 2}}
    assert by_name['DOT队'].faction_reqs == \
        {0: {'持续伤害': 4, '星核猎手': 2}, 1: {'减益': 2}}
    # 档 0 可缺席形态:非羁绊成型阵容档 0 空,加分层照常
    bai_e = by_name['反甲白厄']
    assert bai_e.core_faction_reqs == {} and bai_e.bonus_faction_reqs == \
        {'护盾': 2}
    # 无副档线:只有档 0
    assert by_name['景元仙舟'].faction_reqs == {0: {'仙舟': 5}}
