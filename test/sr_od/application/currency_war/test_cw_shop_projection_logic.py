"""W6波4 商店动作投影直写锁(设计件《商店黑板容器化方案》§4-M1/M5)。

- M1 投影行为等价锁:生产两写合计(``apply_shop_action_logic`` 投影口
  直写 + ``apply_shop_merge_leg`` 合成升星整表直写,买前快照基点;
  此后 simulate 前瞻投影已删,simulate 在本文件只作**等价性基准**)
  vs ``cw_state.simulate``:同动作同输入逐域等价
  (gold/bench/shop payload/xp;含满栏多买 −k×单价)。波 5 sim 反转
  收敛单形态后本锁改钉单形态(设计件 M1 行申报)。
- M5 投影公式语义源锁:None 跳写形态 + 渠道签名纪律(族错显式炸)
  (收口整删:直写域集封闭/executed 回执字段集两条登记面断言——常量
  字面/字段名复述,红时答不出哪个运行行为坏了;消费面纪律归 review)。

口径申报:payload 对比按 canonical 序(name,star,cost)——容器牌无 x
坐标,simulate 的 x 槽位删除与投影口的 (name,star) 计数删除为同义多集
操作;bench 对比按槽位表身份签名(逐槽 (char_id, star))。
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
    board_state_of,
    deployed_slots_of,
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
    simulate,
)

# 改写依据(分诊):写入者登记面随「商店单动作循环收编」演进——
# 生产写点 actor 现役 = CwScreenBuyCards(cw_screen_buy_cards,登记面在册),
# 旧名 CwOpBuyCards 已退役;测试模拟生产写入随登记面改名。
_SIG = ChannelSig(family='logic_action', actor='CwScreenBuyCards',
                  mode='compute', group_id='act:CwScreenBuyCards@1')


def _bs_of(st):
    """CwSimFrame 桩帧 → 容器(sim 合成口;测试/生产同一条喂入通道)。"""
    bs = board_state_of(None)
    synthesize_from_game_state(bs, st)
    return bs


def _sig_of(container):
    """槽位表占用身份签名(逐槽 (char_id, star);None 洞跳过)。"""
    return [(b.char_id or '', b.star or 1) for b in container
            if b is not None]


def _project_with_merge_leg(bs, action, executed, st_frame):
    """执行落地门两写合计的测试复刻(现生产同形):买前快照三件组
    → 投影口直写 → 升星腿整表直写(先投影口后升星写,后写赢)。
    ``simulate(st_frame, action)`` 作等价性基准(kernel 单步应用器;非
    策略决策消费)。"""
    sim = simulate(st_frame, action)
    pre_bench = list(bench_slots_of(bs))
    pre_dep = list(deployed_slots_of(bs))
    pre_shop = (list(bs.shop.value.cards)
                if bs.shop.value is not None else [])
    apply_shop_action_logic(bs, action, executed=executed,
                            produced_by=type(action).__name__, sig=_SIG)
    if isinstance(action, BuyCard):
        apply_shop_merge_leg(bs, action, sig=_SIG, pre_bench=pre_bench,
                             pre_deployed=pre_dep, pre_shop=pre_shop)
    return sim


def _assert_domains_equal(bs, sim):
    """M1 逐域等价断言(gold/bench/shop payload/xp 四域)。"""
    assert bs.gold.value == sim.gold, \
        f'gold: {bs.gold.value} != {sim.gold}'
    # 改写依据:商店 payload 三态定长五槽模型(用户三态裁定 2026-09-13),
    # content 槽紧缩视图 = 旧紧缩列表等价读法。
    got = sorted((c.card.name, c.card.star or 1, c.card.cost or 0)
                 for c in (bs.shop.value.cards if bs.shop.value else [])
                 if c.kind == 'content' and c.card is not None)
    want = sorted((c.name, c.star or 1, c.cost or 0) for c in sim.shop)
    assert got == want, f'shop payload: {got} != {want}'
    assert _sig_of(bench_slots_to_legacy(bs.bench.value)) \
        == _sig_of(sim.bench), \
        f'bench: {_sig_of(bench_slots_to_legacy(bs.bench.value))} ' \
        f'!= {_sig_of(sim.bench)}'
    assert tuple(bs.xp.value or ()) == tuple(sim.xp_progress or ())


# ==================== M5 登记面 ====================


class TestM5Registration:

    # (收口整删)原 test_projection_domain_set_closed「直写域集封闭八域」
    # 与 test_executed_receipt_field_set「executed 回执字段集登记」删:
    # 常量/字段名复述断言,红时是常量或字段改名而非运行行为坏;消费面
    # (M1 逐域比对轴/按字段名取值)由下方 M1 等价锁承重,登记面纪律归
    # review 与代码规范。

    def test_wrong_family_sig_rejected(self):
        """渠道签名纪律:非 logic_action 族显式炸(§3.2.4 硬约束 2)。"""
        bs = _bs_of(_state(gold=30, shop=[_card('希儿')]))
        with pytest.raises(ValueError):
            apply_shop_action_logic(
                bs, BuyCard(card=_card('希儿')),
                executed=ShopActionExecuted(bought_count=1),
                produced_by='BuyCard',
                sig=ChannelSig(family='obs', actor='CwScreenBuyCards'))


# ==================== M1 投影行为等价锁 ====================


class TestM1Equivalence:

    def test_buy_simple_placement(self):
        """简单买:gold −单价 + bench 落位(首空槽)+ payload −该张。"""
        st = _state(gold=30, shop=[_card('希儿', cost=3)])
        bs = _bs_of(st)
        sim = _project_with_merge_leg(
            bs, BuyCard(card=_card('希儿', cost=3)),
            ShopActionExecuted(bought_count=1), st)
        _assert_domains_equal(bs, sim)

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
        bs = _bs_of(st)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            merge_buy_k,
        )
        k = merge_buy_k('希儿', 1, st.bench, st.deployed, st.shop)
        sim = _project_with_merge_leg(
            bs, BuyCard(card=_card('希儿', cost=3)),
            ShopActionExecuted(bought_count=k), st)
        assert k == 2
        _assert_domains_equal(bs, sim)

    def test_merge_leg_alone_prestate_basis(self):
        """升星腿直锁(快照基点回归):腿单写(不跑投影口)时,
        买前快照基点 + shop 视图透传的合成结果对 simulate bench 逐槽等价
        ——非满栏合成买与满栏合成买两形态;gold/payload 域零写(腿只辖
        bench 整表)。基点误取买后容器会重复落位、shop 视图缺失会漏满栏
        合成(失准形态申报见 apply_shop_merge_leg docstring)。"""
        for title, st, act in (
            ('非满栏合成买',
             _state(gold=30, shop=[_card('希儿', cost=3)],
                    bench=[_bc('希儿', star=1, slot=1),
                           _bc('希儿', star=1, slot=2)]),
             BuyCard(card=_card('希儿', cost=3))),
            ('满栏合成买(k=2)',
             _state(gold=60, shop=[_card('希儿', cost=3, x=0),
                                   _card('希儿', cost=3, x=1)],
                    bench=[_bc(f'c{i}', star=1, slot=i + 1)
                           for i in range(8)] + [_bc('希儿', star=1, slot=9)]),
             BuyCard(card=_card('希儿', cost=3))),
        ):
            sim = simulate(st, act)
            bs = _bs_of(st)
            seq0 = bs.write_seq
            # 改写依据(分诊):三态定长五槽模型(用户三态裁定
            # 2026-09-13)后 payload.cards 恒定长 5,「长度不变」旧断言失效;
            # 「腿禁写 payload 域」等价形态 = payload 对象引用不变
            # (observe 换值才换引用)。测试体内 x=100/200 旧画面坐标桩值
            # 同步改槽下标(0/1),合成口按 x 对槽越界丢卡。
            pre_shop_payload = bs.shop.value
            apply_shop_merge_leg(
                bs, act, sig=_SIG,
                pre_bench=list(bench_slots_of(bs)),
                pre_deployed=list(deployed_slots_of(bs)),
                # pre_shop 形态 = 旧牌紧缩视图(与生产投影口同形;
                # 分诊:三态 payload 直传 ShopSlot 列表喂不进
                # mutate 机器的满栏合成素材消费)。
                pre_shop=(shop_cards_to_legacy(
                    shop_payload_content_cards(pre_shop_payload))
                    if pre_shop_payload is not None else []))
            assert _sig_of(bench_slots_to_legacy(bs.bench.value)) \
                == _sig_of(sim.bench), f'{title}: bench 与 simulate 失配'
            assert bs.gold.value == st.gold, f'{title}: 腿禁写 gold 域'
            assert bs.shop.value is pre_shop_payload, \
                f'{title}: 腿禁写 payload 域(引用不变)'
            assert bs.write_seq > seq0, f'{title}: 升星腿应整表直写'

    def test_sell_bench_refund(self):
        """卖备战席:bench −该牌 + gold +退款(sell_refund 锚)。"""
        st = _state(gold=10, shop=[], bench=[_bc('希儿', star=1, slot=1)])
        bs = _bs_of(st)
        sim = _project_with_merge_leg(
            bs, SellBench(bench_idx=0, income=3),
            ShopActionExecuted(), st)
        _assert_domains_equal(bs, sim)

    def test_levelup_clicks_and_level_cross(self):
        """升级:击数×单击价扣金 + xp 推进(含升档结转;level 域不投影);
        满级腿(并入):lv10 购买无效,零金零经验(与 simulate 同门)。"""
        st = _state(gold=30, shop=[], level=3, xp=(2, 6))
        bs = _bs_of(st)
        sim = _project_with_merge_leg(
            bs, LevelUpShop(cost=4), ShopActionExecuted(levelup_clicks=1), st)
        _assert_domains_equal(bs, sim)
        assert bs.level.value == st.level   # level 域不在投影域集
        # 满级腿(并入,原 test_levelup_full_cap_noop):零金零经验
        st_cap = _state(gold=30, shop=[], level=10, xp=(0, 4))
        bs_cap = _bs_of(st_cap)
        sim_cap = _project_with_merge_leg(
            bs_cap, LevelUpShop(cost=4),
            ShopActionExecuted(levelup_clicks=1), st_cap)
        _assert_domains_equal(bs_cap, sim_cap)
        assert bs_cap.gold.value == 30 and tuple(bs_cap.xp.value or ()) == (
            0, 4), '满级购买零金零经验(购买无效)'
        assert bs_cap.level.value == 10, 'level 域不投影(满级不动)'

    def test_refresh_paid_deducts_gold(self):
        """付费刷新:gold −刷新费;payload 不写(刷后牌面等续段重观察)。"""
        st = _state(gold=30, shop=[_card('希儿')])
        bs = _bs_of(st)
        sim = _project_with_merge_leg(
            bs, RefreshShop(cost=2), ShopActionExecuted(refresh_paid=2), st)
        _assert_domains_equal(bs, sim)

    def test_refresh_free_gold_unwritten(self):
        """免费帧(paid=0):gold 不写(fields.md §3.3.4 免费帧不写语义)。"""
        st = _state(gold=30, shop=[_card('希儿')])
        bs = _bs_of(st)
        apply_shop_action_logic(bs, RefreshShop(cost=2),
                                executed=ShopActionExecuted(refresh_paid=0),
                                produced_by='RefreshShop', sig=_SIG)
        assert bs.gold.value == 30

    def test_close_shop_leaves_screen(self):
        """CloseShop:结构离屏(shop payload → None,left_screen)。"""
        st = _state(gold=30, shop=[_card('希儿')])
        bs = _bs_of(st)
        assert bs.shop.value is not None
        apply_shop_action_logic(bs, CloseShop(),
                                executed=ShopActionExecuted(),
                                produced_by='CloseShop', sig=_SIG)
        assert bs.shop.value is None

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
        bs = _bs_of(st)
        apply_shop_action_logic(bs, BuyCard(card=_card('希儿', cost=3)),
                                executed=ShopActionExecuted(),
                                produced_by='BuyCard', sig=_SIG)
        assert bs.gold.value == 27, '自算 k=1:gold −单价'
        assert len(shop_payload_content_cards(bs.shop.value)) == 0, \
            'payload 该张移除'
        assert bench_occupied(bench_slots_to_legacy(bs.bench.value)) == 1, \
            'bench 落位'

    def test_none_gold_domain_skip(self):
        """None 域跳写:gold 未读(容器 None)时 gold 跳写,其余域照写。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            shop_payload_content_cards,
        )
        st = _state(gold=30, shop=[_card('希儿', cost=3)])
        bs = _bs_of(st)
        bs.write_logic(bs.gold, None, produced_by='test',
                       sig=ChannelSig(family='logic_hook',
                                      actor='synthesize_from_game_state'))
        apply_shop_action_logic(bs, BuyCard(card=_card('希儿', cost=3)),
                                executed=ShopActionExecuted(bought_count=1),
                                produced_by='BuyCard', sig=_SIG)
        assert bs.gold.value is None
        # 改写依据:三态定长五槽(用户三态裁定 2026-09-13),买后 content
        # 紧缩计数 = 旧紧缩列表长度等价读法。
        assert len(shop_payload_content_cards(bs.shop.value)) == 0
        assert bench_occupied(bench_slots_to_legacy(bs.bench.value)) == 1

    def test_stale_sell_proposal_no_write(self):
        """陈旧卖出提案(空槽/越界):守卫辖面,本口零写;集外动作型零写
        腿(并入,原 test_out_of_set_action_no_write):登记面未收编动作型
        照样零写,禁扩静默。"""
        st = _state(gold=30, shop=[])
        bs = _bs_of(st)
        seq0 = bs.write_seq
        apply_shop_action_logic(bs, SellBench(bench_idx=0, income=3),
                                executed=ShopActionExecuted(),
                                produced_by='SellBench', sig=_SIG)
        assert bs.write_seq == seq0
        # 集外动作型腿(并入):DeployMove 不在投影登记面 → 零写
        from sr_od.application.currency_war.kernel.cw_vocab import (
            DeployMove,
        )
        st_oos = _state(gold=30, shop=[], bench=[_bc('希儿', slot=1)])
        bs_oos = _bs_of(st_oos)
        seq0_oos = bs_oos.write_seq
        apply_shop_action_logic(
            bs_oos, DeployMove(bench_idx=0, to_row='front', faction='?'),
            executed=ShopActionExecuted(),
            produced_by='DeployMove', sig=_SIG)
        assert bs_oos.write_seq == seq0_oos, '集外动作型零写(禁扩静默)'

    def test_buy_rejected_when_full_and_no_merge(self):
        """满栏且合成不可达 = 游戏拒买(ADR-0283):零写(simulate 同判
        no-op,own=0 满栏域 ADR-0619 门)。"""
        bench = [_bc(f'c{i}', star=1, slot=i + 1) for i in range(9)]
        st = _state(gold=30, shop=[_card('姬子', cost=3)], bench=bench)
        bs = _bs_of(st)
        seq0 = bs.write_seq
        apply_shop_action_logic(bs, BuyCard(card=_card('姬子', cost=3)),
                                executed=ShopActionExecuted(bought_count=1),
                                produced_by='BuyCard', sig=_SIG)
        assert bs.write_seq == seq0
        assert st.gold == simulate(st, BuyCard(card=_card('姬子', cost=3))
                                   ).gold   # simulate 同 no-op

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

    bs = board_state_of(None)
    # prep 装配环式真读观察(bench 观察写端 = 备战装配环 heavy 块;此处
    # 复刻其产物形态):deploy 后 bench 物理槽 4 留一人
    bs.observe(bs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 3
        + [BenchSlot(kind='unit', unit=Unit(char_id='银枝', star=1, slot=4))]
        + [BenchSlot(kind='empty')] * 5,
        capacity=9),
        sig=ChannelSig(family='obs', actor='CwScreenPrep', mode='read'))
    session = SimpleNamespace()
    _tracked = [_bc('银枝', star=1, slot=4)]
    board_state_of(session).tracked_books.bench = _tracked
    # v1 形态帧:bench 恒默认空表 + 不可读位(生产置位点 = read_game_state)
    st = _state(gold=30, shop=[])
    st.bench_readable = False
    synthesize_from_game_state(bs, st)
    # 旧无门合成在此把容器 bench 覆盖成 9 空槽假真空
    view = bs.bench.value
    assert view is not None and view.slots[3].unit is not None \
        and view.slots[3].unit.char_id == '银枝', \
        '合成后容器 bench 仍为漏斗真读值(未读域跳写,兜底空表不覆盖)'
    assert [(b.char_id, b.star) for b in
            board_state_of(session).tracked_books.bench if b is not None] \
        == [('银枝', 1)], '执行账 tracked 不受合成影响(容器/执行两账同源)'
