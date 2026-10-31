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
    pair_target_comp,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell_candidates import (
    FACE_REGULAR,
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

# 注册表事实锚(测试种子选名依据,别换名后不解注册表):
# - 万敌(1费,夜之半神+燃血)/远坂凛(1费)= 档 8 干净件(保护集外);
# - 黄泉(3费,减益)= 档 7 羁绊成员(保护集外);星期日 = 万金油(档 6,
#   常规面身份段排除件——仅自救面在池);停云 = 档 8 干净件(自救面);
# - 花火/瓦尔特/三月七 = 列车同行候选成员(花火 need 2 档 2、瓦尔特
#   need 1 档 5);希儿(registry 核心)/卡芙卡(持续伤害系保护档)=
#   常规面身份段排除件(3.4 身份段收缩前随装配照读);
# - 场上填充件族(镜流/Saber/Archer/杰帕德)= 档 1 部署定型面,统一
#   序列不进输出;备战位件与填充件**禁同名**(档 1 按角色名命中,
#   同名备战件会被部署需要面一并保护)。
_LV8_FILL = ('镜流', 'Saber', 'Archer', '杰帕德')   # 板满前排中性填充族


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
        单一入口纪律;新场景先登记 SCENE_SPECS 再接线)。"""
        sess, gs = _board_full_gs([cw4_bc('停云')])
        with pytest.raises(ValueError, match='未知卖出场景'):
            evaluate_sell_candidates(gs, 'bogus_scene')

    def test_retired_scene_rows_absent(self):
        """退役场景行零残留(3.2/3.4):shop_swap 随席满置换账被六步流程
        整段替换退役(3.2,dismantle §2);c1_make_room 随 C1 支拆除
        (3.4,dismantle §2 场景死行);deploy_swap 冻结遗留路径随旧价值
        函数退役(3.4——部署换人域判据本体 = kernel 直接消费,不经本
        评估器,生产零消费面)。"""
        for scene in ('shop_swap', 'c1_make_room', 'deploy_swap'):
            assert scene not in SCENE_SPECS, scene


# ===== 统一序列消费(无场景专属池子;全局面;板满帧)=====


class TestUnifiedSequence:

    def _pool_gs(self):
        """板满 + 未锁候选帧:bench = 干净档 8 件(万敌)+ 候选成员
        (瓦尔特);场上 = 中性填充三件(板满,cap = level 3)。gold 49 =
        凑息缺口 1(万敌 1 费退金 1 恰跨档,跨档止盈不排空本帧)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('瓦尔特')],
                                  gold=49)
        state_of(gs).line_candidates = ('列车同行',)
        return sess, gs

    def test_full_board_pool_shared_by_guarded_scenes(self):
        """无场景专属池子【拍】:常规面各场景同帧同池,场景间无池差分;
        部署定型内(填充件)= 档 1 不进输出,备战位件按统一序列让位。"""
        sess, gs = self._pool_gs()
        for scene in ('ore_make_room', 'session_funding',
                      'levelup_liquidate_prep', 'node_end_interest'):
            cands, why = evaluate_sell_candidates(gs, scene)
            assert why == '', scene
            # 身份段已随 3.4 退役:候选成员瓦尔特不再被义务基座排除,
            # 按统一序列落位(档 3 未获取成员 = 序列高位 = 让位序末);
            # 场上件 = 档 1 不进输出 → 候选 = 万敌+瓦尔特(万敌先让)。
            assert set(_names(cands)) == {'万敌', '瓦尔特'}, scene
            assert cands[0].zone == 'bench'
            assert cands[0].char_id == '万敌', \
                '档 8 干净件先让(成员件殿后)'

    def test_self_rescue_full_board_pool(self):
        """溢出豁免面 = 真全量:全池可见,按统一序列落位——成员件受
        档 5 保护排让位序末位(最不该卖);身份段退役后常规面不再排除
        成员/registry/保护档件(3.4:常规面 = 自救面的序列差消失,
        差异仅剩循环防线装配)。"""
        sess, gs = _board_full_gs(
            [cw4_bc('希儿'), cw4_bc('卡芙卡'), cw4_bc('瓦尔特')],
            level=5)
        state_of(gs).line_candidates = ('列车同行',)
        # 常规面(晶矿):身份段退役,全池按统一序列。
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert set(_names(cands)) == {'希儿', '卡芙卡', '瓦尔特'}
        assert cands[-1].char_id == '瓦尔特', \
            '统一序列:阵容成员(档 5)排让位序末位(永不先卖)'
        # 自救:真全量 + 统一序列(同构)。
        cands2, why2 = evaluate_sell_candidates(gs, 'self_rescue')
        assert why2 == ''
        assert set(_names(cands2)) == {'希儿', '卡芙卡', '瓦尔特'}
        assert cands2[-1].char_id == '瓦尔特'

    def test_priority_order_tiers_descend_in_yield_order(self):
        """让位序 = 统一序列反转(key 大者先卖):档 8(1 费概率正)
        → 档 7(羁绊)→ 档 6(万金油)——自救豁免面全池可见。"""
        sess, gs = _board_full_gs(
            [cw4_bc('停云'), cw4_bc('黄泉'), cw4_bc('星期日')], level=5)
        cands, why = evaluate_sell_candidates(gs, 'self_rescue')
        assert why == ''
        assert _names(cands) == ['停云', '黄泉', '星期日'], \
            '档 8 → 档 7 → 档 6(让位序 = 优先级降序)'

    def test_guarded_scene_priority_order(self):
        """常规面序列 = 统一序列(身份段已随 3.4 退役,无排除面):
        档 8(1 费概率正先让)→ 档 7。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('黄泉')], level=5)
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert _names(cands) == ['万敌', '黄泉'], \
            '档 8 → 档 7(让位序 = 优先级降序)'


# ===== 取用观测载荷(统一让位优先级迭代 3.5;acquisition §6)=====


class TestTakeObservationPayload:
    """候选行观测载荷(tier/rng_tail_hit):取用观测键(档位分布/随机
    尾键命中)的数据源,键表 = telemetry/schema.py 键表节;判据零消费
    ——载荷失真只伤观测不伤行为,但键值 = sort_key 输出须逐位同源。"""

    def test_tier_attached_distinct_keys_no_tail_hit(self):
        """档位分量随键回填:让位序首位 = 档 8 干净件(万敌),末位 =
        成员持有件(瓦尔特,need 1 已持有未到两星 = 档 5);全池键互异
        → 随机尾键命中恒假(命中判定域 = 排序池,等价牌群才可能撞键)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('瓦尔特')],
                                  gold=49)
        state_of(gs).line_candidates = ('列车同行',)
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert [(c.char_id, c.tier) for c in cands] == \
            [('万敌', 8), ('瓦尔特', 5)]
        assert not any(c.rng_tail_hit for c in cands)

    def test_tail_hit_true_within_equivalent_group(self):
        """随机尾键命中 = 全部子键同(仅随机尾键可分)的等价牌群内部
        定序实际生效:万敌/远坂凛 = 注册表 1 费档 8 干净件(同费同星
        同档 → 键除尾全同;异名不触合成素材守卫)→ 池内键去尾互撞,
        取用件命中为真(命中哨兵语义,非等价件命中 = 键构造异常)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('远坂凛')],
                                  gold=49)
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert len(cands) == 2
        assert all(c.tier == 8 for c in cands)
        assert all(c.rng_tail_hit for c in cands)


# ===== 跨档止盈(节末凑息场景参数;design §2.4 保留行)=====


class TestInterestCrossTier:

    def test_only_refund_ge_gap_kept_priority_ordered(self):
        """跨档止盈:仅「单件退金 ≥ 到下一利息档缺口」者入序列,按
        统一序列取用(不再按「退金最小」选件——3.2 消费位改造);
        缺口 3(gold 7,下一档 10):1 费退金 1 < 3 排除,3 费退金 3
        恰等缺口保留。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('黄泉')],
                                  gold=7, level=5)
        cands, why = evaluate_sell_candidates(gs, 'node_end_interest')
        assert why == ''
        assert _names(cands) == ['黄泉'], '退金 < 缺口件排除(1费退金 1 < 3)'

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


# (冻结遗留路径类 TestLegacyDeploySwapPath 与场上无关角色谓词类
#  TestFieldIrrelevantPredicate 已随 3.4 旧价值函数/deploy_swap 遗留
#  路径/is_field_irrelevant_unit 退役删除——锁定退役语义的负断言见
#  TestSceneClosedSet.test_retired_scene_rows_absent 与
#  TestIdentitySegmentRetired。)


# ===== 身份段退役负断言(3.4)=====


class TestIdentitySegmentRetired:
    """装配 A 身份段退役后的序列承载形态(dismantle §3 卖侧):
    标签命中件/registry 核心/保护档件不再被身份排除,统一按档位结构
    排序——候选线成员/骨架件由档 2/3/5/7 天然殿后,非成员标签件按
    档 8 概率先让(万敌单C 锁定帧,布洛妮娅 = 燃血标签件)。"""

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
        入池(不再被终局键集标签分支排除),按档 8 排序;零标签对照件
        (佩拉)同帧在池。"""
        gs = self._locked_gs(['布洛妮娅', '佩拉'])
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert '布洛妮娅' in _names(cands), \
            '标签命中件仍被身份段排除(3.4 退役失效)'
        assert '佩拉' in _names(cands)

    def test_registry_core_no_longer_excluded(self):
        """registry 核心件(希儿)入常规面候选(身份段退役——核心件
        保护改由档位结构承载:锁定线成员 = 档 2/3/5 殿后)。"""
        gs = self._locked_gs(['希儿', '佩拉'])
        cands, why = evaluate_sell_candidates(gs, 'session_funding')
        assert why == ''
        assert '希儿' in _names(cands)


# ===== 线内身份集单一准入(阶段 1:roster-plane1-union design §2.1/§3)=====


class TestSellLineMembershipSingleAdmission:
    """sell_line_membership 三景(名单单一准入):配方支 = 槽位直读 +
    读前判窗(plane2_started_of),锁定不是退出条件——P1 锁定局 =
    锁定线 ∪ 配方并集;P2 配方支退出;未锁定 = 候选并集 ∪ 配方。"""

    def _recipe_comp(self):
        comp = pair_target_comp(('持续伤害', '希儿系'))
        assert comp is not None
        return comp

    def test_locked_p1_union_locked_line_and_recipe(self):
        """P1 锁定局:身份集 = 锁定线名单 ∪ 配方成员(修复前锁定分支
        只有锁定线——配方成员被排出线内集,防线/投影口径漏自己人)。"""
        sess, gs = _mk_gs()
        st = state_of(gs)
        st.target_comp = get_comp('双王圣杯')
        st.opening_recipe_comp = self._recipe_comp()
        expected = set(cw4_members(get_comp('双王圣杯'))) \
            | set(cw4_members(st.opening_recipe_comp))
        assert sell_line_membership(gs) == frozenset(expected)
        assert '卡芙卡' in sell_line_membership(gs), \
            '纯配方成员入线内集(注册表现查:卡芙卡 ∉ 双王圣杯)'

    def test_p2_recipe_branch_exits(self):
        """P2(plane2_started=True):配方支恒空集——槽位残留不消费
        (判窗在直读之前);身份集退回锁定线单源。"""
        sess, gs = _mk_gs()
        st = state_of(gs)
        st.target_comp = get_comp('双王圣杯')
        st.opening_recipe_comp = self._recipe_comp()
        st.plane2_started = True
        assert sell_line_membership(gs) \
            == frozenset(cw4_members(get_comp('双王圣杯')))
        assert '卡芙卡' not in sell_line_membership(gs), \
            '进位面 2 配方残留不入线内集'

    def test_unlocked_union_candidates_and_recipe(self):
        """未锁定:身份集 = 候选 top3 三线成员并集 ∪ 配方成员(修复前
        未锁定分支只有候选并集,缺配方支)。"""
        sess, gs = _mk_gs()
        st = state_of(gs)
        st.line_candidates = ('列车同行',)
        st.opening_recipe_comp = self._recipe_comp()
        expected = set(cw4_members(get_comp('列车同行'))) \
            | set(cw4_members(st.opening_recipe_comp))
        assert sell_line_membership(gs) == frozenset(expected)
        assert '瓦尔特' in sell_line_membership(gs), '候选支(列车同行)'
        assert '卡芙卡' in sell_line_membership(gs), '配方支'


class TestP1LockedSellPoolNarrowing:
    """行为申报用例(design §2.5 P1 锁定局行):配方成员从「最先让路」
    收窄为「殿后保护」——修复前配方成员不在锁定帧名单,落档 8 兜底
    最先卖;修复后落档 5(成员保护),同帧万金油垫件(档 6)先让。"""

    def test_recipe_member_protected_in_locked_frame(self):
        sess, gs = _board_full_gs(
            [cw4_bc('卡芙卡'), cw4_bc('星期日')], level=5)
        st = state_of(gs)
        st.target_comp = get_comp('列车同行')
        st.opening_recipe_comp = pair_target_comp(('持续伤害', '希儿系'))
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert _names(cands) == ['星期日', '卡芙卡'], \
            '配方成员(档 5)殿后,万金油垫件(档 6)先让——不再误卖自己人'


# ===== 空板守卫(as-built 收编;全场景)=====


class TestEmptyBoardGuard:

    def test_empty_board_blocks_all_scenes(self):
        """deployed = 0 帧全部卖出场景哑火(prep_pipeline §1 第 0 步
        as-built 申报:守卫语义不收窄;拒因键与 sell_gate 单一源同键)。"""
        sess, gs = _mk_gs(bench=[cw4_bc('停云'), cw4_bc('卡芙卡')])
        for scene in ('self_rescue', 'ore_make_room', 'session_funding',
                      'node_end_interest', 'levelup_liquidate_prep'):
            cands, why = evaluate_sell_candidates(gs, scene)
            assert cands == (), scene
            assert why == EMPTY_BOARD_SELL_GUARD_KEY, scene


# ===== 场景注册表参数(通道谱系 + 跨档止盈参数)=====


class TestSceneTableParams:

    def test_scene_table_covers_legacy_channels(self):
        """通道谱系行完整性:凑息→节末凑息 / 筹资→会话内筹资+备战升级
        凑金 / m4_fuel→晶矿;line_switch/projection 不进评估器场景表;
        shop_swap(3.2)/c1_make_room、deploy_swap(3.4)已随退役删除。"""
        assert SCENE_SPECS['node_end_interest'].legacy_channel == 'interest'
        assert SCENE_SPECS['session_funding'].legacy_channel == 'funding'
        assert SCENE_SPECS['levelup_liquidate_prep'].legacy_channel == 'funding'
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
        assert len(SELL_SCENARIOS) == 5   # 三触发五场景(3.4 收敛后)

    def test_interest_scene_carries_cross_tier_param(self):
        """跨档止盈 = 节末凑息独有场景参数(acquisition §3 表):其余
        场景恒 False。"""
        assert SCENE_SPECS['node_end_interest'].cross_tier_only is True
        for name, spec in SCENE_SPECS.items():
            if name != 'node_end_interest':
                assert spec.cross_tier_only is False, name

    def test_face_regular_channel_closure_anchor_list(self):
        """通道闭集锚:FACE_REGULAR 通道逐一点名(SCENE_SPECS 闭集派生)
        ——新增常规面通道会撑破本清单(shop_swap 已随置换账替换退役
        〔3.2〕;c1_make_room/deploy_swap 已随身份段/旧价值函数退役
        删除〔3.4〕)。"""
        regular = {s for s, spec in SCENE_SPECS.items()
                   if spec.face == FACE_REGULAR}
        assert regular == {'ore_make_room', 'session_funding',
                           'node_end_interest', 'levelup_liquidate_prep'}


# ============================================================
# 并段:凑息/支付变现通道占位件物理门(原 test_cw_sell_item_slot_
# predicate 并入;判据单一源 = predicates.item_slot_unsellable)
# ============================================================

_COMP = '列车同行'
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
