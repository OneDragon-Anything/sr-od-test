"""r290 current 左移优先行为锁(局20 node=reward 污染根修;r363 锚定版)。

行为锁口径(同库先例 test_cw_r337_behavior.py:锁行为结果不锁源码
字面):用 mock 观测喂 PrepDirector._probe_node_type,断言
session.node_type_current 的推断结果——

- 左移优先:上一备战帧 upcoming[0] 是本轮 current 的推断源,即使
  OCR 直读给出不同的 current 类型(局20 实证:OCR 标签位置门拦不住
  相邻同类标签,current 直读不可信);
- 锚定轮次(r363):同轮多次 probe 不再左移(防同轮超前一位);
- OCR 兜底:仅当左移无值(开局首帧/无历史)时,才采信 OCR 直读。

判据单一源 = prep_director.PrepDirector._probe_node_type 的写入行为;
session 字段语义(upcoming_types/nodeseq_probe_anchor/node_type_current)
见该函数与 r266/r290/r363 注释。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.obs import cw_observation

from sr_od.application.currency_war.prep_director import PrepDirector


def _slot(idx: int, state: str, node_type: str) -> SimpleNamespace:
    """节点行槽位 mock(最小面:idx/state/node_type;hu_dist 仅日志用)。"""
    return SimpleNamespace(idx=idx, state=state, node_type=node_type,
                           hu_dist=None)


def _director_with_session(plane: int, round_num: int,
                           **sess_kw) -> PrepDirector:
    """构造仅暴露 _probe_node_type 依赖面的 director mock(不进真画面)。"""
    d = PrepDirector.__new__(PrepDirector)
    d.screenshot = lambda: None
    d._capture_unrecognized_node_icons = lambda *a, **k: None
    defaults: dict = {
        'node_type_current': None,
        'upcoming_types': [],
        'nodeseq_probe_anchor': None,
        'plane_node_table_plane': None,
        'plane_lengths_seen': None}
    defaults.update(sess_kw)
    sess = SimpleNamespace(**defaults)
    d.ctx = SimpleNamespace(cw_match=SimpleNamespace(
        session=sess,
        last_state=SimpleNamespace(plane=plane, round_num=round_num)))
    sess.last_state = d.ctx.cw_match.last_state
    return d


def _run_probe(monkeypatch, director: PrepDirector,
               slots: list[SimpleNamespace]) -> None:
    monkeypatch.setattr(cw_observation, 'read_node_sequence',
                        lambda ctx, screen: slots)
    PrepDirector._probe_node_type(director)


def test_left_shift_takes_priority_over_ocr_read(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """r290:左移推断优先——OCR current 直读与左移源冲突时信左移。

    局20 实证形态:上帧 upcoming[0]=reward(真 current),本帧 OCR
    把 current 槽误读为 battle(相邻同类标签污染)→ current 必须
    取左移值 reward,不信 OCR。"""
    d = _director_with_session(plane=1, round_num=3,
                               upcoming_types=['reward'],
                               nodeseq_probe_anchor=(1, 2))
    _run_probe(monkeypatch, d, [
        _slot(0, 'past', '?'),
        _slot(1, 'current', 'battle'),   # OCR 误读
        _slot(2, 'upcoming', 'encounter'),
    ])
    assert d.ctx.cw_match.session.node_type_current == 'reward'


def test_same_round_reprobe_does_not_advance(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """r363 锚定轮次:同轮多次 probe 不左移(current 不超前一位)。

    开店/关店/重开导致同轮多次 probe 时,upcoming 还是本轮的——
    再左移会把 current 写成下一节点。锚 (plane, round) 未变 →
    不动 current,只刷新本帧 upcoming。"""
    d = _director_with_session(plane=1, round_num=3,
                               node_type_current='reward',
                               upcoming_types=['reward'],
                               nodeseq_probe_anchor=(1, 3))
    _run_probe(monkeypatch, d, [
        _slot(1, 'current', 'battle'),
        _slot(2, 'upcoming', 'encounter'),
    ])
    assert d.ctx.cw_match.session.node_type_current == 'reward'
    # 本帧 upcoming 照常刷新(下轮左移源)
    assert d.ctx.cw_match.session.upcoming_types == ['encounter']


def test_ocr_fallback_only_when_no_shift(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """OCR 直读只在无左移源时兜底(开局首帧:无历史 upcoming)。"""
    d = _director_with_session(plane=1, round_num=1,
                               upcoming_types=[],
                               nodeseq_probe_anchor=None)
    _run_probe(monkeypatch, d, [
        _slot(1, 'current', 'battle'),
        _slot(2, 'upcoming', 'encounter'),
    ])
    assert d.ctx.cw_match.session.node_type_current == 'battle'
    assert d.ctx.cw_match.session.upcoming_types == ['encounter']
    # 锚已落,下一轮起走左移链
    assert d.ctx.cw_match.session.nodeseq_probe_anchor == (1, 1)
