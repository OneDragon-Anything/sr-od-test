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
   执行坐标边固定双射(3.2 换算族退役后内联算术,同锁两段)。
"""

from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    xp_click_cost,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
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
    deployed = [Unit( char_id=f'注册表外散件{i}', star=2)
                for i in range(4)]
    frame = mandate.MandateFrame(
        gold=80, level=4, bench=[BenchSlot(kind='unit', unit=Unit(
            char_id='注册表外散件A', star=1))],
        deployed=deployed, deploy_cap=4, node_type='battle',
        stop_flag=False, k_members=(), round_num=2)
    st = {'gold': 80, 'level': 4, 'hp': 30, 'plane': 2, 'round_num': 2,
          'deploy_cap': 4, 'node': 'battle'}
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                           v3_intention=IntentionState(),
                           active_strategies=[])
    out = mandate.run_mandate(frame, sess, state=cw4_box(**st))
    lv = [e for e in out if isinstance(e.action, CwActionLevelUpParam)]
    assert lv, '构帧须命中 M3 升级臂(与 no_target 三臂锁 4 同形)'
    gs_cost_view = cw4_box(gold=80, level=4, hp=30, plane=2,
                           round_num=2, level_up_cost=4)
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
    deployed = [Unit( char_id=f'注册表外散件{i}', star=2)
                for i in range(4)]
    frame = mandate.MandateFrame(
        gold=80, level=4,
        bench=[BenchSlot(kind='unit', unit=Unit(
            char_id='注册表外散件A', star=1))],
        deployed=deployed, deploy_cap=4, node_type='battle',
        stop_flag=False, k_members=(), round_num=2, overflow_warning=True)
    gs = game_state_of(None)
    # 燃料资格面读容器(空板守卫读 deployed + bench 边际维),双容器预写
    gs.write_logic(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=Unit(
            char_id='注册表外散件A', star=1))]
        + [BenchSlot(kind='empty')] * 8, capacity=9),
        produced_by='T', sig=_SIG)
    gs.write_logic(gs.deployed, _dvs([
        Unit( char_id=f'注册表外散件{i}', star=2)
        for i in range(4)], []),
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

def test_bridge_recheck_context_uses_slot_table_indices(monkeypatch):
    """桥复检语境坐标锁(批2b「bridge 复检语境容器下标化」行为半):
    ``decide_prep_frame`` 供给截断复检的 bench 占用集必须 = **定长槽位表
    下标**(动作参数坐标系,bench_idx 同系,cw_vocab 坐标契约节单一源)
    ——前部有洞帧按紧缩序(bench_entries_of)枚举下标供给会错杀后部
    占用槽的合法引用,发射被截空后世界不变 → 备战环「本帧无动作」
    无限交回(sim 多种子首局活锁实证,实机同链路同受害)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        bridge,
        entry,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        Emitted,
    )

    class _Cfg:
        ev_arm = 'full'

    session = SimpleNamespace()
    gs = game_state_of(session)
    # 前部两洞 + 槽3/槽5 占席(槽位信息位 = 数组下标+1);占用槽表下标
    # 集 = {2, 4},紧缩序枚举下标集 = {0, 1}——两坐标系此帧分叉。
    gs.write_logic(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 2
        + [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1)),
           BenchSlot(kind='empty'),
           BenchSlot(kind='unit', unit=Unit(char_id='乙', star=1))]
        + [BenchSlot(kind='empty')] * 4, capacity=9),
        produced_by='T', sig=_SIG)
    # 正半:引用占用槽表下标 4(乙)必须通过复检照发——错杀即本锁红。
    sell = CwActionSellBenchParam(bench_idx=4, reason='interest_prep')
    monkeypatch.setattr(entry, 'emit',
                        lambda *a, **k: [Emitted(sell, True, 'interest_prep')])
    assert bridge.decide_prep_frame(session, _Cfg()) == [sell]
    # 负半:真空槽引用(下标 0)照旧 fail-closed 截空——复检防线语义
    # 不因坐标修复放宽。
    ghost = CwActionSellBenchParam(bench_idx=0, reason='interest_prep')
    monkeypatch.setattr(entry, 'emit',
                        lambda *a, **k: [Emitted(ghost, True, 'interest_prep')])
    assert bridge.decide_prep_frame(session, _Cfg()) == []


def test_emission_resolves_container_index_fail_closed():
    """发射面容器下标解析(换算归属裁定,持久索引见模块头):bench
    域按紧缩位键(overlay-trigger 3.1:占席序 0 基)与容器槽位表枚举
    对位取下标;deployed 域按视图子表条目对位;失配 = None
    (fail-closed 跳过,禁猜位)。"""
    gs = game_state_of(None)
    # 槽位表构造 = 位置映射(槽 i = 列表下标 i)——槽 4(第 1 个占用槽)
    # 的件放列表下标 3。
    gs.write_logic(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 3
        + [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1))]
        + [BenchSlot(kind='empty')] * 5, capacity=9),
        produced_by='T', sig=_SIG)
    gs.write_logic(gs.deployed,
                   DeployedView(front_slots=[None, Unit(char_id='刃', star=1)],
                                back_slots=[]),
                   produced_by='T', sig=_SIG)
    assert mandate._bench_container_idx_by_compact(gs, 0) == 3   # 首占用槽
    assert mandate._bench_container_idx(
        gs, BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1))
    ) == 3
    assert mandate._bench_container_idx_by_compact(gs, 1) is None   # 无第 2 占用
    assert mandate._bench_container_idx_by_compact(gs, -1) is None  # 非法值
    assert mandate._deployed_container_idx(
        gs, Unit( char_id='刃', star=1)) \
        == 1   # front slot2 → 下标1(视图子表下标对位)
    # fail-closed = 视图子表条目失配;不在场 → None。
    assert mandate._deployed_container_idx(
        gs, Unit( char_id='不在场', star=1)) is None
    # 执行坐标边固定双射(overlay-trigger 3.2:换算函数族退役,双射为
    # 内联算术;本段锁值域不变):下标 0-9 → (排, 槽号) → 下标恒等
    #(front 1-4 / back 1-6)。
    from sr_od.application.currency_war.kernel.cw_exec_state import (
        DEPLOYED_FRONT_CAPACITY,
    )

    def _row_slot(idx: int) -> tuple[str, int]:
        return ('front' if idx < DEPLOYED_FRONT_CAPACITY else 'back',
                (idx + 1 if idx < DEPLOYED_FRONT_CAPACITY
                 else idx - DEPLOYED_FRONT_CAPACITY + 1))

    for idx in range(10):
        row, slot_no = _row_slot(idx)
        _back = (slot_no - 1 if row == 'front'
                 else DEPLOYED_FRONT_CAPACITY + slot_no - 1)
        assert _back == idx
    assert _row_slot(0) == ('front', 1)
    assert _row_slot(3) == ('front', 4)
    assert _row_slot(4) == ('back', 1)
    assert _row_slot(9) == ('back', 6)
