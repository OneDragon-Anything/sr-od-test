"""货币战争 GameState 模型(cw_state)测试 —— 纯逻辑,不依赖游戏。

D-78 加法块:strategy/13 §13.2 补字段(match_type/plane_modifiers/shop_locked/
active_strategies/megastar_char/partner_char)+ BenchChar.equips + current_boss 派生。
均 None/空兜底(OCR 未接→安全降级),零行为变化。
⚖️ NodeInfo/node_path 已随死字段删除(2026-08-16 review D3:0 写 0 读;节点序列
由 cw_node_reader.NodeSlot 承载)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    _bench_char_cost,
    sell_refund,
)


def test_new_fields_default_none_or_empty() -> None:
    """D-78 新字段默认值:None / 空容器(OCR 未接 → 安全降级,不编默认值)。"""
    s = GameState()
    assert s.match_type is None
    assert s.plane_modifiers == []
    assert s.shop_locked is False
    assert s.active_strategies == []
    assert s.megastar_char is None
    assert s.partner_char is None


def test_bench_char_equips_default() -> None:
    """BenchChar(= Unit)新 equips 字段默认空列表(身上装备,有序;OCR 未接 → 空)。"""
    bc = BenchChar(slot=0)
    assert bc.equips == []
    bc.equips = ["反重力皮靴", "冷笑话引擎"]
    assert bc.equips == ["反重力皮靴", "冷笑话引擎"]


def test_current_boss_derived_from_plane() -> None:
    """current_boss 派生 = bosses[plane-1];无 boss / 越界 → None(strategy/13 §13.2)。"""
    s = GameState(plane_bosses=["电视机", "琥珀王", "盗火行者"])

    s.plane = 1
    assert s.current_boss == "电视机"
    s.plane = 2
    assert s.current_boss == "琥珀王"
    s.plane = 3
    assert s.current_boss == "盗火行者"

    # 越界 → None
    s.plane = 4
    assert s.current_boss is None

    # 无 boss 数据 → None
    empty = GameState(plane_bosses=[], plane=1)
    assert empty.current_boss is None


def test_additive_change_zero_behavior_regression() -> None:
    """D-78 加法块不改变既有字段/行为:旧构造 + 既有方法照常。"""
    s = GameState(gold=50, level=5, plane=2, hp=80)
    assert s.gold == 50 and s.level == 5 and s.plane == 2 and s.hp == 80
    assert s.max_units() == 5
    s2 = s.copy()
    assert s2.gold == 50 and s2 is not s


def test_mutate_bench_deployed_buy_merge_sell_deploy() -> None:
    """task#105 ``mutate_bench_deployed``:运行时就地同步 bench/deployed(buy+merge / sell / deploy;D-129/D-130)。

    转移规则与 ``simulate`` 一致(单一源);与 simulate 的区别 = 就地改 vs copy(前瞻)。
    ADR-0316 槽位语义:bench 定长 9 空槽表——buy 落首个空槽/sell+deploy 置 None/
    占用数守恒;断言用 ``iter_occupied``/``bench_occupied``(禁 len(bench))。
    """
    from sr_od.application.currency_war.cw_state import (
        BuyCard,
        DeployMove,
        LevelUp,
        SellBench,
        ShopCard,
        bench_occupied,
        iter_occupied,
        mutate_bench_deployed,
    )
    bench: list = []
    deployed: list[BenchChar] = []
    mutate_bench_deployed(bench, deployed, LevelUp(cost=4))   # 入口 pad 9 槽
    assert len(bench) == 9 and bench_occupied(bench) == 0

    # buy 同名 3 张 → _merge_bench 3合1 升星(star1→star2),腾 2 槽
    for _ in range(3):
        mutate_bench_deployed(bench, deployed, BuyCard(ShopCard(x=0, name="姬子", faction="追击")))
    assert bench_occupied(bench) == 1
    first = next(iter_occupied(bench))
    assert first.char_id == "姬子"
    assert first.star == 2  # 3 合 1 → star+1

    # buy 异名 → 不 merge(落空槽)
    mutate_bench_deployed(bench, deployed, BuyCard(ShopCard(x=1, name="阿雅", faction="击破")))
    assert bench_occupied(bench) == 2
    assert [b.char_id for b in iter_occupied(bench)] == ['姬子', '阿雅']

    # deploy bench[1](阿雅)→ 槽位置 None + deployed append + position_pref 记实际站位
    mutate_bench_deployed(bench, deployed, DeployMove(bench_idx=1, to_row="front", faction="击破"))
    assert bench_occupied(bench) == 1 and bench[0].char_id == "姬子"
    assert len(deployed) == 1 and deployed[0].char_id == "阿雅"
    assert deployed[0].position_pref == "front"

    # sell bench[0](姬子)→ 槽清空;deployed 不受 sell 影响
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=0))
    assert bench_occupied(bench) == 0
    assert len(deployed) == 1

    # LevelUp / RefreshShop / PickEvent 不影响 bench/deployed → no-op
    before = (bench_occupied(bench), len(deployed))
    mutate_bench_deployed(bench, deployed, LevelUp(cost=4))
    assert (bench_occupied(bench), len(deployed)) == before

    # 越界 idx 安全 no-op(deploy/sell 不崩);空槽 sell 同 no-op
    mutate_bench_deployed(bench, deployed, DeployMove(bench_idx=99, to_row="back", faction="x"))
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=99))
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=0))
    assert (bench_occupied(bench), len(deployed)) == before


def test_sell_refund_cost_based() -> None:
    """卖出退金 = cost × 合成倍数;手续费仅 star≥2 且 cost≥2(cost=1 exempt;ADR-0121)。

    1星=cost(无合成,免费);2星=cost×3(1费)或 cost×3−1(cost≥2);3星同理 cost×9 / cost×9−1。
    cost=1 全额退(live 实测 2★1费=+3);cost≥2 star≥2 −1(用户「2费开始减1」)。
    """
    # 1星 = cost(各费用,买卖净0 → 免费牌池操纵)
    assert sell_refund(1, 1) == 1
    assert sell_refund(1, 3) == 3
    assert sell_refund(1, 5) == 5
    # 2星:cost=1 全额(无费,live 实测 +3);cost≥2 −1
    assert sell_refund(2, 1) == 3    # 1×3,cost=1 无费(live 实测 万敌 2★1费=+3,ADR-0121)
    assert sell_refund(2, 2) == 5    # 2×3 − 1,cost≥2 减1(用户「2费开始减」)
    assert sell_refund(2, 3) == 8    # 9 − 1
    assert sell_refund(2, 5) == 14   # 15 − 1
    # 3星:cost=1 全额;cost≥2 −1(推测同 2星,待 live 核)
    assert sell_refund(3, 1) == 9    # 1×9,cost=1 无费(同 2星规则)
    assert sell_refund(3, 3) == 26   # 27 − 1
    assert sell_refund(3, 5) == 44   # 45 − 1


def test_bench_char_cost_unknown_defaults_3() -> None:
    """_bench_char_cost:未知 char_id → 默认中费 3(sell_refund 兜底,防身份未识别时崩)。"""
    assert _bench_char_cost(BenchChar(slot=0, char_id="", star=1)) == 3
    assert _bench_char_cost(BenchChar(slot=0, char_id="不存在的角色xyz", star=1)) == 3


# ===== ADR-0129 购买经验模型(单击 +4 XP,攒门槛升级,溢出结转) =====
def test_simulate_level_up_accumulates_xp() -> None:
    """一次 LevelUp = +4 XP(单击),不直接升级;经验条同步推进。"""
    from sr_od.application.currency_war.cw_state import LevelUp, simulate
    s = GameState(level=5, gold=40, xp_progress=(0, 20), hp=100)
    s2 = simulate(s, LevelUp(cost=4))
    assert s2.level == 5, "4/20 未到门槛,不应升级"
    assert s2.xp_progress == (4, 20)
    assert s2.gold == 36


def test_simulate_level_up_crosses_threshold_with_carryover() -> None:
    """18/20 时点 1 次(22 XP)→ 升到 6 级,溢出 2 结转(2/40,用户门槛表)。"""
    from sr_od.application.currency_war.cw_state import LevelUp, simulate
    s = GameState(level=5, gold=40, xp_progress=(18, 20), hp=100)
    s2 = simulate(s, LevelUp(cost=4))
    assert s2.level == 6
    assert s2.xp_progress == (2, 40)


def test_simulate_level_up_xp_unknown_starts_zero() -> None:
    """xp 未知(None)按 0 进度起步 —— 保守(多估所需击数,不虚报升级)。"""
    from sr_od.application.currency_war.cw_state import LevelUp, simulate
    s = GameState(level=3, gold=10, xp_progress=None, hp=100)
    s2 = simulate(s, LevelUp(cost=4))
    assert s2.level == 4, "lv3 门槛 4,一击 +4 恰好升级"
    assert s2.xp_progress == (0, 6)

