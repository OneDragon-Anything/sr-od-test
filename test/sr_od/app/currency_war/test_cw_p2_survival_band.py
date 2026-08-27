"""P2 生存批单帧锁:C3 濒死带支出收窄 + C4 换线存活轮数门(重设计语义)。

设计=唯一规格:`.debug/temp/currency_war/w373_c3c4_redesign/REDESIGN.md`
§2(C3 Δp_board 代理)/§3(C4 剩余节点逐节点投影)/§6.2 锁清单。旧版
(W354 语义)锁的「目标名单授权/LevelUp 无条件滤出/ceil 等权除数」
已随重设计过期:名单退居评分先验、LevelUp 改可部署性谓词、存活轮数
改日历轮投影(逐批处置见本文件各 docstring)。锁的是策略决策行为
(单帧锁=回归工具):

- C3 濒死带(registry.dying_band_account_enabled,默认关=零漂移):
  Δp_board 符号判定——bench 满无空位的纯 hoard 买/升完仍无件可上的
  LevelUp/店无可上件的盲刷删,可上买/可引爆 bench 的 LevelUp/定向
  刷新放行,卖/上阵不辖;四边界(开关/hp_readable 守卫/plane≥2/嵌套
  应急触发线)逐项。
- C4 存活轮数门(registry.line_switch_survival_gate_enabled,默认关):
  rounds_alive(剩余节点逐节点投影) ≥ E_rounds(新线)×(1+δ)+余量;
  边界(开关/plane≥2/inf 豁免);与 should_switch_e 串联语义。
  投影手算/奖励零损/未知占位/缺档/死锁画像/去重专项锁在
  test_cw_w373_c3c4_redesign.py。
"""
from __future__ import annotations

import dataclasses
import math

from sr_od.application.currency_war.cw_line_switch import (
    rounds_alive,
    should_switch_e,
    survival_gate,
)
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
    dying_band_active,
    filter_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG_DYING = dataclasses.replace(DEFAULT_REGISTRY,
                                 dying_band_account_enabled=True)
_REG_GATE = dataclasses.replace(DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)

#: P2 满表投影夹具(economy.md §10.2 模板,boss@末槽)
P2_FULL_TABLE = ['battle', 'battle', 'encounter', 'reward',
                 'encounter', 'reward', 'boss']


def _card(name: str, cost: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _unit(slot: int, name: str = '件', front: bool = True) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction='仙舟罗浮', star=1,
                     position_pref='front' if front else 'back')


def _dying_state(**kw) -> GameState:
    """濒死帧:P2 r3、应急深带内(hp=20 ≤ normal 档 20.05)、hp 可读。"""
    base = {
        'plane': 2, 'round_num': 3, 'gold': 30, 'level': 5,
        'hp': 20, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _cands(target: str, other: str = '散件甲') -> list[Candidate]:
    """六类候选各一:目标件买/非目标件买/升级/刷新/卖/上阵。"""
    return [
        Candidate(action=BuyCard(_card(target), reason=''), tag='line_carry',
                  source='shop'),
        Candidate(action=BuyCard(_card(other), reason=''), tag='plugin',
                  source='shop'),
        Candidate(action=LevelUp(cost=4), tag='levelup', source='xp'),
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
        Candidate(action=SellBench(bench_idx=0, income=1, expect=''),
                  tag='for_gold', source='bench'),
        Candidate(action=DeployMove(bench_idx=1, to_row='front',
                                    faction='仙舟罗浮'),
                  tag='deploy', source='fence'),
    ]


def _tabled_session(round_num: int = 1,
                    table: list[str] | None = None) -> StrategySession:
    sess = StrategySession()
    sess.plane_node_table = list(table or P2_FULL_TABLE)
    sess.plane_node_table_plane = 2
    sess.round_num = round_num
    return sess


# --- C3:濒死带判据边界 ------------------------------------------------------


def test_dying_band_default_off() -> None:
    """默认关=零漂移:registry 缺省下濒死判据恒 False。"""
    assert not dying_band_active(_dying_state(), StrategySession(),
                                 DEFAULT_REGISTRY)


def test_dying_band_hp_readable_guard() -> None:
    """hp_readable=False(置信 0 帧,hp 是沿用值)假帧不评估。"""
    st = _dying_state(hp_readable=False, hp=1)
    assert not dying_band_active(st, StrategySession(), _REG_DYING)


def test_dying_band_plane_scope() -> None:
    """辖域 plane≥2:P1 濒死帧不辖(批辖域声明)。"""
    st = _dying_state(plane=1, round_num=7)
    assert not dying_band_active(st, StrategySession(), _REG_DYING)


def test_dying_band_nested_in_emergency() -> None:
    """触发线嵌套:hp>emergency_hp 恒 False——濒死带不新增覆盖态触发线,
    与 release FLIP 辖区(hp>25)零交集(结构互斥)。"""
    st = _dying_state(hp=DEFAULT_REGISTRY.emergency_hp + 1)
    assert not dying_band_active(st, StrategySession(), _REG_DYING)


def test_dying_band_threshold_boundary() -> None:
    """边界:hp ≤ 下一战期望损血(缺读节点→normal 档)即濒死;
    hp=20 ≤ 20.05 命中,hp=emergency_hp(25)>20.05 不命中。"""
    sess = StrategySession()
    assert dying_band_active(_dying_state(hp=20), sess, _REG_DYING)
    assert not dying_band_active(_dying_state(hp=25), sess, _REG_DYING)


def test_dying_band_boss_bucket_lookup() -> None:
    """三档谱查表:同一 hp=25(应急带内),boss 节点走 boss 档(≤26.71)
    濒死;normal 节点(>20.05)不濒死——档位查表生效。"""
    sess_boss = StrategySession()
    sess_boss.node_type_current = 'boss'
    sess_norm = StrategySession()
    assert dying_band_active(_dying_state(hp=25), sess_boss, _REG_DYING)
    assert not dying_band_active(_dying_state(hp=25), sess_norm, _REG_DYING)


# --- C3:支出收窄(Δp_board 符号判定链行为) ----------------------------------


def _target_name() -> str:
    """目标件名(裸 session 目标集=引擎件全集,单一源回退语义)。"""
    return sorted(engine_char_names())[0]


def test_dying_band_narrows_by_delta_p_board() -> None:
    """濒死帧 Δp_board 收窄:有空位时买(目标与非目标)都放行(名单不再
    是门槛,A1-β);bench 无件 LevelUp 删(levelup_no_deploy——升完仍无
    件可上,Δp=0);金<危机线 refresh 仍被应急标签集滤出(基线行为);
    卖/上阵不辖。(此帧空位充足,买类不触发 hoard 收窄。)"""
    tgt = _target_name()
    st = _dying_state()
    sess = StrategySession()
    kept, flog = filter_candidates(_cands(tgt), st, sess, _REG_DYING)
    tags = {c.tag for c in kept}
    assert {'line_carry', 'plugin', 'for_gold', 'deploy'} <= tags, \
        '有空位时两类买+卖/上阵必须放行'
    assert 'levelup' not in tags
    drops = {e['tag']: e.get('dying_band', '') for e in flog if not e['kept']}
    assert drops.get('levelup') == 'levelup_no_deploy'


def test_dying_band_directed_refresh_by_playable_presence() -> None:
    """定向刷新(金≥40 危机线开 refresh):店有可买+上的目标件→放行;
    店无任何名集件(且非高费强件)→删(blind_refresh,存在性判据)。"""
    tgt = _target_name()
    sess = StrategySession()
    st_with = _dying_state(gold=45, shop=[_card(tgt)])
    kept, _ = filter_candidates(_cands(tgt), st_with, sess, _REG_DYING)
    assert any(isinstance(c.action, RefreshShop) for c in kept)
    st_without = _dying_state(gold=45, shop=[_card('无关件乙')])
    kept2, flog2 = filter_candidates(_cands(tgt), st_without, sess, _REG_DYING)
    assert not any(isinstance(c.action, RefreshShop) for c in kept2)
    drops = {e['tag']: e.get('dying_band', '') for e in flog2 if not e['kept']}
    assert drops.get('refresh') == 'blind_refresh'


def test_dying_band_off_zero_drift() -> None:
    """零漂移锚:同帧开关关 → 应急标签集行为不变(两类买/升级全放行)。"""
    tgt = _target_name()
    st = _dying_state()
    sess = StrategySession()
    kept_off, _ = filter_candidates(_cands(tgt), st, sess, DEFAULT_REGISTRY)
    tags = {c.tag for c in kept_off}
    assert {'line_carry', 'plugin', 'levelup', 'for_gold',
            'deploy'} <= tags


# --- C4:存活轮数门(投影口径) ----------------------------------------------


def test_rounds_alive_projection_basic() -> None:
    """投影底座:默认表(常数口径,p 表空)+P2 满表夹具,r1 起逐节点扣:
    hp=50 → 战斗 29.95/9.9 → 遭遇 −6.77 死 → ra=3;hp=0 → 0。
    (旧 ceil(hp/等权均值) 口径已废除,查表锁随之更新。)"""
    sess = _tabled_session()
    assert rounds_alive(_dying_state(hp=50, round_num=1), sess) == 3
    assert rounds_alive(_dying_state(hp=0), sess) == 0


def test_survival_gate_default_off_and_scope() -> None:
    """开关关/plane<2/新线 inf → 放行(零漂移;inf 已被 should_switch_e
    的 alt_inf 拦,门不重复裁决)。"""
    sess = StrategySession()
    assert survival_gate(_dying_state(), sess, 3.0,
                         DEFAULT_REGISTRY) == (True, 'gate_off')
    st_p1 = _dying_state(plane=1)
    assert survival_gate(st_p1, sess, 99.0, _REG_GATE) == (True, 'gate_off')
    st_inf = _dying_state(hp=100)
    assert survival_gate(st_inf, sess, math.inf, _REG_GATE) == (True,
                                                                'gate_off')


def test_survival_gate_boundary() -> None:
    """门边界(含 δ 先修偏与 boss 附加费):r4 起投影路径含 boss →
    need=E×1.15+1+1.53。hp=50 → ra=5(奖励 0 损/遭遇/战斗/boss 结算死):
    E=1.5 → 需 4.255 放行;E=2.5 → 需 5.405 拦(边界取拦侧——估计量
    方差大的保守方向)。"""
    sess = _tabled_session(round_num=4)
    st = _dying_state(hp=50)
    ok, why = survival_gate(st, sess, 1.5, _REG_GATE)
    assert ok and why == 'ok'
    ok, why = survival_gate(st, sess, 2.5, _REG_GATE)
    assert not ok and why.startswith('survival(')


def test_survival_gate_serial_after_e_rounds() -> None:
    """串联语义:第三道门——should_switch_e 判 ok 后门仍可拦;与 θ/δ/D_min
    同族(纯函数组合;消费点=default_strategy 换线采纳前)。"""
    sess = _tabled_session()
    st = _dying_state(hp=50)
    do, _ = should_switch_e(4.54, 3.0, 2, DEFAULT_REGISTRY)
    assert do, '夹具前提:E_rounds 主判据放行'
    ok, _ = survival_gate(st, sess, 5.0, _REG_GATE)
    assert not ok, '存活轮数不足时串联门必须拦(堵转进死线)'
