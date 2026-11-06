"""商店提案守卫测试(镜像 src = operations/cw_op/cw_shop_action_ops.py
的 ``guard_proposal_vs_expected``;投影测试族双响防御面落位)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionSellBenchParam,
)


def _gs_of(**axes):
    """投影场景种子(原裸帧合成配方承接:节点整域不写、空店离屏;
    域覆盖集与原合成口逐域一致)。"""
    return cw4_gs(node_fill=False, shop_screen='off', **axes)


class TestGuardProposalVsMainDomain:
    """商店提案守卫:expected 侧 = 主域席位视图(3.2 单账化;历史病灶 =
    2026-09-09 双响事故,满栏合成买在第二账丢件 → 同 visit 下一动作
    守卫对拍误炸;单账后分叉结构性不可能,守卫对拍主域即闭环)。
    分叉停机路径 = AssertionError 响亮炸出(禁静默跳过)。"""

    def test_stale_bench_idx_empty_slot_raises(self):
        """卖出提案指向主域空槽(跨代际提案)→ AssertionError 停机
        (空槽形 = 槽内无身份 → 名-槽不一致分支,actual 空)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_proposal_vs_expected,
        )
        gs = _gs_of(bench=[_bc('花火', star=1)])   # 仅槽 1 占用
        with pytest.raises(AssertionError, match='名-槽不一致|空槽|越界'):
            guard_proposal_vs_expected(
                CwActionSellBenchParam(bench_idx=3, expect='花火'), gs)

    def test_expect_name_mismatch_raises(self):
        """卖出提案 expect 名与主域槽内身份不符(名-槽漂移)→ 炸出。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_proposal_vs_expected,
        )
        gs = _gs_of(bench=[_bc('花火', star=1)])
        with pytest.raises(AssertionError, match='名-槽不一致'):
            guard_proposal_vs_expected(
                CwActionSellBenchParam(bench_idx=0, expect='刃'), gs)

    def test_healthy_proposal_passes_and_buy_off_shop_raises(self):
        """健康提案零炸出(主域对得上);买牌提案指向店外牌 → 炸出
        (跨代际/已消费提案 = 策略器 bug 暴露)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_proposal_vs_expected,
        )
        gs = _gs_of(gold=30, shop=[_card('花火', cost=3)], bench=[])
        assert guard_proposal_vs_expected(
            CwActionSellBenchParam(bench_idx=0, expect=''), gs) is None
        assert guard_proposal_vs_expected(
            CwActionBuyCardParam(card=_card('花火', cost=3)), gs) is None
        with pytest.raises(AssertionError, match='不在期望态店中'):
            guard_proposal_vs_expected(
                CwActionBuyCardParam(card=_card('刃', cost=3)), gs)
