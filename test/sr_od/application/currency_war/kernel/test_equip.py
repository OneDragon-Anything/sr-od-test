"""装备域锁(机制主题文件;穿戴计划 → 合并继承 → 可穿性门全链)。

被锁机制(按节):
- **穿戴计划容器换源**(M7 ``_build_equip_wear_plan`` 四路输入全面换
  容器 game state 读口):黑盒区分(无黑板帧照常产出)+ fail 门方向
  (owned/occupied 未观察分别保守关);
- **merge 装备继承**(语义源 = merge_mechanics):同名同星 3 合 1,
  素材装备按扫描序继承到载体(场上载体优先;载体自有在前),素材槽
  清空——重写容器形状时的不变量哨兵;
- **银狼专属装备可穿性门**(2026-09-18 用户定谳,10 件,白名单 =
  银狼 + 银狼LV.999;机制正本 =
  docs/game/currency_war/research/equipment_mechanics.md「银狼专属
  装备」节;事故 = run_20260918_075416 分身墨镜Max 拖给丹恒·饮月
  静默不生效 → 装备滞留 owned → 安灯停局):登记完整性 / 白名单
  真值表 / 分配器消费位排除 / 回退帧 fail-closed / 注册表互检。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp,
    cw4_session,
)

from sr_od.application.currency_war.data.cw_equipment_wear_rules_data import (
    ITEM_WEAR_GATES,
    YINLANG_WEAR_ALLOWLIST,
    check_equipment_wear_rule_coverage,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    _wearable_gate_ok,
    equip_allocation,
)
from sr_od.application.currency_war.kernel.cw_equip_wear_plan import (
    _build_equip_wear_plan,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    ChannelSig,
    GameState,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    _merge_bench,
)

_SIG = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')

# ============================================================ 穿戴计划容器换源(fail 门方向)


def _observe_equips(session, owned, occupied):
    """按容器键形态写装备两域(写端生产键 = 'front:1' 形态字符串)。"""
    gs = game_state_of(session)
    gs.observe(gs.equips, list(owned), sig=_SIG)
    gs.observe(gs.occupied_equips,
               {f'{row}:{int(slot)}': list(names)
                for (row, slot), names in occupied.items()},
               sig=_SIG)
    return gs


def test_m7_reads_container_without_prep_obs():
    """黑盒区分锁:无黑板帧 + 容器三域在 → M7 正常进入判据链
    (fail_reason 为空 = 四路输入全部读通;旧实现此处 fail 观察帧缺失)。"""
    session = cw4_session(cw4_comp())
    gs = _observe_equips(session, owned=['星币收集器'],
                         occupied={('front', 1): ['星币收集器']})
    gs.observe(gs.back_layout, 6, sig=_SIG)
    ret = _build_equip_wear_plan(session)
    assert ret.fail_reason == '', f'四路输入应全部读通,实际 fail: {ret.fail_reason}'
    # deployed 空表 → 合法的 front_only 回退分支(身份读失败回退,与
    # cw_prep_actions.EquipPlanBuild.branch 申报一致);m7 = 角色级分配。
    assert ret.branch in ('m7', 'front_only')


def test_m7_fail_gate_owned_unobserved():
    """fail 门:owned 域未观察(None) → 保守关,fail_reason 指向 owned。
    (直构容器承载:session 容器冷建即种子空表,None 档仅直构域可达。)"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.occupied_equips, {'front:1': ['x']}, sig=_SIG)
    ret = _build_equip_wear_plan(gs)
    assert 'owned' in ret.fail_reason


def test_m7_fail_gate_occupied_unobserved():
    """fail 门:occupied 域未观察(None) → 保守关,fail_reason 指向
    occupied。(直构容器承载,理由同 owned 门锁。)"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, ['星币收集器'], sig=_SIG)
    ret = _build_equip_wear_plan(gs)
    assert 'occupied' in ret.fail_reason


# ============================================================ merge 装备继承


def _char(slot: int, star: int, char_id: str = '阿格莱雅',
          equips: list[str] | None = None) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star,
                                            equips=list(equips or [])))


def test_bench_merge_inherits_material_equips_to_carrier() -> None:
    """bench 内 3 合 1:素材装备按扫描序继承到载体,素材槽清空。"""
    bench = [_char(1, 1, equips=['a']),
             _char(2, 1, equips=['b']),
             _char(3, 1)]
    _merge_bench(bench, None)
    carrier = bench[0]
    assert carrier is not None and carrier.unit.star == 2, '载体升 2★'
    assert carrier.unit.equips == ['a', 'b'], \
        f'素材装备继承到载体,实得 {carrier.unit.equips}'
    assert bench[1] is None and bench[2] is None, '素材槽清空'


def test_merge_keeps_carrier_own_equips_before_inherited() -> None:
    """载体自有装备保留在前,素材装备追加在后(顺序契约)。"""
    bench = [_char(1, 1, equips=['x']),
             _char(2, 1, equips=['a']),
             _char(3, 1, equips=['b'])]
    _merge_bench(bench, None)
    assert bench[0].unit.equips == ['x', 'a', 'b'], \
        f'自有在前/继承在后,实得 {bench[0].unit.equips}'


def test_deployed_carrier_inherits_bench_material_equips() -> None:
    """载体在场上:bench 素材装备继承到场上载体,素材槽清空、
    载体升星(装备跟人走,不掉落在 bench)。"""
    bench = [_char(1, 1, equips=['a']),
             _char(2, 1, equips=['b'])]
    deployed = [Unit(char_id='阿格莱雅', star=1, equips=['x'])]
    _merge_bench(bench, deployed)
    carrier = deployed[0]
    assert carrier is not None and carrier.star == 2, '场上载体升 2★'
    assert carrier.equips == ['x', 'a', 'b'], \
        f'载体自有 + bench 素材装备,实得 {carrier.equips}'
    assert bench[0] is None and bench[1] is None, 'bench 素材槽清空'


# ============================================================ 银狼专属装备可穿性门

#: 口述 10 件清单(2026-09-18 用户定谳;测试锚 = 登记的完整性,防漏登/多登)。
ORAL_EXCLUSIVE_TEN = frozenset({
    '分身墨镜', '分身墨镜Max',
    '数据拷贝仪', '数据拷贝仪Max', '数据拷贝仪Pro',
    '病毒防火墙', '病毒防火墙Max',
    '破解芯片', '管理员手套ProMax', '欢愉卡带Max',
})

#: 白名单外代表角色;丹恒·饮月 = run_20260918_075416 事故角色。
_OTHER_CHARS = ('丹恒·饮月', '希儿')


def test_gate_table_matches_oral_list():
    """登记完整性:件级门恰好 = 口述 10 件,每件白名单 = 银狼两角色单一源。"""
    assert set(ITEM_WEAR_GATES) == ORAL_EXCLUSIVE_TEN
    for gate in ITEM_WEAR_GATES.values():
        assert gate == YINLANG_WEAR_ALLOWLIST


def test_allowlist_two_chars_wearable():
    """白名单两角色全部可穿(定谳:「两个都行」,非仅银狼LV.999)。"""
    for item in ORAL_EXCLUSIVE_TEN:
        for char in ('银狼', '银狼LV.999'):
            assert _wearable_gate_ok([], char, item) is True


def test_non_allowlist_chars_rejected():
    """白名单外角色全部被拒(游戏侧 = 拖拽静默不生效,分配前排除)。"""
    for item in ORAL_EXCLUSIVE_TEN:
        for char in _OTHER_CHARS:
            assert _wearable_gate_ok([], char, item) is False


def test_unregistered_items_unaffected():
    """门只辖登记键:特殊类非专属件(垃圾袋)恒可穿;骇客类非专属件
    (扑满病毒)走类别门定谳白名单(银狼系放行/他人拒)。"""
    assert _wearable_gate_ok([], '丹恒·饮月', '垃圾袋') is True
    assert _wearable_gate_ok([], '银狼', '垃圾袋') is True
    assert _wearable_gate_ok([], '银狼', '扑满病毒') is True
    assert _wearable_gate_ok([], '银狼LV.999', '扑满病毒') is True
    assert _wearable_gate_ok([], '希儿', '扑满病毒') is False


def test_allocator_excludes_illegal_pair():
    """事故路径锁:comp=None 兜底轮转也不把分身墨镜Max 发给丹恒·饮月
    (run_075416:该对进过穿戴规划 → 拖拽静默不生效 → 安灯停局);同池
    普通件(垃圾袋)照常分配,专属件留 owned。
    载体 = 上阵视图 DeployedView(位置 = 子表下标派生)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        Unit,
        deployed_view_sequential,
    )
    view = deployed_view_sequential(
        [Unit(char_id='丹恒·饮月', star=2, equips=[])], [])
    out = equip_allocation(None, view,
                           ['分身墨镜Max', '垃圾袋'], occupied={})
    assert ('丹恒·饮月', '分身墨镜Max') not in out
    assert ('丹恒·饮月', '垃圾袋') in out


def test_front_only_fallback_excludes_gated_items():
    """回退帧门锁(fail-closed):身份读失败帧(deployed 空 → front_only
    回退分支)专属件在 owned → 回退计划不含专属件(件滞留 owned,不发
    拖拽);同池无门件照常入计划(行为不变);空栏前置件(worn=[] 无
    信息恒过)也入计划 = 回退帧只补 W3 有效辖域。"""
    session = cw4_session(cw4_comp())
    gs = game_state_of(session)
    gs.observe(gs.equips, ['分身墨镜Max', '扑满病毒', '掩体生成枪', '随便骰子'],
               sig=_SIG)
    gs.observe(gs.occupied_equips, {}, sig=_SIG)
    ret = _build_equip_wear_plan(session)
    assert ret.branch == 'front_only'
    planned = {s.item_name for s in ret.steps}
    assert planned == {'掩体生成枪', '随便骰子'}
    assert set(ret.owned_wearable_names) == {'掩体生成枪', '随便骰子'}
    for s in ret.steps:
        assert s.char_name == ''
        assert s.row == 'front'
        assert 1 <= s.slot <= 4


def test_wear_rule_coverage_zero_warnings():
    """互检全量健康:件级门孤儿检测接入后,注册表 ↔ 结构化载体零缺口。"""
    assert check_equipment_wear_rule_coverage() == []


def test_orphan_gate_entry_and_bad_char_warned(monkeypatch):
    """门孤儿显警:条目名不在注册表 / 白名单角色名不在角色注册表
    (注册表/角色表重写改名后条目静默失效的防线)。"""
    monkeypatch.setitem(ITEM_WEAR_GATES, '幽灵装备',
                        frozenset({'银狼', '银狼不存在'}))
    warnings = check_equipment_wear_rule_coverage()
    assert any('幽灵装备' in w and '孤儿条目' in w for w in warnings)
    assert any('银狼不存在' in w for w in warnings)
