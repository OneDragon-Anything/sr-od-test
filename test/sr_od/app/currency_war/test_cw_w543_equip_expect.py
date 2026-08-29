"""装备期望态对账网(W543:装备拖拽进期望态对账;架构先例 =
test_cw_w536_buy_expect.py 买牌 / test_cw_w530_drag_reconcile.py 拖动 /
test_cw_w552_xp_reconcile.py 经验,同族:意图 → 期望增量 → heavy 定型帧
对账 → 不一致落缺陷台账,零决策记账)。

语义单一源 = docs/game/currency_war/research/equipment_mechanics.md §1.1
(两件简易必合成无共存,28/28 配方实证 / 合成落点=角色最左简易槽 /
装备不堆叠每格一件 / 卖角色=装备全量回装备区;唯一件=待确认不建模)。
合成规则单一源 = cw_synthesis(勿自造第二套)。

测四类:①期望态计算真值表(五类拖拽×边界:不可合对/未知名/空穿戴
不评)②定型帧对账判据真值表(遮挡格三态如实跳过不评;存量漂移不进
本对账)③接线源码锁(期望在动作发出点计算、对账在 heavy 定型帧后仅
progressed 分支、台账参数锁、合成单一源锁)④台账行形态锁(equip=
中决策相关面 → 单次 L2 初判)。全部纯函数/tmp_path,零触网零落盘真实路径。
"""
import json
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.obs import cw_equipment
from sr_od.application.currency_war.data import cw_synthesis
from sr_od.application.currency_war.obs.cw_equipment import EquipCell
from sr_od.application.currency_war.telemetry import defects, recorder

from sr_od.application.currency_war.prep_director import PrepDirector

from sr_od.application.currency_war.kernel.cw_prep_expect import compare_equip_expect, compute_equip_drag_expect

from sr_od.application.currency_war.kernel.cw_prep_expect import EquipDragIntent, EquipExpect
from sr_od.application.currency_war.telemetry import state as cw_telemetry

# 合成对取自注册表派生图谱(单一源;不硬编码具体件名,图谱更新自动跟上)
_CROSS_ADV, (_CROSS_A, _CROSS_B) = next(iter(cw_synthesis.CROSS_RECIPES.items()))
_SELF_BASE = next(iter(cw_synthesis.SELF_RECIPES.values()))
_SELF_ADV = cw_synthesis.self_advance(_SELF_BASE)


def _cell(name: str | None = None, occluded: bool = False) -> EquipCell:
    return EquipCell(row=1, col=1, cx=0, cy=0, name=name, score=0.9,
                     occluded=occluded)


# ===== ① 期望态计算真值表(五类拖拽 × 边界)=====

def test_expect_cell_synth_cross_and_self():
    """栏内简易A→简易B:两件消耗 + 产物落栏(§1.1 两件简易必合成,
    28/28 配方实证)。交叉对与自配对(×2)都出产物;产物=图谱单一源。"""
    exp = compute_equip_drag_expect(
        EquipDragIntent(kind='cell_synth', source_name=_CROSS_A,
                        target_name=_CROSS_B), {})
    assert exp is not None
    assert exp.deltas == {_CROSS_A: -1, _CROSS_B: -1, _CROSS_ADV: +1}
    assert exp.product == _CROSS_ADV

    exp2 = compute_equip_drag_expect(
        EquipDragIntent(kind='cell_synth', source_name=_SELF_BASE,
                        target_name=_SELF_BASE), {})
    assert exp2 is not None
    assert exp2.deltas == {_SELF_BASE: -2, _SELF_ADV: +1}
    assert exp2.product == _SELF_ADV


def test_expect_cell_synth_invalid_pairs_none():
    """不可合对 → None 不评(不发明期望):非简易(进阶)参与 / 目标名空。"""
    assert compute_equip_drag_expect(
        EquipDragIntent(kind='cell_synth', source_name=_CROSS_ADV,
                        target_name=_CROSS_A), {}) is None
    assert compute_equip_drag_expect(
        EquipDragIntent(kind='cell_synth', source_name=_CROSS_A,
                        target_name=''), {}) is None
    assert compute_equip_drag_expect(
        EquipDragIntent(kind='cell_synth', source_name='不存在件',
                        target_name=_CROSS_A), {}) is None


def test_expect_wear_and_wear_synth():
    """穿上:网格 −1(角色侧本批不评);穿上即合成(已穿简易+拖入简易
    必合成无共存):网格只 −1 拖入件,产物落角色最左简易槽(角色侧不评);
    wear_synth 配对不可合 → None。"""
    exp = compute_equip_drag_expect(
        EquipDragIntent(kind='wear', source_name=_CROSS_A), {})
    assert exp is not None and exp.deltas == {_CROSS_A: -1} and exp.product == ''

    exp2 = compute_equip_drag_expect(
        EquipDragIntent(kind='wear_synth', source_name=_CROSS_A,
                        target_name=_CROSS_B), {})
    assert exp2 is not None
    assert exp2.deltas == {_CROSS_A: -1}
    assert exp2.product == _CROSS_ADV
    # 已穿件同名自配:×2 → 产物
    exp3 = compute_equip_drag_expect(
        EquipDragIntent(kind='wear_synth', source_name=_SELF_BASE,
                        target_name=_SELF_BASE), {})
    assert exp3 is not None and exp3.product == _SELF_ADV
    # 目标非简易(进阶)或空 → 语义未定义,不评
    assert compute_equip_drag_expect(
        EquipDragIntent(kind='wear_synth', source_name=_CROSS_A,
                        target_name=_CROSS_ADV), {}) is None
    assert compute_equip_drag_expect(
        EquipDragIntent(kind='wear_synth', source_name=_CROSS_A,
                        target_name=''), {}) is None


def test_expect_unequip_and_sell_char():
    """卸下:网格 +1;卖角色:已穿装备全量回栏逐件 +1(含同名多件);
    卖角色穿戴空读 = 无可评增量 → None;空 source_name(非 sell_char)→ None。"""
    exp = compute_equip_drag_expect(
        EquipDragIntent(kind='unequip', source_name=_CROSS_A), {})
    assert exp is not None and exp.deltas == {_CROSS_A: +1}

    exp2 = compute_equip_drag_expect(
        EquipDragIntent(kind='sell_char', source_name='',
                        equipped_names=(_CROSS_A, _CROSS_B, _CROSS_A)), {})
    assert exp2 is not None
    assert exp2.deltas == {_CROSS_A: +2, _CROSS_B: +1}
    assert compute_equip_drag_expect(
        EquipDragIntent(kind='sell_char', source_name='',
                        equipped_names=()), {}) is None
    assert compute_equip_drag_expect(
        EquipDragIntent(kind='wear', source_name=''), {}) is None
    assert compute_equip_drag_expect(
        EquipDragIntent(kind='unknown_kind', source_name=_CROSS_A), {}) is None


def test_expect_carries_owned_before_snapshot():
    """before 快照随期望态携带(compare 的期望基准源;拷贝防外部 mutate)。"""
    before = {_CROSS_A: 2}
    exp = compute_equip_drag_expect(
        EquipDragIntent(kind='wear', source_name=_CROSS_A), before)
    assert exp is not None and exp.owned_before == {_CROSS_A: 2}
    before[_CROSS_A] = 99
    assert exp.owned_before == {_CROSS_A: 2}


# ===== ② 定型帧对账判据真值表 =====

def test_compare_counts_consistent_and_mismatch():
    """期望格数 = before + delta:一致 → 空;不等 → 每名一条不一致行。"""
    exp = EquipExpect(kind='wear', summary='wear A', deltas={'A': -1},
                      owned_before={'A': 2})
    cells = [_cell('A'), _cell('A'), _cell('B')]   # 期望 2-1=1 格,实读 2 格
    m = compare_equip_expect(exp, cells)
    assert len(m) == 1 and m[0] == {'domain': 'equip_grid', 'slot': 'A',
                                    'expected': '1格', 'observed': '2格'}
    assert compare_equip_expect(exp, [_cell('A'), _cell('B')]) == []   # 一致
    assert compare_equip_expect(exp, [_cell('B')]) != []               # A 清空过头


def test_compare_occluded_skips_all():
    """存在遮挡格 → 计数不可信 → 整体跳过不评(不算一致也不算不一致,
    equipment_mechanics §1.1 不堆叠语义下遮挡格可能藏着 deltas 涉及件)。"""
    exp = EquipExpect(kind='wear', summary='wear A', deltas={'A': -1},
                      owned_before={'A': 2})
    assert compare_equip_expect(exp, [_cell('A'), _cell(occluded=True)]) == []


def test_compare_ignores_unrelated_names():
    """deltas 未涉及的名字(存量漂移)不进本对账(归 reconcile_tracking)。"""
    exp = EquipExpect(kind='unequip', summary='unequip A', deltas={'A': +1},
                      owned_before={})
    assert compare_equip_expect(exp, [_cell('A'), _cell('X'), _cell('Y')]) == []


# ===== ③ 接线源码锁(静态结构,防重构断链/改口径)=====

def test_w543_wiring_locks():
    """①卖上阵角色期望在动作发出点(execute 之前)构建;②对账在 heavy
    重观察(定型帧)之后、仅 progressed 分支;③对账读法 = read_equip_grid
    纯读 + 复用定型帧(last_screenshot),不经 read_bench_chars;
    ④台账参数锁;⑤合成规则单一源 = cw_synthesis。"""
    src = Path('src/sr_od/application/currency_war/prep_director.py').read_text(
        encoding='utf-8')
    loop_at = src.index('action = match.strategy.decide_prep_action(obs, session, config)')
    exec_at = src.index('progressed, detail = self._executor.execute(action)', loop_at)
    emit_at = src.index('if isinstance(action, SellDeployed):', loop_at)
    build_at = src.index('self._equip_expect_for_sell(action)', loop_at)
    assert emit_at < exec_at
    assert build_at < exec_at
    # ② 对账点:heavy 重观察之后、仅 progressed 分支
    obs_at = src.index('obs = self._observe(heavy=True)', exec_at)
    rec_at = src.index('self._reconcile_equip_expect(_equip_expect)')
    assert obs_at < rec_at
    assert 'if progressed and _equip_expect is not None:' in src
    # ③ 纯读路径
    method = src[src.index('def _reconcile_equip_expect'):]
    method = method[:method.index('\n    def ')]
    assert 'read_equip_grid(' in method
    assert 'last_screenshot' in method
    assert 'read_bench_chars(' not in method
    # ④ 台账参数锁(常量定义 + 接线点使用)
    assert "_EQUIP_DEFECT_SURFACE = 'equip'" in src
    assert "_EQUIP_DEFECT_KIND = 'equip_expect_mismatch'" in src
    assert 'record_defect(\n                _EQUIP_DEFECT_SURFACE, _EQUIP_DEFECT_KIND,' in src
    assert 'equip_expect_reconcile' in src
    # ⑤ 合成单一源:_synth_pair 只转发 cw_synthesis,不自造配对逻辑
    synth = src[src.index('def _synth_pair'):]
    synth = synth[:synth.index('\n\n\n')]
    assert 'synthesize_target(' in synth
    assert 'self_advance(' in synth
    assert 'CROSS_RECIPES' not in synth   # 不直接摸图谱常量(派生/判定归 cw_synthesis)


def test_w543_sell_build_best_effort_locks():
    """期望构建端:遮挡污染 before 快照即不评;全程 best-effort(异常吞掉
    返 None,不阻塞动作执行)。"""
    src = Path('src/sr_od/application/currency_war/prep_director.py').read_text(
        encoding='utf-8')
    build = src[src.index('def _equip_expect_for_sell'):]
    build = build[:build.index('\n    def ')]
    assert 'any(c.occluded for c in cells)' in build
    assert 'except Exception' in build
    assert 'return None' in build


# ===== ④ 台账行形态 + 对账流为(stub director;台账行经 monkeypatch 捕获)=====

def _stub_director(frame: object | None) -> tuple[PrepDirector, list[tuple]]:
    """免 SrContext 构造的 PrepDirector(object.__new__ + stub ctx,
    test_cw_w552_xp_reconcile._stub_director 同款)。"""
    pd = object.__new__(PrepDirector)
    pd.ctx = SimpleNamespace()
    pd.last_screenshot = frame
    pd._cached_state = SimpleNamespace(plane=1, round_num=3)
    captured: list[tuple] = []
    return pd, captured


def _cap(*a, **k):
    return (a, k)


def test_reconcile_clean_and_occluded_no_row(monkeypatch):
    """一致 / 遮挡不评:不落台账。"""
    exp = EquipExpect(kind='wear', summary='wear A', deltas={'A': -1},
                      owned_before={'A': 2})
    pd, captured = _stub_director(frame=object())
    monkeypatch.setattr(defects, 'record_defect', _cap)
    monkeypatch.setattr(cw_equipment, 'ensure_equip_sift_templates',
                        lambda ctx: {'t': object()})
    monkeypatch.setattr(cw_equipment, 'read_equip_grid',
                        lambda frame, templates: [_cell('A'), _cell('B')])
    pd._reconcile_equip_expect(exp)
    assert captured == []
    # 遮挡 → 整体不评
    monkeypatch.setattr(cw_equipment, 'read_equip_grid',
                        lambda frame, templates: [_cell(occluded=True)])
    pd._reconcile_equip_expect(exp)
    assert captured == []


def test_reconcile_mismatch_rows_defect(monkeypatch):
    """不一致 → 落一条 equip/equip_expect_mismatch 台账(surface/kind/
    reader_source/refs 形态;plane/round 取 cached_state)。"""
    exp = EquipExpect(kind='wear', summary='wear A', deltas={'A': -1},
                      owned_before={'A': 2}, product='')
    pd, captured = _stub_director(frame=object())
    monkeypatch.setattr(defects, 'record_defect',
                        lambda *a, **k: captured.append((a, k)))
    monkeypatch.setattr(cw_equipment, 'ensure_equip_sift_templates',
                        lambda ctx: {'t': object()})
    monkeypatch.setattr(cw_equipment, 'read_equip_grid',
                        lambda frame, templates: [_cell('A'), _cell('A')])
    pd._reconcile_equip_expect(exp)
    assert len(captured) == 1
    args, kwargs = captured[0]
    assert args[:2] == ('equip', 'equip_expect_mismatch')
    assert kwargs['reader_source'] == 'equip_expect_reconcile'
    assert kwargs['plane'] == 1 and kwargs['round_num'] == 3
    assert kwargs['gap_large'] is True
    refs = {r['field']: r['value'] for r in kwargs['refs']}
    assert refs['kind'] == 'wear' and refs['deltas'] == 'A:-1'
    assert '期望[1格]' in kwargs['observed'] and '实读[2格]' in kwargs['observed']


def test_reconcile_best_effort_no_frame(monkeypatch):
    """last_screenshot 缺失 / 读链异常:静默跳过,不抛不落账(best-effort)。"""
    exp = EquipExpect(kind='wear', summary='wear A', deltas={'A': -1},
                      owned_before={'A': 2})
    pd, captured = _stub_director(frame=None)
    monkeypatch.setattr(defects, 'record_defect', _cap)
    pd._reconcile_equip_expect(exp)
    assert captured == []
    pd2, captured2 = _stub_director(frame=object())
    monkeypatch.setattr(cw_equipment, 'ensure_equip_sift_templates',
                        lambda ctx: (_ for _ in ()).throw(RuntimeError('x')))
    pd2._reconcile_equip_expect(exp)
    assert captured2 == []


def test_defect_row_shape(tmp_path: Path, monkeypatch):
    """defect_ledger.jsonl 行形态:surface='equip'/kind='equip_expect_mismatch';
    分级:equip=中决策相关面,单次(未复现)→ L2 留证初判
    (judge_severity 既有规则,复现升 L1 由分级承接)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    defects.record_defect(
        'equip', 'equip_expect_mismatch',
        expected='equip wear A',
        observed='A 期望[1格] 实读[2格]',
        plane=1, round_num=3, gap_large=True,
        reader_source='equip_expect_reconcile')
    rows = [ln for ln in
            (tmp_path / 'defect_ledger.jsonl').read_text(encoding='utf-8').splitlines()
            if ln.strip()]
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row['surface'] == 'equip'
    assert row['kind'] == 'equip_expect_mismatch'
    assert row['reader_source'] == 'equip_expect_reconcile'
    assert row['severity'] == SEVERITY_L2_RECORD

from sr_od.application.currency_war.kernel.cw_telemetry_exit import SEVERITY_L2_RECORD


from sr_od.application.currency_war.telemetry import state
