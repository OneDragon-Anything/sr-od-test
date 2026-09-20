"""W6波4 商店动作投影直写锁(设计件《商店黑板容器化方案》§4-M1/M5)。

- M1 投影行为直锁:生产上报函数单写(买牌快照三件组与升星腿内聚
  ``report_action_buy_card_param`` 函数内)的逐域期望态直断言
  (gold/bench 槽位/shop payload/xp;含满栏多买 −k×单价、升档结转)。
  原对拍基准 = cw_vocab 词表单步动作应用器(纯函数逐动作推进),零
  生产消费随死代码删除退役,本锁到期改直锁(设计件 M1 行申报「收敛
  单形态后本锁改钉单形态」兑现)。
- M5 投影公式语义源锁:None 跳写形态 + 渠道签名纪律(族错显式炸)
  (收口整删:直写域集封闭/executed 回执字段集两条登记面断言——常量
  字面/字段名复述,红时答不出哪个运行行为坏了;消费面纪律归 review)。

口径申报:payload 期望按槽序 content 紧缩视图 (idx, name, star, cost)
冻结(离屏 None 归一空表 = 旧紧缩列表等价读法);bench 期望按槽位
占用签名 (idx, char_id, star) 冻结;xp 未读域按种子缺席钉(None)。

种子载体(benchchar-retirement P5):原 CwSimFrame+合成口路径已退役,
场景种子 = 容器域直写(cw4_gs 裸帧配方:节点不写、空店离屏,与原
合成口域覆盖集逐域一致);投影输出逐字节保形凭据 = 改前/改后探针
diff 为空(.debug/temp/p5_m1/)。
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
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
    report_action_close_shop_param,
    report_action_level_up_shop_param,
    report_action_refresh_shop_param,
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopActionExecuted,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionLevelUpShopParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
)

# 改写依据(分诊):写入者登记面随「商店单动作循环收编」演进——
# 生产写点 actor 现役 = CwScreenBuyCards(cw_screen_buy_cards,登记面在册),
# 旧名 CwOpBuyCards 已退役;测试模拟生产写入随登记面改名。
_SIG = ChannelSig(family='logic_action', actor='CwScreenBuyCards',
                  mode='compute', group_id='act:CwScreenBuyCards@1')


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
    """商店域动作单次上报(生产同形):买牌快照三件组与升星腿内聚
    report 函数内,一动作恰一次调用;合计结果的逐域期望态由各案直锁
    断言(设计件 §4-M1)。executed 仅对带回执参数的函数透传。"""
    if isinstance(action, CwActionBuyCardParam):
        return report_action_buy_card_param(gs, action, _SIG, executed=executed)
    if isinstance(action, CwActionLevelUpShopParam):
        return report_action_level_up_shop_param(gs, action, _SIG,
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
    #  (M1 逐域比对轴/按字段名取值)由下方 M1 等价锁承重,登记面纪律归
    #  review 与代码规范。

    def test_wrong_family_sig_rejected(self):
        """渠道签名纪律:非 logic_action 族显式炸(§3.2.4 硬约束 2)。"""
        gs = _gs_of(gold=30, shop=[_card('希儿')])
        with pytest.raises(ValueError):
            report_action_buy_card_param(
                gs, CwActionBuyCardParam(card=_card('希儿')),
                executed=ShopActionExecuted(bought_count=1),
                sig=ChannelSig(family='obs', actor='CwScreenBuyCards'))


# ==================== M1 投影行为直锁 ====================


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
        assert gs.xp.value is None, 'xp: 买腿零写(未读域保持种子初值 None)'

    # (收口整删)原 test_buy_triggers_merge「合成买(2 副本在席 + 买第
    #  3 张)」删:与 test_full_bench_merge_buy_k(满栏合成 k=2)和
    #  test_merge_buy_single_report_two_forms(合成买单口两形态直锁)
    #  断言面重叠——同一升星腿的第三种摆放,留两形态承重。

    def test_full_bench_merge_buy_k(self):
        """满栏多买(k=2):gold −k×单价 + payload −k 张 + bench 归升星腿
        (本口零落位)。"""
        bench = [_bc(f'c{i}', star=1, slot=i + 1) for i in range(8)]
        bench.append(_bc('希儿', star=1, slot=9))
        cards = [_card('希儿', cost=3, x=0), _card('希儿', cost=3, x=1)]
        gs = _gs_of(gold=60, shop=cards, bench=bench)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            merge_buy_k,
        )
        k = merge_buy_k('希儿', 1, bench, None, cards)
        _report_action(
            gs, CwActionBuyCardParam(card=_card('希儿', cost=3)),
            ShopActionExecuted(bought_count=k))
        assert k == 2
        assert gs.gold.value == 54, 'gold: 期望 60 −单价 3×k2 = 54'
        assert _content_of(gs) == [], \
            'shop payload: 期望全空(k 张同身份牌全部下架)'
        assert _bench_slots(gs) == (
            [(i, f'c{i}', 1) for i in range(8)] + [(8, '希儿', 2)]), \
            'bench: 期望满栏零落位,3 副本合 1 升 2★(在席副本槽9)'
        assert gs.xp.value is None, 'xp: 买腿零写(未读域保持种子初值 None)'

    def test_merge_buy_single_report_two_forms(self):
        """合成买单口两形态直锁(升星腿内聚 report_action_buy_card_param 后,
        原升星腿单写锁随聚合口退役;快照基点正确性 = 两形态 bench 期望
        共辖——基点误取买后容器会重复落位/漏升,shop 视图缺失会漏满栏
        合成):非满栏合成买(2 副本在席买第 3 张 → 落位即合成升 2★)与
        满栏合成买(k=2,3 副本合 1 升 2★ 在席副本槽9)。gold −单价×k 与
        payload −k 由同一单口携带(原「腿零写」申报随两写合一消亡)。"""
        for title, axes, act, k, bench_expect in (
            ('非满栏合成买',
             {'gold': 30, 'shop': [_card('希儿', cost=3)],
              'bench': [_bc('希儿', star=1, slot=1),
                        _bc('希儿', star=1, slot=2)]},
             CwActionBuyCardParam(card=_card('希儿', cost=3)),
             1, [(0, '希儿', 2)]),
            ('满栏合成买(k=2)',
             {'gold': 60, 'shop': [_card('希儿', cost=3, x=0),
                                   _card('希儿', cost=3, x=1)],
              'bench': [_bc(f'c{i}', star=1, slot=i + 1)
                        for i in range(8)] + [_bc('希儿', star=1, slot=9)]},
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
            assert gs.write_seq > seq0, f'{title}: 升星腿整表直写'

    def test_sell_bench_refund(self):
        """卖备战席:bench −该牌 + gold +退款(sell_refund 锚)。"""
        gs = _gs_of(gold=10, shop=[], bench=[_bc('希儿', star=1, slot=1)])
        _report_action(gs, CwActionSellBenchParam(bench_idx=0, income=3))
        assert gs.gold.value == 13, \
            'gold: 期望 10 +退款 3(1★ 希儿 sell_refund 现算)'
        assert _content_of(gs) == [], \
            'shop payload: 期望空(shop 空表帧 = 离屏,零写透传)'
        assert _bench_slots(gs) == [], 'bench: 期望卖出槽置空(9 槽全空)'
        assert gs.xp.value is None, 'xp: 卖腿零写(未读域保持种子初值 None)'

    def test_levelup_clicks_and_level_cross(self):
        """升级:击数×单击价扣金 + xp/level 推进(跨档结转 + level 跨档
        直写,与 prep 腿同款;域集扩申报 = SHOP_PROJECTION_DOMAINS 登记
        面);满级腿(并入):lv10 购买无效,零金零经验零写。"""
        gs = _gs_of(gold=30, shop=[], level=3, xp=(2, 6))
        _report_action(
            gs, CwActionLevelUpShopParam(cost=4), ShopActionExecuted(levelup_clicks=1))
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
        gs_cap = _gs_of(gold=30, shop=[], level=10, xp=(0, 4))
        _report_action(
            gs_cap, CwActionLevelUpShopParam(cost=4),
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
            gs, CwActionLevelUpShopParam(cost=4), ShopActionExecuted(levelup_clicks=2))
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
            gs, CwActionLevelUpShopParam(cost=4), ShopActionExecuted(levelup_clicks=1))
        assert gs.level.value == 5, 'level: 15+4=19 < 门槛 20 零跨档不写'
        assert gs.xp.value == (19, 20), 'xp: 推进到位 (19, 20)'
        # 域级跳写对:level 未读(level_unread 种子缺席)+ xp 已读
        gs2 = _gs_of(gold=30, shop=[], xp=(15, 20), level_unread=True)
        assert gs2.level.value is None and gs2.xp.value == (15, 20)
        seq0 = gs2.write_seq
        report_action_level_up_shop_param(
            gs2, CwActionLevelUpShopParam(cost=4),
            _SIG, executed=ShopActionExecuted(levelup_clicks=1))
        assert gs2.level.value is None, 'level 未读保持未读'
        assert gs2.xp.value == (15, 20) and gs2.xp.source == 'observation', \
            'level 未读 → 推进对整体跳写(禁缺省 1 参与推进计算;' \
            'xp 值留种子原值,source 不翻 logic)'
        assert gs2.gold.value == 26, 'gold 域独立于推进对照写'
        assert gs2.write_seq > seq0, '跳写对 ≠ 整动作零写(gold 仍落)'

    def test_refresh_paid_deducts_gold(self):
        """付费刷新:gold −刷新费;payload 不写(刷后牌面等续段重观察)。"""
        gs = _gs_of(gold=30, shop=[_card('希儿')])
        _report_action(
            gs, CwActionRefreshShopParam(cost=2), ShopActionExecuted(refresh_paid=2))
        assert gs.gold.value == 28, 'gold: 期望 30 −刷新费 2'
        assert _content_of(gs) == [(0, '希儿', 1, 3)], \
            'shop payload: 刷新不写牌面(期望原 5 槽保持:槽1 希儿)'
        assert _bench_slots(gs) == [], 'bench: 刷新腿零写(保持全空)'
        assert gs.xp.value is None, \
            'xp: 刷新腿零写(未读域保持种子初值 None)'

    def test_refresh_free_gold_unwritten(self):
        """免费帧(paid=0):gold 不写(fields.md §3.3.4 免费帧不写语义)。"""
        gs = _gs_of(gold=30, shop=[_card('希儿')])
        report_action_refresh_shop_param(gs, CwActionRefreshShopParam(cost=2),
                                         _SIG,
                                         executed=ShopActionExecuted(refresh_paid=0))
        assert gs.gold.value == 30

    def test_close_shop_leaves_screen(self):
        """CwActionCloseShopParam:结构离屏(shop payload → None,left_screen)。"""
        gs = _gs_of(gold=30, shop=[_card('希儿')])
        assert gs.shop.value is not None
        report_action_close_shop_param(gs, CwActionCloseShopParam(), _SIG)
        assert gs.shop.value is None

    def test_missing_receipt_selfcomputes_ideal_execution(self):
        """回执缺字段 = 该动作自算理想执行(单买 k=1)
        (改写:旧锁「回执缺字段 = 零写」语义已随转移函数
        单源化废止——report_action_buy_card_param docstring「k 来源」段申报:
        executed 给定 = 回执 k(live),None = 理想执行自算(简单腿 1,
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
        (集外动作型零写腿删:上报函数族每动作恰一函数,无按类型聚合的
        登记面可「静默收编集外型」——闭集性质归命名规约完备锁
        test_cw_action_report_contract 辖。)"""
        gs = _gs_of(gold=30, shop=[])
        seq0 = gs.write_seq
        report_action_sell_bench_param(
            gs, CwActionSellBenchParam(bench_idx=0, income=3), _SIG)
        assert gs.write_seq == seq0

    def test_buy_rejected_when_full_and_no_merge(self):
        """满栏且合成不可达 = 游戏拒买(ADR-0283):零写(own=0 满栏域
        ADR-0619 门)。"""
        bench = [_bc(f'c{i}', star=1, slot=i + 1) for i in range(9)]
        gs = _gs_of(gold=30, shop=[_card('姬子', cost=3)], bench=bench)
        seq0 = gs.write_seq
        report_action_buy_card_param(gs, CwActionBuyCardParam(card=_card('姬子', cost=3)),
                                     _SIG, executed=ShopActionExecuted(bought_count=1))
        assert gs.write_seq == seq0
        assert gs.gold.value == 30, 'gold: 拒买零写金不动(期望 30)'

    # (原 test_legacy_conversion_roundtrip_view 删:转换透传面已被
    #  test_cw_game_state.py 的 shop_card_mapping 往返锁完整辖住(x 对齐/
    #  记录字段透传),本测为同函数低强度复述,子集断言不留。)


def test_shop_entry_funnel_bench_survives_synthesis() -> None:
    """商店入口漏斗 bench 写门场景锁(run_buy_waves 入口链回归):
    种子对未声明 bench 域整域跳写(bench_unread)——容器 bench 保持
    漏斗真读值,与执行账 tracked 同源不破。回归形态 = 种子把容器 bench
    覆盖成「9 槽全空」假真空(原防御对象 = 旧合成口无门合成,实机
    2026-09-13 商店段循环崩溃 15+ 连发实证;载体随合成口退役改种子
    域纪律锁:未读域≠真空域,跳写语义在种子层等价存续)。"""
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
    # 未读 bench 域种子(生产置位点 = read_game_state 漏斗不读席位的形态)
    cw4_gs(gs, gold=30, shop_screen='off', bench_unread=True, node_fill=False)
    view = gs.bench.value
    assert view is not None and view.slots[3].unit is not None \
        and view.slots[3].unit.char_id == '银枝', \
        '种子后容器 bench 仍为漏斗真读值(未读域跳写,兜底空表不覆盖)'
    assert [(b.unit.char_id, b.unit.star) for b in
            game_state_of(session).tracked_books.bench if b is not None] \
        == [('银枝', 1)], '执行账 tracked 不受种子影响(容器/执行两账同源)'
