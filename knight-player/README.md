# Knight Player - nhân vật hiệp sĩ cho game platform 2D (pygame)

Module nhân vật độc lập cho game platform 2D đánh quái. Chỉ cần copy `knight_player.py`
và thư mục `assets/` vào project là dùng được; không phụ thuộc vào code game khác.

**Cơ chế**
- Di chuyển trái/phải, nhảy, trọng lực, va chạm với bục và tường (xử lý từng trục riêng).
- **Đánh thường:** chém kiếm (cận chiến, mỗi nhát chỉ trúng mỗi quái một lần, kiếm xoay theo đường vung).
- **Kỹ năng:** bắn cung (giương cung 8 frame rồi mới thả tên; tên bay thẳng, không có trọng lực).
- Nhận sát thương: mất máu, choáng, bị hất lùi, bất tử tạm thời (nhấp nháy), huỷ cú bắn đang giương.
- Hoạt ảnh sprite (đứng/chạy/nhảy/bắn cung), tự lật hướng. Thiếu file ảnh thì tự vẽ hình mặc định bằng code.

## Cài đặt

```bash
pip install -r requirements.txt
python example_game.py      # chạy thử ví dụ
```

Trong project của bạn: copy `knight_player.py` + `assets/` vào cùng thư mục với code game.

## Dùng nhanh

```python
import pygame
from knight_player import Player, PlayerConfig

pygame.init()
screen = pygame.display.set_mode((960, 540))        # phải gọi trước khi vẽ (cần để nạp ảnh)

player = Player(100, 300, PlayerConfig())           # (x, y) là góc trên-trái của hitbox

while running:
    for event in pygame.event.get():
        player.handle_event(event)                  # nhảy / chém / bắn

    hits = player.update(pygame.key.get_pressed(), solids, enemies)

    for enemy in enemies:                           # quái chạm nhân vật -> mất máu
        if player.rect.colliderect(enemy.rect):
            player.take_damage(1, source_x=enemy.rect.centerx)

    player.draw(screen, camera=(cam_x, 0))
```

| Tham số | Ý nghĩa |
|---|---|
| `solids` | list `pygame.Rect` (hoặc object có `.rect`): mặt đất, bục, tường |
| `enemies` | list quái có thể bị trúng kiếm / tên |
| `hits` | list `(quái, sát_thương, "melee" / "arrow")` các đòn trúng trong frame đó |

Xem `example_game.py` để có một vòng lặp hoàn chỉnh (camera, quái mẫu, chơi lại).

## Điều khiển mặc định

| Phím | Hành động |
|---|---|
| A / D hoặc ← / → | Di chuyển |
| W / ↑ / Space | Nhảy |
| J / Z | Chém kiếm |
| K / X | Bắn cung |

Đổi phím trong `PlayerConfig` (`left_keys`, `right_keys`, `jump_keys`, `melee_keys`, `shoot_keys`).
Muốn dùng tay cầm hoặc AI: gọi trực tiếp `player.jump()`, `player.melee()`, `player.shoot()`
và truyền `move=-1/0/1` vào `player.update(...)`.

## Giao diện của quái

`Player` không cần biết quái là class gì. Quái chỉ cần:

```python
class Enemy:
    rect: pygame.Rect                              # để va chạm
    def take_damage(self, amount, direction): ...  # hoặc hurt(amount, direction); direction = +1 / -1 (chiều bị đẩy)
    # tuỳ chọn: is_dead / dead / hp <= 0 -> quái đã chết sẽ bị bỏ qua
```

## Cân bằng game: PlayerConfig

Mọi thông số nằm trong `PlayerConfig`, ví dụ:

```python
cfg = PlayerConfig(
    max_hp=8,
    speed=5.0,
    melee_damage=3,
    arrow_damage=2,
    bow_draw_frames=16,       # giương cung nhanh hơn
    shoot_cooldown=30,
)
player = Player(100, 300, cfg)
```

Các nhóm: hitbox, di chuyển, máu/bị đánh, cận chiến, cung, phím, hình ảnh
(`assets_dir`, `sprite_scale`, `sword_scale`). Xem chú thích từng trường trong `knight_player.py`.

## Sự kiện (âm thanh, hiệu ứng)

```python
def on_player_event(name, **info):
    if name == "hit_enemy":      # info: enemy, damage, kind ("melee" / "arrow")
        spawn_particles(info["enemy"].rect.center)
    elif name == "hurt":         # info: amount, direction
        shake_screen()

player.on_event = on_player_event
```

Tên sự kiện: `jump`, `melee`, `bow_draw`, `arrow_fired`, `hit_enemy`, `hurt`, `died`.

## Thuộc tính hữu ích

`player.hp`, `player.is_dead`, `player.rect`, `player.facing` (1 / -1), `player.on_ground`,
`player.arrows`, `player.invuln`, `player.respawn(x, y)` để đặt lại khi chơi lại / sang màn mới.

## Sprite (`assets/`)

| File | Nội dung |
|---|---|
| `knight_sheet.png` | 6 frame 32x32 xếp ngang: đứng / chạy / nhảy (sprite nhìn sang phải) |
| `knight_bow_sheet.png` | 8 frame 44x32 xếp ngang: hoạt ảnh giương cung |
| `knight_sword.png` | cây kiếm 15x15 (mũi kiếm chếch lên bên phải) |

Muốn thay hình: giữ nguyên tên file và kích thước ô (hoặc sửa hằng số `RUN_CELL`, `BOW_CELL`,
`SWORD_GRIP`, `SWORD_TIP` ở đầu `knight_player.py`). Hộp va chạm độc lập với sprite, chỉnh bằng
`PlayerConfig.width / height`.

## Test

```bash
pip install pytest
python -m pytest -q
```

Các test kiểm tra logic (rơi xuống đất, nhảy, va tường, chém trúng một lần, tên bay thẳng,
bất tử sau khi bị đánh, huỷ giương cung khi bị đánh...) và không cần mở cửa sổ game.
