# -*- coding: utf-8 -*-
"""变宝为废·牺牲合成先行锁组(策略开关生命周期第 1 态)。

机制真值(单一源 = data/affix_effects_data.AFFIX_EFFECTS['变宝为废'],
游戏内词缀效果原文实采):「每个位面开始时,首次合成的进阶装备会有 50%
的概率变成垃圾袋」——粒度 = 每位面各一次(P1/P2/P3 各自风险),产物 =
垃圾袋。对策(用户建议,ADR-0498)= 牺牲合成先行。

四面:
1. 环境判据(state.enemy_affixes contains;读不到=无环境,安全默认不启用);
2. 牺牲排序(sacrifice_first:牺牲对分配移到队首,先于高价值合成完成);
3. 无牺牲对推迟一帧(deferred:高价值完成件本帧不出分配;每位面预算=1,
   耗尽后原样放行=接受该位面 50% 垃圾化风险,防无限等);
4. 缺环境/开关关不启用(零漂移锚)+ 主线组件不当牺牲对(P14 定理 3)
   + 位面消耗记账(每面一次,跨面重置)。

⚠️ 验证状态:本锁组与 2026-09-11 位面粒度修正后的实现**尚未运行**
(用户指令暂停 pytest;恢复后需跑:本文件 + adr0293 普查 + 受影响
装备测试 8 文件 + cw_quick)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.affix_effects_data import (
    AFFIX_EFFECTS,
)
from sr_od.application.currency_war.data.cw_synthesis import (
    component_demand,
    recycle_qualified,
    synthesize_target,
)
from sr_od.application.currency_war.kernel.cw_junk_first import (
    JUNK_FIRST_AFFIX,
    JUNK_FIRST_DEFER_BUDGET,
    apply_junk_first,
    find_high_value_completions,
    find_sacrifice_pair,
    junk_first_allocation,
    junk_first_env_active,
    worn_basics_by_char,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar

# 阿雅需求线(w211 同例):key 组件 = 轮滑鞋×5 + 折叠小刀×1;
# 回收合格 = 以太钻头/光能电池/和平手枪/幸运星/生命之花/量产型装甲
_K_AYA = ['反重力皮靴', '反重力皮靴', '白昼·光速螺旋桨', '火力风暴潮']


def _mkcomp(key_equips: list[str], cores: list[str]):
    from sr_od.application.currency_war.kernel.cw_comps import Comp
    return Comp(name='伪comp', factions=['追击'], core_chars=cores,
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=key_equips)


def _aya_pair() -> tuple[str, str]:
    """阿雅回收合格集内一对真实互为配方的基础件(锁语义不锁具体对)。"""
    rq = sorted(recycle_qualified(_K_AYA))
    pair = next(((a, b) for a in rq for b in rq
                 if a != b and synthesize_target(a, b) is not None), None)
    assert pair is not None, '图谱前提:阿雅死库存内存在可配对'
    return pair


# ===== 1. 环境判据 =====

def test_env_active_contains() -> None:
    assert junk_first_env_active([JUNK_FIRST_AFFIX, '其他词缀'])
    assert junk_first_env_active(['其他词缀', JUNK_FIRST_AFFIX])


def test_env_inactive_defaults_safe() -> None:
    """读不到(空/None/其他词缀)= 无该环境 → 不启用(安全默认)。"""
    assert not junk_first_env_active([])
    assert not junk_first_env_active(None)
    assert not junk_first_env_active(['库藏生锈', '倒计时'])


# ===== 2. 牺牲排序(sacrifice_first)=====

def test_high_value_completion_detection() -> None:
    """core 已穿 轮滑鞋,本趟发 折叠小刀 → 完成高价值合成 火力风暴潮(∈key)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    worn = {'阿雅': ['轮滑鞋']}
    alloc = [('三月七', '以太钻头'), ('阿雅', '折叠小刀')]
    assert find_high_value_completions(alloc, worn, comp) == [1]


def test_sacrifice_pair_ordered_before_high_value() -> None:
    """牺牲对(死库存配方对,非 core 共位)两条分配移到队首——
    拖拽序 = 合成事件序,牺牲合成先消耗垃圾化,高价值合成免触发。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    a, b = _aya_pair()
    worn = {'阿雅': ['轮滑鞋']}
    alloc = [('阿雅', '折叠小刀'), ('三月七', a), ('三月七', b)]
    new_alloc, action = apply_junk_first(alloc, worn, comp, True, 1)
    assert action == 'sacrifice_first'
    assert new_alloc[0][1] in (a, b) and new_alloc[1][1] in (a, b), \
        f'牺牲对必须先于高价值合成: {new_alloc}'
    assert new_alloc[-1] == ('阿雅', '折叠小刀')
    assert sorted(map(tuple, new_alloc)) == sorted(map(tuple, alloc)), '成员无损'


def test_sacrifice_pair_with_worn_partner_moved_front() -> None:
    """对的一件已在前帧穿上(非 core),本趟只发另一件 → 该条分配移队首。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    a, b = _aya_pair()
    worn = {'阿雅': ['轮滑鞋'], '三月七': [a]}
    alloc = [('阿雅', '折叠小刀'), ('三月七', b)]
    new_alloc, action = apply_junk_first(alloc, worn, comp, True, 1)
    assert action == 'sacrifice_first'
    assert new_alloc == [('三月七', b), ('阿雅', '折叠小刀')]


def test_sacrifice_pair_rejects_mainline_components() -> None:
    """主线组件(需求向量内,非回收合格)不当牺牲对:绝对热量 = 光能电池+
    生命之花,都 ∈ 绝对热量需求 → 即便非 core 共位也不牺牲(不碰主线凑件)。"""
    comp = _mkcomp(['绝对热量'], ['飞霄'])
    demand = set(component_demand(['绝对热量']))
    assert {'光能电池', '生命之花'} <= demand
    worn = {'三月七': ['光能电池']}
    alloc = [('三月七', '生命之花')]
    assert find_sacrifice_pair(alloc, worn, comp) is None


# ===== 3. 无牺牲对推迟一帧 =====

def test_defer_without_sacrifice_pair() -> None:
    """无牺牲对 → 高价值完成件本帧不出分配(件留 owned 等死库存对)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    worn = {'阿雅': ['轮滑鞋']}
    alloc = [('阿雅', '折叠小刀')]
    new_alloc, action = apply_junk_first(alloc, worn, comp, True, 1)
    assert action == 'deferred' and new_alloc == []


def test_defer_budget_exhausted_releases() -> None:
    """预算耗尽(推迟一帧上限)→ 原样放行(接受垃圾化风险,防无限等)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    worn = {'阿雅': ['轮滑鞋']}
    alloc = [('阿雅', '折叠小刀')]
    new_alloc, action = apply_junk_first(alloc, worn, comp, True, 0)
    assert action == 'budget_exhausted' and new_alloc == alloc


def test_defer_budget_per_plane_and_mechanism_truth_in_registry() -> None:
    """机制真值单一源锁:词缀效果在 affix_effects_data 注册表内为游戏原文
    (每位面首次进阶合成 / 50% / 垃圾袋)——禁第二数据源;推迟预算=每位面
    1 帧(50% × 进阶件损失 ≫ 一帧推迟成本,预算只防无限推迟)。"""
    effect = AFFIX_EFFECTS['变宝为废']
    assert '每个位面开始时' in effect and '首次合成' in effect
    assert '50%' in effect and '垃圾袋' in effect
    assert JUNK_FIRST_DEFER_BUDGET == 1


# ===== 4. 缺环境 / 开关关不启用(零漂移锚)=====

def _dep() -> list:
    return [BenchChar(slot=1, char_id='阿雅', position_pref='back'),
            BenchChar(slot=2, char_id='三月七', position_pref='front')]


def test_disabled_env_returns_base_alloc() -> None:
    """环境不在场:开关开也返回基分配(安全默认不启用)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    reg = SimpleNamespace(junk_first_sacrifice_enabled=True)
    sess = SimpleNamespace(junk_first_done_plane=None)
    a, b = _aya_pair()
    base = junk_first_allocation(sess, reg, comp, _dep(),
                                 [a, b, '轮滑鞋', '折叠小刀'], None, [])
    enabled = junk_first_allocation(sess, reg, comp, _dep(),
                                    [a, b, '轮滑鞋', '折叠小刀'], None,
                                    [JUNK_FIRST_AFFIX])
    assert base == enabled


def test_disabled_switch_zero_drift() -> None:
    """开关关(默认):环境在场也返回基分配 = equip_allocation 原语义(零漂移锚)。"""
    from sr_od.application.currency_war.kernel.cw_comps import equip_allocation
    comp = _mkcomp(_K_AYA, ['阿雅'])
    reg = SimpleNamespace(junk_first_sacrifice_enabled=False)
    sess = SimpleNamespace(junk_first_done_plane=None)
    a, b = _aya_pair()
    owned = [a, b, '轮滑鞋', '折叠小刀']
    got = junk_first_allocation(sess, reg, comp, _dep(), owned, None,
                                [JUNK_FIRST_AFFIX])
    assert got == equip_allocation(comp, _dep(), owned, None)


def test_registry_switch_defaults_off_lifecycle_state1() -> None:
    """开关默认关 = 生命周期第 1 态(落码默认关+开臂判据挂账,禁悬置):
    开臂判据=环境读取通道稳定+牺牲对识别可靠(阈值见 registry 字段注释)。"""
    import dataclasses
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
        DecisionV2Registry,
    )
    fld = {f.name: f for f in dataclasses.fields(DecisionV2Registry)}
    assert 'junk_first_sacrifice_enabled' in fld
    assert fld['junk_first_sacrifice_enabled'].default is False
    assert getattr(DEFAULT_REGISTRY, 'junk_first_sacrifice_enabled') is False


def _sess(plane: int | None) -> SimpleNamespace:
    """带 last_state.plane 的最小 session(位面消耗记账的宿主形态)。"""
    last = SimpleNamespace(plane=plane) if plane is not None else None
    return SimpleNamespace(last_state=last, junk_first_done_plane=None)


def test_wrapper_plane_consumption_once_per_plane() -> None:
    """位面消耗记账(机制=每位面首次合成各判定一次):
    P1 推迟一次后记账;同位面后续帧不再推迟(判定已消耗);
    进位面 2 → 风险窗口重开,可再推迟一次并记账 P2。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    reg = SimpleNamespace(junk_first_sacrifice_enabled=True)
    sess = _sess(1)
    got = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                {('back', 1): ['轮滑鞋']},
                                [JUNK_FIRST_AFFIX])
    assert got == [] and sess.junk_first_done_plane == 1
    got2 = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                 {('back', 1): ['轮滑鞋']},
                                 [JUNK_FIRST_AFFIX])
    assert got2 == [('阿雅', '折叠小刀')], '同位面判定已消耗,不再推迟'
    sess.last_state.plane = 2
    got3 = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                 {('back', 1): ['轮滑鞋']},
                                 [JUNK_FIRST_AFFIX])
    assert got3 == [] and sess.junk_first_done_plane == 2, \
        'P2 首次合成风险独立,推迟预算重开'


def test_wrapper_plane_unreadable_consumed_once() -> None:
    """位面读不到(None):首次动作后记哨兵,后续帧按已消耗降级
    (整局一次,防位面不可读时无限推迟)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    reg = SimpleNamespace(junk_first_sacrifice_enabled=True)
    sess = _sess(None)
    got = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                {('back', 1): ['轮滑鞋']},
                                [JUNK_FIRST_AFFIX])
    assert got == [] and sess.junk_first_done_plane == -1
    got2 = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                 {('back', 1): ['轮滑鞋']},
                                 [JUNK_FIRST_AFFIX])
    assert got2 == [('阿雅', '折叠小刀')], '哨兵后不再推迟'


def test_worn_basics_projection() -> None:
    """(row,slot) 占用 + deployed 身份 → 角色名已穿基础件投影(非基础件滤除)。"""
    dep = [BenchChar(slot=1, char_id='阿雅', position_pref='back')]
    worn = worn_basics_by_char(dep, {('back', 1): ['轮滑鞋', '火力风暴潮']})
    assert worn == {'阿雅': ['轮滑鞋']}
