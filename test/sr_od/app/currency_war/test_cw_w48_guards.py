"""W48 修复批单帧锁测试(W43 leader 裁决 1-4;同名守卫/代际校验/账本/检查器归一化)。

契约来源:`.debug/temp/currency_war/cw_dev/deep_read/W43_报告.md` Leader 裁决:
1. 【阻塞】CompTransaction/SwapDeploy/FillSpec/BuyCard 上场链同名唯一性守卫
   (场上同角色仅 1;违反 → 整事务拒绝 reason='duplicate_on_board',进 action_log);
2. 【阻塞】提案应用时代际校验(生成→应用之间 idx 指向内容已变 → stale_proposal
   拒绝,不套用陈旧引用);
3. 【高】sim 账本 target_comp 补 v3 意向 comp 名(判读依赖);
4. 【高】no_same_round_buy_sell/oscillation_xp_cap/engine_seed_not_resold 对
   d2_ 前缀 reason 的归一化(误报+失明同修)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_sim import (
    _target_comp_label,
    simulate_p1,
)
from sr_od.application.currency_war.cw_sim_checks import (
    check_engine_seed_not_resold,
    check_no_same_round_buy_sell,
    check_oscillation_xp_cap,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    CompTransaction,
    DeployMove,
    FillSpec,
    GameState,
    SellDeployed,
    ShopCard,
    SwapDeploy,
    _recount_board,
    bench_occupied,
    deployed_occupied,
    iter_occupied_deployed,
    board_unique_key,
    mutate_bench_deployed,
    simulate,
)


def _char(name: str, slot: int = 0, row: str = 'back') -> BenchChar:
    """注册表真值构造 BenchChar(faction 单一源)。"""
    c = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row)


def _dup_fixture() -> GameState:
    """旧档 3 人在场 + bench 含「已上场同名副本」+ 异名件的单帧。"""
    names = [n for n, c in CHARACTERS.items()
             if (c.factions or [''])[0] == '贝洛伯格'][:3]
    assert len(names) == 3, '测试假设:贝洛伯格系 ≥3 人(注册表)'
    # ADR-0392:构造器入参 → __post_init__ pad 槽位表(与 simulate 出态同形)
    st = GameState(gold=30, level=8,
                   deployed=[_char(nm, slot=i) for i, nm in enumerate(names)],
                   bench=[_char(names[0], slot=10), _char('青雀', slot=11)])
    st.board = _recount_board(st.deployed)
    return st


# ---------- 裁决 1:同名唯一性守卫(正反例) ----------

def test_tx_duplicate_on_board_rejected_whole():
    """【阻塞·反例】提案含「已上场同名」→ 整事务拒绝,状态零残留。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    tx = CompTransaction(deploy=[(0, 'back')], undeploy=[], sell=[],
                         reason='evolve')
    out = simulate(st, tx)
    log = out.action_log[-1]
    assert log['action'] == 'CompTransaction'
    assert log['result'] == 'rejected'
    assert 'duplicate_on_board' in log['reason']
    assert dup_name in log['reason']
    # 原子:无部分应用痕迹(拒绝记录本身除外)
    out.action_log = []
    st.action_log = []
    # ADR-0316:simulate 入口 pad bench 到定长 9,原子性对照只看占用内容
    assert bench_occupied(out.bench) == bench_occupied(st.bench)
    assert [c.char_id for c in out.bench if c] \
        == [c.char_id for c in st.bench if c]
    assert out.deployed == st.deployed and out.gold == st.gold


def test_tx_duplicate_via_undeploy_swap_ok():
    """【正例】先下再上同名(换血)不是重复——终态名单唯一即过。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    tx = CompTransaction(deploy=[(0, 'back')], undeploy=[0], sell=[],
                         reason='swap_same_name')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied'
    names = [c.char_id for c in iter_occupied_deployed(out.deployed)]
    assert names.count(dup_name) == 1


def test_tx_fill_bench_duplicate_rejected():
    """【反例】fill bench 源指向已上场同名 → 整事务拒绝。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    tx = CompTransaction(deploy=[(1, 'back')], undeploy=[], sell=[],
                         fill=[FillSpec(source='bench', idx=0, row='back')],
                         reason='fill_dup')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'duplicate_on_board' in out.action_log[-1]['reason']
    # 原子:fill/deploy 均未应用
    assert deployed_occupied(out.deployed) == 3 and dup_name in \
        {c.char_id for c in iter_occupied_deployed(out.deployed)}


def test_tx_fill_shop_duplicate_rejected():
    """【反例】shop 填位买后即上,与场上留任者同名 → 整事务拒绝。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    st.shop = [ShopCard(x=0, faction='贝洛伯格', name=dup_name, cost=2)]
    tx = CompTransaction(deploy=[(1, 'back')], undeploy=[], sell=[],
                         fill=[FillSpec(source='shop', idx=0, row='back')],
                         reason='shop_dup')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'duplicate_on_board' in out.action_log[-1]['reason']
    assert out.gold == 30 and len(out.shop) == 1   # 金/店槽均未消费


def test_swap_deploy_duplicate_rejected():
    """【反例】SwapDeploy 上场者与场上其余单位同名 → 拒绝(显式通道不旁路)。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    # bench[0] = deployed[0] 同名;换掉 deployed[1] → 场上会出现 dup_name×2
    out = simulate(st, SwapDeploy(1, 0, reason='swap'))
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'duplicate_on_board' in out.action_log[-1]['reason']
    assert dup_name in out.action_log[-1]['reason']
    # 【正例】换掉同名本尊(1 换 1)合法
    out2 = simulate(st, SwapDeploy(0, 0, reason='swap'))
    assert out2.action_log[-1]['result'] == 'applied'
    assert [c.char_id for c in iter_occupied_deployed(out2.deployed)]\
        .count(dup_name) == 1


def test_deploy_move_duplicate_rejected_and_logged():
    """【反例】单卡上场(DeployMove)同理拒绝 + 进 action_log。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    out = simulate(st, DeployMove(bench_idx=0, to_row='front',
                                  faction=st.bench[0].faction))
    log = out.action_log[-1]
    assert log == {'action': 'DeployMove', 'result': 'rejected',
                   'reason': f'duplicate_on_board:{dup_name}'}
    assert deployed_occupied(out.deployed) == 3 \
        and bench_occupied(out.bench) == 2   # 零残留(ADR-0392 占用数)
    # 【正例】异名上场照常
    out2 = simulate(st, DeployMove(bench_idx=1, to_row='back',
                                   faction=st.bench[1].faction))
    assert deployed_occupied(out2.deployed) == 4   # ADR-0392 占用数
    assert any(c.char_id == '青雀'
               for c in iter_occupied_deployed(out2.deployed))


def test_board_unique_key_trailblazer_and_unknown():
    """唯一性键:开拓者各形态归一;空 char_id(未知身份)不参与查重。"""
    tb_names = [n for n in CHARACTERS
                if n.startswith('开拓者')][:2]
    if len(tb_names) >= 2:
        assert board_unique_key(_char(tb_names[0])) == \
            board_unique_key(_char(tb_names[1]))
    assert board_unique_key(BenchChar(slot=0, char_id='')) is None
    assert board_unique_key(_char('青雀')) == '青雀'


def test_mutate_bench_deployed_parity_guards():
    """运行时跟踪侧(mutate)与 simulate 同源守卫:重复/stale 均 no-op。"""
    bench = [_char('青雀', slot=0)]
    deployed = [_char('青雀', slot=1, row='front'),
                _char('符玄', slot=2, row='back')]
    # DeployMove 同名 → no-op
    mutate_bench_deployed(bench, deployed,
                          DeployMove(0, 'back', '量子同频'))
    assert bench_occupied(bench) == 1 \
        and deployed_occupied(deployed) == 2   # ADR-0392 占用数
    # SwapDeploy 上场者与场上其余同名 → no-op
    mutate_bench_deployed(bench, deployed, SwapDeploy(1, 0))
    assert deployed[1].char_id == '符玄' and bench[0].char_id == '青雀'
    # SellDeployed 代际不符 → no-op(相符 → 正常执行)
    mutate_bench_deployed(bench, deployed, SellDeployed(1, expect='别人'))
    assert deployed_occupied(deployed) == 2
    mutate_bench_deployed(bench, deployed, SellDeployed(1, expect='符玄'))
    assert deployed_occupied(deployed) == 1 \
        and deployed[0].char_id == '青雀'   # ADR-0392:置 None 计占用


# ---------- 裁决 2:代际校验(提案生成→应用之间 idx 已变) ----------

def test_tx_stale_fill_bench_expect_rejected():
    """fill bench 源 idx 指向内容与提案不符 → stale_proposal 整事务拒绝。"""
    st = _dup_fixture()
    tx = CompTransaction(deploy=[], undeploy=[], sell=[],
                         fill=[FillSpec(source='bench', idx=0, row='back',
                                        expect='符玄')],   # 实际指向 deployed[0] 同名
                         reason='stale')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal' in out.action_log[-1]['reason']
    # 【正例】expect 与内容一致 → 通过(bench[1]=青雀;后置 bench 未迁移)
    tx2 = CompTransaction(deploy=[], undeploy=[],
                          sell=[(1, 'deployed')],
                          fill=[FillSpec(source='bench', idx=1, row='back',
                                         expect='青雀')],
                          reason='fresh')
    out2 = simulate(st, tx2)
    assert out2.action_log[-1]['result'] == 'applied'


def test_tx_stale_fill_shop_expect_rejected():
    """fill shop 源 idx 指向的卡与提案不符 → stale_proposal 拒绝。"""
    st = _dup_fixture()
    st.shop = [ShopCard(x=0, faction='仙舟', name='符玄', cost=3)]
    tx = CompTransaction(deploy=[], undeploy=[], sell=[],
                         fill=[FillSpec(source='shop', idx=0, row='back',
                                        expect='白露')],
                         reason='stale_shop')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal:fill_shop' in out.action_log[-1]['reason']
    assert out.gold == 30 and len(out.shop) == 1   # 金/槽不消费


def test_tx_stale_deploy_undeploy_sell_expect_rejected():
    """deploy/undeploy/sell 的 expect 序列与索引同序对齐,不符即拒绝。"""
    st = _dup_fixture()
    # deploy expect 不符
    tx = CompTransaction(deploy=[(1, 'back')], undeploy=[], sell=[],
                         expect_deploy=['符玄'], reason='stale_dep')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal:deploy_bench' in out.action_log[-1]['reason']
    # undeploy expect 不符
    tx2 = CompTransaction(deploy=[(1, 'back')], undeploy=[1], sell=[],
                          expect_undeploy=['别人'], reason='stale_und')
    out2 = simulate(st, tx2)
    assert 'stale_proposal:undeploy' in out2.action_log[-1]['reason']
    # sell expect 不符
    tx3 = CompTransaction(deploy=[], undeploy=[], sell=[(1, 'bench')],
                          expect_sell=['别人'], reason='stale_sell')
    out3 = simulate(st, tx3)
    assert 'stale_proposal:sell_bench' in out3.action_log[-1]['reason']
    # 长度不对齐 → 拒绝(防半配对静默跳过)
    tx4 = CompTransaction(deploy=[(1, 'back')], undeploy=[], sell=[],
                          expect_deploy=[], reason='len')
    assert 'expect_deploy_len' in simulate(st, tx4).action_log[-1]['reason']


def test_swap_and_sell_stale_expect_rejected():
    """SwapDeploy/SellDeployed 的跨轮登记提案(谷底回滚)代际不符 → 拒绝。"""
    st = _dup_fixture()
    out = simulate(st, SwapDeploy(0, 0, reason='valley_rollback',
                                  expect_deployed='别人',
                                  expect_bench=st.bench[0].char_id))
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal' in out.action_log[-1]['reason']
    out2 = simulate(st, SellDeployed(0, reason='valley_rollback',
                                     expect='别人'))
    assert out2.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal' in out2.action_log[-1]['reason']
    # 【正例】expect 相符照常执行
    out3 = simulate(st, SellDeployed(0, reason='valley_rollback',
                                     expect=st.deployed[0].char_id))
    assert out3.action_log[-1]['result'] == 'applied'


def test_sim_redecide_after_shop_fill_tx_no_phantom():
    """裁决 2 根治面:事务 fill 消费店槽后同批陈旧 BuyCard 作废并重决策。

    桩:首批返回 [shop-fill 事务, 同卡 BuyCard](旧代码 = 幻影再买,
    phantom_rebuys 披露);修复后 break 重决策 → 幻影 0、同批买不执行。
    """

    class _TxFillStub:
        def __init__(self) -> None:
            self.fired = False

        def update_target(self, st, sess, screen) -> None:   # noqa: ARG002
            pass

        def decide_prep(self, st, sess, screen):   # noqa: ARG002
            if not self.fired and st.shop:
                self.fired = True
                card = st.shop[0]
                tx = CompTransaction(
                    deploy=[], undeploy=[], sell=[],
                    fill=[FillSpec('shop', 0, 'back', expect=card.name)],
                    reason='probe_tx')
                return [tx, BuyCard(card, reason='probe_phantom')]
            return []

    stub = _TxFillStub()
    res = simulate_p1(11, strategy=stub, pool='fallback')
    assert stub.fired, '桩应在首轮点火'
    assert res.phantom_rebuys == 0, '店槽消费后陈旧买提案应作废重生成'
    # 事务确实 applied(重决策不是把事务也丢了)
    tx_rows = [row for row in res.ledger
               if any(a.get('__type__') == 'CompTransaction'
                      and a.get('result') == 'applied'
                      for a in row.get('actions') or [])]
    assert len(tx_rows) == 1


# ---------- 裁决 3:账本 target_comp 补 v3 意向 ----------

def test_target_comp_label_v3_fallback_and_v2_priority():
    """账本 target_comp = v3_intention.locked_comp(ADR-0336 后唯一
    源;旧 locked_line/bridge_id 优先分支随 LineStrategy 删除)。"""
    sess = SimpleNamespace(locked_line=None, bridge_id=None,
                           v3_intention=SimpleNamespace(locked_comp='仙舟3'))
    assert _target_comp_label(sess) == '仙舟3'
    # 旧 v1 字段不再被读(ADR-0336);意向缺失 → 空
    sess2 = SimpleNamespace(locked_line='DOT2', bridge_id=None,
                            v3_intention=SimpleNamespace(locked_comp='仙舟3'))
    assert _target_comp_label(sess2) == '仙舟3'
    sess3 = SimpleNamespace(locked_line=None, bridge_id='列车2',
                            v3_intention=None)
    assert _target_comp_label(sess3) == ''
    sess4 = SimpleNamespace(locked_line=None, bridge_id=None,
                            v3_intention=None)
    assert _target_comp_label(sess4) == ''


def test_sim_ledger_target_comp_reads_v3_intention():
    """sim 集成:decision_v2 型会话(v3 意向)的决策轮账本 target_comp 可读。"""

    class _V3Stub:
        def update_target(self, st, sess, screen) -> None:   # noqa: ARG002
            sess.v3_intention = SimpleNamespace(phase='locked',
                                                locked_comp='仙舟3')

        def decide_prep(self, st, sess, screen):   # noqa: ARG002
            return []

    res = simulate_p1(3, strategy=_V3Stub(), pool='fallback')
    assert res.ledger, 'P1 至少 1 轮账本'
    assert all(row['target_comp'] == '仙舟3' for row in res.ledger)


# ---------- 裁决 4:三检查器 d2_ reason 归一化(误报+失明同修) ----------

def _row(actions: list[dict], rn: int = 1, level: int = 3) -> dict:
    return {'plane': 1, 'round_num': rn,
            'state': {'board': {}, 'level': level, 'bench': [],
                      'deployed': []},
            'actions': actions, 'sim': {}}


def _buy(name: str, reason: str) -> dict:
    return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': 1},
            'reason': reason}


def _sell(name: str) -> dict:
    return {'__type__': 'SellBench', 'name': name}


def test_no_same_round_buy_sell_d2_normalization():
    """d2_ 前缀归一化:d2_engine_seed×2 同轮让位不报(误报修复);
    d2_pair 买后卖仍报(失明不引入);d2_copy 让位不报。"""
    # 误报修复:旧代码裸匹配 'engine_seed' 匹配不上 d2_engine_seed → 误报
    ok_seed = _row([_buy('青雀', 'd2_engine_seed'),
                    _buy('青雀', 'd2_engine_seed'),
                    _sell('青雀')])
    assert check_no_same_round_buy_sell([ok_seed]) == []
    # 豁免语境外的真实同轮买卖(d2_ 前缀)仍 0 容忍报出
    bad_pair = _row([_buy('青雀', 'd2_pair'), _sell('青雀')])
    v = check_no_same_round_buy_sell([bad_pair])
    assert v and '青雀' in v[0]
    # copy 让位豁免在 d2_ 前缀下同样生效
    ok_copy = _row([_buy('青雀', 'd2_copy_merge'), _sell('青雀')])
    assert check_no_same_round_buy_sell([ok_copy]) == []
    # 单张 d2_engine_seed 买后即卖(振荡主通道)仍报
    bad_seed = _row([_buy('青雀', 'd2_engine_seed'), _sell('青雀')])
    assert check_no_same_round_buy_sell([bad_seed])


def test_engine_seed_not_resold_d2_no_longer_blind():
    """失明修复:d2_engine_seed 买入 ≤2 轮内回卖此前裸匹配不上 → 恒 0;
    归一化后必须报出。"""
    rows = [
        _row([_buy('青雀', 'd2_engine_seed')], rn=1),
        _row([_sell('青雀')], rn=2),
    ]
    v = check_engine_seed_not_resold(rows)
    assert v and '青雀' in v[0]
    # 收集语境(同轮 ≥2)+ 次轮让位 → 不报
    rows_ok = [
        _row([_buy('青雀', 'd2_engine_seed'),
              _buy('青雀', 'd2_engine_seed')], rn=1),
        _row([_sell('青雀')], rn=2),
    ]
    assert check_engine_seed_not_resold(rows_ok) == []
    # >2 轮后卖出 → 窗口外不报
    rows_late = [
        _row([_buy('青雀', 'engine_seed')], rn=1),
        _row([_sell('青雀')], rn=4),
    ]
    assert check_engine_seed_not_resold(rows_late) == []


def test_oscillation_xp_cap_d2_normalization():
    """d2_engine_seed 收集语境不计振荡;d2_pair 振荡照计。"""
    # lv3:升级需 4 XP,30% = 1.2 → 1 次振荡(4 XP)即报
    ok = _row([_buy('青雀', 'd2_engine_seed'),
               _buy('青雀', 'd2_engine_seed'),
               _sell('青雀')])
    assert check_oscillation_xp_cap([ok]) == []
    bad = _row([_buy('青雀', 'd2_pair'), _sell('青雀')])
    v = check_oscillation_xp_cap([bad])
    assert v and '振荡' in v[0]
