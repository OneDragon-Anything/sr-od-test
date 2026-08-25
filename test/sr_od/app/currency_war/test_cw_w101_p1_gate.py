"""货币战争 · P1 锁线资格门(W101/ADR-0341)测试。

锁行为(诊断源=W97 §5 P0-1:万敌单C 被③锁 30.5%,hp 19.7 vs DOT 类
过渡线 28.5-30.7;口述锚=transitions §1「拿到逆天投资策略才配锁直通线」):
- P1 终局专属线(锁线方向不含过渡引擎):③核心卡/④资源证据被门拦下
  (贯穿件照买照囤 [21],只是不构成 P1 锁线证据);
- ①类资格(策略/环境亲和,与 W85 ②门同源)成立 → 放行;
- 过渡线(DOT队/专家桑博DOT/列车同行/希儿量子)+ ⑤兜底线(绯英欢愉)不受辖;
- P2/P3 不辖([21] 上场窗口与 1-8 换血点都在 P1 后);
- 门开关 P1_FINAL_LINE_GATE=False = sim A/B 基线臂(旧行为);
- 派生分类快照锁(CROSS_LINE_SKELETON 同款判例:数据漂移静默改门=禁止)。
"""
from __future__ import annotations

from sr_od.application.currency_war import cw_intention
from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    _p1_transition_eligible,
    _v2_comps,
    detect_signals,
    hoard_target_set,
    update_intention,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState, ShopCard


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


def test_p1_gate_free_for_seele_line() -> None:
    """希儿系=四体系之一:③信号检测照发;P1 锁定产物=配方对
    (希儿系进对须希儿到手,见 test_cw_intention W145 节),comp 不锁。"""
    st = _state(shop=['希儿'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '希儿量子' and s.kind == 'core_card'
               for s in sigs if s.layer == 3)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''


# ===== ④资源层同门 =====

def test_p1_gate_resource_layer() -> None:
    """④升费资源证据与③同类(卡/资源到手):P1 拦狼尊欢愉(终局专属,
    资源锚 9 级),P2 放行。"""
    st = _state(bench=['银狼LV.999'])
    assert not any(s.comp_name == '狼尊欢愉' for s in detect_signals(st))
    st2 = _state(plane=2, bench=['银狼LV.999'])
    assert any(s.comp_name == '狼尊欢愉' and s.kind == 'resource'
               for s in detect_signals(st2) if s.layer == 4)


# ===== A/B 通道:门关=旧行为 =====

def test_gate_off_restores_baseline(monkeypatch) -> None:
    """P1_FINAL_LINE_GATE=False(A/B 基线臂)→ 万敌单C ③锁恢复
    (W97 诊断的 30.5% 病灶形态即此臂)。W145 后 P1 comp 锁定另受
    P1_RECIPE_LOCK 辖——基线臂须双开关同关(回 W143 前完整行为)。"""
    monkeypatch.setattr(cw_intention, 'P1_FINAL_LINE_GATE', False)
    monkeypatch.setattr(cw_intention, 'P1_RECIPE_LOCK', False)
    st = _state(bench=['万敌'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '万敌单C' and s.kind == 'core_card'
               for s in sigs if s.layer == 3)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '万敌单C' and ist.lock_layer == 3


# ===== 派生分类快照锁 =====

def test_derived_classification_snapshot() -> None:
    """过渡线派生分类快照(W97 §5 P0-1 分组的代码化;数据漂移静默改门=禁止,
    CROSS_LINE_SKELETON 快照锁同款判例)。FREE 集=主/副档∩三羁绊体系键
    ∪ 希儿∈core ∪ ⑤兜底;其余 v2 线为终局专属(P1 需①类资格)。"""
    free = {c.name for c in _v2_comps() if _p1_transition_eligible(c)}
    assert free == {'列车同行', 'DOT队', '专家桑博DOT', '希儿量子', '绯英欢愉'}
