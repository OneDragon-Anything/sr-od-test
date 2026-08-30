"""W829 · 支出门(买侧收门)单帧锁组(PREREG v4 §锁清单事前写死)。

设计出处:.debug/temp/currency_war/w829_spend_gate_design/REPORT.md v3
(§1.4 判据/§3 落码规格/§4 辖界切分)+ W830-F 终核验三修正(E-b 内联
解耦/U 推导带/传导格升格,锁 #2 即镜像修复锁)。机制落点 =
decision_v2.spend_gate(arbiter 约束链尾节)。

锁语义不锁牌面:成员名/羁绊键从注册表数据现场派生。开关组
spend_gate_*(伞+两子旗标)默认关 = 第 1 态零漂移锚,每锁带 off 臂
对照断言(开臂翻默认时按本锁组的 off 臂清单重推语义)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    _check_constraint,
    arbitrate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.realization import (
    p29_priority_term,
)
from sr_od.application.currency_war.decision.decision_v2.spend_gate import (
    bench_front_full,
    register_press_buy,
    spend_gate_verdict,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)

_CORE = '姬子·启行'   # 列车同行 3 费成员(断言走语义不锁牌面)


def _reg(**kw) -> DecisionV2Registry:
    base = {
        'spend_gate_enabled': True,
        'spend_gate_interest_enabled': True,
        'spend_gate_bench_enabled': True,
    }
    base.update(kw)
    return dataclasses.replace(DEFAULT_REGISTRY, **base)


_REG_ON = _reg()
_REG_OFF = DEFAULT_REGISTRY


def _scatter_names() -> list[str]:
    """线外对照组:3 费非列车同行成员(注册表派生,非牌面锁定)。"""
    return sorted(
        n for n, c in CHARACTERS.items()
        if c.cost == 3
        and '列车同行' not in (c.factions + c.flows))


def _sess() -> StrategySession:
    s = StrategySession()
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    s.v3_intention = ist
    return s


def _fill_deployed(cap: int) -> list[BenchChar]:
    return [BenchChar(slot=i, char_id=f'填充{i}', star=1, faction='公司')
            for i in range(cap)]


def _st(**kw) -> GameState:
    base = {'plane': 2, 'round_num': 3, 'node_type': '战斗', 'gold': 60,
            'hp': 80, 'hp_readable': True, 'level': 7, 'streak': None,
            'board': {}, 'bench': [], 'shop': []}
    base.update(kw)
    st = GameState(**base)
    if 'deployed' not in kw:
        # 默认上阵满编(D2「当轮可上场」豁免关闭,锁血带判据本身)
        st.deployed = _fill_deployed(st.max_units())
    return st


def _cand(name: str, cost: int, merge: bool = False,
          needs_slot: bool = False) -> Candidate:
    return Candidate(action=BuyCard(ShopCard(x=0, name=name, cost=cost)),
                     tag='line_opportunistic', source='test',
                     merge=merge, needs_slot=needs_slot)


def _bench(n: int) -> list[BenchChar]:
    return [BenchChar(slot=i, char_id=f'囤件{i}', star=1, faction='公司')
            for i in range(n)]


# ===== 锁 0:开关组缺省态 + 链序(守卫先到先记的结构前提)=====

def test_lock0_defaults_off_and_chain_order() -> None:
    """伞+两子旗标默认全关(生命周期第 1 态);spend_gate 链尾。
    锁语义重推记录(W927 删码批):件价值硬门 pv_bench_reserve 已随
    整机制删除(ADR-0497),旧断言「spend_gate < pv_bench_reserve 邻接
    序」的被锁对象不复存在,spend_gate 恢复链尾——本锁回归「守卫序 +
    链尾」原语义。"""
    for f in ('spend_gate_enabled', 'spend_gate_interest_enabled',
              'spend_gate_bench_enabled'):
        assert getattr(DEFAULT_REGISTRY, f) is False
    cons = DEFAULT_REGISTRY.constraints
    assert cons[-1] == 'spend_gate'
    for guard in ('gold_floor', 'copies_cap', 'bench_capacity'):
        assert cons.index(guard) < cons.index('spend_gate')


# ===== 锁 1:D1 息线臂(真破息/零息损/off 臂)=====

def test_lock1_d1_true_interest_break_rejects() -> None:
    """真破息(花后 < 息线 ∧ ⌊g/10⌋ 下降)散件买入拒;off 臂恒放行。"""
    plug = _scatter_names()[0]
    st = _st(gold=20)   # 花后 17:破 50 息线 ∧ 2→1 档
    r = spend_gate_verdict(_cand(plug, 3), st, st, _sess(), _REG_ON)
    assert r is not None and 'd1_interest' in r.describe
    assert spend_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _REG_OFF) is None   # off 零漂移


def test_lock1b_d1_zero_loss_not_blocked() -> None:
    """零息损(⌊g/10⌋ 不变)买入不拦(E3 同款语义)。"""
    plug = _scatter_names()[0]
    st = _st(gold=23)   # 花后 20:同 2 档
    assert spend_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _REG_ON) is None


# ===== 锁 2:E-b 内联解耦 + 镜像修复(W830-G 攻击 B 修)=====

def test_lock2_eb_inline_decoupled_mirror_fix() -> None:
    """①线内缺档成员 hp>25 破息放行(E-b 内联判据,不借 P29 项);
    ②预警带(25<hp<40)线内缺档件放行(镜像修复锁——循环豁免若在,
    本断言红);③应急带(hp≤25)E-b 死,破息拒。"""
    sess = _sess()
    st_open = _st(gold=20, board={'列车同行': 1}, hp=80)
    # ① hp=80 破息帧线内缺档件放行
    assert spend_gate_verdict(_cand(_CORE, 3), st_open, st_open, sess,
                              _REG_ON) is None
    # ② 预警带放行(镜像修复)
    st_warn = _st(gold=20, board={'列车同行': 1}, hp=30)
    assert spend_gate_verdict(_cand(_CORE, 3), st_warn, st_warn, sess,
                              _REG_ON) is None
    # ③ 应急带收窄:线内缺档件破息拒
    st_em = _st(gold=20, board={'列车同行': 1}, hp=20)
    r = spend_gate_verdict(_cand(_CORE, 3), st_em, st_em, sess, _REG_ON)
    assert r is not None and 'd1_interest' in r.describe


# ===== 锁 3:D2 血线臂(预警/应急豁免面 + 压库谓词)=====

def test_lock3_d2_warning_band_faces() -> None:
    """预警带(hp 25-40):非转化∧非压库∧非线内缺档件拒(d2_blood);
    线内缺档件放行(转化语义,与锁 2② 同源)。"""
    plug = _scatter_names()[0]
    st = _st(gold=60, hp=35)   # 不破息,纯血带辖域
    r = spend_gate_verdict(_cand(plug, 3), st, st, _sess(), _REG_ON)
    assert r is not None and 'd2_blood' in r.describe
    assert spend_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _REG_OFF) is None   # off 零漂移


def test_lock3b_d2_press_exempt_and_frame_cap() -> None:
    """压库豁免(ADR-0494 操作化单一源):≤2 费∧非线内成员∧帧 <2 张
    → 放行;第 3 张拒;needs_slot 不获豁免。"""
    low = sorted(n for n, c in CHARACTERS.items()
                 if c.cost == 1
                 and '列车同行' not in (c.factions + c.flows))[0]
    st = _st(gold=60, hp=35)
    sess = _sess()
    auth: dict = {}
    assert spend_gate_verdict(_cand(low, 1), st, st, sess, _REG_ON,
                              auth=auth) is None
    assert auth.get('sg_press') is True   # 豁免 trace → 采纳处计数
    register_press_buy(st, sess)
    register_press_buy(st, sess)
    r = spend_gate_verdict(_cand(low, 1), st, st, sess, _REG_ON)
    assert r is not None and 'd2_blood' in r.describe   # 帧 ≤2 张上限
    # needs_slot(需先腾位)不获豁免:重置预算后仍拒
    sess2 = _sess()
    r2 = spend_gate_verdict(_cand(low, 1, needs_slot=True), st, st,
                            sess2, _REG_ON)
    assert r2 is not None and 'd2_blood' in r2.describe


def test_lock3c_d2_emergency_band_press_banned() -> None:
    """应急带(hp≤25)豁免面收窄:压库禁——1 费散件也拒。"""
    low = sorted(n for n, c in CHARACTERS.items()
                 if c.cost == 1
                 and '列车同行' not in (c.factions + c.flows))[0]
    st = _st(gold=60, hp=20)
    r = spend_gate_verdict(_cand(low, 1), st, st, _sess(), _REG_ON)
    assert r is not None and 'd2_blood' in r.describe


def test_lock3d_d2_conversion_exempt_when_deploy_free() -> None:
    """转化性豁免:有空上阵位(当轮可上场)→ 血带放行。"""
    plug = _scatter_names()[0]
    st = _st(gold=60, hp=35, deployed=[])
    assert spend_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _REG_ON) is None


# ===== 锁 4:D3 位置臂(bench 前瞻挤占)=====

def test_lock4_d3_bench_front_full() -> None:
    """占用 ≥ 容量−1:非合成∧非当轮可部署拒(d3_bench);merge 豁免
    (E-a)与当轮可部署放行;off 臂恒放行。"""
    st = _st(gold=60, bench=_bench(DEFAULT_REGISTRY.bench_capacity - 1))
    plug = _scatter_names()[0]
    r = spend_gate_verdict(_cand(plug, 3), st, st, _sess(), _REG_ON)
    assert r is not None and 'd3_bench' in r.describe
    # E-a:merge 候选门让位
    assert spend_gate_verdict(_cand(plug, 3, merge=True), st, st,
                              _sess(), _REG_ON) is None
    # 当轮可部署(有空上阵位)放行
    st_free = _st(gold=60, bench=_bench(DEFAULT_REGISTRY.bench_capacity - 1),
                  deployed=[])
    assert spend_gate_verdict(_cand(plug, 3), st_free, st_free,
                              _sess(), _REG_ON) is None
    assert spend_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _REG_OFF) is None   # off 零漂移


def test_lock4b_p29_consumes_shared_predicate() -> None:
    """单一实现上提:P29 囤牌加项临近满栏禁囤仍生效(消费
    bench_front_full 同一函数,禁第二处的行为面回归锁)。"""
    sess = _sess()
    reg = dataclasses.replace(_REG_ON, realization_chain_enabled=True,
                              realization_buy_enabled=True)
    st_open = _st(board={'列车同行': 1})
    assert p29_priority_term(_cand(_CORE, 3), st_open, sess, reg) > 0.0
    st_full = _st(board={'列车同行': 1},
                  bench=_bench(DEFAULT_REGISTRY.bench_capacity - 1))
    assert bench_front_full(st_full, reg)
    assert p29_priority_term(_cand(_CORE, 3), st_full, sess, reg) == 0.0


# ===== 锁 5:守卫先到先记(arbitrate 链级去重)=====

def test_lock5_guard_first_wins_dedup() -> None:
    """bench 全满候选:bench_capacity 守卫先拒,门不再求值——log 行
    拒因含守卫、不含 spend_gate(d3_bench 与守卫计数零混账)。"""
    st = _st(gold=60, bench=_bench(DEFAULT_REGISTRY.bench_capacity))
    plug = _scatter_names()[0]
    res = arbitrate([(_cand(plug, 3), 1.0, {})], st, _sess(), _REG_ON)
    row = res.log[0]
    assert not row['accepted']
    assert 'bench_capacity' in row['reject']
    assert 'spend_gate' not in row['reject']


def test_lock5b_d3_fires_only_in_front_full_frame() -> None:
    """未满栏但前瞻挤占帧:d3_bench 经链级裁决显影。"""
    st = _st(gold=60, bench=_bench(DEFAULT_REGISTRY.bench_capacity - 1))
    plug = _scatter_names()[0]
    res = arbitrate([(_cand(plug, 3), 1.0, {})], st, _sess(), _REG_ON)
    row = res.log[0]
    assert not row['accepted'] and 'd3_bench' in row['reject']


# ===== 锁 6:让位序(alloc 接管帧 / merge 通道 / 末窗不新增放行)=====

def test_lock6_alloc_takeover_frame_yields() -> None:
    """ADR-0474 分配器接管帧(d2_entry_frame 单一源)门整体让位;
    关分配器旗标(=gate-only 臂,无接管帧)同帧恢复血带辖域。"""
    reg = _reg(realization_chain_enabled=True, realization_d2_enabled=True)
    st = _st(plane=2, round_num=1, hp=20, gold=60)
    plug = _scatter_names()[0]
    assert spend_gate_verdict(_cand(plug, 3), st, st, _sess(), reg) is None
    reg_no_alloc = _reg()
    r = spend_gate_verdict(_cand(plug, 3), st, st, _sess(), reg_no_alloc)
    assert r is not None and 'd2_blood' in r.describe


def test_lock6b_endgame_no_new_pass() -> None:
    """末窗(ADR-0451 降格独占帧)门不新增放行:非豁免破息买入照拒。"""
    plug = _scatter_names()[0]
    st = _st(gold=20, round_num=DEFAULT_REGISTRY.handoff_gate_min_round)
    r = spend_gate_verdict(_cand(plug, 3), st, st, _sess(), _REG_ON)
    assert r is not None and 'd1_interest' in r.describe


# ===== 锁 7:遥测计数 + 压库采纳计数 =====

def test_lock7_block_telemetry_counter() -> None:
    """拒因枚举进 session.v3_sg_block(帧级计数,轮键惰性重置;
    recorder 透传 sess_spend_gate_block 的写入面)。"""
    plug = _scatter_names()[0]
    st = _st(gold=20)
    sess = _sess()
    spend_gate_verdict(_cand(plug, 3), st, st, sess, _REG_ON)
    spend_gate_verdict(_cand(plug, 3), st, st, sess, _REG_ON)
    assert getattr(sess, 'v3_sg_block', None) == {'d1_interest': 2}


# ===== 锁 8:gate-only 选择性恒等 + arbitrate 零漂移 =====

def test_lock8_gate_only_selective_identity() -> None:
    """选择性恒等(v3 修正,替旧「gate-only ≡ off 逐位」):门谓词
    零命中帧(不破息∧非血带∧非前瞻挤占)上门恒放行;off/on 两臂
    arbitrate 动作序列逐位一致(零命中帧位集)。"""
    plug = _scatter_names()[0]
    st = _st(gold=60, hp=80)   # 零命中帧
    assert spend_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _REG_ON) is None
    off = arbitrate([(_cand(plug, 3), 1.0, {})], st, _sess(), _REG_OFF)
    on = arbitrate([(_cand(plug, 3), 1.0, {})], st, _sess(), _REG_ON)
    assert [type(a).__name__ for a in off.actions] \
        == [type(a).__name__ for a in on.actions]


def test_lock8b_off_arm_verdict_neutral() -> None:
    """off 臂:门函数对任意帧恒 None(约束链在链,行为零漂移)。"""
    plug = _scatter_names()[0]
    for st in (_st(gold=20), _st(gold=60, hp=35),
               _st(gold=60, bench=_bench(8))):
        assert spend_gate_verdict(_cand(plug, 3), st, st, _sess(),
                                  _REG_OFF) is None


# ===== 锁 9:子旗标消融面 =====

def test_lock9_subflag_ablation() -> None:
    """单开息线臂:D3/D2 不辖(D3 判据帧放行);单开位置臂:D1 不辖。"""
    plug = _scatter_names()[0]
    st_front = _st(gold=60, bench=_bench(8))
    reg_i = _reg(spend_gate_bench_enabled=False)
    assert spend_gate_verdict(_cand(plug, 3), st_front, st_front,
                              _sess(), reg_i) is None
    st_broke = _st(gold=20)
    reg_b = _reg(spend_gate_interest_enabled=False)
    assert spend_gate_verdict(_cand(plug, 3), st_broke, st_broke,
                              _sess(), reg_b) is None


# ===== 锁 10:伞关下 _check_constraint 中性(链上节但零行为)=====

def test_lock10_check_constraint_neutral_when_off() -> None:
    """约束链新增一节的缺省中性:_check_constraint('spend_gate',…)
    在伞关时对破息帧返回 None(审计矩阵锁名存在 ≠ 行为变更)。"""
    plug = _scatter_names()[0]
    st = _st(gold=20)
    assert _check_constraint('spend_gate', _cand(plug, 3), st, st,
                             _sess(), _REG_OFF) is None
