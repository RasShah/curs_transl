FROM python:3.12-slim AS checked
WORKDIR /app
COPY spreadsheet_lang/ spreadsheet_lang/
COPY translator.py ./
COPY tests/ tests/
COPY examples/ examples/
RUN python -m unittest discover -s tests -v

FROM python:3.12-slim
WORKDIR /app
COPY --from=checked /app/spreadsheet_lang/ spreadsheet_lang/
COPY translator.py /app/translator.py
WORKDIR /work
ENTRYPOINT ["python", "/app/translator.py"]
