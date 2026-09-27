"""落位策略锁(P3 落位决策权归策略;design §2.2 + 行为变化申报第 1 项)。

 §2.2「mandate_v1 内聚落位策略」
与 §1 根因二(旧链路:框架定排,备战候选注册表
position_pref 恒被丢弃、候选恒按后排路由,「真 front 候选提前」分支永不
触发)。被锁行为:

- 排路由三级 = comp 站位覆盖(``Comp.char_positions``)> 注册表派生
  (``get_char(char_id).position_pref()``,禁全局 get_role_position)>
  back 兜底——旧「恒按后排」病灶的翻转,即行为变化申报第 1 项的注册表
  派生真实生效面;
- 注册表前排角色在前排有空时被排到前排(申报第 1 项点名的验证锁);
- 后排槽位上限 = back_layout 现值(P2 遗留分歧消除:基线 6 槽局发射
  空槽永不指 7-9 号槽,扩展局随实值)。

名字表达纪律:排偏好经注册表角色名获得(开拓者·记忆=front,花火=back,
爻光/万敌=flex 派生 back);comp 覆盖用真实注册表 comp(万敌单C 的
char_positions 万敌→front,攻略实证「燃血角斗场吃受击」)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    deploy_row_pref,
    deploy_slot_plans,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _bs(slot: int, char_id: str) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=1))


def _rows_of(state) -> list[str]:
    """落位计划的 (row, slot) 序(断言辅助)。"""
    return [row for _bi, row, _slot in state]


# ===== 排路由①:comp 站位覆盖 > 注册表 =====

def test_comp_position_override_beats_registry_pref() -> None:
    """comp char_positions 覆盖注册表:万敌注册表 flex(派生 back),
    「万敌单C」覆盖为 front → 落位排 = front(逐件路由直接断言 +
    落位计划端到端各一腿)。"""
    comp = get_comp('万敌单C')
    assert comp is not None and comp.char_positions.get('万敌') == 'front', \
        '注册表前置自检:万敌单C 带 char_positions 覆盖'
    assert deploy_row_pref('万敌', None) == 'back', \
        '无 comp 覆盖时:flex 派生 back(③兜底前先走②注册表)'
    assert deploy_row_pref('万敌', comp) == 'front', \
        'comp 覆盖压过注册表派生(①>②)'

    gs = game_state_of(None)   # 行域全空:两排都有空,路由无 fallback 干扰
    bench = [_bs(1, '万敌')]
    moves = deploy_slot_plans(bench, [0], comp, gs)
    assert moves[0][1] == 'front', \
        f'落位计划按覆盖排路由,实得 {moves[0]!r}'


# ===== 排路由②:注册表派生真实生效(申报第 1 项核心翻转)=====

def test_registry_front_char_seats_front_when_front_has_room() -> None:
    """注册表前排角色(开拓者·记忆,position_pref='front')在前排有空时
    被落位策略排到前排——旧链路恒按后排,本锁钉住派生真实生效。"""
    gs = game_state_of(None)
    bench = [_bs(1, '开拓者·记忆'),
             _bs(2, '花火')]   # 花火 = 注册表 back(对照组)
    moves = deploy_slot_plans(bench, [0, 1], None, gs)
    assert moves[0][:2] == (0, 'front'), \
        f'注册表前排角色落前排,实得 {moves[0]!r}'
    assert moves[1][:2] == (1, 'back'), '注册表后排角色照旧落后排'


def test_unregistered_name_falls_back_to_back() -> None:
    """③兜底:注册表未登记名(识别对齐缺失形态)按后排处理(fail 向
    后排 = 与旧缺省同侧,不因识别缺失翻到前排)。前排预置占位避开
    前排保证强转(前排全空 → back 件被强转前排,是另一条策略规则的
    正确行为,不混入本锁)。"""
    assert deploy_row_pref('未注册角色名', None) == 'back'
    gs = game_state_of(None)
    gs.observe(gs.deployed, _dvs([Unit(char_id='砂金', star=1, equips=[])], []),
               evidence='t', sig=_SIG_OBS)
    bench = [_bs(1, '未注册角色名')]
    moves = deploy_slot_plans(bench, [0], None, gs)
    assert moves[0][1] == 'back', '未注册名兜底后排'


# ===== 后排槽位上限 = back_layout 现值(P2 遗留分歧消除)=====

def test_back_slots_capped_by_back_layout_baseline() -> None:
    """back_layout 基线 6:8 个后排候选(前排被占满)→ 后排槽号至多 6,
    永不发射 7-9 号槽(执行面 6 槽,越界载荷 = 静默分歧的消除面)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_layout, 6, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id=f'前{i}', star=1, equips=[])
                for i in range(1, 5)], []), evidence='t', sig=_SIG_OBS)
    bench = [_bs(i + 1, '花火') for i in range(8)]
    moves = deploy_slot_plans(bench, list(range(8)), None, gs)
    back_slots = [slot for _bi, row, slot in moves if row == 'back']
    assert back_slots == [1, 2, 3, 4, 5, 6], \
        f'后排空槽按 back_layout 现值派生,实得 {back_slots!r}'


def test_back_layout_extended_value_extends_back_slots() -> None:
    """back_layout 扩展局(宝钻 8):后排空槽随实值到 8 号——执行面/表
    随实值,扩展槽在扩展局可达(上限随实值,非恒 6)。前排占满避开
    前排保证强转(不混入本锁)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_layout, 8, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id=f'前{i}', star=1, equips=[])
                for i in range(1, 5)], []), evidence='t', sig=_SIG_OBS)
    bench = [_bs(i + 1, '花火') for i in range(8)]
    moves = deploy_slot_plans(bench, list(range(8)), None, gs)
    back_slots = [slot for _bi, row, slot in moves if row == 'back']
    assert back_slots == [1, 2, 3, 4, 5, 6, 7, 8], \
        f'扩展局后排空槽达 8 号,实得 {back_slots!r}'
