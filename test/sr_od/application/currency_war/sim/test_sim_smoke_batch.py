"""sim 冒烟批(全流程逐 seed 跑通判据;用户裁定 2026-10-13:冒烟只验
「能跑完不崩」,不设基线与 A/B 对照)。

测试面 = 「改后策略能跑完不崩」的批次级判据,**非行为正确性**(行为面由
各批单帧测试承载;用户裁定 2026-10-13 本迭代冒烟不设基线与 A/B 对照):

- 逐 seed 一整局:真 mandate_v1 策略 + 真 CwLoop 驱动 SimBackend,从
  reset 经 P1 → P2 → P3 到局终,op 执行零失败收口(死循环由看门狗轮限转
  execute 失败承载,崩溃由异常传播承载——两者都让本测试红);
- 终局合法形态 = 死亡(hp 归零且保底已用)/ 胜利(走完位面 3,披露键
  run_complete),两源都算「跑完」;
- 逐局统计行(复跑加 ``-s`` 可收):seed/终局源/终点/结算轮/驱动步/
  节点写数/末金/末级/hp 低点/耗时——冒烟报告的产出面,不作断言
  (统计数值随策略正常调整变动,断言即过时);
- 3.4 统计面扩展(统一保护集验证批授权,design §2.6 prereg 观察集
  取数口;同段落不作断言):过渡引擎读数 ``eng``/``p1eng``(点亮率
  /成型率/位面 1 形态分支的逐局输入,判定单一源 =
  ``cw_engine_facts.engines_count``)、位面 2 入口 ``p2``、位面 1 出口
  hp ``hp1``、买卡笔数 ``buys`` 与 M6 压牌库买因笔数 ``m2s``(kernel
  round_fresh_buys / BuyCard receipts 买因)、卖出笔数 ``sells``、
  位面 1 升级投入金 ``xp1``、零动作节点数 ``za``(02 §8 命题 A 零
  动作轮读数输入)、金流量 ``gin``/``gout``(花费率读数输入)、凑息
  凑息发出 ``nies``(凑息保护档阻断 irpb 与囤货臂出口键 pho/phfail
  已随 3.4 身份面退役删除)、压牌库臂 ``m6``/``dg``
  (press_buy_deployable_hit / dead_gold_press_buy_hit)、席满拒买族
  ``bf``(m6_bench_full 等三键合计,sells/xp1 为 receipts 窗口差分
  下界,门判定方向安全)。

运行原语 = ``test/harness/sim_backend_runner.py::run_sim_full_match``
(装配缝单一源:端口槽/容器绑定/时间冻结/journal 内存捕获/留证重定向);
崩点上下文(node/画面/步数)由运行原语以异常 note 注入。

种子集 = :data:`BATCH_SEEDS`(sim/conftest.py)= 2026-10-12 起 20 连号的
8 个代表号(2026-10-24 用户裁定:全量测试压到 ~3 分钟;选号跨全程均匀
取样)。20 连号全量普查不进常跑——修复批后普查时临时把 BATCH_SEEDS
换成 FULL_SWEEP_SEEDS(同文件,用完还原),依据 = 带病树同 20 seed
普查 13 崩(补给/备战节点 op 异常或 fail 重派触限)3 挂(备战决策环
自旋,pytest-timeout 不可杀),修复后同批 20/20 实测全跑通。与首局
验收已登记固定 seed〔20260923/7/61〕零重叠。**失败重派环分支放弃整局
覆盖**(普查中带重派环的局全部触限失败,无一整局跑通),该分支由
test_loop.py「op-fail 重派防线上限」测试单独承压。

整局批跑住 sim/conftest.py 共享夹具(会话级一次,与预注册判据批共用
产物,贵计算只算一次);崩溃局异常按 seed 留档、各参数用例自行
re-raise,保逐 seed 失败隔离。

运行成本:健康树整批 8 局实测约 1 分钟(会话内只跑一次);整批慢桶
登记(slow_marks.txt 逐 seed 条目),不进快集(``-m "not slow"`` 排除)。
复跑带 ``-s`` 可收逐局统计行;单条 timeout 放宽 300s(看门狗 1200 轮
触顶局需要余量,真挂死仍被兜住)。
"""
from __future__ import annotations

from typing import Any

import pytest
from test.sr_od.application.currency_war.sim.conftest import BATCH_SEEDS


def _transition_scan(journal_rows: list) -> dict:
    """扫 journal 投影行取过渡引擎/位面/买入读数(3.4 统计面扩展;
    design §2.6 prereg 观察集逐局取数口,冒烟报告产出面非断言)。

    判定单一源 = ``cw_engine_facts.engines_count``(仙舟3/列车2/持续
    伤害2 + 希儿系=希儿在场∧放大器≥2);board 域写行的 ``after`` 即
    kernel 全集口径计数(与 _recount_board 同形,流派/星徽并入),
    deployed 域写行供希儿系在场判据。字段:``eng_max`` = 局内最大
    体系达成数(点亮 = ≥1,成型 = ≥2 即两两组合);``p1_eng`` = 位面 1
    出口帧(末张 P1 板)达成数(形态分支);``lit`` = 达成体系名集;
    ``p2_entered`` = 是否进过位面 2;``buys`` = 买卡笔数(round_fresh_buys
    逐轮相位内最大长合计;该域按轮累积、轮间清零,取相位最大防重复计);
    ``hp1`` = 位面 1 出口 hp(末张 P1 板时刻的 hp 写行值)。
    """
    from sr_od.application.currency_war.knowledge.cw_engine_facts import (
        TRANSITION_TRAITS,
        engines_count,
    )

    node: dict | None = None
    dep_names: frozenset = frozenset()
    eng_max = 0
    p1_eng = 0
    lit: set[str] = set()
    p2_entered = False
    fresh_max: dict[tuple, int] = {}
    hp1: object = None
    for r in journal_rows:
        if r.get('row') != 'write':
            continue
        field = r.get('field')
        after = r.get('after')
        if field == 'node' and isinstance(after, dict):
            node = after
            if int(after.get('plane') or 1) >= 2:
                p2_entered = True
        elif field == 'deployed' and isinstance(after, dict):
            names: list[str] = []
            for zone in ('front_slots', 'back_slots'):
                for slot in (after.get(zone) or []):
                    unit = (slot or {}).get('unit') \
                        if isinstance(slot, dict) else None
                    cid = (unit or {}).get('char_id') \
                        if isinstance(unit, dict) else None
                    if cid:
                        names.append(str(cid))
            dep_names = frozenset(names)
        elif field == 'board' and isinstance(after, dict) and after:
            n = engines_count(after, dep_names)
            eng_max = max(eng_max, n)
            for bond, tier in TRANSITION_TRAITS:
                if after.get(bond, 0) >= tier:
                    lit.add(bond)
            if ('希儿' in dep_names
                    and (after.get('量子同频', 0) >= 2
                         or after.get('贝洛伯格', 0) >= 2)):
                lit.add('希儿系')
            if node is not None and int(node.get('plane') or 1) <= 1:
                p1_eng = max(p1_eng, n)
        elif field == 'round_fresh_buys' and isinstance(after, dict):
            phase = tuple(after.get('phase') or ())
            fresh_max[phase] = max(fresh_max.get(phase, 0),
                                   len(after.get('names') or []))
        elif field == 'hp' and node is not None \
                and int(node.get('plane') or 1) <= 1:
            hp1 = after
    return {'eng_max': eng_max, 'p1_eng': p1_eng, 'lit': lit,
            'p2_entered': p2_entered, 'buys': sum(fresh_max.values()),
            'hp1': hp1}


#: 动作类 receipts(零动作节点判定的「有动作」面):策略决策动作族。
#: 开局/读数开店/关店/出战属流程噪声不计。
_ACTION_OPS: frozenset[str] = frozenset({
    'CwActionBuyCardParam', 'CwActionSellBenchParam',
    'CwActionLevelUpParam',
    'CwActionDeployMoveParam', 'CwActionWearEquipParam',
    'CwActionCollectOreParam', 'CwActionRefreshShopParam',
    'CwActionSellDeployedParam',
})


def _xp_spend_of(item: dict) -> int:
    """单条升级 receipt 的花金(整批 = detail「花金N」)。"""
    import re
    op = str(item.get('op') or '')
    if op == 'CwActionLevelUpParam':
        m = re.search(r'花金(\d+)', str(item.get('detail') or ''))
        return int(m.group(1)) if m else 0
    return 0


def _action_scan(journal_rows: list) -> dict:
    """扫 journal 投影行取动作面读数(3.4 统计面扩展;design §2.6 prereg
    与 02 §8 命题 A 读数的逐局取数口,冒烟报告产出面非断言)。

    receipts 行为窗口累积快照(同形条目跨窗重复),新增量按「逐键计数
    单调上涨的差值」归属当前节点(journal 行序 = v 序,当前节点 = 最近
    一条 ``node`` 写行)。字段:``sells`` = SellBench 笔数;``xp1`` =
    位面 1 升级投入金;``za`` = 零动作节点数(无任何 :data:`_ACTION_OPS`
    新增量的节点;分母 = 去重节点数,boss 双写行按 (plane,round,kind)
    去重)。单调口径(计数只增不回退)宁少不重:窗口读侧清空后的重积
    不再计新,读数可能少量低估、不会虚增。
    """
    import json

    node_key: tuple | None = None
    node_seen: set[tuple] = set()
    active_nodes: set[tuple] = set()
    xp1 = 0
    sells = 0
    buy_reason: dict[str, int] = {}
    gin = 0.0
    gout = 0.0
    prev_gold: float | None = None
    cum: dict[str, int] = {}
    for r in journal_rows:
        if r.get('row') != 'write':
            continue
        field = r.get('field')
        after = r.get('after')
        if field == 'node' and isinstance(after, dict):
            node_key = (int(after.get('plane') or 0),
                        int(after.get('round_num') or 0),
                        str(after.get('kind') or ''))
            node_seen.add(node_key)
        elif field == 'receipts' and isinstance(after, list):
            cur: dict[str, dict] = {}
            for item in after:
                if not isinstance(item, dict):
                    continue
                key = json.dumps(item, sort_keys=True, ensure_ascii=False)
                slot = cur.get(key)
                if slot is None:
                    cur[key] = slot = {'item': item, 'n': 0}
                slot['n'] += 1
            for key, slot in cur.items():
                prev = cum.get(key, 0)
                if slot['n'] <= prev:
                    continue
                new_n = slot['n'] - prev
                cum[key] = slot['n']
                item = slot['item']
                op = str(item.get('op') or '')
                if node_key is None:
                    continue
                if op == 'CwActionSellBenchParam' \
                        and not item.get('reason'):
                    sells += new_n
                if op == 'CwActionBuyCardParam' \
                        and not item.get('reason'):
                    reason = str((item.get('action') or {}).get('reason')
                                 or '(empty)')
                    buy_reason[reason] = buy_reason.get(reason, 0) + new_n
                if op in _ACTION_OPS:
                    active_nodes.add(node_key)
                if node_key[0] == 1:
                    xp1 += _xp_spend_of(item) * new_n
        elif field == 'gold' and isinstance(after, (int, float)):
            if prev_gold is not None:
                delta = float(after) - prev_gold
                if delta > 0:
                    gin += delta
                else:
                    gout -= delta
            prev_gold = float(after)
    return {'sells': sells, 'xp1': xp1, 'za': len(node_seen - active_nodes),
            'node_count': len(node_seen), 'buy_reason': buy_reason,
            'gin': int(gin), 'gout': int(gout)}


def _protection_counters(gs: Any) -> dict:
    """策略器 cw4_counters 读数(3.4 统计面扩展;键缺失按 0 计)。

    策略器状态附着在局容器上(run.gs.strategy_state),局终存活即现值。
    ``nies`` = 节末凑息卖出计数(node_end_interest_sell,P56+T1 凑息门
    改域申报的发出面;凑息保护档阻断观测键 irpb 已随身份保护判据退役
    删除——统一让位优先级迭代 3.4);``m6`` = M6 压牌库买入计数
    (press_buy_deployable_hit,M6 子门读数);``dg`` = ②(b) 死金压牌库
    命中(dead_gold_press_buy_hit,相邻压牌库臂读数);``bf`` = 席满拒买
    族计数(m6_bench_full + dead_gold_press_bench_full_gate +
    press_buy_deployable_bench_full_gate,命题 A bench 满拒买读数)。
    (囤货臂键族 pho/phfail 已随囤货臂退役删除——3.4。)
    """
    state = getattr(gs, 'strategy_state', None)
    counters = getattr(state, 'cw4_counters', None)
    if not isinstance(counters, dict):
        counters = {}

    def _n(key: str) -> int:
        return int(counters.get(key) or 0)

    return {'nies': _n('node_end_interest_sell'),
            'm6': _n('press_buy_deployable_hit'),
            'dg': _n('dead_gold_press_buy_hit'),
            'bf': _n('m6_bench_full')
                  + _n('dead_gold_press_bench_full_gate')
                  + _n('press_buy_deployable_bench_full_gate')}


def _stats_line(seed: int, run: Any, duration_s: float) -> str:
    """逐局统计行(冒烟报告产出面;字段取现值快照,不做断言)。

    字段口径:终局源 = 死亡(``final_hp == 0``,保底已用归零)/ 胜利
    (走完位面 3,披露键 run_complete)/ abandoned(局未收口即停——
    execute 失败/崩溃局,终点字段仅记录崩点位置);节点写数 = 状态
    journal ``node`` 域写行数(每进一节点恰一写);驱动步 = 后端端口
    驱动计数(advance + click 合计)。
    """
    node = run.gs.node.value
    if not run.backend.done:
        terminal = 'abandoned'
    elif run.gs.hp.value is not None and int(run.gs.hp.value) == 0:
        # hp=0 是 falsy:禁 ``or`` 缺省式(None 哨兵混吃 0 → 死亡局
        # 误标 run_complete),None 判别必须显式 is not None。
        terminal = 'death'
    else:
        terminal = 'run_complete'
    node_writes = sum(1 for r in run.journal_rows
                      if r.get('row') == 'write' and r.get('field') == 'node')
    hp_trail = run.hp_trail or (0,)
    scan = _transition_scan(run.journal_rows)
    act = _action_scan(run.journal_rows)
    prot = _protection_counters(run.gs)
    lit_tag = ','.join(sorted(scan['lit'])) or '-'
    hp1 = scan['hp1']
    return (
        f'[smoke] seed={seed} terminal={terminal} '
        f'end=P{node.plane}r{node.round_num}({node.kind}) '
        f'settled={run.loop._settle.rounds_done} steps={run.backend._steps} '
        f'nodes={node_writes} gold={int(run.gs.gold.value or 0)} '
        f'level={int(run.gs.level.value or 0)} hp_min={min(hp_trail)} '
        f'fail_streak={run.loop._op_fail_streak_n} dur={duration_s:.1f}s '
        f'eng={scan["eng_max"]} p1eng={scan["p1_eng"]} lit={lit_tag} '
        f'p2={int(scan["p2_entered"])} hp1={hp1} buys={scan["buys"]} '
        f'm2s={act["buy_reason"].get("m2_stockpile", 0)} '
        f'sells={act["sells"]} xp1={act["xp1"]} za={act["za"]}/{act["node_count"]} '
        f'gin={act["gin"]} gout={act["gout"]} '
            f'nies={prot["nies"]} m6={prot["m6"]} dg={prot["dg"]} '
        f'bf={prot["bf"]}')


@pytest.mark.timeout(300)
@pytest.mark.parametrize('seed', BATCH_SEEDS)
def test_smoke_match_completes(seed: int,
                               sim_batch_runs: dict[int, Any]) -> None:
    """冒烟判据:该 seed 一整局跑完——收口成功 ∧ 局终位 ∧ 无 op fail
    连发 ∧ 真打过仗(结算轮 ≥ 1)。

    整局由 sim/conftest.py 共享夹具会话级跑一次;本测试只消费该 seed 的
    记录做断言。失败形态三源各自可见:崩溃 = 夹具留档异常在此 re-raise
    (traceback + 运行原语注入的崩点 note〔node/画面/步数〕);死循环 =
    看门狗轮限使 execute 收口失败;未到局终 = done 假。op fail streak
    触限虽被框架重派掩盖,也以计数暴露(连续 fail 达限即软死循环)。
    """
    entry = sim_batch_runs[seed]
    if entry.error is not None:
        print(f'[smoke] seed={seed} terminal=CRASH-exc '
              f'dur={entry.duration_s:.1f}s')
        raise entry.error
    run = entry.run
    print(_stats_line(seed, run, entry.duration_s))
    assert run.result is not None and run.result.success, \
        f'execute 未成功收口: {getattr(run.result, "status", "")!r}'
    assert run.backend.done, '后端局终位未置(done)'
    assert run.loop._op_fail_streak_n < 5, '外环 op 连续 fail 计数触限'
    assert run.loop._settle.rounds_done >= 1, '零结算轮(未打任何一场战斗)'
