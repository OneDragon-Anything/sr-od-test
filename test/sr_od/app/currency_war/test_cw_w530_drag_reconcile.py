"""拖动期望态对账网(期望态层·逻辑版本;观测自检框架设计 §2.2 同族,
架构原则=用户 2026-08-28 裁决「期望态=动作意图的纯函数,定型帧逐槽对账,
不一致落缺陷台账复现升 L0」)。

测四类:①期望态计算真值表(卖出/空槽落位/互换/同名占位不评/源身份未识别
不评)②定型帧对账判据真值表(身份未识别槽=不评跳过,不算不一致)③接线
源码锁(期望态在动作发出点计算、对账在 heavy 定型帧后、纯读路径绕开
read_bench_chars 停机钩子、台账参数锁)④台账行形态锁(surface/kind/
reader_source;复现分级语义由 judge_severity 既有锁覆盖,不重复断言)。
全部纯函数/tmp_path,零触网零落盘真实路径。
"""
from pathlib import Path

from sr_od.application.currency_war.telemetry import cw_telemetry
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.kernel.cw_prep_actions import DeployMove, SellBench
from sr_od.application.currency_war.prep_director import (
    compare_drag_expect,
    compute_drag_expect,
)


def _bc(slot: int, char_id: str, pref: str = 'back') -> BenchChar:
    return BenchChar(slot=slot, char_id=char_id, star=1, position_pref=pref)


# ===== ① 期望态计算真值表(动作意图 → 期望态)=====

def test_expect_sell_truth_table():
    """卖出:源槽身份已知 → 期望=该槽身份消失;未识别 → None 不评。"""
    exp = compute_drag_expect(SellBench(slot=3), [_bc(3, '希儿')], [])
    assert exp is not None
    assert (exp.kind, exp.identity, exp.from_slot) == ('sell', '希儿', 3)
    assert compute_drag_expect(SellBench(slot=5), [_bc(3, '希儿')], []) is None
    assert compute_drag_expect(SellBench(slot=1), [], []) is None


def test_expect_deploy_move_place_vs_swap():
    """拖到部署排:空槽落位=原空+目标该角色;异名占位=互换;同名占位=
    merge_mechanics.md §3 恒成立约束「场上同名同星≤1」+部署链 5.1.7
    不变量「同角色在场只1」下不可达(游戏拒绝)→ None 不评;源身份
    未识别 → None。"""
    exp = compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                         ),
                              [_bc(2, '希儿')],
                              [_bc(2, '花火', 'front')])
    assert exp is not None
    assert exp.target_kind == 'place'
    assert (exp.identity, exp.from_slot, exp.target_row, exp.target_slot) == \
        ('希儿', 2, 'front', 1)

    exp2 = compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                          ),
                               [_bc(2, '希儿')],
                               [_bc(1, '景元', 'front')])
    assert exp2 is not None
    assert exp2.target_kind == 'swap'
    assert exp2.target_identity == '景元'

    assert compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                          ),
                               [_bc(2, '希儿')],
                               [_bc(1, '希儿', 'front')]) is None
    assert compute_drag_expect(DeployMove(from_slot=4, to_row='front', to_slot=1,
                                          ),
                               [_bc(2, '希儿')], []) is None


def test_expect_non_drag_action_is_none():
    """非拖动动作(以 SellDeployed 为代表)不进期望态层。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import SellDeployed
    assert compute_drag_expect(SellDeployed(row='front', slot=1),
                               [_bc(1, '希儿')], []) is None


# ===== ② 定型帧对账判据真值表 =====

def test_compare_sell():
    """卖出:源槽仍出现该身份=不一致;槽空/其他身份/未识别=不判不一致。"""
    exp = compute_drag_expect(SellBench(slot=3), [_bc(3, '希儿')], [])
    assert compare_drag_expect(exp, [_bc(3, '希儿')], []) != []   # 身份仍在=不一致
    assert compare_drag_expect(exp, [], []) == []                 # 槽空=通过
    assert compare_drag_expect(exp, [_bc(3, '景元')], []) == []   # 其他身份不构成本判据
    assert compare_drag_expect(exp, [_bc(3, '')], []) == []       # 未识别槽不评


def test_compare_place():
    """空槽落位:源槽已清+目标=该身份 → 一致;源未清/目标异身份 → 不一致;
    目标未识别 → 不评跳过。"""
    exp = compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                         ),
                              [_bc(2, '希儿')],
                              [_bc(1, '景元', 'front')])
    assert compare_drag_expect(exp, [], [_bc(1, '希儿', 'front')]) == []
    # 源未清
    m = compare_drag_expect(exp, [_bc(2, '希儿')], [_bc(1, '希儿', 'front')])
    assert len(m) == 1 and m[0]['domain'] == 'bench'
    # 目标异身份
    m2 = compare_drag_expect(exp, [], [_bc(1, '景元', 'front')])
    assert len(m2) == 1 and m2[0]['domain'] == 'deployed.front'
    # 目标未识别 → 跳过(不算不一致)
    assert compare_drag_expect(exp, [], []) == []


def test_compare_swap():
    """互换:源槽=原目标身份+目标槽=被拖身份 → 一致;任一侧身份不符 → 不一致;
    未识别侧 → 不评。"""
    exp = compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                         ),
                              [_bc(2, '希儿')],
                              [_bc(1, '景元', 'front'), _bc(2, '花火', 'front')])
    assert exp.target_kind == 'swap'
    assert compare_drag_expect(exp, [_bc(2, '景元')],
                               [_bc(1, '希儿', 'front')]) == []
    m = compare_drag_expect(exp, [_bc(2, '花火')], [_bc(1, '希儿', 'front')])
    assert len(m) == 1 and m[0]['domain'] == 'bench'
    m2 = compare_drag_expect(exp, [_bc(2, '景元')],
                             [_bc(1, '花火', 'front')])
    assert len(m2) == 1 and m2[0]['domain'] == 'deployed.front'
    assert compare_drag_expect(exp, [], []) == []   # 全未识别 → 不评


# ===== ③ 接线源码锁(静态结构,防重构断链/改口径)=====

def test_w530_wiring_locks():
    """①期望态在动作发出点(execute 之前)从意图计算;②对账在 heavy 重观察
    (定型帧)之后且仅 progressed 分支;③身份读=identify_slots 纯读组合,
    不经 read_bench_chars(内置停机钩子);④台账参数锁。"""
    src = Path('src/sr_od/application/currency_war/prep_director.py').read_text(
        encoding='utf-8')
    # ① 发出点:compute 在主环 execute 之前(锚主环 decide,避开破警告分支
    #    更早的 execute——该分支无定型帧,本就不进对账)
    loop_at = src.index('action = match.strategy.decide_prep_action(obs, session, config)')
    exec_at = src.index('progressed, detail = self._executor.execute(action)', loop_at)
    emit_at = src.index('if isinstance(action, (SellBench, DeployMove)):', loop_at)
    comp_at = src.index('compute_drag_expect(', loop_at)
    assert emit_at < exec_at
    assert comp_at < exec_at
    # ② 对账点:heavy 重观察之后、仅 progressed 分支
    obs_at = src.index('obs = self._observe(heavy=True)', exec_at)
    rec_at = src.index('self._reconcile_drag_expect(_drag_expect)')
    assert obs_at < rec_at
    assert 'if progressed and _drag_expect is not None:' in src
    # ③ 纯读路径:对账方法内用 identify_slots / read_deployed_chars,无 read_bench_chars
    method = src[src.index('def _reconcile_drag_expect'):]
    method = method[:method.index('\n    def ')]
    assert 'identify_slots(' in method
    assert 'read_deployed_chars(' in method
    assert 'read_bench_chars(' not in method   # 文档提及可,调用不可
    assert 'last_screenshot' in method   # 零新增截屏:复用定型帧
    # ④ 台账参数锁(surface/kind 常量定义 + 接线点使用)
    assert "_DRAG_DEFECT_SURFACE = 'bench'" in src
    assert "_DRAG_DEFECT_KIND = 'intent_state_mismatch'" in src
    assert 'record_defect(\n                _DRAG_DEFECT_SURFACE, _DRAG_DEFECT_KIND,' in src
    assert 'drag_expect_reconcile' in src


# ===== ④ 台账行形态锁 =====

def test_defect_row_shape(tmp_path: Path, monkeypatch):
    """不一致行落 defect_ledger:surface/kind/reader_source/gap_large 形态;
    分级(bench=决策关键面:单次 L1、复现 L0 由安灯承接)由既有分级锁覆盖。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        cw_telemetry.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    cw_telemetry.record_defect(
        'bench', 'intent_state_mismatch',
        expected='deploy_move identity=希儿 from_slot=2 target=front1/place',
        observed='bench槽2 期望[无 希儿(已离槽)] 实读[希儿]',
        plane=1, round_num=3, gap_large=True,
        reader_source='drag_expect_reconcile')
    rows = [ln for ln in
            (tmp_path / 'defect_ledger.jsonl').read_text(encoding='utf-8').splitlines()
            if ln.strip()]
    assert len(rows) == 1
    import json
    row = json.loads(rows[0])
    assert row['surface'] == 'bench'
    assert row['kind'] == 'intent_state_mismatch'
    assert row['reader_source'] == 'drag_expect_reconcile'
    # 分级:bench=决策关键面+大 gap 单次 → L1 初判(复现第 2 次起 L0 由安灯承接;
    # gap_large 是判级输入非落盘字段,severity 即其结果)
    assert row['severity'] == cw_telemetry.SEVERITY_L1_ALERT
