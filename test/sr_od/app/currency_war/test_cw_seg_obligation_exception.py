"""例外⑦ obligation 因果类笔在场(破息例外谱条目)锁族(T-207)。

主判据与锁族方案 = T-207 方案 v2 §5/§6(先红后绿验收):义务因果类笔
在场的 P1 破息轮「无例外依据」违规事件数 = 0,锁①以 s8434r8 行级形状
为构造锚(g0=52 / gold_end=49 / 单笔 m2_line_member 4 金 / reward 节点
/ 进轮连胜 0)。授权正本(持久索引):02_mandate_layer.md §3 M2 行
「店面出现即买,不走息律门」+ §4 拦截闭集(息律明文无权)+
11_shop_decisions.md §6.3(P54 A3 义务买入破线让渡保留)+ user_playstyle
[13] 2026-09-07 精确化注(金紧期息线带内过渡配方件仍优先买入);囤腿
m2_stockpile 另据 14_p1_consume_arms.md §3.1 义务通道裁决;因果类闭集
单一源 = sell_gate.LAUNCH_CAUSE_BY_ARM(ADR-0585 §2)。
既有例外①-⑥的双向锁在
test_cw_sim_models.py::test_seg_break_interest_exception_bidirectional,
本文件只辖⑦新增面(锁①-⑤),不重复断言既有例外。
"""

from __future__ import annotations


def _ob_row(round_num: int, *, gold0: int, gold_end: int,
            actions: list | None = None, node: str = 'battle') -> dict:
    """合成破息轮账本行(形状对齐 seg 检查器消费面;waves_gold 分离
    时点金与末金)。本文件自带 reason 轴夹具:test_cw_sim_models._seg_buy
    只写 d2_* 桩 reason,表达不了通道授权轴(⑦判定轴)。"""
    return {
        'plane': 1, 'round_num': round_num, 'gold': gold_end,
        'hp': 60, 'formed_stop': False, 'target_comp': '',
        'state': {'board_factions': {}, 'deployed': [], 'bench': [],
                  'cap': 3, 'level': 4},
        'actions': actions or [],
        'sim': {'node': node,
                'income': {'base': 5, 'interest': 0, 'streak': 0,
                           'event': 1},
                'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                          'sell_income': 0},
                'shop_waves': [{'event': 'offer', 'gold': gold0,
                                'cards': []}]},
    }


def _ob_buy(name: str, cost: int, reason: str, channel: str) -> dict:
    """BuyCard 动作(reason=通道授权轴=⑦判定轴;channel=classify_buy
    身份轴——账本 actions 两字段分列,engine_p1 记账面)。"""
    return {'__type__': 'BuyCard',
            'card': {'name': name, 'cost': cost},
            'reason': reason, 'channel': channel}


def test_break_interest_obligation_cause_exemption() -> None:
    """锁① 主判据(⑦正向):义务因果类笔在场的 P1 破息轮不报。

    构造锚 = s8434r8 行级形状(52→49,单笔 m2_line_member 4 金,
    reward 节点,进轮连胜 0——该形态在⑦落地前裸显影「无例外依据」,
    是泛找批 F3 唯一 obligation-only 段级残余)。另对判定集四键逐一
    同判(闭集完备:任一 obligation 臂在场都豁免,零行为差异)。
    负向(非 obligation 轮照报)由锁②辖,本锁不重复。
    """
    from sr_od.application.currency_war.sim.checks import segments
    anchor = [_ob_row(8, gold0=52, gold_end=49, node='reward',
                      actions=[_ob_buy('银狼', 4, 'm2_line_member',
                                       'pair')])]
    evs = segments.seg_check_break_interest_exception(anchor)
    assert evs == [], f'义务笔在场破息轮误报(例外⑦未生效?): {evs}'
    for arm in sorted(segments._OBLIGATION_CAUSE_ARMS):
        rows = [_ob_row(4, gold0=52, gold_end=49,
                        actions=[_ob_buy('成员件', 4, arm, 'engine')])]
        evs_arm = segments.seg_check_break_interest_exception(rows)
        assert evs_arm == [], f'obligation 臂 {arm} 在场破息轮误报: {evs_arm}'


def test_break_interest_unauthorized_still_reported() -> None:
    """锁② 负向(法网不掏空):非 obligation 构成的破息轮照报。

    两形态:无授权杂卡(未映射 reason)与 press 类臂(dominance_buy,
    press ∉ obligation 镜像)——⑦只豁免 obligation 值域,「真破息
    候选」桶的剩余辖域不缩(T-207 方案 v2 §4-④)。"""
    from sr_od.application.currency_war.sim.checks import segments
    off_card = [_ob_row(3, gold0=52, gold_end=48,
                        actions=[_ob_buy('杂卡', 4, 'd2_off', 'off')])]
    evs = segments.seg_check_break_interest_exception(off_card)
    assert len(evs) == 1 and '无例外依据' in evs[0]['detail'], \
        f'无授权破息未报: {evs}'
    press_only = [_ob_row(3, gold0=52, gold_end=49,
                          actions=[_ob_buy('垫件', 3, 'dominance_buy',
                                           'off')])]
    evs_p = segments.seg_check_break_interest_exception(press_only)
    assert len(evs_p) == 1, f'press 类破息被⑦误豁免: {evs_p}'


def test_break_interest_hold_class_isolation() -> None:
    """锁③ hold 类隔离:hold 因果类笔在场不命中⑦,破息轮照报。

    候裁面隔离锁(ADR-0624 候裁面不入本批,T-207 方案 v2 §6-3):hold
    臂集从生产映射表现算(cause=='hold'),新 hold 臂自动入隔离面。
    单笔 + channel='off' 构造,防例外①(≥2 笔无 off)先行吞掉断言。
    """
    from sr_od.application.currency_war.sim.checks import segments
    from sr_od.application.currency_war.strategies.impl.mandate_v1.sell_gate import (  # noqa: E501
        LAUNCH_CAUSE_BY_ARM,
    )
    hold_arms = sorted(arm for arm, cause in LAUNCH_CAUSE_BY_ARM.items()
                       if cause == 'hold')
    assert hold_arms, '生产表 hold 臂集为空(构造前提失守)'
    for arm in hold_arms:
        rows = [_ob_row(4, gold0=52, gold_end=49,
                        actions=[_ob_buy('核心件', 3, arm, 'off')])]
        evs = segments.seg_check_break_interest_exception(rows)
        assert len(evs) == 1, f'hold 类臂 {arm} 被⑦误豁免: {evs}'


def test_obligation_mirror_matches_launch_cause_by_arm() -> None:
    """锁④ 镜像一致性:checks 层镜像集 == 生产表 obligation 静态值域。

    单一源 = LAUNCH_CAUSE_BY_ARM(ADR-0585 §2 定稿载体);生产表
    obligation 行扩集而镜像不跟 = 红。登记门形态:红时该做的事 =
    跟镜像并核对新义务臂的裁定是否带「不走息律门」豁免(桥接假设
    核对,见 segments._OBLIGATION_CAUSE_ARMS 注释双钉)。
    """
    from sr_od.application.currency_war.sim.checks import segments
    from sr_od.application.currency_war.strategies.impl.mandate_v1.sell_gate import (  # noqa: E501
        LAUNCH_CAUSE_BY_ARM,
    )
    prod = {arm for arm, cause in LAUNCH_CAUSE_BY_ARM.items()
            if cause == 'obligation'}
    assert prod == segments._OBLIGATION_CAUSE_ARMS, (
        'obligation 镜像与生产表漂移: '
        f'生产={sorted(prod)} '
        f'镜像={sorted(segments._OBLIGATION_CAUSE_ARMS)}')


def test_obligation_exempt_mixed_visibility() -> None:
    """锁⑤ mixed 披露分键:⑦豁免轮含非 obligation 笔 → 违规事件=0
    且披露事件携分组笔清单;obligation-only 与 hold-only 轮零输出。

    对价入册(T-207 方案 v2 §5.3/§6-5):mixed 轮(义务+hold 同轮,
    s8250 批三起实证形态)的 hold 笔段级/D7 常设显影随⑦豁免让渡,
    本披露面是其可见性承载,防豁免静默黑洞。mixed 帧按 s8318r4 同构
    (m2_merge_completion + dominance + C1:unlocked);未映射臂落
    other 桶且 reason 全文仍携(对账不丢笔)。
    """
    from sr_od.application.currency_war.sim.checks import segments
    mixed = [_ob_row(4, gold0=56, gold_end=47, actions=[
        _ob_buy('停云', 1, 'm2_merge_completion', 'engine'),
        _ob_buy('垫件', 2, 'dominance_buy', 'off'),
        _ob_buy('核心件', 3, 'core_single_card_buy:unlocked', 'off'),
    ])]
    assert segments.seg_check_break_interest_exception(mixed) == [], \
        'mixed 轮(义务笔在场)仍报 = ⑦未生效'
    vis = segments.seg_check_obligation_exempt_mixed_visibility(mixed)
    assert len(vis) == 1, f'mixed 轮披露缺失: {vis}'
    assert vis[0]['mixed_groups']['press'][0]['reason'] == 'dominance_buy'
    assert vis[0]['mixed_groups']['hold'][0]['reason'] == \
        'core_single_card_buy:unlocked'
    assert vis[0]['mixed_groups']['other'] == []
    assert vis[0]['gold_before'] == 56 and vis[0]['gold_after'] == 47
    # obligation-only(s8434r8 型):⑦自辖域,披露零输出
    oblig_only = [_ob_row(8, gold0=52, gold_end=49, node='reward',
                          actions=[_ob_buy('银狼', 4, 'm2_line_member',
                                           'pair')])]
    assert segments.seg_check_break_interest_exception(oblig_only) == []
    assert segments.seg_check_obligation_exempt_mixed_visibility(
        oblig_only) == []
    # hold-only:⑦不成立,披露不辖(照报面由锁③辖)
    hold_only = [_ob_row(4, gold0=52, gold_end=49,
                         actions=[_ob_buy('核心件', 3,
                                          'core_single_card_buy:unlocked',
                                          'off')])]
    assert segments.seg_check_obligation_exempt_mixed_visibility(
        hold_only) == []
    # 未映射臂落 other 桶(reason 全文仍携)
    other_mixed = [_ob_row(5, gold0=53, gold_end=49, actions=[
        _ob_buy('成员', 2, 'm2_stockpile', 'engine'),
        _ob_buy('未来臂', 2, 'future_arm_unmapped', 'off'),
    ])]
    assert segments.seg_check_break_interest_exception(other_mixed) == []
    vis2 = segments.seg_check_obligation_exempt_mixed_visibility(
        other_mixed)
    assert len(vis2) == 1
    assert vis2[0]['mixed_groups']['other'][0]['reason'] == \
        'future_arm_unmapped'
