"""统一 state 派生规则 R1.2 扩展锁面(规则②位面过渡腿 + 规则③BOSS 简报腿
+ 类型派生 + chain_node_type 接口预留)。

设计正本 = ``.debug/temp/currency_war/流程侧遥测-设计v3.4.md`` §3.4.1
(四规则组终版,用户 2026-09-10 终裁;R1.2 实现的正本指针 = 该节):
- 规则②:0q 位面过渡被采到 → 逻辑节点 = (当前位面+1, 1),经节点序坐标系
  公式落单整数写入 ``node_ord``;过渡屏链 = 离开位面链(件 B 设计 v1.1
  F1 定谳)→ 零类型写;
- 规则③:0p BOSS 简报被采到 → 逻辑节点 = 当前节点 + 1,类型 = BOSS 随简报
  证据自带(**禁写死 round=9**——boss 序位随位面格数/环境加节点漂移);
- 类型派生:专属画面现身即定类型(补给→supply/遭遇→encounter/策略→invest/
  0p→boss);商店面板不专属 → 类型「未定型」零写,查现行链接口
  :func:`chain_node_type` 按件 B 设计 v1.1 §3.4/§3.8 语义预留(查链接线候
  件 B 实施批);类型冲突 → obs_event 留证禁静默(同 G10 纪律,最新直定赢);
- 共同语义:候选 ≤ hist 不写不锚(去重键 =(run_id, effective_ord),同序恰
  一次推进);固定次序 = 节点域判定 → 类型派生(同临界区,无 hook 框架)。

本文件锁与 test_cw_state_journal.py 的双腿锁(规则①④)同簇互补。
测试隔离:journal sink 经 fixture 安装/复位;run_id 经 monkeypatch 桩化。
"""
from __future__ import annotations

from collections import Counter

import pytest

from sr_od.application.currency_war.kernel.cw_board_state import (
    BATTLE_WAIT_CONTEXT,
    BS_SCHEMA_VERSION,
    SCREEN_BOSS_BRIEFING,
    SCREEN_NODE_TYPE_DIRECT,
    SCREEN_PLANE_TRANSITION,
    BoardState,
    NodeKey,
    chain_node_type,
)
from sr_od.application.currency_war.kernel.cw_state_journal import (
    install_state_telemetry,
    reset_state_telemetry,
)
from sr_od.application.currency_war.telemetry import state as tel_state

# ============================================================ fixtures


@pytest.fixture()
def journal(tmp_path):
    """装一份指到 tmp 的状态流水(影子面武装;teardown 复位模块全局)。

    flush_every 拉高 = 本文件锁读内存缓冲(j.rows = 未 flush 尾),四腿合成
    走查行量 > 缺省批量阈值时防早段行被自动 flush 清出缓冲(flush 行为本身
    归 test_cw_state_journal 锁面,本文件不辖)。
    """
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                flush_every=100000,
                                run_id_provider=tel_state.current_run_id)
    yield j
    reset_state_telemetry()


@pytest.fixture()
def run_id(monkeypatch):
    """桩一个 run 归属(行内 run_id 键;teardown 由 monkeypatch 自动还原)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_test_r12')
    return 'run_test_r12'


def _prep(bs, plane: int, rnd: int, **kw) -> None:
    """备战帧写点(规则①触发面;与 test_cw_state_journal 同款输入)。"""
    bs.observe_screen_context('货币战争-备战', phase_round=(plane, rnd), **kw)


def _wait(bs) -> None:
    """战斗/结算窗分支 token(守卫族成员;弹窗腿 prev 供给)。"""
    bs.observe_screen_context(BATTLE_WAIT_CONTEXT)


def _rows(journal) -> list[dict]:
    return list(journal.rows)


def _derive_rows(journal, actor: str) -> list[dict]:
    """派生规则行(按 actor 取,家族无涉——四腿序键行均为逻辑层
    family=logic_hook,备战帧顶栏原文行(top_bar_raw)才是观察层
    family=obs,actor 归因不变)。"""
    return [r for r in _rows(journal) if r['sig']['actor'] == actor]


def _advance_rows(journal) -> list[dict]:
    """推进写入行(跃迁本体):node_ord 字段、note 空、非 same_value
    (同序补录/重入重读行 = same_value 形态,非跃迁)。"""
    return [r for r in _rows(journal)
            if r['field'] == 'node_ord'
            and r['note'] == '' and r['same_value'] is False]


# ============================================================ 规则②:位面过渡腿


def test_plane_transition_leg_advances_next_plane_r1(journal, run_id) -> None:
    """§3.4.1 规则②:0q 被采到 → 逻辑节点 = (当前位面+1, 1)。位面来源① =
    调用方顶栏读数 phase_round;候选经坐标系公式 = plane*9+1(基 1)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)                                   # 腿 A:hist=9
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION,
                              phase_round=(1, 9))
    assert bs.node_ord.value == 10, '位面过渡 → (2,1) = ord 10'
    assert bs.node_hist_ord == 10
    rows = _derive_rows(journal, 'derive_node_plane_transition')
    assert len(rows) == 1
    assert rows[0]['after'] == 10
    assert rows[0]['sig']['screen'] == SCREEN_PLANE_TRANSITION
    assert rows[0]['sig']['family'] == 'logic_hook'
    # 过渡屏链 = 离开位面链(件 B v1.1 F1):下位面节点类型不可自定 → 零类型写
    assert bs.node.value is None, '0q 零类型写(下位面类型不由过渡屏定)'


def test_plane_transition_leg_plane_from_observed_mirror(journal, run_id) -> None:
    """规则②位面来源② = bs.node 观察镜像(plane;生产 cw_loop 分支写点不携
    phase_round,镜像顶栏遗产为当前位面来源)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.node, NodeKey(plane=1, round_num=9, kind='boss'))
    _wait(bs)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION)
    assert bs.node_ord.value == 10
    assert bs.node_hist_ord == 10


def test_plane_transition_leg_plane_from_hist_derivation(journal, run_id) -> None:
    """规则②位面来源③ = hist 反解((hist-1)//9+1;镜像与 phase_round 双缺)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)                                   # hist=9,镜像 None
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION)  # 无 phase_round
    assert bs.node_ord.value == 10, 'hist=9 反解位面 1 → (2,1)=10'


def test_plane_transition_leg_reentry_deduped(journal, run_id) -> None:
    """共同语义:候选 ≤ hist 不写不锚——过渡屏多 loop pass 重复写点零重推
    (去重键已占,同序恰一次推进)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    n = len(_derive_rows(journal, 'derive_node_plane_transition'))
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    assert len(_derive_rows(journal, 'derive_node_plane_transition')) == n, \
        '重复 0q 零重推(重入拒绝)'
    assert bs.node_hist_ord == 10


def test_plane_transition_leg_no_plane_source_no_guess(journal, run_id) -> None:
    """开局过渡屏(投资环境前)无「当前位面」可推:三来源全缺 → 禁猜不写,
    交规则①④计数(v3.1-N5 同簇禁猜纪律)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION)
    assert bs.node_ord.value is None
    assert bs.node_hist_ord is None
    assert _derive_rows(journal, 'derive_node_plane_transition') == []


# ============================================================ 规则③:BOSS 简报腿


def test_boss_brief_leg_advances_current_plus_one_no_round9_hardcode(
        journal, run_id) -> None:
    """§3.4.1 规则③:0p 被采到 → 逻辑节点 = 当前节点+1。平面 2 简报 → 13
    (禁写死 round=9:boss 序位随位面格数/环境加节点漂移,简报证据自带类型,
    序位只由「当前+1」承载)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 2, 3)                                   # hist = 9+3 = 12
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    assert bs.node_ord.value == 13, '当前(2,3)+1 → ord 13(非写死 9)'
    assert bs.node_hist_ord == 13
    rows = [r for r in _derive_rows(journal, 'derive_node_boss_brief')
            if r['field'] == 'node_ord']
    assert len(rows) == 1 and rows[0]['after'] == 13
    assert rows[0]['sig']['screen'] == SCREEN_BOSS_BRIEFING


def test_boss_brief_leg_type_boss_written_with_advance(journal, run_id) -> None:
    """规则③类型随简报自带:推进同行为批次写 node.kind='boss'(类型派生
    经节点域,§3.1.3 节点域③格;(plane,round) 由目标序坐标系公式反解)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)                                   # hist=8
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    assert bs.node_ord.value == 9
    assert bs.node.value == NodeKey(plane=1, round_num=9, kind='boss'), \
        'boss 类型落当前+1 节点(1,9)'
    trows = _derive_rows(journal, 'derive_node_boss_brief')
    assert [r['field'] for r in trows] == ['node_ord', 'node'], \
        '规则③双写:先序后类型(固定次序)'
    assert trows[1]['after'] == {'plane': 1, 'round_num': 9, 'kind': 'boss'}


def test_boss_brief_leg_unknown_current_no_guess(journal, run_id) -> None:
    """当前节点未知(effective/hist 双空)→ +1 不可计算,禁猜不写。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    assert bs.node_ord.value is None
    assert bs.node.value is None
    assert _derive_rows(journal, 'derive_node_boss_brief') == []


def test_boss_brief_leg_repeat_deduped_type_idempotent(journal, run_id) -> None:
    """重复 0p(多 loop pass 写点):幂等锚(镜像 boss 节点键 = 本腿类型
    回执)命中 → 推进零重推零类型重写,简报屏重复现身零新增行。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    n = len(_derive_rows(journal, 'derive_node_boss_brief'))
    assert n == 2, '首轮双写:推进 + boss 类型(固定次序)'
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    rows = _derive_rows(journal, 'derive_node_boss_brief')
    assert len(rows) == n, '重复 0p 幂等锚命中,零新增行'
    assert bs.node_hist_ord == 9 and bs.node_ord.value == 9
    assert bs.node.value == NodeKey(plane=1, round_num=9, kind='boss')


# ============================================================ 混合场景:②③与①④去重交互


def test_boss_flow_rule3_suppresses_popup_double_advance(journal, run_id) -> None:
    """boss 流全序(判定方案 E12 边序:奖励关 → 0p → 商店自动开 → boss 备战):
    规则③在 0p 即推进(+boss 类型);后续商店面板块弹窗腿被结构性拒绝
    (prev=0p 出守卫族终版,用户终裁 2026-09-11/攻击 R5 高-1;缓存守卫
    c=8≠hist=9 为第二道防线)零重推;boss 备战帧同序补录。boss 节点恰一次
    推进(级联双推进破口锁)。
    【R1.2 锁语义重推】本锁前身为 R1.1「0p 纯前驱零腿」形态锁——四规则组
    终版(用户 2026-09-10 裁)把 0p 升格为规则③触发面,推进 actor 由弹窗腿
    改为简报腿,锁意图(boss 节点恰一次推进)不变。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)                                     # 腿 A:hist=8
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)     # ③:9 + boss 类型
    assert bs.node_ord.value == 9 and bs.node_hist_ord == 9
    assert bs.node.value == NodeKey(plane=1, round_num=9, kind='boss')
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 8))
    assert bs.node_ord.value == 9, '商店面板块弹窗腿零触发(0p 出族+缓存守卫)'
    assert len(_derive_rows(journal, 'derive_node_inferred')) == 0, \
        '弹窗腿零触发(boss 节点已由③推进,禁双计)'
    _prep(bs, 1, 9)                                     # boss 备战帧后到
    backfill = _derive_rows(journal, 'derive_node_observed')
    assert backfill[-1]['after'] == 9
    assert backfill[-1]['same_value'] is True, '同序补录 = same_value 形态'
    assert backfill[-1]['sig']['family'] == 'logic_hook', \
        '备战腿序键行 = 逻辑层(字段层次终极版,四腿同层)'
    assert bs.node_hist_ord == 9


def test_plane_transition_flow_quiet_shop_popup(journal, run_id) -> None:
    """跨位面级联破口锁(攻击 R5 高-1 同族):0q 推进 (2,1) 后,商店面板块
    若被采到,弹窗腿被结构性拒绝(prev=0q 出守卫族终版;缓存 c=9≠hist=10
    双防)——位面切换后节点序不级联 +1;过渡屏自身零类型写边界同锁。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    assert bs.node_hist_ord == 10
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 9))
    assert bs.node_ord.value == 10, '0q 后商店弹窗腿零触发(0q 出族+缓存守卫)'
    assert len(_derive_rows(journal, 'derive_node_inferred')) == 0, \
        '跨位面节点恰一次推进(来源 = 规则②)'
    assert bs.node.value is None, '0q/商店零类型写(过渡屏=离开位面链)'


def test_plane_transition_then_prep_same_value_backfill(journal, run_id) -> None:
    """跨位面序:0q 推进 (2,1) 后,新位面首备战帧同序 = 观察层补录(腿 A 兜底
    确认,same_value 形态,禁二次跃迁);镜像不被②/①造帧(镜像=观察帧事实,
    漏斗现读更新)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    assert bs.node_hist_ord == 10
    _prep(bs, 2, 1)
    backfill = _derive_rows(journal, 'derive_node_observed')
    assert backfill[-1]['after'] == 10
    assert backfill[-1]['same_value'] is True, '同序补录 = same_value 形态'
    assert bs.node_hist_ord == 10 and bs.node_ord.value == 10
    assert bs.node.value is None, '②/①不造镜像帧(类型派生只在专属画面)'


# ============================================================ 字段层次终极版:观察层/逻辑层分层


def test_layer_split_raw_text_obs_ordinal_logic(journal, run_id) -> None:
    """字段层次终极版锁(用户终裁 2026-09-11):观察层(observe)只落画面
    原始读数——备战帧顶栏原文落 top_bar_raw;节点序键 = 逻辑层字段,四条腿
    (备战=解析顶栏文本成序键/弹窗/0q/0p)全部 write_logic,无 observe 写
    序键的例外;序键无原文不猜(top_raw 缺位 → 原文字段不写)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 3, top_raw='备战阶段 1-3')
    assert bs.top_bar_raw.value == '备战阶段 1-3'
    assert bs.top_bar_raw.source == 'observation', '原文 = 观察层(observe)'
    assert bs.node_ord.value == 3
    assert bs.node_ord.source == 'logic', '序键 = 逻辑层(write_logic)'
    raw_rows = [r for r in journal.rows if r['field'] == 'top_bar_raw']
    assert raw_rows and raw_rows[0]['sig']['family'] == 'obs'
    # 原文缺读形态:top_raw 缺位 → 原文字段不写(禁猜),序键照常派生
    bs2 = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs2.observe_screen_context('货币战争-备战', phase_round=(1, 5))
    assert bs2.top_bar_raw.value is None, '原文缺读不写(禁猜)'
    assert bs2.node_ord.value == 5, '序键派生不依赖原文字段(解析在派生段)'


# ============================================================ 类型派生:专属画面直定


def test_popup_dedicated_screens_direct_type(journal, run_id) -> None:
    """类型派生·直定半部:遭遇/补给/策略三专属屏现身即定该节点类型
    (词表 = boss/supply/encounter/invest 同源,禁新造 token);目标节点 =
    弹窗腿推进后 hist(弹窗屏属即将进入的节点)。弹窗屏无顶栏,缓存守卫
    输入 = 离开节点的顶栏遗产(c == hist 才推进)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _wait(bs)
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node.value == NodeKey(plane=1, round_num=1, kind='encounter')
    _prep(bs, 1, 1)
    _wait(bs)
    bs.observe_screen_context('货币战争-补给', phase_round=(1, 1))
    assert bs.node.value == NodeKey(plane=1, round_num=2, kind='supply')
    _prep(bs, 1, 2)
    _wait(bs)
    bs.observe_screen_context('货币战争-投资策略', phase_round=(1, 2))
    assert bs.node.value == NodeKey(plane=1, round_num=3, kind='invest')
    trows = _derive_rows(journal, 'derive_node_type')
    assert [r['after']['kind'] for r in trows] == ['encounter', 'supply', 'invest']
    assert all(r['sig']['family'] == 'logic_hook' for r in trows)


def test_shop_panel_type_undetermined_no_write(journal, run_id) -> None:
    """商店面板不专属(任意节点类型都开商店)→ 类型「未定型」零写;
    查现行链接线候件 B 实施批(:func:`chain_node_type` 接口在位,本批不接)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _wait(bs)
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_ord.value == 1, '弹窗腿照常推进(序与类型分域)'
    assert bs.node.value is None, '商店类型未定型,零直定写'
    assert '货币战争-备战-开商店' not in SCREEN_NODE_TYPE_DIRECT
    assert _derive_rows(journal, 'derive_node_type') == []


def test_popup_reentry_type_targets_current_node(journal, run_id) -> None:
    """弹窗重入(prev ∉ 守卫集,零推进):类型目标 = hist(本弹窗所属节点
    已由首次现身推进)——同节点同类型 = same_value 形态。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _wait(bs)
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node_hist_ord == 1
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node_hist_ord == 1, '重入零推进(prev=遭遇 ∉ 守卫集)'
    assert bs.node.value == NodeKey(plane=1, round_num=1, kind='encounter'), \
        '类型目标 = 本弹窗所属节点'
    trows = _derive_rows(journal, 'derive_node_type')
    assert len(trows) == 2 and trows[-1]['same_value'] is True


def test_type_conflict_same_node_obs_event_newest_wins(journal, run_id) -> None:
    """类型冲突纪律(G10 同簇):同节点两直定值不一致 → obs_event 留证
    (禁静默)+ 最新直定值落位(最新观察=真相)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _wait(bs)
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node.value == NodeKey(plane=1, round_num=1, kind='encounter')
    # 同节点异源直定:补给屏重入形态(prev ∉ 守卫集 → 目标仍 = hist=1)
    bs.observe_screen_context('货币战争-补给', phase_round=(1, 1))
    ev = [r for r in _rows(journal) if r['row'] == 'obs_event']
    assert len(ev) == 1, '类型冲突必留证(禁静默覆盖)'
    assert ev[0]['event'] == 'arbitrate' and ev[0]['field'] == 'node'
    assert ev[0]['observed'] == {'old_kind': 'encounter', 'new_kind': 'supply',
                                 'node_ord': 1}
    assert '冲突' in ev[0]['verdict']
    assert bs.node.value == NodeKey(plane=1, round_num=1, kind='supply'), \
        '最新直定赢(最新观察=真相)'


def test_derivation_fixed_order_node_domain_then_type(journal, run_id) -> None:
    """固定次序(用户终裁):写入落账后节点域判定 → 类型派生——0p 触发的
    推进行版本序先于类型行(同临界区顺序落账,无 hook 框架)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    seq_field = [(r['v'], r['field']) for r in _rows(journal)
                 if r['field'] in ('node_ord', 'node')]
    pairs = [f for _, f in seq_field]
    assert pairs.index('node_ord') < pairs.index('node'), \
        '节点域判定先于类型派生(版本序可验)'


# ============================================================ chain_node_type 接口预留(件 B v1.1 §3.4)


def test_chain_query_reserved_interface_honest_none(journal, run_id) -> None:
    """件 B 接口语义(§3.4/§3.8):现行链该位原值零内建回落;链缺 = token
    None(「现行链不知道」,不是「该位不存在」);hu_dist 随 token,链缺恒
    None。当前生产零链写端(件 B §④B)→ 恒诚实 None。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    q = chain_node_type(bs, 1, 3)
    assert q.token is None and q.hu_dist is None, \
        '链缺 = 现行链不知道(零内建回落禁把基线/台账当兜底)'


def test_chain_query_position_addressing_on_injected_chain(journal, run_id) -> None:
    """链在位形态(测试注入;生产写端归件 B B-2/B-3):位寻址 = seq[i] 第
    i+1 轮(round 基 1,与 PlaneNodeLedger 下标语义同式);位越界 = None。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.node_path, ['reward', 'battle', 'supply'],
                   produced_by='TestChainWriter')
    assert chain_node_type(bs, 1, 2).token == 'battle'
    assert chain_node_type(bs, 1, 4).token is None, '位越界 = 现行链不知道'
    assert chain_node_type(bs, 1, 1).token == 'reward'


# ============================================================ 四腿合成场景走查


def test_four_leg_synthetic_walkthrough_each_node_advanced_once(
        journal, run_id) -> None:
    """四腿合成走查(§3.4.3 写点完备性;开局→普通→boss→跨位面全流程一遍):
    每节点序恰一次推进(M3 验收判定基准 = 推进去重键);类型逐节点直定;
    每次跃迁恰一行推进写入。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    # 开局:战斗窗 → 商店面板块先被采到(④→1)
    _wait(bs)
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    _prep(bs, 1, 1)                                     # ① 同序补录
    # 普通节点 2/3/4:遭遇→补给→策略(④ 推进 + 类型直定;弹窗屏无顶栏,
    # 缓存 c = 离开节点读数 == hist 才过守卫)
    for screen, cache in (('货币战争-遭遇节点', 1), ('货币战争-补给', 2),
                          ('货币战争-投资策略', 3)):
        _prep(bs, 1, cache)
        _wait(bs)
        bs.observe_screen_context(screen, phase_round=(1, cache))
    # 普通战斗节点 5..8:备战帧顶栏逐节点权威推进(①)
    for rnd in (5, 6, 7, 8):
        _prep(bs, 1, rnd)
    # boss 节点 9:奖励关结算 → 0p 简报(③→9+boss)→ boss 备战帧补录
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    _prep(bs, 1, 9)
    # 跨位面:0q 过渡(②→10)→ 新位面首备战帧补录
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    _prep(bs, 2, 1)

    assert bs.node_hist_ord == 10, '全程 hist 终值 = 位面 2 节点 1'
    # 每节点序恰一次推进:推进行(note 空)按序去重 = 1..10 各恰一次
    adv = Counter(r['after'] for r in _advance_rows(journal))
    assert sorted(adv) == list(range(1, 11)), '节点序 1..10 全覆盖'
    assert all(c == 1 for c in adv.values()), \
        f'每节点序恰一次推进(去重键),实测:{adv}'
    by_leg = {(r['sig']['actor'], r['after']) for r in _advance_rows(journal)}
    assert ('derive_node_inferred', 1) in by_leg, '节点 1 = ④ 弹窗腿'
    assert {('derive_node_observed', n) for n in (5, 6, 7, 8)} <= by_leg, \
        '节点 5..8 = ① 备战腿'
    assert ('derive_node_boss_brief', 9) in by_leg, '节点 9 = ③ 简报腿'
    assert ('derive_node_plane_transition', 10) in by_leg, '节点 10 = ② 过渡腿'
    # 类型逐节点直定
    type_rows = _derive_rows(journal, 'derive_node_type') + \
        [r for r in _derive_rows(journal, 'derive_node_boss_brief')
         if r['field'] == 'node']
    kinds = {(r['after']['round_num'], r['after']['kind']) for r in type_rows
             if r['after'].get('plane') == 1}
    assert {(2, 'encounter'), (3, 'supply'), (4, 'invest'),
            (9, 'boss')} <= kinds, f'专属屏类型逐节点直定,实测:{kinds}'
    assert bs.node.value == NodeKey(plane=1, round_num=9, kind='boss'), \
        '镜像终态 = 最后专属屏类型帧(②/①不造镜像帧,漏斗现读更新)'
