"""动作集 v2(契约包 C1,步 2 sim-P1 扩域)单帧锁测试。

契约来源:`.debug/temp/currency_war/cw_dev/deep_read/契约包_C1-C7.md` C1 节
+ 六矛盾裁决 1(围栏跳过须记账本一行 skip_fence;显式>围栏同轮互斥)。

四条验收落地(对应 C1「验收测试想法」1-3 + 任务 6 开关联动):
1. DOT2→仙舟3 整档替换:旧档 0 人在场、新档全员在场、无半档;
2. 原子性拒绝:金不足 → 事务整体拒绝,状态与账本均无部分应用痕迹;
3. checks 渗透:事务原子性/围栏跳过可见性/skip_fence 配对(含变异探针
   ——去门必须涌现违规);
4. 开关联动:显式动作发出轮围栏跳过 + skip_fence 记账(sim 集成)。
"""
from sr_od.application.currency_war.data.cw_chars import CHARACTERS

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_comp_tx_atomicity,
    check_skip_fence_pairing,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    CompTransaction,
    FillSpec,
    GameState,
    SellDeployed,
    ShopCard,
    SwapDeploy,
    _recount_board,
    deployed_occupied,
    iter_occupied_deployed,
    mutate_bench_deployed,
    sell_refund,
    simulate,
)


def _char(name: str, slot: int = 0, row: str = 'back') -> BenchChar:
    """注册表真值构造 BenchChar(faction/cost 单一源)。"""
    c = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row)


def _xianzhou_trio() -> list[BenchChar]:
    """仙舟铁三角(= cw_line_defs._CORE_TRIO;注册表真值)。"""
    from sr_od.application.currency_war.kernel.cw_line_defs import _CORE_TRIO
    return [_char(n, slot=i) for i, n in enumerate(sorted(_CORE_TRIO))]


def _old_line_deployed(n: int = 3) -> list[BenchChar]:
    """旧档(DOT 过渡占位):非仙舟阵营角色若干(贝洛伯格系)。"""
    names = [n for n, c in CHARACTERS.items()
             if (c.factions or [''])[0] == '贝洛伯格'][:n]
    assert len(names) == n, '测试假设:贝洛伯格系 ≥3 人(注册表)'
    return [_char(nm, slot=i) for i, nm in enumerate(names)]


def _tx_state() -> GameState:
    """DOT2 在场 + 仙舟铁三角 bench 齐 的单帧(验收1 构造)。"""
    # ADR-0392:构造器入参 → __post_init__ pad 槽位表(与 simulate 出态同形)
    st = GameState(gold=20, level=8,
                   deployed=_old_line_deployed(3),
                   bench=_xianzhou_trio() + [_char('青雀', slot=3)])
    st.board = _recount_board(st.deployed)
    return st


# ---------- 1. DOT2 → 仙舟3 整档替换(无半档) ----------

def test_comp_transaction_full_swap_no_half_state():
    st = _tx_state()
    old_names = [c.char_id for c in iter_occupied_deployed(st.deployed)]
    _income = sum(sell_refund(
        c.star, CHARACTERS[c.char_id].cost)
        for c in iter_occupied_deployed(st.deployed)) \
        + sell_refund(1, CHARACTERS['青雀'].cost)
    tx = CompTransaction(
        deploy=[(0, 'front'), (1, 'back'), (2, 'back')],
        undeploy=[],
        # 旧档整档直接卖出 + 新档换位余料(青雀)卖出:一次敲定无残留
        sell=[(0, 'deployed'), (1, 'deployed'), (2, 'deployed'),
              (3, 'bench')],
        fill=None,
        reason='evolve:DOT2→仙舟3')
    out = simulate(st, tx)
    # 旧档 0 人在场:deployed 全为铁三角
    trio = {c.char_id for c in iter_occupied_deployed(out.deployed)}
    from sr_od.application.currency_war.kernel.cw_line_defs import _CORE_TRIO
    assert trio == set(_CORE_TRIO)
    assert deployed_occupied(out.deployed) == 3   # ADR-0392 占用数
    # 新档全员在场:仙舟 3(ADR-0312 W50 全集口径——board 另含铁三角的
    # 流派/副阵营键,精确等值由下行 _recount_board 一致性锁辖)
    assert out.board.get('仙舟') == 3
    # 无半档:board 与 deployed 聚合一致;旧档/余料不在 bench 不在场上
    # (ADR-0316 槽位表:全空=bench_occupied==0,len(bench) 恒 9)
    assert out.board == _recount_board(out.deployed)
    from sr_od.application.currency_war.kernel.cw_state import bench_occupied
    assert bench_occupied(out.bench) == 0
    assert all(n not in {b.char_id for b in out.bench if b is not None}
               for n in old_names)
    # 卖出回金入账(旧档 3 人 + 青雀)
    assert out.gold == 20 + _income
    # 原状态不被改(simulate 纯函数)
    assert deployed_occupied(st.deployed) == 3 \
        and bench_occupied(st.bench) == 4
    assert out.action_log[-1] == {'action': 'CompTransaction',
                                  'result': 'applied',
                                  'reason': 'evolve:DOT2→仙舟3',
                                  'income': _income,
                                  'fill_cost': 0}


# ---------- 2. 原子性:任一子步资源不足 → 整体拒绝 ----------

def test_comp_transaction_rejected_gold_short_no_partial_apply():
    st = _tx_state()
    st.gold = 0
    st.shop = [ShopCard(x=0, faction='仙舟', name='符玄', cost=3)]
    tx = CompTransaction(
        deploy=[(0, 'front'), (1, 'back'), (2, 'back')],
        undeploy=[0, 1, 2],
        sell=[(3, 'bench')],
        fill=[FillSpec(source='shop', idx=0, row='back')],
        reason='evolve+fill')
    out = simulate(st, tx)
    # 整体拒绝:状态与原状态完全一致(无任何部分应用痕迹)
    out.action_log = []   # 唯一允许的差异 = 拒绝记录本身
    st.action_log = []
    # ADR-0316:simulate 入口 pad bench 到定长 9,原子性对照只看占用内容
    from sr_od.application.currency_war.kernel.cw_state import bench_occupied
    assert bench_occupied(out.bench) == bench_occupied(st.bench)
    assert [c.char_id for c in out.bench if c] \
        == [c.char_id for c in st.bench if c]
    assert out.deployed == st.deployed and out.gold == st.gold
    # 拒绝记录进账本(checks 可见)
    assert simulate(st, tx).action_log[-1]['result'] == 'rejected'
    assert 'gold_short' in simulate(st, tx).action_log[-1]['reason']


def test_comp_transaction_rejected_cap_and_overlap():
    st = _tx_state()
    st.level = 3   # cap=3:终态 deployed 3+4=7 > cap → 拒绝
    tx = CompTransaction(deploy=[(0, 'front'), (1, 'back'), (2, 'back'),
                                 (3, 'back')],
                         undeploy=[], sell=[], reason='cap')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'deploy_cap_exceeded' in out.action_log[-1]['reason']
    assert deployed_occupied(out.deployed) == 3   # 未动(ADR-0392 占用数)
    # deploy 与 sell 指向同 bench 槽 → 拒绝
    tx2 = CompTransaction(deploy=[(0, 'front')], undeploy=[],
                          sell=[(0, 'bench')], reason='overlap')
    assert 'overlap' in simulate(st, tx2).action_log[-1]['reason']


# ---------- 3. deployed 生命周期:SellDeployed / SwapDeploy ----------

def test_sell_deployed_lifecycle():
    st = _tx_state()
    sold = st.deployed[1]
    sold.equips = ['虚构装备']
    out = simulate(st, SellDeployed(1, reason='evict_replaced'))
    assert deployed_occupied(out.deployed) == 2   # ADR-0392 占用数
    assert all(c is not sold for c in iter_occupied_deployed(out.deployed))
    assert out.board == _recount_board(out.deployed)
    assert out.gold == 20 + sell_refund(
        sold.star, CHARACTERS[sold.char_id].cost)
    assert out.equips == ['虚构装备']   # 装备回收进 owned(守恒假设)
    assert out.action_log[-1]['result'] == 'applied'
    # 越界 → 拒绝 + 状态不变
    out2 = simulate(st, SellDeployed(99))
    assert out2.action_log[-1]['result'] == 'rejected'
    out2.action_log = []
    st.action_log = []
    from sr_od.application.currency_war.kernel.cw_state import bench_occupied
    assert bench_occupied(out2.bench) == bench_occupied(st.bench)
    assert out2.deployed == st.deployed and out2.gold == st.gold


def test_swap_deploy_equips_follow_char():
    st = _tx_state()
    in_char, out_char = st.bench[0], st.deployed[0]
    in_char.equips = ['铁三角专属件']
    out = simulate(st, SwapDeploy(0, 0, reason='swap'))
    assert out.deployed[0].char_id == in_char.char_id
    assert out.deployed[0].equips == ['铁三角专属件']   # 装备随人走
    assert out.deployed[0].position_pref == out_char.position_pref  # 继承排
    assert out.bench[0].char_id == out_char.char_id
    assert out.board == _recount_board(out.deployed)
    # 越界 → 拒绝
    assert simulate(st, SwapDeploy(0, 99)).action_log[-1]['result'] \
        == 'rejected'


def test_mutate_bench_deployed_v2_actions():
    from sr_od.application.currency_war.kernel.cw_state import (
        bench_occupied,
        pad_bench,
    )
    bench = pad_bench(_xianzhou_trio() + [_char('青雀', slot=3)])
    deployed = _old_line_deployed(3)
    n0 = (bench_occupied(bench), deployed_occupied(deployed))
    mutate_bench_deployed(bench, deployed, SellDeployed(0))
    assert deployed_occupied(deployed) == n0[1] - 1   # ADR-0392 置 None
    mutate_bench_deployed(bench, deployed, SwapDeploy(0, 0))
    assert bench_occupied(bench) == n0[0] \
        and deployed_occupied(deployed) == n0[1] - 1
    # 事务部分:重建干净 fixture(上面两步已移动槽位)
    bench = pad_bench(_xianzhou_trio() + [_char('青雀', slot=3)])
    deployed = _old_line_deployed(3)
    tx = CompTransaction(deploy=[(0, 'front'), (1, 'back'), (2, 'back')],
                         undeploy=[0, 1, 2], sell=[(3, 'bench')],
                         reason='evolve')
    mutate_bench_deployed(bench, deployed, tx)
    assert {c.char_id for c in iter_occupied_deployed(deployed)} == {
        c.char_id for c in _xianzhou_trio()}
    assert bench_occupied(bench) == 3   # 旧档下场进 bench(转移语义;卖出走生产侧)
    # 拒绝路径:越界事务整体不动
    tx_bad = CompTransaction(deploy=[(99, 'front')], undeploy=[],
                             sell=[], reason='bad')
    b2, d2 = list(bench), list(deployed)
    mutate_bench_deployed(b2, d2, tx_bad)
    assert [(c.char_id, c.slot) for c in b2 if c is not None] == \
        [(c.char_id, c.slot) for c in bench if c is not None]
    assert deployed_occupied(d2) == deployed_occupied(deployed)


# ---------- 4. checks 渗透(含变异探针:去门必须涌现违规) ----------

def _agg(dep: list[dict]) -> dict[str, int]:
    """账本行 deployed 的羁绊全集聚合(ADR-0312 W50;unit_bond_tags 同源)。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_bond_equips import unit_bond_tags
    out: dict[str, int] = {}
    for d in dep:
        ns = SimpleNamespace(
            char_id=d.get('char_id') or '',
            position_pref=d.get('position_pref') or 'back',
            faction=d.get('faction') or '',
            equips=d.get('equips') or [])
        tags = unit_bond_tags(ns)
        if tags:
            for t in tags:
                out[t] = out.get(t, 0) + 1
            continue
        f = d.get('faction')
        if f and f != '?':
            out[f] = out.get(f, 0) + 1
    return out


def _row(actions: list[dict], board: dict | None = None,
         deployed: list[dict] | None = None) -> dict:
    dep = deployed if deployed is not None else [
        {'char_id': '藿藿', 'faction': '仙舟', 'slot': 0,
         'position_pref': 'back'}]
    return {'plane': 1, 'round_num': 3, 'state': {
        'board': board if board is not None else _agg(dep),
        'deployed': dep}, 'actions': actions, 'sim': {}}


def test_check_comp_tx_atomicity_locks():
    ok = _row([
        {'__type__': 'CompTransaction', 'result': 'applied',
         'reason': 'evolve'},
        {'__type__': 'skip_fence', 'reason': 'explicit_action_v2'}])
    assert check_comp_tx_atomicity([ok]) == []
    # 变异①:board 与 deployed 聚合不一致(半档残留)→ 涌现违规
    bad = _row(ok['actions'], board={'仙舟': 2})
    v = check_comp_tx_atomicity([bad])
    assert v and '不一致' in v[0]
    # 变异②:拒绝记录缺 reject_reason → 涌现违规
    rej = _row([{'__type__': 'CompTransaction', 'result': 'rejected'}])
    v = check_comp_tx_atomicity([rej])
    assert v and 'reject_reason' in v[0]
    # 拒绝动作不触发 board 一致性分支(拒绝轮状态未变,不检查)
    rej2 = _row([{'__type__': 'CompTransaction', 'result': 'rejected',
                  'reject_reason': 'gold_short:0+1-3<0'}],
                board={})
    assert check_comp_tx_atomicity([rej2]) == []


def test_check_skip_fence_pairing_locks():
    paired = _row([
        {'__type__': 'SellDeployed', 'result': 'applied'},
        {'__type__': 'skip_fence', 'reason': 'explicit_action_v2'}])
    assert check_skip_fence_pairing([paired]) == []
    # 变异①:显式动作无 skip_fence(围栏静默跳过)→ 违规
    v = check_skip_fence_pairing([
        _row([{'__type__': 'SellDeployed', 'result': 'applied'}])])
    assert v and '未配对' in v[0]
    # 变异②:skip_fence 无显式动作(误记)→ 违规
    v = check_skip_fence_pairing([
        _row([{'__type__': 'skip_fence', 'reason': 'x'}])])
    assert v and '误记' in v[0]
    # 变异③:skip_fence 缺 reason → 违规
    v = check_skip_fence_pairing([
        _row([{'__type__': 'SwapDeploy', 'result': 'applied'},
              {'__type__': 'skip_fence', 'reason': ''}])])
    assert v and 'reason' in v[0]
    # 变异④:同轮多条 skip_fence → 违规
    v = check_skip_fence_pairing([
        _row([{'__type__': 'SwapDeploy', 'result': 'applied'},
              {'__type__': 'skip_fence', 'reason': 'x'},
              {'__type__': 'skip_fence', 'reason': 'x'}])])
    assert v and '多条' in v[0]
    # W65/ADR-0323:rejected 显式动作**不**占显式通道(被拒不消耗围栏,
    # 同轮围栏照跑)→ 不要求配对;被拒轮记 skip_fence = 误记
    rej = _row([{'__type__': 'CompTransaction', 'result': 'rejected',
                 'reject_reason': 'duplicate_on_board:万敌'}])
    assert check_skip_fence_pairing([rej]) == [], \
        '被拒事务不要求 skip_fence 配对(W65:被拒不跳围栏)'
    rej_skip = _row([
        {'__type__': 'CompTransaction', 'result': 'rejected',
         'reject_reason': 'duplicate_on_board:万敌'},
        {'__type__': 'skip_fence', 'reason': 'explicit_action_v2'}])
    v = check_skip_fence_pairing([rej_skip])
    assert v and '误记' in v[0], \
        '被拒轮记 skip_fence = 误记(围栏没跳却记账)'


# ---------- 5. 开关联动:显式动作轮围栏跳过(sim 集成) ----------

class _ExplicitStub:
    """测试桩策略:首次见 deployed 非空时发一笔 SellDeployed(其余轮空)。"""

    def __init__(self) -> None:
        self.fired = False

    def update_target(self, st, sess, screen) -> None:   # noqa: ARG002
        pass

    def decide_prep(self, st, sess, screen):   # noqa: ARG002
        # ADR-0392:槽位表滤 None;SellDeployed 打占用槽(空槽会拒)
        occ = [i for i, d in enumerate(st.deployed) if d is not None]
        if not self.fired and occ:
            self.fired = True
            return [SellDeployed(occ[0], reason='plugin_recycle')]
        return []


def test_sim_explicit_action_skips_fence_with_ledger():
    stub = _ExplicitStub()
    res = simulate_p1(7, strategy=stub, pool='fallback')
    assert stub.fired, '桩应在首轮部署后点火'
    assert res.fence_skips == 1
    assert res.explicit_action_rejects == 0
    # 发出轮:SellDeployed applied + skip_fence 同轮配对 + board 一致
    fired_rows = [row for row in res.ledger
                  if any(a.get('__type__') == 'SellDeployed'
                         for a in row.get('actions') or [])]
    assert len(fired_rows) == 1
    row = fired_rows[0]
    types = [a.get('__type__') for a in row['actions']]
    assert 'skip_fence' in types
    assert (row.get('sim') or {}).get('fence_skipped') is True
    # board 一致(ADR-0312 W50 全集口径;_agg 与 unit_bond_tags 同源)
    assert _agg((row.get('state') or {}).get('deployed') or []) \
        == dict((row.get('state') or {}).get('board') or {})
    # 其余轮无 skip_fence(围栏照常)
    assert sum(1 for row in res.ledger
               if any(a.get('__type__') == 'skip_fence'
                      for a in row.get('actions') or [])) == 1
    # 基线不变式:bench 容量/金非负由既有检查网辖,此处冒烟
    assert all(len(r.get('state', {}).get('bench', [])) <= BENCH_CAPACITY
               for r in res.ledger)
