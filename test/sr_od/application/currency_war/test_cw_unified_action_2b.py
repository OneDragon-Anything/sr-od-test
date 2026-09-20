"""CW 统一动作工厂 批2b 锁面(词表归一 + 删除 + 消费面收口)。

出处(持久索引):备战词表单一源与坐标系裁定 = kernel/cw_vocab.py 模块头
(现役声明与全类居所);动作逻辑态规则正本 =
docs/develop/sr_od/application/currency_war/flow/action-logic-state.md;
判据语义 = 备战动作统一词表(基类/元组/action_key 单一源)、席位域动作
携容器槽位表下标(发射面吃下标,物理换算仅存观察写入边与执行坐标边)、
CwActionLevelUpParam 携 cost(单击价现算装载)+auth_basis(授权记录分键)。

锁面四组(全部运行时行为锁,源码扫描测试禁止,AGENTS.md §10.4):
1. action_key 输出前后对照锁(逐类键面钉死:统一类 = 原族A 类原样,
   字段/顺序/metadata 逐字保留 → 键粒度不漂移;route_tag 携
   action_key_exclude 不入键;原族A 侧 reason/convert_reason/auth_basis
   无 exclude 的现状同批保留 = 商店域键面零漂移锚);
2. 词表白名单行为锁(F3 白名单行为半:执行器拒词表外类型、在册动作
   合法域放行;白名单元组面对账已退役——删除面由该行为红兜底,不设
   退役符号墓碑断言);
3. CwActionLevelUpParam 装载锁 2b 半(发射面 cost = kernel xp_click_cost 现算装载、
   auth_basis = 发射臂放行名分键装载;逻辑态金腿 action.cost 直写与
   执行缝退役锁 = test_cw_unified_action_2a 翻转腿);
4. 换算收口锁(发射面容器下标直取:fail-closed 解析 helper 三域真值 +
   执行坐标边换算函数 deployed_row_slot/deployed_idx_of 互逆,同锁两段)。
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
    BenchSlot,
    ChannelSig,
    Unit,
    bench_view_of_slots,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwSimFrame,
    CwActionDeployMoveParam,
    CwActionLevelUpParam,
    CwActionSellBenchParam,
    CwActionSellDeployedParam,
    action_key,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


# ===== 1. action_key 输出前后对照锁 =====

def test_action_key_faces_pinned_per_class():
    """逐类键粒度钉死(词表归一硬判据「改名与字段合并不得漂移键粒度」,
    持久索引见模块头;幂等键消费 = cw_screen_prep 重派/对账去重):
    - 行为参数入键(变化 → 键变 = 幂等键分裂);
    - 发射臂路由标签不入键(同槽不同 tag = 同一动作实例);
    - 容器下标字段(bench_idx/deployed_idx)构成键面(替换物理槽位字段)。
    (原「键串 = 归一前族A 形态逐字」腿降规格:逐字 repr 锁的是 Python
    repr 格式,过度规格,消费面只需键稳定性与粒度。)"""
    # CwActionSellBenchParam:行为参数分裂幂等键;route_tag(发射臂路由标签)不入键
    assert action_key(CwActionSellBenchParam(bench_idx=3)) != \
        action_key(CwActionSellBenchParam(bench_idx=0))
    assert action_key(CwActionSellBenchParam(bench_idx=0, route_tag='m4_fuel_sell')) == \
        action_key(CwActionSellBenchParam(bench_idx=0))
    assert 'bench_idx' in action_key(CwActionSellBenchParam(bench_idx=0))
    # CwActionLevelUpParam:cost 与 auth_basis 入键(键粒度零漂移锚,禁静默改 metadata)
    assert action_key(CwActionLevelUpParam(cost=4)) != action_key(CwActionLevelUpParam(cost=5))
    assert action_key(CwActionLevelUpParam(cost=4, auth_basis='arm1')) != \
        action_key(CwActionLevelUpParam(cost=4))
    assert 'cost' in action_key(CwActionLevelUpParam(cost=4))
    # CwActionDeployMoveParam/CwActionSellDeployedParam:容器下标字段替换物理槽位字段,键形态同构
    assert 'bench_idx' in action_key(CwActionDeployMoveParam(bench_idx=1, to_row='front',
                                                to_slot=1, faction=''))
    assert 'deployed_idx' in action_key(CwActionSellDeployedParam(deployed_idx=0))


# ===== 2. 词表归一与删除锁(行为半)=====

def test_prep_f3_rejects_unknown_and_admits_registered():
    """执行器 F3 白名单 = 统一词表元组的行为半:词表外类型拒(参数非法
    路径,Director 交回外循环留证),在册动作合法域放行。"""
    from one_dragon.base.geometry.point import Point
    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    ex._front_pts = [Point(i * 10, i * 10) for i in range(4)]
    ex._back_pts = [Point(i * 10, i * 10) for i in range(6)]
    assert ex.validate(SimpleNamespace()) is not None   # 词表外 → 拒
    assert ex.validate(CwActionSellBenchParam(bench_idx=0)) is None   # 在册 → 合法


# ===== 3. CwActionLevelUpParam 装载锁(2b 半:发射面)=====

def test_levelup_emission_carries_cost_and_auth_basis():
    """发射面装载(CwActionLevelUpParam 粒度定案③口径,持久索引见模块头):cost = kernel
    xp_click_cost 现算(gs.level_up_cost 缺读时函数内回退
    XP_CLICK_COST_FALLBACK 折扣支,发射位零本地回退分支);auth_basis =
    发射臂放行名分键(arm1/arm0/pop/must_spend 封闭集);route_tag 沿
    Emitted.reason 透传(m3_levelup_batch:<tag>)。"""
    # P4 容器形:MandateFrame 直构面 = 占席条目 + 行域 Unit
    deployed = [Unit(slot=i + 1, char_id=f'注册表外散件{i}', star=2)
                for i in range(4)]
    frame = mandate.MandateFrame(
        gold=80, level=4, bench=[BenchSlot(kind='unit', unit=Unit(
            char_id='注册表外散件A', star=1, slot=1))],
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
    lv = [e for e in out if isinstance(e.action, CwActionLevelUpParam)]
    assert lv, '构帧须命中 M3 升级臂(与 no_target 三臂锁 4 同形)'
    gs_cost_view = cw4_box(CwSimFrame(gold=80, level=4, hp=30, plane=2,
                                      round_num=2, level_up_cost=4))
    a = lv[0].action
    assert a.cost == xp_click_cost(gs_cost_view)   # 现算单一源(含回退支)
    assert a.auth_basis in ('arm1', 'arm0', 'pop', 'must_spend')
    # route_tag 透传面 = Emitted.reason(动作对象 route_tag 由桥伴在
    # decide_prep_frame 装载,发射位直跑不经桥 → reason 承载)
    assert lv[0].reason.startswith('m3_levelup_batch:')


def test_sellbench_emission_carries_channel_reason():
    """CwActionSellBenchParam 发射面通道记录装载:r9 争金归因证据层(决策行 form_ok
    时序批 sibling 件;登记门单一源 = cw_vocab.SELL_BENCH_REASONS)。
    溢出清位臂(overflow_warning 短路 return)CwActionSellBenchParam.reason = 通道键
    m4_fuel_sell;记录非指令,资格单一源(sell_gate 装配 A)零触碰。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    # P4 容器形:MandateFrame 直构面 = 占席条目 + 行域 Unit
    deployed = [Unit(slot=i + 1, char_id=f'注册表外散件{i}', star=2)
                for i in range(4)]
    frame = mandate.MandateFrame(
        gold=80, level=4,
        bench=[BenchSlot(kind='unit', unit=Unit(
            char_id='注册表外散件A', star=1, slot=1))],
        deployed=deployed, deploy_cap=4, node_type='battle',
        stop_flag=False, k_members=(), round_num=2, overflow_warning=True)
    st = CwSimFrame(gold=80, level=4, hp=30, plane=2, round_num=2)
    st.level_readable = True
    st.deploy_cap = 4
    st.node_type = 'battle'
    gs = game_state_of(None)
    # 燃料资格面读容器(空板守卫读 deployed + bench 边际维),双容器预写
    gs.write_logic(gs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='注册表外散件A', star=1)]),
        produced_by='T', sig=_SIG)
    gs.write_logic(gs.front_row, [
        Unit(slot=i + 1, char_id=f'注册表外散件{i}', star=2)
        for i in range(4)],
        produced_by='T', sig=_SIG)
    sess = _NS(cw4_counters={}, target_comp=None,
               v3_intention=IntentionState(), active_strategies=[])
    out = mandate.run_mandate(frame, sess, state=gs)
    sb = [e for e in out if isinstance(e.action, CwActionSellBenchParam)]
    assert sb, '构帧须命中溢出清位臂(1★ 线外燃料 + overflow_warning)'
    assert sb[0].action.reason == 'm4_fuel_sell'
    # route_tag 载体 = Emitted.reason(桥伴装载;通道键单一词汇)
    assert sb[0].reason == 'm4_fuel_sell'


# ===== 4. 换算收口锁 =====

def test_emission_resolves_container_index_fail_closed():
    """发射面容器下标解析(换算归属裁定,持久索引见模块头):bench
    域按槽位信息位与容器槽位表读口对位取枚举下标;deployed 域按
    (排, 槽号) 二元组对位;失配 = None(fail-closed 跳过,禁猜位)。"""
    gs = game_state_of(None)
    # 槽位表构造 = 位置映射(bench_view_of_slots:槽 i = 列表下标 i,信息位
    # 槽号 = i+1 由视图重建)——槽 4 的件放列表下标 3。
    gs.write_logic(gs.bench, bench_view_of_slots(
        [None, None, None, BenchChar(slot=4, char_id='甲', star=1)]),
        produced_by='T', sig=_SIG)
    gs.write_logic(gs.front_row, [Unit(slot=2, char_id='刃', star=1)],
                   produced_by='T', sig=_SIG)
    assert mandate._bench_container_idx_by_slot(gs, 4) == 3   # 槽4 → 下标3
    assert mandate._bench_container_idx(
        gs, BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1, slot=4))
    ) == 3
    assert mandate._bench_container_idx_by_slot(gs, 9) is None   # 空槽失配
    assert mandate._bench_container_idx_by_slot(gs, 0) is None   # 非法值
    assert mandate._deployed_container_idx(
        gs, Unit(slot=2, char_id='刃', star=1)) \
        == 1   # front slot2 → 下标1(对位键 = (身份, 行内槽号))
    # fail-closed = (身份, 行内槽号) 键失配;后排槽位缺席 → None。
    assert mandate._deployed_container_idx(
        gs, Unit(slot=3, char_id='不在场', star=1)) is None
    # 执行坐标边换算函数(kernel 单一源)互逆且边界正确(原互逆锁迁并):
    # 下标 0-9 → (排, 槽号) → 下标恒等;跨界值域锁定(front 1-4 / back 1-6)。
    for idx in range(10):
        row, slot_no = deployed_row_slot(idx)
        assert deployed_idx_of(row, slot_no) == idx
    assert deployed_row_slot(0) == ('front', 1)
    assert deployed_row_slot(3) == ('front', 4)
    assert deployed_row_slot(4) == ('back', 1)
    assert deployed_row_slot(9) == ('back', 6)
