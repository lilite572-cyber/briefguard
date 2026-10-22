FROM python:3.12-slim
WORKDIR /study
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
