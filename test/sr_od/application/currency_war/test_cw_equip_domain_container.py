"""装备域容器换源三锁(迭代 2026-09-18-prep-obs-retirement 阶段 3.2/T-2)。

M7 装备计划(``_build_equip_wear_plan``)四路输入(owned/occupied/
back_layout/deployed)全面换容器 game state 读口,黑板帧消费清零。锁:
- 黑盒区分:session 无黑板帧(prep_obs 缺失)时 M7 照常产出(旧实现
  fail「备战观察帧缺失」)——证明输入真来自容器;
- fail 门方向:owned/occupied 域未观察(None = 识别域未就绪)分别
  保守关,与旧黑板 None 语义同映射。
"""
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp,
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_equip_wear_plan import (
    _build_equip_wear_plan,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)

_SIG = ChannelSig(family='obs', actor='cw4_seed',
                  mode='synthesized')


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
    """fail 门:owned 域未观察(None) → 保守关,fail_reason 指向 owned。"""
    session = cw4_session(cw4_comp())
    gs = game_state_of(session)
    gs.observe(gs.occupied_equips, {'front:1': ['x']}, sig=_SIG)
    ret = _build_equip_wear_plan(session)
    assert 'owned' in ret.fail_reason


def test_m7_fail_gate_occupied_unobserved():
    """fail 门:occupied 域未观察(None) → 保守关,fail_reason 指向 occupied。"""
    session = cw4_session(cw4_comp())
    gs = game_state_of(session)
    gs.observe(gs.equips, ['星币收集器'], sig=_SIG)
    ret = _build_equip_wear_plan(session)
    assert 'occupied' in ret.fail_reason
