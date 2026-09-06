"""cw_batch_stats G4 派生指标读数烟测(ADR-0564 §6 预注册 roster-diff 口径;
ADR §7 G4 派生工具挂账的工具侧兑现,随候补批落地——落地审返工后本文件
fixture 与真实账本转录同形)。

锁面(合成账本行直灌 analyze_game,语义=读数,不锁牌面):
1. 冲突语境轮(locked_comp 解析 ∧ form_tiers['列车同行'] > 门封顶档)
   的仙舟全羁绊件离场 = 事件;卖出行有名 → sell_bench 通道分键;
2. 非仙舟件离场不计(口径=仙舟全羁绊件,注册表 factions+flows 查表);
3. 未武装语境(locked_comp='')/脏名不可解析/非列车冲突 comp 均不计
   语境轮(语境单一源 = cw_intention.locked_line_recipe_floor_conflict);
4. 档案形态(行无 locked_comp,= None)→ 指标 None,不误报 0;
5. report 批级聚合落印冒烟(门语义=事件数,率=事件/语境轮)。

判据名(事件名/率/通道)与脚本 analyze_game 键面同步演进;本文件只锁
ADR-0564 §6 预注册口径的读数语义,不锁打印排版。Fixture 卖出行 =
engine_p1 SellBench 真实账本转录形态(件名在顶层 name,无 card 键)
——fixture 偏离真实转录形态会把实现读错字段钉成假绿,禁改回嵌套形态。
"""
import importlib.util

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    RECIPE_FLOOR_TRAIN_CAP,
)


def _load_stats_module():
    """cw_batch_stats(skill 脚本,非包成员)按路径加载(同采购面批)。"""
    from one_dragon.utils.file_utils import get_project_root
    path = (get_project_root() / 'skills' / 'sr-od-currency-war-dev'
            / 'scripts' / 'cw_batch_stats.py')
    spec = importlib.util.spec_from_file_location('cw_batch_stats_g4', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _conflict_comp_name() -> str:
    """列车冲突 comp 名(注册表解析,锁前提自检不拍名)。"""
    for c in COMP_LIBRARY:
        if c.form_tiers.get('列车同行', 0) > RECIPE_FLOOR_TRAIN_CAP:
            return c.name
    raise AssertionError('注册表缺列车冲突 comp(烟测前提失效)')


def _non_conflict_comp_name() -> str:
    """非列车冲突 comp 名(无列车同行档键或 ≤ 封顶档)。"""
    for c in COMP_LIBRARY:
        if c.form_tiers.get('列车同行', 0) <= RECIPE_FLOOR_TRAIN_CAP:
            return c.name
    raise AssertionError('注册表全为列车冲突 comp(烟测前提失效)')


def _xz_name(exclude: tuple[str, ...] = ()) -> str:
    """仙舟全羁绊件名(用被测工具自己的注册表句柄解析——锁前提与
    被测口径同源)。"""
    reg = _load_stats_module()._g4_registry()
    assert reg, 'G4 注册表不可达(烟测前提失效)'
    for name in sorted(reg['xz_all']):
        if name not in exclude:
            return name
    raise AssertionError('仙舟全羁绊件集为空(烟测前提失效)')


def _non_xz_name(exclude: tuple[str, ...] = ()) -> str:
    """非仙舟件名(对照组)。"""
    reg = _load_stats_module()._g4_registry()
    assert reg, 'G4 注册表不可达(烟测前提失效)'
    for name in CHARACTERS:
        if name not in reg['xz_all'] and name not in exclude:
            return name
    raise AssertionError('注册表缺非仙舟件(烟测前提失效)')


def _row(round_num: int, *, locked_comp: str | None = '',
         deployed=(), bench=(), acts=()) -> dict:
    """最小可析账本行(analyze_game 消费键面 + G4 新增两键)。"""
    return {'plane': 1, 'round': round_num, 'node_type': 'normal',
            'gold': 40, 'hp': 60, 'hp_delta': 0, 'form': 0.5,
            'form_ok': False, 'level': 3, 'deployed': list(deployed),
            'bench': list(bench), 'factions': {}, 'acts': list(acts),
            'launch': None, 'obs': {}, 'shop_waves': [],
            'locked': bool(locked_comp), 'locked_comp': locked_comp}


def _unit(name: str) -> dict:
    return {'char_id': name, 'star': 1}


def _sell_bench_act(name: str) -> dict:
    """SellBench 真实账本转录形态(engine_p1 转录行:件名在顶层
    name,无 card 键)——fixture 与真实转录同形,防实现读错字段被
    假绿遮蔽。"""
    return {'__type__': 'SellBench', 'bench_idx': 0, 'name': name,
            'income': 1, 'sell_reason': ''}


class TestG4RosterDiffSemantics:
    """G4 读数语义锁(roster-diff × 行级 locked_comp 语境)。"""

    def test_xz_departure_in_conflict_context_counts(self):
        """冲突语境轮的仙舟件离场 = 1 事件;SellBench 有名 → sell_bench
        通道分键;率 = 1/1。"""
        mod = _load_stats_module()
        comp = _conflict_comp_name()
        xz = _xz_name()
        rows = [
            _row(1, locked_comp=comp, deployed=[_unit(xz)],
                 acts=[_sell_bench_act(xz)]),
            _row(2, locked_comp=comp),
        ]
        m = mod.analyze_game(rows)
        assert m['g4语境轮数'] == 1
        assert m['g4仙舟离场事件'] == 1
        assert m['g4离场事件率'] == 1.0
        assert m['g4离场通道'] == {'sell_bench': 1}

    def test_non_xz_departure_not_counted(self):
        """非仙舟件离场不计(仙舟全羁绊件口径;语境轮照计)。"""
        mod = _load_stats_module()
        comp = _conflict_comp_name()
        pad = _non_xz_name()
        rows = [
            _row(1, locked_comp=comp, bench=[_unit(pad)],
                 acts=[_sell_bench_act(pad)]),
            _row(2, locked_comp=comp),
        ]
        m = mod.analyze_game(rows)
        assert m['g4语境轮数'] == 1
        assert m['g4仙舟离场事件'] == 0
        assert m['g4离场事件率'] == 0.0

    def test_unarmed_and_unparseable_context_ignored(self):
        """未武装(locked_comp='')与脏名不可解析语境均不计语境轮。"""
        mod = _load_stats_module()
        xz = _xz_name()
        rows = [
            _row(1, locked_comp='', deployed=[_unit(xz)]),
            _row(2, locked_comp='',),
            _row(3, locked_comp='未注册comp脏名', deployed=[_unit(xz)]),
            _row(4, locked_comp='未注册comp脏名'),
        ]
        m = mod.analyze_game(rows)
        assert m['g4语境轮数'] == 0
        assert m['g4仙舟离场事件'] == 0
        assert m['g4离场事件率'] is None

    def test_non_conflict_comp_not_context(self):
        """非列车冲突 comp(无列车同行档键)不计语境轮。"""
        mod = _load_stats_module()
        xz = _xz_name()
        rows = [
            _row(1, locked_comp=_non_conflict_comp_name(),
                 deployed=[_unit(xz)]),
            _row(2, locked_comp=_non_conflict_comp_name()),
        ]
        m = mod.analyze_game(rows)
        assert m['g4语境轮数'] == 0
        assert m['g4仙舟离场事件'] == 0

    def test_archive_rows_without_locked_comp_report_none(self):
        """档案形态(行级 locked_comp=None)→ 指标 None,不误报 0。"""
        mod = _load_stats_module()
        xz = _xz_name()
        rows = [
            _row(1, locked_comp=None, deployed=[_unit(xz)]),
            _row(2, locked_comp=None),
        ]
        m = mod.analyze_game(rows)
        assert m['g4语境轮数'] is None
        assert m['g4仙舟离场事件'] is None
        assert m['g4离场事件率'] is None
        assert m['g4离场通道'] is None

    def test_unattributed_channel_when_no_sell_act(self):
        """无卖出行可归因 → unattributed 通道(离场即计,通道只作
        判读分键不改门语义)。"""
        mod = _load_stats_module()
        comp = _conflict_comp_name()
        xz = _xz_name()
        rows = [
            _row(1, locked_comp=comp, bench=[_unit(xz)]),
            _row(2, locked_comp=comp),
        ]
        m = mod.analyze_game(rows)
        assert m['g4仙舟离场事件'] == 1
        assert m['g4离场通道'] == {'unattributed': 1}


def test_g4_report_smoke(capsys):
    """report 批级聚合落印冒烟:门语义合计行 + 通道分键行可见。"""
    mod = _load_stats_module()
    comp = _conflict_comp_name()
    xz = _xz_name()
    rows = [
        _row(1, locked_comp=comp, bench=[_unit(xz)],
             acts=[_sell_bench_act(xz)]),
        _row(2, locked_comp=comp),
    ]
    mod.report({'smoke': rows}, 'G4 烟测')
    out = capsys.readouterr().out
    assert 'G4 仙舟离场事件(门语义,合计): 1' in out
    assert 'G4 通道分键: ' in out and 'sell_bench' in out
    # 档案形态批:无数据披露,不误报 0
    mod.report({'smoke': [_row(1, locked_comp=None),
                          _row(2, locked_comp=None)]}, 'G4 烟测档案')
    out2 = capsys.readouterr().out
    assert 'G4 仙舟离场事件: 无数据' in out2
