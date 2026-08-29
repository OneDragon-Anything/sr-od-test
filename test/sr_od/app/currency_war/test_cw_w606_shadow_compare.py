"""W606 批③·影子比对隔离与留证锁(协议门1;设计 §7.1)。

编排者放行条件②的锁面:影子路径零当权风险——
1. 全隔离:影子 decide 用深拷贝 session(旧 decide 副作用不重放),
   策略在影子 session 上的变异不回写原 session;
2. 异常隔离:影子内部任何异常只计 error 计数,绝不上抛、绝不影响
   现役决策;
3. 逐位对照与计数:一致 → match+1;分歧 → divergence+1 + 记录;
4. 记录落盘可注入目录(测试零真实 .debug 写入)。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_assembly import (
    SHADOW_STATS,
    shadow_compare_step,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    OpenBox,
    PrepObservation,
    SellBench,
)


class _Strat:
    """可编程假策略(返回动作,可选变异 session / 抛异常)。"""

    def __init__(self, action_factory, mutate=False, boom=False):
        self._factory = action_factory
        self._mutate = mutate
        self._boom = boom

    def decide_prep_action(self, obs, session, config):
        if self._boom:
            raise RuntimeError('影子内部爆炸')
        if self._mutate:
            session.prep_phase = 99   # 副作用只应落在深拷贝上
        return self._factory()


def _run(strategy, old_action, session=None):
    """跑一步影子,返回 (jsonl 行, 影子后原 session)。"""
    import tempfile
    from pathlib import Path
    sess = session or StrategySession()
    before_stats = dict(SHADOW_STATS)
    with tempfile.TemporaryDirectory() as td:
        shadow_compare_step(director=None, match=SimpleNamespace(strategy=strategy),
                            obs=PrepObservation(), session=sess, config=None,
                            old_action=old_action, out_dir=td)
        files = list(Path(td).glob('compare_*.jsonl'))
        assert len(files) == 1
        lines = [json.loads(line) for line in
                 files[0].read_text(encoding='utf-8').splitlines()]
    return lines, sess, before_stats


def test_matching_action_counts_match():
    lines, _sess, before = _run(_Strat(lambda: OpenBox()), OpenBox())
    assert SHADOW_STATS['match'] == before['match'] + 1
    assert lines[-1]['old'] == lines[-1]['new']


def test_divergent_action_counts_and_records():
    lines, _sess, before = _run(_Strat(lambda: SellBench(3)), OpenBox())
    assert SHADOW_STATS['divergence'] == before['divergence'] + 1
    assert lines[-1]['old'] != lines[-1]['new']


def test_shadow_error_isolated_not_raised():
    """影子内部爆炸 → error 计数留证,绝不上抛(零当权风险核心锁)。"""
    lines, _sess, before = _run(_Strat(lambda: None, boom=True), OpenBox())
    assert SHADOW_STATS['error'] == before['error'] + 1
    assert 'error' in lines[-1]


def test_shadow_session_isolation_side_effects_not_replayed():
    """旧 decide 的 session 副作用(prep_phase 前移类)不得重放到原 session。"""
    sess = StrategySession()
    assert sess.prep_phase == 0
    _run(_Strat(lambda: OpenBox(), mutate=True), OpenBox(), session=sess)
    assert sess.prep_phase == 0   # 变异只发生在影子深拷贝上


def test_shadow_control_flow_signature_compare():
    """控制流动作(Defer/Bail 族)按 control 标记对照,与 op 不混判。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import DeferSpheres
    lines, _sess, before = _run(_Strat(lambda: DeferSpheres()), DeferSpheres())
    assert SHADOW_STATS['match'] == before['match'] + 1
    assert lines[-1]['old'][0] == 'control' and lines[-1]['new'][0] == 'control'
