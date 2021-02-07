FROM python:3.7-slim
COPY templates ./templates
COPY mysql-operator.py ./mysql-operator.py
RUN pip install --no-cache-dir \
      wheel
RUN pip install --no-cache-dir \
      jinja2 \
      kopf \
      kubernetes \
      pyyaml
CMD kopf run ./mysql-operator.py
