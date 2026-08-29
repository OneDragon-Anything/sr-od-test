# -*- coding: utf-8 -*-
"""W192/ADR-0375 希儿系守卫辖域补全单帧锁(W190 巡检两件修法)。

辖域语义(**核心条件辖**,域修正:无条件辖首版 n=300 回归 never2 9→11,
回归局全程无希儿——transition_combos「没有希儿时量子/贝不能独立当
过渡(28 帖全部含希儿)」→ 无核心时放大器不是体系件):
- 希儿本人:唯一种子(在手副本 ≤1)不可卖/恒保护;
- 放大器件:仅当希儿在手时辖(卖拒=放大阵营在手 ≤2 成型门槛;
  保护集并入);无希儿时照旧 off_target 合法面。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 希儿唯一种子卖拒(候选不生成 + 弱序键 None + 谓词真)——
  W190 洞一「清空 tier=1 单卡依赖体系唯一件」;
- ② 放大器·有核心·跌破成型门槛:希儿在手 + 唯一贝件 → 卖拒;
- ③ 放大器·有核心·成型线以上冗余:希儿 + 贝 3 件 → 照旧可卖;
- ④ 放大器·无核心不辖:孤立花火(无希儿)→ off_target 照旧
  (首版无条件辖的回归形态——130/280/37 型);
- ⑤ owned=bench∪deployed 逐件计:bench 希儿 + deployed 娜塔莎(贝2)
  → 希儿仍唯一种子(同名副本口径)卖拒;
- ⑥ flag off 逐位回 W188 后行为(有核心的唯一放大件重新可卖);
- ⑦ 保护集单元:希儿恒入集;放大件仅 core_in_hand 时入;散件不入;
- ⑧ 补完事务集成(W190 洞二构造):pair={仙舟,列车}(希儿系∉pair),
  希儿系引擎已成型(希儿在场∧贝2)且 cap 满 → 补完 undeploy 不下
  希儿系贡献件;scope off 时 undeploy 吃希儿+佩拉(旧行为=洞的
  构造性复现)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_evolution import (
    EvolutionState,
    _locked_protected_names,
    evolution_step,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.cw_sim import _board_factions_of
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    CompTransaction,
    GameState,
    _recount_board,
    simulate,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.discipline import (
    sell_priority_key,
    sole_engine_sell_blocked,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY
_REG_SCOPE_OFF = dataclasses.replace(_REG, guard_seele_scope_enabled=False)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_round_key = (1, 5)
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _bc(name: str, faction: str = '', slot: int = 0, star: int = 1,
        row: str = 'back') -> BenchChar:
    if not faction:
        faction = (CHARACTERS[name].factions or ['?'])[0]
    return BenchChar(slot=slot, char_id=name, faction=faction,
                     position_pref=row, star=star)


def _sell_cands(st: GameState, sess: StrategySession, reg=_REG):
    return [c for c in generate_candidates(st, sess, reg)
            if c.tag in ('off_target', 'for_gold', 'free_bench')]


# ===== ①-⑥ 卖侧守卫辖域 =====


def test_guard_blocks_seele_sole_core() -> None:
    """①希儿唯一种子:在手副本 1(单卡依赖体系的不可替核心)→ 三卖
    tag 候选全无 + 弱序键 None + 谓词真(W190 洞一)。"""
    sess = _sess()
    st = _state(bench=[_bc('希儿', '贝洛伯格')])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is True
    assert _sell_cands(st, sess) == []
    assert sell_priority_key(st.bench[0], st, sess, None, _REG) is None


def test_guard_blocks_amp_below_formation_with_core() -> None:
    """②有核心·跌破成型门槛:希儿在手 + 唯一贝件娜塔莎(贝阵营 1≤2)
    → 卖拒(卖出使放大阵营跌破成型线 2,与 TT 系 owned≤tier 同构)。"""
    sess = _sess()
    st = _state(bench=[_bc('希儿', '贝洛伯格', 0),
                       _bc('娜塔莎', '贝洛伯格', 1)])
    assert sole_engine_sell_blocked(st.bench[1], st, _REG) is True
    assert sell_priority_key(st.bench[1], st, sess, None, _REG) is None


def test_guard_not_govern_redundant_amp_with_core() -> None:
    """③有核心·成型线以上冗余:希儿 + 佩拉/娜塔莎/杰帕德(贝 3>2)
    → 佩拉照旧可卖(体系有余量时清仓不受辖)。"""
    sess = _sess()
    st = _state(bench=[_bc('希儿', '贝洛伯格', 0),
                       _bc('佩拉', '贝洛伯格', 1),
                       _bc('娜塔莎', '贝洛伯格', 2),
                       _bc('杰帕德', '贝洛伯格', 3)])
    assert sole_engine_sell_blocked(st.bench[1], st, _REG) is False
    names = [c.breakdown_hint.get('name') for c in _sell_cands(st, sess)]
    assert '佩拉' in names, f'冗余放大件应可卖:{names}'


def test_guard_not_govern_amp_without_core() -> None:
    """④无核心不辖(域修正主锁):孤立花火(量子同频,无希儿在手)
    → off_target 照旧——无条件辖首版的回归形态(130/280/37 型:
    孤立放大件被禁卖堵 bench/被保护占 cap);transition_combos:
    没有希儿时量子/贝不能独立当过渡。"""
    sess = _sess()
    st = _state(bench=[_bc('花火', '盛会之星')])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is False
    cands = _sell_cands(st, sess)
    assert [c.breakdown_hint.get('name') for c in cands] == ['花火']
    assert cands[0].tag == 'off_target'
    assert sell_priority_key(st.bench[0], st, sess, None, _REG) is not None


def test_guard_core_sole_copy_caliber() -> None:
    """⑤核心种子口径:bench 希儿 + deployed 娜塔莎(贝)→ 希儿仍是
    唯一希儿副本 → 卖拒(放大件在体不解除核心唯一性;第二张希儿
    才构成冗余)。"""
    sess = _sess()
    st = _state(bench=[_bc('希儿', '贝洛伯格')],
                deployed=[_bc('娜塔莎', '贝洛伯格', slot=9)])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is True


def test_flag_off_restores_w188_behavior() -> None:
    """⑥guard_seele_scope_enabled=False 逐位回退:有核心的唯一放大
    件重新生成 off_target 卖候选 + 弱序键非 None(=W188 后行为;
    TT 三羁绊辖域由 sell_sole_engine_guard_enabled 独立辖,见 W184 ⑥)。"""
    sess = _sess()
    st = _state(bench=[_bc('希儿', '贝洛伯格', 0),
                       _bc('娜塔莎', '贝洛伯格', 1)])
    assert sole_engine_sell_blocked(st.bench[1], st, _REG_SCOPE_OFF) is False
    cands = _sell_cands(st, sess, _REG_SCOPE_OFF)
    names = [c.breakdown_hint.get('name') for c in cands]
    assert '娜塔莎' in names and cands[names.index('娜塔莎')].tag \
        == 'off_target'
    assert sell_priority_key(st.bench[1], st, sess, None,
                             _REG_SCOPE_OFF) is not None


# ===== ⑦-⑧ 保护集/补完事务辖域 =====


def test_locked_protected_names_core_conditional() -> None:
    """⑦保护集单元:希儿恒入集(seele_scope 开);放大件佩拉仅
    core_in_hand=True 时入;非体系散件(银枝)不入;scope off 回
    旧辖域(仅 TT 三羁绊)。"""
    sess = _sess()
    line = [_bc('希儿', '贝洛伯格', 0), _bc('佩拉', '贝洛伯格', 1),
            _bc('银枝', '星间旅人', 2)]
    # 默认(core_in_hand=False):仅希儿恒入集(本函数只见 old_line,
    # 全池核心判定由调用方从 state 计算后传入)
    assert _locked_protected_names(line, sess) == {'希儿'}
    assert _locked_protected_names(line, sess,
                                   seele_core_in_hand=True) \
        == {'希儿', '佩拉'}
    assert _locked_protected_names(line, sess, seele_scope=False) == set()


def test_completion_undeploy_keeps_seele_engine() -> None:
    """⑧补完事务集成(W190 洞二构造):pair={仙舟,列车}(希儿系∉pair),
    deployed 希儿+佩拉(贝2,引擎已成型)+5 散件占满 cap,bench 列车×2
    → 补完 undeploy 只吃非希儿系散件(引擎数不减);scope off 时
    undeploy 吃希儿+佩拉(旧行为=洞的构造性复现)。

    注意:计数层面补完方新成的列车引擎可在总数上抵平——洞在「希儿系
    体系」被清空(键级:补完后希儿不在场),非计数差。
    """
    # 散件全 cost≥3(佩拉 cost2 = 唯一最弱,保证 scope off 差分确定)
    _SEELE = ('希儿', '佩拉')
    _FILL = ('镜流', '黄泉', 'Saber', '那刻夏', '布洛妮娅')
    st = GameState()
    st.plane = 1
    st.round_num = 4
    st.level = 7
    st.gold = 30
    st.bench = [_bc('姬子·启行'), _bc('三月七')]
    st.deployed = [
        (_bc(n, row='front') if i < 3 else _bc(n))
        for i, n in enumerate((*_SEELE, *_FILL))]
    st.board = _recount_board(st.deployed)
    sess = StrategySession()
    sess.v3_intention = IntentionState(p1_pair=('仙舟', '列车同行'))

    def _tx(seele_scope: bool) -> CompTransaction:
        txs = [a for a in evolution_step(st, sess, EvolutionState(),
                                         seele_scope=seele_scope)
               if isinstance(a, CompTransaction)
               and 'engine_complete' in (a.reason or '')]
        assert txs, '列车 owned2≥2∧上场0 缺口应发补完事务'
        return txs[0]

    # scope on:undeploy 不含希儿系贡献件;事务 applied;希儿系保住
    tx = _tx(True)
    downed = {st.deployed[i].char_id for i in (tx.undeploy or [])}
    assert downed <= set(_FILL), f'希儿系贡献件被下场:{downed}'
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    assert '希儿' in {d.char_id for d in out.deployed
                    if d is not None and d.char_id}   # ADR-0392 滤 None
    assert _board_factions_of(out.deployed).get('贝洛伯格', 0) >= 2

    # scope off:undeploy 吃希儿+佩拉(最弱两件,均无 TT 保护)= W190
    # 洞二旧行为的构造性复现——希儿系引擎体系 1→0
    tx_off = _tx(False)
    downed_off = {st.deployed[i].char_id
                  for i in (tx_off.undeploy or [])}
    assert downed_off == {'希儿', '佩拉'}, \
        f'scope off 应下希儿+佩拉(旧行为):{downed_off}'
    out_off = simulate(st, tx_off)
    assert out_off.action_log[-1]['result'] == 'applied'
    names_off = {d.char_id for d in out_off.deployed
                 if d is not None and d.char_id}   # ADR-0392 滤 None
    assert '希儿' not in names_off, 'scope off:希儿系单卡被下场(旧行为)'
