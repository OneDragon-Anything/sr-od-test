"""超发货币只登记不写状态的实现分支测试(gain_invest_strategy 分目录镜像;负债播值效果条目
首例;镜像先例 = 同目录 test_gain_invest_strategy_gudinglicai_reg.py)。

测试面依据 = 设计稿(原件已退役) 设计稿(原件已退役) §3 锁 7(已退役评审稿(§ 号 = 原稿节序)§四④ 同面):
- 窗内登记:条目已登记 remaining_nodes=6(N_NODES 播种)+ counters[LOST]
  = 登记帧金读数(播值效果条目)+ **gs.gold 状态容器零触碰**(播值 = 状态容器簿记
  非金写,live 零写金断言——gold 值/来源/证据三面现值不变);
- 金读数 None:计数缺省 + 缺陷留存证据(kind
  gain_chain_lost_counter_gold_unread,禁猜测写——锁 7 申报分支);
- 第 6 次入口移除回归:登记后逐入口推进,第 6 次推进条目归零移除
  (既有推进接入点行为,躺平同型回归断言)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    consume_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    HYPEREMIT_SPEC_ID,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')

_GOLD_SEED = 137


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwGainChain',
                      mode='compute')


def _make_gs(*, node: tuple[int, int] | None = (2, 3),
             gold: int | None = _GOLD_SEED) -> GameState:
    """直构状态容器局(bench/equips 种子沿镜像先例;gold 按参观察种子,
    None = 不种走失读分支)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if node is not None:
        gs.observe(gs.node, NodeKey(plane=node[0], round_num=node[1],
                                    kind='battle'),
                   evidence='t:seed', sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, evidence='t:seed', sig=_SIG_OBS)
    return gs


def test_gain_chaofa_huobi_registers_lost_snapshot() -> None:
    """锁 7 主形态:窗内登记 → 条目已登记 remaining_nodes=6 ∧
    counters[LOST] = 登记帧金读数 ∧ gold 状态容器零触碰(值/来源/证据三面
    现值不变 = live 零写金断言)。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '超发货币', rand=False, sig=_lsig())
    assert gs.active_strategies.value == ['超发货币']
    entry = gs.effects.first(HYPEREMIT_SPEC_ID)
    assert entry is not None, '条目已登记(获得链只登记不写状态的实现分支自动登记)'
    assert entry.remaining_nodes == 6, 'N_NODES 播种 = 持续入口数 6'
    assert entry.counters.get('lost') == _GOLD_SEED, \
        '负债播值 = 登记帧金读数(counters[LOST])'
    assert int(gs.gold.value) == _GOLD_SEED, 'gold 值零触碰(播值非金写)'
    assert gs.gold.source == 'observation', 'gold 来源零触碰'
    assert gs.gold.evidence == 't:seed', 'gold 证据零触碰(live 零写金)'


def test_gain_chaofa_huobi_gold_unread_defect_branch() -> None:
    """锁 7 申报分支:登记帧金读数 None → 计数缺省(禁猜测写)+ 缺陷
    留存证据(kind gain_chain_lost_counter_gold_unread);登记其余面
    照常(条目已登记、余期播种)。"""
    consume_defect_sink()
    gs = _make_gs(gold=None)
    gain_invest_strategy(gs, object(), '超发货币', rand=False, sig=_lsig())
    entry = gs.effects.first(HYPEREMIT_SPEC_ID)
    assert entry is not None, '登记照常(播值缺读不阻塞登记分支)'
    assert entry.remaining_nodes == 6
    assert 'lost' not in entry.counters, '计数缺省(金读数 None 禁猜测写)'
    rows = consume_defect_sink()
    assert any(r.get('kind') == 'gain_chain_lost_counter_gold_unread'
               for r in rows), f'缺陷留存证据行缺失: {rows}'
    consume_defect_sink()


def test_gain_chaofa_huobi_sixth_entry_removal_regression() -> None:
    """第 6 次入口移除回归(既有推进接入点行为,躺平同型):登记当节点
    不推进守卫下,后继 5 次推进递减 6→1、第 6 次推进归零移除。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '超发货币', rand=False, sig=_lsig())
    entry = gs.effects.first(HYPEREMIT_SPEC_ID)
    assert entry is not None
    acquired = entry.acquired_key
    for nth in range(1, 7):
        key = (acquired[0], acquired[1] + nth)
        expired = gs.effects.tick_node(key)
        if nth < 6:
            assert gs.effects.first(HYPEREMIT_SPEC_ID) is not None, \
                f'第 {nth} 次推进后条目应已登记'
            assert gs.effects.first(HYPEREMIT_SPEC_ID).remaining_nodes \
                == 6 - nth
            assert expired == [], '未到期零移除'
        else:
            assert gs.effects.first(HYPEREMIT_SPEC_ID) is None, \
                '第 6 次推进归零移除'
            assert [e.spec.id for e in expired] == [HYPEREMIT_SPEC_ID]
