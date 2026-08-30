"""W854 · 件价值买前 bench 容量预检硬门单帧锁组(ADR-0497)。

设计出处:docs/develop/currency_war/decisions/0497-piece-value-bench-
reserve-gate.md(挂账偿付链=W852 REPORT §3+P29 卡点保守处理+W846
归因+ADR-0453 满栏合成买)。机制落点 = decision_v2.piece_value.
bench_gate_verdict(arbiter 约束链 'pv_bench_reserve',spend_gate
之后);判据谓词单一实现 = spend_gate.bench_front_full(reserve
扩参,禁第二处)。

开关组 piece_value_enabled × piece_value_bench_gate_enabled 默认关
= 第 1 态零漂移锚,每锁带 off 臂对照断言(开臂翻默认时按本锁组
off 臂清单重推语义)。锁语义不锁牌面:成员名从注册表数据现场派生。
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
from sr_od.application.currency_war.decision.decision_v2.piece_value import (
    bench_gate_verdict,
    bench_reserve,
)
from sr_od.application.currency_war.decision.decision_v2.spend_gate import (
    bench_front_full,
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

_CORE = '姬子·启行'   # 列车同行 3 费成员(缺档豁免断言走语义不锁牌面)
_CAP = DEFAULT_REGISTRY.bench_capacity


def _reg(**kw) -> DecisionV2Registry:
    base = {
        'piece_value_enabled': True,
        'piece_value_bench_gate_enabled': True,
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


def _sess(locked: bool = True) -> StrategySession:
    s = StrategySession()
    if locked:
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
        # 默认上阵满编(「当轮可部署」豁免关闭,锁门判据本身)
        st.deployed = _fill_deployed(st.max_units())
    return st


def _cand(name: str, cost: int, merge: bool = False) -> Candidate:
    return Candidate(action=BuyCard(ShopCard(x=0, name=name, cost=cost)),
                     tag='line_opportunistic', source='test', merge=merge)


def _bench(n: int, names: list[str] | None = None) -> list[BenchChar]:
    return [BenchChar(slot=i, char_id=(names[i] if names else f'囤件{i}'),
                      star=1, faction='公司')
            for i in range(n)]


# ===== 锁 0:开关组缺省态 + 链序(裁决序去重的结构前提)=====

def test_lock0_defaults_off_and_chain_order() -> None:
    """硬门子旗标默认关(生命周期第 1 态);pv_bench_reserve 在
    spend_gate 之后链尾(D3 先到先记零双计的链序前提),守卫序不变。"""
    assert DEFAULT_REGISTRY.piece_value_bench_gate_enabled is False
    assert DEFAULT_REGISTRY.piece_value_bench_reserve_cap == 2
    cons = DEFAULT_REGISTRY.constraints
    assert cons[-1] == 'pv_bench_reserve'
    assert cons.index('spend_gate') < cons.index('pv_bench_reserve')
    for guard in ('gold_floor', 'copies_cap', 'bench_capacity'):
        assert cons.index(guard) < cons.index('spend_gate')
    # 审计矩阵 bench 格含本门(boss 格不含=让位,与 spend_gate 同语义)
    m = DEFAULT_REGISTRY.audit_matrix
    for rs in ('emergency', 'mode'):
        assert 'pv_bench_reserve' in m[('bench', rs)]
    assert 'pv_bench_reserve' not in m[('bench', 'boss')]


# ===== 锁 1:reserve 推导(基线 1 + 开对项,cap 截断)=====

def test_lock1_reserve_derivation() -> None:
    """基线 1(P29 禁囤阈值);线内 1★ 恰持 1 份=开对线 +1;恰持 2 份
    不再开对(第 3 张到达即 merge 完成不占新空位,ADR-0453);
    cap 截断;无锁线意向退基线。"""
    # 无意向:基线 1
    assert bench_reserve(_st(), _sess(locked=False), _REG_ON) == 1
    # 有意向零持有:基线 1
    assert bench_reserve(_st(), _sess(), _REG_ON) == 1
    # 开对:线内成员恰持 1 份 → 2
    st1 = _st(bench=_bench(2, ['囤件0', _CORE]))
    assert bench_reserve(st1, _sess(), _REG_ON) == 2
    # 开对持在上阵域同样计数(坐标=bench∪deployed 全持有域)
    st_dep = _st()
    st_dep.deployed = [BenchChar(slot=0, char_id=_CORE, star=1,
                                 faction='公司')]
    assert bench_reserve(st_dep, _sess(), _REG_ON) == 2
    # 2★(非 raw)不算开对
    st_star = _st(bench=[BenchChar(slot=0, char_id=_CORE, star=2,
                                   faction='公司')])
    assert bench_reserve(st_star, _sess(), _REG_ON) == 1
    # 恰持 2 份:开对关闭 → 回基线 1(第三张 merge 完成不需要空位)
    st2 = _st(bench=_bench(2, [_CORE, _CORE]))
    assert bench_reserve(st2, _sess(), _REG_ON) == 1
    # 两条开对线 → 3 被 cap=2 截断;放宽 cap 后显影
    other = [n for n, c in CHARACTERS.items()
             if c.cost == 3 and n != _CORE
             and '列车同行' in (c.factions + c.flows)][0]
    st3 = _st(bench=_bench(3, ['囤件0', _CORE, other]))
    assert bench_reserve(st3, _sess(), _REG_ON) == 2
    assert bench_reserve(st3, _sess(),
                         _reg(piece_value_bench_reserve_cap=5)) == 3
    # cap 下界守卫:cap 非法小值不产生 reserve<1(硬不变式)
    assert bench_reserve(_st(), _sess(locked=False),
                         _reg(piece_value_bench_reserve_cap=0)) == 1


# ===== 锁 2:bench_front_full 扩参(单一实现,缺省逐位不变)=====

def test_lock2_bench_front_full_reserve_param() -> None:
    """缺省 reserve=1 ≡ 旧语义(占用 ≥ 容量−1);reserve=2 阈值降到
    容量−2;reserve<1 被钳回 1(硬不变式)。"""
    st_7 = _st(bench=_bench(_CAP - 2))
    st_8 = _st(bench=_bench(_CAP - 1))
    assert not bench_front_full(st_7, _REG_ON)
    assert bench_front_full(st_8, _REG_ON)          # 缺省=D3 旧语义
    assert bench_front_full(st_7, _REG_ON, reserve=2)
    assert bench_front_full(st_8, _REG_ON, reserve=1)
    assert not bench_front_full(st_7, _REG_ON, reserve=0)   # 钳回 1:7<8
    assert bench_front_full(st_8, _REG_ON, reserve=0)       # 钳回 1:8≥8


# ===== 锁 3:触发 + 豁免面(off 臂零漂移)=====

def test_lock3_trigger_and_exemptions() -> None:
    """占用 ≥ 容量−reserve(开对帧 reserve=2 → 占用 7)非合成非缺档
    非可部署拒;merge/当轮可部署/线内缺档成员豁免;off 臂恒 None。"""
    plug = _scatter_names()[0]
    st = _st(bench=_bench(_CAP - 2, ['囤0', '囤1', '囤2', '囤3', '囤4',
                                     '囤5', _CORE]))
    # 触发(占用 7,开对线使 reserve=2)
    r = bench_gate_verdict(_cand(plug, 3), st, st, _sess(), _REG_ON)
    assert r is not None and 'pv_bench_reserve' in r.describe
    # merge 候选豁免(合成完备)
    assert bench_gate_verdict(_cand(plug, 3, merge=True), st, st,
                              _sess(), _REG_ON) is None
    # 当轮可部署豁免(有空上阵位)
    st_free = _st(bench=_bench(_CAP - 2), deployed=[])
    assert bench_gate_verdict(_cand(plug, 3), st_free, st_free,
                              _sess(), _REG_ON) is None
    # 线内缺档成员豁免(受保护类;board 1 档 → 买后恰达下一档仍缺档)
    st_open = _st(board={'列车同行': 1},
                  bench=_bench(_CAP - 2, ['囤0', '囤1', '囤2', '囤3',
                                          '囤4', '囤5', '囤6']))
    assert bench_gate_verdict(_cand(_CORE, 3), st_open, st_open,
                              _sess(), _REG_ON) is None
    # off 臂:默认 registry 同触发帧恒 None(零漂移)
    assert bench_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _REG_OFF) is None


def test_lock3b_reserve_boundary_band() -> None:
    """reserve 边界:无开对(reserve=1)时占用 7 不辖、占用 8 辖
    (与 D3 带重合);_check_constraint 链上节同名显影。"""
    plug = _scatter_names()[0]
    st7 = _st(bench=_bench(_CAP - 2))
    assert bench_gate_verdict(_cand(plug, 3), st7, st7,
                              _sess(), _REG_ON) is None
    st8 = _st(bench=_bench(_CAP - 1))
    r = bench_gate_verdict(_cand(plug, 3), st8, st8, _sess(), _REG_ON)
    assert r is not None and 'pv_bench_reserve' in r.describe
    assert _check_constraint('pv_bench_reserve', _cand(plug, 3),
                             st8, st8, _sess(), _REG_ON) is not None


# ===== 锁 4:与 D3 的裁决序去重(arbitrate 链级)=====

def test_lock4_adjudication_order_dedup_vs_d3() -> None:
    """双门并存:占用 ≥ 容量−1 带 d3_bench 先到先记(拒因含 d3_bench
    不含 pv_bench_reserve,零双计);容量−reserve ≤ 占用 < 容量−1
    不重叠带只显 pv_bench_reserve。"""
    plug = _scatter_names()[0]
    both = dataclasses.replace(_REG_ON, spend_gate_enabled=True,
                               spend_gate_bench_enabled=True)
    # 锁线 + 一条开对线 → reserve=2:占用 7 只入 pv 带,占用 8 入 D3 带
    sess = _sess()
    def _names(n: int) -> list[str]:
        return [f'囤{i}' for i in range(n - 1)] + [_CORE]   # 末位=开对件
    st8 = _st(bench=_bench(_CAP - 1, _names(_CAP - 1)))
    row = arbitrate([(_cand(plug, 3), 1.0, {})], st8, sess, both).log[0]
    assert not row['accepted']
    assert 'd3_bench' in row['reject']
    assert 'pv_bench_reserve' not in row['reject']
    st7 = _st(bench=_bench(_CAP - 2, _names(_CAP - 2)))
    row7 = arbitrate([(_cand(plug, 3), 1.0, {})], st7, sess, both).log[0]
    assert not row7['accepted']
    assert 'pv_bench_reserve' in row7['reject']
    assert 'd3_bench' not in row7['reject']


# ===== 锁 5:让位序(boss 窗 / 非买侧)=====

def test_lock5_yield_faces() -> None:
    """boss 窗让位(node_type=boss,W774⑤ 同仲裁语义);非 BuyCard/
    merge 候选恒不辖。"""
    plug = _scatter_names()[0]
    st_boss = _st(node_type='boss', bench=_bench(_CAP - 1))
    assert bench_gate_verdict(_cand(plug, 3), st_boss, st_boss,
                              _sess(), _REG_ON) is None
    st = _st(bench=_bench(_CAP - 1))
    assert bench_gate_verdict(_cand(plug, 3, merge=True), st, st,
                              _sess(), _REG_ON) is None


# ===== 锁 6:遥测计数(v3_pv_block 帧级,轮键惰性重置)=====

def test_lock6_block_telemetry_counter() -> None:
    """拒因进 session.v3_pv_block(recorder 透传 sess_pv_bench_block
    的写入面);轮键切换惰性重置;off 臂零写点。"""
    plug = _scatter_names()[0]
    st = _st(bench=_bench(_CAP - 1))
    sess = _sess(locked=False)
    bench_gate_verdict(_cand(plug, 3), st, st, sess, _REG_ON)
    bench_gate_verdict(_cand(plug, 3), st, st, sess, _REG_ON)
    assert getattr(sess, 'v3_pv_block', None) == {'pv_bench_reserve': 2}
    st_r2 = _st(plane=2, round_num=4, bench=_bench(_CAP - 1))
    bench_gate_verdict(_cand(plug, 3), st_r2, st_r2, sess, _REG_ON)
    assert getattr(sess, 'v3_pv_block', None) == {'pv_bench_reserve': 1}
    sess_off = _sess(locked=False)
    bench_gate_verdict(_cand(plug, 3), st, st, sess_off, _REG_OFF)
    assert getattr(sess_off, 'v3_pv_block', None) is None


# ===== 锁 7:off 零漂移(缺省中性 + arbitrate 序列恒等)=====

def test_lock7_off_arm_neutral() -> None:
    """约束链在链但行为零漂移:_check_constraint 缺省 registry 对
    触发帧返回 None;零命中帧 off/on 两臂 arbitrate 动作序列逐位一致。"""
    plug = _scatter_names()[0]
    st8 = _st(bench=_bench(_CAP - 1))
    assert _check_constraint('pv_bench_reserve', _cand(plug, 3),
                             st8, st8, _sess(), _REG_OFF) is None
    st_zero = _st(gold=60)
    off = arbitrate([(_cand(plug, 3), 1.0, {})], st_zero,
                    _sess(locked=False), _REG_OFF)
    on = arbitrate([(_cand(plug, 3), 1.0, {})], st_zero,
                   _sess(locked=False), _REG_ON)
    assert [type(a).__name__ for a in off.actions] \
        == [type(a).__name__ for a in on.actions]


# ===== 锁 8:子旗标消融面 =====

def test_lock8_subflag_ablation() -> None:
    """单开硬门子旗标不开伞不辖;单开伞不开硬门子旗标不辖。"""
    plug = _scatter_names()[0]
    st = _st(bench=_bench(_CAP - 1))
    assert bench_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _reg(piece_value_enabled=False)) is None
    assert bench_gate_verdict(_cand(plug, 3), st, st, _sess(),
                              _reg(piece_value_bench_gate_enabled=False)) \
        is None
