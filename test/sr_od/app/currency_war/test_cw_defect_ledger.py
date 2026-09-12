"""W505 B1/B2:统一缺陷台账(defect_ledger.jsonl)+ 金面收口(纯观测)。

测四类:①台账 schema 锁(逐字段,新流不扩旧流)②分级纯函数 judge_severity
真值表(三级判据链)③旁路接线锁(obs_conflict / record_exec_event 写入 →
台账同行出现,调用方零改动)④gold_close 流锁(shop 暂存 → spend_ledger 行
充实;无暂存 → unknown 不猜;读端行内优先)。契约锁形状不锁分布;
全部落盘走 tmp_path(测试纪律:不写真实 .debug/)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/sr_od/application/currency_war/strategy-docs/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import json
from pathlib import Path

from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.kernel.cw_game_state import board_state_of
from sr_od.application.currency_war.telemetry import (
    defects,
    recorder,
    schema,
    state,
)
from sr_od.application.currency_war.telemetry import (
    recorder as rec_mod,
)
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'w505t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', run_id)
    # 复现计数是进程内状态,逐测试清空防串
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    # deployed 分歧分键的逐次计数器是模块级全局(按 run_id 计),逐测试清空防串
    monkeypatch.setattr(defects, '_DEPLOYED_2SRC_RUN_COUNTS', {})
    # L0 安灯副作用链隔离:handler 桩化(缺省 None 会惰性接真停线——gc 扫描命中
    # 测试 ctx → 写真实仓根 flag + stop_running 毒 session 级 fixture 的
    # last_run_result,全集后续 execute 全撞 W209j 刹车);闩锁同批清空,
    # 防 rid 残留让后续测试的 L0 判级场景静默不触发。
    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_HANDLER', lambda payload: True)
    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_FIRED_RUNS', set())
    # 分包期 4:obs_conflict 的旁路/run_id 出口走 kernel.cw_telemetry_exit 钩子位,
    # 注入真实现(monkeypatch 槽位,自动还原)
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_bypass_obs_conflict_to_defect',
                        defects.bypass_obs_conflict_to_defect)
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider',
                        state.current_run_id)


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 台账 schema 锁(逐字段)=====

def test_defect_ledger_schema_field_lock(tmp_path: Path, monkeypatch):
    """落一行并逐字段锁 schema(字段名/形状=设计 §3.2;新字段末尾追加原则)。"""
    _setup_recorder(monkeypatch, tmp_path)
    defects.record_defect(
        'gold', 'invariant_break', 'gold∈[0,400]', '405', gap=5.0,
        plane=1, round_num=3, unit_seq=2, verdict='待研',
        shot='obs_conflict_gold.png',
        refs=[{'stream': 'spend_ledger', 'key': 'plane=1|round=3|unit_seq=2'}],
        reader_source='shop_spend_audit', note='测试行')
    rows = _rows(tmp_path, 'defect_ledger.jsonl')
    assert len(rows) == 1
    r = rows[0]
    # W512 追加可选末尾字段 confidence(§2.10;旧记录缺省 None 兼容)
    assert set(r) == {'schema_version', 'ts', 'run_id', 'plane', 'round_num',
                      'unit_seq', 'surface', 'kind', 'expected', 'observed',
                      'gap', 'severity', 'verdict', 'evidence', 'reader_source',
                      'note', 'confidence'}
    assert r['confidence'] is None   # 未传 → None(无置信度语义面)
    assert r['schema_version'] == schema.SCHEMA_VERSION
    assert r['run_id'] == 'w505t'
    assert (r['plane'], r['round_num'], r['unit_seq']) == (1, 3, 2)
    assert r['surface'] == 'gold' and r['kind'] == 'invariant_break'
    assert r['expected'] == 'gold∈[0,400]' and r['observed'] == '405'
    assert r['gap'] == 5.0
    assert r['severity'] == 'L2_record'   # 显式 gap_large=False → 保守 L2
    assert r['verdict'] == '待研'
    assert r['evidence'] == {'shot': 'obs_conflict_gold.png',
                             'refs': [{'stream': 'spend_ledger',
                                       'key': 'plane=1|round=3|unit_seq=2'}]}
    assert r['reader_source'] == 'shop_spend_audit' and r['note'] == '测试行'


def test_defect_ledger_noop_without_run_id(tmp_path: Path, monkeypatch):
    """run_id 空 → no-op(与其他便捷入口同门控)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', '')
    defects.record_defect('gold', 'perception_conflict', 'a', 'b')
    assert not (tmp_path / 'defect_ledger.jsonl').exists()


# ===== ② 分级纯函数真值表(判据链:①关键面 ②大gap ③复现)=====

def test_judge_severity_truth_table():
    """L0=关键∧大gap∧复现∧非自动;L1=关键∧大gap 单次,或中面∧大gap∧复现;
    L2=自动裁决/非关键/小 gap。"""
    j = defects.judge_severity
    # 决策关键面
    assert j('gold', gap_large=True, reproduced=True) == 'L0_andon'
    assert j('gold', gap_large=True, reproduced=False) == 'L1_alert'
    assert j('gold', gap_large=False, reproduced=True) == 'L2_record'
    # 裁决已自动 → 恒 L2(即使关键面+大gap+复现)
    assert j('gold', gap_large=True, reproduced=True,
             auto_resolved=True) == 'L2_record'
    # 中相关面:大gap∧复现 → L1;单次 → L2
    assert j('hp', gap_large=True, reproduced=True) == 'L1_alert'
    assert j('hp', gap_large=True, reproduced=False) == 'L2_record'
    # 非关键非中面 → L2
    assert j('confidence', gap_large=True, reproduced=True) == 'L2_record'


def test_critical_surface_domain_lock():
    """关键面/中面枚举锁(分级判据①的域;扩面必须显式改此处)。"""
    assert frozenset(
        {'gold', 'bench', 'deployed', 'level_xp', 'shop_refresh', 'phase_round'}) \
        == defects.DECISION_CRITICAL_SURFACES
    assert frozenset({'hp', 'equip', 'strategy', 'node_seq', 'streak'}) \
        == defects.MEDIUM_CRITICAL_SURFACES


def test_reproduction_counter_upgrades_second_occurrence(tmp_path: Path, monkeypatch):
    """同特征第 2 次 = 复现:金面大 gap 单次 L1 → 再犯升 L0(判据③防抖)。"""
    _setup_recorder(monkeypatch, tmp_path)
    for _ in range(2):
        defects.record_defect('gold', 'perception_conflict',
                                   'gold_delta: 45', '20', gap=-25.0,
                                   gap_large=True)
    sevs = [r['severity'] for r in _rows(tmp_path, 'defect_ledger.jsonl')]
    assert sevs == ['L1_alert', 'L0_andon']


# ===== ③ 旁路接线锁(obs_conflict / exec_event 写入 → 台账同行出现)=====

def test_obs_conflict_bypass_appends_ledger_row(tmp_path: Path, monkeypatch):
    """obs_conflict 写入 → defect_ledger 同行出现,refs = journal
    ``(run_id,v)`` 锚且**行级可下钻闭合**(gold_delta 大 gap → 关键面单次
    = L1)。原流行已随删除波 1 退役;W7 refs 迁移(retirement.md §2
    defect_ledger 行,候裁 4 定谳)后 refs 锚指向同栈刚写入的 obs_event
    证据行——本测试同装 journal + 收编制 provider 验证锚与账本行的
    (run_id,v) 精确对账( 下钻闭合 = 迁移的核心承诺)。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel import (
        cw_state_journal,
        cw_telemetry_exit,
    )
    _setup_recorder(monkeypatch, tmp_path)
    journal = cw_state_journal.install_state_telemetry(
        tmp_path / 'state' / 'journal.jsonl', flush_every=1,
        run_id_provider=state.current_run_id)
    match = SimpleNamespace(session=SimpleNamespace())
    cw_telemetry_exit.set_obs_event_board_provider(
        lambda: board_state_of(match.session))
    try:
        cw_observe.obs_conflict('gold_delta', 45, 20, None,
                                verdict='留证-动作账vs读数不等',
                                source='shop_spend_audit', plane=1, round_num=3,
                                spend=5)
    finally:
        cw_telemetry_exit.set_obs_event_board_provider(None)
        cw_state_journal.reset_state_telemetry()
    defects = _rows(tmp_path, 'defect_ledger.jsonl')
    assert len(defects) == 1
    assert not (tmp_path / 'obs_conflicts.jsonl').exists(), \
        '旧流文件零新增(证据行归宿 = journal)'
    d = defects[0]
    assert d['surface'] == 'gold' and d['kind'] == 'perception_conflict'
    assert d['expected'] == 'gold_delta: 45' and d['observed'] == '20'
    assert d['gap'] == -25.0
    assert d['severity'] == 'L1_alert'   # 关键面+大gap(>10)+单次
    assert d['run_id'] == 'w505t'        # 台账 run 归属键
    assert d['reader_source'] == 'shop_spend_audit'
    # refs 锚 = journal (run_id,v),且与账本 obs_event 证据行精确对账。
    refs = d['evidence']['refs']
    assert len(refs) == 1 and refs[0]['stream'] == 'journal', \
        '旁路行 refs 应恰为 journal 锚(旧 obs_conflicts 指针已迁移)'
    assert refs[0]['key'].startswith('run_id=w505t|v=')
    _anchor_v = int(refs[0]['key'].split('|v=', 1)[1])
    jrows = [json.loads(ln) for ln in
             journal.path.read_text(encoding='utf-8').splitlines()
             if ln.strip()]
    ev = [r for r in jrows if r.get('row') == 'obs_event']
    assert ev and ev[-1]['v'] == _anchor_v and ev[-1]['field'] == 'gold_delta', \
        'refs 锚 (run_id,v) 应下钻命中同栈写入的 obs_event 证据行'


def test_obs_conflict_bypass_refs_omitted_without_journal(
        tmp_path: Path, monkeypatch):
    """无账本媒体(未装 journal/provider)→ refs 诚实省略(空列表):
    锚缺媒体不造死地址(W7 refs 迁移的缺省形态;journal_refs 单一源)。"""
    _setup_recorder(monkeypatch, tmp_path)
    cw_observe.obs_conflict('deployed_align', 4, 5, None,
                            verdict='采新-paddle锚', source='align')
    d = _rows(tmp_path, 'defect_ledger.jsonl')[0]
    assert d['evidence']['refs'] == [], \
        '无 journal 媒体时 refs 应为空(诚实缺失,禁残旧流指针)'


def test_obs_conflict_bypass_auto_resolved_and_text_field(tmp_path: Path, monkeypatch):
    """裁决已自动面(deployed_align)恒 L2;R5 W1 键封闭清单补全后
    back_layout 系键映射 deployed,reconcile 对账域 tracking/star 两活键
    落同名 surface(枚举覆盖调用点全集,ADR-0634——原「未映射键原样落
    surface」的敞口面收窄);gap 不硬猜(None)。"""
    _setup_recorder(monkeypatch, tmp_path)
    # (旧证据文件指针桩 _CONFLICT_JOURNAL 已随删除波 1 移除——证据归宿 =
    #  journal obs_event;本锁辖 obs→缺陷台账旁路,旁路不受账本武装影响。)
    cw_observe.obs_conflict('deployed_align', 4, 5, None,
                            verdict='采新-paddle锚', source='align')
    cw_observe.obs_conflict('back_layout_channel_conflict', {'a': 1}, {'b': 2}, None,
                            verdict='留证')
    cw_observe.obs_conflict('tracking', '[(甲,1)]|[]', '[]|[]', None,
                            verdict='保旧-双空读守卫', source='align')
    cw_observe.obs_conflict('star', 2, 1, None,
                            verdict='保旧-回退防抖', source='align', char='甲')
    defects = _rows(tmp_path, 'defect_ledger.jsonl')
    assert defects[0]['surface'] == 'deployed'
    assert defects[0]['severity'] == 'L2_record'   # 自动裁决 → L2
    assert defects[1]['surface'] == 'deployed', \
        'back_layout 系键已入 OBS_FIELD_TO_SURFACE 枚举(R5 W1 补全,映射部署域)'
    assert defects[1]['gap'] is None               # 文本面不填 gap
    assert defects[1]['severity'] == 'L2_record'
    assert defects[2]['surface'] == 'tracking' and defects[3]['surface'] == 'star', \
        'reconcile 对账域两活键已入枚举,surface 保持 field 同名(值跨 bench|deployed 两册)'
    assert defects[2]['gap'] is None               # 账面快照串 = 文本面
    assert defects[2]['severity'] == 'L2_record'


def test_exec_event_bypass_retired(tmp_path: Path, monkeypatch):
    """exec 失败旁路已随 exec_events 流写入端退役(删除波 1):发射语义下
    动作 op 无成败知识(receipts 零成败字段 + 观察侧 reconcile 对比),
    执行失败证据面随之消失;缺陷台账保留面的现役供给 = obs 冲突旁路 +
    各显式判级点。防半删 = 符号面机器可验。"""
    _setup_recorder(monkeypatch, tmp_path)
    rec = state.get_recorder()
    assert not hasattr(rec, 'record_exec_event'), \
        'record_exec_event 应已随删除波 1 删除(防半删)'
    assert not hasattr(rec_mod, 'bypass_exec_event_to_defect'), \
        'bypass_exec_event_to_defect 应已随删除波 1 删除(防半删)'


# ===== ④ spend_ledger gold_close 暂存流(删除波 1 退役重写)=====

def test_gold_close_slot_retired(tmp_path: Path, monkeypatch):
    """gold_close 暂存槽与单元落账写端已随 spend_ledger 流写入端退役
    (删除波 1);单元框架事实的现役归宿 = receipts 发射行 extra 字段。
    读端(query_spend_ledger)对冻结存量档案的视图契约由下方各测继续承。
    防半删 = 符号面机器可验。"""
    _setup_recorder(monkeypatch, tmp_path)
    assert not hasattr(state, 'set_unit_gold_close'), \
        'set_unit_gold_close 应已随删除波 1 删除(防半删)'
    assert not hasattr(state, 'set_unit_exec_facts'), \
        'set_unit_exec_facts 应已随删除波 1 删除(防半删)'
    assert not hasattr(rec_mod, 'record_spend_unit'), \
        'record_spend_unit 应已随删除波 1 删除(防半删)'
    assert not hasattr(rec_mod, 'shop_close_audit_wiring_lock')





def test_shop_close_audit_wiring_retired():
    """买后 gold 收口对拍接线锁(删除波 1 重写):set_unit_gold_close 暂存
    挂点已随 spend_ledger 流写入端退役删除;finalize_buy_phase 保留的金
    对拍(期望账 vs 关店实读)照常走 obs_conflict 收编面(gold_delta 冲突
    行 → journal)。锁「对拍段在场 + 暂存槽符号已删」,防静默断链或半删。"""
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_prep as shop
    src = Path(shop.__file__).read_text(encoding='utf-8')
    assert '_final_gold = read_gold' in src, '金收口对拍读点在(删除断链防线)'
    assert 'gold_delta' in src, '对拍冲突留证面在(收编 obs_conflict)'
    from sr_od.application.currency_war.telemetry import state as tel_state
    assert not hasattr(tel_state, 'set_unit_gold_close'), \
        'gold_close 暂存槽应已随删除波 1 删除(防半删)'


# ===== deployed 计数双源分歧独立分键(观测仲裁批;不一致率防静默)=====

def test_deployed_count_2src_divergence_key_row(tmp_path: Path, monkeypatch):
    """分歧仲裁触发 → 台账落独立分键行(kind=deployed_count_2src_divergence):

    - surface=deployed(决策关键面)、gap=cv−paddle(事故帧 +2);
    - 逐次行恒 L2(auto_resolved:仲裁已在本侧消化,不进安灯);持续显影
      升级由同局达阈值后的独立升级行承载(见 sustained 测试),不在逐次行;
    - 与 obs_conflicts 旁路的通用 perception_conflict 行分键,判读
      「CV 占用源漂移率」直接按 kind 计数,不下钻证据流行。
    """
    _setup_recorder(monkeypatch, tmp_path)
    defects.record_deployed_count_2src_divergence(3, 5, 'deploy_cap_gate')
    rows = [r for r in _rows(tmp_path, 'defect_ledger.jsonl')
            if r['kind'] == defects.DEFECT_KIND_DEPLOYED_COUNT_2SRC]
    assert len(rows) == 1
    r = rows[0]
    assert r['surface'] == 'deployed'
    assert r['expected'] == 'paddle_x=3' and r['observed'] == 'cv_occupied=5'
    assert r['gap'] == 2.0
    assert r['severity'] == 'L2_record'
    assert r['reader_source'] == 'deploy_cap_gate'
    assert 'arbitrate_deployed_count' in r['verdict']


def test_deployed_count_2src_divergence_key_silent_without_run_id(
        tmp_path: Path, monkeypatch):
    """run_id 缺省 → 分键 no-op(局外单跑/mock 不产生遥测;同 record_defect 门)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', '')
    defects.record_deployed_count_2src_divergence(3, 5, 'director_heavy')
    assert _rows(tmp_path, 'defect_ledger.jsonl') == []


def test_deployed_count_2src_paddle_missing_degraded_row(
        tmp_path: Path, monkeypatch):
    """paddle 失读退化帧(paddle_n=None)走独立退化分键(不得静默):

    与真分歧分键拆分:退化帧无 paddle 真值 ⇒ gap 无差值语义(gap=None、
    不进 gap_large 统计),且不入逐次分歧计数——真分歧率不被失读帧污染,
    持续显影不被失读序列误触发(归因不单向指向 CV 占用源)。
    """
    _setup_recorder(monkeypatch, tmp_path)
    defects.record_deployed_count_2src_divergence(None, 5, 'deploy_cap_gate_paddle_missing')
    deg = [r for r in _rows(tmp_path, 'defect_ledger.jsonl')
           if r['kind'] == defects.DEFECT_KIND_DEPLOYED_COUNT_2SRC_DEGRADED]
    per = [r for r in _rows(tmp_path, 'defect_ledger.jsonl')
           if r['kind'] == defects.DEFECT_KIND_DEPLOYED_COUNT_2SRC]
    assert len(deg) == 1 and not per
    assert deg[0]['expected'] == 'paddle_x=失读(检测链退化,单源 CV 行动,向板满侧)'
    assert deg[0]['observed'] == 'cv_occupied=5'
    assert deg[0]['gap'] is None
    assert deg[0]['severity'] == 'L2_record'


def test_deployed_count_2src_degraded_never_triggers_sustained(
        tmp_path: Path, monkeypatch):
    """纯失读序列(同局 ≥阈值次退化帧)不产出真分歧升级行:

    持续显影阈值只计真分歧——paddle 检测链退化(如 det 模型回归)时
    每次部署都记退化帧,若同键计数会冤判成 CV 占用源结构性漂移
    (归因修错方向)。"""
    _setup_recorder(monkeypatch, tmp_path)
    for _ in range(defects.DEPLOYED_COUNT_2SRC_SUSTAINED_N + 1):
        defects.record_deployed_count_2src_divergence(None, 5, 'deploy_cap_gate')
    rows = _rows(tmp_path, 'defect_ledger.jsonl')
    assert not [r for r in rows
                if r['kind'] == defects.DEFECT_KIND_DEPLOYED_COUNT_2SRC_SUSTAINED]
    assert not [r for r in rows
                if r['kind'] == defects.DEFECT_KIND_DEPLOYED_COUNT_2SRC]


def test_deployed_count_2src_sustained_escalation_once_per_run(
        tmp_path: Path, monkeypatch):
    """持续显影:同局真分歧逐次行达阈值(3,既有留证口径「同局 ≥3 次
    排期修」的代码化)→ 落**一条** L1 升级行
    (kind=deployed_count_2src_sustained);第 4 次起不重复升级(每局至多
    一条,与逐次行分键不混计)。真结构性分歧要响铃不只留痕;
    verdict 双向归因(CV 占用源漂移 ∨ paddle 检测链退化对拍失真),
    并指向退化行占比作分流判据。"""
    _setup_recorder(monkeypatch, tmp_path)
    for _ in range(4):
        defects.record_deployed_count_2src_divergence(3, 5, 'director_heavy')
    rows = _rows(tmp_path, 'defect_ledger.jsonl')
    per = [r for r in rows
           if r['kind'] == defects.DEFECT_KIND_DEPLOYED_COUNT_2SRC]
    sus = [r for r in rows
           if r['kind'] == defects.DEFECT_KIND_DEPLOYED_COUNT_2SRC_SUSTAINED]
    assert len(per) == 4, '逐次行每次仲裁事件一条'
    assert len(sus) == 1, '升级行每局至多一条'
    assert sus[0]['severity'] == 'L1_alert'
    assert sus[0]['surface'] == 'deployed'
    assert 'paddle_x=3' in sus[0]['observed'] and 'cv_occupied=5' in sus[0]['observed']
    assert 'CV 占用源' in sus[0]['verdict'] and 'paddle' in sus[0]['verdict'], \
        'verdict 须双向归因(CV 漂移 ∨ paddle 退化),禁单向指向 CV'
    assert 'degraded' in sus[0]['verdict'], 'verdict 须指向退化行占比作归因分流'


def test_deployed_2src_run_counts_bounded(tmp_path: Path, monkeypatch):
    """逐次计数器生命周期有界:新局首条且历史局积压达上限 ⇒ 清空只保
    当前局(常驻进程跨局累积无界;历史局计数无跨局消费面,清零无损)。"""
    _setup_recorder(monkeypatch, tmp_path)
    stale = {f'old_run_{i}': 1 for i in range(defects._DEPLOYED_2SRC_RUN_COUNTS_MAX)}
    monkeypatch.setattr(defects, '_DEPLOYED_2SRC_RUN_COUNTS', stale)
    defects.record_deployed_count_2src_divergence(3, 5, 'director_heavy')
    counts = defects._DEPLOYED_2SRC_RUN_COUNTS
    assert set(counts) == {'w505t'}, counts
    assert counts['w505t'] == 1


# [退役墓碑,W3] test_query_prefers_ledger_gold_close_over_conflict /
# test_spend_view_sim_int_ts_round_seq_disambiguation /
# test_spend_view_live_str_ts_behavior_unchanged 随 query_spend_ledger 旧视图与
# helper(_match_conflict/resolve_unit_gold_close)退役(W3,删旧读面);
# spend 审计现役账面 = receipts 回执窗 + journal obs_event gold_delta 留证。
# git 历史可复活。
