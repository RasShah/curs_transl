# Сборка и запуск TableScript

Все команды выполняются из корневого каталога проекта `tablescript`.

## 1. Запуск готовой программы в Windows

Для запуска необходима Windows 10 или 11 (x64) с .NET Framework 4.x. Устанавливать Python отдельно не требуется: интерпретатор входит в состав проекта.

```powershell
.\bin\translator.exe examples/basic.tbl -o examples/output.py --show-order
.\bin\translator.exe --python examples/output.py
Get-Content examples/result.csv
```

Первая команда выполняет трансляцию файла `basic.tbl` в Python, вторая запускает полученную программу, третья выводит содержимое CSV-файла.

## 2. Запуск из исходного кода

Для работы с исходным кодом требуется Python 3.10 или новее. Транслятор использует стандартную библиотеку Python, поэтому установка дополнительных пакетов не нужна.

```powershell
python translator.py examples/basic.tbl -o examples/output.py --show-order
python examples/output.py
```

Лексический и синтаксический анализаторы реализованы вручную. Грамматика языка описана в `grammar/table.g`. Использование Flex и Bison не требуется.

## 3. Сборка транслятора

Для создания исполняемого Python-архива используется скрипт `tools/build.py`:

```powershell
python tools/build.py
```

В каталоге `bin` создаётся файл `translator.pyz`, содержащий модули транслятора. Проверить его работу можно следующей командой:

```powershell
python bin/translator.pyz examples/basic.tbl -o examples/output.py
```

Для пересборки комплекта Windows необходимо указать каталог установленного CPython x64:

```powershell
python tools/build.py --portable-python "C:\Path\To\Python312"
```

Вместо указанного пути необходимо подставить фактический путь к каталогу Python. Скрипт собирает `translator.pyz`, копирует интерпретатор в `bin/runtime` и компилирует запускатель `translator.exe` с помощью компилятора C# из .NET Framework. При необходимости путь к компилятору можно задать параметром `--csc`.

Если изменялся только исходный код транслятора на Python, достаточно заново выполнить `python tools/build.py`.

## 4. Тестирование

Для запуска автоматических тестов используется команда:

```powershell
python -m unittest discover -s tests -v
```

При использовании встроенного интерпретатора Python тесты запускаются следующим образом:

```powershell
.\bin\translator.exe --python tools/run_tests.py
```

Тесты проверяют обработку корректных программ, вычисление выражений и обнаружение ошибок во входном коде.

Скрипт `python tools/verify.py` позволяет запустить тесты и пример `basic.tbl`, а также сохранить журналы проверки в каталоге `verification`.

## 5. Сборка с помощью Docker (необязательно)

В проекте предусмотрен Dockerfile. При установленном Docker образ можно собрать командой:

```powershell
docker build -t tablescript:1.0.0 .
docker run --rm tablescript:1.0.0 --help
```

Для сборки используется образ `python:3.12-slim`. При подготовке исходной версии проекта сборка Docker-образа не проверялась. Для обычного запуска транслятора Docker не требуется.
