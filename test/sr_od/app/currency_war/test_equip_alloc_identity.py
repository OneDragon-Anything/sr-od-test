"""r134 兜底身份过滤测试(用户质询「为什么给砂金」)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_comps import equip_allocation
from sr_od.application.currency_war.cw_state import BenchChar


def _mk_comp():
    from sr_od.application.currency_war.cw_comps import Comp
    return Comp(name='反甲白厄', factions=['贝洛伯格'],
                core_chars=['白厄', '三月七', '姬子·启行'],
                form_tiers={}, strength=5.0, form_difficulty='hard')


def _deployed():
    return [
        BenchChar(slot=1, char_id='砂金', faction='公司', star=1, position_pref='front'),
        BenchChar(slot=2, char_id='白厄', faction='贝洛伯格', star=1, position_pref='front'),
        BenchChar(slot=3, char_id='赛飞儿', faction='夜之半神', star=1, position_pref='front'),
    ]


def test_generic_goes_to_core_first():
    """通用件兜底:core(白厄)先吃满(容量 3 = 全部 3 件),非 core(砂金/赛飞儿)0 件
    (r134 语义:core 全吃 → 非 core 无剩可分;核心换血摩擦最小)。

    r405(ADR-0265)修订:owned 原 生命之花(合成保留组件,P1 现
    不入穿戴池)——换非组件名保持原语义。"""
    comp = _mk_comp()
    alloc = equip_allocation(comp, _deployed(),
                             ['狙击枪', '永动机', '物质分解液'])
    baiyu = [w for c, w in alloc if c == '白厄']
    shajin = [w for c, w in alloc if c == '砂金']
    assert len(baiyu) == 3, f'core 应吃满全部,实得 {baiyu}'
    assert len(shajin) == 0, f'非 core 不与 core 抢,实得 {shajin}'


def test_core_saturated_others_get_leftover():
    """core 吃满后有余量才轮非 core:白厄容量 3,给 4 件时砂金拿第 4 件。"""
    comp = _mk_comp()
    alloc = equip_allocation(comp, _deployed(),
                             ['a', 'b', 'c', 'd'])
    baiyu = [w for c, w in alloc if c == '白厄']
    shajin = [w for c, w in alloc if c == '砂金']
    assert baiyu == ['a', 'b', 'c']
    assert shajin == ['d'], 'core 饱和后非 core 才兜底'


def test_no_comp_keeps_old_behavior():
    """comp=None:全量兜底不变(无身份信息)。"""
    alloc = equip_allocation(None, _deployed()[:1], ['a', 'b', 'c'])
    assert len(alloc) == 3, '无 comp 时前排应吃满全部'


def test_key_equip_path_unchanged():
    """key_equips 分配(1-2 级)不受影响:carry 先拿。"""
    comp = _mk_comp()
    comp.key_equips = ['以牙还牙甲', '以牙还牙甲']
    alloc = equip_allocation(comp, _deployed(), ['以牙还牙甲', '以牙还牙甲'])
    # 白厄(core 首个场上)拿两件以牙还牙甲
    assert ('白厄', '以牙还牙甲') in alloc
    assert sum(1 for c, w in alloc if w == '以牙还牙甲') == 2
