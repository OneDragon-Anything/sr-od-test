"""CW 过渡层体系对候选机器测试面(dual-layer-candidates 迭代 3.1)。

出处 = 迭代设计 ``docs/develop/sr_od/application/currency_war/changes/
2026-11-01-dual-layer-candidates/design.md`` §2.3(候选空间/对级 min 聚合/
门控候选首位/双体系对冻结域/超窗解冻/希儿系门槛)与 §2.6-6/7/9(判据族
换维/物化链/冻结域收窄行为申报);被测对象 = ``kernel/cw_intention.py``
的候选机器族(``p1_pair_candidates_of``/``update_p1_recipe`` 槽写端/
``clear_p1_recipe``)。committed 等价验证与五测语义面在
``test_intention.py``,本文件不重复。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import cw4_box

from sr_od.application.currency_war.kernel import cw_intention as intention_mod
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    clear_p1_recipe,
    p1_pair_candidates_of,
    update_p1_recipe,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    StrategyState,
)


def _p1_gs(deployed, board: dict | None = None, r: int = 5) -> object:
    """P1 备战场景种子(board 显式给,与 deployed 行一致)。"""
    return cw4_box(plane=1, round_num=r, gold=100, level=5, hp=80,
                   shop_refresh_cost=2, node='reward',
                   front_row=list(deployed[:4]), back_row=list(deployed[4:]),
                   board=board or None)


# ============================================================
# 1. 候选机器:支持度驱动重算 / 平手声明序 / 希儿系门槛 / 开局
# ============================================================


def test_candidates_recompute_on_support_change() -> None:
    """候选重算:支持度事件(持有变化)驱动下一帧候选重排(design §2.3-2;
    写端节拍 = 每 game-round 配方链重算,事件驱动帧间稳定,§2.6-6)。

    只吃真实持有:对级支持度 = min 席级——第二体系零支持度时双对
    不入候选(与旧渐进通道「单体系满即产双对方向」的形态差异,
    §2.3-2/§2.6-6)。"""
    # 帧 1:单 DOT 件(0.5)——首位 = DOT 单对(无双对,第二体系 0)
    gs1 = _p1_gs([Unit(char_id='桑博', star=1)])
    cands1 = p1_pair_candidates_of(gs1)
    assert cands1[0] == ('持续伤害',)
    assert all(len(p) == 1 for p in cands1), \
        f'第二体系零支持:双对 min=0 不入候选, {cands1!r}'
    # 帧 2:补 DOT 第二件(1.0)+ 列车件(0.5)——双对点亮入候选
    gs2 = _p1_gs([Unit(char_id='桑博', star=1),
                  Unit(char_id='艾丝妲', star=1),
                  Unit(char_id='三月七', star=1)])
    cands2 = p1_pair_candidates_of(gs2)
    assert cands2[0] == ('持续伤害',)
    assert ('持续伤害', '列车同行') in cands2, \
        f'第二体系 >0 帧双对点亮入候选: {cands2!r}'


def test_tie_break_declaration_order() -> None:
    """平手声明序:对级支持度平手按 ``_P1_PAIR_PREF`` 索引元组字典序,
    短元组(单体系对)同席补 ∞——同首席双体系对排在单体系对前
    (design §2.3-2,零新常数)。"""
    # 持续伤害 1 件 + 列车 1 件:三对全部 0.5 平手
    gs = _p1_gs([Unit(char_id='桑博', star=1),
                 Unit(char_id='三月七', star=1)])
    assert p1_pair_candidates_of(gs) == (
        ('持续伤害', '列车同行'),   # decl (1,2) —— 双对在同首席单对前
        ('持续伤害',),              # decl (1, ∞)
        ('列车同行',),              # decl (2, ∞)
    )


def test_seele_gate_blocks_partial_and_admits_full() -> None:
    """希儿系对入候选门槛 = 席级支持度 = 1.0(design §2.3-2/§2.6-10):
    单卡希儿(0.5)时含希儿系的一切对不入候选(其他体系对不受影响);
    希儿+任 1 去重放大器(=1.0)时候选含希儿系对。

    放大器口径注意:桑博 = 贝洛伯格+DOT 双籍(注册表常态),会点亮
    贝分支——0.5 拦场景用艾丝妲(银河学者/DOT,无量子无贝)做对照组。"""
    # 0.5 拦:希儿单卡 + DOT 0.5 对照(艾丝妲非放大器)
    gs_half = _p1_gs([Unit(char_id='希儿', star=1),
                      Unit(char_id='艾丝妲', star=1)])
    cands_half = p1_pair_candidates_of(gs_half)
    assert cands_half and ('持续伤害',) in cands_half, \
        f'前置:DOT 0.5 单对照常入候选, {cands_half!r}'
    assert all('希儿系' not in p for p in cands_half), \
        f'希儿席级 0.5 < 1.0:含希儿系对全部被门槛拦, {cands_half!r}'
    # 双件去重计数:希儿(量子+贝双标签)+银狼(量子)→ max(2/2,1/2)=1.0
    gs_full = _p1_gs([Unit(char_id='希儿', star=1),
                      Unit(char_id='银狼', star=1)])
    cands_full = p1_pair_candidates_of(gs_full)
    assert ('希儿系',) in cands_full, \
        f'希儿+放大器 = 1.0 门槛过:希儿系单对入候选, {cands_full!r}'


def test_bond_opening_candidates_nonempty() -> None:
    """有羁绊开局候选非空(design §2.3-2:开局四人组含体系标签 → 候选
    非空;无羁绊开局候选空 → 冷启动臂,§2.3-8 归商店侧不在本模块)。"""
    gs = _p1_gs([Unit(char_id='桑博', star=1),
                 Unit(char_id='三月七', star=1),
                 Unit(char_id='符玄', star=1),
                 Unit(char_id='希儿', star=1)])
    assert p1_pair_candidates_of(gs), '有羁绊开局候选非空'


# ============================================================
# 2. p1_pair 门控候选首位:门控带/回落帧/冻结域全扫描
# ============================================================


def test_gated_first_pair_empty_in_partial_band() -> None:
    """门控带行为:p1_pair = 门控候选首位,首位对级支持度 ≥1.0 才写
    (design §2.3-3)——(0,1) 支持度带(全体系 <1.0)候选非空而 p1_pair
    恒空(committed 序②等价性的带内直测);回落帧(在任对从满席跌破)
    同帧清空为空对,事件面 p1_pair:wait。"""
    # (0,1) 带:DOT 0.5——候选非空、门控不写
    gs = _p1_gs([Unit(char_id='桑博', star=1)])
    ist = IntentionState()
    update_p1_recipe(gs, ist, None)
    assert p1_pair_candidates_of(gs), '前置:候选非空'
    assert ist.p1_pair == (), '(0,1) 带门控不写 p1_pair'
    # 回落帧:种入满席在任对后支持度跌破 → 同帧清空
    ist2 = IntentionState()
    ist2.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist2, None)
    assert ist2.p1_pair == (), '回落帧 p1_pair 清空(与旧 gate_first 等价)'
    assert ist2.last_event == 'p1_pair:wait'


def test_freeze_domain_scans_dual_pairs_beyond_first() -> None:
    """冻结域 = 双体系对全扫描(design §2.3-4):扫描序 = 候选排序键应用于
    全空间双对序列(不截断),超满对先于恰满对;取 form_ok(板面成型)
    首个——超满单对居候选首位时冻结对仍 = 扫描域 form_ok 首个双对
    (置位帧 p1_pair 即钉向冻结对;槽写单元素)。"""
    # 仙舟 4 副本(count 4 > tier 3 → sup 4/3 超满)+ DOT 2 件(1.0);
    # 板面仙舟 3 ∧ DOT 2 成型((仙舟,持续伤害) form_ok)
    gs = _p1_gs([Unit(char_id='符玄', star=1)] * 4
                + [Unit(char_id='桑博', star=1),
                   Unit(char_id='艾丝妲', star=1)],
                board={'仙舟': 3, '持续伤害': 2})
    # 门控首位 = 超满单对(4/3 > 1.0,排序在一切恰满对前)
    assert p1_pair_candidates_of(gs)[0] == ('仙舟',)
    ist = IntentionState()
    st = StrategyState()
    update_p1_recipe(gs, ist, None, st=st)
    # 置位帧:冻结对 = 扫描域 form_ok 首个 = (仙舟, 持续伤害)
    assert ist.p1_pair_frozen
    assert ist.p1_pair_frozen_pair == ('仙舟', '持续伤害')
    assert ist.p1_pair == ('仙舟', '持续伤害'), '置位帧即钉向冻结对'
    assert st.transition_candidates == (('仙舟', '持续伤害'),), \
        '冻结后槽写单元素(冻结对,读端零特判)'


def test_frozen_pair_only_dual_never_single() -> None:
    """单体系对板面凑齐不进冻结域(design §2.6-9):单对 form_progress
    = 1.0(板面单体系档满)不触发置位——置位域 = 双对 only;未冻结帧
    槽 = 候选机器 top3(含双对,第二体系件继续在候选承载)。"""
    gs = _p1_gs([Unit(char_id='桑博', star=1),
                 Unit(char_id='艾丝妲', star=1),
                 Unit(char_id='三月七', star=1)],
                board={'持续伤害': 2})
    ist = IntentionState()
    st = StrategyState()
    update_p1_recipe(gs, ist, None, st=st)
    assert not ist.p1_pair_frozen, '单体系板面成型不冻结(单对不进域)'
    assert st.transition_candidates == p1_pair_candidates_of(gs)
    assert ('持续伤害', '列车同行') in st.transition_candidates, \
        '未冻结帧槽 = top3,渐进承载(第二体系件在候选并集)'


# ============================================================
# 3. 超窗解冻状态机(对双对零改动)
# ============================================================


def _formed_dual_ist() -> tuple[IntentionState, object]:
    """DOT 2 + 列车 2 成型帧的 ist/gs(先跑一帧置位冻结)。"""
    gs = _p1_gs([Unit(char_id='桑博', star=1),
                 Unit(char_id='艾丝妲', star=1),
                 Unit(char_id='三月七', star=1),
                 Unit(char_id='丹恒·饮月', star=1)],
                board={'持续伤害': 2, '列车同行': 2})
    ist = IntentionState()
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair_frozen, '前置:双对成型帧置位'
    return ist, gs


def test_unfreeze_overwindow_restores_competition(monkeypatch) -> None:
    """超窗解冻恢复竞争(design §2.3-4:超窗解冻状态机对双对零改动)——
    E > R_rem 触发出口①:解冻 + 封印该对;封印期内(门控首位 == 封印对
    ∧ fp 未见回落)禁止再闩;fp 回落(板面拆)解封后再达成可再闩。"""
    ist, gs = _formed_dual_ist()
    frozen_pair = ist.p1_pair_frozen_pair
    # 帧 1:E=inf(超窗确定性构造,经模块级 e_rounds 单一源 patch)
    monkeypatch.setattr(intention_mod, 'e_rounds', lambda *a, **k: float('inf'))
    update_p1_recipe(gs, ist, None)
    assert not ist.p1_pair_frozen, '超窗出口解冻'
    assert ist.p1_pair_refreeze_hold == frozen_pair, '解冻封印该对'
    assert 'unfreeze_overwindow' in str(ist.last_event)
    # 帧 2:板面仍成型 → 门控首位 == 封印对 ∧ fp ≥1.0 → 封印保持不再闩
    update_p1_recipe(gs, ist, None)
    assert not ist.p1_pair_frozen, '封印期内不再闩(防逐帧空转环)'
    assert ist.p1_pair_refreeze_hold == frozen_pair
    # 帧 3:板面拆(列车档丢,fp 回落)→ 解封(支持度读持有不降,门控
    # 首位仍 == 封印对,解封由 fp 回落承载)
    gs_broken = _p1_gs([Unit(char_id='桑博', star=1),
                        Unit(char_id='艾丝妲', star=1),
                        Unit(char_id='三月七', star=1),
                        Unit(char_id='丹恒·饮月', star=1)],
                       board={'持续伤害': 2})
    update_p1_recipe(gs_broken, ist, None)
    assert ist.p1_pair_refreeze_hold == (), 'fp 回落解封(方向丢失)'
    assert not ist.p1_pair_frozen, '回落帧不置位'
    # 帧 4:板面恢复成型 → 再达成 = 新 form_ok 事件,允许再闩
    gs_again = _p1_gs([Unit(char_id='桑博', star=1),
                       Unit(char_id='艾丝妲', star=1),
                       Unit(char_id='三月七', star=1),
                       Unit(char_id='丹恒·饮月', star=1)],
                      board={'持续伤害': 2, '列车同行': 2})
    update_p1_recipe(gs_again, ist, None)
    assert ist.p1_pair_frozen, '再达成允许再闩'
    assert ist.p1_pair_frozen_pair == frozen_pair


# ============================================================
# 4. 进 P2 清空 + 槽写端单一
# ============================================================


def test_p2_entry_clears_slot_and_pair() -> None:
    """进 P2 清空(design §2.3-6):clear_p1_recipe 同点清空
    transition_candidates 槽与 opening_recipe_comp(写端单一出口),
    配方锁字段族同帧归零。"""
    st = StrategyState()
    st.transition_candidates = (('持续伤害',),)
    st.opening_recipe_comp = object()
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    ist.p1_pair_frozen = True
    ist.p1_pair_frozen_pair = ('持续伤害',)
    clear_p1_recipe(ist, st)
    assert st.transition_candidates == (), '进 P2 槽清空'
    assert st.opening_recipe_comp is None
    assert ist.p1_pair == () and not ist.p1_pair_frozen


def test_slot_written_only_via_recipe_chain() -> None:
    """槽写端单一 = 配方链重算(design §2.3-3):``st`` 传参时随贵段覆写
    (未冻结帧 top3);st 缺席(裸 kernel 调用)不写——已有槽值不被裸
    调用覆写,消费面读槽须走 flow 贵段接线,禁现算第二源。"""
    gs = _p1_gs([Unit(char_id='桑博', star=1),
                 Unit(char_id='艾丝妲', star=1),
                 Unit(char_id='三月七', star=1)])
    st = StrategyState()
    ist = IntentionState()
    update_p1_recipe(gs, ist, None, st=st)
    assert st.transition_candidates, 'st 传参时槽写 top3'
    assert st.transition_candidates == p1_pair_candidates_of(gs), \
        '槽值 = 候选机器同源输出'
    st_raw = StrategyState()
    st_raw.transition_candidates = (('旧值',),)   # 种入已有值
    update_p1_recipe(gs, IntentionState(), None)   # 裸调用不传 st
    assert st_raw.transition_candidates == (('旧值',),), \
        'st 缺席不写(已有槽值不被覆写,禁双源)'

