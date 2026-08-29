# -*- coding: utf-8 -*-
"""动作索引定义约定测试锁(约定提案 .debug/temp/action_idx_contract_proposal.md
§6 步骤 3;AGENTS.md 硬约束「索引/槽位字段必须带定义注释」的机器面)。

三组锁,对应「动作索引五查」的人工面塌缩:

A. **deployed 域最小反例**(五查②:两笔引用同容器、前者先删)——ADR-0392
   deployed 槽位表化后锁**恒稳语义**:前者卖出置 None 不移位 → 后者索引
   恒指向生成期指向的原槽原人(旧「拒绝语义」锁随紧缩表示一并作废)。
B. **expect 写入端静态锁**(五查④:零写入=死防线)——扫族 A 全 Action 类
   的 expect 字段 × grep src/ 发射点赋值;零写入 → fail,除非字段定义处
   带 `expect-whitelist:` 豁免标记(草案级字段等有意不写入的场景)。
C. **sim↔执行对拍**(五查⑤:双实现同式地错)——同一动作序列过 simulate
   与生产守卫(sell_guard_ok),断言 accept/reject 一致。
D. **F2 型跨源共存锁**(ADR-0392 新增):同轮多源混合动作组,断言每个
   deployed_idx 执行后命中的恰是生成期指向的槽——槽位表不变量的端到端锁。
"""
from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    DEPLOYED_CAPACITY,
    BenchChar,
    CompTransaction,
    DeployMove,
    FillSpec,
    GameState,
    SellBench,
    SellDeployed,
    SwapDeploy,
    deployed_occupied,
    simulate,
)

_ROOT = Path(__file__).resolve().parents[5]          # 仓库根
_SRC = _ROOT / 'src' / 'sr_od' / 'application' / 'currency_war'
_CW_STATE = (_SRC / 'kernel' / 'cw_state.py').read_text(encoding='utf-8')


def _bc(name: str, slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


# ===== A. deployed 域最小反例(ADR-0392 恒稳语义)=====

def test_deployed_double_sell_same_batch_index_stable() -> None:
    """五查② deployed 域反例(ADR-0392 槽位表化后):同批两笔 SellDeployed,
    前者卖出**置 None 不移位** → 后者索引恒稳,命中的恰是生成期指向的原人。

    场景:deployed=[飞霄, 三月七];两笔都按生成期快照发射。第一笔卖飞霄
    (idx0)成功后,第二笔 idx1 **仍指向三月七**(不左移、不越界)——
    任意发射序零漂移。旧紧缩语义下本场景第二笔会漂移/越界(由 expect 拦),
    槽位表示下坑在结构上不存在。
    """
    st = GameState(deployed=[_bc('飞霄', 1), _bc('三月七', 2)])
    s1 = simulate(st, SellDeployed(deployed_idx=0, expect='飞霄'))
    sold = [a for a in s1.action_log if a.get('action') == 'SellDeployed']
    assert sold and sold[0].get('result') == 'applied'
    s2 = simulate(s1, SellDeployed(deployed_idx=1, expect='三月七'))
    # 恒稳语义:第二笔索引不变、照常命中三月七(applied,不是拒绝)
    sold2 = [a for a in s2.action_log if a.get('action') == 'SellDeployed']
    assert sold2[-1].get('result') == 'applied'
    assert sold2[-1].get('char') == '三月七'
    assert deployed_occupied(s2.deployed) == 0   # 两槽皆空(None 留槽)


def test_deployed_swap_after_sell_index_stable() -> None:
    """同反例的 SwapDeploy 面:第一笔卖出后 deployed_idx 恒稳,SwapDeploy
    命中生成期指向的槽(旧紧缩语义下 idx 漂移由 expect 拦,现恒稳直通)。"""
    bench = [None] * BENCH_CAPACITY
    bench[0] = _bc('黑塔', 1)
    st = GameState(deployed=[_bc('飞霄', 1), _bc('三月七', 2)], bench=bench)
    s1 = simulate(st, SellDeployed(deployed_idx=0, expect='飞霄'))
    s2 = simulate(s1, SwapDeploy(
        deployed_idx=1, bench_idx=0,
        expect_deployed='三月七', expect_bench='黑塔'))
    # idx1 恒指向三月七 → 换位照常 applied(不因前笔卖出而漂移)
    applied = [a for a in s2.action_log if a.get('action') == 'SwapDeploy'
               and a.get('result') == 'applied']
    assert applied, '槽位表恒稳:换位应照常执行'
    assert s2.deployed[1].char_id == '黑塔'      # 上场者落原槽
    assert s2.bench[0].char_id == '三月七'


def test_bench_domain_no_left_shift_by_construction() -> None:
    """五查② bench 域已结构性失效(ADR-0316):两笔 SellBench 同容器批,
    前者卖出置 None 不移位 → 后者索引恒指向原槽。锁「反例构造不出来」。"""
    bench = [None] * BENCH_CAPACITY
    bench[0] = _bc('飞霄', 1)
    bench[1] = _bc('三月七', 2)
    st = GameState(bench=bench)
    s1 = simulate(st, SellBench(bench_idx=0, expect='飞霄'))
    s2 = simulate(s1, SellBench(bench_idx=1, expect='三月七'))
    assert s2.bench[0] is None and s2.bench[1] is None, \
        'bench 域两笔卖出后两槽皆空(槽位表恒稳)'


# ===== B. expect 写入端静态锁(零写入=死防线)=====

def _all_action_classes() -> list[type]:
    from sr_od.application.currency_war.kernel import cw_state as m
    return list(getattr(m, 'Action').__args__)


def test_expect_fields_have_writers_or_whitelist() -> None:
    """族 A 全 Action 类的 expect* 字段:src/ 下必须存在发射点对其赋值;
    否则该字段定义处必须带 `expect-whitelist: <理由>` 注释。

    零写入 + 无豁免 = 死防线(校验逻辑再全也是恒放行/恒默认,五查④的
    机器化)。白名单豁免标记写在字段行或其相邻注释行,扫描窗口=字段行
    向上 6 行(覆盖 docstring 尾部与行内注释)。"""
    src_text = '\n'.join(
        p.read_text(encoding='utf-8')
        for p in _SRC.rglob('*.py'))
    offenders: list[str] = []
    for cls in _all_action_classes():
        for f in fields(cls):
            if not f.name.startswith('expect'):
                continue
            assigned = re.search(
                rf'\b{cls.__name__}\s*\([^)]*?\b{f.name}\s*=', src_text,
                re.DOTALL) is not None
            if assigned:
                continue
            # 无发射点赋值 → 查白名单标记(字段定义行本身;豁免标记约定
            # 写在字段行内或其注释块——窗口=字段行向上 6 行 + 本行)
            m = re.search(
                rf'^\s*{f.name}\s*:.*$', _CW_STATE, re.MULTILINE)
            wl = False
            if m:
                start = _CW_STATE.rfind('\n', 0, m.start())
                window = _CW_STATE[max(0, start - 600):m.end()]
                wl = 'expect-whitelist:' in window
            if not wl:
                offenders.append(f'{cls.__name__}.{f.name}')
    assert not offenders, (
        'expect 防线字段零写入且无 expect-whitelist 豁免(死防线): '
        f'{offenders};要么补发射点赋值,要么在字段定义处注释 '
        '`expect-whitelist: 理由`(如草案级字段待发射点接线)')


def test_whitelist_entries_must_declare_reason() -> None:
    """豁免标记必须带理由文本(`expect-whitelist:` 冒号后到行尾非空)——
    无理由的豁免=把死防线静默合法化。"""
    for m in re.finditer(r'expect-whitelist:[ \t]*([^\n]*)', _CW_STATE):
        reason = m.group(1).strip()
        assert reason, (
            'expect-whitelist 标记必须带豁免理由'
            '(草案级/待接线/有意观察位等),位置见 cw_state.py')


# ===== C. sim↔执行对拍(accept/reject 一致)=====

def test_sell_guard_aligns_with_simulate_semantics() -> None:
    """五查⑤对拍:sim 侧 simulate(SellBench) 与执行侧 sell_guard_ok 的
    拒绝语义,在同一「生成期期望名 vs 执行期槽内名」对上结论一致。

    sim 侧(cw_state L967-981):expect 非空且与槽内名不符 → rejected
    (stale_proposal);否则卖出。执行侧(shop.sell_guard_ok):expected
    非空且 live==expected 才放行——expected 空(sim 视为不校验)在执行侧
    是拒(执行器更严:无期望名=无从对拍,不点)。两表逐对对拍。"""
    from sr_od.application.currency_war.operations.prep.shop import (
        sell_guard_ok,
    )

    def sim_accepts(bench_idx: int, expect: str) -> tuple[bool, str | None]:
        bench = [None] * BENCH_CAPACITY
        bench[bench_idx] = _bc('飞霄', 1)
        st = GameState(bench=bench)
        out = simulate(st, SellBench(bench_idx=bench_idx, expect=expect))
        rejected = any(a.get('action') == 'SellBench'
                       and a.get('status') == 'rejected' for a in out.action_log)
        sold = out.bench[bench_idx] is None
        return (not rejected) and sold, out.bench[bench_idx - 1].char_id if False else None

    for bench_idx, expect, live in (
        (0, '飞霄', '飞霄'),    # 名符 → 两路都接受
        (0, '三月七', '飞霄'),  # 名不符 → 两路都拒
        (0, '', '飞霄'),        # sim 不校验(空 expect 放行);执行侧拒(无从对拍)
    ):
        sim_ok, _ = sim_accepts(bench_idx, expect)
        exec_ok = sell_guard_ok(expect or None, live)
        if expect:   # 有期望名的对上:两路结论必须一致
            assert sim_ok == exec_ok == (expect == live), (
                f'idx={bench_idx} expect={expect!r} live={live!r}: '
                f'sim={sim_ok} exec={exec_ok}(同式地错)')
        else:        # 空 expect 是两路的已声明语义差(执行侧更严),锁住不漂移
            assert sim_ok and not exec_ok, \
                '空 expect 语义差漂移:sim 放行(不校验)且执行侧拒(无从对拍)'


def test_deploy_move_index_semantics_sim_only() -> None:
    """DeployMove(族 A)索引语义冒烟:bench_idx=槽位下标,置 None 不移位
    ——与 SellBench 同域同规则(约定块双族对照表的 bench 行)。"""
    bench = [None] * BENCH_CAPACITY
    bench[3] = _bc('飞霄', 4)
    st = GameState(bench=bench)
    out = simulate(st, DeployMove(bench_idx=3, to_row='front', faction='巡海游侠'))
    assert out.bench[3] is None, '上场后槽位置 None(不下移填充)'
    assert len(out.bench) == BENCH_CAPACITY, '定长不变'
    assert [d.char_id for d in out.deployed if d is not None] == ['飞霄']


# ===== D. F2 型跨源共存锁(ADR-0392 新增)=====

def test_f2_cross_source_mixed_batch_slot_stable() -> None:
    """F2 跨源共存:同轮多源混合动作组(演进 CompTransaction + 换位通道
    SwapDeploy + 直卖通道 SellDeployed)对同一 deployed 槽位表按序消费——
    断言每个 deployed_idx 执行后命中的恰是生成期指向的槽。

    构造(全部 idx 按同一生成期快照发射,模拟 decide_prep 多源拼装):
    - deployed 槽位表:0=桑博 / 1=希儿 / 5=卡芙卡(front 0-3 / back 4-9)
    - 源 A(演进):CompTransaction undeploy 桑凡(槽 0)卖掉
    - 源 B(换位):SwapDeploy(槽 1)希儿 ↔ bench
    - 源 C(直卖):SellDeployed(槽 5)卡芙卡
    三笔任意序执行,每笔命中的都是生成期指向的原槽原人。"""
    deployed = [None] * DEPLOYED_CAPACITY
    deployed[0] = BenchChar(slot=1, char_id='桑博', faction='持续伤害',
                            position_pref='front')
    deployed[1] = BenchChar(slot=2, char_id='希儿', faction='量子同频',
                            position_pref='front')
    deployed[5] = BenchChar(slot=2, char_id='卡芙卡', faction='持续伤害',
                            position_pref='back')
    bench = [None] * BENCH_CAPACITY
    bench[0] = _bc('黑塔', 1)
    st = GameState(deployed=deployed, bench=bench, level=8)

    # 源 A/B/C 的动作(idx 全部按生成期快照,跨源拼接)
    tx = CompTransaction(deploy=[], undeploy=[], sell=[(0, 'deployed')],
                         reason='f2:evolve')
    swap = SwapDeploy(1, 0, reason='f2:swap',
                      expect_deployed='希儿', expect_bench='黑塔')
    sell_c = SellDeployed(5, reason='f2:recycle', expect='卡芙卡')

    cur = st
    for act in (tx, swap, sell_c):   # 生成序=执行序(拼装批)
        cur = simulate(cur, act)
        log = cur.action_log[-1]
        assert log.get('result') == 'applied', \
            f'槽位表恒稳:{type(act).__name__} 应命中生成期指向的槽: {log}'

    # 终态断言:每笔打的是生成期指向的原槽原人
    assert cur.deployed[0] is None        # 源 A 卖的是槽 0 桑博
    assert cur.deployed[1].char_id == '黑塔'   # 源 B 换的是槽 1(希儿下黑塔上)
    assert cur.deployed[5] is None        # 源 C 卖的是槽 5 卡芙卡
    assert deployed_occupied(cur.deployed) == 1
    # bench 侧:黑塔上场腾槽 0,希儿下场落槽(装备/对象随人走)
    assert cur.bench[0].char_id == '希儿'
