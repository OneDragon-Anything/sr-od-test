"""sim 运行器 harness(测试仓;sim 统一迭代 flow-seam 详设 §4)。

为「真流程跑在 sim 世界之上」的测试提供装配缝:真 ``screen_loader``(生成
器查档案点位)+ controller 桩(全接口触碰即炸,双保险兜底)+ 最小假后端
+ ``install/uninstall`` 纪律包装 + ``fast_sleep`` 复用。完整 CwLoop 驱动
(真策略器 mandate_v1)随 SimBackend 本体落地(3.2/3.4)接入,本模块先
承载端口/基类/桩的锁测试面。

装配纪律(与生产 ``cw_sim_ports`` 同一契约):``sim_backend_fixture``
上下文管理器保证 teardown 必卸——模块槽是进程全局,残留会把后续测试
静默切进 sim 模式。
"""
from __future__ import annotations

import random
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_ports import (
    SimBackendProtocol,
)
from test.harness.fixture_controller import fast_sleep


class SimControllerStub:
    """sim 运行器 controller 桩:任何属性/方法触碰即 AssertionError。

    双保险兜底(flow-seam 详设 §2):漏改的直连 controller 路径撞桩即炸,
    报「sim 模式触碰真实 IO」+ 触碰点调用栈(定位漏改点)。``__getattr__``
    只对缺失属性触发,桩自身零属性 → 任何接口名都炸;``hasattr`` 依赖
    AttributeError 静默,本桩刻意让 AssertionError 传播 = 触碰即响亮。

    唯一放行面 = :attr:`is_game_window_ready`(恒 True):框架 execute()
    入口的「检测游戏窗口」节点走 ``ctx.is_game_window_ready`` 就绪探针,
    sim 状态副本无窗口即恒就绪——这是就绪查询非真实 IO,放行与 fail-loud
    语义不冲突(任何真实 IO 接口名仍炸)。
    """

    @property
    def is_game_window_ready(self) -> bool:
        return True

    def __getattr__(self, name: str) -> Any:
        stack = ''.join(traceback.format_stack(limit=6)[:-1])
        raise AssertionError(
            f'sim 模式触碰真实 IO: controller.{name}\n{stack}')

    def __setattr__(self, name: str, value: Any) -> None:
        raise AssertionError(f'sim 模式触碰真实 IO: controller.{name} = {value!r}')


class MinimalSimBackend:
    """最小假后端(端口协议最小实现;端口/基类接入的锁测试面)。

    - ``screen_identity`` 返回可设的 ``screen`` 档名;
    - ``observe`` 记录调用并返回 ``observe_result``(默认 None);
    - ``visible`` 按 ``visible_areas`` 集合应答;
    - ``click_answer`` 记录调用后委托端口机械镜
      (:func:`cw_sim_ports.mirror_click_answer` —— 实机同形 round 结果,
      until 走本后端 visible),即「后端处理转移后出机械镜结果」的契约
      最小形态。
    """

    def __init__(self, screen: str = '货币战争-备战') -> None:
        self.screen: str = screen
        #: (screen_name, area_name) → 可见;未登记 = 不可见
        self.visible_areas: set[tuple[str, str]] = set()
        self.observed: list[str] = []
        self.clicked: list[tuple[str, str]] = []
        self.observe_result: Any = None

    def screen_identity(self) -> str:
        return self.screen

    def observe(self, screen_name: str) -> Any:
        self.observed.append(screen_name)
        return self.observe_result

    def visible(self, screen_name: str, area_name: str) -> bool:
        return (screen_name, area_name) in self.visible_areas

    def click_answer(
        self,
        op: Operation,
        screen_name: str,
        area_name: str,
        until_find_all: list[tuple[str, str]] | None,
        until_not_find_all: list[tuple[str, str]] | None,
    ) -> OperationRoundResult:
        self.clicked.append((screen_name, area_name))
        return cw_sim_ports.mirror_click_answer(
            op, screen_name, area_name, until_find_all, until_not_find_all)


def install_sim_fixture(backend: SimBackendProtocol) -> None:
    """装配 sim 后端(测试入口;teardown 请用 :func:`uninstall_sim_fixture`)。"""
    cw_sim_ports.install_sim_backend(backend)


def uninstall_sim_fixture() -> None:
    """卸载 sim 后端(幂等;上下文管理器 teardown 自动调)。"""
    cw_sim_ports.uninstall_sim_backend()


@contextmanager
def sim_backend_fixture(
        backend: SimBackendProtocol | None = None,
) -> Iterator[MinimalSimBackend]:
    """sim 后端装配上下文(进入即装,退出必卸;单装配纪律由端口层锁)。

    backend 缺省 = 新建 :class:`MinimalSimBackend`;传入自定义后端时
    yield 值仍为传入对象(类型标注按缺省形,自定义实现走鸭子类型)。
    """
    _backend = backend if backend is not None else MinimalSimBackend()
    install_sim_fixture(_backend)
    try:
        yield _backend
    finally:
        uninstall_sim_fixture()


# ============================================================ 全流程装配
# (sim 统一 3.4 首局验收:真策略 mandate_v1 + 真 CwLoop 驱动 SimBackend
#  从 reset 跑到局终。装配缝 = flow-seam 详设 §4 运行器。)


@dataclass
class SimFullRun:
    """一次 sim 全流程运行的产物(验收断言消费)。"""

    #: 状态副本后端(done=True = 局终)。
    backend: Any
    #: 状态容器(运行终态)。
    gs: Any
    #: 状态容器逐域值快照(确定性双跑对拍载体;字段名 → 冻结为纯数据的值)。
    snapshot: dict
    #: 字段写操作流(状态 journal sink 内存捕获;不变式断言载体,不落盘)。
    journal_rows: list
    #: op 执行终态结果(execute() 返回值)。
    result: Any
    #: 运行宿主 loop(外环 fail 重派计数/结算轮数等运行级断言消费)。
    loop: Any
    #: hp 轨迹(后端结算链;不变式断言载体)。
    hp_trail: tuple


#: 非状态副本的元数据键(确定性对拍域外,冻结时剥除):match_final 记录
#: 内嵌的局时长(真实运行耗时,双跑必然不同)与 code_commit(落快照时
#: 的代码 HEAD 短哈希,随提交变化)——两者均与 sim 状态副本确定性无关。
_NONDETERMINISTIC_META_KEYS: frozenset = frozenset({'duration_s',
                                                    'code_commit'})


def _freeze_value(value: Any) -> Any:
    """状态容器值冻结为可 == 对拍的纯数据(dataclass → dict;容器/列表递归;
    墙钟度量键剥除,域见 :data:`_NONDETERMINISTIC_META_KEYS`)。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _freeze_value(v) for k, v in value.items()
                if k not in _NONDETERMINISTIC_META_KEYS}
    if isinstance(value, (list, tuple)):
        return [_freeze_value(v) for v in value]
    if hasattr(value, '__dataclass_fields__'):
        return {f: _freeze_value(getattr(value, f))
                for f in value.__dataclass_fields__
                if f not in _NONDETERMINISTIC_META_KEYS}
    return repr(value)


def container_snapshot(gs: Any) -> dict:
    """状态容器逐域值快照(域 = gs 上的 Field 形属性,``hasattr(.value)``;
    非域属性(如 strategy_state 附着对象)天然排除)。确定性双跑对拍
    载体——逐位一致判据的取数口。"""
    out: dict = {}
    for name, obj in sorted(vars(gs).items()):
        if name.startswith('_'):
            continue
        if hasattr(obj, 'value'):
            out[name] = _freeze_value(obj.value)
    return out


class _ModuleTimeProxy:
    """模块级 ``time`` 引用替身(sleep → 记录 no-op,其余透传真模块)。"""

    def __init__(self, real: Any, skipped: list) -> None:
        self._real = real
        self._skipped = skipped

    def sleep(self, seconds: float) -> None:
        self._skipped.append(seconds)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


@contextmanager
def freeze_cw_module_time() -> Iterator[list]:
    """冻结 CW 树内全部模块的裸 ``time.sleep``(op 模块直睡面;sim 状态副本
    瞬时呈现,直睡纯属空等)。范围 = ``sr_od.application.currency_war``
    前缀模块 + 框架 operation 模块,按 sys.modules 现值挂替身,退出逆序
    还原(手法同 fixture_controller.fast_sleep 的模块级桩)。
    """
    import sys
    import time as _time_mod

    import one_dragon.base.operation.operation as _operation_mod  # noqa: F401  (import 即注册 sys.modules,冻结循环才能覆盖 operation 模块)

    skipped: list = []
    saved: list = []
    targets = [n for n in sys.modules
               if (n.startswith('sr_od.application.currency_war')
                   or n == 'one_dragon.base.operation.operation')]
    for name in targets:
        mod = sys.modules.get(name)
        if mod is None or not hasattr(mod, 'time'):
            continue
        if mod.time is not _time_mod:
            continue   # 已被别处桩住(fast_sleep 等)→ 不重复包
        saved.append((mod, mod.time))
        mod.time = _ModuleTimeProxy(_time_mod, skipped)  # type: ignore[assignment]
    try:
        yield skipped
    finally:
        for mod, orig in reversed(saved):
            mod.time = orig  # type: ignore[assignment]


@contextmanager
def capture_state_journal() -> Iterator[list]:
    """状态容器写流内存捕获(kernel 状态 journal sink;不落盘)。

    同点接通 run 归属供给槽(:func:`set_run_id_provider` → telemetry
    现读口):生产装配点 = 局状态容器单例建立漏斗(establish_new_match →
    game_state_of),sim 走状态容器绑定口绕过该点,行归属供给须运行器补装
    ——缺它 = 全部行按「局外拒写」静默丢失(捕获失效)。

    退出复位 sink 与供给槽。捕获 = 行投影(版本/行型/字段/after 值)非
    原行——原行内嵌 full_state_snapshot(全状态容器转储),整局捕获原行会
    内存爆炸;投影行保留不变式断言所需最小面。
    """
    from sr_od.application.currency_war.kernel.cw_game_state import (
        set_run_id_provider,
        set_state_journal_sink,
    )
    from sr_od.application.currency_war.telemetry import state as _tstate

    rows: list = []

    def _project(row: dict) -> None:
        rows.append({'v': row.get('v'), 'row': row.get('row'),
                     'field': row.get('field'), 'after': row.get('after')})

    set_state_journal_sink(_project)
    set_run_id_provider(_tstate.current_run_id)
    try:
        yield rows
    finally:
        set_run_id_provider(None)
        set_state_journal_sink(None)


def run_sim_full_match(test_context: Any,
                       monkeypatch: Any,
                       tmp_path: Any,
                       *,
                       seed: int = 20260923,
                       strategy_seed: int = 20260923,
                       enemy_affixes: tuple = (),
                       max_rounds: int = 1200) -> SimFullRun:
    """真流程 × sim 状态副本跑一整局(3.4 首局验收的运行原语)。

    装配(flow-seam §4):真 screen_loader + controller 桩(就绪探针放行,
    其余触碰即炸)+ SimBackend(端口槽 + 事件钩子 + 动作分支 rng 提供槽)
    + 真 mandate_v1 策略器(构造注入 SimpleNamespace(strategy_seed))
    + 状态容器单例绑定(后端状态容器 = 流程唯一状态副本)+ 真 CwLoop(看门狗轮数
    上限)。obs 读口装配点接通纯钩子半部(缓存清理 + 合成特效帧门;
    缺陷台账 sink 缺省关 = 不落盘,测试零真实 IO)。

    钩子桩(装配缝 1/1c):决策帧留证钩子源上桩(sim 帧无仲裁对象,
    零留证写入)+ 实机采集停机钩子桩(语义同批夹具)。CW 模块
    裸 ``time.sleep`` 冻结。telemetry 归档不接(任务边界:验收只做测试
    断言;journal sink 走内存捕获)。

    返回 :class:`SimFullRun`;teardown 必卸(端口槽/事件 sink/rng 槽/
    运行态/controller/状态容器绑定随 monkeypatch 与 weakref 生命周期还原)。
    """
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_game_state import (
        bind_session_container,
    )
    from sr_od.application.currency_war.kernel.cw_reconcile import (
        set_merge_effect_gate,
    )
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.obs.cw_identity_obs import (
        is_merge_effect_frame,
    )
    from sr_od.application.currency_war.obs.cw_observation import (
        reset_phase_round_cache,
    )
    from sr_od.application.currency_war.operations.cw_loop import CwLoop
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SimBackend,
        install_backend,
        uninstall_backend,
    )
    from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
        set_obs_reset_hook,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        bridge as cw_bridge,
    )
    from test.harness.fixture_controller import (
        WatchdogOperationMixin,
        enter_running_state,
        reset_running_state,
    )

    # —— 装配缝 1:留证钩子源上桩(sim 局零留证写入)——决策帧留的是
    # 「识别完成点的原始画面」,作实机识别漏读/误读的仲裁基准(模块头
    # 层次定位);sim 帧是合成产物,无仲裁对象,逐帧 PNG 落盘纯付测试
    # 时长(单局 ~59 帧,慢盘环境单帧可达秒级 → 整局批预算被磁盘态绑架)。
    # 桩形沿用仓内单帧测试先例(save_decision_frame no-op 桩);桩面 =
    # 调用方模块命名空间绑定(from-import 语义,见 sim-testing「批驱动器
    # monkeypatch 规约」)。get_project_root 重定向保留作兜底:未来新增
    # 直连该缝的写入点仍不落真实仓。
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_loop.save_decision_frame',
        lambda *a, **k: None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_shop.'
        'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.decision_frame_hooks.'
        'get_project_root',
        lambda: tmp_path)

    # —— 装配缝 1b:遥测根重定向(测试零真实 IO)——cw_loop 局终收尾
    # 钩子在生产代码里无条件调 match_archive.assemble_pending(recorder
    # 单例缺省 replay_dir = 生产遥测根),不重定向时整局测试收尾会逐行
    # 解析生产根下累积的全部局 journal(实测量级:根下 jsonl 总量 GB 级、
    # 单局 journal 数十 MB,整局测试被归档读取拖到超时)。重定向到 tmp 后
    # 收尾归档只见本局产物(装配快跑);runs 行/journal 落盘同随根落 tmp。
    # 单例操作不走 monkeypatch(丢弃重建语义),finally 显式复位。
    from sr_od.application.currency_war.telemetry.state import (
        set_recorder_replay_dir,
    )
    set_recorder_replay_dir(tmp_path)

    # —— 装配缝 1c:实机采集停机钩子桩(同 sim/conftest.py 批夹具桩形:
    # sim 局无实机画面可采,语义澄清非绕过验证面)——整局轨迹持
    # _SPEC_INVEST_WATCH_NAMES 名单投资策略进商店即触发真实停机:
    # 验收局被截断,且 stop_running 残留(last_run_result)贯穿同一测试
    # 内的后续局(W209j 刹车拒动作 → 看门狗轮限空转假红)。
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_prep.'
        'CwScreenPrep._spec_invest_shop_stop_hook', lambda self: None)

    # —— 装配缝 2:obs 读口纯钩子半部(生产 = decision_assembly.
    # install_obs_ports;缺陷台账落盘 sink 缺省关,测试零 IO) ——
    set_obs_reset_hook(reset_phase_round_cache)
    set_merge_effect_gate(is_merge_effect_frame)

    # —— 状态副本后端 + 状态容器单例绑定(流程取口与后端状态容器同源) ——
    backend = SimBackend(
        seed=seed,
        cfg=RunConfig(selected_difficulty='A8', enemy_difficulty=108,
                      env_present=True, enemy_affixes=tuple(enemy_affixes)))
    install_backend(backend)

    # —— 策略器 + 局状态容器(真 mandate_v1,构造注入;终态契约 §2.1) ——
    session = StrategySession()
    session.rng = random.Random(strategy_seed)
    bind_session_container(session, backend.gs)
    strategy = cw_bridge.MandateV1Strategy(
        backend.gs, SimpleNamespace(strategy_seed=strategy_seed))
    session.strategy_state = strategy.state
    match = CurrencyWarMatch(strategy, session, backend.gs,
                             performance=getattr(session, 'performance',
                                                 None))

    # —— controller 桩 + 真 CwLoop(看门狗轮数上限) ——
    monkeypatch.setattr(test_context, 'controller', SimControllerStub())

    class _WatchedLoop(WatchdogOperationMixin, CwLoop):
        pass

    _WatchedLoop.watchdog_max_rounds = max_rounds
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    enter_running_state(test_context)
    loop = None
    try:
        with capture_state_journal() as rows, freeze_cw_module_time():
            loop = _WatchedLoop(test_context)
            with fast_sleep(loop):
                result = loop.execute()
    except Exception as exc:
        # 崩点上下文注入(PEP-678 add_note:不改异常类型/不吞 traceback,
        # 报告面追加状态副本——冒烟批「哪节点崩」的最小凭据;「哪动作」
        # 由原 traceback 承载。读 backend 私有槽仅取现值,无副作用)。
        exc.add_note(
            'sim 全流程局崩点上下文: '
            f'seed={seed}, node={backend.gs.node.value!r}, '
            f'screen={backend._screen!r}, steps={backend._steps}, '
            f'hp={backend.gs.hp.value!r}, gold={backend.gs.gold.value!r}')
        raise
    finally:
        if loop is not None:
            reset_running_state(test_context, loop)
        uninstall_backend()
        # 遥测根复位(装配缝 1b 对应;丢弃重建语义,复位后单例按生产
        # 缺省根惰性重建——下一局 run_sim_full_match 重新接 tmp)。
        from sr_od.application.currency_war.telemetry.state import (
            set_recorder_replay_dir,
        )
        set_recorder_replay_dir(None)
    return SimFullRun(
        backend=backend,
        gs=backend.gs,
        snapshot=container_snapshot(backend.gs),
        journal_rows=rows,
        result=result,
        loop=loop,
        hp_trail=tuple(backend.hp_trail),
    )
