"""SellBench / SellDeployed / SwapDeploy v2 族 + LogicOutcome 出参契约直锁
（全仓唯一锁面）。

历史与到期兑现：原为冻结 simulate 快照对照（13 案金样
t185_golden_fixture.json）；2026-09-15 严格瘦身收缩 6 案暂留并注记
「改活等价锁后删快照半」。前提已亡（``cw_vocab.simulate`` 零生产消费，
动作链全走 apply_*_logic 直锁），到期兑现 = 初态本地构造（观察写入口，
替代 restore_state_snapshot 注入）+ 直驱活的
``kernel.cw_game_state.apply_shop_action_logic``，冻结 JSON 与其加载代码
删除（fixture 视为不可再生的一次性捕获，生成器指针
.debug/temp/t185_capture_golden2.py 不入 git；JSON 内 comptx 两案所属
动作类已退役，为不可达死数据，随到期一并删）。

锁面（每案断言域 = v2 平移契约申报表 kernel/cw_game_state.py
SHOP_PROJECTION_DOMAINS 扩面申报：applied/reason/income 出参 +
gold/bench/front_row/back_row/board/equips 域写回 + 未辖域零写）：
- sellbench_apply_equips：卖 bench 退款入金（注册表 sell_refund 现算）
  + 装备回收进 owned 池尾（C6 装备守恒）+ 槽置空；未辖域零写；
- sellbench_stale_reject：陈旧提案（expect 失配）拒 = applied=False +
  reason=stale_proposal:… 零容器写（ADR-0317）；
- selldeployed_apply / selldeployed_stale_reject：deployed 平移契约
  （槽表置空 → front/back rows 整表写）+ board 重算 + 退款/装备回收；
- swapdeploy_apply / swapdeploy_idx_reject：**SwapDeploy 全仓唯一行为
  覆盖**——原槽对调（上场者继承下场者排 + 槽号重写为 deployed 槽号）、
  board 随 deployed 重算；越界拒 reason=idx_out_of_range:dN/bM 零写。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    ShopPayload,
    ShopSlot,
    Unit,
    apply_shop_action_logic,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    SellBench,
    SellDeployed,
    SwapDeploy,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw_observation', mode='read')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='MandateV1Strategy',
                        mode='compute')

#: 初态共用底稿（金样捕获帧 p1-r3 battle / lv5 / xp(4,20) / hp80 / 金 10);
#: 退款真值从注册表现算(1★ 银枝,cost 2 → 退 2,金样捕获 2026-09-13 钉
#: 10→12 同源),不手抄常数。
_REFUND_1STAR = sell_refund(1, bench_char_cost(
    BenchChar(slot=1, char_id='银枝', star=1)))

_EMPTY_SHOP = ShopPayload(cards=[ShopSlot(kind='empty')] * 5,
                          refresh_probs={})


def _unit(char_id: str, slot: int, *, equips: list[str] | None = None) -> Unit:
    return Unit(char_id=char_id, star=1, equips=list(equips or []), slot=slot)


def _gs_with(*, bench: list[Unit], front: list[Unit], gold: int = 10,
             equips: list[str] | None = None,
             board: dict[str, int] | None = None) -> GameState:
    """初态本地构造(替代冻结快照 restore):共用底稿 + 案给定域,全部经
    观察写入口(生产同路,渠道门在测)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
               sig=_SIG_OBS)
    slots = [BenchSlot(kind='empty')] * 9
    for i, u in enumerate(bench):
        if u is not None:
            slots[i] = BenchSlot(kind='unit', unit=u)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.front_row, list(front), sig=_SIG_OBS)
    gs.observe(gs.back_row, [], sig=_SIG_OBS)
    if board is not None:
        gs.observe(gs.board, dict(board), sig=_SIG_OBS)
    gs.observe(gs.back_layout, 6, sig=_SIG_OBS)
    gs.observe(gs.gold, gold, sig=_SIG_OBS)
    gs.observe(gs.level, 5, sig=_SIG_OBS)
    gs.observe(gs.xp, (4, 20), sig=_SIG_OBS)
    gs.observe(gs.hp, 80, sig=_SIG_OBS)
    gs.observe(gs.shop, ShopPayload(cards=[ShopSlot(kind='empty')] * 5,
                                    refresh_probs={}), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def _bench_units(gs: GameState) -> list[tuple[int, str]]:
    """bench 视图 → (槽下标, char_id) 紧缩断言面。"""
    view = gs.bench.value
    assert view is not None
    return [(i, s.unit.char_id) for i, s in enumerate(view.slots)
            if s.kind == 'unit' and s.unit is not None]


def _row_pairs(gs, field) -> list[tuple[str, int]]:
    v = getattr(gs, field).value
    return [(u.char_id, u.slot) for u in (v or [])]


# 案表:(案名, 动作构造, 初态构造参数, applied, reason(None=不辖,原金样
# 对空 reason 案不比), income(None=不辖 | 数值=现算退款断言), 期望金,
# 期望 bench 紧缩, 期望 front 行(char_id, slot) | None=断言不变, 期望
# board | None=未观察不写, 期望 equips | None=未观察不写)。
_REFUND = _REFUND_1STAR

_CASES = [
    pytest.param(
        'sellbench_apply_equips',
        lambda: SellBench(bench_idx=0, expect='银枝', reason='test'),
        {'bench': [_unit('银枝', 1, equips=['以太钻头']),
                   _unit('爻光', 2)],
         'front': [], 'equips': ['光速螺旋桨·特权']},
        True, None, _REFUND, 10 + _REFUND,
        [(1, '爻光')], None, None, ['光速螺旋桨·特权', '以太钻头'],
        id='sellbench-apply-equips'),
    pytest.param(
        'sellbench_stale_reject',
        lambda: SellBench(bench_idx=0, expect='刃', reason='test'),
        {'bench': [_unit('银枝', 1), _unit('爻光', 2)], 'front': []},
        False, 'stale_proposal:刃!=银枝', None, 10,
        [(0, '银枝'), (1, '爻光')], None, None, None,
        id='sellbench-stale-reject'),
    pytest.param(
        'selldeployed_apply',
        lambda: SellDeployed(deployed_idx=0, expect='银枝', reason='test'),
        {'bench': [], 'front': [_unit('银枝', 1, equips=['以太钻头'])],
         'board': {'星间旅人': 1, '群攻': 1}},
        True, 'test', _REFUND, 10 + _REFUND,
        [], [], {}, ['以太钻头'],
        id='selldeployed-apply'),
    pytest.param(
        'selldeployed_stale_reject',
        lambda: SellDeployed(deployed_idx=0, expect='刃', reason='test'),
        {'bench': [], 'front': [_unit('银枝', 1)],
         'board': {'星间旅人': 1, '群攻': 1}},
        False, 'stale_proposal:刃!=银枝', None, 10,
        [], [('银枝', 1)], {'星间旅人': 1, '群攻': 1}, None,
        id='selldeployed-stale-reject'),
    pytest.param(
        'swapdeploy_apply',
        lambda: SwapDeploy(deployed_idx=0, bench_idx=0, reason='test'),
        {'bench': [_unit('爻光', 1), _unit('停云', 2)],
         'front': [_unit('银枝', 1)],
         'board': {'星间旅人': 1, '群攻': 1}},
        True, 'test', None, 10,
        [(0, '银枝'), (1, '停云')], [('爻光', 1)],
        {'仙舟': 1, '欢愉': 1}, None,
        id='swapdeploy-apply'),
    pytest.param(
        'swapdeploy_idx_reject',
        lambda: SwapDeploy(deployed_idx=5, bench_idx=0, reason='test'),
        {'bench': [_unit('爻光', 1)], 'front': [_unit('银枝', 1)],
         'board': {'星间旅人': 1, '群攻': 1}},
        False, 'idx_out_of_range:d5/b0', None, 10,
        [(0, '爻光')], [('银枝', 1)], {'星间旅人': 1, '群攻': 1}, None,
        id='swapdeploy-idx-reject'),
]


@pytest.mark.parametrize(
    'case_name,make_action,init_kw,applied,reason,income,gold,'
    'bench_expect,front_expect,board_expect,equips_expect',
    _CASES)
def test_cw_transfer_golden(case_name: str, make_action, init_kw: dict,
                            applied: bool, reason: str | None,
                            income: int | None, gold: int,
                            bench_expect: list[tuple[int, str]],
                            front_expect: list[tuple[str, int]] | None,
                            board_expect: dict[str, int] | None,
                            equips_expect: list[str] | None) -> None:
    """v2 族直锁(案表驱动;断言域 = 平移契约申报表全集,原冻结快照逐域
    diff 的每条腿改写为显式期望):出参契约(applied/reason/income)+
    gold/bench/rows/board/equips 域写回 + 未辖域(hp/level/xp/shop/
    back_layout)零写。"""
    gs = _gs_with(**init_kw)
    out = apply_shop_action_logic(gs, make_action(), executed=None,
                                  produced_by='MandateV1Strategy',
                                  sig=_SIG_LOGIC)
    # —— 出参契约(LogicOutcome;拒绝 = applied=False + reason 零写)——
    assert out.applied is applied, f'{case_name}: applied'
    if reason is not None:
        assert out.reason == reason, f'{case_name}: reason'
    if income is not None:
        assert out.income == income, f'{case_name}: income(注册表现算)'
    # —— 域写回 ——
    assert gs.gold.value == gold, f'{case_name}: gold'
    assert _bench_units(gs) == bench_expect, f'{case_name}: bench'
    if front_expect is not None:
        assert _row_pairs(gs, 'front_row') == front_expect, \
            f'{case_name}: front_row'
    if board_expect is not None:
        assert gs.board.value == board_expect, f'{case_name}: board'
    if equips_expect is not None:
        assert gs.equips.value == equips_expect, \
            f'{case_name}: equips(回收进 owned 池尾)'
    # —— 未辖域零写(域封闭腿;初态常量即期望)——
    assert gs.hp.value == 80 and gs.level.value == 5 \
        and gs.xp.value == (4, 20), f'{case_name}: hp/level/xp 零写'
    assert gs.back_layout.value == 6, f'{case_name}: back_layout 零写'
    assert gs.shop.value == _EMPTY_SHOP, f'{case_name}: shop 零写'
