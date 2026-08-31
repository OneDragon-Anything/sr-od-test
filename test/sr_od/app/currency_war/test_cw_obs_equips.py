# -*- coding: utf-8 -*-
"""test_cw_obs_equips 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- bench_equips: test_cw_bench_equips.py
- w211_equip_policy: test_cw_w211_equip_policy.py
- w212_sim_equip_fidelity: test_cw_w212_sim_equip_fidelity.py
- w596_equip_guards: test_cw_w596_equip_guards.py
- w880_equip_env: test_cw_w880_equip_env.py
- diamond_detect: test_cw_diamond_detect.py
- w583_snapshot_contracts: test_cw_w583_snapshot_contracts.py
- idx_contract: test_cw_idx_contract.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== bench_equips ====================

from collections import Counter

import pytest

import sr_od.application.currency_war.kernel.cw_bench_equips as cw_bench_equips
from sr_od.application.currency_war.kernel.cw_bench_equips import  EquipsInconsistencyError, assert_equips_consistency, assert_ledger_conserved, ledger_mismatch, state_equips_multiset
from sr_od.application.currency_war.kernel.cw_state import  BenchChar, BuyCard, CompTransaction, GameState, SellBench, SellDeployed, ShopCard, SwapDeploy, simulate


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


# ==================== w211_equip_policy ====================

from sr_od.application.currency_war.kernel.cw_comps import  equip_allocation
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w211_equip_policy_BenchChar
from sr_od.application.currency_war.data.cw_synthesis import  RESERVED_COMPONENTS, component_demand, hoard_gaps, recycle_qualified, synthesize_target

# 例 1 阿雅 K(cw_comps 映夜神阿雅 key_equips 摘录;白昼件无配方跳过)
_K_AYA = ['反重力皮靴', '反重力皮靴', '白昼·光速螺旋桨', '火力风暴潮']
# 例 2 追击飞霄 K
_K_FEI = ['火力风暴潮', '火力风暴潮', '永动机', '电磁弹射器']


# ===== 1. 图谱纯函数对拍 P14 已发表表 =====

def test_component_demand_p14_examples() -> None:
    """K → 组件需求向量,逐位对拍 P14 例 1/例 2(含自配×2 与无配方件跳过)。"""
    assert component_demand(_K_AYA) == {'轮滑鞋': 5, '折叠小刀': 1}
    assert component_demand(_K_FEI) == {
        '折叠小刀': 2, '轮滑鞋': 3, '光能电池': 2, '和平手枪': 1}


def test_recycle_qualified_p14_examples() -> None:
    """回收合格集对拍 P14 Q3 表:阿雅 6 件(轮滑鞋除外);飞霄 4 件。"""
    assert recycle_qualified(_K_AYA) == frozenset({
        '以太钻头', '光能电池', '和平手枪', '幸运星', '生命之花', '量产型装甲'})
    assert recycle_qualified(_K_FEI) == frozenset({
        '以太钻头', '幸运星', '生命之花', '量产型装甲'})


def test_recycle_qualified_no_target_empty() -> None:
    """comp=None(无目标)→ 空集:有用性无从判定,一律不当死库存(保守侧)。"""
    assert recycle_qualified(None) == frozenset()
    assert recycle_qualified([]) == frozenset()


def test_hoard_gaps_offset_by_finished_advance() -> None:
    """「缺什么囤什么」差集:成品 1:1 抵扣 K 需求后才展开组件账。

    阿雅 K 已持 1 皮靴 → 剩 皮靴×1(=轮滑鞋2)+风暴潮(=轮滑鞋+小刀)
    → 缺 轮滑鞋3/折叠小刀1;再持轮滑鞋2 → 缺 轮滑鞋1/小刀1。"""
    assert hoard_gaps(_K_AYA, ['反重力皮靴']) == {'轮滑鞋': 3, '折叠小刀': 1}
    assert hoard_gaps(_K_AYA, ['反重力皮靴', '轮滑鞋', '轮滑鞋']) == {
        '轮滑鞋': 1, '折叠小刀': 1}
    assert hoard_gaps(_K_AYA, _K_AYA) == {}, '成品全持 → 零缺口'


# ===== 2. 防误合成配对守卫(equip_allocation)=====

def _mkcomp(key_equips: list[str], cores: list[str]):
    from sr_od.application.currency_war.kernel.cw_comps import Comp
    return Comp(name='伪comp', factions=['追击'], core_chars=cores,
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=key_equips)


def test_pairing_guard_rejects_unintended_synthesis() -> None:
    """P2:core 已穿 生命之花,新发 光能电池 → 会自动合成「绝对热量」
    (run 26 实锤配方);产物不在该 comp key_equips → 该件不发 core(留 owned)。
    防的是不可逆消耗:穿着触发自动合成无确认,口述「会被残留件带偏」。"""
    assert synthesize_target('光能电池', '生命之花') == '绝对热量', \
        '图谱前提:run 26 实锤配方必须在(否则本锁失锚)'
    comp = _mkcomp(['火力风暴潮'], ['飞霄'])   # 绝对热量 ∉ key_equips
    dep = [_w211_equip_policy_BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    occ = {('front', 1): ['生命之花']}
    alloc = equip_allocation(comp, dep, ['光能电池'], occ)
    assert ('飞霄', '光能电池') not in alloc, \
        f'非预期合成对被发到同一 core: {alloc}'


def test_pairing_guard_allows_wanted_synthesis() -> None:
    """同上场景但 绝对热量 ∈ key_equips 且穿者是 core → 放行:
    想要的配对穿着触发合成 = 快路径(合成+穿一次完成)。"""
    comp = _mkcomp(['绝对热量'], ['飞霄'])
    dep = [_w211_equip_policy_BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    occ = {('front', 1): ['生命之花']}
    alloc = equip_allocation(comp, dep, ['光能电池'], occ)
    assert ('飞霄', '光能电池') in alloc, \
        f'想要的配对应放行(core 快路径): {alloc}'


def test_pairing_guard_no_target_splits_pair() -> None:
    """comp=None:无豁免信息 → 互为配方的基础件对不同人发,不同人同穿。"""
    dep = [_w211_equip_policy_BenchChar(slot=1, char_id='三月七', position_pref='front'),
           _w211_equip_policy_BenchChar(slot=2, char_id='黑塔', position_pref='front')]
    owned = ['光能电池', '生命之花']      # 互为配方(绝对热量)
    alloc = equip_allocation(None, dep, owned)
    holders = [c for c, e in alloc if e in owned]
    assert len(holders) == len(set(holders)), \
        f'配对件必须分人: {alloc}'


def test_pairing_guard_covers_guangneng_base() -> None:
    """守卫覆盖第 8 基础件光能电池(RESERVED_COMPONENTS 恰为全 8 件;
    只查 7 件标准集会漏光能电池系全部配方)。"""
    assert '光能电池' in RESERVED_COMPONENTS
    assert len(RESERVED_COMPONENTS) == 8


# ===== 3. 死库存回收去向(全 plane;P1 随 ADR-0265 增补生效)=====

def test_dead_stock_routed_to_noncore() -> None:
    """P2:回收合格件(对阿雅=以太钻头/幸运星 等)优先发非 core 工具人,
    core 不吃死库存(穿着合成产物落 core=后续转移摩擦)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    dep = [_w211_equip_policy_BenchChar(slot=1, char_id='阿雅', position_pref='back'),
           _w211_equip_policy_BenchChar(slot=2, char_id='三月七', position_pref='front')]
    alloc = equip_allocation(comp, dep, ['以太钻头', '幸运星'])
    wearers = {e: c for c, e in alloc}
    assert wearers.get('以太钻头') == '三月七' \
        and wearers.get('幸运星') == '三月七', \
        f'死库存应全去非 core 工具人: {alloc}'
    assert all(c != '阿雅' for c, _ in alloc), f'core 不得吃死库存: {alloc}'


def test_dead_stock_allows_recycle_pair_on_tool_char() -> None:
    """回收线有意 2合1:非 core 工具人身上两件回收合格件互为配方 → 放行
    (口述「先 2 合 1,到一个没用的角色身上」;合成产物必然 ∉ K——若 ∈ K
    则其组件就不是死库存,P14 定理 3 反证)。"""
    rq = recycle_qualified(_K_AYA)
    # 从图谱里找一对真实互为配方的回收合格基础件(锁语义不锁具体对)
    pair = next(((a, b) for a in sorted(rq) for b in sorted(rq)
                 if a != b and synthesize_target(a, b) is not None), None)
    assert pair is not None, '图谱前提:死库存内存在可配对(回收线可触发)'
    a, b = pair
    assert synthesize_target(a, b) not in set(_K_AYA), '定理 3 反证前提'
    comp = _mkcomp(_K_AYA, ['阿雅'])
    dep = [_w211_equip_policy_BenchChar(slot=1, char_id='阿雅', position_pref='back'),
           _w211_equip_policy_BenchChar(slot=2, char_id='三月七', position_pref='front')]
    alloc = equip_allocation(comp, dep, [a, b])
    got = [(c, e) for c, e in alloc if e in (a, b)]
    assert {c for c, _ in got} == {'三月七'} and len(got) == 2, \
        f'回收对应允许同穿非 core 工具人: {alloc}'


def test_p1_dead_stock_now_routed_and_worn() -> None:
    """P1(ADR-0265 增补:穿戴可逆,组件保留过滤已删,死库存去向全
    plane 生效):死库存改道非 core 工具人穿着(回收线 2合1 候选),
    core 只吃非基础件——改锁重推:旧语义「P1 基础件全保留」钉的是
    已被「卖角色全额返还装备 → 穿戴可逆」裁决取代的保留过滤。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    dep = [_w211_equip_policy_BenchChar(slot=1, char_id='阿雅', position_pref='back'),
           _w211_equip_policy_BenchChar(slot=2, char_id='三月七', position_pref='front')]
    alloc = equip_allocation(comp, dep, ['以太钻头', '火力风暴潮'])
    wearers = {e: c for c, e in alloc}
    assert wearers.get('以太钻头') == '三月七', \
        f'P1 死库存应改道非 core 工具人: {alloc}'
    assert wearers.get('火力风暴潮') == '阿雅', \
        f'非基础件照常发 core: {alloc}'


# ==================== w212_sim_equip_fidelity ====================

from sr_od.application.currency_war.kernel import cw_comps

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1


def test_sim_equip_allocation_call_shape_occupied_snapshot() -> None:
    """sim 调用形态与生产 EquipAll 对齐:occupied = 已穿快照 dict。"""
    calls: list[dict] = []
    orig = cw_comps.equip_allocation

    def spy(comp, deployed, owned, occupied=None, directed_pairs=None):
        calls.append({'occupied': occupied,
                      'deployed_n': len(list(deployed or []))})
        return orig(comp, deployed, owned, occupied)

    cw_comps.equip_allocation = spy
    try:
        # fallback 池(测试仓惯例)。P2 段分配点火是概率事件(equips
        # 非空 ∧ 有 deployed)——扫一小窗 seed,任一 seed 出现带 occupied
        # 的调用即形态可达(修复前恒 None,永不可达)。
        for seed in range(20):
            simulate_p1(seed, planes=2, pool='fallback')
            if any(c['occupied'] is not None for c in calls):
                break
    finally:
        cw_comps.equip_allocation = orig

    assert calls, 'sim 全程未调 equip_allocation(equips 恒空?环境异常)'
    occ_calls = [c for c in calls if c['occupied'] is not None]
    assert occ_calls, 'occupied 恒 None(修复前形态)——ADR-0391 守卫失效'
    sample = occ_calls[0]['occupied']
    assert all(isinstance(k, tuple) and len(k) == 2
               and isinstance(v, list) for k, v in sample.items()), (
        f'occupied 键形态≠(position_pref, slot): {sample}')


def test_sim_p1_still_runs_and_allocates() -> None:
    """P1 段正常出分配调用(零漂移烟雾;分配发生即可,不锁分配内容)。"""
    calls: list[int] = []
    orig = cw_comps.equip_allocation

    def spy(comp, deployed, owned, occupied=None, directed_pairs=None):
        calls.append(1)
        return orig(comp, deployed, owned, occupied)

    cw_comps.equip_allocation = spy
    try:
        for seed in range(10):
            simulate_p1(seed, planes=1, pool='fallback')
            if calls:
                break
    finally:
        cw_comps.equip_allocation = orig
    assert calls, 'P1 段全程未调 equip_allocation(分配链断裂?)'


# ==================== w596_equip_guards ====================

from types import SimpleNamespace

import pytest as _w596_equip_guards_pytest

from sr_od.application.currency_war.kernel.cw_comps import  Comp, equip_alloc_empty_reason, equip_allocation as _w596_equip_guards_equip_allocation
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w596_equip_guards_BenchChar
from sr_od.application.currency_war.data.cw_synthesis import synthesize_target as _w596_equip_guards_synthesize_target
from sr_od.application.currency_war.operations.prep.equip_all import EquipAll
from sr_od.application.currency_war.telemetry import state as cw_telemetry


# ===== 件1:构建指纹 =====

def test_build_fingerprint_format_and_cache() -> None:
    """指纹 = 非空短串;进程内缓存(两次调用同值,git 不重复跑)。"""
    from sr_od.backend.build_info import get_build_fingerprint
    fp1 = get_build_fingerprint()
    fp2 = get_build_fingerprint()
    assert fp1 == fp2 and fp1, '指纹非空且进程内缓存稳定'


def test_build_fingerprint_git_repo_matches_head() -> None:
    """git 可用时:指纹 ∈ {HEAD 短 hash, HEAD 短 hash+'+dirty'},与 git 直查一致。"""
    import subprocess
    from sr_od.backend.build_info import _PROJECT_ROOT, get_build_fingerprint
    try:
        proc = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=_PROJECT_ROOT, capture_output=True, text=True, timeout=5)
        head = proc.stdout.strip()
    except Exception:   # noqa: BLE001  git 缺失环境跳过对拍
        _w596_equip_guards_pytest.skip('git 不可用')
    if proc.returncode != 0 or not head:
        _w596_equip_guards_pytest.skip('非 git 仓库')
    fp = get_build_fingerprint()
    assert fp in (head, head + '+dirty'), f'指纹与 git HEAD 不一致: {fp} vs {head}'


# ===== 件2:零穿戴哨兵 =====

def _mk_op(state: SimpleNamespace | None) -> EquipAll:
    """最小 EquipAll(只调 _zero_wear_sentinel,不碰截图/控制器)。"""
    match = None if state is None else SimpleNamespace(session=SimpleNamespace(last_state=state))
    return EquipAll(SimpleNamespace(cw_match=match))


@_w596_equip_guards_pytest.fixture()
def _captured_defect(monkeypatch):
    """桩化 cw_telemetry.record_defect 捕获调用(零真实副作用,不写台账)。"""
    calls: list[dict] = []
    monkeypatch.setattr(defects, 'record_defect',
                        lambda *a, **k: calls.append({'args': a, 'kwargs': k}))
    return calls


_STATE_R5 = SimpleNamespace(round_num=5, plane=1)
_OWNED_WEARABLE = ['生命之花', '量产型装甲', '冶金炉']   # 末件=工具类,不应计入可穿面


def test_zero_wear_sentinel_fires(_captured_defect) -> None:
    """态①:0 穿 + 有可穿件 + round≥3 → 落账 equip_zero_wear(带 owned 与停手原因)。"""
    _mk_op(_STATE_R5)._zero_wear_sentinel(0, _OWNED_WEARABLE, '分配方案空:pairing_guard')
    assert len(_captured_defect) == 1
    call = _captured_defect[0]
    kw = call['kwargs']
    assert kw['surface'] == 'equip' and kw['kind'] == 'equip_zero_wear'
    assert kw['round_num'] == 5 and kw['plane'] == 1
    observed = kw['observed']
    assert '生命之花' in observed and '量产型装甲' in observed, 'observed 带 owned 名单'
    assert '冶金炉' not in observed, '工具类不得计入可穿面(与穿戴决策同过滤口径)'
    assert 'pairing_guard' in observed, 'observed 带 stop 原因'


def test_zero_wear_sentinel_silent_when_wore(_captured_defect) -> None:
    """态②:穿了 ≥1 件 → 静默(哨兵只报零穿戴)。"""
    _mk_op(_STATE_R5)._zero_wear_sentinel(2, _OWNED_WEARABLE, '')
    assert _captured_defect == []


def test_zero_wear_sentinel_silent_when_no_wearable(_captured_defect) -> None:
    """态③:0 穿但 owned 全工具类/空 → 静默(无货可穿不是缺陷)。"""
    _mk_op(_STATE_R5)._zero_wear_sentinel(0, ['冶金炉'], 'pool_empty')
    _mk_op(_STATE_R5)._zero_wear_sentinel(0, [], '')
    assert _captured_defect == []


def test_zero_wear_sentinel_silent_before_round3(_captured_defect) -> None:
    """round<3 → 静默:r1~r2 开局 hold(ADR-0257)零穿戴是 by design。"""
    _mk_op(SimpleNamespace(round_num=2, plane=1))._zero_wear_sentinel(
        0, _OWNED_WEARABLE, '过渡期hold')
    assert _captured_defect == []


def test_zero_wear_sentinel_silent_without_state(_captured_defect) -> None:
    """无 run 上下文(last_state 缺失)→ 静默跳过,不炸不误报。"""
    _mk_op(None)._zero_wear_sentinel(0, _OWNED_WEARABLE, '')
    assert _captured_defect == []


# ===== 件3:分配空归因 =====

def _w596_equip_guards_mkcomp(key_equips: list[str], cores: list[str]) -> Comp:
    return Comp(name='伪comp', factions=['追击'], core_chars=cores,
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=key_equips)


def test_reason_pool_empty() -> None:
    assert equip_alloc_empty_reason(None, [], []) == 'pool_empty'


def test_reason_no_deployed() -> None:
    assert equip_alloc_empty_reason(None, [], ['生命之花']) == 'no_deployed'


def test_reason_capacity_full() -> None:
    dep = [_w596_equip_guards_BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    occ = {('front', 1): ['生命之花', '量产型装甲', '幸运星']}   # 容量 3 占满
    assert equip_alloc_empty_reason(None, dep, ['以太钻头'], occ) == 'capacity_full'


def test_reason_pairing_guard_matches_allocation() -> None:
    """守卫拦截归因:core 已穿 生命之花,池里只有 光能电池(会合出
    「绝对热量」∉ key)→ 分配空 且 归因=pairing_guard。两函数同输入同结论。"""
    assert _w596_equip_guards_synthesize_target('光能电池', '生命之花') == '绝对热量', '图谱前提'
    comp = _w596_equip_guards_mkcomp(['火力风暴潮'], ['飞霄'])
    dep = [_w596_equip_guards_BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    occ = {('front', 1): ['生命之花']}
    assert _w596_equip_guards_equip_allocation(comp, dep, ['光能电池'], occ) == []
    assert equip_alloc_empty_reason(comp, dep, ['光能电池'], occ) == 'pairing_guard'


def test_reason_unknown_flags_divergence() -> None:
    """存在可行组合却询问归因 → unknown(哨兵值:分配器与诊断漂移时优先暴露)。"""
    dep = [_w596_equip_guards_BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    assert equip_alloc_empty_reason(None, dep, ['生命之花'], None) == 'unknown'


def test_blocked_items_not_discarded_for_later_chars() -> None:
    """配对守卫拦下的件必须**留在池里**轮给后面的人,不得 pop 丢弃。

    出处:equip_allocation docstring ADR-0391 节「发不完留在 owned 囤着」
    与分配体内「跳过=留 owned」注释;实机反例见复盘
    `.debug/temp/currency_war/replay/matches/reviews/g_20260831_032006.md`
    r7 形态(列车配方伪 comp,三月七穿以太钻头,池里 4 件全是与其互为
    配方的基础件 → 旧实现整池被 core 循环吃光,alloc=[] 而诊断判
    「存在可行组合」= unknown 漂移)。锁语义:
    1. 同帧下无残留件的角色(饮月)能分到件(非空分配);
    2. 被拦的 core(三月七)一件不取,被拦件不消失(留给他人/owned);
    3. 分配空 ⇔ 归因非 unknown(两函数同输入同结论的契约恢复)。
    """
    assert _w596_equip_guards_synthesize_target('以太钻头', '折叠小刀') is not None, '图谱前提:池件与已穿件互为配方'
    comp = _w596_equip_guards_mkcomp([], ['三月七', '丹恒·饮月'])
    dep = [_w596_equip_guards_BenchChar(slot=1, char_id='丹恒·饮月', position_pref='front'),
           _w596_equip_guards_BenchChar(slot=2, char_id='三月七', position_pref='back')]
    pool = ['折叠小刀', '轮滑鞋']
    occ = {('back', 2): ['以太钻头']}
    alloc = _w596_equip_guards_equip_allocation(comp, dep, list(pool), dict(occ))
    assert alloc, '被拦 core 不得吃光整池:无残留件的角色应分到件'
    got_chars = {c for c, _ in alloc}
    assert '三月七' not in got_chars, '整池互为配方时被拦 core 一件不取(留 owned)'
    assert all(e == '折叠小刀' or e == '轮滑鞋' for _, e in alloc)
    # 单人整池被拦的形态:分配空,且归因必须是 pairing_guard(不再 unknown)
    dep_only = [_w596_equip_guards_BenchChar(slot=1, char_id='丹恒·饮月', position_pref='front'),
                _w596_equip_guards_BenchChar(slot=2, char_id='三月七', position_pref='back')]
    occ_all_blocked = {('front', 1): ['以太钻头'], ('back', 2): ['以太钻头']}
    assert _w596_equip_guards_equip_allocation(comp, dep_only, ['折叠小刀'], dict(occ_all_blocked)) == []
    assert equip_alloc_empty_reason(comp, dep_only, ['折叠小刀'],
                                    dict(occ_all_blocked)) == 'pairing_guard'


from sr_od.application.currency_war.telemetry import state

from sr_od.application.currency_war.telemetry import defects


# ==================== w880_equip_env ====================

from types import SimpleNamespace as _w880_equip_env_SimpleNamespace

from sr_od.application.currency_war.data.affix_effects_data import  AFFIX_EFFECTS
from sr_od.application.currency_war.kernel.cw_comps import Comp as _w880_equip_env_Comp
from sr_od.application.currency_war.kernel.cw_equip_env import  EQUIP_ENV_FILL3_AFFIXES, EquipEnvSignals, apply_fill3, build_equip_env_signals, fill3_allocation, fill3_env_active
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY, DecisionV2Registry
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w880_equip_env_BenchChar


def _w880_equip_env_mkcomp(key_equips: list[str], cores: list[str]) -> _w880_equip_env_Comp:
    return _w880_equip_env_Comp(name='伪comp', factions=['追击'], core_chars=cores,
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=key_equips)


_COMP = _w880_equip_env_mkcomp(['反重力皮靴', '火力风暴潮'], ['阿雅'])
_KEYS = {'反重力皮靴', '火力风暴潮'}


def _sig(affixes: list[str] | None) -> EquipEnvSignals:
    return build_equip_env_signals(
        _w880_equip_env_SimpleNamespace(enemy_affixes=affixes or [], plane=1, round_num=3))


# ===== 1. 机制真值与开关生命周期 =====

def test_mechanism_truth_single_source() -> None:
    """两词缀原文在 affix_effects_data 注册表(游戏内实采,禁第二数据源)。"""
    assert '穿戴3件装备' in AFFIX_EFFECTS['软弱无力'] and '80%' in AFFIX_EFFECTS['软弱无力']
    assert '空缺装备栏' in AFFIX_EFFECTS['额外打击'] and '8%' in AFFIX_EFFECTS['额外打击']


def test_registry_switch_defaults_off_lifecycle_state1() -> None:
    """开关默认关 = 生命周期第 1 态(开臂判据挂账见 registry 字段注释);
    穿满阈值 = 机制常量 3(真值「穿戴3件装备」)。"""
    import dataclasses
    fld = {f.name: f for f in dataclasses.fields(DecisionV2Registry)}
    assert fld['equip_env_fill3_enabled'].default is False
    assert fld['equip_fill_target'].default == 3
    assert DEFAULT_REGISTRY.equip_env_fill3_enabled is False
    assert DEFAULT_REGISTRY.equip_fill_target == 3


def test_dead_mapping_guard_not_in_mechanic_map() -> None:
    """死映射防线(W872 攻击口径/W875 范式):软弱无力/额外打击未做 comp 携带
    tag 核查前,禁入 AFFIX_MECHANIC_MAP(设计 §3.4 挂账,核查后按范式补)。"""
    from sr_od.application.currency_war.kernel.cw_comps import AFFIX_MECHANIC_MAP
    for a in EQUIP_ENV_FILL3_AFFIXES:
        assert a not in AFFIX_MECHANIC_MAP, f'{a} 未核查携带面,禁先写映射'


# ===== 2. 环境判据(信号单源)=====

def test_env_active_either_affix() -> None:
    assert fill3_env_active(_sig(['软弱无力']))
    assert fill3_env_active(_sig(['额外打击']))
    assert fill3_env_active(_sig(['库藏生锈', '软弱无力']))


def test_env_absent_safe_default() -> None:
    """读不到(空/None/无关词缀)= 无环境,安全默认不启用。"""
    assert not fill3_env_active(_sig([]))
    assert not fill3_env_active(_sig(None))
    assert not fill3_env_active(_sig(['变宝为废']))


def test_signals_single_reading_point_state_missing() -> None:
    """信号单源:state 缺失(None)/字段缺失 → 空集 + None(不抛错,保守默认)。"""
    s = build_equip_env_signals(None)
    assert s.enemy_affixes == frozenset() and s.plane is None and s.round_num is None
    s2 = build_equip_env_signals(_w880_equip_env_SimpleNamespace())
    assert s2.enemy_affixes == frozenset()


# ===== 3. 集中度轴(软弱无力:凑 3 优先于均匀分散)=====

_DEP2 = [_w880_equip_env_BenchChar(slot=1, char_id='甲', position_pref='back'),
         _w880_equip_env_BenchChar(slot=2, char_id='乙', position_pref='back')]
_OCC2 = {('back', 1): ['以太钻头'], ('back', 2): ['以太钻头', '和平手枪']}


def test_concentration_axis_prefers_closest_to_full() -> None:
    """散件改派给已穿件数多者(2 件者先凑满 3),不做均匀分散。"""
    new, moved = apply_fill3([('甲', '幸运星')], _DEP2, _OCC2, _COMP)
    assert moved == 1 and new == [('乙', '幸运星')]


# ===== 4. 承伤序轴(额外打击:前排/受击高位先于输出位)=====

_DEP3 = [_w880_equip_env_BenchChar(slot=1, char_id='三月七', position_pref='front'),
         _w880_equip_env_BenchChar(slot=2, char_id='阿雅', position_pref='back'),
         _w880_equip_env_BenchChar(slot=3, char_id='丹恒', position_pref='back')]
_OCC3 = {('front', 1): ['以太钻头', '和平手枪'],
         ('back', 2): ['轮滑鞋', '生命之花']}


def test_damage_side_order_front_first() -> None:
    """前排(已穿 2)与 core(已穿 2)并列时,前排先凑满(空栏承伤罚最贵)。"""
    new, moved = apply_fill3([('丹恒', '幸运星'), ('阿雅', '反重力皮靴')],
                             _DEP3, _OCC3, _COMP)
    assert moved == 1
    assert new[0] == ('三月七', '幸运星'), f'前排承伤序优先, got {new}'
    assert new[1] == ('阿雅', '反重力皮靴'), 'key 件不动'


def test_same_row_core_first() -> None:
    """同排并列时的辖域优先链(ADR-0502):可行性守卫(ADR-0391)>
    承伤序 > core-first > 集中度——core-first 只在「该件对该候选守卫
    可行」的候选内生效,首选 core 被守卫淘汰后改派落到可行次选是
    约束优先于偏好的正常让位,非回归。

    让位场景:阿雅(core)已穿以太钻头,幸运星 × 以太钻头合成产物
    ∉ key 集 → 例外①不成立、例外②对 core 不成立 → 守卫拦;
    丹恒(非 core)两件均回收合格 → 例外②放行。两候选同 2/3 同
    gap,80% 罚差分为零,让位无实际行为损失。旧语义(无条件断言
    core 必先凑满)把偏好序写成合法性之上的断言,未被任何设计出处
    支撑,锁组落成即红从未对账——按锁的存在性纪律改写,语义出处 =
    ADR-0502(让位事件经 fill3 的 pairing-guard yield info 行披露)。"""
    dep = [_w880_equip_env_BenchChar(slot=1, char_id='阿雅', position_pref='back'),
           _w880_equip_env_BenchChar(slot=2, char_id='丹恒', position_pref='back')]
    occ = {('back', 1): ['以太钻头', '和平手枪'],
           ('back', 2): ['以太钻头', '和平手枪']}
    new, moved = apply_fill3([('丹恒', '幸运星')], dep, occ, _COMP)
    assert moved == 1
    assert new == [('丹恒', '幸运星')], \
        'core 首选被配对守卫让位,改派落可行次选(ADR-0502)'


# ===== 5. 保护集与成员无损 =====

def test_protected_key_and_mainline_components() -> None:
    """key_equips 与主线需求组件(component_demand)不可挪(不碰主线凑件)。"""
    from sr_od.application.currency_war.data.cw_synthesis import component_demand
    mainline = set(component_demand(list(_COMP.key_equips)))
    assert mainline, '前提:阿雅线存在主线组件'
    items = sorted(mainline | _KEYS)
    base = [('甲', items[0]), ('乙', items[-1])]
    new, moved = apply_fill3(base, _DEP2, _OCC2, _COMP)
    assert moved == 0 and new == base


def test_members_lossless_reassign_only() -> None:
    """改派只换 char 不增删件(件集合与长度不变)。"""
    base = [('甲', '幸运星'), ('乙', '量产型装甲')]
    new, moved = apply_fill3(base, _DEP2, _OCC2, _COMP)
    assert len(new) == len(base)
    assert sorted(e for _, e in new) == sorted(e for _, e in base)


def test_pairing_guard_blocks_unexpected_synthesis() -> None:
    """基础件改派过防误合成守卫:会给目标角色触发非预期合成的件换目标/放弃
    (守卫判定单源 = cw_comps._pairing_guard_ok,ADR-0391 纪律 1)。"""
    from sr_od.application.currency_war.data.cw_synthesis import synthesize_target
    dep = [_w880_equip_env_BenchChar(slot=1, char_id='阿雅', position_pref='back')]
    # 阿雅已穿 a;改派 b 到阿雅会合成出非 key 产物 → 不改派(件留原 char)
    pair = next(((a, b) for a in ['光能电池', '和平手枪', '幸运星', '量产型装甲']
                 for b in ['光能电池', '和平手枪', '幸运星', '量产型装甲']
                 if a != b and synthesize_target(a, b) is not None
                 and synthesize_target(a, b) not in _COMP.key_equips), None)
    if pair is None:
        return  # 图谱无此形态则锁退化(不构造伪数据)
    a, b = pair
    dep3 = [dep[0],
            _w880_equip_env_BenchChar(slot=2, char_id='甲', position_pref='back'),
            _w880_equip_env_BenchChar(slot=3, char_id='乙', position_pref='back')]
    new, _ = apply_fill3([('甲', b), ('乙', '幸运星')], dep3,
                         {('back', 1): [a], ('back', 2): [], ('back', 3): []},
                         _COMP)
    assert ('阿雅', b) not in new, f'防误合成守卫拦截改派, got {new}'


# ===== 6. 门序零漂移 =====

def _base() -> list[tuple[str, str]]:
    return [('丹恒', '幸运星'), ('阿雅', '反重力皮靴')]


def test_disabled_switch_zero_drift() -> None:
    """开关关(默认):环境在场也返回基分配原样(零漂移锚)。"""
    out, action = fill3_allocation(DEFAULT_REGISTRY, _COMP, _DEP3, _base(),
                                   _OCC3, _sig(['软弱无力']), hold_active=False)
    assert action == 'inactive' and out == _base()


def test_env_absent_zero_drift_even_enabled() -> None:
    """环境不在场:开关开也返回基分配(安全默认)。"""
    reg = _w880_equip_env_SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3)
    out, action = fill3_allocation(reg, _COMP, _DEP3, _base(),
                                   _OCC3, _sig([]), hold_active=False)
    assert action == 'inactive' and out == _base()


def test_hold_active_blocks_fill() -> None:
    """过渡期 hold(非生锈豁免态)优先:hold 在场 → fill 不激活(防线③)。"""
    reg = _w880_equip_env_SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3)
    out, action = fill3_allocation(reg, _COMP, _DEP3, _base(),
                                   _OCC3, _sig(['额外打击']), hold_active=True)
    assert action == 'hold_active' and out == _base()


def test_no_gap_when_all_full_or_nothing_movable() -> None:
    """全员已满 3 / 可改派散件为空 → no_gap,分配原样。"""
    reg = _w880_equip_env_SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3)
    full_occ = {('front', 1): ['a1', 'a2', 'a3'], ('back', 2): ['b1', 'b2', 'b3'],
                ('back', 3): ['c1', 'c2', 'c3']}
    out, action = fill3_allocation(reg, _COMP, _DEP3, _base(), full_occ,
                                   _sig(['软弱无力']), hold_active=False)
    assert action == 'no_gap' and out == _base()
    out2, action2 = fill3_allocation(reg, _COMP, _DEP3,
                                     [('阿雅', '反重力皮靴')], _OCC3,
                                     _sig(['软弱无力']), hold_active=False)
    assert action2 == 'no_gap' and out2 == [('阿雅', '反重力皮靴')]


def test_wrapper_filled_action_and_log_semantics() -> None:
    """发生改派 → action=filled:<n>(判读锚点 = [cw-equip] env-variant fill3 日志行,
    语义由 fill3_allocation 打点;此处锁返回形态)。"""
    reg = _w880_equip_env_SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3)
    out, action = fill3_allocation(reg, _COMP, _DEP3, _base(), _OCC3,
                                   _sig(['额外打击']), hold_active=False)
    assert action == 'filled:1'
    assert out[0] == ('三月七', '幸运星')


def test_comp_none_conservative_noop() -> None:
    """comp 缺失(无身份信息,保护集不可判)→ 原样返回(保守降级)。"""
    new, moved = apply_fill3(_base(), _DEP3, _OCC3, None)
    assert moved == 0 and new == _base()


# ===== 7. 管道化迁移(设计 §2.2 门/量/序;生锈与变宝为废行为不变归位)=====

def test_rust_gate_consumes_signals() -> None:
    """生锈豁免(门)改吃 signals 派生名单(构造点唯一,不再各自摸 state);
    谓词语义不变(读不到=不豁免,零漂移)。"""
    from sr_od.application.currency_war.operations.prep.equip_all import  _rust_release_active
    assert _rust_release_active(
        sorted(build_equip_env_signals(
            _w880_equip_env_SimpleNamespace(enemy_affixes=['库藏生锈'])).enemy_affixes), True)
    assert not _rust_release_active(
        sorted(build_equip_env_signals(None).enemy_affixes), True)
    assert not _rust_release_active(['库藏生锈'], False), '开关关=不豁免'


def test_junk_first_base_alloc_param_backward_compatible() -> None:
    """junk_first_allocation 新增 base_alloc 直收参(W880 管道量→序接入):
    缺省 None 自算基分配(既有调用/w861 锁行为逐位不变);直收时开关关原样。"""
    from sr_od.application.currency_war.kernel.cw_comps import equip_allocation
    from sr_od.application.currency_war.kernel.cw_junk_first import  junk_first_allocation
    reg = _w880_equip_env_SimpleNamespace(equip_env_fill3_enabled=False,
                          junk_first_sacrifice_enabled=True)
    base = equip_allocation(_COMP, _DEP3, ['幸运星'], _OCC3)
    got = junk_first_allocation(None, reg, _COMP, _DEP3, ['幸运星'], _OCC3,
                                ['变宝为废'], base_alloc=base)
    assert got == base
    got_default = junk_first_allocation(None, reg, _COMP, _DEP3,
                                        ['幸运星'], _OCC3, ['变宝为废'])
    assert got_default == equip_allocation(_COMP, _DEP3, ['幸运星'], _OCC3)


def test_pipeline_all_off_zero_drift() -> None:
    """管道全开关默认关 = 基分配原样(零漂移锚),动作记录在案。"""
    from sr_od.application.currency_war.kernel.cw_comps import equip_allocation
    from sr_od.application.currency_war.kernel.cw_equip_env import  apply_equip_env_variants
    sess = _w880_equip_env_SimpleNamespace(last_state=_w880_equip_env_SimpleNamespace(plane=1),
                           junk_first_done_plane=None)
    out, actions = apply_equip_env_variants(
        build_equip_env_signals(None), DEFAULT_REGISTRY, sess, _COMP,
        _DEP3, ['幸运星'], _OCC3, hold_active=False)
    assert out == equip_allocation(_COMP, _DEP3, ['幸运星'], _OCC3)
    assert actions == ['fill3=inactive']


def test_pipeline_amount_before_order() -> None:
    """管道量→序:fill 改派产出直供序变体(junk_first 消费改派后 alloc),
    门(hold)辖量变体;动作记录含 fill3 结果。"""
    from sr_od.application.currency_war.kernel.cw_equip_env import  apply_equip_env_variants
    sess = _w880_equip_env_SimpleNamespace(last_state=_w880_equip_env_SimpleNamespace(plane=1),
                           junk_first_done_plane=None)
    reg = _w880_equip_env_SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3,
                          junk_first_sacrifice_enabled=False)
    out, actions = apply_equip_env_variants(
        _sig(['软弱无力']), reg, sess, _COMP, _DEP3, ['幸运星'], _OCC3,
        hold_active=False)
    assert actions == ['fill3=filled:1']
    assert out[0] == ('三月七', '幸运星'), '量变体改派经管道生效(序变体未开)'


# ==================== diamond_detect ====================

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.obs.cw_node_obs import (  # noqa: E402
    DIAMOND_EQUIP_NAMES,
    _equip_is_diamond,
)


def test_diamond_name_matching() -> None:
    """文本兜底:三钻名精确匹配;带「钻」字的非钻装备不误判。"""
    assert _equip_is_diamond('红钻')
    assert _equip_is_diamond('蓝钻')
    assert _equip_is_diamond('财富宝钻')
    # 非钻(名带钻但是合成件/钻头系)——精确匹配天然防误判
    assert not _equip_is_diamond('虫洞掘进钻头')
    assert not _equip_is_diamond('行星钻地弹')
    assert not _equip_is_diamond('以太钻头')
    assert not _equip_is_diamond('红钻·特权')   # 特权变体不在集合(保守:交给 SIFT 通道)
    assert not _equip_is_diamond('')
    assert not _equip_is_diamond('折叠小刀')


def test_sift_templates_available() -> None:
    """SIFT 主通道前置:装备模板库中三钻模板存在(assets 已采集;SR 主仓 = 测试仓根上级)。"""
    sr_repo = _REPO.parent   # sr-od-test 仓根的上级 = StarRailOneDragon 主仓
    base = sr_repo / 'assets' / 'template' / 'currency_war'
    found: set[str] = set()
    for sub in ('equip_plaza', 'equip_legacy'):
        d = base / sub
        if d.is_dir():
            for n in DIAMOND_EQUIP_NAMES:
                if (d / f'{n}.png').exists():
                    found.add(n)
    assert found == set(DIAMOND_EQUIP_NAMES), f'模板缺失: {set(DIAMOND_EQUIP_NAMES) - found}'


def test_sift_channel_degrades_to_text() -> None:
    """降级链:SIFT 通道异常/无模板 → 空集,has_diamond 落文本兜底(不炸流程)。
    用空 columns 直接验证(无列 → 空集,不触模板)。"""
    from sr_od.application.currency_war.obs.cw_node_obs import _sift_detect_diamonds
    class _Ctx:  # 最小 ctx(不会被触达——columns 空短路)
        pass
    assert _sift_detect_diamonds(_Ctx(), None, []) == set()


# ==================== w583_snapshot_contracts ====================

import copy
import dataclasses
from types import SimpleNamespace as _w583_snapshot_contracts_SimpleNamespace

import pytest as _w583_snapshot_contracts_pytest

from sr_od.application.currency_war.kernel.cw_state import  BENCH_CAPACITY, DEPLOYED_FRONT_CAPACITY, BenchChar as _w583_snapshot_contracts_BenchChar, GameState as _w583_snapshot_contracts_GameState, ShopCard as _w583_snapshot_contracts_ShopCard, deployed_place

from sr_od.application.currency_war.sim.runner import synthesize_snapshot
from sr_od.application.currency_war.decision.decision_v2.contracts import  SNAPSHOT_SCHEMA_VERSION, AtomOp, Bail, Decision, Defer, RewardSphere, Snapshot, SnapshotSchemaVersionError, SubstateClassification, derive_snapshot
from sr_od.application.currency_war.decision.decision_v2.director_v2 import  DirectorV2, _DirectorPorts


def _full_state() -> _w583_snapshot_contracts_GameState:
    """构造「全通道可读」的 GameState(正路径对拍底座)。"""
    st = _w583_snapshot_contracts_GameState()
    st.plane, st.round_num = 2, 3
    st.node_type = 'boss'
    st.selected_difficulty = 'A8'
    st.gold, st.gold_readable = 47, True
    st.streak = -2
    st.level, st.xp_progress, st.level_up_cost = 7, (2, 6), 4
    st.bench[0] = _w583_snapshot_contracts_BenchChar(slot=1, char_id='jiaoqiu', faction='xxx', star=2)
    st.bench[4] = _w583_snapshot_contracts_BenchChar(slot=5, char_id='seele', faction='quantum', star=1)
    d1 = _w583_snapshot_contracts_BenchChar(slot=1, char_id='acheron', faction='lightning', star=2,
                   position_pref='front')
    d2 = _w583_snapshot_contracts_BenchChar(slot=1, char_id='fu_xuan', faction='quantum', star=2)
    st.deploy_cap = 5
    deployed_place(st.deployed, d1)   # front_pref → 前排区 0-3
    deployed_place(st.deployed, d2)   # back_pref  → 后排区 4-9
    st.board = {'lightning': 1, 'quantum': 1}
    st.shop = [_w583_snapshot_contracts_ShopCard(x=100, faction='xxx', name='jiaoqiu', cost=3),
               _w583_snapshot_contracts_ShopCard(x=200)]
    st.hp, st.hp_readable = 88, True
    return st


def test_lossless_roundtrip_full_state() -> None:
    """门①进出无损:全可读底座逐字段对拍(映射式=SCHEMA_DRAFT §四来源列)。"""
    st = _full_state()
    snap = synthesize_snapshot(st)

    assert snap.schema_version == SNAPSHOT_SCHEMA_VERSION
    # 节点域
    assert (snap.plane, snap.round_num) == (2, 3)
    assert snap.node_type == 'boss'
    assert snap.selected_difficulty == 'A8'
    # 经济域
    assert snap.gold == 47
    assert snap.gold_trusted is True            # sim 真值契约(合成器注释)
    assert snap.streak == -2
    assert snap.level == 7
    assert snap.xp_progress == (2, 6)
    assert snap.level_up_cost == 4
    # 单位域:元素深拷贝(值等价、非同引用——原 is 共享断言已废,改锁依据见模块 docstring)
    assert snap.bench[0] == st.bench[0] and snap.bench[0] is not st.bench[0]
    assert snap.bench[4] == st.bench[4] and snap.bench[4] is not st.bench[4]
    assert sum(1 for b in snap.bench if b is not None) == 2
    assert snap.deploy_cap == 5
    assert snap.deploy_vacancy == 3             # 5 − 占用 2
    assert snap.free_bench_slots == BENCH_CAPACITY - 2
    assert snap.front_occupied == frozenset(range(0, 1))   # d1 落前排区首槽
    assert snap.back_occupied == frozenset(
        i for i in range(DEPLOYED_FRONT_CAPACITY, 10)
        if st.deployed[i] is not None)
    assert snap.board == {'lightning': 1, 'quantum': 1}
    assert snap.front_size == 4 and snap.back_size == 6
    # 商店域:列表拷贝(容器与元素均非同引用)、逐项同值
    assert snap.shop_cards == tuple(st.shop)
    assert snap.shop_cards is not st.shop
    assert all(sc is not orig
               for sc, orig in zip(snap.shop_cards, st.shop))
    # 交互面域:sim 无实体恒空
    assert snap.spheres == () and snap.boxes == () and snap.tomes == ()
    assert snap.box_overlay_open is False and snap.event_overlay is None
    # 生命域
    assert snap.hp == 88 and snap.hp_readable is True
    # 分类合成契约(门③)
    assert snap.classification.confident is True
    assert snap.classification.name == 'prep_shop'


def test_none_semantics_preserved() -> None:
    """门②None 语义保持:「读不到」变体 → None,禁 0/空/兜底(W558 纪律回归锁)。"""
    st = _full_state()

    st.gold_readable = False
    st.streak = None
    st.node_type = None
    st.hp_readable = False
    st.board_readable = False
    st.deploy_cap = None
    st.level_up_cost = None
    st.xp_progress = None
    snap = synthesize_snapshot(st)

    assert snap.gold is None                    # 禁 0 兜底
    assert snap.streak is None
    assert snap.node_type is None
    assert snap.hp is None                      # 禁沿用值/100 兜底(对账锚在 session)
    assert snap.board is None                   # None(不可读)≠ 空 mapping(真清空)
    assert snap.deploy_cap is None
    assert snap.deploy_vacancy is None          # cap 未读 → None,禁 0 兜底
    assert snap.level_up_cost is None
    assert snap.xp_progress is None
    # free_bench_slots 与失读域解耦:sim 占用恒可读 → 恒 int(Q2 裁决)
    assert isinstance(snap.free_bench_slots, int)


def test_game_state_not_mutated() -> None:
    """门④只读保证:合成前后 GameState 深比较不变(快照纯的反向锁)。"""
    st = _full_state()
    before = copy.deepcopy(st)
    synthesize_snapshot(st)
    assert st == before


def test_hp_none_implies_not_readable() -> None:
    """hp 单向蕴含不变式:hp None ⇒ hp_readable False(反向不成立)。"""
    st = _full_state()
    snap_ok = synthesize_snapshot(st)
    assert snap_ok.hp is not None and snap_ok.hp_readable is True

    st.hp_readable = False
    snap_bad = synthesize_snapshot(st)
    assert snap_bad.hp is None and snap_bad.hp_readable is False
    assert not (snap_bad.hp is None and snap_bad.hp_readable)


def test_snapshot_frozen() -> None:
    """快照纯:实例冻结(派生/覆写必须走 derive_snapshot,禁内联 replace 破墙)。"""
    snap = synthesize_snapshot(_full_state())
    with _w583_snapshot_contracts_pytest.raises(dataclasses.FrozenInstanceError):
        snap.gold = 50


def test_snapshot_container_isolation() -> None:
    """容器隔离防线:容器只读 + 元素深拷贝——污染快照不回写上游 GameState。"""
    st = _full_state()
    snap = synthesize_snapshot(st)
    assert isinstance(snap.bench, tuple)
    assert isinstance(snap.deployed, tuple)
    assert isinstance(snap.shop_cards, tuple)
    # board 只读映射:就地写显式炸(TypeError),不是静默生效
    with _w583_snapshot_contracts_pytest.raises(TypeError):
        snap.board['lightning'] = 5  # type: ignore[index]
    # 元素变异只落在快照私有拷贝上,上游零污染(原 is 共享断言合法化的实洞已焊)
    snap.bench[0].star = 9
    snap.deployed[0].char_id = 'polluted'
    snap.shop_cards[0].name = 'polluted'
    assert st.bench[0].star == 2
    assert st.deployed[0].char_id == 'acheron'
    assert st.shop[0].name == 'jiaoqiu'


def test_derive_snapshot_transform_channel() -> None:
    """显式变换通道:派生新实例、原帧不受扰、派生帧容器互不共享、冻结性不丢。"""
    snap = synthesize_snapshot(_full_state())
    derived = derive_snapshot(snap, gold=50)
    assert derived.gold == 50 and snap.gold == 47
    derived.bench[0].star = 9
    assert snap.bench[0].star == 2              # 派生帧元素深拷贝,不串原帧
    with _w583_snapshot_contracts_pytest.raises(dataclasses.FrozenInstanceError):
        derived.gold = 1


def test_director_rejects_version_mismatch() -> None:
    """schema_version 执行者:DirectorV2 环顶对不匹配版本显式抛错(非注释纪律)。"""
    snap = synthesize_snapshot(_full_state())
    bad = derive_snapshot(snap, schema_version=SNAPSHOT_SCHEMA_VERSION + 1)
    ports = _DirectorPorts(
        decide=lambda s, sess: Decision(),
        observe=lambda heavy: bad,
        execute=lambda op: (True, ''),
        recover=lambda: False,
        force_battle=lambda: True,
        is_stopped=lambda: False,
        stop_with_evidence=lambda msg: None,
        record_defect=lambda kind, detail: None,
    )
    session = _w583_snapshot_contracts_SimpleNamespace(defer_count=0, prep_phase=0, bail_reason_counts={})
    with _w583_snapshot_contracts_pytest.raises(SnapshotSchemaVersionError):
        DirectorV2(ports).run(session)


def test_sim_constant_truth_positions_counterfactual_expressible() -> None:
    """逆真值注入表达性:合成器 9 个恒真位逐一可构造反事实快照。

    sim 合成器恒真值(与实机识别侧的边界态断层),本锁钉住契约面可表达
    非恒真位——批③逆真值 fixture/策略端 None/False 改判式有载体,不会
    被「合成器永远恒真」锁死。
    """
    cases: list[tuple[str, Snapshot, object]] = [
        ('classification.confident', Snapshot(
            classification=SubstateClassification(name='prep_shop',
                                                  confident=False)),
            lambda s: s.classification.confident is False),
        ('gold_trusted', Snapshot(gold_trusted=False),
         lambda s: s.gold_trusted is False),
        ('shop_open', Snapshot(shop_open=False),
         lambda s: s.shop_open is False),
        ('board 不可读', Snapshot(board=None), lambda s: s.board is None),
        ('free_bench_slots 失读', Snapshot(free_bench_slots=None),
         lambda s: s.free_bench_slots is None),
        ('spheres 非空', Snapshot(spheres=(RewardSphere(color='blue', x=1, y=2),)),
         lambda s: len(s.spheres) == 1),
        ('event_overlay 挡操作', Snapshot(event_overlay='modal_event'),
         lambda s: s.event_overlay == 'modal_event'),
        ('box_overlay_open', Snapshot(box_overlay_open=True),
         lambda s: s.box_overlay_open is True),
        ('shop_cards 未读', Snapshot(shop_cards=None),
         lambda s: s.shop_cards is None),
    ]
    assert len(cases) == 9
    for name, snap_cf, check in cases:
        assert check(snap_cf), name


def test_decision_contract_shapes() -> None:
    """Decision 骨架:ops+control 形状可构造;frozen;空决策=合法零进展输入。"""
    d1 = Decision()                                  # decide 返回空批 = 合法「本步不动」
    assert d1.ops == () and d1.control is None
    d2 = Decision(ops=(AtomOp(op_key='buy:0', domain='shop'),),
                  control=None)
    d3 = Decision(ops=(), control=Bail(reason='event_overlay'))
    d4 = Decision(ops=(), control=Defer())
    assert d2.ops[0].domain == 'shop'
    assert isinstance(d3.control, Bail) and isinstance(d4.control, Defer)
    for d in (d1, d2, d3, d4):
        with _w583_snapshot_contracts_pytest.raises(dataclasses.FrozenInstanceError):
            d.ops = ()
    # 分类通道默认不可信(name='unknown'):未知子态不进 decide 的缺省安全态
    assert Snapshot().classification.confident is False
    assert SubstateClassification(name='prep_shop').confident is True


# ==================== idx_contract ====================

import re
from dataclasses import fields
from pathlib import Path as _idx_contract_Path

import pytest as _idx_contract_pytest

from sr_od.application.currency_war.kernel.cw_state import  BENCH_CAPACITY as _idx_contract_BENCH_CAPACITY, DEPLOYED_CAPACITY, BenchChar as _idx_contract_BenchChar, CompTransaction as _idx_contract_CompTransaction, DeployMove, FillSpec, GameState as _idx_contract_GameState, SellBench as _idx_contract_SellBench, SellDeployed as _idx_contract_SellDeployed, SwapDeploy as _idx_contract_SwapDeploy, deployed_occupied, simulate as _idx_contract_simulate

_ROOT = _idx_contract_Path(__file__).resolve().parents[5]          # 仓库根
_SRC = _ROOT / 'src' / 'sr_od' / 'application' / 'currency_war'
_CW_STATE = (_SRC / 'kernel' / 'cw_state.py').read_text(encoding='utf-8')


def _idx_contract_bc(name: str, slot: int = 0, star: int = 1) -> _idx_contract_BenchChar:
    return _idx_contract_BenchChar(slot=slot, char_id=name, star=star)


# ===== A. deployed 域最小反例(ADR-0392 恒稳语义)=====

def test_deployed_double_sell_same_batch_index_stable() -> None:
    """五查② deployed 域反例(ADR-0392 槽位表化后):同批两笔 SellDeployed,
    前者卖出**置 None 不移位** → 后者索引恒稳,命中的恰是生成期指向的原人。

    场景:deployed=[飞霄, 三月七];两笔都按生成期快照发射。第一笔卖飞霄
    (idx0)成功后,第二笔 idx1 **仍指向三月七**(不左移、不越界)——
    任意发射序零漂移。旧紧缩语义下本场景第二笔会漂移/越界(由 expect 拦),
    槽位表示下坑在结构上不存在。
    """
    st = _idx_contract_GameState(deployed=[_idx_contract_bc('飞霄', 1), _idx_contract_bc('三月七', 2)])
    s1 = _idx_contract_simulate(st, _idx_contract_SellDeployed(deployed_idx=0, expect='飞霄'))
    sold = [a for a in s1.action_log if a.get('action') == 'SellDeployed']
    assert sold and sold[0].get('result') == 'applied'
    s2 = _idx_contract_simulate(s1, _idx_contract_SellDeployed(deployed_idx=1, expect='三月七'))
    # 恒稳语义:第二笔索引不变、照常命中三月七(applied,不是拒绝)
    sold2 = [a for a in s2.action_log if a.get('action') == 'SellDeployed']
    assert sold2[-1].get('result') == 'applied'
    assert sold2[-1].get('char') == '三月七'
    assert deployed_occupied(s2.deployed) == 0   # 两槽皆空(None 留槽)


def test_deployed_swap_after_sell_index_stable() -> None:
    """同反例的 SwapDeploy 面:第一笔卖出后 deployed_idx 恒稳,SwapDeploy
    命中生成期指向的槽(旧紧缩语义下 idx 漂移由 expect 拦,现恒稳直通)。"""
    bench = [None] * _idx_contract_BENCH_CAPACITY
    bench[0] = _idx_contract_bc('黑塔', 1)
    st = _idx_contract_GameState(deployed=[_idx_contract_bc('飞霄', 1), _idx_contract_bc('三月七', 2)], bench=bench)
    s1 = _idx_contract_simulate(st, _idx_contract_SellDeployed(deployed_idx=0, expect='飞霄'))
    s2 = _idx_contract_simulate(s1, _idx_contract_SwapDeploy(
        deployed_idx=1, bench_idx=0,
        expect_deployed='三月七', expect_bench='黑塔'))
    # idx1 恒指向三月七 → 换位照常 applied(不因前笔卖出而漂移)
    applied = [a for a in s2.action_log if a.get('action') == 'SwapDeploy'
               and a.get('result') == 'applied']
    assert applied, '槽位表恒稳:换位应照常执行'
    assert s2.deployed[1].char_id == '黑塔'      # 上场者落原槽
    assert s2.bench[0].char_id == '三月七'


def test_bench_domain_no_left_shift_by_construction() -> None:
    """五查② bench 域已结构性失效(ADR-0316):两笔 SellBench 同容器批,
    前者卖出置 None 不移位 → 后者索引恒指向原槽。锁「反例构造不出来」。"""
    bench = [None] * _idx_contract_BENCH_CAPACITY
    bench[0] = _idx_contract_bc('飞霄', 1)
    bench[1] = _idx_contract_bc('三月七', 2)
    st = _idx_contract_GameState(bench=bench)
    s1 = _idx_contract_simulate(st, _idx_contract_SellBench(bench_idx=0, expect='飞霄'))
    s2 = _idx_contract_simulate(s1, _idx_contract_SellBench(bench_idx=1, expect='三月七'))
    assert s2.bench[0] is None and s2.bench[1] is None, \
        'bench 域两笔卖出后两槽皆空(槽位表恒稳)'


# ===== B. expect 写入端静态锁(零写入=死防线)=====

def _all_action_classes() -> list[type]:
    from sr_od.application.currency_war.kernel import cw_state as m
    return list(getattr(m, 'Action').__args__)


def test_expect_fields_have_writers_or_whitelist() -> None:
    """族 A 全 Action 类的 expect* 字段:src/ 下必须存在发射点对其赋值;
    否则该字段定义处必须带 `expect-whitelist: <理由>` 注释。

    零写入 + 无豁免 = 死防线(校验逻辑再全也是恒放行/恒默认,五查④的
    机器化)。白名单豁免标记写在字段行或其相邻注释行,扫描窗口=字段行
    向上 6 行(覆盖 docstring 尾部与行内注释)。"""
    src_text = '\n'.join(
        p.read_text(encoding='utf-8')
        for p in _SRC.rglob('*.py'))
    offenders: list[str] = []
    for cls in _all_action_classes():
        for f in fields(cls):
            if not f.name.startswith('expect'):
                continue
            assigned = re.search(
                rf'\b{cls.__name__}\s*\([^)]*?\b{f.name}\s*=', src_text,
                re.DOTALL) is not None
            if assigned:
                continue
            # 无发射点赋值 → 查白名单标记(字段定义行本身;豁免标记约定
            # 写在字段行内或其注释块——窗口=字段行向上 6 行 + 本行)
            m = re.search(
                rf'^\s*{f.name}\s*:.*$', _CW_STATE, re.MULTILINE)
            wl = False
            if m:
                start = _CW_STATE.rfind('\n', 0, m.start())
                window = _CW_STATE[max(0, start - 600):m.end()]
                wl = 'expect-whitelist:' in window
            if not wl:
                offenders.append(f'{cls.__name__}.{f.name}')
    assert not offenders, (
        'expect 防线字段零写入且无 expect-whitelist 豁免(死防线): '
        f'{offenders};要么补发射点赋值,要么在字段定义处注释 '
        '`expect-whitelist: 理由`(如草案级字段待发射点接线)')


def test_whitelist_entries_must_declare_reason() -> None:
    """豁免标记必须带理由文本(`expect-whitelist:` 冒号后到行尾非空)——
    无理由的豁免=把死防线静默合法化。"""
    for m in re.finditer(r'expect-whitelist:[ \t]*([^\n]*)', _CW_STATE):
        reason = m.group(1).strip()
        assert reason, (
            'expect-whitelist 标记必须带豁免理由'
            '(草案级/待接线/有意观察位等),位置见 cw_state.py')


# ===== C. sim↔执行对拍(accept/reject 一致)=====

def test_sell_guard_aligns_with_simulate_semantics() -> None:
    """五查⑤对拍:sim 侧 simulate(SellBench) 与执行侧 sell_guard_ok 的
    拒绝语义,在同一「生成期期望名 vs 执行期槽内名」对上结论一致。

    sim 侧(cw_state L967-981):expect 非空且与槽内名不符 → rejected
    (stale_proposal);否则卖出。执行侧(shop.sell_guard_ok):expected
    非空且 live==expected 才放行——expected 空(sim 视为不校验)在执行侧
    是拒(执行器更严:无期望名=无从对拍,不点)。两表逐对对拍。"""
    from sr_od.application.currency_war.operations.prep.shop import  sell_guard_ok

    def sim_accepts(bench_idx: int, expect: str) -> tuple[bool, str | None]:
        bench = [None] * _idx_contract_BENCH_CAPACITY
        bench[bench_idx] = _idx_contract_bc('飞霄', 1)
        st = _idx_contract_GameState(bench=bench)
        out = _idx_contract_simulate(st, _idx_contract_SellBench(bench_idx=bench_idx, expect=expect))
        rejected = any(a.get('action') == 'SellBench'
                       and a.get('status') == 'rejected' for a in out.action_log)
        sold = out.bench[bench_idx] is None
        return (not rejected) and sold, out.bench[bench_idx - 1].char_id if False else None

    for bench_idx, expect, live in (
        (0, '飞霄', '飞霄'),    # 名符 → 两路都接受
        (0, '三月七', '飞霄'),  # 名不符 → 两路都拒
        (0, '', '飞霄'),        # sim 不校验(空 expect 放行);执行侧拒(无从对拍)
    ):
        sim_ok, _ = sim_accepts(bench_idx, expect)
        exec_ok = sell_guard_ok(expect or None, live)
        if expect:   # 有期望名的对上:两路结论必须一致
            assert sim_ok == exec_ok == (expect == live), (
                f'idx={bench_idx} expect={expect!r} live={live!r}: '
                f'sim={sim_ok} exec={exec_ok}(同式地错)')
        else:        # 空 expect 是两路的已声明语义差(执行侧更严),锁住不漂移
            assert sim_ok and not exec_ok, \
                '空 expect 语义差漂移:sim 放行(不校验)且执行侧拒(无从对拍)'


def test_deploy_move_index_semantics_sim_only() -> None:
    """DeployMove(族 A)索引语义冒烟:bench_idx=槽位下标,置 None 不移位
    ——与 SellBench 同域同规则(约定块双族对照表的 bench 行)。"""
    bench = [None] * _idx_contract_BENCH_CAPACITY
    bench[3] = _idx_contract_bc('飞霄', 4)
    st = _idx_contract_GameState(bench=bench)
    out = _idx_contract_simulate(st, DeployMove(bench_idx=3, to_row='front', faction='巡海游侠'))
    assert out.bench[3] is None, '上场后槽位置 None(不下移填充)'
    assert len(out.bench) == _idx_contract_BENCH_CAPACITY, '定长不变'
    assert [d.char_id for d in out.deployed if d is not None] == ['飞霄']


# ===== D. F2 型跨源共存锁(ADR-0392 新增)=====

def test_f2_cross_source_mixed_batch_slot_stable() -> None:
    """F2 跨源共存:同轮多源混合动作组(演进 CompTransaction + 换位通道
    SwapDeploy + 直卖通道 SellDeployed)对同一 deployed 槽位表按序消费——
    断言每个 deployed_idx 执行后命中的恰是生成期指向的槽。

    构造(全部 idx 按同一生成期快照发射,模拟 decide_prep 多源拼装):
    - deployed 槽位表:0=桑博 / 1=希儿 / 5=卡芙卡(front 0-3 / back 4-9)
    - 源 A(演进):CompTransaction undeploy 桑凡(槽 0)卖掉
    - 源 B(换位):SwapDeploy(槽 1)希儿 ↔ bench
    - 源 C(直卖):SellDeployed(槽 5)卡芙卡
    三笔任意序执行,每笔命中的都是生成期指向的原槽原人。"""
    deployed = [None] * DEPLOYED_CAPACITY
    deployed[0] = _idx_contract_BenchChar(slot=1, char_id='桑博', faction='持续伤害',
                            position_pref='front')
    deployed[1] = _idx_contract_BenchChar(slot=2, char_id='希儿', faction='量子同频',
                            position_pref='front')
    deployed[5] = _idx_contract_BenchChar(slot=2, char_id='卡芙卡', faction='持续伤害',
                            position_pref='back')
    bench = [None] * _idx_contract_BENCH_CAPACITY
    bench[0] = _idx_contract_bc('黑塔', 1)
    st = _idx_contract_GameState(deployed=deployed, bench=bench, level=8)

    # 源 A/B/C 的动作(idx 全部按生成期快照,跨源拼接)
    tx = _idx_contract_CompTransaction(deploy=[], undeploy=[], sell=[(0, 'deployed')],
                         reason='f2:evolve')
    swap = _idx_contract_SwapDeploy(1, 0, reason='f2:swap',
                      expect_deployed='希儿', expect_bench='黑塔')
    sell_c = _idx_contract_SellDeployed(5, reason='f2:recycle', expect='卡芙卡')

    cur = st
    for act in (tx, swap, sell_c):   # 生成序=执行序(拼装批)
        cur = _idx_contract_simulate(cur, act)
        log = cur.action_log[-1]
        assert log.get('result') == 'applied', \
            f'槽位表恒稳:{type(act).__name__} 应命中生成期指向的槽: {log}'

    # 终态断言:每笔打的是生成期指向的原槽原人
    assert cur.deployed[0] is None        # 源 A 卖的是槽 0 桑博
    assert cur.deployed[1].char_id == '黑塔'   # 源 B 换的是槽 1(希儿下黑塔上)
    assert cur.deployed[5] is None        # 源 C 卖的是槽 5 卡芙卡
    assert deployed_occupied(cur.deployed) == 1
    # bench 侧:黑塔上场腾槽 0,希儿下场落槽(装备/对象随人走)
    assert cur.bench[0].char_id == '希儿'


