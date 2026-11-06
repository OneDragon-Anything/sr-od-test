"""sim 分期金节点窗腿测试(镜像 src = sim/cw_sim_backend.py 的
apply_invest_installment_gold 把结果写进状态副本的实现分支 + _begin_node_window 收入段接线 +
apply_strategy_pick_gold_next_nodes_init 拿卡初始化腿 + 呈现一次性标志位;先例 =
本目录 test_invest_node_gold.py [定期福利聚合腿]/test_strategy_pick_xp.py
[拿卡落地拍腿族] 同形态)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-177-changqi-
zhuyi.md §4 锁 3/锁 5/锁 6(REVIEW-T177 §4.3 同面):
- 拿卡后连续 3 个节点窗各 +7、第 4 窗不发(锁 3,引擎链:真拿卡路径走
  初始化腿 + 呈现一次性标志位 + 窗腿接线;每窗容器递减笔 = 分期腿发生过的持久
  证据,金笔在非扑满窗被收入笔覆盖故引擎面以容器笔与金增量公式现算
  断言;金笔 evidence 字面量断言落函数级直构面[无覆盖可全等]);
- 跨卡双持 per-entry(锁 5,同拍双持场景:长期主义 + 长期主义+ 各发
  各额 7 与 9 × 3 窗,每卡独立 evidence 笔,evidence 前缀取完整卡名段
  + 分隔符边界——「长期主义」系「长期主义+」真前缀,断言全等形态即
  天然含边界;禁按聚合额断言);
- 耗尽短路 + 终局截断(锁 6):剩余 0 零写零报错;局终剩余腿留置蒸发
  不补发(可达腿语义 = 剩余 >0 照发,无任何局终补发方)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py 与
sim/cw_sim_backend/test_p3_win_terminal.py(已登记拆分债文件,禁追加,
只 import 复用不改;先例 = 本目录 test_strategy_pick_xp.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_box
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _force_settle,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    round_start_income,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    apply_invest_installment_gold,
    income_modifiers_of,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '长期主义'
_CARD_PLUS = '长期主义+'

#: 分期金独立笔 evidence 前缀(sim 写统一前缀 + 写点 tag;写点形态 =
#: strategy:installment:<卡名>:p{位面}r{轮},设计稿锁 3 字面量钉死)。
_GOLD_EV_PREFIX = 'sim:engine:strategy:installment:'

#: 容器递减簿记笔 evidence(非金 Field 登记事实直写,前缀无 sim:engine)。
_LEDGER_EV_PREFIX = 'strategy:installment:p'


def _backend(seed: int = 41) -> SimBackend:
    """装配后端至 P1r1 备战屏(无投资环境;装配形态先例 =
    test_strategy_pick_xp._backend)。调用方负责 uninstall。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _drive_until(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step——位面过渡屏在其分派表内,
    达 P2 及以后节点窗必经)。"""
    for _ in range(limit):
        if pred():
            return
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend) -> None:
    """驱动至策略 offer 呈现(固定日程首槽 P1r3 起;呈现即置分期金
    初始化腿一次性标志位——本腿生效前提)。"""
    _drive_until(b, lambda: b.screen_identity() == SCREEN_INVEST_STRATEGY)


def _pick(b: SimBackend, name: str, opts: list[str]) -> None:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;先例 =
    test_strategy_pick_xp._pick)。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)


def _window_income(gs, plane: int, r: int, gold_base: int) -> int:
    """节点窗收入面 kernel 公式现算(禁观测差分反推——混账形态测不出;
    先例 = test_invest_node_gold.test_invest_node_gold_leg_via_engine_
    window 同式)。gold_base = 利息基数(窗开金在分期腿落账后的现值口径,
    由调用方传入)。"""
    kind = gs.node.value.kind
    streak = max(int(gs.streak.value or 0), 0)
    mult, flat, cap = income_modifiers_of(gs)
    return round_start_income(
        plane, r, kind, gold_base, streak, win_reward_mult=mult,
        interest_flat=flat, interest_cap=cap).total


def test_pick_then_three_windows_pay_seven_fourth_stops(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """拿卡后 3 窗各 +7、第 4 窗不发(锁 3,引擎链):真拿卡路径落地后
    容器 = {'长期主义': 3}(初始化腿,值 = 注册值 count);r4/r5/r6 每窗
    金增量 = 7 + 收入面(kernel 公式现算,息基数含 +7——窗开先落账)、
    容器逐窗递减且递减笔 evidence 逐窗独立(r4/r5/r6 三笔);r7 耗尽
    短路:金增量 = 纯收入面、容器零写(evidence 保持 r6 笔)。「现在」
    腿无写端:拿卡拍金零增(T-112 族级待办维持)。全胜骨架:开局一次
    patch 强制战斗全胜(防随机败局登记 pending_loss 引入败补支——
    败补窗开参数停驻面不可复现,公式简式以无败局为前提;_force_settle
    patch 面 = backend 模块命名空间,CW skill sim-testing 规约)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gold_before_pick = int(gs.gold.value or 0)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        assert gs.strategy_gold_next_nodes_left.value == {_CARD: 3}, \
            f'拿卡落地拍初始化 = 注册值 count: ' \
            f'{gs.strategy_gold_next_nodes_left.value}'
        assert int(gs.gold.value or 0) == gold_before_pick, \
            '「现在」腿无世界写端,拿卡拍金零增(T-112 待办维持)'
        assert gs.strategy_gold_next_nodes_left.evidence \
            == f'strategy:gold_next_nodes_init:{_CARD}'
        prev_gold = gold_before_pick
        for r, left in ((4, 2), (5, 1), (6, 0)):
            _drive_until(b, lambda r=r: b._node_pos() == (1, r))
            gold_now = int(gs.gold.value or 0)
            # 息基数 = 窗前金 + 7(窗开先落账分期金后的窗开金;窗前捕获式,
            # 禁以窗后金反推——利息 g//10 量化桶会遮蔽基数取错)
            income = _window_income(gs, 1, r, prev_gold + 7)
            assert gold_now - prev_gold == 7 + income, \
                f'r{r} 窗增量 ≠ 7+收入面: ' \
                f'{gold_now - prev_gold} vs 7+{income}'
            assert gs.strategy_gold_next_nodes_left.value == {_CARD: left}, \
                f'r{r} 窗后容器应递减至 {left}: ' \
                f'{gs.strategy_gold_next_nodes_left.value}'
            assert gs.strategy_gold_next_nodes_left.evidence \
                == _LEDGER_EV_PREFIX + f'1r{r}', \
                f'r{r} 容器递减笔缺失或来源漂移: ' \
                f'{gs.strategy_gold_next_nodes_left.evidence}'
            prev_gold = gold_now
        # 第 4 窗(r7):耗尽短路零发
        _drive_until(b, lambda: b._node_pos() == (1, 7))
        gold_now = int(gs.gold.value or 0)
        income = _window_income(gs, 1, 7, gold_now)
        assert gold_now - prev_gold == income, \
            f'r7 窗应零分期发(纯收入面): ' \
            f'{gold_now - prev_gold} vs {income}'
        assert gs.strategy_gold_next_nodes_left.value == {_CARD: 0}, \
            '耗尽条目留置 0'
        assert gs.strategy_gold_next_nodes_left.evidence \
            == _LEDGER_EV_PREFIX + '1r6', \
            f'r7 耗尽零写(容器笔保持 r6): ' \
            f'{gs.strategy_gold_next_nodes_left.evidence}'
    finally:
        uninstall_backend()


def test_installment_leg_per_entry_dual_hold() -> None:
    """跨卡双持 per-entry(锁 5,同拍双持):长期主义(7)+ 长期主义+(9)
    各发各额 × 3 窗,每卡独立金笔——evidence 全等断言含完整卡名段 +
    分隔符边界(「长期主义」系「长期主义+」真前缀,全等形态天然拒裸
    前缀混淆);容器逐卡独立递减;第 4 窗双零。金笔 evidence 可全等面
    = 函数级直构(无收入笔覆盖)。笔数锁 per-entry 形(3 窗 × 2 卡各
    一笔),禁按「4 笔 × 聚合额」断言。"""
    gs = cw4_box()
    assert _CARD in STRATEGY_ECONOMY and _CARD_PLUS in STRATEGY_ECONOMY
    gs.write_logic(gs.strategy_gold_next_nodes_left,
                   {_CARD: 3, _CARD_PLUS: 3},
                   produced_by='Test', evidence='t:seed', sig=_SIG)
    assert apply_invest_installment_gold(gs, plane=1, round_num=4) == 2, \
        '每卡各一笔(同窗两笔)'
    assert int(gs.gold.value or 0) == 7 + 9, '各发各额,禁聚合'
    assert gs.gold.evidence == _GOLD_EV_PREFIX + f'{_CARD_PLUS}:p1r4', \
        f'末笔 = 插入序第二卡(容器 dict 序)独立笔: {gs.gold.evidence}'
    assert gs.strategy_gold_next_nodes_left.value == {_CARD: 2,
                                                      _CARD_PLUS: 2}, \
        '容器逐卡独立递减'
    for r in (5, 6):
        assert apply_invest_installment_gold(
            gs, plane=1, round_num=r) == 2
    assert int(gs.gold.value or 0) == (7 + 9) * 3
    assert gs.strategy_gold_next_nodes_left.value == {_CARD: 0,
                                                      _CARD_PLUS: 0}
    # 第 4 窗:双卡均耗尽,短路零发
    gold_before = int(gs.gold.value or 0)
    assert apply_invest_installment_gold(gs, plane=1, round_num=7) == 0
    assert int(gs.gold.value or 0) == gold_before, '第 4 窗零发'


def test_installment_leg_zero_hold_and_exhaust_short_circuit() -> None:
    """未持卡零写 + 耗尽短路 + 终局截断(锁 6):容器空(未持分期卡)
    调腿 → 返回 0、金零增、零 Field 写(表外卡零噪声);剩余效果条数即
    可达腿上限——局终剩余 >0 时条目留置蒸发(无局终补发方,断言面 =
    留置值不再变动、不报错);耗尽(0)再调零写零报错。"""
    gs = cw4_box()
    assert apply_invest_installment_gold(gs, plane=1, round_num=2) == 0, \
        '未持分期卡零写(容器空)'
    assert int(gs.gold.value or 0) == 0
    assert gs.strategy_gold_next_nodes_left.value in (None, {}), \
        '零 Field 写(无递减笔)'
    # 终局截断:种 3 期,局只走到 2 窗(模拟 R 剩余 <3)——可达腿照发,
    # 剩余 1 期局终蒸发;无任何补发方使金再变,条目留置即终态。
    gs.write_logic(gs.strategy_gold_next_nodes_left, {_CARD: 3},
                   produced_by='Test', evidence='t:seed', sig=_SIG)
    assert apply_invest_installment_gold(gs, plane=3, round_num=7) == 1
    assert int(gs.gold.value or 0) == 7
    assert apply_invest_installment_gold(gs, plane=3, round_num=8) == 1
    assert int(gs.gold.value or 0) == 14
    assert gs.strategy_gold_next_nodes_left.value == {_CARD: 1}, \
        '局终剩余 1 期留置(蒸发不补发——无补发方,容器即终态)'
    gold_final = int(gs.gold.value or 0)
    assert apply_invest_installment_gold(gs, plane=3, round_num=9) == 1, \
        '可达腿语义 = 剩余 >0 照发(下一窗存在则发)'
    assert int(gs.gold.value or 0) == gold_final + 7
    # 耗尽后再调:零写零报错
    assert apply_invest_installment_gold(gs, plane=3, round_num=9) == 0
    assert int(gs.gold.value or 0) == gold_final + 7


def test_installment_leg_skips_registry_missing_entry() -> None:
    """注册表缺行防御支:容器条目卡名不在 STRATEGY_ECONOMY(注册表漂移
    态)→ 悬空跳过不递减不报错(下次窗重试自愈,拒落域不落一次性标志位同向)。"""
    gs = cw4_box()
    gs.write_logic(gs.strategy_gold_next_nodes_left,
                   {_CARD: 3, '幽灵卡': 3},
                   produced_by='Test', evidence='t:seed', sig=_SIG)
    assert apply_invest_installment_gold(gs, plane=1, round_num=4) == 1, \
        '仅注册行已登记的卡发放'
    assert int(gs.gold.value or 0) == 7
    assert gs.strategy_gold_next_nodes_left.value == {_CARD: 2,
                                                      '幽灵卡': 3}, \
        '缺行条目悬空不递减(自愈重试语义)'
