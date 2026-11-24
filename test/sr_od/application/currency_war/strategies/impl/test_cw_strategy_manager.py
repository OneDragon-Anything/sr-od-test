"""establish_new_match 漏斗与 Match 流程态字段写入测试(镜像锚 =
cw_strategy_manager.py;字段面契约 = cw_strategy.py::CurrencyWarMatch)。

锁设计约定(判据单一源 = 2026-11-19-resume-rebuild design §2.2/§2.4/§2.7;
段序规范 = skill sr-od-dev-currency-war references/journal.md §10):

- ``opened_via`` 开局方式事实:establish 按参数一次写入,运行内不变;
  生产三调用点显式传参——入口链 = 'new_game'(本文件直调
  ``_establish_match_once`` 锁接线)/ loop handle_init 兜底 = 'takeover'
  (归 test_cw_loop 重建矩阵)/ 商店防御兜底 = 'takeover'(归
  test_cw_screen_shop 防御支);
- establish 段序:**先铸 run → 再建容器(种子行)→ 职级就地吸收 → 记
  ``created_run_id``**。run 必须在该容器第一行写入之前铸好,否则开局
  种子行与职级吸收行取「进程当前号」挂进上一个 run(实机新局路径
  「一局双档案 + 职级丢失」的根因)。归属 token = session(kernel 局身份,
  容器建立前即存在)——入口链三分支 ensure 与 loop ``__init__`` ensure 传
  ``ctx.cw_match`` 归一到同一 session = 纯认领,``created_run_id`` 与
  handle_init 时点的 run 恒等(重建判据比对载体不变);
- 职级吸收在铸 run 取走 ctx 前捕获 difficulty 实参(铸段携带难度语义保持);
- ``CurrencyWarMatch`` 裸构造吃缺省值(opened_via='new_game' /
  created_run_id=None / probed=False)= sim 直构两点(skill 脚本
  cw_sim_match_drive.py / 测试 harness sim_backend_runner.py)零改动的
  契约面——缺省方向翻转会让 sim 容器被探针/被重建,设计 §2.7 定稿禁移。

零真实副作用:遥测 run 态簇经 ``reset_run_state`` 前后复位(生产路径
零调用的测试复位正规入口);状态流水落盘根由 conftest autouse 重定向到
tmp;策略器实例化走真实 mandate_v1 注册面(内存注册表,零网络零落盘)。
"""

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.run_id_clock import advancing_run_clock

from sr_od.application.currency_war.currency_war_config import CurrencyWarConfig
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_entry.cw_entry_start import (
    CwEntryStart,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy_manager import (
    establish_new_match,
)
from sr_od.application.currency_war.telemetry import state as cw_state


@pytest.fixture
def cw_run_env(test_context: SrTestContext,
               monkeypatch: pytest.MonkeyPatch) -> SrTestContext:
    """遥测 run 态簇复位夹具:前后各清一次(模块级单例跨测防串染);
    ctx.cw_match / ctx.cw_selected_difficulty 经 monkeypatch 挂拆自动还原。"""
    cw_state.reset_run_state()
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_selected_difficulty', None,
                        raising=False)
    yield test_context
    cw_state.reset_run_state()


def _establish(test_context: SrTestContext,
               opened_via: str) -> CurrencyWarMatch:
    """生产漏斗真跑一次(monkeypatch 挂的 ctx.cw_match=None 前提下必走新建)。"""
    established = establish_new_match(
        test_context, CurrencyWarConfig(test_context.current_instance_idx),
        opened_via)
    assert established, 'ctx.cw_match=None 前提下 establish 应走新建分支'
    return test_context.cw_match


def test_establish_writes_opened_via_and_created_run_id(
        cw_run_env: SrTestContext,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """三段式段1/段3 字段写入:opened_via 按参数一次写入;created_run_id
    = ensure 铸造的当前 run(恒非 None,重建判据载体);probed 缺省 False。"""
    match_new = _establish(cw_run_env, 'new_game')
    assert match_new.opened_via == 'new_game'
    assert match_new.created_run_id == cw_state.current_run_id(), \
        ('created_run_id 应记 ensure 铸造的当前 run(每次运行重建判据载体),'
         f'实际 {match_new.created_run_id!r} vs run={cw_state.current_run_id()!r}')
    assert match_new.probed is False

    # 同一 run 内换开局方式重建(先清容器再漏斗重入):takeover 语义同构。
    # (不锁 created_run_id 字符串不等——run_id 秒级时间戳,同秒内两次铸造
    # 合法同值,「新段」语义由 ensure 的 _RUN_SESSION token 比对承载,
    # 非字符串可辨。)
    monkeypatch.setattr(cw_run_env, 'cw_match', None)
    match_takeover = _establish(cw_run_env, 'takeover')
    assert match_takeover.opened_via == 'takeover'
    assert match_takeover.created_run_id == cw_state.current_run_id()
    assert match_takeover.probed is False


def test_establish_mints_run_before_first_row(
        cw_run_env: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """段序锁:run 在容器第一行写入之前铸好——开局种子行与职级吸收行
    都挂在容器自己的 run(= created_run_id)下、版本自 1 连续;上局已
    收尾的 run 不接收本局任何一行。前置 = 进程里已有一个收尾的上局 run
    + 跨秒时钟(铸号若晚于种子行,种子行取「进程当前号」= 上局号 → 红)。"""
    from sr_od.application.currency_war.kernel import cw_state_journal
    from sr_od.application.currency_war.telemetry.journal_query import (
        read_journal_stats,
    )
    advancing_run_clock(monkeypatch)
    prev_run = cw_state.start_run()
    cw_state.close_run()   # 上局已收尾,但其号仍是进程「当前号」
    monkeypatch.setattr(cw_run_env, 'cw_selected_difficulty', 'A5',
                        raising=False)

    match = _establish(cw_run_env, 'new_game')

    cw_state_journal.flush_pending()
    rows, _stats = read_journal_stats(tmp_path)
    run_ids = {r.get('run_id') for r in rows}
    assert rows and run_ids == {match.created_run_id}, (
        f'容器全部行应挂自己的 run(种子行 + 职级行在铸号之后写入),'
        f'实际 run 集 {sorted(map(str, run_ids))}'
        f' vs created_run_id={match.created_run_id!r}')
    assert prev_run not in run_ids, '上局已收尾的 run 不得再收本局的行'
    assert [r['v'] for r in rows] == list(range(1, len(rows) + 1)), \
        '同号内版本号应自 1 连续不重复'
    assert any(r.get('field') == 'selected_difficulty' and r.get('after') == 'A5'
               for r in rows), '职级吸收行应落在本局 run'


def test_establish_idempotent_keeps_existing_container(
        cw_run_env: SrTestContext) -> None:
    """幂等门:容器已在 → False 直过,不覆盖既有容器(开局方式事实一次
    写入不被二次调用翻写;跨 run 残留容器的弃置归 handle_init 判据)。"""
    match_first = _establish(cw_run_env, 'new_game')
    established_again = establish_new_match(
        cw_run_env, CurrencyWarConfig(cw_run_env.current_instance_idx),
        'takeover')
    assert established_again is False, '容器已在应幂等直过返回 False'
    assert cw_run_env.cw_match is match_first, '幂等直过不得替换既有容器'
    assert cw_run_env.cw_match.opened_via == 'new_game', \
        '幂等直过不得改写既有容器的开局方式事实'


def test_entry_chain_call_site_passes_new_game(
        cw_run_env: SrTestContext) -> None:
    """入口链调用点接线:_establish_match_once 显式传 'new_game'
    (design §2.2 写入端第一处;漏传会让新局容器走探针面,方向禁反)。"""
    op_shell = SimpleNamespace(ctx=cw_run_env)
    CwEntryStart._establish_match_once(op_shell)
    assert cw_run_env.cw_match is not None, '入口链调用点应建立容器'
    assert cw_run_env.cw_match.opened_via == 'new_game', \
        (f'入口链新局确凿信号应写 new_game,'
         f'实际 {cw_run_env.cw_match.opened_via!r}')


def test_match_dataclass_defaults_are_sim_contract(
        cw_run_env: SrTestContext) -> None:
    """裸构造缺省值 = sim 直构契约(design §2.7 定稿方向):opened_via
    缺省 new_game(sim 容器永不进探针分支)/ created_run_id 缺省 None
    (handle_init 保留,不判旧 run 重建)/ probed 缺省 False。缺省翻转的
    直接消费方 = skill 脚本 cw_sim_match_drive.py 与测试 harness
    sim_backend_runner.py 的两处直构(零改动前提)。"""
    bare = CurrencyWarMatch(object(), StrategySession(), None)
    assert bare.opened_via == 'new_game'
    assert bare.created_run_id is None
    assert bare.probed is False
