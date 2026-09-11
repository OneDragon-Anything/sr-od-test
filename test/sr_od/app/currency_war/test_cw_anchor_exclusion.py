"""P4R3 锚误读 / 两画面排他 / 误分发上限 单测(第五局 1-9 实锤返工)。

实锤链:全帧 OCR 把「强敌来袭」读成「强敌米」→ CwScreenBossBriefing 0p 锚
(标识-强敌来袭,area LCS)miss → boss 简报帧含共享文案「点击空白处继续」
→ 0q 位面过渡误分发 → 「提示未出现」fail 每 2s 无限循环。
"""
from __future__ import annotations

from types import SimpleNamespace

# ==================== 判别单一源(纯函数) ====================

def test_boss_briefing_texts_misread_forms() -> None:
    """「强敌」片段判别:误读「强敌米」/正常「强敌来袭」全命中;
    位面过渡帧(仅共享文案+boss 名)不误判。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_boss_briefing import (
        is_boss_briefing_texts,
    )
    assert is_boss_briefing_texts(['强敌米', '点击空白处继续', '云骑骁卫·彦卿'])
    # 繁首形态(第七局实锤):OCR 把「强」读成繁体「強」→ 简体单一 token 漏判
    assert is_boss_briefing_texts(['強敌来袭', '点击空白处继续'])
    assert is_boss_briefing_texts(['强敌来袭', '点击空白处继续'])
    # 负样本:位面过渡/备战帧无「强敌」
    assert not is_boss_briefing_texts(['点击空白处继续', '位面过渡'])
    assert not is_boss_briefing_texts(['备战阶段', '购买经验', '出战'])
    assert not is_boss_briefing_texts([])


# ==================== ①「强敌米」误读帧 → 0p 仍接管 ====================

def test_boss_briefing_takeover_on_misread(monkeypatch) -> None:
    """area 锚(误读)miss + OCR 片段判别命中 → handle 走点空白路径
    (0p 接管,不再漏给 0q)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_boss_briefing as bb,
    )

    class _FakeArea:
        def __init__(self, ok: bool): self.is_success = ok

    clicks: list[str] = []

    class _Op(bb.CwScreenBossBriefing):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._first_seen_ts = None
            self.last_screenshot = object()
            self.ctx = SimpleNamespace(
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None,
                    color_range=None, crop_first=False: [
                        SimpleNamespace(data=t) for t in
                        ['强敌米', '点击空白处继续', '云骑骁卫·彦卿']]),
                controller=SimpleNamespace(
                    mouse_move=lambda p: None,
                    click=lambda p: clicks.append('blank')),
            )

        def round_by_find_area(self, scr, screen, area, **k):
            return _FakeArea(False)   # area 锚全 miss(误读形态/DONE 未现)

        def round_wait(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait)

        def round_success(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, success=True)

        def round_fail(self, status=''):
            return SimpleNamespace(status=status, success=False)

        def save_screenshot(self, prefix=None):
            return ''

    monkeypatch.setattr(bb, 'area_center',
                        lambda ctx, name, screen=None: SimpleNamespace(x=960, y=540))
    monkeypatch.setattr(bb.time, 'sleep', lambda s: None)
    op = _Op()
    res = op.handle()
    # 误读帧仍走「横幅命中 → 点空白」路径(接管成功)
    assert clicks == ['blank']
    assert '点空白已发' in str(getattr(res, 'status', ''))


# ==================== ③ 误分发上限 ====================

def test_plane_misdispatch_limit() -> None:
    """0q 误分发型 fail 连续达上限 → round_fail 交兜底链(不再 2s 无限循环);
    上限常量 = 3;0p 接管/过渡成功路径清零计数。"""
    import inspect

    from sr_od.application.currency_war.operations import cw_loop
    assert cw_loop.CwLoop.PLANE_MISDISPATCH_LIMIT == 3
    src = inspect.getsource(cw_loop.CwLoop.loop)
    assert "round_fail('位面过渡连续 fail 超上限(交兜底链)')" in src
    # 清零挂点:boss 简报接管(0p)与过渡成功两条恢复路径
    assert src.count('self._plane_mis_streak = 0') >= 2
    # CwScreenBattleWait 白名单同源消费面锁已并入超集锁
    # test_cw_obs_arch_phase_screens.test_boss_discrimination_single_source_
    # consumers_unchanged(消费点集 + 零复制两源 + 定义在 boss_briefing,
    # 纪律 7 重复断言择一取超集),本文件不再重复断言。
