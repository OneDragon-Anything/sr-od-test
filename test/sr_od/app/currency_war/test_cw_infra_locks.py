"""test_cw_infra_locks 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- l0_andon_default_off: test_cw_l0_andon_default_off.py
- w515_l0_andon: test_cw_w515_l0_andon.py
- dead_arm_cleanup_locks: test_cw_dead_arm_cleanup_locks.py
- sim_cli_smoke: test_cw_sim_cli_smoke.py
- replay_reader: test_cw_replay_reader.py
- w944b_planner_click_fix: test_cw_w944b_planner_click_fix.py
- synthesis_chain: test_cw_synthesis_chain.py
- telemetry_roots(2026-09-07 遥测/深评布局裁定,T-125): 根常量单一源守卫
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== telemetry_roots(布局单一源守卫)====================
import re
from pathlib import Path

import pytest
from fixtures.masked_scan import (
    MaskedSource,
    build_masked_sources,
    find_violations,
    scan_code_violations,
)

from one_dragon.utils.file_utils import get_project_root
from sr_od.application.currency_war.telemetry import defects, recorder

_L0 = 'sr_od.application.currency_war.telemetry.defects'
from sr_od.application.currency_war.telemetry import state


def test_telemetry_roots_single_source() -> None:
    """布局单一源守卫(T-125,2026-09-07 用户裁定):telemetry/live、
    telemetry/matches、telemetry/sim、deep_review 四根只在
    ``kernel/cw_observe`` 根常量块声明一次,消费方(写端 op_journal/
    obs_conflict、装配端 match_archive、sim 侧 pool/runner/生成器)
    一律经 import 取用,禁第二份字面量。

    出处 = 用户裁定「遥测固定 .debug/currency_war/telemetry/{live,matches,sim}
    + 深评固定 .debug/currency_war/deep_review」;旧根
    .debug/temp/currency_war/{replay,sim_runs} 同日退役,存量已迁
    (tools/cw/migrate_telemetry_tree.py,可重跑补迁)。红时先查:
    谁又在本地重声明了根字面量 → 收拢到 cw_observe import,而不是改值。"""
    from sr_od.application.currency_war.kernel import cw_observe as obs
    from sr_od.application.currency_war.sim import cw_delta_pool_gen as _gen
    from sr_od.application.currency_war.sim import pool as _pool
    from sr_od.application.currency_war.sim import runner as _runner
    from sr_od.application.currency_war.telemetry import match_archive as _arch
    from sr_od.application.currency_war.telemetry import op_journal as _oj

    root = get_project_root()
    # ① 根常量块本体:四根一源,值 = 裁定字面
    assert root / '.debug' / 'currency_war' / 'telemetry' == obs.TELEMETRY_ROOT
    assert obs.LIVE_DIR == obs.TELEMETRY_ROOT / 'live'
    assert obs.MATCHES_ROOT == obs.TELEMETRY_ROOT / 'matches'
    assert obs.SIM_ROOT == obs.TELEMETRY_ROOT / 'sim'
    assert root / '.debug' / 'currency_war' / 'deep_review' == obs.DEEP_REVIEW_ROOT
    # ② 写端/读端全走 import(同值断言:与根常量块同一目录,非第二份字面量)
    assert _oj._JOURNAL.parent == obs.LIVE_DIR
    # (obs._CONFLICT_JOURNAL 根常量已随删除波 1 移除——obs_conflicts 写端
    #  退役,证据归宿 journal;根常量块其余四根照旧单一源。)
    assert obs.DEFAULT_REPLAY_DIR == obs.LIVE_DIR
    # ③ 装配端:生产 live 根 → 兄弟 matches 根;其他目录(测试合成流)→ 子目录
    assert _arch.matches_dir(obs.LIVE_DIR) == obs.MATCHES_ROOT
    assert _arch.matches_dir(Path('some_tmp') / 'replay') == (
        Path('some_tmp') / 'replay' / 'matches')
    # ④ sim 侧:批根与 auto 池源同源 import(禁镜像字面量)
    assert _runner.SIM_RUNS_DIR == obs.SIM_ROOT
    assert _pool._AUTO_REPLAY_DIR == obs.DEFAULT_REPLAY_DIR
    assert _gen.REPLAY_DIR == obs.DEFAULT_REPLAY_DIR
    assert _gen.SIM_RUNS_DIR == obs.SIM_ROOT
    # ⑤ 消费端契约:sim 批根与生产 live 根必须是两个不同目录
    # (write_batch_ledger 的禁写守卫比对对象 = 生产 live 根,守卫若失明,
    # sim 账本可静默写进 live 流 —— 自中毒回路,守卫报错文案引用 SIM_ROOT)
    assert obs.SIM_ROOT != obs.LIVE_DIR


def test_telemetry_old_root_tombstone(
        _masked_sources: list[MaskedSource]) -> None:
    """墓碑扫描(退役背书):旧根路径字面量在活代码面零残留。

    退役对象 = ``.debug/temp/currency_war/replay`` 与
    ``.debug/temp/currency_war/sim_runs``(2026-09-07 布局裁定,T-125)。
    扫描面 = src 的 currency_war 包 + tools/cw + skill scripts(默认根的
    消费面);显式豁免两类:①迁移工具 migrate_telemetry_tree.py(其职责
    就是定位旧根搬运存量,旧根字面量是它的输入契约);②tools/cw/proofs/
    证明语料读端(历史冻结件,数据出处注记按写作时点记录旧根,禁随批
    改写——下次重跑证明时再顺带迁移)。出现新命中 = 有人把
    旧根写回活代码,按退役裁定驳回;文档/测试注释提及旧根不在此列
    (历史出处引用合法,本扫描只辖会执行的路径字面量)。

    判定域 = 掩蔽代码域(T-103 迁移;手法单一源 = fixtures/masked_scan.py
    (T-107 收敛;手法定型版 = 测试仓 commit 149f86b)):注释/docstring 里
    的退役背书与历史出处注记按字符
    置空豁免——「旧根已退役」类负向声明是退役背书而非路径字面量;
    代码域字符串字面量(真实路径引用)仍判红,防写回。tokenize/ast
    失败回退原文全判(宁误红不漏判)。"""
    pattern = re.compile(r'temp[/\\]+currency_war[/\\]+(replay|sim_runs)')
    exempt_files = {'migrate_telemetry_tree.py'}
    exempt_dirs = {'proofs'}
    # 生成器产物:META.source_dir 记录生成时点的池源目录(数据出处快照,
    # 非活跃写点),Δ池再生自新根跑一遍即自动跟上,不在墓碑辖域
    exempt_files.add('cw_delta_pool_data.py')
    hits: list[str] = []
    for src in _masked_sources:
        if (src.path.name in exempt_files
                or exempt_dirs & set(src.path.parts)
                or '__pycache__' in src.path.parts):
            continue
        for lineno, _snippet, _pi in find_violations(src.masked, pattern):
            hits.append(
                f'{src.path.relative_to(get_project_root())}:{lineno}')
    assert not hits, ('旧根路径字面量回流活代码(布局已退役,T-125): '
                      f'{hits[:10]}')


# 旧根墓碑扫描根(与锁体逐字同源三根;掩蔽语料构建走进程内缓存,
# currency_war 根那份与 old_stream/runnode 扫描锁共享,T-107)。
_SCAN_ROOTS: tuple[Path, ...] = (
    get_project_root() / 'src' / 'sr_od' / 'application' / 'currency_war',
    get_project_root() / 'tools' / 'cw',
    get_project_root() / 'skills' / 'sr-od-currency-war-dev' / 'scripts',
)


@pytest.fixture(scope='module')
def _masked_sources() -> list[MaskedSource]:
    """旧根墓碑锁共享掩蔽语料(module 级;三根顺序拼接)。"""
    sources: list[MaskedSource] = []
    for root in _SCAN_ROOTS:
        sources.extend(build_masked_sources(root))
    return sources


def test_old_root_tombstone_scan_mutation_selfcheck() -> None:
    """旧根墓碑掩蔽式扫描变异自检(双向):负向声明/出处注记不判红,
    代码域路径字面量仍判红。

    防两种回归:①豁免写宽 → 真实写回漏判;②豁免失效(回退逐行原文)→
    docstring「旧根已退役」负向声明误红复发。含跨 token 复合形态
    (多行语句中代码 token 与注释行相邻)。合成语料直扫共享实现
    scan_code_violations(fixtures.masked_scan),不落扫描根。"""
    pattern = re.compile(r'temp[/\\]+currency_war[/\\]+(replay|sim_runs)')
    old_root = 'temp/currency_war/replay'
    # 豁免腿:注释/docstring 中的退役背书与历史出处注记不得判红
    assert scan_code_violations(
        '# 旧根 .debug/temp/currency_war/replay 已退役(T-125),禁写回',
        pattern) == []
    assert scan_code_violations(
        '"""旧根 .debug/temp/currency_war/sim_runs 同日退役,存量已迁。"""',
        pattern) == []
    # 检出腿:代码域路径字面量(裸字面量/dict 值/调用实参)必须判红
    hits = scan_code_violations(f'replay_dir = r".debug/{old_root}"',
                                 pattern)
    assert len(hits) == 1, f'路径字面量写回复活形须红,实得 {hits}'
    hits = scan_code_violations(
        "cfg = {'dir': 'temp/currency_war/sim_runs'}", pattern)
    assert len(hits) == 1, f'dict 值写回复活形须红,实得 {hits}'
    # 混合腿:行尾注释不豁免同行代码引用(豁免按 token 置空,不按行)
    hits = scan_code_violations(
        f'x = "{old_root}"  # 旧根已退役(负向声明)', pattern)
    assert len(hits) == 1, f'行尾注释不豁免同行代码,实得 {hits}'
    # 跨 token 复合形:引用行与注释行相邻,掩蔽只吞注释行不吞引用行
    hits = scan_code_violations(
        f'p = Path(".debug/{old_root}")\n# 旧根已退役\nlog.info(p)', pattern)
    assert len(hits) == 1 and hits[0][0] == 1, \
        f'隔行注释掩蔽不吞引用行,实得 {hits}'


# ==================== l0_andon_default_off ====================

def _setup_isolated_l0(tmp_path: Path, monkeypatch) -> Path:
    """台账指向 tmp + 安灯槽/闩锁/复现账隔离(与 w505 _setup_recorder 同链)。"""

    monkeypatch.setattr(state, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(state, '_CURRENT_RUN_ID', 'l0iso')
    monkeypatch.setattr(state, '_defect_seen', {})
    monkeypatch.setattr(state, '_defect_seen_run', '')
    monkeypatch.setattr(state, '_L0_ANDON_FIRED_RUNS', set())
    return tmp_path


def test_default_handler_off_is_noop(tmp_path: Path, monkeypatch) -> None:
    """锁1:缺省(Handler=None)触发 L0 → 台账照记 L0_andon,游戏侧停线实现
    不得被触达(canary 挂在 cw_observe,被调即炸)。"""
    from sr_od.application.currency_war.kernel import cw_observe
    d = _setup_isolated_l0(tmp_path, monkeypatch)
    monkeypatch.setattr(state, '_L0_ANDON_HANDLER', None)   # 缺省态显式钉住

    def _canary(payload: dict) -> bool:
        raise AssertionError('缺省关态下停线实现被触达(惰性接线回归?)')

    monkeypatch.setattr(cw_observe, 'stop_for_l0_andon', _canary)

    for _ in range(2):   # 同特征第 2 次 = 复现 → 判级 L0
        defects.record_defect('gold', 'perception_conflict',
                         'gold_delta: 45', '20', gap=-25.0, gap_large=True)

    rows = [__import__('json').loads(ln) for ln in
            (d / 'defect_ledger.jsonl').read_text(encoding='utf-8').splitlines()
            if ln.strip()]
    assert [r['severity'] for r in rows] == ['L1_alert', 'L0_andon']


def test_no_lazy_wiring_in_fire_and_app_arms_handler() -> None:
    """锁2:_fire_l0_andon 源码不含惰性 import(防改回);生产武装点
    (CurrencyWarApp.__init__ 显式 set_l0_andon_handler)在场。"""
    import inspect

    from sr_od.application.currency_war.currency_war_app import CurrencyWarApp

    assert 'stop_for_l0_andon' not in inspect.getsource(defects._fire_l0_andon), (
        '_fire_l0_andon 禁止惰性接真实现(缺省必须关,武装点在 app)')
    assert 'set_l0_andon_handler' in inspect.getsource(CurrencyWarApp.__init__), (
        'CurrencyWarApp.__init__ 缺 L0 安灯显式武装(生产停线将静默失效)')


def test_a_run_leftover_pollution_is_written(test_context) -> None:
    """锁3-前半:人为遗留运行停机位(模拟 w505 型污染;conftest 守卫在
    teardown 复位)。本测试断言写入成立,清洗效果由下一个测试钉住。"""
    test_context.run_context.last_run_result = object()
    assert test_context.run_context.last_run_result is not None


def test_b_run_leftover_is_reset_by_guard(test_context) -> None:
    """锁3-后半:上一测试遗留的停机位必须已被 conftest 守卫复位为 None
    ——守卫失效时本测试红(全集假红的结构性防线,不许静默退化)。"""
    assert test_context.run_context.last_run_result is None, (
        'conftest 运行残留守卫失效:last_run_result 跨测试泄漏'
        '(后续 execute() 将撞 W209j 刹车)')


def test_autouse_stubs_pin_stop_flag_channels(tmp_path: Path) -> None:
    """锁4:conftest autouse 桩在场——停机 flag 族 / exec_fail 族的模块级
    全局在每条测试开始前被钉回隔离态(见 conftest `_isolate_cw_stop_flag_channels`)。
    失守形态:有人删桩 → telemetry 单例回到真实 .debug/ 落盘域,测试台账行
    混进实机 defect_ledger(实证:w323-run 2290 行残渣);flag 路径回真 →
    测试触发钩子写真停机 flag。本锁红 = 隔离层被拆,先查桩再动断言。"""
    from sr_od.application.currency_war import run_state
    from sr_od.application.currency_war.telemetry import defects, state

    # 落盘域已移出真实 .debug/:recorder 指向本测试的 tmp 域
    rec = state._RECORDER
    assert rec is not None and rec.enabled and rec.replay_dir.is_absolute()
    assert '.debug' not in rec.replay_dir.parts, rec.replay_dir
    # run_id 钉空串(便捷入口空 id 门控 no-op;防跨测试局归属泄漏)
    assert state._CURRENT_RUN_ID == ''
    # 进程内闩锁/计数器均为干净缺省
    assert not state._L0_ANDON_FIRED_RUNS
    assert not state._defect_seen and state._defect_seen_run == ''
    # (简报缓冲/暂存槽三件复位桩已随删除波 1 移除——槽本体随旧流写入端退役。)
    # flag 路径常量钉 tmp 绝对路径(get_project_root() / 绝对路径 = 绝对路径)
    assert defects.l0_andon_flag_path().is_relative_to(tmp_path)
    assert run_state.exec_fail_flag_path().is_relative_to(tmp_path)



# ==================== w515_l0_andon ====================

import json
from pathlib import Path as _w515_l0_andon_Path

from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.telemetry import defects as _w515_l0_andon_defects
from sr_od.application.currency_war.telemetry import defects as cw_telemetry
from sr_od.application.currency_war.telemetry import recorder as _w515_l0_andon_recorder
from sr_od.application.currency_war.telemetry import state as _telstate


def _setup(monkeypatch, tmp_path: _w515_l0_andon_Path, run_id: str = 'w515t') -> list[dict]:
    """recorder/run_id/闩锁指向测试态;注入假执行器收集触发载荷。返回调用记录。"""
    monkeypatch.setattr(_telstate, '_RECORDER',
                        _w515_l0_andon_recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(_telstate, '_CURRENT_RUN_ID', run_id)
    # 复现计数与闩锁都是进程内状态,逐测试清空防串
    monkeypatch.setattr(_telstate, '_defect_seen', {})
    monkeypatch.setattr(_telstate, '_defect_seen_run', '')
    monkeypatch.setattr(_telstate, '_L0_ANDON_FIRED_RUNS', set())
    calls: list[dict] = []

    def _fake_handler(payload: dict) -> bool:
        calls.append(payload)
        return True

    monkeypatch.setattr(_telstate, '_L0_ANDON_HANDLER', _fake_handler)
    return calls


def _rows(tmp_path: _w515_l0_andon_Path, name: str = 'defect_ledger.jsonl') -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 首见 L0 停一次 + 闩锁 =====

def test_first_l0_stops_once_then_latch(tmp_path: _w515_l0_andon_Path, monkeypatch):
    """同特征金面大 gap 三连:首见 L1 不停 → 第 2 次 L0 停一次 → 第 3 次
    L0 只补台账不再停(局级闩锁)。台账行数=3(停线不改记录形状)。"""
    calls = _setup(monkeypatch, tmp_path)
    for _ in range(3):
        _w515_l0_andon_defects.record_defect('gold', 'perception_conflict',
                                   'gold_delta: 45', '20', gap=-25.0,
                                   gap_large=True)
    sevs = [r['severity'] for r in _rows(tmp_path)]
    assert sevs == ['L1_alert', 'L0_andon', 'L0_andon']   # 台账照记(补台账)
    assert len(calls) == 1                                 # 只停一次
    assert calls[0]['surface'] == 'gold'
    assert calls[0]['run_id'] == 'w515t'
    assert calls[0]['expected'] == 'gold_delta: 45'
    assert calls[0]['refs'] == []                          # 无 refs 安全缺省


def test_latch_key_is_run_id_resets_next_run(tmp_path: _w515_l0_andon_Path, monkeypatch):
    """闩锁键 = run_id:start_run 每局重生成 run_id → 新局首见 L0 再停
    (复现计数同款按 run 切换语义,无手动清)。"""
    calls = _setup(monkeypatch, tmp_path, run_id='run_a')
    _w515_l0_andon_defects.record_defect('gold', 'perception_conflict',
                               'x: 1', '2', gap=20.0, gap_large=True)
    _w515_l0_andon_defects.record_defect('gold', 'perception_conflict',
                               'x: 1', '2', gap=20.0, gap_large=True)
    assert len(calls) == 1
    # 新局:换 run_id(生产由 start_run 做;复现计数随之重置)
    monkeypatch.setattr(_telstate, '_CURRENT_RUN_ID', 'run_b')
    monkeypatch.setattr(_telstate, '_defect_seen', {})
    monkeypatch.setattr(_telstate, '_defect_seen_run', '')
    _w515_l0_andon_defects.record_defect('gold', 'perception_conflict',
                               'x: 1', '2', gap=20.0, gap_large=True)
    _w515_l0_andon_defects.record_defect('gold', 'perception_conflict',
                               'x: 1', '2', gap=20.0, gap_large=True)
    assert len(calls) == 2
    assert calls[1]['run_id'] == 'run_b'


# ===== ② L1/L2 永不停 =====

def test_l1_and_l2_never_stop(tmp_path: _w515_l0_andon_Path, monkeypatch):
    """L1(关键面大 gap 单次)/L2(非关键面)只落台账,执行器零调用。"""
    calls = _setup(monkeypatch, tmp_path)
    _w515_l0_andon_defects.record_defect('gold', 'perception_conflict',
                               'gold: 200', '230', gap=30.0,
                               gap_large=False)            # 小 gap → L2(特征异于下行,防复现误并)
    _w515_l0_andon_defects.record_defect('gold', 'perception_conflict',
                               'gold_delta: 45', '20', gap=-25.0,
                               gap_large=True)             # 关键面大gap首见 → L1
    _w515_l0_andon_defects.record_defect('confidence', 'perception_conflict',
                               'c: 0.9', '0.1', gap_large=True)   # 非关键面 → L2
    sevs = [r['severity'] for r in _rows(tmp_path)]
    assert sevs == ['L2_record', 'L1_alert', 'L2_record']
    assert calls == []


# ===== ③ auto_resolved 永不停 =====

def test_auto_resolved_never_stops(tmp_path: _w515_l0_andon_Path, monkeypatch):
    """裁决已自动的冲突面(auto_resolved)复现也不升 L0 → 不停
    (判据单一源在 judge_severity,接线处不双保险)。"""
    calls = _setup(monkeypatch, tmp_path)
    for _ in range(3):
        _w515_l0_andon_defects.record_defect('deployed', 'perception_conflict',
                                   'deployed_align: 4', '5',
                                   gap_large=True, auto_resolved=True)
    assert all(r['severity'] == 'L2_record' for r in _rows(tmp_path))
    assert calls == []


# ===== ④ flag 三要素内容锁(含游戏侧执行器端到端)=====

def test_flag_three_element_content_lock(tmp_path: _w515_l0_andon_Path):
    """flag 自描述内容锁:HOOK-STOP 特征行 + 发生了什么 + 定位/期望/观测/
    台账 refs + 处理步骤 + 删除条件,值班者不看代码即知发生了什么。"""
    fp = tmp_path / 'l0_andon_hook.flag'
    content = _w515_l0_andon_defects.write_l0_andon_flag(
        fp, run_id='run_x', surface='gold', kind='perception_conflict',
        expected='gold_delta: 45', observed='20',
        plane=1, round_num=3,
        refs=[{'stream': 'obs_conflicts', 'key': 'field=gold_delta|ts=2026'}],
        defect_shot='obs_conflict_gold__ab12.png',
        stop_shot='l0_andon_run_x_p1r3_stop_1.png')
    assert fp.exists()
    assert '[HOOK-STOP]' in content
    assert 'L0 分级安灯停线' in content
    assert '发生了什么' in content and '复现' in content
    assert 'run_id=run_x surface=gold kind=perception_conflict p1r3' in content
    assert '期望:gold_delta: 45' in content
    assert '观测:20' in content
    assert 'obs_conflicts:field=gold_delta|ts=2026' in content
    assert 'obs_conflict_gold__ab12.png' in content           # 缺陷自带 shot 进 refs 面
    assert 'l0_andon_run_x_p1r3_stop_1.png' in content        # 停机现场帧
    assert '处理步骤' in content and '重启' in content
    assert '删除条件' in content and '本 flag 处理完即删' in content


class _FakeRunContext:
    def __init__(self):
        self.reasons: list[str] = []

    def stop_running(self, reason: str = '') -> None:
        self.reasons.append(reason)


class _FakeCtx:
    def __init__(self):
        self.run_context = _FakeRunContext()


def test_game_side_executor_end_to_end(tmp_path: _w515_l0_andon_Path, monkeypatch):
    """cw_observe.stop_for_l0_andon 端到端(假 ctx):现场帧 → flag 落
    tmp_path → run_context.stop_running(reason=hook:cw_l0_andon) → True。

    分包期 4 起 flag 写入走 kernel/cw_telemetry_exit 安灯出口钩子位:
    注入真实现(monkeypatch 槽位,自动还原)+ flag 路径钉 tmp。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    ctx = _FakeCtx()
    monkeypatch.setattr(cw_observe, 'find_running_ctx', lambda: ctx)
    monkeypatch.setattr(cw_observe, '_save_andon_frame',
                        lambda c, p: 'l0_andon_run_x_p1r3_stop_1.png')
    monkeypatch.setattr(cw_telemetry_exit, '_write_l0_andon_flag',
                        _w515_l0_andon_defects.write_l0_andon_flag)
    monkeypatch.setattr(cw_telemetry_exit, '_l0_andon_flag_path',
                        lambda: tmp_path / 'l0_andon_hook.flag')
    ok = cw_observe.stop_for_l0_andon({
        'run_id': 'run_x', 'surface': 'gold', 'kind': 'perception_conflict',
        'expected': 'gold_delta: 45', 'observed': '20',
        'plane': 1, 'round_num': 3, 'shot': 'obs_conflict_gold__ab12.png',
        'refs': [{'stream': 'obs_conflicts', 'key': 'field=gold_delta'}],
    })
    assert ok is True
    assert ctx.run_context.reasons == ['hook:cw_l0_andon']
    content = (tmp_path / 'l0_andon_hook.flag').read_text(encoding='utf-8')
    assert '[HOOK-STOP]' in content and 'run_id=run_x' in content


def test_game_side_executor_no_ctx_is_no_stop(tmp_path: _w515_l0_andon_Path, monkeypatch):
    """找不到 ctx(离线/测试进程)→ False 不停、不写 flag
    (零误停偏置:无停线通道时不动台账以外的任何状态)。"""
    monkeypatch.setattr(cw_observe, 'find_running_ctx', lambda: None)
    # 分包期 4:安灯出口槽未注入 → 执行器在 ctx 判空即 False,不触达 flag 通道
    # (原 cw_telemetry.l0_andon_flag_path 钉位随出口化移除,路径兜底锁由 no-stop 断言承担)。
    ok = cw_observe.stop_for_l0_andon({'run_id': 'run_x', 'surface': 'gold',
                                       'kind': 'perception_conflict',
                                       'expected': 'e', 'observed': 'o'})
    assert ok is False
    assert not (tmp_path / 'l0_andon_hook.flag').exists()


# ===== ⑤ 接线存在性源码锁 =====

def test_wiring_existence_source_lock():
    """静态锁:模块级 record_defect 判级后必须接 _fire_l0_andon 且只认
    显式 L0_andon;防后续重构静默断链或放宽触发条件。"""
    src = (_w515_l0_andon_Path(cw_telemetry.__file__).read_text(encoding='utf-8')
        + _w515_l0_andon_Path(_telstate.__file__).read_text(encoding='utf-8'))
    assert 'if sev == SEVERITY_L0_ANDON:' in src
    assert src.count('_fire_l0_andon({') == 1   # 触发点唯一(收敛在判级后)
    assert 'def _fire_l0_andon' in src
    assert 'def set_l0_andon_handler' in src
    assert '_L0_ANDON_FIRED_RUNS' in src        # 局级闩锁在
    # 游戏侧三要素执行器在 cw_observe(判定/执行分层不倒挂)
    obs_src = _w515_l0_andon_Path(cw_observe.__file__).read_text(encoding='utf-8')
    assert 'def stop_for_l0_andon' in obs_src
    assert "stop_running(reason='hook:cw_l0_andon')" in obs_src



# ==================== dead_arm_cleanup_locks ====================

from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY

_DELETED_FIELDS = (
    'goldrich_buy_bias', 'goldrich_min_gold', 'goldrich_buy_tags',
    'filler_star_unit', 'pair_copy_direction_exempt',
    'early_pace_enabled', 'early_pace_min_round', 'early_pace_max_round',
    'early_pace_bias', 'early_pace_val_max',
)
_SYMBOLS = ('goldrich', 'early_pace', 'filler_star',
            'pair_copy_direction')
# (_decision_v2_dir 已随 decision/ 整包删除——统一迁移批 ②;
#  源码面符号守卫对象消亡,registry 字段面守卫保留。)


from pathlib import Path as _sim_cli_smoke_Path

# (2026-09-05 污染根治批补回:a8a5739 删 import 时漏带走这三处引用,smoke 红)
from sr_od.application.currency_war.data import cw_delta_pool_data
from sr_od.application.currency_war.sim.engine_p1 import (
    EQUIP_GRANT_CALIB_VERSION,
    simulate_p1,
)
from sr_od.application.currency_war.sim.runner import simulate_p1_batch


def _strip_comments_and_docstrings(text: str) -> str:
    """去 # 注释行与三引号 docstring(守卫只看活代码,定谳墓碑注释放行)。"""
    out: list[str] = []
    in_doc: str | None = None
    for line in text.splitlines():
        if in_doc is not None:
            if in_doc in line:
                in_doc = None
            continue
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            # 单行 docstring(含收尾引号)直接放行
            if not (stripped.endswith(quote) and len(stripped) >= 6):
                in_doc = quote
            continue
        if stripped.startswith('#'):
            continue
        out.append(line)
    return '\n'.join(out)


def test_registry_dead_arm_fields_absent() -> None:
    """字段面:四臂 10 字段全部不存在(hasattr=False)。"""
    for f in _DELETED_FIELDS:
        assert not hasattr(DEFAULT_REGISTRY, f), f



def test_ci_smoke_snapshot_batch(tmp_path: _sim_cli_smoke_Path) -> None:
    """smoke:快照池小批量——指纹命中提交快照+checks 全绿+确定性。"""
    rep = simulate_p1_batch(25, pool='snapshot', ledger=tmp_path / 'b1')
    # 指纹 = 提交快照指纹 + 装备发放结构版本位(供给重校准起,跨版本对照须显式失败)
    assert rep['pool_fingerprint'] == (
        cw_delta_pool_data.META['fingerprint']
        + f'+eqg{EQUIP_GRANT_CALIB_VERSION}')
    assert rep['pool_source'] == 'snapshot'
    # ADR-0268:池级检查(桶饥饿/深崖单调)是**数据披露**非策略
    # 断言——语料饥饿时恒非零(披露即目的),不适用 0 容忍;
    # 行为检查仍全绿。
    # ADR-0276:sim_endgold_calib 同为披露型收敛判据——P1-only 域
    # 末段滞留金无处可花(P2 入口继承价值 sim 不可判),比值 ~2×
    # 是已知校准层缺口(收敛条件见 ADR),不适用 0 容忍。
    _POOL_CHECKS = ('delta_pool_bucket_min_n', 'depth_cliff_monotonicity',
                    'sim_endgold_calib')
    # ADR-0289 检查项清偿批:新检查在 n=300 基线上涌现的红条目 =
    # 「新发现待裁」(真发现候选/判据过严候选),裁决归下一批——
    # smoke 豁免这些**已登记待裁**的检查(待裁清单单一源=
    # ADR-0289 §3);裁决落地(修复或判据定案)后从本豁免表移除,
    # 届时回归 0 容忍。未列名的新检查仍须全绿。
    # ADR-0294(红项修复合卷):phantom_equip_no_wear / engine_seed_
    # not_resold 两真发现已修复,n=30 批内违规 0——移出豁免,回归
    # 0 容忍。decision_v2_candidate_coverage 结构层探针红已清偿
    # (ADR-0296:sell/synthesize 生成器补完 + 探针判据修正)——
    # 移出豁免,回归 0 容忍。
    # 批㉜ F4 价值表覆盖披露(ADR-0303 合流批登记):key_equips ≥3
    # 引用但 _EQUIP_VALUE 缺值——已由 ADR-0555 补值批清偿(15 名全量
    # 入表 + 检查项扩全量披露),移出豁免回归 0 容忍;专项锁 =
    # test_cw_equip_value_table.py。
    # ADR-0336:dead_system_second_pivot 等 v1 检查器已删(见下方注释);
    # ledger_consistency / coldstart_direction 是 v2 已知债(W66 §4 条件
    # 3:12/400 与 79/400,d2 行为面批清)——sim 默认策略切 decision_v2
    # 后固定 seed 域触发,登记豁免。
    # ADR-0338(W85):②资格门落地后,稳定 env 锁局(seed16)涌现
    # engine_seed 买入 2 轮内回卖 1/25(姬子·启行 r4 买 r5 卖 r7 再买
    # ——锁线稳定后 off-target 引擎种子的买/卖两侧判据互踩,振荡形)
    # ——按 ADR-0289 纪律登记待裁(裁决归下一批:买侧 engine_seed
    # 与卖侧 off-target 让位的豁免边怎么划),未裁决前豁免。
    # ADR-0347(FORM_FLOOR=20 保险丝初值接线):相位地板压低金<20
    # 段的早期买入 → r2-r4 deployed 增长变慢,seed16 涌现 deploy_
    # fills_cap 1 例。裁决归步②b 的 Q1 四档 sim 对照(不设/10/20/30)
    # ——定档后从本豁免表移除,回归 0 容忍。
    # ADR-0354(检查器判据重定义):levelup_interest_engine_gate
    # 裁决已落地——判据改读授权依据(账本 LevelUp 行 auth 键);
    # ADR-0410 白名单扩为 {pop_slot, dp, static_ev}(boss 升级禁令删除
    # 后 static_ev 是末窗主授权臂;无授权依据仍计违规),seeds 0-19
    # 新判据 0 违规(旧判据 206/82 局)。回归 0 容忍。
    # mandate_v1 换核定谳批:白名单再扩 {m3_batch}——换核批(ba1176c6)
    # 的 M3 批量授权臂漏更检查器白名单致本锁预存红(seeds 9/16,裸跑
    # 才暴露:本测试在快速集被 slow 过滤);m3_batch 发射前置 =
    # arm1_existence([33] 人口位语境,与 pop_slot 同语义)∧ spend_
    # unified(P48 整买)∧ 危机让位(dd-034),授权强度不低于旧三臂
    # ——出处 = strategy-docs 02_mandate_layer.md §3 M3 / ADR-0518。
    # 锁语义(低金追级须有授权依据)不变,回归 0 容忍。
    # ADR-0357(P1 配方锁):P1 锁定产物改体系对后,锁定局 form_ok
    # 从三件套(核心 2★ 质量)切 兜底门(engines≥2,星级盲)——
    # 成型停手提前触发低质量双引擎板,seed19(n=25 snapshot)涌现危机态
    # 囤金零买 1 例(hp 22 金 51 只升不买,A 臂同 seed hp 34)。交互面在
    # decision_v2 phase/filters(本批边界=意向层单文件),按 ADR-0289
    # 纪律登记待裁(裁决:兜底门是否补质量位/危机与成型停手豁免边)。
    # 供给重校准批(发放结构重校准,行为变更有意):rng 流整体移位,
    # seed9(n=25 snapshot)涌现 gold_nonneg 1 例——r6 buys 6 + levelup 4
    # = 10 > gold_before 9,sim 执行层无金下限钳制、花超 1 金为**策略
    # 花钱规划侧既有边缘**(与装备发放零金语义无关)。按 ADR-0289 纪律
    # 登记待裁(裁决归策略域批:执行层是否补钳制/规划侧修复),未裁决
    # 前豁免;裁决落地后移除,回归 0 容忍。
    # W666(重放语境冻结,W652 §5 处置①):deploy_after_buy_semantics
    # 的 W578 待裁已裁决落地——重放趟成对/点火判据改用真部署趟行动前
    # board/deployed_fac 快照,残余语义 = 行动语境下围栏认可件未上;
    # seeds 0-19 与取证两局(seed 630027/630035)均 0,移出豁免回归
    # 0 容忍(专项锁 = test_cw_w666_replay_context_freeze.py)。
    # P1 资源循环死锁登记(2026-09-05 定谳,与编排者账本「P1 资源循环
    # 死锁/购买意图缺失」候裁行同案):overflow_gold_zero_buy_streak 与
    # gold_dist_calib 两颗被 levelup 锁短路掩蔽的预存红,违规帧语境探针
    # 实证同一根因——板满∧bench=0(arm1_existence 恒 False)∧金 103→236
    # 逐轮上涨∧全通道零动作 = 线购齐后购买意图缺失的全通道静默(与
    # C14 退役后升级授权链零输入叠加,seeds 0/1/5 streak r6-r9 直接
    # 复现)。同案三重实证索引 =
    # .debug/temp/currency_war/p1_econ_design_inputs.md(病灶证据 1-3
    # 及 sim 批3 升级零授权机制发现)。两颗按 ADR-0289 纪律登记待裁
    # (裁决归 P1 经济循环消费臂设计批),未裁决前豁免;设计批落地后
    # 移除,回归 0 容忍。
    _PENDING_ADJUDICATION = ('ledger_consistency',
                             'coldstart_direction',
                             'degrade_recover_mutex',
                             'engine_seed_not_resold',
                             'deploy_fills_cap',
                             'decision_v2_crisis_gold_hoard',
                             'gold_nonneg',
                             'overflow_gold_zero_buy_streak',
                             'gold_dist_calib')
    for name, r in rep['checks_violations'].items():
        if name in _POOL_CHECKS or name in _PENDING_ADJUDICATION:
            assert 'violations' in r, f'{name}: 缺 violations 计数'
            continue
        assert r['violations'] == 0, f'{name}: {r}'
    # 同 seed 确定性(非分布数值——逐局末 HP 全等)。从主 batch 账本 outcomes
    # 流提取逐局末 HP(run_id 尾缀 seed,每局最后一行 = 终值),对一遍轻量复跑
    # (checks/ledger 关——主 batch 已覆盖,复跑只验确定性)。旧版独立跑两遍
    # 25 局 = 全测试 75 局;W971 后主 batch + 复跑 = 50 局;2026-09-03 瘦身批
    # 复跑改抽样对账 = 主 25 + 复跑 3 = 28 局(逐位全等语义不变)。
    import json
    import re

    last_by_run: dict[int, int] = {}
    for ln in _sim_cli_smoke_Path(rep['ledger_dir'], 'outcomes.jsonl').read_text(
            encoding='utf-8').splitlines():
        row = json.loads(ln)
        m = re.search(r'_s(\d+)$', row['run_id'])
        last_by_run[int(m.group(1))] = row['hp_after']
    hps_ledger = [last_by_run[s] for s in sorted(last_by_run)]
    assert len(hps_ledger) == 25, f'账本局数异常: {len(hps_ledger)}'
    # 复跑抽样:首/中/尾 3 个 seed 对照账本行(确定性对账的抽样面)
    _RERUN_SEEDS = (0, 12, 24)
    for s in _RERUN_SEEDS:
        assert last_by_run[s] == simulate_p1(
            s, pool='snapshot').final_hp, f'seed{s} 复跑末 HP 不一致(确定性破)'


def test_levelup_budget_gate_dec_disclosure_write_end() -> None:
    """支A 谓词输入披露·写端在位锁(T-135;供给半环,README 纪律 13)。

    budget-gate 检查器支A 镜像的决策帧真值源 = 引擎在 LevelUp 执行点
    披露的 dec_board_full/dec_bench_2star(写端 = engine_p1 LevelUp
    分支;假阳定谳 = ADR-0589,谓词设计 = ADR-0576 §2.5)。写端
    断线时检查器静默回退行末近似 → t133 假阳(误报绕闸)复现,要等
    slow 锁 test_ci_smoke_snapshot_batch 才红;本锁在快速层直接钉
    写端:探针种子(seed 18,基线 17 击 m3_batch,2026-09-08 现树实测
    ——T-136 可见性行为位移后重探值)每击必携双 bool 键;
    无发射 = 探针失准,报错指向重选探针种子(存在性断言的种子锚
    同责,README 纪律 12:失准的红必须可行动)。
    """
    res = simulate_p1(18, pool='snapshot')
    gated = [a for row in res.ledger for a in row.get('actions') or []
             if a.get('__type__') == 'LevelUp'
             and str(a.get('auth', '') or '').startswith('m3_batch')]
    assert gated, '探针种子无 m3_batch 升级击(策略行为位移,重选探针种子)'
    for a in gated:
        assert isinstance(a.get('dec_board_full'), bool) \
            and isinstance(a.get('dec_bench_2star'), bool), \
            f'写端披露断线(检查器将静默回退行末近似): {a}'


# [退役墓碑,W3] test_views_render_sim_ledger 随旧视图族与 --sim-batch
# 判读入口退役(W3):sim 批目录无 journal,旧视图删后失读面;sim 批判读
# 桥期 = skills 侧 cw_batch_stats(sim 引擎自写账本,活读),journal 侧 sim
# 视图候 W6 sim 切统一容器批。git 历史可复活。
def test_sim_batch_dir_structure(tmp_path: _sim_cli_smoke_Path) -> None:
    """批次目录三流齐:decisions/outcomes/shop_snapshots.jsonl。"""
    rep = simulate_p1_batch(2, pool='fallback', seed_base=7,
                            ledger=tmp_path / 'struct', checks=False)
    d = _sim_cli_smoke_Path(rep['ledger_dir'])
    for name in ('decisions.jsonl', 'outcomes.jsonl',
                 'shop_snapshots.jsonl'):
        assert (d / name).exists(), f'缺 {name}'
    # outcomes 用生产词表(视图 NT 归一同源)
    import json
    rows = [json.loads(ln) for ln in
            (d / 'outcomes.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows and all(r.get('node_type') for r in rows[:2])
    # killed 极性=产线语义(**胜**;审查 major 曾反):delta≥0 ↔ killed
    for r in rows:
        s = r.get('sim') or {}
        if 'delta' in s and 'killed' in s:
            assert s['killed'] == (s['delta'] >= 0), \
                f"killed 极性反转(产线 killed=胜): {r}"


def test_sim_batch_p2_second_engine_full_ledger_wiring() -> None:
    """「局终」口径检查的 full_ledgers 穿线(simulate_p1_batch→批出口;ADR-0629)。

    planes=2 批的批报告 second_engine_deadline 必须出数且自描述局终
    口径。语义面(统一轴/never 判定)由
    test_second_engine_deadline_game_end_caliber 的合成两段账本锁
    承重;本烟雾钉生产接线本身——若 simulate_p1_batch 退回 P1 段
    视图喂入,输出数值静默变截断口径(T-211「never 21 超带」假警报
    根因),口径声明面仍在但本锁的出数形状由语义锁联合把守。
    fallback 池 n=2,实测 ~0.3s(快速集)。
    """
    rep = simulate_p1_batch(2, pool='fallback', seed_base=7,
                            ledger=False, planes=2)
    chk = rep['checks_violations']['second_engine_deadline']
    assert chk['first_engine_games'] == 2, chk
    assert '局终口径' in (chk['caliber_note'] or ''), chk


# ==================== replay_reader ====================

import sys
from dataclasses import is_dataclass
from pathlib import Path as _replay_reader_Path

_REPO = _replay_reader_Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import json as _replay_reader_json  # noqa: E402

from sr_od.application.currency_war.telemetry.cw_divergence_stats import (
    divergence_stats,  # noqa: E402
)
from sr_od.application.currency_war.telemetry.cw_replay_reader import (  # noqa: E402
    DecisionTrace,
    OutcomeRecord,
    from_dict,
    load_decisions,
    load_outcomes,
    posture_tag,
)


def _write(path: _replay_reader_Path, rows: list[dict]) -> _replay_reader_Path:
    path.write_text('\n'.join(_replay_reader_json.dumps(r, ensure_ascii=False) for r in rows),
                    encoding='utf-8')
    return path


def test_load_decisions_current_str_frame(tmp_path: _replay_reader_Path) -> None:
    """现行帧(str tag)→ 类型化 DecisionTrace,字段逐一对上。"""
    row = {'schema_version': 1, 'run_id': 'r1', 'round_num': 3, 'plane': 1,
           'strategy_id': 'decision_v2', 'dp_posture': '升级+D6',
           'hp': 40, 'gold_readable': True, 'actions': [{'__type__': 'BuyCard'}]}
    p = _write(tmp_path / 'decisions.jsonl', [row])
    frames = load_decisions(p)
    assert len(frames) == 1
    f = frames[0]
    assert isinstance(f, DecisionTrace) and is_dataclass(f)
    assert (f.run_id, f.round_num, f.plane) == ('r1', 3, 1)
    assert f.dp_posture == '升级+D6'
    assert f.gold_readable is True
    assert f.actions[0]['__type__'] == 'BuyCard'


def test_load_decisions_historical_dict_frame(tmp_path: _replay_reader_Path) -> None:
    """历史 dict 帧(dp_posture={'spend_mode','target_level'})容忍加载。"""
    row = {'run_id': 'r0', 'round_num': 2, 'strategy_id': '',
           'dp_posture': {'spend_mode': 'adaptive', 'target_level': 4}}
    p = _write(tmp_path / 'decisions.jsonl', [row])
    frames = load_decisions(p)
    assert len(frames) == 1
    assert frames[0].dp_posture == {'spend_mode': 'adaptive', 'target_level': 4}
    # 未声明字段忽略不炸(写端未来加字段的向前容忍)
    row_unknown = dict(row, some_future_field=42)
    p2 = _write(tmp_path / 'd2.jsonl', [row_unknown])
    assert len(load_decisions(p2)) == 1


def test_load_decisions_missing_new_fields(tmp_path: _replay_reader_Path) -> None:
    """历史帧缺新字段(form_ok/phase/dp_posture/handoff)→ dataclass 默认值,不炸。"""
    row = {'run_id': 'r0', 'round_num': 1}   # 只有关键 join 键的最老形态
    p = _write(tmp_path / 'decisions.jsonl', [row])
    f = load_decisions(p)[0]
    assert f.form_ok is False and f.phase == ''
    assert f.dp_posture == '' and f.handoff is None


def test_load_decisions_bad_lines_skipped(tmp_path: _replay_reader_Path) -> None:
    """坏行(JSON 解析失败/非 dict)跳过不抛;run_id 过滤。"""
    p = tmp_path / 'decisions.jsonl'
    p.write_text('{"run_id": "r1", "round_num": 1}\n'
                 'NOT JSON\n'
                 '"bare string"\n'
                 '{"run_id": "r2", "round_num": 2}\n', encoding='utf-8')
    frames = load_decisions(p)
    assert [f.round_num for f in frames] == [1, 2]
    assert [f.round_num for f in load_decisions(p, run_id='r2')] == [2]


def test_load_outcomes(tmp_path: _replay_reader_Path) -> None:
    """outcomes.jsonl → OutcomeRecord(含 enemy_hp_after=None 死字段容忍)。"""
    row = {'run_id': 'r1', 'round_num': 1, 'hp_after': 38,
           'enemy_hp_after': None, 'killed': True}
    p = _write(tmp_path / 'outcomes.jsonl', [row])
    recs = load_outcomes(p)
    assert len(recs) == 1 and isinstance(recs[0], OutcomeRecord)
    assert recs[0].enemy_hp_after is None and recs[0].killed is True
    assert load_outcomes(tmp_path / 'nope.jsonl') == []


def test_posture_tag_forms() -> None:
    """posture_tag 归一:现行 str tag / 历史 dict / 载体帧 str(dict) / 缺失。"""
    tag_long = "{'spend_mode': 'adaptive', 'target_level': 4}"   # 载体帧长串(实测 42-46 字符)
    cases = [
        # (strategy_id, dp_posture, 期望 tag)
        ('decision_v2', '升级+D6', '升级+D6'),       # 现行 str tag
        ('decision_v2', 'release', 'release'),
        ('decision_v2', {'spend_mode': 'adaptive', 'target_level': 4}, 'adaptive'),  # 历史 dict
        ('decision_v2', {'target_level': 4}, None),   # dict 缺 spend_mode 不猜
        ('decision_v2', '', None),                     # 空 tag
        ('decision_v2', tag_long, None),               # str(dict) 泄漏形态非 tag
        ('decision_v2', None, None),
        ('', '存息', None),                            # 载体帧恒 None
        ('', tag_long, None),
        ('', {'spend_mode': 'x'}, None),
        ('decision_v2', 42, None),                     # 非法形态不炸
    ]
    for sid, dp, expect in cases:
        assert posture_tag({'strategy_id': sid, 'dp_posture': dp}) == expect, (sid, dp)
    # typed 对象与裸 dict 同判
    assert posture_tag(DecisionTrace(strategy_id='decision_v2', dp_posture='存息')) == '存息'
    assert posture_tag(DecisionTrace(strategy_id='', dp_posture=tag_long)) is None
    # 历史帧缺 dp_posture 属性路径(dict 行缺键)
    assert posture_tag({'run_id': 'r'}) is None


def test_divergence_stats_on_typed_rows(tmp_path: _replay_reader_Path) -> None:
    """端到端:混合形态(现行 str/历史 dict/载体帧)下统计口径不变。"""
    rows = [
        {'run_id': 'r1', 'round_num': 1, 'strategy_id': 'decision_v2', 'dp_posture': 'release',
         'candidate_scores': {'a': 1.0, 'b': 0.95}},
        {'run_id': 'r1', 'round_num': 2, 'strategy_id': '',   # 载体帧:长串姿态不计入
         'dp_posture': str({'spend_mode': 'adaptive', 'target_level': 4})},
        {'run_id': 'r1', 'round_num': 3, 'strategy_id': 'decision_v2',
         'dp_posture': {'spend_mode': 'adaptive', 'target_level': 4}},   # 历史 dict 帧计 spend_mode
    ]
    _write(tmp_path / 'decisions.jsonl', rows)
    st = divergence_stats(tmp_path)
    assert st['with_dp_posture'] == 2
    assert st['dp_modes'] == {'release': 1, 'adaptive': 1}
    assert st['close_calls'] == 1 and st['per_run'] == {'r1': [1]}


def test_from_dict_is_write_side_single_source() -> None:
    """from_dict 产物即 cw_telemetry 写端类(单一源,非平行类)。"""

    from sr_od.application.currency_war.telemetry.schema import DecisionTrace as WT
    assert DecisionTrace is WT
    f = from_dict(DecisionTrace, {'run_id': 'r', 'not_a_field': 1})
    assert isinstance(f, WT) and f.run_id == 'r'


# ==================== w944b_planner_click_fix ====================

import inspect

from sr_od.application.currency_war.operations.cw_screen import _overlay_confirm
from sr_od.application.currency_war.operations.cw_screen.cw_screen_planner import (
    CwScreenPlanner,
)


def test_card_point_inside_updated_area_and_avoids_detail(test_context) -> None:
    """推导点位落在当前布局卡 rect 内、且相对避让生效(双卡)。

    避让断言用 rect 相对几何(底缘上移 DETAIL_MARGIN_RATIO),非绝对 y
    (W952 P2-1:绝对常数对多布局不成立——弹窗整体平移时相对断言仍成立)。
    """
    op = CwScreenPlanner(test_context)
    for idx in (0, 1):
        area = test_context.screen_loader.get_area(
            CwScreenPlanner.CARD_AREA_SCREEN,
            CwScreenPlanner.CARD_AREAS[idx])
        assert area is not None, f'卡 area 缺失:idx={idx}'
        rect = area.pc_rect
        p = op._card_point(idx)
        assert rect.x1 <= p.x <= rect.x2 and rect.y1 <= p.y <= rect.y2, (
            f'idx={idx} 点 ({p.x},{p.y}) 落在卡 rect {rect} 外(布局漂移复发形态)')
        detail_top = rect.y2 - int(rect.height * CwScreenPlanner.DETAIL_MARGIN_RATIO)
        assert p.y <= detail_top, (
            f'idx={idx} 点 y={p.y} 进入详情钮相对避让带(>={detail_top})')
        assert p.y >= rect.y1 + 60, f'idx={idx} 点过于靠卡顶(上半部点击=详情面板实证)'


def test_card_point_falls_back_to_legacy_safe_band(
    test_context, monkeypatch) -> None:
    """area 缺失 → 兜底点位=旧实证安全带(W952 P1-1 强断言,非平凡 in-rect)。

    旧实证安全点 (755/1225,480) ∈ [460,480];绝对 clamp 425 曾把兜底压到
    旧布局 51.8% 卡高——(755,400) 型详情危险带与安全点之间未验证带。
    """
    monkeypatch.setattr(test_context.screen_loader, 'get_area', lambda *a, **k: None)
    op = CwScreenPlanner(test_context)
    for idx in (0, 1):
        p = op._card_point(idx)
        lx, ly, rx, ry = CwScreenPlanner._LEGACY_CARD_RECTS[idx]
        assert lx <= p.x <= rx, f'idx={idx} x={p.x} 不在旧 rect 内'
        assert 460 <= p.y <= 480, (
            f'idx={idx} 兜底 y={p.y} 出旧实证安全带 [460,480](详情危险带发作形态)')


def test_press_time_hardening_wired() -> None:
    """加固接线(L1-1 改写,验证废除批):点卡/确认都走 0.15 按压;确认
    原语 = emit_overlay_confirm(原 confirm_and_verify 验关半拆除后更名,
    机械交回),默认 0.1(其它 handler 零影响)、press_time 透传保持——
    按压加固语义迁新确认原语后锁新原语,防加固线静默失守。"""
    src = inspect.getsource(CwScreenPlanner)
    assert 'press_time=self.CLICK_PRESS_TIME' in src, '点卡未带按压加固'
    assert 'press_time=self.CLICK_PRESS_TIME)' in inspect.getsource(
        CwScreenPlanner.handle) or 'press_time=self.CLICK_PRESS_TIME' in src
    assert 'press_time: float = 0.1' in inspect.getsource(_overlay_confirm), (
        'emit_overlay_confirm 默认值变了(会波及其它 handler)')
    assert 'press_time=press_time' in inspect.getsource(_overlay_confirm), (
        '确认点击未透传 press_time')


def test_match3_frame_regression_points(test_context) -> None:
    """match3 帧回归:旧硬编码点 (1225,480) 必须落在更新后的右卡 rect 外
    (锁 rect 更新本身——rect 回退旧值 = 本锁红)。"""
    area = test_context.screen_loader.get_area('货币战争-骇入策划', '骇入选项-右卡')
    assert area is not None
    rect = area.pc_rect
    assert not (rect.x1 <= 1225 <= rect.x2 and rect.y1 <= 480 <= rect.y2), (
        '右卡 rect 回退旧布局(y 280-560)——match3 点位漂移根因复发')


# ==================== synthesis_chain ====================

from sr_od.application.currency_war.data import cw_synthesis
from sr_od.application.currency_war.data.cw_synthesis import (
    plan_syntheses,
    synthesis_membership,
)

POOL = 'snapshot'


@pytest.fixture()
def _run_game():
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    return simulate_p1


class TestPlanSyntheses:
    """纯函数语义(配方数据源 = 注册表派生图谱,K8 闭合)。"""

    def test_cross_recipe_completes(self):
        # 火力风暴潮 = 轮滑鞋 + 折叠小刀(交叉配方,cw_synthesis docstring 例)
        actions = plan_syntheses(['火力风暴潮'], ['轮滑鞋', '折叠小刀'])
        # 配方组件序以注册表 recipes 原序为准(折叠小刀在前),断言随源
        assert actions == [('火力风暴潮', ('折叠小刀', '轮滑鞋'))]

    def test_self_recipe_needs_two_copies(self):
        # 反重力皮靴 = 轮滑鞋 ×2:库存 1 件不可合成(不能用「出现即有」判)
        assert plan_syntheses(['反重力皮靴'], ['轮滑鞋']) == []
        actions = plan_syntheses(['反重力皮靴'], ['轮滑鞋', '轮滑鞋'])
        assert actions == [('反重力皮靴', ('轮滑鞋', '轮滑鞋'))]

    def test_owned_advance_deducts_demand(self):
        # 已持有同名成品 1:1 抵扣需求,不再消耗组件
        assert plan_syntheses(
            ['火力风暴潮'], ['火力风暴潮', '轮滑鞋', '折叠小刀']) == []

    def test_multiplicity_fires_repeatedly(self):
        actions = plan_syntheses(
            ['反重力皮靴', '反重力皮靴'], ['轮滑鞋'] * 4)
        assert len(actions) == 2
        assert all(a == '反重力皮靴' for a, _c in actions)

    def test_non_recipe_key_skipped(self):
        # 白昼类无常规配方(component_demand 同口径)不产生可执行合成
        assert plan_syntheses(['白昼'], ['轮滑鞋', '折叠小刀']) == []

    def test_inputs_not_mutated(self):
        owned = ['轮滑鞋', '折叠小刀']
        plan_syntheses(['火力风暴潮'], owned)
        assert owned == ['轮滑鞋', '折叠小刀']


class TestSynthesisMembershipGate:
    """方向确定性门(用户裁决:乱合成=后期缺关键装备;P1 FORM 期换线
    压注禁合成)。隶属度:目标件 1.0 / 共享件 0.5 / 无关 0;默认阈值
    1.0 = 只合目标件。"""

    def test_target_item_membership_one(self):
        assert synthesis_membership('火力风暴潮', ['火力风暴潮']) == 1.0

    def test_shared_component_membership_half(self):
        # 轮滑鞋 ∈ 火力风暴潮需求向量 → 含轮滑鞋的其他进阶(反重力皮靴
        # = 轮滑鞋×2,不在 key)= 共享件 0.5
        assert synthesis_membership('反重力皮靴', ['火力风暴潮']) == 0.5

    def test_unrelated_membership_zero(self):
        # 永动机 = 光能电池×2,与 火力风暴潮(轮滑鞋+折叠小刀)无交
        assert synthesis_membership('永动机', ['火力风暴潮']) == 0.0

    def test_no_direction_no_synthesis(self):
        # 无方向(key 空)→ 恒 0:不存在无方向合成路径
        assert synthesis_membership('火力风暴潮', []) == 0.0
        assert plan_syntheses([], ['轮滑鞋', '折叠小刀']) == []

    def test_default_floor_blocks_shared_item(self):
        # 默认阈值 1.0:候选扩扫中的共享件(0.5)被门拦下
        actions = plan_syntheses(
            ['火力风暴潮'], ['轮滑鞋'] * 2,
            candidates=['反重力皮靴'])
        assert all(a == '火力风暴潮' for a, _c in actions)
        # 显式降阈值 → 共享件可合(显式放宽,非默认)
        actions = plan_syntheses(
            ['火力风暴潮'], ['轮滑鞋'] * 4,
            membership_floor=0.5, candidates=['反重力皮靴'])
        assert any(a == '反重力皮靴' for a, _c in actions)

    def test_gate_fires_only_under_locked_intention(self, monkeypatch,
                                                    _run_game):
        # 变异法:patch plan_syntheses 恒产 1 件成品(hook 只要被调用就
        # 会留痕),断言台账中「有合成事件的轮」全部满足意向已锁线
        # (phase=='locked'∧locked_comp)——锁线门在位且无旁路。
        # seed 窗扫描:组件入穿戴池(ADR-0265 增补)漂移了 owned 消费
        # → 单 seed 的锁线时点不稳定,单 seed 探针 fragile;锁语义是
        # 「点火轮必锁线」,不是「seed N 必点火」,故扫窗找点火 seed。
        monkeypatch.setattr(
            cw_synthesis, 'plan_syntheses',
            lambda keys, owned: [('反重力皮靴', ())] if owned else [])
        hit = None
        for seed in range(20):
            r = _run_game(seed, pool=POOL, planes=2, synthesis_chain=True)
            rows = [row for row in r.ledger if row['sim'].get('syntheses')]
            if rows:
                hit = rows
                break
        assert hit, 'seed 窗 0-19 无合成事件:门过严或发放面异常,复查'
        for row in hit:
            ist = row.get('v3_intention') or {}
            assert ist.get('phase') == 'locked' and ist.get('locked_comp')


class TestWearBasicP1:
    """P1 简易件默认穿(ADR-0265 增补:穿戴可逆——用户裁决「卖角色
    全额返还装备」,原保留过滤前提消失;旧 allow_basic_wear 旁路随
    过滤一并删除,旁路语义升为默认)。"""

    def test_default_wears_basic_p1(self):
        from sr_od.application.currency_war.kernel.cw_comps import equip_allocation
        from sr_od.application.currency_war.kernel.cw_vocab import BenchChar
        dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
        owned = ['轮滑鞋', '光能电池', '蓄能帆']
        alloc = equip_allocation(None, dep, owned)
        worn = {e for _w, e in alloc}
        # 配对守卫(ADR-0391)仍拦危险配对:轮滑鞋+光能电池互为配方,
        # comp=None 无豁免信息 → 只放第一件(默认穿不放松守卫)
        assert '轮滑鞋' in worn and '蓄能帆' in worn, f'得 {alloc}'
        assert '光能电池' not in worn, '配对守卫应拦第二件基础件'


class TestSimSynthesisHook:
    """cw_sim 合成执行 hook(synthesis_chain=True 点火;默认关零漂移)。"""

    def test_hook_fires_and_advance_enters_pool(self, monkeypatch, _run_game):
        # 变异法证明 hook 在位:patch plan_syntheses 恒产 1 件成品,
        # 断言 ①台账 syntheses 行出现;②成品进池(被穿或留 owned)。
        # 成品选反重力皮靴(进阶,非 RESERVED_COMPONENTS)。seed 窗
        # 扫描(组件入穿戴池后 owned 消费漂移,单 seed 探针 fragile;
        # 锁语义=「hook 在位、成品进池」,不是「seed N 必点火」)。
        fired: list[int] = []

        def fake(keys, owned):
            if owned and '反重力皮靴' not in owned:
                fired.append(1)
                return [('反重力皮靴', ())]
            return []

        monkeypatch.setattr(cw_synthesis, 'plan_syntheses', fake)
        ledger = None
        for seed in range(20):
            r = _run_game(seed, pool=POOL, planes=2, synthesis_chain=True)
            if any(row['sim'].get('syntheses') for row in r.ledger):
                ledger = r.ledger
                break
        assert fired, 'hook 未被调用(st.equips 恒空?seed 窗无发放,复查)'
        assert ledger is not None
        have = {e for row in ledger
                for d in row['state']['deployed']
                for e in d.get('equips', [])}
        have |= set(ledger[-1]['state']['owned_equips'])
        assert '反重力皮靴' in have

    def test_chain_on_without_actions_zero_drift(self, monkeypatch, _run_game):
        # 开关开启但无可执行合成(恒返回空)→ 与默认关逐位一致
        # (零漂移锚:差异只能来自合成事件本身)。
        monkeypatch.setattr(cw_synthesis, 'plan_syntheses', lambda k, o: [])
        on = _run_game(4, pool=POOL, planes=2, synthesis_chain=True)
        off = _run_game(4, pool=POOL, planes=2)
        assert on.final_hp == off.final_hp
        assert on.hp_trail == off.hp_trail

    def test_default_off_no_synthesis_rows(self, _run_game):
        r = _run_game(0, pool=POOL, planes=1)
        assert all(not row['sim'].get('syntheses') for row in r.ledger)
