"""货币战争 · 终局意向模块(cw_intention)测试 —— 纯逻辑,不依赖游戏。

strategy_v4 点0 单一规格源,锁行为:
- 信号分层①>②>③>④(五个触发例:env/strategy/family_bond/core_card/resource)
  + ⑤无信号兜底(绯英档);
- 撤销析取两出口:①核心断供证据(三条件合取:miss ≥ max(CORE_MISS_N,
  N_req 闭式)∧ 异线核心可达 ∧ 异线资产厚度 ≥ A_min)/ ②更高层信号+可达性对照;
- 窗口冻结语义:未开窗不计 miss;冻结超位面剩余节点 → 移出候选集、回⑤、不触发③;
- 强制锁线(P3 入口):核心在手或再遇窗口≤剩余节点的资产最厚方向;全不可达 → 降格终局;
- 锁后效果:只输出囤货目标集合(不改板上)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import (
    CORE_MISS_N,
    CROSS_LINE_SKELETON,
    FALLBACK_COMP_NAME,
    IntentionState,
    detect_signals,
    encounter_window_rounds,
    hoard_target_set,
    update_intention,
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
    """②类专属羁绊(ADR-0338 资格门):羁绊副产品计数不是直通资格——
    持续伤害×2 无资格不发②;持有资格(env 特邀专家:桑博 → 专家桑博DOT)
    才发;量子×2 恒不触发(希儿量子无②——量子/贝是放大器)。"""
    st = _state(board={'持续伤害': 2})
    lay = _layers(detect_signals(st))
    assert lay.get(2, set()) == set(), '无资格时②羁绊信号不得发射(锁直通=旧病)'
    st2 = _state(board={'持续伤害': 2}, active_env='特邀专家:桑博')
    lay2 = _layers(detect_signals(st2))
    assert '专家桑博DOT' in lay2.get(2, set())
    st3 = _state(board={'量子同频': 2})
    lay3 = _layers(detect_signals(st3))
    assert '希儿量子' not in lay3.get(2, set())


# ===== ADR-0338:直通终局线资格门(W85 五局同型根因修复)=====


def test_bond_lock_requires_qualification() -> None:
    """银河学者×2(经济凑数位)无资格 → 不锁大黑塔银河学者;P1 方向落
    配方过渡方向(p1_transition,ADR-0357——绯英兜底不辖 P1);
    持黑塔纪元(资格策略)→ 放行锁直通。"""
    st = _state(board={'银河学者': 2})          # 学者2 = 买 DOT 的副产品
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    assert hoard_target_set(st, ist).mode == 'p1_transition'
    st_q = _state(board={'银河学者': 2}, strategies=['黑塔纪元'])
    ist_q = update_intention(st_q, IntentionState())
    assert ist_q.phase == 'locked' and ist_q.locked_comp == '大黑塔银河学者'
    # env 侧资格同放行(银河学者概念股)
    st_e = _state(board={'银河学者': 2}, active_env='银河学者概念股')
    ist_e = update_intention(st_e, IntentionState())
    assert ist_e.locked_comp == '大黑塔银河学者'


def test_bond_lock_wan_di_rejected_core_card_still_legal() -> None:
    """夜之半神×2(燃血副产品)不锁万敌单C(003757 r6 病);
    贯穿件万敌到手:③锁线在 P2/P3 照旧([23] 合法路径),但 P1 被
    ADR-0341 资格门拦下(终局专属线 P1 锁向=板面饥饿,W97:hp 差 9-11)。"""
    st = _state(board={'夜之半神': 2})
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    # P1:贯穿件在手但无①类资格 → ③证据被门拦下,意向落配方过渡方向
    ist_p1 = update_intention(_state(bench=['万敌']), IntentionState())
    assert ist_p1.phase == 'unlocked' and ist_p1.locked_comp == ''
    assert hoard_target_set(_state(), ist_p1).mode == 'p1_transition'
    # P2:门不辖([21] 上场窗口/换血点都在 P1 后),③照旧
    ist2 = update_intention(_state(plane=2, bench=['万敌']), IntentionState())
    assert ist2.phase == 'locked' and ist2.locked_comp == '万敌单C'
    assert ist2.lock_layer == 3


def test_bond_lock_train_requires_strategy() -> None:
    """列车同行×2 不锁列车同行 comp(终局形态需列车4+姬子,024503 r7 病);
    持「本姑娘就是罗刹」(资格策略)→ 放行。"""
    st = _state(board={'列车同行': 2})
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    st_q = _state(board={'列车同行': 2}, strategies=['本姑娘就是罗刹'])
    ist_q = update_intention(st_q, IntentionState())
    assert ist_q.locked_comp == '列车同行'


def test_layer3_core_card_signal() -> None:
    """③核心卡:具名意向核心在店 → 对应线;P2 锁线(回归)。

    P1(W145/ADR-0357):③不再锁终局 comp(锁定产物=过渡配方体系对);
    希儿仅在店可见≠到手([23] 锁定由贯穿件=到手)→ 不构成配方证据,
    p1_pair 空、方向落四体系全集(p1_transition)。"""
    st = _state(plane=2, shop=['希儿'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '希儿量子' and s.kind == 'core_card'
               for s in sigs if s.layer == 3)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.locked_comp == '希儿量子'
    # P1:③证据不再锁 comp
    st1 = _state(shop=['希儿'])
    ist1 = update_intention(st1, IntentionState())
    assert ist1.phase == 'unlocked' and ist1.locked_comp == ''
    assert ist1.p1_pair == ()
    assert hoard_target_set(st1, ist1).mode == 'p1_transition'


def test_layer4_resource_signal() -> None:
    """④资源:升费链角色(银狼LV.999)到手 → 狼尊欢愉资源信号;
    P1 被 ADR-0341 资格门拦下(④与③同为「卡/资源到手」证据类)。"""
    st = _state(bench=['银狼LV.999'])
    sigs = detect_signals(st)
    assert not any(s.comp_name == '狼尊欢愉' and s.kind == 'resource'
                   for s in sigs if s.layer == 4), 'P1 终局专属线④证据应被门拦下'
    st2 = _state(plane=2, bench=['银狼LV.999'])
    sigs2 = detect_signals(st2)
    assert any(s.comp_name == '狼尊欢愉' and s.kind == 'resource'
               for s in sigs2 if s.layer == 4)


def test_layer5_fallback_no_signal() -> None:
    """⑤无信号兜底:无任何信号 → 不锁线;P2+ 囤货方向落绯英档
    (P1 配方方向见 W145 配方锁测试;绯英兜底不辖 P1,ADR-0357)。"""
    st = _state(plane=2)
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

#: 证据组 B 夹具:异线「万敌单C」(v2 家族)终局件 5 张在手(核心万敌
#: 可达;厚度=5×1★ + 骨架重叠×0.5=6.5 ≥ A_min=5,W423 测量值)。
EVIDENCE_BENCH = ['万敌', '千冶·刃', '长夜月', '刻律德菈', '缇宝']


def _default_n_req(core: str, level: int = 5) -> int:
    from sr_od.application.currency_war.cw_intention import (
        core_miss_n_required,
    )
    from sr_od.application.currency_war.decision_v2.registry import (
        DEFAULT_REGISTRY,
    )
    return core_miss_n_required(
        core, level, DEFAULT_REGISTRY.revoke_miss_tolerance_eps)


def test_revoke_exit1_requires_n_req_and_alt_asset_evidence() -> None:
    """撤销出口①三条件合取(设计=`.debug/temp/currency_war/
    w396_r2r3_design/DESIGN.md` R3.1,治 W386 BP1 门放行噪声换线):
    - 仅 miss 达拍死计数 CORE_MISS_N 而无异线资产证据 → 不开窗,
      计数继续累计(「核心短时缺货」的正常噪声不再进撤销);
    - miss 达 max(CORE_MISS_N, N_req) 且存在异线(核心可达+厚度
      ≥ A_min)→ 开窗降弱意向,事件行与证据字段携带 n_req/q/alt/thk
      (实机判读锚:无证据字段的开窗=守卫失效)。"""
    st = _state(plane=2, shop=['希儿'])   # 锁希儿量子(3费,lv5 开窗)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '希儿量子'
    gone = _state(plane=2)                # 窗口开、核心缺、无异线资产
    for _ in range(CORE_MISS_N + 5):
        update_intention(gone, ist)
        assert ist.phase == 'locked', '无证据组 B 时拍死计数不得开窗'
    assert ist.tracks['希儿量子'].miss_count == CORE_MISS_N + 5
    # 补证据组 B → 推进到 N_req 轮开窗
    gone_ev = _state(plane=2, bench=EVIDENCE_BENCH)
    total = max(CORE_MISS_N, _default_n_req('希儿'))
    for _ in range(total - (CORE_MISS_N + 5) - 1):
        update_intention(gone_ev, ist)
        assert ist.phase == 'locked'
    update_intention(gone_ev, ist)   # 第 N_req 轮:三条件齐 → 开窗
    assert ist.phase == 'weak' and ist.weak_comp == '希儿量子'
    assert ist.last_event.startswith('revoke:miss')
    assert 'alt=万敌单C' in ist.last_event
    ev = ist.revoke_evidence
    assert ev['alt_comp'] == '万敌单C'
    assert ev['asset_thickness'] >= ev['a_min'] >= 5.0
    assert ev['n_req'] == total and ev['q'] > 0 and ev['miss_count'] == total
    ht = hoard_target_set(gone_ev, ist)
    assert ht.mode == 'weak'
    assert set(ht.char_targets) == set(CROSS_LINE_SKELETON)


def test_revoke_exit2_higher_signal_with_reachability() -> None:
    """撤销出口②:更高层信号 + 可达性对照 → 撤;下轮新信号锁新线;不可达则不撤。
    (锁线场景设 P2:W145 起 P1 ③不锁 comp——希儿量子 P1 落配方方向。)"""
    st = _state(plane=2, shop=['希儿'])  # ③锁希儿量子(layer3)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '希儿量子'
    # 可达:plane2 剩余节点 > 姬子再遇窗 → 撤,降弱意向
    st2 = _state(plane=2, active_env='列车同行概念股', shop=['希儿'],
                 round_num=2)
    update_intention(st2, ist)
    assert ist.phase == 'weak' and ist.weak_comp == '希儿量子'
    assert 'higher' in ist.last_event
    update_intention(st2, ist)             # 直至新信号:env 再锁列车线
    assert ist.phase == 'locked' and ist.locked_comp == '列车同行'
    # 不可达:P3 末轮只剩少量节点,新信号核心再遇窗远超 → 层级高≠必换,不撤
    st3 = _state(shop=['希儿'], active_env='列车同行概念股',
                 plane=3, round_num=9)
    ist2 = update_intention(_state(plane=3, shop=['希儿']), IntentionState())
    assert ist2.locked_comp == '希儿量子'
    update_intention(st3, ist2)
    assert ist2.phase == 'locked' and ist2.locked_comp == '希儿量子'


def test_revoke_exit1_resets_on_core_visible() -> None:
    """核心再现 → miss 计数清零(不冤枉撤销)。(锁线场景设 P2,W145。)"""
    st = _state(plane=2, shop=['希儿'])
    ist = update_intention(st, IntentionState())
    gone = _state(plane=2)
    for _ in range(3):
        update_intention(gone, ist)
    assert ist.tracks['希儿量子'].miss_count == 3
    update_intention(_state(plane=2, shop=['希儿']), ist)
    assert ist.tracks['希儿量子'].miss_count == 0
    assert ist.phase == 'locked'


# ===== 窗口冻结语义 =====

def test_freeze_counter_and_eviction() -> None:
    """窗口未开不计 miss;冻结超位面剩余节点 → 移出候选集、回⑤、该轮不触发③。
    (锁线场景设 P2:W145 起 P1 ③不锁 comp;冻结语义本身位面无关。)"""
    st = _state(plane=2, shop=['希儿'])  # lv5 锁希儿量子(3费)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '希儿量子'
    frozen = _state(plane=2, level=3, shop=['希儿'])   # lv3 不出 3费 → 窗口关
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
    update_intention(_state(plane=2, shop=['希儿']), ist)
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
    """锁定 → 囤货集合切到意向线(角色件含核心/羁绊成员;装备件=到人配方−禁忌)。
    (万敌单C P1 ③被 ADR-0341 门拦,锁线场景设 P2。)"""
    st = _state(plane=2, bench=['万敌'])
    ist = update_intention(st, IntentionState())
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'locked'
    for c in get_comp('万敌单C').core_chars:
        assert c in ht.char_targets
    assert '高周波电锯' in ht.equip_targets
    assert '以牙还牙甲' not in ht.equip_targets   # equip_taboos(盾装连带禁)
    # 希儿线装备配方也在锁定时切过去(锁线场景设 P2:W145 起 P1 ③不锁)
    ist2 = update_intention(_state(plane=2, shop=['希儿']), IntentionState())
    ht2 = hoard_target_set(_state(plane=2), ist2)
    assert '火力风暴潮·特权' in ht2.equip_targets


def test_line_hoard_flows_members_in_target_set() -> None:
    """W65/ADR-0323:锁定万敌线 → 燃血(flows 流派)成员 刃/镜流/布洛妮娅
    进囤货目标集——旧版 _line_hoard 只查 c.factions,flows 成员被排除
    (W64 Ring1:燃血 8 成员 3/8 采购面缺失)。泛化修正:档位键与
    factions ∪ flows 全集交集,非万敌特判。(锁线场景设 P2:万敌单C
    的 P1 ③证据被 ADR-0341 资格门拦。)"""
    st = _state(plane=2, bench=['万敌'])
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '万敌单C'
    ht = hoard_target_set(st, ist)
    for name in ('刃', '镜流', '布洛妮娅'):
        assert name in ht.char_targets, \
            f'燃血(flows)成员 {name} 应在锁定线目标集内'


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


# ===== P1 过渡配方锁(W145/ADR-0357)=====


def test_p1_pair_lock_from_dot_assets() -> None:
    """P1 锁定产物=体系对:DOT 2 件在手(DOT 支持度 1.0)→ 锁
    (持续伤害, 列车同行)(第二体系按激活占比序);囤货=对成员集,
    mode=p1_pair;不锁任何终局 comp。"""
    st = _state(bench=['桑博', '卡芙卡'])
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    assert ist.p1_pair == ('列车同行', '持续伤害')
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'p1_pair'
    assert '桑博' in ht.char_targets          # DOT 成员
    assert '三月七' in ht.char_targets        # 列车成员(第二体系=目标件)
    assert not ht.equip_targets               # 过渡装备随意([20])


def test_p1_pair_shifts_with_assets() -> None:
    """体系对随资产重派生([20] 变体按来牌选):仙舟三人组到手(1.0)
    → 对切 (列车同行, 仙舟)——饮月双阵营(仙舟+列车)各系并计,
    列车以平手占比序挤掉 DOT(对内序=激活占比序)。"""
    ist = update_intention(_state(bench=['桑博']), IntentionState())
    assert ist.p1_pair == ('列车同行', '持续伤害')
    ist = update_intention(
        _state(bench=['桑博', '藿藿', '丹恒·饮月', '爻光']), ist)
    assert ist.p1_pair == ('列车同行', '仙舟')
    assert ist.last_event.startswith('p1_pair:')


def test_p1_pair_seele_owned_not_shop() -> None:
    """希儿系=到手才计支持度([23] 锁定由贯穿件=到手):店里可见不锁希儿系,
    bench 到手 → 希儿系进对。"""
    ist = update_intention(_state(shop=['希儿']), IntentionState())
    assert '希儿系' not in ist.p1_pair
    ist2 = update_intention(_state(bench=['希儿']), IntentionState())
    assert '希儿系' in ist2.p1_pair
    ht = hoard_target_set(_state(bench=['希儿']), ist2)
    assert '希儿' in ht.char_targets and '缇宝' in ht.char_targets


def test_p1_pair_boundary_empty_fallback() -> None:
    """边界:无任何过渡体系件(空窗期,[31]①)→ 不锁对;方向=四体系
    引擎件全集(p1_transition),不落绯英兜底(零引擎覆盖,W143)。"""
    st = _state(bench=['万敌'])   # 终局专属件,不构成体系支持
    ist = update_intention(st, IntentionState())
    assert ist.p1_pair == ()
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'p1_transition'
    for name in ('三月七', '桑博', '丹恒·饮月'):   # 三体系代表件
        assert name in ht.char_targets


def test_p1_pair_exits_at_p2() -> None:
    """进 P2:配方锁退场(p1_pair 清空),comp 锁定通道照旧
    (P2 锁定产物=终局 comp,回归)。"""
    ist = update_intention(_state(bench=['桑博']), IntentionState())
    assert ist.p1_pair == ('列车同行', '持续伤害')
    ist = update_intention(_state(plane=2), ist)
    assert ist.p1_pair == () and ist.last_event == 'p1_pair:exit_p1'
    assert hoard_target_set(_state(plane=2), ist).mode == 'fallback'


def test_p1_recipe_lock_off_restores_baseline(monkeypatch) -> None:
    """A/B 通道:P1_RECIPE_LOCK=False → P1 ③恢复锁终局 comp
    (W143 锚行为,sim 基线臂)。"""
    from sr_od.application.currency_war import cw_intention
    monkeypatch.setattr(cw_intention, 'P1_RECIPE_LOCK', False)
    st = _state(shop=['卡芙卡'])
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.locked_comp == 'DOT队'
    assert ist.p1_pair == ()
    assert hoard_target_set(st, ist).mode == 'locked'


def test_p1_pair_serialized_to_telemetry() -> None:
    """锁定目标数据形态显式可读(ADR-0357 约束基准契约):p1_pair 落
    ``serialize_intention`` 输出(decisions 行可读,后续「通道约束批」
    按此字段约束 opportunistic/bond_fallback——不隐式)。"""
    from sr_od.application.currency_war.cw_telemetry import serialize_intention
    ist = update_intention(_state(bench=['桑博']), IntentionState())
    d = serialize_intention(ist)
    assert d is not None and list(d['p1_pair']) == ['列车同行', '持续伤害']
    d2 = serialize_intention(update_intention(_state(), IntentionState()))
    assert d2 is not None and list(d2['p1_pair']) == []
