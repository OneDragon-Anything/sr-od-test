"""外环 op-fail 重派防线上限锁(2026-09-15)。

病理(选择伙伴 15 连败,2026-09-15 事故):画面 op 退出 fail → 外环
``_dispatch_screen_op`` 默认映射 round_wait(零预算)→ 同分支每帧再命中
→ 同一 op 无界重派,直到 NODE-DWELL 900s 系统哨兵兜住。op 层有界化
(「确认被拒」显式 fail)后,外环仍对无判读 fail 空转。修 = 环级
连续 fail 上限:同一分发 op 连续 fail 达 ``CwLoop.OP_FAIL_REDISPATCH_
LIMIT`` → round_fail 显式停交上层。

锁的六件事:
1. 计数窗口语义(纯函数):ok 整窗归零(fail 间歇重置)/同键 fail 累加/
   异键 fail 换情节从 1 起算;
2. 包装接线:连续 fail 至上限-1 仍走默认 round_wait,第 LIMIT 次转
   round_fail(status 含 op 行名可判读)+ 留证截图恰一次 + [cw-op]
   日志行每次分发恰一行(出口即落);
3. 间歇 ok 复位:fail 窗内穿插任一 ok → 计数清零,后续 fail 从 1 重计,
   不提前触发;
4. 异键 ok 同闭窗:粘滞 op 的 fail 序列被**其他** op 的 ok 打断 → 该 op
   计数一并清零(跨情节残留不毒化新情节);
5. hook 早退先于通用网:on_result 在 fail 时返回自身轮次结果 → 恒返回
   hook 的结果,且 hook 早退路径不进通用网计数(结构性不抢占;原
   0q/prep streak 专用守卫已退役并入本网,机制契约保留);
6. on_fail_retry 分支同辖:fail 达上限转 round_fail(不再消耗 400 节点
   重试池),上限内维持既有 round_retry 语义。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
from sr_od.application.currency_war.operations.cw_loop import (
    CwLoop,
)


def _spy_cw_op(monkeypatch) -> list[tuple[str, str]]:
    """桩掉 [cw-op] 日志行落点(测试零真实日志副作用)+ 留 (op, outcome)
    序列供配对断言(原 journal record_op_enter/exit 桩随该流退役换型)。"""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cw_loop_mod, '_log_cw_op',
                        lambda name, pos, dur, outcome, detail='':
                        calls.append((name, outcome)))
    return calls


class _Host:
    """``_dispatch_screen_op`` 离线宿主:只供给包装消费面(round 工厂/
    留证/上限值),镜像恢复路由锁的替身纪律(ctx 缺省缺席 = 位置键退 (0, 0);
    刻意**不**预置 ``_op_fail_streak_key/_n``——锁 getattr 缺省初始化
    路径与生产首帧形态一致。
    """

    def __init__(self, limit: int):
        self.last_screenshot = None
        self.OP_FAIL_REDISPATCH_LIMIT = limit
        self.rounds: list[tuple[str, str | None]] = []
        self.shots: list[str] = []

    def round_wait(self, status=None, data=None, wait=None):
        self.rounds.append(('wait', status))
        return SimpleNamespace(is_success=False, status=status)

    def round_retry(self, status=None, data=None, wait=None):
        self.rounds.append(('retry', status))
        return SimpleNamespace(is_success=False, status=status)

    def round_fail(self, status=None, data=None, wait=None):
        self.rounds.append(('fail', status))
        return SimpleNamespace(is_success=False, status=status)

    def save_screenshot(self, prefix: str = '') -> str:
        self.shots.append(prefix)
        return f'{prefix}.png'


class _ScriptedOp:
    """execute() 按剧本吐结果的替身 op( OperationResult 形:success/status)。

    剧本耗尽后重复末项(超出剧本的额外分发仍可驱动)。
    """

    def __init__(self, script: list[bool]):
        self._script = script
        self.calls = 0

    def execute(self):
        ok = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        return SimpleNamespace(success=ok,
                               status='' if ok else '演示fail(无判读形态)')


def _dispatch(host, op, journal_name: str, **kwargs):
    return CwLoop._dispatch_screen_op(host, op, journal_name=journal_name,
                                      frame_tag=None, wait=2, **kwargs)


# (原 test_tick_window_semantics 删:纯函数窗口语义被锁2/3/4 的接线级
#  断言完全辖——同键 ok 复位/异键 ok 闭窗计数从 1 重计/达限转 fail,单层
#  归因价值不及冗余成本。)


def test_cap_fires_at_limit_with_readout(monkeypatch):
    """锁2 接线:上限-1 次维持默认映射,第 LIMIT 次转可判读 round_fail。"""
    calls = _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    op = _ScriptedOp([False] * limit)
    for _ in range(limit - 1):
        _dispatch(host, op, '选择伙伴')
        assert host.rounds[-1][0] == 'wait'   # 上限内维持既有默认映射
    result = _dispatch(host, op, '选择伙伴')
    assert host.rounds[-1][0] == 'fail'
    assert '选择伙伴' in result.status   # op 行名进 status(可判读)
    assert host.shots == ['op_fail_cap']   # 留证恰一次
    # 分发与 [cw-op] 行一比一(出口即落,末行为 fail)
    assert len(calls) == limit and calls[-1] == ('选择伙伴', 'fail')


def test_intermittent_ok_resets_window(monkeypatch):
    """锁3 间歇 ok 复位:ok 打断后需重新连败 LIMIT 次才触发。

    判据形态:ok 前已积 limit-1 连败;若无复位,ok 后第 1 次 fail 即达限
    (4+1=5)。实测 ok 后 limit-1 次连败全 wait = 计数确已清零,第 limit
    次才触发。
    """
    _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    op = _ScriptedOp([False] * (limit - 1) + [True] + [False] * limit)
    for _ in range(2 * limit - 1):   # (limit-1) fail → ok → (limit-1) fail
        _dispatch(host, op, '选择伙伴')
        assert host.rounds[-1][0] != 'fail'   # ok 打断后不提前触发(已复位)
    _dispatch(host, op, '选择伙伴')   # 复位后第 limit 连败 → 触发
    assert host.rounds[-1][0] == 'fail'


def test_other_op_ok_closes_window(monkeypatch):
    """锁4 异键 ok 同闭窗:其他 op 的 ok 打断粘滞 op 的 fail 序列。"""
    _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    stuck = _ScriptedOp([False] * limit)
    other = _ScriptedOp([True])
    for _ in range(limit - 1):
        _dispatch(host, stuck, '选择伙伴')
    _dispatch(host, other, '备战')   # 异键 ok = 屏幕证实推进 → 整窗归零
    for _ in range(limit - 1):
        _dispatch(host, stuck, '选择伙伴')
        assert host.rounds[-1][0] == 'wait'   # 计数从 1 重计,不提前触发
    _dispatch(host, stuck, '选择伙伴')
    assert host.rounds[-1][0] == 'fail'


def test_dedicated_hook_shadows_cap(monkeypatch):
    """锁5 hook 早退先于通用网:hook 返回自身轮次 → 恒 hook 结果且不计数。"""
    _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    op = _ScriptedOp([False] * 20)

    def _guard(ok: bool, _res) -> object:
        if not ok:
            return host.round_fail(status='hook 早退形态(短路通用网)')
        return None

    for _ in range(CwLoop.OP_FAIL_REDISPATCH_LIMIT + 3):
        result = CwLoop._dispatch_screen_op(
            host, op, journal_name='备战', frame_tag=None, wait=1,
            on_result=_guard)
        assert result.status == 'hook 早退形态(短路通用网)'
    assert getattr(host, '_op_fail_streak_n', 0) == 0   # hook 早退路径零计数


def test_on_fail_retry_branch_capped_before_retry_pool(monkeypatch):
    """锁6 on_fail_retry 分支同辖:达限转 round_fail,不再进 400 重试池。"""
    _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    op = _ScriptedOp([False] * (limit + 2))
    for _ in range(limit - 1):
        _dispatch(host, op, '策划事件', on_fail_retry=True)
        assert host.rounds[-1][0] == 'retry'   # 上限内维持既有 retry 语义
    _dispatch(host, op, '策划事件', on_fail_retry=True)
    assert host.rounds[-1][0] == 'fail'   # 达限显式停


# ===== 追加(三审代-2 升应修):出战链 {slot:下标} 对位防线 =====
# 病理:容器槽位表存在重复/越界槽号时 `_cidx_of = {b.slot: i}` 字典推导
# 静默保留后值 → CwActionDeployMoveParam 对位同槽号另一条目、拖错人出场。修 = 判据
# 单一源 bench_slots_healthy(槽号健康不变量)前置门:不健康 →
# 整份部署计划 fail-closed 不出 + cw4 分键显影。
# (P3 锁载体迁移:计划单一源迁 mandate_v1/deploy_plan,分键随迁改名
# deploy_plan_slot_table_unhealthy,断言面不变。)

_KEY_UNHEALTHY = 'deploy_plan_slot_table_unhealthy'


def _bcd_host(monkeypatch, bench_slots, counters):
    """`_battle_chain_deploy_moves` 离线宿主:容器读口给真读口喂桩容器、
    mandate 计划段桩化(select 返回指定 up_idx),锁定对位门行为
    (镜像恢复路由锁的替身纪律)。"""
    from types import SimpleNamespace as _NS

    import sr_od.application.currency_war.kernel.cw_game_state as _gs_mod
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        deploy_plan as _dp_mod,
    )

    gs = _NS(node=_NS(value=None), back_layout=_NS(value=None),
             deploy_cap=_NS(value=None), gold=_NS(value=10),
             level=_NS(value=5), front_row=_NS(value=None),
             back_row=_NS(value=None))
    session = StrategySession()
    session.strategy_state = _NS(cw4_counters=counters)
    monkeypatch.setattr(_gs_mod, 'game_state_of', lambda s: gs)
    monkeypatch.setattr(_gs_mod, 'bench_slots_of', lambda b: bench_slots)
    monkeypatch.setattr(_dp_mod, '_deploy_plan_inputs',
                        lambda *a, **k: {})
    return session


@pytest.mark.parametrize('bench_slots', [
    [BenchChar(slot=1, char_id='花火', faction='风'),
     BenchChar(slot=1, char_id='艾丝妲', faction='光')] + [None] * 7,
    [BenchChar(slot=10, char_id='花火', faction='风')],
], ids=['duplicate-slot', 'out-of-range-slot'])
def test_deploy_chain_unhealthy_slot_table_fails_closed(monkeypatch, bench_slots):
    """锁8/9 槽号不健康(重复/越界)→ 整份计划不出(遮蔽通道 fail-closed)
    + 分键显影——单一 bench_slots_healthy 门,两形态同分支数据变体
    (参数化合并,原两独立测试删并)。"""
    from sr_od.application.currency_war.operations.cw_loop import (
        _battle_chain_deploy_moves,
    )

    counters: dict = {}
    session = _bcd_host(monkeypatch, bench_slots, counters)

    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        deploy_plan as _dp_mod,
    )
    monkeypatch.setattr(_dp_mod, 'select_deployments_reasoned',
                        lambda **k: ([0], [], []))   # 计划段有选择,逼入门内

    assert _battle_chain_deploy_moves(session) == []   # 零 CwActionDeployMoveParam
    assert counters[_KEY_UNHEALTHY] == 1   # 显影分键(禁静默降级)


def test_deploy_chain_healthy_table_maps_and_launches(monkeypatch):
    """锁10 健康表直通:门不误伤,对位取容器槽位表下标(bench_idx 语义)。"""
    from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
    from sr_od.application.currency_war.operations.cw_loop import (
        _battle_chain_deploy_moves,
    )

    counters: dict = {}
    bench_slots = ([BenchChar(slot=1, char_id='花火', faction='风'),
                    BenchChar(slot=2, char_id='艾丝妲', faction='光')]
                   + [None] * 7)
    session = _bcd_host(monkeypatch, bench_slots, counters)

    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        deploy_plan as _dp_mod,
    )
    monkeypatch.setattr(_dp_mod, 'select_deployments_reasoned',
                        lambda **k: ([0], [], []))   # 选 bench 下标 0 上场

    moves = _battle_chain_deploy_moves(session)
    assert counters == {}   # 健康表零分键(门未触发)
    assert len(moves) == 1
    assert moves[0].bench_idx == 0   # = 槽号 1 在容器槽位表的下标(非槽号本身)
    assert moves[0].faction == '风'   # faction = 容器槽位表角色对象现取
    assert moves[0].to_row in ('front', 'back')   # 前排保证语义归策略落位单一源
