"""cw_replay 回放恢复面锁(T-290 意向 latch 回读 + T-291 判读卫生)。

锁面:
1. v3_intention dict → IntentionState 反序列化形状(list→tuple/set、
   tracks 子 dict→LineTrack、未知键宽容忽略——档案跨 schema 版本不炸);
2. _restore_session 意向回读后,锁定/配方对帧的 target_comp 物化
   (派生与 flow._refresh_direction_views 同源);
3. v3_intention=None 行的残源回退(行携顶层 target 标签解析);
4. main() 面:fake_ 前缀 run 恒过滤 + 无 --run 拼接警示头
   (落盘全走 tmp_path,零真实 .debug 副作用)。

消歧正本 = .debug/temp/currency_war/T-286-交付报告.md(回放器语义缺口
消歧说明):LIMITS 旧文案「旧记录无 v3 态」实况是「有态不读」——档案行
携 v3_intention 全量序列化,恢复面(回读代码)此前没跟上。
"""
import json
import sys

from sr_od.application.currency_war.sim import cw_replay


def _session():
    """与 cw_replay.main() 同路的冷建 session(create_session 唯一口)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )
    return MandateV1Strategy().create_session(cw_replay._Cfg())


def _ms(sess):
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )
    return state_of(sess)


#: 档案锁线行的 v3_intention 实际形状抽 self calc 直数(21 键,容器=JSON 形状)
_LOCKED_IST = {
    'phase': 'locked', 'locked_comp': '绯英欢愉', 'p1_pair': [],
    'lock_layer': 3, 'lock_plane': 2, 'lock_round': 2,
    'transition_pair': [], 'forced': False, 'weak_comp': '',
    'demoted_endgame': False, 'evicted': [], 'pair_evicted': [],
    'pair_drought': {'列车同行': 0}, 'shop_supply_streak': {},
    'p1_pair_frozen_obs': ['持续伤害', '列车同行'],
    'p1_pair_frozen': False, 'p1_pair_frozen_pair': [],
    'p1_pair_refreeze_hold': [],
    'tracks': {'绯英欢愉': {'miss_count': 1, 'frozen_rounds': 0,
                            'member_drought': 3}},
    'last_event': 'lock:绯英欢愉', 'revoke_evidence': {},
}


def test_intention_from_trace_shapes() -> None:
    """反序列化形状:list→tuple、tracks 子 dict→LineTrack、未知键忽略。"""
    from sr_od.application.currency_war.kernel.cw_intention import LineTrack

    ist = cw_replay._intention_from_trace(
        dict(_LOCKED_IST, some_future_field=1))
    assert ist.phase == 'locked'
    assert ist.locked_comp == '绯英欢愉'
    assert ist.p1_pair == ()                       # list → tuple
    assert ist.p1_pair_frozen_obs == ('持续伤害', '列车同行')
    assert ist.evicted == set() and ist.pair_evicted == set()
    assert isinstance(ist.tracks['绯英欢愉'], LineTrack)
    assert ist.tracks['绯英欢愉'].miss_count == 1
    assert not hasattr(ist, 'some_future_field')   # 跨版本宽容


def test_restore_session_reads_back_locked_intention() -> None:
    """锁定行回读:v3_intention 在案 → ist 回读 + target 物化为 comp 对象。"""
    from sr_od.application.currency_war.kernel.cw_comps import get_comp

    sess = _session()
    cw_replay._restore_session(None, {'v3_intention': dict(_LOCKED_IST)},
                               sess)
    ms = _ms(sess)
    assert ms.v3_intention is not None
    assert ms.v3_intention.phase == 'locked'
    assert ms.target_comp is get_comp('绯英欢愉')


def test_restore_session_p1_pair_materializes_direction() -> None:
    """P1 配方锁行(locked_comp 空、p1_pair 非空)→ 配方伪 comp 物化。

    物化辖 P1,需快照 plane 判域——黑板先于回读就位(main() 实际调用
    序,顺序倒置 = 物化静默丢失,本用例一并锁调用序契约)。
    """
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )
    from sr_od.application.currency_war.kernel.cw_state import GameState

    ist_dict = dict(_LOCKED_IST, locked_comp='', p1_pair=['仙舟', '持续伤害'])
    sess = _session()
    sess.shop_state_frame = GameState(plane=1, round_num=5)
    cw_replay._restore_session(None, {'v3_intention': ist_dict}, sess)
    expected = pair_target_comp(('仙舟', '持续伤害'))
    assert _ms(sess).target_comp is not None
    # pair_target_comp 每次新建伪 comp(无缓存),按 name 等值比对
    assert _ms(sess).target_comp.name == expected.name


def test_restore_session_none_intention_label_fallback() -> None:
    """v3_intention=None 行:残源 = 行携顶层 target 标签;缺标签 = None 缺省。"""
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )

    sess = _session()
    cw_replay._restore_session(None, {'v3_intention': None,
                                      'target_comp': '绯英欢愉'}, sess)
    assert _ms(sess).target_comp is get_comp('绯英欢愉')

    sess2 = _session()
    cw_replay._restore_session(None, {'v3_intention': None,
                                      'target_comp': '过渡配方·仙舟+持续伤害'},
                               sess2)
    expected = pair_target_comp(('仙舟', '持续伤害'))
    assert _ms(sess2).target_comp is not None
    assert _ms(sess2).target_comp.name == expected.name

    sess3 = _session()
    cw_replay._restore_session(None, {'v3_intention': None}, sess3)
    assert _ms(sess3).target_comp is None


def _write_archive(tmp_path, rows) -> None:
    (tmp_path / 'decisions.jsonl').write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n',
        encoding='utf-8')


def _row(run_id: str, plane: int, round_num: int) -> dict:
    return {'run_id': run_id, 'plane': plane, 'round_num': round_num,
            'actions': [], 'state': {}, 'gold': 0}


def test_main_filters_fake_rows_and_warns_concat(tmp_path, monkeypatch,
                                                 capsys) -> None:
    """无 --run:fake_ 行恒过滤不入回放体 + 打跨局拼接警示头(行数/run 数)。"""
    _write_archive(tmp_path, [
        _row('fake_204482833', 2, 3),
        _row('run_a', 1, 1),
        _row('run_b', 1, 2),
    ])
    monkeypatch.setattr(cw_replay, 'DEFAULT_REPLAY_DIR', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['cw_replay'])
    cw_replay.main()
    out = capsys.readouterr().out
    assert '跨局' in out and '2 个 run' in out
    assert 'fake_ 测试行 1 行' in out
    assert 'fake_204482833' not in out   # 假局 id 不出现在回放输出


def test_main_explicit_fake_run_warns_empty(tmp_path, monkeypatch, capsys) -> None:
    """--run 指向 fake_/未知 id:过滤后零行,打无真实回放行警示。"""
    _write_archive(tmp_path, [_row('fake_x', 1, 1), _row('run_a', 1, 1)])
    monkeypatch.setattr(cw_replay, 'DEFAULT_REPLAY_DIR', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['cw_replay', '--run', 'fake_x'])
    cw_replay.main()
    out = capsys.readouterr().out
    assert '无真实回放行' in out

    # 指向真实 run:无拼接警示、无空行警示
    monkeypatch.setattr(sys, 'argv', ['cw_replay', '--run', 'run_a'])
    cw_replay.main()
    out2 = capsys.readouterr().out
    assert '跨局' not in out2 and '无真实回放行' not in out2
