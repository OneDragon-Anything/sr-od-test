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
        # W306c:不传 options → 无 options/n_options 键(兜底路径形态容忍)
        assert 'options' not in got and 'n_options' not in got
        assert consume_last_supply_pick() is None   # 清槽:残留不串下一轮
    finally:
        consume_last_supply_pick()   # 测试卫生:无论断言走哪支都清干净


def test_pick_slot_options_dynamic_column_count() -> None:
    """W306c 锁:选项清单按**实际识别列数**记录(n_options=len(options),逐列内容
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
    """弱锁保底:RunSupplyNode 选定分支真接线(set_last_supply_pick + 选项清单透传,
    W306c:options=逐列内容动态列表)。"""
    import inspect

    from sr_od.application.currency_war.operations.run_nodes import run_supply_node
    src = inspect.getsource(run_supply_node.RunSupplyNode._do_action)
    assert 'set_last_supply_pick(' in src
    assert "options=[{'char': o.char" in src   # 逐列内容透传(实际识别列数)


