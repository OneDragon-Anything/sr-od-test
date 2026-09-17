"""W6波4 商店动作投影直写锁(设计件《商店黑板容器化方案》§4-M1/M5)。

- M1 投影行为直锁:生产两写合计(``apply_shop_action_logic`` 投影口
  直写 + ``apply_shop_merge_leg`` 合成升星整表直写,买前快照基点)
  的逐域期望态直断言(gold/bench 槽位/shop payload/xp;含满栏多买
  −k×单价、升档结转)。原对拍基准 = cw_vocab 词表单步动作应用器
  (纯函数逐动作推进),零生产消费随死代码删除退役,本锁到期改
  直锁(设计件 M1 行申报「收敛单形态后本锁改钉单形态」兑现)。
- M5 投影公式语义源锁:None 跳写形态 + 渠道签名纪律(族错显式炸)
  (收口整删:直写域集封闭/executed 回执字段集两条登记面断言——常量
  字面/字段名复述,红时答不出哪个运行行为坏了;消费面纪律归 review)。

口径申报:payload 期望按槽序 content 紧缩视图 (idx, name, star, cost)
冻结(离屏 None 归一空表 = 旧紧缩列表等价读法);bench 期望按槽位
占用签名 (idx, char_id, star) 冻结;xp 未读域按合成初值钉(None)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_state as _state,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopActionExecuted,
    apply_shop_action_logic,
    apply_shop_merge_leg,
    bench_slots_of,
    bench_slots_to_legacy,
    deployed_slots_of,
    game_state_of,
    shop_cards_to_legacy,
    shop_payload_content_cards,
    synthesize_from_game_state,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    CloseShop,
    LevelUpShop,
    RefreshShop,
    SellBench,
    bench_occupied,
)

# 改写依据(分诊):写入者登记面随「商店单动作循环收编」演进——
# 生产写点 actor 现役 = CwScreenBuyCards(cw_screen_buy_cards,登记面在册),
# 旧名 CwOpBuyCards 已退役;测试模拟生产写入随登记面改名。
_SIG = ChannelSig(family='logic_action', actor='CwScreenBuyCards',
                  mode='compute', group_id='act:CwScreenBuyCards@1')


def _gs_of(st):
    """CwSimFrame 桩帧 → 容器(sim 合成口;测试/生产同一条喂入通道)。"""
    gs = game_state_of(None)
    synthesize_from_game_state(gs, st)
    return gs


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
    return [(i, b.char_id, b.star)
            for i, b in enumerate(bench_slots_to_legacy(gs.bench.value))
            if b is not None]


def _project_with_merge_leg(gs, action, executed):
    """执行落地门两写合计的测试复刻(现生产同形):买前快照三件组
    → 投影口直写 → 升星腿整表直写(先投影口后升星写,后写赢)。
    合计结果的逐域期望态由各案直锁断言(设计件 §4-M1)。"""
    pre_bench = list(bench_slots_of(gs))
    pre_dep = list(deployed_slots_of(gs))
    pre_shop = (list(gs.shop.value.cards)
                if gs.shop.value is not None else [])
    apply_shop_action_logic(gs, action, executed=executed,
                            produced_by=type(action).__name__, sig=_SIG)
    if isinstance(action, BuyCard):
        apply_shop_merge_leg(gs, action, sig=_SIG, pre_bench=pre_bench,
                             pre_deployed=pre_dep, pre_shop=pre_shop)


# ==================== M5 登记面 ====================


class TestM5Registration:

    # (收口整删)原 test_projection_domain_set_closed「直写域集封闭八域」
    #  与 test_executed_receipt_field_set「executed 回执字段集登记」删:
    #  常量/字段名复述断言,红时是常量或字段改名而非运行行为坏;消费面
    #  (M1 逐域比对轴/按字段名取值)由下方 M1 等价锁承重,登记面纪律归
    #  review 与代码规范。

    def test_wrong_family_sig_rejected(self):
        """渠道签名纪律:非 logic_action 族显式炸(§3.2.4 硬约束 2)。"""
        gs = _gs_of(_state(gold=30, shop=[_card('希儿')]))
        with pytest.raises(ValueError):
            apply_shop_action_logic(
                gs, BuyCard(card=_card('希儿')),
                executed=ShopActionExecuted(bought_count=1),
                produced_by='BuyCard',
                sig=ChannelSig(family='obs', actor='CwScreenBuyCards'))


# ==================== M1 投影行为直锁 ====================


class TestM1DirectLock:

    def test_buy_simple_placement(self):
        """简单买:gold −单价 + bench 落位(首空槽)+ payload −该张。"""
        st = _state(gold=30, shop=[_card('希儿', cost=3)])
        gs = _gs_of(st)
        _project_with_merge_leg(
            gs, BuyCard(card=_card('希儿', cost=3)),
            ShopActionExecuted(bought_count=1))
        assert gs.gold.value == 27, 'gold: 期望 30 −单价 3×k1 = 27'
        assert _content_of(gs) == [], \
            'shop payload: 期望全空(所购槽置 empty,5 槽无货)'
        assert _bench_slots(gs) == [(0, '希儿', 1)], \
            'bench: 期望落位首空槽(槽1,1★希儿)'
        assert gs.xp.value is None, 'xp: 买腿零写(未读域保持合成初值 None)'

    # (收口整删)原 test_buy_triggers_merge「合成买(2 副本在席 + 买第
    #  3 张)」删:与 test_full_bench_merge_buy_k(满栏合成 k=2)和
    #  test_merge_leg_alone_prestate_basis(升星腿双形态直锁)断言面重叠
    #  ——同一升星腿的第三种摆放,留两形态承重。

    def test_full_bench_merge_buy_k(self):
        """满栏多买(k=2):gold −k×单价 + payload −k 张 + bench 归升星腿
        (本口零落位)。"""
        bench = [_bc(f'c{i}', star=1, slot=i + 1) for i in range(8)]
        bench.append(_bc('希儿', star=1, slot=9))
        st = _state(gold=60, shop=[_card('希儿', cost=3, x=0),
                                   _card('希儿', cost=3, x=1)],
                    bench=bench)
        gs = _gs_of(st)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            merge_buy_k,
        )
        k = merge_buy_k('希儿', 1, st.bench, st.deployed, st.shop)
        _project_with_merge_leg(
            gs, BuyCard(card=_card('希儿', cost=3)),
            ShopActionExecuted(bought_count=k))
        assert k == 2
        assert gs.gold.value == 54, 'gold: 期望 60 −单价 3×k2 = 54'
        assert _content_of(gs) == [], \
            'shop payload: 期望全空(k 张同身份牌全部下架)'
        assert _bench_slots(gs) == (
            [(i, f'c{i}', 1) for i in range(8)] + [(8, '希儿', 2)]), \
            'bench: 期望满栏零落位,3 副本合 1 升 2★(在席副本槽9)'
        assert gs.xp.value is None, 'xp: 买腿零写(未读域保持合成初值 None)'

    def test_merge_leg_alone_prestate_basis(self):
        """升星腿直锁(快照基点回归):腿单写(不跑投影口)时,
        买前快照基点 + shop 视图透传的合成结果按冻结槽位签名直断
        ——非满栏合成买与满栏合成买两形态;gold/payload 域零写(腿只辖
        bench 整表)。基点误取买后容器会重复落位、shop 视图缺失会漏满栏
        合成(失准形态申报见 apply_shop_merge_leg docstring)。"""
        for title, st, act, bench_expect in (
            ('非满栏合成买',
             _state(gold=30, shop=[_card('希儿', cost=3)],
                    bench=[_bc('希儿', star=1, slot=1),
                           _bc('希儿', star=1, slot=2)]),
             BuyCard(card=_card('希儿', cost=3)),
             [(0, '希儿', 2)]),
            ('满栏合成买(k=2)',
             _state(gold=60, shop=[_card('希儿', cost=3, x=0),
                                   _card('希儿', cost=3, x=1)],
                    bench=[_bc(f'c{i}', star=1, slot=i + 1)
                           for i in range(8)] + [_bc('希儿', star=1, slot=9)]),
             BuyCard(card=_card('希儿', cost=3)),
             [(i, f'c{i}', 1) for i in range(8)] + [(8, '希儿', 2)]),
        ):
            gs = _gs_of(st)
            seq0 = gs.write_seq
            # 改写依据(分诊):三态定长五槽模型(用户三态裁定
            # 2026-09-13)后 payload.cards 恒定长 5,「长度不变」旧断言失效;
            # 「腿禁写 payload 域」等价形态 = payload 对象引用不变
            # (observe 换值才换引用)。测试体内 x=100/200 旧画面坐标桩值
            # 同步改槽下标(0/1),合成口按 x 对槽越界丢卡。
            pre_shop_payload = gs.shop.value
            apply_shop_merge_leg(
                gs, act, sig=_SIG,
                pre_bench=list(bench_slots_of(gs)),
                pre_deployed=list(deployed_slots_of(gs)),
                # pre_shop 形态 = 旧牌紧缩视图(与生产投影口同形;
                # 分诊:三态 payload 直传 ShopSlot 列表喂不进
                # mutate 机器的满栏合成素材消费)。
                pre_shop=(shop_cards_to_legacy(
                    shop_payload_content_cards(pre_shop_payload))
                    if pre_shop_payload is not None else []))
            assert _bench_slots(gs) == bench_expect, \
                f'{title}: bench 槽位期望 {bench_expect}'
            assert gs.gold.value == st.gold, f'{title}: 腿禁写 gold 域'
            assert gs.shop.value is pre_shop_payload, \
                f'{title}: 腿禁写 payload 域(引用不变)'
            assert gs.write_seq > seq0, f'{title}: 升星腿应整表直写'

    def test_sell_bench_refund(self):
        """卖备战席:bench −该牌 + gold +退款(sell_refund 锚)。"""
        st = _state(gold=10, shop=[], bench=[_bc('希儿', star=1, slot=1)])
        gs = _gs_of(st)
        _project_with_merge_leg(
            gs, SellBench(bench_idx=0, income=3),
            ShopActionExecuted())
        assert gs.gold.value == 13, \
            'gold: 期望 10 +退款 3(1★ 希儿 sell_refund 现算)'
        assert _content_of(gs) == [], \
            'shop payload: 期望空(shop 空表帧 = 离屏,零写透传)'
        assert _bench_slots(gs) == [], 'bench: 期望卖出槽置空(9 槽全空)'
        assert gs.xp.value is None, 'xp: 卖腿零写(未读域保持合成初值 None)'

    def test_levelup_clicks_and_level_cross(self):
        """升级:击数×单击价扣金 + xp/level 推进(跨档结转 + level 跨档
        直写,与 prep 腿同款;域集扩申报 = SHOP_PROJECTION_DOMAINS 登记
        面);满级腿(并入):lv10 购买无效,零金零经验零写。"""
        st = _state(gold=30, shop=[], level=3, xp=(2, 6))
        gs = _gs_of(st)
        _project_with_merge_leg(
            gs, LevelUpShop(cost=4), ShopActionExecuted(levelup_clicks=1))
        assert gs.gold.value == 26, 'gold: 期望 30 −单击价 4×1 击 = 26'
        assert _content_of(gs) == [], \
            'shop payload: 期望空(离屏零写透传)'
        assert _bench_slots(gs) == [], 'bench: 升级腿零写(保持全空)'
        # 2+4=6 ≥ lv3 门槛 4 → 升 lv4,溢出结转 cur=2,cap=lv4 门槛 6;
        # 数值与初值 (2, 6) 巧合相同(跨档结转非零写,升级腿实写 xp 域)。
        assert gs.xp.value == (2, 6), \
            'xp: 期望单击 +4 跨档结转 (2, lv4 门槛 6)'
        assert gs.level.value == 4, \
            'level: 跨档直写 3→4(xp_apply_clicks 单一源;等级滞留会让' \
            '下一击按旧级重算 = 花金零等级推进)'
        # 满级腿(并入,原 test_levelup_full_cap_noop):零金零经验零写
        st_cap = _state(gold=30, shop=[], level=10, xp=(0, 4))
        gs_cap = _gs_of(st_cap)
        _project_with_merge_leg(
            gs_cap, LevelUpShop(cost=4),
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
        st = _state(gold=30, shop=[], level=5, xp=(18, 20))
        gs = _gs_of(st)
        assert max_units_of(gs) == 5, '前置:cap 地板 = 滞留级 5'
        _project_with_merge_leg(
            gs, LevelUpShop(cost=4), ShopActionExecuted(levelup_clicks=2))
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
        st = _state(gold=30, shop=[], level=5, xp=(15, 20))
        gs = _gs_of(st)
        _project_with_merge_leg(
            gs, LevelUpShop(cost=4), ShopActionExecuted(levelup_clicks=1))
        assert gs.level.value == 5, 'level: 15+4=19 < 门槛 20 零跨档不写'
        assert gs.xp.value == (19, 20), 'xp: 推进到位 (19, 20)'
        # 域级跳写对:level 未读(level_readable=False 合成跳写)+ xp 已读
        st_nolv = _state(gold=30, shop=[], xp=(15, 20))
        st_nolv.level_readable = False
        gs2 = _gs_of(st_nolv)
        assert gs2.level.value is None and gs2.xp.value == (15, 20)
        seq0 = gs2.write_seq
        apply_shop_action_logic(
            gs2, LevelUpShop(cost=4),
            executed=ShopActionExecuted(levelup_clicks=1),
            produced_by='LevelUpShop', sig=_SIG)
        assert gs2.level.value is None, 'level 未读保持未读'
        assert gs2.xp.value == (15, 20) and gs2.xp.source == 'observation', \
            'level 未读 → 推进对整体跳写(禁缺省 1 参与推进计算;' \
            'xp 值留观察原值,source 不翻 logic)'
        assert gs2.gold.value == 26, 'gold 域独立于推进对照写'
        assert gs2.write_seq > seq0, '跳写对 ≠ 整动作零写(gold 仍落)'

    def test_refresh_paid_deducts_gold(self):
        """付费刷新:gold −刷新费;payload 不写(刷后牌面等续段重观察)。"""
        st = _state(gold=30, shop=[_card('希儿')])
        gs = _gs_of(st)
        _project_with_merge_leg(
            gs, RefreshShop(cost=2), ShopActionExecuted(refresh_paid=2))
        assert gs.gold.value == 28, 'gold: 期望 30 −刷新费 2'
        assert _content_of(gs) == [(0, '希儿', 1, 3)], \
            'shop payload: 刷新不写牌面(期望原 5 槽保持:槽1 希儿)'
        assert _bench_slots(gs) == [], 'bench: 刷新腿零写(保持全空)'
        assert gs.xp.value is None, \
            'xp: 刷新腿零写(未读域保持合成初值 None)'

    def test_refresh_free_gold_unwritten(self):
        """免费帧(paid=0):gold 不写(fields.md §3.3.4 免费帧不写语义)。"""
        st = _state(gold=30, shop=[_card('希儿')])
        gs = _gs_of(st)
        apply_shop_action_logic(gs, RefreshShop(cost=2),
                                executed=ShopActionExecuted(refresh_paid=0),
                                produced_by='RefreshShop', sig=_SIG)
        assert gs.gold.value == 30

    def test_close_shop_leaves_screen(self):
        """CloseShop:结构离屏(shop payload → None,left_screen)。"""
        st = _state(gold=30, shop=[_card('希儿')])
        gs = _gs_of(st)
        assert gs.shop.value is not None
        apply_shop_action_logic(gs, CloseShop(),
                                executed=ShopActionExecuted(),
                                produced_by='CloseShop', sig=_SIG)
        assert gs.shop.value is None

    def test_missing_receipt_selfcomputes_ideal_execution(self):
        """回执缺字段 = 该动作自算理想执行(单买 k=1)
        (改写:旧锁「回执缺字段 = 零写」语义已随转移函数
        单源化废止——apply_shop_action_logic docstring「k 来源」段申报:
        executed 给定 = 回执 k(live),None = 理想执行自算(简单腿 1,
        满栏从应用机器出);域未读跳写语义独立,归
        test_none_gold_domain_skip 辖。)"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            shop_payload_content_cards,
        )
        st = _state(gold=30, shop=[_card('希儿', cost=3)])
        gs = _gs_of(st)
        apply_shop_action_logic(gs, BuyCard(card=_card('希儿', cost=3)),
                                executed=ShopActionExecuted(),
                                produced_by='BuyCard', sig=_SIG)
        assert gs.gold.value == 27, '自算 k=1:gold −单价'
        assert len(shop_payload_content_cards(gs.shop.value)) == 0, \
            'payload 该张移除'
        assert bench_occupied(bench_slots_to_legacy(gs.bench.value)) == 1, \
            'bench 落位'

    def test_none_gold_domain_skip(self):
        """None 域跳写:gold 未读(容器 None)时 gold 跳写,其余域照写。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            shop_payload_content_cards,
        )
        st = _state(gold=30, shop=[_card('希儿', cost=3)])
        gs = _gs_of(st)
        gs.write_logic(gs.gold, None, produced_by='test',
                       sig=ChannelSig(family='logic_hook',
                                      actor='synthesize_from_game_state'))
        apply_shop_action_logic(gs, BuyCard(card=_card('希儿', cost=3)),
                                executed=ShopActionExecuted(bought_count=1),
                                produced_by='BuyCard', sig=_SIG)
        assert gs.gold.value is None
        # 改写依据:三态定长五槽(用户三态裁定 2026-09-13),买后 content
        # 紧缩计数 = 旧紧缩列表长度等价读法。
        assert len(shop_payload_content_cards(gs.shop.value)) == 0
        assert bench_occupied(bench_slots_to_legacy(gs.bench.value)) == 1

    def test_stale_sell_proposal_no_write(self):
        """陈旧卖出提案(空槽/越界):守卫辖面,本口零写;集外动作型零写
        腿(并入,原 test_out_of_set_action_no_write):登记面未收编动作型
        照样零写,禁扩静默。"""
        st = _state(gold=30, shop=[])
        gs = _gs_of(st)
        seq0 = gs.write_seq
        apply_shop_action_logic(gs, SellBench(bench_idx=0, income=3),
                                executed=ShopActionExecuted(),
                                produced_by='SellBench', sig=_SIG)
        assert gs.write_seq == seq0
        # 集外动作型腿(并入):DeployMove 不在投影登记面 → 零写
        from sr_od.application.currency_war.kernel.cw_vocab import (
            DeployMove,
        )
        st_oos = _state(gold=30, shop=[], bench=[_bc('希儿', slot=1)])
        gs_oos = _gs_of(st_oos)
        seq0_oos = gs_oos.write_seq
        apply_shop_action_logic(
            gs_oos, DeployMove(bench_idx=0, to_row='front', faction='?'),
            executed=ShopActionExecuted(),
            produced_by='DeployMove', sig=_SIG)
        assert gs_oos.write_seq == seq0_oos, '集外动作型零写(禁扩静默)'

    def test_buy_rejected_when_full_and_no_merge(self):
        """满栏且合成不可达 = 游戏拒买(ADR-0283):零写(own=0 满栏域
        ADR-0619 门)。"""
        bench = [_bc(f'c{i}', star=1, slot=i + 1) for i in range(9)]
        st = _state(gold=30, shop=[_card('姬子', cost=3)], bench=bench)
        gs = _gs_of(st)
        seq0 = gs.write_seq
        apply_shop_action_logic(gs, BuyCard(card=_card('姬子', cost=3)),
                                executed=ShopActionExecuted(bought_count=1),
                                produced_by='BuyCard', sig=_SIG)
        assert gs.write_seq == seq0
        assert gs.gold.value == 30, 'gold: 拒买零写金不动(期望 30)'

    # (原 test_legacy_conversion_roundtrip_view 删:转换透传面已被
    #  test_cw_game_state.py 的 shop_card_mapping 往返锁完整辖住(x 对齐/
    #  记录字段透传),本测为同函数低强度复述,子集断言不留。)


def test_shop_entry_funnel_bench_survives_synthesis() -> None:
    """商店入口漏斗 bench 写门场景锁(run_buy_waves 入口链回归):
    visit 入口 = v1 帧合成;容器 bench 由漏斗真读写入(deploy 后留 bench
    一人),v1 形态帧(bench_readable=False)合成对未读 bench 域跳写——
    容器 bench 保持漏斗真读值,与执行账 tracked 同源不破。回归形态 = 无门
    合成把容器 bench 覆盖成「9 槽全空」假真空(实机 2026-09-13 商店段
    循环崩溃 15+ 连发实证;原断言载体双账守卫已退役,本锁改
    容器/tracked 双侧直断言)。"""
    from types import SimpleNamespace

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
        + [BenchSlot(kind='unit', unit=Unit(char_id='银枝', star=1, slot=4))]
        + [BenchSlot(kind='empty')] * 5,
        capacity=9),
        sig=ChannelSig(family='obs', actor='CwScreenPrep', mode='read'))
    session = SimpleNamespace()
    _tracked = [_bc('银枝', star=1, slot=4)]
    game_state_of(session).tracked_books.bench = _tracked
    # v1 形态帧:bench 恒默认空表 + 不可读位(生产置位点 = read_game_state)
    st = _state(gold=30, shop=[])
    st.bench_readable = False
    synthesize_from_game_state(gs, st)
    # 旧无门合成在此把容器 bench 覆盖成 9 空槽假真空
    view = gs.bench.value
    assert view is not None and view.slots[3].unit is not None \
        and view.slots[3].unit.char_id == '银枝', \
        '合成后容器 bench 仍为漏斗真读值(未读域跳写,兜底空表不覆盖)'
    assert [(b.char_id, b.star) for b in
            game_state_of(session).tracked_books.bench if b is not None] \
        == [('银枝', 1)], '执行账 tracked 不受合成影响(容器/执行两账同源)'
