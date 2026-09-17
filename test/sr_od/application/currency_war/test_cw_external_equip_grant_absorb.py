"""外部随机装备授予·精确吸收回归锁(2026-09-18 reconcile 第 4 例修复批)。

病理(重跑 3,round1 备战期,安灯 hook:reconcile_mismatch 停局):
投资环境概念股卡文含「开局时获得…初始简易装备」,授予的「生命之花」
无逻辑写端(effect-domain.md §6.4 随机资产面观察收口);后续穿戴扣减
投影(owned[和平手枪] -1)落在不含该件的逻辑库存上,下一备战帧 equips
实读 ['生命之花','拆装扳手'] 对逻辑 ['拆装扳手'] 必然失配 → 统一观察
对账安灯当推算 bug 停机。机制本身(实读多于逻辑)不是推算 bug,是申报
盲区:修法与 bench 申报表同型对称 = EXTERNAL_EQUIP_GRANTS +
external_equip_grant_pending + observe() 失配分支「纯超集+差额≤计数」
精确吸收(GameState._absorb_external_grant 双字段泛化,bench 语义不变)。

锁依据 = cw_mismatch_policy.EXTERNAL_EQUIP_GRANTS 申报注释的吸收语义
(数量确定、身份不可推算、「只多不少」形状确定)+ GameState._absorb_
external_grant docstring 命中条件全列。改锁先重推语义:本锁钉的是
「申报形状内吸收、形状外照停、字段互不越界」三向,禁为保绿机械跟绿。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel import (
    cw_mismatch_policy as _policy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    consume_defect_sink,
    register_sig_actors,
    set_defect_sink,
)

register_sig_actors('TestGrantWriter')

# ===== 事故帧实录(重跑 3 失配行语义;禁引 .debug 路径)=====

#: 逻辑库存 = 穿戴扣减投影(owned[和平手枪] -1)后的状态,不含概念股授予件。
_LOGIC_EQUIPS: tuple[str, ...] = ('拆装扳手',)
#: 实读 = 概念股初始简易装备「生命之花」+ 既有「拆装扳手」。
_READ_EQUIPS: tuple[str, ...] = ('生命之花', '拆装扳手')


def _logic_sig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='TestGrantWriter',
                      mode='compute')


def _obs_sig() -> ChannelSig:
    return ChannelSig(family='obs', actor='CwScreenPrep',
                      screen='货币战争-备战', mode='read',
                      quality={'equips': 'real_read'})


def _observe_capture(gs: GameState, value: list[str]) -> list[dict]:
    """观察写入 + 缺陷行捕获(sink 挂载/卸载成对;安灯钩子由调用方
    monkeypatch 注入 _policy._ANDON_HOOK)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.equips, value, sig=_obs_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    return rows


def _bench_view(units: tuple[tuple[str, int], ...],
                capacity: int = 9) -> BenchView:
    """(名, 星) 序列 → BenchView(前缀占槽,余槽 empty;单帧构造专用)。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=name, star=star, slot=i + 1))
             for i, (name, star) in enumerate(units)]
    while len(slots) < capacity:
        slots.append(BenchSlot(kind='empty'))
    return BenchView(slots=slots, capacity=capacity)


# ============================================================ 吸收主锁


def test_initial_equip_grant_absorbed(monkeypatch) -> None:
    """事故主形态(第 4 例):概念股初始简易装备申报(待吸收 1)+ 实读
    纯超集差额 1 → 吸收不停机。

    锁:无 observe_vs_logic_mismatch 行、安灯不被调、
    external_grant_absorbed 行在案(豁免 ≠ 消失)、待吸收件数清零、
    覆盖照常(观察赢,equips = 实读)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.equips, list(_LOGIC_EQUIPS),
                   produced_by='TestGrantWriter',
                   evidence='owned[和平手枪] -1(穿戴)', sig=_logic_sig())
    gs.exec_books.external_equip_grant_pending = 1

    rows = _observe_capture(gs, list(_READ_EQUIPS))

    assert gs.equips.value == list(_READ_EQUIPS), '观察赢覆盖照常'
    assert gs.exec_books.external_equip_grant_pending == 0, '吸收后待吸收件数清零'
    assert [r['kind'] for r in rows] == ['external_grant_absorbed'], \
        '落 external_grant_absorbed 台账行(无真失配行,可审计)'
    assert fired == [], '申报形状内:安灯不触发(不无脑停机)'


def test_initial_equip_grant_duplicates_absorbed_by_multiset(monkeypatch) -> None:
    """同名多件计件:待吸收 1 + 实读多 1 件同名装备(多重集差额 1)→
    吸收。锁:计件按多重集,非去重集合(手枪发烧友类同名多件卡形状)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.equips, ['折叠小刀'],
                   produced_by='TestGrantWriter',
                   evidence='proj_sell_equips_recover', sig=_logic_sig())
    gs.exec_books.external_equip_grant_pending = 1

    rows = _observe_capture(gs, ['折叠小刀', '折叠小刀'])

    assert [r['kind'] for r in rows] == ['external_grant_absorbed'], \
        '同名多件差额 1 在申报域内吸收'
    assert gs.exec_books.external_equip_grant_pending == 0


def test_equip_grant_without_declaration_still_stops(monkeypatch) -> None:
    """反腿:未申报(待吸收 0)时同形状实读 → 真失配照落照停。

    锁:吸收只认申报表,非全局放水——equips 失配的默认处置不变。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.equips, list(_LOGIC_EQUIPS),
                   produced_by='TestGrantWriter',
                   evidence='owned[和平手枪] -1(穿戴)', sig=_logic_sig())
    assert gs.exec_books.external_equip_grant_pending == 0

    rows = _observe_capture(gs, list(_READ_EQUIPS))

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '未申报的真失配安灯照触发'


def test_equip_grant_shape_guard_missing_unit(monkeypatch) -> None:
    """形状守卫·缺件腿:待吸收 1 但实读丢了逻辑态已有装备(非纯超集,
    卖出回收漏写类病灶形态)→ 真失配照落照停。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.equips, ['拆装扳手', '和平手枪'],
                   produced_by='TestGrantWriter',
                   evidence='owned[和平手枪] -1(穿戴)', sig=_logic_sig())
    gs.exec_books.external_equip_grant_pending = 1
    # 实读 = 授予「生命之花」但丢「和平手枪」(回收投影漏写形态)
    read = ['生命之花', '拆装扳手']

    rows = _observe_capture(gs, read)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '形状不符(缺件)交回三分流照停'
    assert gs.exec_books.external_equip_grant_pending == 1, \
        '未吸收:待吸收件数不动'


def test_equip_grant_shape_guard_reorder_only(monkeypatch) -> None:
    """形状守卫·差额 0 腿:多重集相等仅顺序错位(授予没发生,纯排序
    病灶形态)→ 真失配照落照停(差额 0 不在 (0, 待吸收] 域)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.equips, list(_READ_EQUIPS),
                   produced_by='TestGrantWriter',
                   evidence='proj_sell_equips_recover', sig=_logic_sig())
    gs.exec_books.external_equip_grant_pending = 1

    rows = _observe_capture(gs, list(reversed(_READ_EQUIPS)))

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '差额 0(纯顺序错位)不吸收'
    assert gs.exec_books.external_equip_grant_pending == 1


def test_equip_grant_surplus_over_declaration(monkeypatch) -> None:
    """形状守卫·超额腿:待吸收 1 但实读多出 2 件新装备 → 真失配照落
    (差额超申报 = 异常增益,不是本卡授予)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.equips, list(_LOGIC_EQUIPS),
                   produced_by='TestGrantWriter',
                   evidence='owned[和平手枪] -1(穿戴)', sig=_logic_sig())
    gs.exec_books.external_equip_grant_pending = 1
    read = ['生命之花', '折叠小刀', '拆装扳手']

    rows = _observe_capture(gs, read)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '差额超申报照停'
    assert gs.exec_books.external_equip_grant_pending == 1


def test_equip_pending_does_not_absorb_bench_mismatch(monkeypatch) -> None:
    """字段越界腿:装备待吸收 > 0 时 bench 真失配照停——双字段分派互不
    串账,装备闩不得吞备战席真投影 bug(bench 吸收只认 bench 申报表)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.bench, _bench_view((('艾丝妲', 1),)),
                   produced_by='TestGrantWriter',
                   evidence='proj_buy_place', sig=_logic_sig())
    gs.exec_books.external_equip_grant_pending = 3

    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.bench, _bench_view((('艾丝妲', 1), ('娜塔莎', 1))),
                   sig=ChannelSig(family='obs', actor='CwScreenPrep',
                                  screen='货币战争-备战', mode='read'))
    finally:
        set_defect_sink(None)
        consume_defect_sink()

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, 'bench 失配不因装备闩在场被吸收'
    assert gs.exec_books.external_equip_grant_pending == 3, \
        '装备待吸收件数不被 bench 分支消费'


# ============================================================ 申报表一致性


def test_external_grant_tables_match_official_text() -> None:
    """双申报表对官方卡文(data/cw_invest_data.py,值唯一源):
    ① 两表键必须全部命中官方卡名(防版本改名/移除后静默失联);
    ② 概念股 15 卡双腿各 +1(第 4 例收口标的,卡文含「开局时获得…初始
       简易装备」);③ 武装支援双腿数值;④ 代表性卡文数值抽查。"""
    from sr_od.application.currency_war.data.cw_invest_data import (
        PLAZA_AUGMENTS,
        PLAZA_PORTALS,
    )
    official = {a.name: a for a in PLAZA_AUGMENTS}
    official.update({q.name: q for q in PLAZA_PORTALS})
    for tbl in (_policy.EXTERNAL_BENCH_GRANTS, _policy.EXTERNAL_EQUIP_GRANTS):
        assert tbl, '申报表非空'
        orphans = [k for k in tbl if k not in official]
        assert not orphans, f'申报表孤儿键(官方卡文无此卡):{sorted(orphans)}'
        assert all(v > 0 for v in tbl.values()), '申报数量恒正'

    concept = ['追击概念股', '燃血概念股', '能量概念股', '列车同行概念股',
               '银河学者概念股', '贝洛伯格概念股', '星间旅人概念股',
               '仙舟概念股', '狼狩概念股', '昼之半神概念股', '夜之半神概念股',
               '击破概念股', '群攻概念股', '减益概念股', '战技点概念股']
    for name in concept:
        assert '开局时获得' in official[name].effect, name
        assert '初始简易装备' in official[name].effect, name
        assert _policy.EXTERNAL_BENCH_GRANTS[name] == 1, name
        assert _policy.EXTERNAL_EQUIP_GRANTS[name] == 1, name

    by_id = {a.id: a for a in PLAZA_AUGMENTS}
    assert by_id['102501'].name == '武装支援'
    assert '2个随机3费角色' in by_id['102501'].effect
    assert '1件随机简易装备' in by_id['102501'].effect
    assert _policy.external_grant_totals('武装支援') == (2, 1)
    assert _policy.external_grant_totals('武装支援+') == (1, 1)
    assert _policy.external_grant_totals('不存在的卡') == (0, 0)

    assert '获得2件随机简易装备' in official['数值碾压'].effect
    assert _policy.EXTERNAL_EQUIP_GRANTS['数值碾压'] == 2
    assert '获得5个【和平手枪】' in official['手枪发烧友'].effect
    assert _policy.EXTERNAL_EQUIP_GRANTS['手枪发烧友'] == 5
    assert '获得2个1费角色' in official['扩充团队'].effect
    assert _policy.EXTERNAL_BENCH_GRANTS['扩充团队'] == 5
    assert '以及1个【' in official['列车同行星徽套组'].effect
    assert _policy.EXTERNAL_EQUIP_GRANTS['列车同行星徽套组'] == 2
    assert '获得一个【追击星徽】' in official['追击邀请'].effect
    assert _policy.EXTERNAL_EQUIP_GRANTS['追击邀请'] == 1
    assert '获得【翡翠】和【砂金】' in official['公司契约'].effect
    assert _policy.EXTERNAL_BENCH_GRANTS['公司契约'] == 2
