"""sim 大扩招扣金负效果条目测试(镜像 src = sim/cw_sim_backend.py 的选卡落地拍
扣金币效果条目 + 呈现一次性标志位;先例 = 本目录 test_strategy_hyperemit_sim_chain.py
〔超发货币负债效果条目,负金币效果条目最同构先例〕同形态)。

测试面依据 = 设计稿(原件已退役) 设计稿(原件已退役) §3 锁 3 + 锁 6(sim 侧对拍) + 已退役评审稿 八裁决点默认案:
- 扣金币效果条目(锁 3):真拿卡路径落地 → 持金 30 扣 28(gold=30→2)∧
  evidence 笔字面量钉死 strategy:recruit_drain:大扩招(sim 写统一
  前缀 + 写点 tag)∧ 扣金额与 dakuozhao_deduction_plan 对拍(锁 6
  sim 侧,与获得链随机角色效果条目发放只数同函数单一源);
- 零金兜底(锁 3 伴随):持金 0 拿卡 → (0, 0) 零写零笔(金证据笔
  保持种子笔);
- 呈现一次性标志位防重放(锁 3 伴随):同声明复喂 → 零动作零噪声(扣金非幂等,
  重放多扣一笔,一次性标志位使重放零写)。

复用声明:引擎驱动助手 import 自本目录 test_strategy_hyperemit_sim_chain.py
(拆分镜像文件,只 import 复用不改)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_strategy_hyperemit_sim_chain import (
    _backend,
    _drive_to_offer,
    _pick,
    _pick_raw,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG_OBS,
    _force_settle,
)

from sr_od.application.currency_war.kernel.cw_investments import (
    dakuozhao_deduction_plan,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    uninstall_backend,
)

_CARD = '大扩招'

#: 扣金笔 evidence(sim 写统一前缀 + 写点 tag,设计稿字面量钉死)。
_DRAIN_EV = 'sim:engine:strategy:recruit_drain:大扩招'


def test_drain_leg_gold_30_deducts_28(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """扣金币效果条目引擎链(锁 3 主形态):真拿卡路径落地 → 持金 30 扣 28
    (gold=2)∧ evidence 笔字面量钉死 ∧ 扣金额与公式对拍(锁 6 sim 侧:
    deduct == dakuozhao_deduction_plan(30)[0],与随机角色效果条目同函数单一源)。
    全胜骨架沿超发货币锁先形(_force_settle patch 面 = backend 模块
    命名空间)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        # 持金定标 30(观察覆盖写,锁面自造输入;先例 = 零金兜底 observe 形)
        gs.observe(gs.gold, 30, evidence='t:gold30', sig=_SIG_OBS)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        deduct, cnt = dakuozhao_deduction_plan(30)
        assert (deduct, cnt) == (28, 7), '公式对拍前提'
        assert int(gs.gold.value or 0) == 30 - deduct, \
            f'持金 30 扣 {deduct}: {gs.gold.value}'
        assert gs.gold.evidence == _DRAIN_EV, \
            f'扣金笔 evidence 字面量钉死: {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_zero_gold_no_write_no_entry(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """零金兜底(锁 3 伴随):持金 0 拿卡 → 公式 (0, 0) → 零写零笔
    (金证据笔保持种子笔,n=0 短路)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gs.observe(gs.gold, 0, evidence='t:gold0', sig=_SIG_OBS)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        assert dakuozhao_deduction_plan(0) == (0, 0), '公式对拍前提'
        assert int(gs.gold.value or 0) == 0
        assert gs.gold.evidence == 't:gold0', \
            f'零写零笔(证据笔保持种子笔): {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_replay_same_declaration_zero_write(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """呈现一次性标志位防重放(锁 3 伴随;先例 = 超发货币重放同形):同 offer 落地
    声明复喂 → 第二次零动作(金证据笔保持首笔、金值不再变——扣金非幂等,
    一次性标志位使重放零写零噪声)。"""
    _force_settle(monkeypatch, won=True)
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gs.observe(gs.gold, 30, evidence='t:gold30', sig=_SIG_OBS)
        out = _pick_raw(b, _CARD, [_CARD, '躺平', '淘金客'])
        cw_sim_ports.declare_world(out)
        assert gs.gold.evidence == _DRAIN_EV, '首次落地扣金笔在场'
        snap = (int(gs.gold.value or 0), gs.gold.evidence)
        cw_sim_ports.declare_world(out)
        assert (int(gs.gold.value or 0), gs.gold.evidence) == snap, \
            '重放零写(金值与证据笔保持首笔)'
    finally:
        uninstall_backend()
