"""sim 重做 S8(M19 难度/M20 boss/M21 特殊角色/M10 装备)回归锁。

设计正本 = ``docs/develop/sr_od/application/currency_war/changes/
2026-09-15-sim-redesign/design.md``;锁面 = U25 难度定谳成分与基础
None 披露/U02 boss 池采样与覆盖优先/U26 银狼升费口径与开拓者形态/
M10 穿着即合成·扳手回区·冶金炉同类型重掷。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENTS,
    get_equip,
)
from sr_od.application.currency_war.data.cw_synthesis import (
    CROSS_RECIPES,
    synthesize_target,
)
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    bench_view_of_slots,
    register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    PrecisionWrenchUse,
    WearEquip,
    WrenchUse,
)
from sr_od.application.currency_war.sim.cw_sim_enemy import (
    BOSS_DEDUP_PENDING,
    DIFFICULTY_BASE_PENDING_U25,
    HOLY_GRAIL_BONUS,
    difficulty_of,
    resolve_plane_bosses,
)
from sr_od.application.currency_war.sim.cw_sim_equips import (
    WEAR_LIMIT,
    apply_furnace_equip_mode,
    apply_precision_wrench,
    apply_wear_equip,
    apply_wrench,
    furnace_reroll,
)
from sr_od.application.currency_war.sim.cw_sim_special import (
    SILVER_WOLF_COST_BY_STAR,
    SILVER_WOLF_ID,
    planner_overlay_due,
    silver_wolf_effective_cost,
    trailblazer_form_of,
)

register_sig_actors('TestSigWriter')

_SIG = ChannelSig(family='obs', actor='TestSigWriter')


def _gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _gs_with_bench_unit(char_id: str, equips: list[str] | None = None,
                        slot: int = 1) -> GameState:
    """容器 + 备战席单角色(0 基槽表下标 = slot−1;BenchChar 形状经
    bench_view_of_slots 转容器视图,r1 S1 同构)。"""
    gs = _gs()
    slots: list[BenchChar | None] = [None] * 9
    slots[slot - 1] = BenchChar(slot=slot, char_id=char_id, faction='散',
                                star=1, equips=list(equips or []))
    gs.observe(gs.bench, bench_view_of_slots(slots), sig=_SIG)
    return gs


def _worn_of(gs: GameState, char_id: str) -> list[str]:
    """读角色 worn 表(测试断言辅助;bench 视图单角色场景)。"""
    for s in gs.bench.value.slots:
        if (s is not None and s.kind == 'unit' and s.unit is not None
                and s.unit.char_id == char_id):
            return list(s.unit.equips)
    raise AssertionError(f'{char_id} 不在席')


def _advance_pair() -> tuple[str, str, str]:
    """取一对真配方(组件A, 组件B, 进阶产物)(注册表单一源取用)。"""
    advance, (a, b) = next(iter(CROSS_RECIPES.items()))
    return a, b, advance


# ============================================================ M19 难度

def test_difficulty_known_components_and_base_none_u25() -> None:
    """U25:定谳成分(品质彩6/遭遇档20/伟大征服连胜项)逐项可算;
    基础曲线未采 → base=None 且 total=None(禁插值不出合计)。"""
    d = difficulty_of(['伟大征服'], node_kind='encounter', streak=2,
                      encounter_tier=3, base=None)
    assert d.base is None and d.total is None
    assert d.quality_bonus == 6, '伟大征服 = 棱彩档 +6(注册表 rarity)'
    assert d.encounter_tier_bonus == 20, '第三档 = 20'
    assert d.special_bonus == 2, 'difficulty_per_streak=1 × streak=2'
    assert d.strategy_delta == 0
    assert DIFFICULTY_BASE_PENDING_U25


def test_difficulty_total_with_base_and_node_scoped_delta() -> None:
    """base 可传(局级输入档):total = base + 定谳成分;难度修改器
    (−4,遭遇+首领限定)只在遭遇/首领节点计入。"""
    d_battle = difficulty_of(['难度修改器'], node_kind='battle',
                             streak=0, base=100)
    assert d_battle.strategy_delta == 0, '战斗节点不计节点型限定 Δ'
    assert d_battle.total == 100
    d_enc = difficulty_of(['难度修改器'], node_kind='encounter',
                          streak=0, base=100)
    assert d_enc.strategy_delta == -4 and d_enc.total == 96
    d_simple = difficulty_of(['简单模式'], node_kind='battle',
                             streak=0, base=100)
    assert d_simple.strategy_delta == -3, '无限定 Δ 恒计入'


def test_difficulty_holy_grail_constant_pending() -> None:
    """圣杯 +30 定谳真值在册;激活态占位(首版恒未激活)。"""
    d_off = difficulty_of([], node_kind='battle', streak=0, base=50)
    assert d_off.special_bonus == 0
    d_on = difficulty_of([], node_kind='battle', streak=0, base=50,
                         holy_grail_active=True)
    assert d_on.special_bonus == HOLY_GRAIL_BONUS == 30


# ============================================================ M20 boss

def test_plane_boss_override_priority_and_pool_membership() -> None:
    """U02:RunConfig 覆盖位优先;None 位 → 内置池采样(池 = boss 机制
    注册表键集)。"""
    from sr_od.application.currency_war.data.cw_enemy_data import (
        BOSS_MECHANICS,
    )
    picked = resolve_plane_bosses(
        ('造梦兄弟影业', None, '灰手生命科技'), random.Random(1))
    assert picked[0] == '造梦兄弟影业' and picked[2] == '灰手生命科技'
    assert picked[1] in BOSS_MECHANICS
    full_sampled = resolve_plane_bosses(None, random.Random(2))
    assert all(b in BOSS_MECHANICS for b in full_sampled)
    assert BOSS_DEDUP_PENDING  # 去重语义占位披露键在册


# ============================================================ M21 特殊角色

def test_silver_wolf_cost_by_star_and_front_gate() -> None:
    """U26:2星→4费、3星(5费线)→5费;备战栏不升费(恒基础 3 费);
    非银狼 → None 非本辖域。"""
    assert SILVER_WOLF_COST_BY_STAR == {1: 3, 2: 4, 3: 5}
    assert silver_wolf_effective_cost(SILVER_WOLF_ID, 2, on_front=True) == 4
    assert silver_wolf_effective_cost(SILVER_WOLF_ID, 3, on_front=True) == 5
    assert silver_wolf_effective_cost(SILVER_WOLF_ID, 2, on_front=False) == 3
    assert silver_wolf_effective_cost('淘金客', 2, on_front=True) is None


def test_planner_overlay_due_on_first_two_star() -> None:
    """「我来当策划」触发判据:银狼升达 2 星的合成事件(1→2);
    非 2 星跨越/非银狼不触发。"""
    assert planner_overlay_due(SILVER_WOLF_ID, 1, 2)
    assert not planner_overlay_due(SILVER_WOLF_ID, 2, 3)
    assert not planner_overlay_due('淘金客', 1, 2)


def test_trailblazer_form_routing() -> None:
    """开拓者双形态按排路由(front=记忆/back=欢愉);非开拓者原样。"""
    assert trailblazer_form_of('开拓者', 'front') == '开拓者·记忆'
    assert trailblazer_form_of('开拓者', 'back') == '开拓者·欢愉'
    assert trailblazer_form_of('淘金客', 'front') == '淘金客'


# ============================================================ M10 装备

def test_wear_equip_triggers_wear_synthesis() -> None:
    """穿着即合成(sim 补齐 kernel 视觉域零写面):穿第二件基础件 →
    worn 内两件立即合成进阶件;owned 扣减。"""
    a, b, advance = _advance_pair()
    assert synthesize_target(a, b) == advance
    gs = _gs_with_bench_unit('淘金客', equips=[a])
    gs.observe(gs.equips, [b], sig=_SIG)
    action = WearEquip(item_name=b, char_name='淘金客', row='front', slot=1)
    assert apply_wear_equip(gs, action)
    assert _worn_of(gs, '淘金客') == [advance], \
        f'穿着即合成:{a}+{b} → {advance}'
    assert gs.equips.value == [], '库存件已穿上'


def test_wear_equip_rejects_unknown_item_or_char() -> None:
    """拒绝形态:owned 无该件 / 目标角色不在册 → False(动作未生效)。"""
    a, _b, _adv = _advance_pair()
    assert not apply_wear_equip(
        _gs_with_bench_unit('淘金客'),
        WearEquip(item_name=a, char_name='淘金客', row='front', slot=1)), \
        'owned 空库拒'
    assert not apply_wear_equip(
        _gs_with_bench_unit('淘金客'),
        WearEquip(item_name=a, char_name='不存在的角色',
                  row='front', slot=1)), '角色不在册拒'


def test_wrench_returns_equips_and_consumes() -> None:
    """拆装扳手:取下全部穿戴回装备区(归属面回区);工具消耗。

    坐标系 = cw_vocab 通用声明:row/slot = 板面物理排(扳手射程 =
    上阵单位;穿戴域读点 = front_row/back_row 容器域)。"""
    a, _b, _adv = _advance_pair()
    gs = _gs()
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    gs.observe(gs.front_row, [Unit(char_id='淘金客', star=1, equips=[a])],
               sig=_SIG)
    gs.observe(gs.equips, ['拆装扳手'], sig=_SIG)
    assert apply_wrench(gs, WrenchUse(row='front', slot=1))
    assert gs.equips.value == [a], '穿戴回区'
    assert gs.front_row.value[0].equips == [], 'worn 已清空'


def test_precision_wrench_no_consumption() -> None:
    """精密扳手:同取下但库存不递减(无限次用);坐标系同扳手。"""
    a, _b, _adv = _advance_pair()
    gs = _gs()
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    gs.observe(gs.front_row, [Unit(char_id='淘金客', star=1, equips=[a])],
               sig=_SIG)
    gs.observe(gs.equips, ['精密拆装扳手'], sig=_SIG)
    assert apply_precision_wrench(gs, PrecisionWrenchUse(row='front', slot=1))
    assert gs.equips.value == ['精密拆装扳手', a]


def test_furnace_same_category_reroll() -> None:
    """冶金炉(效果原文有档):同类型(同 category)随机重掷,排除
    自身;库存无该件 → 拒。"""
    simple = sorted(n for n, e in EQUIPMENTS.items()
                    if e.category == '简易')
    assert simple, '注册表应有简易件'
    src = simple[0]
    new_name = furnace_reroll(random.Random(3), src)
    assert new_name != src
    assert get_equip(new_name).category == '简易'
    gs = _gs()
    gs.observe(gs.equips, [src], sig=_SIG)
    out = apply_furnace_equip_mode(gs, src, rng=random.Random(4))
    assert out == new_name
    assert gs.equips.value == [new_name]
    assert apply_furnace_equip_mode(gs, '不存在的装备',
                                    rng=random.Random(5)) is None


def test_wear_limit_constant_truth() -> None:
    """角色穿戴上限 3 件(equipment_mechanics.md 定谳)。"""
    assert WEAR_LIMIT == 3
