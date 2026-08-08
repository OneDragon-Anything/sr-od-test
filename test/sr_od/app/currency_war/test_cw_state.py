"""货币战争 GameState 模型(cw_state)测试 —— 纯逻辑,不依赖游戏。

D-78 加法块:strategy/13 §13.2 补字段(node_path/match_type/plane_modifiers/shop_locked/
active_strategies/megastar_char/partner_char)+ NodeInfo 类型 + BenchChar.equips + current_boss 派生。
均 None/空兜底(OCR 未接→安全降级),零行为变化。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import BenchChar, GameState, NodeInfo


def test_new_fields_default_none_or_empty() -> None:
    """D-78 新字段默认值:None / 空容器(OCR 未接 → 安全降级,不编默认值)。"""
    s = GameState()
    assert s.node_path == []
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


def test_node_info_defaults() -> None:
    """NodeInfo(node_path 元素)默认 type 空 / status future(未接 OCR 时)。"""
    ni = NodeInfo()
    assert ni.type == ""
    assert ni.status == "future"
    typed = NodeInfo(type="boss", status="current")
    assert typed.type == "boss" and typed.status == "current"


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
    """
    from sr_od.application.currency_war.cw_state import (
        BuyCard, DeployMove, LevelUp, SellBench, ShopCard, mutate_bench_deployed,
    )
    bench: list[BenchChar] = []
    deployed: list[BenchChar] = []

    # buy 同名 3 张 → _merge_bench 3合1 升星(star1→star2)
    for _ in range(3):
        mutate_bench_deployed(bench, deployed, BuyCard(ShopCard(x=0, name="姬子", faction="追击")))
    assert len(bench) == 1
    assert bench[0].char_id == "姬子"
    assert bench[0].star == 2  # 3 合 1 → star+1

    # buy 异名 → 不 merge(append)
    mutate_bench_deployed(bench, deployed, BuyCard(ShopCard(x=1, name="阿雅", faction="击破")))
    assert len(bench) == 2
    assert bench[1].char_id == "阿雅" and bench[1].star == 1

    # deploy bench[1](阿雅)→ bench pop + deployed append + position_pref 记实际站位
    mutate_bench_deployed(bench, deployed, DeployMove(bench_idx=1, to_row="front", faction="击破"))
    assert len(bench) == 1 and bench[0].char_id == "姬子"
    assert len(deployed) == 1 and deployed[0].char_id == "阿雅"
    assert deployed[0].position_pref == "front"

    # sell bench[0](姬子)→ bench 空;deployed 不受 sell 影响
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=0))
    assert bench == []
    assert len(deployed) == 1

    # LevelUp / RefreshShop / PickEvent 不影响 bench/deployed → no-op
    before = (len(bench), len(deployed))
    mutate_bench_deployed(bench, deployed, LevelUp(cost=4))
    assert (len(bench), len(deployed)) == before

    # 越界 idx 安全 no-op(deploy/sell 不崩)
    mutate_bench_deployed(bench, deployed, DeployMove(bench_idx=99, to_row="back", faction="x"))
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=99))
    assert (len(bench), len(deployed)) == before
