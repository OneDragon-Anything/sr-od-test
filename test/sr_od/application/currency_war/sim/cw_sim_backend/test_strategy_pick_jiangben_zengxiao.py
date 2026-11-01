"""sim 降本增效选卡落地全链 walk 测试(镜像 src = sim/cw_sim_backend.py
素出售判据细分零接线 + kernel 获得链登记腿桥;驱动助手 import 复用
test_sim_sell_all_deal/test_strategy_pick_dacaiyuan 同形文件,只 import
复用不改——先例 = test_strategy_pick_dacaiyuan.py 同构)。

测试面依据 = 迭代设计 designs/T-188-jiangben-zengxiao.md §2.2-2/§4
(锁 5 sim 全链主锁)+ 八裁决点默认案。sim 现状持卡局仅记名
active_strategies(清场/退款/免购全无)= 预登记错扣面;注册后世界真值
恢复:选卡拍清场+基础公式退款,后续前 6 张买零扣金(免费闸)、uses 递减、
用尽移除恢复扣金。素出售不入发牌判据集 → bench 零新增单位(零假发牌)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bview,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
)
from test.sr_od.application.currency_war.sim.test_sim_sell_all_deal import (
    _bench_units,
    _drive_to_strategy_offer,
    _pick_card,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    Unit,
    deployed_rows_of_view,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    uninstall_backend,
)

_OPTS = ['降本增效', '躺平', '淘金客']
_SOLD = ('三月七', 2)   # 预种 2★1 费:cost=1 无手续费,×2 两候选口径同值
_SPEC_ID = '202301'


def _seed_sold_unit(b) -> None:
    """预种一枚 2★1 费到前台 + 清空备战席(sim 开局世界自带备战席单位,
    退款公式的输入须全域受控,恰 3 锚才成立)。"""
    b.gs.observe(b.gs.deployed,
                 _dvs([Unit(char_id=_SOLD[0], star=_SOLD[1])], []),
                 sig=_SIG_OBS)
    b.gs.observe(b.gs.bench, cw4_bview([]), sig=_SIG_OBS)


def _board_refund(gs) -> int:
    """现板面全额退款预演算(单一源公式与桥同源;开局单位在席)。"""
    front, back = deployed_rows_of_view(gs.deployed.value)
    bench = [s.unit for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit is not None]
    return sum(sell_refund(int(u.star), bench_char_cost(u, gs))
               for u in front + back + bench)


def test_pick_jiangben_zengxiao_full_chain_sell_and_free_buys() -> None:
    """锁 5(sim 全链主锁):decl 分派选降本增效 → 出售面(场清空 + 基础
    公式退款恰 3 = 预种 2★1 费确定性锚)+ 后续前 6 张买零扣金(uses 逐张
    递减、第 6 张买毕条目离场)+ 第 7 张恢复扣金;bench 零新增单位(素
    出售无发牌面)。"""
    b = _drive()
    try:
        gs = b.gs
        _seed_sold_unit(b)
        expected_refund = _board_refund(gs)
        assert expected_refund == 3, '预种 2★1 费 = 退款恰 3(确定性锚)'
        gs.write_logic(gs.invest_strategy_opts, _OPTS,
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        gold_before = int(gs.gold.value or 0)
        _pick_card(b, '降本增效')
        _f, _bk = deployed_rows_of_view(gs.deployed.value)
        assert (_f, _bk) == ([], []), '场清空(出售面,双端同链)'
        assert int(gs.gold.value or 0) - gold_before == 3, \
            '退款恰 3(基础公式;×2 修饰缺口低估申报,观察覆盖)'
        assert _bench_units(gs) == [], 'bench 清空且零新增(素出售无发牌面)'
        assert gs.effects.first(_SPEC_ID).remaining_uses == 6, \
            '免费购买腿播种(remaining_uses=6)'
        # 前 6 张买零扣金(免费闸;uses 逐张递减,第 6 张买毕离场)。
        for i in range(6):
            out = report_action_buy_card_param(
                gs, CwActionBuyCardParam(card=_card('希儿', cost=3, x=0)),
                _SIG)
            assert out.applied, f'第 {i + 1} 张买牌上报成功'
            assert int(gs.gold.value or 0) == gold_before + 3, \
                f'第 {i + 1} 张免费帧零扣金'
        assert gs.effects.first(_SPEC_ID) is None, 'uses 耗尽条目离场'
        # 第 7 张恢复扣金(uses 耗尽 = 免费窗口关闭)。
        out = report_action_buy_card_param(
            gs, CwActionBuyCardParam(card=_card('希儿', cost=3, x=0)), _SIG)
        assert out.applied
        assert int(gs.gold.value or 0) == gold_before + 3 - 3, \
            'uses 耗尽恢复扣金(全价)'
    finally:
        uninstall_backend()


def _drive():
    """装配 + 驱动到策略选卡屏(助手复用保持单一驱动序)。"""
    from test.sr_od.application.currency_war.sim.test_sim_sell_all_deal import (
        _backend,
    )
    b = _backend(7)
    _drive_to_strategy_offer(b)
    return b
