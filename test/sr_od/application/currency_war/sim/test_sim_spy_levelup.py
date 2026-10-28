"""商业间谍升级回调 sim 闭环测试(2026-10-17-levelup-shop-transition
T-3;landing §3.3 验收凭据)。

设计唯一源 = 迭代 design.md §2.3(回调四步:抽 5 张/偷最贵 3 张入席/
剩余 2 张 = 商店新牌面/置随机态信号)+ §2.4(信号写端唯一 = 上报回调
第 4 步)。驱动形态 = test_sim_backend 同款「上报 + 声明喂入」单轨
(动作 op 同形:report → cw_sim_ports.declare_world),世界分支确定性 =
流键重放(同 seed 同键序逐位一致,sim 确定性判据)。

测试面:
1. 持商业间谍升级:3 张真实入席(可断言具体牌 = 新抽 5 张最贵序)→
   信号置位 → 备战重开触发(step1_shop_randomized_reopen)→ 开店呈现
   剩余 2 张(非重新发牌:重放新抽载荷对拍,被偷槽位置空、剩余原位);
2. 无商业间谍对照:零商店副作用(牌面不变/信号不置/无声明);
3. 席满溢出:不入席 + 计数披露(disclosures + cw4_counters 双面)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_action_report.level_up import (
    report_action_level_up_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    ShopActionExecuted,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenShopParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_PREP,
    SCREEN_SHOP,
    SimBackend,
    effective_deal_probs,
    install_backend,
    sample_shop_deal,
    stream_rng,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_SIG = ChannelSig(family='logic_action', actor='SpyLevelupTest',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='SpyLevelupTest')
_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _content_names(payload) -> list[str]:
    """载荷 content 槽卡名多重集(槽位原位断言用)。"""
    return [s.card.name for s in payload.cards
            if s.kind == 'content' and s.card is not None]


def _top3_of(payload) -> list[str]:
    """新抽载荷的最贵 3 张名(序 = 费用降序 → 星级降序 → 槽位升序,
    单一源 = backend 世界分支同款排序)。"""
    content = [s for s in payload.cards
               if s.kind == 'content' and s.card is not None]
    ranked = sorted(content,
                    key=lambda s: (-(int(s.card.cost or 0)),
                                   -(int(s.card.star or 1)),
                                   int(s.card.slot or 0)))
    return [s.card.name for s in ranked[:3]]


def _to_prep(seed: int = 7) -> SimBackend:
    """构造 + 走到 P1r1 备战屏(窗起点发牌已落:shop 载荷 + 节点级
    记录在册);调用方负责 uninstall。"""
    b = SimBackend(seed=seed, cfg=_CFG)
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _feed_levelup(b: SimBackend, *, spy: bool):
    """升级上报 + 声明喂入(动作 op 同形):lv5 满击升 6;持卡 = 观察直种
    (测试种子纪律;生产写端 = 获得链)。返回 (outcome, 重放新抽载荷)。"""
    b.gs.observe(b.gs.active_strategies, ['商业间谍'] if spy else [],
                 evidence='test:spy', sig=_SIG_OBS)
    b.gs.observe(b.gs.level, 5, evidence='test:spy', sig=_SIG_OBS)
    b.gs.observe(b.gs.xp, (0, XP_TO_NEXT_LEVEL[5]), evidence='test:spy',
                 sig=_SIG_OBS)
    out = report_action_level_up_param(
        b.gs, SimpleNamespace(cost=4), _SIG,
        executed=ShopActionExecuted(levelup_clicks=5))
    # 新抽载荷重放(世界分支流键 M22/spy-deal|M22/spy-rotation;确定性
    # 判据 = 同 seed 同键序逐位一致)。必须在 declare_world 之前构建:
    # sample_shop_deal 读容器剩余牌库派生(drawable_names),世界分支入席
    # 会改牌库——后置重放不与真实抽牌同态,逐位一致判据失效。
    rotation_on = (str(b.gs.active_env.value or '') == '轮岗')
    replay = sample_shop_deal(
        b.gs, stream_rng(b.seed, 'M22/spy-deal/p1/r1'), level=6,
        probs=effective_deal_probs(
            6, stream_rng(b.seed, 'M22/spy-rotation/p1/r1'),
            rotation_on=rotation_on))
    cw_sim_ports.declare_world(out.world_decl)
    return out, replay


def test_spy_levelup_steal_persist_reopen_presents_two() -> None:
    """持商业间谍升级闭环(design §2.3 四步 + §2.4):3 张真实入席
    (可断言具体牌 = 新抽最贵序)→ 信号置位 → 备战重开触发 → 开店呈现
    剩余 2 张(非重新发牌:被偷槽位置空、剩余原位,与重放载荷对拍)。"""
    b = _to_prep()
    try:
        bench_before = [s.unit.char_id for s in b.gs.bench.value.slots
                        if s.kind == 'unit' and s.unit is not None]
        out, replay = _feed_levelup(b, spy=True)
        assert out.applied
        assert out.world_decl is not None \
            and out.world_decl.trigger == 'spy_shop_refresh'
        # 步④:信号置位(写端 = 上报回调,实机/sim 同源)。
        assert b.gs.shop_randomized_pending is True
        # 步②:偷最贵 3 张 → 备战席真实入席(可断言具体牌,多重集对拍)。
        stolen = _top3_of(replay)
        bench_after = [s.unit.char_id for s in b.gs.bench.value.slots
                       if s.kind == 'unit' and s.unit is not None]
        assert sorted(bench_after) == sorted(bench_before + stolen), \
            f'入席 = 新抽 5 张最贵 3 张(具体牌): {stolen}'
        rest2 = list(_content_names(replay))
        for n in stolen:
            rest2.remove(n)   # 多重集扣除(同名多张逐张扣)
        # 步③:剩余 2 张 = 商店新牌面(被偷槽位置空、剩余原位)。
        board = b.gs.shop.value
        assert sorted(_content_names(board)) == sorted(rest2), \
            '牌面 = 新抽 5 张的剩余 2 张'
        assert len([s for s in board.cards if s.kind == 'empty']) == 3, \
            '被偷 3 槽置空(原位保留,非重排)'
        # 备战重开触发(第 1 步:清标记 + 开店 + 清信号)。
        session_scope.mark_shop_handled(b.gs)
        outs = entry.emit(b.gs, None)
        assert outs and outs[0].reason == 'step1_shop_randomized_reopen', \
            f'备战重开触发: {outs}'
        assert isinstance(outs[0].action, CwActionOpenShopParam)
        assert b.gs.shop_randomized_pending is False, '重开位消费后清信号'
        assert state_of(b.gs).shop_handled is None, '重开位清 handled 标记'
        # 开店呈现剩余 2 张(非重新发牌:_shop_record 写回,不再发牌)。
        b._handle_click_source(SCREEN_PREP, '按钮-商店')
        assert b.screen_identity() == SCREEN_SHOP
        presented = b.gs.shop.value
        assert len(_content_names(presented)) == 2, '呈现 = 2 张(非整店重发)'
        assert sorted(_content_names(presented)) == sorted(rest2), \
            '开店呈现 = 回调保存牌面(非重新发牌)'
        assert len([s for s in presented.cards if s.kind == 'empty']) == 3
    finally:
        uninstall_backend()


def test_no_spy_levelup_zero_shop_side_effect() -> None:
    """无商业间谍对照(design §2.3 末条):升级零商店副作用——牌面
    不变、信号不置、无世界分支声明(重开靠备战执行帧清标记通道)。"""
    b = _to_prep()
    try:
        board_before = list(b.gs.shop.value.cards)
        bench_before = [s.unit.char_id for s in b.gs.bench.value.slots
                        if s.kind == 'unit' and s.unit is not None]
        out, _replay = _feed_levelup(b, spy=False)
        assert out.applied, '升级照常生效'
        assert out.world_decl is None, '无持卡 → 无世界分支声明'
        assert b.gs.shop_randomized_pending is False, '信号不置'
        assert _content_names(b.gs.shop.value) == [
            s.card.name for s in board_before
            if s.kind == 'content' and s.card is not None], '牌面不变'
        bench_after = [s.unit.char_id for s in b.gs.bench.value.slots
                       if s.kind == 'unit' and s.unit is not None]
        assert bench_after == bench_before, '备战席零入席'
        assert b.disclosures.get('spy_deal_count', 0) == 0, '零抽牌'
    finally:
        uninstall_backend()


def test_spy_steal_bench_full_overflow_disclosed() -> None:
    """席满溢出(design §2.3 sim 先行形态):备战席 9 满帧偷取 3 张
    全部不入席 + 计数披露(disclosures + cw4_counters 双面);牌面刷新
    与信号置位照常(步骤独立)。"""
    b = _to_prep()
    try:
        state_of(b.gs)   # 挂策略器状态(判读面计数键宿主;生产 = flow 以
        # gs 兼 session 同宿主,直驱测试显式挂接)
        b.gs.observe(
            b.gs.bench,
            BenchView(slots=[BenchSlot(kind='unit',
                                       unit=Unit(char_id=f'垫件{i}',
                                                 star=1))
                             for i in range(9)], capacity=9),
            evidence='test:spy', sig=_SIG_OBS)
        out, replay = _feed_levelup(b, spy=True)
        assert out.applied and b.gs.shop_randomized_pending is True
        bench_now = [s.unit.char_id for s in b.gs.bench.value.slots
                     if s.kind == 'unit' and s.unit is not None]
        assert bench_now == [f'垫件{i}' for i in range(9)], \
            '席满溢出:零入席(原有 9 件原样)'
        assert b.disclosures.get('spy_steal_overflow_count') == 3, \
            '溢出计数披露(张数)'
        assert b.disclosures.get('spy_steal_placed_count', 0) == 0
        assert b.disclosures.get('spy_deal_count') == 1, '抽牌计数披露'
        ct = state_of(b.gs).cw4_counters
        assert ct.get('spy_steal_overflow_frames') == 1, \
            '溢出帧计数键(判读面)'
        stolen = _top3_of(replay)
        rest2 = list(_content_names(replay))
        for n in stolen:
            rest2.remove(n)
        assert sorted(_content_names(b.gs.shop.value)) == sorted(rest2), \
            '牌面刷新照常(步骤独立于入席)'
    finally:
        uninstall_backend()
