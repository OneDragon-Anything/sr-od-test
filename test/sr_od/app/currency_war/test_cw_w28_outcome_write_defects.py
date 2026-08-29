"""W28 行为锁:outcomes 语料两个写入缺陷的修复(W23 定因)。

缺陷①(relaunch 残留结算屏记成 r1):启动宽限内首见结算屏 → 行打
source='recovered' + 按屏面「X-Y」解析真实轮次(修法 a+b 都做)。
缺陷②(补给节点无结算屏零写入):RunSupplyNode 成功完成 → 合成
node_type='补给' 的 outcome 行(source='synthetic_supply',复用
cw_telemetry.record_outcome 单一写入入口)。

纯逻辑/桩测试(monkeypatch 构造 relaunch 首帧场景);不写真实 .debug
(TelemetryRecorder 指向 tmp_path;loop 侧写入端 monkeypatch 捕获)。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.cw_settlement_obs import parse_settlement_round
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.cw_telemetry import TelemetryRecorder, read_jsonl

# ===== 缺陷①修 a:parse_settlement_round 纯函数 =====


def test_parse_round_from_header_window() -> None:
    """头部后 5 token 窗口内的「X-Y」→ (plane, round)(W23 实录 token 形态)。"""
    texts = ['挑战结束', '1-6', '战斗', '小队生命值78i', '继续挑战']
    assert parse_settlement_round(texts) == (1, 6)


def test_parse_round_glued_and_noise_forms() -> None:
    """粘连噪声形态('1-3X点' 实锤)可解析;boss 屏 '1-9首领' 同理。"""
    assert parse_settlement_round(['挑战成功', '1-3X点', '战斗']) == (1, 3)
    assert parse_settlement_round(['挑战结束', '1-9首领']) == (1, 9)


def test_parse_round_rejects_out_of_range_and_far_digits() -> None:
    """值域外(plane>3/round=0)与窗口外数字对 → None(不冒认)。"""
    assert parse_settlement_round(['挑战成功', '4-2']) is None
    assert parse_settlement_round(['挑战成功', '1-0']) is None
    # 窗口外(头部后 >5 token)的数字对不取
    assert parse_settlement_round(
        ['挑战成功'] + ['x'] * 6 + ['1-6']) is None
    # 无头部词 → None(非结算屏帧不解析)
    assert parse_settlement_round(['1-6', '战斗']) is None
    # 紧邻数字的粘连('11-6')不取子串
    assert parse_settlement_round(['挑战成功', '11-6']) is None


# ===== 缺陷①:OutcomeRecord.source 字段(schema 末尾追加,可选) =====


def test_record_outcome_source_field_roundtrip(tmp_path) -> None:
    """recorder.record_outcome(source=...) 落盘;默认 ''(旧 schema 兼容)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.record_outcome('r1', RoundOutcome(round_num=5, plane=1, node_type='补给',
                                          comp_tag='c', hp_after=77, killed=True),
                       source='synthetic_supply')
    rec.record_outcome('r1', RoundOutcome(round_num=6, plane=1, node_type='普通战斗',
                                          comp_tag='c', hp_after=78))
    lines = read_jsonl(tmp_path / 'outcomes.jsonl')
    assert lines[0]['source'] == 'synthetic_supply'
    assert lines[1]['source'] == ''


# ===== battle_loop 桩(monkeypatch 构造 relaunch 首帧场景) =====


class _OcrItem(SimpleNamespace):
    """OCR 结果桩(只需 .data)。"""


def _make_loop(monkeypatch, *, new_match: bool, elapsed_s: float,
               ocr_texts: list[str], first_seen: bool = False):
    """构 battle_loop 桩:bypass __init__,只喂 _record_round_outcome 依赖面。

    read_phase_round 桩返 (1,1)(模拟 relaunch 后缓存已 reset 的兜底值);
    read_round_outcome 桩返高置信 RoundOutcome(hp 真值来自结算屏);
    cw_telemetry.record_outcome / record_exogenous monkeypatch 捕获(自动还原,
    不写真实 .debug)。
    """
    from sr_od.application.currency_war.operations import battle_loop as bl

    captured: list[dict] = []

    def _fake_record_outcome(outcome, source: str = '', supply_pick=None) -> None:
        captured.append({'outcome': outcome, 'source': source,
                         'supply_pick': supply_pick})

    monkeypatch.setattr(bl.cw_telemetry, 'record_outcome', _fake_record_outcome)
    monkeypatch.setattr(bl.cw_telemetry, 'record_exogenous',
                        lambda *a, **k: None)
    monkeypatch.setattr(bl, 'read_phase_round', lambda ctx, screen: (1, 1))

    def _fake_read_outcome(ctx, screen, *, plane, round_num, comp_tag,
                           node_type='普通战斗'):
        return RoundOutcome(round_num=round_num, plane=plane, node_type=node_type,
                            comp_tag=comp_tag, hp_after=78, hp_confidence=1.0)

    monkeypatch.setattr(bl, 'read_round_outcome', _fake_read_outcome)

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._iter = 1
            self._summary_written = False
            self._is_new_match = new_match
            self._run_start_ts = time.monotonic() - elapsed_s
            self._first_settlement_seen = first_seen
            self._settle_page1_progress = None
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(target_comp=None,
                                            last_state=GameState(),
                                            last_hp=None),
                    strategy=SimpleNamespace(on_round_end=lambda *a, **k: None),
                ),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None, color_range=None,
                    crop_first=False: [_OcrItem(data=t) for t in ocr_texts]),
            )
            self._cw_config = None

        def round_by_ocr(self, screen, word, **kw):
            return SimpleNamespace(is_success=False)

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=False)   # T#103:boss 判定改 area(标识-首领)

    return _Loop(), captured


def test_relaunch_residual_tagged_recovered_and_round_fixed(monkeypatch) -> None:
    """启动宽限内首见结算屏:source='recovered' + round 按屏面「1-6」校正。"""
    op, captured = _make_loop(
        monkeypatch, new_match=True, elapsed_s=1.0,
        ocr_texts=['挑战结束', '1-6', '战斗', '小队生命值78i', '继续挑战'])
    op._record_round_outcome(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == 'recovered'
    assert captured[0]['outcome'].round_num == 6
    assert captured[0]['outcome'].plane == 1


def test_second_settlement_not_tagged(monkeypatch) -> None:
    """同 run 第二个结算屏(非首见)→ 不打 recovered(正常行)。"""
    op, captured = _make_loop(
        monkeypatch, new_match=True, elapsed_s=1.0,
        ocr_texts=['挑战成功', '1-6', '战斗'])
    op._record_round_outcome(screen=None)
    op._record_round_outcome(screen=None)
    assert [c['source'] for c in captured] == ['recovered', '']
    #屏面「X-Y」解析升级为全路径(残留专用 → 单调门内恒采纳),
    # 第二行(非残留)round 也按屏面真值 6 落,不再保 last-known 兜底 1。
    assert captured[1]['outcome'].round_num == 6
    assert captured[1]['outcome'].plane == 1


def test_fresh_match_not_tagged(monkeypatch) -> None:
    """新对局正常行(距启动超宽限;或非首见)→ source='' 且 round 不被覆盖。"""
    # 场景1:超宽限的新 match 首个结算(真实对局,分钟级后才见结算屏)
    op, captured = _make_loop(
        monkeypatch, new_match=True, elapsed_s=9999.0,
        ocr_texts=['挑战成功', '1-6', '战斗'])
    op._record_round_outcome(screen=None)
    assert captured[0]['source'] == ''
    #屏面解析全路径生效 → round=6(旧锁「保 last-known 1」已随 失效)
    assert captured[0]['outcome'].round_num == 6
    # 场景2:宽限内但已见过结算屏(续跑/恢复段)
    op2, captured2 = _make_loop(
        monkeypatch, new_match=True, elapsed_s=1.0, first_seen=True,
        ocr_texts=['挑战成功', '1-6', '战斗'])
    op2._record_round_outcome(screen=None)
    assert captured2[0]['source'] == ''


def test_residual_unparseable_still_tagged(monkeypatch) -> None:
    """屏面「X-Y」解析不出(OCR 噪声)→ round 保底,但 recovered 标记仍在
    (修法 b 兜底:脏行可识别,训练侧可剔)。"""
    op, captured = _make_loop(
        monkeypatch, new_match=True, elapsed_s=1.0,
        ocr_texts=['挑战结束', '??', '战斗'])
    op._record_round_outcome(screen=None)
    assert captured[0]['source'] == 'recovered'
    assert captured[0]['outcome'].round_num == 1


# ===== 缺陷②:补给节点合成 outcome 行 =====


def test_supply_outcome_synthesized(monkeypatch) -> None:
    """RunSupplyNode 完成点 → 合成 node_type='补给' 行(source='synthetic_supply')。"""
    from sr_od.application.currency_war.operations import battle_loop as bl

    captured: list[dict] = []

    def _fake_record_outcome(outcome, source: str = '', supply_pick=None) -> None:
        captured.append({'outcome': outcome, 'source': source,
                         'supply_pick': supply_pick})

    monkeypatch.setattr(bl.cw_telemetry, 'record_outcome', _fake_record_outcome)
    monkeypatch.setattr(bl, 'read_phase_round', lambda ctx, screen: (1, 5))

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107  桩
            _tgt = SimpleNamespace(name='仙舟3')
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(
                        target_comp=_tgt,
                        last_state=GameState(hp=77, hp_readable=True,
                                             plane=1, round_num=5)),
                ),
            )

    op = _Loop()
    op._record_supply_outcome(screen=None)
    assert len(captured) == 1
    o = captured[0]['outcome']
    assert captured[0]['source'] == 'synthetic_supply'
    assert o.node_type == '补给'
    assert o.round_num == 5 and o.plane == 1
    assert o.hp_after == 77 and o.hp_confidence == 1.0
    assert o.killed is True   # 语义=节点通过


def test_supply_outcome_hp_unreadable_low_confidence(monkeypatch) -> None:
    """last_state.hp_readable=False(死局 100 兜底毒化面)→ 置信度记 0,hp 不冒认真值。"""
    from sr_od.application.currency_war.operations import battle_loop as bl

    captured: list[dict] = []

    monkeypatch.setattr(bl.cw_telemetry, 'record_outcome',
                        lambda outcome, source='', supply_pick=None: captured.append(
                            {'outcome': outcome, 'source': source,
                             'supply_pick': supply_pick}))
    monkeypatch.setattr(bl, 'read_phase_round', lambda ctx, screen: (2, 5))

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107  桩
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(
                        target_comp=None,
                        last_state=GameState(hp=100, hp_readable=False,
                                             plane=2, round_num=5)),
                ),
            )

    op = _Loop()
    op._record_supply_outcome(screen=None)
    assert captured[0]['outcome'].hp_confidence == 0.0
    assert captured[0]['outcome'].comp_tag == '?'


def test_supply_branch_wiring_in_source() -> None:
    """弱锁保底:0e 分支真接线(RunSupplyNode 成功 → _record_supply_outcome)。"""
    import inspect

    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop.loop)
    assert 'RunSupplyNode(self.ctx).execute()' in src
    assert '_record_supply_outcome(screen)' in src
