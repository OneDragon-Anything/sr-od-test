"""货币战争 CwWorkFrame 模型(cw_state)核不变量测试 —— 纯逻辑,不依赖游戏。

覆盖面(#3 目标形态):mutate 不变量(buy+merge/sell/deploy,占用数守恒)/
deploy 抽象(deployed_place 信息位归一)/双轨代表(mutate 就地 vs simulate
copy:跨门槛溢出结转 + xp 未知保守起步)/金钱不变量(sell_refund 退金表
+ 未知身份 cost 兜底 3)/registry 锚(xp 点击阶梯校准登记门)。

来源:test_cw_state.py(现名保留,零断言改动)。其余历史锁已退役
(git 可复活)。

D-78 加法块:strategy/13 §13.2 补字段(match_type/plane_modifiers/shop_locked/
active_strategies/megastar_char/partner_char)+ BenchChar.equips。
⚖️ NodeInfo/node_path 已随死字段删除(2026-08-16 review D3:0 写 0 读;节点序列
由 cw_node_reader.NodeSlot 承载)。
⚖️ 覆盖对账(2026-09-08 瘦身批,亲读生产消费面):新字段缺省测与
current_boss 派生测删除——shop_locked/plane_modifiers/megastar_char/
partner_char/match_type 生产零读、current_boss 属性零消费(未接线代码
不立锁);字段/属性 src 侧删除候选挂 DEBTS.md D32。xp 累积面由
test_cw_fake_game 升级测承载(FakeMatch.apply 直调 simulate 单一源)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    CwWorkFrame,
    bench_char_cost,
    sell_refund,
    xp_clicks_to_level,
)


def test_mutate_bench_deployed_buy_merge_sell_deploy() -> None:
    """task#105 ``mutate_bench_deployed``:运行时就地同步 bench/deployed(buy+merge / sell / deploy;D-129/D-130)。

    转移规则与 ``simulate`` 一致(单一源);与 simulate 的区别 = 就地改 vs copy(前瞻)。
    ADR-0316 槽位语义:bench 定长 9 空槽表——buy 落首个空槽/sell+deploy 置 None/
    占用数守恒;断言用 ``iter_occupied``/``bench_occupied``(禁 len(bench))。
    """
    from sr_od.application.currency_war.kernel.cw_vocab import (
        BuyCard,
        DeployMove,
        LevelUp,
        SellBench,
        ShopCard,
        bench_occupied,
        deployed_occupied,
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
    assert deployed_occupied(deployed) == 1 and deployed[0].char_id == "阿雅"
    assert deployed[0].position_pref == "front"   # ADR-0392 占用数(表定长 10)

    # sell bench[0](姬子)→ 槽清空;deployed 不受 sell 影响
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=0))
    assert bench_occupied(bench) == 0
    assert deployed_occupied(deployed) == 1

    # LevelUp / RefreshShop / PickEvent 不影响 bench/deployed → no-op
    before = (bench_occupied(bench), deployed_occupied(deployed))
    mutate_bench_deployed(bench, deployed, LevelUp(cost=4))
    assert (bench_occupied(bench), deployed_occupied(deployed)) == before

    # 越界 idx 安全 no-op(deploy/sell 不崩);空槽 sell 同 no-op
    mutate_bench_deployed(bench, deployed, DeployMove(bench_idx=99, to_row="back", faction="x"))
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=99))
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=0))
    assert (bench_occupied(bench), deployed_occupied(deployed)) == before


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
    """bench_char_cost:未知 char_id → 默认中费 3(sell_refund 兜底,防身份未识别时崩)。"""
    assert bench_char_cost(BenchChar(slot=0, char_id="", star=1)) == 3
    assert bench_char_cost(BenchChar(slot=0, char_id="不存在的角色xyz", star=1)) == 3


# ===== ADR-0129 购买经验模型(单击 +4 XP,攒门槛升级,溢出结转) =====
# 累积面(未跨门槛一击 +XP_PER_BUY/金扣减)由 test_cw_fake_game
# 升级测承载(FakeMatch.apply 直调 cw_state.simulate 单一源,断言面
# 超集,覆盖对账后本文件单测删除);本文件保留跨门槛溢出结转与
# xp 未知起步两个独家分支。

def test_simulate_level_up_crosses_threshold_with_carryover() -> None:
    """18/20 时点 1 次(22 XP)→ 升到 6 级,溢出 2 结转(2/40,用户门槛表)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import LevelUp, simulate
    s = CwWorkFrame(level=5, gold=40, xp_progress=(18, 20), hp=100)
    s2 = simulate(s, LevelUp(cost=4))
    assert s2.level == 6
    assert s2.xp_progress == (2, 40)


def test_simulate_level_up_xp_unknown_starts_zero() -> None:
    """xp 未知(None)按 0 进度起步 —— 保守(多估所需击数,不虚报升级)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import LevelUp, simulate
    s = CwWorkFrame(level=3, gold=10, xp_progress=None, hp=100)
    s2 = simulate(s, LevelUp(cost=4))
    assert s2.level == 4, "lv3 门槛 4,一击 +4 恰好升级"
    assert s2.xp_progress == (0, 6)


def test_levelup_clicks_ladder_matches_registry() -> None:
    """购买经验点击数阶梯:lv5→8 = 5/10/13/18(ceil(need/XP_PER_BUY))。

    手值梯 = 校准登记门(门槛表/每击经验常量本身即校准对象,不可自
    推导):常量或公式改动必红,登记新门槛表后跟绿。注册表常量面
    (XP_PER_BUY==4 / XP_TO_NEXT_LEVEL[5]==20)由 test_cw_economy
    承载,不双锁。
    自 test_cw_w502_deathbed_levelup_ev ①(P21 批;w502 ②③④ 为
    math_proofs P21 已证命题的镜像复算,已退役——证明单篇
    docs/game/currency_war/research/proofs/p21-p2-deathbed-levelup-ev.md
    + tools/cw/proofs/ 可重跑脚本承载,测试不再镜像复算)。
    W490 ⑰ P2r2 实测帧:LevelUp×13、87→37 金、lv7→8 —— 与 c=4 的
    C=52 吻合,作为实测锚保留。
    """
    assert [xp_clicks_to_level(lv, 0) for lv in (5, 6, 7, 8)] == [5, 10, 13, 18]


# ===== ADR-0392 deployed 槽位信息位归一(T-180 写端治本;ADR-0605 §5.2)=====

def test_deployed_place_normalizes_pref_and_slot_to_authoritative_idx() -> None:
    """deployed_place 信息位归一锁:放置时 position_pref/slot 恒与实际
    落位下标一致(权威槽位 = 下标,信息位为派生)。①首选排内落位 pref
    保持;②首选排满兜底跨排时 pref 随落位改写——错位形态(pref='front'
    而物理槽在后排)对 sell_recorded 解析键 deployed_idx→(排,槽号) 固定
    双射恒漏匹配,卖出件误归 unexplained(端到端锁 =
    test_cw_departures.test_departure_sell_recorded_pref_fallback_);
    ③无空槽返回 None 且不写信息位。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        DEPLOYED_CAPACITY,
        DEPLOYED_FRONT_CAPACITY,
        deployed_place,
        deployed_slot_no,
    )
    deployed: list[BenchChar | None] = []
    for i in range(DEPLOYED_FRONT_CAPACITY):   # ① front 落前排:pref 保持
        bc = BenchChar(slot=0, char_id=f'前排{i}', star=1,
                       position_pref='front')
        assert deployed_place(deployed, bc) == i
        assert (bc.position_pref, bc.slot) == ('front', i + 1)
    tail = BenchChar(slot=0, char_id='尾件', star=1, position_pref='front')
    assert deployed_place(deployed, tail) == DEPLOYED_FRONT_CAPACITY
    assert (tail.position_pref, tail.slot) == \
        ('back', deployed_slot_no(DEPLOYED_FRONT_CAPACITY))   # ② 兜底改写
    b_tail = BenchChar(slot=0, char_id='背件', star=1, position_pref='back')
    assert deployed_place(deployed, b_tail) == DEPLOYED_FRONT_CAPACITY + 1
    assert (b_tail.position_pref, b_tail.slot) == \
        ('back', deployed_slot_no(DEPLOYED_FRONT_CAPACITY + 1))
    full = [BenchChar(slot=1, char_id=f'X{i}', star=1)
            for i in range(DEPLOYED_CAPACITY)]
    rejected = BenchChar(slot=0, char_id='溢出', star=1)
    assert deployed_place(full, rejected) is None   # ③ 满表拒放
    assert (rejected.position_pref, rejected.slot) == ('back', 0)

