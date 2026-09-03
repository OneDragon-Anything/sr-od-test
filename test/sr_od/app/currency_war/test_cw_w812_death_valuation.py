"""死亡域估值路径三缺陷修复锁组(W810 死亡域审查定谳三缺陷;修复
落码 = ADR-0493,模型主体 = decision_v2/allocator.py)。

锁面 ↔ 缺陷映射(每缺陷一锁;出处纪律:docstring 引 ADR-0493 与
W810 审查反事实证据):
- 缺陷①视界截断失效 → test_death_horizon_truncation_truth:
  plane_node_table 缺失时死亡域截断上限取保守下界(当轮本场 1.0),
  不再退骨架缺省 battles_left_est=5(m_eff 曾虚高 2-5 倍);
- 缺陷②档顶饱和零区分度 → test_death_w_only_supply_unblocked:
  原锁「死亡域不供给纯 w 提案」的守卫语义已随 W956 治本退役
  (守卫锁死 death 帧出清,W933 并联缺位/W951/W955 实证);新锁
  断言供给解锁 + 大额 w-only 在出清层仍被面值账拒(金免费伪影
  由 V 兜底,守卫移除不劣化);
- 缺陷③金免费谬误 → test_death_opportunity_cost_face_value:
  死亡域机会成本按面值 c+I 计(S0 折价的「金必死」前提被实测证伪:
  携金进 P2 三局 3/3 到达可支出语境、1 局转 +2 轮存活),参数集
  版本随重标定升 P23.4R 并登记来源。

锁推导不锁分布;帧构造纪律复用 test_cw_w715(真实谓词路径优先)。
"""
from __future__ import annotations

import logging

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2 import allocator
from sr_od.application.currency_war.decision.decision_v2.allocator import (
    ALLOC_PARAM_SET,
    ALLOCATOR_ENABLED,
    AllocDomain,
    _opportunity_cost,
    _supply_impl,
)
from sr_od.application.currency_war.decision.decision_v2.ev import interest_cost
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)



# ---------- 帧构造(复用 test_cw_w715 纪律) ----------

def _faction_names(faction: str, k: int) -> list[str]:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    return [n for n, c in CHARACTERS.items()
            if faction in (c.factions or ())][:k]


def _pad_names() -> list[str]:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    xz = set(_faction_names('仙舟', 8))
    return [n for n in CHARACTERS if n not in xz]


def _deploy(state: GameState, names: list[str]) -> GameState:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    state.deployed = [
        BenchChar(slot=i + 1, char_id=n,
                  faction=(CHARACTERS[n].factions or ['?'])[0], star=1)
        for i, n in enumerate(names)]
    return state


def _death_state(gold: int = 150, round_num: int = 9,
                 hp: int = 5, level: int = 8) -> GameState:
    """死亡域帧(W810 三局死亡域出手帧形态:hp=5/高金/位面末轮)。"""
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, level, gold, hp
    st.round_num = round_num
    st.node_type = 'battle'
    _deploy(st, _faction_names('仙舟', 2))
    return st


def _sess(table: list[str] | None = None) -> StrategySession:
    """session;table=None = 表缺失(W810 实测:回退骨架缺省的形态)。"""
    s = StrategySession()
    if table is not None:
        s.plane_node_table = table
    return s


DEATH_TABLE_R9 = ['battle'] * 8 + ['boss']


# ---------- 缺陷①锁:视界真值(ADR-0493;W810 缺陷①) ----------

def test_death_horizon_truncation_truth() -> None:
    """死亡域截断上限 = 真实剩余战场,表缺失退保守下界 1.0:
    - 表缺失(W810 三局实测形态:位面末轮 r9)→ 1.0,不再退骨架
      battles_left_est=5(修复前 m_eff=5.0,真实 1-3 场,V 虚高);
    - 表在 → 真实槽序推导(r9 表末位 boss → 1.0);
    - 非死亡域路径(ev.battles_left_plane 骨架回退)不被本守卫波及
      (守卫只在死亡域截断点 `_deploy_free_battles`)。"""
    reg = DEFAULT_REGISTRY
    # 表缺失(=W810 帧形态)
    assert allocator._deploy_free_battles(
        _death_state(), _sess(None), reg) == 1.0
    # 表在:位面末轮真实剩余 = 1
    assert allocator._deploy_free_battles(
        _death_state(), _sess(DEATH_TABLE_R9), reg) == 1.0
    # 表在但位面已过表长(表耗尽,同样只剩骨架回退)→ 保守下界
    tbl = ['battle'] * 3 + ['boss']
    st_mid = _death_state(round_num=7)
    assert allocator._deploy_free_battles(st_mid, _sess(tbl), reg) == 1.0
    # 表在:位面中段真实剩余 = 3(推导面不被守卫改写)
    st_mid2 = _death_state(round_num=2)
    assert allocator._deploy_free_battles(st_mid2, _sess(tbl), reg) == 3.0
    # 骨架回退本体(battles_left_plane)不动:停手窗域仍消费原语义
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        battles_left_plane,
    )
    assert battles_left_plane(_death_state(), _sess(None), reg) \
        == reg.battles_left_est


# ---------- 缺陷②锁:饱和面区分度(语义已随 W956 治本更替) ----------

def test_death_w_only_supply_unblocked(monkeypatch) -> None:
    """win_eq 饱和面(dwin≡0)死亡域 w-only 非刷新提案的供给与出清
    (W956 治本设计 .debug/temp/currency_war/w956_death_allocator/
    DESIGN.md;旧锁「死亡域不供给纯 w 提案」= ADR-0493 缺陷②守卫,
    其语义已被 W956 更替:守卫把 death 帧出清结构性锁死——W933 §3
    「并联缺位」裁决与 W951/W955 sim chosen=[] 恒空实证,守卫移除:
    - 必死子带:E1 = P23.4(i) 极限推论(金终端价值≈0 时任何非负
      板面提案弱优于攥金,拒供不可能是最优);
    - 非应急子带:编排者指令直落(A′),「金免费伪影」顾虑(W810
      缺陷②原动机)由面值机会成本 c+I 与 m_eff 视界截断在出清层
      兜底——大额 w-only 提案 V<0 照拒,只有小额可过。
    断言:DEATH 域供给 levelup(dwin=0 不再拒供);大额成本在出清层
    仍 V<0(allocate 不采纳);STOP_WINDOW 对照供给不变。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as ev_mod
    reg = DEFAULT_REGISTRY
    # hp=80:P21 血预算硬停与本题正交,控制臂需其放行位
    st = _death_state(round_num=9, hp=80)
    xz = _faction_names('仙舟', 8)
    _deploy(st, (xz + _pad_names())[:8])   # 板满
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    st.bench = [BenchChar(slot=1, char_id=xz[0], faction='仙舟', star=1)]
    monkeypatch.setattr(ev_mod, 'levelup_ev_basis',
                        lambda *a, **k: 'pop_slot')   # 白名单放行
    monkeypatch.setattr(allocator, '_win_eq',
                        lambda state, registry: 0.778)   # 饱和面建模
    props_d = _supply_impl(st, _sess(DEATH_TABLE_R9), reg,
                           AllocDomain.DEATH)
    lu = [p for p in props_d if p.kind == 'levelup']
    assert lu, '死亡域饱和面 dwin=0 提案必须被供给(W956 E1/A′ 守卫退役)'
    # 出清层兜底:大额 w-only(dpeff 纯 w=0 构造)m_eff×w − (c+I) < 0
    for p in lu:
        p.v = p.m_eff * p.dpeff - _opportunity_cost(
            st, _sess(DEATH_TABLE_R9), reg, p, AllocDomain.DEATH)
        assert p.v <= 0, ('大额 w-only 死亡域提案出清层仍拒(W810 金免费'
                          '伪影由面值账兜底,非供给层)')
    props_s = _supply_impl(st, _sess(), reg, AllocDomain.STOP_WINDOW)
    assert any(p.kind == 'levelup' for p in props_s), \
        '停手窗对照臂供给行为不变(门移除只涉死亡域)'


# ---------- 缺陷③锁:机会成本面值校准(ADR-0493;W810 缺陷③) ----------

def test_death_opportunity_cost_face_value() -> None:
    """死亡域·**子带外**机会成本 = 面值 c+I(与停手窗同式):手算重算
    interest_cost 单一源;S0 折价退役(「金必死」前提被 W810 反事实
    实测算证伪——携金进 P2 三局 3/3 到达可支出语境、1 局转 +2 轮存活)。
    帧 = hp 80(必死子带 hp≤L_c 之外;子带内 I 退役归 ADR-0510,见
    test_cw_w956_death_allocator.test_must_die_band_opportunity_cost,
    W810 三局 hp 形态均在子带外,本锁语义与该收窄不冲突)。参数集版本
    随重标定升 P23.5R 且 recheck 登记来源(复判条款契约)。"""
    reg = DEFAULT_REGISTRY
    st = _death_state(gold=153, hp=80)
    assert not allocator.must_die_band(st, _sess(), reg), \
        '本锁锚子带外帧(面值 c+I 语义域)'
    p = allocator.AllocProposal(kind='buy', dpeff=0.0, m_eff=1.0, cost=8)
    got = _opportunity_cost(st, _sess(DEATH_TABLE_R9), reg, p,
                            AllocDomain.DEATH)
    expect = 8.0 + interest_cost(153, 8, st,
                                 recovery_rounds=reg.interest_recovery_rounds)
    assert got == pytest.approx(expect)
    assert got > 0.5, '死亡域机会成本不得退化到 ≈0(金免费谬误回归线)'
    # 同式复核:死亡域与停手窗同账(面值)
    got_stop = _opportunity_cost(st, _sess(), reg, p,
                                 AllocDomain.STOP_WINDOW)
    assert got == pytest.approx(got_stop)
    # 参数集重标定登记(版本变更必须伴随来源登记,W690 §4-4 契约;
    # W956 治本随版本升 P23.5R:估计器保底 + w-only 拒供退役)
    assert ALLOC_PARAM_SET.version == 'P23.5R'
    assert 'W810' in ALLOC_PARAM_SET.recheck
    assert 'W956' in ALLOC_PARAM_SET.recheck
    assert ALLOCATOR_ENABLED is True   # 开臂态不因重标定回退

# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
