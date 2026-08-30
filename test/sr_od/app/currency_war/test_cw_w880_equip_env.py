# -*- coding: utf-8 -*-
"""W880 装备穿满族 fill-to-3 量变体锁组(策略开关生命周期第 1 态)。

机制真值(单一源 = data/affix_effects_data.AFFIX_EFFECTS 游戏内原文实采):
- 软弱无力:「没有穿戴3件装备的角色及其忆灵,造成的伤害为原伤害的80%.」
  —— 判据 = 角色级穿满数(3 件),分配集中度成为决策变量;
- 额外打击:「我方队员每有1个空缺装备栏,受到敌人攻击后,额外受到本次攻击
  伤害8%的真实伤害。」—— 承伤侧镜像,凑 3 优先对象 = 前排(受击高位)先于
  输出位。

锁面(设计单一源 = .debug/temp/currency_war/w880_equip_env_design/DESIGN.md
§2/§3.1/§4,实现 = kernel/cw_equip_env.py):
1. 机制真值在注册表(禁第二数据源)+ registry 开关默认关(生命周期第 1 态)
   + 阈值常量 3;
2. 环境判据(任一词缀 contains;读不到 = 安全默认不启用;信号单源读取点);
3. 集中度轴(凑 3 优先于均匀分散:已穿多者先);
4. 承伤序轴(前排先于后排,同位级下 core 先);
5. 保护集(key_equips 与主线需求组件不可挪;基础件过防误合成守卫;成员无损);
6. 门序零漂移(开关关/环境不在场/hold 在场 → 基分配原样);
7. 死映射防线(两词缀未持 comp 携带 tag 核查前,禁入 AFFIX_MECHANIC_MAP,
   W872/W875 范式——设计 §3.4 挂账)。

⚠️ 验证状态:本锁组**尚未运行**(离线落码批禁跑 pytest;恢复后需跑:
本文件 + cw_quick L1 + test_cw_w861/w607 迁移邻接回归)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.affix_effects_data import (
    AFFIX_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_equip_env import (
    EQUIP_ENV_FILL3_AFFIXES,
    EquipEnvSignals,
    apply_fill3,
    build_equip_env_signals,
    fill3_allocation,
    fill3_env_active,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar


def _mkcomp(key_equips: list[str], cores: list[str]) -> Comp:
    return Comp(name='伪comp', factions=['追击'], core_chars=cores,
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=key_equips)


_COMP = _mkcomp(['反重力皮靴', '火力风暴潮'], ['阿雅'])
_KEYS = {'反重力皮靴', '火力风暴潮'}


def _sig(affixes: list[str] | None) -> EquipEnvSignals:
    return build_equip_env_signals(
        SimpleNamespace(enemy_affixes=affixes or [], plane=1, round_num=3))


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
    assert getattr(DEFAULT_REGISTRY, 'equip_env_fill3_enabled') is False
    assert getattr(DEFAULT_REGISTRY, 'equip_fill_target') == 3


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
    s2 = build_equip_env_signals(SimpleNamespace())
    assert s2.enemy_affixes == frozenset()


# ===== 3. 集中度轴(软弱无力:凑 3 优先于均匀分散)=====

_DEP2 = [BenchChar(slot=1, char_id='甲', position_pref='back'),
         BenchChar(slot=2, char_id='乙', position_pref='back')]
_OCC2 = {('back', 1): ['以太钻头'], ('back', 2): ['以太钻头', '和平手枪']}


def test_concentration_axis_prefers_closest_to_full() -> None:
    """散件改派给已穿件数多者(2 件者先凑满 3),不做均匀分散。"""
    new, moved = apply_fill3([('甲', '幸运星')], _DEP2, _OCC2, _COMP)
    assert moved == 1 and new == [('乙', '幸运星')]


# ===== 4. 承伤序轴(额外打击:前排/受击高位先于输出位)=====

_DEP3 = [BenchChar(slot=1, char_id='三月七', position_pref='front'),
         BenchChar(slot=2, char_id='阿雅', position_pref='back'),
         BenchChar(slot=3, char_id='丹恒', position_pref='back')]
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
    """同位级(同排)下输出核心先于非 core(软弱无力罚输出 80% 最实)。"""
    dep = [BenchChar(slot=1, char_id='阿雅', position_pref='back'),
           BenchChar(slot=2, char_id='丹恒', position_pref='back')]
    occ = {('back', 1): ['以太钻头', '和平手枪'],
           ('back', 2): ['以太钻头', '和平手枪']}
    new, moved = apply_fill3([('丹恒', '幸运星')], dep, occ, _COMP)
    assert moved == 1 and new == [('阿雅', '幸运星')]


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
    dep = [BenchChar(slot=1, char_id='阿雅', position_pref='back')]
    # 阿雅已穿 a;改派 b 到阿雅会合成出非 key 产物 → 不改派(件留原 char)
    pair = next(((a, b) for a in ['光能电池', '和平手枪', '幸运星', '量产型装甲']
                 for b in ['光能电池', '和平手枪', '幸运星', '量产型装甲']
                 if a != b and synthesize_target(a, b) is not None
                 and synthesize_target(a, b) not in _COMP.key_equips), None)
    if pair is None:
        return  # 图谱无此形态则锁退化(不构造伪数据)
    a, b = pair
    occ = {('back', 1): [a]}
    base = [('甲', b), ('乙', '幸运星')]
    new, _ = apply_fill3(base, [dep[0],
                                BenchChar(slot=2, char_id='甲', position_pref='back'),
                                BenchChar(slot=3, char_id='乙', position_pref='back')],
                         {('back', 2): [], ('back', 3): []}, _COMP)
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
    reg = SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3)
    out, action = fill3_allocation(reg, _COMP, _DEP3, _base(),
                                   _OCC3, _sig([]), hold_active=False)
    assert action == 'inactive' and out == _base()


def test_hold_active_blocks_fill() -> None:
    """过渡期 hold(非生锈豁免态)优先:hold 在场 → fill 不激活(防线③)。"""
    reg = SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3)
    out, action = fill3_allocation(reg, _COMP, _DEP3, _base(),
                                   _OCC3, _sig(['额外打击']), hold_active=True)
    assert action == 'hold_active' and out == _base()


def test_no_gap_when_all_full_or_nothing_movable() -> None:
    """全员已满 3 / 可改派散件为空 → no_gap,分配原样。"""
    reg = SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3)
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
    reg = SimpleNamespace(equip_env_fill3_enabled=True, equip_fill_target=3)
    out, action = fill3_allocation(reg, _COMP, _DEP3, _base(), _OCC3,
                                   _sig(['额外打击']), hold_active=False)
    assert action == 'filled:1'
    assert out[0] == ('三月七', '幸运星')


def test_comp_none_conservative_noop() -> None:
    """comp 缺失(无身份信息,保护集不可判)→ 原样返回(保守降级)。"""
    new, moved = apply_fill3(_base(), _DEP3, _OCC3, None)
    assert moved == 0 and new == _base()
