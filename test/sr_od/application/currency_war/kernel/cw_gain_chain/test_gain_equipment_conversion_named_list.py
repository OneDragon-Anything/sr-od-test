"""独家代言(331401)装备获得转换·名单集源形锁(镜像 src =
kernel/cw_gain_chain.py 的 ``_equip_gain_conversion_hit`` 名单集源形判定支
+ 名单定向 > 类别词分派序 + gain_equipment 顶段装备目标分支;按被测方法
拆目录规范落位——test_gain_chain.py 已登记超限冻结禁追加,新锁落新镜像;
先例 = 同目录 test_gain_equipment_conversion_equip_target.py〔好运来族〕)。

测试面依据 = 迭代设计 designs/T-372-dujia-daiyan.md §4 +
REVIEW-T372 §4④ 测试锁面(2026-11-05 判定窗现值):
- 锁 1 镜像一致性:登记表 equips_immediate 与效果体发放名逐对相等
  (箱腿一致性锁族形;两处独立字面量漂移在备战断言不可见唯此锁可暴露)
  + 披露键辖卡元组断言;
- 锁 1b 装备名/类别断言锁:目标/名单成员 ∈ EQUIPMENTS ∧ 类别断言 ∧
  与合成配方派生一致(``_validate_strategy_grants`` 无装备名校验,本锁
  为唯一防漂移面);
- 锁 2 转换主锁:持卡 + ``gain_equipment('幸运星', rand=False)`` →
  幸运星零入栏 + 以牙还牙甲入栏;detail = ``converted:独家代言``;
  evidence 带 ``equip_gain_converted:`` 前缀段;on_equipment_gained 以
  替换名分派(以牙还牙甲 ∉ 后果表,effects 空);
- 锁 3 名单/类别边界:非名单简易件照常入栏;进阶/工具/星徽照常入栏;
  名单成员量产型装甲虽 ∉ 开箱候选前缀,直调原语仍转换——拦截按名单
  不按通道;
- 锁 4 不持卡零转换;
- 锁 6 跨卡优先级:双持自由市场 + 本卡,获幸运星(∈ 名单集 ∧ 类别
  简易双命中)→ 名单集行胜类别词行;两种持卡序均断言名单定向胜,
  防持卡序现状语义回潜;单事件单转换;
- 锁 7 不重入:双持好运来 + 本卡,获幸运星 → 以牙还牙甲入栏零令牌
  (名单行胜 + 直落不重查守卫)。效果条目1 pick 事件在双持好运来局被链式
  改判令牌 = 在码链式现值(判读申报,禁当定论转引),本文件不锁该读法。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.data.cw_synthesis import cross_components
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_equipment,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ENDORSE_ADVANCE_CHOICE_CARDS,
    STRATEGY_ENDORSE_ADVANCE_CHOICE_PLACEHOLDER,
    STRATEGY_GRANTS,
    equips_by_category,
)
from sr_od.application.currency_war.sim.cw_sim_backend import box_options

_SIG_OBS = ChannelSig(family='obs', actor='CwGainChainTest')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '独家代言'

_TARGET = '以牙还牙甲'

_MEMBERS = ('量产型装甲', '幸运星')


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None,
             cards: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;镜像同目录
    test_gain_equipment_conversion_equip_target._make_gs)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
                 for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    if cards:
        gs.write_logic(gs.active_strategies, cards, produced_by='test-seed',
                       evidence='t:card', sig=_LSIG)
    return gs


def _hold_card(gs: GameState, cards: list[str]) -> None:
    """持卡直置(注册容器直写;同族多卡持卡态由 cards 列表承载)。"""
    gs.write_logic(gs.active_strategies, cards, produced_by='test-seed',
                   evidence='t:card', sig=_LSIG)


def _box_slots(gs: GameState) -> list:
    return [s for s in gs.bench.value.slots
            if s is not None and s.kind == 'supply_box']


class _RowSink:
    """缺陷台账行收集(镜像 test_gain_chain 同名 fixture,装配 + 必达收尾)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


def test_grant_effect_mirror_and_disclosure_lock(
        rows_sink: _RowSink) -> None:
    """镜像一致性 + 披露键辖卡锁(设计 §4 锁 1):登记表
    ``equips_immediate`` 与效果体发放名逐对相等(直呼同名单效果体,
    经获得链入栏断言,箱腿一致性锁族形;两处独立字面量漂移在备战断言
    不可见唯此锁可暴露)+ 卡名 ∈ 披露键辖卡元组 ∧ 键值形制(T-205/
    T-218 键形先例)∧ base 注册表已登记。"""
    assert INVESTMENT_STRATEGIES['独家代言'].source == 'plaza:331401', \
        'base 注册表已登记(溯源 id 对拍)'
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.equips_immediate == (_TARGET,), \
        '登记行 = 占位选定进阶单件'
    assert _CARD in STRATEGY_ENDORSE_ADVANCE_CHOICE_CARDS, \
        '卡名 ∈ 披露键辖卡元组(键与登记行脱钩漂移防)'
    assert STRATEGY_ENDORSE_ADVANCE_CHOICE_PLACEHOLDER == \
        'strategy_endorse_advance_choice_placeholder', '披露键值形制'
    # 效果体发放名逐对相等(直呼同名单效果体经链入栏,登记行独立字面量)。
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    leg = PICK_INVEST_EFFECTS[_CARD]
    effects = leg(gs, sig=_LSIG, rng=random.Random(0))
    assert effects == [f'named_equip_grant:{_TARGET}(placed=True)'], \
        '效果体发放名与登记表逐对相等(具名确定发放 rand=False)'
    assert gs.equips.value == [_TARGET], '入栏同名单'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_grant_items_registry_and_recipe_consistency() -> None:
    """锁 1b 装备名/类别断言锁:目标与名单成员 ∈ EQUIPMENTS ∧ 类别断言
    (目标 = 进阶/成员 = 简易)∧ 名单 = 目标的合成配方组件(cross_
    components 派生一致——登记名单与配方库漂移的独立字面量防);
    ``_validate_strategy_grants`` 无装备名校验,本锁为唯一防漂移面。"""
    assert _TARGET in EQUIPMENTS, '目标已登记(词表漂移由 import 哨⑤a 辖)'
    assert EQUIPMENTS[_TARGET].category == '进阶', '目标 = 进阶类'
    assert cross_components(_TARGET) == _MEMBERS, \
        '名单 = 目标配方组件(与合成库派生一致;交叉件两读同值)'
    for n in _MEMBERS:
        assert n in EQUIPMENTS, f'成员 {n!r} 已登记'
        assert EQUIPMENTS[n].category == '简易', \
            f'成员 {n!r} = 简易组件(卡面「简易装备」语义前提)'


def test_conversion_intercept_places_target(rows_sink: _RowSink) -> None:
    """转换主锁(设计 §4 锁 2):持卡 + ``gain_equipment('幸运星',
    rand=False)`` → 出参 placed=True/detail=f'converted:{卡}'/
    landing='skipped';幸运星不入栏 + 以牙还牙甲入栏恰 +1;evidence 带
    ``equip_gain_converted:`` 前缀段(evidence 落 equips 容器行);
    on_equipment_gained 以替换名分派(以牙还牙甲 ∉ 后果表,effects 空);
    零箱、零申报行。任一经原语的名单成员获得通道同判定,单咽喉自动覆盖。"""
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, [_CARD])
    out = gain_equipment(gs, '幸运星', rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed, '转换产物入栏 = 转换发生(placed=True)'
    assert out.detail == f'converted:{_CARD}', 'detail 含 converted 标记'
    assert out.landing == 'skipped' and out.merge_levels == 0, \
        '出参形状 = 转换 GainOutcome(装备原语语义档)'
    assert gs.equips.value == [_TARGET], \
        f'幸运星被替换,以牙还牙甲入栏恰 +1: {gs.equips.value!r}'
    assert '幸运星' not in gs.equips.value, '被转换组件不入栏'
    assert gs.equips.evidence.startswith('equip_gain_converted:'), \
        'evidence 前缀段留证'
    assert out.effects == (), '获得后果回调零级联(产物 ∉ 后果表)'
    assert _box_slots(gs) == [], '零箱(装备分支非 bench 分支)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


@pytest.mark.parametrize('item', ['以太钻头', '信心注入器', '好运令牌',
                                  '红钻'])
def test_non_member_items_pass_through(item: str,
                                       rows_sink: _RowSink) -> None:
    """名单/类别边界(设计 §4 锁 3):非名单成员获得照常入栏零转换——
    以太钻头 = 简易但 ∉ 名单集(转换按名单不按类别词);信心注入器 =
    进阶(目标类≠源名单,名单行不辖进阶获得);好运令牌/红钻 = 工具/
    特殊类(非名单非简易)。取样排除后果表成员。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        EQUIP_ACQUIRE_CONSEQUENCES,
    )
    assert item in EQUIPMENTS, f'前提: {item!r} 已登记(漂移须随批改)'
    assert item not in _MEMBERS, f'前提: {item!r} ∉ 名单集(漂移须随批改)'
    assert item not in EQUIP_ACQUIRE_CONSEQUENCES, '取样前提(零后果隔离)'
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, [_CARD])
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed and out.detail == '', '照常入栏(零转换标记)'
    assert gs.equips.value == [item], '入栏恰 +1'
    assert _box_slots(gs) == [], '零箱(不转换)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_member_via_direct_primitive_converts(rows_sink: _RowSink) -> None:
    """名单成员通道无关锁(设计 §4 锁 3 注记支):量产型装甲系名单成员但
    ∉ 开箱候选前缀(box_options = 基础件排序前 4 无它),直调原语仍转换
    ——拦截按名单不按通道(获路全集不可枚举不枚举,单咽喉语义)。"""
    assert '量产型装甲' not in box_options(), \
        '前提:量产型装甲 ∉ 开箱候选前缀(漂移须随批改)'
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, [_CARD])
    out = gain_equipment(gs, '量产型装甲', rand=False, sig=_LSIG,
                         evidence='t', producer='Test')
    assert out.detail == f'converted:{_CARD}', '名单成员直调原语仍转换'
    assert gs.equips.value == [_TARGET], '组件被替换为目标入栏'


def test_no_card_zero_interception(rows_sink: _RowSink) -> None:
    """不持卡零转换(设计 §4 锁 4):同调用无卡时名单成员照常入栏(守卫
    零副作用;表外他卡持卡也不触发——持卡判定 ∩ 转换登记表)。"""
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, ['规模效应'])
    out = gain_equipment(gs, '幸运星', rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed and out.detail == '', '照常入栏'
    assert gs.equips.value == ['幸运星'], '入栏恰 +1'
    assert _box_slots(gs) == [], '零箱'


@pytest.mark.parametrize('cards', [
    ['自由市场', _CARD],
    [_CARD, '自由市场'],
])
def test_named_list_beats_category_word(cards: list[str],
                                        rows_sink: _RowSink) -> None:
    """跨卡优先级(设计 §4 锁 6):双持自由市场 + 本卡,获幸运星 =
    ∈ 名单集 ∧ 类别'简易'双命中 → 名单集行胜类别词行(名单定向 >
    类别词,specific-over-broad);**两种持卡序均断言名单定向胜**,防
    持卡序现状语义回潜;单事件单转换(幸运星不入栏 + 武装箱不落位 +
    equips 恰 +1)。"""
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, cards)
    out = gain_equipment(gs, '幸运星', rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.detail == f'converted:{_CARD}', \
        f'持卡序 {cards} 名单集行仍胜(名单定向 > 类别词)'
    assert gs.equips.value == [_TARGET], '单事件单转换(组件不入栏)'
    assert _box_slots(gs) == [], '零武装箱(类别词行零动作)'
    assert bench_units_of(gs) == [], '零单位域写'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_category_word_still_works_without_overlap(
        rows_sink: _RowSink) -> None:
    """双持互补面回归(锁 6 姊妹面):双持自由市场 + 本卡,获非名单简易件
    (以太钻头)→ 自由市场类别词行照常胜(名单行零命中,败者行语义
    不受分派序影响)。"""
    simple_non_member = [n for n in sorted(equips_by_category('简易'))
                         if n not in _MEMBERS][0]
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, ['自由市场', _CARD])
    out = gain_equipment(gs, simple_non_member, rand=False, sig=_LSIG,
                         evidence='t', producer='Test')
    assert out.detail == 'converted:自由市场', \
        '非名单简易件类别词行照常胜'
    assert _box_slots(gs) != [], '转换箱落位'


def test_no_reentry_with_haoyunlai(rows_sink: _RowSink) -> None:
    """不重入(设计 §4 锁 7):双持好运来 + 本卡,获幸运星 → 名单集行胜
    (好运来进阶谓词不命中简易件)+ 转换产物以牙还牙甲直落写入段不再
    重查守卫(单事件单转换)→ 入栏零令牌零再转换;效果条目1 pick 事件在双持
    好运来局被链式改判令牌 = 在码链式现值(判读申报,禁当定论转引)。"""
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, ['好运来', _CARD])
    out = gain_equipment(gs, '幸运星', rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.detail == f'converted:{_CARD}', '名单成员本卡名单行胜'
    assert gs.equips.value == [_TARGET], \
        f'产物直落入栏零再转换: {gs.equips.value!r}'
    assert '好运令牌' not in gs.equips.value, '零令牌(零重入)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_non_member_advanced_still_token_under_haoyunlai(
        rows_sink: _RowSink) -> None:
    """双持好运来 + 本卡非名单进阶件(锁 7 姊妹面):获光能盾牌(进阶,
    ∉ 名单集)→ 本卡名单行零命中,好运来类别词行胜 → 令牌(两行各辖
    其面,分派序零串扰)。"""
    advanced_non_target = [n for n in sorted(equips_by_category('进阶'))
                           if n != _TARGET][0]
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, ['好运来', _CARD])
    out = gain_equipment(gs, advanced_non_target, rand=False, sig=_LSIG,
                         evidence='t', producer='Test')
    assert out.detail == 'converted:好运来', '非名单进阶件好运来行胜'
    assert gs.equips.value == ['好运令牌'], '令牌入栏'
