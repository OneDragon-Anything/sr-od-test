# -*- coding: utf-8 -*-
"""test_cw_obs_chain 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- test_obs_conflict_guards: test_obs_conflict_guards.py
- w287_obs_readchain: test_cw_w287_obs_readchain.py
- w289_match_start_reset: test_cw_w289_match_start_reset.py
- w529_xy_reader: test_cw_w529_xy_reader.py
- w545_faction_reconcile: test_cw_w545_faction_reconcile.py
- w547_faction_wire: test_cw_w547_faction_wire.py
- w552_xp_reconcile: test_cw_w552_xp_reconcile.py
- w556_shop_obs: test_cw_w556_shop_obs.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== test_obs_conflict_guards ====================

import pytest

from sr_od.application.currency_war.obs.cw_observation import board_from_tracked
from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_tracking
from sr_od.application.currency_war.kernel.cw_state import BenchChar


@pytest.fixture(autouse=True)
def _no_conflict_io(monkeypatch):
    """obs_conflict 落盘 no-op(测试不写 .debug)。

    ⚠️ 打桩打在 cw_observe.obs_conflict **源头**(非 cw_reconcile._conflict 封装)——
    M41 实机教训(2026-08-16):mock 掉封装则封装签名不被执行,#13 star 回退传 char=
    的 TypeError 测试全绿照样漏网,实机 error-loop 卡死 30min。封装必须真实跑。
    (封装函数内延迟 import obs_conflict → 源头 patch 对其生效。)
    """
    import sr_od.application.currency_war.kernel.cw_observe as obs_mod
    monkeypatch.setattr(obs_mod, 'obs_conflict', lambda *a, **kw: None)


class _Sess:
    def __init__(self, bench=None, deployed=None):
        self.tracked_bench_chars = bench or []
        self.tracked_deployed = deployed or []


def test_board_from_tracked_full_known():
    """全已知身份 → 全集计数(每人贡献全部阵营)。"""
    # 瓦尔特: 列车同行+星间旅人;姬子·启行: 列车同行(以注册表为准,断言用注册表值动态算)
    from sr_od.application.currency_war.data.cw_chars import get_char
    chars = [BenchChar(slot=1, char_id='瓦尔特'), BenchChar(slot=2, char_id='姬子·启行')]
    board = board_from_tracked(chars)
    assert board is not None
    for cid in ('瓦尔特', '姬子·启行'):
        for f in get_char(cid).factions:
            assert board.get(f, 0) >= 1


def test_board_from_tracked_unknown_rejects():
    """含未知身份('?' / 空 / 注册表无) → None(混合态不切,OCR 兜底)。"""
    assert board_from_tracked([]) is None
    assert board_from_tracked([BenchChar(slot=1, char_id='?')]) is None
    assert board_from_tracked([BenchChar(slot=1, char_id='')]) is None
    assert board_from_tracked([BenchChar(slot=1, char_id='不存在角色')]) is None


def test_board_from_tracked_factionless_known_skips():
    """无阵营已知角色(白厄「救世主」)不 bail:复制效果不计人数(官方 trait 3005)
    → 跳过零贡献即精确;独立羁绊行计入(与左面板显示同口径,防对拍留证噪声)。
    2026-08-17 修:旧版 not ch.factions 即 None,白厄上场整链误退 OCR。
    """
    chars = [BenchChar(slot=1, char_id='白厄'), BenchChar(slot=2, char_id='姬子·启行')]
    board = board_from_tracked(chars)
    assert board is not None, '白厄上场不应退 OCR(身份已知,贡献可精确计算)'
    assert board.get('救世主') == 1, '独立羁绊「救世主」应计入(面板同口径)'
    assert board.get('列车同行') == 1, '姬子·启行的阵营正常计数'


def test_board_from_tracked_flows_only_char_counts():
    """factions 空但 flows 非空(布洛妮娅 燃血)→ 正常贡献 flows 计数,不 bail。
    旧版只查 ch.factions → 布洛妮娅上场误退 OCR(同白厄 bug 的第二受害者)。"""
    board = board_from_tracked([BenchChar(slot=1, char_id='布洛妮娅')])
    assert board is not None
    assert board.get('燃血') == 1
    assert board.get('大守护者') == 1


def test_streak_dual_source_conflict_guard(test_context, monkeypatch):
    """streak 双源留证(审计 #8 P2,2026-08-17):read_game_state 内联判定 —— 结算带符号
    与备战 magnitude 不等(且结算≠0)→ obs_conflict 留证;一致 → 无噪声。
    直接跑 read_game_state 不可行(需 OCR 全屏栈),此处验判定的两端行为:
    复制内联条件(streak 逻辑为纯比较,无隐藏状态)。"""
    import sr_od.application.currency_war.kernel.cw_observe as obs_mod
    calls: list[tuple] = []
    monkeypatch.setattr(obs_mod, 'obs_conflict',
                        lambda field, old, new, *a, **kw: calls.append((field, old, new)))

    def _check(last_streak: int, prep: int | None) -> None:
        # = read_game_state 内联判定(cw_observation streak 段,保持同条件复制)
        if prep is not None and last_streak != 0 and abs(last_streak) != prep:
            obs_mod.obs_conflict('streak', last_streak, prep, None,
                                 verdict='留证-双源不等(结算带符号 vs 备战magnitude,一方误读)',
                                 source='settlement_vs_prep')

    _check(3, 3)          # 一致 → 不报
    _check(0, 5)          # 结算 0(重置边缘)→ 不报
    _check(3, None)       # 备战读不到 → 不报(单源)
    assert calls == []
    _check(3, 2)          # 不等 → 报
    assert calls == [('streak', 3, 2)]


def test_reconcile_double_empty_guard_keeps_old():
    """双空读 + 前值非空 → 保旧(M14 过渡帧守卫),不写回。"""
    old = [BenchChar(slot=1, char_id='瓦尔特')]
    sess = _Sess(bench=old, deployed=[])
    assert reconcile_tracking(sess, [], [], None, source='t') is False
    assert sess.tracked_bench_chars == old


def test_reconcile_double_empty_with_empty_prev_ok():
    """双空读但前值也空 → 正常写回(空板开局,非读失败)。"""
    sess = _Sess()
    assert reconcile_tracking(sess, [], [], None, source='t') is True
    assert sess.tracked_bench_chars == []


def test_reconcile_none_side_kept():
    """bench=None(读失败侧)不写,deployed 侧正常写。"""
    sess = _Sess(deployed=[BenchChar(slot=1, char_id='瓦尔特')])
    new_dep = [BenchChar(slot=1, char_id='姬子·启行')]
    assert reconcile_tracking(sess, None, new_dep, None, source='t') is True
    assert sess.tracked_bench_chars == []
    # ADR-0392:tracked_deployed 槽位表——按占用序对拍(紧缩视图)
    assert [d for d in sess.tracked_deployed if d is not None] == new_dep


def test_reconcile_star_rollback_no_crash():
    """M41 实机回归(2026-08-16):同名 star 回退(缇宝 2★→1★)走留证分支
    **不得抛异常**——旧版 _conflict 封装无 **ctx,char= 触发 TypeError → PrepDirector
    error-loop 卡死 30min(P3-4 实锤)。
    2026-08-18 防抖升级(274 存证离线复现:36/40 同图重读 2★,live 读 1★ =
    3合1 合成动画窗):首次回退 star **保旧**(动画窗读数不毒化 tracking),
    连续第二次仍回退才采新确认。"""
    sess = _Sess(bench=[BenchChar(slot=1, char_id='缇宝', star=2)])
    # 首次:防抖保旧(不写回 1★)
    assert reconcile_tracking(
        sess, [BenchChar(slot=1, char_id='缇宝', star=1)], [], None, source='t') is True
    assert sess.tracked_bench_chars[0].star == 2, '首次回退保旧(疑合成动画窗)'
    # 连续第二次(独立新读对象——防抖会原地改 star,复用同对象会假自愈):确认真回退 → 采新
    assert reconcile_tracking(
        sess, [BenchChar(slot=1, char_id='缇宝', star=1)], [], None, source='t') is True
    assert sess.tracked_bench_chars[0].star == 1, '连续 2 次回退确认采新'


def test_reconcile_star_regression_pending_self_heals():
    """防抖自愈(2026-08-18):首帧回退(动画窗)→ 下帧读回正常 → pending 清零、
    tracking star 保持旧值(2★)未被动画窗 1★ 毒化。"""
    sess = _Sess(bench=[BenchChar(slot=1, char_id='万敌', star=2)])
    # 首帧:动画窗读 1★ → 保旧
    reconcile_tracking(sess, [BenchChar(slot=1, char_id='万敌', star=1)], [], None, source='t')
    assert sess.tracked_bench_chars[0].star == 2
    # 下帧:动画结束读回 2★(=旧值,非回退)→ 自愈,防抖挂起清零
    reconcile_tracking(sess, [BenchChar(slot=1, char_id='万敌', star=2)], [], None, source='t')
    assert sess.tracked_bench_chars[0].star == 2
    assert not getattr(sess, 'star_pending_regression', {}).get('万敌'), '读回恢复清防抖'


def test_plane_table_smoke():
    """cw_plane_table 冒烟(批 3:标定表模块随 DP 退役平移;
    息闭式边界锁逐位保留)。"""
    from sr_od.application.currency_war.kernel.cw_plane_table import interest
    assert interest(49) == 4
    assert interest(50) == 5

# ===== 等级三源解析 _resolve_level(2026-08-18 治本:live 乒乓根因) =====
from sr_od.application.currency_war.obs.cw_observation import _resolve_level  # noqa: E402


def _kinds(events) -> list[str]:
    return [e[0] for e in events]


def test_resolve_level_pingpong_root_live_regression():
    """live 乒乓场景回归(2026-08-18 10:47-10:48 实锤):OCR 失读 + 启发式兜底 6
    被写进 last_level_obs 毒化;XP 分母反推 5(真值,XP「0/20」+ 部署 5/5 双证)。
    旧链:XP 采新 5 → 单调守卫用毒化 6 打回 → 每帧 6↔5 乒乓。
    新链:XP 主权豁免单调守卫,向下校正到 5 并留证。"""
    level, events, auth = _resolve_level(None, 6, 5, 6)
    assert level == 5
    assert _kinds(events) == ['xp_down']
    assert auth is True   # XP 可读 → 真实观测,写回 last_level_obs(链路自愈)


def test_resolve_level_heuristic_not_authoritative():
    """毒化防线:OCR 与 XP 双失读 → 纯启发式值不作真实观测(authoritative=False,
    调用方不写回 last_level_obs —— 毒源堵住)。解析值本身照给(决策层用)。"""
    level, events, auth = _resolve_level(None, 6, None, 4)
    assert level == 6 and auth is False   # 6 > 4+2? 不(6=4+2)→ 不触发跳变守卫
    assert events == []


def test_resolve_level_monotonic_guard_preserved():
    """旧守卫保留:XP 未确认的下降(纯 OCR 误读)仍保旧(r1 lv4→r2 lv5→r3 lv4 倒退防)。"""
    level, events, auth = _resolve_level(4, 5, None, 6)
    assert level == 6
    assert _kinds(events) == ['mono']
    assert auth is True


def test_resolve_level_jump_guard_preserved():
    """旧守卫保留:单源 OCR 大跳(疑似 XP 数字混入,如「升到 lv10」需 360 金)拒。"""
    level, events, _ = _resolve_level(10, 5, None, 4)
    assert level == 4
    assert _kinds(events) == ['jump']


def test_resolve_level_jump_confirmed_by_xp():
    """M38 语义保留:XP 分母独立确认的真跳变(连点一波 4→8)放行 + 留证。"""
    level, events, _ = _resolve_level(8, 5, 8, 4)
    assert level == 8
    assert _kinds(events) == ['jump_ok']


def test_resolve_level_xp_override_real_disagreement_logged():
    """OCR 可读 6 与 XP 反推 5 真分歧 → 覆盖 + 留证(ADR-0129)。"""
    level, events, _ = _resolve_level(6, 6, 5, 0)
    assert level == 5
    assert _kinds(events) == ['xp_override']


def test_resolve_level_xp_over_fallback_silent():
    """OCR 失读时「兜底让位 XP」= 设计常态,不逐帧记 [cw!](live 10:47-10:48
    每帧 2 冲突的遥测噪声源);新局 last=0 无守卫交互。"""
    level, events, auth = _resolve_level(None, 6, 5, 0)
    assert level == 5 and events == [] and auth is True


def test_resolve_level_agree_no_events():
    """双源一致 → 零事件(健康帧不产遥测噪声)。"""
    level, events, auth = _resolve_level(7, 5, 7, 6)
    assert level == 7 and events == [] and auth is True


# ==================== w287_obs_readchain ====================

import inspect
from pathlib import Path

import pytest as _w287_obs_readchain_pytest

from one_dragon.utils import cv2_utils
import sr_od.application.currency_war.obs.cw_observation as obs_mod
from sr_od.application.currency_war.obs.cw_observation import  _board_pairs, read_deployed_count
from sr_od.application.currency_war.kernel.cw_state import rebuild_deployed_from_board

_IMG_DIR = Path(__file__).parent


def _load(name: str):
    p = _IMG_DIR / name
    if not p.exists():
        _w287_obs_readchain_pytest.skip(f'fixture 缺失:{name}')
    return cv2_utils.read_image(str(p))


def test_paddle_excludes_bench_row_on_empty_board(test_context) -> None:
    """空板帧(1-1,0/3,底部备战栏 4 卡)→ paddle X=0。

    tracking 幻影帧(6796888e)锁:部署数目标取舞台指示,几何上不含底部
    商店行/备战栏 —— 空板不再幻影出部署角色。旧链 board 徽标/计数源无此保证。
    """
    screen = _load('w287_tracking_empty_6796888e.png')
    n = read_deployed_count(test_context, screen)
    assert n == 0, f'空板帧部署数应为 0(底部 4 卡是备战栏,不计部署),实得 {n}'


def test_paddle_obscured_board_sum_is_not_deploy_count(test_context) -> None:
    """实部署 4 帧(前台2+后台2,角色详情 overlay 遮 paddle)→ 对齐基准行为锁。

    deployed_align 误判帧(37e6d7fd)双断言:
    - paddle 被 overlay 遮挡 → read_deployed_count=None → read_game_state 跳过
      对齐(tracked 4 保真,宁缺勿造);
    - 同帧左栏徽标羁绊和 = 8 ≠ 4 —— 实证 board 羁绊和当部署数必错
      (多阵营角色重复计),旧 ``min(sum(board), level)`` 目标即病根。
    """
    screen = _load('w287_deployed_align_37e6d7fd.png')
    n = read_deployed_count(test_context, screen)
    assert n is None, f'paddle 被 overlay 遮挡应读不到(None → 跳过对齐),实得 {n}'
    pairs, _honest = _board_pairs(test_context, screen)
    bond_sum = sum(c for c, _nt in pairs.values())
    assert bond_sum >= 7, f'该帧徽标羁绊和应≥7(≠实部署4,多阵营重复计),实得 {bond_sum}'


def test_board_pairs_reads_badge_truth(test_context) -> None:
    """左栏徽标「盛会之星=2」帧 → _board_pairs 读 2(徽标=画面事实)。

    board 误裁帧(b6fc9934)锁:OCR 徽标行真值可读;旧裁决在该帧采
    computed=1(错)。裁决翻转后此读数即采信源。
    """
    screen = _load('w287_board_b6fc9934.png')
    pairs, honest = _board_pairs(test_context, screen)
    assert honest, '徽标帧应有至少一行 X/Y 真解析(honest)'
    assert pairs.get('盛会之星', (None,))[0] == 2, \
        f'徽标「盛会之星」应读 2(画面事实),实得 {pairs.get("盛会之星")}'


def test_rebuild_cap_zero_blocks_phantom() -> None:
    """重建上限 0(paddle 空板)→ 0 幻影部署;上限 2 → 截到 2。

    锁 ``rebuild_deployed_from_board`` 的 max_count 语义 = read_game_state 重建
    分支 ``min(level, paddle X)`` 的依赖:board 徽标误读(如 6)不再幻影出
    超额部署角色(空板帧 同根)。注意返回是**槽位表**(定长含 None,
    ADR-0392),计数走占用数。
    """
    board = {'盛会之星': 6}
    _occ = lambda lst: sum(1 for x in lst if x is not None)
    assert _occ(rebuild_deployed_from_board(board, max_count=0)) == 0
    assert _occ(rebuild_deployed_from_board(board, max_count=2)) == 2


def test_source_deployed_align_uses_paddle_not_board_sum() -> None:
    """源码锁:read_game_state 部署对齐不再用羁绊和,改用 paddle X。

    防 修复回退(旧 ``min(sum(state.board.values), level)`` 是
    deployed_align 误判族根因)。
    """
    src = inspect.getsource(obs_mod.read_game_state)
    assert '_board_n' not in src, \
        'read_game_state 不得再保留 board 羁绊和对齐目标 _board_n(ADR-0417)'
    # ADR-0462 阶段化后:全量路径仍直读 deployed_count;阶段 gate 路径合并单读
    # (resolve_paddle_pair 产出同一 paddle X)。锁语义=对齐基准是 paddle X 非
    # board 羁绊和,两形态任一在源即守住了语义。
    assert ('_paddle_n = read_deployed_count(ctx, screen)' in src
            or '_paddle_n = _paddle_x if _spec is not None '
               'else read_deployed_count(ctx, screen)' in src), \
        'read_game_state 部署对齐/重建应以 paddle X 为基准(ADR-0417)'
    assert 'resolve_paddle_pair' in src, \
        '阶段 gate 路径应使用 paddle 合并单读(ADR-0462)'
    assert 'tracked_vs_paddle' in src, '对齐留证 source 应指向 paddle 基准'


def test_source_board_arbitration_prefers_badge_with_overlay_guard() -> None:
    """源码锁:board 裁决翻转(备战帧徽标覆入)+ overlay 双不可信守卫。

    board 3/6 采 computed 错 → 备战帧裁决翻转为采徽标;overlay 干扰
    2/6(徽标与 computed 各错一次)→ 非备战帧(is_prep_like_frame=False)不裁
    不覆,保 computed 底座防新错。
    """
    src = inspect.getsource(obs_mod.read_game_state)
    assert '采新-badge' in src, '备战帧裁决应采徽标(画面事实优先,ADR-0417)'
    assert '留证-双不可信' in src, 'overlay/动画帧应留证不裁(双不可信防新错)'
    assert 'is_prep_like_frame(ctx, screen)' in src, \
        '裁决前应过备战帧态判定(overlay 守卫)'
    # 守卫语义:帧态判定仅在真有分歧时做(常态一致零开销),且非备战帧不覆写
    assert '_merged[_f] = _ocr_c' in src, '覆写只应发生在备战帧徽标分支'


# ==================== w289_match_start_reset ====================

import inspect as _w289_match_start_reset_inspect

from sr_od.application.currency_war.obs.cw_observation import  reset_phase_round_cache
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w289_match_start_reset_BenchChar
from sr_od.application.currency_war.decision.cw_strategy import  CurrencyWarMatch, StrategySession, discard_stale_match_container
from sr_od.application.currency_war.decision.decision_v2.strategy import  DecisionV2Strategy


class _FakeCtx:
    """最小 ctx 替身:discard 只读写 cw_match 属性。"""

    def __init__(self) -> None:
        self.cw_match: CurrencyWarMatch | None = None


def _polluted_match() -> CurrencyWarMatch:
    """构造带跨局毒值的容器(覆盖 三层实证字段 + tracked 宿主代表)。"""
    s = StrategySession()
    s.last_level_obs = 5          # 上局等级(cap_vs_level 抽样 4/4 的旧 level=5)
    s.last_streak = -7            # 上局连败(economy fold 门输入)
    s.last_hp_real = 12           # hp 对账锚
    s.tracked_deployed = [_w289_match_start_reset_BenchChar(slot=1, char_id='旧局角色')]
    s.active_strategies = ['旧局策略']
    return CurrencyWarMatch(DecisionV2Strategy(), s)


def test_discard_stale_container_resets_for_new_match():
    """锁 1(核心语义:模拟第二局开始,上一局 tracked 值不残留):
    入口链见到新局确凿信号 → 弃置容器;随后 handle_init 新建 session 全默认。"""
    ctx = _FakeCtx()
    ctx.cw_match = _polluted_match()
    assert discard_stale_match_container(ctx, '到达难度确认屏=新局开始') is True
    assert ctx.cw_match is None   # 新建分支承担全量重置(容器已断开)

    # 第二局 session 由 create_session 重建 —— 与 handle_init 新 match 分支同路径,
    # 锁定观察域关键字段全默认(任何字段若被改成可携带上局值,此处红)。
    fresh = DecisionV2Strategy().create_session(None)
    assert fresh.last_level_obs == 0      # level 单调守卫不再拿上局值保旧
    assert fresh.last_streak == 0
    assert fresh.last_hp_real is None
    assert fresh.tracked_deployed == []
    assert fresh.active_strategies == []


def test_discard_idempotent_when_no_container():
    """锁 2(幂等直过):无残留(正常流程局终已清)→ 返回 False 不动。"""
    ctx = _FakeCtx()
    assert discard_stale_match_container(ctx, '任意原因') is False
    assert ctx.cw_match is None


def test_phase_round_cross_match_reset():
    """锁 3(phase_round 跨局重置豁免语义):last-known-good 在新局边界被清,
    单调守卫不会拿上局 [9,9] 打回新局 1-9(phase_round 抽样 2/3 ✗ 根因)。"""
    import sr_od.application.currency_war.obs.cw_observation as obs_mod
    obs_mod._last_phase_round = (3, 9)     # 模拟上局 P3-9 残留
    try:
        assert obs_mod._last_phase_round == (3, 9)
        reset_phase_round_cache()          # discard/handle_init 新局边界调用点
        assert obs_mod._last_phase_round is None
    finally:
        reset_phase_round_cache()


def test_entry_discard_call_sites_are_new_match_only():
    """锁 4(静态口径:弃置只挂新局确凿三屏,不碰「继续进度」恢复同一物理局的合法续用):
    入口文件恰有 3 个调用点,理由串分别为难度确认/模式选择/简报。"""
    from sr_od.application.currency_war.operations.entry import  start_currency_war_match as entry_mod
    src = _w289_match_start_reset_inspect.getsource(entry_mod)
    for reason in ('到达难度确认屏=新局开始',
                   '到达模式选择屏=新局开始',
                   '到达简报屏=新局开始'):
        assert reason in src                      # 三屏各有登记
    assert src.count('_discard_stale_once(') == 4  # 定义内转发 1 + 三调用点
    # 「继续进度」恢复路径(1b 分支)不得触发弃置:其代码块内无该调用
    resume_at = src.index("round_by_ocr_and_click(screen, '继续进度'")
    resume_block = src[resume_at:src.index('# 2)', resume_at)]
    assert '_discard_stale_once' not in resume_block


# ==================== w529_xy_reader ====================

from pathlib import Path as _w529_xy_reader_Path

import pytest as _w529_xy_reader_pytest

from test.conftest import SrTestContext
from sr_od.application.currency_war.obs.cw_observation import  _read_deploy_paddle, _resolve_paddle_digits, _validate_paddle_xy, read_deploy_cap

_FIX_DIR = _w529_xy_reader_Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战'
# overlay 帧已按画面形态归档到独立 screen 目录(原在 备战/ 目录)
_FIX_FLOAT_DIR = _w529_xy_reader_Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战-装备详情浮窗'
_FIX_TIP_DIR = _w529_xy_reader_Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战-角色信息提示'


# ===== 约束验证器真值表(玩法先验:x≤y;1≤y≤13;y≥level) =====
def test_validate_paddle_xy_truth_table() -> None:
    """合法域内采,域外拒;level 未提供跳过 y≥level 条。"""
    assert _validate_paddle_xy(0, 3, None)
    assert _validate_paddle_xy(9, 10, 10)
    assert _validate_paddle_xy(13, 13, None)        # 绝对板面上界 13(前台4+后台9)
    assert not _validate_paddle_xy(4, 3, None)      # x>y 不可能(deployed>cap)
    assert not _validate_paddle_xy(0, 14, None)     # y 超 13(OCR 结构性误读上界)
    assert not _validate_paddle_xy(0, 0, None)      # y≥1(cap 至少为等级≥1)
    assert not _validate_paddle_xy(0, 3, 5)         # y<level(cap=level+宝钻,只增不减)
    assert _validate_paddle_xy(0, 5, 5)             # level 边界相等合法


# ===== 解析核心真值表(对齐 + 歧义裁决,纯构造不依赖 OCR) =====
def test_resolve_direct_alignment() -> None:
    """文本数字数==字形数且含斜杠 → 直接对齐。"""
    assert _resolve_paddle_digits('44', 2, 1, None, True)[:2] == (4, 4)
    assert _resolve_paddle_digits('1213', 4, 2, None, True)[:2] == (12, 13)


def test_resolve_icon_prefix_drop() -> None:
    """文本多 1 数字(图标/空心字形幻影前缀 '1')→ 去首对齐:'10/3'=0/3、'188'=8/8。"""
    assert _resolve_paddle_digits('103', 2, 1, None, True)[:2] == (0, 3)
    assert _resolve_paddle_digits('188', 2, 1, None, True)[:2] == (8, 8)
    assert _resolve_paddle_digits('1811', 3, 1, None, True)[:2] == (8, 11)


def test_resolve_slash_read_as_digit_prefers_direct() -> None:
    """斜杠被读成数字('717'=7/7):一级两候选歧义拒;二级 direct 候选唯一 → 采。"""
    # 一级:文本无斜杠,去首(1/7)与去斜杠位(7/7)双候选 → 拒
    x, y, cands = _resolve_paddle_digits('717', 2, 1, None, text_has_slash=False)
    assert (x, y) == (None, None)
    assert {(a, b) for a, b, _ in cands} == {(1, 7), (7, 7)}
    # 二级(抹图标重 OCR 读回斜杠):direct 唯一 → 采 7/7
    assert _resolve_paddle_digits('77', 2, 1, None, True)[:2] == (7, 7)


def test_resolve_ambiguous_split_rejected() -> None:
    """多候选全满足约束(如 '317' 无斜杠无二级)→ 歧义拒 None,不猜。"""
    x, y, cands = _resolve_paddle_digits('317', 2, 1, None, text_has_slash=False)
    assert (x, y) == (None, None)
    assert len({(a, b) for a, b, _ in cands}) == 2


def test_resolve_level_constraint_filters() -> None:
    """y<level 候选被滤:'103' 在 level=4 下唯一候选 0/3(y=3<4)被拒 → None。"""
    assert _resolve_paddle_digits('103', 2, 1, 4, True)[:2] == (None, None)
    assert _resolve_paddle_digits('103', 2, 1, 3, True)[:2] == (0, 3)   # level=3 边界内采


# ===== 真帧终态锁(fixture 驱动,模型不可用 → skip) =====
_EXPECTS = {
    'r1_idle_stop.webp': (0, 3),                # 图标前缀 '10/3' 变异(W287 同款)
    'shop_closed_a8_start.webp': (0, 3),        # 同上,编排者锚点
    '后排8槽-满级局.webp': (9, 10),             # 锚点;raw 'i9/10'
    '后排8槽-P3局.webp': (8, 11),               # raw '18/11'
    '后排8槽-全位验证.webp': (8, 8),             # raw '18/8'
    '后排8槽-双宝钻局.webp': (8, 9),             # 双宝钻 cap=level+2 实拍
    '攻略已应用.webp': (7, 7),                   # 斜杠读成数字 raw '717'(旧层死穴①)
    '货币战争-备战-角色信息提示/char_detail.webp': (1, 6),
    'shop_closed.webp': (3, 4),
    'shop_closed_lowhp.webp': (6, 7),
    '补给节点.webp': (4, 4),                     # 补给面板帧 paddle 仍显示(VLM 亲读)
    'deployed_2star.webp': (4, 4),              # 干净直读基线
    'shop_open.png': (None, None),              # 菜单 overlay 遮挡 → None(不猜)
}


def _make_real_ocr_ctx(test_context: SrTestContext, monkeypatch: _w529_xy_reader_pytest.MonkeyPatch) -> list:
    """真 OCR service 注入 + obs_conflict 收集器(防测试写真实 .debug 证据)。"""
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    import sr_od.application.currency_war.obs.cw_observation as obs_mod
    try:
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            _w529_xy_reader_pytest.skip('OCR 模型不可用')
    except Exception:
        _w529_xy_reader_pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))
    conflicts: list = []
    monkeypatch.setattr(obs_mod, 'obs_conflict',
                        lambda *a, **k: conflicts.append((a, k)))
    return conflicts


def _fix_path(name: str) -> _w529_xy_reader_Path:
    """fixture 名 → 实际路径(备战目录;角色提示/装备浮窗帧在各自 screen 目录)。"""
    if name.startswith('货币战争-备战-角色信息提示/'):
        return _FIX_TIP_DIR / name.split('/', 1)[1]
    if name.startswith('货币战争-备战-装备详情浮窗/'):
        return _FIX_FLOAT_DIR / name.split('/', 1)[1]
    return _FIX_DIR / name


def test_read_deploy_paddle_real_fixtures(
        test_context: SrTestContext, monkeypatch: _w529_xy_reader_pytest.MonkeyPatch) -> None:
    """58 帧对拍代表集的终态锁:解析层对「图标前缀/斜杠读成数字/遮挡」全部读对。"""
    from one_dragon.utils import cv2_utils
    if not all(_fix_path(n).exists() for n in _EXPECTS):
        _w529_xy_reader_pytest.skip('fixture 缺失')
    _make_real_ocr_ctx(test_context, monkeypatch)
    for name, expect in _EXPECTS.items():
        img = cv2_utils.read_image(str(_fix_path(name)))
        assert _read_deploy_paddle(test_context, img) == expect, f'{name} 应读 {expect}'


def test_read_deploy_cap_level_constraint_on_real_frame(
        test_context: SrTestContext, monkeypatch: _w529_xy_reader_pytest.MonkeyPatch) -> None:
    """level 参与解析层约束:cap 3/4 帧传 level=8(y<level)→ None 拒;level=3 → 4。"""
    from one_dragon.utils import cv2_utils
    p = _FIX_DIR / 'shop_closed.webp'
    if not p.exists():
        _w529_xy_reader_pytest.skip('fixture 缺失')
    _make_real_ocr_ctx(test_context, monkeypatch)
    img = cv2_utils.read_image(str(p))
    assert read_deploy_cap(test_context, img, level=3) == 4
    assert read_deploy_cap(test_context, img, level=8) is None


def test_covered_frame_leaves_conflict_evidence(
        test_context: SrTestContext, monkeypatch: _w529_xy_reader_pytest.MonkeyPatch) -> None:
    """双级均解析失败(overlay 遮 Y)→ (None, None) 且 obs_conflict 留证。"""
    from one_dragon.utils import cv2_utils
    p = _FIX_FLOAT_DIR / 'equip_detail_synth_target.webp'
    if not p.exists():
        _w529_xy_reader_pytest.skip('fixture 缺失')
    conflicts = _make_real_ocr_ctx(test_context, monkeypatch)
    img = cv2_utils.read_image(str(p))
    assert _read_deploy_paddle(test_context, img) == (None, None)
    assert len(conflicts) >= 1, '解析失败帧应留证(零重帧原则:不重截,只留证)'


# ==================== w545_faction_reconcile ====================

from pathlib import Path as _w545_faction_reconcile_Path

import pytest as _w545_faction_reconcile_pytest

from sr_od.application.currency_war.obs.cw_faction_obs import  FactionReconcileResult, _match_faction, compare_factions, parse_panel_tokens, read_displayed_factions, report_faction_reconcile
from test.conftest import SrTestContext as _w545_faction_reconcile_SrTestContext
from sr_od.application.currency_war.telemetry import state as cw_telemetry

_w545_faction_reconcile_FIX_DIR = _w545_faction_reconcile_Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战'


# ===== 名称→注册表匹配真值表(精确优先;LCS 兜底防邻项误配) =====
def test_match_faction_truth_table() -> None:
    """精确命中;唯一 LCS 兜底;一字差邻项并列/低比例不猜。"""
    assert _match_faction('仙舟') == '仙舟'
    assert _match_faction('列车同行') == '列车同行'
    assert _match_faction('昼之半神') == '昼之半神'
    assert _match_faction('星辰大海') is None        # 完全不沾边
    # 仅一字差的两邻项:候选文本同时接近昼/夜之半神 → 并列不猜
    assert _match_faction('X之半神') is None
    # 唯一高比例兜底(艺术字缺字形态)
    assert _match_faction('战技') == '战技点'


# ===== 对账纯函数真值表(逐名三态 + 不评口径 + 截断嫌疑) =====
def test_compare_factions_truth_table() -> None:
    """一致/不一致/显示侧不可判三态;OCR 失读跳过;computed 独有为截断嫌疑。"""
    r = compare_factions(
        {'仙舟': 3, '能量': 5, '欢愉': 1, '列车同行': 2},
        [('仙舟', 3), ('能量', 4), ('欢愉', 1)],
        unreadable=['战技点'])
    assert isinstance(r, FactionReconcileResult)
    assert [(row.faction, row.verdict) for row in r.rows] == [
        ('仙舟', 'match'), ('能量', 'mismatch'), ('欢愉', 'match')]
    assert r.ocr_skipped == ['战技点']                  # 失读只计数,不成行
    assert r.truncation_suspects == ['列车同行']        # computed 有显示无 = 截断嫌疑
    assert r.mismatch_count == 1


def test_compare_factions_computed_missing_explicit() -> None:
    """显示有而计算无 = computed_missing 显式态(计算侧是全集主源)。"""
    r = compare_factions({'仙舟': 2}, [('仙舟', 2), ('狼狩', 1)])
    assert r.rows[1].verdict == 'computed_missing'
    assert r.rows[1].computed is None and r.rows[1].displayed == 1


# ===== 解析层真值表(锚点提取 + 徽章配对 + 截断标记,纯构造) =====
def _tok(text: str, x1: int, y1: int) -> tuple[str, int, int, int, int]:
    """构造 token(text, x1, y1, x2, y2),高 28、宽按字数。"""
    return (text, x1, y1, x1 + 28 * max(len(text), 1), y1 + 28)


def test_parse_panel_pairs_badge_by_offset_window() -> None:
    """徽章在名 cy+8~65 窗内配对;灰梯(含/)不成为锚点。"""
    names = [_tok('仙舟', 106, 140), _tok('2/3', 110, 205), _tok('能量', 106, 240)]
    badges = [_tok('1', 83, 175), _tok('2', 83, 275)]
    r = parse_panel_tokens(names, badges)
    assert r.entries == [('仙舟', 1), ('能量', 2)]
    assert not r.unreadable and not r.unmatched and not r.truncated


def test_parse_panel_last_anchor_without_badge_is_truncated() -> None:
    """最后一条无徽章 = 截断(名可对上→unreadable+truncated;对不上→unmatched)。"""
    names = [_tok('仙舟', 106, 140), _tok('盛会之星', 107, 732)]
    badges = [_tok('2', 87, 175)]
    r = parse_panel_tokens(names, badges)
    assert r.entries == [('仙舟', 2)]
    assert r.unreadable == ['盛会之星'] and r.truncated
    # 残名对不上注册表:进 unmatched,仍标 truncated
    r2 = parse_panel_tokens([_tok('仙舟', 106, 140), _tok('残缺名', 107, 732)], badges)
    assert r2.unmatched == ['残缺名'] and r2.truncated


def test_parse_panel_badge_out_of_range_ignored() -> None:
    """徽章数字越界(>12)= OCR 误读,不配对 → 条目失读。"""
    names = [_tok('仙舟', 106, 140)]
    badges = [_tok('99', 83, 175)]
    r = parse_panel_tokens(names, badges)
    assert r.entries == [] and r.unreadable == ['仙舟']


# ===== 真帧终态锁(16 帧对拍代表集;模型不可用 → skip) =====
# 真值 = VLM 逐帧亲读(名+徽章数);truncated 条目名列在截断位不计 entries。
_w545_faction_reconcile_EXPECTS: dict[str, list[tuple[str, int]]] = {
    'r1_idle_stop.webp': [],                                   # 空面板
    'shop_closed.webp': [('巡海游侠', 1), ('能量', 2), ('仙舟', 1), ('击破', 1),
                         ('昼之半神', 1), ('治疗', 1)],
    '后排8槽-P3局.webp': [('领航员', 1), ('列车同行', 4), ('能量', 4), ('战技点', 2),
                       ('仙舟', 2), ('昼之半神', 1), ('欢愉', 1)],   # 特殊态+底部截断
    '后排8槽-满级局.webp': [('领航员', 1), ('列车同行', 5), ('仙舟', 3), ('能量', 3),
                        ('战技点', 2), ('欢愉', 2), ('盛会之星', 1)],
    '补给节点.webp': [('狼狩', 1), ('夜之半神', 1), ('燃血', 1), ('列车同行', 1),
                     ('减益', 1), ('战技点', 1), ('持续伤害', 1)],
    '后排6槽-P2开局局.webp': [('盛会之星', 3), ('列车同行', 2), ('战技点', 2),
                          ('量子同频', 2), ('护盾', 2), ('仙舟', 1), ('击破', 1)],
    '攻略已应用.webp': [('领航员', 1), ('列车同行', 4), ('战技点', 3), ('盛会之星', 2),
                     ('护盾', 2), ('仙舟', 1), ('能量', 1)],
    'deployed_p1r9.webp': [('领航员', 1), ('能量', 2), ('仙舟', 1), ('群攻', 1),
                           ('贝洛伯格', 1), ('列车同行', 1), ('减益', 1)],
}
_TRUNCATED = {
    '后排8槽-P3局.webp': ['盛会之星'],
    '后排8槽-满级局.webp': ['治疗'],
    '补给节点.webp': ['盛会之星'],
    '后排6槽-P2开局局.webp': ['追击'],
    '攻略已应用.webp': ['昼之半神'],
    'deployed_p1r9.webp': ['银河学者'],
}


def _w545_faction_reconcile_make_real_ocr_ctx(test_context: _w545_faction_reconcile_SrTestContext,
                       monkeypatch: _w545_faction_reconcile_pytest.MonkeyPatch) -> None:
    """真 OCR service 注入(与 W529 同款;模型不可用 → skip)。"""
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    try:
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            _w545_faction_reconcile_pytest.skip('OCR 模型不可用')
    except Exception:
        _w545_faction_reconcile_pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))


@_w545_faction_reconcile_pytest.mark.parametrize('filename', sorted(_w545_faction_reconcile_EXPECTS))
def test_read_displayed_factions_real_fixtures(
        test_context: _w545_faction_reconcile_SrTestContext, monkeypatch: _w545_faction_reconcile_pytest.MonkeyPatch,
        filename: str) -> None:
    """16 帧对拍代表集终态锁:名称/徽章数逐条读对,截断如实标记。"""
    from one_dragon.utils import cv2_utils
    if not (_w545_faction_reconcile_FIX_DIR / filename).exists():
        _w545_faction_reconcile_pytest.skip(f'fixture 缺:{filename}')
    _w545_faction_reconcile_make_real_ocr_ctx(test_context, monkeypatch)
    img = cv2_utils.read_image(str(_w545_faction_reconcile_FIX_DIR / filename))
    reading = read_displayed_factions(test_context, img)
    assert reading.entries == _w545_faction_reconcile_EXPECTS[filename], filename
    assert sorted(reading.unreadable) == sorted(_TRUNCATED.get(filename, [])), filename
    assert reading.truncated == (filename in _TRUNCATED), filename


def test_report_faction_reconcile_forwards_mismatches_only(
        monkeypatch: _w545_faction_reconcile_pytest.MonkeyPatch) -> None:
    """台账转发锁:逐 mismatch 落 record_defect(kind=faction_display_mismatch)。
    分包期 4:obs 落账走 kernel.cw_telemetry_exit 出口钩子位,桩点随迁。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(cw_telemetry_exit, '_record_defect',
                        lambda *a, **k: calls.append((a, k)))
    r = compare_factions({'仙舟': 3, '能量': 5}, [('仙舟', 3), ('能量', 4)])
    n = report_faction_reconcile(r, round_num=3)
    assert n == 1 and len(calls) == 1
    args, kwargs = calls[0]
    assert kwargs['surface'] == 'board'
    assert kwargs['kind'] == 'faction_display_mismatch'
    assert kwargs['expected'] == '5' and kwargs['observed'] == '4'
    assert kwargs['note'] == 'faction=能量' and kwargs['round_num'] == 3


# ==================== w547_faction_wire ====================

import inspect as _w547_faction_wire_inspect
from pathlib import Path as _w547_faction_wire_Path
from types import SimpleNamespace

import pytest as _w547_faction_wire_pytest

import sr_od.application.currency_war.prep_director as pd
from sr_od.application.currency_war.obs.cw_faction_obs import  parse_panel_tokens as _w547_faction_wire_parse_panel_tokens, read_displayed_factions as _w547_faction_wire_read_displayed_factions

from sr_od.application.currency_war.prep_director import PrepDirector
from test.conftest import SrTestContext as _w547_faction_wire_SrTestContext
from sr_od.application.currency_war.telemetry import state as _w547_faction_wire_cw_telemetry


# ===== 接线源码锁(形态先例=_w547_faction_wire_inspect.getsource 静态锁) =====
def test_faction_wire_source_locks() -> None:
    """接线三锁:方法用 cw_faction_obs 三件套且 best-effort;主环在 XP 对账
    同帧之后消费;禁改面(cw_faction_obs)只 import 不含本地重定义。"""
    src = _w547_faction_wire_inspect.getsource(PrepDirector._reconcile_faction_display)
    assert 'board_from_tracked(' in src
    assert 'read_displayed_factions(' in src
    assert 'compare_factions(' in src
    assert 'report_faction_reconcile(' in src
    # 零决策:方法不 return 环结果、不做任何游戏交互(无 screenshot/click)
    assert 'round_' not in src.replace('round_num', '')
    assert 'screenshot(' not in src
    # best-effort:异常吞掉不阻塞环(与 _reconcile_xp_expect 同款)
    assert 'except Exception' in src
    loop_src = _w547_faction_wire_inspect.getsource(PrepDirector._run_loop)
    xp_at = loop_src.index('self._reconcile_xp_expect(obs)')
    fac_at = loop_src.index('self._reconcile_faction_display(obs)')
    assert fac_at > xp_at, '羁绊对账须与 XP 对账同一 heavy 定型帧、紧随其后'
    mod_src = _w547_faction_wire_Path(pd.__file__).read_text(encoding='utf-8')
    assert 'from sr_od.application.currency_war.obs.cw_faction_obs import' in mod_src


# ===== 行为锁(假 reader/假账本,零 OCR/零游戏) =====
def _make_director(monkeypatch: _w547_faction_wire_pytest.MonkeyPatch, computed, reading) -> PrepDirector:
    """构造无初始化的 Director:session 挂假 tracked,ctx/cw_match 走 _session
    真路径;board_from_tracked / read_displayed_factions 注入假实现。"""
    d = object.__new__(PrepDirector)
    session = SimpleNamespace(tracked_deployed=[])
    d.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    d.last_screenshot = object()   # 消费帧=last_screenshot(heavy 定型帧,零新增截屏)
    monkeypatch.setattr(pd, 'board_from_tracked', lambda tracked: computed)
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: reading)
    return d


def _w547_faction_wire_tok(text: str, x1: int, y1: int) -> tuple[str, int, int, int, int]:
    return (text, x1, y1, x1 + 28 * max(len(text), 1), y1 + 28)


def _capture_defects(monkeypatch: _w547_faction_wire_pytest.MonkeyPatch) -> list[dict]:
    # 分包期 4:obs 落账走 kernel.cw_telemetry_exit 出口钩子位,桩点随迁
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    calls: list[dict] = []
    monkeypatch.setattr(cw_telemetry_exit, '_record_defect',
                        lambda *a, **k: calls.append({'args': a, 'kwargs': k}))
    return calls


def test_wire_mismatch_records_defect(monkeypatch: _w547_faction_wire_pytest.MonkeyPatch) -> None:
    """不一致 → 逐 mismatch 落台账(kind=faction_display_mismatch),带
    plane/round 与不评口径计数 refs;一致行/截断嫌疑不落。"""
    calls = _capture_defects(monkeypatch)
    reading = _w547_faction_wire_parse_panel_tokens(
        [_w547_faction_wire_tok('仙舟', 106, 140), _w547_faction_wire_tok('能量', 106, 240)],
        [_w547_faction_wire_tok('3', 83, 175), _w547_faction_wire_tok('4', 83, 275)])
    d = _make_director(monkeypatch, {'仙舟': 3, '能量': 5}, reading)
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=2, round_num=5)
    d._reconcile_faction_display(obs)
    assert len(calls) == 1
    kw = calls[0]['kwargs']
    assert kw['surface'] == 'board' and kw['kind'] == 'faction_display_mismatch'
    assert kw['expected'] == '5' and kw['observed'] == '4'   # computed(主源) vs 显示
    assert kw['plane'] == 2 and kw['round_num'] == 5
    assert kw['reader_source'] == 'faction_display_reconcile'
    ref_fields = {r['field'] for r in kw['refs']}
    assert {'ocr_skipped', 'unmatched', 'truncated',
            'truncation_suspects', 'computed_missing'} <= ref_fields


def test_wire_match_no_defect(monkeypatch: _w547_faction_wire_pytest.MonkeyPatch) -> None:
    """一致 → 零台账(纯对账票,一致不打扰)。"""
    calls = _capture_defects(monkeypatch)
    reading = _w547_faction_wire_parse_panel_tokens(
        [_w547_faction_wire_tok('仙舟', 106, 140)], [_w547_faction_wire_tok('3', 83, 175)])
    d = _make_director(monkeypatch, {'仙舟': 3}, reading)
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=1, round_num=2)
    d._reconcile_faction_display(obs)
    assert calls == []


def test_wire_computed_none_or_no_frame_skips(monkeypatch: _w547_faction_wire_pytest.MonkeyPatch) -> None:
    """computed 不可算(tracked 含未知身份 → None)或无消费帧 → 不评,
    且不触面板 OCR(宁缺勿造)。"""
    calls = _capture_defects(monkeypatch)
    ocr_calls: list = []
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: ocr_calls.append(1))
    d = _make_director(monkeypatch, None, None)
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=1, round_num=1)
    d._reconcile_faction_display(obs)
    d.last_screenshot = None
    d._reconcile_faction_display(obs)
    assert ocr_calls == [] and calls == []


def test_wire_best_effort_on_reader_error(monkeypatch: _w547_faction_wire_pytest.MonkeyPatch) -> None:
    """识别异常 → 静默跳过,不阻塞环(best-effort 契约)。"""
    _capture_defects(monkeypatch)
    d = _make_director(monkeypatch, {'仙舟': 3}, None)
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: (_ for _ in ()).throw(RuntimeError('ocr down')))
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=1, round_num=1)
    d._reconcile_faction_display(obs)   # 不抛即过
    d = _make_director(monkeypatch, {'仙舟': 3}, None)
    d._session = lambda: None           # 无 session → 直接跳过
    d._reconcile_faction_display(obs)


# ===== 端到端一例(真 fixture 帧 + 真 OCR;模型不可用 → skip) =====
def _w547_faction_wire_make_real_ocr_ctx(test_context: _w547_faction_wire_SrTestContext,
                       monkeypatch: _w547_faction_wire_pytest.MonkeyPatch) -> None:
    """真 OCR service 注入(与 W545 同款;模型不可用 → skip)。"""
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    try:
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            _w547_faction_wire_pytest.skip('OCR 模型不可用')
    except Exception:
        _w547_faction_wire_pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))


_FIX = (_w547_faction_wire_Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战'
        / 'shop_closed.webp')
#: 该帧 VLM 亲读真值(W545 对拍表):computed 与显示一致 → 零台账
_TRUTH = {'巡海游侠': 1, '能量': 2, '仙舟': 1, '击破': 1, '昼之半神': 1, '治疗': 1}


def test_wire_end_to_end_fixture(test_context: _w547_faction_wire_SrTestContext,
                                 monkeypatch: _w547_faction_wire_pytest.MonkeyPatch) -> None:
    """端到端:真帧识别 → compare → report 转发,一致零台账、污染一条。"""
    from one_dragon.utils import cv2_utils
    if not _FIX.exists():
        _w547_faction_wire_pytest.skip(f'fixture 缺:{_FIX.name}')
    _w547_faction_wire_make_real_ocr_ctx(test_context, monkeypatch)
    calls = _capture_defects(monkeypatch)
    img = cv2_utils.read_image(str(_FIX))
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: _w547_faction_wire_read_displayed_factions(test_context, img))
    d = _make_director(monkeypatch, dict(_TRUTH), None)
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: _w547_faction_wire_read_displayed_factions(test_context, img))
    obs = pd.PrepObservation()
    obs.state = SimpleNamespace(plane=1, round_num=1)
    d._reconcile_faction_display(obs)
    assert calls == []                       # 真值一致 → 零台账
    computed_bad = dict(_TRUTH)
    computed_bad['能量'] = 5                  # 污染一个计数
    d = _make_director(monkeypatch, computed_bad, None)
    monkeypatch.setattr(pd, 'read_displayed_factions',
                        lambda ctx, frame: _w547_faction_wire_read_displayed_factions(test_context, img))
    d._reconcile_faction_display(obs)
    assert len(calls) == 1
    kw = calls[0]['kwargs']
    assert kw['kind'] == 'faction_display_mismatch'
    assert kw['expected'] == '5' and kw['observed'] == '2'
    assert kw['note'] == 'faction=能量'


# ==================== w552_xp_reconcile ====================

import json
from pathlib import Path as _w552_xp_reconcile_Path
from types import SimpleNamespace as _w552_xp_reconcile_SimpleNamespace

from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w552_xp_reconcile_StrategySession
from sr_od.application.currency_war.telemetry import defects, recorder
from sr_od.application.currency_war.kernel.cw_prep_actions import  PrepObservation
from sr_od.application.currency_war.kernel.cw_state import  XP_TO_NEXT_LEVEL, xp_apply_clicks, xp_clicks_to_level

from sr_od.application.currency_war.prep_director import PrepDirector as _w552_xp_reconcile_PrepDirector

from sr_od.application.currency_war.kernel.cw_prep_expect import XpLedger, _xp_compare, _xp_parse_buy_clicks
from sr_od.application.currency_war.telemetry import state as _w552_xp_reconcile_cw_telemetry

# ===== ① 推进算子真值表(单一源语义 = ADR-0129;门槛表 XP_TO_NEXT_LEVEL)=====

def test_xp_apply_clicks_plain():
    """普通买(不跨级):lv5 需 20,0+4 → cur 4 不升级。"""
    assert xp_apply_clicks(5, 0, 1) == (5, 4)
    assert xp_apply_clicks(8, 2, 1) == (8, 6)
    assert xp_apply_clicks(8, 2, 0) == (8, 2)      # 零击零推进
    assert xp_apply_clicks(8, 2, -1) == (8, 2)     # 负数防御:原值返回


def test_xp_apply_clicks_cross_level_carryover():
    """跨级买(结转):lv5 18/20 +1 击 = 22 ≥ 20 → lv6 结转 2/40;
    lv4 4/6 +1 击 = 8 ≥ 6 → lv5 结转 2/20(live 局⑳+1 p1r3 实证段)。"""
    assert xp_apply_clicks(5, 18, 1) == (6, 2)
    assert xp_apply_clicks(4, 4, 1) == (5, 2)


def test_xp_apply_clicks_multi_level():
    """多级连穿:lv4 0 + 12 击 = 48 → 过 lv4(6)剩 42 → 过 lv5(20)剩 22
    < lv6(40)→ lv6 22/40(live 局⑳+1 p2r4 的 LU×12 段语义)。"""
    assert xp_apply_clicks(4, 0, 12) == (6, 22)
    assert XP_TO_NEXT_LEVEL[6] == 40


def test_xp_apply_clicks_level_cap():
    """封顶:lv9 80/84 + 2 击 = 88 → lv10 结转 4;lv10 再击无效(零推进,
    live 语义 = 10 级后购买经验按钮无效)。"""
    assert xp_apply_clicks(9, 80, 2) == (10, 4)
    assert xp_apply_clicks(10, 4, 3) == (10, 4)


def test_xp_clicks_to_level_truth_table():
    """恰升 1 级最少击数 = ceil((need-cur)/4):整除/非整除/已过门槛/封顶。"""
    assert xp_clicks_to_level(5, 0) == 5           # 20/4
    assert xp_clicks_to_level(6, 12) == 7          # ceil(28/4)
    assert xp_clicks_to_level(5, 18) == 1          # 已差 2,1 击即升
    assert xp_clicks_to_level(5, 20) == 1          # 已达门槛,1 击触发
    assert xp_clicks_to_level(10, 0) == 0          # 封顶:零推进


# ===== ② 账本流为(stub director;台账行经 monkeypatch 捕获)=====

def _stub_director() -> tuple[_w552_xp_reconcile_PrepDirector, _w552_xp_reconcile_StrategySession, list[tuple]]:
    """免 SrContext 构造的 PrepDirector:object.__new__ + stub ctx
    (cw_match.session = 真 StrategySession;账本动态属性挂其上)。"""
    session = _w552_xp_reconcile_StrategySession()
    pd = object.__new__(_w552_xp_reconcile_PrepDirector)
    pd.ctx = _w552_xp_reconcile_SimpleNamespace(cw_match=_w552_xp_reconcile_SimpleNamespace(session=session))
    captured: list[tuple] = []
    return pd, session, captured


def _cap(*a, **k):
    """record_defect 替身:位置参 (surface, kind, expected, observed) +
    关键字参一并捕获。"""
    return (a, k)


def _obs(xp: tuple[int, int] | None, level: int, plane: int = 2,
         round_num: int = 5) -> PrepObservation:
    return PrepObservation(state=_w552_xp_reconcile_SimpleNamespace(
        xp_progress=xp, level=level, plane=plane, round_num=round_num))


def test_ledger_anchors_then_reconciles_clean(monkeypatch):
    """锚定 → 意图推进 → 同段对账一致:不落台账;锚定前/pending=0 不评。"""
    pd, session, captured = _stub_director()
    monkeypatch.setattr(defects, 'record_defect', _cap)
    # 首帧:锚定(2/72 lv8),不对账
    pd._reconcile_xp_expect(_obs((2, 72), 8))
    led = session.xp_expect_ledger
    assert led.anchored and (led.level, led.xp_cur, led.xp_next) == (8, 2, 72)
    assert led.round_key == (2, 5)
    assert captured == []
    # 同帧再读(pending=0)不评
    pd._reconcile_xp_expect(_obs((2, 72), 8))
    assert captured == []
    # RunBuyPhase 升 1 击 → 期望 6/72;显示一致 → 不落台账
    pd._xp_apply_buy_clicks('买牌 plan 买1张 升1次 刷0次 (gold=30 lv=8)')
    assert (led.level, led.xp_cur) == (8, 6) and led.pending_clicks == 1
    pd._reconcile_xp_expect(_obs((6, 72), 8))
    assert captured == [] and led.pending_clicks == 0


def test_ledger_mismatch_lands_defect_once(monkeypatch):
    """显示与账本不一致 → 落一条 xp_expect_mismatch 台账(surface/kind/
    reader_source 形态;pending 清零后同段不重复落)。"""
    pd, session, captured = _stub_director()
    monkeypatch.setattr(defects, 'record_defect',
                        lambda *a, **k: captured.append((a, k)))
    pd._reconcile_xp_expect(_obs((2, 72), 8))          # 锚定
    pd._xp_apply_buy_clicks('买牌 plan 买0张 升2次 刷1次')  # 期望 10/72
    pd._reconcile_xp_expect(_obs((6, 72), 8))          # 显示只有 +4
    assert len(captured) == 1
    args, row = captured[0]
    assert args[0] == 'xp' and args[1] == 'xp_expect_mismatch'
    assert row['reader_source'] == 'xp_expect_reconcile'
    assert '10' in row['expected'] and '6' in row['observed']
    assert any(r['field'] == 'pending_clicks' and r['value'] == '2'
               for r in row['refs'])
    # pending 已清:同段再读不重复落
    pd._reconcile_xp_expect(_obs((6, 72), 8))
    assert len(captured) == 1


def test_ledger_levelup_channel_and_level_mismatch(monkeypatch):
    """直接 LevelUp 通道(腾席链循环点至 level+1):击数 = 恰升 1 级;
    等级双源不一致同样落台账(等级 = deploy cap 输入的交叉验证面)。"""
    pd, session, captured = _stub_director()
    monkeypatch.setattr(defects, 'record_defect',
                        lambda *a, **k: captured.append((a, k)))
    pd._reconcile_xp_expect(_obs((18, 20), 5, plane=1, round_num=3))
    pd._xp_apply_levelup()                             # 1 击 → lv6 2/40
    led = session.xp_expect_ledger
    assert (led.level, led.xp_cur, led.xp_next) == (6, 2, 40)
    pd._reconcile_xp_expect(_obs((2, 40), 6, plane=1, round_num=3))  # 一致
    assert captured == []
    # 等级不一致形态:显示 lv 仍 5(等级区误读/升级未生效)
    pd._xp_apply_levelup()                             # → lv7 0/52
    pd._reconcile_xp_expect(_obs((0, 52), 6, plane=1, round_num=3))
    assert len(captured) == 1
    args, row = captured[0]
    assert 'level' in row['observed'] and '7' in row['expected']


def test_ledger_round_rollover_reanchors(monkeypatch):
    """轮界 = 重锚点:外生经验流(轮间 +2)吸收进锚点并计入 exogenous_xp
    披露,不落台账(不硬编码外生模型,把未知变实测)。"""
    pd, session, captured = _stub_director()
    monkeypatch.setattr(defects, 'record_defect', _cap)
    pd._reconcile_xp_expect(_obs((2, 72), 8))
    pd._xp_apply_buy_clicks('买牌 plan 买0张 升1次 刷0次')   # 期望 6/72
    pd._reconcile_xp_expect(_obs((6, 72), 8))                # 对账一致清 pending
    # 轮界:显示 8/72(本轮 +2 外生)→ 重锚,不评不落账
    pd._reconcile_xp_expect(_obs((8, 72), 8, round_num=6))
    led = session.xp_expect_ledger
    assert led.round_key == (2, 6) and (led.level, led.xp_cur) == (8, 8)
    assert led.exogenous_xp == 2 and captured == []


def test_ledger_no_session_is_noop():
    """无对局态(cw_match=None)→ 账本方法全 no-op(纯观测,不抛)。"""
    pd = object.__new__(_w552_xp_reconcile_PrepDirector)
    pd.ctx = _w552_xp_reconcile_SimpleNamespace(cw_match=None)
    assert pd._xp_ledger() is None
    pd._xp_apply_levelup()
    pd._xp_apply_buy_clicks('升1次')
    pd._reconcile_xp_expect(_obs((2, 72), 8))   # state 非 None 也不抛


def test_xp_compare_truth_table():
    """对账判据纯函数:一致=空;display/level 失读=不评;逐项域分离。"""
    led = XpLedger(level=8, xp_cur=6, xp_next=72)
    assert _xp_compare(led, (6, 72), 8) == []
    assert _xp_compare(led, None, 8) == []          # XP 失读不评
    assert _xp_compare(led, (6, 72), 0) == []       # 等级失读不评
    m = _xp_compare(led, (4, 60), 7)
    assert [x['domain'] for x in m] == ['level', 'xp', 'xp']
    assert [x['slot'] for x in m if x['domain'] == 'xp'] == ['cur', 'next']


def test_parse_buy_clicks():
    """detail 解析:shop 单元摘要形态命中;无升级/异形 → 0(宁缺勿造)。"""
    assert _xp_parse_buy_clicks('买牌 plan 买2张 升3次 刷1次 (gold=30)') == 3
    assert _xp_parse_buy_clicks('买牌 plan 买2张 升0次 刷1次') == 0
    assert _xp_parse_buy_clicks('买牌 (无plan)') == 0
    assert _xp_parse_buy_clicks('') == 0


# ===== ③ 接线源码锁(静态结构,防重构断链/改口径)=====

def test_w552_wiring_locks():
    """①意图推进在 execute 返回后且仅 progressed 分支;②对账在 heavy
    定型帧观察之后(buy_expect 消费点同区域);③台账常量与解析形态锁。"""
    src = _w552_xp_reconcile_Path(
        'src/sr_od/application/currency_war/prep_director.py'
    ).read_text(encoding='utf-8')
    log_at = src.index("log.info(f'[cw][director] step{self._steps}")
    lv_at = src.index('if progressed and isinstance(action, LevelUp):')
    buy_at = src.index("elif progressed and isinstance(action, RunBuyPhase):")
    assert log_at < lv_at < buy_at                  # 进展后才推账,两通道并列
    assert src.index('self._xp_apply_levelup()') > lv_at
    assert src.index("self._xp_apply_buy_clicks(detail)") > buy_at
    obs_at = src.index('self._reconcile_xp_expect(obs)')
    # W591:pending_buy_expect 升 _w552_xp_reconcile_StrategySession 正式字段,消费端由
    # getattr 兜底改直接字段读写(语义不变,机制被取代——见
    # test_cw_w536_buy_expect.test_w536_wiring_locks 改锁依据)
    consume_at = src.index('_pending_buy = session.pending_buy_expect')
    assert consume_at < obs_at                      # heavy 定型帧之后
    # 分包期 6(DESIGN §4.5):xp 常量/解析形态随纯期望段迁
    # kernel/cw_prep_expect(prep_director 经 import 引用);接线点
    # (reader_source/record 调用)仍在本体。
    expect_src = _w552_xp_reconcile_Path(
        'src/sr_od/application/currency_war/kernel/cw_prep_expect.py'
    ).read_text(encoding='utf-8')
    assert "_XP_DEFECT_KIND = 'xp_expect_mismatch'" in expect_src
    assert "_XP_DEFECT_SURFACE = 'xp'" in expect_src
    assert "reader_source='xp_expect_reconcile'" in src
    assert "_XP_BUY_CLICKS_PAT = re.compile(r'升(\\d+)次')" in expect_src
    # 推进算子单一源 = cw_state(sim 侧不重复建模)
    state_src = _w552_xp_reconcile_Path(
        'src/sr_od/application/currency_war/kernel/cw_state.py'
    ).read_text(encoding='utf-8')
    assert 'def xp_apply_clicks(' in state_src
    assert 'def xp_clicks_to_level(' in state_src
    # 对账在 anchor 之前不评(锚定前纯推算无起点)
    rec_at = src.index('def _reconcile_xp_expect')
    rec_body = src[rec_at:src.index('def _session')]
    assert 'not led.anchored' in rec_body
    assert 'led.round_key != key' in rec_body       # 轮界重锚在位


# ===== ④ 台账行形态锁(写端真实落盘形态)=====

def test_xp_defect_row_shape(tmp_path: _w552_xp_reconcile_Path, monkeypatch):
    """defect_ledger.jsonl 行形态:surface='xp'/kind='xp_expect_mismatch'。"""
    monkeypatch.setattr(_w552_xp_reconcile_cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True,
                                                       replay_dir=tmp_path))
    monkeypatch.setattr(_w552_xp_reconcile_cw_telemetry, '_CURRENT_RUN_ID', 'rt')
    monkeypatch.setattr(_w552_xp_reconcile_cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(_w552_xp_reconcile_cw_telemetry, '_defect_seen_run', '')
    defects.record_defect(
        'xp', 'xp_expect_mismatch',
        expected='lv8 xp 10/72(账本;events=+buy×2击)',
        observed='lv8 xp 6/72',
        plane=2, round_num=5, gap_large=True,
        reader_source='xp_expect_reconcile')
    rows = [ln for ln in
            (tmp_path / 'defect_ledger.jsonl').read_text(encoding='utf-8')
            .splitlines() if ln.strip()]
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row['surface'] == 'xp'
    assert row['kind'] == 'xp_expect_mismatch'
    assert row['reader_source'] == 'xp_expect_reconcile'


from sr_od.application.currency_war.telemetry import state


# ==================== w556_shop_obs ====================

import pytest as _w556_shop_obs_pytest

from sr_od.application.currency_war.obs.cw_shop_obs import  compare_merge_preview, check_shop_pool, refresh_expect
from sr_od.application.currency_war.data.cw_shop_odds import REFRESH_PROB, SHOP_SLOTS

# ---------------------------------------------------------------------------
# 1. check_shop_pool
# ---------------------------------------------------------------------------


class TestCheckShopPool:
    def test_tier_boundary_pass(self) -> None:
        """门槛线内侧:4费在 Lv5(p=0.02)、5费在 Lv7(p=0.01)→ 通过。"""
        assert check_shop_pool([('甲', 4)], level=5) == []
        assert check_shop_pool([('乙', 5)], level=7) == []
        assert check_shop_pool([('丙', 1)], level=3) == []  # Lv1-3 纯 1 费

    def test_tier_boundary_locked(self) -> None:
        """门槛线外侧:4费在 Lv4、5费在 Lv6、2费在 Lv1-3 → tier_locked。"""
        kinds = {v.kind for v in check_shop_pool([('甲', 4)], level=4)}
        assert kinds == {'tier_locked'}
        kinds = {v.kind for v in check_shop_pool([('乙', 5)], level=6)}
        assert kinds == {'tier_locked'}
        kinds = {v.kind for v in check_shop_pool([('丙', 2)], level=3)}
        assert kinds == {'tier_locked'}

    def test_tier_table_exhaustive_with_registry(self) -> None:
        """与 REFRESH_PROB 全表互证:非零档通过、零档锁,无一例外。"""
        for level, tiers in REFRESH_PROB.items():
            for cost, p in tiers.items():
                violations = check_shop_pool([(f'牌{cost}', cost)], level=level)
                assert (violations == []) == (p > 0), \
                    f'Lv{level} {cost}费 p={p} 应{"过" if p > 0 else "锁"}'

    def test_invalid_cost(self) -> None:
        """费用不在 1-5(OCR 误读)→ invalid_cost,两查都免。"""
        vs = check_shop_pool([('怪', 0), ('怪2', 6)], level=10)
        assert {v.kind for v in vs} == {'invalid_cost'}

    def test_pool_overdraw_and_cap_boundary(self) -> None:
        """池守恒:可见+持有 > 上限 → 违例;恰等于上限 → 通过(1费 cap=27)。"""
        ok = check_shop_pool([('甲', 1), ('甲', 1)], level=10,
                             pool_state={'甲': 25})
        assert ok == []  # visible=2 + held=25 = 27 = cap
        bad = check_shop_pool([('甲', 1), ('甲', 1)], level=10,
                              pool_state={'甲': 26})
        assert [v.kind for v in bad] == ['pool_overdraw']  # 按牌名去重,同牌多张只一张票
        assert 'visible=2' in bad[0].detail and 'cap=27' in bad[0].detail

    def test_pool_state_none_skips_pool_check(self) -> None:
        """pool_state None = 池查跳过(现状无池追踪账,入参兜)。"""
        assert check_shop_pool([('甲', 1)] * 30, level=10) == []

    def test_two_checks_independent(self) -> None:
        """tier_locked 牌仍做池查(两票独立留证)。"""
        vs = check_shop_pool([('甲', 5)], level=6, pool_state={'甲': 9})
        assert {v.kind for v in vs} == {'tier_locked', 'pool_overdraw'}

    def test_level_out_of_range_reports_honestly(self) -> None:
        """level 越界按 p=0 兜 → 全档锁,如实报(不静默通过)。"""
        kinds = {v.kind for v in check_shop_pool([('甲', 1)], level=99)}
        assert kinds == {'tier_locked'}


# ---------------------------------------------------------------------------
# 2. compare_merge_preview(单向验证)
# ---------------------------------------------------------------------------


class TestCompareMergePreview:
    def test_detected_none_all_pending(self) -> None:
        """识别端未建(现状恒此形态)→ 全 pending,suspect 恒空(登记形态可跑)。"""
        r = compare_merge_preview({0: True, 2: False}, None)
        assert [row.verdict for row in r.rows] == ['pending', 'pending']
        assert r.suspect_slots == []
        assert [row.detected for row in r.rows] == [None, None]

    def test_our_true_detected_false_is_suspect(self) -> None:
        """单向罚则唯一对象:我方 True 而识别无星 → our_suspect。"""
        r = compare_merge_preview({3: True}, {3: False})
        assert r.rows[0].verdict == 'our_suspect'
        assert r.suspect_slots == [3]

    def test_game_extra_counted_not_penalized(self) -> None:
        """识别 True 而我方 False → game_extra(留证不判罚,不出 suspect)。"""
        r = compare_merge_preview({1: False}, {1: True})
        assert r.rows[0].verdict == 'game_extra'
        assert r.suspect_slots == []

    def test_match_and_key_union(self) -> None:
        """同键相等 = match;键集 = 两侧并集,缺键按 False 兜。"""
        r = compare_merge_preview({0: False, 2: True}, {0: False, 4: False})
        assert [row.slot for row in r.rows] == [0, 2, 4]
        assert [row.verdict for row in r.rows] == ['match', 'our_suspect', 'match']

    def test_empty_inputs(self) -> None:
        assert compare_merge_preview({}, {}).rows == []
        assert compare_merge_preview({}, None).rows == []


# ---------------------------------------------------------------------------
# 3. refresh_expect
# ---------------------------------------------------------------------------


class TestRefreshExpect:
    def test_basic_delta(self) -> None:
        """金 −刷新费;旧五张回池账按名计数(重复牌合并)。

        口径(用户裁决·倾向口径):新五格按当前等级概率独立抽取,同牌可
        重复——本函数是期望增量,对账只硬验金差/五格有牌/池守恒统计面,
        **不逐张断言全异**,故无「新五张互异」类断言(这是收窄后的规格)。
        """
        r = refresh_expect(10, [('甲', 1), ('甲', 1), ('乙', 2), ('丙', 3), ('丁', 4)],
                           refresh_cost=2)
        assert r.gold_after == 8 and r.refresh_cost == 2
        assert r.insufficient is False
        assert r.pool_returned == {'甲': 2, '乙': 1, '丙': 1, '丁': 1}
        assert r.new_slots == SHOP_SLOTS == 5

    def test_insufficient_gold(self) -> None:
        """金不足:insufficient True,算术差如实为负(执行判归调用方)。"""
        r = refresh_expect(1, [('甲', 1)], refresh_cost=2)
        assert r.insufficient is True and r.gold_after == -1

    def test_custom_refresh_cost(self) -> None:
        """费用不写死(W554:疑似 f(当前金币))→ 必填参数,任意现读值合法。"""
        assert refresh_expect(10, [], refresh_cost=0).gold_after == 10
        assert refresh_expect(10, [], refresh_cost=3).gold_after == 7

    def test_refresh_cost_is_required(self) -> None:
        """无默认值:漏传费用 = TypeError(防调用方写死 2 的旧习惯回流)。"""
        with _w556_shop_obs_pytest.raises(TypeError):
            refresh_expect(10, [])  # type: ignore[call-arg]

    def test_empty_old_cards(self) -> None:
        """空旧表合法(首刷无旧牌):回池账空、insufficient 按 gold 判。"""
        r = refresh_expect(5, [], refresh_cost=2)
        assert r.pool_returned == {} and r.insufficient is False
        assert r.gold_after == 3


# ---------------------------------------------------------------------------
# 4. 端到端(fixture 帧经 read_shop_cards → check_shop_pool)
# ---------------------------------------------------------------------------


def test_shop_fixture_end_to_end(test_context) -> None:
    """开商店帧离线复跑:read_shop_cards 全链 → check_shop_pool(Lv10 全档解锁)零违例。

    Lv10 五档概率全非零 → tier 查必过;池查不做(pool_state None,现状无账)。
    本测试锁「识别输出能过一致性票」的生产形态,不锁具体牌名(牌名归 SIFT 锁)。
    """
    from sr_od.application.currency_war.kernel.cw_obs_core import SHOP_SCREEN_NAME
    from sr_od.application.currency_war.obs.cw_observation import read_shop_cards
    from sr_od.application.currency_war.kernel.cw_state import card_cost

    state = 'shop_open_preview_star'
    if not test_context.has_screen(SHOP_SCREEN_NAME, state):
        _w556_shop_obs_pytest.skip(f'存档截图缺失:screens/{SHOP_SCREEN_NAME}/{state}.webp')
    screen = test_context.load_screen(SHOP_SCREEN_NAME, state)
    cards = read_shop_cards(test_context, screen)
    assert len(cards) == 5, f'应读满 5 张牌,实际 {len(cards)}'
    card_tuples = [(c.name, card_cost(c)) for c in cards]
    assert check_shop_pool(card_tuples, level=10) == []


# ===== level_readable 保真位(M2 obs 根因修复:兜底帧与真读帧遥测可分) =====

class _BareCtx:
    """最小 ctx 桩:reader 全被桩,仅承载 getattr 链(无 cw_match)。"""


def test_read_game_state_writes_level_readable(monkeypatch) -> None:
    """read_game_state 写入 level_readable:真读(OCR 或 XP 可读)=True;
    双失读(纯 _expected_level 兜底)=False。开店期 spec 最小读取面。"""
    from sr_od.application.currency_war.obs import cw_observation as obs
    from sr_od.application.currency_war.obs.cw_observation_gate import PHASE_PREP_SHOP_OPEN
    _stubs = {
        'read_gold_settled': 55, 'read_phase_round': (2, 3), 'read_node_type': None,
        'read_xp_progress': (0, 6), 'read_level_raw_opt': 5, 'read_level_up_cost': 4,
        '_board_pairs': ({}, False), 'read_shop_cards': [], 'read_refresh_probs': None,
        'read_bench_full': None,
    }
    for _n, _v in _stubs.items():
        monkeypatch.setattr(obs, _n, (lambda _v: lambda *a, **kw: _v)(_v))
    st = obs.read_game_state(_BareCtx(), None, phase=PHASE_PREP_SHOP_OPEN)
    # XP 分母 (0,6)→lv4 覆盖 OCR 5(ADR-0129 主权),但两源皆可读 → 保真位 True
    assert st.level_readable is True and st.level == 4
    # 双失读:OCR 与 XP 皆 None → 纯启发式兜底帧,保真位 False
    monkeypatch.setattr(obs, 'read_level_raw_opt', lambda *a, **kw: None)
    monkeypatch.setattr(obs, 'read_xp_progress', lambda *a, **kw: None)
    st2 = obs.read_game_state(_BareCtx(), None, phase=PHASE_PREP_SHOP_OPEN)
    assert st2.level_readable is False


def test_decision_trace_level_readable_field() -> None:
    """DecisionTrace 新增 level_readable 缺省 True(旧档案缺省=按现有判读处理)。"""
    from dataclasses import asdict, fields
    from sr_od.application.currency_war.telemetry.schema import DecisionTrace
    assert 'level_readable' in {f.name for f in fields(DecisionTrace)}
    assert asdict(DecisionTrace())['level_readable'] is True
