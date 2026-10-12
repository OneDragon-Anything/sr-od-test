"""环境条件发放 live 接线锁(迭代 2026-10-10-env-conditional-grants 3.2;
判据面 = 该迭代 landing 3.2 节)。

锁面:
- 接线点次序真锁:结算覆盖写端(apply_settlement_cover,streak 真值
  observe)之后才触发条件发放检查——fake 结算路径真实携带 streak_after
  且走真覆盖写端(真函数,streak 落账作可断言前置态),防「fake 不写
  前置状态、断言恒绿」的假绿形态(姊妹迭代实证);
- 随机态发放 + equips 观察整表覆盖纠偏:猜错(发放猜值与实读表不同)
  时观察赢;done 在册使下个结算零重发 = 零持续污染;
- streak_after None 的结算不调触发检查(口径与覆盖写端 None 跳过
  streak 观察一致)。

kernel 条件矩阵本体 = test_cw_env_grants.py(3.1);sim 接线 = 3.3。
驱动 = 裸实例 + 全桩面走生产链路 _record_round_outcome(先例 =
test_cw_settle_obs_coverage 的覆盖度守卫锁)。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel import cw_env_grants as grants_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
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

_ENV = '深井角斗场'
_EQUIP = '财富宝钻'

#: live 接线 sig 契约形态(design §2 契约:logic_hook 族,组号
#: 'battle-wait:env-grant',actor = op 类名;发放两笔 logic 写同组)。
_LIVE_SIG = ChannelSig(family='logic_hook', actor='CwScreenBattleWait',
                       group_id='battle-wait:env-grant')

_FRAME = object()   # 稳定帧哨兵(桩只验判定流,不断言内容)
_SIG_OBS = ChannelSig(family='obs', actor='test-obs', mode='read')


def _make_op(test_context, monkeypatch,
             outcomes: list[RoundOutcome]) -> CwScreenBattleWait:
    """battle_wait 裸实例 + 全桩面(先例 = 覆盖度守卫锁);outcomes =
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
    gs.observe(gs.active_env, _ENV, sig=_SIG_OBS)
    gs.observe(gs.equips, ['永动机'], sig=_SIG_OBS)


def _record_writes(gs, monkeypatch) -> list[tuple[str, str, ChannelSig]]:
    """包装容器三写入口记录 (通道, 字段名, sig) 写序(次序断言面;
    先例 = test_cw_env_grants._record_writes,扩 observe 通道)。"""
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
    """接线点次序真锁:5 连胜结算走真覆盖写端(streak 真值落账为可断言
    前置态)后,条件发放紧随触发——写序 = streak 观察(覆盖写端)→
    equips 随机态写(发放)→ done 登记;发放两笔同组 sig = live 契约
    形态。"""
    op = _make_op(test_context, monkeypatch, [_outcome(5)])
    gs = game_state_of(test_context.cw_match.session)
    _seed_env_and_inventory(gs)
    writes = _record_writes(gs, monkeypatch)

    op._record_round_outcome(_FRAME)

    # 防假绿锚:fake 结算路径真实携带 streak_after 且走了真覆盖写端
    assert gs.streak.value == 5 and gs.streak.source == 'observation', \
        '结算覆盖写端必须真实落账(前置态缺失 = 断言恒绿假形态)'
    # 发放真发生:库存尾部随机态追加 + done 首次登记
    assert gs.equips.value == ['永动机', _EQUIP]
    assert gs.equips.source == 'logic_rand'
    assert gs.env_grants_done.value == ((_ENV, 'first_streak'),)
    # 次序真锁:覆盖写端 streak 观察严格先于发放两笔 logic 写
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
    writes = _record_writes(gs, monkeypatch)

    # 第一结算:发放,猜值 = 库存尾部追加(落位未知 → 猜错是设计内形态)
    op._record_round_outcome(_FRAME)
    assert gs.equips.value == ['永动机', _EQUIP]
    # 下一备战帧:owned_equips 识别器整表覆盖,实读表与猜值不同(宝钻
    # 实际落位在库首;观察写入口与识别器同渠道)
    reality = [_EQUIP, '永动机']
    gs.observe(gs.equips, reality, sig=_SIG_OBS)
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
    writes = _record_writes(gs, monkeypatch)
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
