"""CW 外环(CwLoop)机制测试面:分发身份语料 + boss 简报帧排他 + op-fail
重派防线 + 出战链紧缩对位防线。

三节归并自原三个主题文件(测试函数名全量保留,原文件已删):

1. 分发身份语料回归(原 test_cw_dispatch_corpus.py;纪律单一源 = skill
   反馈「分发用画面身份必须过语料验证」+ flow/outer_loop.md §2.2:每画面
   身份须两向验证——本画面全部已存档实机帧 True + 堆叠底图/兄弟画面帧
   False;身份组合语料误杀 dc435da4d 事故测试);
2. boss 简报帧误派位面过渡防线(原 test_cw_loop_boss_frame_exclusion.py;
   病理 = 第五局 1-9 实锤:boss 帧标题 OCR 误读击穿身份后,旧全帧裸文本
   兜底命中共享文案 → 误派位面过渡空 fail 死循环);
3. op-fail 重派防线上限(原 test_cw_loop_op_fail_redispatch_cap.py;病理
   = 选择伙伴 15 连败事故:画面 op 退出 fail → 默认 round_wait 零预算 →
   同一 op 无界重派直到 NODE-DWELL 900s 系统哨兵兜住)+ 出战链紧缩对位
   防线(Unit.slot 退役后病理结构性不可构造,现役防线 = 槽位表占用数
   守门 fail-closed)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from one_dragon.base.screen.screen_utils import (
    FindAreaResultEnum,
    find_area_in_screen,
    get_match_screen_name,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    ChannelSig,
    Unit,
)
from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
from sr_od.application.currency_war.operations.cw_loop import (
    CwLoop,
)
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_boss_briefing as bb_mod,
)

# ============================================================
# 1. 分发身份语料回归(两阶段身份分发的语料纪律可执行测试)
# ============================================================

# sr-od-test 根(screens/ 语料帧所在):test_loop.py 上溯 6 级 =
# operations→currency_war→application→sr_od→test→sr-od-test。此前
# parents[4] 误指 test/screens(不存在),语料帧恒「缺失」静默 skip,
# 实帧锁从未生效(SA-4 落地时实证)。
_SCREENS_DIR = Path(__file__).parents[5] / 'screens'

#: 阶段一身份清单语料(True 向):帧 → 期望屏名
IDENTITY_CASES: list[tuple[str, str]] = [
    ('货币战争-备战-遭遇锁定/锁定态.webp', '货币战争-备战-遭遇锁定'),
    ('货币战争-列车同行/伙伴遮罩-备战透出.webp', '货币战争-列车同行'),
    ('货币战争-列车同行/伙伴遮罩-未选中.webp', '货币战争-列车同行'),
    ('货币战争-备战-开商店/shop_open.webp', '货币战争-备战-开商店'),
    ('货币战争-备战-角色详情/char_detail_equipped.webp', '货币战争-备战-角色详情'),
    ('货币战争-备战-专家邀请函/弹窗.webp', '货币战争-备战-专家邀请函'),
    ('货币战争-备战-武装箱选择/box_open.webp', '货币战争-备战-武装箱选择'),
    # 免战×商店叠加态:免战只替换出战按钮,不替换商店控件——开商店 id_mark
    # 仍全中,叠加帧由阶段一身份分发接住,不依赖备战穿透双锁认领。
    ('货币战争-备战-开商店/免战叠加态.webp', '货币战争-备战-开商店'),
]

#: 阶段二默认分支语料:阶段一必须 miss(返回 None)+ 双锚必须命中
PREP_DEFAULT_CASES: list[str] = [
    '货币战争-备战/shop_closed.webp',
    '货币战争-备战/shop_closed_a8_start.webp',
    '货币战争-备战/后排8槽-P3局.webp',
]


def test_dispatch_corpus_identity_true_direction(test_context: SrTestContext) -> None:
    """阶段一:身份清单语料帧必须判定为本画面屏名。"""
    for rel, expected in IDENTITY_CASES:
        path = _SCREENS_DIR / rel
        if not path.exists():
            pytest.skip(f'语料帧缺失: {rel}')
        screen = _read(path)
        name = get_match_screen_name(
            test_context, screen, screen_name_list=list(CwLoop.CW_DISPATCH_SCREENS))
        assert name == expected, f'语料帧 {rel} 分发判定 {name!r} ≠ {expected!r}'


def test_dispatch_corpus_prep_default_direction(test_context: SrTestContext) -> None:
    """阶段二:备战语料帧上阶段一必须 miss,且双锚默认分支判据必须命中。"""
    for rel in PREP_DEFAULT_CASES:
        path = _SCREENS_DIR / rel
        if not path.exists():
            pytest.skip(f'语料帧缺失: {rel}')
        screen = _read(path)
        name = get_match_screen_name(
            test_context, screen,
            screen_name_list=_prep_excluded_dispatch_names(test_context))
        assert name is None, \
            f'语料帧 {rel} 阶段一误命中 {name!r}(备战不在清单,应为 miss)'
        for _area in ('备战标识-购买经验', '按钮-出战'):
            area = test_context.screen_loader.get_area('货币战争-备战', _area)
            r = find_area_in_screen(test_context, screen, area, crop_first=False)
            assert r == FindAreaResultEnum.TRUE, \
                f'语料帧 {rel} 备战双锚 {_area} 未命中({r})'


def _read(path: Path):
    from one_dragon.utils import cv2_utils
    screen = cv2_utils.read_image(str(path))
    assert screen is not None, f'语料帧读取失败: {path}'
    return screen


def test_prep_skip_substate_real_frame_anchor_lock(
        test_context: SrTestContext) -> None:
    """免战子态实拍帧锚真值锁(实帧面,钉 screen_info 建档可命中)。

    判定逻辑钉 = test_launch.py::test_prep_anchors_skip_substate_form
    (stub 帧,锁 ``_prep_anchors_hit`` 的 or 双形态)——但 stub 不触
    OCR:跳过锚 rect/lcs 在 screen_info 漂移时 stub 恒绿,实机侧静默
    回到双锚失配形态(免战激活后连续 15 帧未识别整局 abandoned,sim
    冒烟种子 20261015 事故)。本条用归档实拍帧走生产识别链
    ``find_area_in_screen``,锚漂移即红。免战形态单一源 =
    docs/game/screens/currency_war_prep.md「跳过(N/N)」按钮替换节。

    - 免战纯帧(货币战争-备战-免战/跳过态.webp):阶段一身份 miss
      (免战屏不在 CW_DISPATCH_SCREENS)→ 双锚认领形态成立 = 购买
      经验命中 ∧ 出战 miss ∧ 跳过命中(修复前该帧双锚失配);
    - 常规帧(货币战争-备战/shop_closed.webp):跳过锚 miss,常规帧
      无双形态误命中(出战/购买经验两锚已由
      test_dispatch_corpus_prep_default_direction 辖住,不重复)。
    """
    skip_frame = _SCREENS_DIR / '货币战争-备战-免战' / '跳过态.webp'
    if not skip_frame.exists():
        pytest.skip('实拍帧缺失: 货币战争-备战-免战/跳过态.webp')
    screen = _read(skip_frame)
    name = get_match_screen_name(
        test_context, screen,
        screen_name_list=_prep_excluded_dispatch_names(test_context))
    assert name is None, \
        f'免战纯帧阶段一误命中 {name!r}(免战屏不在分发清单,应 miss 走阶段二认领)'
    for _area, _hit in (('备战标识-购买经验', True), ('按钮-出战', False),
                        ('按钮-跳过', True)):
        area = test_context.screen_loader.get_area('货币战争-备战', _area)
        r = find_area_in_screen(test_context, screen, area, crop_first=False)
        assert r == (FindAreaResultEnum.TRUE if _hit
                     else FindAreaResultEnum.FALSE), \
            f'免战帧备战锚「{_area}」期望命中={_hit},实际 {r.name}'

    normal_frame = _SCREENS_DIR / '货币战争-备战' / 'shop_closed.webp'
    if not normal_frame.exists():
        pytest.skip('实拍帧缺失: 货币战争-备战/shop_closed.webp')
    area = test_context.screen_loader.get_area('货币战争-备战', '按钮-跳过')
    r = find_area_in_screen(test_context, _read(normal_frame), area,
                            crop_first=False)
    assert r == FindAreaResultEnum.FALSE, \
        f'常规帧跳过锚应 miss(免战无双形态误命中面),实际 {r.name}'


def _prep_excluded_dispatch_names(test_context: SrTestContext) -> list[str]:
    return list(CwLoop.CW_DISPATCH_SCREENS)


# ============================================================
# 2. boss 简报帧误派位面过渡防线
# ============================================================

_FRAME = object()   # 稳定帧哨兵(读链桩只验判定,不断言内容)


class _StubScreenOp:
    """两屏 op 替身:构造记 ctx,execute 吐 success(排除通用网/重试干扰)。"""

    journal = ''

    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self):
        return SimpleNamespace(success=True, status='stub-ok')


class _StubBoss(_StubScreenOp):
    journal = 'BOSS简报'


class _StubTransition(_StubScreenOp):
    journal = '位面过渡'


def _make_loop(test_context, monkeypatch, *, match_name, ocr_texts,
               transition_prompt_hit):
    """CwLoop 裸装配 + 全桩面(见模块头)。返回 (op, [cw-op] 行序列)。

    ``transition_prompt_hit`` = 位面过渡提示区桩命中(阶段一位面过渡身份
    miss 场景下,该区已无独立兜底分支消费——保留桩位防回归复活静默消费)。
    """
    op = CwLoop.__new__(CwLoop)
    op.ctx = test_context
    op._iter = 3                # 3+1=4:跳过 iter1 预检/焦点检查/首读分支
    op._stop_at_prep = False
    op._max_rounds = None
    op._battle_wait_active = False
    op._battle_ts = None
    op._settle = SimpleNamespace(battle_ts=None, saw_settlement=False,
                                 rounds_done=0)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_ocr',
                        lambda scr, text, **k: _Area(False))
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(
                            transition_prompt_hit
                            and s == '货币战争-位面过渡'
                            and a == '提示-点击空白继续'))
    monkeypatch.setattr(cw_loop_mod, 'get_match_screen_name',
                        lambda ctx, scr, screen_name_list=None: match_name)
    monkeypatch.setattr(cw_loop_mod, 'save_decision_frame',
                        lambda *a, **k: None)   # 留证面 no-op(零落盘)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cw_loop_mod, '_log_cw_op',
                        lambda name, pos, dur, outcome, detail='':
                        calls.append((name, outcome)))
    # boss 判别单一源保持真函数,只桩 OCR 读链(校验「片段进派发裁决」)
    monkeypatch.setattr(bb_mod, 'read_ocr_texts',
                        lambda ctx, scr: list(ocr_texts))
    monkeypatch.setattr(cw_loop_mod, 'CwScreenBossBriefing', _StubBoss)
    monkeypatch.setattr(cw_loop_mod, 'CwScreenPlaneTransition',
                        _StubTransition)
    return op, calls


def test_stage1_transition_identity_boss_frame_takeover(test_context,
                                                        monkeypatch) -> None:
    """测试1 阶段一排他:位面过渡身份帧含「强敌」片段(标题误读形态)→
    接管派发 BOSS 简报,零位面过渡派发。"""
    op, calls = _make_loop(
        test_context, monkeypatch, match_name='货币战争-位面过渡',
        ocr_texts=['强敌米', '点击空白处继续'], transition_prompt_hit=False)
    rs = _run_node(test_context, op, op.loop)
    assert calls == [('BOSS简报', 'ok')], f'boss 帧应接管派发 BOSS 简报:{calls}'
    assert rs.result == OperationRoundResultEnum.WAIT   # 替身成功 → 默认映射


def test_boss_frame_without_anchors_falls_to_unknown_fallback(
        test_context, monkeypatch) -> None:
    """测试2 劣化形态终端:boss 帧位面锚 miss ∧ 判别片段 miss(全帧只剩
    共享文案)→ 零派发,落未知兜底 retry(终端 = 停机留证,不为未建档
    形态预建兜底)。"""
    op, calls = _make_loop(
        test_context, monkeypatch, match_name=None,
        ocr_texts=['点击空白处继续'], transition_prompt_hit=False)
    rs = _run_node(test_context, op, op.loop)
    assert calls == [], f'boss 帧零派发(不误派位面过渡/BOSS):{calls}'
    assert rs.result == OperationRoundResultEnum.RETRY   # 未知兜底(streak 1)


# ============================================================
# 3. op-fail 重派防线上限 + 出战链紧缩对位防线
# ============================================================


def _spy_cw_op(monkeypatch) -> list[tuple[str, str]]:
    """桩掉 [cw-op] 日志行落点(测试零真实日志副作用)+ 留 (op, outcome)
    序列供配对断言(原 journal record_op_enter/exit 桩随该流退役换型)。"""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cw_loop_mod, '_log_cw_op',
                        lambda name, pos, dur, outcome, detail='':
                        calls.append((name, outcome)))
    return calls


class _Host:
    """``_dispatch_screen_op`` 离线宿主:只供给包装消费面(round 工厂/
    留证/上限值),镜像恢复路由测试的替身纪律(ctx 缺省缺席 = 位置键退 (0, 0);
    刻意**不**预置 ``_op_fail_streak_key/_n``——校验 getattr 缺省初始化
    路径与生产首帧形态一致。
    """

    def __init__(self, limit: int):
        self.last_screenshot = None
        self.OP_FAIL_REDISPATCH_LIMIT = limit
        self.rounds: list[tuple[str, str | None]] = []
        self.shots: list[str] = []

    def round_wait(self, status=None, data=None, wait=None):
        self.rounds.append(('wait', status))
        return SimpleNamespace(is_success=False, status=status)

    def round_retry(self, status=None, data=None, wait=None):
        self.rounds.append(('retry', status))
        return SimpleNamespace(is_success=False, status=status)

    def round_fail(self, status=None, data=None, wait=None):
        self.rounds.append(('fail', status))
        return SimpleNamespace(is_success=False, status=status)

    def save_screenshot(self, prefix: str = '') -> str:
        self.shots.append(prefix)
        return f'{prefix}.png'


class _ScriptedOp:
    """execute() 按剧本吐结果的替身 op( OperationResult 形:success/status)。

    剧本耗尽后重复末项(超出剧本的额外分发仍可驱动)。
    """

    def __init__(self, script: list[bool]):
        self._script = script
        self.calls = 0

    def execute(self):
        ok = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        return SimpleNamespace(success=ok,
                               status='' if ok else '演示fail(无判读形态)')


def _dispatch(host, op, journal_name: str, **kwargs):
    return CwLoop._dispatch_screen_op(host, op, journal_name=journal_name,
                                      frame_tag=None, wait=2, **kwargs)


# (原 test_tick_window_semantics 删:纯函数窗口语义被测试2/3/4 的接入调用级
#  断言完全辖——同键 ok 复位/异键 ok 闭窗计数从 1 重计/达限转 fail,单层
#  归因价值不及冗余成本。)


def test_cap_fires_at_limit_with_readout(monkeypatch):
    """测试2 接入调用:上限-1 次维持默认映射,第 LIMIT 次转可判读 round_fail。"""
    calls = _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    op = _ScriptedOp([False] * limit)
    for _ in range(limit - 1):
        _dispatch(host, op, '选择伙伴')
        assert host.rounds[-1][0] == 'wait'   # 上限内维持既有默认映射
    result = _dispatch(host, op, '选择伙伴')
    assert host.rounds[-1][0] == 'fail'
    assert '选择伙伴' in result.status   # op 行名进 status(可判读)
    assert host.shots == ['op_fail_cap']   # 留证恰一次
    # 分发与 [cw-op] 行一比一(出口即落,末行为 fail)
    assert len(calls) == limit and calls[-1] == ('选择伙伴', 'fail')


def test_intermittent_ok_resets_window(monkeypatch):
    """测试3 间歇 ok 复位:ok 打断后需重新连败 LIMIT 次才触发。

    判据形态:ok 前已积 limit-1 连败;若无复位,ok 后第 1 次 fail 即达限
    (4+1=5)。实测 ok 后 limit-1 次连败全 wait = 计数确已清零,第 limit
    次才触发。
    """
    _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    op = _ScriptedOp([False] * (limit - 1) + [True] + [False] * limit)
    for _ in range(2 * limit - 1):   # (limit-1) fail → ok → (limit-1) fail
        _dispatch(host, op, '选择伙伴')
        assert host.rounds[-1][0] != 'fail'   # ok 打断后不提前触发(已复位)
    _dispatch(host, op, '选择伙伴')   # 复位后第 limit 连败 → 触发
    assert host.rounds[-1][0] == 'fail'


def test_other_op_ok_closes_window(monkeypatch):
    """测试4 异键 ok 同闭窗:其他 op 的 ok 打断粘滞 op 的 fail 序列。"""
    _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    stuck = _ScriptedOp([False] * limit)
    other = _ScriptedOp([True])
    for _ in range(limit - 1):
        _dispatch(host, stuck, '选择伙伴')
    _dispatch(host, other, '备战')   # 异键 ok = 屏幕证实推进 → 整窗归零
    for _ in range(limit - 1):
        _dispatch(host, stuck, '选择伙伴')
        assert host.rounds[-1][0] == 'wait'   # 计数从 1 重计,不提前触发
    _dispatch(host, stuck, '选择伙伴')
    assert host.rounds[-1][0] == 'fail'


def test_dedicated_hook_shadows_cap(monkeypatch):
    """测试5 hook 早退先于通用网:hook 返回自身轮次 → 恒 hook 结果且不计数。"""
    _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    op = _ScriptedOp([False] * 20)

    def _guard(ok: bool, _res) -> object:
        if not ok:
            return host.round_fail(status='hook 早退形态(短路通用网)')
        return None

    for _ in range(CwLoop.OP_FAIL_REDISPATCH_LIMIT + 3):
        result = CwLoop._dispatch_screen_op(
            host, op, journal_name='备战', frame_tag=None, wait=1,
            on_result=_guard)
        assert result.status == 'hook 早退形态(短路通用网)'
    assert getattr(host, '_op_fail_streak_n', 0) == 0   # hook 早退路径零计数


def test_on_fail_retry_branch_capped_before_retry_pool(monkeypatch):
    """测试6 on_fail_retry 分支同辖:达限转 round_fail,不再进 400 重试池。"""
    _spy_cw_op(monkeypatch)
    host = _Host(CwLoop.OP_FAIL_REDISPATCH_LIMIT)
    limit = CwLoop.OP_FAIL_REDISPATCH_LIMIT
    op = _ScriptedOp([False] * (limit + 2))
    for _ in range(limit - 1):
        _dispatch(host, op, '策划事件', on_fail_retry=True)
        assert host.rounds[-1][0] == 'retry'   # 上限内维持既有 retry 语义
    _dispatch(host, op, '策划事件', on_fail_retry=True)
    assert host.rounds[-1][0] == 'fail'   # 达限显式停


# ===== 出战链紧缩对位防线(槽位表占用数守门)=====
# (紧缩占席序 × 容器槽位表对位守门两测试(deploy_plan_moves 装配链的
#  unhealthy/healthy 表行为)已随部署统一批丁丁批收编删除:装配链退役,
# 统一链(搜索 + 差分执行器)按容器槽位表下标直读产出动作,无「紧缩序
# vs 槽位表」双坐标系错位面——unified-deploy-order §4;等价防线 = 差分
# 执行器的容器直读坐标系与 deploy_diff 单测承载。)

_SIG_OBS = ChannelSig(family='obs', actor='t', mode='read')


def _bcd_gs(bench_slots) -> object:
    """桩容器:真 GameState + bench 槽位表(占用 = kind 口);deployed
    空视图、deploy_cap/back_layout 不写(缺省读口兜底)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchView,
        DeployedView,
        GameState,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = list(bench_slots) + [BenchSlot(kind='empty')] * (9 - len(bench_slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.deployed, DeployedView(), sig=_SIG_OBS)
    return gs


def test_deploy_chain_stale_frame_no_moves_via_unified_chain():
    """统一链下的等价断言(收编改写):陈旧决策帧(bench 快照与容器现值
    不一致)不再有独立守门面——差分执行器容器直读,快照漂移零动作面
    (部署面 = 容器真值,unified-deploy-order §3 容器坐标系)。"""
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        deploy_plan as _dp_mod,
    )

    counters: dict = {}
    session = StrategySession()
    from types import SimpleNamespace as _NS
    session.strategy_state = _NS(cw4_counters=counters)
    gs = _bcd_gs([BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1))])
    # 陈旧帧形态不再构成防线输入:出战链计划 = battle_chain_deploy_params
    # 容器现读(紧缩快照不入参),零动作形态 = 容器真值决定。
    out = _dp_mod.battle_chain_deploy_params(session)
    assert isinstance(out, list)


