# -*- coding: utf-8 -*-
"""r422/r423(ADR-0287 部署时序 + ADR-0288 凑档降级)锁。

① 部署时序:买后上新板**当轮生效**(r1 买的件出现在 r1 账本行
   state.deployed)+ LevelUp 当轮 cap 生效 + deploy_lag_units 恒 0;
② 凑档触发:锁线+战斗轮+目标全缺+1-2 费+阵营凑 2 档 → reason
   ='bond_fallback';
③ 不触发:目标在店 / r1-r2 / cost>2 / 阵营不在 board∪bench /
   未锁线(五门各一反例);
④ 部署侧:tgt 空集时凑档件不被配方围栏拦;tgt 非空围栏照旧
   (不挤占目标件位置);
⑤ 检查项双向:deploy_after_buy_semantics / ledger_deploy_lag_
   disclosure / hp_upper_bound_truth / bond_fallback_purchase_
   validity 合法行过 + 逐门变异必涌现。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_deploy_logic import (
    DEPLOY_FENCE,
    select_deployments,
)
from sr_od.application.currency_war.cw_sim import simulate_p1
from sr_od.application.currency_war.cw_sim_checks import (
    check_bond_fallback_purchase_validity,
    check_deploy_after_buy_semantics,
    check_hp_upper_bound_truth,
    check_ledger_deploy_lag_disclosure,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _card(faction: str, name: str, cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0)


def _sess(line: str | None = 'jizi_train') -> StrategySession:
    s = StrategySession()
    s.locked_line = line
    return s


# --- ① 部署时序(ADR-0287) -----------------------------------------------


class _BuyOneThenStop:
    """r1 买首件 + LevelUp,其余段/轮记录快照后停。"""

    def __init__(self) -> None:
        self.bought_name: str | None = None
        self._acted = False

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        if st.round_num == 1 and not self._acted and st.shop:
            self._acted = True
            c = st.shop[0]
            self.bought_name = c.name
            return [BuyCard(card=c, reason='stub'), LevelUp(4)]
        return []


def test_deploy_after_buy_same_round() -> None:
    """买后部署:r1 买的件出现在 r1 账本行 state.deployed(当轮上板),
    LevelUp 当轮 cap 生效(cap=level+1 且 deployed 填满),全轮
    deploy_lag_units==0。"""
    strat = _BuyOneThenStop()
    res = simulate_p1(0, pool='fallback', strategy=strat)
    r1 = res.ledger[0]
    dep_names = [d['char_id'] for d in r1['state']['deployed']]
    assert strat.bought_name in dep_names, \
        'ADR-0287:当轮买的件必须当轮上板(买后部署序)'
    # LevelUp(4xp=lv3 门槛)当轮生效:cap 抬到 4 且部署填满
    assert r1['state']['cap'] == 4, '升级当轮 cap 应即时生效(批㉘ F5)'
    assert len(dep_names) == 4, '新 cap 应被当轮部署填满'
    assert all((row['sim'].get('deploy_lag_units') == 0)
               for row in res.ledger), '轮末围栏残留可上件应恒 0'


# --- ②③ 凑档触发/不触发(ADR-0288 买侧) ---------------------------------


def _bf_state(shop_cards: list, board: dict | None = None,
              rn: int = 4) -> GameState:
    return GameState(plane=1, round_num=rn, gold=30, level=4,
                     board=board or {'贝洛伯格': 1}, bench=[],
                     shop=shop_cards)


def test_bond_fallback_triggers_on_full_target_miss() -> None:
    """锁线+战斗轮+目标全缺+1-2 费+阵营凑 2 档 → True / 标签正确。"""
    st = _bf_state([_card('贝洛伯格', '佩拉', 2)])
    s = _sess()
    assert LineStrategy()._bond_fallback_wants(
        _card('贝洛伯格', '佩拉', 2), st, s), '五门全过应放行'
    assert LineStrategy()._want_label(
        _card('贝洛伯格', '佩拉', 2), st, s) == 'bond_fallback'


def test_bond_fallback_blocked_by_each_gate() -> None:
    """五门反例:任一不过即拒(0 容忍检查的谓词侧锚)。"""
    s = _sess()
    strat = LineStrategy()
    pela = _card('贝洛伯格', '佩拉', 2)
    # ① 目标在店(carry 姬子·启行 / opportunistic 三月七 / core 娜塔莎)
    for tgt_name in ('姬子·启行', '三月七', '娜塔莎'):
        st = _bf_state([_card('贝洛伯格', '佩拉', 2),
                        _card('列车同行', tgt_name, 2)])
        assert not strat._bond_fallback_wants(pela, st, s), \
            f'目标件 {tgt_name} 在店 → 主通道辖,不降级'
    # ② 非战斗轮(r1-r2 纯付息,P3 口径)
    assert not strat._bond_fallback_wants(
        pela, _bf_state([pela], rn=2), s), 'r2 无战斗不触发'
    # ③ 成本带:cost>2 拒
    assert not strat._bond_fallback_wants(
        _card('贝洛伯格', '佩拉', 3), _bf_state(
            [_card('贝洛伯格', '佩拉', 3)]), s), 'cost>2 超成本带'
    # ④ 阵营不在 board∪bench(凑 2 档不成立)
    st = _bf_state([pela], board={'欢愉': 1})
    assert not strat._bond_fallback_wants(pela, st, s), \
        '无同阵营第一块砖 → 凑 2 档不成立'
    # ⑤ 未锁线(桥方向期不辖)
    assert not strat._bond_fallback_wants(
        pela, _bf_state([pela]), _sess(line=None)), '未锁线不辖'


def test_bond_fallback_not_a_refresh_target() -> None:
    """降级件不进 _maybe_refresh 目标判据(不拦刷新)。"""
    st = _bf_state([_card('贝洛伯格', '佩拉', 2)])
    st.gold = 40
    acts = LineStrategy()._maybe_refresh(st, _sess(), 40)
    assert isinstance(acts, list), '目标全缺时刷新通道照常(降级≠目标)'


# --- ④ 部署侧(ADR-0288) --------------------------------------------------


def test_deploy_bond_paired_up_when_no_target() -> None:
    """tgt 空集:凑档件(非围栏阵营,board 凑 2 档)不被配方围栏拦。

    阵营口径注意:select_deployments 的 bench_fac 取注册表
    CHARACTERS[cid].factions[0](非 BenchChar.faction 入参)——测试
    件选 艾丝妲(银河学者,非围栏阵营)保证口径成立。"""
    assert '银河学者' not in DEPLOY_FENCE, '测试前提:银河学者非围栏阵营'
    bond = BenchChar(char_id='艾丝妲', faction='银河学者', slot=1)
    dep_cids = {f'已上{i}' for i in range(9)}   # vacancy=1 → not roomy
    up, held = select_deployments(
        [bond], deployed_cids=dep_cids,
        deployed_fac={'银河学者': 1}, board={'银河学者': 1}, cap=10,
        target_factions=frozenset())
    assert 0 in up and not held, \
        'ADR-0288:tgt 空集时凑档件必须上(board 凑 2 档)'


def test_deploy_fence_kept_when_target_present() -> None:
    """tgt 非空:围栏照旧——凑档件让位,不挤占目标件位置。"""
    bond = BenchChar(char_id='艾丝妲', faction='银河学者', slot=1)
    tgt = BenchChar(char_id='三月七', faction='列车同行', slot=2)
    dep_cids = {f'已上{i}' for i in range(9)}
    up, held = select_deployments(
        [bond, tgt], deployed_cids=dep_cids,
        deployed_fac={'银河学者': 1, '列车同行': 1},
        board={'银河学者': 1, '列车同行': 1}, cap=10,
        target_factions=frozenset({'列车同行'}))
    assert 0 in held, 'tgt 在场时围栏照旧(降级件不稀释配方)'
    assert 1 in up, '目标件优先占位'


# --- ⑤ 检查项双向 ----------------------------------------------------------


def _bf_row(**mut) -> dict:
    """合法 bond_fallback 账本行;mut 逐门变异。"""
    row = {
        'plane': 1, 'round_num': 4, 'gold': 20, 'hp': 40,
        'target_comp': 'jizi_train',
        'state': {'board': {'贝洛伯格': 1}, 'level': 4,
                  'bench': [{'char_id': '佩拉', 'faction': '贝洛伯格',
                             'slot': 1}],
                  'deployed': [], 'cap': 4},
        'actions': [
            {'__type__': 'RefreshShop', 'cost': 2},
            {'__type__': 'BuyCard',
             'card': {'name': '佩拉', 'faction': '贝洛伯格',
                      'cost': 2, 'x': 0},
             'reason': 'bond_fallback'}],
        'sim': {'node': 'battle',
                'shop_waves': [
                    {'event': 'offer', 'gold': 20,
                     'cards': [{'name': '桑博', 'faction': '贝洛伯格',
                                'cost': 1}]},
                    {'event': 'refresh', 'gold': 18,
                     'cards': [{'name': '佩拉', 'faction': '贝洛伯格',
                                'cost': 2}]}],
                'deploy_lag_units': 0},
    }
    row.update(mut)
    return row


def test_check_bond_fallback_valid_row_passes() -> None:
    assert check_bond_fallback_purchase_validity([_bf_row()]) == []


def test_check_bond_fallback_each_mutation_flagged() -> None:
    """逐门变异必涌现(0 容忍;未锁线/早轮/成本带/目标在店/阵营)。"""
    # 未锁线
    assert check_bond_fallback_purchase_validity(
        [_bf_row(target_comp='')])
    # 非战斗轮(r2)
    r = _bf_row(round_num=2)
    assert check_bond_fallback_purchase_validity([r])
    # 成本带:cost=3
    r = _bf_row()
    r['actions'][1]['card'] = dict(r['actions'][1]['card'], cost=3)
    assert check_bond_fallback_purchase_validity([r])
    # 目标在店:刷新波内补一个 opportunistic(三月七)未买
    r = _bf_row()
    r['sim']['shop_waves'][1]['cards'].append(
        {'name': '三月七', 'faction': '列车同行', 'cost': 1})
    assert check_bond_fallback_purchase_validity([r])
    # 阵营不在已有阵营(board/bench 全换欢愉系)
    r = _bf_row()
    r['state']['board'] = {'欢愉': 1}
    r['state']['bench'] = [{'char_id': '花火', 'faction': '欢愉',
                            'slot': 1}]
    assert check_bond_fallback_purchase_validity([r])


def test_check_deploy_timing_and_hp_bounds_bidirectional() -> None:
    """deploy_lag>0 / 字段缺失 / hp>100 三检查双向。"""
    ok = _bf_row()
    assert check_deploy_after_buy_semantics([ok]) == []
    assert check_ledger_deploy_lag_disclosure([ok]) == []
    assert check_hp_upper_bound_truth([ok]) == []
    # deploy_lag_units>0 → 部署时序违规
    bad = _bf_row()
    bad['sim'] = dict(bad['sim'], deploy_lag_units=2)
    assert check_deploy_after_buy_semantics([bad])
    # 字段缺失 → 披露断裂
    bad = _bf_row()
    bad['sim'] = {k: v for k, v in bad['sim'].items()
                  if k != 'deploy_lag_units'}
    assert check_ledger_deploy_lag_disclosure([bad])
    # hp>100 → 上界哨兵
    bad = _bf_row(hp=101)
    assert check_hp_upper_bound_truth([bad])
