# Сетевые команды AVR Remote

Транспорт — существующий TCP/10025, запрос `POST AVR HTTP/1.1`, XML
`harman/avr/common/control` с `name`, `zone=Main Zone` и пустым `para`.
Исключение — `source-selection`, где `para` содержит имя входа.

Команды 0.2.0 сверены с первичным исходным кодом:
[KarimGeiger/HKAPI, lib/Actions](https://github.com/KarimGeiger/HKAPI/tree/master/lib/Actions).
У этих действий `hasResponse()` возвращает false. Пакет и XML генерируются
собственным asyncio-клиентом; PHP-код не включён в интеграцию.

| Значение для `remote.send_command` | Имя в XML |
| --- | --- |
| `play`, `pause`, `next`, `previous` | То же имя |
| `forward`, `reverse` | То же имя |
| `up`, `down`, `left`, `right`, `ok`, `back`, `home` | То же имя |
| `info`, `options`, `sleep` | То же имя |
| `volume_up`, `volume_down` | `volume-up`, `volume-down` |
| `mute_toggle` | `mute-toggle` |

Питание и входы сохраняют существующие `power-on`, `power-off`, `source-selection`.
`heart-alive` не добавлен: полезная обратная связь для AVR 151S не установлена,
а фоновое удержание устройства от сна не является целью интеграции.

Сверка имён протокола не доказывает физическое выполнение каждой команды
именно AVR 151S. Реакция зависит от модели, прошивки, источника и открытого меню.
Нет подтверждения точной громкости, mute, фактического питания/входа, позиции
трека или таймера Sleep. Включение из глубокого Off по отключённому Ethernet
не заявляется. Surround/EQ/уровни каналов также не заявляются.
