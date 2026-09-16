"""统一观察对账安灯·装配闭包锁(迭代 2026-09-16-unified-obs-reconcile §2.4;
落地判据 = landing.md §3.3)。

闭包工厂 = currency_war_app._build_reconcile_andon(模块级,ctx/闩/flag 路径
全参数注入);kernel 槽缺省关的零副作用面由 test_cw_mismatch_policy.py 锁,
本文件只锁生产闭包行为面。零真实 IO:截图与落盘均桩,flag 落 tmp_path。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pytest

from sr_od.application.currency_war import currency_war_app as app_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    set_run_id_provider,
)
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    fire_reconcile_andon,
    set_reconcile_andon_hook,
)

_ROW = {'ts': '2026-09-16T12:00:00', 'field': 'gold', 'expected': 17,
        'actual': 19, 'observed_evidence': None, 'screen': '货币战争-备战',
        'actor': 'cw_observation', 'group_id': None,
        'logic_evidence': 'proj_sell_refund'}
#: 真实帧形态(controller 契约 MatLike;B1 回归锚 = 帧本体直传 save)
_FRAME = np.zeros((2, 2, 3), dtype='uint8')


class _Rc:
    """run_context 桩:记录 stop 调用。"""

    def __init__(self) -> None:
        self.stops: list[str] = []

    def stop_running(self, reason: str) -> None:
        self.stops.append(reason)


def _make_ctx():
    """controller 桩 = 真实契约形态:返回 (ts, MatLike|None) 元组
    (controller_base.screenshot 契约;B1 教训:桩返回裸帧/字符串会掩盖
    「元组整传 save」的契约错位)。"""
    rc = _Rc()
    calls: list[int] = []
    controller = SimpleNamespace(
        screenshot=lambda independent=False:
            (calls.append(1), time.time(), _FRAME)[1:])
    return SimpleNamespace(controller=controller,
                           run_context=rc), rc, calls


@pytest.fixture()
def andon_env(tmp_path, monkeypatch):
    """安灯环境:run_id 供给注入 + 截图落盘桩(记录帧本体与前缀)+
    flag 路径指 tmp。"""
    saved_imgs: list = []
    saved_prefixes: list[str] = []

    def _fake_save(image, file_name=None, prefix='', copy_screenshot=False):
        saved_imgs.append(image)
        saved_prefixes.append(prefix)
        return 'img'

    monkeypatch.setattr(app_mod, 'save_debug_image', _fake_save)
    ctx, rc, calls = _make_ctx()
    flag_path = tmp_path / 'cw_reconcile_andon.flag'
    latch: dict[str, bool] = {}
    closure = app_mod._build_reconcile_andon(ctx, latch, flag_path)
    set_reconcile_andon_hook(closure)
    try:
        yield closure, rc, calls, saved_imgs, saved_prefixes, flag_path, latch
    finally:
        set_reconcile_andon_hook(None)


def test_andon_true_mismatch_writes_flag_and_stops_once(
        andon_env, monkeypatch) -> None:
    """真失配:flag 落盘含三要素(HOOK-STOP 定位/处理步骤/移除条件)+
    stop 恰一次(reason=hook:reconcile_mismatch)+ 截图留证(帧本体直传
    save,前缀含 run_id 与字段;B1 回归锚 = 元组整传即此处红)。"""
    closure, rc, calls, saved_imgs, saved_prefixes, flag_path, _latch = \
        andon_env
    set_run_id_provider(lambda: 'run_t1')
    try:
        fire_reconcile_andon(dict(_ROW))
    finally:
        set_run_id_provider(None)
    assert flag_path.exists(), '停机 flag 落盘(主哨兵)'
    content = flag_path.read_text(encoding='utf-8')
    assert '[HOOK-STOP]' in content and '处理步骤' in content \
        and '移除条件' in content, 'flag 三要素齐'
    assert 'run_id=run_t1' in content and '字段=gold' in content \
        and '逻辑写端=proj_sell_refund' in content \
        and '逻辑值(expected)=17' in content and '实读(actual)=19' in content, \
        '触发定位带失配行全维度(画面/actor/写端/两值)'
    assert rc.stops == ['hook:reconcile_mismatch'], '停机恰一次'
    assert saved_imgs and saved_imgs[0] is _FRAME, \
        '帧本体直传 save(元组整传 = B1 契约错位回归)'
    assert saved_prefixes == ['reconcile_andon_run_t1_gold'], \
        '截图留证前缀含 run_id 与字段'


def test_andon_same_run_second_mismatch_latched(andon_env) -> None:
    """每局一闩:同 run_id 第二失配被跳过(flag/stop 不重复)。"""
    closure, rc, _calls, _imgs, _prefixes, flag_path, latch = andon_env
    set_run_id_provider(lambda: 'run_t1')
    try:
        fire_reconcile_andon(dict(_ROW))
        mtime = flag_path.read_text(encoding='utf-8')
        fire_reconcile_andon(dict(_ROW))
    finally:
        set_run_id_provider(None)
    assert rc.stops == ['hook:reconcile_mismatch'], '第二失配被闩,不重复停机'
    assert flag_path.read_text(encoding='utf-8') == mtime, 'flag 不重写'
    assert latch == {'run_t1': True}


def test_andon_out_of_match_evidence_only_no_stop(
        andon_env, monkeypatch) -> None:
    """run_id 空(局外):只落证不停机、不写假局 flag(与 journal 局外
    拒写假行同向)。"""
    closure, rc, _calls, imgs, _prefixes, flag_path, _latch = andon_env
    set_run_id_provider(lambda: '')
    try:
        fire_reconcile_andon(dict(_ROW))
    finally:
        set_run_id_provider(None)
    assert rc.stops == [], '局外不停机'
    assert not flag_path.exists(), '局外不写假局 flag'
    assert len(imgs) == 1, '局外仍落证(截图)'


def test_andon_screenshot_failure_does_not_block_flag_or_stop(
        andon_env, monkeypatch) -> None:
    """截图失败两形态(controller 炸 / 落盘返回空串)都不拦 flag 与停机
    (flag 是主哨兵,先例 = exec_fail 安灯截图策略)。"""
    closure, rc, _calls, _imgs, _prefixes, flag_path, _latch = andon_env

    def _boom():
        raise RuntimeError('截图炸了')

    monkeypatch.setattr(app_mod, 'save_debug_image',
                        lambda image, file_name=None, prefix='',
                        copy_screenshot=False: '')
    ctx_boom = SimpleNamespace(
        controller=SimpleNamespace(screenshot=_boom), run_context=rc)
    closure2 = app_mod._build_reconcile_andon(
        ctx_boom, {}, flag_path.parent / 'flag2')
    set_reconcile_andon_hook(closure2)
    try:
        set_run_id_provider(lambda: 'run_t2')
        try:
            fire_reconcile_andon(dict(_ROW))
        finally:
            set_run_id_provider(None)
        assert flag_path.parent.joinpath('flag2').exists(), \
            '截图炸:flag 照落'
        assert rc.stops == ['hook:reconcile_mismatch'], '截图炸:停机照常'
    finally:
        set_reconcile_andon_hook(None)
