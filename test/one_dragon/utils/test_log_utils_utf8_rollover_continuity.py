"""回归锁:轮转占用下的日志连续性 + UTF-8 编码统一。

背景(2026-08-30 起的「当天对局日志全损」事故面,诊断锚点 =
.debug/sr_od_mcp/main_server.log 顶部 3165 条 ``--- Logging error ---``):
标准库 ``TimedRotatingFileHandler`` 换名被外部句柄挡住时,``rolloverAt``
不推进 → 整天每条日志重试换名、每条都失败,正文只以无时间戳的
``--- Logging error ---`` 碎片落 stderr,当天日志永久不可考。Safe 版
handler 的自愈链(退避重试 → copytruncate 归档 → 推迟降级)已由
test_log_utils_safe_rotate / test_log_utils_rotate_copytruncate 逐路径锁定;
本文件锁「端到端形状」:同一 handler 一次被占用的强制轮转前后,日志流
**连续可读**(归档含轮转前全部行、续写文件含轮转后全部行),且中英文/
特殊字符全程按 UTF-8 落盘(bytes 级断言,防 locale GBK 回潮——
GBK 写入失败正是旧 ``--- Logging error ---`` 的另一前兆形态)。
"""

import logging
import os
import time

import pytest

from one_dragon.utils.log_utils import SafeTimedRotatingFileHandler

_NT_ONLY = pytest.mark.skipif(os.name != 'nt', reason='rename 占位报错是 Windows 行为')

#: 覆盖中文/全角/emoji 类四字节区/引号反斜杠的混合样本(编码用例断言面)
_MIXED_LINES = [
    '区域集合数据加载完成 共124个',
    '混写: "引号" 反斜杠\\ 换行符字面量\\n 保持单行',
    '全角：，！？与特殊字符①②③ ✅❌',
]


@_NT_ONLY
def test_rollover_under_occupied_handle_keeps_log_continuous_utf8(tmp_path) -> None:
    """强制滚转 + 外部句柄占用:归档/续写两段拼起来 = 完整日志流,UTF-8 落盘。"""
    target = str(tmp_path / 'mcp_server.log')
    handler = SafeTimedRotatingFileHandler(
        target, when='midnight', backupCount=3, encoding='utf-8', delay=True,
    )
    formatter = logging.Formatter('[%(levelname)s]: %(message)s')
    handler.setFormatter(formatter)
    logger = logging.getLogger('utf8-rollover-continuity-test')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)

    # 轮转前:写混合编码样本(走 handler 的 utf-8 流)
    for line in _MIXED_LINES:
        logger.info(line)
    handler.flush()

    # 外部只读长持句柄(日志查看器形状)= rename 的阻断者
    holder = open(target, 'rb')  # noqa: SIM115 刻意长持:被测对象就是「外部持有者」
    try:
        handler.rolloverAt = int(time.time())  # 强制到点轮转
        handler.doRollover()  # 占用下自愈:copytruncate 归档,不得抛

        archives = [p for p in tmp_path.iterdir() if p.name.startswith('mcp_server.log.2')]
        assert len(archives) == 1, f'自愈应产生恰一个归档: {[p.name for p in tmp_path.iterdir()]}'

        # 轮转后:续写当前文件(中文样本,验证换名后新流编码与连续性)
        tail_line = '轮转后续写:实例配置加载完成'
        logger.info(tail_line)
        for h in logger.handlers:
            h.flush()

        # bytes 级 UTF-8 断言:归档与当前文件都能按 utf-8 严格解码(GBK 混写会炸)
        archived_bytes = archives[0].read_bytes()
        current_bytes = open(target, 'rb').read()  # noqa: SIM115
        archived_text = archived_bytes.decode('utf-8')  # 非 UTF-8 直接 AssertionError
        current_text = current_bytes.decode('utf-8')

        for line in _MIXED_LINES:
            assert line in archived_text, f'归档缺轮转前行: {line!r}'
            assert line not in current_text, f'轮转前行不应留在当前文件: {line!r}'
        assert tail_line in current_text, '续写行应落在轮转后的当前文件'
        assert tail_line not in archived_text, '续写行不应混入归档(copytruncate 竞态窗口外)'
        assert handler.stream is not None, '轮转后 handler 应持有可写流(日志连续)'
    finally:
        holder.close()
        logger.removeHandler(handler)
        handler.close()


def test_stdout_log_copytruncate_rotates_and_continues_utf8(tmp_path) -> None:
    """stdout 兜底日志(copytruncate helper)超阈值轮转:归档/续写/UTF-8 标记行。

    对应 main_server.log 的轮转路径(daemon/GUI 每次 spawn 前调
    ``rotate_large_stdout_log``):多进程 append 共享句柄下不能 rename,
    helper 走复制归档+截断;轮转标记行自身必须 UTF-8 写入。
    """
    from one_dragon.utils.log_utils import rotate_large_stdout_log

    target = tmp_path / 'main_server.log'
    payload = '启动行\n' * 200
    target.write_bytes(payload.encode('utf-8') + b'\xe4\xb8\xad')  # 略超阈值的 UTF-8 字节

    assert rotate_large_stdout_log(target, max_bytes=64, backup_count=2) is True
    archives = sorted(p.name for p in tmp_path.iterdir() if p.name.endswith('.1'))
    assert archives == ['main_server.log.1']
    archived_text = (tmp_path / archives[0]).read_text(encoding='utf-8')
    assert archived_text.startswith('启动行')
    current = target.read_bytes().decode('utf-8')
    assert '已轮转' in current, '截断后应留 UTF-8 轮转标记行'
    assert len(current) < len(archived_text), '当前文件应被截空(仅剩标记行)'

    # 未超阈值:不动文件
    before = target.read_bytes()
    assert rotate_large_stdout_log(target, max_bytes=64) is False
    assert target.read_bytes() == before


def test_default_file_handler_is_utf8(tmp_path) -> None:
    """框架配置出的文件 handler 显式 encoding='utf-8'(编码单一源,防 locale 回潮)。

    落盘指到 tmp_path:别让 pytest 进程持有真实 .log/log.txt 句柄(测试零真实副作用)。
    """
    from one_dragon.utils.log_utils import LoggerConfig, configure_logger
    from one_dragon.utils.log_utils import log as framework_log

    configure_logger(
        framework_log,
        LoggerConfig(log_file_path=str(tmp_path / 'encoding_probe.log'), add_console_handler=False),
    )
    try:
        file_handlers = [
            h for h in framework_log.handlers
            if getattr(h, '_one_dragon_logger_owner', None) == framework_log.name
            and isinstance(h, logging.FileHandler)
        ]
        assert file_handlers, '框架 logger 应有自管文件 handler'
        assert all(h.encoding == 'utf-8' for h in file_handlers), (
            f'文件 handler 必须显式 UTF-8,实得 {[h.encoding for h in file_handlers]}'
        )
    finally:
        for h in list(framework_log.handlers):
            if getattr(h, '_one_dragon_logger_owner', None) == framework_log.name:
                framework_log.removeHandler(h)
                h.close()
