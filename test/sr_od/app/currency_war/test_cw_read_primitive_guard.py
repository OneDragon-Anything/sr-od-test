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

**第二锁面:全仓 read_game_state 调用点封闭集(统一观察架构 B4 静态锁)**。
出处 = ``docs/develop/currency_war/design/统一观察架构-画面op基类设计.md``
§1.1-1(read_game_state 调用点全量扫描基线 + 调用点白名单制)。两锁面
关系:本文件第一锁面(T-120)辖 operations 桶 × read_* 族的**改道登记
冻结**;B4 锁面辖**全仓 src 树 × read_game_state 本体**的调用点封闭集
(锁面收窄口径:operations/ 内其余 read_* 调用是验真锚,不属 B4 锁面,
仍由第一锁面管辖)——B4 面比第一锁面宽在 obs 桶内部与 operations 之外
(telemetry 等),两面互补不重复。封闭集与第一锁面的 read_game_state
登记项在 operations 桶内交叠:两边登记语义不同(改道收敛 vs 迁移收编),
同批真实事件须两边同步更新,各自红讯指向各自处置。
两锁面共同的**扫描边界申报**:按**调用名**匹配(Name/Attribute),注释
与 def 不入锁面;``from x import read_game_state as rgs`` 的别名调用与
getattr 字符串形态不入扫描集(刻意绕名/绕 AST 的写法不属本锁辖域,
与第一锁面同边界;别名导入本项目风格不用,出现即按绕过守卫处置)。
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
        # (删除波 1:loop._record_supply_outcome read_phase_round 登记项已删
        #  ——合成结算行随旧流写入端退役,读点消失。)
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
        # (统一观察架构迁移批 T-48:plane_intel 采集体为两路径共享体
        #  ``_collect_cycle``,collect 节点 = 装配点分流 + 委托——两读点
        #  宿主名随体迁移,登记语义(残读未改道)不变。)
        ('application/currency_war/operations/cw_screen/cw_screen_plane_intel.py', '_collect_cycle', 'read_node_sequence'),
        ('application/currency_war/operations/cw_screen/cw_screen_plane_intel.py', '_collect_cycle', 'read_phase_round'),
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
        # (删除波 1:supply_node 两处登记项已删——detour 快照读/选卡 state 读
        #  随旧流写入端退役,读点同批消失;去向 = 读点消亡,无改道。)
        # (删除波 1:loop._record_supply_outcome / shop_action_ops.execute 两处
        #  登记项已删——合成结算行/执行段读数随旧流写入端退役,读点同批消失。)
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


# ==================== B4 锁面:全仓 read_game_state 调用点封闭集 ====================
# 出处 = docs/develop/currency_war/design/统一观察架构-画面op基类设计.md
# §1.1-1「read_game_state 调用点全量扫描基线」+「调用点白名单制」。
# 立锁前基线复扫(2026-09-10,全仓 src 树):14 命中 = 真实调用 10(下表
# 8 宿主,observe_full 宿主含 3 点)+ 注释 3 + def 1,与设计文档基线逐条
# 一致、零漂移,按其「立锁前重跑扫描确认基线未漂移」纪律立锁。

#: 封闭集登记:{(相对 sr_od 的 posix 文件路径, 宿主函数): (调用点数, 族别+理由)}。
#: 族别口径 = 设计文档 §1.1-1 四族;「试点迁移收编类」在基类 observe 段
#: 接管后归 obs 族,届时同批从本表移出(移出 = 改道收敛,不是放宽)。
_GS_CLOSURE: dict[tuple[str, str], tuple[int, str]] = {
    ('application/currency_war/obs/cw_observe_full.py', 'observe_full'): (
        3, '族①obs 桶内部:观察漏斗本体互调(readers/漏斗实现即职责)'),
    ('application/currency_war/operations/cw_loop.py',
     '_launch_frame_arbitration'): (
        1, '族②既有豁免:发射帧仲裁段的仲裁读'),
    ('application/currency_war/operations/cw_loop.py', 'loop'): (
        1, '族②既有豁免:开局最小读(恢复对局检测仅位面轮次)'),
    ('application/currency_war/operations/cw_op/cw_op_buy_cards.py',
     'run_buy_waves'): (
        1, '族②既有豁免:开店态买牌波入口的金/牌读'),
    ('application/currency_war/telemetry/cw_match_recorder.py',
     'extract_frame'): (
        1, '族④非画面 op 合法面:遥测录局关键帧结构化(白名单显式收录)'),
    ('application/currency_war/operations/cw_screen/cw_screen_prep.py',
     'finalize_buy_phase'): (
        1, '族③试点迁移收编类:基类 observe 段接管后归 obs 族并移出本表'),
    # (删除波 1:supply_node 两处登记项已删——detour 快照读/选卡读_game_state
    #  随旧流写入端退役,读点同批消失;去向 = 读点消亡,无改道。)
}


def _scan_read_game_state(src_root: Path) -> dict[tuple[str, str], list[int]]:
    """AST 扫描 src 树 read_game_state **真实调用** → {(文件, 宿主): [行号]}。

    注释与 def 不入 AST Call,天然不计锁面(基线 14 命中中 3 注释 + 1 def
    被本口径排除)。名字先文本预过滤再 parse:源码文本不含该名的文件不可
    能含同名调用,全仓 1092 文件扫描成本因此从 ~2.2s 降到 <0.5s(慢桶线下)。
    """
    needle = 'read_game_state'
    hits: dict[tuple[str, str], list[int]] = {}
    for f in sorted(src_root.rglob('*.py')):
        if needle not in f.read_text(encoding='utf-8'):
            continue
        tree = ast.parse(f.read_text(encoding='utf-8'))
        parent: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for ch in ast.iter_child_nodes(node):
                parent[ch] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (fn.id if isinstance(fn, ast.Name)
                    else (fn.attr if isinstance(fn, ast.Attribute) else None))
            if name != needle:
                continue
            cur, host = parent.get(node), '<module>'
            while cur is not None:
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    host = cur.name
                    break
                cur = parent.get(cur)
            rel = f.relative_to(src_root).as_posix()
            hits.setdefault((rel, host), []).append(node.lineno)
    return hits


def test_read_game_state_call_closure() -> None:
    """B4 封闭集:全仓 read_game_state 真实调用点 == 登记集(多/少皆红)。

    红(多) = 封闭集外新增调用点(设计文档 §1.1-1:新增调用点 = 锁红)
    → 处置 = ①观察漏斗本体 → 归 obs 桶实现内部并登记族①;②画面 op 内
    观察语义 → 走基类 observe 段收编,登记「试点迁移收编类」并注明移出
    时点;③其余 → 按白名单纪律逐点申报(禁随手豁免)。禁机械跟绿。
    红(少) = 登记点已收敛(收编/改道)→ 同批删登记项并注明去向。
    """
    src_root = Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
    hits = _scan_read_game_state(src_root)
    extra = sorted(set(hits) - set(_GS_CLOSURE))
    missing = sorted(set(_GS_CLOSURE) - set(hits))
    assert not extra, (
        f'全仓 read_game_state 封闭集外新增调用点 {len(extra)} 处'
        f'(统一观察架构 §1.1-1:新增 = 锁红):{extra}——'
        f'处置 = obs 桶收编/迁移收编类登记/白名单逐点申报,禁随手豁免')
    assert not missing, (
        f'封闭集登记 {len(missing)} 处已不在扫描集(收编/改道收敛?):'
        f'{missing}——同批删除登记项并注明去向')
    drifted = {k: (hits[k], _GS_CLOSURE[k][0]) for k in hits
               if k in _GS_CLOSURE and len(hits[k]) != _GS_CLOSURE[k][0]}
    assert not drifted, (
        f'封闭集登记点调用数漂移(宿主内调用点增减,登记语义须重申):'
        f'{drifted}')


def test_read_game_state_closure_blindspot(tmp_path: Path) -> None:
    """盲区自检(禁假绿,三腿):①新调用点在未登记宿主必须被捕获;
    ②注释与 def 不计锁面(基线分族口径 14 = 10 + 3 + 1);③read_* 族
    其余成员不属 B4 锁面(验真读合法,由本文件第一锁面另行管辖)。"""
    pkg = tmp_path / 'pkg'
    pkg.mkdir()
    (pkg / 'fresh_call.py').write_text(
        'def unregistered_host(ctx, shot):\n'
        '    return read_game_state(ctx, shot)\n',
        encoding='utf-8')
    (pkg / 'comment_and_def_only.py').write_text(
        '# 尽力而为 read_game_state(注释不属锁面)\n'
        'def read_game_state(ctx, screen):\n'
        '    """docstring 提及 read_game_state( 同样不属锁面。"""\n'
        '    return None\n',
        encoding='utf-8')
    (pkg / 'verification_reads.py').write_text(
        'def verify(ctx, shot):\n'
        '    return read_gold(ctx, shot), read_deployed_chars(ctx, shot)\n',
        encoding='utf-8')
    hits = _scan_read_game_state(pkg)
    assert set(hits) == {('fresh_call.py', 'unregistered_host')}, hits
    assert len(hits[('fresh_call.py', 'unregistered_host')]) == 1
