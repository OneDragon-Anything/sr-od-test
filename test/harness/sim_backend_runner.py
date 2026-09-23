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

import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_ports import (
    SimBackendProtocol,
)


class SimControllerStub:
    """sim 运行器 controller 桩:任何属性/方法触碰即 AssertionError。

    双保险兜底(flow-seam 详设 §2):漏改的直连 controller 路径撞桩即炸,
    报「sim 模式触碰真实 IO」+ 触碰点调用栈(定位漏改点)。``__getattr__``
    只对缺失属性触发,桩自身零属性 → 任何接口名都炸;``hasattr`` 依赖
    AttributeError 静默,本桩刻意让 AssertionError 传播 = 触碰即响亮。
    """

    def __getattr__(self, name: str) -> Any:
        stack = ''.join(traceback.format_stack(limit=6)[:-1])
        raise AssertionError(
            f'sim 模式触碰真实 IO: controller.{name}\n{stack}')

    def __setattr__(self, name: str, value: Any) -> None:
        raise AssertionError(f'sim 模式触碰真实 IO: controller.{name} = {value!r}')


class MinimalSimBackend:
    """最小假后端(端口协议最小实现;端口/基类接线的锁测试面)。

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
