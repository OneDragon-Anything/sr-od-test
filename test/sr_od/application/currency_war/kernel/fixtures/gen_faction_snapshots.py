"""羁绊优先级结构迁移(faction_reqs)的快照期望生成脚本。

原稿锁面 的迁移恒等测试载体(details/
faction-priority.md §7)。**真实生成流程**:随仓提交的期望 JSON
(faction_migration_snapshots.json)由**旧代码(form_tiers/sub_tiers
结构)+ 本脚本的历史版本**在迁移前产出(git 历史可溯);3.1 落地后
本脚本读口已全部换新(core_faction_reqs 等),**现运行产出的是新代码
侧的输出**——用于后续结构迁移类重构的重放核对(当期代码重立期望
基线),不是旧期望的再生成。变化①②(副档投资分/轮廓计数)按新语义
镜像生成期望并标注,测试单列断言。基线换代:required-deployed-
retirement(2026-11-06)整文件重立——fp 点名件折条源 = 定义件/core
统一表达式 + 部署 L1 两层支配编码;旧 JSON 的受克 punished 留档轴
随换代消失(其恒等断言已退役,沿革归 git 历史)。

快照面(§7):板面 fixture(每线 3 代表板面 + 2 全局混合板面 = 65)×
21 套阵容 → 成型度/线距离逐档进度/部署 L1/L2/L3;每线静态面 → 囤货
采购集/投资通道逐卡加分/阵容轮廓(变化②)。

板面构造规则(§7,构造确定性——成员取注册表该羁绊成员名单前 N 名):
- zero 零羁绊板 = 独立羁绊白厄 + 两未注册名(板面标签恒空);
- half 半成型板 = 每个档 0 键各上 ⌈目标人数/2⌉ 名该羁绊注册成员;
- formed 成型板 = 各键达标人数;
- mixed 混合板(全局 2 个,线对脚本内定)= 两线 core_chars 各取前半,
  线对刻意覆盖副档形态(变化①②断言面)。

重跑(仓库根): $env:PYTHONPATH='src'; uv run python sr-od-test/test/
sr_od/application/currency_war/kernel/fixtures/gen_faction_snapshots.py
(仅在结构迁移类重构时需要重跑;重跑语义 = 用当期代码重立期望基线)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.kernel import cw_intention, cw_invest_channels
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    form_progress,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    Unit,
    deployed_view_sequential,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
)
from sr_od.application.currency_war.kernel.cw_line_switch import (
    line_distance,
    tier_progress,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_search import (
    DeploySearchPanel,
    SearchUnit,
    _line_form_tier_groups,
    selection_score,
)

_OUT = Path(__file__).parent / 'faction_migration_snapshots.json'

_SIG = ChannelSig(family='obs', actor='GenFactionSnapshots')

#: 混合板线对(脚本内定,构造确定性;两对均覆盖副档形态,
#: 使变化①②的断言面有实际数据)
_MIXED_PAIRS: tuple[tuple[str, str], ...] = (
    ('列车同行·反震', '黄泉减益'),   # 两线均带副档(护盾2/击破2)
    ('希儿量子', '万敌单C'),         # 档 0 双键线 + 副档(战技点2)线
)

_ZERO_MEMBERS: list[str] = ['白厄', '路人甲', '路人乙']


def _comp(name: str):
    for c in COMP_LIBRARY:
        if c.name == name:
            return c
    raise KeyError(name)


def _self_bonds(name: str) -> set[str]:
    """成员自报羁绊标签全集(factions∪flows;未注册名 = 空集)。"""
    ch = CHARACTERS.get(name)
    if ch is None:
        return set()
    return set(ch.factions) | set(ch.flows)


def _board_members(kind: str, comp) -> list[str]:
    """板面成员名单(§7 构造规则;同名跨键去重保序)。

    每个档 0 键从注册表成员名单顺序取「自报该键」成员至 need 名
    (half = ⌈目标/2⌉,formed = 目标);零羁绊线(反甲白厄)退空板。
    """
    if kind == 'zero':
        return list(_ZERO_MEMBERS)
    out: list[str] = []
    for bond, tier in comp.core_faction_reqs.items():
        need = (tier + 1) // 2 if kind == 'half' else tier
        cnt = 0
        for name in FACTIONS[bond].members(include_flows=True):
            if name in out:
                continue
            if bond not in _self_bonds(name):
                continue
            out.append(name)
            cnt += 1
            if cnt >= need:
                break
    return out


def _mixed_members(name_a: str, name_b: str) -> list[str]:
    """混合板 = 两线 core_chars 各取前半(去重保序)。"""
    out: list[str] = []
    for name in (name_a, name_b):
        core = _comp(name).core_chars
        for n in core[:(len(core) + 1) // 2]:
            if n not in out:
                out.append(n)
    return out


def _make_fixture(board_id: str, kind: str, line: str,
                  members: list[str]) -> dict:
    """板面 fixture:成员名单 → GameState(board/deployed)+ 搜索 units。

    板面羁绊计数 = 成员自报标签统计(注册表派生口径);上阵 = 前 4 后 6
    顺序填(StarUnit.row 同源)。
    """
    front = [Unit(char_id=n, star=1, equips=[]) for n in members[:4]]
    back = [Unit(char_id=n, star=1, equips=[]) for n in members[4:]]
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.deployed, deployed_view_sequential(front, back), sig=_SIG)
    counts: Counter[str] = Counter()
    for n in members:
        for tag in _self_bonds(n):
            counts[tag] += 1
    gs.observe(gs.board, dict(counts), sig=_SIG)
    units = [
        SearchUnit(key=n, char_id=n, star=1, origin='board',
                   row=('front' if i < 4 else 'back'), uid=None)
        for i, n in enumerate(members)
    ]
    return {'id': board_id, 'kind': kind, 'line': line,
            'members': members, 'gs': gs, 'units': units,
            'current_board': {u.key: u.row for u in units}}


def _selection_snapshot(comp, fx: dict) -> dict:
    """部署搜索三层分(锁定窗形态调用 = selection_score 生产消费位)。"""
    panel = DeploySearchPanel(
        units=tuple(fx['units']),
        k_budget=len(fx['units']),
        front_capacity=4, back_capacity=6,
        locked=True, locked_comp=comp,
        candidate_comps=(), transition_comps=(),
        current_board=dict(fx['current_board']),
    )
    keys = tuple(dict.fromkeys(
        k for g in _line_form_tier_groups(comp) for k in g))
    l1, l2, l3 = selection_score(panel, list(fx['units']), comp, keys)
    return {'l1': l1, 'l2': l2, 'l3': l3}


def _new_hit_bonus(faction: str, tier: int, comp) -> int:
    """变化①镜像(新语义羁绊命中档,faction-priority.md §4 投资通道行):
    档 0 键 = 全档;副档键 = 降档分(INVEST_SOFT 同 flex 规则);flex
    不变。仅 ``_faction_hit_bonus`` 换轴,查询链其余环节原样。"""
    from sr_od.application.currency_war.kernel.cw_line_scales import (
        INVEST_SOFT,
        INVEST_STRONG,
    )
    if not faction:
        return 0
    core_keys = set(comp.core_faction_reqs)
    if faction in core_keys:
        return tier
    if faction in set(comp.bonus_faction_reqs) \
            or faction in (comp.flex_factions or ()):
        return INVEST_SOFT if tier >= INVEST_STRONG else 0
    return 0


def _invest_snapshots(comp, *, new_semantics: bool) -> dict[str, dict]:
    """投资通道逐卡加分(环境 + 策略全注册卡)。new_semantics=True 时把
    通道模块的羁绊命中函数换成变化①镜像(其余查询链原样)。"""
    original = cw_invest_channels._faction_hit_bonus
    if new_semantics:
        cw_invest_channels._faction_hit_bonus = _new_hit_bonus
    try:
        env = {name: cw_invest_channels.env_line_bonus(name, comp)
               for name in INVESTMENT_ENVS}
        st = {name: cw_invest_channels.strategy_line_bonus(name, comp)
              for name in INVESTMENT_STRATEGIES}
    finally:
        cw_invest_channels._faction_hit_bonus = original
    return {'env': env, 'strategy': st}


def main() -> int:
    boards: list[dict] = []
    for comp in COMP_LIBRARY:
        for kind in ('zero', 'half', 'formed'):
            members = _board_members(kind, comp)
            boards.append(_make_fixture(f'{comp.name}:{kind}', kind,
                                        comp.name, members))
    for i, (a, b) in enumerate(_MIXED_PAIRS, start=1):
        members = _mixed_members(a, b)
        boards.append(_make_fixture(f'mixed{i}', 'mixed', f'{a}+{b}',
                                    members))

    board_line: dict[str, dict[str, dict]] = {}
    for fx in boards:
        per_line: dict[str, dict] = {}
        for comp in COMP_LIBRARY:
            per_line[comp.name] = {
                'fp': form_progress(comp, fx['gs']),
                'prog': {k: list(v) for k, v in
                         tier_progress(comp, fx['gs']).items()},
                'dist': line_distance(comp, fx['gs']),
                **_selection_snapshot(comp, fx),
            }
        board_line[fx['id']] = per_line

    line_static: dict[str, dict] = {}
    for comp in COMP_LIBRARY:
        chars, equips = cw_intention._line_hoard(comp)
        line_static[comp.name] = {
            'hoard_chars': sorted(chars),
            'hoard_equips': sorted(equips),
            'invest_old': _invest_snapshots(comp, new_semantics=False),
            'invest_new': _invest_snapshots(comp, new_semantics=True),
            'all_factions_old': sorted(set(comp.factions)
                                       | set(comp.flex_factions)),
            'all_factions_new': sorted(set(comp.factions)
                                       | set(comp.bonus_faction_reqs)
                                       | set(comp.flex_factions)),
        }

    data = {
        'meta': {
            'boards': len(boards),
            'lines': len(COMP_LIBRARY),
            'mixed_pairs': [list(p) for p in _MIXED_PAIRS],
            'note': '恒等断言面 = board_line 全字段 + line_static 的 '
                    'hoard(迁移前后逐位恒等);invest_old 与 '
                    'all_factions_old 仅供对照,恒等断言面 = invest_new'
                    '/all_factions_new 之外的新代码实跑值与 invest_old'
                    ' 相等、与 all_factions_old 相等——变化①②差异另列;'
                    '受克判定恒等不在此面(3.2 起消费端直写表断言)',
        },
        'boards': [{k: fx[k] for k in ('id', 'kind', 'line', 'members')}
                   for fx in boards],
        'board_line': board_line,
        'line_static': line_static,
    }
    # 写前守卫(防分叉态误覆盖):快照 JSON 是迁移恒等基线,生成器本体
    # 可能落后于判读侧消费面(如 3.2 后 punished 解读轴由旧 JSON 留档、
    # 生成面已不再产出)——整文件重生成会连带抹掉留档轴。覆盖须显式
    # 声明 --confirm-overwrite;只想更新局部期望(如部署系数变更)走
    # 外科手术脚本按键重算,不整文件重写。
    if '--confirm-overwrite' not in sys.argv:
        print(f'[守卫] 拒绝写入 {_OUT}:整文件重生成会重置全部期望基线,')
        print('       且可能抹掉判读侧留档轴(如 punished 历史字段)。')
        print('       确认基线需要整体重立 → 加 --confirm-overwrite 重跑;')
        print('       局部期望更新 → 用按键重算的外科手术脚本。')
        return 1
    _OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1,
                               sort_keys=True), encoding='utf-8')
    diff_inv = [
        c.name for c in COMP_LIBRARY
        if line_static[c.name]['invest_old'] != line_static[c.name][
            'invest_new']
    ]
    diff_all = [
        c.name for c in COMP_LIBRARY
        if line_static[c.name]['all_factions_old'] != line_static[c.name][
            'all_factions_new']
    ]
    print(f'快照写入 {_OUT}')
    print(f'板面 {len(boards)} × 线 {len(COMP_LIBRARY)};'
          f'变化①差异线: {diff_inv}; 变化②差异线: {diff_all}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
