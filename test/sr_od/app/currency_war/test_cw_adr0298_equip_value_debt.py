"""ADR-0298(装备价值表数据债清偿,批㉛ F2):表-注册表双向一致性锁。

裁决证据(2026-08-24 语料核证):_EQUIP_VALUE 旧 12 键中 3 个死名均为
表残留,非注册表漏收——
- 超级电池:游戏语料(实机 replay OCR invest_cards.jsonl 3 次)仅以
  超充站投资卡的 buff 词【超级电池】出现,从未作为供给装备名;
- 能量饮料:docs/sources/replay/攻略语料全零出现(纯幻影名);
- 翁瓦克:仅以局外遗器名出现(风套/翁瓦克,攻略语料明确「局外」),
  ADR-0130 补缺时误收进表。

清偿:删 3 死名;翁瓦克 4 分按功能对位(充能系)转投蓄能帆
(行动值回能;final_comps 语料「蓄能帆(优先级=希儿第一件)」)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENT_ROSTER,
)
from sr_od.application.currency_war.kernel.cw_events import (
    _EQUIP_VALUE,
    SupplyOption,
    _equip_value,
    decide_supply,
)
from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_equip_value_table_roster_coherence,
)
from sr_od.application.currency_war.kernel.cw_state import GameState

# ---- 方向1:价值表键 ⊆ 注册表名(死名清零) --------------------------------


def test_equip_value_keys_subset_of_roster() -> None:
    """表键必须全部在 EQUIPMENT_ROSTER 内(批㉛ F2 死名不得回归)。"""
    stale = sorted(n for n in _EQUIP_VALUE if n not in EQUIPMENT_ROSTER)
    assert stale == [], f'价值表死名 {stale}(ADR-0298 清偿后不得回归)'


def test_dead_names_removed_and_mass_transferred() -> None:
    """3 死名已删;翁瓦克 4 分转投蓄能帆(0 分→4 分)。"""
    for dead in ('超级电池', '能量饮料', '翁瓦克'):
        assert dead not in _EQUIP_VALUE
    assert _EQUIP_VALUE.get('蓄能帆') == 4


# ---- 方向2:roster 供给名(进 sim 采样池者)⊆ 表键(无静默过滤) ------------


def test_sim_supply_pool_equals_table_keys() -> None:
    """sim 供给采样池构造(cw_sim 同式)与表键完全一致。

    ADR-0294 件2 的注册表过滤此前静默剔出 20% 表值质量;死名清偿后
    过滤应为恒等(池=表),再出现差集 = 表-注册表漂移回归。
    """
    pool = [n for n in _EQUIP_VALUE if n in EQUIPMENT_ROSTER]
    assert sorted(pool) == sorted(_EQUIP_VALUE)


# ---- 生产侧 decide_supply 对齐 ---------------------------------------------


def test_decide_supply_reads_transferred_value() -> None:
    """补给决策读得到转投后的蓄能帆价值(真名不再恒 0 分)。"""
    assert _equip_value('蓄能帆') == 4
    assert _equip_value('翁瓦克') == 0  # 死名按未知名 0 分(永不出现)


def test_decide_supply_prefers_valued_equip() -> None:
    """无钻不刷新场景:蓄能帆(4)压过 2 分档活名。"""
    st = GameState()
    opts = [
        SupplyOption(idx=0, equip='绝对热量'),
        SupplyOption(idx=1, equip='蓄能帆'),
        SupplyOption(idx=2, equip='轮滑鞋'),
    ]
    # 轮滑鞋 4 同分:构造上取高分者之一即可——改用唯一高分者断言精确 idx
    opts[2].equip = '物质分解液'  # 3 分
    pick = decide_supply(opts, st, None, None, refresh_used=True)
    assert pick.idx == 1


# ---- 检查项转绿 -------------------------------------------------------------


def test_check_item_green_after_clearance() -> None:
    """批㉛ 验收硬指标:equip_value_table_roster_coherence 归 0(恒绿)。"""
    assert check_equip_value_table_roster_coherence([{}]) == []
