"""统一state R4 策略侧遥测演进锁(DecisionTrace 瘦身演进第一批)。

设计正本 = ADR-0630(统一 state 状态流水,持久结论单一源;.debug/temp
工作稿为易失档)策略侧 state_ref 版本钉与逐项理由溯源面;账本裁定 =
dag T-217 note 2026-09-10T12:33:16(策略侧遥测定稿:四要素/瘦身判据/动作
计划逐项理由溯源)与 12:34:44(每决策一行,动作计划随行携带)。

本文件锁四件:
① state_ref 版本钉——决策行回溯流程侧账本版本 id(``BoardState.
   current_version()`` 读口);R4返工方案 A 钉读点 = 「决策读取完成时点」:
   段入口观察完成处捕获版本经 ``state_ref_version`` 传入落钉(锁①d 钉
   「中途推进不漂移」/①e 钉缺省语义/①f 钉商店段接线);M4 窗内带
   ``pin_scope='board_state'`` 显式标记(v3.3-M1:钉面≠决策消费面,
   禁无标记的对账假结论);
② 动作计划逐项理由溯源——actions 逐项 'reason' 归一键,从现役决策构建
   链已有字段提取(不新算);
③ 申报面锁——B 档快照重复候选字段仍在场(候裁不执行的结构性守卫,
   误删即红)+ A 档删候选已删封闭锁与瘦身后 schema 形态封闭锁(③d)+
   理由提取键序单一源;
④ 消费方兼容面——旧档案行(无新字段)经规范读端零破坏(判读读面宽容
   原则)。
"""
from __future__ import annotations

import json
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_board_state
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.telemetry import recorder as rec_mod
from sr_od.application.currency_war.telemetry import state as telstate
from sr_od.application.currency_war.telemetry.cw_replay_reader import (
    DecisionTrace,
    from_dict,
)
from sr_od.application.currency_war.telemetry.schema import (
    ACTION_REASON_SOURCE_KEYS,
)


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'r4t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/)。"""
    monkeypatch.setattr(telstate, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(telstate, '_CURRENT_RUN_ID', run_id)
    monkeypatch.setattr(telstate, '_CURRENT_DIFFICULTY', 'A8')
    monkeypatch.setattr(telstate, '_RUN_CLOSED', False)
    monkeypatch.setattr(telstate, '_PENDING_BRIEFING_ROWS', [])
    monkeypatch.setattr(telstate, '_defect_seen', {})
    monkeypatch.setattr(telstate, '_defect_seen_run', '')
    monkeypatch.setattr(telstate, '_L0_ANDON_HANDLER', lambda payload: True)
    monkeypatch.setattr(telstate, '_L0_ANDON_FIRED_RUNS', set())
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider',
                        telstate.current_run_id)


def _fake_match() -> SimpleNamespace:
    """fake ctx.cw_match 容器(session 旁挂 BoardState 单例随用随建)。"""
    return SimpleNamespace(session=StrategySession())


def _rows(tmp_path: Path, name: str = 'decisions.jsonl') -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① state_ref 版本钉 =====

def test_state_ref_pin_format_and_scope(tmp_path: Path, monkeypatch) -> None:
    """锁①a:决策行带 state_ref='{run_id}#{v}' + pin_scope='board_state'。

    v = 写入时点 ``board_state_of(session).current_version()``;断言在
    record 返回后现读(current_version 读不写,中间零状态写入则同值)。
    """
    _setup_recorder(monkeypatch, tmp_path)
    m = _fake_match()
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [m])
    sess = m.session
    bs = cw_board_state.board_state_of(sess)
    bs.write_logic(bs.gold, 77, produced_by='r4test')   # 版本 ≥1(非零形态)
    st = GameState(gold=30, hp=50, round_num=6, plane=1)
    telstate.get_recorder().record_decision('r4a', 'A8', st, '', {}, {}, [])
    r = _rows(tmp_path)[0]
    assert r['state_ref'] == f"r4a#{bs.current_version()}"
    assert int(r['state_ref'].split('#')[1]) >= 1
    # M4 窗内钉面标记(v3.3-M1:钉解析出 BoardState 面,非决策消费面)
    assert r['pin_scope'] == 'board_state'


def test_state_ref_pin_tracks_version_advancement(
        tmp_path: Path, monkeypatch) -> None:
    """锁①b:账本版本推进 → 后续决策行钉值严格跟随(回溯键单调可比)。"""
    _setup_recorder(monkeypatch, tmp_path)
    m = _fake_match()
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [m])
    bs = cw_board_state.board_state_of(m.session)
    st = GameState(gold=30, hp=50, round_num=1, plane=1)
    rec = telstate.get_recorder()
    rec.record_decision('r4b', 'A8', st, '', {}, {}, [])
    v1 = int(_rows(tmp_path)[0]['state_ref'].split('#')[1])
    bs.write_logic(bs.gold, 99, produced_by='r4test')
    rec.record_decision('r4b', 'A8', st, '', {}, {}, [])
    v2 = int(_rows(tmp_path)[1]['state_ref'].split('#')[1])
    assert v2 == v1 + 1


def test_state_ref_pin_honest_default_without_session(
        tmp_path: Path, monkeypatch) -> None:
    """锁①c:无 match 注册(离线/测试)→ state_ref=''(诚实缺省,不猜)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [None])
    telstate.get_recorder().record_decision(
        'r4c', 'A8', GameState(gold=30, hp=50, round_num=6, plane=1),
        '', {}, {}, [])
    r = _rows(tmp_path)[0]
    assert r['state_ref'] == ''
    assert r['pin_scope'] == ''


def test_state_ref_pin_uses_observation_version_under_midway_writes(
        tmp_path: Path, monkeypatch) -> None:
    """锁①d(方案 A 钉读点,R4返工核心):决策计算中途动作回执推进版本
    → 钉值 = 观测完成时点版本,不漂移到落盘时点版本。

    场景对位 = 商店段真实时序(ADR-0630 关联序:决策行钉版本 ≤ 其动作
    的落地行版本):段入口观察完成捕获 v_obs → 段内 k 次动作回执推进
    账本版本 → 行落盘。捕获时点归调用方(只有它知道观察何时完成),经
    ``state_ref_version=v_obs`` 显式传入;recorder 不得改读落盘时点版本。
    红态在案(2026-09-11 返工批):实现前本锁 TypeError(签名无该参)。
    """
    _setup_recorder(monkeypatch, tmp_path)
    m = _fake_match()
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [m])
    bs = cw_board_state.board_state_of(m.session)
    bs.write_logic(bs.gold, 77, produced_by='r4test')
    v_obs = bs.current_version()   # 段入口观察完成时点捕获
    for i in range(3):             # 决策计算中途:动作回执逐条推进版本
        bs.write_logic(bs.gold, 80 + i, produced_by='r4test')
    st = GameState(gold=30, hp=50, round_num=6, plane=1)
    telstate.get_recorder().record_decision(
        'r4i', 'A8', st, '', {}, {}, [], state_ref_version=v_obs)
    r = _rows(tmp_path)[0]
    assert r['state_ref'] == f'r4i#{v_obs}', (
        '钉值漂移到落盘时点版本(观测完成捕获未生效/被入口现读覆盖)')
    assert int(r['state_ref'].split('#')[1]) < bs.current_version(), (
        '钉版本须严格早于落盘时点账本版本(ADR-0630 决策行钉 ≤ 动作落地行序)')


def test_state_ref_default_path_pins_at_record_entry(
        tmp_path: Path, monkeypatch) -> None:
    """锁①e(缺省语义申报):不传 state_ref_version = 入口现读(落盘时点)
    ——该缺省只对「观察完成与落盘之间零状态写入交错」的调用点等价于观测
    完成版本(prep 步进行行/补给快照行/流程心跳行等,调用点清点申报面);
    有交错写入的调用点(商店段)必须显式传参(锁①d)。本锁钉缺省行为,
    防缺省语义无声漂移。"""
    _setup_recorder(monkeypatch, tmp_path)
    m = _fake_match()
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [m])
    bs = cw_board_state.board_state_of(m.session)
    bs.write_logic(bs.gold, 77, produced_by='r4test')
    v_obs = bs.current_version()
    for i in range(2):
        bs.write_logic(bs.gold, 80 + i, produced_by='r4test')
    st = GameState(gold=30, hp=50, round_num=6, plane=1)
    telstate.get_recorder().record_decision('r4j', 'A8', st, '', {}, {}, [])
    r = _rows(tmp_path)[0]
    assert r['state_ref'] == f"r4j#{bs.current_version()}"
    assert int(r['state_ref'].split('#')[1]) > v_obs, (
        '缺省路径应钉落盘时点版本(有交错写入的调用点须显式传参,见锁①d)')


def test_shop_segment_capture_wiring() -> None:
    """锁①f(方案 A 落地接线,结构锁):商店段 run_buy_waves 在段入口
    观察完成处捕获账本版本,段尾 record_decision 经 state_ref_version
    传入;捕获点先于首个决策读(段内动作回执推进版本前)。结构锁先例 =
    test_cw_telemetry 记录站点顺序锁 / ADR-0571 grep 守卫。红态在案
    (2026-09-11 返工批):实现前捕获标记不存在,ValueError。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_op import cw_op_buy_cards
    src = inspect.getsource(cw_op_buy_cards.run_buy_waves)
    i_cap = src.index('_seg_pin_version: int | None = None')
    assert 'current_version()' in src[i_cap:i_cap + 240], (
        '段入口捕获未读 BoardState 版本读口')
    i_decide = src.index('decide_shop_action(')
    i_rec = src.index('state_ref_version=_seg_pin_version')
    assert i_cap < i_decide, '捕获点晚于首个决策读(观测完成时点不成立)'
    assert i_rec > i_cap, '段尾落钉未传入捕获版本'


# ===== ② 动作计划逐项理由溯源 =====

def test_action_reason_from_existing_reason_field(
        tmp_path: Path, monkeypatch) -> None:
    """锁②a:动作自带 reason 字段 → 逐项 reason 原值透传(提取非新算)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [_fake_match()])
    acts = [
        BuyCard(card=ShopCard(x=100, name='某角色', cost=3), reason='line'),
        SellBench(bench_idx=0, reason='line_switch_collapse'),
        RefreshShop(cost=2, reason='r1'),
    ]
    telstate.get_recorder().record_decision(
        'r4d', 'A8', GameState(gold=30, hp=50, round_num=1, plane=1),
        '', {}, {}, acts)
    items = _rows(tmp_path)[0]['actions']
    assert [it['reason'] for it in items] == [
        'line', 'line_switch_collapse', 'r1']


def test_action_reason_route_tag_fallback(tmp_path: Path, monkeypatch) -> None:
    """锁②b:无 reason 字段的动作 → route_tag(发射臂标签,Emitted.reason
    经 bridge.decide_from_turn 透传)归一进 reason;两键同值时一致。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [_fake_match()])
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        StartBattle,
    )
    a = StartBattle()
    a.route_tag = 'battle'   # 生产链位 = bridge.decide_from_turn 透传
    telstate.get_recorder().record_decision(
        'r4e', 'A8', GameState(gold=30, hp=50, round_num=1, plane=1),
        '', {}, {}, [a])
    it = _rows(tmp_path)[0]['actions'][0]
    assert it['reason'] == 'battle'
    assert it['route_tag'] == 'battle'   # 原键保留(消费方零迁移)


def test_action_reason_auth_basis_fallback(
        tmp_path: Path, monkeypatch) -> None:
    """锁②c:LevelUp 无 reason 字段 → auth_basis(授权依据)归一进 reason。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [_fake_match()])
    telstate.get_recorder().record_decision(
        'r4f', 'A8', GameState(gold=30, hp=50, round_num=1, plane=1),
        '', {}, {}, [LevelUp(cost=10, auth_basis='dp')])
    it = _rows(tmp_path)[0]['actions'][0]
    assert it['reason'] == 'dp'


def test_action_reason_empty_honest_default(
        tmp_path: Path, monkeypatch) -> None:
    """锁②d:链上无任何理由事实 → reason=''(2026-09-08 归因遥测删除
    指令后的大多数发射形态;诚实缺省,禁新算回填)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [_fake_match()])
    telstate.get_recorder().record_decision(
        'r4g', 'A8', GameState(gold=30, hp=50, round_num=1, plane=1),
        '', {}, {}, [LevelUp(cost=10), BuyCard(card=ShopCard(x=1))])
    items = _rows(tmp_path)[0]['actions']
    assert [it['reason'] for it in items] == ['', '']


def test_action_reason_keys_declared_single_source() -> None:
    """锁②e:理由提取键序单一源(申报面):reason > route_tag > auth_basis
    > convert_reason——动作自带归因优先,发射臂标签次之,授权/豁免记录
    兜底;键序扩展只改 schema 元组。"""
    assert ACTION_REASON_SOURCE_KEYS == (
        'reason', 'route_tag', 'auth_basis', 'convert_reason')
    from sr_od.application.currency_war.telemetry.schema import (
        action_reason_of,
    )
    assert action_reason_of({'reason': 'a', 'route_tag': 'b'}) == 'a'
    assert action_reason_of({'route_tag': 'b', 'auth_basis': 'c'}) == 'b'
    assert action_reason_of({'auth_basis': 'c', 'convert_reason': 'd'}) == 'c'
    assert action_reason_of({'convert_reason': 'd'}) == 'd'
    assert action_reason_of({}) == ''
    assert action_reason_of({'reason': ''}) == ''


# ===== ③ 申报面锁(瘦身候选:候裁不执行的结构性守卫) =====

def test_slimming_candidate_fields_still_present() -> None:
    """锁③a:瘦身候选字段仍在 DecisionTrace 且现役写入缺省不变。

    R4 第一批只申报不执行(GameState 未退役前保守);本锁 = 申报面守卫——
    候裁删除前有人顺手删字段/改缺省即红。候选集语义(设计 v3.6 §3.5.1-2):
    hp/gold/plane/round_num 与行内 state 快照同义重复;三个 *_readable 标志
    的质量语义由流程侧渠道签名承接。
    """
    names = {f.name for f in fields(DecisionTrace)}
    candidates = ('hp', 'gold', 'plane', 'round_num',
                  'hp_readable', 'gold_readable', 'level_readable')
    for n in candidates:
        assert n in names, f'瘦身候选字段 {n} 被删除(候裁未过,禁执行)'
    d = asdict(DecisionTrace())
    assert d['hp_readable'] is True and d['gold_readable'] is True \
        and d['level_readable'] is True
    assert d['hp'] == 0 and d['gold'] == 0 and d['plane'] == 0 \
        and d['round_num'] == 0


def test_tier_a_deleted_fields_absent_and_shape_locked() -> None:
    """锁③d:A 档删候选 4 字段已从 DecisionTrace 删除 + 瘦身后形态封闭锁。

    A 档 4 字段(ledger_fingerprint/sess_v2_state/sess_p2_auth_intercept/
    sess_p2_auth_water)= R4 逐字段消费方审计 A 档「写端已死且全域零读」,
    经用户直迁裁定执行删除(T-217 note 2026-09-10T12:33:16 ②瘦身判据链);
    本锁钉「已删」防回填,并以封闭字段名集钉瘦身后 schema 形态(59−4=55
    面)——未申报的增删字段即红。B 档 7 字段(快照重复)仍由锁③a 守在场,
    其删除归消费方迁移裁决后的后续批。
    """
    names = {f.name for f in fields(DecisionTrace)}
    deleted = ('ledger_fingerprint', 'sess_v2_state',
               'sess_p2_auth_intercept', 'sess_p2_auth_water')
    for n in deleted:
        assert n not in names, f'A 档已删字段 {n} 重新出现(已删封闭,禁回填)'
    assert names == {
        'active_strategies', 'actions', 'b_t', 'candidate_scores',
        'difficulty', 'dp_posture', 'eval_breakdown', 'ev_arm',
        'expected_paths', 'formed_stop', 'form_ok', 'form_score',
        'gold', 'gold_readable', 'handoff', 'hp', 'hp_readable',
        'level_readable', 'phase', 'piggy_reward', 'pin_scope',
        'p1_downgrade_active', 'p26_prep_obs', 'plane',
        'posture_unfulfilled', 'refresh_trigger', 'round_num', 'run_id',
        'schema_version', 'sess_active_env', 'sess_blood_budget_rejects',
        'sess_blood_budget_refresh_rejects', 'sess_commit_scores',
        'sess_drought', 'sess_dual_track', 'sess_framework',
        'sess_p1_pair', 'sess_release_budget', 'sess_release_reason',
        'sess_release_spent', 'sess_reserve_cap', 'sess_reserve_overflow',
        'sess_terminal_release', 'shop_rejects', 'state', 'state_ref',
        'strategy_id', 'supply_pick', 'target_comp', 'ts', 'v2_bridge',
        'v2_locked_line', 'v2_mode', 'v3_intention', 'xp_expect_ledger',
    }, 'DecisionTrace 字段面漂移(瘦身后形态封闭锁;增删字段须申报并改本锁)'


def test_state_ref_fields_are_optional_trailing() -> None:
    """锁③b:state_ref/pin_scope 为末尾追加可选字段,缺省 ''——旧档案行
    经规范读端缺字段落默认值,零破坏(判读读面宽容原则,消费方兼容)。"""
    assert is_dataclass(DecisionTrace)
    f = from_dict(DecisionTrace, {'run_id': 'old_row', 'round_num': 1})
    assert f.state_ref == '' and f.pin_scope == ''
    f2 = from_dict(DecisionTrace, {'run_id': 'r', 'state_ref': 'run#3',
                                   'pin_scope': 'board_state'})
    assert f2.state_ref == 'run#3' and f2.pin_scope == 'board_state'


def test_recorder_row_action_reason_shape_regression(
        tmp_path: Path, monkeypatch) -> None:
    """锁③c:理由归一只加键不改既有键——actions 项原字段(shape)逐位
    保留,BuyCard 的 cost/char_id 富化与 __type__ 标签不受影响(判读 CLI
    旧视图按 __type__/card.* 读,零迁移)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [_fake_match()])
    telstate.get_recorder().record_decision(
        'r4h', 'A8', GameState(gold=30, hp=50, round_num=1, plane=1),
        '', {}, {},
        [BuyCard(card=ShopCard(x=100, name='某角色', cost=3), reason='line')])
    it = _rows(tmp_path)[0]['actions'][0]
    assert it['__type__'] == 'BuyCard'
    assert it['char_id'] == ''   # 非注册表名 → 诚实缺省(serialize_action 契约)
    assert it['cost'] == 3
    assert it['reason'] == 'line'
