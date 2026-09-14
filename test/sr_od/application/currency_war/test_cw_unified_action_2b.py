"""CW 统一动作工厂 批2b 锁面(词表归一 + 删除 + 消费面收口)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-14-unified-action-factory/landing.md §3.2b 判据点名的行为专锁 +
design.md §2.6(词表归一/换算归属/LevelUp 类合并翻转)。

锁面四组(全部运行时行为锁,源码扫描测试禁止,AGENTS.md §10.4):
1. action_key 输出前后对照锁(逐类键面钉死:统一类 = 原族A 类原样,
   字段/顺序/metadata 逐字保留 → 键粒度不漂移;route_tag 携
   action_key_exclude 不入键;原族A 侧 reason/convert_reason/auth_basis
   无 exclude 的现状同批保留 = 商店域键面零漂移锚);
2. 词表归一与删除锁(运行时属性面:族B 旧类/组合壳/CompTransaction/
   FillSpec/PrepAction 在统一词表模块不可达;适配器映射表零组合壳行;
   执行器 F3 拒词表外类型);
3. LevelUp 装载锁 2b 半(发射面 cost = kernel xp_click_cost 现算装载、
   auth_basis = 发射臂放行名分键装载;逻辑态金腿 action.cost 直写与
   执行缝退役锁 = test_cw_unified_action_2a 翻转腿);
4. 换算收口锁(发射面容器下标直取:fail-closed 解析 helper 三域真值 +
   执行坐标边换算函数 deployed_row_slot/deployed_idx_of 互逆)。
"""

from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    xp_click_cost,
)
from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
    deployed_idx_of,
    deployed_row_slot,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
    bench_view_of_slots,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    CwAction,
    CwSimFrame,
    DeployMove,
    LevelUp,
    SellBench,
    SellDeployed,
    action_key,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


# ===== 1. action_key 输出前后对照锁 =====

def test_action_key_faces_pinned_per_class():
    """逐类键面钉死(unified-action-factory §2.6:改名与字段合并不得漂移
    键粒度):统一类 = 原族A 类原样 → 键串 = 归一前族A 形态逐字;
    prep 域键面变化 = 字段值更换(bench_idx),粒度(键内字段集)不变。"""
    # SellBench:字段集 = bench_idx/income/expect/reason/convert_reason
    # (route_tag 基类字段携 exclude 不入键)
    assert action_key(SellBench(bench_idx=0)) == (
        "SellBench({'bench_idx': 0, 'income': None, 'expect': '', "
        "'reason': '', 'convert_reason': ''})")
    assert action_key(SellBench(bench_idx=3)) != \
        action_key(SellBench(bench_idx=0))   # 行为参数分裂幂等键(原语义)
    # route_tag(发射臂路由标签)不入键:同槽不同 tag = 同一动作实例
    assert action_key(SellBench(bench_idx=0, route_tag='m4_fuel_sell')) == \
        action_key(SellBench(bench_idx=0))
    # LevelUp:cost 入键(批2b 装载语义);auth_basis(授权记录)族A
    # 现状无 exclude → 入键,缺省空串形态同在键内(键粒度零漂移锚,
    # 禁后续静默改 metadata)
    assert action_key(LevelUp(cost=4)) == (
        "LevelUp({'cost': 4, 'auth_basis': ''})")
    assert action_key(LevelUp(cost=4, auth_basis='arm1')) != \
        action_key(LevelUp(cost=4))
    # DeployMove/SellDeployed:容器下标字段替换物理槽位字段,键形态同构
    assert 'bench_idx' in action_key(DeployMove(bench_idx=1, to_row='front',
                                                faction=''))
    assert 'deployed_idx' in action_key(SellDeployed(deployed_idx=0))


# ===== 2. 词表归一与删除锁 =====

def test_unified_vocab_is_single_source_and_removals_hold():
    """词表单源 + 退役类运行时不可达:族B 旧类(物理槽位 SellBench 载体
    已合并)/组合壳三件/CompTransaction/FillSpec/PrepAction 旧名在
    cw_vocab 模块面全部 AttributeError;CW_ACTION_TYPES 无组合壳成员。"""
    import sr_od.application.currency_war.kernel.cw_vocab as vocab_mod
    import sr_od.application.currency_war.kernel.cw_prep_actions as kpa_mod
    for dead in ('CompTransaction', 'FillSpec', 'RunDeploy', 'RunEquip',
                 'RunTools', 'PickBoxCard', 'PrepAction',
                 'PREP_ACTION_TYPES', '_resolve_comp_transaction',
                 '_apply_comp_transaction'):
        assert not hasattr(vocab_mod, dead), dead
    # cw_prep_actions 词表退役:只剩观察视图与点球挑选 kernel
    for dead in ('PrepAction', 'SellBench', 'DeployMove', 'RunDeploy',
                 'PREP_ACTION_TYPES', 'action_key'):
        assert not hasattr(kpa_mod, dead), dead
    for live in ('PrepObservation', 'select_sphere_clicks',
                 'SPHERE_CLICK_HARD_CAP'):
        assert hasattr(kpa_mod, live), live
    names = {c.__name__ for c in CW_ACTION_TYPES}
    for dead in ('RunDeploy', 'RunEquip', 'RunTools', 'PickBoxCard',
                 'CompTransaction'):
        assert dead not in names, dead
    # 全类 CwAction 后代(统一基类;isinstance 检查统一走基类)
    assert all(issubclass(c, CwAction) for c in CW_ACTION_TYPES)
    assert {c.__name__ for c in CW_ACTION_TYPES} >= {
        'BuyCard', 'SellBench', 'LevelUp', 'DeployMove', 'SellDeployed',
        'ClickSpheres', 'OpenBox', 'OpenTome', 'WearEquip', 'FurnaceUse',
        'StartBattle', 'OpenShop'}


def test_adapter_spec_rows_and_prep_f3_reject_unknown():
    """适配器映射表零组合壳行(R2 删除面);执行器 F3 白名单 = 统一词表
    元组,词表外类型拒(参数非法路径,Director 交回外循环留证)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        adapter,
    )
    for dead in ('RunDeploy', 'RunEquip', 'RunTools', 'PickBoxCard'):
        assert dead not in adapter._OP_SPECS, dead
    from sr_od.application.currency_war import prep_actions as pa
    from one_dragon.base.geometry.point import Point
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    ex._front_pts = [Point(i * 10, i * 10) for i in range(4)]
    ex._back_pts = [Point(i * 10, i * 10) for i in range(6)]
    assert ex.validate(SimpleNamespace()) is not None   # 词表外 → 拒
    assert ex.validate(SellBench(bench_idx=0)) is None   # 在册 → 合法


# ===== 3. LevelUp 装载锁(2b 半:发射面)=====

def test_levelup_emission_carries_cost_and_auth_basis():
    """发射面装载(design.md §2.6 LevelUp 定案③口径):cost = kernel
    xp_click_cost 现算(bs.level_up_cost 缺读时函数内回退
    XP_CLICK_COST_FALLBACK 折扣支,发射位零本地回退分支);auth_basis =
    发射臂放行名分键(arm1/arm0/pop/must_spend 封闭集);route_tag 沿
    Emitted.reason 透传(m3_levelup_batch:<tag>)。"""
    deployed = [BenchChar(slot=i + 1, char_id=f'注册表外散件{i}', star=2)
                for i in range(4)]
    frame = mandate.MandateFrame(
        gold=80, level=4, bench=[BenchChar(slot=1, char_id='注册表外散件A')],
        deployed=deployed, deploy_cap=4, node_type='battle',
        stop_flag=False, k_members=(), round_num=2)
    st = CwSimFrame(gold=80, level=4, hp=30, plane=2, round_num=2)
    st.level_readable = True
    st.deploy_cap = 4
    st.node_type = 'battle'
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                           v3_intention=IntentionState(),
                           active_strategies=[])
    out = mandate.run_mandate(frame, sess, state=cw4_box(st))
    lv = [e for e in out if isinstance(e.action, LevelUp)]
    assert lv, '构帧须命中 M3 升级臂(与 no_target 三臂锁 4 同形)'
    bs_cost_view = cw4_box(CwSimFrame(gold=80, level=4, hp=30, plane=2,
                                      round_num=2, level_up_cost=4))
    a = lv[0].action
    assert a.cost == xp_click_cost(bs_cost_view)   # 现算单一源(含回退支)
    assert a.auth_basis in ('arm1', 'arm0', 'pop', 'must_spend')
    # route_tag 透传面 = Emitted.reason(动作对象 route_tag 由桥伴在
    # decide_from_turn 装载,发射位直跑不经桥 → reason 承载)
    assert lv[0].reason.startswith('m3_levelup_batch:')


# ===== 4. 换算收口锁 =====

def test_emission_resolves_container_index_fail_closed():
    """发射面容器下标解析(unified-action-factory §2.6 换算归属):bench
    域按槽位信息位与容器槽位表读口对位取枚举下标;deployed 域按
    (排, 槽号) 二元组对位;失配 = None(fail-closed 跳过,禁猜位)。"""
    bs = board_state_of(None)
    # 槽位表构造 = 位置映射(bench_view_of_slots:槽 i = 列表下标 i,信息位
    # 槽号 = i+1 由视图重建)——槽 4 的件放列表下标 3。
    bs.write_logic(bs.bench, bench_view_of_slots(
        [None, None, None, BenchChar(slot=4, char_id='甲', star=1)]),
        produced_by='T', sig=_SIG)
    bs.write_logic(bs.front_row, [Unit(slot=2, char_id='刃', star=1)],
                   produced_by='T', sig=_SIG)
    assert mandate._bench_container_idx_by_slot(bs, 4) == 3   # 槽4 → 下标3
    assert mandate._bench_container_idx(
        bs, BenchChar(slot=4, char_id='甲', star=1)) == 3
    assert mandate._bench_container_idx_by_slot(bs, 9) is None   # 空槽失配
    assert mandate._bench_container_idx_by_slot(bs, 0) is None   # 非法值
    assert mandate._deployed_container_idx(
        bs, BenchChar(slot=2, char_id='刃', star=1, position_pref='front')) \
        == 1   # front slot2 → 下标1
    # fail-closed = (排, 槽号) 键失配(对位键不含身份:两视图同帧同源,
    # 身份随槽位键而来);后排槽位缺席 → None。
    assert mandate._deployed_container_idx(
        bs, BenchChar(slot=3, char_id='不在场', star=1,
                      position_pref='back')) is None


def test_executor_edge_conversion_functions_are_single_inverse_pair():
    """执行坐标边换算函数(kernel 单一源)互逆且边界正确:下标 0-9 →
    (排, 槽号) → 下标恒等;跨界值域锁定(front 1-4 / back 1-6)。"""
    for idx in range(10):
        row, slot_no = deployed_row_slot(idx)
        assert deployed_idx_of(row, slot_no) == idx
    assert deployed_row_slot(0) == ('front', 1)
    assert deployed_row_slot(3) == ('front', 4)
    assert deployed_row_slot(4) == ('back', 1)
    assert deployed_row_slot(9) == ('back', 6)
