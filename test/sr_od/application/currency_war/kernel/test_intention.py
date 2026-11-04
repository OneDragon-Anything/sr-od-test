"""CW 意向/方向层测试面(committed 权威判定 + 局23 型帧商店线哨兵)。

(P1 体系对候选机器全谱/门控等价/配方锁联动三段已随 comp-structure-
unification 3.3 配方决策层退役删除——被测符号 update_p1_recipe/
p1_pair_candidates_of/冻结域全族消亡,测试面继任者 =
test_cw_transition_library.py〔过渡库条目机器〕;考古走 git 历史。)

1. committed 权威(序①锁定线槽 + 序②过渡锁定态直测);
2. 局23 哨兵(商店线行为直测;息线供给恒等/不死守可辨收敛两面由主题
   文件承载: test_cw_realizable_interest_floor / test_cw_statefn /
   test_cw_session_separation / test_cw_shop_line)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box,
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    committed_authority,
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
# (P1 体系对候选机器全谱段已随配方决策层退役删除——
#  update_p1_recipe/p1_pair_candidates_of/冻结域全族消亡,测试面
#  继任者 = test_cw_transition_library.py(过渡库条目机器);考古走
#  git 历史;comp-structure-unification 3.3。)


# ============================================================
# 2. committed 权威判定直测 + 局23 型帧商店线哨兵
# ============================================================

_JU23_COMP = next(c for c in COMP_LIBRARY
                  if c.name == '列车同行·反震')   # 批 3 拆分后取 A 主形态(哨兵语义与装备/引擎分岔无关)
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
    # state setter;未接线时 gs 侧冷建未锁态,货架资格臂(11 号稿 §1)
    # 按未锁评估货架——旧未锁分支空买面无行为面,
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
    else:   # transition_lock_committed(序②替代口径:过渡锁定态非空)
        state_of(sess).v3_intention = IntentionState(
            transition_locked='希儿引擎')
    assert committed_authority(_gs_state(1, 8), sess) is True
# (门控等价测试 test_p1_pair_gate_equivalence_with_gate_first 已随
#  配方决策层退役删除——被测等价式(p1_pair ⟺ 门控首位)两端全为
#  退役符号;comp-structure-unification 3.3。)
# ============================================================
# (配方锁联动段——_pair_lines 映射/restart_dead 排除/partial_dead
#  保留/all_dead 回退四测——已随配方决策层退役删除;comp-structure
#  -unification 3.3,考古走 git 历史。)
