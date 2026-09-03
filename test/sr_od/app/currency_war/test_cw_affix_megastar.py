# -*- coding: utf-8 -*-
"""test_cw_affix_megastar 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w875_env_b_scoring: test_cw_w875_env_b_scoring.py
- w878_deadtag_revive: test_cw_w878_deadtag_revive.py
- w88_star_investment: test_cw_w88_star_investment.py
- w607_affix_consumption: test_cw_w607_affix_consumption.py
- w607_h2o_verdict: test_cw_w607_h2o_verdict.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# (W875 环境B类评分补全包、长线利好刷价与 W878 死 tag 复活批的锁段已随
#  各自开关族删除——旧方案清退批,清查报告 OLD_MIX_AUDIT §1.3;
#  cw_comps 的 W875_* 增表/w875_active_tags/w878_active_tags 门控与
#  longterm_refresh_* 参数同批删,effective_mechanic_attributes 改为
#  永久滤除口径(_W878_RETIRED_TAGS)。)
# ==================== w88_star_investment ====================

from types import SimpleNamespace


from sr_od.application.currency_war.sim.checks.ledger import check_coldstart_seed_squander

from sr_od.application.currency_war.sim.checks.pool import check_engine_seed_not_resold
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    engine_char_names,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import score_state

_REG = DEFAULT_REGISTRY
_CARRY = '姬子·启行'          # 引擎件(恒在目标集)
_PAIR_FILLER = '花火'          # 目标件(锁线视窗内)
_NON_DIRECTION = '翡翠'        # 公司件,线外散件(冷启动反例)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess(line: bool = True) -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    if line:
        from sr_od.application.currency_war.kernel.cw_intention import (
            HoardTarget,
            IntentionState,
        )
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '姬子列车'
        s.v3_intention = ist
        s.v3_hoard = HoardTarget(
            frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
            frozenset(), 'locked')
        s.v3_core_names = {'姬子·启行'}
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 6, 'gold': 60, 'level': 5,
            'board': {'仙舟罗浮': 1}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


# --- 件1:核心升星价值项 ------------------------------------------------------


def test_core_star_term_values_2star_target() -> None:
    """2★ 目标件显影 core_star=unit;1★ 不显影;非目标 2★ 不显影([31]
    填充件可回收语义保留)。"""
    sess = _sess()
    st_2star = _state(bench=[_bench(_PAIR_FILLER, star=2)])
    st_1star = _state(bench=[_bench(_PAIR_FILLER, star=1)])
    v2 = score_state(st_2star, _REG, sess)['core_star']
    v1 = score_state(st_1star, _REG, sess)['core_star']
    import pytest
    assert v2 == pytest.approx(_REG.core_star_unit * _REG.bench_form_weight), \
        f'bench 2★ 目标件应按折减权重显影(实际 {v2})'
    assert v1 == 0.0
    # 非目标 2★ 不受保护
    st_off = _state(bench=[_bench('星期日', faction='盛会之星', star=2)])
    assert score_state(st_off, _REG, sess)['core_star'] == 0.0


def test_core_star_deployed_full_weight_and_ab_off() -> None:
    """deployed 2★ 全额;core_star_unit=0 关闭(A/B 基线臂)。"""
    sess = _sess()
    st = _state(
        deployed=[SimpleNamespace(char_id=_CARRY, faction='列车同行',
                                  star=2, position_pref='back',
                                  equips=(), slot=0)])
    assert score_state(st, _REG, sess)['core_star'] == _REG.core_star_unit
    reg_off = DecisionV2Registry(core_star_unit=0.0)
    assert score_state(st, reg_off, sess)['core_star'] == 0.0


# --- 件2:coldstart v2 防线 ---------------------------------------------------


def test_coldstart_door_single_frame() -> None:
    """v2 冷启动门单帧锁:P1 r1 板面空,pair 通道只放行方向件(引擎件/
    同名副本);线外散件不生成买候选(局49 形态,v1 门语义在 v2 的载体)。"""
    sess = _sess(line=False)   # 无方向(冷启动常态)
    _eng = next(iter(engine_char_names()))
    st = _state(round_num=1, board={}, shop=[
        SimpleNamespace(name=_eng, faction='列车同行', cost=3,
                        x=0, star=1),
        SimpleNamespace(name=_NON_DIRECTION, faction='公司', cost=1,
                        x=0, star=1),
    ])
    cands = generate_candidates(st, sess, _REG)
    tags = {c.action.card.name: c.tag for c in cands
            if c.action.__class__.__name__ == 'BuyCard'}
    assert tags.get(_NON_DIRECTION) is None, \
        f'冷启动线外散件 {_NON_DIRECTION} 不应生成买候选(实际 {tags})'
    assert _eng in tags, '引擎件(方向件)冷启动应放行'


def _cw_row(plane: int, rn: int, actions: list[dict]) -> dict:
    return {'plane': plane, 'round_num': rn, 'actions': actions,
            'state': {}}


def _buy(name: str, reason: str, cost: int = 1) -> dict:
    return {'__type__': 'BuyCard', 'reason': reason,
            'card': {'name': name, 'cost': cost}}


def _sell(name: str) -> dict:
    return {'__type__': 'SellBench', 'name': name}


def test_coldstart_checker_catches_d2_pair_violation() -> None:
    """变异自检(检查器非安慰剂):去门账本(p1 r1 d2_pair 买线外散件)
    必须涌现违规——v2 标签面(d2_ 前缀归一化)可被检查器消费。"""
    rows = [_cw_row(1, 1, [_buy(_NON_DIRECTION, 'd2_pair')]),
            _cw_row(1, 2, [_buy(_NON_DIRECTION, 'd2_pair')])]
    v = check_coldstart_seed_squander(rows)
    assert len(v) == 2, \
        f'去门变异必须涌现违规(实际 {v})——检查器对 v2 标签面失明'


def test_coldstart_checker_passes_legal_v2_ledger() -> None:
    """合法 v2 账本不误报:方向件(engine_seed)/copy(3合1 素材)放行。"""
    rows = [_cw_row(1, 1, [_buy('姬子·启行', 'd2_engine_seed', 3),
                           _buy('花火', 'd2_copy')]),
            _cw_row(1, 2, [_buy('三月七', 'd2_line_carry')])]
    assert check_coldstart_seed_squander(rows) == []


# --- 件3:engine_seed 买/卖互踩(窗口绝对不让位)-------------------------------


def test_carry_gate_yields_to_fresh_seed() -> None:
    """seed16 回归锁:bench 满+唯一可卖=新鲜 engine_seed 种子 →
    carry_gate 本轮不腾(旧 W51 死锁豁免=买侧见即买与卖侧腾位互踩,
    r4 买 r6 卖 r7 再买;ADR-0339 件3 裁决移除豁免)。"""
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        carry_gate_actions,
    )

    sess = _sess()
    sess.v2_round_key = (1, 4)
    sess.v2_seed_bought = {'姬子·启行': ((1, 3), 1)}
    bench = ([_bench('姬子·启行', faction='列车同行', slot=0)]
             + [_bench(n, faction='仙舟罗浮', slot=i)
                for i, n in enumerate(['藿藿', '爻光', '三月七', '花火',
                                       '瓦尔特', '藿藿', '爻光', '三月七'],
                                      start=1)])
    st = _state(round_num=4, gold=50,
                shop=[SimpleNamespace(name='姬子·启行', faction='列车同行',
                                      cost=4, x=0, star=1)],
                bench=bench)
    assert carry_gate_actions(st, sess, _REG) == [], \
        '窗口内种子不让位给 carry 腾位(carry 延后 ≤2 轮,死锁有界)'


def test_seed_age_blocked_phantom_cnt_not_exempt() -> None:
    """幻影计数锁:cnt≥2 但真持有 <2 份(登记重复/执行层否决留痕)
    不解除种子保护(seed16 姬子·启行单买 cnt=2 被 r5 卖出的互踩根因);
    真持有 ≥2 份才走素材语境豁免。"""
    from sr_od.application.currency_war.kernel.cw_discipline_rules import (
        seed_age_blocked,
    )
    sess = _sess()
    sess.v2_round_key = (1, 5)
    sess.v2_seed_bought = {'姬子·启行': ((1, 4), 2)}
    st = _state(round_num=5, bench=[_bench('姬子·启行',
                                            faction='列车同行')])
    bc = st.bench[0]
    assert seed_age_blocked(bc, st, sess) is True, \
        '幻影 cnt=2(真持有 1 份)不得解除种子保护'
    st2 = _state(round_num=5,
                 bench=[_bench('姬子·启行', faction='列车同行', slot=0),
                        _bench('姬子·启行', faction='列车同行', slot=1)])
    assert seed_age_blocked(st2.bench[0], st2, sess) is False, \
        '真持有 2 份=3合1 素材语境,豁免(不挡)'


def test_checker_flags_reason_channel_resale() -> None:
    """检查器(reason 口径,语义不变):engine_seed 买入 ≤2 轮内单份回卖
    必报(seed16 姬子·启行 r4 买 r6 卖形态的账本侧锁)。"""
    rows = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3)]),
            _cw_row(1, 6, [_sell('姬子·启行')])]
    v = check_engine_seed_not_resold(rows)
    assert len(v) == 1 and '姬子·启行' in v[0], f'回卖未报(实际 {v})'


def test_checker_bounds_and_merge_exemption() -> None:
    """边界:>2 轮后卖不报([21] 囤件窗口外合法);同轮 ≥2 份=3合1
    素材语境豁免不报。"""
    rows_late = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3)]),
                 _cw_row(1, 8, [_sell('姬子·启行')])]
    assert check_engine_seed_not_resold(rows_late) == []
    rows_merge = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3),
                                 _buy('姬子·启行', 'd2_engine_seed', 3)]),
                  _cw_row(1, 5, [_sell('姬子·启行')])]
    assert check_engine_seed_not_resold(rows_merge) == []


# ==================== w607_affix_consumption ====================

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
from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
    _opening_hold_active,
    _rust_release_active,
)

_WANDI = '万敌单C'   # hp_charge_stack 累积型线(global_accumulators 注册,accumulator_family §4.1)
_SEELE = '希儿量子'   # 非累积型线(判据不辖,恒 None)


def _w607_affix_consumption_state(affixes: list[str], plane: int = 2, round_num: int = 1) -> GameState:
    st = GameState()
    st.plane = plane
    st.round_num = round_num
    st.enemy_affixes = list(affixes)
    return st


# ===== H1:_line_env_qualified 四态真值表 =====

def test_h1_non_accumulator_line_not_governed() -> None:
    """非累积型线 → None(判据不辖,资格面不变)。"""
    assert _line_env_qualified(_w607_affix_consumption_state(['净化身心']), _SEELE) is None


def test_h1_empty_affixes_missing_evidence() -> None:
    """词缀可信位缺失(空)→ None:不猜,放行(动态剔除同款)。"""
    assert _line_env_qualified(_w607_affix_consumption_state([]), _WANDI) is None


def test_h1_strong_env_hit() -> None:
    """强环境命中:正当防卫→反伤 / 忍无可忍→多段惩罚(accumulator_family §3)。"""
    assert _line_env_qualified(_w607_affix_consumption_state(['正当防卫']), _WANDI) is True
    assert _line_env_qualified(_w607_affix_consumption_state(['忍无可忍']), _WANDI) is True


def test_h1_adverse_or_unmapped_affix_miss() -> None:
    """环境不命中→False;未入 AFFIX_MECHANIC_MAP 的词缀(灼热轰炸)按不命中(宁缺勿错)。"""
    assert _line_env_qualified(_w607_affix_consumption_state(['净化身心']), _WANDI) is False
    assert _line_env_qualified(_w607_affix_consumption_state(['灼热轰炸']), _WANDI) is False


# ===== H1:锁线过滤(gate on/off × 环境)=====

def _wandi_visible_state(affixes: list[str]) -> GameState:
    st = _w607_affix_consumption_state(affixes)
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


# ==================== w607_h2o_verdict ====================

from sr_od.application.currency_war.kernel.cw_events import _EQUIP_VALUE
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY

# 装备获取评分面常数(cw_events 生产单一源)
_KEY_FIT_BONUS = 10          # decide_supply key_equips 命中加分
_PLANNER_KEY_BONUS = 15      # decide_planner 装备类 key 命中加分
_PLANNER_UPGRADE_FLOOR = 40  # 升费卡最低分(100−60 银狼不在场罚后下界)
_PLANNER_WEAKEN_SCORE = 55   # 弱化卡基础分


def _rust_per_piece() -> float:
    reg = DEFAULT_REGISTRY
    return (reg.rust_hoard_damage_share * reg.expected_battle_loss
            * reg.battles_left_est * reg.hp_to_gold)


def test_h2o_per_piece_gold_equivalent_bound() -> None:
    """每件扣减 = 0.75 金当量,封顶 7.5(registry/文档实采常量推导,非独立魔数)。"""
    reg = DEFAULT_REGISTRY
    assert reg.rust_hoard_damage_share == 0.03   # competitors.md:45 敌伤面
    assert reg.rust_hoard_penalty_cap == 10      # competitors.md:45 计件上限
    total = _rust_per_piece() * reg.rust_hoard_penalty_cap
    assert abs(_rust_per_piece() - 0.75) < 1e-9
    assert total < _KEY_FIT_BONUS, '最大滞留扣减须仍小于 key_fit 边际,否则补给面翻红重评'


def test_h2o_supply_face_no_reorder() -> None:
    """补给面无翻转:key 恒先(key_fit 10 > 封顶 7.5),非 key 间扣减同额序不变。"""
    total = _rust_per_piece() * DEFAULT_REGISTRY.rust_hoard_penalty_cap
    key_margin = _KEY_FIT_BONUS - total
    assert key_margin > 0, 'key_fit 边际被滞留扣减侵蚀穿 → 补给选序翻转,重评'
    # 非 key 件间:扣减 = f(owned+1),与候选身份无关 → 同额平移不改序
    assert len(set(_EQUIP_VALUE.values())) > 1   # 前提:价值表有区分度


def test_h2o_planner_face_no_flip() -> None:
    """巨星策划面:装备类扣后上界仍低于升费/弱化下界 → 选型不翻转。"""
    equip_upper = max(_EQUIP_VALUE.values()) + _PLANNER_KEY_BONUS
    total = _rust_per_piece() * DEFAULT_REGISTRY.rust_hoard_penalty_cap
    assert equip_upper - total < _PLANNER_UPGRADE_FLOOR, (
        '装备类扣后触及升费下界 → 策划面翻转,重评')
    assert equip_upper - total < _PLANNER_WEAKEN_SCORE
