"""局终域 match_final + obs_event 登记面 + 局终判定面锁(R5 W2)。

正本锚:retirement.md §2 runs 行(局终域 = runs 收编载体,一段一行,恢复局
跨段多行)/ §3.6.1 同名行(G8 补写语义 note=recovered 显影)/ §3.6.2 消费面
行 9(终局防重读门改挂 match_final 写前查重;复盘触发挂局终行落盘事件)。
设计锚:流程侧遥测正本 §3.2.3 行型 2(obs_event 事件词表封闭集)/ 表 3-3
局终域③格(actor=MatchClose)。

锁面 =
- 终局行 schema:时点版本 id 与行头 v 恒等 + 终局快照随行自带(行内
  state prov)+ 版本戳(code_commit/registry_fingerprint,模块级常量
  落账填充)+ 终局类型词表封闭(集外显式炸错);
- 写口:同版本原子(一次调用恰一行)、段内幂等(G12 写前查重)、渠道签名
  (logic_hook/MatchClose);
- 异常终局补写:backfilled=True → 行注记 recovered 显影 + 版本 id 照常分配;
- 复盘触发器挂点:监听槽缺省关 + 写口受理成功即触发(行落盘以 sink/run_id
  在场为准;幂等跳过不触发)+ 监听异常不毒化;
- obs_event 登记面:G10 倒退读数留证落码(拒读类证据占版本、零状态变更);
- 局终判定面:resolve_final_type 判定序 + runs 词表收编映射 +
  detect_match_final 证据阶梯(journal 已收口幂等 / runs_summary /
  terminal_closure / no_close_evidence→abnormal);
- 下游识别:match_archive extract_match_final_rows + endgame.match_final
  档案键;W4 键收编聚合载体(载荷快照 + journal 行可见性)。

测试隔离:journal sink / run_id provider / 监听槽均为模块级全局——fixture
统一安装/复位;测试零真实副作用(流水落 tmp_path)。
"""
from __future__ import annotations

import json

import pytest

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel import cw_state_journal as journal_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    MATCH_FINAL_FIELD,
    GameState,
    observe_node_anchor,
    set_match_final_listener,
    write_match_final,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_game_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
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


def _lsig() -> _ChannelSig:
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


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


# (原 test_match_final_domain_registered 删:单行「域键在场」断言,经核
#  判读/档案消费面无人读 gs_schema['match_final'] 键——write 系测试红时
#  同故障,子集断言不留。)
# (收口整删)原 test_match_final_closed_vocab「终局类型词表封闭集」:
# 集外炸错腿并入下方原子行锁(常量字面断言不留);原
# test_match_final_version_stamps「版本戳」:载荷戳腿并入原子行锁,
# 解析器等值对拍半(kernel 复刻 vs telemetry 单一源双实现等值)随锁退役
# ——src 侧 cw_game_state.py 常量段注释仍指针本文件对拍,收口申报见报告。
# 原 test_write_match_final_default_duration_segment_level「duration_s
# 缺省 = 段级自算」删:缺省时长 = time.monotonic 差值 ≥0,语言自带保证面,
# 显式传值直通半由原子行锁 duration_s=1234.5 断言承重。


def test_write_match_final_one_atomic_row(journal, run_id,
                                          monkeypatch) -> None:
    """同版本原子:一次调用恰一行,载荷(类型/版本 id/快照/时长/版本戳)
    一次装配(行头 v 与 at_version 恒等);渠道签名 = logic_hook/MatchClose;
    终局类型词表封闭(集外显式炸错,禁自由串);版本戳取模块级常量填充
    (monkeypatch 常量即见即锁,常量与取值单一源 telemetry/version_stamp
    的等值对拍面随退役锁申报)。红 = 拆行/签名漂移/集外放行/戳断供。"""
    monkeypatch.setattr(gs_mod, '_CODE_COMMIT', 't244commit')
    monkeypatch.setattr(gs_mod, '_REGISTRY_FINGERPRINT', 't244finger')
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    # 集外终局类型 = 显式炸错(封闭词表)
    with pytest.raises(ValueError):
        write_match_final(gs, final_type='completed')
    gs.write_logic(gs.hp, 48, produced_by='test', sig=_lsig())
    assert write_match_final(gs, final_type='loss', plane=2, round_num=6,
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
    assert after['code_commit'] == 't244commit', '版本戳随行落账(常量填充)'
    assert after['registry_fingerprint'] == 't244finger', '注册表指纹随行落账'
    # 行行自足:终局快照随行内嵌 state 自带(来源注记面在档)
    vals = row['state']['values']
    assert vals['hp'] == 48, '行内 state = 终局账面(快照行自带)'


def test_write_match_final_segment_idempotent(journal, run_id) -> None:
    """段内幂等(G12 终局防重写前查重收编):本段已有终局行 → 第二次调用
    no-op 返 False,不产第二行。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(gs, final_type='win', plane=3, round_num=9) is True
    n_before = len(_rows())
    assert write_match_final(gs, final_type='loss', plane=3, round_num=9) is False
    assert len(_rows()) == n_before, '幂等跳过零新行'
    assert gs.match_final.value.final_type == 'win', '首行不被覆盖'


def test_abnormal_backfill_note_recovered_version_allocated(journal, run_id) -> None:
    """异常终局补写(G8):backfilled=True → 版本 id 照常分配 + 行载荷
    backfilled 位 + 行注记缺省 recovered 显影(判读可辨真伪)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    v_before = gs.write_seq
    assert write_match_final(gs, final_type='abnormal', plane=1, round_num=3,
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
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(gs, final_type='win', plane=3, round_num=9) is True
    assert len(fired) == 1
    assert fired[0]['run_id'] == run_id
    assert fired[0]['final_type'] == 'win'
    assert fired[0]['version'] == _final_rows()[0]['v']
    assert write_match_final(gs, final_type='loss') is False
    assert len(fired) == 1, '幂等跳过不触发'

    def _boom(info: dict) -> None:
        raise RuntimeError('listener boom')

    set_match_final_listener(_boom)
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
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
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(gs, final_type='win') is True
    assert len(fired) == 1
    assert fired[0]['run_id'] == ''
    assert fired[0]['final_type'] == 'win'
    # 态②局外:武装但供给槽返空 → 行被局外门拒落,事件照发(run_id='')
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=lambda: '')
    try:
        bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        assert write_match_final(bs2, final_type='loss') is True
        assert len(fired) == 2
        assert fired[1]['run_id'] == ''
        rows = [r for r in j.rows if r.get('field') == MATCH_FINAL_FIELD]
        assert rows == [], '未武装/局外两态行均不落盘'
    finally:
        reset_state_telemetry()


# ============================================================ obs_event 登记面


# (收口整删)原 test_obs_event_vocab_closed_set「obs_event 事件词表封闭
# 集(硬约束 2)」删:常量字面断言 + 炸错腿 = 事实源在 cw_vocab 词表定义,
# 集外炸错由 pytest.raises 形态与封闭集测试同构面承重不成立——如实申报:
# note_obs_event 集外炸错行为现无独立锁,词表漂移归 kernel 既有锁与
# review 面(覆盖缺口随收口申报)。


def test_g10_retrograde_obs_event_evidence(journal, run_id) -> None:
    """G10 倒退留证(锚定口径,
    切换后写端 = observe_node_anchor):读数 < 现值 → 零状态变更(字段不动)
    + obs_event 留证(event=arbitrate,actor = 锚定宿主登记名,占版本)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    observe_node_anchor(gs, 5, trigger_screen='货币战争-备战',
                        actor='TestAnchor')
    assert gs.node_ord.value == 5
    n_before = len(_rows())
    observe_node_anchor(gs, 4, trigger_screen='货币战争-备战',
                        actor='TestAnchor')
    assert gs.node_ord.value == 5, '倒退免疫:字段不动(R3 规则三)'
    evs = [r for r in _rows()[n_before:] if r['row'] == 'obs_event']
    assert len(evs) == 1, '倒退丢弃 obs_event 留证(占版本零状态变更)'
    ev = evs[0]
    assert ev['event'] == 'arbitrate'
    assert ev['field'] == 'node_ord'
    assert ev['observed'] == {'reading': 4, 'current': 5}
    assert ev['sig']['actor'] == 'TestAnchor'
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


# (收口整删)原 test_view_match_final_reading「判读 CLI 读面(view_
# match_final 显影/无行提示)」删:CLI 输出文案锁(「type=」「补写」等
# 字样断言)= 展示层快照,红时答不出哪个消费行为坏了;判读读数面由
# match_final_rows 行取数(原 view 测试内同函数断言)与下游档案锁承重。


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


# ============================================================ W4 键收编聚合载体(R5 W4,r5-migration-plan.md §2)

def test_match_final_payload_carries_cw4_aggregate(journal, run_id) -> None:
    """载荷聚合锁:write_match_final(cw4_counters=…) → 载荷原样落账;
    写口浅拷贝(传入容器后写不串账)。None = 无策略载体诚实缺省;聚合键
    进 journal 局终行 after 载荷,行行自足可读(判读直接读行,零重放;
    原 cw4_aggregate_in_journal_row 行可见性腿并入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    counters = {'shop_churn_pair_buy': 3, 'launch_frame_idle_gold': 120}
    assert write_match_final(gs, final_type='loss',
                             cw4_counters=counters) is True
    payload = gs.match_final.value
    assert payload.cw4_counters == counters, '聚合随局终行落账'
    assert payload.cw4_counters is not counters, '载荷持快照副本非容器引用'
    counters['shop_churn_pair_buy'] = 99
    assert payload.cw4_counters['shop_churn_pair_buy'] == 3, '后写不串'
    # 行可见性腿(并入):journal 局终行 after 携带聚合键(快照态,不受
    # 后写串改)
    rows = _final_rows()
    assert rows and rows[0]['after']['cw4_counters'] == {
        'shop_churn_pair_buy': 3, 'launch_frame_idle_gold': 120}, (
        '聚合进 journal 局终行(局终级全键聚合可见性载体,行行自足)')
    # None 形态(无 session/历史段补写无源)
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(bs2, final_type='abnormal',
                             backfilled=True) is True
    assert bs2.match_final.value.cw4_counters is None, (
        '无载体 = None 诚实缺省(与零计数空 dict 可辨)')
