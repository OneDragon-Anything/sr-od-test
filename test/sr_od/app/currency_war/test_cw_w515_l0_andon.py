"""W515:分级安灯 L0 自动停线(观测缺陷面;用户裁决「确认缺陷即停实机」)。

接线点 = cw_telemetry 模块级 record_defect 判级后(两类旁路 + 显式调用
的收敛点);游戏侧三要素执行在 cw_observe.stop_for_l0_andon。测五类:
①首见 L0 停一次 + run_id 闩锁(跨局重置)②L1/L2 永不停 ③auto_resolved
不停 ④flag 三要素内容锁(含游戏侧执行器端到端)⑤接线存在性源码锁。
全落盘走 tmp_path(测试纪律:不写真实 .debug/);安灯执行器逐测试注入
假实现,不触真机。
"""
import json
from pathlib import Path

from sr_od.application.currency_war.telemetry import cw_telemetry
from sr_od.application.currency_war.kernel import cw_observe


def _setup(monkeypatch, tmp_path: Path, run_id: str = 'w515t') -> list[dict]:
    """recorder/run_id/闩锁指向测试态;注入假执行器收集触发载荷。返回调用记录。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        cw_telemetry.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', run_id)
    # 复现计数与闩锁都是进程内状态,逐测试清空防串
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_FIRED_RUNS', set())
    calls: list[dict] = []

    def _fake_handler(payload: dict) -> bool:
        calls.append(payload)
        return True

    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_HANDLER', _fake_handler)
    return calls


def _rows(tmp_path: Path, name: str = 'defect_ledger.jsonl') -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 首见 L0 停一次 + 闩锁 =====

def test_first_l0_stops_once_then_latch(tmp_path: Path, monkeypatch):
    """同特征金面大 gap 三连:首见 L1 不停 → 第 2 次 L0 停一次 → 第 3 次
    L0 只补台账不再停(局级闩锁)。台账行数=3(停线不改记录形状)。"""
    calls = _setup(monkeypatch, tmp_path)
    for _ in range(3):
        cw_telemetry.record_defect('gold', 'perception_conflict',
                                   'gold_delta: 45', '20', gap=-25.0,
                                   gap_large=True)
    sevs = [r['severity'] for r in _rows(tmp_path)]
    assert sevs == ['L1_alert', 'L0_andon', 'L0_andon']   # 台账照记(补台账)
    assert len(calls) == 1                                 # 只停一次
    assert calls[0]['surface'] == 'gold'
    assert calls[0]['run_id'] == 'w515t'
    assert calls[0]['expected'] == 'gold_delta: 45'
    assert calls[0]['refs'] == []                          # 无 refs 安全缺省


def test_latch_key_is_run_id_resets_next_run(tmp_path: Path, monkeypatch):
    """闩锁键 = run_id:start_run 每局重生成 run_id → 新局首见 L0 再停
    (复现计数同款按 run 切换语义,无手动清)。"""
    calls = _setup(monkeypatch, tmp_path, run_id='run_a')
    cw_telemetry.record_defect('gold', 'perception_conflict',
                               'x: 1', '2', gap=20.0, gap_large=True)
    cw_telemetry.record_defect('gold', 'perception_conflict',
                               'x: 1', '2', gap=20.0, gap_large=True)
    assert len(calls) == 1
    # 新局:换 run_id(生产由 start_run 做;复现计数随之重置)
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'run_b')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    cw_telemetry.record_defect('gold', 'perception_conflict',
                               'x: 1', '2', gap=20.0, gap_large=True)
    cw_telemetry.record_defect('gold', 'perception_conflict',
                               'x: 1', '2', gap=20.0, gap_large=True)
    assert len(calls) == 2
    assert calls[1]['run_id'] == 'run_b'


# ===== ② L1/L2 永不停 =====

def test_l1_and_l2_never_stop(tmp_path: Path, monkeypatch):
    """L1(关键面大 gap 单次)/L2(非关键面)只落台账,执行器零调用。"""
    calls = _setup(monkeypatch, tmp_path)
    cw_telemetry.record_defect('gold', 'perception_conflict',
                               'gold: 200', '230', gap=30.0,
                               gap_large=False)            # 小 gap → L2(特征异于下行,防复现误并)
    cw_telemetry.record_defect('gold', 'perception_conflict',
                               'gold_delta: 45', '20', gap=-25.0,
                               gap_large=True)             # 关键面大gap首见 → L1
    cw_telemetry.record_defect('confidence', 'perception_conflict',
                               'c: 0.9', '0.1', gap_large=True)   # 非关键面 → L2
    sevs = [r['severity'] for r in _rows(tmp_path)]
    assert sevs == ['L2_record', 'L1_alert', 'L2_record']
    assert calls == []


# ===== ③ auto_resolved 永不停 =====

def test_auto_resolved_never_stops(tmp_path: Path, monkeypatch):
    """裁决已自动的冲突面(auto_resolved)复现也不升 L0 → 不停
    (判据单一源在 judge_severity,接线处不双保险)。"""
    calls = _setup(monkeypatch, tmp_path)
    for _ in range(3):
        cw_telemetry.record_defect('deployed', 'perception_conflict',
                                   'deployed_align: 4', '5',
                                   gap_large=True, auto_resolved=True)
    assert all(r['severity'] == 'L2_record' for r in _rows(tmp_path))
    assert calls == []


# ===== ④ flag 三要素内容锁(含游戏侧执行器端到端)=====

def test_flag_three_element_content_lock(tmp_path: Path):
    """flag 自描述内容锁:HOOK-STOP 特征行 + 发生了什么 + 定位/期望/观测/
    台账 refs + 处理步骤 + 删除条件,值班者不看代码即知发生了什么。"""
    fp = tmp_path / 'l0_andon_hook.flag'
    content = cw_telemetry.write_l0_andon_flag(
        fp, run_id='run_x', surface='gold', kind='perception_conflict',
        expected='gold_delta: 45', observed='20',
        plane=1, round_num=3,
        refs=[{'stream': 'obs_conflicts', 'key': 'field=gold_delta|ts=2026'}],
        defect_shot='obs_conflict_gold__ab12.png',
        stop_shot='l0_andon_run_x_p1r3_stop_1.png')
    assert fp.exists()
    assert '[HOOK-STOP]' in content
    assert 'L0 分级安灯停线' in content
    assert '发生了什么' in content and '复现' in content
    assert 'run_id=run_x surface=gold kind=perception_conflict p1r3' in content
    assert '期望:gold_delta: 45' in content
    assert '观测:20' in content
    assert 'obs_conflicts:field=gold_delta|ts=2026' in content
    assert 'obs_conflict_gold__ab12.png' in content           # 缺陷自带 shot 进 refs 面
    assert 'l0_andon_run_x_p1r3_stop_1.png' in content        # 停机现场帧
    assert '处理步骤' in content and '重启' in content
    assert '删除条件' in content and '本 flag 处理完即删' in content


class _FakeRunContext:
    def __init__(self):
        self.reasons: list[str] = []

    def stop_running(self, reason: str = '') -> None:
        self.reasons.append(reason)


class _FakeCtx:
    def __init__(self):
        self.run_context = _FakeRunContext()


def test_game_side_executor_end_to_end(tmp_path: Path, monkeypatch):
    """cw_observe.stop_for_l0_andon 端到端(假 ctx):现场帧 → flag 落
    tmp_path → run_context.stop_running(reason=hook:cw_l0_andon) → True。"""
    ctx = _FakeCtx()
    monkeypatch.setattr(cw_observe, 'find_running_ctx', lambda: ctx)
    monkeypatch.setattr(cw_observe, '_save_andon_frame',
                        lambda c, p: 'l0_andon_run_x_p1r3_stop_1.png')
    monkeypatch.setattr(cw_telemetry, 'l0_andon_flag_path',
                        lambda: tmp_path / 'l0_andon_hook.flag')
    ok = cw_observe.stop_for_l0_andon({
        'run_id': 'run_x', 'surface': 'gold', 'kind': 'perception_conflict',
        'expected': 'gold_delta: 45', 'observed': '20',
        'plane': 1, 'round_num': 3, 'shot': 'obs_conflict_gold__ab12.png',
        'refs': [{'stream': 'obs_conflicts', 'key': 'field=gold_delta'}],
    })
    assert ok is True
    assert ctx.run_context.reasons == ['hook:cw_l0_andon']
    content = (tmp_path / 'l0_andon_hook.flag').read_text(encoding='utf-8')
    assert '[HOOK-STOP]' in content and 'run_id=run_x' in content


def test_game_side_executor_no_ctx_is_no_stop(tmp_path: Path, monkeypatch):
    """找不到 ctx(离线/测试进程)→ False 不停、不写 flag
    (零误停偏置:无停线通道时不动台账以外的任何状态)。"""
    monkeypatch.setattr(cw_observe, 'find_running_ctx', lambda: None)
    monkeypatch.setattr(cw_telemetry, 'l0_andon_flag_path',
                        lambda: tmp_path / 'l0_andon_hook.flag')
    ok = cw_observe.stop_for_l0_andon({'run_id': 'run_x', 'surface': 'gold',
                                       'kind': 'perception_conflict',
                                       'expected': 'e', 'observed': 'o'})
    assert ok is False
    assert not (tmp_path / 'l0_andon_hook.flag').exists()


# ===== ⑤ 接线存在性源码锁 =====

def test_wiring_existence_source_lock():
    """静态锁:模块级 record_defect 判级后必须接 _fire_l0_andon 且只认
    显式 L0_andon;防后续重构静默断链或放宽触发条件。"""
    src = Path(cw_telemetry.__file__).read_text(encoding='utf-8')
    assert 'if sev == SEVERITY_L0_ANDON:' in src
    assert src.count('_fire_l0_andon({') == 1   # 触发点唯一(收敛在判级后)
    assert 'def _fire_l0_andon' in src
    assert 'def set_l0_andon_handler' in src
    assert '_L0_ANDON_FIRED_RUNS' in src        # 局级闩锁在
    # 游戏侧三要素执行器在 cw_observe(判定/执行分层不倒挂)
    obs_src = Path(cw_observe.__file__).read_text(encoding='utf-8')
    assert 'def stop_for_l0_andon' in obs_src
    assert "stop_running(reason='hook:cw_l0_andon')" in obs_src
