"""行为锁:位面详情 overlay 主循环兜底分支(0 系名单)+ 采集 op 失败退出关详情契约。

背景(2026-08-30 判读):残局恢复局中位面情报采集因节点条持续非clean超限
失败退出,位面详情屏滞留画面;主循环无对应分支 → 未识别兜底自停,对局中断。
治本两腿:

1. 采集 op 失败退出路径(非clean 超限放弃/位面卡缺失)先尽力关详情
   (op 出口契约=回备战屏;行为锁在 test_cw_w314_plane_intel_wait_clean 锁③);
2. 主循环 0 系 overlay 名单补位面详情分支(ADR-0269「新增画面忘进名单」
   结构性缺口;本文件锁分支存在性与分支序)。
"""
from __future__ import annotations


def test_loop_has_plane_detail_overlay_branch() -> None:
    """主循环 0 系名单含位面详情分支:标题识别 + 关闭键点击,且先于恢复局
    锁定分支(overlay 先消化,不污染其后的商店探针/出战判读)。"""
    import inspect

    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert '标识-位面详情标题' in src, '主循环缺位面详情 overlay 识别分支'
    assert "'货币战争-位面详情', '按钮-关闭位面详情'" in src, (
        '位面详情分支应点关闭键(按钮-关闭位面详情)')
    i_branch = src.index('0a4. 位面详情 overlay')
    i_resume = src.index('恢复局锁定确认')
    assert i_branch < i_resume, (
        '位面详情分支必须先于恢复局锁定分支(overlay 先消化再走 in-match 逻辑)')


def test_collect_fail_paths_close_detail() -> None:
    """采集 op 两失败退出路径(非clean 超限放弃/位面卡缺失)都应先调
    _best_effort_close_detail(出口契约=回备战屏)。"""
    import inspect

    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel,
    )

    src = inspect.getsource(collect_plane_intel.CollectPlaneIntel)
    assert src.count('_best_effort_close_detail()') >= 2, (
        '放弃采集与位面卡缺失两条失败路径都应先尽力关详情')
