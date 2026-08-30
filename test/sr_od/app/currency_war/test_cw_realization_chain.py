"""W802 · 锁线后兑现链 v2 单帧锁组(PREREG 兑现链A_B v3 §5 十一锁)。

设计出处:.debug/temp/currency_war/w795_realization_design/REPORT.md v2/v3
(五侧机制)+ 同目录 PREREG_兑现链A_B.md v3 §5(锁清单事前写死)+
W796/W796v2 复核修正清单;D1/D2 锚 = W797 局 6 p2r7/P3r1 帧证据。

锁语义不锁牌面:成员名/羁绊键从注册表数据现场派生(断言策略决策行为,
不锁具体卡名)。开关组 realization_chain_*(伞+七子旗标)默认关 = 第 1
态零漂移锚,每锁带 off 臂对照断言(策略开关生命周期第 3 态盘点义务:
开臂翻默认时按本锁组的 off 臂清单重推语义)。

观测依赖边界声明:锁 #10(席满对账)/锁 #11(分配器接管)的行为半边
依赖 board_next_tier/bench_full_flag/ADR-0474 遥测键(W793 后继批,
只登记依赖不实现观测键)——本锁组只锁机制函数与辖域判定本体。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.allocator import (
    AllocDomain,
    alloc_domain,
)
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    sell_priority_key,
)
from sr_od.application.currency_war.decision.decision_v2.realization import (
    d2_entry_frame,
    merge_timing_term,
    missing_members,
    p29_priority_term,
    refresh_search_term,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    _pair_hysteresis,
    _supply_prime,
    _update_supply_decay,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)


def _flags_on(**kw) -> object:
    base = {
        'realization_chain_enabled': True,
        'realization_search_enabled': True,
        'realization_buy_enabled': True,
        'realization_merge_timing_enabled': True,
        'realization_deploy_enabled': True,
        'realization_direction_enabled': True,
        'realization_d1_enabled': True,
        'realization_d2_enabled': True,
    }
    base.update(kw)
    return dataclasses.replace(DEFAULT_REGISTRY, **base)


_REG_ON = _flags_on()
_REG_OFF = DEFAULT_REGISTRY

_CORE = '姬子·启行'   # 列车同行 3 费成员(锁线骨架;断言走语义不锁牌面)


def _dot_1cost_names() -> list[str]:
    """线外对照组:1 费持续伤害成员(注册表派生,非牌面锁定)。"""
    return sorted(n for n, c in CHARACTERS.items()
                  if c.cost == 1 and '持续伤害' in (c.factions + c.flows))


def _sess(locked: bool = True) -> StrategySession:
    s = StrategySession()
    ist = IntentionState()
    if locked:
        ist.phase = 'locked'
        ist.locked_comp = '列车同行'
    s.v3_intention = ist
    return s


def _st(**kw) -> GameState:
    base = {'plane': 2, 'round_num': 3, 'node_type': '战斗', 'gold': 60,
            'hp': 80, 'hp_readable': True, 'level': 7, 'streak': None,
            'board': {}, 'bench': [], 'shop': [], 'deployed': []}
    base.update(kw)
    return GameState(**base)


# ===== 锁 0(开关组缺省态)=====

def test_lock0_switch_group_defaults_off() -> None:
    """伞+七子旗标默认全关(生命周期第 1 态:默认关+零漂移锚)。"""
    for f in ('realization_chain_enabled', 'realization_search_enabled',
              'realization_buy_enabled', 'realization_merge_timing_enabled',
              'realization_deploy_enabled', 'realization_direction_enabled',
              'realization_d1_enabled', 'realization_d2_enabled'):
        assert getattr(DEFAULT_REGISTRY, f) is False


# ===== 锁 1(v2 重写)merge 完成豁免通道回归 =====

def test_lock1_merge_exempt_channel_unchanged() -> None:
    """豁免通道现行态回归(ADR-0437/0438):线内单位已持 2 份 1★、
    商店再现同卡 → merge 买候选不被非正分门拒;且不受兑现链开关态
    影响(豁免与本设计排序项作用面不相交,防双计声明的锁面)。"""
    bench = [BenchChar(slot=0, char_id=_CORE, star=1, faction='列车同行'),
             BenchChar(slot=1, char_id=_CORE, star=1, faction='列车同行')]
    st = _st(board={'列车同行': 1}, bench=bench)
    cand = Candidate(action=BuyCard(ShopCard(x=0, name=_CORE, cost=3)),
                     tag='copy', source='test', merge=True)
    for reg in (_REG_OFF, _REG_ON):
        res = arbitrate([(cand, 0.0, {})], st, _sess(), reg)
        assert [type(a).__name__ for a in res.actions] == ['BuyCard']


# ===== 锁 2(v2 重写)档位未满守卫 + 星级守卫 =====

def test_lock2_merge_timing_guards() -> None:
    """时点项守卫:①已满档贡献成员的第 3 份不获显影(档位未满守卫,
    与搜牌缺件判据同一单一源);②合成产物与 deployed 同名不可上场
    (混合星级态产物不可部署 → 零时点价值)。"""
    sess = _sess()

    def _merge_cand() -> Candidate:
        return Candidate(action=BuyCard(ShopCard(x=0, name=_CORE, cost=3)),
                         tag='copy', source='test', merge=True)

    # ① 满档:列车同行 cur=4,tiers (2,4,6) 的下一档 5 不存在 → 非缺件
    st_full = _st(board={'列车同行': 4})
    assert merge_timing_term(_merge_cand(), st_full, sess, _REG_ON) == 0.0
    # ② deployed 同名(1×2★ 已在场 + bench 2×1★ 的混合星级态)
    deployed = [BenchChar(slot=0, char_id=_CORE, star=2, faction='列车同行')]
    st_mixed = _st(board={'列车同行': 1}, deployed=deployed)
    assert merge_timing_term(_merge_cand(), st_mixed, sess, _REG_ON) == 0.0
    # 对照:未满档 ∧ 无同名在场 → 时点项显影
    st_open = _st(board={'列车同行': 1})
    assert merge_timing_term(_merge_cand(), st_open, sess, _REG_ON) > 0.0
    # off 臂恒 0(零漂移)
    assert merge_timing_term(_merge_cand(), st_open, sess, _REG_OFF) == 0.0


# ===== 锁 3 比例折扣制 =====

def test_lock3_off_lock_proportional_discount() -> None:
    """锁线帧线外正增量候选:off-lock 罚分改比例折扣——折扣臂分值
    高于常数罚分臂(不被一票罚负的语义),且两臂差=常数−κ·raw 的
    恒等式(off=raw−3.0 / on=raw·(1−κ),raw>0 时)。"""
    name = _dot_1cost_names()[0]
    st = _st(board={'持续伤害': 1}, gold=55)
    cand = Candidate(action=BuyCard(ShopCard(x=0, name=name, cost=1)),
                     tag='bond_fallback', source='test')
    off, _ = score_candidate(cand, st, _sess(), _REG_OFF)
    on, _ = score_candidate(cand, st, _sess(), _REG_ON)
    raw = off + _REG_ON.off_lock_buy_penalty   # 未罚分原始增量
    assert raw > 0   # 线外正增量候选(折扣制语义的前件)
    assert on > off   # 折扣 < 常数罚 3.0:降级非禁绝重新成立
    assert on == pytest.approx(
        raw * (1.0 - _REG_ON.realization_off_lock_kappa))
    # off 臂(开关关)与 HEAD 常数罚逐位一致
    off2, _ = score_candidate(cand, st, _sess(),
                              dataclasses.replace(_REG_ON,
                                                  realization_buy_enabled=False))
    assert off2 == pytest.approx(off)


# ===== 锁 4 P29 辖域门(含反向锁)=====

def test_lock4_p29_priority_and_reverse_gate() -> None:
    """hp ≥ 报警线帧:线内缺档成员买分 > 线外插件(档位进度项);
    反向锁:hp < 报警线帧囤牌优先级不启用(事前辖域门生效)。"""
    sess = _sess()
    st = _st(board={'列车同行': 1}, hp=80)
    assert _CORE in missing_members(st, sess, _REG_ON)
    missing_members(st, sess, _REG_ON)
    ch = CHARACTERS[_CORE]
    line_cand = Candidate(action=BuyCard(ShopCard(x=0, name=_CORE,
                                                  cost=ch.cost)),
                          tag='line_opportunistic', source='test')
    plug = _dot_1cost_names()[0]
    plug_cand = Candidate(action=BuyCard(ShopCard(x=0, name=plug, cost=1)),
                          tag='bond_fallback', source='test')
    v_line, bd = score_candidate(line_cand, st, sess, _REG_ON)
    v_plug, _ = score_candidate(plug_cand, st, sess, _REG_ON)
    assert bd.get('rc_p29', 0.0) > 0.0   # 优先级项显影
    assert v_line - bd['rc_p29'] >= v_plug   # 去项后不劣于插件(同增量语境)
    # 反向锁:hp 跌破报警线 ∧ 剩余战斗轮 < R_min → 项归零(辖域门生效)
    st_low = _st(board={'列车同行': 1}, hp=30, round_num=1)
    sess_short = _sess()
    sess_short.plane_node_table = ['战斗']   # r_rest=1 < R_min=5
    assert p29_priority_term(line_cand, st_low, sess_short, _REG_ON) == 0.0
    assert missing_members(st_low, sess_short, _REG_ON)[_CORE] > 0  # 缺件仍在,门在辖


# ===== 锁 5/6/7 方向侧 support′ =====

def test_lock5_supply_prime_strict_decay() -> None:
    """某体系连续零在店 → support′ 严格递减(γ 衰减;开关关原样)。"""
    sup = {'列车同行': 1.0}
    prev = _supply_prime(sup, {'列车同行': 0}, _REG_ON)
    for t in range(1, 6):
        cur = _supply_prime(sup, {'列车同行': t}, _REG_ON)
        assert cur['列车同行'] < prev['列车同行']
        prev = cur
    # 开关关:原样返回(零漂移)
    assert _supply_prime(sup, {'列车同行': 4}, _REG_OFF) == sup


def test_lock6_supply_prime_bounded_jump() -> None:
    """窗口内成员在店 → support′ 上跳有界(=β·1;不叠加)。"""
    sup = {'列车同行': 1.0}
    hit = _supply_prime(sup, {'列车同行': 0}, _REG_ON)
    assert hit['列车同行'] == pytest.approx(
        1.0 + _REG_ON.realization_direction_beta)


def test_lock7_pair_hysteresis_p16() -> None:
    """support′ 差 < 滞回带 δ(P16 line_switch_theta 单一源)→ 不切换;
    差 ≥ δ → 按新序切换。"""
    sup = {'甲': 1.0, '乙': 1.05, '丙': 1.5}
    ranked = ['丙', '乙', '甲']
    prev = ('乙',)
    kept = _pair_hysteresis(prev, ranked, sup, _REG_ON)
    assert kept[0] == '乙'          # 差 0.45 < θ=1.0:粘住
    sup2 = {'甲': 1.0, '乙': 1.0, '丙': 3.0}
    switched = _pair_hysteresis(prev, ['丙', '乙', '甲'], sup2, _REG_ON)
    assert switched[0] == '丙'      # 差超带:切换
    assert _pair_hysteresis(prev, ranked, sup, _REG_OFF) == ranked  # off 原样


def test_lock7b_supply_decay_counter_update() -> None:
    """衰减计数器每轮刷新:成员在店清零、零在店递增;开关关不动。"""
    sess = _sess()
    ist = sess.v3_intention
    shop_name = _dot_1cost_names()[0]
    st = _st(shop=[ShopCard(x=0, name=shop_name, cost=1)])
    _update_supply_decay(st, ist, _REG_ON)
    assert ist.supply_drought['持续伤害'] == 0
    st2 = _st(shop=[])
    _update_supply_decay(st2, ist, _REG_ON)
    assert ist.supply_drought['持续伤害'] == 1
    ist2 = IntentionState()
    _update_supply_decay(st2, ist2, _REG_OFF)
    assert ist2.supply_drought == {}   # 开关关零漂移


# ===== 锁 8 金水位辖域门 =====

def test_lock8_refresh_water_level_gate() -> None:
    """金 ≤ 息线+刷价帧 → 定向刷新加项不生成;金充裕 ∧ 3-4 费缺件 →
    加项含 Δp_tier·P(本刷出缺件);满档帧(饱和)无缺件 → 零。"""
    sess = _sess()
    st = _st(board={'列车同行': 1}, gold=60)
    term = refresh_search_term(st, sess, _REG_ON)
    assert term > 0.0
    st_poor = _st(board={'列车同行': 1}, gold=45)
    assert refresh_search_term(st_poor, sess, _REG_ON) == 0.0   # 水位门
    st_full = _st(board={'列车同行': 4}, gold=60)
    assert refresh_search_term(st_full, sess, _REG_ON) == 0.0   # 满档饱和
    assert refresh_search_term(st, sess, _REG_OFF) == 0.0   # off 臂零漂移


# ===== 锁 9 部署显影 =====

def test_lock9_line2star_deploy_showcase() -> None:
    """bench 2★ 线内件、cap 未满 → deploy 候选集必含该件;off 臂
    (开关关)被围栏序 top-K 截断(病灶复现)。"""
    sess = _sess()
    dot = _dot_1cost_names()
    bench: list[BenchChar | None] = [
        BenchChar(slot=i, char_id=n, star=1, faction='持续伤害')
        for i, n in enumerate(dot[:3])]
    bench.append(BenchChar(slot=0, char_id=_CORE, star=2, faction='列车同行'))
    bench += [None] * 5
    st = _st(board={'持续伤害': 1}, bench=bench)
    cands_on = generate_candidates(st, sess, _REG_ON)
    dep_on = [c for c in cands_on if c.tag == 'deploy']
    assert any(c.breakdown_hint.get('name') == _CORE for c in dep_on)
    cands_off = generate_candidates(st, sess, _REG_OFF)
    dep_off = [c for c in cands_off if c.tag == 'deploy']
    assert not any(c.breakdown_hint.get('name') == _CORE for c in dep_off)


# ===== 锁 10 D1 腾席弱序 income 入键 =====

def test_lock10_eviction_weakest_by_income() -> None:
    """席满腾席:弱序键补 income 分量后,同 redundancy 档内低回金件
    先卖(含装备 1★ 后于裸 1★);off 臂键结构逐位旧行为。"""
    sess = _sess()
    dot = _dot_1cost_names()
    bc_plain = BenchChar(slot=0, char_id=dot[0], star=1,
                         faction='持续伤害')
    bc_equip = BenchChar(slot=1, char_id=dot[1], star=1,
                         faction='持续伤害', equips=['火力风暴潮'])
    st = _st(board={'持续伤害': 2},
             bench=[bc_plain, bc_equip,
                    BenchChar(slot=2, char_id=dot[2], star=1,
                              faction='持续伤害')] + [None] * 6)
    key_off_p = sell_priority_key(bc_plain, st, sess, set(), _REG_OFF)
    key_off_e = sell_priority_key(bc_equip, st, sess, set(), _REG_OFF)
    assert key_off_p == key_off_e          # off 臂:装备残值不入键(旧行为)
    key_on_p = sell_priority_key(bc_plain, st, sess, set(), _REG_ON)
    key_on_e = sell_priority_key(bc_equip, st, sess, set(), _REG_ON)
    assert key_on_p is not None and key_on_e is not None
    assert key_on_p < key_on_e             # 裸件更弱 → 先卖
    assert len(key_on_p) == len(key_off_p) + 1   # 仅追加 income 分量
    # (腾席消费面统一性:carry_gate/补偿器/arbiter 卖通道全走本键;
    #  腾席链 c 的 _bench_sell_value 旧键归 strategy/03 语义,不在本锁面。)


# ===== 锁 11 D2 入口帧转化授权 =====

def test_lock11_d2_entry_frame_authorization() -> None:
    """跨位面入口帧 hp 落死亡带 ∧ 携金>息线 → 并入分配器 DEATH 域
    (授权发生+分配器接管两事实;分配正确性归 ADR-0474 既有锁组);
    开关关:同帧不接管(out_of_scope,零漂移)。"""
    st = _st(plane=3, round_num=1, hp=1, gold=92)
    sess = _sess()
    assert d2_entry_frame(st, _REG_ON)
    assert alloc_domain(st, sess, _REG_ON) is AllocDomain.DEATH
    # 非入口帧 / 携金低于息线 / hp 不在死亡带 → 不辖
    assert not d2_entry_frame(_st(plane=3, round_num=4, hp=1, gold=92),
                              _REG_ON)
    assert not d2_entry_frame(_st(plane=3, round_num=1, hp=1, gold=30),
                              _REG_ON)
    assert not d2_entry_frame(_st(plane=3, round_num=1, hp=80, gold=92),
                              _REG_ON)
    # off 臂:同帧不接管(HEAD 行为)
    assert alloc_domain(st, sess, _REG_OFF) is None
