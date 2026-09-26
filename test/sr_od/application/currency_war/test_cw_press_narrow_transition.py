"""锁线转型域收窄单帧锁(P88;ADR-0627)。

出处(单一源):
- 命题正本 = docs/develop/sr_od/application/currency_war/proofs/p88.md(§0 辖域/§1 调和
  引理/§3 解封方向式;收窄集 S_spec = {dominance_buy, hub_option_buy},
  豁免 ⇔ reason ∈ LAUNCH_CAUSE_BY_ARM ∖ S_spec 闭集单一源);
- 落码 = shop.py 两 S_spec 发射位辖域前置(分键 press_narrowed_
  transition_domain / press_narrowed_transition_domain_hub)+
  mandate.swap_transition_narrow_frame(域谓词单一源 = kernel
  ``_swap_transition_domain_of``)+ prep CwActionOpenShopParam 位对称观测
  (press_narrowed_transition_domain_prep_seen,仅登记零行为);
- mandate.dominance_buy_eligible docstring 辖域注(双引注:ADR-0616
  命题 4 + P88 调和引理)= 回滚合法依据封堵面。

锁清单(设计 v2 §六 批B 锁面存续面):
- F1′ 分键口径锁(候选 none 帧):同 D 帧但店无 dominance 候选 ⇒ 无
      将发射笔,收窄分键零显影(禁把辖域机会帧计入开火数,防
      §4.1-⑦① 覆盖比畸变)。
- F9′ hub 哨兵常态面控制:未锁无目标帧(乙臂自然辖域)收窄旗恒 False
      ⇒ hub 照常发射、哨兵键零显影。
(F1 开火/F2/F3 豁免/F5 零漂移/F6 M6 零触碰/F7 单一源/F8 prep 对称/
F9 wiring 旗位各锁已退役;F4 闭集对账正本与 S_spec 辖域腿迁并
test_cw_sell_window_launch::test_launch_cause_closed_set(15 臂映射段)。)

构造声明:候选名注册表实名(线外/核心/枢纽,程序化选取与既有锁文件
同款);D 帧构造 = 锁线(ist.locked_comp)∧ fp<1.00(board 空 dict)
∧ 板满(deployed 占满 max_units)∧ armed=常量 True。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bridge,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)
from test.sr_od.application.currency_war.test_cw_leak_ladder import (
    _bc as _lad_bc,
)
from test.sr_od.application.currency_war.test_cw_leak_ladder import (
    _card as _lad_card,
)
from test.sr_od.application.currency_war.test_cw_leak_ladder import (
    _km as _lad_km,
)
from test.sr_od.application.currency_war.test_cw_leak_ladder import (
    _off_name as _lad_off_name,
)
from test.sr_od.application.currency_war.test_cw_leak_ladder import (
    _session_stub as _lad_session,
)
from test.sr_od.application.currency_war.test_cw_leak_ladder import (
    _st as _lad_st,
)
from test.sr_od.application.currency_war.test_cw_no_target_three_arms import (
    IntentionState,
)
from test.sr_od.application.currency_war.test_cw_no_target_three_arms import (
    _card as _hub_card,
)
from test.sr_od.application.currency_war.test_cw_no_target_three_arms import (
    _ct as _hub_ct,
)
from test.sr_od.application.currency_war.test_cw_no_target_three_arms import (
    _decide as _hub_decide,
)
from test.sr_od.application.currency_war.test_cw_no_target_three_arms import (
    _session as _hub_session,
)
from test.sr_od.application.currency_war.test_cw_no_target_three_arms import (
    _state as _hub_state,
)

from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_NARROW_KEY = 'press_narrowed_transition_domain'
_NARROW_HUB_KEY = 'press_narrowed_transition_domain_hub'


def _d_frame_deps(n_km: int = 0) -> tuple[list[Unit], frozenset[str]]:
    """板满构造(level 5 ⇒ max_units=5,bench 空):锁线采购集前 n_km 名
    2★ 上板(其余线内名留作缺员),余位线外 2★ 垫件补满。
    返回 (板上件, 板上名集)——候选/缺员选取须 exclude 板上名集。"""
    km = _lad_km()
    names = list(km[:n_km])
    while len(names) < 5:
        names.append(_lad_off_name(exclude=tuple(names)))
    deps = [_lad_bc(m, star=2) for i, m in enumerate(names)]
    return deps, frozenset(names)


def _d_frame_st(gold: int, cards: list[ShopCard]) -> dict:
    """D 帧默认形(n_km=0 纯垫件板):锁线 ∧ fp<1.00(board 空)∧ 板满。"""
    deps, _names = _d_frame_deps(0)
    return _lad_st(gold, cards, locked=True, deployed=deps)


def _decide(st: dict, sess) -> object:
    return shop.decide_shop_action(cw4_gs(sess, **st), sess, SimpleNamespace(ev_arm='full'))


# ===== F1:dominance 位收窄开火锁 =====


class TestDominanceNarrowFire:

    def test_f1b_candidate_none_frame_key_silent(self):
        """分键口径 = 将发射笔:同 D 帧但店无 dominance 候选(仅 2★
        线外卡,refund 门先拒)⇒ 无将发射笔,收窄分键零显影(禁把辖域
        机会帧计入开火数,防 §4.1-⑦① 覆盖比畸变)。"""
        _deps, dep_names = _d_frame_deps(0)
        cand = _lad_off_name(exclude=tuple(dep_names))
        st = _d_frame_st(60, [_lad_card(cand, cost=2, star=2)])
        sess = _lad_session(locked=True)
        assert mandate.swap_transition_narrow_frame(_bridge(**st), sess) is True
        _decide(st, sess)
        assert _NARROW_KEY not in state_of(sess).cw4_counters, \
            '无可发射笔帧分键照计 = 口径漂移(帧内无将发射笔)'


# ===== F9′:hub 哨兵锁(常态面控制)=====


class TestHubSentinel:
    def test_f9_hub_natural_frame_untouched(self):
        """锁 F9 控制(空开火面申报的常态面):未锁无目标帧(乙臂自然
        辖域)收窄旗恒 False ⇒ hub 照常发射、哨兵键零显影。"""
        st = _hub_state(shop_cards=[_hub_card('花火', cost=2)])
        sess = _hub_session(IntentionState())
        assert mandate.swap_transition_narrow_frame(_bridge(**st), sess) is False
        act = _hub_decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam) and act.reason == 'hub_option_buy'
        ct = _hub_ct(sess)
        assert ct.get('hub_option_buy_hit') == 1
        assert _NARROW_HUB_KEY not in ct
