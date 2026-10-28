"""环境条件发放测试(机制主题文件;kernel 条件矩阵 → live 接线 → 刷新
次数发放全链;迭代 2026-10-10-env-conditional-grants + T-7 二手市场)。

被测机制(按节):
- **连败/连胜条件发放 kernel 矩阵**(详设 details/env-conditional-grant.md
  §1–§4):触发条件七序短路、随机态发放写行(equips 追加
  write_logic_rand + done 登记 write_logic 同 evidence 相邻)、sig 单
  形态契约、宝钻获得回调三写、登记表构建校验、种子底座与快照恢复;
- **live 接线**(该迭代 landing 3.2 节):结算覆盖写端之后才触发发放
  (fake 结算路径真走覆盖写端,防假绿)、猜错整表观察纠偏、streak
  None 结算跳过;
- **刷新次数条件发放**(T-7 二手市场,设计 =
  .debug/progress/2026-09-23-invest-effects-calc/designs/T-7-ershichang.md
  §2):登记表六查(含 T-21 跨锁失同步)、条件矩阵(含 gold/equips 缺读
  缓发禁半发放)、发放三笔相邻写、计数域全量口径(用户裁定①)、
  一次性(用户裁定②)、上报函数接线存在性;
- **长线利好**(T-21 付费域触发器,设计 =
  .debug/progress/2026-09-23-invest-effects-calc/designs/T-21-changxian-
  liaoli.md §4):付费域计数(「花费金币」限定词,防回退全量域)、
  金-only 两笔发放、一次性、缓发重试、上报接线与刷费价基边界
  (第 30 刷扣旧价同窗 +20,31 刷扣新价 1)。

sim 接线(3.3)与 supply 采纳边界不在此。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel import cw_env_grants as grants_mod
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_refresh_shop_param,
)
from sr_od.application.currency_war.kernel.cw_env_grants import (
    FIRST_STREAK_KEY,
    REFRESH_THRESHOLD_KEY,
    check_env_refresh_grants,
    check_env_streak_grants,
    on_diamond_acquired,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    game_state_of,
    restore_state_snapshot,
    seed_opening_state,
)
from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionRefreshShopParam,
)
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_battle_wait as bw_mod,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
    CwScreenBattleWait,
    SettlementState,
)

_ENV = '深井角斗场'
_EQUIP = '财富宝钻'

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
# 触发函数两写 sig 形态(live 形态,详设 §5:logic_hook 族 group
# 'battle-wait:env-grant';sim 形态 = logic_sig('sim:env') 归 3.3)
_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenBattleWait',
                       group_id='battle-wait:env-grant')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test-seed',
                        mode='compute')


def _make_gs(*, env: str | None = None,
             equips: list[str] | None = None,
             done: tuple[tuple[str, str], ...] | None = None,
             level: int | None = 5,
             diamond_count: int | None = None,
             back_layout: int | None = None) -> GameState:
    """观察面按参组装(None = 保持未写形态;登记域经 logic 直写播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       sig=_SIG_LOGIC)
    if done is not None:
        gs.write_logic(gs.env_grants_done, tuple(done), produced_by='test-seed',
                       sig=_SIG_LOGIC)
    if level is not None:
        gs.observe(gs.level, level, sig=_SIG_OBS)
    if diamond_count is not None:
        gs.observe(gs.diamond_count, diamond_count, sig=_SIG_OBS)
    if back_layout is not None:
        gs.observe(gs.back_layout, back_layout, sig=_SIG_OBS)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道, sig) 写行。"""
    calls: list[tuple[str, str | None, str, ChannelSig]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel, sig))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic',
                        _wrap(gs.write_logic, 'logic'))
    return calls


# ============================================================ 触发条件矩阵


def test_condition_matrix_short_circuits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """条件矩阵前五序短路:env 空链(None/'')/不在册/连败方向/低于阈值/
    已发 done → 全部 None 且零写。"""
    cases: list[tuple[str, GameState]] = [
        ('env 未选择(None 形态)', _make_gs(equips=[])),
        ('env 空链(开局种子形态)', _make_gs(env='', equips=[])),
        ('env 不在册', _make_gs(env='蓝海', equips=[])),
    ]
    for label, gs in cases:
        calls = _record_writes(gs, monkeypatch)
        assert check_env_streak_grants(gs, 5, _SIG_HOOK) is None, label
        assert not calls, f'{label} 零写: {calls}'

    # 连败/零方向(streak_after ≤ 0,带符号口径)
    for streak in (0, -1, -3):
        gs = _make_gs(env=_ENV, equips=[])
        calls = _record_writes(gs, monkeypatch)
        assert check_env_streak_grants(gs, streak, _SIG_HOOK) is None, \
            f'streak={streak}'
        assert not calls, f'streak={streak} 零写'

    # 低于阈值(4 < 5)
    gs = _make_gs(env=_ENV, equips=[])
    calls = _record_writes(gs, monkeypatch)
    assert check_env_streak_grants(gs, 4, _SIG_HOOK) is None
    assert not calls, '低于阈值零写'

    # 已发 done 在册(幂等守卫,5/6 连胜重查不重发)
    gs = _make_gs(env=_ENV, equips=[], done=((_ENV, FIRST_STREAK_KEY),))
    for streak in (5, 6):
        calls = _record_writes(gs, monkeypatch)
        assert check_env_streak_grants(gs, streak, _SIG_HOOK) is None
        assert not calls, f'done 在册 streak={streak} 零写'


def test_done_none_treated_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """done 域 None(从未写形态)→ 视为空防御照发(直构容器域未写,
    守卫 membership 判定不因 None 崩/不误判已发)。"""
    gs = _make_gs(env=_ENV, equips=[])   # env_grants_done 未写 = None
    assert gs.env_grants_done.value is None
    calls = _record_writes(gs, monkeypatch)

    assert check_env_streak_grants(gs, 5, _SIG_HOOK) == _EQUIP
    assert [c[0] for c in calls] == ['equips', 'env_grants_done'], \
        f'done None 防御照发两写: {calls}'


def test_equips_unobserved_no_done_next_settlement_retries(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """equips 缺读(从未观察)→ 宁缺勿造:零写、不标 done,下个结算
    库存已读后自动重试(与晶矿生成集「下帧再试」同性质)。"""
    gs = _make_gs(env=_ENV)   # equips 未写 = None
    calls = _record_writes(gs, monkeypatch)
    assert check_env_streak_grants(gs, 5, _SIG_HOOK) is None
    assert not calls, f'缺读零写: {calls}'
    assert gs.env_grants_done.value is None, '缺读不标 done'

    # 补读后(库存观察/直写到位)下个结算重试 → 发放成功
    gs.write_logic(gs.equips, ['永动机'], produced_by='test-seed',
                   sig=_SIG_LOGIC)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_streak_grants(gs, 5, _SIG_HOOK) == _EQUIP
    assert [c[0] for c in calls] == ['equips', 'env_grants_done']
    assert gs.env_grants_done.value == ((_ENV, FIRST_STREAK_KEY),)


def test_grant_writes_rand_then_done_same_evidence_adjacent(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """发放写行:equips 追加走 write_logic_rand(evidence
    env_grant#深井角斗场#streak5)+ done 追加走 write_logic,两笔同
    evidence 同 sig 相邻(rand 在前);追加位置 = 库存尾部(无 rng)。"""
    gs = _make_gs(env=_ENV, equips=['永动机', '高周波电锯'])
    calls = _record_writes(gs, monkeypatch)

    granted = check_env_streak_grants(gs, 5, _SIG_HOOK)

    assert granted == _EQUIP, '返回被发装备名(调用方据此裁决回调)'
    assert gs.equips.value == ['永动机', '高周波电锯', _EQUIP], \
        '库存尾部追加(随机态指落位未知,追加位置确定)'
    assert gs.env_grants_done.value == ((_ENV, FIRST_STREAK_KEY),)
    assert calls == [
        ('equips', 'env_grant#深井角斗场#streak5', 'rand', _SIG_HOOK),
        ('env_grants_done', 'env_grant#深井角斗场#streak5', 'logic',
         _SIG_HOOK),
    ], f'两笔同 evidence 同 sig 相邻(rand 在前): {calls}'
    assert gs.equips.source == 'logic_rand', '发放 = 随机态通道'
    assert gs.env_grants_done.source == 'logic', 'done = 登记事实直写'


def test_trigger_rejects_obs_sig() -> None:
    """sig 单形态契约:obs 族进触发函数即炸渠道族校验(write_logic_rand
    渠道封闭集 = logic_action/logic_hook;禁 obs_sig,详设 §5)。"""
    gs = _make_gs(env=_ENV, equips=[])
    with pytest.raises(ValueError, match='渠道族'):
        check_env_streak_grants(gs, 5, _SIG_OBS)
    assert gs.equips.value == [], '炸错前置零写'


# ============================================================ 宝钻获得回调


def test_callback_three_writes_cap_and_back_layout(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """回调三写:diamond_count+1 / deploy_cap = level + equips 现值中
    财富宝钻计数(拥有即算可叠加)/ back_layout = min(9, 现值+1);
    三写翻 observation(observe 渠道,sim 世界事实)。"""
    # 标准路径:发放后形态(库存含刚到手的 1 颗),level 5
    gs = _make_gs(env=_ENV, equips=['永动机', _EQUIP],
                  diamond_count=0, back_layout=6)
    on_diamond_acquired(gs, _EQUIP)
    assert gs.diamond_count.value == 1
    assert gs.diamond_count.source == 'observation', '世界事实走观察通道'
    assert gs.deploy_cap.value == 5 + 1, 'cap = level + 拥有财富宝钻数'
    assert gs.back_layout.value == 7, '现值 6 → +1'

    # 可叠加:已持 2 颗再得 1 颗(库存 3)
    gs2 = _make_gs(env=_ENV, equips=[_EQUIP, _EQUIP, _EQUIP],
                   diamond_count=2, back_layout=7)
    on_diamond_acquired(gs2, _EQUIP)
    assert gs2.diamond_count.value == 3
    assert gs2.deploy_cap.value == 5 + 3, '拥有即算、可叠加(D-53 口径)'
    assert gs2.back_layout.value == 8

    # min 9 封顶(现值已 9 → 保持 9)
    gs3 = _make_gs(env=_ENV, equips=[_EQUIP], back_layout=9)
    on_diamond_acquired(gs3, _EQUIP)
    assert gs3.back_layout.value == 9, '后排格数上限 9'

    # back_layout None(未读)→ 机制基线 6 起算(种子后不可达防御)
    gs4 = _make_gs(env=_ENV, equips=[_EQUIP], back_layout=None)
    on_diamond_acquired(gs4, _EQUIP)
    assert gs4.back_layout.value == 7, 'None → 基线 6 起算 +1'


def test_callback_non_rich_diamond_early_return() -> None:
    """非财富宝钻早退(cap 加成语义只属财富宝钻;红/蓝钻无 cap 语义):
    三域零写(未写态保持 None,已写态保持原值)。"""
    gs = _make_gs(env=_ENV, equips=['红钻'])
    on_diamond_acquired(gs, '红钻')
    assert gs.diamond_count.value is None
    assert gs.deploy_cap.value is None
    assert gs.back_layout.value is None

    # 已写形态:值与来源都不动
    gs2 = _make_gs(env=_ENV, equips=['红钻'], diamond_count=2,
                   back_layout=9)
    on_diamond_acquired(gs2, '红钻')
    assert gs2.diamond_count.value == 2
    assert gs2.back_layout.value == 9
    assert gs2.deploy_cap.value is None


# ============================================================ 登记表构建校验


def test_env_streak_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """构建校验(import 即炸语义,注入 + 直调,沿 ENV_ORE_GRANTS 测试
    惯用法;2026-10-28 治理后只留漂移哨,阈值形随删):孤儿环境键 /
    装备名漂移;现表默认通过。"""
    # 现表(与卡面 id 104 同源):直调校验器零异常
    assert cw_investments.ENV_STREAK_GRANTS == {_ENV: (5, _EQUIP)}
    cw_investments._validate_env_streak_grants()

    # ① 孤儿环境键(版本更新改名/移除后静默失联 → 构建期炸)
    bad = dict(cw_investments.ENV_STREAK_GRANTS)
    bad['不存在环境'] = (5, _EQUIP)
    monkeypatch.setattr(cw_investments, 'ENV_STREAK_GRANTS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_streak_grants()
    monkeypatch.undo()

    # ② 装备名漂移(发放写出库存里不存在的名字 = 假身份)
    bad = dict(cw_investments.ENV_STREAK_GRANTS)
    bad[_ENV] = (5, '不存在的装备')
    monkeypatch.setattr(cw_investments, 'ENV_STREAK_GRANTS', bad)
    with pytest.raises(ValueError, match='装备名漂移'):
        cw_investments._validate_env_streak_grants()
    monkeypatch.undo()


# ============================================================ 种子与快照恢复


def test_seed_and_restore_type_roundtrip_no_regrant(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """种子底座(冷建空集)+ 快照→恢复类型不变(tuple-of-tuple)+
    恢复局(快照含 done)触发函数不再发——done 随快照存续,守卫天然
    闭合。"""
    seed_gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(seed_gs)
    assert seed_gs.env_grants_done.value == (), '冷建空底座'

    # 深井局发放完成态 → 快照 → 恢复
    gs = _make_gs(env=_ENV, equips=['永动机'])
    assert check_env_streak_grants(gs, 5, _SIG_HOOK) == _EQUIP
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    dv = restored.env_grants_done.value
    assert dv == ((_ENV, FIRST_STREAK_KEY),), 'done 值往返无损'
    assert isinstance(dv, tuple) and isinstance(dv[0], tuple), \
        'tuple-of-tuple 不漂移为 list-of-lists'
    assert restored.active_env.value == _ENV
    assert restored.equips.value == ['永动机', _EQUIP], '库存快照往返'

    # 恢复局再触发(6 连胜重查)不再发:零写
    calls = _record_writes(restored, monkeypatch)
    assert check_env_streak_grants(restored, 6, _SIG_HOOK) is None
    assert not calls, f'恢复局 done 在册零写: {calls}'


# ============================================================ live 接线
# (驱动 = 裸实例 + 全桩面走生产链路 _record_round_outcome,先例 =
#  test_settle 的覆盖度守卫测试。)

#: live 接线 sig 契约形态(design §2 契约:logic_hook 族,组号
#: 'battle-wait:env-grant',actor = op 类名;发放两笔 logic 写同组)。
_LIVE_SIG = ChannelSig(family='logic_hook', actor='CwScreenBattleWait',
                       group_id='battle-wait:env-grant')

_FRAME = object()   # 稳定帧哨兵(桩只验判定流,不断言内容)
_LIVE_OBS_SIG = ChannelSig(family='obs', actor='test-obs', mode='read')


def _make_op(test_context, monkeypatch,
             outcomes: list[RoundOutcome]) -> CwScreenBattleWait:
    """battle_wait 裸实例 + 全桩面(先例 = 覆盖度守卫测试);outcomes =
    逐次结算的观察桩按序出队——fake 结算路径携带的 streak_after 由这里
    真实给出,走真覆盖写端(_record_round_outcome 直调)。"""
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
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(bw_mod, 'read_phase_round',
                        lambda ctx, scr, round_caps=None: (1, 1))
    queue = list(outcomes)
    monkeypatch.setattr(bw_mod, 'read_round_outcome',
                        lambda ctx, scr, **k: queue.pop(0))
    return op


def _seed_env_and_inventory(gs) -> None:
    """深井局容器种子(观察写入口,与识别器同渠道):环境 + 库存一件。"""
    gs.observe(gs.active_env, _ENV, sig=_LIVE_OBS_SIG)
    gs.observe(gs.equips, ['永动机'], sig=_LIVE_OBS_SIG)


def _live_record_writes(gs, monkeypatch) -> list[tuple[str, str, ChannelSig]]:
    """包装容器三写入口记录 (通道, 字段名, sig) 写序(次序断言面;
    先例 = 本文件 _record_writes,扩 observe 通道)。"""
    writes: list[tuple[str, str, ChannelSig]] = []

    def _wrap(method, channel):
        def rec(target, value, **kw):
            writes.append((channel, gs._field_name(target), kw.get('sig')))
            return method(target, value, **kw)
        return rec

    monkeypatch.setattr(gs, 'observe', _wrap(gs.observe, 'observe'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return writes


def _idx(writes: list[tuple[str, str, ChannelSig]],
         channel: str, field: str) -> int:
    """指定 (通道, 字段) 首次写行下标(次序断言辅助)。"""
    return next(i for i, w in enumerate(writes)
                if w[0] == channel and w[1] == field)


def _outcome(streak: int | None) -> RoundOutcome:
    """胜局结算观察桩(streak = 结算屏「连胜×N」带方向真值;
    None = 收口行不发 streak 真值口径)。"""
    return RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                        comp_tag='c', hp_after=3, hp_confidence=1.0,
                        killed=False, streak=streak)


def test_env_grant_fires_after_settlement_cover_in_order(
        test_context, monkeypatch) -> None:
    """接线点次序真测试:5 连胜结算走真覆盖写端(streak 真值落账为可断言
    前置态)后,条件发放紧随触发——写序 = streak 观察(覆盖写端)→
    equips 随机态写(发放)→ done 登记;发放两笔同组 sig = live 契约
    形态。"""
    op = _make_op(test_context, monkeypatch, [_outcome(5)])
    gs = game_state_of(test_context.cw_match.session)
    _seed_env_and_inventory(gs)
    writes = _live_record_writes(gs, monkeypatch)

    op._record_round_outcome(_FRAME)

    # 防假绿锚:fake 结算路径真实携带 streak_after 且走了真覆盖写端
    assert gs.streak.value == 5 and gs.streak.source == 'observation', \
        '结算覆盖写端必须真实落账(前置态缺失 = 断言恒绿假形态)'
    # 发放真发生:库存尾部随机态追加 + done 首次登记
    assert gs.equips.value == ['永动机', _EQUIP]
    assert gs.equips.source == 'logic_rand'
    assert gs.env_grants_done.value == ((_ENV, 'first_streak'),)
    # 次序真测试:覆盖写端 streak 观察严格先于发放两笔 logic 写
    assert _idx(writes, 'observe', 'streak') \
        < _idx(writes, 'rand', 'equips') \
        < _idx(writes, 'logic', 'env_grants_done'), \
        f'接线次序漂移(发放必须在结算覆盖后): {writes}'
    assert writes[_idx(writes, 'rand', 'equips')][2] == _LIVE_SIG
    assert writes[_idx(writes, 'logic', 'env_grants_done')][2] == _LIVE_SIG


def test_wrong_guess_healed_by_whole_table_observation(
        test_context, monkeypatch) -> None:
    """随机态发放 + equips 观察整表覆盖纠偏(猜错自愈):发放猜值与
    下一备战帧实读表不同 → 观察赢;done 在册使 6 连胜重查零重发 =
    零持续污染。"""
    op = _make_op(test_context, monkeypatch, [_outcome(5), _outcome(6)])
    gs = game_state_of(test_context.cw_match.session)
    _seed_env_and_inventory(gs)
    writes = _live_record_writes(gs, monkeypatch)

    # 第一结算:发放,猜值 = 库存尾部追加(落位未知 → 猜错是设计内形态)
    op._record_round_outcome(_FRAME)
    assert gs.equips.value == ['永动机', _EQUIP]
    # 下一备战帧:owned_equips 识别器整表覆盖,实读表与猜值不同(宝钻
    # 实际落位在库首;观察写入口与识别器同渠道)
    reality = [_EQUIP, '永动机']
    gs.observe(gs.equips, reality, sig=_LIVE_OBS_SIG)
    assert gs.equips.value == reality
    assert gs.equips.source == 'observation', '观察赢(纠偏)'

    # 第二结算(6 连胜重查):done 在册 → 零发放写,观察表不被二次污染
    writes.clear()
    op._record_round_outcome(_FRAME)
    assert gs.streak.value == 6, '第二结算覆盖写端照常落账(路径存活)'
    assert gs.equips.value == reality, '零持续污染(观察值不被猜值回写)'
    assert gs.equips.source == 'observation'
    assert gs.env_grants_done.value == ((_ENV, 'first_streak'),)
    assert not [w for w in writes if w[1] in ('equips', 'env_grants_done')], \
        f'done 在册零发放写: {writes}'


def test_streak_none_settlement_skips_env_grant(
        test_context, monkeypatch) -> None:
    """streak_after None 的结算不调触发检查(口径与覆盖写端 None 跳过
    streak 观察一致):触发函数零调用 + 零发放写。"""
    op = _make_op(test_context, monkeypatch, [_outcome(None)])
    gs = game_state_of(test_context.cw_match.session)
    _seed_env_and_inventory(gs)
    writes = _live_record_writes(gs, monkeypatch)
    # 触发检查调用记录(双点位打桩:kernel 模块属性 = 现函数级 import
    # 调用时的解析点;op 模块属性 = 改模块级 import 后的解析点)
    calls: list[tuple] = []

    def _spy(_gs, streak_after, _sig):
        calls.append((streak_after, _sig))
        return None

    monkeypatch.setattr(grants_mod, 'check_env_streak_grants', _spy)
    monkeypatch.setattr(bw_mod, 'check_env_streak_grants', _spy,
                        raising=False)
    streak_before = gs.streak.value

    op._record_round_outcome(_FRAME)

    assert calls == [], f'streak_after None 不调触发检查: {calls}'
    assert gs.streak.value == streak_before, \
        '覆盖写端 None 跳过 streak 观察(口径基线)'
    assert gs.equips.value == ['永动机'], '零发放写'
    assert gs.env_grants_done.value == (), '零 done 登记'
    assert not [w for w in writes if w[1] in ('equips', 'env_grants_done')], \
        f'None 结算零发放写: {writes}'


# ============================================================ 刷新次数条件发放(T-7 二手市场)

_R_ENV = '二手市场'
_R_EQUIP = '员工投影仪'

_R_SIG_OBS = ChannelSig(family='obs', actor='CwEnvRefreshGrantsTest')
_R_SIG_LOGIC = ChannelSig(family='logic_action',
                          actor='CwEnvRefreshGrantsTest', mode='compute')


def _r_make_gs(*, env: str | None = None,
               gold: int | None = None,
               equips: list[str] | None = None,
               done: tuple[tuple[str, str], ...] | None = None) -> GameState:
    """刷新发放测试容器(观察面按参组装,None = 保持未写形态;登记域经
    logic 直写播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_R_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_R_SIG_OBS)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       sig=_R_SIG_LOGIC)
    if done is not None:
        gs.write_logic(gs.env_grants_done, tuple(done), produced_by='test-seed',
                       sig=_R_SIG_LOGIC)
    return gs


def _count_refreshes(gs: GameState, n: int, *, free: bool = False) -> None:
    """经单一入账口 record_refresh 推进计数到 n(与生产同口,禁直改属性)。"""
    for _ in range(n):
        gs.effects.record_refresh(free=free)


def test_env_refresh_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """构建校验(import 即炸语义,注入 + 直调;2026-10-28 治理后只留
    漂移哨,计数键闭集/值形/双源/跨锁随删):孤儿环境键/装备名漂移;
    现表双行全等(加行漏改本测试即红灯)。"""
    # 现表(与卡面 id 106/120 同源):双行全等 + 直调校验器零异常
    assert cw_investments.ENV_REFRESH_GRANTS == {
        _R_ENV: (cw_investments.CounterKey.REFRESH_TOTAL, 20, 30, _R_EQUIP),
        '长线利好': (cw_investments.CounterKey.REFRESH_PAID, 30, 20, None)}
    cw_investments._validate_env_refresh_grants()

    # ① 孤儿环境键(版本更新改名/移除后静默失联 → 构建期炸)
    bad = dict(cw_investments.ENV_REFRESH_GRANTS)
    bad['不存在环境'] = (cw_investments.CounterKey.REFRESH_TOTAL, 20, 30, None)
    monkeypatch.setattr(cw_investments, 'ENV_REFRESH_GRANTS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_refresh_grants()
    monkeypatch.undo()

    # ② 装备名漂移(发放写出库存里不存在的名字 = 假身份)
    bad = dict(cw_investments.ENV_REFRESH_GRANTS)
    bad[_R_ENV] = (cw_investments.CounterKey.REFRESH_TOTAL, 20, 30, '不存在的装备')
    monkeypatch.setattr(cw_investments, 'ENV_REFRESH_GRANTS', bad)
    with pytest.raises(ValueError, match='装备名漂移'):
        cw_investments._validate_env_refresh_grants()
    monkeypatch.undo()


def test_refresh_condition_matrix_short_circuits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """刷新发放条件矩阵短路:env 空链(None/'')/不在册/已 done/未达阈 →
    全部 None 且零写。"""
    cases: list[tuple[str, GameState]] = [
        ('env 未选择(None 形态)', _r_make_gs(gold=100, equips=[])),
        ('env 空链(开局种子形态)', _r_make_gs(env='', gold=100, equips=[])),
        ('env 不在册', _r_make_gs(env='蓝海', gold=100, equips=[])),
    ]
    for label, gs in cases:
        _count_refreshes(gs, 20)
        calls = _record_writes(gs, monkeypatch)
        assert check_env_refresh_grants(gs, _R_SIG_LOGIC) is None, label
        assert not calls, f'{label} 零写: {calls}'

    # 已 done 在册(幂等守卫,第 21 刷重查不重发)
    gs = _r_make_gs(env=_R_ENV, gold=100, equips=[],
                    done=((_R_ENV, REFRESH_THRESHOLD_KEY),))
    _count_refreshes(gs, 20)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) is None
    assert not calls, 'done 在册零写'

    # 未达阈(19 < 20)
    gs = _r_make_gs(env=_R_ENV, gold=100, equips=[])
    _count_refreshes(gs, 19)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) is None
    assert not calls, '未达阈零写'


def test_refresh_done_none_treated_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """done 域 None(从未写形态)→ 视为空防御照发(直构容器域未写,
    守卫 membership 判定不因 None 崩/不误判已发)。"""
    gs = _r_make_gs(env=_R_ENV, gold=100, equips=[])
    _count_refreshes(gs, 20)
    assert gs.env_grants_done.value is None
    calls = _record_writes(gs, monkeypatch)

    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) == _R_EQUIP
    assert [c[0] for c in calls] == ['gold', 'equips', 'env_grants_done'], \
        f'done None 防御照发三写: {calls}'


def test_refresh_gold_unobserved_no_done_then_retry_after_feed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """gold 缺读(从未观察)→ 宁缺勿造:零写、不标 done,喂值后下次
    刷新自动重查(重试语义;刷新高频,延迟以秒计)。"""
    gs = _r_make_gs(env=_R_ENV, equips=['永动机'])   # gold 未写 = None
    _count_refreshes(gs, 20)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) is None
    assert not calls, f'缺读零写: {calls}'
    assert gs.env_grants_done.value is None, '缺读不标 done'

    # 喂金观察后重查 → 发放成功(gold 50 + 30 = 80)
    gs.observe(gs.gold, 50, sig=_R_SIG_OBS)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) == _R_EQUIP
    assert gs.gold.value == 80
    assert [c[0] for c in calls] == ['gold', 'equips', 'env_grants_done']


def test_refresh_equips_unobserved_withhold_no_half_grant(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """equips 缺读 → 整体缓发禁半发放(金已入账装备永久漏发 = 半发放,
    零写不标 done;库存到位后重查发放)。"""
    gs = _r_make_gs(env=_R_ENV, gold=100)   # equips 未写 = None
    _count_refreshes(gs, 20)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) is None
    assert not calls, f'缓发零写: {calls}'
    assert gs.gold.value == 100, '缓发不动金'
    assert gs.env_grants_done.value is None, '缓发不标 done'

    # 库存到位后重查 → 发放成功
    gs.write_logic(gs.equips, ['永动机'], produced_by='test-seed',
                   sig=_R_SIG_LOGIC)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) == _R_EQUIP
    assert [c[0] for c in calls] == ['gold', 'equips', 'env_grants_done']


def test_refresh_grant_three_writes_same_evidence_adjacent(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """发放三笔相邻写:gold +30 走 write_logic / equips 尾追走
    write_logic_rand / done 追加走 write_logic,三笔同 evidence
    env_grant#二手市场#refresh20 同 sig 相邻(金在前,done 收尾)。"""
    gs = _r_make_gs(env=_R_ENV, gold=100, equips=['永动机', '高周波电锯'])
    _count_refreshes(gs, 20)
    calls = _record_writes(gs, monkeypatch)

    granted = check_env_refresh_grants(gs, _R_SIG_LOGIC)

    assert granted == _R_EQUIP, '返回被发装备名(仅日志面消费)'
    assert gs.gold.value == 130, '金 100 + 30'
    assert gs.gold.source == 'logic', '金 = 登记事实直写'
    assert gs.equips.value == ['永动机', '高周波电锯', _R_EQUIP], \
        '库存尾部追加(随机态指落位未知,追加位置确定)'
    assert gs.equips.source == 'logic_rand', '装备 = 随机态通道'
    assert gs.env_grants_done.value == ((_R_ENV, REFRESH_THRESHOLD_KEY),)
    assert calls == [
        ('gold', 'env_grant#二手市场#refresh20', 'logic', _R_SIG_LOGIC),
        ('equips', 'env_grant#二手市场#refresh20', 'rand', _R_SIG_LOGIC),
        ('env_grants_done', 'env_grant#二手市场#refresh20', 'logic',
         _R_SIG_LOGIC),
    ], f'三笔同 evidence 同 sig 相邻: {calls}'


def test_refresh_trigger_rejects_obs_sig() -> None:
    """sig 单形态契约:obs 族进触发函数即炸渠道族校验(首笔金收入分支即拦;
    唯一调用方 = 上报函数 _grp_sig,logic_action 族,天然满足)。"""
    gs = _r_make_gs(env=_R_ENV, gold=100, equips=[])
    _count_refreshes(gs, 20)
    with pytest.raises(ValueError, match='渠道族'):
        check_env_refresh_grants(gs, _R_SIG_OBS)
    assert gs.gold.value == 100, '炸错前置零写'
    assert gs.env_grants_done.value is None


def test_total_domain_counts_mixed_free_paid_frames(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """计数域测试(用户裁定① = 全量):免费帧与付费帧混排经
    record_refresh 计到 20 → 发放(免费帧若不入账,paid 域恒不可达
    本测试)。"""
    gs = _r_make_gs(env=_R_ENV, gold=100, equips=[])
    for i in range(20):
        gs.effects.record_refresh(free=(i % 2 == 0))   # 免费/付费各 10 帧
    assert gs.effects.refresh_total == 20
    assert gs.effects.refresh_paid == 10, '混排有效:免费帧不进 paid'

    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) == _R_EQUIP, \
        '全量域:免费帧计入 20 次阈值'
    assert [c[0] for c in calls] == ['gold', 'equips', 'env_grants_done']


def test_exactly_once_in_21_refresh_loop(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """一次性(用户裁定②):kernel 级 21 次刷新循环,第 20 次恰发
    一次,第 21 次零新增写(done 封账,40 刷不再发)。"""
    gs = _r_make_gs(env=_R_ENV, gold=100, equips=['永动机'])
    calls = _record_writes(gs, monkeypatch)
    grants: list[str | None] = []
    for _ in range(21):
        gs.effects.record_refresh(free=False)
        grants.append(check_env_refresh_grants(gs, _R_SIG_LOGIC))

    assert grants.count(_R_EQUIP) == 1, f'21 刷恰发一次: {grants}'
    assert grants[19] == _R_EQUIP, '第 20 次发放'
    assert grants[20] is None, '第 21 次 done 在册不再发'
    assert gs.env_grants_done.value == ((_R_ENV, REFRESH_THRESHOLD_KEY),)
    assert len([c for c in calls if c[0] == 'env_grants_done']) == 1, \
        'done 只登记一次'
    assert gs.gold.value == 130, '金只 +30 一次'


def test_report_wiring_grants_on_threshold() -> None:
    """接线存在性:上报函数尾部触发检查在在册环境达阈时发放落地
    (集成 1 条;矩阵断言归 kernel 级,不在此层重复)。窗口内 = 刷费
    扣金分支(容器直读,T-21 分支 3:免费未观察保守按付费,基价 2)+ 发放
    三笔;level 不写 = 随机态采样分支跳写。"""
    gs = _r_make_gs(env=_R_ENV, gold=100, equips=['永动机'])
    _count_refreshes(gs, 20)

    outcome = report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _R_SIG_LOGIC)

    assert outcome.applied is True
    assert gs.gold.value == 128, \
        '第 21 刷扣基价 2(容器直读)+ 发放分支金 +30 落地(100−2+30)'
    assert gs.equips.value == ['永动机', _R_EQUIP], '发放分支装备尾追落地'
    assert gs.env_grants_done.value == ((_R_ENV, REFRESH_THRESHOLD_KEY),), \
        '发放分支 done 封账落地'
    assert gs.effects.refresh_total == 21, '计数分支先行入账(第 21 刷)'


# ============================================================ 长线利好(T-21 付费域 + 金-only)

_L_ENV = '长线利好'


def _l_make_gs(*, gold: int | None = None) -> GameState:
    """长线利好测试容器(金-only 卡:equips 恒保持未观察形态——
    登记装备入账分支 None,发放路径不应有任何 equips 承载要求)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.active_env, _L_ENV, sig=_R_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_R_SIG_OBS)
    return gs


def test_paid_domain_counts_only_paid_frames(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """付费域语义(T-21 锁 2;desc「花费金币」限定词直读,防回退全量域):
    免费帧混排不进阈值——free×29 + paid×1(refresh_total=30 而
    refresh_paid=1)零发放;付费累计 29 零发放;第 30 次付费发放。"""
    gs = _l_make_gs(gold=100)
    for i in range(30):
        gs.effects.record_refresh(free=(i < 29))
    assert gs.effects.refresh_total == 30
    assert gs.effects.refresh_paid == 1, '混排有效:免费帧不进 paid'
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) is None, \
        '付费域:29 免费 + 1 付费不达阈'
    assert not calls, f'零发放零写: {calls}'

    gs2 = _l_make_gs(gold=100)
    _count_refreshes(gs2, 29, free=False)
    calls2 = _record_writes(gs2, monkeypatch)
    assert check_env_refresh_grants(gs2, _R_SIG_LOGIC) is None, '付费 29 未达阈'
    assert not calls2, f'零发放零写: {calls2}'

    gs2.effects.record_refresh(free=False)
    calls3 = _record_writes(gs2, monkeypatch)
    assert check_env_refresh_grants(gs2, _R_SIG_LOGIC) is None, \
        '返回值 = 被发装备名,金-only 发放恒 None'
    assert [c[0] for c in calls3] == ['gold', 'env_grants_done'], \
        '第 30 次付费发放(金-only 两笔)'


def test_gold_only_grant_two_writes_adjacent(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """金-only 形状(T-21 锁 3):发放恰两笔(gold +20 走 write_logic、
    done 追加走 write_logic)同 evidence env_grant#长线利好#refresh30
    相邻,零 equips 笔;equips 未观察也不缓发(装备入账分支 None 无承载要求,
    与二手市场装备入账分支形态互照)。"""
    gs = _l_make_gs(gold=100)
    _count_refreshes(gs, 30, free=False)
    calls = _record_writes(gs, monkeypatch)

    granted = check_env_refresh_grants(gs, _R_SIG_LOGIC)

    assert granted is None, '返回值 = 被发装备名,金-only 恒 None(仅日志面)'
    assert gs.gold.value == 120, '金 100 + 20'
    assert gs.gold.source == 'logic', '金 = 登记事实直写'
    assert gs.equips.value is None, '装备入账分支 None:零 equips 笔(保持未观察)'
    assert gs.env_grants_done.value == ((_L_ENV, REFRESH_THRESHOLD_KEY),)
    assert calls == [
        ('gold', 'env_grant#长线利好#refresh30', 'logic', _R_SIG_LOGIC),
        ('env_grants_done', 'env_grant#长线利好#refresh30', 'logic',
         _R_SIG_LOGIC),
    ], f'金-only 两笔同 evidence 同 sig 相邻: {calls}'


def test_paid_domain_exactly_once_in_31_refresh_loop(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """一次性(T-21 锁 4):31 次付费刷新循环,第 30 次恰发一次,第 31
    次 done 封账零新增写(60 刷不再发)。"""
    gs = _l_make_gs(gold=100)
    calls = _record_writes(gs, monkeypatch)
    granted_at: list[int] = []
    for i in range(31):
        gs.effects.record_refresh(free=False)
        before = gs.env_grants_done.value
        check_env_refresh_grants(gs, _R_SIG_LOGIC)
        if gs.env_grants_done.value != before:
            granted_at.append(i)

    assert granted_at == [29], f'第 30 次(下标 29)恰发一次: {granted_at}'
    assert gs.env_grants_done.value == ((_L_ENV, REFRESH_THRESHOLD_KEY),)
    assert len([c for c in calls if c[0] == 'env_grants_done']) == 1, \
        'done 只登记一次'
    assert gs.gold.value == 120, '金只 +20 一次'


def test_paid_grant_gold_unobserved_withhold_then_retry(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """缓发重试(T-21 锁 5):gold 缺读 → 零写不标 done(宁缺勿造,
    刷新高频下次自动重查),喂值后下次调用发放成功(金-only 无装备入账分支,
    无第二缓发面)。"""
    gs = _l_make_gs()   # gold 未写 = None
    _count_refreshes(gs, 30, free=False)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) is None
    assert not calls, f'缺读零写: {calls}'
    assert gs.env_grants_done.value is None, '缺读不标 done'

    gs.observe(gs.gold, 50, sig=_R_SIG_OBS)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _R_SIG_LOGIC) is None
    assert gs.gold.value == 70, '喂值后发放成功(50 + 20)'
    assert [c[0] for c in calls] == ['gold', 'env_grants_done']


def test_report_wiring_paid_grant_price_base_at_threshold() -> None:
    """接线存在性 + 30 次边界价基(T-21 锁 6/锁 11 前半):第 30 次付费
    刷新动作窗内,上报函数尾部触发检查发放落地;当窗刷费扣旧价 2
    (付完才满 30,容器价基假设 desc 直读)+ 发放 +20 = 净 +18。"""
    gs = _l_make_gs(gold=100)
    gs.observe(gs.shop_refresh_cost, 2, sig=_R_SIG_OBS)
    _count_refreshes(gs, 29, free=False)

    outcome = report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _R_SIG_LOGIC)

    assert outcome.applied is True
    assert gs.gold.value == 118, '第 30 刷扣旧价 2 且同窗 +20(净 +18)'
    assert gs.env_grants_done.value == ((_L_ENV, REFRESH_THRESHOLD_KEY),), \
        '发放分支 done 封账落地'
    assert gs.effects.refresh_paid == 30, '付费计数分支先行入账'


def test_report_refresh_fee_new_price_after_threshold() -> None:
    """31 刷新价(T-21 锁 11 后半):第 30 刷后新 visit 入口观察已采
    新价 1 → 第 31 刷扣 1(降价生效于付完 30 次之后的下一次动作;
    实机价基对账义务 = T-21 §2.4 第 7 项,失配走停机语义)。"""
    gs = _l_make_gs(gold=118)
    gs.observe(gs.shop_refresh_cost, 1, sig=_R_SIG_OBS)
    gs.write_logic(gs.env_grants_done, ((_L_ENV, REFRESH_THRESHOLD_KEY),),
                   produced_by='test-seed', sig=_R_SIG_LOGIC)

    outcome = report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=1), _R_SIG_LOGIC)

    assert outcome.applied is True
    assert gs.gold.value == 117, '第 31 刷扣新价 1'
    assert gs.effects.refresh_total == 1
