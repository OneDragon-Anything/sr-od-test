"""test_cw_intention_gate 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w101_p1_gate: test_cw_w101_p1_gate.py
- w103_strategy_dead: test_cw_w103_strategy_dead.py
- w107_formed_stop: test_cw_w107_formed_stop.py
- w114_phase_shadow: test_cw_w114_phase_shadow.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

# ==================== w101_p1_gate ====================
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    _p1_transition_eligible,
    _v2_comps,
    detect_signals,
    hoard_target_set,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)


def _state(**kw) -> GameState:
    s = GameState()
    s.plane = kw.get('plane', 1)
    s.round_num = kw.get('round_num', 1)
    s.level = kw.get('level', 5)
    s.active_env = kw.get('active_env', '')
    s.active_strategies = list(kw.get('strategies', []))
    for name in kw.get('bench', []):
        ch = CHARACTERS.get(name)
        s.bench.append(BenchChar(slot=len(s.bench), char_id=name,
                                 faction=ch.factions[0] if ch and ch.factions else '?',
                                 star=kw.get('bench_star', 1)))
    for name in kw.get('shop', []):
        ch = CHARACTERS.get(name)
        s.shop.append(ShopCard(x=len(s.shop), name=name,
                               faction=ch.factions[0] if ch and ch.factions else '?',
                               cost=ch.cost if ch else 3))
    for fac, n in kw.get('board', {}).items():
        s.board[fac] = n
    return s


# ===== ③核心卡:P1 门拦终局专属线 =====

def test_p1_gate_blocks_final_line_core_card() -> None:
    """P1 万敌(贯穿件)在手 → ③不发万敌单C,意向 unlocked;囤货方向落
    配方过渡方向(W145/ADR-0357 起 P1 兜底=四体系全集,非绯英)。"""
    st = _state(bench=['万敌'])
    sigs = detect_signals(st)
    assert not any(s.comp_name == '万敌单C' for s in sigs if s.layer == 3)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    assert hoard_target_set(st, ist).mode == 'p1_transition'


def test_p2_core_card_still_locks_final_line() -> None:
    """P2 万敌在手 → ③照旧锁线([23] 合法路径在 P2/P3 保持;门只辖 P1)。"""
    st = _state(plane=2, bench=['万敌'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '万敌单C' and s.kind == 'core_card'
               for s in sigs if s.layer == 3)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.locked_comp == '万敌单C'


def test_p1_gate_qualified_by_env_locks() -> None:
    """P1 终局专属线持①类资格(命运圣杯契约)→ 锁线放行
    (资格=策略/环境亲和,transitions §1「逆天投资策略」语义;
    无资格对照:同布局无 env → 不锁)。"""
    st_q = _state(bench=['Saber'], active_env='命运圣杯契约')
    ist_q = update_intention(st_q, IntentionState())
    assert ist_q.phase == 'locked' and ist_q.locked_comp == '双王圣杯'
    assert ist_q.lock_layer == 1
    st_n = _state(bench=['Saber'])
    ist_n = update_intention(st_n, IntentionState())
    assert ist_n.phase == 'unlocked' and ist_n.locked_comp == ''


# ===== 过渡线/兜底线不受辖 =====

def test_p1_gate_free_for_transition_lines() -> None:
    """过渡线信号检测不受辖(detect_signals 层③照发);W145/ADR-0357 起
    P1 ③不再锁终局 comp——DOT队/绯英欢愉锁定被配方锁取代(落体系对/
    过渡方向),锁线仅 P2(回归见 test_p2_core_card)。"""
    st = _state(shop=['卡芙卡'])
    sigs = detect_signals(st)
    assert any(s.comp_name == 'DOT队' and s.kind == 'core_card'
               for s in sigs if s.layer == 3)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    st_f = _state(shop=['绯英'])
    sigs_f = detect_signals(st_f)
    assert any(s.comp_name == '绯英欢愉' for s in sigs_f if s.layer == 3)
    ist_f = update_intention(st_f, IntentionState())
    assert ist_f.phase == 'unlocked' and ist_f.locked_comp == ''
    # P2:③照旧锁 comp(过渡线在 P2 是合法终局方向)
    ist_p2 = update_intention(_state(plane=2, shop=['卡芙卡']),
                              IntentionState())
    assert ist_p2.locked_comp == 'DOT队'


def test_p1_transition_eligible_snapshot() -> None:
    """过渡线派生分类快照(W97 §5 P0-1 分组的代码化;数据漂移静默改门=禁止,
    CROSS_LINE_SKELETON 快照锁同款判例)。FREE 集=主/副档∩三羁绊体系键
    ∪ 希儿∈core ∪ ⑤兜底;其余 v2 线为终局专属(P1 需①类资格)。"""
    free = {c.name for c in _v2_comps() if _p1_transition_eligible(c)}
    assert free == {'列车同行', 'DOT队', '专家桑博DOT', '希儿量子', '绯英欢愉'}


# ==================== w103_strategy_dead ====================

import json
from pathlib import Path

from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.telemetry import query, recorder, state


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def test_dead_streak_transition_state_machine() -> None:
    """同 key 重入不计数;换 key 时 live 复位 / dead 递增。"""
    t = query.dead_streak_transition
    # 首轮(prev None):不结算
    assert t(None, (1, 1), 0, True) == 0
    assert t(None, (1, 1), 2, False) == 2
    # 同轮重入(过渡帧/重试):不结算
    assert t((1, 1), (1, 1), 1, False) == 1
    # 换轮:live 复位
    assert t((1, 1), (1, 2), 1, True) == 0
    # 换轮:dead 递增
    assert t((1, 1), (1, 2), 0, False) == 1
    assert t((1, 2), (1, 3), 1, False) == 2   # 连击到 2 = loop 侧停局线


def test_strategy_round_live_with_cache(tmp_path, monkeypatch) -> None:
    """mtime 缓存:写入后重查可见;不同 run 互不串。"""
    rec = recorder.TelemetryRecorder(
        replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(state, '_RECORDER', rec)
    query._STRATEGY_LIVE_CACHE.clear()
    f = tmp_path / 'decisions.jsonl'
    _write_rows(f, [
        {'run_id': 'r1', 'plane': 1, 'round_num': 1, 'strategy_id': ''},
        {'run_id': 'r1', 'plane': 1, 'round_num': 2, 'strategy_id': 'decision_v2'},
    ])
    assert query.strategy_round_live('r1', (1, 1)) is False
    assert query.strategy_round_live('r1', (1, 2)) is True
    # 追加(新 mtime)后缓存失效重扫:r1 r1 也变 live
    _write_rows(f, [{'run_id': 'r1', 'plane': 1, 'round_num': 1,
                     'strategy_id': 'decision_v2'}])
    assert query.strategy_round_live('r1', (1, 1)) is True


def test_check_strategy_live_streak_w98_shape() -> None:
    """W98 两局形态(整局恒空)必报;健康局不报;孤立短段不报。"""
    c = query.check_strategy_live_streak
    # W98 形态:P1 全轮 strategy_id 恒空(003757: 57 行实录形状)
    dead_rows = [
        {'plane': 1, 'round_num': rn, 'strategy_id': ''}
        for rn in range(1, 10)
    ]
    v = c(dead_rows)
    assert v and '9 轮' in v[0] and 'W98' in v[0]
    # 健康局:每轮都有 live 行
    ok_rows = [
        {'plane': 1, 'round_num': rn, 'strategy_id': 'decision_v2'}
        for rn in range(1, 10)
    ]
    assert c(ok_rows) == []
    # 混合行投影:同轮任一行带 strategy_id 即 live
    mixed = [{'plane': 1, 'round_num': 1, 'strategy_id': ''},
             {'plane': 1, 'round_num': 1, 'strategy_id': 'decision_v2'}]
    assert c(mixed) == []
    # 孤立 2 轮空段(< 阈值 3)不报
    short = [{'plane': 1, 'round_num': rn, 'strategy_id': ''}
             for rn in (1, 2)] + [
        {'plane': 1, 'round_num': rn, 'strategy_id': 'decision_v2'}
        for rn in (3, 4)]
    assert c(short) == []
    # P2 空轮不辖(只辖 P1)
    p2 = [{'plane': 2, 'round_num': rn, 'strategy_id': ''}
          for rn in range(1, 5)]
    assert c(p2) == []


def test_run_checks_reports_dead_run(tmp_path, monkeypatch) -> None:
    """run_checks_on_replay 对失活局出「[策略失活]」行(不被判栈跳过)。"""
    rec = recorder.TelemetryRecorder(
        replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(state, '_RECORDER', rec)
    _write_rows(tmp_path / 'decisions.jsonl', [
        {'run_id': 'dead1', 'plane': 1, 'round_num': rn, 'strategy_id': '',
         'actions': [{'__type__': 'EnsureShopClosed'}]}
        for rn in range(1, 6)
    ])
    _write_rows(tmp_path / 'outcomes.jsonl', [
        {'run_id': 'dead1', 'plane': 1, 'round_num': rn} for rn in range(1, 6)
    ])
    lines = ledger_hooks.run_checks_on_replay(tmp_path, recent=5)
    assert any('[策略失活]' in x and 'dead1' in x for x in lines), lines




# ==================== w107_formed_stop ====================

from dataclasses import replace

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.filters import (
    filter_candidates,
    formed_stop_active,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    intention_core,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    DeployMove,
    LevelUp,
    RefreshShop,
    SellBench,
)
from sr_od.application.currency_war.sim.checks.ledger import (
    check_overflow_gold_zero_buy_streak,
)


def _card(name: str = '测试卡', cost: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _cands() -> list[Candidate]:
    """四类候选各一(买/等级买/刷新/卖+上阵)。"""
    return [
        Candidate(action=BuyCard(_card(), reason=''), tag='line_carry',
                  source='shop'),
        Candidate(action=LevelUp(cost=4), tag='levelup', source='xp'),
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
        Candidate(action=SellBench(bench_idx=0, income=1, expect=''),
                  tag='for_gold', source='bench'),
        Candidate(action=DeployMove(bench_idx=1, to_row='front',
                                    faction='仙舟罗浮'),
                  tag='deploy', source='fence'),
    ]


def _formed_state(**kw) -> GameState:
    """成型态:DOT队 form_tiers 全满 + 核心**上场** 2★ + P1 r7。

    ADR-0347 构造适配:formed_stop 收编 form_ok——核心须上场
    (旧帧核心躺 bench;「核心须上场」是 2026-08-25 用户裁决,
    影子批已注记本锁需同步)。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    board = {f: t for f, t in comp.form_tiers.items()}
    base = {
        'plane': 1, 'round_num': 7, 'gold': 60, 'level': 5,
        'hp': 60, 'board': board,
        'deployed': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2)],
        'bench': [],
        'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _sess_locked(comp_name: str = 'DOT队') -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp=comp_name)
    return sess


def test_formed_stop_blocks_buy_keeps_exceptions() -> None:
    """成型态(gap=0)买被拦;等级买/刷新/卖/上阵保留([12]/[33] 例外)。

    ADR-0418 gate_min_round 前移 8→6 后 r7 落进新授权窗——窗内
    gap>0 时承接维不停手继续投资,与「成型停手拦买」原意图冲突;与
    对 ADR-0418 的既定改法同式,夹具改构造「窗内∧承接达标
    (gap=0)」帧(hp 64 → boss 投影后 hp 档达标)锁「窗内 gap=0 仍
    停手拦买」:停手结构本身在原参数语义下不变。」"""
    # 承接达标构造:镜像 w227 locked 帧形态——单核心上场帧板面维不足
    # (gap 恒 1),补 DOT 第二件(桑博 1★)后 hp 64 投影达标 gap=0。
    core_name = intention_core(get_comp('DOT队'))
    state = _formed_state(
        hp=64,
        deployed=[BenchChar(slot=0, char_id=core_name, faction='仙舟罗浮',
                            star=2),
                  BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮',
                            star=1)])
    sess = _sess_locked()
    kept, log = filter_candidates(_cands(), state, sess, DEFAULT_REGISTRY)
    assert sess.v3_handoff_gap == 0, '夹具前提:承接达标帧 gap=0'
    tags = {c.tag for c in kept}
    assert 'line_carry' not in tags, '成型 r7+(gap=0)买候选必须被拦'
    assert {'levelup', 'refresh', 'for_gold', 'deploy'} <= tags
    assert sess.v3_formed_stop is True
    dropped = [e for e in log if e['formed_stop']]
    assert dropped and all(not e['kept'] for e in dropped)


def test_unformed_each_piece_passes() -> None:
    """form_ok 谓词缺一即不辖(ADR-0347 收编后;Q2 裁决:等级
    不再是独立条件——lv4 帧随裁决改为合法成型,不辖项换成谓词族):
    ① 核心 2★ 躺 bench(未上场,「核心须上场」裁决);
    ② 羁绊未满(主档缺 1);
    ③ 核心上场但 1★。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    # ① 核心 2★ 在 bench 不上场
    s1 = _formed_state(
        deployed=[BenchChar(slot=0, char_id='桑博', faction='仙舟罗浮',
                            star=1)],
        bench=[BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                         star=2)])
    # ② 羁绊未满(主档缺 1)
    board2 = dict(comp.form_tiers)
    k0 = next(iter(board2))
    board2[k0] = board2[k0] - 1
    s2 = _formed_state(board=board2)
    # ③ 核心上场但 1★
    s3 = _formed_state(deployed=[BenchChar(slot=0, char_id=core,
                                           faction='仙舟罗浮', star=1)])
    for s in (s1, s2, s3):
        sess = _sess_locked()
        assert formed_stop_active(s, sess, DEFAULT_REGISTRY) is False
        kept, _ = filter_candidates(_cands(), s, sess, DEFAULT_REGISTRY)
        assert any(isinstance(c.action, BuyCard) for c in kept)


def test_window_and_plane_gates() -> None:
    """r6 不辖(证据窗 r7+);P2 不辖([13] 是 P1 语义)。"""
    sess1 = _sess_locked()
    assert formed_stop_active(_formed_state(round_num=6), sess1,
                              DEFAULT_REGISTRY) is False
    sess2 = _sess_locked()
    assert formed_stop_active(_formed_state(plane=2), sess2,
                              DEFAULT_REGISTRY) is False


def test_unlocked_intent_not_governed() -> None:
    """意向未锁(unlocked/兜底):「羁绊凑够」无定义,保守不辖。"""
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='unlocked')
    assert formed_stop_active(_formed_state(), sess, DEFAULT_REGISTRY) is False


def test_emergency_does_not_exempt() -> None:
    """应急态(hp≤emergency_hp)不豁免——反因路径正是对象。

    ADR-0418 前移后 r7 ∈ 新授权窗,应急帧 hp=10 必然 gap>0,
    承接维接管=继续投资(与「应急不豁免」断言正交);本锁用 replace
    把 min_round 钉回 8,在旧窗参数下保住原边界意图(应急帧停在授权
    窗外时停手拦买、应急不额外豁免);窗内 gap>0 时承接维让应急让位
    的现行行为(继续投资)另显式立锁于下一用例。"""
    reg = replace(DEFAULT_REGISTRY, handoff_gate_min_round=8)
    s = _formed_state(hp=10)   # hp ≤ 25 = emergency
    sess = _sess_locked()
    kept, _ = filter_candidates(_cands(), s, sess, reg)
    assert not any(isinstance(c.action, BuyCard) for c in kept)
    # 等级买在应急集内本就放行,停手不额外拦
    assert any(c.tag == 'levelup' for c in kept)


def test_emergency_in_new_window_handoff_takes_over() -> None:
    """新窗行为锁(ADR-0418):授权窗内(r7)承接缺口帧 gap>0 →
    承接维接管,应急态(hp≤25)让位——现行行为=不停手继续投资(买
    候选保留;应急豁免逻辑只作用于停手线,不反拦承接投资例外)。"""
    s = _formed_state(hp=10)   # 应急 ∧ 低血 → 承接缺口必 >0
    sess = _sess_locked()
    kept, _ = filter_candidates(_cands(), s, sess, DEFAULT_REGISTRY)
    assert sess.v3_handoff_gap >= 1, '夹具前提:应急低血帧承接缺口>0'
    assert sess.v3_formed_stop is False, '承接维接管:不停手'
    assert any(isinstance(c.action, BuyCard) for c in kept), (
        '窗内 gap>0 应急帧=继续投资(ADR-0418 现行行为)')


def test_switch_off_restores_old_behavior() -> None:
    """总开关 False=旧行为(成型照买)。"""
    reg = replace(DEFAULT_REGISTRY, formed_stop_enabled=False)
    sess = _sess_locked()
    kept, log = filter_candidates(_cands(), _formed_state(), sess, reg)
    assert any(isinstance(c.action, BuyCard) for c in kept)
    assert sess.v3_formed_stop is False


def test_checker_exempts_formed_stop_rounds() -> None:
    """检查器联动:formed_stop 轮重置 streak;旧局无字段不受影响。"""
    def _row(r: int, gold: int = 60, fs: bool | None = None) -> dict:
        d = {'plane': 1, 'round_num': r, 'gold': gold, 'actions': [],
             'run_id': 't'}
        if fs is not None:
            d['formed_stop'] = fs
        return d
    # 旧语义保持:两轮金>50 零买零升级(无标志)→ 违规
    assert check_overflow_gold_zero_buy_streak([_row(7), _row(8)])
    # 成型停手轮夹在中间 → streak 被重置,不再连成 ≥2
    assert not check_overflow_gold_zero_buy_streak(
        [_row(7), _row(8, fs=True), _row(9)])
    # 成型前(未成型)的断买仍报——停手不回溯洗白早前违规
    assert check_overflow_gold_zero_buy_streak(
        [_row(5), _row(6), _row(7, fs=True), _row(8)])


# ==================== w114_phase_shadow ====================


from sr_od.application.currency_war.decision.decision_v2.phase import (
    Phase,
    derive_phase,
    form_ok,
    form_score,
)


def _comp_frame(**kw) -> GameState:
    """成型态帧:DOT队 form_tiers 全满(board 只数上场)+ 核心上场 2★。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 7, 'gold': 40, 'level': 5,
        'hp': 60, 'board': {f: t for f, t in comp.form_tiers.items()},
        'deployed': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2)],
        'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _w114_phase_shadow_sess_locked() -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    return sess


def test_case1_unlocked_empty_board_form() -> None:
    """①意向未锁+板面空 → FORM;form_ok=False(兜底门:有效体系数 0<2)。"""
    state = GameState(plane=1, round_num=1, gold=10, level=3, hp=100)
    sess = StrategySession()   # 默认 unlocked
    assert form_ok(state, sess, DEFAULT_REGISTRY) is False
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.FORM
    assert form_score(state, DEFAULT_REGISTRY) == 0.0


def test_case2_locked_formed_gold40_hoard() -> None:
    """②意向锁定+羁绊凑够+核心上场 2★+金 40 → HOARD;form_ok=True。"""
    state = _comp_frame(gold=40)
    sess = _w114_phase_shadow_sess_locked()
    assert form_ok(state, sess, DEFAULT_REGISTRY) is True
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.HOARD


def test_case3_same_frame_gold55_spend() -> None:
    """③同②帧但金 55(≥interest_floor=50)→ SPEND。"""
    state = _comp_frame(gold=55)
    sess = _w114_phase_shadow_sess_locked()
    assert form_ok(state, sess, DEFAULT_REGISTRY) is True
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.SPEND


def test_case4_core_one_star_form() -> None:
    """④意向锁定+羁绊凑够但核心仍 1★ → FORM(核心未达 2★)。

    附:核心 2★ 躺 bench(未上场)同样不算——「核心须上场」裁决。
    """
    comp = get_comp('DOT队')
    core = intention_core(comp)
    # 核心上场但 1★
    s1 = _comp_frame(deployed=[BenchChar(slot=0, char_id=core,
                                         faction='仙舟罗浮', star=1)])
    # 核心 2★ 但在 bench 不在场上
    s2 = _comp_frame(deployed=[], bench=[
        BenchChar(slot=0, char_id=core, faction='仙舟罗浮', star=2)])
    for s in (s1, s2):
        sess = _w114_phase_shadow_sess_locked()
        assert form_ok(s, sess, DEFAULT_REGISTRY) is False, (
            '核心未达(1★ 或未上场)时 form_ok 必须为 False')
        assert derive_phase(s, sess, DEFAULT_REGISTRY) is Phase.FORM


def test_phase_score_bounds_and_fallback_gate() -> None:
    """form_score ∈ [0,1](纯遥测观测,ADR-0353 起不进判据);兜底门走
    registry 结构常量(可 A/B 注入,禁散落)。

    兜底降级路径(W132/ADR-0353 结构判据):未锁但上场阵容拉满 2 过渡
    体系(真角色上场)→ 有效体系数 ≥ phase_fallback_min_engines →
    form_ok True(体系判定单一源 _engines_count);r<phase_fallback_min_round
    同板仍 False。
    """
    assert DEFAULT_REGISTRY.phase_fallback_min_engines >= 1
    assert DEFAULT_REGISTRY.phase_fallback_min_round >= 1
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        TRANSITION_TRAITS,
    )
    traits = dict(TRANSITION_TRAITS)
    deployed: list[BenchChar] = []
    used: set[str] = set()
    for bond, tier in list(traits.items())[:2]:   # 前两体系逐个凑
        got = 0
        for cid, ch in CHARACTERS.items():
            if got >= tier or cid in used:
                continue
            if bond in (ch.factions or ()) + (ch.flows or ()):
                used.add(cid)
                got += 1
                deployed.append(BenchChar(
                    slot=len(deployed), char_id=cid,
                    faction=ch.factions[0], star=1))
        assert got >= tier, f'角色表凑不齐体系 {bond}×{tier}'
    sess = StrategySession()   # unlocked → 兜底门路径
    state = GameState(plane=1, round_num=5, gold=30, level=6, hp=80,
                      deployed=deployed, bench=[], shop=[])
    score = form_score(state, DEFAULT_REGISTRY)
    assert 0.0 <= score <= 1.0
    assert form_ok(state, sess, DEFAULT_REGISTRY) is True
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.HOARD
    # 同板 r<min_round → 仍 FORM(轮数下限合取)
    s_early = GameState(plane=1, round_num=4, gold=30, level=6, hp=80,
                        deployed=deployed, bench=[], shop=[])
    assert form_ok(s_early, sess, DEFAULT_REGISTRY) is False


def test_fallback_gate_run15_counterexample() -> None:
    """W132/ADR-0353 病象锁:实机 run15 r4/r6 帧(意向未锁,仙舟3 单体系
    + 多线散件,form_score=0.65)在新门下**仍 FORM**——「凑羁绊档过门」
    ≠「板面朝一条线收敛」(用户判读原则 2026-08-26)。

    帧 = run_20260825_225052 r6 复刻:deployed 饮月/藿藿/腾荒/爻光/
    阿格莱雅(仙舟3 引擎=1,其余散线各 1 档);旧门 score 0.65≥0.5 且
    r6≥5 曾转真(HOARD→SPEND,金 49→92 板面不动)。
    """
    names = ['丹恒·饮月', '藿藿', '丹恒·腾荒', '爻光', '阿格莱雅']
    deployed = [BenchChar(slot=i, char_id=n, faction='仙舟', star=1)
                for i, n in enumerate(names)]
    sess = StrategySession()   # unlocked
    state = GameState(plane=1, round_num=6, gold=49, level=5, hp=52,
                      deployed=deployed, bench=[], shop=[])
    assert form_score(state, DEFAULT_REGISTRY) >= 0.5, (
        '复刻帧应具旧门过门分数(病象前提)')
    assert form_ok(state, sess, DEFAULT_REGISTRY) is False, (
        '单体系+散线板:有效体系数 1 < 2,兜底门必须拒')
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.FORM


def test_fallback_gate_hp_charge_stack_exemption() -> None:
    """W132/ADR-0353 万敌豁免(W127 global_accumulators 消费):万敌 2★
    上场(hp_charge_stack 型受击驱动全局叠层)计 1 等效体系;1★ 不豁免;
    豁免集不含 cost_escalation 型(银狼)。
    """
    from sr_od.application.currency_war.decision.decision_v2.phase import (
        fallback_engines_count,
    )
    from sr_od.application.currency_war.kernel.cw_comps import hp_charge_stack_chars
    assert hp_charge_stack_chars() == frozenset({'万敌'})
    # 仙舟3 单体系 + 万敌 2★ → 有效体系数 2 → True(r≥5)
    trio = ['丹恒·饮月', '藿藿', '爻光']
    deployed = [BenchChar(slot=i, char_id=n, faction='仙舟', star=1)
                for i, n in enumerate(trio)]
    deployed.append(BenchChar(slot=3, char_id='万敌',
                              faction='夜之半神', star=2))
    sess = StrategySession()
    state = GameState(plane=1, round_num=5, gold=30, level=6, hp=80,
                      deployed=deployed, bench=[], shop=[])
    assert fallback_engines_count(state) == 2
    assert form_ok(state, sess, DEFAULT_REGISTRY) is True
    # 万敌 1★:豁免不生效(核心 2★ 同向保守)
    deployed[3] = BenchChar(slot=3, char_id='万敌',
                            faction='夜之半神', star=1)
    state2 = GameState(plane=1, round_num=5, gold=30, level=6, hp=80,
                       deployed=deployed, bench=[], shop=[])
    assert fallback_engines_count(state2) == 1
    assert form_ok(state2, sess, DEFAULT_REGISTRY) is False


