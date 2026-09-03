"""期望态双通道三缺陷修复锁(P4R4;第六局复盘 §六⑤)。

①pending 清账延迟(owned 已穿不确认 → 跨轮挂账);
②expected_reconcile.jsonl 跨重启截断(append 语义锁 + 项目根绝对路径);
③diff 重复上报(留证后清账 + 同条目去重,重新登记可重报)。
"""
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture()
def rec(tmp_path: Path) -> Any:
    from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
    return TelemetryRecorder(replay_dir=tmp_path, enabled=True)


def _entry(path: str, value, kind: str = 'merge_group',
           produced_by: str = 'BuyCard') -> Any:
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        ExpectedEntry,
    )
    return ExpectedEntry(path=path, value=value, produced_by=produced_by,
                         at_round='p1-r4', kind=kind)


# ==================== ③ 重复上报去重 ====================

def test_duplicate_diff_reported_once_then_cleared() -> None:
    """同条目 mismatch 只留证一次;留证后清账(旧版漏清 → 下轮重复上报);
    重新登记(last-wins 新对象)→ 可重报。"""
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        reconcile_expected,
        register_expected,
    )
    session = SimpleNamespace(expected_state={})
    register_expected(session, _entry('merge_chain[卡芙卡:2->3]', '落点=bench:2'))
    d1 = reconcile_expected(session, 'prep_obs',
                            {'merge_chain[卡芙卡:2->3]': ('落点=bench:9', True)})
    assert len(d1) == 1                       # 首次留证
    d2 = reconcile_expected(session, 'prep_obs',
                            {'merge_chain[卡芙卡:2->3]': ('落点=bench:9', True)})
    assert d2 == []                           # 去重:同条不重报
    # 留证后清账(缺陷③主修:mismatch 条目不再滞留)
    assert 'merge_chain[卡芙卡:2->3]' not in session.expected_state
    # 重新登记(新对象 reported=False)→ 重报通道畅通
    register_expected(session, _entry('merge_chain[卡芙卡:2->3]', '落点=bench:2'))
    d3 = reconcile_expected(session, 'prep_obs',
                            {'merge_chain[卡芙卡:2->3]': ('落点=bench:9', True)})
    assert len(d3) == 1


def test_reported_flag_reset_on_reregister() -> None:
    """重新登记 = last-wins 新对象 → reported 复位 False(可重报语义)。"""
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        register_expected,
    )
    session = SimpleNamespace(expected_state={})
    e1 = _entry('p', 'v1')
    register_expected(session, e1)
    e1.reported = True
    register_expected(session, _entry('p', 'v2'))   # last-wins 覆盖
    e2 = session.expected_state['p']
    assert e2 is not e1 and e2.reported is False


def test_dup_across_windows_single_report(rec) -> None:
    """R4 场景复现锁(第九局复盘):同 expected 条目在两个覆盖窗口
    (间隔多轮、实读更新)各 reconcile → expected_reconcile 只落一行;
    第二窗口静默清账。"""
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        reconcile_expected,
        register_expected,
        set_evidence_sink,
    )
    rows: list[dict] = []
    set_evidence_sink(rows.append)
    try:
        session = SimpleNamespace(expected_state={})
        register_expected(session, _entry('merge_chain[卡芙卡:2->3]', '落点=bench:2'))
        # 窗口 1(p1-r4 备战观察):mismatch 留证(实证行 coverage_point=prep_obs)
        d1 = reconcile_expected(session, 'prep_obs',
                                {'merge_chain[卡芙卡:2->3]': ('落点=bench:9', True)})
        assert len(d1) == 1
        # ……间隔多轮(其他轮次备战观察,同条目反复 mismatch)……
        # 窗口 2:同条目再遇同 mismatch
        d2 = reconcile_expected(session, 'prep_obs',
                                {'merge_chain[卡芙卡:2->3]': ('落点=bench:9', True)})
        assert d2 == []                   # 去重:不再落第二行
        assert 'merge_chain[卡芙卡:2->3]' not in session.expected_state
        assert len(rows) == 1             # 落盘恰好一行(旧形态 = 两行,R4 实证)
    finally:
        set_evidence_sink(None)


def test_reported_dedup_per_entry_not_global() -> None:
    """去重按条目级:同 path 的**其他未上报条目**(不同轮次登记)不受
    已报条目影响,照常留证。"""
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        reconcile_expected,
        register_expected,
    )
    session = SimpleNamespace(expected_state={})
    register_expected(session, _entry('p', 'v1'))
    d1 = reconcile_expected(session, 'prep_obs', {'p': ('实际', True)})
    assert len(d1) == 1
    register_expected(session, _entry('p', 'v2', produced_by='OtherOp'))
    d2 = reconcile_expected(session, 'prep_obs', {'p': ('实际2', True)})
    assert len(d2) == 1                       # 新条目独立留证


# ==================== ① pending 清账延迟(owned 已穿) ====================

def test_owned_entry_confirmed_when_worn() -> None:
    """owned 装备已被穿(owned 移除、deployed equips 在)→ prep_obs 覆盖点
    确认清账(p2r2 拖到 p2r4 的跨轮挂账根因修复)。"""
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        reconcile_expected,
        register_expected,
    )
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        prep_obs_actual_for,
    )
    session = SimpleNamespace(last_owned_equips=[],     # 已被 EquipAll 移出
                              active_strategies=[])
    entry = _entry('owned[光能电池]', '+1(ConfirmSupply)', kind='owned',
                   produced_by='PickBoxCard')
    st = SimpleNamespace(gold=30, xp_progress=None, level=5)
    obs = SimpleNamespace(state_gold_trusted=False, spheres=None,
                          deployed_chars=[BenchChar(slot=1, char_id='希儿',
                                                    star=1, position_pref='front',
                                                    equips=['光能电池'])])
    actual = prep_obs_actual_for(session, entry, st, obs, '', '希儿@1★')
    assert actual is not None and actual[1] is True   # 可信确认(已穿=到账)
    register_expected(session, entry)
    diffs = reconcile_expected(session, 'prep_obs',
                               {'owned[光能电池]': actual})
    assert diffs == []                                 # 到账确认,不 diff
    assert 'owned[光能电池]' not in session.expected_state   # 即清(不再跨轮挂账)


def test_owned_entry_still_pending_when_nowhere() -> None:
    """对照:装备既不在 owned 也没穿(真未到账/识别缺失)→ 条目保留
    (宁缺勿造,不误清)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        prep_obs_actual_for,
    )
    session = SimpleNamespace(last_owned_equips=[], active_strategies=[])
    entry = _entry('owned[光能电池]', '+1(ConfirmSupply)', kind='owned')
    st = SimpleNamespace(gold=30, xp_progress=None, level=5)
    obs = SimpleNamespace(state_gold_trusted=False, spheres=None,
                          deployed_chars=[])
    actual = prep_obs_actual_for(session, entry, st, obs, '', '')
    assert actual == ('光能电池', False)   # trusted False → 覆盖点保留


# ==================== ② append 语义(跨重启不截断) ====================

def test_sink_appends_across_reinstall(tmp_path: Path) -> None:
    """模拟重启:sink 两轮写入(「进程 1」/「进程 2」各建一个 sink 闭包)→
    同文件行数累加不截断(旧 'w' 形态会截成 2 行);追加语义锁防回退。"""
    from sr_od.application.currency_war.decision_assembly import (
        _expected_reconcile_sink_for_test,
    )
    sink1 = _expected_reconcile_sink_for_test(tmp_path)
    sink1({'i': 1})
    sink2 = _expected_reconcile_sink_for_test(tmp_path)   # 「重启」重建
    sink2({'i': 2})
    sink2({'i': 3})
    lines = [ln for ln in
             (tmp_path / 'expected_reconcile.jsonl').read_text(
                 encoding='utf-8').splitlines() if ln]
    assert len(lines) == 3
    assert [json.loads(ln)['i'] for ln in lines] == [1, 2, 3]


def test_reconcile_dir_is_absolute_project_root() -> None:
    """缺陷②主修锁:目录 = 项目根绝对路径(相对 cwd 路径在 server cwd
    漂移进程会把追加写去别处 = 主文件「零新增」假截断)。"""
    from sr_od.application.currency_war.decision_assembly import _reconcile_dir
    d = _reconcile_dir()
    assert d.is_absolute()
    assert str(d).endswith('.debug\\temp\\currency_war') \
        or str(d).endswith('.debug/temp/currency_war')
