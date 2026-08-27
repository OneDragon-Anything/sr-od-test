"""C1 溢余必花定向优先级单帧锁(P1 末窗投影安全带;FLIP 正交补集)。

设计=唯一规格:`.debug/temp/currency_war/w382_c1_design/DESIGN.md`
§2(期望账)/§3(路线 B 辖域裁决)。辖域=P1 末窗 ∧ d=hp−boss_tax_p75
≥ emergency_hp(与 FLIP 末窗投影臂 d<emergency_hp 按 d 一刀切互斥)
∧ 溢余段 g>interest_floor。锁的是策略决策行为(单帧锁=回归工具):

- 定向优先级锁(registry.c1_directed_spend_enabled,默认关=零漂移):
  C1 帧内零 boss 增量支出删(纯 hoard 买/盲刷/升完无件可上的 LevelUp),
  可部署买/3合1 即时合成买/定向刷新放行,卖/上阵不辖——溢余段花金
  零息损(成本恒 0),Δp≤0 支出确定性零收益,「必花+定向」的优先级
  语义=零贡献让位有增量;
- 辖域正交锁:d 边界(hp=58/59)上 flip_hit(FLIP 末窗投影臂)与
  c1_directed_active 互斥不重叠(两谓词按同一 d 判据切分,合起来
  不重不漏覆盖末窗溢余帧);
- 零漂移锚:默认关时 C1 形帧的过滤行为逐位一致。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.cw_system_cards import engine_char_names
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.filters import (
    c1_directed_active,
    filter_candidates,
)
from sr_od.application.currency_war.decision_v2.posture_release import (
    flip_hit,
)
from sr_od.application.currency_war.decision_v2.registry import (
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


def test_c1_flip_orthogonal_at_d_boundary() -> None:
    """d=hp−boss_tax_p75 判据一刀切:hp=58(d=24<25)归 FLIP 末窗投影臂
    (C1 不评估);hp=59(d=25)归 C1(FLIP 投影臂不命中)——两谓词在
    边界两侧互斥,无重叠帧(ADR-0426 正交补集的 C1 侧兑现)。"""
    for hp, want_flip, want_c1 in ((58, True, False), (59, False, True)):
        st = _c1_state(hp=hp)
        sess = _boss_session()
        assert flip_hit(st, sess, _REG_C1, 'FORM') is want_flip
        assert c1_directed_active(st, sess, _REG_C1) is want_c1


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
    """3合1 即时合成买保留(合成后上场星级即涨);有空位时买全放行;
    店有可买+上的名集件时定向刷新放行(存在性判据)。"""
    tgt = _target_name()
    st_room = _c1_state(shop=[_card(tgt)])
    kept, _ = filter_candidates(_cands(tgt), st_room, _boss_session(),
                                _REG_C1)
    tags = {c.tag for c in kept}
    # bench 空:升级无件可上(Δp=0)照删;有空位时两类买+定向刷新放行
    assert {'line_carry', 'plugin', 'refresh'} <= tags
    assert 'levelup' not in tags
    st_merge = _bench_full_state()
    cands = _cands(tgt, merge=True)
    kept2, _ = filter_candidates(cands, st_merge, _boss_session(), _REG_C1)
    assert any(c.merge and c.tag == 'line_carry' for c in kept2), \
        '合成候选在 bench 满帧也保留(买入即升星上场)'


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
