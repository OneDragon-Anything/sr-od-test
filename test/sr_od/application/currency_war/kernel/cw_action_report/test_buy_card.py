"""buy_card 上报测试(镜像 src = kernel/cw_action_report/buy_card.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-26-liangzi-tongpin-qiyue.md(定稿)§2.4 条 1 + §4.6:买牌上报内采集
升星事实(引擎 A),在升星分支整表写毕后收尾发火——**发火时序锁**:bench
终态 = 合并产物 + 发放角色并存(若发火先于升星分支整表写,发放写会被
覆盖,终态缺发放角色 = 本锁红)。

追加面 = T-42 设计(designs/T-42-teyao-zhuanjia-yinlang.md)§4 锁 3
(购买渠道,条件形态专家触发):购买回调分支段判据一次——买银狼LV.999
解锁 / 买其他 3 费角色不触发 / 拒买( applied=False 早退)不触发。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

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

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
    report_action_close_shop_param,
    report_action_level_up_param,
    report_action_refresh_shop_param,
    report_action_sell_bench_param,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopActionExecuted,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionLevelUpParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
)

_POOL = ('符玄', '希儿')

_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                  mode='compute')


@pytest.fixture
def seeded_provider() -> Iterator[None]:
    """注确定 rng 提供槽(固定种子,期望名可现算钉名),必达复位。"""
    set_action_rng_provider(lambda tool: random.Random(20261016))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def _bench_units(gs) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_buy_merge_fires_grant_after_starup_branch(seeded_provider) -> None:
    """买牌发火时序锁(T-26 设计 §4.6 主分支):2×1★花火在席,买第 3 张
    1★花火 → 合并 2★ 产物;升星分支整表写毕后发火 → bench 终态 = 产物 +
    发放角色并存(发放名 = 注入槽种子现算;gold 未读买分支跳写,场景
    最小化)。"""
    expected = random.Random(20261016).choice(list(_POOL))
    gs = cw4_gs(node_fill=False, shop_screen='off', gold_unread=True,
                bench=[_bc('花火'), _bc('花火')],
                active_env='量子同频契约')
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('花火', cost=2)), _SIG)
    assert out.applied and out.bought_count == 1, '买牌上报成功'
    assert _bench_units(gs) == [('花火', 2), (expected, 1)], \
        f'合并产物 + 发放角色并存(升星分支不覆盖发放写): {_bench_units(gs)}'


# ============================================================ 条件形态专家触发(T-42 §4 锁 3)

_ENV_YINLANG = '特邀专家:银狼'


def test_buy_lv999_unlocks_expert_with_trigger_evidence() -> None:
    """购买渠道主分支(设计 §4 锁 3 条 1):本卡局买银狼LV.999 → 解锁
    银狼入商店;write 行 evidence = buy_card:expert_trigger#expert_unlock
    (购买/桥渠道效果串面以 write 行为准,evidence 可见,设计 §2.5)。"""
    gs = cw4_gs(bench=[], shop=[_card('银狼LV.999', cost=3, x=0)],
                gold_unread=True, active_env=_ENV_YINLANG)
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('银狼LV.999', cost=3, x=0)),
        _SIG)
    assert out.applied, '购买成功'
    assert gs.unlocked_experts.value == ('银狼',), '解锁写入'
    assert gs.unlocked_experts.evidence == \
        'buy_card:expert_trigger#expert_unlock', '触发分支 evidence 可见'


def test_buy_other_3cost_no_trigger() -> None:
    """非目标名不触发(设计 §4 锁 3 条 2):本卡局买其他 3 费角色
    (希儿)→ 判据条件①名不命中,零解锁写。"""
    gs = cw4_gs(bench=[], shop=[_card('希儿', cost=3, x=0)],
                gold_unread=True, active_env=_ENV_YINLANG)
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3, x=0)), _SIG)
    assert out.applied, '购买成功'
    assert gs.unlocked_experts.value in (None, ()), '零解锁写'


def test_buy_rejected_bench_full_no_trigger() -> None:
    """拒买不触发(设计 §4 锁 3 条 3):满栏且合成不可达 = applied=False
    早退(reason='bench_full'),早退路径不经购买回调分支 → 零解锁写
    (触发点在回调分支的时序含义锁)。"""
    full_bench = [_bc(n) for n in ('希儿', '符玄', '花火', '停云', '刃',
                                   '杰帕德', '娜塔莎', '丹恒', '三月七')]
    gs = cw4_gs(bench=full_bench, shop=[_card('银狼LV.999', cost=3, x=0)],
                gold_unread=True, active_env=_ENV_YINLANG)
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('银狼LV.999', cost=3, x=0)),
        _SIG)
    assert out.applied is False and out.reason == 'bench_full', '拒买早退'
    assert gs.unlocked_experts.value in (None, ()), '零解锁写(早退不经触发分支)'


# ============================================================ 金币花费置位(T-92 §4 锁 1)

def _spent_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r['field'] == 'prev_node_spent']


def test_buy_report_marks_prev_node_spent(monkeypatch) -> None:
    """置位正锁(T-92 设计 §4 锁 1):买牌上报 applied → prev_node_spent
    True;第二笔同节点判等跳写(值仍 True + journal 零新行,write_logic
    无同值去重、省行靠调用方早退);拒买(bench_full)零置位零写。
    cw4 一次性载体不跑种子 → 起点 None,非 True 即写(种子载体 False
    起点同语义,开局种子锁 = test_game_state 现址辖)。"""
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: 't92-l1')
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    gs = cw4_gs(bench=[], shop=[_card('希儿', cost=3, x=0)],
                gold_unread=True)
    assert gs.prev_node_spent.value is None, '一次性载体不跑种子(前置)'
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3, x=0)), _SIG)
    assert out.applied, '买牌上报成功'
    assert gs.prev_node_spent.value is True, '花费事件置位 True'
    assert gs.prev_node_spent.evidence == 'gold_spent_flag'
    assert len(_spent_rows(rows)) == 1, '置位恰一行'
    # 第二笔同节点:判等跳写(值仍 True,journal 零新行)
    out2 = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('符玄', cost=2, x=1)), _SIG)
    assert out2.applied, '第二笔上报成功'
    assert gs.prev_node_spent.value is True, '值仍 True'
    assert len(_spent_rows(rows)) == 1, '判等跳写:同节点多笔只落一行'
    # 拒买(bench_full):零置位零写
    full_bench = [_bc(n) for n in ('希儿', '符玄', '花火', '停云', '刃',
                                   '杰帕德', '娜塔莎', '丹恒', '三月七')]
    gs2 = cw4_gs(bench=full_bench, shop=[_card('银狼LV.999', cost=3, x=0)],
                 gold_unread=True)
    out3 = report_action_buy_card_param(
        gs2, CwActionBuyCardParam(card=_card('银狼LV.999', cost=3, x=0)),
        _SIG)
    assert out3.applied is False and out3.reason == 'bench_full', '拒买早退'
    assert gs2.prev_node_spent.value is None, '拒买零置位(不变)'


# ============================================================ M1 投影直测(《商店黑板容器化方案》§4-M1;同 src 按被测方法归并)

# 改写依据(分诊):写入者登记面随「商店单动作循环纳入统一管理」演进——
# 生产写点 actor 现役 = CwScreenShop(cw_screen_shop,登记面已登记),
# 旧名 CwOpBuyCards 已退役;测试模拟生产写入随登记面改名。
_PROJ_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
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
        return report_action_buy_card_param(gs, action, _PROJ_SIG,
                                            executed=executed)
    if isinstance(action, CwActionLevelUpParam):
        return report_action_level_up_param(gs, action, _PROJ_SIG,
                                            executed=executed)
    if isinstance(action, CwActionRefreshShopParam):
        return report_action_refresh_shop_param(gs, action, _PROJ_SIG,
                                                executed=executed)
    if isinstance(action, CwActionSellBenchParam):
        return report_action_sell_bench_param(gs, action, _PROJ_SIG)
    if isinstance(action, CwActionCloseShopParam):
        return report_action_close_shop_param(gs, action, _PROJ_SIG)
    raise AssertionError(f'未覆盖的商店动作类型:{type(action).__name__}')


def test_buy_simple_placement():
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


def test_merge_buy_single_report_two_forms():
    """合成买唯一入口函数两形态直测(升星分支内聚 report_action_buy_card_param 后,
    原升星分支单写测试随聚合口退役;快照基点正确性 = 两形态 bench 期望
    共辖——基点误取买后容器会重复落位/漏升,shop 视图缺失会漏满栏
    合成):非满栏合成买(2 副本在席买第 3 张 → 落位即合成升 2★)与
    满栏合成买(k=2,3 副本合 1 升 2★ 在席副本槽9)。gold −单价×k 与
    payload −k 由同一唯一入口函数携带(原「分支零写」申报随两写合一消亡)。"""
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
        out = report_action_buy_card_param(gs, act, _PROJ_SIG, executed=None)
        assert out.applied and out.bought_count == k, \
            f'{title}: executed 缺 = 理想执行自算 k'
        assert _bench_slots(gs) == bench_expect, \
            f'{title}: bench 槽位期望 {bench_expect}'
        assert gs.gold.value == axes['gold'] - 3 * k, f'{title}: gold −单价×k'
        assert _content_of(gs) == [], f'{title}: payload −k 张'
        assert gs.write_seq > seq0, f'{title}: 升星分支整表直写'


def test_missing_receipt_selfcomputes_ideal_execution():
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
                                 _PROJ_SIG, executed=ShopActionExecuted())
    assert gs.gold.value == 27, '自算 k=1:gold −单价'
    assert len(shop_payload_content_cards(gs.shop.value)) == 0, \
        'payload 该张移除'
    assert sum(1 for s in gs.bench.value.slots if s.kind != 'empty') == 1, \
        'bench 落位'


def test_none_gold_domain_skip():
    """None 域跳写:gold 未读(容器 None)时 gold 跳写,其余域照写。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        shop_payload_content_cards,
    )
    gs = _gs_of(gold=30, shop=[_card('希儿', cost=3)])
    gs.write_logic(gs.gold, None, produced_by='test',
                   sig=ChannelSig(family='logic_hook',
                                  actor='cw4_seed'))
    report_action_buy_card_param(gs, CwActionBuyCardParam(card=_card('希儿', cost=3)),
                                 _PROJ_SIG,
                                 executed=ShopActionExecuted(bought_count=1))
    assert gs.gold.value is None
    # 改写依据:三态定长五槽(用户三态裁定 2026-09-13),买后 content
    # 紧缩计数 = 旧紧缩列表长度等价读法。
    assert len(shop_payload_content_cards(gs.shop.value)) == 0
    assert sum(1 for s in gs.bench.value.slots if s.kind != 'empty') == 1


def test_buy_rejected_when_full_and_no_merge():
    """满栏且合成不可达 = 游戏拒买(ADR-0283):零写(own=0 满栏域
    ADR-0619 门)。"""
    bench = [_bc(f'c{i}', star=1) for i in range(9)]
    gs = _gs_of(gold=30, shop=[_card('姬子', cost=3)], bench=bench)
    seq0 = gs.write_seq
    report_action_buy_card_param(gs, CwActionBuyCardParam(card=_card('姬子', cost=3)),
                                 _PROJ_SIG,
                                 executed=ShopActionExecuted(bought_count=1))
    assert gs.write_seq == seq0
    assert gs.gold.value == 30, 'gold: 拒买零写金不动(期望 30)'


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
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3)), _PROJ_SIG,
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
        gs, CwActionBuyCardParam(card=_card('姬子', cost=3)), _PROJ_SIG,
        executed=ShopActionExecuted(bought_count=1))

    assert not out.applied, '前置:满栏且合成不可达 = 拒买'
    assert seen == [], '拒买不触回调'
