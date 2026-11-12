"""商店入口漏斗 bench 写门场景测试(投影测试族跨方法场景残留件)。

落位 = cw_action_report/test_shop_projection_logic/ 拆目录收留(先例 =
sim/cw_sim_backend/ 拆目录):本件无单一 src 基准——主断言对象 = 种子
未读域跳写纪律(bench_unread,测试种子载体契约),防御场景 = 商店
画面 op 入口链 bench 域的「未读域≠真空域」。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)


def test_shop_entry_funnel_bench_survives_synthesis() -> None:
    """商店入口漏斗 bench 写门场景测试(商店画面 op 入口链回归):
    种子对未声明 bench 域整域跳写(bench_unread)——状态容器 bench 保持
    漏斗真读值,与执行账 tracked 同源不破。回归形态 = 种子把状态容器 bench
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
        '种子后状态容器 bench 仍为漏斗真读值(未读域跳写,兜底空表不覆盖)'
    # (3.2 单账化:原「执行账 tracked 不受种子影响」断言随第二账退役删,
    #  状态容器即唯一账,上式即全量测试面。)
