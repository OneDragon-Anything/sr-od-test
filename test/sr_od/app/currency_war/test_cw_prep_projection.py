"""备战投影 ``_project_prep_obs`` 单元锁(对抗修复批 F2/F3)。

- F2:SellBench 投影补 state 侧——bench 槽位摘除 + ``gold += sell_refund``
  (与 ``cw_state.simulate`` 卖出分支同式);消费读路径 = 下一帧决策读
  ``obs.state.gold``(funding_support/凑息卖等金位判据),投影半面缺
  金账 = 决策读「卖出前旧金」半投影。
- F3:OpenBox/OpenTome 投影按 ``action.slot`` 摘对应槽(slot=None =
  首件,与发射形态对齐);旧恒摘首件在 slot≠首件帧摘错对象。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    OpenBox,
    OpenTome,
    PrepObservation,
    SellBench,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)


def _director() -> CwScreenPrep:
    # _project_prep_obs 纯计算不触 self 状态 → 无初始化实例即够
    return object.__new__(CwScreenPrep)


def _obs(state: GameState | None = None) -> PrepObservation:
    return PrepObservation(state=state, free_bench_slots=2)


def _obs_with_boxes() -> PrepObservation:
    obs = _obs()
    obs.boxes = [(2, 'p2'), (5, 'p5'), (7, 'p7')]
    return obs


# ===== F2:SellBench state 侧金账 =====


def test_sellbench_projection_adds_sell_refund_gold() -> None:
    """卖出后投影金 = 原金 + sell_refund(star, bench_char_cost)——与
    simulate 卖出分支同式(单一源公式);下一帧 funding_support 等金位
    判据读 ``obs.state.gold`` 即读到涨后金。"""
    d = _director()
    bc = BenchChar(slot=3, char_id='希儿', star=1)
    obs = _obs(GameState(gold=10))
    obs.bench_chars = [BenchChar(slot=1, char_id='甲', star=1), bc]
    out = d._project_prep_obs(SellBench(slot=3), obs)
    assert out is not None
    assert [b.slot for b in out.bench_chars if b is not None] == [1]
    assert out.free_bench_slots == 3
    expect = 10 + sell_refund(bc.star, bench_char_cost(bc))
    assert out.state is not None and out.state.gold == expect


def test_sellbench_projection_state_none_skips_gold() -> None:
    """state 缺失帧(heavy 未刷新)⇒ 金账跳过不造值,槽位摘除照常
    (保守侧 = 低估回金,下一 heavy 重读对账)。"""
    d = _director()
    obs = _obs(None)
    obs.bench_chars = [BenchChar(slot=2, char_id='乙', star=1)]
    out = d._project_prep_obs(SellBench(slot=2), obs)
    assert out is not None
    assert out.state is None
    assert out.bench_chars == []


def test_sellbench_projection_empty_slot_no_gold_change() -> None:
    """槽位空(卖空槽,策略器 bug 形态)⇒ 无卖出件:金不动、席位数
    照 +1 是既有语义(投影不校验提案合法性,守卫在执行侧)。"""
    d = _director()
    obs = _obs(GameState(gold=10))
    obs.bench_chars = [BenchChar(slot=1, char_id='甲', star=1)]
    out = d._project_prep_obs(SellBench(slot=5), obs)
    assert out is not None
    assert out.state is not None and out.state.gold == 10
    assert out.free_bench_slots == 3, (
        '空槽卖出席位数照 +1(投影不校验提案合法性,守卫在执行侧)')


# ===== F3:OpenBox/OpenTome 按 action.slot 摘 =====


def test_openbox_projection_removes_named_slot() -> None:
    """OpenBox(slot=5) 摘槽 5 的箱,非恒摘首件;slot 缺号帧列表原样
    (无该槽 = 无对象可摘)。"""
    d = _director()
    out = d._project_prep_obs(OpenBox(slot=5), _obs_with_boxes())
    assert out is not None
    assert [b[0] for b in out.boxes] == [2, 7]
    out2 = d._project_prep_obs(OpenBox(slot=9), _obs_with_boxes())
    assert [b[0] for b in out2.boxes] == [2, 5, 7]


def test_openbox_projection_none_slot_first() -> None:
    """slot=None = 首件(与发射形态对齐:未指定槽即点第一件)。"""
    d = _director()
    out = d._project_prep_obs(OpenBox(), _obs_with_boxes())
    assert out is not None
    assert [b[0] for b in out.boxes] == [5, 7]


def test_opentome_projection_removes_named_slot() -> None:
    """OpenTome 同款:按 action.slot 摘;None = 首件。"""
    d = _director()
    obs = _obs()
    obs.tomes = [(1, 't1'), (4, 't4')]
    out = d._project_prep_obs(OpenTome(slot=4), obs)
    assert out is not None
    assert [t[0] for t in out.tomes] == [1]
    out2 = d._project_prep_obs(OpenTome(), obs)
    assert out2 is not None
    assert [t[0] for t in out2.tomes] == [4]


def test_clickspheres_projection_unchanged_semantics() -> None:
    """ClickSpheres 保守清空语义不随本批改动(回归锚)。"""
    d = _director()
    obs = _obs()
    obs.spheres = [('red', 'p'), ('blue', 'q')]
    out = d._project_prep_obs(ClickSpheres(), obs)
    assert out is not None and out.spheres == []
