"""Generate repository-owned UI translations and a simple receiver icon."""

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/hk_avr"

FIELDS_EN = {
    "name": "Name", "host": "IP address or hostname", "port": "TCP port",
    "wake_remote": "Broadlink remote (optional)",
    "wake_device": "Learned device name in Broadlink",
    "wake_command": "Learned Power On command", "wake_timeout": "Wake timeout (seconds)",
}
FIELDS_RU = {
    "name": "Название", "host": "IP-адрес или имя хоста", "port": "TCP-порт",
    "wake_remote": "Пульт Broadlink (необязательно)",
    "wake_device": "Имя обученного устройства в Broadlink",
    "wake_command": "Обученная команда Power On", "wake_timeout": "Ожидание включения (секунды)",
}
DESCRIPTIONS_EN = {
    "name": "A name for this receiver in Home Assistant.",
    "host": "Reserve the receiver's IP address in your router. Do not enter a URL.",
    "port": "The AVR 151S Remote TCP port, normally 10025.",
    "wake_remote": "Used only when Ethernet is unreachable. Learn a discrete Power On first.",
    "wake_device": "Exactly the device value used with remote.learn_command.",
    "wake_command": "Exactly the command value used with remote.learn_command. Never use a power toggle.",
    "wake_timeout": "Maximum wait for TCP after the IR command. The IR command is sent once.",
}
DESCRIPTIONS_RU = {
    "name": "Название ресивера в Home Assistant.",
    "host": "Закрепите IP-адрес ресивера в роутере. Вводите адрес без http://.",
    "port": "TCP-порт управления AVR 151S, обычно 10025.",
    "wake_remote": "Используется, когда Ethernet недоступен. Сначала обучите отдельную команду Power On.",
    "wake_device": "Точное значение device, указанное при обучении через remote.learn_command.",
    "wake_command": "Точное значение command при обучении. Используйте Power On, а не переключатель питания.",
    "wake_timeout": "Сколько ждать TCP после ИК-команды. ИК-команда отправляется один раз.",
}


def translation(ru=False):
    fields = FIELDS_RU if ru else FIELDS_EN
    descriptions = DESCRIPTIONS_RU if ru else DESCRIPTIONS_EN
    form = {
        "title": "Harman Kardon AVR 151S",
        "description": (
            "Управление по Ethernet; Broadlink включает ресивер из глубокого сна. "
            "При сохранении проверяется только TCP, команды питания не отправляются."
            if ru else
            "Control over Ethernet, with optional Broadlink wake from deep standby. "
            "Setup checks TCP only and never sends power commands."
        ),
        "data": fields, "data_description": descriptions,
    }
    return {
        "config": {
            "step": {
                "user": form, "reconfigure": form,
                "offline": {
                    "title": "Ресивер недоступен" if ru else "Receiver unreachable",
                    "description": (
                        "TCP-соединение не установлено. Можно сохранить настройки спящего "
                        "ресивера с Broadlink, но IP-адрес и протокол пока не проверены. "
                        "Команда включения не отправляется. Нажмите «Отправить», чтобы сохранить."
                        if ru else
                        "TCP connection failed. You can save a sleeping receiver with Broadlink, "
                        "but the address and protocol have not been verified. No wake command "
                        "will be sent. Submit to save anyway."
                    ),
                },
            },
            "error": {
                "cannot_connect": (
                    "Нет TCP-соединения. Включите ресивер, проверьте адрес и порт или выберите Broadlink."
                    if ru else "Cannot connect. Turn on the receiver, check host/port, or select Broadlink."
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
            "button": {"mute_toggle": {"name": "Переключить звук" if ru else "Toggle mute"}},
            "binary_sensor": {"ethernet": {"name": "Доступность Ethernet" if ru else "Ethernet connectivity"}},
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
