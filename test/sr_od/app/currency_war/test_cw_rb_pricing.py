"""W947 · R-B 三信号商店件定价单帧锁组(判前锁 §5-4)。

设计出处:.debug/temp/currency_war/w920_rb_design/DESIGN.md(§2-D1
判据面=商店件定价全件 / §3-D3 三信号命题 / §3 落点表)+ 判前锁
docs/develop/currency_war/prereg/w947_rb_signal_pricing_prereg.md(锁
清单 §5)。命题:P20(激活)/ stage_transitions Q1(贯穿留存)/
P1+P16(费级再遇窗口)。决策 why 挂账 ADR(批C 补)。

锁语义不锁牌面:DOT 成员/线外贯穿件名从注册表现场派生;断言策略
决策行为(rb_offpiece_term 加项与 bd 披露键),不锁具体卡名。
伞开关 rb_signal_pricing_enabled 默认关 = 第 1 态零漂移锚,每锁带
off 臂对照断言(开关生命周期第 3 态盘点义务)。
"""
from __future__ import annotations

import dataclasses
import inspect

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2 import scoring
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.rb_pricing import (
    rb_offpiece_term,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    TRANSITION_TRAITS,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)

_TIER_OF = dict(TRANSITION_TRAITS)
_DOT_KEY = '持续伤害'


def _reg_on(**kw) -> object:
    base = {'rb_signal_pricing_enabled': True}
    base.update(kw)
    return dataclasses.replace(DEFAULT_REGISTRY, **base)


_REG_ON = _reg_on()
_REG_OFF = DEFAULT_REGISTRY


def _dot_members() -> list[str]:
    """DOT 体系成员名(注册表派生,非牌面锁定)。"""
    return sorted(
        n for n, c in CHARACTERS.items()
        if _DOT_KEY in (set(c.factions or ()) | set(c.flows or ())))


def _q1_nonmember() -> str:
    """贯穿字段 ≥阈值 且 不属任何过渡体系的卡名(Q1 数据派生)。"""
    for n, ret in _REG_ON.rb_retention_q1.items():
        ch = CHARACTERS.get(n)
        if ch is not None and ret >= _REG_ON.rb_s2_threshold \
                and not ((set(ch.factions or ()) | set(ch.flows or ()))
                         & set(_TIER_OF)):
            return n
    raise AssertionError('Q1 表内无满足条件的非体系贯穿卡')


def _zero_signal_scatter() -> str:
    """零信号线外散件名(无贯穿字段/无过渡体系/1 费;注册表派生)。"""
    for n, c in CHARACTERS.items():
        if (c.cost == 1
                and n not in _REG_ON.rb_retention_q1
                and not ((set(c.factions or ()) | set(c.flows or ()))
                         & set(_TIER_OF))):
            return n
    raise AssertionError('注册表内无满足条件的零信号散件')


def _locked_sess() -> StrategySession:
    """P1 配方锁定帧 session(体系对=列车同行+仙舟 → DOT 为线外体系)。"""
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked',
                                    p1_pair=('列车同行', '仙舟'))
    return s


def _st(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'node_type': '战斗', 'gold': 60,
            'hp': 80, 'hp_readable': True, 'level': 6, 'streak': None,
            'board': {}, 'bench': [], 'shop': [], 'deployed': []}
    base.update(kw)
    return GameState(**base)


def _buy(name: str, cost: int, tag: str = 'line_opportunistic') -> Candidate:
    return Candidate(action=BuyCard(ShopCard(x=0, name=name, cost=cost)),
                     tag=tag, source='test', needs_slot=False)


def _cand_frame(name: str) -> tuple[Candidate, GameState, GameState]:
    """锁定帧单卡场景:deployed 1 名 DOT 成员(闭包计数=档下界−1),
    候选=再买一名 DOT;after_state = 买入落 bench 后的闭包。"""
    dots = _dot_members()
    holder = next(n for n in dots if n != name)
    st = _st(deployed=[BenchChar(slot=0, char_id=holder)],
             shop=[ShopCard(x=0, name=name, cost=CHARACTERS[name].cost)])
    cand = _buy(name, CHARACTERS[name].cost)
    after = _st(deployed=st.deployed,
                bench=[BenchChar(slot=0, char_id=name)],
                shop=[ShopCard(x=0, name=name, cost=CHARACTERS[name].cost)])
    return cand, st, after


# ===== 锁 0(伞开关缺省态 = off 臂零漂移锚)=====

def test_lock0_switch_default_off_and_off_arm_zero() -> None:
    """伞开关默认关(生命周期第 1 态);默认 registry 下信号恒 0 且
    无披露键(off 臂行为逐位不变——评分消费点在伞关时零副作用)。"""
    assert DEFAULT_REGISTRY.rb_signal_pricing_enabled is False
    name = _q1_nonmember()
    cand, st, after = _cand_frame(name)
    sess = _locked_sess()
    val, keys = rb_offpiece_term(cand, st, after, sess, _REG_OFF)
    assert val == 0.0 and keys == {}
    assert getattr(sess, 'rb_seen_counts', None) is None   # 零副作用


# ===== 锁 1(S1 凑档激活,P20 辖域)=====

def test_lock1_s1_out_of_line_tier_crossing() -> None:
    """锁定帧下,候选使线外体系(DOT,档 2)闭包计数从 下界−1=1 跨到
    2 → S1=rb_s1_unit 开火并披露 bd['rb_s1'];未跨档(计数 0)不开火
    (F1 教训:激活项只在本帧真凑档时开火,DESIGN §3-D3 S1)。"""
    dots = _dot_members()
    cand_name = next(n for n in dots if CHARACTERS[n].cost == 2)
    cand, st, after = _cand_frame(cand_name)
    sess = _locked_sess()
    # 单 holder(计数 1)→ 买后跨档:S1 开火
    val, keys = rb_offpiece_term(cand, st, after, sess, _REG_ON)
    assert keys.get('rb_s1') == pytest.approx(
        round(_REG_ON.rb_s1_unit, 4), abs=1e-6)
    assert val > 0
    # 零 holder(计数 0)→ 买后计数 1,不到下界 2:不开火(卡芙卡@r4
    # 「即凑 DOT2」被证伪的结构化,DESIGN §2-D3 S1 病灶证据)
    st0 = _st(shop=[ShopCard(x=0, name=cand_name,
                             cost=CHARACTERS[cand_name].cost)])
    val0, keys0 = rb_offpiece_term(cand, st0, st0, sess, _REG_ON)
    assert 'rb_s1' not in keys0 and val0 < _REG_ON.rb_s1_unit


# ===== 锁 2(S2 贯穿留存,Q1 字段化)=====

def test_lock2_s2_retention_field_and_threshold() -> None:
    """线外贯穿件(Q1 留存 ≥阈值)获正价 = unit×留存率并披露
    (F3 千冶·刃/F2 姬子·启行病灶语义:贯穿性不随 target 变);
    表外卡(无字段)S2=0 不猜;阈值按值比较非卡名名单(DESIGN §5-3)。"""
    name = _q1_nonmember()
    cand, st, after = _cand_frame(name)
    sess = _locked_sess()
    val, keys = rb_offpiece_term(cand, st, after, sess, _REG_ON)
    ret = _REG_ON.rb_retention_q1[name]
    assert keys.get('rb_s2') == pytest.approx(_REG_ON.rb_s2_unit * ret,
                                              abs=1e-6)
    # 阈值提到留存之上 → 同卡 S2 消失(阈值行为,非名单行为)
    reg_hi = _reg_on(rb_s2_threshold=1.01)
    _, keys_hi = rb_offpiece_term(cand, st, after, sess, reg_hi)
    assert 'rb_s2' not in keys_hi


# ===== 锁 3(S3 费级窗口期权 + 轮级计次衰减)=====

def test_lock3_s3_window_and_seen_decay() -> None:
    """期权价 = unit×(费级窗口/120)×1/见次:1 费趋零(窗口 11/120)、
    同卡第二轮见次衰减折半;窗口单一源=registry.remeet_window_rounds。
    (P1/P16;DESIGN §3-D3 S3「窗口长价高,窗口短价趋零」。)"""
    dots = _dot_members()
    cand_name = next(n for n in dots if CHARACTERS[n].cost == 2)
    cand, st, after = _cand_frame(cand_name)
    sess = _locked_sess()
    unit = _REG_ON.rb_s3_unit
    w2 = _REG_ON.remeet_window_rounds[2]
    _, keys_r5 = rb_offpiece_term(cand, st, after, sess, _REG_ON)
    assert keys_r5.get('rb_s3') == pytest.approx(
        round(unit * w2 / 120, 4), abs=1e-6)
    # 第二轮再遇:见次=2 → 折半
    st_r6 = _st(round_num=6,
                deployed=st.deployed,
                shop=[ShopCard(x=0, name=cand_name,
                               cost=CHARACTERS[cand_name].cost)])
    _, keys_r6 = rb_offpiece_term(cand, st_r6, st_r6, sess, _REG_ON)
    assert keys_r6.get('rb_s3') == pytest.approx(
        round(unit * w2 / 120 / 2, 4), abs=1e-6)
    # 1 费档趋零(同帧内构造:零信号散件 cost=1 的 S3 分量 < 高费档)
    cheap = _zero_signal_scatter()
    cand_c = _buy(cheap, 1)
    st_c = _st(shop=[ShopCard(x=0, name=cheap, cost=1)])
    w1 = _REG_ON.remeet_window_rounds[1]
    _, keys_c = rb_offpiece_term(cand_c, st_c, st_c, sess, _REG_ON)
    assert keys_c.get('rb_s3') == pytest.approx(
        round(unit * w1 / 120, 4), abs=1e-6)
    assert keys_c['rb_s3'] < keys_r5['rb_s3']


# ===== 锁 3b(S3 子旗标:拆臂隔离,W947 批C 判前锁 §1)=====

def test_lock3b_s3_subflag_off_isolates_s3() -> None:
    """rb_s3_enabled=False(伞开)时 S3 恒 0 且无披露键、不计见次(零
    副作用),S1/S2 不受影响——拆臂「S3 关/S1+S2 开」的隔离机制;默认
    True = v1 合臂语义不变。判前锁 = docs/develop/currency_war/prereg/
    w947c_rb_split_prereg.md。"""
    name = _q1_nonmember()
    cand, st, after = _cand_frame(name)
    sess = _locked_sess()
    reg = _reg_on(rb_s3_enabled=False)
    val, keys = rb_offpiece_term(cand, st, after, sess, reg)
    assert 'rb_s3' not in keys
    assert keys.get('rb_s2') is not None        # S1/S2 不受影响
    assert getattr(sess, 'rb_seen_counts', None) is None   # 零副作用
    assert DEFAULT_REGISTRY.rb_s3_enabled is True


# ===== 锁 4(锁线态零信号件归零 + 辖域门)=====

def test_lock4_zero_signal_and_scope_gates() -> None:
    """锁定帧零信号线外件(无贯穿字段/无跨档/1 费)三信号全 0、无披露
    键——定价归零语义(加项后不获得无据正分,DESIGN §2-D5);未锁线帧
    信号=0(不存在「线外」概念);非 P1 / 非买候选不辖。"""
    cheap = _zero_signal_scatter()
    cand = _buy(cheap, 1)
    st = _st(shop=[ShopCard(x=0, name=cheap, cost=1)])
    sess = _locked_sess()
    val, keys = rb_offpiece_term(cand, st, st, sess, _REG_ON)
    # 零信号=S1/S2 不开火;S3 仅剩 1 费趋零分量(<0.1 分,不构成无据
    # 正分通道——13-4 病灶语义:定价不产生可解释性外的底分)
    assert 'rb_s1' not in keys and 'rb_s2' not in keys and val < 0.1
    # 未锁线帧
    sess_open = StrategySession()
    sess_open.v3_intention = IntentionState(phase='unlocked')
    name = _q1_nonmember()
    cand2, st2, _ = _cand_frame(name)
    val2, keys2 = rb_offpiece_term(cand2, st2, st2, sess_open, _REG_ON)
    assert val2 == 0.0 and keys2 == {}


# ===== 锁 5(scoring 消费点接线 + 披露键)=====

def test_lock5_scoring_wiring_and_bd_disclosure() -> None:
    """score_candidate 消费点:伞关时 bd 无 rb_* 键(零漂移);伞开时
    bd 披露 rb_s1/s2/s3 中命中的键、分值含加项(off_lock 降级之前——
    线外标签候选的正项随既有 κ 通道折扣,DESIGN §3-D2)。"""
    name = _q1_nonmember()
    cand, st, _ = _cand_frame(name)
    sess = _locked_sess()
    _v_off, bd_off = scoring.score_candidate(cand, st, sess, _REG_OFF)
    assert not any(k.startswith('rb_') for k in bd_off)
    _v_on, bd_on = scoring.score_candidate(cand, st, sess, _REG_ON)
    assert 'rb_s2' in bd_on   # 贯穿件至少披露 S2


# ===== 锁 6(piece_value 守卫移除红检)=====

def test_lock6_piece_value_removal_redcheck() -> None:
    """守卫移除红检:件价值整机制(ADR-0497 删码)不得以任何形态回归
    ——模块 import 必失败、registry 八字段不得重现、scoring 消费块
    不得复活(R-B 新定价必须走 rb_* 命名空间,DESIGN §5-5)。"""
    with pytest.raises(ImportError):
        import sr_od.application.currency_war.decision.decision_v2.piece_value  # noqa: E501,F401
    field_names = {f.name for f in dataclasses.fields(DEFAULT_REGISTRY)}
    assert not {n for n in field_names if n.startswith('piece_value')}
    src = inspect.getsource(scoring)
    assert 'evaluate_piece' not in src
    sym_names = set(field_names) | set(dir(scoring))
    assert not any(n.startswith('piece_value') for n in sym_names)
