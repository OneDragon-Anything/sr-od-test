"""C1 溢余必花定向优先级单帧锁(P1 末窗投影安全带;FLIP 正交补集)。

设计=唯一规格:`.debug/temp/currency_war/w382_c1_design/DESIGN.md`
§2(期望账)/§3(路线 B 辖域裁决)。辖域=P1 末窗 ∧ d=hp−boss_tax_p75
≥ emergency_hp(与 FLIP 末窗投影臂 d<emergency_hp 按 d 一刀切互斥)
∧ 溢余段 g>interest_floor。锁的是策略决策行为(单帧锁=回归工具):

- 定向优先级锁(registry.c1_directed_spend_enabled,默认关=零漂移):
  C1 帧内零 boss 增量支出删(纯 hoard 买/盲刷/升完无件可上的 LevelUp),
  可部署买/3合1 合成且合成后可上买(完备式,与濒死带同款)/定向刷新放行,
  卖/上阵不辖——溢余段花金
  零息损(成本恒 0),Δp≤0 支出确定性零收益,「必花+定向」的优先级
  语义=零贡献让位有增量;
- 辖域正交锁:d 边界(hp=58/59)上 flip_hit(FLIP 末窗投影臂)与
  c1_directed_active 互斥不重叠(两谓词按同一 d 判据切分,合起来
  不重不漏覆盖末窗溢余帧);
- 零漂移锚:默认关时 C1 形帧的过滤行为逐位一致。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.cw_intention import IntentionState
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


# --- C1 资产臂锁(V_asset 跨位面资产通道)-------------------------------------
#
# 设计=唯一规格:`.debug/temp/currency_war/w397_s5_asset_channel/DESIGN.md`
# §2(V_asset 定义)/§3(析取式判据与边界帧穷举)。锁:
# - 公式锁(手算代入):V_asset = m × p_slot × δ_unit × L2 × hp_to_gold,
#   m=1、p_slot=0.5、δ_unit=0.03、L2=12 → 1×0.5×0.03×12×0.5 = 0.09 金当量
#   >0 → 放行(与现行为零漂移的判据方向解耦:溢余段是符号判定);
# - 边界帧锁:B1/B2/B5 类(m≥m_min 资产臂正→放行)、B3/B4/B8/B10 类
#   (m=0/满星 m_eff=0/店全散件/无可兑现资产→仍删,新删因名
#   c1_hoard_buy_junk 分通道记账);
# - 零漂移锚:资产臂开关关=现行为逐位一致(含删因名与链日志字段)。

# 锁定线=COMP_LIBRARY 注册套(名集单一源:核=core_chars,共享=shared_chars,
# 替班=substitute_plan——不重抄名单)。「DOT队」:核含 卡芙卡(1.0),共享
# 桑博为纯 shared 不在 core(0.5),level_plan star_goals 桑博:2。
_LOCKED_COMP = 'DOT队'
_CORE_NAME = '卡芙卡'
_SHARED_NAME = '桑博'


def _reg_asset(**kw) -> object:
    return dataclasses.replace(_REG_C1, c1_asset_channel_enabled=True, **kw)


def _locked_session(comp: str = _LOCKED_COMP) -> StrategySession:
    sess = _boss_session()
    sess.v3_intention = IntentionState(phase='locked', locked_comp=comp)
    return sess


def test_c1_asset_arm_formula_b1_b2() -> None:
    """公式锁·B1/B2:bench 满无空位、买核件(m=1)/共享件(m=0.5)——
    Δp_board=0 但 V_asset>0 → 放行(手算 0.09/0.045 金当量);链日志带
    c1_asset_pass/c1_asset_m。非目标件(m=0,B3)仍删,删因名改
    c1_hoard_buy_junk 分通道记账。"""
    st = _bench_full_state(shop=[_card(_CORE_NAME)])
    sess = _locked_session()
    cands = _cands(_CORE_NAME)
    # 共享件买候选(m=0.5,m_min=0.5 计入):V_asset=0.5×0.5×0.03×12×0.5
    # = 0.045 > 0 → 同帧放行
    cands.append(Candidate(action=BuyCard(_card(_SHARED_NAME), reason=''),
                           tag='line_carry', source='shop'))
    kept, flog = filter_candidates(cands, st, sess, _reg_asset())
    tags = {c.tag for c in kept}
    assert 'levelup' in tags and 'for_gold' in tags and 'deploy' in tags
    by_name = {}
    for e in flog:
        by_name.setdefault(e['tag'], []).append(e)
    core_rows = by_name['line_carry']
    assert sum(1 for e in core_rows if e.get('c1_asset_pass')) == 2, \
        '核件(m=1)与共享件(m=0.5)两笔资产臂放行'
    assert any(e.get('c1_asset_m') == 1.0 for e in core_rows)
    assert any(e.get('c1_asset_m') == 0.5 for e in core_rows)
    assert all(e.get('kept', True) for e in core_rows)
    plugin = by_name['plugin'][0]   # 散件甲 m=0
    assert not plugin['kept']
    assert plugin['c1_directed'] == 'c1_hoard_buy_junk'
    assert plugin.get('c1_asset_pass') is False
    assert plugin.get('c1_asset_m') == 0.0


def test_c1_asset_arm_directed_refresh_b7_b8() -> None:
    """B7/B8:店有 m≥m_min 可买件但本窗凑不齐可上(bench 满)→ 资产
    刷新存在性臂放行;店全 m<m_min → 仍删(c1_blind_refresh)。"""
    sess = _locked_session()
    st_b7 = _bench_full_state(shop=[_card(_CORE_NAME)])
    kept, _ = filter_candidates(_cands(_CORE_NAME), st_b7, sess,
                                _reg_asset())
    assert any(c.tag == 'refresh' for c in kept), 'B7:核件可买的定向刷新放行'
    st_b8 = _bench_full_state(shop=[_card('散件甲')])
    kept8, flog8 = filter_candidates(_cands(_CORE_NAME), st_b8, sess,
                                     _reg_asset())
    assert not any(c.tag == 'refresh' for c in kept8)
    drop8 = [e for e in flog8 if e['tag'] == 'refresh' and not e['kept']][0]
    assert drop8['c1_directed'] == 'c1_blind_refresh'
    assert drop8.get('c1_asset_pass') is False


def test_c1_asset_arm_b5_merge_bench_fall() -> None:
    """B5:3合1 合成落 bench 无位、合成体是目标件——Δp_board=0 但
    V_asset>0(2★ 件 P2 直接上场,m 按名计与是否即时可上无关)→ 放行。"""
    st = _c1_state(
        deployed=[_unit(i, f'上{i}') for i in range(5)],
        bench=[_unit(i, f'备{i}') for i in range(9)])
    sess = _locked_session()
    cands = [Candidate(action=BuyCard(_card(_CORE_NAME), reason=''),
                       tag='line_carry', source='shop', merge=True)]
    kept, _ = filter_candidates(cands, st, sess, _reg_asset())
    assert any(c.merge for c in kept), 'B5:合成体为目标件的资产臂放行'


def test_c1_asset_arm_star_cap_b4() -> None:
    """B4:已满星目标件(m_eff=0,防重复囤零边际)→ 仍删(junk)。"""
    st = _c1_state(
        deployed=[_unit(i, f'上{i}') for i in range(4)]
        + [BenchChar(slot=10, char_id=_CORE_NAME, faction='仙舟罗浮',
                     star=2, position_pref='front')],
        bench=[_unit(i, f'备{i}') for i in range(9)])
    sess = _locked_session()
    kept, flog = filter_candidates(_cands(_CORE_NAME), st, sess,
                                   _reg_asset())
    assert not any(c.tag == 'line_carry' for c in kept)
    drop = [e for e in flog if e['tag'] == 'line_carry' and not e['kept']][0]
    assert drop['c1_directed'] == 'c1_hoard_buy_junk'
    assert drop.get('c1_asset_m') == 0.0, '满星 m_eff=0'


def test_c1_asset_arm_levelup_b9_b10() -> None:
    """B9:bench 有目标件但升完仍多上不了(空位外结构性原因)→ 资产臂
    放行(等级 cap 跨位面继承);B10:bench_n=0 无可兑现资产 → 仍删。"""
    sess = _locked_session()
    # B9:deployed 4(空位 1)、bench 1 件=核件 → free(1)≥bench_n(1),
    # 升完不多上,Δp_board=0;资产臂按 bench 核件 m=1 放行
    st_b9 = _c1_state(
        deployed=[_unit(i, f'上{i}') for i in range(4)],
        bench=[BenchChar(slot=0, char_id=_CORE_NAME, faction='仙舟罗浮',
                         star=1, position_pref='front')])
    kept, _ = filter_candidates(_cands(_CORE_NAME), st_b9, sess,
                                _reg_asset())
    assert any(c.tag == 'levelup' for c in kept), 'B9:bench 目标件资产臂放行'
    # B10:bench 空 → 无可兑现资产,升级仍删
    st_b10 = _c1_state(deployed=[_unit(i, f'上{i}') for i in range(4)])
    kept10, _ = filter_candidates(_cands(_CORE_NAME), st_b10, sess,
                                  _reg_asset())
    assert not any(c.tag == 'levelup' for c in kept10)


def test_c1_asset_arm_requires_locked_comp() -> None:
    """未锁线:资产臂整体不激活(m 无定义),退回 Δp_board-only 判据——
    删因名保持 c1_hoard_buy,链日志不带 c1_asset_* 字段(DESIGN §2.2)。"""
    st = _bench_full_state(shop=[_card(_CORE_NAME)])
    kept, flog = filter_candidates(_cands(_CORE_NAME), st, _boss_session(),
                                   _reg_asset())
    assert not any(c.tag == 'line_carry' for c in kept)
    drop = [e for e in flog if e['tag'] == 'line_carry' and not e['kept']][0]
    assert drop['c1_directed'] == 'c1_hoard_buy'
    assert 'c1_asset_pass' not in drop and 'c1_asset_m' not in drop


def test_c1_asset_arm_off_zero_drift() -> None:
    """零漂移锚:资产臂开关关(C1 本体开)→ 现行 W384 行为逐位一致:
    删因名 c1_hoard_buy,链日志无 c1_asset_* 字段。"""
    st = _bench_full_state(shop=[_card(_CORE_NAME)])
    kept, flog = filter_candidates(_cands(_CORE_NAME), st, _locked_session(),
                                   _REG_C1)
    assert not any(c.tag == 'line_carry' for c in kept)
    drop = [e for e in flog if e['tag'] == 'line_carry' and not e['kept']][0]
    assert drop['c1_directed'] == 'c1_hoard_buy'
    assert 'c1_asset_pass' not in drop and 'c1_asset_m' not in drop


def test_c1_asset_arm_symbol_gate_constants() -> None:
    """符号门:p_slot 或 δ_unit 归零(标定量未定符号的保守注入)→ 资产臂
    恒不放行,删因名回 c1_hoard_buy(激活前提不满足=未评估)。"""
    st = _bench_full_state(shop=[_card(_CORE_NAME)])
    sess = _locked_session()
    for kw in ({'c1_asset_p_slot': 0.0}, {'c1_asset_delta_unit': 0.0}):
        kept, flog = filter_candidates(_cands(_CORE_NAME), st, sess,
                                       _reg_asset(**kw))
        assert not any(c.tag == 'line_carry' for c in kept)
        drop = [e for e in flog
                if e['tag'] == 'line_carry' and not e['kept']][0]
        assert drop['c1_directed'] == 'c1_hoard_buy'
