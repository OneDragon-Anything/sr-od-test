"""策略卡购买翻星检查/置一次性标志位与买牌上报链翻转局测试(镜像 src =
kernel/cw_gain_chain.py 的 check_strategy_buy_star_flip /
mark_strategy_buy_star_flip_consumed + kernel/cw_action_report/buy_card.py
两处接入调用 + kernel/cw_pool.py 池账跟随)。

测试面依据 = 迭代设计 designs/T-187-sifei-jinsheng.md(定稿)§2.2/§2.4/
§2.5/§4 锁 2/3/4/5 + REVIEW-T187 §四.4(卡面官方原文:「你购买的下1个
4费角色将立刻升到2星。获得12金币。」;直构形态先例 = 同目录
test_check_strategy_first_buy_xp_grants.py):
- 谓词分支矩阵(锁 2):未持卡/表外卡 False;持卡 cost=4 star=1 True;
  已置一次性标志位 False;star>=2 False;cost≠4 False;一次性标志位容器缺省 None 防御分支;
- 置一次性标志位消耗轴(裁决点 4 消耗语义):已 2★ 购买照常消耗(消耗 = 未落一次性标志位 ∧
  费用匹配,无星级轴);费用不匹配/已置一次性标志位二次短路零写;
- 买牌上报链翻转局 walk(锁 3):落位 Unit.star==2 + 一次性标志位置位 + payload
  移除按购买原星匹配(在售 2★ 件幸存)+ 金扣原价 + on_buy 收购买原星;
  未持卡对照局落 1★;升星腿两分支分开断言(首买零同名零重写/同名低星
  在场幂等整表重写一次);
- 一次性消耗(锁 4):第二只 4 费不再翻;
- 池账跟随(锁 5):翻转购买 held 计质量 3/常规对照 held 1/守恒破直构
  (2×2★+1×1★ + 翻转购买 → 级联 3★)ValueError 响停。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_buy_star_flip,
    mark_strategy_buy_star_flip_consumed,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    Field,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_pool import (
    held_copies,
    remaining_pool,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
)

_SIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_BUY_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                      mode='compute')

_CARD = '四费晋升'

_FOUR_COST = '符玄'          # 注册表 4 费非专家(设计 §1.5 名单现值)

_FOUR_COST_ALT = '杰帕德'    # 另一只 4 费(一次性消耗锁)


def _gs(*, card: str | None = _CARD, done=()) -> GameState:
    """谓词/置一次性标志位直构容器(card=None = 未持卡;'躺平' = 表外卡)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card', sig=_SIG)
    if done:
        gs.write_logic(gs.strategy_conditional_done, tuple(done),
                       produced_by='test-seed', evidence='t:done', sig=_SIG)
    return gs


def _bench_units(gs) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


# ============================================================ 谓词矩阵(锁 2)

def test_predicate_matrix() -> None:
    """谓词分支矩阵(锁 2):持卡未消费 cost=4 star=1 True;未持卡/表外
    卡 False(零写);已置一次性标志位 False;star>=2 False(翻转 no-op,消耗归置一次性标志位
    轴);cost≠4 False。"""
    assert check_strategy_buy_star_flip(_gs(), name=_FOUR_COST, star=1,
                                        cost=4, sig=_SIG) is True, \
        '持卡未消费 4 费 1★ = armed'
    for card in (None, '躺平'):
        gs = _gs(card=card)
        seq0 = gs.write_seq
        assert check_strategy_buy_star_flip(
            gs, name=_FOUR_COST, star=1, cost=4, sig=_SIG) is False, \
            f'{card}: 零命中保守 False'
        assert gs.write_seq == seq0, f'{card}: 纯谓词零写'
    assert check_strategy_buy_star_flip(
        _gs(done=(_CARD,)), name=_FOUR_COST, star=1, cost=4,
        sig=_SIG) is False, '已消费一次性标志位短路'
    assert check_strategy_buy_star_flip(
        _gs(), name=_FOUR_COST, star=2, cost=4, sig=_SIG) is False, \
        '已达标星级购买翻转 no-op'
    assert check_strategy_buy_star_flip(
        _gs(), name='希儿', star=1, cost=3, sig=_SIG) is False, \
        '费用档不匹配(3 费)'


def test_predicate_none_latch_container_defense(monkeypatch) -> None:
    """一次性标志位容器缺省 None 防御分支(锁 2):Field 缺省 None 是合法设计语义,
    读取端带 or () 防御——None 容器不炸、按未落一次性标志位处理。"""
    gs = _gs()
    monkeypatch.setattr(gs, 'strategy_conditional_done', Field())
    assert check_strategy_buy_star_flip(gs, name=_FOUR_COST, star=1,
                                        cost=4, sig=_SIG) is True, \
        'None 容器防御读取,不炸不误置一次性标志位'


# ============================================================ 置一次性标志位消耗轴(锁 2 + 裁决点 4)

def test_mark_consumes_without_star_axis() -> None:
    """置一次性标志位消耗轴(裁决点 4 消耗语义锁):「下1个」的消耗与购买星级无关
    (已 2★ 4 费购买翻转 no-op 照常消耗)——消耗 = 未落一次性标志位 ∧ 费用匹配,
    签名不收 star 即无星级轴的结构承载(调用面无法按星过滤);evidence
    = 卡名串;source = logic。"""
    gs = _gs()
    latched = mark_strategy_buy_star_flip_consumed(gs, cost=4, sig=_SIG)
    assert latched == (_CARD,), '已达标星级购买照常消耗'
    assert gs.strategy_conditional_done.value == (_CARD,), '未落一次性标志位'
    assert gs.strategy_conditional_done.source == 'logic', '一次性标志位 = 簿记逻辑态'
    assert gs.strategy_conditional_done.evidence == \
        'strategy_buy_star_flip:四费晋升', 'evidence 卡名串'


def test_mark_cost_mismatch_and_short_circuit() -> None:
    """置一次性标志位守卫(锁 2/锁 4 前置):费用不匹配零置一次性标志位零写;已置一次性标志位二次短路
    零写(at-most-once 消耗)。"""
    gs = _gs()
    seq0 = gs.write_seq
    assert mark_strategy_buy_star_flip_consumed(
        gs, cost=3, sig=_SIG) == (), '费用不匹配零置一次性标志位'
    assert gs.write_seq == seq0, '零写'
    assert gs.strategy_conditional_done.value in (None, ())
    assert mark_strategy_buy_star_flip_consumed(
        gs, cost=4, sig=_SIG) == (_CARD,)
    seq1 = gs.write_seq
    assert mark_strategy_buy_star_flip_consumed(
        gs, cost=4, sig=_SIG) == (), '已置一次性标志位二次短路'
    assert gs.write_seq == seq1, '二次零写'
    assert gs.strategy_conditional_done.value == (_CARD,), '一次性标志位不重复'


# ============================================================ 买牌上报链 walk(锁 3)

def test_buy_path_flip_latch_payload_gold_onbuy_original_star() -> None:
    """翻转局 walk 主条(锁 3):持卡买 4 费 1★ → 落位 Unit.star==2 +
    一次性标志位置位 + payload 移除 1 张按购买原星匹配(在售 2★ 件幸存)+ 金扣
    原价 + on_buy 回调收购买原星(翻转零 bleed 进交易对象与效果账本);
    首买零同名 → 升星腿零重写(分支 a)。"""
    on_buy_calls: list[tuple[object, int, int]] = []
    gs = cw4_gs(node_fill=False, gold=30,
                shop=[_card(_FOUR_COST, cost=4, x=0),
                      _card(_FOUR_COST, cost=4, star=2, x=1)],
                active_strategies=(_CARD,))
    gs.effects.on_buy = (lambda card, star, k=1:
                         on_buy_calls.append((card, star, k)))
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card(_FOUR_COST, cost=4, star=1,
                                            x=0)), _BUY_SIG)
    assert out.applied and out.bought_count == 1, '买牌上报成功'
    assert _bench_units(gs) == [(_FOUR_COST, 2)], \
        f'落位即翻星(2★ 身份进席): {_bench_units(gs)}'
    assert gs.strategy_conditional_done.value == (_CARD,), '一次性标志位置位'
    slots = list(gs.shop.value.cards)
    assert slots[0].kind == 'empty', '在售 1★ 件被移除'
    assert slots[1].kind == 'content' and int(slots[1].card.star) == 2, \
        '在售 2★ 件幸存(payload 匹配持购买原星,翻转零 bleed)'
    assert gs.gold.value == 26, '金扣原价 4(翻转不改付费额)'
    assert len(on_buy_calls) == 1, 'on_buy 恰一次'
    assert on_buy_calls[0][1] == 1, 'on_buy 收购买原星(非翻转后 2)'
    assert gs.bench.evidence == 'proj_buy_place', \
        '首买零同名 → 升星腿零重写(分支 a)'


def test_buy_path_no_card_lands_original_star() -> None:
    """未持卡对照局(锁 3):同链买 4 费 → 落购买原星 1★ + 零一次性标志位。"""
    gs = cw4_gs(node_fill=False, gold=30,
                shop=[_card(_FOUR_COST, cost=4, x=0)], active_strategies=())
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card(_FOUR_COST, cost=4, x=0)),
        _BUY_SIG)
    assert out.applied, '买牌上报成功'
    assert _bench_units(gs) == [(_FOUR_COST, 1)], '未持卡落购买原星'
    assert gs.strategy_conditional_done.value in (None, ()), '零一次性标志位'


def test_buy_path_same_name_low_star_upgrade_branch_fires_once() -> None:
    """升星腿分支 b(锁 3):同名 1★ 已在席,买同名牌翻 2★ → 同名最高星
    抬升 = 升星腿判据真值,幂等整表重写一次(bench 终行 evidence =
    proj_merge_upgrade;写笔账恰 +1 重写,防误加守卫也防重复发火)。"""
    gs = cw4_gs(node_fill=False, gold=30, bench=[_bc(_FOUR_COST)],
                shop=[_card(_FOUR_COST, cost=4, x=0)],
                active_strategies=(_CARD,))
    seq0 = gs.write_seq
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card(_FOUR_COST, cost=4, x=0)),
        _BUY_SIG)
    assert out.applied, '买牌上报成功'
    assert sorted(_bench_units(gs)) == [(_FOUR_COST, 1), (_FOUR_COST, 2)], \
        f'旧 1★ + 翻转 2★ 并存(2×1★ 不合成): {_bench_units(gs)}'
    assert gs.bench.evidence == 'proj_merge_upgrade', \
        '升星腿幂等整表重写(分支 b)'
    assert gs.write_seq == seq0 + 6, \
        '写笔账 = gold+payload+落位+升星重写+一次性标志位+花费置位(重写恰一次)'


# ============================================================ 一次性消耗(锁 4)

def test_single_consumption_second_four_cost_no_flip() -> None:
    """一次性消耗(锁 4):持卡买 4 费翻星一次性标志位置位 → 再买第二只 4 费落
    1★、一次性标志位不再触发(值不重复)。"""
    gs = cw4_gs(node_fill=False, gold=30,
                shop=[_card(_FOUR_COST, cost=4, x=0),
                      _card(_FOUR_COST_ALT, cost=4, x=1)],
                active_strategies=(_CARD,))
    out1 = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card(_FOUR_COST, cost=4, x=0)),
        _BUY_SIG)
    assert out1.applied, '首买成功'
    assert gs.strategy_conditional_done.value == (_CARD,), '首买一次性标志位置位'
    out2 = report_action_buy_card_param(
        gs, CwActionBuyCardParam(
            card=_card(_FOUR_COST_ALT, cost=4, x=1)), _BUY_SIG)
    assert out2.applied, '第二买成功'
    assert sorted(_bench_units(gs)) == [(_FOUR_COST_ALT, 1),
                                        (_FOUR_COST, 2)], \
        f'第二只 4 费落 1★(不再翻): {_bench_units(gs)}'
    assert gs.strategy_conditional_done.value == (_CARD,), '一次性标志位不重复'


# ============================================================ 池账跟随(锁 5)

def test_pool_follows_flip_quality() -> None:
    """池账跟随(锁 5 主条):翻转购买后 held 计质量 3(2★ = 3^(2−1)),
    剩余池对应 −3(固定 9);常规购买对照局 held 1/剩余 8(不变量派生
    自动跟随,机制零代码)。"""
    gs = cw4_gs(node_fill=False, shop_screen='off', gold_unread=True,
                bench=[], active_strategies=(_CARD,))
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card(_FOUR_COST, cost=4, x=0)),
        _BUY_SIG)
    assert out.applied, '翻转购买成功'
    assert held_copies(gs).get(_FOUR_COST) == 3, '翻转件计质量 3'
    assert remaining_pool(gs)[_FOUR_COST] == 6, '剩余 = 固定 9 − 3'

    gs_plain = cw4_gs(node_fill=False, shop_screen='off', gold_unread=True,
                      bench=[], active_strategies=())
    out2 = report_action_buy_card_param(
        gs_plain, CwActionBuyCardParam(
            card=_card(_FOUR_COST, cost=4, x=0)), _BUY_SIG)
    assert out2.applied, '常规购买成功'
    assert held_copies(gs_plain).get(_FOUR_COST) == 1, '常规购买计 1'
    assert remaining_pool(gs_plain)[_FOUR_COST] == 8, '剩余 = 固定 9 − 1'


def test_pool_conservation_break_raises_on_flip_buy() -> None:
    """守恒破路径(锁 5):直构同名 2×2★+1×1★ 席(7 物理副本,合法购得
    形态)+ 持卡未消费 + 再购同名翻转 → 级联 3×2★→3★,held = 9+1 = 10
    > 固定池 9 → 剩余 −1 → ValueError 响停(文案对齐 cw_pool 既有
    「牌池守恒破」语义;极端态守恒破与翻星/级联读法无关)。"""
    gs = cw4_gs(node_fill=False, shop_screen='off', gold_unread=True,
                bench=[_bc(_FOUR_COST, 2), _bc(_FOUR_COST, 2),
                       _bc(_FOUR_COST, 1)],
                active_strategies=(_CARD,))
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card(_FOUR_COST, cost=4, x=0)),
        _BUY_SIG)
    assert out.applied, '翻转购买成功(上报链零池闸)'
    assert sorted(_bench_units(gs)) == [(_FOUR_COST, 1), (_FOUR_COST, 3)], \
        f'级联 3×2★→3★ + 余 1★: {_bench_units(gs)}'
    with pytest.raises(ValueError, match='牌池守恒破'):
        remaining_pool(gs)
