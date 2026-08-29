"""ADR-0418 新授权窗行为锁:gate_min_round 8→6 后 {r6..r9} 的
承接门家族放行行为(旧窗边界语义由 w96/w232 replace 钉窗锁与
w227/w252/w242/adr0293 已同步先例覆盖,本文件只锁新窗正面行为)。

锁行为(每条=一个确定输入下的确定行为,帧构造经探针实证):
- 生成层 C 臂:r7(新窗内)承接缺口 gap>0 时,deployed 目标件+店内
  同名 → 副本候选放行,tag='line_opportunistic';同帧 r5(窗外)
  gap=0 → 买候选不生成(零漂移边界);
- 成型停手承接维:r7 gap>0 → 不停手继续投资(与 w107 的
  「窗内 gap=0 仍停手」锁合成两维完备面);
- boss 投影 wart(ADR-0418 挂账):handoff_boss_reward_bonus 触发
  条件绑定 min_round,+2 随前移落 r6——r6 投影 = hp+2−E[dmg],
  r7/r9 = hp−E[dmg](本锁钉住的是 ADR-0418 已落地语义,解耦重标
  定落地时本锁随 ADR 更新)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import (
    HoardTarget,
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.filters import (
    formed_stop_active,
)
from sr_od.application.currency_war.decision.decision_v2.handoff import (
    boss_projected_hp,
    handoff_gate_gap,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY
_TARGET = '花火'   # hoard 目标件(姬子列车锁定线;C 臂放行对象)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=('姬子·启行',))
    return s


def _state(round_num: int, hp: int = 40) -> GameState:
    """探针帧:deployed 目标件单件 + 店内同名;hp=40(低血,
    hp 维缺口)+ 板面浅 → 新窗内 gap=1、r5 窗外 gap=0。"""
    return GameState(
        plane=1, round_num=round_num, gold=60, level=5, hp=hp,
        board={'列车同行': 2},
        deployed=[BenchChar(slot=0, char_id=_TARGET,
                            faction='仙舟罗浮', star=1)],
        bench=[],
        shop=[ShopCard(name=_TARGET, faction='仙舟罗浮', cost=5,
                       x=0, star=1)])


def test_c_arm_new_window_r7_allows_line_opportunistic_copy() -> None:
    """C 臂(ADR-0405/0411 无条件):r7 ∈ 新窗 ∧ gap>0 → deployed
    目标件的店内同名副本放行,tag='line_opportunistic'(gate 前移前该帧
    基线 gap=0 候选=[];探针实证)。"""
    sess = _sess()
    st = _state(7)
    assert handoff_gate_gap(st, sess, _REG) == 1
    buys = [c for c in generate_candidates(st, sess, _REG)
            if isinstance(c.action, BuyCard)
            and c.action.card.name == _TARGET]
    assert buys and buys[0].tag == 'line_opportunistic', \
        '新窗 r7 gap>0:同名副本候选必须放行(line_opportunistic)'


def test_c_arm_out_of_window_r5_still_zero_drift() -> None:
    """零漂移边界:r5(窗外)同帧 gap=0 → 不生成该买候选。
    (语义演进,ADR-0438:copy_swap_target_exempt 开臂翻默认 True,
    deployed 目标件的第 2 份在窗外也生成——本锁改显式注入关臂,
    钉「守卫直通基线」的原边界;豁免臂行为由 w242/adr0303 锁。)"""
    from dataclasses import replace
    sess = _sess()
    st = _state(5)
    assert handoff_gate_gap(st, sess, _REG) == 0
    assert not [c for c in generate_candidates(
                    st, sess, replace(_REG, copy_swap_target_exempt=False))
                if isinstance(c.action, BuyCard)
                and c.action.card.name == _TARGET], \
        '窗外 r5 同名副本必须仍被守卫拦(零漂移)'


def test_formed_stop_new_window_gap_positive_keeps_investing() -> None:
    """承接维:r7 ∈ 新窗 ∧ gap>0 → 成型停手让位,不停手继续投资
    (买候选保留;w107 锁「窗内 gap=0 仍停手」为本锁的对偶面)。"""
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_intention import intention_core
    comp = get_comp('DOT队')
    core = intention_core(comp)
    st = GameState(
        plane=1, round_num=7, gold=60, level=5, hp=15,
        board=dict(comp.form_tiers),
        deployed=[BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                            star=2)],
        bench=[], shop=[], node_type='battle')
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked',
                                       locked_comp='DOT队')
    assert handoff_gate_gap(st, sess, _REG) == 1   # 末窗缺口帧(镜像 w227)
    assert formed_stop_active(st, sess, _REG) is False, (
        '新窗 r7 gap>0:承接维接管,成型不停手')


def test_boss_reward_bonus_shifted_to_r6_wart() -> None:
    """boss 投影 wart(ADR-0418 挂账):+2 奖励项触发轮=min_round=6
    ——r6 投影比 r7/r9 高 2,「r8 奖励」语义随移的已落地现状钉死,
    防解耦批之外的改动静默移位。"""
    proj6 = boss_projected_hp(_state(6), 60, _REG)
    proj7 = boss_projected_hp(_state(7), 60, _REG)
    proj9 = boss_projected_hp(_state(9), 60, _REG)
    assert proj6 == proj7 + 2 == proj9 + 2, (
        f'r6 奖励 +2 wart 移位面变化:proj6={proj6} '
        f'proj7={proj7} proj9={proj9}(ADR-0418 挂账语义被改,'
        '若为解耦批落地请同步更新本锁)')
