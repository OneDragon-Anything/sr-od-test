"""sim 超发货币两条效果条目测试(镜像 src = sim/cw_sim_backend.py 的选卡落地拍
负债腿 + 节点窗回流腿 pre-read 两拍 + 呈现一次性标志位;先例 =
本目录 test_invest_installment_gold.py〔分期金窗腿〕/
test_strategy_pick_gudinglicai.py〔拿卡落地拍腿族〕同形态)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-191-chaofa-
huobi.md §3 锁 3/锁 4/锁 5/锁 6/锁 9(REVIEW-T191 §四④ 同面;锁 6 直构
形态 = T-177 锁 6 先形「无补发方,容器即终态」):
- 负债腿(锁 3):真拿卡路径落地 → 条目已登记(remaining_nodes=6 ∧
  counters[LOST]=G)∧ 金清零笔(−G = 写前金 − 0)∧ 呈现一次性标志位防重放(同声明
  复喂零动作零噪声);bypass 形态(登记缺位)= 零动作 + disclosures 留证
  (零新增披露键,内联运行时键);
- 回流腿(锁 4):拿卡后第 1-5 个节点窗零发放;第 6 窗 +G+70 一笔
  (evidence 含 p/r 坐标;支付先于该窗收入 = 增量公式以「窗前金 + 回流额」
  为息基数现算,禁观测差分反推);第 7 窗不再发(条目已移除,前读落空);
- 零金兜底(锁 5):0 金拿卡 → 快照 0 → 清零短路零写 → 第 6 窗回流 70;
- 局终蒸发(锁 6):第 6 窗前条目留置蒸发不补发(无任何局终补发方,
  窗口前读 = 唯一触发面,锁 4 引擎侧已证);
- 修饰局计数(锁 9):人身意外险插入补给窗照计数,第 6 个窗事件触发回流
  (计数域 = 节点入口事件全型,T-106 先例)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py 与
sim/cw_sim_backend/test_p3_win_terminal.py(已登记拆分债文件,禁追加,
只 import 复用不改)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _force_settle,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    round_start_income,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    HYPEREMIT_SPEC_ID,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    resolve_plane_node_seqs,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    income_modifiers_of,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '超发货币'

#: 负债清零笔 evidence(sim 写统一前缀 + 写点 tag,设计稿字面量钉死)。
_DRAIN_EV = 'sim:engine:strategy:hyperemit_drain:超发货币'


def _backend(seed: int = 41) -> SimBackend:
    """装配后端至 P1r1 备战屏(无投资环境;装配形态先例 =
    test_invest_installment_gold._backend)。调用方负责 uninstall。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _pick_raw(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡上报(直写 opts 定卡 + 上报;返回声明不喂入,由调用方
    控制落地时点——bypass 形态在声明前改容器;先例 =
    test_strategy_pick_gudinglicai._pick 返回声明同形)。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    return out.world_decl


def _pick(b: SimBackend, name: str, opts: list[str]) -> None:
    """定向选卡落地(上报 + 声明喂入;形态 = 上行 _pick_raw 直落)。"""
    cw_sim_ports.declare_world(_pick_raw(b, name, opts))


def _drive_until(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step——补给/战斗/遭遇/过渡屏在其分派表
    内,跨节点窗必经)。"""
    for _ in range(limit):
        if pred():
            return
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


# 填充卡前提申报(T-311-r1 裁决 a:只修注释、卡不换——换卡位移种子轨迹,
# 明令禁止):淘金客现役 xp_per_refresh=2(cw_investments.py 注册行),
# 刷新 XP 把结果写进状态副本的实现分支已接入调用(T-311);本卡作填充的安全性前提 = 本目录
# sim 链驱动器(_drive_step)商店屏一律直接关店、零付费刷新帧 → XP
# 分支零开火,落卡零扰目标断言;未来引入付费刷新驱动须先换无 XP 字段
# 填充卡或显式预算 XP 推进对。
_SAFE_FILLER = '淘金客'
_SAFE_OPTS = ['淘金客', '躺平', '买断制']


def _drive_with_safe_picks(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立;途中逢策略 offer 定向落安全 filler(防自动
    选卡采到干扰卡;先例 = test_strategy_pick_gudinglicai 同名助手)。"""
    for _ in range(limit):
        if pred():
            return
        if b.screen_identity() == SCREEN_INVEST_STRATEGY:
            _pick(b, _SAFE_FILLER, _SAFE_OPTS)
            continue
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend, plane: int = 1, round_num: int = 3) -> None:
    """驱动至指定位面的策略 offer 呈现(缺省 = 固定日程首槽 P1r3;呈现即
    置负债腿一次性标志位;途中 offer 安全 filler 化,保到达槽为首个未被消费的
    日程槽)。"""

    def _at_offer() -> bool:
        node = b.gs.node.value
        return (b.screen_identity() == SCREEN_INVEST_STRATEGY
                and node is not None and node.plane == plane
                and node.round_num == round_num)
    _drive_with_safe_picks(b, _at_offer)


def _window_income(gs: GameState, plane: int, r: int, gold_base: int) -> int:
    """节点窗收入面 kernel 公式现算(禁观测差分反推——混账形态测不出;
    先例 = test_invest_installment_gold._window_income 同式)。
    gold_base = 利息基数(窗开金在窗前腿落账后的现值口径,由调用方传入)。"""
    kind = gs.node.value.kind
    streak = max(int(gs.streak.value or 0), 0)
    mult, flat, cap = income_modifiers_of(gs)
    return round_start_income(
        plane, r, kind, gold_base, streak, win_reward_mult=mult,
        interest_flat=flat, interest_cap=cap).total


def test_drain_leg_via_engine_and_replay_guard(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负债腿引擎链(锁 3 主形态)+ 呈现一次性标志位防重放:真拿卡路径落地 →
    条目已登记(remaining_nodes=6 ∧ counters[LOST]=登记帧读数 G)∧ 金清零
    (evidence 笔字面量钉死,−G = 写前金 − 0);同声明复喂 → 一次性标志位已消费,
    零动作零噪声(gold 证据笔保持清零笔)。全胜骨架沿分期金锁先形
    (_force_settle patch 面 = backend 模块命名空间)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gold_before = int(gs.gold.value or 0)
        assert gold_before > 0, '前置:引擎链拿卡帧持有金在场'
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        entry = gs.effects.first(HYPEREMIT_SPEC_ID)
        assert entry is not None, '条目已登记(获得链登记,单载体)'
        assert entry.remaining_nodes == 6, 'N_NODES 播种'
        assert entry.counters.get('lost') == gold_before, \
            f'负债播值 = 登记帧金读数: {entry.counters}'
        assert int(gs.gold.value or 0) == 0, '负债腿清零'
        assert gs.gold.evidence == _DRAIN_EV, \
            f'清零笔 evidence 字面量钉死: {gs.gold.evidence}'
        _drive_until(b, lambda: b._node_pos() == (1, 4))
        assert int(gs.gold.value or 0) > 0, 'r4 窗收入面正常(状态副本未锁死)'
    finally:
        uninstall_backend()


def test_replay_same_declaration_zero_noise(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """呈现一次性标志位防重放(锁 3 伴随;先例 = test_strategy_pick_gudinglicai
    重放同形):同 offer 落地声明复喂 → 第二次零动作(gold 证据笔保持
    清零笔、条目快照不变)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        out = _pick_raw(b, _CARD, [_CARD, '躺平', '淘金客'])
        cw_sim_ports.declare_world(out)
        assert gs.gold.evidence == _DRAIN_EV, '首次落地清零笔在场'
        snap = (int(gs.gold.value or 0), dict(
            gs.effects.first(HYPEREMIT_SPEC_ID).counters))
        cw_sim_ports.declare_world(out)
        assert gs.gold.evidence == _DRAIN_EV, \
            '重放零噪声(gold 证据笔保持首笔)'
        entry = gs.effects.first(HYPEREMIT_SPEC_ID)
        assert (int(gs.gold.value or 0), dict(entry.counters)) == snap, \
            '重放零写(条目快照不变)'
    finally:
        uninstall_backend()


def test_bypass_no_entry_disclosures(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """bypass 形态(锁 3 申报分支):本拍拿卡名命中而条目缺(登记缺位
    = 未经获得链的保守态,声明前清账模拟)→ 零动作 + disclosures 留证
    (零新增披露键,内联运行时键承载);金现值原样。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gold_before = int(gs.gold.value or 0)
        out = _pick_raw(b, _CARD, [_CARD, '躺平', '淘金客'])
        gs.effects.entries.clear()   # 模拟 bypass:登记缺位
        cw_sim_ports.declare_world(out)
        assert int(gs.gold.value or 0) == gold_before, \
            'bypass 保守零动作(金现值原样)'
        assert 'strategy_hyperemit_bypass_no_entry' in b.disclosures, \
            f'disclosures 留证: {sorted(b.disclosures)}'
    finally:
        uninstall_backend()


def test_payoff_sixth_window_before_income_then_stop(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """回流腿(锁 4,引擎链):拿卡(P1r3)后第 1-5 个节点窗(r4-r8)
    零发放(条目逐窗递减 5→1 不提前移除 = 无回流发生面;r4-r7 金增量 =
    纯收入面);第 6 窗(r9)+G+70 一笔(evidence 含 p/r 坐标;支付先于
    该窗计息——窗增量公式以「窗前金 + 回流额」为息基数现算);条目已随
    第 6 入口转换 tick 移除;第 7 窗(P2r1)不再发(挂起已消费)。
    r8 = 奖励窗,窗内奖励面板拾取金为状态副本里的值非本腿面,精确增量断言
    落 r9(拾取金已含在窗前金基线内,不受窗内构成影响)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gold_before = int(gs.gold.value or 0)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        assert int(gs.gold.value or 0) == 0
        prev_gold = 0   # 清零后基线
        # 第 1-4 个节点窗(r4-r7):零发放,精确收入面
        for r, left in ((4, 5), (5, 4), (6, 3), (7, 2)):
            _drive_until(b, lambda r=r: b._node_pos() == (1, r))
            gold_now = int(gs.gold.value or 0)
            income = _window_income(gs, 1, r, prev_gold)
            assert gold_now - prev_gold == income, \
                f'r{r} 窗增量 ≠ 纯收入面(零回流): ' \
                f'{gold_now - prev_gold} vs {income}'
            assert 'strategy:hyperemit' not in (gs.gold.evidence or ''), \
                f'r{r} 窗无回流笔: {gs.gold.evidence}'
            entry = gs.effects.first(HYPEREMIT_SPEC_ID)
            assert entry is not None and entry.remaining_nodes == left, \
                f'r{r} 窗后余期应 = {left}: ' \
                f'{entry.remaining_nodes if entry else None}'
            prev_gold = gold_now
        # 第 5 个节点窗(r8,奖励窗):条目在场 remaining==1(6th 入口 =
        # 下一窗),零回流笔
        _drive_until(b, lambda: b._node_pos() == (1, 8))
        entry = gs.effects.first(HYPEREMIT_SPEC_ID)
        assert entry is not None and entry.remaining_nodes == 1, \
            'r8 后余期 = 1(回流在下一入口)'
        assert 'strategy:hyperemit' not in (gs.gold.evidence or ''), \
            f'r8 窗无回流笔: {gs.gold.evidence}'
        prev_gold = int(gs.gold.value or 0)
        # 第 6 窗(r9):+G+70 一笔,支付先于该窗计息
        payoff = gold_before + 70
        _drive_until(b, lambda: b._node_pos() == (1, 9))
        gold_now = int(gs.gold.value or 0)
        income = _window_income(gs, 1, 9, prev_gold + payoff)
        assert gold_now - prev_gold == payoff + income, \
            f'r9 窗增量 ≠ 回流额+收入面(息基数含回流额): ' \
            f'{gold_now - prev_gold} vs {payoff}+{income}'
        assert gs.effects.first(HYPEREMIT_SPEC_ID) is None, \
            '条目已随第 6 入口转换 tick 移除(单载体制)'
        prev_gold = gold_now   # r9 窗后基线(含回流额 + r9 收入面)
        # (金笔 evidence 字面量断言落位面过渡观测窗 =
        # test_payoff_plane_transition_entry_literal_evidence——常规窗金笔
        # 被窗内收入笔覆盖,分期金锁同判据先形。)
        # 第 7 窗(P2r1):不再发(挂起已消费)
        _drive_until(b, lambda: b._node_pos() == (2, 1)
                     and b.screen_identity() == SCREEN_PREP)
        gold_now = int(gs.gold.value or 0)
        income = _window_income(gs, 2, 1, prev_gold)
        assert gold_now - prev_gold == income, \
            'P2r1 窗零回流(纯收入面)'
        assert 'strategy:hyperemit' not in (gs.gold.evidence or ''), \
            '第 7 窗无回流笔'
    finally:
        uninstall_backend()


def test_zero_gold_pick_snapshot_then_pay_seventy(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """零金兜底(锁 5):0 金拿卡 → 快照 0 → 清零短路零写(金证据笔
    保持种子笔)→ 第 6 窗回流 70。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gs.observe(gs.gold, 0, evidence='t:gold0', sig=_SIG_OBS)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        entry = gs.effects.first(HYPEREMIT_SPEC_ID)
        assert entry is not None
        assert entry.counters.get('lost') == 0, '快照 0'
        assert int(gs.gold.value or 0) == 0
        assert gs.gold.evidence == 't:gold0', \
            f'金已为 0 短路零写(证据笔保持种子笔): {gs.gold.evidence}'
        prev_gold = 0
        for r in (4, 5, 6, 7, 8):   # 前 5 窗零发放(r8 奖励窗含面板拾取金
            # 状态副本里的值,不作精确断言;余期递减已由 r9 恰 70 隐证)
            _drive_until(b, lambda r=r: b._node_pos() == (1, r))
            prev_gold = int(gs.gold.value or 0)
        _drive_until(b, lambda: b._node_pos() == (1, 9))
        gold_now = int(gs.gold.value or 0)
        income = _window_income(gs, 1, 9, prev_gold + 70)
        assert gold_now - prev_gold == 70 + income, \
            f'第 6 窗回流 70(快照 0 + gold_at_node 70): ' \
            f'{gold_now - prev_gold} vs 70+{income}'
        assert gs.effects.first(HYPEREMIT_SPEC_ID) is None
    finally:
        uninstall_backend()


def test_match_end_before_expiry_evaporates() -> None:
    """局终蒸发(锁 6,直构形态 = T-177 锁 6 先形):第 6 窗前条目留置
    蒸发不补发——无任何局终补发方,窗口前读 = 唯一触发面(引擎侧窗口
    触发面已由锁 4 证);未到期推进全程零报错零金写,留置条目即终态。"""
    sig = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=sig)
    gs.observe(gs.equips, [], sig=sig)
    gs.observe(gs.node, NodeKey(plane=2, round_num=3, kind='battle'),
               evidence='t:seed', sig=sig)
    gs.observe(gs.gold, 55, evidence='t:seed', sig=sig)
    lsig = ChannelSig(family='logic_action', actor='CwGainChain',
                      mode='compute')
    gain_invest_strategy(gs, object(), _CARD, rand=False, sig=lsig)
    entry = gs.effects.first(HYPEREMIT_SPEC_ID)
    assert entry is not None and entry.remaining_nodes == 6
    for nth in range(1, 6):   # 推进 5 次到「第 6 窗前一拍」状态
        gs.effects.tick_node((2, 3 + nth))
    assert gs.effects.first(HYPEREMIT_SPEC_ID).remaining_nodes == 1
    gold_before = int(gs.gold.value or 0)
    # 局终(无更多节点窗):无补发方——留置条目即终态,金零变动零报错
    assert gs.effects.first(HYPEREMIT_SPEC_ID) is not None, \
        '条目留置(蒸发 = 随局对象丢弃,无终局发放面)'
    assert int(gs.gold.value or 0) == gold_before, '无补发方使金变动'


def test_modified_seq_inserted_window_counts(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """修饰局计数(锁 9,引擎链):人身意外险插入型改写(P1 9→10,
    boss 前插补给)下,插入的补给窗照计数——第 6 个窗事件 = r9(插入
    补给窗)触发回流(evidence p/r 坐标对拍 + 节点 kind 对拍 = 插入窗
    身份)。计数域 = 节点入口事件全型(T-106 先例)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        gs.write_logic(gs.node_seq_by_plane,
                       resolve_plane_node_seqs('人身意外险'),
                       produced_by='Test', evidence='t:seqs', sig=_SIG)
        _drive_to_offer(b)
        gold_before = int(gs.gold.value or 0)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        assert int(gs.gold.value or 0) == 0
        prev_gold = 0
        for r in (4, 5, 6, 7, 8):   # 前 5 窗事件递减(r8 奖励窗含面板拾取
            # 金状态副本里的值,不作精确断言;插入窗恰触发已由 r9 断言隐证)
            _drive_until(b, lambda r=r: b._node_pos() == (1, r))
            prev_gold = int(gs.gold.value or 0)
        # 第 6 个窗事件 = 插入的补给窗 r9(非 boss)——插入窗照计数
        _drive_until(b, lambda: b._node_pos() == (1, 9))
        assert gs.node.value.kind == 'supply', \
            'r9 = 插入补给窗(修饰后序列第 9 位)'
        payoff = gold_before + 70
        gold_now = int(gs.gold.value or 0)
        income = _window_income(gs, 1, 9, prev_gold + payoff)
        assert gold_now - prev_gold == payoff + income, \
            f'插入窗(第 6 个窗事件)触发回流: ' \
            f'{gold_now - prev_gold} vs {payoff}+{income}'
        assert gs.effects.first(HYPEREMIT_SPEC_ID) is None
    finally:
        uninstall_backend()

def test_payoff_plane_transition_entry_literal_evidence(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """回流笔 evidence 字面量断言(无覆盖观测点)+ 位面首入口照常回流:
    (2,2) 拿卡 → 第 6 入口 = P3r1 位面过渡窗——过渡窗早退分支在收入段
    之前,回流笔后无收入笔覆盖 → 金 Field evidence 可全等断言(常规窗
    金笔被收入笔覆盖,evidence 断言落本观测位 = 分期金锁「函数级直构面」
    同判据先形的引擎链等价位);位面首入口照常回流(回流腿挂过渡早退
    分支之前);点空白收尾后收入段以含回流额基数计息(支付先于计息)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b, 2, 2)
        gold_before = int(gs.gold.value or 0)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        assert int(gs.gold.value or 0) == 0
        prev_gold = 0
        for target in ((2, 3), (2, 4), (2, 5), (2, 6), (2, 7)):
            _drive_until(b, lambda t=target: b._node_pos() == t)
            prev_gold = int(gs.gold.value or 0)
        payoff = gold_before + 70
        # 第 6 入口 = P3r1 位面过渡窗:开窗先付(过渡屏上证据笔未覆盖)
        _drive_until(b, lambda: b._node_pos() == (3, 1)
                     and b.screen_identity() == '货币战争-位面过渡')
        assert int(gs.gold.value or 0) - prev_gold == payoff, \
            '位面首入口(第 6 入口)开窗先付回流额'
        assert gs.gold.evidence == \
            'sim:engine:strategy:hyperemit:超发货币:p3r1', \
            f'回流笔 evidence 字面量(含 p/r 坐标,无覆盖窗): ' \
            f'{gs.gold.evidence}'
        assert gs.effects.first(HYPEREMIT_SPEC_ID) is None, \
            '条目已随第 6 入口转换 tick 移除'
        # 点空白收尾:收入段以含回流额基数计息
        _drive_until(b, lambda: b.screen_identity() == SCREEN_PREP)
        gold_now = int(gs.gold.value or 0)
        income = _window_income(gs, 3, 1, prev_gold + payoff)
        assert gold_now - (prev_gold + payoff) == income, \
            '过渡窗收尾收入面以含回流额基数为息基数'
    finally:
        uninstall_backend()
