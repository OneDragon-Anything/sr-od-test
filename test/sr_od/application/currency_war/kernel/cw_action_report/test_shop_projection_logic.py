"""W6波4 商店动作投影直写测试(设计件《商店黑板容器化方案》§4-M1/M5)。

- M1 投影行为直测:生产上报函数单写(买牌快照三件组与升星分支内聚
  ``report_action_buy_card_param`` 函数内)的逐域期望态直断言
  (gold/bench 槽位/shop payload/xp;含满栏多买 −k×单价、升档结转)。
  原对拍基准 = cw_vocab 词表单步动作应用器(纯函数逐动作推进),零
  生产消费随死代码删除退役,本测试到期改直测(设计件 M1 行申报「收敛
  单形态后本测试改钉单形态」兑现)。
- M5 投影公式语义源测试:None 跳写形态 + 渠道签名纪律(族错显式炸)
  (收口整删:直写域集封闭/executed 回执字段集两条登记面断言——常量
  字面/字段名复述,红时答不出哪个运行行为坏了;消费面纪律归 review)。

口径申报:payload 期望按槽序 content 紧缩视图 (idx, name, star, cost)
冻结(离屏 None 归一空表 = 旧紧缩列表等价读法);bench 期望按槽位
占用签名 (idx, char_id, star) 冻结;xp 未读域按种子缺席钉(None)。

并段(**商店免费刷新次数 GameState Field 化回归**,原
test_cw_shop_refresh_field 并入;判据 ↔ 测试对照 = landing §3.2 完成
判据):双态锚定三支(免费态锚次数/付费域锚 0/判不出跳写)→
test_funnel_anchor_three_states;observe 覆盖 logic 失配走既有安灯
(Field 机制白送)→ test_anchor_covers_logic_mismatch_fires_andon;
扣减写端 produced_by/evidence 断言 + 未观察保守按付费 →
test_report_free_leg_deducts_field / test_report_unobserved_field_
conservative_paid;两桥发放写端 produced_by/evidence(None 基 = 0 起算;
值语义测试在 test_game_state 桥面,此处校验写端调用面元数据)→
test_grant_bridges_field_write_end;随机态采样(固定种子确定性 +
write_logic_rand 通道语义:observe 覆盖差异落 logic_rand_outcome 台账、
不进失配安灯三分流)→ test_report_random_leg_deterministic /
test_report_random_leg_rand_outcome_not_andon。

种子载体(benchchar-retirement P5 起):场景种子 = 容器域直写
(cw4_gs 裸帧配方:节点不写、空店离屏);投影输出逐字节保形凭据 =
改前/改后探针 diff 为空(.debug/temp/p5_m1/)。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import REFRESH_PROB
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
    report_action_close_shop_param,
    report_action_level_up_param,
    report_action_refresh_shop_param,
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    ShopActionExecuted,
    ShopPayload,
    ShopSlot,
    consume_defect_sink,
    game_state_of,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_EFFECTS
from sr_od.application.currency_war.kernel.cw_shop_deal import state_deal_probs
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionLevelUpParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.obs import cw_observation as obs
from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
    ShopRefreshButton,
)

# 改写依据(分诊):写入者登记面随「商店单动作循环收编」演进——
# 生产写点 actor 现役 = CwScreenShop(cw_screen_shop,登记面在册),
# 旧名 CwOpBuyCards 已退役;测试模拟生产写入随登记面改名。
_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                  mode='compute', group_id='act:CwScreenShop@1')


def _gs_of(**axes):
    """M1 场景种子(原裸帧合成配方承接:节点整域不写、空店离屏;
    域覆盖集与原合成口逐域一致)。"""
    return cw4_gs(node_fill=False, shop_screen='off', **axes)


def _content_of(gs):
    """shop payload content 槽紧缩视图,槽序 (idx, name, star, cost);
    离屏(None)归一空表 = 旧紧缩列表等价读法(三态定长五槽模型,
    用户三态裁定 2026-09-13)。"""
    payload = gs.shop.value
    if payload is None:
        return []
    return [(i, s.card.name, s.card.star or 1, s.card.cost or 0)
            for i, s in enumerate(payload.cards)
            if s.kind == 'content' and s.card is not None]


def _bench_slots(gs):
    """bench 槽位占用签名,槽序 (idx, char_id, star);空槽跳过。"""
    view = gs.bench.value
    if view is None:
        return []
    return [(i, s.unit.char_id, s.unit.star)
            for i, s in enumerate(view.slots)
            if s.kind != 'empty' and s.unit is not None]


def _report_action(gs, action, executed=None):
    """商店域动作单次上报(生产同形):买牌快照三件组与升星分支内聚
    report 函数内,一动作恰一次调用;合计结果的逐域期望态由各案直测
    断言(设计件 §4-M1)。executed 仅对带回执参数的函数透传。"""
    if isinstance(action, CwActionBuyCardParam):
        return report_action_buy_card_param(gs, action, _SIG, executed=executed)
    if isinstance(action, CwActionLevelUpParam):
        return report_action_level_up_param(gs, action, _SIG,
                                            executed=executed)
    if isinstance(action, CwActionRefreshShopParam):
        return report_action_refresh_shop_param(gs, action, _SIG,
                                                executed=executed)
    if isinstance(action, CwActionSellBenchParam):
        return report_action_sell_bench_param(gs, action, _SIG)
    if isinstance(action, CwActionCloseShopParam):
        return report_action_close_shop_param(gs, action, _SIG)
    raise AssertionError(f'未覆盖的商店动作类型:{type(action).__name__}')


# ==================== M5 登记面 ====================


class TestM5Registration:

    # (收口整删)原 test_projection_domain_set_closed「直写域集封闭八域」
    #  与 test_executed_receipt_field_set「executed 回执字段集登记」删:
    #  常量/字段名复述断言,红时是常量或字段改名而非运行行为坏;消费面
    #  (M1 逐域比对轴/按字段名取值)由下方 M1 等价测试承重,登记面纪律归
    #  review 与代码规范。

    def test_wrong_family_sig_rejected(self):
        """渠道签名纪律:非 logic_action 族显式炸(§3.2.4 硬约束 2)。"""
        gs = _gs_of(gold=30, shop=[_card('希儿')])
        with pytest.raises(ValueError):
            report_action_buy_card_param(
                gs, CwActionBuyCardParam(card=_card('希儿')),
                executed=ShopActionExecuted(bought_count=1),
                sig=ChannelSig(family='obs', actor='CwScreenShop'))


# ==================== M1 投影行为直测 ====================


class TestM1DirectLock:

    def test_buy_simple_placement(self):
        """简单买:gold −单价 + bench 落位(首空槽)+ payload −该张。"""
        gs = _gs_of(gold=30, shop=[_card('希儿', cost=3)])
        _report_action(
            gs, CwActionBuyCardParam(card=_card('希儿', cost=3)),
            ShopActionExecuted(bought_count=1))
        assert gs.gold.value == 27, 'gold: 期望 30 −单价 3×k1 = 27'
        assert _content_of(gs) == [], \
            'shop payload: 期望全空(所购槽置 empty,5 槽无货)'
        assert _bench_slots(gs) == [(0, '希儿', 1)], \
            'bench: 期望落位首空槽(槽1,1★希儿)'
        assert gs.xp.value is None, 'xp: 买分支零写(未读域保持种子初值 None)'

    # (收口整删)原 test_buy_triggers_merge「合成买(2 副本在席 + 买第
    #  3 张)」与 test_full_bench_merge_buy_k「满栏多买(k=2,executed 回执
    #  给定)」删:同一升星分支的摆放已被 test_merge_buy_single_report_
    #  two_forms 两形态直测辖住(满栏 k=2 的 executed=None 自算分支经应用
    #  机器内部 merge_buy_k 单一源,bought_count==2 断言即承压;executed
    #  给定 k 的扣金分支由 test_buy_simple_placement / test_missing_receipt
    #  的回执路径辖)——第三种摆放 = 子集断言,不留。

    def test_merge_buy_single_report_two_forms(self):
        """合成买单口两形态直测(升星分支内聚 report_action_buy_card_param 后,
        原升星分支单写测试随聚合口退役;快照基点正确性 = 两形态 bench 期望
        共辖——基点误取买后容器会重复落位/漏升,shop 视图缺失会漏满栏
        合成):非满栏合成买(2 副本在席买第 3 张 → 落位即合成升 2★)与
        满栏合成买(k=2,3 副本合 1 升 2★ 在席副本槽9)。gold −单价×k 与
        payload −k 由同一单口携带(原「分支零写」申报随两写合一消亡)。"""
        for title, axes, act, k, bench_expect in (
            ('非满栏合成买',
             {'gold': 30, 'shop': [_card('希儿', cost=3)],
              'bench': [_bc('希儿', star=1),
                        _bc('希儿', star=1)]},
             CwActionBuyCardParam(card=_card('希儿', cost=3)),
             1, [(0, '希儿', 2)]),
            ('满栏合成买(k=2)',
             {'gold': 60, 'shop': [_card('希儿', cost=3, x=0),
                                   _card('希儿', cost=3, x=1)],
              'bench': [_bc(f'c{i}', star=1)
                        for i in range(8)] + [_bc('希儿', star=1)]},
             CwActionBuyCardParam(card=_card('希儿', cost=3)),
             2, [(i, f'c{i}', 1) for i in range(8)] + [(8, '希儿', 2)]),
        ):
            gs = _gs_of(**axes)
            seq0 = gs.write_seq
            out = report_action_buy_card_param(gs, act, _SIG, executed=None)
            assert out.applied and out.bought_count == k, \
                f'{title}: executed 缺 = 理想执行自算 k'
            assert _bench_slots(gs) == bench_expect, \
                f'{title}: bench 槽位期望 {bench_expect}'
            assert gs.gold.value == axes['gold'] - 3 * k, f'{title}: gold −单价×k'
            assert _content_of(gs) == [], f'{title}: payload −k 张'
            assert gs.write_seq > seq0, f'{title}: 升星分支整表直写'

    def test_sell_bench_refund(self):
        """卖备战席:bench −该牌 + gold +退款(sell_refund 锚)。"""
        gs = _gs_of(gold=10, shop=[], bench=[_bc('希儿', star=1)])
        _report_action(gs, CwActionSellBenchParam(bench_idx=0, income=3))
        assert gs.gold.value == 13, \
            'gold: 期望 10 +退款 3(1★ 希儿 sell_refund 现算)'
        assert _content_of(gs) == [], \
            'shop payload: 期望空(shop 空表帧 = 离屏,零写透传)'
        assert _bench_slots(gs) == [], 'bench: 期望卖出槽置空(9 槽全空)'
        assert gs.xp.value is None, 'xp: 卖分支零写(未读域保持种子初值 None)'

    def test_levelup_clicks_and_level_cross(self):
        """升级:击数×单击价扣金 + xp/level 推进(跨档结转 + level 跨档
        直写,与 prep 分支同款;域集扩申报 = SHOP_PROJECTION_DOMAINS 登记
        面);满级分支(并入):lv10 购买无效,零金零经验零写。"""
        gs = _gs_of(gold=30, shop=[], level=3, xp=(2, 6))
        _report_action(
            gs, CwActionLevelUpParam(cost=4), ShopActionExecuted(levelup_clicks=1))
        assert gs.gold.value == 26, 'gold: 期望 30 −单击价 4×1 击 = 26'
        assert _content_of(gs) == [], \
            'shop payload: 期望空(离屏零写透传)'
        assert _bench_slots(gs) == [], 'bench: 升级分支零写(保持全空)'
        # 2+4=6 ≥ lv3 门槛 4 → 升 lv4,溢出结转 cur=2,cap=lv4 门槛 6;
        # 数值与初值 (2, 6) 巧合相同(跨档结转非零写,升级分支实写 xp 域)。
        assert gs.xp.value == (2, 6), \
            'xp: 期望单击 +4 跨档结转 (2, lv4 门槛 6)'
        assert gs.level.value == 4, \
            'level: 跨档直写 3→4(xp_apply_clicks 单一源;等级滞留会让' \
            '下一击按旧级重算 = 花金零等级推进)'
        # 满级分支(并入,原 test_levelup_full_cap_noop):零金零经验零写
        gs_cap = _gs_of(gold=30, shop=[], level=10, xp=(0, 4))
        _report_action(
            gs_cap, CwActionLevelUpParam(cost=4),
            ShopActionExecuted(levelup_clicks=1))
        assert gs_cap.gold.value == 30, 'gold: 满级购买零金(购买无效)'
        assert _content_of(gs_cap) == [], \
            'shop payload: 期望空(离屏零写透传)'
        assert _bench_slots(gs_cap) == [], 'bench: 满级零写(保持全空)'
        assert gs_cap.xp.value == (0, 4), 'xp: 满级零经验(购买无效)'
        assert gs_cap.level.value == 10, '满级拒付(applied=False)零写'

    def test_levelup_multi_level_jump_unlocks_seat_cap(self):
        """跨级连跳:多击连跳两级(溢出结转在 xp_apply_clicks 算子内)+
        level 直写到位;席位 cap 联动 = ``max_units_of`` 经读口自动跟随
        (level 为 cap 解锁地板,deploy_cap 未读时 base 取 level;部署环
        消费位零改动,写端修复即解锁)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            max_units_of,
        )
        gs = _gs_of(gold=30, shop=[], level=5, xp=(18, 20))
        assert max_units_of(gs) == 5, '前置:cap 地板 = 滞留级 5'
        _report_action(
            gs, CwActionLevelUpParam(cost=4), ShopActionExecuted(levelup_clicks=2))
        # 18+8=26 ≥ lv5 门槛 20 → 升 lv6 余 6;6 < lv6 门槛 40 → 停。
        assert gs.level.value == 6, 'level: 连跳直写 5→6(跨级不滞留)'
        assert gs.xp.value == (6, 40), 'xp: 溢出结转 (6, lv6 门槛 40)'
        assert max_units_of(gs) == 6, \
            '席位 cap 随 level 解锁 5→6(联动验证)'
        assert gs.gold.value == 22, 'gold: 30 −单击价 4×2 击 = 22'

    def test_levelup_boundary_and_unread_pair_skip(self):
        """门槛边界:未达门槛零跨档(level 不写,xp 照推进);域级跳写对:
        level 未读帧推进对整体跳写(禁缺省 1 参与推进计算),gold 域
        独立照写。"""
        gs = _gs_of(gold=30, shop=[], level=5, xp=(15, 20))
        _report_action(
            gs, CwActionLevelUpParam(cost=4), ShopActionExecuted(levelup_clicks=1))
        assert gs.level.value == 5, 'level: 15+4=19 < 门槛 20 零跨档不写'
        assert gs.xp.value == (19, 20), 'xp: 推进到位 (19, 20)'
        # 域级跳写对:level 未读(level_unread 种子缺席)+ xp 已读
        gs2 = _gs_of(gold=30, shop=[], xp=(15, 20), level_unread=True)
        assert gs2.level.value is None and gs2.xp.value == (15, 20)
        seq0 = gs2.write_seq
        report_action_level_up_param(
            gs2, CwActionLevelUpParam(cost=4),
            _SIG, executed=ShopActionExecuted(levelup_clicks=1))
        assert gs2.level.value is None, 'level 未读保持未读'
        assert gs2.xp.value == (15, 20) and gs2.xp.source == 'observation', \
            'level 未读 → 推进对整体跳写(禁缺省 1 参与推进计算;' \
            'xp 值留种子原值,source 不翻 logic)'
        assert gs2.gold.value == 26, 'gold 域独立于推进对照写'
        assert gs2.write_seq > seq0, '跳写对 ≠ 整动作零写(gold 仍落)'

    def test_refresh_paid_deducts_gold_and_samples_rand_payload(self):
        """付费刷新:gold −容器刷价(费用单一源 = ``gs.shop_refresh_cost``
        容器直读,2026-10-16 用户裁决,付费计数语义不变);payload = 随机
        态采样(2026-09-21 Field 化 supersession:2026-09-18「终结跳写
        payload 不写」的 payload 半边收窄为 write_logic_rand 随机态——观察
        覆盖差异预期内,采样即猜测)。"""
        gs = _gs_of(gold=30, shop=[_card('希儿')])
        gs.observe(gs.shop_refresh_cost, 2,
                   sig=ChannelSig(family='obs', actor='cw_observation'))
        _report_action(gs, CwActionRefreshShopParam(cost=2))
        assert gs.gold.value == 28, 'gold: 期望 30 −容器刷价 2'
        assert gs.shop.source == 'logic_rand', \
            'shop payload: 随机态分支采样写(write_logic_rand 专用通道)'
        assert gs.shop.evidence == 'refresh_random_sample', '随机态写端注记'
        assert len(gs.shop.value.cards) == 5, '采样 payload = 定长 5 槽'
        assert _bench_slots(gs) == [], 'bench: 刷新分支零写(保持全空)'
        assert gs.xp.value is None, \
            'xp: 刷新分支零写(未读域保持种子初值 None)'

    def test_refresh_free_gold_unwritten(self):
        """免费帧:金账扣 0(gold 不写——费用清零集中在上报函数免费分支
        同一 free 判定,2026-10-16 用户裁决;free 显式喂 True = sim 形态)。
        Field 扣减语义测试 = 本文件刷新 Field 段
        (test_report_free_leg_deducts_field)。"""
        gs = _gs_of(gold=30, shop=[_card('希儿')])
        gs.write_logic(gs.free_refresh_left, 2, produced_by='test-bridge',
                       sig=ChannelSig(family='logic_hook', actor='cw4_seed'))
        report_action_refresh_shop_param(gs, CwActionRefreshShopParam(cost=2),
                                         _SIG, free=True)
        assert gs.gold.value == 30
        assert gs.effects.refresh_paid == 0, '免费帧禁进付费计数'

    def test_close_shop_leaves_screen(self):
        """CwActionCloseShopParam:结构离屏(shop payload → None,left_screen)。"""
        gs = _gs_of(gold=30, shop=[_card('希儿')])
        assert gs.shop.value is not None
        report_action_close_shop_param(gs, CwActionCloseShopParam(), _SIG)
        assert gs.shop.value is None

    def test_missing_receipt_selfcomputes_ideal_execution(self):
        """回执缺字段 = 该动作自算理想执行(单买 k=1)
        (改写:旧测试「回执缺字段 = 零写」语义已随转移函数
        单源化废止——report_action_buy_card_param docstring「k 来源」段申报:
        executed 给定 = 回执 k(live),None = 理想执行自算(简单分支 1,
        满栏从应用机器出);域未读跳写语义独立,归
        test_none_gold_domain_skip 辖。)"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            shop_payload_content_cards,
        )
        gs = _gs_of(gold=30, shop=[_card('希儿', cost=3)])
        report_action_buy_card_param(gs, CwActionBuyCardParam(card=_card('希儿', cost=3)),
                                     _SIG, executed=ShopActionExecuted())
        assert gs.gold.value == 27, '自算 k=1:gold −单价'
        assert len(shop_payload_content_cards(gs.shop.value)) == 0, \
            'payload 该张移除'
        assert sum(1 for s in gs.bench.value.slots if s.kind != 'empty') == 1, \
            'bench 落位'

    def test_none_gold_domain_skip(self):
        """None 域跳写:gold 未读(容器 None)时 gold 跳写,其余域照写。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            shop_payload_content_cards,
        )
        gs = _gs_of(gold=30, shop=[_card('希儿', cost=3)])
        gs.write_logic(gs.gold, None, produced_by='test',
                       sig=ChannelSig(family='logic_hook',
                                      actor='cw4_seed'))
        report_action_buy_card_param(gs, CwActionBuyCardParam(card=_card('希儿', cost=3)),
                                     _SIG, executed=ShopActionExecuted(bought_count=1))
        assert gs.gold.value is None
        # 改写依据:三态定长五槽(用户三态裁定 2026-09-13),买后 content
        # 紧缩计数 = 旧紧缩列表长度等价读法。
        assert len(shop_payload_content_cards(gs.shop.value)) == 0
        assert sum(1 for s in gs.bench.value.slots if s.kind != 'empty') == 1

    def test_stale_sell_proposal_no_write(self):
        """陈旧卖出提案(空槽/越界):守卫辖面,拒绝 = applied=False 零写。
        (集外动作型零写分支删:上报函数族每动作恰一函数,无按类型聚合的
        登记面可「静默收编集外型」——闭集性质归命名规约完备测试
        test_action_report 辖。)"""
        gs = _gs_of(gold=30, shop=[])
        seq0 = gs.write_seq
        report_action_sell_bench_param(
            gs, CwActionSellBenchParam(bench_idx=0, income=3), _SIG)
        assert gs.write_seq == seq0

    def test_buy_rejected_when_full_and_no_merge(self):
        """满栏且合成不可达 = 游戏拒买(ADR-0283):零写(own=0 满栏域
        ADR-0619 门)。"""
        bench = [_bc(f'c{i}', star=1) for i in range(9)]
        gs = _gs_of(gold=30, shop=[_card('姬子', cost=3)], bench=bench)
        seq0 = gs.write_seq
        report_action_buy_card_param(gs, CwActionBuyCardParam(card=_card('姬子', cost=3)),
                                     _SIG, executed=ShopActionExecuted(bought_count=1))
        assert gs.write_seq == seq0
        assert gs.gold.value == 30, 'gold: 拒买零写金不动(期望 30)'

    # (原 test_legacy_conversion_roundtrip_view 删:转换透传面已被
    #  test_game_state.py 的 shop_card_mapping 往返测试完整辖住(x 对齐/
    #  记录字段透传),本测为同函数低强度复述,子集断言不留。)


def test_shop_entry_funnel_bench_survives_synthesis() -> None:
    """商店入口漏斗 bench 写门场景测试(商店画面 op 入口链回归):
    种子对未声明 bench 域整域跳写(bench_unread)——容器 bench 保持
    漏斗真读值,与执行账 tracked 同源不破。回归形态 = 种子把容器 bench
    覆盖成「9 槽全空」假真空(原防御对象 = 旧合成口无门合成,实机
    2026-09-13 商店段循环崩溃 15+ 连发实证;载体随合成口退役改种子
    域纪律测试:未读域≠真空域,跳写语义在种子层等价存续)。"""

    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        BenchView,
        Unit,
    )

    gs = game_state_of(None)
    # prep 装配环式真读观察(bench 观察写端 = 备战装配环 heavy 块;此处
    # 复刻其产物形态):deploy 后 bench 物理槽 4 留一人
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 3
        + [BenchSlot(kind='unit', unit=Unit(char_id='银枝', star=1))]
        + [BenchSlot(kind='empty')] * 5,
        capacity=9),
        sig=ChannelSig(family='obs', actor='CwScreenPrep', mode='read'))
    # 未读 bench 域种子(生产置位点 = read_game_state 漏斗不读席位的形态)
    cw4_gs(gs, gold=30, shop_screen='off', bench_unread=True, node_fill=False)
    view = gs.bench.value
    assert view is not None and view.slots[3].unit is not None \
        and view.slots[3].unit.char_id == '银枝', \
        '种子后容器 bench 仍为漏斗真读值(未读域跳写,兜底空表不覆盖)'
    # (3.2 单账化:原「执行账 tracked 不受种子影响」断言随第二账退役删,
    #  容器即唯一账,上式即全量测试面。)


# ==================== 买牌获取回调分支(计数归上报单点)====================


class _SpyEffects:
    """effects 替身:on_buy 记录调用参数(时点判据载体);其余委托真册。"""

    def __init__(self, real, seen: list) -> None:
        self._real = real
        self._seen = seen

    def on_buy(self, card, star, k) -> None:
        self._seen.append((getattr(card, 'name', ''), star, k))

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_on_buy_fires_after_acquisition_compute(monkeypatch):
    """购买回调分支(k 计数 + 时点):回调 = 获取计算完(落位 + 合成连锁 +
    升星分支全毕)后恰一次——满栏一击多买按实际张数 k 计 k 次(k = 上报
    executed);回调可见购买后的席面/升星事实(升星分支已毕)。"""
    bench = [_bc(f'c{i}', star=1) for i in range(8)]
    bench.append(_bc('希儿', star=1))
    gs = _gs_of(gold=60,
                shop=[_card('希儿', cost=3, x=0), _card('希儿', cost=3, x=1)],
                bench=bench)
    seen: list = []
    monkeypatch.setattr(gs, 'effects', _SpyEffects(gs.effects, seen))

    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3)), _SIG,
        executed=ShopActionExecuted(bought_count=2))

    assert out.applied and out.bought_count == 2
    assert seen == [('希儿', 1, 2)], \
        '回调恰一次,k = executed 张数(满栏计 k 次)'
    assert _bench_slots(gs) == (
        [(i, f'c{i}', 1) for i in range(8)] + [(8, '希儿', 2)]), \
        '回调时点 = 升星分支已毕(3 副本合 1 升 2★ 在席副本)'


def test_on_buy_not_fired_on_rejected_buy(monkeypatch):
    """拒买(满栏且合成不可达,applied=False 早退)不触回调(未购买,
    计数不虚进)。"""
    bench = [_bc(f'c{i}', star=1) for i in range(9)]
    gs = _gs_of(gold=30, shop=[_card('姬子', cost=3)], bench=bench)
    seen: list = []
    monkeypatch.setattr(gs, 'effects', _SpyEffects(gs.effects, seen))

    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('姬子', cost=3)), _SIG,
        executed=ShopActionExecuted(bought_count=1))

    assert not out.applied, '前置:满栏且合成不可达 = 拒买'
    assert seen == [], '拒买不触回调'


# ==================== 双响防御(提案守卫 expected-vs-主域;)====================


class TestGuardProposalVsMainDomain:
    """商店提案守卫:expected 侧 = 主域席位视图(3.2 单账化;历史病灶 =
    2026-09-09 双响事故,满栏合成买在第二账丢件 → 同 visit 下一动作
    守卫对拍误炸;单账后分叉结构性不可能,守卫对拍主域即闭环)。
    分叉停机路径 = AssertionError 响亮炸出(禁静默跳过)。"""

    def test_stale_bench_idx_empty_slot_raises(self):
        """卖出提案指向主域空槽(跨代际提案)→ AssertionError 停机
        (空槽形 = 槽内无身份 → 名-槽不一致分支,actual 空)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_proposal_vs_expected,
        )
        gs = _gs_of(bench=[_bc('花火', star=1)])   # 仅槽 1 占用
        with pytest.raises(AssertionError, match='名-槽不一致|空槽|越界'):
            guard_proposal_vs_expected(
                CwActionSellBenchParam(bench_idx=3, expect='花火'), gs)

    def test_expect_name_mismatch_raises(self):
        """卖出提案 expect 名与主域槽内身份不符(名-槽漂移)→ 炸出。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_proposal_vs_expected,
        )
        gs = _gs_of(bench=[_bc('花火', star=1)])
        with pytest.raises(AssertionError, match='名-槽不一致'):
            guard_proposal_vs_expected(
                CwActionSellBenchParam(bench_idx=0, expect='刃'), gs)

    def test_healthy_proposal_passes_and_buy_off_shop_raises(self):
        """健康提案零炸出(主域对得上);买牌提案指向店外牌 → 炸出
        (跨代际/已消费提案 = 策略器 bug 显影)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_proposal_vs_expected,
        )
        gs = _gs_of(gold=30, shop=[_card('花火', cost=3)], bench=[])
        assert guard_proposal_vs_expected(
            CwActionSellBenchParam(bench_idx=0, expect=''), gs) is None
        assert guard_proposal_vs_expected(
            CwActionBuyCardParam(card=_card('花火', cost=3)), gs) is None
        with pytest.raises(AssertionError, match='不在期望态店中'):
            guard_proposal_vs_expected(
                CwActionBuyCardParam(card=_card('刃', cost=3)), gs)


# ==================== 刷新 Field 段(免费刷新次数容器化;原
# test_cw_shop_refresh_field 并入)====================

_LSIG = ChannelSig(family='logic_action', actor='CwShopRefreshFieldTest',
                   mode='compute')
_HSIG = ChannelSig(family='logic_hook', actor='CwShopRefreshFieldTest',
                   mode='compute')
_OSIG = ChannelSig(family='obs', actor='CwShopRefreshFieldTest', mode='read')


def _fresh_gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _spy_write_logic(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """GameState.write_logic 调用面捕获(produced_by 不落 Field,写端
    produced_by/evidence 断言 = 调用面测试):收 (field, value, produced_by,
    evidence) 四元组,调用照常透传。"""
    captured: list[tuple] = []
    real = GameState.write_logic

    def _spy(self: GameState, target, value, **kw):
        captured.append((self._field_name(target), value,
                         kw.get('produced_by'), kw.get('evidence')))
        return real(self, target, value, **kw)

    monkeypatch.setattr(GameState, 'write_logic', _spy)
    return captured


# ---- 观察锚定(漏斗 shop-open 段)----


def _feed_ctx(sess: SimpleNamespace) -> SimpleNamespace:
    """read_game_state 观察流测试的最小 ctx(mock ocr_service 空读;
    与 test_game_state 漏斗桩同款先例)。"""
    return SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: []),
    )


def _patch_shop_open_readers(monkeypatch: pytest.MonkeyPatch,
                             btn: ShopRefreshButton) -> None:
    """shop_open 帧读链桩(零像素;刷新钮三态读 = 注入的 ``btn``)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile

    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs, 'read_phase_round',
                        lambda ctx, screen, round_caps=None: (1, 5),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_level_up_cost', lambda ctx, screen: 4,
                        raising=False)
    monkeypatch.setattr(obs, 'board_from_deployed', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({}, False), raising=False)
    monkeypatch.setattr(obs, 'read_shop_cards',
                        lambda ctx, screen, full_ocr=None: [],
                        raising=False)
    monkeypatch.setattr(obs, 'read_refresh_probs', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_shop_refresh_obs'
        '.read_shop_refresh_button',
        lambda ctx, screen, gold=None: btn, raising=False)


def test_funnel_anchor_three_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """双态锚定三支一测试(零新增读屏,复用现役 read_shop_refresh_button
    产物):免费态锚次数 / 付费域锚 0(耗尽/灰态,游戏规则 ⇒ 免费余量恒
    0)/ 整帧判不出跳写(宁缺勿造)。"""
    cases = [
        (ShopRefreshButton(free=True, free_remaining=2, price=None,
                           affordable=True), 2, '免费态锚次数'),
        (ShopRefreshButton(free=False, free_remaining=None, price=2,
                           affordable=True), 0, '付费域锚 0'),
    ]
    for btn, expect, why in cases:
        sess = SimpleNamespace(last_streak=0, active_strategies=[])
        _patch_shop_open_readers(monkeypatch, btn)
        obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
        gs = game_state_of(sess)
        assert gs.free_refresh_left.value == expect and why
        assert gs.free_refresh_left.source == 'observation', why
    # 判不出(free=None)→ 跳写:字段保持未观察
    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_shop_open_readers(
        monkeypatch, ShopRefreshButton(free=None, free_remaining=None,
                                       price=None, affordable=None))
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    assert game_state_of(sess).free_refresh_left.value is None, '判不出跳写'


def test_anchor_covers_logic_mismatch_fires_andon(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """失配对账 = Field 机制白送:动作扣减/发放登记的 logic 值被下一入口
    观察覆盖,失配走既有 observe_vs_logic_mismatch 安灯(缺陷行 + 钩子),
    零手写台账。"""
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )

    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = _fresh_gs()
    gs.write_logic(gs.free_refresh_left, 1,
                   produced_by='CwActionRefreshShopParam',
                   evidence='proj_refresh_free_left', sig=_LSIG)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.free_refresh_left, 2, sig=_OSIG)   # 入口实读 2 次 ≠ 账面 1
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows) == 1 and rows[0]['kind'] == 'observe_vs_logic_mismatch'
    assert fired and fired[0] == rows[0], '既有安灯被调(行同构)'
    assert gs.free_refresh_left.source == 'observation', '观察赢覆盖照常'


# ---- 动作上报扣减(逻辑态)----


def test_report_free_leg_deducts_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """免费分支扣减:Field 值 > 0 → 免费帧——Field write_logic 扣减(下限 0)
    + 付费计数不动 + 写端 produced_by/evidence 断言。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _fresh_gs()
    gs.observe(gs.level, 3, sig=_OSIG)
    gs.write_logic(gs.free_refresh_left, 2, produced_by='EffectLedgerBridge',
                   evidence='effect_burst@p1-r2', sig=_HSIG)
    captured.clear()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-field-test'))
    assert gs.free_refresh_left.value == 1, '免费帧 Field 扣减 2→1'
    assert gs.free_refresh_left.source == 'logic'
    assert captured == [('free_refresh_left', 1, 'CwActionRefreshShopParam',
                         'proj_refresh_free_left')], '写端调用面元数据'
    assert gs.effects.refresh_paid == 0, '免费帧禁进付费计数'
    assert gs.effects.refresh_total == 1, '全量计数含免费'


def test_report_unobserved_field_conservative_paid() -> None:
    """未观察(None)→ 保守按付费:计数进 paid,零 Field 扣减行(次数是
    记账面非决策闸);level 同帧缺读 → 随机态分支跳写(概率表按级索引)→
    容器整拍零写。"""
    gs = _fresh_gs()
    seq0 = gs.write_seq
    report_action_refresh_shop_param(gs, CwActionRefreshShopParam(cost=2),
                                     _LSIG)
    assert gs.free_refresh_left.value is None, '未观察 = 不扣减(零 Field 行)'
    assert gs.effects.refresh_paid == 1, '保守按付费计数'
    assert gs.effects.refresh_total == 1
    assert gs.write_seq == seq0, 'level 缺读随机态分支跳写 → 容器零写'


# ---- 两桥发放(写端元数据)----


def test_grant_bridges_field_write_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """两桥发放写端元数据(值语义测试 = test_game_state 桥面):burst 桥
    produced_by 带效果名 + evidence effect_burst@frame;节点桥
    produced_by 带在场条目名 + evidence effect_node@frame;None 基 = 0
    起算(开局无免费次数 = 机制真值,发放即首次落值)。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _fresh_gs()
    from sr_od.application.currency_war.kernel.cw_game_state import (
        apply_effect_burst_grant,
        grant_effect_node_refresh_balance,
    )
    apply_effect_burst_grant(gs, STRATEGY_EFFECTS['固定理财'], frame='p1-r2')
    assert gs.free_refresh_left.value == 2, 'None 基 = 0 起算'
    assert captured[-1] == ('free_refresh_left', 2,
                            'EffectLedgerBridge:固定理财',
                            'effect_burst@p1-r2'), 'burst 桥写端元数据'
    gs2 = _fresh_gs()
    gs2.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                  acquired_key=(1, 5))
    gs2.effects.advance_node((1, 6))
    grant_effect_node_refresh_balance(gs2, frame='p1-r6')
    assert gs2.free_refresh_left.value == 2, 'None 基 = 0 起算'
    assert captured[-1] == ('free_refresh_left', 2,
                            'EffectLedgerBridge:双手狸开键盘！',
                            'effect_node@p1-r6'), '节点桥写端元数据'


# ---- 刷新随机态分支(kernel 采样器)----


def _seed_for_random_branch() -> GameState:
    """随机态分支场景种子:等级可读(概率表索引)+ 在屏空店(覆盖面在册)。"""
    gs = _fresh_gs()
    gs.observe(gs.level, 1, sig=_OSIG)
    gs.observe(gs.shop, ShopPayload(cards=[ShopSlot(kind='empty')
                                            for _ in range(5)],
                                    refresh_probs={}), sig=_OSIG)
    return gs


def _slot_signature(payload: ShopPayload) -> list:
    return [(s.kind,
             (s.card.name, s.card.cost, s.card.slot, s.card.star)
             if s.card is not None else None)
            for s in payload.cards]


def test_report_random_leg_deterministic() -> None:
    """随机态分支 = kernel 采样器(sample_shop_deal,与 sim deal_shop 同源):
    固定种子两次独立容器采样逐槽一致(确定性);payload 形态 = 定长 5 槽
    content/1★/注册表名 + 基线概率条;写通道 = write_logic_rand 专用通道
    (source=logic_rand + evidence 注记)。"""
    signatures = []
    for _ in range(2):
        gs = _seed_for_random_branch()
        report_action_refresh_shop_param(
            gs, CwActionRefreshShopParam(cost=2), _LSIG,
            rng=random.Random('cw-shop-deal-fixed-seed'))
        payload = gs.shop.value
        assert payload is not None and len(payload.cards) == 5
        assert payload.refresh_probs == {int(k): float(v)
                                         for k, v in REFRESH_PROB[1].items()
                                         if v > 0}, '基线概率条随载荷'
        for slot in payload.cards:
            if slot.card is not None:
                assert slot.card.name in CHARACTERS
                assert slot.card.star == 1, '表外直出恒 1★(U12 + 注册表分支不触发)'
        assert gs.shop.source == 'logic_rand', '随机态专用通道'
        assert gs.shop.evidence == 'refresh_random_sample'
        signatures.append(_slot_signature(payload))
    assert signatures[0] == signatures[1], '固定种子 → 采样确定性'


def test_report_random_leg_rand_outcome_not_andon(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """write_logic_rand 通道语义:随机态采样被下一入口观察覆盖,差异 =
    预期内——只落 logic_rand_outcome 台账行,不进失配安灯三分流(无
    observe_vs_logic_mismatch 行、安灯钩子不触发、无 [cw!] 告警面)。"""
    from sr_od.application.currency_war.kernel import cw_game_state as _gs_mod
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )

    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    warns: list[tuple] = []
    monkeypatch.setattr(_gs_mod.log, 'warning',
                        lambda *a, **k: warns.append(a))

    gs = _seed_for_random_branch()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-deal-fixed-seed'))
    assert gs.shop.source == 'logic_rand'
    # 下一入口观察覆盖(换一张不同的真值牌面)
    truth = ShopPayload(
        cards=[ShopSlot(kind='content'), ShopSlot(kind='empty'),
               ShopSlot(kind='empty'), ShopSlot(kind='empty'),
               ShopSlot(kind='empty')], refresh_probs={})
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.shop, truth, sig=_OSIG)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    kinds = [r['kind'] for r in rows]
    assert 'logic_rand_outcome' in kinds, '差异落随机结果台账'
    assert 'observe_vs_logic_mismatch' not in kinds, '不进失配三分流'
    assert fired == [], '安灯不触发(随机落地非 bug)'
    assert not any('观察覆盖 logic 失配' in str(w) for w in warns), \
        '无 [cw!] 告警面'
    assert gs.shop.source == 'observation', '观察赢覆盖照常'


# ---- 随机态分支采样表(state_deal_probs:轮岗感知采样,投资环境轮岗
# id 114 建模批接入;锁面出处 = invest_effects.md §2 轮岗行)----


def _seed_for_random_branch_at(level: int,
                            bar: dict[int, float] | None) -> GameState:
    """随机态分支场景种子(指定等级 + 观测概率条):等级可读(概率表按级
    索引)+ ``bar`` 非 None 时在屏店(refresh_probs = ``bar``)/ None =
    店离屏(payload 未观察形态)。"""
    gs = _fresh_gs()
    gs.observe(gs.level, level, sig=_OSIG)
    if bar is not None:
        gs.observe(gs.shop, ShopPayload(
            cards=[ShopSlot(kind='empty') for _ in range(5)],
            refresh_probs=bar), sig=_OSIG)
    return gs


def test_state_deal_probs_falls_back_to_baseline_without_bar() -> None:
    """无观测条形态零行为变化:店离屏(payload 未观察)与概率条空表两
    形态下 ``state_deal_probs`` = 基线表逐键相等(键集 = 正概率档)——
    刷新随机态分支接线对无观测条局的采样分布恒等(出处 =
    docs/game/currency_war/research/invest_effects.md §2 轮岗行)。"""
    baseline = {c: p for c, p in REFRESH_PROB[6].items() if p > 0}
    assert state_deal_probs(_seed_for_random_branch_at(6, None), 6) \
        == baseline, '店离屏(refresh_probs 不可得)→ 基线表逐键'
    assert state_deal_probs(_seed_for_random_branch_at(6, {}), 6) \
        == baseline, '概率条空表 → 逐档退基线表逐键'


def test_state_deal_probs_observed_bar_direct_passthrough() -> None:
    """读屏即真值透传:lv6 1费翻倍观测条(60/22/15/3,实读在案 =
    ``parse_prob_bar`` docstring)→ 表 = 观测值逐键相等(5费 0% 退基线
    0 出键——轮岗只翻倍不归零,优先级链单一源承压)。"""
    bar = {1: 0.60, 2: 0.22, 3: 0.15, 4: 0.03, 5: 0.00}
    assert state_deal_probs(_seed_for_random_branch_at(6, bar), 6) \
        == {1: 0.60, 2: 0.22, 3: 0.15, 4: 0.03}, '观测条在场 = 真值直用'


def test_state_deal_probs_zero_tier_per_tier_fallback() -> None:
    """降级链代表形态:观测条含 0 档 → 该档退基线、其余档观测直用
    (2费档 0 退基线 0.40;优先级链经 helper 透传,既有语义不在本测试
    复制断言)。"""
    bar = {1: 0.60, 2: 0.00, 3: 0.15, 4: 0.25, 5: 0.00}
    assert state_deal_probs(_seed_for_random_branch_at(6, bar), 6) \
        == {1: 0.60, 2: 0.40, 3: 0.15, 4: 0.25}, '0 档退基线,其余档直用'


def test_report_random_leg_uses_observed_boosted_bar() -> None:
    """上报接线:观测翻倍条在场 → 刷新上报写出的载荷概率条 = 翻倍表
    (非基线),槽位费用档 ∈ 翻倍表键集;固定种子复跑载荷逐槽相等
    (采样确定性随轮岗形保持)。"""
    bar = {1: 0.60, 2: 0.22, 3: 0.15, 4: 0.03, 5: 0.00}
    boosted_costs = {c for c, p in bar.items() if p > 0}
    signatures = []
    for _ in range(2):
        gs = _seed_for_random_branch_at(6, bar)
        report_action_refresh_shop_param(
            gs, CwActionRefreshShopParam(cost=2), _LSIG,
            rng=random.Random('cw-shop-deal-boosted-seed'))
        payload = gs.shop.value
        assert payload is not None
        assert payload.refresh_probs == {c: p for c, p in bar.items()
                                         if p > 0}, \
            '翻倍表随载荷(非基线 30/40/25/5)'
        for slot in payload.cards:
            if slot.card is not None:
                assert slot.card.cost in boosted_costs, \
                    '槽位费用档 ∈ 翻倍表键集'
        signatures.append(_slot_signature(payload))
    assert signatures[0] == signatures[1], '固定种子 → 采样确定性'
