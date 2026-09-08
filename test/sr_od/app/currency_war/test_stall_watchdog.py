"""r119 停滞 watchdog 测试:参数在位/宽限语义/退避曲线/豁免固定短语。

2026-09-03 瘦身批删两条:fingerprint hash 自检(纯 Python 语义,不触生产)、
exempt_keywords 自抄互查(测试体自列集合再自查,删生产函数仍绿——纪律 10)。
T-163 批回填豁免判据锁:旧裸子串豁免被弹窗正文撞车致盲(26min 无报警实证),
固定短语判据 + 弹窗样本触发报警见「哨兵去盲」节。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.operations.cw_loop import CwLoop


def test_stall_thresholds_defined():
    """参数在位:5 iter 采样/6 次触发(≈1-2min 检出,vs 局29/32 的 30-41min)。"""
    assert CwLoop.STALL_SNAPSHOT_EVERY == 5
    assert CwLoop.STALL_N == 6


# ===== ADR-0250:战斗窗口宽限(局54 哨兵误报复盘) =====

def test_battle_grace_constant_covers_observed_battles():
    """宽限常量 > 实测最长战斗(局54:P1r9 boss 4min20s / P2r1 遭遇 5min20s),
    且有界(超时恢复哨兵,出战卡死类真挂死仍可检出)。"""
    assert CwLoop.BATTLE_WATCH_GRACE_S >= 8 * 60   # > 8min(> 实测 5.5min 留余量)
    assert CwLoop.BATTLE_WATCH_GRACE_S <= 15 * 60  # 有界,防真挂死漏报窗口过长


def test_battle_grace_semantics():
    """窗口语义:None 恒不宽限;窗口内 True;恰好超时 False。"""
    grace = CwLoop.BATTLE_WATCH_GRACE_S
    assert CwLoop._watch_in_battle_grace(None, 1000.0) is False
    assert CwLoop._watch_in_battle_grace(1000.0, 1000.0 + grace - 1) is True
    assert CwLoop._watch_in_battle_grace(1000.0, 1000.0 + grace) is False


def test_battle_window_observed_vs_watch_threshold():
    """误报根因锁定:局54 战斗时长(5min20s)远超 watch 触发窗(6 次×5 iter×~5s ≈ 2.5min)
    ——即关键词豁免缺失时战斗必误报;该实证是宽限机制的存在理由(ADR-0250)。"""
    observed_battle_s = 5 * 60 + 20          # 局54 P2r1 遭遇战实测(18:38:20 出战 → 18:43:40 结算)
    watch_window_s = CwLoop.STALL_N * CwLoop.STALL_SNAPSHOT_EVERY * 5
    assert observed_battle_s > watch_window_s, '战斗时长必须超 watch 窗(否则宽限无必要)'


# ===== T-163 哨兵去盲:豁免固定短语(裸子串致盲回归锁) =====

#: T-163 失败帧(20260908_181116_921_overlay_role_detail.png)实测 OCR 全文:
#: 弹窗天赋行含「战斗」→ 旧裸子串豁免恒中 → 停滞计数恒清零(26min 致盲源)。
_POPUP_FRAME_TEXTS = frozenset({
    '千冶•刃', '后台', '输出', '星核猎手', '燃血', '减益', '生命值',
    '充能', '716716/716716', '0/9', '100', '125', '0%', '5%', '100%',
    '10%', '万般消磨，吾身为刃', '战技', '终结技天赋',
    '进入战斗前为自己打造装备。',
    '消耗生命值攻击敌人，施放终结技回复生',
    '命。展开结界削弱敌方并增益我方，全队攻',
    '角色详情', '购买', '2',
})


def test_stall_exempt_popup_frame_texts_not_exempt():
    """T-163 弹窗全文集必不豁免——天赋行「进入战斗前为自己打造装备。」
    含「战斗」,词缀式正文含「倒计时/战斗」同理;裸子串回归即红。"""
    assert CwLoop._stall_exempt(_POPUP_FRAME_TEXTS) is False
    assert CwLoop._stall_exempt(frozenset(
        {'战个痛快', '战斗节点的倒计时减少30，但首领节点的倒计时增加20。'},
    )) is False


def test_stall_exempt_settlement_phrases_still_exempt():
    """ADR-0250 合法静止语义不回归:结算族三屏(胜利/轮败/团灭)实帧
    OCR 固定短语仍豁免(短语集标定源 = 归档 fixture 实测)。"""
    assert CwLoop._stall_exempt(
        frozenset({'挑战成功', '继续挑战', '数据统计'})) is True
    assert CwLoop._stall_exempt(
        frozenset({'挑战结束', '挑战进度', '前往结算', '2-1X战斗'})) is True
    assert CwLoop._stall_exempt(
        frozenset({'挑战失败', '下一步', '小队生命值'})) is True


def test_stall_exempt_table_bans_t163_blind_words():
    """表形态锁:致盲词族(战斗/胜利/挑战/结算/准备/倒计时)禁以裸词形态
    回填短语表——任一裸词入表 = 裸子串致盲面回归。"""
    for bare in ('战斗', '胜利', '挑战', '结算', '准备', '倒计时'):
        assert bare not in CwLoop.STALL_EXEMPT_PHRASES, bare


def _make_watch_loop(monkeypatch, tmp_path, texts: frozenset[str]):
    """裸 CwLoop 实例 + OCR 替身(全帧 OCR 恒返 texts;绕过 run 级装配)。"""
    from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod

    class _Mrl:
        max = object()   # 非 None = 该文本命中(与生产读面同形)

    class _OcrService:
        def __init__(self, words: frozenset[str]) -> None:
            self._words = words

        def get_ocr_result_map(self, image=None, rect=None, color_range=None,
                               crop_first: bool = False) -> dict:
            return {w: _Mrl() for w in self._words}

    op = cw_loop_mod.CwLoop.__new__(cw_loop_mod.CwLoop)
    op.ctx = SimpleNamespace(ocr_service=_OcrService(texts))
    op._iter = 0
    op._stall_last_fp = None
    op._stall_count = 0
    op._stall_flag_written = False
    op._battle_ts = None
    # flag 落点重定向 tmp_path(get_project_root 在 cw_loop 模块命名空间;
    # 测试零真实副作用纪律——真路径落 flag 会误报实机停线)
    monkeypatch.setattr(cw_loop_mod, 'get_project_root', lambda: tmp_path)
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: '<shot>')
    return op


def _feed_watch_ticks(op, rounds: int) -> None:
    """按采样节奏喂轮(iter 每次 +STALL_SNAPSHOT_EVERY,模拟同屏静止)。"""
    for _ in range(rounds):
        op._iter += CwLoop.STALL_SNAPSHOT_EVERY
        op._stall_watch_tick(object())


def test_stall_watch_popup_frame_triggers_alarm(tmp_path, monkeypatch):
    """集成锁(T-163 验收④):弹窗文本帧重复采样必触发哨兵报警
    (stall_watch.flag 落盘 + 计数达阈值)——致盲回归 = 本测红。"""
    op = _make_watch_loop(monkeypatch, tmp_path, _POPUP_FRAME_TEXTS)
    # 首采样 = 基线(count=0),此后每次同指纹 +1 → N 次重复需 N+1 个采样
    _feed_watch_ticks(op, CwLoop.STALL_N + 1)
    assert op._stall_count >= CwLoop.STALL_N
    flag = (tmp_path / '.debug' / 'temp' / 'currency_war'
            / 'stall_watch.flag')
    assert flag.exists(), '弹窗文本帧停滞必须触发哨兵报警(flag 未落盘 = 致盲回归)'


def test_stall_watch_settlement_frame_never_flags(tmp_path, monkeypatch):
    """对照臂:结算胜利帧文本同形态喂 3 倍采样轮,零计数零报警
    (豁免语义未被去盲收窄误伤)。"""
    op = _make_watch_loop(
        monkeypatch, tmp_path,
        frozenset({'挑战成功', '继续挑战', '数据统计'}))
    _feed_watch_ticks(op, CwLoop.STALL_N * 3)
    assert op._stall_count == 0
    assert not (tmp_path / '.debug' / 'temp' / 'currency_war'
                / 'stall_watch.flag').exists()


# ===== 未知帧重试退避(保留层缺陷批:重试无退避修复) =====

def test_unknown_backoff_wait_escalates_and_caps():
    """退避曲线:首连 2s,每连续一次翻倍,封顶 UNKNOWN_RETRY_BACKOFF_CAP_S;
    非零递增(禁恒定间隔立即重试打墙)。"""
    waits = [CwLoop._unknown_backoff_wait(s) for s in range(1, 8)]
    assert waits[0] == 2.0
    assert waits[1] == 4.0
    assert waits[2] == 8.0
    assert all(w == CwLoop.UNKNOWN_RETRY_BACKOFF_CAP_S for w in waits[3:])
    assert all(b > a for a, b in zip(waits[:4], waits[1:4])), '封顶前必须严格递增'


def test_unknown_backoff_reset_and_floor():
    """复位语义:streak 归 1(画面被分支接走后)回到 2s 起步;
    streak<1 的异常入参按 1 兜底(不得抛错/返零)。"""
    assert CwLoop._unknown_backoff_wait(1) == 2.0
    assert CwLoop._unknown_backoff_wait(0) == 2.0
    assert CwLoop._unknown_backoff_wait(-3) == 2.0


def test_unknown_fallback_wiring_uses_backoff():
    """接线锁:_handle_unknown_fallback 的 round_retry 消费退避函数,
    防回退成恒定 wait(旧缺陷形态)。"""
    import inspect
    src = inspect.getsource(CwLoop._handle_unknown_fallback)
    assert '_unknown_backoff_wait(' in src
    assert 'round_retry(wait=2)' not in src, '退回恒定 2s 重试 = 退避被移除'
