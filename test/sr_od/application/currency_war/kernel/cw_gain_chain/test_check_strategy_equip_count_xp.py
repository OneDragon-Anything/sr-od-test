"""策略卡装备计数经验检查效果条目测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_equip_count_xp 纯判定 + sim/cw_sim_backend.py 节点窗调用点
唯一调用口;先例 = 同目录 test_check_strategy_empty_equip_xp.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-272-zanmei-
taiyang.md(定稿,REVIEW 无需用户决定 9/9)§4 锁 4(卡面官方原文:「每拥有一件
【白昼装备】以及其原型装备，在进入新节点时就获得1点经验。」):

- 名集闭集锁:DAYLIGHT_EQUIP_XP_NAME_SET == 注册表 category 白昼全集
  ∪ 三基件名(重推导后比对,非硬编码 9 名字面——注册表白昼段扩员即红,
  防静默漂移;特权变体三件不入 = 裁决点 4 默认案锚定);
- 判定矩阵(三态 + 边界):无持卡 → 0;持卡 + 2 件原型 → 2;库存与穿戴
  混合 → 四源合计;特权变体/非白昼装备不计;表外卡 → 0;None 防御
  fail-closed;纯读零写(判定无 sig 形参,状态副本写端归 sim 调用点)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_equip_count_xp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    DAYLIGHT_EQUIP_XP_NAME_SET,
    STRATEGY_EQUIP_COUNT_XP_GRANTS,
    _validate_strategy_equip_count_xp_grants,
)

_CARD = '赞美太阳'
_XP_PER_EQUIP = 1

#: 三基件名(「其原型装备」= 变体链基件,词面直读;闭集锁比对用)。
_BASE_NAMES = ('光速螺旋桨', '武器大师', '斩首行动')

_SIG_OBS = ChannelSig(family='obs', actor='TestEquipCount')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test-seed',
                        mode='compute')


def _gs(*, card: str | None = _CARD, equips: list[str] | None = None,
        bench: list[BenchSlot] | None = None,
        deployed: DeployedView | None = None) -> GameState:
    """直构状态容器(card=None = 未持卡;'躺平' = 表外卡;域传 None = 保持
    未观察,供 None 防御支;bench 传 [] = 裸备战席)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_SIG_LOGIC)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    if bench is not None:
        slots = list(bench) + [BenchSlot(kind='empty')] * (9 - len(bench))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if deployed is not None:
        gs.observe(gs.deployed, deployed, sig=_SIG_OBS)
    return gs


def _unit(char_id: str = '那刻夏',
          equips: list[str] | None = None) -> BenchSlot:
    """单位槽(equips=None = 裸角色)。"""
    return BenchSlot(kind='unit',
                     unit=Unit(char_id=char_id, star=1,
                               equips=list(equips or [])))


def test_name_set_closed_derivation() -> None:
    """名集闭集锁(锁 4 前半):名集 == category 白昼全集 ∪ 三基件名
    (依 EQUIPMENTS 现值重推导后比对,非硬编码 9 名字面);特权变体三件
    不入(裁决点 4 默认案 A 锚定——翻 B 口径本锁先红);基件 = 进阶类已登记
    (结构前提)。"""
    daylight = {n for n, e in EQUIPMENTS.items() if e.category == '白昼'}
    want = daylight | set(_BASE_NAMES)
    assert want == DAYLIGHT_EQUIP_XP_NAME_SET, \
        (f'名集漂移: 多 {sorted(DAYLIGHT_EQUIP_XP_NAME_SET - want)} / '
         f'缺 {sorted(want - DAYLIGHT_EQUIP_XP_NAME_SET)}')
    assert len(DAYLIGHT_EQUIP_XP_NAME_SET) == 9, '恰 9 名(6 白昼 + 3 基件)'
    for n in _BASE_NAMES:
        assert EQUIPMENTS[n].category == '进阶', f'{n} = 进阶基件'
    assert not any(n.endswith('·特权')
                   for n in DAYLIGHT_EQUIP_XP_NAME_SET), '特权变体不入集'


def test_table_row_single_source() -> None:
    """登记单一源旁证:表 = 族现役首例单卡,值 = 卡面直读 1(每件每节点
    XP);键 ∈ 策略注册表且 id 对拍(空仓族登记锁同法)。"""
    assert set(STRATEGY_EQUIP_COUNT_XP_GRANTS) == {_CARD}, \
        '注册面 = 族现役首例(同族后继卡各自独立批,禁顺手代登记)'
    assert STRATEGY_EQUIP_COUNT_XP_GRANTS[_CARD] == _XP_PER_EQUIP, \
        f'行值漂移: {STRATEGY_EQUIP_COUNT_XP_GRANTS!r}'


def test_no_card_and_zero_holding_zero() -> None:
    """无持卡/持卡零持有 → 0(锁 4 三态前两态;未持卡与表外卡同路零命中
    ——白名单表外禁从效果原文自动猜装)。"""
    assert check_strategy_equip_count_xp(_gs(card=None,
                                             equips=['光速螺旋桨'])) == 0
    assert check_strategy_equip_count_xp(_gs(card='躺平',
                                             equips=['光速螺旋桨'])) == 0
    gs = _gs(equips=['垃圾袋'])
    assert check_strategy_equip_count_xp(gs) == 0, '持卡但零白昼系持有'


def test_two_prototypes_grant() -> None:
    """持卡 + 2 件原型(锁 4 三态主真值):库存 2 件基件 → 2 XP(白昼系
    名集含基件,库存单源可达成——sim 结构性可达面,sim 状态副本零羁绊不产
    白昼件但原型件经进阶合成可达,本通道 sim 非死代码)。"""
    gs = _gs(equips=['光速螺旋桨', '武器大师'])
    assert check_strategy_equip_count_xp(gs) == 2


def test_four_source_mixed_total() -> None:
    """四源混合合计(锁 4 三态尾):前排穿 + 后排穿 + 备战席穿(记录内)+
    库存,四源白昼系件数求和 × 表值;非白昼装备(财富/特权变体)不计
    (特权变体不入名集 = 默认案锚定,计入即翻裁据未申报)。"""
    front = [Unit(char_id='那刻夏', star=1, equips=['白昼·武器大师'])]
    back = [Unit(char_id='那刻夏', star=1, equips=['光速螺旋桨']),
            Unit(char_id='希儿', star=1, equips=['财富'])]
    bench = [_unit(equips=['极·白昼·斩首行动'])]
    gs = _gs(equips=['白昼·光速螺旋桨', '光速螺旋桨·特权', '财富'],
             bench=bench,
             deployed=DeployedView(front_slots=front, back_slots=back))
    # 白昼系件:前排 1 + 后排 1 + 备战席 1 + 库存 1 = 4(特权变体/财富不计)
    assert check_strategy_equip_count_xp(gs) == 4


def test_none_defense_fail_closed() -> None:
    """None 防御与按源跳过(锁 4):策略集未观察 → 0(fail-closed);
    四源侧字段未观察 = 该源跳过不猜(held_equip_count 同基座——少计只
    漏发不误发),deployed 独源可见时可见源照计(非 any-None 全零,
    「宁可漏发」的方向语义 = 计数域不虚构不可见源,不否定可见源)。"""
    assert check_strategy_equip_count_xp(
        _gs(card=_CARD, equips=[])) == 0, '策略集未观察'
    gs = _gs(equips=None, deployed=DeployedView(
        front_slots=[Unit(char_id='那刻夏', star=1,
                          equips=['白昼·武器大师'])], back_slots=[]))
    assert check_strategy_equip_count_xp(gs) == 1, \
        'deployed 独源可见照计;库存/备战席未观察跳过不猜'


def test_none_strategy_set_zero() -> None:
    """策略集未观察独立支:持卡集 None → 0(禁沿「交集空」缺省语义误判)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, ['光速螺旋桨'], sig=_SIG_OBS)
    assert check_strategy_equip_count_xp(gs) == 0


def test_pure_read_zero_container_writes() -> None:
    """纯读零写(形态 A):命中路径零容器写(判定无 sig 形参零状态副本写,
    状态副本写端 = sim 唯一调用点)。"""
    gs = _gs(equips=['光速螺旋桨'])
    seq0 = gs.write_seq
    assert check_strategy_equip_count_xp(gs) == 1
    assert gs.write_seq == seq0, '判定零写'


def test_validator_drift_sentinels(monkeypatch) -> None:
    """构建校验负控(两漂移哨):①孤儿键(版本改名/移除静默失联);
    ②装备名漂移(名集成员不在 EQUIPMENTS = 计数恒 0 静默漏发,import 期
    哨是唯一响亮拦截面;白昼半区派生自注册表恒已登记,哨实辖基件名半区)。"""
    import sr_od.application.currency_war.kernel.cw_investments as inv

    bad = dict(STRATEGY_EQUIP_COUNT_XP_GRANTS)
    bad['不存在的卡'] = 1
    monkeypatch.setattr(inv, 'STRATEGY_EQUIP_COUNT_XP_GRANTS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_equip_count_xp_grants()

    # 还原表补丁再验哨②(孤儿哨先跑,表带脏键时名漂移分支不可达)
    monkeypatch.setattr(inv, 'STRATEGY_EQUIP_COUNT_XP_GRANTS',
                        dict(STRATEGY_EQUIP_COUNT_XP_GRANTS))
    monkeypatch.setattr(inv, 'DAYLIGHT_EQUIP_XP_NAME_SET',
                        DAYLIGHT_EQUIP_XP_NAME_SET | {'不存在的装备'})
    with pytest.raises(ValueError, match='装备名漂移'):
        _validate_strategy_equip_count_xp_grants()
