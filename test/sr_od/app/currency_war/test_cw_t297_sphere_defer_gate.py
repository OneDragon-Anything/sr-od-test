"""T-297 席满让路门(备战环奖励球活锁修复)行为锁。

病灶 = 奖励节点席满无箱点球活锁(2026-09-11 实机:席满 9/9 + 上场满编
+ 无箱,球点不动,决策每环恒 ClickSpheres,3 环后守卫停机整局终止)。
旧两腿谓词(ADR-0596 §4.9③ 迁移 B)第二腿占席色集缺省空集恒真 →
`free>0 or not occupied` 恒提前 return 点球,门无条件化是主根。

方案正本 = T-281 修复方案稿 v2.1;决策申报 = ADR-0642。锁面(方案
§5.3 逐项,锁结构/回显不锁分布数值):
1. 席满让路行为锁:搁浅情节首环单探针(K 预注册),次环起让路
   fall-through,决策批不含 ClickSpheres;连续 ClickSpheres 批序列
   ≤ K(弱判据 §3.4,< 守卫阈值 3,决策层不再产生 ≥3 连击恒指纹窗)。
2. 席自由行为等价锁:free>0 路径动作序列与状态迁移不变(逐帧恒
   ClickSpheres 同形态),新增仅 streak 归零记账,不让路不计数。
3. 批构成锁(按下游真实产出面写,可含常规链卖出腿,禁锁死
   「零 SellBench」= r2-P1):格1 席满+免卖腾席语境 → 让路批含常规链
   M4 腾席卖出腿(mandate.py M2→M4 环,m4_fuel_sell);格2 席满+稳态
   无动作 → 让路批 = ⑥ StartBattle(空批合法交回,cw_screen_prep
   消费契约)。
4. 成效载体三元组重置两腿(§7.3 授权实施批终定:载体 =
   (round_num, len(bench_chars), len(obs.spheres)) 压缩整型,字段全部
   obs/state 现成):任一分量变化(球计数/轮次)→ streak 重开再探针;
   分量不变 → streak 持续爬升不再探针;席自由化腿由等价锁 streak==0
   承载。
5. K 预注册锁:SPHERE_DEFER_PROBE_K == 1(改值须回审);K∈{1,2} 竞速
   安全侧(连击 ≤ 2 < 守卫 3,ADR-0554),K=3 反事实触守卫(纯函数级)。
6. 死码保留结构锁:旧谓词第二腿 + 腾席臂保留原位 + 不可达标注在案
   (ADR-0596 §4.9③「结构保活」,方案稿 §7.1 编排者终态;防无申报
   删除),且旧无条件两腿 OR 谓词不复存在(门重写真实落位)。

来源:旧球谓词锁(test_cw_prep_flag_machine.py TestSphereBenchFullPredicate,
后随 test_cw_mandate_lifecycle 重建 A 半面退役)按新门语义重推 = 本文件
全套(锁存在性纪律:旧锁钉的「席满默认收球」语义已被新门取代)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    PrepObservation,
    SellBench,
    StartBattle,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

#: 守卫阈值引用值(无进展守卫,ADR-0554;cw_loop.PREP_NO_PROGRESS_ROUNDS
#: = 3,不 import 重模块,锁只锚「K 与门行为 ≤ 2 < 3」关系)。
_GUARD_ROUNDS = 3


def _bc(name: str, slot: int, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


class _Pt:
    """球元素坐标载体(read_reward_spheres [(color, Point, r)] 对位)。"""

    def __init__(self, x: int = 100, y: int = 100) -> None:
        self.x, self.y = x, y


def _spheres(n: int) -> list:
    """事故同构球面(blue×6+gray×2 缩放版;色在本门默认态不参与判定)。"""
    colors = ('blue', 'gray')
    return [(colors[i % 2], _Pt(300 + 60 * i, 990), 3) for i in range(n)]


def _state(gold: int = 99, round_num: int = 3,
           bench: list | None = None, deployed: list | None = None) -> GameState:
    """决策黑板(GameState.bench/deployed 必须同形接线:T-32 空板止损
    守卫对 state.deployed 现读,漏接线 = 腾席卖出腿结构性哑火,假红)。"""
    gs = GameState(gold=gold, level=3, round_num=round_num, hp=60)
    gs.plane = 1
    gs.bench = list(bench or [])
    gs.deployed = list(deployed or [])
    return gs


def _obs(state: GameState | None, bench: list, deployed: list,
         spheres: list, free: int) -> PrepObservation:
    return PrepObservation(
        state=state, bench_chars=bench, deployed_chars=deployed,
        spheres=list(spheres), boxes=[], tomes=[],
        free_bench_slots=free, deploy_vacancy=0)


def _sess(target=None) -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    if target is not None:
        state_of(s).target_comp = target
    return s


def _emit(sess: StrategySession, obs: PrepObservation) -> list:
    return entry.emit(obs, SimpleNamespace(), sess, None,
                      registry=MandateV1Strategy().registry)


def _run_len_click_spheres(batches: list[list]) -> int:
    """连续 ClickSpheres 决策批的最大连击长度(§3.4 弱判据观测量)。"""
    best = run = 0
    for batch in batches:
        if any(isinstance(e.action, ClickSpheres) for e in batch):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


# ===== 场景语料 =====

def _stuck_pair(gold: int = 0, round_num: int = 3, spheres_n: int = 8):
    """格2 稳态搁浅语境:席满 9×3★(无 1★ 燃料 → 下游无腾席卖出腿)
    + 板满编(state.max_units()@lv3 = 3,金 0 无必花)→ 让路帧下游
    稳态无动作 = ⑥ StartBattle。返回 (sess, obs 构造器)。"""
    sess = _sess()
    bench = [_bc(f'高价{i}', slot=i, star=3) for i in range(1, 10)]
    deployed = [_bc(f'板件{i}', slot=i, star=2) for i in range(1, 4)]

    def _mk(**overrides) -> PrepObservation:
        st = _state(gold=overrides.get('gold', gold),
                    round_num=overrides.get('round_num', round_num),
                    bench=bench, deployed=deployed)
        return _obs(st, bench, deployed,
                    _spheres(overrides.get('spheres_n', spheres_n)), free=0)

    return sess, _mk


def _fuel_pair():
    """格1 免卖腾席语境:席满 9×1★ 燃料 + 锁线缺员(目标线成员全不在
    手)→ 让路帧下游 M2→M4 环发常规链腾席卖出腿。"""
    comps = [c for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    sess = _sess(target=comps[0])
    bench = [_bc(f'燃料件{i}', slot=i, star=1) for i in range(1, 10)]
    deployed = [_bc('板上件锚', slot=1, star=2)]

    def _mk(**overrides) -> PrepObservation:
        st = _state(gold=overrides.get('gold', 99),
                    round_num=overrides.get('round_num', 3),
                    bench=bench, deployed=deployed)
        return _obs(st, bench, deployed,
                    _spheres(overrides.get('spheres_n', 8)), free=0)

    return sess, _mk


# ===== 1. 席满让路行为锁(§5.3 主锁)=====

class TestBenchFullYieldGate:

    def test_first_frame_single_probe_then_yield(self):
        """搁浅情节首环 = 单探针(同 prep_spheres 发射形态);次环起让路
        fall-through,决策批零 ClickSpheres(格2 稳态 → ⑥ StartBattle)。"""
        sess, mk = _stuck_pair()
        out1 = _emit(sess, mk())
        assert len(out1) == 1
        assert isinstance(out1[0].action, ClickSpheres)
        assert out1[0].reason == 'prep_spheres'
        out2 = _emit(sess, mk())
        assert not any(isinstance(e.action, ClickSpheres) for e in out2)
        assert [type(e.action) for e in out2] == [StartBattle], \
            '格2 稳态让路批应为 ⑥ StartBattle(空批合法交回)'
        ct = state_of(sess).cw4_counters
        assert ct['sphere_defer_streak'] == 2
        assert ct['sphere_defer_yield'] == 1
        # 死码块现状不可达:sphere_blocked_bench_full 恒零写
        assert 'sphere_blocked_bench_full' not in ct

    def test_yield_persists_and_streak_climbs(self):
        """签名不变 → 不再探针,让路持续,streak 逐帧爬升(每让路帧
        yield 计数 +1,零静默)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())          # 探针
        batches = [_emit(sess, mk()) for _ in range(3)]
        for batch in batches:
            assert not any(isinstance(e.action, ClickSpheres)
                           for e in batch)
        ct = state_of(sess).cw4_counters
        assert ct['sphere_defer_streak'] == 4
        assert ct['sphere_defer_yield'] == 3

    def test_weak_guarantee_run_length_le_k(self):
        """§3.4 弱判据:席满形态连续 ClickSpheres 决策批序列 ≤ K=1
        < 守卫阈值 3——球分支垄断性活锁消除(不主张恒指纹全局有界:
        让路后 OpenShop/RunDeploy 恒指纹残余由守卫按设计停机)。"""
        sess, mk = _stuck_pair()
        batches = [_emit(sess, mk()) for _ in range(6)]
        run = _run_len_click_spheres(batches)
        assert run == entry.SPHERE_DEFER_PROBE_K
        assert run < _GUARD_ROUNDS


# ===== 2. 席自由行为等价锁(B5;§5.2 锚 3)=====

class TestBenchFreeEquivalence:

    def test_free_bench_clicks_unchanged_multi_frame(self):
        """free>0:逐帧恒 ClickSpheres 同形态(max_k=权界/球数,reason
        prep_spheres,mandate=True),动作序列与状态迁移与改前一致;
        streak 恒 0、零让路计数(单帧偶发失败由既有逐帧重试自愈)。"""
        sess = _sess()
        st = _state()
        obs = _obs(st, [], [], _spheres(8), free=2)
        for _ in range(3):
            out = _emit(sess, obs)
            assert len(out) == 1
            assert isinstance(out[0].action, ClickSpheres)
            assert out[0].action.max_k == min(3, 8)
            assert out[0].reason == 'prep_spheres'
            assert out[0].mandate is True
        ct = state_of(sess).cw4_counters
        assert ct['sphere_defer_streak'] == 0
        assert 'sphere_defer_yield' not in ct

    def test_seat_freed_resets_and_recovers_clicking(self):
        """成效重置·席自由化腿:搁浅情节中席自由化(free>0)→ streak
        归零;再搁浅 = 新情节从探针重新起算(门语义:自愈形态恢复点击
        不让路,#16 自然回补真实成立)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())                      # 探针 streak=1
        _emit(sess, mk())                      # 让路 streak=2
        bench8 = [_bc(f'高价{i}', slot=i, star=3) for i in range(1, 9)]
        deployed3 = [_bc(f'板件{i}', slot=i, star=2) for i in range(1, 4)]
        st = _state(bench=bench8, deployed=deployed3)
        out_free = _emit(sess, _obs(st, bench8, deployed3, _spheres(8),
                                    free=1))
        assert isinstance(out_free[0].action, ClickSpheres)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 0
        out_again = _emit(sess, mk())          # 再搁浅:新情节首环
        assert isinstance(out_again[0].action, ClickSpheres)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 1


# ===== 3. 批构成锁(下游真实产出面;禁锁死「零 SellBench」)=====

class TestYieldBatchComposition:

    def test_yield_batch_carries_regular_chain_sell_leg(self):
        """格1:席满 ∧ 免卖腾席语境(锁线缺员 + 1★ 燃料在场)→ 让路帧
        批 = 常规链自然产出,含 M4 腾席卖出腿(mandate.py M2→M4 环,
        m4_fuel_sell)——常规链恢复求值即让路的设计收益面;本锁明文
        断言卖出腿**在场**,禁反向锁死「零 SellBench」(r2-P1)。"""
        sess, mk = _fuel_pair()
        out1 = _emit(sess, mk())
        assert isinstance(out1[0].action, ClickSpheres)   # 探针前置
        out2 = _emit(sess, mk())
        assert not any(isinstance(e.action, ClickSpheres) for e in out2)
        m4_legs = [e for e in out2
                   if isinstance(e.action, SellBench)
                   and e.reason == 'm4_fuel_sell']
        assert m4_legs, f'让路批缺常规链 M4 腾席卖出腿:\
{[type(e.action).__name__ for e in out2]}'

    def test_yield_batch_quiescent_face_is_start_battle(self):
        """格2:席满 ∧ 稳态无动作 → 让路批 = ⑥ StartBattle(空批合法
        交回,cw_screen_prep 消费契约;弃球 ≤ 弃局)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        out2 = _emit(sess, mk())
        assert [type(e.action) for e in out2] == [StartBattle]


# ===== 4. 成效载体三元组重置两腿(§7.3 实施批终定)=====

class TestProgressSigReset:

    def test_sphere_count_change_resets_episode(self):
        """重置腿·球计数:搁浅情节中球计数变化(一次成功点开,B8 方向)
        → 签名变 → streak 重开 → 次环再探针(连续收球不被打断,宁多
        收球在门语义层保住)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        _emit(sess, mk())                          # streak=2 让路中
        out = _emit(sess, mk(spheres_n=7))         # 一球被点开
        assert isinstance(out[0].action, ClickSpheres)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 1

    def test_round_advance_resets_episode(self):
        """重置腿·轮次:轮次推进(经战斗一轮 = 新备战语境)→ 签名变 →
        streak 重开再探针。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        _emit(sess, mk())
        out = _emit(sess, mk(round_num=4))
        assert isinstance(out[0].action, ClickSpheres)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 1

    def test_unchanged_face_does_not_reset(self):
        """不重置腿:三分量全不变(纯点击失败,机制性拒绝)→ streak
        持续爬升,不再探针(门不被噪声误开)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        _emit(sess, mk())
        _emit(sess, mk())
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 3
        out = _emit(sess, mk())
        assert not any(isinstance(e.action, ClickSpheres) for e in out)
        assert state_of(sess).cw4_counters['sphere_defer_streak'] == 4

    def test_sig_carrier_is_int(self):
        """载体面:签名存 cw4_counters 为 int(sim 轮差分逐值 int() 算术,
        sim/engine_p1.py;禁 tuple/str 破坏数值账本面)。"""
        sess, mk = _stuck_pair()
        _emit(sess, mk())
        sig = state_of(sess).cw4_counters['sphere_defer_progress_sig']
        assert isinstance(sig, int)


# ===== 5. K 预注册锁(§3.3;改值须回审)=====

class TestProbeKPreregistration:

    def test_k_is_preregistered_one(self):
        assert entry.SPHERE_DEFER_PROBE_K == 1, \
            'K 预注册值被改:须回方案审(§3.3 夹逼依据与守卫竞速约束)'

    @pytest.mark.parametrize('k', [1, 2])
    def test_k_within_guard_race_safe_side(self, k, monkeypatch):
        """竞速安全侧:K∈{1,2}(守卫常量 3 夹逼可行域)→ 连击 ≤ 2
        < 3,让路环先于守卫触发环到来。"""
        monkeypatch.setattr(entry, 'SPHERE_DEFER_PROBE_K', k)
        sess, mk = _stuck_pair()
        batches = [_emit(sess, mk()) for _ in range(6)]
        assert _run_len_click_spheres(batches) == k
        assert k < _GUARD_ROUNDS

    def test_k_three_would_meet_guard_counterfactual(self):
        """反事实(K=3,可行性域外):连击 = 3 == 守卫阈值——让路环恰逢
        守卫触发环,上界论证的「K≤2」边界在纯函数级显影(非注册值,
        仅锚边界存在性)。"""
        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(entry, 'SPHERE_DEFER_PROBE_K', 3)
            sess, mk = _stuck_pair()
            batches = [_emit(sess, mk()) for _ in range(6)]
            assert _run_len_click_spheres(batches) == _GUARD_ROUNDS
        finally:
            monkeypatch.undo()


# ===== 6. 死码保留结构锁(ADR-0596 §4.9③ 结构保活;§7.1 终态)=====

class TestDeadArmKeepAlive:

    def _source(self) -> str:
        return Path(entry.__file__).read_text(encoding='utf-8')

    def test_old_predicate_second_leg_and_fuel_arm_kept(self):
        """旧谓词第二腿(_sf_occupied 判定)+ 腾席臂(fuel 候选→
        m4_fuel_sell 发射→blocked 计数)保留原位,且不可达标注在案
        (读者陷阱显影);结构删除必须先走退役申报(ADR-0642 后果)。"""
        src = self._source()
        assert 'SPHERE_OCCUPYING_COLORS' in src
        assert '_sf_occupied' in src
        assert "'m4_fuel_sell'" in src
        assert 'sphere_blocked_bench_full' in src
        assert '当前不可达' in src and '结构' in src and '保活' in src

    def test_old_unconditional_two_leg_or_retired(self):
        """门重写真实落位:旧无条件两腿 OR(`free>0 or not occupied`
        恒提前 return = 活锁主根)不得回归。"""
        src = self._source()
        assert '_sf_free > 0 or not _sf_occupied' not in src
        assert 'SPHERE_DEFER_PROBE_K' in src
        assert 'sphere_defer_yield' in src

    def test_bench_capacity_invariant_untouched(self):
        """席满语境基准:本文件语料 bench 构形 = BENCH_CAPACITY 满席
        (9),与生产席满形态同构(防语料漂移使门锁失真)。"""
        assert BENCH_CAPACITY == 9
