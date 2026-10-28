"""统一卖出候选评估器测试(契约 D 单一入口;迭代 2026-10-12-prep-shop-workflow-redesign 批 3.2)。

出处 = 迭代总纲 design.md 契约 D(八场景参数表:候选池四族/资格面/
消费方式)+ line_and_upgrade §4(价值评估函数金当量三项统一口径)+
prep_pipeline §1 第 2 步(垫件谓词现文口径)与 §1 第 0 步(空板守卫
as-built 不收窄)。测试语义 = 「价值低先让位」的排序结构与各场景候选池
差分,非具体牌名。

本批边界:评估器本体测试——生产接线(3.3/3.5/3.6 各发射位)不在本测试面。

并段(**凑息/支付变现通道占位件物理门**,原 test_cw_sell_item_slot_
predicate 并入):缺陷(修复前)= criteria/sell ``sell_for_interest`` /
``funding_support_sell`` 资格循环对占位件(备战槽占位 kind,SIFT 不可读
⇒ char_id=''、默认 1★)无物理门——空名不在排除集/线内、星级 1、无同名
副本、注册表查无此名 ⇒ bench_effect 谓词 False,门组全放行;凑息缺口帧/
筹资帧占位件按未知名保守估 3 金计入止盈贪心 → 对不可卖对象发射
CwActionSellBenchParam(实机 = 白耗动作,与 M4 燃料通道案发形同族;游戏
真值 = 占位件无卖出交互且无金币现值,知识锚 = board_structure.md
§备战栏)。判据单一源 = ``predicates.item_slot_unsellable`` 跨通道共享
谓词,M4 燃料/凑息/支付变现三通道资格循环同门消费(生产观察层 SIFT 不产
占位件条目,sim 假环境经观察面直喂可及)。
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
    is_ore_pad_unit,
    sell_gold_equivalent,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.sell_gate import (
    EMPTY_BOARD_SELL_GUARD_KEY,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.session_scope import (
    write_line_lock,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

# 注册表事实锚(测试种子选名依据,别换名后不解注册表):
# - 万敌(1费,夜之半神+燃血,非引擎/非保护集/非插件)= 干净垫件/无关件;
# - 远坂凛(1费)/Saber(3费)/Archer(5费)= 命运圣杯族(tiers (2,3,4,5)),
#   单独在场不激活,双人在场 = 贡献件对(且恰在档 = 掉档);
# - 刻律德菈(3费,插件成员,非四体系)、希儿(registry 核心 ∩ 希儿系)、
#   卡芙卡(持续伤害系保护档)、瓦尔特(列车同行系保护档 + 线内候选)。
LV = 7   # 多费用档可刷等级(1-5 费概率全正;3 级纯 1 费会把高费变 inf)


def _mk_gs(**kw):
    """裸会话 + 容器种子(cw4_gs 家族缺省;node 观察使轮号可解析)。"""
    sess = StrategySession()
    gs = cw4_gs(sess, plane=1, round_num=2, node='prep', level=LV, **kw)
    return sess, gs


def _fu(name: str, star: int = 1) -> Unit:
    """场上行域单位(DeployedView 行域元素 = 容器 Unit——别混用备战
    ``cw4_bc`` 的 BenchSlot 形:羁绊聚合/SellCandidate 直读 char_id,
    BenchSlot 塞进行域会被静默读空标签,贡献件判定假阴性)。"""
    return Unit(char_id=name, star=star)


def _names(cands) -> list[str]:
    return [c.char_id for c in cands]


def _swap_ctx(gs) -> SwapPlanContext:
    """换人判定语境(测试手装:fenced 义务臂 + 未锁帧 + 空目标视图——
    现行判据在该语境下对非 core/非 target 件放行,足够校验池族差分;
    装配链本体(3.3)不在本测试面)。"""
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
        _sess, gs = _mk_gs(bench=[cw4_bc('万敌')], front_row=[_fu('三月七')])
        with pytest.raises(ValueError, match='未知卖出场景'):
            evaluate_sell_candidates(gs, 'bogus_scene')

    def test_deploy_swap_without_ctx_fail_closed(self):
        """换人场景缺判定语境 ⇒ 拒评估(现行判据 ctx=None 返回全放行是
        fail-open 形态,评估器侧拒收——资格判据禁缺语境放行)。"""
        _sess, gs = _mk_gs(bench=[cw4_bc('万敌')], front_row=[_fu('三月七')])
        cands, why = evaluate_sell_candidates(gs, 'deploy_swap')
        assert cands == ()
        assert why == REJECT_SWAP_CTX_MISSING


# ===== 四族候选池边界(同状态各场景差分;契约 D 候选池列) =====


class TestCandidatePoolFamilies:

    def _pool_gs(self):
        """同状态种子:bench = 无关件 + 线内件(索引 0 = 占位件,兼校验 bench
        idx 紧缩占席序坐标系);场上 = 无关件 + 命运圣杯贡献件对;候选快照
        = 列车同行(未锁定期线内身份集 = 候选 top3 线内成员)。"""
        sess, gs = _mk_gs(
            bench=[BenchSlot(kind='bookcard'), cw4_bc('刻律德菈'),
                   cw4_bc('瓦尔特')],
            front_row=[_fu('万敌')],
            back_row=[_fu('远坂凛'), _fu('Saber')])
        state_of(gs).line_candidates = ('列车同行',)
        return sess, gs

    def test_bench_only_scenes_exclude_field_zone(self):
        """腾槽族 = 仅备战席:场上件不入池(即使无关),备战席内
        线内件(瓦尔特)被常规面线内排除;bench idx = 紧缩占席序(占位件
        占 0 号下标)。"""
        _sess, gs = self._pool_gs()
        for scene in ('ore_make_room', 'shop_swap', 'session_funding',
                      'c1_make_room'):
            cands, why = evaluate_sell_candidates(gs, scene)
            assert why == ''
            assert _names(cands) == ['刻律德菈'], scene
            assert cands[0].zone == 'bench'
            assert cands[0].idx == 1, scene   # bookcard 占 0 号紧缩下标

    def test_income_family_adds_field_irrelevant_only(self):
        """来金族(节末凑息/备战升级变现)= 备战席 ∪ 场上无关角色:无关
        场上件(万敌)入池;贡献件对(远坂凛/Saber,命运圣杯 2 人恰激活
        2 档)不入池;场上支无「挂后台」资格谓词(刻律德菈为插件仍在池)。"""
        _sess, gs = self._pool_gs()
        for scene in ('node_end_interest', 'levelup_liquidate_prep'):
            cands, why = evaluate_sell_candidates(gs, scene)
            assert why == ''
            assert set(_names(cands)) == {'刻律德菈', '万敌'}, scene
            zones = {c.char_id: c.zone for c in cands}
            assert zones['万敌'] == 'deployed', scene

    def test_deploy_swap_field_and_bench_pool(self):
        """部署换人 = 场上 ∪ 备战席(场上锁定线成员/羁绊件的唯一卖出
        场景):场上三件与备战席两件(含线内件瓦尔特——换人资格走现行
        swap 判据,不走装配 A 的线内排除)全部入池。"""
        _sess, gs = self._pool_gs()
        cands, why = evaluate_sell_candidates(gs, 'deploy_swap',
                                              swap_ctx=_swap_ctx(gs))
        assert why == ''
        assert set(_names(cands)) == {'刻律德菈', '瓦尔特', '万敌',
                                      '远坂凛', 'Saber'}

    def test_locked_line_view_drives_membership(self):
        """锁定态线内身份集切换:锁定写入后线内判定 = line_members_view
        名单(瓦尔特仍线内被常规面排除),候选快照不再承载判定职责。"""
        _sess, gs = self._pool_gs()
        state_of(gs).line_candidates = ()   # 候选快照清空(锁定态唯一源)
        write_line_lock(gs, '列车同行')
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert _names(cands) == ['刻律德菈']   # 瓦尔特仍被锁定线名单排除


# ===== 自救扩展面(P78 通道豁免 + 线内末位;契约 D 自救行) =====


class TestSelfRescueFullPool:

    def test_full_pool_waives_p78_family(self):
        """自救 = 真全量持有:registry 核心(希儿,P78-4)/ 同 visit 买入
        (卡芙卡,P78-1)/ 线内件(瓦尔特)全部可卖——同状态下常规面场景
        (晶矿)三者全被排除、空候选显影;线内件在自救让位序整体置末层
        (自救扩展面,组内仍按金当量序)。"""
        sess, gs = _mk_gs(
            bench=[cw4_bc('希儿'), cw4_bc('卡芙卡'), cw4_bc('瓦尔特')],
            front_row=[_fu('三月七')])
        state_of(gs).line_candidates = ('列车同行',)
        from sr_od.application.currency_war.kernel.cw_deploy_logic import (
            record_fresh_buy,
        )
        record_fresh_buy(None, gs, '卡芙卡')
        # 常规面(晶矿):P78 族三通道排除全生效 → 空候选
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert (cands, why) == ((), REJECT_NO_CANDIDATES)
        # 自救:真全量 + 线内件末位
        cands, why = evaluate_sell_candidates(gs, 'self_rescue')
        assert why == ''
        assert set(_names(cands)) == {'希儿', '卡芙卡', '瓦尔特'}
        assert cands[-1].char_id == '瓦尔特'
        assert cands[-1].line_member is True
        assert all(c.line_member is False for c in cands[:-1])


# ===== 价值排序序(金当量三项构造对比;line_and_upgrade §4) =====


class TestValueOrdering:

    def _value_gs(self):
        """远坂凛 1★ 单张 / 万敌 1★×2(差一张)/ Archer 2★ 高费;场上
        垫一个非同名单位避开空板守卫。"""
        return _mk_gs(
            bench=[cw4_bc('远坂凛'), cw4_bc('万敌'), cw4_bc('万敌'),
                   cw4_bc('Archer', star=2)],
            front_row=[_fu('三月七')])

    def test_order_single_then_pair_then_high_star(self):
        """让位序 = 金当量升序:零散单张(自身再遇期权)< 差一张对(持有
        更多久窗更长 + 合成进度沉淀)< 2★ 高费(变现价×3 + 高费再遇窗
        长,持有期权值钱)——三项维度各断言一档。"""
        _sess, gs = self._value_gs()
        cands, why = evaluate_sell_candidates(gs, 'self_rescue')
        assert why == ''
        assert _names(cands) == ['远坂凛', '万敌', '万敌', 'Archer']

    def test_single_value_composition(self):
        """零散单张金当量 = 变现价 + 再遇期权 + 合成进度(单张 = 自身
        再遇期权)——三项构成 + 边际率 1 金/轮 + fail-closed ×1 的量纲
        测试(期望从注册表单一源现算,非手抄常数)。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            bench_char_cost,
            sell_refund,
        )
        _sess, gs = self._value_gs()
        unit = cw4_bc('远坂凛').unit
        expected = (
            sell_refund(1, bench_char_cost(unit, gs))
            + reencounter_window_frames(LV, 1, 1) * INTEREST_MARGIN_PER_ROUND
            + reencounter_window_frames(LV, 1, 1) * INTEREST_MARGIN_PER_ROUND)
        assert sell_gold_equivalent(gs, unit) == pytest.approx(expected)
        # 同状态候选行携带同一值(评估器消费同一价值函数)
        cands, _ = evaluate_sell_candidates(gs, 'self_rescue')
        assert cands[0].gold_value == pytest.approx(expected)

    def test_merge_pair_multiplier_slot(self):
        """合成进度 ×2 系数走 provisional 槽:缺省 ×1(fail-closed 线性)
        → 注入 2.0 后差一张对价值 = 变现价 + 再遇期权 + 2×再遇期权
        (增量恰为一个再遇期权);值域守卫拒绝 [1,2] 外注入。"""
        _sess, gs = self._value_gs()
        unit = cw4_bc('万敌').unit
        before = sell_gold_equivalent(gs, unit)
        window = reencounter_window_frames(LV, 1, 2) * INTEREST_MARGIN_PER_ROUND
        try:
            provisional.inject(MERGE_PROGRESS_X2_SLOT,
                               provisional.CalibValue(value=2.0))
            assert sell_gold_equivalent(gs, unit) == pytest.approx(before + window)
            with pytest.raises(ValueError):
                provisional.inject(MERGE_PROGRESS_X2_SLOT,
                                   provisional.CalibValue(value=3.0))
        finally:
            provisional.reset(MERGE_PROGRESS_X2_SLOT)

    def test_bond_drop_rule_orders_after_non_drop(self):
        """羁绊排序规则项(不折金):卖后掉当前羁绊档的场上件排在全部
        不掉档件之后——命运圣杯 2 人恰在 2 档(卖一掉档)整体置后于
        无关件万敌(不掉档),与其金当量相对大小无关。"""
        _sess, gs = _mk_gs(
            bench=[], front_row=[_fu('万敌')],
            back_row=[_fu('远坂凛'), _fu('Saber')])
        cands, why = evaluate_sell_candidates(gs, 'deploy_swap',
                                              swap_ctx=_swap_ctx(gs))
        assert why == ''
        assert cands[0].char_id == '万敌'
        assert cands[0].bond_drop is False
        assert {c.char_id for c in cands[1:]} == {'远坂凛', 'Saber'}
        assert all(c.bond_drop is True for c in cands[1:])


# ===== 垫件谓词(晶矿场景过滤;prep_pipeline §1 第 2 步) =====


class TestOrePadPredicate:

    def test_pad_predicate_matrix(self):
        """合取六项逐项否决:1★ / 非线内 / 非合成素材 / 非通用插件 /
        非保护集(统一保护集 design §2.3 垫件分支迁移——registry 核心
        〔希儿〕与四体系件〔卡芙卡〕同被保护身份分支排除)/ 非引擎件
        (种子身份层);全过 = 纯垫件。"""
        _sess, gs = _mk_gs(bench=[cw4_bc('万敌')],
                           front_row=[_fu('三月七')])
        state_of(gs).line_candidates = ('列车同行',)
        assert is_ore_pad_unit(gs, '万敌', 1) is True
        assert is_ore_pad_unit(gs, '万敌', 2) is False        # 非 1★
        assert is_ore_pad_unit(gs, '瓦尔特', 1) is False      # 线内(候选成员)
        assert is_ore_pad_unit(gs, '刻律德菈', 1) is False    # 通用插件成员
        assert is_ore_pad_unit(gs, '希儿', 1) is False        # 保护集(registry 核心 ∩ 希儿系)
        assert is_ore_pad_unit(gs, '卡芙卡', 1) is False      # 保护集(持续伤害系)
        # 合成素材:同名同星另有副本
        _s2, gs2 = _mk_gs(bench=[cw4_bc('万敌'), cw4_bc('万敌')],
                          front_row=[_fu('三月七')])
        assert is_ore_pad_unit(gs2, '万敌', 1) is False

    def test_ore_consumption_pads_filter_not_pool_head(self):
        """晶矿消费 = 垫件谓词过滤后取价值最小(非全池排序首位判断——
        价值函数无垫件身份维):通用插件件刻律德菈(3费 1★,非垫件——
        插件分支,非保护身份)按金当量排首位,垫件过滤后取到的是高费纯垫件
        Archer(对照件须在保护集身份段外的常规面在池;统一保护集
        changes/2026-10-15-unified-protection-set design.md §2.3——原
        引擎件卡芙卡样本已属保护档,常规面禁卖,不再在池)。"""
        _sess, gs = _mk_gs(bench=[cw4_bc('刻律德菈'), cw4_bc('Archer')],
                           front_row=[_fu('三月七')])
        cands, why = evaluate_sell_candidates(gs, 'ore_make_room')
        assert why == ''
        assert cands[0].char_id == '刻律德菈'        # 全池首位(金当量最小)
        assert is_ore_pad_unit(gs, '刻律德菈', 1) is False
        assert is_ore_pad_unit(gs, 'Archer', 1) is True
        pads = [c for c in cands if is_ore_pad_unit(gs, c.char_id, c.star)]
        assert _names(pads) == ['Archer']            # 过滤后价值最小 = Archer


# ===== 场上无关角色谓词(契约 D 来金族候选池的场上支准入) =====


class TestFieldIrrelevantPredicate:

    def test_irrelevant_vs_contributor_vs_line_member(self):
        """无关 = 非线内 ∧ 非有效羁绊贡献件:单挂万敌无关;命运圣杯
        2 人(激活 2 档)为贡献件;线内件(锁定线/候选成员)非无关。"""
        sess, gs = _mk_gs(
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


# ===== 空板守卫(as-built 收编;全场景) =====


class TestEmptyBoardGuard:

    def test_empty_board_blocks_all_scenes(self):
        """deployed = 0 帧全部卖出场景哑火(prep_pipeline §1 第 0 步
        as-built 申报:现行守卫语义不收窄;拒因键与 sell_gate 单一源
        同键)。"""
        _sess, gs = _mk_gs(bench=[cw4_bc('万敌'), cw4_bc('卡芙卡')])
        for scene in ('self_rescue', 'ore_make_room', 'deploy_swap'):
            cands, why = evaluate_sell_candidates(
                gs, scene, swap_ctx=_swap_ctx(gs) if scene == 'deploy_swap'
                else None)
            assert cands == (), scene
            assert why == EMPTY_BOARD_SELL_GUARD_KEY, scene


# ===== P78 通道重映射(现行五通道资格面 → 新场景) =====


class TestChannelRemap:

    def test_scene_table_covers_legacy_channels(self):
        """通道重映射行完整性:凑息→节末凑息 / 筹资→会话内筹资+备战升级
        凑金 / m4_fuel→晶矿;line_switch→退役不接(无场景消费该通道,
        部署换人 legacy_channel=None 走现行 swap 判据);projection→
        保留不动(不进评估器场景表)。店内侧升级变现场景已随 2026-10-17
        迭代 T-4 退役删除(筹资通道场景集随单域收窄)。"""
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
        assert len(SELL_SCENARIOS) == 8   # 八场景(店内侧变现行已退役)


# ============================================================
# 终局键集标签命中件来金资格增补(design 2026-10-26-swap-channel-unified
# §2.8 堵回降口二;排除落点 = 装配 A 身份段,机制面锚另见
# test_sell_window_launch.py)
# ============================================================

#: 泄露样本帧锚(万敌单C 锁定截断帧):义务基座 hoard(19)> cap_hold
#: (lv5 = 14),非名单标签件(布洛妮娅,燃血/夜之半神标签)按费用序被
#: 裁出基座保护面——身份段增补前该件可经全部来金通道换金(增补前候选
#: 现读实证);佩拉 = 零标签对照件(同一帧在池)。
_SWDC = '万敌单C'
_BLN = '布洛妮娅'
_PEL = '佩拉'


class TestTerminalKeyLabelExclusion:

    def _truncation_gs(self, *, bench, front=('万敌',),
                       back=('三月七',)):
        """万敌单C 锁定截断帧(plane2 保护域,锁线名单 = 万敌单C
        core∪shared):cap_hold 由容器派生链现算,义务基座截断使标签件
        不经既有基座排除 = 增补排除谓词的真实泄露面。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=2, round_num=6, node='prep', level=5,
                    bench=[cw4_bc(n) for n in bench],
                    front_row=[_fu(n) for n in front],
                    back_row=[_fu(n) for n in back])
        state_of(gs).plane2_started = True
        write_line_lock(gs, _SWDC)
        return gs

    def test_face_regular_channel_closure_anchor_list(self):
        """通道闭集锚:FACE_REGULAR 通道逐一点名(SCENE_SPECS 闭集派生)
        ——新增常规面通道会撑破本清单,防「装配 A 身份段追加即逐通道
        自动覆盖」的声明静默失守(通道闭集单一源 = SCENE_SPECS)。"""
        regular = {s for s, spec in SCENE_SPECS.items()
                   if spec.face == FACE_REGULAR}
        assert regular == {'ore_make_room', 'shop_swap', 'c1_make_room',
                           'session_funding', 'node_end_interest',
                           'levelup_liquidate_prep'}

    @pytest.mark.parametrize('scene', ['ore_make_room', 'shop_swap',
                                       'c1_make_room', 'session_funding',
                                       'node_end_interest',
                                       'levelup_liquidate_prep'])
    def test_label_hit_bench_piece_excluded_per_channel(self, scene):
        """六通道逐一点名锚:bench 标签命中件(布洛妮娅,燃血无已达成
        档 = 真实泄露形态)在各通道候选中被排除;零标签对照件(佩拉)
        同帧在池——排除面 = 标签命中,非通道空转(design §2.8 堵回降口
        二,bench 侧含内)。"""
        gs = self._truncation_gs(bench=[_BLN, _PEL])
        cands, why = evaluate_sell_candidates(gs, scene)
        assert why == ''
        assert _BLN not in _names(cands), \
            f'{scene}: bench 标签命中件禁换金(身份段增补排除)'
        assert _PEL in _names(cands), \
            f'{scene}: 零标签件不受排除影响(纯过渡件放行锚)'

    @pytest.mark.parametrize('scene', ['node_end_interest',
                                       'levelup_liquidate_prep'])
    def test_label_hit_field_piece_income_pool_excluded(self, scene):
        """来金族场上支:无已达成档的标签命中件(布洛妮娅在场,燃血
        0 档)不入候选池——现行 ``is_field_irrelevant_unit`` 仅资格级
        覆盖「有已达成档」件,真实泄露 = 无档标签件,由装配 A 身份段
        增补排除承接(design §2.8;bench 对照件佩拉同帧在池)。"""
        gs = self._truncation_gs(bench=[_PEL], front=(_BLN, '万敌'))
        cands, why = evaluate_sell_candidates(gs, scene)
        assert why == ''
        assert _BLN not in _names(cands), \
            f'{scene}: 场上无档标签件不入来金候选池(泄露面闭合)'
        assert _PEL in _names(cands), f'{scene}: bench 零标签件放行'

    def test_tier_carrier_bench_label_piece_also_rejected(self):
        """有档标签件同样拒(谓词不看激活档位的另一面:已承载档位不
        豁免换金):锁定双王圣杯帧 bench 远坂凛(圣杯标签,板面圣杯 2 人
        一档已激活)不入晶矿腾位候选;纯过渡件(爻光,键集零命中)同帧
        在池(design §2.8 排除谓词语义 + 教义「哪怕下远坂凛都不能拆
        能量」)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=2, round_num=6, node='prep', level=5,
                    bench=[cw4_bc('远坂凛'), cw4_bc('爻光')],
                    front_row=[_fu('吉尔伽美什'), _fu('Saber'), _fu('停云')],
                    back_row=[_fu('藿藿')])
        state_of(gs).plane2_started = True
        write_line_lock(gs, '双王圣杯')
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

    # 「门序测试」已删(同燃料通道判):滤门禁用变异下 star=2 占位件
    # 输入仍被星门(criteria/sell.py 内 b.star != 1)同样拒——两门同为纯拒、
    # 序不可观测,测试零拦截价值;滤门回归由星=1 两个测试实际拦截(变异红证)。
    # 勿以「钉门序」为由重建:无合法可观测形态。


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

    # 「门序测试」已删(同凑息通道判):滤门禁用变异下 star=2 占位件
    # 输入仍被星门(criteria/sell.py 内 b.star != 1)同样拒——序不可观测,
    # 测试零拦截价值;滤门回归由星=1 测试实际拦截(变异红证)。


# ===== 升级凑金排序键①②③(2026-10-17 迭代 design §2.2 场景级覆盖) =====


class TestLevelupPrepSortKeys:

    def _pick(self, cost: int, taken: set[str]) -> str:
        """按费用档选干净凑金候选名(非锁定线/非贯穿件/非核心/非四体系/
        非引擎/无挂后台效果;注册表现算防漂移)。"""
        from sr_od.application.currency_war.kernel.cw_card_identity import (
            is_engine_piece,
        )
        from sr_od.application.currency_war.kernel.cw_comps import (
            CORE_SINGLE_CARD_REGISTRY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
            CROSS_LINE_KEEP_NAMES,
            four_system_members,
        )
        _line = {'姬子·启行', '三月七', '花火', '瓦尔特'}
        for name, ch in CHARACTERS.items():
            if ch.cost != cost or name in taken:
                continue
            if (name in _line or name in CROSS_LINE_KEEP_NAMES
                    or name in CORE_SINGLE_CARD_REGISTRY
                    or name in four_system_members()
                    or is_engine_piece(name)
                    or getattr(ch, 'bench_effect', '')):
                continue
            return name
        raise AssertionError(f'注册表缺 {cost} 费干净候选名(选名锚失效)')

    def _prep_frame(self, lock: bool):
        """P2 凑金构帧(锁定帧 = 便宜目标持有达标,唯一未完成星级目标 =
        姬子·启行 3 费 → 排序键①目标费用 = 3;无锁帧 = 无停留目标 →
        ①键不分组,且不携带线内持有——非贯穿件线内件在无锁定语境会
        入池污染序断言)。候选名注册表现算,返回 (sess, gs, names)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.session_scope import (
            handle_node_boundary,
            write_line_lock,
        )
        taken: set[str] = set()

        def _pick2(cost: int) -> str:
            name = self._pick(cost, taken | {'姬子·启行'})
            taken.add(name)
            return name

        a = _pick2(1)
        b = _pick2(5)
        c = _pick2(3)
        bench = [cw4_bc(a), cw4_bc(a, 2), cw4_bc(b), cw4_bc(c), cw4_bc(c, 2)]
        if lock:
            # 便宜目标持有达标(2★/2★/1★ = 各自 need_star)→ 唯一未完成
            # 星级目标 = 姬子·启行;三件线内(锁定线名单)不入候选池。
            bench = [cw4_bc('三月七', 2), cw4_bc('花火', 2),
                     cw4_bc('瓦尔特', 1)] + bench
        front = '姬子·启行' if lock else '万敌'
        sess = StrategySession()
        gs = cw4_gs(sess, plane=2, round_num=2, node='prep', level=LV,
                    bench=bench, front_row=[_fu(front)])
        gs.node_hist_pos = (2, 1)
        handle_node_boundary(gs)
        if lock:
            write_line_lock(gs, '列车同行')
        return sess, gs, (a, b, c)

    def test_band_out_then_star_then_gold_with_stay_target(self):
        """排序键①②③按序(费用带外→低星→金当量;design §2.2,用户
        裁定 2026-10-17):带外组(费用 ≠ 停留目标 3 费)整组先于带内组
        (①支配③:带内金当量再低也殿后);组内低星先(②支配③:带外
        2★ 排同组 1★ 后);组内同星金当量升序(③);任意星级可卖
        (one_star_refund_only False:2★ 件入池)。金当量随费用档非单调
        (再遇窗项主导),序断言用候选自带 star/gold_value 字段钉结构。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            bench_char_cost,
        )
        _sess, gs, (a, b, c) = self._prep_frame(lock=True)
        cands, why = evaluate_sell_candidates(gs, 'levelup_liquidate_prep')
        assert why == ''
        assert _names(cands) == [a, b, a, c, c], \
            '①带外组(1★ 金当量序 → 2★)整组先于带内组(3费 1★ → 2★)'
        stars = [cand.star for cand in cands]
        assert stars[:3] == [1, 1, 2] and stars[3:] == [1, 2], \
            '②组内低星先(带外 2★ 殿后于同组 1★,①支配③)'
        golds = [cand.gold_value for cand in cands]
        assert golds[0] <= golds[1], '③同组同星金当量升序'
        assert golds[3] <= golds[4], '③带内组同款'
        costs = [int(bench_char_cost(cand.unit, gs) or 0) for cand in cands]
        assert all(x != 3 for x in costs[:3]), '①带外组先行'
        assert all(x == 3 for x in costs[3:]), '①带内组(目标费用档)殿后'

    def test_no_stay_target_no_band_grouping(self):
        """无停留目标帧(未锁定)①键不分组(design §2.2 排序键①括注):
        序退化为 (低星, 金当量)——费用档不参与分组,3 费 1★ 按金当量
        落 1★ 组内自然序而非殿后(与有目标帧的带内殿后形态对照)。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            bench_char_cost,
        )
        _sess, gs, (a, b, c) = self._prep_frame(lock=False)
        cands, why = evaluate_sell_candidates(gs, 'levelup_liquidate_prep')
        assert why == ''
        stars = [cand.star for cand in cands]
        assert stars == sorted(stars), '②低星先仍生效'
        golds = [cand.gold_value for cand in cands]
        one_star_golds = [g for s, g in zip(stars, golds, strict=True)
                          if s == 1]
        assert one_star_golds == sorted(one_star_golds), \
            '③1★ 组内金当量升序'
        seq = [int(bench_char_cost(cand.unit, gs) or 0)
               for cand in cands if cand.star == 1]
        assert 3 in seq and any(x != 3 for x in seq), '构帧自检(双费用档在场)'
        assert seq != [x for x in seq if x != 3] + [x for x in seq if x == 3], \
            '①不分组:3 费 1★ 未被殿后(按金当量自然落位)'
