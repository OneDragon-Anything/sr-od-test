"""遥测根装配槽锁(T-120 批 1;F4 落盘根槽 + T-129/T-130 journal 根槽
+ 决策帧落盘根槽[三审二波 F2 修复])。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/
方案.md``,**易失产物**)§4-2「落盘根装配槽」+ §2.5/§7.1 telemetry/
state.py 行(F4 方案审修正);journal 根槽 = T-129 严查报告「sim 与
live 共写同一 journal 文件的 run_id 过滤设计」注记的批 1 承接(T-130
任务行④),机制裁决 = 写端根隔离(见 op_journal.set_journal_dir 注)。
决策帧根槽 = 三审报告·第二波(``.debug/temp/currency_war/attacks/
three_review_20260908/三审报告-第二波.md`` F2,**易失产物**待 ADR 回填)
——决策帧原为无槽第三写根,假环境观察 JSON 恒落生产 decision_frames
树,仅靠 harness monkeypatch 私函数 ``_out_dir`` 兜住;不经 harness 的
假局驱动方(易失离线 runner/未来 sim 批真 op 驱动)会静默混流。与
op_journal.py「两根恒一致」旧注释声明对三根现实不符同案修复。
ADR 落点待分配,后续批回填编号。

锁的语义:

- **缺省 None = 生产路径**(方案 §3.2 装配纪律的槽版):三槽缺省时
  recorder 根 = kernel/cw_observe.DEFAULT_REPLAY_DIR、journal 路径 =
  模块常量(其 parent = LIVE_DIR,既有根布局锁 test_cw_infra_locks
  同判)、决策帧目录 = 生产公式(get_project_root 活读)。红 = 生产
  缺省路径被槽改动劫持。
- **接通/复位语义**:接指新根后 recorder 重建(内存累积按根隔离)、
  journal 现算路径改指、决策帧目录改指;复位后三根回生产缺省。红 =
  槽半程(改根不重建/复位失灵)。
- **写端隔离实证**:journal 槽接指 tmp 根时,op 行落 tmp 根;决策帧
  槽接指 tmp 根时,假环境观察证据 JSON 落 tmp 根——「假局遥测行不进
  生产树」的机器可判形(不读真实 .debug 根,纪律 19;生产侧由既有根
  布局锁与槽缺省锁合辖)。
- **拒写守卫**(决策帧槽专属):假环境(观察源在场)+ 槽未接 = 拒写
  返回 None,连生产树目录也不建——F2 风险本体「静默混流」的机器可判
  反面(宁缺勿混:证据缺失可发现,混流不可发现)。
- **生产树零设槽点扫描**(三槽共用):src 树内三槽接通入口只允许出现在
  各自定义文件(def 行自带调用形括号)——槽是测试/回放基础设施,生产
  任何一处接通 = 生产行为改面,红时登记该接通的合法性(生产确要改根 →
  走 ADR + 允许集同批改)。合法源码扫描(纪律 8② 依赖方向守卫;盲区
  自检 = 合成树负测试,纪律 20)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war import cw_game_ports
from sr_od.application.currency_war.kernel.cw_observe import (
    DEFAULT_REPLAY_DIR,
    LIVE_DIR,
)
from sr_od.application.currency_war.operations import decision_frame_hooks as dfh
from sr_od.application.currency_war.telemetry import op_journal
from sr_od.application.currency_war.telemetry import state as tel_state


@pytest.fixture(autouse=True)
def _slots_isolated():
    """三槽都是进程全局态——teardown 强制复位(测试纪律 4:隔离整条
    副作用链;残留会把后续测试的遥测写去假局根/继续改指 tmp)。"""
    yield
    tel_state.set_recorder_replay_dir(None)
    op_journal.set_journal_dir(None)
    dfh.set_decision_frame_dir(None)


class TestRecorderRootSlot:
    """recorder 落盘根槽(F4;install_obs_ports 槽模式的遥测侧同构)。"""

    def test_default_none_keeps_production_root(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """缺省 None = 生产路径:get_recorder 惰性构造指向缺省根
        (DEFAULT_REPLAY_DIR = telemetry/live)。"""
        monkeypatch.setattr(tel_state, '_RECORDER', None)   # 不触真实单例
        tel_state.set_recorder_replay_dir(None)
        assert tel_state.get_recorder().replay_dir == DEFAULT_REPLAY_DIR

    def test_slot_redirects_and_rebuilds_singleton(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """接通新根 → 单例按新根重建(内存累积随根隔离,不复用旧实例);
        复位 → 回生产缺省。"""
        monkeypatch.setattr(tel_state, '_RECORDER', None)
        tel_state.set_recorder_replay_dir(tmp_path)
        rec = tel_state.get_recorder()
        assert rec.replay_dir == tmp_path
        # 重建语义:换根后 get_recorder 不得返回旧根实例
        other = tmp_path / 'other'
        tel_state.set_recorder_replay_dir(other)
        rec2 = tel_state.get_recorder()
        assert rec2 is not rec and rec2.replay_dir == other

    def test_reset_returns_to_production_root(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(tel_state, '_RECORDER', None)
        tel_state.set_recorder_replay_dir(tmp_path)
        tel_state.set_recorder_replay_dir(None)
        assert tel_state.get_recorder().replay_dir == DEFAULT_REPLAY_DIR


class TestJournalRootSlot:
    """journal 根槽(T-129/T-130 混流注记落地;写端根隔离机制)。"""

    def test_default_none_keeps_production_path(self) -> None:
        """缺省 = 模块常量缝(_JOURNAL,既有测试的落盘重定向缝保持
        活读;其 parent = LIVE_DIR 与根布局锁同判)。"""
        op_journal.set_journal_dir(None)
        assert op_journal._journal_path() is op_journal._JOURNAL
        assert op_journal._JOURNAL.parent == LIVE_DIR

    def test_slot_redirects_write_side(self, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        """接指 tmp 根 → op 行落 tmp 根(写端隔离实证;run_id 键不变,
        读端过滤能力不受影响的载体)。"""
        op_journal.set_journal_dir(tmp_path)
        monkeypatch.setattr(op_journal, 'current_run_id',
                            lambda: 'run_jslot')
        token = op_journal.record_op_enter('货币战争-测试op', 1, 1,
                                           obs={'probe': True})
        assert token is not None
        out = tmp_path / 'op_journal.jsonl'
        assert out.exists(), 'journal 行未落接通的根槽'
        import json
        row = json.loads(out.read_text(encoding='utf-8').splitlines()[0])
        assert row['run_id'] == 'run_jslot'
        assert row['kind'] == 'op' and row['event'] == 'enter'

    def test_reset_falls_back_to_constant_seam(self, tmp_path: Path) -> None:
        """复位后回落常量缝:monkeypatch ``_JOURNAL`` 的既有重定向手法
        (test_cw_op_journal/test_cw_dispatch_wrapper 同款)在槽复位态
        下继续生效——两缝叠加不互相遮蔽。"""
        op_journal.set_journal_dir(tmp_path / 'a')
        op_journal.set_journal_dir(None)
        assert op_journal._journal_path() is op_journal._JOURNAL

    def test_exit_row_via_slot_pairing(self, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        """enter/exit 成对行经槽落同一根(token 配对语义不受改根影响)。"""
        op_journal.set_journal_dir(tmp_path)
        monkeypatch.setattr(op_journal, 'current_run_id',
                            lambda: 'run_jpair')
        token = op_journal.record_op_enter('货币战争-测试op', 1, 2)
        op_journal.record_op_exit(token, outcome='ok', detail='收工')
        lines = (tmp_path / 'op_journal.jsonl').read_text(
            encoding='utf-8').splitlines()
        assert len(lines) == 2
        events = [json.loads(x)['event'] for x in lines]
        assert events == ['enter', 'exit']


class _FakeSource:
    """带 evidence_snapshot 的假观察源(save_decision_frame JSON 分支
    的最小实现;真实现 = fixtures/cw_fake_game.fake_ports.FakeCwObserver,
    此处只锁落盘根归属,不复刻其载荷语义)。"""

    def evidence_snapshot(self, tag: str) -> dict[str, str]:
        return {'probe': tag}


class _NoShotOp:
    """空壳宿主 op:JSON 分支不触 screenshot——fn 非 None 即证明走的是
    观察证据分支而非 PNG 兜底(PNG 兜底 screenshot None 会返回 None)。"""

    def screenshot(self) -> None:
        return None


class TestDecisionFrameRootSlot:
    """决策帧落盘根槽(三审二波 F2 修复;写端根隔离的第三根)。"""

    def test_default_none_keeps_production_formula(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """缺省 None = 生产路径:_out_dir 活读 get_project_root 逐位保留
        (既有 test_cw_decision_frame_hooks 的 get_project_root 缝不失效,
        journal 槽回落 _JOURNAL 常量缝同款纪律)。红 = 生产公式被槽改动
        劫持。断言只算路径不落盘。"""
        monkeypatch.setattr(dfh, 'get_project_root', lambda: tmp_path)
        dfh.set_decision_frame_dir(None)
        assert dfh._out_dir('run_x') == (tmp_path / '.debug' / 'temp'
                                         / 'currency_war' / 'decision_frames'
                                         / 'run_x')

    def test_slot_redirects_and_isolates_write_side(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """写端隔离实证:槽接指 tmp 档案根后,假环境观察证据 JSON 落
        ``<根>/decision_frames/<run_id>/``;生产公式根零痕迹(把
        get_project_root 改指隔离区,槽若失效证据必落隔离区——隔离
        断言由此生效,不触真实 .debug,纪律 19)。红 = 槽半程(路径改
        指但写点仍落生产公式)或观察证据静默混流(F2 本体)。"""
        prod_root = tmp_path / 'prod_root'
        monkeypatch.setattr(dfh, 'get_project_root', lambda: prod_root)
        monkeypatch.setattr(tel_state, 'current_run_id',
                            lambda: 'run_dslot')
        monkeypatch.setattr(cw_game_ports, 'observation_source',
                            lambda: _FakeSource())
        archive = tmp_path / 'archive'
        dfh.set_decision_frame_dir(archive)
        fn = dfh.save_decision_frame(_NoShotOp(), 'probe_tag')
        assert fn is not None and fn.endswith('.json')
        landed = archive / 'decision_frames' / 'run_dslot' / fn
        assert landed.is_file(), '观察证据未落接通的根槽'
        payload = json.loads(landed.read_text(encoding='utf-8'))
        assert payload['kind'] == 'observation_evidence'
        assert payload['run_id'] == 'run_dslot'
        # 隔离面:生产公式根连 .debug 目录都不得存在(目录=写痕迹,
        # 守卫判定位次先于 mkdir 的载体)
        assert not (prod_root / '.debug').exists()

    def test_reset_falls_back_to_production_formula(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """复位后回落生产公式活读缝:get_project_root 缝与根槽叠加不
        互相遮蔽(journal 两缝叠加测试同构)。"""
        monkeypatch.setattr(dfh, 'get_project_root', lambda: tmp_path)
        dfh.set_decision_frame_dir(tmp_path / 'a')
        dfh.set_decision_frame_dir(None)
        assert dfh._out_dir('run_r') == (tmp_path / '.debug' / 'temp'
                                         / 'currency_war' / 'decision_frames'
                                         / 'run_r')

    def test_fake_env_without_slot_refuses_write(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """拒写守卫:假环境(观察源在场)+ 槽未接 = 返回 None 且生产
        公式根零目录(宁缺勿混——证据缺失可发现,静默混流不可发现;
        F2 风险本体的机器可判反面)。红 = 守卫脱落,证据静默落生产树。"""
        prod_root = tmp_path / 'prod_root'
        monkeypatch.setattr(dfh, 'get_project_root', lambda: prod_root)
        monkeypatch.setattr(tel_state, 'current_run_id',
                            lambda: 'run_guard')
        monkeypatch.setattr(cw_game_ports, 'observation_source',
                            lambda: _FakeSource())
        dfh.set_decision_frame_dir(None)
        fn = dfh.save_decision_frame(_NoShotOp(), 'probe_tag')
        assert fn is None, '未接槽的假环境观察证据被写出(混流)'
        assert not (prod_root / '.debug').exists(), '拒写时生产树被建目录'


# ===== 生产树零设槽点扫描(装配纪律守卫;三槽共用)=====

#: 三槽接通入口 → 唯一合法定义文件(相对 src/sr_od;def 行自带调用形
#: 括号,故允许集 = 定义文件本身)。针脚 = 调用形(名+左括号):
#: op_journal 三根注 / state.py 边界注等 docstring 与注释的符号提名
#: 不带左括号,实扫不误伤(负例由真实树断言本身承载)。
_SLOT_SETTERS: dict[str, str] = {
    'set_recorder_replay_dir(':
        'application/currency_war/telemetry/state.py',
    'set_journal_dir(':
        'application/currency_war/telemetry/op_journal.py',
    'set_decision_frame_dir(':
        'application/currency_war/operations/decision_frame_hooks.py',
}


def _scan_slot_setters(root: Path) -> dict[str, list[str]]:
    """单遍扫 root 下全部 .py(跳 __pycache__),返回 针脚 → 命中文件尾径
    (排序保断言确定性;不可解码文件跳过,与 test_cw_game_ports 扫描同款)。"""
    hits: dict[str, set[str]] = {k: set() for k in _SLOT_SETTERS}
    for p in sorted(root.rglob('*.py')):
        if '__pycache__' in p.parts:
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        rel = p.relative_to(root).as_posix()
        for needle in _SLOT_SETTERS:
            if needle in text:
                hits[needle].add(rel)
    return {k: sorted(v) for k, v in hits.items()}


class TestZeroProductionWiring:
    """生产树零设槽点守卫(零生产行为变更的机器可判形)。

    槽是测试/回放基础设施:生产代码任何一处接通(哪怕注释写「临时」)
    = 生产行为改面,红。红时登记的语义 = 该调用点的接通合法性——生产
    确实要改根 → 走 ADR 申报 + 本允许集同批改;测试/harness 接线不在
    扫描域(src 树),不受影响。合法源码扫描(测试纪律 8② 依赖方向/
    单一源守卫;盲区自检 = 合成树负测试,测试纪律 20)。
    """

    @staticmethod
    def _src_root() -> Path:
        # decision_frame_hooks.py 位于 src/sr_od 下第 5 层
        # (src/sr_od/application/currency_war/operations/)⇒ parents[5]
        # = 仓根。全 sr_od 域扫描:槽接通落错包也能被起诉(禁假绿)。
        return Path(dfh.__file__).resolve().parents[5] / 'src' / 'sr_od'

    def test_no_production_slot_wiring(self) -> None:
        """生产树设槽点 = 三定义文件各自唯一(多/少/错位皆红)。"""
        hits = _scan_slot_setters(self._src_root())
        for needle, allowed in _SLOT_SETTERS.items():
            assert hits[needle] == [allowed], (
                f'{needle} 生产树接线越出定义文件: {hits[needle]}')

    def test_scanner_catches_synthetic_wiring(self, tmp_path: Path) -> None:
        """盲区自检:合成树上生产文件接通槽必须被起诉,纯 import 不算
        接线(禁假绿,测试纪律 20)。"""
        pkg = tmp_path / 'pkg'
        pkg.mkdir()
        (pkg / 'clean.py').write_text(
            'from sr_od.application.currency_war.operations import '
            'decision_frame_hooks\n', encoding='utf-8')
        guilty = pkg / 'app_boot.py'
        guilty.write_text(
            'def boot(root) -> None:\n'
            '    decision_frame_hooks.set_decision_frame_dir(root)\n',
            encoding='utf-8')
        hits = _scan_slot_setters(tmp_path)
        assert hits['set_decision_frame_dir('] == ['pkg/app_boot.py'], hits
        assert hits['set_journal_dir('] == []
        assert hits['set_recorder_replay_dir('] == []
