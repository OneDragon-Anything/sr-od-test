"""武装箱选卡臂锁(第十八局停场修复,g_20260905_175220 备战 2-2):
武装箱选择对话框在场(OpenBox 已开箱)⇒ 决策面发射 PickBoxCard 补闭环。

病灶证据 = 档案行动流 OpenBox/ClickSpheres 空转 15 分钟(OpenBox 的
弹窗轮询见既有对话框恒真,重开即假成功);根因 = 决策面无
box_overlay_open → PickBoxCard 发射臂(执行器/期望态投影/适配器均在库,
独缺发射位)。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PickBoxCard,
    PrepObservation,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry


def _obs(box_overlay_open: bool, boxes=()) -> PrepObservation:
    return PrepObservation(
        box_overlay_open=box_overlay_open,
        boxes=list(boxes),
        state=None)


def _run(obs):
    sess = SimpleNamespace(cw4_counters={})
    out = entry.emit(obs, SimpleNamespace(), sess, None)
    return out, sess


def test_box_overlay_open_emits_pick_box_card():
    """箱对话框在场 ⇒ 首发射 = PickBoxCard(选卡闭环臂,非 OpenBox 重开)。"""
    out, _sess = _run(_obs(box_overlay_open=True))
    assert out and isinstance(out[0].action, PickBoxCard)
    assert out[0].reason == 'prep_box_pick'


def test_box_overlay_open_suppresses_reopen():
    """对话框在场帧不得再发 OpenBox(重开空转 = 15 分钟滞留根因)。"""
    out, _sess = _run(_obs(box_overlay_open=True,
                           boxes=((1, SimpleNamespace(x=100, y=900)),)))
    assert not any(type(e.action).__name__ == 'OpenBox' for e in out)


def test_box_on_bench_still_emits_open_box_when_overlay_closed():
    """对照:对话框未开 ∧ bench 有箱 ⇒ 照常 OpenBox(既有臂零回退)。"""
    out, _sess = _run(_obs(box_overlay_open=False,
                           boxes=((1, SimpleNamespace(x=100, y=900)),)))
    assert out and type(out[0].action).__name__ == 'OpenBox'
