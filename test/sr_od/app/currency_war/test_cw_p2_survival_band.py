"""P2 生存批单帧锁:C4 换线存活轮数门(重设计语义)+ 定谳清理卫生锁。

设计=唯一规格:`.debug/temp/currency_war/w373_c3c4_redesign/REDESIGN.md`
§3(C4 剩余节点逐节点投影)/§6.2 锁清单。旧版(W354 语义)锁的
「目标名单授权/LevelUp 无条件滤出/ceil 等权除数」已随重设计过期:
存活轮数改日历轮投影(逐批处置见本文件各 docstring)。锁的是策略
决策行为(单帧锁=回归工具):

- C4 存活轮数门(registry.line_switch_survival_gate_enabled,默认关):
  rounds_alive(剩余节点逐节点投影) ≥ E_rounds(新线)×(1+δ)+余量;
  边界(开关/plane≥2/inf 豁免);与 should_switch_e 串联语义。
  投影手算/奖励零损/未知占位/缺档/死锁画像/去重专项锁在
  test_cw_w373_c3c4_redesign.py。
- 定谳清理卫生锁:C3 濒死带(同批设计 §2)已被 ADR-0426 增补节定谳
  清理(删码留档)——开关/谓词/查表包装不再存在,共享面(损血表/
  部署空位判据/刷新名集/hp 可信位守卫)仍健在供 C4/C1 消费。
"""
from __future__ import annotations

import dataclasses
import math

from sr_od.application.currency_war.cw_line_switch import (
    rounds_alive,
    should_switch_e,
    survival_gate,
)
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.filters import (
    _deploy_free,
    _deploy_free_after_merge,
    _refreshable_names,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG_GATE = dataclasses.replace(DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)

#: P2 满表投影夹具(economy.md §10.2 模板,boss@末槽)
P2_FULL_TABLE = ['battle', 'battle', 'encounter', 'reward',
                 'encounter', 'reward', 'boss']


def _dying_state(**kw) -> GameState:
    """P2 帧夹具:plane=2、r3、hp 可读(C4 投影/守卫锁共用底座)。"""
    base = {
        'plane': 2, 'round_num': 3, 'gold': 30, 'level': 5,
        'hp': 20, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _tabled_session(round_num: int = 1,
                    table: list[str] | None = None) -> StrategySession:
    sess = StrategySession()
    sess.plane_node_table = list(table or P2_FULL_TABLE)
    sess.plane_node_table_plane = 2
    sess.round_num = round_num
    return sess


# --- 定谳清理卫生锁:C3 删除面不复存在 + 共享面健在 ---------------------------


def test_c3_symbols_removed_from_registry() -> None:
    """C3 定谳清理(ADR-0426 增补节):总开关与 C3 专属字段不再存在于
    registry——死概念不留「开关还在」的错误信号。"""
    assert not hasattr(DEFAULT_REGISTRY, 'dying_band_account_enabled')
    assert not hasattr(DEFAULT_REGISTRY, 'dying_band_high_cost_floor')
    assert hasattr(DEFAULT_REGISTRY, 'directed_refresh_high_cost_floor')


def test_shared_loss_table_alive_for_c4() -> None:
    """共享损血表健在锁:p2_cond_loss_table(条件败面档,W443 起为 C4
    投影幅度源)仍被 C4 投影消费(轻损表注入后 rounds_alive 位移)——
    表是 C4 的活数据,清理不伤。"""
    reg = dataclasses.replace(
        DEFAULT_REGISTRY,
        p2_cond_loss_table={'normal': 5.0, 'encounter': 6.0,
                            'boss': 8.0, 'reward': 0.0})
    assert rounds_alive(_dying_state(hp=25, round_num=1),
                        _tabled_session(), reg) == 7


def test_shared_face_helpers_alive_for_c1() -> None:
    """C1 判据共享面健在锁:部署空位/合成后空位/刷新名集/hp 可信位
    守卫四组符号仍在且可执行(C1 仍处演进中,清理批只删 C3 专属)。"""
    from sr_od.application.currency_war.decision_v2.posture_release import (
        hp_decision_trusted,
    )
    st = _dying_state()
    sess = StrategySession()
    assert _deploy_free(st) == st.max_units()
    assert isinstance(_refreshable_names(st, sess, DEFAULT_REGISTRY),
                      frozenset) and _refreshable_names(st, sess,
                                                        DEFAULT_REGISTRY)
    assert hp_decision_trusted(st) is True
    # 合成后空位完备式:板上 2 份同名 1★ + 买入合成 → 净腾 1 位
    from sr_od.application.currency_war.cw_state import BenchChar, ShopCard
    card = ShopCard(name='件甲', faction='仙舟罗浮', cost=1, x=0, star=1)
    st2 = _dying_state(
        deployed=[BenchChar(slot=i, char_id='件甲', faction='仙舟罗浮',
                            star=1, position_pref='front')
                  for i in range(st.max_units())])
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    from sr_od.application.currency_war.cw_state import BuyCard
    merge_c = Candidate(action=BuyCard(card, reason=''), tag='bridge_core',
                        source='shop', merge=True)
    assert _deploy_free_after_merge(merge_c, st2) == 1


# --- C4:存活轮数门(投影口径) ----------------------------------------------


def test_rounds_alive_projection_basic() -> None:
    """投影底座:默认表(W443 后=条件败面档 12.77/13.33/15.50,p 表空)
    +P2 满表夹具,r1 起逐节点扣:hp=50 → 37.23/24.46/11.13→奖励→
    遭遇死 → ra=5;hp=0 → 0。(旧 ceil(hp/等权均值) 口径已废除,查表锁
    随之更新。)"""
    sess = _tabled_session()
    assert rounds_alive(_dying_state(hp=50, round_num=1), sess) == 5
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
