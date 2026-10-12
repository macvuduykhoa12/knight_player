"""
example_game.py - Ví dụ tối giản: cách ghép knight_player.Player vào một game platform 2D.

Chạy:  python example_game.py
Điều khiển: A/D di chuyển, W/Space nhảy, J chém, K bắn cung, R chơi lại, ESC thoát.

Quái ở đây chỉ là một class giả để minh hoạ "giao diện của quái" mà Player cần:
    .rect, .take_damage(amount, direction), .is_dead
Trong game thật, bạn thay bằng class quái của riêng mình.
"""
import sys

import pygame

from knight_player import Player, PlayerConfig

W, H = 960, 540
LEVEL_W = 2200


class DummyEnemy:
    """Quái mẫu: đi tuần qua lại, có máu, bị hất lùi khi trúng đòn."""

    def __init__(self, x, ground_y, patrol=(0, 0)):
        self.rect = pygame.Rect(x, ground_y - 50, 28, 50)
        self.hp = 4
        self.dir = -1
        self.patrol = patrol
        self.flash = 0

    @property
    def is_dead(self):
        return self.hp <= 0

    def take_damage(self, amount, direction):     # <- Player gọi hàm này khi đánh trúng
        self.hp -= amount
        self.rect.x += direction * 14
        self.flash = 8

    def update(self):
        self.rect.x += self.dir * 1
        if self.rect.x < self.patrol[0] or self.rect.x > self.patrol[1]:
            self.dir *= -1
        self.flash = max(0, self.flash - 1)

    def draw(self, surf, cam_x):
        color = (255, 150, 150) if self.flash else (225, 225, 205)
        pygame.draw.rect(surf, color, self.rect.move(-cam_x, 0))
        bar = self.rect.move(-cam_x, -10)
        pygame.draw.rect(surf, (60, 20, 30), (bar.x, bar.y, 28, 5))
        pygame.draw.rect(surf, (220, 60, 70), (bar.x, bar.y, 28 * max(self.hp, 0) / 4, 5))


def make_level():
    solids = [
        pygame.Rect(0, 480, LEVEL_W, 60),          # mặt đất
        pygame.Rect(-40, -600, 40, 1300),          # tường trái
        pygame.Rect(LEVEL_W, -600, 40, 1300),      # tường phải
        pygame.Rect(300, 390, 200, 20),
        pygame.Rect(620, 310, 180, 20),
        pygame.Rect(900, 390, 200, 20),
        pygame.Rect(1300, 330, 220, 20),
    ]
    enemies = [
        DummyEnemy(600, 480, (500, 800)),
        DummyEnemy(1000, 480, (900, 1200)),
        DummyEnemy(1500, 480, (1400, 1700)),
        DummyEnemy(1350, 330, (1300, 1490)),
    ]
    return solids, enemies


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Knight player - ví dụ")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 22, bold=True)

    solids, enemies = make_level()
    player = Player(80, 420, PlayerConfig())       # chỉnh chỉ số ở PlayerConfig, vd PlayerConfig(max_hp=8)

    # (tuỳ chọn) lắng nghe sự kiện để gắn âm thanh / hiệu ứng
    player.on_event = lambda name, **info: print("event:", name) if name in ("hurt", "died") else None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                solids, enemies = make_level()
                player.respawn(80, 420)
            player.handle_event(event)             # 1) chuyển event cho nhân vật

        for e in enemies:
            e.update()

        # 2) cập nhật nhân vật: truyền phím đang giữ, vật rắn và danh sách quái
        player.update(pygame.key.get_pressed(), solids, enemies)
        enemies = [e for e in enemies if not e.is_dead]

        # 3) quái chạm vào nhân vật -> nhận sát thương (Player tự lo bất tử tạm thời + hất lùi)
        for e in enemies:
            if player.rect.colliderect(e.rect):
                player.take_damage(1, source_x=e.rect.centerx)

        cam_x = max(0, min(LEVEL_W - W, player.rect.centerx - W // 2))

        screen.fill((24, 24, 48))
        for s in solids[:1] + solids[3:]:
            pygame.draw.rect(screen, (72, 66, 84), s.move(-cam_x, 0))
            pygame.draw.rect(screen, (66, 120, 74), (s.x - cam_x, s.y, s.w, 7))
        for e in enemies:
            e.draw(screen, cam_x)
        player.draw(screen, camera=(cam_x, 0))     # 4) vẽ nhân vật + mũi tên

        msg = f"HP: {player.hp}/{player.cfg.max_hp}   Quái còn: {len(enemies)}"
        if player.is_dead:
            msg = "Bạn đã gục ngã - nhấn R để chơi lại"
        elif not enemies:
            msg = "Chiến thắng! - nhấn R để chơi lại"
        screen.blit(font.render(msg, True, (240, 240, 220)), (16, 14))

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
