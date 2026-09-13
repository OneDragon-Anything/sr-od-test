"""统一 state 状态流水锁面(R5 W1 常开化后形态)。

设计正本 = ADR-0630(含修订节)+ ADR-0634(影子双写推翻:journal 无条件
常开,无开关无影子期;写入口签名必填)。

锁面 =
- 渠道枚举封闭集(§3.2.1:family/mode 集外值 = 红);
- 版本 id 单调不重不漏(§3.2.2:run 段内自 1 连续,行序 = 版本序);
- 自足快照行完整性(§3.2.3:任取一行可独立解读——行内 state 含此前全部写入);
- 常开形态(ADR-0634:签名必填无 legacy 合成;账本接线被动零行为分支);
- 节点推进派生规则(§3.4:双腿照搬判定方案 R3 本体——单调推进/重入拒绝/
  倒退免疫/先到先推进/权威纠偏);
- 批量 flush 与局外拒写(§3.2.3 落盘形态:run_id 空 = 拒写,不写假行)。

测试隔离:journal sink 与 actor 登记面是模块级全局——fixture 统一安装/复位;
run_id 经 monkeypatch 桩化(telemetry.state 测试复位正规入口同簇语义)。
"""
from __future__ import annotations

import json
from collections import Counter

import pytest

from sr_od.application.currency_war.kernel import cw_state_journal as journal_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    BATTLE_WAIT_CONTEXT,
    BENCH_CAPACITY_DEFAULT,
    BS_SCHEMA_VERSION,
    SCREEN_BOSS_BRIEFING,
    SCREEN_CONTEXT_GUARD_PREV,
    SCREEN_NODE_TYPE_DIRECT,
    SCREEN_PLANE_TRANSITION,
    SCREEN_PREP_FRAME,
    BenchSlot,
    BenchView,
    ChannelSig,
    Field,
    GameState,
    NodeKey,
    Unit,
    chain_node_type,
    register_sig_actors,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_game_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    register_sig_actors as _register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_state_journal import (
    install_state_telemetry,
    reset_state_telemetry,
)
from sr_od.application.currency_war.telemetry import state as tel_state

_register_sig_actors('TestSigWriter')


def _sig() -> _ChannelSig:
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> _ChannelSig:
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _hsig() -> _ChannelSig:
    """渠道③签名(logic_hook 族;relay 中继)。"""
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')


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
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    # 未登记 actor + 显式 sig = 拒写
    with pytest.raises(ValueError):
        bs.observe(bs.gold, 20, sig=ChannelSig(family='obs', actor='NeverRegistered'))
    # 登记后放行
    bs.observe(bs.gold, 20, sig=ChannelSig(family='obs', actor='TestActorR1'))
    assert bs.gold.value == 20


def test_api_family_mismatch_rejected() -> None:
    """渠道族语义:观察 API 只收 obs 签名,logic API 不收 obs 签名(错渠道 = 红)。"""
    register_sig_actors('TestActorR1b')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
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
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20, sig=_sig())                       # v1
    bs.observe(bs.gold, 21, sig=_sig())                       # v2(值未变重读也计版本见下条)
    bs.carry(bs.gold, frame='p1-r2', sig=_sig())              # v3
    bs.write_logic(bs.free_refresh_balance, 2,
                   produced_by='RefreshShop', sig=_lsig())     # v4
    rows = journal.rows
    assert [r['v'] for r in rows] == [1, 2, 3, 4], 'run 段内自 1 连续,不重不漏'
    assert rows == sorted(rows, key=lambda r: r['v']), '行序 = 版本序'
    assert bs.current_version() == 4
    assert bs.write_seq == 4, '版本 id = write_seq 升格(心跳语义不变)'


def test_reread_same_value_still_versions_with_same_value_flag(
        journal, run_id) -> None:
    """§3.2.2 规则 4:值未变重读也是「观察发生了」,计版本 + 行注记 same_value。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20, sig=_sig())
    bs.observe(bs.gold, 20, sig=_sig())
    rows = journal.rows
    assert [r['v'] for r in rows] == [1, 2]
    assert rows[0]['same_value'] is False
    assert rows[1]['same_value'] is True, '值未变重读 = same_value 行'


def test_carry_without_value_no_row_no_version(journal, run_id) -> None:
    """§3.2.2 规则 4:carry 且值无正式值(early return)不换帧不产行不占版本。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.carry(bs.gold, frame='p1-r1', sig=_sig())   # gold 从未读过 → 不写
    assert journal.rows == []
    assert bs.current_version() == 0


def test_write_logic_emits_row(journal, run_id) -> None:
    """渠道②:write_logic 逻辑直写产行(ADR-0651 两态制;原「预期登记/
    清账不产行」的簿记面随两步机制废除——逻辑写 = 正式写点必落账)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20, sig=_sig())
    before = len(journal.rows)
    bs.write_logic(bs.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    assert len(journal.rows) == before + 1, '逻辑直写产行(正式写点)'
    assert journal.rows[-1]['field'] == 'gold'
    assert journal.rows[-1]['sig']['family'] == 'logic_action'


# ============================================================ 自足快照行(§3.2.3)


def test_row_schema_complete_and_self_contained(journal, run_id) -> None:
    """§3.2.3 行型 1:行 = v/ts/run_id/row/field/after/same_value/state/sig;
    任取一行可独立解读——行内 state 含该时点完整字段面(含此前写入)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20, sig=_sig())                                    # v1
    bs.observe(bs.bench, BenchView(
        slots=[BenchSlot(kind='unit',
                         unit=Unit(char_id='aglaea', star=1, slot=1))],
        capacity=BENCH_CAPACITY_DEFAULT), sig=_sig())          # v2
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


def test_legacy_sig_synthesis_retired_sig_required(journal, run_id) -> None:
    """R5 W1(ADR-0634,锁语义重推):影子期「缺位合成 legacy 签名」过渡
    路径已退役——写入口签名必填(缺位 = TypeError),显式 sig 的
    family/mode/actor 逐位落行(actor 在册,无空 actor 行)。本锁取代
    原「影子期合成签名逐 API 锁」(该锁钉的过渡语义已被直迁裁定取代)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    # 写入口缺 sig = 结构性拒绝(TypeError),禁静默合成空 actor 行
    # (此处刻意缺 sig——签名必填的调用期 TypeError 正是本锁的断言对象)
    for call in (
        lambda: bs.observe(bs.gold, 20),
        lambda: bs.carry(bs.gold, frame='p1-r1'),
        lambda: bs.write_prior(bs.hp, 82, evidence='prior:adr-0559'),
        lambda: bs.leave_screen(bs.shop),
        lambda: bs.write_logic(bs.free_refresh_balance, 2,
                               produced_by='RefreshShop'),
        lambda: bs.relay(bs.active_strategies, ['x']),
    ):
        try:
            call()
        except TypeError:
            pass
        else:
            raise AssertionError('写入口缺 sig 应显式 TypeError(legacy 合成已退役)')
    # 显式 sig 落行:family/mode/actor 逐位如实
    bs.observe(bs.gold, 20, sig=_sig())
    bs.write_logic(bs.free_refresh_balance, 2, produced_by='RefreshShop',
                   sig=_lsig())
    rows = journal.rows
    assert rows[0]['sig']['family'] == 'obs'
    assert rows[0]['sig']['mode'] == 'read'
    assert rows[0]['sig']['actor'] == 'TestSigWriter'
    assert rows[1]['sig']['family'] == 'logic_action'
    assert rows[1]['sig']['mode'] == 'compute'
    assert rows[1]['sig']['actor'] == 'TestSigWriter'


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
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    for sid in ('s_204999', 's_204100'):
        bs.effects.entries.append(ActiveEffect(
            spec=EffectSpec(id=sid, name=f'n{sid}', trigger=TriggerKind.NODE_ENTER,
                            duration=DurationKind.N_NODES,
                            category=EffectKind.ECONOMY,
                            payload=UnitBuffRef(effect_text='x'),
                            duration_nodes=3),
            source='strategy', acquired_t=1, remaining_nodes=3,
            remaining_uses=None))
    bs.observe(bs.gold, 5, sig=_sig())
    row = journal.rows[-1]
    effect_ids = [e['spec_id'] for e in row['state']['effects']]
    assert effect_ids == sorted(effect_ids), 'effects 按 spec id 规范化排序'


# ============================================================ 常开形态(R5 W1:journal 被动记录,无影子开关)


def test_no_journal_no_file_writes_still_flow(tmp_path) -> None:
    """常开化后形态(锁语义重推,原「影子关 = 零写入零版本消费」作废):
    无流水实例 = 行不落零文件,但写路径照常(字段写入/版本分配不受
    记录层影响——记录被动,ADR-0634)。"""
    reset_state_telemetry()
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    v0 = bs.write_seq
    bs.observe(bs.gold, 20, sig=_sig())
    assert journal_mod.state_journal_instance() is None
    assert bs.gold.value == 20, '无实例 = 行不落而字段照常写入'
    assert bs.write_seq == v0 + 1, '版本照常分配'
    # 不指到 tmp_path 的任何落盘:整体校验 = 装配目录树不存在(临时目录为空)
    assert not (tmp_path / 'state').exists()


def test_journal_passive_wiring_identical_trajectories(journal, run_id, tmp_path) -> None:
    """常开形态的不变式(原「影子开/关两态既有字段轨迹逐位一致」的承接,
    锁语义重推):账本接线与否,写路径的既有字段轨迹逐位一致——journal =
    被动记录,零行为分支(ADR-0634 直迁裁定:常开后记录不再是可开关面)。"""

    def _trajectory() -> list[tuple]:
        bs = GameState(schema_version=BS_SCHEMA_VERSION)
        bs.observe(bs.gold, 20, sig=_sig())
        bs.carry(bs.gold, frame='p1-r2', sig=_sig())
        bs.write_logic(bs.free_refresh_balance, 2, produced_by='RefreshShop',
                       sig=_lsig())
        bs.observe(bs.gold, 25, sig=_sig())
        bs.write_logic(bs.gold, 27, produced_by='TestSigWriter', sig=_lsig())
        bs.leave_screen(bs.shop, sig=_sig())
        bs.relay(bs.active_strategies, [' Handsome'], sig=_hsig())
        seq = []
        for name in ('gold', 'free_refresh_balance', 'shop', 'active_strategies'):
            f = getattr(bs, name)
            seq.append((name, f.value, f.source, f.evidence))
        return seq

    reset_state_telemetry()      # 先取「无实例」轨迹(fixture 的装配先复位)
    off = _trajectory()
    install_state_telemetry(tmp_path / 'state2' / 'journal.jsonl',
                            run_id_provider=tel_state.current_run_id)
    on = _trajectory()
    reset_state_telemetry()
    assert on == off, '账本接线对既有字段轨迹逐位零变更(被动记录)'


def test_run_id_empty_rejects_rows(journal, monkeypatch) -> None:
    """§3.2.3 局外写入拒绝:run_id 空 = 拒写假行(诚实缺失)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', '')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20, sig=_sig())
    assert journal.rows == [], '局外不写假行'
    assert bs.current_version() == 1, 'state 写入本体照常(版本照常分配)'


def test_journal_batch_flush(tmp_path, monkeypatch) -> None:
    """§3.2.3 落盘形态:内存追加 + 批量 flush(缓冲满阈值落盘);崩溃窗 = 未 flush 尾。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_flush')
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                flush_every=2,
                                run_id_provider=tel_state.current_run_id)
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 1, sig=_sig())
    assert not (tmp_path / 'state' / 'journal.jsonl').exists(), \
        '未到阈值不落盘(行在内存缓冲)'
    bs.observe(bs.gold, 2, sig=_sig())
    rows = _read_rows(tmp_path / 'state' / 'journal.jsonl')
    assert [r['v'] for r in rows] == [1, 2], '到阈值批量落盘'
    j.flush()
    assert journal_mod.state_journal_instance() is j


# ============================================================ 节点推进派生规则(§3.4;R3 本体)


def _prep(bs, plane: int, rnd: int, **kw) -> None:
    bs.observe_screen_context('货币战争-备战', phase_round=(plane, rnd), **kw)


def _derive_rows(journal_buffered, actor: str) -> list[dict]:
    """派生规则行(按 actor 取;四腿序键行均为逻辑层 family=logic_hook,
    备战帧顶栏原文行(top_bar_raw)才是观察层 family=obs,actor 归因不变
    ——单字段双层形态,用户终裁 2026-09-11)。"""
    return [r for r in journal.rows if r['sig']['actor'] == actor]


def test_prep_leg_advances_node_observed(journal, run_id) -> None:
    """§3.4.1 规则二(备战腿):干净备战帧 ∧ 顶栏可读 → write_logic(node_ord)
    = 解析顶栏文本成序键(ord = (plane-1)*9 + round);**逻辑层字段**(用户
    终裁 2026-09-11 字段层次终极版:四腿全部 write_logic,无 observe 写序键
    例外);顶栏原文的观察层落点 = top_bar_raw(独立字段)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 2, top_raw='备战阶段 1-2')
    assert bs.node_ord.value == 2
    assert bs.node_ord.source == 'logic', '序键 = 逻辑层(四腿全 write_logic)'
    assert bs.top_bar_raw.value == '备战阶段 1-2', '顶栏原文 = 观察层落点'
    assert bs.top_bar_raw.source == 'observation', '原文走 observe(观察层)'
    rows = _derive_rows(journal, 'derive_node_observed')
    assert len(rows) == 1
    assert rows[0]['after'] == 2
    assert rows[0]['field'] == 'node_ord'
    assert rows[0]['sig']['family'] == 'logic_hook', '序键行 = 逻辑层(logic_hook)'
    assert rows[0]['sig']['screen'] == '货币战争-备战'
    raw_rows = [r for r in journal.rows if r['field'] == 'top_bar_raw']
    assert raw_rows and raw_rows[0]['sig']['family'] == 'obs', \
        '原文行 = 观察层(observe 契约)'
    # 画面上下文对(§3.1.4):旧值转 prev,同 group
    assert bs.current_screen.value == '货币战争-备战'
    ctx_rows = [r for r in journal.rows if r['field'] == 'current_screen']
    assert ctx_rows and ctx_rows[0]['sig']['family'] == 'obs'


def test_prep_leg_same_value_reread_is_same_value_row(journal, run_id) -> None:
    """v3.1-N2 后到腿写字段裁定:备战重入重读(候选 == hist 且字段已同值)
    = 照录,行 = same_value 形态(计入行量预算);不构成第二次跃迁。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 2)
    _prep(bs, 1, 2)   # 同节点重入重读
    rows = _derive_rows(journal, 'derive_node_observed')
    assert len(rows) == 2
    assert rows[-1]['after'] == 2
    assert rows[-1]['same_value'] is True, '重入重读行 = same_value 形态'
    assert bs.node_hist_ord == 2


def test_effective_read_port_max_of_layer_and_hist(journal, run_id) -> None:
    """生效序读口 = max(node_ord 字段现值, hist)(effective_node_ord,派生
    计算非存储字段;单字段双层形态的用户终裁保留面):字段现值滞后于 hist
    的窗内不拖低生效序,弹窗腿候选照常越 hist 推进。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        effective_node_ord,
    )
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 5)                       # 腿 A 推进 hist=5
    # 种子:字段现值回拨到 4(低于 hist;单字段下现值=最近层写,种值只为
    # 单测读口判定,非旁路写入面)
    bs.node_ord = Field(value=4, source='logic')
    assert effective_node_ord(bs) == 5, '读口取 max(现值, hist),滞后不拖低'
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 5))
    # c=5==hist=5 → 候选=effective(5)+1=6 > 5 → 照常推进(去重键未占 6)
    assert bs.node_ord.value == 6, '生效读口不被滞后字段拖低,推进照常'
    assert bs.node_hist_ord == 6


def test_prep_leg_retrograde_rejected(journal, run_id) -> None:
    """R3 规则三:候选 < 现值(读值倒退 = 缓存滞后)拒绝即免疫。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 5)
    _prep(bs, 1, 4)   # 倒退
    assert bs.node_ord.value == 5


def test_prep_leg_authority_correction(journal, run_id) -> None:
    """字段层次终极版分层锁(用户终裁 2026-09-11):备战腿序键 = 逻辑层
    (write_logic),顶栏原文 = 观察层(observe)——两字段两层,序键无
    observe 写入路径;派生规则间的先后覆盖(后写层)不改变「序键恒逻辑层」
    形态。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    # 先让弹窗腿写逻辑层 2(开局形态候选 1 → 再次守卫通过候选 2)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node_ord.value == 2
    assert bs.node_ord.source == 'logic', '弹窗腿 = 逻辑层'
    # 备战帧顶栏真读 3 → 解析成序键后同样写逻辑层(层级不因腿而异)
    _prep(bs, 1, 3)
    assert bs.node_ord.value == 3
    assert bs.node_ord.source == 'logic', '备战腿序键同为逻辑层(终极形态)'


def test_popup_leg_advances_by_inference(journal, run_id) -> None:
    """§3.4.1 规则一(弹窗腿):prev ∈ 守卫集 ∧ current ∈ 弹窗族 → 推断 +1
    (R3 候选 = last+1;开局无前值 → 1)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    # 开局形态:守卫集(开局链/战斗等待)→ 商店面板先被采到,last 空 → 候选 1
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_ord.value == 1
    assert bs.node_ord.source == 'logic', '弹窗腿 = 逻辑层'
    # 常规形态:结算/战斗段之后快弹窗,c == last → 候选 = last+1
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node_ord.value == 2
    rows = _derive_rows(journal, 'derive_node_inferred')
    assert [r['after'] for r in rows] == [1, 2]


def test_popup_leg_prev_guard_rejects_reentry(journal, run_id) -> None:
    """R3 规则五:备战帧已分派后的弹窗 = 段内子阶段(prev ∉ 守卫集)零触发。
    单字段双层:node_ord 已由备战腿写 1(逻辑层 write_logic),弹窗腿零写的
    证据 = 推进行缺席 + hist 不动(不再断言字段 None)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 1)   # 备战帧先被采到(prev 备战 ∉ 守卫集)
    assert bs.node_ord.value == 1 and bs.node_ord.source == 'logic'
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_ord.value == 1 and bs.node_hist_ord == 1, \
        '商店访问重入不误触发(弹窗腿零写)'
    assert _derive_rows(journal, 'derive_node_inferred') == []


def test_popup_leg_cache_guard_and_fallback_to_prep_leg(
        journal, run_id) -> None:
    """R3 规则二③/规则五:缓存 c != last → 零触发交腿 A 兜底;后续弹窗帧
    prev ∈ 弹窗族 ∉ 守卫集 → 持续零触发;下一节点备战帧由腿 A 兜底推进。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 1)                     # 腿 A 先推进 node_ord=1(逻辑层)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 3))
    # c=ord(1,3)=3 != last=1 → 缓存守卫拒绝
    assert bs.node_ord.value == 1 and bs.node_hist_ord == 1, '缓存守卫拒绝零写'
    assert _derive_rows(journal, 'derive_node_inferred') == []
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    # prev=遭遇 ∉ 守卫集(R3 prev_branch 守卫:弹窗重入不触发)
    assert bs.node_ord.value == 1 and bs.node_hist_ord == 1
    assert _derive_rows(journal, 'derive_node_inferred') == []
    _prep(bs, 1, 2)                     # 下一节点备战帧 → 腿 A 兜底
    assert bs.node_ord.value == 2


def test_two_legs_same_transition_popup_first(journal, run_id) -> None:
    """v3.1-N2「两腿落同一跃迁」:弹窗腿先到先推进;备战帧后到同序 = 照写
    (same_value 形态)但去重键已占,不构成第二次跃迁。四腿同写逻辑层
    (字段层次终极版),层级不因腿而异。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_ord.value == 1           # 弹窗腿先到,先推进
    assert bs.node_ord.source == 'logic'
    n_inf = len(_derive_rows(journal, 'derive_node_inferred'))
    _prep(bs, 1, 1)                               # 备战帧后到(同序)
    backfill = _derive_rows(journal, 'derive_node_observed')
    assert len(backfill) == 1 and backfill[0]['after'] == 1
    assert backfill[0]['same_value'] is True, '同序补录行 = same_value 形态'
    assert len(_derive_rows(journal, 'derive_node_inferred')) == n_inf, \
        '推进不重复(去重键已占)'
    assert bs.node_hist_ord == 1 and bs.node_ord.value == 1
    assert bs.node_ord.source == 'logic', '序键恒逻辑层(终极形态)'


def test_popup_leg_resume_disabled(journal, run_id) -> None:
    """R3 规则六:恢复局 last 空时弹窗腿禁用不猜,交腿 A。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点', resumed=True)
    assert bs.node_ord.value is None


def test_popup_leg_without_cache_reading_disabled(journal, run_id) -> None:
    """弹窗腿缓存守卫输入缺位(phase_round 未带)→ 禁用不猜(有 last 时)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 1)
    bs.observe_screen_context('货币战争-战斗等待')
    bs.observe_screen_context('货币战争-遭遇节点')
    assert bs.node_ord.value == 1 and bs.node_hist_ord == 1, '守卫输入缺位零写'
    assert _derive_rows(journal, 'derive_node_inferred') == []


def test_derivation_fields_are_logic_hook_channel_only(journal, run_id) -> None:
    """§3.1.3 域准入(字段层次终极版):node_ord 序键 = 逻辑层(四腿全部
    logic_hook 行,无 observe 写序键路径);顶栏原文 top_bar_raw = 观察层
    (obs 族);上下文域唯一写点 = ①观察汇聚。影子行可对账。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 2, 1, top_raw='备战阶段 2-1')
    assert bs.node_ord.value == 10   # (2-1)*9+1
    writers = {(r['field'], r['sig']['family']) for r in journal.rows}
    assert ('node_ord', 'logic_hook') in writers, '序键行 = 逻辑层'
    assert ('top_bar_raw', 'obs') in writers, '原文行 = 观察层'
    assert ('prev_screen', 'obs') in writers and ('current_screen', 'obs') in writers


# ============================================================ R1.1 守卫族扩员+过渡帧行为(用户 2026-09-10 裁定)


def test_popup_leg_boss_briefing_predecessor_advances(journal, run_id) -> None:
    """boss 流推进锁(判定方案 E12 边序,证据 = screen_flow_timing.md
    #26/#14/#27/#29):boss 流 = 奖励关 → BOSS 简报(0p)→ 商店自动开,
    boss 节点恰一次推进。
    【R1.2 锁语义重推(锁红 ≠ 改动错)】本锁 R1.1 原形态钉「0p 纯前驱零腿,
    推进来自商店面板块弹窗腿」——四规则组终版(用户 2026-09-10 裁,设计
    v3.4 §3.4.1)把 0p 升格为规则③触发面(简报屏自身即确定性证据,推进
    = 当前+1、类型 = boss 随屏自带);守卫族成员终版(用户终裁 2026-09-11,
    ADR-0630 修订节·守卫族终版)0p/0q 出族——商店面板块后到弹窗腿被 prev 守卫结构性拒绝
    (缓存守卫 c=8≠hist=9 为第二道防线),级联双推进破口消除。锁意图
    (boss 节点恰一次推进、推进证据可归因)不变。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)                                    # 奖励关备战帧:腿 A 推 8
    assert SCREEN_BOSS_BRIEFING not in SCREEN_CONTEXT_GUARD_PREV, \
        '0p 出守卫族(专用腿③,残留 = 级联双推进破口,ADR-0630 修订节·守卫族终版)'
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)    # 规则③:当前+1 = 9
    rows3 = _derive_rows(journal, 'derive_node_boss_brief')
    assert [r['after'] for r in rows3 if r['field'] == 'node_ord'] == [9], \
        '0p 即推进(规则③,boss 节点序 = 当前+1,禁写死 round=9 的独立来源)'
    assert bs.node_hist_ord == 9
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 8))
    assert bs.node_ord.value == 9, '商店面板块后到:弹窗腿零触发(prev=0p 出族)'
    assert _derive_rows(journal, 'derive_node_inferred') == [], \
        '推进不重复(boss 节点恰一次推进,来源 = 规则③)'
    _prep(bs, 1, 9)                                    # boss 备战帧后到:同序补录
    backfill = _derive_rows(journal, 'derive_node_observed')
    assert backfill[-1]['after'] == 9
    assert backfill[-1]['same_value'] is True, 'boss 备战帧同序补录 = same_value 形态'
    assert backfill[-1]['sig']['family'] == 'logic_hook', '备战腿序键行 = 逻辑层'


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
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 40, sig=_sig())                                    # v1 (write)
    bs.note_obs_event(
        'arbitrate', 'level', {'old': 4, 'new': 213},
        verdict='保旧-单调守卫', obs_phase='prep_clean',
        sig=_sig(),
        evidence_refs=[{'shot': 'obs_conflict_level_x.webp'}])  # v2 (obs_event)
    bs.observe(bs.gold, 41, sig=_sig())                                    # v3 (write)
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


# ==================== 派生规则②③腿 + 类型派生(自 state_derivation_r12 归并) ====================
# 规则②:0q 位面过渡 → 逻辑节点 = (当前位面+1, 1),node_ord 单整数落写,零类型写;
# 规则③:0p BOSS 简报 → 当前节点+1,类型 = BOSS 随证据(禁写死 round=9);
# 类型派生:专属画面现身即定类型,商店面板不专属零写;类型冲突 obs_event 留证
# 最新直定赢;候选 ≤ hist 不写不锚(去重键 =(run_id, effective_ord));
# 固定次序 = 节点域判定 → 类型派生(同临界区)。设计正本 = 流程侧遥测设计
# v3.4 §3.4.1(四规则组终版);本节与上方规则①④双腿同簇互补。
# journal_buffered:flush 阈值拉高 = 锁读内存缓冲(四腿合成走查行量大,防早段
# 行被自动 flush 清出缓冲;flush 行为本体归本文件上方锁面)。

@pytest.fixture()
def journal_buffered(tmp_path):
    """同 journal fixture,flush_every 拉高版(派生腿走查用)。"""
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                flush_every=100000,
                                run_id_provider=tel_state.current_run_id)
    yield j
    reset_state_telemetry()


def _prep(bs, plane: int, rnd: int, **kw) -> None:
    """备战帧写点(规则①触发面;与 test_cw_state_journal 同款输入)。"""
    bs.observe_screen_context('货币战争-备战', phase_round=(plane, rnd), **kw)


def _wait(bs) -> None:
    """战斗/结算窗分支 token(守卫族成员;弹窗腿 prev 供给)。"""
    bs.observe_screen_context(BATTLE_WAIT_CONTEXT)


def _rows(journal_buffered) -> list[dict]:
    return list(journal_buffered.rows)


def _derive_rows(journal_buffered, actor: str) -> list[dict]:
    """派生规则行(按 actor 取,家族无涉——四腿序键行均为逻辑层
    family=logic_hook,备战帧顶栏原文行(top_bar_raw)才是观察层
    family=obs,actor 归因不变)。"""
    return [r for r in _rows(journal_buffered) if r['sig']['actor'] == actor]


def _advance_rows(journal_buffered) -> list[dict]:
    """推进写入行(跃迁本体):node_ord 字段、note 空、非 same_value
    (同序补录/重入重读行 = same_value 形态,非跃迁)。"""
    return [r for r in _rows(journal_buffered)
            if r['field'] == 'node_ord'
            and r['note'] == '' and r['same_value'] is False]


# ============================================================ 规则②:位面过渡腿


def test_plane_transition_leg_advances_next_plane_r1(journal_buffered, run_id) -> None:
    """§3.4.1 规则②:0q 被采到 → 逻辑节点 = (当前位面+1, 1)。位面来源① =
    调用方顶栏读数 phase_round;候选经坐标系公式 = plane*9+1(基 1)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)                                   # 腿 A:hist=9
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION,
                              phase_round=(1, 9))
    assert bs.node_ord.value == 10, '位面过渡 → (2,1) = ord 10'
    assert bs.node_hist_ord == 10
    rows = _derive_rows(journal_buffered, 'derive_node_plane_transition')
    assert len(rows) == 1
    assert rows[0]['after'] == 10
    assert rows[0]['sig']['screen'] == SCREEN_PLANE_TRANSITION
    assert rows[0]['sig']['family'] == 'logic_hook'
    # 过渡屏链 = 离开位面链(件 B v1.1 F1):下位面节点类型不可自定 → 零类型写
    assert bs.node.value is None, '0q 零类型写(下位面类型不由过渡屏定)'


def test_plane_transition_leg_plane_from_observed_mirror(journal_buffered, run_id) -> None:
    """规则②位面来源② = bs.node 观察镜像(plane;生产 cw_loop 分支写点不携
    phase_round,镜像顶栏遗产为当前位面来源)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.node, NodeKey(plane=1, round_num=9, kind='boss'),
               sig=_sig())
    _wait(bs)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION)
    assert bs.node_ord.value == 10
    assert bs.node_hist_ord == 10


def test_plane_transition_leg_plane_from_hist_derivation(journal_buffered, run_id) -> None:
    """规则②位面来源③ = hist 反解((hist-1)//9+1;镜像与 phase_round 双缺)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)                                   # hist=9,镜像 None
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION)  # 无 phase_round
    assert bs.node_ord.value == 10, 'hist=9 反解位面 1 → (2,1)=10'


def test_plane_transition_leg_reentry_deduped(journal_buffered, run_id) -> None:
    """共同语义:候选 ≤ hist 不写不锚——过渡屏多 loop pass 重复写点零重推
    (去重键已占,同序恰一次推进)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    n = len(_derive_rows(journal_buffered, 'derive_node_plane_transition'))
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    assert len(_derive_rows(journal_buffered, 'derive_node_plane_transition')) == n, \
        '重复 0q 零重推(重入拒绝)'
    assert bs.node_hist_ord == 10


def test_plane_transition_leg_no_plane_source_no_guess(journal_buffered, run_id) -> None:
    """开局过渡屏(投资环境前)无「当前位面」可推:三来源全缺 → 禁猜不写,
    交规则①④计数(v3.1-N5 同簇禁猜纪律)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION)
    assert bs.node_ord.value is None
    assert bs.node_hist_ord is None
    assert _derive_rows(journal_buffered, 'derive_node_plane_transition') == []


# ============================================================ 规则③:BOSS 简报腿


def test_boss_brief_leg_advances_current_plus_one_no_round9_hardcode(
        journal_buffered, run_id) -> None:
    """§3.4.1 规则③:0p 被采到 → 逻辑节点 = 当前节点+1。平面 2 简报 → 13
    (禁写死 round=9:boss 序位随位面格数/环境加节点漂移,简报证据自带类型,
    序位只由「当前+1」承载)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 2, 3)                                   # hist = 9+3 = 12
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    assert bs.node_ord.value == 13, '当前(2,3)+1 → ord 13(非写死 9)'
    assert bs.node_hist_ord == 13
    rows = [r for r in _derive_rows(journal_buffered, 'derive_node_boss_brief')
            if r['field'] == 'node_ord']
    assert len(rows) == 1 and rows[0]['after'] == 13
    assert rows[0]['sig']['screen'] == SCREEN_BOSS_BRIEFING


def test_boss_brief_leg_type_boss_written_with_advance(journal_buffered, run_id) -> None:
    """规则③类型随简报自带:推进同行为批次写 node.kind='boss'(类型派生
    经节点域,§3.1.3 节点域③格;(plane,round) 由目标序坐标系公式反解)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)                                   # hist=8
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    assert bs.node_ord.value == 9
    assert bs.node.value == NodeKey(plane=1, round_num=9, kind='boss'), \
        'boss 类型落当前+1 节点(1,9)'
    trows = _derive_rows(journal_buffered, 'derive_node_boss_brief')
    assert [r['field'] for r in trows] == ['node_ord', 'node'], \
        '规则③双写:先序后类型(固定次序)'
    assert trows[1]['after'] == {'plane': 1, 'round_num': 9, 'kind': 'boss'}


def test_boss_brief_leg_unknown_current_no_guess(journal_buffered, run_id) -> None:
    """当前节点未知(effective/hist 双空)→ +1 不可计算,禁猜不写。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    assert bs.node_ord.value is None
    assert bs.node.value is None
    assert _derive_rows(journal_buffered, 'derive_node_boss_brief') == []


def test_boss_brief_leg_repeat_deduped_type_idempotent(journal_buffered, run_id) -> None:
    """重复 0p(多 loop pass 写点):幂等锚(镜像 boss 节点键 = 本腿类型
    回执)命中 → 推进零重推零类型重写,简报屏重复现身零新增行。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    n = len(_derive_rows(journal_buffered, 'derive_node_boss_brief'))
    assert n == 2, '首轮双写:推进 + boss 类型(固定次序)'
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    rows = _derive_rows(journal_buffered, 'derive_node_boss_brief')
    assert len(rows) == n, '重复 0p 幂等锚命中,零新增行'
    assert bs.node_hist_ord == 9 and bs.node_ord.value == 9
    assert bs.node.value == NodeKey(plane=1, round_num=9, kind='boss')


# ============================================================ 混合场景:②③与①④去重交互


def test_boss_flow_rule3_suppresses_popup_double_advance(journal_buffered, run_id) -> None:
    """boss 流全序(判定方案 E12 边序:奖励关 → 0p → 商店自动开 → boss 备战):
    规则③在 0p 即推进(+boss 类型);后续商店面板块弹窗腿被结构性拒绝
    (prev=0p 出守卫族终版,用户终裁 2026-09-11,ADR-0630 修订节·守卫族终版;缓存守卫
    c=8≠hist=9 为第二道防线)零重推;boss 备战帧同序补录。boss 节点恰一次
    推进(级联双推进破口锁)。
    【R1.2 锁语义重推】本锁前身为 R1.1「0p 纯前驱零腿」形态锁——四规则组
    终版(用户 2026-09-10 裁)把 0p 升格为规则③触发面,推进 actor 由弹窗腿
    改为简报腿,锁意图(boss 节点恰一次推进)不变。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)                                     # 腿 A:hist=8
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)     # ③:9 + boss 类型
    assert bs.node_ord.value == 9 and bs.node_hist_ord == 9
    assert bs.node.value == NodeKey(plane=1, round_num=9, kind='boss')
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 8))
    assert bs.node_ord.value == 9, '商店面板块弹窗腿零触发(0p 出族+缓存守卫)'
    assert len(_derive_rows(journal_buffered, 'derive_node_inferred')) == 0, \
        '弹窗腿零触发(boss 节点已由③推进,禁双计)'
    _prep(bs, 1, 9)                                     # boss 备战帧后到
    backfill = _derive_rows(journal_buffered, 'derive_node_observed')
    assert backfill[-1]['after'] == 9
    assert backfill[-1]['same_value'] is True, '同序补录 = same_value 形态'
    assert backfill[-1]['sig']['family'] == 'logic_hook', \
        '备战腿序键行 = 逻辑层(字段层次终极版,四腿同层)'
    assert bs.node_hist_ord == 9


def test_plane_transition_flow_quiet_shop_popup(journal_buffered, run_id) -> None:
    """跨位面级联破口锁(ADR-0630 修订节·守卫族终版同族):0q 推进 (2,1) 后,商店面板块
    若被采到,弹窗腿被结构性拒绝(prev=0q 出守卫族终版;缓存 c=9≠hist=10
    双防)——位面切换后节点序不级联 +1;过渡屏自身零类型写边界同锁。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    assert bs.node_hist_ord == 10
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 9))
    assert bs.node_ord.value == 10, '0q 后商店弹窗腿零触发(0q 出族+缓存守卫)'
    assert len(_derive_rows(journal_buffered, 'derive_node_inferred')) == 0, \
        '跨位面节点恰一次推进(来源 = 规则②)'
    assert bs.node.value is None, '0q/商店零类型写(过渡屏=离开位面链)'


def test_plane_transition_then_prep_same_value_backfill(journal_buffered, run_id) -> None:
    """跨位面序:0q 推进 (2,1) 后,新位面首备战帧同序 = 观察层补录(腿 A 兜底
    确认,same_value 形态,禁二次跃迁);镜像不被②/①造帧(镜像=观察帧事实,
    漏斗现读更新)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 9)
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9))
    assert bs.node_hist_ord == 10
    _prep(bs, 2, 1)
    backfill = _derive_rows(journal_buffered, 'derive_node_observed')
    assert backfill[-1]['after'] == 10
    assert backfill[-1]['same_value'] is True, '同序补录 = same_value 形态'
    assert bs.node_hist_ord == 10 and bs.node_ord.value == 10
    assert bs.node.value is None, '②/①不造镜像帧(类型派生只在专属画面)'


# ============================================================ 字段层次终极版:观察层/逻辑层分层


def test_layer_split_raw_text_obs_ordinal_logic(journal_buffered, run_id) -> None:
    """字段层次终极版锁(用户终裁 2026-09-11):观察层(observe)只落画面
    原始读数——备战帧顶栏原文落 top_bar_raw;节点序键 = 逻辑层字段,四条腿
    (备战=解析顶栏文本成序键/弹窗/0q/0p)全部 write_logic,无 observe 写
    序键的例外;序键无原文不猜(top_raw 缺位 → 原文字段不写)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 3, top_raw='备战阶段 1-3')
    assert bs.top_bar_raw.value == '备战阶段 1-3'
    assert bs.top_bar_raw.source == 'observation', '原文 = 观察层(observe)'
    assert bs.node_ord.value == 3
    assert bs.node_ord.source == 'logic', '序键 = 逻辑层(write_logic)'
    raw_rows = [r for r in journal_buffered.rows if r['field'] == 'top_bar_raw']
    assert raw_rows and raw_rows[0]['sig']['family'] == 'obs'
    # 原文缺读形态:top_raw 缺位 → 原文字段不写(禁猜),序键照常派生
    bs2 = GameState(schema_version=BS_SCHEMA_VERSION)
    bs2.observe_screen_context('货币战争-备战', phase_round=(1, 5))
    assert bs2.top_bar_raw.value is None, '原文缺读不写(禁猜)'
    assert bs2.node_ord.value == 5, '序键派生不依赖原文字段(解析在派生段)'


# ============================================================ 类型派生:专属画面直定


def test_popup_dedicated_screens_direct_type(journal_buffered, run_id) -> None:
    """类型派生·直定半部:遭遇/补给/策略三专属屏现身即定该节点类型
    (词表 = boss/supply/encounter/invest 同源,禁新造 token);目标节点 =
    弹窗腿推进后 hist(弹窗屏属即将进入的节点)。弹窗屏无顶栏,缓存守卫
    输入 = 离开节点的顶栏遗产(c == hist 才推进)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
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
    trows = _derive_rows(journal_buffered, 'derive_node_type')
    assert [r['after']['kind'] for r in trows] == ['encounter', 'supply', 'invest']
    assert all(r['sig']['family'] == 'logic_hook' for r in trows)


def test_shop_panel_type_undetermined_no_write(journal_buffered, run_id) -> None:
    """商店面板不专属(任意节点类型都开商店)→ 类型「未定型」零写;
    查现行链接线候件 B 实施批(:func:`chain_node_type` 接口在位,本批不接)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _wait(bs)
    bs.observe_screen_context('货币战争-备战-开商店', phase_round=(1, 1))
    assert bs.node_ord.value == 1, '弹窗腿照常推进(序与类型分域)'
    assert bs.node.value is None, '商店类型未定型,零直定写'
    assert '货币战争-备战-开商店' not in SCREEN_NODE_TYPE_DIRECT
    assert _derive_rows(journal_buffered, 'derive_node_type') == []


def test_popup_reentry_type_targets_current_node(journal_buffered, run_id) -> None:
    """弹窗重入(prev ∉ 守卫集,零推进):类型目标 = hist(本弹窗所属节点
    已由首次现身推进)——同节点同类型 = same_value 形态。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _wait(bs)
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node_hist_ord == 1
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node_hist_ord == 1, '重入零推进(prev=遭遇 ∉ 守卫集)'
    assert bs.node.value == NodeKey(plane=1, round_num=1, kind='encounter'), \
        '类型目标 = 本弹窗所属节点'
    trows = _derive_rows(journal_buffered, 'derive_node_type')
    assert len(trows) == 2 and trows[-1]['same_value'] is True


def test_type_conflict_same_node_obs_event_newest_wins(journal_buffered, run_id) -> None:
    """类型冲突纪律(G10 同簇):同节点两直定值不一致 → obs_event 留证
    (禁静默)+ 最新直定值落位(最新观察=真相)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _wait(bs)
    bs.observe_screen_context('货币战争-遭遇节点', phase_round=(1, 1))
    assert bs.node.value == NodeKey(plane=1, round_num=1, kind='encounter')
    # 同节点异源直定:补给屏重入形态(prev ∉ 守卫集 → 目标仍 = hist=1)
    bs.observe_screen_context('货币战争-补给', phase_round=(1, 1))
    ev = [r for r in _rows(journal_buffered) if r['row'] == 'obs_event']
    assert len(ev) == 1, '类型冲突必留证(禁静默覆盖)'
    assert ev[0]['event'] == 'arbitrate' and ev[0]['field'] == 'node'
    assert ev[0]['observed'] == {'old_kind': 'encounter', 'new_kind': 'supply',
                                 'node_ord': 1}
    assert '冲突' in ev[0]['verdict']
    assert bs.node.value == NodeKey(plane=1, round_num=1, kind='supply'), \
        '最新直定赢(最新观察=真相)'


def test_derivation_fixed_order_node_domain_then_type(journal_buffered, run_id) -> None:
    """固定次序(用户终裁):写入落账后节点域判定 → 类型派生——0p 触发的
    推进行版本序先于类型行(同临界区顺序落账,无 hook 框架)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    _prep(bs, 1, 8)
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING)
    seq_field = [(r['v'], r['field']) for r in _rows(journal_buffered)
                 if r['field'] in ('node_ord', 'node')]
    pairs = [f for _, f in seq_field]
    assert pairs.index('node_ord') < pairs.index('node'), \
        '节点域判定先于类型派生(版本序可验)'


# ============================================================ chain_node_type 接口预留(件 B v1.1 §3.4)


def test_chain_query_reserved_interface_honest_none(journal_buffered, run_id) -> None:
    """件 B 接口语义(§3.4/§3.8):现行链该位原值零内建回落;链缺 = token
    None(「现行链不知道」,不是「该位不存在」);hu_dist 随 token,链缺恒
    None。当前生产零链写端(件 B §④B)→ 恒诚实 None。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    q = chain_node_type(bs, 1, 3)
    assert q.token is None and q.hu_dist is None, \
        '链缺 = 现行链不知道(零内建回落禁把基线/台账当兜底)'


def test_chain_query_position_addressing_on_injected_chain(journal_buffered, run_id) -> None:
    """链在位形态(测试注入;生产写端归件 B B-2/B-3):位寻址 = seq[i] 第
    i+1 轮(round 基 1,与 PlaneNodeLedger 下标语义同式);位越界 = None。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.node_path, ['reward', 'battle', 'supply'], sig=_lsig(),
                   produced_by='TestChainWriter')
    assert chain_node_type(bs, 1, 2).token == 'battle'
    assert chain_node_type(bs, 1, 4).token is None, '位越界 = 现行链不知道'
    assert chain_node_type(bs, 1, 1).token == 'reward'


# ============================================================ 四腿合成场景走查


def test_four_leg_synthetic_walkthrough_each_node_advanced_once(
        journal_buffered, run_id) -> None:
    """四腿合成走查(§3.4.3 写点完备性;开局→普通→boss→跨位面全流程一遍):
    每节点序恰一次推进(M3 验收判定基准 = 推进去重键);类型逐节点直定;
    每次跃迁恰一行推进写入。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
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
    adv = Counter(r['after'] for r in _advance_rows(journal_buffered))
    assert sorted(adv) == list(range(1, 11)), '节点序 1..10 全覆盖'
    assert all(c == 1 for c in adv.values()), \
        f'每节点序恰一次推进(去重键),实测:{adv}'
    by_leg = {(r['sig']['actor'], r['after']) for r in _advance_rows(journal_buffered)}
    assert ('derive_node_inferred', 1) in by_leg, '节点 1 = ④ 弹窗腿'
    assert {('derive_node_observed', n) for n in (5, 6, 7, 8)} <= by_leg, \
        '节点 5..8 = ① 备战腿'
    assert ('derive_node_boss_brief', 9) in by_leg, '节点 9 = ③ 简报腿'
    assert ('derive_node_plane_transition', 10) in by_leg, '节点 10 = ② 过渡腿'
    # 类型逐节点直定
    type_rows = _derive_rows(journal_buffered, 'derive_node_type') + \
        [r for r in _derive_rows(journal_buffered, 'derive_node_boss_brief')
         if r['field'] == 'node']
    kinds = {(r['after']['round_num'], r['after']['kind']) for r in type_rows
             if r['after'].get('plane') == 1}
    assert {(2, 'encounter'), (3, 'supply'), (4, 'invest'),
            (9, 'boss')} <= kinds, f'专属屏类型逐节点直定,实测:{kinds}'
    assert bs.node.value == NodeKey(plane=1, round_num=9, kind='boss'), \
        '镜像终态 = 最后专属屏类型帧(②/①不造镜像帧,漏斗现读更新)'
