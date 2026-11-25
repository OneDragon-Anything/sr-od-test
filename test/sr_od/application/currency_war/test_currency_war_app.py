"""CurrencyWarApp 测试(打桩 + 归档真帧,不跑游戏)。

两块覆盖:
- ``_in_match`` 入口判定(``TestInMatch``):画面匹配 → 白名单短路 → 关键词兜底
  三层判定序;锁「对局前建档页被关键词层误判为对局中」故障形态;
- 退出收尾交接节点(``TestExitCleanupHandoff``):loop→exit 交接的三形态判定与两段式。

交接节点覆盖(载体 =
``_previous_round_result.status``,框架在节点转移时写入):

- 大厅完成(``STATUS_LOBBY_DONE``)→ CwEntryExit 被调 + ``ctx.cw_match`` 置
  None(兜底清理点);
- 异常交接(``STATUS_HANDOFF_PREFIX`` 前缀)→ exit 被调 + 置 None;
- max_rounds 停备战(is_debug=True 分支产出)→ exit 零调用(app 直接成功
  收尾,留局采样);
- max_rounds 停点非 debug 分支(交接前缀文本交出)→ exit 被调 + 置 None
  (弃局回大厅,重开由下一次 app 运行承载);
- 假局守卫开局失败-中断 → exit 零调用(已在大厅且对局状态已清);
- loop fail → 不入交接节点(success 边才入)→ exit 零调用 + app 失败收尾;
- 积分奖励弹窗压大厅 → 守卫两段动作(一键领取→关闭)清弹窗 → exit 被调
  (守卫注册表领后关闭两段动作的真实路径)。

打桩模式照 test_nameless_honor_app.py:子 op 类假件(记录构造/执行)、识别
原语桩,真实走 app ``execute()`` 的节点链与边;入口态(_at_lobby/_in_match)
桩为 True 短路入口 op,loop 出口文本由假件注入(异常交接出口文本的 loop 本体
改写不在本批范围,见 STATUS_HANDOFF_PREFIX 注释)。
"""

from types import SimpleNamespace

import numpy as np
import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.screen import screen_utils
from sr_od.application.currency_war import currency_war_app as cw_app_module
from sr_od.application.currency_war.currency_war_app import CurrencyWarApp
from sr_od.application.currency_war.cw_screen_state import LOBBY_STATE_SCREENS
from sr_od.application.currency_war.kernel import cw_code_hash_gate
from sr_od.application.currency_war.kernel.cw_code_hash_gate import GateResult
from sr_od.application.currency_war.operations.cw_loop import (
    STATUS_HANDOFF_PREFIX,
    STATUS_LOBBY_DONE,
)

# 假局守卫出口文本(cw_loop._lobby_return_step 的具名 status;三形态「其余」
# 分支的判定输入,测试注入用)。
FAKE_MATCH_GUARD_STATUS = '开局失败/中断(未产生对局数据,不记 summary)'


class _StubCurrencyWarApp(WatchdogOperationMixin, CurrencyWarApp):
    """绕过游戏窗口前置与生产遥测装配的 CurrencyWarApp(跑完整 execute 节点链)。

    __init__ 直连 SrApplication(跳过 CurrencyWarApp.__init__ 的生产钩子
    装配段);run_record 依赖 get_run_record 桩抛错保持 None(handle_init
    零落盘,见 _patch_common)。
    """

    watchdog_max_rounds: int = 60

    def __init__(self, ctx) -> None:
        from sr_od.application.currency_war.currency_war_const import APP_ID
        from sr_od.application.sr_application import SrApplication

        SrApplication.__init__(
            self, ctx, APP_ID, op_name='货币战争',
            need_check_game_win=False, run_record=None,
        )


def _no_run_record(**kwargs) -> None:
    """get_run_record 替身:抛错让 Application 的 ``suppress(Exception)`` 保持
    run_record=None(handle_init/收尾不写运行记录,零真实副作用)。"""
    raise RuntimeError('测试禁用运行记录')


def _make_loop_fake(result: OperationResult, reveal_frame=None):
    """构造 CwLoop 假件类(每测试独立类对象,零跨测试类属性泄漏)。

    ``reveal_frame`` 非 None 时 execute 前把 controller.mock_screenshot 换成
    该帧——模拟「对局结束瞬间局末弹窗自动弹出压住大厅」的画面转移。
    """

    class _FakeLoop:
        def __init__(self, ctx, max_rounds=None, stop_at_prep=False) -> None:
            self._ctx = ctx

        def execute(self) -> OperationResult:
            if reveal_frame is not None:
                self._ctx.controller.mock_screenshot = reveal_frame
            return result

    return _FakeLoop


def _make_exit_fake():
    """构造 CwEntryExit 假件类:记录构造/执行,恒返回成功(已回大厅)。"""

    class _RecordingExit:
        constructed: int = 0
        executed: int = 0

        def __init__(self, ctx) -> None:
            type(self).constructed += 1

        def execute(self) -> OperationResult:
            type(self).executed += 1
            return OperationResult(success=True, status='已返回货币战争大厅')

    return _RecordingExit


def _miss_find_area(self, screen, screen_name, area_name,
                    *args, **kwargs):
    """识别原语桩(缺省):恒未命中——守卫注册表零真识别(mock 帧为
    None/空白,真识别链对 None 帧直接炸 OCR)。"""
    return self.round_wait(status=f'未找到 {area_name}')


def _patch_common(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
    find_area_impl=None,
) -> None:
    """公共桩:入口态短路 + 运行记录禁用 + 起局码哈希闸放行。

    - ``_at_lobby``/``_in_match`` 桩 True:走「已在 CW(大厅/对局中)」短路,
      CwEntryEnter/CwEntryStart 不构造(入口链非本测试对象);
    - ``_recover_if_paused`` 桩 None:战斗暂停预检零动作;
    - get_run_record 抛错:run_record 保持 None,handle_init 零落盘;
    - 码哈希闸恒放行:真实闸跑 git 子进程读工作树,测试禁真实外部命令;
    - round_by_find_area 桩(缺省恒未命中,弹窗用例传帧键控桩)。
    """
    monkeypatch.setattr(test_context.run_context, 'get_run_record',
                        _no_run_record)
    monkeypatch.setattr(cw_code_hash_gate, 'check_workspace_matches_head',
                        lambda *a, **k: GateResult(ok=True))
    monkeypatch.setattr(CurrencyWarApp, '_at_lobby',
                        lambda self, screen: True)
    monkeypatch.setattr(CurrencyWarApp, '_in_match',
                        lambda self, screen: True)
    monkeypatch.setattr(CurrencyWarApp, '_recover_if_paused',
                        lambda self, screen: None)
    monkeypatch.setattr(CurrencyWarApp, 'round_by_find_area',
                        find_area_impl or _miss_find_area)


def _run_app(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
    loop_result: OperationResult,
    loop_reveal_frame=None,
    exit_cls=None,
    find_area_impl=None,
):
    """公共执行器:装桩 → 建 app(monkeypatch cw_match 哨兵)→ execute。

    返回 (app 执行结果, exit 假件类)。cw_match 哨兵经 monkeypatch 注入,
    测试结束自动还原(session 级 ctx 零污染)。``find_area_impl`` 非 None 时
    替换缺省的恒未命中识别桩(弹窗用例的帧键控桩)。
    """
    _patch_common(test_context, monkeypatch, find_area_impl=find_area_impl)
    if exit_cls is None:
        exit_cls = _make_exit_fake()
    monkeypatch.setattr(cw_app_module, 'CwLoop',
                        _make_loop_fake(loop_result, loop_reveal_frame))
    monkeypatch.setattr(cw_app_module, 'CwEntryExit', exit_cls)
    monkeypatch.setattr(test_context, 'cw_match', object(), raising=False)

    app = _StubCurrencyWarApp(test_context)
    app._init_watchdog()  # type: ignore[attr-defined]

    enter_running_state(test_context)
    try:
        with fast_sleep(app):
            result = app.execute()
    finally:
        reset_running_state(test_context, app)
    return result, exit_cls


class TestExitCleanupHandoff:
    """退出收尾交接节点:三形态判定 + 两段式 + 兜底清理。"""

    def test_lobby_done_calls_exit_and_clears_match(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """大厅完成形态:exit 被调一次,cw_match 置 None,app 成功收尾。"""
        result, exit_cls = _run_app(
            test_context, monkeypatch,
            loop_result=OperationResult(success=True, status=STATUS_LOBBY_DONE),
        )

        assert result.success, f'app 应成功收尾,status={result.status}'
        assert exit_cls.constructed == 1 and exit_cls.executed == 1, (
            f'exit 应被构造并执行恰一次:{exit_cls.constructed}/{exit_cls.executed}'
        )
        assert test_context.cw_match is None, '交接成功后 cw_match 应置 None'

    def test_handoff_prefix_calls_exit_and_clears_match(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """异常交接形态(前缀 + 动态后缀):exit 被调,cw_match 置 None。

        动态后缀模拟 loop 耗尽出口的交接键(如分发键),判定按前缀消费。
        """
        result, exit_cls = _run_app(
            test_context, monkeypatch,
            loop_result=OperationResult(
                success=True, status=f'{STATUS_HANDOFF_PREFIX}投资环境链'),
        )

        assert result.success, f'app 应成功收尾,status={result.status}'
        assert exit_cls.constructed == 1 and exit_cls.executed == 1, (
            f'exit 应被构造并执行恰一次:{exit_cls.constructed}/{exit_cls.executed}'
        )
        assert test_context.cw_match is None, '交接成功后 cw_match 应置 None'

    def test_max_rounds_skips_exit(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """max_rounds 停备战形态(is_debug=True 分支):留局采样,exit 零调用,
        app 直接成功收尾。

        「停备战」出口文本只在 loop 停点段 debug 分支产出(停点分模式),
        is_debug 前提显式锁定——禁依赖 conftest 缺省值(session ctx 共享,
        缺省随 fixture 变,断言会随机红)。假 loop 不读 env_config,此桩 =
        用例前提申报;停点段两分支的产出端锁定在 test_cw_loop 停点出口测试。
        """
        monkeypatch.setattr(test_context, 'env_config',
                            SimpleNamespace(is_debug=True))
        result, exit_cls = _run_app(
            test_context, monkeypatch,
            loop_result=OperationResult(
                success=True, status='已跑 2 轮停备战(达 max_rounds=2)'),
        )

        assert result.success, f'app 应成功收尾,status={result.status}'
        assert '非退出交接形态' in (result.status or ''), (
            f'应走跳过分支,status={result.status}'
        )
        assert exit_cls.constructed == 0 and exit_cls.executed == 0, (
            f'exit 零调用,实际 {exit_cls.constructed}/{exit_cls.executed}'
        )

    def test_max_rounds_non_debug_handoff_calls_exit(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """max_rounds 停点非 debug 分支:交接前缀文本交出 → exit 被调,
        cw_match 置 None(弃局回大厅,重开由下一次 app 运行承载)。

        注入文本与 loop 停点段非 debug 出口同形
        (``STATUS_HANDOFF_PREFIX + '停点重开:max_rounds=N'``),三形态判定
        按前缀命中异常交接形态。is_debug=False 前提显式锁定,禁依赖
        conftest 缺省值。
        """
        monkeypatch.setattr(test_context, 'env_config',
                            SimpleNamespace(is_debug=False))
        result, exit_cls = _run_app(
            test_context, monkeypatch,
            loop_result=OperationResult(
                success=True,
                status=f'{STATUS_HANDOFF_PREFIX}停点重开:max_rounds=2'),
        )

        assert result.success, f'app 应成功收尾,status={result.status}'
        assert exit_cls.constructed == 1 and exit_cls.executed == 1, (
            f'交接形态 exit 应被构造并执行恰一次:'
            f'{exit_cls.constructed}/{exit_cls.executed}'
        )
        assert test_context.cw_match is None, '交接成功后 cw_match 应置 None'

    def test_fake_match_guard_skips_exit(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """假局守卫形态(开局失败-中断):已在大厅且对局状态已清,exit 零调用。"""
        result, exit_cls = _run_app(
            test_context, monkeypatch,
            loop_result=OperationResult(
                success=True, status=FAKE_MATCH_GUARD_STATUS),
        )

        assert result.success, f'app 应成功收尾,status={result.status}'
        assert exit_cls.constructed == 0 and exit_cls.executed == 0, (
            f'exit 零调用,实际 {exit_cls.constructed}/{exit_cls.executed}'
        )

    def test_loop_fail_fails_without_exit(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """loop fail 形态:不入交接节点(success 边才入),exit 零调用,app 失败收尾。"""
        result, exit_cls = _run_app(
            test_context, monkeypatch,
            loop_result=OperationResult(
                success=False, status='投资环境 连续 fail 超上限(交上层处置)'),
        )

        assert not result.success, (
            f'loop fail 应使 app 失败收尾,status={result.status}'
        )
        assert exit_cls.constructed == 0 and exit_cls.executed == 0, (
            f'fail 不入交接节点,exit 应零调用,实际 '
            f'{exit_cls.constructed}/{exit_cls.executed}'
        )

    def test_point_reward_popup_guarded_then_exit(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """积分奖励压大厅:守卫两段动作(一键领取→关闭)清弹窗 → exit 被调。

        真守卫注册表路径(try_handle_entry_popups 不桩,识别原语桩帧键控):
        弹窗帧在场时命中积分奖励守卫,单守卫轮完成领后关闭两段动作;下一轮
        识别标志不命中(弹窗已清)→ 落 exit 调用段。锁两段动作的点击序。
        """
        if not test_context.has_screen('货币战争-积分奖励', '达标弹窗'):
            pytest.skip('存档截图缺失:screens/货币战争-积分奖励/达标弹窗.webp')
        popup_frame = test_context.load_screen('货币战争-积分奖励', '达标弹窗')

        identify_hits: list[str] = []
        clicked: list[tuple[str, str]] = []

        def _fake_find_area(self, screen, screen_name, area_name,
                            *args, **kwargs):
            # 帧键控 + 一次命中:模拟「守卫动作落地后弹窗消失」——首轮守卫
            # 识别标志命中,动作轮之后的重识别不命中(守卫循环的收敛语义)。
            if (screen is popup_frame
                    and screen_name == '货币战争-积分奖励'
                    and area_name == '标识-积分奖励'
                    and not identify_hits):
                identify_hits.append(area_name)
                return self.round_success(status=f'{screen_name}-{area_name}')
            return self.round_wait(status=f'未找到 {area_name}')

        def _fake_find_click(self, screen, screen_name, area_name,
                             *args, **kwargs):
            clicked.append((screen_name, area_name))
            return self.round_success(status=f'{screen_name}-{area_name}')

        monkeypatch.setattr(CurrencyWarApp, 'round_by_find_and_click_area',
                            _fake_find_click)

        result, exit_cls = _run_app(
            test_context, monkeypatch,
            loop_result=OperationResult(success=True, status=STATUS_LOBBY_DONE),
            loop_reveal_frame=popup_frame,
            find_area_impl=_fake_find_area,
        )

        assert result.success, f'app 应成功收尾,status={result.status}'
        # 两段动作点击序:一键领取 → 领后新帧点关闭(守卫注册表迁移面)。
        assert clicked == [
            ('货币战争-积分奖励', '按钮-一键领取'),
            ('货币战争-积分奖励', '按钮-关闭'),
        ], f'守卫两段动作点击漂移:{clicked}'
        assert exit_cls.constructed == 1 and exit_cls.executed == 1, (
            f'弹窗清完后 exit 应被调恰一次:{exit_cls.constructed}/{exit_cls.executed}'
        )
        assert test_context.cw_match is None, '交接成功后 cw_match 应置 None'


class TestInMatch:
    """``_in_match`` 三层判定序锁:画面匹配 → 白名单短路 → 关键词兜底。

    锁的故障形态(待跟进事项「_in_match 第②层关键词兜底绕过对局前画面白名单」):
    对局前建档页(数据银行)带「投资策略图鉴 / 投资环境图鉴」字样,第①层画面匹配
    对白名单屏不可见(名单 = 前缀 − 白名单),直接落第②层关键词 → 误判「已在对局中」
    → 单跑 CW app 跳过 start 交 loop,对局循环跑在图鉴页上。设计约定:精确建档命中
    (任一方向)优先于关键词启发式——白名单屏精确命中即短路 False,不进关键词层。
    """

    def test_data_bank_frame_not_in_match(
        self,
        test_context: SrTestContext,
    ) -> None:
        """数据银行归档帧(带「投资策略图鉴 / 投资环境图鉴」字样)→ False(全真识别)。"""
        if not test_context.has_screen('货币战争-数据银行', '主页'):
            pytest.skip('存档截图缺失:screens/货币战争-数据银行/主页.webp')
        frame = test_context.load_screen('货币战争-数据银行', '主页')

        app = _StubCurrencyWarApp(test_context)
        assert not app._in_match(frame), (
            '数据银行页是对局前建档屏(白名单成员),不应被判为对局中'
        )

    def test_whitelist_hit_short_circuits_before_keywords(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """白名单任一屏精确命中 → False,且关键词层零调用(遍历白名单全集)。"""
        ocr_calls: list[str] = []

        def _matcher(hit: str):
            """画面匹配桩:查询名单含 hit 时答 hit(该屏被精确识别),其余 None。"""
            def _match(ctx, screen, screen_name_list=None, **kwargs):
                return hit if hit in (screen_name_list or []) else None
            return _match

        monkeypatch.setattr(CurrencyWarApp, '_at_lobby', lambda self, screen: False)
        monkeypatch.setattr(
            CurrencyWarApp, 'round_by_ocr',
            lambda self, screen, kw, **kwargs: ocr_calls.append(kw) or self.round_success(kw),
        )
        app = _StubCurrencyWarApp(test_context)
        blank = np.zeros((8, 8, 3), dtype=np.uint8)
        for hit in sorted(LOBBY_STATE_SCREENS):
            monkeypatch.setattr(screen_utils, 'get_match_screen_name', _matcher(hit))
            assert not app._in_match(blank), f'白名单屏 {hit} 精确命中时应短路 False'
        assert ocr_calls == [], f'白名单命中后不应触达关键词层,实际调用 {ocr_calls}'

    def test_keyword_layer_reached_when_no_precise_match(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """两层画面匹配均未命中(半开 / 过渡帧)→ 仍落关键词层,关键词命中 → True。"""
        ocr_calls: list[str] = []
        monkeypatch.setattr(CurrencyWarApp, '_at_lobby', lambda self, screen: False)
        monkeypatch.setattr(screen_utils, 'get_match_screen_name',
                            lambda *args, **kwargs: None)
        monkeypatch.setattr(
            CurrencyWarApp, 'round_by_ocr',
            lambda self, screen, kw, **kwargs: ocr_calls.append(kw) or self.round_success(kw),
        )
        app = _StubCurrencyWarApp(test_context)

        assert app._in_match(np.zeros((8, 8, 3), dtype=np.uint8))
        assert ocr_calls, '两层画面匹配均未命中时应触达关键词层'

    def test_in_match_frame_still_in_match(
        self,
        test_context: SrTestContext,
    ) -> None:
        """对局中帧(备战)不受白名单短路影响 → True(全真识别)。"""
        if not test_context.has_screen('货币战争-备战', 'rail_badge_capsule_prep_r4'):
            pytest.skip('存档截图缺失:screens/货币战争-备战/rail_badge_capsule_prep_r4.webp')
        frame = test_context.load_screen('货币战争-备战', 'rail_badge_capsule_prep_r4')

        app = _StubCurrencyWarApp(test_context)
        assert app._in_match(frame), '备战帧是对局中画面,应判为对局中'
