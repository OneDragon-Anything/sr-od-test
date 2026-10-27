"""mandate 发出闸 bond_gate 分键写入断言(arm 分键新键族/拒绝侧闭集/
双轨域 arm='transition' 照旧)。

被测 = ``strategies/impl/mandate_v1/mandate.py`` ``emit_swap_redeploy``
分键写点与 :1495 发出闸路由(design 2026-10-26-swap-channel-unified
§2.3.1 arm 分键归宿;判据层计划形态另见 kernel 侧
test_select_swap_group_plan.py):

- **accept 侧新键族**:bond_gate_{leg}(leg ∈ tier/support/star/
  completion,首达腿)+ bond_gate_victim_tier_{tier}(值域 =
  一级/二级/名单末位);``cw4_m1p_arm_pending`` 载体保留;
- **拒绝侧分键闭集**:bond_gate_reject_nogain / conservation / novictim
  (3.5 预测表依赖闭集);
- **:1495 路由**:双轨域 arm='transition' 过 P79-3 放行门照旧(分键
  swap_arm_transition_trigger),转型域 bond_gate 臂不经 P79-3;
- **载荷迁移**:cw4_m1p_plan_pending 域事实键 = 'arm'(旧
  'trans_domain' 随域谓词退役)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_GIL = '吉尔伽美什'
_RIN = '远坂凛'
_QING = '青雀'
_TING = '停云'
_YAO = '爻光'
_SBR = 'Saber'
_WALT = '瓦尔特'
_FUX = '符玄'
_HUO = '藿藿'
_JI = '开拓者·记忆'


def _locked_session(comp_name: str) -> tuple:
    """终局锁定 session 桩(target_comp 直种 + ist 腿① + seam 开闸 +
    计数器清零;装配源 = cw4_session/cw4_gs 容器域)。"""
    session = cw4_session(get_comp(comp_name))
    st = state_of(session)
    st.v3_intention = IntentionState(locked_comp=comp_name)
    st.cw4_m1p_seam_verified = True
    st.cw4_counters = {}
    return session, st


def _pair_session() -> tuple:
    """配方对锁 session 桩(p1_pair 腿② + pair 伪阵容;双轨域)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )
    session = cw4_session(pair_target_comp(('持续伤害', '希儿系')))
    st = state_of(session)
    st.v3_intention = IntentionState(p1_pair=('持续伤害', '希儿系'))
    st.cw4_m1p_seam_verified = True
    st.cw4_counters = {}
    return session, st


def _emit(session, st, *, bench: list[str], front: list[str],
          back: list[str], deploy_cap: int = 5, level: int = 5):
    """emit 直驱(A 锚帧形态;deployed = front+back 行域,bench = 占席;
    level 与 deploy_cap 联动定 max_units——板满腿按容器派生链现算)。"""
    gs = cw4_gs(session, deploy_cap=deploy_cap, level=level,
                bench=[cw4_bc(n) for n in bench],
                front_row=[Unit(char_id=n, star=1) for n in front],
                back_row=[Unit(char_id=n, star=1) for n in back])
    frame = mandate.MandateFrame(
        gold=30, level=5,
        bench=[cw4_bc(n) for n in bench],
        deployed=[Unit(char_id=n, star=1) for n in (*front, *back)],
        deploy_cap=deploy_cap, node_type=None, stop_flag=False,
        k_members=(), round_num=2)
    out = mandate.emit_swap_redeploy(frame, session, gs)
    return out, st.cw4_counters


def test_emit_bond_gate_accept_key_family() -> None:
    """accept 侧新键族写入断言(锚帧 A):组计划发射 → bond_gate_tier
    (首达腿)+ bond_gate_victim_tier_一级 + m1p_fired;arm 载体 =
    'bond_gate';不经 P79-3(redeploy_cost_gate_defer 零显影);载荷
    域事实键 = arm(旧 trans_domain 退役)。"""
    session, st = _locked_session('双王圣杯')
    out, counters = _emit(session, st, bench=[_SBR],
                          front=[_GIL, _RIN, _QING, _TING], back=[_YAO])
    assert counters.get('m1p_fired') == 1, '组计划发射'
    assert counters.get('bond_gate_tier') == 1, \
        f"accept 分键 bond_gate_tier(首达腿),实得 {counters}"
    assert counters.get('bond_gate_victim_tier_一级') == 1, \
        'victim 层来源分键(值域一级)'
    assert counters.get('redeploy_cost_gate_defer') is None, \
        'bond_gate 臂不经 P79-3(转型域废弃面,3.2 接线复算)'
    assert st.cw4_m1p_arm_pending == 'bond_gate', 'arm 载体保留'
    assert st.cw4_m1p_plan_pending.get('arm') == 'bond_gate', \
        '载荷域事实键 = arm'
    assert 'trans_domain' not in st.cw4_m1p_plan_pending, \
        '旧 trans_domain 键随域谓词退役'
    sells = [e.action for e in out]
    assert len(sells) == 1, '锚帧 = 单对组(1 换 1)'
    assert getattr(sells[0], 'deployed_idx', None) == 4, \
        'victim 容器下标对位(后排首槽 = 4 + 0)'


def test_emit_bond_gate_reject_key_closed_set() -> None:
    """拒绝侧分键闭集写入断言:二级持平帧四腿全不中 → bond_gate_reject_
    nogain(+ m1p_plan_empty 照旧);arm 载体复位 None。"""
    session, st = _locked_session('双王圣杯')
    _out, counters = _emit(session, st, bench=[_JI],
                           front=[_GIL, _TING, _HUO, _WALT], back=[_FUX])
    assert counters.get('m1p_plan_empty') == 1, '计划空照旧计数'
    assert counters.get('bond_gate_reject_nogain') == 1, \
        f'拒绝侧闭集 nogain(四腿全不中),实得 {counters}'
    assert st.cw4_m1p_arm_pending is None, '无发出帧 arm 载体复位'


def test_emit_pair_frame_transition_gate_unchanged() -> None:
    """:1495 路由双轨域照旧:pair 帧(腿②)完成品计划 arm='transition'
    照旧**经 P79-3 放行门**(现行三轴在容器 bench 形状下的现行为 =
    帧级 defer,与改前逐帧等价——本函数零触碰;P79-3 废弃/复算接线 =
    后续阶段,届时本断言随废弃面改写);bond_gate 键族零显影(域切分,
    design §2.3.1 发出闸路由申报)。"""
    session, st = _pair_session()
    _out, counters = _emit(session, st, bench=['黑天鹅'],
                           front=['卡芙卡', '希儿', '花火', '娜塔莎'],
                           back=[], deploy_cap=4, level=4)
    assert counters.get('redeploy_cost_gate_defer') == 1, \
        '双轨域 arm=transition 过 P79-3 门(现行三轴 verdict 照旧)'
    assert counters.get('m1p_fired') is None, 'defer 帧不发射(现行)'
    assert counters.get('bond_gate_tier') is None \
        and counters.get('bond_gate_victim_tier_一级') is None, \
        '双轨域不产 bond_gate 新键族(域切分)'
    assert st.cw4_m1p_arm_pending is None, 'defer 帧 arm 载体复位(现行)'


def test_emit_bond_gate_no_victim_reject_key() -> None:
    """拒绝侧闭集 novictim:全 2★ 板(victim 池空)且 bench 无义务成员
    (evolution 不武装 → star_guard 恒拒 2★ 生效)→ bond_gate_reject_
    novictim(无可行组零动作)。"""
    session2, st2 = _locked_session('双王圣杯')
    gs = cw4_gs(session2, deploy_cap=5, level=5,
                bench=[cw4_bc('椒丘')],
                front_row=[Unit(char_id=n, star=2)
                           for n in (_GIL, _RIN, _QING, _TING)],
                back_row=[Unit(char_id=_YAO, star=2)])
    frame = mandate.MandateFrame(
        gold=30, level=5, bench=[cw4_bc('椒丘')],
        deployed=[Unit(char_id=n, star=2)
                  for n in (_GIL, _RIN, _QING, _TING, _YAO)],
        deploy_cap=5, node_type=None, stop_flag=False,
        k_members=(), round_num=2)
    mandate.emit_swap_redeploy(frame, session2, gs)
    counters2 = st2.cw4_counters
    assert counters2.get('bond_gate_reject_novictim') == 1, \
        f'拒绝侧闭集 novictim(victim 池空),实得 {counters2}'
    assert counters2.get('m1p_plan_empty') == 1, '计划空照旧计数'
