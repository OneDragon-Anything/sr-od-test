"""PrepActionExecutor 分派链返回形状锁(T-310 实施批;账本 =
.debug/progress/2026-09-06-currency-war-redesign/dag.jsonl 卡 T-299/T-310)。

契约单一源 = ``PrepActionExecutor._execute_dispatch`` docstring:handler 返回
``(机械执行摘要 detail: str, 是否实际发出 emitted: bool)``。``_open_box`` 的
槽不匹配拒绝分支曾反写为 ``(False, detail)``,wrapper 按 (detail, emitted)
解包后:未发出的开箱被记为已发出(回执 applied=True)、实读槽位诊断从
reason 面丢失、``last_detail`` 被布尔污染。本文件两把锁防同形复发。

⚠️ 验证锚警示(T-299 方案对抗审问题 1,勘误版口径):勿以「期望态不变」作
本锁断言——反序下 execute 的 ``if emitted:`` 门虽被带开,但门内
``apply_op_effect(OpenBox)`` 落显式零推进分支(cw_expected_state.apply_op_effect
else 注释块「显式不推进理由」枚举)、
``mark_s1_route_check`` 对 OpenBox 无 route_tag → route='' 直接 return
(mandate.py:898-904):期望态/闩/清键门三面修前修后恒不变,恒真断言 =
无效验证锚。锁断言面 = 返回形状 + detail 内容 + 回执 applied/reason。

锁覆盖边界(T-299 对抗审问题 4,勘误版口径):两把锁均为**分支采样担保**
——只锁现存 handler 的现存拒绝分支,锁不住未来在存量 handler 内**新增**
分支的同类反序变异(本次 bug 即「存量函数内新增分支反序」形态)。Python
注解 ``tuple[str, bool]`` 无运行时强制;``_execute_dispatch`` 返回边界的全量
fail-fast 断言在 T-310 实施批裁量中**不采**(sim harness 经类级替换
``_execute_dispatch``——sr-od-test/fixtures/cw_harness.py:714——不在断言链上,
「全量」主张打折;且形状违约属记账面,生产路径新增崩溃面与本执行器
「记账失败不阻塞执行」纪律相抵)。

executor 桌面形态先例 = test_cw_box_open_pick_merged.py(object.__new__ +
SimpleNamespace 桩,零真实 IO、零真实 sleep)。
"""
from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.kernel.cw_game_state as cw_game_state
import sr_od.application.currency_war.obs.cw_identity_obs as cw_identity_obs
from sr_od.application.currency_war import prep_actions
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    EnsureShopClosed,
    EnsureShopOpen,
    LevelUp,
    OpenBox,
    OpenTome,
    PickBoxCard,
    StartBattle,
)
from sr_od.application.currency_war.prep_actions import PrepActionExecutor


def _point(x: int = 100, y: int = 900) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


def _executor(monkeypatch, find_results: dict[str, bool] | None = None
              ) -> PrepActionExecutor:
    """桌面 executor:读屏/找区/等待/存图全桩;找区按 area 名查表定 is_success。"""
    ex = object.__new__(PrepActionExecutor)
    results = find_results or {}

    def _find(screen, screen_name, area_name, **_kw) -> SimpleNamespace:
        return SimpleNamespace(is_success=results.get(area_name, False))

    ex._op = SimpleNamespace(
        screenshot=lambda: SimpleNamespace(),
        round_by_find_area=_find,
        park_cursor=lambda **_kw: None,
        save_screenshot=lambda **_kw: '',
        check_and_update_current_screen=lambda screen, screen_name_list:
            '货币战争-备战',
    )
    ex._ctx = SimpleNamespace(
        controller=SimpleNamespace(mouse_move=lambda p: None,
                                   click=lambda p, **_kw: None),
        cw_match=None,
    )
    monkeypatch.setattr(prep_actions.time, 'sleep', lambda s: None)
    return ex


# ===== 锁1:槽不匹配拒绝分支(先红后绿)=====


class TestLock1OpenBoxSlotMismatch:
    """槽无箱(槽不匹配)分支返回形状 + 回执面。

    桩:read_supply_boxes → [(7, …)];发 OpenBox(slot=5)。反序形态
    ``(False, 诊断串)`` 下两测试均红;回归 ``(诊断串, False)`` 后绿。
    断言面 = 返回形状 + detail 内容 + 回执 applied/reason/last_detail——
    禁用「期望态不变」(修前修后恒真,无效锚,见模块 docstring 警示)。
    """

    def test_return_shape_direct(self, monkeypatch):
        """_open_box 直调:拒绝分支返回 (诊断串, False)。"""
        ex = _executor(monkeypatch)
        monkeypatch.setattr(prep_actions, 'read_supply_boxes',
                            lambda ctx, screen: [(7, _point())])
        detail, emitted = ex._open_box(OpenBox(slot=5))
        assert isinstance(detail, str), f'detail 非 str(返回序反写): {detail!r}'
        assert emitted is False, f'拒绝分支必须未发出: {emitted!r}'
        assert '无补给箱' in detail and '槽5' in detail, \
            f'实读槽位诊断丢失: {detail!r}'

    def test_receipt_via_execute(self, monkeypatch):
        """execute 全链:拒绝分支回执 applied=False、reason 带诊断、
        last_detail 保持 str。反序下 emitted=诊断串(truthy)→
        applied=True、reason=''、last_detail=False,三者均红。"""
        ex = _executor(monkeypatch)
        monkeypatch.setattr(prep_actions, 'read_supply_boxes',
                            lambda ctx, screen: [(7, _point())])
        captured: list[dict] = []
        monkeypatch.setattr(cw_game_state, 'board_state_from_ctx',
                            lambda ctx: object())
        monkeypatch.setattr(cw_game_state, 'note_action_receipt',
                            lambda bs, **kw: captured.append(kw))
        ex.execute(OpenBox(slot=5))
        assert len(captured) == 1, f'回执恰一条(每动作一行): {captured!r}'
        receipt = captured[0]
        assert receipt['applied'] is False, \
            f'未发出的开箱不得记为已发出: {receipt!r}'
        assert '无补给箱' in receipt['reason'], \
            f'实读诊断必须落在 reason 面: {receipt!r}'
        assert isinstance(ex.last_detail, str) and '无补给箱' in ex.last_detail, \
            f'last_detail 被非 str 污染: {ex.last_detail!r}'


# ===== 锁2:_dispatch_direct 全 handler 拒绝分支形状(table-driven)=====


def _case_click_spheres_empty(mp):
    ex = _executor(mp)
    mp.setattr(prep_actions, 'read_reward_spheres',
               lambda ctx, screen: [])
    return ex._dispatch_direct(ClickSpheres(max_k=1))


def _case_open_box_no_box(mp):
    ex = _executor(mp)
    mp.setattr(prep_actions, 'read_supply_boxes', lambda ctx, screen: [])
    return ex._dispatch_direct(OpenBox())


def _case_open_box_slot_mismatch(mp):
    ex = _executor(mp)
    mp.setattr(prep_actions, 'read_supply_boxes',
               lambda ctx, screen: [(7, _point())])
    return ex._dispatch_direct(OpenBox(slot=5))


def _case_open_tome_no_tome(mp):
    ex = _executor(mp)
    # _open_tome 在函数内 from cw_identity_obs import read_tomes → 桩源模块
    mp.setattr(cw_identity_obs, 'read_tomes', lambda ctx, screen: [])
    return ex._dispatch_direct(OpenTome(slot=5))


def _case_level_up_baseline_unreadable(mp):
    ex = _executor(mp)
    mp.setattr(prep_actions, '_read_level_raw', lambda ctx, screen: None)
    return ex._dispatch_direct(LevelUp())


def _case_ensure_shop_open_idempotent(mp):
    ex = _executor(mp, find_results={'按钮-收起': True})
    return ex._dispatch_direct(EnsureShopOpen())


def _case_ensure_shop_closed_idempotent(mp):
    ex = _executor(mp, find_results={'按钮-收起': False})
    return ex._dispatch_direct(EnsureShopClosed())


def _case_run_composite_guard(mp):
    ex = _executor(mp)
    mp.setattr(ex, '_guard_screen_mismatch',
               lambda guard_screen: '货币战争-备战-开商店')
    return ex._run_composite(
        '工具', 'sr_od.application.currency_war.operations.cw_op.cw_op_tools.CwOpTools',
        guard_screen='货币战争-备战')


def _case_run_equip_guard(mp):
    ex = _executor(mp)
    mp.setattr(ex, '_guard_screen_mismatch',
               lambda guard_screen: '货币战争-备战-开商店')
    return ex._run_equip()


_DISPATCH_CASES = [
    ('click_spheres_empty', '无球', _case_click_spheres_empty),
    ('open_box_no_box', '无补给箱', _case_open_box_no_box),
    ('open_box_slot_mismatch', '槽5', _case_open_box_slot_mismatch),
    ('open_tome_no_tome', '无秘密典籍', _case_open_tome_no_tome),
    ('level_up_baseline_unreadable', '基线读不到',
     _case_level_up_baseline_unreadable),
    ('ensure_shop_open_idempotent', '已开', _case_ensure_shop_open_idempotent),
    ('ensure_shop_closed_idempotent', '已关',
     _case_ensure_shop_closed_idempotent),
    ('run_composite_guard', '不在预期屏', _case_run_composite_guard),
    ('run_equip_guard', '不在预期屏', _case_run_equip_guard),
]


class TestLock2DispatchRejectShapes:
    """现存 handler 拒绝分支统一判别式:
    ``isinstance(ret[0], str) and isinstance(ret[1], bool) and ret[1] is False``。
    分支采样担保边界见模块 docstring(锁不住存量 handler 未来新增分支)。
    """

    @pytest.mark.parametrize('case_id, needle, case_fn', _DISPATCH_CASES,
                             ids=[c[0] for c in _DISPATCH_CASES])
    def test_reject_branch_shape(self, monkeypatch, case_id, needle, case_fn):
        ret = case_fn(monkeypatch)
        assert isinstance(ret, tuple) and len(ret) == 2, \
            f'{case_id}: 返回非二元组: {ret!r}'
        assert isinstance(ret[0], str), \
            f'{case_id}: detail 非 str(返回序反写/类型违约): {ret!r}'
        assert isinstance(ret[1], bool), \
            f'{case_id}: emitted 非 bool: {ret!r}'
        assert ret[1] is False, f'{case_id}: 拒绝分支必须未发出: {ret!r}'
        assert needle in ret[0], f'{case_id}: 拒绝诊断串丢失: {ret!r}'

    def test_pick_box_card_adapter_swap(self, monkeypatch):
        """PickBoxCard 经 _dispatch_direct 适配位换序:内形态
        ``(clicked: bool, msg: str)`` → 适配位 ``return msg, _clicked`` =
        契约形态 (detail, emitted)。适配位若被改回直通 ``(bool, str)``,
        本锁红。"""
        ex = _executor(monkeypatch)
        detail, emitted = ex._dispatch_direct(PickBoxCard())
        assert isinstance(detail, str) and 'overlay 未开' in detail, \
            f'适配位换序后 detail 应为诊断串: {detail!r}'
        assert emitted is False

    def test_start_battle_adapter_swap(self, monkeypatch):
        """StartBattle 经 _execute_dispatch 适配位换序:``_start_battle``
        内形态 ``(ok: bool, detail: str)`` → 适配位 ``return detail, ok`` =
        契约形态。适配位若被改回直通 ``(bool, str)``,本锁红。"""
        ex = _executor(monkeypatch)
        detail, emitted = ex._execute_dispatch(StartBattle())
        assert isinstance(detail, str) and '出战失败' in detail, \
            f'适配位换序后 detail 应为诊断串: {detail!r}'
        assert emitted is False
