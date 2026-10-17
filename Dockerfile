From python:3.12-slim
WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh
CMD  ["sh" , "start.sh"]

