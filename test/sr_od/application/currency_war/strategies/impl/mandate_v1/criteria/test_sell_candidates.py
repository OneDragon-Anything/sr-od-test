"""统一卖出候选评估器测试(三触发卖出判据件;统一让位优先级迭代 3.2 重写)。

规格单一源 = changes/2026-10-29-unified-priority/details/acquisition-
and-sell.md §3(三触发)+ priority-model §5(卖出取用形态):

- **统一序列消费**:各场景排序单一源 = ``criteria/priority.sell_order``
  (部署重排定型后的全局面序列,末位起取用);无场景专属池子【拍】;
- **身份过滤退役**(场景级:垫件谓词/仅一星过滤删除)+ **循环防线
  保留**(窗口段/L1 同轮禁卖/种子豁免经 sell_exclusions 装配——身份段
  收缩归 3.4,收敛前随装配照读;合成素材守卫;空板止损守卫);
- **溢出全资格豁免保留**;**跨档止盈**保留为节末凑息场景参数;
- deploy_swap = 冻结遗留路径(部署换人域不动;价值函数/羁绊谓词仅剩
  该路径消费,生产零消费面)。

构帧纪律:统一序列以「部署重排定型」为前置——测试帧一律**板满**
(上阵数 = cap),否则 M1 空槽补位会把备战位件收进部署定型(档 1)、
候选池被部署需要面掏空,测不到让位序本体。

并段(**凑息/支付变现通道占位件物理门**,原 test_cw_sell_item_slot_
predicate 并入)与 **冻结遗留路径测试**(价值函数构成/provisional 槽/
deploy_swap 羁绊规则项)保留;判据单一源 = ``predicates.item_slot_
unsellable`` 跨通道共享谓词。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import (
    reencounter_window_frames,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell_candidates import (
    FACE_REGULAR,
    INTEREST_MARGIN_PER_ROUND,
    MERGE_PROGRESS_X2_SLOT,
    REJECT_NO_CANDIDATES,
    REJECT_SWAP_CTX_MISSING,
    SCENE_SPECS,
    SELL_SCENARIOS,
    evaluate_sell_candidates,
    is_field_irrelevant_unit,
    sell_gold_equivalent,
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


def _swap_ctx(gs) -> SwapPlanContext:
    """换人判定语境(测试手装:fenced 义务臂 + 未锁帧 + 空目标视图——
    现行判据在该语境下对非 core/非 target 件放行;装配链本体不在本
    测试面)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        bench_entries_of,
        deployed_rows_of,
    )
    front, back = deployed_rows_of(gs)
    return SwapPlanContext(
        target_factions=frozenset(), target_cores=frozenset(),
        fw_carry=frozenset(), locked_factions=frozenset(),
        protect_names=frozenset(), membership=frozenset(),
        fresh_buys=frozenset(), board={}, deployed=[*front, *back],
        bench=bench_entries_of(gs), cap=10, fenced_on=True, locked=False)


# ===== 场景闭集与 fail-closed 输入面 =====


class TestSceneClosedSet:

    def test_unknown_scenario_rejected(self):
        """场景闭集防线:枚举外值抛错(与 sell_gate SELL_CHANNELS 同款
        单一入口纪律;新场景先登记 SCENE_SPECS 再接线)。"""
        sess, gs = _board_full_gs([cw4_bc('停云')])
        with pytest.raises(ValueError, match='未知卖出场景'):
            evaluate_sell_candidates(gs, 'bogus_scene')

    def test_shop_swap_scene_retired_with_six_step_flow(self):
        """shop_swap 场景行随席满置换账被六步流程整段替换退役(3.2,
        dismantle §2——六步流程直通 priority.sell_order,不经本评估器);
        c1_make_room 消费位归 3.4 C1 支拆除,收敛前保留。"""
        assert 'shop_swap' not in SCENE_SPECS
        assert 'c1_make_room' in SCENE_SPECS

    def test_deploy_swap_without_ctx_fail_closed(self):
        """换人场景缺判定语境 ⇒ 拒评估(现行判据 ctx=None 返回全放行是
        fail-open 形态,评估器侧拒收——资格判据禁缺语境放行)。"""
        sess, gs = _board_full_gs([cw4_bc('停云')])
        cands, why = evaluate_sell_candidates(gs, 'deploy_swap')
        assert cands == ()
        assert why == REJECT_SWAP_CTX_MISSING


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
                      'levelup_liquidate_prep', 'node_end_interest',
                      'c1_make_room'):
            cands, why = evaluate_sell_candidates(gs, scene)
            assert why == '', scene
            # 常规面身份段(义务基座 = 候选成员,3.4 收缩前照读)排除
            # 瓦尔特;场上件 = 档 1 不进输出 → 候选 = 万敌单件。
            assert _names(cands) == ['万敌'], scene
            assert cands[0].zone == 'bench'

    def test_self_rescue_full_board_pool(self):
        """溢出豁免面 = 真全量:身份段排除件(候选成员瓦尔特/registry
        核心希儿/保护档卡芙卡)全部在池,按统一序列落位——成员件受
        档 5 保护排让位序末位(最不该卖),身份排除件按档 8 概率先让。"""
        sess, gs = _board_full_gs(
            [cw4_bc('希儿'), cw4_bc('卡芙卡'), cw4_bc('瓦尔特')],
            level=5)
        state_of(gs).line_candidates = ('列车同行',)
        # 常规面(晶矿):身份段三通道排除全生效 → 空候选
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert (cands, why) == ((), REJECT_NO_CANDIDATES)
        # 自救:真全量 + 统一序列(成员档 5 殿后 = 最不该卖)。
        cands, why = evaluate_sell_candidates(gs, 'self_rescue')
        assert why == ''
        assert set(_names(cands)) == {'希儿', '卡芙卡', '瓦尔特'}
        assert cands[-1].char_id == '瓦尔特', \
            '统一序列:阵容成员(档 5)排让位序末位(永不先卖)'

    def test_priority_order_tiers_descend_in_yield_order(self):
        """让位序 = 统一序列反转(key 大者先卖):档 8(1 费概率正)
        → 档 7(羁绊)→ 档 6(万金油)——自救豁免面全池可见。"""
        sess, gs = _board_full_gs(
            [cw4_bc('停云'), cw4_bc('黄泉'), cw4_bc('星期日')], level=5)
        cands, why = evaluate_sell_candidates(gs, 'self_rescue')
        assert why == ''
        assert _names(cands) == ['停云', '黄泉', '星期日'], \
            '档 8 → 档 7 → 档 6(让位序 = 优先级降序)'

    def test_guarded_scene_priority_order_excluding_identity_segment(self):
        """常规面序列 = 身份段过滤后的统一序列(身份段收缩归 3.4):
        档 8(1 费概率正先让)→ 档 7;万金油(星期日)∈ 保护集,常规面
        身份段排除(仅自救面在池,见 :meth:`test_priority_order_tiers_
        descend_in_yield_order`)。"""
        sess, gs = _board_full_gs([cw4_bc('万敌'), cw4_bc('黄泉')], level=5)
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert _names(cands) == ['万敌', '黄泉'], \
            '档 8 → 档 7(让位序 = 优先级降序)'


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


# ===== 冻结遗留路径(deploy_swap;价值函数/羁绊谓词的现役消费面)=====


class TestLegacyDeploySwapPath:

    def test_deploy_swap_field_and_bench_pool(self):
        """部署换人 = 场上 ∪ 备战席(冻结遗留:现行 swap 判据,不走
        装配 A 的线内排除;判据与排序逐位同 3.2 前)。"""
        sess, gs = _board_full_gs([cw4_bc('停云'), cw4_bc('瓦尔特')],
                                  level=5)
        state_of(gs).line_candidates = ('列车同行',)
        cands, why = evaluate_sell_candidates(gs, 'deploy_swap',
                                              swap_ctx=_swap_ctx(gs))
        assert why == ''
        assert sorted(_names(cands)) == sorted(
            ['停云', '瓦尔特'] + ['镜流', 'Saber', 'Archer', '杰帕德',
                                  '镜流']), \
            '冻结遗留路径:场上 ∪ 备战席全池(判据排序逐位同 3.2 前)'

    def test_bond_drop_rule_orders_after_non_drop(self):
        """羁绊排序规则项(不折金;冻结遗留):卖后掉当前羁绊档的场上件
        排在全部不掉档件之后——命运圣杯 2 人恰在 2 档(卖一掉档)整体
        置后于无关件万敌(不掉档)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep', level=5,
                    bench=[], front_row=[_fu('万敌')],
                    back_row=[_fu('远坂凛'), _fu('Saber')])
        cands, why = evaluate_sell_candidates(gs, 'deploy_swap',
                                              swap_ctx=_swap_ctx(gs))
        assert why == ''
        assert cands[0].char_id == '万敌'
        assert cands[0].bond_drop is False
        assert {c.char_id for c in cands[1:]} == {'远坂凛', 'Saber'}
        assert all(c.bond_drop is True for c in cands[1:])

    def test_value_function_composition_frozen(self):
        """价值函数构成(冻结遗留路径专用;五场景已切统一序列,函数
        生产零消费面,3.4 拆除):金当量 = 变现价 + 再遇期权 + 合成进度
        (单张 = 自身再遇期权),量纲期望从注册表单一源现算。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            bench_char_cost,
            sell_refund,
        )
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep', level=5,
                    bench=[cw4_bc('远坂凛')], front_row=[_fu('万敌')])
        unit = cw4_bc('远坂凛').unit
        expected = (
            sell_refund(1, bench_char_cost(unit, gs))
            + reencounter_window_frames(5, 1, 1) * INTEREST_MARGIN_PER_ROUND
            + reencounter_window_frames(5, 1, 1) * INTEREST_MARGIN_PER_ROUND)
        assert sell_gold_equivalent(gs, unit) == pytest.approx(expected)

    def test_merge_pair_multiplier_slot(self):
        """合成进度 ×2 系数走 provisional 槽(冻结遗留路径专用):
        缺省 ×1(fail-closed 线性)→ 注入 2.0 后差一张对价值增量恰为
        一个再遇期权;值域守卫拒绝 [1,2] 外注入。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep', level=5,
                    bench=[cw4_bc('万敌'), cw4_bc('万敌')],
                    front_row=[_fu('停云')])
        unit = cw4_bc('万敌').unit
        before = sell_gold_equivalent(gs, unit)
        window = reencounter_window_frames(5, 1, 2) * INTEREST_MARGIN_PER_ROUND
        try:
            provisional.inject(MERGE_PROGRESS_X2_SLOT,
                               provisional.CalibValue(value=2.0))
            assert sell_gold_equivalent(gs, unit) == pytest.approx(before + window)
            with pytest.raises(ValueError):
                provisional.inject(MERGE_PROGRESS_X2_SLOT,
                                   provisional.CalibValue(value=3.0))
        finally:
            provisional.reset(MERGE_PROGRESS_X2_SLOT)


# ===== 场上无关角色谓词(节末凑息观测键反事实支的现役消费)=====


class TestFieldIrrelevantPredicate:

    def test_irrelevant_vs_contributor_vs_line_member(self):
        """无关 = 非线内 ∧ 非有效羁绊贡献件:单挂万敌无关;命运圣杯
        2 人(激活 2 档)为贡献件;线内件(锁定线/候选成员)非无关。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep', level=5,
                    bench=[], front_row=[_fu('万敌'), _fu('远坂凛')],
                    back_row=[_fu('Saber')])
        state_of(gs).line_candidates = ('列车同行',)
        assert is_field_irrelevant_unit(gs, cw4_bc('万敌').unit, 'front') is True
        assert is_field_irrelevant_unit(gs, cw4_bc('远坂凛').unit, 'front') is False
        assert is_field_irrelevant_unit(gs, cw4_bc('Saber').unit, 'back') is False
        # 线内件(三月七 ∈ 列车同行名单)非无关——即使羁绊不激活
        _s2, gs2 = _mk_gs(bench=[], front_row=[_fu('三月七')])
        state_of(gs2).line_candidates = ('列车同行',)
        assert is_field_irrelevant_unit(gs2, cw4_bc('三月七').unit,
                                        'front') is False


# ===== 空板守卫(as-built 收编;全场景)=====


class TestEmptyBoardGuard:

    def test_empty_board_blocks_all_scenes(self):
        """deployed = 0 帧全部卖出场景哑火(prep_pipeline §1 第 0 步
        as-built 申报:守卫语义不收窄;拒因键与 sell_gate 单一源同键)。"""
        sess, gs = _mk_gs(bench=[cw4_bc('停云'), cw4_bc('卡芙卡')])
        for scene in ('self_rescue', 'ore_make_room', 'deploy_swap'):
            cands, why = evaluate_sell_candidates(
                gs, scene, swap_ctx=_swap_ctx(gs) if scene == 'deploy_swap'
                else None)
            assert cands == (), scene
            assert why == EMPTY_BOARD_SELL_GUARD_KEY, scene


# ===== 场景注册表参数(通道谱系 + 跨档止盈参数)=====


class TestSceneTableParams:

    def test_scene_table_covers_legacy_channels(self):
        """通道谱系行完整性:凑息→节末凑息 / 筹资→会话内筹资+备战升级
        凑金+C1 / m4_fuel→晶矿;line_switch/projection 不进评估器场景表;
        shop_swap 行已随置换账替换退役(3.2)。"""
        assert SCENE_SPECS['node_end_interest'].legacy_channel == 'interest'
        assert SCENE_SPECS['session_funding'].legacy_channel == 'funding'
        assert SCENE_SPECS['levelup_liquidate_prep'].legacy_channel == 'funding'
        assert SCENE_SPECS['ore_make_room'].legacy_channel == 'm4_fuel'
        assert SCENE_SPECS['deploy_swap'].legacy_channel is None
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
        assert len(SELL_SCENARIOS) == 7   # 五场景 + deploy_swap + c1

    def test_interest_scene_carries_cross_tier_param(self):
        """跨档止盈 = 节末凑息独有场景参数(acquisition §3 表):其余
        场景恒 False。"""
        assert SCENE_SPECS['node_end_interest'].cross_tier_only is True
        for name, spec in SCENE_SPECS.items():
            if name != 'node_end_interest':
                assert spec.cross_tier_only is False, name

    def test_face_regular_channel_closure_anchor_list(self):
        """通道闭集锚:FACE_REGULAR 通道逐一点名(SCENE_SPECS 闭集派生)
        ——新增常规面通道会撑破本清单(shop_swap 已随置换账替换退役)。"""
        regular = {s for s, spec in SCENE_SPECS.items()
                   if spec.face == FACE_REGULAR}
        assert regular == {'ore_make_room', 'c1_make_room',
                           'session_funding', 'node_end_interest',
                           'levelup_liquidate_prep'}


# ============================================================
# 终局键集标签命中件排除(装配 A 身份段;3.4 身份段收缩前随装配照读)
# ============================================================

#: 泄露样本帧锚(万敌单C 锁定截断帧):非名单标签件(布洛妮娅,燃血/
#: 夜之半神标签)不在基座保护面;佩拉 = 零标签对照件(同一帧在池)。
_SWDC = '万敌单C'
_BLN = '布洛妮娅'
_PEL = '佩拉'


class TestTerminalKeyLabelExclusion:

    def _truncation_gs(self, *, bench, front=('万敌', _LV8_FILL[0],
                                              _LV8_FILL[1], '停云'),
                       back=('三月七',), gold: int = 30):
        """万敌单C 锁定截断帧(plane2 保护域,锁线名单 = 万敌单C
        core∪shared):**板满**(cap = level 5,front 4 + back 1)——
        统一序列前置 = 部署重排定型,非板满帧备战位件会被 M1 补位收进
        部署需要面(档 1)而整体 sheltered,测不到排除面本体。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=2, round_num=6, node='prep', level=5,
                    gold=gold,
                    bench=[cw4_bc(n) for n in bench],
                    front_row=[_fu(n) for n in front],
                    back_row=[_fu(n) for n in back])
        # 锁定语境 = IntentionState 直锁(ist.locked_comp):标签排除与
        # 义务基座的读源 = 意向面锁定,不经完整锁定写入——避免整锁激活
        # M1″ 换阵计划把 fence 命中的 bench 件收进部署定型(档 1)而
        # 掩盖排除面本体(部署需要面保护 = 统一序列的正交语义,另有
        # self_rescue 全量面测试覆盖)。
        st = state_of(gs)
        st.plane2_started = True
        st.v3_intention = IntentionState(locked_comp=_SWDC)
        return gs

    @pytest.mark.parametrize('scene', ['ore_make_room', 'c1_make_room',
                                       'session_funding',
                                       'node_end_interest',
                                       'levelup_liquidate_prep'])
    def test_label_hit_bench_piece_excluded_per_channel(self, scene):
        """五通道逐一点名锚:bench 标签命中件(布洛妮娅,燃血无已达成
        档 = 真实泄露形态)在各通道候选中被排除;零标签对照件(佩拉)
        同帧在池——排除面 = 标签命中,非通道空转(design 2026-10-26-
        swap-channel-unified §2.8 堵回降口二,bench 侧含内)。"""
        gs = self._truncation_gs(bench=[_BLN, _PEL], gold=38)
        cands, why = evaluate_sell_candidates(gs, scene)
        assert why == '', scene
        assert _BLN not in _names(cands), \
            f'{scene}: bench 标签命中件禁换金(身份段增补排除)'
        assert _PEL in _names(cands), \
            f'{scene}: 零标签件不受排除影响(纯过渡件放行锚)'

    def test_label_hit_field_piece_pool_excluded(self, ):
        """场上标签命中件(布洛妮娅在场,燃血 0 档)不入候选池——统一
        序列全局面池下场上件按自身档位排序,身份段排除照常覆盖(设计
        §2.8;bench 对照件佩拉同帧在池)。"""
        gs = self._truncation_gs(bench=[_PEL], gold=38,
                                 front=(_BLN, _LV8_FILL[0], _LV8_FILL[1],
                                        '停云', '镜流'), back=())
        cands, why = evaluate_sell_candidates(gs, 'node_end_interest')
        assert why == ''
        assert _BLN not in _names(cands), \
            '场上无档标签件不入候选池(泄露面闭合)'
        assert _PEL in _names(cands), 'bench 零标签件放行'

    def test_tier_carrier_bench_label_piece_also_rejected(self):
        """有档标签件同样拒(谓词不看激活档位的另一面:已承载档位不
        豁免换金):锁定双王圣杯帧 bench 远坂凛(圣杯标签,板面圣杯 2 人
        一档已激活)不入晶矿腾位候选;纯过渡件(爻光,键集零命中)同帧
        在池(design §2.8 排除谓词语义 + 教义「哪怕下远坂凛都不能拆
        能量」)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=2, round_num=6, node='prep', level=5,
                    bench=[cw4_bc('远坂凛'), cw4_bc('爻光')],
                    front_row=[_fu('吉尔伽美什'), _fu('Saber'), _fu('停云'),
                               _fu('镜流'), _fu('杰帕德')],
                    back_row=[])
        st = state_of(gs)
        st.plane2_started = True
        st.v3_intention = IntentionState(locked_comp='双王圣杯')
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert '远坂凛' not in _names(cands), \
            '有档标签件同拒(排除不看激活档位,承载档不豁免)'
        assert '爻光' in _names(cands), '纯过渡件放行(排除不越标签命中面)'

    def test_self_rescue_exemption_preserved(self):
        """自救豁免保留(design §2.8 自救豁免申报):FACE_SELF_RESCUE
        不经装配 A 身份段、不受排除面约束——bench 标签件(布洛妮娅)经
        自救仍可卖(经济安全阀豁免;bench 件不在板上,不影响板面恢复
        路径,板上标签件离场仅经换血对)。"""
        gs = self._truncation_gs(bench=[_BLN, _PEL])
        cands, why = evaluate_sell_candidates(gs, 'self_rescue')
        assert why == ''
        assert {_BLN, _PEL} <= set(_names(cands)), \
            '自救真全量面豁免标签排除(FACE_SELF_RESCUE 直通)'


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
