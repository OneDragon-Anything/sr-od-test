"""BoardState 迁移批次四回归锁(退役 + relay 空值闸;设计正本 =
docs/develop/currency_war/design/BoardState-数据结构设计.md,下称「设计」)。

锁面 = §8.7 批次四:
- **relay 会话侧值已确立闸**(§2.1:会话载体默认空值 ''/[] 是「未知」非
  「已知事实」,禁中继成正式值;字符串非空/列表非空才中继)——单元锁 +
  恢复局场景端到端锁(新 session 空默认不落 BoardState、真值后到可落);
- **退役载体零残留**(AST 级静态锁,标识符面):已退役符号全仓零命中 +
  记录面(kernel/cw_board_state.py)零 last_state 标识符命中;
- payload 域三域口径的对齐断言在批一文件(test_cw_board_state.py,
  test_leave_screen_payload_only 负断言辖 settlement),本文件不重复。

断言全部按设计语义写;批一/二/三锁(test_cw_board_state[_consume|_batch3].py)
持续有效,本文件不重复其断言面。
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BoardState,
    board_state_of,
)


# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_board_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
    register_sig_actors as _register_sig_actors,
)

_register_sig_actors('TestSigWriter')


def _sig() -> "_ChannelSig":
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> "_ChannelSig":
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _hsig() -> "_ChannelSig":
    """渠道③签名(logic_hook 族;relay 中继)。"""
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')

_REPO = Path(__file__).resolve().parents[5]
_PKG = _REPO / 'src' / 'sr_od' / 'application' / 'currency_war'

#: §2.1 五镜像字段(批次二 feed 中继点;恢复局新 session 停在空默认的面)。
_MIRROR_FIELDS = ('active_strategies', 'active_env', 'plane_bosses',
                  'enemy_affixes', 'selected_difficulty')


# ============================================================ §2.1 relay 空值闸


def test_relay_rejects_session_empty_defaults() -> None:
    """§2.1 空值=未知态禁中继:字符串空/空白、列表/元组/字典/集合空 = 会话
    侧值未确立,一律拒写(返回 False,字段保持从未写过)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.relay(bs.active_env, '', sig=_hsig()) is False
    assert bs.relay(bs.selected_difficulty, '   ', sig=_hsig()) is False, \
        '空白字符串 = 无内容读数,同空域'
    assert bs.relay(bs.active_strategies, [], sig=_hsig()) is False
    assert bs.relay(bs.plane_bosses, (), sig=_hsig()) is False
    assert bs.relay(bs.enemy_affixes, {}, sig=_hsig()) is False
    for name in _MIRROR_FIELDS:
        fld = getattr(bs, name)
        assert fld.value is None, f'空默认禁落 BoardState:{name}'
        assert fld.evidence is None, '拒写不留任何来源痕迹'


def test_relay_empty_refusal_does_not_block_late_truth() -> None:
    """恢复局核心语义:空默认被拒后字段仍是「从未写过」——真值后到可正常
    落(source=logic + evidence=session_carrier,§2.1 中继形态);「持卡名单
    [] 为假事实、拦截后到真值」的缺陷面由本锁钉死。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.relay(bs.active_strategies, [], sig=_hsig()) is False
    assert bs.relay(bs.active_env, '', sig=_hsig()) is False
    assert bs.relay(bs.active_strategies, ['白银投资'], sig=_hsig()) is True
    assert bs.active_strategies.value == ['白银投资']
    assert bs.active_strategies.source == 'logic'
    assert bs.active_strategies.evidence == 'session_carrier'
    assert bs.relay(bs.active_env, '昼之半神概念股', sig=_hsig()) is True
    assert bs.active_env.value == '昼之半神概念股'
    assert bs.active_env.evidence == 'session_carrier'


def test_relay_gate_scope_is_empty_string_and_containers_only() -> None:
    """闸辖域 = 空字符串与空容器(§2.1 词面:字符串非空/列表非空);falsy 但
    有语义的标量(如 streak=0 真 0)不受闸辖,禁过度收紧。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.relay(bs.streak, 0, sig=_hsig()) is True
    assert bs.streak.value == 0 and bs.streak.source == 'logic'
    assert bs.relay(bs.plane_bosses, [None, None, None], sig=_hsig()) is True, \
        '非空列表即确立(结构已知,元素 None = 该位面无身份,§8.4)'


# ============================================================ 恢复局场景端到端


def _feed_ctx(sess: SimpleNamespace) -> SimpleNamespace:
    """read_game_state 观察流测试的最小 ctx(mock ocr_service 空读;
    screen_loader 空 = 全部 area rect 缺失 → 各 reader 自然失读)。"""
    return SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: []),
    )


def _patch_clean_readers(monkeypatch: pytest.MonkeyPatch) -> None:
    """prep_clean 帧各 reader 桩(只读链,零像素;与批一文件同式——镜像字段
    中继走 feed 尾部公共段,reader 读值与本锁断言面无关)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation as obs

    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen: (1, 4),
                        raising=False)
    monkeypatch.setattr(obs, 'read_hp_opt', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_node_type', lambda ctx, screen: 'battle',
                        raising=False)
    monkeypatch.setattr(obs, 'gate_node_type', lambda v, rn: v, raising=False)
    monkeypatch.setattr(obs, 'ledger_node_type',
                        lambda sess_, p, r: None, raising=False)
    monkeypatch.setattr(obs, 'verify_node_type_votes',
                        lambda ctx, screen, p, r: None, raising=False)
    monkeypatch.setattr(obs, 'read_xp_progress',
                        lambda ctx, screen, expected_level=None: (2, 8),
                        raising=False)
    monkeypatch.setattr(obs, 'read_level_raw_opt', lambda ctx, screen: 5,
                        raising=False)
    monkeypatch.setattr(obs, '_level_from_xp', lambda xp: None, raising=False)
    monkeypatch.setattr(obs, '_resolve_level',
                        lambda raw, exp, xp_lv, last: (5, [], True),
                        raising=False)
    monkeypatch.setattr(obs, 'resolve_paddle_pair',
                        lambda ctx, screen, level: (None, None), raising=False)
    monkeypatch.setattr(obs, 'board_from_tracked', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, 'is_prep_like_frame',
                        lambda ctx, screen: True, raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({'列车同行': (2, 3)}, True), raising=False)


def test_restore_session_empty_mirrors_not_relayed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """§2.1 恢复局场景(端到端):恢复局新 session 五镜像字段停会话默认
    (''/[])→ 生产 feed(read_game_state 观察流)逐帧中继全被空值闸拒,
    BoardState 五字段保持 None(未知态不固化成正式值)。"""
    from sr_od.application.currency_war.obs import cw_observation

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_clean_readers(monkeypatch)

    cw_observation.read_game_state(_feed_ctx(sess), None, phase='prep_clean')

    bs = board_state_of(sess)
    for name in _MIRROR_FIELDS:
        fld = getattr(bs, name)
        assert fld.value is None, f'恢复局空默认禁中继落记录:{name}'


def test_restore_session_late_truth_relay_lands(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """§2.1 恢复局场景(端到端续):真值后到(session 侧被接管协议/事件屏
    handler 写入)→ 下一帧中继正常落五镜像(source=logic + evidence=
    session_carrier)——空默认拒写不拦截后到真值。"""
    from sr_od.application.currency_war.obs import cw_observation

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_clean_readers(monkeypatch)
    ctx = _feed_ctx(sess)

    cw_observation.read_game_state(ctx, None, phase='prep_clean')

    # 真值后到(恢复局:简报/事件屏/难度确认屏写端补齐会话侧事实)
    sess.active_strategies = ['白银投资']
    sess.active_env = '昼之半神概念股'
    sess.briefing_bosses = ['首领甲', None, None]
    sess.briefing_affixes = ['正当防卫']
    sess.selected_difficulty = 'A8'
    cw_observation.read_game_state(ctx, None, phase='prep_clean')

    bs = board_state_of(sess)
    assert bs.active_strategies.value == ['白银投资']
    assert bs.active_env.value == '昼之半神概念股'
    assert bs.plane_bosses.value == ['首领甲', None, None]
    assert bs.enemy_affixes.value == ['正当防卫']
    assert bs.selected_difficulty.value == 'A8'
    for name in _MIRROR_FIELDS:
        fld = getattr(bs, name)
        assert fld.source == 'logic', f'中继形态 logic(§2.1):{name}'
        assert fld.evidence == 'session_carrier', f'中继注记:{name}'


# ============================================================ AST 级静态锁(退役零残留)

#: 已退役符号(载体已删,防复活):免战牌平行 Field(批次二载体归一,§8.6-3)
#: 与席满警告位字段(§3.2.5 通道退役,载体随退役批删除)。
_RETIRED_SYMBOLS = ('skip_battle_active', 'skip_battle_remaining',
                    'bench_full_flag')


def _identifiers(path: Path) -> set[str]:
    """AST 标识符集(Name/Attribute/关键字形参)——docstring/注释/字典键
    字符串不属标识符,天然不在断言面(遥测行 'bench_full_flag' 键不受辖)。"""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            out.add(node.arg)
    return out


def test_ast_retired_symbols_zero_hits_repo_wide() -> None:
    """§8.7 批次四静态锁:已退役符号在 CW 包全仓零标识符命中(定义/引用/
    关键字实参皆算)——字段本体删除后的防复活锁(比字段存在性负锁更广:
    连「重新引用已删名」的代码也拦)。"""
    offenders: list[str] = []
    for f in sorted(_PKG.rglob('*.py')):
        hit = sorted(set(_RETIRED_SYMBOLS) & _identifiers(f))
        if hit:
            offenders.append(f'{f.relative_to(_PKG)}: {hit}')
    assert not offenders, f'已退役符号标识符复活:{offenders}'


def test_ast_record_layer_reads_no_last_state() -> None:
    """§8.7 批次四静态锁(记录面):kernel/cw_board_state.py 零 last_state
    标识符命中——记录模型只由观察流/写入 API/sim 合成口供数(§2.4),
    禁读 session.last_state 旧观察帧(帧新鲜度差域的独立性与记录/消费
    分离的结构前提)。

    **锁面边界申报**:「last_state 全仓 0 命中」= 迁移尾批完成态断言——
    执行侧装配源切换 ~18 点(ADR-0530,设计 §8.7 尾批行)在产消费
    last_state,尾批完成后把本断言面从记录面扩到全仓;现写全仓零命中
    断言 = 永久红锁,不做。
    """
    ids = _identifiers(_PKG / 'kernel' / 'cw_board_state.py')
    assert 'last_state' not in ids, \
        '记录面(kernel/cw_board_state.py)不得引用 last_state 旧帧'
