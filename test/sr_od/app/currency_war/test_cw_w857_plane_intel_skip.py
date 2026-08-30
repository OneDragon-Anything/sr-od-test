"""行为锁:位面情报采集跳过已完成位面(实机观察实证修复批)。

背景:实机 P2 采集时逐位面全量重采——位面 1 已变暗(过去时),重采浪费
且变暗渲染下节点条识别退化,采集长时间停留无法从日志诊断。治本:
采集循环按会话位面真值跳过过去位面(台账保留其已写值,不覆写不重采),
并补齐逐位面采集/跳过/耗时的细节日志(观测缺口)。

判据纯函数 = ``collect_plane_intel.decide_plane_skip``(设计语义见其
docstring;边界:无会话真值不跳 / past 缺值降级补采一次 / 当前与未来
位面正常采)。
"""
from __future__ import annotations


def test_decide_plane_skip_truth_table() -> None:
    """skip 判据真值表:过去跳过 / 当前未来采集 / 无真值不跳 / 缺值补采。"""
    from sr_od.application.currency_war.operations.handlers.collect_plane_intel import (
        decide_plane_skip,
    )

    # 过去位面 + 台账有值 → 跳过
    skip, note = decide_plane_skip(1, 2, ['battle', 'reward', 'boss'])
    assert skip is True
    assert '跳过' in note and '台账' in note
    skip, _ = decide_plane_skip(2, 3, ['battle', 'boss'])
    assert skip is True
    # 当前位面 → 采集;未来位面 → 采集
    assert decide_plane_skip(2, 2, ['battle', 'boss']) == (False, '')
    assert decide_plane_skip(3, 2, None) == (False, '')
    # 会话真值未知(None)→ 不跳全量采集(无真值不发明跳过)
    assert decide_plane_skip(1, None, ['battle', 'boss']) == (False, '')
    # past 位面台账缺值(None/空/全 None 位)→ 降级补采(变暗态低置信标注)
    skip, note = decide_plane_skip(1, 2, None)
    assert skip is False
    assert '补采' in note and '低置信' in note
    skip, note = decide_plane_skip(1, 2, [])
    assert skip is False and '补采' in note
    skip, note = decide_plane_skip(1, 2, [None, None])
    assert skip is False and '补采' in note


def test_collect_loop_has_skip_filter_and_per_plane_logs() -> None:
    """采集循环接线锁:skip 过滤被调用 + 逐位面「采集/跳过/耗时」日志落地
    (观测缺口补齐:用户观察到的停留必须能从日志诊断)。"""
    import inspect

    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel,
    )

    src = inspect.getsource(collect_plane_intel.CollectPlaneIntel)
    assert 'decide_plane_skip(' in src, '采集循环未接 skip 判据'
    assert '跳过(已完成)' in src, '采集循环缺跳过日志(观测缺口)'
    assert '采集完成(耗时' in src, '采集循环缺逐位面耗时日志(观测缺口)'
    assert '_session_plane' in src, '采集循环缺会话位面真值读取'
    # 跳过位面不进 _detail_seqs → close_and_report 不覆写其台账值(保留语义)
    assert 'self._detail_seqs[self._cur_plane + 1]' in src, (
        '详情条序列写入点漂移,跳过位面「不覆写」契约失去载体')


def test_observation_docstring_annotates_dimmed_state() -> None:
    """读法注释锁:位面详情节点条读法须标注「过去位面变暗渲染识别退化」
    (防止后续改动把变暗态当识别 bug 误修,而非 skip 语义覆盖)。"""
    import inspect

    from sr_od.application.currency_war.obs import cw_observation

    doc = inspect.getdoc(cw_observation.read_plane_detail_nodes) or ''
    assert '变暗' in doc, '节点条读法缺过去位面变暗态注释'


# --------------------------------------------------------------------------- #
# clean 等待门静止帧提前放弃(2026-08-30 哨兵 20:22:36 实证治理)
# --------------------------------------------------------------------------- #
# 实证链:P2 采集点位面 1(变暗灰态)→ read 恒 None → 门把 None 一律归因
# 「切卡动画中」硬等 90s 后放弃——采集从未通过此门(设计=新局 P1 一次性
# 补采,却在 P2 反复出现即此慢性失败的漂移结果)。治本:门加帧稳定性信号
# ——连续 2 帧零变化=静止渲染态(等不会变 clean)→ 提前放弃;
# 真动画帧间必有变化 → 原超上限路径保持不动(w314 锁①/②锁该路)。


def test_gate_fails_fast_on_static_frames() -> None:
    """静止帧提前放弃:连续 2 帧零变化 → round_fail,不等 90s 上限。"""
    import numpy as np

    from test.harness.fixture_controller import fast_sleep

    img = np.zeros((108, 192, 3), dtype=np.uint8)   # 静止帧(两轮同图)
    op = _bare_op()
    op.last_screenshot = img

    with fast_sleep():
        r1 = op._nonclean_read_gate('切卡动画中')
        assert '间隔重读' in str(r1.status), (
            f'第 1 帧(尚无前帧可比)应走间隔重读,得 {r1.status!r}')
        r2 = op._nonclean_read_gate('切卡动画中')
    assert r2.is_fail, f'连续 2 帧零变化应提前放弃,得 {r2.status!r}'
    assert '静止' in str(r2.status), f'失败应声明静止帧根因,得 {r2.status!r}'
    assert '动画' in str(r2.status), f'失败应声明非动画(与 90s 超限相区分),得 {r2.status!r}'


def test_gate_keeps_waiting_on_changing_frames() -> None:
    """帧在变(真动画)→ 不触发静止提前放弃,仍走间隔重读/超上限路径。"""
    import numpy as np

    from test.harness.fixture_controller import fast_sleep

    img_a = np.zeros((108, 192, 3), dtype=np.uint8)
    img_b = np.full((108, 192, 3), 200, dtype=np.uint8)   # 与 a 差异显著
    op = _bare_op()

    with fast_sleep():
        op.last_screenshot = img_a
        r1 = op._nonclean_read_gate('切卡动画中')
        assert '间隔重读' in str(r1.status), f'第 1 帧应间隔重读,得 {r1.status!r}'
        op.last_screenshot = img_b
        r2 = op._nonclean_read_gate('切卡动画中')
    assert '间隔重读' in str(r2.status), f'帧间有变化(真动画)不应提前放弃,得 {r2.status!r}'


def test_frames_identical_tolerance() -> None:
    """帧差判定:同图=零变化;显著差异图=有变化(容忍压缩噪声的容差语义)。"""
    import numpy as np

    from sr_od.application.currency_war.operations.handlers.collect_plane_intel import (
        _frames_identical,
    )

    a = np.zeros((54, 96), dtype=np.uint8)
    assert _frames_identical(a, a.copy()) is True
    assert _frames_identical(a, a + 1) is True          # 噪声级差异容忍
    b = np.full((54, 96), 180, dtype=np.uint8)
    assert _frames_identical(a, b) is False             # 显著差异=动画


def _bare_op():
    """免 fixture 构造最小 op(仅测门方法:跳过 SrOperation 重初始化)。"""
    from sr_od.application.currency_war.operations.handlers.collect_plane_intel import (
        CollectPlaneIntel,
    )

    op = CollectPlaneIntel.__new__(CollectPlaneIntel)
    op._nonclean_wait_start = None
    op._gate_prev_thumb = None
    op._gate_static_streak = 0
    op._best_effort_close_detail = lambda: None   # 单测不触真实截图/点击
    return op
