"""遭遇分支选卡 E3 判据锁(mandate_v1/encounter.py;判据语义单一源 = ADR-0536)。

锁面(语义锁,守卫移除验证属性;数值只锁注册表查表值):
1. E3 同构决策树锁——两分支按实例对评估 + λ label 四态接死(不可判 ⇒
   整体 fail 向选低难,「负项置零续比」禁止)+ flip 不可判带 fail 向 +
   刷新肢条件化(非免费期权:原对弃用强制新选、可为负);
2. 清算下界锁——3×sell_refund(1★,4费)=12 > 金币观察值(经
   ENCOUNTER_G_GOLD 槽注入;cw_state.sell_refund 注册表直调,唯一数值断言);
3. P51 生存折现锁——金充裕帧敞口放大覆盖奖励增量(λ 负项经
   differential_composite 入 EV,锁只作方向,不锁数值分布);
4. 双槽互锁锁——只注 dstat 映射(半标定)时金币支未立 ⇒ 恒 fail 向,
   「12>8 ⇒ 高难更优」结论不会在 G_gold 定带前产出(ADR-0536 §3)。
"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

import pytest

from sr_od.application.currency_war.kernel.cw_events import EncounterOption
from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import encounter
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    provisional,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    lambda_death,
)

_LOW = EncounterOption(idx=0, difficulty=1, rewards=['金币×2'])
_HIGH = EncounterOption(idx=1, difficulty=3, rewards=['随机4费角色×3'])


def _cell(label: str = '可消费', lo: float | None = 0.30,
          hi: float | None = 0.31) -> lambda_death.LambdaCell:
    return lambda_death.LambdaCell(n=5, mono=0.3, ci_lo=lo, ci_hi=hi,
                                   label=label)


def _table(d0: lambda_death.LambdaCell,
           d1: lambda_death.LambdaCell) -> dict[str, lambda_death.LambdaCell]:
    """双难度带 × hp>40 × P1 的 encounter 最小表(其余键按域外处理)。"""
    return {
        'D0|hp>40|P1|encounter': d0,
        'D1|hp>40|P1|encounter': d1,
    }


def _session() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    return s


def _state(gold: int = 20, hp: int | None = 100) -> GameState:
    return GameState(gold=gold, hp=hp, plane=1, round_num=2)


@pytest.fixture()
def ev_slots():
    """E3 数值开闸双槽注入(dstat 映射 + G_gold 观察值 8,注入形态):
    1→D0 带、3→D1 带;测试后复原。现态生产 = 双槽 None 期(见
    test_production_state_both_slots_none)。"""
    provisional.inject('ENCOUNTER_DSTAT_MAP', provisional.CalibValue(
        value={1: 100, 3: 150}, injected_form=True))
    provisional.inject('ENCOUNTER_G_GOLD', provisional.CalibValue(
        value=8, injected_form=True))
    yield
    provisional.reset('ENCOUNTER_DSTAT_MAP')
    provisional.reset('ENCOUNTER_G_GOLD')


# ===== 1. E3 同构决策树锁 =====

class TestE3DecisionTree:

    def test_lambda_undecidable_fails_low_zeroing_forbidden(self, ev_slots,
                                                             monkeypatch):
        """λ 不可判整体 fail 向锁(ADR-0536 §2-③):λ 项不可判 ⇒ 放弃
        argmax、fail 向选低难支。

        「负项置零继续 argmax」(12>8 ⇒ 选高难)是禁止实现——本锁在双槽
        注入但 λ 格全域外(表空)形态下断言 pick=低难支:fail 向不依赖
        任何 λ 数值授权。**不可判帧不刷新**(fail 向已知安全选项,重掷
        可能更差不赌——不可判出口零刷新断言并入本锁,双锁合一)。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', {})
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(),
                                             _session())
        assert pick.idx == _LOW.idx
        assert not pick.refresh
        assert 'lambda_undecidable' in pick.reason
        # λ 格非可消费(禁用)形态同判:整体不可判 fail 向 + 零刷新
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(label='禁用', lo=None, hi=None), _cell()))
        pick2 = encounter.decide_encounter_ev([_LOW, _HIGH], _state(),
                                              _session())
        assert pick2.idx == _LOW.idx
        assert pick2.refresh is False
        assert 'label禁用' in pick2.reason

    def test_production_state_both_slots_none(self):
        """生产现态锁(ADR-0536 §4):双槽 None 期(旗牌→stat 映射与金币
        金额均未定带)⇒ 恒 fail 向选低难、零刷新建议(未成型帧与现行
        低难保生存动作序列零冲突);拒因报金币支未定带(G_gold 闸在
        λ 闸之前)。"""
        assert provisional.get('ENCOUNTER_DSTAT_MAP') is None
        assert provisional.get('ENCOUNTER_G_GOLD') is None
        sess = _session()
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(), sess)
        assert pick.idx == _LOW.idx
        assert not pick.refresh
        assert 'reward_unmodeled' in pick.reason
        assert 'gold' in pick.reason
        assert state_of(sess).cw4_counters.get(
            'encounter_ev_fail_low_reward_unmodeled') == 1

    def test_dstat_only_injection_interlock(self, monkeypatch):
        """双槽互锁锁(ADR-0536 §3):只注 dstat 映射(G_gold 未定带)⇒
        金币支 V_r 未立 → fail 向,「12>8 ⇒ 高难更优」不会在半标定态
        产出(落地审建议-1:单例金额不进承重比较位)。"""
        provisional.inject('ENCOUNTER_DSTAT_MAP', provisional.CalibValue(
            value={1: 100, 3: 150}, injected_form=True))
        try:
            monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
                _cell(lo=0.30, hi=0.31), _cell(lo=0.40, hi=0.42)))
            pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(),
                                                 _session())
            assert pick.idx == _LOW.idx
            assert not pick.refresh
            assert 'gold' in pick.reason
        finally:
            provisional.reset('ENCOUNTER_DSTAT_MAP')

    def test_label_four_states_each_fail_low(self, ev_slots, monkeypatch):
        """label 四态接死:仅方向/禁用/空格/域外(key None)逐一 ⇒
        整体不可判 fail 向选低难。"""
        for label in ('仅方向', '禁用', '空格'):
            monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
                _cell(label=label, lo=None, hi=None), _cell()))
            pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(),
                                                 _session())
            assert pick.idx == _LOW.idx, label
            assert 'lambda_undecidable' in pick.reason, label
            assert f'label{label}' in pick.reason, label
        # key 观测量缺失(hp 缺读)→ 域外同判 fail 向
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(), _cell()))
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(hp=None),
                                             _session())
        assert pick.idx == _LOW.idx
        assert 'key_observable_missing' in pick.reason

    def test_direction_label_counts_note_only(self, ev_slots, monkeypatch):
        """仅方向格:不作数值(不进 argmax),只记方向注记分键。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(label='仅方向', lo=None, hi=None), _cell()))
        sess = _session()
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(), sess)
        assert pick.idx == _LOW.idx
        assert state_of(sess).cw4_counters.get('encounter_ev_lambda_direction_note') == 1

    def test_ev_argmax_robust_picks_high(self, ev_slots, monkeypatch):
        """双支 λ 可消费且比较稳健(保守端与乐观端同胜者)⇒ EV argmax
        选高难支(4费清算下界 12 > 金币观察值 8,λ 惩罚不足以翻转)。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(lo=0.30, hi=0.31), _cell(lo=0.40, hi=0.42)))
        sess = _session()
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(gold=20),
                                             sess)
        assert pick.idx == _HIGH.idx
        assert pick.reason.startswith('e3_pick:ev_argmax')
        assert state_of(sess).cw4_counters.get('encounter_ev_pick') == 1

    def test_real_lambda_table_flip_band_fails_low(self, ev_slots,
                                                   monkeypatch):
        """flip 不可判带锁(双锁合一:构表格 + 真实 P51 表两来源;双锁
        合一前为两条独立锁,语义同源故并)——EV 差在 CI 宽度下不稳健 ⇒
        fail 向选低难 + 探索性刷新建议(注入后窄域条件触发观察位,
        非生产现态预期)。

        构表格源:可控 d̂/gold 精确落 flip 带(注入形态)。
        真实表源:双槽注入时真表双带 encounter 格均「可消费」(D0
        0.354-0.623 / D1 0.48-0.889,d̂ 宽 0.269/0.409),默认局敞口
        (g=20,Ī=4,R=26)下 λ 惩罚差覆盖 12−8 奖励增量 ⇒ flip。
        ⚠️ 低-1 注记(真实表源):本锁是「λ 表当前分布形态锁」——λ 表
        按退役条件可重标,重标致红 = 表态变化信号(可消费格/d̂ 宽度
        变了),**先判表再判码**,禁为保绿机械回退判据改动。"""
        # 构表格源(gold=500 精确落 flip 带)
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(lo=0.30, hi=0.31), _cell(lo=0.40, hi=0.42)))
        sess = _session()
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(gold=500),
                                             sess)
        assert pick.idx == _LOW.idx
        assert pick.refresh is True
        assert state_of(sess).cw4_counters.get('encounter_ev_undecidable_band_flip') == 1
        assert state_of(sess).cw4_counters.get('encounter_ev_refresh_suggested') == 1
        # 真实表源(先复原启动必载真表,再默认敞口即 flip)
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE',
                            lambda_death._load_table())
        sess2 = _session()
        pick2 = encounter.decide_encounter_ev([_LOW, _HIGH], _state(), sess2)
        assert lambda_death.cell('D0|hp>40|P1|encounter') is not None
        assert pick2.idx == _LOW.idx
        assert pick2.refresh is True
        assert state_of(sess2).cw4_counters.get('encounter_ev_undecidable_band_flip') == 1

    def test_ev_exact_tie_fails_low_no_refresh(self, ev_slots, monkeypatch):
        """EV 精确并列锁(三审必修-1):双支 V_r 与复合项全等(典型 =
        标定后同难度双卡帧,两支解析到同 λ 格)⇒ 并列出口 fail 向低难
        (决策树第 5 肢)——不记 band_flip、不给刷新。守卫移除即红:
        并列误入翻转支时 refresh=True + flip 计数双双击穿本锁。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(lo=0.30, hi=0.31), _cell(lo=0.40, hi=0.42)))
        # dstat 两旗牌同 stat ⇒ 两支同 λ 格,复合项全等;双支同 4 费 ⇒ V_r 全等
        provisional.reset('ENCOUNTER_DSTAT_MAP')
        provisional.inject('ENCOUNTER_DSTAT_MAP', provisional.CalibValue(
            value={1: 100, 3: 100}, injected_form=True))
        try:
            tie_low = EncounterOption(idx=0, difficulty=1,
                                      rewards=['随机4费角色×3'])
            tie_high = EncounterOption(idx=1, difficulty=3,
                                       rewards=['随机4费角色×3'])
            sess = _session()
            pick = encounter.decide_encounter_ev([tie_low, tie_high],
                                                 _state(), sess)
            assert pick.idx == tie_low.idx
            assert pick.refresh is False
            assert 'ev_tie' in pick.reason
            assert 'encounter_ev_fail_low_tie' in state_of(sess).cw4_counters
            assert 'encounter_ev_undecidable_band_flip' not in state_of(sess).cw4_counters
            assert 'encounter_ev_refresh_suggested' not in state_of(sess).cw4_counters
        finally:
            provisional.reset('ENCOUNTER_DSTAT_MAP')

    def test_gold_unreadable_fail_closed(self, ev_slots, monkeypatch):
        """金缺读 fail-closed 锁(三审应修-5):gold_readable False 帧
        λ 敞口缺真值金 ⇒ 整体不可判 fail 向(缺读兜底 0 非真值,进敞口
        会压薄 λ 项,方向与保守相反)。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(lo=0.30, hi=0.31), _cell(lo=0.40, hi=0.42)))
        st = _state(gold=20)
        st.gold_readable = False
        sess = _session()
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], st, sess)
        assert pick.idx == _LOW.idx
        assert not pick.refresh
        assert 'gold_unreadable' in pick.reason
        assert 'encounter_ev_undecidable_band_flip' not in state_of(sess).cw4_counters

    def test_refresh_not_free_option_wording_and_gate(self, ev_slots,
                                                      monkeypatch):
        """刷新肢非免费期权(ADR-0536 §2-④):拒因明载「原对弃用强制
        新选、可为负」;refresh_used=True(本局已用)不再建议。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(lo=0.30, hi=0.31), _cell(lo=0.40, hi=0.42)))
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(gold=500),
                                             _session(), refresh_used=True)
        assert pick.idx == _LOW.idx
        assert pick.refresh is False
        assert 'branch_refresh_suggest' not in pick.reason
        sess = _session()
        pick2 = encounter.decide_encounter_ev([_LOW, _HIGH],
                                              _state(gold=500), sess)
        assert '原对弃用' in pick2.reason and '可为负' in pick2.reason

    def test_reward_unmodeled_fails_low(self, ev_slots, monkeypatch):
        """未建模子型(5费在册实录未立/读空帧)⇒ fail 向(未立 ≠ 0)。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(), _cell()))
        five = EncounterOption(idx=1, difficulty=3, rewards=['随机5费角色'])
        pick = encounter.decide_encounter_ev([_LOW, five], _state(),
                                             _session())
        assert pick.idx == _LOW.idx
        assert 'reward_unmodeled' in pick.reason
        empty = EncounterOption(idx=1, difficulty=3, rewards=[])
        pick2 = encounter.decide_encounter_ev([_LOW, empty], _state(),
                                              _session())
        assert pick2.idx == _LOW.idx
        assert 'unread' in pick2.reason

    def test_gold_on_high_branch_per_instance(self, ev_slots, monkeypatch):
        """子型与难度档独立组合(金子型在高难支实录在案)——判据按实例
        对评估,金在高难支不改变「fail 向选低难支」的支位选择。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', {})
        gold_high = EncounterOption(idx=0, difficulty=3, rewards=['金币×2'])
        fee_low = EncounterOption(idx=1, difficulty=1, rewards=['随机4费角色×3'])
        pick = encounter.decide_encounter_ev([gold_high, fee_low], _state(),
                                             _session())
        assert pick.idx == fee_low.idx   # 低难度支,与其上奖励子型无关

    def test_single_option_and_empty_options(self):
        """读缺帧:单卡帧选已读卡;无选项 idx0(生产 default)。"""
        pick = encounter.decide_encounter_ev([_HIGH], _state(), _session())
        assert pick.idx == _HIGH.idx
        assert 'single_option' in pick.reason
        pick2 = encounter.decide_encounter_ev([], _state(), _session())
        assert pick2.idx == 0


# ===== 2. 清算下界锁(唯一数值断言;注册表直调)=====

class TestClearingLowerBound:

    def test_12_over_8_registry_derived(self, ev_slots):
        """3×sell_refund(1★,4费)=12 > G_gold 注入观察值 8(cw_state 直调:
        star=1 无手续费全额退路径)。下界全类成立(P41 清算随时可得);
        8 是观察值经 ENCOUNTER_G_GOLD 槽注入(ADR-0536 §3),禁锁池构成/
        金额机制语义——未定带期金币支未立
        (test_production_state_both_slots_none 锁)。"""
        assert sell_refund(1, 4) == 4
        assert 3 * sell_refund(1, encounter.FEE4_COST) == 12
        g_gold = encounter._g_gold_observed()
        assert g_gold == 8
        assert 3 * sell_refund(1, encounter.FEE4_COST) > g_gold
        # 5 费子型下界形态声明(标定轮首扩展对象,未入树)
        assert 3 * sell_refund(1, 5) == 15

    def test_subtype_dispatch(self, ev_slots):
        """子型分派:文本 → (子型, V_r);子型与难度档独立组合。"""
        assert encounter.reward_subtype_value(
            ['随机4费角色×3'], 8) == ('4fee', 12)
        assert encounter.reward_subtype_value(['金币×2'], 8) == ('gold', 8)
        assert encounter.reward_subtype_value(['金币×2'], None) \
            == ('gold', None)    # 未定带:未立,非置零
        assert encounter.reward_subtype_value(['随机5费角色'], 8) \
            == ('5fee', None)
        assert encounter.reward_subtype_value([], 8) == ('unread', None)
        assert encounter.reward_subtype_value(['员工投影仪×1'], 8) \
            == ('other', None)


# ===== 3. P51 生存折现锁 =====

class TestP51SurvivalDiscount:

    def test_gold_rich_exposure_flips_to_fail_low(self, ev_slots,
                                                  monkeypatch):
        """P51 折现语义:λ 负项经 differential_composite(d̂×(g+Ī×R_剩余))
        入 EV——同一判据、同一 λ 格,金充裕帧敞口放大使 λ 惩罚覆盖奖励
        增量(12−8 差被 (d̂_高−d̂_低)×敞口 翻转)⇒ fail 向选低难。
        现态只锁方向,不锁敞口数值分布(P51 §5-11 区间敞口比较口径)。"""
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', _table(
            _cell(lo=0.30, hi=0.31), _cell(lo=0.40, hi=0.42)))
        # 金少:惩罚增量 < 奖励增量 → 稳健选高难
        assert encounter.decide_encounter_ev(
            [_LOW, _HIGH], _state(gold=20), _session()).idx == _HIGH.idx
        # 金充裕:同一 λ 项敞口放大 → flip 不可判带 → fail 向选低难
        pick = encounter.decide_encounter_ev([_LOW, _HIGH], _state(gold=500),
                                             _session())
        assert pick.idx == _LOW.idx


# ===== 4. 接线锁(mandate_v1 策略核消费位)=====

class TestWiring:

    def test_mandate_v1_decide_encounter_delegates(self, ev_slots):
        """mandate_v1.decide_encounter = E3 判据单一源消费位(桥壳零逻辑)。"""
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strat = MandateV1Strategy(registry=sim_decision_registry())
        sess = _session()
        pick = strat.decide_encounter([_LOW, _HIGH], _state(), sess, None)
        direct = encounter.decide_encounter_ev([_LOW, _HIGH], _state(), sess)
        assert pick.idx == direct.idx
        assert pick.refresh == direct.refresh
        assert pick.reason == direct.reason

    def test_baseline_cw_events_untouched(self):
        """基线核零触碰:未成型帧现行行为仍 = 低难保生存(cw_events 原
        评分路径,判据落地不外溢到其他策略核)。"""
        from sr_od.application.currency_war.kernel import cw_events
        opts = [EncounterOption(idx=0, difficulty=1),
                EncounterOption(idx=1, difficulty=3)]
        pick = cw_events.decide_encounter(opts, GameState(), None, None)
        assert pick.idx == 0


if __name__ == '__main__':
    pytest.main([__file__])
