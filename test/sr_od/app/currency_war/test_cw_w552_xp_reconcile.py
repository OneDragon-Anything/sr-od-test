"""经验期望态对账网(W552:XP/等级期望态对账;架构先例 =
test_cw_w536_buy_expect.py 买牌 / test_cw_w530_drag_reconcile.py 拖动,同族:
意图 → 期望增量 → 稳定帧对账 → 不一致落台账,零决策记账)。

测四类:①推进算子真值表(xp_apply_clicks 普通买/跨级买/结转/封顶;
xp_clicks_to_level 击数)②账本流为(锚定→意图推进→对账→不一致落台账;
轮界重锚吸收外生经验)③接线源码锁④台账行形态锁。全部纯函数/tmp_path,
零触网零落盘真实路径。
"""
import json
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.telemetry import defects, recorder
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_state import (
    XP_TO_NEXT_LEVEL,
    xp_apply_clicks,
    xp_clicks_to_level,
)

from sr_od.application.currency_war.prep_director import PrepDirector

from sr_od.application.currency_war.kernel.cw_prep_expect import XpLedger, _xp_compare, _xp_parse_buy_clicks

# ===== ① 推进算子真值表(单一源语义 = ADR-0129;门槛表 XP_TO_NEXT_LEVEL)=====

def test_xp_apply_clicks_plain():
    """普通买(不跨级):lv5 需 20,0+4 → cur 4 不升级。"""
    assert xp_apply_clicks(5, 0, 1) == (5, 4)
    assert xp_apply_clicks(8, 2, 1) == (8, 6)
    assert xp_apply_clicks(8, 2, 0) == (8, 2)      # 零击零推进
    assert xp_apply_clicks(8, 2, -1) == (8, 2)     # 负数防御:原值返回


def test_xp_apply_clicks_cross_level_carryover():
    """跨级买(结转):lv5 18/20 +1 击 = 22 ≥ 20 → lv6 结转 2/40;
    lv4 4/6 +1 击 = 8 ≥ 6 → lv5 结转 2/20(live 局⑳+1 p1r3 实证段)。"""
    assert xp_apply_clicks(5, 18, 1) == (6, 2)
    assert xp_apply_clicks(4, 4, 1) == (5, 2)


def test_xp_apply_clicks_multi_level():
    """多级连穿:lv4 0 + 12 击 = 48 → 过 lv4(6)剩 42 → 过 lv5(20)剩 22
    < lv6(40)→ lv6 22/40(live 局⑳+1 p2r4 的 LU×12 段语义)。"""
    assert xp_apply_clicks(4, 0, 12) == (6, 22)
    assert XP_TO_NEXT_LEVEL[6] == 40


def test_xp_apply_clicks_level_cap():
    """封顶:lv9 80/84 + 2 击 = 88 → lv10 结转 4;lv10 再击无效(零推进,
    live 语义 = 10 级后购买经验按钮无效)。"""
    assert xp_apply_clicks(9, 80, 2) == (10, 4)
    assert xp_apply_clicks(10, 4, 3) == (10, 4)


def test_xp_clicks_to_level_truth_table():
    """恰升 1 级最少击数 = ceil((need-cur)/4):整除/非整除/已过门槛/封顶。"""
    assert xp_clicks_to_level(5, 0) == 5           # 20/4
    assert xp_clicks_to_level(6, 12) == 7          # ceil(28/4)
    assert xp_clicks_to_level(5, 18) == 1          # 已差 2,1 击即升
    assert xp_clicks_to_level(5, 20) == 1          # 已达门槛,1 击触发
    assert xp_clicks_to_level(10, 0) == 0          # 封顶:零推进


# ===== ② 账本流为(stub director;台账行经 monkeypatch 捕获)=====

def _stub_director() -> tuple[PrepDirector, StrategySession, list[tuple]]:
    """免 SrContext 构造的 PrepDirector:object.__new__ + stub ctx
    (cw_match.session = 真 StrategySession;账本动态属性挂其上)。"""
    session = StrategySession()
    pd = object.__new__(PrepDirector)
    pd.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    captured: list[tuple] = []
    return pd, session, captured


def _cap(*a, **k):
    """record_defect 替身:位置参 (surface, kind, expected, observed) +
    关键字参一并捕获。"""
    return (a, k)


def _obs(xp: tuple[int, int] | None, level: int, plane: int = 2,
         round_num: int = 5) -> PrepObservation:
    return PrepObservation(state=SimpleNamespace(
        xp_progress=xp, level=level, plane=plane, round_num=round_num))


def test_ledger_anchors_then_reconciles_clean(monkeypatch):
    """锚定 → 意图推进 → 同段对账一致:不落台账;锚定前/pending=0 不评。"""
    pd, session, captured = _stub_director()
    monkeypatch.setattr(cw_telemetry, 'record_defect', _cap)
    # 首帧:锚定(2/72 lv8),不对账
    pd._reconcile_xp_expect(_obs((2, 72), 8))
    led = session.xp_expect_ledger
    assert led.anchored and (led.level, led.xp_cur, led.xp_next) == (8, 2, 72)
    assert led.round_key == (2, 5)
    assert captured == []
    # 同帧再读(pending=0)不评
    pd._reconcile_xp_expect(_obs((2, 72), 8))
    assert captured == []
    # RunBuyPhase 升 1 击 → 期望 6/72;显示一致 → 不落台账
    pd._xp_apply_buy_clicks('买牌 plan 买1张 升1次 刷0次 (gold=30 lv=8)')
    assert (led.level, led.xp_cur) == (8, 6) and led.pending_clicks == 1
    pd._reconcile_xp_expect(_obs((6, 72), 8))
    assert captured == [] and led.pending_clicks == 0


def test_ledger_mismatch_lands_defect_once(monkeypatch):
    """显示与账本不一致 → 落一条 xp_expect_mismatch 台账(surface/kind/
    reader_source 形态;pending 清零后同段不重复落)。"""
    pd, session, captured = _stub_director()
    monkeypatch.setattr(cw_telemetry, 'record_defect',
                        lambda *a, **k: captured.append((a, k)))
    pd._reconcile_xp_expect(_obs((2, 72), 8))          # 锚定
    pd._xp_apply_buy_clicks('买牌 plan 买0张 升2次 刷1次')  # 期望 10/72
    pd._reconcile_xp_expect(_obs((6, 72), 8))          # 显示只有 +4
    assert len(captured) == 1
    args, row = captured[0]
    assert args[0] == 'xp' and args[1] == 'xp_expect_mismatch'
    assert row['reader_source'] == 'xp_expect_reconcile'
    assert '10' in row['expected'] and '6' in row['observed']
    assert any(r['field'] == 'pending_clicks' and r['value'] == '2'
               for r in row['refs'])
    # pending 已清:同段再读不重复落
    pd._reconcile_xp_expect(_obs((6, 72), 8))
    assert len(captured) == 1


def test_ledger_levelup_channel_and_level_mismatch(monkeypatch):
    """直接 LevelUp 通道(腾席链循环点至 level+1):击数 = 恰升 1 级;
    等级双源不一致同样落台账(等级 = deploy cap 输入的交叉验证面)。"""
    pd, session, captured = _stub_director()
    monkeypatch.setattr(cw_telemetry, 'record_defect',
                        lambda *a, **k: captured.append((a, k)))
    pd._reconcile_xp_expect(_obs((18, 20), 5, plane=1, round_num=3))
    pd._xp_apply_levelup()                             # 1 击 → lv6 2/40
    led = session.xp_expect_ledger
    assert (led.level, led.xp_cur, led.xp_next) == (6, 2, 40)
    pd._reconcile_xp_expect(_obs((2, 40), 6, plane=1, round_num=3))  # 一致
    assert captured == []
    # 等级不一致形态:显示 lv 仍 5(等级区误读/升级未生效)
    pd._xp_apply_levelup()                             # → lv7 0/52
    pd._reconcile_xp_expect(_obs((0, 52), 6, plane=1, round_num=3))
    assert len(captured) == 1
    args, row = captured[0]
    assert 'level' in row['observed'] and '7' in row['expected']


def test_ledger_round_rollover_reanchors(monkeypatch):
    """轮界 = 重锚点:外生经验流(轮间 +2)吸收进锚点并计入 exogenous_xp
    披露,不落台账(不硬编码外生模型,把未知变实测)。"""
    pd, session, captured = _stub_director()
    monkeypatch.setattr(cw_telemetry, 'record_defect', _cap)
    pd._reconcile_xp_expect(_obs((2, 72), 8))
    pd._xp_apply_buy_clicks('买牌 plan 买0张 升1次 刷0次')   # 期望 6/72
    pd._reconcile_xp_expect(_obs((6, 72), 8))                # 对账一致清 pending
    # 轮界:显示 8/72(本轮 +2 外生)→ 重锚,不评不落账
    pd._reconcile_xp_expect(_obs((8, 72), 8, round_num=6))
    led = session.xp_expect_ledger
    assert led.round_key == (2, 6) and (led.level, led.xp_cur) == (8, 8)
    assert led.exogenous_xp == 2 and captured == []


def test_ledger_no_session_is_noop():
    """无对局态(cw_match=None)→ 账本方法全 no-op(纯观测,不抛)。"""
    pd = object.__new__(PrepDirector)
    pd.ctx = SimpleNamespace(cw_match=None)
    assert pd._xp_ledger() is None
    pd._xp_apply_levelup()
    pd._xp_apply_buy_clicks('升1次')
    pd._reconcile_xp_expect(_obs((2, 72), 8))   # state 非 None 也不抛


def test_xp_compare_truth_table():
    """对账判据纯函数:一致=空;display/level 失读=不评;逐项域分离。"""
    led = XpLedger(level=8, xp_cur=6, xp_next=72)
    assert _xp_compare(led, (6, 72), 8) == []
    assert _xp_compare(led, None, 8) == []          # XP 失读不评
    assert _xp_compare(led, (6, 72), 0) == []       # 等级失读不评
    m = _xp_compare(led, (4, 60), 7)
    assert [x['domain'] for x in m] == ['level', 'xp', 'xp']
    assert [x['slot'] for x in m if x['domain'] == 'xp'] == ['cur', 'next']


def test_parse_buy_clicks():
    """detail 解析:shop 单元摘要形态命中;无升级/异形 → 0(宁缺勿造)。"""
    assert _xp_parse_buy_clicks('买牌 plan 买2张 升3次 刷1次 (gold=30)') == 3
    assert _xp_parse_buy_clicks('买牌 plan 买2张 升0次 刷1次') == 0
    assert _xp_parse_buy_clicks('买牌 (无plan)') == 0
    assert _xp_parse_buy_clicks('') == 0


# ===== ③ 接线源码锁(静态结构,防重构断链/改口径)=====

def test_w552_wiring_locks():
    """①意图推进在 execute 返回后且仅 progressed 分支;②对账在 heavy
    定型帧观察之后(buy_expect 消费点同区域);③台账常量与解析形态锁。"""
    src = Path(
        'src/sr_od/application/currency_war/prep_director.py'
    ).read_text(encoding='utf-8')
    log_at = src.index("log.info(f'[cw][director] step{self._steps}")
    lv_at = src.index('if progressed and isinstance(action, LevelUp):')
    buy_at = src.index("elif progressed and isinstance(action, RunBuyPhase):")
    assert log_at < lv_at < buy_at                  # 进展后才推账,两通道并列
    assert src.index('self._xp_apply_levelup()') > lv_at
    assert src.index("self._xp_apply_buy_clicks(detail)") > buy_at
    obs_at = src.index('self._reconcile_xp_expect(obs)')
    # W591:pending_buy_expect 升 StrategySession 正式字段,消费端由
    # getattr 兜底改直接字段读写(语义不变,机制被取代——见
    # test_cw_w536_buy_expect.test_w536_wiring_locks 改锁依据)
    consume_at = src.index('_pending_buy = session.pending_buy_expect')
    assert consume_at < obs_at                      # heavy 定型帧之后
    assert "_XP_DEFECT_KIND = 'xp_expect_mismatch'" in src
    assert "_XP_DEFECT_SURFACE = 'xp'" in src
    assert "reader_source='xp_expect_reconcile'" in src
    assert "_XP_BUY_CLICKS_PAT = re.compile(r'升(\\d+)次')" in src
    # 推进算子单一源 = cw_state(sim 侧不重复建模)
    state_src = Path(
        'src/sr_od/application/currency_war/kernel/cw_state.py'
    ).read_text(encoding='utf-8')
    assert 'def xp_apply_clicks(' in state_src
    assert 'def xp_clicks_to_level(' in state_src
    # 对账在 anchor 之前不评(锚定前纯推算无起点)
    rec_at = src.index('def _reconcile_xp_expect')
    rec_body = src[rec_at:src.index('def _session')]
    assert 'not led.anchored' in rec_body
    assert 'led.round_key != key' in rec_body       # 轮界重锚在位


# ===== ④ 台账行形态锁(写端真实落盘形态)=====

def test_xp_defect_row_shape(tmp_path: Path, monkeypatch):
    """defect_ledger.jsonl 行形态:surface='xp'/kind='xp_expect_mismatch'。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True,
                                                       replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    defects.record_defect(
        'xp', 'xp_expect_mismatch',
        expected='lv8 xp 10/72(账本;events=+buy×2击)',
        observed='lv8 xp 6/72',
        plane=2, round_num=5, gap_large=True,
        reader_source='xp_expect_reconcile')
    rows = [ln for ln in
            (tmp_path / 'defect_ledger.jsonl').read_text(encoding='utf-8')
            .splitlines() if ln.strip()]
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row['surface'] == 'xp'
    assert row['kind'] == 'xp_expect_mismatch'
    assert row['reader_source'] == 'xp_expect_reconcile'


