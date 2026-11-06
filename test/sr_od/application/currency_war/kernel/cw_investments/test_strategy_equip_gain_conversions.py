"""策略卡装备获得转换登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_EQUIP_GAIN_CONVERSIONS + 构建校验;按拆目录规范落位,先例 =
同目录 test_strategy_conditional_grants.py)。

测试面依据 = 迭代设计 designs/T-143-ziyou-shichang.md §4 锁 9 校验注册
义务 + REVIEW-T143 §3 漂移表 #10 校验面收敛(2026-10-28 治理口径):
三漂移哨留(孤儿键/源漂移按源形分派/目标名 ∈ 词表 ∪ 装备注册表,均能被
游戏版本变更独立触发);源类别 ≠ 目标类别防自指属写表人纯笔误类,不加
import 期校验 → 降为表域数据性质测试(本文件 test_target_domain_
disjoint_no_self_reference,BENCH_ITEM_KINDS 键集一致性同口径归测试与
评审)。族第二成员好运来(装备目标分支首例)登记面依据 =
designs/T-248-haoyunlai.md §2.1(行值 = 卡面获得效果条目直读)。族第三成员
独家代言(名单集源形首例)登记面依据 = designs/T-372-dujia-daiyan.md
§2.2 + REVIEW-T372 §3.3(行值 = 卡面获得效果条目直读;源形 = 配方组件名单
元组,成员判;名单集哨两支 = ⑤a 词表/⑤b 类别,⑤c 防自指禁加)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_NAMES,
    EQUIPMENTS,
    INVESTMENT_STRATEGIES,
    STRATEGY_EQUIP_GAIN_CONVERSIONS,
    _validate_strategy_equip_gain_conversions,
    equips_by_category,
)


def test_conversion_rows_single_source() -> None:
    """登记单一源(逐行 = 卡面效果原文直读 + base 溯源 id 对拍):
    - 自由市场行:「将要获得一件简易装备」→ 源类别简易,「改为获得1个
      【简易武装箱】」→ 目标占席道具(id 130601 ↔ plaza:130601);
    - 好运来行(装备目标分支首例):「合成与获得进阶装备时，改为获得
      一个【好运令牌】」的获得效果条目 → 源类别进阶、目标装备注册表已登记
      工具类物(id 231601 ↔ plaza:231601);卡面合成效果条目不走获得链零建模;
    - 独家代言行(名单集源形首例):「你获得组成该装备的简易装备时，
      改为获得该进阶装备」→ 源 = 配方组件名单元组(成员判)、目标 =
      效果条目1 占位选定件以牙还牙甲(id 331401 ↔ plaza:331401);
    - 表键集闭族 = 族现役卡(新卡随各自实现批领取,禁顺手代登记)。"""
    assert set(STRATEGY_EQUIP_GAIN_CONVERSIONS) == {
        '自由市场', '好运来', '独家代言'}, \
        '注册面 = 族现役三卡(新卡随各自实现批领取,禁顺手代登记)'
    source_cat, target = STRATEGY_EQUIP_GAIN_CONVERSIONS['自由市场']
    assert (source_cat, target) == ('简易', '简易武装箱'), '行值 = 卡面直读'
    assert equips_by_category(source_cat), '源类别池非空(数据性质)'
    assert target in BENCH_ITEM_NAMES, '目标 = 占席道具(bench 分支)'
    assert INVESTMENT_STRATEGIES['自由市场'].source == 'plaza:130601', \
        f'溯源 id 对拍失同步: {INVESTMENT_STRATEGIES["自由市场"].source}'
    source_cat, target = STRATEGY_EQUIP_GAIN_CONVERSIONS['好运来']
    assert (source_cat, target) == ('进阶', '好运令牌'), '行值 = 卡面直读'
    assert equips_by_category(source_cat), '源类别池非空(数据性质)'
    assert target in EQUIPMENTS, '目标 = 装备注册表已登记物(装备分支)'
    assert EQUIPMENTS[target].category == '工具', \
        '转换产物 = 工具类装备(非占席道具、非占源类别)'
    assert INVESTMENT_STRATEGIES['好运来'].source == 'plaza:231601', \
        f'溯源 id 对拍失同步: {INVESTMENT_STRATEGIES["好运来"].source}'
    source_names, target = STRATEGY_EQUIP_GAIN_CONVERSIONS['独家代言']
    assert isinstance(source_names, tuple), '源形 = 名单集元组(首例)'
    assert tuple(source_names) == ('量产型装甲', '幸运星'), \
        '名单 = 占位选定进阶的配方组件(卡面直读;派生式现值同值)'
    assert all(EQUIPMENTS[n].category == '简易' for n in source_names), \
        '名单成员全 = 简易组件(卡面「简易装备」语义前提)'
    assert target == '以牙还牙甲', '目标 = 效果条目1 占位选定件'
    assert EQUIPMENTS[target].category == '进阶', '目标 = 进阶类(装备分支)'
    assert INVESTMENT_STRATEGIES['独家代言'].source == 'plaza:331401', \
        f'溯源 id 对拍失同步: {INVESTMENT_STRATEGIES["独家代言"].source}'


def test_target_domain_disjoint_no_self_reference() -> None:
    """数据性质(防自指,治理口径归测试与评审非 import 校验):目标名不
    属源集——若目标 ∈ 源类别池/名单集,转换产物再入装备域会形成转换环;
    现值目标域两分支并存(占席道具 + 装备注册表已登记物),逐行按源形分派
    验证(装备分支行 = 好运来:产物工具类 ∉ 进阶池;独家代言:产物
    以牙还牙甲 ∉ 配方组件名单,即使误重入零再转换,不重入主防线 =
    守卫直落不重查)。"""
    assert BENCH_ITEM_NAMES & set(EQUIPMENTS) == set(), \
        '占席道具词表与装备注册表互斥(目标域判别无歧义前提)'
    for name, (source, target) in STRATEGY_EQUIP_GAIN_CONVERSIONS.items():
        if isinstance(source, tuple):
            assert target not in source, \
                f'{name}: 目标 ∉ 名单集(转换无环数据性质)'
        else:
            assert target not in equips_by_category(source), \
                f'{name}: 目标 ∉ 源类别池(转换无环数据性质)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在 base 注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_EQUIP_GAIN_CONVERSIONS, '不存在的卡',
        ('简易', '简易武装箱'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_equip_gain_conversions()


def test_validator_source_category_drift_raises(monkeypatch) -> None:
    """构建校验②(源类别漂移哨):源类别池空 → ValueError——类别名
    漂移的运行期实况 = 拦截谓词永不命中、转换静默失效(无异常无台账),
    import 期哨是唯一响亮拦截面(STRATEGY_HP_LOSS_GRANTS 类别漂移哨
    同形)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_EQUIP_GAIN_CONVERSIONS, '自由市场',
        ('不存在的类别', '简易武装箱'))
    with pytest.raises(ValueError, match='源类别漂移'):
        _validate_strategy_equip_gain_conversions()


def test_validator_target_name_drift_raises(monkeypatch) -> None:
    """构建校验③(目标名漂移哨):目标 ∉ BENCH_ITEM_NAMES ∪ EQUIPMENTS
    → ValueError——错名运行期实况 = 占席道具域落席直查 KeyError 炸原语
    或装备域盲追加幻影,import 期哨是唯一响亮拦截面
    (_validate_strategy_conditional_grants 装备名漂移哨同理由)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_EQUIP_GAIN_CONVERSIONS, '自由市场',
        ('简易', '不存在的目标'))
    with pytest.raises(ValueError, match='目标名漂移'):
        _validate_strategy_equip_gain_conversions()


def test_validator_list_member_drift_raises(monkeypatch) -> None:
    """构建校验⑤a(名单集哨·词表漂移支):名单集源形成员 ∉ EQUIPMENTS
    → ValueError——词表漂移成员运行期永不命中(守卫 EQUIPMENTS 早退),
    转换静默失效无台账,import 期哨唯一响亮面(源形分派扩形支,与哨②
    同理由)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_EQUIP_GAIN_CONVERSIONS, '独家代言',
        (('量产型装甲', '不存在的组件'), '以牙还牙甲'))
    with pytest.raises(ValueError, match='名单成员漂移'):
        _validate_strategy_equip_gain_conversions()


def test_validator_list_category_drift_raises(monkeypatch) -> None:
    """构建校验⑤b(名单集哨·类别漂移支):名单成员类别 ≠ '简易' →
    ValueError——名单集源形的语义前提 = 卡文「获得组成该装备的简易
    装备」,游戏类别改版后成员不再是 desc 辖域的简易装备,名单行成过
    名单须随批修表(import 期哨唯一响亮面)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_EQUIP_GAIN_CONVERSIONS, '独家代言',
        (('量产型装甲', '以牙还牙甲'), '以牙还牙甲'))
    with pytest.raises(ValueError, match='名单类别漂移'):
        _validate_strategy_equip_gain_conversions()
