"""CW 意向/方向层测试面(P1 体系对候选机器 + committed 权威判定 +
局23 型帧商店线哨兵)。

两节归并自原两个主题文件(测试函数名全量保留,原文件已删):

1. 过渡候选机器(原 test_cw_pair_progressive.py;dual-layer-candidates
   迭代 3.1 候选化改写——四层谓词族[在任优先单席易手/排序维选席/argmin
   e_rounds 渐进/换席可行性门]整体退役,design §2.6-6):出处链 =
   kernel 成型线 ``cw_battle_calib._transition_formed``(四体系两两
   组合 = 成型)+ 设计 §2.3(候选空间/对级 min 聚合/门控候选首位/
   双体系对冻结域);旧病灶史 = sim 批 ``sim_20260918_072900_000_n320``
   问题 1(65.6% 局终态配方锁停在单体系)——新制以「单体系对不进冻结
   域」结构性免疫(§2.6-9)。候选机器全谱测试(平手声明序/解冻/进 P2
   清空/槽写端)在 ``test_cw_transition_candidates.py``。
2. committed 权威 + 局23 哨兵(原 test_cw_migration_direction_layer.py;
   该文件系 W628 重构迁移批测试面,迁移对拍半边已随旧判定式退役,现役
   内容 = 权威序直测 + 商店线行为直测,非迁移对照):
   - D2 缺供给保守 False 直测在 p1_unarmed 一案;D3 息线 grep 测试(源码
     扫描形态)已删且不恢复,interest_floor 裸属性读禁令归 review 面;
   - 局23 哨兵复活说明:曾以「并入 w633」为名删除,并入目标经核查不存在
     = 指针失真,后按现行商店线决策面复活;息线供给恒等/不死守可辨收敛
     两面由主题文件承载(test_cw_realizable_interest_floor /
     test_cw_statefn / test_cw_session_separation / test_cw_shop_line)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box,
    cw4_gs,
)

from sr_od.application.currency_war.kernel import cw_intention as intention_mod
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    committed_authority,
    p1_pair_candidates_of,
    pair_target_comp,
    update_p1_recipe,
)
from sr_od.application.currency_war.kernel.cw_launch_admission import (
    readiness_form_ok,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionLevelUpParam,
    CwActionRefreshShopParam,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

# ============================================================
# 1. P1 体系对候选机器(配方链候选化;design §2.3)
# ============================================================


def _seed_gs(*, deployed, gold: int = 100, level: int = 5, r: int = 5,
             board: dict | None = None) -> object:
    """P1 备战场景种子(容器域直写;board 显式给,与 deployed 行一致;
    deployed = 行域 Units,槽号 1 基信息位)。"""
    return cw4_box(plane=1, round_num=r, gold=gold, level=level, hp=80,
                   shop_refresh_cost=2, node='reward',
                   front_row=list(deployed[:4]), back_row=list(deployed[4:]),
                   board=board or None)


def _ignite_dot_board(train_n: int = 0) -> tuple[list, dict]:
    """DOT 点火态(桑博+艾丝妲;DOT 支持 = 2/2 = 1.0 → 单对过门控),
    外加 train_n 个列车件(三/四月七占位;1 件 = 支持 0.5)。"""
    dep = [Unit(char_id='桑博', star=1),
           Unit(char_id='艾丝妲', star=1)]
    board = {'持续伤害': 2}
    for _ in range(train_n):
        dep.append(Unit(char_id='三月七', star=1 + 1))
        board['列车同行'] = board.get('列车同行', 0) + 1
    return dep, board


def test_ignited_pair_stays_single_dual_in_candidates() -> None:
    """点火帧门控首位 = 单满对;渐进第二席由候选并集承载(design §2.3-3/§2.6-4)。

    构造判别态:板上 2 DOT(点火 1.0)+ 1 列车件(支持 0.5)——旧制渐进
    通道在此帧产 2 元对(估计器 argmin 选第二席);候选制下门控首位 =
    支持度最高的 ('持续伤害',) 单满对,双对 ('持续伤害','列车同行') 0.5
    入候选(第二体系件买面经候选并集承载,不再经 p1_pair)。无单体系
    冻结(单对不进冻结域);板面对双对方向 readiness 未成型(两档 AND,
    kernel 成型线)。"""
    dep, board = _ignite_dot_board(train_n=1)
    gs = _seed_gs(deployed=dep, board=board)

    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair == ('持续伤害',), \
        '门控首位 = 单满对(渐进 2 元对形态随四层谓词族退役,§2.6-6)'
    cands = p1_pair_candidates_of(gs)
    assert ('持续伤害', '列车同行') in cands, \
        f'渐进第二席由候选并集承载: {cands!r}'
    assert not ist.p1_pair_frozen, '单体系点火不得触发方向冻结(病灶直测)'
    # readiness 对齐:双对两档 AND 未成型(列车档 1/2)
    assert not readiness_form_ok(
        gs, pair_target_comp(('持续伤害', '列车同行')))


def test_single_system_formed_pair_not_frozen() -> None:
    """单体系对板面凑齐不冻结(design §2.6-9 新语义;旧「超窗冻结单对」
    形态消亡)。

    DOT 点火态单对物化 form_progress = 1.0(单体系档满)——旧制置位评估
    对当前对求值会冻结单对(窗口关闭帧的停手战);新制冻结域 = 双体系对
    (§2.3-4),单体系对板面凑齐**不触发冻结**,第二体系件继续经候选
    并集买进——「单体系锁停 65.6% 局」死锁结构性免疫的直测。"""
    dep, board = _ignite_dot_board()
    gs = _seed_gs(deployed=dep, board=board)
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair == ('持续伤害',), '门控首位保持单满对'
    assert not ist.p1_pair_frozen, \
        '单体系对板面凑齐不冻结(单对不进冻结域,§2.6-9 新语义)'


def test_dual_system_formed_pair_freezes() -> None:
    """真两体系成型照旧冻结(成型停手语义不变;design §2.3-4 冻结域
    取 form_ok 首个)。

    板面 DOT 2 + 列车 2:双对 ('持续伤害','列车同行') 对级支持度
    min(1.0,1.0)=1.0 居候选首位(门控写 p1_pair)且 form_ok(两档
    AND)——置位帧冻结,事件面走 p1_pair: 前缀。"""
    dep = [Unit(char_id='桑博', star=1), Unit(char_id='艾丝妲', star=1), Unit(char_id='三月七', star=1), Unit(char_id='丹恒·饮月', star=1)]
    board = {'持续伤害': 2, '列车同行': 2}
    gs = _seed_gs(deployed=dep, board=board)
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair == ('持续伤害', '列车同行')
    assert str(ist.last_event).startswith('p1_pair:'), \
        f'置位走 p1_pair 事件族, got {ist.last_event!r}'
    assert ist.p1_pair_frozen, '真两体系成型照旧冻结([13] 停手语义不变)'
    assert readiness_form_ok(gs, pair_target_comp(ist.p1_pair)), \
        '两档齐 = form_ok(kernel 成型线)'


def test_seele_pair_gate_requires_full_support() -> None:
    """希儿系对入候选门槛 = 席级支持度 1.0(design §2.3-2/§2.6-10)。

    DOT 点火 + 希儿缺席(席级 0 < 1.0):含希儿系的一切对(单对/双对)
    不入候选——与旧 Q 门槛路径对齐(单卡希儿 0.5 不驱动买入);旧
    无门槛 top-2 方向可选希儿系的早期通道随候选制消亡(§2.6-10)。"""
    dep, board = _ignite_dot_board()
    gs = _seed_gs(deployed=dep, board=board)
    cands = p1_pair_candidates_of(gs)
    assert cands, '前置:DOT 点火帧候选非空'
    assert all('希儿系' not in p for p in cands), \
        f'希儿席级 0 < 1.0 门槛:含希儿系对全部不入候选, got {cands!r}'
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair == ('持续伤害',)
    assert '希儿系' not in ist.p1_pair


def test_empty_window_still_empty() -> None:
    """空窗支零漂移——零资产帧候选空、派生对恒空。"""
    gs = _seed_gs(deployed=[])
    ist = IntentionState()
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair == (), '空窗恒空对(既有语义)'
    assert p1_pair_candidates_of(gs) == (), '无羁绊开局候选空(§2.3-2)'


# ============================================================
# 2. committed 权威判定直测 + 局23 型帧商店线哨兵
# ============================================================

_JU23_COMP = next(c for c in COMP_LIBRARY if c.name == '列车同行')
_JU23_STOCK_COST = 4     # 压库件卡费(档窗内;与注册表 cost 解耦)


def _sc(name: str, cost: int = _JU23_STOCK_COST, star: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=star)


def _ju23_axes(gold: int, shop: list[ShopCard] | None = None) -> dict:
    """局23 型种子轴:线成型(全员 2★ 上场,前排 4/后排按行内槽号)
    + 备战空 + P1 局中(返回 = ``cw4_gs`` kwargs,feed 配方)。"""
    members = list(line_members(_JU23_COMP))
    return {'plane': 1, 'round_num': 4, 'gold': gold, 'level': 6,
            'hp': 80, 'node': 'battle',
            'front_row': [Unit(char_id=m, star=2)
                          for i, m in enumerate(members) if i < 4],
            'back_row': [Unit(char_id=m, star=2)
                         for i, m in enumerate(members) if i >= 4],
            'shop': shop if shop is not None else []}


def _ju23_session() -> StrategySession:
    sess = StrategySession()
    state_of(sess).target_comp = _JU23_COMP
    # 宿主归一接线(锁定局意图成立的前提):decide_shop_action 内
    # line_members_view(gs) 读 gs 侧状态,生产接线 = cw_strategy.py 的
    # state setter;未接线时 gs 侧冷建未锁态,货架资格臂(dual-layer-
    # candidates 3.2)按未锁评估货架——旧未锁分支空买面无行为面,
    # 接线缺陷随资格臂显形。
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    game_state_of(sess).strategy_state = state_of(sess)
    return sess


def test_ju23_star2_stock_card_has_no_refund_backing_no_spend():
    """局23 帧 2★ 压库件:无全额可退背书 ⇒ 不经背书门辖的两臂买入。

    stockpile_buy 与 dominance 同以 refund_full_star_ok 为背书门:
    2★ 件两条买面都不可发射(断言面 = 逐动作 reason 闭集,非单位测试
    复述)。出口形态沿革:商店收缩适配 → 3.6 会话重排 → 升级转场
    (2026-10-17 迭代)→ 升级触发统一批(P1 零主动升级,触发辖域 =
    锁定后 ∧ plane2_started——溢余帧的转场出口消失,会话自然走到
    买面:序 2 场况插件 = 义务通道不走背书门([41]),花火 2★ 若被
    其买入属现行买面语义,非背书门破口;stockpile/dominance 仍被
    背书门拦)。店内升级动作退役(升级执行位迁备战画面)。
    """
    cfg = SimpleNamespace(ev_arm='full')
    sess = _ju23_session()
    st = _ju23_axes(100, [_sc('花火', star=2)])
    reasons: list[str] = []
    act = None
    for _ in range(8):
        act = decide_shop_action(cw4_gs(sess, **st), sess, cfg)
        assert not isinstance(act, CwActionLevelUpParam), \
            '店内升级动作已退役(升级执行位迁备战画面)'
        reasons.append(getattr(act, 'reason', '') or type(act).__name__)
        if isinstance(act, CwActionBuyCardParam):
            st['gold'] -= act.card.cost if act.card.cost else 3
            st['shop'] = [c for c in st['shop'] if c is not act.card]
        elif isinstance(act, CwActionCloseShopParam):
            break
    assert isinstance(act, CwActionCloseShopParam), \
        f'决策有界收束(死守嫌疑): {reasons!r}'
    assert not ({'m2_stockpile', 'dominance_buy'} & set(reasons)), \
        f'2★ 无背书件不经背书门辖的两臂买入: {reasons!r}'
    assert state_of(sess).cw4_counters.get('levelup_transition_close', 0) == 0, \
        'P1 帧零主动升级(触发辖域 = 锁定后 ∧ plane2_started)'


def test_ju23_full_surface_gold_never_breaks_interest_line():
    """金位不破息线(端到端复合):0-100 金全决策面逐帧走真函数。

    每个起始金位完整走一次店内访问(动作后真值回写再判,ADR-0517
    §8.1 口径):任一 CwActionBuyCardParam/CwActionRefreshShopParam 花后金 ≥ s_reserve(本帧形状
    = 50);息线下(≤50)整访问零支出(无误清);每访问都以 CwActionCloseShopParam
    收束且有界迭代(无死守环)。P1 帧升级意图出口不命中(触发辖域 =
    锁定后 ∧ plane2_started,升级触发统一批),溢余帧经正常收工关店
    收束;店内升级发射已退役(2026-10-17 迭代 T-1,升级动作不在店内
    动作面;若复现即 else 分支响亮红)。
    恒买腾席适配(ADR-0580):店卡改用真无关件(局23杂件,非④放行集/
    registry 核心)——原探针花火 ∈ TRANSITION_PACK carry,未锁双轨
    P1 帧会被 ④转线放行臂在息线下买入(1★ 全额退 = 可逆资产,裁定
    408② 的有意取舍);「息线下零支出」不变式对④放行件域已被裁定
    取代,④例外语义由 test_cw_locked_buy_membership_split 重推测试
    承载,本测试在真无关件域保持。"""
    cfg = SimpleNamespace(ev_arm='full')
    # 扫面收窄(审计判决):连续 0..100 → 息线两侧边界 + 两端代表点
    for gold0 in (0, 49, 50, 51, 100):
        st = _ju23_axes(gold0, [_sc('局23杂件')])
        sess = _ju23_session()
        for _ in range(15):
            act = decide_shop_action(cw4_gs(sess, **st), sess, cfg)
            if isinstance(act, CwActionBuyCardParam):
                cost = act.card.cost if act.card.cost else 3
                if gold0 <= 50:
                    assert st['gold'] - cost >= 50, (gold0, st['gold'], cost)
                st['gold'] -= cost
                st['shop'] = [c for c in st['shop'] if c is not act.card]
            elif isinstance(act, CwActionRefreshShopParam):
                if gold0 <= 50:
                    assert st['gold'] - act.cost >= 50, (gold0, st['gold'])
                st['gold'] -= act.cost
            elif isinstance(act, CwActionCloseShopParam):
                break
            else:
                raise AssertionError(f'局23 帧意外动作 {act!r} @ {gold0} 金')
        else:
            raise AssertionError(f'决策不收敛(死守嫌疑)@ {gold0} 金')
        if gold0 <= 50:
            assert st['gold'] == gold0, (gold0, st['gold'])


def _gs_state(plane: int, round_num: int):
    """容器单例构造(真值语义 = 节点 plane/round)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        GameState,
        NodeKey,
    )
    gs = GameState(schema_version=1)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num,
                                kind='普通战斗'),
               sig=ChannelSig(family='obs', actor='cw_observation',
                              mode='read'))
    return gs


@pytest.mark.parametrize('case', [
    'p1_unarmed_conservative', 'locked_committed', 'p1_pair_committed',
    'p2_unlocked_dual_track'],
    ids=['p1-unarmed-conservative', 'locked-committed', 'p1-pair-committed',
         'p2-unlocked-dual-track'])
def test_committed_authority_semantics(case: str):
    """committed 权威判定直测(方向层单一派生源;批 3.7 候选-锁定制
    语义重锚)。

    权威序任一成立即 True:①``st.target_comp`` 非空(锁定线槽——定型
    语义 = 锁定线非空,line_and_upgrade §1.6 判定源迁移)②ist.p1_pair
    非空(P1 配方锁,保留项);缺供给(state/session 缺、未锁线)= 保守
    False——True=已定型=激进侧,攒息门/双轨买门全开(供给点清单 D2)。
    原「plane≥2 恒定型」支已退役(P2 时点兜底锁定替代)——P2 入口至
    兜底锁帧之间的短窗 committed=False(双轨期口径,§1.6 行为差申报,
    p2_unlocked_dual_track 案校验此短窗)。"""
    if case == 'p1_unarmed_conservative':
        assert committed_authority(_gs_state(1, 3), StrategySession()) is False
        return
    if case == 'p2_unlocked_dual_track':
        # P2 未锁帧(兜底锁未触发):committed=False——双轨期口径
        assert committed_authority(_gs_state(2, 1), StrategySession()) is False
        return
    sess = StrategySession()
    if case == 'locked_committed':
        from sr_od.application.currency_war.kernel.cw_comps import get_comp
        state_of(sess).target_comp = get_comp('万敌单C')   # 锁定线槽直种
    else:   # p1_pair_committed
        state_of(sess).v3_intention = IntentionState(p1_pair=('万敌燃血',))
    assert committed_authority(_gs_state(1, 8), sess) is True


@pytest.mark.parametrize('shape', [
    'dual_full', 'single_full', 'partial_band', 'fallback_frame', 'empty'],
    ids=['dual-full', 'single-full', 'partial-band', 'fallback-frame',
         'empty'])
def test_p1_pair_gate_equivalence_with_gate_first(shape: str) -> None:
    """committed 等价验证(design §2.3-3/§2.6-4):p1_pair 非空 ⟺ 门控
    首位支持度 ≥1.0 ⟺ 旧 gate_first 合格集非空(席级最高支持度 ≥1.0),
    含支持度回落帧逐帧等价——committed ⟺ p1_pair 非空 判定零变化
    (``committed_authority`` 序②等价论证的可执行形式;五形态覆盖满
    席/单满/(0,1) 混合带/回落帧/空窗)。"""
    if shape == 'dual_full':
        dep, board = [  # DOT 2 + 列车 2:双对 1.0(置位帧冻结)
            Unit(char_id='桑博', star=1), Unit(char_id='艾丝妲', star=1),
            Unit(char_id='三月七', star=1), Unit(char_id='丹恒·饮月', star=1)], \
            {'持续伤害': 2, '列车同行': 2}
    elif shape == 'single_full':
        dep, board = _ignite_dot_board()      # DOT 1.0 单满
    elif shape == 'partial_band':
        # DOT 1.0 + 仙舟 1/3((0,1) 混合带:p1_pair 非空而仙舟未满)
        dep, board = [Unit(char_id='桑博', star=1),
                      Unit(char_id='艾丝妲', star=1),
                      Unit(char_id='符玄', star=1)], {'持续伤害': 2}
    elif shape == 'fallback_frame':
        dep, board = [Unit(char_id='桑博', star=1)], {}   # DOT 0.5 回落带
    else:
        dep, board = [], {}
    gs = _seed_gs(deployed=dep, board=board)

    ist = IntentionState()
    update_p1_recipe(gs, ist, None)
    sup = intention_mod._p1_system_support(gs)
    expect_nonempty = (
        max(sup.values(), default=0.0)
        >= intention_mod.P1_PAIR_LOCK_MIN_SUPPORT)
    assert bool(ist.p1_pair) == expect_nonempty, \
        f'{shape}: 门控首位非空 ⟺ 席级最高支持度 ≥1.0(旧 gate_first Q 非空)'
    # committed 序②直证:ist 供给下 committed ⟺ p1_pair 非空
    sess = StrategySession()
    state_of(sess).v3_intention = ist
    assert committed_authority(gs, sess) == bool(ist.p1_pair)
