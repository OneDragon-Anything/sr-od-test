"""test_cw_run_terminal_summary 主题锁(删除波 1 重写)。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件。

删除波 1(用户 2026-09-10 直迁裁定)重写:runs 流写入端(outcomes 收口终局
行 T-185 件/防重门/runs summary 行)整段退役——本文件原辖的行面锁随写端
消亡,收口位的现役语义 = 零落盘置跨局 run_id 重铸位(telemetry.state.close_run)
+ 局终旁路面保留(cw4 计数快照/BoardState 归档/档案装配)。保留锁:

- 结算词汇 normalizer(读面);
- 收口位行为(真局守卫/幂等/after_operation_done 接线/档案装配连带);
- 退役锁(写点符号不存在,防半删)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.operations.cw_loop import CwLoop


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


# ===== 收口位(删除波 1 后 = close_run 零落盘 + 旁路面)=====
# (2026-09-03 瘦身批:test_table_written_on_first_frame 删除——测试体自建
#  slots 自己排序断言自己,零生产代码触达(纪律 10)。)

def _make_stop_loop(*, summary_written: bool = False,
                    last_outcome_hp: int | None = 30,
                    rounds_done: int = 3,
                    stopped: bool = True,
                    plane: int = 2, round_num: int = 7, hp: int = 100,
                    hp_readable: bool = False) -> CwLoop:
    """构造 loop 桩(bypass __init__):喂 _write_terminal_summary_if_needed 依赖面。

    last_state.hp=100 + hp_readable=False = 死局兜底污染面(ADR-0282 语义)。
    """
    from sr_od.application.currency_war.operations import cw_loop as bl

    class _Loop(bl.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            self.op_name = '收口桩loop'
            self.op_callback = None   # 基类 after_operation_done 尾部读取
            self._summary_written = summary_written
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


def test_stop_closure_sets_marker_zero_writes(monkeypatch, tmp_path) -> None:
    """stop 收口(重写):置收口位(_RUN_CLOSED)且 runs/outcomes 零文件产出。"""
    import sr_od.application.currency_war.telemetry.state as tel
    from sr_od.application.currency_war.telemetry.recorder import (
        TelemetryRecorder,
    )
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_stop_1')
    monkeypatch.setattr(tel, '_RUN_CLOSED', False)
    monkeypatch.setattr(tel, '_RUN_MATCH', None)
    monkeypatch.setattr(tel, '_RECORDER',
                        TelemetryRecorder(replay_dir=tmp_path, enabled=True))
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    assert tel._RUN_CLOSED is True, '收口位在(跨局 run_id 重铸承接口)'
    assert not (tmp_path / 'runs.jsonl').exists(), \
        'runs 写入端已退役:收口零落盘'
    assert not (tmp_path / 'outcomes.jsonl').exists(), \
        'outcomes 写入端已退役:收口零落盘'
    assert op._summary_written


def test_stop_summary_skips_true_fake_run(monkeypatch, tmp_path) -> None:
    """真·假局守卫(P4R4 语义,删除波 1 后照常):从未观察到对局态
    (last_state 缺失)且零 outcome = 开局即失败 → 不走收口。"""
    import sr_od.application.currency_war.telemetry.state as tel
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ghost_1')
    monkeypatch.setattr(tel, '_RUN_CLOSED', False)
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
    assert op._summary_written is False, '真假局不置收口位(污染分母防线)'


def test_stop_summary_no_duplicate_on_second_call(monkeypatch, tmp_path) -> None:
    """幂等:同实例二次调用(收口重入/守护)不重复收口。"""
    import sr_od.application.currency_war.telemetry.state as tel
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_stop_2')
    monkeypatch.setattr(tel, '_RUN_CLOSED', False)
    monkeypatch.setattr(tel, '_RUN_MATCH', None)
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    op._write_terminal_summary_if_needed()
    assert tel._RUN_CLOSED is True
    assert not (tmp_path / 'runs.jsonl').exists()


def test_after_operation_done_wires_closure(monkeypatch, tmp_path) -> None:
    """收口接线行为锁(重写):after_operation_done 真调收口位(execute()
    全路径必达位,成功/失败/停止三路共达)。失守事故 = MCP stop 后 loop()
    不再被调([RUNS-GAP] 哨兵四局连报史实)——本锁红 = 接线再次脱落。"""
    import sr_od.application.currency_war.telemetry.state as tel
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_wire_1')
    monkeypatch.setattr(tel, '_RUN_CLOSED', False)
    monkeypatch.setattr(tel, '_RUN_MATCH', None)
    op = _make_stop_loop()
    op.after_operation_done(SimpleNamespace(success=True, status='测试收口'))
    assert tel._RUN_CLOSED is True, '收口位经 after_operation_done 到达'
    assert not (tmp_path / 'runs.jsonl').exists()


def test_terminal_summary_triggers_archive_assemble(monkeypatch, tmp_path) -> None:
    """收口连带按局存档装配(行为锁;P4R4 出处:非正常终局此前只在 3c 装配
    → 对局档案缺该局,run_20260903_004418 实证)——spy 装配入口,红 = 装配
    连带脱落。"""
    import sr_od.application.currency_war.telemetry.state as tel
    from sr_od.application.currency_war.telemetry import match_archive
    from sr_od.application.currency_war.telemetry.recorder import (
        TelemetryRecorder,
    )
    calls: list = []
    monkeypatch.setattr(match_archive, 'assemble_pending',
                        lambda replay_dir: calls.append(replay_dir))
    monkeypatch.setattr(tel, '_RECORDER',
                        TelemetryRecorder(replay_dir=tmp_path, enabled=True))
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_asm_1')
    monkeypatch.setattr(tel, '_RUN_CLOSED', False)
    monkeypatch.setattr(tel, '_RUN_MATCH', None)
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    assert calls == [tmp_path]


# ===== T-185 收口终局行(删除波 1 退役)=====
# 原病灶(末轮无结算行→档案不可判)的写端面(outcomes 行/防重门)随
# outcomes 流写入端退役;结算真值现役归宿 = BoardState settlement 域
# apply_settlement_cover,局终收口形态归宿 = 局终域 match_final 行
# (写点接线归后续批)。防半删:

def test_terminal_outcome_writer_retired(monkeypatch, tmp_path) -> None:
    """退役锁:收口终局行写点(_write_terminal_outcome_row/_run_has_outcome_at)
    与 TERMINAL_OUTCOME_SOURCE 常量不存在(防半删);收口跑完零 outcomes 产出。"""
    op = _make_stop_loop()
    assert not hasattr(op, '_write_terminal_outcome_row')
    assert not hasattr(op, '_run_has_outcome_at')
    assert not hasattr(type(op), 'TERMINAL_OUTCOME_SOURCE')
    import sr_od.application.currency_war.telemetry.state as tel
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ret_1')
    monkeypatch.setattr(tel, '_RUN_CLOSED', False)
    monkeypatch.setattr(tel, '_RUN_MATCH', None)
    op._write_terminal_summary_if_needed()
    assert not (tmp_path / 'outcomes.jsonl').exists()
