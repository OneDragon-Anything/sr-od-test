"""货币战争 · 终局意向模块(cw_intention)测试 —— 纯逻辑,不依赖游戏。

strategy_v4 点0 单一规格源,锁行为:
- 信号分层①>②>③>④(五个触发例:env/strategy/family_bond/core_card/resource)
  + ⑤无信号兜底(绯英档);
- 撤销析取两出口:①核心 N=6 轮不可得(只计开窗轮)/ ②更高层信号+可达性对照;
- 窗口冻结语义:未开窗不计 miss;冻结超位面剩余节点 → 移出候选集、回⑤、不触发③;
- 强制锁线(P3 入口):核心在手或再遇窗口≤剩余节点的资产最厚方向;全不可达 → 降格终局;
- 锁后效果:只输出囤货目标集合(不改板上)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import (
    CROSS_LINE_SKELETON,
    FALLBACK_COMP_NAME,
    CORE_MISS_N,
    detect_signals,
    encounter_window_rounds,
    hoard_target_set,
    update_intention,
    IntentionState,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState, ShopCard


def _state(**kw) -> GameState:
    s = GameState()
    s.plane = kw.get('plane', 1)
    s.round_num = kw.get('round_num', 1)
    s.level = kw.get('level', 5)
    s.active_env = kw.get('active_env', '')
    s.active_strategies = list(kw.get('strategies', []))
    for name in kw.get('bench', []):
        ch = CHARACTERS.get(name)
        s.bench.append(BenchChar(slot=len(s.bench), char_id=name,
                                 faction=ch.factions[0] if ch and ch.factions else '?',
                                 star=kw.get('bench_star', 1)))
    for name in kw.get('shop', []):
        ch = CHARACTERS.get(name)
        s.shop.append(ShopCard(x=len(s.shop), name=name,
                               faction=ch.factions[0] if ch and ch.factions else '?',
                               cost=ch.cost if ch else 3))
    for fac, n in kw.get('board', {}).items():
        s.board[fac] = n
    return s


def _layers(sigs: list) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    for s in sigs:
        out.setdefault(s.layer, set()).add(s.comp_name)
    return out


# ===== 信号五层触发例 =====

def test_layer1_env_signal() -> None:
    """①策略驱动-环境:列车同行概念股 → 列车同行;且锁线。"""
    st = _state(active_env='列车同行概念股')
    sigs = detect_signals(st)
    l1 = [s for s in sigs if s.layer == 1]
    assert any(s.comp_name == '列车同行' and s.kind == 'env' for s in l1)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.locked_comp == '列车同行'
    assert ist.lock_layer == 1 and not ist.forced


def test_layer1_strategy_signal() -> None:
    """①策略驱动-投资策略:黑塔纪元(augment)→ 大黑塔银河学者。"""
    st = _state(strategies=['黑塔纪元'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '大黑塔银河学者' and s.kind == 'strategy'
               for s in sigs if s.layer == 1)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '大黑塔银河学者'


def test_layer2_family_bond_signal() -> None:
    """②类专属羁绊:持续伤害×2 → DOT 家族线;量子×2 不触发(希儿量子无②——量子/贝是放大器)。"""
    st = _state(board={'持续伤害': 2})
    lay = _layers(detect_signals(st))
    assert {'DOT队', '专家桑博DOT'} <= lay.get(2, set())
    st2 = _state(board={'量子同频': 2})
    lay2 = _layers(detect_signals(st2))
    assert '希儿量子' not in lay2.get(2, set())


def test_layer3_core_card_signal() -> None:
    """③核心卡:具名意向核心在店 → 对应线;锁线。"""
    st = _state(shop=['希儿'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '希儿量子' and s.kind == 'core_card'
               for s in sigs if s.layer == 3)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.locked_comp == '希儿量子'


def test_layer4_resource_signal() -> None:
    """④资源:升费链角色(银狼LV.999)到手 → 狼尊欢愉资源信号。"""
    st = _state(bench=['银狼LV.999'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '狼尊欢愉' and s.kind == 'resource'
               for s in sigs if s.layer == 4)


def test_layer5_fallback_no_signal() -> None:
    """⑤无信号兜底:无任何信号 → 不锁线;囤货方向落绯英档。"""
    st = _state()
    assert detect_signals(st) == []
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'fallback'
    assert '绯英' in ht.char_targets
    assert get_comp(FALLBACK_COMP_NAME) is not None


def test_layer_priority_order() -> None:
    """①>②>③>④:同轮多层并存取最高层(①)。"""
    st = _state(active_env='列车同行概念股', board={'持续伤害': 3},
                shop=['希儿'], bench=['银狼LV.999'])
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '列车同行' and ist.lock_layer == 1


# ===== 撤销两出口 =====

def test_revoke_exit1_core_miss_n() -> None:
    """撤销出口①:意向核心 6 轮不可得(开窗轮)→ 降级弱意向,只囤跨线骨架。"""
    st = _state(shop=['希儿'])           # 锁希儿量子(3费,lv5 开窗)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '希儿量子'
    gone = _state()                       # 店里/bench 无希儿,窗口仍开
    for _ in range(CORE_MISS_N - 1):
        update_intention(gone, ist)
        assert ist.phase == 'locked'      # 前 5 轮只计数
    update_intention(gone, ist)
    assert ist.phase == 'weak' and ist.weak_comp == '希儿量子'
    assert ist.last_event.startswith('revoke:miss')
    ht = hoard_target_set(gone, ist)
    assert ht.mode == 'weak'
    assert set(ht.char_targets) == set(CROSS_LINE_SKELETON)


def test_revoke_exit2_higher_signal_with_reachability() -> None:
    """撤销出口②:更高层信号 + 可达性对照 → 撤;下轮新信号锁新线;不可达则不撤。"""
    st = _state(bench=['万敌'])           # ③锁万敌单C(layer3)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '万敌单C'
    # 可达:plane1 剩 26 节点 > 姬子再遇窗(~13 轮)→ 撤,降弱意向
    st2 = _state(active_env='列车同行概念股', bench=['万敌'], round_num=2)
    update_intention(st2, ist)
    assert ist.phase == 'weak' and ist.weak_comp == '万敌单C'
    assert 'higher' in ist.last_event
    update_intention(st2, ist)             # 直至新信号:env 再锁列车线
    assert ist.phase == 'locked' and ist.locked_comp == '列车同行'
    # 不可达:P3 末轮只剩 1 节点,新信号核心再遇窗远超 → 层级高≠必换,不撤
    st3 = _state(bench=['万敌'], active_env='列车同行概念股',
                 plane=3, round_num=9)
    ist2 = update_intention(_state(bench=['万敌']), IntentionState())
    assert ist2.locked_comp == '万敌单C'
    update_intention(st3, ist2)
    assert ist2.phase == 'locked' and ist2.locked_comp == '万敌单C'


def test_revoke_exit1_resets_on_core_visible() -> None:
    """核心再现 → miss 计数清零(不冤枉撤销)。"""
    st = _state(shop=['希儿'])
    ist = update_intention(st, IntentionState())
    gone = _state()
    for _ in range(3):
        update_intention(gone, ist)
    assert ist.tracks['希儿量子'].miss_count == 3
    update_intention(_state(shop=['希儿']), ist)
    assert ist.tracks['希儿量子'].miss_count == 0
    assert ist.phase == 'locked'


# ===== 窗口冻结语义 =====

def test_freeze_counter_and_eviction() -> None:
    """窗口未开不计 miss;冻结超位面剩余节点 → 移出候选集、回⑤、该轮不触发③。"""
    st = _state(shop=['希儿'])            # lv5 锁希儿量子(3费)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '希儿量子'
    frozen = _state(level=3, shop=['希儿'])   # lv3 不出 3费 → 窗口关
    # 轮 2-5:frozen 1..4,均未超位面剩余(轮5 剩 5)→ 仍锁;miss 恒 0(未开窗不计)
    for r in range(2, 6):
        frozen.round_num = r
        update_intention(frozen, ist)
        assert ist.phase == 'locked'
        assert ist.tracks['希儿量子'].miss_count == 0
    # 轮 6:frozen=5 > 位面剩余 4 → 逐出;店里有希儿但③被排除 → 回⑤兜底
    frozen.round_num = 6
    update_intention(frozen, ist)
    assert ist.phase == 'unlocked' and '希儿量子' in ist.evicted
    assert ist.last_event.startswith('evict:frozen')
    assert hoard_target_set(frozen, ist).mode == 'fallback'
    # 之后希儿再出现,③信号也被 evicted 过滤(等同信号未发生)
    update_intention(_state(shop=['希儿']), ist)
    assert ist.phase == 'unlocked' and ist.locked_comp == ''


# ===== 强制锁线与降格终局 =====

def test_forced_lock_p3_thickest() -> None:
    """P3 入口无意向:可达候选中资产最厚方向强制锁线(非 carry 件堆出的厚度)。"""
    st = _state(plane=3, level=4, bench=['千冶·刃', '缇宝'])   # 万敌线终局件×2,无③信号
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.forced
    assert ist.locked_comp == '万敌单C'   # 厚度 2+0.5 > DOT 系 1.5
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'forced' and '万敌' in ht.char_targets


def test_forced_lock_demote_endgame() -> None:
    """全候选不可达(P3 末轮+低等级+无资产)→ 降格终局标记;absorbing,新信号不解锁。"""
    st = _state(plane=3, round_num=9, level=3)
    ist = update_intention(st, IntentionState())
    assert ist.demoted_endgame and ist.last_event == 'demote:endgame'
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'demoted_endgame'
    assert set(ht.char_targets) == set(CROSS_LINE_SKELETON)
    # absorbing:此后任何信号不再改意向(承认下限,「赢不了就少输」)
    update_intention(_state(active_env='列车同行概念股'), ist)
    assert ist.demoted_endgame and ist.locked_comp == ''


# ===== 锁后效果(只改囤货方向) =====

def test_lock_effect_hoard_target_set() -> None:
    """锁定 → 囤货集合切到意向线(角色件含核心/羁绊成员;装备件=到人配方−禁忌)。"""
    st = _state(bench=['万敌'])
    ist = update_intention(st, IntentionState())
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'locked'
    for c in get_comp('万敌单C').core_chars:
        assert c in ht.char_targets
    assert '高周波电锯' in ht.equip_targets
    assert '以牙还牙甲' not in ht.equip_targets   # equip_taboos(盾装连带禁)
    # 希儿线装备配方也在锁定时切过去
    ist2 = update_intention(_state(shop=['希儿']), IntentionState())
    ht2 = hoard_target_set(_state(), ist2)
    assert '火力风暴潮·特权' in ht2.equip_targets


def test_encounter_window_monotonic() -> None:
    """再遇窗近似:窗口未开=inf;低费窗更近(静态近似 sanity)。"""
    assert encounter_window_rounds('希儿', 3) == float('inf')
    assert encounter_window_rounds('万敌', 5) < encounter_window_rounds('希儿', 5)


def test_cross_line_skeleton_source() -> None:
    """跨线骨架名单 = W16 八张 + 双身份两张(点0 弱意向囤货集单一源)。"""
    assert set(CROSS_LINE_SKELETON) == {
        '瓦尔特', '千冶·刃', '符玄', '星期日', '开拓者·记忆',
        '花火', '缇宝', '刻律德菈', '三月七', '藿藿',
    }
