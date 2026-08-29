# -*- coding: utf-8 -*-
"""W607 词缀消费面锁(H1 锁线环境判据 / H2② 生锈穿戴豁免 / H3 opening hold 收窄)。

设计出处:设计件「词缀消费面」.debug/temp/currency_war/w607_affix_consumption/DESIGN.md
§3(修法)+ §5(测试计划);决策记录=ADR-0461。词条语义出处见被测符号注释
(cw_comps.STRONG_ENV_MECHS / RUST_AFFIX_NAME / registry W607 字段块)。
三开关默认关=零漂移锚;本文件另锁「默认关=旧行为」与「H3 台账缺失降级=维持现状 hold」。
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    _line_env_qualified,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.operations.prep.equip_all import (
    _opening_hold_active,
    _rust_release_active,
)

_WANDI = '万敌单C'   # hp_charge_stack 累积型线(global_accumulators 注册,accumulator_family §4.1)
_SEELE = '希儿量子'   # 非累积型线(判据不辖,恒 None)


def _state(affixes: list[str], plane: int = 2, round_num: int = 1) -> GameState:
    st = GameState()
    st.plane = plane
    st.round_num = round_num
    st.enemy_affixes = list(affixes)
    return st


# ===== H1:_line_env_qualified 四态真值表 =====

def test_h1_non_accumulator_line_not_governed() -> None:
    """非累积型线 → None(判据不辖,资格面不变)。"""
    assert _line_env_qualified(_state(['净化身心']), _SEELE) is None


def test_h1_empty_affixes_missing_evidence() -> None:
    """词缀可信位缺失(空)→ None:不猜,放行(动态剔除同款)。"""
    assert _line_env_qualified(_state([]), _WANDI) is None


def test_h1_strong_env_hit() -> None:
    """强环境命中:正当防卫→反伤 / 忍无可忍→多段惩罚(accumulator_family §3)。"""
    assert _line_env_qualified(_state(['正当防卫']), _WANDI) is True
    assert _line_env_qualified(_state(['忍无可忍']), _WANDI) is True


def test_h1_adverse_or_unmapped_affix_miss() -> None:
    """环境不命中→False;未入 AFFIX_MECHANIC_MAP 的词缀(灼热轰炸)按不命中(宁缺勿错)。"""
    assert _line_env_qualified(_state(['净化身心']), _WANDI) is False
    assert _line_env_qualified(_state(['灼热轰炸']), _WANDI) is False


# ===== H1:锁线过滤(gate on/off × 环境)=====

def _wandi_visible_state(affixes: list[str]) -> GameState:
    st = _state(affixes)
    st.shop = [SimpleNamespace(name='万敌')]   # ③核心卡信号:意向核心可见
    return st


def test_h1_unconditional_adverse_env_holds_lock() -> None:
    """行为无条件化(W628 清偿):环境不命中 → 缓锁(判据恒在,无开关)。"""
    ist = update_intention(_wandi_visible_state(['净化身心']), IntentionState())
    assert ist.locked_comp == ''


def test_h1_strong_env_locks() -> None:
    """强环境命中 → 照常落锁(判据恒在,无开关)。"""
    ist = update_intention(_wandi_visible_state(['正当防卫']),
                           IntentionState())
    assert ist.locked_comp == _WANDI


def test_h1_missing_affixes_does_not_block() -> None:
    """词缀空帧(None=信息缺失)→ 不拦(不猜)。"""
    ist = update_intention(_wandi_visible_state([]),
                           IntentionState())
    assert ist.locked_comp == _WANDI


# ===== H3:_opening_hold_active 真值表(含降级锁)=====

_BATTLE_NODES = frozenset({'战斗', 'boss', '遭遇', '精英'})


def test_h3_default_unconditional_gate_on() -> None:
    """行为无条件化(W628 清偿):registry 默认恒 True,生产配置无关臂。"""
    assert DEFAULT_REGISTRY.opening_hold_battle_gate_enabled is True
    assert _opening_hold_active(2, '战斗', True, _BATTLE_NODES) is False


def test_h3_gate_on_battle_node_no_hold() -> None:
    """开臂:r2 战斗节点不 hold(W593 闸门①病灶:白板挨打)。"""
    assert _opening_hold_active(2, '战斗', True, _BATTLE_NODES) is False
    assert _opening_hold_active(2, 'boss', True, _BATTLE_NODES) is False


def test_h3_gate_on_non_battle_node_holds() -> None:
    """开臂:非战斗节点(奖励/补给/投资)维持 hold(r388 原语义保留)。"""
    for nt in ('奖励', '补给', '投资', '巨星'):
        assert _opening_hold_active(2, nt, True, _BATTLE_NODES) is True, nt


def test_h3_gate_on_round3_plus_no_hold() -> None:
    """r>2:无论节点类型都不属 opening hold(r70 语义接手)。"""
    assert _opening_hold_active(3, '奖励', True, _BATTLE_NODES) is False


def test_h3_missing_round_not_opening() -> None:
    """round 缺失(P1 之外/读不到)→ False(同旧「非开局轮」)。"""
    assert _opening_hold_active(None, '战斗', True, _BATTLE_NODES) is False


def test_h3_missing_node_type_degrades_to_old_hold() -> None:
    """降级锁:node_type 缺失(OCR+台账都空)→ 维持现状 hold(观察缺失不改行为)。"""
    assert _opening_hold_active(2, None, True, _BATTLE_NODES) is True


# ===== H2②:_rust_release_active 真值表 =====

def test_h2_default_unconditional_gate_on() -> None:
    """行为无条件化(W628 清偿):registry 默认恒 True,生产配置无关臂。"""
    assert DEFAULT_REGISTRY.rust_wear_release_enabled is True
    assert _rust_release_active(['库藏生锈'], True) is True


def test_h2_gate_on_rust_present_releases() -> None:
    """开臂+库藏生锈在场 → 豁免(owned 滞留=喂敌,competitors.md:45)。"""
    assert _rust_release_active(['库藏生锈', '忍无可忍'], True) is True


def test_h2_gate_on_no_rust_no_release() -> None:
    """开臂+词条不在场 → 不豁免(hold 原语义)。"""
    assert _rust_release_active(['忍无可忍'], True) is False
    assert _rust_release_active(None, True) is False


# ===== 注册表面 =====

def test_h1_strong_env_registry_nonempty_for_hp_charge_stack() -> None:
    """数据层守卫:hp_charge_stack 强环境集已建模且含多动/反伤两类机制 tag。"""
    from sr_od.application.currency_war.kernel.cw_comps import STRONG_ENV_MECHS
    assert {'反伤', '多段惩罚'} <= set(STRONG_ENV_MECHS['hp_charge_stack'])
    assert get_comp(_WANDI) is not None   # 判据锚:注册表存在该累积型线
