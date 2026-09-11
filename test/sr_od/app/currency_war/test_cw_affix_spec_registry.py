"""test_cw_affix_spec_registry —— 词缀源效果结构化注册 + 装备改写成员扫描申报锁。

被测 = kernel/cw_affix_effects.py(AFFIX_EFFECT_SPECS/AFFIX_SPEC_EXEMPT/
scan_rewrite_affixes/scan_rewrite_equipments/EQUIP_REWRITE_DECLARATIONS)
与 kernel/cw_effect_inventory.py 的词缀源登记端(register_affix/SOURCE_* 词表/
by_source)。

锁四件事:
1. **词缀规格值锁**(登记门):会改写 BoardState 字段的三条词缀(成长的烦恼/
   变宝为废/永久创伤)的结构化数值与触发面——数值即设计内容(效果写入归属
   判据:确定性→逻辑写 / 随机→观察收口),改值须同步归属语义再跟绿;
2. **词缀源登记端行为锁**:register_affix 产 source='affix' 条目,与策略源
   同册分源可读(by_source),余期播种与策略源同轨;
3. **覆盖恰等锁(词缀)**:谓词扫描命中集 == SPEC ∪ EXEMPT——运行时采集
   (write_affix_effects)追加新改写词缀未申报时,此锁红强制评审;
4. **覆盖恰等锁(装备)**:scan_rewrite_equipments 命中集 ==
   EQUIP_REWRITE_DECLARATIONS,加**具名代表在扫锁**(防「谓词与申报表同时
   删行」的合谋收缩——恰等锁两向各自绿,召回面靠代表锚看管)。

键域合法性(键 ⊆ affix_effects_data ∧ id/name==键)由生产模块 import 即炸
校验单一承责(`_validate_affix_specs`,cw_affix_effects),测试面不设重复锁
——违例时本模块收集期即炸,测试体永不独立执行到断言。

开局不利走豁免(专用写端载体 cw_opening_hp._AFFIX_HP_DELTA,ADR-0559):
本文件锁「豁免条目在册 ∧ 载体键在」防悬空豁免,数值归载体主题锁
test_cw_opening_hp_prior。

出处:统一 state 迭代 BoardState 数据结构设计
docs/develop/sr_od/application/currency_war/changes/2026-09-11-unified-state/
details/BoardState-数据结构设计.md §5.1(词缀效果辖域申报)/§5.3(写入归属
判据)/§7(扫描范围源 c/源 e);开局不利数值 = ADR-0559。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_affix_effects import (
    AFFIX_EFFECT_SPECS,
    AFFIX_SPEC_EXEMPT,
    EQUIP_REWRITE_DECLARATIONS,
    scan_rewrite_affixes,
    scan_rewrite_equipments,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    SOURCE_AFFIX,
    ActiveEffectInventory,
    DurationKind,
    EffectKind,
    EffectSpec,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
    EconomyEffect,
)
from sr_od.application.currency_war.kernel.cw_opening_hp import _AFFIX_HP_DELTA

# 同次运行只算一次(锁契约:重结果一次复用)
_AFFIX_SCAN = scan_rewrite_affixes()
_EQUIP_SCAN = scan_rewrite_equipments()


# ==================== 1. 词缀规格值锁(登记门) ====================

def test_chengzhang_fannao_levelup_gold_face() -> None:
    """成长的烦恼 = LevelUp 金面改写源:8 级起每次购经验 +1 金。

    确定性 → 归属 = 逻辑写;predict 开(买经验成本对账须预知)。
    """
    spec = AFFIX_EFFECT_SPECS['成长的烦恼']
    assert spec.trigger == TriggerKind.CONDITIONAL
    assert spec.category == EffectKind.ECONOMY
    assert spec.payload.xp_click_surcharge_from_level == 1
    assert spec.payload.xp_click_surcharge_from_level_at == 8
    assert spec.duties.predict
    assert '逻辑写' in spec.notes


def test_bianbaoweifei_equip_junk_face() -> None:
    """变宝为废 = 装备库存改写源:每位面首次合成进阶装备 50% 变垃圾袋。

    随机面 → 不建逻辑写端(观察收口);predict 开(装备合成期望对账须预知
    垃圾袋分支);ON_MERGE 与武力刷新同装备合成触发面。
    """
    spec = AFFIX_EFFECT_SPECS['变宝为废']
    assert spec.trigger == TriggerKind.ON_MERGE
    assert spec.category == EffectKind.BATTLEFIELD
    assert spec.payload.first_merge_equip_junk == 0.5
    assert spec.duties.predict
    assert '观察收口' in spec.notes


def test_yongjiuchuangshang_hpmax_face() -> None:
    """永久创伤 = hp_max 词缀源:损血 20% 计入生命上限损耗、至多 60%。

    hp_max 字段缺位 → 观察收口,数值仅建档(零响应,不设 duties 位)。
    """
    spec = AFFIX_EFFECT_SPECS['永久创伤']
    assert spec.category == EffectKind.STATE
    assert spec.payload.hp_max_loss_pct_of_loss == 20
    assert spec.payload.hp_max_loss_cap_pct == 60
    assert not (spec.duties.predict or spec.duties.respond or spec.duties.track)
    assert '观察收口' in spec.notes


# ==================== 2. 词缀源登记端行为锁 ====================

def test_register_affix_and_strategy_sources_separated() -> None:
    """词缀源登记端行为锁(register_affix):①产 source='affix' 条目
    (schema 词表值 = ActiveEffect.source 预留位的启用面),与策略源
    (register_strategy 仍产 'strategy')同册互不混,by_source 分源可读
    ——词缀修饰与策略修饰的写端消费按来源分面取;first 以词缀名为键
    (spec.id = 词缀键)。②余期播种与策略源同轨:N_NODES → remaining_nodes;
    duration_uses>0 → remaining_uses(同一 _seed_progress 路径)——词缀
    现役条目无时限/次数形,播种轨用合成 spec 验证。"""
    inv = ActiveEffectInventory()
    affix_entry = inv.register_affix(AFFIX_EFFECT_SPECS['成长的烦恼'], acquired_t=5)
    strat_entry = inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    assert SOURCE_AFFIX == 'affix'
    assert affix_entry.source == 'affix'
    assert strat_entry.source == 'strategy'
    assert [e.spec.id for e in inv.by_source('affix')] == ['成长的烦恼']
    # 键域双约定:策略源 spec.id=plaza 数字 id,词缀源 spec.id=词缀名(无 plaza 命名空间)
    assert [e.spec.id for e in inv.by_source('strategy')] == ['102001']
    assert inv.first('成长的烦恼') is affix_entry
    # 词缀条目余期播种不因来源而异(现役三条均 WHILE_HELD → 双余期 None)
    assert affix_entry.remaining_nodes is None and affix_entry.remaining_uses is None
    # 播种轨(合成 spec):N_NODES → remaining_nodes 播种,与策略源同一路径
    timed = EffectSpec(id='词缀时限形', name='词缀时限形',
                       trigger=TriggerKind.NODE_ENTER, duration=DurationKind.N_NODES,
                       category=EffectKind.ECONOMY, payload=EconomyEffect(),
                       duration_nodes=3)
    timed_entry = inv.register_affix(timed, acquired_t=1)
    assert timed_entry.remaining_nodes == 3
    assert timed_entry.remaining_uses is None


# ==================== 3. 覆盖恰等锁(词缀) ====================

def test_affix_scan_coverage_exact() -> None:
    """谓词扫描命中集 == SPEC ∪ EXEMPT(零「无归属改写词缀」):
    运行时采集追加新词缀 → 命中集扩大 → 红指向「补 SPEC 或补豁免理由」;
    删谓词关键词 → 命中集缩小 → 红指向「召回面收窄须带理由」。"""
    managed = set(AFFIX_EFFECT_SPECS) | set(AFFIX_SPEC_EXEMPT)
    assert set(_AFFIX_SCAN) == managed, (
        f'词缀改写源覆盖缺口:未申报={sorted(set(_AFFIX_SCAN) - managed)} '
        f'申报未命中={sorted(managed - set(_AFFIX_SCAN))}(补 '
        f'AFFIX_EFFECT_SPECS 或 AFFIX_SPEC_EXEMPT,禁删谓词词表硬凑绿)')


def test_kaiju_buli_exemption_carrier_alive() -> None:
    """开局不利豁免条目在册 ∧ 专用写端载体键在(悬空豁免防线):豁免理由
    指向 cw_opening_hp._AFFIX_HP_DELTA(ADR-0559);数值不在此锁——行为级
    等价锁在载体主题文件 test_cw_opening_hp_prior(opening_hp_prior 值断言),
    值漂移由该锁红,本条只防「豁免在册而载体消失」。"""
    assert '开局不利' in AFFIX_SPEC_EXEMPT
    assert '开局不利' in _AFFIX_HP_DELTA


# ==================== 4. 覆盖恰等锁(装备)+ 具名代表 ====================

def test_equip_scan_coverage_exact() -> None:
    """装备改写成员:谓词扫描命中集 == 申报表(逐件写入归属,零静默)。"""
    assert set(_EQUIP_SCAN) == set(EQUIP_REWRITE_DECLARATIONS), (
        f'装备改写成员申报缺口:未申报={sorted(set(_EQUIP_SCAN) - set(EQUIP_REWRITE_DECLARATIONS))} '
        f'申报未命中={sorted(set(EQUIP_REWRITE_DECLARATIONS) - set(_EQUIP_SCAN))}')


def test_equip_scan_named_representatives() -> None:
    """具名代表在扫锁(召回面锚):金/生命族代表(财富宝钻/财富/罪孽王冠/
    诅咒·阿瓦隆)与单位族代表(数据拷贝仪/分身墨镜)必须在扫——防「谓词与
    申报表同时删行」的合谋收缩(恰等锁对此合谋不红)。"""
    for name in ('财富宝钻', '财富', '罪孽王冠', '诅咒·阿瓦隆',
                 '数据拷贝仪', '分身墨镜'):
        assert name in _EQUIP_SCAN, f'具名改写成员 {name} 脱扫描(谓词召回面收窄?)'
