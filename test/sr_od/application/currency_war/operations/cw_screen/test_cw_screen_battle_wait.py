"""战斗等待 op 利息接入调用测试(镜像 src = operations/cw_screen/
cw_screen_battle_wait.py 的来源 A/B 计数刻;streak 兄弟接入调用测试 =
kernel/test_env_grants.py〔超限只读复用〕,本文件按 src 镜像规范落位)。

测试面依据 = 迭代 T-27 公司契约利息累计触发设计(v2.3 定稿)§2.5 + §4.8③④ + §4.9:
- **来源 A**(胜局结算覆盖窗):面板息行读数 → record+check;计数达标
  → gain_character+done 两笔同 evidence 同 sig(logic_hook 族 group
  'battle-wait:env-grant',同 streak live 形态);「前往结算」补录帧
  (非 telemetry 无面板)零计数不混计;
- **来源 B 唯一计数刻**(V2-F2):1f 败局行写点(_record_loss_page 成功
  路径)显式 killed is False 门内恰计一次;killed=None 抑制零计数;
  「前往结算」补录路径零计数防双计;同败局多帧指纹重入由入账节点一次性标志位拦;
- **三来源覆盖判据**(§4.9):胜局+败局+补给三节点序列逐轮累计,每轮
  恰好一来源,面板读数与推算支不混计。

面板读数经模块读口桩(合成 token,形态坐标 = h_004_012710 实测定标);
识别面真帧锁归 obs/test_cw_settlement_obs.py,本文件零真 OCR。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    DEFAULT_INTEREST_CAP,
    interest,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_battle_wait as bw_mod,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
    CwScreenBattleWait,
    SettlementState,
)

_ENV = '公司契约'
_CHAR = '托帕&账账'
_INTEREST_KEY = 'interest_threshold'
_EVIDENCE = f'env_grant#{_ENV}#interest40'

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenBattleWait',
                       group_id='battle-wait:env-grant')

_FRAME = object()   # 稳定帧哨兵(桩只验判定流;先例 = kernel/test_env_grants)


# ------------------------------------------------------------ 桩面构造


def _tok(data: str, x: int, y: int, w: int = 60, h: int = 30
         ) -> SimpleNamespace:
    """面板 token 桩(属性面 = MatchResult 消费面 data/x/y/w/h)。"""
    return SimpleNamespace(data=data, x=x, y=y, w=w, h=h)


def _panel_items(interest_value: str = '2') -> list:
    """胜局面板合成 token(相对面板原点 2x 裁剪坐标系;形态/坐标 =
    h_004_012710 实测定标:标签 + 独立数值,行序 基础奖励/利息/连胜)。"""
    return [
        _tok('获得金币总览', 40, 17, 292, 54),
        _tok('基础奖励', 40, 119, 197, 56), _tok('4', 1090, 126, 34, 42),
        _tok('利息', 37, 218, 105, 60),
        _tok(interest_value, 1093, 229, 29, 40),
        _tok('连胜', 40, 320, 109, 57), _tok('×0', 137, 321, 125, 58),
        _tok('1', 1102, 332, 15, 31),
    ]


def _make_op(test_context, monkeypatch,
             outcomes: list[RoundOutcome],
             positions: list[tuple[int, int]] | None = None
             ) -> CwScreenBattleWait:
    """battle_wait 裸实例 + 全桩面(先例 = kernel/test_env_grants.
    _make_op;outcomes = 逐次结算的观察桩按序出队;positions = 逐次结算
    的屏面轮次读数桩按序出队,缺省恒 (1,1))。"""
    session = cw4_session()
    st = SettlementState(battle_ts=1234.0, run_start_ts=time.monotonic(),
                         is_new_match=False)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    monkeypatch.setattr(test_context, 'ocr_service',
                        SimpleNamespace(get_ocr_result_list=lambda **k: []),
                        raising=False)
    op = CwScreenBattleWait.__new__(CwScreenBattleWait)
    op.ctx = test_context
    op._st = st
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: SimpleNamespace(is_success=False))
    pos_queue = list(positions or [])
    monkeypatch.setattr(bw_mod, 'read_phase_round',
                        lambda ctx, scr, round_caps=None:
                        pos_queue.pop(0) if pos_queue else (1, 1))
    outcome_queue = list(outcomes)
    monkeypatch.setattr(bw_mod, 'read_round_outcome',
                        lambda ctx, scr, **k: outcome_queue.pop(0))
    return op


def _seed_interest_gs(test_context, *, gold: int | None = None):
    """公司契约局容器种子(环境/席面观察写 + 可选金基座)。"""
    gs = game_state_of(test_context.cw_match.session)
    gs.observe(gs.active_env, _ENV, sig=_SIG_OBS)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
    return gs


def _outcome(killed: bool | None, streak: int | None = None) -> RoundOutcome:
    """结算观察桩(先例 = kernel/test_env_grants._outcome,扩 killed 面)。"""
    return RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                        comp_tag='c', hp_after=3, hp_confidence=1.0,
                        killed=killed, streak=streak)


def _record_logic_writes(gs, monkeypatch) -> list[tuple]:
    """包装两 logic 写入口记录 (字段名, evidence, sig)(透传真实现)。"""
    calls: list[tuple[str, str | None, ChannelSig]] = []

    def _wrap(real, channel):
        def rec(target, value, **kw):
            calls.append((gs._field_name(target), kw.get('evidence'),
                          kw.get('sig')))
            return real(target, value, **kw)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    return calls


# ============================================================ 来源 A


def test_source_a_panel_interest_counts_and_grants(
        test_context, monkeypatch) -> None:
    """来源 A 胜局计数 + 触发(T-27 设计 §4.8③):结算覆盖窗内息行读数
    入账(38+2 跨阈)→ gain_character + done 两笔同 evidence 同 sig;
    sig = logic_hook 族 group 'battle-wait:env-grant'(同 streak live
    形态);入账节点一次性标志位置位。面板读口桩 = 合成 token(真帧锁归 obs 测试)。"""
    op = _make_op(test_context, monkeypatch, [_outcome(killed=True)])
    gs = _seed_interest_gs(test_context)
    gs.effects.record_interest_earned(38)
    monkeypatch.setattr(bw_mod, 'read_settle_interest_panel',
                        lambda ctx, screen: _panel_items('2'))
    calls = _record_logic_writes(gs, monkeypatch)

    op._record_round_outcome(_FRAME)

    assert gs.effects.interest_earned == 40, '面板息读数入账(38+2)'
    assert gs.env_grants_done.value == ((_ENV, _INTEREST_KEY),), 'done 封账'
    units = [s.unit.char_id for s in gs.bench.value.slots
             if s is not None and s.kind == 'unit' and s.unit is not None]
    assert units == [_CHAR], '托帕&账账 1★ 入席(rand=False 确定发放)'
    # 两笔写契约:done evidence = 基串;bench 链写 = 基串 + '#place'
    # (gain-chain.md §2 链内后缀约定);同 sig(logic_hook 族 live 形态)
    pair = [c for c in calls if c[0] in ('bench', 'env_grants_done')]
    assert [c[0] for c in pair] == ['bench', 'env_grants_done'], \
        f'发放两笔相邻写: {calls}'
    assert pair[0][1] == _EVIDENCE + '#place', '链写 evidence(基串+#place)'
    assert pair[1][1] == _EVIDENCE, 'done evidence(基串)'
    assert all(c[2] == _SIG_HOOK for c in pair), '同 sig(logic_hook 族)'
    assert op._st.interest_counted_pos == (1, 1), '入账节点一次性标志位置位'


def test_source_a_zero_interest_row_still_records(
        test_context, monkeypatch) -> None:
    """息 0 形态照常过账(T-27 设计 §2.5:面板在息行缺席 = 零值形态非
    失读):面板读数 0 → record(0) 零增量但计数刻成立(一次性标志位置位),阈值
    不足零发放。"""
    op = _make_op(test_context, monkeypatch, [_outcome(killed=True)])
    gs = _seed_interest_gs(test_context)
    # 无息面板 token(息行整行缺席,形态 = h_004_084253 实测):
    monkeypatch.setattr(bw_mod, 'read_settle_interest_panel',
                        lambda ctx, screen: [
                            _tok('获得金币总览', 40, 17, 292, 54),
                            _tok('基础奖励', 38, 119, 199, 55),
                            _tok('3', 1093, 128, 29, 39),
                            _tok('连胜', 39, 220, 111, 56),
                            _tok('×0', 134, 222, 126, 55)])
    op._record_round_outcome(_FRAME)
    assert gs.effects.interest_earned == 0, '零值入账(过唯一入口函数)'
    assert gs.env_grants_done.value == (), '阈值不足零发放(初始值空元组)'
    assert op._st.interest_counted_pos == (1, 1), '计数刻成立(一次性标志位置位)'


def test_source_a_no_count_on_transfer_button_page(
        test_context, monkeypatch) -> None:
    """「前往结算」补录帧零计数(V2-F2 防双计半边):非 telemetry 路径
    进覆盖块,但按钮页帧面无面板 → 解析 None 零计数,与来源 A 不混计。"""
    op = _make_op(test_context, monkeypatch, [_outcome(killed=None)])
    gs = _seed_interest_gs(test_context, gold=100)
    monkeypatch.setattr(bw_mod, 'read_settle_interest_panel',
                        lambda ctx, screen: [])   # 按钮页无面板
    op._record_round_outcome(_FRAME)
    assert gs.effects.interest_earned == 0, '无面板帧零计数'
    assert op._st.interest_counted_pos is None, '一次性标志位未置位(刻未成立)'


# ============================================================ 来源 B


def test_source_b_unique_counting_point(test_context, monkeypatch) -> None:
    """来源 B 唯一计数刻(T-27 设计 §4.8④/V2-F2):①killed=None 抑制
    形态零计数(宁缺勿造);②killed=False 行写点恰计一次(推算 = 出战金
    100 → 息 10);③同败局多帧指纹重入由入账节点一次性标志位拦零双加;④「前往
    结算」补录路径(非 telemetry 帧面)零计数防双计。"""
    # ① 抑制形态:killed=None 进度漏读败局页
    op = _make_op(test_context, monkeypatch, [_outcome(killed=None)])
    gs = _seed_interest_gs(test_context, gold=100)
    op._record_loss_page(_FRAME, pre_fp=('loss-a', 1))
    assert gs.effects.interest_earned == 0, 'killed=None 抑制零计数'
    # ② 显式败局(killed=False)行写点计一次
    queue = [_outcome(killed=False)]
    monkeypatch.setattr(bw_mod, 'read_round_outcome',
                        lambda ctx, scr, **k: queue.pop(0))
    op._record_loss_page(_FRAME, pre_fp=('loss-b', 1))
    assert gs.effects.interest_earned == interest(100, DEFAULT_INTEREST_CAP), \
        '推算息入账(基座 100,缺省 cap 满档,现算期望)'
    assert op._st.interest_counted_pos == (1, 1), '入账节点一次性标志位置位'
    # ③ 同败局多帧指纹重入(不同指纹 = 双补录行形态)零双加
    op._record_loss_page(_FRAME, pre_fp=('loss-c', 2))
    assert gs.effects.interest_earned == interest(100, DEFAULT_INTEREST_CAP), \
        '入账节点一次性标志位拦零双加'
    # ④ 「前往结算」补录路径(非 telemetry,killed=None 帧面,无面板)
    queue.append(_outcome(killed=None))
    monkeypatch.setattr(bw_mod, 'read_settle_interest_panel',
                        lambda ctx, screen: [])
    op._record_round_outcome(_FRAME)
    assert gs.effects.interest_earned == interest(100, DEFAULT_INTEREST_CAP), \
        '前往结算路径零计数(防双计)'


# ============================================================ 三来源覆盖


def test_three_sources_one_count_per_node(test_context, monkeypatch) -> None:
    """三来源覆盖判据(T-27 设计 §4.9):胜局+败局+补给三节点序列,
    interest_earned 逐轮累计与各来源口径一致;每轮恰好一来源——胜局面板
    读数与推算支不混计(阈值内纯累计面,发放面归专项锁)。"""
    op = _make_op(test_context, monkeypatch, [
        _outcome(killed=True),      # r1 胜局(来源 A:面板息 3)
        _outcome(killed=False),     # r2 败局(来源 B:基座金推算)
    ], positions=[(1, 1), (1, 2)])
    gs = _seed_interest_gs(test_context, gold=100)
    monkeypatch.setattr(bw_mod, 'read_settle_interest_panel',
                        lambda ctx, screen: _panel_items('3'))
    op._record_round_outcome(_FRAME)
    assert gs.effects.interest_earned == 3, 'r1 = 来源 A 面板读数'
    assert op._st.interest_counted_pos == (1, 1)
    # r2 败局(入账节点一次性标志位换节点 = (1,2) 开放;基座金 = 出战前观察 100 →
    # 缺省 cap 满档息 5)
    op._record_loss_page(_FRAME, pre_fp=('loss-r2', 2))
    assert gs.effects.interest_earned == 3 + interest(100, DEFAULT_INTEREST_CAP), \
        'r2 = 来源 B 推算(现算期望)'
    assert op._st.interest_counted_pos == (1, 2)
    # r3 补给(来源 C:常规形态门开,基座 = 备战帧 gs.gold 观察 100 →
    # 息 5;领取完成刻)
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    sup = CwScreenSupplyNode.__new__(CwScreenSupplyNode)
    sup.ctx = test_context
    sup._prep_anchored = True
    sup._count_interest_after_pick(SimpleNamespace(gs=gs))
    assert gs.effects.interest_earned == 3 + interest(100, DEFAULT_INTEREST_CAP) \
        + interest(100, DEFAULT_INTEREST_CAP), 'r3 = 来源 C 推算(现算期望)'
    assert gs.env_grants_done.value == (), '阈值内纯累计(无发放混入)'


# ==================================================== 策略卡到级装备腿

#: live 接入调用 sig 契约形态(logic_hook 族,组号按触发名区分,同窗多触发
#: 各归各组台账可对账;src = 结算覆盖段策略卡到级装备腿调用)。
_SIG_STRAT = ChannelSig(family='logic_hook', actor='CwScreenBattleWait',
                        group_id='battle-wait:strategy-level-grant')

_LATCH_EV = 'strategy_level_grant:钻石商人'


def _stub_settlement_assets(monkeypatch, level: int | None) -> None:
    """结算资产读数桩(纯函数面直桩;gold 恒有值 = 跳过定点补读支)。"""
    from sr_od.application.currency_war.obs import cw_settlement_obs as _so
    monkeypatch.setattr(_so, 'parse_settlement_assets',
                        lambda texts: {'gold': 10, 'level': level,
                                       'xp_cur': None, 'xp_next': None})


def _record_strategy_writes(gs, monkeypatch) -> list[tuple]:
    """包装容器写入口记录 (通道, 字段名, evidence, sig, produced_by)
    (透传真实现;observe 扩展先例 = kernel/test_env_grants
    _live_record_writes,扩 produced_by 轴)。"""
    calls: list[tuple] = []

    def _wrap_logic(real, channel):
        def rec(target, value, **kw):
            calls.append((channel, gs._field_name(target), kw.get('evidence'),
                          kw.get('sig'), kw.get('produced_by')))
            return real(target, value, **kw)
        return rec

    def _wrap_obs(real):
        def rec(target, value, **kw):
            calls.append(('observe', gs._field_name(target),
                          kw.get('evidence'), kw.get('sig'), None))
            return real(target, value, **kw)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap_logic(gs.write_logic, 'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap_logic(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return calls


def test_strategy_level_grant_fires_on_settlement_level_asset(
        test_context, monkeypatch) -> None:
    """live 接入调用锁(结算覆盖位):持卡 + 结算 level 资产 9 → 覆盖写端
    level 真值落账后 equips 写 + 一次性标志位(确定面 logic 写,evidence 基串/
    基串+#equip,同 sig = logic_hook 族组 battle-wait:strategy-level-
    grant);live 零回调 = 三联动域(diamond_count/deploy_cap/back_layout)
    零写零观察。"""
    op = _make_op(test_context, monkeypatch, [_outcome(killed=True)])
    gs = game_state_of(test_context.cw_match.session)
    gs.prep_anchored = True   # 置一次性标志位:达标发放 = 确定事件,锁确定面写通道
    gs.observe(gs.active_strategies, ['钻石商人'], sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    _stub_settlement_assets(monkeypatch, level=9)
    monkeypatch.setattr(bw_mod, 'read_settle_interest_panel',
                        lambda ctx, screen: [])
    coupling_before = (gs.diamond_count.value, gs.deploy_cap.value,
                       gs.back_layout.value)
    calls = _record_strategy_writes(gs, monkeypatch)

    op._record_round_outcome(_FRAME)

    # 防假绿锚:fake 结算路径真实携带 level 真值且走了真覆盖写端
    assert gs.level.value == 9 and gs.level.source == 'observation', \
        '结算覆盖写端必须真实落账(前置态缺失 = 断言恒绿假形态)'
    assert gs.equips.value == ['财富宝钻'], f'未发放: {gs.equips.value!r}'
    assert gs.equips.source == 'logic', '确定事件应走确定面写'
    assert gs.strategy_conditional_done.value == ('钻石商人',), '未落一次性标志位'
    pair = [c for c in calls
            if c[1] in ('equips', 'strategy_conditional_done')]
    assert [c[1] for c in pair] == ['equips', 'strategy_conditional_done'], \
        f'发放两笔相邻写: {[c[:3] for c in calls]}'
    assert pair[0][2] == f'{_LATCH_EV}#equip', '发放 evidence(#equip 链)'
    assert pair[1][2] == _LATCH_EV, '一次性标志位 evidence(基串)'
    assert all(c[3] == _SIG_STRAT for c in pair), '同 sig(logic_hook 族)'
    assert all(c[4] == 'strategy_level_equip_grant' for c in pair), \
        'producer 专名(家族纪律)'
    # 次序:level 观察(覆盖写端)严格先于发放两笔
    idx_level = next(i for i, c in enumerate(calls) if c[1] == 'level')
    assert idx_level < calls.index(pair[0]), \
        f'接入调用次序漂移(发放必须在结算覆盖后): {calls}'
    # live 零回调(锁 8 live 半):三联动域零写零观察(逻辑侧禁写,
    # 联动归观察域识别器;种子初始值调用前后零变化)
    touched = [c for c in calls if c[1] in ('diamond_count', 'deploy_cap',
                                            'back_layout')]
    assert touched == [], f'live 出现联动域写: {touched}'
    assert (gs.diamond_count.value, gs.deploy_cap.value, gs.back_layout.value) \
        == coupling_before, 'live 联动域值漂移(应零回调)'


def test_strategy_level_grant_skipped_when_level_asset_none(
        test_context, monkeypatch) -> None:
    """门控锁:结算 level 资产 None(覆盖写端跳过 level 观察口径)→ 不调
    不写——门控与覆盖写端同口径,防「读不到硬判」误发。流达证明 =
    同段持续伤害检查(dot)被调到(门控位前最后一段),kernel 检查腿
    记录器零调用。"""
    op = _make_op(test_context, monkeypatch, [_outcome(killed=True)])
    gs = game_state_of(test_context.cw_match.session)
    gs.observe(gs.active_strategies, ['钻石商人'], sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    _stub_settlement_assets(monkeypatch, level=None)
    monkeypatch.setattr(bw_mod, 'read_settle_interest_panel',
                        lambda ctx, screen: [])
    from sr_od.application.currency_war.kernel import cw_env_grants as _grants
    from sr_od.application.currency_war.kernel import cw_gain_chain as _gc
    reached: list[str] = []
    monkeypatch.setattr(_grants, 'check_env_dot_grants',
                        lambda *a, **k: reached.append('dot'))
    kernel_calls: list = []
    monkeypatch.setattr(_gc, 'check_strategy_level_equip_grants',
                        lambda gs_, sig: kernel_calls.append(sig))

    op._record_round_outcome(_FRAME)

    assert reached == ['dot'], '前置:结算覆盖段未走到装备腿门控位(块中断)'
    assert kernel_calls == [], 'level 资产 None 门控失效(误调检查腿)'
    assert gs.equips.value == [], '门控窗误发放'
    assert gs.strategy_conditional_done.value in (None, ()), '门控窗误置一次性标志位'
