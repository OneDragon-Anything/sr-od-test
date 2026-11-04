"""criteria/priority 单帧测试(角色统一让位优先级判据件)。

被测 = ``strategies/impl/mandate_v1/criteria/priority.py``;十档判定
规格(排序单位 = 单张牌 + 保留张谓词)= 本迭代设计定稿
``docs/develop/sr_od/application/currency_war/changes/2026-11-01-
completed-unit-protection/design.md`` §2.1(保留张定义与身份域)/
§2.2(十档判定表)/§2.3(落档边界)/§2.5(行为变化申报);承继
未变面(输入契约/档内键序数与随机流规则/取用形态)= 上一迭代
priority-model §1/§3/§4/§5(总纲 = 同目录 design.md §2.1):

- 十档判定表逐档断言(按序命中即出)+ 落档边界(design §2.3 全列:
  达标完成品档 2〔未锁/锁定两帧分帧〕/ need≤1 完成品档 4 / 凑两星
  中间态档 7 / 多余副本与等价群落兜底档 10〔自愈〕/ 2★ 直出候选恒
  非保留张);
- 档内键表断言(成员档 2/3/4/5/7 ①序数;档 2/3/4 总星级数+单卡星级;
  档 6 星级;档 8/9 总星级数;档 10 概率分档 + 同值低费先卖 + 星级键);
  「后卖」属性在「key 大者先卖」方向下以负号承载;
- 在手旗标(同优先级在手优先,总纲 §2.7)与随机尾键(种子同序,
  priority-model §4);
- sell_order 取用形态(升序 = 从最不该卖到最先让路,末位最先让路)+
  旋转门同型帧(达标 2★ 完成品在席满让位帧不做 victim);
- PriorityContext 生产装配(锁定帧 need_star 表 = 锁定线知识卡全量
  照录〔design §2.5-1 装配补全〕/ 未锁帧 = 实候选三线并集 + need_star
  跨线取最大 + 过渡候选成员随 transition_candidates 槽并入;P1 锁定局
  过渡支照收 = 名单景之一,32 号稿 §2 双层名单);
- member_rank 二元组族(32 号稿 §2):双层名单/同档垫底(过渡 (1,r)
  键恒大于终局 (0,r),先让路)/缺省值 (1, CANDIDATE_TOP_N)/跨对
  最小位次/重叠归终元(装配序承载,零特判)/过渡完成品层内档 4;
- 档内并列金币 tie-break(用户裁定三,上一迭代 design §2.2 第 1 项)
  与 member_rank 装配切换回归(承继未变)。

旧八档断言过期缘由(改写记录):统一序列排序单位从「角色名」改为
「单张牌」,原档 2 升星主线拆出完成品保护档 2、原档 5 拆出档 4,
原档 3/4/5/6/7/8 依次位移为 5/6/7/8/9/10(design §2.2 十档判定表)。
旧 rank 整数断言过期缘由:member_rank 键改 (层, 位次) 二元组
(32 号稿 §2)——终局 (0, 线内序数)/过渡
(1, 候选位次),字典序承载「同档占位、档内垫底」,键域/十档结构
零改动。旧配方支塞槽(opening_recipe_comp)过期缘由:过渡半边
名单源从物化单对改过渡候选槽并集(32 号稿 §2)。
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
    transition_entry_of,
    transition_member_set,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.priority import (
    RANK_TRANSITION_BOTTOM,
    HeldUnit,
    PriorityContext,
    ShopUnit,
    assemble_priority_context,
    held_copies_of,
    interest_exempt_member,
    sell_order,
    sort_key,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.line_select import (
    CANDIDATE_TOP_N,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.session_scope import (
    LineMembersView,
)

# 测试角色事实(注册表现查 cw_chars:费用/羁绊;万金油名单 =
# protection.CROSS_LINE_KEEP_NAMES = 千冶·刃/三月七/花火/星期日):
# - 停云 1费 仙舟/能量   —— 无万金油无档 9 羁绊,兜底档 10 中性件
# - 黄泉 3费 巡海游侠/减益 —— 档 9 羁绊成员(减益)
# - 椒丘 1费 狼狩/持续伤害、减益 —— 档 9 羁绊成员(减益)
# - 镜流 3费 狼狩/燃血   —— 兜底档 10 中性件
# - 波提欧 4费 / 流萤 5费 —— 兜底档 10 中性件(Lv4 概率全 0 撞值对)
# - 花火 2费 万金油(档 8)∧ 盛会之星(档 9)∧ 可为候选成员
#   —— 三身份叠加件
# - 三月七 1费 万金油(档 8)∧ 护盾(档 9)
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
    """测试上下文(双层名单面:locked_members = 锁定线名单,缺省 =
    实候选并集 + 过渡成员的未锁形态;rank 二元组 = 终局 (0, core 0/
    其余 1)迁移期映射,过渡成员 (1, 位次 1),重叠取终局——与生产
    装配序同构;位次精调用装配测试(塞真槽)承载)。"""
    if locked_members is not None:
        view = LineMembersView(locked=True, comp_name='测试线',
                               members=locked_members)
    else:
        view = LineMembersView(locked=False, comp_name=None, members=())
    core_set = set(cores)
    rank_map: dict[str, tuple[int, int]] = dict.fromkeys(recipe, (1, 1))
    rank_map.update({n: (0, 0) if n in core_set else (0, 1)
                     for n in candidates})
    return PriorityContext(
        held_copies=dict(copies or {}),
        deployed_names=frozenset(deployed),
        line_view=view,
        candidate_members=frozenset(candidates),
        recipe_members=frozenset(recipe),
        stay_target=stay,
        need_star_by_member=dict(need_star or {}),
        member_rank=rank_map,
        level=level,
        rng=random.Random(seed),
    )


def test_tier_assignment_in_order_and_boundaries() -> None:
    """十档判定按序命中即出 + 落档边界(design §2.2 表逐档;§2.3-1/3/4)。

    一上下文覆盖档 1-10 各一个代表件;边界例:need≥2 未达标中间态
    多张全留档 3(§2.3-1)、万金油/羁绊两星掉兜底(§2.3-4 非成员支
    对照)、档 6 成员整体排除、stay_target None 档 6 为空、need=1
    成员未持落档 5。"""
    ctx = _ctx(
        candidates=frozenset({_SABER, _WALT, _GIL, _TING, _JING}),
        cores=frozenset({_SABER}),
        need_star={_SABER: 3, _WALT: 2},
        copies={_SABER: [3], _WALT: [1], _GIL: [2], _TING: [1],
                _HUA: [1], _JIAO: [1], _HUANG: [1], _MAR: [1], _BO: [1]},
        deployed=frozenset({_MAR}),
        stay=('镜流占位', 3, 3),
    )
    # 档 1:部署在场名集(手持件;三月七万金油身份被档 1 先截)。
    assert sort_key(HeldUnit(_MAR, 1, 0, True), ctx)[0] == 1
    # 档 2:need≥2 达标成员保留张(need 3 持 3★,名下唯一最高星)。
    assert sort_key(HeldUnit(_SABER, 3, 1, False), ctx)[0] == 2
    # 档 3:成员有星级要求(need=2 ≥ 2)未达标。
    assert sort_key(HeldUnit(_WALT, 1, 2, False), ctx)[0] == 3
    # 档 4:need≤1 成员到两星的保留张(吉尔伽美什无星级要求持 2★)。
    assert sort_key(HeldUnit(_GIL, 2, 3, False), ctx)[0] == 4
    # 档 5:成员 need=1 未持任何副本(仅商店牌可命中;镜流 3 费虽与
    # 升星目标实费档同值,成员身份整体排除档 6,先落在档 5)。
    assert sort_key(ShopUnit(_JING, 1, 4), ctx)[0] == 5
    # 档 6:非成员 ∧ 费用档 == 升星目标实费档(黄泉 3 费;其档 9 羁绊
    # 身份被按序先出的档 6 截走)。
    assert sort_key(HeldUnit(_HUANG, 1, 5, False), ctx)[0] == 6
    # 档 7:成员已持、need=1、未到两星(凑两星过程保护)。
    assert sort_key(HeldUnit(_TING, 1, 6, False), ctx)[0] == 7
    # 档 8:万金油未到两星(花火;档 9 羁绊身份被万金油档先截)。
    assert sort_key(HeldUnit(_HUA, 1, 7, False), ctx)[0] == 8
    # 档 9:羁绊成员(减益)未到两星且非万金油。
    assert sort_key(HeldUnit(_JIAO, 1, 8, False), ctx)[0] == 9
    # 档 10:兜底(无任何名单/羁绊/费用档命中的中性件)。
    assert sort_key(HeldUnit(_BO, 1, 9, False), ctx)[0] == 10
    # —— 落档边界 ——
    # need≥2 未达标名中间态多张全留档 3(design §2.3-1:合成需要,
    # 多余判定只在达标后生效;[1,1] 两张同落档 3)。
    ctx_mid = _ctx(candidates=frozenset({_SABER}),
                   cores=frozenset({_SABER}),
                   need_star={_SABER: 3}, copies={_SABER: [1, 1]})
    assert sort_key(HeldUnit(_SABER, 1, 0, False), ctx_mid)[0] == 3
    assert sort_key(HeldUnit(_SABER, 1, 1, False), ctx_mid)[0] == 3
    # 万金油两星掉出档 8 → 兜底档 10(design §2.3-4 非成员支对照;
    # 档 9 羁绊身份同样限 <2 不中)。
    ctx_2star = _ctx(copies={_HUA: [2], _JIAO: [2], _MAR: [2]})
    assert sort_key(HeldUnit(_HUA, 2, 0, False), ctx_2star)[0] == 10
    assert sort_key(HeldUnit(_JIAO, 2, 0, False), ctx_2star)[0] == 10
    assert sort_key(HeldUnit(_MAR, 2, 0, False), ctx_2star)[0] == 10
    # 档 6 成员整体排除:成员费用档命中目标档也不入档 6(吉尔伽美什
    # 2 费 = 目标档 → 档 7 而非档 6)。
    ctx_member_cost = _ctx(
        candidates=frozenset({_GIL}), need_star={},
        copies={_GIL: [1]}, stay=('目标', 2, 2))
    assert sort_key(HeldUnit(_GIL, 1, 0, False), ctx_member_cost)[0] == 7
    # stay_target None(未锁定窗口/无未完成目标)档 6 为空:黄泉落档 9。
    ctx_no_stay = _ctx(copies={_HUANG: [1]})
    assert sort_key(HeldUnit(_HUANG, 1, 0, False), ctx_no_stay)[0] == 9
    # 档 1 按名命中不分手牌/商店牌(在场角色的店卡同为部署需要面)。
    assert sort_key(ShopUnit(_MAR, 1, 1), ctx)[0] == 1


def test_completed_kept_tier2_unlocked_and_locked_frames() -> None:
    """达标 2★ 完成品进档 2,未锁定/锁定两帧一致(design §2.3-2/
    §2.5-1)。锁定帧断言吃装配补全:need_star 表 = 锁定线知识卡全量
    照录——旧装配自 unfinished_star_targets 只收未达标成员,已达标
    花火缺省 1 会使档 2 谓词 need≥2 永不命中、错落档 4。

    注册表事实:列车同行知识卡 need_star 花火 = 2(2★ 即达标);花火
    同钉万金油 ∧ 盛会之星羁绊,成员完成品档按序先出(design §2.5-10
    叠加身份的实卡形态)。"""
    # 未锁定帧:候选线知识卡 need_star 直读,达标成员天然在表。
    s1 = cw4_session()
    gs1 = cw4_gs(s1, level=7, bench=[cw4_bc(_HUA, star=2)])
    state_of(gs1).line_candidates = ('列车同行·反震',)
    ctx_u = assemble_priority_context(s1, gs1, deployed_names=frozenset())
    assert not ctx_u.line_view.locked
    assert ctx_u.need_star_by_member.get(_HUA) == 2
    assert sort_key(HeldUnit(_HUA, 2, 0, False), ctx_u)[0] == 2
    # 锁定帧:同板面,锁定列车同行——need_star 表全量照录,达标成员
    # 不缺行(装配补全判定位:旧装配缺此行 → get() 为 None)。
    s2 = cw4_session()
    gs2 = cw4_gs(s2, level=7, bench=[cw4_bc(_HUA, star=2)])
    state_of(gs2).target_comp = get_comp('列车同行·反震')
    ctx_l = assemble_priority_context(s2, gs2, deployed_names=frozenset())
    assert ctx_l.line_view.locked
    assert ctx_l.need_star_by_member.get(_HUA) == 2, \
        '锁定帧达标成员按知识卡照录(design §2.5-1 装配补全)'
    assert sort_key(HeldUnit(_HUA, 2, 0, False), ctx_l)[0] == 2


def test_need2_completed_name_redundant_and_equivalence_group() -> None:
    """need≥2 已达标名的按张分家(design §2.3-2/§2.1 等价群自愈):
    保留张(最高星唯一张)档 2;其余副本(低星 1★)自然落兜底档 10;
    两星等价群 [2,2] 同星多张全不属保留张、双双落兜底,卖一张后剩张
    恢复保留身份(档 2)。"""
    ctx = _ctx(candidates=frozenset({_SABER}), cores=frozenset({_SABER}),
               need_star={_SABER: 2}, copies={_SABER: [2, 1]})
    assert sort_key(HeldUnit(_SABER, 2, 0, False), ctx)[0] == 2, \
        '达标保留张进档 2'
    assert sort_key(HeldUnit(_SABER, 1, 1, False), ctx)[0] == 10, \
        '达标名下冗余 1★ 落兜底(档 2/3/4/6/7/8/9 谓词全不命中)'
    # 等价群 [2,2]:同星多张全不属保留张 → 双双落兜底。
    ctx_eq = _ctx(candidates=frozenset({_SABER}), cores=frozenset({_SABER}),
                  need_star={_SABER: 2}, copies={_SABER: [2, 2]})
    assert sort_key(HeldUnit(_SABER, 2, 0, False), ctx_eq)[0] == 10
    assert sort_key(HeldUnit(_SABER, 2, 1, False), ctx_eq)[0] == 10
    # 自愈:卖一张后名下 [2],剩张恢复保留身份 → 档 2。
    ctx_healed = _ctx(candidates=frozenset({_SABER}),
                      cores=frozenset({_SABER}),
                      need_star={_SABER: 2}, copies={_SABER: [2]})
    assert sort_key(HeldUnit(_SABER, 2, 0, False), ctx_healed)[0] == 2


def test_need1_two_star_completion_boundaries() -> None:
    """need≤1 名底线两星口径(design §2.3-3/§2.1):凑两星中间态
    (max_star<2,含 1★×1 与 1★×2)全部副本留档 7;到两星后保留张
    档 4(2★ 本体与超额 3★ 均按实际最高星);名下多余副本(1★)落
    兜底档 10;两星等价群 [2,2] 双双落兜底、卖一张自愈恢复档 4。"""
    # 凑两星中间态:[1] 与 [1,1] 全留档 7(原档 5 保护域原样,仅位移)。
    ctx_mid = _ctx(candidates=frozenset({_TING}), copies={_TING: [1]})
    assert sort_key(HeldUnit(_TING, 1, 0, False), ctx_mid)[0] == 7
    ctx_mid2 = _ctx(candidates=frozenset({_TING}), copies={_TING: [1, 1]})
    assert sort_key(HeldUnit(_TING, 1, 0, False), ctx_mid2)[0] == 7
    assert sort_key(HeldUnit(_TING, 1, 1, False), ctx_mid2)[0] == 7
    # 完成品:2★ 保留张档 4;超额 3★ 保留张亦档 4。
    ctx_done = _ctx(candidates=frozenset({_TING}), copies={_TING: [2]})
    assert sort_key(HeldUnit(_TING, 2, 0, False), ctx_done)[0] == 4
    ctx_over = _ctx(candidates=frozenset({_TING}), copies={_TING: [3]})
    assert sort_key(HeldUnit(_TING, 3, 0, False), ctx_over)[0] == 4
    # 两星后名下多余 1★ 落兜底:[2,1] 保留张与冗余张分家。
    ctx_mix = _ctx(candidates=frozenset({_TING}), copies={_TING: [2, 1]})
    assert sort_key(HeldUnit(_TING, 2, 0, False), ctx_mix)[0] == 4
    assert sort_key(HeldUnit(_TING, 1, 1, False), ctx_mix)[0] == 10
    # 两星等价群 [2,2] 双双落兜底;卖一张后剩张自愈恢复档 4。
    ctx_eq = _ctx(candidates=frozenset({_TING}), copies={_TING: [2, 2]})
    assert sort_key(HeldUnit(_TING, 2, 0, False), ctx_eq)[0] == 10
    assert sort_key(HeldUnit(_TING, 2, 1, False), ctx_eq)[0] == 10
    ctx_heal = _ctx(candidates=frozenset({_TING}), copies={_TING: [2]})
    assert sort_key(HeldUnit(_TING, 2, 0, False), ctx_heal)[0] == 4


def test_shop_candidate_two_star_never_kept_unit() -> None:
    """候选牌恒非保留张(design §2.1 身份域/§2.3-5):获取让位评估的
    虚拟语境下,2★ 直出候选 X 不享受完成品保护——保留张谓词对
    ShopUnit 恒 False,X 落兜底档 10,「末位 = X → 放弃买入」对一切
    候选牌保持可达;对照:同板面的存量 2★ 在手件按虚拟快照现算保留
    张身份,照常受保(档 2/4)。"""
    # need≥2 已达标名 + 2★ 直出候选:候选落兜底,非档 2。
    ctx = _ctx(candidates=frozenset({_SABER}), cores=frozenset({_SABER}),
               need_star={_SABER: 2}, copies={_SABER: [2]})
    assert sort_key(ShopUnit(_SABER, 2, 3), ctx)[0] == 10, \
        '2★ 直出候选恒非保留张(身份域排除)'
    assert sort_key(HeldUnit(_SABER, 2, 0, False), ctx)[0] == 2, \
        '存量 2★ 按虚拟快照现算保留张身份,照常受保'
    # 无星级要求已两星名:2★ 直出候选同样落兜底(非档 4)。
    ctx_n1 = _ctx(candidates=frozenset({_TING}), copies={_TING: [2]})
    assert sort_key(ShopUnit(_TING, 2, 1), ctx_n1)[0] == 10
    assert sort_key(HeldUnit(_TING, 2, 0, False), ctx_n1)[0] == 4


def test_huahuo_triple_identity_completed_protection() -> None:
    """万金油 ∧ 羁绊 ∧ 线内成员三身份叠加件(花火型)的 2★ 保留张按
    成员身份落档 2/4(design §2.3-4/§2.5-10 行为申报回归锁):完成品
    保护档按序先于万金油(档 8)/羁绊(档 9);非成员对照支——2★ 掉
    兜底、1★ 万金油先截——保持原样。"""
    # 成员 need≥2 达标:2★ 保留张 → 档 2(压过万金油/羁绊身份)。
    ctx_t2 = _ctx(candidates=frozenset({_HUA}), need_star={_HUA: 2},
                  copies={_HUA: [2]})
    assert sort_key(HeldUnit(_HUA, 2, 0, False), ctx_t2)[0] == 2
    # 成员 need≤1 达标:2★ 保留张 → 档 4。
    ctx_t4 = _ctx(candidates=frozenset({_HUA}), copies={_HUA: [2]})
    assert sort_key(HeldUnit(_HUA, 2, 0, False), ctx_t4)[0] == 4
    # 非成员对照(design §2.6:现 fixture 非成员支 2★→兜底仍保留):
    # 2★ 掉兜底档 10;1★ 万金油档 8 先于羁绊档 9 截走(不变)。
    ctx_non = _ctx(copies={_HUA: [2]})
    assert sort_key(HeldUnit(_HUA, 2, 0, False), ctx_non)[0] == 10
    ctx_1 = _ctx(copies={_HUA: [1]})
    assert sort_key(HeldUnit(_HUA, 1, 0, False), ctx_1)[0] == 8
    # 成员 1★(need≤1,凑两星过程):档 7 先于万金油档 8(不变)。
    ctx_m1 = _ctx(candidates=frozenset({_HUA}), copies={_HUA: [1]})
    assert sort_key(HeldUnit(_HUA, 1, 0, False), ctx_m1)[0] == 7


def test_turnstile_completed_two_star_not_victim() -> None:
    """旋转门同型帧(迭代现象 d_20261101_125430 A-1 的回归锁;design
    §2.7-1):席满获取让位帧,达标 2★ 完成品不再从统一序列末位做牺牲
    者——victim 退位给兜底杂件;候选牌侧保持「末位 = X → 放弃买入」
    可达,decline 分支不因完成品保护翻转为必买(design §2.5-6)。"""
    ctx = _ctx(candidates=frozenset({_SABER}), cores=frozenset({_SABER}),
               need_star={_SABER: 2},
               copies={_SABER: [2], _TING: [1]})
    pool: list[HeldUnit | ShopUnit] = [
        HeldUnit(_SABER, 2, 0, False),  # 档 2 达标保留张(乱破型完成品)
        HeldUnit(_TING, 1, 1, False),   # 档 10 兜底杂件
    ]
    ordered = sell_order(pool, ctx)
    assert ordered[0] is pool[0], '达标 2★ 完成品居序列保护端'
    assert ordered[-1] is pool[1], 'victim = 兜底杂件(完成品不再垫底)'
    # 候选牌侧:2★ 直出 X 仍可成为末位 → 放弃买入分支保持可达。
    pool_x: list[HeldUnit | ShopUnit] = [
        HeldUnit(_SABER, 2, 0, False),
        ShopUnit(_TING, 2, 1),          # 候选恒非保留张 → 兜底
    ]
    assert sell_order(pool_x, ctx)[-1] is pool_x[1], \
        '末位 = 候选 X → decline 可达(行为不变,design §2.5-6)'


def test_tier_keys_and_sell_direction() -> None:
    """档内键与「key 大者先卖」方向(design §2.2 档内键列;后卖属性
    负号承载)。

    - 成员档 2/3/4 ①序数(core 先留)→ ②总星级数(多者后卖)→
      ③单卡星级(高者后卖;档 2/4 完成品跨名最高星可变,高星完成品
      后卖——design §2.2 档 2/档 4 键注);
    - 档 6 星级键高者后卖;档 8/9 总星级数键多副本者后卖;档 10
      概率高者先卖、概率同值并入同档按费用号稳定序低费先卖(Lv4 的
      4/5 费概率全 0 撞值对)、同费用星级高者后卖。"""
    # 档 3 ①序数:同 need 成员 core((0,0)) 先于非 core((0,1)) 卖出序
    # (终局层二元组,§2.4-3)。
    ctx_rank = _ctx(candidates=frozenset({_SABER, _WALT}),
                    cores=frozenset({_SABER}),
                    need_star={_SABER: 3, _WALT: 3},
                    copies={_SABER: [1], _WALT: [1]})
    k_core = sort_key(HeldUnit(_SABER, 1, 0, False), ctx_rank)
    k_other = sort_key(HeldUnit(_WALT, 1, 1, False), ctx_rank)
    assert k_core[:2] == (3, (0, 0)) and k_other[:2] == (3, (0, 1))
    # 档 3 ②③:同成员跨星副本,总星级数同值,单卡星级高者键小(后卖)
    # ——1★ 副本先让路。
    ctx_cross = _ctx(candidates=frozenset({_SABER}),
                     cores=frozenset({_SABER}),
                     need_star={_SABER: 3}, copies={_SABER: [1, 2]})
    k_1 = sort_key(HeldUnit(_SABER, 1, 0, False), ctx_cross)
    k_2 = sort_key(HeldUnit(_SABER, 2, 1, False), ctx_cross)
    assert k_1[2] == k_2[2] == -3, '总星级数键 = -(1+2)'
    assert k_1[3] == -1 and k_2[3] == -2 and k_2 < k_1, '2★ 后卖(键更小)'
    # 档 2 ③单卡星级判别力:不同名达标完成品总星级数并列时(3★ 独张
    # vs 2★+1★ 冗余名),高星完成品后卖(design §2.2 档 2 键注:
    # -unit_star 有判别力)。
    ctx_t2 = _ctx(candidates=frozenset({_SABER, _WALT}),
                  cores=frozenset({_SABER, _WALT}),
                  need_star={_SABER: 2, _WALT: 2},
                  copies={_SABER: [3], _WALT: [2, 1]})
    k_over3 = sort_key(HeldUnit(_SABER, 3, 0, False), ctx_t2)
    k_done2 = sort_key(HeldUnit(_WALT, 2, 1, False), ctx_t2)
    assert k_over3[0] == k_done2[0] == 2
    assert k_over3[2] == k_done2[2] == -3, '②总星级数并列(-3)'
    assert k_over3[3] == -3 and k_done2[3] == -2 and k_done2 > k_over3, \
        '3★ 完成品后卖'
    # 档 4 ③单卡星级:与档 2 同构(无星级要求完成品,跨名最高星可变)。
    ctx_t4k = _ctx(candidates=frozenset({_GIL, _TING}),
                   copies={_GIL: [3], _TING: [2, 1]})
    k_g3 = sort_key(HeldUnit(_GIL, 3, 0, False), ctx_t4k)
    k_t4b = sort_key(HeldUnit(_TING, 2, 1, False), ctx_t4k)
    assert k_g3[0] == k_t4b[0] == 4
    assert k_g3[2] == k_t4b[2] == -3, '②总星级数并列(-3)'
    assert k_g3[3] == -3 and k_t4b[3] == -2 and k_t4b > k_g3, '3★ 后卖'
    # 档 6 星级:同档两星压库牌键小(后卖,牌池抽稀贡献大)。
    ctx_t6 = _ctx(stay=('目标', 3, 3), copies={_HUANG: [1, 1]})
    k6_1 = sort_key(HeldUnit(_HUANG, 1, 0, False), ctx_t6)
    k6_2 = sort_key(HeldUnit(_HUANG, 2, 1, False), ctx_t6)
    assert k6_2 < k6_1 and k6_1[0] == 6
    # 档 8 总星级数键:多副本者后卖(攒两张离两星更近)。
    ctx_t8 = _ctx(copies={_MAR: [1], _HUA: [1, 1]})
    k_mar = sort_key(HeldUnit(_MAR, 1, 0, False), ctx_t8)
    k_hua = sort_key(HeldUnit(_HUA, 1, 1, False), ctx_t8)
    assert k_mar[:2] == (8, -1) and k_hua[:2] == (8, -2) and k_hua < k_mar
    # 档 9 同构(羁绊层,非万金油成员)。
    ctx_t9 = _ctx(copies={_HUANG: [1], _JIAO: [1, 1]})
    k_h = sort_key(HeldUnit(_HUANG, 1, 0, False), ctx_t9)
    k_j = sort_key(HeldUnit(_JIAO, 1, 1, False), ctx_t9)
    assert k_h[:2] == (9, -1) and k_j[:2] == (9, -2) and k_j < k_h
    # 档 10 概率分档:概率高者先卖(Lv7 3 费 vs 4 费,期望值 = 概率表现查)。
    ctx_t10 = _ctx(level=7, copies={_JING: [1], _BO: [1]})
    k_jing = sort_key(HeldUnit(_JING, 1, 0, False), ctx_t10)
    k_bo = sort_key(HeldUnit(_BO, 1, 1, False), ctx_t10)
    assert k_jing[0] == 10 and k_bo[0] == 10
    assert k_jing[1] == refresh_prob(7, get_char(_JING).cost)
    assert k_bo[1] == refresh_prob(7, get_char(_BO).cost)
    assert k_jing > k_bo, '3 费(高概率)先卖'
    # 档 10 概率同值并入同档 + 低费先卖稳定序(Lv4 4/5 费概率同值,
    # 同值前提 = 概率表现查,版本随表自动传导)。
    ctx_tie = _ctx(level=4, copies={_BO: [1], _LIU: [1]})
    k4c = sort_key(HeldUnit(_BO, 1, 0, False), ctx_tie)
    k5c = sort_key(HeldUnit(_LIU, 1, 1, False), ctx_tie)
    assert refresh_prob(4, get_char(_BO).cost) \
        == refresh_prob(4, get_char(_LIU).cost), '撞值前提(注册表现查)'
    assert k4c[1] == k5c[1], '概率同值并入同档'
    assert k4c[2] == -4 and k5c[2] == -5 and k4c > k5c, '低费先卖'
    # 档 10 星级键(同费用):高星后卖。
    ctx_star = _ctx(level=7, copies={_TING: [1, 2]})
    assert sort_key(HeldUnit(_TING, 2, 0, False), ctx_star) \
        < sort_key(HeldUnit(_TING, 1, 1, False), ctx_star)


def test_held_unit_effective_cost_for_variable_cost_card() -> None:
    """手持变费卡实费档(HeldUnit.cost 治本载体;修「变费卡升费后仍按
    注册表起始费误判档位」的档 10 概率分档/档 6 匹配残差)。

    银狼LV.999 升费后(现档 4/5)由装配方按 effective_cost 现值供给
    ``HeldUnit.cost``:档 10 概率分档与档 6 匹配按供给值判,不再按
    注册表起始费 3 档误判;缺省(非变费卡/未供给)回退注册表起始费。"""
    _LV999 = '银狼LV.999'
    ctx = _ctx(level=7, copies={_LV999: [1]})
    k_upgraded = sort_key(HeldUnit(_LV999, 1, 0, False, cost=4), ctx)
    k_baseline = sort_key(HeldUnit(_LV999, 1, 1, False), ctx)
    assert k_upgraded[1] == refresh_prob(7, 4), '档 10 按供给实费档现查'
    assert k_baseline[1] == refresh_prob(7, get_char(_LV999).cost), \
        '缺省回退 = 注册表起始费'
    # 档 6 匹配同吃供给值:升费 4 费 == 目标实费档 → 入档 6。
    ctx_t6 = _ctx(stay=('目标', 3, 4), copies={_LV999: [1]})
    assert sort_key(HeldUnit(_LV999, 1, 0, False, cost=4), ctx_t6)[0] == 6


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
        HeldUnit(_SABER, 1, 1, False),  # 档 3(升星主线)
        HeldUnit(_HUANG, 2, 2, False),  # 档 6 两星压库牌
    ]
    ordered = sell_order(pool, ctx)
    assert ordered[0] is pool[0], '档 1 排序列首(部署定型内永不先卖)'
    assert ordered[-1] is pool[2], '末位 = 最先让路(档 6 > 档 3 > 档 1)'


def test_locked_frame_need_star_full_transcription() -> None:
    """装配·锁定帧:need_star 表 = 锁定线知识卡字段全量照录(design
    §2.5-1 装配补全),达标成员不缺省——旧装配自 unfinished_star_
    targets 只收未达标成员,Saber 3★ 达标后缺行会使命 need≥2 完成
    品保护谓词在锁定帧永不命中;unfinished_star_targets 本体与其余
    消费位(升级触发/停留目标)不动。

    种子纪律:方向状态宿主 = gs.strategy_state(生产 = cw_strategy
    状态 setter 同源接线;装配面统一读 gs 侧,与 line_members_view
    同宿主)→ 锁定线槽种 gs 侧状态对象。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[cw4_bc(_SABER, star=3)],
                front_row=[Unit(char_id=_TING, star=1)])
    state_of(gs).target_comp = get_comp('双王圣杯')
    ctx = assemble_priority_context(
        session, gs, deployed_names=frozenset({_TING}))
    assert ctx.line_view.locked and _SABER in ctx.line_view.members
    # 表 = 知识卡 need_star 全量(design §2.5-1);判定位 = 已达标
    # 成员(Saber 持 3★ = need 3)仍在表——旧装配缺此行。
    _comp = get_comp('双王圣杯')
    assert ctx.need_star_by_member == {n: int(v) for n, v
                                       in _comp.need_star.items()}, \
        '锁定帧 need_star 表 = 知识卡全量照录(达标成员不缺省)'
    # 达标完成品的行为落点:锁定帧 Saber 3★ 保留张 → 档 2(旧装配下
    # 缺省 1 会错落档 4)。
    assert sort_key(HeldUnit(_SABER, 3, 0, False), ctx)[0] == 2
    # 升星目标 = 未完成目标中费用档最低者(现读单一源 stay_target_of
    # 的多目标停留顺序;Saber 达标退出未完成集,1 费辅助藿藿仍为最低
    # 费目标——目标名 = 探测记录,实费档 = 注册表现查)。
    assert ctx.stay_target is not None and ctx.stay_target[0] == '藿藿'
    assert ctx.stay_target[2] == get_char('藿藿').cost, \
        '实费档 resolved 口径'
    # 锁定帧名单 = 锁定线成员(经 line_view 承载;候选快照字段照读口
    # 真值冻结为空集——锁定写入连带清空停算),过渡支空集——本帧
    # 过渡候选槽未种(P1 锁定局过渡支照收的并集形态见
    # test_locked_p1_frame_recipe_members_join_roster)。
    assert _GIL in ctx.member_rank
    assert ctx.candidate_members == frozenset()
    assert ctx.recipe_members == frozenset()
    assert ctx.member_rank[_SABER] == (0, 0), 'core 迁移期高优先级'
    assert all(v == (0, 0) for v in ctx.member_rank.values()), \
        '双王圣杯锁定线 shared ⊆ core,全员 core 形态'
    assert held_copies_of(gs) == {_SABER: [3], _TING: [1]}, \
        '持牌全量快照 = 备战位 ∪ 前后台'


def test_unlocked_frame_candidates_union_and_recipe_members() -> None:
    """装配·未锁定帧(双层名单,§2.4-2/§2.4-3):成员档(2/3/4/5/7)
    名单 = 实候选三线成员并集 ∪ 过渡候选成员(transition_candidates
    槽展开);need_star 命中各线取最大值(保守方向),过渡成员不入表
    (缺省 1);rank 二元组 = 终局 (0, 线内序数)/过渡 (1, 槽位次),
    重叠成员取终局值(装配序承载)。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[])
    st = state_of(gs)
    st.line_candidates = ('列车同行·反震', '火花星间旅人')
    st.transition_candidates = ('希儿引擎',)
    ctx = assemble_priority_context(
        session, gs, deployed_names=frozenset())
    assert not ctx.line_view.locked
    # 候选两线的 need_star 跨线取最大:花火 ∈ 列车同行 ∧ 火金星间
    # 旅人,期望 = 命中各线知识卡取最大(规则现算,值 = 注册表现查)。
    expected_hua = max(get_comp('列车同行·反震').need_star[_HUA],
                       get_comp('火花星间旅人').need_star[_HUA])
    assert ctx.need_star_by_member.get(_HUA) == expected_hua
    # 过渡层贡献名单并入(过渡支 = 条目见即买集)。
    expected_recipe = transition_member_set(transition_entry_of('希儿引擎'))
    assert ctx.recipe_members == frozenset(expected_recipe), \
        '过渡候选条目成员非空(见即买集展开)'
    # 序数二元组:候选 core (0,0) 高优先级、候选 shared (0,1) 低档;
    # 重叠成员(过渡 ∩ 候选——花火/银狼均量子同频 ∈ 希儿引擎放大器池)
    # 取终局值(零特判)。
    assert ctx.member_rank.get(_HUA) == (0, 0), '重叠归终元:花火 = 候选 core'
    assert ctx.member_rank.get('银狼') == (0, 1), \
        '重叠归终元:银狼 = 候选 shared'
    # 纯过渡成员(点名件)统一 (1, 0)(条目内两档 core=0;羁绊半边
    # 放大器/凑数件表外落判定端缺省)。
    recipe_only = ctx.recipe_members - ctx.candidate_members
    assert recipe_only, '纯过渡支非空'
    assert ctx.member_rank.get('希儿') == (1, 0), \
        '点名过渡成员 = (1, 线内位次 0)'
    assert '佩拉' not in ctx.member_rank, \
        '羁绊半边件不入序数表(判定端缺省 RANK_TRANSITION_BOTTOM)'


def test_member_rank_field_direct_read_cross_line_highest() -> None:
    """装配·字段直读 + 跨线取最高(成员档 ①键取值规则 = priority-
    model §3,档 2/3/4/5/7 共用):序数表 = 各候选线知识卡
    ``member_priority`` 字段直读合成,跨线成员取各线最小序数(序数小
    = 优先级高,core 优先于非 core)。

    判别例(注册表现查):符玄 = 双王圣杯 core((0, 0)) ∧ 火花星间旅人
    shared((0, 1)) → 取 (0, 0);银狼仅火花单线 shared → 维持 (0, 1)
    (非 core 不因跨线抬升);花火双线皆 core → 恒 (0, 0)。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[])
    st = state_of(gs)
    st.line_candidates = ('火花星间旅人', '双王圣杯')
    ctx = assemble_priority_context(session, gs, deployed_names=frozenset())
    assert ctx.member_rank['符玄'] == (0, 0), \
        '跨线取最高:任一线 core 命中即 (0, 0)'
    assert ctx.member_rank['银狼'] == (0, 1), '单线 shared 维持低档'
    assert ctx.member_rank['花火'] == (0, 0), '双线 core 同为高档'


def test_recipe_members_stay_low_priority() -> None:
    """装配·过渡成员垫底保持(priority-model §3 配方支 → §2.4-3
    过渡支):过渡候选成员不入终局字段直读面 → rank 恒 (1, 位次)——
    过渡候选对成员若被物化伪阵容(pair_target_comp)字段直读即全员
    (0, 0) 高档,装配禁读物化单对字段。两态分断:

    - 未锁帧:纯过渡成员(不在实候选)= (1, 线内位次);过渡 ∩ 实候选
      交集成员按候选线字段取值(终局身份优先,不被过渡层覆盖)。
    (配方伪锁帧段已随物化链退役删除——伪阵容载体随配方决策层退役。)
    """
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[])
    st = state_of(gs)
    st.line_candidates = ('火花星间旅人', '双王圣杯')
    st.transition_candidates = ('希儿引擎',)
    ctx = assemble_priority_context(session, gs, deployed_names=frozenset())
    recipe_only = ctx.recipe_members - ctx.candidate_members
    assert recipe_only, '纯过渡支非空(希儿类,前置)'
    assert ctx.member_rank.get('希儿') == (1, 0), \
        '点名过渡成员 (1, 线内位次 0)'
    overlap = ctx.recipe_members & ctx.candidate_members
    assert {'花火', '银狼', '符玄'} <= overlap, '交集前置(注册表现查)'
    assert ctx.member_rank['花火'] == (0, 0) \
        and ctx.member_rank['符玄'] == (0, 0), \
        '交集成员按候选线字段取值(core 不被过渡层覆盖)'
    assert ctx.member_rank['银狼'] == (0, 1)


def test_member_rank_migration_equivalence() -> None:
    """消费面切换回归(档内排序不变性;§2.4-3 二元组化):迁移前后
    member_rank 输出等价。

    旧装配 = core_chars 并集推导((0, 0 if n in cores else 1));新装配 =
    ``member_priority`` 字段直读 + 跨线最小序数合成 + 包 (0, ·) 终局层。
    迁移期两档形态下两者必须逐成员相等——成员档(2/3/4/5/7)①键是
    sort_key 对 ``member_rank`` 的纯表查,表等价即档内排序不变;末段
    抽样实证序数值确实落到成员档的①键位。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[])
    st = state_of(gs)
    st.line_candidates = ('列车同行·反震', '火花星间旅人', '双王圣杯')
    ctx = assemble_priority_context(session, gs, deployed_names=frozenset())
    members: set[str] = set()
    cores: set[str] = set()
    for line_name in st.line_candidates:
        c = get_comp(line_name)
        members |= set(c.core_chars) | set(c.shared_chars)
        cores |= set(c.core_chars)
    legacy = {n: (0, 0 if n in cores else 1) for n in members}
    assert ctx.member_rank == legacy, '未锁帧:字段直读 ≡ 旧集合并集推导'
    # 锁定帧同构等价。
    state_of(gs).target_comp = get_comp('双王圣杯')
    ctx_locked = assemble_priority_context(
        session, gs, deployed_names=frozenset())
    lock = get_comp('双王圣杯')
    lock_members = set(lock.core_chars) | set(lock.shared_chars)
    assert ctx_locked.member_rank == {
        n: (0, 0 if n in lock.core_chars else 1) for n in lock_members}, \
        '锁定帧:字段直读 ≡ 旧推导'
    # 序数落键抽样:花火(core,need 3,持 1★)档 3 ①键 = (0, 0);银狼
    # (shared,need 缺省 1,持 1★)档 7 ①键 = (0, 1)。独立 session(状态
    # 宿主 = 会话容器,与前段锁定写入隔离)。
    session2 = cw4_session()
    gs2 = cw4_gs(session2, level=7,
                 bench=[cw4_bc('花火'), cw4_bc('银狼')])
    state_of(gs2).line_candidates = ('火花星间旅人',)
    ctx_rank = assemble_priority_context(session2, gs2,
                                         deployed_names=frozenset())
    k_hua = sort_key(HeldUnit('花火', 1, 0, False), ctx_rank)
    k_yin = sort_key(HeldUnit('银狼', 1, 1, False), ctx_rank)
    assert k_hua[0] == 3 \
        and k_hua[1] == ctx_rank.member_rank['花火'] == (0, 0)
    assert k_yin[0] == 7 \
        and k_yin[1] == ctx_rank.member_rank['银狼'] == (0, 1)


def _final_locked_gs(plane: int = 1):
    """终局锁定种子(两景共用):锁定线 = 双王圣杯,过渡候选 = 廉价DOT
    (注册表事实:卡芙卡 ∈ 廉价DOT ∉ 锁定线);bench 持卡芙卡 1★,
    场上镜流中性件。"""
    session = cw4_session()
    gs = cw4_gs(session, plane=plane, level=7, bench=[cw4_bc('卡芙卡')],
                front_row=[Unit(char_id='镜流', star=1)])
    st = state_of(gs)
    st.target_comp = get_comp('双王圣杯')
    st.transition_candidates = ('廉价DOT',)
    return session, gs


def test_final_lock_frame_recipe_members_retired() -> None:
    """装配·终局锁定帧(换轴:原 P1 锁定局并集形态随「终局锁定即过渡层
    退役」收敛):锁定帧名单 = 锁定线单源,纯过渡成员退出成员档
    (2/3/4/5/7)名单——已持 1★ 落非成员档(≥8,具体档随羁绊/万金油
    身份,断言收敛为「不在成员档」)。"""
    session, gs = _final_locked_gs()
    ctx = assemble_priority_context(
        session, gs, deployed_names=frozenset({'镜流'}))
    assert ctx.line_view.locked
    assert ctx.recipe_members == frozenset(), \
        '终局锁定帧过渡支恒空(换轴:退役清空出口 = 锁定写入点)'
    assert sort_key(HeldUnit('卡芙卡', 1, 0, False), ctx)[0] > 7, \
        '纯过渡成员退出成员档名单'


def test_p2_unlocked_frame_recipe_branch_stays_active() -> None:
    """装配·位面 2 未终局锁定帧(换轴行为申报 6):原「进位面 2 过渡支
    恒空」随生命周期挂钩终局锁定事件废除——位面 2 未终局锁定的帧
    过渡层照常贡献,纯过渡成员已持 1★ 落档 7。"""
    session = cw4_session()
    gs = cw4_gs(session, plane=2, level=7, bench=[cw4_bc('卡芙卡')])
    st = state_of(gs)
    st.plane2_started = True
    st.transition_candidates = ('廉价DOT',)
    ctx = assemble_priority_context(
        session, gs, deployed_names=frozenset())
    assert not ctx.line_view.locked
    assert '卡芙卡' in ctx.recipe_members, \
        '位面 2 未终局锁定帧过渡支照常贡献'
    k_held = sort_key(HeldUnit('卡芙卡', 1, 0, False), ctx)
    assert k_held[0] == 7, '已持纯过渡成员(need 缺省 1)落档 7'


def test_tier_tie_refund_loss_tiebreak() -> None:
    """档内并列金币 tie-break(用户裁定 2026-10-30 三;roster-
    plane1-union design §2.2 第 1 项/金币核查表):现行档内键全并列
    → 退金损失最小者优先让路(键内取负,损失大 = 后卖)。

    档 5 商店牌同序数并列三组:①同名跨星 1★(全额退,损失 0)先让于
    2★(折价,损失 1)——同价值档内选不亏的卖;②cost=1 exempt:1 费
    2★ 退金无手续费(损失 0)先让于 3 费 2★(损失 1);③序数现行键
    不删:非 core(终局层低档)仍先让于 core(终局层高档)
    ——退金损失只在现行档内键之后参与定序。"""
    ctx = _ctx(candidates=frozenset({_SABER, _WALT, _GIL}),
               cores=frozenset({_SABER}), copies={})
    k_walt_1 = sort_key(ShopUnit(_WALT, 1, 3), ctx)
    k_walt_2 = sort_key(ShopUnit(_WALT, 2, 3), ctx)
    assert k_walt_1[:4] == (5, (0, 1), 0, 1), \
        '档 5 键形 = (档, 序数二元组, -退金损失, 在手旗标)'
    assert k_walt_2[:4] == (5, (0, 1), -1, 1)
    assert k_walt_1 > k_walt_2, '同档并列:1★ 全额退(损失 0)先让'
    # cost=1 exempt(2★ 1 费退金 = cost×3 无手续费 → 损失 0)。
    k_gil_2c1 = sort_key(ShopUnit(_GIL, 2, 1), ctx)
    assert k_gil_2c1[:3] == (5, (0, 1), 0)
    assert k_gil_2c1 > k_walt_2, '1 费 2★ 全额退先让于 3 费 2★ 折价'
    # 序数(现行档内键)先于退金损失:非 core 1★ 先让于 core 2★。
    k_saber_2 = sort_key(ShopUnit(_SABER, 2, 3), ctx)
    assert k_saber_2[:3] == (5, (0, 0), -1)
    assert k_walt_1 > k_saber_2, '序数键先判(core 后让,损失键不越位)'


# ===== member_rank 二元组族(32 号稿 §2)=====

def test_transition_rank_dual_layer_and_min_position() -> None:
    """装配·双层 rank 合成(32 号稿 §2):过渡成员 = (1, 线内位次)
    (member_rank_of 两档:core=0/其余=1;条目 shared 空 → 点名成员
    位次 0,羁绊半边件表外落判定端缺省);多条目同名成员跨条目取最小
    位次;重叠成员归终元(rank 取终局值,装配序承载零特判);点名
    成员按条目 need_star 入表,未点名成员缺省 1。

    种槽:候选 1 = 仙舟铁三角(点名 爻光/藿藿/丹恒·饮月 → (1, 0)),
    候选 2 = 希儿引擎(点名 希儿 → (1, 0);量子/贝放大器 = 羁绊半边,
    表外落判定端缺省)。符玄 = 量子同频 ∈ 希儿引擎放大器池 ∧ 双王
    圣杯候选 core → 归终元 (0, 0)。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[])
    st = state_of(gs)
    st.line_candidates = ('双王圣杯',)
    st.transition_candidates = ('仙舟铁三角', '希儿引擎')
    ctx = assemble_priority_context(session, gs, deployed_names=frozenset())
    # 点名成员 = (1, 线内位次 0)(条目 core 两档派生)。
    assert ctx.member_rank['爻光'] == (1, 0), \
        '点名过渡成员 (1, 0)(仙舟铁三角 core)'
    assert ctx.member_rank['希儿'] == (1, 0), \
        '点名过渡成员 (1, 0)(希儿引擎 core;跨条目同名取最小位次)'
    # 羁绊半边成员(放大器/凑数件)不入序数表 → 判定端缺省
    # RANK_TRANSITION_BOTTOM(佩拉 ∈ 贝洛伯格全体 ∉ core∪shared)。
    assert '佩拉' in ctx.recipe_members
    assert '佩拉' not in ctx.member_rank, \
        '羁绊半边件不入序数表(判定端缺省)'
    # 重叠归终元:符玄 = 过渡并集 ∧ 实候选(双王圣杯 core)→ (0, 0)。
    assert '符玄' in ctx.recipe_members and '符玄' in ctx.candidate_members
    assert ctx.member_rank['符玄'] == (0, 0), \
        '重叠成员 rank 取终局值(零特判)'
    # 点名成员按条目 need_star 入表(铁三角三人各 2;未点名成员缺省)。
    assert ctx.need_star_by_member.get('爻光') == 2, \
        '过渡点名成员 need_star 入表(行为变化申报)'
    assert '佩拉' not in ctx.need_star_by_member, \
        '未点名过渡成员不入 need_star 表(缺省 1)'


def test_transition_member_bottom_in_same_tier() -> None:
    """同档垫底(§2.4-3 字典序承载;用户裁定「和终局阵容一样的位置,
    比终局阵容的低」):同档(档 7 凑两星)内过渡 (1, 1) 键恒大于终局
    (0, 1)——统一序列末位(最先让路) = 过渡成员,终局成员殿后。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7,
                bench=[cw4_bc('瓦尔特'), cw4_bc('桑博')])
    st = state_of(gs)
    st.line_candidates = ('列车同行·反震',)
    st.transition_candidates = ('廉价DOT',)
    ctx = assemble_priority_context(session, gs, deployed_names=frozenset())
    k_walt = sort_key(HeldUnit('瓦尔特', 1, 0, False), ctx)
    k_mar = sort_key(HeldUnit('桑博', 1, 1, False), ctx)
    assert k_walt[0] == k_mar[0] == 7, \
        '两者均档 7(need 1 持 1★ 未到两星,谓词同构)'
    assert ctx.member_rank['瓦尔特'][0] == 0, '终局成员层 0'
    assert '桑博' not in ctx.member_rank, \
        '羁绊型成员不入序数表(判定端缺省过渡层末位)'
    assert k_walt < k_mar, \
        '同档内终局 (0,r) 键小后卖、过渡 (1,r) 键大先让(垫底)'
    pool: list[HeldUnit | ShopUnit] = [
        HeldUnit('瓦尔特', 1, 0, False),
        HeldUnit('桑博', 1, 1, False),
    ]
    assert sell_order(pool, ctx)[-1] is pool[1], \
        '统一序列末位 = 过渡成员(同档垫底)'


def test_unlisted_member_rank_defaults_transition_bottom() -> None:
    """缺省值(§2.4-3):表外/非候选成员的判定端缺省 = (1,
    CANDIDATE_TOP_N)——与第三候选并列垫底,由后续键判别;防 int vs
    tuple 混型(五读点 ``.get`` 缺省二元组化,同档内同型比较)。"""
    ctx = _ctx(candidates=frozenset({_TING}), copies={_TING: [1]})
    ctx.member_rank.pop(_TING)   # 名单内但表缺行 = 缺省消费形态
    k = sort_key(HeldUnit(_TING, 1, 0, False), ctx)
    assert k[0] == 7
    assert k[1] == RANK_TRANSITION_BOTTOM == (1, CANDIDATE_TOP_N), \
        '缺省 = (1, 3):与第三候选并列,不抛混型比较'


def test_transition_completed_unit_tier4_same_predicates() -> None:
    """过渡完成品层内档 4(§2.4-2 谓词同构/§2.3-5「2★ 完成品按成员
    档 4 同构受保」):过渡成员 need 缺省 1,底线两星口径——2★ 保留张
    档 4、1★ 凑两星中间态档 7、未持商店牌档 5、等价群 [2,2] 双双落
    兜底档 10(保留张谓词与等价群自愈随档复制,零例外)。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[cw4_bc('卡芙卡', star=2)])
    state_of(gs).transition_candidates = ('廉价DOT',)
    ctx = assemble_priority_context(session, gs, deployed_names=frozenset())
    assert sort_key(HeldUnit('卡芙卡', 2, 0, False), ctx)[0] == 4, \
        '过渡 2★ 保留张同构进档 4(未点名成员 need 缺省 1)'
    assert sort_key(ShopUnit('桑博', 1, 1), ctx)[0] == 5, \
        '未持过渡成员商店牌档 5'
    # 点名成员 need_star 入表:希儿(need 3)持 1★ → 档 3 升星主线
    # (行为变化申报:过渡条目点名成员星级保护生效)。
    session_ns = cw4_session()
    gs_ns = cw4_gs(session_ns, level=7, bench=[cw4_bc('希儿')])
    state_of(gs_ns).transition_candidates = ('希儿引擎',)
    ctx_ns = assemble_priority_context(session_ns, gs_ns,
                                       deployed_names=frozenset())
    assert sort_key(HeldUnit('希儿', 1, 0, False), ctx_ns)[0] == 3, \
        '点名成员 need 3 未达标落档 3(升星主线)'
    # 1★ 中间态与等价群:手造 copies 形态(装配快照 = bench 现读,
    # 等价群 [2,2] 经 bench 两张 2★ 种入)。
    session2 = cw4_session()
    gs2 = cw4_gs(session2, level=7, bench=[cw4_bc('卡芙卡')])
    state_of(gs2).transition_candidates = ('廉价DOT',)
    ctx1 = assemble_priority_context(session2, gs2,
                                     deployed_names=frozenset())
    assert sort_key(HeldUnit('卡芙卡', 1, 0, False), ctx1)[0] == 7, \
        '过渡 1★ 未到两星档 7(过程保护同构)'
    session3 = cw4_session()
    gs3 = cw4_gs(session3, level=7,
                 bench=[cw4_bc('卡芙卡', star=2), cw4_bc('卡芙卡', star=2)])
    state_of(gs3).transition_candidates = ('廉价DOT',)
    ctx2 = assemble_priority_context(session3, gs3,
                                     deployed_names=frozenset())
    assert sort_key(HeldUnit('卡芙卡', 2, 0, False), ctx2)[0] == 10, \
        '过渡等价群 [2,2] 双双落兜底(自愈同构)'


def test_interest_exempt_covers_transition_members() -> None:
    """凑息豁免域含过渡在建件(§2.4-5 豁免语义对过渡成员同构生效):
    过渡成员 need 缺省 1 → 底线两星——未满两星(1★)为利息绝对不可
    卖;达标(2★ 完成品)不豁免(可为利息变现,完成品档 4 殿后仍照
    常参与凑息池)。名单源 = _member_names 双层并集,装配改后自动
    跟随。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[cw4_bc('卡芙卡')])
    state_of(gs).transition_candidates = ('廉价DOT',)
    ctx = assemble_priority_context(session, gs, deployed_names=frozenset())
    assert interest_exempt_member('卡芙卡', ctx), \
        '过渡在建件(1★ 未到两星)受凑息豁免'
    session2 = cw4_session()
    gs2 = cw4_gs(session2, level=7, bench=[cw4_bc('卡芙卡', star=2)])
    state_of(gs2).transition_candidates = ('廉价DOT',)
    ctx2 = assemble_priority_context(session2, gs2,
                                     deployed_names=frozenset())
    assert not interest_exempt_member('卡芙卡', ctx2), \
        '过渡完成品(2★ 达标)不豁免,可为利息变现'
