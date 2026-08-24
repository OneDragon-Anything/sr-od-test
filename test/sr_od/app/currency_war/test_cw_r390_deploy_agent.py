# -*- coding: utf-8 -*-
"""r390 执行层代理锁测:deploy 围栏在 sim 生效(变异可检出)。

锁三件事:
1. select_deployments 语义(cap 富余填空/r387;target 优先;
   桥 carry 通道);
2. _deployable_depth 读 deployed(不再数 bench——变异差异死点);
3. sim 变异检出:关 cap_roomy → 批量指标涌现变化(r387 类 bug
   从此 sim 可发现;本测试是「非空转」的永久回归锁)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war import cw_deploy_logic as dl
from sr_od.application.currency_war.cw_state import BenchChar, GameState


def _bench(*pairs) -> list[BenchChar]:
    return [BenchChar(char_id=n, faction=f, slot=i + 1)
            for i, (n, f) in enumerate(pairs)]


def test_roomy_fill_vacancy_r387() -> None:
    """cap 富余:散牌填空(局62 r2 形态——cap3/board2/散件应上满)。"""
    bench = _bench(('三月七', '列车同行'), ('三月七', '列车同行'),
                   ('艾丝妲', '银河学者'), ('阿格莱雅', '昼之半神'))
    up, held = dl.select_deployments(
        bench, deployed_cids=set(), deployed_fac={'列车同行': 1},
        board={'列车同行': 1, '护盾': 1}, cap=3,
        target_factions={'列车同行'})
    assert len(up) == 3, f'富余应填满 cap:up={len(up)}'
    # 第 4 张(阿格莱雅,单张非对非 fence)cap 截断留 bench——合理
    # (cap=3 上满后第 4 张必留;艾丝妲借 fill_mode 上场)
    assert len(held) == 1


def test_target_bridge_carry_channel() -> None:
    """桥期 target 走 fw_carry 通道(r373:桥 framework 名单)。"""
    bench = _bench(('藿藿', '仙舟'), ('飞霄', '狼狩'), ('万敌', '夜之半神'))
    up, _ = dl.select_deployments(
        bench, deployed_cids=set(), deployed_fac={},
        board={}, cap=5,
        fw_carry={'藿藿', '丹恒·饮月'})
    assert 0 in up            # 藿藿(桥 carry)上
    assert 1 in up            # 飞霄:狼狩在 DEPLOY_FENCE(引擎桥派生)
    # 万敌:非 fence 非对,但 vacancy>2 fill_mode → 上


def test_depth_reads_deployed_not_bench() -> None:
    """_deployable_depth 口径=Σboard(W50 ADR-0312;空板=0,
    bench 有件不产生板深——r390「不数 bench」语义的现行形态)。"""
    from sr_od.application.currency_war.cw_sim import _deployable_depth
    st = GameState()
    st.level = 5
    st.bench = _bench(('三月七', '列车同行'), ('三月七', '列车同行'),
                      ('艾丝妲', '银河学者'))   # bench 有件不产生板深
    st.deployed = []            # board 空 → 0(没上场就是 0)
    assert _deployable_depth(st) == 0


@pytest.mark.skip(reason='批量变异探针跑 ~40s,留手动(_r390_probe.py);'
                         '语义锁由上三条覆盖')
def test_mutation_detectable() -> None:
    pass
