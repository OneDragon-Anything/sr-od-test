"""W242/ADR-0405:末窗星级定向授权(C 项)单帧锁。

**语义演进(ADR-0411 flag 家族清理)**:C 项授权自 W257 起无条件启用
——历史 handoff_star_directed(及 gate/proj 正交 flag)布尔删除,原
「默认关零漂移/仅 C 开正交臂/off 臂整局一致」锁面随 flag 退场
(docstring 记过期原因);gap 判据经薄封装 ``star_directed_gap``(
flag 检查 + gate_gap)并入 ``handoff_gate_gap`` 本体。历史四臂 A/B
数字见 ADR-0405/0411。

锁面:
- 授权点:candidates 层(r410 守卫+方向门)只放行候选生成,不是授权
  (copies_cap/r408 同轮守卫/bench 容量照常辖);arbiter 非正分门放行
  'copy' 标签买候选进约束链——授权值零新增(EV 由 interest_rule 的
  W227 缺口项独担,防双计);
- 窗口:gap>0 只在 P1 末窗(r>=8)∧ P1(非末窗/P2 恒 0);
- 定向性:只辖 'copy' 标签(其它零分候选照拒);r408 同轮已卖仍拒。
n 取断言成立最小值。
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import (
    _check_constraint,
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import (
    Candidate,
    _buy_tag,
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.handoff import (
    handoff_gate_gap,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

logging.disable(logging.CRITICAL)

#: ADR-0411:C 项授权无条件启用——行为臂即 DEFAULT_REGISTRY
_REG = DEFAULT_REGISTRY

_CARRY = '姬子·启行'
_FILLER = '娜塔莎'
_FAC = '贝洛伯格'


def _bench(name: str, faction: str, slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _deployed(name: str, faction: str, star: int = 1,
              slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=star,
                           position_pref='back', equips=(), slot=slot)


def _sess() -> StrategySession:
    from sr_od.application.currency_war.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {_CARRY}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=(_CARRY,))
    return s


def _state(**kw) -> GameState:
    """末窗承接缺口帧:P1 r8,hp 临界(boss 投影后 hp_tier=0)+板面
    tier0(全 1★ → core2=0)→ gap=1(C 项目标场景:星级深度主罚维)。"""
    base = {'plane': 1, 'round_num': 8, 'gold': 55, 'level': 5,
            'hp': 20,
            'board': {'列车同行': 2, _FAC: 1},
            'deployed': [_deployed(_CARRY, '列车同行'),
                         _deployed(_FILLER, _FAC)],
            'bench': [], 'shop': [], 'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


# ---------- ① 授权点:candidates 层放行生成(非授权) ----------


def test_copy_candidate_generated_in_final_window() -> None:
    """末窗 gap≥1 时方向外 deployed 填充件同名卡生成 'copy' 候选
    (r410 守卫+方向门双豁免)。

    语义演进(ADR-0451 血预算停手·第二波):授权帧改 hp=90(带外,
    ≥p1_exit_blood_target;board 维 tier0 主罚 gap≥1 前置不变)——
    原 hp=20 帧已入末窗血预算不足带,降格面停定向 'copy' 生成臂
    (反例见同文件 test_copy_arm_downgraded_in_blood_band)。"""
    sess = _sess()
    st = _state(hp=90,
                shop=[ShopCard(x=1, faction=_FAC, name=_FILLER, cost=3)])
    assert handoff_gate_gap(st, sess, _REG) >= 1   # 前置:缺口成立
    got = generate_candidates(st, sess, _REG)
    names = [c.action.card.name for c in got if isinstance(c.action,
                                                           BuyCard)]
    assert _FILLER in names
    tag = _buy_tag(st.shop[0], st, sess, _REG)
    assert tag == 'copy'


def test_copy_arm_downgraded_in_blood_band() -> None:
    """ADR-0451 反例锁:同构造 hp=20(末窗血预算不足带)定向 'copy'
    臂降格不生成——血预算不足帧行为(战力投资搜索 → 减损保血)。"""
    sess = _sess()
    st = _state(shop=[ShopCard(x=1, faction=_FAC, name=_FILLER, cost=3)])
    assert handoff_gate_gap(st, sess, _REG) >= 1   # 前置:缺口仍在
    assert _buy_tag(st.shop[0], st, sess, _REG) != 'copy'


def test_copies_cap_and_r408_still_govern() -> None:
    """约束照常辖:星级加权 ≥3 份不生成;r408 同轮已卖名不生成
    (豁免只跳过 r410+方向门,纪律守卫不豁免)。"""
    sess = _sess()
    # copies_cap:deployed 1 + bench 2 = 加权 3 → 第 4 份拒
    st = _state(
        bench=[_bench(_FILLER, _FAC, slot=0),
               _bench(_FILLER, _FAC, slot=1)],
        shop=[ShopCard(x=1, faction=_FAC, name=_FILLER, cost=3)])
    names = [c.action.card.name for c in generate_candidates(st, sess, _REG)
             if isinstance(c.action, BuyCard)]
    assert _FILLER not in names
    # r408 同轮已卖:session 簿记已卖名 → 不生成
    st2 = _state(shop=[ShopCard(x=1, faction=_FAC, name=_FILLER, cost=3)])
    s2 = _sess()
    s2.v2_round_key = (1, 8)
    s2.v2_round_sold = {_FILLER}
    assert _buy_tag(st2.shop[0], st2, s2, _REG) is None


# ---------- ② arbiter 非正分门:定向放行 + 防双计 ----------


def _copy_cand(st: GameState, cost: int = 3) -> Candidate:
    return Candidate(action=BuyCard(
        ShopCard(x=1, faction=_FAC, name=_FILLER, cost=cost), reason=''),
        tag='copy', source='shop')


def test_arbiter_nonpositive_gate_directed_pass() -> None:
    """主通道:末窗 gap≥1 时零分 'copy' 买候选进约束链而非「非正分」
    拒(放行≠必买:金不足/容量约束仍拒);非末窗照拒;非 'copy'
    标签零分候选照拒(定向性)。

    语义演进(ADR-0451):授权帧改 hp=90 带外——血预算不足帧的非正分
    'copy' 豁免同步降格(见 test_copy_arm_downgraded_in_blood_band)。"""
    st = _state(gold=55, hp=90)
    sess = _sess()
    res = arbitrate([(_copy_cand(st), 0.0, {'cost': 3})], st, sess, _REG)
    row = res.log[0]
    assert row['accepted'] is True, f'末窗 gap 授权应放行(log={row})'
    assert any(isinstance(a, BuyCard) for a in res.actions)
    # 同帧 r5(非末窗,W288/ADR-0418 前移后边界):gap=0 → 非正分照拒
    st5 = _state(round_num=5)
    res7 = arbitrate([(_copy_cand(st5), 0.0, {'cost': 3})], st5, sess,
                     _REG)
    assert res7.log[0]['reject'] == '非正分'
    # 定向性:非 copy 标签的零分候选照拒(如 line_opportunistic)
    res_other = arbitrate(
        [(Candidate(action=BuyCard(
            ShopCard(x=1, faction='列车同行', name='三月七', cost=3),
            reason=''), tag='line_opportunistic', source='shop'),
          0.0, {'cost': 3})], st, sess, _REG)
    assert res_other.log[0]['reject'] == '非正分'


def test_arbiter_constraint_chain_still_rejects() -> None:
    """放行只跳过非正分门,不豁免约束链:金不足以付地板 → gold_floor
    拒(零分候选不进 EV 账时地板族照辖;放行≠必买)。"""
    st = _state(gold=8)   # boss 前低金:经济地板 50 远超
    sess = _sess()
    res = arbitrate([(_copy_cand(st, cost=3), 0.0, {'cost': 3})], st,
                    sess, _REG)
    assert res.log[0]['accepted'] is False
    assert not any(isinstance(a, BuyCard) for a in res.actions)


def test_ev_gap_bonus_single_source_no_double_count() -> None:
    """防双计:EV 授权值单一源 = interest_rule 的 W227 缺口项
    (handoff_ev_gap_bonus×gap);C 授权路径不加第二份授权值——r8
    (boss 窗外)跨档买经缺口项放行(auth 带 handoff_gap);
    registry 无 C 项专有数值常量(no star_directed_* bonus 字段)。

    语义演进(ADR-0451):授权帧改 hp=70 带外——hp<60 末窗帧缺口项
    降格不加成(血预算停手·P1-a),反例:hp=30 帧同构造被拒。"""
    st = _state(gold=53, hp=70)   # 带外:投影后 hp_tier=2,board 维 tier0
    sess = _sess()
    cand = _copy_cand(st, cost=4)
    auth: dict = {}
    r = _check_constraint('interest_rule', cand, st, st, sess, _REG,
                          val=1.0, bd={'int_emb': 0.0}, auth=auth)
    # r8 node_type=battle → interest_rule 辖:缺口项 V+5×1 → 放行
    assert r is None
    assert auth.get('handoff_gap') == 1
    assert auth.get('ev_auth', 0) > 0
    # ADR-0451 反例:hp=30(末窗血预算不足带)缺口项不加成 → EV≤0 拒
    st_band = _state(gold=53, hp=30)
    r_band = _check_constraint('interest_rule', _copy_cand(st_band, cost=4),
                               st_band, st_band, sess, _REG,
                               val=1.0, bd={'int_emb': 0.0})
    assert r_band is not None
    # 数值单一源:registry 无 C 项专有 bonus 常量
    assert not [f for f in type(DEFAULT_REGISTRY).__dataclass_fields__
                if f.startswith('handoff_star')]


# ---------- ③ 窗口辖域 ----------


def test_gap_window_scope() -> None:
    """缺口窗口辖域:P1 末窗(r>=6,W288/ADR-0418 前移)才 >0;
    非末窗/P2/达标帧恒 0。"""
    sess = _sess()
    st = _state()
    assert handoff_gate_gap(st, sess, _REG) >= 1
    # 新窗内(r7):照辖(窗加宽语义)
    assert handoff_gate_gap(_state(round_num=7), sess, _REG) >= 0
    assert handoff_gate_gap(_state(round_num=5), sess, _REG) == 0
    assert handoff_gate_gap(_state(plane=2), sess, _REG) == 0
    # 达标帧(W227 锁同式 DOT 队成型帧,hp 高带):gap=0 → C 授权随之关
    # (授权强度单一源随 gap 走,gap=0 即零行为)
    from sr_od.application.currency_war.cw_comps import get_comp
    from sr_od.application.currency_war.cw_intention import (
        IntentionState,
        intention_core,
    )
    comp = get_comp('DOT队')
    core = intention_core(comp)
    st_ok = GameState(
        plane=1, round_num=8, gold=55, level=5, hp=90,
        board=dict(comp.form_tiers),
        deployed=[BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                            star=2),
                  BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮',
                            star=1)],
        bench=[], shop=[], node_type='battle')
    s_ok = StrategySession()
    s_ok.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    s_ok.v3_mode = 'economy'
    assert handoff_gate_gap(st_ok, s_ok, _REG) == 0
