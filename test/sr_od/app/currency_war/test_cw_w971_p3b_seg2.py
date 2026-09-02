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
    """流程层拦截 = 类型分派(字符串匹配判据退役,W970 §3)。"""
    from sr_od.application.currency_war import prep_director as pd_mod

    port_src = inspect.getsource(pd_mod.PrepDirector._run_prep_loop_v2)
    assert 'isinstance(action, OpenShop)' in port_src, '执行端口缺 OpenShop 类型分派'
    assert "if 'EnsureShopClosed' in key" not in port_src, (
        '探针挂点字符串匹配判据未退役(§3:改类型分派)')


def test_open_shop_phase_orchestration() -> None:
    """流程层商店编排契约(read_only 与买牌两形态 + 探针挂点随迁)。"""
    from sr_od.application.currency_war import prep_director as pd_mod

    src = inspect.getsource(pd_mod.PrepDirector._open_shop_phase)
    # 编排序:open_shop → (read_only: 观察+关店 | 波循环+关店) → finalize → 探针
    assert src.index('open_shop(self)') < src.index('close_shop(self)'), '开店须先于关店'
    assert 'run_buy_waves' in src and 'finalize_buy_phase' in src, (
        '买牌形态缺商店动作波循环/单元收尾(壳直调三 op 调用点须上移流程层)')
    assert src.rindex('_probe_node_type') > src.rindex('close_shop(self)'), (
        '节点探针挂点须在 CloseShopOp 完成后(W970 §4.3.5)')
    # read_only 形态:heavy 观察刷新(gold 开态真值)语义在编排内声明
    assert src.count('read_only') >= 3 and '_observe(heavy=True)' in src


def test_buy_phase_finalize_single_source() -> None:
    """买后收尾单一源:finalize_buy_phase 模块函数,壳与流程层共用(防双份漂移)。"""
    from sr_od.application.currency_war.operations.prep import shop as shop_mod

    assert hasattr(shop_mod, 'finalize_buy_phase')
    buy_src = inspect.getsource(shop_mod.BuyShopCards.buy)
    assert 'finalize_buy_phase(' in buy_src, '壳未改用共用收尾函数'
    assert 'pending_buy_expect' not in buy_src, (
        '买后收尾段仍内联在壳里(应已抽入 finalize_buy_phase 单一源)')


# ==================== 主循环:稳定门/标志位/接管补采退役 ====================


def _loop_src() -> str:
    from sr_od.application.currency_war.operations import battle_loop
    return inspect.getsource(battle_loop.CurrencyWarRunLoop)


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
    """接管局补采挂点迁移(01-opening §2.1):battle_loop 内联块退役,
    由干净备战观察(prep_director 环入口 gate 后稳定帧)承担。"""
    assert '_cw_takeover_done' not in _loop_src(), 'loop 内联补采块未退役'
    from sr_od.application.currency_war import prep_director as pd_mod
    src = inspect.getsource(pd_mod.PrepDirector._run_loop)
    assert 'cw_takeover_collect_done' in src, 'prep_director 缺接管补采块'
    assert 'briefing_bosses' in src, '补采触发门(简报真值空)缺失'
    assert 'CollectPlaneIntel' in src, '补采通道(位面详情采集 op)缺失'


# ==================== 环入口分诊(实机 P1-r6 bail ping-pong 返工) ====================

def _make_entry_director(test_context, monkeypatch, hits: list[tuple[str, str]]):
    """分诊单测装配:环入口探针桩(收店恒失败)+ 锚命中集替身 + 副作用替身。"""
    from types import SimpleNamespace as _SN

    from sr_od.application.currency_war import prep_director as pd_mod
    from sr_od.application.currency_war.decision.cw_strategy import (
        StrategySession,
    )
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        DeferSpheres as _DS,
    )

    class _StubStrategy:
        def decide_prep_screen(self, session, config):
            return _DS()

    d = pd_mod.PrepDirector(test_context)
    session = StrategySession()
    match = _SN(strategy=_StubStrategy(), session=session)
    monkeypatch.setattr(d, 'screenshot', lambda *a, **k: None)
    monkeypatch.setattr(d, '_try_collapse_open_shop', lambda: False)
    monkeypatch.setattr(d, 'save_screenshot', lambda *a, **k: '<shot>')

    def _find(screen, screen_name, area_name, **k):
        if (screen_name, area_name) in hits:
            return d.round_success('')
        return d.round_fail('')

    monkeypatch.setattr(d, 'round_by_find_area', _find)
    stops: list[str] = []
    monkeypatch.setattr(
        test_context, 'run_context',
        _SN(stop_running=lambda reason='': stops.append(reason)), raising=False)
    return d, match, session, stops


def test_entry_known_overlay_hands_back_and_resets_counter(
    test_context, monkeypatch,
) -> None:
    """遭遇 overlay 帧在环入口 → 交回外环分发 + 帧不clean 同因计数重置
    (实机 P1-r6:同因 ×3 停机的返工判据)。"""
    from sr_od.application.currency_war import prep_director as pd_mod

    d, match, session, _stops = _make_entry_director(
        test_context, monkeypatch,
        hits=[('货币战争-遭遇节点', '标识-遭遇节点')])
    session.bail_reason_counts[pd_mod.GATE_UNCLEAN_REASON] = 2   # 差 1 次即停机

    result = d._entry_dispatch_or_bail(match, session)

    assert result.is_success, f'已知 overlay 应交回(success),实得 {result.status!r}'
    assert '遭遇' in (result.status or '') and '交回' in (result.status or ''), (
        f'交回语义缺失:{result.status!r}')
    assert pd_mod.GATE_UNCLEAN_REASON not in session.bail_reason_counts, (
        '同因计数未重置(仍会 ×3 停机)')
    assert session.cw_entry_diag_streak == 1
    assert _stops == [], '命中已知 overlay 不得触发停机'


def test_entry_unknown_frame_still_counts_gate_bail(
    test_context, monkeypatch, tmp_path,
) -> None:
    """未知帧(无任何已知 overlay 锚命中)→ 同因 bail 计数照旧(兜底语义不变)。"""
    monkeypatch.chdir(tmp_path)   # _bail ≥3 分支的 flag 写相对路径,隔离到 tmp
    from sr_od.application.currency_war import prep_director as pd_mod

    d, match, session, _stops = _make_entry_director(
        test_context, monkeypatch, hits=[])
    session.bail_reason_counts[pd_mod.GATE_UNCLEAN_REASON] = 0

    result = d._entry_dispatch_or_bail(match, session)

    assert result.is_success   # bail = round_success 交外环(未达停机阈)
    assert session.bail_reason_counts[pd_mod.GATE_UNCLEAN_REASON] == 1


def test_entry_diag_streak_resets_on_tag_change(
    test_context, monkeypatch,
) -> None:
    """标签变化(遭遇→巨星)→ 已知 overlay 交回连击清零(合法多 overlay 逐个
    消化不是 ping-pong;M11 同型教训)。"""
    d, match, session, _stops = _make_entry_director(
        test_context, monkeypatch,
        hits=[('货币战争-遭遇节点', '标识-遭遇节点')])
    r1 = d._entry_dispatch_or_bail(match, session)
    assert r1.is_success and session.cw_entry_diag_streak == 1

    monkeypatch.setattr(
        d, 'round_by_find_area',
        lambda s, sn, a, **k: d.round_success('')
        if (sn, a) == ('货币战争-盛会之星', '标识-盛会之星') else d.round_fail(''))
    r2 = d._entry_dispatch_or_bail(match, session)
    assert r2.is_success and session.cw_entry_diag_streak == 1, '标签变化应重置连击'
    assert _stops == []


def test_entry_diag_same_tag_x3_stops_with_evidence(
    test_context, monkeypatch, tmp_path,
) -> None:
    """同标签 ×3 交回仍回环 = loop 分支接不住 → 停机留证(兜底换形态保留)。"""
    monkeypatch.chdir(tmp_path)   # flag 相对路径隔离
    d, match, session, stops = _make_entry_director(
        test_context, monkeypatch,
        hits=[('货币战争-遭遇节点', '标识-遭遇节点')])

    for _ in range(3):
        result = d._entry_dispatch_or_bail(match, session)

    assert not result.is_success, f'连击 ≥3 应停机 fail,实得 {result.status!r}'
    assert stops and stops[0] == 'hook:entry_overlay_pingpong'
    assert (tmp_path / '.debug/temp/currency_war/entry_overlay_pingpong_hook.flag').exists()


def test_loop_redispatches_after_director_return() -> None:
    """修复①(重入必经全分支判定):director 返回后外环显式交回顶层分发
    (round_wait 重跑 loop 节点 = 全分支重判,0x overlay 分支先于备战双锚)。"""
    src = _loop_src()
    assert '交回顶层分发' in src, 'director 返回后缺显式重入日志/交回点'
    assert 'return self.round_wait(wait=1.0)  # 下轮重新识别分发' in src, (
        'director 返回后的 round_wait 交回点缺失')
