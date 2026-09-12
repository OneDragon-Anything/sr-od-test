"""备战执行缝金账包络锁(T-16 备战帧金动作漏账修复批;旧账 T-306)。

定谳与出处(持久索引):备战帧 m3 经验批 ``LevelUp``(-20 金)不经执行缝
账务入账的机制定谳 = ``.debug/progress/2026-09-06-currency-war-redesign/
reviews/T-234-落地审.md``(归层 = 执行/遥测账务包络层:journal 动作回执/
outcome 计数/spend_executed 三套账只辖商店单元);任务凭据 = 当前迭代
``dag.jsonl`` T-16 criteria;修复语义 = ``PrepActionExecutor.execute``
执行点金差显影 + receipts 域结构化 ``gold_delta`` + 容器金账直推(写通道
单一源 = ``cw_exec_state._advance_gold``);金额公式单一源 = kernel
``xp_click_cost``/``sell_refund``/``bench_char_cost``。

T-234 验收义务兑现位:
- P2「另立备战帧金账锁(对备战帧全部金动作的独立记账对账,非仅净负
  报警)」= 本文件逐动作归属锁:金额全部由 kernel 公式在测试侧独立重算
  对拍(不经假环境 verification 回执,非同义反复),声明盲区(收球金/
  身份不可辨)禁拍值锁死;
- P3「锁出处回填持久指针」:本 docstring 即本锁持久锚。

被测对象 = 生产 ``execute()`` 包装半边(机械半边 ``_execute_dispatch``
按假环境 harness 同款方式替身;替身保真生产 handler 的 tracked 同步时序
——卖出发出即销账,防 apply_op_effect 卖入腿双记账)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
    exec_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    LevelUp,
    SellBench,
    SellDeployed,
)
from sr_od.application.currency_war.kernel.cw_state_journal import (
    install_state_telemetry,
    reset_state_telemetry,
)
from sr_od.application.currency_war.prep_actions import PrepActionExecutor
from sr_od.application.currency_war.telemetry import state as tel_state

#: 金账包络对拍的期初金(容器 gold 播种值;非注册表量,测试编排值)。
_OPEN_GOLD: int = 60


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
    """桩 run 归属(receipts 行落盘门;teardown 由 monkeypatch 还原)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_t16_gold')
    return 'run_t16_gold'


@pytest.fixture()
def op_journal_rows(tmp_path, monkeypatch):
    """op_journal 落盘重定向 tmp(test_cw_op_journal 同款缝),返回行读取
    helper(备战域 journal 回执腿的断言输入)。"""
    import json

    from sr_od.application.currency_war.telemetry import op_journal as oj
    out = tmp_path / 'op_journal.jsonl'
    monkeypatch.setattr(oj, '_JOURNAL', out)
    monkeypatch.setattr(oj, '_frame_seq_by_run', {})

    def _rows() -> list[dict]:
        if not out.exists():
            return []
        return [json.loads(x)
                for x in out.read_text(encoding='utf-8').splitlines()]

    return _rows


@pytest.fixture(autouse=True)
def _reset_telemetry():
    """每用例复位影子面 + 登记测试 actor(同 test_cw_state_action_receipts
    先例;登记幂等,防跨文件装配残留串染)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        register_sig_actors,
    )
    register_sig_actors('T16TestActor')
    reset_state_telemetry()
    yield
    reset_state_telemetry()


# ============================================================ 装配 helpers


def _make_session() -> SimpleNamespace:
    """裸 session 桩(board_state_of 旁表惰性建;零真实副作用)。"""
    return SimpleNamespace()


def _seed_gold(session, value: int = _OPEN_GOLD) -> None:
    """容器金播种(prior 渠道:测试编排的环境初值,非观察事实)。"""
    board_state_of(session).write_prior(
        board_state_of(session).gold, value,
        evidence='prior:t16-envelope-seed',
        sig=ChannelSig(family='obs', actor='T16TestActor'))


def _gold_of(session) -> int | None:
    return board_state_of(session).gold.value


def _receipt_rows(journal) -> list[dict]:
    return [r for r in journal.rows if r['field'] == 'receipts']


def _last_receipt(journal) -> dict:
    rows = _receipt_rows(journal)
    assert rows, '回执行缺位(执行缝回执接线断裂)'
    return rows[-1]['after'][-1]


def _make_executor(session: SimpleNamespace, monkeypatch) -> PrepActionExecutor:
    """接线级执行器桩(__new__ 免 screen_loader 依赖;发出位 mandate 登记件
    桩化 no-op——被测面 = 金账包络,登记件语义有专锁,测试隔离 = 桩化整条
    副作用链,test_cw_state_action_receipts 同款先例)。apply_op_effect
    **不桩**(其卖入腿是本包络的既有面,双记账防线正是被测语义)。"""
    ex = PrepActionExecutor.__new__(PrepActionExecutor)
    ex._op = SimpleNamespace()
    ex._ctx = SimpleNamespace(
        cw_match=SimpleNamespace(session=session), run_context=None)
    ex.last_detail = ''
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        mandate as _mandate,
    )
    monkeypatch.setattr(_mandate, 'mark_equip_pass_executed',
                        lambda *a, **k: None)
    monkeypatch.setattr(_mandate, 'mark_tools_pass_executed',
                        lambda *a, **k: None)
    monkeypatch.setattr(_mandate, 'mark_s1_route_check', lambda *a, **k: None)
    return ex


def _stub_sync_sell_bench(session, action: SellBench) -> tuple[str, bool]:
    """卖出机械半边替身:保真生产 handler 发出即 tracked 销账时序
    (_track_remove_bench;销账缺失会让 apply_op_effect 卖入腿再推一次
    = 双记账,替身禁省此步)。"""
    es = exec_state_of(session)
    es.tracked_bench_chars = [
        b for b in (es.tracked_bench_chars or [])
        if b is None or b.slot != action.slot]
    return f'卖备战槽{action.slot} ✓', True


def _stub_sync_sell_deployed(session, action: SellDeployed) -> tuple[str, bool]:
    """上阵卖出替身(同上;deployed 置 None 不移位,ADR-0392 槽表语义)。"""
    from sr_od.application.currency_war.kernel.cw_exec_state import (
        DEPLOYED_FRONT_CAPACITY,
    )
    es = exec_state_of(session)
    tracked = list(es.tracked_deployed or [])
    idx = (action.slot - 1 if action.row == 'front'
           else DEPLOYED_FRONT_CAPACITY + action.slot - 1)
    if 0 <= idx < len(tracked):
        tracked[idx] = None
    es.tracked_deployed = tracked
    return f'卖{action.row}排{action.slot} ✓', True


# ============================================================ 逐动作归属锁


def test_levelup_gold_books_envelope(journal, run_id, monkeypatch,
                                     op_journal_rows):
    """m3 经验批形态:LevelUp 发出 → 三账齐入(journal 备战动作行 + 回执
    结构化 gold_delta + 金账直推)。金额 = kernel 公式测试侧独立重算
    (机械半边回报花金 20 = 5 击 × 4,与 T-234 定谳剧本同量级),红 =
    执行缝仍漏账(定谳缺口回潮)。"""
    session = _make_session()
    _seed_gold(session)
    ex = _make_executor(session, monkeypatch)

    def _dispatch(action):
        # 机械半边替身:回报实击花金(生产 = _level_up 逐击 xp_click_cost 累计)
        ex._last_levelup_spent = 20
        return '买经验授权5击实击5花金20(基线 level 8)', True

    monkeypatch.setattr(ex, '_execute_dispatch', _dispatch)
    ex.execute(LevelUp())
    assert _gold_of(session) == _OPEN_GOLD - 20, \
        '金账直推:备战 LevelUp 花金入容器账(漏账定谳缺口闭合)'
    receipt = _last_receipt(journal)
    assert receipt['op'] == 'LevelUp' and receipt['applied'] is True
    assert receipt['gold_delta'] == -20, \
        '回执域结构化金差:逐动作归属可判(P2 独立金账锁语义)'
    assert ex.last_gold_delta == -20, '执行点显影镜像供观察侧对账'
    # —— journal 回执腿(T-234 定谳「备战帧 5 击零 journal 行」缺口闭合)
    rows = op_journal_rows()
    assert len(rows) == 1, '备战动作恰一条 journal 行'
    row = rows[0]
    assert row['kind'] == 'action'
    assert row['op'] == '货币战争-备战动作', \
        '域分键:与商店「货币战争-买牌」分行,复盘金动归属直读'
    assert row['action']['__type__'] == 'LevelUp'
    assert row['exec_ok'] is True and row['gold_delta'] == -20
    assert row['run_id'] == run_id and row['seq'] == 0, \
        '备战域无段序账(seq 恒 0,行序即时序)'


def test_sell_bench_gold_books_envelope(journal, run_id, monkeypatch,
                                        op_journal_rows):
    """卖备战槽:回金入账(金额 = sell_refund×bench_char_cost kernel 重算
    对拍,非同义反复);tracked 销账后 apply_op_effect 卖入腿不再重复推进
    (双记账防线)。"""
    session = _make_session()
    _seed_gold(session)
    bc = BenchChar(slot=1, char_id='花火', star=2, position_pref='back')
    exec_state_of(session).tracked_bench_chars = [bc]
    ex = _make_executor(session, monkeypatch)
    monkeypatch.setattr(ex, '_execute_dispatch',
                        lambda a: _stub_sync_sell_bench(session, a))
    action = SellBench(slot=1)
    ex.execute(action)
    refund = sell_refund(2, bench_char_cost(bc))
    assert refund > 0
    assert _gold_of(session) == _OPEN_GOLD + refund, \
        '卖出回金入容器账(恰好一次:直推 + 卖入腿不重复)'
    assert _last_receipt(journal)['gold_delta'] == refund
    rows = op_journal_rows()
    assert len(rows) == 1 and rows[0]['gold_delta'] == refund, \
        'journal 行携卖出回金金差'


def test_sell_deployed_gold_books_envelope(journal, run_id, monkeypatch,
                                           op_journal_rows):
    """卖上阵角色:回金入账(deployed 槽表下标换算 = 前排 slot-1)。"""
    session = _make_session()
    _seed_gold(session)
    bc = BenchChar(slot=1, char_id='希儿', star=1, position_pref='front')
    exec_state_of(session).tracked_deployed = [bc]
    ex = _make_executor(session, monkeypatch)
    monkeypatch.setattr(ex, '_execute_dispatch',
                        lambda a: _stub_sync_sell_deployed(session, a))
    ex.execute(SellDeployed(row='front', slot=1))
    refund = sell_refund(1, bench_char_cost(bc))
    assert _gold_of(session) == _OPEN_GOLD + refund
    assert _last_receipt(journal)['gold_delta'] == refund
    assert op_journal_rows()[0]['gold_delta'] == refund


# ============================================================ 诚实缺失锁


def test_unidentified_sell_no_fabricated_book(journal, run_id, monkeypatch,
                                              op_journal_rows):
    """身份不可辨(char_id 空)→ 回金不可算 = 诚实缺失:零金账、零金差键
    (禁按保守估值拍账;观察覆盖兜底,T-234 P2「漏没修全不可知」防线的
    对偶面——宁缺勿造假账)。journal 行照落(动作事实在账)但无金差键。"""
    session = _make_session()
    _seed_gold(session)
    exec_state_of(session).tracked_bench_chars = [
        BenchChar(slot=1, char_id='', star=2)]
    ex = _make_executor(session, monkeypatch)
    monkeypatch.setattr(ex, '_execute_dispatch',
                        lambda a: _stub_sync_sell_bench(session, a))
    ex.execute(SellBench(slot=1))
    assert _gold_of(session) == _OPEN_GOLD, '不可算不推账(诚实缺失)'
    receipt = _last_receipt(journal)
    assert receipt['applied'] is True
    assert 'gold_delta' not in receipt, '无显影 = 无金差键(非 0 假账)'
    rows = op_journal_rows()
    assert len(rows) == 1 and 'gold_delta' not in rows[0], \
        'journal 行照落(动作事实)但无金差键'


def test_click_spheres_gold_declared_blind_spot(journal, run_id, monkeypatch,
                                                op_journal_rows):
    """收球金 = 声明盲区:通道随机执行点不可推算 → 零金账零金差键
    (禁拍值;apply_op_effect 盲区申报同源,观察覆盖兜底)。"""
    session = _make_session()
    _seed_gold(session)
    ex = _make_executor(session, monkeypatch)
    monkeypatch.setattr(ex, '_execute_dispatch',
                        lambda a: ('点球 3/3(动画等待 2s)', True))
    ex.execute(ClickSpheres(max_k=3))
    assert _gold_of(session) == _OPEN_GOLD, '盲区不推账'
    assert 'gold_delta' not in _last_receipt(journal)
    assert len(op_journal_rows()) == 1, '动作行照落(收球事实在账)'
    assert 'gold_delta' not in op_journal_rows()[0]


def test_unemitted_action_no_books(journal, run_id, monkeypatch,
                                   op_journal_rows):
    """未发出(执行前契约拒绝/拖拽未过)→ 无金动无账:零直推、零金差键、
    零 journal 行(失败可见性走 applied=false 回执通道,金账面诚实归零;
    journal「未执行动作零行」与商店域同语义)。"""
    session = _make_session()
    _seed_gold(session)
    exec_state_of(session).tracked_bench_chars = [
        BenchChar(slot=1, char_id='花火', star=2)]
    ex = _make_executor(session, monkeypatch)
    monkeypatch.setattr(
        ex, '_execute_dispatch',
        lambda a: ('卖备战槽1 拖3次源槽未变', False))   # 未销账,同真 handler
    ex.execute(SellBench(slot=1))
    assert _gold_of(session) == _OPEN_GOLD, '未发出零金账'
    receipt = _last_receipt(journal)
    assert receipt['applied'] is False
    assert 'gold_delta' not in receipt
    assert op_journal_rows() == [], '未发出零 journal 行'


def test_mechanical_half_missing_report_honest_missing(journal, run_id,
                                                       monkeypatch,
                                                       op_journal_rows):
    """机械半边未报数(LevelUp emitted 但 _last_levelup_spent 未置)→
    诚实缺失:零金账零金差键(显影供给缺位禁拍 0,防「假报平账」)。"""
    session = _make_session()
    _seed_gold(session)
    ex = _make_executor(session, monkeypatch)
    monkeypatch.setattr(ex, '_execute_dispatch',
                        lambda a: ('买经验(替身未回报花金)', True))
    ex.execute(LevelUp())
    assert _gold_of(session) == _OPEN_GOLD
    assert 'gold_delta' not in _last_receipt(journal)
    assert 'gold_delta' not in op_journal_rows()[0]


def test_journal_prep_row_outside_match_writes_nothing(tmp_path, monkeypatch):
    """局外门控:run_id 空 → 备战动作零 journal 行(不写假键,两域同规)。"""

    from sr_od.application.currency_war.telemetry import op_journal as oj
    out = tmp_path / 'op_journal.jsonl'
    monkeypatch.setattr(oj, '_JOURNAL', out)
    monkeypatch.setattr(oj, '_frame_seq_by_run', {})
    monkeypatch.setattr(oj, 'current_run_id', lambda: '')
    session = _make_session()
    _seed_gold(session)
    ex = _make_executor(session, monkeypatch)
    monkeypatch.setattr(ex, '_execute_dispatch',
                        lambda a: _stub_sync_sell_bench(session, a))
    ex.execute(SellBench(slot=1))
    assert not out.exists(), '局外零行'


# ============================================================ 结构锁


def test_sell_handlers_emit_only_on_landed_drag():
    """卖出 handler 发出诚实性结构锁:拖拽未过(源槽像素验失败)必须返回
    emitted=False——失败卖出若记 True,执行缝金账会把未发生的回金入账
    (apply_op_effect 卖入腿按 tracked 复查推进 + 直推腿 = 双幻记账)。
    字面锚 = 两 handler 返回位的 ``ok`` 透传;复活字面 True = 红。"""
    for name in ('_sell_bench', '_sell_deployed'):
        src = inspect.getsource(getattr(PrepActionExecutor, name))
        assert ", True)" not in src, (
            f'{name}: 拖拽失败必须透传 ok(未发出),字面 True = 幻记账回归')
