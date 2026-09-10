"""统一 state 状态流水(R1 影子双写)锁面。

设计正本 = ``.debug/temp/currency_war/流程侧遥测-设计v3.1.md``(v3 根本性纠正
定稿:自足状态流水——每次写入一行,行内 = 改了什么 + 渠道签名 + 版本 id +
写入后完整 state 快照;快照锚/对账自检/前溯推导整套作废,禁回归)。

锁面 =
- 渠道枚举封闭集(§3.2.1:family/mode 集外值 = 红);
- 版本 id 单调不重不漏(§3.2.2:run 段内自 1 连续,行序 = 版本序);
- 自足快照行完整性(§3.2.3:任取一行可独立解读——行内 state 含此前全部写入);
- 影子双写零行为变更(§3.7.1:开关缺省关 = 零文件零写入;开 = 既有字段轨迹逐位一致);
- 节点推进派生规则(§3.4:双腿照搬判定方案 R3 本体——单调推进/重入拒绝/
  倒退免疫/先到先推进/权威纠偏);
- 批量 flush 与局外拒写(§3.2.3 落盘形态:run_id 空 = 拒写,不写假行)。

测试隔离:journal sink 与 actor 登记面是模块级全局——fixture 统一安装/复位;
run_id 经 monkeypatch 桩化(telemetry.state 测试复位正规入口同簇语义)。
"""
from __future__ import annotations

import json

import pytest

from sr_od.application.currency_war.kernel import cw_state_journal as journal_mod
from sr_od.application.currency_war.kernel.cw_board_state import (
    BATTLE_WAIT_CONTEXT,
    BENCH_CAPACITY_DEFAULT,
    BS_SCHEMA_VERSION,
    SCREEN_PREP_FRAME,
    BenchSlot,
    BenchView,
    BoardState,
    ChannelSig,
    Field,
    Unit,
    register_sig_actors,
    state_telemetry_armed,
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

    run 归属读取函数经 provider 注入(kernel 禁依 telemetry 的依赖倒置口,
    与生产装配点同形)——monkeypatch ``_CURRENT_RUN_ID`` 后经该函数生效。
    """
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=tel_state.current_run_id)
    yield j
    reset_state_telemetry()


@pytest.fixture()
def run_id(monkeypatch):
    """桩一个 run 归属(行内 run_id 键;teardown 由 monkeypatch 自动还原)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_test_journal')
    return 'run_test_journal'


def _read_rows(path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _write_rows(bs) -> list[dict]:
    """从当前装着的 journal 缓冲取行(不经落盘;装 journal 才有)。"""
    j = journal_mod.state_journal_instance()
    assert j is not None, '本用例须先装 journal(fixture journal)'
    return list(j.rows)


# ============================================================ 渠道枚举封闭集(§3.2.1)


def test_channel_family_closed_set() -> None:
    """§3.2.1 硬约束 2:family 封闭集 {obs, logic_action, logic_hook},集外 = 红。"""
    for family in ('obs', 'logic_action', 'logic_hook'):
        assert ChannelSig(family=family, actor='cw_observation').family == family
    with pytest.raises(ValueError):
        ChannelSig(family='event', actor='x')
    with pytest.raises(ValueError):
        ChannelSig(family='hook', actor='x')


def test_channel_mode_closed_set_per_family() -> None:
    """§3.2.1:obs 族子模 = read/carried/prior/synthesized;logic 两族恒 compute。"""
    for mode in ('read', 'carried', 'prior', 'synthesized'):
        ChannelSig(family='obs', actor='cw_observation', mode=mode)
    with pytest.raises(ValueError):
        ChannelSig(family='obs', actor='cw_observation', mode='compute')
    for family in ('logic_action', 'logic_hook'):
        ChannelSig(family=family, actor='derive_node_observed', mode='compute')
        with pytest.raises(ValueError):
            ChannelSig(family=family, actor='derive_node_observed', mode='read')


def test_actor_registration_gate() -> None:
    """§3.2.1/§3.2.4 硬约束 2:显式 sig 的 actor 须为登记面在册,集外 = 红。"""
    register_sig_actors('TestActorR1')
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    # 未登记 actor + 显式 sig = 拒写
    with pytest.raises(ValueError):
        bs.observe(bs.gold, 20, sig=ChannelSig(family='obs', actor='NeverRegistered'))
    # 登记后放行
    bs.observe(bs.gold, 20, sig=ChannelSig(family='obs', actor='TestActorR1'))
    assert bs.gold.value == 20


def test_api_family_mismatch_rejected() -> None:
    """渠道族语义:观察 API 只收 obs 签名,logic API 不收 obs 签名(错渠道 = 红)。"""
    register_sig_actors('TestActorR1b')
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    logic_sig = ChannelSig(family='logic_action', actor='TestActorR1b')
    obs_sig = ChannelSig(family='obs', actor='TestActorR1b')
    with pytest.raises(ValueError):
        bs.observe(bs.gold, 1, sig=logic_sig)
    with pytest.raises(ValueError):
        bs.write_logic(bs.gold, 1, produced_by='x', sig=obs_sig)


# ============================================================ 版本 id(§3.2.2)


def test_version_id_monotonic_contiguous_and_row_order(
        journal, run_id, tmp_path) -> None:
    """§3.2.2:run 段内自 1 连续单调不重不漏;行序 = 版本序;读口一致。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)                       # v1
    bs.observe(bs.gold, 21)                       # v2(值未变重读也计版本见下条)
    bs.carry(bs.gold, frame='p1-r2')              # v3
    bs.write_logic(bs.free_refresh_balance, 2,
                   produced_by='RefreshShop')     # v4
    rows = journal.rows
    assert [r['v'] for r in rows] == [1, 2, 3, 4], 'run 段内自 1 连续,不重不漏'
    assert rows == sorted(rows, key=lambda r: r['v']), '行序 = 版本序'
    assert bs.current_version() == 4
    assert bs.write_seq == 4, '版本 id = write_seq 升格(心跳语义不变)'


def test_reread_same_value_still_versions_with_same_value_flag(
        journal, run_id) -> None:
    """§3.2.2 规则 4:值未变重读也是「观察发生了」,计版本 + 行注记 same_value。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)
    bs.observe(bs.gold, 20)
    rows = journal.rows
    assert [r['v'] for r in rows] == [1, 2]
    assert rows[0]['same_value'] is False
    assert rows[1]['same_value'] is True, '值未变重读 = same_value 行'


def test_carry_without_value_no_row_no_version(journal, run_id) -> None:
    """§3.2.2 规则 4:carry 且值无正式值(early return)不换帧不产行不占版本。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.carry(bs.gold, frame='p1-r1')   # gold 从未读过 → 不写
    assert journal.rows == []
    assert bs.current_version() == 0


def test_expect_bookkeeping_no_row(journal, run_id) -> None:
    """§3.1.1-5(v3 简化):预期登记/清账不产行,挂起面随快照可见。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)
    before = len(journal.rows)
    entry = bs.expect(bs.gold, 17)
    bs.discard_expected(entry)
    assert len(journal.rows) == before, '预期簿记不产行(v3 简化语义)'


# ============================================================ 自足快照行(§3.2.3)


def test_row_schema_complete_and_self_contained(journal, run_id) -> None:
    """§3.2.3 行型 1:行 = v/ts/run_id/row/field/after/same_value/state/sig;
    任取一行可独立解读——行内 state 含该时点完整字段面(含此前写入)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)                                    # v1
    bs.observe(bs.bench, BenchView(
        slots=[BenchSlot(kind='unit',
                         unit=Unit(char_id='aglaea', star=1, slot=1))],
        capacity=BENCH_CAPACITY_DEFAULT))                      # v2
    rows = journal.rows
    assert len(rows) == 2
    for r in rows:
        assert set(r) >= {'v', 'ts', 'run_id', 'row', 'field', 'after',
                          'same_value', 'state', 'sig'}
        assert r['run_id'] == 'run_test_journal'
        assert r['row'] == 'write'
        assert set(r['sig']) >= {'family', 'actor', 'screen', 'mode',
                                 'quality', 'group_id'}
    # 行 1 自足:state.gold 已是本行写入后的 20
    assert rows[0]['field'] == 'gold' and rows[0]['after'] == 20
    assert rows[0]['state']['values']['gold'] == 20
    assert rows[0]['state']['values'].get('bench') is None
    # 行 2 自足:此前 gold=20 与本行 bench 同帧可见(查询直接读行,零前溯)
    assert rows[1]['field'] == 'bench'
    assert rows[1]['state']['values']['gold'] == 20
    assert rows[1]['state']['values']['bench']['capacity'] == BENCH_CAPACITY_DEFAULT
    assert rows[1]['state']['values']['bench']['slots'][0]['unit']['char_id'] == 'aglaea'


def test_legacy_sig_synthesis_per_api(journal, run_id) -> None:
    """影子期过渡:显式 sig 缺位时按 API 语义合成封闭集内签名
    (write_logic 带 produced_by → actor;观察族 family=obs)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)
    bs.write_logic(bs.free_refresh_balance, 2, produced_by='RefreshShop')
    rows = journal.rows
    assert rows[0]['sig']['family'] == 'obs'
    assert rows[0]['sig']['mode'] == 'read'
    assert rows[1]['sig']['family'] == 'logic_action'
    assert rows[1]['sig']['mode'] == 'compute'
    assert rows[1]['sig']['actor'] == 'RefreshShop', \
        'legacy 合成 sig 的 actor = produced_by(留证不丢)'


def test_state_snapshot_effects_normalized(journal, run_id) -> None:
    """§3.2.3 序列化规范化:effects 按 spec id 排序(同态同形,离线 diff 可比)。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        ActiveEffect,
        DurationKind,
        EffectKind,
        EffectSpec,
        TriggerKind,
        UnitBuffRef,
    )
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    for sid in ('s_204999', 's_204100'):
        bs.effects.entries.append(ActiveEffect(
            spec=EffectSpec(id=sid, name=f'n{sid}', trigger=TriggerKind.NODE_ENTER,
                            duration=DurationKind.N_NODES,
                            category=EffectKind.ECONOMY,
                            payload=UnitBuffRef(effect_text='x'),
                            duration_nodes=3),
            source='strategy', acquired_t=1, remaining_nodes=3,
            remaining_uses=None))
    bs.observe(bs.gold, 5)
    row = journal.rows[-1]
    effect_ids = [e['spec_id'] for e in row['state']['effects']]
    assert effect_ids == sorted(effect_ids), 'effects 按 spec id 规范化排序'


# ============================================================ 影子双写零行为变更(§3.7.1)


def test_shadow_off_no_file_no_sink(tmp_path) -> None:
    """缺省关(项目纪律):不武装 = sink 缺席,写入链零新增副作用零文件。"""
    reset_state_telemetry()
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)
    assert state_telemetry_armed() is False
    assert journal_mod.state_journal_instance() is None
    # 不指到 tmp_path 的任何落盘:整体校验 = 装配目录树不存在(临时目录为空)
    assert not (tmp_path / 'state').exists()


def test_shadow_on_off_identical_preexisting_fields(journal, run_id, tmp_path) -> None:
    """§3.7.1 影子纪律:开/关两种状态下,既有字段写入轨迹逐位一致
    (影子面只新增派生域,不改既有域任何一帧)。"""

    def _trajectory() -> list[tuple]:
        bs = BoardState(schema_version=BS_SCHEMA_VERSION)
        bs.observe(bs.gold, 20)
        bs.carry(bs.gold, frame='p1-r2')
        bs.write_logic(bs.free_refresh_balance, 2, produced_by='RefreshShop')
        bs.observe(bs.gold, 25)
        entry = bs.expect(bs.gold, 27, confirm_point='prep_obs')
        bs.confirm(entry)
        bs.leave_screen(bs.shop)
        bs.relay(bs.active_strategies, [' Handsome'])
        seq = []
        for name in ('gold', 'free_refresh_balance', 'shop', 'active_strategies'):
            f = getattr(bs, name)
            seq.append((name, f.value, f.source, f.evidence))
        return seq

    reset_state_telemetry()      # 先取「关」轨迹(fixture 的武装先复位)
    off = _trajectory()
    install_state_telemetry(tmp_path / 'state2' / 'journal.jsonl',
                            run_id_provider=tel_state.current_run_id)
    on = _trajectory()
    reset_state_telemetry()
    assert on == off, '影子双写对既有字段轨迹逐位零变更'


def test_run_id_empty_rejects_rows(journal, monkeypatch) -> None:
    """§3.2.3 局外写入拒绝:run_id 空 = 拒写假行(诚实缺失)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', '')
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)
    assert journal.rows == [], '局外不写假行'
    assert bs.current_version() == 1, 'state 写入本体照常(版本照常分配)'


def test_journal_batch_flush(tmp_path, monkeypatch) -> None:
    """§3.2.3 落盘形态:内存追加 + 批量 flush(缓冲满阈值落盘);崩溃窗 = 未 flush 尾。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_flush')
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                flush_every=2,
                                run_id_provider=tel_state.current_run_id)
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 1)
    assert not (tmp_path / 'state' / 'journal.jsonl').exists(), \
        '未到阈值不落盘(行在内存缓冲)'
    bs.observe(bs.gold, 2)
    rows = _read_rows(tmp_path / 'state' / 'journal.jsonl')
    assert [r['v'] for r in rows] == [1, 2], '到阈值批量落盘'
    j.flush()
    assert journal_mod.state_journal_instance() is j


# ============================================================ 节点推进派生规则(§3.4;R3 本体)


def _prep(bs, plane: int, rnd: int, **kw) -> None:
    bs.observe_screen_context('货币战争-备战', phase_round=(plane, rnd), **kw)


def _derive_rows(journal, actor: str) -> list[dict]:
    return [r for r in journal.rows
            if r['sig']['family'] == 'logic_hook' and r['sig']['actor'] == actor]


def test_prep_leg_advances_node_observed(journal, run_id) -> None:
    """§3.4.1 规则二(备战腿):干净备战帧 ∧ 顶栏可读 → node_observed = 节点序
    (ord = (plane-1)*9 + round);渠道 = ③ logic_hook。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 2)
    assert bs.node_observed.value == 2
    rows = _derive_rows(journal, 'derive_node_observed')
    assert len(rows) == 1
    assert rows[0]['after'] == 2
    assert rows[0]['sig']['family'] == 'logic_hook'
    assert rows[0]['sig']['screen'] == '货币战争-备战'
    # 画面上下文对(§3.1.4):旧值转 prev,同 group
    assert bs.current_screen.value == '货币战争-备战'
    ctx_rows = [r for r in journal.rows if r['field'] == 'current_screen']
    assert ctx_rows and ctx_rows[0]['sig']['family'] == 'obs'


def test_prep_leg_same_value_reread_is_same_value_row(journal, run_id) -> None:
    """v3.1-N2 后到腿写字段裁定:备战重入重读(候选 == hist 且字段已同值)
    = 观察真值照录,行 = same_value 形态(计入行量预算);不构成第二次跃迁。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 2)
    _prep(bs, 1, 2)   # 同节点重入重读
    rows = _derive_rows(journal, 'derive_node_observed')
    assert len(rows) == 2
    assert rows[-1]['after'] == 2
    assert rows[-1]['same_value'] is True, '重入重读行 = same_value 形态'
    assert rows[-1]['note'] == 'same_advance', '同序行注记(去重键已占,非跃迁)'
    assert bs.node_hist_ord == 2


def test_advance_dedup_key_hist_survives_correction(journal, run_id) -> None:
    """v3.1-N2 去重键 = (run_id, effective_ord):同序恰一次推进——字段低于
    hist 的窗内,弹窗腿候选 ≤ hist 不写不锚(去重键已占,禁重推已见序)。

    「字段低于 hist」窗 = 测试直设属性种子(生产不可达:备战腿推进即拉齐
    推断;种值只为单测去重键判定,非旁路写入面)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 5)                       # 腿 A 推进 hist=5
    # 种子:两派生字段均低于 hist(effective=4,candidate=5 ≤ hist=5)
    bs.node_inferred = Field(value=4, source='logic')
    bs.node_observed = Field(value=4, source='logic')
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 5))
    # c=5==hist=5 → 候选=effective(4)+1=5 ≤ hist=5 → 不写不锚(去重键已占)
    assert bs.node_inferred.value == 4, '去重键已占,同序不重推'
    assert _derive_rows(journal, 'derive_node_inferred') == []


def test_prep_leg_retrograde_rejected(journal, run_id) -> None:
    """R3 规则三:候选 < 现值(读值倒退 = 缓存滞后)拒绝即免疫。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 5)
    _prep(bs, 1, 4)   # 倒退
    assert bs.node_observed.value == 5


def test_prep_leg_authority_correction(journal, run_id) -> None:
    """§3.4.1 规则二(权威纠偏):备战腿观察值与 node_inferred 不一致时
    以观察值为准拉齐,纠偏事实记入行 note(推断偏差显影不静默)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    # 先让弹窗腿推到 2(开局形态候选 1 → 再次守卫通过候选 2)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node_inferred.value == 2
    # 备战帧顶栏真读 3(与推断不一致)→ 权威值落位 + 推断拉齐 + 纠偏显影
    _prep(bs, 1, 3)
    assert bs.node_observed.value == 3
    corr = [r for r in _derive_rows(journal, 'derive_node_observed')
            if r.get('note')]
    assert corr and '纠偏' in corr[-1]['note'], '纠偏事实入 note 显影'
    assert bs.node_inferred.value == 3, '以观察值为准拉齐(决策消费面 max 不被推断毒化)'


def test_popup_leg_advances_by_inference(journal, run_id) -> None:
    """§3.4.1 规则一(弹窗腿):prev ∈ 守卫集 ∧ current ∈ 弹窗族 → 推断 +1
    (R3 候选 = last+1;开局无前值 → 1)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    # 开局形态:守卫集(开局链/战斗等待)→ 商店面板先被采到,last 空 → 候选 1
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_inferred.value == 1
    # 常规形态:结算/战斗段之后快弹窗,c == last → 候选 = last+1
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node_inferred.value == 2
    rows = _derive_rows(journal, 'derive_node_inferred')
    assert [r['after'] for r in rows] == [1, 2]


def test_popup_leg_prev_guard_rejects_reentry(journal, run_id) -> None:
    """R3 规则五:备战帧已分派后的弹窗 = 段内子阶段(prev ∉ 守卫集)零触发。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 1)   # 备战帧先被采到(prev 备战 ∉ 守卫集)
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_inferred.value is None, '商店访问重入不误触发'


def test_popup_leg_cache_guard_and_fallback_to_prep_leg(
        journal, run_id) -> None:
    """R3 规则二③/规则五:缓存 c != last → 零触发交腿 A 兜底;后续弹窗帧
    prev ∈ 弹窗族 ∉ 守卫集 → 持续零触发;下一节点备战帧由腿 A 兜底推进。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 1)                     # 腿 A 先推进 node_observed=1
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 3))
    # c=ord(1,3)=3 != last=1 → 缓存守卫拒绝
    assert bs.node_inferred.value is None
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    # prev=遭遇 ∉ 守卫集(R3 prev_branch 守卫:弹窗重入不触发)
    assert bs.node_inferred.value is None
    _prep(bs, 1, 2)                     # 下一节点备战帧 → 腿 A 兜底
    assert bs.node_observed.value == 2


def test_two_legs_same_transition_popup_first(journal, run_id) -> None:
    """v3.1-N2「两腿落同一跃迁」:弹窗腿先到先推进;备战帧后到同序 = 观察
    真值补全照写(note=same_advance)但去重键已占,不构成第二次跃迁。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_inferred.value == 1           # 弹窗腿先到,先推进
    n_inf = len(_derive_rows(journal, 'derive_node_inferred'))
    _prep(bs, 1, 1)                               # 备战帧后到(同序)
    backfill = _derive_rows(journal, 'derive_node_observed')
    assert len(backfill) == 1 and backfill[0]['after'] == 1
    assert backfill[0]['note'] == 'same_advance', '同序补录行注记'
    assert len(_derive_rows(journal, 'derive_node_inferred')) == n_inf, \
        '推进不重复(去重键已占)'
    assert bs.node_hist_ord == 1 and (bs.node_inferred.value,
                                      bs.node_observed.value) == (1, 1)


def test_popup_leg_resume_disabled(journal, run_id) -> None:
    """R3 规则六:恢复局 last 空时弹窗腿禁用不猜,交腿 A。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', resumed=True)
    assert bs.node_inferred.value is None


def test_popup_leg_without_cache_reading_disabled(journal, run_id) -> None:
    """弹窗腿缓存守卫输入缺位(phase_round 未带)→ 禁用不猜(有 last 时)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 1)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点')
    assert bs.node_inferred.value is None


def test_derivation_fields_are_logic_hook_channel_only(journal, run_id) -> None:
    """§3.1.3 域准入:node_inferred/node_observed 唯一写点 = 派生规则(渠道③);
    上下文域唯一写点 = ①观察汇聚。影子行可对账。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 2, 1)
    assert bs.node_observed.value == 10   # (2-1)*9+1
    writers = {(r['field'], r['sig']['family']) for r in journal.rows}
    assert ('node_observed', 'logic_hook') in writers
    assert ('prev_screen', 'obs') in writers and ('current_screen', 'obs') in writers


# ============================================================ R1.1 守卫族扩员+过渡帧行为(用户 2026-09-10 裁定)


def test_popup_leg_boss_briefing_predecessor_advances(journal, run_id) -> None:
    """R1.1 守卫族扩员锁(用户 2026-09-10 裁定;证据 = screen_flow_timing.md
    #26/#14/#27/#29):boss 流 = 奖励关 → BOSS 简报(0p)→ 商店自动开,
    弹窗腿前驱 = 0p(非结算窗)——0p 前驱下商店面板块被采到,弹窗腿必须
    推进(候选 = hist+1 = boss 节点序)。
    走查(判定方案 E12 边序勘误后):奖励关备战帧(腿 A,hist=8)→ 0p 分支
    写点(前驱供给,自身零腿——不在弹窗族)→ 0n 商店面板块漏斗写 → 弹窗腿
    推 9;boss 备战帧后到同序 = 观察补录(R3 本体零变化,锁
    test_two_legs_same_transition_popup_first 同簇)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)                                    # 奖励关备战帧:腿 A 推 8
    bs.observe_screen_context('货币战争-BOSS简报')      # 0p 分支写点(cw_loop 同款输入)
    assert _derive_rows(journal, 'derive_node_inferred') == [], \
        '0p 分支写点自身零腿(BOSS简报不在弹窗族,纯 prev 供给)'
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 8))
    assert bs.node_inferred.value == 9, \
        '0p 前驱 → 商店面板块弹窗腿推 9(boss 节点;守卫族漏 0p = 本场景漏触发)'
    rows = _derive_rows(journal, 'derive_node_inferred')
    assert len(rows) == 1 and rows[0]['after'] == 9
    assert rows[0]['sig']['screen'] == '货币战争-备战-开商店', '触发画面 = 商店面板块'
    assert bs.node_hist_ord == 9
    _prep(bs, 1, 9)                                    # boss 备战帧后到:同序补录
    backfill = _derive_rows(journal, 'derive_node_observed')
    assert backfill[-1]['after'] == 9
    assert backfill[-1]['note'] == 'same_advance', 'boss 备战帧同序补录注记'


def test_funnel_transition_frames_never_write_context() -> None:
    """R1.1 过渡帧行为锁(R1.1 核验结论 = 交付报告「过渡帧写点核验」节):
    0p/0q/0r 过渡帧**不计入**画面标识写入(观察汇聚漏斗面)——阶段键→画面
    标识映射封闭(备战/开商店/战斗等待/禁猜 None 四态),任何阶段输入都不
    产出过渡帧标识。
    生产依赖:①过渡帧不改 prev(弹窗腿守卫族判据面不被过渡帧污染);②过渡
    帧不动顶栏 last-known-good 缓存(弹窗腿缓存守卫 c==hist 的输入稳定性);
    过渡帧的画面标识供给唯一走 cw_loop 分支写点(分支级标识变体,R2 五点)。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import SHOP_SCREEN_NAME
    from sr_od.application.currency_war.obs.cw_observation import (
        PHASE_BATTLE_OR_TRANSIT,
        PHASE_PREP_CLEAN,
        PHASE_PREP_SHOP_OPEN,
        _phase_screen_context,
    )
    legal = {SCREEN_PREP_FRAME, SHOP_SCREEN_NAME, BATTLE_WAIT_CONTEXT, None}
    for phase in (None, PHASE_PREP_CLEAN, PHASE_PREP_SHOP_OPEN,
                  PHASE_BATTLE_OR_TRANSIT, 'no_such_phase'):
        for plane, rnd in ((1, 8), (2, 1), (None, None)):
            name, top = _phase_screen_context(phase, plane, rnd)
            assert name in legal, \
                f'阶段 {phase!r} 产出越界画面标识 {name!r}(映射封闭集破口)'
    produced = {_phase_screen_context(p, 1, 8)[0] for p in
                (None, PHASE_PREP_CLEAN, PHASE_PREP_SHOP_OPEN,
                 PHASE_BATTLE_OR_TRANSIT)}
    for t in ('货币战争-BOSS简报', '货币战争-位面过渡', '货币战争-简报'):
        assert t not in produced, f'过渡帧标识 {t} 不得由漏斗产出(过渡帧零写入)'


# ============================================================ 观察事件行(v3.1-N1/§3.2.3 行型 2)


def test_obs_event_occupies_version_and_embeds_state(journal, run_id) -> None:
    """v3.1-N1/§3.2.3 行型 2:obs_event 同流、占版本、内嵌当时 state——
    零状态变更;「run 段内行序 = 版本序」不变量覆盖全部行型。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 40)                                    # v1 (write)
    bs.note_obs_event(
        'arbitrate', 'level', {'old': 4, 'new': 213},
        verdict='保旧-单调守卫', obs_phase='prep_clean',
        evidence_refs=[{'shot': 'obs_conflict_level_x.webp'}])  # v2 (obs_event)
    bs.observe(bs.gold, 41)                                    # v3 (write)
    rows = journal.rows
    assert [r['v'] for r in rows] == [1, 2, 3], 'obs_event 占版本,行序=版本序'
    ev = rows[1]
    assert ev['row'] == 'obs_event'
    assert ev['event'] == 'arbitrate' and ev['field'] == 'level'
    assert ev['observed'] == {'old': 4, 'new': 213}
    assert ev['verdict'] == '保旧-单调守卫' and ev['obs_phase'] == 'prep_clean'
    assert ev['evidence_refs'] == [{'shot': 'obs_conflict_level_x.webp'}]
    assert ev['state']['values']['gold'] == 40, '内嵌当时 state(行行自足)'
    assert ev['sig']['family'] == 'obs'
    # 零状态变更:版本推进但字段面不动
    assert bs.level.value is None
    assert rows[2]['state']['values']['gold'] == 41
