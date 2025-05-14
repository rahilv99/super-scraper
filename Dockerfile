FROM python:3.12-slim

# Copy requirements.txt
COPY src/requirements.txt ./

# Install the specified packages
RUN pip install -r requirements.txt && \
    python -m spacy download en_core_web_sm

COPY src /app

CMD ["python", "/app/main.py"]