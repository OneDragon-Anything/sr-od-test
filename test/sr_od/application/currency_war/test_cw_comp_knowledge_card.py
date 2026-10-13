"""CW 线知识卡三字段锁（3.0b 建表批；line_and_upgrade §1.2/§1.4/§1.5）。

锁面（设计约定，非逐字段断言）：
① schema：COMP_LIBRARY 全 20 线三字段非空，角色型每线在册——角色型是唯一恒可判定的
   硬规则路径（策略型可空表 = 无策略定义线走角色型/时点兜底，§1.4 表语义）；
② 名字空间：角色类名单 ⊆ cw_chars 注册表键、策略型名 ⊆ 投资注册表名——手编建表的
   笔误防线（写错名 = 判定永不命中且静默）；
③ CARRY 锚派生：plaza_carry 非空直用（聚类对拍锚不覆写）、空值 3 线走攻略补全登记
   （CARRY_ANCHOR_FALLBACK，§1.2 派生申报）；
④ 单帧锁：构造持有状态 → char_lock_hit 全组合命中/缺一未命中（AND 语义）、
   strategy_lock_hit 任一命中（OR 语义）+ OCR 间隔号形变归一仍命中。

对拍依据（need_star × star_goals 冲突裁决）= 迭代目录
`.debug/progress/2026-10-12-prep-shop-workflow-redesign/knowledge_card_30b/对拍记录.md`，
不入测试断言（数据文档面非行为面）。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_invest_data import (
    PLAZA_AUGMENTS,
    PLAZA_PORTALS,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    CARRY_ANCHOR_FALLBACK,
    COMP_LIBRARY,
    carry_anchor,
    char_lock_hit,
    strategy_lock_hit,
)


def test_knowledge_card_schema_nonempty_all_lines():
    """① 三字段全 20 线非空；角色型每线在册（判据「lock_rules 角色型按持有状态
    可判定」的前提 = 每线有可判定的角色组合）；策略型两键齐（值可空表）。"""
    assert len(COMP_LIBRARY) == 20
    for comp in COMP_LIBRARY:
        assert comp.lock_rules, comp.name
        assert comp.lock_rules.get('角色型'), comp.name
        assert '策略型' in comp.lock_rules, comp.name
        assert comp.need_star, comp.name
        assert comp.key_items, comp.name


def test_knowledge_card_names_in_registries():
    """② 名单/键全落注册表键空间：角色名 ⊆ CHARACTERS、策略型名 ⊆ 投资注册表
    （augment+portal 并集）。建表是手编数据，名字写错 = 锁定判定永不命中。"""
    invest_names = ({a.name for a in PLAZA_AUGMENTS}
                    | {p.name for p in PLAZA_PORTALS})
    for comp in COMP_LIBRARY:
        for rule in comp.lock_rules['策略型']:
            assert rule in invest_names, (comp.name, rule)
        for name in (*comp.lock_rules['角色型'], *comp.need_star, *comp.key_items):
            assert name in CHARACTERS, (comp.name, name)


def test_carry_anchor_plaza_first_fallback_registered():
    """③ 锚派生口径（§1.2）：plaza_carry 非空直用；空值线恰为攻略补全登记的
    3 线（银枝/飞霄/桑博，依据 = CARRY_ANCHOR_FALLBACK 就地注释）。"""
    for comp in COMP_LIBRARY:
        anchor = carry_anchor(comp)
        assert anchor, comp.name
        if comp.plaza_carry:
            assert anchor == comp.plaza_carry, comp.name
    assert set(CARRY_ANCHOR_FALLBACK) == {
        c.name for c in COMP_LIBRARY if not c.plaza_carry}
    assert (CARRY_ANCHOR_FALLBACK['银枝群攻'] == '银枝'
            and CARRY_ANCHOR_FALLBACK['追击飞霄'] == '飞霄'
            and CARRY_ANCHOR_FALLBACK['专家桑博DOT'] == '桑博')


def test_char_lock_hit_and_semantics():
    """④ 角色型单帧锁：全组合在手命中、缺任一未命中（AND = §1.4「关键角色组合
    到手」）；无关持有不命中（万敌线 3 件组合，对拍记录一节登记）。"""
    wandi = next(c for c in COMP_LIBRARY if c.name == '万敌单C')
    combo = wandi.lock_rules['角色型']
    assert len(combo) == 3   # 万敌+千冶·刃+刻律德菈(final_wandi 构造机理§2)
    assert char_lock_hit(wandi, set(combo))
    for missing in combo:
        assert not char_lock_hit(wandi, set(combo) - {missing})
    assert not char_lock_hit(wandi, {'希儿', '花火'})


def test_strategy_lock_hit_any_and_ocr_normalization():
    """④ 策略型任一命中（OR = §1.4「策略定义线」）；OCR 间隔号形变（•→·）
    经归一仍命中（run_20260826_004527 缺陷链同型防线）。"""
    jing = next(c for c in COMP_LIBRARY if c.name == '景元仙舟')
    assert strategy_lock_hit(jing, {'飞光·映月'})
    assert strategy_lock_hit(jing, {'嘴硬', '飞光·传剑'})   # 多持有任一命中
    assert not strategy_lock_hit(jing, {'嘴硬'})
    assert strategy_lock_hit(jing, {'飞光•映月'})   # OCR bullet 形变归一命中
