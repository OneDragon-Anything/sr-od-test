"""战斗等待 op 败局闩键门锁(迭代 2026-10-12-abolish-node-ordinal 3.3;
判据面 = 该迭代 landing §3.3 + 设计 §2.11 锁 7)。

锁面:
- 键门与旧 t 门逐值对拍:(1,10)/(2,1)/(2,4)/(2,5) 边界上新门
  (位面, 轮) >= (2,5) 与旧门 (p-1)*9+r >= 14 逐值同判(含修饰局
  (1,10) 形态——旧 9 制序数 t=10<14 不置闩,新字典序同判);
- 门另两臂语义保持:负分量缺席不置闩;容器节点读口未观察
  fail-closed 不置闩。

驱动 = 裸实例直调 ``_defeat_latch_by_secondary``(先例 =
test_cw_env_grants_live 裸实例;该函数只读容器 node 读口,无画面/OCR
依赖)。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    NodeKey,
    game_state_of,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
    CwScreenBattleWait,
    SettlementState,
)

_SIG_OBS = ChannelSig(family='obs', actor='TestDefeatLatch', mode='read')

#: 面板负分量形态(damage_base < 0 = 次级证据负分量在)。
_NEG_PNL = {'damage_base': -1, 'damage_unfinished_progress': None}


def _make_op(test_context, monkeypatch) -> CwScreenBattleWait:
    """battle_wait 裸实例(先例 = test_cw_env_grants_live._make_op;
    ctx.cw_match 无 gs 属性 → 容器走 session 旁表兜底,与生产同取口
    gs_of_ctx)。"""
    session = cw4_session()
    st = SettlementState(battle_ts=1234.0, run_start_ts=time.monotonic(),
                         is_new_match=False)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op = CwScreenBattleWait.__new__(CwScreenBattleWait)
    op.ctx = test_context
    op._st = st
    return op


@pytest.mark.parametrize('pos', [(1, 10), (2, 1), (2, 4), (2, 5)])
def test_lock7_defeat_latch_gate_matches_old_t_gate(
        test_context, monkeypatch, pos) -> None:
    """败局闩键门与旧 t 门逐值对拍(设计 §2.11 锁 7):旧门
    (p-1)*9+r >= 14 在边界值上的判定 = 新键门 (p,r) >= (2,5) 的实际
    置闩行为,逐值不分叉。"""
    old_t = (pos[0] - 1) * 9 + pos[1]
    expected = old_t >= 14
    op = _make_op(test_context, monkeypatch)
    gs = game_state_of(test_context.cw_match.session)
    gs.observe(gs.node, NodeKey(plane=pos[0], round_num=pos[1], kind='battle'),
               evidence='t', sig=_SIG_OBS)

    op._defeat_latch_by_secondary(dict(_NEG_PNL))

    assert op._st.saw_defeat_settlement is expected, \
        f'{pos}: 新键门与旧 t 门(t={old_t})判定分叉'


def test_lock7_latch_requires_neg_and_node(test_context, monkeypatch) -> None:
    """门另两臂语义保持:面板负分量缺席不置闩(序位过门也不置);
    节点未观察(容器 node 读口 None)fail-closed 不置闩。"""
    op = _make_op(test_context, monkeypatch)
    gs = game_state_of(test_context.cw_match.session)
    gs.observe(gs.node, NodeKey(plane=2, round_num=5, kind='battle'),
               evidence='t', sig=_SIG_OBS)
    op._defeat_latch_by_secondary({'damage_base': 3})   # 非负分量
    assert op._st.saw_defeat_settlement is False

    op = _make_op(test_context, monkeypatch)            # 节点未观察
    op._defeat_latch_by_secondary(dict(_NEG_PNL))
    assert op._st.saw_defeat_settlement is False
