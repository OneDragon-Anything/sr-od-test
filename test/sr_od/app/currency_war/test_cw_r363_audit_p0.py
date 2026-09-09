# -*- coding: utf-8 -*-
"""test_cw_r363_audit_p0 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations



from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.telemetry.query import read_jsonl
from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder


def test_normalize_node_type_vocab() -> None:
    """三源词汇统一:英文 token/OCR 中文/旧兜底 → EXPECTED_DROP 键域中文。

    (W971 05-battle §1 P4:词汇 normalizer 随结算链收编进 CwScreenBattleWait。)
    """
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
        CwScreenBattleWait,
    )
    n = CwScreenBattleWait._normalize_node_type
    assert n('battle') == '普通战斗'
    assert n('reward') == '奖励'
    assert n('encounter') == '遭遇'
    assert n('supply') == '补给'
    assert n('boss') == 'boss'
    assert n('megastar') == '巨星'
    assert n('奖励') == '奖励'
    assert n('首领') == 'boss'
    assert n('普通战斗') == '普通战斗'
    assert n('') == '普通战斗'
    assert n(None) == '普通战斗'
    assert n('未知类型') == '未知类型'   # 未知透传不吞


# ===== W75(ADR-0335):stop 路径 runs summary 收口(治本 r363 死码) =====
# (2026-09-03 瘦身批:test_table_written_on_first_frame 删除——测试体自建
#  slots 自己排序断言自己,零生产代码触达(纪律 10)。)

def _make_stop_loop(*, summary_written: bool = False,
                    last_outcome_hp: int | None = 30,
                    rounds_done: int = 3,
                    stopped: bool = True,
                    plane: int = 2, round_num: int = 7, hp: int = 100,
                    hp_readable: bool = False) -> CwLoop:
    """构造 loop 桩(bypass __init__):喂 _write_terminal_summary_if_needed 依赖面。

    last_state.hp=100 + hp_readable=False = 死局兜底污染面(ADR-0282 语义),
    收口应取 outcome 真值(_last_outcome_hp)而非 100。
    """
    from sr_od.application.currency_war.operations import cw_loop as bl

    class _Loop(bl.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            self.op_name = '收口桩loop'
            self.op_callback = None   # 基类 after_operation_done 尾部读取
            self._summary_written = summary_written
            # (W971 05-battle §1 P4:hp/轮计数真值源收编进 SettlementState,
            #  收口经 self._settle 读——桩同形。)
            self._settle = SimpleNamespace(
                last_outcome_hp=last_outcome_hp, rounds_done=rounds_done)
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(
                        last_state=GameState(plane=plane, round_num=round_num,
                                             hp=hp, hp_readable=hp_readable),
                    ),
                ),
                run_context=SimpleNamespace(is_context_stop=stopped),
                # 基类 after_operation_done 会调 ctx.unlisten_all_event(self)
                # (事件监听清理);SimpleNamespace 桩补 no-op 满足该依赖面。
                unlisten_all_event=lambda *_a, **_k: None,
            )

    return _Loop()


def test_stop_path_writes_stopped_summary(monkeypatch, tmp_path) -> None:
    """stop 收口:构造 run 上下文 → stop → runs 行存在且 result='stopped'。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_stop_1')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1
    s = rows[0]
    assert s['result'] == 'stopped'
    assert s['run_id'] == 'run_stop_1'
    assert s['plane_reached'] == 2
    assert s['rounds_survived'] == 7
    assert s['final_hp'] == 30   # outcome 真值,非 last_state 100 兜底
    assert op._summary_written


def test_non_stop_abnormal_exit_writes_abandoned(monkeypatch, tmp_path) -> None:
    """非 stop 异常退出(超时/FAIL,is_context_stop=False)→ result='abandoned'。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_fail_1')
    op = _make_stop_loop(stopped=False, last_outcome_hp=55,
                         plane=3, round_num=2, hp=55, hp_readable=True)
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1
    assert rows[0]['result'] == 'abandoned'
    assert rows[0]['final_hp'] == 55


def test_zero_outcome_but_observed_writes_row(monkeypatch, tmp_path) -> None:
    """P4R4 假局守卫语义修正:零 outcome 但观察过对局态 = **真局** → 必写
    终局行(run_20260903_004418 超时 fail / run_20260903_204908 stop 两实例
    runs 缺行根因:部署死循环阶段零结算行被旧守卫当假局吞掉)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_zeroutcome_1')
    op = _make_stop_loop(last_outcome_hp=None, rounds_done=0,
                         stopped=False, plane=1, round_num=2, hp=100)
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1
    assert rows[0]['result'] == 'abandoned'
    assert rows[0]['plane_reached'] == 1 and rows[0]['rounds_survived'] == 2
    assert op._summary_written


def test_stop_summary_skips_true_fake_run(monkeypatch, tmp_path) -> None:
    """真·假局守卫(P4R4 新语义):从未观察到对局态(last_state 缺失)
    且零 outcome = 开局即失败 → 不写假 summary(镜像 3c 污染分母防线)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ghost_1')
    from sr_od.application.currency_war.operations import cw_loop as bl

    class _GhostLoop(bl.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass __init__
            self._summary_written = False
            self._settle = SimpleNamespace(
                last_outcome_hp=None, rounds_done=0)
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(session=None),
                run_context=SimpleNamespace(is_context_stop=True),
            )

    op = _GhostLoop()
    op._write_terminal_summary_if_needed()
    assert read_jsonl(tmp_path / 'runs.jsonl') == []


def test_stop_summary_no_duplicate_on_second_call(monkeypatch, tmp_path) -> None:
    """幂等:同实例二次调用(收口重入/守护)不重复写行。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_stop_2')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    op._write_terminal_summary_if_needed()
    assert len(read_jsonl(tmp_path / 'runs.jsonl')) == 1


def test_after_operation_done_wires_summary_write(monkeypatch, tmp_path) -> None:
    """收口接线行为锁:after_operation_done 真调收口(execute() 全路径必达位,
    成功/失败/停止三路共达)。失守事故 = MCP stop 后 loop() 不再被调,
    runs 缺行([RUNS-GAP] 哨兵四局连报,生产 cw_loop.after_operation_done
    docstring 实锤)——本锁红 = 接线再次脱落。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_wire_1')
    op = _make_stop_loop()
    op.after_operation_done(SimpleNamespace(success=True, status='测试收口'))
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1 and rows[0]['result'] == 'stopped'


def test_terminal_summary_triggers_archive_assemble(monkeypatch, tmp_path) -> None:
    """补写收口连带按局存档装配(行为锁;P4R4 出处:非正常终局的 runs 行
    此前没有装配机会 → 对局档案缺该局,run_20260903_004418 实证)——
    spy 装配入口,红 = 装配连带脱落。"""
    import sr_od.application.currency_war.telemetry.state as tel
    from sr_od.application.currency_war.telemetry import match_archive
    calls: list = []
    monkeypatch.setattr(match_archive, 'assemble_pending',
                        lambda replay_dir: calls.append(replay_dir))
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_asm_1')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    assert calls == [tmp_path]


# ===== T-185:收口终局结算行(outcomes 末轮 outcome 采集补全) =====
# 病灶:result=stopped 局末轮无结算行 → 档案末轮 outcome=null → batch_stats
# 通关权威口径 killed(ADR-0306 件3)落不可判桶。写点 = 收口
# (_write_terminal_summary_if_needed)内 _write_terminal_outcome_row。

def _terminal_rows(tmp_path, run_id: str) -> list[dict]:
    from sr_od.application.currency_war.telemetry.query import read_jsonl
    return [r for r in read_jsonl(tmp_path / 'outcomes.jsonl')
            if r.get('run_id') == run_id]


def test_stop_closure_writes_terminal_outcome_row(monkeypatch, tmp_path) -> None:
    """stop 收口补写末轮终局行:字段齐且不发任何战斗/hp 真值(killed=False
    为对局级终了真值;hp/conf/progress/streak/node_type 全空防冒认)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_term_1')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    rows = _terminal_rows(tmp_path, 'run_term_1')
    assert len(rows) == 1
    r = rows[0]
    assert (r['plane'], r['round_num']) == (2, 7)   # last_state 键
    assert r['killed'] is False                     # 对局级:终了时未通关
    assert r['hp_after'] is None                    # 不冒认 hp 真值
    assert r['hp_confidence'] == 0.0                # 显式不可信(防可信门放行)
    assert r['progress_delta'] is None and r['streak'] is None
    assert r['node_type'] == ''                     # 不冒认节点型(读端回落帧)
    assert r['source'] == op.TERMINAL_OUTCOME_SOURCE
    assert r['match_result'] == 'stopped'
    # 档案 E2E 手写 fixture(test_cw_telemetry_archive 终局行)消费键对账锚
    #(落地审建议-5③):生产行必须至少携带该键集,生产写端形状漂移时
    # 两侧(本锁与档案 E2E)同步红。
    assert {'plane', 'round_num', 'ts', 'killed', 'source', 'match_result',
            'node_type', 'hp_after', 'hp_confidence'} <= set(r.keys())


def test_terminal_row_precedes_runs_row(monkeypatch, tmp_path) -> None:
    """承载性次序锁(落地审建议-5①):终局行 ts ≤ runs 行 ts——档案装配按
    start_ts ≤ ts ≤ end_ts 切窗,终局行若晚于 runs 行(ts 超 end_ts)会被
    切出档案,T-185 静默失效(同秒粒度下由写点先后保证)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    from sr_od.application.currency_war.telemetry.query import read_jsonl
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ord_1')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    oc_rows = _terminal_rows(tmp_path, 'run_ord_1')
    run_rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(oc_rows) == 1 and len(run_rows) == 1
    assert oc_rows[0]['ts'] <= run_rows[0]['ts']


def test_run_has_outcome_at_fails_closed_on_read_error(monkeypatch, tmp_path) -> None:
    """防重门 fail 方向锁(落地审建议-1 裁决:宁缺勿污):文件级读失败
    视同「键已有行」返回 True 不补——误放行会让终局行以 ts 末行身份覆盖
    既有 killed 真值(恶性);缺行只是回到不可判(良性,方向不对称)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_failclosed_1')
    op = _make_stop_loop()
    (tmp_path / 'outcomes.jsonl').mkdir()   # 文件位被目录占位 = 文件级读必失败
    assert op._run_has_outcome_at(2, 7) is True


def test_run_has_outcome_at_tolerates_torn_tail_line(monkeypatch, tmp_path) -> None:
    """撕裂行容错锁(落地审建议-1 伴生):append 尾行撕裂(半写 JSON)不使
    整读抛异常——既有键行照常命中(门不失能),无键行时放行补行(功能保留)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_torn_1')
    op = _make_stop_loop()
    # 键行在前 + 尾行撕裂(生产 append 崩溃的半写形态)
    (tmp_path / 'outcomes.jsonl').write_text(
        '{"run_id": "run_torn_1", "plane": 2, "round_num": 7}\n'
        '{"run_id": "run_torn_1", "plane": 2', encoding='utf-8')
    assert op._run_has_outcome_at(2, 7) is True    # 坏行不挡键行命中
    # 仅它轮行 + 尾行撕裂,无本键行 → 放行
    (tmp_path / 'outcomes.jsonl').write_text(
        '{"run_id": "run_torn_1", "plane": 2, "round_num": 6}\n'
        '{"torn', encoding='utf-8')
    assert op._run_has_outcome_at(2, 7) is False


def test_abandoned_closure_carries_match_result(monkeypatch, tmp_path) -> None:
    """非 stop 异常退出收口 → 终局行 match_result='abandoned'。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_term_2')
    op = _make_stop_loop(stopped=False)
    op._write_terminal_summary_if_needed()
    rows = _terminal_rows(tmp_path, 'run_term_2')
    assert len(rows) == 1 and rows[0]['match_result'] == 'abandoned'


def test_terminal_row_skipped_when_key_already_settled(monkeypatch, tmp_path) -> None:
    """防重门:末轮键已有本 run 结算行(停止点在结算读取之后,如败局
    多页链/通关结算链中途停)→ 不补行——终局行 ts 更晚会以「ts 末行」
    身份在档案覆盖既有真值行(killed=True/False 被冲成对局级 False)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    from sr_od.application.currency_war.telemetry.query import read_jsonl
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_term_3')
    # 预置:末轮键 (2,7) 已有结算屏真值行(胜利结算 killed=True)
    rec.record_outcome('run_term_3', SimpleNamespace(
        round_num=7, plane=2, node_type='boss', comp_tag='甲',
        intentional_fold=False, hp_after=55, hp_confidence=1.0,
        enemy_hp_after=None, damage_dealt=None, killed=True,
        progress_delta=2, streak=3, match_result=''))
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'outcomes.jsonl')
    assert len(rows) == 1                     # 未补终局行
    assert rows[0]['killed'] is True          # 原真值行原样在档
    assert rows[0]['source'] == ''


def test_terminal_row_skipped_without_last_state(monkeypatch, tmp_path) -> None:
    """last_state 缺失(无键可落)→ 只写 runs summary,不落终局行。"""
    import sr_od.application.currency_war.telemetry.state as tel
    from sr_od.application.currency_war.operations import cw_loop as bl

    class _NoStateLoop(bl.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass __init__
            self.op_name = '收口桩loop'
            self.op_callback = None
            self._summary_written = False
            self._settle = SimpleNamespace(
                last_outcome_hp=30, rounds_done=2)   # 有结算痕迹=真局
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(session=SimpleNamespace(
                    last_state=None)),
                run_context=SimpleNamespace(is_context_stop=True),
                unlisten_all_event=lambda *_a, **_k: None,
            )

    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_term_4')
    op = _NoStateLoop()
    op._write_terminal_summary_if_needed()
    assert len(read_jsonl(tmp_path / 'runs.jsonl')) == 1   # summary 照写
    assert read_jsonl(tmp_path / 'outcomes.jsonl') == []   # 终局行不落
