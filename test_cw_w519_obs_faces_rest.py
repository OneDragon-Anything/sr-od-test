"""观测自检框架剩余三面(bench 买牌落位/结算 vs 备战 round/节点序列互证;
DESIGN.md §2.2/§2.7/§1 行11+§5-B5,观测自检框架)。

测四类:①§2.2 判据纯函数真值表(占位不出现=硬失败;计数=买牌数−卖出数;
身份回读=留证非失败,空读不猜)②§2.11 节点序列互证纯函数真值表(仅双方
已识别位可比;空序列/无可比位=不可判)③三面接线锁(静态:判据必须接在
动作记录点、台账行参数锁——防后续重构静默断链或改口径)④§2.7 裁决已自动
恒 L2 的分级锁(auto_resolved 路径)。全部落盘走 tmp_path(测试纪律)。
"""
import json
from pathlib import Path

from sr_od.application.currency_war import cw_telemetry
from sr_od.application.currency_war.operations.handlers.collect_plane_intel import (
    node_seq_cross_mismatch,
)
from sr_od.application.currency_war.operations.prep.shop import (
    bench_buy_count_ok,
    bench_buy_identity_missing,
    bench_buy_occupancy_ok,
)


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① §2.2 买牌落位判据真值表 =====

def test_bench_buy_occupancy_truth_table():
    """占位判据:买≥1 张而新槽=0 = 硬失败(设计点名「占位不出现才算失败」);
    有新槽 = 通过;未买牌 = None 不判。"""
    assert bench_buy_occupancy_ok(2, 0) is False
    assert bench_buy_occupancy_ok(1, 1) is True
    assert bench_buy_occupancy_ok(3, 2) is True   # 计数差归计数判据,占位已满足
    assert bench_buy_occupancy_ok(0, 0) is None
    assert bench_buy_occupancy_ok(0, 5) is None


def test_bench_buy_count_truth_table():
    """计数总账:新槽 = 买牌数 − 中途卖出数(设计 §2.2 原文口径);
    未买牌 = None 不判。"""
    assert bench_buy_count_ok(2, 2, 0) is True
    assert bench_buy_count_ok(2, 1, 0) is False
    assert bench_buy_count_ok(2, 1, 1) is True
    assert bench_buy_count_ok(3, 0, 0) is False
    assert bench_buy_count_ok(0, 0, 0) is None


def test_bench_buy_identity_missing_semantics():
    """身份回读=留证清单非失败判据(设计明示);回读空=SIFT 整帧失读
    → None 不猜;两侧均为规范名 → 全等匹配。"""
    assert bench_buy_identity_missing(['A', 'B'], ['A', 'C']) == ['B']
    assert bench_buy_identity_missing(['A', 'B'], ['B', 'A', 'X']) == []
    assert bench_buy_identity_missing(['A'], []) is None
    assert bench_buy_identity_missing([], ['A']) is None


# ===== ② §2.11 节点序列互证判据真值表 =====

def test_node_seq_cross_mismatch_truth_table():
    """仅双方已识别位可比;空序列/无可比位 = None 不可判;一致 = []。"""
    assert node_seq_cross_mismatch(['battle', 'reward', None],
                                   ['encounter', 'reward', None]) == [0]
    assert node_seq_cross_mismatch(['battle', 'reward'],
                                   ['battle', 'reward']) == []
    assert node_seq_cross_mismatch(['battle', None, 'reward'],
                                   ['battle', 'supply', 'reward']) == []  # 未识别位跳过
    assert node_seq_cross_mismatch([], ['battle']) is None
    assert node_seq_cross_mismatch(['battle'], []) is None
    assert node_seq_cross_mismatch([None, None], ['battle', 'reward']) is None  # 无可比位


# ===== ③ 三面接线锁(静态结构)=====

def test_w519_wiring_locks():
    """三面对拍必须接在既有动作记录点、台账行锁关键参数(防重构断链):
    ① bench 落位对拍在买后 pixel-diff 点后(bench_buy_* + reader_source);
    ② 结算 vs 备战 round 对拍在 parse_settlement_round 门后(residual 分支外,
    裁决已自动 auto_resolved=True);
    ③ 节点序列互证消费在采集循环详情条读出点(prep_vs_plane_detail_seq)。"""
    root = Path('src/sr_od/application/currency_war')
    shop = (root / 'operations/prep/shop.py').read_text(encoding='utf-8')
    tail = shop[shop.index('new_bench_slots(self.ctx, _buy_baseline'):]
    assert "'bench', 'invariant_break'" in tail
    assert 'bench_buy_occupancy_ok(' in tail
    assert 'bench_buy_count_ok(' in tail
    assert 'bench_buy_identity_missing(' in tail
    assert 'bench_buy_pixel_diff' in tail
    assert 'bench_buy_sift_readback' in tail
    assert 'identify_slots(' in tail   # SIFT 纯读路径(绕开 read_bench_chars 的停机钩子)
    assert 'read_bench_chars(' not in tail

    loop = (root / 'operations/battle_loop.py').read_text(encoding='utf-8')
    gate = loop[loop.index('parse_settlement_round(_ocr_texts)'):]
    assert gate.count("'phase_round', 'perception_conflict'") == 2   # 采新侧 + 拒信侧
    assert gate.count('settlement_vs_prep_round') == 2
    assert gate.count('auto_resolved=True') >= 2
    assert "'phase_round', 'perception_conflict'" not in loop[:loop.index('parse_settlement_round(_ocr_texts)')]  # 残留屏分支不落行

    intel = (root / 'operations/handlers/collect_plane_intel.py').read_text(encoding='utf-8')
    assert 'node_seq_cross_mismatch(' in intel
    assert 'prep_vs_plane_detail_seq' in intel
    assert "_cross_check_node_seq(_detail_slots)" in intel
    assert "'node_seq', 'perception_conflict'" in intel


# ===== ④ §2.7 分级锁:裁决已自动恒 L2 =====

def test_settlement_round_defect_auto_resolved_is_l2(tmp_path: Path, monkeypatch):
    """同轮双读不等的裁决已自动(采新/单调门拒)→ 按分级标准恒 L2,
    不进 L1/L0(与 streak 双源等「裁决已自动」同族)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        cw_telemetry.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    cw_telemetry.record_defect(
        'phase_round', 'perception_conflict',
        expected='备战缓存 1-6', observed='结算屏 1-7',
        plane=1, round_num=6,
        reader_source='settlement_vs_prep_round', auto_resolved=True)
    rows = _rows(tmp_path, 'defect_ledger.jsonl')
    assert len(rows) == 1
    assert rows[0]['severity'] == 'L2_record'
