"""journal 流水装配兜底 + 收口落盘锁(;W3 欠账修复的行为契约)。

锁三件:

1. ``ensure_journal_assembly`` 幂等兜底:未装配 → 按缺省根补装(测试进程
   经 conftest ``_isolate_state_journal`` 重定向 = tmp,证明测试零真实账面
   写入);已装配 → 现役实例原样保留(兜底口不顶掉测试/生产自管装配)。
2. 正主单例建立路径接线(用户裁定 2026-09-15:遥测装配 = game state
   职责;精化令:触发只钉 game_state_of 局容器建立点,GameState 构造器零
   装配逻辑;原「run 领取单点接线」锁随分层纠正重定向至此):建立注入
   ``run_id_provider`` 即装配——行为等价锚 = 未初始化容器首写前装配已发生;
   边界 = 草稿容器直构/一次性空载体/缺省建立(sim/测试口径)与 run 领取层
   (``ensure_run_started``)都不触发装配。
3. 收口落盘:``close_run`` 在批量 flush 阈值之前把缓冲行落盘——批量阈值
   之间收口时档案装配读盘漏局终行的实证形态(g_20260915_070645 档案缺
   ``endgame.match_final``;行随进程终止永失)。

背景实证:2026-09-14 18:56 起 8 连局零 state 行零档案(op 直跑 CwLoop 未经
app 装配段,sink 缺席行按「诚实缺失」静默不落;深检 run_20260915_054718.md
§0)。修法正本 = kernel ``ensure_journal_assembly`` docstring +
``cw_game_state.game_state_of`` 建立路径注释。
"""
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_state_journal import (
    ensure_journal_assembly,
    flush_pending,
    install_state_telemetry,
    reset_state_telemetry,
    state_journal_instance,
)
from sr_od.application.currency_war.telemetry.state import (
    close_run,
    current_run_id,
    ensure_run_started,
    reset_run_state,
    start_run,
)


@pytest.fixture
def _reset_run_cluster() -> None:
    """run 态簇前后复位(telemetry.state 模块全局;防跨测试残留)。"""
    reset_run_state()
    yield
    reset_run_state()


def test_ensure_assembly_installs_at_default_root_when_absent(
        tmp_path: Path) -> None:
    """兜底口双分支:未装配 → 按缺省根补装(测试进程 = conftest 重定向的
    tmp 根);已装配 → 现役实例零成本直过(不 reset 不顶掉,兜底口禁顶掉
    测试/生产自管装配)。"""
    reset_state_telemetry()
    assert state_journal_instance() is None
    ensure_journal_assembly(current_run_id)
    journal = state_journal_instance()
    assert journal is not None
    # conftest 把缺省根缝重定向到本测试的 tmp_path——兜底装配落 tmp,
    # 证明「自动装真实现」在测试进程不触真实账面(测试纪律 2)。
    assert journal.path == tmp_path / 'state' / 'journal.jsonl'
    # 已装配分支:现役实例原样保留
    mine = install_state_telemetry(tmp_path / 'mine' / 'journal.jsonl')
    ensure_journal_assembly(current_run_id)
    assert state_journal_instance() is mine


def test_game_state_establish_wires_assembly() -> None:
    """正主单例建立路径接线:game_state_of 局容器建立注入 run_id_provider
    即装配(重定向原「run 领取单点接线」锁;精化令 2026-09-15:触发
    只钉该建立点,GameState 构造器零装配逻辑;行为等价 = 未初始化容器首写
    前装配已发生)。"""
    reset_state_telemetry()
    assert state_journal_instance() is None
    game_state_of(object(), run_id_provider=current_run_id)
    assert state_journal_instance() is not None


def test_draft_birth_and_run_claim_do_not_wire_assembly(
        _reset_run_cluster: None) -> None:
    """装配边界三支(分层归属 + 精化令):草稿容器直构(GameState
    构造器零装配逻辑)/ 一次性空载体 / 缺省单例建立(sim/测试口径)均不
    装配;run 领取层 ``ensure_run_started`` 只铸 run,不辖装配。"""
    reset_state_telemetry()
    assert state_journal_instance() is None
    GameState(schema_version=GAME_STATE_SCHEMA_VERSION)   # 草稿容器直构:结构性不触发
    game_state_of(None)   # 一次性空载体(局外):不装配
    game_state_of(object())   # 缺省 provider=None 单例建立:不装配
    assert state_journal_instance() is None
    ensure_run_started(match=object(), difficulty='A8')
    assert current_run_id() != ''   # run 领取职责不变(ADR-0588 三分支)
    assert state_journal_instance() is None   # 领取层不辖装配


def test_close_run_flushes_buffered_rows_before_threshold(
        tmp_path: Path, _reset_run_cluster: None) -> None:
    """收口落盘:批量阈值内的缓冲行随 close_run 落盘(装配读盘不漏局终行);
    无装配实例时 flush_pending 恒 0(收口单点在未武装进程零副作用)。"""
    # 未武装进程:flush 零副作用(先于装配,隔离面)
    reset_state_telemetry()
    assert flush_pending() == 0
    jpath = tmp_path / 'journal.jsonl'
    install_state_telemetry(jpath)
    rid = start_run()
    journal = state_journal_instance()
    assert journal is not None
    journal.append({'run_id': rid, 'v': 1, 'row': 'write', 'field': 'gold'})
    assert not jpath.exists()   # 仍在内存缓冲(阈值 64 未到)
    close_run(result='loss', plane_reached=2, rounds_survived=7,
              final_hp=0, notes='auto')
    lines = jpath.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    assert state_journal_instance() is not None   # 收口 flush ≠ 拆装配
