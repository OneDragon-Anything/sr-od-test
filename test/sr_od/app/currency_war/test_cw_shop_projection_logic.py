"""T-97 W6波4 商店动作投影直写锁(设计件《商店黑板容器化方案》§4-M1/M5)。

- M1 投影行为等价锁:``apply_shop_action_logic``(容器直写,合成升星腿
  由执行侧既有 ``detect_merge_upgrade`` 整表直写承接——测试内按执行侧
  同序复刻两写合计)vs ``cw_state.simulate``:同动作同输入逐域等价
  (gold/bench/shop payload/xp;含满栏多买 −k×单价)。波 5 sim 反转
  收敛单形态后本锁改钉单形态(设计件 M1 行申报)。
- M5 投影公式语义源锁:登记面断言(直写域集封闭/executed 回执字段集/
  None 跳写形态)+ 渠道签名纪律(族错显式炸)。

口径申报:payload 对比按 canonical 序(name,star,cost)——容器牌无 x
坐标,simulate 的 x 槽位删除与投影口的 (name,star) 计数删除为同义多集
操作;bench 对比按槽位表身份签名(逐槽 (char_id, star))。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.kernel.cw_board_state import (
    ChannelSig,
    ShopActionExecuted,
    SHOP_PROJECTION_DOMAINS,
    apply_shop_action_logic,
    bench_slots_to_legacy,
    board_state_of,
    detect_merge_upgrade,
    shop_cards_to_legacy,
    synthesize_from_game_state,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    CloseShop,
    LevelUpShop,
    RefreshShop,
    SellBench,
    bench_occupied,
    simulate,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_state as _state,
)

_SIG = ChannelSig(family='logic_action', actor='CwOpBuyCards',
                  mode='compute', group_id='act:CwOpBuyCards@1')


def _bs_of(st):
    """GameState 桩帧 → 容器(sim 合成口;测试/生产同一条喂入通道)。"""
    bs = board_state_of(None)
    synthesize_from_game_state(bs, st)
    return bs


def _sig_of(container):
    """槽位表占用身份签名(逐槽 (char_id, star);None 洞跳过)。"""
    return [(b.char_id or '', b.star or 1) for b in container
            if b is not None]


def _project_with_merge_leg(bs, action, executed, st_frame):
    """执行落地门两写合计的测试复刻:投影口直写 → 升星腿整表直写
    (顺序与 cw_op_buy_cards.apply_action_outcome 一致:先投影口后
    升星写,后写赢)。返回逐动作 simulate 帧(供逐域对拍)。"""
    sim = simulate(st_frame, action)
    apply_shop_action_logic(bs, action, executed=executed,
                            produced_by=type(action).__name__, sig=_SIG)
    if isinstance(action, BuyCard) and detect_merge_upgrade(st_frame, sim):
        from sr_od.application.currency_war.kernel.cw_board_state import (
            bench_view_of_slots,
        )
        bs.write_logic(bs.bench, bench_view_of_slots(sim.bench),
                       produced_by='BuyCard',
                       sig=ChannelSig(family='logic_action',
                                      actor='CwOpBuyCards',
                                      mode='compute',
                                      group_id=f'act:CwOpBuyCards@'
                                               f'{bs.write_seq + 1}'))
    return sim


def _assert_domains_equal(bs, sim):
    """M1 逐域等价断言(gold/bench/shop payload/xp 四域)。"""
    assert bs.gold.value == sim.gold, \
        f'gold: {bs.gold.value} != {sim.gold}'
    got = sorted((c.name, c.star or 1, c.cost or 0)
                 for c in (bs.shop.value.cards if bs.shop.value else []))
    want = sorted((c.name, c.star or 1, c.cost or 0) for c in sim.shop)
    assert got == want, f'shop payload: {got} != {want}'
    assert _sig_of(bench_slots_to_legacy(bs.bench.value)) \
        == _sig_of(sim.bench), \
        f'bench: {_sig_of(bench_slots_to_legacy(bs.bench.value))} ' \
        f'!= {_sig_of(sim.bench)}'
    assert tuple(bs.xp.value or ()) == tuple(sim.xp_progress or ())


# ==================== M5 登记面 ====================


class TestM5Registration:

    def test_projection_domain_set_closed(self):
        """直写域集封闭四域(禁扩静默,登记面即锁)。"""
        assert SHOP_PROJECTION_DOMAINS == ('gold', 'bench', 'shop', 'xp')

    def test_executed_receipt_field_set(self):
        """executed 回执字段集登记(bought_count/levelup_clicks/
        refresh_paid;缺字段 None = 该动作不投影)。"""
        assert [f.name for f in dataclasses.fields(ShopActionExecuted)] \
            == ['bought_count', 'levelup_clicks', 'refresh_paid']
        assert ShopActionExecuted().bought_count is None

    def test_wrong_family_sig_rejected(self):
        """渠道签名纪律:非 logic_action 族显式炸(§3.2.4 硬约束 2)。"""
        bs = _bs_of(_state(gold=30, shop=[_card('希儿')]))
        with pytest.raises(ValueError):
            apply_shop_action_logic(
                bs, BuyCard(card=_card('希儿')),
                executed=ShopActionExecuted(bought_count=1),
                produced_by='BuyCard',
                sig=ChannelSig(family='obs', actor='CwOpBuyCards'))


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

    def test_buy_triggers_merge(self):
        """合成买(2 副本在席 + 买第 3 张):落位写 + 升星整表写合计
        对 simulate 等价。"""
        st = _state(gold=30, shop=[_card('希儿', cost=3)],
                    bench=[_bc('希儿', star=1, slot=1),
                           _bc('希儿', star=1, slot=2)])
        bs = _bs_of(st)
        sim = _project_with_merge_leg(
            bs, BuyCard(card=_card('希儿', cost=3)),
            ShopActionExecuted(bought_count=1), st)
        assert detect_merge_upgrade(st, sim)   # 升星腿确曾触发
        _assert_domains_equal(bs, sim)

    def test_full_bench_merge_buy_k(self):
        """满栏多买(k=2):gold −k×单价 + payload −k 张 + bench 归升星腿
        (本口零落位)。"""
        bench = [_bc(f'c{i}', star=1, slot=i + 1) for i in range(8)]
        bench.append(_bc('希儿', star=1, slot=9))
        st = _state(gold=60, shop=[_card('希儿', cost=3, x=100),
                                   _card('希儿', cost=3, x=200)],
                    bench=bench)
        bs = _bs_of(st)
        from sr_od.application.currency_war.kernel.cw_state import (
            merge_buy_k,
        )
        k = merge_buy_k('希儿', 1, st.bench, st.deployed, st.shop)
        sim = _project_with_merge_leg(
            bs, BuyCard(card=_card('希儿', cost=3)),
            ShopActionExecuted(bought_count=k), st)
        assert k == 2
        _assert_domains_equal(bs, sim)

    def test_sell_bench_refund(self):
        """卖备战席:bench −该牌 + gold +退款(sell_refund 锚)。"""
        st = _state(gold=10, shop=[], bench=[_bc('希儿', star=1, slot=1)])
        bs = _bs_of(st)
        sim = _project_with_merge_leg(
            bs, SellBench(bench_idx=0, income=3),
            ShopActionExecuted(), st)
        _assert_domains_equal(bs, sim)

    def test_levelup_clicks_and_level_cross(self):
        """升级:击数×单击价扣金 + xp 推进(含升档结转;level 域不投影)。"""
        st = _state(gold=30, shop=[], level=3, xp=(2, 6))
        bs = _bs_of(st)
        sim = _project_with_merge_leg(
            bs, LevelUpShop(cost=4), ShopActionExecuted(levelup_clicks=1), st)
        _assert_domains_equal(bs, sim)
        assert bs.level.value == st.level   # level 域不在投影域集

    def test_levelup_full_cap_noop(self):
        """满级 lv10 购买无效:零金零经验(与 simulate 同门)。"""
        st = _state(gold=30, shop=[], level=10, xp=(0, 4))
        bs = _bs_of(st)
        sim = _project_with_merge_leg(
            bs, LevelUpShop(cost=4), ShopActionExecuted(levelup_clicks=1), st)
        _assert_domains_equal(bs, sim)

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

    def test_missing_receipt_skips_projection(self):
        """回执缺字段 = 该动作本轮不投影(等观察覆盖;零写)。"""
        st = _state(gold=30, shop=[_card('希儿', cost=3)])
        bs = _bs_of(st)
        seq0 = bs.write_seq
        apply_shop_action_logic(bs, BuyCard(card=_card('希儿', cost=3)),
                                executed=ShopActionExecuted(),
                                produced_by='BuyCard', sig=_SIG)
        assert bs.write_seq == seq0
        assert bs.gold.value == 30
        assert len(bs.shop.value.cards) == 1

    def test_none_gold_domain_skip(self):
        """None 域跳写:gold 未读(容器 None)时 gold 跳写,其余域照写。"""
        st = _state(gold=30, shop=[_card('希儿', cost=3)])
        bs = _bs_of(st)
        bs.write_logic(bs.gold, None, produced_by='test',
                       sig=ChannelSig(family='logic_hook',
                                      actor='synthesize_from_game_state'))
        apply_shop_action_logic(bs, BuyCard(card=_card('希儿', cost=3)),
                                executed=ShopActionExecuted(bought_count=1),
                                produced_by='BuyCard', sig=_SIG)
        assert bs.gold.value is None
        assert len(bs.shop.value.cards) == 0
        assert bench_occupied(bench_slots_to_legacy(bs.bench.value)) == 1

    def test_out_of_set_action_no_write(self):
        """集外动作型零写(登记面申报;等观察覆盖,禁扩静默)。"""
        from sr_od.application.currency_war.kernel.cw_state import (
            DeployMove,
        )
        st = _state(gold=30, shop=[], bench=[_bc('希儿', slot=1)])
        bs = _bs_of(st)
        seq0 = bs.write_seq
        apply_shop_action_logic(bs, DeployMove(bench_idx=0, to_row='front',
                                               faction='?'),
                                executed=ShopActionExecuted(),
                                produced_by='DeployMove', sig=_SIG)
        assert bs.write_seq == seq0

    def test_stale_sell_proposal_no_write(self):
        """陈旧卖出提案(空槽/越界):守卫辖面,本口零写。"""
        st = _state(gold=30, shop=[])
        bs = _bs_of(st)
        seq0 = bs.write_seq
        apply_shop_action_logic(bs, SellBench(bench_idx=0, income=3),
                                executed=ShopActionExecuted(),
                                produced_by='SellBench', sig=_SIG)
        assert bs.write_seq == seq0

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

    def test_legacy_conversion_roundtrip_view(self):
        """消费视图边界:容器牌 → 旧牌列表(shop_cards_to_legacy)五记录
        字段透传,x/merge_preview 不随行(禁旧牌面兜底的成本源折叠)。"""
        st = _state(gold=30, shop=[_card('希儿', cost=3)])
        bs = _bs_of(st)
        legacy = shop_cards_to_legacy(list(bs.shop.value.cards))
        assert len(legacy) == 1
        assert legacy[0].name == '希儿'
        assert legacy[0].x == 0   # 坐标不入存储(§2.5-5)
