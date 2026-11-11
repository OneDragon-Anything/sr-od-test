"""环境直发策略取卡调用点 sim 全链轻量局测试(镜像 src = sim/cw_sim_backend.py
的 ``_begin_node_window`` 直发发放事件;按流程级测试落位本目录,引擎驱动
助手 import 自 sim/test_sim_backend.py〔已登记超限拆分债文件,禁追加,只
import 复用不改;先例 = 本目录 test_env_bond_tier_sim_chain.py〕)。

测试面依据 = 原稿锁面 designs/
原稿锁面(§ 号 = 原稿节序)§4 锁 5(§2.2(e) 落地形态):
- 定向策略大师推进至 P3r5 → 无选卡屏、active_strategies +1(随机新策略,
  排除已拥有)、发放行金额 = 2×直发后持有数(直发本身触发金币分支的耦合锁,
  金额对账 = 发放行值 − 同窗轮首收入行值,与收入数值解耦);
- 直发后 excluded_invest 含到手名(全程去重契约锁);
- 窗口重放不双发(幂等守卫族语义锁,boss 先例同款断言位);
- 非调用点节点不发;表外环境不发。

追加面 = 概念股族模式卡(权威版本 = game_state/gain-chain.md §3 随机支/随机
装备支段 + fields.md §5.2 效果缺口与载体登记,语义 = 「概念股族模式卡
登记约定」):sim 局选追击概念股 → 写状态副本发放全链自动生效(选卡上报条件
解析注入流键 rng,状态副本里的值)——bench 增追击阵营域 1★ 一张、equips 增
简易类别一件;同 seed 重放确定性。

再追加面 = 概念股族展开卡(燃血概念股 id 1002 族内第二实例/能量概念股
id 1003 第三实例/列车同行概念股 id 1004 第四实例/银河学者概念股
id 1005 第五实例/贝洛伯格概念股 id 1006 第六实例/星间旅人概念股
id 1007 第七实例/仙舟概念股 id 1008 第八实例/狼狩概念股 id 1009
第九实例/昼之半神概念股 id 1010 第十实例/夜之半神概念股 id 1011
第十一实例/击破概念股 id 1012 第十二实例/群攻概念股 id 1013
第十三实例/减益概念股 id 1014 第十四实例,概念股族展开卡登记
约定,权威版本同上):与追击全链同构
仅值异——期望名改从对应阵营池/简易池现算(列车同行域 = 开拓者双形态
按角色位合并后 7 名池,采样即发放名恒欢愉;银河学者域无开拓者条目,
合并对本域零作用,池 = 原始域;贝洛伯格域 = 布洛妮娅双羁绊注册表修正
后 6 名池,独立单位照发;星间旅人域无开拓者条目,合并对本域零作用,
池 = 原始域 7 名;仙舟/狼狩域含专家,牌库时点池过滤后候选 = 域 −
未解锁专家,economy.md §8 用户裁定 2026-10-28;昼之半神/夜之半神/群攻
域 is_expert 全空 = 全员非专家,牌库时点过滤恒等,池 = 原始域 6/7/7 名;
击破域 9 名含专家加拉赫/姬子 2 名,牌库时点池过滤后候选 7 名,flows
轴纯流派域,独立条目「姬子·启行」flows 空非本域;群攻域 flows 轴纯
流派域,缇宝双羁绊「群攻、量子同频」照发〔量子同频无概念股卡,零联动〕、
翡翠为公司契约具名发放对象〔具名 vs 随机字段不相交〕;减益域 7 名含
专家佩拉 1 名,牌库时点池过滤后候选 6 名,flows 轴纯流派域,椒丘为
「持续伤害契约」具名发放对象〔具名 vs 随机字段不相交,照发〕、
千冶·刃双羁绊「燃血、减益」照发〔≠ 专家「刃」〕),
选卡助手按环境名
参数化(追击调用点缺省值不变)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _env_pick_backend,
    _force_settle,
    _seed_and_pick_env,
)

from sr_od.application.currency_war.data.cw_chars import chars_by_faction
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SCREEN_INVEST_STRATEGY,
    SimBackend,
    uninstall_backend,
)

_SIG = ChannelSig(family='logic_action', actor='T46PickGrantTest',
                  mode='compute')

_ENV = '策略大师'
_FOREIGN_ENV = '增发货币'   # ENV_ECONOMY 成员 ∉ ENV_PICK_GRANTS/ENV_POOL_REWRITE


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(先例 = sim/test_sim_backend 同名 fixture,fixture
    不可跨文件 import 故本文件自带同名同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _node_pos(b: SimBackend) -> tuple[int, int] | None:
    """当前节点序位(节点未进窗 = None)。"""
    node = b.gs.node.value
    return None if node is None else (node.plane, node.round_num)


def _drive_until_pos(b: SimBackend, pos: tuple[int, int],
                     limit: int = 512) -> None:
    """步进驱动至节点序位(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step——位面过渡屏在其分派表内,
    test_sim_backend._drive_env_grant_step 无该档,达 P3 必经)。"""
    for _ in range(limit):
        if _node_pos(b) == pos:
            return
        _drive_step(b, 37)
    raise AssertionError(f'驱动步数超限,未达 {pos}')


def _record_write_values(gs, monkeypatch: pytest.MonkeyPatch
                         ) -> list[tuple[str, str, str | None, object]]:
    """记录 (通道, 字段, evidence, 写入值) 四元写行(test_sim_backend
    ._record_all_writes 同式包装,本文件版增记 value 供发放金额对账;
    透传真实现零行为变化)。"""
    rows: list[tuple[str, str, str | None, object]] = []

    def _wrap_logic(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            rows.append((channel, gs._field_name(target), evidence, value))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    def _wrap_obs(real):
        def rec(target, value, *, evidence=None, sig, note=''):
            rows.append(('obs', gs._field_name(target), evidence, value))
            real(target, value, evidence=evidence, sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap_logic(gs.write_logic,
                                                       'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap_logic(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return rows


def _grant_gold_rows(rows: list[tuple[str, str, str | None, object]]
                     ) -> list[tuple[str, str, str | None, object]]:
    """直发金币分支写行(evidence = env_grant#<环境>#pick<k> 的 gold 行)。"""
    return [r for r in rows if r[0] == 'logic' and r[1] == 'gold'
            and r[2] and r[2].startswith('env_grant#策略大师#pick')]


def test_direct_grant_fires_at_p3r5_no_offer_screen(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """主锁(T-46 设计 §4 锁 5):策略大师局推进至 P3r5 窗口 → 直发恰
    一张(随机新策略,排除已拥有)、无选卡屏(窗后直落节点屏)、发放行
    金额 = 2×直发后持有数(直发经获得链自动触发金币分支)、到手名并入
    excluded_invest。结算恒胜桩保全程存活(死亡分支与本测无关)。
    非调用点节点不发:r4 窗开时点已入快照基线——若误挂 (3,4),直发卡已在
    held_before 内、r5 段零新发放行,本组断言即红(最近邻非调用点窗负例;
    表外环境负例另测)。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _ENV)
        assert gs.active_env.value == _ENV, '选卡事实前置'
        rows = _record_write_values(gs, monkeypatch)
        _drive_until_pos(b, (3, 4))
        held_before = list(gs.active_strategies.value or [])
        grants_before = len(_grant_gold_rows(rows))
        _drive_until_pos(b, (3, 5))
        # 无选卡屏:直发不开 offer,窗后直落节点屏
        assert b.screen_identity() != SCREEN_INVEST_STRATEGY, '无选卡屏'
        held_after = list(gs.active_strategies.value or [])
        assert len(held_after) == len(held_before) + 1, \
            f'r5 窗直发恰一张: {held_before} -> {held_after}'
        name = held_after[-1]
        assert name not in held_before, '随机新策略(排除已拥有)'
        # 直发本身触发金币分支(耦合锁):r4→r5 段恰一行新发放写,
        # 金额 = 2×直发后持有数(与同窗轮首收入解耦的差分;
        # 前段既有行 = offer 取卡分支各行,同 evidence 形态属预期)
        grants_after = _grant_gold_rows(rows)
        assert len(grants_after) == grants_before + 1, \
            f'r5 段恰一行新发放写: {grants_before} -> {len(grants_after)}'
        grant = grants_after[-1]
        assert grant[2] == f'env_grant#{_ENV}#pick{len(held_after)}', \
            f'evidence 携含本张 k: {grant[2]}'
        idx = rows.index(grant)
        income_value = next(r[3] for r in reversed(rows[:idx])
                            if r[1] == 'gold')
        assert int(grant[3]) - int(income_value) == 2 * len(held_after), \
            f'金额 = 2×含本张持有数: {grant[3]} - {income_value}'
        # 全程去重契约:到手名并入 excluded_invest
        assert name in b.excluded_invest, \
            f'到手名并入排除集: {name} ∉ {sorted(b.excluded_invest)}'
    finally:
        uninstall_backend()


def test_window_replay_no_double_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """窗口重放不双发(幂等守卫族语义锁,boss 先例同款断言位):P3r5 窗
    已开(直发已落)后,同节点二次 ``_begin_node_window`` 零二次发放
    (持有数与金不动)。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _ENV)
        _drive_until_pos(b, (3, 5))
        held_at_window = len(gs.active_strategies.value or [])
        assert held_at_window >= 1, '直发已落(窗口已开)'
        rows = _record_write_values(gs, monkeypatch)
        b._begin_node_window()
        assert len(gs.active_strategies.value or []) == held_at_window, \
            '重放零二次发放(持有不动)'
        assert _grant_gold_rows(rows) == [], '重放零发放写行'
    finally:
        uninstall_backend()


def test_foreign_env_no_grant_at_p3r5(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """表外环境不发(T-46 设计 §4 锁 5):登记表外环境(增发货币)局
    推进至 (3,5) 窗口 → 零直发(持有不动、零 env_grant gold 写行);
    direct 调用点查询 get None = 无直发的合法语义。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _FOREIGN_ENV)
        assert gs.active_env.value == _FOREIGN_ENV
        rows = _record_write_values(gs, monkeypatch)
        _drive_until_pos(b, (3, 4))
        held_at_r4 = len(gs.active_strategies.value or [])
        _drive_until_pos(b, (3, 5))
        assert len(gs.active_strategies.value or []) == held_at_r4, \
            '表外环境零直发(持有不动)'
        assert _grant_gold_rows(rows) == [], '表外环境零 env_grant 写行'
    finally:
        uninstall_backend()


# ============================================================ 概念股族全链
# (选追击概念股:随机阵营赠卡 + 随机简易装备经 kernel 获得链自动实机(live)和模拟器(sim)两边
# 生效,零 sim 新代码;权威版本 = game_state/gain-chain.md §3 随机支/随机
# 装备支段 + fields.md §5.2 效果缺口与载体登记。)

_CONCEPT_ENV = '追击概念股'


def _bench_units(gs) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star)
            for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def _pick_concept_stock_backend(seed: int,
                                env_name: str = _CONCEPT_ENV
                                ) -> tuple[SimBackend, list, list]:
    """驱动到环境选卡屏并选指定概念股(缺省 = 追击概念股,T-48 调用点
    不变;选卡前 bench 快照,防开局手牌巧合同阵营致成员计数失真;选卡
    步骤 = _seed_and_pick_env 同链展开,快照插入在播种 opts 之后、上报
    之前)。"""
    b = _env_pick_backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV, '驱动至环境选卡屏'
    b.gs.write_logic(b.gs.invest_env_opts, [env_name, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts',
                     sig=ChannelSig(family='logic_action', actor='Test',
                                    mode='compute'))
    bench_before = _bench_units(b.gs)
    env_out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0),
        ChannelSig(family='logic_action', actor='Test', mode='compute'))
    assert env_out.applied
    cw_sim_ports.declare_world(env_out.world_decl)
    return b, bench_before, _bench_units(b.gs)


def test_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链(gain-chain.md §3 随机支/随机装备支段:sim 状态副本
    真值 = 流键 rng,新形状经 kernel 获得链自动生效,零 sim 新代码):
    选追击概念股 → bench = 开局 4 + 追击阵营域 1★ 一张(星级 = spec
    先验;成员名 ∈ chars_by_faction('追击') 现算集,不手抄)、equips
    计数 +1 且名 ∈ equips_by_category('简易') 现算集;同 seed 重放
    确定性(写状态副本发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('追击')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(seed)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 追击阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_RANXUE_ENV = '燃血概念股'


def test_ranxue_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第二实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选燃血概念股 → bench = 开局 4 +
    燃血阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('燃血') 现算集,不手抄)、equips 计数 +1 且名 ∈ equips_by_category
    ('简易') 现算集;同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('燃血')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _RANXUE_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 燃血阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_ENERGY_ENV = '能量概念股'


def test_nengliang_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第三实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选能量概念股 → bench = 开局 4 +
    能量阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('能量') 现算集,不手抄)、equips 计数 +1 且名 ∈ equips_by_category
    ('简易') 现算集;同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('能量')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _ENERGY_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 能量阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_LIECHE_ENV = '列车同行概念股'


def test_lieche_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第四实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定 + 开拓者双形态角色位合并约定):选列车
    同行概念股 → bench = 开局 4 + 列车同行域 1★ 一张(星级 = spec 先验;
    成员名 ∈ 合并后池现算 = chars_by_faction('列车同行') 剔除
    '开拓者·记忆',采样即发放名恒欢愉,不手抄)、equips 计数 +1 且名 ∈
    equips_by_category('简易') 现算集;同 seed 重放确定性(写状态副本发放可
    重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('列车同行')} \
        - {'开拓者·记忆'}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _LIECHE_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 列车同行合并池现算集: {granted[0][0]}'
    assert granted[0][0] != '开拓者·记忆', '发放恒欢愉形态(键侧剔除)'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_YINHE_ENV = '银河学者概念股'


def test_yinhe_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第五实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选银河学者概念股 → bench = 开局 4 +
    银河学者阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('银河学者') 现算集,不手抄;双阵营成员真理医生等按 factions 轴在池,
    域内无开拓者条目,合并对本域零作用)、equips 计数 +1 且名 ∈
    equips_by_category('简易') 现算集(装备身份零先验,economy.md 四卡
    线索名单不含银河学者);同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('银河学者')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _YINHE_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 银河学者阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_BELOBOGE_ENV = '贝洛伯格概念股'


def test_beluoboge_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第六实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选贝洛伯格概念股 → bench = 开局 4 +
    贝洛伯格阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('贝洛伯格') 现算集,不手抄;域 = 布洛妮娅双羁绊注册表修正后 6 名,
    独立单位「大守护者」在候选内照发)、equips 计数 +1 且名 ∈
    equips_by_category('简易') 现算集(装备身份零先验,economy.md 四卡
    线索名单不含贝洛伯格);同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('贝洛伯格')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _BELOBOGE_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 贝洛伯格阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_XINGJIANLVREN_ENV = '星间旅人概念股'


def test_xingjianlvren_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第七实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选星间旅人概念股 → bench = 开局 4 +
    星间旅人阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('星间旅人') 现算集,不手抄;域 7 名全档覆盖,双阵营成员桑博/真理
    医生/瓦尔特按 factions 轴在池,域内无开拓者条目,合并对本域零作用)、
    equips 计数 +1 且名 ∈ equips_by_category('简易') 现算集(装备身份
    零先验,economy.md 四卡线索名单不含星间旅人);同 seed 重放确定性
    (写状态副本发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('星间旅人')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _XINGJIANLVREN_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 星间旅人阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_XIANZHOU_ENV = '仙舟概念股'


def test_xianzhou_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第八实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选仙舟概念股 → bench = 开局 4 +
    仙舟阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('仙舟') 现算集,不手抄;域 9 名中青雀/停云为专家,牌库时点池过滤后
    7 名候选——环境注册时点解锁恒空,economy.md §8 用户裁定 2026-10-28;
    赠卡名显式 ∉ EXPERT_CHARS 钉专家剔除生效;双阵营成员丹恒·饮月/彦卿
    按 factions 轴在池)、equips 计数 +1 且名 ∈ equips_by_category('简易')
    现算集(装备线索含仙舟→折叠小刀,economy.md:92 随家族键已登记,零新增
    申报);同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter

    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    faction_names = {c.name for c in chars_by_faction('仙舟')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _XIANZHOU_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 仙舟阵营池现算集: {granted[0][0]}'
    assert granted[0][0] not in EXPERT_CHARS, \
        f'赠卡名非专家(牌库时点过滤生效): {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_LANGSHOU_ENV = '狼狩概念股'


def test_langshou_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第九实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选狼狩概念股 → bench = 开局 4 +
    狼狩阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('狼狩') 现算集,不手抄;域 7 名中貊泽为专家,牌库时点池过滤后
    6 名候选——环境注册时点解锁恒空,economy.md §8 用户裁定 2026-10-28;
    赠卡名显式 ∉ EXPERT_CHARS 钉专家剔除生效;双阵营成员彦卿按 factions
    轴在池)、equips 计数 +1 且名 ∈ equips_by_category('简易') 现算集
    (装备身份零先验,economy.md 四卡线索名单不含狼狩,随家族键已登记,
    零新增申报);同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter

    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    faction_names = {c.name for c in chars_by_faction('狼狩')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _LANGSHOU_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 狼狩阵营池现算集: {granted[0][0]}'
    assert granted[0][0] not in EXPERT_CHARS, \
        f'赠卡名非专家(牌库时点过滤生效): {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_ZHOUZHIBANSHEN_ENV = '昼之半神概念股'


def test_zhouzhibanshen_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第十实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选昼之半神概念股 → bench = 开局 4 +
    昼之半神阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('昼之半神') 现算集,不手抄;域 6 名 is_expert 全空 = 全员非专家,
    牌库时点池过滤恒等零收窄,与仙舟/狼狩专家域相反型,池 = 原始域;
    独立单位成员昔涟照发,族级口径 economy.md:94)、equips 计数 +1 且
    名 ∈ equips_by_category('简易') 现算集(装备先验「昼神送轮滑鞋」随
    家族键已登记,零新增申报);同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter

    faction_names = {c.name for c in chars_by_faction('昼之半神')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _ZHOUZHIBANSHEN_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 昼之半神阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_YEZHIBANSHEN_ENV = '夜之半神概念股'
_JIPO_ENV = '击破概念股'
_QUNGONG_ENV = '群攻概念股'


def test_yezhibanshen_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第十一实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选夜之半神概念股 → bench = 开局 4 +
    夜之半神阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('夜之半神') 现算集,不手抄;域 7 名 is_expert 全空 = 全员非专家,
    牌库时点池过滤恒等零收窄,与仙舟/狼狩专家域相反型,池 = 原始域;
    独立单位成员昔涟照发,族级口径 economy.md:94)、equips 计数 +1 且
    名 ∈ equips_by_category('简易') 现算集(economy.md 四卡线索名单不含
    夜之半神 = 装备身份零先验,均匀 v0 + 按卡固定假说待校准随家族键在
    册,零新增申报);同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter

    faction_names = {c.name for c in chars_by_faction('夜之半神')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _YEZHIBANSHEN_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 夜之半神阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


def test_jipo_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第十二实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选击破概念股 → bench = 开局 4 +
    击破阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('击破') 现算集,不手抄;域 9 名中加拉赫/姬子为专家,牌库时点池
    过滤后 7 名候选——环境注册时点解锁恒空,economy.md §8 用户裁定
    2026-10-28;赠卡名显式 ∉ EXPERT_CHARS 钉专家剔除生效;双羁绊成员
    加拉赫/灵砂按 flows 轴在池)、equips 计数 +1 且名 ∈
    equips_by_category('简易') 现算集(economy.md 四卡线索名单不含
    击破 = 装备身份零先验,均匀 v0 + 按卡固定假说待校准随家族键已登记,
    零新增申报);同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter

    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    faction_names = {c.name for c in chars_by_faction('击破')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _JIPO_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 击破阵营池现算集: {granted[0][0]}'
    assert granted[0][0] not in EXPERT_CHARS, \
        f'赠卡名非专家(牌库时点过滤生效): {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


def test_qungong_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第十三实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选群攻概念股 → bench = 开局 4 +
    群攻流派域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('群攻') 现算集,不手抄;域 7 名 is_expert 全空 = 全员非专家,牌库
    时点池过滤恒等零收窄,与仙舟/狼狩专家域相反型,池 = 原始域;双羁绊
    成员缇宝按 flows 轴在池〔量子同频无概念股卡,零联动〕、域独占成员
    翡翠在公司契约具名发放对象之外照发随机池成员资格〔具名 vs 随机字段
    不相交〕)、equips 计数 +1 且名 ∈ equips_by_category('简易') 现算集
    (economy.md 四卡线索名单不含群攻 = 装备身份零先验,均匀 v0 + 按卡
    固定假说待校准随家族键已登记,零新增申报);同 seed 重放确定性(状态副本
    发放可重放)。"""
    from collections import Counter

    faction_names = {c.name for c in chars_by_faction('群攻')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _QUNGONG_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 群攻阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_JIANYI_ENV = '减益概念股'


def test_jianyi_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第十四实例(gain-chain.md §3 随机支/随机装备支段:sim
    状态副本里的值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选减益概念股 → bench = 开局 4 +
    减益流派域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('减益') 现算集,不手抄;域 7 名中佩拉为专家,牌库时点池过滤后
    6 名候选——环境注册时点解锁恒空,economy.md:96 用户裁定
    2026-10-28;赠卡名显式 ∉ EXPERT_CHARS 钉专家剔除生效;双羁绊成员
    千冶·刃按 flows 轴在池〔燃血域已落地,跨域共享〕;椒丘为持续伤害
    契约具名发放对象,具名契约不改随机池成员资格照发)、equips 计数 +1
    且名 ∈ equips_by_category('简易') 现算集(economy.md 四卡线索名单
    不含减益 = 装备身份零先验,均匀 v0 + 按卡固定假说待校准随家族键在
    册,零新增申报);同 seed 重放确定性(写状态副本发放可重放)。"""
    from collections import Counter

    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    faction_names = {c.name for c in chars_by_faction('减益')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _JIANYI_ENV)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 减益阵营池现算集: {granted[0][0]}'
    assert granted[0][0] not in EXPERT_CHARS, \
        f'赠卡名非专家(牌库时点过滤生效): {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'
