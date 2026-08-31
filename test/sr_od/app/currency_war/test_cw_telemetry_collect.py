# -*- coding: utf-8 -*-
"""test_cw_telemetry_collect 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w306_supply_telemetry: test_cw_w306_supply_telemetry.py
- w312_event_choice_telemetry: test_cw_w312_event_choice_telemetry.py
- w323_sell_income_telemetry: test_cw_w323_sell_income_telemetry.py
- w239_p2r1_loss_outcome: test_cw_w239_p2r1_loss_outcome.py
- w28_outcome_write_defects: test_cw_w28_outcome_write_defects.py
- w280_takeover_collect: test_cw_w280_takeover_collect.py
- w414_gold_detail_hook: test_cw_w414_gold_detail_hook.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w306_supply_telemetry ====================

import time
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.kernel.cw_state import GameState

from sr_od.application.currency_war.telemetry import recorder
from sr_od.application.currency_war.telemetry import state

from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder

from sr_od.application.currency_war.telemetry.state import consume_last_supply_pick, set_last_supply_pick

from sr_od.application.currency_war.telemetry.query import read_jsonl
from sr_od.application.currency_war.telemetry import state
from sr_od.application.currency_war.telemetry import state as cw_telemetry

# ===== ③ OutcomeRecord.supply_pick(schema 锁) =====


def test_record_outcome_supply_pick_roundtrip(tmp_path) -> None:
    """recorder.record_outcome(supply_pick=...) 落盘;不传 → None(旧 schema 兼容)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    pick = {'char': '三月七', 'equip': '记忆', 'has_diamond': True,
            'refreshed': False, 'gold': 120}
    rec.record_outcome('r1', RoundOutcome(round_num=5, plane=1, node_type='补给',
                                          comp_tag='c', hp_after=77, killed=True),
                       source='synthetic_supply', supply_pick=pick)
    rec.record_outcome('r1', RoundOutcome(round_num=6, plane=1, node_type='普通战斗',
                                          comp_tag='c', hp_after=78))
    lines = read_jsonl(tmp_path / 'outcomes.jsonl')
    assert lines[0]['source'] == 'synthetic_supply'
    assert lines[0]['supply_pick'] == pick
    assert lines[1]['source'] == ''
    assert lines[1]['supply_pick'] is None


# ===== ①→② 暂存槽:一次消费 =====


def test_pick_slot_set_then_consume_once() -> None:
    """set_last_supply_pick 存快照;consume 返回并清槽(第二次取 None 不串轮)。"""
    try:
        set_last_supply_pick('仙舟笑笑', '长枪', True, refreshed=True)
        got = consume_last_supply_pick()
        assert got is not None
        assert got['char'] == '仙舟笑笑'
        assert got['equip'] == '长枪'
        assert got['has_diamond'] is True
        assert got['refreshed'] is True
        #不传 options → 无 options/n_options 键(兜底路径形态容忍)
        assert 'options' not in got and 'n_options' not in got
        assert consume_last_supply_pick() is None   # 清槽:残留不串下一轮
    finally:
        consume_last_supply_pick()   # 测试卫生:无论断言走哪支都清干净


def test_pick_slot_options_dynamic_column_count() -> None:
    """锁:选项清单按**实际识别列数**记录(n_options=len(options),逐列内容
    透传);列数动态(3 与 5 都成立)——补给通常 4 选 1,augment 改写可变 3-5,禁写死。"""
    try:
        for n in (3, 4, 5):
            opts = [{'char': f'c{i}', 'equip': f'e{i}', 'has_diamond': i % 2 == 0}
                    for i in range(n)]
            set_last_supply_pick('c0', 'e0', True, refreshed=False, options=opts)
            got = consume_last_supply_pick()
            assert got['n_options'] == n
            assert got['options'] == opts
            assert consume_last_supply_pick() is None
    finally:
        consume_last_supply_pick()


def test_synthetic_row_carries_options_list(monkeypatch) -> None:
    """synthetic 行透传选项清单(实际列数+逐列内容,合成行与牌面对拍源)。"""
    op, captured = _make_loop(
        monkeypatch,
        GameState(hp=14, gold=55, plane=1, round_num=5),
        pick={'char': '姬子', 'equip': '火焰', 'has_diamond': False,
              'refreshed': False, 'gold': 55,
              'options': [{'char': '姬子', 'equip': '火焰', 'has_diamond': False},
                          {'char': '', 'equip': '熔炉', 'has_diamond': True},
                          {'char': '笑笑', 'equip': '面具', 'has_diamond': False}],
              'n_options': 3})
    op._record_supply_outcome(screen=None)
    row = captured[0]['supply_pick']
    assert row['n_options'] == 3          # 动态列数(此局 3 列)
    assert len(row['options']) == row['n_options']
    assert row['options'][0] == {'char': '姬子', 'equip': '火焰',
                                 'has_diamond': False}


# ===== ② battle_loop 合成路径(消费者接线) =====


def _make_loop(monkeypatch, last_state: GameState, *, pick=None):
    """构 battle_loop 桩(bypass __init__,只喂 _record_supply_outcome 依赖面)。

    record_outcome / read_phase_round 走 monkeypatch.setattr(自动还原);
    consume_last_supply_pick 由调用方注入(pick 参数,None=兜底点卡路径)。
    返回 (op, captured)。
    """
    from sr_od.application.currency_war.operations import battle_loop as bl

    captured: list[dict] = []

    def _fake_record_outcome(outcome, source: str = '', supply_pick=None) -> None:
        captured.append({'outcome': outcome, 'source': source,
                         'supply_pick': supply_pick})

    monkeypatch.setattr(recorder, 'record_outcome', _fake_record_outcome)
    # consume_last_supply_pick 注入:battle_loop 经模块属性消费(cw_telemetry.*)
    monkeypatch.setattr(state, 'consume_last_supply_pick', lambda: pick)
    monkeypatch.setattr(bl, 'read_phase_round', lambda ctx, screen: (1, 5))

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107  桩
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(
                        target_comp=None, last_state=last_state),
                ),
            )

    return _Loop(), captured


def test_synthetic_row_carries_choice_gold(monkeypatch) -> None:
    """暂存有快照:合成的 supply 行带 char/equip/diamond/refreshed+完成时点 gold。"""
    op, captured = _make_loop(
        monkeypatch,
        GameState(hp=14, gold=55, plane=1, round_num=5,
                  hp_readable=True, gold_readable=True),
        pick={'char': '姬子', 'equip': '火焰', 'has_diamond': False,
              'refreshed': False})
    op._record_supply_outcome(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == 'synthetic_supply'
    assert captured[0]['supply_pick'] == {
        'char': '姬子', 'equip': '火焰', 'has_diamond': False,
        'refreshed': False, 'gold': 55}


def test_synthetic_row_gold_unreadable_omitted(monkeypatch) -> None:
    """last_state.gold_readable=False → supply_pick 无 gold 键(不冒认真值);
    暂存空(兜底点卡路径)→ supply_pick 为 None(choices 键缺失容忍)。"""
    op, captured = _make_loop(
        monkeypatch,
        GameState(hp=100, gold=0, plane=2, round_num=5,
                  hp_readable=False, gold_readable=False),
        pick=None)
    op._record_supply_outcome(screen=None)
    assert len(captured) == 1
    assert captured[0]['supply_pick'] is None


def test_supply_producer_wiring_in_source() -> None:
    """弱锁保底:RunSupplyNode 选定分支真接线(set_last_supply_pick + 选项清单透传,
    :options=逐列内容动态列表)。"""
    import inspect

    from sr_od.application.currency_war.operations.run_nodes import run_supply_node
    src = inspect.getsource(run_supply_node.RunSupplyNode._do_action)
    assert 'set_last_supply_pick(' in src
    assert "options=[{'char': o.char" in src   # 逐列内容透传(实际识别列数)


# ===== 补给备战状态采集 detour(坐标 2026-08-27 实机实测后复实现) =====


class _NoSleepTime:
    """time 替身:sleep 只记账不真睡,其余属性透传真 time 模块。

    detour 的等待常量(TO_PREP_SETTLE_S 等)是为真机画面过渡设计的;离线桩里
    mock 画面点击后瞬间就位,这些 sleep 纯属空等(两用例曾各烧 10.5s)。
    同 test harness fast_sleep 的思路,但 run_supply_node 模块自持
    ``import time``,fast_sleep 替换的是 operation.py 的 time,覆盖不到这里。
    """

    def __init__(self) -> None:
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        """记录被跳过的等待时长(诊断用),不真正睡眠。"""
        self.skipped.append(seconds)

    def __getattr__(self, name: str):
        return getattr(time, name)


def _make_supply_op(monkeypatch):
    """构 RunSupplyNode 桩(__new__ 绕过 op __init__;只喂 detour 依赖面)。

    返回 (op, decision_captured)。round_by_find_and_click_area 全成功;
    截图恒为同一伪帧(离线桩);read_game_state 桩出确定值。
    """
    from sr_od.application.currency_war.operations.run_nodes import run_supply_node as m

    # 离线桩空等消除:模块自持 import time,换 no-sleep 替身(类 docstring 详因)
    monkeypatch.setattr(m, 'time', _NoSleepTime())

    decision_captured: list[dict] = []

    monkeypatch.setattr(recorder, 'record_decision',
                        lambda state, target_comp='', candidate_scores=None,
                        eval_breakdown=None, actions=None, gold_point=True,
                        extra=None: decision_captured.append(
                            {'target_comp': target_comp,
                             'actions': list(actions or []),
                             'gold_point': gold_point,
                             'extra': dict(extra or {})}))
    monkeypatch.setattr(m, 'read_game_state',
                        lambda ctx, screen, **kw: GameState(hp=88, gold=66,
                                                            plane=1,
                                                            round_num=5))
    op = m.RunSupplyNode.__new__(m.RunSupplyNode)
    fake_screen = object()
    match = SimpleNamespace(session=SimpleNamespace(target_comp=None,
                                                    last_state=None))
    op.ctx = SimpleNamespace(cw_match=match, current_instance_idx=1)
    op.screenshot = lambda: fake_screen   # noqa: ANN001  实例属性遮蔽方法
    click_log: list[tuple] = []
    op._click_log = click_log
    op.round_by_find_and_click_area = (
        lambda screen, sn, an, **kw: (click_log.append((sn, an)) or
                                      SimpleNamespace(is_success=True)))
    # 重进后 overlay 判定(_in_node 内部用):桩成命中(离线无画面)
    op.round_by_find_area = (
        lambda screen, sn, an, **kw: SimpleNamespace(is_success=True))
    # OCR 文本兜底枪(重进序列末位):桩离线无画面
    op.round_by_ocr_and_click = (
        lambda screen, text, **kw: SimpleNamespace(is_success=False))
    return op, decision_captured


def test_detour_records_non_buy_snapshot(monkeypatch) -> None:
    """detour 快照语义锁:actions=[] + phase='supply_detour'(**非购买轮**标注);
    流程 = 点返回备战 → 采集 → 点返回补给阶段 重进。"""
    op, captured = _make_supply_op(monkeypatch)
    match = op.ctx.cw_match
    ok = (op._should_supply_detour(match) and op._mark_supply_detour(match)
          is None and op._supply_detour_collect(match))
    assert ok is True
    assert len(captured) == 1
    row = captured[0]
    assert row['actions'] == []                 # 无任何购买动作
    assert row['extra']['phase'] == 'supply_detour'
    assert row['target_comp'] == ''             # 无 target=非购买轮决策
    assert ('货币战争-补给', '按钮-返回备战界面') in op._click_log
    assert ('货币战争-备战', '按钮-返回补给阶段') in op._click_log
    assert match.session._supply_detour_done is True


def test_detour_once_per_node(monkeypatch) -> None:
    """一次语义锁:_mark 后不再触发(_should_supply_detour=False);无 match 退实例态。"""
    op, _c = _make_supply_op(monkeypatch)
    match = op.ctx.cw_match
    assert op._should_supply_detour(match) is True
    op._mark_supply_detour(match)
    assert op._should_supply_detour(match) is False
    # 实例态兜底(离线/测试无 match 路径)
    op2, _c2 = _make_supply_op(monkeypatch)
    op2.ctx.cw_match = None
    assert op2._should_supply_detour(None) is True
    op2._mark_supply_detour(None)
    assert op2._should_supply_detour(None) is False


def test_detour_return_miss_no_snapshot(monkeypatch) -> None:
    """「返回备战界面」点击 miss → 不记快照、不误采集(detour 静默放弃)。"""
    op, captured = _make_supply_op(monkeypatch)
    op.round_by_find_and_click_area = (
        lambda screen, sn, an, **kw:
        SimpleNamespace(is_success=(an != '按钮-返回备战界面')))
    assert op._supply_detour_collect(op.ctx.cw_match) is False
    assert captured == []


def test_do_action_skips_pick_when_detour_fails(monkeypatch) -> None:
    """重进失败 → 本轮不做任何选择动作(防备战屏盲点卡身),交下轮重试 detour。"""
    from sr_od.application.currency_war.operations.run_nodes import run_supply_node as m

    op, captured = _make_supply_op(monkeypatch)

    def _fail_reenter(screen, sn, an, **kw):
        # 「返回备战界面」成功;备战侧「按钮-返回补给阶段」恒失败 → 重进不通
        if an == '按钮-返回备战界面':
            return SimpleNamespace(is_success=True)
        return SimpleNamespace(is_success=False)
    op.round_by_find_and_click_area = _fail_reenter
    op.round_by_find_area = (
        lambda screen, sn, an, **kw: SimpleNamespace(is_success=False))

    pick_calls: list = []
    monkeypatch.setattr(m, 'read_supply_options',
                        lambda ctx, screen: pick_calls.append(screen) or [])
    monkeypatch.setattr(state, 'consume_last_supply_pick', lambda: None)
    op._do_action(object())
    assert len([r for r in captured
                if r['extra'].get('phase') == 'supply_detour']) == 1
    assert pick_calls == []   # 未进入选择读帧(detour 失败即止)


def test_detour_failure_not_marked_retry_next_round(monkeypatch) -> None:
    """失败不落标记(宁可见 FAIL bail 不带病假完成):session 无 _supply_detour_done,
    下轮 _should_supply_detour 仍 True → 重试整个 detour;OCR 文本兜底点击已尝试。"""

    op, captured = _make_supply_op(monkeypatch)
    ocr_clicks: list[str] = []
    op.round_by_find_and_click_area = (
        lambda screen, sn, an, **kw: SimpleNamespace(
            is_success=(an == '按钮-返回备战界面')))
    op.round_by_find_area = (
        lambda screen, sn, an, **kw: SimpleNamespace(is_success=False))
    op.round_by_ocr_and_click = (
        lambda screen, text, **kw: (ocr_clicks.append(text) or
                                    SimpleNamespace(is_success=False)))
    match = op.ctx.cw_match
    assert op._supply_detour_collect(match) is False
    assert not getattr(match.session, '_supply_detour_done', False), \
        '失败不得落标记(否则下轮跳过 detour 直接在错误画面选择)'
    assert op._should_supply_detour(match) is True   # 下轮重试 detour
    assert ocr_clicks == ['返回补给阶段']   # OCR 文本兜底枪已打(重试序列末位)


def test_detour_semantics_lock_in_source() -> None:
    """弱锁:detour 快照带 phase='supply_detour' 且 actions=[](非购买轮语义)。"""
    import inspect

    from sr_od.application.currency_war.operations.run_nodes import run_supply_node
    src = inspect.getsource(run_supply_node.RunSupplyNode._supply_detour_collect)
    assert "extra={'phase': 'supply_detour'}" in src
    assert 'actions=[], gold_point=True' in src








# ==================== w312_event_choice_telemetry ====================

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


# ==================== w323_sell_income_telemetry ====================

import inspect
from contextlib import contextmanager

import pytest

from sr_od.application.currency_war.telemetry import state
from sr_od.application.currency_war.telemetry import recorder

from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    SellBench,
)

from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder, record_sell_income

from sr_od.application.currency_war.telemetry.query import query_economy, read_jsonl


@pytest.fixture(autouse=True)
def _w323_sell_income_telemetry_reset_run_ctx(monkeypatch):
    """测试卫生:run_id 与 ctx match 引用经 monkeypatch 还原(不串后续测试)。"""
    monkeypatch.setattr(state, '_CURRENT_RUN_ID', 'w323-run')
    monkeypatch.setattr(state, '_CTX_MATCH_REF', [None])


@contextmanager
def _recorder_as_module(tmp_path):
    """构造 enabled recorder 并临时注入模块 get_recorder(参照 event_choice 落盘测试手法)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    origin = state.get_recorder
    state.get_recorder = lambda: rec   # noqa: ANN001  测试内注入
    try:
        yield rec
    finally:
        state.get_recorder = origin


# ===== ① 写端:record_sell_income =====


def test_record_sell_income_writes_row(tmp_path) -> None:
    """卖出实收回金落盘:kind/round/slot/char/gold_delta 齐,快照带 plane/gold。"""
    with _recorder_as_module(tmp_path) as rec:
        record_sell_income(GameState(gold=12, round_num=4, plane=1),
                           slot=3, char_id='桑博',
                           gold_before=10, gold_after=13)
        rows = read_jsonl(tmp_path / 'exogenous.jsonl')
    assert len(rows) == 1
    row = rows[0]
    assert row['kind'] == 'sell_income'
    assert row['round_num'] == 4
    assert row['choice'] == {'slot': 3, 'char': '桑博', 'gold_delta': 3}
    assert row['state_snapshot']['plane'] == 1
    assert row['state_snapshot']['gold'] == 12


def test_record_sell_income_none_when_gold_unreadable(tmp_path) -> None:
    """执行前后 gold 任一读不到(OCR miss)→ gold_delta=None(视图计 0 并标 ?)。"""
    with _recorder_as_module(tmp_path) as rec:
        record_sell_income(GameState(gold=10, round_num=2, plane=1),
                           slot=0, char_id='青雀', gold_before=10, gold_after=None)
        row = read_jsonl(tmp_path / 'exogenous.jsonl')[0]
    assert row['choice']['gold_delta'] is None
    assert rec.enabled   # 注入确实生效(防假绿)


def test_record_sell_income_no_run_id_noop(tmp_path) -> None:
    """run_id 空(局外)直接 no-op,不产生孤儿行(与 record_exogenous 同门控)。"""
    origin_run = state._CURRENT_RUN_ID
    state._CURRENT_RUN_ID = ''
    try:
        record_sell_income(GameState(round_num=1), slot=0, char_id='x',
                           gold_before=1, gold_after=2)
    finally:
        state._CURRENT_RUN_ID = origin_run
    assert not (tmp_path / 'exogenous.jsonl').exists()


def test_shop_sell_branch_wiring_in_source() -> None:
    """接线锁:shop.py SellBench 执行分支真调 record_sell_income(落盘点唯一源)。"""
    from sr_od.application.currency_war.operations.prep import shop

    src = inspect.getsource(shop.BuyShopCards.buy)
    assert 'record_sell_income(' in src, 'SellBench 执行分支未接 W323 落盘'


# ===== ② 读端:economy 视图「卖回」格 =====


def test_economy_uses_observed_sell_income(tmp_path) -> None:
    """实收 sell_income 在场:视图 卖+NN 用执行点真值,income 残差按它倒推。

    场景:r1 金 20 → r2 金 25,期间仅卖一件实收 3(无利息/连胜):
    income 残差 = 25 − 20 + 0(花)− 3(卖回)= 2。
    """
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('w323a', 'A8')
    rec.record_decision('w323a', 'A8',
                        GameState(gold=20, round_num=1, plane=1),
                        'c', {}, {}, [])
    rec.record_decision('w323a', 'A8',
                        GameState(gold=25, round_num=2, plane=1),
                        'c', {}, {}, [SellBench(bench_idx=0)])   # 生产行不带 income
    with _recorder_as_module(tmp_path):
        state._CURRENT_RUN_ID = 'w323a'
        try:
            record_sell_income(GameState(gold=25, round_num=2, plane=1),
                               slot=0, char_id='桑博', gold_before=22, gold_after=25)
        finally:
            state._CURRENT_RUN_ID = 'w323-run'
    eco = query_economy(tmp_path, 'w323a')
    assert any('卖+3' in ln for ln in eco), f'economy 应显示实收卖回 3,实际 {eco}'
    assert any('收=2' in ln for ln in eco), \
        f'收入残差应扣掉卖回(25-20+0-3=2,无噪声),实际 {eco}'


def test_economy_marks_unknown_when_delta_none(tmp_path) -> None:
    """该轮有 sell_income 行但 gold_delta=None → 计 0 并标 `?`(有偏可辨)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('w323b', 'A8')
    rec.record_decision('w323b', 'A8',
                        GameState(gold=10, round_num=2, plane=1),
                        'c', {}, {}, [SellBench(bench_idx=0)])
    with _recorder_as_module(tmp_path):
        state._CURRENT_RUN_ID = 'w323b'
        try:
            record_sell_income(GameState(gold=10, round_num=2, plane=1),
                               slot=0, char_id='青雀', gold_before=10, gold_after=None)
        finally:
            state._CURRENT_RUN_ID = 'w323-run'
    eco = query_economy(tmp_path, 'w323b')
    assert any('卖+0?' in ln for ln in eco), f'delta=None 应计 0 并标 ?,实际 {eco}'


def test_economy_falls_back_to_action_income_legacy(tmp_path) -> None:
    """旧数据/sim 局(无 exogenous 行):回退 actions 的 SellBench.income 口径
    (W69 锁 3 语义不回归,且不误标卖回 `?`)。

    (W707 对账瘦身·w729 收尾执行:原 test_cw_w69_sell_channel 锁 3 并入本锁
    ——SellBench.income 序列化→decisions 行→query_economy「卖+NN」全链
    由本锁的 record_decision(income=6) 行程覆盖,单一保留点在此。)
    """
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('w323c', 'A8')
    rec.record_decision('w323c', 'A8',
                        GameState(gold=50, round_num=1, plane=1),
                        'c', {}, {}, [SellBench(bench_idx=0, income=6)])
    eco = query_economy(tmp_path, 'w323c')
    assert any('卖+6' in ln and '卖+6?' not in ln for ln in eco), \
        f'旧口径卖入应保留且不标 ?,实际 {eco}'


def test_economy_no_sell_round_unchanged(tmp_path) -> None:
    """无卖轮:不显示卖回格(与既有『无卖局不显示』锁一致,不回归)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('w323d', 'A8')
    rec.record_decision('w323d', 'A8',
                        GameState(gold=30, round_num=1, plane=1),
                        'c', {}, {}, [])
    eco = query_economy(tmp_path, 'w323d')
    assert len(eco) == 1 and '卖+' not in eco[0], f'无卖轮不应出现卖回格,实际 {eco}'


# ==================== w239_p2r1_loss_outcome ====================

import inspect
import time
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.telemetry import state as cw_telemetry


class _OcrItem(SimpleNamespace):
    """OCR 结果桩(.data 文本 + .y 坐标,fp 指纹需要)。"""


def _w239_p2r1_loss_outcome_make_loop(monkeypatch, *, ocr_texts: list[str], read_phase: tuple[int, int],
               killed=None, hp_confidence: float = 0.0):
    """构 battle_loop 桩:bypass __init__,喂 _record_round_outcome/_record_loss_page 依赖面。

    read_phase_round 桩返 ``read_phase``(模拟 last-known 缓存态);read_round_outcome
    桩按入参回显 plane/round 并可控 killed/hp_confidence;cw_telemetry 写端 monkeypatch
    捕获(自动还原);strategy.on_round_end 记调用次数(telemetry-only 面断言用)。
    """
    from sr_od.application.currency_war.operations import battle_loop as bl

    captured: list[dict] = []
    on_round_end_calls: list[int] = []

    def _fake_record_outcome(outcome, source: str = '') -> None:
        captured.append({'outcome': outcome, 'source': source})

    monkeypatch.setattr(recorder, 'record_outcome', _fake_record_outcome)
    monkeypatch.setattr(recorder, 'record_exogenous', lambda *a, **k: None)
    monkeypatch.setattr(bl, 'read_phase_round', lambda ctx, screen: read_phase)

    def _fake_read_outcome(ctx, screen, *, plane, round_num, comp_tag,
                           node_type='普通战斗'):
        return RoundOutcome(round_num=round_num, plane=plane, node_type=node_type,
                            comp_tag=comp_tag, hp_after=0, hp_confidence=hp_confidence,
                            killed=killed)

    monkeypatch.setattr(bl, 'read_round_outcome', _fake_read_outcome)

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._iter = 1
            self._is_new_match = True
            self._run_start_ts = time.monotonic() - 9999.0   # 超宽限:非残留
            self._first_settlement_seen = False
            self._settle_page1_progress = None
            self._battle_ts = object()   # 哨兵值:断言 telemetry-only 不清它
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(target_comp=None,
                                            last_state=GameState(),
                                            last_hp=None, last_hp_t=None),
                    strategy=SimpleNamespace(
                        on_round_end=lambda *a, **k: on_round_end_calls.append(1)),
                ),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None, color_range=None,
                    crop_first=False: [
                        _OcrItem(data=t, y=i * 20) for i, t in enumerate(ocr_texts)]),
            )
            self._cw_config = None

        def round_by_ocr(self, screen, word, **kw):
            return SimpleNamespace(is_success=False)

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=False)   # T#103:boss 判定改 area(标识-首领)

    return _Loop(), captured, on_round_end_calls


# ===== 修复②:结算屏「X-Y」屏面真值全路径(根因=last-known 缓存位面切换滞后) =====


def test_win_settlement_screen_truth_overrides_stale_p1_cache(monkeypatch) -> None:
    """P1→P2 过场后首结算:缓存停在 (1,9),屏面「2-1」→ 行落 plane=2/r1。

    即 replay 实锤的错归属形态(run_20260825_145641:node_type=普通战斗 落在 (1,9),
    P1r9 恒为 boss 不可能)——屏面真值在读时点,不依赖过场后是否有帧读到「2-1」。
    """
    op, captured, _ = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(1, 9),
        ocr_texts=['挑战成功', '2-1', '战斗', '小队生命值78i', '继续挑战'],
        hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert captured[0]['outcome'].plane == 2
    assert captured[0]['outcome'].round_num == 1


def test_screen_truth_equal_to_cache_no_op(monkeypatch) -> None:
    """屏面真值与 last-known 一致(位面内常规轮)→ 原值原样,不引入新行为。"""
    op, captured, _ = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(1, 6),
        ocr_texts=['挑战成功', '1-6', '战斗'], hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert (captured[0]['outcome'].plane, captured[0]['outcome'].round_num) == (1, 6)


def test_screen_truth_behind_cache_rejected(monkeypatch) -> None:
    """屏面解析落后 last-known(OCR 假阳形态,如把 '1-4' 误读在 (1,6) 帧)→ 拒,保缓存。

    单调门镜像 read_phase_round 的单调守卫;位面前进 (1,9)→(2,1) 合法不受影响
    (t 序 (2-1)*9+1=10 > 9,见 test_win_settlement_screen_truth_overrides_stale_p1_cache)。
    """
    op, captured, _ = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(1, 6),
        ocr_texts=['挑战成功', '1-4', '战斗'], hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert captured[0]['outcome'].round_num == 6


def test_screen_unparseable_keeps_last_known(monkeypatch) -> None:
    """屏面解析不出(无头部词/噪声)→ last-known 兜底,零回归。"""
    op, captured, _ = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(2, 1),
        ocr_texts=['??', 'xx'], hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert (captured[0]['outcome'].plane, captured[0]['outcome'].round_num) == (2, 1)


# ===== 修复①:失败结算页(1f)telemetry-only 补录 =====


def test_loss_page_records_row_telemetry_only(monkeypatch) -> None:
    """败局页(killed=False)→ 落一行 source='loss_page';零策略/循环状态面。

    断言面:on_round_end 不被调(不喂 performance/last_hp → prep 行为面零变更)、
    _battle_ts 不清(ADR-0250 战斗窗口维持 1f 原语义)、_last_outcome_t 不写
    (killed 兜底对比链不受新路径扰动)。
    """
    op, captured, on_round_end_calls = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(2, 1),
        ocr_texts=['挑战结束', '2-1', '战斗', '-22', '挑战进度', '前往结算'],
        killed=False)
    _battle_ts_sentinel = op._battle_ts
    op._record_loss_page(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == 'loss_page'
    o = captured[0]['outcome']
    assert o.plane == 2 and o.round_num == 1
    assert o.killed is False
    assert on_round_end_calls == []                    # 策略面零变更
    assert op._battle_ts is _battle_ts_sentinel        # ADR-0250 窗口语义不变
    assert getattr(op, '_last_outcome_t', None) is None   # killed 对比链不扰动
    assert getattr(op, '_last_outcome_hp', None) is None  # summary 真值链不扰动


def test_loss_page_fingerprint_dedupe(monkeypatch) -> None:
    """同屏指纹防重:同帧重入只记一次(与 3b 共用 _last_loss_fp);换帧再记。"""
    op, captured, _ = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(2, 1),
        ocr_texts=['挑战结束', '2-1', '战斗', '-22'], killed=False)
    op._record_loss_page(screen=None)
    op._record_loss_page(screen=None)   # 同屏(点击未生效停留)→ 不重复
    assert len(captured) == 1
    op.ctx.ocr_service.get_ocr_result_list = lambda image, rect=None, color_range=None, crop_first=False: [
        _OcrItem(data=t, y=i * 20) for i, t in enumerate(
            ['挑战结束', '2-2', '战斗', '-7'])]
    op._record_loss_page(screen=None)   # 新败局帧 → 新行
    assert len(captured) == 2
    assert captured[1]['outcome'].round_num == 2


def test_loss_page_non_defeat_killed_gate(monkeypatch) -> None:
    """killed 非 False(位面通关过渡页误入 1f 门/OCR 未判)→ 不落行,防伪行进语料。"""
    op, captured, _ = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(1, 9),
        ocr_texts=['挑战结束', '1-9首领', '战斗'], killed=None)
    op._record_loss_page(screen=None)
    assert captured == []


def test_loss_page_failures_do_not_raise(monkeypatch) -> None:
    """OCR 服务抛错 → 补录吞异常不阻塞对局(观测为辅)。"""
    op, captured, _ = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(2, 1), ocr_texts=[], killed=False)
    def _boom(**kw):
        raise RuntimeError('ocr down')
    op.ctx.ocr_service.get_ocr_result_list = _boom
    op._record_loss_page(screen=None)   # 不抛
    assert captured == []


# ===== 弱锁保底:1f 真接线、3b 原路径保留 =====


def test_branch_wiring_in_source() -> None:
    """loop 源码弱锁:1f 分支调 _record_loss_page;3b 原输轮记录仍在。"""
    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop.loop)
    # 1f(失败结算页)翻页前补录
    assert '_record_loss_page(screen)' in src
    # 3b 原「前往结算」输轮记录路径保留(fp 防重共用,1f miss 时兜底)
    assert "btn == '前往结算'" in src
    assert '_record_round_outcome(screen)   # killed/progress_delta 由屏文本判定' in src


from sr_od.application.currency_war.telemetry import recorder


# ==================== w28_outcome_write_defects ====================

import time
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.obs.cw_settlement_obs import parse_settlement_round
from sr_od.application.currency_war.kernel.cw_state import GameState

from sr_od.application.currency_war.telemetry import recorder
from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder

from sr_od.application.currency_war.telemetry.query import read_jsonl

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


class _w28_outcome_write_defects_OcrItem(SimpleNamespace):
    """OCR 结果桩(只需 .data)。"""


def _w28_outcome_write_defects_make_loop(monkeypatch, *, new_match: bool, elapsed_s: float,
               ocr_texts: list[str], first_seen: bool = False):
    """构 battle_loop 桩:bypass __init__,只喂 _record_round_outcome 依赖面。

    read_phase_round 桩返 (1,1)(模拟 relaunch 后缓存已 reset 的兜底值);
    read_round_outcome 桩返高置信 RoundOutcome(hp 真值来自结算屏);
    recorder.record_outcome / record_exogenous monkeypatch 捕获(自动还原,
    不写真实 .debug)。
    """
    from sr_od.application.currency_war.operations import battle_loop as bl

    captured: list[dict] = []

    def _fake_record_outcome(outcome, source: str = '', supply_pick=None) -> None:
        captured.append({'outcome': outcome, 'source': source,
                         'supply_pick': supply_pick})

    monkeypatch.setattr(recorder, 'record_outcome', _fake_record_outcome)
    monkeypatch.setattr(recorder, 'record_exogenous',
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
                    crop_first=False: [_w28_outcome_write_defects_OcrItem(data=t) for t in ocr_texts]),
            )
            self._cw_config = None

        def round_by_ocr(self, screen, word, **kw):
            return SimpleNamespace(is_success=False)

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=False)   # T#103:boss 判定改 area(标识-首领)

    return _Loop(), captured


def test_relaunch_residual_tagged_recovered_and_round_fixed(monkeypatch) -> None:
    """启动宽限内首见结算屏:source='recovered' + round 按屏面「1-6」校正。"""
    op, captured = _w28_outcome_write_defects_make_loop(
        monkeypatch, new_match=True, elapsed_s=1.0,
        ocr_texts=['挑战结束', '1-6', '战斗', '小队生命值78i', '继续挑战'])
    op._record_round_outcome(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == 'recovered'
    assert captured[0]['outcome'].round_num == 6
    assert captured[0]['outcome'].plane == 1


def test_second_settlement_not_tagged(monkeypatch) -> None:
    """同 run 第二个结算屏(非首见)→ 不打 recovered(正常行)。"""
    op, captured = _w28_outcome_write_defects_make_loop(
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
    op, captured = _w28_outcome_write_defects_make_loop(
        monkeypatch, new_match=True, elapsed_s=9999.0,
        ocr_texts=['挑战成功', '1-6', '战斗'])
    op._record_round_outcome(screen=None)
    assert captured[0]['source'] == ''
    #屏面解析全路径生效 → round=6(旧锁「保 last-known 1」已随 失效)
    assert captured[0]['outcome'].round_num == 6
    # 场景2:宽限内但已见过结算屏(续跑/恢复段)
    op2, captured2 = _w28_outcome_write_defects_make_loop(
        monkeypatch, new_match=True, elapsed_s=1.0, first_seen=True,
        ocr_texts=['挑战成功', '1-6', '战斗'])
    op2._record_round_outcome(screen=None)
    assert captured2[0]['source'] == ''


def test_residual_unparseable_still_tagged(monkeypatch) -> None:
    """屏面「X-Y」解析不出(OCR 噪声)→ round 保底,但 recovered 标记仍在
    (修法 b 兜底:脏行可识别,训练侧可剔)。"""
    op, captured = _w28_outcome_write_defects_make_loop(
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

    monkeypatch.setattr(recorder, 'record_outcome', _fake_record_outcome)
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

    monkeypatch.setattr(recorder, 'record_outcome',
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





# ==================== w280_takeover_collect ====================

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_base import OperationResult
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_OP_ID = (
    'sr_od.application.currency_war.operations.entry.'
    'takeover_collect_plane_intel.TakeoverCollectPlaneIntel'
)


def _make_op(test_context: SrTestContext, monkeypatch, phases: list[dict]):
    """构造被测 op(fixture 控制器注入 + 看门狗),返回 (op, fixture_controller)。"""
    from sr_od.application.currency_war.operations.entry.takeover_collect_plane_intel import (
        TakeoverCollectPlaneIntel,
    )

    class _Watched(WatchdogOperationMixin, TakeoverCollectPlaneIntel):
        pass

    fc = FixtureController(test_context)
    fc.set_phases(phases)
    # fixture 控制器注入 ctx(is_game_window_ready=True 绕过开游戏前置链)
    monkeypatch.setattr(test_context, 'controller', fc)
    return _Watched(test_context), fc


def _exec(op) -> OperationResult:
    with fast_sleep():
        return op.execute()


# --------------------------------------------------------------------------- #
# ①注册面:run_operation 可发现
# --------------------------------------------------------------------------- #


def test_takeover_op_discoverable_by_registry(test_context: SrTestContext) -> None:
    """锁①:op 扫描注册表应含本 op(run_operation 可调起的前提)。"""
    from sr_od.backend.operation_registry import scan_operations

    ops = {o.op_id for o in scan_operations(test_context, refresh=True).operations}
    assert _OP_ID in ops, f'接管补采 op 未被扫描注册: {_OP_ID}'


# --------------------------------------------------------------------------- #
# ②入口门:错屏快速 fail
# --------------------------------------------------------------------------- #


def test_gate_fail_fast_on_lobby_frame(test_context: SrTestContext, monkeypatch) -> None:
    """锁②:大厅帧 → 快速 fail 并存证,零点击、不碰 session。"""
    monkeypatch.setattr(
        test_context, 'cw_match',
        SimpleNamespace(session=SimpleNamespace(briefing_bosses=[], briefing_affixes=[])),
        raising=False)
    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-大厅', 'lobby')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)
    assert not res.success, f'大厅帧应 fail,得成功:{res.status}'
    assert '无法补采' in str(res.status), f'status 应指明画面错误,得 {res.status!r}'
    assert fc.recorded_clicks == [], '入口门 fail 不应产生任何点击'
    sess = test_context.cw_match.session
    assert sess.briefing_bosses == [], 'fail 路径不得改写 session'


# --------------------------------------------------------------------------- #
# ③跳过门:session 已有真值 → 零点击,不委派子 op
# --------------------------------------------------------------------------- #


def test_skip_when_session_has_truth(test_context: SrTestContext, monkeypatch) -> None:
    """锁③:briefing_bosses 非空 → 直通 success,CollectPlaneIntel 不被实例化。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    truth = ['巨鹿', None, '绘师']

    def _must_not_run(*a, **k):
        raise AssertionError('session 已有真值时不应委派实采子 op')

    monkeypatch.setattr(cpi_mod, 'CollectPlaneIntel', _must_not_run)
    sess = SimpleNamespace(briefing_bosses=list(truth), briefing_affixes=['已有'])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', ['残留'], raising=False)

    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)
    assert res.success, f'跳过路径应 success,得 {res.status!r}'
    assert '跳过' in str(res.status)
    assert fc.recorded_clicks == [], '跳过路径应为零点击'
    assert sess.briefing_bosses == truth, '跳过路径不得改写已有真值'
    assert getattr(test_context, 'cw_plane_bosses', None) is None, (
        '真值保护路径应清残留中转池(防跨局判空泄漏)'
    )
    # 跳过分支池空且 session 有真值 → 清残留也属消费收尾,但跳过节点不改池:
    # 本锁只钉「session 真值未被触碰」,池语义由写回节点测试覆盖。


# --------------------------------------------------------------------------- #
# ④成功链:实采产出 → 保位落 session → 清池
# --------------------------------------------------------------------------- #


class _FakeIntel:
    """CollectPlaneIntel 替身:直接产中转池结果(壳层测试不重跑 SIFT 链)。"""

    produced_bosses: list | None = ['巨鹿', None, '绘师']
    produced_affixes: list | None = ['财富造物主', '敌人难度108']

    def __init__(self, ctx) -> None:
        self.ctx = ctx

    def execute(self) -> OperationResult:
        self.ctx.cw_plane_bosses = list(self.produced_bosses)
        self.ctx.cw_plane_affixes = list(self.produced_affixes)
        return OperationResult(success=True, status='位面情报采集')


def test_success_writes_session_and_clears_pools(test_context: SrTestContext, monkeypatch) -> None:
    """锁④主链:保位 3 槽落 session、affixes 仅空时写、消费后清池。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CollectPlaneIntel', _FakeIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=[])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_affixes', None, raising=False)

    op, _fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert res.success, f'成功链应 success,得 {res.status!r}'
    assert sess.briefing_bosses == ['巨鹿', None, '绘师'], (
        f'bosses 应保位写 3 槽(None 原样占槽),得 {sess.briefing_bosses}'
    )
    assert sess.briefing_affixes == ['财富造物主', '敌人难度108'], (
        f'affixes 仅空时应写入,得 {sess.briefing_affixes}'
    )
    assert test_context.cw_plane_bosses is None, '消费后 boss 中转池应清空'
    assert test_context.cw_plane_affixes is None, '消费后词缀中转池应清空'


def test_success_does_not_overwrite_existing_affixes(test_context: SrTestContext, monkeypatch) -> None:
    """锁④伴生:session.briefing_affixes 已有值时随采词缀**不覆写**(与
    battle_loop 内联块「仅简报未供时」口径一致)。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CollectPlaneIntel', _FakeIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=['简报先到'])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_affixes', None, raising=False)

    op, _fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert res.success
    assert sess.briefing_affixes == ['简报先到'], '已有词缀不得被随采覆写'
    assert sess.briefing_bosses == ['巨鹿', None, '绘师']


# --------------------------------------------------------------------------- #
# ⑤异常形态:实采成功但无产出 → 不落 session
# --------------------------------------------------------------------------- #


class _EmptyIntel(_FakeIntel):
    """成功但不产出的异常替身(中转池保持 None)。"""

    def execute(self) -> OperationResult:
        return OperationResult(success=True, status='位面情报采集(空)')


def test_no_output_leaves_session_untouched(test_context: SrTestContext, monkeypatch) -> None:
    """锁⑤:子 op 称成功但中转池空 → fail,session 保持空表不被覆写成假成功。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CollectPlaneIntel', _EmptyIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=[])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)

    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert not res.success, f'无产出应 fail,得 {res.status!r}'
    assert sess.briefing_bosses == [], '无产出不得写 session'


# --------------------------------------------------------------------------- #
# ⑥静态口径锁:ADR-0414 双面之一(loop 内联块的镜像面在 w219/w221 锁)
# --------------------------------------------------------------------------- #


def test_static_write_semantics_locked() -> None:
    """锁⑥:静态锁——保位写形态在位、None 过滤禁回潮、双池取走即清。"""
    from sr_od.application.currency_war.operations.entry.takeover_collect_plane_intel import (
        TakeoverCollectPlaneIntel,
    )

    src = inspect.getsource(TakeoverCollectPlaneIntel.write_back)
    assert 'list(bosses)' in src, '保位写形态消失(须 list() 原样拷贝)'
    assert '[n for n in' not in src, '滤 None 回潮(徽章态位面名字左移错序)'
    assert 'self.ctx.cw_plane_bosses = None' in src, 'boss 中转池未清(跨局泄漏)'
    assert 'self.ctx.cw_plane_affixes = None' in src, '词缀中转池未清(跨局泄漏)'


# --------------------------------------------------------------------------- #
# fixture 真帧锚:存档引用帧仍是组装画面单一源(id_mark 在屏可判)
# --------------------------------------------------------------------------- #


def test_w277_reference_frame_ids_plane_detail(test_context: SrTestContext) -> None:
    """锁⑦:存档引用帧(screens png 存档)上「标识-位面详情标题」id_mark
    必命中——组装画面锚漂移即本 op 入口判定失效的前置信号。"""
    import cv2
    import numpy as np

    p = (Path(__file__).parents[4] / 'screens' / '货币战争-位面详情'
         / '位面详情-点节点直开.png')
    img_bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {p}'
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB

    from sr_od.application.currency_war.operations.entry.takeover_collect_plane_intel import (
        TakeoverCollectPlaneIntel,
    )

    op = TakeoverCollectPlaneIntel(test_context)
    res = op.round_by_find_area(img_rgb, '货币战争-位面详情', '标识-位面详情标题',
                                crop_first=False)
    assert res.is_success, 'W277 引用帧上位面详情 id_mark 应命中(真实 OCR)'


# ==================== w414_gold_detail_hook ====================

import json
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.obs import cw_settlement_obs
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    collect_gold_detail_hook,
    parse_settlement_gold_detail,
    read_round_outcome,
)


class _Item(SimpleNamespace):
    """OCR 结果桩(data/x/y/width/height;坐标取自 win.webp 实测帧)。"""


def _items(spec: list[tuple[str, int, int, int, int]]) -> list[_Item]:
    return [_Item(data=t, x=x, y=y, width=w, height=h)
            for t, x, y, w, h in spec]


# win.webp 全屏 OCR 实测(与 test_cw_w40_settlement_damage.WIN_FRAME 同源;金币明细区:
# 基础奖励(530,604)→5(1051,605);利息(527,653)→4(1057,660);连胜×0(528,702))
WIN_FRAME = _items([
    ('挑战成功', 831, 192, 256, 73), ('1-8', 887, 270, 44, 28),
    ('奖励', 981, 269, 55, 30), ('Lv.5', 1110, 367, 85, 66),
    ('4/20', 1127, 427, 55, 25), ('小队命值20i', 646, 479, 226, 43),
    ('获得金币总览', 530, 553, 146, 28), ('10', 1042, 555, 31, 26),
    ('数据统计', 1120, 554, 98, 29), ('基础奖励', 530, 604, 98, 28),
    ('5', 1051, 605, 22, 25), ('试用', 1144, 601, 47, 25),
    ('396.3万', 1198, 635, 81, 25), ('利息', 527, 653, 56, 31),
    ('4', 1057, 660, 13, 17), ('试用', 1144, 678, 48, 26),
    ('连胜×0', 528, 702, 113, 35), ('6.4万', 1196, 712, 58, 26),
    ('掉落晶矿', 528, 771, 100, 32), ('5', 1058, 780, 8, 14),
    ('继续挑战', 910, 878, 100, 31),
])


# ===== 纯函数:parse_settlement_gold_detail =====

def test_win_fixture_three_components() -> None:
    """实锤帧:基础奖励=5 / 利息=4 / 连胜=0(总分 10 = 5+4+0 交叉自洽)。"""
    assert parse_settlement_gold_detail(WIN_FRAME) == {
        'base': 5, 'streak': 0, 'interest': 4}


def test_attached_token_forms() -> None:
    """同 token 粘连形态(OCR 把标签与值读进一块):'基础奖励5' / '连胜x3'。"""
    items = _items([
        ('获得金币总览', 530, 553, 146, 28), ('基础奖励5', 530, 604, 120, 28),
        ('连胜x3', 528, 702, 113, 35), ('利息', 527, 653, 56, 31),
    ])
    assert parse_settlement_gold_detail(items) == {
        'base': 5, 'streak': 3, 'interest': None}


def test_header_streak_affix_not_detail_row() -> None:
    """头部「火热连胜×1」词缀不是明细行(锚点下方守卫)→ 连胜只取明细行值。"""
    items = _items([
        ('火热连胜×1', 700, 300, 150, 30),
        ('获得金币总览', 530, 553, 146, 28),
        ('连胜×2', 528, 702, 113, 35),
    ])
    assert parse_settlement_gold_detail(items)['streak'] == 2


def test_no_anchor_returns_all_none() -> None:
    """无「总览」标题(非结算屏/OCR 全漏)→ 三分量全 None,不抛。"""
    items = _items([('挑战成功', 831, 192, 256, 73)])
    assert parse_settlement_gold_detail(items) == {
        'base': None, 'streak': None, 'interest': None}


def test_missing_value_component_is_none() -> None:
    """某分量标签在、同行数值缺(OCR 漏)→ 该分量 None,其余照读。"""
    items = _items([
        ('获得金币总览', 530, 553, 146, 28), ('基础奖励', 530, 604, 98, 28),
        ('利息', 527, 653, 56, 31), ('4', 1057, 660, 13, 17),
    ])
    assert parse_settlement_gold_detail(items) == {
        'base': None, 'streak': None, 'interest': 4}


def test_value_out_of_range_guard() -> None:
    """三位数/越界值不是明细分量(格式先验 0-99)→ 拒,置 None。"""
    items = _items([
        ('获得金币总览', 530, 553, 146, 28), ('基础奖励', 530, 604, 98, 28),
        ('120', 1051, 605, 40, 25),
    ])
    assert parse_settlement_gold_detail(items)['base'] is None


# ===== 采集钩子契约(jsonl 落盘 / 去重 / 容错;全走 tmp_path) =====

@pytest.fixture()
def _hook_env(tmp_path, monkeypatch):
    """钩子落盘指向 tmp_path + 截图/运行号外部依赖 no-op(测试不触真实 .debug)。"""
    monkeypatch.setattr(cw_settlement_obs, '_GOLD_DETAIL_JOURNAL',
                        tmp_path / 'gold_detail.jsonl')
    monkeypatch.setattr(cw_settlement_obs, '_gold_last_row_key', None)
    import sr_od.application.currency_war.kernel.cw_observe as obs_mod
    monkeypatch.setattr(obs_mod, 'cw_shot_unique',
                        lambda image, label: f'{label}__dead.png')
    import sr_od.application.currency_war.telemetry.state as tel
    monkeypatch.setattr(tel, 'current_run_id', lambda: 'run_x')
    # 分包期 4:gold_detail 的 run_id 归属键读 kernel.cw_telemetry_exit 钩子位,
    # provider 桩随迁(自动还原)
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider', lambda: 'run_x')
    return tmp_path


def test_hook_appends_jsonl_row(_hook_env) -> None:
    texts = [it.data for it in WIN_FRAME]
    collect_gold_detail_hook(object(), texts, WIN_FRAME, plane=1, round_num=8,
                             node_type='奖励', streak_after=0)
    rows = [json.loads(l) for l in
            (_hook_env / 'gold_detail.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 1
    r = rows[0]
    assert (r['run_id'], r['plane'], r['round_num'], r['node_type']) == \
        ('run_x', 1, 8, '奖励')
    assert (r['base'], r['streak'], r['interest']) == (5, 0, 4)
    assert r['shot'] == 'cw_settle__dead.png'


def test_hook_dedup_same_frame(_hook_env) -> None:
    """结算停留期同帧重复读(同 plane/round/文本)只落一行。"""
    texts = [it.data for it in WIN_FRAME]
    for _ in range(3):
        collect_gold_detail_hook(None, texts, WIN_FRAME, plane=1, round_num=8,
                                 node_type='奖励', streak_after=0)
    lines = (_hook_env / 'gold_detail.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1


def test_hook_tolerates_run_id_failure(_hook_env, monkeypatch) -> None:
    """run id 源抛异常 → 行照落,run_id='-'(采集零行为影响,不炸主流程)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    def _boom():
        raise RuntimeError('no session')
    monkeypatch.setattr(tel, 'current_run_id', _boom)
    # 分包期 4:provider 桩随迁出口钩子位(抛异常 → 行照落 run_id='-')
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider', _boom)
    texts = [it.data for it in WIN_FRAME]
    collect_gold_detail_hook(None, texts, WIN_FRAME, plane=2, round_num=1,
                             node_type='普通战斗', streak_after=-1)
    r = json.loads((_hook_env / 'gold_detail.jsonl')
                   .read_text(encoding='utf-8').splitlines()[0])
    assert r['run_id'] == '-'


def test_hook_swallows_journal_failure(_hook_env, monkeypatch) -> None:
    """落盘路径不可用(父级是普通文件,mkdir 必败)→ 吞异常不抛(钩子 best-effort 纪律)。"""
    blocker = _hook_env / 'blocker.txt'
    blocker.write_text('x', encoding='utf-8')
    monkeypatch.setattr(cw_settlement_obs, '_GOLD_DETAIL_JOURNAL',
                        blocker / 'sub' / 'gold_detail.jsonl')
    texts = [it.data for it in WIN_FRAME]
    collect_gold_detail_hook(None, texts, WIN_FRAME, plane=1, round_num=8,
                             node_type='奖励', streak_after=0)   # 不抛即过


# ===== read_round_outcome 接线(同帧产明细 → jsonl) =====

def _ctx_with_items(items: list[_Item]) -> SimpleNamespace:
    return SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=lambda image, rect=None, crop_first=False: items))


def test_read_round_outcome_triggers_hook(_hook_env) -> None:
    """结算帧 → RoundOutcome 照旧 + 旁路 jsonl 落一行明细(零额外 OCR 调用)。"""
    obs = read_round_outcome(_ctx_with_items(WIN_FRAME), None,
                             plane=1, round_num=8, comp_tag='c')
    assert obs.hp_after == 20
    lines = (_hook_env / 'gold_detail.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])['base'] == 5


def test_read_round_outcome_no_detail_frame_still_row(_hook_env) -> None:
    """无明细区帧(面板被遮形态)→ 明细 None 照落行(缺行会伪装「没轮」,假 0 不许)。"""
    items = _items([('挑战成功', 831, 192, 256, 73),
                    ('小队生命值86i', 646, 479, 226, 43)])
    read_round_outcome(_ctx_with_items(items), None,
                       plane=1, round_num=3, comp_tag='c')
    r = json.loads((_hook_env / 'gold_detail.jsonl')
                   .read_text(encoding='utf-8').splitlines()[0])
    assert (r['base'], r['streak'], r['interest']) == (None, None, None)

