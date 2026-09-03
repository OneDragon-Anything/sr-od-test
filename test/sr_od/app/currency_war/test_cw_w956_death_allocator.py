"""W956 death 域分配器治本锁组(设计单一源 =
``.debug/temp/currency_war/w956_death_allocator/DESIGN.md``;数学 =
P23.4(i) 极限形式推论 E1 + A′ 编排者指令;方案 B 归属 = 转型臂实施批
对账移交,W954 REPORT §5)。

锁面 ↔ 设计组件映射(出处纪律:docstring 引 DESIGN 与 P23 证明篇):
- 必死子带谓词 → test_must_die_band_predicate:hp ≤ L_c(「再败一场
  必死」;标定记录 = 同目录 CALIBRATION.md,n=60 单窗两判据重合);
- w-only 拒供退役 → test_w_only_guard_removed:供给层守卫符号已删
  (守卫把 death 帧出清结构性锁死,见 W933 并联缺位裁决);
- 刷新估计器死亡域保底 → test_refresh_estimator_death_floor:结构零
  (板满)帧 DEATH 取 w、停手窗取 0.0,缺省参数 = 停手窗语义;
- 危机帧购买兜底集 → test_crisis_fallback_generation:开关缺省关 /
  应急带 + release 活跃门 / 互斥谓词(常规购买集非空不启用)/
  成本上限与 merge 优先排序。

帧构造纪律复用 test_cw_w812(真实谓词路径优先)。
"""
from __future__ import annotations


import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2 import allocator
from sr_od.application.currency_war.decision.decision_v2.allocator import (
    AllocDomain,
    _opportunity_cost,
    _refresh_dpeff_estimate,
    must_die_band,
)
from sr_od.application.currency_war.decision.decision_v2.filters import (
    _deploy_free,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
)


def _faction_names(faction: str, k: int) -> list[str]:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    return [n for n, c in CHARACTERS.items()
            if faction in (c.factions or ())][:k]


def _death_state(gold: int = 150, round_num: int = 9,
                 hp: int = 5, level: int = 8) -> GameState:
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, level, gold, hp
    st.round_num = round_num
    st.node_type = 'battle'
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    names = _faction_names('仙舟', 2)
    st.deployed = [
        BenchChar(slot=i + 1, char_id=n,
                  faction=(CHARACTERS[n].factions or ['?'])[0], star=1)
        for i, n in enumerate(names)]
    return st


def _sess() -> StrategySession:
    return StrategySession()


# ---------- 必死子带谓词锁(W956 §3.2 定档 hp≤L_c) ----------

def test_must_die_band_predicate() -> None:
    """hp ≤ L_c =「再败一场必死」:带内真/带外假/hp 缺读与已死不辖;
    P2 域 L_c = vd_p2_loss(位面越深判据越严)。标定 = 同目录
    CALIBRATION.md(P1 样本内与应急带重合,取 L_c 版为单一源复用)。"""
    reg = DEFAULT_REGISTRY
    ss = _sess()
    lc = allocator._l_c(_death_state(), reg)
    assert must_die_band(_death_state(hp=int(lc)), ss, reg) is True
    assert must_die_band(_death_state(hp=int(lc) + 5), ss, reg) is False
    st_none = _death_state()
    st_none.hp = None
    assert must_die_band(st_none, ss, reg) is False
    assert must_die_band(_death_state(hp=0), ss, reg) is False
    st_p2 = _death_state(hp=int(reg.vd_p2_loss))
    st_p2.plane = 2
    assert must_die_band(st_p2, ss, reg) is True


# ---------- w-only 拒供退役红检(W956 E1/A′;守卫移除) ----------

# ---------- 必死子带机会成本重定价锁(ADR-0510;编排者批准子带收窄) ----------

def test_must_die_band_opportunity_cost() -> None:
    """必死子带内 I 退役:DEATH 域 opp == c 面值(息档保护对象被死亡
    截断,I 无保护语义;论证链 P23.4(i)→W907→ADR-0503→0508→E1→本步,
    ADR-0510)。带外(hp>L_c)c+I 原样(W810 证据面覆盖域,ADR-0493 语义
    不变);停手窗域不受谓词辖。"""
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        interest_cost,
    )
    reg = DEFAULT_REGISTRY
    lc = allocator._l_c(_death_state(), reg)
    st_in = _death_state(gold=153, hp=int(lc))
    st_out = _death_state(gold=153, hp=int(lc) + 5)
    p = allocator.AllocProposal(kind='buy', dpeff=0.0, m_eff=1.0, cost=8)
    assert allocator.must_die_band(st_in, _sess(), reg)
    assert _opportunity_cost(st_in, _sess(), reg, p, AllocDomain.DEATH) \
        == pytest.approx(8.0), '必死子带内 I 退役:opp=c 面值(ADR-0510)'
    assert not allocator.must_die_band(st_out, _sess(), reg)
    got_out = _opportunity_cost(st_out, _sess(), reg, p, AllocDomain.DEATH)
    assert got_out == pytest.approx(
        8.0 + interest_cost(153, 8, st_out,
                            recovery_rounds=reg.interest_recovery_rounds)), \
        '子带外 c+I 原样(ADR-0493 面值语义,W810 域)'
    got_stop = _opportunity_cost(st_in, _sess(), reg, p,
                                 AllocDomain.STOP_WINDOW)
    assert got_stop == pytest.approx(
        8.0 + interest_cost(153, 8, st_in,
                            recovery_rounds=reg.interest_recovery_rounds)), \
        '停手窗域不受必死带谓词辖'


def test_must_die_band_refresh_clears() -> None:
    """必死子带出清锁(重定价的行为面):板满帧刷新提案(估计器保底
    dpeff=w)在 V = m_eff·w − c 下出清——供给解锁+成本退役合流后,
    death 帧分配器不再恒哑火。构造取可清形态(w=1、m_eff≥3):
    端局 m_eff=1 帧在 c 面值保留下可能仍负——c 权重是否跟进退役
    = ADR-0510 选项2 暂缓面,以出清率实测定,不在本锁断言。"""
    reg = DEFAULT_REGISTRY
    st = _death_state(gold=195, hp=1, round_num=1)
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    xz = _faction_names('仙舟', 8)
    st.deployed = [
        BenchChar(slot=i + 1, char_id=n,
                  faction=(CHARACTERS[n].factions or ['?'])[0], star=1)
        for i, n in enumerate((xz * 2)[:8])]
    ss = _sess()
    ss.plane_node_table = ['battle'] * 9   # 位面中段:真实剩余战场 ≥3
    ss.last_streak = 4                      # w = streak 表相邻档差 = 1
    w = allocator._w_per_battle(st, ss)
    assert w == pytest.approx(1.0)
    props = allocator._supply_impl(st, ss, reg, AllocDomain.DEATH)
    refresh = [p for p in props if p.kind == 'refresh']
    assert refresh, '保底后刷新提案被供给'
    for p in refresh:
        p.v = p.m_eff * p.dpeff - _opportunity_cost(st, ss, reg, p,
                                                    AllocDomain.DEATH)
        assert p.v > 0, \
            '必死子带内刷新提案必须出清(V=m_eff·w−c>0,ADR-0510 行为面)'


def test_w_only_guard_removed() -> None:
    """供给层 w-only 守卫符号必须不存在:守卫使 death 帧 dwin=0 提案
    结构性不供给(W933 并联缺位裁决的机制本体);退役后出清层由面值
    机会成本 c+I 与 m_eff 视界截断兜底(语义更替推导见
    test_cw_w812_death_valuation.test_death_w_only_supply_unblocked)。"""
    assert not hasattr(allocator, '_w_only_rejected'), \
        'w-only 拒供守卫已退役,不得回潜(符号级红检)'


# ---------- 刷新估计器死亡域保底锁(W956 A′ 件) ----------

def test_refresh_estimator_death_floor() -> None:
    """结构零(板满)帧:停手窗域估计 0.0(原语义,test_cw_w715
    手算锁口径);死亡域保底取 w(win_eq 对「刷新找可上阵件加当场
    战力」的增量量化盲区 → 零估值 = 刷新臂在死亡域恒负 V 的结构性
    哑火;保底后 V = m_eff·w − (c+I) 与买臂同式,面值账仍门控)。"""
    reg = DEFAULT_REGISTRY
    st = _death_state(gold=195)
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    xz = _faction_names('仙舟', 8)
    st.deployed = [
        BenchChar(slot=i + 1, char_id=n,
                  faction=(CHARACTERS[n].factions or ['?'])[0], star=1)
        for i, n in enumerate((xz * 2)[:8])]
    ss = _sess()
    w = allocator._w_per_battle(st, ss)
    assert w >= 0
    assert _refresh_dpeff_estimate(st, ss, reg) == 0.0, \
        '缺省参数 = 停手窗语义,结构零帧估 0(test_cw_w715 口径不变)'
    assert _refresh_dpeff_estimate(st, ss, reg,
                                   AllocDomain.STOP_WINDOW) == 0.0
    assert _refresh_dpeff_estimate(st, ss, reg,
                                   AllocDomain.DEATH) == pytest.approx(w)


# ---------- (危机帧购买兜底集锁已随 crisis_fallback 开关族删除——旧方案
# ---------- 清退批,清查报告 OLD_MIX_AUDIT §1.3;生成器同批删) ----------


# ---------- alloc 一致性断言锁(W956 P0①;W954 契约断言面) ----------

def _locked_session(locked_comp: str):
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    s = StrategySession()
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = locked_comp
    s.v3_intention = ist
    return s


def test_alloc_reason_consistency_predicate() -> None:
    """断言式:执行目标 ∈ 锁定体系集 → '';否则 off_lock 标签。
    语义复现锚 = 实机档案 match g_20260831_082322 p2r1(locked=希儿量子,
    evolve「→仙舟3」脱节;探针 = 同目录 w956/verify_match_archive.py)。
    边界:无意向载体 / 无锁定帧(weak/空窗,scope=None)不辖——跨线骨架
    与弱占位在语义集内。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        alloc_reason_consistency,
    )
    s = _locked_session('希儿量子')
    got = alloc_reason_consistency(s, '仙舟', '仙舟3')
    assert 'off_lock' in got, '锁定希儿量子帧的仙舟向演进必须报警(存档病灶)'
    assert alloc_reason_consistency(s, '量子同频', '希儿量子') == '', \
        '锁定集内目标不报警'
    assert alloc_reason_consistency(StrategySession(), '仙舟', '') == '', \
        '无意向载体不辖(无法判定)'
    weak = _locked_session('')
    weak.v3_intention.phase = 'weak'
    assert alloc_reason_consistency(weak, '仙舟', '') == '', \
        'weak 帧无锁定体系集,跨线骨架在语义集内'


def test_execute_replacement_wires_consistency_log() -> None:
    """断言接线锁(结构):execute_replacement 消费 alloc_reason_consistency
    ——reason 线名脱节的帧级观测面在发射点,不依赖事后检查网回放。"""
    import inspect

    from sr_od.application.currency_war.kernel import cw_evolution
    src = inspect.getsource(cw_evolution.execute_replacement)
    assert 'alloc_reason_consistency' in src, \
        'execute_replacement 必须消费一致性断言(发射点观测)'


# ---------- 线名来源收口锁(W956 P0②;W954 契约执行半边) ----------

def test_propose_upgrades_reads_intention_authority(monkeypatch) -> None:
    """propose_upgrades 的意向 tie-break 消费 ``cw_recipe.decision_target``
    (意向单一入口),不再直读 ``session.target_comp`` 缓存(数据来源收口,
    加权语义不变——behavior 未变,只换读端)。结构锁 + 行为锁双面:
    - 结构:源码含 decision_target 调用、不含 session.target_comp 直读;
    - 行为:bare session(定型路径,decision_target ≡ target_comp)下,
      与 target_comp 同名候选项获得 tie-break 加权(选最优时胜出)。"""
    import inspect

    from sr_od.application.currency_war.kernel import cw_evolution, cw_recipe
    src = inspect.getsource(cw_evolution.propose_upgrades)
    assert 'decision_target(session, state)' in src
    body = src.split('"""')[-1]   # 只查代码体,docstring 的历史叙述不算读端
    assert "session.target_comp" not in body, \
        'tie-break 不得直读缓存线名(收口后只走意向单一入口)'

    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    # 行为面用可枚举 comp(列车同行:阵营在 CHARACTERS 内,在手 ≥2 门槛可达;
    # 希儿量子主档「量子同频」非 CHARACTERS 阵营键,枚举走希儿特例,不合适)
    comp = next(c for c in COMP_LIBRARY if c.name == '列车同行')
    st = _death_state(hp=80)
    t_names = [n for n, c in CHARACTERS.items()
               if '列车同行' in (c.factions or ())][:2]
    st.bench = [BenchChar(slot=i + 1, char_id=n,
                          faction=(CHARACTERS[n].factions or ['?'])[0],
                          star=1)
                for i, n in enumerate(t_names)]
    ss = StrategySession()
    ss.target_comp = comp
    # 行为面:蒙特卡洛无随机源,直接比打分序——同名加权后 faction 分数更高
    opts = cw_evolution.propose_upgrades(st, ss)
    assert opts, '构造帧应至少产生一个演进机会'
    same = [o for o in opts if o.comp_name == comp.name]
    assert same, '锁定线 comp 的提案应被枚举'
    # 收口后行为不变:bare session 的 decision_target 返回 target_comp,
    # tie-break 仍作用于 target_comp.name(cw_recipe 零漂移依据同源)
    assert cw_recipe.decision_target(ss, st) is comp


# ---------- F5 部署供给锁(W956 §1.4;免开关=缺陷语义直落) ----------

def _board_short_state(bench_count: int) -> GameState:
    """末窗板缺帧:deployed 2 人(仙舟),cap 5 → 3 空位;bench 放
    bench_count 个非同已署名可上件。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    st = _death_state(hp=5, round_num=8)
    dep_names = {d.char_id for d in (st.deployed or [])}
    names = [n for n in CHARACTERS if n not in dep_names][:bench_count]
    st.bench = [BenchChar(slot=i + 1, char_id=n,
                          faction=(CHARACTERS[n].factions or ['?'])[0],
                          star=1)
                for i, n in enumerate(names)]
    return st


def test_deploy_supply_untruncated_when_board_short() -> None:
    """板缺帧部署候选不截断:bench 4 件可上(空位 3)→ 候选数 = 空位数
    (top-K=3 在此形态的截断即缺陷:第 4 件有位不上);同名禁双保持;
    板满帧走原 top-K 路径(对照:w715/w721 邻锁覆盖,零漂移)。"""
    from sr_od.application.currency_war.decision.decision_v2.candidates import (
        _deploy_candidates,
    )
    from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
    reg = DEFAULT_REGISTRY
    assert reg.deploy_top_k == 3
    st = _board_short_state(4)
    cands = _deploy_candidates(st, _sess(), reg)
    free = _deploy_free(st)
    assert len(cands) == min(4, free) > reg.deploy_top_k, \
        '板缺帧候选数 = min(围栏合法件, 空位数),不落 top-K 截断'
    seen_slots = [c.action.bench_idx for c in cands]
    assert len(seen_slots) == len(set(seen_slots)), '部署候选槽位不重复'
    dep_names = {d.char_id for d in (st.deployed or [])}
    for c in cands:
        assert st.bench[c.action.bench_idx].char_id not in dep_names, \
            '同名禁双在扩展供给路径仍然成立'


def test_late_board_short_idle_check() -> None:
    """F5 观测检查(check_late_board_short_idle,披露型——沿
    late_deploy_full 同款「先观测后定阈」生命周期):末窗板缺 ∧ bench
    有不同名可上件 ∧ 帧无 DeployMove → 计 idle 实例;采纳层(非正分门)
    修复后升格断言门。violations 字段恒 0(检查网契约)。"""
    from sr_od.application.currency_war.sim.checks.runtime import (
        check_late_board_short_idle,
    )
    dep = [{'char_id': '仙舟甲'}, {'char_id': '仙舟乙'}]
    bench = [{'char_id': '丙件', 'faction': '列车同行'}]

    def _row(**kw):
        row = {'round_num': 8,
               'state': {'deployed': dep, 'bench': bench, 'cap': 5},
               'actions': []}
        row.update(kw)
        return row

    idle = _row(actions=[{'__type__': 'StartBattle'}])
    active = _row(actions=[{'__type__': 'DeployMove'}])
    empty_bench = _row(state={'deployed': dep, 'bench': [], 'cap': 5})
    early = _row(round_num=3)
    got = check_late_board_short_idle([[idle], [active],
                                       [_row()], [empty_bench], [early]])
    assert got['violations'] == 0, '披露型 violations 恒 0(检查网契约)'
    assert got['idle_instances'] == 2, \
        '两局零部署计 idle(active/空 bench 豁免)'
    got2 = check_late_board_short_idle([[early]])
    assert got2['idle_instances'] == 0, '观测辖域 = 末窗带(r≥7)'

# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
