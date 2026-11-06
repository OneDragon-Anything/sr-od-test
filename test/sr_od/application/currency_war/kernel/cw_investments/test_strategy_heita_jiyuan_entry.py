"""黑塔纪元(id 352601)条目锁(cw_investments 分目录镜像;UNIT_BUFF 族
战力类零响应登记 + GRANTS 条目现状;先例 = 同目录
test_strategy_sansan_entry.py 三三三)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-409-heita-
jiyuan.md §2.5/§4 锁 1/锁 3 + §5.1 用户终裁(2026-11-06)。卡面官方原文:
「出战时，你拥有的【黑塔】们每有1总金币价值，都使【黑塔】们追击时额外
转一圈。你拥有的【黑塔】们每有1总金币价值，使【黑塔】/【大黑塔】获得
10%前后台强度。」(强度效果条目 UNIT_BUFF 零响应登记,计量与数值游戏侧
自算 bot 零响应;追击转圈效果条目型③两边皆盲零登记,不入条目载体):

- 条目锁:PLANE_START 占位形 / WHILE_HELD / UNIT_BUFF / payload
  UnitBuffRef 且 effect_text 与卡面单一源对拍 / id 352601 / duties 三位
  全 False / pending False;
- PLAZA_AUGMENTS 恰一命中:id 352601 在数据面注册表恰一条(effect_text
  经数据面表达式单一源,重复登记会使单一源失效);
- 现金 fail-closed 锁:条目载荷非 EconomyEffect = 经济面零承载;
- GRANTS 条目现状锁:STRATEGY_GRANTS['黑塔纪元'] chars_immediate/
  chars_conditional 逐字段断言(估值域登记防漂移,本批零动作面)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_invest_data import (
    PLAZA_AUGMENTS,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    EffectKind,
    TriggerKind,
    UnitBuffRef,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
)

_CARD = '黑塔纪元'
_CID = '352601'


def test_heita_jiyuan_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(三三三同形;五元组逐位 + id 对拍;
    duties 三位全 False;pending False);构建校验(孤儿键/id 双匹配)
    import 期已过。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == _CID, 'id 对拍'
    assert spec.name == _CARD
    assert spec.trigger is TriggerKind.PLANE_START, '占位形(无离散触发)'
    assert spec.duration is DurationKind.WHILE_HELD, '持有期绑定'
    assert spec.category is EffectKind.UNIT_BUFF, 'category = UNIT_BUFF'
    assert isinstance(spec.payload, UnitBuffRef), '载荷 = UnitBuffRef'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_heita_jiyuan_effect_text_single_source() -> None:
    """effect_text 与卡面单一源对拍(经 PLAZA_AUGMENTS 数据面表达式,
    版本更新改文自动跟随;id 漂移 = StopIteration import 即炸,本条目
    存活即证)。"""
    assert STRATEGY_EFFECTS[_CARD].payload.effect_text \
        == INVESTMENT_STRATEGIES[_CARD].effect, \
        'effect_text 单一源对拍(= base 注册表 .effect)'


def test_heita_jiyuan_plaza_exactly_one_hit() -> None:
    """PLAZA_AUGMENTS 恰一命中:id 352601 在数据面注册表恰一条(payload
    表达式 next() 取首条,多条命中会静默取错条,唯一性唯本锁可暴露)。"""
    hits = [a for a in PLAZA_AUGMENTS if a.id == _CID]
    assert len(hits) == 1, f'id {_CID} 恰一命中: {len(hits)}'
    assert hits[0].name == _CARD, '数据面条目名对拍'


def test_heita_jiyuan_cash_fail_closed() -> None:
    """现金 fail-closed 锁:战力类零响应登记无经济面——条目载荷非
    EconomyEffect 载体 = 经济聚合面零承载。"""
    assert not hasattr(STRATEGY_EFFECTS[_CARD].payload, 'gold_per_node'), \
        'UNIT_BUFF 载体非 EconomyEffect(经济面零承载)'


def test_heita_jiyuan_grants_entry_shape() -> None:
    """GRANTS 条目现状锁(估值域登记,本批零动作面):chars_immediate =
    大黑塔直读;chars_conditional = 大黑塔×条件句原文;无 items/advisor
    等其余字段混入(即时/条件双效果条目单卡条目形)。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_immediate == ('大黑塔',), \
        f'即时效果条目漂移: {grant.chars_immediate!r}'
    assert grant.chars_conditional == \
        (('大黑塔', '你获得3星【黑塔】时获得【大黑塔】'),), \
        f'条件效果条目漂移: {grant.chars_conditional!r}'
    assert grant.items_immediate == () and grant.items_scheduled == (), \
        '无道具效果条目(216 张黑塔供给面不入册)'
    assert grant.advisor is False, '非顾问卡'
