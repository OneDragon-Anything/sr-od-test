"""N5 稳定性形态锁:同投资策略浮层两时序形态(首帧命中/淡入期复探命中)
同判据同路由(分发层根修 `_invest_overlay_dispatch`,行为驱动真 loop())。

与消费点防御分层声明:达标臂浮层排除/遭遇 OCR/test_cw_p1_spend_face 的
readiness 锁族管「路由误判后的发射兜底」,本文件管「路由本身稳定」,
两文件禁合并谓词(分层见 _invest_overlay_dispatch docstring)。
"""

from types import SimpleNamespace as _NS


class _Hit:
    is_success = True


class _Miss:
    is_success = False


def _make_op(invest_find_hits_from: int, ocr_hits_from: int = 10 ** 9):
    """分发判据桩 op:find/ocr 逐调用计数——invest_anchor 从第
    `invest_find_hits_from` 次 find 调用起命中(时序形态建模:0 = 首帧
    命中,1 = 淡入期第二次探测才命中);OCR「请选择投资策略」同理。"""
    calls = {'find': 0, 'ocr': 0, 'shots': 0, 'invest_executes': 0}

    class _Res:
        def __init__(self, ok: bool):
            self.is_success = ok

    class _Op:
        INVEST_REPROBE_WAIT = 0.0   # 测试零等待

        def screenshot(self):
            calls['shots'] += 1
            return ('shot', calls['shots'])

        def round_by_find_area(self, screen, s1, s2, **kw):
            calls['find'] += 1
            if s1 == '货币战争-投资策略' and s2 == '标识-请选择投资策略':
                return _Res(calls['find'] >= invest_find_hits_from)
            if s1 == '货币战争-备战' and s2 in ('备战标识-购买经验',
                                                '按钮-出战'):
                return _Res(getattr(self, 'prep_hits', True))   # 双锚穿透形态
            return _Res(False)

        def round_by_ocr(self, screen, target_cn=None, **kw):
            calls['ocr'] += 1
            if target_cn == '请选择投资策略':
                return _Res(calls['ocr'] >= ocr_hits_from)
            return _Res(False)

    op = _Op()
    op.calls = calls
    op.prep_hits = True   # 默认双锚穿透形态(浮层盖备战);no-overlay 锁改 False
    sess = _NS(target_comp=None, last_state=None, cw4_counters={})
    op.ctx = _NS(cw_match=_NS(session=sess))
    return op, sess, calls


def _patch_handler(monkeypatch):
    from sr_od.application.currency_war.operations import cw_loop
    executes: list[int] = []

    class _FakeHandler:
        def __init__(self, ctx):
            pass

        def execute(self):
            executes.append(1)
            return None

    monkeypatch.setattr(cw_loop, 'CwScreenInvestStrategy', _FakeHandler)
    return executes


def test_first_frame_hit_routes_to_handler(monkeypatch):
    """形态一(15:52 正确形态回归锚):首帧 id_mark 锚命中 → 即刻分发
    CwScreenInvestStrategy(现行正确行为,零回退)。"""
    from sr_od.application.currency_war.operations.cw_loop import (
        _invest_overlay_dispatch,
    )
    op, _sess, calls = _make_op(invest_find_hits_from=1)
    dispatch, _screen = _invest_overlay_dispatch(op, ('shot', 0))
    assert dispatch is True
    assert calls['invest_executes'] == 0   # 分发判定与 handler 执行解耦


def test_fadein_reprobe_routes_same_handler(monkeypatch):
    """形态二(15:14 病根形态):首探测 miss(id_mark+OCR 均淡入未采到)
    ∧ 备战双锚穿透命中 → 短窗复探(新截图)OCR 命中 → **同判据同路由**
    dispatch=True——两时序形态不再翻转。"""
    from sr_od.application.currency_war.operations.cw_loop import (
        _invest_overlay_dispatch,
    )
    # find 首探 miss、复探(第 2 次 find)命中;OCR 全程 miss = 纯锚复探形态
    op, _sess, calls = _make_op(invest_find_hits_from=2)
    dispatch, _screen = _invest_overlay_dispatch(op, ('shot', 0))
    assert dispatch is True, '淡入期复探命中须与首帧命中同路由'
    assert calls['find'] >= 3, '复探确实发生(双锚对拍+复探)'

    # OCR 信号形态:find 全程 miss、OCR 第二次探测命中 → 同样 dispatch
    op2, _s2, calls2 = _make_op(invest_find_hits_from=10 ** 9,
                                ocr_hits_from=2)
    dispatch2, _ = _invest_overlay_dispatch(op2, ('shot', 0))
    assert dispatch2 is True, 'OCR 信号复探命中同路由'


def test_no_overlay_no_dispatch():
    """对照:浮层不在场(全 miss)→ 不分发(落备战链),且不空转复探
    ——备战双锚未命中时不进复探窗。"""
    from sr_od.application.currency_war.operations.cw_loop import (
        _invest_overlay_dispatch,
    )
    op, _sess, calls = _make_op(invest_find_hits_from=10 ** 9,
                                ocr_hits_from=10 ** 9)
    op.prep_hits = False   # 双锚未命中(常规非备战帧):不进复探窗
    dispatch, _screen = _invest_overlay_dispatch(op, ('shot', 0))
    assert dispatch is False
    assert calls['shots'] == 0, '双锚未命中不进复探窗(常规帧零行为差)'


def test_loop_routes_both_timing_forms_to_handler(monkeypatch):
    """路由锁(行为面):真 CwLoop.loop() 驱动——两时序形态最终都执行
    CwScreenInvestStrategy(同路由),处理 monkeypatch 单一源。"""
    from sr_od.application.currency_war.operations import cw_loop
    executes = _patch_handler(monkeypatch)

    class _Res:
        def __init__(self, ok: bool):
            self.is_success = ok

    class _Loop(cw_loop.CwLoop):
        _iter = 2
        _is_new_match = False
        _cw_locked_resume = False
        _cw_back_btn_count = 0
        _battle_ts = None
        INVEST_REPROBE_WAIT = 0.0

        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            pass

        @property
        def last_screenshot(self):
            return self._screen

        @last_screenshot.setter
        def last_screenshot(self, v):
            pass

        def _stall_watch_tick(self, screen):
            pass

        def screenshot(self):
            return self._screen

        def round_by_find_area(self, screen, s1, s2, **kw):
            # 时序建模:投资策略锚从第 2 次 find 调用起命中(淡入形态);
            # 其余锚恒 miss;备战双锚恒命中(穿透形态)。
            calls['find'] += 1
            if s1 == '货币战争-投资策略' and s2 == '标识-请选择投资策略':
                return _Res(calls['find'] >= 2)
            if s1 == '货币战争-备战' and s2 in ('备战标识-购买经验',
                                                '按钮-出战'):
                return _Res(True)
            return _Res(False)

        def round_by_ocr(self, *a, **kw):
            return _Res(False)

        def round_by_ocr_and_click(self, *a, **kw):
            return _Res(False)

        def round_by_find(self, *a, **kw):
            return _Res(False)

        def round_by_find_and_click_area(self, *a, **kw):
            return _Res(False)

        def round_wait(self, wait=1.0, status=''):
            return ('wait', status)

    calls = {'find': 0}
    op = _Loop()
    op._screen = object()
    op.ctx = _NS(cw_match=_NS(session=_NS(
        target_comp=None, last_state=None,
        last_prep_action_sig=None, cw4_counters={})))
    op.loop()
    assert executes, '淡入形态须经复探同路由分发 CwScreenInvestStrategy'

    # 形态一:首帧命中同路由
    calls2 = {'find': 0}

    class _Loop2(_Loop):
        def round_by_find_area(self, screen, s1, s2, **kw):
            calls2['find'] += 1
            if s1 == '货币战争-投资策略' and s2 == '标识-请选择投资策略':
                return _Res(True)   # 首帧命中
            if s1 == '货币战争-备战' and s2 in ('备战标识-购买经验',
                                                '按钮-出战'):
                return _Res(True)
            return _Res(False)

    executes.clear()
    op2 = _Loop2()
    op2._screen = object()
    op2._iter = 2
    op2._is_new_match = False
    op2._cw_locked_resume = False
    op2._cw_back_btn_count = 0
    op2._battle_ts = None
    op2.ctx = _NS(cw_match=_NS(session=_NS(
        target_comp=None, last_state=None,
        last_prep_action_sig=None, cw4_counters={})))
    op2.loop()
    assert executes, '首帧命中形态同路由分发'
