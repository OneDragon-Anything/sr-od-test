"""买牌上报·合成 3 星条件金币效果条目 sim 集成测试(镜像 src = kernel/cw_action_report/
buy_card.py 合并发火段调用点;kernel 发放函数单元面 + 获得链集成面 =
kernel/cw_gain_chain/test_check_strategy_star_merge_gold.py,本文件锁
buy 域调用点经真实上报函数的 sim 状态副本落地面)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 2 + 已退役评审稿(§ 号 = 原稿节序)§四 ④:

- 主锁:sim 局预种持卡 + 席面 2★×2 → 买入同名第 3 只(2★)→ gold +5
  (观察笔恰一笔,evidence = sim:engine:strategy_star_merge_gold:1,
  sim 侧策略金币效果条目家族统一形态);金位同拍先经 proj_buy_gold logic 写、
  发放 observe 相邻异通道覆盖落失配抑制分支 = 记账路径(T-108 同拍
  相邻写先例,全程零真失配告警行);
- 负锁:凑不齐三只(席面 2★×1 买第 2 只,只凑对不出 3 星)→ 零金笔
  (费用 logic 笔照常,条件金币效果条目与买牌费用解耦)。

驱动形态:引擎构造助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改 = T-426 政策);上报函数直调
先例 = kernel/cw_action_report/test_buy_card.py。
"""
from __future__ import annotations

import pytest
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
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
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

_CARD = '星星相印'
_CHAR = '花火'
_EV = 'sim:engine:strategy_star_merge_gold:1'

_HOLD_SIG = ChannelSig(family='logic_action', actor='TestSeed',
                       mode='compute')


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本);主锁同拍相邻写应落抑制分支,
    本夹具兼作「零告警行」断言基础数据。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _prep_backend(seed: int) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录
    到级金币效果条目锁 _prep_backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _hold_card(gs) -> None:
    """持卡直置(注册状态容器直写 = 持卡事实)+ 账本条目登记(发放类效果条目读
    效果账本,登记缺位 = 零命中零动作)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card',
                   sig=_HOLD_SIG)
    gs.effects.register_strategy(STRATEGY_EFFECTS[_CARD], (1, 2))


def _seed_bench(gs, star: int, n: int) -> None:
    """备战席直置 n 只同名同星(合成素材受控,不经获得链)。"""
    slots = [_bc(_CHAR, star) for _ in range(n)]
    slots += [BenchSlot(kind='empty')] * (9 - n)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)


def _buy(gs, star: int):
    """买一只同星同名(上报函数直调;备战屏 shop 离屏 payload 缺席 =
    跳写合法)。"""
    return report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card(_CHAR, cost=2, star=star)), _SIG)


def _bench_units(gs) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_buy_third_two_star_grants_five_gold(
        _isolate_defect_buffer) -> None:
    """主锁:席面 2★×2 + 买第 3 只 2★ → 合成 3★ → gold = 买前 − 单价
    +5(费用 logic 笔与发放观察笔同拍相邻,零真失配告警行;发放笔
    evidence/通道/值三面钉死)。"""
    b = _prep_backend(62)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_bench(gs, 2, 2)
        gold_before = int(gs.gold.value or 0)
        out = _buy(gs, 2)
        assert out.applied and out.bought_count == 1, '买牌上报成功'
        assert ('花火', 3) in _bench_units(gs), \
            f'合成产物 3★ 在席(前置:凑齐三只): {_bench_units(gs)}'
        assert gs.gold.value == gold_before - 2 + 5, \
            f'金值 = 买前 {gold_before} − 单价 2 + 发放 5'
        assert gs.gold.source == 'observation', '发放 = 观察通道'
        assert gs.gold.evidence == _EV, \
            f'发放笔证据串 = 本效果条目写点 tag: {gs.gold.evidence!r}'
        # 相邻异通道覆盖落 sim:engine 抑制分支 = 零真失配告警行
        assert all(r['kind'] != 'observe_vs_logic_mismatch'
                   for r in consume_defect_sink()), '零真失配行'
    finally:
        uninstall_backend()


def test_buy_no_trio_no_gold_grant(_isolate_defect_buffer) -> None:
    """负锁:凑不齐三只(席面 2★×1 + 买第 2 只 = 2×2★ 不合成)→ 零
    金笔(金位 = 费用 logic 笔现值,发放条件不达零动作;费用与条件金
    解耦)。"""
    b = _prep_backend(63)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_bench(gs, 2, 1)
        gold_before = int(gs.gold.value or 0)
        out = _buy(gs, 2)
        assert out.applied, '买牌上报成功(无合成也落位)'
        assert gs.gold.value == gold_before - 2, \
            '凑不齐:只扣费用零发放(金面无 +5 笔)'
        assert gs.gold.source == 'logic', \
            '金位停留费用 logic 笔(零观察覆盖)'
        assert ('花火', 2) in _bench_units(gs), '2★ 产物落席(无 3★)'
    finally:
        uninstall_backend()
