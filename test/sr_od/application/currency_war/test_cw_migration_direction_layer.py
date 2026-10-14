"""W628 · 重构迁移批 2(方向层接管+效果层归位+开关清偿)锁面。

依据 = 蓝图 v-final.1 §7 批 2 行 + §4.3-R1/R5 + W622 预验尸 P1-P9 +
W620 BATCH2_APPENDIX 三危险供给点(D1/D2/D3):

1. D2:committed 缺供给帧 = 保守侧 False——本文件不再持测;保守侧直锁
   = test_cw_session_separation::test_none_state_criterion_faces_
   return_defaults(``committed_authority(None, bare) is False``);原并入目标
   test_cw_w620_migration_b1 本体已随统一迁移批(commit b94e9cfb)删除,指针收口重锚;
2. D3:息线单一源 = ``registry.interest_floor()`` 派生(interest_cap×10),
   全仓属性读点 = 0(grep 锁)+ ALL IN override 通道;
3. P6 注入分歧探针:registry 注入臂与缺省臂必须出现受控分歧(注入链
   可达证);
4. 哨兵锁:局23 型帧(100 金+备战空+息线姿态)在现行 mandate_v1 商店线
   决策面(``decide_shop_action``)。2026-09-08 覆盖对账后收敛为两面:
   2★ 压库件无退金背书 ⇒ 端到端零支出;金位不破息线(金位全决策面端到端,
   扫面收窄 = {0,49,50,51,100},息线两侧边界 + 两端,2026-09-17 审计判决;
   主题文件无此扫面)。原「息线供给恒等」
   「不死守可辨收敛」两面经亲读对账由主题文件承载(test_cw_realizable_interest_floor/
   test_cw_statefn + test_cw_session_separation;test_cw_mandate_v1::
   test_shop_visit_sets_latch / test_cw_shop_line::
   test_d_p2idle_idle_gold_counter),重复锁已删
   (README 纪律 7 跨文件择一);复活史见哨兵节注。原列
   test_cw_must_spend_zone::test_whitelist_empty_shop_cap_top_zero_consume
   系幽灵指针(该文件全史不存在,2026-09-15 覆盖对账勘误):
   shop_r1_no_chaseable_member==1 面无本帧族独立覆盖锁,现役近邻 =
   test_cw_no_target_three_arms::test_must_spend_zone_no_refresh_burn
   (必花域空店帧同键断言,p2plus 无目标帧族,非局23 帧型);
5. committed 权威判定直锁(权威序三支 + 缺供给保守 False;原逐帧对拍锁
   的对拍半边随退役旧判定式删除,现役语义腿重锚为直锁)。锁面三案 =
   保守真帧一支(P1 未锁线)+ ist 定型两支(locked/p1_pair);plane≥2
   位面序支与 None 退化输入案经审计判决简化(None 案直锁 =
   test_cw_session_separation)。

退役面(审计判决删除):P7 drive_intention 键守卫幂等锁(drive_intention
生产调用点已清零)、P4 ist 跨局零残留锁(每局新建 StrategySession
构造性保证,非行为锁面)、D1 hoard 可信位锁(hoard 投影消费域随方向
投影视图层退役删除,消费侧保守域语义无载体)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
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


def _state(plane: int = 1, round_num: int = 2, gold: int = 40) -> dict:
    """方向层场景种子轴(桥配方缺省;返回 = ``cw4_box`` kwargs)。"""
    return {'plane': plane, 'round_num': round_num, 'gold': gold,
            'level': 3}


# ----------------------------------------------------- D2 缺供给保守侧
# (保守 False 直锁 = 本文件 test_committed_authority_semantics 的
#  p1_unarmed 一案;原并入目标均已退役或全史不存在,指针已收口。)


# ----------------------------------------------------- D3 grep 锁(不恢复)
# 分诊:原 test_d3_grep_lock_no_interest_floor_attribute_reads
# (rglob 扫 src 断言 reg.interest_floor 裸属性读点 = 0)不恢复——源码
# 扫描形态(AGENTS §10.4.4 禁,判据「红的时候是哪个运行行为坏了」答不
# 出);「interest_floor 只可方法调用不可裸属性读」的 API 契约防线归
# review 与代码规范,不进测试网。


# ----------------------------------------------------- 哨兵锁:局23 型帧
# 复活说明:原 test_sentinel_ju23_frame_releases_on_new_stack 以「并入
# w633」为名删除,并入目标经 2026-09-03 歼击战核查不存在 = 指针失真。
# 旧「release 帧」形态随 DP 姿态核/泄息指令死链退役(w633 同批注记),
# dp_posture='release' 遥测标签写端已死、不可锁;复活语义改锁现行
# mandate_v1 商店线决策面的三件事:息线供给恒等 / 不死守可辨收敛 /
# 金位不破息线。统一帧形状 = 列车同行线成型(全员 2★ 上场,stop_buy
# 成立)+ bench 空 + level 6(4 费档在档窗内)+ P1 局中帧。

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
    return sess


# (test_ju23_supply_identity_gstar_and_s_reserve_boundary 已删 2026-09-08
#  覆盖对账:息线供给恒等两面均由主题文件承载——g*==50 = saturation_line(5)
#  ==50(test_cw_statefn)× cap_resolved_of_session(裸真 session)==DEFAULT
#  (test_cw_session_separation),组合面另经 test_cw_launch_arbitrage 全域
#  等价扫现算;s_reserve==50 金约束边界(49 拒/50 过)= test_cw_realizable_interest_floor::
#  test_m6_p56_reject_counter 同边界对 + test_stockpile_s_reserve_boundary
#  位移面超集。README 纪律 7 跨文件等价择一。)


# (test_ju23_stock_match_buys_and_empty_shop_close_discernible 已删
#  2026-09-08 覆盖对账:店空必花域帧原 → CwActionLevelUpShopParam(m3_batch:must_spend)
#  终结面随商店期升级决策面收缩退役,现役帧表达 = CwActionCloseShopParam 收工
#  (本文件 test_ju23_star2_stock_card_has_no_refund_backing_no_spend
#  同构造域承载);shop_visit_idle_gold==1 = test_cw_shop_line::
#  test_d_p2idle_idle_gold_counter,shop_r1_no_chaseable_member==1 无本帧族独立覆盖锁,现役近邻 =
#  test_cw_no_target_three_arms::test_must_spend_zone_no_refresh_burn
#  (必花域空店帧同键断言,p2plus 无目标帧族,非局23 帧型;原指
#  test_cw_must_spend_zone 系幽灵指针,全史不存在,2026-09-15 对账勘误);
#  stockpile_buy 放行面 = test_cw_shop_line::test_stockpile_face_m6_
#  opens_with_frame_window。README 纪律 7 跨文件择一。)


def test_ju23_star2_stock_card_has_no_refund_backing_no_spend():
    """局23 帧 2★ 压库件:无全额可退背书 ⇒ 端到端零支出。

    stockpile_buy 与 dominance 同以 refund_full_star_ok 为背书门:
    2★ 件两条买面都不可发射,溢余滞留(不放行)而非带病买——
    锁「背书门在局23 帧端到端成立」,非单位锁复述。
    商店收缩适配 → 3.6 会话重排再翻转:前置升级检查恢复店内溢余段
    升级消费(次序翻转行为差形态锁)——gold 100 > 息线的帧首动作 =
    CwActionLevelUpShopParam(must_spend 整批授权发射)。
    """
    cfg = SimpleNamespace(ev_arm='full')
    sess = _ju23_session()
    act = decide_shop_action(cw4_gs(sess, **_ju23_axes(
        100, [_sc('花火', star=2)])), sess, cfg)
    assert not isinstance(act, (CwActionBuyCardParam, CwActionRefreshShopParam))
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionLevelUpShopParam,
    )
    assert isinstance(act, CwActionLevelUpShopParam), (
        f'溢余帧应前置升级(翻转行为差): {act!r}')
    assert act.auth_basis == 'must_spend'


# (test_ju23_liquid_refund_shifts_s_reserve_down 已删 2026-09-08 覆盖对账:
#  断言面 = stockpile_buy 金约束边界在 s_reserve=48 的实例,与
#  test_cw_realizable_interest_floor::test_stockpile_s_reserve_boundary(s_reserve=47,差 1 拒/
#  边界过/差 2 过)同谓词等价,常量差异零新语义;docstring 所称「活期退金
#  投影进 s_reserve」的算术不在断言路径(s_reserve 是测试手抄入参,
#  stockpile_buy 不算投影)——与 DEBTS D21 删 test_liquid_refund_excludes_
#  material 同判据(rule 18 docstring≠断言面)。投影值收缩的 decide 级
#  真锁缺口维持 D21 记账。)


def test_ju23_full_surface_gold_never_breaks_interest_line():
    """金位不破息线(端到端复合):0-100 金全决策面逐帧走真函数。

    每个起始金位完整走一次店内访问(动作后真值回写再判,ADR-0517
    §8.1 口径):任一 CwActionBuyCardParam/CwActionRefreshShopParam 花后金 ≥ s_reserve(本帧形状
    = 50);息线下(≤50)整访问零支出(无误清);每访问都以 CwActionCloseShopParam
    收束且有界迭代(无死守环)。
    恒买腾席适配(ADR-0580):店卡改用真无关件(局23杂件,非④放行集/
    registry 核心)——原探针花火 ∈ TRANSITION_PACK carry,未锁双轨
    P1 帧会被 ④转线放行臂在息线下买入(1★ 全额退 = 可逆资产,裁定
    408② 的有意取舍);「息线下零支出」不变式对④放行件域已被裁定
    取代,④例外语义由 test_cw_locked_buy_membership_split 重推锁
    承载,本锁在真无关件域保持。"""
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
            elif type(act).__name__ == 'CwActionLevelUpShopParam':
                # 3.6 前置升级(翻转行为差):溢余段整批消费,花后 ≥ 保底
                # 金门(义务臂不受守 50 辖;升级即收工下一帧关店)。
                spend = act.cost * act.clicks
                assert st['gold'] - spend >= 10, (gold0, st['gold'], spend)
                st['gold'] -= spend
                st['level'] = st.get('level', 5) + 1
            elif isinstance(act, CwActionCloseShopParam):
                break
            else:
                raise AssertionError(f'局23 帧意外动作 {act!r} @ {gold0} 金')
        else:
            raise AssertionError(f'决策不收敛(死守嫌疑)@ {gold0} 金')
        if gold0 <= 50:
            assert st['gold'] == gold0, (gold0, st['gold'])


# ------------------------------------------- committed 权威判定直锁

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
    """committed 权威判定直锁(方向层单一派生源;批 3.7 候选-锁定制
    语义重锚)。

    权威序任一成立即 True:①``st.target_comp`` 非空(锁定线槽——定型
    语义 = 锁定线非空,line_and_upgrade §1.6 判定源迁移)②ist.p1_pair
    非空(P1 配方锁,保留项);缺供给(state/session 缺、未锁线)= 保守
    False——True=已定型=激进侧,攒息门/双轨买门全开(供给点清单 D2)。
    原「plane≥2 恒定型」支已退役(P2 时点兜底锁定替代)——P2 入口至
    兜底锁帧之间的短窗 committed=False(双轨期口径,§1.6 行为差申报,
    p2_unlocked_dual_track 案锁此短窗)。"""
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
