"""sim 采样与候选生成回归测试(投资 offer M02/M11 + 派生池与商店发牌
M06/M05 + 节点选项生成 M16/M17/M18)。

测试面:
- 投资 offer:U07 固定日程(P1r3/P2r2/P3r2 + 联席决策 2-6 额外槽)/
  U07③ 候选结构(品质→池取样、offer 内去重、全程不重复)/U08 环境
  offer 同构 3 选 1/品质分布显式常量占位。选卡入账腿 = kernel 获得链
  (测试面迁 test_sim_backend.py,注入核随退役删除);品质改写已接入
  三选一抽样(判据测试 rewrite_quality_for_pick 只接全改写型 + kernel
  游戏事实名单一致性测试;「未建模」披露键已退役,名单常量位仍 =
  kernel cw_investments);
- 派生池与发牌:副本数真值(27/27/9/9/9)/held 星级派生不变量/≥9 清空
  发牌过滤(U11)与双出口分野/专家入池假设(U10)/5 槽发牌与概率表/
  免费刷先行(M05);
- 节点选项:U22 遭遇档位结构/扑满替换单一源(两卡同构参数化)+ 面板矿
  占位增量登记闸(ENV_ORE_PANEL_BONUS 手抄锁值)/U24·T-9 补给 3 选 1
  基础件放回均匀 + 带钻占位 + 环境每列件数表(ENV_SUPPLY_EQUIP_COUNT)。
  pick 动作入账腿退役(测试面迁 test_sim_backend.py:选卡走 op → 上报
  函数族获得链,与实机同构);遭遇加成真值表归宿 = cw_sim_enemy(难度
  账域)。
"""
from __future__ import annotations

import random

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_bview,
)

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTERS,
    chars_by_cost,
)
from sr_od.application.currency_war.data.cw_shop_odds import (
    POOL_COPIES_PER_CARD,
    REFRESH_PROB,
)
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_refresh_shop_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ORE_PANEL_BONUS,
    ENV_POOL_REWRITE,
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    QUALITY_REWRITE_ENV_NAMES,
)
from sr_od.application.currency_war.kernel.cw_pool import (
    EXPERT_COPIES_ASSUMED,
    drawable_names,
    fixed_pool,
    grant_bucket_names,
    held_copies,
    remaining_pool,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionRefreshShopParam,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    INVEST_OFFER_SCHEDULE,
    JOINT_DECISION_ENV_NAME,
    OFFER_CANDIDATES,
    ROTATION_ASSUMPTION_DISCLOSURE,
    deal_shop,
    effective_deal_probs,
    encounter_options,
    is_piggy_node,
    offer_slots,
    rewrite_quality_for_pick,
    sample_env_offer,
    sample_strategy_offer,
    supply_options,
)
from sr_od.application.currency_war.sim.cw_sim_enemy import (
    ENCOUNTER_TIER_BONUS,
)
from sr_od.application.currency_war.sim.cw_sim_streams import stream_rng


def _gs(node_kind: str = 'reward') -> GameState:
    """节点事件面容器(节点观察写;is_piggy_node 判定用)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node, NodeKey(plane=1, round_num=7, kind=node_kind),
               sig=ChannelSig(family='obs', actor='TestSigWriter'))
    return gs


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='TestSigWriter',
                      mode='compute')


def _fresh_gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


# ============================================================ 投资 offer:固定日程(U07①)

def test_offer_schedule_fixed_slots_u07() -> None:
    """U07①:固定轮次 P1r3/P2r2/P3r2 各一次;日程外轮无槽。"""
    assert INVEST_OFFER_SCHEDULE == ((1, 3), (2, 2), (3, 2))
    for plane, rnd in INVEST_OFFER_SCHEDULE:
        assert offer_slots(plane, rnd, None)
    for plane, rnd in ((1, 1), (1, 2), (1, 4), (2, 1), (2, 3), (2, 5)):
        assert not offer_slots(plane, rnd, None), (plane, rnd)


def test_joint_decision_extra_slot_env_gated() -> None:
    """联席决策(id122)→ 2-6 额外策略槽;环境不在场无额外槽。"""
    assert not offer_slots(2, 6, None), '无环境时 2-6 无槽'
    assert not offer_slots(2, 6, '轮岗'), '非联席决策环境无额外槽'
    assert offer_slots(2, 6, JOINT_DECISION_ENV_NAME), '联席决策 2-6 额外槽'


# ============================================================ 投资 offer:候选生成(U07③)

def test_strategy_offer_shape_and_lifelong_dedup() -> None:
    """候选 = 3 张、互不重名、全在注册表;排除集(全程去重)同规则
    排除旧选项——刷新重掷不再出已出名(U07③)。"""
    rng = random.Random(20260915)
    excluded: set[str] = set()
    seen: list[str] = []
    for _ in range(40):
        picks = sample_strategy_offer(rng, excluded)
        assert len(picks) == OFFER_CANDIDATES
        assert len(set(picks)) == OFFER_CANDIDATES, 'offer 内去重'
        for name in picks:
            assert name in INVESTMENT_STRATEGIES
            assert name not in excluded, '全程不重复(已出选项不再入 offer)'
            excluded.add(name)
        seen.extend(picks)
    assert len(set(seen)) == len(seen)


def test_strategy_offer_quality_distribution_uniform_placeholder() -> None:
    """品质掷点占位 = 三档均匀(显式常量,候实机回填):n=900 候选下
    各档频率断言 1/3±6σ 宽带(σ=sqrt(p(1-p)/n),禁卡边);三档品质池均有
    产出(频率非零 = 池映射无空档)。

    统计面用逐 offer 独立排除集(只校验 offer 内去重):全程去重累计
    集会在 ~111 个 offer 处吃光 335 张注册表 → 采样不足死等;品质掷点
    分布与排除集大小无关,独立集不影响本测试面(全程去重另测)。
    """
    rng = random.Random(77)
    counts = {'银': 0, '金': 0, '棱彩': 0}
    n = 0
    while n < 900:
        picks = sample_strategy_offer(rng, ())
        assert len(picks) == OFFER_CANDIDATES
        for name in picks:
            counts[INVESTMENT_STRATEGIES[name].rarity] += 1
            n += 1
    for quality, count in counts.items():
        p = count / n
        sigma = (1.0 / 3.0 * 2.0 / 3.0 / n) ** 0.5
        assert abs(p - 1.0 / 3.0) < 6 * sigma, (quality, p)


# ============================================================ 投资 offer:品质改写次抽样(forced_quality)

def test_strategy_offer_forced_quality_targets_pool() -> None:
    """品质改写次抽样(2026-10-14 用户裁定:固定目标品质后照常抽
    3 张):forced_quality='棱彩' → 候选全棱彩注册名 + offer 内去重;
    预置排除集生效(排除名不再出现);多 seed 扫。"""
    prism_names = {n for n, s in INVESTMENT_STRATEGIES.items()
                   if s.rarity == '棱彩'}
    assert prism_names, '注册表棱彩池非空(建表前提)'
    for seed in range(20):
        # 排除集取棱彩池头部两名(现算,非手抄名):校验「排除集在
        # 改写次同样生效」,不断言具体候选值
        banned = set(sorted(prism_names)[:2])
        picks = sample_strategy_offer(random.Random(seed), set(banned),
                                      forced_quality='棱彩')
        assert len(picks) == OFFER_CANDIDATES
        assert len(set(picks)) == OFFER_CANDIDATES, 'offer 内去重'
        for name in picks:
            assert name in INVESTMENT_STRATEGIES and \
                INVESTMENT_STRATEGIES[name].rarity == '棱彩', name
            assert name not in banned, '排除集生效'


def test_strategy_offer_forced_quality_pool_exhausted_falls_back() -> None:
    """防御语义(用户裁定:回退全池契约沿用,不扩防御分支):排除集
    = 全部棱彩名(注册表现算)→ 目标品质池吃光,回退全池(排除后)
    照常发满 3 张;候选必然非棱彩(棱彩名已全部在排除集)。"""
    prism_names = {n for n, s in INVESTMENT_STRATEGIES.items()
                   if s.rarity == '棱彩'}
    picks = sample_strategy_offer(random.Random(7), set(prism_names),
                                  forced_quality='棱彩')
    assert len(picks) == OFFER_CANDIDATES, '池吃光回退全池,如实少发不触发'
    for name in picks:
        assert name in INVESTMENT_STRATEGIES
        assert name not in prism_names, '排除集照常排除(候选必非棱彩)'


def test_strategy_offer_default_regression_forced_empty() -> None:
    """默认局回归:forced_quality='' 与不传参逐值同(同 seed 同排除集
    对拍)——默认局抽样路径零变化。"""
    for seed in range(12):
        ex: set[str] = set(sorted(INVESTMENT_STRATEGIES)[:seed * 3])
        a = sample_strategy_offer(random.Random(seed), set(ex))
        b = sample_strategy_offer(random.Random(seed), set(ex),
                                  forced_quality='')
        assert a == b, seed


def test_env_offer_shape_and_registry_membership() -> None:
    """U08:环境 offer = 3 张占位、互不重名、全在环境注册表;排除集
    生效(同构去重)。"""
    rng = random.Random(4242)
    excluded: set[str] = set()
    for _ in range(20):
        picks = sample_env_offer(rng, excluded)
        assert len(picks) == OFFER_CANDIDATES
        assert len(set(picks)) == OFFER_CANDIDATES
        for name in picks:
            assert name in INVESTMENT_ENVS
            assert name not in excluded
        excluded.update(picks)
    # 排除集吃光剩余池 → 如实少发(防御边界,占位池 83 张实际不可达)
    tiny = sample_env_offer(random.Random(1), set(INVESTMENT_ENVS))
    assert tiny == ()


# ============================================================ 投资 offer:品质改写判据与名单一致性

def test_rewrite_quality_for_pick_full_rewrite_family_only() -> None:
    """品质改写判据(2026-10-14 用户裁定:只接全改写型,判据 =
    rewrite_picks == (1,2,3) 结构特征):时代族命中次返回目标品质
    (彩虹 1/2/3 次 → 棱彩,第 4 次不存在于固定日程但判据仍闭)、
    黄金/白银同构族自动覆盖;部分改写型(头彩 picks=(1,)/尾彩
    picks=(3,))offer 覆盖面歧义未定谳不接入 → None;联席决策无
    rewrite_quality → None;None/空/名单外环境恒 None。"""
    assert rewrite_quality_for_pick('彩虹时代', 1) == '棱彩'
    assert rewrite_quality_for_pick('彩虹时代', 2) == '棱彩'
    assert rewrite_quality_for_pick('彩虹时代', 3) == '棱彩'
    assert rewrite_quality_for_pick('彩虹时代', 4) is None
    assert rewrite_quality_for_pick('黄金时代', 2) == '金'
    assert rewrite_quality_for_pick('白银时代', 3) == '银'
    assert rewrite_quality_for_pick('头彩', 1) is None, '部分改写型不接入'
    assert rewrite_quality_for_pick('尾彩', 3) is None, '部分改写型不接入'
    assert rewrite_quality_for_pick('联席决策', 1) is None, \
        '数量通道无 rewrite_quality'
    for env in (None, '', '轮岗', '经济过热'):
        assert rewrite_quality_for_pick(env, 1) is None, env


def test_quality_rewrite_name_list_subset_of_registry() -> None:
    """游戏事实名单 ⊆ 结构化注册表(防双名单漂移:名单新增环境而
    ENV_POOL_REWRITE 未建条目时,品质改写会静默漏接,本测试红)。"""
    assert set(QUALITY_REWRITE_ENV_NAMES) <= set(ENV_POOL_REWRITE)


# ============================================================ 派生池(M06)

def test_fixed_pool_copies_truth_and_expert_append() -> None:
    """副本数真值(1/2 费 27、3/4/5 费 9,V3.7 收案);专家入池 = U10
    首版假设(同费档追加 9 副本,标注待核);注册表外具名拒收。"""
    pool = fixed_pool()
    assert pool, '固定池非空'
    for name, copies in pool.items():
        assert copies == POOL_COPIES_PER_CARD[CHARACTERS[name].cost], \
            f'{name} 副本数偏离 POOL_COPIES_PER_CARD'
    any_cost1 = chars_by_cost(1)[0].name
    boosted = fixed_pool(extra_experts={any_cost1: EXPERT_COPIES_ASSUMED})
    assert boosted[any_cost1] == pool[any_cost1] + EXPERT_COPIES_ASSUMED
    with pytest.raises(ValueError, match='注册表'):
        fixed_pool(extra_experts={'不存在的角色': 9})


def test_held_derived_from_bench_and_deployed_stars() -> None:
    """held = Σ 3^(star−1)(容器 bench/deployed 派生;合成不销毁口径:
    2★ 计 3 张);剩余 = 固定 − held 不变量。"""
    gs = _fresh_gs()
    n1 = chars_by_cost(1)[0].name
    n2 = chars_by_cost(2)[0].name
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    gs.observe(gs.bench, cw4_bview([
        cw4_bc(n1, star=1),
        cw4_bc(n1, star=1),
    ]), sig=sig)
    gs.observe(gs.deployed, _dvs([Unit(char_id=n2, star=2)], []), sig=sig)
    held = held_copies(gs)
    assert held[n1] == 2, '两只 1★ = 2 副本'
    assert held[n2] == 3, '2★ = 3 副本(3^(2−1))'
    remaining = remaining_pool(gs)
    assert remaining[n1] == POOL_COPIES_PER_CARD[1] - 2
    assert remaining[n2] == POOL_COPIES_PER_CARD[2] - 3


def test_drawable_names_nine_copy_clearance() -> None:
    """≥9 清空 = 发牌过滤(U11):held ≥9 的牌不再进店,即便 1/2 费
    27 副本下剩余仍 >0(两条件不可互替);同态双出口分野:授予出口
    (grant_bucket_names)无 ≥9 过滤,同卡仍在册。"""
    gs = _fresh_gs()
    n1 = chars_by_cost(1)[0].name
    gs.observe(gs.bench, cw4_bview([
        cw4_bc(n1, star=3),   # 3★ = 9 副本
    ]), sig=ChannelSig(family='obs', actor='TestSigWriter'))
    assert held_copies(gs)[n1] == 9
    assert remaining_pool(gs)[n1] == POOL_COPIES_PER_CARD[1] - 9, \
        '27 副本卡 9 持有后剩余仍为正'
    assert n1 not in drawable_names(gs, 1), '≥9 清空:不再进店'
    other = [n for n in drawable_names(gs, 1) if n != n1]
    assert other, '同档其余牌照常可进店'
    assert n1 in grant_bucket_names(gs, 1), \
        '授予出口无 ≥9 过滤(商店出口已清空 = 双出口分野)'


def test_drawable_names_tier_aware_bucket() -> None:
    """档感知:档 = 4(写点先例 = pick_planner 升费腿 write_logic 档行)
    → drawable_names(4) 含银狼LV.999、drawable_names(3) 不含;档未
    观察(None)→ 归约 3 费桶(起始档语义默认)。授予出口同享档过滤。"""
    gs = _fresh_gs()
    sw = '银狼LV.999'
    gs.write_logic(gs.lv999_cost_tier, 4, produced_by='TestWriter',
                   sig=_lsig())
    assert sw in drawable_names(gs, 4), '升费后归新费用档桶'
    assert sw not in drawable_names(gs, 3), '升费后旧档抽不出'
    assert sw in grant_bucket_names(gs, 4), '授予出口同享档过滤'
    gs_default = _fresh_gs()
    assert sw in drawable_names(gs_default, 3), '档未观察归约 3 费桶'
    assert sw not in drawable_names(gs_default, 4)
    assert sw in grant_bucket_names(gs_default, 3)


def test_conservation_safe_across_tier_transform() -> None:
    """守恒跨档安全:升费变换 2★→1★(升费腿形态,held 3 份→1 份)不炸
    守恒、旧档桶账面不出负值;副本数按名计与档无关(3/4/5 费同 9,
    升费只换桶归属)。"""
    sw = '银狼LV.999'
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    gs = _fresh_gs()
    gs.observe(gs.bench, cw4_bview([cw4_bc(sw, star=2)]), sig=sig)
    assert held_copies(gs)[sw] == 3
    gs.write_logic(gs.lv999_cost_tier, 4, produced_by='TestWriter',
                   sig=_lsig())
    gs.observe(gs.bench, cw4_bview([cw4_bc(sw, star=1)]), sig=sig)
    assert held_copies(gs)[sw] == 1
    assert remaining_pool(gs)[sw] == POOL_COPIES_PER_CARD[3] - 1, \
        '守恒按名核对跨档不误炸,旧档账面不为负'
    assert sw in drawable_names(gs, 4)
    assert sw in grant_bucket_names(gs, 4)


# ============================================================ 商店发牌与刷价(M05)

def test_deal_shop_level1_pure_cost1_payload() -> None:
    """Lv1 概率表纯 1 费 → 5 槽全 1 费注册表名;概率条随载荷落容器
    (§3.3.2 契约);槽号 1 基连号。"""
    gs = _fresh_gs()
    deal_shop(gs, stream_rng(3, 'M05/deal/1/1'), level=1,
              tag='shop:deal:p1r1')
    payload = gs.shop.value
    assert payload is not None and len(payload.cards) == 5
    assert payload.refresh_probs == {1: 1.0}
    for i, slot in enumerate(payload.cards):
        assert slot.kind == 'content' and slot.card is not None
        assert slot.card.cost == 1 and slot.card.star == 1
        assert slot.card.name in CHARACTERS
        assert slot.card.slot == i + 1
    assert gs.shop.evidence is not None \
        and 'sim:engine:' in gs.shop.evidence


def test_deal_shop_level9_domain_and_registered_names() -> None:
    """Lv9 混档发牌:出场费用档 ⊆ 表内正概率档,名集全部注册表在册
    (M06 抽名约束;直出 2/3 星 = 0,U12)。"""
    gs = _fresh_gs()
    deal_shop(gs, stream_rng(4, 'M05/deal/1/9'), level=9)
    payload = gs.shop.value
    legal_costs = {c for c, p in REFRESH_PROB[9].items() if p > 0}
    for slot in payload.cards:
        if slot.card is not None:
            assert slot.card.cost in legal_costs
            assert slot.card.star == 1, 'U12:首版直出概率 0'
            assert slot.card.name in CHARACTERS


def test_effective_deal_probs_rotation_toggle() -> None:
    """基线 = REFRESH_PROB 原表;轮岗开 = 重掷翻倍档(1/5 均匀系假设档,
    假设随 ROTATION_ASSUMPTION_DISCLOSURE 申报)或不可行档退基线。"""
    base = effective_deal_probs(6, stream_rng(1, 'M05/rotation/1/6'),
                                rotation_on=False)
    assert base == dict(REFRESH_PROB[6])
    rotated = effective_deal_probs(6, stream_rng(2, 'M05/rotation/1/6'),
                                   rotation_on=True)
    assert abs(sum(rotated.values()) - 1.0) < 1e-6
    assert set(rotated) <= {1, 2, 3, 4, 5}
    assert ROTATION_ASSUMPTION_DISCLOSURE


def test_in_stage_refresh_keeps_rotated_probs() -> None:
    """轮岗局 sim 世界真值阶段内不回退:M05 首刷携带翻倍表
    (``effective_deal_probs`` → ``deal_shop`` 真值直写)后,阶段内刷新
    上报(kernel 随机态腿,与生产 op 同段同口)写回载荷的概率条仍 =
    翻倍表——刷新上报采样表经 ``state_deal_probs`` 轮岗感知接线
    (出处 = docs/game/currency_war/research/invest_effects.md §2 轮岗行)。"""
    base = dict(REFRESH_PROB[6])
    rotated = effective_deal_probs(6, stream_rng(11, 'M05/rotation/1/6'),
                                   rotation_on=True)
    assert rotated != base, '前置:lv6 基线档全可行,重掷恒翻倍形'
    boosted = [c for c, p in rotated.items() if p > base[c]]
    assert len(boosted) == 1 and rotated[boosted[0]] == 2 * base[boosted[0]], \
        '翻倍档 = 基线×2(轮岗只翻倍)'
    gs = _fresh_gs()
    gs.observe(gs.level, 6, sig=ChannelSig(family='obs',
                                           actor='TestSigWriter'))
    deal_shop(gs, stream_rng(12, 'M05/deal/1/6'), level=6, probs=rotated,
              tag='shop:deal:p1r1')
    assert gs.shop.value.refresh_probs == rotated, 'M05 首刷携带翻倍表'
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _lsig(),
        rng=random.Random('cw-rotation-instage-refresh'))
    assert gs.shop.value.refresh_probs == rotated, \
        '阶段内刷新后仍翻倍形(不被基线污染)'
    assert gs.shop.source == 'logic_rand', '刷新上报 = 随机态专用通道'


# ============================================================ 节点选项生成(M16/M17/M18)

def test_encounter_options_structure_and_tier_bonus_truth() -> None:
    """U22:档位集 = 四档序结构;遭遇等级加成四档 0/10/20/30 = 定谳
    真值(economy.md §9,唯一有档数值;表住 cw_sim_enemy 难度账域)。"""
    opts = encounter_options()
    assert len(opts) == 4
    assert [o.difficulty for o in opts] == [1, 2, 3, 4]
    assert [o.idx for o in opts] == [0, 1, 2, 3]
    assert ENCOUNTER_TIER_BONUS == (0, 10, 20, 30)


@pytest.mark.parametrize('piggy_env', ['经济过热', '经济严重过热'])
def test_piggy_env_replacement_single_source(piggy_env: str) -> None:
    """扑满替换守卫(两卡同构参数化,设计 designs/T-20-jingji-
    yanzhong-guore.md §2.1.2):扑满族环境 + reward 节点 → True;其它
    环境/其它节点型恒 False(单一源 = PIGGY_ENV_NAMES × active_env;
    谓词级无变体分叉,变体分叉仅在面板矿增量注册表)。"""
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    gs = _gs('reward')
    gs.observe(gs.active_env, piggy_env, sig=sig)
    assert is_piggy_node(gs)
    gs.observe(gs.active_env, '轮岗', sig=sig)
    assert not is_piggy_node(gs)
    assert not is_piggy_node(_gs('battle')), '非奖励节点恒 False'


def test_env_ore_panel_bonus_registry_gate() -> None:
    """面板矿占位增量登记闸:恰两键且值逐字锁定。

    手抄期望是刻意的(sr-od-test README「数值期望现算」纪律的显式
    豁免,设计 designs/T-20-jingji-yanzhong-guore.md §2.1.2):期望若
    从注册表现算,占位值改动会自动跟随、登记闸失效——手抄锁死现值,
    任何占位值改动(含实采校准)必须过本测试显式更新 = 占位漂移在
    测试期可见,防「好心现算化」废闸与静默改值。"""
    assert ENV_ORE_PANEL_BONUS == {'经济过热': 4, '经济严重过热': 8}


def test_supply_options_replacement_sampling_and_env_driven() -> None:
    """U24/T-9:3 选项 = 8 基础件池**逐槽独立均匀有放回**(裁定 3:单纯
    随机可重复——「随机到一样就一样」;既有 distinct 断言钉住旧设计约定,
    随裁定退役)+ 带钻槽 equip 级均匀占位(恰一选项带钻);默认环境每列
    1 件、'过剩经费' 每列 2 件(ENV_SUPPLY_EQUIP_COUNT 查表);char 维
    恒空(补给 = 装备选)。带钻授予腿 = 后端列表派生(测试面 =
    test_sim_backend.py 补给窗)。同 seed 采样值随采样式变更漂移 =
    分布假设变更(设计披露 9),非回归破坏。"""
    # 默认环境:同 seed 逐值确定(回归可重跑)+ 结构恒定
    for seed in (0, 7, 42):
        a = supply_options(random.Random(seed))
        assert a == supply_options(random.Random(seed)), '同 seed 逐值确定'
        assert len(a) == 3
        assert sum(1 for o in a if o.has_diamond) == 1, '恰一带钻选项'
        assert all(o.char == '' for o in a)
        assert all(o.extra_equips == () for o in a), '默认环境每列 1 件'
    # 放回采样可重复:多 seed 扫描必存在同 offer 重复样本(逐槽独立
    # choice 的直接后果;跨列/同列重复同源,归档帧证跨列真实游戏可重)
    dup = any(len({o.equip for o in supply_options(random.Random(s))}) < 3
              for s in range(200))
    assert dup, '放回采样存在重复样本(不重名断言已随裁定退役)'

    # 过剩经费:每列 2 件(equip + extra_equips 恰 1 件)、恰一选项带钻
    env = cw_investments.normalize_invest_name('过剩经费')
    assert env == '过剩经费'
    opts = supply_options(random.Random(11), env)
    assert len(opts) == 3
    for o in opts:
        assert o.equip and len(o.extra_equips) == 1, '每列 2 件(首件+附加件)'
    assert sum(1 for o in opts if o.has_diamond) == 1, '恰一选项带钻(选项级布尔)'
    # 同列重复合法:锁定一个同列重复样本(逐槽独立放回的直接允许态;
    # 探针记录 = seed 22 首个命中)
    same_col = [(s, os_) for s in range(500)
                for os_ in [supply_options(random.Random(s), env)]
                if any(o.extra_equips and o.extra_equips[0] == o.equip
                       for o in os_)]
    assert same_col, '放回采样在同列也产出重复(1/8 每列,设计披露 9)'
    seed_hit, opts_hit = same_col[0]
    assert supply_options(random.Random(seed_hit), env) == opts_hit, \
        '同列重复样本同 seed 可重放'


def test_env_supply_equip_count_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ENV_SUPPLY_EQUIP_COUNT 登记表构建校验(import 即炸语义,注入 +
    直调,沿 ENV_STREAK_GRANTS 测试惯用法):孤儿环境键 / 值形(<2 或
    非 int 与默认 1 件无差 = 登记笔误);现表默认通过(与卡面 id 108
    同源)。"""
    assert cw_investments.ENV_SUPPLY_EQUIP_COUNT == {'过剩经费': 2}
    cw_investments._validate_env_supply_equip_count()

    # ① 孤儿环境键(版本更新改名/移除后静默失联 → 构建期炸)
    bad = dict(cw_investments.ENV_SUPPLY_EQUIP_COUNT)
    bad['不存在环境'] = 2
    monkeypatch.setattr(cw_investments, 'ENV_SUPPLY_EQUIP_COUNT', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_supply_equip_count()
    monkeypatch.undo()

    # ② 值形:<2 与默认 1 件无差 / 非 int(bool 排除)/ 0 = 登记笔误
    for bad_val in (1, 0, -1, True, 1.5):
        bad = dict(cw_investments.ENV_SUPPLY_EQUIP_COUNT)
        bad['过剩经费'] = bad_val
        monkeypatch.setattr(cw_investments, 'ENV_SUPPLY_EQUIP_COUNT', bad)
        with pytest.raises(ValueError, match='值形'):
            cw_investments._validate_env_supply_equip_count()
        monkeypatch.undo()
