"""C1 溢余必花定向优先级单帧锁(P1 末窗投影安全带;FLIP 正交补集)。

设计=唯一规格:`.debug/temp/currency_war/w382_c1_design/DESIGN.md`
§2(期望账)/§3(路线 B 辖域裁决)。辖域=P1 末窗 ∧ d=hp−boss_tax_p75
≥ emergency_hp(C1 自身辖域;原「与 FLIP 投影臂互斥」已随 ADR-0426
增补 D 溢余化退场,FLIP 不再按 d 切分)∧ 溢余段 g>interest_floor。
锁的是策略决策行为(单帧锁=回归工具):

- 定向优先级锁(registry.c1_directed_spend_enabled,默认关=零漂移):
  C1 帧内零 boss 增量支出删(纯 hoard 买/盲刷/升完无件可上的 LevelUp),
  可部署买/3合1 合成且合成后可上买(完备式,与濒死带同款)/定向刷新放行,
  卖/上阵不辖——溢余段花金
  零息损(成本恒 0),Δp≤0 支出确定性零收益,「必花+定向」的优先级
  语义=零贡献让位有增量;
- C1 d 门锁:hp=58/59 边界上 c1_directed_active 的 d 门语义不变;
  FLIP 同帧行为与 hp 无关(增补 D 溢余化,见 d 门锁 docstring);
- 零漂移锚:默认关时 C1 形帧的过滤行为逐位一致。
- (原 C1 资产臂锁节已随定谳清理删除:开臂前置触发面实测为零,通道
  构造性恒不激活,决策 why=ADR-0444。)
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_system_cards import engine_char_names
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.filters import (
    c1_directed_active,
    filter_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    flip_hit,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG_C1 = dataclasses.replace(DEFAULT_REGISTRY,
                              c1_directed_spend_enabled=True)


def _card(name: str, cost: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _unit(slot: int, name: str = '件', front: bool = True) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction='仙舟罗浮', star=1,
                     position_pref='front' if front else 'back')


def _c1_state(**kw) -> GameState:
    """C1 帧底座:P1 r9 boss 窗、hp=60(投影安全带 d=60−34=26≥25)、
    溢余 60 金、hp 真读。"""
    base = {
        'plane': 1, 'round_num': 9, 'gold': 60, 'level': 5,
        'hp': 60, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _boss_session() -> StrategySession:
    sess = StrategySession()
    sess.node_type_current = 'boss'   # 末窗统一口径主判据(节点图)
    return sess


def _target_name() -> str:
    """目标件名(裸 session 目标集=引擎件全集,单一源回退语义)。"""
    return sorted(engine_char_names())[0]


def _cands(target: str, merge: bool = False) -> list[Candidate]:
    """六类候选各一:目标件买/非目标件买/升级/刷新/卖/上阵。"""
    return [
        Candidate(action=BuyCard(_card(target), reason=''), tag='line_carry',
                  source='shop', merge=merge),
        Candidate(action=BuyCard(_card('散件甲'), reason=''), tag='plugin',
                  source='shop'),
        Candidate(action=LevelUp(cost=4), tag='levelup', source='xp'),
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
        Candidate(action=SellBench(bench_idx=0, income=1, expect=''),
                  tag='for_gold', source='bench'),
        Candidate(action=DeployMove(bench_idx=1, to_row='front',
                                    faction='仙舟罗浮'),
                  tag='deploy', source='fence'),
    ]


# --- 辖域正交锁:d 边界上 FLIP 与 C1 互斥不重叠 ------------------------------


def test_c1_d_boundary_after_flip_simplification() -> None:
    """d=hp−boss_tax_p75 判据一刀切(增补 D 后只辖 C1 自己的辖域):
    hp=58(d=24<25)C1 不评估;hp=59(d=25)C1 可评估——C1 的 d 门
    语义不变。FLIP 侧已随 ADR-0426 增补 D 溢余化(血量维度退场):同帧
    两 hp 行为逐位一致,不再按 d 与 C1 互斥(C1 是自身辖域自辖的独立
    通道,义务=溢余判定见 ADR-0445)。"""
    for hp in (58, 59):
        st = _c1_state(hp=hp)
        sess = _boss_session()
        assert flip_hit(st, sess, _REG_C1, 'FORM') is True   # 溢余帧,hp 无关
    st = _c1_state(hp=58)
    assert c1_directed_active(st, _boss_session(), _REG_C1) is False
    assert c1_directed_active(_c1_state(hp=59), _boss_session(),
                              _REG_C1) is True


def test_c1_scope_guards() -> None:
    """逐项守卫:hp 可信位缺(双 False=兜底帧)不评估;非 P1 不辖;
    无溢余(g≤50)不辖;非 boss 窗不辖。"""
    sess = _boss_session()
    assert not c1_directed_active(
        _c1_state(hp_readable=False, hp_trusted=False), sess, _REG_C1)
    assert c1_directed_active(
        _c1_state(hp_readable=False, hp_trusted=True), sess, _REG_C1), \
        'hp_trusted(沿用真值帧)放行(ADR-0428 可信位口径)'
    assert not c1_directed_active(_c1_state(plane=2, hp=80), sess, _REG_C1)
    assert not c1_directed_active(_c1_state(gold=50), sess, _REG_C1)
    assert c1_directed_active(
        _c1_state(round_num=9), StrategySession(), _REG_C1), \
        'node 缺读 r9 兜底也是 boss 窗统一口径的一部分,r9 帧仍辖'
    assert not c1_directed_active(
        _c1_state(round_num=5), StrategySession(), _REG_C1), \
        'node 缺读且 r<9:非 boss 窗不辖(轮数兜底不误扩)'


def test_c1_default_off() -> None:
    """默认关=零漂移锚:registry 缺省下 C1 判据恒 False。"""
    assert not c1_directed_active(_c1_state(), _boss_session(),
                                  DEFAULT_REGISTRY)


# --- 定向优先级锁:C1 帧内的零增量支出收窄 ------------------------------------


def _bench_full_state(**kw) -> GameState:
    """bench 满 9 槽 + 上阵 5(cap 内):无空位可上,买=纯 hoard。"""
    return _c1_state(deployed=[_unit(i, f'上{i}') for i in range(5)],
                     bench=[_unit(i, f'备{i}') for i in range(9)], **kw)


def test_c1_narrows_zero_delta_spend() -> None:
    """C1 帧 bench 满无空位:非合成买删(c1_hoard_buy——本轮不可能上场,
    对 boss 战胜率零增量)、店无可上件刷新删(c1_blind_refresh);升级
    保留(bench 有件、升完 cap+1 即可多上 1 件,Δp>0);卖/上阵不辖。"""
    tgt = _target_name()
    st = _bench_full_state()
    kept, flog = filter_candidates(_cands(tgt), st, _boss_session(), _REG_C1)
    tags = {c.tag for c in kept}
    assert 'levelup' in tags and 'for_gold' in tags and 'deploy' in tags
    assert 'line_carry' not in tags and 'plugin' not in tags
    assert 'refresh' not in tags
    drops = {e['tag']: e.get('c1_directed', '') for e in flog if not e['kept']}
    assert drops.get('line_carry') == 'c1_hoard_buy'
    assert drops.get('plugin') == 'c1_hoard_buy'
    assert drops.get('refresh') == 'c1_blind_refresh'


def test_c1_keeps_merge_and_directed_refresh() -> None:
    """3合1 合成买取完备式(合成后可上才豁免,与濒死带侧同款):板满+
    合成落 bench 无位可上仍删;板满+合成消场上同名同星 2 份净腾 1 位
    放行。有空位时买全放行;店有可买+上的名集件时定向刷新放行(存在性
    判据)。"""
    tgt = _target_name()
    st_room = _c1_state(shop=[_card(tgt)])
    kept, _ = filter_candidates(_cands(tgt), st_room, _boss_session(),
                                _REG_C1)
    tags = {c.tag for c in kept}
    # bench 空:升级无件可上(Δp=0)照删;有空位时两类买+定向刷新放行
    assert {'line_carry', 'plugin', 'refresh'} <= tags
    assert 'levelup' not in tags
    # 板满+合成落 bench 无位可上(板上无同名同星)→ 仍删(c1_hoard_buy)
    st_merge_bench = _bench_full_state()
    kept2, flog2 = filter_candidates(_cands(tgt, merge=True), st_merge_bench,
                                     _boss_session(), _REG_C1)
    assert not any(c.merge for c in kept2)
    drops = {e['tag']: e.get('c1_directed', '') for e in flog2
             if not e['kept']}
    assert drops.get('line_carry') == 'c1_hoard_buy'
    # 板满+合成消场上同名同星 2 份(载体落场上占 1 份,净腾 1 位)→ 放行
    st_merge_board = _c1_state(
        deployed=[_unit(i, f'上{i}') for i in range(3)]
        + [_unit(10, tgt), _unit(11, tgt)])
    kept3, _ = filter_candidates(_cands(tgt, merge=True), st_merge_board,
                                 _boss_session(), _REG_C1)
    assert any(c.merge and c.tag == 'line_carry' for c in kept3), \
        '合成候选在合成后可上帧放行(消场上份净腾上阵位)'


def test_c1_off_zero_drift() -> None:
    """零漂移锚:同一 C1 形帧开关关 → 六类候选全按既有行为放行,链日志
    无 c1_directed 原因(逐位一致)。"""
    tgt = _target_name()
    st = _bench_full_state(shop=[_card(tgt)])
    sess = _boss_session()
    kept_off, flog_off = filter_candidates(_cands(tgt), st, sess,
                                           DEFAULT_REGISTRY)
    assert {c.tag for c in _cands(tgt)} <= {c.tag for c in kept_off}
    assert not any(e.get('c1_directed') for e in flog_off)
