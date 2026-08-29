"""货币战争 备战决策环 测试 —— 表驱动决策单测 + 环级防护测试(doc 15 §9)。

- 决策表(纯逻辑,喂构造 obs 断言 action):奖励收取规则序/腾席链分支/主流程/M-6 门/3合1。
- 环级(review round-1 M-6 补):mock executor + obs 序列驱动 _run_loop,断言 H-1 观察分层、
  H-2 恢复-屏蔽-bail 分型、F5 步数预算、H-3 verified 语义、M-4 白名单。
策略纯逻辑可离线测;换策略不改框架测试(doc 15 §6)。
"""
from __future__ import annotations

from types import SimpleNamespace

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war import prep_actions as pa_mod
from sr_od.application.currency_war import prep_director as pd_mod
from sr_od.application.currency_war.cw_evaluate import _card_hits_target
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.prep_actions import (
    ClickSpheres,
    DeferSpheres,
    DeployMove,
    EnsureShopOpen,
    LevelUp,
    OpenBox,
    PickBoxCard,
    PrepAction,
    RunBuyPhase,
    RunDeploy,
    RunEquip,
    SellBench,
    StartBattle,
)
from sr_od.application.currency_war.prep_director import PrepDirector, PrepObservation
from sr_od.application.currency_war.strategies.default_strategy import DefaultCwStrategy

if True:
    from test.conftest import SrTestContext


def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,策略钩子用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
        "character_build_around": [],
        "strategy_id": "default",
        "strategy_seed": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _obs(**kw) -> PrepObservation:
    """构造 PrepObservation(默认全空;P1 恒空字段 None)。"""
    o = PrepObservation()
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def _sess(**kw) -> StrategySession:
    s = StrategySession()
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _bc(slot: int, char_id: str, faction: str = '?', star: int = 1,
        pref: str = 'back') -> BenchChar:
    return BenchChar(slot=slot, char_id=char_id, faction=faction, star=star,
                     position_pref=pref)


S = DefaultCwStrategy()


# ===== §5.1 奖励收取规则序(表驱动)=====


def test_rule1_box_overlay_pick_card() -> None:
    """武装箱 overlay 开 → PickBoxCard(默认选卡)。"""
    a = S.decide_prep_action(_obs(box_overlay_open=True), _sess(), _cfg())
    assert isinstance(a, PickBoxCard) and a.card_idx is None


def test_rule2_boxes_open_first() -> None:
    """有箱 → OpenBox 优先(箱白占席;两步非一步)。"""
    a = S.decide_prep_action(_obs(boxes=[(1, None)]), _sess(), _cfg())
    assert isinstance(a, OpenBox)


def test_rule3_spheres_with_free_clicks_k() -> None:
    """有球有空席 → ClickSpheres(k=min(free, n));球多席少 k=free。"""
    a = S.decide_prep_action(_obs(spheres=[('gold', None, 40)] * 4,
                                  free_bench_slots=2), _sess(), _cfg())
    assert isinstance(a, ClickSpheres) and a.max_k == 2
    a = S.decide_prep_action(_obs(spheres=[('gold', None, 40)],
                                  free_bench_slots=3), _sess(), _cfg())
    assert isinstance(a, ClickSpheres) and a.max_k == 1


def test_rule4_spheres_no_free_enter_free_chain() -> None:
    """有球无空席 defer<2 → 进腾席链;level 满 + 无可卖 → d 步 DeferSpheres。"""
    st = GameState(level=10)
    a = S.decide_prep_action(_obs(spheres=[('gold', None, 40)], free_bench_slots=0),
                             _sess(last_state=st, last_level_obs=10), _cfg())
    assert isinstance(a, DeferSpheres)


def _full_board_bench_worth() -> tuple[list, list, GameState]:
    """ADR-0274 腾席链 b 可达 fixture:板满(cap=deployed)+ bench 有应上场件
    (同阵营 count≥2 → _should_deploy True)→ 真缺人口缺口 ≥1。"""
    st = GameState(level=5)
    bench = [_bc(1, '甲', '贝洛伯格'), _bc(2, '乙', '贝洛伯格')]
    deployed = [_bc(i, f'd{i}', '仙舟') for i in range(1, 6)]   # cap 5 全满
    return bench, deployed, st


def test_rule4_chain_b_level_up_wants_shop_open() -> None:
    """腾席链 b:真缺人口 + level<10 + shop 关 → EnsureShopOpen(gold 关态不可信,M2)。"""
    bench, deployed, st = _full_board_bench_worth()
    a = S.decide_prep_action(_obs(spheres=[('gold', None, 40)], free_bench_slots=0),
                             _sess(last_state=st, last_level_obs=5,
                                   tracked_bench_chars=bench,
                                   tracked_deployed=deployed), _cfg())
    assert isinstance(a, EnsureShopOpen)


def test_chain_b_untrusted_gold_requires_heavy_reread() -> None:
    """MED-1:shop_open=True 但 trusted=False(缓存过期)→ 仍 EnsureShopOpen(不信 gold)。"""
    bench, deployed, st = _full_board_bench_worth()
    sess = _sess(tracked_bench_chars=bench, tracked_deployed=deployed,
                 last_state=st, last_level_obs=5)
    obs = _obs(spheres=[('gold', None, 40)], free_bench_slots=0,
               deploy_vacancy=0, bench_chars=bench, shop_open=True,
               state_gold_trusted=False,   # shop 开但 state 非 fresh
               state=GameState(level=5, gold=50))
    a = S.decide_prep_action(obs, sess, _cfg())
    assert isinstance(a, EnsureShopOpen), 'untrusted gold 不得直接判 gate(会误判有金/无金)'


def test_rule5_defer_gate_falls_to_main_flow() -> None:
    """defer≥2 → 球留置进主流程(不空转,§5.1 规则 4 门)。

    free=1(有空席)隔离 M-6 门:主流程第一步 = RunBuyPhase。
    """
    a = S.decide_prep_action(_obs(spheres=[('gold', None, 40)],
                                  free_bench_slots=1),
                             _sess(defer_count=2), _cfg())
    assert isinstance(a, (RunBuyPhase, RunDeploy, RunEquip, StartBattle))


def test_no_spheres_no_boxes_main_flow() -> None:
    """球箱皆无 + 有空席 → 主流程买牌(free=0 走 M-6 门跳过,见下条)。"""
    a = S.decide_prep_action(_obs(free_bench_slots=9), _sess(), _cfg())
    assert isinstance(a, RunBuyPhase)


# ===== §5.2 腾席链分支(表驱动)=====


def test_chain_a_deploy_vacancy() -> None:
    """a. deploy 空位 + bench 阵营 count≥2(_should_deploy 满足)→ DeployMove(零成本最优)。"""
    st = GameState(level=6)
    bench = [_bc(1, '阿格莱雅', '贝洛伯格'), _bc(2, '路人', '?')]
    sess = _sess(tracked_bench_chars=bench,
                 tracked_deployed=[_bc(1, 'x', '贝洛伯格', pref='back')],
                 last_state=st, last_level_obs=6)
    obs = _obs(spheres=[('gold', None, 40)], free_bench_slots=0,
               deploy_vacancy=1, bench_chars=bench,
               front_occupied={1}, back_occupied=set(), front_size=4, back_size=6)
    a = S.decide_prep_action(obs, sess, _cfg())
    assert isinstance(a, DeployMove) and a.to_row == 'back' and a.to_slot == 1


def test_chain_b_needs_shop_open_gold() -> None:
    """b. shop 关态 gold 不可信 → EnsureShopOpen(开态重读,§5.2b M2;ADR-0274 后
    需真缺人口 fixture 才可达链 b)。"""
    bench, deployed, st = _full_board_bench_worth()
    sess = _sess(tracked_bench_chars=bench, tracked_deployed=deployed,
                 last_state=st, last_level_obs=5)
    obs = _obs(spheres=[('gold', None, 40)], free_bench_slots=0,
               deploy_vacancy=0, bench_chars=bench, shop_open=False)
    a = S.decide_prep_action(obs, sess, _cfg())
    assert isinstance(a, EnsureShopOpen)


def test_chain_c_sell_weakest() -> None:
    """c. 无空位不可升 → 卖最弱(_weakest_bench_idx;非 priority 非保护件)。"""
    bench = [_bc(1, '路人甲', '?'), _bc(2, '路人乙', '?')]
    sess = _sess(tracked_bench_chars=bench, tracked_deployed=[])
    st = GameState(level=10)   # level 10 → b 步跳过
    sess.last_state = st
    sess.last_level_obs = 10
    obs = _obs(spheres=[('gold', None, 40)], free_bench_slots=0,
               deploy_vacancy=0, bench_chars=bench, shop_open=True,
               state=GameState(level=10, gold=0))
    a = S.decide_prep_action(obs, sess, _cfg())
    assert isinstance(a, SellBench) and a.slot in (1, 2)


def test_chain_c3in1_protection_none_sellable() -> None:
    """c. 全是 3合1 进行件(同名同星≥2)→ 无可卖 → DeferSpheres(3合1 保护)。"""
    bench = [_bc(1, '飞霄', '?'), _bc(2, '飞霄', '?'), _bc(3, '三月七', '?'), _bc(4, '三月七', '?')]
    sess = _sess(tracked_bench_chars=bench, tracked_deployed=[])
    sess.last_state = GameState(level=10)
    sess.last_level_obs = 10
    obs = _obs(spheres=[('gold', None, 40)], free_bench_slots=0,
               deploy_vacancy=0, bench_chars=bench, shop_open=True,
               state=GameState(level=10, gold=0))
    a = S.decide_prep_action(obs, sess, _cfg())
    assert isinstance(a, DeferSpheres)


def test_weakest_bench_idx_protects_triplicates() -> None:
    """_weakest_bench_idx 3合1 保护(直测):同名同星 2 张保护,只返回散件。"""
    from sr_od.application.currency_war import cw_plan

    bench = [_bc(1, '飞霄'), _bc(2, '飞霄'), _bc(3, '散件')]
    st = GameState(bench=bench)
    idx = cw_plan._weakest_bench_idx(st, [])
    assert idx == 2   # 前两张保护(3合1 进行),返回散件下标
    # 全保护 → None
    st2 = GameState(bench=[_bc(1, '飞霄'), _bc(2, '飞霄')])
    assert cw_plan._weakest_bench_idx(st2, []) is None


# ===== §5.3 主流程(P1 组合;阶段位推进)=====


def test_main_flow_phase_progression() -> None:
    """主流程阶段位:买→部署→装备→出战(每步前移;阶段位环入口清零由框架)。"""
    sess = _sess()
    cfg = _cfg()
    obs = _obs(free_bench_slots=1)
    a1 = S._main_flow_step(obs, sess, cfg)
    assert isinstance(a1, RunBuyPhase) and sess.prep_phase == 1
    a2 = S._main_flow_step(obs, sess, cfg)
    assert isinstance(a2, RunDeploy) and sess.prep_phase == 2
    a3 = S._main_flow_step(obs, sess, cfg)
    assert isinstance(a3, RunEquip) and sess.prep_phase == 3
    a4 = S._main_flow_step(obs, sess, cfg)
    assert isinstance(a4, StartBattle)


def test_main_flow_m6_gate_skips_buy_when_free0() -> None:
    """M-6 门:free=0 跳过买牌(防 shop._handle_bench_full 位置式卖)→ 走腾席链 a/b/c 破满席。

    M24 卡死修(2026-08-16):旧逻辑直奔 RunDeploy,deploy-swap 卖拖拽失败(bug#1 变体)+ 金不够
    升级 → 警告不消死循环。新语义:满席先过腾席链(deploy/升级/卖最弱),链 d(Defer)落回部署段。
    mock 无 gold 真值 → 链 b EnsureShopOpen(开态重读,合法破局步)。
    """
    sess = _sess()
    a = S._main_flow_step(_obs(free_bench_slots=0), sess, _cfg())
    assert not isinstance(a, RunBuyPhase), "free=0 永不买牌(M-6 门)"
    assert isinstance(a, (DeployMove, LevelUp, EnsureShopOpen, SellBench, RunDeploy))


def test_m6_gate_chain_c_sells_weakest_when_no_gold() -> None:
    """M24 死循环破坏守卫:满席 + gold 真值 + 升级门不通 → 链 c 卖最弱(而非回 RunDeploy 空转)。"""
    bench = [_bc(1, '藿藿', '仙舟'), _bc(2, '三月七', '列车同行')]
    st = GameState(level=7, gold=4)   # 金 4 不够任何升级(52 XP 档)
    sess = _sess(tracked_bench_chars=bench, tracked_deployed=[],
                 last_state=st, last_level_obs=7)
    obs = _obs(free_bench_slots=0, deploy_vacancy=0, bench_chars=bench,
               state_gold_trusted=True, state=st)
    a = S._main_flow_step(obs, sess, _cfg())
    assert isinstance(a, SellBench), (
        f"满席+金不够升级+无 deploy 空位 → 链 c 卖最弱破局,得 {type(a).__name__}"
    )


# ===== level_up_gate 单一源 =====


def test_level_up_gate() -> None:
    """level_up_gate:level<10 + gold≥cost + (goal 说升/落后 node goal)。"""
    from sr_od.application.currency_war import cw_plan

    # level 10 封顶
    assert not cw_plan.level_up_gate(GameState(level=10, gold=999))
    # 不够钱
    assert not cw_plan.level_up_gate(GameState(level=5, gold=0))
    # 落后 node goal(早期 plane1 r1 target_level 高)+ 够钱 → 升
    assert cw_plan.level_up_gate(GameState(level=2, gold=50, plane=1, round_num=1))


# ===== 框架杂项 =====


def test_action_key_param_granularity() -> None:
    """action_key 屏蔽粒度 = 类型+参数(SellBench(3) ≠ SellBench(5),§13.2)。"""
    k3, k5 = pa_mod.action_key(SellBench(slot=3)), pa_mod.action_key(SellBench(slot=5))
    assert k3 != k5 and 'SellBench' in k3
    assert pa_mod.action_key(StartBattle()) == 'StartBattle'


def test_session_counters() -> None:
    """StrategySession 环级字段默认值(defer/prep_phase 环入口清零;bail 计数局级)。"""
    s = _sess()
    assert s.defer_count == 0 and s.prep_phase == 0
    assert s.bail_reason_counts == {}


# ===== 环级测试(review M-6):mock executor + obs 序列驱动 _run_loop =====


class _FakeExecutor:
    """脚本化执行器:默认返回 default;可按动作类型覆盖。记录调用序(动作键)。"""

    def __init__(self, results=None, default=(True, 'ok')):
        self.results = dict(results or {})
        self.default = default
        self.calls: list[str] = []

    def validate(self, action):
        return None   # 环级测试聚焦环逻辑;参数校验语义走真 PrepActionExecutor 单测

    def execute(self, action):
        self.calls.append(pa_mod.action_key(action))
        res = self.results.get(type(action), self.default)
        return res(action) if callable(res) else res


def _make_director(monkeypatch, executor) -> PrepDirector:
    """构造绕过 __init__ 的 PrepDirector(mock 全 IO;环逻辑单测专用)。"""
    d = PrepDirector.__new__(PrepDirector)
    d.ctx = SimpleNamespace(current_instance_idx=99)   # _run_loop 读 config 用
    d._executor = executor
    d._steps = 0
    d._stall = 0
    d._fail_counts = {}
    d._blocked = set()
    d._recovered = set()
    d._recovery_closed_known = {}
    d._recovery_tried = False
    d._bench_pts = []
    d._cached_state = None
    d._cached_bench = []
    d._cached_deployed = []
    d._cached_vacancy = 0
    d._cached_gold_trusted = False
    # 光标 parking no-op(2026-08-16 重 IO 动作,mock 环境无 controller)
    monkeypatch.setattr(d, 'park_cursor', lambda *a, **kw: None)
    import sr_od.application.currency_war.currency_war_config as cfg_mod
    monkeypatch.setattr(cfg_mod, 'CurrencyWarConfig', lambda idx: _cfg())
    monkeypatch.setattr(pd_mod.time, 'sleep', lambda s: None)   # 恢复等待不拖测试
    return d


def _seq_observe(seq):
    """_observe 替身:按序返回 obs(耗尽复用最后个);记录 heavy 调用序(分层断言用)。

    screen 关键字收下不消费(r344:_observe 新增可选 gate 帧参数,替身对齐签名)。"""
    state = {'i': 0, 'heavy_calls': []}

    def _obs_at(heavy: bool, screen=None):
        state['heavy_calls'].append(heavy)
        i = min(state['i'], len(seq) - 1) if seq else 0
        state['i'] += 1
        return seq[i] if seq else PrepObservation()
    _obs_at.calls = state
    return _obs_at


def _fake_snapshot():
    """最小 confident 快照(新环观察端口替身用;离线免真值合成)。"""
    from sr_od.application.currency_war.decision_v2.contracts import (
        Snapshot,
        SubstateClassification,
    )
    return Snapshot(classification=SubstateClassification(
        name='prep_shop', evidence=('test',), confident=True))


def _stub_snapshot_from_obs(monkeypatch) -> None:
    """新环 obs→快照 替身(W620 批 1:生产路径 = DirectorV2 环)。"""
    import sr_od.application.currency_war.decision_v2.adapter as _adapter
    monkeypatch.setattr(_adapter, 'snapshot_from_obs',
                        lambda obs, session: _fake_snapshot())


class _ScriptStrategy:
    """脚本化策略替身:按序返回动作(驱动新环管线;防永动机)。"""

    def __init__(self, actions):
        self._acts = list(actions)
        self.seen: list[str] = []

    def decide_prep_action(self, obs, session, config):
        a = self._acts.pop(0) if self._acts else StartBattle()
        self.seen.append(type(a).__name__)
        if len(self.seen) > 12:
            raise RuntimeError('环未如预期推进(可能永动机)')
        return a


def test_loop_h1_heavy_reread_after_action(monkeypatch) -> None:
    """H-1 回归(新环管线):执行过的游戏动作后 heavy 重读(review H-1 定稿语义)。

    W620 批 1 起 _run_loop = DirectorV2 环(引擎批尾 heavy 语义;旧环断言
    「EnsureShopOpen→LevelUp 腾席链」归策略单测,此处锁环的观察分层)。
    """
    _stub_snapshot_from_obs(monkeypatch)
    ex = _FakeExecutor(default=(True, 'ok'))
    d = _make_director(monkeypatch, ex)
    observe = _seq_observe([])
    monkeypatch.setattr(d, '_observe', observe)
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)
    strat = _ScriptStrategy([EnsureShopOpen(), LevelUp(), StartBattle()])
    match = SimpleNamespace(strategy=strat, session=_sess())
    result = d._run_loop(match)
    assert strat.seen[:3] == ['EnsureShopOpen', 'LevelUp', 'StartBattle'], \
        f'动作序应逐脚本推进,实得 {strat.seen}'
    hc = observe.calls['heavy_calls']
    assert hc[0] is True    # 环入口 heavy
    assert hc[1] is True    # EnsureShopOpen 执行后 heavy(H-1 旧 bug 为 False)
    assert all(hc), f'动作后一律 heavy,实得 {hc}'   # 出口在 StartBattle 落地,无后续观察
    assert '出战' in (result.status or ''), f'出战落地应正常出口,实得 {result.status}'


def test_loop_h2_state_failure_blocks_action(monkeypatch) -> None:
    """H-2 回归(新环引擎):连败 2 → 恢复(无弹层)→ 再败 2 → 屏蔽;重提案被拒。"""
    monkeypatch.setattr(pd_mod, 'try_recovery', lambda op, ctx: ('点空白兜底', False))
    _stub_snapshot_from_obs(monkeypatch)
    ex = _FakeExecutor(default=(False, 'fail'))
    d = _make_director(monkeypatch, ex)
    monkeypatch.setattr(d, '_observe', _seq_observe([]))
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)
    strat = _ScriptStrategy([SellBench(slot=1)] * 8)
    match = SimpleNamespace(strategy=strat, session=_sess())
    d._run_loop(match)
    sells = [c for c in ex.calls if c.startswith('SellBench')]
    # 连败2 → 恢复 → 连败2 → 屏蔽:SellBench 最多执行 4 次,第 5 次提案起被拒(stall 路径)
    assert len(sells) <= 4, f'H-2 回归:屏蔽后不应继续执行,实执行 {len(sells)}: {ex.calls}'
    assert any(c.startswith('StartBattle') for c in ex.calls)   # F5 强制出战兜底


def test_loop_h2_stubborn_overlay_bails(monkeypatch) -> None:
    """H-2 回归·分型(新环引擎):恢复关过已知弹层仍败 → bail 让位(环出口)。"""
    monkeypatch.setattr(pd_mod, 'try_recovery', lambda op, ctx: ('ESC 关消耗品详情', True))
    _stub_snapshot_from_obs(monkeypatch)
    ex = _FakeExecutor(default=(False, 'fail'))
    d = _make_director(monkeypatch, ex)
    monkeypatch.setattr(d, '_observe', _seq_observe([]))
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)
    strat = _ScriptStrategy([SellBench(slot=1)] * 6)
    match = SimpleNamespace(strategy=strat, session=_sess())
    result = d._run_loop(match)
    assert 'BailToOuter' in (result.status or ''), f'弹层顽固应 bail 让位,实得 {result.status}'
    sells = [c for c in ex.calls if c.startswith('SellBench')]
    assert len(sells) == 4, f'连败2+恢复+连败2 即 bail(执行 4 次),实 {len(sells)}: {ex.calls}'


def test_loop_forced_battle_on_step_budget(monkeypatch) -> None:
    """F5(新环引擎):步数预算耗尽 → 强制出战(Defer 计步不计 stall,靠 MAX_STEPS 兜底)。"""
    from sr_od.application.currency_war.decision_v2.director_v2 import DirectorV2
    monkeypatch.setattr(pd_mod, 'try_recovery', lambda op, ctx: ('点空白兜底', False))
    monkeypatch.setattr(DirectorV2, 'MAX_STEPS', 4)
    _stub_snapshot_from_obs(monkeypatch)

    ex = _FakeExecutor(default=(True, 'ok'))
    d = _make_director(monkeypatch, ex)
    monkeypatch.setattr(d, '_observe', _seq_observe([]))
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)
    strat = _ScriptStrategy([DeferSpheres()] * 10)
    match = SimpleNamespace(strategy=strat, session=_sess())
    result = d._run_loop(match)
    assert '强制出战' in (result.status or ''), f'步数耗尽应强制出战,实得 {result.status}'


def test_executor_h3_sphere_verified_only(test_context: SrTestContext,
                                          monkeypatch) -> None:
    """H-3 回归(executor):点击后球数不减 → progressed=False;球减少 → True。"""
    import numpy as np

    op = PrepDirector(test_context)
    ex = pa_mod.PrepActionExecutor(op, test_context)
    monkeypatch.setattr(test_context.controller, 'mouse_move', lambda p: True, raising=False)   # MockController 缺 stub
    fake_screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr(op, 'screenshot', lambda: fake_screen)
    spheres = [('gold', Point(100, 100), 40)] * 3
    monkeypatch.setattr(pa_mod, 'read_reward_spheres', lambda ctx, screen: list(spheres))
    monkeypatch.setattr(pa_mod, 'read_supply_boxes', lambda ctx, screen: [])
    progressed, detail = ex.execute(pa_mod.ClickSpheres(max_k=2))
    assert not progressed, f'H-3:球未消失应 False,实 {progressed} ({detail})'
    # 点后球减少 → True
    state = {'n': 3}
    monkeypatch.setattr(pa_mod, 'read_reward_spheres',
                        lambda ctx, screen: list(spheres[:state['n']]))
    orig_click = test_context.controller.click

    def _shrinking_click(pos, *a, **k):
        state['n'] = max(0, state['n'] - 1)
        return orig_click(pos, *a, **k)

    monkeypatch.setattr(test_context.controller, 'click', _shrinking_click)
    progressed2, _ = ex.execute(pa_mod.ClickSpheres(max_k=2))
    assert progressed2, '球减少应算进展'


def test_validate_rejects_unknown_action_type(test_context: SrTestContext) -> None:
    """M-4 回归:未知类型走参数非法路径(validate 报错,不进 execute 的 fail 循环)。"""
    ex = pa_mod.PrepActionExecutor(PrepDirector(test_context), test_context)

    class RogueAction(PrepAction):
        pass

    err = ex.validate(RogueAction())
    assert err is not None and '未知动作类型' in err


# ===== W209j 刹车语义锁(run 27 停机事故第三层,ADR-0388)=====
# 实证链:14:09:08 Deploy 钩子 stop_running → 14:09:14「出战成功」(CW 备战
# 不自动出战,出战必是 bot 点的)= 停 bot 后 director 环仍落地动作。
# 判据 = last_run_result 非空(start_running 清 None/stop 写入;run_state
# STOP 是 idle 初始态不能直接用——离线测试 ctx 恒 STOP 会全拒)。

class _StoppedRunCtx:
    """运行中被停的 run_context 替身:last_run_result 已写入。"""

    def __init__(self) -> None:
        self.last_run_result = object()   # 非 None = 本次运行被请求停止
        self.is_context_stop = True


def test_executor_brake_rejects_action_when_stopped(
        test_context: SrTestContext, monkeypatch) -> None:
    """第二层锁:executor 拒绝执行任何动作(含 StartBattle),零点击落地。"""
    from sr_od.application.currency_war.prep_actions import StartBattle
    op = PrepDirector(test_context)
    ex = pa_mod.PrepActionExecutor(op, test_context)
    clicked: list = []
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda p, *a, **k: clicked.append(p), raising=False)
    monkeypatch.setattr(test_context, 'run_context', _StoppedRunCtx())
    progressed, detail = ex.execute(StartBattle())
    assert not progressed and '已停止' in detail
    assert not clicked, '停机后不得有任何点击落地(W209j 刹车)'


def test_director_loop_brake_before_each_step(monkeypatch, test_context) -> None:
    """第一层锁:环顶查停机标志 → 不再发动作直接收口(run 27 形态:Deploy
    停后不发 StartBattle)。"""
    match = SimpleNamespace(
        strategy=SimpleNamespace(
            decide_prep_action=lambda o, s, c: pa_mod.StartBattle()),
        session=_sess())
    ex = _FakeExecutor(default=(True, '不该被执行'))
    d = _make_director(monkeypatch, ex)
    # ctx 挂运行中被停的 run_context(_make_director 的 SimpleNamespace ctx
    # 无该属性 → getattr None = 不拦;测试显式挂上)
    d.ctx.run_context = _StoppedRunCtx()
    d.ctx.controller = getattr(test_context, 'controller', None)
    monkeypatch.setattr(d, '_observe', _seq_observe([]))
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)
    result = d._run_loop(match)
    assert '已停止' in (result.status or ''), \
        f'环顶刹车应收口停止态,实得 {result.status}'
    assert not ex.calls, '停机标志已设后不得再发任何动作'


def test_brake_inactive_when_running(test_context: SrTestContext, monkeypatch) -> None:
    """正常运行(last_run_result=None,idle/运行中未停)不误拦——刹车判据
    不把离线测试(ctx run_state=STOP 初始态)误判为停机。"""
    from types import SimpleNamespace

    class _IdleRunCtx:
        last_run_result = None
        is_context_stop = True   # idle 初始态也是 STOP——但未在运行,不拦

    monkeypatch.setattr(test_context, 'run_context', _IdleRunCtx())
    op = PrepDirector(test_context)
    ex = pa_mod.PrepActionExecutor(op, test_context)
    monkeypatch.setattr(test_context.controller, 'mouse_move', lambda p: True,
                        raising=False)
    # 用控制流动作(BailToOuter)验证 execute 未被刹车误拦
    progressed, detail = ex.execute(pa_mod.BailToOuter(reason='t'))
    assert '刹车' not in detail, f'idle 态不得误拦: {detail}'


def test_weakest_bench_protects_same_star_only() -> None:
    """L-5 回归:3合1 保护按 (char_id, star) —— 同名不同星不保护。"""
    from sr_od.application.currency_war import cw_plan

    bench2 = [_bc(1, '飞霄', star=1), _bc(2, '飞霄', star=1), _bc(3, '散件', star=1)]
    assert cw_plan._weakest_bench_idx(GameState(bench=bench2), []) == 2
    # 同名不同星:两单张不构成进度 → 都可候选(不保护)
    bench_mixed = [_bc(1, '飞霄', star=1), _bc(2, '飞霄', star=2), _bc(3, '散件', star=1)]
    idx = cw_plan._weakest_bench_idx(GameState(bench=bench_mixed), [])
    assert idx is not None and idx != -1   # 有候选(不因同名保护而 None)

def test_observe_light_reuses_heavy_cache(monkeypatch, test_context: SrTestContext) -> None:
    """LOW-3:_observe 分支直测 —— light 步沿用 heavy 缓存(state/trusted/vacancy)。"""
    d = _make_director(monkeypatch, _FakeExecutor())
    d.ctx = test_context
    monkeypatch.setattr(d, 'screenshot', lambda: None)
    monkeypatch.setattr(d, 'round_by_find_area',
                        lambda scr, scr_name, area, **kw: SimpleNamespace(
                            is_success=(scr_name == '货币战争-备战-开商店')))   # 模拟 shop 开
    monkeypatch.setattr(pd_mod, 'read_reward_spheres', lambda c, s: [])
    monkeypatch.setattr(pd_mod, 'read_supply_boxes', lambda c, s: [])
    monkeypatch.setattr(pd_mod, 'cw_identity_obs_read_tomes', lambda c, s: [])
    monkeypatch.setattr(pd_mod, 'row_area_centers', lambda c, p: [Point(i, i) for i in range(9)]
                        if p == '备战栏' else [])
    monkeypatch.setattr(pd_mod, 'slot_occupied', lambda s, x, y: False)
    monkeypatch.setattr(pd_mod, 'ensure_portrait_templates', lambda c: None)
    heavy_state = GameState(gold=42, level=5)
    # r331:heavy 读已上收 observe_full——打桩随迁(patch 其模块)
    from sr_od.application.currency_war import cw_observe_full as of_mod
    monkeypatch.setattr(of_mod, 'ensure_portrait_templates', lambda c: None)
    monkeypatch.setattr(of_mod, 'read_game_state', lambda c, s: heavy_state)
    monkeypatch.setattr(of_mod, 'read_node_sequence', lambda c, s: None)
    monkeypatch.setattr(of_mod, 'read_shop_cards', lambda c, s: [])
    monkeypatch.setattr(pd_mod, 'read_deploy_cap', lambda c, s: None)
    monkeypatch.setattr(pd_mod, 'read_deployed_count', lambda c, s: None)
    o1 = d._observe(heavy=True)
    assert o1.state is heavy_state
    assert o1.state_gold_trusted is True   # shop 开态 heavy 读 → trusted
    o2 = d._observe(heavy=False)
    assert o2.state is heavy_state   # LOW-3:light 沿用缓存(旧 bug 为 None)
    assert o2.state_gold_trusted is True   # MED-1:trusted 位随缓存 state 带出
    assert o2.deploy_vacancy == o1.deploy_vacancy


def test_observe_gold_zero_reread(monkeypatch, test_context: SrTestContext) -> None:
    """MED-2:shop 开态 gold 读 0(间歇漏读)→ 重读取真值(防链 b 误判无金误卖)。"""
    d = _make_director(monkeypatch, _FakeExecutor())
    d.ctx = test_context
    shots = {'n': 0}

    def _screenshot():
        shots['n'] += 1
        return None

    monkeypatch.setattr(d, 'screenshot', _screenshot)
    monkeypatch.setattr(d, 'round_by_find_area',
                        lambda scr, scr_name, area, **kw: SimpleNamespace(
                            is_success=(scr_name == '货币战争-备战-开商店')))
    monkeypatch.setattr(pd_mod, 'read_reward_spheres', lambda c, s: [])
    monkeypatch.setattr(pd_mod, 'read_supply_boxes', lambda c, s: [])
    monkeypatch.setattr(pd_mod, 'cw_identity_obs_read_tomes', lambda c, s: [])
    monkeypatch.setattr(pd_mod, 'row_area_centers', lambda c, p: [Point(i, i) for i in range(9)]
                        if p == '备战栏' else [])
    monkeypatch.setattr(pd_mod, 'slot_occupied', lambda s, x, y: False)
    monkeypatch.setattr(pd_mod, 'ensure_portrait_templates', lambda c: None)
    st0 = GameState(gold=0, level=5)   # read_game_state 读到 gold=0(漏读)
    # r331:heavy 读在 observe_full——打桩随迁;gold==0 重读
    # 用 read_game_state(重截图;首帧 0,重读返真值 55)
    from sr_od.application.currency_war import cw_observe_full as of_mod
    monkeypatch.setattr(of_mod, 'ensure_portrait_templates', lambda c: None)
    _calls = {'n': 0}

    def _gs(c, s):
        _calls['n'] += 1
        return st0 if _calls['n'] == 1 else GameState(gold=55, level=5)
    monkeypatch.setattr(of_mod, 'read_game_state', _gs)
    monkeypatch.setattr(of_mod, 'read_node_sequence', lambda c, s: None)
    monkeypatch.setattr(of_mod, 'read_shop_cards', lambda c, s: [])
    monkeypatch.setattr(pd_mod, 'read_deploy_cap', lambda c, s: None)
    monkeypatch.setattr(pd_mod, 'read_deployed_count', lambda c, s: None)
    o = d._observe(heavy=True)
    assert o.state.gold == 55, 'MED-2:gold=0 应触发重读取真值'


def test_levelup_raw_read_no_fallback(monkeypatch, test_context: SrTestContext) -> None:
    """MED-8:_read_level_raw 无 _expected_level 兜底(漏读返 None,不造假值)。"""
    from sr_od.application.currency_war.prep_actions import _read_level_raw

    # 直读失读(_read_level_raw 委托 read_level_raw_opt,patch 该缝)→ None
    import sr_od.application.currency_war.cw_observation as cwo
    monkeypatch.setattr(cwo, 'read_level_raw_opt', lambda ctx, scr: None)
    assert _read_level_raw(test_context, None) is None
def test_composite_reads_success_field(test_context: SrTestContext,
                                       monkeypatch) -> None:
    """live 回归(2026-08-14):_run_composite 读 OperationResult.success(非 is_success)。"""
    from sr_od.application.currency_war import prep_actions as pa
    from sr_od.application.currency_war.prep_actions import RunBuyPhase

    ex = pa.PrepActionExecutor(PrepDirector(test_context), test_context)

    class _OpResult:   # 形状对齐 one_dragon OperationResult(success 字段)
        def __init__(self) -> None:
            self.success = True
            self.status = 'plan 买2张 升1次 刷0次'

    class _FakeOp:
        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            return _OpResult()

    class _FakeModule:
        BuyShopCards = _FakeOp

    import importlib
    real_import = importlib.import_module
    monkeypatch.setattr(importlib, 'import_module',
                        lambda path: _FakeModule if path.endswith('.shop') else real_import(path))
    ok, detail = ex.execute(RunBuyPhase())
    assert ok, f'success=True 的组合结果必须判成功(live bug:旧读 is_success 恒 False): {detail}'

def test_rule3_shop_open_closes_shop_first() -> None:
    """live 回归(2026-08-14 1-2):商店开态奖励面板与概率表按钮重叠 → 假球误开弹窗。"""
    from sr_od.application.currency_war.prep_actions import EnsureShopClosed
    obs = _obs(spheres=[('gold', None, 40)] * 2, free_bench_slots=3, shop_open=True)
    a = S.decide_prep_action(obs, _sess(), _cfg())
    assert isinstance(a, EnsureShopClosed), '商店开态须先关店再收球(防假球点击)'
    obs2 = _obs(spheres=[('gold', None, 40)] * 2, free_bench_slots=3, shop_open=False)
    a2 = S.decide_prep_action(obs2, _sess(), _cfg())
    assert isinstance(a2, ClickSpheres) and a2.max_k == 2

def test_level_up_clamps_phantom_jump(test_context, monkeypatch) -> None:
    """live 幽灵 lv10 回归(2026-08-15):_level_up 接受窗钳 before+2 —— 6→10 不确认成功。"""
    import numpy as np

    from sr_od.application.currency_war import prep_actions as pa_mod

    op = PrepDirector(test_context)
    ex = pa_mod.PrepActionExecutor(op, test_context)
    monkeypatch.setattr(test_context.controller, 'mouse_move', lambda p: True, raising=False)
    fake = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr(op, 'screenshot', lambda: fake)
    # 基线读 6(真),循环读 10(XP 数字混入)→ 窗外 → 不确认
    reads = {'n': 0}

    def _raw(ctx, screen):
        reads['n'] += 1
        return 6 if reads['n'] == 1 else 10

    monkeypatch.setattr(pa_mod, '_read_level_raw', _raw)
    sess = _sess(last_level_obs=6, last_state=GameState(level=6))
    monkeypatch.setattr(op.ctx if hasattr(op, 'ctx') else test_context, 'cw_match', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    ok, detail = ex._level_up()
    assert not ok, f'幽灵 6→10 不得确认成功(窗外): {detail}'

def test_offtarget_sell_protects_core_enablers() -> None:
    """live 回归(2026-08-15 M1):comp 核心辅助(阵营∉comp 阵营)不得当 off-target 卖。

    列车同行 core 含 花火(其阵营=战技点/盛会之星,∉列车同行)—— M1 位面2 deploy-swap
    把花火卖掉 → 板成型度崩(列车同行4→1)。target 判定须含 core_chars(ADR-0103 同语义)。
    """
    # 纯逻辑:_is_tgt_char 语义在 deploy_bench 闭包内 —— 用 _card_hits_target
    # 同语义对照(它已含 core 命中):花火 ∈ core_chars → True(即便阵营不交集)。
    from sr_od.application.currency_war.cw_comps import get_comp

    comp = get_comp('列车同行')
    assert comp is not None and '花火' in comp.core_chars
    # 花火:core 命中(阵营不交集也应 True)
    assert _card_hits_target('花火', '盛会之星', comp) is True
    # 普通盛会之星单位(非 core):按阵营不交集 → False(可卖)
    assert _card_hits_target('陌生角色', '盛会之星', comp) is False


# ===== ADR-0136 M16 死循环修复(未达上限弹窗勾选 + 备战席已满警告感知) =====
def test_start_battle_dialog_checkbox_equipped(monkeypatch) -> None:
    """_start_battle 弹窗处理 = 勾选(幂等)+确认(对齐 HandleDeployNotFull;M16 只确认→每次出战都弹)。"""
    import sr_od.application.currency_war.prep_actions as pa

    clicks: list[tuple[int, int]] = []
    screens = {'iter': 0}

    class _FakeArea:
        def __init__(self, ok: bool): self.is_success = ok

    class _Dir:
        def screenshot(self):
            screens['iter'] += 1
            return object()
        def round_by_find_area(self, scr, screen, area):
            # iter1-2: 出战按钮/弹窗在;iter3+: 弹窗消失+备战标识消失 = 出战成功
            if area == '按钮-出战':
                return _FakeArea(screens['iter'] == 1)
            if area == '标识-未达上限警告':
                return _FakeArea(screens['iter'] == 2)
            if area == '备战标识-购买经验':
                return _FakeArea(screens['iter'] < 3)   # iter≥3 消失
            return _FakeArea(False)
        def save_screenshot(self, prefix=None): pass

    class _Ctrl:
        def mouse_move(self, p): pass
        def click(self, p): clicks.append((p.x, p.y))

    class _Ctx:
        controller = _Ctrl()

    area_centers = {
        ('按钮-出战', None): None,
        ('勾选-本局不再提示', '货币战争-未达上限警告'): None,   # None → fallback 常量
        ('按钮-确认', '货币战争-未达上限警告'): None,
    }
    monkeypatch.setattr(pa, 'area_center', lambda ctx, name, screen=None: area_centers.get((name, screen)))
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._op = _Dir(); ex._ctx = _Ctx()
    ok, detail = pa.PrepActionExecutor._start_battle(ex)
    assert ok, detail
    # iter2 弹窗:勾选(912,589)先于确认(1159,653)—— M16 修复核心断言
    assert (912, 589) in clicks and (1159, 653) in clicks
    i_check = clicks.index((912, 589))
    i_confirm = clicks.index((1159, 653))
    assert i_check < i_confirm, "勾选必须先于确认(否则整局每次出战都弹)"

