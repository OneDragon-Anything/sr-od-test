"""货币战争 OpenTome 单击化()动作 op 链路锁。

单击化依据:用户确认 2026-09-25 游戏实际 = 点典籍槽一次即弹星徽四选一
(用户确认口径);原双击序列第二击落在已弹弹窗上有误触风险。
实机核凭据 = 待实机局 journal(代码批先落地,实机验证随迭代收尾)。

锁面:单次点击(选中即开启,无第二击)→ 固定动画等待 → 自上报
(开件腾席 + star_tome 登记);槽载荷匹配。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    consume_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenTomeParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_tome_action import (
    CwActionOpenTomeOp,
)
from sr_od.application.currency_war.prep_actions import PrepExecEnv

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    consume_defect_sink()
    yield
    consume_defect_sink()


def _tome_env(session, clicks: list, monkeypatch):
    """OpenTomeOp 离线执行环境:read_tomes 桩回两典籍槽;控制器记点击;
    time.sleep 桩(固定等待零耗时)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war.obs import cw_identity_obs
    monkeypatch.setattr(
        cw_identity_obs, 'read_tomes',
        lambda ctx, screen: [(1, (301, 302)), (2, (401, 402))])

    class _Ctl:
        def mouse_move(self, pt) -> None:
            pass

        def click(self, pt) -> None:
            clicks.append(pt)

    class _Op:
        screenshot = staticmethod(lambda: object())
        park_cursor = staticmethod(lambda **kw: None)
        ctx = SimpleNamespace(controller=_Ctl(),
                              screen_loader=SimpleNamespace(
                                  get_screen=lambda name: None))

    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor(_Op(), _Op.ctx)
    env = PrepExecEnv(op=_Op(), match=SimpleNamespace(session=session),
                      executor=ex)
    return env


def test_open_tome_single_click_registers_and_clears(
        test_context, monkeypatch):
    """单击链路:一次点击落载荷槽中心(无第二击)→ 自上报腾席 +
    star_tome 登记;槽失配 round_fail 零点击。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    session = StrategySession()
    gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='tome'), BenchSlot(kind='tome')]
        + [BenchSlot(kind='empty')] * 7, capacity=9), sig=_SIG_OBS)

    clicks: list = []
    env = _tome_env(session, clicks, monkeypatch)
    op = CwActionOpenTomeOp(test_context, CwActionOpenTomeParam(slot=2),
                            env=env)
    from test.sr_od.application.currency_war._cw_helpers import (
        run_node,
    )
    rr = run_node(test_context, op, lambda: CwActionOpenTomeOp.run(op))
    assert rr.is_success, '单击开典籍成功(选中即开启)'
    assert len(clicks) == 1 and tuple(clicks[0]) == (401, 402), \
        '恰一次点击落载荷槽中心(双击序列已退役,第二击有误触风险)'
    assert gs.bench.value.slots[1].kind == 'empty', '开件腾席落账'
    assert [p.kind for p in gs.screen_changes.pending] == ['star_tome'], \
        'star_tome 登记在册'

    # 槽失配:零点击零登记
    clicks.clear()
    consume_defect_sink()
    op2 = CwActionOpenTomeOp(test_context, CwActionOpenTomeParam(slot=3),
                             env=env)
    rr2 = run_node(test_context, op2, lambda: CwActionOpenTomeOp.run(op2))
    assert not rr2.is_success and clicks == [], '槽失配 = 零点击(round_fail)'
