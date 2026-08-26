# -*- coding: utf-8 -*-
"""W126/ADR-0349 步③「切调度」单帧锁(经济循环总模型迁移收口)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① V_D 批口径正分帧(金 100/r8/c5 概率窗核心未齐,D 候选正分
  =W119 锁④ 升级版;附金口径断言:批成本项在分内);
- ③ c=2@L4 型格子(k=1)升级判负(P5 边界 a:升级收益侧 k 放大后
  仍不过平台账);
- ⑦ V_level 省刷金项:k 放大(k 剩余多→省刷金大)+ 峰值以上为 0
  (P5 边界 b);
- ⑧ 概率窗二分([3]/通道表冲突消解:goal=level_up→D 让位,
  goal=roll→V_D 生效);
- ④ 34 帧误拒形态(cap 满+bench 目标件+花后<form_floor)→本批
  修复后放行;金不足对照仍拒;
- ⑤ 追赶态退场静态断言(覆盖序/字段/标签集无 catchup);
- ⑥ war 模式帧 refresh 候选在场(war 滤 refresh 废除)。
(②金 50/51 拒 D/≥52+放行四格=P5⑤ 既有锁 test_w120_p5_c_interest_
boundary,W126 复核通过,不重复立锁。)
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import IntentionState
from sr_od.application.currency_war.cw_shop_odds import (
    expected_refreshes_for_card,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    LevelUp,
    RefreshShop,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.candidates import (
    Candidate,
    _target_names,
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.ev import (
    levelup_ev_authorized,
    levelup_refresh_saving,
)
from sr_od.application.currency_war.decision_v2.filters import (
    filter_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
    vd_refresh_score,
)

_REG = DEFAULT_REGISTRY


def _locked_sess(comp: str) -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp=comp)
    s.target_comp = get_comp(comp)
    s.v3_mode = 'economy'
    return s


def _state(level: int, copies: list[str], gold: int, r: int, *,
           comp: str = 'DOT队', deployed: int = 4,
           node: str = 'battle') -> tuple[GameState, StrategySession]:
    s = _locked_sess(comp)
    st = GameState(
        plane=1, round_num=r, gold=gold, level=level, hp=60,
        deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1)
                  for i in range(deployed)],
        bench=[BenchChar(slot=i, char_id=n, faction='公司', star=1)
               for i, n in enumerate(copies)],
        shop=[], node_type=node)
    return st, s


# --- ① V_D 批口径正分帧(W119 锁④ 升级版)------------------------------------


def test_vd_batch_caliber_positive_frame() -> None:
    """①金 100/r8/c5 概率窗(Archer,命运圣杯红A L10 roll)核心未齐
    (j=2,k=1):refresh 候选正分。断言三件:
    - 评分>0(V_D 生效,非恒 0/负);
    - 分值=vd_refresh_score(批口径金账,含 E×刷价成本项——
      val < 收益侧毛值,证明批成本在分内);
    - 离窗对照(L8:概率窗未到)为负(批成本放大,不硬 D)。"""
    st, s = _state(10, ['Archer', 'Archer'], 100, 8,
                   comp='命运圣杯红A')
    vd = vd_refresh_score(st, s, _REG)
    assert vd is not None and vd > 0, vd
    cand = [c for c in generate_candidates(st, s, _REG)
            if c.tag == 'refresh'][0]
    val, _bd = score_candidate(cand, st, s, _REG)
    assert val == vd, (val, vd)
    # 批成本项在分内:收益毛值(1.6R+9.05)> val(净)=毛值−E×刷价
    from sr_od.application.currency_war.decision_v2.ev import (
        cross_plane_remaining_nodes,
    )
    gross = (1.6 * cross_plane_remaining_nodes(st) + 9.05)
    assert val < gross, '批口径成本项(E×刷价)必须在分内(禁单次边际)'
    # 离窗对照:L8(c5 概率 p=0.03)→ 批成本爆炸 → 负分
    st8, s8 = _state(8, ['Archer', 'Archer'], 100, 8,
                     comp='命运圣杯红A')
    vd8 = vd_refresh_score(st8, s8, _REG)
    assert vd8 is not None and vd8 < 0, vd8


def test_vd_requires_opened_core() -> None:
    """V_D 目标语境=核心已开张(≥1 张):0 张时 D 关闭(攒自然刷新+
    买入压库;[1] r1/r2 不 D 的保守侧落法,ADR-0349 记档)。
    L4=DOT队 plan roll 窗内(排除窗二分干扰)。"""
    st, s = _state(4, [], 60, 4)
    assert vd_refresh_score(st, s, _REG) is None
    st2, s2 = _state(4, ['卡芙卡'], 60, 4)
    assert vd_refresh_score(st2, s2, _REG) is not None


# --- ⑦ V_level 省刷金项:k 放大 + 峰值以上为 0(P5 检验点②)-------------------


def test_levelup_saving_k_amplification() -> None:
    """⑦省刷金随 k(剩余张数)放大:c2@L4,k=2(j=1)的省刷金 >
    k=1(j=2)——升级收益侧必须过 k 放大总账(P5 边界 a 的判据本体);
    峰值以上(L6→L7,c2 峰值在 L6)ΔE≤0 → saving=0(P5 边界 b:
    峰值级/峰值以上停留最优,不设独立峰值惩罚)。"""
    st_k2, s_k2 = _state(4, ['卡芙卡'], 50, 4)      # j=1 → k=2
    st_k1, s_k1 = _state(4, ['卡芙卡', '卡芙卡'], 50, 4)   # j=2 → k=1
    sv2 = levelup_refresh_saving(st_k2, s_k2, _REG)
    sv1 = levelup_refresh_saving(st_k1, s_k1, _REG)
    assert sv2 > sv1 > 0, (sv2, sv1)
    # 表值对拍:sv1 = 刷价×(E(L4,j2)−E(L5,j2))
    e = (expected_refreshes_for_card(4, 2, 2, owned=2)
         - expected_refreshes_for_card(5, 2, 2, owned=2))
    assert abs(sv1 - e * 2) < 1e-6
    # 峰值以上:L6(c2 峰值)→L7 概率降 → 0
    st6, s6 = _state(6, ['卡芙卡', '卡芙卡'], 50, 6)
    assert levelup_refresh_saving(st6, s6, _REG) == 0.0


# --- ⑧ 概率窗二分([3]/通道表冲突消解)----------------------------------------


def test_roll_window_dichotomy() -> None:
    """⑧升 vs D 的概率窗二分(判据=level_plan roll 窗单一源):
    DOT队 L5(plan 说 level_up)→ vd 返回 None(D 让位给升,
    「没到就少刷新、多买经验」);L8(plan 说 roll 卡芙卡 2★)
    → V_D 生效且该帧正分。"""
    st5, s5 = _state(5, ['卡芙卡', '卡芙卡'], 60, 5)
    assert vd_refresh_score(st5, s5, _REG) is None, '窗外 D 必须让位'
    st8, s8 = _state(8, ['卡芙卡', '卡芙卡'], 60, 8)
    vd8 = vd_refresh_score(st8, s8, _REG)
    assert vd8 is not None and vd8 > 0, vd8


# --- ③ c=2@L4 型格子(k=1)升级判负(P5 边界 a)-------------------------------


def test_c2_l4_k1_levelup_negative() -> None:
    """③P5 边界 a:c2@L4 找 1 张(k=1),金 51 的升级(单击 4)
    被平台总账拒——省刷金(k 放大后 6.25 金)仍远小于平台延迟损
    (花后 47<50:满息缺口 1×R=24)。「概率提高」本身不构成升级理由。"""
    st, s = _state(4, ['卡芙卡', '卡芙卡'], 51, 4)
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    res = arbitrate([(cand, 1.0, {})], st, s, _REG)
    row = next(r for r in res.log if r['tag'] == 'levelup')
    assert row['accepted'] is False, row
    assert '息引擎总账拒' in (row['reject'] or ''), row
    assert not any(isinstance(a, LevelUp) for a in res.actions)


# --- ④ 34 帧误拒形态复现 → 修复后放行 ----------------------------------------


def test_pop_slot_affordable_below_form_floor_allowed() -> None:
    """④W123 34 帧误拒形态:cap 满+bench 目标件+整组升级花费花后
    <form_floor(金 23,5 击×4=20,花后 3)——W126 修复前被 arm① 的
    form_floor 保险丝拦;修复后放行(人口位价值=当轮战力兑现,
    保险丝=可负担性)。对照:金不足(15<20)仍拒(可负担性入口门)。"""
    st, s = _state(5, ['希儿'], 23, 5, deployed=5)
    assert st.deployed_count() >= st.max_units(), '前置:cap 满(ADR-0392 占用数)'
    targets = _target_names(st, s)
    assert '希儿' in targets, '前置:bench 目标件'
    assert levelup_ev_authorized(st, s, _REG, 23, 20, targets,
                                 val=1.0, int_emb=0.0) is True
    # 金不足对照:整组总价超本金 → 拒(可负担性入口门,W126)
    assert levelup_ev_authorized(st, s, _REG, 15, 20, targets,
                                 val=1.0, int_emb=0.0) is False
    # 无人口位对照:deployed<cap 同帧 → arm① 不辖
    st2, s2 = _state(5, ['希儿'], 23, 5, deployed=4)
    assert st2.deployed_count() < st2.max_units()   # ADR-0392 占用数
    assert levelup_ev_authorized(st2, s2, _REG, 23, 20,
                                 _target_names(st2, s2),
                                 val=1.0, int_emb=0.0) is False
    # 单击路径端到端:gold_floor 让位后由 ev 单一裁决(同帧单击 4 也放行)
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    res = arbitrate([(cand, 1.0, {})], st, s, _REG)
    assert any(isinstance(a, LevelUp) for a in res.actions), \
        'cap 满+bench 目标件的可负担单击升级应放行(34 帧修复)'


# --- ⑤ 追赶态退场静态断言 -----------------------------------------------------


def test_catchup_retired_static() -> None:
    """⑤追赶态(F6)退场:registry 无追赶字段、过滤链无 catchup 层、
    filters/discipline 无 is_catchup、覆盖序不产 'catchup'
    (人口落后由通道 2/4+EV 涌现承接,ADR-0349)。"""
    for field in ('catchup_tags', 'catchup_forbidden_tags',
                  'catchup_min_level', 'pop_baseline'):
        assert not hasattr(_REG, field), field
    assert 'catchup' not in _REG.filter_chain_order
    assert 'catchup' not in _REG.audit_round_state_dims
    from sr_od.application.currency_war.decision_v2 import (
        filters as _f,
        discipline as _d,
        arbiter as _a,
    )
    for mod in (_f, _d, _a):
        assert not hasattr(mod, 'is_catchup'), mod.__name__
    # 行为面:旧追赶触发帧(等级≥6+人口<基线-1,r232 形态)不再产
    # catchup 覆盖——回落 mode(经济),refresh 候选不被追赶禁
    s = _locked_sess('DOT队')
    s.v3_mode = 'economy'
    st = GameState(plane=2, round_num=3, gold=40, level=6, hp=70,
                   deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                                       faction='公司', star=1)
                             for i in range(2)],
                   bench=[], shop=[], node_type='battle')
    disc = _d.assess_discipline(st, s, _REG)
    assert disc.coverage == 'mode', disc
    cands = generate_candidates(st, s, _REG)
    kept, _flog = filter_candidates(cands, st, s, _REG)
    assert any(c.tag == 'refresh' for c in kept), \
        '旧追赶帧 refresh 不再被禁(追赶态退场)'


# --- ⑥ war 模式帧 refresh 候选在场 --------------------------------------------


def test_war_mode_refresh_candidate_present() -> None:
    """⑥war 滤 refresh 废除:war 模式帧(报警升级/boss_breaker 覆盖)
    refresh 候选层2 在场(war_tags 含 refresh)——D 是一等花钱通道,
    授权由 V_D+interest_rule 辖,不再按模式整体消失(run10 病症的
    通道层根治)。"""
    assert 'refresh' in _REG.war_tags
    s = _locked_sess('DOT队')
    s.v3_mode = 'war'
    st, _s = _state(8, ['卡芙卡', '卡芙卡'], 60, 8)
    cands = generate_candidates(st, s, _REG)
    kept, flog = filter_candidates(cands, st, s, _REG)
    assert any(c.tag == 'refresh' for c in kept), \
        'war 模式帧 refresh 候选必须在场'
    # 评分不受 war 模式影响(V_D 同账;授权由层4 辖)
    rc = next(c for c in cands if c.tag == 'refresh')
    val, _bd = score_candidate(rc, st, s, _REG)
    assert val > 0, f'概率窗内 V_D 应正分(实际 {val})'
    # 端到端:war 帧 refresh 被采纳
    res = arbitrate([(rc, val, _bd)], st, s, _REG)
    assert any(isinstance(a, RefreshShop) for a in res.actions)


# --- ⑩ 伴随修复:CompTransaction shop fill 索引漂移(B 批 sim 涌现)--------


def test_comp_tx_shop_fill_index_drift_fixed() -> None:
    """⑩W126 sim ledger_consistency 2→12/100 涌现的根:CompTransaction
    多笔 shop fill 的 apply 循环内 ``s.shop.remove`` 左移列表,后续
    f.idx 失效——买错卡(错档部署)+记错账(实扣 6 记 4)。修复=按
    校验期解析的卡对象(``plan['shop_fill_cards']``)按身份消费。
    锁:两笔 shop fill([1]=2费,[2]=2费)后金恰扣 4、上场的是提案的
    两张(非移位后的遐蝶 4费)、店内只剩未提案的。"""
    from sr_od.application.currency_war.cw_state import (
        CompTransaction,
        FillSpec,
        ShopCard,
        simulate,
    )
    st = GameState(plane=1, round_num=5, gold=30, level=4, hp=60,
                   shop=[ShopCard(name='卡零', faction='公司', cost=1, x=0),
                         ShopCard(name='砂金', faction='公司', cost=2, x=1),
                         ShopCard(name='佩拉', faction='贝洛伯格', cost=2, x=2),
                         ShopCard(name='遐蝶', faction='夜之半神', cost=4, x=3)],
                   bench=[], deployed=[], node_type='battle')
    tx = CompTransaction(deploy=[], undeploy=[], sell=[],
                         fill=[FillSpec(source='shop', idx=1, row='back'),
                               FillSpec(source='shop', idx=2, row='back')],
                         reason='test:drift')
    out = simulate(st, tx)
    log = out.action_log[-1]
    assert log['result'] == 'applied', log
    assert log['fill_cost'] == 4, log
    assert st.gold - out.gold == 4, (st.gold, out.gold)
    dep_names = {d.char_id for d in out.deployed if d is not None}
    assert dep_names == {'砂金', '佩拉'}, dep_names   # ADR-0392 滤 None
    shop_names = [c.name for c in out.shop]
    assert shop_names == ['卡零', '遐蝶'], shop_names
