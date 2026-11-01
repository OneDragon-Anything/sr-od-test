"""策略卡空仓经验检查腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_empty_equip_xp 纯判定 + sim/cw_sim_backend.py 节点窗挂点
唯一调用口)。

测试面依据 = 迭代设计 designs/T-189-kongcang.md(定稿)§4 锁 3 + REVIEW-T189
§五④(卡面官方原文:「进入新节点时，如果物品栏和备战席没有任何装备(消耗品
除外)，则获得2经验值。」;直构形态先例 = 同目录 check_strategy_* 族镜像):
- 条件矩阵(锁 3):满装备→0;工具类/特殊类(垃圾袋,口径 A 锚定)+裸
  bench→表值;空+裸→表值;bench unit 带装备→0;名字不在册→0(防御);
  上阵带装备→表值(辖域判读 A 锚定);None 防御→0(fail-closed);
- 腿1→腿2 交互(锁 3):选卡落地后物品栏恒非消耗品(简易池无工具/特殊类)
  → 拿卡当窗必判 0(结构性自洽);
- 纯读零写:函数体零容器写(判定无 sig 形参,世界写端归 sim 挂点)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_equipment_data import (
    CONSUMABLE_EQUIP_CATEGORIES,
    EQUIPMENTS,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_empty_equip_xp,
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
    equips_by_category,
)

_CARD = '空仓'
_XP = 2

#: 类别代表件(注册表现值直读):工具/特殊类各一;非消耗品取简易池首件。
_TOOL = '员工投影仪'      # 工具类(EQUIPMENTS 在册,穿戴候选过滤面同源)
_SPECIAL = '垃圾袋'       # 特殊类(两口径判别件,口径 A 下按消耗品)
_UNKNOWN = '不存在的装备'  # 注册表外名(防御分支输入)

_SIG_OBS = ChannelSig(family='obs', actor='TestEmptyDeck')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test-seed',
                        mode='compute')


def _simple_item() -> str:
    """非消耗品代表件(简易池首件,注册表派生禁手抄池清单)。"""
    return equips_by_category('简易')[0]


def _gs(*, card: str | None = _CARD, equips: list[str] | None = None,
        bench: list[BenchSlot] | None = None,
        deployed: DeployedView | None = None) -> GameState:
    """直构容器(card=None = 未持卡;'躺平' = 表外卡;三域传 None = 保持
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


def _unit(char_id: str = '希儿',
          equips: list[str] | None = None) -> BenchSlot:
    """备战席单位槽(equips=None = 裸角色)。"""
    return BenchSlot(kind='unit',
                     unit=Unit(char_id=char_id, star=1,
                               equips=list(equips or [])))


def test_full_deck_zero() -> None:
    """满装备(锁 3):物品栏含非消耗品(简易件)+ 工具类混排 + 裸 bench
    → 0(任意非消耗品在场即破,消耗品豁免不救非消耗品同伴)。"""
    gs = _gs(equips=[_simple_item(), _TOOL], bench=[])
    assert check_strategy_empty_equip_xp(gs) == 0


def test_tool_only_consumable_grants() -> None:
    """工具类豁免面(锁 3):物品栏仅工具类 + 裸 bench → 表值(消耗品
    除外 = 工具类不计入「没有任何装备」)。"""
    gs = _gs(equips=[_TOOL], bench=[])
    assert check_strategy_empty_equip_xp(gs) == _XP


def test_special_category_grants_anchor_a() -> None:
    """特殊类判别件(锁 3,口径 A 锚定):垃圾袋(特殊类)+ 裸 bench →
    表值(裁决点 2 默认 {工具, 特殊} 整类按消耗品;若翻 B 口径本锁先红)。"""
    assert EQUIPMENTS[_SPECIAL].category == '特殊', '前置:垃圾袋 = 特殊类'
    gs = _gs(equips=[_SPECIAL], bench=[])
    assert check_strategy_empty_equip_xp(gs) == _XP


def test_empty_inventory_bare_bench_grants() -> None:
    """双空主条(锁 3):物品栏空 + 裸 bench → 表值(真值锁锚点)。"""
    gs = _gs(equips=[], bench=[])
    assert check_strategy_empty_equip_xp(gs) == _XP


def test_bench_unit_with_equips_zero() -> None:
    """备战席穿戴面(锁 3):任一 unit 槽带装备(含特殊类)→ 0——消耗品
    豁免只辖物品栏面,席位穿戴任何装备即破(设计 §2.3 序 4,守卫方向 =
    宁可漏发)。"""
    for worn in ([_SPECIAL], [_simple_item()]):
        gs = _gs(equips=[], bench=[_unit(equips=worn)])
        assert check_strategy_empty_equip_xp(gs) == 0, f'穿戴 {worn} 应破'


def test_unknown_name_counts_as_equip_zero() -> None:
    """名字不在册防御(锁 3):按装备计 → 0(log 留证;XP 是奖励,误发 =
    捏造世界真值,宁可漏发)。"""
    gs = _gs(equips=[_UNKNOWN], bench=[])
    assert check_strategy_empty_equip_xp(gs) == 0


def test_deployed_wearing_irrelevant_scope_a() -> None:
    """上阵辖域判读 A 锚定(锁 3):上阵前排带满装备 + 物品栏/备战席空
    → 表值(卡面「物品栏和备战席」文义直读,上阵不在辖域;判读申报制,
    证伪路径 = 实机上阵穿满空仓局 XP 发放观察)。"""
    front = [Unit(char_id='希儿', star=1, equips=[_simple_item()])]
    gs = _gs(equips=[], bench=[],
             deployed=DeployedView(front_slots=front, back_slots=[]))
    assert check_strategy_empty_equip_xp(gs) == _XP


def test_none_defense_fail_closed() -> None:
    """None 防御(锁 3 序 0):三域任一未观察 → 0(fail-closed;sim 生产
    开局种子底座不触发,直构单测域触发)。"""
    assert check_strategy_empty_equip_xp(_gs(card=_CARD)) == 0
    assert check_strategy_empty_equip_xp(_gs(card=_CARD, equips=[])) == 0
    assert check_strategy_empty_equip_xp(_gs(card=_CARD, bench=[])) == 0


def test_no_card_and_off_table_zero() -> None:
    """未持卡/表外卡零命中(锁 3):双空也零发放(白名单表外禁从效果原文
    自动猜装)。"""
    for card in (None, '躺平'):
        gs = _gs(card=card, equips=[], bench=[])
        assert check_strategy_empty_equip_xp(gs) == 0, f'{card}: 零命中'


def test_leg1_interaction_pick_window_zero() -> None:
    """腿1→腿2 交互(锁 3):选卡落地后物品栏 = 采样简易件(简易池全体
    非消耗品,注册表派生断言)→ 拿卡当窗必判 0(结构性自洽——拿卡即破
    空仓,发放起点 = 卖出/耗用该件之后的节点窗)。"""
    pool_cats = {EQUIPMENTS[n].category for n in equips_by_category('简易')}
    assert pool_cats.isdisjoint(CONSUMABLE_EQUIP_CATEGORIES), \
        '前置:简易池无工具/特殊类(交互用例的结构前提)'
    gs = _gs(equips=[_simple_item()], bench=[])
    assert check_strategy_empty_equip_xp(gs) == 0


def test_pure_read_zero_container_writes() -> None:
    """纯读零写(形态 A):命中路径零容器写(判定无 sig 形参零世界写,
    世界写端 = sim 挂点唯一调用口)。"""
    gs = _gs(equips=[], bench=[])
    seq0 = gs.write_seq
    assert check_strategy_empty_equip_xp(gs) == _XP
    assert gs.write_seq == seq0, '判定零写'


def test_simple_pool_names_all_in_registry() -> None:
    """注册表闭合旁证(锁 3 防御支的结构前提):简易池全体 ∈ EQUIPMENTS
    (生产不可达「名字不在册」,防御分支仅为读链漂移兜底)。"""
    assert set(equips_by_category('简易')) <= set(EQUIPMENTS)
