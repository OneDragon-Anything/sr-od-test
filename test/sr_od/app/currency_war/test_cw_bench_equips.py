"""bench 装备 tracking 单一源 + 对账断言(契约包 C6 契约 2)锁测试(W38)。

验收(对应 C6「验收测试想法」3):
- ``assert_equips_consistency``:账面↔画面可读面交叉校验(一致过/不一致 raise/
  bench 侧不可读 visible=None 直接过);
- 装备守恒对账:BuyCard/SellBench/SwapDeploy/CompTransaction/SellDeployed
  动作前后账本多重集守恒(simulate 挂点);
- SellBench 卖带装单位 → 装备回收进 owned 池(修复前漏回收 = 账本凭空消失);
- 构造账本不一致 → 断言报(``assert_ledger_conserved`` raise /
  simulate 挂点记 ``EquipsLedger`` mismatch 条目,不静默)。
"""
from collections import Counter

import pytest

import sr_od.application.currency_war.kernel.cw_bench_equips as cw_bench_equips
from sr_od.application.currency_war.kernel.cw_bench_equips import (
    EquipsInconsistencyError,
    assert_equips_consistency,
    assert_ledger_conserved,
    ledger_mismatch,
    state_equips_multiset,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    CompTransaction,
    GameState,
    SellBench,
    SellDeployed,
    ShopCard,
    SwapDeploy,
    simulate,
)


def _bc(slot: int = 0, char_id: str = '桑博', row: str = 'back',
        equips: list[str] | None = None) -> BenchChar:
    return BenchChar(slot=slot, char_id=char_id, faction='?',
                     position_pref=row, equips=list(equips or []))


# ---------- 1. assert_equips_consistency(画面可读面交叉校验) ----------

def test_consistency_pass_when_multiset_equal():
    c = _bc(equips=['镜中我', '镜中我'])
    assert_equips_consistency(c, ['镜中我', '镜中我'], source='t')   # 不 raise


def test_consistency_raises_on_mismatch():
    c = _bc(equips=['镜中我'])
    with pytest.raises(EquipsInconsistencyError) as ei:
        assert_equips_consistency(c, ['银河坠日'], source='sell_bench')
    assert 'sell_bench' in str(ei.value)
    assert ei.value.ledger == ['镜中我'] and ei.value.visible == ['银河坠日']


def test_consistency_visible_none_passes_bench_blind_spot():
    """bench 侧画面机制不可读(W21 #17)→ 无对拍面,tracking 单一源直接过。"""
    c = _bc(equips=['镜中我'])
    assert_equips_consistency(c, None, source='sell_bench')   # 不 raise


# ---------- 2. 账本多重集 + 守恒断言(构造不一致 → 断言报) ----------

def test_ledger_multiset_covers_assigned_and_pool():
    st = GameState()
    st.bench = [_bc(slot=1, equips=['A'])]
    st.deployed = [_bc(slot=1, row='front', char_id='希儿', equips=['B', 'B'])]
    st.equips = ['C']
    assert state_equips_multiset(st) == Counter({'A': 1, 'B': 2, 'C': 1})


def test_ledger_mismatch_lists_drift_and_assert_raises():
    before = Counter({'A': 1, 'B': 2})
    after = Counter({'A': 1, 'B': 1, 'X': 1})          # B 消失一件 / X 凭空出现
    diffs = ledger_mismatch(before, after)
    assert diffs == ['B:-1(凭空消失)', 'X:+1(凭空出现)']
    with pytest.raises(EquipsInconsistencyError) as ei:
        assert_ledger_conserved(before, after, source='unit')
    assert 'ledger_drift' in str(ei.value)
    # 守恒时静默通过且返回空清单
    assert assert_ledger_conserved(before, Counter(before), 'unit') == []


# ---------- 3. simulate 挂点:动作前后账本守恒 ----------

def _state_with_equips() -> GameState:
    st = GameState()
    st.gold = 50
    st.bench = [_bc(slot=1, equips=['A']),
                _bc(slot=2, char_id='卡芙卡', equips=[])]
    st.deployed = [_bc(slot=1, row='front', char_id='希儿', equips=['B'])]
    st.equips = ['C']
    return st


def test_buy_card_keeps_ledger_conserved():
    st = _state_with_equips()
    s2 = simulate(st, BuyCard(card=ShopCard(x=100, faction='仙舟',
                                            name='藿藿', cost=1)))
    assert state_equips_multiset(s2) == state_equips_multiset(st)
    assert not [e for e in s2.action_log if e['action'] == 'EquipsLedger']


def test_merge_star_up_inherits_equips_conserved():
    """3 合 1 合并:被吃副本的装备随载体继承(守恒建模,不凭空消失)。"""
    st = _state_with_equips()
    st.bench = [_bc(slot=1, char_id='桑博', equips=['A']),
                _bc(slot=2, char_id='桑博', equips=['D']),
                _bc(slot=3, char_id='桑博', equips=[])]
    st.deployed = []
    st.equips = []
    s2 = simulate(st, BuyCard(card=ShopCard(x=100, faction='贝洛伯格',
                                            name='桑博', cost=1)))
    # 4 张同名 1★ → 3 合 1 出一张 2★(装备随载体继承)+ 余一张 1★
    two_star = [c for c in s2.bench if c is not None
                and c.char_id == '桑博' and c.star == 2]
    one_star = [c for c in s2.bench if c is not None
                and c.char_id == '桑博' and c.star == 1]
    assert len(two_star) == 1 and len(one_star) == 1
    assert sorted(two_star[0].equips) == ['A', 'D']       # 装备随载体继承
    assert state_equips_multiset(s2) == Counter({'A': 1, 'D': 1})
    assert not [e for e in s2.action_log if e['action'] == 'EquipsLedger']


def test_sell_bench_recycles_equips_into_pool():
    """卖带装 bench 单位 → 装备回收进 owned 池(修复锁:修复前漏回收)。"""
    st = _state_with_equips()
    s2 = simulate(st, SellBench(bench_idx=0))           # 卖带 'A' 的桑博
    assert 'A' in s2.equips
    assert state_equips_multiset(s2) == state_equips_multiset(st)
    assert not [e for e in s2.action_log if e['action'] == 'EquipsLedger']


def test_sell_deployed_recycles_equips_conserved():
    st = _state_with_equips()
    s2 = simulate(st, SellDeployed(deployed_idx=0))     # 卖带 'B' 的希儿
    assert 'B' in s2.equips
    assert state_equips_multiset(s2) == state_equips_multiset(st)


def test_swap_deploy_equips_travel_with_chars():
    """换位装备随人走:上场者带 Y 上、下场者带 B 回 bench(对象迁移)。"""
    st = _state_with_equips()
    st.bench[1].equips = ['Y']
    s2 = simulate(st, SwapDeploy(deployed_idx=0, bench_idx=1))
    assert [c.equips for c in s2.deployed
            if c is not None and c.char_id == '卡芙卡'] == [['Y']]   # ADR-0392
    assert [c.equips for c in s2.bench if c is not None
            and c.char_id == '希儿'] == [['B']]
    assert state_equips_multiset(s2) == state_equips_multiset(st)


def test_comp_transaction_ledger_conserved():
    st = _state_with_equips()
    st.gold = 0
    tx = CompTransaction(
        deploy=[(1, 'front')],          # 卡芙卡(bench1)上前排
        undeploy=[0],                   # 希儿(带 B)下场
        sell=[(0, 'bench')],            # 卖带 A 的桑博 → A 回池
        reason='test',
    )
    s2 = simulate(st, tx)
    entry = [e for e in s2.action_log if e['action'] == 'CompTransaction']
    assert entry and entry[0]['result'] == 'applied'
    assert 'A' in s2.equips                                   # 卖 bench 带 A → 回池
    assert [c for c in s2.bench if c is not None
            and c.char_id == '希儿'][0].equips == ['B']   # 下场带装回 bench
    assert state_equips_multiset(s2) == state_equips_multiset(st)
    assert not [e for e in s2.action_log if e['action'] == 'EquipsLedger']


# ---------- 4. simulate 挂点 wiring:账本漂移 → EquipsLedger 记账(不静默) ----------

def test_simulate_hooks_equips_ledger_mismatch(monkeypatch):
    """monkeypatch 账本快照制造漂移 → simulate 记 EquipsLedger mismatch 条目。"""
    real = state_equips_multiset
    calls: list[Counter] = []

    def fake(st: GameState) -> Counter:
        c = real(st)
        calls.append(c)
        if len(calls) == 2:               # 第二次 = post 快照:制造 'A' 凭空消失
            return c - Counter({'A': 1})
        return c

    monkeypatch.setattr(cw_bench_equips, 'state_equips_multiset', fake)
    st = _state_with_equips()
    s2 = simulate(st, SellBench(bench_idx=0))
    mism = [e for e in s2.action_log if e['action'] == 'EquipsLedger']
    assert len(mism) == 1
    assert mism[0]['result'] == 'mismatch'
    assert 'A:-1' in mism[0]['reason'] and 'SellBench' in mism[0]['reason']
    # 非装备动作(PickEvent/RefreshShop 等)不跑对账(fake 只被调用 2 次)
    simulate(st, SellBench(bench_idx=0))
    assert len(calls) == 4
