"""决策行文件发射面行为锁(两文件模型②落地批)。

正本锚:``docs/develop/sr_od/application/currency_war/design/决策行文件
schema设计.md``(§2.1 行五段结构 / §2.4 首批发射面与披露族封闭清单 /
§4 字段语义 / §5.1 窗口与锚 / §5.2 望远镜恒等式与终局对账 / §5.4 文件名
与寿命契约 / §10 锁面清单 L1-L6);定谳依据 =
``.debug/progress/2026-09-11-cw-clear-run/定谳记录-c1c8.md``(C1 降格
主张 / C2 文件名 / C3 派生列不发射 / C4 首批发射面 / C7 独立版本常量 /
C8 候裁 6 联动;挂波 C6 = W6 后)。

锁面 =
- 行形状(§10-L5):首批发射面只含 cw4_counters(C4);退役面字段与
  派生列 refresh_trigger(C3)不入行;披露族 14 字段未接线期不入行;
  cw4_counters 值全 int;行内 dict 与容器无共享引用;
- 三态分型(§10-L4):None(无载体)/ {}(零变更)/ 非空(有变更)
  三态可辨且各自可构造;
- 望远镜恒等式(§10-L2):逐行校验「至该行的前缀和 == 该行收口时点容器
  现读」,逐键精确(含清零负差/签名覆写/容器重建消失键)——回放对拍
  口径(行流重放重建容器真值);
- 终局对账(§10-L3):单调键 Σ行增量 ≤ 局终聚合同键值(残差窗口由局终
  聚合承载,定谳 C1 降格主张);非单调键不作断言;
- 键域封闭(§10-L1):发射键集 ⊆ 封闭锁 registry(字面 + 闭族实例 +
  开放族前缀),豁免七名反查面零交集;
- 跨载体键名一致(§10-L6):决策行键名空间 == 局终聚合键名空间
  (同一容器来源,防第二命名);
- 发射语义(§5.1):窗口归属(求值内写点入本行/执行侧写点入下一行)、
  一收口一行无节流、局段边界锚独立、局外拒写不产假行;
- 钉(R4):state_ref 形态与显式传参语义;
- 版本常量(定谳 C7):独立常量初值 1,行头取该常量;
- 文件(定谳 C2):strategy/decision_trace.jsonl 缺省布局、装配落盘
  端到端、寿命联动(journal 已淘汰的同一 run_id 集协同淘汰,两文件禁
  单件淘汰)。

测试隔离:sink / run 归属供给槽 / 锚旁表 / 落盘实例均为模块级全局——
fixture 统一安装/复位;零真实副作用(落盘走 tmp_path)。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from sr_od.application.currency_war.kernel import (
    cw_decision_trace as dt_mod,
)
from sr_od.application.currency_war.kernel.cw_board_state import (
    ChannelSig,
    Field,
    NodeKey,
    board_state_of,
    register_sig_actors,
    set_run_id_provider,
    write_match_final,
)
from sr_od.application.currency_war.kernel.cw_decision_trace import (
    DECISION_TRACE_SCHEMA_VERSION,
    DERIVED_COLUMN_NOT_EMITTED,
    DISCLOSURE_FAMILY_CLOSED_LIST,
    EMITTED_FIELDS,
    RETIRED_FIELDS_NOT_EMITTED,
    ROW_KEY_ORDER,
    install_decision_trace,
    record_decision_frame,
    reset_decision_trace,
    reset_decision_trace_all_anchors,
    set_decision_trace_sink,
)
from sr_od.application.currency_war.kernel.cw_observe import LIVE_DIR
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.telemetry import match_archive

# cw4 键全集封闭锁登记面(§10-L1 断格的唯一登记单一源)
from test.sr_od.app.currency_war.test_cw4_key_closure import (
    CLOSED_FAMILIES,
    EXEMPT_KEYS,
    LITERAL_KEYS,
    OPEN_FAMILY_PREFIXES,
    _family_instances,
)

register_sig_actors('TestSigWriter')

_RUN = 'run_dt_test'


def _lsig() -> ChannelSig:
    """渠道②签名(logic_action;测试逻辑写入用)。"""
    return ChannelSig(family='logic_action', actor='TestSigWriter',
                      mode='compute')


def _osig() -> ChannelSig:
    """渠道①签名(obs;测试观察写入用)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


class _Carrier:
    """策略状态黑盒替身(容器字段形态与 StrategyState.cw4_counters 同)。"""

    def __init__(self, counters: dict | None = None) -> None:
        self.cw4_counters = counters


def _session(counters: dict | None = None, *,
             difficulty: str = 'A6') -> StrategySession:
    """带策略载体替身的局身份(局段边界载体;每调用新对象 = 新局段)。"""
    s = StrategySession()
    s.selected_difficulty = difficulty
    if counters is not None:
        s.strategy_state = _Carrier(counters)
    return s


@pytest.fixture()
def run_env(monkeypatch):
    """run 归属供给槽桩(monkeypatch 自动还原;同 test_cw_match_final)。"""
    set_run_id_provider(lambda: _RUN)
    yield _RUN
    set_run_id_provider(None)


@pytest.fixture(autouse=True)
def _dt_clean():
    """发射面模块级全局复位(防跨用例残留;发射纪律 = 缺省关)。"""
    reset_decision_trace()
    reset_decision_trace_all_anchors()
    set_decision_trace_sink(None)
    yield
    reset_decision_trace()
    reset_decision_trace_all_anchors()
    set_decision_trace_sink(None)


def _records(session: StrategySession, n: int, **kw) -> list[dict]:
    return [record_decision_frame(session, **kw) for _ in range(n)]


# ============================================================ 行形状(§10-L5;C3/C4)


def test_row_shape_first_batch_contract(run_env) -> None:
    """行形状锁:行键恰 = 五段发射序;退役面/派生列/披露族不入行;
    cw4_counters 值全 int(§10-L5;定谳 C3/C4)。"""
    s = _session({'shop_churn_pair_buy': 2, 'launch_frame_idle_gold': 120})
    row = record_decision_frame(s, strategy_id='mandate_v1', ev_arm='full')
    assert list(row.keys()) == list(ROW_KEY_ORDER), '行键 = 五段发射序平铺'
    assert set(EMITTED_FIELDS) == {'cw4_counters'}, '首批发射面单一(C4)'
    # 退役面字段(§2.3)与派生列(定谳 C3)不入行
    for f in (*RETIRED_FIELDS_NOT_EMITTED, *DERIVED_COLUMN_NOT_EMITTED):
        assert f not in row, f'退役面/派生列 {f} 不入新文件行'
    # 披露族 14 字段未接线期不入行(定谳 C4)
    for f in DISCLOSURE_FAMILY_CLOSED_LIST:
        assert f not in row, f'披露族 {f} 未接线不入行'
    payload = row['cw4_counters']
    assert isinstance(payload, dict)
    assert all(type(v) is int for v in payload.values()), '值域全 int'


def test_row_payload_no_shared_reference_with_container(run_env) -> None:
    """浅拷贝边界(§4):行内 dict 与容器无共享引用,后写不串。"""
    s = _session({'a_key': 1})
    row = record_decision_frame(s)
    s.strategy_state.cw4_counters['a_key'] = 99
    assert row['cw4_counters'] == {'a_key': 1}, '行持差分独立副本'


def test_disclosure_family_closed_list_membership(run_env) -> None:
    """披露族成员封闭清单(定谳 C4):恰 14 成员;sess_p1_pair 不属本族
    (归「决策记录」段);清单 = 发射面常量单一源。"""
    assert len(DISCLOSURE_FAMILY_CLOSED_LIST) == 14
    assert 'sess_p1_pair' not in DISCLOSURE_FAMILY_CLOSED_LIST
    assert len(set(DISCLOSURE_FAMILY_CLOSED_LIST)) == 14, '成员无重复登记'
    assert RETIRED_FIELDS_NOT_EMITTED == (
        'state', 'hp', 'gold', 'hp_readable', 'gold_readable',
        'level_readable', 'active_strategies', 'form_score', 'phase')
    assert DERIVED_COLUMN_NOT_EMITTED == ('refresh_trigger',)


# ============================================================ 三态分型(§10-L4)


def test_three_state_typing(run_env) -> None:
    """三态分型锁(§10-L4):None(无载体)/ {}(零变更)/ 非空(有变更)
    可辨且各自可构造(§4 None/{} 分型契约沿局终聚合)。"""
    # 态 1:无策略载体(第三方策略未装配)→ None
    s_none = _session()
    assert record_decision_frame(s_none)['cw4_counters'] is None
    # 态 2:载体在、零变更 → {}(局段首行窗口起点 = 冷建空容器)
    s_zero = _session({})
    assert record_decision_frame(s_zero)['cw4_counters'] == {}
    # 态 3:有变更 → 非空(只含差非零键)
    s_chg = _session({'bench_full': 1})
    row = record_decision_frame(s_chg)
    assert row['cw4_counters'] == {'bench_full': 1}


# ============================================================ 望远镜恒等式(§10-L2)


def test_telescope_identity_per_row(run_env) -> None:
    """望远镜恒等式锁(§10-L2,回放对拍口径):逐行前缀和 == 该行收口
    时点容器现读,逐键精确(§5.2);禁断言 == 局段终值(残差归 L3)。"""
    s = _session({})
    st = s.strategy_state
    snapshots: list[dict] = []
    rows: list[dict] = []

    def _close(container: dict) -> None:
        st.cw4_counters = container
        rows.append(record_decision_frame(s))
        snapshots.append(dict(container))   # 收口时点现读快照

    _close({'inc_key': 1, 'sphere_defer_streak': 3,
            'sphere_defer_progress_sig': 7})            # 常规 + 门簿三键形态
    _close({'inc_key': 4, 'sphere_defer_streak': 0,
            'sphere_defer_progress_sig': 9,
            'new_key': 2})                              # 清零 + 覆写 + 新增
    _close({'inc_key': 4, 'sphere_defer_streak': 1,
            'sphere_defer_progress_sig': 2,
            'new_key': 2})                              # 覆写回落
    del st.cw4_counters                                 # 容器整体重建(消失键形态)
    _close({'inc_key': 6, 'new_key': 5})

    assert len(rows) == 4
    prefix: dict[str, int] = {}
    for i, row in enumerate(rows):
        for k, v in row['cw4_counters'].items():
            prefix[k] = prefix.get(k, 0) + v
        truth = snapshots[i]
        for k in set(prefix) | set(truth):
            assert prefix.get(k, 0) == truth.get(k, 0), (
                f'行 {i + 1} 前缀和 ≠ 收口时点容器现读(键 {k})')
    # 清零/覆写窗口的带符号差可见(负差/覆写差是发射值,不是省略)
    assert rows[1]['cw4_counters']['sphere_defer_streak'] == -3
    assert rows[1]['cw4_counters']['sphere_defer_progress_sig'] == 2
    assert rows[3]['cw4_counters']['new_key'] == 3, '消失键按缺席=0 入账'


def test_window_attribution_timing(run_env) -> None:
    """发射时机语义(§5.1):求值过程写点落**本行**窗口;收口后执行侧
    写点归**下一行**;一收口一行,无内部节流(频率 = 调用频率)。"""
    s = _session({})
    st = s.strategy_state
    # 求值期间的写点(决策自身行为归因)→ 本行
    st.cw4_counters['wanted_leg_deploy'] = 1
    row1 = record_decision_frame(s)
    assert row1['cw4_counters'] == {'wanted_leg_deploy': 1}
    # 收口后的执行侧写点(部署 held/仲裁等)→ 下一行窗口
    st.cw4_counters['deploy_exec_held_cap'] = \
        st.cw4_counters.get('deploy_exec_held_cap', 0) + 1
    row2 = record_decision_frame(s)
    assert row1['cw4_counters'].get('deploy_exec_held_cap') is None
    assert row2['cw4_counters'] == {'deploy_exec_held_cap': 1}
    # 频率:N 次收口 = N 行(零变更窗口也显式发射 {})
    rows = _records(s, 3)
    assert len(rows) == 3
    assert [r['cw4_counters'] for r in rows] == [{}, {}, {}]


def test_segment_boundary_anchor_independence(run_env) -> None:
    """局段边界(§5.2):锚按局段(session)重置,跨局段零账务耦合;
    各局段首行窗口起点 = 各自局段起点。"""
    s1 = _session({'k_a': 5})
    s2 = _session({'k_a': 100})
    r1 = record_decision_frame(s1)
    r2 = record_decision_frame(s2)
    assert r1['cw4_counters'] == {'k_a': 5}
    assert r2['cw4_counters'] == {'k_a': 100}, '跨 session 锚零串染'
    # 同 session 续行:窗口只含增量
    s1.strategy_state.cw4_counters['k_a'] = 7
    r3 = record_decision_frame(s1)
    assert r3['cw4_counters'] == {'k_a': 2}


# ============================================================ 终局对账(§10-L3;C1)


def test_terminal_reconciliation_monotone_keys(run_env) -> None:
    """终局对账锁(§10-L3):单调键 M(全键 − sphere_defer_streak/
    sphere_defer_progress_sig)Σ行增量 ≤ 局终聚合同键值;非单调键不作
    断言;残差窗口(末行收口后、局终收口前写点)由局终聚合承载
    (定谳 C1 降格主张)。"""
    s = _session({})
    st = s.strategy_state
    st.cw4_counters = {'monotone_a': 3, 'monotone_b': 2,
                       'sphere_defer_streak': 5}
    rows = [record_decision_frame(s)]
    # 残差窗口:末决策行之后的写点(耗尽臂/引擎直写形态)
    st.cw4_counters['monotone_a'] = 8       # +5 残差
    st.cw4_counters['sphere_defer_streak'] = 0   # 非单调键残差(清零)
    final_payload = dict(st.cw4_counters)
    bs = board_state_of(s)
    assert write_match_final(bs, final_type='loss',
                             cw4_counters=final_payload) is True
    mf = bs.match_final.value.cw4_counters
    non_monotone = {'sphere_defer_streak', 'sphere_defer_progress_sig'}
    for k in set(final_payload):
        if k in non_monotone:
            continue
        assert sum(r['cw4_counters'].get(k, 0)
                   for r in rows if r['cw4_counters']) <= mf[k]
    assert sum(r['cw4_counters'].get('monotone_a', 0) for r in rows) \
        < mf['monotone_a'], '残差窗口严格大于 0(不等式非空转)'
    # 非单调键不作断言(清零后终值 < 行增量,无对账语义)
    assert mf['sphere_defer_streak'] == 0


# ============================================================ 键域封闭(§10-L1)


def _allowed_key_domain() -> frozenset[str]:
    """封闭锁 registry 全集(字面 + 闭族实例 + 开放族前缀判定分离)。"""
    keys = set(LITERAL_KEYS)
    for fam in CLOSED_FAMILIES:
        keys.update(_family_instances(fam))
    return frozenset(keys)


def test_emitted_keys_within_closure_registry(run_env) -> None:
    """键域封闭锁(§10-L1):发射键集 ⊆ 封闭锁 registry;豁免七名反查面
    零交集(§3.4;封闭锁豁免清单反向锁语义沿用)。"""
    allowed = _allowed_key_domain()
    # 反查面:豁免七名不在 registry 全集(声明面键禁落计数域,先验封闭)
    for k in EXEMPT_KEYS:
        assert k not in allowed, f'豁免键 {k} 混入 registry'
    s = _session({})
    st = s.strategy_state
    st.cw4_counters = {
        'shop_churn_pair_buy': 1,           # 字面键(族 L)
        'deploy_exec_held_cap': 1,          # 闭族实例(deploy_exec_held_{reason})
        't3_fenced_no_candidate': 1,        # 开放族前缀(t3_fenced_{why})
    }
    row = record_decision_frame(s)
    for k in row['cw4_counters']:
        in_open_family = any(k.startswith(p) for p in OPEN_FAMILY_PREFIXES)
        assert k in allowed or in_open_family, f'发射键 {k} 越域(未登记)'


# ============================================================ 跨载体键名一致(§10-L6)


def test_cross_carrier_key_namespace_identity(run_env) -> None:
    """跨载体键名一致锁(§10-L6):决策行键名空间 == 局终聚合键名空间
    (同一容器来源,恒等映射零改名零翻译层,§3.1)。"""
    s = _session({})
    st = s.strategy_state
    st.cw4_counters = {'close_on_sell': 1, 'm6_bench_full': 2,
                       'launch_frame_idle_gold': 50}
    rows = [record_decision_frame(s)]
    st.cw4_counters['close_on_sell'] = 3
    rows.append(record_decision_frame(s))
    final_payload = dict(st.cw4_counters)
    bs = board_state_of(s)
    write_match_final(bs, final_type='win', cw4_counters=final_payload)
    row_keys = {k for r in rows for k in (r['cw4_counters'] or {})}
    final_keys = set(bs.match_final.value.cw4_counters)
    assert row_keys == final_keys, '两载体键名空间恒等(同一容器键域)'


# ============================================================ 发射面管道语义


def test_offmatch_rejects_no_fake_rows(run_env, monkeypatch) -> None:
    """局外拒写(§3.2.3 同纪律):run 归属空 = 不写假行,返 None,sink
    零调用,锚零创建(再入局首行仍为全量窗口)。"""
    monkeypatch.setattr(dt_mod, 'current_run_id_safe', lambda: '')
    seen: list[dict] = []
    set_decision_trace_sink(seen.append)
    s = _session({'k_a': 1})
    assert record_decision_frame(s) is None
    assert seen == []
    # 锚未被创建:恢复 run 归属后首行 = 全量窗口(局段起点口径)
    monkeypatch.setattr(dt_mod, 'current_run_id_safe', lambda: _RUN)
    row = record_decision_frame(s)
    assert row['cw4_counters'] == {'k_a': 1}


def test_sink_absent_default_off_record_passive(run_env) -> None:
    """缺省关 + 显式接通(测试纪律):sink 缺席 = 行不落,写口差分与锚
    推进照常(记录被动,不分支决策路径语义)。"""
    s = _session({'k_a': 1})
    row1 = record_decision_frame(s)     # 无 sink(缺省态)
    assert row1['cw4_counters'] == {'k_a': 1}
    seen: list[dict] = []
    set_decision_trace_sink(seen.append)
    s.strategy_state.cw4_counters['k_a'] = 4
    row2 = record_decision_frame(s)
    assert seen == [row2], '接通后仅新行外送'
    assert row2['cw4_counters'] == {'k_a': 3}, '未武装期间锚照常推进'


def test_sink_exception_does_not_poison(run_env) -> None:
    """记录层 best-effort:sink 异常不毒化决策链(写口照常返回行)。"""

    def _boom(row: dict) -> None:
        raise RuntimeError('sink boom')

    set_decision_trace_sink(_boom)
    s = _session({'k_a': 1})
    row = record_decision_frame(s)
    assert row is not None and row['cw4_counters'] == {'k_a': 1}


# ============================================================ 钉与行头(§8-2/R4;读面衔接)


def test_state_ref_pin_contract(run_env) -> None:
    """钉契约:state_ref = '{run_id}#{v}';显式 state_ref_version 直用
    零回读(R4:交错写点调用方显式传参防钉漂移)。"""
    s = _session({'k_a': 1})
    row = record_decision_frame(s, state_ref_version=41,
                                strategy_id='mandate_v1', ev_arm='full')
    assert row['state_ref'] == f'{_RUN}#41', '显式钉版本直用'
    assert row['strategy_id'] == 'mandate_v1' and row['ev_arm'] == 'full'


def test_state_ref_default_entry_board_read(run_env) -> None:
    """钉缺省 = 入口现读 BoardState 版本读口(读不写不占版本;R4 语义)。
    行头 plane/round_num = cw_board_state 四读口单一源(读面衔接)。"""
    s = _session({'k_a': 1})
    bs = board_state_of(s)
    bs.observe(bs.node,
               NodeKey(plane=2, round_num=5, kind='prep'),
               evidence='test', sig=_osig())
    v_before = bs.current_version()
    row = record_decision_frame(s)
    assert row['state_ref'] == f'{_RUN}#{v_before}', '缺省钉 = 入口现读版本'
    assert row['plane'] == 2 and row['round_num'] == 5, '行头走四读口'
    assert row['difficulty'] == 'A6', 'difficulty 自 session 现读'


def test_state_ref_unreadable_honest_default(run_env, monkeypatch) -> None:
    """钉读取失败/无 BoardState 面 = state_ref 诚实缺省 ''(不猜;
    R4 读取失败语义)。"""
    class _BoomBoard:
        node = Field()

        def current_version(self) -> int:
            raise RuntimeError('board read fail')

    monkeypatch.setattr(dt_mod, 'board_state_of', lambda s: _BoomBoard())
    s = _session({'k_a': 1})
    row = record_decision_frame(s)
    assert row['state_ref'] == ''
    assert row['plane'] == 1 and row['round_num'] == 1, '未观察帧读口引导窗'


# ============================================================ 版本常量(定谳 C7)


def test_independent_version_constant(monkeypatch, run_env) -> None:
    """独立版本常量(定谳 C7):初值 1 独立谱系;行头 schema_version 取
    该常量(常量漂移可辨,非冻结字面);不动 telemetry/schema.py 模块级
    共用常量(kernel 桶依赖矩阵禁 kernel→telemetry,布局锁辖)。"""
    assert DECISION_TRACE_SCHEMA_VERSION == 1
    s = _session({'k_a': 1})
    row = record_decision_frame(s)
    assert row['schema_version'] == DECISION_TRACE_SCHEMA_VERSION
    monkeypatch.setattr(dt_mod, 'DECISION_TRACE_SCHEMA_VERSION', 2)
    row2 = record_decision_frame(s)
    assert row2['schema_version'] == 2, '行头取常量现值(非冻结字面)'


# ============================================================ 文件面(定谳 C2;§5.4)


def test_default_path_mirrors_journal_layout() -> None:
    """缺省目录位(定谳 C2):<live 根>/strategy/decision_trace.jsonl,
    镜像 state/journal.jsonl 布局(两文件模型①②对位)。"""
    install_decision_trace()
    try:
        inst = dt_mod.decision_trace_instance()
        assert inst.path == LIVE_DIR / 'strategy' / 'decision_trace.jsonl'
    finally:
        reset_decision_trace()


def test_install_emits_to_file_end_to_end(run_env, tmp_path) -> None:
    """装配端到端:install → 收口发射 → 文件逐行 JSONL 可回读(回放对拍
    底座:行流 = 文件实况,逐行自足)。"""
    path = tmp_path / 'strategy' / 'decision_trace.jsonl'
    install_decision_trace(path)
    try:
        s = _session({'shop_churn_pair_buy': 1})
        record_decision_frame(s, strategy_id='mandate_v1', ev_arm='full')
        s.strategy_state.cw4_counters['shop_churn_pair_buy'] = 3
        record_decision_frame(s)
        dt_mod.decision_trace_instance().close()   # 收口 flush(丢窗上界收敛)
        lines = [ln for ln in path.read_text(
            encoding='utf-8').splitlines() if ln.strip()]
        assert len(lines) == 2, '两收口两行落盘'
        back = [json.loads(ln) for ln in lines]
        assert back[0]['run_id'] == _RUN
        assert back[0]['cw4_counters'] == {'shop_churn_pair_buy': 1}
        assert back[1]['cw4_counters'] == {'shop_churn_pair_buy': 2}
        assert [r['schema_version'] for r in back] == [1, 1]
    finally:
        reset_decision_trace()


def test_coupled_retirement_same_run_segments(run_env, tmp_path) -> None:
    """寿命契约联动(§5.4):journal 段清理判定的同一 run_id 集从决策行
    文件协同淘汰——两文件禁单件淘汰;坏行/未点名段原样保留;manifest
    逐段 archived_out 显影。"""
    now = datetime.now()
    old_ts = (now - timedelta(days=60)).isoformat(timespec='seconds')
    new_ts = now.isoformat(timespec='seconds')
    j_path = tmp_path / 'state' / 'journal.jsonl'
    j_path.parent.mkdir(parents=True)
    dt_path = tmp_path / 'strategy' / 'decision_trace.jsonl'
    dt_path.parent.mkdir(parents=True)

    def _dt_line(run: str, ts: str) -> str:
        return json.dumps({'schema_version': 1, 'ts': ts, 'run_id': run,
                           'cw4_counters': {}}, ensure_ascii=False)

    j_path.write_text('\n'.join([
        json.dumps({'v': 1, 'ts': old_ts, 'run_id': 'run_old'}) + '\n',
        json.dumps({'v': 2, 'ts': new_ts, 'run_id': 'run_new'}) + '\n',
    ]), encoding='utf-8')
    dt_path.write_text('\n'.join([
        _dt_line('run_old', old_ts) + '\n',
        _dt_line('run_new', new_ts) + '\n',
        _dt_line('run_orphan', old_ts) + '\n',   # journal 无此段:不连带删
        'not-a-json-line\n',                      # 坏行原样保留
    ]), encoding='utf-8')

    install_decision_trace(dt_path, journal_path=j_path)
    reset_decision_trace()

    raw_lines = [ln for ln in
                 dt_path.read_text(encoding='utf-8').splitlines() if ln.strip()]
    assert any(ln == 'not-a-json-line' for ln in raw_lines), '坏行原样保留'
    kept = [json.loads(ln) for ln in raw_lines if ln != 'not-a-json-line']
    kept_runs = [r['run_id'] for r in kept if 'run_id' in r]
    assert 'run_old' not in kept_runs, 'journal 已淘汰段协同淘汰'
    assert 'run_new' in kept_runs and 'run_orphan' in kept_runs
    manifest = json.loads((dt_path.parent /
                           dt_mod.DECISION_TRACE_RETIREMENT_MANIFEST_NAME
                           ).read_text(encoding='utf-8').splitlines()[0])
    assert manifest['run_id'] == 'run_old' and manifest['archived_out'] is True
    # journal 侧同轮已淘汰(判定单一源在 journal pass)
    assert 'run_old' not in j_path.read_text(encoding='utf-8')


def test_install_idempotent_no_double_slot() -> None:
    """装配幂等(同 install_state_telemetry 语义):重入先复位再装,
    防双槽叠加。"""
    p1 = install_decision_trace()
    try:
        p2 = install_decision_trace()
        assert dt_mod.decision_trace_instance() is p2
        assert p2 is not p1
    finally:
        reset_decision_trace()
    assert dt_mod.decision_trace_instance() is None


def test_archive_layout_no_decision_trace_key_regression(tmp_path) -> None:
    """档案面零回归(定谳 C8 联动的守约半面):本批纯新增发射面,既有
    档案切片键面零改动(无 decision_trace 键混入既有 _SLICE_FILES 面)。"""
    rd = tmp_path / 'replay'
    (rd / 'state').mkdir(parents=True)
    (rd / 'state' / 'journal.jsonl').write_text('', encoding='utf-8')
    game = {'game_id': 'g', 'segments': [], 'start_ts': '', 'end_ts': ''}
    a = match_archive.build_archive(rd, game)
    assert 'decision_trace.jsonl' not in (a.get('slices') or {}), (
        '切片面扩登记归 match_archive 批(本批文件面零越界)')
