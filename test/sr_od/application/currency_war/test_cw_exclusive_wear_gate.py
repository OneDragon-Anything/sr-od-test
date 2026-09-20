"""银狼专属装备可穿性门锁(2026-09-18 用户定谳;10 件,白名单 = 银狼 + 银狼LV.999)。

机制正本 = docs/game/currency_war/research/equipment_mechanics.md「银狼专属
装备」节;数据单一源 = data/cw_equipment_wear_rules_data.py(ITEM_WEAR_GATES
件级门 + CATEGORY_WEAR_GATES 骇客类别门);消费位 =
kernel/cw_comps._wearable_gate_ok W3(equip_allocation 分配前排除)。

事故背景 = run_20260918_075416:分身墨镜Max 被穿戴规划发给丹恒·饮月,拖拽
静默不生效 → 装备滞留 owned → equips 实读失配安灯停局。本批后该对在分配器
候选过滤即被排除(件留 owned,不发拖拽)。

锁的六件事:
1. 登记完整性:件级门恰好 = 口述 10 件清单,白名单恒 = 银狼两角色;
2. 白名单放行:10 件 × {银狼, 银狼LV.999} 全部可穿;
3. 白名单外拒绝:10 件 × 普通角色全部被拒(拖错角色 = 游戏静默拒);
4. 未登记件不受影响:特殊类非专属件(垃圾袋)恒可穿;骇客类非专属件
   (扑满病毒)走类别门定谳白名单;
5. 分配器消费位:comp=None 兜底轮转也不把专属件发给白名单外角色(事故
   路径分配前排除);互检:全量健康零警告 + 孤儿条目/错字角色显警;
6. 回退帧门锁:身份读失败帧(front_only 回退分支)专属件在 owned →
   计划不含专属件(fail-closed,件滞留 owned),无门件照常入计划。
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
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)

#: 口述 10 件清单(2026-09-18 用户定谳;测试锚 = 本批登记的完整性,防漏登/多登)。
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
    普通件(垃圾袋)照常分配,专属件留 owned。"""
    deployed = [BenchChar(slot=1, char_id='丹恒·饮月', star=2, position_pref='front')]
    out = equip_allocation(None, deployed, ['分身墨镜Max', '垃圾袋'], occupied={})
    assert ('丹恒·饮月', '分身墨镜Max') not in out
    assert ('丹恒·饮月', '垃圾袋') in out


_OBS_SIG = ChannelSig(family='obs', actor='synthesize_from_game_state',
                      mode='synthesized')


def test_front_only_fallback_excludes_gated_items():
    """回退帧门锁(fail-closed):身份读失败帧(deployed 空 → front_only
    回退分支)专属件在 owned → 回退计划不含专属件(件滞留 owned,不发
    拖拽);同池无门件照常入计划(行为不变);空栏前置件(worn=[] 无
    信息恒过)也入计划 = 回退帧只补 W3 有效辖域。"""
    session = cw4_session(cw4_comp())
    gs = game_state_of(session)
    gs.observe(gs.equips, ['分身墨镜Max', '扑满病毒', '掩体生成枪', '随便骰子'],
               sig=_OBS_SIG)
    gs.observe(gs.occupied_equips, {}, sig=_OBS_SIG)
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
