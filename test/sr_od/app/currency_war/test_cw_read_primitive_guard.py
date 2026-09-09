"""读屏原语直调守卫锁(T-120 方案 §3.3 守卫锁②;批 1 落地审 G-2 登记)。

**辖域**:operations 桶对 obs 读屏原语(集合 ``_PRIMITIVES``)的**直调**——
被测代码取「环境观察」应经统一注入口(cw_game_ports 观察源端口,批 1
改道清单)或属于已登记的合法直调面。红 = 集合外新增 (文件, 函数, 原语)
直调 → 处置 = 审其合法性:①属 live 实现封口内部(端口/执行器的实机侧
实现,方案 §3.3「B 类执行层验证读物理住在 Live 实现内部」豁免)→ 登记进
``_LIVE_SEAL``;②残读(未改道面,候批 3 外循环分支接入收敛)→ 登记进
``RESIDUAL`` 并携申报;都不属 → 收敛到已登记改道点。禁机械跟绿。

**现状冻结口径**:登记集 = 批 2 开工时全量扫描亲跑所得(live 16 对 +
残读 29 对 = 45 对);批 3 外循环分支接入时,RESIDUAL 面随改道
逐项删除(该域收敛方向 = 登记只减不增;``_LIVE_SEAL`` 随 live 实现面
如实维护)。

出处 = T-120 方案 v2 §3.3 守卫锁② + 批 1 落地审 §1.2-G-2(「visit 链
接入前必须有」;批 2 visit/备战链已接入假局,锁随批落地)。
"""
from __future__ import annotations

import ast
from pathlib import Path

from sr_od.application.currency_war import operations as _ops_pkg

#: 读屏原语名单(方案 §2.3 观察注入接口覆盖的入口读取族;语义 = 被
#: 端口改道或登记豁免的「取环境观察」面,非全部 obs 函数)
_PRIMITIVES: frozenset[str] = frozenset({
    'read_game_state', 'read_gold', 'read_gold_settled', 'read_hp_opt',
    'read_node_sequence', 'read_deployed_count', 'observe_full',
    'read_shop_cards', 'read_reward_spheres', 'read_supply_boxes',
    'read_tomes', 'read_bench_chars', 'read_deployed_chars',
    'read_phase_round', 'read_level', 'read_xp_progress',
    'read_enemy_difficulty', 'read_refresh_probs', 'read_node_type',
    'read_streak', 'read_level_up_cost',
})

#: live 实现封口内部(合法直调面,方案 §3.3 B 类豁免):这些函数本体
#: 就是端口/执行器的实机实现,直调读屏即其职责。
_LIVE_SEAL: frozenset[tuple[str, str, str]] = frozenset({
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', '_deploy_deterministic', 'read_bench_chars'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', '_deploy_deterministic', 'read_deployed_chars'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', '_deploy_deterministic', 'read_deployed_count'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', '_fix_misplaced_rows', 'read_deployed_chars'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', '_reconcile_tracking', 'read_bench_chars'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', '_reconcile_tracking', 'read_deployed_chars'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', '_rowfix_front_empty_recoverable', 'read_deployed_chars'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', '_sell_offtarget_deployed', 'read_deployed_chars'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', 'deploy', 'read_bench_chars'),
        ('application/currency_war/operations/cw_op/cw_op_deploy.py', 'deploy', 'read_deployed_chars'),
        ('application/currency_war/operations/cw_op/cw_shop_action_ops.py', 'execute', 'read_gold'),
        ('application/currency_war/operations/cw_op/cw_shop_action_ops.py', 'execute', 'read_shop_cards'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_observe', 'observe_full'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_observe', 'read_deployed_count'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_observe', 'read_reward_spheres'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_observe', 'read_supply_boxes'),
})

#: 残读登记面(未改道,候批 3 外循环分支接入收敛;批 2 现状冻结)
RESIDUAL: frozenset[tuple[str, str, str]] = frozenset({
        ('application/currency_war/operations/cw_entry/cw_entry_plane_intel.py', 'takeover', 'read_phase_round'),
        ('application/currency_war/operations/cw_loop.py', '_launch_frame_arbitration', 'read_game_state'),
        ('application/currency_war/operations/cw_loop.py', '_record_supply_outcome', 'read_phase_round'),
        ('application/currency_war/operations/cw_loop.py', 'loop', 'read_game_state'),
        ('application/currency_war/operations/cw_loop.py', 'loop', 'read_node_sequence'),
        ('application/currency_war/operations/cw_loop.py', 'loop', 'read_phase_round'),
        ('application/currency_war/operations/cw_loop.py', 'prep_exhaustion_exclusion_reason', 'read_node_sequence'),
        ('application/currency_war/operations/cw_loop.py', 'prep_exhaustion_exclusion_reason', 'read_reward_spheres'),
        ('application/currency_war/operations/cw_op/cw_op_buy_cards.py', 'run_buy_waves', 'read_game_state'),
        ('application/currency_war/operations/cw_op/cw_op_buy_cards.py', 'run_buy_waves', 'read_gold'),
        ('application/currency_war/operations/cw_op/cw_op_buy_cards.py', 'run_buy_waves', 'read_shop_cards'),
        ('application/currency_war/operations/cw_screen/cw_screen_battle_wait.py', '_record_round_outcome', 'read_phase_round'),
        ('application/currency_war/operations/cw_screen/cw_screen_invest_env.py', '_refresh_node_ledger', 'read_node_sequence'),
        ('application/currency_war/operations/cw_screen/cw_screen_invest_env.py', '_refresh_node_ledger', 'read_phase_round'),
        ('application/currency_war/operations/cw_screen/cw_screen_plane_intel.py', 'collect', 'read_node_sequence'),
        ('application/currency_war/operations/cw_screen/cw_screen_plane_intel.py', 'collect', 'read_phase_round'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_probe_node_type', 'read_node_sequence'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_reconcile_buy_expect', 'read_deployed_chars'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_reconcile_drag_expect', 'read_deployed_chars'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_takeover_collect_if_needed', 'read_node_sequence'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_takeover_collect_if_needed', 'read_phase_round'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', '_v2_post_frame_accounting', 'read_deployed_count'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', 'finalize_buy_phase', 'read_game_state'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', 'finalize_buy_phase', 'read_gold'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', 'finalize_buy_phase', 'read_gold_settled'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', 'lifecycle_decision_cycle', 'read_deployed_count'),
        ('application/currency_war/operations/cw_screen/cw_screen_prep.py', 'run', 'read_deployed_count'),
        ('application/currency_war/operations/cw_screen/cw_screen_supply_node.py', '_do_action', 'read_game_state'),
        ('application/currency_war/operations/cw_screen/cw_screen_supply_node.py', '_supply_detour_collect', 'read_game_state'),
})

_EXPECTED: frozenset[tuple[str, str, str]] = _LIVE_SEAL | RESIDUAL


def _scan() -> set:
    """operations 桶 AST 扫描:直调读屏原语 → (文件尾, 宿主函数, 原语)。"""
    root = Path(_ops_pkg.__file__).parent
    hits = set()
    for f in sorted(root.rglob('*.py')):
        tree = ast.parse(f.read_text(encoding='utf-8'))
        parent = {}
        for node in ast.walk(tree):
            for ch in ast.iter_child_nodes(node):
                parent[ch] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (fn.id if isinstance(fn, ast.Name)
                    else (fn.attr if isinstance(fn, ast.Attribute) else None))
            if name not in _PRIMITIVES:
                continue
            cur, host = parent.get(node), '<module>'
            while cur is not None:
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    host = cur.name
                    break
                cur = parent.get(cur)
            rel = str(f.relative_to(root.parent.parent.parent)).replace(
                '\\', '/')
            hits.add((rel, host, name))
    return hits


def test_operations_read_primitives_frozen() -> None:
    """直调面冻结:扫描集 == 登记集(多/少皆红)。

    红(多)= 集合外新直调,处置见模块 docstring(禁机械跟绿);
    红(少)= 登记面已收敛(批 3 改道删除)→ 同批删登记项。
    """
    hits = _scan()
    extra = sorted(hits - _EXPECTED)
    missing = sorted(_EXPECTED - hits)
    assert not extra, (
        f'operations 桶新增读屏原语直调 {len(extra)} 处(未经登记):'
        f'{extra}——处置 = 走端口改道或按模块 docstring 登记申报')
    assert not missing, (
        f'登记面 {len(missing)} 处已不在扫描集(改道收敛?)——'
        f'同批删除登记项:{missing}')


def test_scanner_catches_new_direct_call(tmp_path: Path) -> None:
    """盲区自检:合成树上的新直调必须被起诉(禁假绿)。"""
    pkg = tmp_path / 'pkg'
    pkg.mkdir()
    guilty = pkg / 'offender.py'
    guilty.write_text(
        'def f(ctx, shot):\n'
        '    return read_game_state(ctx, shot)\n',
        encoding='utf-8')
    tree = ast.parse(guilty.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = (fn.id if isinstance(fn, ast.Name)
                    else (fn.attr if isinstance(fn, ast.Attribute) else None))
            if name in _PRIMITIVES:
                names.add(name)
    assert names == {'read_game_state'}
