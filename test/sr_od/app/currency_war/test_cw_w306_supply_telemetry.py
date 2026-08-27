"""W306 行为锁:补给节点选择写入 synthetic_supply 合成行(选择+刷新+金 快照)。

实证缺口(W23/cw_node_validate「P1 r5 补给行 34/34 全缺」的语义补齐):W28 已接
合成行(节点通过/hp),但补给的**选择**(角色+装备)与**效果归因**(如治疗生效)
在 rounds 判读时无据可查。修法三段:
①生产者 RunSupplyNode 选定+确认 → cw_telemetry.set_last_supply_pick 暂存;
②消费者 battle_loop._record_supply_outcome → consume_last_supply_pick 取走+
 附完成时点 gold,经 record_outcome(supply_pick=...) 落账;
③OutcomeRecord.supply_pick 可选字段(schema 末尾追加,None 缺省旧记录兼容)。

纯逻辑/桩测试(monkeypatch 构造;TelemetryRecorder 指 tmp_path,不写真实 .debug)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war import cw_telemetry
from sr_od.application.currency_war.cw_performance import RoundOutcome
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_telemetry import (
    TelemetryRecorder,
    consume_last_supply_pick,
    read_jsonl,
    set_last_supply_pick,
)

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
        assert consume_last_supply_pick() is None   # 清槽:残留不串下一轮
    finally:
        consume_last_supply_pick()   # 测试卫生:无论断言走哪支都清干净


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

    monkeypatch.setattr(bl.cw_telemetry, 'record_outcome', _fake_record_outcome)
    # consume_last_supply_pick 注入:battle_loop 经模块属性消费(cw_telemetry.*)
    monkeypatch.setattr(cw_telemetry, 'consume_last_supply_pick', lambda: pick)
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
    """弱锁保底:RunSupplyNode 选定分支真接线(set_last_supply_pick 调用)。"""
    import inspect

    from sr_od.application.currency_war.operations.run_nodes import run_supply_node
    src = inspect.getsource(run_supply_node.RunSupplyNode._do_action)
    assert 'set_last_supply_pick(' in src


# ===== W306b 补给备战状态采集 detour =====


def _make_supply_op(monkeypatch):
    """构 RunSupplyNode 桩(__new__ 绕过 op __init__;只喂 detour 依赖面)。

    返回 (op, decision_captured)。round_by_find_and_click_area 全成功;
    截图恒为同一伪帧(离线桩);read_game_state 桩出确定值。
    """
    from sr_od.application.currency_war.operations.run_nodes import run_supply_node as m

    decision_captured: list[dict] = []

    monkeypatch.setattr(cw_telemetry, 'record_decision',
                        lambda state, target_comp='', candidate_scores=None,
                        eval_breakdown=None, actions=None, gold_point=True,
                        extra=None: decision_captured.append(
                            {'target_comp': target_comp,
                             'actions': list(actions or []),
                             'gold_point': gold_point,
                             'extra': dict(extra or {})}))
    monkeypatch.setattr(m, 'read_game_state',
                        lambda ctx, screen: GameState(hp=88, gold=66, plane=1,
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
    """重进失败 → 本轮不做任何选择动作(防备战屏盲点卡身),交下轮 _in_node 判定。"""
    from sr_od.application.currency_war.operations.run_nodes import run_supply_node as m

    op, captured = _make_supply_op(monkeypatch)

    def _fail_reenter(screen, sn, an, **kw):
        # 「返回备战界面」成功;备战侧「按钮-返回补给阶段」恒失败 → 重进不通
        if an == '按钮-返回备战界面':
            return SimpleNamespace(is_success=True)
        return SimpleNamespace(is_success=False)
    op.round_by_find_and_click_area = _fail_reenter

    pick_calls: list = []
    monkeypatch.setattr(m, 'read_supply_options',
                        lambda ctx, screen: pick_calls.append(screen) or [])
    monkeypatch.setattr(m.cw_telemetry, 'consume_last_supply_pick', lambda: None)
    op._do_action(object())
    assert len([r for r in captured
                if r['extra'].get('phase') == 'supply_detour']) == 1
    assert pick_calls == []   # 未进入选择读帧(detour 失败即止)


def test_detour_semantics_lock_in_source() -> None:
    """弱锁:detour 快照带 phase='supply_detour' 且 actions=[](非购买轮语义)。"""
    import inspect

    from sr_od.application.currency_war.operations.run_nodes import run_supply_node
    src = inspect.getsource(run_supply_node.RunSupplyNode._supply_detour_collect)
    assert "extra={'phase': 'supply_detour'}" in src
    assert 'actions=[], gold_point=True' in src
