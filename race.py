import sys
import math
import pygame

# --- Genel ayarlar ---
WIDTH, HEIGHT = 1000, 700
FPS = 60

# Pist sınırları
TRACK_MARGIN_X = 60
TRACK_MARGIN_Y = 50

# Sensör ayarları
SENSOR_ANGLES_DEG = [-60, -30, -10, 0, 10, 30, 60]
SENSOR_MAX_DIST = 300  # piksel


class Car:
    def __init__(self, x, y):
        # Konum
        self.x = x
        self.y = y

        # Gövde yönü (heading) ve ön teker açısı (steering)
        self.angle = 0.0           # radyan
        self.steer_angle = 0.0     # radyan

        # Araç boyutları / geometri (biraz büyüttüm)
        self.body_length = 80.0    # gövde uzunluğu
        self.body_width = 40.0     # gövde genişliği
        self.wheel_base = 52.0     # aks mesafesi
        self.track_width = 32.0    # sağ-sol teker mesafesi

        # Fizik
        self.speed = 0.0
        self.max_speed = 280.0
        self.max_reverse_speed = -120.0

        self.accel = 240.0
        self.brake = 300.0
        self.friction = 120.0

        # Direksiyon parametreleri
        self.max_steer_angle = math.radians(18)      # +/-18°
        self.steer_rate = math.radians(90)           # saniyede max 90° çevrine
        self.steer_return_rate = math.radians(45)    # self-center hızı
        self.steer_return_speed_threshold = 20.0     # bu hızın altı → self-center yok

        # Yaw clamp
        self.max_yaw_rate = math.radians(120)        # rad/s

        # --- Gövde sprite (araba silueti) ---
        w = int(self.body_length)
        h = int(self.body_width)
        self.body_surface = pygame.Surface((w, h), pygame.SRCALPHA)

        # Renkler
        body_color = (40, 80, 160)
        roof_color = (60, 120, 200)
        glass_color = (180, 220, 255)
        outline_color = (20, 20, 20)

        # Dış gövde
        pygame.draw.rect(
            self.body_surface,
            body_color,
            (0, 0, w, h),
            border_radius=10,
        )
        pygame.draw.rect(
            self.body_surface,
            outline_color,
            (0, 0, w, h),
            width=2,
            border_radius=10,
        )

        # Kabin / tavan (ortada küçük dikdörtgen)
        roof_rect = pygame.Rect(w * 0.25, h * 0.15, w * 0.45, h * 0.7)
        pygame.draw.rect(self.body_surface, roof_color, roof_rect, border_radius=8)

        # Cam alanı (kabin içinde)
        glass_rect = roof_rect.inflate(-roof_rect.width * 0.25, -roof_rect.height * 0.25)
        pygame.draw.rect(self.body_surface, glass_color, glass_rect, border_radius=6)

        # Ön farlar (sarı)
        headlight_radius = 4
        front_x = w - 4
        front_y_offset = h * 0.25
        pygame.draw.circle(self.body_surface, (250, 250, 160), (front_x, int(front_y_offset)), headlight_radius)
        pygame.draw.circle(self.body_surface, (250, 250, 160), (front_x, int(h - front_y_offset)), headlight_radius)

        # Arka stoplar (kırmızı)
        rear_x = 4
        pygame.draw.circle(self.body_surface, (220, 60, 60), (rear_x, int(front_y_offset)), headlight_radius)
        pygame.draw.circle(self.body_surface, (220, 60, 60), (rear_x, int(h - front_y_offset)), headlight_radius)

        # --- Teker sprite ---
        # Lastik gibi görünmesi için kalın, kısa dikdörtgen
        self.wheel_length = 18   # eksen boyunca
        self.wheel_width = 8     # eksene dik
        self.wheel_surface = pygame.Surface(
            (self.wheel_length, self.wheel_width),
            pygame.SRCALPHA,
        )
        tire_color = (15, 15, 15)
        rim_color = (180, 180, 180)

        pygame.draw.rect(
            self.wheel_surface,
            tire_color,
            (0, 0, self.wheel_length, self.wheel_width),
            border_radius=3,
        )
        # jant gibi küçük iç dikdörtgen
        pygame.draw.rect(
            self.wheel_surface,
            rim_color,
            (3, 2, self.wheel_length - 6, self.wheel_width - 4),
            border_radius=2,
        )

        # Sensörler
        self.sensor_distances = [SENSOR_MAX_DIST for _ in SENSOR_ANGLES_DEG]
        self.sensor_points = [(self.x, self.y) for _ in SENSOR_ANGLES_DEG]

    # ---------------- Fizik ----------------
    def update(self, dt, steering_input, throttle_input):
        """
        steering_input: -1 (sol) / 0 / +1 (sağ)
        throttle_input: -1 (fren/geri) / 0 / +1 (gaz)
        dt: saniye
        """

        # --- Hız ---
        if throttle_input > 0:  # gaz
            self.speed += self.accel * dt
        elif throttle_input < 0:  # fren / geri
            self.speed -= self.brake * dt
        else:
            if self.speed > 0:
                self.speed -= self.friction * dt
                if self.speed < 0:
                    self.speed = 0.0
            elif self.speed < 0:
                self.speed += self.friction * dt
                if self.speed > 0:
                    self.speed = 0.0

        self.speed = max(self.max_reverse_speed, min(self.max_speed, self.speed))

        # --- Direksiyon / teker açısı ---
        if steering_input != 0:
            # Tuşa basılı iken teker dönsün
            self.steer_angle += steering_input * self.steer_rate * dt
        else:
            # Araç yeterince hızlıysa steer yavaş yavaş normale dönsün
            if abs(self.speed) > self.steer_return_speed_threshold:
                if abs(self.steer_angle) > 1e-4:
                    sign = 1 if self.steer_angle > 0 else -1
                    delta = self.steer_return_rate * dt
                    if abs(self.steer_angle) <= delta:
                        self.steer_angle = 0.0
                    else:
                        self.steer_angle -= sign * delta
            # Hız düşükken direksiyon olduğu gibi kalıyor (gerçekçi)

        self.steer_angle = max(-self.max_steer_angle,
                               min(self.max_steer_angle, self.steer_angle))

        # --- Heading (bicycle model) ---
        if abs(self.speed) > 1.0 and abs(self.steer_angle) > 1e-4:
            curvature = math.tan(self.steer_angle) / self.wheel_base
            angular_velocity = self.speed * curvature
        else:
            angular_velocity = 0.0

        # Yaw clamp
        if angular_velocity > self.max_yaw_rate:
            angular_velocity = self.max_yaw_rate
        if angular_velocity < -self.max_yaw_rate:
            angular_velocity = -self.max_yaw_rate

        self.angle += angular_velocity * dt

        # Açıyı [-pi, pi] aralığında tut
        self.angle = (self.angle + math.pi) % (2 * math.pi) - math.pi

        # --- Konum ---
        dx = math.cos(self.angle) * self.speed * dt
        dy = math.sin(self.angle) * self.speed * dt
        self.x += dx
        self.y += dy

        self.x = max(0, min(WIDTH, self.x))
        self.y = max(0, min(HEIGHT, self.y))

    # ---------------- Sensörler ----------------
    def compute_sensors(self, track_rect):
        distances = []
        points = []

        for rel_deg in SENSOR_ANGLES_DEG:
            ang = self.angle + math.radians(rel_deg)
            step = 4
            d = 0.0
            hit_x = self.x
            hit_y = self.y

            while d < SENSOR_MAX_DIST:
                px = self.x + math.cos(ang) * d
                py = self.y + math.sin(ang) * d

                if not track_rect.collidepoint(px, py):
                    hit_x, hit_y = px, py
                    break

                hit_x, hit_y = px, py
                d += step

            distances.append(min(d, SENSOR_MAX_DIST))
            points.append((hit_x, hit_y))

        self.sensor_distances = distances
        self.sensor_points = points

    # ---------------- RL State ----------------
    def get_state_vector(self):
        norm_sensors = [d / SENSOR_MAX_DIST for d in self.sensor_distances]

        speed_norm = (self.speed - self.max_reverse_speed) / (self.max_speed - self.max_reverse_speed)
        speed_norm = max(0.0, min(1.0, speed_norm))

        steer_norm = self.steer_angle / self.max_steer_angle if self.max_steer_angle > 0 else 0.0
        steer_norm = max(-1.0, min(1.0, steer_norm))

        return norm_sensors + [speed_norm, steer_norm]

    # ---------------- Çizim ----------------
    def draw(self, surface):
        # Gövde
        rotated_body = pygame.transform.rotate(self.body_surface, -math.degrees(self.angle))
        body_rect = rotated_body.get_rect(center=(self.x, self.y))
        surface.blit(rotated_body, body_rect)

        # Teker merkezleri (dünya koordinatında)
        half_wb = self.wheel_base / 2.0
        half_tw = self.track_width / 2.0

        def local_to_world(lx, ly):
            wx = self.x + math.cos(self.angle) * lx - math.sin(self.angle) * ly
            wy = self.y + math.sin(self.angle) * lx + math.cos(self.angle) * ly
            return wx, wy

        # Lokal teker pozisyonları (lx, ly)
        front_right_local = (half_wb, +half_tw)
        front_left_local = (half_wb, -half_tw)
        rear_right_local = (-half_wb, +half_tw)
        rear_left_local = (-half_wb, -half_tw)

        wheels = []

        # Arka tekerler – gövde ile aynı açı
        for lx, ly in (rear_right_local, rear_left_local):
            wx, wy = local_to_world(lx, ly)
            wheels.append((wx, wy, self.angle))

        # Ön tekerler – gövde açısı + steer açısı
        front_angle = self.angle + self.steer_angle
        for lx, ly in (front_right_local, front_left_local):
            wx, wy = local_to_world(lx, ly)
            wheels.append((wx, wy, front_angle))

        for wx, wy, ang in wheels:
            rotated_wheel = pygame.transform.rotate(self.wheel_surface, -math.degrees(ang))
            wheel_rect = rotated_wheel.get_rect(center=(wx, wy))
            surface.blit(rotated_wheel, wheel_rect)

    def draw_sensors(self, surface):
        for (px, py) in self.sensor_points:
            pygame.draw.line(surface, (100, 200, 255), (self.x, self.y), (px, py), 2)
            pygame.draw.circle(surface, (255, 255, 0), (int(px), int(py)), 3)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.setCaption = pygame.display.set_caption
        pygame.display.setCaption("RL Race – Araç Görseli")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.car = Car(WIDTH // 2, HEIGHT // 2)

        self.track_rect = pygame.Rect(
            TRACK_MARGIN_X,
            TRACK_MARGIN_Y,
            WIDTH - 2 * TRACK_MARGIN_X,
            HEIGHT - 2 * TRACK_MARGIN_Y,
        )

        self.running = True

        self.font_small = pygame.font.SysFont(None, 20)
        self.last_reward = 0.0

    def handle_input(self):
        keys = pygame.key.get_pressed()

        steering = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            steering = -1
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            steering = 1

        throttle = 0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            throttle = 1
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            throttle = -1

        return steering, throttle

    def draw_track(self):
        pygame.draw.rect(self.screen, (80, 80, 80), self.track_rect, width=8)

    def draw_hud(self):
        x = 10
        y = 10
        lines = []

        speed_kmh = self.car.speed * 0.10
        heading_deg = math.degrees(self.car.angle)
        steer_deg = math.degrees(self.car.steer_angle)
        steer_norm = self.car.steer_angle / self.car.max_steer_angle if self.car.max_steer_angle > 0 else 0.0

        lines.append("[Vehicle]")
        lines.append(f"Speed px/s : {self.car.speed:7.2f}  (~{speed_kmh:5.1f} km/h)")
        lines.append(f"Heading   : {heading_deg:7.2f} deg")
        lines.append(f"Steer ang.: {steer_deg:7.2f} deg  (norm {steer_norm:+4.2f})")

        lines.append("")
        lines.append("[Sensors]")
        sensor_str = " ".join(f"{d:5.0f}" for d in self.car.sensor_distances)
        lines.append(f"Dist(px): {sensor_str}")

        state_vec = self.car.get_state_vector()
        sensor_vals = state_vec[:-2]
        speed_norm = state_vec[-2]
        steer_norm_state = state_vec[-1]

        lines.append("")
        lines.append("[RL State]")
        sens_str = " ".join(f"{v:4.2f}" for v in sensor_vals)
        lines.append(f"Sensors: {sens_str}")
        lines.append(f"Speed_n: {speed_norm:5.2f}  Steer_n: {steer_norm_state:+5.2f}")

        lines.append("")
        lines.append("[Reward]")
        lines.append(f"Last R: {self.last_reward:+6.3f}")

        for line in lines:
            surf = self.font_small.render(line, True, (230, 230, 230))
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 2

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False

            steering, throttle = self.handle_input()

            self.car.update(dt, steering, throttle)
            self.car.compute_sensors(self.track_rect)

            if self.track_rect.collidepoint(self.car.x, self.car.y):
                self.last_reward = 0.01
            else:
                self.last_reward = -1.0

            self.screen.fill((30, 30, 30))
            self.draw_track()
            self.car.draw(self.screen)
            self.car.draw_sensors(self.screen)
            self.draw_hud()

            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = Game()
    game.run()
