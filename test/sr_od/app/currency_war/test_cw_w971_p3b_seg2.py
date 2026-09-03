"""W971 P3b 段2 接线锁:纯分发器接管备战/商店常态编排(W970 批 C 全项)。

设计单一源 = docs/develop/currency_war/prereg/w970_layered_arch/DESIGN.md
§3/§4.3(RunBuyPhase 解体/EnsureShop 意图退役/腾席链 b read_only/探针挂点
随迁/_handle_bench_full 合流)+ w971_flow_layer/03-prep.md(稳定门退役)。
"""

import inspect

from sr_od.application.currency_war.decision.decision_v2.adapter import (
    action_to_atomop,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PREP_ACTION_TYPES,
    OpenShop,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

# ==================== 决策层:动作发射改型(新旧映射对拍) ====================

#: 新旧动作映射(决策输出等价改名;流程层语义由编排承接)
_RENAME_MAP = {
    'RunBuyPhase': lambda a: isinstance(a, OpenShop) and not a.read_only,
    'EnsureShopOpen': lambda a: isinstance(a, OpenShop) and a.read_only,
    'EnsureShopClosed': lambda a: isinstance(a, OpenShop) and a.read_only,
}


def test_open_shop_action_registered() -> None:
    """OpenShop 进动作全集白名单 + AtomOp 映射(漏登记 = F3 拒绝/影子未知缺陷)。"""
    assert OpenShop in PREP_ACTION_TYPES
    op = action_to_atomop(OpenShop(read_only=True))
    assert op.op_key.startswith('open_shop') and op.domain == 'shop'


def test_strategy_emits_open_shop_forms() -> None:
    """决策发射改型(对拍:旧输出 → 新输出按改名映射逐项等价):
    RunBuyPhase→OpenShop / EnsureShopOpen→OpenShop(read_only) /
    EnsureShopClosed→OpenShop(read_only),生产路径零旧意图残留。"""
    from sr_od.application.currency_war.decision.decision_v2 import (
        strategy as strat_mod,
    )

    src = inspect.getsource(strat_mod.DecisionV2Strategy)
    assert src.count('return OpenShop(read_only=True)') == 2, (
        '腾席链 b / 开态清洁面板两处须发 OpenShop(read_only)')
    assert 'return OpenShop()' in src, '主流程买牌段须发显式开店意图 OpenShop()'
    for retired in ('return RunBuyPhase()', 'return EnsureShopOpen()',
                    'return EnsureShopClosed()'):
        assert retired not in src, f'{retired} 仍在新接口发射(须按映射改型)'


def test_v2_engine_intercepts_open_shop_by_type() -> None:
    """流程层拦截 = 类型分派(字符串匹配判据退役,W970 §3)。

    W971 P3b 拆内环:拦截点自 v2 执行端口平移到备战单轮 run(五段⑤执行)。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep as pd_mod

    run_src = inspect.getsource(pd_mod.CwScreenPrep.run)
    assert 'isinstance(action, OpenShop)' in run_src, '单轮执行段缺 OpenShop 类型分派'
    assert "if 'EnsureShopClosed' in key" not in run_src, (
        '探针挂点字符串匹配判据未退役(§3:改类型分派)')


def test_open_shop_phase_orchestration() -> None:
    """流程层商店编排契约(read_only 与买牌两形态 + 探针挂点随迁)。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep as pd_mod

    src = inspect.getsource(pd_mod.CwScreenPrep._open_shop_phase)
    # 编排序:open_shop → (read_only: 观察+关店 | 波循环+关店) → finalize → 探针
    assert src.index('open_shop(self)') < src.index('close_shop(self)'), '开店须先于关店'
    assert 'run_buy_waves' in src and 'finalize_buy_phase' in src, (
        '买牌形态缺商店动作波循环/单元收尾(壳直调三 op 调用点须上移流程层)')
    assert src.rindex('_probe_node_type') > src.rindex('close_shop(self)'), (
        '节点探针挂点须在 CwOpCloseShop 完成后(W970 §4.3.5)')
    # read_only 形态:heavy 观察刷新(gold 开态真值)语义在编排内声明
    assert src.count('read_only') >= 3 and '_observe(heavy=True)' in src


def test_buy_phase_finalize_single_source() -> None:
    """买后收尾单一源:finalize_buy_phase 模块函数(退役批:壳删除后唯一宿主
    = 流程层 cw_screen_prep;防双份漂移的单一源语义不变)。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep as pd_mod

    assert hasattr(pd_mod, 'finalize_buy_phase'), (
        'finalize_buy_phase 未落流程层单一源')

# ==================== 主循环:稳定门/标志位/接管补采退役 ====================


def _loop_src() -> str:
    from sr_od.application.currency_war.operations import cw_loop
    return inspect.getsource(cw_loop.CwLoop)


def test_prep_settle_gate_retired() -> None:
    """PREP_SETTLE_S 稳定门退役(W971 03-prep §1):门常量与 bookkeeping 删除。"""
    src = _loop_src()
    assert 'PREP_SETTLE_S: ClassVar' not in src, '稳定门常量未退役'
    assert '_prep_entry_ts' not in src and '_prev_frame_prep' not in src, (
        '稳定门 bookkeeping 未删')


def test_post_settle_auto_shop_flag_retired() -> None:
    """_post_settle_auto_shop 标志位退役(W971 §2.11:判稳收编战斗等待侧/
    director 环入口预收探针,不再跨分支传标志)。"""
    src = _loop_src()
    assert '_post_settle_auto_shop = True' not in src, '标志位写入点未退役'
    assert 'getattr(self, \'_post_settle_auto_shop\', False)' not in src, (
        '标志位消费点未退役')


def test_takeover_collect_moved_to_director() -> None:
    """接管局补采挂点迁移(01-opening §2.1):cw_loop 内联块退役,
    由备战单轮 op 观察段(_takeover_collect_if_needed)承担。"""
    assert '_cw_takeover_done' not in _loop_src(), 'loop 内联补采块未退役'
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep as pd_mod
    src = inspect.getsource(pd_mod.CwScreenPrep._takeover_collect_if_needed)
    assert 'cw_takeover_collect_done' in src, 'cw_screen_prep 缺接管补采块'
    assert 'briefing_bosses' in src, '补采触发门(简报真值空)缺失'
    assert 'CwScreenPlaneIntel' in src, '补采通道(位面详情采集 op)缺失'
    assert '_takeover_collect_if_needed(match, session)' in inspect.getsource(
        pd_mod.CwScreenPrep.run), '单轮观察段缺接管补采挂点'


# ==================== 拆内环定稿:备战单轮 op + 外循环轮转(返工升级) ====================

def _make_round_director(test_context, monkeypatch, scripted_action):
    """备战单轮单测装配:观察/清场/收店/补采/对账/破墙/遥测全替身,
    策略脚本化(单动作),OpenShop 编排替身。"""
    from types import SimpleNamespace as _SN

    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep as pd_mod
    from sr_od.application.currency_war.decision.cw_strategy import (
        StrategySession,
    )

    class _StubStrategy:
        def __init__(self):
            self.calls = 0

        def decide_prep_screen(self, session, config):
            self.calls += 1
            return scripted_action

        def update_target(self, state, session, config):
            pass

    d = pd_mod.CwScreenPrep(test_context)
    session = StrategySession()
    strat = _StubStrategy()
    match = _SN(strategy=strat, session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    monkeypatch.setattr(d, '_clear_entry_overlays', lambda: None)
    monkeypatch.setattr(d, '_try_collapse_open_shop', lambda: False)
    monkeypatch.setattr(d, '_takeover_collect_if_needed', lambda m, s: None)
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)   # 遥测替身

    class _Obs:
        event_overlay = None
        state = None
        bench_chars: list = []
        deployed_chars: list = []
        spheres: list = []
        boxes: list = []
        deploy_vacancy = 0

    monkeypatch.setattr(d, '_observe', lambda heavy=True, screen=None: _Obs())
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_observation.read_bench_full',
        lambda ctx, screen: False)   # 破墙分支让路
    monkeypatch.setattr(d, '_open_shop_phase', lambda a, obs: (True, 'read_only 读牌完成'))
    return d, match, session, strat


def test_prep_round_full_lifecycle_hands_back(
    test_context, monkeypatch,
) -> None:
    """备战单轮 op 五段(观察→对账→决策→期望态→执行)→ 交回外循环:
    单轮恰执行一个动作即交回,无内环 while(拆内环定稿)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        OpenShop,
    )

    d, match, session, strat = _make_round_director(
        test_context, monkeypatch, OpenShop(read_only=True))

    with fast_sleep():
        enter_running_state(test_context)
        try:
            result = d.run()
        finally:
            reset_running_state(test_context, d)

    assert strat.calls == 1, '单轮恰一次决策'
    assert '交回外循环' in (result.status or ''), f'单轮须交回外循环:{result.status!r}'
    assert 'read_only' in (result.status or ''), '执行段须消费 OpenShop 编排'


def test_prep_round_event_overlay_hands_back_without_execute(
    test_context, monkeypatch,
) -> None:
    """轮转回归锁(实机 P1-r6 场景的结构性修复):备战帧带事件 overlay →
    单轮观察段即交回外循环(零计数、零执行)——外循环重识别后 0x 分支
    (遭遇 op 等)接管,回备战再进单轮。bail/同因 ×3/ping-pong 停机机制
    已随内环拆除。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        OpenShop,
    )

    d, match, session, strat = _make_round_director(
        test_context, monkeypatch, OpenShop(read_only=True))

    class _OverlayObs:
        event_overlay = '遭遇'
        state = None
        bench_chars: list = []
        deployed_chars: list = []
        spheres: list = []
        boxes: list = []
        deploy_vacancy = 0

    monkeypatch.setattr(d, '_observe', lambda heavy=True, screen=None: _OverlayObs())

    with fast_sleep():
        enter_running_state(test_context)
        try:
            result = d.run()
        finally:
            reset_running_state(test_context, d)

    assert strat.calls == 0, 'overlay 帧不得进入决策/执行'
    assert '交回外循环' in (result.status or ''), f'须交回外循环:{result.status!r}'
    assert not getattr(session, 'bail_reason_counts', None), (
        '交回不得带任何同因计数(bail 机制已拆除)')


def test_outer_loop_rediscovers_between_prep_rounds() -> None:
    """外循环轮转(单层循环定稿):备战单轮交回 → loop 顶全分支重判 →
    遭遇 overlay 帧由 0c 遭遇分支(CwScreenEncounter)先于备战双锚接管
    (P1-r6 停机场景的回归锁,源级)。"""
    src = _loop_src()
    # 遭遇分发在备战分支之前(源码序 = 判定优先序)
    assert src.index("'货币战争-遭遇节点', '标识-遭遇节点'") < src.index(
        "and self.round_by_find_area(screen, '货币战争-备战', '按钮-出战')"), (
        '遭遇分发须先于备战双锚(overlay 帧不得直落备战分支)')
    assert 'CwScreenEncounter(self.ctx)' in src, '遭遇 op 分发缺失'
    # 单轮交回 → 外循环重识别(前锁 test_loop_redispatches_after_director_return)
    assert '交回顶层分发' in src


def test_prep_stall_evidence_in_outer_loop() -> None:
    """stall 防线平移外循环(03-prep §3 规格最小集):连续 N 轮备战画面
    session 对账字段族无变化 → 留证(log + 存图,不停机)。"""
    from sr_od.application.currency_war.operations import cw_loop
    src = _loop_src()
    assert 'PREP_STALL_EVIDENCE_ROUNDS' in inspect.getsource(cw_loop), (
        'stall 留证阈值常量缺失')
    assert '_prep_stall_sig' in src and '_prep_stall_count' in src, (
        'stall 签名/计数状态缺失')
    assert 'prep_stall' in src, '留证存图缺失'


def test_loop_redispatches_after_director_return() -> None:
    """修复①(重入必经全分支判定):director 返回后外环显式交回顶层分发
    (round_wait 重跑 loop 节点 = 全分支重判,0x overlay 分支先于备战双锚)。"""
    src = _loop_src()
    assert '交回顶层分发' in src, 'director 返回后缺显式重入日志/交回点'
    assert 'return self.round_wait(wait=1.0)  # 下轮重新识别分发' in src, (
        'director 返回后的 round_wait 交回点缺失')


# ==================== BOSS 简报 op(实机第三局走查补:06-overlays §3) ====================

_FRAME = ('货币战争-BOSS简报', 'default')


def _make_boss_op(test_context: SrTestContext, monkeypatch):
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_boss_briefing import (
        CwScreenBossBriefing,
    )
    from test.harness.fixture_controller import (
        FixtureController,
        WatchdogOperationMixin,
    )

    fc = FixtureController(test_context)
    fc.set_phases([{'frame': _FRAME}])
    monkeypatch.setattr(test_context, 'controller', fc)
    op = type('W', (WatchdogOperationMixin, CwScreenBossBriefing), {})(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    monkeypatch.setattr(fc, 'mouse_move', lambda *a, **k: None, raising=False)
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: '<shot>')
    return op, fc


def test_boss_briefing_op_click_blank_then_wait_shop_anchor(
    test_context: SrTestContext, monkeypatch,
) -> None:
    """行为锁(06-overlays §3/§5):识别「强敌来袭」→ 点空白 → 完成承诺 =
    轮询备战商店开锚(「按钮-收起」);锚现 → 收口交回。"""
    op, _fc = _make_boss_op(test_context, monkeypatch)
    # 入口锚 + 空白区命中;完成锚首帧未现、第二轮现(点击生效推进)。
    hits = {('货币战争-BOSS简报', '标识-强敌来袭'),
            ('货币战争-BOSS简报', '区域-空白点击')}
    done_seen: list[int] = []

    def _find(screen, screen_name, area_name, **k):
        if (screen_name, area_name) == ('货币战争-备战-开商店', '按钮-收起'):
            done_seen.append(1)
            if len(done_seen) >= 2:   # 首查未现,轮询一次后现
                return op.round_success('')
            return op.round_fail('')
        if (screen_name, area_name) in hits:
            return op.round_success('')
        return op.round_fail('')

    monkeypatch.setattr(op, 'round_by_find_area', _find)
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda *a, **k: op.round_success(''))
    monkeypatch.setattr(op, 'screenshot', lambda *a, **k: op.last_screenshot)
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)

    enter_running_state(test_context)
    try:
        with fast_sleep():
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert result.success, f'boss 简报应推进成功:{result.status!r}'
    assert _fc.click_hit_area('货币战争-BOSS简报', '区域-空白点击'), (
        f'未点空白:{_fc.recorded_clicks}')
    assert '商店开' in (result.status or '')


def test_boss_briefing_op_mark_miss_fails_without_click(
    test_context: SrTestContext, monkeypatch,
) -> None:
    """入口识别不中(非 boss 简报帧/接管误派)→ fail 且不点。"""
    op, fc = _make_boss_op(test_context, monkeypatch)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sn, a, **k: op.round_fail(''))

    enter_running_state(test_context)
    try:
        with fast_sleep():
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert not result.success
    assert not fc.recorded_clicks, '锚不中不得点击'


def test_boss_briefing_dispatch_before_prep_anchor() -> None:
    """分发源锁(P1-r6 同型教训锚位):boss 简报分支必须**先于备战双锚**,
    且横幅遮挡下双锚透出命中时帧不得直落备战分支。"""
    src = _loop_src()
    assert "CwScreenBossBriefing(self.ctx)" in src, 'BOSS 简报分支未接线'
    assert src.index("'货币战争-BOSS简报', '标识-强敌来袭'") < src.index(
        "and self.round_by_find_area(screen, '货币战争-备战', '按钮-出战')"), (
        'BOSS 简报分发须先于备战双锚(横幅遮挡双锚透出命中)')
