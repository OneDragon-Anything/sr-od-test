"""统一卖出候选评估器测试(三触发卖出判据件;统一让位优先级迭代 3.2 重写、
3.4 旧判据拆除收敛)。

规格单一源 = changes/2026-10-29-unified-priority/details/acquisition-
and-sell.md §3(三触发)+ priority-model §5(卖出取用形态):

- **统一序列消费**:各场景排序单一源 = ``criteria/priority.sell_order``
  (部署重排定型后的全局面序列,末位起取用);无场景专属池子【拍】;
- **身份过滤退役**(场景级:垫件谓词/仅一星过滤删除)+ **循环防线
  保留**(窗口段/L1 同轮禁卖/种子豁免经 sell_exclusions 装配——身份段
  已随 3.4 整段退役,装配自动收缩;合成素材守卫;空板止损守卫);
- **溢出全资格豁免保留**;**跨档止盈**保留为节末凑息场景参数;
  **凑息豁免**(roster-plane1-union design §2.2 第 5 项)同为节末
  凑息场景参数——候选池剔除线内未达标成员(为利息绝对不可卖,非
  排序后移;池空零动作 + 剔光帧观测键),被迫类场景不适用(动机
  二分);**线内身份集双层名单**(32 号稿 §2):
  过渡支 = transition_candidates 槽展开(与买面同源),
  豁免名单随 _member_names 装配改后自动覆盖过渡在建件;
- 3.4 退役面:shop_swap 场景行(3.2 六步流程替换)、c1_make_room
  场景行(C1 支拆除)、deploy_swap 冻结遗留路径与旧价值函数
  (sell_gold_equivalent/MERGE_PROGRESS_X2)/羁绊排序谓词/场上无关
  角色谓词——对应测试随批删除,退役语义以负断言锁存。

构帧纪律:统一序列以「部署重排定型」为前置——测试帧一律**板满**
(上阵数 = cap),否则 M1 空槽补位会把备战位件收进部署定型(档 1)、
候选池被部署需要面掏空,测不到让位序本体。

并段(**凑息/支付变现通道占位件物理门**,原 test_cw_sell_item_slot_
predicate 并入)保留;判据单一源 = ``predicates.item_slot_
unsellable`` 跨通道共享谓词。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
    cw4_members,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    transition_member_set,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell_candidates import (
    FACE_REGULAR,
    INTEREST_EXEMPT_DEPLETED_KEY,
    REJECT_NO_CANDIDATES,
    SCENE_SPECS,
    SELL_SCENARIOS,
    evaluate_sell_candidates,
    sell_line_membership,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.sell_gate import (
    EMPTY_BOARD_SELL_GUARD_KEY,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

# 注册表事实锚(测试种子选名依据,别换名后不解注册表;档号 = 十档口径,
# 完成品保护迭代 design §2.2):
# - 万敌(1费,夜之半神+燃血)/远坂凛(1费)= 兜底档 10 干净件(保护集外);
# - 黄泉(3费,减益)= 档 9 羁绊成员(保护集外);星期日 = 万金油(档 8,
#   常规面身份段排除件——仅自救面在池);停云 = 兜底档 10 干净件(自救面);
# - 花火/瓦尔特/三月七 = 列车同行候选成员(花火 need 2 未达标档 3、瓦尔特
#   need 1 已持有未到两星档 7);希儿(registry 核心)/卡芙卡(持续伤害系
#   保护档)= 常规面身份段排除件(3.4 身份段收缩前随装配照读);
# - 场上填充件族(镜流/Saber/Archer/杰帕德)= 档 1 部署定型面,统一
#   序列不进输出;备战位件与填充件**禁同名**(档 1 按角色名命中,
#   同名备战件会被部署需要面一并保护)。
# 板满前排中性填充族(阶段 5/6 起 = 注册表外杂名:零羁绊标签 + 非终局库
# ——统一部署搜索的枚举/评分对板件真实参与竞争,注册表填充名会被窗口
# 谓词(终局库件窗口未开)或羁绊标签卷入换血,中性板 = 搜索定型保持现板
# 的滞回载体)。名字表达纪律:注册表外名 = 「未知阵营/零羁绊」语义。
_LV8_FILL = tuple(f'杂板{i}' for i in range(1, 11))


def _mk_gs(**kw):
    """裸会话 + 容器种子(cw4_gs 家族缺省;node 观察使轮号可解析)。"""
    sess = StrategySession()
    gs = cw4_gs(sess, plane=1, round_num=2, node='prep', **kw)
    return sess, gs


def _fu(name: str, star: int = 1) -> Unit:
    """场上行域单位(DeployedView 行域元素 = 容器 Unit——别混用备战
    ``cw4_bc`` 的 BenchSlot 形)。"""
    return Unit(char_id=name, star=star)


def _names(cands) -> list[str]:
    return [c.char_id for c in cands]


def _board_full_gs(bench, *, level: int = 3, gold: int = 30,
                   front=None, back=None, plane: int = 1,
                   round_num: int = 2):
    """板满帧(统一序列前置:上阵数 = cap,备战位全部为部署外)。

    前排以中性填充件补满 cap(level ≤ 4 全前排,超出部分补后排);
    候选快照/锁定态由调用方按需置位。"""
    cap = min(level, 10)
    if front is None:
        fill = [_fu(_LV8_FILL[i % len(_LV8_FILL)]) for i in range(cap)]
        front = fill[:min(4, cap)]
        back = fill[4:cap]
    sess = StrategySession()
    gs = cw4_gs(sess, plane=plane, round_num=round_num, node='prep',
                level=level, gold=gold,
                bench=list(bench), front_row=list(front),
                back_row=list(back or []))
    return sess, gs


# ===== 场景闭集与 fail-closed 输入面 =====


class TestSceneClosedSet:

    def test_unknown_scenario_rejected(self):
        """场景闭集防线:枚举外值抛错(与 sell_gate SELL_CHANNELS 同款
        单一入口纪律;新场景先登记 SCENE_SPECS 再接入调用)。"""
        sess, gs = _board_full_gs([cw4_bc('停云')])
        with pytest.raises(ValueError, match='未知卖出场景'):
            evaluate_sell_candidates(gs, 'bogus_scene')

    def test_retired_scene_rows_absent(self):
        """退役场景行零残留(3.2/3.4/阶段 3):shop_swap 随席满置换账被
        统一获取让位评估整段替换退役(3.2,dismantle §2);c1_make_room
        随 C1 支拆除(3.4,dismantle §2 场景死行);deploy_swap 冻结遗留
        路径随旧价值函数退役(3.4——部署换人域判据本体 = kernel 直接
        消费,不经本评估器,生产零消费面);session_funding 随统一获取
        让位评估并入后退役(roster-plane1-union design §2.2 第 4 项:
        金不足与席满同一评估,禁再立筹资/凑金/腾位类场景)。"""
        for scene in ('shop_swap', 'c1_make_room', 'deploy_swap',
                      'session_funding', 'levelup_liquidate_prep'):
            assert scene not in SCENE_SPECS, scene


# ===== 统一序列消费(无场景专属池子;全局面;板满帧)=====


class TestUnifiedSequence:

    def _pool_gs(self):
        """板满 + 未锁候选帧:bench = 干净兜底档 10 件(万敌)+ 候选成员
        (瓦尔特);场上 = 中性填充三件(板满,cap = level 3)。gold 49 =
        凑息缺口 1(万敌 1 费退金 1 恰跨档,跨档止盈不排空本帧)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('瓦尔特')],
                                  gold=49)
        state_of(gs).line_candidates = ('列车同行·反震',)
        return sess, gs

    def test_full_board_pool_shared_by_guarded_scenes(self):
        """无场景专属池子【拍】(利息动机例外):常规面各场景同帧同池,
        场景间无池差分。entry_signals 退役后(entry_signals 整体退役,
        2026-11 用户终裁):候选线在建件(瓦尔特,列车·反震成员)被
        部署定型编入上场 → 档 1 名级保护(比凑息豁免更强);被换下的
        垫件(杂板3,deployed zone)落兜底档 10 入池——凑息豁免域相应
        收窄(线内未达标件几乎总在档 1,豁免无件可剔)。"""
        sess, gs = self._pool_gs()
        for scene in ('ore_make_room', 'node_end_interest', 'self_rescue'):
            cands, why = evaluate_sell_candidates(gs, scene)
            assert why == ''
            assert [(c.char_id, c.tier, c.zone) for c in cands] \
                == [('万敌', 10, 'bench'), ('杂板3', 10, 'deployed')], \
                f'{scene}: 同帧同池(豁免域收窄——瓦尔特档 1 编入)'

    def test_self_rescue_full_board_pool(self):
        """溢出豁免面 = 真全量:全池可见,按统一序列落位——entry_signals
        退役后成员件(卡芙卡/瓦尔特)上场进档 1 不在池,非成员羁绊件
        (希儿,档 9)殿后让位序末位;被换下垫件(杂板,兜底档 10)
        先让——「最不该卖的排末位」主题在垫件域承载(档 9 羁绊垫件
        末位;身份段退役后常规面不再排除任何件,3.4)。"""
        sess, gs = _board_full_gs(
            [cw4_bc('希儿'), cw4_bc('卡芙卡'), cw4_bc('瓦尔特')],
            level=5)
        state_of(gs).line_candidates = ('列车同行·反震',)
        # 常规面(晶矿)与自救同构:全池统一序列。
        for scene in ('ore_make_room', 'self_rescue'):
            cands, why = evaluate_sell_candidates(gs, scene)
            assert why == ''
            assert [(c.char_id, c.tier, c.zone) for c in cands] \
                == [('杂板4', 10, 'deployed'), ('杂板5', 10, 'deployed'),
                    ('希儿', 9, 'bench')], scene
            assert cands[-1].char_id == '希儿', \
                '统一序列:非成员羁绊垫件(档 9)排让位序末位'

    def test_priority_order_tiers_descend_in_yield_order(self):
        """让位序 = 统一序列反转(key 大者先卖):兜底档 10(1 费概率正
        与被换下垫件)先让;档 9(羁绊垫件)殿后。entry_signals 退役后
        万金油(星期日)与羁绊件(黄泉)均被统一部署搜索定型编入
        (L3 按件/按羁绊 → 上场 → 档 1 保护)——比万金油层让位更强的
        保护面;万金油档位模型本身仍由 test_priority 纯档位测试辖。"""
        sess, gs = _board_full_gs(
            [cw4_bc('停云'), cw4_bc('黄泉'), cw4_bc('星期日')], level=5)
        cands, why = evaluate_sell_candidates(gs, 'self_rescue')
        assert why == ''
        # 换轴后未终局锁定帧终局候选族参与部署枚举:黄泉/星期日/停云
        # 全被统一部署搜索定型编入(档 1),让位池 = 被换下垫件。
        assert [(c.char_id, c.tier, c.zone) for c in cands] \
            == [('杂板3', 10, 'deployed'), ('杂板4', 10, 'deployed'),
                ('杂板5', 10, 'deployed')], \
            '兜底档 10(被换下垫件);黄泉/星期日/停云档 1 编入不在池'

    def test_guarded_scene_priority_order(self):
        """常规面序列 = 统一序列(身份段已随 3.4 退役,无排除面):
        entry_signals 退役后万敌/黄泉均上场进档 1(名级保护),让位池
        主体 = 被换下垫件(兜底档 10 先让;十档口径 design §2.2)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('黄泉')], level=5)
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert [(c.char_id, c.tier, c.zone) for c in cands] \
            == [('杂板4', 10, 'deployed'), ('杂板5', 10, 'deployed')], \
            '让位序 = 优先级降序(万敌/黄泉档 1 编入,垫件先让)'


# ===== 取用观测载荷(统一让位优先级迭代 3.5;acquisition §6)=====


class TestTakeObservationPayload:
    """候选行观测载荷(tier/rng_tail_hit):取用观测键(档位分布/随机
    尾键命中)的数据源,键表 = telemetry/schema.py 键表节;判据零消费
    ——载荷失真只伤观测不伤行为,但键值 = sort_key 输出须逐位同源。"""

    def test_tier_attached_distinct_keys_no_tail_hit(self):
        """档位分量随键回填(十档口径 = 完成品保护迭代 design §2.2):
        entry_signals 退役后候选线在建件(瓦尔特)上场进档 1,让位池 =
        干净兜底档 10 件(万敌,bench)+ 被换下垫件(杂板3,deployed)
        ——两名件费档/星级子键互异 → 全池键互异
        → 随机尾键命中恒假(命中判定域 = 排序池,等价牌群才可能撞键)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('瓦尔特')],
                                  gold=49)
        state_of(gs).line_candidates = ('列车同行·反震',)
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert [(c.char_id, c.tier) for c in cands] == \
            [('万敌', 10), ('杂板3', 10)]
        assert not any(c.rng_tail_hit for c in cands)

    def test_tail_hit_true_within_equivalent_group(self):
        """随机尾键命中 = 全部子键同(仅随机尾键可分)的等价牌群内部
        定序实际生效:万敌/远坂凛 = 注册表 1 费兜底档 10 干净件(同费
        同星同档 → 键除尾全同;异名不触合成素材守卫)→ 池内键去尾互撞,
        取用件命中为真(命中哨兵语义,非等价件命中 = 键构造异常)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('远坂凛')],
                                  gold=49)
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert len(cands) == 2
        assert all(c.tier == 10 for c in cands)
        assert all(c.rng_tail_hit for c in cands)


# ===== 跨档止盈(节末凑息场景参数;design §2.4 保留行)=====


class TestInterestCrossTier:

    def test_only_refund_ge_gap_kept_priority_ordered(self):
        """跨档止盈:仅「单件退金 ≥ 到下一利息档缺口」者入序列,按
        统一序列取用(不再按「退金最小」选件——3.2 消费位改造);
        entry_signals 退役后万敌/黄泉(羁绊件)档 1 编入,让位池 =
        被换下垫件(退金恰跨档保留;缺口 3 = gold 7 下一档 10)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('黄泉')],
                                  gold=7, level=5)
        cands, why = evaluate_sell_candidates(gs, 'node_end_interest')
        assert why == ''
        assert _names(cands) == ['杂板4', '杂板5'], \
            '退金 ≥ 缺口垫件保留(万敌/黄泉档 1 编入不在池)'

    def test_no_next_tier_yields_empty(self):
        """满档(无下一利息档)= 无卖益,一件不卖(诚实空输出)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌')], gold=500, level=5)
        cands, why = evaluate_sell_candidates(gs, 'node_end_interest')
        assert cands == ()
        assert why == REJECT_NO_CANDIDATES

    def test_two_star_piece_enters_pool_when_crossing(self):
        """仅一星代理过滤退役【拍,总纲 §2.4】:2★ 件退金(变现价 ×3)
        跨档即入序列——星级让位代价由档位结构承载,不设资格过滤。"""
        sess, gs = _board_full_gs([cw4_bc('万敌', 2)], gold=9, level=5)
        cands, why = evaluate_sell_candidates(gs, 'node_end_interest')
        assert why == ''
        assert _names(cands) == ['万敌'], '2★ 件退金跨档入池(无仅一星门)'


# ===== 凑息豁免(阶段 4:roster-plane1-union design §2.2 第 5 项/§3 四用例)=====


class TestInterestMemberExemption:
    """凑息卖出豁免(design §3「凑息豁免测试」行):线内未达标成员
    (现行排序形态 = 档 3 升星主线/档 7 阵容强度,十档口径 design §2.2)
    为利息绝对不可卖——候选池剔除,非排序后移;达标线内件(≥ 目标星,
    完成品保护档 2/4 殿后,design §2.5-1/2)与非线内件照常参与;被迫类
    卖出(溢出/晶矿/获取让位)零豁免(动机二分:因席位/金币被迫按
    优先级让位的无豁免)。

    注册表事实锚:姬子·启行 = 列车同行 need 3(2★ 未达标 = 档 3 形态,
    3 费 2★ 退金 8)/花火 = need 2(2★ 达标 = 完成品保护档 2,2 费 2★
    退金 5)/瓦尔特 = need 1(1★ 未到两星 = 档 7 形态,5 费 1★ 退金 5);
    布洛妮娅
    (5 费)/万敌(1 费)= 非线内垫件。无覆写局利息帽 =
    ``cw_economy.DEFAULT_INTEREST_CAP`` 5(与等级无关),gold 2/5/9 →
    下一档线 10,缺口 8/5/1;level=5 只定板满 cap(min(level,10))
    与概率表键。
    """

    def _candidate_gs(self, bench, *, gold: int):
        """板满 + 未锁候选帧(列车同行;豁免集口径 = 候选 ∪ 配方 ∪
        锁定线,§2.1 名单一致——本类用候选支承载)。"""
        sess, gs = _board_full_gs(bench, level=5, gold=gold)
        state_of(gs).line_candidates = ('列车同行·反震',)
        return sess, gs

    def test_only_feasible_is_unmet_member_zero_action(self):
        """用例 1(豁免剔光 → 档 1 编入吞没豁免场景,entry_signals 退役
        行为演进):退役前构局(线内未达标成员在 bench)凑息帧豁免剔光
        → 零动作+剔光键;退役后线内在建件被部署定型编入上场(档 1 名
        级保护,比豁免更强)——凑息帧池 = 被换下垫件(退金 < 缺口全
        剔)→ 零动作但**非豁免剔光**(不落剔光键);豁免谓词逻辑本体
        仍在(直测 = test_priority.interest_exempt_member),消费域收窄
        至「档 1 外线内件」(上场锁锁住等边角形态)。金 2 → 缺口 8:
        姬子·启行 2★ 档 1 编入,垫件退金 < 8 全剔。"""
        sess, gs = self._candidate_gs(
            [cw4_bc('姬子·启行', 2), cw4_bc('布洛妮娅')], gold=2)
        ct: dict = {}
        cands, why = evaluate_sell_candidates(
            gs, 'node_end_interest', counters=ct)
        assert cands == ()
        assert why == REJECT_NO_CANDIDATES
        assert INTEREST_EXEMPT_DEPLETED_KEY not in ct, \
            '档 1 编入下的零动作 = 跨档止盈剔空(非豁免剔光)'
        # 对照:被迫类场景同帧垫件在池(动机二分——豁免/档 1 不辖被迫)。
        cands_ore, why_ore = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why_ore == ''
        assert _names(cands_ore), '被迫类(晶矿)垫件照卖'
        cands_rescue, _why_r = evaluate_sell_candidates(gs, 'self_rescue')
        assert _names(cands_rescue), '溢出自救垫件照卖'

    def test_non_member_pad_sold_when_member_exempted(self):
        """用例 2(卖垫件 → 档 1 编入形态):退役前「豁免剔线内件 →
        卖垫件」;退役后线内在建件档 1 编入(不在池),凑息池 = 被换下
        垫件照卖——「为利息不动在建阵容件」的动机语义由档 1 承载
        (更强保护面)。金 9 → 缺口 1:垫件退金恰跨档。"""
        sess, gs = self._candidate_gs(
            [cw4_bc('姬子·启行', 2), cw4_bc('布洛妮娅')], gold=9)
        cands, why = evaluate_sell_candidates(gs, 'node_end_interest')
        assert why == ''
        assert _names(cands), \
            '凑息池 = 被换下垫件照卖(线内件档 1 编入)'
        assert '姬子·启行' not in _names(cands)
        # 对照:晶矿场景(被迫类)同帧同池(无场景池差分)。
        cands_ore, _why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert set(_names(cands)) == set(_names(cands_ore))

    def test_met_member_participates(self):
        """用例 3(达标件照常 → 档 1 编入保护升级,entry_signals 退役
        行为演进):线内达标件(花火 2★)退役前按完成品保护档 2 参与
        凑息;退役后被部署定型编入上场(候选线 L1 增益)→ 档 1 名级
        保护(永不先卖,比凑息参与更强的保护)——凑息帧池 = 被换下
        垫件;花火谓词直测(未达标才豁免)由
        test_priority.interest_exempt_member 单元面承载。金 9 → 缺口 1:
        垫件退金恰跨档照卖。"""
        sess, gs = self._candidate_gs(
            [cw4_bc('花火', 2), cw4_bc('万敌')], gold=9)
        cands, why = evaluate_sell_candidates(gs, 'node_end_interest')
        assert why == ''
        assert _names(cands) == ['万敌', '杂板5'], \
            '达标成员档 1 编入(上场保护),凑息池 = 部署外垫件'

    def test_cross_tier_empty_frame_not_counted_depleted(self):
        """剔光键边界:可行池本空的帧(跨档止盈已剔空)零动作与豁免
        无关——不落观测键(键只计豁免真正翻转卖出→零动作的帧,
        design §2.2 第 3 项观测键登记点判读口径;entry_signals 退役后
        瓦尔特(线内在建件)上场进档 1,豁免域收窄)。"""
        sess, gs = self._candidate_gs(
            [cw4_bc('瓦尔特'), cw4_bc('布洛妮娅')], gold=9)
        ct: dict = {}
        # 跨档止盈剔空对照帧:全部候选退金 < 缺口(金 2 → 缺口 8)→
        # 提前返回,豁免不评估。
        gs2_sess, gs2 = self._candidate_gs(
            [cw4_bc('瓦尔特'), cw4_bc('布洛妮娅')], gold=2)
        cands2, why2 = evaluate_sell_candidates(
            gs2, 'node_end_interest', counters=ct)
        assert cands2 == () and why2 == REJECT_NO_CANDIDATES
        assert INTEREST_EXEMPT_DEPLETED_KEY not in ct, \
            '可行池本空帧不落剔光键(豁免未翻转行为)'
        # 非剔光帧(垫件在池)同样不落键。
        cands, why = evaluate_sell_candidates(
            gs, 'node_end_interest', counters=ct)
        assert why == '' and _names(cands)
        assert '瓦尔特' not in _names(cands), \
            '线内在建件档 1 编入(退役后不在卖池)'
        assert INTEREST_EXEMPT_DEPLETED_KEY not in ct


# (冻结遗留路径类 TestLegacyDeploySwapPath 与场上无关角色谓词类
#  TestFieldIrrelevantPredicate 已随 3.4 旧价值函数/deploy_swap 遗留
#  路径/is_field_irrelevant_unit 退役删除——锁定退役语义的负断言见
#  TestSceneClosedSet.test_retired_scene_rows_absent 与
#  TestIdentitySegmentRetired。)


# ===== 身份段退役负断言(3.4)=====


class TestIdentitySegmentRetired:
    """装配 A 身份段退役后的序列承载形态(dismantle §3 卖侧):
    标签命中件/registry 核心/保护档件不再被身份排除,统一按档位结构
    排序——候选线成员/骨架件由成员档族档 2/3/4/5/7 天然殿后(十档
    口径 design §2.2),非成员标签件按兜底档 10 概率先让
    (万敌单C 锁定帧,布洛妮娅 = 燃血标签件)。"""

    def _locked_gs(self, bench):
        sess = StrategySession()
        gs = cw4_gs(sess, plane=2, round_num=6, node='prep', level=5,
                    gold=38,
                    bench=[cw4_bc(n) for n in bench],
                    front_row=[_fu('万敌'), _fu(_LV8_FILL[0]),
                               _fu(_LV8_FILL[1]), _fu('停云')],
                    back_row=[_fu('三月七')])
        st = state_of(gs)
        st.plane2_started = True
        st.v3_intention = IntentionState(locked_comp='万敌单C')
        return gs

    def test_label_hit_piece_no_longer_excluded(self):
        """身份段退役申报:bench 标签命中件(布洛妮娅,燃血无已达成档)
        不被身份排除——entry_signals 退役后被部署编入上场进档 1(名级
        保护);零标签对照件(佩拉,非成员)在池按羁绊档 9 排序
        (十档口径 design §2.2)。"""
        gs = self._locked_gs(['布洛妮娅', '佩拉'])
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert '佩拉' in _names(cands), \
            '非成员标签件不被身份段排除(3.4 退役保持)'
        assert '布洛妮娅' not in _names(cands), \
            '布洛妮娅档 1 编入(entry_signals 退役后上场保护)'

    def test_registry_core_no_longer_excluded(self):
        """registry 核心件(希儿)不被身份排除(身份段退役;entry_signals
        退役后希儿〔单卡体系〕与佩拉〔羁绊件〕均被部署编入上场 →
        档 1 名级保护,不在卖池)——「非成员件不被身份排除」的排序
        承载见 label_hit 条(佩拉档 9 在池);本构局希儿+佩拉双上场,
        池 = 被换下垫件(同档等价群,尾键命中)。"""
        gs = self._locked_gs(['希儿', '佩拉'])
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert _names(cands) == ['杂板1', '杂板2']
        assert '希儿' not in _names(cands) and '佩拉' not in _names(cands), \
            '希儿/佩拉档 1 编入(entry_signals 退役后上场保护)'


# ===== 线内身份集单一准入(阶段 1:roster-plane1-union design §2.1/§3)=====


class TestSellLineMembershipSingleAdmission:
    """sell_line_membership 三景(换轴后口径;双层名单 = 32 号稿 §2):
    终局锁定 = 锁定线单源(过渡层在锁定写入点退役清空);位面 2 未终局
    锁定 = 过渡支照常活跃(行为申报 6);未锁定 = 实候选并集 ∪ 过渡层
    贡献名单(transition_member_union 单一源,与买面同源)。"""

    def test_final_lock_line_only_transition_retired(self):
        """终局锁定:身份集 = 锁定线单源——换轴后「P1 锁定局并集」形态
        随终局锁定写入点过渡层退役清空而收敛(槽位残留不消费)。"""
        sess, gs = _mk_gs()
        st = state_of(gs)
        st.target_comp = get_comp('双王圣杯')
        st.transition_candidates = ('DOT2+列车2',)
        assert sell_line_membership(gs) \
            == frozenset(cw4_members(get_comp('双王圣杯')))
        assert '卡芙卡' not in sell_line_membership(gs), \
            '终局锁定帧过渡槽残留不入线内集(退役清空)'

    def test_p2_unlocked_recipe_branch_stays_active(self):
        """位面 2 未终局锁定:过渡支照常贡献(换轴行为申报 6——旧
        「进位面 2 即退出」随生命周期挂钩终局锁定事件废除)。"""
        sess, gs = _mk_gs()
        st = state_of(gs)
        st.plane2_started = True
        st.transition_candidates = ('DOT2+列车2',)
        assert '卡芙卡' in sell_line_membership(gs), \
            '位面 2 未终局锁定帧过渡支照常贡献'

    def test_unlocked_union_candidates_and_recipe(self):
        """未锁定:身份集 = 实候选三线成员并集 ∪ 过渡层贡献名单(条目
        见即买集展开;混合块含点名件与放大器全体)。"""
        sess, gs = _mk_gs()
        st = state_of(gs)
        st.line_candidates = ('列车同行·反震',)
        st.transition_candidates = ('希儿量2+希儿贝2',)
        from sr_od.application.currency_war.kernel.cw_intention import (
            transition_entry_of,
        )
        expected = set(cw4_members(get_comp('列车同行·反震'))) \
            | transition_member_set(transition_entry_of('希儿量2+希儿贝2'))
        assert sell_line_membership(gs) == frozenset(expected)
        assert '瓦尔特' in sell_line_membership(gs), '候选支(列车同行·反震)'
        assert '佩拉' in sell_line_membership(gs), '过渡支(放大器成员)'


class TestP1LockedSellPoolNarrowing:
    """行为申报用例(32 号稿 §2 P1 锁定局行为申报;过渡支口径 = 32 号稿
    §2):过渡成员从「最先让路」收窄为「殿后保护」——
    修复前过渡成员不在锁定帧名单,落兜底档最先卖;修复后落凑两星
    过程保护档,同帧万金油垫件先让(档号 = 十档口径:兜底档 10〔旧
    八档档 8〕/凑两星档 7〔旧档 5〕/万金油档 8〔旧档 6〕,design
    §2.2)。"""

    def test_recipe_member_retired_in_final_lock_frame(self):
        """终局锁定帧(换轴):过渡层退役——过渡槽残留不消费,卡芙卡
        退出成员档名单落兜底档;星期日照纳入(万金油)。旧「P1 锁定局
        过渡成员殿后保护」形态随终局锁定即退役收敛(位面 2 未终局锁定
        帧的保护形态由 test_p2_unlocked 系承载)。"""
        sess, gs = _board_full_gs(
            [cw4_bc('卡芙卡'), cw4_bc('星期日')], level=5)
        st = state_of(gs)
        st.target_comp = get_comp('列车同行·反震')
        st.transition_candidates = ('DOT2+列车2',)
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert '星期日' not in _names(cands), \
            '万金油档 1 编入不在池'


# ===== 空板守卫(as-built 纳入;全场景)=====


class TestEmptyBoardGuard:

    def test_empty_board_blocks_all_scenes(self):
        """deployed = 0 帧全部卖出场景哑火(prep_pipeline §1 第 0 步
        as-built 申报:守卫语义不收窄;拒因键与 sell_gate 单一源同键)。"""
        sess, gs = _mk_gs(bench=[cw4_bc('停云'), cw4_bc('卡芙卡')])
        for scene in ('self_rescue', 'ore_make_room',
                      'node_end_interest'):
            cands, why = evaluate_sell_candidates(gs, scene)
            assert cands == (), scene
            assert why == EMPTY_BOARD_SELL_GUARD_KEY, scene


# ===== 场景注册表参数(通道谱系 + 跨档止盈参数)=====


class TestSceneTableParams:

    def test_scene_table_covers_legacy_channels(self):
        """通道谱系行完整性:凑息→节末凑息 / m4_fuel→晶矿;
        line_switch/projection 不进评估器场景表;shop_swap(3.2)/
        c1_make_room、deploy_swap(3.4)已随退役删除;levelup_liquidate_prep
        已随凑金链整删退役(用户裁定 2026-10-30:不存在升级卖牌凑金,
        保持最大压牌库,钱够了再升——金不足帧恒 defer 零卖出);
        session_funding 与 funding 通道已随统一获取让位评估并入后退役
        (roster-plane1-union design §2.2 第 4 项:金不足与席满同一
        评估,场景/通道/专属计数整链删除)。"""
        assert SCENE_SPECS['node_end_interest'].legacy_channel == 'interest'
        assert SCENE_SPECS['ore_make_room'].legacy_channel == 'm4_fuel'
        assert 'line_switch' not in {s.legacy_channel for s in
                                     SCENE_SPECS.values()}
        assert 'projection' not in {s.legacy_channel for s in
                                    SCENE_SPECS.values()}
        # 常规面装配通道 ∈ 现行通道闭集(闭集外值会被 sell_exclusions 拒收)
        from sr_od.application.currency_war.strategies.impl.mandate_v1.sell_gate import (
            SELL_CHANNELS,
        )
        for spec in SCENE_SPECS.values():
            if spec.legacy_channel is not None:
                assert spec.legacy_channel in SELL_CHANNELS
        assert 'funding' not in SELL_CHANNELS, \
            'funding 通道随筹资场景退役,闭集零残留'
        assert len(SELL_SCENARIOS) == 3   # 三触发三场景(闭集 5→3 收尾)

    def test_interest_scene_carries_cross_tier_param(self):
        """跨档止盈 = 节末凑息独有场景参数(acquisition §3 表):其余
        场景恒 False。"""
        assert SCENE_SPECS['node_end_interest'].cross_tier_only is True
        for name, spec in SCENE_SPECS.items():
            if name != 'node_end_interest':
                assert spec.cross_tier_only is False, name

    def test_interest_scene_carries_member_exemption_param(self):
        """凑息豁免 = 节末凑息独有场景参数(roster-plane1-union design
        §2.2 第 5 项):仅利息动机场景声明池过滤;被迫类(溢出/晶矿)
        恒 False——动机二分,豁免只挂「为利息」类。"""
        assert SCENE_SPECS['node_end_interest'].exempt_unmet_members is True
        for name, spec in SCENE_SPECS.items():
            if name != 'node_end_interest':
                assert spec.exempt_unmet_members is False, name

    def test_face_regular_channel_closure_anchor_list(self):
        """通道闭集锚:FACE_REGULAR 通道逐一点名(SCENE_SPECS 闭集派生)
        ——新增常规面通道会撑破本清单(shop_swap 已随置换账替换退役
        〔3.2〕;c1_make_room/deploy_swap 已随身份段/旧价值函数退役
        删除〔3.4〕;levelup_liquidate_prep 已随凑金链整删退役;
        session_funding 已随统一获取让位评估并入后退役〔roster-plane1-
        union design §2.2 第 4 项〕)。"""
        regular = {s for s, spec in SCENE_SPECS.items()
                   if spec.face == FACE_REGULAR}
        assert regular == {'ore_make_room', 'node_end_interest'}


# ============================================================
# 并段:凑息/支付变现通道占位件物理门(原 test_cw_sell_item_slot_
# predicate 并入;判据单一源 = predicates.item_slot_unsellable)
# ============================================================

_COMP = '列车同行·反震'
_K = ('线内件',)


def _bc(name: str, star: int = 1) -> BenchSlot:
    """容器占席条目(P4 载体迁移:身份/星级/槽号随内嵌 Unit)。"""
    return BenchSlot(kind='unit',
                     unit=Unit(char_id=name, star=star))


def _item(slot: int = 1, star: int = 1) -> BenchSlot:
    """占位件(假环境同款形态):kind 非 unit、无内嵌单位。"""
    return BenchSlot(kind='tome', unit=None)


def _gate_state(bench: list, deployed: list | None = None) -> dict:
    # 上阵缺省非空板:空板帧会被空板止损守卫
    # (sell_gate.empty_board_sell_blocked,ADR-0636)先于资格循环短路,
    # 测不到本段辖的物理门本体;plane=2 压掉 P1 血线禁令域(凑息)。
    # 资格循环输入 = 容器占席条目(本段辖的载体);返回 = ``_bsb``
    # kwargs(桥配方,旧帧缺省 gold=0/hp 直写)。
    if deployed is None:
        deployed = [Unit(char_id='前线', star=1)]
    return {'plane': 2, 'hp': 50, 'bench': list(bench),
            'front_row': list(deployed)}


def _fuel_pair() -> tuple[str, str]:
    """两个线外无后台效果注册表名(注册表现查,禁手抄)。"""
    km = set(line_members(get_comp(_COMP)))
    pool = [n for n, c in CHARACTERS.items()
            if n not in km and not getattr(c, 'bench_effect', '') and c.cost]
    assert len(pool) >= 2, '注册表缺少线外无效果角色(测试前提失效)'
    return pool[0], pool[1]


class TestInterestItemSlotGate:
    """凑息资格循环占位件物理门(gap 帧:gold < g*)。"""

    def test_placeholder_excluded_real_fuel_kept(self):
        """占位件不入资格集,同帧真燃料件照卖(修复前形态 = 两槽全入);
        仅占位件可「凑」的帧 = 诚实空集(占位件槽永不入发射列)。
        调用帧 = gold 9(下一利息档线 10,缺口 1,燃料件退金 ≥ 1 可行)
        ——跨档止盈判据(单件退金 ≥ 缺口,单一源 = kernel
        next_interest_line)下 gold 0 帧(缺口 10)无可行件,
        'no_tier_gain' 零发出,资格面不可观测。"""
        fuel_a, _fuel_b = _fuel_pair()
        bench = [_item(slot=1), _bc(fuel_a)]
        slots, key = sell.sell_for_interest(
            9, bench, 5, _K, state=_bsb(**_gate_state(bench)))
        assert key == ''
        assert slots == [1]   # 紧缩位键(0 基)
        # 仅占位件帧 = 诚实空集(资格集空,拒因保持 '')
        bench_only = [_item(slot=1)]
        slots2, key2 = sell.sell_for_interest(
            9, bench_only, 5, _K, state=_bsb(**_gate_state(bench_only)))
        assert slots2 == []
        assert key2 == ''

    def test_below_tier_gap_no_sell(self):
        """跨档止盈:单件退金 < 到下一利息档缺口 = 零利息收益,一件不卖
        ('no_tier_gain')——同档卖出纯亏持有资产,旧判据(卖到饱和线
        g*=50)会把 bench 卖光。"""
        fuel_a, _fuel_b = _fuel_pair()
        bench = [_item(slot=1), _bc(fuel_a)]
        # gold 0:下一档线 10,缺口 10,燃料件退金(cost ≤ 5)< 缺口
        slots, key = sell.sell_for_interest(
            0, bench, 5, _K, state=_bsb(**_gate_state(bench)))
        assert slots == []
        assert key == 'no_tier_gain'
        # 同判据的反向帧:缺口 1(金 9)即发射(上一条已校验,此处钉
        # 「缺口与退金的 ≥ 关系」边界:退金恰等缺口可行)
        slots3, key3 = sell.sell_for_interest(
            9, [_bc(fuel_a)], 5, _K, state=_bsb(
                **_gate_state([_bc(fuel_a)])))
        assert key3 == ''
        assert len(slots3) == 1


class TestFundingItemSlotGate:
    """筹资资格循环占位件物理门 + 止盈贪心不消费占位件退金。"""

    def test_placeholder_not_used_to_cover_gap(self):
        """缺口可覆盖帧:修复前 = 占位件(退金 3)+ 真件凑满贪心;
        修复后 = 只用真件,占位件槽不入发射列、缺口诚实短欠;仅占位件
        可「筹」的帧 = 诚实空集。"""
        fuel_a, _fuel_b = _fuel_pair()
        bench = [_item(slot=1), _bc(fuel_a)]
        slots, key = sell.funding_support_sell(
            0, 5, bench, _K, state=_bsb(**_gate_state(bench)))
        assert key == ''
        assert slots == [1]   # 紧缩位键(0 基)
        # 仅占位件帧 = 诚实空集
        bench_only = [_item(slot=1)]
        slots2, key2 = sell.funding_support_sell(
            0, 5, bench_only, _K, state=_bsb(**_gate_state(bench_only)))
        assert slots2 == []
        assert key2 == ''
