"""环境条件发放锁(迭代 2026-10-10-env-conditional-grants 3.1;详设
details/env-conditional-grant.md §1–§4)。

锁面:
- 触发条件矩阵七序短路(env 空链/不在册/连败方向/低于阈值/已发 done
  含 None 视为空防御/equips 缺读不标 done 下结算重试/达标发放返回名);
- 随机态发放写行:equips 追加走 write_logic_rand(evidence
  ``env_grant#<env>#streak<阈值>``),done 追加走 write_logic 同
  evidence 同 sig 相邻两笔;恢复后无 rng(随机态指认知通道,追加位置
  尾部确定);
- sig 单形态契约:obs 族进触发函数即炸渠道族校验(禁 obs_sig);
- 回调三写:diamond_count+1 / deploy_cap = level + equips 现值中财富
  宝钻计数(拥有即算可叠加)/ back_layout = min(9, 现值+1,None →
  基线 6 起算);非财富宝钻早退零写;
- 登记表三条构建校验(孤儿环境键/装备名漂移/阈值形,注入 + 直调
  import 即炸语义,沿 ENV_ORE_GRANTS 测试惯用法);
- 种子底座(冷建空集)+ 快照→恢复类型不变(tuple-of-tuple)+ 恢复局
  含 done 触发函数不再发。

live/sim 接线(3.2/3.3)与 supply 采纳边界不在此。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_env_grants import (
    FIRST_STREAK_KEY,
    check_env_streak_grants,
    on_diamond_acquired,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    restore_state_snapshot,
    seed_opening_state,
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
    """三条构建校验(import 即炸语义,注入 + 直调,沿 ENV_ORE_GRANTS
    测试惯用法):孤儿环境键 / 装备名漂移 / 阈值形;现表默认通过。"""
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

    # ③ 阈值形(≤0 = 条件永真,一次性守卫失真)
    for bad_threshold in (0, -1):
        bad = dict(cw_investments.ENV_STREAK_GRANTS)
        bad[_ENV] = (bad_threshold, _EQUIP)
        monkeypatch.setattr(cw_investments, 'ENV_STREAK_GRANTS', bad)
        with pytest.raises(ValueError, match='阈值形'):
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
