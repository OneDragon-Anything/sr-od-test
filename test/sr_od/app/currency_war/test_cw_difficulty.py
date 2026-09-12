"""test_cw_difficulty 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- difficulty_account: test_cw_difficulty_account.py
- difficulty_live_contamination: test_cw_difficulty_live_contamination.py
- difficulty_readchain: test_cw_difficulty_readchain.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== difficulty_account ====================
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_difficulty_account import (  # noqa: E402
    DifficultyAccount,
    marginal_value,
)


def test_j1_account_identity() -> None:
    """J1:恒等式对账——total = base+Σaug+通胀+动态+曲线;OCR 修正残差进未知桶。"""
    acc = DifficultyAccount(base=108, augments={'简单模式': -3, '难度修改器': -4},
                            quality_inflation=12, streak=3, node_curve=5)
    assert acc.total() == 108 - 7 + 12 + 3 + 5
    acc.reconcile(acc.total() + 2.5)   # OCR 读到比账本多 2.5
    assert abs(acc.total() - (108 - 7 + 12 + 3 + 5 + 2.5)) < 1e-6
    acc2 = DifficultyAccount(base=100)
    acc2.reconcile(None)               # 读不到 → 外推不回退
    assert acc2.total() == 100.0


def test_marginal_three_states() -> None:
    """三态价值:同 −5 难度,大胜局≈0/边际局峰值/无解局→0(场合依赖,flat 惩罚算不出)。"""
    v_blow = marginal_value(100, -5, gap=-80)     # 大胜
    v_edge = marginal_value(100, -5, gap=0)        # 边际
    v_lost = marginal_value(100, -5, gap=80)       # 无解
    assert v_edge > v_blow and v_edge > 0
    assert abs(v_lost) < 0.01 and abs(v_blow) < 0.01


def test_p1_spike_retired() -> None:
    """ADR-0519:P1 尖峰 ×1.5 放大已按「未证即退役」删除(「一层最凶」
    定性有实证、系数拍定)——位面不再改变降难度边际价值。"""
    v_p1 = marginal_value(100, -5, gap=0, plane=1)
    v_p2 = marginal_value(100, -5, gap=0, plane=2)
    assert v_p1 == v_p2


def test_overflow_gambit_version_guard() -> None:
    """溢出反转:堆难度跨 200 → 大跳价值;证据态 refuted → gambit 退役(不跳)。"""
    v_overflow = marginal_value(195, +20, gap=0, overflow_evidence='verified')
    v_normal = marginal_value(95, +20, gap=0)
    assert v_overflow > v_normal + 5
    # refuted:同一跳跃位置不触发
    v_refuted = marginal_value(195, +20, gap=0, overflow_evidence='refuted')
    assert v_refuted < v_overflow


def test_floor_diminishing() -> None:
    """地板:压到 0 以下收益衰减。"""
    v_ok = marginal_value(30, -5, gap=0)
    v_over = marginal_value(3, -5, gap=0)    # 压到 -2
    assert v_over < v_ok


# ==================== difficulty_live_contamination ====================

from sr_od.application.currency_war.sim.checks.corpus import (
    check_difficulty_curve_live_contamination as chk,
)


def _row(ed: int | None, live: bool | None, rnd: int = 1) -> dict:
    d: dict = {'plane': 1, 'round_num': rnd, 'enemy_difficulty': ed}
    if live is not None:
        d['enemy_difficulty_live'] = live
    return d


class TestDifficultyLiveContamination:
    def test_mixed_disjoint_sets_violation(self) -> None:
        """live 真值集与 non-live 值集不相交并存 → 污染红(全帧口径判废)。"""
        rows = [_row(8, True, i) for i in range(3)] + \
               [_row(108, False, i) for i in range(3, 6)]
        r = chk(rows)
        assert r['violations'] >= 1
        assert any('污染' in v or '判废' in v for v in r['detail'])

    def test_partial_contamination_overlapping_note(self) -> None:
        """批39:live 与 non-live 并存但值集相交 → 不红,但 mixed_note
        必须披露混帧计数与两组值集(部分污染不再静默放行)。"""
        rows = [_row(8, True, i) for i in range(2)] + \
               [_row(108, False, i) for i in range(2, 3)] + \
               [_row(8, False, i) for i in range(3, 5)]
        r = chk(rows)
        assert r['violations'] == 0
        assert r['mixed_note'] is not None
        assert 'live 2 帧' in r['mixed_note']
        assert 'non-live 3 帧' in r['mixed_note']
        assert r['live_vals'] == [8]
        assert r['nonlive_vals'] == [8, 108]

    def test_missing_flag_schema_violation(self) -> None:
        """有难度读数但缺保真位 → schema 红(历史局调用方豁免)。"""
        rows = [_row(108, None, i) for i in range(5)]
        r = chk(rows)
        assert r['violations'] >= 1

    def test_all_live_green(self) -> None:
        """全 live 真值帧(即使有爬升)→ 0 红(真爬升合法)。"""
        rows = [_row(8 + i, True, i) for i in range(5)]
        assert chk(rows)['violations'] == 0

    def test_overlapping_values_green(self) -> None:
        """live 与 non-live 值集相交 → 0 红(同值兜底无害)。"""
        rows = [_row(8, True, i) for i in range(3)] + \
               [_row(8, False, i) for i in range(3, 6)]
        assert chk(rows)['violations'] == 0

    def test_empty_rows_not_governed(self) -> None:
        """空行 → 不辖 0 红。"""
        assert chk([])['violations'] == 0

    def test_no_reading_not_governed(self) -> None:
        """无难度读数帧 → 不辖 0 红。"""
        rows = [_row(None, True, i) for i in range(3)]
        assert chk(rows)['violations'] == 0


# ==================== difficulty_readchain ====================

from sr_od.application.currency_war.kernel.cw_state import GameState


def _state() -> GameState:
    return GameState(plane=1, round_num=3, hp=80, gold=30,
                     board={'仙舟': 1}, bench=[], shop=[], hp_readable=True)


def test_state_field_default_and_serialize() -> None:
    """GameState 字段默认(False)+ dataclass 全量序列化自带该字段
    (decisions.jsonl 落盘无需白名单——serialize_state 全量语义锁)。"""
    st = _state()
    assert st.enemy_difficulty_live is False

    from sr_od.application.currency_war.telemetry.schema import serialize_state
    d = serialize_state(st)
    assert 'enemy_difficulty_live' in d
    assert d['enemy_difficulty_live'] is False


def test_replay_rebuild_reads_live_field() -> None:
    """cw_replay._rebuild_state 白名单含 enemy_difficulty_live(回放忠实)。"""
    from sr_od.application.currency_war.sim.cw_replay import _rebuild_state
    snap = {'gold': 10, 'hp': 80, 'enemy_difficulty': 125,
            'enemy_difficulty_live': True}
    st = _rebuild_state(snap)
    assert st.enemy_difficulty == 125
    assert st.enemy_difficulty_live is True
