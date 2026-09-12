"""统一 state 动作 op 写入接线(R2 logic_action 渠道)锁面。

设计正本 = ``.debug/temp/currency_war/流程侧遥测-设计v3.1.md``:
- §3.1.1-4/§3.2.5 动作回执域 ``receipts`` = 普通 Field 域(滚动窗容量 8,
  先进先出,帧替换语义);写点 = 各动作 op 执行回执处普通 ``write_logic``
  写入;失败动作也产行(applied=false + reason)——「失败可见性」治本位;
- §3.1.3 表 3-3 回执域渠道准入:② = 唯一合法渠道(logic_action),③ = —;
- §3.2.1 ②渠道 group_id = ``act:<op类名>@<seq>``;
- M1③ 纪律(用户裁定):回执 = 「发出即簿记」不是验证——写点零成败判定,
  applied = 动作 op 自身发出的机械事实透传,禁读屏核验。

开局链写点(R2 §3.4.1 弹窗腿守卫集 prev_branch 供给,cw_loop 侧):
分支标识写点经 :meth:`observe_screen_context` 唯一写口落上下文域(域准入
①obs 家族不破)。守卫集成员终版 = 结算窗 ∪ 开局链{简报,投资环境,等待1-1}
(0p/0q 有专用腿②③出族,用户终裁 2026-09-11,ADR-0630 修订节·守卫族终版)。

常开形态(R5 W1/ADR-0634,原影子纪律作废):回执写点与分支写点写入
无条件(记录被动不分支写路径);行落盘另以 sink/run_id 在场为准。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    RECEIPTS_WINDOW_CAP,
    SCREEN_CONTEXT_GUARD_PREV,
    GameState,
    note_action_receipt,
)
from sr_od.application.currency_war.kernel.cw_state_journal import (
    install_state_telemetry,
    reset_state_telemetry,
)
from sr_od.application.currency_war.kernel.cw_state_journal import (
    state_journal_instance as journal_mod_state_journal_instance,
)
from sr_od.application.currency_war.telemetry import state as tel_state

# ============================================================ fixtures


@pytest.fixture()
def journal(tmp_path):
    """装一份指到 tmp 的状态流水(影子面武装;teardown 复位模块全局)。"""
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=tel_state.current_run_id)
    yield j
    reset_state_telemetry()


@pytest.fixture()
def run_id(monkeypatch):
    """桩一个 run 归属(行内 run_id 键;teardown 由 monkeypatch 自动还原)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_test_receipts')
    return 'run_test_receipts'


@pytest.fixture(autouse=True)
def _reset_journal_default():
    """每条用例前复位影子面 + 登记测试用 actor(防同进程其他测试装配
    残留串染;登记幂等,语义同 R1 锁 test_actor_registration_gate)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        register_sig_actors,
    )
    register_sig_actors('TestActorR2')
    reset_state_telemetry()
    yield
    reset_state_telemetry()


def _receipt_rows(journal) -> list[dict]:
    return [r for r in journal.rows if r['field'] == 'receipts']


def _stub_session():
    """裸 session 桩(board_state_of 旁表惰性建,测试隔离纪律:零真实副作用)。"""
    return SimpleNamespace()


# ============================================================ receipts 域(helper 锁,§3.1.1-4/§3.2.5)


def test_bs_schema_receipts_domain_registered() -> None:
    """§3.7.1 域登记:receipts 域入 bs_schema(缺域键 = 该域未建模,禁占位)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.bs_schema.get('receipts') == 1
    assert RECEIPTS_WINDOW_CAP == 8, '设计 §3.1.1-4:滚动窗容量 8'


def test_receipt_row_channel_and_shape(journal, run_id) -> None:
    """回执行 = 普通 write_logic 写入行:field='receipts',渠道② logic_action
    (域准入 ②=✓ 唯一合法族),group_id = act:<actor>@<seq>(§3.2.1 ②格式)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    note_action_receipt(bs, op='SellBench', applied=True,
                        reason='', screen='货币战争-备战',
                        actor='PrepActionExecutor')
    rows = _receipt_rows(journal)
    assert len(rows) == 1, '逐动作 op 一条 logic_action 行'
    row = rows[0]
    assert row['row'] == 'write'
    assert row['sig']['family'] == 'logic_action'
    assert row['sig']['mode'] == 'compute'
    assert row['sig']['actor'] == 'PrepActionExecutor'
    assert row['sig']['group_id'].startswith('act:PrepActionExecutor@')
    # after = 写入后的完整滚动窗(帧替换语义;新回执 = 窗尾)
    assert row['after'][-1]['op'] == 'SellBench'
    assert row['after'][-1]['applied'] is True
    # 行内自足:state 快照含同一窗
    assert row['state']['values']['receipts'] == row['after']
    assert bs.receipts.value == row['after']


def test_receipt_window_fifo_capacity_eight(journal, run_id) -> None:
    """滚动有界列表容量 8,先进先出(§3.1.1-4):超出淘汰最老回执。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    for i in range(10):
        note_action_receipt(bs, op=f'Op{i}', applied=True, actor='TestActorR2')
    window = bs.receipts.value
    assert len(window) == RECEIPTS_WINDOW_CAP
    assert [r['op'] for r in window] == [f'Op{i}' for i in range(2, 10)], \
        '先进先出:最老两条被淘汰,窗序 = 写入序'


def test_receipt_failure_visibility_no_success_judgment(journal, run_id) -> None:
    """失败可见性(§3.2.5):applied=false + reason 也产行;写点零成败判定
    (M1③ 发出即簿记——applied/reason 由调用方机械事实透传,本口不读屏
    不核验,extra 结构化字段原样入回执)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    note_action_receipt(bs, op='OpenBox', applied=False,
                        reason='无补给箱', screen='货币战争-备战',
                        actor='PrepActionExecutor')
    note_action_receipt(
        bs, op='RefreshShop', applied=False,
        reason='skipped:max_cap(刷新硬墙,计划未尝试)',
        actor='CwOpBuyCards',
        extra={'plan_truncated': True, 'refresh_skipped': 'max_cap'})
    rows = _receipt_rows(journal)
    assert [r['after'][-1]['applied'] for r in rows] == [False, False], \
        '失败动作也产行(exec_events「正在蒸发的失败数据」收编)'
    assert rows[0]['after'][-1]['reason'] == '无补给箱'
    last = rows[1]['after'][-1]
    assert last['plan_truncated'] is True and last['refresh_skipped'] == 'max_cap', \
        '执行面结构化字段入回执(§3.2.1 质量词表执行面承接)'


def test_receipt_no_journal_no_rows_field_still_written(tmp_path, monkeypatch) -> None:
    """常开化后形态(R5 W1 影子闸折叠,ADR-0634;锁语义重推,原「影子关 =
    回执零写入零版本消费」作废):无流水实例 = 行不落零文件,但回执域照常
    写入、版本照常分配——记录被动,不分支写路径(与 match_final 写口
    「未装配 = 行不落而事件照发」同语义)。"""
    reset_state_telemetry()
    assert journal_mod_state_journal_instance() is None
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_off')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    note_action_receipt(bs, op='SellBench', applied=True, actor='TestActorR2')
    assert bs.receipts.value is not None and len(bs.receipts.value) == 1, \
        '无实例 = 行不落而回执域照常写入'
    assert bs.current_version() == 1, '版本照常分配'
    assert not (tmp_path / 'state').exists()


def test_receipt_out_of_match_rejected(journal, monkeypatch) -> None:
    """局外拒写(§3.2.3):run_id 空 = 不写假行(诚实缺失);回执写点与
    观察流同分层——行被拒,容器写入本体照常(版本照常分配,R1 锁
    test_run_id_empty_rejects_rows 同款语义,两锁互为印证)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', '')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    note_action_receipt(bs, op='SellBench', applied=True, actor='TestActorR2')
    assert journal.rows == [], '局外不写假行'
    assert bs.current_version() == 1, '容器写入本体照常(版本照常分配)'


# ============================================================ prep 执行器接线(逐动作 op 一锁)


_ACTION_CASES: list = [
    'ClickSpheres', 'OpenBox', 'OpenTome', 'PickBoxCard', 'SellBench',
    'SellDeployed', 'DeployMove', 'LevelUp', 'EnsureShopOpen',
    'EnsureShopClosed', 'StartBattle', 'RunDeploy', 'RunEquip', 'RunTools',
    'DeferSpheres', 'BailToOuter',
]


def _make_action(name: str):
    """按动作类型名构造最小动作实例(参数取合法域内值;仅过接线,不进真分派)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        BailToOuter,
        ClickSpheres,
        DeferSpheres,
        DeployMove,
        EnsureShopClosed,
        EnsureShopOpen,
        LevelUp,
        OpenBox,
        OpenTome,
        PickBoxCard,
        RunDeploy,
        RunEquip,
        RunTools,
        SellBench,
        SellDeployed,
        StartBattle,
    )
    return {
        'ClickSpheres': lambda: ClickSpheres(max_k=1),
        'OpenBox': OpenBox,
        'OpenTome': OpenTome,
        'PickBoxCard': PickBoxCard,
        'SellBench': lambda: SellBench(slot=1),
        'SellDeployed': lambda: SellDeployed(row='front', slot=1),
        'DeployMove': lambda: DeployMove(from_slot=1, to_row='front', to_slot=1),
        'LevelUp': LevelUp,
        'EnsureShopOpen': EnsureShopOpen,
        'EnsureShopClosed': EnsureShopClosed,
        'StartBattle': StartBattle,
        'RunDeploy': RunDeploy,
        'RunEquip': RunEquip,
        'RunTools': RunTools,
        'DeferSpheres': DeferSpheres,
        'BailToOuter': lambda: BailToOuter(reason='测试'),
    }[name]()


def _make_executor(session, monkeypatch):
    """接线级执行器桩:跳过重 __init__(screen_loader 依赖),分派面替换为
    可控行为——被测对象 = execute() 完成点的回执接线,非各 handler 机械体。"""
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor

    executor = PrepActionExecutor.__new__(PrepActionExecutor)
    executor._op = SimpleNamespace()
    executor._ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session),
                                    run_context=None)
    executor.last_detail = ''
    # 发出位副作用面(mandate 登记件/期望态登记)桩化为 no-op:本锁面对准
    # 回执接线,非登记件语义(其自身面有专锁;测试隔离纪律 = 桩化整条链)。
    from sr_od.application.currency_war.kernel import cw_exec_state
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        mandate as _mandate,
    )
    monkeypatch.setattr(_mandate, 'mark_equip_pass_executed',
                        lambda *a, **k: None)
    monkeypatch.setattr(_mandate, 'mark_tools_pass_executed',
                        lambda *a, **k: None)
    monkeypatch.setattr(_mandate, 'mark_s1_route_check', lambda *a, **k: None)
    monkeypatch.setattr(cw_exec_state, 'apply_op_effect',
                        lambda *a, **k: None)
    return executor


@pytest.mark.parametrize('action_name', _ACTION_CASES)
def test_prep_executor_one_receipt_per_action_op(
        action_name, journal, run_id, monkeypatch):
    """逐动作 op 一锁(R2 任务书 §4):prep_actions 动作全集每个动作 op 经
    execute() 恰产出一条 logic_action 回执行,applied = 发出事实透传。"""
    session = _stub_session()
    executor = _make_executor(session, monkeypatch)
    action = _make_action(action_name)
    monkeypatch.setattr(executor, '_execute_dispatch',
                        lambda a: (f'{type(a).__name__} 摘要', True))
    executor.execute(action)
    rows = _receipt_rows(journal)
    assert len(rows) == 1, f'{action_name}: 每动作 op 恰一条回执行'
    row = rows[0]
    assert row['sig']['family'] == 'logic_action', '渠道②(域准入表 3-3)'
    assert row['after'][-1]['op'] == action_name
    assert row['after'][-1]['applied'] is True
    assert row['after'][-1]['screen'] == '货币战争-备战'
    assert row['after'][-1]['detail'] == f'{action_name} 摘要', \
        '机械执行摘要随回执在账(做了什么可判读)'


@pytest.mark.parametrize('action_name', ['SellBench', 'LevelUp', 'StartBattle'])
def test_prep_executor_receipt_failure_visible(
        action_name, journal, run_id, monkeypatch):
    """失败可见性锁:动作未发出(执行前输入契约拒绝)也在账可见——
    applied=false + reason=机械摘要,行照写;写点零成败判定(不读屏核验)。"""
    session = _stub_session()
    executor = _make_executor(session, monkeypatch)
    action = _make_action(action_name)
    monkeypatch.setattr(executor, '_execute_dispatch',
                        lambda a: ('找不到出战按钮', False))
    executor.execute(action)
    rows = _receipt_rows(journal)
    assert len(rows) == 1, '未发出也簿记(exec_events 失败可见性收编)'
    receipt = rows[0]['after'][-1]
    assert receipt['op'] == action_name
    assert receipt['applied'] is False
    assert receipt['reason'] == '找不到出战按钮'


def test_prep_executor_stop_brake_no_receipt(journal, run_id, monkeypatch):
    """W209j 停机短路:执行被拒(动作未进分派)→ 零回执行(停机非动作)。"""
    from sr_od.application.currency_war.prep_actions import (
        StopBrakeShortCircuit,
    )

    session = _stub_session()
    executor = _make_executor(session, monkeypatch)

    def _brake(a):
        raise StopBrakeShortCircuit('已停止[W209j刹车]')

    monkeypatch.setattr(executor, '_execute_dispatch', _brake)
    with pytest.raises(StopBrakeShortCircuit):
        executor.execute(_make_action('StartBattle'))
    assert _receipt_rows(journal) == [], '执行被拒 = 无动作发生,不产行'


# ============================================================ 商店动作接线(run_buy_waves 单一写点)


def test_shop_action_receipt_channel(journal, run_id) -> None:
    """商店动作 op 回执:渠道② logic_action、actor=CwOpBuyCards、
    screen=商店面板(exec_events 动作族×画面词表承接)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import BuyCard, ShopCard
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        note_shop_action_receipt,
    )

    session = _stub_session()
    match = SimpleNamespace(session=session)
    action = BuyCard(card=ShopCard(name='银狼', faction='贝洛伯格', cost=3,
                                   x=100))
    note_shop_action_receipt(match, action, applied=True)
    rows = _receipt_rows(journal)
    assert len(rows) == 1
    row = rows[0]
    assert row['sig']['family'] == 'logic_action'
    assert row['sig']['actor'] == 'CwOpBuyCards'
    receipt = row['after'][-1]
    assert receipt['op'] == 'BuyCard' and receipt['applied'] is True
    assert receipt['screen'] == '货币战争-备战-开商店'


def test_shop_action_receipt_blocked_paths_visible(journal, run_id) -> None:
    """受阻/放弃也簿记(exec_events 词表 blocked/放弃族):硬墙跳过与
    政策闸拒均产 applied=false 行,携带执行面结构化字段。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        RefreshShop,
        SellBench,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        note_shop_action_receipt,
    )

    match = SimpleNamespace(session=_stub_session())
    note_shop_action_receipt(
        match, RefreshShop(), applied=False,
        reason='skipped:max_cap(刷新硬墙,计划未尝试)',
        extra={'plan_truncated': True, 'refresh_skipped': 'max_cap'})
    note_shop_action_receipt(
        match, SellBench(bench_idx=0, expect='x', income=1), applied=False,
        reason='blocked:spend_gate:测试拒因',
        extra={'blocked': 'spend_gate'})
    rows = _receipt_rows(journal)
    assert [r['after'][-1]['applied'] for r in rows] == [False, False]
    assert rows[0]['after'][-1]['refresh_skipped'] == 'max_cap'
    assert rows[1]['after'][-1]['blocked'] == 'spend_gate'


def test_shop_receipt_wiring_single_choke_point() -> None:
    """接线源面锁:run_buy_waves 三个挂点(执行落地/硬墙/闸拒)都走
    note_shop_action_receipt 单一写点(防第二实现漂移)。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_op import cw_op_buy_cards

    src = inspect.getsource(cw_op_buy_cards)
    assert 'applied=bool(_ok)' in src, \
        '执行落地挂点在 _aop.execute 单一执行点'
    assert src.count('note_shop_action_receipt(') >= 4, \
        '执行/硬墙/闸拒三挂点齐(逐动作 op 一行,受阻路径也簿记;含定义 1 处)'


# ============================================================ 开关店原子接线


class _StubRoundResult:
    def __init__(self, success: bool, status: str, retry: bool = False):
        self.success = success
        self.status = status
        self.is_success = success
        self.retry = retry


class _StubShopOp:
    """open_shop/close_shop 宿主 op 桩(round_by_* 可控;零真实 IO)。"""

    def __init__(self, *, shop_open: bool = False, click_ok: bool = True):
        self.ctx = SimpleNamespace(cw_match=SimpleNamespace(
            session=_stub_session()))
        self._shop_open = shop_open
        self._click_ok = click_ok

    def screenshot(self):
        return object()

    def round_by_find_area(self, *a, **k):
        return _StubRoundResult(self._shop_open, 'anchor')

    def round_by_find_and_click_area(self, *a, **k):
        return _StubRoundResult(self._click_ok, 'click')

    def park_cursor(self, *a, **k):
        return None

    def round_success(self, status: str = '', **k):
        return _StubRoundResult(True, status)

    def round_retry(self, status: str = '', **k):
        return _StubRoundResult(True, status, retry=True)

    def round_fail(self, status: str = '', **k):
        return _StubRoundResult(False, status)


@pytest.mark.parametrize('mode', ['click_issued', 'already_open', 'not_found'])
def test_open_shop_receipt_all_exits(mode, journal, run_id, monkeypatch):
    """开商店原子三出口全簿记:点击已发 = applied=true;幂等已开/入口观察
    失败 = applied=false + reason(动作没发出也在账可见)。"""
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_op.cw_op_open_shop.time.sleep',
        lambda s: None)
    from sr_od.application.currency_war.operations.cw_op.cw_op_open_shop import (
        open_shop,
    )

    op = _StubShopOp(shop_open=(mode == 'already_open'),
                     click_ok=(mode != 'not_found'))
    open_shop(op)
    rows = _receipt_rows(journal)
    assert len(rows) == 1, f'{mode}: 恰一条回执行'
    receipt = rows[0]['after'][-1]
    assert receipt['op'] == 'CwOpOpenShop'
    applied_expect = {'click_issued': True, 'already_open': False,
                      'not_found': False}[mode]
    assert receipt['applied'] is applied_expect
    if mode != 'click_issued':
        assert receipt['reason'], '未发出出口必带 reason(失败可见性)'


@pytest.mark.parametrize('mode', ['click_issued', 'already_closed'])
def test_close_shop_receipt_all_exits(mode, journal, run_id, monkeypatch):
    """关商店原子两出口全簿记(幂等对称;点击已发/已关无动作)。"""
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_op.cw_op_close_shop.time.sleep',
        lambda s: None)
    from sr_od.application.currency_war.operations.cw_op.cw_op_close_shop import (
        close_shop,
    )

    op = _StubShopOp(shop_open=(mode == 'click_issued'),
                     click_ok=(mode == 'click_issued'))
    close_shop(op)
    rows = _receipt_rows(journal)
    assert len(rows) == 1
    receipt = rows[0]['after'][-1]
    assert receipt['op'] == 'CwOpCloseShop'
    assert receipt['applied'] is (mode == 'click_issued')


# ============================================================ 开局链写点(cw_loop 侧;弹窗腿 prev_branch 供给)


def test_guard_set_opening_chain_members_complete() -> None:
    """守卫族成员终版锁(用户终裁 2026-09-11,ADR-0630 修订节·守卫族终版):守卫族 =
    结算窗 ∪ 开局链{简报,投资环境,等待1-1};**0p/0q 出族**——二者有专用腿
    ②③(规则②位面过渡/规则③BOSS简报),守卫族残留其成员会与专用腿构成
    级联双推进(专用腿推进后弹窗腿再 +1,缓存守卫只是掩码)。
    【R1.2 锁语义重推】本锁前身为 R2「开局链五成员」形态(R1.1 曾把 0p 列入
    守卫族,E12 边序勘误),随规则③落码与守卫族收缩更新;写点本体(cw_loop
    五分支)不受影响——分支写点仍供上下文域,只是 0p/0q 不再作弹窗腿 prev
    判据成员。"""
    for member in ('货币战争-战斗等待', '货币战争-简报',
                   '货币战争-投资环境', '货币战争-等待1-1'):
        assert member in SCREEN_CONTEXT_GUARD_PREV, \
            f'守卫集缺成员 {member}(弹窗腿 S1/S3 形态漏判据)'
    for leg_own in ('货币战争-BOSS简报', '货币战争-位面过渡'):
        assert leg_own not in SCREEN_CONTEXT_GUARD_PREV, \
            f'{leg_own} 有专用腿②③,守卫族残留 = 级联双推进破口(ADR-0630 修订节·守卫族终版)'


def test_opening_chain_write_arms_popup_leg_s1(journal, run_id) -> None:
    """S1 开局形态(判定方案 §3.6):开局链分支写点供 prev_branch → 商店
    面板先被采到 → 弹窗腿推断候选 1(等 1-1 ∈ 守卫集是本链判据)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    # cw_loop 分支写点同款输入(0r 简报 → 等待1-1;observe_screen_context 唯一写口)
    bs.observe_screen_context('货币战争-简报')
    bs.observe_screen_context('货币战争-等待1-1')
    # 开局补给动画期间商店面板先被采到(funnel prep_shop_open → 开商店块)
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_ord.value == 1, '开局无前值 → 候选 1(弹窗腿)'
    assert bs.node_hist_ord == 1
    ctx_rows = [r for r in journal.rows if r['field'] == 'current_screen']
    assert [r['after'] for r in ctx_rows] == [
        '货币战争-简报', '货币战争-等待1-1', '货币战争-备战-开商店'], \
        '开局链分支标识逐分支在账(prev_branch 供给面)'


def test_cw_loop_branch_writepoints_wired(journal, run_id, monkeypatch):
    """cw_loop 开局链五分支写点在位(0p/0q/0r/0s×2);行为 = 上下文对
    (域准入 ①obs 家族,actor=CwLoop);常开形态 = 写入无条件
    (R5 W1 影子闸折叠,ADR-0634——原「影子关零调用」段作废,改锁
    「无实例 = 行不落而上下文照常写入」)。"""
    # —— 源面:五分支写点字面在位(最小侵入面锚,防静默脱落)——
    import inspect

    from sr_od.application.currency_war.operations.cw_loop import CwLoop

    src = inspect.getsource(CwLoop)
    for branch in ('货币战争-BOSS简报', '货币战争-位面过渡', '货币战争-简报',
                   '货币战争-投资环境', '货币战争-等待1-1'):
        assert f"_note_branch_screen('{branch}')" in src, \
            f'cw_loop 缺分支写点 {branch}(prev_branch 供给断供)'

    # —— 行为:写入无条件(上下文对入账);无实例 = 行不落而写入照常 ——
    loop = CwLoop.__new__(CwLoop)
    session = _stub_session()
    loop.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    loop._note_branch_screen('货币战争-BOSS简报')
    bs = journal_mod_board_state(session)
    assert bs.current_screen.value == '货币战争-BOSS简报'
    assert bs.prev_screen.value == '', '开局前 prev 为空串(R1 §3.1.4 语义)'
    ctx_rows = [r for r in journal.rows if r['field'] == 'current_screen']
    assert ctx_rows[-1]['sig']['family'] == 'obs'
    assert ctx_rows[-1]['sig']['actor'] == 'CwLoop'

    reset_state_telemetry()
    bs2 = journal_mod_board_state(session)
    loop._note_branch_screen('货币战争-简报')
    assert bs2.current_screen.value == '货币战争-简报', \
        '无流水实例 = 行不落而上下文照常写入(常开形态,记录被动)'


def journal_mod_board_state(session):
    from sr_od.application.currency_war.kernel.cw_game_state import (
        board_state_of,
    )
    return board_state_of(session)


# ============================================================ 序列化形态


def test_receipt_window_json_safe_in_snapshot(journal, run_id) -> None:
    """回执窗随全量快照 JSON 安全化(行行自足;dict 窗序列化不炸)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    note_action_receipt(bs, op='SellBench', applied=False, reason='无补给箱',
                        screen='货币战争-备战', actor='TestActorR2')
    row = journal.rows[-1]
    payload = json.dumps(row['state']['values']['receipts'],
                         ensure_ascii=False)
    assert '无补给箱' in payload
