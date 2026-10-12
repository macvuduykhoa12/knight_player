"""
knight_player.py - Nhân vật hiệp sĩ cho game platform 2D (pygame).

Chỉ cần copy file này (và thư mục ``assets/``) vào project của bạn:

    from knight_player import Player, PlayerConfig

    player = Player(100, 300)                       # vị trí xuất hiện (góc trên-trái của hitbox)

    # --- trong vòng lặp game ---
    for event in pygame.event.get():
        player.handle_event(event)                  # nhảy / chém / bắn cung (KEYDOWN)
    hits = player.update(pygame.key.get_pressed(),  # đi trái/phải, trọng lực, va chạm, tấn công
                         solids,                    # list pygame.Rect (hoặc object có .rect): nền, bục, tường
                         enemies)                   # list quái (xem "Giao diện của quái" bên dưới)
    player.draw(screen, camera=(cam_x, 0))          # vẽ hiệp sĩ + mũi tên đang bay

Điều khiển mặc định (đổi trong PlayerConfig):
    A/D hoặc ←/→ : di chuyển        W/↑/Space : nhảy
    J/Z          : chém kiếm        K/X       : bắn cung (giương cung rồi mới thả tên)

Giao diện của quái (enemy) - Player không cần biết quái là class gì, chỉ cần:
    enemy.rect                          pygame.Rect dùng để va chạm
    enemy.take_damage(amount, direction)  (hoặc enemy.hurt(amount, direction)); direction = +1 / -1
                                        là chiều quái bị đẩy lùi (+1: sang phải)
    enemy.is_dead / enemy.dead / enemy.hp <= 0   (tuỳ chọn) quái đã chết thì bị bỏ qua

Quái đánh hiệp sĩ: gọi ``player.take_damage(1, source_x=enemy.rect.centerx)``.

Sự kiện (tuỳ chọn) để gắn âm thanh / hiệu ứng:
    player.on_event = lambda name, **info: ...
    name: "jump", "melee", "bow_draw", "arrow_fired" (arrow=),
          "hit_enemy" (enemy=, damage=, kind="melee"/"arrow"), "hurt" (amount=), "died"

Yêu cầu: pygame >= 2.0
"""
from __future__ import annotations

import math
import os
import warnings
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import pygame

__all__ = ["Player", "PlayerConfig", "Arrow"]
__version__ = "1.0.0"

DEFAULT_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Tên file và kích thước ô (cell) của các sprite sheet
RUN_SHEET = "knight_sheet.png"          # 6 frame 32x32 xếp ngang (chạy/đứng/nhảy)
RUN_CELL = (32, 32)
BOW_SHEET = "knight_bow_sheet.png"      # 8 frame 44x32 xếp ngang (giương cung)
BOW_CELL = (44, 32)
SWORD_IMAGE = "knight_sword.png"        # 1 ảnh 15x15 (cây kiếm)
SWORD_GRIP = (3.5, 11.5)                # điểm tay cầm trong ảnh kiếm gốc (xoay quanh điểm này)
SWORD_TIP = (14.0, 0.5)                 # mũi kiếm trong ảnh kiếm gốc


# =============================================================== cấu hình
@dataclass
class PlayerConfig:
    """Mọi thông số cân bằng game của nhân vật. Chỉnh ở đây, không cần sửa code Player."""

    # --- hitbox (pixel)
    width: int = 30
    height: int = 52

    # --- di chuyển
    speed: float = 4.5                  # tốc độ ngang (px/frame)
    jump_velocity: float = -13.5        # vận tốc nhảy (âm = đi lên)
    gravity: float = 0.6
    max_fall_speed: float = 15.0
    action_speed_factor: float = 0.45   # nhân tốc độ khi đang chém / giương cung

    # --- máu và bị đánh
    max_hp: int = 5
    invulnerable_frames: int = 70       # bất tử sau khi trúng đòn
    stun_frames: int = 14               # choáng, mất điều khiển
    knockback: Tuple[float, float] = (6.0, -6.0)   # (ngang, dọc) khi bị hất lùi

    # --- cận chiến (chém kiếm)
    melee_damage: int = 2
    melee_frames: int = 20              # tổng thời gian một nhát chém
    melee_hit_window: Tuple[int, int] = (4, 14)    # chỉ gây sát thương khi số frame còn lại nằm trong khoảng này
    melee_range: int = 54               # tầm với tính từ mép thân
    melee_overlap: int = 4              # phần hộp đòn chồng vào thân
    melee_height: int = 40
    melee_y_offset: int = 6

    # --- bắn cung
    arrow_damage: int = 1
    arrow_speed: float = 13.0           # mũi tên bay thẳng, không có trọng lực
    arrow_range: float = 1170.0         # quãng đường tối đa (px)
    bow_draw_frames: int = 24           # thời gian giương cung trước khi thả tên
    shoot_cooldown: int = 36            # hồi chiêu, tính từ lúc bắt đầu giương

    # --- phím (hằng số pygame.K_*)
    left_keys: Tuple[int, ...] = (pygame.K_a, pygame.K_LEFT)
    right_keys: Tuple[int, ...] = (pygame.K_d, pygame.K_RIGHT)
    jump_keys: Tuple[int, ...] = (pygame.K_w, pygame.K_UP, pygame.K_SPACE)
    melee_keys: Tuple[int, ...] = (pygame.K_j, pygame.K_z)
    shoot_keys: Tuple[int, ...] = (pygame.K_k, pygame.K_x)

    # --- hình ảnh
    assets_dir: Optional[str] = None    # None = thư mục "assets" cạnh file này
    sprite_scale: int = 2               # phóng to sprite hiệp sĩ
    sword_scale: int = 3                # phóng to ảnh cây kiếm
    run_anim_speed: float = 0.21        # frame hoạt ảnh chạy mỗi tick (~12.5 fps ở 60 FPS)


# ================================================================ tiện ích
def _rect_of(obj) -> pygame.Rect:
    """Nhận pygame.Rect hoặc bất kỳ object nào có thuộc tính .rect."""
    return obj if isinstance(obj, pygame.Rect) else obj.rect


def _is_dead(enemy) -> bool:
    if getattr(enemy, "is_dead", False) or getattr(enemy, "dead", False):
        return True
    hp = getattr(enemy, "hp", None)
    return hp is not None and hp <= 0


# =============================================================== mũi tên
class Arrow:
    """Mũi tên bay thẳng theo chiều ngang, không chịu trọng lực."""

    def __init__(self, x: float, y: float, direction: int, speed: float = 13.0,
                 damage: int = 1, max_range: float = 1170.0):
        self.x = float(x)
        self.y = float(y)
        self.direction = direction
        self.vx = direction * speed
        self.vy = 0.0
        self.damage = damage
        self.max_range = max_range
        self.travelled = 0.0
        self.alive = True
        self.rect = pygame.Rect(0, 0, 22, 6)
        self.rect.center = (round(self.x), round(self.y))

    def update(self, solids: Sequence[pygame.Rect]) -> None:
        self.x += self.vx
        self.y += self.vy
        self.travelled += math.hypot(self.vx, self.vy)
        self.rect.center = (round(self.x), round(self.y))
        if self.travelled >= self.max_range:
            self.alive = False
        for s in solids:
            if self.rect.colliderect(s):
                self.alive = False
                break

    def draw(self, surface: pygame.Surface, cam_x: float = 0, cam_y: float = 0) -> None:
        ang = math.atan2(self.vy, self.vx)
        head = (self.x - cam_x, self.y - cam_y)
        tail = (head[0] - math.cos(ang) * 22, head[1] - math.sin(ang) * 22)
        pygame.draw.line(surface, (150, 105, 55), tail, head, 3)
        pygame.draw.circle(surface, (210, 215, 225), (int(head[0]), int(head[1])), 3)
        pygame.draw.circle(surface, (220, 70, 70), (int(tail[0]), int(tail[1])), 3)


# ============================================================ nạp sprite
def _read_image(path: str) -> Optional[pygame.Surface]:
    if not os.path.exists(path):
        warnings.warn(f"[knight_player] không tìm thấy sprite: {path} - dùng hình vẽ mặc định", stacklevel=3)
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except pygame.error as e:                 # file hỏng, hoặc chưa gọi pygame.display.set_mode()
        warnings.warn(f"[knight_player] không đọc được {path}: {e}", stacklevel=3)
        return None


class _Sprites:
    """Nạp và chuẩn bị ảnh. File nào thiếu thì thuộc tính tương ứng là None -> vẽ bằng code."""

    def __init__(self, assets_dir: str, scale: int, sword_scale: int):
        self.scale = scale
        self.run = self._load_sheet(os.path.join(assets_dir, RUN_SHEET), RUN_CELL, scale)
        self.bow = self._load_sheet(os.path.join(assets_dir, BOW_SHEET), BOW_CELL, scale)
        self.sword, self.sword_reach = self._load_sword(os.path.join(assets_dir, SWORD_IMAGE), sword_scale)

    @staticmethod
    def _load_sheet(path, cell, scale):
        """-> (frames_nhìn_phải, frames_nhìn_trái) hoặc None. Sprite gốc nhìn sang phải."""
        sheet = _read_image(path)
        if sheet is None:
            return None
        cw, ch = cell
        n = sheet.get_width() // cw
        if n == 0:
            return None
        size = (cw * scale, ch * scale)
        right, left = [], []
        for i in range(n):
            frame = pygame.transform.scale(sheet.subsurface((i * cw, 0, cw, ch)), size)  # giữ nét pixel
            right.append(frame)
            left.append(pygame.transform.flip(frame, True, False))
        return right, left

    @staticmethod
    def _load_sword(path, scale):
        """-> ({1: (ảnh, tay_cầm, góc_gốc), -1: ...}, tầm_với) hoặc (None, 48)."""
        img = _read_image(path)
        if img is None:
            return None, 48.0
        big = pygame.transform.scale(img, (img.get_width() * scale, img.get_height() * scale))
        gx, gy = SWORD_GRIP[0] * scale, SWORD_GRIP[1] * scale
        tx, ty = SWORD_TIP[0] * scale, SWORD_TIP[1] * scale
        base = math.degrees(math.atan2(-(ty - gy), tx - gx))   # góc trục kiếm trong ảnh (trục y hướng lên)
        reach = math.hypot(tx - gx, ty - gy)                   # từ tay cầm tới mũi kiếm
        right = (big, (gx, gy), base)
        left = (pygame.transform.flip(big, True, False), (big.get_width() - gx, gy), 180 - base)
        return {1: right, -1: left}, reach


_SPRITE_CACHE: Dict[tuple, _Sprites] = {}


def _get_sprites(cfg: PlayerConfig) -> _Sprites:
    assets = cfg.assets_dir or DEFAULT_ASSETS_DIR
    key = (assets, cfg.sprite_scale, cfg.sword_scale)
    if key not in _SPRITE_CACHE:
        _SPRITE_CACHE[key] = _Sprites(assets, cfg.sprite_scale, cfg.sword_scale)
    return _SPRITE_CACHE[key]


# ================================================================ nhân vật
class Player:
    """Hiệp sĩ: di chuyển, nhảy, chém kiếm, bắn cung, nhận sát thương."""

    def __init__(self, x: float, y: float, config: Optional[PlayerConfig] = None):
        self.cfg = config or PlayerConfig()
        c = self.cfg

        self.rect = pygame.Rect(int(x), int(y), c.width, c.height)
        self.x = float(x)               # vị trí thật (số thực); rect chỉ là bản làm tròn
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.hit_wall = False

        self.hp = c.max_hp
        self.facing = 1                 # 1 = phải, -1 = trái
        self.invuln = 0                 # frame bất tử còn lại
        self.stun = 0                   # frame choáng còn lại
        self.melee_t = 0                # frame còn lại của nhát chém (0 = không chém)
        self.shoot_cd = 0
        self.bow_t = 0                  # frame còn lại của lúc giương cung
        self.bow_pending = False
        self.hit_ids: set = set()       # quái đã trúng nhát chém hiện tại
        self.anim = 0.0                 # bộ đếm hoạt ảnh chạy
        self.arrows: List[Arrow] = []

        self.on_event: Optional[Callable[..., None]] = None

        # vị trí mũi tên rời cung, tính theo độ phóng sprite (khớp đầu mũi tên trong sprite bắn cung)
        self._arrow_offset = (round(15 * c.sprite_scale), round(10.5 * c.sprite_scale))

    # ------------------------------------------------------------ trạng thái
    @property
    def is_dead(self) -> bool:
        return self.hp <= 0

    @property
    def melee_active(self) -> bool:
        lo, hi = self.cfg.melee_hit_window
        return lo <= self.melee_t <= hi

    def respawn(self, x: float, y: float) -> None:
        """Đặt lại nhân vật (hồi đầy máu, xoá mũi tên) - dùng khi chơi lại / sang màn mới."""
        c = self.cfg
        self.rect.topleft = (int(x), int(y))
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.hp = c.max_hp
        self.facing = 1
        self.invuln = self.stun = self.melee_t = self.shoot_cd = self.bow_t = 0
        self.bow_pending = False
        self.hit_ids = set()
        self.arrows.clear()

    def _emit(self, name: str, **info) -> None:
        if self.on_event:
            self.on_event(name, **info)

    # ------------------------------------------------------------ điều khiển
    def handle_event(self, event: pygame.event.Event) -> None:
        """Gọi với mỗi event của pygame. Xử lý các phím bấm một lần: nhảy, chém, bắn."""
        if event.type != pygame.KEYDOWN:
            return
        c = self.cfg
        if event.key in c.jump_keys:
            self.jump()
        elif event.key in c.melee_keys:
            self.melee()
        elif event.key in c.shoot_keys:
            self.shoot()

    def jump(self) -> bool:
        if self.on_ground and self.stun == 0 and not self.is_dead:
            self.vy = self.cfg.jump_velocity
            self._emit("jump")
            return True
        return False

    def melee(self) -> bool:
        """Chém kiếm (đánh thường)."""
        if self.melee_t == 0 and self.bow_t == 0 and self.stun == 0 and not self.is_dead:
            self.melee_t = self.cfg.melee_frames
            self.hit_ids = set()
            self._emit("melee")
            return True
        return False

    def shoot(self) -> bool:
        """Bắt đầu giương cung; mũi tên chỉ rời cung khi giương xong."""
        if (self.shoot_cd == 0 and self.melee_t == 0 and self.bow_t == 0
                and self.stun == 0 and not self.is_dead):
            self.shoot_cd = self.cfg.shoot_cooldown
            self.bow_t = self.cfg.bow_draw_frames
            self.bow_pending = True
            self._emit("bow_draw")
            return True
        return False

    def take_damage(self, amount: int = 1, source_x: Optional[float] = None) -> bool:
        """Nhận sát thương. ``source_x``: toạ độ x của kẻ đánh (để hất lùi ra xa).
        Trả về True nếu đòn có hiệu lực (False khi đang bất tử hoặc đã chết)."""
        c = self.cfg
        if self.invuln > 0 or self.is_dead:
            return False
        self.hp = max(0, self.hp - amount)
        self.invuln = c.invulnerable_frames
        self.stun = c.stun_frames
        if source_x is None:
            direction = -self.facing
        else:
            direction = 1 if self.rect.centerx >= source_x else -1
        self.vx = direction * c.knockback[0]
        self.vy = c.knockback[1]
        self.melee_t = 0                 # bị đánh thì huỷ chém / giương cung đang thực hiện
        self.bow_t = 0
        self.bow_pending = False
        self._emit("hurt", amount=amount, direction=direction)
        if self.is_dead:
            self._emit("died")
        return True

    # ------------------------------------------------------------ cập nhật
    def update(self, keys=None, solids: Iterable = (), enemies: Iterable = (),
               move: Optional[int] = None) -> List[Tuple[object, int, str]]:
        """Cập nhật một frame.

        keys    : kết quả pygame.key.get_pressed() (None = không có input)
        solids  : các vật rắn để đứng/va chạm (pygame.Rect hoặc object có .rect)
        enemies : các quái có thể bị trúng kiếm/tên
        move    : ghi đè hướng đi (-1/0/1), dùng cho tay cầm game hoặc AI; None = đọc từ keys
        Trả về danh sách (quái, sát_thương, "melee"/"arrow") các đòn trúng trong frame này.
        """
        c = self.cfg
        solid_rects = [_rect_of(s) for s in solids]
        enemies = list(enemies)

        for attr in ("invuln", "melee_t", "shoot_cd", "bow_t"):
            v = getattr(self, attr)
            if v > 0:
                setattr(self, attr, v - 1)

        if self.bow_pending and self.bow_t == 0:       # giương xong -> thả tên
            self.bow_pending = False
            self._release_arrow()

        if self.stun > 0:                              # đang bị hất lùi: mất điều khiển
            self.stun -= 1
            self.vx *= 0.9
        elif self.is_dead:
            self.vx *= 0.8
        else:
            if move is None:
                move = self._read_move(keys)
            acting = self.melee_t > 0 or self.bow_t > 0
            speed = c.speed * (c.action_speed_factor if acting else 1.0)
            self.vx = move * speed
            if move and not acting:                    # không đổi hướng giữa lúc chém / giương cung
                self.facing = 1 if move > 0 else -1

        self._physics(solid_rects)
        if abs(self.vx) > 0.5 and self.on_ground:
            self.anim += c.run_anim_speed

        hits = self._melee_hits(enemies)
        hits += self._update_arrows(solid_rects, enemies)
        return hits

    def _read_move(self, keys) -> int:
        if keys is None:
            return 0
        c = self.cfg
        right = any(keys[k] for k in c.right_keys)
        left = any(keys[k] for k in c.left_keys)
        return int(right) - int(left)

    def _physics(self, solids: Sequence[pygame.Rect]) -> None:
        """Di chuyển và va chạm: xử lý từng trục riêng để biết chính xác đụng từ phía nào."""
        c = self.cfg
        self.hit_wall = False

        self.x += self.vx
        self.rect.x = round(self.x)
        for p in solids:
            if self.rect.colliderect(p):
                if self.vx > 0:
                    self.rect.right = p.left
                elif self.vx < 0:
                    self.rect.left = p.right
                self.x = self.rect.x
                self.hit_wall = True

        self.vy = min(self.vy + c.gravity, c.max_fall_speed)
        self.y += self.vy
        self.rect.y = round(self.y)
        self.on_ground = False
        for p in solids:
            if self.rect.colliderect(p):
                if self.vy > 0:
                    self.rect.bottom = p.top
                    self.on_ground = True
                elif self.vy < 0:
                    self.rect.top = p.bottom
                self.y = self.rect.y
                self.vy = 0

    # ------------------------------------------------------------ tấn công
    def melee_box(self) -> pygame.Rect:
        """Vùng trúng đòn của nhát chém (phía trước mặt)."""
        c = self.cfg
        w = c.melee_range + c.melee_overlap
        top = self.rect.y + c.melee_y_offset
        if self.facing > 0:
            return pygame.Rect(self.rect.right - c.melee_overlap, top, w, c.melee_height)
        return pygame.Rect(self.rect.left - c.melee_range, top, w, c.melee_height)

    def _damage_enemy(self, enemy, amount: int, direction: int, kind: str) -> None:
        fn = getattr(enemy, "take_damage", None) or getattr(enemy, "hurt", None)
        if fn is None:
            raise TypeError(f"{type(enemy).__name__} cần có phương thức take_damage(amount, direction)")
        fn(amount, direction)
        self._emit("hit_enemy", enemy=enemy, damage=amount, kind=kind)

    def _melee_hits(self, enemies) -> list:
        hits = []
        if not self.melee_active:
            return hits
        box = self.melee_box()
        for e in enemies:
            if id(e) in self.hit_ids or _is_dead(e):
                continue
            if box.colliderect(_rect_of(e)):
                self.hit_ids.add(id(e))              # mỗi nhát chém chỉ trúng một quái một lần
                self._damage_enemy(e, self.cfg.melee_damage, self.facing, "melee")
                hits.append((e, self.cfg.melee_damage, "melee"))
        return hits

    def _release_arrow(self) -> None:
        c = self.cfg
        ox, oy = self._arrow_offset
        arrow = Arrow(self.rect.centerx + self.facing * ox, self.rect.bottom - oy, self.facing,
                      speed=c.arrow_speed, damage=c.arrow_damage, max_range=c.arrow_range)
        self.arrows.append(arrow)
        self._emit("arrow_fired", arrow=arrow)

    def _update_arrows(self, solids, enemies) -> list:
        hits = []
        for a in self.arrows:
            a.update(solids)
            if not a.alive:
                continue
            for e in enemies:
                if _is_dead(e):
                    continue
                if a.rect.colliderect(_rect_of(e)):
                    self._damage_enemy(e, a.damage, a.direction, "arrow")
                    hits.append((e, a.damage, "arrow"))
                    a.alive = False
                    break
        self.arrows = [a for a in self.arrows if a.alive]
        return hits

    # ------------------------------------------------------------ vẽ
    def draw(self, surface: pygame.Surface, camera=(0, 0)) -> None:
        """Vẽ mũi tên và hiệp sĩ. ``camera``: (x, y) góc trên-trái của camera, hoặc một số (chỉ x)."""
        cam_x, cam_y = (camera, 0) if isinstance(camera, (int, float)) else camera
        for a in self.arrows:
            a.draw(surface, cam_x, cam_y)
        self._draw_knight(surface, cam_x, cam_y)

    def _draw_knight(self, surface, cam_x, cam_y) -> None:
        if self.invuln > 0 and (self.invuln // 4) % 2 == 0:
            return                                   # nhấp nháy khi đang bất tử
        c = self.cfg
        sp = _get_sprites(c)
        r = self.rect.move(-cam_x, -cam_y)
        d = self.facing
        cx = r.centerx

        if sp.run:
            right, left = sp.run
            frames = right if d > 0 else left        # sprite gốc nhìn phải, lật khi nhìn trái
            half = RUN_CELL[0] * c.sprite_scale // 2
            if self.bow_t > 0 and sp.bow:            # đang giương cung: phát hoạt ảnh bắn cung
                bright, bleft = sp.bow
                n = len(bright)
                elapsed = c.bow_draw_frames - self.bow_t
                idx = max(0, min(n - 1, int(elapsed * n / c.bow_draw_frames)))
                if d > 0:   # ô cung rộng hơn ô chạy: canh theo cạnh để thân hiệp sĩ trùng nhau
                    img = bright[idx]
                    surface.blit(img, img.get_rect(bottomleft=(cx - half, r.bottom)))
                else:
                    img = bleft[idx]
                    surface.blit(img, img.get_rect(bottomright=(cx + half, r.bottom)))
            else:
                if not self.on_ground:
                    idx = min(1, len(frames) - 1)    # đang ở trên không
                elif abs(self.vx) > 0.5:
                    idx = int(self.anim) % len(frames)   # đang chạy
                else:
                    idx = 0                          # đứng yên
                img = frames[idx]
                surface.blit(img, img.get_rect(midbottom=r.midbottom))   # chân chạm đáy hitbox
            pivot = (cx + d * 7 * c.sprite_scale, r.bottom - 11 * c.sprite_scale)   # tay cầm vũ khí
        else:
            self._draw_fallback_body(surface, r)
            pivot = (cx + d * 8, r.y + 26)

        # kiếm khi chém
        if self.melee_t > 0:
            t = 1 - self.melee_t / c.melee_frames
            ang = math.radians(-85 + 140 * t)        # góc vung: từ trên cao xuống phía trước
            reach = sp.sword_reach
            if self.melee_active:                    # vệt chém
                for k in range(1, 4):
                    a2 = ang - math.radians(14 * k)
                    t2 = (pivot[0] + d * math.cos(a2) * reach, pivot[1] + math.sin(a2) * reach)
                    pygame.draw.line(surface, (200, 220, 255), pivot, t2, 2)
            if sp.sword:
                self._blit_sword(surface, sp, pivot, ang)
            else:                                    # không có ảnh kiếm: vẽ bằng nét
                tip = (pivot[0] + d * math.cos(ang) * reach, pivot[1] + math.sin(ang) * reach)
                pygame.draw.line(surface, (225, 230, 245), pivot, tip, 5)
                pygame.draw.circle(surface, (255, 255, 255), (int(tip[0]), int(tip[1])), 3)
                pygame.draw.circle(surface, (200, 160, 60), (int(pivot[0]), int(pivot[1])), 4)
        elif not sp.run:                             # kiếm đeo bên hông (chỉ với hình vẽ mặc định)
            tip = (pivot[0] + d * 6, pivot[1] + 20)
            pygame.draw.line(surface, (200, 205, 220), pivot, tip, 4)
            pygame.draw.circle(surface, (200, 160, 60), (int(pivot[0]), int(pivot[1])), 4)

        # cung vẽ bằng nét (chỉ khi không có sprite bắn cung)
        if self.bow_t > 0 and not sp.bow:
            bx, by = cx + d * 18, pivot[1]
            box = pygame.Rect(bx - 10, by - 22, 20, 44)
            if d > 0:
                pygame.draw.arc(surface, (140, 90, 40), box, -math.pi / 2, math.pi / 2, 4)
            else:
                pygame.draw.arc(surface, (140, 90, 40), box, math.pi / 2, 3 * math.pi / 2, 4)
            pygame.draw.line(surface, (230, 230, 230), (bx, by - 22), (bx, by + 22), 1)

    def _blit_sword(self, surface, sp: _Sprites, pivot, ang: float) -> None:
        """Vẽ ảnh kiếm xoay quanh tay cầm sao cho mũi kiếm chỉ đúng hướng vung."""
        d = self.facing
        img, grip, base = sp.sword[d]
        want = math.degrees(math.atan2(-math.sin(ang), d * math.cos(ang)))   # hướng cần chỉ tới
        rot = want - base                                                    # xoay ngược chiều kim đồng hồ
        rotated = pygame.transform.rotate(img, rot)
        offset = pygame.math.Vector2(grip) - (img.get_width() / 2, img.get_height() / 2)
        center = pygame.math.Vector2(pivot) - offset.rotate(-rot)            # đặt tay cầm đúng vào pivot
        surface.blit(rotated, rotated.get_rect(center=(round(center.x), round(center.y))))

    def _draw_fallback_body(self, surface, r: pygame.Rect) -> None:
        """Hình vẽ bằng code, dùng khi thiếu file sprite."""
        d = self.facing
        cx = r.centerx
        swing = math.sin(self.anim) * 5 if (abs(self.vx) > 0.5 and self.on_ground) else 0

        pygame.draw.rect(surface, (50, 80, 160), (cx - d * 16 - 5, r.y + 18, 10, 22), border_radius=3)   # khiên
        pygame.draw.rect(surface, (70, 72, 92), (cx - 9 + swing, r.y + 40, 8, 12))                       # chân
        pygame.draw.rect(surface, (70, 72, 92), (cx + 1 - swing, r.y + 40, 8, 12))
        pygame.draw.rect(surface, (150, 160, 185), (r.x + 3, r.y + 18, 24, 24), border_radius=4)         # thân giáp
        pygame.draw.rect(surface, (190, 200, 220), (r.x + 3, r.y + 18, 24, 6), border_radius=3)
        pygame.draw.rect(surface, (120, 80, 40), (r.x + 3, r.y + 34, 24, 4))
        pygame.draw.circle(surface, (165, 175, 200), (cx, r.y + 12), 12)                                 # mũ giáp
        pygame.draw.rect(surface, (25, 25, 40), (cx + d * 2 - 6, r.y + 9, 12, 4))
        pygame.draw.polygon(surface, (200, 40, 50), [                                                    # lông mũ
            (cx - d * 2, r.y), (cx - d * 14, r.y + 8 + swing * 0.3), (cx - d * 4, r.y + 6)])
