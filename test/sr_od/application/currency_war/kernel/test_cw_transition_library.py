"""过渡阵容库与候选机器测试面(comp-structure-unification 3.3)。

锁定对象 = 详设(details/transition-library.md)的关键设计约定:
- 建库结构:四条目三型口径/required_deployed 建库自动填/or_reqs ⊆ 档 0;
- 计分基准集 = 见即买集(按型展开,点名型不含羁绊凑数件);
- 候选机器:持有计分开局全 0、词缀减分软排除、top3 与注册序、
  锁定评估域 = 候选槽内条目(候选外偶然凑齐不锁)、锁后不换。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_box,
)

from sr_od.application.currency_war.kernel.cw_comps import (
    TRANSITION_ENTRY_KIND,
    TRANSITION_LIBRARY,
    form_progress,
)
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    TRANSIT_AFFIX_PENALTY_SCORE,
    IntentionState,
    transition_entry_of,
    transition_library_buy_now_union,
    transition_member_set,
    update_transition_candidates,
)

_TRIO = ('爻光', '藿藿', '丹恒·饮月')


def _lib(name: str):
    e = transition_entry_of(name)
    assert e is not None, f'过渡条目名未注册: {name}'
    return e


def test_library_structure_and_autofill() -> None:
    """四条目三型;required_deployed 建库自动填 = core(点名/混合型);
    faction_reqs 只填档 0 且值 = 体系卡判据档;or_reqs 键 ⊆ 档 0。"""
    assert [e.name for e in TRANSITION_LIBRARY] == [
        '仙舟铁三角', '廉价DOT', '列车骨架', '希儿引擎']
    assert set(TRANSITION_ENTRY_KIND) == {e.name for e in TRANSITION_LIBRARY}
    for e in TRANSITION_LIBRARY:
        # 羁绊要求只填档 0(无更高档)
        assert set(e.faction_reqs) <= {0}, f'{e.name}: 过渡条目禁更高档'
        # 点名型/混合型:required_deployed = core_chars(引擎不可拆语义)
        # 羁绊型:core 空 → required 恒空
        assert e.required_deployed == tuple(e.core_chars)
        # or_reqs 键 ⊆ 档 0 键(承接规则,同键同值)
        assert {k for k, _t in e.or_reqs} <= set(e.core_faction_reqs)
    assert _lib('仙舟铁三角').faction_reqs == {0: {'仙舟': 3}}
    assert _lib('廉价DOT').faction_reqs == {0: {'持续伤害': 2}}
    assert _lib('列车骨架').faction_reqs == {0: {'列车同行': 2}}
    seele = _lib('希儿引擎')
    assert seele.faction_reqs == {0: {'量子同频': 2, '贝洛伯格': 2}}
    assert seele.or_reqs == [('量子同频', 2), ('贝洛伯格', 2)]
    # need_star 数值取自体系卡 star_goal,就地复制
    assert _lib('仙舟铁三角').need_star == dict.fromkeys(_TRIO, 2)
    assert seele.need_star == {'希儿': 3}


def test_member_set_by_kind() -> None:
    """计分基准集 = 见即买集按型展开:点名型 = 点名集(羁绊凑数件不进);
    羁绊型 = 羁绊全体注册成员;混合型 = 点名 ∪ 羁绊成员(去重)。"""
    # 点名型:仙舟全体 9 人中只有铁三角三人入集(引擎不可拆)
    assert transition_member_set(_lib('仙舟铁三角')) == set(_TRIO)
    assert transition_member_set(_lib('列车骨架')) == {'姬子·启行', '三月七'}
    # 羁绊型:持续伤害全体(桑博/卡芙卡/黑天鹅等,不限定人)
    dot = transition_member_set(_lib('廉价DOT'))
    assert {'桑博', '卡芙卡', '黑天鹅'} <= dot
    # 混合型:希儿点名 + 量子/贝放大器全体;希儿双标签只计一次(集合语义)
    seele = transition_member_set(_lib('希儿引擎'))
    assert '希儿' in seele and '花火' in seele and '佩拉' in seele
    assert len(seele) == 10
    # 冷启动/回退键域 = 全体条目见即买并集
    assert len(transition_library_buy_now_union()) == 20


def test_opening_all_zero_no_candidates() -> None:
    """开局持有全 0:候选空、未锁(空窗合法形态)。"""
    gs = cw4_box()
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    assert st.transition_candidates == ()
    assert ist.transition_locked == ''


def test_scoring_ranks_by_holds() -> None:
    """持有分排序:希儿+花火(混合型 2 分)压过桑博(羁绊型 1 分),
    候选按(分数降序,注册序)落槽。"""
    gs = cw4_box(bench=[cw4_bc('希儿'), cw4_bc('花火'), cw4_bc('桑博')])
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    assert st.transition_candidates == ('希儿引擎', '廉价DOT')


def test_affix_penalty_soft_excludes() -> None:
    """词缀减分制:量子熄火局希儿引擎被软排除(纯减分不设一票否决),
    未被克方向照常候选。"""
    gs = cw4_box(bench=[cw4_bc('希儿'), cw4_bc('花火'), cw4_bc('桑博')],
                 enemy_affixes=['量子熄火'])
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    # 希儿引擎 2 − 150 < 0 → 不入候选;廉价 DOT 1 分照常
    assert st.transition_candidates == ('廉价DOT',)
    assert TRANSIT_AFFIX_PENALTY_SCORE < 0


def test_lock_on_formed_candidate_and_no_relock() -> None:
    """候选内成型即锁(廉价 DOT 板面达标);锁后不换(新成型条目不改锁)。"""
    gs = cw4_box(front_row=[Unit(char_id='桑博', star=1),
                            Unit(char_id='艾丝妲', star=1)],
                 board={'持续伤害': 2})
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    # 桑博兼贝洛伯格成员 → 希儿引擎同帧 1 分入候选(混合型羁绊半边覆盖)
    assert st.transition_candidates == ('廉价DOT', '希儿引擎')
    assert ist.transition_locked == '廉价DOT'
    assert form_progress(_lib('廉价DOT'), gs) >= 1.0
    # 下一帧希儿方向也成型:锁不换(锁后不换、不解、不重评)
    gs2 = cw4_box(front_row=[Unit(char_id='希儿', star=1),
                             Unit(char_id='花火', star=1),
                             Unit(char_id='桑博', star=1)],
                  board={'量子同频': 2, '持续伤害': 2})
    update_transition_candidates(gs2, ist, st)
    assert ist.transition_locked == '廉价DOT'


def test_no_lock_outside_candidates() -> None:
    """候选外偶然凑齐不锁:板面羁绊计数达标但零成员持有 → 计分 0 →
    不入候选 → 不锁(计分门控防偶然锁定)。"""
    gs = cw4_box(board={'持续伤害': 2})
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    assert st.transition_candidates == ()
    assert ist.transition_locked == ''
    assert form_progress(_lib('廉价DOT'), gs) >= 1.0  # 板面达标但计分门控拦截


def test_required_deployed_gates_engine_entries() -> None:
    """点名型引擎条件(required 逐名折条):持 2/3 铁三角不锁;
    三人全在板才锁(「引擎不可拆」语义)。"""
    gs2 = cw4_box(
        front_row=[Unit(char_id='爻光', star=1),
                   Unit(char_id='藿藿', star=1)],
        board={'仙舟': 2})
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs2, ist, st)
    assert ist.transition_locked == ''   # 2/3 引擎,form < 1
    gs3 = cw4_box(
        front_row=[Unit(char_id=n, star=1) for n in _TRIO],
        board={'仙舟': 3})
    update_transition_candidates(gs3, ist, st)
    assert ist.transition_locked == '仙舟铁三角'
