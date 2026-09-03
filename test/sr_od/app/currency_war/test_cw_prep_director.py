"""test_cw_prep_director 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- test_prep_director: test_prep_director.py
- test_prep_action_whitelist: test_prep_action_whitelist.py
- test_prep_skip_substate: test_prep_skip_substate.py
- adr0269_prep_two_stage: test_cw_adr0269_prep_two_stage.py
- w588_director_v2: test_cw_w588_director_v2.py
- w817_recovery_precheck: test_cw_w817_recovery_precheck.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== test_prep_director ====================
from types import SimpleNamespace

import sr_od.application.currency_war.kernel.cw_prep_actions as pv
from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war import prep_actions as pa_mod
from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep as pd_mod
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.kernel.cw_deploy_seat import _card_hits_target
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    DeferSpheres,
    DeployMove,
    LevelUp,
    OpenBox,
    OpenShop,
    PickBoxCard,
    PrepAction,
    PrepObservation,
    RunDeploy,
    RunEquip,
    SellBench,
    StartBattle,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import CwScreenPrep

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


S = DecisionV2Strategy()


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
    """腾席链 b:真缺人口 + level<10 + shop 关 → OpenShop(read_only)
    (gold 关态不可信,M2;W970 批 C EnsureShopOpen 退役,§4.3.6)。"""
    bench, deployed, st = _full_board_bench_worth()
    a = S.decide_prep_action(_obs(spheres=[('gold', None, 40)], free_bench_slots=0),
                             _sess(last_state=st, last_level_obs=5,
                                   tracked_bench_chars=bench,
                                   tracked_deployed=deployed), _cfg())
    assert isinstance(a, OpenShop) and a.read_only


def test_chain_b_untrusted_gold_requires_heavy_reread() -> None:
    """MED-1:shop_open=True 但 trusted=False(缓存过期)→ 仍 OpenShop(read_only)(不信 gold)。"""
    bench, deployed, st = _full_board_bench_worth()
    sess = _sess(tracked_bench_chars=bench, tracked_deployed=deployed,
                 last_state=st, last_level_obs=5)
    obs = _obs(spheres=[('gold', None, 40)], free_bench_slots=0,
               deploy_vacancy=0, bench_chars=bench, shop_open=True,
               state_gold_trusted=False,   # shop 开但 state 非 fresh
               state=GameState(level=5, gold=50))
    a = S.decide_prep_action(obs, sess, _cfg())
    assert isinstance(a, OpenShop) and a.read_only, 'untrusted gold 不得直接判 gate(会误判有金/无金)'


def test_rule5_defer_gate_falls_to_main_flow() -> None:
    """defer≥2 → 球留置进主流程(不空转,§5.1 规则 4 门)。

    free=1(有空席)隔离 M-6 门:主流程第一步 = OpenShop(买牌段显式开店意图,
    W970 批 C RunBuyPhase 解体)。
    """
    a = S.decide_prep_action(_obs(spheres=[('gold', None, 40)],
                                  free_bench_slots=1),
                             _sess(defer_count=2), _cfg())
    assert isinstance(a, (OpenShop, RunDeploy, RunEquip, StartBattle))


def test_no_spheres_no_boxes_main_flow() -> None:
    """球箱皆无 + 有空席 → 主流程买牌(free=0 走 M-6 门跳过,见下条)。"""
    a = S.decide_prep_action(_obs(free_bench_slots=9), _sess(), _cfg())
    assert isinstance(a, OpenShop) and not a.read_only


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
    """b. shop 关态 gold 不可信 → OpenShop(read_only)(开态重读,§5.2b M2/
    §4.3.6;ADR-0274 后需真缺人口 fixture 才可达链 b)。"""
    bench, deployed, st = _full_board_bench_worth()
    sess = _sess(tracked_bench_chars=bench, tracked_deployed=deployed,
                 last_state=st, last_level_obs=5)
    obs = _obs(spheres=[('gold', None, 40)], free_bench_slots=0,
               deploy_vacancy=0, bench_chars=bench, shop_open=False)
    a = S.decide_prep_action(obs, sess, _cfg())
    assert isinstance(a, OpenShop) and a.read_only


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
    from sr_od.application.currency_war.kernel import cw_deploy_seat as seat

    bench = [_bc(1, '飞霄'), _bc(2, '飞霄'), _bc(3, '散件')]
    st = GameState(bench=bench)
    idx = seat._weakest_bench_idx(st, [])
    assert idx == 2   # 前两张保护(3合1 进行),返回散件下标
    # 全保护 → None
    st2 = GameState(bench=[_bc(1, '飞霄'), _bc(2, '飞霄')])
    assert seat._weakest_bench_idx(st2, []) is None


# ===== §5.3 主流程(P1 组合;阶段位推进)=====


def test_main_flow_phase_progression() -> None:
    """主流程阶段位:买→部署→装备→出战(每步前移;阶段位环入口清零由框架)。"""
    sess = _sess()
    cfg = _cfg()
    obs = _obs(free_bench_slots=1)
    a1 = S._main_flow_step(obs, sess, cfg)
    assert isinstance(a1, OpenShop) and not a1.read_only and sess.prep_phase == 1
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
    mock 无 gold 真值 → 链 b OpenShop(read_only)(开态重读,合法破局步)。
    """
    sess = _sess()
    a = S._main_flow_step(_obs(free_bench_slots=0), sess, _cfg())
    assert not isinstance(a, OpenShop), "free=0 永不买牌(M-6 门)"
    assert isinstance(a, (DeployMove, LevelUp, OpenShop, SellBench, RunDeploy))


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
    from sr_od.application.currency_war.kernel import cw_deploy_seat as seat

    # level 10 封顶
    assert not seat.level_up_gate(GameState(level=10, gold=999))
    # 不够钱
    assert not seat.level_up_gate(GameState(level=5, gold=0))
    # 落后 node goal(早期 plane1 r1 target_level 高)+ 够钱 → 升
    assert seat.level_up_gate(GameState(level=2, gold=50, plane=1, round_num=1))


# ===== 框架杂项 =====


def test_action_key_param_granularity() -> None:
    """action_key 屏蔽粒度 = 类型+参数(SellBench(3) ≠ SellBench(5),§13.2)。"""
    k3, k5 = pv.action_key(SellBench(slot=3)), pv.action_key(SellBench(slot=5))
    assert k3 != k5 and 'SellBench' in k3
    assert pv.action_key(StartBattle()) == 'StartBattle'


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
        self.calls.append(pv.action_key(action))
        res = self.results.get(type(action), self.default)
        return res(action) if callable(res) else res


def _make_director(monkeypatch, executor) -> CwScreenPrep:
    """构造绕过 __init__ 的 CwScreenPrep(mock 全 IO;环逻辑单测专用)。"""
    d = CwScreenPrep.__new__(CwScreenPrep)
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
    from sr_od.application.currency_war.decision.decision_v2.contracts import (
        Snapshot,
        SubstateClassification,
    )
    return Snapshot(classification=SubstateClassification(
        name='prep_shop', evidence=('test',), confident=True))


def _stub_snapshot_from_obs(monkeypatch) -> None:
    """新环 obs→快照 替身(W620 批 1:生产路径 = DirectorV2 环)。"""
    import sr_od.application.currency_war.decision_assembly as _adapter
    monkeypatch.setattr(_adapter, 'snapshot_from_obs',
                        lambda obs, session: _fake_snapshot())


class _ScriptStrategy:
    """脚本化策略替身:按序返回动作(驱动新环管线;防永动机)。"""

    def __init__(self, actions):
        self._acts = list(actions)
        self.seen: list[str] = []

    def decide_prep_screen(self, session, config):
        # W971 §2 黑板接口(P2):生产 cw_screen_prep 写 session.prep_obs_frame
        # 后调本入口(替身不消费帧,仅按脚本吐动作)。
        a = self._acts.pop(0) if self._acts else StartBattle()
        self.seen.append(type(a).__name__)
        if len(self.seen) > 12:
            raise RuntimeError('环未如预期推进(可能永动机)')
        return a



# (原内环机制锁 H-1/H-2×2/F5 强制出战/环顶刹车 ×5 随内环拆除删除(W971 P3b
#  返工定稿):单轮无步数预算/屏蔽/bail;停机刹车由执行器层锁(上方)+ 外循环
#  框架每轮 stop 检查承担;无进展留证 = 外循环 stall 防线(test_cw_w971_p3b_seg2)。)








def test_executor_h3_sphere_verified_only(test_context: SrTestContext,
                                          monkeypatch) -> None:
    """H-3 回归(executor):点击后球数不减 → progressed=False;球减少 → True。"""
    import numpy as np

    op = CwScreenPrep(test_context)
    ex = pa_mod.PrepActionExecutor(op, test_context)
    monkeypatch.setattr(test_context.controller, 'mouse_move', lambda p: True, raising=False)   # MockController 缺 stub
    fake_screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr(op, 'screenshot', lambda: fake_screen)
    spheres = [('gold', Point(100, 100), 40)] * 3
    monkeypatch.setattr(pa_mod, 'read_reward_spheres', lambda ctx, screen: list(spheres))
    monkeypatch.setattr(pa_mod, 'read_supply_boxes', lambda ctx, screen: [])
    progressed, detail = ex.execute(pv.ClickSpheres(max_k=2))
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
    progressed2, _ = ex.execute(pv.ClickSpheres(max_k=2))
    assert progressed2, '球减少应算进展'


def test_validate_rejects_unknown_action_type(test_context: SrTestContext) -> None:
    """M-4 回归:未知类型走参数非法路径(validate 报错,不进 execute 的 fail 循环)。"""
    ex = pa_mod.PrepActionExecutor(CwScreenPrep(test_context), test_context)

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
    from sr_od.application.currency_war.kernel.cw_prep_actions import StartBattle
    op = CwScreenPrep(test_context)
    ex = pa_mod.PrepActionExecutor(op, test_context)
    clicked: list = []
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda p, *a, **k: clicked.append(p), raising=False)
    monkeypatch.setattr(test_context, 'run_context', _StoppedRunCtx())
    progressed, detail = ex.execute(StartBattle())
    assert not progressed and '已停止' in detail
    assert not clicked, '停机后不得有任何点击落地(W209j 刹车)'




def test_brake_inactive_when_running(test_context: SrTestContext, monkeypatch) -> None:
    """正常运行(last_run_result=None,idle/运行中未停)不误拦——刹车判据
    不把离线测试(ctx run_state=STOP 初始态)误判为停机。"""

    class _IdleRunCtx:
        last_run_result = None
        is_context_stop = True   # idle 初始态也是 STOP——但未在运行,不拦

    monkeypatch.setattr(test_context, 'run_context', _IdleRunCtx())
    op = CwScreenPrep(test_context)
    ex = pa_mod.PrepActionExecutor(op, test_context)
    monkeypatch.setattr(test_context.controller, 'mouse_move', lambda p: True,
                        raising=False)
    # 用控制流动作(BailToOuter)验证 execute 未被刹车误拦
    progressed, detail = ex.execute(pv.BailToOuter(reason='t'))
    assert '刹车' not in detail, f'idle 态不得误拦: {detail}'


def test_weakest_bench_protects_same_star_only() -> None:
    """L-5 回归:3合1 保护按 (char_id, star) —— 同名不同星不保护。"""
    from sr_od.application.currency_war.kernel import cw_deploy_seat as seat

    bench2 = [_bc(1, '飞霄', star=1), _bc(2, '飞霄', star=1), _bc(3, '散件', star=1)]
    assert seat._weakest_bench_idx(GameState(bench=bench2), []) == 2
    # 同名不同星:两单张不构成进度 → 都可候选(不保护)
    bench_mixed = [_bc(1, '飞霄', star=1), _bc(2, '飞霄', star=2), _bc(3, '散件', star=1)]
    idx = seat._weakest_bench_idx(GameState(bench=bench_mixed), [])
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
    from sr_od.application.currency_war.obs import cw_observe_full as of_mod
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
    from sr_od.application.currency_war.obs import cw_observe_full as of_mod
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
    # 直读失读(_read_level_raw 委托 read_level_raw_opt,patch 该缝)→ None
    import sr_od.application.currency_war.obs.cw_observation as cwo
    from sr_od.application.currency_war.prep_actions import _read_level_raw
    monkeypatch.setattr(cwo, 'read_level_raw_opt', lambda ctx, scr: None)
    assert _read_level_raw(test_context, None) is None
def test_composite_reads_success_field(test_context: SrTestContext,
                                       monkeypatch) -> None:
    """live 回归(2026-08-14):_run_composite 读 OperationResult.success(非 is_success)。

    退役批改锚:RunBuyPhase 组合已随 prep/shop.py 壳删除,本锁改用仍在线的
    RunEquip 组合(同一 _run_composite 机制,success 字段读法不变)。
    """
    from sr_od.application.currency_war import prep_actions as pa
    from sr_od.application.currency_war.kernel.cw_prep_actions import RunEquip

    ex = pa.PrepActionExecutor(CwScreenPrep(test_context), test_context)

    class _OpResult:   # 形状对齐 one_dragon OperationResult(success 字段)
        def __init__(self) -> None:
            self.success = True
            self.status = '穿 2 件'

    class _FakeOp:
        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            return _OpResult()

    class _FakeModule:
        EquipAllOp = _FakeOp

    # patch 消费点:只替换被测链要导入的那一个 sys.modules 条目
    # (importlib.import_module 命中缓存直返 _FakeModule),不动标准库
    import sys
    monkeypatch.setitem(sys.modules,
                        'sr_od.application.currency_war.operations.prep.equip_all',
                        _FakeModule)
    ok, detail = ex.execute(RunEquip())
    assert ok, f'success=True 的组合结果必须判成功(live bug:旧读 is_success 恒 False): {detail}'
def test_rule3_shop_open_closes_shop_first() -> None:
    """live 回归(2026-08-14 1-2):商店开态奖励面板与概率表按钮重叠 → 假球误开弹窗。

    W970 批 C:EnsureShopClosed 退役 → OpenShop(read_only) 编排(幂等开店
    [已开不点]→观察刷新→不调商店决策→CloseShopOp→回备战,同收清洁面板效果)。
    """
    obs = _obs(spheres=[('gold', None, 40)] * 2, free_bench_slots=3, shop_open=True)
    a = S.decide_prep_action(obs, _sess(), _cfg())
    assert isinstance(a, OpenShop) and a.read_only, '商店开态须先关店再收球(防假球点击)'
    obs2 = _obs(spheres=[('gold', None, 40)] * 2, free_bench_slots=3, shop_open=False)
    a2 = S.decide_prep_action(obs2, _sess(), _cfg())
    assert isinstance(a2, ClickSpheres) and a2.max_k == 2

def test_level_up_clamps_phantom_jump(test_context, monkeypatch) -> None:
    """live 幽灵 lv10 回归(2026-08-15):_level_up 接受窗钳 before+2 —— 6→10 不确认成功。"""
    import numpy as np

    from sr_od.application.currency_war import prep_actions as pa_mod

    op = CwScreenPrep(test_context)
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
    from sr_od.application.currency_war.kernel.cw_comps import get_comp

    comp = get_comp('列车同行')
    assert comp is not None and '花火' in comp.core_chars
    # 花火:core 命中(阵营不交集也应 True)
    assert _card_hits_target('花火', '盛会之星', comp) is True
    # 普通盛会之星单位(非 core):按阵营不交集 → False(可卖)
    assert _card_hits_target('陌生角色', '盛会之星', comp) is False


# ===== ADR-0136 M16 死循环修复(未达上限弹窗勾选 + 备战席已满警告感知) =====
def test_start_battle_dialog_checkbox_equipped(monkeypatch) -> None:
    """_start_battle 弹窗处理 = 勾选(幂等)+确认(对齐 CwScreenDeployNotFull;M16 只确认→每次出战都弹)。"""
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
        def click(self, p, press_time: float = 0.1): clicks.append((p.x, p.y))

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


# ===== 出战发射锁(原样重发 + 零激活策略 + 连败停机;两局同型停滞实证) =====
# 现象:游戏只在前台处理鼠标输入,两局实证备战环 mid-game「出战 click 未落地」
# ×4 环 ~2min/次,直到人工点击解锁。修法(用户裁定 2026-08-30):未落地 → 原样
# 重发(长按下);**禁用 active_window 激活**(激活=抢用户桌面焦点,自主推进期
# 不可接受);连败(跨环 session 计数)达限 → 停机留证,根因判定交人工。

class _LaunchArea:
    def __init__(self, ok: bool): self.is_success = ok


def _make_launch_env(monkeypatch, prep_visible_rounds: int):
    """发射锁测试环境:可编程「备战标识可见轮数」+ 点击/激活记录 + session。

    prep_visible_rounds:每次发射尝试的轮询中「备战标识-购买经验」可见的次数上限
    (消耗完 = 备战标识消失 = 出战成功)。按钮恒可找到。
    返回 (ex, clicks, activations, session, stop_calls)。
    """
    import sr_od.application.currency_war.prep_actions as pa

    clicks: list[str] = []
    activations: list[bool] = []
    stops: list[str] = []
    rounds = {'left': prep_visible_rounds}

    class _Dir:
        def screenshot(self): return object()
        def round_by_find_area(self, scr, screen, area, **k):
            if area == '按钮-出战':
                return _LaunchArea(True)
            if area == '备战标识-购买经验':
                if rounds['left'] > 0:
                    rounds['left'] -= 1
                    return _LaunchArea(True)
                return _LaunchArea(False)   # 标识消失 = 出战成功
            return _LaunchArea(False)   # 未达上限警告恒无
        def save_screenshot(self, prefix=None): pass

    class _Ctrl:
        def mouse_move(self, p): pass
        def click(self, p, press_time: float = 0.1): clicks.append(press_time)
        def active_window(self): activations.append(True)

    class _RunCtx:
        def stop_running(self, reason=None): stops.append(reason or '')

    class _Sess:
        launch_dead_streak = 0

    class _Match:
        session = _Sess()

    class _Ctx:
        controller = _Ctrl()
        cw_match = _Match()
        run_context = _RunCtx()

    monkeypatch.setattr(pa, 'area_center', lambda ctx, name, screen=None: None)
    monkeypatch.setattr(pa.time, 'sleep', lambda s: None)   # 跳过轮询等待
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._op = _Dir()
    ex._ctx = _Ctx()
    return ex, clicks, activations, _Match.session, stops


def test_start_battle_relaunches_without_activation_on_dead_click(monkeypatch) -> None:
    """发射锁核心:第 1 次发射未落地 → 原样重发(长按下)成功;全程零激活。

    竞态纪律:重发只发生在第 1 次发射完整轮询耗尽之后(点击序 = btn, btn),
    不与正常发射时序交叠;**激活策略锁:任何路径不得调用 active_window**。
    """
    # 两段可编程:尝试0 = 备战标识恒在(轮询耗尽未落地);尝试1 = 标识消失(成功)
    ex, clicks, activations, session, stops = _make_launch_env(monkeypatch, 0)
    import sr_od.application.currency_war.prep_actions as pa
    state = {'attempt': 0}

    def _find_area(scr, screen, area, **k):
        if area == '按钮-出战':
            return _LaunchArea(True)
        if area == '备战标识-购买经验':
            return _LaunchArea(state['attempt'] == 0)   # 尝试0=恒在(未落地),尝试1=消失(成功)
        return _LaunchArea(False)

    monkeypatch.setattr(ex._op, 'round_by_find_area', _find_area)
    orig_launch = pa.PrepActionExecutor._launch_attempt

    def _counting_launch(self, *a, **k):
        try:
            return orig_launch(self, *a, **k)
        finally:
            state['attempt'] += 1

    monkeypatch.setattr(pa.PrepActionExecutor, '_launch_attempt', _counting_launch)
    ok, detail = pa.PrepActionExecutor._start_battle(ex)
    assert ok, f'原样重发后应成功,实 {detail}'
    assert '(重发)' in detail, f'成功 detail 应标注重发: {detail}'
    assert activations == [], f'零激活策略:任何路径不得激活窗口,实 {activations}'
    # click 记录 = press_time:首发默认 0.1,重发段 0.15(人工解锁实证参数)
    assert clicks == [0.1, 0.15], f'两段各点一次出战,重发放长按下,实 {clicks}'
    assert stops == [], '发射成功不得触发停机'


def test_start_battle_launch_dead_escalates_to_evidence_stop(monkeypatch) -> None:
    """两段全败 → session 连败计数 +1;达 LAUNCH_DEAD_LIMIT → 停机留证 + stop_running。"""
    import sr_od.application.currency_war.prep_actions as pa
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor

    ex, clicks, activations, session, stops = _make_launch_env(monkeypatch, 10**9)
    session.launch_dead_streak = PrepActionExecutor.LAUNCH_DEAD_LIMIT - 1   # 差 1 次达限

    ok, detail = pa.PrepActionExecutor._start_battle(ex)
    assert not ok
    assert '停机留证' in detail, f'达限应停机留证,实 {detail}'
    assert session.launch_dead_streak == PrepActionExecutor.LAUNCH_DEAD_LIMIT
    assert stops and 'launch_dead' in stops[0], f'应 stop_running(hook:cw_launch_dead),实 {stops}'
    assert activations == [], '失败路径同样零激活(重发=原样重试,无窗口激活)'


def test_start_battle_success_resets_launch_dead_streak(monkeypatch) -> None:
    """发射成功 → 清 session 连败计数(输入通道恢复的证据),不残留半程计数。"""
    import sr_od.application.currency_war.prep_actions as pa

    ex, clicks, activations, session, stops = _make_launch_env(monkeypatch, 3)   # 3 轮后标识消失 = 成功
    session.launch_dead_streak = 2
    ok, detail = pa.PrepActionExecutor._start_battle(ex)
    assert ok, detail
    assert session.launch_dead_streak == 0, '发射成功须清零连败计数'
    assert activations == [], '首发成功不得激活重发(不与正常发射竞态)'



# ==================== test_prep_action_whitelist ====================

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import sr_od.application.currency_war.kernel.cw_prep_actions as _test_prep_action_whitelist_pa_mod  # noqa: E402
from sr_od.application.currency_war.kernel.cw_prep_actions import PREP_ACTION_TYPES
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepAction as _test_prep_action_whitelist_PrepAction,
)


def _all_prep_subclasses() -> set[type]:
    """prep_actions 模块内定义的全部 PrepAction 具体子类。"""
    return {obj for _, obj in vars(_test_prep_action_whitelist_pa_mod).items()
            if isinstance(obj, type)
            and issubclass(obj, _test_prep_action_whitelist_PrepAction)
            and obj is not _test_prep_action_whitelist_PrepAction
            and obj.__module__ == _test_prep_action_whitelist_pa_mod.__name__}


def test_whitelist_covers_all_prep_subclasses() -> None:
    """模块内全部 PrepAction 子类都在白名单(新动作漏登记 = 此测试红)。"""
    subs = _all_prep_subclasses()
    assert subs, ' PrepAction 子类发现失败(模块扫描空)'
    missing = subs - set(PREP_ACTION_TYPES)
    assert not missing, (
        f'动作漏登记白名单(将 never-execute): {sorted(m.__name__ for m in missing)}')


def test_opentome_registered() -> None:
    """OpenTome 回归锚(P0-① 直接用例)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import OpenTome
    assert OpenTome in PREP_ACTION_TYPES


# ==================== test_prep_skip_substate ====================

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import (
    find_area_in_screen,
    get_match_screen_name,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_skip_substate_matches_own_screen(test_context: SrTestContext) -> None:
    """免战跳过态 fixture:精准匹配自己的子屏(货币战争-备战-免战),不再匹配备战。"""
    if not test_context.has_screen('货币战争-备战-免战', '跳过态'):
        pytest.skip('fixture 缺:screens/货币战争-备战-免战/跳过态.webp')
    img = test_context.load_screen('货币战争-备战-免战', '跳过态')
    assert get_match_screen_name(
        test_context, img,
        screen_name_list=['货币战争-备战', '货币战争-备战-免战'],
    ) == '货币战争-备战-免战', (
        '免战跳过态应精准匹配子屏(出战 id_mark 被跳过替换 → 备战不精准,场景④语义)')
    # 「按钮-跳过」area(备战屏,handler 点它)在子屏帧上仍可命中(跨屏正交查找)
    si = test_context.screen_loader.get_screen('货币战争-备战')
    skip_area = next((a for a in si.area_list if a.area_name == '按钮-跳过'), None)
    assert skip_area is not None, '按钮-跳过 area 应已建档'
    assert find_area_in_screen(test_context, img, skip_area).value == 1, (
        '免战跳过态 fixture 上「按钮-跳过」应命中(OCR 跳过)')


def test_skip_area_not_hit_in_normal_prep(test_context: SrTestContext) -> None:
    """常态备战 fixture(无免战):「按钮-跳过」不命中(出战按钮态)。"""
    if not test_context.has_screen('货币战争-备战', 'shop_closed'):
        pytest.skip('fixture 缺:screens/货币战争-备战/shop_closed.webp')
    img = test_context.load_screen('货币战争-备战', 'shop_closed')
    si = test_context.screen_loader.get_screen('货币战争-备战')
    skip_area = next((a for a in si.area_list if a.area_name == '按钮-跳过'), None)
    if skip_area is None:
        pytest.skip('按钮-跳过 area 未建')
    assert find_area_in_screen(test_context, img, skip_area).value != 1, (
        '常态备战(出战按钮)不应命中「按钮-跳过」')


# ==================== adr0269_prep_two_stage ====================

from pathlib import Path as _adr0269_prep_two_stage_Path

import numpy as np
import pytest as _adr0269_prep_two_stage_pytest


class _FakeMatcher:
    """get_match_screen_name 替身:hits 集合内的屏名命中,否则 None;记录调用序。"""

    def __init__(self, hits: set[str]) -> None:
        self.hits = hits
        self.calls: list[list[str]] = []

    def __call__(self, *, ctx, screen, screen_name_list, crop_first):  # noqa: ANN001 ANN003
        self.calls.append(list(screen_name_list))
        for name in screen_name_list:
            if name in self.hits:
                return name
        return None


@_adr0269_prep_two_stage_pytest.fixture
def matcher_env(monkeypatch):
    from one_dragon.base.screen import screen_utils
    from sr_od.application.currency_war.kernel import cw_obs_core
    fm = _FakeMatcher(set())
    monkeypatch.setattr(screen_utils, 'get_match_screen_name', fm)
    return cw_obs_core, fm


def _run(mod):
    ctx = object()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    return mod.is_prep_like_frame(ctx, screen)


def test_upper_hit_returns_false(matcher_env) -> None:
    """上层屏命中(如 选择伙伴)→ False,且命中即短路(不再判备战)。"""
    mod, fm = matcher_env
    fm.hits = {'货币战争-列车同行'}
    assert _run(mod) is False
    assert ['货币战争-列车同行'] in fm.calls
    # 第二段(备战/开商店,双元素调用)未发生——命中即短路:
    assert not any(len(c) == 2 for c in fm.calls)


def test_upper_miss_prep_hit_returns_true(matcher_env) -> None:
    """上层全未命中 + 备战命中 → True。"""
    mod, fm = matcher_env
    fm.hits = {'货币战争-备战'}
    assert _run(mod) is True
    # 先逐个判完所有上层屏,再判备战双屏(两段显式分离)
    assert len(fm.calls) == len(mod.UPPER_SCREENS) + 1
    assert all(len(c) == 1 for c in fm.calls[:-1])
    assert fm.calls[-1] == ['货币战争-备战', '货币战争-备战-开商店']


def test_all_miss_returns_false(matcher_env) -> None:
    """上层与备战/开商店全未命中(过渡/动画帧)→ False。"""
    mod, fm = matcher_env
    fm.hits = set()
    assert _run(mod) is False


def test_shop_open_returns_true(matcher_env) -> None:
    """开商店屏(第二段子态)→ True。"""
    mod, fm = matcher_env
    fm.hits = {'货币战争-备战-开商店'}
    assert _run(mod) is True


def test_upper_screens_names_registered() -> None:
    """UPPER_SCREENS 的每个 screen_name 都真实存在于 screen_info yml
    (防手写错别字静默失配——名单名错 = 该上层屏永不命中)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    repo_root = _adr0269_prep_two_stage_Path(__file__).resolve().parents[5]
    si_dir = repo_root / 'assets' / 'game_data' / 'screen_info'
    yml_names: set[str] = set()
    for yml in si_dir.glob('*.yml'):
        for line in yml.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('screen_name:'):
                yml_names.add(line.split(':', 1)[1].strip())
                break
    for name in cw_obs_core.UPPER_SCREENS:
        assert name in yml_names, f'UPPER_SCREENS 名 {name!r} 未在 screen_info 注册'


def test_mid_interest_floor_removed() -> None:
    """ADR-0270 死门删除:src 全仓无 _MID_INTEREST_FLOOR 引用残留。"""
    repo_root = _adr0269_prep_two_stage_Path(__file__).resolve().parents[5]
    src_dir = repo_root / 'src'
    hits = [p for p in src_dir.rglob('*.py')
            if '_MID_INTEREST_FLOOR' in p.read_text(encoding='utf-8')]
    assert hits == [], f'残留引用: {hits}'


# ==================== w588_director_v2 ====================

from types import SimpleNamespace as _w588_director_v2_SimpleNamespace

from sr_od.application.currency_war.decision.decision_v2.contracts import (
    AtomOp,
    Bail,
    Decision,
    Defer,
    Snapshot,
    SubstateClassification,
)
from sr_od.application.currency_war.decision.decision_v2.director_v2 import (
    DirectorV2,
    LoopOutcomeKind,
    _DirectorPorts,
)

# ===== 桩与构造 ============================================================


def _snap(confident: bool = True, overlay: str | None = None,
          name: str = 'prep_shop') -> Snapshot:
    """构造快照:仅分类与 overlay 有意义,其余字段框架不读。"""
    return Snapshot(
        classification=SubstateClassification(name=name, confident=confident),
        event_overlay=overlay)


def _ops(*keys: str, domain: str = 'shop') -> Decision:
    """单域 op 批(op_key 即列表序执行)。"""
    return Decision(ops=tuple(AtomOp(k, domain) for k in keys))


class _Recorder:
    """端口桩调用记录(heavy 序/executed 序/恢复/强制/停机/缺陷台账)。"""

    def __init__(self) -> None:
        self.heavy_flags: list[bool] = []
        self.executed: list[str] = []
        self.recover_calls = 0
        self.forced_calls = 0
        self.stops: list[str] = []
        self.defects: list[tuple[str, str]] = []
        self.decide_count = 0


def _engine(snapshots: list[Snapshot] | Snapshot,
            decisions: list[Decision] | Decision,
            exec_results: dict[str, bool] | None = None,
            stopped_flags: list[bool] | bool = False,
            recover_closed_known: bool = False
            ) -> tuple[DirectorV2, _Recorder, _w588_director_v2_SimpleNamespace]:
    """构造引擎 + 记录桩 + 假 session。

    - snapshots:观察序列,耗尽复用最后一个(恒不 confident 场景靠它);
    - decisions:决策序列,耗尽再取 = AssertionError(防测试自身死循环,
      decide 超发即测试脚本错);传单个 Decision = 恒同值(步数预算类用);
    - stopped_flags:is_stopped 现读序列(耗尽复用最后一个)。
    """
    rec = _Recorder()
    snaps = snapshots if isinstance(snapshots, list) else [snapshots]
    obs_state = {'i': 0}

    def observe(heavy: bool) -> Snapshot:
        rec.heavy_flags.append(heavy)
        i = min(obs_state['i'], len(snaps) - 1)
        obs_state['i'] += 1
        return snaps[i]

    if isinstance(decisions, Decision):
        def decide(_s, _sess):
            rec.decide_count += 1
            return decisions
    else:
        def decide(_s, _sess):
            rec.decide_count += 1
            if not decisions:
                raise AssertionError('decide 超发(测试脚本耗尽决策序列)')
            return decisions.pop(0)

    exec_map = exec_results or {}

    def execute(op):
        rec.executed.append(op.op_key)
        return exec_map.get(op.op_key, True), 'ok'

    flags = stopped_flags if isinstance(stopped_flags, list) else [stopped_flags]
    stop_state = {'i': 0}

    def is_stopped() -> bool:
        i = min(stop_state['i'], len(flags) - 1)
        stop_state['i'] += 1
        return flags[i]

    ports = _DirectorPorts(
        decide=decide, observe=observe, execute=execute,
        recover=lambda: (rec.__setattr__('recover_calls', rec.recover_calls + 1)
                         or recover_closed_known),
        force_battle=lambda _why='': rec.__setattr__('forced_calls', rec.forced_calls + 1)
        or True,
        is_stopped=is_stopped,
        stop_with_evidence=lambda reason: rec.stops.append(reason),
        record_defect=lambda kind, detail: rec.defects.append((kind, detail)))
    engine = DirectorV2(ports)
    session = _w588_director_v2_SimpleNamespace(defer_count=0, prep_phase=0, bail_reason_counts={})
    return engine, rec, session


# ===== 循环行为锁 ==========================================================


def test_normal_step_progress_clears_stall_and_heavy_tail() -> None:
    """正常步:op progressed → stall/连败清零;批尾 heavy 观察恰一次;
    decide 收到该批尾后快照(环推进)。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops('k1'), Decision(control=Bail('done'))])
    engine._stall = 3          # 预置零进展计数:成功步必须断链清零
    engine._fail_counts = {'k1': 1}
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.executed == ['k1']
    assert engine._stall == 0
    assert 'k1' not in engine._fail_counts
    assert rec.heavy_flags == [True, True]   # 环入口 heavy + 批尾 heavy
    assert rec.forced_calls == 0


def test_defer_counts_and_light_observe() -> None:
    """defer 路径:框架计 defer、轻观察、不进 execute(控制流不经验证链)。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Defer()), Decision(control=Bail('done'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert sess.defer_count == 1
    assert rec.executed == []
    assert rec.heavy_flags == [True, False]   # 控制流走轻观察


def test_bail_counts_only_grows_and_pingpong_stops() -> None:
    """bail 局级计数只增不清;同因达阈值 → 留证停机;异因不清彼因计数。"""
    # 基础:bail 计数 +1 → BAIL 出口
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Bail('ov'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert sess.bail_reason_counts == {'ov': 1}
    assert rec.stops == []
    # 同因预置 2 次,再 bail 一次 → ≥3 → ping-pong 留证停机
    engine2, rec2, sess2 = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Bail('ov'))])
    sess2.bail_reason_counts = {'ov': DirectorV2.BAIL_SAME_REASON_DIAG - 1}
    outcome2 = engine2.run(sess2)
    assert outcome2.kind is LoopOutcomeKind.PINGPONG_STOP
    assert len(rec2.stops) == 1
    # 异因不清彼因:ov 已 2 次,来因 'other' → 仍 BAIL 不停
    engine3, rec3, sess3 = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Bail('other'))])
    sess3.bail_reason_counts = {'ov': DirectorV2.BAIL_SAME_REASON_DIAG - 1}
    outcome3 = engine3.run(sess3)
    assert outcome3.kind is LoopOutcomeKind.BAIL
    assert sess3.bail_reason_counts['ov'] == DirectorV2.BAIL_SAME_REASON_DIAG - 1   # 不清
    assert rec3.stops == []


def test_unconfident_bounded_retry_then_evidence_stop() -> None:
    """非 confident 不进 decide:有界重试(重观察)内恢复 → 正常推进;
    恒不 confident → 耗尽 → 留证停机接口位恰调一次。"""
    # a) 前 2 帧不 confident(不 decide),第 3 帧恢复 → 正常走
    engine, rec, sess = _engine(
        snapshots=[_snap(confident=False), _snap(confident=False), _snap()],
        decisions=[_ops('k1'), Decision(control=Bail('done'))],
        exec_results={'k1': True})
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.decide_count == 2   # 两帧不 confident 均未到 decide
    assert rec.executed == ['k1']
    # b) 恒不 confident → 重试耗尽 → EVIDENCE_STOP + stop_with_evidence 一次
    engine2, rec2, sess2 = _engine(
        snapshots=_snap(confident=False),
        decisions=[_ops('k1')])
    outcome2 = engine2.run(sess2)
    assert outcome2.kind is LoopOutcomeKind.EVIDENCE_STOP
    assert rec2.decide_count == 0
    assert len(rec2.stops) == 1
    assert rec2.heavy_flags == [True] * (DirectorV2.CONF_RETRY_LIMIT + 1)   # 入口 + 3 重试


def test_brake_top_before_any_decide() -> None:
    """W209j 刹车·环顶查:停机标志已设 → 收口,decide/execute 零调用。"""
    engine, rec, sess = _engine(snapshots=[_snap()],
                                decisions=[_ops('k1')], stopped_flags=True)
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BRAKE_STOPPED
    assert rec.decide_count == 0
    assert rec.executed == []


def test_brake_before_execute() -> None:
    """W209j 刹车·执行前双查:op 已出 decide、未落地 → 停机收口不发动作。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[_ops('k1')],
                                exec_results={'k1': True},
                                stopped_flags=[False, True])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BRAKE_STOPPED
    assert rec.decide_count == 1   # decide 已发生
    assert rec.executed == []      # execute 前被刹


def test_step_budget_exhausted_forces_battle() -> None:
    """步数预算:DirectorV2.MAX_STEPS+1 步 → F5 强制出战端口恰调一次(恒空批驱动)。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=_ops())   # 恒空批
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BATTLE_FORCED
    assert outcome.reason == '步数预算耗尽'
    assert rec.forced_calls == 1
    assert rec.decide_count == DirectorV2.MAX_STEPS   # 第 MAX_STEPS+1 步过门


def test_stall_gate_requires_recovery_tried() -> None:
    """stall 门:stall≥阈值但恢复未试 → 不强制;恢复已试 → 强制出战。"""
    # a) 连续零进展(空批)×DirectorV2.STALL_LIMIT,恢复未试 → 门不放行
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops(), _ops(), _ops(), _ops(), _ops(),
        Decision(control=Bail('done'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL   # 门未触发,由 bail 收口
    assert engine._stall == DirectorV2.STALL_LIMIT
    assert rec.forced_calls == 0
    # b) 恢复已试(经真实失败链取得)+ 连续零进展补到阈值 → 门放行强制出战。
    # 注:引擎计数由 run() 环入口清零重建,不预设——这正是时机锁的语义。
    engine2, rec2, sess2 = _engine(snapshots=[_snap()], decisions=[
        _ops('k1'), _ops('k1'),          # 连败×2 → 恢复一次(recovery_tried=True)
        _ops(), _ops(), _ops()],         # 零进展×3 → stall 5 → 过门
        exec_results={'k1': False})
    outcome2 = engine2.run(sess2)
    assert outcome2.kind is LoopOutcomeKind.BATTLE_FORCED
    assert outcome2.reason == 'stall+恢复试尽'
    assert rec2.forced_calls == 1
    assert rec2.recover_calls == 1


def test_fail_chain_recover_once_then_block() -> None:
    """连败→恢复→屏蔽链:连败 2 → 恢复原语恰一次 + 连败清零(重试窗);
    再连败 2 → 屏蔽落定 + 连败清零(防重复触发);屏蔽后同 key 重提案被拒。"""
    # a) 四次失败走完整链,恢复恰一次,不强制(stall 未到门)
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops('k1'), _ops('k1'), _ops('k1'), _ops('k1'),
        Decision(control=Bail('done'))],
        exec_results={'k1': False})
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.recover_calls == 1   # 恢复原语一次/实例,后续失败不再发
    assert engine._recovered == {'k1'}
    assert engine._blocked == {'k1'}
    assert engine._fail_counts.get('k1', 0) == 0   # 屏蔽落定清连败计数
    assert rec.forced_calls == 0
    # b) 恢复关过已知弹层仍败 → 弹层顽固 → bail 交外环(分型)。
    # 注:恢复发放清连败计数(重试窗),分型需恢复后再连败 2 次 → 共 4 决策。
    engine2, rec2, sess2 = _engine(
        snapshots=[_snap()],
        decisions=[_ops('k1'), _ops('k1'), _ops('k1'), _ops('k1')],
        exec_results={'k1': False}, recover_closed_known=True)
    outcome2 = engine2.run(sess2)
    assert outcome2.kind is LoopOutcomeKind.BAIL
    assert '恢复无效-弹层' in outcome2.reason
    assert engine2._blocked == set()   # 弹层顽固走 bail 不屏蔽
    # c) 屏蔽后同 key 重提案:拒绝执行 + 计 stall(确定性重提案防线);
    # 引擎计数同样不预设,屏蔽态由真实链走到(4 连败 + 第 5 次提案被拒过门)。
    engine3, rec3, sess3 = _engine(snapshots=[_snap()], decisions=[
        _ops('k1'), _ops('k1'), _ops('k1'), _ops('k1'), _ops('k1')],
        exec_results={'k1': False})
    outcome3 = engine3.run(sess3)
    assert outcome3.kind is LoopOutcomeKind.BATTLE_FORCED   # 拒绝计 stall → 过门
    assert rec3.executed == ['k1', 'k1', 'k1', 'k1']        # 第 5 次未落地


def test_fail_stop_batch_drops_remaining() -> None:
    """fail-stop 批:三 op 批第 2 个失败 → 第 3 个不执行、批中止。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops('k1', 'k2', 'k3'), Decision(control=Bail('done'))],
        exec_results={'k1': True, 'k2': False, 'k3': True})
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.executed == ['k1', 'k2']   # k3 丢弃
    assert engine._blocked == set()       # k2 仅失败一次,未到连败门


def test_cross_domain_batch_rejected() -> None:
    """跨域批:域校验拒绝,零 execute 调用,计 stall(MED-3 拒绝路径过门)。"""
    cross = Decision(ops=(AtomOp('k1', 'shop'), AtomOp('k2', 'bench')))
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        cross, Decision(control=Bail('done'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.executed == []
    assert engine._stall == 1


def test_empty_ops_zero_progress_stall() -> None:
    """空批 = 合法零进展:计 stall、无 execute(空返回防线,W561 攻击1)。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops(), Decision(control=Bail('done'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.executed == []
    assert engine._stall == 1


# ===== 六件套时机锁(权威表 = ADR-0458;「表=代码」一致性)==================


def test_entry_reset_table() -> None:
    """环入口清零表:defer/prep_phase/步数/stall/连败链全清,
    **bail 局级计数不清**(唯一清零点 = 外环 handler 成功消化)。"""
    engine, rec, sess = _engine(snapshots=[_snap()],
                                decisions=[Decision(control=Bail('probe'))])
    sess.defer_count = 5
    sess.prep_phase = 7
    sess.bail_reason_counts = {'x': 2}          # 局级陈计数
    engine._steps = 9
    engine._stall = 4
    engine._fail_counts = {'a': 1}
    engine._blocked = {'b'}
    engine._recovered = {'c'}
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert sess.defer_count == 0                # 件 4:环入口清
    assert sess.prep_phase == 0
    assert engine._steps == 1                   # 件 1:入口清零后本步已 +1
    assert engine._stall == 0                   # 件 2:入口清(bail 路径不计 stall)
    assert engine._fail_counts == {}            # 件 3:重建
    assert engine._blocked == set()             # 件 3:屏蔽集生命周期 = 本环
    assert engine._recovered == set()
    assert sess.bail_reason_counts == {'x': 2, 'probe': 1}   # 件 5:只增不清


def test_intra_loop_clear_points_table() -> None:
    """环内清零表:progressed 清 stall+连败;恢复发放清连败留 recovered;
    屏蔽落定清连败留 blocked;defer 跨步累积不被步间清零。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Defer()),
        Decision(control=Defer()),
        _ops('k1'),
        Decision(control=Bail('done')),
    ], exec_results={'k1': True})
    engine._stall = 2
    engine._fail_counts = {'k1': 1}
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert sess.defer_count == 2                # 件 4:步间不清,跨步累积
    assert engine._stall == 0                   # 件 2:progressed 即清
    assert 'k1' not in engine._fail_counts      # 件 3:progressed 清连败


# ==================== w817_recovery_precheck ====================

import pytest as _w817_recovery_precheck_pytest
from cv2.typing import MatLike

from sr_od.application.currency_war import currency_war_app as cw_app_module
from sr_od.application.currency_war.currency_war_app import CurrencyWarApp
from sr_od.application.currency_war.operations.cw_entry.cw_entry_exit import (
    CwEntryExit,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

# ---------------------------------------------------------------------------
# 识别锁(fixture 级,离线 OCR,无 controller)
# ---------------------------------------------------------------------------


def _rect_has_text(ctx: SrTestContext, screen: MatLike, area_screen: str,
                   area_name: str, kw: str) -> bool:
    """在指定 area 的 pc_rect 内做 OCR,判关键词是否出现。"""
    area = ctx.screen_loader.get_area(area_screen, area_name)
    assert area is not None, f'area 未建档:{area_screen}/{area_name}'
    texts = [m.data for m in ctx.ocr_service.get_ocr_result_list(
        image=screen, rect=area.pc_rect)]
    return any(kw in t for t in texts)


def test_pause_fixture_hits_mark(test_context: SrTestContext) -> None:
    """恢复态 fixture:战斗暂停锚在画面上(预检正例)。"""
    screen = test_context.load_screen(CurrencyWarApp.PAUSE_SCREEN, 'paused')
    assert _rect_has_text(test_context, screen,
                          CurrencyWarApp.PAUSE_SCREEN, CurrencyWarApp.PAUSE_MARK,
                          '战斗暂停'), '暂停面板帧应命中「标识-战斗暂停」area'


def test_lobby_fixture_no_pause_mark(test_context: SrTestContext) -> None:
    """负例:大厅帧在战斗暂停锚 rect 内无该文本(正常启动不触发预检)。"""
    screen = test_context.load_screen('货币战争-大厅', 'lobby')
    assert not _rect_has_text(test_context, screen,
                              CurrencyWarApp.PAUSE_SCREEN, CurrencyWarApp.PAUSE_MARK,
                              '战斗暂停')


def test_pause_screen_areas_onboarded() -> None:
    """恢复链依赖的 screen_info area 齐:标识 + 三按钮(撤退/重新挑战/继续战斗)。"""
    import yaml

    with open('assets/game_data/screen_info/currency_war_battle_pause.yml',
              encoding='utf-8') as f:
        d = yaml.safe_load(f)
    names = {a['area_name'] for a in d['area_list']}
    assert {'标识-战斗暂停', '按钮-撤退', '按钮-重新挑战',
            '按钮-继续战斗'} <= names


# ---------------------------------------------------------------------------
# 恢复链行为测试(FixtureController 剧本)
# ---------------------------------------------------------------------------


class _WatchedCwEntryExit(WatchdogOperationMixin, CwEntryExit):
    """带看门狗的退局 op(防恢复链 WAIT 死循环拖挂测试)。"""


def _recovery_phases() -> list[dict]:
    """暂停面板 → 撤退 → 放弃并结算 → 下一步 → 大厅(手动验证范式)。"""
    return [
        {
            'frame': ('货币战争-战斗暂停', 'paused'),
            'exit': ('on_click_in', '货币战争-战斗暂停', '按钮-撤退'),
        },
        {
            'frame': ('货币战争-中断挑战弹窗', 'open'),
            'exit': ('on_click_in', '货币战争-中断挑战弹窗', '按钮-放弃并结算'),
        },
        {
            'frame': ('货币战争-挑战失败', 'failed'),
            'exit': ('on_click_in', '货币战争-挑战失败', '按钮-下一步'),
        },
        {  # 大厅:恢复链终点(exit op 大厅锚命中 → success;预检后回大厅)
            'frame': ('货币战争-大厅', 'lobby'),
        },
    ]


@_w817_recovery_precheck_pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
    monkeypatch: _w817_recovery_precheck_pytest.MonkeyPatch,
) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    return ctrl


def _require_screens(test_context: SrTestContext, phases: list[dict]) -> None:
    for phase in phases:
        screen_name, state = phase['frame']
        if not test_context.has_screen(screen_name, state):
            _w817_recovery_precheck_pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _patch_watched_exit(monkeypatch: _w817_recovery_precheck_pytest.MonkeyPatch) -> None:
    """app 内构造的退局 op 换成看门狗版(防死循环)。"""
    def _factory(ctx) -> CwEntryExit:
        op = _WatchedCwEntryExit(ctx)
        op._init_watchdog()  # type: ignore[attr-defined]
        return op
    monkeypatch.setattr(cw_app_module, 'CwEntryExit', _factory)


def test_pause_panel_triggers_recovery_chain_to_lobby(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
    monkeypatch: _w817_recovery_precheck_pytest.MonkeyPatch,
) -> None:
    """暂停面板起跑:预检命中 → 恢复链三点击按序落地 → 回大厅。"""
    phases = _recovery_phases()
    _require_screens(test_context, phases)
    _patch_watched_exit(monkeypatch)
    fixture_controller.set_phases(phases)

    app = CurrencyWarApp(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep():
            app.screenshot()
            result = app._enter_lobby()
    finally:
        reset_running_state(test_context, app)

    assert result.is_success, f'恢复链未走通到大厅:status={result.status}'
    assert fixture_controller.click_hit_area('货币战争-战斗暂停', '按钮-撤退'), (
        f'未点「撤退」:{fixture_controller.recorded_clicks}')
    assert fixture_controller.click_hit_area('货币战争-中断挑战弹窗', '按钮-放弃并结算'), (
        f'未点「放弃并结算」:{fixture_controller.recorded_clicks}')
    assert fixture_controller.click_hit_area('货币战争-挑战失败', '按钮-下一步'), (
        f'未点「下一步」:{fixture_controller.recorded_clicks}')
    # 恢复链终点 = 大厅(末 phase),此后正常启动流接管
    assert fixture_controller.phase_idx == len(phases) - 1

    # 回大厅后重跑入口节点:走「已在 CW」常规分支,不再触发恢复
    enter_running_state(test_context)
    try:
        with fast_sleep():
            app.screenshot()
            result2 = app._enter_lobby()
    finally:
        reset_running_state(test_context, app)
    assert result2.is_success and result2.status == '已在 CW(大厅/对局中),跳过 enter', (
        f'回大厅后应走常规分支:status={result2.status}')


def test_normal_lobby_start_zero_intervention(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """正常启动(大厅帧):预检零介入 —— 零点击、直接走「已在 CW」分支。"""
    phases = [{'frame': ('货币战争-大厅', 'lobby')}]
    _require_screens(test_context, phases)
    fixture_controller.set_phases(phases)

    app = CurrencyWarApp(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep():
            app.screenshot()
            result = app._enter_lobby()
    finally:
        reset_running_state(test_context, app)

    assert result.is_success and result.status == '已在 CW(大厅/对局中),跳过 enter', (
        f'大厅帧应走常规分支:status={result.status}')
    assert fixture_controller.recorded_clicks == [], (
        f'正常启动不应有任何恢复介入点击:{fixture_controller.recorded_clicks}')
