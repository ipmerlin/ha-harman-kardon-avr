"""Generate repository-owned UI translations and a simple receiver icon."""

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/hk_avr"

FIELDS_EN = {
    "name": "Name", "host": "IP address or hostname", "port": "TCP port",
    "wake_remote": "IR remote (optional)",
    "wake_device": "Device name in the command library",
    "wake_command": "Power On command name", "wake_timeout": "Wake timeout (seconds)",
    "learn_power_on": "Learn Power On during setup",
}
FIELDS_RU = {
    "name": "Название", "host": "IP-адрес или имя хоста", "port": "TCP-порт",
    "wake_remote": "ИК-пульт (необязательно)",
    "wake_device": "Имя устройства в библиотеке команд",
    "wake_command": "Имя команды Power On", "wake_timeout": "Ожидание включения (секунды)",
    "learn_power_on": "Обучить Power On при настройке",
}
DESCRIPTIONS_EN = {
    "name": "A name for this receiver in Home Assistant.",
    "host": "Reserve the receiver's IP address in your router. Do not enter a URL.",
    "port": "The AVR 151S Remote TCP port, normally 10025.",
    "wake_remote": "Used when Ethernet is unreachable. Select your IR transmitter.",
    "wake_device": "Use an existing device name or choose one for learning below.",
    "wake_command": "Use an existing command name or choose one for learning. Use discrete Power On.",
    "wake_timeout": "Maximum wait for TCP after the IR command. The IR command is sent once.",
    "learn_power_on": "Optional. The next step explains learning before it starts. Uncheck to use an existing command.",
}
DESCRIPTIONS_RU = {
    "name": "Название ресивера в Home Assistant.",
    "host": "Закрепите IP-адрес ресивера в роутере. Вводите адрес без http://.",
    "port": "TCP-порт управления AVR 151S, обычно 10025.",
    "wake_remote": "Используется, когда Ethernet недоступен. Выберите ваш ИК-передатчик.",
    "wake_device": "Имя уже обученного устройства или новое имя для обучения ниже.",
    "wake_command": "Имя существующей команды или новое имя для обучения. Используйте отдельную Power On.",
    "wake_timeout": "Сколько ждать TCP после ИК-команды. ИК-команда отправляется один раз.",
    "learn_power_on": "Необязательно. Перед запуском появится инструкция. Оставьте выключенным для готовой команды.",
}

BUTTON_LABELS = {
    "mute_toggle": ("Toggle mute", "Переключить звук"),
    "play": ("Play", "Воспроизведение"), "pause": ("Pause", "Пауза"),
    "next": ("Next track", "Следующий трек"),
    "previous": ("Previous track", "Предыдущий трек"),
    "forward": ("Fast forward", "Перемотка вперёд"),
    "reverse": ("Rewind", "Перемотка назад"),
    "up": ("Up", "Вверх"), "down": ("Down", "Вниз"),
    "left": ("Left", "Влево"), "right": ("Right", "Вправо"),
    "ok": ("OK", "ОК"), "back": ("Back", "Назад"),
    "home": ("Home", "Главное меню"), "info": ("Info", "Информация"),
    "options": ("Options", "Параметры"),
    "sleep": ("Sleep / sleep timer", "Sleep / таймер сна"),
}


def translation(ru=False):
    fields = FIELDS_RU if ru else FIELDS_EN
    descriptions = DESCRIPTIONS_RU if ru else DESCRIPTIONS_EN
    form = {
        "title": "Harman Kardon AVR 151S",
        "description": (
            "Управление по Ethernet; выбранный ИК-пульт включает ресивер из глубокого сна. "
            "При сохранении проверяется только TCP, команды питания не отправляются."
            if ru else
            "Control over Ethernet, with optional IR wake from deep standby. "
            "Setup checks TCP only and never sends power commands."
        ),
        "data": fields, "data_description": descriptions,
    }
    return {
        "config": {
            "step": {
                "user": form, "reconfigure": form,
                "learn_confirm": {
                    "title": "Обучение команды Power On" if ru else "Learn Power On",
                    "description": (
                        "Пульт: {remote}. Команда будет сохранена как {device} / {command}. "
                        "Подготовьте штатный пульт ресивера. Нажмите «Подтвердить», дождитесь "
                        "режима обучения и нажмите отдельную кнопку Power On, направив штатный "
                        "пульт на ИК-передатчик. На нажатие отводится 30 секунд. "
                        "Существующий код с этими именами будет заменён. Команда питания не отправляется."
                        if ru else
                        "Remote: {remote}. Save as {device} / {command}. Prepare the original AVR remote. "
                        "Submit, wait for learning mode, then point it at the IR transmitter and press "
                        "the discrete Power On button within 30 seconds. An existing code with these "
                        "names will be replaced. No power command is transmitted."
                    ),
                },
                "learn_progress": {"title": "Ожидание Power On" if ru else "Waiting for Power On"},
                "learn_done": {
                    "title": "Команда обучена" if ru else "Command learned",
                    "description": (
                        "ИК-пульт завершил обучение. Нажмите «Подтвердить», чтобы сохранить настройки "
                        "ресивера. Передача команды и фактическое включение ещё не проверялись."
                        if ru else
                        "The IR remote completed learning. Submit to save the receiver configuration. "
                        "Transmission and physical power-on have not been tested."
                    ),
                },
                "learn_failed": {
                    "title": "Обучение не подтверждено" if ru else "Learning not confirmed",
                    "description": (
                        "Не удалось подтвердить обучение: проверьте, что ИК-пульт включён и доступен. "
                        "Повторите обучение или сохраните настройки без него. Необученная команда "
                        "не сможет включить ресивер. Автоматического повтора нет."
                        if ru else
                        "Learning could not be confirmed. Check that the IR remote is enabled and "
                        "available. Retry or save without learning. An unlearned command cannot wake "
                        "the AVR. Learning is not retried automatically."
                    ),
                    "menu_options": {
                        "learn_confirm": "Повторить обучение" if ru else "Retry learning",
                        "save_without_learning": "Сохранить без обучения" if ru else "Save without learning",
                    },
                },
                "offline": {
                    "title": "Ресивер недоступен" if ru else "Receiver unreachable",
                    "description": (
                        "TCP-соединение не установлено. Можно сохранить настройки спящего "
                        "ресивера с ИК-пультом, но IP-адрес и протокол пока не проверены. "
                        "Команда включения не отправляется. Нажмите «Отправить», чтобы сохранить."
                        if ru else
                        "TCP connection failed. You can save a sleeping receiver with an IR remote, "
                        "but the address and protocol have not been verified. No wake command "
                        "will be sent. Submit to save anyway."
                    ),
                },
            },
            "progress": {
                "learn_power_on": (
                    "Дождитесь сигнала ИК-передатчика или уведомления HA. Направьте на него штатный "
                    "пульт и нажмите Power On. Ожидание — до 30 секунд."
                    if ru else
                    "Wait for the transmitter signal or HA notification, then point the original "
                    "remote at it and press Power On. Waiting up to 30 seconds."
                ),
            },
            "error": {
                "cannot_connect": (
                    "Нет TCP-соединения. Включите ресивер, проверьте адрес и порт или выберите ИК-пульт."
                    if ru else "Cannot connect. Turn on the receiver, check host/port, or select an IR remote."
                ),
                "invalid_config": (
                    "Проверьте адрес, название и заполнение параметров ИК-команды."
                    if ru else "Check the host, name and IR command fields."
                ),
            },
            "abort": {
                "already_configured": "Этот адрес и порт уже добавлены." if ru else "This host and port are already configured.",
                "reconfigure_successful": "Настройки сохранены." if ru else "Configuration updated.",
            },
        },
        "entity": {
            "button": {key: {"name": labels[int(ru)]} for key, labels in BUTTON_LABELS.items()},
            "binary_sensor": {"ethernet": {"name": "Доступность Ethernet" if ru else "Ethernet connectivity"}},
            "select": {"source": {"name": "Вход" if ru else "Input"}},
            "remote": {"network_remote": {"name": "Сетевой пульт" if ru else "Network remote"}},
        },
    }


if __name__ == "__main__":
    (COMPONENT / "translations").mkdir(exist_ok=True)
    for language in ("en", "ru"):
        content = json.dumps(translation(language == "ru"), ensure_ascii=False, indent=2) + "\n"
        (COMPONENT / f"translations/{language}.json").write_text(content, encoding="utf-8")
        if language == "en":
            (COMPONENT / "strings.json").write_text(content, encoding="utf-8")
    # A generic receiver silhouette; no manufacturer trademark artwork is reused.
    for size, filename in ((256, "icon.png"), (512, "icon@2x.png")):
        image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((42, 136, 470, 370), radius=28, fill="#152632")
        draw.rounded_rectangle((76, 172, 330, 240), radius=9, fill="#274759")
        draw.line((98, 206, 286, 206), fill="#65dce4", width=9)
        draw.ellipse((358, 188, 434, 264), fill="#e9f1f4")
        draw.ellipse((86, 286, 112, 312), fill="#65dce4")
        draw.line((150, 299, 316, 299), fill="#6e8999", width=9)
        draw.rectangle((90, 370, 140, 388), fill="#152632")
        draw.rectangle((370, 370, 420, 388), fill="#152632")
        for directory in (ROOT / "brand", COMPONENT / "brand"):
            directory.mkdir(exist_ok=True)
            image.resize((size, size), Image.Resampling.LANCZOS).save(directory / filename)
