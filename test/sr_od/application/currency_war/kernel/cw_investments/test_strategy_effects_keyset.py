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

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    BENCH_REROLL_LEFT6,
    DurationKind,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)

#: 键集闭集基线 = 活体 46 名(2026-11 实现批 T-182~T-190 后现值)+
#: 超发货币(T-191)= 47 + 全都要·金双腿两键(2026-11-02)= 49 + 幸运星祝福(2026-11-03)= 50;
#: 扩员 = 新卡实现批随批显式并入。
#: 后续:折叠小刀/和平手枪/生命之花/量产型装甲祝福 + 公司军火更新·金/人海战术/打通上下游·金;
#: 现金为王(2026-11-02)= 59 键;赞美太阳(装备计数 XP 族首例,2026-11-03)= 74 键;
#: 星魂升华(策略源 UNIT_BUFF 族,前台星魂 +1 阶零响应登记)= 75 键现值;
#: 开源节流(条件息顶满载体宿主条目,2026-11-03)= 78 键现值;
#: 公司严选(「现在及每个位面开始时」族第 3 员,位面周期金 + 商店改写对,
#: 2026-11-03)= 82 键现值;
#: 搜打撤(每节点 +1 免费刷 overlay 补条,T-332 批)= 83 键现值;
#: 全都要·彩双腿两键(族收官,None 无界 recurring,T-375 批,2026-11-05)= 87 键现值。
#: 分解万物(三面分治:腿1 PICK 具名工厂 + 腿2 装备变换登记型,案甲 pending 冻结,2026-11-05)= 88 键现值。
#: 幸运闪避EX(受击概率伤害变换零响应登记,幸运一击域)= 103 键现值。
#: 羁绊的力量(羁绊计数条件双轴战力 buff 零响应登记)= 104 键现值。
#: 乱成一锅粥(bench_reroll 重掷零逻辑写 + burst=5 载体字段单条目双载登记,
#: bench_reroll 族第 2 员)= 105 键现值。
#: 乱成一锅粥+(姊妹展开卡,同形双载 burst=7,bench_reroll 族第 3 员)= 106 键现值。
_EXPECTED_KEYS: frozenset[str] = frozenset({
    '淘金客', '固定理财', '固定理财+', '经验就是财富', '商业间谍',
    '双手狸开键盘！', '采购专员·金', '采购专员·彩', '全员晋升', '人力重组',
    '大裁员', '降本增效', '躺平', '免战牌', '本金充裕', '本金充裕+',
    '加油站', '免费午餐', '存款回报', '打捞人才库', '打捞人才库+',
    '全队的希望', '成长基金', '武力刷新', '星星相印', '节省工位',
    '公司人才流动', '公司军火更新·银', '公司军火更新·金', '公司军火更新·彩', '入职礼包', '市场干预', '合并同类项', '溜佩佩',
    '溜佩佩+', '全都要·银', '全都要·银#supply_delta', '全都要·金',
    '全都要·金#supply_delta', '全都要·彩', '全都要·彩#supply_delta',
    '团队力量·银',
    '应援团', '正能量', '完美开局', '效率员工奖', '基层贡献',
    '榜样的力量·银', '当头一棒', '幸运喷雾', '延迟收益', '星级压制', '星变',
    '超发货币',
    '幸运星祝福',
    '折叠小刀祝福',
    '和平手枪祝福',
    '生命之花祝福',
    '量产型装甲祝福',
    '人海战术',
    '打通上下游·金',
    '独狼',
    '中产阶级',
    '前段发力',
    '三三三',
    '创伤小组',
    '绕口令',
    '风暴骑士',
    '幸运中的幸运',
    '榜样的力量·金',
    'OOTD·金',
    '打人就打脸·金',
    '团队力量·金',
    '钻石恒永久',
    '读博深造',
    '装备党',
    '赞美太阳',
    '现金为王',
    '星魂升华',
    '爆仓',
    '领航专家:姬子',
    '概率事件',
    '及时雨',
    '利息上调',
    '开源节流',
    '公司严选',
    '搜打撤',
    '分解万物', '完美进化', '幸运之子', '超光速提拔', '榜样的力量·彩', '万箭齐发', '后勤超响应', '三五成群', '基本保障', '更快,更幸运', '打通上下游·彩', '野蛮成长', '保守派', '攻防一体', '战术义眼+', '幸运闪避EX', '羁绊的力量', '乱成一锅粥', '乱成一锅粥+',
})


def test_strategy_effects_keyset_closed() -> None:
    """键集闭集断言(锁 8):全量键集与基线全等(缺员 = 漏登记静默失联;
    多员 = 未申报键混入,两向同红)。"""
    assert set(STRATEGY_EFFECTS) == set(_EXPECTED_KEYS), (
        'STRATEGY_EFFECTS 键集漂移:\n'
        f'  缺员: {sorted(set(_EXPECTED_KEYS) - set(STRATEGY_EFFECTS))}\n'
        f'  多员: {sorted(set(STRATEGY_EFFECTS) - set(_EXPECTED_KEYS))}')
    assert len(STRATEGY_EFFECTS) == 106, '基数申报对账(effect-domain §5)'


def test_strategy_effects_keys_unique_ids() -> None:
    """伴生锁:规范键条目 id 唯一(同卡双腿申报键除外——全都要·银/金/彩#
    supply_delta 与 canon 键同 id 系在册申报形态,非漂移)。"""
    ids: dict[str, str] = {}
    for key, spec in STRATEGY_EFFECTS.items():
        if '#' in key:
            continue   # 申报键(同卡第二腿声明面)豁免,对表 = 键集锁
        assert spec.id not in ids, \
            f'id 重复:{spec.id}({ids.get(spec.id)} vs {key})'
        ids[spec.id] = key


def test_strategy_effects_bench_reroll_dual_carrier() -> None:
    """乱成一锅粥 双载条目锁:五元组 + payload 双载(bench_reroll 词表值 /
    free_refresh_burst=5)+ duties.track 单置;burst 双源同值(注册行 ==
    载体值,治理后形双源对账归注册面测试锁,同形先例 =
    test_strategy_dacaiyuan_registry)。"""
    spec = STRATEGY_EFFECTS['乱成一锅粥']
    assert spec.id == '352101'
    assert spec.trigger is TriggerKind.NODE_ENTER, '触发 = 节点进入'
    assert spec.duration is DurationKind.WHILE_HELD, '持续期 = 持有绑定'
    assert spec.category is EffectKind.BATTLEFIELD, '类别 = 战场改变'
    assert spec.payload.bench_reroll == BENCH_REROLL_LEFT6, \
        '词表值单一源(禁裸串漂移)'
    assert spec.payload.free_refresh_burst == 5, \
        '官方卡文「立刻获得5次免费刷新」'
    assert spec.duties.track is True, 'track 单置(重掷面账本可见性)'
    assert spec.duties.predict is False and spec.duties.respond is False, \
        '无预知/姿态消费面'
    reg = STRATEGY_ECONOMY['乱成一锅粥'].free_refresh_burst
    assert reg == 5, '官方卡文 5(base 层 plaza:352101)'
    assert reg == spec.payload.free_refresh_burst, '双源同值(注册行 ↔ 载体条目)'


def test_strategy_effects_bench_reroll_plus_dual_carrier() -> None:
    """乱成一锅粥+ 双载条目锁:五元组 + payload 双载(bench_reroll 词表值 /
    free_refresh_burst=7)+ duties.track 单置;burst 双源同值(注册行 ==
    载体值,治理后形双源对账归注册面测试锁,同形先例 =
    test_strategy_dacaiyuan_registry)。与姊妹条目锁互不替代——值不同
    5 ≠ 7,两验各锁各卡。"""
    spec = STRATEGY_EFFECTS['乱成一锅粥+']
    assert spec.id == '352102'
    assert spec.trigger is TriggerKind.NODE_ENTER, '触发 = 节点进入'
    assert spec.duration is DurationKind.WHILE_HELD, '持续期 = 持有绑定'
    assert spec.category is EffectKind.BATTLEFIELD, '类别 = 战场改变'
    assert spec.payload.bench_reroll == BENCH_REROLL_LEFT6, \
        '词表值单一源(与姊妹条目同值互证,禁裸串漂移)'
    assert spec.payload.free_refresh_burst == 7, \
        '官方卡文「立刻获得7次免费刷新」'
    assert spec.duties.track is True, 'track 单置(重掷面账本可见性)'
    assert spec.duties.predict is False and spec.duties.respond is False, \
        '无预知/姿态消费面'
    reg = STRATEGY_ECONOMY['乱成一锅粥+'].free_refresh_burst
    assert reg == 7, '官方卡文 7(base 层 plaza:352102)'
    assert reg == spec.payload.free_refresh_burst, '双源同值(注册行 ↔ 载体条目)'
