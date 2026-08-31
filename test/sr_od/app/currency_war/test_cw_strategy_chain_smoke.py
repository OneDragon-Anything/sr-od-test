"""策略链冒烟(r98):核心决策入口 import + 调用级冒烟,防「import 错路径直到实跑才爆」。

背景(r98,局15/16/18 三局同病根):_stash_form_progress 里写了不存在的模块路径
``from one_dragon.utils import calc_utils`` → 进攒息门的 plan 调用全部 ImportError →
buy op retry 4 次失败 → 0 买出战。三个局的「钱变不成板」都是这一个静态错误,
但直到留证钩子(r95)+日志 append 生效才抓到。单测只测各自函数,没人调决策链全链
→ import 错误漏网。本文件锁:策略链入口模块全部可导入 + 关键决策函数真调用一遍。

(default 栈退役批重写:v2 决策链冒烟——decide_prep 全链真调用四层
候选→过滤→评分→仲裁;v1 plan/攒息门冒烟随本体退役。)


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from sr_od.application.currency_war.kernel import cw_comps, cw_economy, cw_plane_table
from sr_od.application.currency_war.telemetry import state, recorder as recorder
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)


def test_strategy_chain_importable():
    """策略链入口模块全部可导入(import 错路径在此爆,不等实跑)。"""
    for m in (cw_comps, cw_economy, cw_plane_table, state, recorder,
              DecisionV2Strategy):
        assert m is not None


def test_decide_prep_smoke():
    """decide_prep 全链真调用(四层:候选生成/硬过滤/板面评分/预算仲裁;无游戏依赖)。"""
    strat = DecisionV2Strategy()

    class _Cfg:
        faction_priority: list[str] = ['仙舟', '列车同行', '持续伤害']
    sess = strat.create_session(_Cfg())
    from sr_od.application.currency_war.kernel.cw_state import ShopCard
    st = GameState(gold=30, hp=80, level=5, round_num=3, plane=1,
                   board={"仙舟": 2, "持续伤害": 1},
                   shop=[ShopCard(x=400, faction="仙舟", name="爻光", cost=1)])
    actions = strat.decide_prep(st, sess, _Cfg())
    assert isinstance(actions, list)


def test_decide_prep_action_smoke():
    """步级决策环入口真调用(腾席链/主流程平移自持钩子;M-6 门/空板守卫全链)。"""
    from types import SimpleNamespace
    strat = DecisionV2Strategy()
    sess = strat.create_session(SimpleNamespace())
    obs = SimpleNamespace(box_overlay_open=False, tomes=[], boxes=[], spheres=[],
                          free_bench_slots=9, shop_open=False, bench_chars=[],
                          deployed_chars=[], front_occupied=set(), back_occupied=set(),
                          front_size=4, back_size=6, state=None,
                          state_gold_trusted=False)
    act = strat.decide_prep_action(obs, sess, SimpleNamespace(
        faction_priority=[], character_priority=[]))
    assert type(act).__name__ == 'RunBuyPhase'



