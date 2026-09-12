"""W5 透传域建模收编回归锁(方案正本 = changes/2026-09-06-redesign/
w5-透传域建模方案.md;锁定面 = §2 改动设计逐域 + hp 专项等价证明 + 双
ShopCard 类型去重 + sim 合成口扩域 + 写入口锚扩面)。

锁族对应(方案 §2.6 测试锁族):
- 逐域行为锁:回放语料形态(合成真值帧)逐位等价 + 失读帧构造定向用例;
- hp 专项对拍:视图真值 + 消费侧施门 == 旧链门后值(等价三支实证),
  gap==1 / gap∈2..3 / gap>3 三窗 + 结算覆盖邻接帧 + encounter 读点域;
- 类型去重:映射单一源往返 + kernel 旧类型引用静态锁(精确辖域);
- payload 域离屏语义锁 + 开店态失读「陈旧牌面」申报行为锁;
- D1 锚扩面:新写点全走写入口 API(spec 门不加无效键一并锁定)。
"""
from __future__ import annotations

import inspect
import re
from types import SimpleNamespace
from typing import Any

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    GameState,
    bench_slots_to_legacy,
    board_state_of,
    deployed_rows_from_obs,
    shop_card_to_container,
    shop_cards_to_legacy,
    synthesize_from_game_state,
    unit_rows_to_deployed,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_game_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    register_sig_actors as _register_sig_actors,
)

# (game_state_view 视图锁族 7 锁已随 kernel/cw_bs_view 文件退役同批删除
#  ——波 5b 双删,锁与所辖面同批退役;apply_settlement_cover 消费锁同批。)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    CwWorkFrame,
)
from sr_od.application.currency_war.obs import cw_observation as cobs

_register_sig_actors('TestSigWriter')


def _sig() -> _ChannelSig:
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _hsig() -> _ChannelSig:
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')


def _mk_legacy_card(x: int, name: str, *, cost: int = 1, star: int = 1,
                    faction: str = '仙舟',
                    cost_source: str = 'badge', merge_preview: int = 0):
    from sr_od.application.currency_war.kernel.cw_vocab import ShopCard
    return ShopCard(x=x, faction=faction, name=name, cost=cost, star=star,
                    merge_preview=merge_preview, cost_source=cost_source)


# ============================================================ 逐域行为锁:常态帧逐位等价

def _full_truth_frame() -> CwWorkFrame:
    """回放语料形态的真值帧(全域可读,无失读)。"""
    st = CwWorkFrame()
    st.plane, st.round_num, st.node_type = 1, 4, 'battle'
    st.gold, st.gold_readable = 37, True
    st.level, st.xp_progress, st.streak = 5, (2, 8), 3
    st.hp, st.hp_readable, st.hp_trusted = 82, True, True
    st.deploy_cap = 6
    st.board = {'仙舟': 2}
    st.active_env = '昼之半神概念股'
    st.plane_bosses = ['镜流', None, '卡芙卡']
    st.enemy_affixes = ['迅捷']
    st.equips = ['星币收集器', '旧世仁医']
    st.active_strategies = ['白银投资']
    st.selected_difficulty = 'A8'
    st.shop = [_mk_legacy_card(300, '希儿'), _mk_legacy_card(500, '景元',
                                                            cost=4)]
    st.refresh_probs = {1: 0.6, 2: 0.22}
    st.bench = [BenchChar(slot=1, char_id='花火', star=2, faction='仙舟'),
                None, BenchChar(slot=3, char_id='佩佩', star=1,
                                faction='贝洛伯格')] + [None] * 6
    st.deployed = [BenchChar(slot=1, char_id='希儿', star=1, faction='仙舟',
                             position_pref='front'),
                   None, None, None,
                   BenchChar(slot=1, char_id='景元', star=1, faction='仙舟',
                             position_pref='back'),
                   None, None, None, None, None]
    return st


def test_deployed_rows_from_obs_splits_rows_and_guards_empty() -> None:
    """SIFT 读链 → (front_row, back_row):分排按 position_pref、行内 1 基
    slot 直传;空集/全无身份 = 失读返 None(P2-1 同款守卫,禁「全场无人」
    假观察)。"""
    assert deployed_rows_from_obs([]) is None
    assert deployed_rows_from_obs([BenchChar(slot=0, char_id='')]) is None
    front, back = deployed_rows_from_obs([
        BenchChar(slot=2, char_id='希儿', star=2, position_pref='front'),
        BenchChar(slot=1, char_id='景元', star=1, position_pref='back'),
        BenchChar(slot=3, char_id='花火', star=1, position_pref='back'),
    ])
    assert [(u.char_id, u.slot) for u in front] == [('希儿', 2)]
    assert [(u.char_id, u.slot) for u in back] == [('景元', 1), ('花火', 3)]


def test_unit_rows_to_deployed_rebuilds_legacy_slot_table() -> None:
    """容器席位 → 旧定长槽表(ADR-0392 0 基 0-3 前/4-9 后):视图收编后
    消费形状零变化(None 填充,行内 1 基 slot = 旧下标换算)。"""
    front, back = deployed_rows_from_obs([
        BenchChar(slot=2, char_id='希儿', star=2, position_pref='front'),
        BenchChar(slot=1, char_id='景元', star=1, position_pref='back'),
    ])
    table = unit_rows_to_deployed(front, back)
    assert len(table) == 10
    assert table[1] is not None and table[1].char_id == '希儿' \
        and table[1].position_pref == 'front'
    assert table[4] is not None and table[4].char_id == '景元' \
        and table[4].position_pref == 'back'
    assert all(table[i] is None for i in (0, 2, 3, 5, 6, 7, 8, 9))


def test_bench_slots_to_legacy_derives_faction_from_registry() -> None:
    """BenchView → 旧槽表:阵营不入容器(§3.2.3),查角色注册表派生
    (识别链同源 get_char);槽位两端同构 1:1。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        bench_view_of_slots,
    )
    view = bench_view_of_slots([BenchChar(slot=1, char_id='花火', star=2),
                                None])
    table = bench_slots_to_legacy(view)
    assert table[0] is not None and table[0].char_id == '花火' \
        and table[0].star == 2 and table[0].slot == 1
    assert table[0].faction != '?', '阵营自注册表派生(非容器存储)'
    assert table[1] is None and len(table) == 9


# ============================================================ deploy_cap / equips 喂入口

def test_feed_deploy_cap_observes_truth_and_carries_rejection(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """deploy_cap 观察写端(§2.3 入容器):采信门输出(非 None)observe;
    拒信/失读帧(None)carry 沿用——禁拿兜底当观察。"""
    sess = SimpleNamespace()
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
    bs = board_state_of(sess)
    st = CwWorkFrame()
    st.plane, st.round_num = 1, 3
    st.deploy_cap = 6
    cobs._feed_board_state(ctx, st, cobs.PHASE_PREP_CLEAN, None,
                           frozenset({'deploy_cap'}), had_hp_real=False)
    assert bs.deploy_cap.value == 6 and bs.deploy_cap.source == 'observation'
    st2 = CwWorkFrame()
    st2.plane, st2.round_num = 1, 3
    st2.deploy_cap = None   # 域外拒信/失读形态
    cobs._feed_board_state(ctx, st2, cobs.PHASE_PREP_CLEAN, None,
                           frozenset({'deploy_cap'}), had_hp_real=False)
    assert bs.deploy_cap.value == 6 and bs.deploy_cap.source == 'carried'
    # spec 无键阶段(prep_shop_open)根本没读 → 不写(诚实缺位不沿用)
    st3 = CwWorkFrame()
    st3.plane, st3.round_num = 1, 3
    st3.deploy_cap = 9   # 未读帧的杂值禁入记录
    cobs._feed_board_state(ctx, st3, cobs.PHASE_PREP_SHOP_OPEN, None,
                           frozenset(set()), had_hp_real=False)
    assert bs.deploy_cap.value == 6, 'spec 无 deploy_cap 键的帧不写'


def test_feed_equips_relay_from_session_mirror_when_never_written() -> None:
    """equips 载体中继兜底(§2.2):从未写过 → relay 自 session 镜像
    (source=logic + evidence=session_carrier);接线滞后窗值冻结申报见
    喂入口 equips 段注释(观察写端 = 装备分配链现读)。"""
    sess = SimpleNamespace(last_owned_equips=['星币收集器'])
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
    bs = board_state_of(sess)
    st = CwWorkFrame()
    st.plane, st.round_num = 2, 1
    cobs._feed_board_state(ctx, st, cobs.PHASE_PREP_CLEAN, None,
                           frozenset(), had_hp_real=False)
    assert bs.equips.value == ['星币收集器']
    assert bs.equips.source == 'logic' and bs.equips.evidence == 'session_carrier'


def test_sim_synth_writes_w5_domains() -> None:
    """sim 合成口扩域(§2.6:合成口与实机喂入口域覆盖集对齐):八新域
    (plane_bosses/enemy_affixes/active_env/equips/front_row/back_row/
    deploy_cap + back_max 语义裁决增补的 back_layout)真值直写
    observation + evidence=sim:synthesized;缺席域不写(禁假值)。"""
    st = _full_truth_frame()
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    synthesize_from_game_state(bs, st, at_round='p1-r4')
    assert bs.deploy_cap.value == 6
    assert bs.back_layout.value == 6, \
        'back_layout 增补域:CwWorkFrame.back_max 真值直写(sim 场景侧设定)'
    assert bs.plane_bosses.value == ['镜流', None, '卡芙卡']
    assert bs.enemy_affixes.value == ['迅捷']
    assert bs.active_env.value == '昼之半神概念股'
    assert bs.equips.value == ['星币收集器', '旧世仁医']
    assert [u.char_id for u in bs.front_row.value] == ['希儿']
    assert [u.char_id for u in bs.back_row.value] == ['景元']
    assert bs.front_row.value[0].slot == 1 and bs.back_row.value[0].slot == 1, \
        'Unit.slot = 行内 1 基(前排 1..4/后排 1..N)'
    assert all('sim:synthesized' in (f.evidence or '')
               for f in (bs.deploy_cap, bs.back_layout, bs.plane_bosses,
                         bs.enemy_affixes, bs.active_env, bs.equips,
                         bs.front_row, bs.back_row))


# ============================================================ hp 专项对拍(等价三支实证)

def _session_with_settlement(last_hp: int | None, last_t: int | None,
                             last_node: int | None = None) -> Any:
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )
    sess = StrategySession()
    sess.last_hp = last_hp
    sess.last_hp_t = last_t
    sess.last_hp_real = last_hp
    sess.last_hp_real_node = last_node
    return sess


def _bs_hp_from_frame(frame_hp: int | None, *, readable: bool,
                      source: str) -> GameState:
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    if frame_hp is not None:
        if source == 'observation':
            bs.observe(bs.hp, frame_hp, sig=_sig())
        elif source == 'carried':
            bs.observe(bs.hp, frame_hp, sig=_sig())
            bs.carry(bs.hp, frame='p1-r3', sig=_sig())   # 值保持,来源翻沿用
        elif source == 'prior':
            bs.write_prior(bs.hp, frame_hp, evidence='prior:adr-0559',
                           sig=_sig())
    return bs


def test_hp_gate_equivalence_three_windows() -> None:
    """等价证明实证面(方案 §2.4):新链 gated_hp(容器真值, 视图 readable)
    与旧链语义在三窗逐位一致——①gap==1 真读帧:结算真值覆盖;②gap∈2..3
    失读帧:放宽窗覆盖;③gap>3:保持现值。窗界外/窗界内均与旧链门输出
    相同(门本体与 session 锚不动)。"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        gated_hp,
    )

    def _old_chain(frame_hp: int, readable: bool, gap: int) -> int | None:
        # 旧链 = 门后帧值再过消费门(幂等):等价于对门后值单次施门
        sess = _session_with_settlement(40, 10 - gap, 10 - gap)
        t = 10
        return gated_hp(gated_hp(frame_hp, sess, t, current_readable=readable),
                        sess, t, current_readable=readable)

    def _new_chain(truth: int, readable: bool, gap: int) -> int | None:
        sess = _session_with_settlement(40, 10 - gap, 10 - gap)
        return gated_hp(truth, sess, 10, current_readable=readable)

    for gap, readable in ((1, True), (2, False), (3, False), (4, False),
                          (2, True), (4, True)):
        assert _new_chain(75, readable, gap) == _old_chain(75, readable, gap), \
            f'gap={gap} readable={readable} 窗:新链 == 旧链(门幂等+同源)'


def test_encounter_read_point_gates_view_truth() -> None:
    """encounter λ 键读点施门(W5 读点清单点名域):decide_encounter_ev
    入口对 state.hp 施新鲜度门——视图真值 + 视图 readable 单一源;
    session 无结算锚时恒等返回(旧行为,纯函数可单测)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        encounter as enc,
    )
    st = CwWorkFrame(hp=75, plane=1, round_num=4)
    st.hp_readable = True
    # 无锚:恒等(同对象),旧测试零波及
    assert enc._hp_gate_state(st, _session_with_settlement(None, None)) is st
    # gap==1 锚 + 真读:结算真值覆盖(门辖域)
    gated = enc._hp_gate_state(st, _session_with_settlement(40, 3, 3))
    assert gated is not None and gated.hp == 40 and st.hp == 75, \
        '门输出落副本(入参 state 不可变);λ 键 hp 维 = 门后值'
    # 决策入口接线:monkeypatch 侦 _branch_lambda_label 收到的 state = 门后
    from sr_od.application.currency_war.kernel.cw_events import EncounterOption
    captured: list[CwWorkFrame] = []

    def _spy(option, state):
        captured.append(state)
        return None, None

    orig = enc._branch_lambda_label
    enc._branch_lambda_label = _spy
    try:
        enc.decide_encounter_ev(
            [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
             EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])],
            st, _session_with_settlement(40, 3, 3))
    finally:
        enc._branch_lambda_label = orig
    assert captured and captured[0].hp == 40, \
        'decide_encounter_ev 消费的是施门后 state(读点域接线在位)'


def test_adapter_decision_seams_retired_tombstone() -> None:
    """T-116 段2 退役墓碑(原 readable 单一源锁+back_max 闸门三锁收口):
    adapter 缝(decision_state/_anchor_state)已随 T-116 段 2 退役删除
    (snapshot_from_obs 纯容器锚),符号复活即红。原两锁的断言面随之
    消亡:decision back_max 供数单一源 = 容器 back_capacity_of(无 adapter
    触点);Snapshot/PrepObservation back_size 死字段墓碑与 adapter 源
    扫描归 test_cw_w5_sim_retirement 哨兵(波 5b)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        adapter as _adapter,
    )
    assert not hasattr(_adapter, 'decision_state'), \
        'adapter.decision_state 应已删除(T-116 段 2 缝收敛)'
    assert not hasattr(_adapter, '_anchor_state'), \
        'adapter._anchor_state 应已删除(T-116 段 2 缝收敛)'


def test_adapter_decision_state_back_max_from_container() -> None:
    """闸门三语义归宿注(原锁收口):decision back_max 供数单一源 =
    容器 back_capacity_of——T-116 段 2 删 adapter.decision_state 缝后
    本锁断言面消亡,语义守护迁 test_cw_w5_sim_retirement 哨兵
    (Snapshot/PrepObservation back_size 死字段墓碑 + src 零回写扫描,
    波 5b 版本演进移除 T-23-r1 §⑤.2)。本位保留符号墓碑防缝复活。"""
    import dataclasses as _dc

    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        adapter as _adapter,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.contracts import (
        Snapshot,
    )
    assert not hasattr(_adapter, 'decision_state')
    assert 'back_size' not in {f.name for f in _dc.fields(Snapshot)}, \
        'Snapshot.back_size 死字段应已移除(波 5b 版本演进收口)'


def test_posture_flip_guard_predicate_unchanged_on_view_outputs() -> None:
    """posture flip_hit 假帧守卫既有锁继续辖(容器可信位):
    沿用帧(carried)守卫仍放行;先验帧(prior)仍拒——谓词口径零改
    (方案 §2.4 等价验证申报面;波 2 起谓词 = 容器形态单一源
    hp_decision_trusted_of)。"""
    from sr_od.application.currency_war.kernel.cw_discipline_rules import (
        hp_decision_trusted,
    )

    bs_carry = _bs_hp_from_frame(80, readable=False, source='carried')
    assert hp_decision_trusted(bs_carry) is True
    bs_prior = _bs_hp_from_frame(82, readable=False, source='prior')
    assert hp_decision_trusted(bs_prior) is False


# ============================================================ 类型去重(双 ShopCard 归一)

def test_shop_card_mapping_roundtrip_and_frame_alignment() -> None:
    """映射单一源往返:旧→容器保五记录字段;容器→旧 x/merge_preview 同帧
    对齐透传,失配窗置 0(执行/读取器域引导窗,申报见映射函数)。"""
    legacy = _mk_legacy_card(300, '希儿', cost=1, star=2,
                             cost_source='roster_fallback',
                             merge_preview=2)
    container = shop_card_to_container(legacy)
    assert (container.name, container.faction, container.cost,
            container.star, container.cost_source) == \
        ('希儿', '仙舟', 1, 2, 'roster_fallback'), \
        '五记录字段原值透传不折叠(cost_source 证据分级禁丢)'
    assert not hasattr(container, 'x') and not hasattr(container,
                                                       'merge_preview')
    back = shop_cards_to_legacy([container], frame_cards=[legacy])
    assert (back[0].x, back[0].merge_preview) == (300, 2), '同帧下标对齐'
    back_misaligned = shop_cards_to_legacy([container],
                                           frame_cards=[legacy, legacy])
    assert (back_misaligned[0].x, back_misaligned[0].merge_preview) == (0, 0), \
        '长度失配 = 失配窗置缺省(禁错位对齐)'


def test_kernel_legacy_shopcard_reference_static_lock() -> None:
    """kernel 内零旧 ShopCard 引用静态锁(方案 §2.6④,精确辖域):豁免 =
    ①cw_state.py(本体,旧类型唯一居所)②cw_game_state.shop_cards_to_legacy
    (映射函数单一源)③cw_merge_simulate.py / cw_economy.py 的 TYPE_CHECKING
    旧类型注解行(候裁9 迁移:两文件自 cw_state 迁入的函数自带旧类型签名
    注解,随旧工作帧世界退役消亡;非映射函数外的新消费,运行时零依赖);
    其余 kernel 旧类型引用 = 红。"""
    from pathlib import Path
    kernel = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
              / 'currency_war' / 'kernel')
    assert (kernel / 'cw_state.py').is_file(), '扫描根失准'
    pat = re.compile(r'cw_state\s+import\s+[^#\n)]*\bShopCard\b'
                     r'|cw_state\.ShopCard')
    # 迁入函数的 TYPE_CHECKING 注解行豁免(候裁9 迁移伴随注解,见 docstring ③)
    migrated_annotation = re.compile(
        r'^\s*from\s+\S*kernel\.cw_state\s+import\s+ShopCard\s*\n', re.M)
    annotation_exempt = {'cw_merge_simulate.py', 'cw_economy.py'}
    offenders: dict[str, str] = {}
    for path in sorted(kernel.glob('*.py')):
        if path.name == 'cw_state.py':
            continue
        text = path.read_text(encoding='utf-8')
        if path.name in annotation_exempt:
            text = migrated_annotation.sub('', text)
        if path.name == 'cw_game_state.py':
            # 豁免面 = 映射函数本体(单一源);函数外残留 = 红
            import sr_od.application.currency_war.kernel.cw_game_state as _m
            text = text.replace(inspect.getsource(_m.shop_cards_to_legacy), '')
        for m in pat.finditer(text):
            offenders[f'{path.name}:{m.group(0)}'] = m.group(0)
    assert not offenders, (
        f'kernel 出现映射函数外的旧容器 ShopCard 引用(双 ShopCard 归一,'
        f'转换只许在映射函数发生):{offenders}')
    # 变异自检:判据对真实旧引用形态有捕获力
    assert pat.search('from a.b.cw_state import ShopCard')
    assert pat.search('cw_state.ShopCard(x=0)')


# ============================================================ D1 锚扩面(写入口在位)

def test_w5_write_points_anchor_via_entry_api() -> None:
    """D1 锚扩面:新写点(deploy_cap 喂入/deployed 席位喂入/equips 观察
    + 中继)全部以写入口 API 形态在位(observe/carry/relay),禁直摸
    Field(旁路形态另由 test_cw_state_write_discipline grep 锁辖)。"""
    import sr_od.application.currency_war.obs.cw_observation as _obs
    feed_src = inspect.getsource(_obs._feed_board_state)
    assert 'bs.observe(bs.deploy_cap' in feed_src \
        and 'bs.carry(bs.deploy_cap' in feed_src, 'deploy_cap 喂入锚'
    assert 'bs.relay(bs.equips' in feed_src, 'equips 中继锚'
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep,
    )
    prep_src = inspect.getsource(cw_screen_prep)
    assert 'bs.observe(_bs_obs.front_row' in prep_src \
        and 'bs.observe(_bs_obs.back_row' in prep_src, 'deployed 席位喂入锚'
    assert 'deployed_rows_from_obs' in prep_src, '空集守卫构造源在位'
    import sr_od.application.currency_war.prep_actions as _pa
    pa_src = inspect.getsource(_pa)
    assert pa_src.count('_bs_eq.observe(_bs_eq.equips') == 2, \
        'equips 观察写端两分支(M7 + 回退)同点在位'


def test_phase_field_spec_no_invalid_keys_added() -> None:
    """spec 门申报修正(对抗审 v2 发现 5 定谳形态):席位域不经漏斗读,
    PHASE_FIELD_SPEC 不加 bench/deployed/equips 键;deploy_cap 键已在册
    (容器喂入沿用既有键门)。"""
    assert 'deploy_cap' in cobs.PHASE_FIELD_SPEC[cobs.PHASE_PREP_CLEAN]
    for phase, keys in cobs.PHASE_FIELD_SPEC.items():
        assert not ({'bench', 'deployed', 'equips'} & keys), \
            f'{phase}: 席位域键不得入 spec(不经漏斗读,防无效键复活)'


# ============================================================ 调用点基线(批首 grep 口径)

def test_strategy_input_state_call_sites_baseline() -> None:
    """退役落地锁(原孤儿态钉零锁收口):波 5b 双删后 cw_bs_view 模块本体
    已删除,src 树内 ``strategy_input_state(`` 直调恒 0——任何复活调用点
    (新取帧点误接已退役视图口)即本锁红,防退役后静默回流。"""
    from pathlib import Path
    root = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
            / 'currency_war')
    assert not (root / 'kernel' / 'cw_bs_view.py').exists(), \
        'cw_bs_view.py 应已物理删除(波 5b 双删)'
    hits: list[str] = []
    for path in root.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        hits += [f'{path.relative_to(root)}:{m.start()}'
                 for m in re.finditer(r'strategy_input_state\(', text)]
    assert not hits, f'退役面被破坏(strategy_input_state 直调复活):{hits}'
