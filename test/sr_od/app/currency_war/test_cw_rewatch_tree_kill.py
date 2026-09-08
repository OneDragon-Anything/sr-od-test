"""哨兵树终杀与杀后复扫断言锁(tools/cw/rewatch.py + cycle_restart 消费点)。

出处 = ADR-0602(docs/develop/currency_war/decisions/,树终杀+杀后复扫
断言+cycle_restart 两消费点收口的决策 why)。病灶 = 2026-09-08 实录:手工
Stop-Process 单点杀哨兵,Windows 不级联,pwsh 包装死后 uv→venv python
链照常存活——孤儿占 runs_gap 锁拒新实例武装+报警链断成哑哨兵。
裁决形态:①杀净补杀后复扫断言(复扫非空自动再杀,有界重试,仍非空
exit 2)——把「杀净」变成可验证出口;②树语义防御纵深(psutil
children(recursive=True) 收编后代,单机制,不引 taskkill/CIM 第二套);
③cycle_restart 两处单点 terminate 消费点复用同一树杀实现。

三行为锁(ADR-0602 §5 验收设计逐条):
  ① 树递归:匹配进程的后代(命令行不含脚本名)被收进杀集;
  ② 杀后复扫:复扫才抓得到的漏网哨兵被自动再杀(凭据=其 kill 调用数
    超过单轮上限 2);有界重试后仍非空 → exit 2;
  ③ --selftest 路径零杀。
附加:kill_pids_tree 复用缝语义 + 消费点源码锁(terminate() 绝迹 /
杀语义单一源在 rewatch / cycle_restart 不自引 psutil)。

零真实进程:psutil 以桩命名空间整体替换(mod.psutil,查旧/树遍历/宽限
等待全走桩表;异常类借用真 psutil,保证 contextlib.suppress 与桩抛错
同类);零真实 .debug 写(verify 落状态文件路径不在本锁面)。毫秒级,
不入慢桶。
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psutil
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_REWATCH_PATH = _REPO_ROOT / 'tools' / 'cw' / 'rewatch.py'
_CYCLE_PATH = _REPO_ROOT / 'tools' / 'cw' / 'cycle_restart.py'
_REWATCH_MOD = 'cw_rewatch_tool_under_lock'
_CYCLE_MOD = 'cw_cycle_restart_tool_under_lock'

#: 单轮杀的 kill() 调用上限(kill→宽限确认→强杀)= 2。被杀对象的 kill
#: 调用数超过它 = 存在第二轮杀 = 「复扫非空再杀」已发生的计数凭据
#: (不锁具体次数,只锁「超过单轮上限」)
_SINGLE_ROUND_KILL_CAP = 2


def _load(path: Path, name: str) -> Any:
    """按路径装载被测工具(sys.modules 缓存,跨用例只 exec 一次;
    先例 = test_cw_migrate_lineage._load_tool)。"""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _FakeProc:
    """伪进程:树/命令行/存活全由构造给定。

    survive_kills = 档壳数:每被 kill() 一次消耗一档,耗尽才置 dead;
    deny_kill=True 时 kill() 改抛 psutil.AccessDenied(永不置 dead)。
    ⚠️ 档壳是「杀→复扫」循环的**机制锁,非 Windows 杀语义的真实映射**:
    TerminateProcess 原子(死或抛),「多挨几发才死」的现实对应物 =
    复扫轮抓到首轮与杀之间新出现的实例;真实可达的「杀不动」模式
    (需管理员抛 AccessDenied)由 deny_kill 桩建模。桩杀恒即时(无宽限
    时钟),单轮打 2 发(kill+强杀),要活过 1 轮、死于下一轮给 2 档。
    kill_calls 留痕,作「走了第二轮」的计数凭据。
    """

    def __init__(self, pid: int, cmdline: list[str],
                 children: list[_FakeProc] | None = None,
                 survive_kills: int = 0,
                 deny_kill: bool = False) -> None:
        self.pid = pid
        self._cmdline = cmdline
        self._children: list[_FakeProc] = children or []
        self.survive_kills = survive_kills
        self.deny_kill = deny_kill
        self.kill_calls = 0
        self.alive = True

    def cmdline(self) -> list[str]:
        return list(self._cmdline)

    def name(self) -> str:
        return 'python.exe'

    def children(self, recursive: bool = False) -> list[_FakeProc]:
        """仿 psutil.children:目标已死抛 NoSuchProcess(真库同形);
        recursive=True 返回全部后代(先序)。"""
        if not self.alive:
            raise psutil.NoSuchProcess(self.pid)
        if not recursive:
            return list(self._children)
        out: list[_FakeProc] = []
        for child in self._children:
            out.append(child)
            out.extend(child.children(recursive=True))
        return out

    def kill(self) -> None:
        self.kill_calls += 1
        if self.deny_kill:
            raise psutil.AccessDenied(self.pid)
        if self.survive_kills > 0:
            self.survive_kills -= 1
            return
        self.alive = False


class _PsutilStub:
    """psutil 桩命名空间:查旧/树遍历/宽限等待全走桩表。

    桩表只含存活成员对 process_iter 可见(仿真库快照语义);异常类借用
    真 psutil——rewatch 的 contextlib.suppress 写的是 psutil.NoSuchProcess
    等真类,桩抛错必须同类才压得住。
    """

    NoSuchProcess = psutil.NoSuchProcess
    AccessDenied = psutil.AccessDenied
    ZombieProcess = psutil.ZombieProcess

    def __init__(self, table: list[_FakeProc]) -> None:
        self._table = table

    def process_iter(self) -> Iterator[_FakeProc]:
        return iter([p for p in self._table if p.alive])

    def Process(self, pid: int) -> _FakeProc:
        for proc in self._table:
            if proc.pid == pid:
                if not proc.alive:
                    raise psutil.NoSuchProcess(pid)
                return proc
        raise psutil.NoSuchProcess(pid)

    @staticmethod
    def wait_procs(procs: list[Any], timeout: float | None = None,
                   ) -> tuple[list[Any], list[Any]]:
        """桩杀即时收敛:按 alive 一刀切分(已死 / 仍活),不耗真实时钟。"""
        gone = [p for p in procs if not p.alive]
        alive = [p for p in procs if p.alive]
        return gone, alive


def _script_cmd(script: str) -> str:
    """哨兵武装命令行尾段(口径 = runtime-ops:uv run python <脚本>)。"""
    return f'C:/repo/skills/sr-od-currency-war-dev/scripts/{script}'


# ---- 行为①:树递归 ------------------------------------------------------


def test_tree_recursion_collects_unnamed_descendants(monkeypatch) -> None:
    """树递归:匹配链的后代中命令行不含任何哨兵脚本名的成员,仍被
    collect_tree 收进杀集;kill_all 端到端全链死亡。

    防御对象 = 未来拓扑漂移:今天四层(pwsh→uv→venv python→base python)
    命令行都含脚本名、命令行匹配够用,明天 uv 改实现未必——无名后代
    只能靠树语义抓。"""
    mod = _load(_REWATCH_PATH, _REWATCH_MOD)
    worker = _FakeProc(103, ['C:/Python311/python.exe', '-c', 'import worker'])
    leaf = _FakeProc(102, ['C:/Python311/python.exe', '-B', _script_cmd('cw_sentinel.py')],
                     children=[worker])
    uv = _FakeProc(101, ['C:/Tools/uv.exe', 'run', 'python', _script_cmd('cw_sentinel.py')],
                   children=[leaf])
    pwsh = _FakeProc(100, ['pwsh.exe', '-c', f'uv run python {_script_cmd("cw_sentinel.py")}'],
                     children=[uv])
    table = [pwsh, uv, leaf, worker]
    monkeypatch.setattr(mod, 'psutil', _PsutilStub(table))

    collected = {p.pid for p in mod.collect_tree([pwsh])}
    assert {100, 101, 102, 103} <= collected, '不含脚本名的链内后代没进杀集'

    mod.kill_all([pwsh])
    assert all(not p.alive for p in table), '树终杀后链上仍有存活'
    assert worker.kill_calls >= 1, '无名后代未被杀(树语义失效)'


# ---- 行为②:杀后复扫 ----------------------------------------------------


def test_rescan_catches_straggler_and_kills_again(monkeypatch, capsys) -> None:
    """复扫非空走第二轮杀:杀净入参只含 target,漏网哨兵 straggler
    只有复扫能抓到——终态全死、straggler 的 kill 调用数超过单轮上限、
    输出带「复扫零残留」契约行(ADR-0602 §5 实弹验收判据 = 该行出现)。
    档壳=通道机制锁非 Windows 杀语义映射(见 _FakeProc);现实对应形态
    = 首轮扫描与杀之间新出现的实例。"""
    mod = _load(_REWATCH_PATH, _REWATCH_MOD)
    target = _FakeProc(210, ['pwsh.exe', '-c', f'uv run python {_script_cmd("cw_sentinel.py")}'])
    # 2 档壳:round2 的 2 发杀不穿、round3 首发即死(KILL_RESCAN_MAX=3 内收敛)
    straggler = _FakeProc(211, ['pwsh.exe', '-c', f'uv run python {_script_cmd("cw_runs_gap.py")}'],
                          survive_kills=2)
    monkeypatch.setattr(mod, 'psutil', _PsutilStub([target, straggler]))

    mod.kill_all([target])   # 不抛 SystemExit = 有界重试内杀净
    assert not target.alive
    assert not straggler.alive, '复扫抓到的漏网哨兵未被再杀(复扫断言失效)'
    assert straggler.kill_calls > _SINGLE_ROUND_KILL_CAP, (
        f'未走第二轮杀(straggler kill 调用 {straggler.kill_calls} '
        f'≤ 单轮上限 {_SINGLE_ROUND_KILL_CAP})')
    assert '复扫零残留' in capsys.readouterr().out, (
        '缺杀净可验证出口契约行「复扫零残留」(编排者按此行判停净)')


def test_rescan_still_nonempty_exits_2(monkeypatch, capsys) -> None:
    """杀不掉的哨兵经 KILL_RESCAN_MAX 轮杀+复扫后仍在岗 → exit 2:
    「杀净」从尽力而为变成可验证失败——人忘了核的形态,命令报红。
    (桩侧 kill 不抛异常只不死,是循环机制锁;真实可达的杀不动模式
    = AccessDenied 抛异常,由下一测试单独锁。)"""
    mod = _load(_REWATCH_PATH, _REWATCH_MOD)
    zombie = _FakeProc(300, ['pwsh.exe', '-c', f'uv run python {_script_cmd("cw_sentinel.py")}'],
                       survive_kills=10**9)
    monkeypatch.setattr(mod, 'psutil', _PsutilStub([zombie]))

    with pytest.raises(SystemExit) as exc_info:
        mod.kill_all([zombie])
    assert exc_info.value.code == 2, f'杀净失败退出码应为 2,实为 {exc_info.value.code}'
    assert zombie.alive
    out = capsys.readouterr().out
    assert '复扫' in out and '失败' in out, '失败输出未点名复扫语义'


def test_access_denied_routes_to_exit_2_contract(monkeypatch, capsys) -> None:
    """AccessDenied(需管理员,Windows 上真实可达的杀不动模式)归 exit 2
    契约:kill 抛 AccessDenied 被抑制 → 视作存活 → 复扫轮有界重试 →
    轮数耗尽 exit 2;不得变成未处理异常(traceback 退 1,契约外退出码,
    消费方拿到不可判读的失败)。"""
    mod = _load(_REWATCH_PATH, _REWATCH_MOD)
    denied = _FakeProc(310, ['pwsh.exe', '-c', f'uv run python {_script_cmd("cw_sentinel.py")}'],
                       deny_kill=True)
    monkeypatch.setattr(mod, 'psutil', _PsutilStub([denied]))

    with pytest.raises(SystemExit) as exc_info:
        mod.kill_all([denied])
    assert exc_info.value.code == 2, f'杀净失败退出码应为 2,实为 {exc_info.value.code}'
    assert denied.alive and denied.kill_calls > 0, 'AccessDenied 未被抑制(异常逃逸出 kill_all)'
    out = capsys.readouterr().out
    assert '复扫' in out and '失败' in out, '失败输出未点名复扫语义'


# ---- 行为③:--selftest 零杀 ---------------------------------------------


def test_selftest_kills_nothing(monkeypatch, capsys) -> None:
    """--selftest 干跑路径零杀:查旧+列计划即止,不杀不起不写状态
    (零真实 .debug 写;argv 经 monkeypatch 注入,工具自 parse)。"""
    mod = _load(_REWATCH_PATH, _REWATCH_MOD)
    chain_top = _FakeProc(400, ['pwsh.exe', '-c', f'uv run python {_script_cmd("cw_sentinel.py")}'])
    monkeypatch.setattr(mod, 'psutil', _PsutilStub([chain_top]))
    monkeypatch.setattr(sys, 'argv', ['rewatch.py', '--selftest'])

    mod.main()
    assert chain_top.kill_calls == 0 and chain_top.alive, '--selftest 路径发生了杀'
    assert '[干跑]' in capsys.readouterr().out


# ---- 复用缝与消费点 -----------------------------------------------------


def test_kill_pids_tree_reuse_seam(monkeypatch) -> None:
    """kill_pids_tree 复用缝语义:按 pid 树终杀(目标+无名后代一并),
    返回杀后仍存活的杀集 pid;目标已死时幂等返回空(cycle_restart
    supervise 兄弟终止 / start_app 失败回滚两消费点共用本实现)。"""
    mod = _load(_REWATCH_PATH, _REWATCH_MOD)
    worker = _FakeProc(403, ['C:/Python311/python.exe', '-c', 'import worker'])
    leaf = _FakeProc(402, ['C:/Python311/python.exe', '-B', _script_cmd('cw_early_stop.py')],
                     children=[worker])
    uv = _FakeProc(401, ['C:/Tools/uv.exe', 'run', 'python', _script_cmd('cw_early_stop.py')],
                   children=[leaf])
    kid = _FakeProc(400, ['pwsh.exe', '-c', f'uv run python {_script_cmd("cw_early_stop.py")}'],
                    children=[uv])
    table = [kid, uv, leaf, worker]
    monkeypatch.setattr(mod, 'psutil', _PsutilStub(table))

    assert mod.kill_pids_tree([kid.pid]) == [], '目标链有成员未被杀净'
    assert all(not p.alive for p in table)
    assert worker.kill_calls >= 1, '无名后代未被杀(复用缝树语义失效)'
    assert mod.kill_pids_tree([kid.pid]) == [], '目标已死后再次调用应幂等'


def test_cycle_restart_consumes_rewatch_tree_kill() -> None:
    """消费点源码锁(ADR-0602 §3 两处单点杀):supervise 兄弟终止与
    start_app 失败回滚都必须复用 rewatch.kill_pids_tree——
    ①rw.kill_pids_tree 恰两处;②Popen.terminate() 绝迹(Windows 不级联,
    只杀 uv 层会孤儿化 venv python 链);③不自 import psutil(树机制
    单源在 rewatch,禁消费点第二套实现)。"""
    src = _CYCLE_PATH.read_text(encoding='utf-8')
    assert src.count('rw.kill_pids_tree(') == 2, (
        'kill_pids_tree 消费点应恰两处(supervise + start_app 回滚)')
    assert '.terminate()' not in src, '单点 terminate 回流(孤儿化 venv python 链)'
    assert 'import psutil' not in src, 'cycle_restart 自引 psutil(树杀第二实现)'


def test_supervise_terminates_siblings_via_tree_kill(monkeypatch) -> None:
    """supervise() 消费点行为锁:首个哨兵退出后,兄弟经 rewatch 树杀缝
    终止(收兄弟 pid,而非单点 terminate),首个退出者的退出码透传。
    伪 Popen + 桩 _rewatch,零真实子进程;time.sleep 桩掉使看守轮询
    即刻收敛(monkeypatch 自动还原)。"""
    cyc = _load(_CYCLE_PATH, _CYCLE_MOD)
    rw_mod = _load(_REWATCH_PATH, _REWATCH_MOD)
    killed_pids: list[int] = []

    class _StubRW:
        WATCHERS = rw_mod.WATCHERS

        @staticmethod
        def kill_pids_tree(pids: list[int]) -> list[int]:
            killed_pids.extend(pids)
            return []

    monkeypatch.setattr(cyc, '_rewatch', lambda: _StubRW)
    monkeypatch.setattr(cyc.time, 'sleep', lambda _s: None)

    class _FakeKid:
        """伪 Popen:supervise 只消费 pid / args / poll()。"""

        def __init__(self, pid: int, script: str, rc: int | None) -> None:
            self.pid = pid
            self.args = ['uv', 'run', 'python', _script_cmd(script)]
            self._rc = rc

        def poll(self) -> int | None:
            return self._rc

    alarm = _FakeKid(11, 'cw_sentinel.py', 7)       # 首个退出者(报警码)
    sibling = _FakeKid(12, 'cw_runs_gap.py', None)  # 在岗兄弟
    code = cyc.supervise({alarm.pid: alarm, sibling.pid: sibling})
    assert code == 7, f'首个退出者退出码未透传(实为 {code})'
    assert killed_pids == [sibling.pid], (
        f'兄弟未(只)经 rewatch 树杀缝终止,实杀 {killed_pids}')
