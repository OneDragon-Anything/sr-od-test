"""策略卡合成触发发放注册面测试(cw_investments 分目录镜像;单一源 +
两表同键各表各域对账 + 构建校验负例,先例 = 同目录
test_strategy_win_gold_grants.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-179-shali-
taojin.md(定稿)§4 锁 5 + REVIEW-T179 §3.4 + designs/T-409-heita-jiyuan.md
§2.3/§5.1 用户终裁(2026-11-06 表值形泛化四元组收行)。卡面官方原文:
「合成2星2费角色时，获得1张【砂金】。」(id 201501,品质金)/「你获得
3星【黑塔】时获得【大黑塔】」(id 352601,品质棱):

- 登记单一源:STRATEGY_MERGE_GRANTS 行值 = 卡面直读四元组(判据星级,
  判据费用, 判据角色名[''=通配], 发放角色)——注册行直测承担值形对账:
  判据值域(星级/费用)与非负查按 2026-10-28 治理口径不设校验,值形漂移
  唯此锁可暴露;
- 通配行(砂里淘金):卡面不限定角色 → 判据角色名空串,费用/星级双匹配
  即发(泛化前原语义零改);
- 具名行(黑塔纪元):卡面双具名直读,判据角色名 = 黑塔,判据费用 = 黑塔
  注册 cost=1;
- 双母体对账:本表(世界发放域)与 STRATEGY_GRANTS(估值域档位机器)
  同键共存 = 合法形态,条目保留零删(反扫闭集底册完整);
- 构建校验 4 条(漂移哨,import 即炸语义经直调校验函数锁定):
  孤儿键 + 发放角色名漂移 + 判据角色名闭集 + 具名行判据费用一致性
  (后两哨 = 游戏数值/词表改版会触发的漂移哨,按 2026-10-28 治理判据
  可留;判据值域/非负防笔误哨不复活)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTERS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    CHARACTER_ROSTER,
    INVESTMENT_STRATEGIES,
    STRATEGY_GRANTS,
    STRATEGY_MERGE_GRANTS,
    _validate_strategy_merge_grants,
)

_CARD = '砂里淘金'
_REWARD = '砂金'
_CARD_NAMED = '黑塔纪元'
_JUDGE = '黑塔'
_REWARD_NAMED = '大黑塔'


def test_registry_rows_single_source() -> None:
    """登记单一源(锁 5 主锚):行值 = 卡面直读四元组;键 ∈ 策略注册表
    (孤儿哨现值通过 = import 过闸即证,显式对拍防静默漂移);注册面 =
    合成触发发放族现役两行(通配首例 + 具名首例,同族后续卡各自独立批,
    禁顺手代登记)。"""
    assert set(STRATEGY_MERGE_GRANTS) == {_CARD, _CARD_NAMED}, \
        '注册面 = 合成触发发放族现役两行(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_MERGE_GRANTS[_CARD] == (2, 2, '', _REWARD), \
        f'通配行值漂移(卡面明写合成2星2费得砂金,不限定角色): ' \
        f'{STRATEGY_MERGE_GRANTS!r}'
    assert STRATEGY_MERGE_GRANTS[_CARD_NAMED] == \
        (3, 1, _JUDGE, _REWARD_NAMED), \
        f'具名行值漂移(卡面明写获得3星黑塔得大黑塔): ' \
        f'{STRATEGY_MERGE_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES \
        and _CARD_NAMED in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_reward_char_registered_and_cost_matches_criterion() -> None:
    """发放/判据角色在册三对拍:两行发放名 ∈ CHARACTER_ROSTER(角色漂移
    哨现值通过);通配行判据角色名恒空串(费用是唯一判别维,无具名一致性
    面);具名行判据角色名 ∈ CHARACTER_ROSTER 且其注册费用与判据费用
    一致——黑塔 cost=1 = 判据费用 1(游戏改费漂移唯构建校验哨 + 本锁
    可暴露)。"""
    assert _REWARD in CHARACTER_ROSTER \
        and _REWARD_NAMED in CHARACTER_ROSTER, '发放角色必须在角色注册表'
    assert STRATEGY_MERGE_GRANTS[_CARD][2] == '', '通配行判据角色名 = 空串'
    assert STRATEGY_MERGE_GRANTS[_CARD_NAMED][2] == _JUDGE, \
        '具名行判据角色名对拍'
    assert _JUDGE in CHARACTER_ROSTER, '具名判据角色必须在角色注册表'
    assert CHARACTERS[_REWARD].cost == STRATEGY_MERGE_GRANTS[_CARD][1], \
        '通配行判据费用 ≠ 发放角色注册费用(两表面漂移)'
    assert CHARACTERS[_JUDGE].cost == STRATEGY_MERGE_GRANTS[_CARD_NAMED][1], \
        '具名行判据费用 ≠ 判据角色注册费用(游戏改费漂移产生永假判据)'


def test_grants_entry_coexists_world_channel_pointer() -> None:
    """双母体对账(两行各一):STRATEGY_GRANTS 估值域条目保留零删
    (即时/条件腿底册完整,反扫闭集不受新表影响);本表辖世界发放,
    两表同键各表各域。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_conditional == ((_REWARD, '合成2星2费角色时'),), \
        f'估值域条件效果条目底册漂移: {grant.chars_conditional!r}'
    grant2 = STRATEGY_GRANTS[_CARD_NAMED]
    assert grant2.chars_immediate == (_REWARD_NAMED,), \
        f'估值域即时效果条目底册漂移: {grant2.chars_immediate!r}'
    assert grant2.chars_conditional == \
        ((_REWARD_NAMED, '你获得3星【黑塔】时获得【大黑塔】'),), \
        f'估值域条件效果条目底册漂移: {grant2.chars_conditional!r}'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。值域/非负查按 2026-10-28 治理口径
    不设,无对应锁(校验函数本体不存在该查,防哨复增由评审把关)。"""
    monkeypatch.setitem(STRATEGY_MERGE_GRANTS, '不存在的卡',
                        (2, 2, '', _REWARD))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_merge_grants()


def test_validator_reward_char_drift_raises(monkeypatch) -> None:
    """构建校验(发放角色名漂移哨):发放角色不在 CHARACTER_ROSTER →
    ValueError(版本改名不静默)。"""
    monkeypatch.setitem(STRATEGY_MERGE_GRANTS, _CARD,
                        (2, 2, '', '不存在的角色'))
    with pytest.raises(ValueError, match='角色名漂移'):
        _validate_strategy_merge_grants()


def test_validator_judge_char_drift_raises(monkeypatch) -> None:
    """构建校验(判据角色名闭集哨):具名判据角色不在 CHARACTER_ROSTER
    → ValueError(游戏改名不静默——改名后事件角色名永不匹配 = 永假
    判据);空串通配形合法不触本哨(现网两行即证)。"""
    monkeypatch.setitem(STRATEGY_MERGE_GRANTS, _CARD_NAMED,
                        (3, 1, '不存在的角色', _REWARD_NAMED))
    with pytest.raises(ValueError, match='判据角色名漂移'):
        _validate_strategy_merge_grants()


def test_validator_judge_cost_mismatch_raises(monkeypatch) -> None:
    """构建校验(具名行判据费用一致性哨):判据角色注册费用 ≠ 判据费用
    → ValueError(游戏改费漂移产生永假判据;黑塔现值 cost=1 与判据 1
    相符 = 现网通过,本负例直构失配值)。"""
    assert CHARACTERS[_JUDGE].cost == 1, \
        '前置:判据角色现值 cost=1(与判据费用相符,现网通过)'
    monkeypatch.setitem(STRATEGY_MERGE_GRANTS, _CARD_NAMED,
                        (3, 4, _JUDGE, _REWARD_NAMED))
    with pytest.raises(ValueError, match='判据费用失配'):
        _validate_strategy_merge_grants()
