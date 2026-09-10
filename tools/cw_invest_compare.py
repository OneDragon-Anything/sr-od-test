"""CW 投资剧本对拍件(常驻版;T-204 易失 runner 升级迁驻,T-209/G1)。

用法(主仓根):
    uv run python sr-od-test/tools/cw_invest_compare.py --out \
        .debug/temp/currency_war/<批次目录> [--since 20260901] [--limit 5]

主线(确认性对拍,strategy-work §3:sim 对拍不构成数值合法性来源):
- 实机侧:`.debug/currency_war/telemetry/matches/` 档案提取带卡局
  (决策帧 active_strategies 增量 = 实机真实投资决策序列,全位面;
  env 首选 invest_cards.jsonl chosen 行,回退 sess_active_env);
- 注入侧:逐局剧本 → SimInvestProfile → 假局重放(P1 = run_p1 全程
  真链,与 T-204 逐位同法;P2+ = 外循环分支序驱动续跑到位面结束/
  死亡),seed = game_id crc32 派生,逐局确定性;
- 对拍:逐 (位面,轮) 金分布带(中位/p90/p10)假局 vs 实机;在带 =
  假局中位 ∈ 实机 [p10, p90];实机 n<10 = 样本不足不判带。

时点口径(G1 同帧时点重提取;T-204 落地审 §三-G1 义务):
- 口径A-同帧:实机 = 该轮首个 FORM(布阵)相位可读帧(轮开收入后、
  花销前的同帧锚);假局 = 期初金(收入+选卡 instant_gold 后)。T-204
  旧口径A 实机 = 轮内首个可读帧(常为 entry 尾/收入前读数,时点不齐)——
  本口径即「对拍时点对齐消费节奏」的构造性验证载体;
- 口径B:实机 = 该轮末个可读帧(消费后);假局 = 期末金。轮末对齐。
- 假局 P2+ 轮开快照位 = 分支驱动 last_gold_after_income + 选卡轮
  instant_gold 修正(与 P1 期初金同域;P1 由 run_p1 内生同点)。

产出 = <out>/对拍分布.{json,md} + 重放缓存.json + archives/(逐局
重放遥测留证)。边界申报见产物 md 尾节(运行树偏置/观测缺口,规范 =
sr-od-test/README.md「对拍与批驱动申报规范」)。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import zlib
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / 'src'))
sys.path.insert(0, str(_REPO / 'sr-od-test'))
sys.path.insert(0, str(_REPO))

MATCHES_ROOT = _REPO / '.debug' / 'currency_war' / 'telemetry' / 'matches'

#: 在带判定的实机侧最小样本(低于 = 样本不足不判带,防小 n 过度声明)
MIN_N_FOR_BAND: int = 10


class _Mp:
    """pytest.MonkeyPatch 的最小替身(runner 侧桩面用;undo 序还原)。"""

    def __init__(self) -> None:
        self._undo: list = []

    def setattr(self, target, name, value, **_kw) -> None:
        old = getattr(target, name)
        self._undo.append(lambda t=target, n=name, v=old: setattr(t, n, v))
        setattr(target, name, value)

    def undo(self) -> None:
        for fn in reversed(self._undo):
            fn()
        self._undo.clear()


def _row(r: object) -> dict:
    return r if isinstance(r, dict) else json.loads(r)  # type: ignore[arg-type,return-value]


def extract_live_matches(since: str = '', until: str = '',
                         limit: int = 0) -> tuple[list[dict], int]:
    """实机档案提取:带卡局的 env/全位面选卡日程/逐轮三时点金。

    三时点金(键 = (plane, round)):
    - gold_open:轮内首个 gold_readable 帧(T-204 旧口径A 实机侧,留作
      同帧重提取前后对照);
    - gold_form:轮内首个 FORM 相位可读帧(同帧口径A 锚;缺失 = 该轮
      无 FORM 读数,出口径);
    - gold_close:轮内末个可读帧(口径B,消费时点)。

    同键坍缩披露:同一 (plane, round) 增量出多名时(选卡 + 效果赠卡
    同帧等),日程按键取增量首名(键内时序不可辨,取首为口径非裁定),
    落选名计数披露;装配侧对同键多 pick 显式拒绝(T-209/G5),坍缩
    必须发生在提取层且有披露,不得把畸形剧本递给装配位。
    """
    files = sorted(MATCHES_ROOT.glob('match_g_2026*.json'))
    out: list[dict] = []
    dropped_dedup = 0
    for f in files:
        gid = f.stem.replace('match_', '')
        if 'fake' in f.stem:
            continue   # 假局档案(采集演练)不入实机带
        date = gid[2:10]   # g_YYYYMMDD_HHMMSS
        if since and date < since:
            continue
        if until and date > until:
            continue
        if limit and len(out) >= limit:
            break
        try:
            m = json.loads(f.read_text(encoding='utf-8'))
        except Exception:   # noqa: BLE001  坏档跳过(计披露)
            continue
        slices = m.get('slices') or {}
        dec = slices.get('decisions.jsonl') or []
        rows = [_row(r) for r in dec if isinstance(r, (dict, str))]
        rows.sort(key=lambda r: str(r.get('ts')))
        prev: set = set()
        picks: list[tuple[int, int, str]] = []
        seen_keys: set = set()
        env = ''
        gold: dict[tuple[int, int], int] = {}
        gold_form: dict[tuple[int, int], int] = {}
        gold_close: dict[tuple[int, int], int] = {}
        for r in rows:
            cur = set(r.get('active_strategies') or [])
            for n in sorted(cur - prev):
                key = (int(r.get('plane') or 1),
                       int(r.get('round_num') or 1))
                if key in seen_keys:
                    dropped_dedup += 1
                    continue
                seen_keys.add(key)
                picks.append((key[0], key[1], n))
            prev = cur
            se = r.get('sess_active_env') or ''
            if se and not env:
                env = se
            if (r.get('gold_readable') and r.get('gold') is not None):
                key = (int(r.get('plane') or 1),
                       int(r.get('round_num') or 0))
                if key[1] <= 0:
                    continue
                if key not in gold:
                    gold[key] = int(r['gold'])
                    if r.get('phase') == 'FORM':
                        gold_form[key] = int(r['gold'])
                elif key not in gold_form and r.get('phase') == 'FORM':
                    gold_form[key] = int(r['gold'])
                gold_close[key] = int(r['gold'])   # 末帧覆盖 = 期末
        # env 首选 invest_cards chosen 行(带 chosen 事实)
        inv = slices.get('invest_cards.jsonl') or []
        for r in (_row(x) for x in inv):
            if r.get('kind') == 'env' and r.get('chosen'):
                env = r.get('name') or env
                break
        if not picks:
            continue   # 非带卡局
        out.append({'game_id': gid, 'env': env, 'picks': picks,
                    'gold': gold, 'gold_form': gold_form,
                    'gold_close': gold_close})
    if dropped_dedup:
        print(f'[披露] 同键坍缩落选名 {dropped_dedup} 个(赠卡族,提取层'
              f'取首名披露;装配侧同键多 pick 已拒绝,见 G5 锁)')
    return out, dropped_dedup


def run_fake_replay(ctx, game: dict, archives: Path) -> dict:
    """单局剧本注入假局重放(P1 run_p1 同法 + P2+ 分支序续跑)。

    P1 段 = ``run_p1`` 全程真链(与 T-204 逐位同法,保前后对照可比性);
    P2+ 段 = 外循环分支序驱动(0q 位面过渡真 op 续跑),终点 = 位面
    日程耗尽不再进场 / hp 归零(死亡态,与实机局终同语义)/ 安全轮预算。
    """
    from fixtures.cw_fake_game.fake_ports import (
        FakeActionSink,
        FakeCwObserver,
    )
    from fixtures.cw_harness import FakeP1Run

    from sr_od.application.currency_war import cw_game_ports
    from sr_od.application.currency_war.operations import decision_frame_hooks as dfh
    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )
    from sr_od.application.currency_war.telemetry import op_journal
    from sr_od.application.currency_war.telemetry import state as tel_s

    seed = 204_000_000 + zlib.crc32(game['game_id'].encode()) % 1_000_000
    profile = SimInvestProfile(
        active_env=game['env'],
        picks=tuple((p, r, n) for p, r, n in game['picks']))
    run = FakeP1Run(ctx, seed, invest_profile=profile)
    root = archives / f"replay_{game['game_id']}"
    tel_s.set_recorder_replay_dir(root)
    op_journal.set_journal_dir(root)
    dfh.set_decision_frame_dir(root)
    cw_game_ports.install_game_ports(FakeCwObserver(run.match),
                                     FakeActionSink(run.match))
    mp = _Mp()
    run._monkeypatch = mp
    try:
        run._install_stubs(mp)
        result = run.run_p1()
        later = _drive_planes_after_p1(run, mp)
    finally:
        cw_game_ports.uninstall_game_ports()
        rc = getattr(ctx, 'run_context', None)
        if rc is not None:
            rc.last_run_result = None
        tel_s.reset_run_state()
        tel_s.set_recorder_replay_dir(None)
        op_journal.set_journal_dir(None)
        dfh.set_decision_frame_dir(None)
        mp.undo()
    held = list(run.match.state.active_strategies)
    invest_total = sum(row['income'].get('invest', 0)
                       for row in result.rounds.values())
    invest_total += sum(row['income'].get('invest', 0)
                        for row in later.values())
    return {'seed': seed,
            'gold': {r: row['gold_after_income']
                     for r, row in result.rounds.items()},
            'gold_close': {r: row['gold_close']
                           for r, row in result.rounds.items()},
            'later': later,
            'held_final': held,
            'invest_income_total': invest_total,
            'env_version': run.match.env_fingerprint()}


def _drive_planes_after_p1(run, mp) -> dict[int, dict]:
    """P2+ 段续跑(分支序驱动):逐 (位面,轮) 期初/期末金收集。

    期初金口径与 P1 对齐:分支驱动快照位 = 收入后(选卡前),对 0e
    选卡轮补 instant_gold 修正(剧本名直注入,单一源 economy_effect_of
    现算)→ 与 run_p1 的「决策时点金」同域。期末金 = 回合收口后
    state.gold(settle 只迁 hp/streak,零金效应,与 run_p1 捕点同值)。
    """
    from fixtures.cw_fake_game.fake_match import PHASE_PLANE_TRANSITION

    from sr_od.application.currency_war.kernel.cw_investments import (
        economy_effect_of,
    )

    m = run.match
    rounds: dict[int, dict] = {}
    safety = 0
    while (m.state.plane <= 3 and safety < 60
           and (m.state.hp or 0) > 0):
        safety += 1
        if m.phase == PHASE_PLANE_TRANSITION:
            if m.state.plane >= 3:
                break   # P3 日程耗尽 = 建模域终点(假局无独立局终相位)
            order = run.run_round_branch_order(mp)
            if '0q_plane_transition' not in order['dispatch']:
                break   # 过渡未发生(防御):交调用方判读,不猜
            continue
        pre = (m.state.plane, m.state.round_num)
        order = run.run_round_branch_order(mp)
        if not order['dispatch']:
            break   # 未知相位(分支序防御分支):停,申报于产物
        gold_open = int(run.last_gold_after_income)
        sched = m.scheduled_invest_pick(*pre)
        if ('0e_invest_pick' in order['dispatch'] and sched
                and sched in m.state.active_strategies):
            gold_open += economy_effect_of(sched).instant_gold
        rounds[pre[0] * 100 + pre[1]] = {
            'plane': pre[0], 'round': pre[1],
            'gold_after_income': gold_open,
            'gold_close': int(m.state.gold),
            'income': dict(run.last_income),
        }
        if (m.state.hp or 0) <= 0:
            break   # 死亡态(与实机局终同语义)
    return rounds


def _band(vals: list[float]) -> dict:
    if not vals:
        return {'n': 0, 'p10': None, 'median': None, 'p90': None}
    ordered = sorted(vals)

    def pct(p: float) -> float:
        return ordered[min(int(len(ordered) * p), len(ordered) - 1)]

    return {'n': len(ordered), 'p10': pct(0.1),
            'median': statistics.median(ordered), 'p90': pct(0.9)}


def _cmp_rows(live: list[dict], replays: list[dict], plane: int,
              real_key: str, fake_key: str, max_round: int) -> list[dict]:
    """逐轮分布带行(real_key/gold_form/gold_close;fake 同名视图)。"""
    rows = []
    for rnd in range(1, max_round + 1):
        key = (plane, rnd)
        real_vals = [float(g[real_key][key]) for g in live
                     if key in g.get(real_key, {})]
        if fake_key == 'later_gold':
            fake_vals = [float(r['later'][plane * 100 + rnd]
                               ['gold_after_income'])
                         for r in replays
                         if plane * 100 + rnd in r.get('later', {})]
        elif fake_key == 'later_gold_close':
            fake_vals = [float(r['later'][plane * 100 + rnd]['gold_close'])
                         for r in replays
                         if plane * 100 + rnd in r.get('later', {})]
        else:
            fake_vals = [float(r[fake_key][rnd]) for r in replays
                         if rnd in r.get(fake_key, {})]
        rb, fb = _band(real_vals), _band(fake_vals)
        judged = rb['n'] >= MIN_N_FOR_BAND and fb['n'] > 0
        in_band = (judged and rb['p10'] is not None
                   and rb['p10'] <= fb['median'] <= rb['p90'])
        rows.append({'round': rnd, 'real': rb, 'fake': fb,
                     'judged': judged, 'fake_median_in_band': in_band})
    return rows


def _table(rows: list[dict], title: str) -> list[str]:
    lines = [f'## {title}', '',
             '| 轮 | 实机 n | 实机 p10\\|中位\\|p90 | 假局 n '
             '| 假局 p10\\|中位\\|p90 | 在带 |',
             '|---|---|---|---|---|---|']
    for row in rows:
        rb, fb = row['real'], row['fake']

        def fmt(b: dict) -> str:
            if b['median'] is None:
                return '—'
            return (f"{b['p10']:.0f}|{b['median']:.0f}|{b['p90']:.0f}")

        mark = ('—' if not row['judged']
                else ('✓' if row['fake_median_in_band'] else '✗'))
        lines.append(f"| {row['round']} | {rb['n']} | {fmt(rb)} "
                     f"| {fb['n']} | {fmt(fb)} | {mark} |")
    return lines


def _score(rows: list[dict]) -> tuple[int, int]:
    judged = [r for r in rows if r['judged']]
    return (sum(1 for r in judged if r['fake_median_in_band']),
            len(judged))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=str, required=True)
    parser.add_argument('--since', type=str, default='',
                        help='档案时间窗起 YYYYMMDD(game_id 日期;空=全量)')
    parser.add_argument('--until', type=str, default='')
    parser.add_argument('--limit', type=int, default=0,
                        help='只取前 N 局(烟测用;0=全量)')
    args = parser.parse_args()

    import shutil

    from test.conftest import SrTestContext

    ctx = SrTestContext()
    ctx.env_config.is_debug = True
    ctx.current_instance_idx = 99
    from one_dragon.envs.ghproxy_service import GhProxyService
    GhProxyService.update_proxy_url = lambda self: False  # type: ignore[method-assign]
    try:
        ctx.init_by_config()
    except Exception as _e:   # noqa: BLE001  init best-effort(离线可跑)
        print(f'ctx.init_by_config 跳过({_e})')
    # 运行态前置(fixture_controller 同款;runner 不经 pytest fixture,
    # 须显式建 RUNNING 态,否则真 op 首轮即「已停止」退出)
    from test.harness.fixture_controller import enter_running_state
    enter_running_state(ctx)

    out_dir = Path(args.out)
    archives = out_dir / 'archives'
    shutil.rmtree(archives, ignore_errors=True)
    archives.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    live, dedup = extract_live_matches(args.since, args.until, args.limit)
    print(f'实机档案带卡局: {len(live)} 局(提取 {time.time()-t0:.1f}s;'
          f' 时间窗 since={args.since or "全"} until={args.until or "全"})')

    replays: list[dict] = []
    t1 = time.time()
    for i, game in enumerate(live):
        replays.append(run_fake_replay(ctx, game, archives))
        if (i + 1) % 20 == 0:
            print(f'  注入重放 {i+1}/{len(live)}({time.time()-t1:.0f}s)',
                  flush=True)
    print(f'注入重放完成:{len(replays)} 局({time.time()-t1:.0f}s)')

    max_round = 9
    p1_form = _cmp_rows(live, replays, 1, 'gold_form', 'gold', max_round)
    p1_open = _cmp_rows(live, replays, 1, 'gold', 'gold', max_round)
    p1_close = _cmp_rows(live, replays, 1, 'gold_close', 'gold_close',
                         max_round)
    max_round2 = 10
    p2_form = _cmp_rows(live, replays, 2, 'gold_form', 'later_gold',
                        max_round2)
    p2_close = _cmp_rows(live, replays, 2, 'gold_close', 'later_gold_close',
                         max_round2)
    p3_form = _cmp_rows(live, replays, 3, 'gold_form', 'later_gold', 10)
    p3_close = _cmp_rows(live, replays, 3, 'gold_close', 'later_gold_close',
                         10)

    # ---- 注入保真面(重放 vs 剧本,构造性核对;域 = P1 全部 + 假局
    # 实际到达的 P2+ 轮——未到达轮的日程本就不该入列)----
    sched_ok = 0
    sched_miss: list[str] = []
    sched_ok_p1_only = 0
    for game, rep in zip(live, replays, strict=True):
        reached = set(rep['later'].keys())
        expected = {n for p, r, n in game['picks']
                    if p == 1 or (p * 100 + r) in reached}
        if expected == set(rep['held_final']):
            sched_ok += 1
        else:
            sched_miss.append(game['game_id'])
        p1_picks = {n for p, _r, n in game['picks'] if p == 1}
        if p1_picks <= set(rep['held_final']):
            sched_ok_p1_only += 1
    later_rounds = sum(len(r['later']) for r in replays)
    report = {
        'n_live_card_matches': len(live),
        'n_replays': len(replays),
        'archive_window': {'since': args.since, 'until': args.until},
        'dedup_dropped_names': dedup,
        'schedule_reproduced': sched_ok,
        'schedule_reproduced_p1_only': sched_ok_p1_only,
        'schedule_miss_game_ids': sched_miss[:10],
        'later_plane_rounds_total': later_rounds,
        'bands_p1_form_open': p1_form,
        'bands_p1_first_open': p1_open,
        'bands_p1_close': p1_close,
        'bands_p2_form_open': p2_form,
        'bands_p2_close': p2_close,
        'bands_p3_form_open': p3_form,
        'bands_p3_close': p3_close,
        'replay_env_fingerprints': sorted(
            {json.dumps(r['env_version'], sort_keys=True)
             for r in replays}),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / '对拍分布.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    (out_dir / '重放缓存.json').write_text(
        json.dumps([{'game_id': g['game_id'], **rep}
                    for g, rep in zip(live, replays, strict=True)],
                   ensure_ascii=False), encoding='utf-8')

    s_form = _score(p1_form)
    s_close = _score(p1_close)
    md = '\n'.join(
        ['# CW 投资剧本注入 vs 实机带卡局分布对拍(确认性;无数值裁决权)', '',
         f'- 局数:{len(live)}(时间窗 since={args.since or "全"} '
         f'until={args.until or "全"});同键坍缩落选名:{dedup}',
         f'- 日程保真(注入=重放):{sched_ok}/{len(live)}'
         f'(P1-only 口径 {sched_ok_p1_only}/{len(live)});'
         f' P2+ 续跑轮合计:{later_rounds}',
         f'- P1 全轮在带:同帧口径A {s_form[0]}/{s_form[1]},'
         f' 口径B {s_close[0]}/{s_close[1]}',
         '']
        + _table(p1_form, 'P1 口径A-同帧(实机=首个FORM帧 / 假局=期初金;'
                 'G1 同帧时点重提取)')
        + ['']
        + _table(p1_open, 'P1 口径A-旧(实机=轮内首可读帧;T-204 对照面,'
                 '时点不齐留证)')
        + ['']
        + _table(p1_close, 'P1 口径B-轮末(实机=末可读帧 / 假局=期末金)')
        + ['']
        + _table(p2_form, 'P2 口径A-同帧(实机=首个FORM帧 / 假局=期初金)')
        + ['']
        + _table(p2_close, 'P2 口径B-轮末')
        + ['']
        + _table(p3_form, 'P3 口径A-同帧(n<10 不判带,样本披露)')
        + ['']
        + _table(p3_close, 'P3 口径B-轮末(n<10 不判带,样本披露)')
        + ['', '## 边界申报(规范 = sr-od-test/README.md'
           '「对拍与批驱动申报规范」)', '',
           '- **entry 选卡观测缺口(W162 在案)**:match 建立前写点丢失,'
           '实机侧持卡域缺 entry 选卡 → 剧本只覆盖可见选卡域,假局'
           '低估侧;',
           '- **重放树行为偏置**:本批重放运行于合并工作树,树内他批'
           '已落码偏置面(如假环境直出 2★ 演练偏置 '
           'rules.SHOP_DIRECT_OUT_2STAR_P=0.05,非真值)对金分布存在'
           '方向不定扰动;环境指纹见 json replay_env_fingerprints;',
           '- **P2+ 节点日程**:假局 P2+ 节点序列 = seed 真码采样,'
           '非逐局实机节点重放(实机逐轮节点真值在 outcomes 域,'
           '本件不消费);分布带读数为分布级,非逐局对位;',
           '- **P2 轮开快照位**:分支驱动期初金 = 收入后+选卡修正,'
           '与 P1 run_p1 内生快照点同域;实机 FORM 帧若缺 = 该轮出'
           '口径A(n 披露);',
           '- **死亡截断**:假局 hp 归零即停(P2+ 段),与实机局终同'
           '语义;逐轮存活数差异体现在各轮 n。',
           '- **P2+ 备战决策链受假环境幽灵箱缺陷制约(2026-09-10 发现;'
           '精确定位与修复归假环境扩面批)**:P1 段某条 bench 写路径'
           '覆写箱占槽未同步 ``FakeMatch.boxes`` 登记表 → 观察面报告'
           '幽灵箱(boxes=[N] 而 bench 无箱),策略反复 OpenBox(N) 被'
           '环境永拒至 visit 预算耗尽 → P2+ 买动作未发生,假局 P2+ 金'
           '带 = 纯收入累积域。**P2/P3 带只证注入机制可达性(0e 选卡/'
           '收入聚合按日程工作),不构成 P2 经济行为对读**;',
           ''])
    (out_dir / '对拍分布.md').write_text(md + '\n', encoding='utf-8')
    print(md)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
