"""策略卡赠礼条件两条效果条目发放检查腿测试(镜像 src = kernel/cw_gain_chain.py
的 ``check_strategy_gift_grants``;分方法拆目录规范落位,新函数落拆目录
新文件,先例 = 同目录 check_strategy_* 族镜像文件)。

测试面依据 = 迭代设计 designs/T-283-mi-zhi-lvren.md(定稿)§4 锁 2/锁 3
+ 七裁决点全部默认案(经族级授权自动收口,判定 = designs/REVIEW-T283.md):

- 锁 2 效果条目1(羁绊人数条件):种 4 巡海游侠上阵 + 持卡 → 备战 2★黄泉
  (placed)+ 装备栏星间旅人星徽 + 封账恰一笔;重复调用零双发(done
  短路);3 巡海零写不标 done;deployed 未观察零写不标 done;装备栏
  未观察零写不标 done(徽与角色同拍原子,拆拍引双发面);非持卡零写;
  计数口径 = 上阵(bench 同名不计入判据,T-30 口径);
- 锁 3 效果条目2(节点类型条件):持卡 + reward → 1★波提欧 + 封账;battle
  零发;无持卡 + reward 零发;已发 + reward 零双发;
- 随机态通道:直构容器恒未锚定 → 角色确定发放(rand=False)走
  write_logic_rand 通道(容器锚定态决定,与 discharge 族 rand=False
  现役形态同形)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    STRATEGY_GIFT_LEG_FACTION_COUNT,
    STRATEGY_GIFT_LEG_NEXT_REWARD_NODE,
    check_strategy_gift_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    bench_units_of,
)

_CARD = '迷之旅人'
_CHAR_L1 = '黄泉'
_CHAR_L2 = '波提欧'
_EQUIP = '星间旅人星徽'

_LATCH_L1 = f'{_CARD}#{STRATEGY_GIFT_LEG_FACTION_COUNT}'
_LATCH_L2 = f'{_CARD}#{STRATEGY_GIFT_LEG_NEXT_REWARD_NODE}'

#: 巡海游侠注册表全员四名(cw_chars 现值:乱破/不死途/黄泉/波提欧,
#: 判据档位 4 = 全员上阵恰达标;注册表派生断言在卡面档位锁内)。
_RAIDER_FOUR = ('乱破', '不死途', '黄泉', '波提欧')

_SIG_OBS = ChannelSig(family='obs', actor='TestGiftGrants')
_LSIG = ChannelSig(family='logic_action', actor='TestGiftGrants',
                   mode='compute')


def _gs(*, cards: list[str] | None = None,
        deployed: list[str] | None = None,
        bench: list[tuple[str, int]] | None = None,
        equips: list[str] | None = None) -> GameState:
    """直构容器(cards=None = 未持卡;'躺平' = 表外卡;deployed/bench/
    equips 传 None = 保持未观察,供宁缺勿造防御支;deployed = 上阵角色
    名集,bench = (角色, 星) 槽位)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if cards is not None:
        gs.write_logic(gs.active_strategies, list(cards),
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    if deployed is not None:
        front = [Unit(char_id=n, star=1) for n in deployed]
        gs.observe(gs.deployed,
                   DeployedView(front_slots=front, back_slots=[]),
                   sig=_SIG_OBS)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def _units(gs: GameState) -> list[tuple[str, int]]:
    return [(u.char_id, u.star) for u in bench_units_of(gs)]


def test_leg1_grants_char_and_equip_with_latch() -> None:
    """锁 2 主锁:4 巡海游侠上阵 + 持卡 + battle 节点窗 → 备战 2★黄泉
    (placed)+ 装备栏徽 + 封账恰一笔(一次性「一次讨论」语义;节点类型
    无关 = 状态条件任意窗评估)。"""
    gs = _gs(cards=[_CARD], deployed=list(_RAIDER_FOUR), bench=[],
             equips=[])
    out = check_strategy_gift_grants(gs, node_kind='battle', sig=_LSIG)
    assert out == (f'strategy_gift:{_CARD}#{STRATEGY_GIFT_LEG_FACTION_COUNT}',
                   ), '返回 = 腿1 evidence 串'
    assert _units(gs) == [(_CHAR_L1, 2)], '备战恰 1 只 2★黄泉(placed)'
    assert gs.equips.value == [_EQUIP], '携带装备入栏(非穿戴)'
    assert gs.strategy_grants_done.value == (_LATCH_L1,), '封账恰一笔'


def test_leg1_replay_no_double_grant() -> None:
    """锁 2 幂等:重复调用零双发(done 短路;板面维持达标亦不再发;
    同节点 kind 重放形态,sim 窗口重放同构)。"""
    gs = _gs(cards=[_CARD], deployed=list(_RAIDER_FOUR), bench=[],
             equips=[])
    check_strategy_gift_grants(gs, node_kind='battle', sig=_LSIG)
    out = check_strategy_gift_grants(gs, node_kind='battle', sig=_LSIG)
    assert out == (), '闩后零发放'
    assert _units(gs).count((_CHAR_L1, 2)) == 1, '黄泉不双发'
    assert gs.equips.value.count(_EQUIP) == 1, '徽不双发'
    assert gs.strategy_grants_done.value == (_LATCH_L1,), '封账不追加'


def test_leg1_below_threshold_no_write_no_latch() -> None:
    """锁 2 负锁:3 巡海游侠(差 1)→ 零写零闩(条件未满足下窗重查,
    与 done 已发短路不同,未达条件永驻重查)。"""
    gs = _gs(cards=[_CARD], deployed=list(_RAIDER_FOUR[:3]), bench=[],
             equips=[])
    seq0 = gs.write_seq
    out = check_strategy_gift_grants(gs, node_kind='battle', sig=_LSIG)
    assert out == () and gs.write_seq == seq0, '未达标零写'
    assert gs.strategy_grants_done.value in (None, ()), '不标 done'


def test_leg1_bench_same_name_not_counted() -> None:
    """锁 2 计数口径:同名单位在备战席(非上阵)不计入判据(参与 = 上阵,
    deployed_bond_counts 注册表单一源;bench 3 黄泉 + 上阵 3 巡海 = 3 差 1)。"""
    gs = _gs(cards=[_CARD], deployed=list(_RAIDER_FOUR[:3]),
             bench=[(_CHAR_L1, 1), (_CHAR_L1, 1), (_CHAR_L1, 1)],
             equips=[])
    out = check_strategy_gift_grants(gs, node_kind='battle', sig=_LSIG)
    assert out == (), 'bench 同名不计入判据'


def test_leg1_unobserved_containers_fail_closed() -> None:
    """锁 2 宁缺勿造:deployed 未观察(计数不可评估)/ equips 未观察
    (徽与角色拆拍引双发面,原子同窗)→ 零写零闩,下窗自愈。"""
    gs = _gs(cards=[_CARD], bench=[], equips=[])
    out = check_strategy_gift_grants(gs, node_kind='battle', sig=_LSIG)
    assert out == () and gs.strategy_grants_done.value in (None, ()), \
        'deployed 未观察零写零闩'
    gs2 = _gs(cards=[_CARD], deployed=list(_RAIDER_FOUR), bench=[])
    out2 = check_strategy_gift_grants(gs2, node_kind='battle', sig=_LSIG)
    assert out2 == () and gs2.strategy_grants_done.value in (None, ()), \
        'equips 未观察零写零闩(原子宁缺勿造)'
    assert _units(gs2) == [], '角色不落位'


def test_leg1_no_card_zero_write() -> None:
    """锁 2 负锁:未持卡/表外卡零写(白名单表外禁从效果原文自动猜装)。"""
    for cards in (None, ['躺平']):
        gs = _gs(cards=cards, deployed=list(_RAIDER_FOUR), bench=[],
                 equips=[])
        seq0 = gs.write_seq
        out = check_strategy_gift_grants(gs, node_kind='battle', sig=_LSIG)
        assert out == () and gs.write_seq == seq0, f'{cards}: 零命中'
        assert gs.strategy_grants_done.value in (None, ())


def test_leg2_reward_node_grants_with_latch() -> None:
    """锁 3 主锁:持卡 + reward 节点窗 → 备战 1★波提欧 + 封账(星级未标
    1★ 先验;「下一个奖励节点」判定 = kind 现值,持卡后首个可达 reward)。"""
    gs = _gs(cards=[_CARD], bench=[], equips=[])
    out = check_strategy_gift_grants(gs, node_kind='reward', sig=_LSIG)
    assert out == (f'strategy_gift:{_CARD}'
                   f'#{STRATEGY_GIFT_LEG_NEXT_REWARD_NODE}',), '腿2 evidence'
    assert _units(gs) == [(_CHAR_L2, 1)], '备战恰 1 名 1★波提欧'
    assert gs.strategy_grants_done.value == (_LATCH_L2,), '封账恰一笔'


def test_leg2_non_reward_node_zero_write() -> None:
    """锁 3 门控:非 reward 节点(battle/supply/encounter/boss)整腿跳过
    零写(「奖励节点」= 节点类型词分立判读,T-161 口径)。"""
    for kind in ('battle', 'supply', 'encounter', 'boss'):
        gs = _gs(cards=[_CARD], bench=[], equips=[])
        seq0 = gs.write_seq
        out = check_strategy_gift_grants(gs, node_kind=kind, sig=_LSIG)
        assert out == () and gs.write_seq == seq0, f'{kind}: 零写'
        assert gs.strategy_grants_done.value in (None, ())


def test_leg2_no_card_and_replay_guards() -> None:
    """锁 3 负锁:无持卡 + reward 零发;已发 + reward 零双发。"""
    gs = _gs(cards=None, bench=[], equips=[])
    seq0 = gs.write_seq
    assert check_strategy_gift_grants(gs, node_kind='reward',
                                      sig=_LSIG) == ()
    assert gs.write_seq == seq0 and gs.strategy_grants_done.value \
        in (None,), '无持卡零发'
    gs2 = _gs(cards=[_CARD], bench=[], equips=[])
    check_strategy_gift_grants(gs2, node_kind='reward', sig=_LSIG)
    out = check_strategy_gift_grants(gs2, node_kind='reward', sig=_LSIG)
    assert out == () and _units(gs2).count((_CHAR_L2, 1)) == 1, '零双发'
    assert gs2.strategy_grants_done.value == (_LATCH_L2,)


def test_leg2_legs_independent_latches() -> None:
    """两条效果条目闩独立:效果条目1 已发不封效果条目2(reward 窗两条效果条目各闩各的,复合键各段
    独立;反向同里)。"""
    gs = _gs(cards=[_CARD], deployed=list(_RAIDER_FOUR), bench=[],
             equips=[])
    check_strategy_gift_grants(gs, node_kind='battle', sig=_LSIG)
    assert gs.strategy_grants_done.value == (_LATCH_L1,), '前置:仅腿1 闩'
    check_strategy_gift_grants(gs, node_kind='reward', sig=_LSIG)
    assert gs.strategy_grants_done.value == (_LATCH_L1, _LATCH_L2), \
        '两腿复合键并存'
    assert _units(gs) == [(_CHAR_L1, 2), (_CHAR_L2, 1)], '两腿发放物并存'


def test_leg2_bench_unobserved_no_latch_retry_selfheal() -> None:
    """锁 3 拒落自愈:bench 未观察 → gain_character 拒落零写不闩
    (placed 才闩,观察到位后下窗重试)。"""
    gs = _gs(cards=[_CARD])
    out = check_strategy_gift_grants(gs, node_kind='reward', sig=_LSIG)
    assert out == () and gs.strategy_grants_done.value in (None, ()), \
        '拒落零写零闩'


def test_raider_faction_threshold_is_registry_truth() -> None:
    """判据档位注册表锚:「激活4」= FACTIONS 巡海游侠 tiers 4 人档在册
    (表值 4 与注册表档位一致,判据人数非凭空常量)。"""
    from sr_od.application.currency_war.data.cw_factions import FACTIONS
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_FACTION_COUNT_GRANTS,
    )
    faction, threshold, _char, _star, _equip = \
        STRATEGY_FACTION_COUNT_GRANTS[_CARD]
    assert threshold in FACTIONS[faction].tiers, \
        '判据人数 = FACTIONS 真实档位(4 人档在册)'
