"""工具原子七类记账路径(坐标反查)测试。

锁的设计约定(记账路径总契约第二适用者;契约正文 = action-op.md「记账
路径总契约」条款;被测单一源 = kernel/cw_action_report/tool_use):
- 记账键 = 上报坐标(源 tool_cx/tool_cy 七类通用;equip 模式另带
  tgt_cx/tgt_cy 第二反查键),内容 = 坐标伴随域反查产物;反查不到 =
  tool_xy_unresolved / tool_target_xy_unresolved 拒单零写(名称在库检查
  furnace_target_missing / privilege_target_missing 已退役);
- 名称零消费:同坐标 × 任意 item_name → 记账结果逐位相同(宪法③锁面);
- 反查产物移除 = 严格移除(命中但名单缺条目 = 禁消费窗口违反,自然
  ValueError);状态推导名(炉 char 分支穿戴件)维持 _remove_one 容错
  (混合语义锁面,防两族语义搅浑);
- tool_target_unit_missing 升格拒单(applied=False,与穿装批同形统一);
- 精密扳手 consume=False 源反查豁免:不拒单,evidence 注记
  tool_xy_unresolved 形态(无消耗笔可拒,拒单 = 物理卸装无账);
- 冶金炉采样与后果采证钩子回归:行为不变(仅键源换反查产物)。

⚠️ 测试内对 ``tool_use.FURNACE_MUTATE_CATEGORIES`` 打补丁(注册表官方
类别名 '简易装备'/'进阶装备')——v4.7 注册表重灌后类别命名与该白名单
短名失配,池恒不可用为数据域在飞问题(判据白名单对齐归 v4.7 适配批,
非本参数面批辖域);补丁只还原类别对齐,采样/严格移除/合并写全链走
真实路径。未打补丁用例单独锁定「池不可用 → fail-closed 零写」现状。
"""

import random
import types

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import tool_use
from sr_od.application.currency_war.kernel.cw_action_report.tool_use import (
    report_action_furnace_use_param,
    report_action_lucky_token_use_param,
    report_action_perfect_projector_use_param,
    report_action_precision_wrench_use_param,
    report_action_privilege_card_use_param,
    report_action_staff_projector_use_param,
    report_action_wrench_use_param,
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
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionFurnaceUseParam,
    CwActionLuckyTokenUseParam,
    CwActionPerfectProjectorUseParam,
    CwActionPrecisionWrenchUseParam,
    CwActionPrivilegeCardUseParam,
    CwActionStaffProjectorUseParam,
    CwActionWrenchUseParam,
)

_SIG = ChannelSig(family='logic_action', actor='test')
_OBS = ChannelSig(family='obs', actor='test')

_TOOL_XY = (1660, 120)
_TGT_XY = (1740, 210)


def _seed_gs(owned: list[str], xy: dict | None,
             front_units: list[Unit | None],
             bench_slots: list[BenchSlot] | None = None) -> GameState:
    """测试种子(与观察链同写入口 gs.observe;deployed 前排补齐定长 4)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, list(owned), sig=_OBS)
    if xy is not None:
        gs.observe(gs.owned_equip_xy, xy, sig=_OBS)
    slots = list(front_units) + [None] * (4 - len(front_units))
    gs.observe(gs.deployed,
               DeployedView(front_slots=slots, back_slots=[None] * 6),
               sig=_OBS)
    if bench_slots is not None:
        gs.observe(gs.bench, BenchView(slots=bench_slots, capacity=9),
                   sig=_OBS)
    return gs


def _furnace_equip(item_name: str = '量产型装甲',
                   tool_xy: tuple[int, int] = _TOOL_XY,
                   tgt_xy: tuple[int, int] = _TGT_XY,
                   ) -> CwActionFurnaceUseParam:
    return CwActionFurnaceUseParam(
        target_kind='equip', tool_cx=tool_xy[0], tool_cy=tool_xy[1],
        tgt_cx=tgt_xy[0], tgt_cy=tgt_xy[1], item_name=item_name)


def _furnace_char(row: str = 'front', slot: int = 1,
                  tool_xy: tuple[int, int] = _TOOL_XY,
                  ) -> CwActionFurnaceUseParam:
    return CwActionFurnaceUseParam(
        target_kind='char', tool_cx=tool_xy[0], tool_cy=tool_xy[1],
        row=row, slot=slot)


def _priv_equip(item_name: str = '武器大师',
                tool_xy: tuple[int, int] = _TOOL_XY,
                tgt_xy: tuple[int, int] = _TGT_XY,
                ) -> CwActionPrivilegeCardUseParam:
    return CwActionPrivilegeCardUseParam(
        target_kind='equip', tool_cx=tool_xy[0], tool_cy=tool_xy[1],
        tgt_cx=tgt_xy[0], tgt_cy=tgt_xy[1], item_name=item_name)


@pytest.fixture
def aligned_categories(monkeypatch):
    """炉采样白名单对齐注册表官方类别名(见模块头 ⚠️ 注)。"""
    monkeypatch.setattr(tool_use, 'FURNACE_MUTATE_CATEGORIES',
                        frozenset({'简易装备', '进阶装备'}))


def test_furnace_equip_hit_accounts_by_resolution(aligned_categories) -> None:
    """反查命中(冶金炉 equip):双键反查产物记账——owned 严格移除工具与
    目标件、追加同类别池采样替换件,evidence 含反查产物名。"""
    gs = _seed_gs(owned=['冶金炉', '量产型装甲'],
                  xy={'冶金炉': [_TOOL_XY], '量产型装甲': [_TGT_XY]},
                  front_units=[Unit(char_id='罗刹', star=2, equips=[])])
    outcome = report_action_furnace_use_param(
        gs, _furnace_equip(), _SIG, rng=random.Random(7))
    assert outcome.applied is True
    from sr_od.application.currency_war.kernel.cw_action_report.tool_use import (
        furnace_mutate_pool,
    )
    new_inv = gs.equips.value
    assert len(new_inv) == 1   # 2 − 工具 − 目标件 + 采样替换件
    assert '冶金炉' not in new_inv and '量产型装甲' not in new_inv
    assert new_inv[0] in furnace_mutate_pool('量产型装甲')
    assert f'量产型装甲>{new_inv[0]}' in (gs.equips.evidence or '')


def test_furnace_equip_pool_unavailable_fails_closed() -> None:
    """池不可用(类别越白名单/不在注册表,未打补丁现状)→ fail-closed
    零写(applied=True 保留,bug 面失败安全语义不变)。"""
    gs = _seed_gs(owned=['冶金炉', '量产型装甲'],
                  xy={'冶金炉': [_TOOL_XY], '量产型装甲': [_TGT_XY]},
                  front_units=[Unit(char_id='罗刹', star=2, equips=[])])
    outcome = report_action_furnace_use_param(
        gs, _furnace_equip(), _SIG, rng=random.Random(7))
    assert outcome.applied is True
    assert outcome.reason == 'furnace_pool_unavailable'
    assert gs.equips.value == ['冶金炉', '量产型装甲']   # 零写


def test_furnace_equip_resolve_miss_rejects_zero_write() -> None:
    """反查不到:源键(坐标不在表/伴随域 None)→ tool_xy_unresolved 拒单;
    目标键不在表 → tool_target_xy_unresolved 拒单;均零写。"""
    unit = Unit(char_id='罗刹', star=2, equips=[])
    # 源坐标不在表
    gs = _seed_gs(owned=['冶金炉', '量产型装甲'],
                  xy={'冶金炉': [(1, 1)], '量产型装甲': [_TGT_XY]},
                  front_units=[unit])
    outcome = report_action_furnace_use_param(
        gs, _furnace_equip(tool_xy=(9, 9)), _SIG, rng=random.Random(7))
    assert outcome.applied is False
    assert outcome.reason == 'tool_xy_unresolved'
    assert gs.equips.value == ['冶金炉', '量产型装甲']
    # 伴随域未就绪(None)
    gs2 = _seed_gs(owned=['冶金炉', '量产型装甲'], xy=None,
                   front_units=[unit])
    outcome2 = report_action_furnace_use_param(
        gs2, _furnace_equip(), _SIG, rng=random.Random(7))
    assert outcome2.applied is False
    assert outcome2.reason == 'tool_xy_unresolved'
    assert gs2.equips.value == ['冶金炉', '量产型装甲']
    # 目标坐标不在表
    gs3 = _seed_gs(owned=['冶金炉', '量产型装甲'],
                   xy={'冶金炉': [_TOOL_XY], '量产型装甲': [(1, 1)]},
                   front_units=[unit])
    outcome3 = report_action_furnace_use_param(
        gs3, _furnace_equip(tgt_xy=(9, 9)), _SIG, rng=random.Random(7))
    assert outcome3.applied is False
    assert outcome3.reason == 'tool_target_xy_unresolved'
    assert gs3.equips.value == ['冶金炉', '量产型装甲']


def test_furnace_equip_name_fields_zero_consumption(
        aligned_categories) -> None:
    """名称零消费锁测:同坐标 × item_name 三变体(含与反查产物不同的名)
    → 记账结果逐位相同。"""
    snapshots = []
    for item_name in ('', '折叠小刀', '量产型装甲'):
        gs = _seed_gs(owned=['冶金炉', '量产型装甲'],
                      xy={'冶金炉': [_TOOL_XY], '量产型装甲': [_TGT_XY]},
                      front_units=[Unit(char_id='罗刹', star=2, equips=[])])
        outcome = report_action_furnace_use_param(
            gs, _furnace_equip(item_name=item_name), _SIG,
            rng=random.Random(7))
        assert outcome.applied is True
        snapshots.append(list(gs.equips.value))
    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert '冶金炉' not in snapshots[0] and '量产型装甲' not in snapshots[0]


def test_furnace_equip_stale_window_violation_raises(
        aligned_categories) -> None:
    """禁消费窗口违反:伴随域含坐标、名单缺反查产物 → 严格移除抛
    ValueError(零防御,防静默守卫洗错账)。"""
    unit = Unit(char_id='罗刹', star=2, equips=[])
    gs = _seed_gs(owned=['冶金炉'],
                  xy={'冶金炉': [_TOOL_XY], '量产型装甲': [_TGT_XY]},
                  front_units=[unit])
    with pytest.raises(ValueError):
        report_action_furnace_use_param(
            gs, _furnace_equip(), _SIG, rng=random.Random(7))


def test_furnace_char_mixed_semantics_lock(aligned_categories) -> None:
    """混合语义锁测(§3.3 两族边界):工具端(反查产物)缺席名单 →
    ValueError 严格;穿戴件端(状态推导名)缺席名单 → _remove_one 容错
    零移除不抛。"""
    # 工具端缺席(owned 无冶金炉)→ ValueError
    gs = _seed_gs(owned=['折叠小刀'],
                  xy={'冶金炉': [_TOOL_XY]},
                  front_units=[Unit(char_id='罗刹', star=2,
                                    equips=['量产型装甲'])])
    with pytest.raises(ValueError):
        report_action_furnace_use_param(
            gs, _furnace_char(), _SIG, rng=random.Random(7))
    # 穿戴件端缺席(owned 有工具、无穿戴件名)→ 容错零移除不抛
    gs2 = _seed_gs(owned=['冶金炉'],
                   xy={'冶金炉': [_TOOL_XY]},
                   front_units=[Unit(char_id='罗刹', star=2,
                                     equips=['折叠小刀'])])
    outcome = report_action_furnace_use_param(
        gs2, _furnace_char(), _SIG, rng=random.Random(7))
    assert outcome.applied is True
    new_inv = gs2.equips.value
    assert '冶金炉' not in new_inv and '折叠小刀' not in new_inv
    assert len(new_inv) == 1   # 穿戴件采样替换件(名单原缺该名 = 容错跳移除)
    # 行域穿戴清空照写
    assert gs2.deployed.value.front_slots[0].equips == []


def test_wrench_consume_removes_resolved_tool() -> None:
    """拆装扳手(consume=True)反查命中:移除反查产物 + 追加穿戴件 +
    行域清空(两笔 logic)。"""
    unit = Unit(char_id='罗刹', star=2, equips=['折叠小刀', '量产型装甲'])
    gs = _seed_gs(owned=['拆装扳手'],
                  xy={'拆装扳手': [_TOOL_XY]},
                  front_units=[unit])
    param = CwActionWrenchUseParam(tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1],
                                   row='front', slot=1, char_name='罗刹')
    outcome = report_action_wrench_use_param(gs, param, _SIG)
    assert outcome.applied is True
    assert gs.equips.value == ['折叠小刀', '量产型装甲']   # 工具已移除
    assert gs.deployed.value.front_slots[0].equips == []   # 行域清空


def test_precision_wrench_keeps_tool_and_exempt_from_reject() -> None:
    """精密扳手(consume=False):不移除工具;源键反查不到不拒单——穿戴件
    追加与行域清空照写,evidence 含 tool_xy_unresolved 形态注记(豁免
    语义锁测)。"""
    unit = Unit(char_id='罗刹', star=2, equips=['折叠小刀'])
    gs = _seed_gs(owned=['量产型装甲'],
                  xy={'冶金炉': [(1, 1)]},   # 精密扳手坐标不在表 → 反查不到
                  front_units=[unit])
    param = CwActionPrecisionWrenchUseParam(
        tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1], row='front', slot=1,
        char_name='罗刹')
    outcome = report_action_precision_wrench_use_param(gs, param, _SIG)
    assert outcome.applied is True   # 豁免不拒单
    assert gs.equips.value == ['量产型装甲', '折叠小刀']   # 工具不动,穿戴件回区
    assert gs.equips.evidence is not None
    assert 'tool_xy_unresolved' in gs.equips.evidence
    assert gs.deployed.value.front_slots[0].equips == []


def test_wrench_resolve_miss_split_by_consume() -> None:
    """源键反查不到按 consume 分裂:拆装扳手 → tool_xy_unresolved 拒单
    零写;精密扳手 → 豁免照写(见上测);拆装扳手命中零写断言在此。"""
    unit = Unit(char_id='罗刹', star=2, equips=['折叠小刀'])
    gs = _seed_gs(owned=['拆装扳手'], xy={'拆装扳手': [(1, 1)]},
                  front_units=[unit])
    param = CwActionWrenchUseParam(tool_cx=(9), tool_cy=(9),
                                   row='front', slot=1)
    outcome = report_action_wrench_use_param(gs, param, _SIG)
    assert outcome.applied is False
    assert outcome.reason == 'tool_xy_unresolved'
    assert gs.equips.value == ['拆装扳手']   # 拒单零写
    assert gs.deployed.value.front_slots[0].equips == ['折叠小刀']


def test_slot_target_missing_rejects_upgraded() -> None:
    """槽位解析升格锁测:越界/空槽 → tool_target_unit_missing
    applied=False 拒单(原 applied=True 缺陷留存退役)。"""
    unit = Unit(char_id='罗刹', star=2, equips=['折叠小刀'])
    gs = _seed_gs(owned=['拆装扳手'],
                  xy={'拆装扳手': [_TOOL_XY]},
                  front_units=[unit])
    # slot 越界(前排定长 4)
    bad = CwActionWrenchUseParam(tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1],
                                 row='front', slot=9)
    outcome = report_action_wrench_use_param(gs, bad, _SIG)
    assert outcome.applied is False
    assert outcome.reason == 'tool_target_unit_missing'
    assert gs.equips.value == ['拆装扳手']
    # 空槽(slot=2 槽位无人)
    empty = CwActionWrenchUseParam(tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1],
                                   row='front', slot=2)
    outcome2 = report_action_wrench_use_param(gs, empty, _SIG)
    assert outcome2.applied is False
    assert outcome2.reason == 'tool_target_unit_missing'
    assert gs.deployed.value.front_slots[0].equips == ['折叠小刀']


def test_projector_cost_gate_zero_write_unchanged() -> None:
    """投影仪费用门超门(希露瓦 4 费 > 门 3)→ 零写分支不变
    (applied=True 保留,bug 面失败安全语义)。"""
    unit = Unit(char_id='希露瓦', star=2, equips=[])
    gs = _seed_gs(owned=['员工投影仪'],
                  xy={'员工投影仪': [_TOOL_XY]},
                  front_units=[unit])
    param = CwActionStaffProjectorUseParam(
        tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1], row='front', slot=1)
    outcome = report_action_staff_projector_use_param(gs, param, _SIG)
    assert outcome.applied is True
    assert outcome.reason == 'projector_cost_gate'
    assert gs.equips.value == ['员工投影仪']   # 零写


def test_projector_hit_removes_tool_and_gain_walks_chain() -> None:
    """投影仪反查命中(罗刹 3 费 ≤ 门):反查产物严格移除工具 +
    gain_character 走链(复制落备战空槽)。"""
    unit = Unit(char_id='罗刹', star=2, equips=[])
    gs = _seed_gs(owned=['员工投影仪'],
                  xy={'员工投影仪': [_TOOL_XY]},
                  front_units=[unit],
                  bench_slots=[BenchSlot() for _ in range(9)])
    param = CwActionStaffProjectorUseParam(
        tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1], row='front', slot=1)
    outcome = report_action_staff_projector_use_param(gs, param, _SIG)
    assert outcome.applied is True
    assert 'projector_copied' in outcome.reason
    assert gs.equips.value == []   # 反查产物严格移除工具
    landed = gs.bench.value.slots[0]
    assert landed.kind == 'unit' and landed.unit.char_id == '罗刹'


def test_projector_perfect_no_gate_and_tool_reject() -> None:
    """完美投影仪无费用门;源键反查不到 → tool_xy_unresolved 拒单零写。"""
    unit = Unit(char_id='希露瓦', star=2, equips=[])
    gs = _seed_gs(owned=['完美投影仪'], xy={'完美投影仪': [_TOOL_XY]},
                  front_units=[unit],
                  bench_slots=[BenchSlot() for _ in range(9)])
    param = CwActionPerfectProjectorUseParam(
        tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1], row='front', slot=1)
    outcome = report_action_perfect_projector_use_param(gs, param, _SIG)
    assert outcome.applied is True
    assert 'projector_copied' in outcome.reason   # 4 费无门
    assert gs.equips.value == []
    # 反查不到 → 拒单
    gs2 = _seed_gs(owned=['完美投影仪'], xy={'完美投影仪': [_TOOL_XY]},
                   front_units=[unit],
                   bench_slots=[BenchSlot() for _ in range(9)])
    param2 = CwActionPerfectProjectorUseParam(
        tool_cx=9, tool_cy=9, row='front', slot=1)
    outcome2 = report_action_perfect_projector_use_param(gs2, param2, _SIG)
    assert outcome2.applied is False
    assert outcome2.reason == 'tool_xy_unresolved'
    assert gs2.equips.value == ['完美投影仪']


def test_privilege_card_equip_transform_by_resolution() -> None:
    """特权卡 equip 分支反查改造回归:双键反查 → 严格移除工具 ∧ 反查产物
    →·特权名替换(变换同笔);evidence 含反查产物名。"""
    gs = _seed_gs(owned=['特权赋予卡', '武器大师', '折叠小刀'],
                  xy={'特权赋予卡': [_TOOL_XY], '武器大师': [_TGT_XY]},
                  front_units=[Unit(char_id='罗刹', star=2, equips=[])])
    outcome = report_action_privilege_card_use_param(gs, _priv_equip(), _SIG)
    assert outcome.applied is True
    assert gs.equips.value == ['武器大师·特权', '折叠小刀']
    assert '武器大师>武器大师·特权' in (gs.equips.evidence or '')


def test_privilege_card_resolve_miss_rejects() -> None:
    """特权卡反查不到:目标键 → tool_target_xy_unresolved;源键 →
    tool_xy_unresolved;均零写(名称在库检查 privilege_target_missing
    退役回归)。"""
    unit = Unit(char_id='罗刹', star=2, equips=[])
    gs = _seed_gs(owned=['特权赋予卡', '武器大师'],
                  xy={'特权赋予卡': [_TOOL_XY], '武器大师': [(1, 1)]},
                  front_units=[unit])
    outcome = report_action_privilege_card_use_param(
        gs, _priv_equip(tgt_xy=(9, 9)), _SIG)
    assert outcome.applied is False
    assert outcome.reason == 'tool_target_xy_unresolved'
    assert gs.equips.value == ['特权赋予卡', '武器大师']
    gs2 = _seed_gs(owned=['特权赋予卡', '武器大师'],
                   xy={'特权赋予卡': [(1, 1)], '武器大师': [_TGT_XY]},
                   front_units=[unit])
    outcome2 = report_action_privilege_card_use_param(
        gs2, _priv_equip(tool_xy=(9, 9)), _SIG)
    assert outcome2.applied is False
    assert outcome2.reason == 'tool_xy_unresolved'
    assert gs2.equips.value == ['特权赋予卡', '武器大师']


def test_privilege_char_branch_fail_closed_unchanged() -> None:
    """特权卡 char 分支 fail-closed 零写不变(用户裁定 2026-09-21 语义)。"""
    gs = _seed_gs(owned=['特权赋予卡'], xy={'特权赋予卡': [_TOOL_XY]},
                  front_units=[Unit(char_id='罗刹', star=2, equips=[])])
    param = CwActionPrivilegeCardUseParam(
        target_kind='char', tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1],
        row='front', slot=1)
    outcome = report_action_privilege_card_use_param(gs, param, _SIG)
    assert outcome.applied is True
    assert outcome.reason == 'privilege_worn_unsupported'
    assert gs.equips.value == ['特权赋予卡']   # 零写


def test_lucky_token_zero_write_unchanged() -> None:
    """令牌零写留存证据不变(永不发出面;反查不适用)。"""
    gs = _seed_gs(owned=['好运令牌'], xy={'好运令牌': [_TOOL_XY]},
                  front_units=[Unit(char_id='罗刹', star=2, equips=[])])
    param = CwActionLuckyTokenUseParam(
        tool_cx=_TOOL_XY[0], tool_cy=_TOOL_XY[1], row='front', slot=1)
    outcome = report_action_lucky_token_use_param(gs, param, _SIG)
    assert outcome.applied is True
    assert outcome.reason == 'token_not_admitted'
    assert gs.equips.value == ['好运令牌']   # 零写


def test_furnace_char_out_of_scope_kept_unchanged(
        aligned_categories, monkeypatch) -> None:
    """越白名单穿戴件保留 + 聚合留存证据(既有行为回归;键源 = 反查产物
    后的穿戴采样链)。特権件 category='特权装备' 越白名单 → 原样保留。"""
    gs = _seed_gs(owned=['冶金炉', '武器大师'],
                  xy={'冶金炉': [_TOOL_XY]},
                  front_units=[Unit(char_id='罗刹', star=2,
                                    equips=['武器大师·特权'])])
    outcome = report_action_furnace_use_param(
        gs, _furnace_char(), _SIG, rng=random.Random(7))
    assert outcome.applied is True
    assert '冶金炉' not in gs.equips.value   # 工具端严格移除照走
    assert '武器大师·特权' in gs.equips.value   # 越白名单保留原样
