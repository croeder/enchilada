FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY enchilada/ enchilada/
RUN pip install --no-cache-dir .
COPY config.docker.yaml /app/config.docker.yaml
COPY certs/ /certs/
COPY concept_extra.tsv /data/concept_extra.tsv
COPY concept_relationship_extra.tsv /data/concept_relationship_extra.tsv
COPY vocabulary_extra.tsv /data/vocabulary_extra.tsv
ENV ENCHILADA_CONFIG=/app/config.docker.yaml
EXPOSE 8081
CMD ["python", "-m", "enchilada"]
