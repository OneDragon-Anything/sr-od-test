"""test_cw_shop_refresh 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w510_refreshfee: test_cw_w510_refreshfee.py
- w514_refresh_surface: test_cw_w514_refresh_surface.py
- w564_shop_wire: test_cw_w564_shop_wire.py
- w591_refresh_wave_op: test_cw_w591_refresh_wave_op.py
- w891_buy_edge: test_cw_w891_buy_edge.py
- w944_shop_unk_settle: test_cw_w944_shop_unk_settle.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== w510_refreshfee ====================
from one_dragon.base.operation.operation_node import operation_node
from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
    expected_gold_after_actions,
)


def test_multiwave_refresh_expected_closes_per_accounting():
    """多波刷新对拍闭合语义(瘦身后;原自抄复刻主体已删——旧测试体重抄
    「逐动作累计与 op 内分支同规则」的算术再断言自己,删掉真函数它照样绿,
    违反纪律第 10 条;波间基线/刷费去重的 op 级行为面由 w591 族 fixture
    锁(锁①~④,单波链路)与对账消费面分担,多波端到端无现成宿主)。

    波间语义(3 波场景,开店金 60;刷费 2/波,买 3/波 ×3):对拍期望 =
    开店金 − **逐波执行侧花金合计**(每次刷新的当次刷价只计一次) =
    60 − (3+2+3+2+3) = 47 = 实读。修复前口径(末波重读金当基线 +
    跨波刷新费重复扣)= 43,差 4 = 波1+波2 刷费重复扣——真函数若改回
    「以中段重读金为基线」类口径,本断言的锚值即不再闭合。
    """
    gold_open = 60
    spend_whole_run = 3 + 2 + 3 + 2 + 3   # 买+刷×2波 + 末波买(场景参数,非复刻 op 分支)
    assert expected_gold_after_actions(gold_open, spend_whole_run, 0) == 47, (
        '多波花金合计口径下对拍期望应与实读闭合(刷费单次计数)')
    # 卖入腿同式可见(对拍口径单一源:− 花出 + 卖入)
    assert expected_gold_after_actions(gold_open, spend_whole_run, 5) == 52



# ==================== w514_refresh_surface ====================

import json
from pathlib import Path

from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import refresh_effective
from sr_od.operations.sr_operation import SrOperation
from sr_od.application.currency_war.telemetry import defects, recorder
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 判据纯函数真值表 =====

def test_refresh_effective_truth_table():
    """集合不等=生效;全同=未生效嫌疑;任一侧含未识别槽('')或空读=None 不猜。"""
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['B', 'A', 'C', 'D', 'E']) is False  # 集合语义:同 5 牌换位=全同(DESIGN §2.5 口径;真刷出同 5 牌是组合级小概率,判据容忍)
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['A', 'B', 'C', 'D', 'E']) is False   # 全同=未生效
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['A', '', 'C', 'D', 'E']) is None     # 刷后读含未识别槽
    assert refresh_effective(['A', 'B', 'C', '', 'E'],
                             ['A', 'B', 'C', 'D', 'E']) is None    # 刷前(plan 帧)含未识别槽
    assert refresh_effective([], ['A', 'B']) is None               # 空读不可判
    assert refresh_effective(['A'], []) is None


# ===== ③ 两连全同防抖(台账复现计数)=====


# ===== ③ 两连全同防抖(台账复现计数)=====

def test_refresh_defect_debounce_l1_then_l0(tmp_path: Path, monkeypatch):
    """同特征(刷前牌名串)首见 L1、第二波再全同升 L0——「连续两次刷新全同
    才确认」的防抖由台账复现计数承载,判据函数只给单波判定。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    # 安灯 handler 是模块级单例(生产武装点=CurrencyWarApp.__init__),同进程
    # 先跑的测试构造过 App 即泄漏真 handler → 本测试升 L0 时会真停线写真
    # flag(2026-09-03 实证:真 flag 带 run_id=rt 落仓根)。本测试只验台账
    # 分级,钉 None 隔离停线通道(同 test_cw_infra_locks 缺省态钉法)。
    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_HANDLER', None)
    names = sorted(['A', 'B', 'C', 'D', 'E'])
    for _ in range(2):
        defects.record_defect(
            'shop_refresh', 'invariant_break',
            expected=f'刷后牌面≠刷前:{names}',
            observed=f'刷新后5牌与刷前全同:{names}',
            plane=1, round_num=3, gap_large=True,
            reader_source='refresh_set_compare')
    sevs = [r['severity'] for r in _rows(tmp_path, 'defect_ledger.jsonl')]
    assert sevs == ['L1_alert', 'L0_andon']


# ===== ④ 流纯净锁 =====

def test_record_defect_does_not_pollute_spend_ledger(tmp_path: Path, monkeypatch):
    """缺陷台账行只进 defect_ledger 一条流:spend_ledger 是原始证据层
    (消费端按单元框架字段解析),缺陷行混入会被当伪单元误读。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    defects.record_defect('shop_refresh', 'invariant_break', 'a', 'b')
    assert len(_rows(tmp_path, 'defect_ledger.jsonl')) == 1
    assert not (tmp_path / 'spend_ledger.jsonl').exists()




# ==================== w564_shop_wire ====================

from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.operations.cw_screen.cw_screen_prep as pd
from sr_od.application.currency_war.kernel.cw_state import GameState, ShopCard
from sr_od.application.currency_war.obs.cw_shop_obs import RefreshExpect
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
    build_refresh_expect,
    refresh_reconcile_mismatches,
)

# ===== _shop_pool_inputs(参评牌过滤,纯函数)=====


def _state_with_shop(cards: list[ShopCard]) -> GameState:
    st = GameState(plane=2, round_num=5, level=7)
    st.shop = cards
    return st


def test_pool_inputs_filters_unnamed() -> None:
    """未识别牌(name 空)不参评(空名+0费=invalid_cost 假票),只计数。"""
    st = _state_with_shop([
        ShopCard(x=100, name='甲', cost=1),
        ShopCard(x=200, name='', cost=0),
        ShopCard(x=300, name='乙', cost=2),
    ])
    cards, unnamed = pd._shop_pool_inputs(st)
    assert cards == [('甲', 1), ('乙', 2)]
    assert unnamed == 1


def test_pool_inputs_empty_shop() -> None:
    """shop 关态帧 read_shop_cards 返空 → 无参评牌(调用方天然跳过)。"""
    st = _state_with_shop([])
    assert pd._shop_pool_inputs(st) == ([], 0)
    assert pd._shop_pool_inputs(GameState()) == ([], 0)


# ===== build_refresh_expect(producer 契约,None 口径单一源)=====


class TestBuildRefreshExpect:
    def test_cost_none_skips(self) -> None:
        """刷费读不到(None)→ 跳过对账;禁 or-2 合并(不兜 2)。"""
        assert build_refresh_expect(10, None, [], 1, 1) is None

    def test_gold_none_skips(self) -> None:
        """开店金失读(None)→ 同跳(宁缺勿造)。"""
        assert build_refresh_expect(None, 2, [], 1, 1) is None

    def test_true_zero_preserved(self) -> None:
        """真 0(免费刷/减免档)原样保 0:gold_after==gold_before、不判不足。
        与 None 分道——0 是「读到的免费」,None 是「读不到」,绝不混写。"""
        r = build_refresh_expect(10, 0, [('甲', 1)], 1, 1)
        assert r is not None
        expect, plane, round_num = r
        assert expect.refresh_cost == 0
        assert expect.gold_after == 10
        assert expect.insufficient is False
        assert (plane, round_num) == (1, 1)

    def test_normal_and_insufficient(self) -> None:
        """正常扣费与金不足(算术差如实为负,判归调用方)。"""
        r = build_refresh_expect(10, 3, [], 2, 5)
        assert r is not None and r[0].gold_after == 7
        r = build_refresh_expect(1, 2, [], 2, 5)
        assert r is not None and r[0].gold_after == -1 and r[0].insufficient

    def test_cards_old_pooling(self) -> None:
        """旧五张回池账经 cw_shop_obs.refresh_expect 按名合并计数。"""
        r = build_refresh_expect(8, 2, [('甲', 1), ('甲', 1), ('乙', 2)], 1, 1)
        assert r is not None and r[0].pool_returned == {'甲': 2, '乙': 1}


# ===== refresh_reconcile_mismatches(消费判据,纯函数)=====


class TestRefreshReconcileMismatches:
    @staticmethod
    def _expect(gold_before: int = 10, cost: int = 2) -> RefreshExpect:
        return RefreshExpect(gold_before=gold_before, gold_after=gold_before - cost,
                             refresh_cost=cost, insufficient=gold_before < cost)

    def test_all_match(self) -> None:
        assert refresh_reconcile_mismatches(self._expect(), 8, 5) == []

    def test_gold_mismatch(self) -> None:
        m = refresh_reconcile_mismatches(self._expect(), 7, 5)
        assert m == [{'domain': 'gold', 'slot': '-', 'expected': '8', 'observed': '7'}]

    def test_gold_unreadable_not_judged(self) -> None:
        """金失读(None)→ 金腿不评(宁缺勿造,不猜)。"""
        assert refresh_reconcile_mismatches(self._expect(), None, 5) == []

    def test_no_cards_is_violation(self) -> None:
        """刷新后一格有身份牌都没有 → 刷新未生效形态,开票。"""
        m = refresh_reconcile_mismatches(self._expect(10, 0), 10, 0)
        assert m == [{'domain': 'cards', 'slot': '-',
                      'expected': '>=1', 'observed': '0'}]

    def test_partial_slots_not_judged(self) -> None:
        """1-4 张不判错(低等级后槽未解锁常态,槽位解锁规则未建模)。"""
        assert refresh_reconcile_mismatches(self._expect(), 8, 3) == []

    def test_combined_legs(self) -> None:
        m = refresh_reconcile_mismatches(self._expect(), 5, 0)
        assert {x['domain'] for x in m} == {'gold', 'cards'}


# ===== 行为锁(假 reader/假台账,零 OCR/零游戏)=====


def _make_director(monkeypatch: pytest.MonkeyPatch,
                   violations: list) -> CwScreenPrep:
    """构造无初始化的 Director;check_shop_pool 注入假实现。"""
    d = object.__new__(CwScreenPrep)
    session = SimpleNamespace()
    d.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    monkeypatch.setattr(pd, 'check_shop_pool', lambda cards, level, pool_state:
                        violations)
    return d


def _capture_defects(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    from sr_od.application.currency_war.telemetry import defects as tel
    calls: list[dict] = []
    monkeypatch.setattr(tel, 'record_defect',
                        lambda *a, **k: calls.append({'args': a, 'kwargs': k}))
    return calls


def _shop_obs(st: GameState | None, shop_open: bool = True) -> pd.PrepObservation:
    obs = pd.PrepObservation()
    obs.shop_open = shop_open
    obs.state = st
    return obs


def test_pool_wire_violation_records_defect(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """违例 → 落台账(surface=shop,kind=shop_pool_violation),带降级披露 refs。"""
    calls = _capture_defects(monkeypatch)
    viol = SimpleNamespace(name='甲', cost=5, kind='tier_locked', detail='p=0')
    d = _make_director(monkeypatch, [viol])
    st = _state_with_shop([ShopCard(x=100, name='甲', cost=5),
                           ShopCard(x=200, name='', cost=0)])
    d._reconcile_shop_pool(_shop_obs(st))
    assert len(calls) == 1
    assert calls[0]['args'] == ('shop', 'shop_pool_violation')
    kw = calls[0]['kwargs']
    assert kw['plane'] == 2 and kw['round_num'] == 5
    assert kw['reader_source'] == 'shop_pool_reconcile'
    assert kw['gap_large'] is True
    assert 'tier_locked' in kw['observed'] and 'p=0' in kw['observed']
    refs = {r['field']: r['value'] for r in kw['refs']}
    assert refs['level'] == '7' and refs['cards'] == '1' and refs['unnamed'] == '1'
    assert 'None' in refs['pool_state']   # 池守恒查降级如实披露


def test_pool_wire_clean_or_closed_or_empty_skips(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """零违例 / 关店帧 / 空牌帧 → 零台账(一致不打扰,宁缺勿造)。"""
    calls = _capture_defects(monkeypatch)
    d = _make_director(monkeypatch, [])
    st = _state_with_shop([ShopCard(x=100, name='甲', cost=1)])
    d._reconcile_shop_pool(_shop_obs(st))            # 零违例
    d._reconcile_shop_pool(_shop_obs(st, shop_open=False))   # 关店帧
    d._reconcile_shop_pool(_shop_obs(_state_with_shop([])))  # 空牌
    d._reconcile_shop_pool(_shop_obs(None))          # 无 state
    assert calls == []


def test_pool_wire_best_effort_on_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """违例票异常 → 静默跳过,不阻塞环(best-effort 契约)。"""
    _capture_defects(monkeypatch)
    d = _make_director(monkeypatch, [])
    monkeypatch.setattr(pd, 'check_shop_pool',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('down')))
    st = _state_with_shop([ShopCard(x=100, name='甲', cost=1)])
    d._reconcile_shop_pool(_shop_obs(st))   # 不抛即过



# ==================== w591_refresh_wave_op ====================

import pathlib
from typing import Any

from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_obs_core import SHOP_SCREEN_NAME
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    CloseShop,
    RefreshShop,
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


class _BuyPhaseHostOp(SrOperation):
    """买牌单元离线宿主(prep/shop.py BuyShopCards 壳退役后的测试装配面)。

    编排 = 现役链同款:开店 → 波循环 → 关店 → finalize_buy_phase 单一源收尾;
    生产编排唯一宿主 = CwScreenPrep._open_shop_phase,本类只作波循环/收尾
    语义的离线驱动器,不承载生产逻辑。
    """

    def __init__(self, ctx):
        SrOperation.__init__(self, ctx, op_name='货币战争-买牌波测试宿主')

    @operation_node(name='商店买牌', is_start_node=True)
    def buy(self):
        from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
            run_buy_waves,
        )
        from sr_od.application.currency_war.operations.cw_op.cw_op_close_shop import (
            close_shop,
        )
        from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep as finalize_home
        from sr_od.application.currency_war.operations.cw_op.cw_op_open_shop import (
            open_shop,
        )
        screen = self.last_screenshot
        if not self.round_by_find_area(screen, '货币战争-备战',
                                       '备战标识-购买经验').is_success:
            return self.round_fail('非备战屏(回合事件叠层?),交主循环处理')
        _r_open = open_shop(self)
        if not _r_open.is_success:
            return _r_open
        match = self.ctx.cw_match
        _rr, outcome = run_buy_waves(self, match, None, False, False)
        if _rr is not None or outcome is None:
            return _rr if _rr is not None else self.round_fail('买牌波循环无产出')
        _r_close = close_shop(self)
        if not _r_close.is_success:
            return _r_close
        return self.round_success(finalize_home.finalize_buy_phase(
            self, match, outcome, None, False, False))

class _StubStrategy:
    """替身决策源(ADR-0517 单动作形态):按调用次序逐帧吐单动作。

    ``plans`` 沿用旧「段 × 动作序列」入参形态,构造时拍平为动作流;
    耗尽后恒吐 ``CloseShop``(单动作决策核「无动作可做」的终结语义,
    决策 4/6)。生产执行侧消费口 = ``decide_shop_action``(旧
    decide_shop_screen 序列口退役为 sim/回放兼容驱动器)。
    """

    def __init__(self, plans: list[list[Any]]):
        self._acts = [a for plan in plans for a in plan]
        self.calls = 0

    def update_target(self, state, session, config) -> None:
        pass

    def decide_shop_action(self, session, config) -> Any:
        i = self.calls
        self.calls += 1
        return self._acts[i] if i < len(self._acts) else CloseShop()


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
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep as pd
    from sr_od.application.currency_war.obs import cw_observation as cwo
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards as buy_cards_mod,
    )


    class _Watched(WatchdogOperationMixin, _BuyPhaseHostOp):
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

    # 顺序替身读数(逐次消耗,耗尽后恒最后一个)。W970 批 A 原子化后读点
    # 随波循环迁 buy_cards 模块(编排壳只留关店后对拍读:read_gold/read_game_state;
    # read_gold_opt 仅波循环消费)。
    _state_seq = _make_seq(states)
    _gold_opt_seq = _make_seq(gold_opts)
    _shop_seq = _make_seq(shop_reads)
    for _mod in (cwo, buy_cards_mod):
        monkeypatch.setattr(_mod, 'read_game_state', _state_seq)
        # gold 差值对拍(关店后 stylized 读):正常链读 8 与期望一致,零冲突
        monkeypatch.setattr(_mod, 'read_gold',
                            lambda *a, **k: gold_opts[min(1, len(gold_opts) - 1)])
    monkeypatch.setattr(buy_cards_mod, 'read_gold_opt', _gold_opt_seq)
    monkeypatch.setattr(buy_cards_mod, 'read_shop_cards',
                        lambda *a, **k: _shop_cards(_shop_seq()))
    # W592:执行事实暂存槽捕获(分类器观测面 refresh_board_changed 的
    # 执行侧真值直接在此断言,不经台账二次解析)
    facts: list[dict] = []
    monkeypatch.setattr(cw_telemetry, 'set_unit_exec_facts',
                        lambda **k: facts.append(k))
    monkeypatch.setattr(cwo, 'read_hp_opt', lambda *a, **k: None)
    monkeypatch.setattr(cwo, 'read_phase_round', lambda *a, **k: (1, 5))

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

    # 画面判定替身:备战锚成功(防空 overlay 误判)+ 商店开态锚「按钮-收起」成功
    # (DD-011 开店判稳轮询的离线放行 = 判「店已开」跳过开店段;其余失败)
    op = _Watched(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    # 画面判定替身(状态化):备战锚恒成功(防空 overlay 误判);「按钮-收起」
    # 按 shop 开合状态翻转(W970 批 A 后 CwOpOpenShop/CwOpCloseShop 以「收起
    # 出现/消失」做 fail-closed 验证,离线桩须模拟真转移,否则收起验证死循环)。
    shop_open = {'v': True}

    def _find_area(screen, screen_name, area_name, **k):
        if (screen_name, area_name) == _ANCHOR:
            return op.round_success('')
        if area_name == '按钮-收起':
            return op.round_success('') if shop_open['v'] else op.round_fail('')
        return op.round_fail('')

    def _find_and_click(screen, screen_name, area_name, **k):
        if area_name == '按钮-收起':
            shop_open['v'] = False
        elif area_name == '按钮-商店':
            shop_open['v'] = True
        return op.round_success('')

    monkeypatch.setattr(op, 'round_by_find_area', _find_area)
    monkeypatch.setattr(op, 'round_by_find_and_click_area', _find_and_click)
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


# ===== W593:决策循环帧帽(对抗修复批 F1 执行侧兜底)=====


def test_segment_action_cap_raises_loud(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path, _require_fixture,
) -> None:
    """帧帽锁:决策循环恒收非终结动作(不收敛形态)⇒ 第
    SHOP_SEGMENT_ACTION_CAP+1 帧触发 RuntimeError(响亮暴露,禁静默
    续跑)+ decisions 行落 ``plan_visit_action_cap`` 分键计数。

    场景替身 = 恒吐 LevelUpShop(非终结、守卫无辖面、simulate 无金
    校验)——复现「决策器每帧重复提案同类动作」的无限循环形态;席位
    门的收敛根因修复在决策侧(test_cw4_shop_line TestEvBuySeatGate),
    本帽 = 执行侧最后防线。动作 sleep 经模块级替身吃掉(测试纪律:
    不为生产加参数)。
    """
    from types import SimpleNamespace as _NS

    import sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops as saop
    from sr_od.application.currency_war.kernel.cw_state import LevelUpShop
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        SHOP_SEGMENT_ACTION_CAP,
    )
    monkeypatch.setattr(saop, 'time', _NS(sleep=lambda *_a: None))
    events: list[str] = []
    op, fc, rows, _facts = _make_op(
        test_context, monkeypatch, tmp_path,
        plans=[[LevelUpShop(cost=4)] * (SHOP_SEGMENT_ACTION_CAP + 4)],
        states=[_state(60, _OLD_NAMES), _state(60, _OLD_NAMES),
                _state(60, _OLD_NAMES), _state(60, _OLD_NAMES)],
        gold_opts=[60, 60], shop_reads=[_NEW_NAMES, _NEW_NAMES], events=events)

    # 直调循环主体(不经 op.execute 的 retry 链——框架会把异常转失败轮
    # 并重试,掩盖「响亮暴露」形态;本锁钉循环本体行为)
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        run_buy_waves,
    )
    with pytest.raises(RuntimeError, match='超帽'):
        run_buy_waves(op, test_context.cw_match, None, False, False)
    # decisions 行分键计数(占位行;读取隔离台账 tmp_path)
    dec = _rows(tmp_path, 'decisions.jsonl')
    assert any(r.get('plan_visit_action_cap') == 1.0
               or (isinstance(r.get('eval_breakdown'), dict)
                   and r['eval_breakdown'].get('plan_visit_action_cap'))
               for r in dec), f'超帽须落遥测分键:decisions={dec}'


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
    # (锁③断言此处弱化为 `is not True`——'' 槽使判据 None 是既有申报形态;
    #  「未误判已变」的行为面由下方 classify_spend_unit 端到端断言覆盖。)
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



# ==================== w891_buy_edge ====================


from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    LevelUp,
    SellBench,
    bench_occupied,
)
from one_dragon.base.operation.operation_node import operation_node
from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
    build_post_buy_incremental_state,
    refresh_wave_is_refresh_only,
)


def _st(**kw) -> GameState:
    base = {'plane': 2, 'round_num': 3, 'node_type': '战斗', 'gold': 60,
            'hp': 80, 'hp_readable': True, 'level': 7, 'streak': None,
            'board': {'列车同行': 1}, 'bench': [], 'shop': []}
    base.update(kw)
    return GameState(**base)


def _tracked() -> list[BenchChar]:
    return [BenchChar(slot=1, char_id='姬子·启行', star=1, faction='列车'),
            BenchChar(slot=2, char_id='囤件', star=1, faction='公司')]


# ===== 锁 1:仅刷新波判定(连击共享往返的边界)=====

def test_refresh_only_wave_predicate() -> None:
    """首动作即 RefreshShop = 仅刷新波(可复用波循环顶读当刷前现读);
    前缀含买/升/卖的波一票否决(w592 勘误失效条件只在含买波成立);
    空 plan 非(无刷新可谈)。"""
    assert refresh_wave_is_refresh_only([RefreshShop()]) is True
    assert refresh_wave_is_refresh_only(
        [BuyCard(ShopCard(x=0, name='姬子·启行', cost=3)), RefreshShop()]) is False
    assert refresh_wave_is_refresh_only([LevelUp(cost=40)]) is False
    assert refresh_wave_is_refresh_only(
        [SellBench(bench_idx=0, income=1), RefreshShop()]) is False
    assert refresh_wave_is_refresh_only([]) is False


# ===== 锁 2:买后重估增量态构造 =====

def test_post_buy_incremental_state_gold_truth_and_bench_replay() -> None:
    """gold=关店帧真读覆盖(末波垫底值是执行前快照,必须换真值);
    bench 重播 tracked(执行侧 mutate 逐动作同步的权威源,垫底值过期)。"""
    last = _st(gold=55, bench=[])   # 末波垫底:买前金/买前 bench
    post = build_post_buy_incremental_state(
        last, 41, _tracked(), '战斗', 80, True, True)
    assert post is not None
    assert post.gold == 41
    assert bench_occupied(post.bench) == 2
    assert post.hp == 80 and post.hp_readable and post.hp_trusted
    assert post.node_type == '战斗'


def test_post_buy_incremental_state_invariants_preserved() -> None:
    """机制不变量沿用末波读值:本单元动作(无升级)不触 plane/round/
    board/level/xp——增量构造不得回退这些面为缺省/零值。"""
    last = _st(plane=2, round_num=3, level=7, board={'列车同行': 1})
    post = build_post_buy_incremental_state(
        last, 41, _tracked(), None, 80, True, True)
    assert post is not None
    assert (post.plane, post.round_num, post.level) == (2, 3, 7)
    assert post.board == {'列车同行': 1}
    assert post.shop == []   # 沿用垫底(刷后牌面不进重估消费面,保真边界见报告 §1.5)
    assert post.hp_readable is True and post.hp_trusted is True


def test_post_buy_incremental_state_hp_unreadable_not_overwritten() -> None:
    """hp 不产值链(hp_value=None)→ _apply_hp 不覆盖:保留垫底帧的
    值+位(对账层产物),增量构造不引入假 hp/假可信位。"""
    last = _st(hp=80, hp_readable=True)
    post = build_post_buy_incremental_state(last, 41, _tracked(), None,
                                            None, False, False)
    assert post is not None
    assert post.hp == 80
    # 不覆盖语义:值+位与垫底帧逐位相同(不引入假 hp/假可信位)
    assert post.hp_readable == last.hp_readable
    assert post.hp_trusted == last.hp_trusted


def test_post_buy_incremental_state_gold_miss_fails_closed() -> None:
    """金失读 → None(调用方回退全量 read_game_state):宁全量不造值。"""
    assert build_post_buy_incremental_state(
        _st(), None, _tracked(), None, 80, True, True) is None


def test_post_buy_incremental_state_empty_tracked_fails_closed() -> None:
    """空 tracked → None(fail-closed 第二维):bench 真空与跟踪丢失在
    构造点不可区分,垫底 state.bench 是执行前快照——沿它会拿陈旧 bench
    当真值(误读维度造值);调用方回退全量 OCR 后两情形都得真值。"""
    stale_bench = _tracked()
    last = _st(gold=55, bench=stale_bench)
    assert build_post_buy_incremental_state(
        last, 41, [], None, 80, True, True) is None


def test_post_buy_incremental_state_no_mutation_of_last_state() -> None:
    """垫底 state 不得被就地改写(round_success 仍消费其 gold/plane)。"""
    last = _st(gold=55, bench=[])
    build_post_buy_incremental_state(last, 41, _tracked(), None, 80, True, True)
    assert last.gold == 55 and bench_occupied(last.bench) == 0


# (锁 3「gate 零触碰回归锚」已随 2026-09-03 gate 清尾批删除——gate 模块退役,
#  常量/签名不复存在;shop 稳定门 = cw_op_buy_cards._wait_shop_row_stable,锁在
#  下方 test_stable_gate_* 组。)



# ==================== w944_shop_unk_settle ====================


import numpy as np
import pytest

_w944_shop_unk_settle_PREP = '货币战争-备战'
_w944_shop_unk_settle_ANCHOR = (_w944_shop_unk_settle_PREP, '备战标识-购买经验')

_NAMED = ['希儿', '景元', '布洛妮娅', '克拉拉', '杰帕德']


def _frame(changed: bool = False) -> Any:
    """合成 1080p 帧:基色 30;changed=True 时牌行区打亮块(指纹必异)。"""
    img: Any = np.full((1080, 1920, 3), 30, dtype=np.uint8)
    if changed:
        img[240:320, 320:1500] = 200
    return img


# ---------------------------------------------------------------------------
# 1. 稳定门单元锁(真实指纹基元 + 合成帧,无 fixture 文件依赖)
# ---------------------------------------------------------------------------

class _FakeOp:
    """最小 op 替身:仅暴露 _wait_shop_row_stable 用到的 screenshot()。"""

    def __init__(self, frames: list[Any]):
        self._frames = frames
        self._i = 0

    def screenshot(self) -> Any:
        f = self._frames[min(self._i, len(self._frames) - 1)]
        self._i += 1
        return f


def test_stable_gate_waits_animation_then_settles() -> None:
    """锁①a 动画帧序列:A→B(变)→B→B(连续同)→ 门判稳定放行。"""
    from one_dragon.base.operation.operation_node import operation_node
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        _wait_shop_row_stable,
    )

    op = _FakeOp([_frame(False), _frame(True), _frame(True), _frame(True),
                  _frame(True), _frame(True), _frame(True), _frame(True)])
    assert _wait_shop_row_stable(op) is True


def test_stable_gate_fast_path_minimum_observation() -> None:
    """锁①d(W952 P2-1)冻结帧 fast-path 最短观察 ≥1.0s。

    慢机冻结帧两次采样相同可短至 0.5s 即放行 → 非终帧误判稳定;
    修复后指纹相同仍须观察满 min_observe_s(对齐被替换 M35 单次 1.0s)
    才放行。实测放行耗时 ≥0.95s(0.25s 采样栅上的 1.0s 判据)。
    """
    import time as _t

    from one_dragon.base.operation.operation_node import operation_node
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        _wait_shop_row_stable,
    )

    op = _FakeOp([_frame(True)])   # 恒冻结帧:修复前 0.5s 即放行
    t0 = _t.monotonic()
    ok = _wait_shop_row_stable(op)
    elapsed = _t.monotonic() - t0
    assert ok is True
    assert elapsed >= 0.95, (
        f'冻结帧 fast-path 放行过快({elapsed:.2f}s < 0.95s):'
        'P2-1 回归(最短观察窗被摘)')


def test_stable_gate_timeout_has_compensation_wait() -> None:
    """锁①e(W952 P2-2)永变超时回退含补偿静置,不立读。

    调用方契约=「等稳后读」;超时(画面永变)若立即返回即「未稳即读」。
    修复后超时返回前静置 _SETTLE_TIMEOUT_COMPENSATE_S,实测 False 返回
    总耗时 ≥ max_wait_s + 补偿。
    """
    import time as _t

    from one_dragon.base.operation.operation_node import operation_node
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        _SETTLE_TIMEOUT_COMPENSATE_S,
        _wait_shop_row_stable,
    )

    op = _FakeOp([_frame(i % 2 == 0) for i in range(32)])
    t0 = _t.monotonic()
    ok = _wait_shop_row_stable(op, max_wait_s=0.4)
    elapsed = _t.monotonic() - t0
    assert ok is False
    assert elapsed >= 0.4 + _SETTLE_TIMEOUT_COMPENSATE_S - 0.05, (
        f'超时回退无补偿静置({elapsed:.2f}s):P2-2 回归(立读形态回流)')


def test_stable_gate_screenshot_exception_offline_contract() -> None:
    """锁①c 离线契约:截图恒炸 → suppress 降级继续等,超时 False(不炸调用方)。"""
    from one_dragon.base.operation.operation_node import operation_node
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        _wait_shop_row_stable,
    )

    class _BoomOp:
        def screenshot(self) -> Any:
            raise RuntimeError('offline')

    assert _wait_shop_row_stable(_BoomOp(), max_wait_s=0.3) is False


# ---------------------------------------------------------------------------
# 2. op 级行为锁(w591 替身手法:替身观测输入 + 替身计划源 + 台账隔离)
# ---------------------------------------------------------------------------

class _w944_shop_unk_settle_StubStrategy:
    """替身决策源(ADR-0517 单动作形态):恒吐 CloseShop(零买 → 直接
    进钩子判定;旧 decide_shop_screen 空 plan 序列口已退役)。"""

    def __init__(self) -> None:
        self.calls = 0

    def update_target(self, state, session, config) -> None:
        pass

    def decide_shop_action(self, session, config) -> Any:
        self.calls += 1
        return CloseShop()


def _make_hook_op(test_context: SrTestContext,
                  monkeypatch: pytest.MonkeyPatch,
                  tmp_path: pathlib.Path,
                  wave_shop: list[str],
                  hook_rereads: list[list[str]],
                  writes: list[str]) -> tuple[Any, FixtureController, int]:
    """装配钩子路径被测 op。返回 (op, fixture_controller, 钩子重读次数容器)。

    ``wave_shop`` 是波循环顶 read_game_state 的商店名表(含 ''=未识别槽);
    ``hook_rereads`` 是停机钩子 read_shop_cards 的逐次返回(名表)。
    """
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
        StrategySession,
    )
    from sr_od.application.currency_war.kernel.cw_state import GameState, ShopCard
    from sr_od.application.currency_war.obs import cw_observation as cwo
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards as buy_cards_mod,
    )
    from sr_od.application.currency_war.telemetry import defects, recorder
    from sr_od.application.currency_war.telemetry import state as cw_telemetry

    class _Watched(WatchdogOperationMixin, _BuyPhaseHostOp):
        pass

    # 台账隔离(不写真实 .debug;test_cw_w536 手法)
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True,
                                                   replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'w944t')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    monkeypatch.setattr(defects, 'record_defect', lambda *a, **k: None)

    def _spy_write(self: pathlib.Path, data: Any, *args: Any, **kwargs: Any):
        writes.append(str(data))
        return len(data)

    monkeypatch.setattr(pathlib.Path, 'write_text', _spy_write)

    def _state() -> GameState:
        shop = [ShopCard(x=i, faction='?', name=n, cost=3, star=1)
                for i, n in enumerate(wave_shop)]
        return GameState(gold=10, plane=1, round_num=7, level=5, shop=shop)

    reads = {'n': 0}

    def _read_shop(*args: Any, **kwargs: Any):
        i = reads['n']
        reads['n'] += 1
        names = hook_rereads[min(i, len(hook_rereads) - 1)]
        return [ShopCard(x=j, faction='?', name=n, cost=3, star=1)
                for j, n in enumerate(names)]

    # 读点随波循环迁 buy_cards 模块(W970 批 A);finalize(单一源在 cw_screen_prep)经 cw_observation 函数级导入
    for _mod in (cwo, buy_cards_mod):
        monkeypatch.setattr(_mod, 'read_game_state', lambda *a, **k: _state())
        monkeypatch.setattr(_mod, 'read_gold', lambda *a, **k: 10)
    monkeypatch.setattr(buy_cards_mod, 'read_gold_opt', lambda *a, **k: 10)
    monkeypatch.setattr(buy_cards_mod, 'read_shop_cards', _read_shop)
    monkeypatch.setattr(cwo, 'read_hp_opt', lambda *a, **k: None)
    monkeypatch.setattr(cwo, 'read_phase_round', lambda *a, **k: (1, 7))

    monkeypatch.setattr(test_context, 'cw_match',
                        CurrencyWarMatch(_w944_shop_unk_settle_StubStrategy(), StrategySession()))

    fc = FixtureController(test_context)
    fc.set_phases([{'frame': (_w944_shop_unk_settle_PREP, 'shop_closed')}])
    monkeypatch.setattr(test_context, 'controller', fc)

    op = _Watched(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    # 画面判定替身(状态化):收起锚按 shop 开合翻转(同 _make_op,W970 批 A
    # Open/CwOpCloseShop 的 fail-closed 验证需离线模拟真转移)。
    shop_open = {'v': True}

    def _find_area(screen, screen_name, area_name, **k):
        if (screen_name, area_name) == _w944_shop_unk_settle_ANCHOR:
            return op.round_success('')
        if area_name == '按钮-收起':
            return op.round_success('') if shop_open['v'] else op.round_fail('')
        return op.round_fail('')

    def _find_and_click(screen, screen_name, area_name, **k):
        if area_name == '按钮-收起':
            shop_open['v'] = False
        elif area_name == '按钮-商店':
            shop_open['v'] = True
        return op.round_success('')

    monkeypatch.setattr(op, 'round_by_find_area', _find_area)
    monkeypatch.setattr(op, 'round_by_find_and_click_area', _find_and_click)
    monkeypatch.setattr(op, 'round_by_ocr', lambda *a, **k: op.round_fail(''))
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: '<shot>')
    return op, fc, reads


def _w944_shop_unk_settle_execute(op) -> Any:
    enter_running_state(op.ctx)
    try:
        with fast_sleep():
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


@pytest.fixture()
def _w944_shop_unk_settle_require_fixture(test_context: SrTestContext) -> None:
    if not test_context.has_screen(_w944_shop_unk_settle_PREP, 'shop_closed'):
        pytest.skip(f'存档截图缺失:screens/{_w944_shop_unk_settle_PREP}/shop_closed.webp')


def test_hook_heals_after_settled_reread(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _w944_shop_unk_settle_require_fixture,
) -> None:
    """锁②a 瞬态帧形态:波顶读含未识别槽 → 稳定门后重读全识别 → 不停机。

    修复前该形态靠 blind sleep 猜时长;修复后门等牌行区两帧一致再读
    (替身单帧恒同 → 门秒过),第 1 次重读全识别 → 正常收工,零 flag 零停。
    """
    writes: list[str] = []
    op, _fc, reads = _make_hook_op(
        test_context, monkeypatch, tmp_path,
        wave_shop=['', '景元', '', '克拉拉', '杰帕德'],
        hook_rereads=[_NAMED],
        writes=writes)

    result = _w944_shop_unk_settle_execute(op)

    assert result.success, f'自愈后应正常收工:status={result.status!r}'
    assert reads['n'] == 1, f'第 1 次重读即自愈,实际重读 {reads["n"]} 次'
    assert not any('HOOK-STOP' in w for w in writes), (
        f'自愈形态不得写停机 flag:{writes[:3]}')


def test_hook_persistent_unknown_stops_with_evidence(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _w944_shop_unk_settle_require_fixture,
) -> None:
    """锁②b 模态弹窗压暗形态:预算 2 次重读仍 unknown → 真停 + flag 留证。

    弹窗遮挡不是瞬态帧,重读不会自愈——判据化门秒过(画面稳定)后预算
    耗尽照旧停机留证(用户 2026-08-24 裁决:未识别不能降级带病跑)。
    """
    writes: list[str] = []
    unk = ['', '景元', '', '克拉拉', '杰帕德']
    op, _fc, reads = _make_hook_op(
        test_context, monkeypatch, tmp_path,
        wave_shop=unk,
        hook_rereads=[unk, unk],
        writes=writes)

    result = _w944_shop_unk_settle_execute(op)

    assert not result.success, f'持续 unknown 应真停:{result.status!r}'
    assert '未识别卡槽' in (result.status or ''), result.status
    assert reads['n'] == 2, f'预算应恰 2 次重读,实际 {reads["n"]} 次'
    assert any('HOOK-STOP' in w and 'shop' in w for w in writes), (
        f'真停必须留证 flag:{writes[:3]}')


# ---------------------------------------------------------------------------
# 2c. match2 复盘候选形态锁(replay/matches/reviews/g_20260831_053546):
#     读空帧 → 标记跳过该槽(不点空槽)→ 不误停;持续读空才停机(锁②b)
# ---------------------------------------------------------------------------

def test_hook_unknown_slot_skipped_not_stopped(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _w944_shop_unk_settle_require_fixture,
) -> None:
    """锁②c 同波含未识别槽:执行只买有身份牌(不点读空槽),重读自愈不停机。

    复盘候选形态「unknown 标记跳过该槽 + 持续读空才停机」的执行半部:
    plan 不发读空槽的 BuyCard → 执行侧零空槽点击;稳定门重读自愈 →
    op 正常收工。「持续读空才停机」半部由锁②b 承载(预算耗尽真停)。
    """
    from sr_od.application.currency_war.kernel.cw_obs_core import (
        shop_card_click_points,
    )
    from sr_od.application.currency_war.kernel.cw_state import (
        BuyCard,
        ShopCard,
    )

    writes: list[str] = []
    op, fc, reads = _make_hook_op(
        test_context, monkeypatch, tmp_path,
        wave_shop=['', '景元', '布洛妮娅', '克拉拉', '杰帕德'],
        hook_rereads=[_NAMED],
        writes=writes)
    # 给替身策略注入「只买有身份牌(x≈1300 → 槽5)」的单动作流
    # (ADR-0517 单动作形态:逐帧吐单动作,后续帧 CloseShop 收尾)
    _injected = {'n': 0}

    def _decide(session, config):
        _injected['n'] += 1
        return (BuyCard(card=ShopCard(x=1300, faction='?', name='杰帕德',
                                      cost=3, star=1))
                if _injected['n'] == 1 else CloseShop())
    test_context.cw_match.strategy.decide_shop_action = _decide

    result = _w944_shop_unk_settle_execute(op)

    assert result.success, f'跳过读空槽后应正常收工:{result.status!r}'
    assert reads['n'] == 1, f'重读自愈,实际重读 {reads["n"]} 次'
    assert not any('HOOK-STOP' in w for w in writes), (
        f'自愈形态不得写停机 flag:{writes[:3]}')
    expected = min(shop_card_click_points(test_context),
                   key=lambda p: abs(p.x - 1300))
    buys = [c for c in fc.recorded_clicks
            if abs(c.x - expected.x) <= 5 and c.y == expected.y]
    assert len(buys) == 1, (
        f'应恰好 1 次有身份牌点击@~({expected.x},{expected.y}),'
        f'recorded={[str(p) for p in fc.recorded_clicks]}')
    assert all(abs(c.x - expected.x) <= 5 for c in fc.recorded_clicks), (
        f'不得点击读空槽(槽1 rect x≈250 区):{[str(p) for p in fc.recorded_clicks]}')


# ---------------------------------------------------------------------------
# 3. 守卫移除红检(源码锁,手法同 test_cw_w515):摘掉稳定门 → 红
# ---------------------------------------------------------------------------

def test_guard_hook_uses_settle_gate_not_blind_sleep() -> None:
    """接线烟雾:钩子防抖调用判据化稳定门 _wait_shop_row_stable;blind sleep 回流 = 红。

    W944 失守事故背书:读卡失败的防抖重读曾退化为猜时长的固定 sleep,
    误读率回升。本函数原 4 条 `in src` 肯定断言(函数定义在场 /
    min_observe_s / time.sleep 字面)已由本文件 L913-958 两条计时行为锁
    更强覆盖(行为锁直接驱动真实帧序列,不依赖源码字面),故只保留
    「钩子确实调用了稳定门」这一条接线烟雾——行为锁测不了"接线在",
    只能测"接上后行为对"。摘掉 _wait_shop_row_stable 调用(或回退
    sleep 等待)时,本锁红,防感知自愈被静默移除。
    """
    src = pathlib.Path(
        'src/sr_od/application/currency_war/operations/cw_op/cw_op_buy_cards.py'
    ).read_text(encoding='utf-8')
    # 钩子调用稳定门(调用形态:门 → 重读,紧邻;W970 批 A 波循环迁
    # buy_cards,宿主参数形 self→op,调用形态同步迁移)
    assert '_wait_shop_row_stable(op)' in src, '钩子未调用稳定门'
    # 钩子段不得回流 blind sleep(门到位前旧码形态:先 sleep 再重读)
    assert 'time.sleep(1.0)\n                _reshop' not in src, (
        '钩子防抖回流 blind sleep(摘门回归形态)')
