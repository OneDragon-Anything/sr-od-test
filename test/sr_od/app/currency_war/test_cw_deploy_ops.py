"""test_cw_deploy_ops 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- a3_deploy_align: test_cw_a3_deploy_align.py
- a3_deploy_stock_engine: test_cw_a3_deploy_stock_engine.py
- r357_deploy_fence: test_cw_r357_deploy_fence.py
- r387_deploy_fill_vacancy: test_cw_r387_deploy_fill_vacancy.py
- r390_deploy_agent: test_cw_r390_deploy_agent.py
- r391_deploy_fills_cap: test_cw_r391_deploy_fills_cap.py
- r410_bench_units_conservation: test_cw_r410_bench_units_conservation.py
- r412_bench_free_gates: test_cw_r412_bench_free_gates.py
- w322_deploy_cap_readchain: test_cw_w322_deploy_cap_readchain.py
- w530_drag_reconcile: test_cw_w530_drag_reconcile.py
- test_drag_cw_char: test_drag_cw_char.py
- test_deploy_recipe_target: test_deploy_recipe_target.py
- test_empty_board_guard: test_empty_board_guard.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== a3_deploy_align ====================
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import select_deployments
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
    _deployment_order,
)
from sr_od.application.currency_war.strategies.impl.flow import (
    CwFlowStrategy,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)


# ADR-0517 迁移批:旧死码核具现(_decide_prep_action_impl 桥)退役,
# 直用活策略核(下述测试全部消费 live 接口)。
_FlowStrategy = MandateV1Live
def _bonds(cid: str) -> set[str]:
    ch = CHARACTERS[cid]
    return set(ch.factions) | set(ch.flows)


def _fac(cid: str) -> str:
    return CHARACTERS[cid].factions[0]


def test_op_order_ignition_first_key_probe_form() -> None:
    """裁决选项1 探针形态:bench 姬子(点火)+ 非引擎 tgt 件,deployed
    含三月七(列车1)+非引擎 → 姬子优先上(点火首键+桶序修正)。"""
    bench_id = {0: _bonds('姬子·启行'), 1: _bonds('大丽花')}
    bench_fac = {0: _fac('姬子·启行'), 1: _fac('大丽花')}
    deployed_fac = {'列车同行': 1, '盛会之星': 1}
    order = _deployment_order(
        tgt_idx=[1], rest=[0], bench_id=bench_id,
        bench_fac=bench_fac, deployed_fac=deployed_fac)
    assert order[0] == 0, (
        '点火引擎件(姬子,列车1→2)应先于 ignition=0 的非引擎 tgt 件'
        '(旧序 tgt 全体压 rest = 局64 引擎件躺 bench 的排序侧机制)')


def test_op_order_tgt_internal_ignition_first() -> None:
    """tgt 内部:点火 tgt 件(三月七,列车1→2)先于冗余 tgt 件
    (彦卿,仙舟已3 的第4人)。"""
    bench_id = {0: _bonds('彦卿'), 1: _bonds('三月七')}
    bench_fac = {0: _fac('彦卿'), 1: _fac('三月七')}
    deployed_fac = {'仙舟': 3, '列车同行': 1}
    order = _deployment_order(
        tgt_idx=[0, 1], rest=[], bench_id=bench_id,
        bench_fac=bench_fac, deployed_fac=deployed_fac)
    assert order[0] == 1, 'tgt 序点火首键:点火件(三月七)应排首'


def test_op_and_pure_function_order_aligned() -> None:
    """对齐锁(裁决③):同输入下 op 排序与纯函数上场序一致——
    bench=[冗余 tgt 彦卿, 点火 rest 三月七],deployed 仙舟3+列车1,
    target={仙舟}。两侧都应把三月七排第一。"""
    bench = [BenchChar(slot=1, char_id='彦卿', faction=_fac('彦卿')),
             BenchChar(slot=2, char_id='三月七', faction=_fac('三月七'))]
    deployed_fac = {'仙舟': 3, '列车同行': 1, '减益': 1}
    up, held = select_deployments(
        bench, deployed_cids={'藿藿', '丹恒·饮月', '爻光'},
        deployed_fac=deployed_fac, board=dict(deployed_fac), cap=6,
        target_factions=frozenset({'仙舟'}))
    assert up and bench[up[0]].char_id == '三月七', '纯函数:点火件先上'
    op_order = _deployment_order(
        tgt_idx=[0], rest=[1],
        bench_id={0: _bonds('彦卿'), 1: _bonds('三月七')},
        bench_fac={0: _fac('彦卿'), 1: _fac('三月七')},
        deployed_fac=deployed_fac)
    assert op_order[0] == up[0] == 1, (
        'op 排序与纯函数上场序对齐(ADR-0261 裁决:差异只剩读屏 vs 内存态)')


# ==================== a3_deploy_stock_engine ====================

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTERS as _a3_deploy_stock_engine_CHARACTERS,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    select_deployments as _a3_deploy_stock_engine_select_deployments,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _a3_deploy_stock_engine_BenchChar,
)


def _a3_deploy_stock_engine_bonds(cid: str) -> set[str]:
    ch = _a3_deploy_stock_engine_CHARACTERS[cid]
    return set(ch.factions) | set(ch.flows)


def _a3_deploy_stock_engine_fac(cid: str) -> str:
    return _a3_deploy_stock_engine_CHARACTERS[cid].factions[0]


def _deployed_fac(names: list[str]) -> dict[str, int]:
    fac: dict[str, int] = {}
    for c in names:
        for f in _a3_deploy_stock_engine_bonds(c):
            fac[f] = fac.get(f, 0) + 1
    return fac


def test_stock_engine_piece_deploys_game64_form() -> None:
    """局64 精确形态:deployed 饮月+三月七+3 非引擎(列车2 已达,仙舟 1<3),
    bench 姬子·启行×2,cap=7 → r288 配方底线门拦(ADR-0261 裁决选项3;
    原诊断锁断言「纯函数让姬子上场」,对齐后按新语义更新——op/sim
    在该形态一致拦截,sim 盲区消除)。"""
    dep = ['丹恒·饮月', '三月七', '阿格莱雅', '乱破', '大丽花']
    bench = [_a3_deploy_stock_engine_BenchChar(slot=i, char_id='姬子·启行',
                       faction=_a3_deploy_stock_engine_fac('姬子·启行'), star=1)
             for i in range(2)]
    up, held = _a3_deploy_stock_engine_select_deployments(
        bench, set(dep), _deployed_fac(dep), _deployed_fac(dep),
        cap=7)
    up_names = [bench[i].char_id for i in up]
    assert '姬子·启行' not in up_names, (
        '列车≥2 且仙舟<3 时列车件应被 r288 配方底线门拦下(与 op 对齐)')
    # 两张全部让位留 bench(仙舟基础线优先)
    assert len(held) == 2
    assert all(bench[h].char_id == '姬子·启行' for h in held)


def test_engine_piece_ignition_priority_with_vacancy() -> None:
    """点火形态:deployed 三月七(列车1)+3 非引擎,cap 宽 →
    r288 门不触发(列车<2),姬子(列车 1→2 恰点火)上场。"""
    dep = ['三月七', '阿格莱雅', '乱破', '大丽花']
    bench = [_a3_deploy_stock_engine_BenchChar(slot=0, char_id='姬子·启行',
                       faction=_a3_deploy_stock_engine_fac('姬子·启行'), star=1)]
    up, held = _a3_deploy_stock_engine_select_deployments(
        bench, set(dep), _deployed_fac(dep), _deployed_fac(dep),
        cap=8)
    assert [bench[i].char_id for i in up] == ['姬子·启行']
    assert not held


def test_r288_gate_releases_when_xianzhou_base_met() -> None:
    """门放行对照:仙舟≥3(基础线已满)时列车件不再让位——r288 只在
    「仙舟基础线未满」时拦,基础线满足后列车第 3 人照常上(门语义,
    非永久封顶)。"""
    dep = ['丹恒·饮月', '三月七', '藿藿', '爻光', '大丽花']
    bench = [_a3_deploy_stock_engine_BenchChar(slot=0, char_id='姬子·启行',
                       faction=_a3_deploy_stock_engine_fac('姬子·启行'), star=1)]
    up, held = _a3_deploy_stock_engine_select_deployments(
        bench, set(dep), _deployed_fac(dep), _deployed_fac(dep),
        cap=7)
    assert [bench[i].char_id for i in up] == ['姬子·启行']
    assert not held


# ==================== r357_deploy_fence ====================

from sr_od.application.currency_war.kernel.cw_line_defs import (
    ENGINE_FACTIONS,
    RECIPE_FACTIONS,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import _DEPLOY_FENCE


def test_deploy_fence_includes_bridge_factions() -> None:
    """r357 主锁(围栏=RECIPE ∪ ENGINE 桥派生单一源)。
    W126/ADR-0350:狼狩/贝洛伯格已随四体系封闭裁定退出围栏
    (hunt3/dot_belog 桥删除)——已封存体系件不再有框架豁免通道;
    桥派生(存活三桥=仙舟/dot/列车)与配方四老成员保持。"""
    assert frozenset(RECIPE_FACTIONS | ENGINE_FACTIONS) == _DEPLOY_FENCE
    assert '狼狩' not in _DEPLOY_FENCE, 'W126:已封存体系退出围栏'
    assert '贝洛伯格' not in _DEPLOY_FENCE, 'W126:已封存体系退出围栏'
    # 配方四老成员不丢
    for f in ('仙舟', '列车同行', '护盾', '持续伤害'):
        assert f in _DEPLOY_FENCE


def test_deploy_fence_still_blocks_pure_scatter() -> None:
    """纯散阵营(欢愉/公司/盛会之星)仍被围栏——r263b 纪律
    对非过渡配方阵营保持(防散件稀释)。"""
    for f in ('欢愉', '公司', '盛会之星', '夜之半神'):
        assert f not in _DEPLOY_FENCE, f'{f} 是散阵营,配方饥饿期必须留 bench'


# ==================== r387_deploy_fill_vacancy ====================

from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import _cap_roomy_of


def test_roomy_vacancy_more_than_must_up() -> None:
    """vacancy 6 > 必上 2(1 target+1 对)→ 富余,散牌放行填空。"""
    assert _cap_roomy_of(front_empty=3, back_empty=3, must_up=2) is True


def testtight_vacancy_le_must_up() -> None:
    """vacancy 2 ≤ 必上 3 → 紧张,配方围栏生效(散牌留 bench)。"""
    assert _cap_roomy_of(front_empty=1, back_empty=1, must_up=3) is False


def test_boundary_equal() -> None:
    """vacancy == must_up → 紧张(恰好够必上件,无富余)。"""
    assert _cap_roomy_of(front_empty=2, back_empty=1, must_up=3) is False


# ==================== r390_deploy_agent ====================


from sr_od.application.currency_war.kernel import cw_deploy_logic as dl
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _r390_deploy_agent_BenchChar,
)
from sr_od.application.currency_war.kernel.cw_state import GameState


def _bench(*pairs) -> list[_r390_deploy_agent_BenchChar]:
    return [_r390_deploy_agent_BenchChar(char_id=n, faction=f, slot=i + 1)
            for i, (n, f) in enumerate(pairs)]


def test_roomy_fill_vacancy_r387() -> None:
    """cap 富余:散牌填空(局62 r2 形态——cap3/board2/散件应上满)。"""
    bench = _bench(('三月七', '列车同行'), ('三月七', '列车同行'),
                   ('艾丝妲', '银河学者'), ('阿格莱雅', '昼之半神'))
    up, held = dl.select_deployments(
        bench, deployed_cids=set(), deployed_fac={'列车同行': 1},
        board={'列车同行': 1, '护盾': 1}, cap=3,
        target_factions={'列车同行'})
    assert len(up) == 3, f'富余应填满 cap:up={len(up)}'
    # 第 4 张(阿格莱雅,单张非对非 fence)cap 截断留 bench——合理
    # (cap=3 上满后第 4 张必留;艾丝妲借 fill_mode 上场)
    assert len(held) == 1


def test_target_bridge_carry_channel() -> None:
    """桥期 target 走 fw_carry 通道(r373:桥 framework 名单)。"""
    bench = _bench(('藿藿', '仙舟'), ('飞霄', '狼狩'), ('万敌', '夜之半神'))
    up, _ = dl.select_deployments(
        bench, deployed_cids=set(), deployed_fac={},
        board={}, cap=5,
        fw_carry={'藿藿', '丹恒·饮月'})
    assert 0 in up            # 藿藿(桥 carry)上
    assert 1 in up            # 飞霄:狼狩在 DEPLOY_FENCE(引擎桥派生)
    # 万敌:非 fence 非对,但 vacancy>2 fill_mode → 上


def test_depth_reads_deployed_not_bench() -> None:
    """_deployable_depth 口径=Σboard(W50 ADR-0312;空板=0,
    bench 有件不产生板深——r390「不数 bench」语义的现行形态)。"""

    from sr_od.application.currency_war.kernel.cw_battle_calib import _deployable_depth
    st = GameState()
    st.level = 5
    st.bench = _bench(('三月七', '列车同行'), ('三月七', '列车同行'),
                      ('艾丝妲', '银河学者'))   # bench 有件不产生板深
    st.deployed = []            # board 空 → 0(没上场就是 0)
    assert _deployable_depth(st) == 0


# ==================== r391_deploy_fills_cap ====================

from sr_od.application.currency_war.sim.checks.ledger import check_deploy_fills_cap


def _row(rn: int, deployed: int, cap: int, lag: int) -> dict:
    """合成行:deployed 名单 x0..xN;lag = 围栏认可件未上数。"""
    return {
        'plane': 1, 'round_num': rn,
        'state': {'deployed': [{'char_id': f'x{k}'}
                               for k in range(deployed)],
                  'cap': cap},
        'sim': {'deploy_lag_units': lag},
    }


def test_no_lag_not_reported() -> None:
    """lag=0(bench 有货但围栏合法 held:在场同名素材/跨线散牌)→ 不报
    (W767 643567 r5-r8 形态:旧口径误报,lag 口径不报)。"""
    rows = [_row(5, 4, 7, 0), _row(6, 4, 7, 0)]
    assert not check_deploy_fills_cap(rows)


def test_persistent_gap_reported() -> None:
    """连续 2 轮 deployed≤cap-2 且 lag≥2 → 报(r387 指纹)。"""
    rows = [_row(2, 1, 3, 2), _row(3, 1, 3, 2)]
    assert check_deploy_fills_cap(rows), '连续短缺应报'


def test_transient_gap_not_reported() -> None:
    """单轮短缺(下一轮补满)→ 不报(代理时序过渡态,game14)。"""
    rows = [_row(2, 4, 6, 2), _row(3, 6, 6, 2)]
    assert not check_deploy_fills_cap(rows)


def test_near_cap_not_reported() -> None:
    """差 1(贴 cap)→ 不报(cap 竞争合法保守)。"""
    rows = [_row(2, 2, 3, 2), _row(3, 2, 3, 2)]
    assert not check_deploy_fills_cap(rows)


def test_lag_one_not_reported() -> None:
    """lag=1(单件围栏认可未上)→ 不报(≥2 才成「系统性拦截」量级)。"""
    rows = [_row(2, 1, 3, 1), _row(3, 1, 3, 1)]
    assert not check_deploy_fills_cap(rows)


def test_growing_deployed_not_reported() -> None:
    """ADR-0260 增长豁免:连续短缺但 deployed 在增长 → 不报
    (deploy 代理先于买入,每轮买新件时账本恒见滞后一拍的
    「上轮买未部署」形态;engine_seed 放行后 seed4 实证)。"""
    rows = [_row(2, 4, 6, 2), _row(3, 5, 7, 2)]
    assert not check_deploy_fills_cap(rows)


# ==================== r410_bench_units_conservation ====================

from sr_od.application.currency_war.kernel.cw_battle_calib import _board_counts_of
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _r410_bench_units_conservation_BenchChar,
)
from sr_od.application.currency_war.sim.engine_p1 import START_BENCH_COUNT, simulate_p1


def test_units_conservation_across_bench_deployed() -> None:
    """单位守恒(bench+deployed+2×merges;ADR-0316 槽位模型下
    bench 只含未上阵占用槽):

    (ADR-0336 适配:decision_v2 的 CompTransaction 整档替换事务
    内部含 fill(shop 源买新件)/ sell(卖件),账本不落 tx 明细
    (只记 reason/result)——tx 轮重置守恒基线(该轮单位数作新
    起点),非 tx 段内 v1 同式守恒照验;tx 披露缺口登记 ADR-0336。)"""
    # 5→2 seed(2026-09-03 瘦身批,纪律 12:守恒不变量逐局成立,2 seed 足够)
    for seed in (0, 42):
        r = simulate_p1(seed, pool='fallback')
        base_units = START_BENCH_COUNT
        buys = sells = merges = 0
        for row in r.ledger:
            has_tx = any(a['__type__'] == 'CompTransaction'
                         and a.get('result') == 'applied'
                         for a in row['actions'])
            n_bench = len(row['state']['bench'])
            n_dep = len(row['state']['deployed'])
            if has_tx:
                # tx 单位变化不入账本:重置基线(ADR-0336 登记)
                base_units = n_bench + n_dep
                buys = sells = merges = 0
                continue
            for a in row['actions']:
                if a['__type__'] == 'BuyCard':
                    buys += 1
                elif a['__type__'] == 'SellBench':
                    sells += 1
            merges += (row['sim'].get('merges') or 0)
            expect = base_units + buys - sells - 2 * merges
            assert n_bench + n_dep == expect, (
                f'seed{seed} r{row["round_num"]}: bench{n_bench}'
                f'+deployed{n_dep} != {expect}'
                f'(单位守恒破坏:bench 表示 / 双重计数 / 合并计数漂移)')


def test_deployed_accumulates_monotonic() -> None:
    """deployed 跨轮累积(生产跟踪态),轮间单调不减。

    (ADR-0336 适配:decision_v2 的 CompTransaction 整档替换会
    合法缩减 deployed(换人下场)——tx 轮跳过;非 tx 轮单调照验。)"""
    for seed in (0, 5, 11):
        r = simulate_p1(seed, pool='fallback')
        prev = 0
        for row in r.ledger:
            n = len(row['state']['deployed'])
            has_tx = any(a['__type__'] == 'CompTransaction'
                         and a.get('result') == 'applied'
                         for a in row['actions'])
            if has_tx:
                continue   # tx 整档替换合法缩减排面(ADR-0336)
            assert n >= prev, (
                f'seed{seed} r{row["round_num"]}: deployed {n}<{prev}'
                '(累积态不应缩减——无下场机制)')
            prev = n


def test_board_is_deployed_faction_counts() -> None:
    """state.board = deployed 羁绊全集聚合(ADR-0312 W50 口径;
    per-unit 单一源 unit_bond_tags——本锁锁「sim 维护 board ← 聚合」
    的接线,per-unit 值由 test_cw_w50_board_caliber 直锁)。"""
    from sr_od.application.currency_war.kernel.cw_bond_equips import unit_bond_tags
    r = simulate_p1(7, pool='fallback')
    for row in r.ledger:
        expect: dict[str, int] = {}
        for d in row['state']['deployed']:
            tags = unit_bond_tags(_ns(d))
            if tags:
                for t in tags:
                    expect[t] = expect.get(t, 0) + 1
                continue
            f = d.get('faction') or ''
            if f and f != '?':
                expect[f] = expect.get(f, 0) + 1
        assert row['state']['board'] == expect


def _ns(d: dict):
    from types import SimpleNamespace
    return SimpleNamespace(
        char_id=d.get('char_id') or '',
        position_pref=d.get('position_pref') or 'back',
        faction=d.get('faction') or '',
        equips=d.get('equips') or [])


def test_board_counts_of_fullset_caliber() -> None:
    """_board_counts_of:羁绊全集(factions+flows+independent+星徽装备
    贡献;ADR-0312 W50);未识别回退 faction 单标签(空/'?' 不计)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    dep = [
        _r410_bench_units_conservation_BenchChar(slot=1, char_id='希儿', faction='量子同频'),
        _r410_bench_units_conservation_BenchChar(slot=2, char_id='银狼', faction='量子同频'),
        _r410_bench_units_conservation_BenchChar(slot=3, char_id='', faction='?'),
        _r410_bench_units_conservation_BenchChar(slot=4, char_id='银狼LV.999', faction='星核猎手',
                  equips=['欢愉卡带']),
    ]
    expect: dict[str, int] = {}
    for d in dep[:2] :
        ch = CHARACTERS[d.char_id]
        for t in (*ch.factions, *ch.flows, ch.independent):
            if t:
                expect[t] = expect.get(t, 0) + 1
    # 银狼LV.999 = 星核猎手 + 欢愉(flow) + 头号玩家(独立)+ 卡带欢愉 +1
    expect['星核猎手'] = expect.get('星核猎手', 0) + 1
    expect['欢愉'] = expect.get('欢愉', 0) + 2
    expect['头号玩家'] = expect.get('头号玩家', 0) + 1
    assert _board_counts_of(dep) == expect
    assert _board_counts_of([]) == {}


# ==================== w322_deploy_cap_readchain ====================

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from sr_od.application.currency_war.obs.cw_observation import (
    _level_from_xp,
    _parse_xp_pair,
    read_level_raw_opt,
    read_xp_progress,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_DIR = Path(__file__).parent
_FIX_LV3 = _DIR / 'cw_conflict_lv3_xp24_prep_frame.png'   # 备战 1-2:Lv.3、XP 2/4、paddle 3/3
_FIX_LV4 = _DIR / 'cw_conflict_lv4_xp26_prep_frame.png'   # 备战 1-4:Lv.4、XP 2/6、paddle 3/4


def _load_fixture_rgb(path: Path) -> np.ndarray:
    img_bgr = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {path}'
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB


# ===== 锁①:_parse_xp_pair 两级解析(今日冲突帧 OCR 形态回归) =====

def test_parse_xp_pair_normal_slash() -> None:
    """斜杠正常可读:直读 X/Y(既有契约形态)。"""
    assert _parse_xp_pair('2/6') == (2, 6)
    assert _parse_xp_pair('4/20') == (4, 20)
    assert _parse_xp_pair('0/4') == (0, 4)


def test_parse_xp_pair_slash_read_as_one() -> None:
    """斜杠被识成数字 '1'(冲突帧实测 "214"/"416"):按等级表分母先验插 '/'。"""
    assert _parse_xp_pair('214') == (2, 4)      # 23dee97a 帧 "2/4" 实读形态
    assert _parse_xp_pair('416') == (4, 6)      # 77a0e871 帧 "4/6" 实读形态
    assert _parse_xp_pair('2140') == (2, 40)    # 6 级门槛 40 同族
    # 非法拆分不采:任何 '1' 位拆出的分母都不在等级表 → None(先验守卫,防普通数字串误拆)
    assert _parse_xp_pair('919') is None       # 9/9:9 非合法分母
    assert _parse_xp_pair('515') is None       # 5/5 同理
    assert _parse_xp_pair('购买经验') is None


def test_parse_xp_pair_slash_noise_normalized() -> None:
    """数字间非数字单字符 → '/' normalize(D-53 同款,先行级)。"""
    assert _parse_xp_pair('2l6') == (2, 6)
    assert _parse_xp_pair('2/6/') == (2, 6)     # 尾部残留不干扰首个 X/Y


# ===== 锁①b:'1' 拆分的上下文等级先验收紧(M2 obs 根因修复:lv 3↔4 乒乓潜在源) =====

def test_parse_xp_pair_split_prior_consistent_accepted() -> None:
    """先验一致:拆分照常采信(收紧不伤真读)。"""
    assert _parse_xp_pair('214', expected_level=3) == (2, 4)    # lv3 帧 "2/4" 实读形态
    assert _parse_xp_pair('416', expected_level=4) == (4, 6)    # lv4 帧 "4/6" 实读形态
    assert _parse_xp_pair('416', expected_level=3) is None      # 分母 6→lv4 ≠ 先验 3 → 失读


def test_parse_xp_pair_split_prior_mismatch_rejected() -> None:
    """先验不一致 → 判失读(None):分母 4=lv3 独有且单数字易混,
    真 lv4 帧斜杠误识串("3/4"→"314")被拆成 (3,4) 不再反推 lv3(乒乓潜在源根除)。"""
    assert _parse_xp_pair('314', expected_level=4) is None      # (3,4)→lv3 ≠ 先验 4 → 拒
    assert _parse_xp_pair('314', expected_level=3) == (3, 4)    # 先验 lv3 → 采信
    assert _parse_xp_pair('214', expected_level=4) is None      # (2,4)→lv3 ≠ 先验 4


def test_parse_xp_pair_split_no_prior_keeps_old_behavior() -> None:
    """无先验(None/0,新局无 last_level_obs)→ 旧行为放行(向后兼容)。"""
    assert _parse_xp_pair('214', expected_level=None) == (2, 4)
    # normalize 斜杠路径不受先验收紧(XP 纠正 OCR 的主权通道,ADR-0129)
    assert _parse_xp_pair('2l6', expected_level=3) == (2, 6)


def test_read_xp_progress_prior_passthrough(test_context: SrTestContext, monkeypatch) -> None:
    """read_xp_progress 透传 expected_level 到 '1' 拆分判定。"""
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': '214'})()])
    assert read_xp_progress(test_context, None, expected_level=3) == (2, 4)
    assert read_xp_progress(test_context, None, expected_level=4) is None
    assert read_xp_progress(test_context, None) == (2, 4)       # 无先验旧行为


def test_read_level_uses_session_prior_for_xp_split(test_context, monkeypatch) -> None:
    """read_level 的 XP 反推先验 = session.last_level_obs(read_game_state 同源)。"""
    from sr_od.application.currency_war.obs.cw_observation import read_level
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': '314'})()])   # "3/4" 斜杠识成 '1';等级区 314 越界 → 直读失读
    _sess = type('S', (), {'last_level_obs': 4})()
    _match = type('M', (), {'session': _sess})()
    monkeypatch.setattr(test_context, 'cw_match', _match, raising=False)
    # 先验 lv4:"314" 拆 (3,4) 反推 lv3 与先验矛盾 → XP 失读 → 落 _expected_level(1,1)
    lv = read_level(test_context, None, plane=1, round_num=1)
    assert lv != 3
    # 无先验(新局 last=0)旧行为:拆分采信 → 反推 lv3
    _sess0 = type('S', (), {'last_level_obs': 0})()
    monkeypatch.setattr(test_context, 'cw_match', type('M', (), {'session': _sess0})(), raising=False)
    assert read_level(test_context, None, plane=1, round_num=1) == 3


# ===== 锁②:read_level_raw_opt 无兜底契约 + 放大读不破坏 mock 注入 =====

def test_read_level_raw_opt_contract(test_context: SrTestContext, monkeypatch) -> None:
    """直读无兜底:读到返回值,失读/越界返 None(完成验证依赖此契约)。"""
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': 'Lv.3'})()])
    assert read_level_raw_opt(test_context, None) == 3
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': 'Lv.'})()])
    assert read_level_raw_opt(test_context, None) is None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': '14'})()])
    assert read_level_raw_opt(test_context, None) is None   # LEVEL_MAX=10 域外按失读


def test_read_xp_progress_keeps_domain_guard(test_context: SrTestContext, monkeypatch) -> None:
    """read_xp_progress sanity 不放松:cur>next / 无 X/Y 仍 None(既有契约,修法不放宽)。"""
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': '20/4'})()])
    assert read_xp_progress(test_context, None) is None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': '购买经验'})()])
    assert read_xp_progress(test_context, None) is None


# ===== 锁③:今日冲突帧真实 OCR 回归(修复前 lv_raw/xp 双 None;修复后全可读) =====

def test_conflict_frame_lv3_xp24_readable(test_context: SrTestContext) -> None:
    """23dee97a 帧:修复前「文本-等级」与 XP 双失读(→启发式虚高 5);修复后 lv=3、xp=(2,4)。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect
    if _area_rect(test_context, '文本-等级') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    screen = _load_fixture_rgb(_FIX_LV3)
    assert read_level_raw_opt(test_context, screen) == 3
    assert read_xp_progress(test_context, screen) == (2, 4)
    assert _level_from_xp((2, 4)) == 3


def test_conflict_frame_lv4_xp26_readable(test_context: SrTestContext) -> None:
    """6f41536e 帧:修复前 XP 失读(lv OCR 偶读 4,XP 兜底缺位);修复后 xp=(2,6)。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect
    if _area_rect(test_context, '文本-等级') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    screen = _load_fixture_rgb(_FIX_LV4)
    assert read_level_raw_opt(test_context, screen) == 4
    assert read_xp_progress(test_context, screen) == (2, 6)
    assert _level_from_xp((2, 6)) == 4


def test_conflict_frame_level_resolves_in_domain(test_context: SrTestContext) -> None:
    """端到端:冲突帧三源解析后 level 与 paddle cap 自洽入域(cap≥level),域守卫不再拒信。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect
    from sr_od.application.currency_war.obs.cw_observation import (
        _expected_level,
        _resolve_level,
        read_deploy_cap_debounced,
    )
    if _area_rect(test_context, '文本-等级') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    for path, truth_lv, truth_cap in ((_FIX_LV3, 3, 3), (_FIX_LV4, 4, 4)):
        screen = _load_fixture_rgb(path)
        lv_raw = read_level_raw_opt(test_context, screen)
        xp_lv = _level_from_xp(read_xp_progress(test_context, screen))
        # plane/round 传帧内真值(该帧备战阶段;phase_round 非本批修复对象)
        level, _ev, _auth = _resolve_level(lv_raw, _expected_level(1, truth_lv), xp_lv, 0)
        assert level == truth_lv, f'{path.name}: level={level} 应为 {truth_lv}'
        cap = read_deploy_cap_debounced(test_context, screen, level)
        assert cap == truth_cap, f'{path.name}: cap={cap} 应为 {truth_cap}(拒信=None 即回归)'


def test_prep_actions_level_raw_uses_shared_reader() -> None:
    """完成验证直读与决策读链单一源(prep_actions._read_level_raw 委托 read_level_raw_opt)。"""
    import inspect

    from sr_od.application.currency_war import prep_actions
    src = inspect.getsource(prep_actions._read_level_raw)
    assert 'read_level_raw_opt' in src, '完成验证直读应委托单一源(重复裁剪 OCR 实现已删)'


# (r412 腾席链门测试组 + 空板出战守卫测试组已随 ADR-0517 迁移批死码清理
# 删除——被测体 = flow.py 死码簇;_bc 助手保留,w530 期望态锁组消费)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _r412_bench_free_gates_BenchChar,
)

def _bc(slot: int, char_id: str, faction: str = '?', star: int = 1,
        pref: str = 'back') -> _r412_bench_free_gates_BenchChar:
    return _r412_bench_free_gates_BenchChar(slot=slot, char_id=char_id, faction=faction, star=star,
                     position_pref=pref)


# ==================== w530_drag_reconcile ====================

from pathlib import Path as _w530_drag_reconcile_Path

from sr_od.application.currency_war.kernel.cw_prep_actions import DeployMove
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    SellBench as _w530_drag_reconcile_SellBench,
)
from sr_od.application.currency_war.kernel.cw_prep_expect import (
    compare_drag_expect,
    compute_drag_expect,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _w530_drag_reconcile_BenchChar,
)
from sr_od.application.currency_war.telemetry import defects, recorder
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def _w530_drag_reconcile_bc(slot: int, char_id: str, pref: str = 'back') -> _w530_drag_reconcile_BenchChar:
    return _w530_drag_reconcile_BenchChar(slot=slot, char_id=char_id, star=1, position_pref=pref)


# ===== ① 期望态计算真值表(动作意图 → 期望态)=====

def test_expect_sell_truth_table():
    """卖出:源槽身份已知 → 期望=该槽身份消失;未识别 → None 不评。"""
    exp = compute_drag_expect(_w530_drag_reconcile_SellBench(slot=3), [_w530_drag_reconcile_bc(3, '希儿')], [])
    assert exp is not None
    assert (exp.kind, exp.identity, exp.from_slot) == ('sell', '希儿', 3)
    assert compute_drag_expect(_w530_drag_reconcile_SellBench(slot=5), [_w530_drag_reconcile_bc(3, '希儿')], []) is None
    assert compute_drag_expect(_w530_drag_reconcile_SellBench(slot=1), [], []) is None


def test_expect_deploy_move_place_vs_swap():
    """拖到部署排:空槽落位=原空+目标该角色;异名占位=互换;同名占位=
    merge_mechanics.md §3 恒成立约束「场上同名同星≤1」+部署链 5.1.7
    不变量「同角色在场只1」下不可达(游戏拒绝)→ None 不评;源身份
    未识别 → None。"""
    exp = compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                         ),
                              [_w530_drag_reconcile_bc(2, '希儿')],
                              [_w530_drag_reconcile_bc(2, '花火', 'front')])
    assert exp is not None
    assert exp.target_kind == 'place'
    assert (exp.identity, exp.from_slot, exp.target_row, exp.target_slot) == \
        ('希儿', 2, 'front', 1)

    exp2 = compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                          ),
                               [_w530_drag_reconcile_bc(2, '希儿')],
                               [_w530_drag_reconcile_bc(1, '景元', 'front')])
    assert exp2 is not None
    assert exp2.target_kind == 'swap'
    assert exp2.target_identity == '景元'

    assert compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                          ),
                               [_w530_drag_reconcile_bc(2, '希儿')],
                               [_w530_drag_reconcile_bc(1, '希儿', 'front')]) is None
    assert compute_drag_expect(DeployMove(from_slot=4, to_row='front', to_slot=1,
                                          ),
                               [_w530_drag_reconcile_bc(2, '希儿')], []) is None


def test_expect_non_drag_action_is_none():
    """非拖动动作(以 SellDeployed 为代表)不进期望态层。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import SellDeployed
    assert compute_drag_expect(SellDeployed(row='front', slot=1),
                               [_w530_drag_reconcile_bc(1, '希儿')], []) is None


# ===== ② 定型帧对账判据真值表 =====

def test_compare_sell():
    """卖出:源槽仍出现该身份=不一致;槽空/其他身份/未识别=不判不一致。"""
    exp = compute_drag_expect(_w530_drag_reconcile_SellBench(slot=3), [_w530_drag_reconcile_bc(3, '希儿')], [])
    assert compare_drag_expect(exp, [_w530_drag_reconcile_bc(3, '希儿')], []) != []   # 身份仍在=不一致
    assert compare_drag_expect(exp, [], []) == []                 # 槽空=通过
    assert compare_drag_expect(exp, [_w530_drag_reconcile_bc(3, '景元')], []) == []   # 其他身份不构成本判据
    assert compare_drag_expect(exp, [_w530_drag_reconcile_bc(3, '')], []) == []       # 未识别槽不评


def test_compare_place():
    """空槽落位:源槽已清+目标=该身份 → 一致;源未清/目标异身份 → 不一致;
    目标未识别 → 不评跳过。"""
    exp = compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                         ),
                              [_w530_drag_reconcile_bc(2, '希儿')],
                              [_w530_drag_reconcile_bc(1, '景元', 'front')])
    assert compare_drag_expect(exp, [], [_w530_drag_reconcile_bc(1, '希儿', 'front')]) == []
    # 源未清
    m = compare_drag_expect(exp, [_w530_drag_reconcile_bc(2, '希儿')], [_w530_drag_reconcile_bc(1, '希儿', 'front')])
    assert len(m) == 1 and m[0]['domain'] == 'bench'
    # 目标异身份
    m2 = compare_drag_expect(exp, [], [_w530_drag_reconcile_bc(1, '景元', 'front')])
    assert len(m2) == 1 and m2[0]['domain'] == 'deployed.front'
    # 目标未识别 → 跳过(不算不一致)
    assert compare_drag_expect(exp, [], []) == []


def test_compare_swap():
    """互换:源槽=原目标身份+目标槽=被拖身份 → 一致;任一侧身份不符 → 不一致;
    未识别侧 → 不评。"""
    exp = compute_drag_expect(DeployMove(from_slot=2, to_row='front', to_slot=1,
                                         ),
                              [_w530_drag_reconcile_bc(2, '希儿')],
                              [_w530_drag_reconcile_bc(1, '景元', 'front'), _bc(2, '花火', 'front')])
    assert exp.target_kind == 'swap'
    assert compare_drag_expect(exp, [_w530_drag_reconcile_bc(2, '景元')],
                               [_w530_drag_reconcile_bc(1, '希儿', 'front')]) == []
    m = compare_drag_expect(exp, [_w530_drag_reconcile_bc(2, '花火')], [_w530_drag_reconcile_bc(1, '希儿', 'front')])
    assert len(m) == 1 and m[0]['domain'] == 'bench'
    m2 = compare_drag_expect(exp, [_w530_drag_reconcile_bc(2, '景元')],
                             [_w530_drag_reconcile_bc(1, '花火', 'front')])
    assert len(m2) == 1 and m2[0]['domain'] == 'deployed.front'
    assert compare_drag_expect(exp, [], []) == []   # 全未识别 → 不评


# ===== ③ 接线源码锁(静态结构,防重构断链/改口径)=====

def test_w530_wiring_locks():
    """①期望态在动作发出点(execute 之前)从意图计算;②对账(ADR-0517
    迁移重锚:per-action heavy 重读契约退役)——acct 在执行后暂存,下一
    入口对账段经 _v2_post_frame_accounting 统一消费(入口观察即对账),
    仅 progressed 分支;③身份读=identify_slots 纯读组合,不经
    read_bench_chars(内置停机钩子);④台账参数锁。"""
    src = _w530_drag_reconcile_Path('src/sr_od/application/currency_war/operations/cw_screen/cw_screen_prep.py').read_text(
        encoding='utf-8')
    # ① 发出点:compute 在单轮 execute 之前(W971 P3b 拆内环:单轮 = run
    #    五段;锚「备战单轮」节标记,破警告分支的 decide 在其后)。
    #    ADR-0517 迁移后:单动作决策循环内逐帧决策,期望态仍在 execute
    #    之前从意图计算(锚 = 调用面)。
    loop_at = src.index(
        'match.strategy.decide_prep_screen(session, config)',
        src.index('备战单轮'))
    exec_at = src.index('progressed, detail = self._executor.execute(action)', loop_at)
    emit_at = src.index('if isinstance(action, (SellBench, DeployMove)):', loop_at)
    comp_at = src.index('compute_drag_expect(', loop_at)
    assert emit_at < exec_at
    assert comp_at < exec_at
    # ② 对账点(ADR-0517 重锚):acct 在执行后暂存(session.
    # cw_prep_pending_accts),消费点在下一入口对账段(决策循环之前)。
    stash_at = src.index('session.cw_prep_pending_accts.append(acct)', exec_at)
    drain_at = src.index(
        'self._v2_post_frame_accounting(obs, _pend, session)',
        src.index('def run('))
    assert exec_at < stash_at
    assert drain_at < loop_at   # 消费在入口段(决策循环之前)
    assert "if progressed and acct.get('drag_expect') is not None:" in src
    # ③ 纯读路径:对账方法内用 identify_slots / read_deployed_chars,无 read_bench_chars
    method = src[src.index('def _reconcile_drag_expect'):]
    method = method[:method.index('\n    def ')]
    assert 'identify_slots(' in method
    assert 'read_deployed_chars(' in method
    assert 'read_bench_chars(' not in method   # 文档提及可,调用不可
    assert 'last_screenshot' in method   # 零新增截屏:复用定型帧
    # ④ 台账参数锁(surface/kind 常量定义 + 接线点使用)。
    # 分包期 6(DESIGN §4.5):常量定义随纯期望段迁 kernel/cw_prep_expect
    # (cw_screen_prep 经 import 引用);接线点使用仍在本体。
    expect_src = _w530_drag_reconcile_Path(
        'src/sr_od/application/currency_war/kernel/cw_prep_expect.py'
    ).read_text(encoding='utf-8')
    assert "_DRAG_DEFECT_SURFACE = 'bench'" in expect_src
    assert "_DRAG_DEFECT_KIND = 'intent_state_mismatch'" in expect_src
    assert 'record_defect(' in src and '_DRAG_DEFECT_SURFACE, _DRAG_DEFECT_KIND' in src  # 拆内环:缩进锁降内容级
    assert 'drag_expect_reconcile' in src


# ===== ④ 台账行形态锁 =====

def test_defect_row_shape(tmp_path: _w530_drag_reconcile_Path, monkeypatch):
    """不一致行落 defect_ledger:surface/kind/reader_source/gap_large 形态;
    分级(bench=决策关键面:单次 L1、复现 L0 由安灯承接)由既有分级锁覆盖。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    defects.record_defect(
        'bench', 'intent_state_mismatch',
        expected='deploy_move identity=希儿 from_slot=2 target=front1/place',
        observed='bench槽2 期望[无 希儿(已离槽)] 实读[希儿]',
        plane=1, round_num=3, gap_large=True,
        reader_source='drag_expect_reconcile')
    rows = [ln for ln in
            (tmp_path / 'defect_ledger.jsonl').read_text(encoding='utf-8').splitlines()
            if ln.strip()]
    assert len(rows) == 1
    import json
    row = json.loads(rows[0])
    assert row['surface'] == 'bench'
    assert row['kind'] == 'intent_state_mismatch'
    assert row['reader_source'] == 'drag_expect_reconcile'
    # 分级:bench=决策关键面+大 gap 单次 → L1 初判(复现第 2 次起 L0 由安灯承接;
    # gap_large 是判级输入非落盘字段,severity 即其结果)
    assert row['severity'] == SEVERITY_L1_ALERT

# ==================== test_drag_cw_char ====================
from types import SimpleNamespace as _test_drag_cw_char_SimpleNamespace
from unittest.mock import MagicMock

import numpy as _test_drag_cw_char_np

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_telemetry_exit import SEVERITY_L1_ALERT
from sr_od.application.currency_war.operations.dev.drag_cw_char import DragCwChar


def test_src_changed_detects_pixel_diff() -> None:
    """_src_changed:drag 前后源槽像素均值 diff > 阈 → True(角色离开/swap 换人);不变 → False。"""
    src = Point(30, 30)   # 中心在数组内(40×40 crop [10:50] 不越界)
    before = _test_drag_cw_char_np.zeros((60, 60, 3), _test_drag_cw_char_np.uint8)
    after_same = before.copy()
    after_diff = _test_drag_cw_char_np.full((60, 60, 3), 200, _test_drag_cw_char_np.uint8)   # 均值 diff 200 >> 阈 8
    assert DragCwChar._src_changed(before, after_diff, src) is True
    assert DragCwChar._src_changed(before, after_same, src) is False


def test_src_changed_empty_crop_safe() -> None:
    """_src_changed:crop 越界(空)→ 不崩,返 False。"""
    src = Point(0, 0)   # 中心 0,0 → crop [-20:20,...] 部分越界
    before = _test_drag_cw_char_np.zeros((50, 50, 3), _test_drag_cw_char_np.uint8)
    after = _test_drag_cw_char_np.full((50, 50, 3), 200, _test_drag_cw_char_np.uint8)
    # 不应崩(越界切片→空或部分,diff 计算安全)
    DragCwChar._src_changed(before, after, src)


def _mock_area(name: str, cx: int, cy: int) -> _test_drag_cw_char_SimpleNamespace:
    return _test_drag_cw_char_SimpleNamespace(area_name=name, pc_rect=_test_drag_cw_char_SimpleNamespace(center=Point(cx, cy)))


def test_slot_center_reads_screen_info() -> None:
    """_slot_center:从 screen_info area_list 读 ``{前排/后排/备战栏}-{idx}`` 中心。"""
    ctx = MagicMock()
    ctx.screen_loader.get_screen.return_value = _test_drag_cw_char_SimpleNamespace(area_list=[
        _mock_area('前排-1', 743, 398), _mock_area('后排-6', 1315, 669), _mock_area('备战栏-9', 1436, 912),
    ])
    op = DragCwChar(ctx, 'front', 1, 'bench', 9)
    assert (op._slot_center('front', 1).x, op._slot_center('front', 1).y) == (743, 398)
    assert (op._slot_center('back', 6).x, op._slot_center('back', 6).y) == (1315, 669)
    assert (op._slot_center('bench', 9).x, op._slot_center('bench', 9).y) == (1436, 912)
    # 缺该 area / 非法 row → None(不崩;后排>6 见 op TODO)
    assert op._slot_center('front', 2) is None
    assert op._slot_center('xx', 1) is None


def test_slot_center_none_when_no_screen_info() -> None:
    """_slot_center:screen_info 未加载(None)→ None(op 起手 guard,round_fail BAD_SLOT)。"""
    ctx = MagicMock()
    ctx.screen_loader.get_screen.return_value = None
    op = DragCwChar(ctx, 'front', 1, 'front', 2)
    assert op._slot_center('front', 1) is None


def test_slot_center_back_centers_override() -> None:
    """_slot_center:``back_centers`` 覆盖 screen_info(财富宝钻致后排 >6 时调用方传实际后排槽)。

    screen_info「后排-1..6」基准不够 → 调用方传 7 槽的 back_centers → 后排-7 可解析;front/bench 不受影响。
    """
    ctx = MagicMock()
    ctx.screen_loader.get_screen.return_value = _test_drag_cw_char_SimpleNamespace(area_list=[
        _mock_area('后排-1', 604, 670), _mock_area('后排-6', 1316, 670),   # 基准 6(无后排-7)
    ])
    back_centers = [Point(604 + i * 142, 670) for i in range(7)]   # 7 槽(财富宝钻 +1,等距 142px)
    op = DragCwChar(ctx, 'bench', 1, 'back', 7, back_centers=back_centers)
    # back 走 back_centers:后排-7 = 第 7 个(0-based idx 6)= (1456, 670)
    p7 = op._slot_center('back', 7)
    assert p7 is not None
    assert (p7.x, p7.y) == (604 + 6 * 142, 670)
    # 越界 → None
    assert op._slot_center('back', 8) is None
    # front/bench 仍走 screen_info(不受 back_centers 影响);mock 无 前排-1 → None
    assert op._slot_center('front', 1) is None


# ==================== test_deploy_recipe_target ====================

import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_recipe import _RECIPES, decision_target
from sr_od.application.currency_war.kernel.cw_transition import TRANSITION_PACK
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession as _test_deploy_recipe_target_StrategySession,
)


class _FakeState:
    """局35 r7 形态的最小复刻(dual_track + board)。"""

    def __init__(self):
        self.dual_track_phase = True
        self.board = {'列车同行': 1, '护盾': 1}


def _mk_comp(name: str, factions: list[str], cores: list[str]) -> Comp:
    return Comp(name=name, factions=factions, core_chars=cores,
                form_tiers={}, strength=5.0, form_difficulty='easy')


def test_decision_target_dual_track_returns_recipe():
    """双轨期 + 框架已定 → 配方伪 comp(不是终局 comp)。"""
    sess = _test_deploy_recipe_target_StrategySession()
    sess.transition_framework = '仙舟'
    sess.target_comp = _mk_comp('列车同行', ['列车同行'], ['三月七'])
    st = _FakeState()
    dt = decision_target(sess, st)
    assert dt is not None and dt.name == _RECIPES['仙舟'].name, \
        f'双轨期应返仙舟配方,实得 {dt.name if dt else None}'


def test_framework_char_is_recipe_core():
    """框架件(藿藿/卡芙卡)∈ 配方伪 comp 的 core → deploy 判 target 为 True。"""
    rc = _RECIPES['仙舟']
    for n in ('藿藿', '卡芙卡', '爻光'):
        fw, tier = TRANSITION_PACK[n]
        assert fw == '仙舟'
    # 配方 core 含 carry/partial(drop 不追)
    assert '藿藿' in rc.core_chars
    assert '丹恒·饮月' in rc.core_chars


def test_deploy_no_longer_sells_framework_char_dual_track():
    """r120 语义:双轨期 deploy-swap 的 target 判定用配方——
    卡芙卡(仙舟框架件,drop 档)按旧逻辑(off-target)会被卖;新逻辑下
    decision_target=仙舟配方 → deploy_bench._tgt_comp=配方 → 不在卖集。"""
    sess = _test_deploy_recipe_target_StrategySession()
    sess.transition_framework = '仙舟'
    sess.dual_track_phase = True
    sess.target_comp = _mk_comp('列车同行', ['列车同行'], ['三月七'])
    st = _FakeState()
    dt = decision_target(sess, st)
    # deploy_bench 的 _is_tgt_char 同款判定:阵营/流派交集 or core
    _c_factions = {'仙舟'}
    _c_flows = {'持续伤害'}
    is_tgt = bool((_c_factions | _c_flows) & set(dt.all_factions)) or '卡芙卡' in dt.core_chars
    assert is_tgt or '卡芙卡' not in dt.core_chars, \
        '卡芙卡在配方 target 下应判 target(或至少不被当 off-target 卖)'


def test_nondual_track_keeps_final_comp():
    """定型后(P2)deploy 仍用终局 comp(语义不回归)。"""
    sess = _test_deploy_recipe_target_StrategySession()
    sess.transition_framework = ''
    sess.dual_track_phase = False
    final = _mk_comp('反甲白厄', ['贝洛伯格'], ['白厄'])
    sess.target_comp = final
    st = _FakeState()
    st.dual_track_phase = False
    dt = decision_target(sess, st)
    assert dt is final, '非双轨期应保持终局 comp'


# ==================== test_empty_board_guard ====================

import sys as _test_empty_board_guard_sys
from pathlib import Path as _test_empty_board_guard_Path
from types import SimpleNamespace as _test_empty_board_guard_SimpleNamespace

_REPO = _test_empty_board_guard_Path(__file__).resolve().parents[5]
_test_empty_board_guard_sys.path.insert(0, str(_REPO / 'src'))



def _obs(dep=0, bench=0):
    return _test_empty_board_guard_SimpleNamespace(
        box_overlay_open=False, tomes=[], boxes=[], spheres=[],
        free_bench_slots=9 - bench, shop_open=False,
        bench_chars=[_test_empty_board_guard_SimpleNamespace(char_id=f'c{i}') for i in range(bench)],
        deployed_chars=[_test_empty_board_guard_SimpleNamespace(char_id=f'd{i}') for i in range(dep)],
        front_occupied=set(), back_occupied=set(), front_size=4, back_size=6,
        state=None, state_gold_trusted=False)


def _test_empty_board_guard_cfg():
    return _test_empty_board_guard_SimpleNamespace()


# ==================== dd-037 发射侧同源谓词(has_deployable + 装配)====================

from sr_od.application.currency_war.kernel.cw_deploy_logic import (  # noqa: E402
    deploy_target_sets as _has_dep_deploy_target_sets,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (  # noqa: E402
    deployed_bond_counts as _has_dep_deployed_bond_counts,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (  # noqa: E402
    has_deployable,
)


def test_has_deployable_floor_gate_plan_empty_false() -> None:
    """计划空形态(配方底线门:列车档满 ∧ 仙舟<基础线 ⇒ 列车件留
    bench)⇒ has_deployable False——2026-09-06 实机首局备战环无进展
    守卫停机形态的谓词腿(发射侧不提案 RunDeploy 的判据本体)。"""
    bench = [BenchChar(slot=1, char_id='开拓者·欢愉', faction='列车同行')]
    up, held = select_deployments(
        bench, deployed_cids={'三月七', '姬子'},
        deployed_fac={'列车同行': 2, '护盾': 1, '击破': 1}, board={}, cap=8)
    assert not up and held, '前置:select_deployments 计划空(全留 bench)'
    assert has_deployable(
        bench, deployed_cids={'三月七', '姬子'},
        deployed_fac={'列车同行': 2, '护盾': 1, '击破': 1}, board={}, cap=8,
    ) is False


def test_has_deployable_normal_true() -> None:
    bench = [BenchChar(slot=1, char_id='彦卿', faction='仙舟')]
    assert has_deployable(
        bench, deployed_cids={'三月七'}, deployed_fac={'列车同行': 1},
        board={}, cap=8) is True


def test_has_deployable_unidentified_fail_open() -> None:
    """SIFT 未识别(char_id 空)fail-open 照旧上——与 select_deployments
    语义一致(身份不可判时不激进留 bench)。"""
    bench = [BenchChar(slot=1, char_id='', faction='?')]
    assert has_deployable(
        bench, deployed_cids=set(), deployed_fac={}, board={}, cap=8) is True


def test_deployed_bond_counts_full_bond_scope() -> None:
    """全羁绊口径(factions+flows 逐项 +1;r361b);未注册名不计。"""
    counts = _has_dep_deployed_bond_counts({'三月七', '未注册名', ''})
    assert counts.get('列车同行') == 1
    assert counts.get('护盾') == 1


def test_deploy_target_sets_r70_dual_track() -> None:
    """r70 双轨:comp 阵营 ∪ 框架阵营;fw_carry = 框架/通用非 drop 件。"""
    comp = _test_empty_board_guard_SimpleNamespace(
        factions=('仙舟',), core_chars=('藿藿',))
    tgt, carry = _has_dep_deploy_target_sets(comp, '列车')
    assert '仙舟' in tgt and '列车同行' in tgt
    assert '三月七' in carry and '千冶·刃' in carry
    assert '卡芙卡' not in carry   # drop 件不入 carry
    tgt2, carry2 = _has_dep_deploy_target_sets(None, '')
    assert tgt2 == set() and carry2 == set()


# ==================== 换阵卖出义务臂(板满换阵死锁修复) ====================
# 事故形态(线成型后板满换阵死锁:备战环守卫三环 RunDeploy 单签名停机,
# 详见诊断档案 20260905_noprogress_stop_diag「第三次停机」节):线成型
# fp=1.00、板 7/7 真满、bench 有 target 单位待进场,唯一腾位通道 = 卖
# off-target deployed,但 W209 振荡熔断把 off-line 的引擎/配方件按「恒
# 不卖」护住 → sold 0/2 → 死锁。
# 修复:线成型 ∧ 板满(真部署数,喂入单一源 swap_arm_deployed_count)时
# off-line fenced 件让位(换阵卖出义务臂);新线 core∪shared 仍保护
# (禁卖护栏不因换阵解除)。

from sr_od.application.currency_war.data.cw_chars import get_char as _swap_get_char
from sr_od.application.currency_war.kernel.cw_comps import get_comp as _swap_get_comp
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _swap_BenchChar
from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
    fenced_swap_arm_of,
    offtarget_sell_allowed,
    swap_arm_deployed_count,
)


def _swap_bonds(name: str) -> set[str]:
    ch = _swap_get_char(name)
    return set(ch.factions) | set(ch.flows)


def test_w209_default_arm_still_fences_offline() -> None:
    """守卫移除验证(停滞必须复现):义务臂关闭(默认形态,即修复前的
    判据)下,事故板面(艾丝妲/停云/丹恒·饮月 deployed)逐个判卖——
    off-line fenced 件(艾丝妲,flows=持续伤害)拒卖、target 单位照留
    ⇒ sold=0 停滞形态复现(证明停机确由本判据承载,非其他环节)。
    黑塔(银河学者/群攻)不在围栏键域(注册表事实:非 RECIPE∪ENGINE
    成员),本不经熔断,不入本锁。"""
    tf = {'仙舟', '列车同行'}
    tc = {'花火', '瓦尔特', '姬子·启行', '三月七'}
    for name in ('艾丝妲', '停云', '丹恒·饮月'):
        assert offtarget_sell_allowed(name, _swap_bonds(name), tf, tc) is False, \
            f'{name} 在义务臂关闭时须被拒卖(停滞形态复现)'
    assert '持续伤害' in _swap_bonds('艾丝妲'), '锁前提:艾丝妲=旧线持续伤害'


def test_w209_swap_arm_offline_fenced_sellable() -> None:
    """事故帧锁(修复形态):线成型 + 板满 ⇒ 义务臂开启后 off-line fenced
    件(艾丝妲=旧线持续伤害)进入可卖;target 单位(丹恒·饮月/停云/
    忘归人)与新线 core∪shared 仍保护;非 fenced 的 off-line 件(黑塔)
    两臂同可卖(原语义不变)。"""
    tf = {'仙舟', '列车同行'}
    comp = _swap_get_comp('列车同行')
    tc = set(comp.core_chars)
    protect = frozenset(set(comp.core_chars)
                        | set(getattr(comp, 'shared_chars', []) or ()))
    assert offtarget_sell_allowed(
        '艾丝妲', _swap_bonds('艾丝妲'), tf, tc,
        fenced_offline_sellable=True, protect_names=protect) is True
    assert offtarget_sell_allowed(
        '黑塔', _swap_bonds('黑塔'), tf, tc) is True   # 非 fenced:默认臂本就可卖
    for name in ('丹恒·饮月', '停云', '忘归人'):   # target 单位两臂都留
        assert offtarget_sell_allowed(
            name, _swap_bonds(name), tf, tc,
            fenced_offline_sellable=True, protect_names=protect) is False
    for name in protect:   # 新线 core∪shared 禁卖护栏不因换阵解除
        assert offtarget_sell_allowed(
            name, _swap_bonds(name), tf, tc,
            fenced_offline_sellable=True, protect_names=protect) is False


def test_w209_swap_arm_trigger_gate() -> None:
    """触发门真值表(纯函数 fenced_swap_arm_of,喂入=真部署数):线成型
    (fp≥1.00)∧ 板满(占用数 ≥ cap,占用数口径;物理槽位门旧形态
    domain 不可达已收口,见 test_cw_swap_plan 复活锁)双条件;未成型或
    未满板帧不开启(双轨期预囤框架件保护原语义零变化)。"""
    assert fenced_swap_arm_of(1.0, 7, 7) is True      # 板满形态:fp=1.00 ∧ 7 占用
    assert fenced_swap_arm_of(0.42, 7, 7) is False    # 未成型(成型前对照)
    assert fenced_swap_arm_of(1.0, 6, 7) is False     # 未满板:无腾位需求
    assert fenced_swap_arm_of(1.0, 8, 7) is True      # 超满(cap 叠加)同辖


def test_w209_swap_arm_feed_is_deployed_count_not_bond_sum() -> None:
    """live 喂入语义锁(P1 阻断判别):「板满」喂入 = 真部署数
    (deployed_occupied 槽位表计数),禁羁绊计数总和——board 语义 =
    阵营→在场人数,一人多阵营(4 人可 11 阵营次):旧形态喂 sum(board
    .values())=11 ≥ 7 槽 ⇒ 板未满即开臂、不可逆卖出逐环发生;修复后
    喂 4 < 7 ⇒ 不开臂。"""
    board = {'仙舟': 3, '治疗': 2, '列车同行': 3, '战技点': 2, '护盾': 1}
    assert sum(board.values()) == 11, '锁前提:4 人多阵营贡献 11 阵营次'
    tracked = [_swap_BenchChar(slot=i + 1, char_id=n, star=1)
               for i, n in enumerate(('丹恒·饮月', '停云', '藿藿', '艾丝妲'))]
    assert swap_arm_deployed_count(board, tracked) == 4
    # 建模对象判别:同一形态下,喂部署数不开臂;喂羁绊总和必开臂(旧病)
    assert fenced_swap_arm_of(1.0, swap_arm_deployed_count(board, tracked),
                              7) is False
    assert fenced_swap_arm_of(1.0, sum(board.values()), 7) is True
    # 边界:tracked 缺失/空 ⇒ 0(缺输入保守侧,不开臂)
    assert swap_arm_deployed_count(board, []) == 0
    assert swap_arm_deployed_count(None, None) == 0
    assert fenced_swap_arm_of(1.0, swap_arm_deployed_count(board, []),
                              7) is False


def test_p59_substitute_protected_from_swap_arm() -> None:
    """P59 反例锁:黄泉减益×卡芙卡(替班者=off-line∧fenced)——替班者
    凭 substitute_plan 直入买面义务集却无羁绊保证,修复后入保护域、
    义务臂判不可卖(修复前臂可卖 = M2 义务买↔换阵臂卖振荡)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        protect_names_of,
    )
    comp = _swap_get_comp('黄泉减益')
    protect = protect_names_of(comp)
    assert '卡芙卡' in protect, '替班者必须入保护域(P59 反例成员)'
    bonds = _swap_bonds('卡芙卡')
    tf = set(comp.all_factions)
    tc = set(comp.core_chars)
    assert not (bonds & tf), '锁前提:卡芙卡对本 comp off-line'
    assert offtarget_sell_allowed(
        '卡芙卡', bonds, tf, tc,
        fenced_offline_sellable=True, protect_names=protect) is False, \
        'P59 反例:替班者不得被义务臂判可卖'


def test_p59_registry_buysell_disjoint() -> None:
    """注册表级静态断言(P59 防复发锚):全 comp 扫描——锁定采购集
    (_line_hoard 全集)中对本 comp off-line ∧ fenced 的成员必须 ⊆
    保护域(core∪shared∪替班者)。买面新增任何不经羁绊检查的成员腿而
    未同步入保护域时,本锁红(替班者腿本身由保护域组装自动覆盖)。"""
    from sr_od.application.currency_war.kernel import cw_intention as _ci
    from sr_od.application.currency_war.kernel.cw_comps import (
        COMP_LIBRARY,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        protect_names_of,
    )
    violations: list[str] = []
    for comp in COMP_LIBRARY:
        if not getattr(comp, 'core_chars', None):
            continue
        protect = protect_names_of(comp)
        subs = {s.get('替班者') for s in (getattr(comp, 'substitute_plan',
                None) or []) if isinstance(s, dict) and s.get('替班者')}
        assert subs <= protect, \
            f'{comp.name}: 替班者 {subs - protect} 未入保护域'
        hoard, _eq = _ci._line_hoard(comp)
        all_fac = set(comp.all_factions)
        for m in hoard:
            bonds = _swap_bonds(m)
            offline = not (bonds & all_fac)
            fenced = bool(bonds & _DEPLOY_FENCE)
            if offline and fenced and m not in protect:
                violations.append(f'{comp.name}:{m}')
    assert not violations, \
        f'买↔卖振荡反例(成员入买入集但不在保护域):{violations}'

