# -*- coding: utf-8 -*-
"""W596(W593 方案①②③):装备执行面三防御——构建指纹/零穿戴哨兵/分配空归因。

三件全是**观测/记账/守卫告警**(零行为变更红线):
1. build_info.get_build_fingerprint:git 短 hash+脏标记,缓存;git 缺失降级 unknown;
2. EquipAll._zero_wear_sentinel:round≥3 ∧ 有可穿件 ∧ 穿 0 件 → record_defect
   (`equip_zero_wear`);三态(0穿有货/0穿无货/有穿)与 round<3 门;
3. equip_alloc_empty_reason:分配空三因结构化(pool_empty/capacity_full/
   pairing_guard/no_deployed/unknown),与 equip_allocation 同输入同结论。

病灶出处:局22(r3~r9 连续零穿戴,归因耗三段证据合围,见
`.debug/temp/currency_war/w593_equip_wear/DESIGN.md` §2)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_comps import (
    Comp,
    equip_alloc_empty_reason,
    equip_allocation,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.data.cw_synthesis import synthesize_target
from sr_od.application.currency_war.operations.prep.equip_all import EquipAll
from sr_od.application.currency_war.telemetry import state as cw_telemetry


# ===== 件1:构建指纹 =====

def test_build_fingerprint_format_and_cache() -> None:
    """指纹 = 非空短串;进程内缓存(两次调用同值,git 不重复跑)。"""
    from sr_od.backend.build_info import get_build_fingerprint
    fp1 = get_build_fingerprint()
    fp2 = get_build_fingerprint()
    assert fp1 == fp2 and fp1, '指纹非空且进程内缓存稳定'


def test_build_fingerprint_git_repo_matches_head() -> None:
    """git 可用时:指纹 ∈ {HEAD 短 hash, HEAD 短 hash+'+dirty'},与 git 直查一致。"""
    import subprocess
    from sr_od.backend.build_info import _PROJECT_ROOT, get_build_fingerprint
    try:
        proc = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=_PROJECT_ROOT, capture_output=True, text=True, timeout=5)
        head = proc.stdout.strip()
    except Exception:   # noqa: BLE001  git 缺失环境跳过对拍
        pytest.skip('git 不可用')
    if proc.returncode != 0 or not head:
        pytest.skip('非 git 仓库')
    fp = get_build_fingerprint()
    assert fp in (head, head + '+dirty'), f'指纹与 git HEAD 不一致: {fp} vs {head}'


# ===== 件2:零穿戴哨兵 =====

def _mk_op(state: SimpleNamespace | None) -> EquipAll:
    """最小 EquipAll(只调 _zero_wear_sentinel,不碰截图/控制器)。"""
    match = None if state is None else SimpleNamespace(session=SimpleNamespace(last_state=state))
    return EquipAll(SimpleNamespace(cw_match=match))


@pytest.fixture()
def _captured_defect(monkeypatch):
    """桩化 cw_telemetry.record_defect 捕获调用(零真实副作用,不写台账)。"""
    calls: list[dict] = []
    monkeypatch.setattr(defects, 'record_defect',
                        lambda *a, **k: calls.append({'args': a, 'kwargs': k}))
    return calls


_STATE_R5 = SimpleNamespace(round_num=5, plane=1)
_OWNED_WEARABLE = ['生命之花', '量产型装甲', '冶金炉']   # 末件=工具类,不应计入可穿面


def test_zero_wear_sentinel_fires(_captured_defect) -> None:
    """态①:0 穿 + 有可穿件 + round≥3 → 落账 equip_zero_wear(带 owned 与停手原因)。"""
    _mk_op(_STATE_R5)._zero_wear_sentinel(0, _OWNED_WEARABLE, '分配方案空:pairing_guard')
    assert len(_captured_defect) == 1
    call = _captured_defect[0]
    kw = call['kwargs']
    assert kw['surface'] == 'equip' and kw['kind'] == 'equip_zero_wear'
    assert kw['round_num'] == 5 and kw['plane'] == 1
    observed = kw['observed']
    assert '生命之花' in observed and '量产型装甲' in observed, 'observed 带 owned 名单'
    assert '冶金炉' not in observed, '工具类不得计入可穿面(与穿戴决策同过滤口径)'
    assert 'pairing_guard' in observed, 'observed 带 stop 原因'


def test_zero_wear_sentinel_silent_when_wore(_captured_defect) -> None:
    """态②:穿了 ≥1 件 → 静默(哨兵只报零穿戴)。"""
    _mk_op(_STATE_R5)._zero_wear_sentinel(2, _OWNED_WEARABLE, '')
    assert _captured_defect == []


def test_zero_wear_sentinel_silent_when_no_wearable(_captured_defect) -> None:
    """态③:0 穿但 owned 全工具类/空 → 静默(无货可穿不是缺陷)。"""
    _mk_op(_STATE_R5)._zero_wear_sentinel(0, ['冶金炉'], 'pool_empty')
    _mk_op(_STATE_R5)._zero_wear_sentinel(0, [], '')
    assert _captured_defect == []


def test_zero_wear_sentinel_silent_before_round3(_captured_defect) -> None:
    """round<3 → 静默:r1~r2 开局 hold(ADR-0257)零穿戴是 by design。"""
    _mk_op(SimpleNamespace(round_num=2, plane=1))._zero_wear_sentinel(
        0, _OWNED_WEARABLE, '过渡期hold')
    assert _captured_defect == []


def test_zero_wear_sentinel_silent_without_state(_captured_defect) -> None:
    """无 run 上下文(last_state 缺失)→ 静默跳过,不炸不误报。"""
    _mk_op(None)._zero_wear_sentinel(0, _OWNED_WEARABLE, '')
    assert _captured_defect == []


# ===== 件3:分配空归因 =====

def _mkcomp(key_equips: list[str], cores: list[str]) -> Comp:
    return Comp(name='伪comp', factions=['追击'], core_chars=cores,
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=key_equips)


def test_reason_pool_empty() -> None:
    assert equip_alloc_empty_reason(None, [], []) == 'pool_empty'


def test_reason_no_deployed() -> None:
    assert equip_alloc_empty_reason(None, [], ['生命之花']) == 'no_deployed'


def test_reason_capacity_full() -> None:
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    occ = {('front', 1): ['生命之花', '量产型装甲', '幸运星']}   # 容量 3 占满
    assert equip_alloc_empty_reason(None, dep, ['以太钻头'], occ) == 'capacity_full'


def test_reason_pairing_guard_matches_allocation() -> None:
    """守卫拦截归因:core 已穿 生命之花,池里只有 光能电池(会合出
    「绝对热量」∉ key)→ 分配空 且 归因=pairing_guard。两函数同输入同结论。"""
    assert synthesize_target('光能电池', '生命之花') == '绝对热量', '图谱前提'
    comp = _mkcomp(['火力风暴潮'], ['飞霄'])
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    occ = {('front', 1): ['生命之花']}
    assert equip_allocation(comp, dep, ['光能电池'], occ) == []
    assert equip_alloc_empty_reason(comp, dep, ['光能电池'], occ) == 'pairing_guard'


def test_reason_unknown_flags_divergence() -> None:
    """存在可行组合却询问归因 → unknown(哨兵值:分配器与诊断漂移时优先暴露)。"""
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    assert equip_alloc_empty_reason(None, dep, ['生命之花'], None) == 'unknown'


def test_blocked_items_not_discarded_for_later_chars() -> None:
    """配对守卫拦下的件必须**留在池里**轮给后面的人,不得 pop 丢弃。

    出处:equip_allocation docstring ADR-0391 节「发不完留在 owned 囤着」
    与分配体内「跳过=留 owned」注释;实机反例见复盘
    `.debug/temp/currency_war/replay/matches/reviews/g_20260831_032006.md`
    r7 形态(列车配方伪 comp,三月七穿以太钻头,池里 4 件全是与其互为
    配方的基础件 → 旧实现整池被 core 循环吃光,alloc=[] 而诊断判
    「存在可行组合」= unknown 漂移)。锁语义:
    1. 同帧下无残留件的角色(饮月)能分到件(非空分配);
    2. 被拦的 core(三月七)一件不取,被拦件不消失(留给他人/owned);
    3. 分配空 ⇔ 归因非 unknown(两函数同输入同结论的契约恢复)。
    """
    assert synthesize_target('以太钻头', '折叠小刀') is not None, '图谱前提:池件与已穿件互为配方'
    comp = _mkcomp([], ['三月七', '丹恒·饮月'])
    dep = [BenchChar(slot=1, char_id='丹恒·饮月', position_pref='front'),
           BenchChar(slot=2, char_id='三月七', position_pref='back')]
    pool = ['折叠小刀', '轮滑鞋']
    occ = {('back', 2): ['以太钻头']}
    alloc = equip_allocation(comp, dep, list(pool), dict(occ))
    assert alloc, '被拦 core 不得吃光整池:无残留件的角色应分到件'
    got_chars = {c for c, _ in alloc}
    assert '三月七' not in got_chars, '整池互为配方时被拦 core 一件不取(留 owned)'
    assert all(e == '折叠小刀' or e == '轮滑鞋' for _, e in alloc)
    # 单人整池被拦的形态:分配空,且归因必须是 pairing_guard(不再 unknown)
    dep_only = [BenchChar(slot=1, char_id='丹恒·饮月', position_pref='front'),
                BenchChar(slot=2, char_id='三月七', position_pref='back')]
    occ_all_blocked = {('front', 1): ['以太钻头'], ('back', 2): ['以太钻头']}
    assert equip_allocation(comp, dep_only, ['折叠小刀'], dict(occ_all_blocked)) == []
    assert equip_alloc_empty_reason(comp, dep_only, ['折叠小刀'],
                                    dict(occ_all_blocked)) == 'pairing_guard'


from sr_od.application.currency_war.telemetry import state

from sr_od.application.currency_war.telemetry import defects
