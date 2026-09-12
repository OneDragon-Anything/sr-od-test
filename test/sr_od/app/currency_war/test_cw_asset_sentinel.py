"""资产完整性哨兵锁(tools/cw/cw_asset_sentinel.py:基线对比/分级判定/驻留收账)。

被测工具 = 主仓 ``tools/cw/cw_asset_sentinel.py``(纯 stdlib + psutil,零 src 导入;
按路径装载,先例 = test_cw_rewatch_tree_kill._load)。背景 = 运行时资产目录
(OCR 模型/CW 模板库)多次被外部清空、每次靠人工/框架下载链事后恢复——
哨兵做基线对比看门,只报不修。行为契约(skill references/runtime-ops.md
「哨兵脚本组」表行 + 脚本文件头「分级」节):

  ① 分级:critical 档监控面的目录丢失(junction 悬空同判)/目录清空/关键
    模型文件缺失 → critical(process_round 返回即退码 3);部分文件缺失/
    新文件/大小变化/链接形态变化/目录恢复 → general 驻留;watch 档
    (ppocrv6)任何变更恒 general。
  ② 目录级翻转吞并逐文件条目(dir_emptied 不双报 file_missing、
    dir_refilled 不双报 file_added)——同因噪声,证据一条够定位。
  ③ 驻留收账:general 首见入 outstanding + 证据落盘,恢复出账返回 None
    继续驻留;签名稳定(size_changed 不含大小值,同文件反复变不刷屏)。
  ④ rewatch 纳管(重武三步兼容):WATCHER_CMD_NAMES 含 cw_asset_sentinel,
    词级匹配与既有哨兵名互不误配。

零真实副作用:全部 IO 走 tmp_path/合成树(main 路径经 monkeypatch 重定向,
不写真实 .debug);junction 用例仅 Windows 走 _winapi.CreateJunction,其余
平台跳过。毫秒级,不入慢桶。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_TOOL_PATH = _REPO_ROOT / 'tools' / 'cw' / 'cw_asset_sentinel.py'
_REWATCH_PATH = _REPO_ROOT / 'tools' / 'cw' / 'rewatch.py'
_MOD = 'cw_asset_sentinel_tool_under_lock'
_REWATCH_MOD = 'cw_rewatch_tool_under_lock'

WIN32 = sys.platform == 'win32'


def _load(path: Path, name: str) -> Any:
    """按路径装载被测工具(sys.modules 缓存,跨用例只 exec 一次;
    先例 = test_cw_rewatch_tree_kill._load)。"""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _spec(path_parts: list[str], level: str = 'critical',
          key_files: list[str] | None = None) -> dict:
    """合成监控面 spec(与生产 spec 同构;key_files 进快照供纯 diff 消费)。"""
    return {'label': 't', 'path': path_parts, 'level': level,
            'key_files': key_files or [], 'source': 'test'}


def _wrap(snap: dict, key: str = 't') -> dict:
    """单监控面快照包成 diff_targets 的入参形态。"""
    return {'targets': {key: snap}}


@pytest.fixture()
def model_tree(tmp_path: Path) -> tuple[Path, dict]:
    """合成 OCR 模型面(仿 ppocrv5:关键件+字典+普通件),返回 (根, spec)。"""
    d = tmp_path / 'assets' / 'models' / 'onnx_ocr' / 'ppocrv5'
    d.mkdir(parents=True)
    for name, size in (('det.onnx', 100), ('rec.onnx', 200), ('cls.onnx', 50),
                       ('ppocrv5_dict.txt', 10), ('extra.bin', 5)):
        (d / name).write_bytes(b'x' * size)
    spec = _spec(['assets', 'models', 'onnx_ocr', 'ppocrv5'],
                 key_files=['det.onnx', 'rec.onnx', 'cls.onnx', 'ppocrv5_dict.txt'])
    return tmp_path, spec


# ---- 快照与基线 IO -------------------------------------------------------


def test_scan_snapshot_and_baseline_roundtrip(model_tree) -> None:
    """快照清点(文件数/大小/相对路径 POSIX 化)与基线 save/load 往返一致。"""
    mod = _load(_TOOL_PATH, _MOD)
    root, spec = model_tree
    snap = mod.scan_target(root, spec)
    assert snap['exists'] and snap['file_count'] == 5
    assert snap['total_bytes'] == 365
    assert snap['files']['det.onnx'] == 100
    assert not snap['is_link']
    path = root / 'baseline.json'
    mod.save_baseline(path, _wrap(snap))
    assert mod.load_baseline(path) == _wrap(snap)


def test_load_baseline_missing_returns_none(tmp_path: Path) -> None:
    """基线不存在 → None(调用方走首跑生成),不抛错。"""
    mod = _load(_TOOL_PATH, _MOD)
    assert mod.load_baseline(tmp_path / 'nope.json') is None


def test_load_baseline_corrupt_exits_2(tmp_path: Path, capsys) -> None:
    """基线损坏 → exit 2 拒静默重建:基线是对比锚,自动重建会把已发生的
    清空钉成新正常态(--rebaseline 是唯一显式重建口)。"""
    mod = _load(_TOOL_PATH, _MOD)
    bad = tmp_path / 'baseline.json'
    bad.write_text('{not json', encoding='utf-8')
    with pytest.raises(SystemExit) as exc:
        mod.load_baseline(bad)
    assert exc.value.code == 2
    assert '禁静默重建' in capsys.readouterr().out


# ---- 分级判定(纯 diff)--------------------------------------------------


def test_critical_dir_missing_with_dangling_junction_note() -> None:
    """目录丢失 = critical;junction 基线附悬空提示(junction 目标侧被清是
    实证清空形态,提示可修链接 vs 重下)。"""
    mod = _load(_TOOL_PATH, _MOD)
    base = {'exists': True, 'is_link': True, 'link_target': 'D:/store/m1',
            'level': 'critical', 'key_files': [], 'path': 'a/b',
            'files': {'x.onnx': 1}, 'file_count': 1}
    curr = dict(base, exists=False, files={}, file_count=0, total_bytes=0)
    findings = mod.diff_targets(_wrap(base), _wrap(curr))
    assert mod.has_critical(findings)
    assert findings[0]['kind'] == 'dir_missing'
    assert findings[0]['severity'] == 'critical'
    assert '悬空' in findings[0]['detail'] and 'D:/store/m1' in findings[0]['detail']


def test_persistent_missing_not_refired() -> None:
    """基线缺失且当前仍缺失 = 持续缺失不逐轮重复报(基线已如实记录,
    重复报警无增量信息)。"""
    mod = _load(_TOOL_PATH, _MOD)
    missing = {'exists': False, 'is_link': False, 'link_target': None,
               'level': 'critical', 'key_files': [], 'path': 'a',
               'files': {}, 'file_count': 0}
    assert mod.diff_targets(_wrap(missing), _wrap(dict(missing))) == []


def test_key_file_missing_grades_by_level() -> None:
    """同一关键模型文件缺失:critical 档(ppocrv5 缺省在用档)升即退;
    watch 档(ppocrv6 非缺省可选档)恒 general——丢不破缺省运行时。"""
    mod = _load(_TOOL_PATH, _MOD)

    def snapshot(level: str) -> tuple[dict, dict]:
        files = {'det.onnx': 100, 'rec.onnx': 200}
        base = {'exists': True, 'is_link': False, 'link_target': None,
                'level': level, 'key_files': ['det.onnx'], 'path': 'm',
                'files': dict(files), 'file_count': 2}
        curr_files = {'rec.onnx': 200}
        curr = dict(base, files=dict(curr_files), file_count=1)
        return _wrap(base), _wrap(curr)

    for level, expected in (('critical', 'critical'), ('watch', 'general')):
        b, c = snapshot(level)
        findings = mod.diff_targets(b, c)
        hit = [f for f in findings if f['kind'] == 'file_missing']
        assert len(hit) == 1 and hit[0]['severity'] == expected, level
        assert mod.has_critical(findings) == (expected == 'critical')


def test_dir_level_transitions_subsume_file_entries(model_tree) -> None:
    """目录级翻转吞并逐文件条目(契约②):清空 = dir_emptied 且无
    file_missing;空目录回填 = dir_refilled 且无 file_added——同因噪声
    不在证据里双报。"""
    mod = _load(_TOOL_PATH, _MOD)
    root, spec = model_tree
    base = mod.scan_target(root, spec)

    for p in (root / 'assets/models/onnx_ocr/ppocrv5').iterdir():
        p.unlink()
    emptied = mod.diff_targets(_wrap(base), _wrap(mod.scan_target(root, spec)))
    assert any(f['kind'] == 'dir_emptied' and f['severity'] == 'critical'
               for f in emptied)
    assert not any(f['kind'] == 'file_missing' for f in emptied)

    empty_base = mod.scan_target(root, spec)   # 目录此刻为空 = 回填场景的基线
    (root / 'assets/models/onnx_ocr/ppocrv5/refilled.onnx').write_bytes(b'y')
    refilled = mod.diff_targets(_wrap(empty_base),
                                _wrap(mod.scan_target(root, spec)))
    assert [f['kind'] for f in refilled] == ['dir_refilled']
    assert not mod.has_critical(refilled)


def test_general_changes_and_signature_stability(model_tree) -> None:
    """一般变更(新文件/大小变化/目录恢复)恒 general;签名只由
    kind|key|path 构成——size_changed 不含大小值,同文件反复变同签名
    (纪元内首见必报、复见静默,防高频写文件刷屏)。"""
    mod = _load(_TOOL_PATH, _MOD)
    root, spec = model_tree
    base = mod.scan_target(root, spec)
    d = root / 'assets/models/onnx_ocr/ppocrv5'

    (d / 'new.bin').write_bytes(b'n' * 7)
    (d / 'det.onnx').write_bytes(b'x' * 999)
    findings = mod.diff_targets(_wrap(base), _wrap(mod.scan_target(root, spec)))
    kinds = {f['kind'] for f in findings}
    assert {'file_added', 'size_changed'} <= kinds
    assert not mod.has_critical(findings)
    size_f = next(f for f in findings if f['kind'] == 'size_changed')
    assert mod.finding_signature(size_f) == 'size_changed|t|det.onnx'
    assert (mod.finding_signature(size_f)
            == mod.finding_signature(dict(size_f, detail='大小变化 1 → 2 字节')))

    (d / 'new.bin').unlink()
    (d / 'det.onnx').write_bytes(b'x' * 100)
    restored = mod.diff_targets(_wrap(base), _wrap(mod.scan_target(root, spec)))
    assert restored == []


def test_spec_drift_reported_general() -> None:
    """基线与当前扫描监控面清单不一致(基线跨版本)→ general spec_drift,
    不静默也不误判 critical(--rebaseline 收敛)。"""
    mod = _load(_TOOL_PATH, _MOD)
    snap = {'exists': True, 'is_link': False, 'link_target': None,
            'level': 'critical', 'key_files': [], 'path': 'a',
            'files': {}, 'file_count': 0}
    findings = mod.diff_targets({'targets': {'old': snap}}, {'targets': {'new': snap}})
    assert [f['kind'] for f in findings] == ['spec_drift', 'spec_drift']
    assert all(f['severity'] == 'general' for f in findings)


# ---- 驻留收账(process_round)--------------------------------------------


def test_process_round_resident_resolve_and_critical_exit(
        monkeypatch, tmp_path, capsys) -> None:
    """驻留收账全链(契约③):general 首见 → [ASSET-HIT-CONT]+outstanding
    入账+证据落盘,返回 None 继续驻留;恢复 → [ASSET-OK] 出账;目录丢失
    → 返回即退码 3。证据路径重定向 tmp(零真实 .debug 写)。"""
    mod = _load(_TOOL_PATH, _MOD)
    monkeypatch.setattr(mod, 'EVIDENCE_PATH', tmp_path / 'evidence.md')
    watched = tmp_path / 'watched'
    watched.mkdir()
    spec = _spec(['watched'])
    base = _wrap(mod.scan_target(tmp_path, spec))

    def scan() -> dict:
        return _wrap(mod.scan_target(tmp_path, spec))

    outstanding: dict[str, tuple[str, str]] = {}
    (watched / 'a.txt').write_text('hi')
    assert mod.process_round(base, scan(), outstanding) is None
    assert len(outstanding) == 1   # 空目录回填只报 dir_refilled 一条(契约②)
    assert 'ASSET-HIT-CONT' in capsys.readouterr().out
    assert (tmp_path / 'evidence.md').exists()

    (watched / 'a.txt').unlink()
    assert mod.process_round(base, scan(), outstanding) is None
    assert outstanding == {}   # 恢复出账
    assert 'ASSET-OK' in capsys.readouterr().out

    watched.rmdir()
    assert mod.process_round(base, scan(), outstanding) == mod.EXIT_CRITICAL
    assert 'ASSET-HIT]' in capsys.readouterr().out


def test_evidence_body_lists_findings_and_advice() -> None:
    """证据正文含逐条明细(签名+严重度+首见时刻)与处置指引(恢复走
    框架下载链/git checkout,只报不修契约可读)。"""
    mod = _load(_TOOL_PATH, _MOD)
    findings = [
        {'kind': 'dir_missing', 'key': 'ocr_ppocrv5', 'path': 'assets/...',
         'detail': '目录丢失', 'severity': 'critical'},
        {'kind': 'file_added', 'key': 'cw_boss_avatar', 'path': 'x.png',
         'detail': '新文件(1 字节)', 'severity': 'general'},
    ]
    body = '\n'.join(mod.evidence_body(findings, {
        'file_added|cw_boss_avatar|x.png': '2026-09-11 12:00:00'}))
    assert 'critical 数: 1' in body
    assert 'dir_missing|ocr_ppocrv5' in body
    assert 'file_added|cw_boss_avatar|x.png' in body
    assert '[首见 2026-09-11 12:00:00]' in body
    assert '--rebaseline' in body   # 收敛口可发现


# ---- main 装配(--once 端到端,路径全重定向)------------------------------


def _seed_full_tree(root: Path) -> None:
    """按生产监控面造最小合成树:两 OCR 模型 + 两模板库(文件数随意,
    基线对比只看相对变化)。"""
    ocr5 = root / 'assets/models/onnx_ocr/ppocrv5'
    ocr6 = root / 'assets/models/onnx_ocr/ppocrv6'
    plaza = root / 'assets/template/currency_war/portrait_plaza/某角色'
    boss = root / 'assets/template/currency_war/boss_avatar'
    for d, files in ((ocr5, ('det.onnx', 'rec.onnx', 'cls.onnx', 'simfang.ttf',
                             'ppocrv5_dict.txt')),
                     (ocr6, ('det.onnx', 'rec.onnx', 'cls.onnx', 'simfang.ttf',
                             'ppocrv6_dict.txt')),
                     (plaza, ('raw.png', 'mask.png')),
                     (boss, ('boss1.png',))):
        d.mkdir(parents=True, exist_ok=True)
        for name in files:
            (d / name).write_bytes(b'x' * 8)


def test_main_once_first_run_baselines_then_clean(monkeypatch, tmp_path,
                                                  capsys) -> None:
    """--once 首跑:落基线 + 干净退出 0(合成树全监控面,路径经
    monkeypatch 重定向,零真实 .debug 写)。"""
    mod = _load(_TOOL_PATH, _MOD)
    root = tmp_path / 'repo_root'   # 哨兵的资产根;树必须种在它下面
    _seed_full_tree(root)
    for name in ('BASELINE_PATH', 'EVIDENCE_PATH', 'LOCK_PATH', 'POS_PATH'):
        monkeypatch.setattr(mod, name, tmp_path / name.lower())
    monkeypatch.setattr(mod, 'REPO_ROOT', root)
    monkeypatch.setattr(sys, 'argv', ['cw_asset_sentinel.py', '--once'])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    assert 'ASSET-BASELINE' in capsys.readouterr().out
    baseline = json.loads(
        (tmp_path / 'baseline_path').read_text(encoding='utf-8'))
    assert set(baseline['targets']) == {
        'ocr_ppocrv5', 'ocr_ppocrv6', 'cw_portrait_plaza', 'cw_boss_avatar'}
    assert baseline['targets']['ocr_ppocrv5']['file_count'] == 5


def test_main_once_critical_exits_3_after_key_file_loss(monkeypatch, tmp_path,
                                                        capsys) -> None:
    """--once 二跑:关键模型文件缺失(det.onnx)→ [ASSET-HIT] + exit 3
    (即退契约;编排者后台任务信道靠非 0 退出码收警报)。"""
    mod = _load(_TOOL_PATH, _MOD)
    root = tmp_path / 'repo_root'
    _seed_full_tree(root)
    for name in ('BASELINE_PATH', 'EVIDENCE_PATH', 'LOCK_PATH', 'POS_PATH'):
        monkeypatch.setattr(mod, name, tmp_path / name.lower())
    monkeypatch.setattr(mod, 'REPO_ROOT', root)
    monkeypatch.setattr(sys, 'argv', ['cw_asset_sentinel.py', '--once'])
    with pytest.raises(SystemExit):
        mod.main()
    capsys.readouterr()

    (root / 'assets/models/onnx_ocr/ppocrv5/det.onnx').unlink()
    # 清掉首跑留下的锁再 arm:锁内是本 pytest 进程 pid,而本测试文件名恰含
    # 'cw_asset_sentinel' 子串 → 陈旧锁检查会把测试进程误判为在岗实例
    # (生产形态是独立 python 进程,无此重入)。rewatch 杀净后重武的对应物。
    (tmp_path / 'lock_path').unlink(missing_ok=True)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == mod.EXIT_CRITICAL
    out = capsys.readouterr().out
    assert '[ASSET-HIT]' in out and 'det.onnx' in out
    assert (tmp_path / 'evidence_path').exists()


# ---- junction 实形态(Windows 可达)---------------------------------------


@pytest.mark.skipif(not WIN32, reason='junction 是 Windows 形态')
def test_junction_scan_penetrates_and_detects_dangling(tmp_path) -> None:
    """junction 监控面:穿透清点目标内容;目标侧被清 → exists False 且
    is_link True(悬空态可辨),diff 判 critical——ppocrv5 实为 junction
    指向外部模型库,这是本哨兵的核心清空形态。"""
    import _winapi

    mod = _load(_TOOL_PATH, _MOD)
    store = tmp_path / 'store' / 'm1'
    store.mkdir(parents=True)
    (store / 'a.onnx').write_bytes(b'z' * 3)
    link = tmp_path / 'link_m1'
    _winapi.CreateJunction(str(store), str(link))
    spec = _spec(['link_m1'], key_files=['a.onnx'])
    live = mod.scan_target(tmp_path, spec)
    assert live['is_link'] and live['file_count'] == 1
    assert 'm1' in (live['link_target'] or '')

    import shutil as _shutil
    _shutil.rmtree(store)
    dangling = mod.scan_target(tmp_path, spec)
    assert (not dangling['exists']) and dangling['is_link']
    findings = mod.diff_targets(_wrap(live), _wrap(dangling))
    assert mod.has_critical(findings)
    assert findings[0]['kind'] == 'dir_missing'


# ---- rewatch 纳管(重武三步兼容)------------------------------------------


def test_rewatch_manages_asset_sentinel() -> None:
    """rewatch 纳管锁(契约④,接线存在性——防查旧/杀净对资产哨兵静默脱落,
    脱落 = 双实例报警链断,重武三步管不到它):WATCHER_CMD_NAMES 含本哨兵,
    词级匹配与既有哨兵名互不误配(\\b 边界:'cw_sentinel' 不命中
    'cw_asset_sentinel' 命令行,反之亦然)。"""
    rw = _load(_REWATCH_PATH, _REWATCH_MOD)
    assert 'cw_asset_sentinel' in rw.WATCHER_CMD_NAMES
    key, (script, _note) = next(
        (k, v) for k, v in rw.WATCHERS.items() if v[0] == 'cw_asset_sentinel.py')
    assert key == 'asset'
    asset_cmd = 'uv run python tools/cw/cw_asset_sentinel.py'
    event_cmd = 'uv run python skills/sr-od-currency-war-dev/scripts/cw_sentinel.py'
    assert rw._is_on_duty(asset_cmd, 'cw_asset_sentinel')
    assert rw._is_on_duty(event_cmd, 'cw_sentinel')
    assert not rw._is_on_duty(asset_cmd, 'cw_sentinel'), '同前缀名误配(假在岗)'
    assert not rw._is_on_duty(event_cmd, 'cw_asset_sentinel')


# ---- 内置自测入口 ---------------------------------------------------------


def test_selftest_entry_exits_zero(monkeypatch) -> None:
    """--selftest 合成树回归全过即 0(机上一键验证口,不碰真实资产与
    .debug;OS 临时目录自清理)。"""
    mod = _load(_TOOL_PATH, _MOD)
    monkeypatch.setattr(sys, 'argv', ['cw_asset_sentinel.py', '--selftest'])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
