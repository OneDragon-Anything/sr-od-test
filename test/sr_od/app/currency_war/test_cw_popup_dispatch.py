"""T-163 实机弹窗死循环事故修复锁(0t 商店卡牌详情分支 + 1b 锚化 + D5 闸门降级)。

事故(2026-09-08 17:45-18:11):奖励节点点球误触开「商店卡牌详情」弹窗,
全屏 OCR 1b 判据(「角色详情」全等撞车)垄断分发 → 点 X 坐标落面板内零
效果 → 无验效假成功 → ~2.8s/轮 ×26 分钟。方案审放行组合:D1 建档+0t
分支 / D2 1b 锚化 / D3 验效(D3 行为面在 test_cw_progression_ops)/ D4
哨兵去盲(test_cw_stall_watchdog)/ D5 动作 op 内嵌闸门降级执行断言+判断
上提 _run_composite 派发前置(2026-09-08 用户架构裁定:动作 op 机械执行,
「该不该执行」归分发层)。

判定位口径:分发判据走模块级 helper(_shop_card_detail_anchor_hit /
_role_detail_anchor_hit),行为锁直接调 helper(stub op,与
test_cw_shop_open_branch 对 _shop_open_anchors_hit 同手法)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.operations import cw_loop
from sr_od.application.currency_war.operations.cw_loop import (
    _role_detail_anchor_hit,
    _shop_card_detail_anchor_hit,
)


class _Res:
    def __init__(self, ok: bool) -> None:
        self.is_success = ok


def _stub_op(hits: set[tuple[str, str]]):
    """分发判据 stub op:find_area 按 (画面, area) 命中集判定。"""
    return SimpleNamespace(
        round_by_find_area=lambda screen, s1, s2, **kw: _Res(
            (s1, s2) in hits),
    )


# ==================== D1:0t 商店卡牌详情双锚判据 ====================


def test_shop_card_detail_anchor_requires_both_marks() -> None:
    """双锚 AND 语义:两锚全中才接管;单锚形态(其他带购买按钮的弹窗)
    不放行——防误吞同族弹窗。"""
    both = _stub_op({('货币战争-商店卡牌详情', '按钮-购买'),
                     ('货币战争-商店卡牌详情', '按钮-角色详情')})
    assert _shop_card_detail_anchor_hit(both, object()) is True
    only_buy = _stub_op({('货币战争-商店卡牌详情', '按钮-购买')})
    assert _shop_card_detail_anchor_hit(only_buy, object()) is False
    none = _stub_op(set())
    assert _shop_card_detail_anchor_hit(none, object()) is False


# ==================== D2:1b 判据锚化(全屏 OCR 退场) ====================


def test_role_detail_anchor_either_leg() -> None:
    """双锚 OR 语义:装备推荐(角色详情变体)∨ 合成公式(可合成列表变体)
    其一命中即接管——两腿分别成立,与 ADR-0454 定稿锚同源。"""
    rec = _stub_op({('货币战争-备战-角色详情', '按钮-装备推荐')})
    assert _role_detail_anchor_hit(rec, object()) is True
    synth = _stub_op({('货币战争-备战-角色详情', '装备详情-合成公式')})
    assert _role_detail_anchor_hit(synth, object()) is True
    none = _stub_op(set())
    assert _role_detail_anchor_hit(none, object()) is False


def test_role_detail_fullscreen_ocr_retired() -> None:
    """退场锁:旧全屏 OCR 判据(「可合成列表」/「角色详情」,lcs 0.8)不得
    回到 cw_loop 分发——全屏「角色详情」与商店卡牌详情弹窗底部按钮全等共享
    (LCS 1.0,收紧无济于事)= T-163 垄断 26 分钟的判据根。1b 分发走锚化
    判据单一源的在场面由 test_role_detail_dispatch_on_fail_retry_wired
    的分支定位自持(同串断言,不重复)。"""
    src = inspect.getsource(cw_loop)
    assert "round_by_ocr(screen, '角色详情'" not in src, \
        '1b 全屏 OCR 判据回归(T-163 事故判据根)'
    assert "round_by_ocr(screen, '可合成列表'" not in src, \
        '1b 全屏 OCR 判据回归(T-163 事故判据根)'


def test_role_detail_dispatch_on_fail_retry_wired() -> None:
    """F2 传递锁:1b 分发必须带 on_fail_retry=True(对齐 0a2/0a3/0a4/0t)
    ——op 单尝试 fail 经包装映射 loop 级 round_retry 消费 retry 池;
    缺失 = round_fail 零预算重派,D3 失败梯度断在 1b。"""
    src = inspect.getsource(cw_loop.CwLoop.loop)
    i_branch = src.find('_role_detail_anchor_hit(self, screen)')
    assert i_branch >= 0, '1b 分支判定行未找到(结构变更,本锁须同步)'
    i_dispatch = src.find('CwScreenRoleDetailOverlay(self.ctx)', i_branch)
    assert i_dispatch > i_branch, '1b 分发调用不在分支体内'
    seg = src[i_branch:i_dispatch + 200]
    assert 'on_fail_retry=True' in seg, '1b 分发缺 on_fail_retry(落地审 F2 回归)'


# ==================== D5:动作 op 内嵌闸门降级执行断言 ====================


def _bare_equip_op(monkeypatch, current: str):
    """裸 CwOpEquipAll:画面判定替身返 ``current``,直调节点函数
    (operation_node 装饰器直返原函数,绕过 run 级装配)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
        CwOpEquipAll,
    )
    op = CwOpEquipAll.__new__(CwOpEquipAll)
    op.last_screenshot = object()
    monkeypatch.setattr(op, 'check_and_update_current_screen',
                        lambda screen, screen_name_list: current)
    return op


def _bare_tools_op(monkeypatch, current: str):
    """裸 CwOpTools(同上;节点先 screenshot 再判画面,双替身)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_tools import (
        CwOpTools,
    )
    op = CwOpTools.__new__(CwOpTools)
    monkeypatch.setattr(op, 'screenshot', lambda: object())
    monkeypatch.setattr(op, 'check_and_update_current_screen',
                        lambda screen, screen_name_list: current)
    return op


def test_equip_all_unexpected_screen_fails_not_skips(monkeypatch) -> None:
    """D5(2026-09-08 用户架构裁定):非预期屏 → round_fail 执行断言,
    禁旧 round_success('跳过') 假成功吞分发(外层把 RunEquip ✓ 当完成
    入账,装备实际没装 = T-163 事故放大器)。"""
    op = _bare_equip_op(monkeypatch, '货币战争-商店卡牌详情')
    res = op.equip_all()
    assert res.result.name == 'FAIL'
    assert '不在预期屏' in (res.status or '')


def test_equip_all_expected_screen_passes_gate(monkeypatch) -> None:
    """对照臂:预期屏通过闸门(裸实例缺 ctx,闸门放行后第一步模板读取
    即 AttributeError;若闸门误拦,round_fail 正常返回 → raises 不触发
    = 红,精确证明「放行」而非恒 fail)。"""
    op = _bare_equip_op(monkeypatch, '货币战争-备战')
    with pytest.raises(AttributeError):
        op.equip_all()


def test_tools_unexpected_screen_fails_not_skips(monkeypatch) -> None:
    """D5 同形件:tools 非预期屏 → FAIL(与 equip_all 同批同改,防半拉子)。"""
    op = _bare_tools_op(monkeypatch, '货币战争-商店卡牌详情')
    res = op.tools_consume()
    assert res.result.name == 'FAIL'
    assert '不在预期屏' in (res.status or '')


def _executor_with(op_stub) -> object:
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor
    # ctx 桩:__init__ 构造期读槽位中心(row_area_centers → get_screen,
    # 返 None = 空槽位表,守卫测试不触槽位面)
    ctx = SimpleNamespace(
        screen_loader=SimpleNamespace(get_screen=lambda name: None))
    return PrepActionExecutor(op_stub, ctx)


def test_run_composite_guard_blocks_dispatch(monkeypatch) -> None:
    """派发前置(T-163 D5 判断上提):非干净备战 → 不实例化组合 op 即
    返回未发出断批(op_path 故意给不存在模块——若守卫失效,延迟导入会抛
    ModuleNotFoundError,本测即 error)。批3a:返回形态 = (摘要, 是否发出)
    (T-223 三元组退役);守卫拦截 = 未发出。"""
    calls = {'check': 0}

    def _check(screen, screen_name_list):
        calls['check'] += 1
        return '货币战争-商店卡牌详情'

    host = SimpleNamespace(screenshot=lambda: object(),
                           check_and_update_current_screen=_check)
    ex = _executor_with(host)
    detail, emitted = ex._run_composite(
        '装备', 'nonexistent_module_t163.NoSuchOp',
        guard_screen='货币战争-备战')
    assert emitted is False, '守卫拦截 = 动作未发出(非成败回执)'
    assert '不在预期屏' in detail
    assert calls['check'] == 1


def test_run_composite_guard_passes_clean_prep() -> None:
    """对照臂:干净备战 → 守卫放行(到达延迟导入,坏路径抛
    ModuleNotFoundError = 守卫确实放行,派发链未被守卫截断)。"""
    host = SimpleNamespace(
        screenshot=lambda: object(),
        check_and_update_current_screen=lambda screen,
        screen_name_list: '货币战争-备战')
    ex = _executor_with(host)
    with pytest.raises(ModuleNotFoundError):
        ex._run_composite('装备', 'nonexistent_module_t163.NoSuchOp',
                          guard_screen='货币战争-备战')


def test_run_composite_deploy_not_guarded() -> None:
    """边界申报锁:部署组合不带 guard_screen(其画面检查属转移验证用途,
    cw_op_deploy 非路由闸门;D5 只接管装备/工具两处 success-skip 降级面,
    勿误伤 op 边界契约)——无守卫时直接到达延迟导入。

    语义重推(T-164 批A/D1,方案审选项 b):deploy 派发仍不带回环守卫,
    本锁语义不变;派发间隙的 overlay 弹出由 op 内 registry decision 全集
    检查(T-277 registry 化,旧措辞「三锚」)降级后的
    **执行断言**(round_fail STATUS_EVENT_OVERLAY)如实上报交回重判——
    「op 内 overlay 弹出 = 执行环境失配,重判归分发层」。行为锁在
    test_cw_action_op_compliance.py;本锁只钉「不升 guard_screen」
    这一边界(升守卫 = 本锁红,须先重推批前提)。"""
    host = SimpleNamespace(
        screenshot=lambda: object(),
        check_and_update_current_screen=lambda screen,
        screen_name_list: pytest.fail('部署派发不应触发画面守卫'))
    ex = _executor_with(host)
    with pytest.raises(ModuleNotFoundError):
        ex._run_composite('部署', 'nonexistent_module_t163.NoSuchOp')


def test_dispatch_point_guards_registered() -> None:
    """接线锁:装备/工具两处派发点必须带派发前置守卫(判断上提落位),
    防后续新增组合动作时漏带守卫退回「op 内自判」形态。

    结构跟进(T-164 C1 计划化):装备派发改走专用 ``_run_equip``(计划
    随指令下发,通用 _run_composite 路径无法传构造参),其守卫经共用
    helper ``_guard_screen_mismatch`` 接线;工具派发仍走 _run_composite
    的 guard_screen 参数。锁义不变 = 两处派发点都有守卫,仅字面锚随
    结构更新(锁红≠改动错,先判锁再跟进,判据=守卫语义仍全覆盖)。"""
    import sr_od.application.currency_war.prep_actions as pa_mod
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor

    src = inspect.getsource(pa_mod)
    dispatch_src = inspect.getsource(PrepActionExecutor._execute_dispatch)
    equip_src = inspect.getsource(PrepActionExecutor._run_equip)
    assert 'self._run_equip()' in dispatch_src, \
        '装备派发未走专用计划产出位(C1 计划化结构回归)'
    assert "_guard_screen_mismatch('货币战争-备战')" in equip_src, \
        '装备派发点守卫接线缺失'
    assert src.count("guard_screen='货币战争-备战'") == 1, \
        '工具派发点守卫接线缺失'
