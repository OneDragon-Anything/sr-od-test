"""位面情报采集·时序修正批(2026-09-03 用户裁决)验证锁。

裁决语义:
1. 时序反过来——进位面详情**之前**先在备战画面识别当前节点(顶栏 X-Y,
   如 2-2)得当前位面,详情内只采当前及之后的位面(之前的跳过,已通过
   节点变暗 ⇒ 详情条识别退化是正常态,重采浪费);
2. 详情侧节点条读不出 → **直接**位面级结论记 None 推进,不再经等待门
   间隔重试(第六局接管实证:「切卡动画中」重试等待烧 7s 后才放弃);
3. 用户定值等待:进详情开屏 ~3s;详情内点位面卡切换后 2s 即读;
4. 备战识别失败(起始位面未取得)→ 回退全量采集(保底)。

活跃锁(与 test_cw_plane_p2.py 的 legacy 基线桶分离;该桶随旧核冻结,
本文件锁当前语义)。
"""
import inspect

import pytest

from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_plane_intel,
)

# ==================== 裁剪判据(纯函数) ====================

def test_start_plane_trim_truth_table() -> None:
    """start_plane 裁剪真值表:当前 2-2 ⇒ start_plane=2 ⇒ 位面1跳过、
    位面2/3 采集;start_plane 无真值(None/0)⇒ 全采回退。"""
    decide = cw_screen_plane_intel.decide_plane_skip
    skip, note = decide(1, 2)
    assert skip is True and '跳过' in note
    assert decide(2, 2) == (False, '')      # 当前位面正常采
    assert decide(3, 2) == (False, '')      # 未来位面正常采
    assert decide(1, None) == (False, '')   # 无真值 → 全采回退
    assert decide(1, 0) == (False, '')


def test_start_plane_defaults_to_full_collect() -> None:
    """备战识别失败回退:构造参数缺省 start_plane=0(未知)→ 判据不跳。"""
    op = cw_screen_plane_intel.CwScreenPlaneIntel.__new__(
        cw_screen_plane_intel.CwScreenPlaneIntel)
    cw_screen_plane_intel.CwScreenPlaneIntel.__init__(op, ctx=None)
    assert op._start_plane == 0, '缺省应未知(0),全采回退'
    assert cw_screen_plane_intel.decide_plane_skip(1, op._start_plane or None)[0] is False


# ==================== 详情侧不重试(变暗=正常态) ====================

def test_detail_unreadable_concludes_without_gate_retry() -> None:
    """采集循环的「节点条读不出」路径直接进位面级结论,不经等待门:
    ①源码含直接结论调用;②不再有 conclude_plane 门参数(重试等待已删);
    ③理由声明变暗为正常态(防后人把它当识别 bug 误修)。"""
    src = inspect.getsource(cw_screen_plane_intel.CwScreenPlaneIntel.collect)
    assert '_conclude_plane_unreadable(' in src, (
        '采集循环读不出应直接位面级结论')
    assert src.count('_nonclean_read_gate') == 1, (
        '采集节点内等待门只允许备战入口一处(详情侧读不出不得再间隔重试;'
        '2026-09-03 裁决)')
    assert '变暗' in src and '正常态' in src, (
        '读不出分支应声明「已通过节点变暗=正常态」根因')
    sig = inspect.signature(cw_screen_plane_intel.CwScreenPlaneIntel._nonclean_read_gate)
    assert 'conclude_plane' not in sig.parameters, (
        '等待门不应再承载详情侧结论分流(仅备战入口路径)')


# ==================== 用户定值等待 ====================

def test_user_fixed_waits() -> None:
    """用户定值:进详情开屏 ~3s、详情内切位面卡后 2s;且确实接在两次点击后。"""
    assert cw_screen_plane_intel._DETAIL_OPEN_WAIT_S == 3.0
    assert cw_screen_plane_intel._PLANE_SWITCH_WAIT_S == 2.0
    src = inspect.getsource(cw_screen_plane_intel.CwScreenPlaneIntel.collect)
    assert 'time.sleep(_DETAIL_OPEN_WAIT_S)' in src, '开屏等待未接 3s 定值'
    assert 'time.sleep(_PLANE_SWITCH_WAIT_S)' in src, '切卡等待未接 2s 定值'


# ==================== 接管链接线(时序反过来) ====================

def test_takeover_chain_passes_start_plane() -> None:
    """接管链两入口(cw_loop 备战环接管补采 / 独立接管补采 op)都在进详情
    之前现读当前位面并以 start_plane 传入采集 op。"""
    from sr_od.application.currency_war.operations.cw_entry import cw_entry_plane_intel
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep

    prep_src = inspect.getsource(cw_screen_prep)
    assert 'start_plane=_start_plane' in prep_src, (
        'cw_loop 接管补采未传 start_plane')
    assert prep_src.index('read_phase_round') < prep_src.index('start_plane=_start_plane'), (
        '接管链应先备战帧现读当前位面,再委派采集(时序反过来)')
    entry_src = inspect.getsource(cw_entry_plane_intel.CwEntryPlaneIntel)
    assert 'start_plane=_start_plane' in entry_src, (
        '独立接管补采入口未传 start_plane')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
