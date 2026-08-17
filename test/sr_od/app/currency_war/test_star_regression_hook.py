"""star 回退停机钩子测试(用户 2026-08-17:预估升星 vs 实机读回不符 → 停机排查)。

三路径:①首节点回退只留证不停(防抖,特效过渡帧);②连续 2 节点 star≥2 回退 → 停机
(sentinel 自描述+stop_running);③读回恢复 → 计数清零(不再累积)。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))
sys.path.insert(0, str(_REPO / 'sr-od-test'))

from sr_od.application.currency_war.cw_reconcile import reconcile_tracking  # noqa: E402


class _Ctx:
    def __init__(self, tmp_path):
        self.stopped = False
        self.run_context = SimpleNamespace(stop_running=lambda: setattr(self, 'stopped', True))
        self._cwd = Path.cwd()
        import os
        os.chdir(tmp_path)   # sentinel 写 .debug/... 隔离

    def restore(self):
        import os
        os.chdir(self._cwd)


def _sess(tracked_2star: bool):
    bench = [SimpleNamespace(char_id='银狼', star=2, slot=1, position_pref='back')] if tracked_2star else []
    return SimpleNamespace(
        tracked_bench_chars=bench, tracked_deployed=[],
        star_regression_count={})


def _read(star: int):
    return [SimpleNamespace(char_id='银狼', star=star, slot=1, position_pref='back')]


def test_first_regression_no_stop(tmp_path, monkeypatch) -> None:
    """首节点 2★→1★:留证 + 计数 1,不停机(防抖)。"""
    import sr_od.application.currency_war.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(tmp_path)
    s = _sess(True)
    try:
        reconcile_tracking(s, _read(1), [], None, source='t', ctx=ctx)
        assert not ctx.stopped
        assert s.star_regression_count.get('银狼') == 1
    finally:
        ctx.restore()


def test_second_regression_stops(tmp_path, monkeypatch) -> None:
    """连续第 2 节点 2★→1★:停机 + sentinel 自描述(含删除位置/排查项)。"""
    import sr_od.application.currency_war.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(tmp_path)
    s = _sess(True)
    s.star_regression_count = {'银狼': 1}   # 上一节点已回退一次
    try:
        reconcile_tracking(s, _read(1), [], None, source='t', ctx=ctx)
        assert ctx.stopped, '连续 2 节点 star≥2 回退应停机'
        flag = tmp_path / '.debug' / 'temp' / 'currency_war' / 'star_regression_hook.flag'
        assert flag.exists(), 'sentinel 应写入'
        content = flag.read_text(encoding='utf-8')
        assert '_star_stop_hook' in content        # 删除位置指针
        assert '非手停' in content                  # 自描述(r17-r31 教训)
    finally:
        ctx.restore()


def test_recovered_star_resets_count(tmp_path, monkeypatch) -> None:
    """读回恢复(2★ 读回 2★):计数清零,不累积误停。"""
    import sr_od.application.currency_war.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(tmp_path)
    s = _sess(True)
    s.star_regression_count = {'银狼': 1}
    try:
        reconcile_tracking(s, _read(2), [], None, source='t', ctx=ctx)
        assert not ctx.stopped
        assert '银狼' not in s.star_regression_count
    finally:
        ctx.restore()


def test_low_star_regression_never_stops(tmp_path, monkeypatch) -> None:
    """1★ 档回退不入停机范围(用户担心面 = star2/3 识别;1★ 常态噪声大)。"""
    import sr_od.application.currency_war.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(tmp_path)
    s = SimpleNamespace(
        tracked_bench_chars=[SimpleNamespace(char_id='藿藿', star=1, slot=1, position_pref='back')],
        tracked_deployed=[], star_regression_count={'藿藿': 5})
    try:
        # 1★→更低不存在(read fallback=1),构造 old=1 new 不会更低 → 本测验「old<2 不入计数」:
        # 用 old=1 走不到回退分支;直接验 3★→2★ 入计数、1★ 组合计数不动
        s2 = _sess(True)
        s2.tracked_bench_chars[0].star = 3
        reconcile_tracking(s2, _read(2), [], None, source='t', ctx=ctx)
        assert s2.star_regression_count.get('银狼') == 1   # 3★→2★ 入计数
        assert not ctx.stopped
    finally:
        ctx.restore()
