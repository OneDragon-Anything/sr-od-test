"""统一state R4 策略侧遥测演进锁(删除波 1 重写:写端退役,申报面守卫保留)。

设计正本 = ADR-0630(统一 state 状态流水,持久结论单一源;.debug/temp
工作稿为易失档)策略侧 state_ref 版本钉与逐项理由溯源面;账本裁定 =
dag T-217 note 2026-09-10T12:33:16(策略侧遥测定稿:四要素/瘦身判据/动作
计划逐项理由溯源)与 12:34:44(每决策一行,动作计划随行携带)。

删除波 1(用户 2026-09-10 直迁裁定):本文件原辖的 decisions 行写端面
(① state_ref 版本钉五支、② 理由溯源 record 路径四支、③c 行 shape 回归)
随 record_decision 写入端整段退役——state_ref 钉与逐项理由的现役归宿 =
策略侧决策行(两文件之二,M4 前落地),接线批重立锁。保留面:

- 申报面锁:理由提取键序单一源(schema 纯函数)/ B 档瘦身候选字段在场
  (候裁不执行的结构性守卫)/ A 档删候选已删封闭 + 瘦身后 schema 形态
  封闭 / state_ref、pin_scope 可选末尾字段读端兼容;
- 退役锁:写端符号不存在(防半删)。
"""
from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass

from sr_od.application.currency_war.telemetry import recorder as rec_mod
from sr_od.application.currency_war.telemetry.cw_replay_reader import (
    DecisionTrace,
    from_dict,
)
from sr_od.application.currency_war.telemetry.schema import (
    ACTION_REASON_SOURCE_KEYS,
)

# ===== ① state_ref 版本钉(写端退役;字段面归策略侧决策行接线批)=====

def test_state_ref_writer_retired() -> None:
    """锁①(重写):决策行写入端退役,防半删;版本钉语义(决策行回溯
    流程侧账本版本,ADR-0630)现役落点 = 策略侧决策行(两文件之二,
    M4 前落地),接线批重立钉读点锁。"""
    assert not hasattr(rec_mod, 'record_decision'), \
        'record_decision 应已随删除波 1 删除(防半删)'
    assert not hasattr(rec_mod.TelemetryRecorder, 'record_decision'), \
        '类方法 record_decision 应已随删除波 1 删除(防半删)'


# ===== ② 动作计划逐项理由溯源(键序单一源保留;record 路径退役)=====

def test_action_reason_keys_declared_single_source() -> None:
    """锁②e:理由提取键序单一源(申报面):reason > route_tag > auth_basis
    > convert_reason——动作自带归因优先,发射臂标签次之,授权/豁免记录
    兜底;键序扩展只改 schema 元组。"""
    assert ACTION_REASON_SOURCE_KEYS == (
        'reason', 'route_tag', 'auth_basis', 'convert_reason')
    from sr_od.application.currency_war.telemetry.schema import (
        action_reason_of,
    )
    assert action_reason_of({'reason': 'a', 'route_tag': 'b'}) == 'a'
    assert action_reason_of({'route_tag': 'b', 'auth_basis': 'c'}) == 'b'
    assert action_reason_of({'auth_basis': 'c', 'convert_reason': 'd'}) == 'c'
    assert action_reason_of({'convert_reason': 'd'}) == 'd'
    assert action_reason_of({}) == ''
    assert action_reason_of({'reason': ''}) == ''


# ===== ③ 申报面锁(瘦身候选:候裁不执行的结构性守卫) =====

def test_slimming_candidate_fields_still_present() -> None:
    """锁③a:瘦身候选字段仍在 DecisionTrace 且现役写入缺省不变。

    R4 第一批只申报不执行(GameState 未退役前保守);本锁 = 申报面守卫——
    候裁删除前有人顺手删字段/改缺省即红。候选集语义(设计 v3.6 §3.5.1-2):
    hp/gold/plane/round_num 与行内 state 快照同义重复;三个 *_readable 标志
    的质量语义由流程侧渠道签名承接。
    """
    names = {f.name for f in fields(DecisionTrace)}
    candidates = ('hp', 'gold', 'plane', 'round_num',
                  'hp_readable', 'gold_readable', 'level_readable')
    for n in candidates:
        assert n in names, f'瘦身候选字段 {n} 被删除(候裁未过,禁执行)'
    d = asdict(DecisionTrace())
    assert d['hp_readable'] is True and d['gold_readable'] is True \
        and d['level_readable'] is True
    assert d['hp'] == 0 and d['gold'] == 0 and d['plane'] == 0 \
        and d['round_num'] == 0


def test_tier_a_deleted_fields_absent_and_shape_locked() -> None:
    """锁③d:A 档删候选 4 字段已从 DecisionTrace 删除 + 瘦身后形态封闭锁。

    A 档 4 字段(ledger_fingerprint/sess_v2_state/sess_p2_auth_intercept/
    sess_p2_auth_water)= R4 逐字段消费方审计 A 档「写端已死且全域零读」,
    经用户直迁裁定执行删除(T-217 note 2026-09-10T12:33:16 ②瘦身判据链);
    本锁钉「已删」防回填,并以封闭字段名集钉瘦身后 schema 形态(59−4=55
    面)——未申报的增删字段即红。B 档 7 字段(快照重复)仍由锁③a 守在场,
    其删除归消费方迁移裁决后的后续批。
    """
    names = {f.name for f in fields(DecisionTrace)}
    deleted = ('ledger_fingerprint', 'sess_v2_state',
               'sess_p2_auth_intercept', 'sess_p2_auth_water')
    for n in deleted:
        assert n not in names, f'A 档已删字段 {n} 重新出现(已删封闭,禁回填)'
    assert names == {
        'active_strategies', 'actions', 'b_t', 'candidate_scores',
        'difficulty', 'dp_posture', 'eval_breakdown', 'ev_arm',
        'expected_paths', 'formed_stop', 'form_ok', 'form_score',
        'gold', 'gold_readable', 'handoff', 'hp', 'hp_readable',
        'level_readable', 'phase', 'piggy_reward', 'pin_scope',
        'p1_downgrade_active', 'p26_prep_obs', 'plane',
        'posture_unfulfilled', 'refresh_trigger', 'round_num', 'run_id',
        'schema_version', 'sess_active_env', 'sess_blood_budget_rejects',
        'sess_blood_budget_refresh_rejects', 'sess_commit_scores',
        'sess_drought', 'sess_dual_track', 'sess_framework',
        'sess_p1_pair', 'sess_release_budget', 'sess_release_reason',
        'sess_release_spent', 'sess_reserve_cap', 'sess_reserve_overflow',
        'sess_terminal_release', 'shop_rejects', 'state', 'state_ref',
        'strategy_id', 'supply_pick', 'target_comp', 'ts', 'v2_bridge',
        'v2_locked_line', 'v2_mode', 'v3_intention', 'xp_expect_ledger',
    }, 'DecisionTrace 字段面漂移(瘦身后形态封闭锁;增删字段须申报并改本锁)'


def test_state_ref_fields_are_optional_trailing() -> None:
    """锁③b:state_ref/pin_scope 为末尾追加可选字段,缺省 ''——旧档案行
    经规范读端缺字段落默认值,零破坏(判读读面宽容原则,消费方兼容)。"""
    assert is_dataclass(DecisionTrace)
    f = from_dict(DecisionTrace, {'run_id': 'old_row', 'round_num': 1})
    assert f.state_ref == '' and f.pin_scope == ''
    f2 = from_dict(DecisionTrace, {'run_id': 'r', 'state_ref': 'run#3',
                                   'pin_scope': 'board_state'})
    assert f2.state_ref == 'run#3' and f2.pin_scope == 'board_state'
