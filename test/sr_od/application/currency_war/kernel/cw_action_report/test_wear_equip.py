"""report_action_wear_equip_param 穿报测试·穿着即合成特权档边专测
(镜像 src = kernel/cw_action_report/wear_equip.py;零卡穿戴与槽位定位
既有断言住 test_action_report.py,本文件不与其混写)。

特权档合成边 = 融合召唤(id 332301)效果条目1,卡面「给角色穿戴2件相同进阶
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

刃锻特权化支 = 锻冶专家:刃(id 360601)效果条目2,卡面「在【刃】的装备栏
中合成进阶装备时，将其变为特权装备，该效果可生效1次」——合成触发特权
变换族第二成员(融合召唤姊妹卡,异构形:基础档产物特权化 + 刃栏辖域 +
次数账限次)。门③ 产物判定 = 名字计数差分(重名场景锁在册:名字集差
∅ 而计数差 1 仍触发),多产物 × 次数不足按 worn 序最左优先;样例对 =
步步生花 recipes = (('生命之花','轮滑鞋'),)(基础档交叉形),类别门
样例 = 好运来转换产物好运令牌(工具类产物零变换;合成图谱按类别排除
星徽/宝钻配方,钻系样例在穿着即合成层不可达)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.kernel.cw_action_report.wear_equip import (
    report_action_wear_equip_param,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    FORGE_PRIVILEGE_CARD,
    FORGE_PRIVILEGE_CHAR,
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


def _gs_with_card(card: str | list[str] | None, worn: list[str],
                  owned: list[str], *, char: str = '希儿',
                  charges: int | None = None) -> GameState:
    """观察面组装:deployed 前排 1 号位单位携 worn 集追加穿戴件;持卡局
    write_logic 播种 active_strategies(持卡判定基底,cw_game_state
    Field[list[str]];多卡传列表)。charges 非 None 时播种次数账(次数
    耗尽锁用;None = Field 缺省承载值即开局态,零置位)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.deployed, DeployedView(
        front_slots=[Unit(char_id=char, star=1, equips=list(worn))]
        + [None] * 3,
        back_slots=[None] * 6), sig=_SIG_OBS)
    gs.observe(gs.equips, list(owned), sig=_SIG_OBS)
    if card is not None:
        cards = card if isinstance(card, list) else [card]
        gs.write_logic(gs.active_strategies, cards,
                       produced_by='test-seed', sig=_SIG_ACT)
    if charges is not None:
        gs.write_logic(gs.forge_privilege_charges_left, charges,
                       produced_by='test-seed', sig=_SIG_ACT)
    return gs


def _wear(gs: GameState, item: str, *, char: str = '希儿') -> LogicOutcome:
    return report_action_wear_equip_param(
        gs, CwActionWearEquipParam(item_name=item, char_name=char,
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
    与效果条目1 零登记面(STRATEGY_EFFECTS / STRATEGY_BINDINGS 双缺席)同点
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
    assert len(PICK_INVEST_EFFECTS) == 167
    assert len(_STRATEGY_BOX_GRANTS) == 14
    assert '融合召唤' not in STRATEGY_EFFECTS, \
        '效果条目1 零登记(TriggerKind 无穿戴事件成员,死条目主体更紧)'
    assert '融合召唤' not in STRATEGY_BINDINGS, \
        '效果主语全装备,不绑(绑定判据:泛用装备 → 不绑)'


# ===== 刃锻特权化支(锻冶专家:刃效果条目2;设计锁 1-4)=====


def test_wear_forge_converts_advance_product() -> None:
    """刃锻行为锁·正支:持卡 + 次数账缺省 1(Field 缺省承载基础次数,
    零置位)+ 刃(部署域)身上 [生命之花] 穿 [轮滑鞋] → 基础档合成
    产物特权化([步步生花·特权]) + 次数 −1 + owned 摘件 + evidence
    带 ``forge_privilege`` 后缀段;次数扣减 = 独立 evidence 笔。"""
    assert EQUIPMENTS['步步生花'].recipes == (('生命之花', '轮滑鞋'),)
    assert privilege_counterpart('步步生花') in EQUIPMENTS
    gs = _gs_with_card(FORGE_PRIVILEGE_CARD, worn=['生命之花'],
                       owned=['轮滑鞋'], char=FORGE_PRIVILEGE_CHAR)
    assert gs.forge_privilege_charges_left.value == 1, \
        'Field 缺省承载基础次数(零置位开局态)'
    out = _wear(gs, '轮滑鞋', char=FORGE_PRIVILEGE_CHAR)
    assert out.applied is True
    unit = gs.deployed.value.front_slots[0]
    assert list(unit.equips) == ['步步生花·特权'], \
        '基础档合成产物 → 对应特权件'
    assert list(gs.equips.value) == [], 'owned 摘件(穿戴原子)'
    assert gs.forge_privilege_charges_left.value == 0, '次数扣减'
    assert gs.forge_privilege_charges_left.evidence \
        == 'forge_privilege_consume', '次数扣减独立 evidence 笔'
    assert gs.deployed.evidence == 'wear_worn|forge_privilege', \
        '刃锻 evidence 后缀段可审计'


def test_wear_forge_duplicate_product_still_converts() -> None:
    """重名场景锁:刃栏已有步步生花,再合成第二个步步生花 → 名字集差
    = ∅ 而计数差 = 1,门③ Counter 正增量判定下特权化仍触发(名字集
    差分读法漏检全部该形合成)。终态序 = worn 序最左优先(多产物 ×
    次数不足变换序的确定性规则,单产物场景同一规则定左位)。"""
    gs = _gs_with_card(FORGE_PRIVILEGE_CARD,
                       worn=['步步生花', '生命之花'],
                       owned=['轮滑鞋'], char=FORGE_PRIVILEGE_CHAR)
    out = _wear(gs, '轮滑鞋', char=FORGE_PRIVILEGE_CHAR)
    assert out.applied is True
    unit = gs.deployed.value.front_slots[0]
    assert list(unit.equips) == ['步步生花·特权', '步步生花'], \
        '名字集差 ∅ 场景特权化仍触发,左序定变换位'
    assert gs.forge_privilege_charges_left.value == 0, '次数恰耗 1'


def test_wear_forge_exhausted_charges_keeps_advance() -> None:
    """次数耗尽锁:charges=0(直构播种)同穿戴 → 产物照常进阶零变换
    零扣减(门④ 关闭),evidence 原形无后缀。"""
    gs = _gs_with_card(FORGE_PRIVILEGE_CARD, worn=['生命之花'],
                       owned=['轮滑鞋'], char=FORGE_PRIVILEGE_CHAR,
                       charges=0)
    out = _wear(gs, '轮滑鞋', char=FORGE_PRIVILEGE_CHAR)
    assert out.applied is True
    unit = gs.deployed.value.front_slots[0]
    assert list(unit.equips) == ['步步生花'], '产物照常进阶零变换'
    assert gs.forge_privilege_charges_left.value == 0, '零扣减'
    assert gs.deployed.evidence == 'wear_worn', '零变换无后缀段'


def test_wear_forge_category_gate_blocks_non_advance() -> None:
    """类别门锁:非进阶产物零变换零扣减(门③ 进阶类别门)。可达样例形
    = 持好运来 + 锻冶专家:刃,基础档产物步步生花经合成转换预测面改写
    为好运令牌(工具类)——计数差非零而类别门拦截,特权化零触发。
    (合成图谱按类别排除星徽/宝钻配方,设计稿红钻+折叠小刀样例在穿着
    即合成层不可达,锁面样例按现值图谱取可达形。)"""
    assert EQUIPMENTS['好运令牌'].category == '工具'
    gs = _gs_with_card(['好运来', FORGE_PRIVILEGE_CARD],
                       worn=['生命之花'], owned=['轮滑鞋'],
                       char=FORGE_PRIVILEGE_CHAR)
    out = _wear(gs, '轮滑鞋', char=FORGE_PRIVILEGE_CHAR)
    assert out.applied is True
    unit = gs.deployed.value.front_slots[0]
    assert list(unit.equips) == ['好运令牌'], \
        '合成照常,产物经转换改写为工具类'
    assert gs.forge_privilege_charges_left.value == 1, \
        '非进阶产物零变换零扣减'
    assert gs.deployed.evidence == 'wear_worn', '零变换无后缀段'


def test_wear_forge_non_ren_unit_no_trigger() -> None:
    """非刃栏零触发锁:同持卡同缺省次数,穿戴目标非刃 → 合成照常
    零变换零扣减(门② 刃栏辖域)。"""
    gs = _gs_with_card(FORGE_PRIVILEGE_CARD, worn=['生命之花'],
                       owned=['轮滑鞋'])
    out = _wear(gs, '轮滑鞋')
    assert out.applied is True
    assert list(gs.deployed.value.front_slots[0].equips) == ['步步生花']
    assert gs.forge_privilege_charges_left.value == 1, \
        '非刃栏零触发零扣减'
    assert gs.deployed.evidence == 'wear_worn'


def test_wear_forge_without_card_keeps_advance() -> None:
    """零卡对照:同输入零卡局逐位旧形态——合成照常进阶零变换,次数账
    缺省值零扰(无卡局不消费零行为差)。"""
    gs = _gs_with_card(None, worn=['生命之花'], owned=['轮滑鞋'],
                       char=FORGE_PRIVILEGE_CHAR)
    out = _wear(gs, '轮滑鞋', char=FORGE_PRIVILEGE_CHAR)
    assert out.applied is True
    assert list(gs.deployed.value.front_slots[0].equips) == ['步步生花']
    assert gs.forge_privilege_charges_left.value == 1, '零卡零扣减'
    assert gs.deployed.evidence == 'wear_worn'
