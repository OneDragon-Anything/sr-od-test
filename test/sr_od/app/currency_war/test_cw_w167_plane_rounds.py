# -*- coding: utf-8 -*-
"""W167/ADR-0366 位面轮数口径断层修复单帧锁。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 单一源:nodes_of_plane 表在=表长(P1 9/P2 7/P3 自适应);表缺回退
  NODES_PER_PLANE=9 并告警一次(可 grep 记档通道);
- ② 冻结窗(cw_evolution final_freeze):P2 帧(表=7)r6 拆板事务冻结
  发射(旧按 9 判=空集的修复);P1 帧(表缺/9 槽)r7 不辖、r8-9 辖不变;
- ③ plane_last_battle:P2 boss@r7 判位面末(旧按 9 永不触发);P1 r9
  boss 判位面末不变;
- ④ _hard_node remaining≤3:P2(表=7)r5 战斗节点入窗(旧按 9 需 r7);
- ⑤ final_fence 轮门(scoring):P2 末轮(r7)+boss 窗 → line_opportunistic
  非目标件 'final_fence'(旧按 9 在 P2 永不触发);
- ⑥ plane_remaining_nodes:P2(表=7)r6 → 2(旧按 9 = 4);session 缺省
  None → P1 先验兼容(裸调用旧签名);
- ⑦ battles_left_p2 切片按表长(与旧 NODES_PER_PLANE 切片逐位等价——
  7 长表切到 9 本就取全表,纯语义对齐);
- ⑧ P1 逐位回归:表缺(P1 sim/裸 session)时冻结窗/plane_last_battle/
  _hard_node 与旧常量口径逐位同(零漂移的结构面)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_evolution import (
    EvolutionState,
    evolution_step,
)
from sr_od.application.currency_war.cw_plane_table import (    NODES_PER_PLANE,
    nodes_of_plane,
)
from sr_od.application.currency_war.cw_intention import plane_remaining_nodes
from sr_od.application.currency_war.cw_state import CompTransaction, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.discipline import (
    _hard_node,
    plane_last_battle,
)
from sr_od.application.currency_war.decision_v2.ev import battles_left_p2
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_P2_TABLE = ['battle', 'battle', 'supply', 'battle',
             'encounter', 'reward', 'boss']       # W157 16 局拼版(7 槽)
_P1_TABLE = ['reward'] * 2 + ['battle'] * 4 + ['encounter', 'battle', 'boss']


def _sess(table: list[str] | None) -> StrategySession:
    s = StrategySession()
    if table is not None:
        s.plane_node_table = list(table)
    return s


# ---------- ① 单一源 ----------

def test_nodes_of_plane_table_lengths():
    assert nodes_of_plane(_sess(_P2_TABLE)) == 7
    assert nodes_of_plane(_sess(_P1_TABLE)) == 9
    # P3 首局进表即自适应(口径断层修复的前向性:不写死 7)
    assert nodes_of_plane(_sess(_P1_TABLE[:-1])) == 8


def test_nodes_of_plane_fallback_when_table_missing():
    # 裸 session / None → 回退 P1 先验(零漂移的结构面)
    assert nodes_of_plane(_sess(None)) == NODES_PER_PLANE == 9
    assert nodes_of_plane(None) == 9


# ---------- ② 冻结窗 ----------

def _freeze_frame(plane: int, r: int, table: list[str] | None) -> GameState:
    """DOT2 单引擎帧(拆板事务可发射;test_cw_evolution 同构造法)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.cw_line_defs import _CORE_TRIO
    from sr_od.application.currency_war.cw_state import BenchChar, _recount_board

    def _c(name: str, faction: str) -> BenchChar:
        return BenchChar(slot=0, char_id=name, faction=faction,
                         position_pref=CHARACTERS[name].position_pref())

    st = GameState()
    st.plane = plane
    st.round_num = r
    st.gold = 20
    st.level = 8
    st.deployed = [_c(n, '持续伤害') for n in ('桑博', '艾丝妲', '卡芙卡')]
    st.bench = [_c(n, '仙舟') for n in sorted(_CORE_TRIO)]
    st.board = _recount_board(st.deployed)
    return st


def test_final_freeze_p2_r6_now_blocks_dismantle():
    """主修复:P2(表=7)r6 起冻结拆板——旧按 NODES_PER_PLANE=9 判,
    P2 冻结窗是空集(W165 #3 实证)。"""
    sess = _sess(_P2_TABLE)
    st = _freeze_frame(2, 6, _P2_TABLE)
    actions = evolution_step(st, sess, EvolutionState())
    assert not any(isinstance(a, CompTransaction) for a in actions)
    # P2 r5(末窗前)不受辖
    st5 = _freeze_frame(2, 5, _P2_TABLE)
    a5 = evolution_step(st5, sess, EvolutionState())
    assert any(isinstance(a, CompTransaction) for a in a5)


def test_final_freeze_p1_r7_r8_unchanged():
    """P1 逐位回归:表缺(session 未写表,= sim P1 段/开局首帧前)与
    9 槽表两路,r7 不辖 / r8 辖——与旧常量口径逐位同。"""
    for table in (None, _P1_TABLE):
        sess = _sess(table)
        st7 = _freeze_frame(1, 7, table)
        assert any(isinstance(a, CompTransaction)
                   for a in evolution_step(st7, sess, EvolutionState()))
        st8 = _freeze_frame(1, 8, table)
        assert not any(isinstance(a, CompTransaction)
                       for a in evolution_step(st8, sess, EvolutionState()))


# ---------- ③ plane_last_battle / ④ _hard_node ----------

def _node_state(plane: int, r: int, node: str) -> GameState:
    st = GameState()
    st.plane = plane
    st.round_num = r
    st.node_type = node
    return st


def test_plane_last_battle_p2_boss_at_r7():
    sess2 = _sess(_P2_TABLE)
    assert plane_last_battle(_node_state(2, 7, 'boss'), sess2) is True
    assert plane_last_battle(_node_state(2, 6, 'battle'), sess2) is False
    # P1:表缺与 9 槽表同判(r9 boss 位面末;r8 boss 非位面末——P1 boss@r9)
    for table in (None, _P1_TABLE):
        s = _sess(table)
        assert plane_last_battle(_node_state(1, 9, 'boss'), s) is True
        assert plane_last_battle(_node_state(1, 8, 'boss'), s) is False


def test_hard_node_p2_window_opens_two_rounds_earlier():
    """P2(表=7)remaining≤3 → r5 起战斗节点入窗(旧按 9 需 r7)。"""
    sess2 = _sess(_P2_TABLE)
    assert _hard_node(_node_state(2, 4, 'battle'), sess2) is True   # 7-4=3
    assert _hard_node(_node_state(2, 3, 'battle'), sess2) is False
    for table in (None, _P1_TABLE):
        s = _sess(table)
        assert _hard_node(_node_state(1, 6, 'battle'), s) is True
        assert _hard_node(_node_state(1, 5, 'battle'), s) is False


# ---------- ⑤ final_fence 轮门 ----------

def test_final_fence_p2_last_round_gate():
    """P2 末轮(r7)+boss 窗 → line_opportunistic 非目标件拒(final_fence)。

    直接锁轮门谓词(与 scoring._off_lock_verdict 内联条件同式):
    state.round_num >= nodes_of_plane(session) ∧ boss_window_active。
    """
    from sr_od.application.currency_war.decision_v2.discipline import (
        boss_window_active,
    )
    sess2 = _sess(_P2_TABLE)
    sess2.node_type_current = 'boss'
    reg = DEFAULT_REGISTRY
    st = _node_state(2, 7, 'boss')
    assert st.round_num >= nodes_of_plane(sess2)
    assert boss_window_active(st, sess2, reg)
    # r6 非末轮:轮门关(boss 窗开着也不辖——fence 只辖末轮)
    st6 = _node_state(2, 6, 'boss')
    assert not (st6.round_num >= nodes_of_plane(sess2))


# ---------- ⑥ plane_remaining_nodes ----------

def test_plane_remaining_nodes_p2_truth_and_legacy_signature():
    st = _node_state(2, 6, 'battle')
    assert plane_remaining_nodes(st, _sess(_P2_TABLE)) == 2   # 7-6+1
    # 裸调用(旧签名/兼容):回退 P1 先验
    assert plane_remaining_nodes(st) == NODES_PER_PLANE - 6 + 1  # = 4
    assert plane_remaining_nodes(_node_state(1, 1, 'battle')) == 9


# ---------- ⑦ battles_left_p2 切片 ----------

def test_battles_left_p2_slice_by_table_length():
    reg = DEFAULT_REGISTRY
    sess = _sess(_P2_TABLE)
    # r6(r_idx=5):[battle? no——slot6='reward' 除外] → slot5 encounter +
    # slot6 reward 之外…… 表[5:] = ['encounter','reward'] → 1 战斗
    assert battles_left_p2(_node_state(2, 6, 'battle'), sess, reg) == 1.0
    assert battles_left_p2(_node_state(2, 7, 'boss'), sess, reg) == 1.0
    # r1:全表 battle/battle/supply/battle/encounter/reward/boss → 5 战斗
    assert battles_left_p2(_node_state(2, 1, 'battle'), sess, reg) == 5.0
    # 表缺失 → registry 缺省(P1 骨架)
    assert battles_left_p2(_node_state(2, 1, 'battle'), _sess(None),
                           reg) == float(reg.battles_left_est)
    # 超长脏表守卫(W154 越界槽不数,ADR-0366 保留):7 槽表 + 脏尾 5 槽,
    # 切片按 NODES_PER_PLANE=9 封顶 → 前 9 槽内 5+2=7 战斗,第 10+ 槽不数
    dirty = _sess(list(_P2_TABLE) + ['battle'] * 5)   # 12 槽=脏表
    assert battles_left_p2(_node_state(2, 1, 'battle'), dirty,
                           reg) == 7.0
