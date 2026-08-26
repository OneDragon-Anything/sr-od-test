# -*- coding: utf-8 -*-
"""动作索引定义约定测试锁(约定提案 .debug/temp/action_idx_contract_proposal.md
§6 步骤 3;AGENTS.md 硬约束「索引/槽位字段必须带定义注释」的机器面)。

三组锁,对应「动作索引五查」的人工面塌缩:

A. **deployed 域最小反例**(五查②:两笔引用同容器、前者先删)——锁「坑
   真实存在且被 expect 拦住」的**现状拒绝语义**(不是锁左移正确;左移根
   治=deployed 槽位表化 ADR 议程,届时本锁改锁恒稳)。
B. **expect 写入端静态锁**(五查④:零写入=死防线)——扫族 A 全 Action 类
   的 expect 字段 × grep src/ 发射点赋值;零写入 → fail,除非字段定义处
   带 `expect-whitelist:` 豁免标记(草案级字段等有意不写入的场景)。
C. **sim↔执行对拍**(五查⑤:双实现同式地错)——同一动作序列过 simulate
   与生产守卫(sell_guard_ok),断言 accept/reject 一致。
"""
from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from sr_od.application.currency_war.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    DeployMove,
    FillSpec,
    GameState,
    SellBench,
    SellDeployed,
    SwapDeploy,
    simulate,
)

_ROOT = Path(__file__).resolve().parents[5]          # 仓库根
_SRC = _ROOT / 'src' / 'sr_od' / 'application' / 'currency_war'
_CW_STATE = (_SRC / 'cw_state.py').read_text(encoding='utf-8')


def _bc(name: str, slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


# ===== A. deployed 域最小反例(现状拒绝语义)=====

def test_deployed_double_sell_later_index_left_shift_intercepted() -> None:
    """五查② deployed 域反例:同批两笔 SellDeployed,前者先删 → 后者索引
    左移指向别人。锁现状防御:后笔带 expect 时被按名拦截(stale_proposal),
    **不误卖索引漂移后指到的人**。

    场景:deployed=[飞霄, 三月七];两笔都按生成期快照发射。第一笔卖飞霄
    (idx0)成功 pop 后,第二笔 idx1 已左移指向「空」(越界)→ 拒。
    第二笔换成 idx0(漂移后恰在界内、指向三月七)但 expect=飞霄 → 名不符
    拒。两形态都不得卖错人。"""
    for second_idx, second_expect, must_survive in (
        (1, '三月七', '三月七'),   # 左移越界:第二笔 no-op
        (0, '飞霄', '三月七'),     # 左移界内指向别人:expect 按名拦截
    ):
        st = GameState(deployed=[_bc('飞霄', 1), _bc('三月七', 2)])
        s1 = simulate(st, SellDeployed(deployed_idx=0, expect='飞霄'))
        sold = [a for a in s1.action_log
                if a.get('action') == 'SellDeployed']
        assert sold and sold[0].get('result') == 'applied'
        s2 = simulate(s1, SellDeployed(
            deployed_idx=second_idx, expect=second_expect))
        # must_survive 的人不得被误卖(仍 deployed 且存活)
        names = [d.char_id for d in s2.deployed]
        assert must_survive in names, \
            f'第二笔 {second_idx}/{second_expect} 误卖: {names}'
        # 第二笔必须被拒绝或 no-op(不得 applied 卖错人)
        applied2 = [a for a in s2.action_log
                    if a.get('action') == 'SellDeployed'
                    and a.get('result') == 'applied']
        assert len(applied2) <= 1, f'第二笔被应用(卖错人): {applied2}'


def test_deployed_swap_after_sell_rejected_by_expect() -> None:
    """同反例的 SwapDeploy 面:第一笔卖出后 deployed_idx 漂移,SwapDeploy
    的 expect_deployed 按名拦截(跨代际提案,坑同源)。"""
    bench = [None] * BENCH_CAPACITY
    bench[0] = _bc('黑塔', 1)
    st = GameState(deployed=[_bc('飞霄', 1), _bc('三月七', 2)], bench=bench)
    s1 = simulate(st, SellDeployed(deployed_idx=0, expect='飞霄'))
    s2 = simulate(s1, SwapDeploy(
        deployed_idx=1, bench_idx=0,
        expect_deployed='三月七', expect_bench='黑塔'))
    # idx1 已左移越界(len=1)→ 拒;三月七不上场不换走
    assert [d.char_id for d in s2.deployed] == ['三月七']
    assert s2.bench[0] is not None and s2.bench[0].char_id == '黑塔'


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
    from sr_od.application.currency_war import cw_state as m
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
    assert [d.char_id for d in out.deployed] == ['飞霄']
