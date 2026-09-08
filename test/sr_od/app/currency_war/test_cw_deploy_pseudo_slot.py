"""占槽物品排除双源缺口修复批 锁集(方案 = .debug/temp/currency_war/
deploy_pseudo_slot/方案.md;三件 ①单一源双置信档 ②kernel 防线 ③熔断)。

- 单一源 grep 锁:bench_item_slots 定义点唯一,钩子/部署两消费点各自引用,
  禁第三方手搓 find_* 拼集;
- 置信档锁:fuzzy=True ⊇ fuzzy=False,部署面消费恰为精确档(A1 方向性:
  泛扫描命中但 find_* 未命中的槽不进标记集——防误标真角色);
- 局34 回放锁(同形态 fixture,B1 显式标记形态):银箱帧精确档识别出伪槽
  槽号;装配点写入端标记(kernel 恒拒的活水,直跑锁);kernel 防线下伪槽
  候选恒 held、计划为空,P24 补部署不绕回;
- kernel 防线锁 + 「照旧上」语义锁(A2):is_item_slot=True 恒 held 拒因
  'item_slot';char_id='' 非伪槽照旧上(SIFT 漏读真角色不被关死 bench);
- 熔断锁:同签名连续 2 次触发;签名变化计数重置;异签名不累积;无 session
  惰性禁用;成功/合法空计划重置。
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path
from types import SimpleNamespace as _NS

import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.cv2_utils import read_image
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    select_deployments_reasoned,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.obs import cw_identity_obs as cio
from sr_od.application.currency_war.operations.cw_op import cw_op_deploy
from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
    assemble_bench_list,
    zero_place_breaker_record,
    zero_place_breaker_should_trip,
    zero_place_sig,
)

_REPO = Path(__file__).resolve().parents[5]
_SCREEN_DIR = _REPO / 'sr-od-test' / 'screens' / '货币战争-备战'

# 备战栏-1..9 pc_rect(assets/game_data/screen_info/currency_war_battle_prep.yml;
# 与 cw_identity_obs._ctx_slots 同一坐标系的离线硬编码,同 find_supply_boxes 分层约定)
_SLOTS = [
    (1, Rect(382, 845, 495, 979)), (2, Rect(507, 844, 620, 978)),
    (3, Rect(632, 844, 743, 978)), (4, Rect(757, 845, 869, 979)),
    (5, Rect(882, 846, 995, 980)), (6, Rect(1004, 847, 1118, 978)),
    (7, Rect(1132, 846, 1244, 977)), (8, Rect(1256, 845, 1368, 979)),
    (9, Rect(1379, 844, 1493, 980)),
]


@pytest.fixture(scope='module')
def _box_frame():
    """局34 同形态 fixture:slot1 银箱、备战 9/9 满(reward_spheres_5.webp)。"""
    img = read_image(str(_SCREEN_DIR / 'reward_spheres_5.webp'))
    assert img is not None, 'fixture 缺失:reward_spheres_5.webp'
    return img


def _patch_slots(monkeypatch) -> None:
    from sr_od.application.currency_war.obs import cw_identity_obs as cio
    monkeypatch.setattr(cio, '_ctx_slots',
                        lambda ctx, prefix, count: list(_SLOTS))


# ==================== 单一源 grep 锁 ====================

def test_bench_item_slots_defined_once_and_consumed_at_both_sites() -> None:
    """单一源:src 全树 ``def bench_item_slots`` 恰一处(obs 层);钩子消费
    模糊档、部署消费精确档,拔掉任一消费点接线(守卫移除)本锁即红。"""
    def_files = [p for p in (_REPO / 'src').rglob('*.py')
                 if 'def bench_item_slots' in p.read_text(encoding='utf-8',
                                                         errors='ignore')]
    assert [p.resolve() for p in def_files] \
        == [Path(cio.__file__).resolve()], \
        f'bench_item_slots 定义点必须唯一(obs 层),实得 {def_files}'

    hook_src = inspect.getsource(cio.read_bench_chars)
    assert 'bench_item_slots(ctx, screen, fuzzy=True)' in hook_src, \
        'summon 停机钩子必须消费单一源模糊档(精确 ∪ 泛扫描)'
    deploy_src = re.sub(r'\s+', '',
                        inspect.getsource(
                            cw_op_deploy.CwOpDeploy._deploy_deterministic))
    assert 'bench_item_slots(self.ctx,scr,fuzzy=False)' in deploy_src, \
        '部署扫描必须消费单一源精确档(泛扫描不给部署面,A1)'


def test_no_third_party_manual_find_set_assembly() -> None:
    """禁第三方手搓拼集:find_supply_boxes 与 find_tomes 的引用只许在
    单一源文件(cw_identity_obs)内;他处再拼 = 新双源。"""
    src_root = _REPO / 'src'
    allowed = {'cw_identity_obs.py'}
    offenders: list[str] = []
    for p in src_root.rglob('*.py'):
        if p.name in allowed:
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        if 'find_supply_boxes' in text or 'find_tomes' in text:
            offenders.append(str(p.relative_to(_REPO)))
    assert not offenders, f'find_* 拼集只许单一源文件引用,越界: {sorted(offenders)}'


# ==================== 置信档锁(A1 方向性) ====================

def test_exact_tier_on_box_fixture(_box_frame, monkeypatch) -> None:
    """精确档:银箱帧 slot1 命中 find_* 族,返回 1-based 槽号。"""
    _patch_slots(monkeypatch)
    exact = cio.bench_item_slots(None, _box_frame, fuzzy=False)
    assert 1 in exact, f'银箱槽1 应被精确档识别,实得 {sorted(exact)}'


def test_fuzzy_superset_of_exact(_box_frame, monkeypatch) -> None:
    """置信档锁:fuzzy=True ⊇ fuzzy=False(同帧同参,档间包含关系)。"""
    _patch_slots(monkeypatch)
    exact = cio.bench_item_slots(None, _box_frame, fuzzy=False)
    fuzzy = cio.bench_item_slots(None, _box_frame, fuzzy=True)
    assert exact <= fuzzy, f'模糊档必须是精确档超集:{sorted(exact)} ⊄ {sorted(fuzzy)}'


def test_deploy_tier_excludes_generic_scan_only_slot(_box_frame, monkeypatch) -> None:
    """A1 方向性:泛扫描可认而 find_* 族(被桩空)未命中的槽,模糊档仍识别
    (钩子不停机判定的输入面在),但**精确档返空**——部署面不消费泛扫描,
    该槽照常进部署(误排真角色 = 战力真空,贵方向,拔掉分档本锁即红)。"""
    _patch_slots(monkeypatch)
    monkeypatch.setattr(cio, 'find_supply_boxes', lambda screen, slots: [])
    monkeypatch.setattr(cio, 'find_tomes', lambda screen, slots: [])
    monkeypatch.setattr(cio, 'find_bookcards', lambda screen, slots: [])
    monkeypatch.setattr(cio, 'find_trial_reveal_cards', lambda screen, slots: [])
    exact = cio.bench_item_slots(None, _box_frame, fuzzy=False)
    fuzzy = cio.bench_item_slots(None, _box_frame, fuzzy=True)
    assert exact == set(), f'精确档不消费泛扫描,应返空,实得 {sorted(exact)}'
    assert 1 in fuzzy, '模糊档应经泛 TM 扫描兜住银箱槽1(钩子档语义)'


# ==================== 局34 回放锁(同形态 fixture)+ 写入端存在性锁 ====================

def test_assembly_marks_item_slot_true() -> None:
    """写入端存在性锁(落地审 B1 盲区补):装配产物对 obs 精确档命中的槽
    显式写 is_item_slot=True,未命中槽恒 False——kernel 恒拒逻辑的活水。
    直跑锁(守卫移除即红)。"""
    # bench_occ=[0,1](像素占用),精确档命中槽2 → 槽2 True、槽1 False
    out = assemble_bench_list([0, 1], bench_cid={}, bench_pos={},
                              item_slots_exact={2})
    assert [bc.slot for bc in out] == [1, 2], '物品槽照常装配(B1 标记形态,非剔除)'
    assert out[0].is_item_slot is False
    assert out[1].is_item_slot is True and out[1].char_id == ''


def test_replay_pseudo_slot_never_reaches_plan(_box_frame, monkeypatch) -> None:
    """局34 形态回放(B1 标记形态):银箱帧精确档产出伪槽槽号 → 装配点
    写入端标记(接线在源内)+ kernel 防线下伪槽候选恒 held、计划为空
    (up=[])、P24 补部署不绕回——伪槽不再流入拖拽。"""
    _patch_slots(monkeypatch)
    item_slots = cio.bench_item_slots(None, _box_frame, fuzzy=False)
    assert 1 in item_slots

    # 装配接线锁:装配点消费精确档标记集(B1 显式标记形态;守卫移除即红)
    deploy_src = re.sub(r'\s+', '',
                        inspect.getsource(
                            cw_op_deploy.CwOpDeploy._deploy_deterministic))
    assert 'assemble_bench_list(bench_occ,_bench_cid,_bench_pos,_item_slots_exact)' \
        in deploy_src
    # P24 补部署绕回守卫:held 名单剔除物品槽(kernel 恒拒件不经 fill 上板)
    assert '(_hi+1)notin_item_slots_exact' in deploy_src

    # kernel 防线行为(直跑装配产物形态):伪槽恒 held、计划为空
    pseudo = cw_op_deploy.assemble_bench_list(
        [0], bench_cid={}, bench_pos={}, item_slots_exact={1})[0]
    up, held, reasons = select_deployments_reasoned(
        [pseudo], deployed_cids=set(), deployed_fac={}, board={}, cap=9)
    assert up == [], '伪槽候选禁入计划(计划为空 = plan_empty=True 合法稳态)'
    assert held == [0] and reasons.get(0) == 'item_slot'


# ==================== kernel 防线 + 「照旧上」语义锁(A2) ====================

def _normal_bc(name: str, slot: int) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(ch.factions[0] if ch.factions else '?'))


def test_item_slot_held_even_as_target_with_vacancy() -> None:
    """防线强度:is_item_slot=True 即使是 target 件且板面有大量空位,
    仍恒 held(先于一切围栏/cap 判定被拒)。"""
    name = next(n for n, ch in CHARACTERS.items() if ch.factions)
    item = BenchChar(slot=2, char_id=name,
                     faction=CHARACTERS[name].factions[0], is_item_slot=True)
    up, held, reasons = select_deployments_reasoned(
        [item], deployed_cids=set(), deployed_fac={}, board={}, cap=9,
        target_factions=frozenset(CHARACTERS[name].factions))
    assert up == [] and held == [0] and reasons.get(0) == 'item_slot'


def test_normal_char_deployed_alongside_item_slot() -> None:
    """混合 bench:正常角色照常上场,伪槽相邻不影响他人(防防线误伤)。"""
    name = next(n for n, ch in CHARACTERS.items() if ch.factions)
    bench = [_normal_bc(name, 1),
             BenchChar(slot=2, char_id='', faction='?', is_item_slot=True)]
    up, held, reasons = select_deployments_reasoned(
        bench, deployed_cids=set(), deployed_fac={}, board={}, cap=9)
    assert up == [0] and held == [1] and reasons.get(1) == 'item_slot'


def test_board_empty_rescue_never_promotes_item_slot() -> None:
    """板空保底只救规则留置件:item_slot 恒拒不因保底被推上板。"""
    item = BenchChar(slot=1, char_id='', faction='?', is_item_slot=True)
    up, _held, reasons = select_deployments_reasoned(
        [item], deployed_cids=set(), deployed_fac={}, board={}, cap=9)
    assert up == [] and reasons.get(0) == 'item_slot'


def test_empty_char_id_still_deploys_deploy_lock() -> None:
    """A2 语义锁(拔掉即红):char_id='' 且非伪槽照旧上——SIFT 漏读的真
    角色不被关死 bench;伪槽身份只能由 is_item_slot 显式标记。"""
    ghost = BenchChar(slot=1, char_id='', faction='?')
    up, held, reasons = select_deployments_reasoned(
        [ghost], deployed_cids=set(), deployed_fac={}, board={}, cap=9)
    assert up == [0], 'char_id='' 未识别候选必须「照旧上」(fail-open 语义保留)'
    assert 0 not in held and reasons.get(0) is None


# ==================== 熔断锁(签名/计数/禁用/重置) ====================

_SIG_A = ((0,), (0,), ('',))
_SIG_B = ((0, 1), (0,), ('', ''))


def test_breaker_trips_on_second_consecutive_same_signature() -> None:
    """同签名连续 2 次:首次失败只记数不熔(让位瞬态重试);第二次触发。"""
    sess = _NS()
    zero_place_breaker_record(sess, _SIG_A, placed=0, plan_non_empty=True)
    assert zero_place_breaker_should_trip(sess, _SIG_A) is False
    zero_place_breaker_record(sess, _SIG_A, placed=0, plan_non_empty=True)
    assert zero_place_breaker_should_trip(sess, _SIG_A) is True


def test_breaker_counts_isolated_per_signature() -> None:
    """签名隔离:异签名不互相累积;签名变化即重置(真重试场景必变
    bench_occ,不误熔)。"""
    sess = _NS()
    zero_place_breaker_record(sess, _SIG_A, 0, True)
    zero_place_breaker_record(sess, _SIG_A, 0, True)
    assert sess.cw_deploy_zeroplace_cnt == 2
    # 换签名:计数归 1 重计,旧签名残留不触发新签名
    zero_place_breaker_record(sess, _SIG_B, 0, True)
    assert sess.cw_deploy_zeroplace_cnt == 1
    assert zero_place_breaker_should_trip(sess, _SIG_B) is False
    assert zero_place_breaker_should_trip(sess, _SIG_A) is False


def test_breaker_reset_on_success_and_on_legal_noop() -> None:
    """重置路径:placed>0(结构性拒绝解除)与 placed=0 且计划空(合法
    稳态 no-op,dd-037)都不算拒拖失败,计数清零。"""
    sess = _NS()
    zero_place_breaker_record(sess, _SIG_A, 0, True)
    zero_place_breaker_record(sess, _SIG_A, placed=2, plan_non_empty=True)
    assert sess.cw_deploy_zeroplace_cnt == 0
    assert zero_place_breaker_should_trip(sess, _SIG_A) is False
    zero_place_breaker_record(sess, _SIG_A, placed=0, plan_non_empty=False)
    assert sess.cw_deploy_zeroplace_cnt == 0


def test_breaker_disabled_without_session() -> None:
    """无 session(测试/离线)→ 熔断惰性禁用,行为等价旧路径。"""
    assert zero_place_breaker_should_trip(None, _SIG_A) is False
    zero_place_breaker_record(None, _SIG_A, 0, True)   # 不抛即过


def test_zero_place_sig_excludes_round_dimensions() -> None:
    """签名 = 计划结构(bench_occ/order/char_id),不含 plane/round_num——
    外循环换轮重试时签名不变,熔断才可能触发(A4)。"""
    assert zero_place_sig([0, 2], [2], {0: '姬子', 2: ''}) \
        == ((0, 2), (2,), ('姬子', ''))
    assert zero_place_sig([0], [0], {0: ''}) == zero_place_sig([0], [0], {})
