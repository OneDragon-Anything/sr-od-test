"""过渡组合条目库与候选机器测试面(or-reqs-retirement 3.2)。

锁定对象 = 详设(details/transition-combos.md)的关键设计约定:
- 建库结构:五块构造块两两组合恒 10 条/字段合并规则/建库校验五条;
- 计分成员域 = 见即买集(块级域并集,点名块不含羁绊凑数件);
- 候选机器:持有计分开局全 0、词缀减分 7+3 粒度、top3 与注册序
  tie-break(单一实现在 transition_scores);
- 锁定语义:锁定域 = 组合条目(两羁绊完整组合才锁;单羁绊凑出
  任何组合 fp < 1.0 永不锁)、候选外成型不锁、锁后不换。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_box,
)

from sr_od.application.currency_war.kernel.cw_comps import (
    TRANSITION_BONDS,
    TRANSITION_COMBO_PARTS,
    TRANSITION_LIBRARY,
    Comp,
    TransitionBond,
    _validate_transition_combos,
    bond_score_members,
    form_progress,
    transition_bond_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    TRANSIT_AFFIX_PENALTY_SCORE,
    IntentionState,
    transition_entry_of,
    transition_library_buy_now_union,
    transition_member_set,
    transition_scores,
    update_transition_candidates,
)
from sr_od.application.currency_war.knowledge.cw_line_facts import (
    bond_members,
)

_TRIO = ('爻光', '藿藿', '丹恒·饮月')


def _lib(name: str) -> Comp:
    e = transition_entry_of(name)
    assert e is not None, f'过渡条目名未注册: {name}'
    return e


def test_library_structure_generated_combos() -> None:
    """生成器结构锁(设计 §2):库恒 10 条(五块两两组合序),档 0 = 两块
    键 AND,core/required = 两块点名件保序去重(生成期显式填),need_star
    两块合批,其余 Comp 字段缺省空。"""
    assert [e.name for e in TRANSITION_LIBRARY] == [
        '仙舟3+DOT2', '仙舟3+列车2', '仙舟3+希儿量2', '仙舟3+希儿贝2',
        'DOT2+列车2', 'DOT2+希儿量2', 'DOT2+希儿贝2',
        '列车2+希儿量2', '列车2+希儿贝2', '希儿量2+希儿贝2']
    by_name = {e.name: e for e in TRANSITION_LIBRARY}
    assert set(TRANSITION_COMBO_PARTS) == set(by_name)
    for name, parts in TRANSITION_COMBO_PARTS.items():
        a, b = (transition_bond_of(p) for p in parts)
        assert a is not None and b is not None and a is not b
        e = by_name[name]
        assert e.faction_reqs == {0: {a.bond: a.tier, b.bond: b.tier}}, \
            f'{name}: 档 0 = 两块 (bond, tier) AND,且只填档 0'
        assert e.core_chars == list(dict.fromkeys((*a.named, *b.named))), \
            f'{name}: core = 两块点名件保序去重'
        assert e.required_deployed == tuple(e.core_chars), \
            f'{name}: required 生成期显式填 = core'
        assert e.need_star == {n: s for blk in (a, b) for n, s in blk.need_star}
    # 去重证据:希儿双修两块点名合并为一人
    assert by_name['希儿量2+希儿贝2'].core_chars == ['希儿']
    # need_star 合并证据:仙舟3+希儿量2 = 铁三角三人各 2 + 希儿 3
    assert by_name['仙舟3+希儿量2'].need_star == {
        '爻光': 2, '藿藿': 2, '丹恒·饮月': 2, '希儿': 3}
    assert by_name['DOT2+列车2'].need_star == {}
    # 其余 Comp 字段缺省空(过渡只填档 0)
    for e in TRANSITION_LIBRARY:
        assert e.key_equips == [] \
            and e.shared_chars == [] and e.flex_factions == []


def test_bond_score_members_domains() -> None:
    """块计分域(设计 §1):点名型 = 点名集(羁绊凑数件不进);羁绊型与
    混合型 = 点名 ∪ 羁绊全体注册成员;combo 条目见即买集 = 两块域并集
    (跨点名/多羁绊阵营按角色去重);未知名(旧条目名/防御态)返空集。"""
    xz = transition_bond_of('仙舟3')
    assert bond_score_members(xz) == set(_TRIO)
    assert '青雀' not in bond_score_members(xz), '仙舟凑数件非证据(点名型)'
    train = transition_bond_of('列车2')
    assert bond_score_members(train) == {'姬子·启行', '三月七'}
    assert '瓦尔特' not in bond_score_members(train), '任意列车成员非证据'
    assert bond_score_members(transition_bond_of('DOT2')) \
        == bond_members('持续伤害')
    assert bond_score_members(transition_bond_of('希儿量2')) \
        == {'希儿'} | bond_members('量子同频')
    b2 = transition_bond_of('希儿贝2')
    assert bond_score_members(b2) == {'希儿'} | bond_members('贝洛伯格')
    # combo 展开 = 两块域并集;希儿跨点名/双阵营只计一次(5+6-1=10)
    assert transition_member_set(_lib('希儿量2+希儿贝2')) \
        == bond_score_members(transition_bond_of('希儿量2')) \
        | bond_score_members(b2)
    assert len(transition_member_set(_lib('希儿量2+希儿贝2'))) == 10
    assert transition_member_set(_lib('仙舟3+DOT2')) \
        == set(_TRIO) | bond_members('持续伤害')
    # 未知名(旧库退役条目名)防御态返空集
    assert transition_member_set(Comp(name='希儿引擎', core_chars=[])) == set()
    # 冷启动并集 = 五块计分域并集(组合并集 = 五块域并集,与旧库并集
    # 等值——沿旧库 20 人断言值作等值凭据)
    expected: set[str] = set()
    for blk in TRANSITION_BONDS:
        expected |= bond_score_members(blk)
    union = transition_library_buy_now_union()
    assert union == frozenset(expected)
    assert len(union) == 20


def test_validation_rejects_illegal_bonds() -> None:
    """建库校验五条(设计 §4;模块级真值调用 = import 期防线,import 成功
    即证真值合法),非法构造直接断言 ValueError(逐条独立命中)。"""
    # ① 库长 != C(n,2)(真值五块配截断库)
    with pytest.raises(ValueError, match='库长'):
        _validate_transition_combos(
            TRANSITION_BONDS, TRANSITION_COMBO_PARTS, TRANSITION_LIBRARY[:9])
    # ① parts 键集 != 条目名集(真值库配空 parts)
    with pytest.raises(ValueError, match='键集'):
        _validate_transition_combos(TRANSITION_BONDS, {}, TRANSITION_LIBRARY)
    # ② 五块 bond 互斥(两块同 bond,配对合法小库绕过①)
    dup = TransitionBond(name='X', bond='仙舟', tier=3,
                         named=(), need_star=(), hybrid=True)
    with pytest.raises(ValueError, match='互斥|冲突'):
        _validate_transition_combos(
            (transition_bond_of('仙舟3'), dup),
            {'仙舟3+X': ('仙舟3', 'X')},
            [Comp(name='仙舟3+X', core_chars=[],
                  faction_reqs={0: {'仙舟': 3}})])
    # ③ 点名件不在 CHARACTERS 注册表(单块配空库:C(1,2)=0)
    ghost = TransitionBond(name='G', bond='仙舟', tier=3,
                           named=('不存在的人',), need_star=(), hybrid=False)
    with pytest.raises(ValueError, match='注册表'):
        _validate_transition_combos((ghost,), {}, [])
    # ④ need_star 键 ⊄ named
    stray = TransitionBond(name='S', bond='仙舟', tier=3,
                           named=(), need_star=(('希儿', 3),), hybrid=True)
    with pytest.raises(ValueError, match='need_star'):
        _validate_transition_combos((stray,), {}, [])
    # ⑤ 点名件费段位面 1 不可刷(银狼 4 费,lv5 起才刷)
    pricey = TransitionBond(name='P', bond='量子同频', tier=2,
                            named=('银狼',), need_star=(), hybrid=True)
    with pytest.raises(ValueError, match='费段'):
        _validate_transition_combos((pricey,), {}, [])


def test_opening_all_zero_no_candidates() -> None:
    """开局持有全 0:候选空、未锁(空窗合法形态)。"""
    gs = cw4_box()
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    assert st.transition_candidates == ()
    assert ist.transition_locked == ''


def test_scoring_ranks_and_registration_tiebreak() -> None:
    """持有分排序 + tie-break(设计 §3):分数降序,同分按注册序(排序键
    单一实现在 transition_scores,返回有序全序);候选槽 = 前 3 切片。"""
    held = {'希儿', '花火', '桑博'}
    assert transition_scores(held, ()) == [
        ('DOT2+希儿量2', 3.0), ('希儿量2+希儿贝2', 3.0),
        ('仙舟3+希儿量2', 2.0), ('仙舟3+希儿贝2', 2.0),
        ('DOT2+希儿贝2', 2.0), ('列车2+希儿量2', 2.0),
        ('列车2+希儿贝2', 2.0),
        ('仙舟3+DOT2', 1.0), ('DOT2+列车2', 1.0)]
    gs = cw4_box(bench=[cw4_bc('希儿'), cw4_bc('花火'), cw4_bc('桑博')])
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    assert st.transition_candidates == (
        'DOT2+希儿量2', '希儿量2+希儿贝2', '仙舟3+希儿量2')


def test_affix_penalty_hits_seven_of_ten() -> None:
    """词缀减分粒度(3.2 行为申报 3):量子熄火命中含量子/贝键的 7 条
    组合(双修条两边都含、按条目只计 1 次),其余 3 条组合上位
    (7 + 3 = 10 = 库容;减分制软排除,非一票否决)。"""
    held = {'希儿', '花火', '桑博', '爻光', '姬子·启行'}
    assert len(transition_scores(held, ())) == 10, '无克制源帧全库有分(对照)'
    ranked = transition_scores(held, ('量子熄火',))
    assert ranked == [('仙舟3+DOT2', 2.0), ('仙舟3+列车2', 2.0),
                      ('DOT2+列车2', 2.0)], '未被克三方向照常,按注册序'
    assert TRANSIT_AFFIX_PENALTY_SCORE < 0
    # 命中域划分:含希儿量2/希儿贝2 块的 7 条;7 + 3 = 库容
    penalized = {n for n, parts in TRANSITION_COMBO_PARTS.items()
                 if '希儿量2' in parts or '希儿贝2' in parts}
    assert len(penalized) == 7
    assert penalized | {n for n, _s in ranked} \
        == {e.name for e in TRANSITION_LIBRARY}
    # 端到端:词缀经开局简报观察通道生效
    gs = cw4_box(bench=[cw4_bc(n) for n in held],
                 enemy_affixes=['量子熄火'])
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    assert st.transition_candidates == ('仙舟3+DOT2', '仙舟3+列车2', 'DOT2+列车2')


def test_single_bond_never_locks() -> None:
    """单羁绊凑出永不锁(3.2 行为申报 1/2):仅仙舟3 成型(DOT 缺)时
    任何组合条目 fp < 1.0(另一键必缺)——锁定域 = 组合,单羁绊构造块
    不是条目;候选照常活动(软方向,买面双向)。"""
    gs = cw4_box(front_row=[Unit(char_id=n, star=1) for n in _TRIO],
                 board={'仙舟': 3})
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    assert st.transition_candidates, '单羁绊局候选照常活动(软方向)'
    for e in TRANSITION_LIBRARY:
        assert form_progress(e, gs) < 1.0, f'{e.name}: 单羁绊局 fp < 1'
    assert ist.transition_locked == ''


def test_combo_formed_locks_and_no_relock() -> None:
    """锁定语义(3.2 行为申报 1):组合成型才锁——仙舟3+DOT2 两羁绊齐
    ∧ 铁三角三人在板;required 逐名门控(2/3 在板不锁);锁后不换。"""
    # 2/3 铁三角在板(羁绊计数达标、required 缺一):fp < 1 不锁
    gs2 = cw4_box(
        front_row=[Unit(char_id='爻光', star=1),
                   Unit(char_id='藿藿', star=1)],
        board={'仙舟': 3, '持续伤害': 2})
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs2, ist, st)
    assert ist.transition_locked == '', '2/3 引擎,required 逐名折条不满'
    # 组合成型:两羁绊齐 + 三人全在板 → 锁
    gs3 = cw4_box(
        front_row=[*[Unit(char_id=n, star=1) for n in _TRIO],
                   Unit(char_id='桑博', star=1)],
        back_row=[Unit(char_id='卡芙卡', star=1)],
        board={'仙舟': 3, '持续伤害': 2})
    update_transition_candidates(gs3, ist, st)
    assert ist.transition_locked == '仙舟3+DOT2'
    # 锁后不换:新帧双修组合也成型,锁保持(锁后不换、不解、不重评)
    gs4 = cw4_box(
        front_row=[*[Unit(char_id=n, star=1) for n in _TRIO],
                   Unit(char_id='希儿', star=1)],
        back_row=[Unit(char_id='花火', star=1),
                  Unit(char_id='佩拉', star=1)],
        board={'量子同频': 2, '贝洛伯格': 2})
    assert form_progress(_lib('希儿量2+希儿贝2'), gs4) >= 1.0, '双修同帧成型(前置)'
    update_transition_candidates(gs4, ist, st)
    assert ist.transition_locked == '仙舟3+DOT2'


def test_no_lock_outside_candidates() -> None:
    """锁定评估域 = 候选槽内条目:多条组合同帧成型时锁候选序首位;
    候选外 fp=1.0 条目(仙舟3+DOT2 持有分第 4 落榜)不进锁定评估——
    计分排序先于锁定评估,候选外凑齐不锁。"""
    gs = cw4_box(
        front_row=[*[Unit(char_id=n, star=1) for n in _TRIO],
                   Unit(char_id='希儿', star=1)],
        back_row=[Unit(char_id=n, star=1)
                  for n in ('桑博', '卡芙卡', '花火', '银狼', '佩拉', '杰帕德')],
        board={'仙舟': 3, '持续伤害': 2, '量子同频': 2, '贝洛伯格': 2})
    ist = IntentionState()
    st = SimpleNamespace()
    update_transition_candidates(gs, ist, st)
    assert st.transition_candidates == (
        '仙舟3+希儿贝2', '仙舟3+希儿量2', '希儿量2+希儿贝2')
    assert form_progress(_lib('仙舟3+DOT2'), gs) >= 1.0, '候选外条目同帧成型(前置)'
    assert '仙舟3+DOT2' not in st.transition_candidates
    assert ist.transition_locked == '仙舟3+希儿贝2', '锁候选序首位 fp=1 条目'
