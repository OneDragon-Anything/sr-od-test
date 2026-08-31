"""刷新有效性观测面(shop_refresh;DESIGN.md §2.5/§5-B4,观测自检框架)。

测四类:①判据纯函数 refresh_effective 真值表(全同=未生效嫌疑;未识别槽/
空读=不可判不猜)②shop.py 接线锁(静态:对拍落在 r97 刷后重读点、台账行
参数锁)③两连全同防抖(台账复现计数:首见 L1、再现升 L0)④流纯净锁
(record_defect 只写 defect_ledger,spend_ledger 不被缺陷行污染——消费端
query_spend_ledger 按 SpendUnitRecord 字段解析,缺陷行会被当伪单元误读)。
全部落盘走 tmp_path(测试纪律:不写真实 .debug/)。
"""
import json
from pathlib import Path

from sr_od.application.currency_war.operations.prep.shop import refresh_effective
from sr_od.application.currency_war.telemetry import defects, recorder
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 判据纯函数真值表 =====

def test_refresh_effective_truth_table():
    """集合不等=生效;全同=未生效嫌疑;任一侧含未识别槽('')或空读=None 不猜。"""
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['B', 'A', 'C', 'D', 'E']) is False  # 集合语义:同 5 牌换位=全同(DESIGN §2.5 口径;真刷出同 5 牌是组合级小概率,判据容忍)
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['A', 'B', 'C', 'D', 'E']) is False   # 全同=未生效
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['A', '', 'C', 'D', 'E']) is None     # 刷后读含未识别槽
    assert refresh_effective(['A', 'B', 'C', '', 'E'],
                             ['A', 'B', 'C', 'D', 'E']) is None    # 刷前(plan 帧)含未识别槽
    assert refresh_effective([], ['A', 'B']) is None               # 空读不可判
    assert refresh_effective(['A'], []) is None


# ===== ③ 两连全同防抖(台账复现计数)=====


# ===== ③ 两连全同防抖(台账复现计数)=====

def test_refresh_defect_debounce_l1_then_l0(tmp_path: Path, monkeypatch):
    """同特征(刷前牌名串)首见 L1、第二波再全同升 L0——「连续两次刷新全同
    才确认」的防抖由台账复现计数承载,判据函数只给单波判定。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    names = sorted(['A', 'B', 'C', 'D', 'E'])
    for _ in range(2):
        defects.record_defect(
            'shop_refresh', 'invariant_break',
            expected=f'刷后牌面≠刷前:{names}',
            observed=f'刷新后5牌与刷前全同:{names}',
            plane=1, round_num=3, gap_large=True,
            reader_source='refresh_set_compare')
    sevs = [r['severity'] for r in _rows(tmp_path, 'defect_ledger.jsonl')]
    assert sevs == ['L1_alert', 'L0_andon']


# ===== ④ 流纯净锁 =====

def test_record_defect_does_not_pollute_spend_ledger(tmp_path: Path, monkeypatch):
    """缺陷台账行只进 defect_ledger 一条流:spend_ledger 是原始证据层
    (消费端按单元框架字段解析),缺陷行混入会被当伪单元误读。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    defects.record_defect('shop_refresh', 'invariant_break', 'a', 'b')
    assert len(_rows(tmp_path, 'defect_ledger.jsonl')) == 1
    assert not (tmp_path / 'spend_ledger.jsonl').exists()


from sr_od.application.currency_war.telemetry import state
