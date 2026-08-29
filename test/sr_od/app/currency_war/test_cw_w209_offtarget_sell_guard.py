"""W209/ADR-0386:deploy 层 off-target 卖出振荡熔断锁(run 26 崩坏根因②)。

事故形态(2026-08-26 run 26,P2r7 用户热键停局):deploy 侧 off-target 卖出
只按终局 ``session.target_comp`` 阵营集判定,把买/演进层仍在买入的引擎·配方
体系件反复卖出——日志实锤 ``sell-offtarget:藿藿(仙舟) ✓``×3 + 丹恒·饮月×2
+ 爻光×1,同期商店 plan 不停 ``Buy(仙舟/藿藿/1)`` 等 = 买→卖→买振荡;
仙舟引擎三人组全下岗 + 列车 2→1。

熔断判据(``deploy_bench.offtarget_sell_allowed`` 纯函数):
引擎/配方体系件(羁绊 ∩ ``_DEPLOY_FENCE`` = RECIPE ∪ ENGINE,与散牌围栏同源)
恒不进 off-target 卖集——deploy 自己都把它们当围栏件不许留 bench,卖出判定
不得同源反向;真要换血走演进层显式 SellDeployed/CompTransaction。
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / 'src'))

from sr_od.application.currency_war.operations.prep.deploy_bench import (
    offtarget_sell_allowed,
)

# run 26 终局 target 阵营集(希儿量子线,日志 target_factions 实录)
_RUN26_TARGET_FACTIONS = {'减益', '持续伤害', '星核猎手', '昼之半神',
                          '盛会之星', '量子同频'}
_RUN26_CORES: set[str] = set()


def test_run26_sold_trio_now_blocked() -> None:
    """run 26 实卖三件(藿藿/饮月/爻光,全羁绊含仙舟)→ 熔断后恒不可卖。"""
    cases = {
        '藿藿': {'仙舟', '治疗', '能量'},
        '丹恒·饮月': {'仙舟', '列车同行', '战技点'},
        '爻光': {'仙舟', '欢愉'},
    }
    for cid, bonds in cases.items():
        assert not offtarget_sell_allowed(cid, bonds, _RUN26_TARGET_FACTIONS,
                                          _RUN26_CORES), \
            f'{cid}(引擎/配方体系件)不得再被 off-target 卖(run 26 振荡熔断)'


def test_true_offtarget_still_sellable() -> None:
    """真 off-target(非 target / 非 core / 非引擎配方体系)照旧可卖——
    熔断只拦体系件,不废 D-10 腾位通道。"""
    assert offtarget_sell_allowed('艾丝妲', {'银河学者'}, _RUN26_TARGET_FACTIONS,
                                  _RUN26_CORES)
    assert offtarget_sell_allowed('风堇', {'记忆'}, _RUN26_TARGET_FACTIONS,
                                  _RUN26_CORES)


def test_core_and_target_members_protected_as_before() -> None:
    """core_char 辅助与 target 阵营成员保留(旧语义不回归)。"""
    assert not offtarget_sell_allowed('花火', {'欢愉'}, _RUN26_TARGET_FACTIONS,
                                      {'花火'})          # core 辅助
    assert not offtarget_sell_allowed('希儿', {'量子同频', '贝洛伯格'},
                                      _RUN26_TARGET_FACTIONS, _RUN26_CORES)  # target 阵营


def test_fence_source_shared_with_deploy_fence() -> None:
    """熔断保留集与散牌围栏 _DEPLOY_FENCE 同源(RECIPE ∪ ENGINE)——
    deploy 不许留 bench 的集合 = 不许卖出的集合,单一源防两处漂移。"""
    from sr_od.application.currency_war.kernel.cw_line_defs import (
        ENGINE_FACTIONS,
        RECIPE_FACTIONS,
    )
    from sr_od.application.currency_war.operations.prep import deploy_bench
    assert frozenset(RECIPE_FACTIONS | ENGINE_FACTIONS) == deploy_bench._DEPLOY_FENCE
    # 引擎阵营抽查:仙舟/列车同行/持续伤害成员均被熔断覆盖
    for bond in ('仙舟', '列车同行', '持续伤害'):
        assert not offtarget_sell_allowed('任意', {bond}, set(), set()), \
            f'{bond} 体系件必须被熔断拦下'
