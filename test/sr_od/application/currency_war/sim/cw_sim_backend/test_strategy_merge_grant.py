"""买牌上报·策略卡合成触发发放类效果条目 sim 集成测试(镜像 src = kernel/
cw_action_report/buy_card.py 合并发火段调用点;kernel 发放函数单元面 +
获得链集成面 = kernel/cw_gain_chain/test_check_strategy_merge_grants.py,
本文件锁 buy 域调用点经真实上报函数的 sim 状态副本落地面,先例 = 同目录
test_star_merge_gold.py)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 2 + 原稿评审锁(§ 号 = 原稿节序)§3.4(卡面官方原文:「合成
2星2费角色时，获得1张【砂金】。」):

- 主锁:sim 局预种持卡 + 席面 1★×2 同名 2 费 → 买入第 3 只 1★ →
  合成 2★ → bench 含 1 个 1★砂金(buy 域调用点,发放 1★ 先验);
- 负锁:买入非 2 费同名凑三(席面 1★×2 3 费 + 买第 3 只 3 费 → 合成
  2★3费)→ 判据费用不符零发放(合成照常,费用笔照常)。

驱动形态:引擎构造助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改 = T-426 政策);上报函数直调
先例 = kernel/cw_action_report/test_buy_card.py。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _backend,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_PREP,
    SimBackend,
    uninstall_backend,
)

_CARD = '砂里淘金'
_CHAR2 = '花火'   # 2 费(判据费用域内)
_CHAR3 = '姬子'   # 3 费(判据费用不符负例)

_HOLD_SIG = ChannelSig(family='logic_action', actor='TestSeed',
                       mode='compute')


def _prep_backend(seed: int) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录
    合成金币效果条目锁 _prep_backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _hold_card(gs) -> None:
    """持卡直置(注册状态容器直写 = 持卡事实;本卡不进 STRATEGY_EFFECTS,
    零账本登记面——触发效果条目查 active_strategies ∩ STRATEGY_MERGE_GRANTS)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card',
                   sig=_HOLD_SIG)


def _seed_bench(gs, char: str, star: int, n: int) -> None:
    """备战席直置 n 只同名同星(合成素材受控,不经获得链)。"""
    slots = [_bc(char, star) for _ in range(n)]
    slots += [BenchSlot(kind='empty')] * (9 - n)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)


def _buy(gs, char: str, cost: int, star: int):
    """买一只同星同名(上报函数直调;备战屏 shop 离屏 payload 缺席 =
    跳写合法)。"""
    return report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card(char, cost=cost, star=star)),
        _SIG)


def _bench_units(gs) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_buy_third_one_star_merges_and_grants_shajin() -> None:
    """主锁(锁 2):席面 1★×2 花火 + 买第 3 只 1★ → 合成 2★花火 →
    bench 含 1 个 1★砂金(buy 域调用点发放,1★ 先验)。"""
    b = _prep_backend(62)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_bench(gs, _CHAR2, 1, 2)
        out = _buy(gs, _CHAR2, cost=2, star=1)
        assert out.applied and out.bought_count == 1, '买牌上报成功'
        units = _bench_units(gs)
        assert ('花火', 2) in units, \
            f'合成产物 2★ 在席(前置:凑齐三只): {units}'
        assert units.count(('砂金', 1)) == 1, \
            f'buy 域调用点发放恰 1 个 1★砂金: {units}'
        assert gs.bench.evidence == 'strategy_merge_grant:砂里淘金#place', \
            f'bench 尾笔 evidence = 发放写点(链 #place 后缀): ' \
            f'{gs.bench.evidence!r}'
    finally:
        uninstall_backend()


def test_buy_third_three_cost_no_grant() -> None:
    """负锁(锁 2):席面 1★×2 姬子(3 费)+ 买第 3 只 1★ → 合成
    2★3费 → 判据费用不符零发放(合成照常落席,零砂金笔)。"""
    b = _prep_backend(63)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_bench(gs, _CHAR3, 1, 2)
        out = _buy(gs, _CHAR3, cost=3, star=1)
        assert out.applied, '买牌上报成功'
        units = _bench_units(gs)
        assert ('姬子', 2) in units, \
            f'合成产物 2★3费 在席(合成照常): {units}'
        assert ('砂金', 1) not in units, \
            f'判据费用不符零发放: {units}'
    finally:
        uninstall_backend()
