"""cw_formation(08 号阵型层 v0)测试:规则锚点 + 退化正确性(ADR-0165)。"""
from sr_od.application.currency_war.cw_formation import decide_formation


def _units():
    return [
        {'name': '万敌', 'position_pref': 'front', 'char_type': '输出', 'star': 2, 'is_carry': True},
        {'name': '杰帕德', 'position_pref': 'front', 'char_type': '坦克·护盾', 'star': 1},
        {'name': '符玄', 'position_pref': 'back', 'char_type': '治疗', 'star': 1},
        {'name': '姬子·启行', 'position_pref': 'back', 'char_type': '输出', 'star': 1, 'is_carry': True},
        {'name': '三月七', 'position_pref': 'back', 'char_type': '辅助', 'star': 1},
    ]


def test_no_semantics_degrades_to_status_quo():
    """对拍锚点:无阵型语义词缀/增强 → 先验填序(排内按韧性稳定排,成员集=先验分排)。"""
    plan = decide_formation(_units())
    assert sorted(plan.front) == ['万敌', '杰帕德']       # 前排成员集 = 先验 front
    assert sorted(plan.back) == ['三月七', '姬子·启行', '符玄']
    assert '现状行为' in plan.reasons[0]
    # 排内排序确定(坦克先于输出,可复现)
    assert plan.front[0] == '杰帕德'


def test_front_lock_moves_carry_back():
    """词缀锚:前台熄火 → 前排 carry(万敌)移后排。"""
    plan = decide_formation(_units(), affixes=['前台熄火'])
    assert '万敌' in plan.back
    assert '杰帕德' in plan.front   # 坦克非 carry 不动


def test_aggro1_puts_toughest_first():
    """词缀锚:灼热轰炸 → 1 号位(前排首位)放最扛者(杰帕德)。"""
    plan = decide_formation(_units(), affixes=['灼热轰炸'])
    assert plan.front[0] == '杰帕德'
    assert plan.slot('杰帕德') == ('front', 1)


def test_back_lock_moves_carry_front():
    plan = decide_formation(_units(), affixes=['后台熄火'])
    assert '姬子·启行' in plan.front   # 后排 carry 移前排


def test_augment_hard_constraint():
    """增强锚:应援团 → 后排 ≥4(从前排挪最扛的补)。"""
    plan = decide_formation(_units(), held_augments=['应援团'])
    assert len(plan.back) >= 4
    assert any('应援团' in r for r in plan.reasons)


def test_slot_lookup():
    plan = decide_formation(_units())
    assert plan.slot('万敌') == ('front', 1) or plan.slot('万敌')[0] == 'front'
    assert plan.slot('不存在') is None
