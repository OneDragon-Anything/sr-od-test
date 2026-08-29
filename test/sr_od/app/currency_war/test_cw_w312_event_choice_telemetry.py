"""行为锁:overlay 选项选择族落盘(exogenous.jsonl kind='event_choice')。

实证缺口(遥测审计 G1):遭遇/巨星/伙伴/策划事件/命运卜者/装备选卡/祈愿
七个 handler 的选项选择此前只 log.info 不进账本——「当时提供了什么选项、bot 选了
哪个、为什么」跨局归因在遥测上断链(对照:invest 族全量落盘、supply_pick)。
修法三段:
① schema:ExogenousEvent.choice 可选字段(kind='event_choice' 行携带;旧记录
  与其它 kind 恒 None——缺省兼容);
② 共用辅助 recorder.record_event_choice(一处实现,禁 7 份复制);
③ 七个 handler 在选项确认时点各接一行。

纯逻辑/桩测试(monkeypatch 构造;TelemetryRecorder 指 tmp_path,不写真实 .debug;
_CURRENT_RUN_ID / _CTX_MATCH_REF 经 monkeypatch.setattr 还原,不污染 session)。
"""
from __future__ import annotations

import inspect

import pytest

from sr_od.application.currency_war.telemetry import state
from sr_od.application.currency_war.telemetry import recorder


from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder, record_event_choice

from sr_od.application.currency_war.telemetry.query import read_jsonl
from sr_od.application.currency_war.telemetry import state as cw_telemetry


@pytest.fixture(autouse=True)
def _reset_run_ctx(monkeypatch):
    """测试卫生:run_id 与 ctx match 引用经 monkeypatch 还原(不串后续测试)。"""
    monkeypatch.setattr(state, '_CURRENT_RUN_ID', 'w312-run')
    monkeypatch.setattr(state, '_CTX_MATCH_REF', [None])


# ===== ① schema:choice 字段 roundtrip + 旧记录 None 兼容 =====


def test_exogenous_choice_roundtrip(tmp_path) -> None:
    """record_exogenous(choice=...) 落盘为结构化 dict;不传 → None(旧 schema 兼容)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    choice = {'event': 'encounter', 'options': [{'difficulty': '难度1', 'rewards': '金币'}],
              'n_options': 1, 'pick_idx': 0, 'reason': 'low-diff'}
    rec.record_exogenous('r1', 5, 'event_choice', detail='encounter pick=idx0',
                         choice=choice)
    rec.record_exogenous('r1', 6, 'popup', detail='普通弹窗')
    lines = read_jsonl(tmp_path / 'exogenous.jsonl')
    assert lines[0]['kind'] == 'event_choice'
    assert lines[0]['choice'] == choice
    assert lines[1]['choice'] is None       # 非 event_choice 行恒 None
    assert lines[1]['kind'] == 'popup'


def test_disabled_recorder_choice_noop(tmp_path) -> None:
    """enabled=False 全 no-op(与既有遥测门控一致,不产生半行)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=False)
    rec.record_exogenous('r1', 5, 'event_choice',
                         choice={'event': 'encounter', 'options': [],
                                 'n_options': 0, 'pick_idx': 0, 'reason': ''})
    assert not (tmp_path / 'exogenous.jsonl').exists()


# ===== ② 共用辅助 record_event_choice =====


def test_helper_writes_event_choice_row(tmp_path) -> None:
    """helper 一行进 exogenous.jsonl:event/options/n_options/pick_idx/reason 齐;
    round_num 从 ctx match last_state 兜底解析。"""
    monkey_match = type('M', (), {})()
    monkey_match.session = type('S', (), {})()
    monkey_match.session.last_state = GameState(round_num=5)
    state.set_ctx_match(monkey_match)
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch_rec = rec
    origin = state.get_recorder
    state.get_recorder = lambda: monkeypatch_rec   # noqa: ANN001  测试内注入
    try:
        record_event_choice('encounter',
                            [{'difficulty': '难度3', 'rewards': '角色x3'},
                             {'difficulty': '难度1', 'rewards': '金币x2'}],
                            1, reason='formed→high-diff')
    finally:
        state.get_recorder = origin
    lines = read_jsonl(tmp_path / 'exogenous.jsonl')
    assert len(lines) == 1
    row = lines[0]
    assert row['kind'] == 'event_choice'
    assert row['round_num'] == 5            # 来自 last_state(overlay 期最近备战快照)
    assert row['choice']['event'] == 'encounter'
    assert row['choice']['n_options'] == 2
    assert row['choice']['pick_idx'] == 1
    assert row['choice']['reason'] == 'formed→high-diff'
    assert len(row['choice']['options']) == 2


def test_helper_empty_options_and_no_round(tmp_path) -> None:
    """识别失败路径照记(options=[] 且 round_num=0 兜底)——留证据不断链。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    origin = state.get_recorder
    state.get_recorder = lambda: rec
    try:
        record_event_choice('megastar', None, 0, reason='no match')
    finally:
        state.get_recorder = origin
    row = read_jsonl(tmp_path / 'exogenous.jsonl')[0]
    assert row['choice'] == {'event': 'megastar', 'options': [], 'n_options': 0,
                             'pick_idx': 0, 'reason': 'no match'}
    assert row['round_num'] == 0            # 无 match → 0(离线/测试兜底)


def test_helper_no_run_id_noop(tmp_path) -> None:
    """run_id 空(局外)直接 no-op,不产生孤儿行。"""
    monkey_run = cw_telemetry
    origin_run, origin_rec = monkey_run._CURRENT_RUN_ID, monkey_run.get_recorder
    monkey_run._CURRENT_RUN_ID = ''
    try:
        record_event_choice('encounter', ['a'], 0, reason='x')
    finally:
        monkey_run._CURRENT_RUN_ID = origin_run
    assert not (tmp_path / 'exogenous.jsonl').exists()
    del origin_rec


# ===== ③ 七个 handler 接线锁(源码级弱锁;≥3 的合格线取全集) =====

_W312_WIRING = [
    # (模块路径, 承载函数/节点方法, 事件短码)
    ('sr_od.application.currency_war.operations.handlers.handle_encounter',
     'HandleEncounter.handle', 'encounter'),
    ('sr_od.application.currency_war.operations.run_nodes.run_megastar_node',
     'RunMegastarNode._do_action', 'megastar'),
    ('sr_od.application.currency_war.operations.handlers.handle_select_partner',
     'HandleSelectPartner.handle', 'partner'),
    ('sr_od.application.currency_war.operations.handlers.handle_planner_event',
     'HandlePlannerEvent.handle', 'planner_event'),
    ('sr_od.application.currency_war.operations.handlers.handle_fortune_picker',
     'HandleFortunePicker.handle', 'fortune_pick'),
    ('sr_od.application.currency_war.operations.handlers.handle_equip_pick',
     'HandleEquipPick.handle', 'equip_pick'),
    ('sr_od.application.currency_war.operations.handlers.handle_wish_trial',
     'HandleWishTrial.handle', 'wish_trial'),
]


@pytest.mark.parametrize('module_path,func_qual,event', _W312_WIRING)
def test_handler_wiring_in_source(module_path: str, func_qual: str,
                                  event: str) -> None:
    """弱锁:每个 handler 的选择点真调 record_event_choice,且事件短码对位。"""
    import importlib

    mod = importlib.import_module(module_path)
    obj = mod
    for part in func_qual.split('.'):
        obj = getattr(obj, part)
    src = inspect.getsource(obj)
    assert 'record_event_choice(' in src, f'{func_qual} 未接 W312 落盘'
    assert f"'{event}'" in src or f'"{event}"' in src, \
        f'{func_qual} 事件短码应为 {event}'


def test_single_helper_no_copy() -> None:
    """共用辅助唯一源锁:handler 面不得出现自造第二套 record_exogenous(kind=
    'event_choice')直调(禁 7 份复制的纪律落进测试)。"""
    for module_path, func_qual, _ev in _W312_WIRING:
        import importlib

        mod = importlib.import_module(module_path)
        obj = mod
        for part in func_qual.split('.'):
            obj = getattr(obj, part)
        src = inspect.getsource(obj)
        assert "record_exogenous(" not in src, \
            f'{func_qual} 应走共用 record_event_choice,不直调 record_exogenous'

from sr_od.application.currency_war.kernel.cw_state import GameState
