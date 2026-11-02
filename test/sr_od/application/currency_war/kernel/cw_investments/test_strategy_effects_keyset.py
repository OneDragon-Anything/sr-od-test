"""STRATEGY_EFFECTS 键集闭集断言(cw_investments 分目录镜像;新写锁,
落位守 T-426 超限冻结判例——test_cw_investments.py 禁追加,拆目录新文件
先例 = 同目录各登记锁文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-191-chaofa-
huobi.md §3 锁 8(REVIEW-T191 §四④ 基线修正:活体 46 + 本卡 = **47**,
禁按设计稿 14/15 动刀)。实码原无任何 STRATEGY_EFFECTS 键集断言(设计稿
轮 1 F1 全测试仓反查实证)——本闭集锁「注册即红防静默漏登记」:新增/删改
条目键必须显式过本断言,静默漏登记(卡在册无条目 = 获得链登记分支永不
命中)即红。

键序 = 注册表字典序(登记序);全等形态连「意外多出的申报键」同红。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)

#: 键集闭集基线 = 活体 46 名(2026-11 实现批 T-182~T-190 后现值)+
#: 超发货币(T-191)= 47 + 全都要·金双腿两键(2026-11-02)= 49 + 幸运星祝福(2026-11-03)= 50;
#: 扩员 = 新卡实现批随批显式并入。
_EXPECTED_KEYS: frozenset[str] = frozenset({
    '淘金客', '固定理财', '固定理财+', '经验就是财富', '商业间谍',
    '双手狸开键盘！', '采购专员·金', '采购专员·彩', '全员晋升', '人力重组',
    '大裁员', '降本增效', '躺平', '免战牌', '本金充裕', '本金充裕+',
    '加油站', '免费午餐', '存款回报', '打捞人才库', '打捞人才库+',
    '全队的希望', '成长基金', '武力刷新', '星星相印', '节省工位',
    '公司人才流动', '公司军火更新·银', '市场干预', '合并同类项', '溜佩佩',
    '溜佩佩+', '全都要·银', '全都要·银#supply_delta', '全都要·金',
    '全都要·金#supply_delta', '团队力量·银',
    '应援团', '正能量', '完美开局', '效率员工奖', '基层贡献',
    '榜样的力量·银', '当头一棒', '幸运喷雾', '延迟收益', '星级压制', '星变',
    '超发货币',
    '幸运星祝福',
    '折叠小刀祝福',
})


def test_strategy_effects_keyset_closed() -> None:
    """键集闭集断言(锁 8):全量键集与基线全等(缺员 = 漏登记静默失联;
    多员 = 未申报键混入,两向同红)。"""
    assert set(STRATEGY_EFFECTS) == set(_EXPECTED_KEYS), (
        'STRATEGY_EFFECTS 键集漂移:\n'
        f'  缺员: {sorted(set(_EXPECTED_KEYS) - set(STRATEGY_EFFECTS))}\n'
        f'  多员: {sorted(set(STRATEGY_EFFECTS) - set(_EXPECTED_KEYS))}')
    assert len(STRATEGY_EFFECTS) == 51, '基数申报对账(effect-domain §5)'


def test_strategy_effects_keys_unique_ids() -> None:
    """伴生锁:规范键条目 id 唯一(同卡双腿申报键除外——全都要·银/金#
    supply_delta 与 canon 键同 id 系在册申报形态,非漂移)。"""
    ids: dict[str, str] = {}
    for key, spec in STRATEGY_EFFECTS.items():
        if '#' in key:
            continue   # 申报键(同卡第二腿声明面)豁免,对表 = 键集锁
        assert spec.id not in ids, \
            f'id 重复:{spec.id}({ids.get(spec.id)} vs {key})'
        ids[spec.id] = key
