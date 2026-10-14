"""sim 商店牌面节点级记录 + 再进店写回锁(观察层商店缺口修复)。

病理(3.8 冒烟批阻断诊断):sim 内 gs.shop 唯一写点 = 节点窗起发牌
(deal_shop);关店动作上报 leave_screen 正确清空;同节点再开店无写径
(report_screen_shop_obs 占位 no-op,live 读屏漏斗 sim 分支不可达)
——3.6 会话模型合法产生同节点两次进店(金位读数开店〔不置标记〕→
备战正式开店),第二次进店 gs.shop 空,decide_shop_action 按 fail-loud
契约崩(容器商店 payload 离屏)。

修复语义(2026-10-17 用户裁定):牌面 = 节点级持久事实(发牌时定),
开店呈现时写回 gs.shop(对偶实机「每次进店读屏」);关店清呈现不清
记录;节点切换新发牌覆盖记录。锁三件事:

1. 同节点二次进店可观察:开店 → 关店 → 再开店 → gs.shop 牌面在且
   同值(首访在屏态保持现值零写);
2. 节点切换发牌更新:推进后新发牌覆盖记录,再开店写回 = 当前节点
   牌面(非旧节点残值);
3. 记录跟随语义边界:关店离屏期间记录存活(关店清的是呈现不是记录)。

驱动方式 = SimBackend 真类实例 + 点击源直驱 + 动作上报同形喂入
(先例 = test_cw_sim_backend)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_start_battle_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.close_shop import (
    report_action_close_shop_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    report_node_advance,
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
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='SimShopReopenTest',
                  mode='compute')

_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _backend(seed: int = 7) -> SimBackend:
    """构造 + 装配(含 kernel 事件钩子订阅;调用方负责 uninstall)。"""
    backend = SimBackend(seed=seed, cfg=_CFG)
    install_backend(backend)
    return backend


def _drive_to_first_prep(b: SimBackend) -> None:
    """驱动到 P1r1 备战(简报下一步 → wait_one_one 惰性完成进节点窗)。"""
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP


def _close_shop_feed(b: SimBackend) -> None:
    """关店动作上报 + 声明喂入(动作 op「上报后一行喂入」同形)。"""
    out = report_action_close_shop_param(b.gs, CwActionCloseShopParam(),
                                         _SIG)
    assert out.applied, f'关店上报未落账: {out.reason!r}'
    cw_sim_ports.declare_world(out.world_decl)


def _open_shop(b: SimBackend) -> None:
    """开店点击(备战按钮-商店;点击源直驱,先例同 test_cw_sim_backend)。"""
    b._handle_click_source(SCREEN_PREP, '按钮-商店')


# ============================================================ 锁1 二次进店


def test_same_node_second_visit_restores_payload() -> None:
    """同节点二次进店可观察:开店 → 关店 → 再开店 → gs.shop 牌面在且
    同值(3.6 会话模型合法形态,修复主径)。

    首访 = 节点窗起发牌后在屏态,开店保持现值零写;关店清呈现;再
    开店以节点级记录补写——实机对偶 = live 漏斗每次进店重读屏。"""
    b = _backend(seed=7)
    try:
        _drive_to_first_prep(b)
        gs = b.gs
        first = gs.shop.value
        assert first is not None, '前置:节点窗起发牌已写容器'

        _open_shop(b)
        assert b.screen_identity() == SCREEN_SHOP, '开店呈现商店态'
        assert gs.shop.value == first, '首访在屏态保持现值(零写回)'
        obs = b.observe(SCREEN_SHOP)
        assert obs.shop == list(first.cards), '首访观察产物 = 发牌牌面'

        _close_shop_feed(b)
        assert gs.shop.value is None, '关店清呈现(payload 离屏)'
        assert b.screen_identity() == SCREEN_PREP, '纯转移交回备战'

        _open_shop(b)
        assert gs.shop.value is not None, '再开店必须可观察(修复面:缺口即此处崩)'
        assert gs.shop.value == first, '牌面 = 节点级记录同值'
        obs2 = b.observe(SCREEN_SHOP)
        assert obs2.shop == list(first.cards), '再访观察产物同值(策略决策面)'
    finally:
        uninstall_backend()


# ============================================================ 锁2 节点切换覆盖


def test_node_switch_new_deal_overrides_record() -> None:
    """节点切换发牌更新:推进到下一节点 → 新发牌覆盖记录 → 再开店写回
    = 当前节点牌面(非旧节点残值);顺带锁记录与呈现的分界(关店离屏
    期间新发牌在屏,记录跟随新值)。"""
    b = _backend(seed=7)
    try:
        _drive_to_first_prep(b)
        gs = b.gs
        first = gs.shop.value
        assert first is not None, '前置:P1r1 发牌在屏'

        _close_shop_feed(b)
        assert gs.shop.value is None, '离屏后再推进(记录存活,呈现清空)'

        # 节点推进(P1r1 奖励节点:出战 → 结算确认;声明化单轨同形)
        out = report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        adv = report_node_advance(gs, trigger='settle_confirm')
        assert adv.applied, f'节点推进未落账: {adv.reason!r}'
        cw_sim_ports.declare_world(adv.world_decl)
        second = gs.shop.value
        assert second is not None, '前置:节点切换自动全刷新发牌'
        assert second != first, '前置:新旧节点发牌分形(记录覆盖可判)'
        assert b.screen_identity() == SCREEN_PREP, 'P1r2 备战呈现'

        _close_shop_feed(b)
        assert gs.shop.value is None
        _open_shop(b)
        assert gs.shop.value == second, \
            '写回 = 当前节点发牌(记录随节点窗新发牌覆盖)'
    finally:
        uninstall_backend()
