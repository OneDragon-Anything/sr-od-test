"""占位件登记表真值对账 + 卖出拒绝语义锁(T-216 幽灵箱修复 + T-23 卖出语义对齐)。

缺陷链与语义演进(单一源 = 各批交付报告与账本,此处只留锁面需要的语义):

- T-209④ → T-216:P1 商店段策略器把箱占位件列为卖出候选并合法卖出
  (kernel ``simulate`` 不识 is_item_slot)→ ``FakeMatch.boxes`` 登记表
  残留幽灵槽号 → 后续买入落座原箱槽后,P2 备战 OpenBox 对幽灵槽恒拒
  死循环。T-216 修复 = applied 转移后登记表对账
  (``_reconcile_item_slot_registry``)。
- T-18(主仓):fuel_sell_candidates 资格面占位件物理门——策略腾席通道
  不再发射卖占位件。
- T-23(v8):实机真值「箱不可卖」(T-15 实机采证定谳:同参数拖拽,
  角色 9 连全卖、箱零效果)落环境层——SellBench 对占位件 = 规则层拒绝
  applied=False,幽灵链在源头断绝;登记表对账保留 = kernel 未来写路径
  的纵深防线(门辖「发射前」,对账辖「转移后」,互不替代)。

本文件锁:

- **卖出拒绝锁**:卖箱/卖典籍 applied=False、占位件不离席、登记表照旧、
  金账零变化;实角色卖出不受门影响(对照臂,门越界即红)。
- **对账纵深锁**(白盒):kernel 侧写路径清掉占位件槽(直清模拟)后,
  任一 applied 转移的对账点把失效槽从登记表剔除,活槽不误删。
- **正常开箱/开典籍流程不受对账影响**(幂等)。
- **登记表≡真值恒等锁**(P1 全段真实策略链,慢桶):不变式对全部路径
  成立——红 = 对账点被拆/卖出拒绝被拆/新 kernel 分支再引入脱节面。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fixtures.cw_fake_game.fake_match import FakeMatch
from fixtures.cw_harness import fake_p1_run

from test.conftest import SrTestContext
from test.harness.fixture_controller import enter_running_state, reset_running_state


def _item_slots(match: FakeMatch) -> list[int]:
    """bench 占位件真值槽号(1 基;对账判据同源现算)。"""
    return sorted(i + 1 for i, b in enumerate(match.state.bench)
                  if b is not None and b.is_item_slot)


def test_sell_item_slot_refused_env_v8() -> None:
    """卖出拒绝锁(v8):SellBench 对箱/典籍占位件 = 规则层拒绝。

    动作形 = 策略腾席发射位的真实形态(``SellBench(bench_idx=槽-1,
    expect='')``,expect 空放行见 kernel SellBench 分支守卫)。
    applied=False、零状态变化(金账/占位件在席/登记表三面钉死)。
    """
    from sr_od.application.currency_war.kernel.cw_vocab import SellBench

    m = FakeMatch(seed=7, node_sequence=['battle'])
    # —— 箱:spawn → 卖 → 拒绝且三面零变化 ——
    box_slot = m.spawn_box()
    assert box_slot is not None and m.boxes == [box_slot]
    gold_pre = m.state.gold
    res = m.apply(SellBench(bench_idx=box_slot - 1, expect=''))
    assert res.applied is False, '占位件卖出被放行(v8 拒绝门回潮)'
    assert res.income is None, '拒绝路径携带卖出回金'
    assert m.state.gold == gold_pre, '拒绝路径动了金账'
    box = m.state.bench[box_slot - 1]
    assert box is not None and box.is_item_slot, '拒绝路径占位件离席'
    assert m.boxes == [box_slot], '拒绝路径登记表变动'
    # —— 典籍:同构同门 ——
    tome_slot = m.spawn_tome()
    assert tome_slot is not None and m.tomes == [tome_slot]
    assert m.apply(SellBench(bench_idx=tome_slot - 1, expect='')).applied \
        is False, '典籍占位件卖出被放行(同门回潮)'
    assert m.tomes == [tome_slot]

    # —— 对照臂:实角色卖出不受门影响(门只辖占位件,越界即红)——
    ch = m._draw_pool_char_to_bench()
    assert ch is not None, '场景前置:牌池抽角色入座失败'
    real_idx = m.state.bench.index(ch)
    res2 = m.apply(SellBench(bench_idx=real_idx, expect=''))
    assert res2.applied, '实角色卖出被误拒(拒绝门越界)'


def test_reconcile_prunes_cleared_slot_on_applied_transfer() -> None:
    """对账纵深锁(白盒,T-216 语义保留):kernel 写路径清掉占位件槽后,
    applied 转移的对账点把失效槽剔除。

    驱动形 = 直清 bench 槽(等价模拟 kernel 侧转移清占位件的效果——
    v8 后现役 kernel 分支无此形,锁的是对账判据本身与未来分支)+
    一次普通 applied 转移(卖实角色)触发对账点。
    """
    from sr_od.application.currency_war.kernel.cw_vocab import SellBench

    m = FakeMatch(seed=7, node_sequence=['battle'])
    box_slot = m.spawn_box()
    tome_slot = m.spawn_tome()
    assert box_slot is not None and tome_slot is not None
    # 直清箱槽 = 模拟 kernel 写路径清占位件(登记表不自知)
    m.state.bench[box_slot - 1] = None
    ch = m._draw_pool_char_to_bench()
    assert ch is not None
    res = m.apply(SellBench(bench_idx=m.state.bench.index(ch), expect=''))
    assert res.applied, '场景前置:实角色卖出未落地(对账触发器失效)'
    assert box_slot not in m.boxes, \
        '失效槽未被对账剔除(对账点失效,T-216 语义回潮)'
    assert m.tomes == [tome_slot], '活典籍槽被对账误删'


def test_normal_open_flow_unaffected() -> None:
    """正常开箱/开典籍流程不受拒绝门与对账影响(幂等):
    spawn → OpenBox/OpenTome → 登记表同步 + 浮层弹出。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        OpenBox,
        OpenTome,
    )

    m = FakeMatch(seed=7, node_sequence=['battle'])
    slot2 = m.spawn_box()
    assert slot2 is not None
    res = m.apply_prep(OpenBox(slot=slot2))
    assert res.applied, '正常开箱被对账/拒绝门破坏(幂等破缺)'
    assert m.boxes == [] and m.top_overlay('box') is not None, (
        '开箱后登记表/浮层状态异常(误删活箱)')
    # 开典籍同款
    slot3 = m.spawn_tome()
    assert slot3 is not None
    assert m.apply_prep(OpenTome(slot=slot3)).applied
    assert m.tomes == [] and m.top_overlay('star_tome') is not None


#: P1 全段剧本(与保真批同段:5 节点覆盖收入四分量与结算两态)。
_SCRIPT: list[str] = ['battle', 'reward', 'battle', 'supply', 'boss']

#: 种子集:11/101 = T-216 探针案发局(v7 前幽灵必现);23/57 = 既有保真批
#: 种子(未案发局回归保护)。v8 后案发形在源头拒绝,种子保留 = 轨迹位移
#: 局的不变式回归保护。显式固定保确定性。
_SEEDS: tuple[int, ...] = (11, 23, 57, 101)


@pytest.mark.slow
def test_p1_registry_matches_truth_full_chain(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """登记表≡真值恒等锁(P1 全段真实策略链):局末 boxes/tomes 与
    bench is_item_slot 真值恒等。红 = 对账点被拆/卖出拒绝门被拆/kernel
    新分支再引入脱节面。案发种子逐位可复现(确定性契约),锁红即按
    seed 复现路径下钻。"""
    violations: list[str] = []
    enter_running_state(test_context)
    try:
        for seed in _SEEDS:
            with fake_p1_run(test_context, monkeypatch, tmp_path, seed,
                             node_sequence=_SCRIPT, initial_gold=30,
                             archive_dir_name=f'registry_{seed}') as run:
                run.run_p1()
                m = run.match
                truth = _item_slots(m)
                if sorted(m.boxes) != truth:
                    violations.append(
                        f'seed={seed}: boxes={sorted(m.boxes)} '
                        f'≠ bench占位件真值 {truth}(幽灵箱)')
                # tomes 恒等判据:登记表内槽号必须全部仍是占位件
                # (占位件归属箱/典籍不可从 bench 区分,恒等判据只辖
                # 「登记 ⊆ 真值」——幽灵判据与 boxes 同式)
                ghost_tomes = [s for s in m.tomes
                               if not m._slot_holds_item(s)]
                if ghost_tomes:
                    violations.append(
                        f'seed={seed}: tomes 幽灵槽号 {ghost_tomes}')
    finally:
        reset_running_state(test_context, test_context.cw_match)
    assert not violations, (
        '占位件登记表与 bench 真值脱节(对账点失效/新脱节面):\n'
        + '\n'.join(violations))
