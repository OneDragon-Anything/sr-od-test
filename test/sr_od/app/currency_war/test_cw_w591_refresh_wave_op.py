"""刷新波 op 级行为锁(W591 补 W573 欠账:fixture 帧驱动完整 execute)。

锁的链路:**plan 发射 RefreshShop → 期望生成(producer)→ 刷新点击 → 两帧
一致门 → 刷后重读 → 对账消费 → 台账行**。被测 = 真实 ``BuyShopCards.buy``
节点完整 ``execute()``(op 级,非纯函数);仅替身观测输入与计划源:

- ``read_game_state`` / ``read_gold_opt`` / ``read_gold`` / ``read_shop_cards``
  按剧本逐次返回(替身 OCR;真实 OCR 依赖存档帧,离线不可控刷新前后差异);
- ``decide_prep`` 替身策略:第一轮 ``[RefreshShop]``、第二轮 ``[]``
  (模拟「刷新后重 plan 无进一步动作」的两阶段收束);
- 框架找钮/OCR 判定替身成功(备战锚)/失败(其余),shop 开态由替身点击
  「按钮-商店」直接成立——这些属画面判定,不是本锁对象;
- ``cw_telemetry.record_defect`` 捕获替身 + recorder 指向 tmp(台账隔离,
  test_cw_w536 同手法);``cw_observation_gate.wait_stable_frame`` 替身
  (gate 是既有单帧锁对象)。

锁两条链(出处:观测自检框架设计 §2.5 + prep_director.build_refresh_expect
docstring 契约 + ADR-0456 免费刷新事后正证据通道):

1. **正常刷新一帧链**:producer 以基价常量构建(金 10−2=8)→ 点击落
   「按钮-刷新」→ 实读金 8/牌面已变 → 对账零票、台账零行、无免费 proc;
2. **免费生效帧链**:牌面已变 ∧ 点后金=点前金(10)→ 免费刷新 proc 通道
   触发(FREE-REFRESH-PROC 留证文案写出,不停机)→ 对账落一条金腿票
   (期望 8 vs 实读 10;免费不是失败,票=留证)。

producer 期望在**波内**构建的契约(先例=W573 源码锁)在本文件升为行为
验证:spy 记录 build/reconcile 调用,断言次序 build → 点击 → reconcile。

W592 追加锁③④(ADR-0456 勘误注):买+刷新同波两形态——before 名集
改为点击前现读后,真落空 → 未变(not_effective 停线面),真免费 →
已变(free_refresh_proc 采证不停);修复前落空形态必被误判免费。
"""
from __future__ import annotations

import pathlib
from typing import Any

import pytest

from sr_od.application.currency_war.telemetry import recorder
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.kernel.cw_obs_core import SHOP_SCREEN_NAME
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import (
    CurrencyWarMatch,
    StrategySession,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_PREP = '货币战争-备战'
_ANCHOR = (_PREP, '备战标识-购买经验')

_OLD_NAMES = ['希儿', '景元', '布洛妮娅', '克拉拉', '杰帕德']
_NEW_NAMES = ['白露', '彦卿', '姬子', '瓦尔特', '三月七']


def _shop_cards(names: list[str]) -> list[ShopCard]:
    return [ShopCard(x=i, faction='?', name=n, cost=3, star=1)
            for i, n in enumerate(names)]


def _state(gold: int, names: list[str]) -> GameState:
    return GameState(gold=gold, plane=1, round_num=5, level=5,
                     shop=_shop_cards(names))


class _StubStrategy:
    """替身计划源:按调用次序吐剧本 plan(耗尽后重复最后一个)。"""

    def __init__(self, plans: list[list[Any]]):
        self._plans = plans
        self.calls = 0

    def update_target(self, state, session, config) -> None:
        pass

    def decide_prep(self, state, session, config) -> list[Any]:
        acts = self._plans[min(self.calls, len(self._plans) - 1)]
        self.calls += 1
        return acts


def _make_op(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
             tmp_path: pathlib.Path, plans: list[list[Any]],
             states: list[GameState], gold_opts: list[int | None],
             shop_reads: list[list[str]], events: list[str]) -> Any:
    """装配被测 op + 全部替身(观测输入/计划源/台账隔离/找钮判定)。

    返回 (op, fixture_controller, defect_rows)。``gold_opts`` 是
    read_gold_opt 的逐次返回(耗尽后重复最后一个);``states`` 同型;
    ``shop_reads`` 是 read_shop_cards 的逐次返回(名列表)。
    读序语义随 W891 候选①(执行边界压缩,报告
    .debug/temp/currency_war/w891_c1_buy_edge/REPORT.md §1.4)重推:
    - 仅刷新波:波循环顶整帧读即点击前现读(无买卡污染),**不再有
      独立 pre-shot 读** → read_shop_cards 第 1 次 = 刷后重读;
    - 买+刷新波(W592 语义不变):第 1 次 = 点击前现读,第 2 次 =
      刷后重读;read_gold_opt 第 1 次 = 点击前现读金,第 2 次 = 刷后金。
    """
    from sr_od.application.currency_war.obs import cw_observation as cwo
    from sr_od.application.currency_war.obs import cw_observation_gate as gate
    from sr_od.application.currency_war import prep_director as pd
    from sr_od.application.currency_war.operations.prep import shop as shop_mod
    from sr_od.application.currency_war.operations.prep.shop import BuyShopCards

    class _Watched(WatchdogOperationMixin, BuyShopCards):
        pass

    # 台账隔离(不写真实 .debug;test_cw_w536 手法)。
    # 分包期 6 单例归家:_RECORDER/run_id 单例簇唯一拥有者=telemetry.state
    # (recorder 模块不再持单例;get_recorder 走 state 属性读)
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True,
                                                   replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'w591t')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    defect_rows: list[tuple] = []

    def _cap_defect(*args: Any, **kwargs: Any) -> Any:
        defect_rows.append((args, kwargs))
        return None

    monkeypatch.setattr(defects, 'record_defect', _cap_defect)

    # 顺序替身读数(逐次消耗,耗尽后恒最后一个)
    seq_idx: dict[str, int] = {}

    def _make_seq(seq: list):
        tag = f'seq{id(seq)}'

        def _read(*args: Any, **kwargs: Any):
            i = seq_idx.get(tag, 0)
            seq_idx[tag] = i + 1
            return seq[min(i, len(seq) - 1)]
        return _read

    monkeypatch.setattr(shop_mod, 'read_game_state', _make_seq(states))
    monkeypatch.setattr(shop_mod, 'read_gold_opt', _make_seq(gold_opts))
    # gold 差值对拍(关店后 stylized 读):正常链读 8 与期望一致,零冲突
    monkeypatch.setattr(shop_mod, 'read_gold',
                        lambda *a, **k: gold_opts[min(1, len(gold_opts) - 1)])
    _shop_seq = _make_seq(shop_reads)
    monkeypatch.setattr(shop_mod, 'read_shop_cards',
                        lambda *a, **k: _shop_cards(_shop_seq()))
    # W592:执行事实暂存槽捕获(分类器观测面 refresh_board_changed 的
    # 执行侧真值直接在此断言,不经台账二次解析)
    facts: list[dict] = []
    monkeypatch.setattr(cw_telemetry, 'set_unit_exec_facts',
                        lambda **k: facts.append(k))
    monkeypatch.setattr(cwo, 'read_hp_opt', lambda *a, **k: None)
    monkeypatch.setattr(cwo, 'read_phase_round', lambda *a, **k: (1, 5))
    # gate 替身(单帧锁另有对象;此处只求离线直过)
    monkeypatch.setattr(gate, 'wait_stable_frame', lambda *a, **k: None)

    # producer / reconcile spy(锁次序 build → 点击 → reconcile)
    _real_build = pd.build_refresh_expect
    _real_reconcile = pd.refresh_reconcile_mismatches

    def _spy_build(*args: Any, **kwargs: Any):
        events.append('build')
        return _real_build(*args, **kwargs)

    def _spy_reconcile(*args: Any, **kwargs: Any):
        events.append('reconcile')
        return _real_reconcile(*args, **kwargs)

    monkeypatch.setattr(pd, 'build_refresh_expect', _spy_build)
    monkeypatch.setattr(pd, 'refresh_reconcile_mismatches', _spy_reconcile)

    # 无对局 → 挂替身 match(plan 源替身 + 全新 session)
    monkeypatch.setattr(test_context, 'cw_match',
                        CurrencyWarMatch(_StubStrategy(plans),
                                         StrategySession()))

    # fixture 控制器(替身游戏:记录 click;单帧恒同 → 两帧一致门秒过)
    fc = FixtureController(test_context)
    fc.set_phases([{'frame': (_PREP, 'shop_closed')}])
    monkeypatch.setattr(test_context, 'controller', fc)

    # 画面判定替身:备战锚成功(防空 overlay 误判),其余失败
    op = _Watched(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    monkeypatch.setattr(
        op, 'round_by_find_area',
        lambda screen, screen_name, area_name, **k:
        op.round_success('') if (screen_name, area_name) == _ANCHOR
        else op.round_fail(''))
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda screen, screen_name, area_name, **k:
                        op.round_success(''))
    monkeypatch.setattr(op, 'round_by_ocr', lambda *a, **k: op.round_fail(''))
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: '<shot>')
    return op, fc, defect_rows, facts


def _execute(op) -> Any:
    enter_running_state(op.ctx)
    try:
        with fast_sleep():
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


@pytest.fixture()
def _require_fixture(test_context: SrTestContext) -> None:
    if not test_context.has_screen(_PREP, 'shop_closed'):
        pytest.skip(f'存档截图缺失:screens/{_PREP}/shop_closed.webp')


def test_refresh_wave_normal_chain(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _require_fixture,
) -> None:
    """锁①正常刷新一帧链:producer 基价期望 → 点击落刷新钮 → 对账零票。

    链路语义(出处=build_refresh_expect docstring 契约):期望以
    REFRESH_COST_BASE 基价在波内构建(10−2=8)→ 点击 → 刷后实读金 8、
    牌面已变 → 对账零票、台账零行、无免费 proc 留证。
    (W891 候选①后仅刷新波刷前现读复用波循环顶读,替身序列见
    _make_op docstring;牌面已变 = 刷后重读相对波顶读。)
    """
    events: list[str] = []
    op, fc, rows, _facts = _make_op(
        test_context, monkeypatch, tmp_path,
        plans=[[RefreshShop(cost=2)], []],
        states=[_state(10, _OLD_NAMES),
                _state(8, _NEW_NAMES), _state(8, _NEW_NAMES)],
        gold_opts=[8, 8], shop_reads=[_NEW_NAMES, _NEW_NAMES], events=events)

    result = _execute(op)

    assert result.success, f'刷新波单元应正常收工:status={result.status!r}'
    # 链路次序:期望生成 → 刷新点击 → 对账消费
    assert events == ['build', 'reconcile'], f'链路次序漂移: {events}'
    assert fc.click_hit_area(SHOP_SCREEN_NAME, '按钮-刷新'), (
        f'刷新点击未落「按钮-刷新」:{[str(p) for p in fc.recorded_clicks]}')
    # 对账零票(金 8==8、牌腿有身份牌),台账零行
    assert rows == [], f'正常刷新不应落台账: {rows}'


def test_refresh_wave_free_refresh_proc_chain(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _require_fixture,
) -> None:
    """锁②免费生效帧链:牌面已变 ∧ 金未扣 → 免费 proc 留证 + 金腿票。

    语义(ADR-0456 免费刷新事后正证据通道):点击已发、牌面已变、
    点后金=点前金 → 免费刷新 proc 真实发生,写 FREE-REFRESH-PROC 留证
    (不停机);对账按期望基价口径落一条金腿票(期望 8 vs 实读 10,
    免费不是失败,票=留证);牌面已变 → 无刷新未生效 invariant_break。
    flag 落盘经 pathlib.Path.write_text 捕获替身(测试纪律:不写真实
    .debug;窗口内其它 Path.write_text 一并被吞,本测试不经文件断言
    其它台账,record_defect 走捕获替身不受影响)。
    """
    events: list[str] = []
    writes: list[str] = []
    _real_write = pathlib.Path.write_text

    def _spy_write(self: pathlib.Path, data: Any, *args: Any, **kwargs: Any):
        writes.append(str(data))
        return len(data)

    monkeypatch.setattr(pathlib.Path, 'write_text', _spy_write)

    op, fc, rows, _facts = _make_op(
        test_context, monkeypatch, tmp_path,
        plans=[[RefreshShop(cost=2)], []],
        states=[_state(10, _OLD_NAMES),
                _state(10, _NEW_NAMES), _state(10, _NEW_NAMES)],
        gold_opts=[10, 10], shop_reads=[_NEW_NAMES, _NEW_NAMES], events=events)

    result = _execute(op)

    assert result.success, f'免费刷新链不应停机:status={result.status!r}'
    assert fc.click_hit_area(SHOP_SCREEN_NAME, '按钮-刷新')
    # 免费 proc 留证文案已产出(事件通道写入,未落真实盘)
    assert any('FREE-REFRESH-PROC' in w for w in writes), (
        f'免费刷新 proc 留证未产出;writes={writes[:3]}')
    # 对账:恰好一条金腿票(期望 8 vs 实读 10);无牌面未生效票
    assert events == ['build', 'reconcile'], f'链路次序漂移: {events}'
    kinds = [k[0][1] for k in rows]
    assert kinds == ['refresh_expect_mismatch'], f'台账行漂移: {kinds}'
    assert rows[0][0][0] == 'shop' and rows[0][0][1] == 'refresh_expect_mismatch'
    assert not any(k[0][1] == 'invariant_break' for k in rows), (
        '牌面已变时不应落刷新未生效票')


# ===== W592:买+刷新波 before 名集现读锁(ADR-0456 勘误注) =====

def _bought_wave_plan() -> list[list[Any]]:
    """买+刷新同波 plan:买「希儿」(x=0, 3金)后刷新(基价 2)。"""
    return [[BuyCard(card=ShopCard(x=0, faction='?', name='希儿',
                                   cost=3, star=1)),
             RefreshShop(cost=2)], []]


# 游戏侧买后「希儿」离场:现读帧该槽为空(''),其余 4 牌不变
_POST_BUY = ['', '景元', '布洛妮娅', '克拉拉', '杰帕德']


def test_buy_refresh_wave_real_miss_not_effective(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _require_fixture,
) -> None:
    """锁③买+刷新波真落空 → 牌面未变 → not_effective 形态(停线面)。

    W590 缺陷形态(修复前必错):state.shop(plan 读)仍含已买牌,而
    现读画面买后即离场——刷新落空时「plan 读 vs 点击后实读」集合必不等,
    被误判 free_refresh_proc(不停+写假采证 flag)。修复后 before 名集 =
    点击前现读 → 落空=相对点击前未变 → False → 落刷新未生效票,执行
    事实 refresh_board_changed=False 透传分类器(not_effective 停)。
    """
    events: list[str] = []
    writes: list[str] = []

    def _spy_write(self: pathlib.Path, data: Any, *args: Any, **kwargs: Any):
        writes.append(str(data))
        return len(data)

    monkeypatch.setattr(pathlib.Path, 'write_text', _spy_write)
    op, fc, rows, facts = _make_op(
        test_context, monkeypatch, tmp_path,
        plans=_bought_wave_plan(),
        states=[_state(10, _OLD_NAMES), _state(10, _OLD_NAMES),
                _state(10, _OLD_NAMES), _state(10, _OLD_NAMES)],
        gold_opts=[10, 10],   # 落空:金未扣
        shop_reads=[_POST_BUY, _POST_BUY],   # 点击前后牌面全同
        events=events)

    result = _execute(op)

    assert result.success, f'落空波单元仍应正常收工(停线由安灯消费):{result.status!r}'
    assert fc.click_hit_area(SHOP_SCREEN_NAME, '按钮-刷新')
    assert facts and facts[0]['refresh_attempted'] is True
    # 落空形态:已买空槽使刷后读含未识别槽('')→ 判据不可判(None,不猜
    # ——ADR-0456 有锁禁把 None 当已变);关键在分类器不得落 free_refresh_proc。
    assert facts[0]['refresh_board_changed'] is not True, (
        f'真落空不得判「已变」(修复前此形态必误判 True):{facts}')
    # 分类器端到端:计划花费 5(买3+刷2)∧ 金差 0 ∧ 刷后读含 '' 不可判
    # → not_effective 停线(修复前被洗成 free_refresh_proc 不停+假采证)。

    from sr_od.application.currency_war.telemetry.query import classify_spend_unit
    verdict = classify_spend_unit(
        [{'__type__': 'BuyCard', 'card': {'x': 0, 'name': '希儿', 'cost': 3}},
         {'__type__': 'RefreshShop', 'cost': 2}],
        10, 10, executed=facts[0])
    assert verdict['verdict'] == 'not_effective', verdict
    # 刷新面不落「已变」系票,且不得产出免费 proc 假采证
    assert not any(k[0][0] == 'shop_refresh' and k[0][1] == 'invariant_break'
                   for k in rows), f'落空波不应落「已变」票: {rows}'
    assert not any('FREE-REFRESH-PROC' in w for w in writes), (
        '真落空不得写免费 proc 假采证')


def test_buy_refresh_wave_real_free_proc(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _require_fixture,
) -> None:
    """锁④买+刷新波真免费 → free_refresh_proc 形态(不停+采证)。

    修复后语义:牌面已变=相对点击前现读(已买槽空剔除后)——真免费时
    刷出新牌 → changed=True ∧ 金未扣 → 免费 proc 留证不停;不落全同票。
    """
    events: list[str] = []
    writes: list[str] = []

    def _spy_write(self: pathlib.Path, data: Any, *args: Any, **kwargs: Any):
        writes.append(str(data))
        return len(data)

    monkeypatch.setattr(pathlib.Path, 'write_text', _spy_write)
    op, fc, rows, facts = _make_op(
        test_context, monkeypatch, tmp_path,
        plans=_bought_wave_plan(),
        states=[_state(10, _OLD_NAMES), _state(10, _OLD_NAMES),
                _state(10, _NEW_NAMES), _state(10, _NEW_NAMES)],
        gold_opts=[10, 10],   # 免费:金未扣
        shop_reads=[_POST_BUY, _NEW_NAMES],   # 点击前含已买空槽,刷后全新牌
        events=events)

    result = _execute(op)

    assert result.success, f'免费刷新链不应停机:{result.status!r}'
    assert fc.click_hit_area(SHOP_SCREEN_NAME, '按钮-刷新')
    assert facts and facts[0]['refresh_board_changed'] is True, (
        f'真免费应判「相对点击前已变」(空槽剔除后):{facts}')
    assert any('FREE-REFRESH-PROC' in w for w in writes), (
        f'免费刷新 proc 留证未产出;writes={writes[:3]}')
    assert not any(k[0][0] == 'shop_refresh' and k[0][1] == 'invariant_break'
                   for k in rows), (
        '刷新面牌面已变时不应落刷新未生效票')

from sr_od.application.currency_war.telemetry import defects
