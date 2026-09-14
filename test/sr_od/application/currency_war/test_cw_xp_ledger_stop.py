"""CW 升级停止 XP 期望账本判据锁面(xp_ledger_stop + D12 检测器)。

出处 = kernel/cw_game_state.py apply_shop_action_logic LevelUpShop 行
(商店域逻辑态直写只写 xp 元组不写 level 域,升档等观察覆盖)+
design.md unified-action-factory §2.6 LevelUp 定案④(推进算子单一源
= xp_apply_clicks)+ sim/checks/suspects.py D12 docstring(位面末轮
超发对账式)。

锁的三件事:
1. xp_ledger_stop 判据真值表——账本越过 level_max 即停;live
   level_max=10 无门槛表项判据不辖(live 行为零变更锚);
2. 商店域转移函数的账本不变量(跨门槛后 need 槽换新级门槛)与判据
   合取下,逐击发射恰停在整买一级需求上(ALL IN 窗同级超发病灶形态);
3. D12 位面末轮超发对账检测器:超上限命中 / 恰达上限不命中 /
   非末轮不入辖 / sim 行与生产合并行的入口等级语义分派。
"""

from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_economy import (
    XP_PER_BUY,
    XP_TO_NEXT_LEVEL,
    clicks_to_next_level,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    apply_shop_action_logic,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import LevelUp
from sr_od.application.currency_war.sim.checks.suspects import (
    d12_plane_last_xp_overspend,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def test_xp_ledger_stop_truth_table():
    """账本判据真值表:sim 域(level_max=9)越过即停;live 域(10)不辖。

    (cur, need) 不变量:need = XP_TO_NEXT_LEVEL[账本真等级]
    (xp_apply_clicks 写端写入)。sim 注入视图 level_max=9
    (sim_decision_registry,LEVEL_CAP 冻结);live DEFAULT_REGISTRY
    level_max=10 无表项 → 判据不辖,停止语义全归 lv9_stop。
    """
    # lv8 账本(未到 9):不停
    assert not levelup.xp_ledger_stop((0, XP_TO_NEXT_LEVEL[8]), 9)
    assert not levelup.xp_ledger_stop((70, XP_TO_NEXT_LEVEL[8]), 9)
    # 跨门槛推进后 need 槽换 9 级门槛(2, 84):账本已到 9 → 停
    assert levelup.xp_ledger_stop((2, XP_TO_NEXT_LEVEL[9]), 9)
    # live level_max=10:无门槛表项,判据不辖(live 行为零变更锚)
    assert not levelup.xp_ledger_stop((0, XP_TO_NEXT_LEVEL[8]), 10)
    assert not levelup.xp_ledger_stop((2, XP_TO_NEXT_LEVEL[9]), 10)
    # 缺读/形状不全不辖(停判据缺读宁可放行,交 lv9_stop/量闸管辖)
    assert not levelup.xp_ledger_stop(None, 9)
    assert not levelup.xp_ledger_stop((5,), 9)


def test_shop_ledger_invariant_stops_at_target_level():
    """账本推进 + 判据合取:逐击发射恰停在整买一级需求(病灶形态回归锁)。

    复现 ALL IN 窗决策环骨架(decide_shop_screen 驱动器逐动作直写,
    level 域轮内滞留):lv8 起步逐击推进,lv9_stop 因 level 域滞留恒
    False——修复后由 xp_ledger_stop 在账本越过 9 的下一迭代拒发,总击数
    = ⌈XP_TO_NEXT_LEVEL[8]/4⌉,无超发。
    """
    bs = board_state_of(None)
    bs.write_logic(bs.level, 8, produced_by='CwScreenPrep', sig=_SIG)
    bs.write_logic(bs.xp, (0, XP_TO_NEXT_LEVEL[8]), produced_by='CwScreenPrep',
                   sig=_SIG)
    level_max = 9
    clicks = 0
    for _ in range(100):   # 防御上界:判据失效时循环有界(响亮红而非挂死)
        if levelup.lv9_stop(bs.level.value, level_max):
            break   # live 语义锚:level 域新鲜时照旧生效
        if levelup.xp_ledger_stop(bs.xp.value, level_max):
            break   # 修复判据:账本越过目标即停(level 域滞留盲区补位)
        if clicks_to_next_level(bs) <= 0:
            break   # 整批可发行前置(发射位 spend_unified 前置同式)
        outcome = apply_shop_action_logic(
            bs, LevelUp(cost=4), produced_by='test', sig=_SIG)
        assert outcome.applied
        clicks += 1
    assert clicks == -(-XP_TO_NEXT_LEVEL[8] // XP_PER_BUY)   # 恰整买需求
    # 终态账本:已推进到 9 级门槛元组(need 槽换新级),level 域仍滞留 8
    assert bs.xp.value[1] == XP_TO_NEXT_LEVEL[9]
    assert bs.level.value == 8


def _sim_rows(entry_level: int, last_clicks: int,
              *, last_is_sim: bool = True,
              last_own_level: int | None = None) -> list[dict]:
    """两轮账本行:r8(普通轮,轮末等级=entry_level)+
    r9 boss(位面末,clicks 笔 LevelUp,行内 state.level=
    last_own_level or entry_level)。last_is_sim=False 时末行
    摘掉 sim.spend 键 = 生产合并行形状(入口等级语义切换)。"""
    def _row(rn: int, node: str, level: int, sim: dict) -> dict:
        return {'plane': 1, 'round_num': rn,
                'sim': {'node': node, **sim},
                'state': {'level': level},
                'actions': []}
    rows = [_row(8, 'battle', entry_level,
                 {'spend': {'levelup': 0, 'buys': {}}}),
            _row(9, 'boss', last_own_level or entry_level, {})]
    if last_is_sim:
        rows[1]['sim']['spend'] = {'levelup': 0, 'buys': {}}
    rows[1]['actions'] = [{'__type__': 'LevelUp', 'cost': 4}
                          for _ in range(last_clicks)]
    return rows


def test_d12_flags_plane_last_overspend():
    """超上限命中:25 击 > lv8 整买上限 18 击 → 恰一条,上限/入口级入证据。"""
    entries = d12_plane_last_xp_overspend(_sim_rows(8, 25))
    assert len(entries) == 1
    e = entries[0]
    assert (e['plane'], e['round_num']) == (1, 9)
    assert e['evidence']['clicks'] == 25
    assert e['evidence']['cap_clicks'] == -(-XP_TO_NEXT_LEVEL[8] // 4)
    assert e['evidence']['entry_level'] == 8


def test_d12_silent_when_within_cap_or_not_last_round():
    """恰达上限(18 击)与超击非末轮:零条目(对账型零误报)。"""
    assert d12_plane_last_xp_overspend(
        _sim_rows(8, -(-XP_TO_NEXT_LEVEL[8] // 4))) == []


def test_d12_entry_level_by_row_shape():
    """入口等级按行形状分派:sim 行=前行轮末值;合并行=本行轮首帧值。

    生产合并行 state.level 是轮首帧值(=入口本级),若误用 sim 行携带
    口径会取到上一轮的入口级、需求上限偏小(误报方向),故分派锁死。
    """
    # sim 行:入口 = 前一行轮末值 9 → entry=9(本行轮末值同 9 级无推进)
    e = d12_plane_last_xp_overspend(
        _sim_rows(9, 25, last_is_sim=True, last_own_level=9))
    assert len(e) == 1 and e[0]['evidence']['entry_level'] == 9
    # 合并行:入口 = 本行轮首帧值 8(前行轮末 9 仅携带,不入判)→ entry=8
    e = d12_plane_last_xp_overspend(
        _sim_rows(9, 25, last_is_sim=False, last_own_level=8))
    assert len(e) == 1 and e[0]['evidence']['entry_level'] == 8
