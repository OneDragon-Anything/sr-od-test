"""check_env_dot_grants 持续伤害契约条件分支(猜测写+证实)测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同模块兄弟触发函数测试 =
kernel/test_env_grants.py〔超限只读复用〕与本目录按被测方法拆分文件,
本文件按拆目录规范落位)。

测试面依据 = 原稿锁面(原稿锁面,
本文件锁面申报)§2.2/§2.3 + §4.1:
- **结算窗分支条件矩阵**(顺序短路):env 非本卡/已证实/幂等守卫(全视图
  含黑天鹅)→ 零写;否则猜测写(rand 通道,evidence ``env_dot_speculate``
  可辨);
- **进度分支**(count_battle=True,sim 专用):逐结算追加进度键
  dot_battle#<k>,第 ENV_DOT_CONFIRM_BATTLES 笔同窗证实,live 调用零进度;
- **观察证实分支**:观察含黑天鹅 → done 封账(不区分来源),观察无 → 零写;
- **观察擦除自愈**:猜测态被观察覆盖契约抹除后,下次结算重写。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_env_grants import (
    DOT_BATTLE_KEY_PREFIX,
    DOT_CONFIRM_KEY,
    DOT_CONTRACT_ENV,
    ENV_DOT_CONFIRM_BATTLES,
    check_env_dot_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    deployed_view_sequential,
)

_ENV = DOT_CONTRACT_ENV
_CHAR = '黑天鹅'

_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenBattleWait',
                       group_id='battle-wait:env-grant')
_SIG_SIM = ChannelSig(family='logic_action', actor='SimBackend',
                      mode='compute', group_id='sim:env')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_SEED = ChannelSig(family='logic_action', actor='test-seed',
                       mode='compute')


def _make_gs(*, env: str | None = _ENV,
             bench: list[tuple[str, int]] | None = None,
             deployed: list[str] | None = None,
             overflow: str | None = None,
             done: tuple[tuple[str, str], ...] | None = None,
             node: bool = False,
             anchored: bool = False) -> GameState:
    """观察面按参组装(None = 保持未写形态;登记/溢出域经 logic 直写
    播种)。``deployed`` = 上阵单位名顺延落位;``overflow`` = 溢出位身份。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if bench is not None:
        slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
        for i, (c, s) in enumerate(bench):
            slots[i] = BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if deployed is not None:
        gs.observe(gs.deployed,
                   deployed_view_sequential(
                       [Unit(char_id=c, star=1) for c in deployed], []),
                   sig=_SIG_OBS)
    if overflow is not None:
        gs.write_logic(gs.overflow_card, overflow, produced_by='test-seed',
                       evidence='t:ovf', sig=_SIG_SEED)
    if node:
        gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
                   sig=_SIG_OBS)
    if done is not None:
        gs.write_logic(gs.env_grants_done, tuple(done),
                       produced_by='test-seed', sig=_SIG_SEED)
    if anchored:
        gs.prep_anchored = True
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(先例 = 同目录 test_check_env_interest_grants
    同名 helper)。"""
    calls: list[tuple[str, str | None, str, ChannelSig, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel, sig,
                          produced_by))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


# ============================================================ 条件矩阵


def test_condition_matrix_short_circuits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """零写分支逐序(原稿锁面 §2.3 条件矩阵):env 空链/非本卡环境/
    已证实(done 封账)→ 返回 None 且状态容器零写行;env 门对进度分支同样生效
    (count_battle=True 零计数)。"""
    # ① env 未激活(None/空链)
    gs = _make_gs(env=None, bench=[])
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_HOOK, count_battle=True) is None
    assert not calls, f'env 空链零写: {calls}'
    # ② 非本卡环境(表外门:五触发函数条件矩阵同形)
    gs = _make_gs(env='公司契约', bench=[])
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_HOOK, count_battle=True) is None
    assert not calls, f'非本卡环境零写: {calls}'
    # ③ 已证实(一次性封账:结算窗与观察窗两条分支同门)
    gs = _make_gs(bench=[], done=((_ENV, DOT_CONFIRM_KEY),))
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_HOOK, count_battle=True) is None
    assert check_env_dot_grants(
        gs, sig=_SIG_HOOK,
        bench_observation=BenchView(
            slots=[BenchSlot(kind='unit', unit=Unit(char_id=_CHAR, star=1))],
            capacity=9)) is None
    assert not calls, f'已证实两条分支零写: {calls}'


def test_speculate_write_first_settlement(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """猜测写(设计稿 §4.1①):锚定状态容器上结算窗调用 → bench 增 1★ 黑天鹅
    (rand 通道恒 write_logic_rand,锚定后与确定面可辨)+ evidence
    ``env_dot_speculate#<帧>`` 可辨;live 调用(count_battle 缺省)零进度
    键零证实。"""
    gs = _make_gs(bench=[], node=True, anchored=True)
    calls = _record_writes(gs, monkeypatch)
    granted = check_env_dot_grants(gs, sig=_SIG_HOOK)
    assert granted == _CHAR, '返回发放角色名(日志面消费)'
    assert _bench_units(gs) == [(_CHAR, 1)], '1★ 先验入席'
    assert gs.bench.source == 'logic_rand', '猜测态 = rand 通道(锚定后可辨)'
    assert not gs.env_grants_done.value, 'live 调用零进度键零证实'
    assert len(calls) == 1 and calls[0][0] == 'bench', f'单笔席写: {calls}'
    assert calls[0][1] == 'env_dot_speculate#1-3#place', \
        '链写 evidence(基串带「位面-轮」帧+#place 后缀)'
    assert calls[0][3] == _SIG_HOOK and calls[0][4] == 'env_conditional_grant'


def test_idempotent_full_view_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """幂等守卫(设计稿 §2.2 条件 3,全视图三域同判):bench 已含黑天鹅 →
    连续结算零叠写;黑天鹅在上阵/溢出位同样封写(与 gain_character 3 合 1
    扫描域同域)。"""
    # ① 连续结算不叠写(bench 侧)
    gs = _make_gs(bench=[])
    check_env_dot_grants(gs, sig=_SIG_HOOK)
    assert _bench_units(gs) == [(_CHAR, 1)]
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_SIM) is None
    assert not calls, f'二次结算零写: {calls}'
    assert _bench_units(gs) == [(_CHAR, 1)], '恰一只,不叠写'
    # ② 上阵侧守卫(bench 空,黑天鹅已上阵)
    gs = _make_gs(bench=[], deployed=[_CHAR])
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_HOOK) is None
    assert not calls, f'上阵侧守卫零写: {calls}'
    # ③ 溢出位守卫(席满落溢出局型,设计稿 §2.2 溢出披露)
    gs = _make_gs(bench=[('椒丘', 1), ('卡芙卡', 1), ('希儿', 1), ('银狼', 1),
                         ('翡翠', 1), ('砂金', 1), ('符玄', 1), ('花火', 1),
                         ('停云', 1)], overflow=_CHAR)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_HOOK) is None
    assert not calls, f'溢出位守卫零写: {calls}'


def test_observation_confirm_then_no_speculate(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """观察证实(设计稿 §2.2 证实分支 + §4.1③):结算猜测写后,备战观察含
    黑天鹅 → done 封账(evidence ``env_dot_confirm#obs``,不区分来源);
    此后结算窗/观察窗两条分支零写(证实短路猜测写)。"""
    gs = _make_gs(bench=[])
    check_env_dot_grants(gs, sig=_SIG_HOOK)
    calls = _record_writes(gs, monkeypatch)
    obs_view = BenchView(slots=[BenchSlot(kind='unit',
                                          unit=Unit(char_id=_CHAR, star=1))],
                         capacity=9)
    granted = check_env_dot_grants(gs, sig=_SIG_HOOK,
                                   bench_observation=obs_view)
    assert granted == _CHAR
    assert gs.env_grants_done.value == ((_ENV, DOT_CONFIRM_KEY),), '证实封账'
    assert [(c[0], c[1]) for c in calls] == [('env_grants_done',
                                              'env_dot_confirm#obs')], \
        f'证实单笔 logic 写: {calls}'
    # 证实后两条分支零写
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_HOOK) is None
    assert check_env_dot_grants(gs, sig=_SIG_HOOK,
                                bench_observation=obs_view) is None
    assert not calls, f'证实后零写: {calls}'


def test_observation_erase_then_rewrite(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """观察擦除自愈(设计稿 §2.2 证实分支 + §4.1④):备战观察无黑天鹅 →
    零写(不误证);观察覆盖契约抹除猜测态(bench 回空)后,下次结算
    重写猜测态。"""
    gs = _make_gs(bench=[])
    check_env_dot_grants(gs, sig=_SIG_HOOK)
    assert _bench_units(gs) == [(_CHAR, 1)]
    # 备战观察无黑天鹅:证实分支零写 + 整表观察同步抹除猜测态(观察覆盖
    # 契约:首观察静默覆盖)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_HOOK,
                                bench_observation=BenchView(slots=[])) is None
    assert not calls, f'观察无黑天鹅零写: {calls}'
    assert gs.env_grants_done.value is None, '不误证'
    empty = BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9)
    gs.observe(gs.bench, empty, sig=_SIG_OBS)
    assert _bench_units(gs) == [], '猜测态被观察覆盖抹除'
    # 下次结算重写(自愈循环:写 → 观察 → 擦 → 再写)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_HOOK) == _CHAR
    assert _bench_units(gs) == [(_CHAR, 1)], '下次结算重写'
    assert len(calls) == 1 and calls[0][0] == 'bench'


# ============================================================ sim 进度分支


def test_sim_battle_counting_progress_and_confirm(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """sim 战斗计数(设计稿 §2.3 + §4.1⑤):门真后逐结算追加进度键
    dot_battle#1..k(append-only);第 ENV_DOT_CONFIRM_BATTLES 笔同窗相邻
    追加证实(evidence ``env_dot_confirm#sim``);阈值前不证实;证实后
    继续结算零写(门关)。"""
    gs = _make_gs(bench=[])
    calls = _record_writes(gs, monkeypatch)
    for _ in range(ENV_DOT_CONFIRM_BATTLES - 1):
        assert check_env_dot_grants(gs, sig=_SIG_SIM,
                                    count_battle=True) == _CHAR
    keys = [k for e, k in gs.env_grants_done.value
            if e == _ENV and k.startswith(DOT_BATTLE_KEY_PREFIX)]
    assert keys == [f'dot_battle#{i}'
                    for i in range(1, ENV_DOT_CONFIRM_BATTLES)], \
        f'阈值前逐笔进度键: {keys}'
    assert (_ENV, DOT_CONFIRM_KEY) not in gs.env_grants_done.value, \
        '第 7 结算不达,零证实'
    progress_rows = [c for c in calls
                     if c[1] and c[1].startswith('env_dot_progress#')]
    assert len(progress_rows) == ENV_DOT_CONFIRM_BATTLES - 1, \
        '每结算恰一笔进度写'
    assert all(c[3] == _SIG_SIM for c in calls), 'sig 单形态'
    # 第 8 结算:进度键 + 证实同窗相邻两写
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_SIM,
                                count_battle=True) == _CHAR
    assert [(c[0], c[1]) for c in calls] == [
        ('env_grants_done', f'env_dot_progress#{ENV_DOT_CONFIRM_BATTLES}'),
        ('env_grants_done', 'env_dot_confirm#sim'),
    ], f'第 8 结算两笔相邻写: {calls}'
    assert gs.env_grants_done.value[-2:] == (
        (_ENV, f'dot_battle#{ENV_DOT_CONFIRM_BATTLES}'),
        (_ENV, DOT_CONFIRM_KEY)), '进度键与证实键同窗落地'
    assert _bench_units(gs) == [(_CHAR, 1)], '猜测态恰一只(守卫封叠写)'
    # 证实后继续结算零写(计数门随证实关闭)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_dot_grants(gs, sig=_SIG_SIM, count_battle=True) is None
    assert not calls, f'证实后零写: {calls}'
