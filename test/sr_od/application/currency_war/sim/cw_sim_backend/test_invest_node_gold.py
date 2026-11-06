"""sim 投资策略每节点金腿测试(镜像 src = sim/cw_sim_backend.py 的
strategy_invest_node_gold_of 聚合 helper + _begin_node_window 收入段最前
invest 金腿;先例 = 本目录 test_strategy_boss_gold.py 收尾腿同形态)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-162-dingqi-
fuli.md §4 锁 2/锁 3/锁 4:
- 腿函数真值(锁 2,直构状态容器):持卡 = 2、与姊妹近似卡同持 = sum 3、
  未持 = 0(数值 = 卡面真值字面锁,锁注册表值流经聚合单一源);
- 调用点接通(锁 3):非扑满局窗增量 = invest + 收入面(kernel 公式现算,
  息基数 = 窗前基准现值 + 本窗 invest——腿在收入段最前先落账),窗后
  evidence = 收入笔(invest 笔先落账被收入笔
  覆盖 = 调用点在收入段之前的机制序证据)+ 同窗重放零双发;扑满局窗开
  即 +2 且**结算腿利息基数含 +2**(息差断言:窗开金落在进位档
  (g−2 mod10 ∈ {8,9}、帽界内)时 interest(g) − interest(g−2) = 1
  ——调用点若后置于快照,快照金少 2、息恰少 1,断言红);
- 未持卡零发放(锁 4,腿零噪声:窗内金来源 = 收入笔)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改;先例 = 本目录
test_strategy_boss_gold.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_box
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _PIGGY_ENV,
    _SIG,
    _SIG_OBS,
    _close_shop_feed,
    _drive_step,
    _drive_until,
    _force_settle,
    _piggy_backend,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    interest,
    round_start_income,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOSS_BRIEFING,
    SCREEN_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_ENV,
    SCREEN_INVEST_STRATEGY,
    SCREEN_LOBBY,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    income_modifiers_of,
    install_backend,
    is_piggy_node,
    strategy_invest_node_gold_of,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '定期福利'
_SISTER_FLAT = '剩余价值'
#: 分期金参数化扩名用卡(T-177 长期主义;注册值 7/3,与 +2 版锁同构)。
_CARD_INSTALLMENT = '长期主义'

#: 每节点金独立笔 evidence(sim 写统一前缀 + 写点 tag,单一源 =
#: sim_evidence;写点形态 = strategy:invest_node_gold:p{位面}r{轮})。
_GOLD_EV_PREFIX = 'sim:engine:strategy:invest_node_gold:p'

_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_SHOP)


def _backend(seed: int = 23) -> SimBackend:
    """装配后端至 P1r1 备战屏(无投资环境;装配形态先例 =
    test_strategy_boss_gold._backend)。调用方负责 uninstall。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source('货币战争-简报', '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _hold(b: SimBackend, names: list[str]) -> None:
    """持卡直种(测试种子纪律:生产写端 = 获得链,观察直种先例 =
    test_strategy_boss_gold._hold)。"""
    b.gs.observe(b.gs.active_strategies, names,
                 evidence='test:hold', sig=_SIG_OBS)


def test_invest_node_gold_aggregation_matrix() -> None:
    """数值矩阵(锁 2,直构状态容器锁聚合数学):定期福利 = 2、与姊妹近似
    卡(剩余价值,注册值系战斗表现条件金的每节点期望近似)同持 = sum 3、
    未持 = 0(数值 = 卡面真值字面锁;0 = 零值零写前提)。"""
    assert strategy_invest_node_gold_of(cw4_box(
        active_strategies=(_CARD,))) == 2
    assert strategy_invest_node_gold_of(cw4_box(
        active_strategies=(_CARD, _SISTER_FLAT))) == 3
    assert strategy_invest_node_gold_of(cw4_box()) == 0


def test_invest_node_gold_leg_via_engine_window() -> None:
    """持卡真值(锁 3 前半,单局串联):奖励窗后 evidence = 收入笔
    (invest 笔先落账、收入笔后写覆盖——调用点在收入段之前的机制序);
    boss 窗金增量 = invest + 收入面(kernel 公式现算,息基数 = 窗开金 =
    窗前基准现值 + 本窗 invest);同节点窗重放零双发(窗口幂等守卫复用
    回归)。"""
    b = _backend()
    try:
        gs = b.gs
        _hold(b, [_CARD])
        # P1r8 奖励窗:r2 起每窗先发 invest 再结算收入,窗后 evidence
        # 应为收入笔(若腿挂收入段之后,此处会留 invest 笔)
        _drive_until(b, lambda: b._node_pos() == (1, 8))
        assert gs.gold.evidence == 'sim:engine:income:p1r8', \
            f'窗后 evidence 非 income 笔(invest 落账序漂移): ' \
            f'{gs.gold.evidence}'
        # 收入面输入在 r8 窗捕获:gold = r8 落账后现值(r9 息算基数,
        # 含 r9 窗开时本腿未发前口径),streak = 奖励轮不动连胜,至 r9
        # 窗开同值
        g8 = int(gs.gold.value or 0)
        s8 = max(int(gs.streak.value or 0), 0)
        mult, flat, cap = income_modifiers_of(gs)
        _drive_until(b, lambda: b._node_pos() == (1, 9))
        # 真值:窗增量 = invest + 收入面现算(收入面息基数 = 窗开金 =
        # g8 + 本窗 invest——腿在收入段最前先落账;禁由观测差分反推,
        # 否则混账形态测不出)
        invest = strategy_invest_node_gold_of(gs)
        income = round_start_income(
            1, 9, 'boss', g8 + invest, s8, win_reward_mult=mult,
            interest_flat=flat, interest_cap=cap).total
        assert gs.gold.value == g8 + income + invest, \
            f'窗金增量 ≠ invest+收入面: ' \
            f'{g8}+{invest}+{income} vs {gs.gold.value}'
        # boss 节点窗后 evidence 仍为收入笔(本局未持特战资金,boss 金
        # 腿零写;invest 笔先落账被覆盖)
        assert gs.gold.evidence == 'sim:engine:income:p1r9', \
            f'boss 窗后 evidence 非 income 笔: {gs.gold.evidence}'
        # 幂等回归:同节点窗重放,守卫住整段收尾零双发
        gold_at_boss = gs.gold.value
        b._begin_node_window()
        assert gs.gold.value == gold_at_boss \
            and gs.gold.evidence == 'sim:engine:income:p1r9', \
            f'同窗重放双发或来源漂移: {gold_at_boss} vs {gs.gold.value}'
    finally:
        uninstall_backend()


def _drive_to_interest_base_band_piggy_window(
        monkeypatch: pytest.MonkeyPatch, b: SimBackend
) -> tuple[int, int, int]:
    """自当前扑满窗起逐窗推进至「息差非平凡」扑满窗(窗口开金 g 含本腿
    +2 且 interest(g) − interest(g−2) = 1——g−2 mod10 ∈ {8,9} 的进位
    档、帽界内 → 本腿 +2 使结算息恰多 1,基数序可判),停在窗未结算;
    返回 (位面, 轮, 窗口开金)。P1r1 除外(该窗开于持卡直种前,无本腿
    笔,恒穿过)。驱动骨架 =
    test_resolve_battle._drive_to_interest_band_piggy_window 同型
    (窗收尾自动弹店 → 关店回备战;途经非扑满节点全胜强制穿过防随机
    败局死局;途中补给/遭遇/首领走真写端消费;局终大厅屏 = 息差窗
    未达,报错带因)。"""
    gs = b.gs
    for _ in range(16):
        if b.screen_identity() == SCREEN_SHOP:
            _close_shop_feed(b)   # 窗收尾自动弹店 → 关店回备战
        assert b.screen_identity() == SCREEN_PREP and is_piggy_node(gs), \
            '应停在扑满节点备战窗'
        plane, r = b._node_pos()
        gold_at_window = int(gs.gold.value or 0)
        if (plane, r) != (1, 1) \
                and interest(gold_at_window) \
                - interest(gold_at_window - 2) == 1:
            return plane, r, gold_at_window
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        reached = False
        for _ in range(48):
            screen = b.screen_identity()
            if screen == SCREEN_PREP:
                if is_piggy_node(gs):
                    reached = True
                    break
                # 非扑满战斗节点:全胜强制穿过(防随机败局死局)
                _force_settle(monkeypatch, won=True)
                _start_battle_feed(gs)
                continue
            if screen in _TRANSIT_SCREENS:
                _drive_step(b, 7)   # 中间屏(含补给/遭遇/首领窗)真写端消费
                continue
            if screen == SCREEN_LOBBY:
                raise AssertionError('局终(大厅)仍未遇息差非平凡扑满窗'
                                     '(经济序列漂移?)')
            raise AssertionError(f'推进途遇未预期屏 {screen}')
        assert reached, '48 步未遇扑满窗(节点序列漂移?)'
    raise AssertionError('16 窗未遇息差非平凡扑满窗(经济序列漂移?)')


def test_piggy_window_pays_first_and_interest_base_contains_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """扑满局窗开即付 + 利息基数序(锁 3 后半,裁决点默认案核心):
    扑满窗开 evidence = 本腿独立笔(窗内唯一金写,快照不写金——独立
    观察笔与收入笔分键的直接证据);窗开金含本窗 +2;结算分支息 =
    interest(窗开金)(kernel 公式现算期望)且息差非平凡(interest(g)
    − interest(g−2) = 1,搜索器保证)——若腿调用点后置于递延快照,快照
    金少 2、息恰少 1,本断言红(基数序回归防线)。"""
    b = _piggy_backend()
    try:
        gs = b.gs
        _hold(b, [_CARD])
        plane, r, gold_at_window = \
            _drive_to_interest_base_band_piggy_window(monkeypatch, b)
        assert gs.gold.evidence \
            == _GOLD_EV_PREFIX + f'{plane}r{r}', \
            f'扑满窗开 evidence 非本腿独立笔: {gs.gold.evidence}'
        counter_at_window = gs.effects.interest_earned
        assert interest(gold_at_window) \
            - interest(gold_at_window - 2) == 1, \
            '息差非平凡前提(搜索条件静默漂移 = 断言退化)'
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.effects.interest_earned \
            == counter_at_window + interest(gold_at_window), \
            f'结算息 ≠ 窗开快照金口径息: 期望 ' \
            f'{counter_at_window + interest(gold_at_window)} vs ' \
            f'{gs.effects.interest_earned}(基数含本腿 +2)'
    finally:
        uninstall_backend()


def test_no_invest_node_gold_without_card() -> None:
    """未持卡零发放(锁 4,腿零噪声):boss 窗金来源 = 收入笔,无
    策略笔(聚合 = 0 → 零值零写;先例 = test_strategy_boss_gold
    同名锁,本腿全节点型故同窗位断言)。"""
    b = _backend(seed=24)
    try:
        gs = b.gs
        _drive_until(b, lambda: b._node_pos() == (1, 9))
        assert gs.gold.evidence == 'sim:engine:income:p1r9', \
            f'未持卡局出现策略笔: {gs.gold.evidence}'
    finally:
        uninstall_backend()


# —— 分期金腿参数化扩名(T-177;存量为 T-162 批锁,禁动,只追加) ——

#: 分期金独立笔 evidence 前缀(与 test_invest_installment_gold 同源字面;
#: 本地重复声明 = 跨文件常量零共享的既有目录纪律)。
_INSTALLMENT_EV_PREFIX = 'sim:engine:strategy:installment:'


def _piggy_backend_card_held_before_first_window(card: str) -> SimBackend:
    """扑满局装配 + 首窗开前持卡直种(展开 _piggy_backend 流程,种卡位
    插在构造后、简报点击前——r1 窗开时已持卡,分期腿在首窗即发;
    _piggy_backend 无种子钩子且债文件禁追加,故本地展开,装配序与其
    逐行同构)。"""
    b = SimBackend(seed=31, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    # 首窗开前持卡(观察直种先例 = _hold;r1 窗开于环境选卡推进内,
    # 此刻尚未发生)。分期金窗腿判递减状态容器非持卡面——状态容器同步种注册值
    # count = 拿卡落地拍状态的直种表达(初始化写端的真身路径归
    # test_invest_installment_gold 引擎链锁,此处直种合法)。
    b.gs.observe(b.gs.active_strategies, [card],
                 evidence='test:hold', sig=_SIG_OBS)
    b.gs.write_logic(b.gs.strategy_gold_next_nodes_left, {card: 3},
                     produced_by='Test', evidence='t:hold_container',
                     sig=_SIG)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_PIGGY_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    # wait_one_one 惰性完成显式化(环境选卡推进落 wait_one_one 变体,
    # r1 窗开挂下次问询;不问询则窗未开、分期腿未跑——+2 版测试由搜索
    # 器 assert screen_identity() 问询隐式触发,本形态无搜索器,显式调)
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def test_piggy_window_installment_pays_first_and_interest_base_contains_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """扑满局分期金腿窗开即付 + 利息基数序(锁 4 分期参数化扩名,
    裁决点 5 默认案 T-177 腿侧;+2 版同名锁的分期 +7 变体):种卡前置于
    装配 → r1 扑满首窗窗开金 = 种子 3 + 分期 7 = 10,evidence = 分期腿
    独立笔(窗内唯一金写——聚合腿未持零写、快照不写金);息差非平凡
    (interest(10) − interest(3) = 1,首窗低金段帽界内,**确定命中**非
    搜索——+7 版若搜后期窗,金 ≥50 息帽恒吞差,息断言不可判,首窗
    形态绕开);结算息 = interest(窗开金)(kernel 公式现算期望)——若
    分期腿调用点后置于递延快照,快照金 3、息恰少 1,本断言红(基数序
    回归防线)。"""
    b = _piggy_backend_card_held_before_first_window(_CARD_INSTALLMENT)
    try:
        gs = b.gs
        assert b._node_pos() == (1, 1), '应停在 r1 扑满首窗备战'
        gold_at_window = int(gs.gold.value or 0)
        assert gold_at_window == 10, \
            f'窗开金 = 种子 3 + 分期首窗 7: {gold_at_window}'
        assert gs.gold.evidence \
            == _INSTALLMENT_EV_PREFIX + f'{_CARD_INSTALLMENT}:p1r1', \
            f'扑满窗开 evidence 非分期腿独立笔: {gs.gold.evidence}'
        counter_at_window = gs.effects.interest_earned
        assert interest(gold_at_window) \
            - interest(gold_at_window - 7) == 1, \
            '息差非平凡前提(息帽/进位漂移 = 断言退化)'
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.effects.interest_earned \
            == counter_at_window + interest(gold_at_window), \
            f'结算息 ≠ 窗开快照金口径息: 期望 ' \
            f'{counter_at_window + interest(gold_at_window)} vs ' \
            f'{gs.effects.interest_earned}(基数含分期腿 +7)'
    finally:
        uninstall_backend()
