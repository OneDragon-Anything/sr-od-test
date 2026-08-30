"""W849 bug#1 drag 落空根治批:补救链可靠性锁 + 593-596 语义锁。

病灶:replay/defect_ledger.jsonl drag 条目 6/6「retry 仍败」——原地 retry 与首拖
共用同一帧坐标/同一时序,失败相关(非独立事件),「retry 一次」缓解失效。
根治三件:①拖前稳帧确认 `_wait_stable_frame`;②落空补救链 `_wear_with_recovery`
(坐标现读重定位 + 按压/移动参数逐档升级);③equip_all 主循环「槽位坐标缺失」
分支 break→continue 语义修正(原日志说跳过该角色、行为却中断整轮)。

测试全部零真实副作用:截图/控制器/park 光标均实例级桩化。
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.operations.prep import equip_all as ea_mod
from sr_od.application.currency_war.operations.prep.equip_all import EquipAll

_EQUIP_ALL_PATH = (Path(ea_mod.__file__).parent / 'equip_all.py').resolve()


def _mk_op() -> EquipAll:
    """最小 EquipAll(不碰真实截图/控制器;测试只调被测方法)。"""
    return EquipAll.__new__(EquipAll)   # 跳过 SrOperation.__init__(免 OpenAndEnterGame 依赖)


_Frame = np.zeros((100, 100, 3), dtype=np.uint8)


# ===== 件1:拖前稳帧确认 =====

def test_stable_frame_returns_after_settle(monkeypatch) -> None:
    """首帧动画帧 + 后续静止帧 → 返回静止帧(两帧差 < 阈值即收)。"""
    op = _mk_op()
    moving = _Frame.copy()
    moving[40:60, 40:60] = 255
    static = _Frame.copy()
    frames = iter([moving, static, static])
    monkeypatch.setattr(op, 'screenshot', lambda: next(frames))
    got = op._wait_stable_frame(interval=0.0, budget_s=1.0)
    assert (got == static).all(), '稳帧确认应返回静止帧'


def test_stable_frame_gives_up_within_budget(monkeypatch) -> None:
    """预算内始终不稳(持续动画)→ 放行返回当前帧,不卡死流程。"""
    op = _mk_op()
    flip = {'v': False}

    def _shot():
        flip['v'] = not flip['v']
        f = _Frame.copy()
        if flip['v']:
            f[0:20, :] = 255
        return f

    monkeypatch.setattr(op, 'screenshot', _shot)
    got = op._wait_stable_frame(interval=0.0, budget_s=0.05)
    assert got is not None, '预算耗尽必须放行返回帧(不抛/不卡死)'


# ===== 件2:补救链可靠性锁(模拟落空 → 补救链生效)=====

class _DragRecorder:
    """桩 _drag_equip:按剧本返回落空/穿上,记录每次调用的坐标与参数。"""

    def __init__(self, script: list[bool]):
        self.script = list(script)
        self.calls: list[dict] = []

    def __call__(self, start, target, verify_y, hold_time, duration):
        self.calls.append({'start': (start.x, start.y),
                           'hold': hold_time, 'dur': duration})
        return self.script.pop(0), 12.0


def test_recovery_chain_recovers_after_misses(monkeypatch) -> None:
    """核心锁:前两拖落空(模拟 bug#1)→ 补救链第 3 档穿上;
    每次重试前 relocate 现读坐标、参数逐档升级(非原地同参)。"""
    op = _mk_op()
    rec = _DragRecorder([False, False, True])
    monkeypatch.setattr(op, '_drag_equip', rec)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    relocates: list[int] = []

    def _relocate() -> Point | None:
        relocates.append(len(relocates))
        return Point(1800, 600)

    landed, _diff = op._wear_with_recovery(Point(1750, 600), Point(743, 350),
                                           479, _relocate)
    assert landed, '补救链应在第 3 档穿上'
    assert [c['hold'] for c in rec.calls] == [
        ea_mod.DRAG_HOLD_TIME, 0.8, 1.1], '按压时长应逐档升级'
    assert [c['dur'] for c in rec.calls] == [
        ea_mod.DRAG_DURATION, 2.0, 2.5], '移动时长应逐档升级'
    assert [c['start'] for c in rec.calls][1:] == [
        (1800, 600), (1800, 600)], '重试应用 relocate 现读坐标(非首读坐标)'
    assert len(relocates) == 2, '每次重试前各 relocate 一次'


def test_recovery_chain_first_try_no_relocate(monkeypatch) -> None:
    """首拖即穿 → 不进补救链(relocate 零调用、单次 drag)。"""
    op = _mk_op()
    rec = _DragRecorder([True])
    monkeypatch.setattr(op, '_drag_equip', rec)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    calls: list[int] = []
    landed, _ = op._wear_with_recovery(Point(1750, 600), Point(743, 350),
                                       479, lambda: calls.append(1) or None)
    assert landed and len(rec.calls) == 1 and calls == [], '首穿不触发补救链'


def test_recovery_chain_aborts_when_item_gone(monkeypatch) -> None:
    """relocate 返 None(件被合成消耗/reflow)→ 立即放弃本件,不再空拖。"""
    op = _mk_op()
    rec = _DragRecorder([False])
    monkeypatch.setattr(op, '_drag_equip', rec)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    landed, _ = op._wear_with_recovery(Point(1750, 600), Point(743, 350),
                                       479, lambda: None)
    assert not landed and len(rec.calls) == 1, '件已不在 owned 应立即放弃(仅 1 次拖)'


def test_recovery_chain_exhausts_to_failure(monkeypatch) -> None:
    """全档仍败 → 返回 False(交主循环停手 + 哨兵归因),恰好 3 次拖不无限空转。"""
    op = _mk_op()
    rec = _DragRecorder([False, False, False])
    monkeypatch.setattr(op, '_drag_equip', rec)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    landed, _ = op._wear_with_recovery(Point(1750, 600), Point(743, 350),
                                       479, lambda: Point(1800, 600))
    assert not landed and len(rec.calls) == 3


# ===== 件3:593-596 语义锁(槽位坐标缺失 = 跳过分配项,非中断整轮)=====

def test_slot_missing_branch_is_skip_not_break() -> None:
    """「槽位坐标缺失」分支:必须 stall 计数 + continue(跳过该分配项),
    不得 break(旧行为:日志说跳过角色、代码却中断整轮穿戴,日志与行为不符)。"""
    src = _EQUIP_ALL_PATH.read_text(encoding='utf-8')
    m = re.search(r'if target_pv is None:\n(.*?)\n(\s+)entry = ', src, re.S)
    assert m is not None, '未定位到槽位坐标缺失分支(结构漂移,重推本锁语义)'
    branch = m.group(1)
    assert 'stall += 1' in branch, '同分配项会反复顶到队首,必须 stall 计数防死循环'
    assert 'continue' in branch, '语义=跳过该分配项继续整轮(593-596 break 修正)'
    assert re.search(r'^\s*break\s*$', branch, re.M) is None, \
        '分支内禁止 break 语句(旧语义:单角色坐标缺失中断整轮)'
