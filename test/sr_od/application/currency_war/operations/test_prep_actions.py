"""CW 备战执行器动作回执受阻码测试(prep_actions.py 统一口镜像)。

被测 = ``PrepActionExecutor._note_action_receipt`` 统一口的 reason 码化
(纯动作事实契约,词表暂住 kernel ``note_action_receipt`` docstring 与
``prep_actions._PREP_RECEIPT_BLOCK_CODES`` 闭集映射表):
round 结果成功态 = ``''``;round_fail = status 经闭集映射取受阻码——
``not_emitted:*``(点击前失败,动作没发出)/ ``no_effect:*``(点后未生效,
动作已发出但点击序列未完成;StartBattle 弹窗收尾段 = 唯一现役形态,
已登记例外类 = flow/action_ops.md §2.3)。

驱动 = 真 executor + 真 kernel 写路径(容器供给口不桩,session 冷建),
出战 op 的宿主替身/area_center 按剧本应答(先例 =
operations/cw_op/test_prep_action_ops.py 出战段桩形);零真实 IO。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from test.harness.fixture_controller import fast_sleep

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_obs_core import SCREEN_NAME
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionStartBattleParam,
)

#: 识别命中表的键 = (画面名, area 名)(op 桩 round_by_find_area 判定面)。
_HIT_BTN = ('货币战争-备战', '按钮-出战')
_HIT_NOTFULL = ('货币战争-未达上限警告', '标识-未达上限警告')

#: area_center 桩返回表:**只含主按钮**——弹窗收尾两 area(勾选/确认)
#: 刻意缺席 = 「点后未生效」受阻形态的可达构造(主点击已发,收尾点击
#: 定位缺失)。
_SB_AREA_POINTS = {
    ('货币战争-备战', '按钮-出战'): Point(100, 200),
    ('货币战争-备战-开商店', '按钮-出战'): Point(100, 200),
}


class _RecordingController:
    def __init__(self) -> None:
        self.moves: list[Point] = []
        self.clicks: list[Point] = []

    def mouse_move(self, p: Point) -> None:
        self.moves.append(p)

    def click(self, p: Point) -> None:
        self.clicks.append(p)


class _NoSleepTime:
    """模块内 ``time`` 替身:固定等待记录不真睡(真机等待节奏非本测试辖面)。"""

    def __init__(self) -> None:
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.skipped.append(seconds)


def _sb_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    """出战 op 模块桩:area_center 按缺席表应答 + 模块内 ``time`` 替身
    (POST_CLICK_WAIT 弹窗渲染窗空等;screen_info 坐标解析非本测试面)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_start_battle_action as _sba,
    )
    monkeypatch.setattr(
        _sba, 'area_center',
        lambda ctx, name, screen_name=_sba.SCREEN_NAME:
        _SB_AREA_POINTS.get((screen_name, name)))
    monkeypatch.setattr(_sba, 'time', _NoSleepTime())


def _sb_stub_op(hits: set[tuple[str, str]]):
    """op 桩:screenshot 恒同帧对象,round_by_find_area 按命中表演。"""

    def _find(_screen, screen_name: str, area_name: str, **_kw):
        return SimpleNamespace(is_success=(screen_name, area_name) in hits)

    return SimpleNamespace(screenshot=lambda: object(),
                           round_by_find_area=_find,
                           save_screenshot=lambda prefix='': 'stub.png')


def _sb_executor(controller: _RecordingController, stub_op,
                 cw_match=None):
    """执行器桩宿主(真 executor 容纳回执统一口与 last_launch_ok 旁路)。"""
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor
    ctx = SimpleNamespace(controller=controller, cw_match=cw_match,
                          run_context=None,
                          screen_loader=SimpleNamespace(
                              get_screen=lambda name: None))
    return PrepActionExecutor(stub_op, ctx)


def test_receipt_not_emitted_code_on_button_miss(monkeypatch):
    """点击前失败 → not_emitted:*:两屏查空找不到按钮 = 动作没发出
    (零点击)→ 回执 reason=not_emitted:定位缺失(按钮-出战),detail =
    round_fail status 原文(机械摘要恒透传)。"""
    _sb_patch(monkeypatch)
    sess = SimpleNamespace()
    ctl = _RecordingController()
    ex = _sb_executor(ctl, _sb_stub_op(set()),
                      cw_match=SimpleNamespace(session=sess))

    with fast_sleep():
        ex.execute(CwActionStartBattleParam())

    assert ctl.clicks == [], '点击前失败 = 零点击(动作没发出)'
    assert game_state_of(sess).receipts.value == [{
        'op': 'CwActionStartBattleParam',
        'reason': 'not_emitted:定位缺失(按钮-出战)',
        'detail': '未执行:找不到按钮',
        'screen': SCREEN_NAME,
    }]


def test_receipt_no_effect_code_on_postclick_popup_miss(monkeypatch):
    """点后未生效 → no_effect:*(StartBattle 已登记例外类):主点击已发
    (点击记录在册)后弹窗收尾定位缺失 → round_fail,回执 reason=
    no_effect:弹窗确认未执行(未达上限警告)——点了 ≠ 没点,分族事实码
    不说谎。"""
    _sb_patch(monkeypatch)
    sess = SimpleNamespace()
    ctl = _RecordingController()
    ex = _sb_executor(ctl, _sb_stub_op({_HIT_BTN, _HIT_NOTFULL}),
                      cw_match=SimpleNamespace(session=sess))

    with fast_sleep():
        ex.execute(CwActionStartBattleParam())

    assert len(ctl.clicks) == 1, '主点击已发出(no_effect 族前提:点了)'
    assert game_state_of(sess).receipts.value == [{
        'op': 'CwActionStartBattleParam',
        'reason': 'no_effect:弹窗确认未执行(未达上限警告)',
        'detail': ('area 缺失:勾选-本局不再提示'
                   '(货币战争-未达上限警告),禁兜底坐标'),
        'screen': SCREEN_NAME,
    }]


def test_receipt_success_reason_empty_and_invariant(monkeypatch):
    """已发出 = reason='':round_success 出口回执零受阻码;invariant
    「每动作 op 恰一条回执行」(单动作恰一行);last_launch_ok 旁路
    显式保留(锁定恢复局守卫消费面,不受 reason 码化影响)。"""
    _sb_patch(monkeypatch)
    sess = SimpleNamespace()
    ex = _sb_executor(_RecordingController(), _sb_stub_op({_HIT_BTN}),
                      cw_match=SimpleNamespace(session=sess))

    with fast_sleep():
        ex.execute(CwActionStartBattleParam())

    gs = game_state_of(sess)
    assert len(gs.receipts.value) == 1, 'invariant:每动作 op 恰一条回执行'
    rec = gs.receipts.value[0]
    assert rec['op'] == 'CwActionStartBattleParam'
    assert rec['reason'] == '', '已发出出口 = 零受阻码'
    assert ex.last_launch_ok is True, 'last_launch_ok 旁路保留(发送事实)'
