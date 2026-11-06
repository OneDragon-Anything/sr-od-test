"""sim 策略 boss 金腿测试(镜像 src = sim/cw_sim_backend.py 的
strategy_boss_gold_of 聚合 helper + _begin_node_window 收口 boss 金腿)。

测试面依据 = 迭代设计 designs/T-85-tezhan-zijin.md §2.1/§2.4/§4 七语义点:
- 持卡发放真值(锁 1/7):进 boss 节点窗金增量 = 轮首收入面(kernel
  公式现算,期望不由观测差分反推)+ 聚合 boss 金,独立观察笔
  (evidence 与收入笔分键,收入三分量账不混入);
- 非 boss 节点零发放(锁 2)/ 未持卡零发放(锁 3);
- 数值矩阵(锁 4):特战资金+ = 11、双卡同持 = 18、未持 = 0(直构
  容器,数值 = 卡面真值字面锁,锁注册表值流经聚合);
- 同窗重放零双发(锁 5,幂等守卫复用回归);
- 修饰局发放位随序列现值(锁 6,人身意外险 boss 前插 supply)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改;先例 = 本目录
test_apply_round_start_income.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import cw4_box
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _drive_until,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    round_start_income,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SCREEN_PREP,
    SimBackend,
    income_modifiers_of,
    install_backend,
    strategy_boss_gold_of,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '特战资金'
_CARD_PLUS = '特战资金+'
_MOD_ENV = '人身意外险'

#: boss 金独立笔 evidence(sim 写统一前缀 + 写点 tag,单一源 =
#: sim_evidence;写点形态 = strategy:boss_gold:p{位面}r{轮})。
_GOLD_EV_PREFIX = 'sim:engine:strategy:boss_gold:p'


def _backend(seed: int = 23, *, env_name: str = '') -> SimBackend:
    """装配后端至 P1r1 备战屏(env_name 非空走投资环境屏选环境流——改
    节点序列经环境注册写场字段 ``node_seq_by_plane``,直写容器不触;
    装配形态先例 = test_apply_round_start_income._interest_backend)。
    调用方负责 uninstall。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_env_param,
    )
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108,
        env_present=bool(env_name)))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    if env_name:
        assert b.screen_identity() == SCREEN_INVEST_ENV
        b.gs.write_logic(b.gs.invest_env_opts,
                         [env_name, '轮岗', '头彩'],
                         produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_env_param(
            b.gs, SimpleNamespace(idx=0), _SIG)
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _hold(b: SimBackend, names: list[str]) -> None:
    """持卡直种(测试种子纪律:生产写端 = 获得链,观察直种先例 =
    test_sim_spy_levelup._feed_levelup)。"""
    b.gs.observe(b.gs.active_strategies, names,
                 evidence='test:hold', sig=_SIG_OBS)


def test_boss_gold_leg_via_engine_window() -> None:
    """持卡真值(锁 1/2/5/7,单局串联):奖励窗(非 boss)零策略笔;
    boss 窗独立笔 evidence 分键 + 窗金增量 = 轮首收入面(kernel 公式
    现算)+7(收入三分量账不破 = 差值恰卡面值);同节点窗重放零双发。"""
    b = _backend()
    try:
        gs = b.gs
        _hold(b, [_CARD])
        # P1r8 奖励窗(非 boss,锁 2):窗内金来源 = 收入笔,无策略笔
        _drive_until(b, lambda: b._node_pos() == (1, 8))
        assert gs.gold.evidence == 'sim:engine:income:p1r8', \
            f'非 boss 节点出现策略笔: {gs.gold.evidence}'
        # 收入面输入在 r8 窗捕获:gold = r8 收入落账后现值(r9 息算基数),
        # streak = 奖励轮不动连胜,至 r9 窗开同值
        g8 = int(gs.gold.value or 0)
        s8 = max(int(gs.streak.value or 0), 0)
        mult, flat, cap = income_modifiers_of(gs)
        _drive_until(b, lambda: b._node_pos() == (1, 9))
        # 锁 1 独立笔:evidence 与收入笔分键(若并入收入写则留 income 键)
        assert gs.gold.evidence == _GOLD_EV_PREFIX + '1r9', \
            f'boss 窗独立笔缺或来源漂移: {gs.gold.evidence}'
        # 锁 1/7 真值:窗增量 = 收入面 + 卡面值;收入面现算自 kernel
        # 公式单一源(禁由观测差分反推,否则混账形态测不出)
        income = round_start_income(
            1, 9, 'boss', g8, s8, win_reward_mult=mult,
            interest_flat=flat, interest_cap=cap).total
        assert gs.gold.value == g8 + income + 7, \
            f'窗金增量 ≠ 收入面+7: {g8}+{income}+7 vs {gs.gold.value}'
        # 锁 5 幂等回归:同节点窗重放,守卫住整段收口零双发
        gold_at_boss = gs.gold.value
        b._begin_node_window()
        assert gs.gold.value == gold_at_boss \
            and gs.gold.evidence == _GOLD_EV_PREFIX + '1r9', \
            f'同窗重放双发或来源漂移: {gold_at_boss} vs {gs.gold.value}'
    finally:
        uninstall_backend()


def test_no_boss_gold_without_card() -> None:
    """未持卡零发放(锁 3):boss 窗金来源 = 收入笔,无策略笔
    (offer 定卡加油站无 boss 金分量,聚合 = 0 → 零值零写)。"""
    b = _backend(seed=24)
    try:
        gs = b.gs
        _drive_until(b, lambda: b._node_pos() == (1, 9))
        assert gs.gold.evidence == 'sim:engine:income:p1r9', \
            f'未持卡局出现策略笔: {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_modified_env_boss_position_follows_sequence() -> None:
    """修饰局跟随(锁 6):人身意外险 boss 前插 supply → 发放位随
    ``node_seq_by_plane`` 现值(evidence 轮次自序列现值推导,非硬编码
    默认表 r9;boss 位由 kind 序列现值判定)。"""
    b = _backend(seed=25, env_name=_MOD_ENV)
    try:
        gs = b.gs
        _hold(b, [_CARD])
        seq = list((gs.node_seq_by_plane.value or {}).get(1) or [])
        r_boss = seq.index('boss') + 1
        assert r_boss != 9 and seq[r_boss - 2] == 'supply', \
            f'修饰序列形状不符(应为 boss 前插 supply): {seq}'
        _drive_until(b, lambda: b._node_pos() == (1, r_boss))
        assert gs.gold.evidence == _GOLD_EV_PREFIX + f'1r{r_boss}', \
            f'发放位未随序列现值: {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_strategy_boss_gold_aggregation_matrix() -> None:
    """数值矩阵(锁 4,直构容器锁聚合数学):特战资金+ = 11、双卡同持
    = 18、未持 = 0(数值 = 卡面真值字面锁;0 = 零值零写前提)。"""
    assert strategy_boss_gold_of(cw4_box(
        active_strategies=(_CARD_PLUS,))) == 11
    assert strategy_boss_gold_of(cw4_box(
        active_strategies=(_CARD, _CARD_PLUS))) == 18
    assert strategy_boss_gold_of(cw4_box()) == 0
