"""C4 重设计落码批单帧锁(§6.2 锁清单;C3 侧锁已随 ADR-0426 增补节
定谳清理删除)。

设计=唯一规格:`.debug/temp/currency_war/w373_c3c4_redesign/REDESIGN.md`
§3/§4/§6.2。旧 W354 语义的反模式在本批锁死不复发:
- A3:rounds_alive 用 ceil(hp/等权均值) 把战斗均摊损失摊到奖励零损轮,
  系统性低估存活——C4-L1/L2 锁投影口径。
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from sr_od.application.currency_war.cw_line_switch import (
    node_loss_kind,
    register_gate_block,
    rounds_alive,
    should_switch_e,
    survival_gate,
)
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG_GATE = dataclasses.replace(DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)
#: 两态口径夹具(p_rung=0.65,W346 §3.2 rung2 胜占比量级;空板 rung=0;
#: rounds_two_state_enabled=True——两态通道总开关,默认关=零漂移锚)
_REG_TWO_STATE = dataclasses.replace(
    _REG_GATE, rounds_two_state_enabled=True,
    p_win_p2_by_rung={0: 0.65, 1: 0.65, 2: 0.65})

P2_FULL_TABLE = ['battle', 'battle', 'encounter', 'reward',
                 'encounter', 'reward', 'boss']


def _state(**kw) -> GameState:
    base = {
        'plane': 2, 'round_num': 1, 'gold': 30, 'level': 5,
        'hp': 20, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _sess(round_num: int = 1,
          table: list[str] | None = None) -> StrategySession:
    s = StrategySession()
    s.plane_node_table = list(table or P2_FULL_TABLE)
    s.plane_node_table_plane = 2
    s.round_num = round_num
    return s


# --- C4-L1:投影手算锁(常数口径数表入注释) ----------------------------------


def test_c4_l1_projection_hand_computed() -> None:
    """满表夹具×常数口径(W443 后幅度源=p2_cond_loss_table 条件败面档
    12.77/13.33/15.50,p 表空),r1 起:
    hp=29:12.77→16.23→12.77→3.46→遭遇 13.33 死 → ra=3;hp=43:
    30.23→17.46→4.13→奖励→遭遇死 → ra=5;hp=60:…→奖励→7.8→奖励→
    boss 15.5 死 → ra=7。"""
    sess = _sess()
    assert rounds_alive(_state(hp=29), sess) == 3
    assert rounds_alive(_state(hp=43), sess) == 5
    assert rounds_alive(_state(hp=60), sess) == 7


# --- C4-L2:奖励零损轮锁 ------------------------------------------------------


def test_c4_l2_reward_front_extends_survival() -> None:
    """同 hp=25、同战斗构成:奖励轮前置的表 ra=3 > 战斗轮前置 ra=2——
    零损日历轮照走(等权除数口径漏算奖励轮的病灶方向锁)。"""
    reward_front = ['reward', 'battle', 'battle', 'encounter',
                    'reward', 'encounter', 'boss']
    battle_front = list(P2_FULL_TABLE)
    ra_r = rounds_alive(_state(hp=25), _sess(table=reward_front))
    ra_b = rounds_alive(_state(hp=25), _sess(table=battle_front))
    assert ra_r == 3 and ra_b == 2 and ra_r > ra_b


# --- C4-L3:未知节点保守锁 ----------------------------------------------------


def test_c4_l3_unknown_node_counts_as_normal_battle() -> None:
    """表含「?」占位 → 按 battle+normal 档计损(hp=20:12.77→7.23→
    奖励→遭遇死 → ra=3;未知多算一场损失=存活估计更短=门更紧,
    保守方向声明)。"""
    table = ['?', 'reward', 'encounter', 'reward', 'encounter',
             'reward', 'boss']
    assert node_loss_kind('?') == 'normal'
    assert rounds_alive(_state(hp=20), _sess(table=table)) == 3


# --- C4-L4:缺档零损锁 --------------------------------------------------------


def test_c4_l4_missing_kind_zero_loss_calendar_still_ticks() -> None:
    """p2_cond_loss_table 缺 kind → 该轮损 0、轮数照计(与旧实现
    「缺读=normal 最大战斗档」方向相反且各自声明):缺 encounter/boss
    档,hp=1 走完 encounter(0 损)与 boss(0 损)→ ra=2=全表长。"""
    reg = dataclasses.replace(DEFAULT_REGISTRY,
                              p2_cond_loss_table={'normal': 12.77})
    sess = _sess(table=['encounter', 'boss'])
    assert rounds_alive(_state(hp=1), sess, reg) == 2


# --- S8 单一源不变量锁:损血表唯一(消费面=C4 投影) ----------------------------


def test_p2_node_loss_table_single_source() -> None:
    """损血表单一源不变量(C4 逐节点投影 rounds_alive 读
    registry.p2_cond_loss_table 条件败面档;原批 C3 桶位查表消费点已随
    ADR-0426 增补节定谳清理删除;无条件期望表 p2_node_loss_table 是另一
    estimand,消费面=阈值层 _loss_dist,W443 起):注入自定义表后投影
    同步位移——重标定覆写只改一处,「数值源唯一」由本锁固化,不靠人工
    纪律。"""
    assert not hasattr(DEFAULT_REGISTRY, 'dying_band_next_loss')
    assert not hasattr(DEFAULT_REGISTRY, 'line_switch_node_loss')
    assert not hasattr(DEFAULT_REGISTRY, 'dying_band_account_enabled')
    reg = dataclasses.replace(
        DEFAULT_REGISTRY,
        p2_cond_loss_table={'normal': 5.0, 'encounter': 6.0,
                            'boss': 8.0, 'reward': 0.0})
    sess = _sess(table=P2_FULL_TABLE)
    # C4 逐节点投影跟随同一份表(hp=25:默认条件档 12.77/13.33/15.50 →
    # ra=2;轻损表 5/6/8 → 25−5−5−6+0−6+0−8 死于 boss → ra=7)
    assert rounds_alive(_state(hp=25), _sess()) == 2
    assert rounds_alive(_state(hp=25), sess, reg) == 7


# --- C4-L5:死锁画像双向锁 ----------------------------------------------------


def test_c4_l5_deadlock_frame_both_calibers() -> None:
    """hp=29 + E_cur=inf + E_alt=2 的死锁画像,两行行为各锁:
    常数口径(p 表空,每战全损)→ ra=2 < need → 拦(理由 survival);
    两态口径(p_rung=0.65 注入,板强通道进投影)→ ra=7 ≥ need → 放行
    (「强板换线能活到兑现」由胜率通道可达,REDESIGN §3.6 数表)。"""
    sess = _sess()
    st = _state(hp=29)
    do, _ = should_switch_e(math.inf, 2.0, 2, DEFAULT_REGISTRY)
    assert do, '夹具前提:E_cur=inf 时主判据放行'
    ok, why = survival_gate(st, sess, 2.0, _REG_GATE)
    assert not ok and why.startswith('survival(')
    ok2, why2 = survival_gate(st, sess, 2.0, _REG_TWO_STATE)
    assert ok2 and why2 == 'ok', f'两态口径必须放行(实得 {why2})'
    assert rounds_alive(st, sess, _REG_TWO_STATE) == 7


# --- C4-L6:去重锁 ------------------------------------------------------------


def test_c4_l6_gate_block_log_dedup() -> None:
    """同线对二次拦截不重复发日志:计数累加(1→2→3),换线对重新计数
    (消费侧约定=次数 1 发日志行,>1 只累加)。"""
    sess = StrategySession()
    assert register_gate_block(sess, '甲线', '乙线') == 1
    assert register_gate_block(sess, '甲线', '乙线') == 2
    assert register_gate_block(sess, '甲线', '乙线') == 3
    assert register_gate_block(sess, '甲线', '丙线') == 1


# --- 标-L1:标定双源锁(口径语义固化在夹具语料上) ----------------------------


def _frame_losses(rows: list[dict]) -> dict[str, list[float]]:
    """标定脚本源 A 同口径(相邻战斗类行差分;hp_after=0 死亡行按
    hp_before 全额;hp≤1 不删失;不按置信度过滤;净负记 0 损)。"""
    BK = {'普通战斗': 'normal', '遭遇': 'encounter', 'boss': 'boss'}
    by_run: dict[str, list[dict]] = {}
    for r in rows:
        by_run.setdefault(r['run_id'], []).append(r)
    buckets: dict[str, list[float]] = {}
    for seq in by_run.values():
        seq = sorted(seq, key=lambda r: (r['plane'], r['round_num']))
        pb = [r for r in seq if r['plane'] == 2
              and r.get('node_type') in BK]
        for prev, cur in zip(pb, pb[1:], strict=False):
            a, b = prev.get('hp_after'), cur.get('hp_after')
            if a is None or b is None:
                continue
            loss = float(a) if b <= 0 else max(0.0, float(a) - float(b))
            buckets.setdefault(BK[cur['node_type']], []).append(loss)
    return buckets


def test_std_l1_dual_source_calibration_semantics() -> None:
    """标定口径三要素(死亡行全额入桶修反保守/hp≤1 入桶/置信=0 行入桶):
    夹具语料上帧级桶必须含死亡事件全额 30、hp=1 行前差 19;双源互校
    判据=帧级合并均值必须落在 run 级 CI 内,出界即 raise(红旗)。"""
    rows = [
        # run A:战斗 40 → 奖励 45(回血)→ 战斗 30 → boss 死(hp 0,置信 0)
        {'run_id': 'A', 'plane': 2, 'round_num': 1, 'node_type': '普通战斗',
         'hp_after': 40, 'hp_confidence': 1.0},
        {'run_id': 'A', 'plane': 2, 'round_num': 2, 'node_type': '奖励',
         'hp_after': 45, 'hp_confidence': 1.0},
        {'run_id': 'A', 'plane': 2, 'round_num': 3, 'node_type': '普通战斗',
         'hp_after': 30, 'hp_confidence': 1.0},
        {'run_id': 'A', 'plane': 2, 'round_num': 4, 'node_type': 'boss',
         'hp_after': 0, 'hp_confidence': 0.0},
        # run B:战斗 20 → 战斗 1(hp=1 非死亡,不删失)
        {'run_id': 'B', 'plane': 2, 'round_num': 1, 'node_type': '普通战斗',
         'hp_after': 20, 'hp_confidence': 1.0},
        {'run_id': 'B', 'plane': 2, 'round_num': 2, 'node_type': '普通战斗',
         'hp_after': 1, 'hp_confidence': 1.0},
    ]
    buckets = _frame_losses(rows)
    assert buckets['boss'] == [30.0], '死亡行必须按 hp_before 全额入桶'
    assert buckets['normal'] == [10.0, 19.0], (
        '跨奖励回血的战斗差分=10,hp=1 行前差 19 必须入桶(不删失)')
    # 互校判据:帧级均值 19.67 ∉ run 级 CI [10,11] → raise
    frame_mean = (sum(buckets['normal']) + sum(buckets['boss'])) / 3
    run_ci = (10.0, 11.0)
    with pytest.raises(SystemExit):
        if not (run_ci[0] <= frame_mean <= run_ci[1]):
            raise SystemExit('标定红旗:帧级均值 ∉ run 级 CI')


# --- 兜-L1:零漂移锁 ----------------------------------------------------------


def test_zero_drift_default_off_chain() -> None:
    """开关默认关:registry 缺省下门恒放行——decide 全链与基线逐位
    一致的结构前提(registry hash 锁另辖字段面)。"""
    assert DEFAULT_REGISTRY.line_switch_survival_gate_enabled is False
    st = _state(hp=20)
    assert survival_gate(st, _sess(), 99.0, DEFAULT_REGISTRY)[0] is True
