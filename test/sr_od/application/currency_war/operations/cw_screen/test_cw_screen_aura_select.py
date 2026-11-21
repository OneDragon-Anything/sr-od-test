"""主角光环选择 op 剧本集(CwScreenAuraSelect;迭代 2026-11-20-cw-p0-chain
tasks 3.4,design §2.3 op4):

- 剧本 1 = 三步链成功:标准化门(report 落 aura_select_opts 标准名)→
  preview_xy 零参读拖拽源(idx 0)→ CwSelectProtagonist 三步链(点卡/
  拖拽/微距确认)→ 判效双锚过(回备战)→ success;拖拽源坐标断言;
- 剧本 2 = 换抓点重试链:判效恒 miss → 状态词边回动作换抓点(同卡
  换点 → 跨卡下一候选)→ VERIFY_RETRY_MAX 耗尽 fail;拖拽起点序列
  断言(换抓点语义,r6 低-3 申报);
- 纯函数 = 标准化门两段转换(注册表精确 / lcs 相似 / 转换失败 '')。

帧资产 = 光环屏归档帧(205441:富翁的梦泡/闪耀蓝星双卡);备战帧 =
现役存档。CwSelectProtagonist 原样消费(点卡点击推进帧序列,拖拽/
微距走 mock 记录)。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.cw_fixture_controller import CwFixtureController
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_aura_select import (
    CwScreenAuraSelect,
)

_AURA: str = '货币战争-主角光环选择'
#: 光环屏归档帧(左=富翁的梦泡,右=闪耀蓝星;预览卡前排 4 后排 6)。
_F_AURA: tuple[str, str] = (_AURA, 'default')
#: 备战帧(判效双锚的目标帧)。
_F_PREP: tuple[str, str] = ('货币战争-备战', 'deployed_2star')


def _require_frames(test_context: SrTestContext) -> None:
    for screen_name, state in (_F_AURA, _F_PREP):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _attach_gs(test_context: SrTestContext,
               monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    match = SimpleNamespace(session=SimpleNamespace(), gs=None)
    monkeypatch.setattr(test_context, 'cw_match', match)
    return match


def _run_op(test_context: SrTestContext, op: CwScreenAuraSelect):
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def test_three_step_chain_reports_then_grabs_idx0_and_verifies(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 1 三步链成功:标准化 report → idx 0 拖拽源 → 三步链 →
    判效双锚过交回。"""
    _require_frames(test_context)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        # 光环屏帧:CwSelectProtagonist 点卡(卡-左光环 area 内)推进到备战帧
        {'frame': _F_AURA,
         'exit': ('on_click_in', _AURA, '卡-左光环')},
        {'frame': _F_PREP},
    ])
    op = CwScreenAuraSelect(test_context)
    result = _run_op(test_context, op)

    assert result.success, f'三步链成功应 success,实际 {result.status!r}'
    # —— report:标准化标准名 + 中心/拖拽源伴随域
    gs = game_state_of(test_context.cw_match.session)
    assert list(gs.aura_select_opts.value or []) == ['富翁的梦泡', '闪耀蓝星'], \
        (f'光环名应标准化后写入,实际 '
         f'{gs.aura_select_opts.value!r}')
    centers = list(gs.aura_select_opts_xy.value or [])
    assert len(centers) == 2, f'光环卡中心应固定二槽,实际 {centers!r}'
    preview = list(gs.aura_select_preview_xy.value or [])
    assert len(preview) == (CwScreenAuraSelect.FRONT_SLOTS
                            + CwScreenAuraSelect.BACK_SLOTS), \
        f'预览产点应 10 槽行主序,实际 {preview!r}'
    # —— 选择落地记账:判效双锚过后按末次抓点槽写 aura_slot(首发
    #    idx 0 = 前排槽 1;与备战帧光标观察同字段同语义)
    assert gs.aura_slot.value == 1, \
        f'判效过后 aura_slot 应按首发抓点落前排槽 1,实际 {gs.aura_slot.value!r}'
    assert gs.aura_slot.source == 'logic', \
        f'选择记账应为逻辑态,实际 {gs.aura_slot.source!r}'
    # —— 拖拽源 = preview_xy[0] 零参读(v1 固定前排第一)
    assert len(ctrl.recorded_drags) >= 1, \
        f'三步链应含拖拽,实际 {ctrl.recorded_drags}'
    grab = ctrl.recorded_drags[0][0]
    assert grab == (preview[0][0], preview[0][1]), \
        (f'拖拽源应 = aura_select_preview_xy[0]({preview[0]}),'
         f'实际 {grab}')
    # 微距确认拖拽存在(胶囊按钮,静态点击免疫)
    assert len(ctrl.recorded_drags) >= 2, \
        f'三步链应含微距确认拖拽,实际 {ctrl.recorded_drags}'


def test_verify_miss_retries_grab_points_then_fails(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 2 换抓点重试链:判效恒 miss → 回动作换抓点(首发 idx0 →
    同卡换点 +ALT_OFFSET → 跨卡 idx 递进)→ 超限 fail;拖拽起点序列
    断言换抓点语义。"""
    _require_frames(test_context)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([{'frame': _F_AURA}])   # 无 exit:判效恒 miss
    op = CwScreenAuraSelect(test_context)
    result = _run_op(test_context, op)

    assert not result.success, \
        f'判效恒 miss 应 fail 交外环,实际 {result.status!r}'
    gs = game_state_of(test_context.cw_match.session)
    # 判效未过 = 选择未落地 → aura_slot 零写(记账闸在判效成功分支)
    assert gs.aura_slot.value is None, \
        f'判效恒 miss fail 路径不应写 aura_slot,实际 {gs.aura_slot.value!r}'
    preview = list(gs.aura_select_preview_xy.value or [])
    # 每次尝试的首次拖拽起点序列(每次三步链 2 次拖拽,取偶数位)
    grabs = [d[0] for d in ctrl.recorded_drags[::2]]
    expected = [
        (preview[0][0], preview[0][1]),                      # 首发 idx 0
        (preview[0][0] + CwScreenAuraSelect.GRAB_ALT_OFFSET,
         preview[0][1]),                                     # 同卡换点
        (preview[1][0], preview[1][1]),                      # 跨卡 idx 1
        (preview[2][0], preview[2][1]),                      # 跨卡 idx 2
    ]
    assert len(grabs) == CwScreenAuraSelect.VERIFY_RETRY_MAX + 1, \
        (f'尝试次数应 = 首发 + 重试上限,实际 {len(grabs)} 次')
    assert grabs == expected, \
        f'换抓点序列不符(首发/同卡换点/跨卡递进),实际 {grabs!r}'


def test_normalize_gate_two_stage_conversion() -> None:
    """纯函数:标准化门两段转换——精确命中 / 形变 lcs 相似命中 /
    注册表外转换失败 ''(禁带病上报);两槽独立解析重复名不判失败
    (r6 低-4 边界)。"""
    op = CwScreenAuraSelect.__new__(CwScreenAuraSelect)
    # 精确命中(注册表在册名)
    assert op._normalize_aura_name('富翁的梦泡') == '富翁的梦泡'
    assert op._normalize_aura_name('闪耀蓝星') == '闪耀蓝星'
    # 形变归一(空白剥离)后精确命中
    assert op._normalize_aura_name(' 富翁的梦泡 ') == '富翁的梦泡'
    # 形变 lcs 相似(单字误读,4 字名 3/4 = 0.75 过阈)
    assert op._normalize_aura_name('富翁的梦' ) in ('富翁的梦泡', ''), \
        '单字缺损应走 lcs 门(命中或拒判,禁野值)'
    # 注册表外 = 转换失败(观察失败早退语义)
    assert op._normalize_aura_name('完全不存在的光环名') == ''
    assert op._normalize_aura_name('') == ''
