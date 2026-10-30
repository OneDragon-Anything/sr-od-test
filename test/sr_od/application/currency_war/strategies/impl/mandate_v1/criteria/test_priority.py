"""criteria/priority 单帧测试(角色统一让位优先级判据件)。

被测 = ``strategies/impl/mandate_v1/criteria/priority.py``;规格单一源 =
``docs/develop/sr_od/application/currency_war/changes/2026-10-29-unified-
priority/details/priority-model.md`` §1-§5(总纲 = 同目录 design.md §2.1):

- 八档判定表逐档断言(按序命中即出 + 落档边界:达标成员落档 8 /
  万金油·羁绊两星掉档 / need=1 成员落档 3·5 / 档 4 成员整体排除);
- 档内键表断言(档 2 三键 = 序数+总星级数+单卡星级;档 6/7 总星级数;
  档 8 概率分档 + 概率同值低费先卖 + 星级键);「后卖」属性在
  「key 大者先卖」方向下以负号承载;
- 在手旗标(同优先级在手优先,总纲 §2.7)与随机尾键(种子同序,
  priority-model §4);
- sell_order 取用形态(升序 = 从最不该卖到最先让路,末位最先让路);
- PriorityContext 生产装配(锁定帧 need_star 表源 = unfinished_star_
  targets / 未锁帧 = 候选三线并集 + need_star 跨线取最大 + 过渡配方
  成员回落 opening_recipe_comp)。
"""
from __future__ import annotations

import random

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
    cw4_session,
)

from sr_od.application.currency_war.data.cw_chars import get_char
from sr_od.application.currency_war.data.cw_shop_odds import refresh_prob
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    pair_target_comp,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.priority import (
    HeldUnit,
    PriorityContext,
    ShopUnit,
    assemble_priority_context,
    held_copies_of,
    sell_order,
    sort_key,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.session_scope import (
    LineMembersView,
)

# 测试角色事实(注册表现查 cw_chars:费用/羁绊;万金油名单 =
# protection.CROSS_LINE_KEEP_NAMES):
# - 停云 1费 仙舟/能量   —— 无万金油无档 7 羁绊,档 8 中性件
# - 黄泉 3费 巡海游侠/减益 —— 档 7 羁绊成员(减益)
# - 椒丘 1费 狼狩/持续伤害、减益 —— 档 7 羁绊成员(减益)
# - 镜流 3费 狼狩/燃血   —— 档 8 中性件
# - 波提欧 4费 / 流萤 5费 —— 档 8 中性件(Lv4 概率全 0 撞值对)
# - 花火 2费 万金油 ∧ 盛会之星(档 7)∧ 可为候选成员 —— 三身份叠加件
# - 三月七 1费 万金油 ∧ 护盾(档 7)
_GIL = '吉尔伽美什'
_SABER = 'Saber'
_WALT = '瓦尔特'
_TING = '停云'
_HUANG = '黄泉'
_JING = '镜流'
_BO = '波提欧'
_LIU = '流萤'
_HUA = '花火'
_MAR = '三月七'
_JIAO = '椒丘'


def _ctx(*, candidates: frozenset[str] = frozenset(),
         cores: frozenset[str] = frozenset(),
         recipe: frozenset[str] = frozenset(),
         need_star: dict[str, int] | None = None,
         copies: dict[str, list[int]] | None = None,
         deployed: frozenset[str] = frozenset(),
         stay: tuple[str, int, int] | None = None,
         level: int = 7,
         locked_members: tuple[str, ...] | None = None,
         seed: int = 42) -> PriorityContext:
    """测试上下文(两态名单面:locked_members = 锁定线名单,缺省 =
    候选并集 + 配方成员的未锁形态;rank = core 0/其余 1 迁移期映射)。"""
    if locked_members is not None:
        view = LineMembersView(locked=True, comp_name='测试线',
                               members=locked_members)
        members: set[str] = set(locked_members)
    else:
        view = LineMembersView(locked=False, comp_name=None, members=())
        members = set(candidates) | set(recipe)
    core_set = set(cores)
    return PriorityContext(
        held_copies=dict(copies or {}),
        deployed_names=frozenset(deployed),
        line_view=view,
        candidate_members=frozenset(candidates),
        recipe_members=frozenset(recipe),
        stay_target=stay,
        need_star_by_member=dict(need_star or {}),
        member_rank={n: (0 if n in core_set else 1) for n in members},
        level=level,
        rng=random.Random(seed),
    )


def test_tier_assignment_in_order_and_boundaries() -> None:
    """八档判定按序命中即出 + 落档边界(priority-model §2 表逐档)。

    一上下文覆盖档 1-8 各一个代表件;边界三例(达标成员落档 8 /
    万金油两星掉档 8 / 羁绊两星掉档 8)与档 4 的成员整体排除、
    stay_target None 档 4 为空、need=1 成员未持落档 3。"""
    ctx = _ctx(
        candidates=frozenset({_SABER, _WALT, _GIL}),
        cores=frozenset({_SABER}),
        need_star={_SABER: 3},
        copies={_SABER: [1, 1], _GIL: [1], _HUA: [1], _JIAO: [1],
                _TING: [1], _HUANG: [1], _MAR: [1]},
        deployed=frozenset({_MAR}),
        stay=('镜流占位', 3, 3),
    )
    # 档 1:部署在场名集(手持件;三月七万金油身份被档 1 先截)。
    assert sort_key(HeldUnit(_MAR, 1, 0, True), ctx)[0] == 1
    # 档 2:成员有星级要求(need=3 ≥ 2)未达标。
    assert sort_key(HeldUnit(_SABER, 1, 1, False), ctx)[0] == 2
    # 档 3:成员 need=1(无表项缺省)未持任何副本(仅商店牌可命中)。
    assert sort_key(ShopUnit(_WALT, 1, 2), ctx)[0] == 3
    # 档 4:非成员 ∧ 费用档 == 升星目标实费档(黄泉 3 费;其档 7 身份
    # 被按序先出的档 4 截走)。
    assert sort_key(HeldUnit(_HUANG, 1, 2, False), ctx)[0] == 4
    # 档 5:成员已持、need=1、未到两星。
    assert sort_key(HeldUnit(_GIL, 1, 3, False), ctx)[0] == 5
    # 档 6:万金油未到两星(花火;档 7 羁绊身份被万金油档先截)。
    assert sort_key(HeldUnit(_HUA, 1, 4, False), ctx)[0] == 6
    # 档 7:羁绊成员(减益)未到两星且非万金油。
    assert sort_key(HeldUnit(_JIAO, 1, 5, False), ctx)[0] == 7
    # 档 8:兜底(无任何名单/羁绊/费用档命中的中性件)。
    assert sort_key(HeldUnit(_TING, 1, 6, False), ctx)[0] == 8
    # —— 落档边界 ——
    # 达标成员(持有最高星 ≥ need)落档 8:need 3 持 [1,2,3]。
    ctx_done = _ctx(candidates=frozenset({_SABER}),
                    cores=frozenset({_SABER}),
                    need_star={_SABER: 3}, copies={_SABER: [1, 2, 3]})
    assert sort_key(HeldUnit(_SABER, 1, 0, False), ctx_done)[0] == 8
    # 万金油两星掉出档 6(花火 2★ → 档 8;档 7 羁绊身份同样限 <2 不中)。
    ctx_2star = _ctx(copies={_HUA: [2], _JIAO: [2]})
    assert sort_key(HeldUnit(_HUA, 2, 0, False), ctx_2star)[0] == 8
    # 羁绊成员两星掉出档 7(椒丘 2★ → 档 8)。
    assert sort_key(HeldUnit(_JIAO, 2, 0, False), ctx_2star)[0] == 8
    # 档 4 成员整体排除:成员费用档命中目标档也不入档 4(吉尔伽美什
    # 2 费 = 目标档 → 档 5 而非档 4)。
    ctx_member_cost = _ctx(
        candidates=frozenset({_GIL}), need_star={},
        copies={_GIL: [1]}, stay=('目标', 2, 2))
    assert sort_key(HeldUnit(_GIL, 1, 0, False), ctx_member_cost)[0] == 5
    # stay_target None(未锁定窗口/无未完成目标)档 4 为空:黄泉落档 7。
    ctx_no_stay = _ctx(copies={_HUANG: [1]})
    assert sort_key(HeldUnit(_HUANG, 1, 0, False), ctx_no_stay)[0] == 7
    # 档 1 按名命中不分手牌/商店牌(在场角色的店卡同为部署需要面)。
    assert sort_key(ShopUnit(_MAR, 1, 1), ctx)[0] == 1


def test_tier_keys_and_sell_direction() -> None:
    """档内键与「key 大者先卖」方向(priority-model §3;后卖属性负号承载)。

    - 档 2 三键:序数(core 先留)→ 总星级数(多者后卖)→ 单卡星级
      (高者后卖——追三星持 1★+2★ 先卖 1★);
    - 档 4/8 星级键高者后卖;档 8 概率高者先卖、概率同值并入同档按
      费用号稳定序低费先卖(Lv4 的 4/5 费概率全 0 撞值对)。"""
    # 档 2 ①序数:同 need 成员 core(0) 先于非 core(1) 卖出序。
    ctx_rank = _ctx(candidates=frozenset({_SABER, _WALT}),
                    cores=frozenset({_SABER}),
                    need_star={_SABER: 3, _WALT: 3},
                    copies={_SABER: [1], _WALT: [1]})
    k_core = sort_key(HeldUnit(_SABER, 1, 0, False), ctx_rank)
    k_other = sort_key(HeldUnit(_WALT, 1, 1, False), ctx_rank)
    assert k_core[:2] == (2, 0) and k_other[:2] == (2, 1)
    # 档 2 ②③:同成员跨星副本,总星级数同值,单卡星级高者键小(后卖)
    # ——1★ 副本先让路。
    ctx_cross = _ctx(candidates=frozenset({_SABER}),
                     cores=frozenset({_SABER}),
                     need_star={_SABER: 3}, copies={_SABER: [1, 2]})
    k_1 = sort_key(HeldUnit(_SABER, 1, 0, False), ctx_cross)
    k_2 = sort_key(HeldUnit(_SABER, 2, 1, False), ctx_cross)
    assert k_1[2] == k_2[2] == -3, '总星级数键 = -(1+2)'
    assert k_1[3] == -1 and k_2[3] == -2 and k_2 < k_1, '2★ 后卖(键更小)'
    # 档 2 ②跨名总星级数:同序数成员多副本者后卖。
    ctx_total = _ctx(candidates=frozenset({_SABER, _WALT}),
                     cores=frozenset({_SABER}),
                     need_star={_SABER: 3, _WALT: 3},
                     copies={_SABER: [1], _WALT: [1, 1]})
    assert sort_key(HeldUnit(_WALT, 1, 1, False), ctx_total)[2] == -2
    assert sort_key(HeldUnit(_SABER, 1, 0, False), ctx_total)[2] == -1
    # 档 4 星级:同档两星压库牌键小(后卖,牌池抽稀贡献大)。
    ctx_t4 = _ctx(stay=('目标', 3, 3), copies={_HUANG: [1, 1]})
    k4_1 = sort_key(HeldUnit(_HUANG, 1, 0, False), ctx_t4)
    k4_2 = sort_key(HeldUnit(_HUANG, 2, 1, False), ctx_t4)
    assert k4_2 < k4_1 and k4_1[0] == 4
    # 档 8 概率分档:概率高者先卖(Lv7 3 费 vs 4 费,期望值 = 概率表现查)。
    ctx_t8 = _ctx(level=7, copies={_JING: [1], _BO: [1]})
    k_jing = sort_key(HeldUnit(_JING, 1, 0, False), ctx_t8)
    k_bo = sort_key(HeldUnit(_BO, 1, 1, False), ctx_t8)
    assert k_jing[0] == 8
    assert k_jing[1] == refresh_prob(7, get_char(_JING).cost)
    assert k_bo[1] == refresh_prob(7, get_char(_BO).cost)
    assert k_jing > k_bo, '3 费(高概率)先卖'
    # 档 8 概率同值并入同档 + 低费先卖稳定序(Lv4 4/5 费概率同值,
    # 同值前提 = 概率表现查,版本随表自动传导)。
    ctx_tie = _ctx(level=4, copies={_BO: [1], _LIU: [1]})
    k4c = sort_key(HeldUnit(_BO, 1, 0, False), ctx_tie)
    k5c = sort_key(HeldUnit(_LIU, 1, 1, False), ctx_tie)
    assert refresh_prob(4, get_char(_BO).cost) \
        == refresh_prob(4, get_char(_LIU).cost), '撞值前提(注册表现查)'
    assert k4c[1] == k5c[1], '概率同值并入同档'
    assert k4c[2] == -4 and k5c[2] == -5 and k4c > k5c, '低费先卖'
    # 档 8 星级键(同费用):高星后卖。
    ctx_star = _ctx(level=7, copies={_TING: [1, 2]})
    assert sort_key(HeldUnit(_TING, 2, 0, False), ctx_star) \
        < sort_key(HeldUnit(_TING, 1, 1, False), ctx_star)
    # 档 6/7 总星级数键:多副本者后卖(攒两张离两星更近)。
    ctx_t6 = _ctx(copies={_MAR: [1], _HUA: [1, 1]})
    k_mar = sort_key(HeldUnit(_MAR, 1, 0, False), ctx_t6)
    k_hua = sort_key(HeldUnit(_HUA, 1, 1, False), ctx_t6)
    assert k_mar[:2] == (6, -1) and k_hua[:2] == (6, -2) and k_hua < k_mar


def test_in_hand_flag_and_random_tail() -> None:
    """在手旗标与随机尾键(priority-model §4)。

    - 在手旗标:同优先级手持牌键小(在手优先,同优先级不换手——
      席满时与手上同优先级的店牌不买);
    - 随机尾键:仅手持完全等价牌群参与(键前缀全同),同 seed 同序;
      商店牌已被旗标区分、跨星副本已被星级键区分,不入随机域。"""
    ctx = _ctx(copies={_TING: [1]})
    k_held = sort_key(HeldUnit(_TING, 1, 0, False), ctx)
    k_shop = sort_key(ShopUnit(_TING, 1, 1), ctx)
    assert k_held[-2] == 0 and k_shop[-2] == 1
    assert k_held < k_shop, '同优先级在手优先'
    # 随机域收窄:完全等价手持对的前缀键全同(只差尾键)。
    ctx_pair = _ctx(copies={_TING: [1, 1]})
    k_a = sort_key(HeldUnit(_TING, 1, 0, False), ctx_pair)
    k_b = sort_key(HeldUnit(_TING, 1, 1, False), ctx_pair)
    assert k_a[:-1] == k_b[:-1] and k_a[-1] != k_b[-1]
    # 同 seed 同序:同一上下文对象重排两次,等价对的相对序由随机流
    # 顺序决定——同一装配(同一 rng 实例)两次排序结果一致才可复现;
    # 换 seed 允许翻转(随机语义本体,不断言具体方向)。
    order_a = [u.slot for u in sell_order(
        [HeldUnit(_TING, 1, 0, False), HeldUnit(_TING, 1, 1, False)],
        _ctx(copies={_TING: [1, 1]}, seed=42))]
    order_b = [u.slot for u in sell_order(
        [HeldUnit(_TING, 1, 0, False), HeldUnit(_TING, 1, 1, False)],
        _ctx(copies={_TING: [1, 1]}, seed=42))]
    assert order_a == order_b, '同 seed 同序(确定性,优先级序列可复现)'


def test_sell_order_shape() -> None:
    """sell_order 取用形态(priority-model §5):升序 = 从最不该卖到
    最先让路;部署定型内(档 1)永不先卖,末位 = 让位对象。"""
    ctx = _ctx(
        candidates=frozenset({_SABER}),
        cores=frozenset({_SABER}),
        need_star={_SABER: 3},
        copies={_SABER: [1], _TING: [1], _HUANG: [2]},
        deployed=frozenset({_TING}),
        stay=('目标', 3, 3),
    )
    pool: list[HeldUnit | ShopUnit] = [
        HeldUnit(_TING, 1, 0, True),    # 档 1(部署内)—— 最不该卖
        HeldUnit(_SABER, 1, 1, False),  # 档 2(升星主线)
        HeldUnit(_HUANG, 2, 2, False),  # 档 4 两星压库牌
    ]
    ordered = sell_order(pool, ctx)
    assert ordered[0] is pool[0], '档 1 排序列首(部署定型内永不先卖)'
    assert ordered[-1] is pool[2], '末位 = 最先让路(档 4 > 档 2 > 档 1)'


def test_locked_frame_need_star_from_unfinished_targets() -> None:
    """装配·锁定帧:need_star 表消费单一源 = unfinished_star_targets
    (priority-model §2;仅锁定帧适用),聚合快照与升星目标同源现读。

    种子纪律:方向状态宿主 = gs.strategy_state(生产 = cw_strategy
    状态 setter 同源接线;装配面统一读 gs 侧,与 line_members_view
    同宿主)→ 锁定线槽种 gs 侧状态对象。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[cw4_bc(_SABER)],
                front_row=[Unit(char_id=_TING, star=1)])
    state_of(gs).target_comp = get_comp('双王圣杯')
    ctx = assemble_priority_context(
        session, gs, deployed_names=frozenset({_TING}))
    assert ctx.line_view.locked and _SABER in ctx.line_view.members
    # 表 = unfinished_star_targets 全量输出(未达标成员,含未持的
    # need=1 行——判定端 need ≥ 2 门使该行惰性,档 3/5 语义不变;
    # 期望值 = 锁定线知识卡 need_star 注册表现查)。
    _comp = get_comp('双王圣杯')
    assert ctx.need_star_by_member.get(_SABER) == _comp.need_star[_SABER]
    assert ctx.need_star_by_member.get(_GIL) == _comp.need_star.get(_GIL, 1)
    # 升星目标 = 未完成目标中费用档最低者(现读单一源 stay_target_of
    # 的多目标停留顺序;未持的 1 费辅助先于 3 费 Saber——目标名 =
    # 探测记录,实费档 = 注册表现查)。
    assert ctx.stay_target is not None and ctx.stay_target[0] == '藿藿'
    assert ctx.stay_target[2] == get_char('藿藿').cost, \
        '实费档 resolved 口径'
    # 锁定帧名单 = 锁定线成员(经 line_view 承载;候选快照字段照读口
    # 真值冻结为空集——锁定写入连带清空停算),配方支空集。
    assert _GIL in ctx.member_rank
    assert ctx.candidate_members == frozenset()
    assert ctx.recipe_members == frozenset()
    assert ctx.member_rank[_SABER] == 0, 'core 迁移期高优先级'
    assert all(v == 0 for v in ctx.member_rank.values()), \
        '双王圣杯锁定线 shared ⊆ core,全员 core 形态'
    assert held_copies_of(gs) == {_SABER: [1], _TING: [1]}, \
        '持牌全量快照 = 备战位 ∪ 前后台'


def test_unlocked_frame_candidates_union_and_recipe_members() -> None:
    """装配·未锁定帧:档 2/3/5 名单 = 候选三线成员并集 ∪ 过渡配方对
    成员;need_star 命中各线取最大值(保守方向);配方成员读口 =
    direction_comp_of 未锁定回落 opening_recipe_comp(P2 守卫由读口
    承载);序数迁移期 = core 0/其余 1,配方成员统一低档。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[])
    st = state_of(gs)
    st.line_candidates = ('列车同行', '火花星间旅人')
    st.opening_recipe_comp = pair_target_comp(('持续伤害', '希儿系'))
    ctx = assemble_priority_context(
        session, gs, deployed_names=frozenset())
    assert not ctx.line_view.locked
    # 候选两线的 need_star 跨线取最大:花火 ∈ 列车同行 ∧ 火金星间
    # 旅人,期望 = 命中各线知识卡取最大(规则现算,值 = 注册表现查)。
    expected_hua = max(get_comp('列车同行').need_star[_HUA],
                       get_comp('火花星间旅人').need_star[_HUA])
    assert ctx.need_star_by_member.get(_HUA) == expected_hua
    # 过渡配方对成员并入名单(配方支)。
    assert ctx.recipe_members, 'P1 配方对成员非空'
    union = ctx.candidate_members | ctx.recipe_members
    assert all(m in union for m in ctx.recipe_members)
    # 序数:候选 core 高优先级、候选 shared 低优先级、配方成员统一低档。
    assert ctx.member_rank.get(_HUA) == 0, '花火 = 火金星间旅人 core'
    assert ctx.member_rank.get('银狼') == 1, '银狼 = 候选 shared'
    recipe_core = next(iter(ctx.recipe_members))
    assert ctx.member_rank.get(recipe_core, 1) == 1, '配方成员统一低档'
