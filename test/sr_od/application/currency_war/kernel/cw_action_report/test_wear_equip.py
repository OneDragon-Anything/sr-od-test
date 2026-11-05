"""report_action_wear_equip_param 穿报测试·穿着即合成特权档边专测
(镜像 src = kernel/cw_action_report/wear_equip.py;零卡穿戴与槽位定位
既有断言住 test_action_report.py,本文件不与其混写)。

特权档合成边 = 融合召唤(id 332301)腿1,卡面「给角色穿戴2件相同进阶
装备时，它们会合成为对应的特权装备」。规则住 ``_wear_synthesis`` kernel
单一源,三门时点 = 门①持卡调用侧前置 / 门②「worn 现值同进阶对」门③
「对应特权件在册」都是特权档边循环内的逐轮边判定(前置闸读法下基础档
级联场景不可达)。样例对自注册表:碎星斩舰刀 recipes =
(('折叠小刀','折叠小刀'),) 系自配形——基础档预测层只走交叉配对
(``synthesize_target`` 不含自配,批前既有缺口非本卡引入),自配对作
零卡对照样例;武器大师 recipes = (('和平手枪','折叠小刀'),) 系交叉形,
作级联样例。特权件 category='特权' recipes 空,双档闭包天然终止。

特权档合成同属「合成装备时」事件 → 计入 merged 计数(持武力刷新局
每次特权档合成 +2 刷新,卡文字面直读,申报面非缺陷);零 rng 消费。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.kernel.cw_action_report.wear_equip import (
    report_action_wear_equip_param,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    privilege_counterpart,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    LogicOutcome,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_BINDINGS,
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionWearEquipParam,
)

_FUSE_CARD = '融合召唤'
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_ACT = ChannelSig(family='logic_action', actor='t', mode='compute')


def _gs_with_card(card: str | None, worn: list[str],
                  owned: list[str]) -> GameState:
    """观察面组装:deployed 前排 1 号位单位携 worn 集追加穿戴件;持卡局
    write_logic 播种 active_strategies(持卡判定基底,cw_game_state
    Field[list[str]])。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.deployed, DeployedView(
        front_slots=[Unit(char_id='希儿', star=1, equips=list(worn))]
        + [None] * 3,
        back_slots=[None] * 6), sig=_SIG_OBS)
    gs.observe(gs.equips, list(owned), sig=_SIG_OBS)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', sig=_SIG_ACT)
    return gs


def _wear(gs: GameState, item: str) -> LogicOutcome:
    return report_action_wear_equip_param(
        gs, CwActionWearEquipParam(item_name=item, char_name='希儿',
                                   row='front', slot=1), _SIG_ACT)


def test_wear_same_advance_pair_fuses_privilege() -> None:
    """特权档行为锁·正支(持卡局):deployed 单位 worn ['碎星斩舰刀'] +
    wear '碎星斩舰刀' → 同进阶对合成为对应特权件;evidence 带
    ``wear_worn|fuse_privilege`` 后缀(卡闸行为可审计);owned 摘件。"""
    assert EQUIPMENTS['碎星斩舰刀'].category == '进阶'
    assert privilege_counterpart('碎星斩舰刀') in EQUIPMENTS
    gs = _gs_with_card(_FUSE_CARD, worn=['碎星斩舰刀'],
                       owned=['碎星斩舰刀'])
    out = _wear(gs, '碎星斩舰刀')
    assert out.applied is True
    unit = gs.deployed.value.front_slots[0]
    assert list(unit.equips) == ['碎星斩舰刀·特权'], '同进阶对 → 对应特权件'
    assert list(gs.equips.value) == [], 'owned 摘件(穿戴原子)'
    assert gs.deployed.evidence == 'wear_worn|fuse_privilege', \
        '特权档合成 evidence 后缀可审计'
    assert gs.deployed.source == 'logic'


def test_wear_same_pair_without_card_keeps_both() -> None:
    """特权档行为锁·零卡对照:同输入零卡局逐位旧形态——同名对非交叉
    配方(基础档边不触发)且特权档边零感知 → 两件共存零合成,
    evidence 原形无后缀。"""
    gs = _gs_with_card(None, worn=['碎星斩舰刀'], owned=['碎星斩舰刀'])
    out = _wear(gs, '碎星斩舰刀')
    assert out.applied is True
    unit = gs.deployed.value.front_slots[0]
    assert list(unit.equips) == ['碎星斩舰刀', '碎星斩舰刀'], '零卡零合成'
    assert gs.deployed.evidence == 'wear_worn', '基础档 evidence 原形'


def test_wear_cross_cascade_reaches_privilege_fixed_point() -> None:
    """双档级联不动点锁:基础档交叉配对(和平手枪+折叠小刀 → 武器大师)
    的产物与 worn 既有武器大师凑成同进阶对 → 特权档边在不动点循环内
    逐轮求值可达(本锁即验证门②③时点定义,前置闸读法下级联不可达);
    闭包收敛单终态。"""
    assert EQUIPMENTS['武器大师'].recipes == (('和平手枪', '折叠小刀'),)
    gs = _gs_with_card(_FUSE_CARD, worn=['和平手枪', '武器大师'],
                       owned=['折叠小刀'])
    out = _wear(gs, '折叠小刀')
    assert out.applied is True
    unit = gs.deployed.value.front_slots[0]
    assert list(unit.equips) == ['武器大师·特权'], '双档级联收敛单终态'
    assert gs.deployed.evidence == 'wear_worn|fuse_privilege'


def test_wear_same_simple_pair_no_blind_concat() -> None:
    """门③键域阴性:同名对为非进阶件(简易)→ 特权档边不产盲拼接产物
    (后缀映射为拼接非查表,键域保证 = 类别校验 + 特权件在册校验,
    在边判定内非前置闸);行为与零卡局同形。"""
    assert EQUIPMENTS['折叠小刀'].category == '简易'
    gs = _gs_with_card(_FUSE_CARD, worn=['折叠小刀'], owned=['折叠小刀'])
    out = _wear(gs, '折叠小刀')
    assert out.applied is True
    unit = gs.deployed.value.front_slots[0]
    assert list(unit.equips) == ['折叠小刀', '折叠小刀'], \
        '非进阶同名对不合成(禁无意义拼接入账)'
    assert gs.deployed.evidence == 'wear_worn'


def test_fusion_summon_registration_consolidated() -> None:
    """登记对拍汇总(四把存量锁就地扩集的卡级收口,防扩集漏项):箱腿
    注册形状(GRANTS 条目 items 直读 + 镜像表逐对相等 + PICK 工厂键)
    与腿1 零登记面(STRATEGY_EFFECTS / STRATEGY_BINDINGS 双缺席)同点
    钉死;计数 = 各存量锁扩集后的现值。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_BOX_GRANTS,
        PICK_INVEST_EFFECTS,
    )
    grant = STRATEGY_GRANTS['融合召唤']
    assert grant.items_immediate == ('简易武装箱',), '箱腿卡文直读'
    assert grant.chars_immediate == () and grant.chars_conditional == (), \
        'items-only 合法形态(箱腿正面形)'
    assert _STRATEGY_BOX_GRANTS['融合召唤'] == ('简易武装箱',), \
        '镜像表与登记表逐对相等'
    assert '融合召唤' in PICK_INVEST_EFFECTS, '工厂自动占 PICK 键'
    assert len(STRATEGY_GRANTS) == 106
    assert len(PICK_INVEST_EFFECTS) == 156
    assert len(_STRATEGY_BOX_GRANTS) == 13
    assert '融合召唤' not in STRATEGY_EFFECTS, \
        '腿1 零登记(TriggerKind 无穿戴事件成员,死条目主体更紧)'
    assert '融合召唤' not in STRATEGY_BINDINGS, \
        '效果主语全装备,不绑(绑定判据:泛用装备 → 不绑)'
