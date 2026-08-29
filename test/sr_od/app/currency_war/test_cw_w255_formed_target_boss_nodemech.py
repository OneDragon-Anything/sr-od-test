# -*- coding: utf-8 -*-
"""ADR-0410 单帧锁:成型停手目标件白名单 + boss 升级禁令臂删除。

锁行为:
- 新语义正向:成型停手态下,目标件(锁定线 hoard 采购集 ∪ 引擎件)的
  BuyCard 通过层2 后置步;白名单外(非目标名)仍拒。
- 链日志:被拦行 formed_stop=True 且 kept=False;白名单放行的目标件行带
  formed_stop_exempt=True。
- 约束链:boss 轮(plane1 r9)中 EV 总账人口位臂成立的 LevelUp 被接受
  (旧禁令会以 'boss_levelup_ban:boss 轮禁升级' 拒);EV 总账不过
  (可负担性入口门)的 LevelUp 拒且拒因为息引擎总账文案(非 boss 文案)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_comps import (
    get_comp,
)
from sr_od.application.currency_war.cw_intention import (
    HoardTarget,
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.cw_system_cards import (
    engine_char_names,
)
from sr_od.application.currency_war.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.filters import (
    filter_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)


def _card(name: str, cost: int = 3) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _cands(buy_names: list[str]) -> list[Candidate]:
    """多条买候选(各一条)+ 等级买/刷新/卖/上阵各一(例外域)。"""
    out = [Candidate(action=BuyCard(_card(n), reason=''), tag='line_carry',
                     source='shop') for n in buy_names]
    out += [
        Candidate(action=LevelUp(cost=4), tag='levelup', source='xp'),
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
        Candidate(action=SellBench(bench_idx=0, income=1, expect=''),
                  tag='for_gold', source='bench'),
        Candidate(action=DeployMove(bench_idx=1, to_row='front',
                                    faction='仙舟罗浮'),
                  tag='deploy', source='fence'),
    ]
    return out


def _formed_state(**kw) -> GameState:
    """成型态(DOT队 form_tiers 全满 + 核心上场 2★ + P1 r7,金 60)。

    ADR-0418 前移后 r7 ∈ 新授权窗 {r6..r9}:白名单锁的夹具需
    成型停手真激活(窗内 gap>0 会转承接继续投资)。默认部署只含核心
    单件时板面维不足(gap 恒 1),镜像 w227 locked 帧补 DOT 第二件
    (桑博 1★)并抬 hp 到 64 → 承接达标 gap=0;kw 可覆盖。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 7, 'gold': 60, 'level': 5,
        'hp': 64, 'board': {f: t for f, t in comp.form_tiers.items()},
        'deployed': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2),
                     BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮',
                               star=1)],
        'bench': [],
        'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _sess_locked_with_hoard(comp_name: str = 'DOT队') -> StrategySession:
    """意向锁 + v3_hoard 目标集(update_target 的生产形态;否则
    _target_names 只有引擎件全集,hoard 采购集分支测不到)。"""
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp=comp_name)
    comp = get_comp(comp_name)
    chars = set(comp.core_chars) | set(getattr(comp, 'shared_chars', ())
                                       or set())
    sess.v3_hoard = HoardTarget(frozenset(chars), frozenset(), 'locked')
    return sess


def test_formed_stop_passes_target_piece() -> None:
    """新语义:成型停手态,hoard 目标件买入通过;过渡件(名单外)仍拒。"""
    core = intention_core(get_comp('DOT队'))
    state = _formed_state()
    sess = _sess_locked_with_hoard()
    # 名单外过渡件占位:从注册表取一个不在目标集/引擎件的普通件
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    sess2 = _sess_locked_with_hoard()
    from sr_od.application.currency_war.decision_v2.candidates import (
        _target_names,
    )
    _tg = _target_names(state, sess2)
    filler = next(n for n in CHARACTERS if n not in _tg)
    kept, log = filter_candidates(
        _cands([core, filler]), state, sess, DEFAULT_REGISTRY)
    names_kept = {c.action.card.name for c in kept
                  if isinstance(c.action, BuyCard)}
    assert core in names_kept, f'目标件 {core} 必须放行(W255 白名单)'
    assert filler not in names_kept, f'过渡件 {filler} 必须仍拒'
    assert sess.v3_formed_stop is True
    dropped = [e for e in log if e.get('formed_stop')]
    assert dropped and all(not e['kept'] for e in dropped)
    exempt = [e for e in log if e.get('formed_stop_exempt')]
    assert len(exempt) == 1


def test_formed_stop_engine_whitelist_without_hoard() -> None:
    """裸 session(v3_hoard 缺):白名单退化到引擎件全集(种子语义),
    引擎件放行、普通体系外件拒。"""
    engine = next(iter(engine_char_names()))
    filler = '卡芙卡' if engine != '卡芙卡' else '希儿'
    state = _formed_state()
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    kept, _ = filter_candidates(_cands([engine, filler]),
                                state, sess, DEFAULT_REGISTRY)
    names = {c.action.card.name for c in kept
             if isinstance(c.action, BuyCard)}
    assert engine in names and filler not in names


# ---------- boss 升级禁令臂删除(约束链验证) ----------

def _boss_frame_state(gold: int = 70) -> GameState:
    """cap 满 + bench 有目标件等待上场,P1 r9 boss 帧
    (deploy_cap 补偿触发形态,镜像 w52 锁基座)。"""
    st = GameState(
        plane=1, round_num=9, node_type='boss', gold=gold,
        level=5, hp=60, board={},
        bench=[BenchChar(slot=i, char_id=n, faction='公司', star=1)
               for i, n in enumerate(['姬子·启行', '卡芙卡'])],
        shop=[],
        deployed=[BenchChar(slot=i, char_id=n, faction='公司', star=2)
                  for i, n in enumerate(['丹恒·饮月', '千冶·刃', '绯英',
                                         '娜塔莎', '阿格莱雅'])],
    )
    return st


def _sess_for_compensation(round_key: tuple[int, int]) -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='unlocked')
    sess.v3_core_names = {'姬子·启行'}
    sess.v2_round_key = round_key
    return sess


def test_boss_round_levelup_allowed_via_ev_basis() -> None:
    """boss 帧内,cap 满+bench 有目标件(EV 总账人口位臂成立)→ 补偿级
    LevelUp 接受,'boss 轮禁升级' 文案不出现。"""
    st = _boss_frame_state()
    cand = Candidate(action=DeployMove(bench_idx=0, to_row='back',
                                       faction='列车同行'),
                     tag='deploy', source='test')
    res = arbitrate([(cand, 5.0, {})], st,
                    _sess_for_compensation((1, 9)), DEFAULT_REGISTRY)
    lvs = [a for a in res.actions if isinstance(a, LevelUp)]
    assert lvs, ('boss 帧 LevelUp 应经 EV 人口位臂接受(ADR-0410):'
                 f'{[r.get("reject") for r in res.log]}')
    # 授权臂不锁死(pop_slot/dp/static_ev 随金位与 DP 姿态浮动):
    # 锁「经 EV 总账放行」本身——auth_basis 非空即可。
    assert all(a.auth_basis for a in lvs)
    joined = '; '.join(r.get('reject') or '' for r in res.log)
    assert 'boss 轮禁升级' not in joined


def test_boss_frame_levelup_rejected_only_by_ev_account() -> None:
    """EV 总账不过(金不足可负担性入口门)→ 拒因走息引擎总账文案,
    非 boss 文案(约束名保留、裁决去 boss 化的行为锁)。"""
    from dataclasses import replace
    reg = replace(DEFAULT_REGISTRY, formed_stop_enabled=False)
    st = _boss_frame_state(gold=2)   # 金 2 < 单击价 4 → 可负担性拒
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='test')
    res = arbitrate([(cand, 5.0, {})], st,
                    _sess_for_compensation((1, 9)), reg)
    row = next(r for r in res.log if r['tag'] == 'levelup')
    assert not row['accepted']
    assert 'boss 轮禁升级' not in (row.get('reject') or '')
