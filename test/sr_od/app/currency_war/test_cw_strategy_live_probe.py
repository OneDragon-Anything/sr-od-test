"""策略失活探针判据锁(dd-031 判据重写批)。

被测生产面:
- 运行探针:operations/cw_loop.py 备战入口失活检查(ADR-0342 接线)。
- 判据单一源:telemetry/query.py 的 _row_heartbeat / strategy_round_live /
  check_strategy_live_streak。
- 消费接线:sim/ledger_hooks.run_checks_on_replay(离线检查网)。

dd-031 定谳(g_20260904_022537 / g_20260904_010335 两局误杀):旧判据
「该轮无 strategy_id 决策行 = 策略失活」把 mandate 合法跳过开店的健康局
误杀(整轮只有载体行,sid='');新判据 = 策略心跳(sid 行或载体行,任一
即活),探针辖域收敛为「外环停转」(整轮零心跳行)。真死形态、误杀形态、
离线检查网三面同源锁定,防两处判据漂移。

⚠️ 本文件从 test_cw_intention_gate.py(legacy_baseline 桶)拆出:这些锁
钉的是**生产运行行为**(探针 + 离线检查),不随 decision_v2 旧核退役,
必须进常规快速集。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.telemetry import query, recorder, state


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


@pytest.fixture(autouse=True)
def _rec(tmp_path, monkeypatch):
    rec = recorder.TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(state, '_RECORDER', rec)
    query._STRATEGY_LIVE_CACHE.clear()
    yield rec
    query._STRATEGY_LIVE_CACHE.clear()


# ===== 心跳判定核心(单一源 _row_heartbeat)=====

def test_heartbeat_row_criterion() -> None:
    """心跳 = sid 非空或 actions 非空,二者缺一即哑行。"""
    hb = query._row_heartbeat
    assert hb({'strategy_id': 'mandate_v1', 'actions': []}) is True
    assert hb({'strategy_id': '', 'actions': [{'__type__': 'StartBattle'}]}) is True
    assert hb({'strategy_id': '', 'actions': []}) is False
    assert hb({}) is False
    # 缺键容忍(actions None/缺键按空)
    assert hb({'strategy_id': None}) is False


# ===== 回归锁①:g_20260904_022537 r7/r8 误杀形态 =====

def test_mandate_skip_shop_round_is_live() -> None:
    """误杀形态(022537 r7/r8 / 010335 r8/r9 实录形状):整轮只有载体行
    (sid='' + StartBattle 等动作)→ 活。mandate 三开店站全关时合法跳过
    开店,sid 行唯一写点在店内决策,无 sid 行 ≠ 策略死亡。"""
    f = Path(str(state._RECORDER.replay_dir) + '/decisions.jsonl')
    _write_rows(f, [
        {'run_id': 'm1', 'plane': 1, 'round_num': 7, 'strategy_id': '',
         'actions': [{'__type__': 'StartBattle'}]},
    ])
    assert query.strategy_round_live('m1', (1, 7)) is True


def test_supply_quiet_round_isolated_no_false_stop() -> None:
    """补给轮形态(022537/010335 r5 实录:决策行存在但零动作零 sid)
    → 该轮非心跳(失活候选),但被前后健康轮隔离,连击不成立——
    两个误杀局的 r5 都形如此,探针在整局上不得判死。"""
    f = Path(str(state._RECORDER.replay_dir) + '/decisions.jsonl')
    rows = []
    for rn in range(1, 9):
        if rn == 5:
            rows.append({'run_id': 'm2', 'plane': 1, 'round_num': rn,
                         'strategy_id': '', 'actions': []})
        elif rn == 7:
            # 022537 r7 形态:mandate 跳过开店,仅载体行
            rows.append({'run_id': 'm2', 'plane': 1, 'round_num': rn,
                         'strategy_id': '',
                         'actions': [{'__type__': 'StartBattle'}]})
        else:
            rows.append({'run_id': 'm2', 'plane': 1, 'round_num': rn,
                         'strategy_id': 'mandate_v1', 'actions': []})
    _write_rows(f, rows)
    for rn in range(1, 9):
        if rn == 5:
            assert query.strategy_round_live('m2', (1, rn)) is False
        else:
            assert query.strategy_round_live('m2', (1, rn)) is True
    # 整局连击走查(022537 逐轮 replay):连击永不达 2,不触发早停
    streak = 0
    for rn in range(1, 9):
        streak = query.dead_streak_transition(
            (1, rn), (1, rn + 1), streak,
            query.strategy_round_live('m2', (1, rn)))
    assert streak < 2


# ===== 回归锁②:真死形态(外环停转)必判死 =====

def test_outer_loop_dead_still_stops() -> None:
    """真死形态:整轮零心跳行(sid 空且动作空)连续 ≥2 → 连击成立,
    loop 侧停局线(阈值 2,同 ADR-0342 原响应性)。哑行(观测错误行)
    不算心跳——兜底/异常留证行救不活停转判定。"""
    f = Path(str(state._RECORDER.replay_dir) + '/decisions.jsonl')
    _write_rows(f, [
        {'run_id': 'dead1', 'plane': 1, 'round_num': 3,
         'strategy_id': '', 'actions': []},
        {'run_id': 'dead1', 'plane': 1, 'round_num': 4,
         'strategy_id': '', 'actions': []},
    ])
    assert query.strategy_round_live('dead1', (1, 3)) is False
    assert query.strategy_round_live('dead1', (1, 4)) is False
    # 连击状态机逐轮结算(与 cw_loop 接线同式:进入新轮结算上一轮)
    streak = 0
    for prev, cur in (((1, 2), (1, 3)), ((1, 3), (1, 4)), ((1, 4), (1, 5))):
        streak = query.dead_streak_transition(
            prev, cur, streak, query.strategy_round_live('dead1', prev))
    assert streak >= 2


def test_strategy_round_live_with_cache(tmp_path) -> None:
    """mtime 缓存:写入后重查可见;不同 run 互不串。"""
    f = tmp_path / 'decisions.jsonl'
    _write_rows(f, [
        {'run_id': 'r1', 'plane': 1, 'round_num': 1, 'strategy_id': ''},
        {'run_id': 'r1', 'plane': 1, 'round_num': 2, 'strategy_id': 'decision_v2'},
        {'run_id': 'r2', 'plane': 1, 'round_num': 1,
         'strategy_id': '', 'actions': [{'__type__': 'StartBattle'}]},
    ])
    assert query.strategy_round_live('r1', (1, 1)) is False
    assert query.strategy_round_live('r1', (1, 2)) is True
    assert query.strategy_round_live('r2', (1, 1)) is True
    # 追加(新 mtime)后缓存失效重扫:r1 r1 也变 live
    _write_rows(f, [{'run_id': 'r1', 'plane': 1, 'round_num': 1,
                     'strategy_id': 'decision_v2'}])
    assert query.strategy_round_live('r1', (1, 1)) is True


def test_dead_streak_transition_state_machine() -> None:
    """同 key 重入不计数;换 key 时 live 复位 / dead 递增。"""
    t = query.dead_streak_transition
    # 首轮(prev None):不结算
    assert t(None, (1, 1), 0, True) == 0
    assert t(None, (1, 1), 2, False) == 2
    # 同轮重入(过渡帧/重试):不结算
    assert t((1, 1), (1, 1), 1, False) == 1
    # 换轮:live 复位
    assert t((1, 1), (1, 2), 1, True) == 0
    # 换轮:dead 递增
    assert t((1, 1), (1, 2), 0, False) == 1
    assert t((1, 2), (1, 3), 1, False) == 2   # 连击到 2 = loop 侧停局线


# ===== 回归锁③:离线检查网同源同步 =====

def test_check_strategy_live_streak_same_criterion() -> None:
    """sim 检查网 check_strategy_live_streak 与运行探针同源(_row_heartbeat):
    误杀形态(载体行健康局)不报;哑行停转段必报。"""
    c = query.check_strategy_live_streak
    # 误杀形态(022537 形状:r5 补给哑行孤立,r7/r8 载体行)→ 不报
    ok_rows = []
    for rn in range(1, 9):
        if rn == 5:
            ok_rows.append({'plane': 1, 'round_num': rn,
                            'strategy_id': '', 'actions': []})
        elif rn == 7:
            ok_rows.append({'plane': 1, 'round_num': rn, 'strategy_id': '',
                            'actions': [{'__type__': 'StartBattle'}]})
        else:
            ok_rows.append({'plane': 1, 'round_num': rn,
                            'strategy_id': 'mandate_v1', 'actions': []})
    assert c(ok_rows) == []
    # 真死形态:哑行连续 ≥ 阈值 3 → 报
    dead_rows = [{'plane': 1, 'round_num': rn, 'strategy_id': '', 'actions': []}
                 for rn in range(1, 10)]
    v = c(dead_rows)
    assert v and '9 轮' in v[0] and 'dd-031' in v[0]
    # 孤立 2 轮哑行(< 阈值 3)不报
    short = [{'plane': 1, 'round_num': rn, 'strategy_id': '', 'actions': []}
             for rn in (1, 2)] + [
        {'plane': 1, 'round_num': rn, 'strategy_id': 'mandate_v1', 'actions': []}
        for rn in (3, 4)]
    assert c(short) == []
    # P2 哑行不辖(只辖 P1)
    p2 = [{'plane': 2, 'round_num': rn, 'strategy_id': '', 'actions': []}
          for rn in range(1, 5)]
    assert c(p2) == []


def test_run_checks_reports_dead_run(tmp_path) -> None:
    """run_checks_on_replay 对停转局出报警行(不被判栈跳过)。

    夹具用真死形态(哑行):旧夹具的 EnsureShopClosed 载体行在新判据下
    是心跳行(不报),语义随 dd-031 判据重写同步换形。"""
    _write_rows(tmp_path / 'decisions.jsonl', [
        {'run_id': 'dead2', 'plane': 1, 'round_num': rn,
         'strategy_id': '', 'actions': []}
        for rn in range(1, 6)
    ])
    _write_rows(tmp_path / 'outcomes.jsonl', [
        {'run_id': 'dead2', 'plane': 1, 'round_num': rn} for rn in range(1, 6)
    ])
    lines = ledger_hooks.run_checks_on_replay(tmp_path, recent=5)
    assert any('[策略失活]' in x and 'dead2' in x for x in lines), lines


# ===== 流程心跳载体行修复批(策略失活误杀「恢复局+补给链」无声双轮)=====
# 定谳(诊断档案 noprogress_stop_diag「第五次停机」节):恢复局锁定直出战
# 分支与补给节点按设计整轮零策略决策行——「无声」是流程性合法无声,外环
# 活着却在别的分支干活;连续 2 轮此类轮被失活连击误判「外环停转」停局。
# 修复:两类分支消费一轮时显式登记 decisions 可见的心跳载体行——恢复局
# 直出战 = 真实执行的 StartBattle 载体行(sid=''+actions 非空,与 mandate
# 跳开店健康轮同构);补给节点 = 流程 sid 标记行(strategy_id='cw:flow:
# supply_node_divert',自描述非店内决策)。钩子本体保留(真死局检测价值在)。

_FLOW_ROUNDS = [
    # r2:恢复局锁定分支消费(载体行:真实执行的出战动作)
    {'run_id': 'm5', 'plane': 2, 'round_num': 2, 'strategy_id': '',
     'actions': [{'__type__': 'StartBattle'}]},
    # r3:补给节点流程标记行(sid 自描述,actions 空)
    {'run_id': 'm5', 'plane': 2, 'round_num': 3,
     'strategy_id': 'cw:flow:supply_node_divert', 'actions': []},
]


def test_flow_silent_rounds_are_live_after_fix() -> None:
    """本局误杀形态回放:恢复局直出战载体行 + 补给节点流程标记行——
    两轮按 _row_heartbeat 均为心跳,失活连击不再累积(修复前:两轮均
    哑行 → streak=2 → 误杀停局)。"""
    f = Path(str(state._RECORDER.replay_dir) + '/decisions.jsonl')
    _write_rows(f, _FLOW_ROUNDS)
    assert query.strategy_round_live('m5', (2, 2)) is True
    assert query.strategy_round_live('m5', (2, 3)) is True
    streak = 0
    for prev, cur in (((2, 1), (2, 2)), ((2, 2), (2, 3)), ((2, 3), (2, 4))):
        streak = query.dead_streak_transition(
            prev, cur, streak, query.strategy_round_live('m5', prev))
    assert streak < 2, '流程性合法无声双轮不得触发早停连击'


def test_true_dead_still_caught_alongside_flow_rounds() -> None:
    """真死局仍被抓(钩子保留不删):真哑行连续 2 轮(前后夹流程心跳轮,
    证明不是流程轮被放行而是判据区分开)→ 连击达 2,停局线不变。"""
    f = Path(str(state._RECORDER.replay_dir) + '/decisions.jsonl')
    _write_rows(f, _FLOW_ROUNDS + [
        {'run_id': 'm5', 'plane': 2, 'round_num': 4,
         'strategy_id': '', 'actions': []},
        {'run_id': 'm5', 'plane': 2, 'round_num': 5,
         'strategy_id': '', 'actions': []},
    ])
    streak = 0
    keys = [(2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6)]
    for prev, cur in zip(keys, keys[1:], strict=False):
        streak = query.dead_streak_transition(
            prev, cur, streak, query.strategy_round_live('m5', prev))
    assert streak >= 2, '真哑行连续 2 轮必须仍被抓(钩子保留)'


def test_strategy_dead_flag_three_elements(tmp_path) -> None:
    """钩子 flag 三要素锁(od-dev-stop-hooks 审计口径):写入文件含
    [HOOK-STOP] 特征头 / 处理步骤 / 删除条件 + 定位(run/轮/streak/截图)。"""
    from sr_od.application.currency_war.operations.cw_loop import (
        write_strategy_dead_flag,
    )
    p = tmp_path / 'strategy_dead_early_stop.flag'
    ret = write_strategy_dead_flag(2, (2, 3), 'run-x', 'shot.png', path=p)
    text = p.read_text(encoding='utf-8')
    assert ret == str(p)
    assert '[HOOK-STOP]' in text
    assert '处理步骤' in text and '删除条件' in text
    assert 'run-x' in text and 'P2-r3' in text and 'streak=2' in text
    assert 'shot.png' in text


def test_register_flow_heartbeat_writes_carrier_rows(monkeypatch) -> None:
    """登记函数行为锁:恢复局分支写真实 StartBattle 载体行(sid=''),
    补给分支写流程 sid 标记行;遥测关闭/last_state 缺席静默跳过。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.operations import cw_loop

    written: list[tuple] = []
    monkeypatch.setattr(recorder, 'record_decision',
                        lambda st, t, cs, eb, actions, extra=None,
                        gold_point=True: written.append((actions, extra)))
    _rec_enabled = _NS(enabled=True)
    _state = _NS(get_recorder=lambda: _rec_enabled, plane=2, round_num=2,
                 hp=1, gold=68, level=7)
    ctx = _NS(cw_match=_NS(session=_NS(last_state=_state)))
    cw_loop.register_flow_heartbeat(ctx, 'locked_resume_direct_battle')
    assert written and len(written[0][0]) == 1
    assert written[0][1] == {'strategy_id': ''}
    cw_loop.register_flow_heartbeat(ctx, 'supply_node_divert')
    assert written[1][0] == []
    assert written[1][1] == {'strategy_id': 'cw:flow:supply_node_divert'}
    # 静默面:遥测关闭 / last_state 缺席 ⇒ 不写不炸
    _state_off = _NS(get_recorder=lambda: _NS(enabled=False), plane=2,
                     round_num=3, hp=1, gold=68, level=7)
    n = len(written)
    cw_loop.register_flow_heartbeat(
        _NS(cw_match=_NS(session=_NS(last_state=_state_off))), 'supply_node_divert')
    cw_loop.register_flow_heartbeat(_NS(cw_match=_NS(session=_NS(last_state=None))),
                                    'supply_node_divert')
    assert len(written) == n


def test_stack_detection_ignores_flow_marker_rows(tmp_path) -> None:
    """判栈 × 流程标记行波及面锁(策略审查十二跳打回):判栈取「第一条
    非空 strategy_id」,若流程标记行(cw:flow:*)居 run 段首,该段曾被判
    「[未知栈] coldstart 跳过」→ mandate_v1 局漏跑冷启动检查。
    修复 = 判栈过滤 cw:flow: 前缀:标记行居首的 mandate 局仍正确判栈;
    纯标记行局不冒充任何已知栈。"""
    _write_rows(tmp_path / 'decisions.jsonl', [
        # m6:标记行居 run 段首(恢复局/补给分支先写),随后 mandate_v1 行
        {'run_id': 'm6', 'plane': 2, 'round_num': 3,
         'strategy_id': 'cw:flow:supply_node_divert', 'actions': []},
        {'run_id': 'm6', 'plane': 1, 'round_num': 1,
         'strategy_id': 'mandate_v1', 'ev_arm': 'full', 'actions': []},
        # m7:纯标记行(无任何策略栈行)——不得冒充已知栈
        {'run_id': 'm7', 'plane': 2, 'round_num': 1,
         'strategy_id': 'cw:flow:locked_resume_direct_battle', 'actions': []},
    ])
    _write_rows(tmp_path / 'outcomes.jsonl', [
        {'run_id': 'm6'}, {'run_id': 'm7'},
    ])
    lines = ledger_hooks.run_checks_on_replay(tmp_path, recent=5)
    assert any('m6' in x and '[mandate[full] 栈]' in x for x in lines), lines
    assert not any('未知栈' in x and 'cw:flow' in x for x in lines), lines
    m7 = [x for x in lines if x.startswith('m7')]
    assert m7 and '未知栈' not in m7[0], m7


# ===== 恢复局首战前备战同步步(策略审查十二跳 #7)=====

def test_locked_resume_sync_step_precedes_start_battle(monkeypatch) -> None:
    """8:44 形态锁(恢复局锁定直出战,board_before 空):LockedResume 分支
    的出战执行 = 同步步(RunDeploy 组合:deploy-swap/腾席/确定性部署)
    **先于** StartBattle,且每锁定局恰一次(第二次调用不再同步);
    无条件插入,零血线入参。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.operations import cw_loop

    calls: list[str] = []

    class _FakeExecutor:
        def __init__(self, op, ctx):
            calls.append('init')

        def execute(self, action):
            calls.append(type(action).__name__)
            return True, 'ok'

    import sr_od.application.currency_war.prep_actions as _pa
    monkeypatch.setattr(_pa, 'PrepActionExecutor', _FakeExecutor)

    class _Loop(cw_loop.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            self.ctx = _NS(cw_match=_NS(session=None))
            self._cw_locked_sync_done = False

    op = _Loop()
    progressed, detail = cw_loop.locked_resume_sync_and_battle(op, op.ctx)
    assert progressed is True
    assert calls == ['init', 'RunDeploy', 'StartBattle'], calls
    assert op._cw_locked_sync_done is True
    # 同一锁定局第二次出战:只 StartBattle,不重复同步(init = 执行体重建,非动作)
    calls.clear()
    progressed2, _ = cw_loop.locked_resume_sync_and_battle(op, op.ctx)
    assert [c for c in calls if c != 'init'] == ['StartBattle'], calls
    assert progressed2 is True


def test_locked_resume_sync_reset_per_lock_episode() -> None:
    """同步步证据位按锁定局复位:锁定确认分支置 _cw_locked_sync_done=False
    (行为面 = 新锁定局重新获得一次同步步);出战执行函数无 hp 入参
    (血线判据禁直读,00§3 合规,挂账不落码)。"""
    import inspect

    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop.CwLoop)
    assert '_cw_locked_sync_done = False' in src, \
        '锁定确认分支必须复位同步步证据位'
    sig = inspect.signature(cw_loop.locked_resume_sync_and_battle)
    assert list(sig.parameters) == ['op', 'ctx']


def _mk_sync_loop():
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.operations import cw_loop

    class _Loop(cw_loop.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            self.ctx = _NS(cw_match=_NS(session=None))
            self._cw_locked_sync_done = False
            self._cw_locked_sync_fails = 0

    return _Loop()


def _patch_executor(monkeypatch, results: list[tuple[bool, str]],
                    calls: list[str]):
    import sr_od.application.currency_war.prep_actions as _pa

    class _FakeExecutor:
        def __init__(self, op, ctx):
            calls.append('init')

        def execute(self, action):
            name = type(action).__name__
            calls.append(name)
            return results.pop(0) if name == 'RunDeploy' else (True, 'ok')

    monkeypatch.setattr(_pa, 'PrepActionExecutor', _FakeExecutor)


def test_locked_resume_sync_failure_not_marked_and_retried(monkeypatch) -> None:
    """R1/R2 失败路径锁:RunDeploy ok=False(drag 白拖/刹车/板满门退化)
    ⇒ 证据位不置位 + StartBattle 照常发射(本环不出席);下环重进同步
    (RunDeploy 再次执行);重试成功后证据位置位、不再重试。"""
    from sr_od.application.currency_war.operations import cw_loop
    op = _mk_sync_loop()
    calls: list[str] = []
    _patch_executor(monkeypatch, [(False, '拖3次源槽未变'), (True, '计划空')],
                    calls)
    # 第 1 环:同步失败 → 证据位不置位,StartBattle 照发(本环不出席)
    p1, _ = cw_loop.locked_resume_sync_and_battle(op, op.ctx)
    assert p1 is True and op._cw_locked_sync_done is False
    assert [c for c in calls if c != 'init'] == ['RunDeploy', 'StartBattle']
    # 第 2 环:重进同步,成功 ⇒ 置位;此后不再同步
    p2, _ = cw_loop.locked_resume_sync_and_battle(op, op.ctx)
    assert p2 is True and op._cw_locked_sync_done is True
    calls.clear()
    cw_loop.locked_resume_sync_and_battle(op, op.ctx)
    assert [c for c in calls if c != 'init'] == ['StartBattle']


def test_locked_resume_sync_gives_up_after_retry_limit(monkeypatch) -> None:
    """重试上限锁:连续失败达上限(3)⇒ 放弃重试(证据位置位,防止与
    StartBattle 重试共用 retry 池的无限消耗),StartBattle 照发——放弃侧
    显式代价,非静默。新锁定局复位计数后重新获得完整重试预算。"""
    from sr_od.application.currency_war.operations import cw_loop
    op = _mk_sync_loop()
    calls: list[str] = []
    _patch_executor(monkeypatch, [(False, '已停止[W209j刹车]')] * 4, calls)
    limit = 3
    for _i in range(1, limit):
        p, _ = cw_loop.locked_resume_sync_and_battle(op, op.ctx)
        assert p is True   # StartBattle 每环照发
        assert op._cw_locked_sync_done is False, '未达上限不放弃'
    # 第 limit 次失败:达上限 ⇒ 放弃置位(此后不再重试同步)
    cw_loop.locked_resume_sync_and_battle(op, op.ctx)
    assert op._cw_locked_sync_done is True
    runs = [c for c in calls if c == 'RunDeploy']
    assert len(runs) == limit, '放弃后不得再消耗同步重试'
    # 新锁定局复位:证据位与失败计数归零
    op._cw_locked_sync_done = False
    op._cw_locked_sync_fails = 0
    cw_loop.locked_resume_sync_and_battle(op, op.ctx)
    assert op._cw_locked_sync_fails == 1
