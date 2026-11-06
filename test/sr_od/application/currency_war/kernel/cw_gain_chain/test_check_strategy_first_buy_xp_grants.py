"""策略卡首购经验检查腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_first_buy_xp_grants + kernel/cw_action_report/buy_card.py
尾段发火腿接线)。

测试面依据 = 迭代设计 designs/T-163-luansheng-sushu.md(定稿)§4 锁
3/4/5/6 + REVIEW-T163 §4②(卡面官方原文:「获得本投资策略后，首次购买
1/2/3/4/5费角色时，获得2/3/5/7/11点经验值。」;直构形态先例 = 同目录
check_strategy_* 族镜像):
- 条件矩阵(锁 3):未持卡/表外卡零写;首购 cost=c → 闩键
  ``first_buy_xp#c`` + 返回 XP_c(值下标 = 费用−1);同桶二次短路;
  cost=0/6 表外零写;五桶全取 = 28(一局上限算例,含跨级结转);
- sim 世界锁(锁 4):持卡局买牌上报 path → gs.level/gs.xp 按
  xp_apply_amount 结转推进(含门槛恰跨结转算例,evidence
  ``sim:engine:xp:first_buy:<费用>`` 独立笔);
- live 零写锁(锁 5):非 sim 形态同 path → 闩写、gs.level/gs.xp 零写
  (实机经验由游戏自发,经验条观察链覆盖);
- 拒买不可达锁(锁 6):bench_full applied=False → 发火段不可达。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_first_buy_xp_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_SIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '孪生素数'

_XP_EV_PREFIX = 'sim:engine:xp:first_buy:'


class _SimPresenceStub:
    """装配占位后端(仅令 ``sim_backend_installed()`` 为真;本腿不触后端
    任何口,触即 AssertionError 响亮——被测门控只读装配槽非 None;
    test_check_strategy_star_merge_gold 同名先例)。"""

    def screen_identity(self) -> str:
        raise AssertionError('首购经验腿不触后端读口')

    def observe(self, screen_name: str) -> object:
        raise AssertionError('首购经验腿不触后端观察')

    def visible(self, screen_name: str, area_name: str) -> bool:
        raise AssertionError('首购经验腿不触后端门问询')

    def click_answer(self, op: object, screen_name: str, area_name: str,
                     until_find_all: object, until_not_find_all: object):
        raise AssertionError('首购经验腿不触后端点击')

    def advance(self, decl: object) -> None:
        raise AssertionError('首购经验腿不触后端推进')


@pytest.fixture
def sim_installed():
    """sim 形态:装配占位后端;teardown 必卸(模块槽进程全局)。"""
    cw_sim_ports.install_sim_backend(_SimPresenceStub())
    yield
    cw_sim_ports.uninstall_sim_backend()


def _seed_obs_sig() -> ChannelSig:
    return ChannelSig(family='obs', actor='test-seed')


def _gs(*, card: str | None = _CARD, level: int | None = 5,
        cur: int = 0) -> GameState:
    """直构容器(card=None = 未持卡;'躺平' = 表外卡;level=None = 等级/
    经验未观察)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card', sig=_SIG)
    if level is not None:
        gs.observe(gs.level, level, sig=_seed_obs_sig())
        gs.observe(gs.xp, (cur, XP_TO_NEXT_LEVEL[level]), sig=_seed_obs_sig())
    return gs


def test_hold_card_first_buy_latch_and_grant(sim_installed) -> None:
    """触发主条(锁 3):持卡首购 1 费 → 返回 2;闩键 first_buy_xp#1
    落账(逻辑面,evidence 同键);xp 世界写独立笔(source=observation,
    evidence = sim:engine:xp:first_buy:1);恰三笔写(闩 + level + xp)。"""
    gs = _gs()
    seq0 = gs.write_seq
    out = check_strategy_first_buy_xp_grants(gs, cost=1, sig=_SIG)
    assert out == 2, '1 费桶 = 2 XP'
    assert gs.strategy_conditional_done.value == ('first_buy_xp#1',), \
        f'闩未落: {gs.strategy_conditional_done.value!r}'
    assert gs.strategy_conditional_done.source == 'logic', '闩 = 簿记逻辑态'
    assert gs.strategy_conditional_done.evidence == 'first_buy_xp#1'
    assert gs.xp.value == (2, XP_TO_NEXT_LEVEL[5]), f'xp 恰 +2: {gs.xp.value}'
    assert gs.xp.source == 'observation', '世界数值面 = 观察通道'
    assert gs.xp.evidence == _XP_EV_PREFIX + '1', \
        f'独立笔缺失或来源漂移: {gs.xp.evidence}'
    assert gs.write_seq == seq0 + 3, '恰三笔(闩 + level + xp)'


def test_value_index_is_cost_minus_one_all_buckets(sim_installed) -> None:
    """值下标 = 费用−1(锁 3):同一局五费用桶顺序首购 → 依次返回
    2/3/5/7/11,合计 28(一局上限算例);五键各自独立落闩(复合键费用
    粒度,纯卡名键会让第二桶被误短路——本锁即红判据);末段含跨级结转
    (5 级门槛 20 于第 5 桶跨过 → 6 级余 8)。"""
    gs = _gs()
    amounts = [check_strategy_first_buy_xp_grants(gs, cost=c, sig=_SIG)
               for c in (1, 2, 3, 4, 5)]
    assert amounts == [2, 3, 5, 7, 11], f'五桶直读: {amounts}'
    assert sum(amounts) == 28, '五桶全取上限 = 28'
    assert gs.strategy_conditional_done.value == tuple(
        f'first_buy_xp#{c}' for c in (1, 2, 3, 4, 5)), '五键独立落闩'
    assert gs.level.value == 6, '第 5 桶跨级(17+11=28 ≥ 门槛 20)'
    assert gs.xp.value == (8, XP_TO_NEXT_LEVEL[6]), \
        f'跨级结转余量 8: {gs.xp.value}'


def test_second_buy_same_bucket_short_circuit(sim_installed) -> None:
    """同桶一次性闩(锁 3):同费用二次购买 → 短路返 0,闩不重复、xp
    零写(「首次」语义,at-most-once)。"""
    gs = _gs()
    assert check_strategy_first_buy_xp_grants(gs, cost=2, sig=_SIG) == 3
    seq1 = gs.write_seq
    assert check_strategy_first_buy_xp_grants(gs, cost=2, sig=_SIG) == 0, \
        '同桶二次应短路返 0'
    assert gs.write_seq == seq1, '二次零写'
    assert gs.strategy_conditional_done.value == ('first_buy_xp#2',), \
        '闩值漂移'
    assert gs.xp.value == (3, XP_TO_NEXT_LEVEL[5]), 'xp 零增量'


def test_cost_out_of_domain_zero_write(sim_installed) -> None:
    """表外费用(锁 3):cost=0/6 → 返 0 零写留 log(费用域异常属上游
    形态,不炸不静默);闩与 xp 均不动。"""
    for bad_cost in (0, 6):
        gs = _gs()
        seq0 = gs.write_seq
        assert check_strategy_first_buy_xp_grants(
            gs, cost=bad_cost, sig=_SIG) == 0, f'cost={bad_cost} 应零发放'
        assert gs.write_seq == seq0, f'cost={bad_cost} 零写'
        assert gs.strategy_conditional_done.value in (None, ()), '零闩'


def test_no_card_and_off_table_card_zero_write(sim_installed) -> None:
    """未持卡/表外卡零写(锁 3):账本零命中与持表外卡同路(白名单表外
    禁从效果原文自动猜装)。"""
    for card in (None, '躺平'):
        gs = _gs(card=card)
        seq0 = gs.write_seq
        assert check_strategy_first_buy_xp_grants(
            gs, cost=3, sig=_SIG) == 0, f'{card}: 零命中保守零动作'
        assert gs.write_seq == seq0, f'{card}: 零写'
        assert gs.xp.value == (0, XP_TO_NEXT_LEVEL[5]), f'{card}: xp 零写'


def test_sim_world_write_exact_threshold_carry(sim_installed) -> None:
    """跨级结转算例(锁 4):门槛恰跨形态(5 级余 18 + 2)→ 6 级余 0
    (xp_apply_amount 结转语义经本腿回归)。"""
    gs = _gs(cur=XP_TO_NEXT_LEVEL[5] - 2)
    out = check_strategy_first_buy_xp_grants(gs, cost=1, sig=_SIG)
    assert out == 2
    assert gs.level.value == 6, '升一级'
    assert gs.xp.value == (0, XP_TO_NEXT_LEVEL[6]), \
        f'余量 20−2+2−20=0: {gs.xp.value}'
    assert gs.xp.evidence == _XP_EV_PREFIX + '1', '跨级笔 evidence 不变'


def test_live_form_latch_only_world_write_zero() -> None:
    """live 零写锁(锁 5,核心):未装配 sim(纯实机态)→ 闩照写(簿记
    逻辑态实机(live)和模拟器(sim)两边同写)、gs.level/gs.xp 零写(防门控失效退化成猜测写状态副本
    真值)。"""
    cw_sim_ports.uninstall_sim_backend()
    gs = _gs()
    seq0 = gs.write_seq
    assert check_strategy_first_buy_xp_grants(gs, cost=3, sig=_SIG) == 5
    assert gs.strategy_conditional_done.value == ('first_buy_xp#3',), \
        'live 闩照写'
    assert gs.xp.value == (0, XP_TO_NEXT_LEVEL[5]) \
        and gs.xp.source == 'observation', 'live xp 零写'
    assert gs.level.value == 5 and gs.level.source == 'observation', \
        'live level 零写'
    assert gs.write_seq == seq0 + 1, '恰一笔(仅闩)'


def test_buy_card_path_grants_xp(sim_installed) -> None:
    """买牌上报 path 世界锁(锁 4 主条):持卡局经上报单口买 2 费牌 →
    xp 恰 +3、闩落(发火腿接线全链;gold 未读买分支跳写,场景最小化)。"""
    gs = cw4_gs(node_fill=False, shop_screen='off', gold_unread=True,
                bench=[], active_strategies=(_CARD,),
                level=5, xp=(0, XP_TO_NEXT_LEVEL[5]))
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=2, x=0)),
        ChannelSig(family='logic_action', actor='CwScreenShop',
                   mode='compute'))
    assert out.applied and out.bought_count == 1, '买牌上报成功'
    assert gs.strategy_conditional_done.value == ('first_buy_xp#2',), \
        f'闩未落: {gs.strategy_conditional_done.value!r}'
    assert gs.xp.value == (3, XP_TO_NEXT_LEVEL[5]), \
        f'买 2 费牌 xp 恰 +3: {gs.xp.value}'
    assert gs.xp.evidence == _XP_EV_PREFIX + '2', \
        f'独立笔缺失或来源漂移: {gs.xp.evidence}'


def test_buy_card_path_rejected_bench_full_unreachable(sim_installed) -> None:
    """拒买不可达锁(锁 6):满栏且合成不可达 = applied=False 早退
    (reason='bench_full'),早退路径不经发火段 → 零闩零 xp 写。"""
    full_bench = [_bc(n) for n in ('希儿', '符玄', '花火', '停云', '刃',
                                   '杰帕德', '娜塔莎', '丹恒', '三月七')]
    gs = cw4_gs(node_fill=False, shop_screen='off', gold_unread=True,
                bench=full_bench, active_strategies=(_CARD,),
                level=5, xp=(0, XP_TO_NEXT_LEVEL[5]))
    xp0, ev0 = gs.xp.value, gs.xp.evidence
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('银狼LV.999', cost=3, x=0)),
        ChannelSig(family='logic_action', actor='CwScreenShop',
                   mode='compute'))
    assert out.applied is False and out.reason == 'bench_full', '拒买早退'
    assert gs.strategy_conditional_done.value in (None, ()), \
        '拒买零闩(早退不经发火段)'
    assert gs.xp.value == xp0 and gs.xp.evidence == ev0, '拒买零 xp 写'
