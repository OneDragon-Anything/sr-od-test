"""test_cw_strategy_chain_smoke 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_strategy_planner.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations

from sr_od.application.currency_war.kernel import cw_comps, cw_economy, cw_plane_table
from sr_od.application.currency_war.kernel.cw_state import (
    GameState as _strategy_chain_smoke_GameState,
)
from sr_od.application.currency_war.strategies.impl.flow import (
    CwFlowStrategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy as _strategy_chain_smoke_MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)
from sr_od.application.currency_war.telemetry import recorder as recorder
from sr_od.application.currency_war.telemetry import state


class _FlowStrategy(MandateV1Live):
    """流程域测试具现(统一迁移批 ②):prep 决策面 = flow 规则序栈
    (_decide_prep_action_impl),不经 cw4 装配缝——腾席链/发射门/
    相位机测试的锁语义保持(v2 prep 流栈平移件)。"""

    def decide_prep_action(self, obs, session, config):
        session.prep_obs_frame = obs
        return CwFlowStrategy._decide_prep_action_impl(self, obs, session, config)

    def decide_prep_screen(self, session, config):
        if session.prep_obs_frame is None:
            raise ValueError('prep_obs_frame 缺失(黑板契约:观察层失约)')
        return CwFlowStrategy._decide_prep_action_impl(
            self, session.prep_obs_frame, session, config)
def test_strategy_chain_importable():
    """策略链入口模块全部可导入(import 错路径在此爆,不等实跑)。"""
    for m in (cw_comps, cw_economy, cw_plane_table, state, recorder,
              _strategy_chain_smoke_MandateV1Strategy):
        assert m is not None


def test_decide_prep_smoke():
    """decide_prep 全链真调用(四层:候选生成/硬过滤/板面评分/预算仲裁;无游戏依赖)。"""
    strat = _FlowStrategy()

    class _Cfg:
        faction_priority: list[str] = ['仙舟', '列车同行', '持续伤害']
    sess = strat.create_session(_Cfg())
    from sr_od.application.currency_war.kernel.cw_state import ShopCard
    st = _strategy_chain_smoke_GameState(gold=30, hp=80, level=5, round_num=3, plane=1,
                   board={"仙舟": 2, "持续伤害": 1},
                   shop=[ShopCard(x=400, faction="仙舟", name="爻光", cost=1)])
    sess.shop_state_frame = st
    actions = strat.decide_shop_screen(sess, _Cfg())
    assert isinstance(actions, list)


def test_decide_prep_action_smoke():
    """步级决策环入口真调用(腾席链/主流程平移自持钩子;M-6 门/空板守卫全链)。"""
    from types import SimpleNamespace
    strat = _FlowStrategy()
    sess = strat.create_session(SimpleNamespace())
    obs = SimpleNamespace(box_overlay_open=False, tomes=[], boxes=[], spheres=[],
                          free_bench_slots=9, shop_open=False, bench_chars=[],
                          deployed_chars=[], front_occupied=set(), back_occupied=set(),
                          front_size=4, back_size=6, state=None,
                          state_gold_trusted=False)
    act = strat.decide_prep_action(obs, sess, SimpleNamespace(
        faction_priority=[], character_priority=[]))
    # W970 批 C 改型(dd-017):主流程买牌段 RunBuyPhase → OpenShop(等价改名)
    assert type(act).__name__ == 'OpenShop' and not act.read_only
