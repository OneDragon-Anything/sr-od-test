"""死亡域估值路径三缺陷修复锁组(W810 死亡域审查定谳三缺陷;修复
落码 = ADR-0493,模型主体 = decision_v2/allocator.py)。

锁面 ↔ 缺陷映射(每缺陷一锁;出处纪律:docstring 引 ADR-0493 与
W810 审查反事实证据):
- 缺陷①视界截断失效 → test_death_horizon_truncation_truth:
  plane_node_table 缺失时死亡域截断上限取保守下界(当轮本场 1.0),
  不再退骨架缺省 battles_left_est=5(m_eff 曾虚高 2-5 倍);
- 缺陷②档顶饱和零区分度 → test_death_w_only_proposal_rejected:
  win_eq 饱和面(dwin≡0)上死亡域不供给纯 w 支撑的非刷新提案
  (W810 反事实:该形态三局 0 正 EV、1 局负 EV);
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

logging.disable(logging.CRITICAL)


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


# ---------- 缺陷②锁:饱和面区分度(ADR-0493;W810 缺陷②) ----------

def test_death_w_only_proposal_rejected(monkeypatch) -> None:
    """win_eq 饱和面(dwin≡0)死亡域不供给纯 w 非刷新提案:
    饱和面用常量 win_eq 建模(钳制表顶,任意动作前后恒 0.778——
    W810 三局死亡域帧的实测形态 engines_formed=3/frac=0)。断言:
    - DEATH 域:白名单放行(pop_slot)+板满等待件齐备,levelup 仍
      不被供给(dpeff 纯 w,W810 反事实 0 正 EV);
    - STOP_WINDOW 对照:同帧同白名单 levelup 照常供给(门只辖死亡域
      ——停手窗有真实机会成本 c+I 门控,W810 证据面仅覆盖死亡域)。"""
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
    assert not [p for p in props_d if p.kind != 'refresh'], \
        '死亡域饱和面不得供给纯 w 非刷新提案(ADR-0493 缺陷②)'
    props_s = _supply_impl(st, _sess(), reg, AllocDomain.STOP_WINDOW)
    assert any(p.kind == 'levelup' for p in props_s), \
        '停手窗对照臂不受死亡域区分度门辖(门只辖死亡域)'


# ---------- 缺陷③锁:机会成本面值校准(ADR-0493;W810 缺陷③) ----------

def test_death_opportunity_cost_face_value() -> None:
    """死亡域机会成本 = 面值 c+I(与停手窗同式):手算重算对拍
    interest_cost 单一源;S0 折价退役(「金必死」前提被 W810 反事实
    实测算证伪——修复前 opp=S0×(c+I)≈0.01 金,金被当作免费)。参数集
    版本随重标定升 P23.4R 且 recheck 登记反事实来源(复判条款契约)。"""
    reg = DEFAULT_REGISTRY
    st = _death_state(gold=153)
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
    # 参数集重标定登记(版本变更必须伴随来源登记,W690 §4-4 契约)
    assert ALLOC_PARAM_SET.version == 'P23.4R'
    assert 'W810' in ALLOC_PARAM_SET.recheck
    assert ALLOCATOR_ENABLED is True   # 开臂态不因重标定回退
