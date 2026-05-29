import os
import threading
import time
import socket

from kivy.config import Config
Config.set('graphics', 'width', '400')
Config.set('graphics', 'height', '650')
Config.set('graphics', 'resizable', '0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.graphics import RoundedRectangle, Color, Line, Rotate, PushMatrix, PopMatrix

# Темный фон
Window.clearcolor = get_color_from_hex("#121212")

HOSTS = ["vk.com", "yandex.ru", "google.com", "telegram.org", "instagram.com", "habr.com"]
TIMEOUT_SEC = 3 # Уменьшен таймаут для непрерывного мониторинга

class CircularSpinner(Widget):
    """Кастомный виджет вращающегося спиннера."""
    def __init__(self, color_hex="#03DAC6", line_width=2, **kwargs):
        super().__init__(**kwargs)
        self.angle = 0
        self.color_hex = color_hex
        self.line_width = line_width
        with self.canvas:
            PushMatrix()
            self.rot = Rotate(angle=self.angle, origin=self.center)
            Color(rgba=get_color_from_hex(self.color_hex))
            self.arc = Line(circle=(self.center_x, self.center_y, 10, 0, 270), width=self.line_width)
            PopMatrix()
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.event = None
        
    def start(self):
        if not self.event:
            self.event = Clock.schedule_interval(self.update_angle, 1/60)
            
    def stop(self):
        if self.event:
            self.event.cancel()
            self.event = None

    def update_canvas(self, *args):
        self.rot.origin = self.center
        radius = min(self.width, self.height) / 2 - self.line_width
        self.arc.circle = (self.center_x, self.center_y, radius, 0, 270)

    def update_angle(self, dt):
        self.angle -= 10
        self.rot.angle = self.angle


class RoundedButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0,0,0,0)
        self.background_normal = ''
        self.bg_color = get_color_from_hex("#1E88E5")
        self.disabled_color = get_color_from_hex("#424242")
        
        with self.canvas.before:
            self.color_instruction = Color(rgba=self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self.update_rect, size=self.update_rect, state=self.on_state_change, disabled=self.on_disabled_change)

    def set_bg_color(self, hex_color):
        self.bg_color = get_color_from_hex(hex_color)
        if not self.disabled and self.state != 'down':
            self.color_instruction.rgba = self.bg_color

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_state_change(self, instance, value):
        if self.disabled:
            return
        if value == 'down':
            # Слегка затемняем цвет при нажатии
            r, g, b, a = self.bg_color
            self.color_instruction.rgba = (max(0, r-0.2), max(0, g-0.2), max(0, b-0.2), a)
        else:
            self.color_instruction.rgba = self.bg_color

    def on_disabled_change(self, instance, value):
        if value:
            self.color_instruction.rgba = self.disabled_color
        else:
            self.color_instruction.rgba = self.bg_color


class PingApp(App):
    def build(self):
        self.title = "Пинг Тест"
        self.running_pings = {}
        self.host_labels = {}
        self.is_monitoring = False
        self.monitor_event = None
        self.ping_history = {}
        self.active_threads = {}
        
        self.root = BoxLayout(orientation='vertical', padding=30, spacing=20)
        
        title_label = Label(
            text="Пинг Тест", 
            font_size=36, 
            bold=True, 
            size_hint_y=None, 
            height=60, 
            color=get_color_from_hex("#FFFFFF")
        )
        self.root.add_widget(title_label)
        
        self.results_grid = GridLayout(cols=2, spacing=15, size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        
        for host in HOSTS:
            self.add_host_ui(host)
            
        self.root.add_widget(self.results_grid)
        
        # Пустое пространство
        self.root.add_widget(Label(size_hint_y=1))
        
        # Поле "Свой ресурс"
        custom_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=15)
        lbl_custom = Label(
            text="Свой ресурс:", 
            size_hint_x=0.3, 
            font_size=16, 
            halign="left",
            valign="middle",
            color=get_color_from_hex("#B0B0B0")
        )
        lbl_custom.bind(size=lbl_custom.setter('text_size'))
        
        self.custom_input = TextInput(
            multiline=False, 
            size_hint_x=0.55, 
            font_size=18, 
            background_color=get_color_from_hex("#2C2C2C"), 
            foreground_color=get_color_from_hex("#FFFFFF"), 
            cursor_color=get_color_from_hex("#FFFFFF"),
            padding=[10, 10, 10, 10],
            background_normal='',
            background_active='',
            hint_text='example.com'
        )
        self.custom_input.bind(on_text_validate=self.add_custom_host) # Добавление по Enter
        
        self.add_btn = RoundedButton(
            text="+", 
            size_hint_x=0.15, 
            font_size=24, 
            bold=True, 
            color=get_color_from_hex("#FFFFFF")
        )
        self.add_btn.bind(on_press=self.add_custom_host)
        
        custom_layout.add_widget(lbl_custom)
        custom_layout.add_widget(self.custom_input)
        custom_layout.add_widget(self.add_btn)
        self.root.add_widget(custom_layout)
        
        # Контейнер для кнопки старта/стопа
        self.btn_layout = FloatLayout(size_hint_y=None, height=55)
        self.ping_btn = RoundedButton(
            text="Start Ping", 
            font_size=20, 
            bold=True, 
            color=get_color_from_hex("#FFFFFF"),
            size_hint=(1, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        self.ping_btn.bind(on_press=self.toggle_monitoring)
        self.btn_layout.add_widget(self.ping_btn)
        
        self.root.add_widget(self.btn_layout)
        
        return self.root

    def add_host_ui(self, host):
        # Левая часть: Иконка + Имя
        left_box = BoxLayout(orientation='horizontal', size_hint_x=0.6, spacing=10, size_hint_y=None, height=40)
        
        icon_path = f"assets/{host}.png"
        if not os.path.exists(icon_path):
            icon_path = "assets/default.png"
            
        if os.path.exists(icon_path):
            icon = Image(source=icon_path, size_hint=(None, None), size=(24, 24))
            icon.pos_hint = {'center_y': 0.5}
        else:
            icon = Widget(size_hint=(None, None), size=(24, 24))
            
        left_box.add_widget(icon)
        
        lbl_name = Label(
            text=host, 
            font_size=18, 
            halign="left", 
            valign="middle",
            color=get_color_from_hex("#E0E0E0")
        )
        lbl_name.bind(size=lbl_name.setter('text_size'))
        left_box.add_widget(lbl_name)
        
        # Правая часть: Контейнер для результата или спиннера
        right_box = AnchorLayout(anchor_x='right', anchor_y='center', size_hint_x=0.4, size_hint_y=None, height=40)
        
        lbl_result = Label(
            text="-", 
            font_size=18, 
            bold=True, 
            color=get_color_from_hex("#757575"),
            halign="right",
            valign="middle"
        )
        lbl_result.bind(size=lbl_result.setter('text_size'))
        
        right_box.add_widget(lbl_result)
        
        self.results_grid.add_widget(left_box)
        self.results_grid.add_widget(right_box)
        
        self.host_labels[host] = {'container': right_box, 'label': lbl_result, 'spinner': None}

    def set_host_loading(self, host, is_loading):
        """Включает или выключает круговой спиннер для конкретного хоста."""
        if host not in self.host_labels:
            return
            
        data = self.host_labels[host]
        container = data['container']
        
        if is_loading:
            if not data['spinner']:
                data['spinner'] = CircularSpinner(size_hint=(None, None), size=(20, 20), color_hex="#03DAC6")
            container.clear_widgets()
            container.add_widget(data['spinner'])
            data['spinner'].start()
        else:
            if data['spinner']:
                data['spinner'].stop()
            container.clear_widgets()
            container.add_widget(data['label'])

    def add_custom_host(self, instance=None):
        """Добавляет кастомный хост из текстового поля и сразу начинает пинг, если мониторинг активен."""
        custom_host = self.custom_input.text.strip()
        if not custom_host:
            return
            
        custom_host = custom_host.replace("http://", "").replace("https://", "").split("/")[0]
        
        if custom_host in self.host_labels:
            self.custom_input.text = ""
            return
            
        self.add_host_ui(custom_host)
        
        if self.is_monitoring:
            # Инициализируем переменные для нового хоста и сразу включаем его в мониторинг
            self.running_pings[custom_host] = True
            self.ping_history[custom_host] = []
            self.active_threads[custom_host] = False
            
            # Обновляем UI
            self.host_labels[custom_host]['label'].color = get_color_from_hex("#03DAC6")
            self.host_labels[custom_host]['label'].text = "-"
            self.set_host_loading(custom_host, True)
            
        self.custom_input.text = ""

    def toggle_monitoring(self, instance):
        # Если в поле что-то введено, сначала добавляем это
        if self.custom_input.text.strip():
            self.add_custom_host()
            
        if self.is_monitoring:
            # Остановить мониторинг
            self.is_monitoring = False
            self.ping_btn.text = "Start Ping"
            self.ping_btn.set_bg_color("#1E88E5") # Синий
            
            if self.monitor_event:
                self.monitor_event.cancel()
                self.monitor_event = None
                
            # Убираем все спиннеры, если где-то остались
            for host in self.running_pings.keys():
                self.set_host_loading(host, False)
            return

        # Начать мониторинг для всех добавленных хостов
        self.is_monitoring = True
        self.ping_btn.text = "Stop Ping"
        self.ping_btn.set_bg_color("#CF6679") # Красный
        
        hosts_to_ping = list(self.host_labels.keys())
        self.running_pings = {host: True for host in hosts_to_ping}
        self.ping_history = {host: [] for host in hosts_to_ping}
        self.active_threads = {host: False for host in hosts_to_ping}
        
        for host in hosts_to_ping:
             self.host_labels[host]['label'].color = get_color_from_hex("#03DAC6")
             self.host_labels[host]['label'].text = "-"
             self.set_host_loading(host, True) # Показываем спиннер до первого ответа
             
        # Запускаем пинги сразу и затем каждую секунду
        self.monitor_tick(0)
        if not self.monitor_event:
            self.monitor_event = Clock.schedule_interval(self.monitor_tick, 1.0)

    def monitor_tick(self, dt):
        for host in self.running_pings.keys():
            # Запускаем новый пинг, только если предыдущий для этого хоста уже завершился
            if not self.active_threads.get(host, False):
                self.active_threads[host] = True
                threading.Thread(target=self.tcp_ping_host, args=(host,), daemon=True).start()

    def tcp_ping_host(self, host_entry):
        host = host_entry
        port = 443
        
        if ":" in host:
            parts = host.split(":")
            host = parts[0]
            try:
                port = int(parts[1])
            except:
                pass
                
        ms = None
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TIMEOUT_SEC)
            sock.connect((host, port))
            sock.close()
            elapsed = int((time.time() - start) * 1000)
            if elapsed <= TIMEOUT_SEC * 1000:
                ms = elapsed
        except Exception:
            pass
            
        Clock.schedule_once(lambda dt: self.handle_ping_result(host_entry, ms))

    def handle_ping_result(self, host, ms):
        if not self.is_monitoring:
            self.active_threads[host] = False
            return
            
        self.active_threads[host] = False
        
        # Могло произойти так, что результат пришел для хоста, который мы еще не успели инициализировать
        if host not in self.ping_history:
            return
            
        history = self.ping_history[host]
        history.append(ms)
        # Храним историю только за последние 5 секунд (до 5 пингов)
        if len(history) > 5:
            history.pop(0)
            
        valid_pings = [p for p in history if p is not None]
        
        if valid_pings:
            avg_ms = int(sum(valid_pings) / len(valid_pings))
            result_text = f"~{avg_ms} мс"
            color = get_color_from_hex("#03DAC6") 
        else:
            result_text = "н/д"
            color = get_color_from_hex("#CF6679")
            
        if host in self.host_labels:
            self.set_host_loading(host, False)
            self.host_labels[host]['label'].text = result_text
            self.host_labels[host]['label'].color = color

if __name__ == '__main__':
    PingApp().run()
