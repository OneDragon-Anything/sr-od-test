"""买牌上报免费购买闸测试(镜像 src = kernel/cw_action_report/buy_card.py
免费闸段 + mark_gold_spent 免费帧门控;直构形态照同目录 test_buy_card.py
现值先例,金账经 journal sink 对行)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§2.2-2/§3
(T-92 免费帧豁免义务)/§4(锁 3/锁 4/锁 6 负写端)+ 八裁决点默认案:

- 锁 3(免费闸单点·主锁):持条目(uses=6)买 1 张 cost=3 → 金零变动 +
  uses=5;uses=2 买 k=3 → 前两张免 + 1 张照付(gold −3)+ uses 归零条目
  离场;全免帧零金写(journal 零 proj_buy_gold 行);
- 花销账免费帧豁免(T-92 动作到达型置位的显式豁免):全免帧不置
  prev_node_spent(免费购买零金变动不属花费事件,存款回报条件输入保真),
  部分免费帧(有实付)照常置位;
- 锁 4(拒买零递减):bench_full 早退序位在闸前 → uses 不变零虚耗;
- 锁 6(负写端):未持卡局买牌照常扣金 + 置位(零扰动回归)。
"""
from __future__ import annotations

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
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopActionExecuted,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                  mode='compute')

_SPEC_ID = '202301'


def _gold_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r['field'] == 'gold']


def _attach_journal(monkeypatch, tag: str) -> list[dict]:
    """journal sink 挂接(必须在校准种子写入之后挂——种子观察行会进
    流水,本锁只数动作窗行;返回行缓冲)。"""
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: tag)
    return rows


def _register_card_uses(gs, uses: int) -> None:
    """持卡态直种:登记降本增效条目并把余量钉到指定值(免 6 连买构造)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EFFECTS,
    )
    gs.effects.register_strategy(STRATEGY_EFFECTS['降本增效'],
                                 acquired_key=(1, 2))
    gs.effects.first(_SPEC_ID).remaining_uses = uses


def test_buy_free_gate_single_card_zero_gold_write(monkeypatch) -> None:
    """锁 3 主分支 A(单张全免帧):持条目 uses=6 买 1 张 cost=3 → gold
    零变动 + journal 零 proj_buy_gold 行 + uses=5(上报时递减)。"""
    gs = cw4_gs(bench=[], shop=[_card('希儿', cost=3, x=0)], gold=30)
    _register_card_uses(gs, 6)
    rows = _attach_journal(monkeypatch, 't188-gate')
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3, x=0)), _SIG)
    assert out.applied and out.bought_count == 1, '买牌上报成功'
    assert gs.gold.value == 30, '免费帧金零变动'
    assert _gold_rows(rows) == [], '全免帧零金写(扣 0 不落行)'
    assert gs.effects.first(_SPEC_ID).remaining_uses == 5, 'uses 6→5'


def test_buy_free_gate_partial_k3_two_free_one_paid(monkeypatch) -> None:
    """锁 3 主分支 B(部分免费,按张计):uses=2 买 k=3 → 前两张免 +
    1 张照付(gold −3)+ uses 归零条目离场(first 返 None)。"""
    gs = cw4_gs(bench=[], shop=[_card('符玄', cost=3, x=0),
                                _card('符玄', cost=3, x=1),
                                _card('符玄', cost=3, x=2)], gold=30)
    _register_card_uses(gs, 2)
    rows = _attach_journal(monkeypatch, 't188-partial')
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('符玄', cost=3, x=0)),
        _SIG, executed=ShopActionExecuted(bought_count=3))
    assert out.applied and out.bought_count == 3, '一击多买 k=3'
    assert gs.gold.value == 27, '净扣 = 单价×(k−免) = 3×(3−2)'
    assert len(_gold_rows(rows)) == 1, '部分免费帧恰一行净扣'
    assert gs.effects.first(_SPEC_ID) is None, 'uses 归零条目离场'


def test_buy_free_gate_all_free_k3_zero_gold_write(monkeypatch) -> None:
    """锁 3 主分支 C(k=3 全免帧):uses=6 买 k=3 → gold 零变动 +
    journal 零金行(全免帧零金写,免 no-op 行)。"""
    gs = cw4_gs(bench=[], shop=[_card('停云', cost=2, x=0),
                                _card('停云', cost=2, x=1),
                                _card('停云', cost=2, x=2)], gold=30)
    _register_card_uses(gs, 6)
    rows = _attach_journal(monkeypatch, 't188-allfree')
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('停云', cost=2, x=0)),
        _SIG, executed=ShopActionExecuted(bought_count=3))
    assert out.applied and out.bought_count == 3
    assert gs.gold.value == 30, '全免帧金零变动'
    assert _gold_rows(rows) == [], '全免帧零金写'
    assert gs.effects.first(_SPEC_ID).remaining_uses == 3, 'uses 6→3'


def test_buy_free_gate_skips_spend_flag_on_free_frame(
        monkeypatch) -> None:
    """花销账免费帧豁免(T-92 置位判据=动作到达型的显式豁免):全免帧
    买牌不置 prev_node_spent(免费购买零金变动不属花费事件,同函数刷新
    通道「非免费帧」同判);部分免费帧(有实付)照常置位。"""
    gs = cw4_gs(bench=[], shop=[_card('希儿', cost=3, x=0),
                                _card('停云', cost=2, x=1)], gold=30)
    _register_card_uses(gs, 6)
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3, x=0)), _SIG)
    assert out.applied
    assert gs.prev_node_spent.value is None, \
        '全免帧不置花费事件(误置位 = 存款回报条件输入失真)'
    out2 = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('停云', cost=2, x=1)), _SIG)
    assert out2.applied
    assert gs.effects.first(_SPEC_ID).remaining_uses == 4
    # 造全价帧:连买 4 张停云(uses 余量 4 张全免,全部零金写零置位),
    # 第 6 张免毕条目离场;此后购买 = 全价帧。
    for _ in range(4):
        out_n = report_action_buy_card_param(
            gs, CwActionBuyCardParam(card=_card('停云', cost=2, x=1)), _SIG)
        assert out_n.applied
        assert gs.gold.value == 30, '免费帧金零变动(连买全程)'
    assert gs.effects.first(_SPEC_ID) is None, 'uses 耗尽条目离场'
    assert gs.prev_node_spent.value is not True, '免费帧全程零置位'
    gold_before = gs.gold.value
    _attach_journal(monkeypatch, 't188-paid')
    out_p = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('停云', cost=2, x=1)), _SIG)
    assert out_p.applied
    assert gs.gold.value == gold_before - 2, 'uses 耗尽恢复收费(全价帧)'
    assert gs.prev_node_spent.value is True, '全价帧照常置位花费事件'


def test_buy_rejected_bench_full_no_uses_consumption(monkeypatch) -> None:
    """锁 4(拒买零递减):bench_full 早退序位在免费闸之前 → applied=False
    零递减零虚耗余量,金零写零置位。"""
    full_bench = [_bc(n) for n in ('希儿', '符玄', '花火', '停云', '刃',
                                   '杰帕德', '娜塔莎', '丹恒', '三月七')]
    gs = cw4_gs(bench=full_bench, shop=[_card('银狼LV.999', cost=3, x=0)],
                gold=30)
    _register_card_uses(gs, 6)
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('银狼LV.999', cost=3, x=0)),
        _SIG)
    assert out.applied is False and out.reason == 'bench_full', '拒买早退'
    assert gs.effects.first(_SPEC_ID).remaining_uses == 6, '零递减(不虚耗)'
    assert gs.gold.value == 30, '拒买零金写'
    assert gs.prev_node_spent.value is None, '拒买零置位'


def test_buy_without_card_pays_full_price(monkeypatch) -> None:
    """锁 6(负写端·零扰动回归):未持卡局买牌照常全价扣金 + 置位花费
    事件(闸按条目在场判定,非持卡局面零变化)。"""
    gs = cw4_gs(bench=[], shop=[_card('希儿', cost=3, x=0)], gold=30)
    rows = _attach_journal(monkeypatch, 't188-neg')
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3, x=0)), _SIG)
    assert out.applied
    assert gs.gold.value == 27, '未持卡照常扣金'
    assert len(_gold_rows(rows)) == 1, '全价恰一行'
    assert gs.prev_node_spent.value is True, '置位照常'
