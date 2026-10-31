"""策略卡胜利结算条件金检查腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_win_gold_grants)。

测试面依据 = 迭代设计 designs/T-130-zhaocai-gou.md §4 锁 2/锁 3 +
REVIEW-T130(直构形态先例 = 同目录 test_check_strategy_battle_grants.py
的容器直置):
- 条件矩阵主锁(锁 2):持卡+胜+无损+佩佩 2 → 2;败局 → 0;损血 → 0;
  **扑满败局形态(won=False, hp_delta=0)→ 0 双条件必要锁**——sim 扑满
  不掉血豁免只改 hp_delta 保留掷点 won,单条件 hp_delta==0 化会在此
  误发(防回归核心形态);零佩佩 → 0;未持卡 → 0;bench 未观察 → 0;
- 计数域(锁 3):bench 2 + 上阵 1 + 溢出位 1 → 4(合并池口径,与升星
  判断同池——佩佩恒后台仍可因席满落溢出,都是玩家「有」的佩佩);
  2★ 佩佩计 1(单位数不折星,「每有一个佩佩」量词直修饰单位)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_win_gold_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '招财狗'


def _unit_slot(name: str, star: int = 1) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


def _bench_view(units: list[tuple[str, int]]) -> BenchView:
    slots = [_unit_slot(n, s) for n, s in units]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    return BenchView(slots=slots, capacity=9)


def _gs(*, card: str | None = _CARD,
        bench: BenchView | None = None,
        deployed: DeployedView | None = None,
        overflow_card: str | None = None) -> GameState:
    """直构 gs(card=None = 未持卡;bench/deployed None = 未观察;
    overflow_card None = 不置溢出身份)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card', sig=_LSIG)
    if bench is not None:
        gs.observe(gs.bench, bench, sig=_SIG_OBS)
    if deployed is not None:
        gs.observe(gs.deployed, deployed, sig=_SIG_OBS)
    if overflow_card is not None:
        gs.observe(gs.overflow_card, overflow_card, sig=_SIG_OBS)
    return gs


def test_win_no_loss_two_peipei_pays_two() -> None:
    """锁 2 主条:持卡 + 胜 + 无损 + 佩佩 2 → 2(2 × 每佩佩 1 金,表值
    单一源;函数纯读零写,零容器写面)。"""
    gs = _gs(bench=_bench_view([('佩佩', 1), ('佩佩', 1)]))
    before = gs.write_seq
    assert check_strategy_win_gold_grants(gs, won=True, hp_delta=0) == 2
    assert gs.write_seq == before, '纯读零写(写面归调用方)'


def test_loss_zero_grant() -> None:
    """锁 2 胜利判据:败局(won=False)→ 0(卡面「战斗胜利后」)。"""
    gs = _gs(bench=_bench_view([('佩佩', 1), ('佩佩', 1)]))
    assert check_strategy_win_gold_grants(gs, won=False, hp_delta=0) == 0


def test_hp_loss_zero_grant() -> None:
    """锁 2 未损血判据:损血(hp_delta≠0)→ 0(卡面「若未损失小队
    生命值」)。"""
    gs = _gs(bench=_bench_view([('佩佩', 1), ('佩佩', 1)]))
    assert check_strategy_win_gold_grants(gs, won=True, hp_delta=-3) == 0


def test_piggy_loss_shape_double_condition() -> None:
    """锁 2 双条件必要锁:扑满败局形态(won=False ∧ hp_delta=0)→ 0
    ——sim 扑满不掉血豁免产出该形态,单条件 hp_delta==0 化回归会在此
    误发(本锁即红),双写判据必要性由本形态实证。"""
    gs = _gs(bench=_bench_view([('佩佩', 1), ('佩佩', 1)]))
    assert check_strategy_win_gold_grants(gs, won=False, hp_delta=0) == 0


def test_zero_peipei_zero_grant() -> None:
    """锁 2 零佩佩:持卡+胜+无损但场内无佩佩 → 0(n=0 自然零发)。"""
    gs = _gs(bench=_bench_view([('希儿', 1)]))
    assert check_strategy_win_gold_grants(gs, won=True, hp_delta=0) == 0


def test_no_card_zero_grant() -> None:
    """锁 2 未持卡 → 0;表外卡同路(白名单表外禁自动猜装)。"""
    assert check_strategy_win_gold_grants(
        _gs(card=None, bench=_bench_view([('佩佩', 1)])),
        won=True, hp_delta=0) == 0
    assert check_strategy_win_gold_grants(
        _gs(card='躺平', bench=_bench_view([('佩佩', 1)])),
        won=True, hp_delta=0) == 0


def test_unobserved_containers_zero_grant() -> None:
    """锁 2 未观察防御:bench/deployed 未观察(None)→ 该域计 0 宁缺
    勿造(env 触发器同契约;溢出位身份在仍计 1,域防御不整腿废弃)。"""
    gs = _gs(bench=None, overflow_card='佩佩')
    assert check_strategy_win_gold_grants(gs, won=True, hp_delta=0) == 1


def test_count_domain_full_pool() -> None:
    """锁 3 计数域:bench 2 + 上阵(后排)1 + 溢出位 1 → 4(合并池
    全域;佩佩 = cost0 恒后台单位,溢出/备战形态都在玩家「有」域)。"""
    gs = _gs(bench=_bench_view([('佩佩', 1), ('佩佩', 1)]),
             deployed=DeployedView(
                 front_slots=[Unit(char_id='希儿', star=1)],
                 back_slots=[Unit(char_id='佩佩', star=1)]),
             overflow_card='佩佩')
    assert check_strategy_win_gold_grants(gs, won=True, hp_delta=0) == 4


def test_upgraded_peipei_counts_one() -> None:
    """锁 3 单位数不折星:2★ 佩佩计 1(裁决点 3 默认案锁——「每有一个
    佩佩」量词直修饰单位,副本折算读法被设计稿自证字面不支持)。"""
    gs = _gs(bench=_bench_view([('佩佩', 2)]))
    assert check_strategy_win_gold_grants(gs, won=True, hp_delta=0) == 1
