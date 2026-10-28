"""羁绊档位条件发放判据测试(T-41 特邀专家:加拉赫击破档分支;镜像 src =
kernel/cw_faction_callbacks.py)。

被测面 = T-41 设计稿 §4.2 判据矩阵(经生产写路径 write_logic(deployed)
→ 值回调级联驱动,防假绿;判定语义单一源 = ``check_env_bond_tier_
grants``,发放原语 = ``cw_env_grants.grant_env_bond_tier``):
- 无环境 / 环境非加拉赫 → 零写零 done;
- 跨档发放恰 1 件 + done 恰如预期(两笔同 evidence 同 sig 相邻,
  equips 走 write_logic_rand / done 走 write_logic);
- 单窗跨两档各 1 件(两对写,evidence 各带档位);
- 每档一次性:降档再回零新增写(用户裁定「每个档位只发一次奖励」);
- equips None 跳过后,不改任何 watched 集的板面写(卖非在册阵营场上件)
  重试补发(sets-changed 门外的必查语义,判据挂点锁);
- 阈值边界:计数 1(2/4/6/9 全不达)零写;
- L2 装备贡献锁:非击破出身穿【击破星徽】→ 计数达标触发;
- 递归安全:发放窗口内无 deployed 行域写(写序检查)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_env_grants as grants_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)

_ENV = '特邀专家:加拉赫'
_EQUIP = '以太钻头'
_BOND = '击破'
_TIER2_KEY = (_ENV, 'bond_tier_2')

_SIG = ChannelSig(family='logic_action', actor='test', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _gs(*, env: str | None = None,
        equips: list[str] | None = None) -> GameState:
    """容器组装(None = 保持未写形态;登记/库存经 logic 直写播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       sig=_SIG)
    return gs


def _u(cid: str, star: int = 1, equips: list[str] | None = None) -> Unit:
    return Unit(char_id=cid, star=star, equips=list(equips or []))


def _view(front: list[Unit] = (), back: list[Unit] = ()) -> DeployedView:
    """紧凑序 → 视图(front/back = Unit 列表,顺延落位)。"""
    f = list(front) + [None] * (4 - len(front))
    b = list(back) + [None] * (6 - len(back))
    return DeployedView(front_slots=f, back_slots=b)


def _write_dep(gs: GameState, front: list[Unit]) -> None:
    """deployed 逻辑写(生产写路径 = write_logic → 值回调级联)。"""
    gs.write_logic(gs.deployed, _view(front), produced_by='test',
                   evidence='t:deploy', sig=_SIG)


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道, sig)
    写行(嵌套回调内的发放写同经实例属性包装,一并落记录)。"""
    calls: list[tuple[str, str | None, str, ChannelSig]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel, sig))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def _grant_rows(calls: list[tuple]) -> list[tuple]:
    """发放域写行过滤(deployed 触发行不入)。"""
    return [c for c in calls if c[0] in ('equips', 'env_grants_done')]


# ============================================================ 门与发放


def test_no_env_and_other_env_zero_writes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """无环境(active_env 未选)/ 环境非加拉赫(在册但无表条目)→
    零写零 done。"""
    for label, gs in (('无环境', _gs(equips=[])),
                      ('环境不在表', _gs(env='蓝海', equips=[]))):
        calls = _record_writes(gs, monkeypatch)
        _write_dep(gs, [_u('乱破'), _u('大丽花')])
        assert _grant_rows(calls) == [], f'{label} 零发放写'
        assert gs.env_grants_done.value in (None, ()), f'{label} 零 done'


def test_threshold_boundary_then_cross_tier_grants_once(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """阈值边界:计数 1(2/4/6/9 全不达)零写;部署过 2 档 → 恰发 1 件
    以太钻头(equips 尾追)+ done 恰 bond_tier_2;两笔同 evidence 同
    sig 相邻(rand 在前)。"""
    gs = _gs(env=_ENV, equips=['永动机'])
    calls = _record_writes(gs, monkeypatch)
    _write_dep(gs, [_u('乱破')])
    assert _grant_rows(calls) == [], '计数 1 未达档零写'
    assert gs.env_grants_done.value in (None, ())

    _write_dep(gs, [_u('乱破'), _u('大丽花')])
    evidence = f'env_grant#{_ENV}#bond{_BOND}@tier2'
    assert _grant_rows(calls) == [
        ('equips', evidence, 'rand', grants_mod._GRANT_SIG),
        ('env_grants_done', evidence, 'logic', grants_mod._GRANT_SIG),
    ], f'两笔同 evidence 同 sig 相邻(rand 在前): {calls}'
    assert gs.equips.value == ['永动机', _EQUIP], '库存尾部追加恰 1 件'
    assert gs.equips.source == 'logic_rand', '发放 = 随机态通道'
    assert gs.env_grants_done.value == (_TIER2_KEY,)
    assert gs.env_grants_done.source == 'logic', 'done = 登记事实直写'


def test_single_window_two_tiers_two_pairs(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """单窗跨两档(1→4):两档各 1 件,两对写相邻,evidence 各带档位,
    done 双键齐(bond_tier_2 + bond_tier_4)。"""
    gs = _gs(env=_ENV, equips=[])
    calls = _record_writes(gs, monkeypatch)
    _write_dep(gs, [_u('乱破')])
    calls.clear()
    _write_dep(gs, [_u('乱破'), _u('大丽花'), _u('阮·梅'), _u('波提欧')])
    ev2 = f'env_grant#{_ENV}#bond{_BOND}@tier2'
    ev4 = f'env_grant#{_ENV}#bond{_BOND}@tier4'
    assert _grant_rows(calls) == [
        ('equips', ev2, 'rand', grants_mod._GRANT_SIG),
        ('env_grants_done', ev2, 'logic', grants_mod._GRANT_SIG),
        ('equips', ev4, 'rand', grants_mod._GRANT_SIG),
        ('env_grants_done', ev4, 'logic', grants_mod._GRANT_SIG),
    ], f'逐档各自成对写(一档一证据): {calls}'
    assert gs.equips.value == [_EQUIP, _EQUIP], '两档各 1 件'
    assert gs.env_grants_done.value == ((_ENV, 'bond_tier_2'),
                                        (_ENV, 'bond_tier_4'))


def test_once_per_tier_downgrade_reup_no_regrant(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """每档一次性(用户裁定「每个档位只发一次奖励」):发放后卖到 1 再
    回 2 → 零新增写(done 封账,祈愿「首达档一次」同口径)。"""
    gs = _gs(env=_ENV, equips=['永动机'])
    calls = _record_writes(gs, monkeypatch)
    _write_dep(gs, [_u('乱破'), _u('大丽花')])
    assert gs.env_grants_done.value == (_TIER2_KEY,)
    calls.clear()

    _write_dep(gs, [_u('乱破')])       # 卖到 1(下穿,本就无判)
    assert _grant_rows(calls) == [], '下穿零写'
    _write_dep(gs, [_u('乱破'), _u('大丽花')])   # 再回 2(档已封账)
    assert _grant_rows(calls) == [], '降档再回不重发(done 封账)'
    assert gs.equips.value == ['永动机', _EQUIP], '仍只 1 件'
    assert gs.env_grants_done.value == (_TIER2_KEY,)


def test_equips_none_withhold_then_board_write_retry(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """equips None 跳过(宁缺勿造,零写零 done)后,不改任何 watched 集
    的板面写(卖非在册阵营场上件,击破计数不动)重试补发——sets-changed
    门辖不到的写,门外必查分支兜住(判据挂点锁,接回门内本测试即红)。"""
    gs = _gs(env=_ENV)   # equips 未写 = None
    _write_dep(gs, [_u('乱破'), _u('大丽花'), _u('希儿')])
    assert gs.equips.value is None, '缺读零写(宁缺勿造)'
    assert gs.env_grants_done.value is None, '缺读不标 done'

    gs.write_logic(gs.equips, ['永动机'], produced_by='test-seed', sig=_SIG)
    calls = _record_writes(gs, monkeypatch)
    _write_dep(gs, [_u('乱破'), _u('大丽花')])   # 卖希儿:watched 集不变
    evidence = f'env_grant#{_ENV}#bond{_BOND}@tier2'
    assert _grant_rows(calls) == [
        ('equips', evidence, 'rand', grants_mod._GRANT_SIG),
        ('env_grants_done', evidence, 'logic', grants_mod._GRANT_SIG),
    ], f'零计数变化板面写重试补发: {calls}'
    assert gs.equips.value == ['永动机', _EQUIP]
    assert gs.env_grants_done.value == (_TIER2_KEY,)


def test_l2_badge_contribution_triggers_grant(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """L2 装备贡献锁(资格集口径):出身非击破的两位穿【击破星徽】后
    计数 2 → 触发发放;无徽时零写(触发归装备贡献,非成员身份)。"""
    gs = _gs(env=_ENV, equips=[])
    calls = _record_writes(gs, monkeypatch)
    _write_dep(gs, [_u('希儿'), _u('白厄')])
    assert _grant_rows(calls) == [], '无徽非出身零计零写'

    _write_dep(gs, [_u('希儿', equips=['击破星徽']),
                    _u('白厄', equips=['击破星徽'])])
    assert _grant_rows(calls) != [], '穿击破星徽计数达标触发'
    assert gs.env_grants_done.value == (_TIER2_KEY,)
    assert gs.equips.value == [_EQUIP]


def test_grant_window_has_no_deployed_row_writes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """递归安全断言(写序检查):跨档部署写窗口内,写序 = deployed 触发行
    → equips 随机态 → done 登记,零第二笔 deployed 行域写(发放两笔均非
    deployed 域,不触发回调再入)。"""
    gs = _gs(env=_ENV, equips=['永动机'])
    calls = _record_writes(gs, monkeypatch)
    _write_dep(gs, [_u('乱破'), _u('大丽花')])
    assert [c[0] for c in calls] == ['deployed', 'equips', 'env_grants_done'], \
        f'发放窗口内无 deployed 行域写(写序): {calls}'
