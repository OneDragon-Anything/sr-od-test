"""screen_info 文本 area 的 pc_rect 契约批量审计工具(ADR-0215)。

背景:OCR crop_first 框架默认翻转 True→False 后,文本 area 的 pc_rect 必须
容纳全图 OCR 检测框 ≥70%(以检测框为基准,`ocr_service.get_ocr_result_list`
的重叠过滤),否则 OCR 读到也会被静默过滤(find 返 FALSE 不报错)。
翻转时只校正了 12 处,其余靠本工具全量对拍发现(2026-08-24 一条龙事故:
战斗画面.退出关卡按钮 失配 → 历战余响卡 2 小时,即漏网案例)。

用法(仓库根):
    $env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
    uv run python sr-od-test/tools/audit_screen_rect_contract.py [--verbose]

对拍范围:`sr-od-test/screens/<screen_name>/*.{png,jpg,webp}` fixture ×
同名画面的全部文本 area。复刻运行时 find_area_in_screen 语义:
存在任一 OCR 框同时满足 LCS 匹配 + 重叠>0.7 → OK(运行时命中);
所有 LCS 匹配框均重叠≤0.7 → 失配(运行时静默过滤,需修 rect 或消费点
显式 crop_first=True——图标并框场景,见 ADR-0215 第 3 条)。

输出说明:MISMATCH 行含「位置无关」的跨子屏同名文本误报(短文本如
'确认' 在登录形态/别的子屏命中),按 area/ocr 框中心距离与是否相交
人工判读;`--verbose` 附全部 OK 对。退出码:有失配=1(可挂 CI)。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
# 从 sr-od-test/tools/ 定位仓库根并注入 src 到 sys.path(独立可运行)
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / 'src'))

from one_dragon.base.geometry.rectangle import Rect  # noqa: E402
from one_dragon.utils import cal_utils, cv2_utils, str_utils  # noqa: E402
from one_dragon.utils.i18_utils import gt  # noqa: E402
from sr_od.context.sr_context import SrContext  # noqa: E402

BASE_W, BASE_H = 1920, 1080  # 项目基准:1080p 游戏空间(截图同分辨率则免换算)


def to_1080p(rect: Rect, w: int, h: int) -> Rect:
    """OCR 坐标(截图像素) → 1080p 游戏空间(项目既有前提,硬编码换算)"""
    if (w, h) == (BASE_W, BASE_H):
        return rect
    sx, sy = BASE_W / w, BASE_H / h
    return Rect(
        int(rect.x1 * sx), int(rect.y1 * sy),
        int(rect.x2 * sx), int(rect.y2 * sy),
    )


def center_dist(a: Rect, b: Rect) -> float:
    """两框中心距(用于人工判读失配行是否「位置相关」=真失配)"""
    acx, acy = (a.x1 + a.x2) / 2, (a.y1 + a.y2) / 2
    bcx, bcy = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
    return ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5


def main() -> int:
    verbose = '--verbose' in sys.argv
    screens_dir = REPO_ROOT / 'sr-od-test' / 'screens'

    ctx = SrContext()
    ctx.init_ocr()
    ctx.screen_loader.reload()

    total_pairs = 0
    rows: list[tuple] = []
    seen_screens: set[str] = set()

    for screen_info in ctx.screen_loader.screen_info_list:
        screen_name = screen_info.screen_name
        fixture_dir = screens_dir / screen_name
        if not fixture_dir.exists():
            continue
        images = [p for p in fixture_dir.iterdir()
                  if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
        if not images:
            continue
        text_areas = [a for a in screen_info.area_list if a.text]
        if not text_areas:
            continue
        seen_screens.add(screen_name)

        for img_path in images:
            img = cv2_utils.read_image(str(img_path))
            if img is None:
                print(f'[WARN] 读取失败 {img_path}')
                continue
            h, w = img.shape[:2]
            ocr_list = ctx.ocr_service.get_ocr_result_list(image=img)
            for area in text_areas:
                target = gt(area.text, 'game')
                best: tuple[float, Rect, str] | None = None
                runtime_hit = False
                for ocr in ocr_list:
                    if not str_utils.find_by_lcs(target, ocr.data, percent=area.lcs_percent):
                        continue
                    ocr_rect = to_1080p(ocr.rect, w, h)
                    pct = cal_utils.cal_overlap_percent(ocr_rect, area.rect, base=ocr_rect)
                    if pct > 0.7:
                        runtime_hit = True
                        break
                    if best is None or pct > best[0]:
                        best = (pct, ocr_rect, ocr.data)
                if runtime_hit:
                    total_pairs += 1
                    if verbose:
                        print(f'[OK] {screen_name}.{area.area_name} @ {img_path.name}')
                    continue
                if best is None:
                    continue  # 本 fixture 未读到该文本,无法判
                total_pairs += 1
                pct, ocr_rect, text = best
                rows.append((screen_name, area.area_name, img_path.name,
                             f'{w}x{h}', area.rect, ocr_rect, text, pct))

    print(f'\n===== 对拍完成: 画面数={len(seen_screens)} '
          f'可判对数={total_pairs + len(rows)} 失配数={len(rows)} =====')
    for screen_name, area_name, img, size, area_rect, ocr_rect, text, pct in rows:
        dist = center_dist(area_rect, ocr_rect)
        print(f'[MISMATCH {pct:.2f} dist={dist:.0f}] {screen_name}.{area_name} @ {img} ({size})')
        print(f'    area_rect={[area_rect.x1, area_rect.y1, area_rect.x2, area_rect.y2]}'
              f' ocr_rect={[ocr_rect.x1, ocr_rect.y1, ocr_rect.x2, ocr_rect.y2]} text={text!r}')
    return 1 if rows else 0


if __name__ == '__main__':
    sys.exit(main())
