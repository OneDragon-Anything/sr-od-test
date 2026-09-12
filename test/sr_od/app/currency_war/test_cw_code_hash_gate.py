"""码哈希结构闸锁(ADR-0581;防线背景 = T-106 run6 混合码事故)。

出处(持久锚):ADR-0581
(docs/develop/sr_od/application/currency_war/decisions/0581-start-match-code-hash-gate.md)
= 设计口径/覆盖边界/豁免申报单一源;闸口径申报另一镜像 =
kernel/cw_code_hash_gate.py 模块 docstring。实施批账本行(T-107,.debug/progress/
易失)仅为辅助出处。闸语义:货币战争起局前比对「server 已加载码面(sys.modules
近似)的现盘内容」vs「git HEAD 内容」,不一致即拒起局;混合码(server 内存码 ≠
盘上码)行为不可归因,T-106 事故的结构防线。

三态主锁:洁净放行 / 不洁拦截(modified / untracked / 盘上被删)/ 豁免放行;
辅锁:git 不可用 fail-closed(两类异常)、untracked 报文两形态、sys.modules
收集口径、豁免名单最小性 + 锚定完整相对路径(同尾缀路径不豁免)、config 开关
缺省开 + save() 持久化(GUI 保存不得静默抹掉 yml 关闭值,先例 = max_rounds);
接线行为锁:起局节点真正调用闸并服从其判定(删 app 闸段即红)。

零副作用纪律的落实:repo/HEAD 全部合成在 tmp_path,head_reader 注入桩不触
真 git;config 测试把 os_utils.get_path_under_work_dir 整体重定向 tmp_path,
读写都不落真实 config 目录;sys.modules 注入用 monkeypatch.setitem 自动还原。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from one_dragon.utils import os_utils
from sr_od.application.currency_war.currency_war_config import CurrencyWarConfig
from sr_od.application.currency_war.kernel import cw_code_hash_gate
from sr_od.application.currency_war.kernel.cw_code_hash_gate import (
    DEFAULT_EXEMPTION_PATHS,
    GateResult,
    check_workspace_matches_head,
    collect_currency_war_module_files,
    default_head_reader,
)
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def _make_tree(root: Path, rel_contents: dict[str, str]) -> list[Path]:
    """在 tmp 根下合成工作树文件,返回对应路径列表(作为注入的 module_files)。"""
    files: list[Path] = []
    for rel, content in rel_contents.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        files.append(p)
    return files


def _head_of(head_contents: dict[str, str]):
    """合成 HEAD 读取桩:按 rel 查表返回 bytes;缺表 = untracked(None)。"""
    def _reader(_root: Path, rel: str) -> bytes | None:
        raw = head_contents.get(rel)
        return None if raw is None else raw.encode('utf-8')
    return _reader


def test_clean_tree_passes(tmp_path: Path) -> None:
    """洁净态(磁盘内容 == HEAD)→ 放行,扫描数如实。"""
    files = _make_tree(tmp_path, {'a_mod.py': 'x = 1', 'sub/b_mod.py': 'y = 2'})
    r: GateResult = check_workspace_matches_head(
        module_files=files, repo_root=tmp_path,
        head_reader=_head_of({'a_mod.py': 'x = 1', 'sub/b_mod.py': 'y = 2'}))
    assert r.ok, f'洁净树被误拦:{r.reason} {r.mismatches}'
    assert r.scanned == 2
    assert r.mismatches == []


def test_modified_file_blocks(tmp_path: Path) -> None:
    """不洁态①:HEAD 有该文件但工作树内容不同 → 拦截 + kind=modified + 点名路径。"""
    files = _make_tree(tmp_path, {'a_mod.py': 'x = 2(在飞编辑)'})
    r = check_workspace_matches_head(
        module_files=files, repo_root=tmp_path,
        head_reader=_head_of({'a_mod.py': 'x = 1'}))
    assert not r.ok, '工作树被编辑后仍放行 = 闸失效'
    assert r.mismatches == [{'path': 'a_mod.py', 'kind': 'modified'}]


def test_untracked_file_blocks(tmp_path: Path) -> None:
    """不洁态②:HEAD 无该文件(新文件未提交)→ 拦截 + kind=untracked。"""
    files = _make_tree(tmp_path, {'new_mod.py': 'z = 1'})
    r = check_workspace_matches_head(
        module_files=files, repo_root=tmp_path, head_reader=_head_of({}))
    assert not r.ok, '未提交新文件仍放行 = 闸失效'
    assert r.mismatches == [{'path': 'new_mod.py', 'kind': 'untracked'}]


def test_missing_on_disk_blocks(tmp_path: Path) -> None:
    """不洁态③:已加载模块盘上被删(码只存在于进程内存)→ 拦截 + kind=missing_on_disk。

    这是「即将运行的码 ≠ 盘上码」的最极端形态,读盘异常必须落成结构化
    不一致条目而非异常炸穿起局链。
    """
    gone = tmp_path / 'deleted_mod.py'
    r = check_workspace_matches_head(
        module_files=[gone], repo_root=tmp_path,
        head_reader=_head_of({'deleted_mod.py': 'w = 1'}))
    assert not r.ok
    assert r.mismatches == [{'path': 'deleted_mod.py', 'kind': 'missing_on_disk'}]


def test_crlf_disk_vs_lf_head_passes(tmp_path: Path) -> None:
    """CRLF 盘上文件 vs LF HEAD → 放行(换行差不算改动)。

    实机演练抓到的假阳性:Windows checkout(core.autocrlf)下盘上 CRLF、
    HEAD blob LF 是稳态,raw 字节哈希会把 git status 判净的洁净树全量
    拦死——防线变永久误报即失效。闸归一口径与 git 自身一致;
    反向伴随锁:换行之外的真内容差异仍必须拦。
    """
    crlf_disk = tmp_path / 'eol_mod.py'
    crlf_disk.write_bytes(b'a = 1\r\nb = 2\r\n')   # autocrlf checkout 后的盘上形态
    r = check_workspace_matches_head(
        module_files=[crlf_disk], repo_root=tmp_path,
        head_reader=lambda _root, _rel: b'a = 1\nb = 2\n')
    assert r.ok, f'纯换行差被误拦(autocrlf 稳态):{r.reason} {r.mismatches}'

    edited = tmp_path / 'edited_mod.py'
    edited.write_bytes(b'a = 999\r\nb = 2\r\n')   # 换行之外真改了内容
    r2 = check_workspace_matches_head(
        module_files=[edited], repo_root=tmp_path,
        head_reader=lambda _root, _rel: b'a = 1\nb = 2\n')
    assert not r2.ok, '换行归一不得吞掉真内容差异'
    assert r2.mismatches == [{'path': 'edited_mod.py', 'kind': 'modified'}]


def test_exempt_file_passes(tmp_path: Path) -> None:
    """豁免态:Δ池快照(局终自动再生管线写入,ADR-0344)磁盘 ≠ HEAD → 放行。

    同时锁两件事:
    ①「豁免 = 移出扫描域」——豁免文件不进 scanned 计数,报告口径里不出现
      「查过但豁免」的歧义态;
    ②「豁免锚定完整相对路径」(ADR-0581 §2.3)——仅尾缀相同的其他路径(如
      other_app/data/cw_delta_pool_data.py)**不得**豁免,仍按普通文件比对拦截;
      退回 endswith 后缀匹配会让该断言红。
    """
    exempt_rel = 'src/sr_od/application/currency_war/data/cw_delta_pool_data.py'
    files = _make_tree(tmp_path, {exempt_rel: 'SNAPSHOT = {}(局终再生)'})
    r = check_workspace_matches_head(
        module_files=files, repo_root=tmp_path,
        head_reader=_head_of({exempt_rel: 'SNAPSHOT = {}'}))
    assert r.ok, f'设计内再生文件被误拦:{r.reason}'
    assert r.scanned == 0

    # 反向伴随锁:同尾缀但路径不同 → 不豁免,照常拦截
    impostor_rel = 'src/sr_od/other_app/data/cw_delta_pool_data.py'
    files2 = _make_tree(tmp_path, {impostor_rel: 'x = 2(在飞编辑)'})
    r2 = check_workspace_matches_head(
        module_files=files2, repo_root=tmp_path,
        head_reader=_head_of({impostor_rel: 'x = 1'}))
    assert not r2.ok, '同尾缀路径被后缀匹配误豁免 = 豁免未锚定完整相对路径'
    assert r2.mismatches == [{'path': impostor_rel, 'kind': 'modified'}]


def test_exemption_list_is_minimal() -> None:
    """豁免名单最小性守卫:缺省名单只有 Δ池快照一条(逐条理由制,禁宽豁免)。

    豁免 = 闸的盲区,新增条目必须连理由一起过审;这条锁让「顺手加豁免」
    变成显式登记动作(锁红 = 有人改了缺省名单,须核对理由是否在册)。
    值 = 锚定完整相对路径(仓库根相对,含 src/ 前缀),非后缀——见
    test_exempt_file_passes 的反向伴随锁。
    """
    assert DEFAULT_EXEMPTION_PATHS == (
        'src/sr_od/application/currency_war/data/cw_delta_pool_data.py',
    )


def test_git_unavailable_fail_closed(tmp_path: Path) -> None:
    """git 不可用 → 宁拦勿放(RuntimeError 与文件系统级 OSError 同判)。"""
    files = _make_tree(tmp_path, {'a_mod.py': 'x = 1'})

    def _broken_runtime(_root: Path, _rel: str) -> bytes | None:
        raise RuntimeError('git show 失败')

    r = check_workspace_matches_head(module_files=files, repo_root=tmp_path,
                                     head_reader=_broken_runtime)
    assert not r.ok and 'fail-closed' in r.reason

    def _broken_fs(_root: Path, _rel: str) -> bytes | None:
        raise FileNotFoundError('git')

    r2 = check_workspace_matches_head(module_files=files, repo_root=tmp_path,
                                      head_reader=_broken_fs)
    assert not r2.ok and 'fail-closed' in r2.reason


def test_default_head_reader_wraps_missing_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """git 二进制缺失(subprocess 抛 OSError)→ default_head_reader 包成 RuntimeError。

    保证 check 层只需面对单一故障类型即能 fail-closed(口径见模块 docstring)。
    """
    def _no_git(*_args, **_kwargs):
        raise FileNotFoundError('git executable not found')

    monkeypatch.setattr(cw_code_hash_gate.subprocess, 'run', _no_git)
    with pytest.raises(RuntimeError, match='git 不可用'):
        default_head_reader(tmp_path, 'a_mod.py')


def test_head_reader_untracked_both_git_message_forms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """untracked 判定兼容 git 两种报文形态,均返回 None(而非误判 git 故障)。

    实机演练抓到的失效:git 新版对「盘上有、HEAD 无」报
    "path 'x' exists on disk, but not in 'HEAD'",旧判据只认
    "does not exist in 'HEAD'" → 合法新文件被当 git 故障 fail-closed,
    闸永远走不到真比对。两种形态都必须落到 untracked 语义。
    同时锁 LC_ALL=C 注入(ADR-0581 §2.1):报文判据认英文子串,子进程必须
    固定报文语言,防非英文 locale 本地化让判据失配退化成 fail-closed 硬拦。
    """
    import subprocess as _subprocess

    seen_envs: list[dict | None] = []

    def _git_says(stderr: bytes):
        def _run(*_args, **kwargs) -> _subprocess.CompletedProcess:
            seen_envs.append(kwargs.get('env'))
            return _subprocess.CompletedProcess(args=[], returncode=128, stdout=b'', stderr=stderr)
        return _run

    cases = [
        b"fatal: path 'a_mod.py' does not exist in 'HEAD'",
        b"fatal: path 'a_mod.py' exists on disk, but not in 'HEAD'",
    ]
    for stderr in cases:
        monkeypatch.setattr(cw_code_hash_gate.subprocess, 'run', _git_says(stderr))
        assert default_head_reader(tmp_path, 'a_mod.py') is None, f'报文未判为 untracked:{stderr!r}'
    assert all(e is not None and e.get('LC_ALL') == 'C' for e in seen_envs), \
        'git 子进程未注入 LC_ALL=C(报文本地化会让 untracked 判据失配)'


def test_collect_module_files_scopes_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """收集口径:只收 currency_war 前缀且带 __file__ 的已加载模块。

    server 加载码面的近似真值——前缀外的模块(含测试自身的其他 import)
    不入闸辖域;无 __file__ 的命名空间壳跳过。monkeypatch.setitem 保证
    进程级 sys.modules 测试后原样还原。
    """
    fake = types.ModuleType('sr_od.application.currency_war.fake_gate_mod')
    fake.__file__ = str(tmp_path / 'fake_gate_mod.py')
    monkeypatch.setitem(sys.modules, 'sr_od.application.currency_war.fake_gate_mod', fake)

    outside = types.ModuleType('sr_od.other_pkg.mod')
    outside.__file__ = str(tmp_path / 'outside.py')
    monkeypatch.setitem(sys.modules, 'sr_od.other_pkg.mod', outside)

    no_file = types.ModuleType('sr_od.application.currency_war.namespace_shell')
    monkeypatch.setitem(sys.modules, 'sr_od.application.currency_war.namespace_shell', no_file)

    collected = collect_currency_war_module_files()
    assert (tmp_path / 'fake_gate_mod.py') in collected
    assert all(p.name != 'outside.py' for p in collected)
    assert all(p.name != 'namespace_shell' for p in collected)


def test_gate_switch_default_on_and_save_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """闸开关缺省开(安全闸宁拦勿放)且 save() 持久化。

    回归锚:max_rounds 先例——save() 白名单漏字段时,GUI 保存会静默抹掉
    yml 手写值;闸的关闭值被抹 = 闸被悄悄重开 = 配置丢失即行为漂移。
    os_utils 路径函数整体重定向 tmp_path,读写均不落真实 config 目录。
    """
    monkeypatch.setattr(os_utils, 'get_path_under_work_dir',
                        lambda *parts: tmp_path.joinpath(*parts))

    cfg = CurrencyWarConfig()
    assert cfg.code_hash_gate is True, '安全闸缺省必须开'

    cfg.code_hash_gate = False
    cfg.save()
    cfg_reloaded = CurrencyWarConfig()
    assert cfg_reloaded.code_hash_gate is False, \
        'save() 未持久化 code_hash_gate:GUI 保存会静默抹掉 yml 关闭值'


def test_start_match_gate_wiring_rejects_unclean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    test_context: SrTestContext,
) -> None:
    """接线行为锁(ADR-0581 §2.1;失守事故 = T-106 run6 混合码):起局节点
    `_start_match` 必须真正调用码哈希闸并服从其判定——闸判不洁 → round_fail 拒起。

    其余锁全部罩闸本体与 config:删掉 app 起局节点的闸段,它们依旧全绿、
    防线静默脱落(本锁立项时的对抗审实证)。本锁断言两件事:①闸函数被调用
    (接线存在);②不洁判定传导为起局失败(round_fail 路径)。harness 形态
    复用 test_cw_screens_entry 的 CurrencyWarApp 节点直调
    (enter_running_state/reset_running_state + fast_sleep)。
    """
    from sr_od.application.currency_war.currency_war_app import CurrencyWarApp

    # _start_match 内构造 CurrencyWarConfig:os_utils 路径函数整体重定向
    # tmp_path,读写均不落真实 config(同 config 回环锁手法,闸走缺省开分支)。
    monkeypatch.setattr(os_utils, 'get_path_under_work_dir',
                        lambda *parts: tmp_path.joinpath(*parts))

    gate_calls: list[GateResult] = []

    def _unclean_gate(*_args, **_kwargs) -> GateResult:
        result = GateResult(
            ok=False, scanned=2,
            mismatches=[{'path': 'a_mod.py', 'kind': 'modified'},
                        {'path': 'b_mod.py', 'kind': 'untracked'}],
            reason='工作树与 HEAD 不一致 2 个文件')
        gate_calls.append(result)
        return result

    # 桩打在闸模块属性上:_start_match 函数体内的 from-import 每次调用
    # 都重新解析模块属性,monkeypatch 可达(无需触真 git)。
    monkeypatch.setattr(cw_code_hash_gate, 'check_workspace_matches_head',
                        _unclean_gate)

    app = CurrencyWarApp(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep():
            result = app._start_match()
    finally:
        reset_running_state(test_context, app)

    assert len(gate_calls) == 1, '起局节点未调用码哈希闸(闸接线脱落)'
    assert result.is_fail and not result.is_success, \
        f'闸判不洁未拒起:status={result.status!r}'
    assert '起局拒绝' in (result.status or ''), \
        f'失败文案缺「起局拒绝」语义:status={result.status!r}'
