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

import pytest

from sr_od.application.currency_war.kernel import cw_state_journal as journal_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    BATTLE_WAIT_CONTEXT,
    BENCH_CAPACITY_DEFAULT,
    BS_SCHEMA_VERSION,
    SCREEN_BOSS_BRIEFING,
    SCREEN_CONTEXT_GUARD_PREV,
    SCREEN_PREP_FRAME,
    BenchSlot,
    BenchView,
    GameState,
    ChannelSig,
    Field,
    Unit,
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


def _derive_rows(journal, actor: str) -> list[dict]:
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
