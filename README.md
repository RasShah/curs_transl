# TableScript 1.0.0

Транслятор собственного языка электронных таблиц в Python. Вход — файл `.tbl` в UTF-8; результат трансляции — самостоятельная программа `.py`, которая вычисляет все ячейки и сохраняет CSV. Программа реализована на Python 3.10+ и использует только стандартную библиотеку. `eval` и `exec` для входного языка не используются.

## Готовый запуск в Windows 10 и 11 x64

Распакуйте весь архив. Откройте PowerShell в каталоге `tablescript`. Сохраняйте рядом `bin/translator.exe`, `bin/translator.pyz` и папку `bin/runtime`.

```powershell
.\bin\translator.exe examples/basic.tbl -o examples/output.py --show-order
.\bin\translator.exe --python examples/output.py
Get-Content examples/result.csv
```

Устанавливать Python и скачивать библиотеки для этого варианта не нужно. `translator.exe` — скомпилированный запускатель на C#, который вызывает поставляемый CPython 3.12 x64 и Python-код транслятора. Это не компиляция модулей Python в машинный код. Требуется стандартный для Windows 10/11 .NET Framework 4.x.

Результат примера без заголовков строк и столбцов:

```csv
120,3,360
80,2,160
,,520
```

`C1 = 360`, `C2 = 160`, `C3 = 520`. Относительный путь из `export` отсчитывается от каталога **созданной Python-программы**, поэтому CSV находится в `examples/result.csv`.

## Запуск исходного кода

Нужен Python 3.10 или новее. Внешних зависимостей нет.

```text
python translator.py examples/basic.tbl -o examples/output.py
python examples/output.py
python -m spreadsheet_lang --help
python bin/translator.pyz --version
```

Для команды `translator input.tbl -o output.py` установите проект в виртуальное окружение:

```text
python -m venv .venv
```

Активируйте его: Windows — `.venv\Scripts\activate`, Linux/macOS — `source .venv/bin/activate`. Затем:

```text
python -m pip install .
translator examples/basic.tbl -o examples/output.py
python examples/output.py
```

`pip install .` использует setuptools как инструмент упаковки; если setuptools отсутствует, pip может скачать его. Для запуска через `python translator.py` установка и сеть не нужны.

## Пример языка

```text
A1 = 120;
B1 = 3;
A2 = 80;
B2 = 2;
fill C1:C2 = A1 * B1;
C3 = SUM(C1:C2);
export "result.csv";
```

Поддерживаются числа, строки, `true`/`false`, `+ - * / %`, сравнения, скобки, диапазоны, `SUM`, `AVG`, `MIN`, `MAX`, `IF`, относительные, абсолютные и смешанные ссылки. Комментарии: `#`, `//`, `/* ... */`.

Объявления могут идти в любом порядке. Каждая ячейка определяется один раз. Все ссылки, включая ячейки внутри диапазонов и обе ветви `IF`, проверяются до генерации кода. Граф зависимостей обнаруживает циклы. Во время выполнения `IF` вычисляет только выбранную ветвь выражения.

Диагностика содержит имя файла, строку, позицию, код и объяснение. Ошибочная трансляция сохраняет прежний выходной файл. Вычисления завершаются до начала записи CSV; CSV заменяется атомарно.

## Проверка и материалы

```text
python -m unittest discover -s tests -v
python tools/verify.py
python tools/inspect_program.py examples/basic.tbl
```

- `USER_GUIDE.md` — полная справка по допустимым конструкциям и ошибкам.
- `BUILD.md` — упаковка, Windows-сборка и Docker.
- `grammar/table.g` — исходная EBNF-грамматика; анализатор написан вручную, генератор не нужен.
- `ARCHITECTURE.md` и `docs/diagrams/` — архитектура и схемы.
- `spreadsheet_lang/` — полный исходный код.
- `tests/invalid/` — 44 ошибочных входных файла; `tests/cases.json` задаёт ожидаемые результаты для 48 файловых примеров.
- `examples/expected/` — эталонные CSV; `examples/output.py` и `examples/result.csv` — фактически полученные результаты.
- `verification/` — журналы реальных проверок и запуска примера.
- `Курсовая_работа.docx` — пояснительная записка с техническим заданием, схемами и примером работы.

Проверенные версии платформы и результаты находятся в `verification/tests.log`. Dockerfile включён; факт его локального запуска отмечен в `BUILD.md`.
