"""轮内新鲜度账容器宿主同口 + 商店访问账本死字段退役锁。

锁两件设计约定(逐字段处置表 #18/#19;行为语义 = 处置行迁移契约):
1. 轮内新鲜度账宿主 = 容器 Field ``GameState.round_fresh_buys``:
   ``record_fresh_buy`` 写 → ``fresh_buys_of``/``fresh_buys_sell_face``
   读**同一容器**(写读单口,sim/live 同口);相位失配 = 跨轮整体作废、
   读取零销账语义逐位保留;值形状 names = list(容器 JSON 序列化安全形)。
2. 商店访问账本的四死基座字段(期望态残留,全为写端无读端)不再在场
   ——对象面运行时检查,非源码扫描。(原卖出落地锁随商店域 SellBenchOp
   退役移除:动作 op 重组批③,备战域卖出由 CwActionSellBenchOp 承接。)
"""
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    fresh_buys_of,
    fresh_buys_sell_face,
    record_fresh_buy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    NodeKey,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopVisitLedger,
)


def _feed_phase(session: StrategySession, plane: int,
                round_num: int) -> GameState:
    """容器节点播种(与 _cw_helpers.cw4_feed 节点补写同式;kind 空串 =
    帧未识别的忠实镜像,相位读口 plane_of/round_num_of 只读键维)。"""
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind=''),
               evidence='kind_inherited',
               sig=ChannelSig(family='obs',
                              actor='synthesize_from_game_state',
                              mode='synthesized'))
    return gs


def test_round_fresh_buys_host_switch_same_container() -> None:
    """宿主切换同口:record 写入容器 Field,读端自同容器解析(相位内)。"""
    session = StrategySession()
    gs = _feed_phase(session, plane=2, round_num=3)
    record_fresh_buy(session, gs, '三月七')
    # 写端落容器 Field(值形状:phase 元组对 + names list,非 set)
    assert gs.round_fresh_buys.value == {'phase': (2, 3),
                                         'names': ['三月七']}
    # 同批发射逐名入集(防批量漏记语义保留)
    record_fresh_buy(session, gs, '丹恒')
    assert gs.round_fresh_buys.value['names'] == ['三月七', '丹恒']
    # 读端 = 同容器(同口;换出守卫视角)
    assert fresh_buys_of(session, gs) == frozenset({'三月七', '丹恒'})


def test_round_fresh_buys_phase_mismatch_invalidates_whole_record() -> None:
    """相位失配 = 跨轮整体作废(读取零销账,无逐名生命周期面);新相位
    写入 = 换记录,旧相位名不泄入。"""
    session = StrategySession()
    gs = _feed_phase(session, plane=2, round_num=3)
    record_fresh_buy(session, gs, '三月七')
    assert fresh_buys_of(session, gs) == frozenset({'三月七'})
    # 轮次推进:旧记录整体作废,且记录本体未被读端销账(零销账)
    gs = _feed_phase(session, plane=2, round_num=4)
    assert fresh_buys_of(session, gs) == frozenset()
    assert gs.round_fresh_buys.value['names'] == ['三月七']
    record_fresh_buy(session, gs, '丹恒')
    assert gs.round_fresh_buys.value == {'phase': (2, 4), 'names': ['丹恒']}


def test_fresh_buys_sell_face_failclosed_and_phase_gate() -> None:
    """L1 卖侧闩读端(容器宿主):节点未定帧 = fail-closed 排除当前记录
    全集(方向安全,上界单轮);节点已定帧相位失配 = 整体作废。"""
    session = StrategySession()
    gs = game_state_of(session)   # node 未定:相位键 = 缺省 (1, 1)
    record_fresh_buy(session, gs, '三月七')
    assert fresh_buys_sell_face(session) == frozenset({'三月七'})
    # 节点已定且相位失配 = 跨轮,整体作废
    _feed_phase(session, plane=2, round_num=3)
    assert fresh_buys_sell_face(session) == frozenset()
    # 同相位重录后硬面恢复可见
    record_fresh_buy(session, gs, '丹恒')
    assert fresh_buys_sell_face(session) == frozenset({'丹恒'})


def test_buy_ledger_dead_base_fields_retired() -> None:
    """四死基座字段不再在场(期望态残留,全为写端无读端,对象面运行时
    检查);存活面 buy_purchases 保留。"""
    ledger = ShopVisitLedger()
    for _dead in ('buy_pre_bench', 'buy_pre_deployed', 'buy_has_sell',
                  'buy_unidentified'):
        assert not hasattr(ledger, _dead)
    assert ledger.buy_purchases == []
