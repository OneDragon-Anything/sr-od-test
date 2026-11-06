"""等级帽覆写行为锁(镜像 src = kernel/cw_action_report/level_up.py 满级门
+ kernel/cw_economy 两推进算子 level_cap 形参消费链;登记面锁 =
cw_investments/test_strategy_kongzhi_guimo_entry.py,解析/聚合锁 =
kernel/test_economy.py,宝钻联动锁 = sim/cw_sim_backend/test_strategy_
pick_diamond_grant_sim_chain.py,本文件只锁行为面)。

测试面依据 = 迭代设计 designs/T-324-kongzhi-guimo.md §4 锁 3:
- 直构 gs(level=7 持控制规模)→ 满级门 applied=False reason='level_cap'
  零写 + 推进算子两件零推进(持卡状态副本等级轴 7 封顶);
- 无卡对照同参推进成功(跨 7 级断言——帽缺省 = MAX_PLAYER_LEVEL,
  门与算子对无卡局零扰);
- 边界 level=6 持卡升至 7 恰停(帽截断等级推进,溢出照常 cur 结转)。

建模语义 = 持卡生效的进度轴上限改写(cap-only,不回退已达等级;策略侧
lv 判据读注册表 level_max 系另一把尺,状态副本这一侧拒发与规划失配 = 决策质量
议题,本锁不辖)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
    report_action_close_shop_param,
    report_action_level_up_param,
    report_action_refresh_shop_param,
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    MAX_PLAYER_LEVEL,
    XP_PER_BUY,
    XP_TO_NEXT_LEVEL,
    xp_apply_amount,
    xp_apply_clicks,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopActionExecuted,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionLevelUpParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
)

_SIG = ChannelSig(family='logic_action', actor='CwActionLevelUpOp',
                  mode='compute')

_CARD = '控制规模'


def _hold(gs, cards: list[str]) -> None:
    """持卡播种(active_strategies 状态容器直写,终态契约单一源)。"""
    gs.write_logic(gs.active_strategies, list(cards),
                   produced_by='test', evidence='t:hold', sig=_SIG)


def _clicks_to(level: int) -> int:
    """恰跨 level 门槛的击数(表派生,禁手抄经验常数)。"""
    return XP_TO_NEXT_LEVEL[level] // XP_PER_BUY


def test_gate_blocks_at_held_cap_and_writes_nothing() -> None:
    """满级门随帽提前(锁 3 正面):level=7 持卡 → applied=False
    reason='level_cap',金/xp/level 零写(门在金写之前,整帧零投影)。"""
    gs = cw4_gs(gold=30, level=7, xp=(0, XP_TO_NEXT_LEVEL[7]))
    _hold(gs, [_CARD])
    gold_before = int(gs.gold.value)
    out = report_action_level_up_param(
        gs, SimpleNamespace(cost=0), _SIG,
        executed=SimpleNamespace(levelup_clicks=5))
    assert out.applied is False and out.reason == 'level_cap'
    assert int(gs.gold.value) == gold_before, '门拦截帧应零金写'
    assert int(gs.level.value) == 7 and int(gs.xp.value[0]) == 0, '零推进'


def test_no_card_control_advances_past_seven() -> None:
    """无卡对照(锁 3):同参(level=7 cur=0,恰跨门槛击数)无卡局跨 7
    升 8——帽缺省 = MAX_PLAYER_LEVEL,门与算子对无卡局零扰。"""
    gs = cw4_gs(gold=30, level=7, xp=(0, XP_TO_NEXT_LEVEL[7]))
    out = report_action_level_up_param(
        gs, SimpleNamespace(cost=0), _SIG,
        executed=SimpleNamespace(levelup_clicks=_clicks_to(7)))
    assert out.applied is True
    assert int(gs.level.value) == 8, f'无卡局应跨 7 升 8: {gs.level.value!r}'
    assert int(gs.xp.value[0]) == 0, '恰满门槛跨级清零'


def test_boundary_six_to_seven_stops_exactly() -> None:
    """边界(锁 3):level=6 持卡,超量击数推进恰停在 7(帽截断**推进**,
    不截累计——溢出留在当前级条内作 cur 结转,语义与无卡溢出结转同式,
    仅等级不再越 7)。"""
    gs = cw4_gs(gold=30, level=6, xp=(0, XP_TO_NEXT_LEVEL[6]))
    _hold(gs, [_CARD])
    clicks = _clicks_to(6) * 4
    out = report_action_level_up_param(
        gs, SimpleNamespace(cost=0), _SIG,
        executed=SimpleNamespace(levelup_clicks=clicks))
    assert out.applied is True
    assert int(gs.level.value) == 7, f'恰停 7: {gs.level.value!r}'
    assert int(gs.xp.value[0]) == clicks * XP_PER_BUY - XP_TO_NEXT_LEVEL[6], \
        '溢出结转进当前级条(帽只截等级推进)'


def test_operators_cap_param_zero_advance_at_cap() -> None:
    """推进算子两件帽形参(锁 3):xp_apply_clicks/xp_apply_amount 传
    level_cap=7 在 7 级零推进;缺省(无卡既有语义)对照推进成功。"""
    assert xp_apply_clicks(7, 0, 20, level_cap=7) == (7, 0)
    assert xp_apply_amount(7, 0, 500, level_cap=7) == (7, 0)
    assert xp_apply_clicks(7, 0, _clicks_to(7)) == (8, 0)
    assert xp_apply_amount(7, 0, XP_TO_NEXT_LEVEL[7]) == (8, 0)
    assert MAX_PLAYER_LEVEL == 10, '无卡缺省帽自证(语义单一源)'


# ============================================================ M1 投影直测(《商店黑板容器化方案》§4-M1;同 src 按被测方法归并)

# 改写依据(分诊):写入者登记面随「商店单动作循环纳入统一管理」演进——
# 生产写点 actor 现役 = CwScreenShop(cw_screen_shop,登记面已登记),
# 旧名 CwOpBuyCards 已退役;测试模拟生产写入随登记面改名。
_PROJ_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                       mode='compute', group_id='act:CwScreenShop@1')


def _gs_of(**axes):
    """M1 场景种子(原裸帧合成配方承接:节点整域不写、空店离屏;
    域覆盖集与原合成口逐域一致)。"""
    return cw4_gs(node_fill=False, shop_screen='off', **axes)


def _content_of(gs):
    """shop payload content 槽紧缩视图,槽序 (idx, name, star, cost);
    离屏(None)归一空表 = 旧紧缩列表等价读法(三态定长五槽模型,
    用户三态裁定 2026-09-13)。"""
    payload = gs.shop.value
    if payload is None:
        return []
    return [(i, s.card.name, s.card.star or 1, s.card.cost or 0)
            for i, s in enumerate(payload.cards)
            if s.kind == 'content' and s.card is not None]


def _bench_slots(gs):
    """bench 槽位占用签名,槽序 (idx, char_id, star);空槽跳过。"""
    view = gs.bench.value
    if view is None:
        return []
    return [(i, s.unit.char_id, s.unit.star)
            for i, s in enumerate(view.slots)
            if s.kind != 'empty' and s.unit is not None]


def _report_action(gs, action, executed=None):
    """商店域动作单次上报(生产同形):买牌快照三件组与升星分支内聚
    report 函数内,一动作恰一次调用;合计结果的逐域期望态由各案直测
    断言(设计件 §4-M1)。executed 仅对带回执参数的函数透传。"""
    if isinstance(action, CwActionBuyCardParam):
        return report_action_buy_card_param(gs, action, _PROJ_SIG,
                                            executed=executed)
    if isinstance(action, CwActionLevelUpParam):
        return report_action_level_up_param(gs, action, _PROJ_SIG,
                                            executed=executed)
    if isinstance(action, CwActionRefreshShopParam):
        return report_action_refresh_shop_param(gs, action, _PROJ_SIG,
                                                executed=executed)
    if isinstance(action, CwActionSellBenchParam):
        return report_action_sell_bench_param(gs, action, _PROJ_SIG)
    if isinstance(action, CwActionCloseShopParam):
        return report_action_close_shop_param(gs, action, _PROJ_SIG)
    raise AssertionError(f'未覆盖的商店动作类型:{type(action).__name__}')


def test_levelup_clicks_and_level_cross():
    """升级:击数×单击价扣金 + xp/level 推进(跨档结转 + level 跨档
    直写,与 prep 分支同款;域集扩申报 = SHOP_PROJECTION_DOMAINS 登记
    面);满级分支(并入):lv10 购买无效,零金零经验零写。"""
    gs = _gs_of(gold=30, shop=[], level=3, xp=(2, 6))
    _report_action(
        gs, CwActionLevelUpParam(cost=4), ShopActionExecuted(levelup_clicks=1))
    assert gs.gold.value == 26, 'gold: 期望 30 −单击价 4×1 击 = 26'
    assert _content_of(gs) == [], \
        'shop payload: 期望空(离屏零写透传)'
    assert _bench_slots(gs) == [], 'bench: 升级分支零写(保持全空)'
    # 2+4=6 ≥ lv3 门槛 4 → 升 lv4,溢出结转 cur=2,cap=lv4 门槛 6;
    # 数值与初值 (2, 6) 巧合相同(跨档结转非零写,升级分支实写 xp 域)。
    assert gs.xp.value == (2, 6), \
        'xp: 期望单击 +4 跨档结转 (2, lv4 门槛 6)'
    assert gs.level.value == 4, \
        'level: 跨档直写 3→4(xp_apply_clicks 单一源;等级滞留会让' \
        '下一击按旧级重算 = 花金零等级推进)'
    # 满级分支(并入,原 test_levelup_full_cap_noop):零金零经验零写
    gs_cap = _gs_of(gold=30, shop=[], level=10, xp=(0, 4))
    _report_action(
        gs_cap, CwActionLevelUpParam(cost=4),
        ShopActionExecuted(levelup_clicks=1))
    assert gs_cap.gold.value == 30, 'gold: 满级购买零金(购买无效)'
    assert _content_of(gs_cap) == [], \
        'shop payload: 期望空(离屏零写透传)'
    assert _bench_slots(gs_cap) == [], 'bench: 满级零写(保持全空)'
    assert gs_cap.xp.value == (0, 4), 'xp: 满级零经验(购买无效)'
    assert gs_cap.level.value == 10, '满级拒付(applied=False)零写'


def test_levelup_multi_level_jump_unlocks_seat_cap():
    """跨级连跳:多击连跳两级(溢出结转在 xp_apply_clicks 算子内)+
    level 直写到位;席位 cap 联动 = ``max_units_of`` 经读口自动跟随
    (level 为 cap 解锁地板,deploy_cap 未读时 base 取 level;部署环
    消费位零改动,写端修复即解锁)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        max_units_of,
    )
    gs = _gs_of(gold=30, shop=[], level=5, xp=(18, 20))
    assert max_units_of(gs) == 5, '前置:cap 地板 = 滞留级 5'
    _report_action(
        gs, CwActionLevelUpParam(cost=4), ShopActionExecuted(levelup_clicks=2))
    # 18+8=26 ≥ lv5 门槛 20 → 升 lv6 余 6;6 < lv6 门槛 40 → 停。
    assert gs.level.value == 6, 'level: 连跳直写 5→6(跨级不滞留)'
    assert gs.xp.value == (6, 40), 'xp: 溢出结转 (6, lv6 门槛 40)'
    assert max_units_of(gs) == 6, \
        '席位 cap 随 level 解锁 5→6(联动验证)'
    assert gs.gold.value == 22, 'gold: 30 −单击价 4×2 击 = 22'


def test_levelup_boundary_and_unread_pair_skip():
    """门槛边界:未达门槛零跨档(level 不写,xp 照推进);域级跳写对:
    level 未读帧推进对整体跳写(禁缺省 1 参与推进计算),gold 域
    独立照写。"""
    gs = _gs_of(gold=30, shop=[], level=5, xp=(15, 20))
    _report_action(
        gs, CwActionLevelUpParam(cost=4), ShopActionExecuted(levelup_clicks=1))
    assert gs.level.value == 5, 'level: 15+4=19 < 门槛 20 零跨档不写'
    assert gs.xp.value == (19, 20), 'xp: 推进到位 (19, 20)'
    # 域级跳写对:level 未读(level_unread 种子缺席)+ xp 已读
    gs2 = _gs_of(gold=30, shop=[], xp=(15, 20), level_unread=True)
    assert gs2.level.value is None and gs2.xp.value == (15, 20)
    seq0 = gs2.write_seq
    report_action_level_up_param(
        gs2, CwActionLevelUpParam(cost=4),
        _PROJ_SIG, executed=ShopActionExecuted(levelup_clicks=1))
    assert gs2.level.value is None, 'level 未读保持未读'
    assert gs2.xp.value == (15, 20) and gs2.xp.source == 'observation', \
        'level 未读 → 推进对整体跳写(禁缺省 1 参与推进计算;' \
        'xp 值留种子原值,source 不翻 logic)'
    assert gs2.gold.value == 26, 'gold 域独立于推进对照写'
    assert gs2.write_seq > seq0, '跳写对 ≠ 整动作零写(gold 仍落)'
