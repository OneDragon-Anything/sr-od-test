"""SimBackend planner 呈现分支候选合成单测(``_present_planner_options``;
架构正本 = docs/develop/sr_od/application/currency_war/sim/sim-design.md §6.4
观察生成器「生成器从状态副本填结构体」;同族样板 =
``_present_megastar_options``)。

锁的故障形态:后端呈现 planner 模态却不合成候选 → 生成器 ``gen_planner``
自读自写回空 → 画面 op 决策无候选(sim 局到策划事件节点必崩退)。约定:
- 呈现即写槽:模态呈现后 ``planner_opts`` 恒两卡(0 左 / 1 右),生成器
  ``gen_planner`` 回读同两卡(写端 ↔ 读端闭环);
- 合成口径随现费用档:档 < 5 → [升费卡(含「提升费用」+ 目标档 = 现档 + 1),
  非升费卡];档 ≥ 5 → 两卡皆非升费(费用封顶);
- 升费链落地:呈现的两卡经真实决策(``decide_planner`` 按文案命中升费卡,
  非兜底)→ 真实上报(``report_action_pick_planner_param`` 升费分支)→
  档 + 1、2★ 变 1★。

直构 SimBackend(开局序列纯内存);断言依据全部来自测试自造 bench 视图。
"""

from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
    report_action_pick_planner_param,
)
from sr_od.application.currency_war.kernel.cw_economy import effective_cost
from sr_od.application.currency_war.kernel.cw_events import (
    PLANNER_LEG_UPGRADE,
    classify_planner_branch,
    decide_planner,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    KIND_SCREEN_NAMES,
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickPlannerParam,
)
from sr_od.application.currency_war.sim import cw_sim_backend
from sr_od.application.currency_war.sim.cw_sim_backend import SCREEN_PLANNER
from sr_od.application.currency_war.sim.cw_sim_base import obs_sig
from sr_od.application.currency_war.sim.cw_sim_obs_gen import observe_screen
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG_OBS = obs_sig(group_id='test')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test')

#: 开局 HP 查表唯一实证档(RunConfig 字段注释;sim 构造期校验按档查表)。
_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)

#: 升费关键词(决策词表与记账分类词表同字面;kernel cw_events)。
_UPGRADE_KEYWORD = '提升费用'


def _make_backend() -> cw_sim_backend.SimBackend:
    return cw_sim_backend.SimBackend(seed=0, cfg=_CFG)


def _bench_with_wolf(star: int) -> BenchView:
    """9 槽席位视图:物理槽 1 放指定星级的银狼 LV.999,其余槽放互不相干
    的 1 星单位(无 3 合 1 素材,升费后的合成级联零触发)。"""
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='银狼LV.999', star=star))]
    slots += [BenchSlot(kind='unit', unit=Unit(char_id=f'c{i}', star=1))
              for i in range(1, 9)]
    return BenchView(slots=slots, capacity=9)


def _present_planner(backend: cw_sim_backend.SimBackend) -> None:
    """登记一条待呈现 planner 弹窗 → 步界呈现检查(生产入口)。"""
    register_screen_change(backend.gs, 'planner',
                           KIND_SCREEN_NAMES['planner'], source='test')
    backend._present_pending_overlay()


def _set_tier(backend: cw_sim_backend.SimBackend, tier: int) -> None:
    backend.gs.write_logic(backend.gs.lv999_cost_tier, tier,
                           produced_by='test', sig=_SIG_LOGIC)


@pytest.mark.parametrize('tier', [3, 4])
def test_present_synthesizes_upgrade_card_and_generator_reads_back(
        tier: int) -> None:
    """档 < 5:呈现后槽内两卡(0 左 / 1 右)——左卡含「提升费用」且目标档 =
    现档 + 1,右卡非升费;生成器 ``gen_planner`` 回读同两卡。"""
    backend = _make_backend()
    _set_tier(backend, tier)

    _present_planner(backend)

    assert backend._screen == SCREEN_PLANNER
    opts = backend.gs.planner_opts.value
    assert [o.idx for o in opts] == [0, 1], f'应恒两卡 0 左/1 右,实际 {opts!r}'
    assert _UPGRADE_KEYWORD in opts[0].text, opts[0].text
    assert f'{tier + 1}费' in opts[0].text, opts[0].text
    assert _UPGRADE_KEYWORD not in opts[1].text, opts[1].text
    obs = observe_screen(backend, SCREEN_PLANNER)
    assert [o.text for o in obs.options] == [o.text for o in opts], \
        '生成器应原样回读呈现写点的两卡'


def test_present_at_tier_ceiling_has_no_upgrade_card() -> None:
    """档 ≥ 5(费用封顶):两卡皆非升费且互不相同。"""
    backend = _make_backend()
    _set_tier(backend, 5)

    _present_planner(backend)

    opts = backend.gs.planner_opts.value
    assert len(opts) == 2, f'应恒两卡,实际 {opts!r}'
    assert all(_UPGRADE_KEYWORD not in o.text for o in opts), opts
    assert opts[0].text != opts[1].text, opts


def test_synthesized_cards_land_upgrade_through_real_decision_and_report() -> None:
    """升费链落地(开局档语义默认 3):呈现两卡 → 真实决策按文案命中升费卡
    (reason 为升费非兜底)→ 真实上报升费分支 → 档 + 1、2★ 变 1★、planner
    登记被消费。"""
    backend = _make_backend()
    backend.gs.observe(backend.gs.bench, _bench_with_wolf(star=2), sig=_SIG_OBS)
    tier_before = effective_cost(backend.gs, '银狼LV.999')

    _present_planner(backend)
    options = backend.gs.planner_opts.value
    pick = decide_planner(options, backend.gs, None)
    branch_type, norm_item = classify_planner_branch(options[pick.idx].text)

    assert pick.reason.startswith('升费'), \
        f'应按文案命中升费卡(非兜底左卡),实际 reason={pick.reason!r}'
    assert (branch_type, norm_item) == (PLANNER_LEG_UPGRADE, '')
    outcome = report_action_pick_planner_param(
        backend.gs, CwActionPickPlannerParam(idx=pick.idx), _SIG_LOGIC,
        branch_type=branch_type, norm_item=norm_item)

    assert outcome.applied, f'升费分支应受理,实际 {outcome.reason!r}'
    assert backend.gs.lv999_cost_tier.value == tier_before + 1
    wolf = backend.gs.bench.value.slots[0].unit
    assert wolf is not None and wolf.star == 1, \
        f'升费后银狼应变 1 星,实际 {wolf!r}'
    assert backend.gs.screen_changes.pending == [], '选卡上报应消费 planner 登记'
