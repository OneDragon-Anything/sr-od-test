"""环境刷新次数条件发放锁(T-7 二手市场;设计 =
.debug/progress/2026-09-23-invest-effects-calc/designs/T-7-ershichang.md §2,
对抗修补 C4 值形锁面并入)。

锁面:
- 登记表五查构建校验(import 即炸语义,注入 + 直调,沿 ENV_STREAK_GRANTS
  测试惯用法):孤儿环境键/计数键闭集外/值形(阈值 0 与金 0 两例,C4)/
  装备名漂移/双源失同步(ENV_ECONOMY.gold_after_refreshes 单侧改数);
- 触发条件矩阵七序短路(env 空链/不在册/已 done/done None 视为空防御/
  未达阈/gold 缺读不标 done 喂值后重试成功/equips 缺读整体缓发禁半发放);
- 达标发放三笔相邻写(gold +30 走 write_logic / equips 尾追员工投影仪走
  write_logic_rand / done 追加走 write_logic),同 evidence
  ``env_grant#<env>#refresh<阈值>`` 同 sig 相邻;
- 计数域锁(用户裁定①):免费帧与付费帧混排经 record_refresh 计到 20 →
  发放(锁 REFRESH_TOTAL 全量域;免费帧若不入账则 paid 域不可达本锁);
- 一次性(用户裁定②):kernel 级 21 次循环第 20 次恰发一次,第 21 次
  零新增写(done 封账);
- sig 单形态契约:obs 族进触发函数即炸渠道族校验(唯一调用方 = 上报函数
  _grp_sig,logic_action 族,天然满足);
- 接线存在性:report_action_refresh_shop_param 尾部触发在在册环境达阈时
  发放落地(集成 1 条,矩阵断言不在此层重复)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_refresh_shop_param,
)
from sr_od.application.currency_war.kernel.cw_env_grants import (
    REFRESH_THRESHOLD_KEY,
    check_env_refresh_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionRefreshShopParam,
)

_ENV = '二手市场'
_EQUIP = '员工投影仪'

_SIG_OBS = ChannelSig(family='obs', actor='CwEnvRefreshGrantsTest')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='CwEnvRefreshGrantsTest',
                        mode='compute')


def _make_gs(*, env: str | None = None,
             gold: int | None = None,
             equips: list[str] | None = None,
             done: tuple[tuple[str, str], ...] | None = None) -> GameState:
    """观察面按参组装(None = 保持未写形态;登记域经 logic 直写播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       sig=_SIG_LOGIC)
    if done is not None:
        gs.write_logic(gs.env_grants_done, tuple(done), produced_by='test-seed',
                       sig=_SIG_LOGIC)
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


def _count_refreshes(gs: GameState, n: int, *, free: bool = False) -> None:
    """经单一入账口 record_refresh 推进计数到 n(与生产同口,禁直改属性)。"""
    for _ in range(n):
        gs.effects.record_refresh(free=free)


# ============================================================ 登记表构建校验


def test_env_refresh_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """五查构建校验(import 即炸语义,注入 + 直调):孤儿环境键/计数键
    闭集外/值形(阈值 0 与金 0 两例,C4)/装备名漂移/双源失同步;
    现表默认通过。"""
    # 现表(与卡面 id 106 同源):直调校验器零异常
    assert cw_investments.ENV_REFRESH_GRANTS == {
        _ENV: (cw_investments.CounterKey.REFRESH_TOTAL, 20, 30, _EQUIP)}
    cw_investments._validate_env_refresh_grants()

    # ① 孤儿环境键(版本更新改名/移除后静默失联 → 构建期炸)
    bad = dict(cw_investments.ENV_REFRESH_GRANTS)
    bad['不存在环境'] = (cw_investments.CounterKey.REFRESH_TOTAL, 20, 30, None)
    monkeypatch.setattr(cw_investments, 'ENV_REFRESH_GRANTS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_refresh_grants()
    monkeypatch.undo()

    # ② 计数键闭集外(计数读取按键分支,闭集外无读口)
    bad = dict(cw_investments.ENV_REFRESH_GRANTS)
    bad[_ENV] = ('no_such_counter', 20, 30, None)
    monkeypatch.setattr(cw_investments, 'ENV_REFRESH_GRANTS', bad)
    with pytest.raises(ValueError, match='计数键闭集外'):
        cw_investments._validate_env_refresh_grants()
    monkeypatch.undo()

    # ③ 值形两例(C4):阈值 0(条件永真,一次性守卫失真)/ 金 0
    for _label, threshold, gold in (('阈值0', 0, 30), ('金0', 20, 0)):
        bad = dict(cw_investments.ENV_REFRESH_GRANTS)
        bad[_ENV] = (cw_investments.CounterKey.REFRESH_TOTAL, threshold, gold,
                     None)
        monkeypatch.setattr(cw_investments, 'ENV_REFRESH_GRANTS', bad)
        with pytest.raises(ValueError, match='值形'):
            cw_investments._validate_env_refresh_grants()
        monkeypatch.undo()

    # ④ 装备名漂移(发放写出库存里不存在的名字 = 假身份)
    bad = dict(cw_investments.ENV_REFRESH_GRANTS)
    bad[_ENV] = (cw_investments.CounterKey.REFRESH_TOTAL, 20, 30, '不存在的装备')
    monkeypatch.setattr(cw_investments, 'ENV_REFRESH_GRANTS', bad)
    with pytest.raises(ValueError, match='装备名漂移'):
        cw_investments._validate_env_refresh_grants()
    monkeypatch.undo()

    # ⑤ 双源失同步(估值面单侧改数:世界面与估值面同出卡面)
    monkeypatch.setitem(
        cw_investments.ENV_ECONOMY, _ENV,
        cw_investments.EnvEconomyEffect(gold_after_refreshes=(19, 30)))
    with pytest.raises(ValueError, match='双源失同步'):
        cw_investments._validate_env_refresh_grants()
    monkeypatch.undo()


# ============================================================ 触发条件矩阵


def test_condition_matrix_short_circuits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """条件矩阵前四序短路:env 空链(None/'')/不在册/已 done →
    全部 None 且零写。"""
    cases: list[tuple[str, GameState]] = [
        ('env 未选择(None 形态)', _make_gs(gold=100, equips=[])),
        ('env 空链(开局种子形态)', _make_gs(env='', gold=100, equips=[])),
        ('env 不在册', _make_gs(env='蓝海', gold=100, equips=[])),
    ]
    for label, gs in cases:
        _count_refreshes(gs, 20)
        calls = _record_writes(gs, monkeypatch)
        assert check_env_refresh_grants(gs, _SIG_LOGIC) is None, label
        assert not calls, f'{label} 零写: {calls}'

    # 已 done 在册(幂等守卫,第 21 刷重查不重发)
    gs = _make_gs(env=_ENV, gold=100, equips=[],
                  done=((_ENV, REFRESH_THRESHOLD_KEY),))
    _count_refreshes(gs, 20)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _SIG_LOGIC) is None
    assert not calls, 'done 在册零写'

    # 未达阈(19 < 20)
    gs = _make_gs(env=_ENV, gold=100, equips=[])
    _count_refreshes(gs, 19)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _SIG_LOGIC) is None
    assert not calls, '未达阈零写'


def test_done_none_treated_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """done 域 None(从未写形态)→ 视为空防御照发(直构容器域未写,
    守卫 membership 判定不因 None 崩/不误判已发)。"""
    gs = _make_gs(env=_ENV, gold=100, equips=[])
    _count_refreshes(gs, 20)
    assert gs.env_grants_done.value is None
    calls = _record_writes(gs, monkeypatch)

    assert check_env_refresh_grants(gs, _SIG_LOGIC) == _EQUIP
    assert [c[0] for c in calls] == ['gold', 'equips', 'env_grants_done'], \
        f'done None 防御照发三写: {calls}'


def test_gold_unobserved_no_done_then_retry_after_feed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """gold 缺读(从未观察)→ 宁缺勿造:零写、不标 done,喂值后下次
    刷新自动重查(重试语义;刷新高频,延迟以秒计)。"""
    gs = _make_gs(env=_ENV, equips=['永动机'])   # gold 未写 = None
    _count_refreshes(gs, 20)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _SIG_LOGIC) is None
    assert not calls, f'缺读零写: {calls}'
    assert gs.env_grants_done.value is None, '缺读不标 done'

    # 喂金观察后重查 → 发放成功(gold 50 + 30 = 80)
    gs.observe(gs.gold, 50, sig=_SIG_OBS)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _SIG_LOGIC) == _EQUIP
    assert gs.gold.value == 80
    assert [c[0] for c in calls] == ['gold', 'equips', 'env_grants_done']


def test_equips_unobserved_withhold_no_half_grant(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """equips 缺读 → 整体缓发禁半发放(金已入账装备永久漏发 = 半发放,
    零写不标 done;库存到位后重查发放)。"""
    gs = _make_gs(env=_ENV, gold=100)   # equips 未写 = None
    _count_refreshes(gs, 20)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _SIG_LOGIC) is None
    assert not calls, f'缓发零写: {calls}'
    assert gs.gold.value == 100, '缓发不动金'
    assert gs.env_grants_done.value is None, '缓发不标 done'

    # 库存到位后重查 → 发放成功
    gs.write_logic(gs.equips, ['永动机'], produced_by='test-seed',
                   sig=_SIG_LOGIC)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _SIG_LOGIC) == _EQUIP
    assert [c[0] for c in calls] == ['gold', 'equips', 'env_grants_done']


def test_grant_three_writes_same_evidence_adjacent(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """发放三笔相邻写:gold +30 走 write_logic / equips 尾追走
    write_logic_rand / done 追加走 write_logic,三笔同 evidence
    env_grant#二手市场#refresh20 同 sig 相邻(金在前,done 收尾)。"""
    gs = _make_gs(env=_ENV, gold=100, equips=['永动机', '高周波电锯'])
    _count_refreshes(gs, 20)
    calls = _record_writes(gs, monkeypatch)

    granted = check_env_refresh_grants(gs, _SIG_LOGIC)

    assert granted == _EQUIP, '返回被发装备名(仅日志面消费)'
    assert gs.gold.value == 130, '金 100 + 30'
    assert gs.gold.source == 'logic', '金 = 登记事实直写'
    assert gs.equips.value == ['永动机', '高周波电锯', _EQUIP], \
        '库存尾部追加(随机态指落位未知,追加位置确定)'
    assert gs.equips.source == 'logic_rand', '装备 = 随机态通道'
    assert gs.env_grants_done.value == ((_ENV, REFRESH_THRESHOLD_KEY),)
    assert calls == [
        ('gold', 'env_grant#二手市场#refresh20', 'logic', _SIG_LOGIC),
        ('equips', 'env_grant#二手市场#refresh20', 'rand', _SIG_LOGIC),
        ('env_grants_done', 'env_grant#二手市场#refresh20', 'logic',
         _SIG_LOGIC),
    ], f'三笔同 evidence 同 sig 相邻: {calls}'


def test_trigger_rejects_obs_sig() -> None:
    """sig 单形态契约:obs 族进触发函数即炸渠道族校验(首笔金腿即拦;
    唯一调用方 = 上报函数 _grp_sig,logic_action 族,天然满足)。"""
    gs = _make_gs(env=_ENV, gold=100, equips=[])
    _count_refreshes(gs, 20)
    with pytest.raises(ValueError, match='渠道族'):
        check_env_refresh_grants(gs, _SIG_OBS)
    assert gs.gold.value == 100, '炸错前置零写'
    assert gs.env_grants_done.value is None


# ============================================================ 计数域与一次性


def test_total_domain_counts_mixed_free_paid_frames(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """计数域锁(用户裁定① = 全量):免费帧与付费帧混排经
    record_refresh 计到 20 → 发放(免费帧若不入账,paid 域恒不可达
    本锁)。"""
    gs = _make_gs(env=_ENV, gold=100, equips=[])
    for i in range(20):
        gs.effects.record_refresh(free=(i % 2 == 0))   # 免费/付费各 10 帧
    assert gs.effects.refresh_total == 20
    assert gs.effects.refresh_paid == 10, '混排有效:免费帧不进 paid'

    calls = _record_writes(gs, monkeypatch)
    assert check_env_refresh_grants(gs, _SIG_LOGIC) == _EQUIP, \
        '全量域:免费帧计入 20 次阈值'
    assert [c[0] for c in calls] == ['gold', 'equips', 'env_grants_done']


def test_exactly_once_in_21_refresh_loop(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """一次性(用户裁定②):kernel 级 21 次刷新循环,第 20 次恰发
    一次,第 21 次零新增写(done 封账,40 刷不再发)。"""
    gs = _make_gs(env=_ENV, gold=100, equips=['永动机'])
    calls = _record_writes(gs, monkeypatch)
    grants: list[str | None] = []
    for _ in range(21):
        gs.effects.record_refresh(free=False)
        grants.append(check_env_refresh_grants(gs, _SIG_LOGIC))

    assert grants.count(_EQUIP) == 1, f'21 刷恰发一次: {grants}'
    assert grants[19] == _EQUIP, '第 20 次发放'
    assert grants[20] is None, '第 21 次 done 在册不再发'
    assert gs.env_grants_done.value == ((_ENV, REFRESH_THRESHOLD_KEY),)
    assert len([c for c in calls if c[0] == 'env_grants_done']) == 1, \
        'done 只登记一次'
    assert gs.gold.value == 130, '金只 +30 一次'


# ============================================================ 接线存在性


def test_report_wiring_grants_on_threshold() -> None:
    """接线存在性:上报函数尾部触发检查在在册环境达阈时发放落地
    (集成 1 条;矩阵断言归 kernel 级,不在此层重复)。level 不写 =
    随机态采样腿跳写,窗口内只剩发放三笔。"""
    gs = _make_gs(env=_ENV, gold=100, equips=['永动机'])
    _count_refreshes(gs, 20)

    outcome = report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _SIG_LOGIC)

    assert outcome.applied is True
    assert gs.gold.value == 130, '发放腿金 +30 落地'
    assert gs.equips.value == ['永动机', _EQUIP], '发放腿装备尾追落地'
    assert gs.env_grants_done.value == ((_ENV, REFRESH_THRESHOLD_KEY),), \
        '发放腿 done 封账落地'
    assert gs.effects.refresh_total == 21, '计数腿先行入账(第 21 刷)'
