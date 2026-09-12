"""旧流写入端退役锁(删除波 1;用户 2026-09-10 直迁裁定)。

裁定口径:不用影子开关/影子期,新账本 journal 无条件常开后,旧 12 流中
「策略源收编 9 流」的写入端直接删除(处置表单一源 =
docs/develop/sr_od/application/currency_war/game_state/retirement.md §2)。禁碰面 =
保留 2 流(defect_ledger/op_journal)+ journal 写路径本体 + 旧档案只读
判读面(query/cli/match_archive 读旧档)。

W4 增量(r5-migration-plan.md §2 W4):逐 key 审计流
cw4_counters 写入端亦退役——局终级全键聚合收编载体 = 局终域行载荷
``MatchFinal.cw4_counters``(journal);键全集登记 = test_cw4_key_closure。
本锁 _OLD_STREAM_FILES/_CALL_SITE_RE/_STREAM_NAME_RE 随之扩员辖 cw4 面。

W7 增量(r5-migration-plan.md §2 W7):清点补遗流 board_state_archive
写点(cw_loop._archive_board_state)退役并入本锁——逐能力归宿 W2 已落位
(bs_prov=快照来源注记/局终速查=match_final 行),存量数据文件归档只读
(不删不写,裸读考古,§4-6)。**保留流豁免申明**(候裁 4 定谳,对抗定谳
记录 T-68 第十节):defect_ledger/op_journal 两流全保留专用,W7 删除面
不含两流(r5 §7 条 4 合法性条款);defect_ledger refs 同批迁移 journal
``(run_id,v)`` 键(本锁 refs 旧挂点归零锁辖)。

锁面 =
- 结构删净锁:9+1 流 writer 符号在 telemetry.recorder/match_archive 上
  不存在;src 生产树代码域无写入调用点/流文件名残留(防半删:writer 删了
  调用点留着 = 死代码)。判定域 = 掩蔽代码域:注释与 docstring 在源文本
  上按字符置空后对代码文本跑正则(机制见 _scan_code_violations)——
  「禁复用 X.jsonl」类负向声明是退役背书而非写入面引用,豁免不误红
  (决策行文件 docstring/注释实测误伤两处);掩蔽保留行/文本结构,代码域
  引用(字符串字面量/标识符/dict 字面量对)仍在域内,复合正则(缺陷 refs
  旧挂点形)跨 token 照常检出,防复活语义不弱化;
- 行为零产出锁:模拟流(run 生命周期 + BoardState 写入 + obs_conflict
  收编面 + run 收口)跑完,旧流文件零新增;journal 照常产出
  (write 行 + obs_event 行,run 归属一致);
- 常开锁:state_journal 影子开关已销案(config 无此字段,app 装配段
  无条件武装 + obs_event 收编制 provider 已注册)。
"""
from __future__ import annotations

import ast
import bisect
import io
import json
import re
import tokenize
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war import currency_war_app as cw_app_mod
from sr_od.application.currency_war import currency_war_config as cw_cfg_mod
from sr_od.application.currency_war.kernel import cw_state_journal
from sr_od.application.currency_war.kernel.cw_board_state import (
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
from sr_od.application.currency_war.kernel.cw_observe import obs_conflict
from sr_od.application.currency_war.telemetry import state as tel_state

#: 收编 9+1 流的旧流文件名(写入端退役对象;retirement.md §2 处置表;
#: cw4_counters.jsonl 随 R5 W4 流删并入——聚合载体改局终域行,r5-migration-plan.md §2 W4;
#: board_state_archive.jsonl 随 R5 W7 写点下线并入——能力归宿 W2 已落位)。
_OLD_STREAM_FILES: tuple[str, ...] = (
    'decisions.jsonl', 'outcomes.jsonl', 'exogenous.jsonl',
    'spend_ledger.jsonl', 'shop_snapshots.jsonl', 'exec_events.jsonl',
    'invest_cards.jsonl', 'obs_conflicts.jsonl', 'runs.jsonl',
    'cw4_counters.jsonl', 'board_state_archive.jsonl',
)

#: 随旧流写入端退役的 writer 符号(telemetry.recorder 模块面)。
_RETIRED_RECORDER_SYMBOLS: tuple[str, ...] = (
    'record_decision', 'record_outcome', 'record_exogenous',
    'record_event_choice', 'record_sell_income', 'record_modality_gold',
    'record_spend_unit', 'record_invest_cards', 'record_shop_snapshot',
    'snapshot_expected_paths',   # 期望态快照 helper,随 ADR-0651 两态制退役
)

#: TelemetryRecorder 类面上退役的方法(保留面 = record_defect/_append/
#: _path/replay_dir 根槽载体)。
_RETIRED_RECORDER_METHODS: tuple[str, ...] = (
    'record_decision', 'record_outcome', 'record_run_summary',
    'record_exec_event', 'record_exogenous', 'record_spend_unit',
)

#: writer 符号/流文件名的只读豁免面(旧档案判读/装配/缺陷 refs/读侧检查;
#: 这些面读旧档案但零写入)。相对 src/sr_od/application/currency_war。
#: 三处书面豁免(逐条申报):kernel/cw_telemetry_exit.py = record_exogenous
#: no-op 桩(护在飞挂起面调用方,恒零产出);kernel/cw_anchor.py = 未入库
#: 在飞文件(T-221 挂起面禁碰,经出口桩上行);strategies/impl/mandate_v1/
#: encounter.py = mandate 本体(禁碰,仅 docstring 提及)。
_READ_FACE_WHITELIST: frozenset[str] = frozenset({
    'telemetry/query.py', 'telemetry/cli.py', 'telemetry/match_archive.py',
    'telemetry/journal_query.py', 'telemetry/schema.py',
    'telemetry/defects.py', 'telemetry/undo_evidence.py',
    'telemetry/cw_replay_reader.py', 'telemetry/cw_match_recorder.py',
    'telemetry/cw_win_features.py', 'telemetry/cw_win_model.py',
    'telemetry/cw_divergence_stats.py', 'telemetry/version_stamp.py',
    'telemetry/op_journal.py', 'sim/ledger_hooks.py',
    'kernel/cw_telemetry_exit.py', 'kernel/cw_anchor.py',
    'strategies/impl/mandate_v1/encounter.py',
    # sim 批账本/语料/离线检查面:批目录同名 jsonl = 独立语料写入
    # (sim runner 自有账本,非 live 旧流),迁移归 M4(sim runner 经统一
    # 写入口落 journal);本锁辖 live 流程侧写入端。
    'sim/runner.py', 'sim/pool.py', 'sim/cw_delta_pool_gen.py',
    'sim/cw_replay.py', 'sim/cw_sim_invest.py', 'sim/checks/ledger.py',
    'sim/checks/pool.py', 'data/cw_delta_pool_data.py',
    'tools/cw_node_validate.py',
})

#: 生产树扫描正则:退役 writer 调用残留(W4 扩员:record_cw4_counters*)。
_CALL_SITE_RE: re.Pattern = re.compile(
    r'record_(?:decision|outcome|run_summary|exec_event|exogenous'
    r'|event_choice|sell_income|modality_gold|spend_unit|invest_cards'
    r'|shop_snapshot|cw4_counters)\b')
#: 生产树扫描正则:旧流文件名字面量(写入面残留;W7 扩员 board_state_archive)。
_STREAM_NAME_RE: re.Pattern = re.compile(
    r'(?:decisions|outcomes|exogenous|spend_ledger|shop_snapshots'
    r'|exec_events|invest_cards|obs_conflicts|runs|cw4_counters'
    r'|board_state_archive)\.jsonl')
#: 缺陷台账 refs 旧挂点字面量(W7 refs 迁移判据:retirement.md §2
#: defect_ledger 行「refs 改指 journal (run_id,v) 键」——旧流行指针在
#: 保留流写点上零残留,防新落台账行继续携带下钻扑空的死地址)。
_REFS_RETIRED_STREAM_RE: re.Pattern = re.compile(
    r"'stream'\s*:\s*'(?:decisions|outcomes|exogenous|spend_ledger"
    r"|shop_snapshots|exec_events|invest_cards|obs_conflicts|runs"
    r"|cw4_counters|board_state_archive)'")

_SRC_ROOT: Path = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
                   / 'application' / 'currency_war')

#: 孤儿构造器符号钉(防写面借尸复活;W7 形态)。
_ORPHAN_SNAPSHOT_RE: re.Pattern = re.compile(r'archive_snapshot')


def _docstring_spans(text: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """收集模块/类/函数 docstring 的位置跨度((起行,起列),(止行,止列))。

    docstring 判定 = 定义体首语句为孤立字符串表达式(ast 标准语义),
    嵌套定义逐层收集。语法解析失败的文件返回空表(扫描回退逐行全判,
    宁误红不漏判)。
    """
    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return spans
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                expr = body[0]
                spans.append(((expr.lineno, expr.col_offset),
                              (expr.end_lineno, expr.end_col_offset)))
    return spans


def _scan_code_violations(
        text: str, *patterns: re.Pattern) -> list[tuple[int, str, int]]:
    """在掩蔽后的代码文本上跑正则,返回 (行号, 命中行原文, 正则序号)。

    判定域机制 = 掩蔽式:先用 tokenize 找出注释 token,用 ast 找出
    docstring 跨度(定义体首语句孤立字符串,ast 标准语义),把这些跨度在
    源文本上**按字符等长置空**,再对置空后的文本跑正则。两全:

    - 豁免:注释/docstring 里的文档性提及(「禁复用 decisions.jsonl」
      类负向声明)随置空消失,不误红——它们是退役背书而非写入面引用
      (决策行文件 docstring:15/注释 :105 实测误伤形状);
    - 检出力:掩蔽只置空字符、不拆结构,正则在连续文本上匹配,跨 token
      复合正则(`_REFS_RETIRED_STREAM_RE` 形 `'stream'\\s*:\\s*'流名'`,
      源码里拆为三个 token)照常检出。禁用「逐 token search」承载复合
      正则——逐单 token 搜索下该形永久失配,dict 字面量复活形
      (`refs=[{'stream': 'decisions', ...}]`,生产树现存同型惯用写法)
      会盲绿。

    与逐行原文语义(掩蔽前的旧判定域)的等价性:豁免面差异 = 仅注释与
    docstring 离开判定域;检出面只强不弱——逐行能检出的形态掩蔽后仍能
    检出,且正则按全文域跑,`\\s*` 可跨行吸收空白/被掩蔽的注释行,键值对
    跨行拆写的 dict 形(`'stream':` 与 `'decisions'` 分行)也检出。

    失败回退(宁误红不漏判):tokenize 失败 → 不掩蔽,对原文全判(含
    注释);ast 解析失败 → docstring 跨度空表 → docstring 不掩蔽(同向)。
    代码位置的字符串字面量(非 docstring 形态)不掩蔽,照判——真实写入
    引用防复活。同一 (行, 正则) 只记一条,不同正则分别记账(序号供调用
    方区分违规类别);行号取匹配起点所在行。
    """
    lines = text.split('\n')
    # 行起始偏移(与 tokenize 物理行一致:按 \n 分行,\r 留在行尾),
    # 供匹配偏移 → 行号换算。
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line) + 1)

    masked_lines: list[str] | None
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        masked_lines = None   # 回退:原文全判
    else:
        masked_lines = list(lines)
        doc_spans = _docstring_spans(text)

        def _in_docstring(tok: tokenize.TokenInfo) -> bool:
            start = (tok.start[0], tok.start[1])
            end = (tok.end[0], tok.end[1])
            return any(s <= start and end <= e for s, e in doc_spans)

        def _blank(srow: int, scol: int, erow: int, ecol: int) -> None:
            """把 (srow,scol)-(erow,ecol) 跨度逐字符置空(等长,保行号)。"""
            for row in range(srow, erow + 1):
                line = masked_lines[row - 1]
                c0 = scol if row == srow else 0
                c1 = ecol if row == erow else len(line)
                masked_lines[row - 1] = \
                    line[:c0] + ' ' * (c1 - c0) + line[c1:]

        for tok in tokens:
            if tok.type == tokenize.COMMENT or (
                    tok.type == tokenize.STRING and _in_docstring(tok)):
                _blank(tok.start[0], tok.start[1], tok.end[0], tok.end[1])

    judge_text = '\n'.join(masked_lines) if masked_lines is not None else text
    hits: dict[tuple[int, int], str] = {}
    for pi, pat in enumerate(patterns):
        for m in pat.finditer(judge_text):
            row = bisect.bisect_right(line_starts, m.start()) - 1
            hits.setdefault((row, pi), lines[row].strip()[:120])
    return [(row + 1, hits[(row, pi)], pi)
            for row, pi in sorted(hits)]


@pytest.fixture()
def _retire_isolation():
    """run 态/recorder 根槽/journal 槽三面隔离(模块槽进程全局,teardown 复位)。"""
    tel_state.reset_run_state()
    yield
    tel_state.reset_run_state()
    tel_state.set_recorder_replay_dir(None)
    cw_state_journal.reset_state_telemetry()
    cw_telemetry_exit_reset_obs_provider()


def cw_telemetry_exit_reset_obs_provider() -> None:
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    cw_telemetry_exit.set_obs_event_board_provider(None)


# ============================================================ 结构删净锁


def test_retired_writer_symbols_absent_from_recorder() -> None:
    """9 流 writer 符号自 recorder 模块/类面删除(删代码非停写)。"""
    from sr_od.application.currency_war.telemetry import recorder
    for sym in _RETIRED_RECORDER_SYMBOLS:
        assert not hasattr(recorder, sym), \
            f'recorder.{sym} 应已随退役删除(防半删)'
    for m in _RETIRED_RECORDER_METHODS:
        assert not hasattr(recorder.TelemetryRecorder, m), \
            f'TelemetryRecorder.{m} 应已随退役删除(防半删)'
    # 保留面在位:缺陷台账(保留专用流)写入。
    # (snapshot_expected_paths 已移入退役符号表——expected_state 条目表
    #  随 ADR-0651 两态制废除,快照无源可取。)
    assert hasattr(recorder.TelemetryRecorder, 'record_defect')


def test_no_retired_writer_call_sites_in_production_tree() -> None:
    """src 生产树代码域无退役 writer 调用点/旧流文件名残留(只读豁免面除外)。

    判定域 = 掩蔽代码域(注释/docstring 置空后跑正则,机制见
    _scan_code_violations):「禁复用 decisions.jsonl」类负向声明是退役
    背书,不是写入面引用(决策行文件 docstring/注释误伤实测修正);真实
    写入引用(字符串字面量/标识符)仍判红,防复活语义不变。
    """
    violations: list[str] = []
    for py in sorted(_SRC_ROOT.rglob('*.py')):
        rel = py.relative_to(_SRC_ROOT).as_posix()
        if rel in _READ_FACE_WHITELIST:
            continue
        text = py.read_text(encoding='utf-8')
        for lineno, snippet, pi in _scan_code_violations(
                text, _CALL_SITE_RE, _STREAM_NAME_RE):
            kind = '调用残留' if pi == 0 else '流名残留'
            violations.append(f'{rel}:{lineno} {kind}: {snippet}')
    assert violations == [], '旧流写入面残留(防半删):\n' + '\n'.join(violations)


def test_defect_refs_no_retired_stream_anchors() -> None:
    """缺陷台账 refs 旧挂点归零锁(W7 refs 迁移判据)。

    retirement.md §2 defect_ledger 行(候裁 4 定谳):保留专用流的 refs
    改指 journal ``(run_id,v)`` 键——构造单一源 =
    kernel.cw_telemetry_exit.journal_refs(无账本媒体时诚实省略)。旧流
    (decisions/outcomes/obs_conflicts 等)写面已随删除波 1 退役,refs 字面
    指旧流名 = 新落台账行携带下钻扑空的死地址。豁免面 = 本锁白名单
    (读旧冻结档案的判读/装配面);非白名单命中 = 旧挂点复活。
    """
    violations: list[str] = []
    for py in sorted(_SRC_ROOT.rglob('*.py')):
        rel = py.relative_to(_SRC_ROOT).as_posix()
        if rel in _READ_FACE_WHITELIST:
            continue
        text = py.read_text(encoding='utf-8')
        for lineno, snippet, _pi in _scan_code_violations(
                text, _REFS_RETIRED_STREAM_RE):
            violations.append(f'{rel}:{lineno} refs 旧挂点: {snippet}')
    assert violations == [], '缺陷 refs 旧挂点残留:\n' + '\n'.join(violations)


def test_board_state_archive_writer_orphan_pinned() -> None:
    """board_state_archive 写点退役后 kernel 侧孤儿符号钉住(W7)。

    ``archive_snapshot``(kernel/cw_board_state)是写点删除后的孤儿构造器:
    本体在该文件内(守卫族+波次面禁触,删除归 kernel 面批),锁其生产树
    **零调用点**防写面借尸复活;删除时机 = kernel 面微批,届时连同本锁
    收窄。tool/测试直接调用不受生产树扫描辖。
    """
    violations: list[str] = []
    for py in sorted(_SRC_ROOT.rglob('*.py')):
        rel = py.relative_to(_SRC_ROOT).as_posix()
        if rel == 'kernel/cw_board_state.py':
            continue   # 本体居所(孤儿待删,禁触面)
        text = py.read_text(encoding='utf-8')
        for lineno, snippet, _pi in _scan_code_violations(
                text, _ORPHAN_SNAPSHOT_RE):
            violations.append(f'{rel}:{lineno}: {snippet}')
    assert violations == [], \
        'archive_snapshot 生产调用点残留(写点应已退役):\n' + '\n'.join(violations)


def test_docstring_mention_exempted_but_code_reference_flagged() -> None:
    """负向声明豁免的变异自检(双向):文档性提及不判红,代码域引用仍判红。

    防三种回归:①豁免写宽(STRING 一刀切全豁)→ 真实写入引用漏判,
    防复活失效;②豁免失效(回退逐行原文全判)→「禁复用 decisions.jsonl」
    类负向声明误红复发(决策行文件 docstring:15/注释 :105 误伤形状);
    ③判定域退化为逐 token 搜索 → refs 复合正则
    (`'stream'\\s*:\\s*'流名'`,源码拆为三 token)在单 token 上永久失配,
    dict 字面量复活形盲绿——前六形态辖的两把正则都是单 token 形,探不到
    该退化,refs 面单独钉住(豁免/检出两条腿,含单行/跨行对齐/键值对
    跨行拆写三种复活形)。合成语料直扫 _scan_code_violations,不落生产树。
    """
    assert _scan_code_violations(
        '# 禁复用 decisions.jsonl(历史档案以该名为键,双载体同名 = 读面歧义)',
        _STREAM_NAME_RE) == [], '注释负向声明不得判红(T-93 误伤形状)'
    assert _scan_code_violations(
        '"""禁复用 decisions.jsonl(退役背书)。"""',
        _STREAM_NAME_RE) == [], 'docstring 负向声明不得判红(T-93 误伤形状)'
    assert _scan_code_violations(
        '# 退役 writer 记录口:record_decision 已删',
        _CALL_SITE_RE) == [], '注释里 writer 符号提及不得判红'
    hits = _scan_code_violations("_legacy = 'decisions.jsonl'",
                                 _STREAM_NAME_RE)
    assert len(hits) == 1 and hits[0][0] == 1, \
        f'代码域字符串字面量引用必须判红(防复活),实得 {hits}'
    hits_call = _scan_code_violations('telemetry.record_decision(row)',
                                      _CALL_SITE_RE)
    assert len(hits_call) == 1, \
        f'代码域 writer 调用必须判红(防复活),实得 {hits_call}'
    hits_mixed = _scan_code_violations(
        "_legacy = 'decisions.jsonl'  # 禁复用(见 retirement.md §2)",
        _STREAM_NAME_RE)
    assert len(hits_mixed) == 1, \
        f'行尾注释掩蔽后同行代码引用仍须判红,实得 {hits_mixed}'
    # ---- refs 复合正则双向断言(豁免腿)----
    assert _scan_code_violations(
        "# 缺陷 refs 旧挂点形 {'stream': 'decisions'} 已退役,"
        "新行 refs 改指 journal (run_id,v) 键",
        _REFS_RETIRED_STREAM_RE) == [], '注释里 refs 旧挂点形提及不得判红'
    assert _scan_code_violations(
        "\"\"\"refs 旧挂点 'stream': 'decisions' 形已退役(负向声明)。\"\"\"",
        _REFS_RETIRED_STREAM_RE) == [], \
        'docstring 里 refs 旧挂点形提及不得判红'
    # ---- refs 复合正则双向断言(检出腿:dict 字面量复活形三种)----
    hits_refs_1 = _scan_code_violations(
        "refs=[{'stream': 'decisions', 'run_id': 1}]",
        _REFS_RETIRED_STREAM_RE)
    assert len(hits_refs_1) == 1 and hits_refs_1[0][0] == 1, \
        f'dict 字面量复活形(单行)必须判红(防复活),实得 {hits_refs_1}'
    hits_refs_n = _scan_code_violations(
        'refs=[\n'
        '    {\n'
        "        'stream': 'decisions',\n"
        "        'run_id': 1,\n"
        '    },\n'
        ']',
        _REFS_RETIRED_STREAM_RE)
    assert len(hits_refs_n) == 1 and hits_refs_n[0][0] == 3, \
        f'dict 字面量复活形(跨行对齐)必须判红(防复活),实得 {hits_refs_n}'
    hits_refs_split = _scan_code_violations(
        "refs=[{\n    'stream':\n    'decisions',\n}]",
        _REFS_RETIRED_STREAM_RE)
    assert len(hits_refs_split) == 1 and hits_refs_split[0][0] == 2, \
        f'键值对跨行拆写复活形必须判红(掩蔽域按全文跑正则),实得 {hits_refs_split}'


# ============================================================ 行为零产出 + journal 照常锁


def test_simulated_flow_zero_old_stream_output_and_journal_produces(
        tmp_path) -> None:
    """模拟流(run 生命周期+BoardState 写入+obs_conflict 收编+run 收口)后:
    旧 9 流文件零新增;journal 照常产出(write+obs_event,归属一致)。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    from sr_od.application.currency_war.kernel.cw_board_state import (
        BS_SCHEMA_VERSION,
        BoardState,
    )

    tel_state.set_recorder_replay_dir(tmp_path)
    journal = cw_state_journal.install_state_telemetry(
        tmp_path / 'state' / 'journal.jsonl', flush_every=1,
        run_id_provider=tel_state.current_run_id)
    # 收编制 provider(生产在 app 装配段注册;测试同形接通)
    match = SimpleNamespace(session=SimpleNamespace())
    cw_telemetry_exit.set_obs_event_board_provider(
        lambda: board_state_of(match.session))
    rid = tel_state.ensure_run_started(match, 'mandate_v1')
    assert rid, 'run 生命周期照常(run_id 供给 journal 归属)'
    # BoardState 照常写入(journal write 行)
    bs = board_state_of(match.session)
    assert isinstance(bs, BoardState)
    bs.schema_version = BS_SCHEMA_VERSION
    bs.observe(bs.gold, 20, sig=_sig())
    # obs_conflict 收编面:证据进 journal 行型 2,旧流零写入
    obs_conflict('gold', 20, 21, verdict='锁面', source='retire_lock')
    # run 收口(收口位;runs 流零写入)
    tel_state.close_run(result='stopped', plane_reached=1,
                        rounds_survived=1, final_hp=10)
    journal.flush()
    for name in _OLD_STREAM_FILES:
        assert not (tmp_path / name).exists(), \
            f'旧流 {name} 不得新增(写入端已退役,模拟流零产出)'
    jpath = tmp_path / 'state' / 'journal.jsonl'
    rows = [json.loads(line) for line in
            jpath.read_text(encoding='utf-8').splitlines() if line.strip()]
    kinds = {r.get('row') for r in rows}
    assert {'write', 'obs_event'} <= kinds, \
        f'journal 照常产出(write+obs_event),实得 {kinds}'
    assert all(r.get('run_id') == rid for r in rows), 'journal 行归属一致'
    ev = [r for r in rows if r.get('row') == 'obs_event'][-1]
    assert ev['field'] == 'gold' and ev['verdict'] == '锁面', \
        'obs_event 行携带原 obs_conflict 证据语义'


# ============================================================ journal 无条件常开锁


def test_state_journal_flag_abolished_and_assembly_unconditional() -> None:
    """state_journal 影子开关销案:config 面无字段;app 装配段无条件武装
    并注册 obs_event 收编制 provider(无 flag 分支)。"""
    cfg_src = Path(cw_cfg_mod.__file__).read_text(encoding='utf-8')
    assert 'state_journal' not in cfg_src, \
        'state_journal 开关应已随直迁裁定销案(无影子开关)'
    app_src = Path(cw_app_mod.__file__).read_text(encoding='utf-8')
    assert 'install_state_telemetry' in app_src, '装配段保留 journal 武装'
    assert '.state_journal' not in app_src, '装配段不得再有开关分支'
    assert 'set_obs_event_board_provider' in app_src, \
        '装配段注册 obs_event 收编制 provider'
