"""T-153 自证循环迁移·可疑项检测器与复盘骨架锁(ADR-0593)。

被测面(出处 = ADR-0593 §4 + 用户裁定 2026-09-08;方案正本 =
该ADR-0593 §D1-D11 与节点结合方式):
- 检查器迁移(9 判定核,C1/C2/C4/C5/C7;C3 判据本体保留机械检查器、
  辖域缺口由 D3 补位,C6 语境条目归 D6):失配 → 可疑项条目 + 不豁免;
  复核通过/不可复核 → 豁免照旧(兼容策略,避免一刀切翻旧案;无键回退
  先例 = ADR-0589);
- 生成侧自算披露三键(engine_p1 执行点;先例 = ADR-0589 dec_board_full):
  ``dec_engines_count``/``dec_sell_in_line``/``dec_bench_wait_member``;
- 检测器集 D1-D11(sim/checks/suspects.py)与复盘骨架生成器
  (tools/cw/review_skeleton.py):可疑项挂对应节点小节、判定三槽前,
  禁独立附录(用户裁定);
- 生产行为守卫:criteria/sell_gate/mandate 发射判定不读新披露键
  (决策路径零变化,T-153 硬约束;依赖方向守卫 = sr-od-test README
  纪律 8 的合法源码扫描)。
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.sim.checks import ledger, suspects
from sr_od.application.currency_war.sim.checks.pool import (
    check_engine_seed_not_resold,
    check_engine_seed_sell_exemption,
)
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_TOOL = (Path(__file__).resolve().parents[5] / 'tools/cw/review_skeleton.py')


@lru_cache(maxsize=1)
def _seed18_ledger() -> tuple:
    """seed18 全局账本(同次运行内只算一次;README 纪律 11)。"""
    return tuple(simulate_p1(18, pool='snapshot').ledger)


def _locked_target() -> tuple[str, str]:
    """(锁定线标签, 其名册首个成员名)——注册表现推,禁手抄名。"""
    label = '绯英欢愉'   # 生产 target_comp 同域的 COMP_LIBRARY 套名
    members = line_members(get_comp(label))
    assert members, '注册表名册空(测试锚失准,重选套名)'
    return label, members[0]


def _engine_piece() -> str:
    """注册表现推的引擎件名(禁手抄;锚失准红 = 重选)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_line_defs import (
        ENGINE_FACTIONS,
    )
    for n, ch in sorted(CHARACTERS.items()):
        bonds = set(ch.factions or ()) | set(ch.flows or ())
        if bonds & set(ENGINE_FACTIONS):
            return n
    raise AssertionError('注册表无引擎件(测试锚失准)')


def _non_engine_piece() -> str:
    """注册表现推的非引擎件名(身份复核的对照腿)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_line_defs import (
        ENGINE_FACTIONS,
    )
    for n, ch in sorted(CHARACTERS.items()):
        bonds = set(ch.factions or ()) | set(ch.flows or ())
        if not bonds & set(ENGINE_FACTIONS):
            return n
    raise AssertionError('注册表无非引擎件(测试锚失准)')


def _lv_rows(auth: str, full: bool | None, wait: bool | None,
             bench: list[str] | None = None) -> list[dict]:
    """追级段合成账本(锁定线语境;dec 键可选 = 旧账本形态)。"""
    label, member = _locked_target()
    row: dict = {
        'plane': 1, 'round_num': 7, 'gold': 40,
        'target_comp': label,
        'state': {'level': 7, 'cap': 6,
                  'board_factions': {}, 'deployed': [],
                  'bench': [{'char_id': n, 'faction': '?'}
                            for n in (bench if bench is not None
                                      else [member])]},
        'sim': {'shop_waves': [{'gold': 40, 'cards': []}]},
        'actions': [dict({'__type__': 'LevelUp', 'cost': 4, 'auth': auth},
                         **({} if full is None and wait is None else {
                             'dec_board_full': full,
                             'dec_bench_wait_member': wait}))],
    }
    return [{'plane': 1, 'round_num': 6, 'gold': 40,
             'state': {'level': 7}}, row]


# ===== C1 冷启动身份复核 ======================================================

def test_c1_coldstart_identity_review() -> None:
    """C1:身份断言型自述降级——失配产可疑项;一致豁免照旧。

    红证:拔掉迁移分支(恢复静默 continue)则失配行零输出 = 改标绕门
    攻击面(T-153 §1-C1 词表白名单漏报)复现。
    """
    ok = {'plane': 1, 'round_num': 1,
          'state': {'board_factions': {}, 'bench': [], 'deployed': []},
          'actions': [{'__type__': 'BuyCard',
                       'card': {'name': '桑博', 'faction': '风', 'cost': 1},
                       'reason': 'bridge_seed', 'channel': 'bridge_seed'}]}
    bad = {'plane': 1, 'round_num': 1,
           'state': {'board_factions': {}, 'bench': [], 'deployed': []},
           'actions': [{'__type__': 'BuyCard',
                        'card': {'name': '银狼', 'faction': '星核猎手',
                                 'cost': 3},
                        'reason': 'bridge_seed', 'channel': 'off'}]}
    assert ledger.check_coldstart_seed_squander([ok]) == []
    v = ledger.check_coldstart_seed_squander([bad])
    assert len(v) == 1 and '可疑项' in v[0] \
        and '自报 reason=bridge_seed' in v[0] \
        and '自算身份=off' in v[0] and '请裁决' in v[0]


# ===== C2 升级授权前置复核(ledger + seg 两核) ================================

def test_c2_levelup_auth_prereq_review() -> None:
    """C2-a:pop_slot/m3_batch 可核前置复核;dp 不可复算豁免照旧。

    红证:拔掉复核分支则谎报臂名(板不满却自称 m3_batch)静默豁免。
    """
    bad = _lv_rows('m3_batch', False, True)
    v = ledger.check_levelup_interest_engine_gate(bad)
    assert len(v) == 1 and '可疑项' in v[0] \
        and '自报授权=m3_batch' in v[0] and '板满=False' in v[0]
    ok = _lv_rows('pop_slot', True, True)
    assert ledger.check_levelup_interest_engine_gate(ok) == []
    # dp/static_ev:决策期中间量不可机械复算 = unverifiable → 豁免照旧
    assert ledger.check_levelup_interest_engine_gate(
        _lv_rows('dp', None, None)) == []
    # 名册不可解析(未锁线,target 空)×板满腿反证解耦(ADR-0593 后果.1 L6):
    # - dec_board_full=False = 名册无关反驳证据 → 仍产失配(后门封死)
    unlocked_lie = _lv_rows('m3_batch', False, False)
    unlocked_lie[1]['target_comp'] = ''
    v = ledger.check_levelup_interest_engine_gate(unlocked_lie)
    assert len(v) == 1 and '可疑项' in v[0] and '板满=False' in v[0]
    # - 板满宣称与真值一致(键 True)+ 待上场腿不可得 → unverifiable 豁免
    unlocked_ok = _lv_rows('m3_batch', True, False)
    unlocked_ok[1]['target_comp'] = ''
    assert ledger.check_levelup_interest_engine_gate(unlocked_ok) == []


def test_c2b_seg_unjustified_review_event() -> None:
    """C2-b(段级镜像):失配产出带 ``suspect`` 标记的事件;金门辖域。

    ADR-0593 后果.5(L4):复核辖域与批版同门(lv≥5 ∧ 时点金<金门)——金门外
    白名单臂不产可疑项,且「80<50」类假文案禁再现(阈值由注册表现读)。
    """
    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_unjustified_levelup,
    )
    evs = seg_check_unjustified_levelup(_lv_rows('m3_batch:arm1', True, False))
    assert len(evs) == 1
    assert evs[0].get('suspect') is True
    assert '待上场=False' in evs[0]['detail']
    assert '<50' not in evs[0]['detail'], '禁硬编码阈数字假文案'
    assert seg_check_unjustified_levelup(_lv_rows('pop_slot', True, True)) == []
    # ADR-0593 后果.5 L4 红证:金 80(金门外)板不满 pop_slot → 不产可疑项
    gold80 = _lv_rows('pop_slot', False, True)
    gold80[1]['gold'] = 80
    gold80[1]['sim']['shop_waves'][0]['gold'] = 80
    assert seg_check_unjustified_levelup(gold80) == []


# ===== C4 同轮买卖三豁免复核(互斥 + XP 镜像) ================================

def _pair_row(sell_extra: dict) -> dict:
    return {'plane': 1, 'round_num': 3, 'state': {'bench': [], 'deployed': []},
            'actions': [
                {'__type__': 'BuyCard',
                 'card': {'name': '青雀', 'faction': '量子', 'cost': 1},
                 'reason': 'line'},
                dict({'__type__': 'SellBench', 'name': '青雀', 'income': 1},
                     **sell_extra)]}


def test_c4a_convert_key_review() -> None:
    """C4-a:转化分键豁免降级——失配产可疑项+按振荡判违。

    红证:复核分支拆除则「任意卖出挂四键」绕过 0 容忍(T-153 §1-C4
    攻击面)复现。
    """
    label, member = _locked_target()
    bad = _pair_row({'sell_reason': 'line_switch_collapse',
                     'dec_sell_in_line': False})
    bad['target_comp'] = label
    v = ledger.check_no_same_round_buy_sell([bad])
    assert len(v) == 2, v   # 可疑项 + 振荡判违(不豁免)
    assert '可疑项(转化分键失配)' in v[0] and '请裁决' in v[0]
    assert 'ADR-0267 买卖互斥违规' in v[1]
    ok = _pair_row({'sell_reason': 'line_switch_collapse',
                    'dec_sell_in_line': True})
    ok['target_comp'] = label
    assert ledger.check_no_same_round_buy_sell([ok]) == []
    # 旧账本无披露键:不可复核 → 豁免照旧(兼容)
    nokey = _pair_row({'sell_reason': 'line_switch_collapse'})
    nokey['target_comp'] = label
    assert ledger.check_no_same_round_buy_sell([nokey]) == []
    # 未锁线(target 空):名册不可解析 → 豁免照旧(seed18 p1r1 口径)
    unlocked = _pair_row({'sell_reason': 'line_switch_collapse',
                          'dec_sell_in_line': False})
    assert ledger.check_no_same_round_buy_sell([unlocked]) == []


def test_c4b_oscillation_mirror_review() -> None:
    """C4-b(XP 镜像):失配对计入 osc 且产可疑项;通过/无键照旧豁免。

    ADR-0611 按键分工(§3-5):自报分键载体改 convert_reason(结构化键);
    reason 载体上的转化值落 0 容忍格(无复核分支)——分工两态各锁。"""
    label, _ = _locked_target()
    bad = _pair_row({'convert_reason': 'funding_hold_liquidated',
                     'dec_sell_in_line': False})
    bad['target_comp'] = label
    bad['state']['level'] = 8   # osc*4=4 ≤ 0.3*need(lv8) 不触 XP 报警线,
    # 本锁只辖复核失配面(XP 报警线自身归既有锁辖,不重复断言)
    v = ledger.check_oscillation_xp_cap([bad])
    assert len(v) == 1 and '可疑项(转化分键失配)' in v[0]
    ok = _pair_row({'convert_reason': 'funding_hold_liquidated',
                    'dec_sell_in_line': True})
    ok['target_comp'] = label
    assert ledger.check_oscillation_xp_cap([ok]) == []
    # 错误载体(reason 带转化值)= 直接 0 容忍计违例,无复核分支
    #(lv3 缺省档:osc*4 > 0.3*need 报警线内,恰 1 条判违)。
    wrong = _pair_row({'sell_reason': 'funding_hold_liquidated',
                       'dec_sell_in_line': False})
    wrong['target_comp'] = label
    v_wrong = ledger.check_oscillation_xp_cap([wrong])
    assert len(v_wrong) == 1 and '可疑项' not in v_wrong[0], \
        'reason 载体转化值不得再入复核分支(按键分工)'


# ===== 检查器修复锁(L1/L2/L3/L5;语义单一源 = ADR-0593 后果.5) ==========

def test_l1_pure_copy_pair_reaches_review() -> None:
    """L1:纯「copy 买→同轮卖」对在检查器机械面可达复核。

    红证:恢复旧结构(copy 买不进 bought)则该对整体不可达——
    「三连豁免降级」申报对 copy 腿失效的落差复现。
    """
    single = [{'plane': 1, 'round_num': 3,
               'state': {'bench': [], 'deployed': []},
               'actions': [
                   {'__type__': 'BuyCard',
                    'card': {'name': '青雀', 'faction': '量子', 'cost': 1},
                    'reason': 'copy'},
                   {'__type__': 'SellBench', 'name': '青雀', 'income': 1}]}]
    v = ledger.check_no_same_round_buy_sell(single)
    assert len(v) == 2, v   # 可疑项(copy 失配)+ 判违
    assert '自报 copy' in v[0] and '请裁决' in v[0]
    # 收集语境成立(同轮同名 copy 买≥2)→ 豁免照旧
    collect = [{'plane': 1, 'round_num': 3,
                'state': {'bench': [], 'deployed': []},
                'actions': [
                    {'__type__': 'BuyCard',
                     'card': {'name': '青雀', 'faction': '量子', 'cost': 1},
                     'reason': 'copy'},
                    {'__type__': 'BuyCard',
                     'card': {'name': '青雀', 'faction': '量子', 'cost': 1},
                     'reason': 'copy'},
                    {'__type__': 'SellBench', 'name': '青雀', 'income': 1}]}]
    assert ledger.check_no_same_round_buy_sell(collect) == []


def test_l2_held_context_settles_on_sell() -> None:
    """L2:净持有销账——曾持有但中途已卖出者,其 copy 买不再有持有证据。

    探针场景(审查复现形):r1 买 X→r2 卖 X→r3 copy 买 X 同轮卖 X,
    购买时点净持有为空 → 必产可疑项+判违;修复前 checker 输出 []
    (终身持有通行证逃逸面)。
    """
    x = '青雀'
    rows = [
        {'plane': 1, 'round_num': 1, 'state': {'bench': [], 'deployed': []},
         'actions': [{'__type__': 'BuyCard',
                      'card': {'name': x, 'faction': '量子', 'cost': 1},
                      'reason': 'line'}]},
        {'plane': 1, 'round_num': 2, 'state': {'bench': [], 'deployed': []},
         'actions': [{'__type__': 'SellBench', 'name': x, 'income': 1}]},
        {'plane': 1, 'round_num': 3, 'state': {'bench': [], 'deployed': []},
         'actions': [
             {'__type__': 'BuyCard',
              'card': {'name': x, 'faction': '量子', 'cost': 1},
              'reason': 'copy'},
             {'__type__': 'SellBench', 'name': x, 'income': 1}]},
    ]
    v = ledger.check_no_same_round_buy_sell(rows)
    assert any('可疑项(同轮买卖分键失配)' in s and '自报 copy' in s
               for s in v), v
    assert any('ADR-0267 买卖互斥违规' in s for s in v)
    # D1 复盘面同判据:同场景产 D1 失配条目
    d1 = [e for e in suspects.run_suspect_checks(rows)
          if e.get('mode') == 'D1' and not e.get('cross_ref')]
    assert d1 and '自报 copy' in d1[0]['detail'], d1
    # 对照:持有未卖出(r2 不卖)→ copy 对豁免照旧
    rows_kept = [dict(rows[0]),
                 dict(rows[2], round_num=2)]
    assert ledger.check_no_same_round_buy_sell(rows_kept) == []


def test_l3_d5_window_uses_monotonic_axis() -> None:
    """L3:D5 窗口改行序单调轴——跨面紧邻不漏报、跨面远距不假阳。

    红证:恢复 round_num 差值算术则 p1r5买→p2r1卖(真实紧邻)0 命中、
    p1r3买→p2r5卖(实际隔 8 轮)假阳+错挂交叉引用。
    """
    seed = _engine_piece()

    def _row(plane: int, rn: int, act: list[dict]) -> dict:
        return {'plane': plane, 'round_num': rn, 'gold': 9,
                'state': {'board_factions': {}, 'bench': [],
                          'deployed': []},
                'sim': {'node': 'prep'}, 'actions': act}

    # 跨面紧邻:p1r5 买 → p2r1 卖(行序相邻,窗口内)
    near = [
        _row(1, 3, []),
        _row(1, 4, []),
        _row(1, 5, [{'__type__': 'BuyCard',
                     'card': {'name': seed, 'faction': '?', 'cost': 2},
                     'reason': 'other'}]),
        _row(2, 1, [{'__type__': 'SellBench', 'name': seed,
                     'income': 2}]),
        _row(2, 2, []),
    ]
    d5 = [e for e in suspects.run_suspect_checks(near)
          if e.get('mode') == 'D5' and not e.get('cross_ref')]
    assert len(d5) == 1 and d5[0]['round_num'] == 1, d5
    # 跨面远距:p1r3 买 → p2r5 卖(行序差 8,窗口外)
    far = [
        _row(1, 3, [{'__type__': 'BuyCard',
                     'card': {'name': seed, 'faction': '?', 'cost': 2},
                     'reason': 'other'}]),
        _row(1, 4, []),
        _row(1, 5, []),
        _row(2, 1, []),
        _row(2, 5, [{'__type__': 'SellBench', 'name': seed,
                     'income': 2}]),
    ]
    d5 = [e for e in suspects.run_suspect_checks(far)
          if e.get('mode') == 'D5' and not e.get('cross_ref')]
    assert d5 == [], d5


def test_l5_streak_suspect_stays_in_overflow_jurisdiction() -> None:
    """L5:C5-b 谎报条目辖域收溢金——非溢金轮只剥夺豁免不产条目。

    红证:恢复「formed_stop∧engines<2 即产条目」则金 30 + 有花费轮
    产出「金 30 零花费」双假文案条目(越辖+事实错误)。
    """
    lie_spend = {'plane': 1, 'round_num': 4, 'gold': 30,
                 'formed_stop': True,
                 'state': {'board_factions': {},
                           'deployed': [{'char_id': '桑博'}]},
                 'actions': [{'__type__': 'LevelUp', 'cost': 4}]}
    v = ledger.check_overflow_gold_zero_buy_streak([lie_spend])
    assert v == [], v   # 非溢金轮:无条目(streak 也因有花费不计数)
    # 溢金未泄辖域内谎报仍产条目(既有 test_c5b 覆盖,此处辖域对照)
    lie_overflow = dict(lie_spend, gold=60, actions=[])
    v = ledger.check_overflow_gold_zero_buy_streak(
        [lie_overflow, dict(lie_overflow, round_num=5)])
    assert sum('可疑项(成型谎报)' in s for s in v) == 2, v


# ===== C5 成型停手复核 ========================================================

def _overflow_rows(formed_stop: bool, factions: dict | None,
                   with_factions: bool = True) -> list[dict]:
    state: dict = {}
    if with_factions:
        state = {'board_factions': factions or {},
                 'deployed': [{'char_id': '桑博'}]}
    row = {'plane': 1, 'round_num': 4, 'gold': 60,
           'formed_stop': formed_stop, 'state': state,
           'sim': {'node': 'prep'}, 'actions': []}
    return [dict(row, round_num=r) for r in (4, 5)]


def test_c5b_overflow_streak_review() -> None:
    """C5-b:ADR-0343 豁免降级——成型谎报产可疑项且不断 streak。

    红证:恢复「自报即断 streak」则谎报轮静默豁免(连续零买窗被切断)。
    """
    formed = {'仙舟': 3, '列车同行': 2}
    v = ledger.check_overflow_gold_zero_buy_streak(
        _overflow_rows(True, formed))
    assert v == []   # 自洽停手:豁免照旧
    v = ledger.check_overflow_gold_zero_buy_streak(
        _overflow_rows(True, {}))
    assert len(v) == 3, v   # 两轮谎报可疑项 + streak 违规(不豁免)
    assert sum('可疑项(成型谎报)' in x for x in v) == 2
    assert any('溢出金断买 2 连' in x for x in v)
    # 旧账本无成型度键:不可复核 → 豁免照旧
    v = ledger.check_overflow_gold_zero_buy_streak(
        _overflow_rows(True, None, with_factions=False))
    assert v == []


# ===== C7 种子辖域复核 ========================================================

def test_c7_seed_scope_review() -> None:
    """C7:自报 engine_seed 辖域保留,叠加种子身份自算复核。

    红证:非引擎件改标 engine_seed 后回卖,恢复原样则只余振荡判违、
    身份失配不可见(改标攻击面,T-153 §1-C7)。
    """
    fake_seed, real_seed = _non_engine_piece(), _engine_piece()
    # 非引擎件冒充种子,跨轮回卖
    rows = [
        {'plane': 1, 'round_num': 2, 'gold': 9,
         'state': {'board_factions': {}, 'bench': [], 'deployed': []},
         'sim': {'node': 'prep'},
         'actions': [{'__type__': 'BuyCard',
                      'card': {'name': fake_seed, 'faction': '?',
                               'cost': 1},
                      'reason': 'engine_seed'}]},
        {'plane': 1, 'round_num': 4, 'gold': 9,
         'state': {'board_factions': {}, 'bench': [], 'deployed': []},
         'sim': {'node': 'prep'},
         'actions': [{'__type__': 'SellBench', 'name': fake_seed,
                      'income': 1}]},
    ]
    v = check_engine_seed_not_resold(rows)
    assert any('可疑项(种子身份失配)' in x for x in v), v
    assert any('≤2 轮内回卖' in x for x in v)
    # 真种子(引擎件∧未持有):判违照旧,无身份可疑项
    rows_ok = [
        {'plane': 1, 'round_num': 2, 'gold': 9,
         'state': {'board_factions': {}, 'bench': [], 'deployed': []},
         'sim': {'node': 'prep'},
         'actions': [{'__type__': 'BuyCard',
                      'card': {'name': real_seed, 'faction': '?',
                               'cost': 2},
                      'reason': 'engine_seed'}]},
        {'plane': 1, 'round_num': 4, 'gold': 9,
         'state': {'board_factions': {}, 'bench': [], 'deployed': []},
         'sim': {'node': 'prep'},
         'actions': [{'__type__': 'SellBench', 'name': real_seed,
                      'income': 2}]},
    ]
    v = check_engine_seed_not_resold(rows_ok)
    assert v and all('可疑项' not in x for x in v), v
    # 探针(C7-b):同轮单张冒充种子卖回 → 身份可疑项 + 振荡
    same = [{'plane': 1, 'round_num': 2,
             'state': {'board_factions': {}, 'bench': [], 'deployed': []},
             'actions': [
                 {'__type__': 'BuyCard',
                  'card': {'name': fake_seed, 'faction': '?', 'cost': 1},
                  'reason': 'engine_seed'},
                 {'__type__': 'SellBench', 'name': fake_seed,
                  'income': 1}]}]
    v = check_engine_seed_sell_exemption(same)
    assert any('可疑项(种子身份失配)' in x for x in v), v


# ===== 生成侧披露三键(engine_p1 执行点;供给半环,README 纪律 13) ==========

def test_disclosure_keys_write_end_seed18() -> None:
    """三披露键写端在位锁(探针 seed 18;写端断线 = 检查器/检测器静默
    退回不可复核,失配显形能力归零)。键形状:BuyCard= int 成型度,
    LevelUp/SellBench= bool。发射面为零的种子 = 探针失准,红须指向
    重选探针种子(README 纪律 12)。"""
    rows = [dict(r) for r in _seed18_ledger()]
    buys = [a for row in rows for a in (row.get('actions') or [])
            if a.get('__type__') == 'BuyCard']
    lvs = [a for row in rows for a in (row.get('actions') or [])
           if a.get('__type__') == 'LevelUp']
    sells = [a for row in rows for a in (row.get('actions') or [])
             if a.get('__type__') == 'SellBench']
    assert buys and lvs and sells, \
        f'探针种子三动作面不全(buys={len(buys)} lv={len(lvs)} ' \
        f'sells={len(sells)}),重选探针种子'
    for a in buys:
        assert isinstance(a.get('dec_engines_count'), int), a
    for a in lvs:
        assert isinstance(a.get('dec_board_full'), bool) \
            and isinstance(a.get('dec_bench_wait_member'), bool), a
    for a in sells:
        assert isinstance(a.get('dec_sell_in_line'), bool), a


def test_seed18_t141_exemption_holds_under_review() -> None:
    """seed18 端到端:T-141 豁免在复核新机制下仍工作(未锁线期孤儿
    清算 = 名册不可解析 → unverifiable → 豁免照旧,ADR-0591 语义
    不被迁移翻案)。红证:把该行语境改造成可解析名册并保留键 False
    (人为失配)→ 可疑项 + 判违产出(检查端复核确实在岗)。"""
    rows = _seed18_ledger()
    p1r1 = [dict(r) for r in rows
            if r.get('plane') == 1 and r.get('round_num') == 1]
    assert ledger.check_no_same_round_buy_sell(p1r1) == []
    # 检测器面同样不产 D1 失配条目(复核同判据,单一源)
    d1 = [e for e in suspects.run_suspect_checks(list(rows))
          if e.get('mode') == 'D1' and e.get('round_num') == 1
          and not e.get('cross_ref')]
    assert d1 == [], d1
    # 人为失配(红证):语境改成可解析名册,dec 键仍 False → 显形
    label, _ = _locked_target()
    forged = [dict(r, target_comp=label) for r in p1r1]
    v = ledger.check_no_same_round_buy_sell(forged)
    assert any('可疑项(转化分键失配)' in x for x in v), v


# ===== 检测器集 ===============================================================

def test_detector_registry_shape() -> None:
    """登记门:D1-D11 全在册;条目形状含模式定位与裁决问句。"""
    assert suspects.detector_ids() == \
        [f'D{i}' for i in range(1, 12)]
    rows = [
        {'plane': 1, 'round_num': 4, 'gold': 60, 'formed_stop': True,
         'state': {'board_factions': {}, 'deployed': [{'char_id': '桑博'}]},
         'sim': {'node': 'prep'}, 'actions': []},
    ]
    entries = suspects.run_suspect_checks(rows)
    assert entries, '谎报停手局应至少命中 D2'
    for e in entries:
        if e.get('mode') == '_errors':
            continue
        assert {'mode', 'mode_name', 'plane', 'round_num',
                'node', 'detail'} <= set(e), e
        assert '请裁决' in e['detail'], e


def test_d5_selfcalc_scope_and_cross_ref() -> None:
    """D5:自算种子辖域(不依赖自报分键)回卖命中 + 买入轮交叉引用行。

    红证:改标(reason='other')的种子买入回卖,自报辖域检查器
    (check_engine_seed_not_resold)对其失明,D5 仍命中——辖域自算
    即迁移点(C7 的检测器补位面)。"""
    seed = _engine_piece()
    rows = [
        {'plane': 1, 'round_num': 2, 'gold': 9,
         'state': {'board_factions': {}, 'bench': [], 'deployed': []},
         'sim': {'node': 'prep'},
         'actions': [{'__type__': 'BuyCard',
                      'card': {'name': seed, 'faction': '?', 'cost': 2},
                      'reason': 'other'}]},   # 改标:不自称 engine_seed
        {'plane': 1, 'round_num': 4, 'gold': 9,
         'state': {'board_factions': {}, 'bench': [], 'deployed': []},
         'sim': {'node': 'prep'},
         'actions': [{'__type__': 'SellBench', 'name': seed,
                      'income': 2}]},
    ]
    assert check_engine_seed_not_resold(rows) == []   # 自报辖域失明
    entries = [e for e in suspects.run_suspect_checks(rows)
               if e.get('mode') == 'D5']
    full = [e for e in entries if not e.get('cross_ref')]
    xref = [e for e in entries if e.get('cross_ref')]
    assert len(full) == 1 and full[0]['round_num'] == 4, entries
    assert len(xref) == 1 and xref[0]['round_num'] == 2 \
        and xref[0]['anchor_round'] == 4, entries


# ===== 复盘骨架生成器 =========================================================

def _load_tool():
    spec = importlib.util.spec_from_file_location('cw_review_skeleton', _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # type: ignore[union-attr]
    return mod


def test_review_skeleton_prefill_in_node_before_slots() -> None:
    """骨架输出锁:可疑项挂对应节点小节、位次 = 判定三槽前;禁独立附录。

    红证:附录化渲染(把条目汇成文末清单)或三槽前置违反用户裁定
    (T-153 §4.2 禁止形态),本锁直接红。
    """
    mod = _load_tool()
    seed = _engine_piece()
    rows = [
        {'plane': 1, 'round_num': 3, 'gold': 40, 'hp': 70,
         'state': {'level': 5, 'bench': [], 'deployed': []},
         'sim': {'node': 'prep'},
         'actions': [{'__type__': 'BuyCard',
                      'card': {'name': seed, 'faction': '?', 'cost': 2},
                      'reason': 'other'}]},
        {'plane': 1, 'round_num': 4, 'gold': 60, 'hp': 70,
         'formed_stop': True,
         'state': {'level': 5, 'board_factions': {},
                   'deployed': [{'char_id': '桑博'}], 'bench': []},
         'sim': {'node': 'prep'}, 'actions': []},
        {'plane': 1, 'round_num': 5, 'gold': 30, 'hp': 70,
         'state': {'level': 5, 'bench': [], 'deployed': []},
         'sim': {'node': 'battle'}, 'actions': []},
    ]
    entries = suspects.run_suspect_checks(rows)
    md = mod.render_skeleton(rows, entries, '测试合成局')
    # 结构:每个节点小节存在;可疑项块在 r4 小节内且位于判定三槽之前
    assert '### P1·R3' in md and '### P1·R4' in md and '### P1·R5' in md
    r4 = md.split('### P1·R4')[1].split('### P1·R5')[0]
    assert '可疑项' in r4 and '判定三槽' in r4
    assert r4.index('可疑项预填') < r4.index('判定三槽'), '预填必须在三槽前'
    # r3 买入轮:必有 D5 交叉引用行(姬子 r5 无卖,r3 只有买入 → 无全条目);
    # 无命中小节显式标注(非静默)
    r3 = md.split('### P1·R3')[1].split('### P1·R4')[0]
    assert '本节点无检测器命中条目' in r3
    r5 = md.split('### P1·R5')[1]
    assert '本节点无检测器命中条目' in r5
    # 禁独立附录:文末不得出现条目清单节(候选修复项为协议自有空节,辖外)
    tail = md.split('## 候选修复项')[0]
    assert tail.count('可疑项(') == sum(
        1 for e in entries if e.get('round_num') in (3, 4, 5)
        and not e.get('cross_ref') and e.get('mode') != '_errors')


def test_merge_round_rows_carries_sells_for_detectors() -> None:
    """生产接线锁(README 纪律 13 供给半环):合并行动作并集含 SellBench
    ——D1/D5 检测器生产覆盖面的数据地基(生产卖出行缺 name/sell_reason
    键,检测器按缺键跳过 = 声明缺口,不炸面)。"""
    from sr_od.application.currency_war.sim.ledger_hooks import (
        merge_round_rows,
    )
    frames = [
        {'plane': 1, 'round_num': 2, 'ts': 't1', 'gold': 30, 'hp': 80,
         'formed_stop': False, 'target_comp': '',
         'state': {'board': {}, 'deployed': [], 'bench': [],
                   'node_type': 'prep'},
         'actions': [{'__type__': 'BuyCard', 'card': {'name': '青雀'},
                      'reason': 'm2_line_member'}]},
        {'plane': 1, 'round_num': 2, 'ts': 't2', 'gold': 28, 'hp': 80,
         'formed_stop': False, 'target_comp': '',
         'state': {'board': {}, 'deployed': [], 'bench': [],
                   'node_type': 'prep'},
         'actions': [{'__type__': 'SellBench', 'slot': 3}]},
    ]
    merged = merge_round_rows(frames)
    assert len(merged) == 1
    types = [a.get('__type__') for a in merged[0]['actions']]
    assert types == ['BuyCard', 'SellBench'], types
    # 段级消费面不因并入翻转:_seg_spent 白名单不含 SellBench
    assert merged[0]['actions'][1].get('name') is None   # 缺键如实保留


# ===== 生产行为守卫(决策路径零变化) ==========================================

def test_no_decision_path_reads_disclosure_keys() -> None:
    """grep 守卫:criteria/sell_gate/mandate 发射判定不读新披露键
    (T-153 硬约束;披露键只进检查/检测/复盘面,策略读自身披露 =
    新自证循环)。扫描面 = mandate_v1 全包(含 criteria/ 与 sell_gate)。
    盲区自检(README 纪律 20):扫描路径失效(包搬走/零文件)必须红,
    禁静默假绿。"""
    root = Path(r'src/sr_od/application/currency_war/strategies/impl/mandate_v1')
    scanned = sorted(root.rglob('*.py'))
    names = {p.name for p in scanned}
    assert 'sell_gate.py' in names and 'shop.py' in names \
        and 'mandate.py' in names, \
        f'扫描面失真(守卫哑火风险): {sorted(names)[:5]}'
    keys = ('dec_sell_in_line', 'dec_engines_count',
            'dec_bench_wait_member')
    hits: list[str] = []
    for py in scanned:
        text = py.read_text(encoding='utf-8')
        for k in keys:
            if k in text:
                hits.append(f'{py}: {k}')
    assert not hits, f'决策面读披露键(新自证循环): {hits}'
