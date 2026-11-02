"""策略卡延时发放注册表测试(镜像 src = kernel/cw_investments.py 的
StrategyDelayedGrant + STRATEGY_DELAYED_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 1(经治理收缩:
防登记笔误类校验「delay_nodes 形/下界」不落校验不落锁——2026-10-28
治理口径,T-98 锁 1 同款收缩先例;只留漂移哨)+ T-107 展开卡随批扩面
(designs/T-107-rencai-jili-plus.md §4 锁 1 同型)+ 许诺特权随批扩面
(designs/T-139-xunuo-tequan.md §4 锁 1 同型)+ 先亏后盈随批扩面
(designs/T-144-xiankui-houying.md §4 锁 1:count 字段首例 + 伴随损血
腿 STRATEGY_ECONOMY 行)+ 好运令牌·银随批扩面(designs/
T-146-haoyun-lingpai-yin.md §4 锁 1:卡名与发放物异名首例,物名断言
防卡名当物名笔误)+ 是钻石总会发光随批扩面(designs/
T-148-shizuanshi-zonghui-faguang.md §4 锁 1/锁 4:随机 choice-set 行
首例,item='' 占位走 item_choices;item 与 item_choices 恰一 = 防登记
笔误类按治理口径不入 import 校验,对账归表域恰一锁)+ 回收计划随批扩面
(designs/T-237-huishou-jihua.md §4 锁 2:item_category 类别池行首例,
item='' 占位走类别池,值域词表由池派生承载):
- 登记单一源:行值 = 卡面效果原文直读(人才激励 id 101601/4 节点、
  人才激励+ id 101602/3 节点,两卡唯一差异 = 倒计时 4→3,发放物同
  员工投影仪;许诺特权 id 130201/7 节点/发放物特权武装箱;先亏后盈
  id 130701/4 节点/发放物简易武装箱/数量 2 = 族内首例 >1;好运令牌·
  银 id 130901/3 节点/发放物好运令牌 = EQUIPMENTS 工具类装备;是钻石
  总会发光 id 131101/2 节点/发放物 = 红钻/蓝钻具名二元封闭集;回收
  计划 id 230701/5 节点/发放物 = 「随机简易装备」类别池
  item_category='简易',item='' 占位),
  表键集闭族现役卡(展开卡各自独立批领取,禁顺手代登记);
- 构建校验 5 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 /
  id 双匹配(改名且 id 仍在的漂移也炸)/ 发放物名双域皆非(确定行)
  / choice-set 元素漂移(逐元素双域皆非)/ 类别池漂移(池 = 注册表
  category 等值过滤,表外类别名与类别清空两触发路径同哨)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_NAMES,
    INVESTMENT_STRATEGIES,
    STRATEGY_DELAYED_GRANTS,
    STRATEGY_ECONOMY,
    StrategyDelayedGrant,
    _validate_strategy_delayed_grants,
)


@pytest.mark.parametrize(('card', 'gid', 'delay', 'item', 'count',
                          'choices', 'category'), [
    ('人才激励', '101601', 4, '员工投影仪', 1, (), ''),
    ('人才激励+', '101602', 3, '员工投影仪', 1, (), ''),
    ('许诺特权', '130201', 7, '特权武装箱', 1, (), ''),
    ('先亏后盈', '130701', 4, '简易武装箱', 2, (), ''),
    ('好运令牌·银', '130901', 3, '好运令牌', 1, (), ''),
    ('是钻石总会发光', '131101', 2, '', 1, ('红钻', '蓝钻'), ''),
    ('回收计划', '230701', 5, '', 1, (), '简易'),
])
def test_rencai_jili_registry_row_single_source(
        card: str, gid: str, delay: int, item: str, count: int,
        choices: tuple, category: str) -> None:
    """登记单一源(姊妹双卡 + 许诺特权 + 先亏后盈 + 好运令牌·银 +
    是钻石总会发光 + 回收计划参数化):行值 = 卡面
    效果原文直读(「N个节点后」→ N 拍,「获得1个【X】」→ 发放物 X;
    人才激励系即时腿「获得1个【员工投影仪】」由 PICK_INVEST_EFFECTS
    工厂承载不入本表,许诺特权卡文纯延时单句零即时腿,登记腿 = 延时-
    only 单腿载体;先亏后盈卡文延时腿「获得2个」→ count=2 族内首例
    >1,伴随损血腿不入本表走 STRATEGY_ECONOMY hp 通道;好运令牌·银
    卡文纯延时单句零即时腿同延时-only 载体,发放物与卡名异名——item
    断言为物名「好运令牌」非卡名,防拿卡名当物名笔误;是钻石总会发光
    卡文「获得【红钻】或【蓝钻】」→ item='' 占位(空串断言锁二元集行
    不携确定件)+ item_choices 封闭集直读,掷骰时点 = 到点发放窗;回收
    计划卡文「获得1件随机简易装备」→ 类别池形 item_category='简易'
    直读(族内类别池行首例),item='' 占位,同卡即时腿「获得1件进阶
    装备」由 PICK_INVEST_EFFECTS 组合登记行承载不入本表);
    base 溯源 id 对拍(id ↔ plaza:<id>)。表键集闭族现役七卡(未注册
    展开卡安静不写,禁顺手代登记)。"""
    assert set(STRATEGY_DELAYED_GRANTS) == {
        '人才激励', '人才激励+', '许诺特权', '先亏后盈', '好运令牌·银',
        '是钻石总会发光', '回收计划'}, \
        '注册面 = 族现役七卡(未注册展开卡安静不写,禁顺手代登记)'
    row = STRATEGY_DELAYED_GRANTS[card]
    assert row == StrategyDelayedGrant(id=gid, delay_nodes=delay,
                                       item=item, count=count,
                                       item_choices=choices,
                                       item_category=category), \
        f'行值漂移: {row!r}'
    base = INVESTMENT_STRATEGIES[card]
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_grant_item_not_in_bench_wordlist() -> None:
    """发放物分道词表归属对拍(分道判据前提,注册表逐行锁):装备名
    不入占席词表(本专表不接入 BENCH_ITEM_NAMES 派生,装备名误入词表
    即被当占席道具——溢出腿假道具,该形态钉死);许诺特权发放物特权
    武装箱 = 占席词表在册 ∧ 装备表无条目(占席分道判据前提);好运
    令牌·银发放物好运令牌 = 装备表在册 ∧ 占席词表负成员(装备分道
    判据前提,负成员申报 = 入 items 会错派占席身份,禁入占席通道);
    是钻石总会发光 choice-set 两元素红钻/蓝钻 = 装备表在册 ∧ 占席词表
    负成员(采样行同走装备分道,钻石禁入占席通道)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    row = STRATEGY_DELAYED_GRANTS['人才激励']
    assert row.item in EQUIPMENTS, '发放物 = 装备表在册(装备腿分道)'
    assert row.item not in BENCH_ITEM_NAMES, \
        '装备名误入占席词表(禁入形态被破坏)'
    xunuo = STRATEGY_DELAYED_GRANTS['许诺特权']
    assert xunuo.item in BENCH_ITEM_NAMES, \
        '特权武装箱不在占席词表(占席分道判据前提被破坏)'
    assert xunuo.item not in EQUIPMENTS, \
        '占席道具误入装备表(分道双归属)'
    haoyun = STRATEGY_DELAYED_GRANTS['好运令牌·银']
    assert haoyun.item in EQUIPMENTS, \
        '好运令牌不在装备表(装备分道判据前提被破坏)'
    assert haoyun.item not in BENCH_ITEM_NAMES, \
        '好运令牌误入占席词表(负成员申报被破坏,入 items 错派占席身份)'
    shizuanshi = STRATEGY_DELAYED_GRANTS['是钻石总会发光']
    assert all(c in EQUIPMENTS for c in shizuanshi.item_choices), \
        '红钻/蓝钻不在装备表(采样行装备分道判据前提被破坏)'
    assert all(c not in BENCH_ITEM_NAMES for c in shizuanshi.item_choices), \
        '红钻/蓝钻误入占席词表(负成员申报被破坏,禁入占席通道)'


def test_xiankui_hp_instant_negative_row() -> None:
    """先亏后盈伴随损血腿注册行(STRATEGY_ECONOMY):hp_instant = −20
    (卡面「损失20点小队生命值」数值 20 直读取负,非设计数);同字段
    正负成员并存(健康充值 +30 / 本卡 −20)。两表行断言随本表域锁面
    (损血腿与延时腿同卡分道,行值漂移在此显形);负值支写端行为面 =
    sim 侧 test_strategy_pick_hp.py 锁面。"""
    from sr_od.application.currency_war.data.cw_invest_data import (
        PLAZA_AUGMENTS,
    )
    assert '先亏后盈' in STRATEGY_ECONOMY, '损血腿注册行缺位'
    assert STRATEGY_ECONOMY['先亏后盈'].hp_instant == -20, \
        f'损血腿值漂移: {STRATEGY_ECONOMY["先亏后盈"].hp_instant}'
    # 卡面数值对拍:注册值取负 = 卡面「损失20点」的 20 直读,防两源漂移。
    base = next(a for a in PLAZA_AUGMENTS if a.id == '130701')
    assert '损失20点小队生命值' in base.effect, f'卡面漂移: {base.effect!r}'
    assert STRATEGY_ECONOMY['先亏后盈'].hp_instant == -int(
        base.effect.split('损失')[1].split('点')[0]), '注册值与卡面失同步'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在 base 注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_GRANTS, '不存在的卡',
        StrategyDelayedGrant(id='999999', delay_nodes=4,
                             item='员工投影仪'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_delayed_grants()


def test_validator_id_mismatch_raises(monkeypatch) -> None:
    """构建校验②(id 双匹配哨):登记 id ≠ base 溯源 id → ValueError
    (版本改名且 id 仍在的漂移也炸)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_GRANTS, '人才激励',
        StrategyDelayedGrant(id='101999', delay_nodes=4,
                             item='员工投影仪'))
    with pytest.raises(ValueError, match='id 漂移'):
        _validate_strategy_delayed_grants()


def test_validator_item_unknown_raises(monkeypatch) -> None:
    """构建校验③(发放物名漂移哨):发放物双域皆非(装备表/占席词表
    均无)→ ValueError(版本改名/未知名,发放腿无从分道)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_GRANTS, '人才激励',
        StrategyDelayedGrant(id='101601', delay_nodes=4,
                             item='不存在的发放物'))
    with pytest.raises(ValueError, match='发放物名漂移'):
        _validate_strategy_delayed_grants()


def test_validator_choice_element_unknown_raises(monkeypatch) -> None:
    """构建校验④(choice-set 元素漂移哨):非空 item_choices 逐元素
    双域皆非(装备表/占席词表均无)→ ValueError(版本改名/未知名,
    采样行发放腿无从分道;镜像③形态)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_GRANTS, '是钻石总会发光',
        StrategyDelayedGrant(id='131101', delay_nodes=2, item='',
                             item_choices=('红钻', '不存在的发放物')))
    with pytest.raises(ValueError, match='发放物元素漂移'):
        _validate_strategy_delayed_grants()


def test_registry_triplet_exactly_one() -> None:
    """表域三方恰一纪律锁(item / item_choices / item_category 三选一
    登记;治理口径 = 2026-10-28「防登记笔误校验不加」,对账归表域测试,
    同 count/delay_nodes 处置):注册全集逐行三形恰一非空,双填/多填/
    全空均红——双填 = 分道判据静默走 item 丢随机集,全空 = 发放腿双域
    皆非防御支条目永久滞留,两形态都越 import 哨不可见(回收计划批由
    二方恰一扩为三方恰一)。"""
    for name, row in STRATEGY_DELAYED_GRANTS.items():
        assert sum((bool(row.item), bool(row.item_choices),
                    bool(row.item_category))) == 1, \
            f'{name} 三形恰一被破坏: {row!r}'


def test_huishou_category_pool_membership() -> None:
    """回收计划类别池成员锁(「随机简易装备」目标全集 = 注册表简易 8
    件派生,派生集禁手抄清单):item_category='简易' 池 = equips_by_
    category('简易') 非空 8 件,逐件 ∈ EQUIPMENTS ∧ ∉ BENCH_ITEM_NAMES
    (装备分道判据前提,采样件禁入占席通道);注册表扩员(新简易件)时
    池派生自动跟随,本锁只锚「类别池行发放走注册表派生全集」语义。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    row = STRATEGY_DELAYED_GRANTS['回收计划']
    pool = equips_by_category(row.item_category)
    assert len(pool) == 8, f'简易池规模漂移: {len(pool)}'
    assert all(p in EQUIPMENTS for p in pool), '池成员 ∉ 装备表(分道破)'
    assert all(p not in BENCH_ITEM_NAMES for p in pool), \
        '池成员误入占席词表(负成员申报被破坏)'


def test_validator_item_category_unknown_raises(monkeypatch) -> None:
    """构建校验⑤(类别漂移哨·表外类别名):非空 item_category 注册表
    category 无此值(池空)→ ValueError(版本类别词表改名可独立触发,
    镜像③④形态;值域词表由池派生承载,零第二字面量)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_GRANTS, '回收计划',
        StrategyDelayedGrant(id='230701', delay_nodes=5, item='',
                             item_category='不存在的类别'))
    with pytest.raises(ValueError, match='类别漂移'):
        _validate_strategy_delayed_grants()


def test_validator_item_category_pool_empty_raises(
        monkeypatch) -> None:
    """构建校验⑤(类别漂移哨·类别清空路径):类别名合法但注册表该类
    清零(游戏版本数据漂移可独立触发)→ 同哨 ValueError——哨按池派生
    表达,两触发路径(改名/清空)同响,import 期把拦截面前移到构建期
    (运行期实况 = 发放腿类别池查空防御 log + 条目保留)。"""
    monkeypatch.setattr(cw_investments, 'equips_by_category',
                        lambda category: ())
    with pytest.raises(ValueError, match='类别漂移'):
        _validate_strategy_delayed_grants()
