"""T-266 外环 op-fail 重派防线上限锁(2026-09-15)。

病理(选择伙伴 15 连败,2026-09-15 事故):画面 op 退出 fail → 外环
``_dispatch_screen_op`` 默认映射 round_wait(零预算)→ 同分支每帧再命中
→ 同一 op 无界重派,直到 NODE-DWELL 900s 系统哨兵兜住。op 层有界化
(T-264「确认被拒」显式 fail)后,外环仍对无判读 fail 空转。修 = 环级
连续 fail 上限:同一分发 op 连续 fail 达 ``CwLoop.OP_FAIL_REDISPATCH_
LIMIT`` → round_fail 显式停交上层。

锁的六件事:
1. 计数窗口语义(纯函数):ok 整窗归零(fail 间歇重置)/同键 fail 累加/
   异键 fail 换情节从 1 起算;
2. 包装接线:连续 fail 至上限-1 仍走默认 round_wait,第 LIMIT 次转
   round_fail(status 含 op 行名可判读)+ 留证截图恰一次 + journal
   enter/exit 每次分发成对;
3. 间歇 ok 复位:fail 窗内穿插任一 ok → 计数清零,后续 fail 从 1 重计,
   不提前触发;
4. 异键 ok 同闭窗:粘滞 op 的 fail 序列被**其他** op 的 ok 打断 → 该 op
   计数一并清零(跨情节残留不毒化新情节);
5. 专用守卫先于通用网:on_result 在 fail 时返回自身轮次结果(0q/prep
   streak 守卫形态)→ 恒返回 hook 的结果,且 hook 早退路径不进通用网
   计数(结构性不抢占);
6. on_fail_retry 分支同辖:fail 达上限转 round_fail(不再消耗 400 节点
   重试池),上限内维持既有 round_retry 语义。

附:上限值组合性质锁(LIMIT ≥ 0j/0q 专用阈值,= prep streak 阈值 5,
零新拍定值的推导锁)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
from sr_od.application.currency_war.operations.cw_loop import (
    CwLoop,
    op_fail_redispatch_tick,
)


def _spy_journal(monkeypatch) -> list[str]:
    """桩掉 journal 写入(测试零真实副作用)+ 留出口行序列供配对断言。"""
    exits: list[str] = []
    monkeypatch.setattr(cw_loop_mod, 'record_op_enter',
                        lambda name, *a, **k: {'op': name})
    monkeypatch.setattr(cw_loop_mod, 'record_op_exit',
                        lambda token, outcome='ok', **k: exits.append(outcome))
    return exits


class _Host:
    """``_dispatch_screen_op`` 离线宿主:只供给包装消费面(round 工厂/
    留证/位置键/上限值),镜像 T-230 恢复路由锁的替身纪律。

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

    def _op_journal_pos(self) -> tuple[int, int]:
        return (0, 0)


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


def test_tick_window_semantics():
    """锁1 计数窗口语义:ok 归零/同键累加/异键换情节(纯函数)。"""
    assert op_fail_redispatch_tick(None, 0, 'A', True) == (None, 0)
    assert op_fail_redispatch_tick('A', 3, 'A', True) == (None, 0)
    assert op_fail_redispatch_tick(None, 0, 'A', False) == ('A', 1)
    assert op_fail_redispatch_tick('A', 2, 'A', False) == ('A', 3)
    assert op_fail_redispatch_tick('A', 4, 'B', False) == ('B', 1)


def test_cap_fires_at_limit_with_readout(monkeypatch):
    """锁2 接线:上限-1 次维持默认映射,第 LIMIT 次转可判读 round_fail。"""
    exits = _spy_journal(monkeypatch)
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
    assert len(exits) == limit and exits[-1] == 'fail'   # 分发与出口行成对


def test_intermittent_ok_resets_window(monkeypatch):
    """锁3 间歇 ok 复位:ok 打断后需重新连败 LIMIT 次才触发。

    判据形态:ok 前已积 limit-1 连败;若无复位,ok 后第 1 次 fail 即达限
    (4+1=5)。实测 ok 后 limit-1 次连败全 wait = 计数确已清零,第 limit
    次才触发。
    """
    _spy_journal(monkeypatch)
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
    _spy_journal(monkeypatch)
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
    """锁5 专用守卫先于通用网:hook 返回自身轮次 → 恒 hook 结果且不计数。"""
    _spy_journal(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    op = _ScriptedOp([False] * 20)

    def _guard(ok: bool, _res) -> object:
        if not ok:
            return host.round_fail(status='专用守卫形态(0q/prep streak)')
        return None

    for _ in range(CwLoop.OP_FAIL_REDISPATCH_LIMIT + 3):
        result = CwLoop._dispatch_screen_op(
            host, op, journal_name='备战', frame_tag=None, wait=1,
            on_result=_guard)
        assert result.status == '专用守卫形态(0q/prep streak)'
    assert getattr(host, '_op_fail_streak_n', 0) == 0   # hook 早退路径零计数


def test_on_fail_retry_branch_capped_before_retry_pool(monkeypatch):
    """锁6 on_fail_retry 分支同辖:达限转 round_fail,不再进 400 重试池。"""
    _spy_journal(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    op = _ScriptedOp([False] * (limit + 2))
    for _ in range(limit - 1):
        _dispatch(host, op, '策划事件', on_fail_retry=True)
        assert host.rounds[-1][0] == 'retry'   # 上限内维持既有 retry 语义
    _dispatch(host, op, '策划事件', on_fail_retry=True)
    assert host.rounds[-1][0] == 'fail'   # 达限显式停


def test_limit_derivation_invariant():
    """锁7 上限组合性质:≥ 全部专用守卫阈值,= prep streak 阈值 5。"""
    assert CwLoop.OP_FAIL_REDISPATCH_LIMIT >= CwLoop.FRONTLESS_REDEPLOY_LIMIT
    assert CwLoop.OP_FAIL_REDISPATCH_LIMIT >= CwLoop.PLANE_MISDISPATCH_LIMIT
    # prep 环 _director_fail_streak 阈值 5(loop._on_prep_round 内字面量):
    # 通用网取同值 → 平手时 hook 先返回,结构性不抢占专用守卫。
    assert CwLoop.OP_FAIL_REDISPATCH_LIMIT == 5
