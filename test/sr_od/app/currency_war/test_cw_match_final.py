"""局终域 match_final + obs_event 登记面 + 局终判定面锁(R5 W2)。

正本锚:retirement.md §2 runs 行(局终域 = runs 收编载体,一段一行,恢复局
跨段多行)/ §3.6.1 同名行(G8 补写语义 note=recovered 显影)/ §3.6.2 消费面
行 9(终局防重读门改挂 match_final 写前查重;复盘触发挂局终行落盘事件)。
设计锚:流程侧遥测正本 §3.2.3 行型 2(obs_event 事件词表封闭集)/ 表 3-3
局终域③格(actor=MatchClose)。

锁面 =
- 终局行 schema:载荷封闭词表 + 时点版本 id 与行头 v 恒等 + 终局快照随行
  自带(行内 state prov)+ 版本戳(code_commit/registry_fingerprint,模块
  级常量落账填充,与 telemetry/version_stamp 单一源等值对拍);
- 写口:同版本原子(一次调用恰一行)、段内幂等(G12 写前查重)、渠道签名
  (logic_hook/MatchClose);
- 异常终局补写:backfilled=True → 行注记 recovered 显影 + 版本 id 照常分配;
- 复盘触发器挂点:监听槽缺省关 + 写口受理成功即触发(行落盘以 sink/run_id
  在场为准;幂等跳过不触发)+ 监听异常不毒化;
- obs_event 登记面:事件词表封闭集(集外 = 红)+ G10 倒退读数留证落码
  (拒读类证据占版本、零状态变更);
- 局终判定面:resolve_final_type 判定序 + runs 词表收编映射 +
  detect_match_final 证据阶梯(journal 已收口幂等 / runs_summary /
  terminal_closure / no_close_evidence→abnormal);
- 下游识别:match_archive extract_match_final_rows + endgame.match_final
  档案键;判读 CLI 读面 view_match_final。

测试隔离:journal sink / run_id provider / 监听槽均为模块级全局——fixture
统一安装/复位;测试零真实副作用(流水落 tmp_path)。
"""
from __future__ import annotations

import json

import pytest

from sr_od.application.currency_war.kernel import cw_state_journal as journal_mod
from sr_od.application.currency_war.kernel import cw_board_state as bs_mod
from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BoardState,
    MATCH_FINAL_FIELD,
    MATCH_FINAL_TYPES,
    OBS_EVENT_EVENTS,
    _derive_node_observed,
    set_match_final_listener,
    state_telemetry_armed,
    write_match_final,
)
from sr_od.application.currency_war.kernel.cw_state_journal import (
    install_state_telemetry,
    reset_state_telemetry,
)
from sr_od.application.currency_war.obs.cw_observation import (
    detect_match_final,
    resolve_final_type,
    runs_result_to_final_type,
)
from sr_od.application.currency_war.telemetry import match_archive
from sr_od.application.currency_war.telemetry import state as tel_state
from sr_od.application.currency_war.telemetry import version_stamp
from sr_od.application.currency_war.telemetry.journal_query import (
    match_final_rows,
    view_match_final,
)


@pytest.fixture()
def journal(tmp_path):
    """装一份指到 tmp 的状态流水(影子面武装;teardown 复位模块全局)。"""
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=tel_state.current_run_id)
    yield j
    reset_state_telemetry()


@pytest.fixture()
def run_id(monkeypatch):
    """桩一个 run 归属(行内 run_id 键;teardown 由 monkeypatch 自动还原)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_test_final')
    return 'run_test_final'


@pytest.fixture(autouse=True)
def _no_listener():
    """监听槽复位(模块级全局;防跨测试残留)。"""
    set_match_final_listener(None)
    yield
    set_match_final_listener(None)


def _rows() -> list[dict]:
    j = journal_mod.state_journal_instance()
    assert j is not None, '本用例须先装 journal(fixture journal)'
    return list(j.rows)


def _final_rows() -> list[dict]:
    return [r for r in _rows() if r.get('field') == MATCH_FINAL_FIELD]


# ============================================================ 终局行 schema + 写口


def test_match_final_domain_registered() -> None:
    """局终域入 bs_schema(缺域键 = 该域未建模,§3.7.1;同 receipts 先例)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.bs_schema.get('match_final') == 1


def test_write_match_final_one_atomic_row(journal, run_id) -> None:
    """同版本原子:一次调用恰一行,载荷(类型/版本 id/快照/时长)一次装配
    (行头 v 与 at_version 恒等);渠道签名 = logic_hook/MatchClose。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.hp, 48, produced_by='test')
    assert write_match_final(bs, final_type='loss', plane=2, round_num=6,
                             level=7, hp=48, gold=53, streak=-1,
                             node_kind='boss', duration_s=1234.5) is True
    rows = _final_rows()
    assert len(rows) == 1, '一次终局写口调用 = 恰一行(同版本原子)'
    row = rows[0]
    assert row['row'] == 'write' and row['run_id'] == run_id
    assert row['sig']['family'] == 'logic_hook'
    assert row['sig']['actor'] == 'MatchClose'
    after = row['after']
    assert after['final_type'] == 'loss'
    assert after['at_version'] == row['v'], '时点版本 id = 本行自身版本 id'
    assert after['plane'] == 2 and after['round_num'] == 6
    assert after['hp'] == 48 and after['gold'] == 53 and after['level'] == 7
    assert after['streak'] == -1 and after['node_kind'] == 'boss'
    assert after['duration_s'] == 1234.5
    assert after['backfilled'] is False
    # 行行自足:终局快照随行内嵌 state 自带(来源注记面在档)
    vals = row['state']['values']
    assert vals['hp'] == 48, '行内 state = 终局账面(快照行自带)'


def test_write_match_final_segment_idempotent(journal, run_id) -> None:
    """段内幂等(G12 终局防重写前查重收编):本段已有终局行 → 第二次调用
    no-op 返 False,不产第二行。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert write_match_final(bs, final_type='win', plane=3, round_num=9) is True
    n_before = len(_rows())
    assert write_match_final(bs, final_type='loss', plane=3, round_num=9) is False
    assert len(_rows()) == n_before, '幂等跳过零新行'
    assert bs.match_final.value.final_type == 'win', '首行不被覆盖'


def test_match_final_closed_vocab() -> None:
    """终局类型词表封闭集:集外显式炸错(禁自由串)。"""
    assert MATCH_FINAL_TYPES == ('win', 'loss', 'stopped', 'abnormal')
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    with pytest.raises(ValueError):
        write_match_final(bs, final_type='completed')


def test_write_match_final_default_duration_segment_level() -> None:
    """duration_s 缺省 = 段级自算(容器创建 → 判定,≥0);显式传值直通。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert write_match_final(bs, final_type='stopped') is True
    assert bs.match_final.value.duration_s is not None
    assert bs.match_final.value.duration_s >= 0.0


def test_abnormal_backfill_note_recovered_version_allocated(journal, run_id) -> None:
    """异常终局补写(G8):backfilled=True → 版本 id 照常分配 + 行载荷
    backfilled 位 + 行注记缺省 recovered 显影(判读可辨真伪)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    v_before = bs.write_seq
    assert write_match_final(bs, final_type='abnormal', plane=1, round_num=3,
                             backfilled=True) is True
    row = _final_rows()[0]
    assert row['v'] == v_before + 1, '补写行版本 id 照常分配'
    assert row['after']['final_type'] == 'abnormal'
    assert row['after']['backfilled'] is True
    assert row['note'] == 'recovered', '补写行 note=recovered 显影'


def test_match_final_listener_fires_on_row_only(journal, run_id) -> None:
    """复盘触发器挂点(武装+局内态):监听缺省关;写口受理成功即触发
    (幂等跳过不触发);事件携带 run_id/终局类型/版本;监听异常不毒化终局
    流转。未武装/局外两态的触发真值 = 下一把锁。"""
    fired: list[dict] = []
    set_match_final_listener(fired.append)
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert write_match_final(bs, final_type='win', plane=3, round_num=9) is True
    assert len(fired) == 1
    assert fired[0]['run_id'] == run_id
    assert fired[0]['final_type'] == 'win'
    assert fired[0]['version'] == _final_rows()[0]['v']
    assert write_match_final(bs, final_type='loss') is False
    assert len(fired) == 1, '幂等跳过不触发'

    def _boom(info: dict) -> None:
        raise RuntimeError('listener boom')

    set_match_final_listener(_boom)
    bs2 = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert write_match_final(bs2, final_type='loss') is True, \
        '监听异常不毒化终局流转'


def test_match_final_listener_fires_unarmed_and_offmatch(tmp_path) -> None:
    """触发真值两态(申报勘误钉锁):未武装(无 sink)/局外(供给槽返空)
    行均不落而监听照触发,事件 run_id=''——消费方(复盘触发接线)按此
    自滤,禁按「落行才触发」旧申报消费。"""
    fired: list[dict] = []
    set_match_final_listener(fired.append)
    # 态①未武装:sink 缺席 → 版本照耗、Field 照写、零落盘,事件照发
    reset_state_telemetry()
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert write_match_final(bs, final_type='win') is True
    assert len(fired) == 1
    assert fired[0]['run_id'] == ''
    assert fired[0]['final_type'] == 'win'
    # 态②局外:武装但供给槽返空 → 行被局外门拒落,事件照发(run_id='')
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=lambda: '')
    try:
        bs2 = BoardState(schema_version=BS_SCHEMA_VERSION)
        assert write_match_final(bs2, final_type='loss') is True
        assert len(fired) == 2
        assert fired[1]['run_id'] == ''
        rows = [r for r in j.rows if r.get('field') == MATCH_FINAL_FIELD]
        assert rows == [], '未武装/局外两态行均不落盘'
    finally:
        reset_state_telemetry()


def test_match_final_version_stamps(journal, run_id, monkeypatch) -> None:
    """版本戳(§3.6.1 runs 行「+ code_commit/registry_fingerprint 版本戳,
    沿用 version_stamp」):终局行载荷带两戳、write_match_final 落账时取模块
    级常量填充;常量与取值单一源 telemetry/version_stamp 等值(kernel 桶依赖
    矩阵禁依 telemetry,就地复刻,对拍防双实现漂移)。"""
    assert bs_mod._CODE_COMMIT == version_stamp.code_commit()
    assert bs_mod._REGISTRY_FINGERPRINT == version_stamp.registry_fingerprint()
    monkeypatch.setattr(bs_mod, '_CODE_COMMIT', 't244commit')
    monkeypatch.setattr(bs_mod, '_REGISTRY_FINGERPRINT', 't244finger')
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert write_match_final(bs, final_type='loss', plane=2, round_num=6) is True
    after = _final_rows()[0]['after']
    assert after['code_commit'] == 't244commit'
    assert after['registry_fingerprint'] == 't244finger'


# ============================================================ obs_event 登记面


def test_obs_event_vocab_closed_set() -> None:
    """obs_event 事件词表封闭集(§3.2.3 行型 2 产生面;硬约束 2 同纪律):
    arbitrate/miss/popup 合法,集外显式炸错。"""
    assert OBS_EVENT_EVENTS == ('arbitrate', 'miss', 'popup')
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    for ev in OBS_EVENT_EVENTS:
        bs.note_obs_event(ev, 'level', {'old': 1, 'new': 2})
    with pytest.raises(ValueError):
        bs.note_obs_event('bogus_event', 'level', {})


def test_g10_retrograde_obs_event_evidence(journal, run_id) -> None:
    """G10 倒退留证:候选 < hist → 零状态变更(字段不动)+ obs_event 留证
    (event=arbitrate,actor 保留触发规则归因,占版本)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _derive_node_observed(bs, 5, trigger_screen='货币战争-备战', seq=1)
    assert bs.node_ord.value == 5
    n_before = len(_rows())
    _derive_node_observed(bs, 4, trigger_screen='货币战争-备战', seq=2)
    assert bs.node_ord.value == 5, '倒退免疫:字段不动(R3 规则三)'
    evs = [r for r in _rows()[n_before:] if r['row'] == 'obs_event']
    assert len(evs) == 1, '倒退丢弃 obs_event 留证(占版本零状态变更)'
    ev = evs[0]
    assert ev['event'] == 'arbitrate'
    assert ev['field'] == 'node_ord'
    assert ev['observed'] == {'candidate': 4, 'hist': 5}
    assert ev['sig']['actor'] == 'derive_node_observed'
    assert '倒退' in ev['verdict']


# ============================================================ 局终判定面


def test_resolve_final_type_priority_ladder() -> None:
    """在线判定序 = 主动停止 > 失败 > 通关(plane==3 精确值,假 win 守卫
    同口径);未打轮 = None(开局失败形态非终局);其余真实结束 = abnormal。"""
    assert resolve_final_type(stop_requested=True, saw_defeat=True,
                              plane_reached=3) == 'stopped'
    assert resolve_final_type(stop_requested=False, saw_defeat=True,
                              plane_reached=3) == 'loss'
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=3) == 'win'
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=1, rounds_played=False) is None
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=1) == 'abnormal'
    # plane=8(OCR 难度泄漏形态)≠ 通关:假 win 守卫同口径,禁 >=
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=8) == 'abnormal'


def test_runs_result_mapping_covers_archive_values() -> None:
    """runs result 词表收编映射:win/loss/stopped 直映;非完结值(含
    abandoned/completed/空)= abnormal——与档案装配器完结判定同界。"""
    assert runs_result_to_final_type('win') == 'win'
    assert runs_result_to_final_type('loss') == 'loss'
    assert runs_result_to_final_type('stopped') == 'stopped'
    assert runs_result_to_final_type('abandoned') == 'abnormal'
    assert runs_result_to_final_type('completed') == 'abnormal'
    assert runs_result_to_final_type('') == 'abnormal'


def test_detect_match_final_evidence_ladder() -> None:
    """证据阶梯:journal 已收口 → None(幂等);runs_summary 行 → 收编映射;
    terminal_closure 结算行 → 收口行映射;全缺 → abnormal(补写形态判据)。"""
    assert detect_match_final(run_id='r', journal_final={'v': 1}) is None
    d = detect_match_final(
        run_id='r',
        runs_summary={'result': 'loss', 'plane_reached': 2,
                      'rounds_survived': 6, 'final_hp': 48,
                      'ts': '2026-09-10T10:00:00'})
    assert (d.final_type, d.plane, d.round_num, d.hp) == ('loss', 2, 6, 48)
    assert d.evidence == 'runs_summary'
    d2 = detect_match_final(
        run_id='r',
        outcome_rows=[{'source': 'terminal_closure', 'match_result': 'stopped',
                       'plane': 2, 'round_num': 6, 'ts': 't'}])
    assert (d2.final_type, d2.plane, d2.round_num) == ('stopped', 2, 6)
    assert d2.evidence == 'terminal_closure'
    d3 = detect_match_final(run_id='r', outcome_rows=[
        {'source': '', 'killed': False}])   # 非收口行不入阶梯 3
    assert d3.final_type == 'abnormal'
    assert d3.evidence == 'no_close_evidence'


# ============================================================ 下游识别(装配器 + 判读 CLI 读面)


def _journal_line(v: int, run: str, final_type: str, *, note: str = '') -> str:
    payload = {'final_type': final_type, 'at_version': v, 'plane': 3,
               'round_num': 9, 'node_kind': None, 'level': 9, 'hp': 10,
               'gold': 77, 'streak': 5, 'duration_s': 600.0,
               'backfilled': bool(note)}
    row = {'v': v, 'ts': '2026-09-10T10:00:00', 'run_id': run, 'row': 'write',
           'field': MATCH_FINAL_FIELD, 'after': payload, 'same_value': False,
           'state': {'values': {}}, 'sig': {'family': 'logic_hook',
                                            'actor': 'MatchClose'},
           'note': note, 'evidence_refs': []}
    return json.dumps(row, ensure_ascii=False)


def test_extract_match_final_rows_recognition() -> None:
    """识别判据封闭:write ∧ field=match_final ∧ run_id 非空;同 run 多行取
    v 最大;obs_event 行/他字段行不误收。"""
    rows = [
        {'row': 'write', 'field': 'gold', 'run_id': 'r1', 'v': 1},
        {'row': 'write', 'field': MATCH_FINAL_FIELD, 'run_id': 'r1', 'v': 2,
         'after': {'final_type': 'loss'}},
        {'row': 'obs_event', 'field': MATCH_FINAL_FIELD, 'run_id': 'r1',
         'v': 3, 'event': 'arbitrate'},
        {'row': 'write', 'field': MATCH_FINAL_FIELD, 'run_id': '', 'v': 4},
        {'row': 'write', 'field': MATCH_FINAL_FIELD, 'run_id': 'r2', 'v': 5,
         'after': {'final_type': 'win'}},
        {'row': 'write', 'field': MATCH_FINAL_FIELD, 'run_id': 'r1', 'v': 6,
         'after': {'final_type': 'win'}},
    ]
    out = match_archive.extract_match_final_rows(rows)
    assert set(out) == {'r1', 'r2'}
    assert out['r1']['v'] == 6, '同 run 多行取 v 最大'
    assert out['r2']['v'] == 5
    assert match_archive.extract_match_final_rows(None) == {}


def test_view_match_final_reading(tmp_path) -> None:
    """判读 CLI 读面:局终行显影(类型/快照/补写位);无行 = 显式提示。"""
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=tel_state.current_run_id)
    try:
        j.append(json.loads(_journal_line(7, 'run_a', 'loss')))
        j.append(json.loads(_journal_line(9, 'run_b', 'abnormal',
                                          note='recovered')))
        rows = list(j.rows)
        out = view_match_final(rows, 'run_a')
        assert any('type=loss' in ln for ln in out)
        assert any('run_a' in out[0] for _ in [0])
        out_b = view_match_final(rows, 'run_b')
        assert any('type=abnormal' in ln and '补写' in ln for ln in out_b), \
            '补写行显影'
        assert any('recovered' in ln for ln in out_b)
        assert match_final_rows(rows, 'run_a')[-1]['after']['final_type'] == 'loss'
        empty = view_match_final([], 'run_x')
        assert any('无局终行' in ln for ln in empty)
    finally:
        reset_state_telemetry()


def test_build_archive_endgame_match_final(tmp_path, monkeypatch) -> None:
    """档案端到端(假环境):新账局终行在档 → endgame.match_final 装配;
    无局终行 → None 键(旧档案/影子未开形态)。加法键零 bump 申报锁。"""
    rd = tmp_path / 'replay'
    (rd / 'state').mkdir(parents=True)
    for name in ('decisions.jsonl', 'outcomes.jsonl', 'runs.jsonl'):
        (rd / name).write_text('', encoding='utf-8')
    j = rd / 'state' / 'journal.jsonl'
    j.write_text(_journal_line(3, 'run_x', 'loss') + '\n', encoding='utf-8')
    game = {'game_id': 'g_test', 'segments': ['run_x'],
            'start_ts': '2026-09-10T10:00:00', 'end_ts': '2026-09-10T10:10:00'}
    a = match_archive.build_archive(rd, game)
    mf = a['endgame']['match_final']
    assert mf is not None
    assert mf['run_id'] == 'run_x'
    assert mf['final']['final_type'] == 'loss'
    assert mf['v'] == 3
    # 无局终行形态
    j.write_text('', encoding='utf-8')
    a2 = match_archive.build_archive(rd, game)
    assert a2['endgame']['match_final'] is None
    assert a2['schema_version'] == match_archive.SCHEMA_VERSION
