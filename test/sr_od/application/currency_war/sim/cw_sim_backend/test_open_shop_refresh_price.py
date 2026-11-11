"""sim 开店呈现 · 刷价改价写回测试面(cw_sim_backend._open_shop)。

设计依据 = invest-effects-calc 迭代
设计稿(原件已退役;§ 号 = 原稿节序)§2.2/§4 锁 9(2026-10-16 用户裁定:
「够次数之后,要将刷新费用变成 1,就是 sim 里观察的刷新费用也需要是 1」):
开店呈现以 kernel 渲染状态副本里的值(:func:`cw_economy.world_shop_refresh_cost`)
经**观察通道**写 ``gs.shop_refresh_cost``——对偶实机每次进店 live 漏斗
重读刷价;不走 write_logic(观察域字段只收观察写端,防 W875 式逻辑侧
预写回潮)。测试面:未达阈开店基价 / 达阈开店翻新价 / 离屏不开店不写
(呈现节奏 = 开店,非持续写)/ 写端观察通道 + 渲染值等值。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_close_shop_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    REFRESH_COST_BASE,
    world_shop_refresh_cost,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCloseShopParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_PREP,
    SCREEN_SHOP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_base import ChannelSig
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='T21ShopPriceTest',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='T21ShopPriceTest')

_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _backend(seed: int = 7) -> SimBackend:
    """构造 + 装配(调用方负责 uninstall;先例 = test_sim_backend)。"""
    backend = SimBackend(seed=seed, cfg=_CFG)
    install_backend(backend)
    return backend


def _drive_to_first_prep(b: SimBackend) -> None:
    """驱动到 P1r1 备战(简报下一步 → wait_one_one 惰性完成进节点窗)。"""
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP


def _open_shop(b: SimBackend) -> None:
    """开店点击(备战按钮-商店;点击源直驱)。"""
    b._handle_click_source(SCREEN_PREP, '按钮-商店')


def _close_shop_feed(b: SimBackend) -> None:
    """关店动作上报 + 声明喂入(动作 op「上报后一行喂入」同形)。"""
    out = report_action_close_shop_param(b.gs, CwActionCloseShopParam(),
                                         _SIG)
    assert out.applied, f'关店上报未落账: {out.reason!r}'
    cw_sim_ports.declare_world(out.world_decl)


def test_open_shop_presents_world_refresh_price_at_threshold() -> None:
    """开店呈现刷价(T-21 锁 9):长线利好付费 29 次开店 → observe 基价
    (未达阈);第 30 次付费后**不开店不写**(离屏呈现面保持旧值);
    再开店 → observe 新价(渲染 helper 现值);写端 = 观察通道。"""
    b = _backend(seed=7)
    try:
        _drive_to_first_prep(b)
        gs = b.gs
        gs.observe(gs.active_env, '长线利好', sig=_SIG_OBS)
        for _ in range(29):
            gs.effects.record_refresh(free=False)

        _open_shop(b)
        assert b.screen_identity() == SCREEN_SHOP, '前置:开店呈现商店态'
        assert gs.shop_refresh_cost.value == REFRESH_COST_BASE, \
            '付费 29 未达阈:开店呈现基价'
        assert gs.shop_refresh_cost.source == 'observation', \
            '写端 = 观察通道(不走 write_logic)'
        assert gs.shop_refresh_cost.value == world_shop_refresh_cost(gs), \
            '呈现值 = kernel 渲染状态副本里的值'

        _close_shop_feed(b)
        gs.effects.record_refresh(free=False)   # 第 30 次付费(不开店)
        assert gs.shop_refresh_cost.value == REFRESH_COST_BASE, \
            '达阈后离屏不开店不写(呈现节奏 = 开店,非持续写)'

        _open_shop(b)
        assert gs.shop_refresh_cost.value == \
            world_shop_refresh_cost(gs), '再开店呈现渲染现值'
        assert gs.shop_refresh_cost.value == 1, '达阈开店翻注册表新价'
    finally:
        uninstall_backend()
