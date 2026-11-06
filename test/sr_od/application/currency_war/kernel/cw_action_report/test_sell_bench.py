"""sell_bench 溢出分支入位身份守恒测试(镜像 src =
kernel/cw_action_report/sell_bench.py;同 src 兄弟测试 =
kernel/test_gain_chain.py 卖牌段〔已登记超限文件,只读复用不追加〕)。

测试面依据 = 迭代 T-39 专家研讨会设计(.debug/progress/2026-09-23-invest-
effects-calc/designs/T-39-zhuanjia-yantaohui.md)§2.4.3 + §4 锁 5:
溢出往返身份守恒——overflow_warning + overflow_card='专家邀请函' → 卖牌
腾槽入位 = bookcard 带名槽件;='简易武装箱' → supply_box 带名(回归);
角色名 → unit 分支(回归)。入位构造 = 词表守卫保留 + 查映射带名槽件
(身份守恒闭环:发放带名落席 → 溢出字符串(名字本身)→ 入位槽带名)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
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
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    seed_opening_state,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionLevelUpParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
)

_SIG = ChannelSig(family='logic_action', actor='SellBenchTest', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='SellBenchTest')


def _make_gs_full_bench() -> GameState:
    """种子初始值 + 9 满席(1★ 希儿 ×9,无装备无三连)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1))
               for _ in range(9)], capacity=9), sig=_SIG_OBS)
    return gs


def _sell_slot0(gs: GameState) -> None:
    out = report_action_sell_bench_param(
        gs, SimpleNamespace(bench_idx=0, expect='', reason='t'), _SIG)
    assert out.applied


def test_sell_absorbs_overflow_bookcard_named_slot() -> None:
    """溢出邀请函入位(设计 §2.4.3 + §4 锁 5):席满 + 溢出位 = 专家邀请函
    → 卖牌腾槽入位 = bookcard 带名槽件(kind+item 逐位),溢出两字段成对
    清写——邀请函全旅程 bookcard/名不漂。"""
    gs = _make_gs_full_bench()
    gs.observe(gs.overflow_card, '专家邀请函', sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    _sell_slot0(gs)
    slot = gs.bench.value.slots[0]
    assert (slot.kind, slot.item) == ('bookcard', '专家邀请函'), \
        f'入位带名槽件: {(slot.kind, slot.item)}'
    assert gs.overflow_card.value == '' \
        and gs.overflow_warning.value is False, '溢出两字段成对清写'


def test_sell_absorbs_overflow_box_named_slot_regression() -> None:
    """溢出箱入位回归(设计 §4 锁 5):溢出位 = 简易武装箱 → supply_box
    带名槽件(原写死 supply_box 行为逐位等价 + 名字随行)。"""
    gs = _make_gs_full_bench()
    gs.observe(gs.overflow_card, '简易武装箱', sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    _sell_slot0(gs)
    slot = gs.bench.value.slots[0]
    assert (slot.kind, slot.item) == ('supply_box', '简易武装箱')


def test_sell_absorbs_overflow_char_unit_leg_regression() -> None:
    """角色入账分支回归(设计 §4 锁 5):溢出位 = 角色名(词表外)→ 入位 unit
    槽件星级 1 兜底;item 恒 None(词表守卫保留,行为不变)。"""
    gs = _make_gs_full_bench()
    gs.observe(gs.overflow_card, '银狼', sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    _sell_slot0(gs)
    slot = gs.bench.value.slots[0]
    assert slot.kind == 'unit' and slot.unit is not None
    assert (slot.unit.char_id, slot.unit.star) == ('银狼', 1)
    assert slot.item is None, 'unit 槽 item 恒 None'


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


def test_sell_bench_refund():
    """卖备战席:bench −该牌 + gold +退款(sell_refund 基准)。"""
    gs = _gs_of(gold=10, shop=[], bench=[_bc('希儿', star=1)])
    _report_action(gs, CwActionSellBenchParam(bench_idx=0, income=3))
    assert gs.gold.value == 13, \
        'gold: 期望 10 +退款 3(1★ 希儿 sell_refund 现算)'
    assert _content_of(gs) == [], \
        'shop payload: 期望空(shop 空表帧 = 离屏,零写透传)'
    assert _bench_slots(gs) == [], 'bench: 期望卖出槽置空(9 槽全空)'
    assert gs.xp.value is None, 'xp: 卖分支零写(未读域保持种子初值 None)'


def test_stale_sell_proposal_no_write():
    """陈旧卖出提案(空槽/越界):守卫辖面,拒绝 = applied=False 零写。
    (集外动作型零写分支删:上报函数族每动作恰一函数,无按类型聚合的
    登记面可「静默纳入集外型」——闭集性质归命名规约完备测试
    test_action_report 辖。)"""
    gs = _gs_of(gold=30, shop=[])
    seq0 = gs.write_seq
    report_action_sell_bench_param(
        gs, CwActionSellBenchParam(bench_idx=0, income=3), _PROJ_SIG)
    assert gs.write_seq == seq0
