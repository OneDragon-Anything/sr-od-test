"""检查的变异自检锁(锁防锁第 3 层):冷启动门失效 → 检查必须报警。

把审查 316ebbc0 的一次性变异探针(去门重跑,违规涌现)固化为
CI 回归:check_coldstart_seed_squander 若被改坏(恒绿)/sim 集成
断裂(账本 reason 不再流通),本锁红——「0 违规=门真过滤」从此
不靠人记,靠 CI 钉死。方法论:skill verification.md「检查的非
空转验证(变异探针)」。
"""
from __future__ import annotations

import contextlib
import io


def test_mutation_gate_off_violations_emerge(monkeypatch) -> None:
    """去门变异(恢复 pre-r368 A5 放行语义)→ 小批次涌现违规。

    变异 = _pair_wants 换 pre-r368 A5 语义(owned<3 放行一切)——
    局49 原始失效形态;若检查报 0 违规 = 检查静默失效。
    """
    from sr_od.application.currency_war.cw_sim import simulate_p1_batch
    from sr_od.application.currency_war.strategies.line_strategy import (
        LineStrategy,
    )

    def _gate_off(card, state, session=None):   # noqa: ANN001
        owned = set(state.board.keys())
        for b in (state.bench or []):
            if b is None:
                continue   # ADR-0316 槽位表空槽(变异体同生产适配)
            if b.faction and b.faction != '?':
                owned.add(b.faction)
        return len(owned) < 3 or card.faction in owned

    monkeypatch.setattr(LineStrategy, '_pair_wants',
                        staticmethod(_gate_off))
    with contextlib.redirect_stderr(io.StringIO()):
        rep = simulate_p1_batch(15, pool='fallback', checks=True,
                                ledger=False)
    v = rep['checks_violations']['coldstart_direction']['violations']
    assert v > 0, (
        '去门变异下检查 0 违规 = 检查静默失效(恒绿)——对照审查\n'
        '316ebbc0 变异1:同型变异曾涌现 44 笔 pair/15 局违规')


def test_baseline_gate_on_zero_violations() -> None:
    """基线对照:门在位时同批次 0 违规(非空转的反面锚)。"""
    from sr_od.application.currency_war.cw_sim import simulate_p1_batch
    with contextlib.redirect_stderr(io.StringIO()):
        rep = simulate_p1_batch(15, pool='fallback', checks=True,
                                ledger=False)
    assert rep['checks_violations']['coldstart_direction']['violations'] == 0
