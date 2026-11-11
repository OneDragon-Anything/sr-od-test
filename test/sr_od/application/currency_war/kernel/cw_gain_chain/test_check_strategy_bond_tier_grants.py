"""策略卡羁绊档位条件发放检查效果条目测试(镜像 src = kernel/cw_gain_chain.py
的 check_strategy_bond_tier_grants + kernel/cw_game_state.py 的
strategy_bond_tier_fired 一次性标志位域)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 3/4/5
(构造 = 状态容器直置直调检查效果条目;计数判据单一源 = cw_system_cards.
_faction_count 双源 max——board 状态容器(左面板真值口径,含 L2 星徽装备
贡献)× board_by_row 身份聚合(仅 factions+flows),直构按断言面向单侧
或双侧喂源;禁经 gain_character 构造达标态,会对触发面盲区假绿):

- 条件矩阵短路:无卡零写 / gate 不达(门槛羁绊计数 < tiers[0])零写
  零一次性标志位 / 激活非独立数 < 档位零写;
- 逐档首达一次性标志位:首达 3 发 1 件 + 一次性标志位;同板面再结算零重发;降档再回零重发;
  3∧7∧10 同拍跳档三笔升序;独立羁绊不计(救世主板面判别);gate 羁绊
  计入(首达锁板面即判别形);L2 星徽贡献计入(board 状态容器侧承载);
- 计数双源 max:身份侧 > 状态容器侧取大;双源双缺 → 0 零武装 fail-closed。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    seed_opening_state,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '梦境大舞台'
_EQUIP = '盛会之星星徽'

#: 满 3 激活板(左面板真值口径):盛会之星 2(gate ✓ 且计入激活)+
#: 治疗 2 + 护盾 2 → 激活非独立 = 3 → tier 3。
_BOARD_T3: dict[str, int] = {'盛会之星': 2, '治疗': 2, '护盾': 2}
#: 2 激活负控板(去护盾):gate ✓ 但激活数 2 < 3。
_BOARD_ACT2: dict[str, int] = {'盛会之星': 2, '治疗': 2}
#: gate 不达负控板:盛会之星 1(< tiers[0]=2),非 gate 激活已 ≥3
#: (治疗/护盾/贝洛伯格/列车同行/星核猎手五族)——「gate 关闭期即便
#: 激活数达标也不发」的唯一判别形态。
_BOARD_GATE_SHUT: dict[str, int] = {
    '盛会之星': 1, '治疗': 2, '护盾': 2, '贝洛伯格': 2, '列车同行': 2,
    '星核猎手': 2,
}
#: 满 10 激活板:10 个非独立族各达 tiers[0](跳档三笔 3/7/10 判别板)。
_BOARD_T10: dict[str, int] = {
    '盛会之星': 2, '治疗': 2, '护盾': 2, '贝洛伯格': 2, '列车同行': 2,
    '星核猎手': 2, '巡海游侠': 1, '命运圣杯': 2, '银河学者': 2,
    '持续伤害': 2,
}
#: 独立羁绊判别板:盛会之星 2 + 治疗 2 + 救世主 1(独立,tiers=(1,))
#: ——救世主计入则激活 = 3 误发(红判据),排除则 = 2 零写。
_BOARD_INDEP: dict[str, int] = {'盛会之星': 2, '治疗': 2, '救世主': 1}


def _slots(bench: list[tuple[str, int]]) -> list[BenchSlot]:
    out = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
           for c, s in bench]
    return out + [BenchSlot(kind='empty')] * (9 - len(out))


def _gs(*, card: str | None = _CARD, board: dict[str, int] | None,
        deployed: DeployedView | None = None) -> GameState:
    """持卡 + 板面直置直构域(equips 走 seed 初始值 [] = 观察态,发放可
    落位;board/deployed None = 双缺域,fail-closed 判别输入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    gs.prep_anchored = True   # 置一次性标志位:达标发放 = 确定事件,锁确定面写通道
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    if board is not None:
        gs.observe(gs.board, dict(board), sig=_SIG_OBS)
    if deployed is not None:
        gs.observe(gs.deployed, deployed, sig=_SIG_OBS)
    return gs


def _deployed(*units: tuple[str, str | None]) -> DeployedView:
    """行域直构:(角色名, 佩戴装备名 | None);前排承载全部单位
    (检查效果条目不分排,全板合计口径)。"""
    front = [Unit(char_id=name, star=1,
                  equips=[equip] if equip else [])
             for name, equip in units]
    return DeployedView(front_slots=front, back_slots=[])


def _bond_counts(gs: GameState) -> int:
    """激活非独立羁绊数镜像(测试侧判读辅助,口径 = 检查效果条目单一源)。"""
    from sr_od.application.currency_war.data.cw_factions import FACTIONS
    from sr_od.application.currency_war.kernel.cw_system_cards import (
        _faction_count,
    )
    return sum(1 for f, info in FACTIONS.items()
               if info.category != 'independent'
               and _faction_count(gs, f) >= info.tiers[0])


def test_no_card_zero_write() -> None:
    """短路锁(无卡):板面达标但未持卡 → 零发放零一次性标志位(持卡交集为空 =
    整效果条目无候选)。"""
    gs = _gs(card=None, board=_BOARD_T3)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    assert gs.equips.value == [], '未持卡误发放'
    assert gs.strategy_bond_tier_fired.value in (None, ()), '未持卡误置一次性标志位'


def test_gate_shut_zero_write_zero_latch() -> None:
    """短路锁(gate 不达):门槛羁绊计数 1 < tiers[0]=2 → 零写零一次性标志位
    (状态检查型:gate 关闭期不武装不记档,即便激活数已达标也不发)。"""
    gs = _gs(board=_BOARD_GATE_SHUT)
    assert _bond_counts(gs) >= 3, '前置:激活数本身已达标(gate 唯一判别)'
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    assert gs.equips.value == [], 'gate 关闭误发放'
    assert gs.strategy_bond_tier_fired.value in (None, ()), 'gate 关闭误置一次性标志位'


def test_activated_below_tier_zero_write() -> None:
    """短路锁(激活非独立数 < 档位):gate 开但激活数 2 < 3 → 零写
    零一次性标志位。"""
    gs = _gs(board=_BOARD_ACT2)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    assert gs.equips.value == [], '激活不足误发放'
    assert gs.strategy_bond_tier_fired.value in (None, ()), '激活不足误置一次性标志位'


def test_first_reach_tier3_grants_and_latches() -> None:
    """首达一次性标志位锁(主条,兼 gate 羁绊计入口径判别):板面 3 激活(含
    gate 羁绊自身)→ 发 1 件星徽 + 落一次性标志位;发放走确定面,evidence =
    strategy_bond_tier:<卡名>@<档位>(gain_equipment #equip 后缀链)。
    若 gate 羁绊不计入则激活 = 2 不触发(红判据)。"""
    gs = _gs(board=_BOARD_T3)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    effects = check_strategy_bond_tier_grants(gs, _LSIG)
    assert effects == (f'strategy_bond_tier:{_CARD}@3',), \
        f'效果串漂移: {effects!r}'
    assert gs.equips.value == [_EQUIP], f'未发放: {gs.equips.value!r}'
    assert gs.equips.source == 'logic', '确定事件应走确定面写'
    assert gs.equips.evidence \
        == f'strategy_bond_tier:{_CARD}@3#equip'
    assert gs.strategy_bond_tier_fired.value == (f'{_CARD}#3',), \
        f'未落一次性标志位: {gs.strategy_bond_tier_fired.value!r}'
    assert gs.strategy_bond_tier_fired.source == 'logic', '一次性标志位 = 登记事实直写'
    assert gs.strategy_bond_tier_fired.evidence \
        == f'strategy_bond_tier:{_CARD}@3'
    # 同板面再结算:零重发(一次性标志位命中)
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    assert gs.equips.value == [_EQUIP], '同板面重发'
    assert gs.strategy_bond_tier_fired.value == (f'{_CARD}#3',), '一次性标志位值漂移'


def test_latch_survives_dip_and_restore() -> None:
    """首达一次性标志位锁(降档再回):发放后板面跌回(2 激活)→ 零写;再回 3
    激活 → 仍零重发(一次性标志位 = 「首次」语义,卖员降档不回滚已发放)。"""
    gs = _gs(board=_BOARD_T3)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) != ()
    assert gs.equips.value == [_EQUIP]
    gs.observe(gs.board, dict(_BOARD_ACT2), sig=_SIG_OBS)
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    gs.observe(gs.board, dict(_BOARD_T3), sig=_SIG_OBS)
    assert check_strategy_bond_tier_grants(gs, _LSIG) == (), '回档重发'
    assert gs.equips.value == [_EQUIP], '回档误发放'
    assert gs.strategy_bond_tier_fired.value == (f'{_CARD}#3',), '一次性标志位值漂移'


def test_same_call_tier_jump_grants_ascending() -> None:
    """跳档锁(3∧7∧10 同拍):10 激活板 → 单次调用三笔发放按档位升序,
    一次性标志位三键升序齐落(一局上限 Σ档位 = 3 件;禁全局单发形态)。"""
    gs = _gs(board=_BOARD_T10)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    effects = check_strategy_bond_tier_grants(gs, _LSIG)
    assert effects == (f'strategy_bond_tier:{_CARD}@3',
                       f'strategy_bond_tier:{_CARD}@7',
                       f'strategy_bond_tier:{_CARD}@10'), \
        f'跳档语序漂移: {effects!r}'
    assert gs.equips.value == [_EQUIP] * 3, \
        f'入栏应恰 3 件: {gs.equips.value!r}'
    assert gs.strategy_bond_tier_fired.value \
        == (f'{_CARD}#3', f'{_CARD}#7', f'{_CARD}#10'), '一次性标志位键序漂移'
    # 再结算零重发(三一次性标志位全命中)
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    assert gs.equips.value == [_EQUIP] * 3, '跳档后重发'


def test_independent_factions_excluded() -> None:
    """独立羁绊不计锁:救世主(独立,tiers=(1,) 单人即激活)在场 →
    排除后激活 = 2 < 3 零写;若误计入则激活 = 3 误发(红判据)。"""
    gs = _gs(board=_BOARD_INDEP)
    assert _bond_counts(gs) == 2, \
        '前置:非独立激活数应为 2(救世主被排除)'
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    assert gs.equips.value == [], '独立羁绊误计入激活数'


def test_l2_badge_contribution_counts_via_board_source() -> None:
    """L2 星徽贡献计入锁:盛会之星第 2 计数来自穿徽单位(L2 装备贡献,
    身份聚合口径不计——cw_board_by_row 只算 factions+flows),仅 board
    状态容器(左面板真值)承载 → gate 经双源 max 融合开启;若检查效果条目单吃
    身份源则 gate 关闭误零发(红判据)。板面 = 花火 + 娜塔莎(佩戴
    星徽)→ 盛会之星 2;娜塔莎+藿藿 = 治疗 2;杰帕德+砂金 = 护盾 2。"""
    deployed = _deployed(('花火', None), ('娜塔莎', _EQUIP), ('藿藿', None),
                         ('杰帕德', None), ('砂金', None))
    gs = _gs(board={'盛会之星': 2, '治疗': 2, '护盾': 2},
             deployed=deployed)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) \
        == (f'strategy_bond_tier:{_CARD}@3',)
    assert gs.equips.value == [_EQUIP], 'L2 贡献凑档未触发'


def test_identity_source_superiority_max_fusion() -> None:
    """计数双源 max 锁(身份侧 > 状态容器侧):board 状态容器滞留盛会之星 1
    (单侧 miss 形态)而身份聚合 = 2 → max 取 2 gate 开;若单吃状态容器
    源则 gate 关闭误零发(红判据)。治疗 2 = 娜塔莎+藿藿,护盾 2 =
    杰帕德+砂金(双源同值)。"""
    deployed = _deployed(('花火', None), ('知更鸟', None), ('娜塔莎', None),
                         ('藿藿', None), ('杰帕德', None), ('砂金', None))
    gs = _gs(board={'盛会之星': 1, '治疗': 2, '护盾': 2},
             deployed=deployed)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) \
        == (f'strategy_bond_tier:{_CARD}@3',)
    assert gs.equips.value == [_EQUIP], '身份源计数缺失'


def test_dual_source_missing_fail_closed() -> None:
    """计数双源双缺 fail-closed 锁:board 与 deployed 均未观察 →
    全族计数 0,gate 关闭零写零一次性标志位(宁缺勿造)。"""
    gs = _gs(board=None, deployed=None)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    assert gs.equips.value == [], '双缺域误发放'
    assert gs.strategy_bond_tier_fired.value in (None, ()), '双缺域误置一次性标志位'


def test_bench_side_unused_in_count() -> None:
    """备战席不计锁(哨兵面):达标单位全在备战席(非上阵)→ 板面
    计数双源均不含 → gate 关闭零写(激活判定 = 板面口径,bench 不是
    计数源;防后继误扩池口径)。"""
    gs = _gs(board={'治疗': 2, '护盾': 2})
    gs.observe(gs.bench, BenchView(slots=_slots([('花火', 1)]),
                                   capacity=9), sig=_SIG_OBS)
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_bond_tier_grants,
    )
    assert check_strategy_bond_tier_grants(gs, _LSIG) == ()
    assert gs.strategy_bond_tier_fired.value in (None, ()), 'bench 误计入'
